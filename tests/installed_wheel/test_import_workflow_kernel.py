from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from arnold.conformance.deleted_surfaces import DELETED_IMPORT_MODULES


def test_editable_install_imports_workflow_and_kernel() -> None:
    repo = Path(__file__).resolve().parents[2]

    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-e", ".", "--quiet"],
        cwd=repo,
        check=True,
    )
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import arnold.workflow, arnold.kernel; print('ok')",
        ],
        cwd=repo,
        check=True,
        text=True,
        capture_output=True,
    )

    assert result.stdout.strip() == "ok"


def test_editable_install_deleted_inventory_modules_fail() -> None:
    repo = Path(__file__).resolve().parents[2]

    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-e", ".", "--quiet"],
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
        [sys.executable, "-c", probe],
        cwd=repo,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "ok"
