"""Synthetic outcome normalization tests for megaplan.supervisor.outcomes.

Covers:
- All 16 documented DriverOutcome.status → RunOutcome mappings
- Cursor/diagnostic metadata preservation (every DriverOutcome field)
- Unknown-status fallback to RunOutcome.ESCALATED with diagnostics
- Dict-sourced normalization (normalize_driver_outcome_from_dict)
- RunResultMetadata projection (to_run_result_metadata)
- Module-level completeness assertion
"""

from __future__ import annotations

import copy
from typing import Any

import pytest

from megaplan.run_outcome import RunOutcome, RunResultMetadata
from megaplan.supervisor.outcomes import (
    NORMALIZED_FROM_DRIVER_SOURCE,
    NormalizedOutcome,
    _DOCUMENTED_STATUSES,
    _DRIVER_STATUS_TO_RUN_OUTCOME,
    normalize_driver_outcome,
    normalize_driver_outcome_from_dict,
)

# ──────────────────────────────────────────────────────────────────────────────
# Reference data
# ──────────────────────────────────────────────────────────────────────────────

# All 16 documented statuses (from outcomes.py _DOCUMENTED_STATUSES)
ALL_DOCUMENTED_STATUSES = sorted(_DOCUMENTED_STATUSES)

# Expected RunOutcome for each status
EXPECTED_OUTCOME_MAP: dict[str, RunOutcome] = {
    # Successful
    "done": RunOutcome.SUCCEEDED,
    # Failed
    "aborted": RunOutcome.FAILED,
    "cancelled": RunOutcome.FAILED,
    "failed": RunOutcome.FAILED,
    "cap": RunOutcome.FAILED,
    "cost_cap_exceeded": RunOutcome.FAILED,
    "context_retry_exhausted": RunOutcome.FAILED,
    # Escalated
    "escalated": RunOutcome.ESCALATED,
    "paused": RunOutcome.ESCALATED,
    "stalled": RunOutcome.ESCALATED,
    # Blocked
    "blocked": RunOutcome.BLOCKED,
    "worker_blocked": RunOutcome.BLOCKED,
    # Awaiting human
    "human_required": RunOutcome.AWAITING_HUMAN,
    "awaiting_human": RunOutcome.AWAITING_HUMAN,
    "tiebreaker_pending": RunOutcome.AWAITING_HUMAN,
    "tiebreaker_ready": RunOutcome.AWAITING_HUMAN,
}

# Representative metadata for cursor-preservation tests
FULL_METADATA: dict[str, Any] = {
    "plan": "plan-v3",
    "final_state": "execute",
    "iterations": 12,
    "reason": "iteration cap reached",
    "last_phase": "review",
    "total_cost_usd": 4.56,
    "cost_cap_usd": 10.0,
    "context_retries_used": 2,
    "max_context_retries": 5,
    "external_retries_used": 1,
    "max_external_retries": 3,
    "blocked_retries_used": 0,
    "max_blocked_retries": 5,
    "blocking_reasons": ["prereq:task-3", "quality:review-failed"],
    "tier_escalations_used": 1,
    "escalation_tier_pin": 3,
}


# ──────────────────────────────────────────────────────────────────────────────
# Module-level completeness
# ──────────────────────────────────────────────────────────────────────────────

def test_mapping_covers_all_documented_statuses() -> None:
    """Every status in _DOCUMENTED_STATUSES has an entry in _DRIVER_STATUS_TO_RUN_OUTCOME."""
    missing = _DOCUMENTED_STATUSES - _DRIVER_STATUS_TO_RUN_OUTCOME.keys()
    assert not missing, f"Unmapped documented statuses: {sorted(missing)}"

    # Conversely, every key in the mapping should be a documented status
    extra = _DRIVER_STATUS_TO_RUN_OUTCOME.keys() - _DOCUMENTED_STATUSES
    assert not extra, f"Mapping contains non-documented statuses: {sorted(extra)}"


def test_all_five_run_outcome_values_are_reachable() -> None:
    """Each of the five RunOutcome values appears at least once in the mapping."""
    reached = set(_DRIVER_STATUS_TO_RUN_OUTCOME.values())
    all_values = set(RunOutcome)
    assert reached == all_values, (
        f"RunOutcome values not covered: {all_values - reached}"
    )


# ──────────────────────────────────────────────────────────────────────────────
# Known-status mapping — one parametrized test per documented status
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("status", ALL_DOCUMENTED_STATUSES)
def test_known_status_maps_to_expected_run_outcome(status: str) -> None:
    """Every documented status maps deterministically to the expected RunOutcome."""
    result = normalize_driver_outcome(status, plan="p", final_state="s", iterations=1)
    expected = EXPECTED_OUTCOME_MAP[status]
    assert result.outcome is expected, (
        f"status={status!r} → outcome={result.outcome!r}, expected {expected!r}"
    )
    assert result.original_status == status
    assert result.escalated_diagnostic is False
    assert result.diagnostic_reason is None


# ──────────────────────────────────────────────────────────────────────────────
# Cursor / diagnostic metadata preservation
# ──────────────────────────────────────────────────────────────────────────────

def test_all_metadata_fields_preserved_verbatim() -> None:
    """Every DriverOutcome metadata field is preserved exactly through normalization."""
    result = normalize_driver_outcome("done", **FULL_METADATA)

    assert result.plan == FULL_METADATA["plan"]
    assert result.final_state == FULL_METADATA["final_state"]
    assert result.iterations == FULL_METADATA["iterations"]
    assert result.reason == FULL_METADATA["reason"]
    assert result.last_phase == FULL_METADATA["last_phase"]
    assert result.total_cost_usd == FULL_METADATA["total_cost_usd"]
    assert result.cost_cap_usd == FULL_METADATA["cost_cap_usd"]
    assert result.context_retries_used == FULL_METADATA["context_retries_used"]
    assert result.max_context_retries == FULL_METADATA["max_context_retries"]
    assert result.external_retries_used == FULL_METADATA["external_retries_used"]
    assert result.max_external_retries == FULL_METADATA["max_external_retries"]
    assert result.blocked_retries_used == FULL_METADATA["blocked_retries_used"]
    assert result.max_blocked_retries == FULL_METADATA["max_blocked_retries"]
    assert result.blocking_reasons == FULL_METADATA["blocking_reasons"]
    assert result.tier_escalations_used == FULL_METADATA["tier_escalations_used"]
    assert result.escalation_tier_pin == FULL_METADATA["escalation_tier_pin"]


def test_metadata_defaults_when_fields_omitted() -> None:
    """When no metadata is provided, NormalizedOutcome defaults are sensible."""
    result = normalize_driver_outcome("done")

    assert result.plan is None
    assert result.final_state is None
    assert result.iterations is None
    assert result.reason is None
    assert result.last_phase is None
    assert result.total_cost_usd is None
    assert result.cost_cap_usd is None
    assert result.context_retries_used == 0
    assert result.max_context_retries is None
    assert result.external_retries_used == 0
    assert result.max_external_retries is None
    assert result.blocked_retries_used == 0
    assert result.max_blocked_retries is None
    assert result.blocking_reasons == []
    assert result.tier_escalations_used == 0
    assert result.escalation_tier_pin is None


@pytest.mark.parametrize("status", ["blocked", "worker_blocked"])
def test_blocking_reasons_preserved_for_blocked_statuses(status: str) -> None:
    """Blocking reasons are critical cursor metadata for blocked outcomes."""
    reasons = ["prereq:task-A", "quality:score-low"]
    result = normalize_driver_outcome(status, blocking_reasons=reasons)
    assert result.outcome is RunOutcome.BLOCKED
    assert result.blocking_reasons == reasons
    assert result.escalated_diagnostic is False


@pytest.mark.parametrize("status", ["aborted", "cancelled", "cap", "context_retry_exhausted"])
def test_retry_counters_preserved_for_failure_statuses(status: str) -> None:
    """Retry counters carry diagnostic value for failure outcomes."""
    result = normalize_driver_outcome(
        status,
        context_retries_used=3,
        max_context_retries=5,
        external_retries_used=1,
        max_external_retries=3,
    )
    assert result.outcome is RunOutcome.FAILED
    assert result.context_retries_used == 3
    assert result.max_context_retries == 5
    assert result.external_retries_used == 1
    assert result.max_external_retries == 3


@pytest.mark.parametrize("status", ["paused", "stalled"])
def test_paused_and_stalled_escalate_for_supervisor_policy(status: str) -> None:
    """Paused/stalled runs need supervisor intervention, not failure closure."""
    result = normalize_driver_outcome(status, tier_escalations_used=1)

    assert result.outcome is RunOutcome.ESCALATED
    assert result.tier_escalations_used == 1
    assert result.escalated_diagnostic is False


def test_escalation_pins_preserved_for_escalated_status() -> None:
    """Tier escalation metadata must survive normalization for operator triage."""
    result = normalize_driver_outcome(
        "escalated",
        tier_escalations_used=2,
        escalation_tier_pin=4,
    )
    assert result.outcome is RunOutcome.ESCALATED
    assert result.tier_escalations_used == 2
    assert result.escalation_tier_pin == 4


def test_cost_cap_fields_preserved() -> None:
    """Cost fields are preserved even when they signal a cap-exceeded outcome."""
    result = normalize_driver_outcome(
        "cost_cap_exceeded",
        total_cost_usd=15.73,
        cost_cap_usd=10.00,
    )
    assert result.outcome is RunOutcome.FAILED
    assert result.total_cost_usd == 15.73
    assert result.cost_cap_usd == 10.00


# ──────────────────────────────────────────────────────────────────────────────
# Unknown-status fallback
# ──────────────────────────────────────────────────────────────────────────────

def test_unknown_status_escalates_with_diagnostics() -> None:
    """An unrecognised status maps to ESCALATED with escalated_diagnostic=True."""
    result = normalize_driver_outcome("unrecognized_state_v99")

    assert result.outcome is RunOutcome.ESCALATED
    assert result.original_status == "unrecognized_state_v99"
    assert result.escalated_diagnostic is True
    assert result.diagnostic_reason is not None
    assert "unrecognized_state_v99" in result.diagnostic_reason
    assert "not in documented status vocabulary" in result.diagnostic_reason


def test_unknown_status_diagnostic_reason_is_descriptive() -> None:
    """The diagnostic_reason must include the unrecognised value for triage."""
    result = normalize_driver_outcome("future-status-v3")
    assert "future-status-v3" in result.diagnostic_reason
    assert len(result.diagnostic_reason) > 30, "diagnostic_reason too short to be useful"


@pytest.mark.parametrize("unknown_status", [
    "",
    "UNKNOWN",
    "PARTIAL_SUCCESS",
    "timeout",
    "retryable-failure",
    "custom:delegated",
])
def test_various_unknown_statuses_escalate(unknown_status: str) -> None:
    """A variety of unexpected status strings uniformly escalate with diagnostics."""
    result = normalize_driver_outcome(unknown_status)

    assert result.outcome is RunOutcome.ESCALATED
    assert result.original_status == unknown_status
    assert result.escalated_diagnostic is True
    assert result.diagnostic_reason is not None
    assert unknown_status in result.diagnostic_reason


def test_unknown_status_still_preserves_metadata() -> None:
    """Even unknown statuses preserve cursor metadata for operator triage."""
    result = normalize_driver_outcome(
        "unrecognized",
        plan="plan-v5",
        final_state="gate",
        iterations=7,
        reason="unknown transition",
        last_phase="execute",
        blocking_reasons=["custom-block"],
        tier_escalations_used=3,
    )

    assert result.outcome is RunOutcome.ESCALATED
    assert result.escalated_diagnostic is True
    assert result.plan == "plan-v5"
    assert result.final_state == "gate"
    assert result.iterations == 7
    assert result.reason == "unknown transition"
    assert result.last_phase == "execute"
    assert result.blocking_reasons == ["custom-block"]
    assert result.tier_escalations_used == 3


# ──────────────────────────────────────────────────────────────────────────────
# normalize_driver_outcome_from_dict
# ──────────────────────────────────────────────────────────────────────────────

def test_from_dict_normalizes_status_and_preserves_metadata() -> None:
    """Dict-sourced outcome with matching NormalizedOutcome fields works correctly."""
    outcome_dict: dict[str, Any] = {
        "status": "failed",
        "plan": "plan-A",
        "final_state": "review",
        "iterations": 3,
        "reason": "test failure",
        "last_phase": "execute",
        "total_cost_usd": 2.50,
        "context_retries_used": 1,
        "max_context_retries": 3,
        "blocking_reasons": [],
    }

    result = normalize_driver_outcome_from_dict(outcome_dict)

    assert result.outcome is RunOutcome.FAILED
    assert result.original_status == "failed"
    assert result.plan == "plan-A"
    assert result.final_state == "review"
    assert result.iterations == 3
    assert result.reason == "test failure"
    assert result.last_phase == "execute"
    assert result.total_cost_usd == 2.50
    assert result.context_retries_used == 1
    assert result.max_context_retries == 3


def test_from_dict_unknown_status_escalates_with_diagnostics() -> None:
    """Dict with unknown status produces escalated diagnostic outcome."""
    outcome_dict: dict[str, Any] = {
        "status": "emergency_brake",
        "plan": "plan-Z",
        "iterations": 1,
    }

    result = normalize_driver_outcome_from_dict(outcome_dict)

    assert result.outcome is RunOutcome.ESCALATED
    assert result.escalated_diagnostic is True
    assert "emergency_brake" in (result.diagnostic_reason or "")
    assert result.plan == "plan-Z"
    assert result.iterations == 1


def test_from_dict_ignores_extra_keys_not_in_normalized_outcome() -> None:
    """Extra dict keys not matching NormalizedOutcome fields are silently ignored."""
    outcome_dict: dict[str, Any] = {
        "status": "done",
        "plan": "plan-X",
        "iterations": 5,
        # These fields exist in DriverOutcome but not in NormalizedOutcome:
        "events": [{"kind": "test"}],
        "_internal_marker": "should-not-appear",
        "extra_field": 42,
    }

    result = normalize_driver_outcome_from_dict(outcome_dict)

    # Extra keys should be ignored — no crash, no leakage
    assert result.outcome is RunOutcome.SUCCEEDED
    assert result.plan == "plan-X"
    assert result.iterations == 5


def test_from_dict_missing_status_is_empty_string_escalates() -> None:
    """Dict with no 'status' key defaults to empty string, which is unknown → ESCALATED."""
    result = normalize_driver_outcome_from_dict({})

    assert result.outcome is RunOutcome.ESCALATED
    assert result.escalated_diagnostic is True
    assert result.original_status == ""


def test_from_dict_partial_metadata_preserves_what_is_supplied() -> None:
    """Dict with only a subset of NormalizedOutcome fields gets partial preservation."""
    outcome_dict: dict[str, Any] = {
        "status": "paused",
        "plan": "plan-partial",
        "iterations": 8,
        "total_cost_usd": 1.23,
    }

    result = normalize_driver_outcome_from_dict(outcome_dict)

    assert result.outcome is RunOutcome.ESCALATED
    assert result.plan == "plan-partial"
    assert result.iterations == 8
    assert result.total_cost_usd == 1.23
    # Fields not in dict get defaults
    assert result.final_state is None
    assert result.reason is None
    assert result.blocking_reasons == []


# ──────────────────────────────────────────────────────────────────────────────
# to_run_result_metadata projection
# ──────────────────────────────────────────────────────────────────────────────

def test_to_run_result_metadata_projects_outcome_and_source() -> None:
    """The RunResultMetadata projection carries the outcome and source sentinel."""
    result = normalize_driver_outcome("done", plan="p", final_state="s", iterations=1)
    meta = result.to_run_result_metadata()

    assert isinstance(meta, RunResultMetadata)
    assert meta.outcome is RunOutcome.SUCCEEDED
    assert meta.source == NORMALIZED_FROM_DRIVER_SOURCE
    assert meta.blocking_reason is None


def test_to_run_result_metadata_joins_blocking_reasons() -> None:
    """Multiple blocking reasons are joined with '; ' separator."""
    result = normalize_driver_outcome(
        "blocked",
        blocking_reasons=["prereq:task-1", "quality:score-0.3", "resource:gpu-unavailable"],
    )
    meta = result.to_run_result_metadata()

    assert meta.outcome is RunOutcome.BLOCKED
    assert meta.blocking_reason == "prereq:task-1; quality:score-0.3; resource:gpu-unavailable"


def test_to_run_result_metadata_empty_blocking_reasons_yields_none() -> None:
    """Empty blocking_reasons list yields blocking_reason=None."""
    result = normalize_driver_outcome("blocked", blocking_reasons=[])
    meta = result.to_run_result_metadata()

    assert meta.blocking_reason is None


def test_to_run_result_metadata_for_unknown_status() -> None:
    """Even ESCALATED from unknown status projects cleanly."""
    result = normalize_driver_outcome("bogus")
    meta = result.to_run_result_metadata()

    assert meta.outcome is RunOutcome.ESCALATED
    assert meta.source == NORMALIZED_FROM_DRIVER_SOURCE
    assert meta.blocking_reason is None


# ──────────────────────────────────────────────────────────────────────────────
# NormalizedOutcome is frozen
# ──────────────────────────────────────────────────────────────────────────────

def test_normalized_outcome_is_frozen() -> None:
    """NormalizedOutcome dataclass is frozen — cannot mutate after creation."""
    result = normalize_driver_outcome("done", plan="p", final_state="s", iterations=1)

    with pytest.raises(Exception):
        result.plan = "mutated"  # type: ignore[misc]


# ──────────────────────────────────────────────────────────────────────────────
# Round-trip: from_dict → normalize → metadata projection
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("status,expected_outcome", sorted(EXPECTED_OUTCOME_MAP.items()))
def test_round_trip_from_dict_for_every_status(status: str, expected_outcome: RunOutcome) -> None:
    """Every status survives a dict→normalize→projection round-trip."""
    outcome_dict: dict[str, Any] = {
        "status": status,
        "plan": f"plan-{status}",
        "final_state": "execute",
        "iterations": 5,
        "reason": f"ended with {status}",
        "last_phase": "review",
        "total_cost_usd": 3.14,
        "cost_cap_usd": 20.0,
        "context_retries_used": 0,
        "max_context_retries": 3,
        "blocking_reasons": [],
    }

    normalized = normalize_driver_outcome_from_dict(outcome_dict)

    assert normalized.outcome is expected_outcome
    assert normalized.original_status == status
    assert normalized.escalated_diagnostic is False
    assert normalized.plan == f"plan-{status}"
    assert normalized.iterations == 5
    assert normalized.total_cost_usd == 3.14

    meta = normalized.to_run_result_metadata()
    assert meta.outcome is expected_outcome
    assert meta.source == NORMALIZED_FROM_DRIVER_SOURCE
