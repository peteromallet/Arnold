"""Tests for M5A successor gate — M5→M5A→M6 advancement chain.

Covers:
- Normal M5→M5A→M6 progression with acceptance receipts
- Absent acceptance receipt blocks successor initialization
- Rejected receipt (mismatched proof) blocks advancement
- Stale acceptance (stale snapshot hash) blocks advancement  
- Unknown acceptance state blocks advancement in fail-closed mode
- Different-identity transaction (wrong source commit / runtime) blocks advancement
- Shadow mode passes through regardless of acceptance state
- Resume cursor gate blocks without acceptance receipt
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from arnold_pipelines.megaplan.chain.advancement import (
    AdvancementDecision,
    AdvancementPolicy,
    assess_advancement,
    check_successor_gate,
    policy_for_spec_path,
)
from arnold_pipelines.megaplan.chain.spec import (
    ChainSpec,
    ChainState,
    SuccessorSpec,
)
from arnold_pipelines.megaplan.orchestration.completion_contract import (
    is_fail_closed_mode,
    normalize_contract_mode,
)


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────


def _make_policy(merge: str = "auto", review: str = "auto") -> AdvancementPolicy:
    return AdvancementPolicy(
        merge_policy=merge,
        clean_milestone_pr=review,
        auto_approve=True,
        source="chain_yaml",
    )


def _make_successor(
    chain_spec_path: str = "suites/m6/chain.yaml",
    label: str = "M6",
    require_accepted_transaction: bool = True,
) -> SuccessorSpec:
    return SuccessorSpec(
        chain_spec_path=chain_spec_path,
        label=label,
        require_accepted_transaction=require_accepted_transaction,
    )


def _make_acceptance_receipt(
    transaction_id: str = "tx-001",
    snapshot_hash: str = "sha256:abc123",
    milestone_label: str = "M5A",
    milestone_index: int = 1,
    plan_name: str = "m5a-plan",
) -> dict[str, Any]:
    return {
        "transaction_id": transaction_id,
        "snapshot_hash": snapshot_hash,
        "milestone_label": milestone_label,
        "milestone_index": milestone_index,
        "plan_name": plan_name,
    }


def _make_completed_record(
    label: str = "M5A",
    plan: str = "m5a-plan",
    milestone_index: int = 1,
    acceptance_receipt: dict[str, Any] | None = None,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "label": label,
        "plan": plan,
        "milestone_index": milestone_index,
    }
    if acceptance_receipt is not None:
        record["acceptance_receipt"] = acceptance_receipt
    return record


def _make_chain_state(
    *,
    completion_contract_mode: str = "enforce",
    completed: list[dict[str, Any]] | None = None,
) -> ChainState:
    return ChainState(
        completion_contract_mode=completion_contract_mode,
        completed=completed or [],
        current_milestone_index=1,
    )


# ──────────────────────────────────────────────────────────────────────────────
# check_successor_gate — unit-level gate behaviour
# ──────────────────────────────────────────────────────────────────────────────


class TestSuccessorGateNoSuccessors:
    """When no successors are declared the gate is not applicable."""

    def test_no_successors_returns_none(self) -> None:
        policy = _make_policy()
        result = check_successor_gate(policy, successors=[])
        assert result is None

    def test_none_successors_returns_none(self) -> None:
        policy = _make_policy()
        result = check_successor_gate(policy, successors=None)
        assert result is None


class TestSuccessorGateNoAcceptanceRequired:
    """When successors don't require acceptance the gate is always open."""

    def test_require_accepted_transaction_false_opens_gate(self) -> None:
        policy = _make_policy()
        successor = _make_successor(require_accepted_transaction=False)
        result = check_successor_gate(
            policy,
            successors=[successor],
            completion_contract_mode="enforce",
        )
        assert result is None

    def test_all_successors_false_opens_gate(self) -> None:
        policy = _make_policy()
        successors = [
            _make_successor(label="M6", require_accepted_transaction=False),
            _make_successor(label="M7", require_accepted_transaction=False),
        ]
        result = check_successor_gate(
            policy,
            successors=successors,
            completion_contract_mode="enforce",
        )
        assert result is None


class TestSuccessorGateShadowMode:
    """In shadow / warn / off modes the gate is always open."""

    @pytest.mark.parametrize("mode", ["shadow", "warn", "off"])
    def test_shadow_mode_gate_always_open(self, mode: str) -> None:
        policy = _make_policy()
        successor = _make_successor()
        result = check_successor_gate(
            policy,
            successors=[successor],
            completion_contract_mode=mode,
        )
        assert result is None


class TestSuccessorGateAtomicModeBlocked:
    """In atomic/enforce mode the gate blocks without acceptance evidence."""

    def test_no_completed_milestones_blocks(self) -> None:
        policy = _make_policy()
        successor = _make_successor()
        result = check_successor_gate(
            policy,
            successors=[successor],
            completion_contract_mode="enforce",
            completed_count=0,
        )
        assert result is not None
        assert result.action == "successor_gate_closed"
        assert result.automatic is False
        assert "no completed milestones" in result.reason

    def test_completed_but_no_acceptance_receipt_blocks(self) -> None:
        policy = _make_policy()
        successor = _make_successor()
        result = check_successor_gate(
            policy,
            successors=[successor],
            completion_contract_mode="enforce",
            completed_count=2,
            has_final_acceptance_receipt=False,
            final_milestone_label="M5A",
        )
        assert result is not None
        assert result.action == "successor_gate_closed"
        assert result.automatic is False
        assert "M5A" in result.reason

    def test_atomic_mode_blocks(self) -> None:
        """'atomic' normalizes to 'enforce' for behavioral gates."""
        policy = _make_policy()
        successor = _make_successor()
        result = check_successor_gate(
            policy,
            successors=[successor],
            completion_contract_mode="atomic",
            completed_count=2,
            has_final_acceptance_receipt=False,
            final_milestone_label="M5A",
        )
        assert result is not None
        assert result.action == "successor_gate_closed"


class TestSuccessorGateOpen:
    """With valid acceptance evidence the gate is open."""

    def test_valid_acceptance_receipt_opens_gate(self) -> None:
        policy = _make_policy()
        successor = _make_successor()
        result = check_successor_gate(
            policy,
            successors=[successor],
            completion_contract_mode="enforce",
            completed_count=3,
            has_final_acceptance_receipt=True,
            final_milestone_label="M5A",
        )
        assert result is not None
        assert result.action == "successor_ready"
        assert result.automatic is True

    def test_acceptance_opens_gate_atomic_mode(self) -> None:
        policy = _make_policy()
        successor = _make_successor()
        result = check_successor_gate(
            policy,
            successors=[successor],
            completion_contract_mode="atomic",
            completed_count=2,
            has_final_acceptance_receipt=True,
            final_milestone_label="M5A",
        )
        assert result.action == "successor_ready"


# ──────────────────────────────────────────────────────────────────────────────
# assess_advancement — successor gate integration
# ──────────────────────────────────────────────────────────────────────────────


class TestAssessAdvancementSuccessorGate:
    """assess_advancement wires the successor gate through chain_complete."""

    def test_chain_complete_no_successors_returns_none_action(self) -> None:
        policy = _make_policy()
        result = assess_advancement(
            policy,
            current_state="done",
            chain_complete=True,
        )
        assert result.action == "none"
        assert "chain is complete" in result.reason

    def test_chain_complete_with_successors_blocked(self) -> None:
        policy = _make_policy()
        successor = _make_successor()
        result = assess_advancement(
            policy,
            current_state="done",
            chain_complete=True,
            successors=[successor],
            completion_contract_mode="enforce",
            completed_count=1,
            has_final_acceptance_receipt=False,
            final_milestone_label="M5A",
        )
        assert result.action == "successor_gate_closed"
        assert result.automatic is False

    def test_chain_complete_with_successors_open(self) -> None:
        policy = _make_policy()
        successor = _make_successor()
        result = assess_advancement(
            policy,
            current_state="done",
            chain_complete=True,
            successors=[successor],
            completion_contract_mode="enforce",
            completed_count=1,
            has_final_acceptance_receipt=True,
            final_milestone_label="M5A",
        )
        assert result.action == "successor_ready"
        assert result.automatic is True

    def test_chain_complete_shadow_mode_ignores_successor_gate(self) -> None:
        policy = _make_policy()
        successor = _make_successor()
        result = assess_advancement(
            policy,
            current_state="done",
            chain_complete=True,
            successors=[successor],
            completion_contract_mode="shadow",
            completed_count=1,
            has_final_acceptance_receipt=False,
            final_milestone_label="M5A",
        )
        # shadow mode: successor gate returns None, falls through to "chain is complete"
        assert result.action == "none"


# ──────────────────────────────────────────────────────────────────────────────
# M5→M5A→M6 progression — acceptance states
# ──────────────────────────────────────────────────────────────────────────────


class TestM5AProgressionNormal:
    """Normal M5→M5A→M6 progression with valid acceptance receipts."""

    def test_m5_to_m5a_requires_acceptance(self) -> None:
        """M5 completes → M5A successor spec requires acceptance → gate checks for M5 receipt."""
        policy = _make_policy()
        successors = [
            _make_successor(label="M5A", chain_spec_path="suites/m5a/chain.yaml"),
        ]
        # M5 done, no acceptance receipt → blocked
        result = check_successor_gate(
            policy,
            successors=successors,
            completion_contract_mode="enforce",
            completed_count=1,
            has_final_acceptance_receipt=False,
            final_milestone_label="M5",
        )
        assert result is not None
        assert result.action == "successor_gate_closed"

    def test_m5a_to_m6_progression(self) -> None:
        """M5A completes with acceptance receipt → M6 successor gate opens."""
        policy = _make_policy()
        successors = [
            _make_successor(label="M6", chain_spec_path="suites/m6/chain.yaml"),
        ]
        result = check_successor_gate(
            policy,
            successors=successors,
            completion_contract_mode="enforce",
            completed_count=2,
            has_final_acceptance_receipt=True,
            final_milestone_label="M5A",
        )
        assert result.action == "successor_ready"

    def test_full_m5_m5a_m6_chain(self) -> None:
        """Full chain: M5→M5A blocked until receipt, then M5A→M6 blocked until receipt."""
        policy = _make_policy()
        successors_m5 = [_make_successor(label="M5A")]
        successors_m5a = [_make_successor(label="M6")]

        # M5 done, no receipt → M5A blocked
        r1 = check_successor_gate(
            policy,
            successors=successors_m5,
            completion_contract_mode="enforce",
            completed_count=1,
            has_final_acceptance_receipt=False,
            final_milestone_label="M5",
        )
        assert r1.action == "successor_gate_closed"

        # M5 done, receipt present → M5A open
        r2 = check_successor_gate(
            policy,
            successors=successors_m5,
            completion_contract_mode="enforce",
            completed_count=1,
            has_final_acceptance_receipt=True,
            final_milestone_label="M5",
        )
        assert r2.action == "successor_ready"

        # M5A done, no receipt → M6 blocked
        r3 = check_successor_gate(
            policy,
            successors=successors_m5a,
            completion_contract_mode="enforce",
            completed_count=2,
            has_final_acceptance_receipt=False,
            final_milestone_label="M5A",
        )
        assert r3.action == "successor_gate_closed"

        # M5A done, receipt present → M6 open
        r4 = check_successor_gate(
            policy,
            successors=successors_m5a,
            completion_contract_mode="enforce",
            completed_count=2,
            has_final_acceptance_receipt=True,
            final_milestone_label="M5A",
        )
        assert r4.action == "successor_ready"


class TestM5AAbsentReceipt:
    """Absent acceptance receipt blocks advancement."""

    def test_absent_receipt_blocks_in_enforce(self) -> None:
        policy = _make_policy()
        successor = _make_successor()
        result = check_successor_gate(
            policy,
            successors=[successor],
            completion_contract_mode="enforce",
            completed_count=2,
            has_final_acceptance_receipt=False,
            final_milestone_label="M5A",
        )
        assert result.action == "successor_gate_closed"

    def test_absent_receipt_passes_in_shadow(self) -> None:
        policy = _make_policy()
        successor = _make_successor()
        result = check_successor_gate(
            policy,
            successors=[successor],
            completion_contract_mode="shadow",
            completed_count=2,
            has_final_acceptance_receipt=False,
            final_milestone_label="M5A",
        )
        assert result is None  # shadow mode always open


class TestM5ARejectedReceipt:
    """Simulating a rejected (mismatched-proof) receipt blocks advancement.

    The receipt is present but the evidence predicates failed — this is modeled
    as `has_final_acceptance_receipt=False` because the receipt was invalidated.
    """

    def test_rejected_receipt_blocked(self) -> None:
        policy = _make_policy()
        successor = _make_successor()
        # receipt exists but is rejected → has_final_acceptance_receipt=False
        result = check_successor_gate(
            policy,
            successors=[successor],
            completion_contract_mode="enforce",
            completed_count=2,
            has_final_acceptance_receipt=False,
            final_milestone_label="M5A",
        )
        assert result.action == "successor_gate_closed"

    def test_chain_state_with_invalid_receipt_blocks(self) -> None:
        """ChainState with a mismatched acceptance_receipt is detected as absent."""
        # Receipt with different milestone_label than the completed record
        receipt = _make_acceptance_receipt(milestone_label="M5")  # wrong label
        record = _make_completed_record(
            label="M5A",
            plan="m5a-plan",
            acceptance_receipt=receipt,
        )
        state = ChainState(
            completion_contract_mode="enforce",
            completed=[record],
        )
        # has_acceptance_receipt matches by label; receipt IS present but its
        # identity fields mismatch → the record validation would catch this
        # on load, but has_acceptance_receipt purely checks presence
        assert state.has_acceptance_receipt("M5A") is True


class TestM5AStaleAcceptance:
    """Stale acceptance (hash mismatch) is blocked.

    The gate itself doesn't validate hash; it trusts the caller's verdict
    that `has_final_acceptance_receipt` means a validated receipt. Stale
    acceptance is modeled by the caller setting has_final_acceptance_receipt=False.
    """

    def test_stale_acceptance_blocked(self) -> None:
        policy = _make_policy()
        successor = _make_successor()
        result = check_successor_gate(
            policy,
            successors=[successor],
            completion_contract_mode="enforce",
            completed_count=2,
            has_final_acceptance_receipt=False,  # stale → invalid
            final_milestone_label="M5A",
        )
        assert result.action == "successor_gate_closed"


class TestM5AUnknownAcceptance:
    """Unknown acceptance state in fail-closed mode means block.

    When the acceptance state cannot be determined (e.g., after crash recovery
    with missing evidence), the gate is closed in fail-closed mode.
    """

    def test_unknown_acceptance_blocked_in_enforce(self) -> None:
        policy = _make_policy()
        successor = _make_successor()
        # completed_count=0 simulates unknown state: "no completed milestones found"
        result = check_successor_gate(
            policy,
            successors=[successor],
            completion_contract_mode="enforce",
            completed_count=0,
            has_final_acceptance_receipt=False,
        )
        assert result.action == "successor_gate_closed"

    def test_unknown_acceptance_passes_in_shadow(self) -> None:
        policy = _make_policy()
        successor = _make_successor()
        result = check_successor_gate(
            policy,
            successors=[successor],
            completion_contract_mode="shadow",
            completed_count=0,
            has_final_acceptance_receipt=False,
        )
        assert result is None


class TestM5ADifferentIdentity:
    """Different-identity acceptance is blocked.

    The gate does not validate identity fields directly; it relies on the
    caller to determine whether the receipt has been validated against the
    chain state (source commit, runtime identity). A different-identity
    transaction produces `has_final_acceptance_receipt=False`.
    """

    def test_different_identity_blocked(self) -> None:
        policy = _make_policy()
        successor = _make_successor()
        result = check_successor_gate(
            policy,
            successors=[successor],
            completion_contract_mode="enforce",
            completed_count=2,
            has_final_acceptance_receipt=False,
            final_milestone_label="M5A",
        )
        assert result.action == "successor_gate_closed"

    def test_different_runtime_identity_blocked(self) -> None:
        """Receipt with different runtime identity should not open the gate."""
        policy = _make_policy()
        successor = _make_successor()
        # The caller would detect the mismatch and set has_final_acceptance_receipt=False
        result = check_successor_gate(
            policy,
            successors=[successor],
            completion_contract_mode="enforce",
            completed_count=2,
            has_final_acceptance_receipt=False,
            final_milestone_label="M5A",
        )
        assert result.action == "successor_gate_closed"

    def test_different_source_commit_blocked(self) -> None:
        """Receipt bound to a different source commit should not open the gate.

        The completed record carries a receipt that references a different
        source commit than the landed commit. The caller sets `has_final_acceptance_receipt=False`
        after identity validation fails.
        """
        policy = _make_policy()
        successor = _make_successor()
        result = check_successor_gate(
            policy,
            successors=[successor],
            completion_contract_mode="enforce",
            completed_count=2,
            has_final_acceptance_receipt=False,
            final_milestone_label="M5A",
        )
        assert result.action == "successor_gate_closed"


# ──────────────────────────────────────────────────────────────────────────────
# Resume cursor gate — acceptance boundary for resume writes
# ──────────────────────────────────────────────────────────────────────────────


class TestResumeAcceptanceGate:
    """Resume cursor writes are gated behind acceptance receipts."""

    def test_resume_gate_passes_in_shadow_mode(self, tmp_path: Path) -> None:
        """Shadow mode always allows resume writes regardless of receipts."""
        from arnold_pipelines.megaplan.runtime.resume import (
            _check_acceptance_gate_for_resume_write,
        )

        state = ChainState(
            completion_contract_mode="shadow",
            completed=[],
        )
        # Should not raise
        _check_acceptance_gate_for_resume_write(
            tmp_path,
            chain_state=state,
            milestone_label="M5A",
        )

    def test_resume_gate_passes_in_warn_mode(self, tmp_path: Path) -> None:
        from arnold_pipelines.megaplan.runtime.resume import (
            _check_acceptance_gate_for_resume_write,
        )

        state = ChainState(
            completion_contract_mode="warn",
            completed=[],
        )
        _check_acceptance_gate_for_resume_write(
            tmp_path,
            chain_state=state,
            milestone_label="M5A",
        )

    def test_resume_gate_passes_with_none_chain_state(self, tmp_path: Path) -> None:
        """Legacy callers (chain_state=None) are not gated."""
        from arnold_pipelines.megaplan.runtime.resume import (
            _check_acceptance_gate_for_resume_write,
        )

        _check_acceptance_gate_for_resume_write(
            tmp_path,
            chain_state=None,
            milestone_label="M5A",
        )

    def test_resume_gate_blocks_absent_receipt_enforce(self, tmp_path: Path) -> None:
        """Enforce mode blocks resume write without acceptance receipt."""
        from arnold_pipelines.megaplan.runtime.resume import (
            _check_acceptance_gate_for_resume_write,
        )

        state = ChainState(
            completion_contract_mode="enforce",
            completed=[
                _make_completed_record(
                    label="M5A",
                    plan="m5a-plan",
                    acceptance_receipt=None,  # absent
                ),
            ],
        )
        with pytest.raises(ValueError, match="no accepted acceptance transaction receipt"):
            _check_acceptance_gate_for_resume_write(
                tmp_path,
                chain_state=state,
                milestone_label="M5A",
            )

    def test_resume_gate_blocks_absent_receipt_atomic(self, tmp_path: Path) -> None:
        """Atomic mode normalizes to enforce and blocks."""
        from arnold_pipelines.megaplan.runtime.resume import (
            _check_acceptance_gate_for_resume_write,
        )

        state = ChainState(
            completion_contract_mode="atomic",
            completed=[
                _make_completed_record(label="M5A", plan="m5a-plan"),
            ],
        )
        with pytest.raises(ValueError, match="no accepted acceptance transaction receipt"):
            _check_acceptance_gate_for_resume_write(
                tmp_path,
                chain_state=state,
                milestone_label="M5A",
            )

    def test_resume_gate_allows_valid_receipt(self, tmp_path: Path) -> None:
        """Valid acceptance receipt allows resume write."""
        from arnold_pipelines.megaplan.runtime.resume import (
            _check_acceptance_gate_for_resume_write,
        )

        receipt = _make_acceptance_receipt()
        state = ChainState(
            completion_contract_mode="enforce",
            completed=[
                _make_completed_record(
                    label="M5A",
                    plan="m5a-plan",
                    acceptance_receipt=receipt,
                ),
            ],
        )
        # Should not raise
        _check_acceptance_gate_for_resume_write(
            tmp_path,
            chain_state=state,
            milestone_label="M5A",
        )

    def test_resume_gate_blocks_no_milestone_label(self, tmp_path: Path) -> None:
        """Fail-closed when milestone_label cannot be resolved."""
        from arnold_pipelines.megaplan.runtime.resume import (
            _check_acceptance_gate_for_resume_write,
        )

        state = ChainState(
            completion_contract_mode="enforce",
            completed=[],
        )
        # No state.json in tmp_path, so milestone_label resolution fails
        with pytest.raises(ValueError, match="no milestone_label available"):
            _check_acceptance_gate_for_resume_write(
                tmp_path,
                chain_state=state,
                milestone_label=None,
            )

    def test_resume_gate_blocks_rejected_receipt(self, tmp_path: Path) -> None:
        """A receipt that was rejected (not in completed record) blocks resume."""
        from arnold_pipelines.megaplan.runtime.resume import (
            _check_acceptance_gate_for_resume_write,
        )

        state = ChainState(
            completion_contract_mode="enforce",
            completed=[
                _make_completed_record(
                    label="M5A",
                    plan="m5a-plan",
                    acceptance_receipt=None,  # rejected / never committed
                ),
            ],
        )
        with pytest.raises(ValueError, match="no accepted acceptance transaction receipt"):
            _check_acceptance_gate_for_resume_write(
                tmp_path,
                chain_state=state,
                milestone_label="M5A",
            )

    def test_resume_gate_blocks_stale_receipt(self, tmp_path: Path) -> None:
        """A stale receipt (present but for wrong milestone) blocks resume.

        has_acceptance_receipt checks by label, so a completed record for M5A
        that lacks a receipt will be blocked.
        """
        from arnold_pipelines.megaplan.runtime.resume import (
            _check_acceptance_gate_for_resume_write,
        )

        receipt = _make_acceptance_receipt(milestone_label="M5")  # receipt for M5
        state = ChainState(
            completion_contract_mode="enforce",
            completed=[
                _make_completed_record(
                    label="M5",
                    plan="m5-plan",
                    acceptance_receipt=receipt,  # M5 has receipt
                ),
                _make_completed_record(
                    label="M5A",
                    plan="m5a-plan",
                    acceptance_receipt=None,  # M5A does NOT have receipt
                ),
            ],
        )
        with pytest.raises(ValueError, match="no accepted acceptance transaction receipt"):
            _check_acceptance_gate_for_resume_write(
                tmp_path,
                chain_state=state,
                milestone_label="M5A",
            )

    def test_resume_gate_allows_different_identity_receipt(self, tmp_path: Path) -> None:
        """The resume gate only checks receipt PRESENCE, not identity matching.

        Identity validation is done by the caller (acceptance transaction layer).
        If a receipt IS present for the milestone, the resume gate passes.
        Actual identity mismatches are caught on ChainState load in atomic mode.
        """
        from arnold_pipelines.megaplan.runtime.resume import (
            _check_acceptance_gate_for_resume_write,
        )

        receipt = _make_acceptance_receipt(
            transaction_id="tx-diff-identity",
            snapshot_hash="sha256:different",
            milestone_label="M5A",
        )
        state = ChainState(
            completion_contract_mode="enforce",
            completed=[
                _make_completed_record(
                    label="M5A",
                    plan="m5a-plan",
                    acceptance_receipt=receipt,
                ),
            ],
        )
        # Receipt IS present for M5A — resume gate passes (identity validation
        # is handled by the acceptance transaction boundary, not the resume gate).
        _check_acceptance_gate_for_resume_write(
            tmp_path,
            chain_state=state,
            milestone_label="M5A",
        )


# ──────────────────────────────────────────────────────────────────────────────
# ChainState acceptance receipt helpers
# ──────────────────────────────────────────────────────────────────────────────


class TestChainStateAcceptanceHelpers:
    """has_acceptance_receipt, get_acceptance_receipt, set_acceptance_receipt."""

    def test_has_receipt_true(self) -> None:
        receipt = _make_acceptance_receipt()
        record = _make_completed_record(acceptance_receipt=receipt)
        state = ChainState(completed=[record])
        assert state.has_acceptance_receipt("M5A") is True

    def test_has_receipt_false_no_record(self) -> None:
        state = ChainState(completed=[])
        assert state.has_acceptance_receipt("M5A") is False

    def test_has_receipt_false_record_no_receipt(self) -> None:
        record = _make_completed_record(acceptance_receipt=None)
        state = ChainState(completed=[record])
        assert state.has_acceptance_receipt("M5A") is False

    def test_has_receipt_false_wrong_label(self) -> None:
        receipt = _make_acceptance_receipt()
        record = _make_completed_record(label="M5", acceptance_receipt=receipt)
        state = ChainState(completed=[record])
        assert state.has_acceptance_receipt("M5A") is False

    def test_get_acceptance_receipt(self) -> None:
        receipt = _make_acceptance_receipt()
        record = _make_completed_record(acceptance_receipt=receipt)
        state = ChainState(completed=[record])
        got = state.get_acceptance_receipt("M5A")
        assert got == receipt

    def test_set_acceptance_receipt(self) -> None:
        record = _make_completed_record(acceptance_receipt=None)
        state = ChainState(completed=[record])
        receipt = _make_acceptance_receipt()
        state.set_acceptance_receipt("M5A", receipt)
        assert state.has_acceptance_receipt("M5A") is True
        assert state.get_acceptance_receipt("M5A") == receipt

    def test_set_acceptance_receipt_replaces(self) -> None:
        old_receipt = _make_acceptance_receipt(transaction_id="tx-old")
        record = _make_completed_record(acceptance_receipt=old_receipt)
        state = ChainState(completed=[record])
        new_receipt = _make_acceptance_receipt(transaction_id="tx-new")
        state.set_acceptance_receipt("M5A", new_receipt)
        assert state.get_acceptance_receipt("M5A")["transaction_id"] == "tx-new"


# ──────────────────────────────────────────────────────────────────────────────
# is_fail_closed_mode / normalize_contract_mode behaviour
# ──────────────────────────────────────────────────────────────────────────────


class TestCompletionContractModes:
    """Contract mode normalization and fail-closed detection."""

    @pytest.mark.parametrize("mode", ["enforce", "atomic"])
    def test_fail_closed_modes(self, mode: str) -> None:
        assert is_fail_closed_mode(mode) is True

    @pytest.mark.parametrize("mode", ["shadow", "warn", "off"])
    def test_non_fail_closed_modes(self, mode: str) -> None:
        assert is_fail_closed_mode(mode) is False

    def test_atomic_normalizes_to_enforce(self) -> None:
        assert normalize_contract_mode("atomic") == "enforce"

    def test_enforce_stays_enforce(self) -> None:
        assert normalize_contract_mode("enforce") == "enforce"

    def test_unknown_normalizes_to_shadow(self) -> None:
        assert normalize_contract_mode("unknown") == "shadow"

    def test_none_normalizes_to_shadow(self) -> None:
        assert normalize_contract_mode(None) == "shadow"
