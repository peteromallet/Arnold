from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.cloud import repair_lock


def test_acquire_repair_lock_claims_owner_metadata_and_reports_busy_without_mutation(
    tmp_path: Path,
) -> None:
    lock_dir = tmp_path / "demo-session.lock"
    live_pids = {111}
    started_at = datetime.now(timezone.utc).isoformat()

    first = repair_lock.acquire_repair_lock(
        lock_dir,
        session="demo-session",
        target_id="target-1",
        pid=111,
        command="arnold-repair-loop --session demo-session",
        started_at=started_at,
        cwd="/workspace/project",
        timeout_seconds=300,
        hostname="worker-a",
        is_pid_live=lambda pid: pid in live_pids,
    )

    assert first.acquired
    owner_path = repair_lock.owner_metadata_path(lock_dir)
    owner_before = json.loads(owner_path.read_text(encoding="utf-8"))
    assert owner_before == {
        "session": "demo-session",
        "target_id": "target-1",
        "pid": 111,
        "command": "arnold-repair-loop --session demo-session",
        "started_at": started_at,
        "cwd": "/workspace/project",
        "timeout_seconds": 300,
        "hostname": "worker-a",
    }

    second = repair_lock.acquire_repair_lock(
        lock_dir,
        session="demo-session",
        target_id="target-2",
        pid=222,
        command="arnold-repair-loop --session demo-session --retry",
        is_pid_live=lambda pid: pid in live_pids,
    )

    assert second.busy
    assert second.owner == owner_before
    assert second.stale_evidence is None
    assert json.loads(owner_path.read_text(encoding="utf-8")) == owner_before

    assert repair_lock.release_repair_lock(lock_dir, owner=first.owner)
    assert not lock_dir.exists()


def test_acquire_repair_lock_reports_stale_evidence_without_deleting_lock(tmp_path: Path) -> None:
    lock_dir = tmp_path / "demo-session.lock"
    lock_dir.mkdir()
    owner_path = repair_lock.owner_metadata_path(lock_dir)
    owner_path.write_text(
        json.dumps(
            {
                "session": "demo-session",
                "target_id": "target-stale",
                "pid": 333,
                "command": "arnold-repair-loop --session demo-session",
                "started_at": "2026-07-01T18:00:00+00:00",
                "cwd": "/workspace/project",
                "timeout_seconds": 60,
                "hostname": "worker-a",
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    snapshot = owner_path.read_text(encoding="utf-8")

    result = repair_lock.acquire_repair_lock(
        lock_dir,
        session="demo-session",
        target_id="target-new",
        pid=444,
        now=datetime(2026, 7, 1, 18, 10, tzinfo=timezone.utc),
        is_pid_live=lambda pid: False,
    )

    assert result.stale
    assert result.owner["pid"] == 333
    assert result.stale_evidence is not None
    assert "owner_pid_not_live" in result.stale_evidence["reasons"]
    assert "timeout_expired" in result.stale_evidence["reasons"]
    assert owner_path.read_text(encoding="utf-8") == snapshot
    assert lock_dir.exists()


def test_repair_lock_context_manager_releases_on_success_and_exception(tmp_path: Path) -> None:
    lock_dir = tmp_path / "demo-session.lock"

    with repair_lock.repair_lock(
        lock_dir,
        session="demo-session",
        pid=555,
        started_at="2026-07-01T18:36:00+00:00",
        timeout_seconds=300,
    ) as result:
        assert result.acquired
        assert lock_dir.exists()

    assert not lock_dir.exists()

    with pytest.raises(RuntimeError):
        with repair_lock.repair_lock(
            lock_dir,
            session="demo-session",
            pid=556,
            started_at="2026-07-01T18:37:00+00:00",
            timeout_seconds=300,
        ) as result:
            assert result.acquired
            raise RuntimeError("boom")

    assert not lock_dir.exists()


def test_repair_lock_owner_fence_is_not_enriched_by_resident_provenance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "ARNOLD_RESIDENT_DELEGATION_CONTEXT",
        json.dumps(
            {
                "applicability": "not_applicable",
                "transport": "non_discord",
                "source_kind": "test",
            }
        ),
    )
    lock_dir = tmp_path / "demo-session.lock"

    acquired = repair_lock.acquire_repair_lock(
        lock_dir,
        session="demo-session",
        pid=557,
        started_at=datetime.now(timezone.utc).isoformat(),
        timeout_seconds=300,
    )

    assert acquired.acquired
    persisted = json.loads(
        repair_lock.owner_metadata_path(lock_dir).read_text(encoding="utf-8")
    )
    assert persisted == acquired.owner
    assert "resident_delegation" not in persisted
    assert repair_lock.release_repair_lock(lock_dir, owner=acquired.owner)
    assert not lock_dir.exists()


def test_acquire_repair_lock_uses_default_pid_liveness_probe(tmp_path: Path) -> None:
    lock_dir = tmp_path / "demo-session.lock"
    lock_dir.mkdir()
    owner_path = repair_lock.owner_metadata_path(lock_dir)
    owner_path.write_text(
        json.dumps(
            {
                "session": "demo-session",
                "target_id": "target-stale",
                "pid": 99_999_999,
                "command": "arnold-repair-loop --session demo-session",
                "started_at": "2026-07-01T18:00:00+00:00",
                "cwd": "/workspace/project",
                "timeout_seconds": None,
                "hostname": "worker-a",
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    result = repair_lock.acquire_repair_lock(
        lock_dir,
        session="demo-session",
        target_id="target-new",
        pid=444,
    )

    assert result.stale
    assert result.stale_evidence is not None
    assert "owner_pid_not_live" in result.stale_evidence["reasons"]


def test_release_repair_lock_refuses_mismatched_owner(tmp_path: Path) -> None:
    lock_dir = tmp_path / "demo-session.lock"
    acquired = repair_lock.acquire_repair_lock(
        lock_dir,
        session="demo-session",
        pid=777,
        started_at=(datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat(),
        timeout_seconds=300,
    )

    assert acquired.acquired
    assert not repair_lock.release_repair_lock(lock_dir, expected_pid=999)
    assert lock_dir.exists()
    assert repair_lock.release_repair_lock(lock_dir, expected_pid=777)
    assert not lock_dir.exists()
