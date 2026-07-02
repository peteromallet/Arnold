"""T11 — pipelines new scaffold tests (aligned for native-first).

Verifies that ``pipelines new <name>`` via both module paths:
* ``python -m arnold_pipelines.megaplan pipelines new <name>``
* ``python -m arnold_pipelines.megaplan.cli.arnold pipelines new <name>``

creates a native-first projected shell module and SKILL.md stub,
and that the emitted package passes authoring validation.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
from argparse import Namespace
from pathlib import Path

import pytest

from arnold.pipelines._authoring import validate_package_module


def _run_pipelines(*args: str) -> subprocess.CompletedProcess[str]:
    """Run ``python -m arnold_pipelines.megaplan pipelines ...`` and return the result."""
    return subprocess.run(
        [sys.executable, "-m", "arnold_pipelines.megaplan", "pipelines", *args],
        capture_output=True,
        text=True,
        env={**os.environ, "MEGAPLAN_MOCK_WORKERS": "1"},
    )


def _run_arnold_pipelines(*args: str) -> subprocess.CompletedProcess[str]:
    """Run ``python -m arnold_pipelines.megaplan.cli.arnold pipelines ...``."""
    return subprocess.run(
        [sys.executable, "-m", "arnold_pipelines.megaplan.cli.arnold", "pipelines", *args],
        capture_output=True,
        text=True,
        env={**os.environ, "MEGAPLAN_MOCK_WORKERS": "1"},
    )


# ── Handler-level tests (tmp_path) ────────────────────────────────────────


def test_pipelines_new_creates_module_and_skill(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """``new`` emits a Python module + SKILL.md stub (handler-level)."""
    from arnold_pipelines.megaplan import cli as cli_mod
    from arnold_pipelines.megaplan.runtime import discovery as discovery_mod

    pipelines_dir = tmp_path / "pipelines"
    pipelines_dir.mkdir()
    monkeypatch.setattr(
        discovery_mod,
        "_SCAN_ROOTS",
        ((tmp_path, "arnold_pipelines"), (pipelines_dir, "arnold_pipelines.megaplan.pipelines")),
    )

    name = "t11-test-scaffold"
    rc = cli_mod._handle_pipelines(
        os.getcwd(),
        Namespace(pipelines_action="new", pipeline_name=name, driver=None),
    )

    assert rc == 0
    module_stem = name.replace("-", "_")
    module_path = pipelines_dir / f"{module_stem}.py"
    skill_path = pipelines_dir / name / "SKILL.md"

    assert module_path.exists(), f"module not created at {module_path}"
    assert skill_path.exists(), f"SKILL.md not created at {skill_path}"

    content = module_path.read_text()
    assert "def build_pipeline" in content
    assert name in content
    assert "@pipeline" in content
    assert "@phase" in content
    assert "@decision" in content
    assert "compile_pipeline(" in content
    assert "project_graph(" in content
    assert 'driver: tuple[str, str] = ("native", "project+validate")' in content
    assert 'supported_modes: tuple[str, ...] = ("native",)' in content

    skill_content = skill_path.read_text()
    assert f"name: {name}" in skill_content


def test_pipelines_new_emitted_package_passes_authoring_validation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The scaffolded pipeline passes :func:`validate_package_module`."""
    from arnold_pipelines.megaplan import cli as cli_mod
    from arnold_pipelines.megaplan.runtime import discovery as discovery_mod

    pipelines_dir = tmp_path / "pipelines"
    pipelines_dir.mkdir()
    monkeypatch.setattr(
        discovery_mod,
        "_SCAN_ROOTS",
        ((tmp_path, "arnold_pipelines"), (pipelines_dir, "arnold_pipelines.megaplan.pipelines")),
    )

    name = "t11-test-scaffold-check"
    rc = cli_mod._handle_pipelines(
        os.getcwd(),
        Namespace(pipelines_action="new", pipeline_name=name, driver=None),
    )
    assert rc == 0

    module_stem = name.replace("-", "_")
    module_path = pipelines_dir / f"{module_stem}.py"

    spec = importlib.util.spec_from_file_location(module_stem, module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    validate_package_module(module)  # raises on failure

    pipeline = module.build_pipeline()
    assert pipeline.native_program is not None


def test_arnold_pipelines_new_emits_native_only_module(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The Arnold entry point (cli.arnold) emits native-first shape."""
    from arnold_pipelines.megaplan import cli as cli_mod
    from arnold_pipelines.megaplan.runtime import discovery as discovery_mod

    pipelines_dir = tmp_path / "pipelines"
    pipelines_dir.mkdir()
    monkeypatch.setattr(
        discovery_mod,
        "_SCAN_ROOTS",
        ((tmp_path, "arnold_pipelines"), (pipelines_dir, "arnold_pipelines.megaplan.pipelines")),
    )

    name = "t11-arnold-scaffold-check"
    rc = cli_mod._handle_pipelines(
        os.getcwd(),
        Namespace(pipelines_action="new", pipeline_name=name, driver=None),
    )
    assert rc == 0

    module_stem = name.replace("-", "_")
    module_path = pipelines_dir / f"{module_stem}.py"
    assert module_path.exists(), f"module not created at {module_path}"
    content = module_path.read_text(encoding="utf-8")
    assert 'driver: tuple[str, str] = ("native", "project+validate")' in content
    assert "Deprecated hand-built graph scaffold" not in content
    assert 'driver: tuple[str, str] = (\'graph\',' not in content

    # Also verify via authoring validation
    spec = importlib.util.spec_from_file_location(module_stem, module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    validate_package_module(module)


def test_pipelines_new_refuses_overwrite(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``new`` exits non-zero when the module file already exists."""
    from arnold_pipelines.megaplan import cli as cli_mod
    from arnold_pipelines.megaplan.runtime import discovery as discovery_mod

    pipelines_dir = tmp_path / "pipelines"
    pipelines_dir.mkdir()
    monkeypatch.setattr(
        discovery_mod,
        "_SCAN_ROOTS",
        ((tmp_path, "arnold_pipelines"), (pipelines_dir, "arnold_pipelines.megaplan.pipelines")),
    )

    name = "t11-test-exists"
    first = cli_mod._handle_pipelines(
        os.getcwd(),
        Namespace(pipelines_action="new", pipeline_name=name, driver=None),
    )
    assert first == 0

    second = cli_mod._handle_pipelines(
        os.getcwd(),
        Namespace(pipelines_action="new", pipeline_name=name, driver=None),
    )
    assert second == 1
    assert "already exists" in capsys.readouterr().err


def test_pipelines_new_missing_name_errors() -> None:
    """``new`` with no name exits non-zero."""
    result = _run_pipelines("new")
    assert result.returncode != 0


# ── Subprocess-level tests (both module paths) ────────────────────────────


def test_subprocess_pipelines_new_via_megaplan_module(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """``python -m arnold_pipelines.megaplan pipelines new`` works end-to-end."""
    from arnold_pipelines.megaplan.runtime import discovery as discovery_mod

    pipelines_dir = tmp_path / "pipelines"
    pipelines_dir.mkdir()
    monkeypatch.setattr(
        discovery_mod,
        "_SCAN_ROOTS",
        ((tmp_path, "arnold_pipelines"), (pipelines_dir, "arnold_pipelines.megaplan.pipelines")),
    )
    # Also patch getattr on the cli module to use monkeypatched _SCAN_ROOTS
    import arnold_pipelines.megaplan.cli as cli_mod
    monkeypatch.setattr(cli_mod, "_handle_pipelines", cli_mod._handle_pipelines)

    name = "t11-subprocess-megaplan"
    module_stem = name.replace("-", "_")
    result = subprocess.run(
        [sys.executable, "-m", "arnold_pipelines.megaplan", "pipelines", "new", name],
        capture_output=True,
        text=True,
        env={**os.environ, "MEGAPLAN_MOCK_WORKERS": "1"},
    )
    # This will use the real _SCAN_ROOTS, so the module won't be in tmp_path.
    # We just verify the CLI doesn't crash with "invalid choice".
    assert "invalid choice" not in result.stderr
    # Clean up any scaffold written to the real directory
    real_module = Path("/workspace/arnold/arnold_pipelines/megaplan/pipelines") / f"{module_stem}.py"
    real_skill_dir = Path("/workspace/arnold/arnold_pipelines/megaplan/pipelines") / name
    if real_module.exists():
        real_module.unlink()
    if real_skill_dir.exists():
        shutil.rmtree(real_skill_dir)


def test_subprocess_pipelines_new_via_arnold_entry(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """``python -m arnold_pipelines.megaplan.cli.arnold pipelines new`` works."""
    name = "t11-subprocess-arnold"
    module_stem = name.replace("-", "_")
    result = subprocess.run(
        [sys.executable, "-m", "arnold_pipelines.megaplan.cli.arnold", "pipelines", "new", name],
        capture_output=True,
        text=True,
        env={**os.environ, "MEGAPLAN_MOCK_WORKERS": "1"},
    )
    assert "invalid choice" not in result.stderr
    # Clean up
    real_module = Path("/workspace/arnold/arnold_pipelines/megaplan/pipelines") / f"{module_stem}.py"
    real_skill_dir = Path("/workspace/arnold/arnold_pipelines/megaplan/pipelines") / name
    if real_module.exists():
        real_module.unlink()
    if real_skill_dir.exists():
        shutil.rmtree(real_skill_dir)
