from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from tests.cloud.test_watchdog_wrappers import REPO_ROOT, _extract_repair_program


def test_repair_recovery_preserves_current_explicit_human_gate(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    marker_dir = tmp_path / "markers"
    repair_dir = marker_dir / "repair-data"
    repair_dir.mkdir(parents=True)
    spec_path = workspace / ".megaplan" / "initiatives" / "demo" / "chain.yaml"
    spec_path.parent.mkdir(parents=True)
    spec_path.write_text("merge_policy: auto\nmilestones: []\n", encoding="utf-8")
    plan_name = "demo-plan"
    plan_dir = workspace / ".megaplan" / "plans" / plan_name
    plan_dir.mkdir(parents=True)
    plan_path = plan_dir / "state.json"
    plan_path.write_text(
        json.dumps(
            {
                "name": plan_name,
                "current_state": "manual_review",
                "resume_cursor": {"phase": "execute", "retry_strategy": "manual_review"},
                "latest_failure": {"kind": "execution_blocked", "phase": "execute"},
            }
        ),
        encoding="utf-8",
    )
    chain_dir = workspace / ".megaplan" / "plans" / ".chains"
    chain_dir.mkdir(parents=True)
    chain_path = chain_dir / "chain.json"
    chain_path.write_text(
        json.dumps({"current_plan_name": plan_name, "last_state": "blocked"}),
        encoding="utf-8",
    )
    (marker_dir / "demo-session.json").write_text(
        json.dumps(
            {
                "session": "demo-session",
                "workspace": str(workspace),
                "remote_spec": str(spec_path),
                "run_kind": "chain",
            }
        ),
        encoding="utf-8",
    )
    (repair_dir / "demo-session.needs-human.json").write_text(
        json.dumps(
            {
                "session": "demo-session",
                "plan_name": plan_name,
                "summary": "security approval required",
            }
        ),
        encoding="utf-8",
    )

    program = _extract_repair_program(
        "recover_blocked_after_dev_fix_if_possible",
        '"${MARKER_DIR:-/workspace/.megaplan/cloud-sessions}" "$iteration" "$attempt_id" <<\'PY\'',
    )
    env = dict(os.environ)
    env["PYTHONPATH"] = f"{REPO_ROOT}:{env.get('PYTHONPATH', '')}"
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            program,
            str(workspace),
            "chain",
            plan_name,
            str(spec_path),
            "demo-session",
            str(marker_dir),
            "1",
            "1",
        ],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )

    assert result.returncode == 0, result.stderr
    assert "human gate preserved" in result.stdout
    assert json.loads(plan_path.read_text(encoding="utf-8"))["current_state"] == "manual_review"
    assert json.loads(chain_path.read_text(encoding="utf-8"))["last_state"] == "blocked"
