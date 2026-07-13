from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
WRAPPER = REPO_ROOT / "arnold_pipelines/megaplan/cloud/wrappers/arnold-meta-repair-loop"


def _classification_program() -> str:
    text = WRAPPER.read_text(encoding="utf-8")
    start = text.index("classification_and_prompt() {")
    marker = (
        'python3 - "$SESSION" "$REPAIR_DATA_DIR" "$REPAIR_DATA_PATH" '
        '"$MARKER_DIR" "$META_REPAIR_ENABLED_VAR" "$WATCHDOG_TRIGGER" <<'
    )
    py_start = text.index(marker, start)
    py_start = text.index("\n", py_start) + 1
    py_end = text.index("\nPY\n", py_start)
    return text[py_start:py_end]


def test_preclassified_trigger_survives_live_target_mismatch(tmp_path: Path) -> None:
    """Live discovery corroborates but cannot revoke bounded trigger custody."""
    repair_root = tmp_path / "repair-data"
    marker_root = tmp_path / "markers"
    workspace = tmp_path / "workspace"
    chain_root = workspace / ".megaplan" / "plans" / ".chains"
    current_plan = workspace / ".megaplan" / "plans" / "new-plan"
    repair_root.mkdir()
    marker_root.mkdir()
    chain_root.mkdir(parents=True)
    current_plan.mkdir(parents=True)
    repair_path = repair_root / "demo.repair-data.json"
    repair_path.write_text(
        json.dumps(
            {
                "session": "demo",
                "workspace": str(workspace),
                "plan_name": "old-plan",
                "outcome": "partial_liveness",
            }
        ),
        encoding="utf-8",
    )
    (marker_root / "demo.json").write_text(
        json.dumps({"session": "demo", "workspace": str(workspace), "kind": "chain"}),
        encoding="utf-8",
    )
    (chain_root / "chain-demo.json").write_text(
        json.dumps({"current_plan_name": "new-plan", "last_state": "finalized"}),
        encoding="utf-8",
    )
    (current_plan / "state.json").write_text(
        json.dumps({"name": "new-plan", "current_state": "finalized"}),
        encoding="utf-8",
    )

    env = dict(os.environ)
    env["PYTHONPATH"] = f"{REPO_ROOT}:{env.get('PYTHONPATH', '')}"
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            _classification_program(),
            "demo",
            str(repair_root),
            str(repair_path),
            str(marker_root),
            "1",
            "partial_liveness_recurrence",
        ],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "TRIGGER:partial_liveness_recurrence" in result.stdout
    assert "PROMPT_START" in result.stdout
    assert "NO_TRIGGER" not in result.stdout


def test_preclassified_l1_custody_failure_reaches_meta_repair(tmp_path: Path) -> None:
    repair_root = tmp_path / "repair-data"
    marker_root = tmp_path / "markers"
    workspace = tmp_path / "workspace"
    repair_root.mkdir()
    marker_root.mkdir()
    workspace.mkdir()
    repair_path = repair_root / "demo.repair-data.json"
    repair_path.write_text(
        json.dumps(
            {
                "session": "demo",
                "workspace": str(workspace),
                "outcome": "repair_exhausted",
                "l1_custody_failure": {
                    "reason": "missing canonical blocker identity",
                    "request_id": "7473fa42",
                    "blocker_id": "",
                },
            }
        ),
        encoding="utf-8",
    )
    (marker_root / "demo.json").write_text(
        json.dumps({"session": "demo", "workspace": str(workspace), "kind": "chain"}),
        encoding="utf-8",
    )

    env = dict(os.environ)
    env["PYTHONPATH"] = f"{REPO_ROOT}:{env.get('PYTHONPATH', '')}"
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            _classification_program(),
            "demo",
            str(repair_root),
            str(repair_path),
            str(marker_root),
            "1",
            "l1_custody_failure",
        ],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "TRIGGER:l1_custody_failure" in result.stdout
    assert "PROMPT_START" in result.stdout
    assert "NO_TRIGGER" not in result.stdout
