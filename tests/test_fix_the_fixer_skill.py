from __future__ import annotations

import subprocess
import sys
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "arnold_pipelines/megaplan/skills/fix-the-fixer/scripts/render_goal.py"
)


def test_render_goal_binds_target_and_single_agent_contract() -> None:
    target = "custody-control-plane-20260714 / m6-exact-contract-and-20260716-1303"

    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--target", target],
        check=True,
        capture_output=True,
        text=True,
    )

    assert completed.stdout.startswith("/goal\n")
    assert target in completed.stdout
    assert "only implementation/recovery agent" in completed.stdout
    assert "Launch no agents or subagents" in completed.stdout
    assert "retrigger ordinary" in completed.stdout
    assert "prove the actual epic or session advances" in completed.stdout


def test_render_goal_rejects_blank_target() -> None:
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--target", "   "],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 2
    assert "--target must contain epic or session text" in completed.stderr
