"""Bounded, progressively disclosed cloud status for resident prompts and tools.

The watchdog snapshot is a durable diagnostic projection.  It can contain full
plan states, raw repair attempts, and repeated log tails, so it must never be
embedded wholesale in a model prompt.  This module exposes a compact root and
explicit child nodes for targeted inspection while leaving raw evidence on
disk.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
import json
from typing import Any
from urllib.parse import quote, unquote


STATUS_TREE_SCHEMA = "megaplan-resident-status-tree-v1"
DEFAULT_NODE_LIMIT = 10
MAX_NODE_LIMIT = 25
MAX_TEXT_CHARS = 600
_RECENT_COMPLETED_LIMIT = MAX_NODE_LIMIT
_RECENT_COMPLETED_WINDOW = timedelta(hours=12)


def compact_cloud_status_snapshot(snapshot: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """Return the bounded root node placed in resident hot context."""

    if snapshot is None:
        return None
    sessions = [
        _compact_session(item)
        for item in _as_sequence(snapshot.get("sessions"))
        if isinstance(item, Mapping)
    ]
    active = [item for item in sessions if _root_session_needs_detail(item)]
    completed = [item for item in sessions if _is_completed_session(item)]
    indeterminate = [item for item in sessions if _is_indeterminate_completion(item)]
    # Completion is a terminal canonical status, not an inference from an idle
    # process.  Sort by terminal receipt time so a watchdog refresh cannot make
    # an old completion eligible for the bounded resident card.
    # Use the snapshot's own observation clock so archived/replayed snapshots
    # retain the truthful rolling window they had when generated.
    snapshot_time = _parse_utc_timestamp(snapshot.get("generated_at"))
    recent_candidates = [
        item for item in completed
        if _is_within_recent_completion_window(item, snapshot_time)
    ]
    recent_completed = sorted(
        recent_candidates,
        key=_completion_sort_key,
        reverse=True,
    )[:_RECENT_COMPLETED_LIMIT]
    # M9/T44: Indeterminate completions — surface typed evidence gaps
    indeterminate_preview = [
        {
            key: item.get(key)
            for key in ("node_id", "session", "display_name", "status", "completed_at")
            if item.get(key) is not None
        }
        for item in indeterminate[:3]
    ]
    # ── M9: aggregate source-cursor state from all sessions ──
    source_cursor_aggregate = _aggregate_source_cursor_state(sessions)

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
        # Active/blocked/repairing work belongs in the always-on root.  Finished
        # sessions are represented by a tiny preview and remain navigable.
        "sessions": active,
        "completed_session_count": len(completed),
        # M9/T44: Indeterminate completion count — sessions that claim
        # completion but have insufficient evidence to verify
        "indeterminate_completion_count": len(indeterminate),
        "indeterminate_completions_preview": indeterminate_preview,
        "recently_completed": recent_completed,
        "recently_completed_omitted_count": max(0, len(recent_candidates) - len(recent_completed)),
        # Kept for compatibility with existing hot-context consumers. New
        # callers must use ``recently_completed`` rather than this tiny preview.
        "completed_sessions_preview": [
            {
                key: item.get(key)
                for key in ("node_id", "session", "display_name", "status", "completed_at", "latest_activity")
                if item.get(key) is not None
            }
            for item in recent_completed[:3]
        ],
        # ── M9: aggregate source-cursor state for all active sessions ──
        "source_cursor_aggregate": source_cursor_aggregate,
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


def _root_session_needs_detail(session: Mapping[str, Any]) -> bool:
    status = str(session.get("status") or session.get("display_state") or "").casefold()
    return bool(
        session.get("repairing")
        or session.get("should_run")
        or session.get("process")
        or status not in {"complete", "completed", "finished", "success", "succeeded"}
    )


# ── M9/T44: Completion state classification ─────────────────────────────────

_TERMINAL_STATUSES: frozenset[str] = frozenset({
    "complete", "completed", "finished", "success", "succeeded",
})


def _classify_completion_state(
    session: Mapping[str, Any],
) -> str:
    """Classify session completion as ``complete``, ``indeterminate``, or ``idle``.

    M9/T44: Completion classification surfaces typed indeterminate results
    instead of collapsing to complete or idle.  When source-cursor metadata
    is present but the WBC dimension is unknown/stale/incoherent, the
    session is ``indeterminate`` — it MAY be complete but the evidence
    cannot be verified through the adapter.

    Returns:
        ``complete`` — terminal success status confirmed.
        ``indeterminate`` — status suggests completion but source-cursor
            evidence is insufficient to verify (e.g. WBC unknown/stale).
        ``idle`` — not a completion state; session is active/blocked/paused.
    """
    status = str(session.get("status") or "").casefold()
    is_terminal = status in _TERMINAL_STATUSES

    if not is_terminal:
        return "idle"

    # Check source-cursor metadata for indeterminate evidence
    source_cursor = session.get("source_cursor")
    if isinstance(source_cursor, Mapping):
        cursors = source_cursor.get("cursors")
        if isinstance(cursors, (list, tuple)):
            for c in cursors:
                if not isinstance(c, Mapping):
                    continue
                dim = c.get("dimension", "")
                state = c.get("state", "")
                # WBC, custody, or run_authority in non-fresh state
                # makes the completion indeterminate — the terminal
                # status claim cannot be verified against live evidence.
                if dim in {"wbc", "custody", "run_authority"} and state != "fresh":
                    return "indeterminate"

    return "complete"


def _is_completed_session(session: Mapping[str, Any]) -> bool:
    """Return canonical terminal-success session classifications.

    M9/T44: Uses ``_classify_completion_state`` so that indeterminate
    evidence is not silently collapsed to ``complete``.
    """
    return _classify_completion_state(session) == "complete"


def _is_indeterminate_completion(session: Mapping[str, Any]) -> bool:
    """Return True when session claims completion but evidence is indeterminate.

    M9/T44: Surfaces typed indeterminate results from adapter-backed
    projections instead of collapsing to complete or idle.
    """
    return _classify_completion_state(session) == "indeterminate"


def _completion_sort_key(session: Mapping[str, Any]) -> str:
    """Sort terminal completion timestamps newest first without guessing."""

    completed_at = session.get("completed_at")
    return str(completed_at).strip() if completed_at is not None else ""


def _is_within_recent_completion_window(
    session: Mapping[str, Any], snapshot_time: datetime | None
) -> bool:
    """Accept only durable terminal timestamps in the snapshot's last 12 hours."""

    completed_at = _parse_utc_timestamp(session.get("completed_at"))
    return bool(
        snapshot_time is not None
        and completed_at is not None
        and timedelta() <= snapshot_time - completed_at <= _RECENT_COMPLETED_WINDOW
    )


def _parse_utc_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, (str, datetime)):
        return None
    try:
        parsed = value if isinstance(value, datetime) else datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(UTC)


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
    if section == "source_cursor":
        return _node(normalized, _safe_value(session.get("source_cursor"), depth=3))
    return _error(normalized, f"unknown session branch {section!r}")


def _compact_session(session: Mapping[str, Any]) -> dict[str, Any]:
    session_name = str(session.get("session") or session.get("display_name") or "unknown")
    raw_progress = _as_mapping(session.get("progress"))
    progress = {
        key: _safe_value(raw_progress.get(key), depth=2)
        for key in (
            "percent",
            "plan_percent",
            "plan_percent_basis",
            "display_state",
            "plan_state",
            "current_plan",
            "completed_count",
            "milestone_count",
            "completed_sprints",
            "total_sprints",
            "epic_delta_1h",
            "epic_delta_5h",
            "stage_changes_1h",
            "epic_started_at",
            "plan_started_at",
        )
        if raw_progress.get(key) is not None
    } or None
    full_repair = _repair_summary(session)
    repair = (
        {
            key: full_repair.get(key)
            for key in (
                "canonical_state", "current_state", "custody_bucket", "failure_kind",
                "retry_strategy", "canonical_reason", "request_count", "claim_count",
                "attempt_count", "active_request_ids",
            )
            if full_repair.get(key) is not None
        }
        if full_repair
        else None
    )
    # ── M9: bounded source-cursor projection metadata ──
    source_cursor_compact = _compact_source_cursor(session.get("source_cursor"))

    children = [
        f"session/{quote(session_name, safe='')}/{name}"
        for name in ("progress", "runtime", "failure", "repair", "publication", "events")
    ]
    # M9: add source-cursor child node when metadata is available
    if source_cursor_compact is not None:
        children.append(f"session/{quote(session_name, safe='')}/source_cursor")

    return {
        "node_id": f"session/{quote(session_name, safe='')}",
        "session": session_name,
        "display_name": _bounded_text(session.get("display_name")),
        "run_kind": session.get("run_kind"),
        "status": session.get("status"),
        "display_state": session.get("display_state"),
        "review_verdict": session.get("review_verdict"),
        "should_run": session.get("should_run"),
        "process": session.get("process"),
        "tmux": session.get("tmux"),
        "watchdog": session.get("watchdog"),
        "repairing": session.get("repairing"),
        "current_plan": session.get("current_plan"),
        "active_phase": session.get("active_phase"),
        "completed_at": session.get("completed_at"),
        "latest_activity": session.get("latest_activity"),
        "operator_next": _bounded_text(session.get("operator_next")),
        "progress": progress,
        "repair": repair,
        # ── M9: source-cursor projection metadata (bounded) ──
        "source_cursor": source_cursor_compact,
        "children": children,
    }


def _compact_source_cursor(source_cursor: Any) -> dict[str, Any] | None:
    """Build a bounded projection of source-cursor metadata.

    Keeps raw full watchdog JSON opaque while exposing typed uncertainty
    per dimension with evidence IDs.  Fresh dimensions are preserved for
    complete projection fidelity; stale/unknown/incoherent are highlighted.
    """
    if not isinstance(source_cursor, Mapping):
        return None
    cursors = source_cursor.get("cursors")
    if not isinstance(cursors, (list, tuple)):
        return None

    dimensions: list[dict[str, Any]] = []
    for c in cursors:
        if not isinstance(c, Mapping):
            continue
        dim_entry = {
            "dimension": c.get("dimension"),
            "state": c.get("state"),
            "evidence_id": c.get("evidence_id"),
        }
        detail = c.get("detail")
        if detail:
            dim_entry["detail"] = _bounded_text(detail)
        dimensions.append(dim_entry)

    if not dimensions:
        return None

    return {
        "vector_id": source_cursor.get("vector_id"),
        "_non_authoritative": source_cursor.get("_non_authoritative", True),
        "dimensions": dimensions,
        "non_fresh_count": sum(
            1 for d in dimensions if d.get("state") not in ("fresh", "")
        ),
    }


def _aggregate_source_cursor_state(
    sessions: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Aggregate source-cursor states across sessions for bounded disclosure.

    Produces a summary of how many sessions have source-cursor metadata and
    a count of non-fresh dimensions across the active set.  Raw watchdog JSON
    remains opaque — only projection metadata is surfaced.
    """
    session_cursors: list[dict[str, Any]] = []
    for s in sessions:
        sc = s.get("source_cursor") if isinstance(s, Mapping) else None
        if isinstance(sc, Mapping):
            session_cursors.append({
                "session": s.get("session"),
                "vector_id": sc.get("vector_id"),
                "non_fresh_dimensions": [
                    c.get("dimension") for c in (sc.get("cursors") or [])
                    if isinstance(c, Mapping) and c.get("state") not in ("fresh", "")
                ],
            })

    if not session_cursors:
        return None

    total_non_fresh = sum(len(sc["non_fresh_dimensions"]) for sc in session_cursors)
    return {
        "sessions_with_cursor": len(session_cursors),
        "total_sessions": len(sessions),
        "total_non_fresh_dimensions": total_non_fresh,
        # Bounded disclosure: just vector IDs and non-fresh dimensions per session
        "session_cursors": session_cursors[:MAX_NODE_LIMIT],
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
