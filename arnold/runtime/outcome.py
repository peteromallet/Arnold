"""Neutral run outcome carriers for Arnold runtime consumers."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class RunOutcome(StrEnum):
    """Domain-neutral run outcome vocabulary shared by control-plane callers."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"
    ESCALATED = "escalated"
    BLOCKED = "blocked"
    AWAITING_HUMAN = "awaiting_human"


@dataclass(frozen=True)
class RunResultMetadata:
    """Structured metadata attached to a classified run outcome."""

    outcome: RunOutcome
    blocking_reason: str | None = None
    source: str | None = None


__all__ = ["RunOutcome", "RunResultMetadata"]
