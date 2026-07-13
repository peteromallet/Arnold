"""Bounded, progressively disclosed cloud status for resident prompts and tools.

The watchdog snapshot is a durable diagnostic projection.  It can contain full
plan states, raw repair attempts, and repeated log tails, so it must never be
embedded wholesale in a model prompt.  This module exposes a compact root and
explicit child nodes for targeted inspection while leaving raw evidence on
disk.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import json
from typing import Any
from urllib.parse import quote, unquote


STATUS_TREE_SCHEMA = "megaplan-resident-status-tree-v1"
DEFAULT_NODE_LIMIT = 10
MAX_NODE_LIMIT = 25
MAX_TEXT_CHARS = 600


def compact_cloud_status_snapshot(snapshot: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """Return the bounded root node placed in resident hot context."""

    if snapshot is None:
        return None
    sessions = [
        _compact_session(item)
        for item in _as_sequence(snapshot.get("sessions"))
        if isinstance(item, Mapping)
    ]
    return {
        "schema_version": STATUS_TREE_SCHEMA,
        "node_id": "root",
        "generated_at": snapshot.get("generated_at"),
        "source": snapshot.get("source"),
        "watchdog_generated_at": snapshot.get("watchdog_generated_at"),
        "degraded": snapshot.get("degraded"),
        "stale_banner": snapshot.get("stale_banner"),
        "stale_reason": snapshot.get("stale_reason"),
        "summary": _safe_value(snapshot.get("summary"), depth=1),
        "session_count": len(sessions),
        "sessions": sessions,
        "navigation": {
            "cli": (
                "python -P -m arnold_pipelines.megaplan resident status-tree "
                "--node '<node_id>'"
            ),
            "tool": "read_cloud_status_node",
            "instruction": (
                "Use a session's child node IDs to inspect only the relevant branch. "
                "Do not read or embed the full cloud-status JSON."
            ),
        },
    }


def read_cloud_status_node(
    snapshot: Mapping[str, Any] | None,
    *,
    node_id: str = "root",
    cursor: int = 0,
    limit: int = DEFAULT_NODE_LIMIT,
) -> dict[str, Any]:
    """Read one bounded status-tree node from a full watchdog snapshot."""

    if snapshot is None:
        return _error(node_id, "cloud status snapshot is unavailable")
    if cursor < 0:
        return _error(node_id, "cursor must be non-negative")
    if limit < 1 or limit > MAX_NODE_LIMIT:
        return _error(node_id, f"limit must be between 1 and {MAX_NODE_LIMIT}")
    normalized = (node_id or "root").strip().strip("/") or "root"
    if normalized == "root":
        return {"success": True, "node": compact_cloud_status_snapshot(snapshot)}
    parts = normalized.split("/")
    if len(parts) < 2 or parts[0] != "session":
        return _error(normalized, "unknown status-tree node")
    session_name = unquote(parts[1])
    session = _find_session(snapshot, session_name)
    if session is None:
        return _error(normalized, f"cloud session {session_name!r} was not found")
    branch = parts[2:]
    if not branch:
        return {
            "success": True,
            "node": {
                **_compact_session(session),
                "overview": _session_overview(session),
            },
        }
    section = branch[0]
    if section == "progress":
        return _node(normalized, _safe_value(session.get("progress"), depth=3))
    if section == "runtime":
        return _node(
            normalized,
            {
                key: _safe_value(session.get(key), depth=3)
                for key in (
                    "runner",
                    "execution_authority",
                    "status_authority_shadow",
                    "evidence",
                )
                if session.get(key) is not None
            },
        )
    if section == "failure":
        return _node(normalized, _failure_node(session))
    if section == "repair":
        return _read_repair_node(
            session, normalized=normalized, branch=branch[1:], cursor=cursor, limit=limit
        )
    if section == "publication":
        return _node(normalized, _safe_value(session.get("publication"), depth=3))
    if section == "events":
        history = _plan_history(session)
        return _paged_node(
            normalized,
            [_safe_value(item, depth=3) for item in history],
            cursor=cursor,
            limit=limit,
        )
    return _error(normalized, f"unknown session branch {section!r}")


def _compact_session(session: Mapping[str, Any]) -> dict[str, Any]:
    session_name = str(session.get("session") or session.get("display_name") or "unknown")
    progress = _safe_value(session.get("progress"), depth=2)
    repair = _repair_summary(session)
    return {
        "node_id": f"session/{quote(session_name, safe='')}",
        "session": session_name,
        "display_name": _bounded_text(session.get("display_name")),
        "run_kind": session.get("run_kind"),
        "status": session.get("status"),
        "display_state": session.get("display_state"),
        "should_run": session.get("should_run"),
        "process": session.get("process"),
        "tmux": session.get("tmux"),
        "watchdog": session.get("watchdog"),
        "repairing": session.get("repairing"),
        "current_plan": session.get("current_plan"),
        "active_phase": session.get("active_phase"),
        "latest_activity": session.get("latest_activity"),
        "operator_next": _bounded_text(session.get("operator_next")),
        "progress": progress,
        "repair": repair,
        "children": [
            f"session/{quote(session_name, safe='')}/{name}"
            for name in ("progress", "runtime", "failure", "repair", "publication", "events")
        ],
    }


def _session_overview(session: Mapping[str, Any]) -> dict[str, Any]:
    keys = (
        "spec",
        "workspace",
        "started_at",
        "execution_state",
        "plan_state",
        "chain_complete",
        "milestone_count",
        "completed_count",
        "advancement",
        "human_gate",
        "recovery",
        "repair_dispatch",
    )
    return {
        key: _safe_value(session.get(key), depth=3)
        for key in keys
        if session.get(key) is not None
    }


def _failure_node(session: Mapping[str, Any]) -> dict[str, Any]:
    custody = _as_mapping(session.get("repair_custody"))
    plan_state = _as_mapping(custody.get("plan_state"))
    plan_view = _as_mapping(session.get("megaplan_plan_view"))
    return {
        "current_state": plan_state.get("current_state") or session.get("plan_state"),
        "latest_failure": _safe_value(
            plan_state.get("latest_failure") or plan_view.get("latest_failure"), depth=4
        ),
        "last_gate": _safe_value(plan_state.get("last_gate"), depth=3),
        "resume_cursor": _safe_value(plan_state.get("resume_cursor"), depth=3),
        "recovery": _safe_value(session.get("recovery"), depth=3),
        "human_gate": _safe_value(session.get("human_gate"), depth=3),
        "advancement": _safe_value(session.get("advancement"), depth=3),
        "repair": _repair_summary(session),
    }


def _repair_summary(session: Mapping[str, Any]) -> dict[str, Any] | None:
    custody = _as_mapping(session.get("repair_custody"))
    dispatch = _as_mapping(session.get("repair_dispatch"))
    if not custody and not dispatch:
        return None
    keys = (
        "canonical_state",
        "current_state",
        "custody_bucket",
        "failure_kind",
        "retry_strategy",
        "canonical_reason",
        "request_count",
        "claim_count",
        "attempt_count",
        "active_request_ids",
        "active_claim_request_ids",
        "accepted_unclaimed_request_ids",
        "terminal_outcomes",
        "retry_budget",
    )
    return {
        **{
            key: _safe_value(custody.get(key), depth=2)
            for key in keys
            if custody.get(key) is not None
        },
        "dispatch": _safe_value(dispatch, depth=3) if dispatch else None,
    }


def _read_repair_node(
    session: Mapping[str, Any],
    *,
    normalized: str,
    branch: list[str],
    cursor: int,
    limit: int,
) -> dict[str, Any]:
    custody = _as_mapping(session.get("repair_custody"))
    session_name = str(session.get("session") or session.get("display_name") or "unknown")
    session_node = f"session/{quote(session_name, safe='')}"
    attempts = [item for item in _as_sequence(custody.get("attempts")) if isinstance(item, Mapping)]
    requests = [item for item in _as_sequence(custody.get("requests")) if isinstance(item, Mapping)]
    if not branch:
        return _node(
            normalized,
            {
                "summary": _repair_summary(session),
                "current_target": _safe_value(custody.get("current_target"), depth=3),
                "requests": [_compact_request(item) for item in requests[:limit]],
                "attempts": [
                    _compact_attempt(item, node_id=f"{session_node}/repair/attempt/{index}")
                    for index, item in enumerate(attempts[:limit])
                ],
                "request_count": len(requests),
                "attempt_count": len(attempts),
            },
        )
    if branch[0] != "attempt" or len(branch) < 2:
        return _error(normalized, "unknown repair branch")
    try:
        index = int(branch[1])
        attempt = attempts[index]
    except (ValueError, IndexError):
        return _error(normalized, "repair attempt index is invalid")
    if len(branch) == 2:
        return _node(normalized, _attempt_detail(attempt, node_id=normalized))
    raw = _as_mapping(attempt.get("raw"))
    context_name = branch[2]
    context = _as_mapping(raw.get(context_name))
    if not context:
        return _error(normalized, f"repair context {context_name!r} is unavailable")
    if len(branch) == 3:
        return _node(normalized, _context_detail(context, node_id=normalized))
    tail_name = branch[3]
    tail = context.get(tail_name)
    if not isinstance(tail, str):
        return _error(normalized, f"evidence tail {tail_name!r} is unavailable")
    lines = [_summarize_evidence_line(line) for line in tail.splitlines() if line.strip()]
    return _paged_node(normalized, lines, cursor=cursor, limit=limit)


def _compact_request(request: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: _safe_value(request.get(key), depth=2)
        for key in (
            "request_id",
            "status",
            "active",
            "source",
            "blocker_id",
            "problem_signature",
            "decision",
        )
        if request.get(key) is not None
    }


def _compact_attempt(attempt: Mapping[str, Any], *, node_id: str) -> dict[str, Any]:
    return {
        "node_id": node_id,
        **{
            key: _safe_value(attempt.get(key), depth=2)
            for key in (
                "attempt_id",
                "request_id",
                "source",
                "state",
                "outcome",
                "terminal",
                "recorded_at",
                "blocker_id",
                "path",
            )
            if attempt.get(key) is not None
        },
        "detail_available": isinstance(attempt.get("raw"), Mapping),
    }


def _attempt_detail(attempt: Mapping[str, Any], *, node_id: str) -> dict[str, Any]:
    raw = _as_mapping(attempt.get("raw"))
    context_names = [
        name
        for name in ("failure_context", "post_launch_failure_context", "post_kimi_failure_context")
        if isinstance(raw.get(name), Mapping)
    ]
    metadata = {
        key: _safe_value(value, depth=3)
        for key, value in raw.items()
        if key not in context_names and key not in {"plan_state", "raw"}
    }
    return {
        **_compact_attempt(attempt, node_id=node_id),
        "metadata": metadata,
        "children": [f"{node_id}/{name}" for name in context_names],
    }


def _context_detail(context: Mapping[str, Any], *, node_id: str) -> dict[str, Any]:
    tails: list[dict[str, Any]] = []
    details: dict[str, Any] = {}
    for key, value in context.items():
        if key.endswith("_tail") and isinstance(value, str):
            tails.append(
                {
                    "node_id": f"{node_id}/{key}",
                    "name": key,
                    "line_count": len(value.splitlines()),
                    "character_count": len(value),
                }
            )
        else:
            details[key] = _safe_value(value, depth=3)
    return {"details": details, "evidence_tails": tails}


def _summarize_evidence_line(line: str) -> dict[str, Any]:
    prefix, separator, payload = line.partition(" | state=")
    if separator:
        try:
            state = json.loads(payload)
        except json.JSONDecodeError:
            state = None
        if isinstance(state, Mapping):
            return {
                "event": prefix,
                "state": {
                    key: _safe_value(state.get(key), depth=3)
                    for key in (
                        "name",
                        "current_state",
                        "iteration",
                        "active_step",
                        "latest_failure",
                        "resume_cursor",
                    )
                    if state.get(key) is not None
                },
                "raw_character_count": len(line),
            }
    return {"event": _bounded_text(line), "raw_character_count": len(line)}


def _plan_history(session: Mapping[str, Any]) -> list[Any]:
    custody = _as_mapping(session.get("repair_custody"))
    state = _as_mapping(custody.get("plan_state"))
    return list(_as_sequence(state.get("history")))


def _find_session(snapshot: Mapping[str, Any], session_name: str) -> Mapping[str, Any] | None:
    for item in _as_sequence(snapshot.get("sessions")):
        if not isinstance(item, Mapping):
            continue
        if session_name in {str(item.get("session") or ""), str(item.get("display_name") or "")}:
            return item
    return None


def _safe_value(value: Any, *, depth: int) -> Any:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return _bounded_text(value)
    if depth <= 0:
        if isinstance(value, Mapping):
            return {"omitted_field_count": len(value)}
        if isinstance(value, Sequence):
            return {"omitted_item_count": len(value)}
        return _bounded_text(value)
    if isinstance(value, Mapping):
        rendered: dict[str, Any] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= 25:
                rendered["_omitted_field_count"] = len(value) - index
                break
            if key in {"raw", "plan_events_tail", "run_log_tail", "chain_log_tail", "mechanical_log_tail"}:
                rendered[key] = _evidence_reference(item)
            else:
                rendered[str(key)] = _safe_value(item, depth=depth - 1)
        return rendered
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        items = list(value)
        rendered = [_safe_value(item, depth=depth - 1) for item in items[:20]]
        if len(items) > 20:
            rendered.append({"omitted_item_count": len(items) - 20})
        return rendered
    return _bounded_text(value)


def _evidence_reference(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        return {
            "available": True,
            "character_count": len(value),
            "line_count": len(value.splitlines()),
        }
    if isinstance(value, Mapping):
        return {"available": True, "field_count": len(value)}
    return {"available": value is not None}


def _bounded_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if len(text) <= MAX_TEXT_CHARS else f"{text[: MAX_TEXT_CHARS - 1]}…"


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _as_sequence(value: Any) -> Sequence[Any]:
    return value if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)) else ()


def _node(node_id: str, value: Any) -> dict[str, Any]:
    return {"success": True, "node": {"node_id": node_id, "value": value}}


def _paged_node(
    node_id: str,
    items: list[Any],
    *,
    cursor: int,
    limit: int,
) -> dict[str, Any]:
    page = items[cursor : cursor + limit]
    next_cursor = cursor + len(page) if cursor + len(page) < len(items) else None
    return {
        "success": True,
        "node": {
            "node_id": node_id,
            "items": page,
            "cursor": cursor,
            "next_cursor": next_cursor,
            "total_count": len(items),
        },
    }


def _error(node_id: str, message: str) -> dict[str, Any]:
    return {"success": False, "node_id": node_id, "error": message}


__all__ = [
    "DEFAULT_NODE_LIMIT",
    "MAX_NODE_LIMIT",
    "STATUS_TREE_SCHEMA",
    "compact_cloud_status_snapshot",
    "read_cloud_status_node",
]
