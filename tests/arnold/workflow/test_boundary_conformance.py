"""Tests for generic in-memory boundary conformance verifier.

Covers :mod:`arnold.workflow.boundary_conformance` — the generic verifier
for graph-shaped workflows with boundary contracts, receipts, evidence,
durable effects, and template/profile metadata.

All tests use only :class:`BoundaryContract`, :class:`BoundaryReceipt`,
:class:`BoundaryEvidence`, :class:`BoundaryGraph`, and template/profile
primitives.  No Megap plan imports allowed.
"""

from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError
from types import MappingProxyType

import pytest

from arnold.workflow.boundary_evidence import (
    AuthorityRecord,
    BoundaryContract,
    BoundaryEvidence,
    BoundaryGraph,
    BoundaryOutcome,
    BoundaryPhase,
    BoundaryReceipt,
    SemanticFinding,
)
from arnold.workflow.boundary_templates import (
    BoundaryTemplateKind,
    check_contract_conformance,
    get_template,
)
from arnold.workflow.boundary_conformance import (
    ConformanceResult,
    ConformanceViolation,
    ConformanceViolationKind,
    WorkflowBoundarySpec,
    classify_and_verify_boundaries,
    verify_boundary_conformance,
    verify_semantic_findings_against_boundaries,
    verify_single_boundary,
)


# ── Shared fixture helpers ────────────────────────────────────────────────


def _make_contract(
    boundary_id: str = "b.test",
    workflow_id: str = "arnold.workflow",
    *,
    required_artifacts: tuple[str, ...] = ("artifact.json",),
    receipt_required: bool = True,
    authority_required: bool = False,
    phase_result_required: bool = True,
    row_id: str | None = None,
    phase: BoundaryPhase | None = None,
    details: dict | None = None,
) -> BoundaryContract:
    return BoundaryContract(
        boundary_id=boundary_id,
        workflow_id=workflow_id,
        row_id=row_id,
        phase=phase,
        required_artifacts=required_artifacts,
        expected_state_delta={"status": "done"},
        expected_history_entry=None,
        phase_result_required=phase_result_required,
        receipt_required=receipt_required,
        authority_required=authority_required,
        details=details or {},
    )


def _make_receipt(
    boundary_id: str = "b.test",
    workflow_id: str = "arnold.workflow",
    *,
    artifact_refs: tuple[str, ...] = ("artifact.json",),
    outcome: BoundaryOutcome | None = BoundaryOutcome.COMPLETE,
    authority_records: tuple[AuthorityRecord, ...] = (),
    phase_result_ref: str | None = "phase_result.json",
) -> BoundaryReceipt:
    return BoundaryReceipt(
        boundary_id=boundary_id,
        workflow_id=workflow_id,
        artifact_refs=artifact_refs,
        outcome=outcome,
        authority_records=authority_records,
        phase_result_ref=phase_result_ref,
    )


def _make_evidence(
    evidence_id: str = "ev.test",
    boundary_id: str = "b.test",
    workflow_id: str = "arnold.workflow",
    *,
    artifact_refs: tuple[str, ...] = ("artifact.json",),
) -> BoundaryEvidence:
    return BoundaryEvidence(
        evidence_id=evidence_id,
        boundary_id=boundary_id,
        workflow_id=workflow_id,
        artifact_refs=artifact_refs,
    )


def _make_graph_spec(
    graph_id: str = "g.test",
    boundary_id: str = "b.test",
    *,
    dependencies: tuple[str, ...] = (),
    fan_out_refs: tuple[str, ...] = (),
    fan_in_ref: str | None = None,
    joins: tuple[str, ...] = (),
) -> BoundaryGraph:
    return BoundaryGraph(
        graph_id=graph_id,
        boundary_id=boundary_id,
        dependencies=dependencies,
        fan_out_refs=fan_out_refs,
        fan_in_ref=fan_in_ref,
        joins=joins,
    )


def _make_spec(
    boundary_id: str = "b.test",
    *,
    contract: BoundaryContract | None = None,
    receipt: BoundaryReceipt | None = None,
    evidence: tuple[BoundaryEvidence, ...] = (),
    template_kind: BoundaryTemplateKind | str | None = None,
    dependencies: tuple[str, ...] = (),
    graph_spec: BoundaryGraph | None = None,
) -> WorkflowBoundarySpec:
    if contract is None:
        contract = _make_contract(boundary_id=boundary_id)
    return WorkflowBoundarySpec(
        boundary_id=boundary_id,
        contract=contract,
        receipt=receipt,
        evidence=evidence,
        template_kind=template_kind,
        dependencies=dependencies,
        graph_spec=graph_spec,
    )


# ── Importability and Megaplan-import compliance ──────────────────────────


def test_module_importable_with_all_public_symbols() -> None:
    """All public symbols must be importable from boundary_conformance."""
    from arnold.workflow.boundary_conformance import (
        ConformanceResult,
        ConformanceViolation,
        ConformanceViolationKind,
        WorkflowBoundarySpec,
        classify_and_verify_boundaries,
        verify_boundary_conformance,
        verify_semantic_findings_against_boundaries,
        verify_single_boundary,
    )
    assert ConformanceViolationKind.MISSING_REQUIRED_FIELD == "missing_required_field"
    assert ConformanceViolationKind.RECEIPT_REQUIRED_BUT_MISSING == "receipt_required_but_missing"
    assert ConformanceViolationKind.AUTHORITY_REQUIRED_BUT_MISSING == "authority_required_but_missing"
    assert ConformanceViolationKind.GRAPH_DANGLING_DEPENDENCY == "graph_dangling_dependency"
    assert ConformanceViolationKind.GRAPH_DANGLING_FAN_OUT == "graph_dangling_fan_out"


def test_no_megaplan_imports_in_module_source() -> None:
    """The boundary_conformance module must not import from arnold_pipelines.megaplan."""
    import arnold.workflow.boundary_conformance as mod

    source_path = mod.__file__
    assert source_path is not None
    with open(source_path) as fh:
        source = fh.read()
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            module_name = ""
            if isinstance(node, ast.ImportFrom) and node.module:
                module_name = node.module
            for alias in getattr(node, "names", []):
                full = f"{module_name}.{alias.name}" if module_name else alias.name
                assert "megaplan" not in full.lower(), (
                    f"Megaplan import found in boundary_conformance: {full}"
                )


# ── ConformanceViolationKind ──────────────────────────────────────────────


def test_violation_kind_is_str_enum() -> None:
    """ConformanceViolationKind is a StrEnum with all expected members."""
    members = list(ConformanceViolationKind)
    assert len(members) >= 14  # may grow
    for m in members:
        assert isinstance(m, ConformanceViolationKind)
        assert isinstance(m.value, str)
        assert m.value == str(m)


def test_violation_kind_covers_all_categories() -> None:
    """Every major verification category has at least one violation kind."""
    kinds = {k.value for k in ConformanceViolationKind}
    # Contract
    assert "missing_required_field" in kinds
    assert "template_profile_mismatch" in kinds
    # Receipt
    assert "receipt_required_but_missing" in kinds
    assert "receipt_workflow_mismatch" in kinds
    assert "receipt_artifact_mismatch" in kinds
    assert "receipt_outcome_unexpected" in kinds
    # Authority
    assert "authority_required_but_missing" in kinds
    # Evidence
    assert "evidence_missing_for_contract" in kinds
    assert "evidence_workflow_mismatch" in kinds
    # Durable effects
    assert "durable_effect_unverified" in kinds
    assert "phase_result_unverified" in kinds
    # Graph topology
    assert "graph_dangling_dependency" in kinds
    assert "graph_dangling_fan_out" in kinds
    assert "graph_dangling_fan_in" in kinds
    assert "graph_dangling_join" in kinds
    # Semantic findings
    assert "semantic_finding_unresolved" in kinds


# ── ConformanceViolation ──────────────────────────────────────────────────


def test_violation_construction_and_immutability() -> None:
    """ConformanceViolation is frozen with required fields."""
    v = ConformanceViolation(
        boundary_id="b.1",
        kind=ConformanceViolationKind.MISSING_REQUIRED_FIELD,
        description="Missing field X",
    )
    assert v.boundary_id == "b.1"
    assert v.kind == ConformanceViolationKind.MISSING_REQUIRED_FIELD
    assert v.description == "Missing field X"
    assert v.detail == {}

    with pytest.raises(FrozenInstanceError):
        v.boundary_id = "b.2"  # type: ignore[misc]


def test_violation_rejects_empty_boundary_id() -> None:
    """ConformanceViolation rejects empty boundary_id."""
    with pytest.raises(ValueError, match="boundary_id"):
        ConformanceViolation(
            boundary_id="",
            kind=ConformanceViolationKind.MISSING_REQUIRED_FIELD,
            description="x",
        )


def test_violation_rejects_empty_description() -> None:
    """ConformanceViolation rejects empty description."""
    with pytest.raises(ValueError, match="description"):
        ConformanceViolation(
            boundary_id="b.1",
            kind=ConformanceViolationKind.MISSING_REQUIRED_FIELD,
            description="",
        )


def test_violation_detail_is_frozen() -> None:
    """Violation detail mapping is frozen (MappingProxyType)."""
    v = ConformanceViolation(
        boundary_id="b.1",
        kind=ConformanceViolationKind.MISSING_REQUIRED_FIELD,
        description="Missing field X",
        detail={"missing": ["x", "y"]},
    )
    assert isinstance(v.detail, MappingProxyType)
    with pytest.raises(TypeError):
        v.detail["new"] = "value"  # type: ignore[index]


def test_violation_to_dict() -> None:
    """Violation to_dict produces primitives."""
    v = ConformanceViolation(
        boundary_id="b.1",
        kind=ConformanceViolationKind.MISSING_REQUIRED_FIELD,
        description="Missing field X",
        detail={"missing_fields": ["x"]},
    )
    d = v.to_dict()
    assert d["boundary_id"] == "b.1"
    assert d["kind"] == "missing_required_field"
    assert d["description"] == "Missing field X"
    assert d["detail"]["missing_fields"] == ["x"]


# ── ConformanceResult ─────────────────────────────────────────────────────


def test_result_conformant_with_zero_violations() -> None:
    """ConformanceResult.conformant is True when violations is empty."""
    r = ConformanceResult(workflow_id="w.test", boundary_count=3, receipt_count=2, evidence_count=1)
    assert r.conformant is True
    assert r.violation_count == 0
    assert len(r.violations) == 0


def test_result_not_conformant_with_violations() -> None:
    """ConformanceResult.conformant is False when violations exist."""
    v = ConformanceViolation(
        boundary_id="b.1",
        kind=ConformanceViolationKind.MISSING_REQUIRED_FIELD,
        description="x",
    )
    r = ConformanceResult(
        workflow_id="w.test",
        violations=(v,),
        boundary_count=3,
        receipt_count=2,
        evidence_count=1,
    )
    assert r.conformant is False
    assert r.violation_count == 1


def test_result_to_dict() -> None:
    """ConformanceResult to_dict produces primitives."""
    v = ConformanceViolation(
        boundary_id="b.1",
        kind=ConformanceViolationKind.MISSING_REQUIRED_FIELD,
        description="x",
    )
    r = ConformanceResult(
        workflow_id="w.test",
        violations=(v,),
        boundary_count=3,
        receipt_count=2,
        evidence_count=1,
    )
    d = r.to_dict()
    assert d["workflow_id"] == "w.test"
    assert d["conformant"] is False
    assert d["violation_count"] == 1
    assert d["boundary_count"] == 3
    assert d["receipt_count"] == 2
    assert d["evidence_count"] == 1
    assert len(d["violations"]) == 1


def test_result_immutable() -> None:
    """ConformanceResult is frozen."""
    r = ConformanceResult(workflow_id="w.test")
    with pytest.raises(FrozenInstanceError):
        r.workflow_id = "other"  # type: ignore[misc]


# ── WorkflowBoundarySpec ──────────────────────────────────────────────────


def test_spec_construction() -> None:
    """WorkflowBoundarySpec bundles contract, receipt, evidence, template info."""
    contract = _make_contract("b.1")
    receipt = _make_receipt("b.1")
    evidence = _make_evidence("ev.1", "b.1")
    spec = WorkflowBoundarySpec(
        boundary_id="b.1",
        contract=contract,
        receipt=receipt,
        evidence=(evidence,),
        template_kind="revision_boundary",
        dependencies=("b.2",),
    )
    assert spec.boundary_id == "b.1"
    assert spec.contract is contract
    assert spec.receipt is receipt
    assert len(spec.evidence) == 1
    assert spec.template_kind == BoundaryTemplateKind.REVISION_BOUNDARY
    assert spec.dependencies == ("b.2",)


def test_spec_rejects_empty_boundary_id() -> None:
    """WorkflowBoundarySpec rejects empty boundary_id."""
    with pytest.raises(ValueError, match="boundary_id"):
        WorkflowBoundarySpec(boundary_id="", contract=_make_contract("b.1"))


def test_spec_is_frozen() -> None:
    """WorkflowBoundarySpec is frozen."""
    spec = _make_spec("b.1")
    with pytest.raises(FrozenInstanceError):
        spec.boundary_id = "b.2"  # type: ignore[misc]


def test_spec_template_kind_coerced_to_enum() -> None:
    """String template_kind is coerced to BoundaryTemplateKind."""
    spec = WorkflowBoundarySpec(
        boundary_id="b.1",
        contract=_make_contract("b.1"),
        template_kind="external_effect",
    )
    assert isinstance(spec.template_kind, BoundaryTemplateKind)
    assert spec.template_kind == BoundaryTemplateKind.EXTERNAL_EFFECT


def test_spec_dependencies_are_tuples() -> None:
    """Dependencies are always tuples."""
    spec = _make_spec("b.1", dependencies=["a", "b"])  # type: ignore[arg-type]
    assert isinstance(spec.dependencies, tuple)
    assert spec.dependencies == ("a", "b")


# ── verify_boundary_conformance: basic ────────────────────────────────────


def test_empty_workflow_is_conformant() -> None:
    """Empty workflow has zero violations."""
    result = verify_boundary_conformance("w.empty", {})
    assert result.conformant is True
    assert result.boundary_count == 0
    assert result.violation_count == 0


def test_empty_workflow_id_raises() -> None:
    """Empty workflow_id raises ValueError."""
    with pytest.raises(ValueError, match="workflow_id"):
        verify_boundary_conformance("", {})


def test_single_conformant_boundary() -> None:
    """A fully satisfied boundary with receipt and evidence is conformant."""
    spec = _make_spec(
        "b.1",
        receipt=_make_receipt("b.1", artifact_refs=("artifact.json",)),
        evidence=(_make_evidence("ev.1", "b.1", artifact_refs=("artifact.json",)),),
    )
    result = verify_boundary_conformance("arnold.workflow", {"b.1": spec})
    assert result.conformant is True
    assert result.boundary_count == 1
    assert result.receipt_count == 1
    assert result.evidence_count == 1


def test_boundary_without_receipt_when_not_required() -> None:
    """Boundary with receipt_required=False and no receipt is conformant."""
    contract = _make_contract(
        "b.1",
        required_artifacts=(),
        receipt_required=False,
        phase_result_required=False,
    )
    spec = _make_spec("b.1", contract=contract, receipt=None)
    result = verify_boundary_conformance("arnold.workflow", {"b.1": spec})
    assert result.conformant is True


# ── verify_boundary_conformance: receipt violations ───────────────────────


def test_receipt_required_but_missing() -> None:
    """receipt_required=True + no receipt → RECEIPT_REQUIRED_BUT_MISSING."""
    contract = _make_contract("b.1", receipt_required=True)
    spec = _make_spec("b.1", contract=contract, receipt=None)
    result = verify_boundary_conformance("arnold.workflow", {"b.1": spec})
    assert result.conformant is False
    kinds = {v.kind for v in result.violations}
    assert ConformanceViolationKind.RECEIPT_REQUIRED_BUT_MISSING in kinds


def test_receipt_workflow_mismatch() -> None:
    """Receipt with wrong workflow_id → RECEIPT_WORKFLOW_MISMATCH."""
    receipt = _make_receipt("b.1", workflow_id="other.workflow")
    spec = _make_spec("b.1", receipt=receipt)
    result = verify_boundary_conformance("arnold.workflow", {"b.1": spec})
    assert result.conformant is False
    kinds = {v.kind for v in result.violations}
    assert ConformanceViolationKind.RECEIPT_WORKFLOW_MISMATCH in kinds


def test_receipt_boundary_mismatch() -> None:
    """Receipt with wrong boundary_id → RECEIPT_BOUNDARY_MISMATCH."""
    contract = _make_contract("b.1")
    receipt = _make_receipt("b.other")  # different from spec/contract
    spec = _make_spec("b.1", contract=contract, receipt=receipt)
    result = verify_boundary_conformance("arnold.workflow", {"b.1": spec})
    assert result.conformant is False
    kinds = {v.kind for v in result.violations}
    assert ConformanceViolationKind.RECEIPT_BOUNDARY_MISMATCH in kinds


def test_receipt_artifact_mismatch() -> None:
    """Receipt missing required artifacts → RECEIPT_ARTIFACT_MISMATCH."""
    contract = _make_contract("b.1", required_artifacts=("a.json", "b.json"))
    receipt = _make_receipt("b.1", artifact_refs=("a.json",))  # missing b.json
    spec = _make_spec("b.1", contract=contract, receipt=receipt)
    result = verify_boundary_conformance("arnold.workflow", {"b.1": spec})
    assert result.conformant is False
    kinds = {v.kind for v in result.violations}
    assert ConformanceViolationKind.RECEIPT_ARTIFACT_MISMATCH in kinds


def test_receipt_non_terminal_outcome() -> None:
    """Receipt with INCOMPLETE outcome → RECEIPT_OUTCOME_UNEXPECTED."""
    receipt = _make_receipt("b.1", outcome=BoundaryOutcome.INCOMPLETE)
    spec = _make_spec("b.1", receipt=receipt)
    result = verify_boundary_conformance("arnold.workflow", {"b.1": spec})
    assert result.conformant is False
    kinds = {v.kind for v in result.violations}
    assert ConformanceViolationKind.RECEIPT_OUTCOME_UNEXPECTED in kinds


def test_receipt_partial_outcome_is_non_terminal() -> None:
    """PARTIAL outcome also triggers RECEIPT_OUTCOME_UNEXPECTED."""
    receipt = _make_receipt("b.1", outcome=BoundaryOutcome.PARTIAL)
    spec = _make_spec("b.1", receipt=receipt)
    result = verify_boundary_conformance("arnold.workflow", {"b.1": spec})
    kinds = {v.kind for v in result.violations}
    assert ConformanceViolationKind.RECEIPT_OUTCOME_UNEXPECTED in kinds


def test_terminal_outcomes_do_not_trigger() -> None:
    """COMPLETE, SUCCEEDED, IRREVERSIBLE outcomes are acceptable."""
    for outcome in (BoundaryOutcome.COMPLETE, BoundaryOutcome.SUCCEEDED, BoundaryOutcome.IRREVERSIBLE):
        receipt = _make_receipt("b.1", outcome=outcome)
        spec = _make_spec("b.1", receipt=receipt)
        result = verify_boundary_conformance("arnold.workflow", {"b.1": spec})
        kinds = {v.kind for v in result.violations}
        assert ConformanceViolationKind.RECEIPT_OUTCOME_UNEXPECTED not in kinds, (
            f"Outcome {outcome} should not trigger RECEIPT_OUTCOME_UNEXPECTED"
        )


# ── verify_boundary_conformance: authority violations ─────────────────────


def test_authority_required_but_no_receipt() -> None:
    """authority_required=True + no receipt → AUTHORITY_REQUIRED_BUT_MISSING."""
    contract = _make_contract("b.1", authority_required=True)
    spec = _make_spec("b.1", contract=contract, receipt=None)
    result = verify_boundary_conformance("arnold.workflow", {"b.1": spec})
    assert result.conformant is False
    kinds = {v.kind for v in result.violations}
    assert ConformanceViolationKind.AUTHORITY_REQUIRED_BUT_MISSING in kinds


def test_authority_required_but_empty_records() -> None:
    """authority_required=True + receipt with no authority records → violation."""
    contract = _make_contract("b.1", authority_required=True)
    receipt = _make_receipt("b.1", authority_records=())
    spec = _make_spec("b.1", contract=contract, receipt=receipt)
    result = verify_boundary_conformance("arnold.workflow", {"b.1": spec})
    assert result.conformant is False
    kinds = {v.kind for v in result.violations}
    assert ConformanceViolationKind.AUTHORITY_REQUIRED_BUT_MISSING in kinds


def test_authority_satisfied_with_records() -> None:
    """authority_required=True + receipt with authority records → conformant."""
    contract = _make_contract("b.1", authority_required=True)
    receipt = _make_receipt(
        "b.1",
        authority_records=(
            AuthorityRecord(actor="alice", role="approver", decision="approved"),
        ),
    )
    spec = _make_spec("b.1", contract=contract, receipt=receipt)
    result = verify_boundary_conformance("arnold.workflow", {"b.1": spec})
    kinds = {v.kind for v in result.violations}
    assert ConformanceViolationKind.AUTHORITY_REQUIRED_BUT_MISSING not in kinds


# ── verify_boundary_conformance: evidence violations ──────────────────────


def test_evidence_missing_for_contract() -> None:
    """Contract with requirements, no receipt coverage, no evidence → EVIDENCE_MISSING_FOR_CONTRACT."""
    contract = _make_contract("b.1", required_artifacts=("a.json",))
    spec = _make_spec("b.1", contract=contract, receipt=None, evidence=())
    result = verify_boundary_conformance("arnold.workflow", {"b.1": spec})
    assert result.conformant is False
    kinds = {v.kind for v in result.violations}
    assert ConformanceViolationKind.EVIDENCE_MISSING_FOR_CONTRACT in kinds


def test_evidence_not_flagged_when_receipt_covers_all() -> None:
    """Evidence not flagged when receipt covers all required artifacts and phase/authority."""
    contract = _make_contract(
        "b.1",
        required_artifacts=("a.json",),
        receipt_required=True,
        authority_required=True,
        phase_result_required=True,
    )
    receipt = _make_receipt(
        "b.1",
        artifact_refs=("a.json",),
        phase_result_ref="result.json",
        authority_records=(
            AuthorityRecord(actor="alice", role="approver", decision="approved"),
        ),
    )
    spec = _make_spec("b.1", contract=contract, receipt=receipt, evidence=())
    result = verify_boundary_conformance("arnold.workflow", {"b.1": spec})
    kinds = {v.kind for v in result.violations}
    assert ConformanceViolationKind.EVIDENCE_MISSING_FOR_CONTRACT not in kinds


def test_evidence_workflow_mismatch() -> None:
    """Evidence with wrong workflow_id → EVIDENCE_WORKFLOW_MISMATCH."""
    ev = _make_evidence("ev.1", "b.1", workflow_id="other.wf")
    spec = _make_spec("b.1", evidence=(ev,), receipt=_make_receipt("b.1"))
    result = verify_boundary_conformance("arnold.workflow", {"b.1": spec})
    assert result.conformant is False
    kinds = {v.kind for v in result.violations}
    assert ConformanceViolationKind.EVIDENCE_WORKFLOW_MISMATCH in kinds


def test_evidence_boundary_mismatch() -> None:
    """Evidence with wrong boundary_id → EVIDENCE_BOUNDARY_MISMATCH."""
    ev = _make_evidence("ev.1", "b.other")
    spec = _make_spec("b.1", evidence=(ev,), receipt=_make_receipt("b.1"))
    result = verify_boundary_conformance("arnold.workflow", {"b.1": spec})
    assert result.conformant is False
    kinds = {v.kind for v in result.violations}
    assert ConformanceViolationKind.EVIDENCE_BOUNDARY_MISMATCH in kinds


# ── verify_boundary_conformance: durable effect violations ────────────────


def test_durable_effect_unverified() -> None:
    """Contract requires artifacts not in receipt or evidence."""
    contract = _make_contract("b.1", required_artifacts=("a.json", "b.json"))
    receipt = _make_receipt("b.1", artifact_refs=("a.json",))
    spec = _make_spec("b.1", contract=contract, receipt=receipt, evidence=())
    result = verify_boundary_conformance("arnold.workflow", {"b.1": spec})
    assert result.conformant is False
    kinds = {v.kind for v in result.violations}
    assert ConformanceViolationKind.DURABLE_EFFECT_UNVERIFIED in kinds


def test_durable_effect_covered_by_evidence() -> None:
    """Artifacts covered by evidence (not receipt) are still verified."""
    contract = _make_contract("b.1", required_artifacts=("a.json", "b.json"))
    receipt = _make_receipt("b.1", artifact_refs=("a.json",))
    ev = _make_evidence("ev.1", "b.1", artifact_refs=("b.json",))
    spec = _make_spec("b.1", contract=contract, receipt=receipt, evidence=(ev,))
    result = verify_boundary_conformance("arnold.workflow", {"b.1": spec})
    kinds = {v.kind for v in result.violations}
    assert ConformanceViolationKind.DURABLE_EFFECT_UNVERIFIED not in kinds


def test_durable_effect_declaration_without_effect() -> None:
    """Contract with receipt/authority but no artifacts or state delta."""
    contract = _make_contract(
        "b.1",
        required_artifacts=(),
        receipt_required=True,
        authority_required=True,
        phase_result_required=False,
    )
    contract = BoundaryContract(
        boundary_id=contract.boundary_id,
        workflow_id=contract.workflow_id,
        required_artifacts=(),
        expected_state_delta={},
        receipt_required=True,
        authority_required=True,
        phase_result_required=False,
    )
    spec = _make_spec("b.1", contract=contract, receipt=_make_receipt("b.1"))
    result = verify_boundary_conformance("arnold.workflow", {"b.1": spec})
    assert result.conformant is False
    kinds = {v.kind for v in result.violations}
    assert ConformanceViolationKind.DURABLE_EFFECT_UNVERIFIED in kinds


# ── verify_boundary_conformance: phase result violations ──────────────────


def test_phase_result_unverified_no_receipt() -> None:
    """phase_result_required=True + no receipt → PHASE_RESULT_UNVERIFIED."""
    contract = _make_contract("b.1", phase_result_required=True)
    spec = _make_spec("b.1", contract=contract, receipt=None)
    result = verify_boundary_conformance("arnold.workflow", {"b.1": spec})
    assert result.conformant is False
    kinds = {v.kind for v in result.violations}
    assert ConformanceViolationKind.PHASE_RESULT_UNVERIFIED in kinds


def test_phase_result_unverified_no_ref() -> None:
    """phase_result_required=True + receipt with phase_result_ref=None."""
    contract = _make_contract("b.1", phase_result_required=True)
    receipt = _make_receipt("b.1", phase_result_ref=None)
    spec = _make_spec("b.1", contract=contract, receipt=receipt)
    result = verify_boundary_conformance("arnold.workflow", {"b.1": spec})
    assert result.conformant is False
    kinds = {v.kind for v in result.violations}
    assert ConformanceViolationKind.PHASE_RESULT_UNVERIFIED in kinds


def test_phase_result_satisfied() -> None:
    """phase_result_required=True + receipt with phase_result_ref → OK."""
    contract = _make_contract("b.1", phase_result_required=True)
    receipt = _make_receipt("b.1", phase_result_ref="result.json")
    spec = _make_spec("b.1", contract=contract, receipt=receipt)
    result = verify_boundary_conformance("arnold.workflow", {"b.1": spec})
    kinds = {v.kind for v in result.violations}
    assert ConformanceViolationKind.PHASE_RESULT_UNVERIFIED not in kinds


# ── verify_boundary_conformance: template conformance ─────────────────────


def test_template_conformance_missing_fields() -> None:
    """Template kind with missing required fields → MISSING_REQUIRED_FIELD."""
    contract = _make_contract(
        "b.1",
        required_artifacts=(),  # required by revision_boundary
        phase_result_required=False,
        details={},  # missing revision_kind, revision_log_ref
    )
    spec = _make_spec("b.1", contract=contract, template_kind="revision_boundary")
    result = verify_boundary_conformance(
        "arnold.workflow",
        {"b.1": spec},
        template_kinds={"b.1": "revision_boundary"},
    )
    assert result.conformant is False
    kinds = {v.kind for v in result.violations}
    assert ConformanceViolationKind.MISSING_REQUIRED_FIELD in kinds


def test_template_conformance_fully_satisfied() -> None:
    """Template with all required fields populated → no MISSING_REQUIRED_FIELD."""
    contract = BoundaryContract(
        boundary_id="b.1",
        workflow_id="arnold.workflow",
        row_id="b.1.row",
        phase=BoundaryPhase.REVISE,
        required_artifacts=("revised.json",),
        expected_state_delta={"stage": "revised"},
        phase_result_required=True,
        receipt_required=True,
        details={
            "revision_kind": "revision",
            "revision_log_ref": "log.md",
        },
    )
    spec = _make_spec("b.1", contract=contract, template_kind="revision_boundary")
    result = verify_boundary_conformance(
        "arnold.workflow",
        {"b.1": spec},
        template_kinds={"b.1": "revision_boundary"},
    )
    kinds = {v.kind for v in result.violations}
    assert ConformanceViolationKind.MISSING_REQUIRED_FIELD not in kinds


def test_template_kinds_override_spec_level() -> None:
    """template_kinds parameter overrides spec.template_kind."""
    # spec says revision_boundary, but parameter says external_effect
    contract = _make_contract("b.1", details={"effect_kind": "ext", "effect_id": "e1"})
    spec = _make_spec("b.1", contract=contract, template_kind="revision_boundary")
    result = verify_boundary_conformance(
        "arnold.workflow",
        {"b.1": spec},
        template_kinds={"b.1": "external_effect"},
    )
    # With external_effect, missing_required_field for effect_kind/effect_id would NOT trigger 
    # since they are present. But other fields like required_artifacts still apply.
    kinds = {v.kind for v in result.violations}
    # Should NOT have revision_boundary level violations
    for v in result.violations:
        if v.kind == ConformanceViolationKind.MISSING_REQUIRED_FIELD:
            assert v.detail.get("template_kind") != "revision_boundary"


# ── verify_boundary_conformance: native-platform-only metadata ─────────────


def test_native_platform_only_without_shared_profile_triggers_violation() -> None:
    """Contract with native_platform_only=True and no template kind → TEMPLATE_PROFILE_MISMATCH."""
    contract = _make_contract(
        "b.native",
        required_artifacts=("artifact.json",),
        receipt_required=True,
        phase_result_required=True,
        details={
            "native_platform_metadata": {"runtime": "megaplan"},
            "native_platform_only": True,
        },
    )
    receipt = _make_receipt("b.native", artifact_refs=("artifact.json",), phase_result_ref="result.json")
    ev = _make_evidence("ev.1", "b.native", artifact_refs=("artifact.json",))
    spec = _make_spec("b.native", contract=contract, receipt=receipt, evidence=(ev,), template_kind=None)
    result = verify_boundary_conformance("arnold.workflow", {"b.native": spec})
    assert result.conformant is False
    kinds = {v.kind for v in result.violations}
    assert ConformanceViolationKind.TEMPLATE_PROFILE_MISMATCH in kinds
    # Verify the violation detail carries the right information
    mismatch = [v for v in result.violations if v.kind == ConformanceViolationKind.TEMPLATE_PROFILE_MISMATCH]
    assert len(mismatch) == 1
    assert mismatch[0].detail.get("native_platform_only") is True


def test_native_platform_only_with_shared_profile_does_not_trigger() -> None:
    """Contract with native_platform_metadata AND a declared template kind → no TEMPLATE_PROFILE_MISMATCH."""
    contract = BoundaryContract(
        boundary_id="b.with_profile",
        workflow_id="arnold.workflow",
        row_id="b.with_profile.1",
        phase=BoundaryPhase.REVISE,
        required_artifacts=("revised.json",),
        expected_state_delta={"stage": "revised"},
        phase_result_required=True,
        receipt_required=True,
        details={
            "native_platform_metadata": {"runtime": "megaplan"},
            "revision_kind": "revision",
            "revision_log_ref": "log.md",
        },
    )
    receipt = _make_receipt("b.with_profile", artifact_refs=("revised.json",))
    spec = _make_spec("b.with_profile", contract=contract, receipt=receipt, template_kind="revision_boundary")
    result = verify_boundary_conformance(
        "arnold.workflow",
        {"b.with_profile": spec},
        template_kinds={"b.with_profile": "revision_boundary"},
    )
    kinds = {v.kind for v in result.violations}
    assert ConformanceViolationKind.TEMPLATE_PROFILE_MISMATCH not in kinds


def test_native_platform_only_metadata_without_only_flag_triggers() -> None:
    """Contract with native_platform_metadata (non-empty dict) and no template → violation."""
    contract = _make_contract(
        "b.meta",
        required_artifacts=("artifact.json",),
        receipt_required=True,
        phase_result_required=True,
        details={"native_platform_metadata": {"runtime": "megaplan"}},
    )
    receipt = _make_receipt("b.meta", artifact_refs=("artifact.json",), phase_result_ref="result.json")
    ev = _make_evidence("ev.1", "b.meta", artifact_refs=("artifact.json",))
    spec = _make_spec("b.meta", contract=contract, receipt=receipt, evidence=(ev,), template_kind=None)
    result = verify_boundary_conformance("arnold.workflow", {"b.meta": spec})
    kinds = {v.kind for v in result.violations}
    assert ConformanceViolationKind.TEMPLATE_PROFILE_MISMATCH in kinds


def test_native_platform_only_empty_metadata_does_not_trigger() -> None:
    """Contract with native_platform_metadata={} (empty) and no template → no profile mismatch."""
    contract = _make_contract(
        "b.empty",
        required_artifacts=("artifact.json",),
        receipt_required=True,
        phase_result_required=True,
        details={"native_platform_metadata": {}},
    )
    receipt = _make_receipt("b.empty", artifact_refs=("artifact.json",), phase_result_ref="result.json")
    ev = _make_evidence("ev.1", "b.empty", artifact_refs=("artifact.json",))
    spec = _make_spec("b.empty", contract=contract, receipt=receipt, evidence=(ev,), template_kind=None)
    result = verify_boundary_conformance("arnold.workflow", {"b.empty": spec})
    kinds = {v.kind for v in result.violations}
    assert ConformanceViolationKind.TEMPLATE_PROFILE_MISMATCH not in kinds


# ── verify_boundary_conformance: template-version compatibility ────────────


def test_template_version_pin_compatible_does_not_trigger() -> None:
    """Template version pin with compatible (same) version → no TEMPLATE_PROFILE_MISMATCH."""
    from arnold.workflow.boundary_templates import pin_template_version

    contract = BoundaryContract(
        boundary_id="b.revision",
        workflow_id="arnold.workflow",
        row_id="b.revision.1",
        phase=BoundaryPhase.REVISE,
        required_artifacts=("revised.json",),
        expected_state_delta={"stage": "revised"},
        phase_result_required=True,
        receipt_required=True,
        details={"revision_kind": "revision", "revision_log_ref": "log.md"},
    )
    receipt = _make_receipt("b.revision", artifact_refs=("revised.json",))
    spec = _make_spec("b.revision", contract=contract, receipt=receipt, template_kind="revision_boundary")
    pin = pin_template_version("revision_boundary", "1.0.0")
    result = verify_boundary_conformance(
        "arnold.workflow",
        {"b.revision": spec},
        template_kinds={"b.revision": "revision_boundary"},
        version_pins={"b.revision": pin},
    )
    kinds = {v.kind for v in result.violations}
    assert ConformanceViolationKind.TEMPLATE_PROFILE_MISMATCH not in kinds


def test_template_version_pin_incompatible_triggers_violation() -> None:
    """Template version pin with an incompatible version → TEMPLATE_PROFILE_MISMATCH."""
    from arnold.workflow.boundary_templates import pin_template_version
    from arnold.workflow.boundary_evidence import TemplateCompatibility, TemplateCompatibilityResult

    # Create a pin that would be flagged as incompatible by monkey-patching
    # check_template_upgrade to return BREAKING_CHANGE.
    contract = BoundaryContract(
        boundary_id="b.breaking",
        workflow_id="arnold.workflow",
        row_id="b.breaking.1",
        phase=BoundaryPhase.REVISE,
        required_artifacts=("revised.json",),
        expected_state_delta={"stage": "revised"},
        phase_result_required=True,
        receipt_required=True,
        details={"revision_kind": "revision", "revision_log_ref": "log.md"},
    )
    receipt = _make_receipt("b.breaking", artifact_refs=("revised.json",))
    spec = _make_spec("b.breaking", contract=contract, receipt=receipt, template_kind="revision_boundary")
    pin = pin_template_version("revision_boundary", "0.9.0")

    import arnold.workflow.boundary_conformance as bcm
    _original = bcm.check_template_upgrade

    def _incompatible_upgrade(kind, from_version, to_version, template_id=None):
        return TemplateCompatibilityResult(
            compatibility=TemplateCompatibility.BREAKING_CHANGE,
            template_id=template_id or kind.value if hasattr(kind, 'value') else str(kind),
            from_version=from_version,
            to_version=to_version,
            removed_required_fields=("details.revision_kind",),
        )

    try:
        bcm.check_template_upgrade = _incompatible_upgrade  # type: ignore[assignment]
        result = verify_boundary_conformance(
            "arnold.workflow",
            {"b.breaking": spec},
            template_kinds={"b.breaking": "revision_boundary"},
            version_pins={"b.breaking": pin},
        )
        kinds = {v.kind for v in result.violations}
        assert ConformanceViolationKind.TEMPLATE_PROFILE_MISMATCH in kinds
        mismatch = [v for v in result.violations if v.kind == ConformanceViolationKind.TEMPLATE_PROFILE_MISMATCH]
        assert len(mismatch) == 1
        assert mismatch[0].detail.get("compatibility") == "breaking_change"
    finally:
        bcm.check_template_upgrade = _original  # type: ignore[assignment]


def test_no_version_pin_no_compatibility_check() -> None:
    """Without version_pins, no compatibility violations are emitted."""
    contract = BoundaryContract(
        boundary_id="b.revision",
        workflow_id="arnold.workflow",
        row_id="b.revision.1",
        phase=BoundaryPhase.REVISE,
        required_artifacts=("revised.json",),
        expected_state_delta={"stage": "revised"},
        phase_result_required=True,
        receipt_required=True,
        details={"revision_kind": "revision", "revision_log_ref": "log.md"},
    )
    receipt = _make_receipt("b.revision", artifact_refs=("revised.json",))
    spec = _make_spec("b.revision", contract=contract, receipt=receipt, template_kind="revision_boundary")
    # No version_pins argument
    result = verify_boundary_conformance(
        "arnold.workflow",
        {"b.revision": spec},
        template_kinds={"b.revision": "revision_boundary"},
    )
    kinds = {v.kind for v in result.violations}
    assert ConformanceViolationKind.TEMPLATE_PROFILE_MISMATCH not in kinds


# ── verify_boundary_conformance: graph topology ───────────────────────────


def test_dangling_dependency() -> None:
    """Dependency on missing boundary → GRAPH_DANGLING_DEPENDENCY."""
    spec = _make_spec("b.1", dependencies=("b.missing",))
    result = verify_boundary_conformance("arnold.workflow", {"b.1": spec})
    assert result.conformant is False
    kinds = {v.kind for v in result.violations}
    assert ConformanceViolationKind.GRAPH_DANGLING_DEPENDENCY in kinds


def test_dependency_on_existing_boundary_is_ok() -> None:
    """Dependency on an existing boundary → no graph violation."""
    spec_a = _make_spec("b.a", receipt=_make_receipt("b.a"))
    spec_b = _make_spec("b.b", dependencies=("b.a",), receipt=_make_receipt("b.b"))
    result = verify_boundary_conformance("arnold.workflow", {"b.a": spec_a, "b.b": spec_b})
    kinds = {v.kind for v in result.violations}
    assert ConformanceViolationKind.GRAPH_DANGLING_DEPENDENCY not in kinds


def test_graph_spec_dangling_fan_out() -> None:
    """Graph spec with fan-out to missing boundary → GRAPH_DANGLING_FAN_OUT."""
    gs = _make_graph_spec("g.1", "b.1", fan_out_refs=("b.missing",))
    spec = _make_spec("b.1", graph_spec=gs)
    result = verify_boundary_conformance("arnold.workflow", {"b.1": spec})
    assert result.conformant is False
    kinds = {v.kind for v in result.violations}
    assert ConformanceViolationKind.GRAPH_DANGLING_FAN_OUT in kinds


def test_graph_spec_dangling_fan_in() -> None:
    """Graph spec with fan-in from missing boundary → GRAPH_DANGLING_FAN_IN."""
    gs = _make_graph_spec("g.1", "b.1", fan_in_ref="b.missing")
    spec = _make_spec("b.1", graph_spec=gs)
    result = verify_boundary_conformance("arnold.workflow", {"b.1": spec})
    assert result.conformant is False
    kinds = {v.kind for v in result.violations}
    assert ConformanceViolationKind.GRAPH_DANGLING_FAN_IN in kinds


def test_graph_spec_dangling_join() -> None:
    """Graph spec with join to missing boundary → GRAPH_DANGLING_JOIN."""
    gs = _make_graph_spec("g.1", "b.1", joins=("b.missing",))
    spec = _make_spec("b.1", graph_spec=gs)
    result = verify_boundary_conformance("arnold.workflow", {"b.1": spec})
    assert result.conformant is False
    kinds = {v.kind for v in result.violations}
    assert ConformanceViolationKind.GRAPH_DANGLING_JOIN in kinds


def test_graph_spec_dangling_dependency() -> None:
    """Graph spec with dependency on missing boundary → GRAPH_DANGLING_DEPENDENCY."""
    gs = _make_graph_spec("g.1", "b.1", dependencies=("b.missing",))
    spec = _make_spec("b.1", graph_spec=gs)
    result = verify_boundary_conformance("arnold.workflow", {"b.1": spec})
    assert result.conformant is False
    kinds = {v.kind for v in result.violations}
    assert ConformanceViolationKind.GRAPH_DANGLING_DEPENDENCY in kinds


def test_valid_graph_topology() -> None:
    """Fan-out/fan-in/joins all resolved → no graph violations."""
    gs = _make_graph_spec(
        "g.1", "b.1",
        fan_out_refs=("b.2",),
        fan_in_ref="b.2",
        joins=("b.2",),
        dependencies=("b.2",),
    )
    spec1 = _make_spec("b.1", graph_spec=gs, receipt=_make_receipt("b.1"))
    spec2 = _make_spec("b.2", receipt=_make_receipt("b.2"))
    result = verify_boundary_conformance("arnold.workflow", {"b.1": spec1, "b.2": spec2})
    kinds = {v.kind for v in result.violations}
    for gk in (
        ConformanceViolationKind.GRAPH_DANGLING_FAN_OUT,
        ConformanceViolationKind.GRAPH_DANGLING_FAN_IN,
        ConformanceViolationKind.GRAPH_DANGLING_JOIN,
        ConformanceViolationKind.GRAPH_DANGLING_DEPENDENCY,
    ):
        assert gk not in kinds


# ── verify_single_boundary ────────────────────────────────────────────────


def test_verify_single_boundary_conformant() -> None:
    """verify_single_boundary for a fully satisfied boundary."""
    contract = _make_contract("b.1")
    receipt = _make_receipt("b.1")
    spec = _make_spec("b.1", contract=contract, receipt=receipt)
    result = verify_single_boundary(spec)
    assert result.boundary_count == 1
    assert result.conformant is True


def test_verify_single_boundary_with_template_kind() -> None:
    """verify_single_boundary with explicit template_kind performs template checks."""
    contract = BoundaryContract(
        boundary_id="b.1",
        workflow_id="arnold.workflow",
        row_id="b.1.row",
        phase=BoundaryPhase.REVISE,
        required_artifacts=("revised.json",),
        expected_state_delta={"stage": "revised"},
        phase_result_required=True,
        receipt_required=True,
        details={"revision_kind": "revision", "revision_log_ref": "log.md"},
    )
    receipt = _make_receipt("b.1", artifact_refs=("revised.json",))
    spec = _make_spec("b.1", contract=contract, receipt=receipt)
    result = verify_single_boundary(spec, template_kind="revision_boundary")
    assert result.conformant is True


# ── verify_semantic_findings_against_boundaries ───────────────────────────


def test_semantic_findings_all_resolved() -> None:
    """All findings reference known boundaries → no violations."""
    f1 = SemanticFinding(
        finding_id="f.1",
        boundary_id="b.1",
        description="Finding on b.1",
    )
    spec = _make_spec("b.1")
    result = verify_semantic_findings_against_boundaries((f1,), {"b.1": spec})
    assert len(result) == 0


def test_semantic_finding_unresolved() -> None:
    """Finding references unknown boundary → SEMANTIC_FINDING_UNRESOLVED."""
    f1 = SemanticFinding(
        finding_id="f.1",
        boundary_id="b.missing",
        description="Finding on missing boundary",
    )
    spec = _make_spec("b.1")
    result = verify_semantic_findings_against_boundaries((f1,), {"b.1": spec})
    assert len(result) == 1
    assert result[0].kind == ConformanceViolationKind.SEMANTIC_FINDING_UNRESOLVED
    assert result[0].boundary_id == "b.missing"


def test_semantic_findings_mixed() -> None:
    """Mix of resolved and unresolved findings."""
    f_ok = SemanticFinding(finding_id="f.ok", boundary_id="b.1", description="ok")
    f_bad = SemanticFinding(finding_id="f.bad", boundary_id="b.missing", description="bad")
    spec = _make_spec("b.1")
    result = verify_semantic_findings_against_boundaries((f_ok, f_bad), {"b.1": spec})
    assert len(result) == 1
    assert result[0].kind == ConformanceViolationKind.SEMANTIC_FINDING_UNRESOLVED


# ── classify_and_verify_boundaries ────────────────────────────────────────


def test_classify_and_verify_auto_classifies() -> None:
    """classify_and_verify_boundaries auto-detects template kinds."""
    contract = BoundaryContract(
        boundary_id="b.revision",
        workflow_id="arnold.workflow",
        row_id="b.rev.1",
        phase=BoundaryPhase.REVISE,
        required_artifacts=("revised.json",),
        expected_state_delta={"stage": "done"},
        phase_result_required=True,
        receipt_required=True,
        details={"revision_kind": "revision", "revision_log_ref": "log.md"},
    )
    receipt = _make_receipt("b.revision")
    spec = _make_spec("b.revision", contract=contract, receipt=receipt)
    result = classify_and_verify_boundaries("arnold.workflow", {"b.revision": spec})
    # Should auto-detect as revision_boundary and check conformance
    assert result.boundary_count == 1
    assert ConformanceViolationKind.MISSING_REQUIRED_FIELD not in {v.kind for v in result.violations}


def test_classify_and_verify_respects_explicit_kind() -> None:
    """classify_and_verify_boundaries respects explicit template_kind on spec."""
    contract = BoundaryContract(
        boundary_id="b.ext",
        workflow_id="arnold.workflow",
        row_id="b.ext.row",
        required_artifacts=("effect.json",),
        details={"effect_kind": "ext", "effect_id": "e1"},
    )
    spec = _make_spec("b.ext", contract=contract, template_kind="external_effect")
    result = classify_and_verify_boundaries("arnold.workflow", {"b.ext": spec})
    # With row_id, effect_kind, and effect_id all present, external_effect template
    # should not produce MISSING_REQUIRED_FIELD violations.
    kinds = {v.kind for v in result.violations}
    assert ConformanceViolationKind.MISSING_REQUIRED_FIELD not in kinds


# ── Multiple boundaries in graph ──────────────────────────────────────────


def test_multi_boundary_workflow_with_all_violations() -> None:
    """Workflow with diverse violations across boundaries reports all of them."""
    # b.ok: fully conformant
    contract_ok = _make_contract("b.ok")
    receipt_ok = _make_receipt("b.ok")
    spec_ok = _make_spec("b.ok", contract=contract_ok, receipt=receipt_ok)

    # b.no_receipt: receipt required but missing
    contract_nr = _make_contract("b.no_receipt", receipt_required=True)
    spec_nr = _make_spec("b.no_receipt", contract=contract_nr, receipt=None)

    # b.wrong_artifact: receipt missing required artifact
    contract_wa = _make_contract("b.wrong_artifact", required_artifacts=("x.json",))
    receipt_wa = _make_receipt("b.wrong_artifact", artifact_refs=("y.json",))
    spec_wa = _make_spec("b.wrong_artifact", contract=contract_wa, receipt=receipt_wa)

    # b.dangle: depends on missing boundary
    spec_dangle = _make_spec("b.dangle", dependencies=("b.nonexistent",), receipt=_make_receipt("b.dangle"))

    boundaries = {
        "b.ok": spec_ok,
        "b.no_receipt": spec_nr,
        "b.wrong_artifact": spec_wa,
        "b.dangle": spec_dangle,
    }
    result = verify_boundary_conformance("arnold.workflow", boundaries)
    assert result.conformant is False
    assert result.boundary_count == 4
    assert result.receipt_count == 3  # b.ok, b.wrong_artifact, b.dangle

    # Check we have diverse violation kinds
    kinds = {v.kind for v in result.violations}
    assert len(kinds) >= 3  # multiple kinds represented


def test_multi_boundary_receipt_evidence_counts() -> None:
    """Receipt and evidence counts are accurate."""
    spec_rcpt = _make_spec("b.rcpt", receipt=_make_receipt("b.rcpt"))
    spec_ev = _make_spec(
        "b.ev",
        contract=_make_contract("b.ev", receipt_required=False, phase_result_required=False),
        evidence=(_make_evidence("ev.1", "b.ev"),),
    )
    spec_both = _make_spec(
        "b.both",
        receipt=_make_receipt("b.both"),
        evidence=(_make_evidence("ev.2", "b.both"),),
    )
    spec_none = _make_spec(
        "b.none",
        contract=_make_contract("b.none", receipt_required=False, phase_result_required=False),
    )
    boundaries = {
        "b.rcpt": spec_rcpt,
        "b.ev": spec_ev,
        "b.both": spec_both,
        "b.none": spec_none,
    }
    result = verify_boundary_conformance("arnold.workflow", boundaries)
    assert result.receipt_count == 2  # b.rcpt, b.both
    assert result.evidence_count == 2  # b.ev, b.both


# ── Edge cases ────────────────────────────────────────────────────────────


def test_receipt_matches_contract_workflow_id() -> None:
    """Receipt that matches contract workflow_id but not verification workflow_id is OK."""
    contract = _make_contract("b.1", workflow_id="custom.wf")
    receipt = _make_receipt("b.1", workflow_id="custom.wf")
    spec = _make_spec("b.1", contract=contract, receipt=receipt)
    result = verify_boundary_conformance("arnold.workflow", {"b.1": spec})
    kinds = {v.kind for v in result.violations}
    assert ConformanceViolationKind.RECEIPT_WORKFLOW_MISMATCH not in kinds


def test_evidence_matches_contract_workflow_id() -> None:
    """Evidence matching contract workflow_id is OK."""
    contract = _make_contract("b.1", workflow_id="custom.wf")
    ev = _make_evidence("ev.1", "b.1", workflow_id="custom.wf")
    spec = _make_spec("b.1", contract=contract, receipt=_make_receipt("b.1"), evidence=(ev,))
    result = verify_boundary_conformance("arnold.workflow", {"b.1": spec})
    kinds = {v.kind for v in result.violations}
    assert ConformanceViolationKind.EVIDENCE_WORKFLOW_MISMATCH not in kinds


def test_deterministic_ordering() -> None:
    """Violations are always in deterministic order (sorted by boundary_id)."""
    contract_a = _make_contract("b.a", receipt_required=True)
    contract_z = _make_contract("b.z", receipt_required=True)
    boundaries = {
        "b.z": _make_spec("b.z", contract=contract_z, receipt=None),
        "b.a": _make_spec("b.a", contract=contract_a, receipt=None),
    }
    result = verify_boundary_conformance("arnold.workflow", boundaries)
    # Boundaries are iterated in sorted order → b.a first, then b.z
    assert len(result.violations) > 0
    # First violation should be from b.a
    first_bid = result.violations[0].boundary_id
    # Both boundaries have violations; since b.a < b.z, b.a comes first
    # Actually both have receipt_required violations
    boundary_order = [v.boundary_id for v in result.violations]
    # All for b.a then all for b.z (or interleaved by boundary sort)
    b_a_indices = [i for i, bid in enumerate(boundary_order) if bid == "b.a"]
    b_z_indices = [i for i, bid in enumerate(boundary_order) if bid == "b.z"]
    assert max(b_a_indices) < min(b_z_indices) if b_a_indices and b_z_indices else True


def test_workflow_boundary_spec_without_template_kind() -> None:
    """WorkflowBoundarySpec with template_kind=None does not trigger template checks."""
    contract = _make_contract("b.1", details={})
    spec = _make_spec("b.1", contract=contract, template_kind=None)
    result = verify_boundary_conformance("arnold.workflow", {"b.1": spec})
    kinds = {v.kind for v in result.violations}
    assert ConformanceViolationKind.MISSING_REQUIRED_FIELD not in kinds


def test_cross_workflow_graph_ref_not_checked() -> None:
    """cross_workflow_refs in BoundaryGraph are noted but not checked (no resolution context)."""
    gs = BoundaryGraph(
        graph_id="g.1",
        boundary_id="b.1",
        cross_workflow_refs=("other.wf/b.1",),
    )
    spec = _make_spec("b.1", graph_spec=gs)
    result = verify_boundary_conformance("arnold.workflow", {"b.1": spec})
    kinds = {v.kind for v in result.violations}
    assert ConformanceViolationKind.GRAPH_DANGLING_CROSS_WORKFLOW not in kinds
