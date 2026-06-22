from __future__ import annotations

import sys
from pathlib import Path

import pytest

import arnold.patterns as patterns
import arnold.workflow as workflow
from arnold.workflow import check_neutral_import_boundary


PRODUCT_FORBIDDEN_PREFIXES = (
    "arnold.execution",
    "arnold.pipelines.megaplan",
    "arnold_pipelines.megaplan",
    "megaplan",
)


def _is_forbidden_module(name: str) -> bool:
    return name == "arnold.execution" or name.startswith("arnold.execution.") or any(
        name == prefix or name.startswith(prefix + ".") for prefix in PRODUCT_FORBIDDEN_PREFIXES[1:]
    )


def test_workflow_package_does_not_import_execution_or_product_modules() -> None:
    before = set(sys.modules.keys())
    import arnold.workflow  # noqa: F401 - importing to inspect side effects
    imported = set(sys.modules.keys()) - before

    forbidden = {name for name in imported if _is_forbidden_module(name)}
    assert not forbidden, f"arnold.workflow imported forbidden modules: {forbidden}"


def test_patterns_package_does_not_import_execution_or_product_modules() -> None:
    before = set(sys.modules.keys())
    import arnold.patterns  # noqa: F401
    imported = set(sys.modules.keys()) - before

    forbidden = {name for name in imported if _is_forbidden_module(name)}
    assert not forbidden, f"arnold.patterns imported forbidden modules: {forbidden}"


def test_neutral_source_files_have_no_forbidden_imports() -> None:
    root = Path(__file__).parent.parent.parent.parent
    manifest_sources = list((root / "arnold" / "manifest").rglob("*.py"))
    workflow_sources = list((root / "arnold" / "workflow").rglob("*.py"))
    patterns_sources = list((root / "arnold" / "patterns").rglob("*.py"))
    violations = check_neutral_import_boundary(manifest_sources + workflow_sources + patterns_sources)

    assert violations == {}, f"forbidden product imports found: {violations}"


def test_workflow_has_explicit_all_and_stability_markers() -> None:
    assert hasattr(workflow, "__all__")
    assert hasattr(workflow, "PUBLIC_EXPORTS")
    assert hasattr(workflow, "PROVISIONAL_EXPORTS")
    assert hasattr(workflow, "INTERNAL_EXPORTS")
    assert set(workflow.__all__).issuperset(set(workflow.PUBLIC_EXPORTS))


def test_patterns_has_explicit_all_and_stability_markers() -> None:
    assert hasattr(patterns, "__all__")
    assert hasattr(patterns, "PUBLIC_EXPORTS")
    assert hasattr(patterns, "PROVISIONAL_EXPORTS")
    assert hasattr(patterns, "INTERNAL_EXPORTS")
    assert set(patterns.__all__).issuperset(set(patterns.PUBLIC_EXPORTS))


def test_workflow_public_namespace_has_no_banned_authoring_surfaces() -> None:
    banned = {"PipelineBuilder", "Stage", "Edge", "stage", "step", "builder", "pipeline"}
    public_names = set(workflow.__all__)

    assert banned.isdisjoint(public_names)


def test_patterns_public_namespace_has_no_live_object_capture_helpers() -> None:
    banned = {"PipelineBuilder", "Stage", "Edge"}
    public_names = set(patterns.__all__)

    assert banned.isdisjoint(public_names)
