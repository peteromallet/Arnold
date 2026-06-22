from __future__ import annotations

import subprocess
import sys
import tempfile
import venv
from pathlib import Path
from zipfile import ZipFile

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.wheel_smoke
def test_wheel_has_arnold_entrypoint_and_py_typed() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        build_dir = tmp / "build"
        build_dir.mkdir()

        subprocess.run(
            [sys.executable, "-m", "pip", "wheel", "--no-deps", "-w", str(build_dir), str(REPO_ROOT)],
            check=True,
            capture_output=True,
            text=True,
        )

        wheels = list(build_dir.glob("*.whl"))
        assert wheels, "no wheel produced"
        wheel = wheels[0]

        with ZipFile(wheel) as whl:
            names = whl.namelist()
            assert "arnold-" in wheel.name
            assert any(name.endswith("arnold/py.typed") for name in names), "missing arnold/py.typed"
            assert any(
                name.endswith("arnold_pipelines/py.typed") for name in names
            ), "missing arnold_pipelines/py.typed"
            assert any(
                name.endswith("pipeline_ids.json") for name in names
            ), "missing pipeline_ids.json data"

        # Install into a clean venv and verify the console script works.
        venv_dir = tmp / "venv"
        venv.create(venv_dir, with_pip=True)
        pip = venv_dir / "bin" / "pip"
        arnold = venv_dir / "bin" / "arnold"

        subprocess.run([str(pip), "install", str(wheel)], check=True, capture_output=True)

        result = subprocess.run(
            [str(arnold), "workflow", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        assert "check" in result.stdout
        assert "run" in result.stdout
