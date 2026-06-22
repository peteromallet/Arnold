"""T15 — pipelines new scaffold tests.

Verifies that ``pipelines new <name>``:
* Creates a build_pipeline module file (``arnold/pipelines/megaplan/pipelines/<stem>.py``)
* Creates a SKILL.md stub (``arnold/pipelines/megaplan/pipelines/<cli-name>/SKILL.md``)
* The emitted package passes ``pipelines check`` (exit 0).
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest


_PIPELINES_DIR = (
    Path(__file__).resolve().parent.parent / "arnold" / "pipelines" / "megaplan" / "pipelines"
)


def _run_pipelines(*args: str) -> subprocess.CompletedProcess[str]:
    """Run ``python -m arnold_pipelines.megaplan pipelines ...`` and return the result."""
    return subprocess.run(
        [sys.executable, "-m", "arnold_pipelines.megaplan", "pipelines", *args],
        capture_output=True,
        text=True,
        env={**__import__("os").environ, "MEGAPLAN_MOCK_WORKERS": "1"},
    )


def _run_arnold_pipelines(*args: str) -> subprocess.CompletedProcess[str]:
    """Run ``python -m arnold_pipelines.megaplan.cli.arnold pipelines ...``."""
    return subprocess.run(
        [sys.executable, "-m", "arnold_pipelines.megaplan.cli.arnold", "pipelines", *args],
        capture_output=True,
        text=True,
        env={**__import__("os").environ, "MEGAPLAN_MOCK_WORKERS": "1"},
    )


@pytest.fixture
def clean_scaffold():
    """Remove any leftover scaffold artifacts from prior runs."""
    to_remove: list[Path] = []
    yield to_remove
    for p in to_remove:
        if p.is_file():
            p.unlink(missing_ok=True)
        elif p.is_dir():
            shutil.rmtree(p, ignore_errors=True)


def test_pipelines_new_creates_module_and_skill(clean_scaffold: list[Path]):
    """``new`` emits a Python module + SKILL.md stub."""
    name = "t15-test-scaffold"
    module_stem = name.replace("-", "_")
    module_path = _PIPELINES_DIR / f"{module_stem}.py"
    skill_dir = _PIPELINES_DIR / name
    skill_path = skill_dir / "SKILL.md"

    clean_scaffold.extend([module_path, skill_dir])

    # Ensure clean state.
    if module_path.exists():
        module_path.unlink()
    if skill_dir.exists():
        shutil.rmtree(skill_dir)

    result = _run_pipelines("new", name)
    assert result.returncode == 0, f"stderr: {result.stderr}"

    assert module_path.exists(), f"module not created at {module_path}"
    assert skill_path.exists(), f"SKILL.md not created at {skill_path}"

    content = module_path.read_text()
    assert "def build_pipeline" in content
    assert name in content

    skill_content = skill_path.read_text()
    assert f"name: {name}" in skill_content


def test_pipelines_new_emitted_package_passes_check(clean_scaffold: list[Path]):
    """The scaffolded pipeline passes ``pipelines check`` (exit 0)."""
    name = "t15-test-scaffold-check"
    module_stem = name.replace("-", "_")
    module_path = _PIPELINES_DIR / f"{module_stem}.py"
    skill_dir = _PIPELINES_DIR / name

    clean_scaffold.extend([module_path, skill_dir])

    if module_path.exists():
        module_path.unlink()
    if skill_dir.exists():
        shutil.rmtree(skill_dir)

    # Scaffold.
    result = _run_pipelines("new", name)
    assert result.returncode == 0, f"new failed: {result.stderr}"

    # Check — must pass (GREEN).
    check_result = _run_pipelines("check", name)
    assert check_result.returncode == 0, (
        f"check failed (exit {check_result.returncode}):\n"
        f"stdout: {check_result.stdout}\n"
        f"stderr: {check_result.stderr}"
    )
    assert name in check_result.stdout


def test_arnold_pipelines_new_driver_graph_emits_checkable_module(
    clean_scaffold: list[Path],
):
    """The documented Arnold scaffold command exists and emits a checkable module."""
    name = "t14-arnold-scaffold-check"
    module_stem = name.replace("-", "_")
    module_path = _PIPELINES_DIR / f"{module_stem}.py"
    skill_dir = _PIPELINES_DIR / name

    clean_scaffold.extend([module_path, skill_dir])

    if module_path.exists():
        module_path.unlink()
    if skill_dir.exists():
        shutil.rmtree(skill_dir)

    result = _run_arnold_pipelines("new", name, "--driver", "graph")
    assert result.returncode == 0, f"new failed: {result.stderr}"
    assert module_path.exists(), f"module not created at {module_path}"
    assert 'driver: tuple[str, str] = (\'graph\', "dispatch+emit")' in module_path.read_text(
        encoding="utf-8"
    )

    check_result = _run_pipelines("check", name)
    assert check_result.returncode == 0, (
        f"check failed (exit {check_result.returncode}):\n"
        f"stdout: {check_result.stdout}\n"
        f"stderr: {check_result.stderr}"
    )
    assert name in check_result.stdout


def test_pipelines_new_refuses_overwrite(clean_scaffold: list[Path]):
    """``new`` exits non-zero when the module file already exists."""
    name = "t15-test-exists"
    module_stem = name.replace("-", "_")
    module_path = _PIPELINES_DIR / f"{module_stem}.py"
    skill_dir = _PIPELINES_DIR / name

    clean_scaffold.extend([module_path, skill_dir])

    if module_path.exists():
        module_path.unlink()
    if skill_dir.exists():
        shutil.rmtree(skill_dir)

    # First scaffold succeeds.
    result1 = _run_pipelines("new", name)
    assert result1.returncode == 0

    # Second scaffold on same name must fail.
    result2 = _run_pipelines("new", name)
    assert result2.returncode != 0, "should refuse to overwrite existing module"
    assert "already exists" in result2.stderr


def test_pipelines_new_missing_name_errors():
    """``new`` with no name exits non-zero."""
    result = _run_pipelines("new")
    # argparse catches it first (exit 2), but our handler also checks.
    assert result.returncode != 0
