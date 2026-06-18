from __future__ import annotations

import asyncio
import dataclasses
import json
import logging
import os
from pathlib import Path
from typing import Any, Mapping

_LOGGER = logging.getLogger(__name__)

from .contracts import (
    FailureKind,
    classify_failure,
    ensure_agent_edit_response_contract,
    failure_envelope,
)
from .provider import readiness, handle_credential_submission
from .hivemind_feedback import submit_hivemind_feedback


def _handle_agent_executor(
    payload: dict[str, Any],
    *,
    client_id: str | None = None,
) -> dict[str, Any]:
    """Run the stateless executor pipeline and return a JSON-serializable result."""
    # Lazy import to avoid pulling executor (and its heavy ingestion graph
    # imports) into the module-level import graph of routes.py.
    from vibecomfy.executor.contracts import ClassifyDecision, ExecutorRequest
    from vibecomfy.executor.core import run_executor

    if not isinstance(payload, Mapping):
        message = "ExecutorRequest payload must be a JSON object."
        failure = failure_envelope(
            FailureKind.VALIDATION_ERROR,
            "executor",
            agent_failure_context={"explanation": message},
        ).to_dict()
        failure.update({
            "report": {"executor": {"plan": ClassifyDecision.respond_only().to_dict()}},
            "failure_kind": FailureKind.VALIDATION_ERROR.value,
            "failure_stage": "executor",
            "failure_message": message,
        })
        return {
            **failure,
        }

    try:
        request = ExecutorRequest.from_payload(payload)
    except ValueError as exc:
        failure = failure_envelope(
            FailureKind.MISSING_REQUIRED_FIELD,
            "request",
            agent_failure_context={"explanation": str(exc)},
        ).to_dict()
        failure.update({
            "report": {"executor": {"plan": ClassifyDecision.respond_only().to_dict()}},
            "failure_kind": FailureKind.MISSING_REQUIRED_FIELD.value,
            "failure_stage": "request",
            "failure_message": str(exc),
        })
        return {
            **failure,
        }

    try:
        result = run_executor(request, client_id=client_id)
        return result.to_dict()
    except Exception as exc:
        failure = failure_envelope(
            FailureKind.VALIDATION_ERROR,
            "executor",
            agent_failure_context={"explanation": f"Unexpected executor error: {exc}"},
        ).to_dict()
        failure.update({
            "report": {"executor": {"plan": ClassifyDecision.respond_only().to_dict()}},
            "failure_kind": FailureKind.VALIDATION_ERROR.value,
            "failure_stage": "executor",
            "failure_message": f"Unexpected executor error: {exc}",
        })
        return {
            **failure,
        }


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



def _validated_failure_response(
    stage: str,
    failure: Any,
) -> dict[str, Any]:
    response = failure.to_dict() if hasattr(failure, "to_dict") else dict(failure)
    recovery = _extract_failure_recovery(response)
    if recovery is not None:
        response.setdefault("rebaseline_recovery", recovery)
        outcome = response.get("outcome")
        if isinstance(outcome, Mapping) and outcome.get("kind") == "error":
            response["outcome"] = {
                **dict(outcome),
                "rebaseline_recovery": dict(outcome.get("rebaseline_recovery"))
                if isinstance(outcome.get("rebaseline_recovery"), Mapping)
                else recovery,
            }
    return ensure_agent_edit_response_contract(response, stage=stage)



def _extract_failure_recovery(response: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(response, Mapping):
        return None
    top_level = response.get("rebaseline_recovery")
    if isinstance(top_level, Mapping):
        return dict(top_level)
    contexts: list[Any] = [response.get("agent_failure_context")]
    outcome = response.get("outcome")
    if isinstance(outcome, Mapping):
        outcome_recovery = outcome.get("rebaseline_recovery")
        if isinstance(outcome_recovery, Mapping):
            return dict(outcome_recovery)
        contexts.append(outcome.get("agent_failure_context"))
    debug = response.get("debug")
    if isinstance(debug, Mapping):
        failure_debug = debug.get("failure")
        if isinstance(failure_debug, Mapping):
            contexts.append(failure_debug.get("agent_failure_context"))
    for context in contexts:
        if not isinstance(context, Mapping):
            continue
        issues = context.get("issues")
        if not isinstance(issues, list):
            continue
        for issue in issues:
            if not isinstance(issue, Mapping):
                continue
            recovery = issue.get("rebaseline_recovery")
            if isinstance(recovery, Mapping):
                return dict(recovery)
    return None

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


def register_agent_edit_routes(app) -> None:
    """Register the /agent/edit route on a ComfyUI PromptServer *app*.

    This function is a no-op when ``VIBECOMFY_HEADLESS=1`` is set in the
    environment, so importing this module outside a ComfyUI server does not
    trigger ``aiohttp`` or ``server`` side effects.

    Parameters
    ----------
    app:
        A ComfyUI ``PromptServer`` instance whose ``.routes`` attribute exposes
        an ``aiohttp.RouteTableDef``.
    """
    from .edit import handle_agent_edit  # noqa: PLC0415
    from .contracts import (
        FailureKind as _FK,
        classify_failure as _classify_failure,
        ensure_agent_edit_response_contract as _ensure_contract,
        failure_envelope as _failure_envelope,
    )

    @app.routes.post("/agent/edit")
    async def _agent_edit_route(request):  # type: ignore[no-untyped-def]
        try:
            payload = await request.json()
        except Exception as exc:
            return app.web.json_response(
                _ensure_contract(
                    _failure_envelope(
                        _FK.MISSING_REQUIRED_FIELD,
                        "agent_edit",
                        agent_failure_context={
                            "explanation": f"Request body must be valid JSON: {exc}"
                        },
                    ).to_dict(),
                    stage="agent_edit",
                ),
                status=400,
            )
        try:
            result = await asyncio.to_thread(handle_agent_edit, payload)
        except Exception as exc:
            failure = _classify_failure("agent_edit", exc)
            return app.web.json_response(
                _ensure_contract(failure.to_dict(), stage="agent_edit"),
                status=500,
            )
        if not isinstance(result, dict):
            return app.web.json_response(
                _ensure_contract(
                    _failure_envelope(
                        _FK.VALIDATION_ERROR,
                        "agent_edit",
                        agent_failure_context={
                            "explanation": "handle_agent_edit returned a non-dict result."
                        },
                    ).to_dict(),
                    stage="agent_edit",
                ),
                status=500,
            )
        if result.get("status") == "error":
            return app.web.json_response(result, status=400)
        return app.web.json_response(result)


# ── Route registration (guarded: no-op when VIBECOMFY_HEADLESS=1) ──────────

if os.environ.get("VIBECOMFY_HEADLESS") != "1":
    try:
        from aiohttp import web as _web  # noqa: PLC0415
        from server import PromptServer as _PromptServer  # noqa: PLC0415

        @_PromptServer.instance.routes.post("/vibecomfy/roundtrip")
        async def roundtrip_route(request):  # type: ignore[no-untyped-def]
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


        @_PromptServer.instance.routes.post("/vibecomfy/agent-executor")
        async def agent_executor_route(request):  # type: ignore[no-untyped-def]
            try:
                payload = await request.json()
            except Exception as exc:
                return _web.json_response(
                    _validated_failure_response(
                        "executor",
                        failure_envelope(
                            FailureKind.MISSING_REQUIRED_FIELD,
                            "executor",
                            agent_failure_context={
                                "explanation": f"Request body must be valid JSON: {exc}"
                            },
                        ),
                    ),
                    status=400,
                )
            client_id = payload.get("client_id") if isinstance(payload.get("client_id"), str) and payload.get("client_id").strip() else None
            result = await asyncio.to_thread(_handle_agent_executor, payload, client_id=client_id)
            if result.get("ok") is False:
                status = 500 if result.get("stage") == "route" else 400
                return _web.json_response(result, status=status)
            return _web.json_response(result)

        @_PromptServer.instance.routes.post("/vibecomfy/agent-edit/rating")
        async def agent_edit_rating_route(request):  # type: ignore[no-untyped-def]
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

    except ImportError:
        pass
