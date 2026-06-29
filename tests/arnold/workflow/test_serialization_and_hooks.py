from __future__ import annotations

import subprocess
import sys

import pytest

from arnold.workflow import (
    HookRef,
    ImportRef,
    Pipeline,
    RefDiagnosticError,
    Step,
    as_hook_ref,
    as_import_ref,
    compile_pipeline,
)
from tests.arnold.patterns import _fixtures


def test_manifest_hash_is_stable_across_separate_processes() -> None:
    pipeline = Pipeline(
        id="planning",
        version="v1",
        steps=[Step(id="plan", kind="agent")],
    )
    manifest = compile_pipeline(pipeline)
    json_text = manifest.to_json()

    code = (
        "import sys; "
        "from arnold.workflow import WorkflowManifest, compute_manifest_hash, compute_topology_hash; "
        "m = WorkflowManifest.from_json(sys.argv[1]); "
        "print(m.manifest_hash); print(m.topology_hash)"
    )
    result = subprocess.run(
        [sys.executable, "-c", code, json_text],
        capture_output=True,
        text=True,
        check=True,
    )
    remote_manifest_hash, remote_topology_hash = result.stdout.strip().splitlines()

    assert remote_manifest_hash == manifest.manifest_hash
    assert remote_topology_hash == manifest.topology_hash


def test_importable_hooks_are_accepted() -> None:
    ref = HookRef.from_callable(_fixtures.agent_prompt, node_id="plan", field="prompt_ref")

    assert ref.spec == "tests.arnold.patterns._fixtures:agent_prompt"
    resolved = ref.resolve()
    assert resolved is _fixtures.agent_prompt


def test_hook_ref_from_string_resolves_importable_function() -> None:
    ref = HookRef.parse("tests.arnold.patterns._fixtures:decide_condition")

    assert ref.resolve() is _fixtures.decide_condition


def test_hook_ref_rejects_lambdas() -> None:
    with pytest.raises(RefDiagnosticError, match="lambdas"):
        HookRef.from_callable(lambda: None, node_id="plan", field="hook")


def test_hook_ref_rejects_closures() -> None:
    captured = "state"

    def closure() -> str:
        return captured

    with pytest.raises(RefDiagnosticError, match="closures"):
        HookRef.from_callable(closure, node_id="plan", field="hook")


def test_hook_ref_rejects_bound_methods() -> None:
    class Container:
        def method(self) -> str:
            return "method"

    with pytest.raises(RefDiagnosticError, match="bound methods"):
        HookRef.from_callable(Container().method, node_id="plan", field="hook")


def test_hook_ref_rejects_callable_instances() -> None:
    class Callable:
        def __call__(self) -> str:
            return "callable"

    with pytest.raises(RefDiagnosticError, match="callable instances"):
        HookRef.from_callable(Callable(), node_id="plan", field="hook")


def test_import_ref_rejects_non_importable_string() -> None:
    with pytest.raises(RefDiagnosticError):
        ImportRef.from_callable("not_a_module:func", node_id="plan", field="hook")


def test_as_import_ref_resolves_module_level_callables_and_strings() -> None:
    from_callable = as_import_ref(_fixtures.agent_prompt)
    from_string = as_import_ref("tests.arnold.patterns._fixtures:agent_prompt")

    assert from_callable.spec == from_string.spec
    assert from_callable.resolve() is _fixtures.agent_prompt


def test_as_hook_ref_rejects_anonymous_partials_with_context() -> None:
    from functools import partial

    def target(a: int, b: int) -> int:
        return a + b

    with pytest.raises(RefDiagnosticError, match="node 'plan' field 'reducer_ref'") as exc_info:
        as_hook_ref(partial(target, 1), node_id="plan", field="reducer_ref")

    assert "callable instances" in str(exc_info.value)


def test_pattern_constructors_route_hook_refs_through_workflow_adapters() -> None:
    from arnold.patterns import agent, branch

    plan_step = agent("plan", task="draft", prompt_ref=_fixtures.agent_prompt)
    decide_block = branch(
        "decide",
        condition_ref=_fixtures.decide_condition,
        then_id="plan",
        else_id="fallback",
    )

    assert plan_step.metadata["prompt_ref"] == "tests.arnold.patterns._fixtures:agent_prompt"
    assert decide_block.routes[0].condition_ref == "tests.arnold.patterns._fixtures:decide_condition"
