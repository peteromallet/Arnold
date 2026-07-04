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
