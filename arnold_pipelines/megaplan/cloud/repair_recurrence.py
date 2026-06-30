"""Recurrence detection for cloud repair-loop dispatches."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

PROBLEM_SIGNATURE_FIELDS = (
    "failure_kind",
    "current_state",
    "phase_or_step",
    "milestone_or_plan",
    "gate_recommendation",
    "blocked_task_id",
)


def _as_dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _as_text(value: object) -> str:
    return str(value or "").strip()


def _as_int(value: object) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_when(value: object) -> datetime | None:
    text = _as_text(value)
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _first_blocked_task_id(execute_attempt_context: Mapping[str, Any]) -> str:
    context = _as_dict(execute_attempt_context)
    for section_name, key in (
        ("execution_batch", "blocked_or_deferred_tasks"),
        ("execute_batch_output", "blocked_or_deferred_tasks"),
        ("finalize", "skipped_or_deferred_tasks"),
    ):
        section = _as_dict(context.get(section_name))
        for task in _as_list(section.get(key)):
            if not isinstance(task, dict):
                continue
            task_id = _as_text(task.get("task_id") or task.get("id"))
            if task_id:
                return task_id
    return ""


def _history_last_step(execute_attempt_context: Mapping[str, Any]) -> str:
    context = _as_dict(execute_attempt_context)
    history = _as_dict(context.get("plan_history"))
    last_entries = _as_list(history.get("last_entries"))
    for entry in reversed(last_entries):
        if not isinstance(entry, dict):
            continue
        step = _as_text(entry.get("step"))
        if step:
            return step
    return ""


def build_problem_signature(failure_context: Mapping[str, Any]) -> dict[str, str]:
    """Return the controlled-field signature used for recurrence identity."""

    context = _as_dict(failure_context)
    plan_failure = _as_dict(context.get("plan_latest_failure"))
    chain_state = _as_dict(context.get("chain_state_summary"))
    plan_runtime = _as_dict(context.get("plan_runtime_state"))
    last_gate = _as_dict(context.get("last_gate"))
    execute_attempt = _as_dict(context.get("execute_attempt_context"))
    return {
        "failure_kind": _as_text(
            plan_failure.get("kind")
            or context.get("failure_classification")
            or chain_state.get("last_state")
        ),
        "current_state": _as_text(
            plan_runtime.get("current_state")
            or plan_failure.get("current_state")
            or chain_state.get("last_state")
            or chain_state.get("current_state")
        ),
        "phase_or_step": _as_text(
            plan_failure.get("phase")
            or _history_last_step(execute_attempt)
        ),
        "milestone_or_plan": _as_text(
            chain_state.get("current_milestone_label")
            or chain_state.get("current_plan_name")
            or plan_failure.get("plan_name")
        ),
        "gate_recommendation": _as_text(last_gate.get("recommendation")),
        "blocked_task_id": _first_blocked_task_id(execute_attempt),
    }


def signature_tuple(signature: Mapping[str, Any]) -> tuple[str, ...]:
    return tuple(_as_text(signature.get(field)) for field in PROBLEM_SIGNATURE_FIELDS)


def build_advancement_snapshot(
    failure_context: Mapping[str, Any],
    *,
    run_kind: str = "",
) -> dict[str, Any]:
    context = _as_dict(failure_context)
    plan_failure = _as_dict(context.get("plan_latest_failure"))
    chain_state = _as_dict(context.get("chain_state_summary"))
    plan_runtime = _as_dict(context.get("plan_runtime_state"))
    return {
        "run_kind": _as_text(run_kind or context.get("run_kind")),
        "completed_count": _as_int(chain_state.get("completed_count")),
        "current_milestone_index": _as_int(chain_state.get("current_milestone_index")),
        "current_state": _as_text(
            plan_runtime.get("current_state")
            or plan_failure.get("current_state")
            or chain_state.get("last_state")
            or chain_state.get("current_state")
        ),
        "phase": _as_text(plan_failure.get("phase")),
        "milestone_or_plan": _as_text(
            chain_state.get("current_milestone_label")
            or chain_state.get("current_plan_name")
            or plan_failure.get("plan_name")
        ),
    }


def has_advancement(
    previous: Mapping[str, Any] | None,
    current: Mapping[str, Any],
) -> bool:
    if not previous:
        return False
    prev = _as_dict(previous)
    curr = _as_dict(current)
    prev_completed = _as_int(prev.get("completed_count"))
    curr_completed = _as_int(curr.get("completed_count"))
    if (
        prev_completed is not None
        and curr_completed is not None
        and curr_completed > prev_completed
    ):
        return True
    prev_index = _as_int(prev.get("current_milestone_index"))
    curr_index = _as_int(curr.get("current_milestone_index"))
    if prev_index is not None and curr_index is not None and curr_index != prev_index:
        return True
    for key in ("current_state", "phase"):
        if _as_text(prev.get(key)) != _as_text(curr.get(key)):
            return True
    return False


def update_session_repair_snapshot(
    previous_snapshot: Mapping[str, Any] | None,
    current_snapshot: Mapping[str, Any],
    *,
    dispatched_at: str,
    min_dispatches: int = 3,
    window_seconds: int = 21600,
) -> dict[str, Any]:
    previous = _as_dict(previous_snapshot)
    current = _as_dict(current_snapshot)
    previous_dispatch_snapshot = _as_dict(previous.get("last_dispatch_snapshot"))
    advanced = has_advancement(previous_dispatch_snapshot, current)
    recent_dispatches: list[str]
    if advanced:
        recent_dispatches = [dispatched_at]
    else:
        cutoff = (_parse_when(dispatched_at) or datetime.now(timezone.utc)) - timedelta(
            seconds=max(int(window_seconds), 0)
        )
        recent_dispatches = []
        for value in _as_list(previous.get("no_advance_dispatches")):
            when = _parse_when(value)
            if when is not None and when >= cutoff:
                recent_dispatches.append(_as_text(value))
        recent_dispatches.append(dispatched_at)
    no_advance_count = len(recent_dispatches)
    return {
        "updated_at": dispatched_at,
        "current": current,
        "last_dispatch_snapshot": current,
        "no_advance_dispatches": recent_dispatches,
        "no_advance_count": no_advance_count,
        "advancement_since_last_dispatch": advanced,
        "window_seconds": int(window_seconds),
        "min_dispatches": int(min_dispatches),
        "layer2_recurrence": no_advance_count >= int(min_dispatches),
    }


def evaluate_recurrence(
    current_signature: Mapping[str, Any],
    attempts: list[Mapping[str, Any]] | None,
    session_snapshot: Mapping[str, Any] | None,
) -> dict[str, Any]:
    normalized_signature = {
        field: _as_text(_as_dict(current_signature).get(field))
        for field in PROBLEM_SIGNATURE_FIELDS
    }
    current_key = signature_tuple(normalized_signature)
    prior_attempts = attempts or []
    matching_attempt_ids: list[int] = []
    for attempt in prior_attempts:
        if not isinstance(attempt, Mapping):
            continue
        prior_signature = _as_dict(attempt.get("problem_signature"))
        if signature_tuple(prior_signature) != current_key:
            continue
        attempt_id = _as_int(attempt.get("attempt_id"))
        if attempt_id is not None:
            matching_attempt_ids.append(attempt_id)
    snapshot = _as_dict(session_snapshot)
    no_advance_count = _as_int(snapshot.get("no_advance_count")) or 0
    min_dispatches = _as_int(snapshot.get("min_dispatches")) or 0
    layer1_detected = bool(matching_attempt_ids)
    layer2_detected = no_advance_count >= min_dispatches > 0
    attempt_number = max(len(matching_attempt_ids) + 1, no_advance_count or 1)
    return {
        "detected": layer1_detected or layer2_detected,
        "attempt_number": attempt_number,
        "problem_signature": normalized_signature,
        "layer1": {
            "detected": layer1_detected,
            "matching_attempt_ids": matching_attempt_ids,
            "repeat_count": len(matching_attempt_ids),
        },
        "layer2": {
            "detected": layer2_detected,
            "no_advance_dispatch_count": no_advance_count,
            "min_dispatches": min_dispatches,
            "window_seconds": _as_int(snapshot.get("window_seconds")) or 0,
        },
    }
