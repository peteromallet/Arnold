from __future__ import annotations

from pathlib import Path

import pytest

import arnold_pipelines
import arnold_pipelines.megaplan as megaplan


def test_package_is_importable() -> None:
    assert megaplan.__name__ == "arnold_pipelines.megaplan"


def test_py_typed_present() -> None:
    root = Path(__file__).parents[3]
    assert (root / "arnold_pipelines" / "py.typed").exists()
    assert (root / "arnold_pipelines" / "__init__.py").exists()


def test_package_metadata() -> None:
    assert megaplan.name == "megaplan"
    assert "Canonical Megaplan" in megaplan.description
    assert megaplan.entrypoint == "build_pipeline"
    assert megaplan.arnold_api_version == "1.0"
    assert "planning" in megaplan.capabilities


def test_public_exports_defined() -> None:
    assert hasattr(megaplan, "__all__")
    assert "build_pipeline" in megaplan.__all__
    assert "build_and_compile_pipeline" in megaplan.__all__
    # Removed legacy names must NOT appear in __all__
    assert "compile_planning_pipeline" not in megaplan.__all__
    assert "build_legacy_pipeline" not in megaplan.__all__
    assert "WorkflowManifest" not in megaplan.__all__


def test_build_pipeline_is_callable() -> None:
    assert callable(megaplan.build_pipeline)


def test_legacy_package_is_not_importable() -> None:
    with pytest.raises(ModuleNotFoundError):
        import arnold.pipelines.megaplan  # noqa: F401


# ── Absence tests: removed legacy names must not be exposed ───────────────

_REMOVED_NAMES = (
    "build_legacy_pipeline",
    "compile_planning_pipeline",
    "WorkflowManifest",
)


def test_hasattr_removed_names_false() -> None:
    """hasattr(megaplan, <removed>) must return False for every removed name."""
    for name in _REMOVED_NAMES:
        assert not hasattr(megaplan, name), (
            f"hasattr(megaplan, {name!r}) must be False"
        )


def test_getattr_removed_names_raises_attribute_error() -> None:
    """getattr(megaplan, <removed>) must raise AttributeError for every removed name."""
    for name in _REMOVED_NAMES:
        with pytest.raises(AttributeError, match=name):
            getattr(megaplan, name)


def test_removed_names_not_directly_importable() -> None:
    """Direct top-level imports of removed names must raise ImportError."""
    for name in _REMOVED_NAMES:
        with pytest.raises(ImportError):
            exec(f"from arnold_pipelines.megaplan import {name}")


def test_build_pipeline_returns_pipeline_type() -> None:
    """build_pipeline() must return arnold.workflow.dsl.Pipeline."""
    from arnold.workflow.dsl import Pipeline

    pipeline = megaplan.build_pipeline()
    assert isinstance(pipeline, Pipeline), (
        f"build_pipeline() returned {type(pipeline)}, expected Pipeline"
    )


def test_compiler_smoke_build_and_compile() -> None:
    """compile_pipeline(build_pipeline()) must produce a valid manifest."""
    from arnold.workflow.compiler import compile_pipeline

    pipeline = megaplan.build_pipeline()
    manifest = compile_pipeline(pipeline)
    assert manifest.id == "megaplan"
    assert manifest.manifest_hash is not None


# ── Absence tests: deleted submodule imports ────────────────────────────

_DELETED_SUBMODULE_IMPORTS = (
    "arnold_pipelines.megaplan._pipeline",
    "arnold_pipelines.megaplan._pipeline.builder",
    "arnold_pipelines.megaplan._pipeline.runtime",
    "arnold_pipelines.megaplan._pipeline.dispatch",
    "arnold_pipelines.megaplan._pipeline.types",
    "arnold_pipelines.megaplan.stages",
    "arnold_pipelines.megaplan.stages.inprocess_step",
    "arnold_pipelines.megaplan._compatibility",
)


def test_deleted_submodules_raise_module_not_found() -> None:
    """Importing deleted submodules via importlib must raise ModuleNotFoundError."""
    import importlib

    for mod_name in _DELETED_SUBMODULE_IMPORTS:
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module(mod_name)


def test_deleted_submodules_not_importable_via_from() -> None:
    """from arnold_pipelines.megaplan import <deleted_subpackage> must raise ImportError."""
    for subpkg in ("_pipeline", "stages"):
        with pytest.raises(ImportError):
            exec(f"from arnold_pipelines.megaplan import {subpkg}")


# ── Absence tests: sys.modules prefix leakage ───────────────────────────


def test_sys_modules_free_of_deleted_prefixes_after_package_import() -> None:
    """After importing arnold_pipelines.megaplan, sys.modules must not contain
    any key starting with the deleted _pipeline, stages, or _compatibility
    prefixes."""
    import sys

    # Re-import to guarantee the package is loaded
    import arnold_pipelines.megaplan  # noqa: F401, F811

    deleted_prefixes = (
        "arnold_pipelines.megaplan._pipeline",
        "arnold_pipelines.megaplan.stages",
        "arnold_pipelines.megaplan._compatibility",
    )
    leaked = [
        key
        for key in sys.modules
        if any(key == prefix or key.startswith(prefix + ".") for prefix in deleted_prefixes)
    ]
    assert not leaked, f"sys.modules leaks deleted prefixes: {leaked}"


# ── Absence tests: representative deleted stage-class symbols ────────────


def test_deleted_stage_classes_not_exposed() -> None:
    """Stage classes from the deleted stages/ package must not be accessible
    through megaplan or megaplan.pipeline."""
    import arnold_pipelines.megaplan.pipeline as pipeline_mod

    deleted_stage_classes = (
        "InProcessHandlerStep",
        "HandlerStep",
        "PrepStep",
        "PlanStep",
        "CritiqueStep",
        "GateStep",
        "ReviseStep",
        "FinalizeStep",
        "ExecuteStep",
        "ReviewStep",
        "TiebreakerStep",
    )
    for cls_name in deleted_stage_classes:
        assert not hasattr(megaplan, cls_name), (
            f"megaplan.{cls_name} must not exist"
        )
        assert not hasattr(pipeline_mod, cls_name), (
            f"pipeline.{cls_name} must not exist"
        )
