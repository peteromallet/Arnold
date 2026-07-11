from __future__ import annotations

import json
import os
import stat
import subprocess
from pathlib import Path

from arnold_pipelines.megaplan.cloud import repair_requests


REPO_ROOT = Path(__file__).resolve().parents[2]
WRAPPER_DIR = REPO_ROOT / "arnold_pipelines" / "megaplan" / "cloud" / "wrappers"


def _write_plan(plan_dir: Path) -> None:
    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "name": "demo-plan",
                "current_state": "blocked",
                "iteration": 1,
                "latest_failure": {
                    "kind": "phase_failed",
                    "message": "boom",
                    "recorded_at": "2026-06-29T00:00:00Z",
                    "metadata": {"exit_code": 1},
                },
            }
        ),
        encoding="utf-8",
    )


def test_watchdog_dispatch_exports_claim_owner_pid() -> None:
    text = (WRAPPER_DIR / "arnold-watchdog").read_text(encoding="utf-8")

    assert (
        'export CLOUD_WATCHDOG_REPAIR_CLAIM_OWNER_PID="$8"; export ARNOLD_REPAIR_QUEUE_ROOT="$9"; exec "$2" "$3" "$4" "$5"'
        in text
    )


def test_repair_loop_releases_dispatcher_owned_active_claim_on_shutdown(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    repair_root = tmp_path / "repair-root"
    workspace = tmp_path / "workspace"
    bin_dir = tmp_path / "bin"
    marker_dir.mkdir()
    repair_root.mkdir()
    workspace.mkdir()
    bin_dir.mkdir()

    (marker_dir / "demo-session.json").write_text(
        json.dumps({"run_kind": "plan", "plan_name": "demo-plan", "relaunch_command": "true"}),
        encoding="utf-8",
    )
    _write_plan(workspace / ".megaplan" / "plans" / "demo-plan")

    timeout_path = bin_dir / "timeout"
    timeout_path.write_text(
        "#!/usr/bin/env bash\n"
        "shift\n"
        "exec \"$@\"\n",
        encoding="utf-8",
    )
    timeout_path.chmod(timeout_path.stat().st_mode | stat.S_IXUSR)
    codex_path = bin_dir / "codex"
    codex_path.write_text(
        "#!/usr/bin/env bash\n"
        "sleep 30\n",
        encoding="utf-8",
    )
    codex_path.chmod(codex_path.stat().st_mode | stat.S_IXUSR)
    launcher_path = tmp_path / "launcher.py"
    launcher_path.write_text("import time\n\ntime.sleep(30)\n", encoding="utf-8")

    blocker_id = "blocker:v1:test"
    request_id = "req-test"
    queue_root = workspace / ".megaplan" / "repair-queue"
    claim = repair_requests.claim_active_repair_request(
        queue_root,
        blocker_id=blocker_id,
        request_id=request_id,
        actor="test-dispatcher",
        session="demo-session",
        pid=os.getpid(),
        command="arnold-repair-loop demo-session /tmp/ws /tmp/spec.json",
        cwd=str(workspace),
    )
    assert claim.claimed
    decoy_queue_root = tmp_path / "decoy-workspace" / ".megaplan" / "repair-queue"
    decoy_claim = repair_requests.claim_active_repair_request(
        decoy_queue_root,
        blocker_id=blocker_id,
        request_id="decoy-request",
        actor="decoy-dispatcher",
        session="demo-session",
        pid=os.getpid(),
        command="decoy",
        cwd=str(workspace),
    )
    assert decoy_claim.claimed

    env = dict(os.environ)
    env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
    env["CLOUD_WATCHDOG_MARKER_DIR"] = str(marker_dir)
    env["CLOUD_WATCHDOG_REPAIR_ROOT"] = str(repair_root)
    env["CLOUD_WATCHDOG_REPAIR_DATA_DIR"] = str(marker_dir / "repair-data")
    env["ARNOLD_REPAIR_QUEUE_ROOT"] = str(queue_root)
    env["CLOUD_WATCHDOG_HERMES_LAUNCHER"] = str(launcher_path)
    env["CLOUD_WATCHDOG_REPAIR_REQUEST_ID"] = request_id
    env["CLOUD_WATCHDOG_REPAIR_BLOCKER_ID"] = blocker_id
    env["CLOUD_WATCHDOG_REPAIR_CLAIM_OWNER_PID"] = str(os.getpid())

    proc = subprocess.Popen(
        ["bash", str(WRAPPER_DIR / "arnold-repair-loop"), "demo-session", str(workspace), "/tmp/spec.json"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    _, stderr = proc.communicate(timeout=15)
    assert proc.returncode == 0, stderr

    claim_lock_dir = repair_requests.active_repair_claim_lock_dir(
        queue_root,
        blocker_id,
    )
    assert not claim_lock_dir.exists()
    assert repair_requests.active_repair_claim_lock_dir(decoy_queue_root, blocker_id).exists()
