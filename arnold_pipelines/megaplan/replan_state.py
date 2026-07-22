from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from typing import Any

REPLAN_META_KEYS_TO_CLEAR: tuple[str, ...] = (
    "tiebreaker_count",
    "user_approved_gate",
)
REPLAN_STATE_KEYS_TO_CLEAR: tuple[str, ...] = (
    "active_step",
    "latest_failure",
    "resume_cursor",
)


def blocked_iterate_gate_replan_allowed(state: Mapping[str, Any]) -> bool:
    """Return whether a blocked ITERATE gate may re-enter planning.

    The critique-loop cap can latch the plan in ``blocked`` after an ITERATE
    verdict without writing a resume cursor.  Replanning is the narrow recovery
    seam for that exact state; every other blocked state remains fail closed.
    """

    if state.get("current_state") != "blocked":
        return False
    last_gate = state.get("last_gate")
    if not isinstance(last_gate, Mapping):
        return False
    recommendation = last_gate.get("recommendation")
    return (
        isinstance(recommendation, str)
        and recommendation.upper() == "ITERATE"
        and last_gate.get("passed") is False
    )


def reset_replan_loop_state(
    state: MutableMapping[str, Any],
    *,
    target_state: str,
) -> MutableMapping[str, Any]:
    """Clear stale loop/runtime state before re-entering planning."""

    raw_meta = state.get("meta")
    if isinstance(raw_meta, MutableMapping):
        meta = raw_meta
    else:
        meta = {}
        state["meta"] = meta

    for key in REPLAN_META_KEYS_TO_CLEAR:
        meta.pop(key, None)
    for key in REPLAN_STATE_KEYS_TO_CLEAR:
        state.pop(key, None)

    state["last_gate"] = {}
    state["current_state"] = target_state
    return meta
