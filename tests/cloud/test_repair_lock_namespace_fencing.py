from __future__ import annotations

import json
import os
from pathlib import Path

from arnold_pipelines.megaplan.cloud import repair_lock
from arnold_pipelines.megaplan.custody.contracts import CustodyTargetKey
from tests.cloud.repair_identity_fixtures import repair_identity


def _queue_root(tmp_path: Path) -> Path:
    root = tmp_path / ".megaplan" / "repair-queue"
    root.mkdir(parents=True)
    return root


def _enqueue(
    queue_dir: Path,
    *,
    identity: dict[str, object],
    actor: str,
    failure_kind: str = "phase_failed",
) -> tuple[str, str, dict[str, object]]:
    """Enqueue one request; returns (blocker_id, request_id, request)."""

    queued = repair_requests.enqueue_repair_request(
        queue_root=queue_dir,
        session="demo-session",
        source=actor,
        problem_signature={
            "failure_kind": failure_kind,
            "current_state": "blocked",
            "phase_or_step": "execute",
            "milestone_or_plan": "demo-plan",
            "blocked_task_id": "T1",
        },
        repair_identity=identity,
    )
    request = queued["request"]
    return (
        str(request["blocker_id"]),
        str(request["request_id"]),
        request,
    )


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
        command="arnold-babysitter demo-session",
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


def test_wrappers_fail_closed_on_unknown_and_do_not_reap_pidfile_projection() -> None:
    root = Path(__file__).resolve().parents[2]
    watchdog = (
        root / "arnold_pipelines/megaplan/cloud/wrappers/arnold-watchdog"
    ).read_text(encoding="utf-8")
    babysitter = (
        root / "arnold_pipelines/megaplan/cloud/wrappers/arnold-babysitter"
    ).read_text(encoding="utf-8")

    # The layered repair stack removed wrapper-side lock inspection and
    # pidfile-projection reaping entirely: no surviving wrapper may reclaim a
    # stale repair pidfile as accepted repair authority, and the thin
    # babysitter launcher carries no pidfile handling at all.
    assert "stale repair pidfile detected; reclaiming" not in watchdog
    assert "namespace-bound durable lock owns admission" not in watchdog
    assert "repair pidfile" not in babysitter
