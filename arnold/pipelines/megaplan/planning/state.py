"""Canonical planning lifecycle state definitions."""

from __future__ import annotations

from typing import Any, Literal

STATE_INITIALIZED = "initialized"
STATE_PREPPED = "prepped"
STATE_PLANNED = "planned"
STATE_CRITIQUED = "critiqued"
STATE_GATED = "gated"
STATE_FINALIZED = "finalized"
STATE_EXECUTED = "executed"
STATE_REVIEWED = "reviewed"
STATE_DONE = "done"
STATE_ABORTED = "aborted"
STATE_FAILED = "failed"
STATE_BLOCKED = "blocked"
STATE_PAUSED = "paused"
STATE_CANCELLED = "cancelled"
STATE_AWAITING_PR_MERGE = "awaiting_pr_merge"
STATE_AWAITING_HUMAN_VERIFY = "awaiting_human_verify"
STATE_AWAITING_HUMAN = STATE_AWAITING_HUMAN_VERIFY
STATE_TIEBREAKER_PENDING = "tiebreaker_pending"
STATE_TIEBREAKER_READY = "tiebreaker_ready"

PlanCurrentState = Literal[
    "initialized",
    "prepped",
    "planned",
    "critiqued",
    "gated",
    "finalized",
    "executed",
    "reviewed",
    "done",
    "aborted",
    "failed",
    "blocked",
    "paused",
    "cancelled",
    "awaiting_pr_merge",
    "awaiting_human_verify",
    "tiebreaker_pending",
    "tiebreaker_ready",
]

CANONICAL_PLAN_STATES: frozenset[str] = frozenset(
    {
        STATE_INITIALIZED,
        STATE_PREPPED,
        STATE_PLANNED,
        STATE_CRITIQUED,
        STATE_GATED,
        STATE_FINALIZED,
        STATE_EXECUTED,
        STATE_REVIEWED,
        STATE_DONE,
        STATE_ABORTED,
        STATE_FAILED,
        STATE_BLOCKED,
        STATE_PAUSED,
        STATE_CANCELLED,
        STATE_AWAITING_PR_MERGE,
        STATE_AWAITING_HUMAN_VERIFY,
        STATE_TIEBREAKER_PENDING,
        STATE_TIEBREAKER_READY,
    }
)
TERMINAL_STATES: frozenset[str] = frozenset(
    {
        STATE_DONE,
        STATE_ABORTED,
        STATE_FAILED,
        STATE_BLOCKED,
        STATE_CANCELLED,
    }
)
AUTOMATION_TERMINAL_STATES: frozenset[str] = TERMINAL_STATES | frozenset(
    {
        STATE_PAUSED,
        STATE_AWAITING_HUMAN_VERIFY,
        STATE_TIEBREAKER_PENDING,
        STATE_TIEBREAKER_READY,
    }
)


def validate_plan_current_state(value: Any) -> str:
    """Return a canonical plan state or raise for invalid persisted state."""

    if value not in CANONICAL_PLAN_STATES:
        raise ValueError(f"invalid current_state {value!r}")
    return str(value)


__all__ = [
    "AUTOMATION_TERMINAL_STATES",
    "CANONICAL_PLAN_STATES",
    "PlanCurrentState",
    "STATE_ABORTED",
    "STATE_AWAITING_HUMAN",
    "STATE_AWAITING_HUMAN_VERIFY",
    "STATE_AWAITING_PR_MERGE",
    "STATE_BLOCKED",
    "STATE_CANCELLED",
    "STATE_CRITIQUED",
    "STATE_DONE",
    "STATE_EXECUTED",
    "STATE_FAILED",
    "STATE_FINALIZED",
    "STATE_GATED",
    "STATE_INITIALIZED",
    "STATE_PAUSED",
    "STATE_PLANNED",
    "STATE_PREPPED",
    "STATE_REVIEWED",
    "STATE_TIEBREAKER_PENDING",
    "STATE_TIEBREAKER_READY",
    "TERMINAL_STATES",
    "validate_plan_current_state",
]
