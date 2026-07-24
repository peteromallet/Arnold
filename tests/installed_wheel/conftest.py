from __future__ import annotations

import subprocess
import sys
import venv
from dataclasses import dataclass
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class InstalledWheel:
    python: Path
    arnold: Path
    wheel: Path


@pytest.fixture(scope="module")
def installed_wheel(tmp_path_factory: pytest.TempPathFactory) -> InstalledWheel:
    tmp = tmp_path_factory.mktemp("installed-wheel")
    wheel_dir = tmp / "wheelhouse"
    wheel_dir.mkdir()

    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            "--no-deps",
            "-w",
            str(wheel_dir),
            str(REPO_ROOT),
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    wheels = sorted(wheel_dir.glob("*.whl"))
    assert len(wheels) == 1, (
        f"expected one built wheel, found {[wheel.name for wheel in wheels]}"
    )

    venv_dir = tmp / "venv"
    venv.create(venv_dir, with_pip=True)
    python = venv_dir / "bin" / "python"
    pip = venv_dir / "bin" / "pip"
    arnold = venv_dir / "bin" / "arnold"

    subprocess.run(
        [str(pip), "install", str(wheels[0])],
        check=True,
        capture_output=True,
        text=True,
    )

    assert python.exists(), f"missing venv Python at {python}"
    assert arnold.exists(), f"missing arnold entrypoint at {arnold}"

    return InstalledWheel(python=python, arnold=arnold, wheel=wheels[0])
