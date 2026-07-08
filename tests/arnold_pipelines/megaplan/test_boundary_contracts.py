"""Tests for the S2/S3/S4/S5 boundary contract registry.

Covers immutability, completeness, row-ID correctness, phase assignment,
and the absence of routing targets/predicates in boundary contracts.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from arnold.workflow.boundary_evidence import BoundaryContract, BoundaryPhase
from arnold.workflow.semantic_evidence import (
    S2_CRITIQUE_ROW_ID,
    S2_GATE_ROW_ID,
    S2_PLAN_ROW_ID,
    S2_PREP_ROW_ID,
    S2_REVISE_ROW_ID,
    S3_PARENT_REJOIN_ROW_ID,
    S3_REPLAN_AUTHORITY_ROW_ID,
    S3_TIEBREAKER_CHALLENGER_ROW_ID,
    S3_TIEBREAKER_DECISION_ROW_ID,
    S3_TIEBREAKER_RESEARCHER_ROW_ID,
    S3_TIEBREAKER_SYNTHESIS_ROW_ID,
)

from arnold_pipelines.megaplan.workflows.boundary_contracts import (
    BOUNDARY_CONTRACTS,
    BOUNDARY_CONTRACTS_BY_ID,
    challenger_to_synthesis,
    critique_to_gate,
    decision_to_parent,
    execute_aggregate_promotion,
    execute_approval,
    execute_approval_denial,
    execute_batch_checkpoint,
    execute_blocked_anchor,
    execute_no_review_terminal,
    execute_partial_failure,
    execute_resume_anchor,
    final_projection,
    finalize_artifacts,
    finalize_fallback,
    gate_to_revise,
    parent_rejoin_promotion,
    plan_to_critique,
    prep_to_plan,
    replan_authority,
    review_cap_authority,
    review_child_outputs,
    review_human_verification,
    review_reducer_promotion,
    review_rework_effects,
    researcher_to_challenger,
    revise_to_critique,
    synthesis_to_decision,
)

# ── Registry completeness ──────────────────────────────────────────────────


def test_registry_defines_exactly_twenty_seven_contracts() -> None:
    """The registry must contain exactly the twenty-seven S2+S3+S4+S5 contracts."""
    assert len(BOUNDARY_CONTRACTS) == 27


def test_registry_by_id_has_no_duplicates() -> None:
    """BOUNDARY_CONTRACTS_BY_ID must have the same count as BOUNDARY_CONTRACTS."""
    assert len(BOUNDARY_CONTRACTS_BY_ID) == len(BOUNDARY_CONTRACTS)


def test_registry_by_id_maps_all_contracts() -> None:
    """Every contract in BOUNDARY_CONTRACTS must appear in BOUNDARY_CONTRACTS_BY_ID."""
    for contract in BOUNDARY_CONTRACTS:
        assert BOUNDARY_CONTRACTS_BY_ID[contract.boundary_id] is contract


def test_named_contracts_are_in_registry() -> None:
    """Each named contract variable must be present in BOUNDARY_CONTRACTS."""
    named_ids = {
        prep_to_plan.boundary_id,
        plan_to_critique.boundary_id,
        critique_to_gate.boundary_id,
        gate_to_revise.boundary_id,
        revise_to_critique.boundary_id,
        researcher_to_challenger.boundary_id,
        challenger_to_synthesis.boundary_id,
        synthesis_to_decision.boundary_id,
        decision_to_parent.boundary_id,
        replan_authority.boundary_id,
        parent_rejoin_promotion.boundary_id,
        execute_approval.boundary_id,
        execute_approval_denial.boundary_id,
        execute_batch_checkpoint.boundary_id,
        execute_partial_failure.boundary_id,
        execute_blocked_anchor.boundary_id,
        execute_resume_anchor.boundary_id,
        execute_aggregate_promotion.boundary_id,
        execute_no_review_terminal.boundary_id,
        review_child_outputs.boundary_id,
        review_reducer_promotion.boundary_id,
        review_rework_effects.boundary_id,
        review_cap_authority.boundary_id,
        review_human_verification.boundary_id,
        finalize_artifacts.boundary_id,
        finalize_fallback.boundary_id,
        final_projection.boundary_id,
    }
    registry_ids = {c.boundary_id for c in BOUNDARY_CONTRACTS}
    assert named_ids == registry_ids


def test_all_registry_entries_are_boundary_contracts() -> None:
    """Every entry in BOUNDARY_CONTRACTS must be a BoundaryContract instance."""
    for contract in BOUNDARY_CONTRACTS:
        assert isinstance(contract, BoundaryContract)


# ── Boundary ID uniqueness ─────────────────────────────────────────────────


def test_boundary_ids_are_unique() -> None:
    """No two contracts may share the same boundary_id."""
    ids = [c.boundary_id for c in BOUNDARY_CONTRACTS]
    assert len(ids) == len(set(ids))


def test_boundary_ids_match_expected() -> None:
    """Each contract must have the expected boundary_id."""
    assert prep_to_plan.boundary_id == "prep_to_plan"
    assert plan_to_critique.boundary_id == "plan_to_critique"
    assert critique_to_gate.boundary_id == "critique_to_gate"
    assert gate_to_revise.boundary_id == "gate_to_revise"
    assert revise_to_critique.boundary_id == "revise_to_critique"
    assert researcher_to_challenger.boundary_id == "tiebreaker_researcher_to_challenger"
    assert challenger_to_synthesis.boundary_id == "tiebreaker_challenger_to_synthesis"
    assert synthesis_to_decision.boundary_id == "tiebreaker_synthesis_to_decision"
    assert decision_to_parent.boundary_id == "tiebreaker_decision_to_parent"
    assert replan_authority.boundary_id == "replan_authority"
    assert parent_rejoin_promotion.boundary_id == "parent_rejoin_promotion"
    assert review_child_outputs.boundary_id == "review_child_outputs"
    assert review_reducer_promotion.boundary_id == "review_reducer_promotion"
    assert review_rework_effects.boundary_id == "review_rework_effects"
    assert review_cap_authority.boundary_id == "review_cap_authority"
    assert review_human_verification.boundary_id == "review_human_verification"
    assert finalize_artifacts.boundary_id == "finalize_artifacts"
    assert finalize_fallback.boundary_id == "finalize_fallback"
    assert final_projection.boundary_id == "final_projection"


# ── Row ID correctness ─────────────────────────────────────────────────────


def test_prep_to_plan_has_correct_row_id() -> None:
    """prep_to_plan must reference S2_PREP_ROW_ID."""
    assert prep_to_plan.row_id == S2_PREP_ROW_ID
    assert prep_to_plan.row_id == "s2.prep.1"


def test_plan_to_critique_has_correct_row_id() -> None:
    """plan_to_critique must reference S2_PLAN_ROW_ID."""
    assert plan_to_critique.row_id == S2_PLAN_ROW_ID
    assert plan_to_critique.row_id == "s2.plan.1"


def test_critique_to_gate_has_correct_row_id() -> None:
    """critique_to_gate must reference S2_CRITIQUE_ROW_ID."""
    assert critique_to_gate.row_id == S2_CRITIQUE_ROW_ID
    assert critique_to_gate.row_id == "s2.critique.1"


def test_gate_to_revise_has_correct_row_id() -> None:
    """gate_to_revise must reference S2_GATE_ROW_ID."""
    assert gate_to_revise.row_id == S2_GATE_ROW_ID
    assert gate_to_revise.row_id == "s2.gate.1"


def test_revise_to_critique_has_correct_row_id() -> None:
    """revise_to_critique must reference S2_REVISE_ROW_ID."""
    assert revise_to_critique.row_id == S2_REVISE_ROW_ID
    assert revise_to_critique.row_id == "s2.revise.1"


def test_researcher_to_challenger_has_correct_row_id() -> None:
    """researcher_to_challenger must reference S3_TIEBREAKER_RESEARCHER_ROW_ID."""
    assert researcher_to_challenger.row_id == S3_TIEBREAKER_RESEARCHER_ROW_ID
    assert researcher_to_challenger.row_id == "s3.tiebreaker_researcher.1"


def test_challenger_to_synthesis_has_correct_row_id() -> None:
    """challenger_to_synthesis must reference S3_TIEBREAKER_CHALLENGER_ROW_ID."""
    assert challenger_to_synthesis.row_id == S3_TIEBREAKER_CHALLENGER_ROW_ID
    assert challenger_to_synthesis.row_id == "s3.tiebreaker_challenger.1"


def test_synthesis_to_decision_has_correct_row_id() -> None:
    """synthesis_to_decision must reference S3_TIEBREAKER_SYNTHESIS_ROW_ID."""
    assert synthesis_to_decision.row_id == S3_TIEBREAKER_SYNTHESIS_ROW_ID
    assert synthesis_to_decision.row_id == "s3.tiebreaker_synthesis.1"


def test_decision_to_parent_has_correct_row_id() -> None:
    """decision_to_parent must reference S3_TIEBREAKER_DECISION_ROW_ID."""
    assert decision_to_parent.row_id == S3_TIEBREAKER_DECISION_ROW_ID
    assert decision_to_parent.row_id == "s3.tiebreaker_decision.1"


def test_replan_authority_has_correct_row_id() -> None:
    """replan_authority must reference S3_REPLAN_AUTHORITY_ROW_ID."""
    assert replan_authority.row_id == S3_REPLAN_AUTHORITY_ROW_ID
    assert replan_authority.row_id == "s3.replan_authority.1"


def test_parent_rejoin_promotion_has_correct_row_id() -> None:
    """parent_rejoin_promotion must reference S3_PARENT_REJOIN_ROW_ID."""
    assert parent_rejoin_promotion.row_id == S3_PARENT_REJOIN_ROW_ID
    assert parent_rejoin_promotion.row_id == "s3.parent_rejoin.1"


# ── Phase correctness ──────────────────────────────────────────────────────


def test_prep_to_plan_has_correct_phase() -> None:
    """prep_to_plan must carry BoundaryPhase.PREP."""
    assert prep_to_plan.phase is BoundaryPhase.PREP


def test_plan_to_critique_has_correct_phase() -> None:
    """plan_to_critique must carry BoundaryPhase.PLAN."""
    assert plan_to_critique.phase is BoundaryPhase.PLAN


def test_critique_to_gate_has_correct_phase() -> None:
    """critique_to_gate must carry BoundaryPhase.CRITIQUE."""
    assert critique_to_gate.phase is BoundaryPhase.CRITIQUE


def test_gate_to_revise_has_correct_phase() -> None:
    """gate_to_revise must carry BoundaryPhase.GATE."""
    assert gate_to_revise.phase is BoundaryPhase.GATE


def test_revise_to_critique_has_correct_phase() -> None:
    """revise_to_critique must carry BoundaryPhase.REVISE."""
    assert revise_to_critique.phase is BoundaryPhase.REVISE


def test_researcher_to_challenger_has_correct_phase() -> None:
    """researcher_to_challenger must carry BoundaryPhase.TIEBREAKER_RESEARCHER."""
    assert researcher_to_challenger.phase is BoundaryPhase.TIEBREAKER_RESEARCHER


def test_challenger_to_synthesis_has_correct_phase() -> None:
    """challenger_to_synthesis must carry BoundaryPhase.TIEBREAKER_CHALLENGER."""
    assert challenger_to_synthesis.phase is BoundaryPhase.TIEBREAKER_CHALLENGER


def test_synthesis_to_decision_has_correct_phase() -> None:
    """synthesis_to_decision must carry BoundaryPhase.TIEBREAKER_SYNTHESIS."""
    assert synthesis_to_decision.phase is BoundaryPhase.TIEBREAKER_SYNTHESIS


def test_decision_to_parent_has_correct_phase() -> None:
    """decision_to_parent must carry BoundaryPhase.TIEBREAKER_DECISION."""
    assert decision_to_parent.phase is BoundaryPhase.TIEBREAKER_DECISION


def test_replan_authority_has_correct_phase() -> None:
    """replan_authority must carry BoundaryPhase.REPLAN_AUTHORITY."""
    assert replan_authority.phase is BoundaryPhase.REPLAN_AUTHORITY


def test_parent_rejoin_promotion_has_correct_phase() -> None:
    """parent_rejoin_promotion must carry BoundaryPhase.PARENT_REJOIN."""
    assert parent_rejoin_promotion.phase is BoundaryPhase.PARENT_REJOIN


# ── Immutability ───────────────────────────────────────────────────────────


def test_prep_to_plan_is_frozen() -> None:
    """prep_to_plan must be immutable."""
    with pytest.raises(FrozenInstanceError):
        prep_to_plan.boundary_id = "changed"  # type: ignore[misc]


def test_plan_to_critique_is_frozen() -> None:
    """plan_to_critique must be immutable."""
    with pytest.raises(FrozenInstanceError):
        plan_to_critique.boundary_id = "changed"  # type: ignore[misc]


def test_critique_to_gate_is_frozen() -> None:
    """critique_to_gate must be immutable."""
    with pytest.raises(FrozenInstanceError):
        critique_to_gate.boundary_id = "changed"  # type: ignore[misc]


def test_gate_to_revise_is_frozen() -> None:
    """gate_to_revise must be immutable."""
    with pytest.raises(FrozenInstanceError):
        gate_to_revise.boundary_id = "changed"  # type: ignore[misc]


def test_revise_to_critique_is_frozen() -> None:
    """revise_to_critique must be immutable."""
    with pytest.raises(FrozenInstanceError):
        revise_to_critique.boundary_id = "changed"  # type: ignore[misc]


def test_researcher_to_challenger_is_frozen() -> None:
    """researcher_to_challenger must be immutable."""
    with pytest.raises(FrozenInstanceError):
        researcher_to_challenger.boundary_id = "changed"  # type: ignore[misc]


def test_challenger_to_synthesis_is_frozen() -> None:
    """challenger_to_synthesis must be immutable."""
    with pytest.raises(FrozenInstanceError):
        challenger_to_synthesis.boundary_id = "changed"  # type: ignore[misc]


def test_synthesis_to_decision_is_frozen() -> None:
    """synthesis_to_decision must be immutable."""
    with pytest.raises(FrozenInstanceError):
        synthesis_to_decision.boundary_id = "changed"  # type: ignore[misc]


def test_decision_to_parent_is_frozen() -> None:
    """decision_to_parent must be immutable."""
    with pytest.raises(FrozenInstanceError):
        decision_to_parent.boundary_id = "changed"  # type: ignore[misc]


def test_replan_authority_is_frozen() -> None:
    """replan_authority must be immutable."""
    with pytest.raises(FrozenInstanceError):
        replan_authority.boundary_id = "changed"  # type: ignore[misc]


def test_parent_rejoin_promotion_is_frozen() -> None:
    """parent_rejoin_promotion must be immutable."""
    with pytest.raises(FrozenInstanceError):
        parent_rejoin_promotion.boundary_id = "changed"  # type: ignore[misc]


def test_registry_tuple_is_immutable() -> None:
    """BOUNDARY_CONTRACTS must be a tuple (immutable sequence)."""
    assert isinstance(BOUNDARY_CONTRACTS, tuple)
    with pytest.raises(TypeError):
        BOUNDARY_CONTRACTS[0] = prep_to_plan  # type: ignore[index]


# ── No routing targets or predicates ───────────────────────────────────────


def test_contracts_do_not_declare_route_targets() -> None:
    """Boundary contracts must not contain 'route_target' or 'next_step' in details."""
    for contract in BOUNDARY_CONTRACTS:
        details = dict(contract.details)
        assert "route_target" not in details, (
            f"{contract.boundary_id} must not declare route_target"
        )
        assert "next_step" not in details, (
            f"{contract.boundary_id} must not declare next_step"
        )
        assert "routing_predicate" not in details, (
            f"{contract.boundary_id} must not declare routing_predicate"
        )


def test_contracts_do_not_declare_route_target_fields() -> None:
    """No BoundaryContract field suggests route authority."""
    # BoundaryContract has no route-related fields by construction;
    # this test ensures no route-like data leaks into the payload.
    for contract in BOUNDARY_CONTRACTS:
        payload = contract.to_dict()
        for key in ("route_target", "next_step", "routing_predicate", "route"):
            assert key not in payload, (
                f"{contract.boundary_id}.to_dict() must not contain '{key}'"
            )


# ── Workflow ID consistency ────────────────────────────────────────────────


def test_all_contracts_have_same_workflow_id() -> None:
    """All contracts must share the same workflow_id ('megaplan-review')."""
    for contract in BOUNDARY_CONTRACTS:
        assert contract.workflow_id == "megaplan-review", (
            f"{contract.boundary_id} has unexpected workflow_id {contract.workflow_id}"
        )


# ── gate_to_revise authority requirement ───────────────────────────────────


def test_gate_to_revise_requires_authority() -> None:
    """Only explicit authority boundaries may set authority_required=True."""
    authority_boundaries = {
        "gate_to_revise",
        "replan_authority",
        "execute_approval",
        "review_cap_authority",
    }
    for contract in BOUNDARY_CONTRACTS:
        if contract.boundary_id in authority_boundaries:
            assert contract.authority_required is True, (
                f"{contract.boundary_id} must require authority"
            )
        else:
            assert contract.authority_required is False, (
                f"{contract.boundary_id} must NOT require authority"
            )


# ── Contract version consistency ───────────────────────────────────────────


def test_all_contracts_have_boundary_contract_version() -> None:
    """All contracts must declare the expected contract version."""
    for contract in BOUNDARY_CONTRACTS:
        assert contract.contract_version == "arnold.workflow.boundary_contract.v1"


# ── to_dict round-trip for each named contract ─────────────────────────────


def test_prep_to_plan_to_dict() -> None:
    """prep_to_plan.to_dict() must produce expected fields."""
    payload = prep_to_plan.to_dict()
    assert payload["boundary_id"] == "prep_to_plan"
    assert payload["row_id"] == "s2.prep.1"
    assert payload["phase"] == "prep"
    assert payload["phase_result_required"] is True
    assert payload["receipt_required"] is True
    assert payload["authority_required"] is False


def test_plan_to_critique_to_dict() -> None:
    """plan_to_critique.to_dict() must produce expected fields."""
    payload = plan_to_critique.to_dict()
    assert payload["boundary_id"] == "plan_to_critique"
    assert payload["row_id"] == "s2.plan.1"
    assert payload["phase"] == "plan"


def test_critique_to_gate_to_dict() -> None:
    """critique_to_gate.to_dict() must produce expected fields."""
    payload = critique_to_gate.to_dict()
    assert payload["boundary_id"] == "critique_to_gate"
    assert payload["row_id"] == "s2.critique.1"
    assert payload["phase"] == "critique"


def test_gate_to_revise_to_dict() -> None:
    """gate_to_revise.to_dict() must produce expected fields."""
    payload = gate_to_revise.to_dict()
    assert payload["boundary_id"] == "gate_to_revise"
    assert payload["row_id"] == "s2.gate.1"
    assert payload["phase"] == "gate"
    assert payload["authority_required"] is True


def test_revise_to_critique_to_dict() -> None:
    """revise_to_critique.to_dict() must produce expected fields."""
    payload = revise_to_critique.to_dict()
    assert payload["boundary_id"] == "revise_to_critique"
    assert payload["row_id"] == "s2.revise.1"
    assert payload["phase"] == "revise"


def test_researcher_to_challenger_to_dict() -> None:
    """researcher_to_challenger.to_dict() must produce expected fields."""
    payload = researcher_to_challenger.to_dict()
    assert payload["boundary_id"] == "tiebreaker_researcher_to_challenger"
    assert payload["row_id"] == "s3.tiebreaker_researcher.1"
    assert payload["phase"] == "tiebreaker_researcher"


def test_challenger_to_synthesis_to_dict() -> None:
    """challenger_to_synthesis.to_dict() must produce expected fields."""
    payload = challenger_to_synthesis.to_dict()
    assert payload["boundary_id"] == "tiebreaker_challenger_to_synthesis"
    assert payload["row_id"] == "s3.tiebreaker_challenger.1"
    assert payload["phase"] == "tiebreaker_challenger"


def test_synthesis_to_decision_to_dict() -> None:
    """synthesis_to_decision.to_dict() must produce expected fields."""
    payload = synthesis_to_decision.to_dict()
    assert payload["boundary_id"] == "tiebreaker_synthesis_to_decision"
    assert payload["row_id"] == "s3.tiebreaker_synthesis.1"
    assert payload["phase"] == "tiebreaker_synthesis"


def test_decision_to_parent_to_dict() -> None:
    """decision_to_parent.to_dict() must produce expected fields."""
    payload = decision_to_parent.to_dict()
    assert payload["boundary_id"] == "tiebreaker_decision_to_parent"
    assert payload["row_id"] == "s3.tiebreaker_decision.1"
    assert payload["phase"] == "tiebreaker_decision"


def test_replan_authority_to_dict() -> None:
    """replan_authority.to_dict() must produce expected fields."""
    payload = replan_authority.to_dict()
    assert payload["boundary_id"] == "replan_authority"
    assert payload["row_id"] == "s3.replan_authority.1"
    assert payload["phase"] == "replan_authority"
    assert payload["authority_required"] is True
    assert payload["receipt_required"] is False


def test_parent_rejoin_promotion_to_dict() -> None:
    """parent_rejoin_promotion.to_dict() must produce expected fields."""
    payload = parent_rejoin_promotion.to_dict()
    assert payload["boundary_id"] == "parent_rejoin_promotion"
    assert payload["row_id"] == "s3.parent_rejoin.1"
    assert payload["phase"] == "parent_rejoin"
    assert payload["receipt_required"] is True
    assert payload["phase_result_required"] is False


# ── S3 child output boundary contracts ───────────────────────────────────


def test_researcher_to_challenger_is_child_output_boundary() -> None:
    """researcher→challenger must be a child output boundary with trace path."""
    assert researcher_to_challenger.receipt_required is True
    assert researcher_to_challenger.phase_result_required is True
    assert researcher_to_challenger.details.get("child_trace_path") == "tiebreaker/researcher"


def test_challenger_to_synthesis_is_child_output_boundary() -> None:
    """challenger→synthesis must be a child output boundary with trace path."""
    assert challenger_to_synthesis.receipt_required is True
    assert challenger_to_synthesis.phase_result_required is True
    assert challenger_to_synthesis.details.get("child_trace_path") == "tiebreaker/challenger"


def test_synthesis_to_decision_is_reducer_promotion_boundary() -> None:
    """synthesis→decision must mark reducer_promotion in details."""
    assert synthesis_to_decision.receipt_required is True
    assert synthesis_to_decision.phase_result_required is True
    assert synthesis_to_decision.details.get("child_trace_path") == "tiebreaker/synthesis"
    assert synthesis_to_decision.details.get("reducer_promotion") is True


def test_decision_to_parent_is_parent_rejoin_boundary() -> None:
    """decision→parent must mark parent_rejoin_promotion in details."""
    assert decision_to_parent.receipt_required is True
    assert decision_to_parent.phase_result_required is True
    assert decision_to_parent.details.get("child_trace_path") == "tiebreaker/decision"
    assert decision_to_parent.details.get("parent_rejoin_promotion") is True
    assert decision_to_parent.details.get("decision_outcomes") == ("proceed", "iterate", "escalate")


def test_replan_authority_requires_authority_and_not_receipt() -> None:
    """replan_authority must require authority but not a receipt."""
    assert replan_authority.authority_required is True
    assert replan_authority.receipt_required is False
    assert replan_authority.phase_result_required is True


def test_parent_rejoin_promotion_requires_receipt_not_phase_result() -> None:
    """parent_rejoin must require receipt but not phase_result."""
    assert parent_rejoin_promotion.receipt_required is True
    assert parent_rejoin_promotion.phase_result_required is False
    assert parent_rejoin_promotion.authority_required is False


# ── S5 review/finalize boundary contracts ─────────────────────────────────


def test_s5_contracts_have_stable_row_ids() -> None:
    """S5 contracts must expose stable row IDs for durable receipt evidence."""
    assert review_child_outputs.row_id == "s5.review_child_outputs.1"
    assert review_reducer_promotion.row_id == "s5.review_reducer_promotion.1"
    assert review_rework_effects.row_id == "s5.review_rework_effects.1"
    assert review_cap_authority.row_id == "s5.review_cap_authority.1"
    assert review_human_verification.row_id == "s5.review_human_verification.1"
    assert finalize_artifacts.row_id == "s5.finalize_artifacts.1"
    assert finalize_fallback.row_id == "s5.finalize_fallback.1"
    assert final_projection.row_id == "s5.final_projection.1"


def test_s5_contract_payloads_remain_evidence_only() -> None:
    """S5 contract payloads may reference policy surfaces but must not own routing."""
    s5_contracts = (
        review_child_outputs,
        review_reducer_promotion,
        review_rework_effects,
        review_cap_authority,
        review_human_verification,
        finalize_artifacts,
        finalize_fallback,
        final_projection,
    )
    for contract in s5_contracts:
        payload = contract.to_dict()
        assert payload["receipt_required"] is True
        for key in ("route_target", "next_step", "routing_predicate", "route"):
            assert key not in payload
            assert key not in payload.get("details", {})


def test_review_child_outputs_and_reducer_promotion_capture_durable_effects() -> None:
    """Review fanout/fan-in evidence must require receipts without adding route control."""
    assert review_child_outputs.required_artifacts == ("review.json",)
    assert review_child_outputs.phase_result_required is True
    assert review_child_outputs.receipt_required is True
    assert review_child_outputs.authority_required is False
    assert review_child_outputs.details["child_trace_template"] == "review/{item_id}"
    assert review_child_outputs.details["fan_in_ref"] == "review-fan-in"
    assert (
        review_child_outputs.details["evidence_surface_ref"]
        == "REVIEW_POLICY.metadata.route_surface.fan_in_contract"
    )

    assert review_reducer_promotion.required_artifacts == ("review.json",)
    assert review_reducer_promotion.phase_result_required is True
    assert review_reducer_promotion.receipt_required is True
    assert review_reducer_promotion.details["reducer_promotion"] is True
    assert review_reducer_promotion.details["effect_id"] == "artifact.review.output"
    assert (
        review_reducer_promotion.details["artifact_policy_ref"]
        == "megaplan:artifact-contract"
    )
    assert review_reducer_promotion.details["reducer_ref"] == "SOURCE_REVIEW"


def test_review_rework_and_cap_contracts_capture_projection_and_authority() -> None:
    """Rework projection stays declarative while cap exhaustion carries receipts and authority."""
    assert review_rework_effects.required_artifacts == ("review.json",)
    assert review_rework_effects.phase_result_required is True
    assert review_rework_effects.receipt_required is True
    assert review_rework_effects.authority_required is False
    assert review_rework_effects.details["effect_kind"] == "review_rework_cycle"
    assert review_rework_effects.details["fresh_execute_session"] is True
    assert (
        review_rework_effects.details["evidence_surface_ref"]
        == "REVIEW_POLICY.metadata.route_surface.rework_cycle"
    )
    assert review_rework_effects.details["projection_state_ref"] == "finalized"

    assert review_cap_authority.required_artifacts == ("review.json",)
    assert review_cap_authority.phase_result_required is True
    assert review_cap_authority.receipt_required is True
    assert review_cap_authority.authority_required is True
    assert review_cap_authority.details["authority_scope"] == "review.cap_exhausted"
    assert review_cap_authority.details["authority_outcomes"] == (
        "blocked",
        "force_proceeded",
    )
    assert review_cap_authority.details["policy_ref"] == "megaplan:review"


def test_review_human_verification_and_finalize_contracts_capture_projection() -> None:
    """Human verification, finalize artifacts, fallback, and final projection stay evidence-only."""
    assert review_human_verification.required_artifacts == ("review.json",)
    assert review_human_verification.phase_result_required is True
    assert review_human_verification.receipt_required is True
    assert review_human_verification.authority_required is False
    assert review_human_verification.details["suspension_route_id"] == "review:human"
    assert review_human_verification.details["resume_policy_ref"] == "megaplan:suspension"
    assert review_human_verification.details["resume_cursor_ref"] == "cursor:suspension"
    assert review_human_verification.details["terminal_state"] == "awaiting_human_verify"

    assert finalize_artifacts.required_artifacts == (
        "contract.json",
        "final.md",
        "finalize.json",
    )
    assert finalize_artifacts.phase_result_required is True
    assert finalize_artifacts.receipt_required is True
    assert finalize_artifacts.details["effect_id"] == "artifact.finalize.plan"
    assert (
        finalize_artifacts.details["artifact_policy_ref"]
        == "megaplan:artifact-contract"
    )
    assert finalize_artifacts.details["artifact_refs"] == (
        "contract.json",
        "final.md",
        "finalize.json",
    )

    assert finalize_fallback.required_artifacts == ("finalize_revise_feedback.json",)
    assert finalize_fallback.phase_result_required is False
    assert finalize_fallback.receipt_required is True
    assert finalize_fallback.authority_required is False
    assert (
        finalize_fallback.details["evidence_surface_ref"]
        == "FINALIZE_POLICY.metadata.route_surface.fallback_routes."
        "plan_contract_revise_needed"
    )
    assert finalize_fallback.details["projection_ref"] == "finalize:revise"

    assert final_projection.required_artifacts == ("finalize.json",)
    assert final_projection.phase_result_required is False
    assert final_projection.receipt_required is True
    assert final_projection.authority_required is False
    assert final_projection.details["projection_cases"] == (
        "execute",
        "revise_fallback",
        "no_review_done",
        "no_review_deferred_human",
    )
    assert final_projection.details["projected_status_ref"] == "status:terminal"
    assert (
        final_projection.details["evidence_surface_ref"]
        == "FINALIZE_POLICY.metadata.route_surface.final_projection_routes"
    )
