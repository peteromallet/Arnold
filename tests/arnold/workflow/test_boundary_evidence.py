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
        BoundaryEvidence,
        BoundaryGraph,
        BoundaryOutcome,
        BoundaryPhase,
        BoundaryReceipt,
        EvidenceProfile,
        FindingSeverity,
        SemanticFinding,
        TemplateCompatibility,
        TemplateCompatibilityResult,
        TemporalPolicy,
        check_template_compatibility,
    )
    assert BoundaryPhase.PREP == "prep"
    assert BoundaryPhase.PLAN == "plan"
    assert BoundaryPhase.CRITIQUE == "critique"
    assert BoundaryPhase.GATE == "gate"
    assert BoundaryPhase.REVISE == "revise"
    assert BoundaryOutcome.COMPLETE == "complete"
    assert FindingSeverity.ERROR == "error"
    assert TemplateCompatibility.EXACT_MATCH == "exact_match"
    assert TemplateCompatibility.COMPATIBLE_EXTENSION == "compatible_extension"
    assert TemplateCompatibility.BREAKING_CHANGE == "breaking_change"
    assert TemplateCompatibility.INCOMPATIBLE_RANGE == "incompatible_range"
    assert TemplateCompatibility.DELIBERATE_UPGRADE == "deliberate_upgrade"


def test_boundary_evidence_re_exported_from_workflow_init() -> None:
    """All stable boundary types must be importable from arnold.workflow."""
    from arnold.workflow import (
        AuthorityRecord,
        BoundaryContract,
        BoundaryEvidence,
        BoundaryGraph,
        BoundaryOutcome,
        BoundaryPhase,
        BoundaryReceipt,
        EvidenceProfile,
        FindingSeverity,
        SemanticFinding,
        TemplateCompatibility,
        TemplateCompatibilityResult,
        TemporalPolicy,
    )
    assert BoundaryContract is not None
    assert BoundaryReceipt is not None
    assert AuthorityRecord is not None
    assert SemanticFinding is not None
    assert BoundaryEvidence is not None
    assert BoundaryGraph is not None
    assert EvidenceProfile is not None
    assert TemporalPolicy is not None
    assert TemplateCompatibility is not None
    assert TemplateCompatibilityResult is not None


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
    """BoundaryContract, BoundaryReceipt, AuthorityRecord, SemanticFinding,
    BoundaryEvidence, BoundaryGraph, EvidenceProfile, TemporalPolicy
    must NOT be subclasses of SemanticEvidence or SemanticFailure."""
    from arnold.workflow import semantic_evidence as se
    from arnold.workflow.boundary_evidence import (
        AuthorityRecord,
        BoundaryContract,
        BoundaryEvidence,
        BoundaryGraph,
        BoundaryReceipt,
        EvidenceProfile,
        SemanticFinding,
        TemporalPolicy,
    )

    for cls in (
        BoundaryContract, BoundaryReceipt, AuthorityRecord, SemanticFinding,
        BoundaryEvidence, BoundaryGraph, EvidenceProfile, TemporalPolicy,
    ):
        assert not issubclass(cls, se.SemanticEvidence)
        assert not issubclass(cls, se.SemanticFailure)


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


# ── BoundaryEvidence tests ─────────────────────────────────────────────────


def test_boundary_evidence_constructs_with_required_fields() -> None:
    """BoundaryEvidence must construct with evidence_id, boundary_id, workflow_id."""
    from arnold.workflow.boundary_evidence import BoundaryEvidence

    evidence = BoundaryEvidence(
        evidence_id="ev-001",
        boundary_id="prep-boundary",
        workflow_id="megaplan-review",
    )
    assert evidence.evidence_id == "ev-001"
    assert evidence.boundary_id == "prep-boundary"
    assert evidence.workflow_id == "megaplan-review"
    assert evidence.producer_id is None
    assert evidence.invocation_id is None
    assert evidence.artifact_refs == ()
    assert evidence.artifact_fingerprints == {}
    assert evidence.event_journal_refs == ()
    assert evidence.step_io_envelope_refs == ()
    assert evidence.warrant_capsule_refs == ()
    assert evidence.authority_level is None
    assert evidence.evidence_profile_ref is None
    assert evidence.freshness is None
    assert evidence.observation_time is None
    assert evidence.evidence_version == "arnold.workflow.boundary_evidence.v1"


def test_boundary_evidence_constructs_with_all_fields() -> None:
    """BoundaryEvidence must carry all fields without error."""
    from arnold.workflow.boundary_evidence import BoundaryEvidence

    evidence = BoundaryEvidence(
        evidence_id="ev-full-001",
        boundary_id="gate-boundary",
        workflow_id="megaplan-review",
        producer_id="handler-gate",
        invocation_id="inv-abc-123",
        artifact_refs=("gate_decision.json", "phase_result.json"),
        artifact_fingerprints={"gate_decision.json": "sha256:abc123"},
        event_journal_refs=("journal/gate_entry",),
        step_io_envelope_refs=("envelope/gate_io",),
        warrant_capsule_refs=("warrant/gate_proceed",),
        authority_level="gatekeeper",
        evidence_profile_ref="profiles/gatekeeper.v1",
        freshness="2026-07-13T12:00:00Z",
        observation_time="2026-07-13T12:00:01Z",
        details={"checker_version": "v1"},
    )
    assert evidence.evidence_id == "ev-full-001"
    assert evidence.boundary_id == "gate-boundary"
    assert evidence.workflow_id == "megaplan-review"
    assert evidence.producer_id == "handler-gate"
    assert evidence.invocation_id == "inv-abc-123"
    assert evidence.artifact_refs == ("gate_decision.json", "phase_result.json")
    assert dict(evidence.artifact_fingerprints) == {"gate_decision.json": "sha256:abc123"}
    assert evidence.event_journal_refs == ("journal/gate_entry",)
    assert evidence.step_io_envelope_refs == ("envelope/gate_io",)
    assert evidence.warrant_capsule_refs == ("warrant/gate_proceed",)
    assert evidence.authority_level == "gatekeeper"
    assert evidence.evidence_profile_ref == "profiles/gatekeeper.v1"
    assert evidence.freshness == "2026-07-13T12:00:00Z"
    assert evidence.observation_time == "2026-07-13T12:00:01Z"


def test_boundary_evidence_rejects_empty_evidence_id() -> None:
    """BoundaryEvidence must reject empty evidence_id."""
    from arnold.workflow.boundary_evidence import BoundaryEvidence

    with pytest.raises(ValueError, match="evidence_id"):
        BoundaryEvidence(evidence_id="", boundary_id="b1", workflow_id="w1")


def test_boundary_evidence_rejects_empty_boundary_id() -> None:
    """BoundaryEvidence must reject empty boundary_id."""
    from arnold.workflow.boundary_evidence import BoundaryEvidence

    with pytest.raises(ValueError, match="boundary_id"):
        BoundaryEvidence(evidence_id="ev1", boundary_id="", workflow_id="w1")


def test_boundary_evidence_rejects_empty_workflow_id() -> None:
    """BoundaryEvidence must reject empty workflow_id."""
    from arnold.workflow.boundary_evidence import BoundaryEvidence

    with pytest.raises(ValueError, match="workflow_id"):
        BoundaryEvidence(evidence_id="ev1", boundary_id="b1", workflow_id="")


def test_boundary_evidence_is_frozen() -> None:
    """BoundaryEvidence must be immutable (frozen dataclass)."""
    from arnold.workflow.boundary_evidence import BoundaryEvidence

    evidence = BoundaryEvidence(
        evidence_id="ev1", boundary_id="b1", workflow_id="w1",
    )
    with pytest.raises(FrozenInstanceError):
        evidence.evidence_id = "changed"  # type: ignore[misc]


def test_boundary_evidence_to_dict_round_trip() -> None:
    """BoundaryEvidence.to_dict() must produce a sidecar-safe dict with all fields."""
    from arnold.workflow.boundary_evidence import BoundaryEvidence

    evidence = BoundaryEvidence(
        evidence_id="ev-roundtrip-001",
        boundary_id="prep-boundary",
        workflow_id="megaplan-review",
        producer_id="handler-prep",
        invocation_id="inv-001",
        artifact_refs=("research.md", "brief.md"),
        artifact_fingerprints={"research.md": "sha256:def456"},
        event_journal_refs=("journal/prep_entry",),
        step_io_envelope_refs=("envelope/prep_io",),
        warrant_capsule_refs=("warrant/prep_start",),
        authority_level="planner",
        evidence_profile_ref="profiles/planner.v1",
        freshness="2026-07-13T12:00:00Z",
        observation_time="2026-07-13T12:00:01Z",
        details={"tool": "megaplan"},
    )

    payload = evidence.to_dict()

    assert payload["evidence_id"] == "ev-roundtrip-001"
    assert payload["boundary_id"] == "prep-boundary"
    assert payload["workflow_id"] == "megaplan-review"
    assert payload["producer_id"] == "handler-prep"
    assert payload["invocation_id"] == "inv-001"
    assert payload["artifact_refs"] == ["research.md", "brief.md"]
    assert payload["artifact_fingerprints"] == {"research.md": "sha256:def456"}
    assert payload["event_journal_refs"] == ["journal/prep_entry"]
    assert payload["step_io_envelope_refs"] == ["envelope/prep_io"]
    assert payload["warrant_capsule_refs"] == ["warrant/prep_start"]
    assert payload["authority_level"] == "planner"
    assert payload["evidence_profile_ref"] == "profiles/planner.v1"
    assert payload["freshness"] == "2026-07-13T12:00:00Z"
    assert payload["observation_time"] == "2026-07-13T12:00:01Z"
    assert payload["evidence_version"] == "arnold.workflow.boundary_evidence.v1"
    assert payload["details"] == {"tool": "megaplan"}


def test_boundary_evidence_from_dict_round_trip() -> None:
    """BoundaryEvidence.from_dict() must reconstruct from a minimal serialized dict."""
    from arnold.workflow.boundary_evidence import BoundaryEvidence

    minimal_payload = {
        "evidence_id": "ev-minimal-001",
        "boundary_id": "gate-boundary",
        "workflow_id": "megaplan-review",
    }
    evidence = BoundaryEvidence.from_dict(minimal_payload)
    assert evidence.evidence_id == "ev-minimal-001"
    assert evidence.boundary_id == "gate-boundary"
    assert evidence.workflow_id == "megaplan-review"
    assert evidence.artifact_refs == ()
    assert evidence.details == {}

    # Full round-trip through to_dict -> from_dict
    full_evidence = BoundaryEvidence(
        evidence_id="ev-roundtrip-002",
        boundary_id="prep-boundary",
        workflow_id="megaplan-review",
        producer_id="handler-prep",
        invocation_id="inv-002",
        artifact_refs=("output.json",),
        artifact_fingerprints={"output.json": "sha256:ccc"},
        event_journal_refs=("journal/entry",),
        step_io_envelope_refs=("envelope/step1",),
        warrant_capsule_refs=("warrant/proceed",),
        authority_level="planner",
        evidence_profile_ref="profiles/planner.v1",
        freshness="2026-07-13T12:00:00Z",
        observation_time="2026-07-13T12:00:01Z",
        details={"tool": "megaplan"},
    )
    payload = full_evidence.to_dict()
    reconstructed = BoundaryEvidence.from_dict(payload)
    assert reconstructed.evidence_id == full_evidence.evidence_id
    assert reconstructed.boundary_id == full_evidence.boundary_id
    assert reconstructed.workflow_id == full_evidence.workflow_id
    assert reconstructed.producer_id == full_evidence.producer_id
    assert reconstructed.invocation_id == full_evidence.invocation_id
    assert reconstructed.artifact_refs == full_evidence.artifact_refs
    assert dict(reconstructed.artifact_fingerprints) == dict(full_evidence.artifact_fingerprints)
    assert reconstructed.event_journal_refs == full_evidence.event_journal_refs
    assert reconstructed.step_io_envelope_refs == full_evidence.step_io_envelope_refs
    assert reconstructed.warrant_capsule_refs == full_evidence.warrant_capsule_refs
    assert reconstructed.authority_level == full_evidence.authority_level
    assert reconstructed.evidence_profile_ref == full_evidence.evidence_profile_ref
    assert reconstructed.freshness == full_evidence.freshness
    assert reconstructed.observation_time == full_evidence.observation_time
    assert dict(reconstructed.details) == dict(full_evidence.details)


def test_boundary_evidence_legacy_minimal_payload_readable() -> None:
    """BoundaryEvidence.from_dict() must read a legacy minimal payload
    that contains only the three required fields."""
    from arnold.workflow.boundary_evidence import BoundaryEvidence

    legacy_payload = {
        "evidence_id": "legacy-ev-001",
        "boundary_id": "legacy-boundary",
        "workflow_id": "legacy-workflow",
    }
    evidence = BoundaryEvidence.from_dict(legacy_payload)
    assert evidence.evidence_id == "legacy-ev-001"
    assert evidence.boundary_id == "legacy-boundary"
    assert evidence.workflow_id == "legacy-workflow"
    assert evidence.producer_id is None
    assert evidence.artifact_refs == ()
    assert evidence.artifact_fingerprints == {}
    assert evidence.event_journal_refs == ()
    assert evidence.step_io_envelope_refs == ()
    assert evidence.warrant_capsule_refs == ()
    assert evidence.evidence_version == "arnold.workflow.boundary_evidence.v1"
    assert evidence.details == {}


def test_boundary_evidence_details_is_immutable() -> None:
    """BoundaryEvidence.details must be a MappingProxyType."""
    from arnold.workflow.boundary_evidence import BoundaryEvidence

    evidence = BoundaryEvidence(
        evidence_id="ev1",
        boundary_id="b1",
        workflow_id="w1",
        details={"key": "value"},
    )
    assert isinstance(evidence.details, MappingProxyType)
    with pytest.raises(TypeError):
        evidence.details["new"] = "value"  # type: ignore[index]


def test_boundary_evidence_artifact_fingerprints_is_immutable() -> None:
    """BoundaryEvidence.artifact_fingerprints must be a MappingProxyType."""
    from arnold.workflow.boundary_evidence import BoundaryEvidence

    evidence = BoundaryEvidence(
        evidence_id="ev1",
        boundary_id="b1",
        workflow_id="w1",
        artifact_fingerprints={"a": "sha256:abc"},
    )
    assert isinstance(evidence.artifact_fingerprints, MappingProxyType)
    with pytest.raises(TypeError):
        evidence.artifact_fingerprints["b"] = "sha256:def"  # type: ignore[index]


# ── BoundaryGraph tests ────────────────────────────────────────────────────


def test_boundary_graph_constructs_with_required_fields() -> None:
    """BoundaryGraph must construct with graph_id and boundary_id."""
    from arnold.workflow.boundary_evidence import BoundaryGraph

    graph = BoundaryGraph(
        graph_id="graph-001",
        boundary_id="prep-boundary",
    )
    assert graph.graph_id == "graph-001"
    assert graph.boundary_id == "prep-boundary"
    assert graph.dependencies == ()
    assert graph.joins == ()
    assert graph.fan_out_refs == ()
    assert graph.fan_in_ref is None
    assert graph.cross_workflow_refs == ()
    assert graph.entity_lineage == ()
    assert graph.peer_join_requirements == ()
    assert graph.graph_version == "arnold.workflow.boundary_graph.v1"


def test_boundary_graph_constructs_with_all_fields() -> None:
    """BoundaryGraph must carry all graph-structure fields."""
    from arnold.workflow.boundary_evidence import BoundaryGraph

    graph = BoundaryGraph(
        graph_id="graph-full-001",
        boundary_id="review-boundary",
        dependencies=("prep-boundary", "plan-boundary"),
        joins=("critique-boundary",),
        fan_out_refs=("gate-boundary", "revise-boundary"),
        fan_in_ref="tiebreaker_synthesis",
        cross_workflow_refs=("other-workflow:prep",),
        entity_lineage=("entity-a", "entity-b"),
        peer_join_requirements=("evidence_profile:v1",),
        details={"topology": "dag"},
    )
    assert graph.graph_id == "graph-full-001"
    assert graph.boundary_id == "review-boundary"
    assert graph.dependencies == ("prep-boundary", "plan-boundary")
    assert graph.joins == ("critique-boundary",)
    assert graph.fan_out_refs == ("gate-boundary", "revise-boundary")
    assert graph.fan_in_ref == "tiebreaker_synthesis"
    assert graph.cross_workflow_refs == ("other-workflow:prep",)
    assert graph.entity_lineage == ("entity-a", "entity-b")
    assert graph.peer_join_requirements == ("evidence_profile:v1",)


def test_boundary_graph_rejects_empty_graph_id() -> None:
    """BoundaryGraph must reject empty graph_id."""
    from arnold.workflow.boundary_evidence import BoundaryGraph

    with pytest.raises(ValueError, match="graph_id"):
        BoundaryGraph(graph_id="", boundary_id="b1")


def test_boundary_graph_rejects_empty_boundary_id() -> None:
    """BoundaryGraph must reject empty boundary_id."""
    from arnold.workflow.boundary_evidence import BoundaryGraph

    with pytest.raises(ValueError, match="boundary_id"):
        BoundaryGraph(graph_id="g1", boundary_id="")


def test_boundary_graph_is_frozen() -> None:
    """BoundaryGraph must be immutable."""
    from arnold.workflow.boundary_evidence import BoundaryGraph

    graph = BoundaryGraph(graph_id="g1", boundary_id="b1")
    with pytest.raises(FrozenInstanceError):
        graph.graph_id = "changed"  # type: ignore[misc]


def test_boundary_graph_to_dict_round_trip() -> None:
    """BoundaryGraph.to_dict() must produce a sidecar-safe dict."""
    from arnold.workflow.boundary_evidence import BoundaryGraph

    graph = BoundaryGraph(
        graph_id="graph-rt-001",
        boundary_id="prep-boundary",
        dependencies=("plan-boundary",),
        joins=("critique-boundary",),
        fan_out_refs=("gate-boundary",),
        fan_in_ref="tiebreaker_synthesis",
        cross_workflow_refs=("other:prep",),
        entity_lineage=("entity-a",),
        peer_join_requirements=("profile:v1",),
        details={"topology": "dag"},
    )

    payload = graph.to_dict()

    assert payload["graph_id"] == "graph-rt-001"
    assert payload["boundary_id"] == "prep-boundary"
    assert payload["dependencies"] == ["plan-boundary"]
    assert payload["joins"] == ["critique-boundary"]
    assert payload["fan_out_refs"] == ["gate-boundary"]
    assert payload["fan_in_ref"] == "tiebreaker_synthesis"
    assert payload["cross_workflow_refs"] == ["other:prep"]
    assert payload["entity_lineage"] == ["entity-a"]
    assert payload["peer_join_requirements"] == ["profile:v1"]
    assert payload["graph_version"] == "arnold.workflow.boundary_graph.v1"
    assert payload["details"] == {"topology": "dag"}


def test_boundary_graph_from_dict_round_trip() -> None:
    """BoundaryGraph.from_dict() must reconstruct from a serialized dict."""
    from arnold.workflow.boundary_evidence import BoundaryGraph

    minimal_payload = {
        "graph_id": "graph-min-001",
        "boundary_id": "gate-boundary",
    }
    graph = BoundaryGraph.from_dict(minimal_payload)
    assert graph.graph_id == "graph-min-001"
    assert graph.boundary_id == "gate-boundary"
    assert graph.dependencies == ()
    assert graph.details == {}

    # Full round-trip
    full_graph = BoundaryGraph(
        graph_id="graph-rt-002",
        boundary_id="review-boundary",
        dependencies=("prep-boundary",),
        joins=("critique-boundary",),
        fan_out_refs=("gate-boundary",),
        fan_in_ref="ts",
        cross_workflow_refs=("other:prep",),
        entity_lineage=("e-a",),
        peer_join_requirements=("p:v1",),
        details={"topo": "dag"},
    )
    payload = full_graph.to_dict()
    reconstructed = BoundaryGraph.from_dict(payload)
    assert reconstructed.graph_id == full_graph.graph_id
    assert reconstructed.boundary_id == full_graph.boundary_id
    assert reconstructed.dependencies == full_graph.dependencies
    assert reconstructed.joins == full_graph.joins
    assert reconstructed.fan_out_refs == full_graph.fan_out_refs
    assert reconstructed.fan_in_ref == full_graph.fan_in_ref
    assert reconstructed.cross_workflow_refs == full_graph.cross_workflow_refs
    assert reconstructed.entity_lineage == full_graph.entity_lineage
    assert reconstructed.peer_join_requirements == full_graph.peer_join_requirements
    assert dict(reconstructed.details) == dict(full_graph.details)


def test_boundary_graph_details_is_immutable() -> None:
    """BoundaryGraph.details must be a MappingProxyType."""
    from arnold.workflow.boundary_evidence import BoundaryGraph

    graph = BoundaryGraph(
        graph_id="g1",
        boundary_id="b1",
        details={"key": "value"},
    )
    assert isinstance(graph.details, MappingProxyType)
    with pytest.raises(TypeError):
        graph.details["new"] = "value"  # type: ignore[index]


# ── EvidenceProfile tests ──────────────────────────────────────────────────


def test_evidence_profile_constructs_with_required_fields() -> None:
    """EvidenceProfile must construct with profile_id."""
    from arnold.workflow.boundary_evidence import EvidenceProfile

    profile = EvidenceProfile(profile_id="prof-001")
    assert profile.profile_id == "prof-001"
    assert profile.provenance is None
    assert profile.trust_level is None
    assert profile.source_type is None
    assert profile.source_kind is None
    assert profile.actor_identity is None
    assert profile.tool_version_vector == ()
    assert profile.confidence is None
    assert profile.privacy_class is None
    assert profile.observation_window is None
    assert profile.profile_version == "arnold.workflow.evidence_profile.v1"


def test_evidence_profile_constructs_with_all_fields() -> None:
    """EvidenceProfile must carry all provenance and trust metadata."""
    from arnold.workflow.boundary_evidence import EvidenceProfile

    profile = EvidenceProfile(
        profile_id="prof-full-001",
        provenance="megaplan-handler",
        trust_level="high",
        source_type="handler",
        source_kind="gate",
        actor_identity="gate-handler@megaplan",
        tool_version_vector=("megaplan@1.0.0", "checker@2.0.0"),
        confidence="verified",
        privacy_class="internal",
        observation_window="PT5M",
        details={"region": "us-east-1"},
    )
    assert profile.profile_id == "prof-full-001"
    assert profile.provenance == "megaplan-handler"
    assert profile.trust_level == "high"
    assert profile.source_type == "handler"
    assert profile.source_kind == "gate"
    assert profile.actor_identity == "gate-handler@megaplan"
    assert profile.tool_version_vector == ("megaplan@1.0.0", "checker@2.0.0")
    assert profile.confidence == "verified"
    assert profile.privacy_class == "internal"
    assert profile.observation_window == "PT5M"


def test_evidence_profile_rejects_empty_profile_id() -> None:
    """EvidenceProfile must reject empty profile_id."""
    from arnold.workflow.boundary_evidence import EvidenceProfile

    with pytest.raises(ValueError, match="profile_id"):
        EvidenceProfile(profile_id="")


def test_evidence_profile_is_frozen() -> None:
    """EvidenceProfile must be immutable."""
    from arnold.workflow.boundary_evidence import EvidenceProfile

    profile = EvidenceProfile(profile_id="prof-001")
    with pytest.raises(FrozenInstanceError):
        profile.profile_id = "changed"  # type: ignore[misc]


def test_evidence_profile_to_dict_round_trip() -> None:
    """EvidenceProfile.to_dict() must produce a sidecar-safe dict."""
    from arnold.workflow.boundary_evidence import EvidenceProfile

    profile = EvidenceProfile(
        profile_id="prof-rt-001",
        provenance="megaplan",
        trust_level="medium",
        source_type="handler",
        source_kind="prep",
        actor_identity="prep-handler",
        tool_version_vector=("megaplan@1.0.0",),
        confidence="verified",
        privacy_class="internal",
        observation_window="PT10M",
        details={"region": "us-west-2"},
    )

    payload = profile.to_dict()

    assert payload["profile_id"] == "prof-rt-001"
    assert payload["provenance"] == "megaplan"
    assert payload["trust_level"] == "medium"
    assert payload["source_type"] == "handler"
    assert payload["source_kind"] == "prep"
    assert payload["actor_identity"] == "prep-handler"
    assert payload["tool_version_vector"] == ["megaplan@1.0.0"]
    assert payload["confidence"] == "verified"
    assert payload["privacy_class"] == "internal"
    assert payload["observation_window"] == "PT10M"
    assert payload["profile_version"] == "arnold.workflow.evidence_profile.v1"
    assert payload["details"] == {"region": "us-west-2"}


def test_evidence_profile_from_dict_round_trip() -> None:
    """EvidenceProfile.from_dict() must reconstruct from a serialized dict."""
    from arnold.workflow.boundary_evidence import EvidenceProfile

    minimal_payload = {"profile_id": "prof-min-001"}
    profile = EvidenceProfile.from_dict(minimal_payload)
    assert profile.profile_id == "prof-min-001"
    assert profile.provenance is None
    assert profile.tool_version_vector == ()
    assert profile.details == {}

    # Full round-trip
    full_profile = EvidenceProfile(
        profile_id="prof-rt-002",
        provenance="megaplan",
        trust_level="high",
        source_type="handler",
        source_kind="gate",
        actor_identity="actor@megaplan",
        tool_version_vector=("megaplan@1.0.0",),
        confidence="verified",
        privacy_class="internal",
        observation_window="PT5M",
        details={"region": "us-east-1"},
    )
    payload = full_profile.to_dict()
    reconstructed = EvidenceProfile.from_dict(payload)
    assert reconstructed.profile_id == full_profile.profile_id
    assert reconstructed.provenance == full_profile.provenance
    assert reconstructed.trust_level == full_profile.trust_level
    assert reconstructed.source_type == full_profile.source_type
    assert reconstructed.source_kind == full_profile.source_kind
    assert reconstructed.actor_identity == full_profile.actor_identity
    assert reconstructed.tool_version_vector == full_profile.tool_version_vector
    assert reconstructed.confidence == full_profile.confidence
    assert reconstructed.privacy_class == full_profile.privacy_class
    assert reconstructed.observation_window == full_profile.observation_window
    assert dict(reconstructed.details) == dict(full_profile.details)


def test_evidence_profile_details_is_immutable() -> None:
    """EvidenceProfile.details must be a MappingProxyType."""
    from arnold.workflow.boundary_evidence import EvidenceProfile

    profile = EvidenceProfile(
        profile_id="prof-001",
        details={"key": "value"},
    )
    assert isinstance(profile.details, MappingProxyType)
    with pytest.raises(TypeError):
        profile.details["new"] = "value"  # type: ignore[index]


# ── TemporalPolicy tests ───────────────────────────────────────────────────


def test_temporal_policy_constructs_with_required_fields() -> None:
    """TemporalPolicy must construct with policy_id."""
    from arnold.workflow.boundary_evidence import TemporalPolicy

    policy = TemporalPolicy(policy_id="temp-pol-001")
    assert policy.policy_id == "temp-pol-001"
    assert policy.staleness_duration is None
    assert policy.deadline is None
    assert policy.verification_timeout is None
    assert policy.minimum_observation_duration is None
    assert policy.expiry is None
    assert policy.sunset_renewal is None
    assert policy.policy_version == "arnold.workflow.temporal_policy.v1"


def test_temporal_policy_constructs_with_all_fields() -> None:
    """TemporalPolicy must carry all temporal constraint fields."""
    from arnold.workflow.boundary_evidence import TemporalPolicy

    policy = TemporalPolicy(
        policy_id="temp-pol-full-001",
        staleness_duration="PT1H",
        deadline="2026-07-14T00:00:00Z",
        verification_timeout="PT30S",
        minimum_observation_duration="PT5M",
        expiry="2026-07-20T00:00:00Z",
        sunset_renewal="PT24H",
        details={"strategy": "sliding_window"},
    )
    assert policy.policy_id == "temp-pol-full-001"
    assert policy.staleness_duration == "PT1H"
    assert policy.deadline == "2026-07-14T00:00:00Z"
    assert policy.verification_timeout == "PT30S"
    assert policy.minimum_observation_duration == "PT5M"
    assert policy.expiry == "2026-07-20T00:00:00Z"
    assert policy.sunset_renewal == "PT24H"


def test_temporal_policy_rejects_empty_policy_id() -> None:
    """TemporalPolicy must reject empty policy_id."""
    from arnold.workflow.boundary_evidence import TemporalPolicy

    with pytest.raises(ValueError, match="policy_id"):
        TemporalPolicy(policy_id="")


def test_temporal_policy_is_frozen() -> None:
    """TemporalPolicy must be immutable."""
    from arnold.workflow.boundary_evidence import TemporalPolicy

    policy = TemporalPolicy(policy_id="tp1")
    with pytest.raises(FrozenInstanceError):
        policy.policy_id = "changed"  # type: ignore[misc]


def test_temporal_policy_to_dict_round_trip() -> None:
    """TemporalPolicy.to_dict() must produce a sidecar-safe dict."""
    from arnold.workflow.boundary_evidence import TemporalPolicy

    policy = TemporalPolicy(
        policy_id="temp-pol-rt-001",
        staleness_duration="PT1H",
        deadline="2026-07-14T00:00:00Z",
        verification_timeout="PT30S",
        minimum_observation_duration="PT5M",
        expiry="2026-07-20T00:00:00Z",
        sunset_renewal="PT24H",
        details={"strategy": "sliding_window"},
    )

    payload = policy.to_dict()

    assert payload["policy_id"] == "temp-pol-rt-001"
    assert payload["staleness_duration"] == "PT1H"
    assert payload["deadline"] == "2026-07-14T00:00:00Z"
    assert payload["verification_timeout"] == "PT30S"
    assert payload["minimum_observation_duration"] == "PT5M"
    assert payload["expiry"] == "2026-07-20T00:00:00Z"
    assert payload["sunset_renewal"] == "PT24H"
    assert payload["policy_version"] == "arnold.workflow.temporal_policy.v1"
    assert payload["details"] == {"strategy": "sliding_window"}


def test_temporal_policy_from_dict_round_trip() -> None:
    """TemporalPolicy.from_dict() must reconstruct from a serialized dict."""
    from arnold.workflow.boundary_evidence import TemporalPolicy

    minimal_payload = {"policy_id": "temp-pol-min-001"}
    policy = TemporalPolicy.from_dict(minimal_payload)
    assert policy.policy_id == "temp-pol-min-001"
    assert policy.staleness_duration is None
    assert policy.deadline is None
    assert policy.details == {}

    # Full round-trip
    full_policy = TemporalPolicy(
        policy_id="temp-pol-rt-002",
        staleness_duration="PT2H",
        deadline="2026-07-15T00:00:00Z",
        verification_timeout="PT60S",
        minimum_observation_duration="PT10M",
        expiry="2026-07-21T00:00:00Z",
        sunset_renewal="PT48H",
        details={"strategy": "fixed"},
    )
    payload = full_policy.to_dict()
    reconstructed = TemporalPolicy.from_dict(payload)
    assert reconstructed.policy_id == full_policy.policy_id
    assert reconstructed.staleness_duration == full_policy.staleness_duration
    assert reconstructed.deadline == full_policy.deadline
    assert reconstructed.verification_timeout == full_policy.verification_timeout
    assert reconstructed.minimum_observation_duration == full_policy.minimum_observation_duration
    assert reconstructed.expiry == full_policy.expiry
    assert reconstructed.sunset_renewal == full_policy.sunset_renewal
    assert dict(reconstructed.details) == dict(full_policy.details)


def test_temporal_policy_details_is_immutable() -> None:
    """TemporalPolicy.details must be a MappingProxyType."""
    from arnold.workflow.boundary_evidence import TemporalPolicy

    policy = TemporalPolicy(
        policy_id="tp1",
        details={"key": "value"},
    )
    assert isinstance(policy.details, MappingProxyType)
    with pytest.raises(TypeError):
        policy.details["new"] = "value"  # type: ignore[index]


# ── TemplateCompatibilityResult tests ──────────────────────────────────────


def test_template_compatibility_result_constructs() -> None:
    """TemplateCompatibilityResult must construct with compatibility field."""
    from arnold.workflow.boundary_evidence import (
        TemplateCompatibility,
        TemplateCompatibilityResult,
    )

    result = TemplateCompatibilityResult(
        compatibility=TemplateCompatibility.EXACT_MATCH,
        template_id="tpl-001",
        from_version="v1",
        to_version="v1",
    )
    assert result.compatibility is TemplateCompatibility.EXACT_MATCH
    assert result.template_id == "tpl-001"
    assert result.from_version == "v1"
    assert result.to_version == "v1"
    assert result.added_optional_fields == ()
    assert result.removed_required_fields == ()
    assert result.changed_required_fields == ()


def test_template_compatibility_result_is_frozen() -> None:
    """TemplateCompatibilityResult must be immutable."""
    from arnold.workflow.boundary_evidence import (
        TemplateCompatibility,
        TemplateCompatibilityResult,
    )

    result = TemplateCompatibilityResult(
        compatibility=TemplateCompatibility.EXACT_MATCH,
    )
    with pytest.raises(FrozenInstanceError):
        result.compatibility = TemplateCompatibility.BREAKING_CHANGE  # type: ignore[misc]


def test_template_compatibility_result_to_dict_round_trip() -> None:
    """TemplateCompatibilityResult.to_dict() must produce a serializable dict."""
    from arnold.workflow.boundary_evidence import (
        TemplateCompatibility,
        TemplateCompatibilityResult,
    )

    result = TemplateCompatibilityResult(
        compatibility=TemplateCompatibility.COMPATIBLE_EXTENSION,
        added_optional_fields=("new_field",),
        template_id="tpl-001",
        from_version="v1",
        to_version="v2",
        details={"note": "added optional field"},
    )

    payload = result.to_dict()

    assert payload["compatibility"] == "compatible_extension"
    assert payload["added_optional_fields"] == ["new_field"]
    assert payload["template_id"] == "tpl-001"
    assert payload["from_version"] == "v1"
    assert payload["to_version"] == "v2"
    assert payload["details"] == {"note": "added optional field"}
    assert "removed_required_fields" not in payload
    assert "changed_required_fields" not in payload


def test_template_compatibility_result_breaking_to_dict() -> None:
    """TemplateCompatibilityResult for BREAKING_CHANGE must serialize removed/changed fields."""
    from arnold.workflow.boundary_evidence import (
        TemplateCompatibility,
        TemplateCompatibilityResult,
    )

    result = TemplateCompatibilityResult(
        compatibility=TemplateCompatibility.BREAKING_CHANGE,
        removed_required_fields=("old_required", "tightened_optional"),
        added_optional_fields=("new_optional",),
        template_id="tpl-001",
        from_version="v1",
        to_version="v2",
    )

    payload = result.to_dict()

    assert payload["compatibility"] == "breaking_change"
    assert payload["removed_required_fields"] == ["old_required", "tightened_optional"]
    assert payload["added_optional_fields"] == ["new_optional"]


def test_template_compatibility_result_details_is_immutable() -> None:
    """TemplateCompatibilityResult.details must be a MappingProxyType."""
    from arnold.workflow.boundary_evidence import (
        TemplateCompatibility,
        TemplateCompatibilityResult,
    )

    result = TemplateCompatibilityResult(
        compatibility=TemplateCompatibility.EXACT_MATCH,
        details={"key": "value"},
    )
    assert isinstance(result.details, MappingProxyType)
    with pytest.raises(TypeError):
        result.details["new"] = "value"  # type: ignore[index]


# ── check_template_compatibility tests ─────────────────────────────────────


def test_check_template_compatibility_exact_match() -> None:
    """check_template_compatibility must return EXACT_MATCH when field sets are identical."""
    from arnold.workflow.boundary_evidence import (
        TemplateCompatibility,
        check_template_compatibility,
    )

    required = frozenset({"a", "b"})
    optional = frozenset({"c"})

    result = check_template_compatibility(
        template_id="tpl-001",
        from_required_fields=required,
        from_optional_fields=optional,
        to_required_fields=required,
        to_optional_fields=optional,
        from_version="v1",
        to_version="v1",
    )

    assert result.compatibility is TemplateCompatibility.EXACT_MATCH
    assert result.template_id == "tpl-001"
    assert result.from_version == "v1"
    assert result.to_version == "v1"
    assert result.added_optional_fields == ()
    assert result.removed_required_fields == ()
    assert result.changed_required_fields == ()


def test_check_template_compatibility_compatible_extension() -> None:
    """check_template_compatibility must return COMPATIBLE_EXTENSION when
    only optional fields are added."""
    from arnold.workflow.boundary_evidence import (
        TemplateCompatibility,
        check_template_compatibility,
    )

    from_required = frozenset({"a", "b"})
    from_optional = frozenset({"c"})
    to_required = frozenset({"a", "b"})
    to_optional = frozenset({"c", "d", "e"})

    result = check_template_compatibility(
        template_id="tpl-001",
        from_required_fields=from_required,
        from_optional_fields=from_optional,
        to_required_fields=to_required,
        to_optional_fields=to_optional,
    )

    assert result.compatibility is TemplateCompatibility.COMPATIBLE_EXTENSION
    assert set(result.added_optional_fields) == {"d", "e"}
    assert result.removed_required_fields == ()
    assert result.changed_required_fields == ()


def test_check_template_compatibility_breaking_removed_required() -> None:
    """check_template_compatibility must return BREAKING_CHANGE when a
    required field is removed."""
    from arnold.workflow.boundary_evidence import (
        TemplateCompatibility,
        check_template_compatibility,
    )

    from_required = frozenset({"a", "b", "c"})
    from_optional = frozenset()
    to_required = frozenset({"a", "b"})
    to_optional = frozenset()

    result = check_template_compatibility(
        template_id="tpl-001",
        from_required_fields=from_required,
        from_optional_fields=from_optional,
        to_required_fields=to_required,
        to_optional_fields=to_optional,
    )

    assert result.compatibility is TemplateCompatibility.BREAKING_CHANGE
    assert "c" in result.removed_required_fields


def test_check_template_compatibility_breaking_optional_to_required() -> None:
    """check_template_compatibility must return BREAKING_CHANGE when an
    optional field becomes required."""
    from arnold.workflow.boundary_evidence import (
        TemplateCompatibility,
        check_template_compatibility,
    )

    from_required = frozenset({"a"})
    from_optional = frozenset({"b"})
    to_required = frozenset({"a", "b"})
    to_optional = frozenset()

    result = check_template_compatibility(
        template_id="tpl-001",
        from_required_fields=from_required,
        from_optional_fields=from_optional,
        to_required_fields=to_required,
        to_optional_fields=to_optional,
    )

    assert result.compatibility is TemplateCompatibility.BREAKING_CHANGE
    assert "b" in result.removed_required_fields


def test_check_template_compatibility_breaking_newly_added_required() -> None:
    """check_template_compatibility must return BREAKING_CHANGE when a
    brand-new required field is added that was neither previously required
    nor optional."""
    from arnold.workflow.boundary_evidence import (
        TemplateCompatibility,
        check_template_compatibility,
    )

    from_required = frozenset({"a"})
    from_optional = frozenset({"b"})
    to_required = frozenset({"a", "c"})
    to_optional = frozenset({"b"})

    result = check_template_compatibility(
        template_id="tpl-001",
        from_required_fields=from_required,
        from_optional_fields=from_optional,
        to_required_fields=to_required,
        to_optional_fields=to_optional,
    )

    assert result.compatibility is TemplateCompatibility.BREAKING_CHANGE
    assert "c" in result.changed_required_fields
    assert result.removed_required_fields == ()


def test_check_template_compatibility_incompatible_range() -> None:
    """check_template_compatibility must return INCOMPATIBLE_RANGE when
    optional fields are removed but required fields are unchanged
    (neither a compatible extension nor a straightforward breaking change)."""
    from arnold.workflow.boundary_evidence import (
        TemplateCompatibility,
        check_template_compatibility,
    )

    # Required fields identical; only optional fields removed (no additions)
    from_required = frozenset({"a"})
    from_optional = frozenset({"b", "c"})
    to_required = frozenset({"a"})
    to_optional = frozenset({"b"})

    result = check_template_compatibility(
        template_id="tpl-001",
        from_required_fields=from_required,
        from_optional_fields=from_optional,
        to_required_fields=to_required,
        to_optional_fields=to_optional,
    )

    assert result.compatibility is TemplateCompatibility.INCOMPATIBLE_RANGE


def test_check_template_compatibility_without_versions() -> None:
    """check_template_compatibility must work without version strings."""
    from arnold.workflow.boundary_evidence import (
        TemplateCompatibility,
        check_template_compatibility,
    )

    required = frozenset({"a"})
    optional = frozenset()

    result = check_template_compatibility(
        template_id="tpl-001",
        from_required_fields=required,
        from_optional_fields=optional,
        to_required_fields=required,
        to_optional_fields=optional,
    )

    assert result.compatibility is TemplateCompatibility.EXACT_MATCH
    assert result.from_version is None
    assert result.to_version is None
