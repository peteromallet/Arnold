"""Round-trip tests for boundary evidence vocabulary (S2.5).

Covers BoundaryContract, BoundaryReceipt, AuthorityRecord, and
SemanticFinding — verifying construction, serialization, required-field
validation, and separation from SemanticEvidence/SemanticFailure.
"""

from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError
from pathlib import Path
from types import MappingProxyType

import pytest

from arnold.workflow import diagnostics
from arnold.workflow.diagnostics import DiagnosticCode, DiagnosticFamily, DiagnosticSeverity


# ── Importability and stability ───────────────────────────────────────────


def test_boundary_evidence_module_importable() -> None:
    """boundary_evidence module must be importable with all public symbols present."""
    from arnold.workflow.boundary_evidence import (
        AuthorityRecord,
        BoundaryContract,
        BoundaryOutcome,
        BoundaryPhase,
        BoundaryReceipt,
        FindingSeverity,
        SemanticFinding,
    )
    assert BoundaryPhase.PREP == "prep"
    assert BoundaryPhase.PLAN == "plan"
    assert BoundaryPhase.CRITIQUE == "critique"
    assert BoundaryPhase.GATE == "gate"
    assert BoundaryPhase.REVISE == "revise"
    assert BoundaryOutcome.COMPLETE == "complete"
    assert FindingSeverity.ERROR == "error"


def test_boundary_evidence_re_exported_from_workflow_init() -> None:
    """All stable boundary types must be importable from arnold.workflow."""
    from arnold.workflow import (
        AuthorityRecord,
        BoundaryContract,
        BoundaryOutcome,
        BoundaryPhase,
        BoundaryReceipt,
        FindingSeverity,
        SemanticFinding,
    )
    assert BoundaryContract is not None
    assert BoundaryReceipt is not None
    assert AuthorityRecord is not None
    assert SemanticFinding is not None


# ── BoundaryContract tests ────────────────────────────────────────────────


def test_boundary_contract_constructs_with_required_fields() -> None:
    """BoundaryContract must construct with boundary_id and workflow_id."""
    from arnold.workflow.boundary_evidence import BoundaryContract, BoundaryPhase

    contract = BoundaryContract(
        boundary_id="prep-boundary",
        workflow_id="megaplan-review",
    )
    assert contract.boundary_id == "prep-boundary"
    assert contract.workflow_id == "megaplan-review"
    assert contract.phase is None
    assert contract.required_artifacts == ()
    assert contract.phase_result_required is False
    assert contract.receipt_required is False
    assert contract.authority_required is False
    assert contract.contract_version == "arnold.workflow.boundary_contract.v1"


def test_boundary_contract_constructs_with_all_fields() -> None:
    """BoundaryContract must carry all durable-proof fields without error."""
    from arnold.workflow.boundary_evidence import BoundaryContract, BoundaryPhase

    contract = BoundaryContract(
        boundary_id="gate-boundary",
        workflow_id="megaplan-review",
        row_id="s2.gate.1",
        phase=BoundaryPhase.GATE,
        required_artifacts=("gate_decision.json", "phase_result.json"),
        expected_state_delta={"current_phase": "gate"},
        expected_history_entry="gate_completed",
        phase_result_required=True,
        receipt_required=True,
        authority_required=True,
        details={"policy": "strict"},
    )
    assert contract.boundary_id == "gate-boundary"
    assert contract.workflow_id == "megaplan-review"
    assert contract.row_id == "s2.gate.1"
    assert contract.phase is BoundaryPhase.GATE
    assert contract.required_artifacts == ("gate_decision.json", "phase_result.json")
    assert dict(contract.expected_state_delta) == {"current_phase": "gate"}
    assert contract.expected_history_entry == "gate_completed"
    assert contract.phase_result_required is True
    assert contract.receipt_required is True
    assert contract.authority_required is True


def test_boundary_contract_rejects_empty_boundary_id() -> None:
    """BoundaryContract must reject empty boundary_id."""
    from arnold.workflow.boundary_evidence import BoundaryContract

    with pytest.raises(ValueError, match="boundary_id"):
        BoundaryContract(boundary_id="", workflow_id="w1")


def test_boundary_contract_rejects_empty_workflow_id() -> None:
    """BoundaryContract must reject empty workflow_id."""
    from arnold.workflow.boundary_evidence import BoundaryContract

    with pytest.raises(ValueError, match="workflow_id"):
        BoundaryContract(boundary_id="b1", workflow_id="")


def test_boundary_contract_is_frozen() -> None:
    """BoundaryContract must be immutable (frozen dataclass)."""
    from arnold.workflow.boundary_evidence import BoundaryContract

    contract = BoundaryContract(boundary_id="b1", workflow_id="w1")
    with pytest.raises(FrozenInstanceError):
        contract.boundary_id = "changed"  # type: ignore[misc]


def test_boundary_contract_to_dict_round_trip() -> None:
    """BoundaryContract.to_dict() must produce a sidecar-safe dict preserving all fields."""
    from arnold.workflow.boundary_evidence import BoundaryContract, BoundaryPhase

    contract = BoundaryContract(
        boundary_id="prep-boundary",
        workflow_id="megaplan-review",
        row_id="s2.prep.1",
        phase=BoundaryPhase.PREP,
        required_artifacts=("research.md", "brief.md"),
        expected_state_delta={"current_phase": "prep"},
        expected_history_entry="prep_completed",
        phase_result_required=True,
        receipt_required=True,
        authority_required=False,
        details={"owner": "megaplan"},
    )

    payload = contract.to_dict()

    assert payload["boundary_id"] == "prep-boundary"
    assert payload["workflow_id"] == "megaplan-review"
    assert payload["row_id"] == "s2.prep.1"
    assert payload["phase"] == "prep"
    assert payload["required_artifacts"] == ["research.md", "brief.md"]
    assert payload["expected_state_delta"] == {"current_phase": "prep"}
    assert payload["expected_history_entry"] == "prep_completed"
    assert payload["phase_result_required"] is True
    assert payload["receipt_required"] is True
    assert payload["authority_required"] is False
    assert payload["contract_version"] == "arnold.workflow.boundary_contract.v1"
    assert payload["details"] == {"owner": "megaplan"}


def test_boundary_contract_to_dict_preserves_s5_effect_and_projection_details() -> None:
    """BoundaryContract must preserve S5-style effect, receipt, and projection evidence."""
    from arnold.workflow.boundary_evidence import BoundaryContract

    contract = BoundaryContract(
        boundary_id="review-rework-effects",
        workflow_id="megaplan-review",
        row_id="s5.review_rework_effects.1",
        required_artifacts=("review.json", "finalize.json"),
        expected_state_delta={"current_phase": "review", "projection_state": "finalized"},
        expected_history_entry="review_rework_projected",
        phase_result_required=True,
        receipt_required=True,
        authority_required=True,
        details={
            "effect": {
                "effect_id": "artifact.review.output",
                "projection_cases": (
                    "execute",
                    "revise_fallback",
                    "no_review_deferred_human",
                ),
            },
            "authority": {
                "scope": "review.cap_exhausted",
                "outcomes": ("blocked", "force_proceeded"),
                "policy_ref": "megaplan:review",
            },
            "evidence_surface_ref": "REVIEW_POLICY.metadata.route_surface.rework_cycle",
        },
    )

    payload = contract.to_dict()

    assert payload["row_id"] == "s5.review_rework_effects.1"
    assert payload["required_artifacts"] == ["review.json", "finalize.json"]
    assert payload["expected_state_delta"] == {
        "current_phase": "review",
        "projection_state": "finalized",
    }
    assert payload["expected_history_entry"] == "review_rework_projected"
    assert payload["phase_result_required"] is True
    assert payload["receipt_required"] is True
    assert payload["authority_required"] is True
    assert payload["details"] == {
        "effect": {
            "effect_id": "artifact.review.output",
            "projection_cases": [
                "execute",
                "revise_fallback",
                "no_review_deferred_human",
            ],
        },
        "authority": {
            "scope": "review.cap_exhausted",
            "outcomes": ["blocked", "force_proceeded"],
            "policy_ref": "megaplan:review",
        },
        "evidence_surface_ref": "REVIEW_POLICY.metadata.route_surface.rework_cycle",
    }
    for key in ("route_target", "next_step", "routing_predicate"):
        assert key not in payload


# ── BoundaryReceipt tests ─────────────────────────────────────────────────


def test_boundary_receipt_constructs_with_required_fields() -> None:
    """BoundaryReceipt must construct with boundary_id and workflow_id."""
    from arnold.workflow.boundary_evidence import BoundaryReceipt

    receipt = BoundaryReceipt(
        boundary_id="prep-boundary",
        workflow_id="megaplan-review",
    )
    assert receipt.boundary_id == "prep-boundary"
    assert receipt.workflow_id == "megaplan-review"
    assert receipt.artifact_refs == ()
    assert receipt.authority_records == ()
    assert receipt.receipt_version == "arnold.workflow.boundary_receipt.v1"


def test_boundary_receipt_constructs_with_all_fields() -> None:
    """BoundaryReceipt must carry all durable-proof fields."""
    from arnold.workflow.boundary_evidence import (
        AuthorityRecord,
        BoundaryOutcome,
        BoundaryReceipt,
    )

    authority = AuthorityRecord(
        actor="gate-handler",
        role="gatekeeper",
        decision="proceed",
        scope="megaplan-review",
    )

    receipt = BoundaryReceipt(
        boundary_id="gate-boundary",
        workflow_id="megaplan-review",
        row_id="s2.gate.1",
        invocation_id="inv-001",
        artifact_refs=("gate_decision.json", "phase_result.json"),
        state_observation={"current_phase": "gate", "gate_outcome": "proceed"},
        history_ref="history/gate_completed",
        phase_result_ref="phase_results/gate.json",
        outcome=BoundaryOutcome.COMPLETE,
        authority_records=(authority,),
        details={"checker_version": "v1"},
    )

    assert receipt.boundary_id == "gate-boundary"
    assert receipt.workflow_id == "megaplan-review"
    assert receipt.row_id == "s2.gate.1"
    assert receipt.invocation_id == "inv-001"
    assert receipt.artifact_refs == ("gate_decision.json", "phase_result.json")
    assert dict(receipt.state_observation) == {
        "current_phase": "gate",
        "gate_outcome": "proceed",
    }
    assert receipt.history_ref == "history/gate_completed"
    assert receipt.phase_result_ref == "phase_results/gate.json"
    assert receipt.outcome is BoundaryOutcome.COMPLETE
    assert len(receipt.authority_records) == 1
    assert receipt.authority_records[0].actor == "gate-handler"


def test_boundary_receipt_rejects_empty_boundary_id() -> None:
    """BoundaryReceipt must reject empty boundary_id."""
    from arnold.workflow.boundary_evidence import BoundaryReceipt

    with pytest.raises(ValueError, match="boundary_id"):
        BoundaryReceipt(boundary_id="", workflow_id="w1")


def test_boundary_receipt_is_frozen() -> None:
    """BoundaryReceipt must be immutable."""
    from arnold.workflow.boundary_evidence import BoundaryReceipt

    receipt = BoundaryReceipt(boundary_id="b1", workflow_id="w1")
    with pytest.raises(FrozenInstanceError):
        receipt.boundary_id = "changed"  # type: ignore[misc]


def test_boundary_receipt_to_dict_round_trip() -> None:
    """BoundaryReceipt.to_dict() must produce a sidecar-safe dict."""
    from arnold.workflow.boundary_evidence import (
        AuthorityRecord,
        BoundaryOutcome,
        BoundaryReceipt,
    )

    authority = AuthorityRecord(
        actor="gate-handler",
        role="gatekeeper",
        decision="proceed",
    )
    receipt = BoundaryReceipt(
        boundary_id="gate-boundary",
        workflow_id="megaplan-review",
        row_id="s2.gate.1",
        invocation_id="inv-001",
        artifact_refs=("gate_decision.json",),
        state_observation={"current_phase": "gate"},
        history_ref="history/gate_entry",
        phase_result_ref="phase_results/gate.json",
        outcome=BoundaryOutcome.COMPLETE,
        authority_records=(authority,),
    )

    payload = receipt.to_dict()

    assert payload["boundary_id"] == "gate-boundary"
    assert payload["workflow_id"] == "megaplan-review"
    assert payload["row_id"] == "s2.gate.1"
    assert payload["invocation_id"] == "inv-001"
    assert payload["artifact_refs"] == ["gate_decision.json"]
    assert payload["state_observation"] == {"current_phase": "gate"}
    assert payload["history_ref"] == "history/gate_entry"
    assert payload["phase_result_ref"] == "phase_results/gate.json"
    assert payload["outcome"] == "complete"
    assert payload["receipt_version"] == "arnold.workflow.boundary_receipt.v1"
    assert len(payload["authority_records"]) == 1
    assert payload["authority_records"][0]["actor"] == "gate-handler"


def test_boundary_receipt_to_dict_preserves_s5_authority_and_projection_evidence() -> None:
    """BoundaryReceipt must carry S5 authority records and projection evidence durably."""
    from arnold.workflow.boundary_evidence import (
        AuthorityRecord,
        BoundaryOutcome,
        BoundaryReceipt,
    )

    authority = AuthorityRecord(
        actor="review-policy",
        role="cap_authority",
        decision="force_proceeded",
        scope="review.cap_exhausted",
        conditions=("advisory_cap", "receipt_present"),
        evidence_refs=("receipts/review_cap.json", "policy/review_surface.json"),
        waiver_reason="advisory_threshold_only",
        details={"policy_ref": "megaplan:review"},
    )
    receipt = BoundaryReceipt(
        boundary_id="review-cap-authority",
        workflow_id="megaplan-review",
        row_id="s5.review_cap_authority.1",
        invocation_id="inv-review-001",
        artifact_refs=("review.json", "finalize.json"),
        state_observation={
            "current_phase": "review",
            "projection_state": "finalized",
            "terminal_state": "awaiting_human_verify",
        },
        history_ref="history/review_cap_authorized",
        phase_result_ref="phase_results/review.json",
        outcome=BoundaryOutcome.DEGRADED_CONTINUE,
        authority_records=(authority,),
        details={
            "projection_cases": (
                "execute",
                "no_review_deferred_human",
            ),
            "evidence_surface_ref": (
                "FINALIZE_POLICY.metadata.route_surface.final_projection_routes"
            ),
        },
    )

    payload = receipt.to_dict()

    assert payload["boundary_id"] == "review-cap-authority"
    assert payload["workflow_id"] == "megaplan-review"
    assert payload["row_id"] == "s5.review_cap_authority.1"
    assert payload["invocation_id"] == "inv-review-001"
    assert payload["artifact_refs"] == ["review.json", "finalize.json"]
    assert payload["state_observation"] == {
        "current_phase": "review",
        "projection_state": "finalized",
        "terminal_state": "awaiting_human_verify",
    }
    assert payload["history_ref"] == "history/review_cap_authorized"
    assert payload["phase_result_ref"] == "phase_results/review.json"
    assert payload["outcome"] == "degraded_continue"
    assert payload["authority_records"] == [
        {
            "actor": "review-policy",
            "role": "cap_authority",
            "decision": "force_proceeded",
            "scope": "review.cap_exhausted",
            "conditions": ["advisory_cap", "receipt_present"],
            "evidence_refs": [
                "receipts/review_cap.json",
                "policy/review_surface.json",
            ],
            "waiver_reason": "advisory_threshold_only",
            "authority_version": "arnold.workflow.authority_record.v1",
            "details": {"policy_ref": "megaplan:review"},
        }
    ]
    assert payload["details"] == {
        "projection_cases": [
            "execute",
            "no_review_deferred_human",
        ],
        "evidence_surface_ref": (
            "FINALIZE_POLICY.metadata.route_surface.final_projection_routes"
        ),
    }


# ── AuthorityRecord tests ─────────────────────────────────────────────────


def test_authority_record_constructs_with_required_fields() -> None:
    """AuthorityRecord must construct with actor and role."""
    from arnold.workflow.boundary_evidence import AuthorityRecord

    record = AuthorityRecord(actor="gate-handler", role="gatekeeper")
    assert record.actor == "gate-handler"
    assert record.role == "gatekeeper"
    assert record.decision is None
    assert record.conditions == ()
    assert record.evidence_refs == ()
    assert record.authority_version == "arnold.workflow.authority_record.v1"


def test_authority_record_constructs_with_all_fields() -> None:
    """AuthorityRecord must carry all authority metadata."""
    from arnold.workflow.boundary_evidence import AuthorityRecord

    record = AuthorityRecord(
        actor="gate-handler",
        role="gatekeeper",
        decision="proceed",
        scope="megaplan-review",
        conditions=("test_pass", "coverage_ok"),
        evidence_refs=("receipts/gate.json",),
        expiry="2026-07-07T00:00:00Z",
        waiver_reason="",
        details={"policy": "strict"},
    )
    assert record.actor == "gate-handler"
    assert record.role == "gatekeeper"
    assert record.decision == "proceed"
    assert record.scope == "megaplan-review"
    assert record.conditions == ("test_pass", "coverage_ok")
    assert record.evidence_refs == ("receipts/gate.json",)
    assert record.expiry == "2026-07-07T00:00:00Z"
    assert record.waiver_reason == ""


def test_authority_record_rejects_empty_actor() -> None:
    """AuthorityRecord must reject empty actor."""
    from arnold.workflow.boundary_evidence import AuthorityRecord

    with pytest.raises(ValueError, match="actor"):
        AuthorityRecord(actor="", role="gatekeeper")


def test_authority_record_rejects_empty_role() -> None:
    """AuthorityRecord must reject empty role."""
    from arnold.workflow.boundary_evidence import AuthorityRecord

    with pytest.raises(ValueError, match="role"):
        AuthorityRecord(actor="gate-handler", role="")


def test_authority_record_is_frozen() -> None:
    """AuthorityRecord must be immutable."""
    from arnold.workflow.boundary_evidence import AuthorityRecord

    record = AuthorityRecord(actor="a", role="r")
    with pytest.raises(FrozenInstanceError):
        record.actor = "changed"  # type: ignore[misc]


def test_authority_record_to_dict_round_trip() -> None:
    """AuthorityRecord.to_dict() must produce a sidecar-safe dict."""
    from arnold.workflow.boundary_evidence import AuthorityRecord

    record = AuthorityRecord(
        actor="gate-handler",
        role="gatekeeper",
        decision="proceed",
        scope="megaplan-review",
        conditions=("test_pass",),
        evidence_refs=("receipts/gate.json",),
        expiry="2026-07-07T00:00:00Z",
        waiver_reason="forced_proceed",
    )

    payload = record.to_dict()

    assert payload["actor"] == "gate-handler"
    assert payload["role"] == "gatekeeper"
    assert payload["decision"] == "proceed"
    assert payload["scope"] == "megaplan-review"
    assert payload["conditions"] == ["test_pass"]
    assert payload["evidence_refs"] == ["receipts/gate.json"]
    assert payload["expiry"] == "2026-07-07T00:00:00Z"
    assert payload["waiver_reason"] == "forced_proceed"
    assert payload["authority_version"] == "arnold.workflow.authority_record.v1"


# ── SemanticFinding tests ─────────────────────────────────────────────────


def test_semantic_finding_constructs_with_required_fields() -> None:
    """SemanticFinding must construct with finding_id, boundary_id, description."""
    from arnold.workflow.boundary_evidence import FindingSeverity, SemanticFinding

    finding = SemanticFinding(
        finding_id="F001",
        boundary_id="prep-boundary",
        description="prep artifacts exist but state.json remains initialized",
    )
    assert finding.finding_id == "F001"
    assert finding.boundary_id == "prep-boundary"
    assert finding.description == "prep artifacts exist but state.json remains initialized"
    assert finding.severity is FindingSeverity.ERROR
    assert finding.finding_version == "arnold.workflow.semantic_finding.v1"


def test_semantic_finding_constructs_with_diagnostic_code() -> None:
    """SemanticFinding must accept a DiagnosticCode."""
    from arnold.workflow.boundary_evidence import SemanticFinding

    finding = SemanticFinding(
        finding_id="F002",
        boundary_id="gate-boundary",
        description="missing authority record for gate boundary",
        diagnostic_code=DiagnosticCode.BOUNDARY_CONTRACT_MISSING,
        severity="warning",
    )
    assert finding.diagnostic_code is DiagnosticCode.BOUNDARY_CONTRACT_MISSING
    assert finding.severity == "warning"


def test_semantic_finding_rejects_empty_finding_id() -> None:
    """SemanticFinding must reject empty finding_id."""
    from arnold.workflow.boundary_evidence import SemanticFinding

    with pytest.raises(ValueError, match="finding_id"):
        SemanticFinding(finding_id="", boundary_id="b1", description="desc")


def test_semantic_finding_rejects_empty_boundary_id() -> None:
    """SemanticFinding must reject empty boundary_id."""
    from arnold.workflow.boundary_evidence import SemanticFinding

    with pytest.raises(ValueError, match="boundary_id"):
        SemanticFinding(finding_id="F1", boundary_id="", description="desc")


def test_semantic_finding_rejects_empty_description() -> None:
    """SemanticFinding must reject empty description."""
    from arnold.workflow.boundary_evidence import SemanticFinding

    with pytest.raises(ValueError, match="description"):
        SemanticFinding(finding_id="F1", boundary_id="b1", description="")


def test_semantic_finding_is_frozen() -> None:
    """SemanticFinding must be immutable."""
    from arnold.workflow.boundary_evidence import SemanticFinding

    finding = SemanticFinding(
        finding_id="F1", boundary_id="b1", description="desc",
    )
    with pytest.raises(FrozenInstanceError):
        finding.description = "changed"  # type: ignore[misc]


def test_semantic_finding_to_dict_round_trip() -> None:
    """SemanticFinding.to_dict() must produce a sidecar-safe dict."""
    from arnold.workflow.boundary_evidence import SemanticFinding

    finding = SemanticFinding(
        finding_id="F001",
        boundary_id="prep-boundary",
        description="prep artifacts exist but state.json remains initialized",
        severity="error",
        diagnostic_code=DiagnosticCode.BOUNDARY_EVIDENCE_STALE,
        contract_ref="contracts/prep.json",
        evidence_ref="receipts/prep.json",
        details={"state_key": "current_state", "expected": "prep_done"},
    )

    payload = finding.to_dict()

    assert payload["finding_id"] == "F001"
    assert payload["boundary_id"] == "prep-boundary"
    assert payload["description"] == "prep artifacts exist but state.json remains initialized"
    assert payload["severity"] == "error"
    assert payload["diagnostic_code"] == "AWF249_BOUNDARY_EVIDENCE_STALE"
    assert payload["contract_ref"] == "contracts/prep.json"
    assert payload["evidence_ref"] == "receipts/prep.json"
    assert payload["finding_version"] == "arnold.workflow.semantic_finding.v1"
    assert payload["details"] == {"state_key": "current_state", "expected": "prep_done"}


# ── Separation from SemanticEvidence / SemanticFailure ────────────────────


def test_boundary_types_do_not_extend_semantic_evidence() -> None:
    """BoundaryContract, BoundaryReceipt, AuthorityRecord, SemanticFinding
    must NOT be subclasses of SemanticEvidence or SemanticFailure."""
    from arnold.workflow import semantic_evidence as se
    from arnold.workflow.boundary_evidence import (
        AuthorityRecord,
        BoundaryContract,
        BoundaryReceipt,
        SemanticFinding,
    )

    assert not issubclass(BoundaryContract, se.SemanticEvidence)
    assert not issubclass(BoundaryContract, se.SemanticFailure)
    assert not issubclass(BoundaryReceipt, se.SemanticEvidence)
    assert not issubclass(BoundaryReceipt, se.SemanticFailure)
    assert not issubclass(AuthorityRecord, se.SemanticEvidence)
    assert not issubclass(AuthorityRecord, se.SemanticFailure)
    assert not issubclass(SemanticFinding, se.SemanticEvidence)
    assert not issubclass(SemanticFinding, se.SemanticFailure)


def test_boundary_types_do_not_import_semantic_evidence() -> None:
    """boundary_evidence.py must not import SemanticEvidence or SemanticFailure."""
    from arnold.workflow import boundary_evidence as be

    source_path = Path(be.__file__)
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    imports: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            if node.module == "arnold.workflow.semantic_evidence":
                for alias in node.names:
                    imports.add(alias.name)

    assert "SemanticEvidence" not in imports
    assert "SemanticFailure" not in imports


# ── AWF246-AWF249 diagnostic codes ────────────────────────────────────────


def test_boundary_diagnostic_codes_exist_and_are_classified() -> None:
    """AWF246-AWF249 codes must be present in DiagnosticCode, DiagnosticFamily,
    DIAGNOSTIC_CODE_SPECS, and all derived lookup maps."""
    boundary_codes = [
        DiagnosticCode.BOUNDARY_CONTRACT_MISSING,
        DiagnosticCode.BOUNDARY_EVIDENCE_MISSING,
        DiagnosticCode.BOUNDARY_EVIDENCE_WITHOUT_SOURCE,
        DiagnosticCode.BOUNDARY_EVIDENCE_STALE,
    ]
    for code in boundary_codes:
        assert code in diagnostics.DIAGNOSTIC_SPEC_BY_CODE
        spec = diagnostics.DIAGNOSTIC_SPEC_BY_CODE[code]
        assert spec.code is code
        assert spec.family in DiagnosticFamily.__members__.values()
        assert spec.severity is DiagnosticSeverity.ERROR
        assert spec.message_template
        assert spec.remediation


def test_boundary_codes_flow_through_authoring_diagnostic() -> None:
    """Each AWF246+ code must be usable with AuthoringDiagnostic and survive
    a to_dict() round-trip with the correct code string."""
    from arnold.manifest.refs import SourceSpan

    boundary_codes = [
        DiagnosticCode.BOUNDARY_CONTRACT_MISSING,
        DiagnosticCode.BOUNDARY_EVIDENCE_MISSING,
        DiagnosticCode.BOUNDARY_EVIDENCE_WITHOUT_SOURCE,
        DiagnosticCode.BOUNDARY_EVIDENCE_STALE,
    ]
    for code in boundary_codes:
        diag = diagnostics.AuthoringDiagnostic(
            code=code,
            message=f"test diagnostic for {code.value}",
            source_span=SourceSpan("test.py", 1, 1, 1, 10),
        )
        assert diag.code is code
        payload = diag.to_dict()
        assert payload["code"] == code.value
        assert payload["severity"] == "error"
        assert payload["grammar_version"] == "arnold.workflow.authoring.v2"
        spec = diagnostics.diagnostic_spec(code)
        assert spec.code is code


def test_boundary_code_specs_use_v2_spec_helper() -> None:
    """All AWF246+ specs must be error severity with non-empty message and remediation."""
    boundary_codes = {
        DiagnosticCode.BOUNDARY_CONTRACT_MISSING,
        DiagnosticCode.BOUNDARY_EVIDENCE_MISSING,
        DiagnosticCode.BOUNDARY_EVIDENCE_WITHOUT_SOURCE,
        DiagnosticCode.BOUNDARY_EVIDENCE_STALE,
    }
    for spec in diagnostics.DIAGNOSTIC_CODE_SPECS:
        if spec.code in boundary_codes:
            assert spec.severity is DiagnosticSeverity.ERROR
            assert len(spec.message_template) > 0
            assert len(spec.remediation) > 0


def test_boundary_evidence_module_is_declarative() -> None:
    """boundary_evidence.py must not import forbidden runtime/execution modules."""
    from arnold.workflow import boundary_evidence as be

    source_path = Path(be.__file__)
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    imports: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)

    forbidden_imports = {
        "ast",
        "importlib",
        "arnold.execution",
        "arnold.pipeline.native",
        "arnold.pipeline",
        "arnold.runtime",
        "arnold_pipelines",
        "_pipeline",
        "stages",
    }
    assert imports.isdisjoint(forbidden_imports)


# ── Immutability of details/frozen mappings ───────────────────────────────


def test_boundary_contract_details_is_immutable() -> None:
    """BoundaryContract.details must be a MappingProxyType (immutable)."""
    from arnold.workflow.boundary_evidence import BoundaryContract

    contract = BoundaryContract(
        boundary_id="b1",
        workflow_id="w1",
        details={"key": "value"},
    )
    assert isinstance(contract.details, MappingProxyType)
    with pytest.raises(TypeError):
        contract.details["new"] = "value"  # type: ignore[index]


def test_boundary_receipt_details_is_immutable() -> None:
    """BoundaryReceipt.details must be a MappingProxyType."""
    from arnold.workflow.boundary_evidence import BoundaryReceipt

    receipt = BoundaryReceipt(
        boundary_id="b1",
        workflow_id="w1",
        details={"key": "value"},
    )
    assert isinstance(receipt.details, MappingProxyType)
    with pytest.raises(TypeError):
        receipt.details["new"] = "value"  # type: ignore[index]


def test_authority_record_details_is_immutable() -> None:
    """AuthorityRecord.details must be a MappingProxyType."""
    from arnold.workflow.boundary_evidence import AuthorityRecord

    record = AuthorityRecord(
        actor="a",
        role="r",
        details={"key": "value"},
    )
    assert isinstance(record.details, MappingProxyType)
    with pytest.raises(TypeError):
        record.details["new"] = "value"  # type: ignore[index]


def test_semantic_finding_details_is_immutable() -> None:
    """SemanticFinding.details must be a MappingProxyType."""
    from arnold.workflow.boundary_evidence import SemanticFinding

    finding = SemanticFinding(
        finding_id="F1",
        boundary_id="b1",
        description="desc",
        details={"key": "value"},
    )
    assert isinstance(finding.details, MappingProxyType)
    with pytest.raises(TypeError):
        finding.details["new"] = "value"  # type: ignore[index]
