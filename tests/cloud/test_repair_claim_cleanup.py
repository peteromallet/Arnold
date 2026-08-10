from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from arnold_pipelines.megaplan.cloud import repair_requests
from tests.cloud.repair_identity_fixtures import repair_identity


REPO_ROOT = Path(__file__).resolve().parents[2]
WRAPPER_DIR = REPO_ROOT / "arnold_pipelines" / "megaplan" / "cloud" / "wrappers"


def _write_allow_manifestless_policy(tmp_path: Path) -> Path:
    """A valid unexpired allow_manifestless permit sidecar.

    This test exercises the repair-loop shutdown/claim-release path, not
    admission: the P1 admission kernel (G2 correction 3) gates every wrapper
    entry, so the direct invocation pins a valid permit.
    """
    now = datetime.now(timezone.utc)
    policy_path = tmp_path / ".runtime_policy.json"
    policy_path.write_text(
        json.dumps(
            {
                "permits": [
                    {
                        "kind": "allow_manifestless",
                        "id": "permit-claim-cleanup-1",
                        "issued_at": now.isoformat(),
                        "expires_at": (now + timedelta(hours=1)).isoformat(),
                        "actor": "claim-cleanup-test",
                        "reason": "claim-release path harness (admission not under test)",
                        "evidence": ["claim-cleanup harness injects a valid permit"],
                        "chain_digest": "deadbeef" * 4,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return policy_path


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


def test_repair_loop_releases_dispatcher_owned_active_claim_on_shutdown(tmp_path: Path) -> None:
    repair_root = tmp_path / "repair-root"
    workspace = tmp_path / "workspace"
    marker_dir = workspace / ".megaplan" / "cloud-sessions"
    bin_dir = tmp_path / "bin"
    snapshot_dir = tmp_path / "snapshots"
    marker_dir.mkdir(parents=True)
    repair_root.mkdir()
    bin_dir.mkdir()
    snapshot_dir.mkdir()

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

    queue_root = workspace / ".megaplan" / "repair-queue"
    identity = repair_identity(
        session="demo-session",
        plan="demo-plan",
        failure_kind="phase_failed",
        phase="execute",
        task="T1",
    )
    queued = repair_requests.enqueue_repair_request(
        queue_root=queue_root,
        session="demo-session",
        source="test-dispatcher",
        problem_signature={
            "failure_kind": "phase_failed",
            "current_state": "blocked",
            "phase_or_step": "execute",
            "milestone_or_plan": "demo-plan",
            "blocked_task_id": "T1",
        },
        repair_identity=identity,
    )
    blocker_id = str(queued["request"]["blocker_id"])
    request_id = str(queued["request"]["request_id"])
    claim = repair_requests.claim_active_repair_request(
        queue_root,
        blocker_id=blocker_id,
        request_id=request_id,
        actor="test-dispatcher",
        session="demo-session",
        pid=os.getpid(),
        command="arnold-repair-loop demo-session /tmp/ws /tmp/spec.json",
        cwd=str(workspace),
        repair_identity=identity,
    )
    assert claim.claimed
    decoy_queue_root = tmp_path / "decoy-workspace" / ".megaplan" / "repair-queue"
    decoy_identity = repair_identity(
        session="demo-session",
        plan="demo-plan",
        failure_kind="phase_failed",
        phase="execute",
        task="T1",
        run_incarnation_id="decoy-run-incarnation",
        coordinator_attempt_id="decoy-coordinator-attempt",
        run_authority_grant_id="decoy-grant",
        lease_id="decoy-lease",
    )
    decoy_queued = repair_requests.enqueue_repair_request(
        queue_root=decoy_queue_root,
        session="demo-session",
        source="decoy-dispatcher",
        problem_signature={
            "failure_kind": "phase_failed",
            "current_state": "blocked",
            "phase_or_step": "execute",
            "milestone_or_plan": "demo-plan",
            "blocked_task_id": "T1",
        },
        repair_identity=decoy_identity,
    )
    decoy_blocker_id = str(decoy_queued["request"]["blocker_id"])
    decoy_request_id = str(decoy_queued["request"]["request_id"])
    decoy_claim = repair_requests.claim_active_repair_request(
        decoy_queue_root,
        blocker_id=decoy_blocker_id,
        request_id=decoy_request_id,
        actor="decoy-dispatcher",
        session="demo-session",
        pid=os.getpid(),
        command="decoy",
        cwd=str(workspace),
        repair_identity=decoy_identity,
    )
    assert decoy_claim.claimed

    env = dict(os.environ)
    env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
    env["CLOUD_WATCHDOG_MARKER_DIR"] = str(marker_dir)
    env["CLOUD_WATCHDOG_REPAIR_ROOT"] = str(repair_root)
    env["CLOUD_WATCHDOG_REPAIR_DATA_DIR"] = str(marker_dir / "repair-data")
    env["MEGAPLAN_RUNTIME_SRC"] = str(REPO_ROOT)
    # Pin the interpreter whose installed dependencies are under test.  An
    # ambient ``python3`` earlier on PATH may be a dependency-empty Homebrew
    # interpreter and is not evidence about wrapper readiness.
    env["MEGAPLAN_SUPERVISOR_PYTHON"] = sys.executable
    env["ARNOLD_REPAIR_QUEUE_ROOT"] = str(queue_root)
    env["CLOUD_WATCHDOG_HERMES_LAUNCHER"] = str(launcher_path)
    env["CLOUD_WATCHDOG_REPAIR_REQUEST_ID"] = request_id
    env["CLOUD_WATCHDOG_REPAIR_BLOCKER_ID"] = blocker_id
    env["CLOUD_WATCHDOG_REPAIR_CLAIM_OWNER_PID"] = str(os.getpid())
    env["TMPDIR"] = str(snapshot_dir)
    env["ARNOLD_RUNTIME_POLICY"] = str(_write_allow_manifestless_policy(tmp_path))
    env.pop("ARNOLD_RUNTIME_MANIFEST", None)

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
    assert repair_requests.active_repair_claim_lock_dir(
        decoy_queue_root, decoy_blocker_id
    ).exists()
    assert not list(snapshot_dir.glob("arnold-repair-loop.*"))
