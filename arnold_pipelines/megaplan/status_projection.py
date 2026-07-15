"""Derived, user-facing Megaplan lifecycle presentation.

The persisted plan lifecycle, independent review verdict, and currently running
phase answer different questions.  In particular, ``finalized`` is the correct
durable state while an ``execute`` step consumes the finalized task document.
Consumers should retain those raw facts and use this projection for labels
shown to people.
"""

from __future__ import annotations

from typing import Any, Mapping


_FAILED_STATES = {"failed", "aborted", "cancelled"}
_PAUSED_STATES = {"paused", "awaiting_human", "awaiting_human_verify"}
_COMPLETED_STATES = {"done", "complete", "completed"}
_BLOCKED_STATES = {"blocked", "clarifying"}


def plan_status_presentation(
    plan_state: Any,
    *,
    active_step: Mapping[str, Any] | None = None,
    active_phase: Any = None,
    review_verdict: Any = None,
    completed: bool = False,
) -> dict[str, str | None]:
    """Project lifecycle, review truth, and live phase into a display contract."""

    raw_state = str(plan_state or "").strip().lower()
    phase_value = active_phase
    if phase_value is None and isinstance(active_step, Mapping):
        phase_value = active_step.get("phase") or active_step.get("step")
    phase = str(phase_value or "").strip().lower() or None
    if phase == "loop_execute":
        phase = "execute"
    verdict = str(review_verdict or "").strip().lower()

    if completed or raw_state in _COMPLETED_STATES:
        execution_state = "completed"
        display_state = "completed" if completed else raw_state
    elif raw_state in _FAILED_STATES:
        execution_state = "failed"
        display_state = raw_state
    elif raw_state in _PAUSED_STATES:
        execution_state = "paused"
        display_state = raw_state
    elif raw_state in _BLOCKED_STATES:
        execution_state = "blocked"
        display_state = raw_state
    elif phase == "review":
        execution_state = "reviewing"
        display_state = "reviewing"
    elif phase == "execute":
        execution_state = "reworking" if verdict == "needs_rework" else "executing"
        display_state = execution_state
    elif verdict == "needs_rework":
        execution_state = "rework_required"
        display_state = "needs_rework"
    elif raw_state == "finalized":
        execution_state = "ready"
        display_state = raw_state
    else:
        execution_state = "inactive"
        display_state = raw_state or None

    return {
        "active_phase": phase,
        "execution_state": execution_state,
        "display_state": display_state,
    }


__all__ = ["plan_status_presentation"]
