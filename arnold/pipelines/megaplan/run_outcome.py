"""SDK-owned run outcome vocabulary and reducer mappings."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from arnold.pipelines.megaplan.execute._binding.reducer import BatchOutcome


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


_BATCH_OUTCOME_METADATA: dict[BatchOutcome, RunResultMetadata] = {
    BatchOutcome.SUCCESS: RunResultMetadata(
        outcome=RunOutcome.SUCCEEDED,
        blocking_reason=None,
        source="execute_batch",
    ),
    BatchOutcome.BLOCKED_BY_QUALITY: RunResultMetadata(
        outcome=RunOutcome.BLOCKED,
        blocking_reason="quality",
        source="execute_batch",
    ),
    BatchOutcome.BLOCKED_BY_PREREQ: RunResultMetadata(
        outcome=RunOutcome.BLOCKED,
        blocking_reason="prereq",
        source="execute_batch",
    ),
    BatchOutcome.TIMEOUT: RunResultMetadata(
        outcome=RunOutcome.FAILED,
        blocking_reason=None,
        source="execute_batch",
    ),
}


def run_metadata_from_batch_outcome(outcome: BatchOutcome) -> RunResultMetadata:
    """Map an M5b execute reducer outcome into the SDK run vocabulary."""

    return _BATCH_OUTCOME_METADATA[outcome]


def run_outcome_from_batch_outcome(outcome: BatchOutcome) -> RunOutcome:
    """Return only the neutral outcome for an M5b execute reducer outcome."""

    return run_metadata_from_batch_outcome(outcome).outcome


__all__ = [
    "RunOutcome",
    "RunResultMetadata",
    "run_metadata_from_batch_outcome",
    "run_outcome_from_batch_outcome",
]
