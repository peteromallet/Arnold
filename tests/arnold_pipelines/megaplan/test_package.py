from __future__ import annotations

from pathlib import Path

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
    assert "compile_planning_pipeline" in megaplan.__all__


def test_build_pipeline_is_callable() -> None:
    assert callable(megaplan.build_pipeline)


def test_legacy_shim_re_exports() -> None:
    import arnold.pipelines.megaplan as legacy

    assert legacy.__name__ == "arnold.pipelines.megaplan"
    assert legacy.name == megaplan.name
    assert legacy.entrypoint == megaplan.entrypoint
    assert callable(legacy.build_pipeline)
