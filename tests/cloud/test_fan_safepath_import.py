"""Tests for fan.py's PYTHONSAFEPATH-safe sibling-module import.

The babysitter runs fan.py from a managed-agent env that sets PYTHONSAFEPATH
(and/or passes -P), which strips the script's own directory from sys.path.
Without the explicit sys.path shim, ``from fan_process import ...`` at module
top fails with ModuleNotFoundError and the swarm can never start.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys

FAN_DIR = (
    pathlib.Path(__file__).resolve().parents[2]
    / "arnold_pipelines"
    / "megaplan"
    / "skills"
    / "subagent-launcher"
)
FAN_PY = FAN_DIR / "fan.py"


def test_fan_py_imports_under_pythonsafepath() -> None:
    """fan.py must import its sibling modules even when the script dir is
    stripped from sys.path (PYTHONSAFEPATH=1 / python -P)."""
    assert FAN_PY.is_file(), f"fan.py missing at {FAN_PY}"
    code = (
        "import runpy, sys; "
        "sys.argv=['fan.py', '--help']; "
        "runpy.run_path(%r, run_name='__main__')" % str(FAN_PY)
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        env={"PYTHONSAFEPATH": "1", "PATH": "/usr/bin:/bin"},
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, (
        f"fan.py failed under PYTHONSAFEPATH: rc={proc.returncode}\n"
        f"stdout: {proc.stdout[-800:]}\nstderr: {proc.stderr[-800:]}"
    )
    assert "ModuleNotFoundError" not in proc.stderr
