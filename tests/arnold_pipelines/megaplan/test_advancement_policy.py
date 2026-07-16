from __future__ import annotations

from pathlib import Path

import pytest

from arnold_pipelines.megaplan.chain.advancement import (
    AdvancementPolicy,
    assess_advancement,
    check_successor_gate,
    policy_for_spec_path,
)
from arnold_pipelines.megaplan.chain import _automatic_pr_progression_permitted
from arnold_pipelines.megaplan.chain.spec import (
    ChainState,
    SuccessorSpec,
    load_spec,
)


def _write_spec(path: Path, *, merge: str = "auto", review: str = "auto") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""merge_policy: {merge}
review_policy:
  clean_milestone_pr: {review}
driver:
  auto_approve: true
milestones: []
""",
        encoding="utf-8",
    )


def test_runtime_manual_review_override_disables_automatic_pr_progression(
    tmp_path: Path,
) -> None:
    spec_path = tmp_path / "initiative" / "chain.yaml"
    _write_spec(spec_path)
    # Use the production writer rather than assuming the sidecar filename.
    from arnold_pipelines.megaplan.chain.spec import save_runtime_policy

    save_runtime_policy(
        spec_path,
        {"review_policy": {"clean_milestone_pr": "manual"}},
    )

    policy = policy_for_spec_path(spec_path)

    assert policy.automatic_pr_progression is False
    assert policy.clean_milestone_pr == "manual"
    assert policy.source == "runtime_override"
    assert _automatic_pr_progression_permitted(load_spec(spec_path), spec_path) is False


def test_awaiting_pr_merge_respects_manual_review_but_merged_evidence_advances(
    tmp_path: Path,
) -> None:
    spec_path = tmp_path / "initiative" / "chain.yaml"
    _write_spec(spec_path, review="manual")
    policy = policy_for_spec_path(spec_path)

    waiting = assess_advancement(
        policy,
        current_state="done",
        chain_last_state="awaiting_pr_merge",
        pr_state="open",
    )
    merged = assess_advancement(
        policy,
        current_state="done",
        chain_last_state="awaiting_pr_merge",
        pr_state="merged",
    )

    assert waiting.action == "await_human"
    assert waiting.automatic is False
    assert waiting.gate == "review_policy.clean_milestone_pr"
    assert merged.action == "reconcile_terminal"
    assert merged.automatic is True


def test_review_and_between_milestone_actions_are_automatic_when_policy_allows(
    tmp_path: Path,
) -> None:
    spec_path = tmp_path / "initiative" / "chain.yaml"
    _write_spec(spec_path)
    policy = policy_for_spec_path(spec_path)

    review = assess_advancement(policy, current_state="executed")
    between = assess_advancement(
        policy,
        current_state="done",
        chain_last_state="between_milestones",
    )

    assert (review.action, review.automatic) == ("run_review", True)
    # Terminal reconciliation is the first safe action; the normal chain then
    # initializes the next milestone through its guarded loop.
    assert (between.action, between.automatic) == ("reconcile_terminal", True)


def test_explicit_human_and_security_gates_always_win(tmp_path: Path) -> None:
    spec_path = tmp_path / "initiative" / "chain.yaml"
    _write_spec(spec_path)
    policy = policy_for_spec_path(spec_path)

    for gate in ("security_approval", "credential_account", "verification"):
        decision = assess_advancement(
            policy,
            current_state="executed",
            explicit_human_gate=gate,
        )
        assert decision.action == "await_human"
        assert decision.automatic is False
        assert decision.gate == gate


def test_active_step_is_never_duplicated(tmp_path: Path) -> None:
    spec_path = tmp_path / "initiative" / "chain.yaml"
    _write_spec(spec_path)
    decision = assess_advancement(
        policy_for_spec_path(spec_path),
        current_state="executed",
        active_step=True,
    )

    assert decision.action == "preserve_live"
    assert decision.automatic is False


# ──────────────────────────────────────────────────────────────────────────────
# Successor gate — M5→M5A→M6 advancement and acceptance states
# ──────────────────────────────────────────────────────────────────────────────


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


class TestAdvancementSuccessorGate:
    """Successor gate wired through assess_advancement (chain_complete path)."""

    def test_normal_m5_to_m5a_progression_with_receipt(self) -> None:
        """M5 completes with acceptance receipt → M5A successor gate opens."""
        policy = AdvancementPolicy("auto", "auto", True, "chain_yaml")
        successors = [_make_successor(label="M5A", chain_spec_path="suites/m5a/chain.yaml")]
        result = assess_advancement(
            policy,
            current_state="done",
            chain_complete=True,
            successors=successors,
            completion_contract_mode="enforce",
            completed_count=1,
            has_final_acceptance_receipt=True,
            final_milestone_label="M5",
        )
        assert result.action == "successor_ready"
        assert result.automatic is True

    def test_normal_m5a_to_m6_progression_with_receipt(self) -> None:
        """M5A completes with acceptance receipt → M6 successor gate opens."""
        policy = AdvancementPolicy("auto", "auto", True, "chain_yaml")
        successors = [_make_successor(label="M6", chain_spec_path="suites/m6/chain.yaml")]
        result = assess_advancement(
            policy,
            current_state="done",
            chain_complete=True,
            successors=successors,
            completion_contract_mode="enforce",
            completed_count=2,
            has_final_acceptance_receipt=True,
            final_milestone_label="M5A",
        )
        assert result.action == "successor_ready"
        assert result.automatic is True

    def test_absent_receipt_blocks_m5a_advancement(self) -> None:
        """No acceptance receipt for M5 → M5A blocked in enforce mode."""
        policy = AdvancementPolicy("auto", "auto", True, "chain_yaml")
        successors = [_make_successor(label="M5A")]
        result = assess_advancement(
            policy,
            current_state="done",
            chain_complete=True,
            successors=successors,
            completion_contract_mode="enforce",
            completed_count=1,
            has_final_acceptance_receipt=False,
            final_milestone_label="M5",
        )
        assert result.action == "successor_gate_closed"
        assert result.automatic is False
        assert result.gate == "successor_acceptance"

    def test_rejected_receipt_blocks_advancement(self) -> None:
        """A receipt that was rejected (predicate failures) blocks advancement."""
        policy = AdvancementPolicy("auto", "auto", True, "chain_yaml")
        successors = [_make_successor(label="M5A")]
        result = assess_advancement(
            policy,
            current_state="done",
            chain_complete=True,
            successors=successors,
            completion_contract_mode="enforce",
            completed_count=1,
            has_final_acceptance_receipt=False,  # rejected → False
            final_milestone_label="M5",
        )
        assert result.action == "successor_gate_closed"

    def test_stale_receipt_blocks_advancement(self) -> None:
        """A stale acceptance (old snapshot hash) blocks advancement."""
        policy = AdvancementPolicy("auto", "auto", True, "chain_yaml")
        successors = [_make_successor(label="M5A")]
        result = assess_advancement(
            policy,
            current_state="done",
            chain_complete=True,
            successors=successors,
            completion_contract_mode="enforce",
            completed_count=1,
            has_final_acceptance_receipt=False,  # stale → invalid → False
            final_milestone_label="M5",
        )
        assert result.action == "successor_gate_closed"

    def test_unknown_acceptance_blocks_advancement(self) -> None:
        """Unknown acceptance state (crash recovery, missing evidence) blocks."""
        policy = AdvancementPolicy("auto", "auto", True, "chain_yaml")
        successors = [_make_successor(label="M5A")]
        result = assess_advancement(
            policy,
            current_state="done",
            chain_complete=True,
            successors=successors,
            completion_contract_mode="enforce",
            completed_count=0,  # unknown — no completed milestones found
            has_final_acceptance_receipt=False,
            final_milestone_label="M5",
        )
        assert result.action == "successor_gate_closed"

    def test_different_identity_blocks_advancement(self) -> None:
        """A receipt bound to a different source commit or runtime blocks."""
        policy = AdvancementPolicy("auto", "auto", True, "chain_yaml")
        successors = [_make_successor(label="M5A")]
        result = assess_advancement(
            policy,
            current_state="done",
            chain_complete=True,
            successors=successors,
            completion_contract_mode="enforce",
            completed_count=1,
            has_final_acceptance_receipt=False,  # different identity → invalid
            final_milestone_label="M5",
        )
        assert result.action == "successor_gate_closed"
        assert result.gate == "successor_acceptance"

    def test_shadow_mode_passes_absent_receipt(self) -> None:
        """Shadow mode: absent receipt does not block (gate always open)."""
        policy = AdvancementPolicy("auto", "auto", True, "chain_yaml")
        successors = [_make_successor(label="M5A")]
        result = assess_advancement(
            policy,
            current_state="done",
            chain_complete=True,
            successors=successors,
            completion_contract_mode="shadow",
            completed_count=1,
            has_final_acceptance_receipt=False,
            final_milestone_label="M5",
        )
        # shadow mode → gate returns None → falls through to "chain is complete"
        assert result.action == "none"

    def test_shadow_mode_passes_rejected_receipt(self) -> None:
        """Shadow mode: rejected receipt does not block."""
        policy = AdvancementPolicy("auto", "auto", True, "chain_yaml")
        successors = [_make_successor(label="M5A")]
        result = assess_advancement(
            policy,
            current_state="done",
            chain_complete=True,
            successors=successors,
            completion_contract_mode="shadow",
            completed_count=1,
            has_final_acceptance_receipt=False,
            final_milestone_label="M5",
        )
        assert result.action == "none"

    def test_no_successors_chain_complete_is_none(self) -> None:
        """Without successor declarations, chain_complete returns 'none'."""
        policy = AdvancementPolicy("auto", "auto", True, "chain_yaml")
        result = assess_advancement(
            policy,
            current_state="done",
            chain_complete=True,
            successors=[],
        )
        assert result.action == "none"

    def test_successor_no_acceptance_required_opens_gate(self) -> None:
        """When require_accepted_transaction=False, gate is open even in enforce."""
        policy = AdvancementPolicy("auto", "auto", True, "chain_yaml")
        successors = [_make_successor(require_accepted_transaction=False)]
        result = assess_advancement(
            policy,
            current_state="done",
            chain_complete=True,
            successors=successors,
            completion_contract_mode="enforce",
            completed_count=1,
            has_final_acceptance_receipt=False,
            final_milestone_label="M5",
        )
        # Gate returns None (no acceptance requirement) → falls through
        assert result.action == "none"

    def test_m5_m5a_m6_full_chain_progression(self) -> None:
        """Full M5→M5A→M6 progression through assess_advancement.

        M5 done → blocked without receipt → open with receipt.
        M5A done → blocked without receipt → open with receipt (M6 successor).
        """
        policy = AdvancementPolicy("auto", "auto", True, "chain_yaml")

        # M5 done, no receipt
        r1 = assess_advancement(
            policy,
            current_state="done",
            chain_complete=True,
            successors=[_make_successor(label="M5A", chain_spec_path="suites/m5a/chain.yaml")],
            completion_contract_mode="enforce",
            completed_count=1,
            has_final_acceptance_receipt=False,
            final_milestone_label="M5",
        )
        assert r1.action == "successor_gate_closed"

        # M5 done, with receipt
        r2 = assess_advancement(
            policy,
            current_state="done",
            chain_complete=True,
            successors=[_make_successor(label="M5A", chain_spec_path="suites/m5a/chain.yaml")],
            completion_contract_mode="enforce",
            completed_count=1,
            has_final_acceptance_receipt=True,
            final_milestone_label="M5",
        )
        assert r2.action == "successor_ready"

        # M5A done, no receipt
        r3 = assess_advancement(
            policy,
            current_state="done",
            chain_complete=True,
            successors=[_make_successor(label="M6", chain_spec_path="suites/m6/chain.yaml")],
            completion_contract_mode="enforce",
            completed_count=2,
            has_final_acceptance_receipt=False,
            final_milestone_label="M5A",
        )
        assert r3.action == "successor_gate_closed"

        # M5A done, with receipt
        r4 = assess_advancement(
            policy,
            current_state="done",
            chain_complete=True,
            successors=[_make_successor(label="M6", chain_spec_path="suites/m6/chain.yaml")],
            completion_contract_mode="enforce",
            completed_count=2,
            has_final_acceptance_receipt=True,
            final_milestone_label="M5A",
        )
        assert r4.action == "successor_ready"


class TestCheckSuccessorGateUnit:
    """Direct unit tests of check_successor_gate (the pure function)."""

    def test_no_successors_returns_none(self) -> None:
        policy = AdvancementPolicy("auto", "auto", True, "chain_yaml")
        assert check_successor_gate(policy, successors=[]) is None

    def test_shadow_mode_returns_none(self) -> None:
        policy = AdvancementPolicy("auto", "auto", True, "chain_yaml")
        result = check_successor_gate(
            policy,
            successors=[_make_successor()],
            completion_contract_mode="shadow",
            completed_count=1,
            has_final_acceptance_receipt=False,
        )
        assert result is None

    def test_warn_mode_returns_none(self) -> None:
        policy = AdvancementPolicy("auto", "auto", True, "chain_yaml")
        result = check_successor_gate(
            policy,
            successors=[_make_successor()],
            completion_contract_mode="warn",
            completed_count=1,
            has_final_acceptance_receipt=False,
        )
        assert result is None

    def test_enforce_no_completed_blocks(self) -> None:
        policy = AdvancementPolicy("auto", "auto", True, "chain_yaml")
        result = check_successor_gate(
            policy,
            successors=[_make_successor()],
            completion_contract_mode="enforce",
            completed_count=0,
            has_final_acceptance_receipt=False,
        )
        assert result is not None
        assert result.action == "successor_gate_closed"
        assert "no completed milestones" in result.reason

    def test_enforce_no_receipt_blocks(self) -> None:
        policy = AdvancementPolicy("auto", "auto", True, "chain_yaml")
        result = check_successor_gate(
            policy,
            successors=[_make_successor()],
            completion_contract_mode="enforce",
            completed_count=2,
            has_final_acceptance_receipt=False,
            final_milestone_label="M5A",
        )
        assert result is not None
        assert result.action == "successor_gate_closed"
        assert "M5A" in result.reason

    def test_enforce_with_receipt_opens(self) -> None:
        policy = AdvancementPolicy("auto", "auto", True, "chain_yaml")
        result = check_successor_gate(
            policy,
            successors=[_make_successor()],
            completion_contract_mode="enforce",
            completed_count=2,
            has_final_acceptance_receipt=True,
            final_milestone_label="M5A",
        )
        assert result is not None
        assert result.action == "successor_ready"
        assert result.automatic is True

    def test_atomic_mode_blocks_without_receipt(self) -> None:
        """'atomic' normalizes to 'enforce' for behavioral gates."""
        policy = AdvancementPolicy("auto", "auto", True, "chain_yaml")
        result = check_successor_gate(
            policy,
            successors=[_make_successor()],
            completion_contract_mode="atomic",
            completed_count=2,
            has_final_acceptance_receipt=False,
            final_milestone_label="M5A",
        )
        assert result.action == "successor_gate_closed"

    def test_acceptance_not_required_opens_gate(self) -> None:
        """require_accepted_transaction=False skips the gate entirely."""
        policy = AdvancementPolicy("auto", "auto", True, "chain_yaml")
        result = check_successor_gate(
            policy,
            successors=[_make_successor(require_accepted_transaction=False)],
            completion_contract_mode="enforce",
            completed_count=0,
            has_final_acceptance_receipt=False,
        )
        assert result is None

    def test_mixed_successors_one_requires_acceptance(self) -> None:
        """If ANY successor requires acceptance, the gate applies."""
        policy = AdvancementPolicy("auto", "auto", True, "chain_yaml")
        successors = [
            _make_successor(label="M6", require_accepted_transaction=False),
            _make_successor(label="M7", require_accepted_transaction=True),
        ]
        result = check_successor_gate(
            policy,
            successors=successors,
            completion_contract_mode="enforce",
            completed_count=2,
            has_final_acceptance_receipt=False,
            final_milestone_label="M5A",
        )
        assert result.action == "successor_gate_closed"

    def test_final_milestone_label_in_reason(self) -> None:
        """When no receipt, the reason includes the final milestone label."""
        policy = AdvancementPolicy("auto", "auto", True, "chain_yaml")
        result = check_successor_gate(
            policy,
            successors=[_make_successor()],
            completion_contract_mode="enforce",
            completed_count=2,
            has_final_acceptance_receipt=False,
            final_milestone_label="M5A",
        )
        assert "M5A" in result.reason

    def test_no_final_label_still_blocks(self) -> None:
        """Even without final_milestone_label, gate still blocks."""
        policy = AdvancementPolicy("auto", "auto", True, "chain_yaml")
        result = check_successor_gate(
            policy,
            successors=[_make_successor()],
            completion_contract_mode="enforce",
            completed_count=2,
            has_final_acceptance_receipt=False,
            final_milestone_label=None,
        )
        assert result.action == "successor_gate_closed"
        # No label in reason hint
        assert "None" not in result.reason
