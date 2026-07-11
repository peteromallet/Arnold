from __future__ import annotations

from pathlib import Path

from arnold_pipelines.megaplan.workflows import (
    _extend_runtime_workflow_path,
    _runtime_target_workflows_path,
)


def _mirror_package(tmp_path: Path, *, with_target: bool = True) -> tuple[Path, Path]:
    project = tmp_path / "project"
    mirror = (
        project
        / ".megaplan"
        / "runtime"
        / "editable-engine"
        / "arnold_pipelines"
        / "megaplan"
        / "workflows"
    )
    mirror.mkdir(parents=True)
    package_file = mirror / "__init__.py"
    package_file.write_text("", encoding="utf-8")
    target = project / "arnold_pipelines" / "megaplan" / "workflows"
    if with_target:
        target.mkdir(parents=True)
    return package_file, target


def test_runtime_mirror_exposes_target_workflows_as_fallback(tmp_path: Path) -> None:
    package_file, target = _mirror_package(tmp_path)

    assert _runtime_target_workflows_path(package_file) == target.resolve()
    paths = [str(package_file.parent)]
    assert _extend_runtime_workflow_path(paths, package_file) is True
    assert paths == [str(package_file.parent), str(target.resolve())]


def test_runtime_workflow_overlay_is_idempotent(tmp_path: Path) -> None:
    package_file, target = _mirror_package(tmp_path)
    paths = [str(package_file.parent), str(target.resolve())]

    assert _extend_runtime_workflow_path(paths, package_file) is True
    assert paths.count(str(target.resolve())) == 1


def test_non_mirror_package_does_not_gain_an_overlay(tmp_path: Path) -> None:
    package = tmp_path / "arnold_pipelines" / "megaplan" / "workflows"
    package.mkdir(parents=True)
    package_file = package / "__init__.py"
    package_file.write_text("", encoding="utf-8")
    paths = [str(package)]

    assert _runtime_target_workflows_path(package_file) is None
    assert _extend_runtime_workflow_path(paths, package_file) is False
    assert paths == [str(package)]


def test_missing_target_workflows_does_not_gain_an_overlay(tmp_path: Path) -> None:
    package_file, _target = _mirror_package(tmp_path, with_target=False)
    paths = [str(package_file.parent)]

    assert _runtime_target_workflows_path(package_file) is None
    assert _extend_runtime_workflow_path(paths, package_file) is False
    assert paths == [str(package_file.parent)]
