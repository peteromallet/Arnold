from __future__ import annotations

import json
from pathlib import Path

import pytest

from arnold.manifest.refs import ImportRef
import arnold.workflow as workflow
from arnold.workflow import authoring, diagnostics


PUBLIC_SOURCE_APIS = (
    "check_workflow_source",
    "check_workflow_file",
    "lower_workflow_source",
    "lower_workflow_file",
    "compile_workflow_source",
    "compile_workflow_file",
)


def test_source_compiler_public_api_names_are_exported() -> None:
    for name in PUBLIC_SOURCE_APIS:
        assert hasattr(workflow, name), name
        assert name in workflow.__all__
    assert hasattr(workflow, "SourceCompileError")
    assert "SourceCompileError" in workflow.__all__


def test_source_compiler_public_api_call_shapes_accept_source_and_file_inputs() -> None:
    source = Path("tests/fixtures/workflow_authoring/valid_direct_linear.py").read_text(
        encoding="utf-8"
    )
    source_path = Path("tests/fixtures/workflow_authoring/valid_direct_linear.py")

    workflow.check_workflow_source(source, source_path=source_path)
    workflow.lower_workflow_source(source, source_path=source_path)
    workflow.compile_workflow_source(source, source_path=source_path)
    workflow.check_workflow_file(source_path)
    workflow.lower_workflow_file(source_path)
    workflow.compile_workflow_file(source_path)


def test_source_compiler_resolves_components_through_static_resolver_boundary() -> None:
    source = """
from __future__ import annotations

from arnold.workflow.authoring import workflow
from project.workflow_components import plan

workflow(id="custom-resolver", steps=[plan(id="plan")])
"""
    resolver = _Resolver(
        {
            "project.workflow_components:plan": authoring.StepComponent(
                id="plan",
                provenance=authoring.ComponentProvenance(
                    module="project.workflow_components",
                    qualname="plan",
                    export_name="plan",
                ),
            )
        }
    )

    pipeline = workflow.lower_workflow_source(
        source,
        source_path="tests/fixtures/workflow_authoring/custom_resolver.py",
        resolver=resolver,
    )

    assert pipeline.steps[0].metadata["component_ref"] == "project.workflow_components:plan"
    assert resolver.resolved == (ImportRef("project.workflow_components", "plan"),)


def test_source_compiler_lowers_direct_form_to_linear_pipeline_with_call_site_spans() -> None:
    source_path = Path("tests/fixtures/workflow_authoring/valid_direct_linear.py")
    source = source_path.read_text(encoding="utf-8")

    pipeline = workflow.lower_workflow_source(source, source_path=source_path)

    assert [step.id for step in pipeline.steps] == ["plan", "execute", "review"]
    assert [step.kind for step in pipeline.steps] == ["agent", "agent", "agent"]
    assert [step.source_span.start_line for step in pipeline.steps if step.source_span] == [
        10,
        11,
        12,
    ]
    assert [step.metadata["component_ref"] for step in pipeline.steps] == [
        "tests.fixtures.workflow_authoring.components:plan",
        "tests.fixtures.workflow_authoring.components:execute",
        "tests.fixtures.workflow_authoring.components:review",
    ]
    assert [(route.id, route.source, route.target) for route in pipeline.routes] == [
        ("plan-execute", "plan", "execute"),
        ("execute-review", "execute", "review"),
    ]
    assert [route.source_span.start_line for route in pipeline.routes if route.source_span] == [
        11,
        12,
    ]


def test_source_compiler_compiles_direct_form_through_existing_manifest_contract() -> None:
    source_path = Path("tests/fixtures/workflow_authoring/valid_direct_linear.py")
    source = source_path.read_text(encoding="utf-8")

    manifest = workflow.compile_workflow_source(source, source_path=source_path)

    assert manifest.id == "linear-direct"
    assert [node.id for node in manifest.nodes] == ["execute", "plan", "review"]
    assert [(edge.id, edge.source, edge.target) for edge in manifest.edges] == [
        ("execute-review", "execute", "review"),
        ("plan-execute", "plan", "execute"),
    ]
    assert not hasattr(manifest.edges[0], "source_span")
    assert {node.id: node.source_span.start_line for node in manifest.nodes if node.source_span} == {
        "plan": 10,
        "execute": 11,
        "review": 12,
    }


def test_source_compiler_rejects_invalid_import_forms_and_intrinsic_provenance_loss() -> None:
    invalid_sources = {
        "future": "from __future__ import division\n",
        "intrinsic_alias": "from arnold.workflow.authoring import workflow as wf\nwf(id='x', steps=[])\n",
        "intrinsic_unknown": "from arnold.workflow.authoring import not_an_intrinsic\n",
        "dynamic": (
            "from arnold.workflow.authoring import workflow\n"
            "plan = __import__('project.workflow_components').plan\n"
            "workflow(id='x', steps=[plan(id='plan')])\n"
        ),
        "assigned_workflow": (
            "from arnold.workflow.authoring import workflow\n"
            "value = workflow(id='not-direct', steps=[])\n"
        ),
    }

    results = {
        name: workflow.check_workflow_source(source, source_path=f"{name}.py")
        for name, source in invalid_sources.items()
    }

    assert diagnostics.DiagnosticCode.INVALID_IMPORT_SOURCE in _codes(results["future"])
    assert diagnostics.DiagnosticCode.RESERVED_INTRINSIC_SHADOWING in _codes(
        results["intrinsic_alias"]
    )
    assert diagnostics.DiagnosticCode.INVALID_IMPORT_SOURCE in _codes(results["intrinsic_unknown"])
    assert diagnostics.DiagnosticCode.UNSUPPORTED_SYNTAX in _codes(results["dynamic"])
    assert diagnostics.DiagnosticCode.MISSING_WORKFLOW_DECLARATION in _codes(
        results["assigned_workflow"]
    )


def test_source_compiler_accepts_exactly_one_direct_or_function_workflow_source_form() -> None:
    direct_source = Path("tests/fixtures/workflow_authoring/valid_direct_linear.py").read_text(
        encoding="utf-8"
    )
    function_source = Path("tests/fixtures/workflow_authoring/valid_function_linear.py").read_text(
        encoding="utf-8"
    )
    mixed_source = direct_source + "\n" + function_source

    direct = workflow.check_workflow_source(
        direct_source,
        source_path="tests/fixtures/workflow_authoring/valid_direct_linear.py",
    )
    function = workflow.check_workflow_source(
        function_source,
        source_path="tests/fixtures/workflow_authoring/valid_function_linear.py",
    )
    mixed = workflow.check_workflow_source(
        mixed_source,
        source_path="tests/fixtures/workflow_authoring/mixed.py",
    )

    assert direct.ok
    assert direct.parsed_source.workflow is not None
    assert direct.parsed_source.workflow.source_form == "direct"
    assert function.ok
    assert function.parsed_source.workflow is not None
    assert function.parsed_source.workflow.source_form == "function"
    assert [step.id for step in function.parsed_source.workflow.steps] == [
        "plan",
        "execute",
        "review",
    ]
    assert diagnostics.DiagnosticCode.MULTIPLE_WORKFLOW_DECLARATIONS in _codes(mixed)


def test_source_compiler_parses_function_header_metadata_and_ordered_scope() -> None:
    source = Path("tests/fixtures/workflow_authoring/valid_function_linear.py").read_text(
        encoding="utf-8"
    )

    result = workflow.check_workflow_source(
        source,
        source_path="tests/fixtures/workflow_authoring/valid_function_linear.py",
    )

    assert result.ok
    assert result.parsed_source.workflow is not None
    assert result.parsed_source.workflow.id == "linear-function"
    assert result.parsed_source.workflow.version == "1.0"
    assert result.parsed_source.workflow.function_name == "linear"
    assert result.parsed_source.workflow.parameters == ("brief",)
    assert result.parsed_source.scope.parameters == ("brief",)


def test_source_compiler_lowers_function_body_dataflow_in_source_order() -> None:
    source = Path("tests/fixtures/workflow_authoring/valid_function_linear.py").read_text(
        encoding="utf-8"
    )

    pipeline = workflow.lower_workflow_source(
        source,
        source_path="tests/fixtures/workflow_authoring/valid_function_linear.py",
    )

    assert [step.id for step in pipeline.steps] == ["plan", "execute", "review"]
    assert [
        [(input_binding.name, input_binding.value_ref) for input_binding in step.inputs]
        for step in pipeline.steps
    ] == [
        [("brief", "param:brief")],
        [("plan", "output:plan_output")],
        [("evidence", "output:evidence")],
    ]
    assert [[output.name for output in step.outputs] for step in pipeline.steps] == [
        ["plan_output"],
        ["execute_output", "evidence"],
        [],
    ]
    assert [(route.id, route.source, route.target) for route in pipeline.routes] == [
        ("plan-execute", "plan", "execute"),
        ("execute-review", "execute", "review"),
    ]


def test_source_compiler_compiles_function_body_bindings_through_manifest_contract() -> None:
    source_path = Path("tests/fixtures/workflow_authoring/valid_function_linear.py")
    manifest = workflow.compile_workflow_file(source_path)

    nodes = {node.id: node for node in manifest.nodes}
    assert nodes["plan"].inputs == ("brief",)
    assert nodes["plan"].outputs == ("plan_output",)
    assert nodes["plan"].metadata["input_bindings"]["brief"]["value_ref"] == "param:brief"
    assert nodes["execute"].inputs == ("plan",)
    assert nodes["execute"].outputs == ("execute_output", "evidence")
    assert nodes["execute"].metadata["input_bindings"]["plan"]["value_ref"] == "output:plan_output"
    assert nodes["review"].inputs == ("evidence",)
    assert nodes["review"].outputs == ()
    assert nodes["review"].metadata["input_bindings"]["evidence"]["value_ref"] == "output:evidence"


@pytest.mark.parametrize(
    ("fixture_name", "expected_topology_hash", "expected_manifest_hash"),
    [
        (
            "valid_direct_linear",
            "sha256:b8241316a814bb9145914b9fa079363215a7b71b7b634390374edb0174a47bc5",
            "sha256:a1d884c2d6116aa82d1d8304b36f6c728b81e71ca2a69dd51d37d6bcdfec8585",
        ),
        (
            "valid_function_linear",
            "sha256:552872e0ffacd32b29cd25ad55298ef4866d186be0326d3f7c90293f70ad866e",
            "sha256:63846e02a691f11141d8a439f647eda7f25609f1a9f9e803b86d0b6ca6a18ada",
        ),
    ],
)
def test_source_compiler_valid_fixture_manifest_goldens_are_stable(
    fixture_name: str,
    expected_topology_hash: str,
    expected_manifest_hash: str,
) -> None:
    source_path = Path(f"tests/fixtures/workflow_authoring/{fixture_name}.py")

    manifest = workflow.compile_workflow_file(source_path)
    manifest_payload = json.loads(manifest.to_json())

    assert manifest.topology_hash == expected_topology_hash
    assert manifest.manifest_hash == expected_manifest_hash
    assert manifest_payload["topology_hash"] == expected_topology_hash
    assert manifest_payload["manifest_hash"] == expected_manifest_hash
    assert [node["id"] for node in manifest_payload["nodes"]] == ["execute", "plan", "review"]
    assert [edge["id"] for edge in manifest_payload["edges"]] == [
        "execute-review",
        "plan-execute",
    ]
    assert all(node["metadata"]["component_ref"].endswith(f":{node['id']}") for node in manifest_payload["nodes"])


def test_source_compiler_function_fixture_pins_parameter_local_and_tuple_ordering() -> None:
    source_path = Path("tests/fixtures/workflow_authoring/valid_function_linear.py")

    pipeline = workflow.lower_workflow_file(source_path)
    manifest = workflow.compile_workflow_file(source_path)

    assert [
        (
            step.id,
            [(input_binding.name, input_binding.value_ref) for input_binding in step.inputs],
            [output.name for output in step.outputs],
        )
        for step in pipeline.steps
    ] == [
        ("plan", [("brief", "param:brief")], ["plan_output"]),
        ("execute", [("plan", "output:plan_output")], ["execute_output", "evidence"]),
        ("review", [("evidence", "output:evidence")], []),
    ]
    assert {
        node.id: (
            node.inputs,
            node.outputs,
            {
                name: binding["value_ref"]
                for name, binding in node.metadata.get("input_bindings", {}).items()
            },
        )
        for node in manifest.nodes
    } == {
        "execute": (("plan",), ("execute_output", "evidence"), {"plan": "output:plan_output"}),
        "plan": (("brief",), ("plan_output",), {"brief": "param:brief"}),
        "review": (("evidence",), (), {"evidence": "output:evidence"}),
    }


def test_source_compiler_repeated_compiles_are_deterministic() -> None:
    source_path = Path("tests/fixtures/workflow_authoring/valid_function_linear.py")
    source = source_path.read_text(encoding="utf-8")

    manifests = [
        workflow.compile_workflow_source(source, source_path=source_path)
        for _ in range(3)
    ]

    assert {manifest.topology_hash for manifest in manifests} == {
        "sha256:552872e0ffacd32b29cd25ad55298ef4866d186be0326d3f7c90293f70ad866e"
    }
    assert {manifest.manifest_hash for manifest in manifests} == {
        "sha256:63846e02a691f11141d8a439f647eda7f25609f1a9f9e803b86d0b6ca6a18ada"
    }
    assert len({manifest.to_json() for manifest in manifests}) == 1


def test_source_compiler_rejects_future_and_unknown_dataflow_with_precise_spans() -> None:
    source = (
        "from arnold.workflow.authoring import workflow\n"
        "from tests.fixtures.workflow_authoring.components import plan, execute\n"
        "@workflow(id='x')\n"
        "def flow(brief):\n"
        "    execute_output = execute(id='execute', plan=plan_output)\n"
        "    plan_output = plan(id='plan', brief=brief)\n"
    )

    result = workflow.check_workflow_source(source, source_path="future_output.py")

    assert _diagnostic_payloads(result) == [
        {
            "code": "AWF005_UNKNOWN_COMPONENT",
            "message": "keyword dataflow reference is not a workflow parameter or prior local output",
            "source_span": {
                "path": "future_output.py",
                "start_line": 5,
                "start_column": 44,
                "end_line": 5,
                "end_column": 60,
            },
        }
    ]


def test_source_compiler_lowers_canonical_intrinsics_to_existing_policy_slots() -> None:
    source = """
from arnold.workflow.authoring import workflow, halt, suspend, transition
from tests.fixtures.workflow_authoring.components import plan, execute

@workflow(id="intrinsic-linear")
def flow(brief):
    plan_output = plan(id="plan", brief=brief)
    execute(id="execute", plan=plan_output)
    suspend(route_id="operator", reentry_id="execute")
    transition(id="operator-resume", type="override", trigger_ref="operator.resume", target_ref="execute")
    halt(id="operator-stop", trigger_ref="operator.stop")
"""

    pipeline = workflow.lower_workflow_source(source, source_path="intrinsic_linear.py")

    assert pipeline.policy is not None
    assert [
        route.route_id for route in pipeline.policy.suspension_routes
    ] == ["operator"]
    assert [
        (transition.transition_id, transition.transition_type, transition.trigger_ref, transition.target_ref)
        for transition in pipeline.policy.control_transitions
    ] == [
        ("operator-resume", "override", "operator.resume", "execute"),
        ("operator-stop", "halt", "operator.stop", None),
    ]

    manifest = workflow.compile_workflow_source(source, source_path="intrinsic_linear.py")

    assert manifest.policy is not None
    assert manifest.policy.suspension_routes[0].route_id == "operator"
    assert manifest.policy.control_transitions[1].transition_type == "halt"


def test_source_compiler_rejects_malformed_intrinsic_usage() -> None:
    invalid_sources = {
        "aliased": (
            "from arnold.workflow.authoring import workflow, halt as stop\n"
            "@workflow(id='x')\n"
            "def flow():\n"
            "    stop(id='stop')\n"
        ),
        "assigned": (
            "from arnold.workflow.authoring import workflow, halt\n"
            "@workflow(id='x')\n"
            "def flow():\n"
            "    result = halt(id='stop')\n"
        ),
        "ordinary_component": (
            "from arnold.workflow.authoring import workflow, halt\n"
            "workflow(id='x', steps=[halt(id='stop')])\n"
        ),
        "shadowed_output": (
            "from arnold.workflow.authoring import workflow\n"
            "from tests.fixtures.workflow_authoring.components import plan\n"
            "@workflow(id='x')\n"
            "def flow(brief):\n"
            "    halt = plan(id='plan', brief=brief)\n"
        ),
        "value_passed": (
            "from arnold.workflow.authoring import workflow, halt\n"
            "from tests.fixtures.workflow_authoring.components import plan\n"
            "@workflow(id='x')\n"
            "def flow(brief):\n"
            "    plan_output = plan(id='plan', brief=halt)\n"
        ),
        "nonliteral": (
            "from arnold.workflow.authoring import workflow, suspend\n"
            "ROUTE = 'operator'\n"
            "@workflow(id='x')\n"
            "def flow():\n"
            "    suspend(route_id=ROUTE)\n"
        ),
        "unknown_keyword": (
            "from arnold.workflow.authoring import workflow, transition\n"
            "@workflow(id='x')\n"
            "def flow():\n"
            "    transition(id='operator-resume', type='override', unsupported='x')\n"
        ),
    }

    results = {
        name: workflow.check_workflow_source(source, source_path=f"{name}.py")
        for name, source in invalid_sources.items()
    }

    assert diagnostics.DiagnosticCode.RESERVED_INTRINSIC_SHADOWING in _codes(results["aliased"])
    assert diagnostics.DiagnosticCode.UNSUPPORTED_SYNTAX in _codes(results["assigned"])
    assert diagnostics.DiagnosticCode.UNSUPPORTED_SYNTAX in _codes(results["ordinary_component"])
    assert diagnostics.DiagnosticCode.RESERVED_INTRINSIC_SHADOWING in _codes(
        results["shadowed_output"]
    )
    assert diagnostics.DiagnosticCode.RESERVED_INTRINSIC_SHADOWING in _codes(
        results["value_passed"]
    )
    assert diagnostics.DiagnosticCode.UNSUPPORTED_SYNTAX in _codes(results["nonliteral"])
    assert diagnostics.DiagnosticCode.UNSUPPORTED_SYNTAX in _codes(results["unknown_keyword"])


def test_source_compiler_rejects_function_body_dataflow_outside_linear_subset() -> None:
    invalid_sources = {
        "future_output": (
            "from arnold.workflow.authoring import workflow\n"
            "from tests.fixtures.workflow_authoring.components import plan, execute\n"
            "@workflow(id='x')\n"
            "def flow(brief):\n"
            "    execute_output = execute(id='execute', plan=plan_output)\n"
            "    plan_output = plan(id='plan', brief=brief)\n"
        ),
        "self_reference": (
            "from arnold.workflow.authoring import workflow\n"
            "from tests.fixtures.workflow_authoring.components import plan\n"
            "@workflow(id='x')\n"
            "def flow(brief):\n"
            "    plan_output = plan(id='plan', brief=plan_output)\n"
        ),
        "literal_keyword": (
            "from arnold.workflow.authoring import workflow\n"
            "from tests.fixtures.workflow_authoring.components import plan\n"
            "@workflow(id='x')\n"
            "def flow(brief):\n"
            "    plan_output = plan(id='plan', brief='literal')\n"
        ),
        "call_keyword": (
            "from arnold.workflow.authoring import workflow\n"
            "from tests.fixtures.workflow_authoring.components import plan\n"
            "@workflow(id='x')\n"
            "def flow(brief):\n"
            "    plan_output = plan(id='plan', brief=str(brief))\n"
        ),
        "attribute_keyword": (
            "from arnold.workflow.authoring import workflow\n"
            "from tests.fixtures.workflow_authoring.components import plan\n"
            "@workflow(id='x')\n"
            "def flow(brief):\n"
            "    plan_output = plan(id='plan', brief=brief.text)\n"
        ),
        "unsupported_local": (
            "from arnold.workflow.authoring import workflow\n"
            "from tests.fixtures.workflow_authoring.components import plan\n"
            "@workflow(id='x')\n"
            "def flow(brief):\n"
            "    local = brief\n"
            "    plan_output = plan(id='plan', brief=local)\n"
        ),
    }

    results = {
        name: workflow.check_workflow_source(source, source_path=f"{name}.py")
        for name, source in invalid_sources.items()
    }

    assert diagnostics.DiagnosticCode.UNKNOWN_COMPONENT in _codes(results["future_output"])
    assert diagnostics.DiagnosticCode.UNKNOWN_COMPONENT in _codes(results["self_reference"])
    assert diagnostics.DiagnosticCode.UNSUPPORTED_SYNTAX in _codes(results["literal_keyword"])
    assert diagnostics.DiagnosticCode.UNSUPPORTED_SYNTAX in _codes(results["call_keyword"])
    assert diagnostics.DiagnosticCode.UNSUPPORTED_SYNTAX in _codes(results["attribute_keyword"])
    assert diagnostics.DiagnosticCode.UNSUPPORTED_SYNTAX in _codes(results["unsupported_local"])


def test_source_compiler_rejects_function_header_features_outside_m2_subset() -> None:
    invalid_sources = {
        "positional_decorator": (
            "from arnold.workflow.authoring import workflow\n"
            "@workflow('x')\n"
            "def flow(brief):\n"
            "    return None\n"
        ),
        "default_parameter": (
            "from arnold.workflow.authoring import workflow\n"
            "@workflow(id='x')\n"
            "def flow(brief='default'):\n"
            "    return None\n"
        ),
        "vararg": (
            "from arnold.workflow.authoring import workflow\n"
            "@workflow(id='x')\n"
            "def flow(*briefs):\n"
            "    return None\n"
        ),
        "keyword_only": (
            "from arnold.workflow.authoring import workflow\n"
            "@workflow(id='x')\n"
            "def flow(*, brief):\n"
            "    return None\n"
        ),
        "dynamic_version": (
            "from arnold.workflow.authoring import workflow\n"
            "VERSION = '1.0'\n"
            "@workflow(id='x', version=VERSION)\n"
            "def flow(brief):\n"
            "    return None\n"
        ),
    }

    for name, source in invalid_sources.items():
        result = workflow.check_workflow_source(source, source_path=f"{name}.py")
        assert diagnostics.DiagnosticCode.UNSUPPORTED_SYNTAX in _codes(result), name


def test_source_compiler_rejects_initial_scope_parameter_shadowing() -> None:
    source = """
from arnold.workflow.authoring import workflow
from tests.fixtures.workflow_authoring.components import plan

@workflow(id="shadowing")
def flow(workflow, plan, brief):
    missing(id="not-lowered", brief=brief)
"""

    result = workflow.check_workflow_source(source, source_path="shadowing.py")

    assert _codes(result) == {diagnostics.DiagnosticCode.RESERVED_INTRINSIC_SHADOWING}
    assert result.parsed_source.workflow is not None
    assert result.parsed_source.workflow.parameters == ("workflow", "plan", "brief")
    assert result.parsed_source.workflow.steps == ()


def test_source_compiler_does_not_execute_workflow_source() -> None:
    source = """
from __future__ import annotations

from arnold.workflow.authoring import workflow
from project.workflow_components import plan

raise RuntimeError("source execution leaked into static parsing")

workflow(id="no-exec", steps=[plan(id="plan")])
"""
    resolver = _Resolver(
        {
            "project.workflow_components:plan": authoring.StepComponent(
                id="plan",
                provenance=authoring.ComponentProvenance(
                    module="project.workflow_components",
                    qualname="plan",
                    export_name="plan",
                ),
            )
        }
    )

    result = workflow.check_workflow_source(source, source_path="no_exec.py", resolver=resolver)

    assert result.ok


def test_source_compiler_compile_apis_raise_source_compile_error_with_diagnostics() -> None:
    source = "from arnold.workflow.authoring import workflow\nworkflow(id='x', steps=[missing(id='x')])\n"

    with pytest.raises(workflow.SourceCompileError) as source_error:
        workflow.compile_workflow_source(source, source_path="invalid.py")
    assert diagnostics.DiagnosticCode.UNKNOWN_COMPONENT in {
        diagnostic.code for diagnostic in source_error.value.diagnostics
    }

    with pytest.raises(workflow.SourceCompileError) as lower_error:
        workflow.lower_workflow_source(source, source_path="invalid.py")
    assert diagnostics.DiagnosticCode.UNKNOWN_COMPONENT in {
        diagnostic.code for diagnostic in lower_error.value.diagnostics
    }


def test_source_compiler_file_apis_read_text_without_executing_source_files(tmp_path: Path) -> None:
    source_path = tmp_path / "no_exec_file.py"
    source_path.write_text(
        """
from arnold.workflow.authoring import workflow
from project.workflow_components import plan

raise RuntimeError("source execution leaked into file API")

workflow(id="no-exec-file", steps=[plan(id="plan")])
""",
        encoding="utf-8",
    )
    resolver = _Resolver(
        {
            "project.workflow_components:plan": authoring.StepComponent(
                id="plan",
                provenance=authoring.ComponentProvenance(
                    module="project.workflow_components",
                    qualname="plan",
                    export_name="plan",
                ),
            )
        }
    )

    check_result = workflow.check_workflow_file(source_path, resolver=resolver)
    pipeline = workflow.lower_workflow_file(source_path, resolver=resolver)
    manifest = workflow.compile_workflow_file(source_path, resolver=resolver)

    assert check_result.ok
    assert pipeline.id == "no-exec-file"
    assert manifest.id == "no-exec-file"


def _codes(result: workflow.CheckWorkflowSourceResult) -> set[diagnostics.DiagnosticCode]:
    return {diagnostic.code for diagnostic in result.diagnostics}


def _diagnostic_payloads(result: workflow.CheckWorkflowSourceResult) -> list[dict[str, object]]:
    payloads: list[dict[str, object]] = []
    for diagnostic in result.diagnostics:
        payload: dict[str, object] = {
            "code": diagnostic.code.value,
            "message": diagnostic.message,
        }
        if diagnostic.source_span is not None:
            payload["source_span"] = {
                "path": diagnostic.source_span.path,
                "start_line": diagnostic.source_span.start_line,
                "start_column": diagnostic.source_span.start_column,
                "end_line": diagnostic.source_span.end_line,
                "end_column": diagnostic.source_span.end_column,
            }
        if diagnostic.import_ref is not None:
            payload["import_ref"] = {
                "module": diagnostic.import_ref.module,
                "qualname": diagnostic.import_ref.qualname,
            }
        if diagnostic.component_ref is not None:
            payload["component_ref"] = diagnostic.component_ref
        payloads.append(payload)
    return payloads


class _Resolver:
    def __init__(self, components: dict[str, authoring.ComponentContract]) -> None:
        self._components = components
        self._resolved: list[ImportRef] = []

    @property
    def resolved(self) -> tuple[ImportRef, ...]:
        return tuple(self._resolved)

    def resolve(self, import_ref: ImportRef) -> authoring.ComponentContract | None:
        self._resolved.append(import_ref)
        return self._components.get(import_ref.spec)
