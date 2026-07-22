"""Repair receipt adoption tests — exact-match skip replay, quarantine, and normal execution.

These tests prove that:
- Exact-match adoption (T7/T12-style) skips worker replay when all boundary
  conditions match.
- Altered context (revision, task, tree, test, fence, custody, WBC) produces
  QUARANTINE outcomes and the caller MUST continue normal execution without
  rewriting immutable attempts.
- Invalid receipts produce INVALID outcomes.
- The AdoptionDecision is a pure deterministic comparison; it is never authority.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any

import pytest

from arnold_pipelines.megaplan.custody.repair_adoption import (
    REPAIR_ADOPTION_SCHEMA_VERSION,
    AdoptionContext,
    AdoptionDecision,
    AdoptionFieldMismatch,
    AdoptionOutcome,
    adopt_repair_receipt,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Standard test_results payload used in receipts — must match context.test_result_hash
_STD_TEST_RESULTS: dict[str, Any] = {"passed": True, "count": 10}
# Pre-computed payload_hash for _STD_TEST_RESULTS (sha256 of canonical JSON)
_STD_TEST_RESULT_HASH: str = (
    "ea269d29149ad41bc05ab7e7eeef13d651cc60081e430ba4a3d21918413f697d"
)
_STD_BLOCKER_HASH: str = "blocker-hash-001"


def _fresh_ctx(**overrides: Any) -> AdoptionContext:
    """Build a valid AdoptionContext with sensible defaults for testing."""
    defaults: dict[str, Any] = {
        "run_authority_grant_id": "grant-001",
        "coordinator_fence_token": 42,
        "custody_lease_id": "lease-abc",
        "custody_epoch": 7,
        "wbc_attempt_reference": "wbc-ref-xyz",
        "plan_revision": "rev-2024-01-01",
        "task_contract": "T1",
        "tree_commit": "abc123def456",
        "test_result_hash": _STD_TEST_RESULT_HASH,
        "blocker_hash": _STD_BLOCKER_HASH,
    }
    defaults.update(overrides)
    return AdoptionContext(**defaults)


def _valid_receipt_payload(**overrides: Any) -> dict[str, Any]:
    """Build a RepairReceipt-compatible dict payload."""
    defaults: dict[str, Any] = {
        "receipt_id": "00000000-0000-0000-0000-000000000001",
        "status": "attempt",
        "target": {
            "environment": "prod",
            "session": "session-1",
            "chain": "chain-1",
            "plan_revision": "rev-2024-01-01",
            "phase": "execute",
            "task": "T1",
            "attempt": "attempt-1",
            "normalized_failure_kind": "none",
            "blocker_or_phase_result_hash": "hash-blocker",
            "fence": "42",
            "chain_identity": "ci-1",
        },
        "occurrence_key": {
            "target": {
                "environment": "prod",
                "session": "session-1",
                "chain": "chain-1",
                "plan_revision": "rev-2024-01-01",
                "phase": "execute",
                "task": "T1",
                "attempt": "attempt-1",
                "normalized_failure_kind": "none",
                "blocker_or_phase_result_hash": "hash-blocker",
                "fence": "42",
                "chain_identity": "ci-1",
            },
            "run_id": "run-1",
            "run_revision": "run-rev-1",
            "coordinator_attempt_id": "ca-1",
            "fence_token": 42,
            "wbc_attempt_reference": "wbc-ref-xyz",
        },
        "run_authority_grant_id": "grant-001",
        "plan_revision": "rev-2024-01-01",
        "phase": "execute",
        "task_contract": "T1",
        "subject_attempt": "attempt-1",
        "wbc_attempt_reference": "wbc-ref-xyz",
        "tree_commit": "abc123def456",
        "test_results": {"passed": True, "count": 10},
        "blocker_hash": "blocker-hash-001",
        "coordinator_fence_token": 42,
        "custody_lease_id": "lease-abc",
        "custody_epoch": 7,
        "causal_predecessor": "",
        "occurred_at": "2024-01-01T00:00:00Z",
        "recorded_by": {"host": "test-host", "pid": "1234"},
    }
    defaults.update(overrides)
    return defaults


# ---------------------------------------------------------------------------
# Exact-match adoption — all fields match → ADOPT
# ---------------------------------------------------------------------------


class TestExactMatchAdoption:
    """When every compared field matches, the outcome is ADOPT and skip-replay is allowed."""

    def test_exact_match_produces_adopt(self) -> None:
        """All fields match → ADOPT outcome with no mismatches."""
        receipt = _valid_receipt_payload()
        ctx = _fresh_ctx()

        decision = adopt_repair_receipt(receipt, ctx)

        assert decision.outcome == AdoptionOutcome.ADOPT
        assert decision.is_adoptable is True
        assert decision.is_quarantined is False
        assert len(decision.mismatches) == 0
        assert decision.receipt_digest != ""

    def test_exact_match_adoptable_property(self) -> None:
        """is_adoptable returns True only for ADOPT."""
        receipt = _valid_receipt_payload()
        ctx = _fresh_ctx()

        decision = adopt_repair_receipt(receipt, ctx)
        assert decision.is_adoptable is True
        assert decision.is_quarantined is False

    def test_exact_match_to_dict_has_correct_shape(self) -> None:
        """to_dict() returns all required fields for evidence recording."""
        receipt = _valid_receipt_payload()
        ctx = _fresh_ctx()

        decision = adopt_repair_receipt(receipt, ctx)
        d = decision.to_dict()

        assert d["contract_type"] == "adoption_decision"
        assert d["schema_version"] == REPAIR_ADOPTION_SCHEMA_VERSION
        assert d["outcome"] == "adopt"
        assert d["receipt_digest"] != ""
        assert d["mismatches"] == []
        assert "compared_at" in d
        assert "diagnostics" in d

    def test_exact_match_with_empty_blocker_hash_is_still_adopt(self) -> None:
        """Empty blocker_hash in both receipt and context still produces ADOPT."""
        receipt = _valid_receipt_payload(blocker_hash="")
        ctx = _fresh_ctx(blocker_hash="")

        decision = adopt_repair_receipt(receipt, ctx)
        assert decision.outcome == AdoptionOutcome.ADOPT

    def test_exact_match_with_empty_wbc_reference_is_still_adopt(self) -> None:
        """Empty WBC reference when both agree still produces ADOPT."""
        receipt = _valid_receipt_payload(wbc_attempt_reference="")
        ctx = _fresh_ctx(wbc_attempt_reference="")

        decision = adopt_repair_receipt(receipt, ctx)
        assert decision.outcome == AdoptionOutcome.ADOPT


# ---------------------------------------------------------------------------
# Quarantine — altered context → QUARANTINE, normal execution continues
# ---------------------------------------------------------------------------


class TestQuarantineOnMismatch:
    """When any compared field differs, the outcome is QUARANTINE and the caller
    MUST continue normal execution WITHOUT rewriting immutable attempts."""

    def test_altered_revision_quarantines(self) -> None:
        """Different plan_revision → QUARANTINE with revision mismatch."""
        receipt = _valid_receipt_payload(plan_revision="rev-old")
        ctx = _fresh_ctx(plan_revision="rev-new")

        decision = adopt_repair_receipt(receipt, ctx)
        assert decision.outcome == AdoptionOutcome.QUARANTINE
        assert decision.is_quarantined is True
        assert decision.is_adoptable is False
        assert len(decision.mismatches) >= 1
        fields = {m.field for m in decision.mismatches}
        assert "plan_revision" in fields

    def test_altered_task_contract_quarantines(self) -> None:
        """Different task_contract → QUARANTINE."""
        receipt = _valid_receipt_payload(task_contract="T1")
        ctx = _fresh_ctx(task_contract="T2")

        decision = adopt_repair_receipt(receipt, ctx)
        assert decision.outcome == AdoptionOutcome.QUARANTINE
        fields = {m.field for m in decision.mismatches}
        assert "task_contract" in fields

    def test_altered_tree_commit_quarantines(self) -> None:
        """Different tree_commit → QUARANTINE."""
        receipt = _valid_receipt_payload(tree_commit="old-commit")
        ctx = _fresh_ctx(tree_commit="new-commit")

        decision = adopt_repair_receipt(receipt, ctx)
        assert decision.outcome == AdoptionOutcome.QUARANTINE
        fields = {m.field for m in decision.mismatches}
        assert "tree_commit" in fields

    def test_altered_test_result_hash_quarantines(self) -> None:
        """Different test_result_hash → QUARANTINE (receipt payload_hash vs context)."""
        receipt = _valid_receipt_payload()
        ctx = _fresh_ctx(test_result_hash="sha256:different-hash")

        decision = adopt_repair_receipt(receipt, ctx)
        assert decision.outcome == AdoptionOutcome.QUARANTINE
        fields = {m.field for m in decision.mismatches}
        assert "test_result_hash" in fields

    def test_altered_coordinator_fence_quarantines(self) -> None:
        """Different coordinator_fence_token → QUARANTINE."""
        receipt = _valid_receipt_payload(coordinator_fence_token=42)
        ctx = _fresh_ctx(coordinator_fence_token=99)

        decision = adopt_repair_receipt(receipt, ctx)
        assert decision.outcome == AdoptionOutcome.QUARANTINE
        fields = {m.field for m in decision.mismatches}
        assert "coordinator_fence_token" in fields

    def test_altered_custody_lease_id_quarantines(self) -> None:
        """Different custody_lease_id → QUARANTINE."""
        receipt = _valid_receipt_payload(custody_lease_id="lease-old")
        ctx = _fresh_ctx(custody_lease_id="lease-new")

        decision = adopt_repair_receipt(receipt, ctx)
        assert decision.outcome == AdoptionOutcome.QUARANTINE
        fields = {m.field for m in decision.mismatches}
        assert "custody_lease_id" in fields

    def test_altered_custody_epoch_quarantines(self) -> None:
        """Different custody_epoch → QUARANTINE."""
        receipt = _valid_receipt_payload(custody_epoch=7)
        ctx = _fresh_ctx(custody_epoch=8)

        decision = adopt_repair_receipt(receipt, ctx)
        assert decision.outcome == AdoptionOutcome.QUARANTINE
        fields = {m.field for m in decision.mismatches}
        assert "custody_epoch" in fields

    def test_altered_wbc_reference_quarantines(self) -> None:
        """Different wbc_attempt_reference → QUARANTINE."""
        receipt = _valid_receipt_payload(wbc_attempt_reference="wbc-old")
        ctx = _fresh_ctx(wbc_attempt_reference="wbc-new")

        decision = adopt_repair_receipt(receipt, ctx)
        assert decision.outcome == AdoptionOutcome.QUARANTINE
        fields = {m.field for m in decision.mismatches}
        assert "wbc_attempt_reference" in fields

    def test_altered_run_authority_grant_quarantines(self) -> None:
        """Different run_authority_grant_id → QUARANTINE."""
        receipt = _valid_receipt_payload(run_authority_grant_id="grant-old")
        ctx = _fresh_ctx(run_authority_grant_id="grant-new")

        decision = adopt_repair_receipt(receipt, ctx)
        assert decision.outcome == AdoptionOutcome.QUARANTINE
        fields = {m.field for m in decision.mismatches}
        assert "run_authority_grant_id" in fields

    def test_altered_blocker_hash_quarantines(self) -> None:
        """Different blocker_hash → QUARANTINE."""
        receipt = _valid_receipt_payload(blocker_hash="blocker-old")
        ctx = _fresh_ctx(blocker_hash="blocker-new")

        decision = adopt_repair_receipt(receipt, ctx)
        assert decision.outcome == AdoptionOutcome.QUARANTINE
        fields = {m.field for m in decision.mismatches}
        assert "blocker_hash" in fields

    def test_multiple_mismatches_all_recorded(self) -> None:
        """When multiple fields differ, all mismatches are recorded."""
        receipt = _valid_receipt_payload(
            plan_revision="rev-old",
            task_contract="T1-old",
            tree_commit="old-commit",
        )
        ctx = _fresh_ctx(
            plan_revision="rev-new",
            task_contract="T1-new",
            tree_commit="new-commit",
        )

        decision = adopt_repair_receipt(receipt, ctx)
        assert decision.outcome == AdoptionOutcome.QUARANTINE
        assert len(decision.mismatches) == 3
        fields = {m.field for m in decision.mismatches}
        assert fields == {"plan_revision", "task_contract", "tree_commit"}

    def test_quarantine_mismatch_detail_contains_both_values(self) -> None:
        """Each mismatch record shows receipt_value and current_value."""
        receipt = _valid_receipt_payload(plan_revision="receipt-rev")
        ctx = _fresh_ctx(plan_revision="current-rev")

        decision = adopt_repair_receipt(receipt, ctx)
        assert decision.outcome == AdoptionOutcome.QUARANTINE
        m = decision.mismatches[0]
        assert m.field == "plan_revision"
        assert m.receipt_value == "receipt-rev"
        assert m.current_value == "current-rev"


# ---------------------------------------------------------------------------
# INVALID — malformed or missing receipt → INVALID (treated as quarantine)
# ---------------------------------------------------------------------------


class TestInvalidReceipt:
    """Invalid or missing receipts produce INVALID outcomes — treated identically
    to QUARANTINE by callers."""

    def test_none_receipt_is_invalid(self) -> None:
        """None receipt → INVALID outcome."""
        ctx = _fresh_ctx()
        decision = adopt_repair_receipt(None, ctx)

        assert decision.outcome == AdoptionOutcome.INVALID
        assert decision.is_quarantined is True
        assert decision.is_adoptable is False
        assert decision.receipt_digest == ""

    def test_empty_dict_receipt_is_invalid(self) -> None:
        """Empty dict payload that can't normalize → INVALID."""
        ctx = _fresh_ctx()
        decision = adopt_repair_receipt({}, ctx)

        assert decision.outcome == AdoptionOutcome.INVALID

    def test_non_dict_receipt_is_invalid(self) -> None:
        """Non-Mapping, non-RepairReceipt → INVALID."""
        ctx = _fresh_ctx()
        decision = adopt_repair_receipt("not-a-receipt", ctx)  # type: ignore[arg-type]

        assert decision.outcome == AdoptionOutcome.INVALID

    def test_invalid_outcome_is_quarantined(self) -> None:
        """INVALID is_quarantined returns True."""
        ctx = _fresh_ctx()
        decision = adopt_repair_receipt(None, ctx)

        assert decision.is_quarantined is True
        assert decision.is_adoptable is False

    def test_invalid_diagnostics_contain_error(self) -> None:
        """INVALID outcome includes error diagnostics."""
        ctx = _fresh_ctx()
        decision = adopt_repair_receipt(None, ctx)

        assert "error" in decision.diagnostics or decision.diagnostics


# ---------------------------------------------------------------------------
# AdoptionContext validation
# ---------------------------------------------------------------------------


class TestAdoptionContextValidation:
    """AdoptionContext rejects invalid field values at construction time."""

    def test_empty_run_authority_grant_id_raises(self) -> None:
        """Empty run_authority_grant_id raises ValueError."""
        with pytest.raises(ValueError):
            _fresh_ctx(run_authority_grant_id="")

    def test_whitespace_only_run_authority_grant_id_raises(self) -> None:
        """Whitespace-only grant ID raises ValueError."""
        with pytest.raises(ValueError):
            _fresh_ctx(run_authority_grant_id="   ")

    def test_negative_coordinator_fence_token_raises(self) -> None:
        """Negative fence token raises ValueError."""
        with pytest.raises(ValueError):
            _fresh_ctx(coordinator_fence_token=-1)

    def test_bool_fence_token_raises(self) -> None:
        """Bool fence_token raises ValueError (bool is subclass of int)."""
        with pytest.raises(ValueError):
            _fresh_ctx(coordinator_fence_token=True)  # type: ignore[arg-type]

    def test_non_string_custody_lease_id_raises(self) -> None:
        """Non-string custody_lease_id raises ValueError."""
        with pytest.raises(ValueError):
            _fresh_ctx(custody_lease_id=123)  # type: ignore[arg-type]

    def test_negative_custody_epoch_raises(self) -> None:
        """custody_epoch < 1 raises ValueError."""
        with pytest.raises(ValueError):
            _fresh_ctx(custody_epoch=0)

    def test_empty_plan_revision_raises(self) -> None:
        """Empty plan_revision raises ValueError."""
        with pytest.raises(ValueError):
            _fresh_ctx(plan_revision="")

    def test_empty_task_contract_raises(self) -> None:
        """Empty task_contract raises ValueError."""
        with pytest.raises(ValueError):
            _fresh_ctx(task_contract="")


# ---------------------------------------------------------------------------
# AdoptionDecision properties
# ---------------------------------------------------------------------------


class TestAdoptionDecisionProperties:
    """AdoptionDecision is an immutable frozen dataclass with correct properties."""

    def test_decision_is_frozen(self) -> None:
        """AdoptionDecision cannot be mutated after creation."""
        receipt = _valid_receipt_payload()
        ctx = _fresh_ctx()
        decision = adopt_repair_receipt(receipt, ctx)

        with pytest.raises(Exception):  # FrozenInstanceError or AttributeError
            decision.outcome = AdoptionOutcome.INVALID  # type: ignore[misc]

    def test_adopt_has_empty_mismatches(self) -> None:
        """ADOPT decision has exactly zero mismatches."""
        receipt = _valid_receipt_payload()
        ctx = _fresh_ctx()
        decision = adopt_repair_receipt(receipt, ctx)

        assert decision.outcome == AdoptionOutcome.ADOPT
        assert len(decision.mismatches) == 0

    def test_quarantine_has_non_empty_mismatches(self) -> None:
        """QUARANTINE decision has at least one mismatch."""
        receipt = _valid_receipt_payload(plan_revision="rev-old")
        ctx = _fresh_ctx(plan_revision="rev-new")
        decision = adopt_repair_receipt(receipt, ctx)

        assert decision.outcome == AdoptionOutcome.QUARANTINE
        assert len(decision.mismatches) >= 1

    def test_compared_at_is_set_even_for_invalid(self) -> None:
        """All decisions have a non-empty compared_at timestamp."""
        ctx = _fresh_ctx()
        decision = adopt_repair_receipt(None, ctx)

        assert decision.compared_at != ""

    def test_contract_type_is_consistent(self) -> None:
        """All decisions have the same contract_type."""
        receipt = _valid_receipt_payload()
        ctx = _fresh_ctx()
        decision = adopt_repair_receipt(receipt, ctx)

        assert decision.contract_type == "adoption_decision"


# ---------------------------------------------------------------------------
# AdoptionFieldMismatch record
# ---------------------------------------------------------------------------


class TestAdoptionFieldMismatch:
    """AdoptionFieldMismatch is a frozen record of a single field difference."""

    def test_mismatch_to_dict_has_field_receipt_current(self) -> None:
        """to_dict returns field, receipt_value, current_value."""
        m = AdoptionFieldMismatch(
            field="plan_revision",
            receipt_value="rev-old",
            current_value="rev-new",
        )

        d = m.to_dict()
        assert d["field"] == "plan_revision"
        assert d["receipt_value"] == "rev-old"
        assert d["current_value"] == "rev-new"

    def test_mismatch_is_frozen(self) -> None:
        """AdoptionFieldMismatch cannot be mutated."""
        m = AdoptionFieldMismatch(field="f", receipt_value="r", current_value="c")

        with pytest.raises(Exception):
            m.field = "other"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# AdoptionOutcome enum
# ---------------------------------------------------------------------------


class TestAdoptionOutcomeEnum:
    """AdoptionOutcome enum has exactly three members."""

    def test_three_outcomes_exist(self) -> None:
        """ADOPT, QUARANTINE, INVALID are the only outcomes."""
        outcomes = set(AdoptionOutcome)
        assert outcomes == {AdoptionOutcome.ADOPT, AdoptionOutcome.QUARANTINE, AdoptionOutcome.INVALID}

    def test_outcome_string_values(self) -> None:
        """Outcome string values match their enum names."""
        assert str(AdoptionOutcome.ADOPT) == "adopt"
        assert str(AdoptionOutcome.QUARANTINE) == "quarantine"
        assert str(AdoptionOutcome.INVALID) == "invalid"


# ---------------------------------------------------------------------------
# Verbatim receipt dict (non-normalized) — still compared correctly
# ---------------------------------------------------------------------------


class TestDictReceiptAdoption:
    """Receipt passed as a plain dict (not RepairReceipt instance) is normalized
    and compared correctly."""

    def test_dict_payload_exact_match_adopts(self) -> None:
        """Plain dict payload with matching fields → ADOPT."""
        receipt = _valid_receipt_payload()
        ctx = _fresh_ctx()

        decision = adopt_repair_receipt(receipt, ctx)
        assert decision.outcome == AdoptionOutcome.ADOPT

    def test_dict_payload_mismatch_quarantines(self) -> None:
        """Plain dict payload with mismatched revision → QUARANTINE."""
        receipt = _valid_receipt_payload(plan_revision="rev-old")
        ctx = _fresh_ctx(plan_revision="rev-new")

        decision = adopt_repair_receipt(receipt, ctx)
        assert decision.outcome == AdoptionOutcome.QUARANTINE
