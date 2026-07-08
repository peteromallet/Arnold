from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

import pytest

import arnold.workflow as workflow
from arnold.workflow import diagnostics


FIXTURE_DIR = Path("tests/fixtures/workflow_authoring")
M0_FIXTURE_DIR = FIXTURE_DIR / "m0"
M3_FIXTURE_DIR = FIXTURE_DIR / "m3"
GRAMMAR_VERSION = "arnold.workflow.authoring.v2"
M0_GRAMMAR_VERSION = "arnold.workflow.authoring.v2"
M3_GRAMMAR_VERSION = "arnold.workflow.authoring.v2"
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
M0_EXPECTED_CASES = {
    "valid_m0_single_workflow": "valid",
    "valid_m0_nested_child_workflow": "valid",
    "valid_m0_repeated_call_sites": "valid",
    "invalid_m0_manual_graph_nodes": "invalid",
    "invalid_m0_manual_path_strings": "invalid",
    "invalid_m0_validator_directives": "invalid",
    "invalid_m0_direct_manifest_authoring": "invalid",
    "invalid_m0_native_program_projection": "invalid",
    "invalid_m0_megaplan_only_helpers": "invalid",
    "deferred_m0_nested_child_workflow": "valid",
    "deferred_m0_repeated_call_sites": "valid",
    "deferred_m0_review_revise_loop": "valid",
}
M3_EXPECTED_CASES = {
    "valid_m3_bounded_loop": "valid",
    "valid_m3_branch_routes": "valid",
    "valid_m3_canonical_megaplan_topology": "valid",
    "valid_m3_parallel_map_loop_policy": "valid",
    "valid_m3_policy_refs": "valid",
    "valid_m3_subflow_control_flow": "valid",
    "valid_m3_subflow_ref": "valid",
    "invalid_m3_ambiguous_loop": "invalid",
    "invalid_m3_ambiguous_route_metadata": "invalid",
    "invalid_m3_dynamic_dispatch": "invalid",
    "invalid_m3_dynamic_subflow_identity": "invalid",
    "invalid_m3_handler_owned_review_cap": "invalid",
    "invalid_m3_hidden_finalize_fallback": "invalid",
    "invalid_m3_loop_dynamic_bounds": "invalid",
    "invalid_m3_loop_missing_bounds": "invalid",
    "invalid_m3_loop_non_true_test": "invalid",
    "invalid_m3_malformed_capability_metadata": "invalid",
    "invalid_m3_malformed_retry_policy_config": "invalid",
    "invalid_m3_malformed_timing_policy_config": "invalid",
    "invalid_m3_megaplan_helper_fanout": "invalid",
    "invalid_m3_mismatched_route_metadata": "invalid",
    "invalid_m3_missing_fallthrough_route": "invalid",
    "invalid_m3_non_literal_routing": "invalid",
    "invalid_m3_nonliteral_path_construction": "invalid",
    "invalid_m3_repeated_route_comparison": "invalid",
    "invalid_m3_single_handler_review_fanout": "invalid",
    "invalid_m3_single_handler_wrapper": "invalid",
    "invalid_m3_tiebreaker_single_call_carrier": "invalid",
    "invalid_m3_unreachable_path": "invalid",
    "invalid_m3_unsupported_mutation": "invalid",
    "invalid_m3_unsupported_policy_carrier": "invalid",
    "invalid_m3_unsupported_step_policy_carrier": "invalid",
    "invalid_m3_unsupported_workflow_policy_carrier": "invalid",
}
SUPPORT_MODULES = {"components"}
SOURCE_SPAN_FIELDS = {"start_line", "start_column", "end_line", "end_column"}
COMMON_SIDECAR_FIELDS = {"grammar_version", "source_path", "outcome", "expected_diagnostics"}
M0_VALID_SIDECAR_FIELDS = COMMON_SIDECAR_FIELDS | {"expected_provenance"}
M0_INVALID_SIDECAR_FIELDS = COMMON_SIDECAR_FIELDS | {"rejection_category"}
M0_DEFERRED_SIDECAR_FIELDS = M0_VALID_SIDECAR_FIELDS | {
    "status",
    "deferred_until",
    "description",
}
M0_DEFERRED_CASES = {
    "deferred_m0_review_revise_loop",
}
M0_INVALID_REJECTION_CATEGORIES = {
    "invalid_m0_manual_graph_nodes": "manual_graph_nodes",
    "invalid_m0_manual_path_strings": "manual_path_strings",
    "invalid_m0_validator_directives": "validator_directives",
    "invalid_m0_direct_manifest_authoring": "direct_manifest_authoring",
    "invalid_m0_native_program_projection": "native_program_projection",
    "invalid_m0_megaplan_only_helpers": "megaplan_only_helpers",
}
M0_AWF2XX_CODES = {
    "AWF200_MANUAL_GRAPH_NODES",
    "AWF201_MANUAL_PATH_STRINGS",
    "AWF202_VALIDATOR_DIRECTIVES",
    "AWF203_DIRECT_MANIFEST_AUTHORING",
    "AWF204_NATIVE_PROGRAM_PROJECTION",
    "AWF205_MEGAPLAN_ONLY_HELPERS",
}
M0_DECORATOR_BOUNDARY_CODES = {
    diagnostics.DiagnosticCode.UNSUPPORTED_SYNTAX.value,
    diagnostics.DiagnosticCode.MALFORMED_COMPONENT_EXPORT.value,
    diagnostics.DiagnosticCode.UNKNOWN_COMPONENT.value,
    diagnostics.DiagnosticCode.RESERVED_INTRINSIC_SHADOWING.value,
    diagnostics.DiagnosticCode.MISSING_WORKFLOW_DECLARATION.value,
}


def test_python_authoring_acceptance_fixture_set_is_complete() -> None:
    source_cases = {path.stem for path in FIXTURE_DIR.glob("*.py")} - SUPPORT_MODULES
    sidecar_cases = {path.name.removesuffix(".expected.json") for path in FIXTURE_DIR.glob("*.expected.json")}

    assert source_cases == set(EXPECTED_CASES)
    assert sidecar_cases == set(EXPECTED_CASES)


def test_python_authoring_m0_fixture_set_is_complete() -> None:
    source_cases = {path.stem for path in M0_FIXTURE_DIR.glob("*.py")}
    sidecar_cases = {
        path.name.removesuffix(".expected.json")
        for path in M0_FIXTURE_DIR.glob("*.expected.json")
    }

    assert source_cases == set(M0_EXPECTED_CASES)
    assert sidecar_cases == source_cases


def test_python_authoring_m3_fixture_set_is_complete() -> None:
    source_cases = {path.stem for path in M3_FIXTURE_DIR.glob("*.py")}
    sidecar_cases = {
        path.name.removesuffix(".expected.json")
        for path in M3_FIXTURE_DIR.glob("*.expected.json")
    }

    assert source_cases == set(M3_EXPECTED_CASES)
    assert sidecar_cases == source_cases


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


def test_python_authoring_m0_fixture_sidecars_match_contract() -> None:
    for case_name, outcome in M0_EXPECTED_CASES.items():
        source_path = M0_FIXTURE_DIR / f"{case_name}.py"
        sidecar = _load_sidecar_from_dir(M0_FIXTURE_DIR, case_name)

        assert source_path.exists()
        assert sidecar["grammar_version"] == M0_GRAMMAR_VERSION
        assert sidecar["source_path"] == source_path.as_posix()
        assert sidecar["outcome"] == outcome

        if case_name in M0_DEFERRED_CASES:
            assert set(sidecar) == M0_DEFERRED_SIDECAR_FIELDS
            assert sidecar["status"] == "deferred"
            assert sidecar["deferred_until"]
            assert sidecar["description"]
            assert sidecar["expected_diagnostics"] == []
            _assert_m0_valid_provenance_sidecar(sidecar)
            continue

        if outcome == "valid":
            if "expected_provenance" in sidecar:
                assert set(sidecar) == M0_VALID_SIDECAR_FIELDS
                assert sidecar["expected_diagnostics"] == []
                _assert_m0_valid_provenance_sidecar(sidecar)
                continue
            assert set(sidecar) == {
                "grammar_version",
                "source_path",
                "outcome",
                "group",
                "expected_lowering",
                "expected_diagnostics",
            }
            assert sidecar["expected_diagnostics"] == []
            assert sidecar["expected_lowering"]["workflow_id"]
            continue

        assert set(sidecar) == M0_INVALID_SIDECAR_FIELDS
        assert sidecar["rejection_category"] == M0_INVALID_REJECTION_CATEGORIES[case_name]
        expected_diagnostics = sidecar["expected_diagnostics"]
        assert len(expected_diagnostics) == 1
        expected = expected_diagnostics[0]
        assert expected["code"] in M0_AWF2XX_CODES
        assert expected["rejection_category"] == sidecar["rejection_category"]
        assert expected["grammar_version"] == M0_GRAMMAR_VERSION
        assert expected["message"]


def test_python_authoring_m3_fixture_sidecars_match_contract() -> None:
    known_codes = {code.value for code in diagnostics.DiagnosticCode}

    for case_name, outcome in M3_EXPECTED_CASES.items():
        source_path = M3_FIXTURE_DIR / f"{case_name}.py"
        sidecar = _load_sidecar_from_dir(M3_FIXTURE_DIR, case_name)

        assert source_path.exists()
        assert sidecar["grammar_version"] == M3_GRAMMAR_VERSION
        assert sidecar["source_path"] == source_path.as_posix()
        assert sidecar["outcome"] == outcome
        assert sidecar["group"]

        if outcome == "valid":
            assert set(sidecar) == {
                "grammar_version",
                "source_path",
                "outcome",
                "group",
                "expected_lowering",
                "expected_diagnostics",
            }
            expected_lowering = sidecar["expected_lowering"]
            assert expected_lowering["workflow_id"]
            assert expected_lowering["nodes"]
            assert sidecar["expected_diagnostics"] == []
            continue

        assert set(sidecar) == {
            "grammar_version",
            "source_path",
            "outcome",
            "group",
            "expected_diagnostics",
        }
        diagnostics_payload = sidecar["expected_diagnostics"]
        assert diagnostics_payload
        for diagnostic in diagnostics_payload:
            assert set(diagnostic) >= {"code", "message", "source_span"}
            assert diagnostic["code"] in known_codes
            assert diagnostic["message"]
            source_span = diagnostic["source_span"]
            assert source_span["path"] == source_path.as_posix()
            _assert_span_matches_source(
                source_path,
                {key: value for key, value in source_span.items() if key != "path"},
            )


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


def test_python_authoring_m0_valid_fixture_is_registered_without_requiring_later_lowering() -> None:
    source_path = M0_FIXTURE_DIR / "valid_m0_single_workflow.py"
    result = workflow.check_workflow_file(source_path)

    _assert_m0_step_workflow_authoring_shape(source_path)
    assert _m0_is_currently_decorator_blocked(result) or result.ok


@pytest.mark.parametrize(
    "case_name",
    ["deferred_m0_nested_child_workflow", "deferred_m0_repeated_call_sites"],
)
def test_python_authoring_m0_activated_nested_workflow_fixtures_match_sidecars(
    case_name: str,
) -> None:
    source_path = M0_FIXTURE_DIR / f"{case_name}.py"
    sidecar = _load_sidecar_from_dir(M0_FIXTURE_DIR, case_name)

    result = workflow.check_workflow_file(source_path)
    pipeline = workflow.lower_workflow_file(source_path)

    assert result.ok
    assert result.parsed_source.workflow is not None
    assert _m0_lowered_provenance_payload(result.parsed_source.workflow, pipeline) == sidecar[
        "expected_provenance"
    ]


@pytest.mark.parametrize("case_name", sorted(M0_DEFERRED_CASES))
def test_python_authoring_m0_deferred_sidecars_honor_aspirational_cases(case_name: str) -> None:
    source_path = M0_FIXTURE_DIR / f"{case_name}.py"
    result = workflow.check_workflow_file(source_path)

    assert _load_sidecar_from_dir(M0_FIXTURE_DIR, case_name)["status"] == "deferred"
    _assert_m0_deferred_fixture_shape(case_name, source_path)
    assert _m0_is_currently_decorator_blocked(result) or result.ok


@pytest.mark.parametrize(
    ("case_name", "rejection_category"),
    sorted(M0_INVALID_REJECTION_CATEGORIES.items()),
)
def test_python_authoring_m0_invalid_categories_are_rejected_for_intended_reasons(
    case_name: str,
    rejection_category: str,
) -> None:
    source_path = M0_FIXTURE_DIR / f"{case_name}.py"
    result = workflow.check_workflow_file(source_path)

    _assert_m0_invalid_fixture_shape(source_path, rejection_category)
    assert not result.ok
    if _m0_is_currently_decorator_blocked(result):
        return
    expected_codes = {
        diagnostic["code"]
        for diagnostic in _load_sidecar_from_dir(M0_FIXTURE_DIR, case_name)["expected_diagnostics"]
    }
    assert _diagnostic_codes(result) & expected_codes


def _load_sidecar(case_name: str) -> dict[str, Any]:
    return _load_sidecar_from_dir(FIXTURE_DIR, case_name)


def _load_sidecar_from_dir(fixture_dir: Path, case_name: str) -> dict[str, Any]:
    with (fixture_dir / f"{case_name}.expected.json").open(encoding="utf-8") as handle:
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


def _assert_m0_valid_provenance_sidecar(sidecar: dict[str, Any]) -> None:
    provenance = sidecar["expected_provenance"]
    assert provenance["source_form"] == "function"
    assert provenance["grammar_version"] == M0_GRAMMAR_VERSION
    workflow_payload = provenance["workflow"]
    assert workflow_payload["id"]
    assert workflow_payload["name"]
    assert workflow_payload["inputs_schema"]
    assert workflow_payload["outputs_schema"]
    if "steps" in provenance:
        assert provenance["steps"]
        for step in provenance["steps"]:
            assert step["id"]
            assert step["call_site_path"]


def _m0_lowered_provenance_payload(
    workflow_declaration: workflow.WorkflowDeclaration,
    pipeline: Any,
) -> dict[str, Any]:
    nested_steps = [
        step for step in pipeline.steps if step.metadata.get("executable_workflow") is True
    ]
    ordinary_steps = [
        step for step in pipeline.steps if step.metadata.get("executable_workflow") is not True
    ]
    return {
        "source_form": workflow_declaration.source_form,
        "grammar_version": M0_GRAMMAR_VERSION,
        "workflow": {
            "id": workflow_declaration.id,
            "name": workflow_declaration.function_name,
            "inputs_schema": list(workflow_declaration.parameters),
            "outputs_schema": list(_literal_workflow_outputs(workflow_declaration)),
        },
        "child_workflows": [
            {
                "id": step.metadata["child_workflow_id"],
                "call_site_path": step.metadata["call_site_path"],
                "inputs_schema": list(step.metadata["inputs_schema"]),
                "outputs_schema": list(step.metadata["outputs_schema"]),
            }
            for step in nested_steps
        ],
        "steps": [
            {
                "id": step.id,
                "call_site_path": f"{workflow_declaration.id}/{step.id}",
            }
            for step in ordinary_steps
        ],
    }


def _literal_workflow_outputs(workflow_declaration: workflow.WorkflowDeclaration) -> tuple[str, ...]:
    module = ast.parse(Path(workflow_declaration.source_span.path).read_text(encoding="utf-8"))
    for node in module.body:
        if not isinstance(node, ast.FunctionDef) or node.name != workflow_declaration.function_name:
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call) or getattr(decorator.func, "id", None) != "workflow":
                continue
            for keyword in decorator.keywords:
                if keyword.arg == "outputs" and isinstance(keyword.value, (ast.Set, ast.List, ast.Tuple)):
                    return tuple(
                        element.value
                        for element in keyword.value.elts
                        if isinstance(element, ast.Constant) and isinstance(element.value, str)
                    )
    return ()


def _assert_m0_step_workflow_authoring_shape(source_path: Path) -> None:
    module = ast.parse(source_path.read_text(encoding="utf-8"))
    imported_names = {
        alias.name
        for node in module.body
        if isinstance(node, ast.ImportFrom) and node.module == "arnold.pipeline"
        for alias in node.names
    }
    decorated_functions = [
        node for node in module.body if isinstance(node, ast.FunctionDef) and node.decorator_list
    ]

    assert {"step", "workflow"} <= imported_names
    assert any(_decorator_calls_name(node, "step") for node in decorated_functions)
    assert any(_decorator_calls_name(node, "workflow") for node in decorated_functions)


def _assert_m0_deferred_fixture_shape(case_name: str, source_path: Path) -> None:
    module = ast.parse(source_path.read_text(encoding="utf-8"))

    if case_name == "deferred_m0_nested_child_workflow":
        workflow_defs = [node for node in module.body if _decorator_calls_name(node, "workflow")]
        assert len(workflow_defs) >= 2
        assert any(
            isinstance(node, ast.Call) and getattr(node.func, "id", None) == "review_subprocess"
            for node in ast.walk(module)
        )
        return

    if case_name == "deferred_m0_repeated_call_sites":
        review_calls = [
            node
            for node in ast.walk(module)
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "review"
        ]
        assert len(review_calls) == 2
        return

    if case_name == "deferred_m0_review_revise_loop":
        assert any(isinstance(node, ast.For) for node in ast.walk(module))
        assert any(isinstance(node, ast.Break) for node in ast.walk(module))
        return

    raise AssertionError(f"unknown deferred M0 fixture: {case_name}")


def _assert_m0_invalid_fixture_shape(source_path: Path, rejection_category: str) -> None:
    module = ast.parse(source_path.read_text(encoding="utf-8"))

    if rejection_category == "manual_graph_nodes":
        names = {node.id for node in ast.walk(module) if isinstance(node, ast.Name)}
        assert {"Pipeline", "Stage", "Edge"} <= names
        return

    if rejection_category == "manual_path_strings":
        assert any(isinstance(node, ast.JoinedStr) for node in ast.walk(module))
        return

    if rejection_category == "validator_directives":
        assert any(
            isinstance(node, ast.Call) and getattr(node.func, "id", None) == "validate"
            for node in ast.walk(module)
        )
        return

    if rejection_category == "direct_manifest_authoring":
        assert any(
            isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "WorkflowManifest" for target in node.targets)
            for node in ast.walk(module)
        )
        return

    if rejection_category == "native_program_projection":
        assert any(
            isinstance(node, ast.ImportFrom)
            and node.module == "arnold.pipeline.native.ir"
            and any(alias.name == "NativeProgram" for alias in node.names)
            for node in ast.walk(module)
        )
        return

    if rejection_category == "megaplan_only_helpers":
        assert any(isinstance(node, ast.AsyncFunctionDef) for node in ast.walk(module))
        return

    raise AssertionError(f"unknown rejection category: {rejection_category}")


def _decorator_calls_name(node: ast.AST, name: str) -> bool:
    if not isinstance(node, ast.FunctionDef):
        return False
    return any(
        isinstance(decorator, ast.Call) and getattr(decorator.func, "id", None) == name
        for decorator in node.decorator_list
    )


def _diagnostic_codes(result: workflow.CheckWorkflowResult) -> set[str]:
    return {diagnostic.code.value for diagnostic in result.diagnostics}


def _m0_is_currently_decorator_blocked(result: workflow.CheckWorkflowResult) -> bool:
    return bool(_diagnostic_codes(result) & M0_DECORATOR_BOUNDARY_CODES)


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
