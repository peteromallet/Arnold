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
