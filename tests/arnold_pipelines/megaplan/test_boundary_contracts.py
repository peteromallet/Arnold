"""Tests for the S2/S3 boundary contract registry.

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
    gate_to_revise,
    parent_rejoin_promotion,
    plan_to_critique,
    prep_to_plan,
    replan_authority,
    researcher_to_challenger,
    revise_to_critique,
    synthesis_to_decision,
)

# ── Registry completeness ──────────────────────────────────────────────────


def test_registry_defines_exactly_nineteen_contracts() -> None:
    """The registry must contain exactly the nineteen S2+S3+S4 contracts."""
    assert len(BOUNDARY_CONTRACTS) == 19


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
    """All five contracts must share the same workflow_id ('megaplan-review')."""
    for contract in BOUNDARY_CONTRACTS:
        assert contract.workflow_id == "megaplan-review", (
            f"{contract.boundary_id} has unexpected workflow_id {contract.workflow_id}"
        )


# ── gate_to_revise authority requirement ───────────────────────────────────


def test_gate_to_revise_requires_authority() -> None:
    """Only gate_to_revise, replan_authority, and execute_approval must have authority_required=True."""
    authority_boundaries = {"gate_to_revise", "replan_authority", "execute_approval"}
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
