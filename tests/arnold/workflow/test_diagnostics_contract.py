from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError
from pathlib import Path
from types import MappingProxyType

import pytest

from arnold.manifest.refs import ImportRef, SourceSpan
from arnold.workflow import diagnostics


def test_diagnostic_contract_exposes_grammar_and_import_metadata() -> None:
    assert diagnostics.GRAMMAR_METADATA == {
        "grammar_version": "arnold.workflow.authoring.v2",
        "source_kind": "python-shaped-workflow",
        "module": "arnold.workflow.authoring",
    }
    assert isinstance(diagnostics.GRAMMAR_METADATA, MappingProxyType)
    assert diagnostics.AUTHORING_INTRINSIC_MODULE == "arnold.workflow.authoring"
    assert diagnostics.ALLOWED_FUTURE_IMPORTS == ("annotations",)
    assert diagnostics.RESERVED_AUTHORING_INTRINSICS == (
        "workflow",
        "loop",
        "halt",
        "suspend",
        "transition",
    )
    assert diagnostics.RESERVED_AUTHORING_STEP_CALL_KEYWORDS == (
        "id",
        "policy",
        "policies",
        "schema",
    )
    assert diagnostics.RESERVED_AUTHORING_INTRINSIC_CALL_KEYWORDS == {
        "loop": ("policy", "reentry_id"),
        "halt": ("id", "trigger_ref", "target_ref", "payload_schema_hash", "policy_ref"),
        "suspend": (
            "route_id",
            "capability_id",
            "reentry_id",
            "payload_schema_hash",
            "resume_schema_hash",
            "resume_schema_ref",
            "resume_payload_ref",
        ),
        "transition": (
            "id",
            "type",
            "trigger_ref",
            "target_ref",
            "payload_schema_hash",
            "policy_ref",
        ),
    }
    assert diagnostics.ALLOWED_IMPORT_FORMS == (
        diagnostics.ImportForm.FUTURE_ANNOTATIONS,
        diagnostics.ImportForm.AUTHORING_INTRINSIC,
        diagnostics.ImportForm.COMPONENT_ABSOLUTE,
        diagnostics.ImportForm.COMPONENT_RELATIVE,
        diagnostics.ImportForm.COMPONENT_ALIAS,
    )


def test_diagnostic_codes_are_unique_and_cover_required_families() -> None:
    specs = diagnostics.DIAGNOSTIC_CODE_SPECS
    codes = [spec.code for spec in specs]
    families = {spec.family for spec in specs}

    assert len(codes) == len(set(codes))
    assert set(diagnostics.DiagnosticFamily) == families
    assert set(diagnostics.DIAGNOSTIC_CODE_BY_FAMILY) == set(diagnostics.DiagnosticFamily)
    assert set(diagnostics.DIAGNOSTIC_SPEC_BY_CODE) == set(diagnostics.DiagnosticCode)
    assert all(spec.severity is diagnostics.DiagnosticSeverity.ERROR for spec in specs)
    assert all(spec.message_template for spec in specs)
    assert all(spec.remediation for spec in specs)
    assert diagnostics.DiagnosticCode.MANUAL_GRAPH_NODES in codes
    assert diagnostics.DiagnosticCode.COMPOSITION_EFFECT_SCHEMA_MISMATCH in codes


def test_diagnostic_dataclass_carries_stable_shape() -> None:
    diagnostic = diagnostics.AuthoringDiagnostic(
        code=diagnostics.DiagnosticCode.INVALID_IMPORT_SOURCE,
        message="legacy imports are rejected",
        source_span=SourceSpan("workflow.py", 3, 1, 3, 42),
        import_ref=ImportRef("example.workflow.steps", "plan"),
        component_ref="example.workflow.steps:plan",
        call_site_path="review/plan",
        invocable_id="review-plan",
        policy_category="retry",
        rejection_category="manual_graph_nodes",
        remediation="import a typed authoring component",
        details={"local_name": "plan", "aliases": ["planner"]},
    )

    assert diagnostic.grammar_version == "arnold.workflow.authoring.v2"
    assert diagnostic.severity is diagnostics.DiagnosticSeverity.ERROR
    assert diagnostic.source_span == SourceSpan("workflow.py", 3, 1, 3, 42)
    assert diagnostic.import_ref == ImportRef("example.workflow.steps", "plan")
    assert diagnostic.component_ref == "example.workflow.steps:plan"
    assert diagnostic.call_site_path == "review/plan"
    assert diagnostic.invocable_id == "review-plan"
    assert diagnostic.policy_category == "retry"
    assert diagnostic.rejection_category == "manual_graph_nodes"
    assert diagnostic.details["aliases"] == ("planner",)
    assert isinstance(diagnostic.details, MappingProxyType)
    with pytest.raises(TypeError):
        diagnostic.details["new"] = "value"  # type: ignore[index]
    with pytest.raises(FrozenInstanceError):
        diagnostic.message = "changed"  # type: ignore[misc]


def test_diagnostic_source_span_serializes_with_required_coordinates() -> None:
    diagnostic = diagnostics.AuthoringDiagnostic(
        code=diagnostics.DiagnosticCode.MISSING_CALL_SITE_ID,
        message="missing call-site id",
        source_span=SourceSpan("workflow.py", 7, 5, 7, 19),
        call_site_path="review",
        invocable_id="review-subflow",
        rejection_category="missing_call_site_id",
        details={"keyword": "policy"},
    )

    payload = diagnostic.to_dict()

    assert payload["code"] == "AWF220_MISSING_CALL_SITE_ID"
    assert payload["severity"] == "error"
    assert payload["grammar_version"] == "arnold.workflow.authoring.v2"
    assert payload["source_span"] == {
        "path": "workflow.py",
        "start_line": 7,
        "start_column": 5,
        "end_line": 7,
        "end_column": 19,
    }
    assert payload["call_site_path"] == "review"
    assert payload["invocable_id"] == "review-subflow"
    assert payload["rejection_category"] == "missing_call_site_id"
    assert payload["details"] == {"keyword": "policy"}


def test_diagnostic_dataclass_rejects_malformed_required_fields() -> None:
    with pytest.raises(ValueError, match="message"):
        diagnostics.AuthoringDiagnostic(
            code=diagnostics.DiagnosticCode.UNSUPPORTED_SYNTAX,
            message="",
        )

    with pytest.raises(ValueError, match="grammar_version"):
        diagnostics.AuthoringDiagnostic(
            code=diagnostics.DiagnosticCode.UNSUPPORTED_SYNTAX,
            message="bad grammar",
            grammar_version="other",
        )

    with pytest.raises(ValueError, match="component_ref"):
        diagnostics.AuthoringDiagnostic(
            code=diagnostics.DiagnosticCode.UNKNOWN_COMPONENT,
            message="unknown component",
            component_ref="",
        )

    with pytest.raises(ValueError, match="call_site_path"):
        diagnostics.AuthoringDiagnostic(
            code=diagnostics.DiagnosticCode.MISSING_CALL_SITE_ID,
            message="missing id",
            call_site_path="",
        )


def test_runtime_ref_can_be_serialized_in_diagnostic_details() -> None:
    from arnold.workflow import RuntimeRef

    ref = RuntimeRef(
        node_id="plan",
        output="draft",
        dependencies=("research.note",),
        fallback_route="fallback.draft",
        metadata={"schema_hash": "sha256:" + "a" * 64},
    )
    diagnostic = diagnostics.AuthoringDiagnostic(
        code=diagnostics.DiagnosticCode.UNSUPPORTED_MUTATION,
        message="runtime ref used in unsupported control flow",
        details={"runtime_ref": ref, "reason": "truthiness"},
    )

    payload = diagnostic.to_dict()
    assert payload["details"]["runtime_ref"].identity == "plan.draft"
    assert payload["details"]["runtime_ref"].dependencies == ("research.note",)
    assert payload["details"]["reason"] == "truthiness"


def test_diagnostics_module_is_declarative_and_static_only() -> None:
    source_path = Path(diagnostics.__file__)
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    imports: set[str] = set()
    function_names: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
        elif isinstance(node, ast.FunctionDef):
            function_names.add(node.name)

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
    assert not any(name.startswith(("parse", "validate", "resolve")) for name in function_names)
    assert not any(name.startswith(("render", "format")) for name in function_names)
    assert "cli" not in source_path.read_text(encoding="utf-8").lower()


# ── AWF240+ Megaplan semantic diagnostics ──────────────────────────────────


def test_megaplan_semantic_codes_exist_and_are_classified() -> None:
    """AWF240-AWF245 codes must be present in DiagnosticCode, DiagnosticFamily,
    DIAGNOSTIC_CODE_SPECS, and all derived lookup maps."""
    new_codes = [
        diagnostics.DiagnosticCode.UNRESOLVED_CALLEE_PROVENANCE,
        diagnostics.DiagnosticCode.BRANCH_VOCABULARY_MISMATCH,
        diagnostics.DiagnosticCode.RAW_STRING_ROUTE_BRANCH,
        diagnostics.DiagnosticCode.LOWERED_TOPOLOGY_DISCARD,
        diagnostics.DiagnosticCode.HANDLER_PURITY_VIOLATION,
        diagnostics.DiagnosticCode.ROW_EVIDENCE_INSUFFICIENCY,
    ]
    for code in new_codes:
        assert code in diagnostics.DIAGNOSTIC_SPEC_BY_CODE
        spec = diagnostics.DIAGNOSTIC_SPEC_BY_CODE[code]
        assert spec.code is code
        assert spec.family in diagnostics.DiagnosticFamily.__members__.values()
        assert spec.severity is diagnostics.DiagnosticSeverity.ERROR
        assert spec.message_template
        assert spec.remediation


def test_megaplan_codes_flow_through_authoring_diagnostic() -> None:
    """Each AWF240+ code must be usable with AuthoringDiagnostic and survive
    a to_dict() round-trip with the correct code string."""
    megaplan_codes = [
        diagnostics.DiagnosticCode.UNRESOLVED_CALLEE_PROVENANCE,
        diagnostics.DiagnosticCode.BRANCH_VOCABULARY_MISMATCH,
        diagnostics.DiagnosticCode.RAW_STRING_ROUTE_BRANCH,
        diagnostics.DiagnosticCode.LOWERED_TOPOLOGY_DISCARD,
        diagnostics.DiagnosticCode.HANDLER_PURITY_VIOLATION,
        diagnostics.DiagnosticCode.ROW_EVIDENCE_INSUFFICIENCY,
    ]
    for code in megaplan_codes:
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
        # Verify round-trip lookup
        spec = diagnostics.diagnostic_spec(code)
        assert spec.code is code


def test_megaplan_code_specs_use_v2_spec_helper() -> None:
    """All AWF240+ specs must be error severity with non-empty message and remediation."""
    megaplan_codes = {
        diagnostics.DiagnosticCode.UNRESOLVED_CALLEE_PROVENANCE,
        diagnostics.DiagnosticCode.BRANCH_VOCABULARY_MISMATCH,
        diagnostics.DiagnosticCode.RAW_STRING_ROUTE_BRANCH,
        diagnostics.DiagnosticCode.LOWERED_TOPOLOGY_DISCARD,
        diagnostics.DiagnosticCode.HANDLER_PURITY_VIOLATION,
        diagnostics.DiagnosticCode.ROW_EVIDENCE_INSUFFICIENCY,
    }
    for spec in diagnostics.DIAGNOSTIC_CODE_SPECS:
        if spec.code in megaplan_codes:
            assert spec.severity is diagnostics.DiagnosticSeverity.ERROR
            assert len(spec.message_template) > 0
            assert len(spec.remediation) > 0


# ── AWF246+ S2.5 boundary evidence diagnostics ──────────────────────────────


def test_boundary_evidence_codes_exist_and_are_classified() -> None:
    """AWF246-AWF249 codes must be present in DiagnosticCode, DiagnosticFamily,
    DIAGNOSTIC_CODE_SPECS, and all derived lookup maps."""
    boundary_codes = [
        diagnostics.DiagnosticCode.BOUNDARY_CONTRACT_MISSING,
        diagnostics.DiagnosticCode.BOUNDARY_EVIDENCE_MISSING,
        diagnostics.DiagnosticCode.BOUNDARY_EVIDENCE_WITHOUT_SOURCE,
        diagnostics.DiagnosticCode.BOUNDARY_EVIDENCE_STALE,
    ]
    for code in boundary_codes:
        assert code in diagnostics.DIAGNOSTIC_SPEC_BY_CODE, f"{code.value} missing from DIAGNOSTIC_SPEC_BY_CODE"
        spec = diagnostics.DIAGNOSTIC_SPEC_BY_CODE[code]
        assert spec.code is code
        assert spec.family in diagnostics.DiagnosticFamily.__members__.values()
        assert spec.severity is diagnostics.DiagnosticSeverity.ERROR
        assert spec.message_template, f"{code.value} missing message_template"
        assert spec.remediation, f"{code.value} missing remediation"


def test_boundary_evidence_codes_flow_through_authoring_diagnostic() -> None:
    """Each AWF246+ code must be usable with AuthoringDiagnostic and survive
    a to_dict() round-trip with the correct code string."""
    boundary_codes = [
        diagnostics.DiagnosticCode.BOUNDARY_CONTRACT_MISSING,
        diagnostics.DiagnosticCode.BOUNDARY_EVIDENCE_MISSING,
        diagnostics.DiagnosticCode.BOUNDARY_EVIDENCE_WITHOUT_SOURCE,
        diagnostics.DiagnosticCode.BOUNDARY_EVIDENCE_STALE,
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
        # Verify round-trip lookup
        spec = diagnostics.diagnostic_spec(code)
        assert spec.code is code


def test_boundary_evidence_code_specs_use_v2_spec_helper() -> None:
    """All AWF246+ specs must be error severity with non-empty message and remediation."""
    boundary_codes = {
        diagnostics.DiagnosticCode.BOUNDARY_CONTRACT_MISSING,
        diagnostics.DiagnosticCode.BOUNDARY_EVIDENCE_MISSING,
        diagnostics.DiagnosticCode.BOUNDARY_EVIDENCE_WITHOUT_SOURCE,
        diagnostics.DiagnosticCode.BOUNDARY_EVIDENCE_STALE,
    }
    for spec in diagnostics.DIAGNOSTIC_CODE_SPECS:
        if spec.code in boundary_codes:
            assert spec.severity is diagnostics.DiagnosticSeverity.ERROR
            assert len(spec.message_template) > 0
            assert len(spec.remediation) > 0


def test_boundary_evidence_diagnostic_families_match_codes() -> None:
    """AWF246-AWF249 DiagnosticFamily members must map back to the correct
    DiagnosticCode via DIAGNOSTIC_CODE_BY_FAMILY."""
    family_to_expected_code = {
        diagnostics.DiagnosticFamily.BOUNDARY_CONTRACT_MISSING: diagnostics.DiagnosticCode.BOUNDARY_CONTRACT_MISSING,
        diagnostics.DiagnosticFamily.BOUNDARY_EVIDENCE_MISSING: diagnostics.DiagnosticCode.BOUNDARY_EVIDENCE_MISSING,
        diagnostics.DiagnosticFamily.BOUNDARY_EVIDENCE_WITHOUT_SOURCE: diagnostics.DiagnosticCode.BOUNDARY_EVIDENCE_WITHOUT_SOURCE,
        diagnostics.DiagnosticFamily.BOUNDARY_EVIDENCE_STALE: diagnostics.DiagnosticCode.BOUNDARY_EVIDENCE_STALE,
    }
    for family, expected_code in family_to_expected_code.items():
        assert diagnostics.DIAGNOSTIC_CODE_BY_FAMILY[family] is expected_code


# ── Semantic evidence carrier tests ────────────────────────────────────────


def test_semantic_evidence_importable_and_stable() -> None:
    """semantic_evidence module must be importable with all public symbols present."""
    from arnold.workflow.semantic_evidence import (
        CompatibilityQuarantineCategory,
        CompatibilityQuarantineEntry,
        ConstructType,
        SemanticEvidence,
        SemanticFailure,
    )
    assert ConstructType.HANDLER_FUNCTION == "handler_function"
    assert ConstructType.ROUTE_BRANCH == "route_branch"
    assert CompatibilityQuarantineCategory.MANIFEST_SERIALIZATION == "manifest_serialization"


def test_semantic_evidence_constructs_with_required_fields() -> None:
    """SemanticEvidence must construct with diagnostic_code and carry all optional
    carrier fields: source_span, construct_type, row_id, checker_version, and
    compatibility_quarantine."""
    from arnold.workflow.semantic_evidence import (
        CompatibilityQuarantineCategory,
        CompatibilityQuarantineEntry,
        ConstructType,
        SemanticEvidence,
    )

    evidence = SemanticEvidence(
        diagnostic_code=diagnostics.DiagnosticCode.RAW_STRING_ROUTE_BRANCH,
        source_span=SourceSpan("workflow.pypeline", 42, 5, 42, 38),
        construct_type=ConstructType.ROUTE_BRANCH,
        row_id="raw-string-route-branch",
        checker_version="arnold.workflow.semantic_evidence.v1",
        compatibility_quarantine=(
            CompatibilityQuarantineEntry(
                category=CompatibilityQuarantineCategory.ROUTE_DISPATCH_LEGACY,
                adapter_location="arnold_pipelines/megaplan/route_dispatch.py:_to_label",
                enum_type="GateOutcome",
                note="serialized for manifest backend compatibility",
            ),
        ),
        details={"branch_literal": "proceed", "expected_enum": "GateOutcome.PROCEED"},
    )

    assert evidence.diagnostic_code is diagnostics.DiagnosticCode.RAW_STRING_ROUTE_BRANCH
    assert evidence.source_span == SourceSpan("workflow.pypeline", 42, 5, 42, 38)
    assert evidence.construct_type is ConstructType.ROUTE_BRANCH
    assert evidence.row_id == "raw-string-route-branch"
    assert evidence.checker_version == "arnold.workflow.semantic_evidence.v1"
    assert len(evidence.compatibility_quarantine) == 1
    assert evidence.compatibility_quarantine[0].category is CompatibilityQuarantineCategory.ROUTE_DISPATCH_LEGACY
    assert evidence.compatibility_quarantine[0].adapter_location == "arnold_pipelines/megaplan/route_dispatch.py:_to_label"
    assert evidence.compatibility_quarantine[0].enum_type == "GateOutcome"


def test_semantic_evidence_to_dict_round_trip() -> None:
    """SemanticEvidence.to_dict() must produce a sidecar-safe dict with all
    required carrier fields preserved."""
    from arnold.workflow.semantic_evidence import (
        CompatibilityQuarantineCategory,
        CompatibilityQuarantineEntry,
        ConstructType,
        SemanticEvidence,
    )

    evidence = SemanticEvidence(
        diagnostic_code=diagnostics.DiagnosticCode.HANDLER_PURITY_VIOLATION,
        source_span=SourceSpan("handlers/gate.py", 100, 1, 100, 25),
        construct_type=ConstructType.HANDLER_FUNCTION,
        row_id="gate-handler-purity",
        compatibility_quarantine=(
            CompatibilityQuarantineEntry(
                category=CompatibilityQuarantineCategory.MANIFEST_SERIALIZATION,
                adapter_location="arnold_pipelines/megaplan/_compatibility.py:gate_to_label",
                enum_type="GateOutcome",
            ),
        ),
        details={"handler": "handle_gate", "routing_calls": ["workflow_transition"]},
    )

    payload = evidence.to_dict()

    assert payload["diagnostic_code"] == "AWF244_HANDLER_PURITY_VIOLATION"
    assert payload["checker_version"] == "arnold.workflow.semantic_evidence.v1"
    assert payload["source_span"] == {
        "path": "handlers/gate.py",
        "start_line": 100,
        "start_column": 1,
        "end_line": 100,
        "end_column": 25,
    }
    assert payload["construct_type"] == "handler_function"
    assert payload["row_id"] == "gate-handler-purity"
    assert len(payload["compatibility_quarantine"]) == 1
    assert payload["compatibility_quarantine"][0]["category"] == "manifest_serialization"
    assert payload["details"]["handler"] == "handle_gate"


def test_semantic_failure_requires_at_least_one_evidence() -> None:
    """SemanticFailure must reject construction with empty evidence."""
    from arnold.workflow.semantic_evidence import SemanticFailure

    with pytest.raises(ValueError, match="at least one"):
        SemanticFailure(evidence=())


def test_semantic_failure_carries_evidence_and_optional_code() -> None:
    """SemanticFailure must aggregate multiple SemanticEvidence records and
    carry an optional AuthoringDiagnostic code for integration."""
    from arnold.workflow.semantic_evidence import (
        ConstructType,
        SemanticEvidence,
        SemanticFailure,
    )

    failure = SemanticFailure(
        evidence=(
            SemanticEvidence(
                diagnostic_code=diagnostics.DiagnosticCode.UNRESOLVED_CALLEE_PROVENANCE,
                construct_type=ConstructType.HANDLER_FUNCTION,
                row_id="unresolved-handler",
            ),
            SemanticEvidence(
                diagnostic_code=diagnostics.DiagnosticCode.HANDLER_PURITY_VIOLATION,
                construct_type=ConstructType.HANDLER_FUNCTION,
                row_id="impure-handler",
            ),
        ),
        authoring_diagnostic_code=diagnostics.DiagnosticCode.UNRESOLVED_CALLEE_PROVENANCE,
        summary="two handler issues found",
    )

    assert len(failure.evidence) == 2
    assert failure.authoring_diagnostic_code is diagnostics.DiagnosticCode.UNRESOLVED_CALLEE_PROVENANCE
    assert failure.summary == "two handler issues found"

    payload = failure.to_dict()
    assert len(payload["evidence"]) == 2
    assert payload["authoring_diagnostic_code"] == "AWF240_UNRESOLVED_CALLEE_PROVENANCE"
    assert payload["summary"] == "two handler issues found"


def test_semantic_evidence_module_is_declarative() -> None:
    """semantic_evidence.py must not import forbidden runtime/execution modules."""
    from arnold.workflow import semantic_evidence as se

    source_path = Path(se.__file__)
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
