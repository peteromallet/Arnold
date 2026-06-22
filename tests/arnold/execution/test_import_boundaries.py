from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import Any

import pytest


FORBIDDEN_PREFIXES = (
    "arnold.workflow",
    "arnold.patterns",
    "arnold.pipelines.megaplan",
    "arnold_pipelines.megaplan",
    "megaplan",
)


def _is_forbidden(name: str) -> bool:
    return any(name == prefix or name.startswith(prefix + ".") for prefix in FORBIDDEN_PREFIXES)


def test_execution_imports_do_not_load_workflow_or_product_modules() -> None:
    before = set(sys.modules)
    import arnold.execution  # noqa: F401

    imported = set(sys.modules) - before
    forbidden = {name for name in imported if _is_forbidden(name)}

    assert forbidden == set()


def test_execution_source_has_no_forbidden_imports() -> None:
    package_root = Path(__file__).parents[3] / "arnold" / "execution"
    violations: dict[str, list[str]] = {}

    for source in sorted(package_root.rglob("*.py")):
        tree = ast.parse(source.read_text(encoding="utf-8"))
        imports: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names if _is_forbidden(alias.name))
            elif isinstance(node, ast.ImportFrom) and node.module and _is_forbidden(node.module):
                imports.append(node.module)
        if imports:
            violations[str(source.relative_to(package_root.parent.parent))] = imports

    assert violations == {}


def test_execution_public_namespace_is_narrow() -> None:
    import arnold.execution as execution

    assert set(execution.__all__) == {
        "ExecutionBackend",
        "ExecutionDiagnostic",
        "ExecutionLogger",
        "ExecutionRegistries",
        "ExecutionResult",
        "ExecutionState",
        "FileStateStore",
        "RunCheckpoint",
        "SkeletalBackend",
        "StateStore",
        "run",
    }


def test_run_rejects_dsl_pipeline_and_step_objects(tmp_path: Path) -> None:
    """arnold.execution.run() accepts only compiled WorkflowManifest instances."""

    from arnold.execution import run
    from arnold.workflow import Pipeline, Step

    pipeline = Pipeline(id="dsl-pipeline", version="v1", steps=(Step(id="s", kind="task"),))
    with pytest.raises(TypeError, match="WorkflowManifest"):
        run(pipeline, artifact_root=tmp_path)

    with pytest.raises(TypeError, match="WorkflowManifest"):
        run(Step(id="s", kind="task"), artifact_root=tmp_path)  # type: ignore[arg-type]


def test_execution_never_invokes_native_step_run(tmp_path: Path) -> None:
    """If a DSL Step is accidentally passed, run() must reject it before Step.run()."""

    from arnold.execution import run
    from arnold.workflow import Step

    calls: list[Any] = []

    class TrappingStep(Step):
        def run(self, **kwargs: Any) -> Any:
            calls.append(kwargs)
            raise AssertionError("native Step.run() must not be invoked by arnold.execution")

    step = TrappingStep(id="trap", kind="task")
    with pytest.raises(TypeError, match="WorkflowManifest"):
        run(step, artifact_root=tmp_path)  # type: ignore[arg-type]

    assert calls == []


def test_execution_source_contains_no_generator_frames() -> None:
    """The execution package must not execute workflow nodes inside generators."""

    package_root = Path(__file__).parents[3] / "arnold" / "execution"
    violations: list[str] = []
    for source in sorted(package_root.rglob("*.py")):
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Yield, ast.YieldFrom)):
                violations.append(str(source.relative_to(package_root.parent.parent)))
                break
    assert violations == [], f"yield statements found in execution package: {violations}"


def test_neutral_packages_have_no_forbidden_product_imports() -> None:
    """arnold/execution, arnold/kernel, and arnold/manifest stay product-neutral."""

    from arnold.conformance.workflow_manifest_runtime import scan_neutral_product_imports

    root = Path(__file__).parents[3]
    paths = (
        list((root / "arnold" / "execution").rglob("*.py"))
        + list((root / "arnold" / "kernel").rglob("*.py"))
        + list((root / "arnold" / "manifest").rglob("*.py"))
    )
    violations = scan_neutral_product_imports(paths)
    assert violations == {}, f"forbidden product imports: {violations}"
