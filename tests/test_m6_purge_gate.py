from __future__ import annotations

from pathlib import Path

from scripts.m6_purge_gate import check_m6_purge


def test_m6_purge_gate_passes_when_product_root_is_absent(tmp_path: Path) -> None:
    assert check_m6_purge(repo_root=tmp_path) == []


def test_m6_purge_gate_fails_legacy_product_dirs_and_exports(tmp_path: Path) -> None:
    product = tmp_path / "arnold_pipelines" / "megaplan"
    (product / "_pipeline").mkdir(parents=True)
    (product / "stages").mkdir()
    build_legacy = "build_" + "legacy_pipeline"
    compile_planning = "compile_" + "planning_pipeline"
    (product / "pipeline.py").write_text(
        f"def {build_legacy}():\n    pass\n"
        f"__all__ = [{compile_planning!r}]\n",
        encoding="utf-8",
    )
    (product / "__init__.py").write_text(
        f"from .pipeline import {compile_planning}\n",
        encoding="utf-8",
    )
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_pipeline.py").write_text(
        f"def test_legacy():\n    assert {build_legacy}\n",
        encoding="utf-8",
    )

    errors = check_m6_purge(repo_root=tmp_path)

    assert any("_pipeline" in error for error in errors)
    assert any("stages" in error for error in errors)
    assert any("defines legacy constructors" in error for error in errors)
    assert any("exports legacy constructors" in error for error in errors)
    assert any("references legacy constructors in tests" in error for error in errors)
