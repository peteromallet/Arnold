"""Tests for the S2/S3/S4/S5 boundary contract registry.

Covers immutability, completeness, row-ID correctness, phase assignment,
and the absence of routing targets/predicates in boundary contracts.
"""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from arnold.workflow.boundary_evidence import (
    BoundaryContract,
    BoundaryPhase,
    TemplateCompatibility,
    TemplateCompatibilityResult,
    check_template_compatibility,
)
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
    OVERRIDE_AUTHORITY_CONTRACTS,
    REQUIRED_FIELD_PROFILES,
    REQUIRED_FIELD_PROFILES_BY_KIND,
    TYPED_BOUNDARY_TEMPLATES,
    TYPED_BOUNDARY_TEMPLATES_BY_ID,
    ApprovalBoundary,
    ArtifactHandoffBoundary,
    RevisionBoundary,
    ValidationBoundary,
    artifact_promotion_template,
    auditor_6h_completion,
    auditor_completion_template,
    chain_complete,
    chain_milestone_completion,
    chain_milestone_start,
    chain_milestone_template,
    challenger_to_synthesis,
    cloud_custody_blocked_relaunch_failure,
    cloud_custody_complete,
    cloud_custody_escalated_repeated_unchanged,
    cloud_custody_managed_running,
    cloud_custody_template,
    cloud_custody_unmanaged_running_warning,
    cloud_repair_dispatch,
    contract_satisfies_profile,
    critique_to_gate,
    decision_to_parent,
    diff_contracts,
    execute_aggregate_promotion,
    execute_approval,
    execute_approval_denial,
    execute_batch_checkpoint,
    execute_blocked_anchor,
    execute_no_review_terminal,
    execute_partial_failure,
    execute_resume_anchor,
    execution_custody_template,
    external_effect_template,
    external_witness_template,
    final_projection,
    finalize_artifacts,
    finalize_fallback,
    gate_to_revise,
    get_contract_by_id,
    get_profile_by_kind,
    get_template_by_id,
    graph_join_fanout_template,
    human_approval_waiver_template,
    lifecycle_transition_template,
    list_profile_kinds,
    list_template_ids,
    meta_repair_completion,
    ordinary_repair_completion,
    override_abort_authority,
    override_adopt_execution_authority,
    override_force_proceed_authority,
    override_human_gate_authority,
    override_recover_blocked_authority,
    override_replan_authority,
    override_resume_clarify_authority,
    override_suspension_authority,
    parent_rejoin_promotion,
    plan_to_critique,
    pr_merged,
    pr_ready,
    pr_transition_template,
    prep_to_plan,
    reducer_template,
    repair_verdict_template,
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

ROOT = Path(__file__).resolve().parents[3]
BOUNDARY_FIXTURE_ROOT = (
    ROOT / "docs" / "arnold" / "megaplan-native-representation-boundary-fixtures"
)


def _load_generated_fixture_json(boundary_id: str, filename: str) -> dict[str, object]:
    payload = json.loads(
        (BOUNDARY_FIXTURE_ROOT / boundary_id / filename).read_text(encoding="utf-8")
    )
    assert isinstance(payload, dict)
    return payload


# ── Registry completeness ──────────────────────────────────────────────────


def test_registry_defines_exactly_forty_nine_contracts() -> None:
    """The registry must contain the 35 legacy + S6 contracts plus 14 new chain/PR/repair/auditor/custody contracts."""
    assert len(BOUNDARY_CONTRACTS) == 49


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
        override_abort_authority.boundary_id,
        override_force_proceed_authority.boundary_id,
        override_replan_authority.boundary_id,
        override_recover_blocked_authority.boundary_id,
        override_resume_clarify_authority.boundary_id,
        override_adopt_execution_authority.boundary_id,
        override_suspension_authority.boundary_id,
        override_human_gate_authority.boundary_id,
        chain_milestone_start.boundary_id,
        chain_milestone_completion.boundary_id,
        chain_complete.boundary_id,
        pr_ready.boundary_id,
        pr_merged.boundary_id,
        cloud_repair_dispatch.boundary_id,
        ordinary_repair_completion.boundary_id,
        meta_repair_completion.boundary_id,
        auditor_6h_completion.boundary_id,
        cloud_custody_managed_running.boundary_id,
        cloud_custody_complete.boundary_id,
        cloud_custody_unmanaged_running_warning.boundary_id,
        cloud_custody_blocked_relaunch_failure.boundary_id,
        cloud_custody_escalated_repeated_unchanged.boundary_id,
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
    assert override_abort_authority.boundary_id == "override_abort_authority"
    assert (
        override_force_proceed_authority.boundary_id
        == "override_force_proceed_authority"
    )
    assert override_replan_authority.boundary_id == "override_replan_authority"
    assert (
        override_recover_blocked_authority.boundary_id
        == "override_recover_blocked_authority"
    )
    assert (
        override_resume_clarify_authority.boundary_id
        == "override_resume_clarify_authority"
    )
    assert (
        override_adopt_execution_authority.boundary_id
        == "override_adopt_execution_authority"
    )
    assert (
        override_suspension_authority.boundary_id
        == "override_suspension_authority"
    )
    assert override_human_gate_authority.boundary_id == "override_human_gate_authority"
    assert chain_milestone_start.boundary_id == "chain_milestone_start"
    assert chain_milestone_completion.boundary_id == "chain_milestone_completion"
    assert chain_complete.boundary_id == "chain_complete"
    assert pr_ready.boundary_id == "pr_ready"
    assert pr_merged.boundary_id == "pr_merged"
    assert cloud_repair_dispatch.boundary_id == "cloud_repair_dispatch"
    assert ordinary_repair_completion.boundary_id == "ordinary_repair_completion"
    assert meta_repair_completion.boundary_id == "meta_repair_completion"
    assert auditor_6h_completion.boundary_id == "auditor_6h_completion"
    assert cloud_custody_managed_running.boundary_id == "cloud_custody_managed_running"
    assert cloud_custody_complete.boundary_id == "cloud_custody_complete"
    assert (
        cloud_custody_unmanaged_running_warning.boundary_id
        == "cloud_custody_unmanaged_running_warning"
    )
    assert (
        cloud_custody_blocked_relaunch_failure.boundary_id
        == "cloud_custody_blocked_relaunch_failure"
    )
    assert (
        cloud_custody_escalated_repeated_unchanged.boundary_id
        == "cloud_custody_escalated_repeated_unchanged"
    )


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


# ── New contract row IDs (chain, PR, repair, auditor, custody) ───────────


def test_chain_milestone_start_has_correct_row_id() -> None:
    """chain_milestone_start must reference chain.milestone.start.1."""
    assert chain_milestone_start.row_id == "chain.milestone.start.1"


def test_chain_milestone_completion_has_correct_row_id() -> None:
    """chain_milestone_completion must reference chain.milestone.complete.1."""
    assert chain_milestone_completion.row_id == "chain.milestone.complete.1"


def test_chain_complete_has_correct_row_id() -> None:
    """chain_complete must reference chain.complete.1."""
    assert chain_complete.row_id == "chain.complete.1"


def test_pr_ready_has_correct_row_id() -> None:
    """pr_ready must reference pr.ready.1."""
    assert pr_ready.row_id == "pr.ready.1"


def test_pr_merged_has_correct_row_id() -> None:
    """pr_merged must reference pr.merged.1."""
    assert pr_merged.row_id == "pr.merged.1"


def test_cloud_repair_dispatch_has_correct_row_id() -> None:
    """cloud_repair_dispatch must reference repair.cloud_dispatch.1."""
    assert cloud_repair_dispatch.row_id == "repair.cloud_dispatch.1"


def test_ordinary_repair_completion_has_correct_row_id() -> None:
    """ordinary_repair_completion must reference repair.ordinary_complete.1."""
    assert ordinary_repair_completion.row_id == "repair.ordinary_complete.1"


def test_meta_repair_completion_has_correct_row_id() -> None:
    """meta_repair_completion must reference repair.meta_complete.1."""
    assert meta_repair_completion.row_id == "repair.meta_complete.1"


def test_auditor_6h_completion_has_correct_row_id() -> None:
    """auditor_6h_completion must reference auditor.6h_complete.1."""
    assert auditor_6h_completion.row_id == "auditor.6h_complete.1"


def test_cloud_custody_managed_running_has_correct_row_id() -> None:
    """cloud_custody_managed_running must reference custody.managed_running.1."""
    assert cloud_custody_managed_running.row_id == "custody.managed_running.1"


def test_cloud_custody_complete_has_correct_row_id() -> None:
    """cloud_custody_complete must reference custody.complete.1."""
    assert cloud_custody_complete.row_id == "custody.complete.1"


def test_cloud_custody_unmanaged_running_warning_has_correct_row_id() -> None:
    """cloud_custody_unmanaged_running_warning must reference custody.unmanaged_warning.1."""
    assert cloud_custody_unmanaged_running_warning.row_id == "custody.unmanaged_warning.1"


def test_cloud_custody_blocked_relaunch_failure_has_correct_row_id() -> None:
    """cloud_custody_blocked_relaunch_failure must reference custody.blocked_relaunch.1."""
    assert cloud_custody_blocked_relaunch_failure.row_id == "custody.blocked_relaunch.1"


def test_cloud_custody_escalated_repeated_unchanged_has_correct_row_id() -> None:
    """cloud_custody_escalated_repeated_unchanged must reference custody.escalated_unchanged.1."""
    assert cloud_custody_escalated_repeated_unchanged.row_id == "custody.escalated_unchanged.1"


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
        "chain_milestone_start",
        "chain_milestone_completion",
        "chain_complete",
        "pr_ready",
        "pr_merged",
        "cloud_repair_dispatch",
        "ordinary_repair_completion",
        "meta_repair_completion",
        "auditor_6h_completion",
        "cloud_custody_managed_running",
        "cloud_custody_complete",
        "cloud_custody_unmanaged_running_warning",
        "cloud_custody_blocked_relaunch_failure",
        "cloud_custody_escalated_repeated_unchanged",
        *(contract.boundary_id for contract in OVERRIDE_AUTHORITY_CONTRACTS),
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


def test_generated_boundary_fixtures_preserve_negative_case_surfaces() -> None:
    """Generated manifests/semantic-health payloads must expose the same
    receipt, phase, authority, reducer, and state surfaces that the contracts
    require for the negative semantic-health cases."""
    prep_manifest = _load_generated_fixture_json("prep_to_plan", "manifest.json")
    gate_manifest = _load_generated_fixture_json("gate_to_revise", "manifest.json")
    gate_health = _load_generated_fixture_json("gate_to_revise", "semantic_health.json")
    execute_manifest = _load_generated_fixture_json(
        "execute_aggregate_promotion",
        "manifest.json",
    )
    final_manifest = _load_generated_fixture_json("final_projection", "manifest.json")
    override_manifest = _load_generated_fixture_json(
        "override_abort_authority",
        "manifest.json",
    )

    assert prep_manifest["artifact_refs"] == list(prep_to_plan.required_artifacts)
    assert "receipt" in prep_manifest["capability_effects"]

    assert gate_manifest["artifact_refs"] == list(gate_to_revise.required_artifacts)
    assert gate_manifest["authority_records"]
    assert [finding["finding_id"] for finding in gate_health["scoped_findings"]] == [
        "SH-gate_to_revise-phase-result-stale-phase"
    ]
    assert [finding["diagnostic_code"] for finding in gate_health["scoped_findings"]] == [
        "AWF249_BOUNDARY_EVIDENCE_STALE"
    ]

    assert execute_manifest["artifact_refs"] == list(
        execute_aggregate_promotion.required_artifacts
    )
    assert execute_manifest["reducer_promotion"] is True
    assert "reducer" in execute_manifest["capability_effects"]

    assert final_manifest["artifact_refs"] == list(final_projection.required_artifacts)
    assert "state_history" in final_manifest["capability_effects"]
    assert "external_effect" in final_manifest["capability_effects"]

    assert override_manifest["authority_records"]
    assert "authority" in override_manifest["capability_effects"]
    assert override_manifest["artifact_refs"] == []


def test_s6_override_authority_contracts_capture_scope_and_evidence_contracts() -> None:
    """S6 override authority contracts must stay authority-only and specify durable evidence."""
    assert len(OVERRIDE_AUTHORITY_CONTRACTS) == 8

    expected = {
        "override_abort_authority": ("abort", "override.abort", ("state.json",)),
        "override_force_proceed_authority": (
            "force-proceed",
            "override.force_proceed",
            ("state.json",),
        ),
        "override_replan_authority": ("replan", "override.replan", ("state.json",)),
        "override_recover_blocked_authority": (
            "recover-blocked",
            "override.recover_blocked",
            ("state.json",),
        ),
        "override_resume_clarify_authority": (
            "resume-clarify",
            "override.resume_clarify",
            ("state.json",),
        ),
        "override_adopt_execution_authority": (
            "adopt-execution",
            "override.adopt_execution",
            ("state.json", "execution.json", "finalize.json"),
        ),
        "override_suspension_authority": (
            "suspension-waiver",
            "override.suspension_waiver",
            ("state.json", "human_verifications.json"),
        ),
        "override_human_gate_authority": (
            "human-gate",
            "override.human_gate",
            ("state.json", "approval_record.json"),
        ),
    }

    for contract in OVERRIDE_AUTHORITY_CONTRACTS:
        transition, scope, required_refs = expected[contract.boundary_id]
        assert contract.phase is None
        assert contract.required_artifacts == ()
        assert contract.receipt_required is False
        assert contract.authority_required is True
        assert contract.details["authority_transition"] == transition
        assert contract.details["authority_scope"] == scope
        assert contract.details["required_evidence_refs"] == required_refs
        assert contract.details["evidence_hashes_ref"] == (
            "authority_records[].details.evidence_hashes"
        )
        assert contract.details["freshness_token_ref"] == "state.meta.current_invocation_id"
        assert contract.details["actor_role_ref"] == "authority_records[].{actor,role}"


# ── Required-field profiles ────────────────────────────────────────────────


def test_required_field_profiles_count() -> None:
    """Exactly 17 required-field profiles must be registered."""
    assert len(REQUIRED_FIELD_PROFILES) == 17
    assert len(REQUIRED_FIELD_PROFILES_BY_KIND) == 17


def test_required_field_profiles_kinds() -> None:
    """All expected profile kinds must be present."""
    expected = frozenset({
        "artifact_promotion",
        "lifecycle_transition",
        "reducer",
        "external_effect",
        "execution_custody",
        "human_approval_waiver",
        "graph_join_fanout",
        "external_witness",
        "revision_boundary",
        "validation_boundary",
        "artifact_handoff_boundary",
        "approval_boundary",
        "chain_milestone",
        "pr_transition",
        "repair_verdict",
        "auditor_completion",
        "cloud_custody",
    })
    actual = frozenset(kind for kind, _fields in REQUIRED_FIELD_PROFILES)
    assert actual == expected


def test_required_field_profiles_non_empty() -> None:
    """Every registered profile must be a non-empty frozenset[str]."""
    for kind, fields in REQUIRED_FIELD_PROFILES:
        assert isinstance(fields, frozenset), (
            f"Profile {kind} must be a frozenset"
        )
        assert len(fields) > 0, f"Profile {kind} must not be empty"


def test_required_field_profiles_contain_boundary_id() -> None:
    """Every profile must require 'boundary_id'."""
    for kind, fields in REQUIRED_FIELD_PROFILES:
        assert "boundary_id" in fields, (
            f"Profile {kind} must require 'boundary_id'"
        )


def test_required_field_profiles_contain_workflow_id() -> None:
    """Every profile must require 'workflow_id'."""
    for kind, fields in REQUIRED_FIELD_PROFILES:
        assert "workflow_id" in fields, (
            f"Profile {kind} must require 'workflow_id'"
        )


def test_required_field_profiles_contain_row_id() -> None:
    """Every profile must require 'row_id'."""
    for kind, fields in REQUIRED_FIELD_PROFILES:
        assert "row_id" in fields, (
            f"Profile {kind} must require 'row_id'"
        )


def test_profile_by_kind_returns_profile() -> None:
    """get_profile_by_kind must return the matching frozenset for each registered kind."""
    for kind, fields in REQUIRED_FIELD_PROFILES:
        result = get_profile_by_kind(kind)
        assert result is fields, (
            f"get_profile_by_kind({kind!r}) must return the profile"
        )


def test_profile_by_kind_returns_none_for_unknown() -> None:
    """get_profile_by_kind must return None for unknown kind."""
    assert get_profile_by_kind("nonexistent_profile") is None


def test_profile_by_kind_matches_registry() -> None:
    """REQUIRED_FIELD_PROFILES_BY_KIND must match REQUIRED_FIELD_PROFILES."""
    assert set(REQUIRED_FIELD_PROFILES_BY_KIND.keys()) == {
        kind for kind, _fields in REQUIRED_FIELD_PROFILES
    }
    for kind, expected in REQUIRED_FIELD_PROFILES:
        assert REQUIRED_FIELD_PROFILES_BY_KIND[kind] == expected


# ── Typed boundary templates ───────────────────────────────────────────────


def test_typed_templates_count() -> None:
    """Exactly 17 typed templates must be registered."""
    assert len(TYPED_BOUNDARY_TEMPLATES) == 17
    assert len(TYPED_BOUNDARY_TEMPLATES_BY_ID) == 17


def test_all_templates_are_boundary_contracts() -> None:
    """Every entry in TYPED_BOUNDARY_TEMPLATES must be a BoundaryContract."""
    for template in TYPED_BOUNDARY_TEMPLATES:
        assert isinstance(template, BoundaryContract), (
            f"{template.boundary_id} must be a BoundaryContract"
        )


def test_template_ids_have_template_prefix() -> None:
    """All template boundary_ids must use the 'template.*' namespace."""
    for template in TYPED_BOUNDARY_TEMPLATES:
        assert template.boundary_id.startswith("template."), (
            f"{template.boundary_id} must start with 'template.'"
        )


def test_template_ids_match_expected() -> None:
    """Each template must have the expected boundary_id."""
    expected = {
        "template.artifact_promotion": artifact_promotion_template,
        "template.lifecycle_transition": lifecycle_transition_template,
        "template.reducer": reducer_template,
        "template.external_effect": external_effect_template,
        "template.execution_custody": execution_custody_template,
        "template.human_approval_waiver": human_approval_waiver_template,
        "template.graph_join_fanout": graph_join_fanout_template,
        "template.external_witness": external_witness_template,
        "template.revision_boundary": RevisionBoundary,
        "template.validation_boundary": ValidationBoundary,
        "template.artifact_handoff_boundary": ArtifactHandoffBoundary,
        "template.approval_boundary": ApprovalBoundary,
        "template.chain_milestone": chain_milestone_template,
        "template.pr_transition": pr_transition_template,
        "template.repair_verdict": repair_verdict_template,
        "template.auditor_completion": auditor_completion_template,
        "template.cloud_custody": cloud_custody_template,
    }
    for bid, template in expected.items():
        assert template.boundary_id == bid
        assert TYPED_BOUNDARY_TEMPLATES_BY_ID[bid] is template


def test_templates_by_id_no_duplicates() -> None:
    """TYPED_BOUNDARY_TEMPLATES_BY_ID must have no duplicate keys."""
    assert len(TYPED_BOUNDARY_TEMPLATES_BY_ID) == len(TYPED_BOUNDARY_TEMPLATES)


def test_templates_are_frozen() -> None:
    """Every template must be immutable."""
    for template in TYPED_BOUNDARY_TEMPLATES:
        with pytest.raises(FrozenInstanceError):
            template.boundary_id = "mutated"  # type: ignore[misc]


def test_templates_share_workflow_id() -> None:
    """All templates must share the same workflow_id."""
    for template in TYPED_BOUNDARY_TEMPLATES:
        assert template.workflow_id == "megaplan-review"


def test_templates_have_contract_version() -> None:
    """All templates must declare the expected contract version."""
    for template in TYPED_BOUNDARY_TEMPLATES:
        assert template.contract_version == "arnold.workflow.boundary_contract.v1"


def test_templates_have_phase_none() -> None:
    """Templates do not carry a phase by default (boundary_id conveys intent)."""
    for template in TYPED_BOUNDARY_TEMPLATES:
        assert template.phase is None, (
            f"{template.boundary_id} phase must be None"
        )


def test_templates_have_description_in_details() -> None:
    """Every template must include a non-empty description in its details."""
    for template in TYPED_BOUNDARY_TEMPLATES:
        desc = template.details.get("description")
        assert desc is not None, f"{template.boundary_id} missing description"
        assert isinstance(desc, str) and len(desc) > 0, (
            f"{template.boundary_id} description must be a non-empty string"
        )


def test_approval_boundary_pascal_case() -> None:
    """ApprovalBoundary must be the PascalCase alias for template.approval_boundary."""
    assert ApprovalBoundary is TYPED_BOUNDARY_TEMPLATES_BY_ID["template.approval_boundary"]
    assert ApprovalBoundary.boundary_id == "template.approval_boundary"
    assert ApprovalBoundary.authority_required is True


def test_artifact_handoff_boundary_pascal_case() -> None:
    """ArtifactHandoffBoundary must be the PascalCase alias."""
    assert ArtifactHandoffBoundary is TYPED_BOUNDARY_TEMPLATES_BY_ID["template.artifact_handoff_boundary"]
    assert ArtifactHandoffBoundary.boundary_id == "template.artifact_handoff_boundary"
    assert "handoff_from" in ArtifactHandoffBoundary.details


def test_revision_boundary_pascal_case() -> None:
    """RevisionBoundary must be the PascalCase alias."""
    assert RevisionBoundary is TYPED_BOUNDARY_TEMPLATES_BY_ID["template.revision_boundary"]
    assert RevisionBoundary.boundary_id == "template.revision_boundary"
    assert "revised_content.json" in RevisionBoundary.required_artifacts


def test_validation_boundary_pascal_case() -> None:
    """ValidationBoundary must be the PascalCase alias."""
    assert ValidationBoundary is TYPED_BOUNDARY_TEMPLATES_BY_ID["template.validation_boundary"]
    assert ValidationBoundary.boundary_id == "template.validation_boundary"
    assert "validation_result.json" in ValidationBoundary.required_artifacts


# ── Lookup helpers ──────────────────────────────────────────────────────────


def test_get_contract_by_id_returns_contract() -> None:
    """get_contract_by_id must return the correct contract for a valid id."""
    result = get_contract_by_id("prep_to_plan")
    assert result is prep_to_plan
    assert result.boundary_id == "prep_to_plan"


def test_get_contract_by_id_returns_none_for_unknown() -> None:
    """get_contract_by_id must return None for unknown id."""
    assert get_contract_by_id("nonexistent_contract_id") is None


def test_get_contract_by_id_consistent_with_dict() -> None:
    """get_contract_by_id must match BOUNDARY_CONTRACTS_BY_ID for all ids."""
    for cid in BOUNDARY_CONTRACTS_BY_ID:
        assert get_contract_by_id(cid) is BOUNDARY_CONTRACTS_BY_ID[cid]


def test_get_template_by_id_returns_template() -> None:
    """get_template_by_id must return the correct template for a valid id."""
    result = get_template_by_id("template.artifact_promotion")
    assert result is artifact_promotion_template


def test_get_template_by_id_returns_none_for_unknown() -> None:
    """get_template_by_id must return None for unknown id."""
    assert get_template_by_id("template.nonexistent") is None


def test_get_template_by_id_returns_none_for_contract_id() -> None:
    """get_template_by_id must return None when given a contract id (not a template id)."""
    assert get_template_by_id("prep_to_plan") is None


def test_get_profile_by_kind_known() -> None:
    """get_profile_by_kind must return frozenset for known kinds."""
    profile = get_profile_by_kind("artifact_promotion")
    assert isinstance(profile, frozenset)
    assert "boundary_id" in profile
    assert "details.effect_id" in profile


def test_list_template_ids_returns_all() -> None:
    """list_template_ids must return all 17 template ids."""
    ids = list_template_ids()
    assert isinstance(ids, tuple)
    assert len(ids) == 17
    assert set(ids) == set(TYPED_BOUNDARY_TEMPLATES_BY_ID.keys())


def test_list_profile_kinds_returns_all() -> None:
    """list_profile_kinds must return all 17 profile kinds."""
    kinds = list_profile_kinds()
    assert isinstance(kinds, tuple)
    assert len(kinds) == 17
    assert set(kinds) == set(REQUIRED_FIELD_PROFILES_BY_KIND.keys())


# ── Structural diff helpers ─────────────────────────────────────────────────


def test_diff_contracts_identical() -> None:
    """diff_contracts must report matching=True for identical contracts."""
    result = diff_contracts(prep_to_plan, prep_to_plan)
    assert result["matching"] is True
    assert result["field_diffs"] == {}
    assert result["detail_diffs"] == {}


def test_diff_contracts_different_contracts() -> None:
    """diff_contracts must detect differences between distinct contracts."""
    result = diff_contracts(prep_to_plan, gate_to_revise)
    assert result["matching"] is False
    assert "boundary_id" in result["field_diffs"]
    assert result["field_diffs"]["boundary_id"] == ("prep_to_plan", "gate_to_revise")


def test_diff_contracts_detail_diffs() -> None:
    """diff_contracts must detect detail-level differences."""
    # prep_to_plan and plan_to_critique have different descriptions
    result = diff_contracts(prep_to_plan, plan_to_critique)
    assert result["matching"] is False
    assert "details.description" in result["detail_diffs"]


def test_diff_contracts_artifact_diffs() -> None:
    """diff_contracts must detect required_artifacts differences."""
    # prep_to_plan has artifacts; execute_no_review_terminal has none
    result = diff_contracts(prep_to_plan, execute_no_review_terminal)
    assert result["artifact_diffs"] is not None
    assert len(result["artifact_diffs"]["only_in_a"]) > 0


def test_diff_contracts_returns_all_keys() -> None:
    """diff_contracts result must always contain matching, field_diffs, detail_diffs."""
    result = diff_contracts(prep_to_plan, prep_to_plan)
    assert "matching" in result
    assert "field_diffs" in result
    assert "detail_diffs" in result


def test_diff_contracts_phase_diff() -> None:
    """diff_contracts must detect phase differences between contracts."""
    result = diff_contracts(prep_to_plan, plan_to_critique)
    assert "phase" in result["field_diffs"]
    assert result["field_diffs"]["phase"][0] != result["field_diffs"]["phase"][1]


def test_diff_contracts_authority_diff() -> None:
    """diff_contracts must detect authority_required differences."""
    result = diff_contracts(prep_to_plan, gate_to_revise)
    assert "authority_required" in result["field_diffs"]
    assert result["field_diffs"]["authority_required"] == (False, True)


# ── contract_satisfies_profile ──────────────────────────────────────────────


def test_contract_satisfies_profile_all_satisfied() -> None:
    """prep_to_plan satisfies the lifecycle_transition profile."""
    profile = REQUIRED_FIELD_PROFILES_BY_KIND["lifecycle_transition"]
    satisfied, missing = contract_satisfies_profile(prep_to_plan, profile)
    assert satisfied is True
    assert missing == ()


def test_contract_satisfies_profile_missing_keys() -> None:
    """prep_to_plan does not satisfy artifact_promotion profile (missing details keys)."""
    profile = REQUIRED_FIELD_PROFILES_BY_KIND["artifact_promotion"]
    satisfied, missing = contract_satisfies_profile(prep_to_plan, profile)
    assert satisfied is False
    assert len(missing) > 0
    assert "details.effect_id" in missing


def test_contract_satisfies_profile_missing_phase() -> None:
    """A template without phase fails a profile that requires phase."""
    profile = REQUIRED_FIELD_PROFILES_BY_KIND["lifecycle_transition"]
    satisfied, missing = contract_satisfies_profile(artifact_promotion_template, profile)
    # artifact_promotion_template has phase=None, lifecycle requires phase
    assert satisfied is False
    assert "phase" in missing


def test_contract_satisfies_profile_empty_profile() -> None:
    """Every contract satisfies an empty profile."""
    satisfied, missing = contract_satisfies_profile(prep_to_plan, frozenset())
    assert satisfied is True
    assert missing == ()


def test_contract_satisfies_profile_with_custom_profile() -> None:
    """A minimal custom profile must pass for a fully-populated contract."""
    minimal = frozenset({"boundary_id", "workflow_id", "row_id"})
    satisfied, missing = contract_satisfies_profile(prep_to_plan, minimal)
    assert satisfied is True
    assert missing == ()


def test_contract_satisfies_profile_missing_unknown_attr() -> None:
    """A profile key that is not an attribute of BoundaryContract is treated as missing."""
    bogus_profile = frozenset({"nonexistent_field"})
    satisfied, missing = contract_satisfies_profile(prep_to_plan, bogus_profile)
    assert satisfied is False
    assert "nonexistent_field" in missing


def test_contract_satisfies_profile_satisfies_approval_boundary_template() -> None:
    """ApprovalBoundary template must satisfy the approval_boundary profile."""
    profile = REQUIRED_FIELD_PROFILES_BY_KIND["approval_boundary"]
    satisfied, missing = contract_satisfies_profile(ApprovalBoundary, profile)
    assert satisfied is True, f"Missing: {missing}"


def test_contract_satisfies_profile_satisfies_artifact_promotion_template() -> None:
    """artifact_promotion_template has required_artifacts=() which is empty;
    the artifact_promotion profile requires non-empty required_artifacts,
    so this correctly fails."""
    profile = REQUIRED_FIELD_PROFILES_BY_KIND["artifact_promotion"]
    satisfied, missing = contract_satisfies_profile(artifact_promotion_template, profile)
    assert satisfied is False
    assert "required_artifacts" in missing


# ── Breaking required-field change vs non-breaking optional extension ───────


def test_check_template_compatibility_breaking_added_required_field() -> None:
    """Adding a field to ``to_required_fields`` that was neither previously
    required nor optional is a breaking change — existing producers cannot
    satisfy a required field they never knew about."""
    base_required = frozenset({"boundary_id", "workflow_id", "row_id"})
    base_optional = frozenset({"details.description"})

    # New version adds "details.effect_id" as a required field that was
    # neither required nor optional before → breaking
    new_required = frozenset({"boundary_id", "workflow_id", "row_id", "details.effect_id"})
    new_optional = frozenset({"details.description"})

    result = check_template_compatibility(
        template_id="test.breaking_new_required",
        from_required_fields=base_required,
        from_optional_fields=base_optional,
        to_required_fields=new_required,
        to_optional_fields=new_optional,
        from_version="1.0",
        to_version="2.0",
    )
    assert result.compatibility is TemplateCompatibility.BREAKING_CHANGE
    assert "details.effect_id" in result.changed_required_fields
    assert result.template_id == "test.breaking_new_required"


def test_check_template_compatibility_breaking_optional_to_required() -> None:
    """Moving an optional field to required is a breaking change."""
    base_required = frozenset({"boundary_id", "workflow_id", "row_id"})
    base_optional = frozenset({"details.description"})

    # New version makes details.description required → breaking
    new_required = frozenset({"boundary_id", "workflow_id", "row_id", "details.description"})
    new_optional: frozenset[str] = frozenset()

    result = check_template_compatibility(
        template_id="test.optional_to_required",
        from_required_fields=base_required,
        from_optional_fields=base_optional,
        to_required_fields=new_required,
        to_optional_fields=new_optional,
    )
    assert result.compatibility is TemplateCompatibility.BREAKING_CHANGE
    assert "details.description" in result.removed_required_fields


def test_check_template_compatibility_non_breaking_optional_extension() -> None:
    """Adding optional fields without changing required fields is a
    compatible extension (non-breaking)."""
    base_required = frozenset({"boundary_id", "workflow_id", "row_id", "phase"})
    base_optional = frozenset({"details.description"})

    # New version adds optional field "details.new_optional_field" → compatible
    new_required = base_required
    new_optional = base_optional | {"details.new_optional_field"}

    result = check_template_compatibility(
        template_id="test.optional_extension",
        from_required_fields=base_required,
        from_optional_fields=base_optional,
        to_required_fields=new_required,
        to_optional_fields=new_optional,
    )
    assert result.compatibility is TemplateCompatibility.COMPATIBLE_EXTENSION
    assert "details.new_optional_field" in result.added_optional_fields
    assert result.removed_required_fields == ()
    assert result.changed_required_fields == ()


def test_check_template_compatibility_exact_match() -> None:
    """Identical required and optional field sets produce EXACT_MATCH."""
    required = frozenset({"boundary_id", "workflow_id", "row_id"})
    optional = frozenset({"details.description"})

    result = check_template_compatibility(
        template_id="test.exact",
        from_required_fields=required,
        from_optional_fields=optional,
        to_required_fields=required,
        to_optional_fields=optional,
    )
    assert result.compatibility is TemplateCompatibility.EXACT_MATCH


def test_check_template_compatibility_with_real_profiles_breaking() -> None:
    """Using real profile data, demonstrate that a required-field profile
    that drops a mandatory field is a BREAKING_CHANGE."""
    # Base: artifact_promotion profile fields
    base_profile = REQUIRED_FIELD_PROFILES_BY_KIND["artifact_promotion"]
    # "Breaking" version: drop 'details.effect_id' from required
    breaking_profile = frozenset(
        f for f in base_profile
        if f != "details.effect_id"
    )

    result = check_template_compatibility(
        template_id="artifact_promotion",
        from_required_fields=base_profile,
        from_optional_fields=frozenset(),
        to_required_fields=breaking_profile,
        to_optional_fields=frozenset({"details.effect_id"}),
        from_version="1.0",
        to_version="2.0",
    )
    assert result.compatibility is TemplateCompatibility.BREAKING_CHANGE
    assert "details.effect_id" in result.removed_required_fields


def test_check_template_compatibility_with_real_profiles_non_breaking() -> None:
    """Using real profile data, adding optional fields without changing
    required fields is a COMPATIBLE_EXTENSION."""
    base_profile = REQUIRED_FIELD_PROFILES_BY_KIND["lifecycle_transition"]

    result = check_template_compatibility(
        template_id="lifecycle_transition",
        from_required_fields=base_profile,
        from_optional_fields=frozenset(),
        to_required_fields=base_profile,
        to_optional_fields=frozenset({"details.new_optional_note"}),
        from_version="1.0",
        to_version="1.1",
    )
    assert result.compatibility is TemplateCompatibility.COMPATIBLE_EXTENSION
    assert "details.new_optional_note" in result.added_optional_fields
    assert result.removed_required_fields == ()
