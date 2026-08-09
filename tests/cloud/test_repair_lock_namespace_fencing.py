from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

from arnold_pipelines.megaplan.cloud import repair_lock, repair_requests
from arnold_pipelines.megaplan.custody.contracts import CustodyTargetKey


def _queue_root(tmp_path: Path) -> Path:
    root = tmp_path / ".megaplan" / "repair-queue"
    root.mkdir(parents=True)
    return root


def _identity() -> dict[str, object]:
    target = CustodyTargetKey(
        environment="/workspace/demo", session="demo-session",
        chain="/workspace/demo/chain.yaml", plan_revision="rev-1",
        phase="repair", task="T1", attempt="1",
        normalized_failure_kind="blocked", blocker_or_phase_result_hash="blocker-1",
        fence="runner-fence:1",
    )
    identity = repair_requests.build_normalized_repair_identity(
        target=target, run_id="run-1", run_revision="rev-1",
        run_incarnation_id="incarnation-1", coordinator_attempt_id="coord-1",
        fence_token=1, wbc_attempt_reference="wbc-1",
        run_authority_grant_id="grant-1", lease_id="lease-1", custody_epoch=1,
    )
    assert identity is not None
    return identity


def test_foreign_namespace_pid_collision_is_unknown_and_cannot_release(tmp_path: Path) -> None:
    lock_dir = tmp_path / "repair.lock"
    acquired = repair_lock.acquire_repair_lock(
        lock_dir,
        session="demo-session",
        pid=os.getpid(),
        command="arnold-repair-loop demo-session",
    )
    assert acquired.acquired

    owner_path = repair_lock.owner_metadata_path(lock_dir)
    foreign_owner = json.loads(owner_path.read_text(encoding="utf-8"))
    foreign_owner["pid_namespace"] = "pid:[foreign-container]"
    owner_path.write_text(json.dumps(foreign_owner), encoding="utf-8")

    observed = repair_lock.inspect_repair_lock(lock_dir, is_pid_live=lambda _pid: True)
    assert observed.unknown
    assert "owner_pid_liveness_unknown" in (observed.stale_evidence or {})["reasons"]
    assert not repair_lock.release_repair_lock(
        lock_dir,
        owner=foreign_owner,
        expected_pid=os.getpid(),
    )
    assert json.loads(owner_path.read_text(encoding="utf-8")) == foreign_owner


def test_same_namespace_pid_reuse_is_stale_only_after_process_birth_mismatch(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(repair_lock, "_pid_namespace", lambda _pid: "pid:[same]")
    monkeypatch.setattr(repair_lock, "_process_start_ticks", lambda _pid: "birth-1")
    lock_dir = tmp_path / "repair.lock"
    acquired = repair_lock.acquire_repair_lock(
        lock_dir,
        session="demo-session",
        pid=4242,
        is_pid_live=lambda _pid: True,
    )
    assert acquired.acquired

    monkeypatch.setattr(repair_lock, "_process_start_ticks", lambda _pid: "birth-2")
    observed = repair_lock.inspect_repair_lock(lock_dir, is_pid_live=lambda _pid: True)
    assert observed.stale
    assert "owner_pid_not_live" in (observed.stale_evidence or {})["reasons"]
    assert repair_lock.release_repair_lock(
        lock_dir,
        owner=observed.owner,
        expected_pid=4242,
    )


def test_concurrent_contenders_cannot_reclaim_foreign_namespace_claim(tmp_path: Path) -> None:
    queue_dir = _queue_root(tmp_path)
    identity = _identity()
    queued = repair_requests.enqueue_repair_request(
        queue_root=queue_dir,
        session="demo-session",
        source="test",
        problem_signature={
            "failure_kind": "blocked", "current_state": "blocked",
            "phase_or_step": "repair", "milestone_or_plan": "demo-plan",
            "gate_recommendation": "", "blocked_task_id": "T1",
        },
        repair_identity=identity,
    )
    request = queued["request"]
    blocker_id = request["blocker_id"]
    first = repair_requests.claim_active_repair_request(
        queue_dir,
        blocker_id=blocker_id,
        request_id=request["request_id"],
        actor="owner",
        session="demo-session",
        repair_identity=identity,
        pid=os.getpid(),
        is_pid_live=lambda _pid: True,
    )
    assert first.claimed
    owner_path = first.lock_dir / "owner.json"
    foreign_owner = json.loads(owner_path.read_text(encoding="utf-8"))
    foreign_owner["pid_namespace"] = "pid:[foreign-container]"
    owner_path.write_text(json.dumps(foreign_owner), encoding="utf-8")

    contenders = 8
    barrier = Barrier(contenders)

    def contend(index: int) -> repair_requests.ActiveRepairClaimResult:
        barrier.wait(timeout=10)
        return repair_requests.claim_active_repair_request(
            queue_dir,
            blocker_id=blocker_id,
            request_id=request["request_id"],
            actor=f"contender-{index}",
            session="demo-session",
            repair_identity=identity,
            pid=os.getpid(),
            is_pid_live=lambda _pid: False,
        )

    with ThreadPoolExecutor(max_workers=contenders) as executor:
        results = list(executor.map(contend, range(contenders)))

    assert all(not result.claimed for result in results)
    assert all(result.status == "already_claimed" for result in results)
    assert json.loads(owner_path.read_text(encoding="utf-8")) == foreign_owner


def test_wrappers_fail_closed_on_unknown_and_do_not_reap_pidfile_projection() -> None:
    root = Path(__file__).resolve().parents[2]
    repair_loop = (
        root / "arnold_pipelines/megaplan/cloud/wrappers/arnold-repair-loop"
    ).read_text(encoding="utf-8")
    watchdog = (
        root / "arnold_pipelines/megaplan/cloud/wrappers/arnold-watchdog"
    ).read_text(encoding="utf-8")

    assert '"$lock_status" == "unknown"' in repair_loop
    assert "stale repair pidfile detected; reclaiming" not in repair_loop
    assert "namespace-bound durable lock owns admission" in repair_loop
    assert 'result.status == "stale"' in watchdog
    assert 'owner_pid_not_live' in watchdog
    assert 'owner_process_mismatch' in watchdog
