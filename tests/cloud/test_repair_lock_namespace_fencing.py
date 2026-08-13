from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

from arnold_pipelines.megaplan.cloud import repair_lock, repair_requests
from arnold_pipelines.megaplan.cloud.simple_fixer import (
    build_simple_fixer_occurrence,
    claim_singleton_occurrence,
    inspect_singleton_occurrence_claim,
)
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


# ═══════════════════════════════════════════════════════════════════════════
# T-0204 — active (blocker-keyed) + occurrence (fingerprint-keyed) claim
# namespaces must converge on ONE owner through the canonical alias index
# and current fence.
# ═══════════════════════════════════════════════════════════════════════════


def _occurrence_identity(
    *,
    custody_epoch: int,
    incarnation: str,
    lease: str,
    fence_token: int = 1,
) -> dict[str, object]:
    return repair_identity(
        session="demo-session",
        plan="demo-plan",
        failure_kind="phase_failed",
        phase="execute",
        task="T1",
        custody_epoch=custody_epoch,
        run_incarnation_id=f"incarnation-{incarnation}",
        coordinator_attempt_id=f"attempt-{incarnation}",
        run_authority_grant_id=f"grant-{incarnation}",
        lease_id=f"lease-{lease}",
        fence_token=fence_token,
    )


def _claim_active(
    queue_dir: Path,
    *,
    blocker_id: str,
    request_id: str,
    identity: dict[str, object],
    actor: str,
    pid: int,
    is_pid_live,
) -> repair_requests.ActiveRepairClaimResult:
    return repair_requests.claim_active_repair_request(
        queue_dir,
        blocker_id=blocker_id,
        request_id=request_id,
        actor=actor,
        session="demo-session",
        repair_identity=identity,
        pid=pid,
        is_pid_live=is_pid_live,
    )


def test_same_owner_joins_both_claim_namespaces(tmp_path: Path) -> None:
    queue_dir = _queue_root(tmp_path)
    identity = _occurrence_identity(custody_epoch=1, incarnation="a", lease="a")
    blocker_id, request_id, _ = _enqueue(
        queue_dir, identity=identity, actor="dispatcher"
    )

    active_claim = _claim_active(
        queue_dir,
        blocker_id=blocker_id,
        request_id=request_id,
        identity=identity,
        actor="dispatcher",
        pid=os.getpid(),
        is_pid_live=lambda _pid: True,
    )
    assert active_claim.claimed
    active_dir = repair_requests.active_repair_claim_lock_dir(
        queue_dir, blocker_id
    )
    assert active_dir.is_dir()

    # The same owner (same exact occurrence identity) joins the occurrence
    # namespace instead of being refused — the claim is acquired.
    occurrence = build_simple_fixer_occurrence(identity)
    assert occurrence is not None and occurrence.authoritative
    occ_claim = claim_singleton_occurrence(
        str(queue_dir),
        occurrence,
        actor="fixer",
        request_id=request_id,
        session="demo-session",
        pid=os.getpid(),
        is_pid_live=lambda _pid: True,
    )
    assert occ_claim.claimed
    occ_dir = repair_requests.singleton_occurrence_claim_lock_dir(
        queue_dir, occurrence.occurrence_fingerprint
    )
    assert occ_dir.is_dir()

    active_owner = json.loads((active_dir / "owner.json").read_text(encoding="utf-8"))
    occ_owner = json.loads((occ_dir / "owner.json").read_text(encoding="utf-8"))
    assert active_owner["repair_identity_key"] == occ_owner["repair_identity_key"]
    assert active_owner["repair_identity_key"] == occurrence.occurrence_fingerprint

    # ONE canonical alias record reachable from both keys.
    by_fingerprint = repair_lock.claim_alias_record(
        queue_dir, occurrence_fingerprint=occurrence.occurrence_fingerprint
    )
    assert by_fingerprint is not None
    assert by_fingerprint.blocker_id == blocker_id
    assert by_fingerprint.request_id == request_id
    by_blocker = repair_lock.claim_alias_record(
        queue_dir, blocker_id=blocker_id
    )
    assert by_blocker is not None
    assert by_blocker.occurrence_fingerprint == occurrence.occurrence_fingerprint


def test_foreign_owner_across_namespaces_is_busy_no_double_launch(
    tmp_path: Path,
) -> None:
    queue_dir = _queue_root(tmp_path)
    identity_a = _occurrence_identity(custody_epoch=1, incarnation="a", lease="a")
    blocker_a, request_a, _ = _enqueue(
        queue_dir, identity=identity_a, actor="dispatcher-a"
    )
    occurrence_a = build_simple_fixer_occurrence(identity_a)
    assert occurrence_a is not None and occurrence_a.authoritative
    first = claim_singleton_occurrence(
        str(queue_dir),
        occurrence_a,
        actor="fixer-a",
        request_id=request_a,
        session="demo-session",
        pid=os.getpid(),
        is_pid_live=lambda _pid: True,
    )
    assert first.claimed

    # A different exact occurrence of the SAME logical blocker: the active
    # claim must be refused — the occurrence namespace already owns it.
    identity_b = _occurrence_identity(custody_epoch=2, incarnation="b", lease="b")
    blocker_b, request_b, _ = _enqueue(
        queue_dir, identity=identity_b, actor="dispatcher-b"
    )
    assert blocker_b == blocker_a
    second = _claim_active(
        queue_dir,
        blocker_id=blocker_b,
        request_id=request_b,
        identity=identity_b,
        actor="dispatcher-b",
        pid=os.getpid(),
        is_pid_live=lambda _pid: True,
    )
    assert not second.claimed
    assert second.status == "busy"
    evidence = second.evidence or {}
    assert evidence.get("kind") == "cross_namespace_claim_conflict"
    assert evidence.get("outcome") == "busy_other_owner"
    # No double launch: the active lock dir was never created.
    assert not repair_requests.active_repair_claim_lock_dir(
        queue_dir, blocker_b
    ).exists()
    # The occurrence claim is untouched.
    assert repair_requests.singleton_occurrence_claim_lock_dir(
        queue_dir, occurrence_a.occurrence_fingerprint
    ).is_dir()


def test_foreign_owner_reverse_direction_active_first_refuses_occurrence(
    tmp_path: Path,
) -> None:
    queue_dir = _queue_root(tmp_path)
    identity_a = _occurrence_identity(custody_epoch=1, incarnation="a", lease="a")
    blocker_a, request_a, _ = _enqueue(
        queue_dir, identity=identity_a, actor="dispatcher-a"
    )
    active_claim = _claim_active(
        queue_dir,
        blocker_id=blocker_a,
        request_id=request_a,
        identity=identity_a,
        actor="dispatcher-a",
        pid=os.getpid(),
        is_pid_live=lambda _pid: True,
    )
    assert active_claim.claimed

    identity_b = _occurrence_identity(custody_epoch=2, incarnation="b", lease="b")
    blocker_b, request_b, _ = _enqueue(
        queue_dir, identity=identity_b, actor="dispatcher-b"
    )
    assert blocker_b == blocker_a
    occurrence_b = build_simple_fixer_occurrence(identity_b)
    assert occurrence_b is not None and occurrence_b.authoritative
    refused = claim_singleton_occurrence(
        str(queue_dir),
        occurrence_b,
        actor="fixer-b",
        request_id=request_b,
        session="demo-session",
        pid=os.getpid(),
        is_pid_live=lambda _pid: True,
    )
    assert not refused.claimed
    assert refused.outcome == "busy"
    assert (refused.evidence or {}).get("outcome") == "busy_other_owner"
    assert not repair_requests.singleton_occurrence_claim_lock_dir(
        queue_dir, occurrence_b.occurrence_fingerprint
    ).exists()


def test_stale_cross_namespace_reclaim_requires_newer_fence(
    tmp_path: Path,
) -> None:
    queue_dir = _queue_root(tmp_path)
    # Owner A claims the occurrence with a DEAD pid — the claim is stale.
    identity_a = _occurrence_identity(custody_epoch=1, incarnation="a", lease="a")
    blocker_a, request_a, _ = _enqueue(
        queue_dir, identity=identity_a, actor="dispatcher-a"
    )
    occurrence_a = build_simple_fixer_occurrence(identity_a)
    assert occurrence_a is not None and occurrence_a.authoritative
    first = claim_singleton_occurrence(
        str(queue_dir),
        occurrence_a,
        actor="fixer-a",
        request_id=request_a,
        session="demo-session",
        pid=4242,
        is_pid_live=lambda _pid: False,
    )
    assert first.claimed
    occ_dir = repair_requests.singleton_occurrence_claim_lock_dir(
        queue_dir, occurrence_a.occurrence_fingerprint
    )
    assert repair_lock.inspect_repair_lock(
        occ_dir, is_pid_live=lambda _pid: False
    ).stale

    # B carries a NEWER fence (custody_epoch=2): the active claim is
    # acquired AND the stale occurrence claim is reclaimed under B's owner
    # — both namespaces converge on ONE owner.
    identity_b = _occurrence_identity(custody_epoch=2, incarnation="b", lease="b")
    blocker_b, request_b, _ = _enqueue(
        queue_dir, identity=identity_b, actor="dispatcher-b"
    )
    assert blocker_b == blocker_a
    second = _claim_active(
        queue_dir,
        blocker_id=blocker_b,
        request_id=request_b,
        identity=identity_b,
        actor="dispatcher-b",
        pid=4242,
        is_pid_live=lambda _pid: False,
    )
    assert second.claimed
    active_dir = repair_requests.active_repair_claim_lock_dir(
        queue_dir, blocker_b
    )
    assert active_dir.is_dir()
    occ_owner = json.loads((occ_dir / "owner.json").read_text(encoding="utf-8"))
    assert occ_owner["request_id"] == request_b
    assert occ_owner["repair_identity_key"] == repair_requests.repair_identity_key(
        identity_b
    )
    alias = repair_lock.claim_alias_record(
        queue_dir, occurrence_fingerprint=occurrence_a.occurrence_fingerprint
    )
    assert alias is not None and alias.fence_epoch == 2

    # C carries a NON-newer fence (custody_epoch=1): the stale active claim
    # (fence 2) cannot be reclaimed — refused, and no occurrence lock lands.
    identity_c = _occurrence_identity(custody_epoch=1, incarnation="c", lease="c")
    blocker_c, request_c, _ = _enqueue(
        queue_dir, identity=identity_c, actor="dispatcher-c"
    )
    assert blocker_c == blocker_a
    occurrence_c = build_simple_fixer_occurrence(identity_c)
    assert occurrence_c is not None and occurrence_c.authoritative
    refused = claim_singleton_occurrence(
        str(queue_dir),
        occurrence_c,
        actor="fixer-c",
        request_id=request_c,
        session="demo-session",
        pid=os.getpid(),
        is_pid_live=lambda _pid: False,
    )
    assert not refused.claimed
    assert refused.outcome == "busy"
    assert (refused.evidence or {}).get("outcome") == "fenced_stale_refused"
    assert not repair_requests.singleton_occurrence_claim_lock_dir(
        queue_dir, occurrence_c.occurrence_fingerprint
    ).exists()


def test_newer_fence_reclaims_stale_active_from_occurrence_side(
    tmp_path: Path,
) -> None:
    queue_dir = _queue_root(tmp_path)
    identity_a = _occurrence_identity(custody_epoch=1, incarnation="a", lease="a")
    blocker_a, request_a, _ = _enqueue(
        queue_dir, identity=identity_a, actor="dispatcher-a"
    )
    first = _claim_active(
        queue_dir,
        blocker_id=blocker_a,
        request_id=request_a,
        identity=identity_a,
        actor="dispatcher-a",
        pid=4242,
        is_pid_live=lambda _pid: False,
    )
    assert first.claimed
    active_dir = repair_requests.active_repair_claim_lock_dir(
        queue_dir, blocker_a
    )
    assert repair_lock.inspect_repair_lock(
        active_dir, is_pid_live=lambda _pid: False
    ).stale

    # A NEWER fence (custody_epoch=3) reclaims from the occurrence side:
    # the occurrence claim is acquired AND the stale active claim is
    # re-acquired under the new owner.
    identity_b = _occurrence_identity(custody_epoch=3, incarnation="b", lease="b")
    blocker_b, request_b, _ = _enqueue(
        queue_dir, identity=identity_b, actor="dispatcher-b"
    )
    assert blocker_b == blocker_a
    occurrence_b = build_simple_fixer_occurrence(identity_b)
    assert occurrence_b is not None and occurrence_b.authoritative
    claimed = claim_singleton_occurrence(
        str(queue_dir),
        occurrence_b,
        actor="fixer-b",
        request_id=request_b,
        session="demo-session",
        pid=os.getpid(),
        is_pid_live=lambda _pid: False,
    )
    assert claimed.claimed
    active_owner = json.loads((active_dir / "owner.json").read_text(encoding="utf-8"))
    assert active_owner["request_id"] == request_b
    # The reclaimed active claim keeps the ACTIVE namespace shape so
    # dispatcher bind paths can still read it.
    assert active_owner["kind"] == "active_repair_request_claim"
    assert active_owner["blocker_id"] == blocker_b
    assert repair_requests.singleton_occurrence_claim_lock_dir(
        queue_dir, occurrence_b.occurrence_fingerprint
    ).is_dir()
    alias = repair_lock.claim_alias_record(
        queue_dir, occurrence_fingerprint=occurrence_b.occurrence_fingerprint
    )
    assert alias is not None and alias.blocker_id == blocker_b
    assert alias.fence_epoch == 3


def test_corrupt_alias_record_fails_closed_and_refuses_claims(
    tmp_path: Path,
) -> None:
    queue_dir = _queue_root(tmp_path)
    identity = _occurrence_identity(custody_epoch=1, incarnation="a", lease="a")
    blocker_id, request_id, _ = _enqueue(
        queue_dir, identity=identity, actor="dispatcher"
    )
    occurrence = build_simple_fixer_occurrence(identity)
    assert occurrence is not None and occurrence.authoritative

    # Corrupt the fingerprint-keyed alias (present but unreadable).
    alias_path = repair_lock._claim_alias_path(
        queue_dir, occurrence.occurrence_fingerprint
    )
    alias_path.parent.mkdir(parents=True, exist_ok=True)
    alias_path.write_text('{"schema": "claim-alias/v1", "broken', encoding="utf-8")
    assert repair_lock.claim_alias_file_exists(
        queue_dir, occurrence_fingerprint=occurrence.occurrence_fingerprint
    )

    # The occurrence-side claim must fail closed (never bypass the mapping).
    refused = claim_singleton_occurrence(
        str(queue_dir),
        occurrence,
        actor="fixer-a",
        request_id=request_id,
        session="demo-session",
        pid=os.getpid(),
        is_pid_live=lambda _pid: True,
    )
    assert not refused.claimed
    assert refused.outcome == "busy"
    assert (refused.evidence or {}).get("outcome") == "alias_invalid"
    assert not repair_requests.singleton_occurrence_claim_lock_dir(
        queue_dir, occurrence.occurrence_fingerprint
    ).exists()

    # Corrupt the blocker-keyed alias: the active-side claim must also
    # fail closed.
    blocker_alias_path = repair_lock._claim_alias_path(queue_dir, blocker_id)
    blocker_alias_path.write_text('{"schema": "claim-alias/v1", "broken', encoding="utf-8")
    refused_active = _claim_active(
        queue_dir,
        blocker_id=blocker_id,
        request_id=request_id,
        identity=identity,
        actor="dispatcher",
        pid=os.getpid(),
        is_pid_live=lambda _pid: True,
    )
    assert not refused_active.claimed
    assert refused_active.status == "busy"
    assert (refused_active.evidence or {}).get("outcome") == "alias_invalid"
    assert not repair_requests.active_repair_claim_lock_dir(
        queue_dir, blocker_id
    ).exists()


def test_concurrent_cross_namespace_claims_converge_on_one_owner(
    tmp_path: Path,
) -> None:
    queue_dir = _queue_root(tmp_path)
    # Two different exact occurrences of the SAME blocker race in opposite
    # namespaces: X via the blocker-keyed active claim, Y via the
    # fingerprint-keyed occurrence claim.  Exactly one owner may win.
    identity_x = _occurrence_identity(custody_epoch=1, incarnation="x", lease="x")
    blocker_x, request_x, _ = _enqueue(
        queue_dir, identity=identity_x, actor="dispatcher-x"
    )
    identity_y = _occurrence_identity(custody_epoch=2, incarnation="y", lease="y")
    blocker_y, request_y, _ = _enqueue(
        queue_dir, identity=identity_y, actor="dispatcher-y"
    )
    assert blocker_x == blocker_y
    occurrence_y = build_simple_fixer_occurrence(identity_y)
    assert occurrence_y is not None and occurrence_y.authoritative

    active_dir = repair_requests.active_repair_claim_lock_dir(
        queue_dir, blocker_x
    )
    occ_y_dir = repair_requests.singleton_occurrence_claim_lock_dir(
        queue_dir, occurrence_y.occurrence_fingerprint
    )

    contenders = 8
    barrier = Barrier(contenders)

    def contend(index: int) -> str:
        barrier.wait(timeout=20)
        if index % 2 == 0:
            result = _claim_active(
                queue_dir,
                blocker_id=blocker_x,
                request_id=request_x,
                identity=identity_x,
                actor=f"x-{index}",
                pid=os.getpid(),
                is_pid_live=lambda _pid: True,
            )
            return f"active:{result.status}"
        result = claim_singleton_occurrence(
            str(queue_dir),
            occurrence_y,
            actor=f"y-{index}",
            request_id=request_y,
            session="demo-session",
            pid=os.getpid(),
            is_pid_live=lambda _pid: True,
        )
        return f"occurrence:{result.outcome}"

    with ThreadPoolExecutor(max_workers=contenders) as executor:
        results = list(executor.map(contend, range(contenders)))

    claimed = [result for result in results if result.endswith(":claimed")]
    # Convergence: never more than one owner across both namespaces.
    assert len(claimed) <= 1
    # No double launch: the two namespace lock dirs can never both belong
    # to different owners — at most one of them exists at all.
    assert not (active_dir.exists() and occ_y_dir.exists())
    if claimed:
        if claimed[0].startswith("active:"):
            assert active_dir.exists()
            assert not occ_y_dir.exists()
        else:
            assert occ_y_dir.exists()
            assert not active_dir.exists()
    else:
        # Every contender failed closed (e.g. both backstops tripped) —
        # still no split ownership.
        assert not active_dir.exists()
        assert not occ_y_dir.exists()
    for result in results:
        assert result in {
            "active:claimed",
            "active:already_claimed",
            "active:busy",
            "occurrence:claimed",
            "occurrence:already_claimed",
            "occurrence:busy",
        }, result
