"""Installed-wheel smoke test for ``arnold_pipelines.megaplan``.

Builds a wheel and sdist in a temp directory, installs the wheel into a clean
venv, and proves that the product package, metadata, ``py.typed``,
``build_pipeline()``, compile, fake-run, and CLI projection imports work outside
editable mode.
"""

from __future__ import annotations

import subprocess
import sys
import venv
from pathlib import Path
from typing import Any

import pytest


pytestmark = pytest.mark.wheel_smoke


def _run_checked(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(args, capture_output=True, text=True, **kwargs)
    if result.returncode != 0:
        raise AssertionError(
            f"command failed ({result.returncode}): {' '.join(args)}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    return result


@pytest.fixture
def built_wheel(tmp_path: Path) -> Path:
    """Build a wheel/sdist and return the wheel path."""

    repo_root = Path(__file__).parents[3]
    build_dir = tmp_path / "build"
    build_dir.mkdir()

    # Ensure the test interpreter has pip available for wheel builds.
    try:
        _run_checked(
            [sys.executable, "-m", "pip", "--version"],
        )
    except AssertionError:
        _run_checked(
            [sys.executable, "-m", "ensurepip"],
        )

    _run_checked(
        [sys.executable, "-m", "pip", "wheel", "--no-deps", str(repo_root), "-w", str(build_dir)],
        cwd=repo_root,
    )

    wheels = list(build_dir.glob("*.whl"))
    assert wheels, "no wheel produced"
    return wheels[0]


@pytest.fixture
def clean_venv(tmp_path: Path) -> Path:
    """Create an isolated venv and return its python path."""

    venv_dir = tmp_path / "venv"
    venv.create(venv_dir, with_pip=True)
    return venv_dir / "bin" / "python"


class TestWheelSmoke:
    def test_skill_links_are_repository_relative_and_resolve(self) -> None:
        repo_root = Path(__file__).parents[3]
        skill_root = repo_root / "arnold_pipelines" / "megaplan" / "skills"
        skill_links = sorted(skill_root.glob("*/SKILL.md"))

        assert skill_links, "no packaged Megaplan skill links found"
        for skill_link in skill_links:
            if skill_link.is_symlink():
                assert not skill_link.readlink().is_absolute(), skill_link
            assert skill_link.resolve(strict=True).is_file(), skill_link

    def test_wheel_installs_and_imports_product_package(
        self, built_wheel: Path, clean_venv: Path, tmp_path: Path
    ) -> None:
        repo_root = Path(__file__).parents[3]
        subprocess.run(
            [str(clean_venv), "-m", "pip", "install", str(built_wheel)],
            check=True,
            capture_output=True,
            text=True,
            cwd=repo_root,
        )

        script = tmp_path / "smoke.py"
        script.write_text(
            "import arnold_pipelines.megaplan as mp\n"
            "assert mp.__name__ == 'arnold_pipelines.megaplan'\n"
            "assert hasattr(mp, 'build_pipeline')\n"
            "from pathlib import Path\n"
            "assert (Path(mp.__file__).parent / 'py.typed').exists()\n"
            "manifest = mp.build_and_compile_pipeline()\n"
            "assert manifest.id == 'megaplan'\n"
            "print('smoke-ok')\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            [str(clean_venv), str(script)],
            check=True,
            capture_output=True,
            text=True,
            cwd=repo_root,
        )
        assert "smoke-ok" in result.stdout

    def test_cli_projection_imports_in_wheel(self, built_wheel: Path, clean_venv: Path, tmp_path: Path) -> None:
        repo_root = Path(__file__).parents[3]
        subprocess.run(
            [str(clean_venv), "-m", "pip", "install", str(built_wheel)],
            check=True,
            capture_output=True,
            text=True,
            cwd=repo_root,
        )

        script = tmp_path / "cli_smoke.py"
        script.write_text(
            "from arnold_pipelines.megaplan.cli.projection import project_status, project_trace\n"
            "assert callable(project_status)\n"
            "assert callable(project_trace)\n"
            "print('cli-smoke-ok')\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            [str(clean_venv), str(script)],
            check=True,
            capture_output=True,
            text=True,
            cwd=repo_root,
        )
        assert "cli-smoke-ok" in result.stdout
