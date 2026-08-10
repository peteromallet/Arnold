"""Compatibility shim for Megaplan batch-outcome projections."""

from __future__ import annotations

from arnold.runtime.outcome import RunOutcome, RunResultMetadata
from arnold_pipelines.megaplan.execute._binding.reducer import BatchOutcome


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
