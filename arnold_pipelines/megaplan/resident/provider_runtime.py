"""Provider-neutral execution policy and evidence normalization.

The upstream CLIs do not emit byte-identical streams.  This module preserves
each raw stream separately and projects only shared facts into a small JSONL
contract used by the resident lifecycle.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import re
import uuid
from pathlib import Path
from typing import Any, Mapping

from arnold.agent.routing import managed_agent_capabilities


PROVIDER_EVENT_SCHEMA = "arnold-managed-provider-event-v1"
PROVIDER_TELEMETRY_SCHEMA = "arnold-managed-provider-telemetry-v1"
GENERIC_TOOLSETS = frozenset({"file", "web", "terminal"})
FULL_GENERIC_TOOLSETS = ("file", "web", "terminal")
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
_HERMES_SESSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_CLAUDE_TOOLS = {
    "file": ("Read", "Edit", "Write", "Glob", "Grep"),
    "web": ("WebFetch", "WebSearch"),
    "terminal": ("Bash",),
}


@dataclass(frozen=True, slots=True)
class ProviderEvidence:
    session_id: str | None
    final_text: str | None
    events: tuple[dict[str, Any], ...]
    usage: Mapping[str, Any]
    failure_category: str | None
    failure_message: str | None


def normalize_toolsets(toolsets: str) -> tuple[str, ...]:
    requested = tuple(
        dict.fromkeys(
            part.strip().lower() for part in str(toolsets).split(",") if part.strip()
        )
    )
    unknown = sorted(set(requested) - GENERIC_TOOLSETS)
    if unknown:
        raise ValueError(
            "unsupported managed-agent toolsets: " + ", ".join(unknown)
        )
    return tuple(name for name in FULL_GENERIC_TOOLSETS if name in requested)


def claude_tools_for(toolsets: tuple[str, ...]) -> str:
    tools: list[str] = []
    for toolset in toolsets:
        tools.extend(_CLAUDE_TOOLS[toolset])
    return ",".join(tools)


def provider_execution_contract(
    *, backend: str, toolsets: str, max_tokens: int, timeout_s: float
) -> dict[str, Any]:
    normalized = normalize_toolsets(toolsets)
    capabilities = managed_agent_capabilities(backend)
    if backend == "codex" and normalized != FULL_GENERIC_TOOLSETS:
        raise ValueError(
            "Codex CLI cannot enforce a narrowed generic toolset; use the full "
            "file,web,terminal policy or select Hermes/Claude"
        )
    if max_tokens <= 0:
        raise ValueError("max_tokens must be positive")
    if timeout_s <= 0:
        raise ValueError("provider timeout must be positive")
    return {
        "schema_version": "arnold-managed-provider-capabilities-v1",
        "backend": backend,
        "capabilities": asdict(capabilities),
        "controls": {
            "toolsets": list(normalized),
            "tool_policy_enforcement": capabilities.generic_tool_policy,
            "max_tokens": int(max_tokens),
            "max_tokens_enforcement": capabilities.max_output_tokens,
            "timeout_s": float(timeout_s),
            "timeout_enforcement": capabilities.provider_timeout,
        },
    }


def reserve_session_id(backend: str) -> str | None:
    if backend == "claude":
        return str(uuid.uuid4())
    if backend == "hermes":
        return f"resident_{uuid.uuid4().hex}"
    return None


def valid_session_id(backend: str, session_id: str) -> bool:
    if backend in {"codex", "claude"}:
        return bool(_UUID_RE.fullmatch(session_id))
    if backend == "hermes":
        return bool(_HERMES_SESSION_RE.fullmatch(session_id))
    return False


def _read_json_lines(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return rows
    for line in lines:
        try:
            payload = json.loads(line)
        except (TypeError, ValueError):
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _event(provider: str, kind: str, **evidence: Any) -> dict[str, Any]:
    return {
        "schema_version": PROVIDER_EVENT_SCHEMA,
        "provider": provider,
        "kind": kind,
        "evidence": evidence,
    }


def _normalize_codex(
    rows: list[dict[str, Any]], expected_session_id: str | None
) -> tuple[str | None, list[dict[str, Any]], dict[str, Any]]:
    session_id = expected_session_id
    events: list[dict[str, Any]] = []
    usage: dict[str, Any] = {}
    for row in rows:
        row_type = str(row.get("type") or "unknown")
        if row_type == "thread.started":
            session_id = str(row.get("thread_id") or session_id or "") or None
            events.append(_event("codex", "session.started", session_id=session_id))
        elif row_type in {"item.started", "item.completed"}:
            item = row.get("item") if isinstance(row.get("item"), dict) else {}
            item_type = str(item.get("type") or "unknown")
            if item_type not in {"agent_message", "reasoning"}:
                events.append(
                    _event(
                        "codex",
                        "tool.started" if row_type.endswith("started") else "tool.completed",
                        tool=item_type,
                        item_id=item.get("id"),
                    )
                )
        elif row_type == "turn.completed":
            usage = dict(row.get("usage") or {})
            events.append(_event("codex", "turn.completed", usage=usage))
        elif "error" in row_type:
            events.append(_event("codex", "provider.error", raw_type=row_type))
    return session_id, events, usage


def _normalize_claude(
    rows: list[dict[str, Any]], expected_session_id: str | None
) -> tuple[
    str | None,
    str | None,
    list[dict[str, Any]],
    dict[str, Any],
    str | None,
    str | None,
]:
    session_id = expected_session_id
    final_text = None
    events: list[dict[str, Any]] = []
    usage: dict[str, Any] = {}
    failure_category = None
    failure_message = None
    for row in rows:
        row_session = str(row.get("session_id") or "").strip()
        if row_session:
            session_id = row_session
        row_type = str(row.get("type") or "unknown")
        subtype = str(row.get("subtype") or "")
        if row_type == "system" and subtype == "init":
            events.append(
                _event(
                    "claude",
                    "session.started",
                    session_id=session_id,
                    model=row.get("model"),
                    tools=row.get("tools"),
                )
            )
        elif row_type == "assistant":
            message = row.get("message") if isinstance(row.get("message"), dict) else {}
            for block in message.get("content") or []:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    events.append(
                        _event(
                            "claude",
                            "tool.requested",
                            tool=block.get("name"),
                            tool_call_id=block.get("id"),
                        )
                    )
            if row.get("error"):
                failure_category = str(row["error"])
                failure_message = failure_category
        elif row_type == "user":
            message = row.get("message") if isinstance(row.get("message"), dict) else {}
            for block in message.get("content") or []:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    events.append(
                        _event(
                            "claude",
                            "tool.completed",
                            tool_call_id=block.get("tool_use_id"),
                            is_error=bool(block.get("is_error")),
                        )
                    )
        elif row_type == "result":
            final_text = row.get("result") if isinstance(row.get("result"), str) else None
            usage = dict(row.get("usage") or {})
            is_error = bool(row.get("is_error"))
            errors = row.get("errors") if isinstance(row.get("errors"), list) else []
            if is_error:
                joined = "; ".join(str(value) for value in errors if value)
                lowered = joined.lower()
                if "not logged in" in lowered or "authentication" in lowered:
                    failure_category = "authentication_failed"
                else:
                    failure_category = failure_category or "provider_error"
                failure_message = joined or failure_message or "Claude result reported an error"
            events.append(
                _event(
                    "claude",
                    "turn.failed" if is_error else "turn.completed",
                    usage=usage,
                    errors=errors,
                )
            )
    return session_id, final_text, events, usage, failure_category, failure_message


def _normalize_hermes(
    metadata_path: Path, expected_session_id: str | None
) -> tuple[str | None, list[dict[str, Any]], dict[str, Any]]:
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError):
        metadata = {}
    session_id = str(metadata.get("session_id") or expected_session_id or "") or None
    usage = dict(metadata.get("usage") or {})
    events = [
        _event(
            "hermes",
            "session.started",
            session_id=session_id,
            model=metadata.get("resolved_model"),
            toolsets=metadata.get("toolsets"),
        )
    ]
    for entry in metadata.get("events") or []:
        if isinstance(entry, dict):
            events.append(
                _event(
                    "hermes",
                    str(entry.get("event") or "tool.requested"),
                    tool=entry.get("tool"),
                    tool_call_id=entry.get("tool_call_id"),
                )
            )
    if metadata:
        events.append(_event("hermes", "turn.completed", usage=usage))
    return session_id, events, usage


def collect_provider_evidence(
    *,
    backend: str,
    raw_output_path: Path,
    metadata_path: Path,
    expected_session_id: str | None,
    returncode: int,
    diagnostics_path: Path | None = None,
) -> ProviderEvidence:
    rows = _read_json_lines(raw_output_path)
    final_text = None
    failure_category = None
    failure_message = None
    if backend == "codex":
        session_id, events, usage = _normalize_codex(rows, expected_session_id)
    elif backend == "claude":
        (
            session_id,
            final_text,
            events,
            usage,
            failure_category,
            failure_message,
        ) = _normalize_claude(rows, expected_session_id)
    elif backend == "hermes":
        session_id, events, usage = _normalize_hermes(
            metadata_path, expected_session_id
        )
        try:
            final_text = raw_output_path.read_text(encoding="utf-8").strip() or None
        except OSError:
            final_text = None
    else:
        raise ValueError(f"unsupported provider evidence backend: {backend}")

    if returncode == 124:
        failure_category = "timeout"
        failure_message = "provider process exceeded its configured timeout"
    elif returncode != 0 and failure_category is None:
        failure_category = "provider_error"
        failure_message = f"provider process exited with status {returncode}"
    if backend == "claude" and failure_category == "provider_error" and diagnostics_path:
        try:
            diagnostics = diagnostics_path.read_text(
                encoding="utf-8", errors="replace"
            )
        except OSError:
            diagnostics = ""
        lowered = diagnostics.lower()
        if "not logged in" in lowered or "authentication_failed" in lowered:
            failure_category = "authentication_failed"
            failure_message = "Claude CLI reported that no authenticated session is available"
    if returncode == 0 and backend in {"hermes", "claude"} and not final_text:
        failure_category = "empty_result"
        failure_message = "provider returned success without a final response"

    events.insert(
        0,
        _event(
            backend,
            "provider.process.started",
            raw_stream=managed_agent_capabilities(backend).raw_stream,
        ),
    )
    events.append(
        _event(backend, "provider.process.completed", returncode=returncode)
    )
    return ProviderEvidence(
        session_id=session_id,
        final_text=final_text,
        events=tuple(events),
        usage=usage,
        failure_category=failure_category,
        failure_message=failure_message,
    )


def write_normalized_events(path: Path, events: tuple[dict[str, Any], ...]) -> None:
    rendered = "".join(
        json.dumps({**event, "sequence": index}, sort_keys=True) + "\n"
        for index, event in enumerate(events, start=1)
    )
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(rendered, encoding="utf-8")
    temporary.replace(path)


__all__ = [
    "FULL_GENERIC_TOOLSETS",
    "PROVIDER_EVENT_SCHEMA",
    "PROVIDER_TELEMETRY_SCHEMA",
    "ProviderEvidence",
    "claude_tools_for",
    "collect_provider_evidence",
    "normalize_toolsets",
    "provider_execution_contract",
    "reserve_session_id",
    "valid_session_id",
    "write_normalized_events",
]
