"""Tests for the S2 front-half boundary contract registry.

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
)

from arnold_pipelines.megaplan.workflows.boundary_contracts import (
    BOUNDARY_CONTRACTS,
    BOUNDARY_CONTRACTS_BY_ID,
    critique_to_gate,
    gate_to_revise,
    plan_to_critique,
    prep_to_plan,
    revise_to_critique,
)

# ── Registry completeness ──────────────────────────────────────────────────


def test_registry_defines_exactly_five_contracts() -> None:
    """The registry must contain exactly the five S2 front-half contracts."""
    assert len(BOUNDARY_CONTRACTS) == 5


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
    """Only gate_to_revise must have authority_required=True."""
    for contract in BOUNDARY_CONTRACTS:
        if contract.boundary_id == "gate_to_revise":
            assert contract.authority_required is True, (
                "gate_to_revise must require authority"
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
