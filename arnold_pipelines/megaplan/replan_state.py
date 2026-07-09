from __future__ import annotations

from collections.abc import MutableMapping
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
