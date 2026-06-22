"""Normalize DriverOutcome.status into RunOutcome, preserving metadata.

Every documented ``DriverOutcome.status`` value from ``megaplan/auto.py`` is
mapped deterministically into one of the five ``RunOutcome`` members.  Cursor
fields (plan, final_state, iterations, reason, last_phase, retry counters,
blocking_reasons, tier escalation pins) and diagnostic cost metadata are
preserved unchanged so the supervisor tier can make informed recovery
decisions without re-deriving anything from the plan directory.

Unknown statuses are mapped to ``RunOutcome.ESCALATED`` with
``escalated_diagnostic=True`` and a ``diagnostic_reason`` explaining the gap
so the operator can triage.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from arnold_pipelines.megaplan.run_outcome import RunOutcome, RunResultMetadata

# ---------------------------------------------------------------------------
# Documented DriverOutcome.status → RunOutcome mapping
# ---------------------------------------------------------------------------
# Source: megaplan/auto.py DriverOutcome docstring and every _outcome() call
# site inside drive().  The commented status set in auto.py:157 is the
# primary reference; it is extended here with the three additional statuses
# produced by _outcome() calls that appear after the comment line
# (awaiting_human, tiebreaker_pending, tiebreaker_ready).

_DRIVER_STATUS_TO_RUN_OUTCOME: dict[str, RunOutcome] = {
    # Successful completions
    "done": RunOutcome.SUCCEEDED,
    # Terminal failures / stopped runs
    "aborted": RunOutcome.FAILED,
    "cancelled": RunOutcome.FAILED,
    # Hard failures
    "failed": RunOutcome.FAILED,
    "cap": RunOutcome.FAILED,
    "cost_cap_exceeded": RunOutcome.FAILED,
    "context_retry_exhausted": RunOutcome.FAILED,
    # Escalation
    "escalated": RunOutcome.ESCALATED,
    "paused": RunOutcome.ESCALATED,
    "stalled": RunOutcome.ESCALATED,
    # Blocked (task-level or worker-level)
    "blocked": RunOutcome.BLOCKED,
    "worker_blocked": RunOutcome.BLOCKED,
    # Awaiting human intervention
    "human_required": RunOutcome.AWAITING_HUMAN,
    "awaiting_human": RunOutcome.AWAITING_HUMAN,
    "tiebreaker_pending": RunOutcome.AWAITING_HUMAN,
    "tiebreaker_ready": RunOutcome.AWAITING_HUMAN,
}


# Sentinel key for RunResultMetadata.source when the outcome was normalised
# from a DriverOutcome (as opposed to a BatchOutcome reducer).
NORMALIZED_FROM_DRIVER_SOURCE = "supervisor_driver_outcome"


@dataclass(frozen=True)
class NormalizedOutcome:
    """A ``DriverOutcome.status`` normalized into the ``RunOutcome`` vocabulary.

    Preserves every driver-level metadata field from ``DriverOutcome`` so
    the supervisor can reconstruct the run's cursor position and diagnostic
    counters without re-reading ``state.json`` or ``events.ndjson``.
    """

    outcome: RunOutcome
    original_status: str
    escalated_diagnostic: bool = False
    diagnostic_reason: str | None = None
    # ── Preserved DriverOutcome fields ────────────────────────────────
    plan: str | None = None
    final_state: str | None = None
    iterations: int | None = None
    reason: str | None = None
    last_phase: str | None = None
    total_cost_usd: float | None = None
    cost_cap_usd: float | None = None
    context_retries_used: int = 0
    max_context_retries: int | None = None
    external_retries_used: int = 0
    max_external_retries: int | None = None
    blocked_retries_used: int = 0
    max_blocked_retries: int | None = None
    blocking_reasons: list[str] = field(default_factory=list)
    tier_escalations_used: int = 0
    escalation_tier_pin: int | None = None

    def to_run_result_metadata(self) -> RunResultMetadata:
        """Project into the shared ``RunResultMetadata`` shape."""
        return RunResultMetadata(
            outcome=self.outcome,
            blocking_reason=(
                "; ".join(self.blocking_reasons) if self.blocking_reasons else None
            ),
            source=NORMALIZED_FROM_DRIVER_SOURCE,
        )


def normalize_driver_outcome(
    status: str,
    **metadata: Any,
) -> NormalizedOutcome:
    """Map a ``DriverOutcome.status`` string into ``NormalizedOutcome``.

    Known statuses map deterministically into the five ``RunOutcome``
    members.  Unknown statuses produce ``RunOutcome.ESCALATED`` with
    ``escalated_diagnostic=True`` and a ``diagnostic_reason`` that
    includes the unrecognised value so the operator can triage.

    Extra keyword arguments are forwarded to ``NormalizedOutcome`` as
    preserved metadata fields.
    """
    outcome = _DRIVER_STATUS_TO_RUN_OUTCOME.get(status)
    if outcome is not None:
        return NormalizedOutcome(
            outcome=outcome,
            original_status=status,
            escalated_diagnostic=False,
            **metadata,
        )

    # Unknown status — escalate with diagnostics
    return NormalizedOutcome(
        outcome=RunOutcome.ESCALATED,
        original_status=status,
        escalated_diagnostic=True,
        diagnostic_reason=(
            f"Unknown DriverOutcome.status '{status}' — "
            f"not in documented status vocabulary; escalated for operator review"
        ),
        **metadata,
    )


def normalize_driver_outcome_from_dict(
    outcome_dict: dict[str, Any],
) -> NormalizedOutcome:
    """Normalize a ``DriverOutcome`` represented as a dict (e.g. from JSON).

    Only keys that match ``NormalizedOutcome`` field names are forwarded;
    extra keys are silently ignored.
    """
    status = outcome_dict.get("status", "")
    field_names = frozenset(NormalizedOutcome.__dataclass_fields__)
    metadata = {
        k: v for k, v in outcome_dict.items() if k != "status" and k in field_names
    }
    return normalize_driver_outcome(status, **metadata)


# ---------------------------------------------------------------------------
# Module validation: assert every documented status has a deterministic entry.
# ---------------------------------------------------------------------------
_DOCUMENTED_STATUSES: frozenset[str] = frozenset(
    {
        "done",
        "paused",
        "stalled",
        "escalated",
        "failed",
        "aborted",
        "cancelled",
        "cap",
        "blocked",
        "cost_cap_exceeded",
        "context_retry_exhausted",
        "worker_blocked",
        "human_required",
        "awaiting_human",
        "tiebreaker_pending",
        "tiebreaker_ready",
    }
)

# Fail-fast at import time if the mapping is incomplete.
_missing = _DOCUMENTED_STATUSES - _DRIVER_STATUS_TO_RUN_OUTCOME.keys()
if _missing:
    raise AssertionError(
        f"supervisor/outcomes.py: documented DriverOutcome.status values "
        f"missing from mapping: {sorted(_missing)}"
    )

__all__ = [
    "NORMALIZED_FROM_DRIVER_SOURCE",
    "NormalizedOutcome",
    "normalize_driver_outcome",
    "normalize_driver_outcome_from_dict",
    "_DRIVER_STATUS_TO_RUN_OUTCOME",
]
