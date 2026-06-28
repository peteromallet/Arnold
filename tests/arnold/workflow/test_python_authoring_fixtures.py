from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

import arnold.workflow as workflow
from arnold.workflow import diagnostics


FIXTURE_DIR = Path("tests/fixtures/workflow_authoring")
GRAMMAR_VERSION = "arnold.workflow.authoring.v1"
EXPECTED_CASES = {
    "valid_direct_linear": "valid",
    "valid_function_linear": "valid",
    "valid_linear_halt_intrinsic": "valid",
    "valid_linear_single_step": "valid",
    "valid_linear_suspend_intrinsic": "valid",
    "valid_linear_transition_intrinsic": "valid",
    "valid_linear_tuple_unused_outputs": "valid",
    "invalid_alias_provenance_loss": "invalid",
    "invalid_duplicate_local_assignment": "invalid",
    "invalid_dynamic_import": "invalid",
    "invalid_function_header": "invalid",
    "invalid_forbidden_root_import": "invalid",
    "invalid_intrinsic_missing_required_keyword": "invalid",
    "invalid_intrinsic_shadowing": "invalid",
    "invalid_intrinsic_unknown_keyword": "invalid",
    "invalid_intrinsic_wrong_keyword_set": "invalid",
    "invalid_malformed_call": "invalid",
    "invalid_dynamic_component_construction": "invalid",
    "invalid_nested_subflow": "invalid",
    "invalid_parallel_fanout": "invalid",
    "invalid_missing_workflow": "invalid",
    "invalid_multiple_workflows": "invalid",
    "invalid_reserved_step_keyword": "invalid",
    "invalid_star_import": "invalid",
    "invalid_static_prompt_resource_dependencies": "invalid",
    "invalid_unknown_component": "invalid",
    "invalid_unknown_reference": "invalid",
    "invalid_unsupported_syntax": "invalid",
    "invalid_unsupported_control_flow": "invalid",
    "invalid_wrong_component_kind": "invalid",
    "invalid_runtime_truthiness": "invalid",
    "invalid_runtime_iteration": "invalid",
    "invalid_runtime_arithmetic": "invalid",
    "invalid_runtime_attribute": "invalid",
}
SUPPORT_MODULES = {"components"}
SOURCE_SPAN_FIELDS = {"start_line", "start_column", "end_line", "end_column"}
COMMON_SIDECAR_FIELDS = {"grammar_version", "source_path", "outcome", "expected_diagnostics"}


def test_python_authoring_acceptance_fixture_set_is_complete() -> None:
    source_cases = {path.stem for path in FIXTURE_DIR.glob("*.py")} - SUPPORT_MODULES
    sidecar_cases = {path.name.removesuffix(".expected.json") for path in FIXTURE_DIR.glob("*.expected.json")}

    assert source_cases == set(EXPECTED_CASES)
    assert sidecar_cases == set(EXPECTED_CASES)


def test_python_authoring_fixture_sidecars_match_contract() -> None:
    known_codes = {code.value for code in diagnostics.DiagnosticCode}

    for case_name, outcome in EXPECTED_CASES.items():
        source_path = FIXTURE_DIR / f"{case_name}.py"
        sidecar = _load_sidecar(case_name)

        expected_fields = COMMON_SIDECAR_FIELDS | ({"expected_provenance"} if outcome == "valid" else set())
        assert set(sidecar) == expected_fields
        assert sidecar["grammar_version"] == GRAMMAR_VERSION
        assert sidecar["source_path"] == source_path.as_posix()
        assert source_path.exists()
        assert sidecar["outcome"] == outcome

        diagnostics_payload = sidecar["expected_diagnostics"]
        if outcome == "valid":
            assert diagnostics_payload == []
            _assert_valid_provenance_sidecar(sidecar, source_path)
        else:
            assert diagnostics_payload
            for diagnostic in diagnostics_payload:
                assert set(diagnostic) >= {"code", "message", "source_span"}
                assert diagnostic["code"] in known_codes
                assert diagnostic["message"]
                _assert_span_matches_source(source_path, diagnostic["source_span"])


def test_python_authoring_invalid_fixture_diagnostics_match_sidecars() -> None:
    for case_name, outcome in EXPECTED_CASES.items():
        if outcome != "invalid":
            continue
        source_path = FIXTURE_DIR / f"{case_name}.py"
        expected = _load_sidecar(case_name)["expected_diagnostics"]

        result = workflow.check_workflow_file(source_path)

        assert [_diagnostic_payload(diagnostic) for diagnostic in result.diagnostics] == expected


def test_python_authoring_valid_fixture_provenance_matches_sidecars() -> None:
    for case_name, outcome in EXPECTED_CASES.items():
        if outcome != "valid":
            continue
        source_path = FIXTURE_DIR / f"{case_name}.py"
        expected = _load_sidecar(case_name)["expected_provenance"]

        result = workflow.check_workflow_file(source_path)

        assert result.ok
        parsed = result.parsed_source
        assert parsed.workflow is not None
        assert {
            "source_form": parsed.workflow.source_form,
            "workflow": _workflow_provenance_payload(parsed.workflow),
            "imports": [
                _import_provenance_payload(binding)
                for binding in parsed.scope.imports.values()
            ],
            "steps": [
                _step_provenance_payload(step)
                for step in parsed.workflow.steps
            ],
            "intrinsics": [
                _intrinsic_provenance_payload(intrinsic)
                for intrinsic in parsed.workflow.intrinsics
            ],
        } == expected


def _load_sidecar(case_name: str) -> dict[str, Any]:
    with (FIXTURE_DIR / f"{case_name}.expected.json").open(encoding="utf-8") as handle:
        return json.load(handle)


def _diagnostic_payload(diagnostic: diagnostics.AuthoringDiagnostic) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "code": diagnostic.code.value,
        "message": diagnostic.message,
    }
    if diagnostic.import_ref is not None:
        payload["import_ref"] = {
            "module": diagnostic.import_ref.module,
            "qualname": diagnostic.import_ref.qualname,
        }
    if diagnostic.component_ref is not None:
        payload["component_ref"] = diagnostic.component_ref
    if diagnostic.source_span is not None:
        payload["source_span"] = _span_payload(diagnostic.source_span)
    return payload


def _workflow_provenance_payload(workflow_declaration: workflow.WorkflowDeclaration) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": workflow_declaration.id,
        "source_span": _span_payload(workflow_declaration.source_span),
    }
    if workflow_declaration.function_name is not None:
        payload["function_name"] = workflow_declaration.function_name
    if workflow_declaration.parameters:
        payload["parameters"] = list(workflow_declaration.parameters)
    return payload


def _import_provenance_payload(binding: workflow.ImportBinding) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "module": binding.import_ref.module,
        "qualname": binding.import_ref.qualname,
        "local_name": binding.local_name,
        "kind": binding.kind,
        "source_span": _span_payload(binding.source_span),
    }
    if binding.component is not None:
        payload["component_id"] = binding.component.id
    return payload


def _step_provenance_payload(step: workflow.StepCall) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": step.id,
        "component_ref": step.component_ref,
        "generated_dsl_id": f"step:{step.id}",
        "generated_manifest_node_id": step.id,
        "source_span": _span_payload(step.source_span),
    }
    if step.outputs:
        payload["output_spans"] = [_span_payload(output.source_span) for output in step.outputs]
    if step.inputs:
        payload["inputs"] = [
            {
                "name": input_binding.name,
                "ref": input_binding.value_ref,
                "source_span": _span_payload(input_binding.source_span),
            }
            for input_binding in step.inputs
        ]
    return payload


def _intrinsic_provenance_payload(intrinsic: workflow.IntrinsicCall) -> dict[str, Any]:
    return {
        "name": intrinsic.name,
        "arguments": dict(intrinsic.arguments),
        "source_span": _span_payload(intrinsic.source_span),
    }


def _span_payload(span: Any) -> dict[str, int]:
    return {
        "start_line": span.start_line,
        "start_column": span.start_column,
        "end_line": span.end_line,
        "end_column": span.end_column,
    }


def _assert_valid_provenance_sidecar(sidecar: dict[str, Any], source_path: Path) -> None:
    provenance = sidecar["expected_provenance"]
    assert provenance["source_form"] in {"direct", "function"}
    assert provenance["workflow"]["id"]
    _assert_span_matches_source(source_path, provenance["workflow"]["source_span"])

    imports = provenance["imports"]
    assert [item["local_name"] for item in imports]
    assert {item["kind"] for item in imports} >= {"intrinsic", "step"}
    for item in imports:
        assert item["module"]
        assert item["qualname"]
        _assert_span_matches_source(source_path, item["source_span"])

    steps = provenance["steps"]
    step_ids = [step["id"] for step in steps]
    assert step_ids
    assert len(step_ids) == len(set(step_ids))
    for step in steps:
        assert step["component_ref"].endswith(f":{step['id']}")
        assert step["generated_dsl_id"] == f"step:{step['id']}"
        assert step["generated_manifest_node_id"] == step["id"]
        _assert_span_matches_source(source_path, step["source_span"])
        for span in step.get("output_spans", []):
            _assert_span_matches_source(source_path, span)
        for binding in step.get("inputs", []):
            assert set(binding) >= {"name", "ref", "source_span"}
            _assert_span_matches_source(source_path, binding["source_span"])

    intrinsics = provenance["intrinsics"]
    assert isinstance(intrinsics, list)
    for intrinsic in intrinsics:
        assert set(intrinsic) == {"name", "arguments", "source_span"}
        assert isinstance(intrinsic["name"], str)
        assert intrinsic["name"]
        assert isinstance(intrinsic["arguments"], dict)
        assert all(isinstance(key, str) for key in intrinsic["arguments"])
        _assert_span_matches_source(source_path, intrinsic["source_span"])


def _assert_span_matches_source(source_path: Path, span: dict[str, int]) -> None:
    _assert_source_span_shape(span)
    expected = (
        span["start_line"],
        span["start_column"] - 1,
        span["end_line"],
        span["end_column"] - 1,
    )
    actual_spans = {
        (
            node.lineno,
            node.col_offset,
            node.end_lineno,
            node.end_col_offset,
        )
        for node in ast.walk(ast.parse(source_path.read_text(encoding="utf-8")))
        if hasattr(node, "lineno")
    }
    assert expected in actual_spans


def _assert_source_span_shape(span: dict[str, int]) -> None:
    assert set(span) == SOURCE_SPAN_FIELDS
    assert all(isinstance(value, int) for value in span.values())
    assert all(value >= 1 for value in span.values())
    assert (span["end_line"], span["end_column"]) >= (
        span["start_line"],
        span["start_column"],
    )
