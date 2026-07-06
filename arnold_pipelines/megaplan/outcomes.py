"""Closed route outcome enums for Megaplan authored workflow topology."""

from __future__ import annotations

from enum import StrEnum
from types import MappingProxyType


class PrepOutcome(StrEnum):
    CONTINUE = "continue"
    AWAITING_HUMAN = "awaiting_human"


class CritiqueOutcome(StrEnum):
    COMPLETED = "completed"


class GateOutcome(StrEnum):
    PROCEED = "proceed"
    ITERATE = "iterate"
    TIEBREAKER = "tiebreaker"
    ESCALATE = "escalate"
    ABORT = "abort"
    SUSPEND = "suspend"
    BLOCKED_PREFLIGHT = "blocked_preflight"
    FORCE_PROCEED = "force_proceed"
    RETRY_GATE = "retry_gate"
    REPROMPT_DOWNGRADE = "reprompt_downgrade"


class ReviewOutcome(StrEnum):
    PASS = "pass"
    REWORK = "rework"
    BLOCKED = "blocked"
    FORCE_PROCEEDED = "force_proceeded"
    DEFERRED_HUMAN = "deferred_human"


class TiebreakerOutcome(StrEnum):
    PROCEED = "proceed"
    ITERATE = "iterate"
    ESCALATE = "escalate"


class OverrideOutcome(StrEnum):
    ABORT = "abort"
    FORCE_PROCEED = "force_proceed"
    REPLAN = "replan"


class SuspensionOutcome(StrEnum):
    SUSPEND = "suspend"
    RESUME = "resume"


class HaltOutcome(StrEnum):
    HALT = "halt"


class ExecuteOutcome(StrEnum):
    SUCCESS = "success"
    BLOCKED = "blocked"
    FAILED = "failed"


class FinalizeOutcome(StrEnum):
    FINALIZED = "finalized"
    BLOCKED = "blocked"


class ReviseOutcome(StrEnum):
    COMPLETED = "completed"


__all__ = [
    "CritiqueOutcome",
    "ExecuteOutcome",
    "FinalizeOutcome",
    "GateOutcome",
    "HaltOutcome",
    "OverrideOutcome",
    "PrepOutcome",
    "ReviewOutcome",
    "ReviseOutcome",
    "SuspensionOutcome",
    "TiebreakerOutcome",
    "OUTCOME_CLASS_BY_VOCABULARY_KEY",
]


OUTCOME_CLASS_BY_VOCABULARY_KEY = MappingProxyType(
    {
        "prep": PrepOutcome,
        "critique": CritiqueOutcome,
        "gate": GateOutcome,
        "tiebreaker_decide": TiebreakerOutcome,
        "review": ReviewOutcome,
        "override": OverrideOutcome,
        "revise": ReviseOutcome,
    }
)
