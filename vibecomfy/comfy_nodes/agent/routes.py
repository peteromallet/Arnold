from __future__ import annotations

import asyncio
import dataclasses
import json
import logging
import os
from pathlib import Path
from typing import Any, Mapping

_LOGGER = logging.getLogger(__name__)

from .contracts import FailureKind, classify_failure, failure_envelope
from .provider import readiness, handle_credential_submission
from .hivemind_feedback import submit_hivemind_feedback


def _handle_roundtrip(
    payload: dict[str, Any], *, schema_provider: Any = None
) -> dict[str, Any]:
    """Torch-free core: convert UI graph + emit, return enriched graph + change report.

    All engine imports are lazy so this function is importable without ComfyUI or torch.
    Call from tests directly; the aiohttp wrapper below delegates to this.
    """
    from vibecomfy.ingest.normalize import convert_to_vibe_format  # noqa: PLC0415
    from vibecomfy.porting.layout import evaluate_felt_delta  # noqa: PLC0415
    from vibecomfy.porting.emit.ui import emit_ui_json  # noqa: PLC0415
    from vibecomfy.schema import get_schema_provider  # noqa: PLC0415

    try:
        if schema_provider is None:
            schema_provider = get_schema_provider("local")
        recovery_report: list = []
        change_report_out: list = []
        wf = convert_to_vibe_format(payload["graph"])
        emitted_ui = emit_ui_json(
            wf,
            schema_provider=schema_provider,
            recovery_report=recovery_report,
            change_report_out=change_report_out,
            guard_original_ui=payload["graph"],
        )
        change_dict = dataclasses.asdict(change_report_out[0]) if change_report_out else {}
        reroute_uids = frozenset(
            (node.uid or node_id)
            for node_id, node in wf.nodes.items()
            if node.class_type == "Reroute"
        )
        felt_report = (
            evaluate_felt_delta(
                None,
                emitted_ui,
                change_report_out[0],
                reroute_uids=reroute_uids,
            )
            if change_report_out
            else None
        )
        return {
            "graph": emitted_ui,
            "report": {
                "change": change_dict,
                "recovery": recovery_report,
                "felt": dataclasses.asdict(felt_report) if felt_report is not None else {},
            },
            "version": 1,
        }
    except Exception as exc:
        return {"error": str(exc), "kind": type(exc).__name__}


def _handle_agent_status(params: dict[str, Any] | None = None) -> dict[str, Any]:
    params = params or {}
    route = params.get("route") if isinstance(params.get("route"), str) else None
    model = params.get("model") if isinstance(params.get("model"), str) else None
    _LOGGER.info("/vibecomfy/agent/status request route=%r model=%r", route, model)
    try:
        ready_payload = readiness(route=route, model=model)
    except Exception as exc:
        _LOGGER.exception("/vibecomfy/agent/status readiness() raised an exception")
        raise
    ok = bool(ready_payload.get("ready"))
    status: dict[str, Any] = {
        **ready_payload,
        "ok": ok,
        "readiness": "ready" if ok else "unavailable",
    }
    if not ok and not status.get("provider_available") and "error" not in status:
        status["error"] = str(status.get("reason") or "Provider is unavailable.")
    _LOGGER.info(
        "/vibecomfy/agent/status response ready=%s route=%s requested_route=%s route_options=%s",
        status.get("ready"),
        status.get("route"),
        status.get("requested_route"),
        list(status.get("route_options", {}).keys()),
    )
    return status





def _handle_agent_credentials(
    payload: Any,
    *,
    env_path: Any = None,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return failure_envelope(
            FailureKind.MISSING_REQUIRED_FIELD,
            "credentials",
            agent_failure_context={"explanation": "Request body must be a JSON object."},
        ).to_dict()
    try:
        return handle_credential_submission(
            payload,
            env_path=Path(env_path) if env_path is not None else None,
        )
    except Exception as exc:
        return classify_failure("ingest", exc).to_dict()




def _handle_vibecomfy_submit_rating(payload: Any) -> tuple[dict[str, Any], int]:
    result, status = submit_hivemind_feedback(payload)
    if result.get("ok") is True and 200 <= status < 300:
        return result, 201
    return result, status


def _to_serializable(result: Any) -> Any:
    """Convert a FailureEnvelope/dataclass result to a plain dict for JSON."""
    if result is None:
        return {}
    if isinstance(result, dict):
        return result
    if hasattr(result, "to_dict") and callable(result.to_dict):
        return result.to_dict()
    return {"error": "Non-serializable result", "repr": repr(result)}


def register_agent_edit_routes(app) -> None:
    """Register the /vibecomfy/agent-edit/* routes on a ComfyUI PromptServer *app*.

    Includes the legacy POST /agent/edit alias for backward compatibility.
    This function is a no-op when ``VIBECOMFY_HEADLESS=1`` is set in the
    environment, so importing this module outside a ComfyUI server does not
    trigger ``aiohttp`` or ``server`` side effects.

    Parameters
    ----------
    app:
        A ComfyUI ``PromptServer`` instance whose ``.routes`` attribute exposes
        an ``aiohttp.RouteTableDef``.
    """
    from pathlib import Path as _Path  # noqa: PLC0415
    from aiohttp import web as _web  # noqa: PLC0415
    from .edit import (  # noqa: PLC0415
        _safe_session_id as _safe_session_id,
        _SESSION_ROOT as _EDIT_SESSION_ROOT,
        handle_agent_edit,
        read_session_bundle,
        read_session_chat,
        read_session_json,
    )
    from .session import (  # noqa: PLC0415
        accept_turn,
        reject_turn,
        rebaseline_session,
    )
    from .contracts import (
        FailureKind as _FK,
        classify_failure as _classify_failure,
        ensure_agent_edit_response_contract as _ensure_contract,
        failure_envelope as _failure_envelope,
    )

    _SESSION_ROOT = _Path(_EDIT_SESSION_ROOT)

    def _client_id_from_payload(payload: Any) -> str | None:
        cid = payload.get("client_id") if isinstance(payload, dict) else None
        if isinstance(cid, str) and cid.strip():
            return cid
        return None

    def _session_id_from_query(request) -> str:  # type: ignore[no-untyped-def]
        return _safe_session_id(request.query.get("session_id"))

    def _json_error(message: str, stage: str = "agent_edit", status: int = 400):  # type: ignore[no-untyped-def]
        return _web.json_response(
            _ensure_contract(
                _failure_envelope(
                    _FK.MISSING_REQUIRED_FIELD,
                    stage,
                    agent_failure_context={"explanation": message},
                ).to_dict(),
                stage=stage,
            ),
            status=status,
        )

    @app.routes.post("/vibecomfy/agent-edit")
    async def _agent_edit_route(request):  # type: ignore[no-untyped-def]
        try:
            payload = await request.json()
        except Exception as exc:
            return _json_error(f"Request body must be valid JSON: {exc}", stage="agent_edit")
        if not isinstance(payload, dict):
            return _json_error("Request body must be a JSON object.", stage="agent_edit")
        try:
            result = await asyncio.to_thread(
                handle_agent_edit,
                payload,
                client_id=_client_id_from_payload(payload),
            )
        except Exception as exc:
            failure = _classify_failure("agent_edit", exc)
            return _web.json_response(
                _ensure_contract(failure.to_dict(), stage="agent_edit"),
                status=500,
            )
        if not isinstance(result, dict):
            return _json_error("handle_agent_edit returned a non-dict result.", stage="agent_edit", status=500)
        if result.get("status") == "error":
            return _web.json_response(result, status=400)
        return _web.json_response(result)

    @app.routes.post("/agent/edit")
    async def _legacy_agent_edit_route(request):  # type: ignore[no-untyped-def]
        try:
            payload = await request.json()
        except Exception as exc:
            return _json_error(f"Request body must be valid JSON: {exc}", stage="agent_edit")
        if not isinstance(payload, dict):
            return _json_error("Request body must be a JSON object.", stage="agent_edit")
        try:
            result = await asyncio.to_thread(handle_agent_edit, payload)
        except Exception as exc:
            failure = _classify_failure("agent_edit", exc)
            return _web.json_response(
                _ensure_contract(failure.to_dict(), stage="agent_edit"),
                status=500,
            )
        if not isinstance(result, dict):
            return _json_error("handle_agent_edit returned a non-dict result.", stage="agent_edit", status=500)
        if result.get("status") == "error":
            return _web.json_response(result, status=400)
        return _web.json_response(result)

    @app.routes.post("/vibecomfy/agent-edit/accept")
    async def _agent_edit_accept_route(request):  # type: ignore[no-untyped-def]
        try:
            payload = await request.json()
        except Exception as exc:
            return _json_error(f"Request body must be valid JSON: {exc}", stage="accept")
        if not isinstance(payload, dict):
            return _json_error("Request body must be a JSON object.", stage="accept")
        session_id = _safe_session_id(payload.get("session_id"))
        turn_id = payload.get("turn_id")
        if not isinstance(turn_id, str) or not turn_id.strip():
            return _json_error("turn_id is required.", stage="accept")
        try:
            result = await asyncio.to_thread(
                accept_turn,
                session_root=_SESSION_ROOT,
                session_id=session_id,
                turn_id=turn_id,
                client_graph_hash=payload.get("client_graph_hash"),
                request_payload=payload,
                idempotency_key=payload.get("idempotency_key")
                if isinstance(payload.get("idempotency_key"), str)
                else None,
            )
        except Exception as exc:
            failure = _classify_failure("accept", exc)
            return _web.json_response(
                _ensure_contract(failure.to_dict(), stage="accept"),
                status=500,
            )
        return _web.json_response(_to_serializable(result))

    @app.routes.post("/vibecomfy/agent-edit/reject")
    async def _agent_edit_reject_route(request):  # type: ignore[no-untyped-def]
        try:
            payload = await request.json()
        except Exception as exc:
            return _json_error(f"Request body must be valid JSON: {exc}", stage="reject")
        if not isinstance(payload, dict):
            return _json_error("Request body must be a JSON object.", stage="reject")
        session_id = _safe_session_id(payload.get("session_id"))
        turn_id = payload.get("turn_id")
        if not isinstance(turn_id, str) or not turn_id.strip():
            return _json_error("turn_id is required.", stage="reject")
        try:
            result = await asyncio.to_thread(
                reject_turn,
                session_root=_SESSION_ROOT,
                session_id=session_id,
                turn_id=turn_id,
                client_graph_hash=payload.get("client_graph_hash"),
                request_payload=payload,
                idempotency_key=payload.get("idempotency_key")
                if isinstance(payload.get("idempotency_key"), str)
                else None,
            )
        except Exception as exc:
            failure = _classify_failure("reject", exc)
            return _web.json_response(
                _ensure_contract(failure.to_dict(), stage="reject"),
                status=500,
            )
        return _web.json_response(_to_serializable(result))

    @app.routes.post("/vibecomfy/agent-edit/rebaseline")
    async def _agent_edit_rebaseline_route(request):  # type: ignore[no-untyped-def]
        try:
            payload = await request.json()
        except Exception as exc:
            return _json_error(f"Request body must be valid JSON: {exc}", stage="rebaseline")
        if not isinstance(payload, dict):
            return _json_error("Request body must be a JSON object.", stage="rebaseline")
        session_id = _safe_session_id(payload.get("session_id"))
        try:
            result = await asyncio.to_thread(
                rebaseline_session,
                session_root=_SESSION_ROOT,
                session_id=session_id,
                request_payload=payload,
                idempotency_key=payload.get("idempotency_key")
                if isinstance(payload.get("idempotency_key"), str)
                else None,
            )
        except Exception as exc:
            failure = _classify_failure("rebaseline", exc)
            return _web.json_response(
                _ensure_contract(failure.to_dict(), stage="rebaseline"),
                status=500,
            )
        return _web.json_response(_to_serializable(result))

    @app.routes.get("/vibecomfy/agent-edit/chat")
    async def _agent_edit_chat_route(request):  # type: ignore[no-untyped-def]
        session_id = _session_id_from_query(request)
        try:
            result = await asyncio.to_thread(
                read_session_chat,
                _SESSION_ROOT,
                session_id,
            )
        except Exception as exc:
            failure = _classify_failure("chat", exc)
            return _web.json_response(
                _ensure_contract(failure.to_dict(), stage="chat"),
                status=500,
            )
        return _web.json_response(_to_serializable(result))

    @app.routes.get("/vibecomfy/agent-edit/session-bundle")
    async def _agent_edit_session_bundle_route(request):  # type: ignore[no-untyped-def]
        session_id = _session_id_from_query(request)
        try:
            result = await asyncio.to_thread(
                read_session_bundle,
                _SESSION_ROOT,
                session_id,
            )
        except Exception as exc:
            failure = _classify_failure("session_bundle", exc)
            return _web.json_response(
                _ensure_contract(failure.to_dict(), stage="session_bundle"),
                status=500,
            )
        return _web.json_response(_to_serializable(result))

    @app.routes.get("/vibecomfy/agent-edit/session-json")
    async def _agent_edit_session_json_route(request):  # type: ignore[no-untyped-def]
        session_id = _session_id_from_query(request)
        try:
            result = await asyncio.to_thread(
                read_session_json,
                _SESSION_ROOT,
                session_id,
            )
        except Exception as exc:
            failure = _classify_failure("session_json", exc)
            return _web.json_response(
                _ensure_contract(failure.to_dict(), stage="session_json"),
                status=500,
            )
        return _web.json_response(_to_serializable(result))


# ── Route registration (guarded: no-op when VIBECOMFY_HEADLESS=1) ──────────

if os.environ.get("VIBECOMFY_HEADLESS") != "1":
    try:
        from aiohttp import web as _web  # noqa: PLC0415
        from server import PromptServer as _PromptServer  # noqa: PLC0415

        @_PromptServer.instance.routes.post("/vibecomfy/roundtrip")
        async def roundtrip_route(request):  # type: ignore[no-untyped-def]
            _LOGGER.info("/vibecomfy/roundtrip request")
            try:
                payload = await request.json()
            except Exception as exc:
                return _web.json_response(
                    {"error": str(exc), "kind": type(exc).__name__}, status=400
                )
            result = _handle_roundtrip(payload)
            if "error" in result:
                return _web.json_response(result, status=400)
            return _web.json_response(result)


        @_PromptServer.instance.routes.post("/vibecomfy/agent-edit/rating")
        async def agent_edit_rating_route(request):  # type: ignore[no-untyped-def]
            _LOGGER.info("/vibecomfy/agent-edit/rating request")
            try:
                payload = await request.json()
            except Exception as exc:
                return _web.json_response(
                    {
                        "ok": False,
                        "error": "validation",
                        "detail": f"Request body must be valid JSON: {exc}",
                    },
                    status=400,
                )
            result, status = await asyncio.to_thread(_handle_vibecomfy_submit_rating, payload)
            return _web.json_response(result, status=status)

        @_PromptServer.instance.routes.get("/vibecomfy/agent/status")
        async def agent_status_route(request):  # type: ignore[no-untyped-def]
            try:
                payload = _handle_agent_status(dict(request.query))
                return _web.json_response(payload)
            except Exception as exc:
                _LOGGER.exception("/vibecomfy/agent/status route handler failed")
                return _web.json_response(
                    {
                        "ok": False,
                        "ready": False,
                        "error": f"Status handler error: {exc}",
                        "route_options": {},
                    },
                    status=500,
                )

        @_PromptServer.instance.routes.post("/vibecomfy/agent/credentials")
        async def agent_credentials_route(request):  # type: ignore[no-untyped-def]
            _LOGGER.info("/vibecomfy/agent/credentials request")
            try:
                payload = await request.json()
            except Exception as exc:
                return _web.json_response(
                    failure_envelope(
                        FailureKind.MISSING_REQUIRED_FIELD,
                        "credentials",
                        agent_failure_context={
                            "explanation": f"Request body must be valid JSON: {exc}"
                        },
                    ).to_dict(),
                    status=400,
                )
            result = _handle_agent_credentials(payload)
            return _web.json_response(result, status=400 if result.get("ok") is False else 200)

        # Also register the agent edit route on the global PromptServer instance
        register_agent_edit_routes(_PromptServer.instance)
        _LOGGER.info("vibecomfy agent routes module loaded and all routes registered.")

    except ImportError as _routes_import_exc:
        _LOGGER.warning("vibecomfy agent routes module could not register server routes: %s", _routes_import_exc)
