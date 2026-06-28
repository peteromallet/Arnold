"""Artifact synthesis for the headless VibeComfy agent surface.

Writes a stable, redacted artifact directory that harnesses and external
consumers (e.g. Astrid) can grade without parsing narrative output.
"""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from typing import Any, Mapping

LOGGER = logging.getLogger(__name__)


_FLOW_KIND = "live_agentic_headless"
_SENSITIVE_KEY_PARTS = frozenset({
    "api_key",
    "apikey",
    "authorization",
    "bearer",
    "password",
    "secret",
    "token",
})
_MODEL_ARTIFACT_NAMES = frozenset({
    "messages.jsonl",
    "model_request.json",
    "model_response.json",
})


def _safe_write(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return _json_safe(value.to_dict())
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    return str(value)


def _is_sensitive_key(key: str) -> bool:
    lower = key.lower()
    return any(part in lower for part in _SENSITIVE_KEY_PARTS)


def _redact(value: Any, *, parent_key: str = "") -> Any:
    """Return a JSON-safe copy with credential-like values redacted."""
    if _is_sensitive_key(parent_key) and isinstance(value, str):
        return "<redacted>"
    if isinstance(value, Mapping):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            redacted[key_text] = _redact(item, parent_key=key_text)
        return redacted
    if isinstance(value, (list, tuple, set)):
        return [_redact(item, parent_key=parent_key) for item in value]
    return _json_safe(value)


def _turn_dir_from_response(response: Mapping[str, Any]) -> Path | None:
    detail = response.get("detail_json_path") or response.get("detail_json_path_resolved")
    if isinstance(detail, str) and detail:
        return Path(detail).parent
    session_path = response.get("session_path") or response.get("session_path_resolved")
    turn_id = response.get("turn_id")
    if isinstance(session_path, str) and session_path and isinstance(turn_id, str) and turn_id:
        candidate = Path(session_path) / "turns" / turn_id
        if candidate.is_dir():
            return candidate
    return None


def _copy_turn_artifacts(turn_dir: Path, output_dir: Path) -> list[str]:
    copied: list[str] = []
    if not turn_dir.is_dir():
        return copied
    for source in sorted(turn_dir.iterdir()):
        if source.is_file() and source.suffix in {".json", ".jsonl"}:
            dest = output_dir / source.name
            shutil.copy2(source, dest)
            copied.append(str(dest.relative_to(output_dir)))
    return copied


def _executor_report(result: Any) -> dict[str, Any]:
    result_payload = _json_safe(result)
    if isinstance(result_payload, Mapping):
        report = result_payload.get("report")
        if isinstance(report, Mapping):
            executor = report.get("executor")
            if isinstance(executor, Mapping):
                return dict(executor)

    report_obj = getattr(result, "report", None)
    report_payload = _json_safe(report_obj)
    if isinstance(report_payload, Mapping):
        executor = report_payload.get("executor")
        if isinstance(executor, Mapping):
            return dict(executor)
    return {}


def _implementation_payload_from_report(
    *,
    request: Mapping[str, Any],
    classification: Mapping[str, Any],
    research: Mapping[str, Any] | None,
) -> dict[str, Any]:
    route = classification.get("route")
    route_text = route if isinstance(route, str) and route else ""
    if not route_text:
        route_text = "adapt" if classification.get("research") and classification.get("implement") else (
            "revise" if classification.get("implement") else "research"
        )

    payload: dict[str, Any] = {
        "task": request.get("query") or request.get("task") or "",
        "query": request.get("query") or request.get("task") or "",
        "route": route_text,
        "executor_route": route_text,
        "executor_classification": dict(classification),
    }
    if "graph" in request:
        payload["graph"] = request.get("graph")
    if isinstance(request.get("session_id"), str):
        payload["session_id"] = request["session_id"]

    if research:
        if route_text == "adapt":
            notes: dict[str, Any] = {}
            for key in ("research_goal", "pattern_category", "change_goal", "model_families"):
                value = classification.get(key)
                if value:
                    notes[key] = value
            if research.get("summary"):
                notes["research_summary"] = research["summary"]
            for key in ("sources", "warnings"):
                value = research.get(key)
                if value:
                    notes[f"research_{key}"] = value
            if notes:
                notes["_discardability"] = (
                    "This research context is provided as evidence only. "
                    "It is NOT authoritative guidance or a required implementation."
                )
                payload["execution_protocol_notes"] = notes
            packet = research.get("precedent_packet")
            if isinstance(packet, Mapping):
                payload["research_context_packet"] = dict(packet)
            else:
                context_packet = {
                    key: research[key]
                    for key in ("summary", "sources", "warnings", "precedent_slices")
                    if research.get(key)
                }
                if context_packet:
                    payload["research_context_packet"] = context_packet
        else:
            payload["research_summary"] = research.get("summary", "")
            payload["research_sources"] = research.get("sources", [])
            payload["executor_research"] = dict(research)

    if route_text in {"research", "adapt"}:
        brief = {
            key: classification[key]
            for key in ("research_goal", "search_directions", "source_preferences", "avoid")
            if classification.get(key)
        }
        if brief:
            payload["research_brief"] = brief

    return payload


def _append_manifest(manifest: list[str], file_name: str) -> None:
    if file_name not in manifest:
        manifest.append(file_name)


def synthesize_headless_artifacts(
    *,
    request: Mapping[str, Any],
    result: Any,
    response: Mapping[str, Any],
    output_dir: Path,
    status: str,
    readiness: Mapping[str, Any] | None = None,
    entrypoint: str = "headless_cli",
) -> dict[str, Any]:
    """Write the standard headless artifact directory and return a manifest.

    The manifest lists every file written relative to *output_dir*.  Real durable
    turn artifacts are copied from the underlying agent-edit turn when they exist;
    synthetic summaries are always written so callers have a stable contract.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest: list[str] = []

    request_path = output_dir / "request.json"
    _safe_write(request_path, _redact(request))
    _append_manifest(manifest, "request.json")

    response_path = output_dir / "response.json"
    _safe_write(response_path, _redact(response))
    _append_manifest(manifest, "response.json")

    flow_metadata = {
        "flow_kind": _FLOW_KIND,
        "dispatcher": "real",
        "model_behavior": "agentic",
        "frontend": "not_used",
        "entrypoint": entrypoint,
        "status": status,
        "live": bool(request.get("live", True)),
        "dry_run": bool(request.get("dry_run", False)),
        "apply": bool(request.get("apply", False)),
        "network": bool(request.get("network", True)),
        "readiness": dict(readiness) if readiness else {},
    }
    _safe_write(output_dir / "flow_metadata.json", _redact(flow_metadata))
    _append_manifest(manifest, "flow_metadata.json")

    report = _executor_report(result)
    classification = report.get("plan")
    if isinstance(classification, Mapping):
        classification_payload = _redact(classification)
        _safe_write(output_dir / "classification.json", classification_payload)
        _append_manifest(manifest, "classification.json")

        research = report.get("research")
        research_payload: dict[str, Any] | None = None
        if isinstance(research, Mapping):
            research_payload = _redact(research)
            _safe_write(output_dir / "research.json", research_payload)
            _append_manifest(manifest, "research.json")

        implementation = report.get("implementation")
        if isinstance(implementation, Mapping):
            implementation_payload = _implementation_payload_from_report(
                request=request,
                classification=classification_payload,
                research=research_payload,
            )
            _safe_write(
                output_dir / "implementation_payload.json",
                _redact(implementation_payload),
            )
            _append_manifest(manifest, "implementation_payload.json")
            _safe_write(
                output_dir / "implementation_result.json",
                _redact(implementation),
            )
            _append_manifest(manifest, "implementation_result.json")

    turn_dir = _turn_dir_from_response(response)
    copied: list[str] = []
    if turn_dir is not None and turn_dir.is_dir():
        copied = _copy_turn_artifacts(turn_dir, output_dir)
        for copied_name in copied:
            _append_manifest(manifest, copied_name)

    copied_set = set(copied)
    optional_model_artifacts = {
        name: name in copied_set
        for name in sorted(_MODEL_ARTIFACT_NAMES)
    }

    LOGGER.info(
        "headless artifacts synthesized",
        extra={"output_dir": str(output_dir), "artifact_count": len(manifest)},
    )
    return {
        "output_dir": str(output_dir),
        "manifest": manifest,
        "copied_turn_artifacts": copied,
        "optional_model_artifacts": optional_model_artifacts,
        "turn_dir": str(turn_dir) if turn_dir else None,
    }


__all__ = ["synthesize_headless_artifacts"]
