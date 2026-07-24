from __future__ import annotations

import subprocess
import sys
import tarfile
import tempfile
import venv
from pathlib import Path
from zipfile import ZipFile

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _run_checked(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(args, capture_output=True, text=True, **kwargs)
    if result.returncode != 0:
        raise AssertionError(
            f"command failed ({result.returncode}): {' '.join(args)}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    return result


@pytest.mark.wheel_smoke
def test_wheel_has_arnold_entrypoint_and_py_typed() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        build_dir = tmp / "build"
        build_dir.mkdir()
        sdist_dir = tmp / "sdist"
        sdist_dir.mkdir()

        _run_checked(
            [sys.executable, "-m", "pip", "wheel", "--no-deps", "-w", str(build_dir), str(REPO_ROOT)],
        )
        _run_checked(
            [sys.executable, "-m", "build", "--sdist", "-o", str(sdist_dir), str(REPO_ROOT)],
        )

        wheels = list(build_dir.glob("*.whl"))
        assert wheels, "no wheel produced"
        wheel = wheels[0]

        sdists = list(sdist_dir.glob("*.tar.gz"))
        assert sdists, "no sdist produced"
        sdist = sdists[0]

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
            assert any(
                "arnold_pipelines/megaplan/data/_composed/" in name for name in names
            ), "missing composed rules"
            assert not any(
                "arnold/pipelines/megaplan/data/" in name for name in names
            ), "legacy generated data still packaged"

        with tarfile.open(sdist, "r:gz") as tar:
            sdist_names = tar.getnames()
            assert any(name.endswith("pyproject.toml") for name in sdist_names)

        # Install into a clean venv and verify the console script works.
        venv_dir = tmp / "venv"
        venv.create(venv_dir, with_pip=True)
        pip = venv_dir / "bin" / "pip"
        arnold = venv_dir / "bin" / "arnold"
        python = venv_dir / "bin" / "python"

        subprocess.run([str(pip), "install", str(wheel)], check=True, capture_output=True)

        result = subprocess.run(
            [str(arnold), "workflow", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        assert "check" in result.stdout
        assert "run" in result.stdout

        # Workflow CLI can validate and manifest a shipped pipeline from the wheel.
        for subcommand in ("check", "manifest", "dry-run"):
            result = subprocess.run(
                [
                    str(arnold),
                    "workflow",
                    subcommand,
                    "--module",
                    "arnold_pipelines.evidence_pack:build_pipeline",
                ],
                capture_output=True,
                text=True,
            )
            assert result.returncode == 0, (
                f"arnold workflow {subcommand} failed: {result.stderr}"
            )
            if subcommand in {"check", "manifest"}:
                assert "sha256:" in result.stdout
