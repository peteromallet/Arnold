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
