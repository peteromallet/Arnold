from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from arnold.conformance.deleted_surfaces import DELETED_IMPORT_MODULES


def test_built_wheel_imports_workflow_and_kernel(installed_wheel) -> None:
    result = subprocess.run(
        [
            str(installed_wheel.python),
            "-c",
            "import arnold.workflow, arnold.kernel; print('ok')",
        ],
        check=True,
        text=True,
        capture_output=True,
    )

    assert result.stdout.strip() == "ok"


def test_installed_arnold_workflow_entrypoint_starts(installed_wheel) -> None:
    result = subprocess.run(
        [
            str(installed_wheel.arnold),
            "workflow",
            "--help",
        ],
        check=True,
        text=True,
        capture_output=True,
    )

    assert "usage: arnold workflow" in result.stdout


def test_editable_install_deleted_inventory_modules_fail(tmp_path) -> None:
    repo = Path(__file__).resolve().parents[2]
    venv_dir = tmp_path / "editable-venv"

    subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)
    python = venv_dir / "bin" / "python"

    subprocess.run(
        [str(python), "-m", "pip", "install", "-e", ".", "--quiet"],
        cwd=repo,
        check=True,
    )
    probe = (
        "import importlib\n"
        f"deleted = {DELETED_IMPORT_MODULES!r}\n"
        "for name in deleted:\n"
        "    try:\n"
        "        importlib.import_module(name)\n"
        "    except ModuleNotFoundError:\n"
        "        pass\n"
        "    else:\n"
        "        raise SystemExit(f'deleted module {name!r} is importable')\n"
        "print('ok')\n"
    )
    result = subprocess.run(
        [str(python), "-c", probe],
        cwd=repo,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "ok"
