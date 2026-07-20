from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from arnold_pipelines.megaplan.cloud import repair_lock
from arnold_pipelines.megaplan.custody.contracts import (
    CustodyLease,
    CustodyTargetKey,
    RepairOccurrenceKey,
    build_custody_target_key,
    build_repair_occurrence_key,
)


# ── Minimal fake lease store for testing lease-authority integration ──────


@dataclass
class FakeLeaseStore:
    """A minimal in-memory lease store that exposes ``current_lease(lease_id)``."""

    _leases: dict[str, CustodyLease]

    def current_lease(self, lease_id: str) -> CustodyLease | None:
        return self._leases.get(lease_id)


def _make_test_custody_lease(
    lease_id: str = "lease-001",
    owner_host: str = "worker-a",
    owner_pid: str = "111",
    owner_boot_id: str = "",
    custody_epoch: int = 1,
    acquired_at: str | None = None,
    expires_at: str | None = None,
    is_expired: bool = False,
) -> CustodyLease:
    """Build a minimal CustodyLease for testing lease-authority integration."""
    if acquired_at is None:
        acquired_at = (datetime.now(timezone.utc) - timedelta(seconds=60)).isoformat()
    if expires_at is None:
        if is_expired:
            expires_at = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        else:
            expires_at = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()

    target = build_custody_target_key(
        environment="test",
        session="test-session",
        chain="test-chain",
        plan_revision="rev-1",
        phase="repair",
        task="task-1",
        attempt="1",
        normalized_failure_kind="none",
        blocker_or_phase_result_hash="abc123",
        fence="0",
        chain_identity="",
    )
    assert target is not None

    occurrence_key = build_repair_occurrence_key(
        target=target,
        run_id="run-1",
        run_revision="rev-1",
        coordinator_attempt_id="ca-1",
        fence_token=0,
        wbc_attempt_reference="wbc-test-001",
    )
    assert occurrence_key is not None

    return CustodyLease(
        lease_id=lease_id,
        occurrence_key=occurrence_key,
        owner_host=owner_host,
        owner_pid=owner_pid,
        owner_boot_id=owner_boot_id,
        run_authority_grant_id="grant-1",
        coordinator_fence_token=0,
        wbc_attempt_reference="wbc-test-001",
        custody_epoch=custody_epoch,
        acquired_at=acquired_at,
        expires_at=expires_at,
        idempotency_key=f"idem-{lease_id}",
        causal_predecessor="",
    )


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


# ═══════════════════════════════════════════════════════════════════════════
# M7 lease-store authority tests — PID liveness alone is NOT authority
# ═══════════════════════════════════════════════════════════════════════════


class TestPidLivenessIsNotAuthority:
    """PID liveness (from inspect/acquire) is admission evidence only —
    it does not authorize release, renew, or any repair action."""

    def test_inspect_stale_reports_pid_dead_but_does_not_authorize_action(
        self, tmp_path: Path
    ) -> None:
        """A stale lock (dead PID) is advisory evidence, not release authority."""
        lock_dir = tmp_path / "stale-advisory.lock"
        lock_dir.mkdir()
        owner_path = repair_lock.owner_metadata_path(lock_dir)
        owner_path.write_text(
            json.dumps(
                {
                    "session": "demo-session",
                    "target_id": "target-1",
                    "pid": 99999,
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

        result = repair_lock.inspect_repair_lock(
            lock_dir,
            now=datetime(2026, 7, 1, 18, 10, tzinfo=timezone.utc),
            is_pid_live=lambda pid: False,
        )

        # Stale detection works — but this is evidence, not authority.
        assert result.stale
        assert result.stale_evidence is not None
        assert "owner_pid_not_live" in result.stale_evidence["reasons"]
        # The lock is NOT released just because it's stale.
        assert lock_dir.exists()

    def test_lease_store_required_for_authoritative_release(
        self, tmp_path: Path
    ) -> None:
        """release_repair_lock with a lease store that lacks the lease
        refuses to release, proving PID liveness alone is insufficient."""
        lock_dir = tmp_path / "needs-lease.lock"
        live_pids = {111}

        acquired = repair_lock.acquire_repair_lock(
            lock_dir,
            session="demo-session",
            target_id="target-1",
            pid=111,
            command="arnold-repair-loop --session demo-session",
            started_at=datetime.now(timezone.utc).isoformat(),
            timeout_seconds=300,
            hostname="worker-a",
            is_pid_live=lambda pid: pid in live_pids,
        )
        assert acquired.acquired

        # PID is live — but lease store has no lease for this lease_id.
        empty_store = FakeLeaseStore(_leases={})
        assert not repair_lock.release_repair_lock(
            lock_dir,
            owner=acquired.owner,
            lease_store=empty_store,
            lease_id="missing-lease",
        )
        # Lock must still exist — release was refused.
        assert lock_dir.exists()

        # Cleanup without lease store (best-effort admission cleanup).
        assert repair_lock.release_repair_lock(lock_dir, owner=acquired.owner)
        assert not lock_dir.exists()

    def test_lease_store_wrong_owner_refuses_authoritative_release(
        self, tmp_path: Path
    ) -> None:
        """A lease for a different owner (host/PID) cannot authorize release."""
        lock_dir = tmp_path / "wrong-owner.lock"
        live_pids = {111}

        acquired = repair_lock.acquire_repair_lock(
            lock_dir,
            session="demo-session",
            target_id="target-1",
            pid=111,
            command="arnold-repair-loop --session demo-session",
            started_at=datetime.now(timezone.utc).isoformat(),
            timeout_seconds=300,
            hostname="worker-a",
            is_pid_live=lambda pid: pid in live_pids,
        )
        assert acquired.acquired

        # Lease store has a lease but owned by a different host.
        alien_lease = _make_test_custody_lease(
            lease_id="lease-001",
            owner_host="worker-b",  # different host
            owner_pid="111",
        )
        alien_store = FakeLeaseStore(_leases={"lease-001": alien_lease})
        assert not repair_lock.release_repair_lock(
            lock_dir,
            owner=acquired.owner,
            lease_store=alien_store,
            lease_id="lease-001",
        )
        assert lock_dir.exists()

        # Lease store has a lease but owned by a different PID.
        alien_pid_lease = _make_test_custody_lease(
            lease_id="lease-001",
            owner_host="worker-a",
            owner_pid="222",  # different PID
        )
        alien_pid_store = FakeLeaseStore(_leases={"lease-001": alien_pid_lease})
        assert not repair_lock.release_repair_lock(
            lock_dir,
            owner=acquired.owner,
            lease_store=alien_pid_store,
            lease_id="lease-001",
        )
        assert lock_dir.exists()

        # Cleanup.
        assert repair_lock.release_repair_lock(lock_dir, owner=acquired.owner)
        assert not lock_dir.exists()

    def test_lease_store_matching_owner_allows_authoritative_release(
        self, tmp_path: Path
    ) -> None:
        """When the lease store confirms ownership, authoritative release succeeds."""
        lock_dir = tmp_path / "matching-owner.lock"
        live_pids = {111}

        acquired = repair_lock.acquire_repair_lock(
            lock_dir,
            session="demo-session",
            target_id="target-1",
            pid=111,
            command="arnold-repair-loop --session demo-session",
            started_at=datetime.now(timezone.utc).isoformat(),
            timeout_seconds=300,
            hostname="worker-a",
            is_pid_live=lambda pid: pid in live_pids,
        )
        assert acquired.acquired

        matching_lease = _make_test_custody_lease(
            lease_id="lease-001",
            owner_host="worker-a",
            owner_pid="111",
        )
        store = FakeLeaseStore(_leases={"lease-001": matching_lease})
        assert repair_lock.release_repair_lock(
            lock_dir,
            owner=acquired.owner,
            lease_store=store,
            lease_id="lease-001",
        )
        assert not lock_dir.exists()

    def test_expired_lease_cannot_authorize_release(self, tmp_path: Path) -> None:
        """An expired lease cannot authorize release even if host/PID match."""
        lock_dir = tmp_path / "expired-lease.lock"
        live_pids = {111}

        acquired = repair_lock.acquire_repair_lock(
            lock_dir,
            session="demo-session",
            target_id="target-1",
            pid=111,
            command="arnold-repair-loop --session demo-session",
            started_at=datetime.now(timezone.utc).isoformat(),
            timeout_seconds=300,
            hostname="worker-a",
            is_pid_live=lambda pid: pid in live_pids,
        )
        assert acquired.acquired

        expired_lease = _make_test_custody_lease(
            lease_id="lease-001",
            owner_host="worker-a",
            owner_pid="111",
            is_expired=True,
        )
        store = FakeLeaseStore(_leases={"lease-001": expired_lease})
        assert not repair_lock.release_repair_lock(
            lock_dir,
            owner=acquired.owner,
            lease_store=store,
            lease_id="lease-001",
        )
        assert lock_dir.exists()

        # Cleanup.
        assert repair_lock.release_repair_lock(lock_dir, owner=acquired.owner)
        assert not lock_dir.exists()


class TestRenewRequiresLeaseAuthority:
    """renew_repair_lock requires lease-store ownership — PID liveness alone
    is never sufficient."""

    def test_renew_succeeds_with_matching_lease(self, tmp_path: Path) -> None:
        """Renew updates timeout_seconds when lease store confirms ownership."""
        lock_dir = tmp_path / "renew-ok.lock"
        live_pids = {111}
        started = datetime.now(timezone.utc).isoformat()

        acquired = repair_lock.acquire_repair_lock(
            lock_dir,
            session="demo-session",
            target_id="target-1",
            pid=111,
            command="arnold-repair-loop --session demo-session",
            started_at=started,
            timeout_seconds=300,
            hostname="worker-a",
            is_pid_live=lambda pid: pid in live_pids,
        )
        assert acquired.acquired

        matching_lease = _make_test_custody_lease(
            lease_id="lease-001",
            owner_host="worker-a",
            owner_pid="111",
        )
        store = FakeLeaseStore(_leases={"lease-001": matching_lease})

        result = repair_lock.renew_repair_lock(
            lock_dir,
            lease_store=store,
            lease_id="lease-001",
            timeout_seconds=600,
            is_pid_live=lambda pid: pid in live_pids,
        )

        assert result.acquired
        assert result.owner is not None
        assert result.owner["timeout_seconds"] == 600
        assert "renewed_at" in result.owner
        # Verify the metadata was persisted.
        persisted = json.loads(
            repair_lock.owner_metadata_path(lock_dir).read_text(encoding="utf-8")
        )
        assert persisted["timeout_seconds"] == 600
        assert "renewed_at" in persisted

        # Cleanup using updated owner from the renew result.
        assert repair_lock.release_repair_lock(lock_dir, owner=result.owner)
        assert not lock_dir.exists()

    def test_renew_refuses_without_lease_store_ownership(self, tmp_path: Path) -> None:
        """renew_repair_lock returns unauthorized when lease store has no lease."""
        lock_dir = tmp_path / "renew-unauthorized.lock"
        live_pids = {111}

        acquired = repair_lock.acquire_repair_lock(
            lock_dir,
            session="demo-session",
            target_id="target-1",
            pid=111,
            command="arnold-repair-loop --session demo-session",
            started_at=datetime.now(timezone.utc).isoformat(),
            timeout_seconds=300,
            hostname="worker-a",
            is_pid_live=lambda pid: pid in live_pids,
        )
        assert acquired.acquired

        empty_store = FakeLeaseStore(_leases={})
        result = repair_lock.renew_repair_lock(
            lock_dir,
            lease_store=empty_store,
            lease_id="nonexistent",
            timeout_seconds=600,
            is_pid_live=lambda pid: pid in live_pids,
        )

        assert result.unauthorized
        assert result.stale_evidence is not None
        assert any(
            "lease_authority_check_failed" in reason
            for reason in result.stale_evidence["reasons"]
        )
        assert lock_dir.exists()

        # Cleanup (owner metadata unchanged by failed renew).
        assert repair_lock.release_repair_lock(lock_dir, owner=acquired.owner)
        assert not lock_dir.exists()

    def test_renew_refuses_with_wrong_owner_lease(self, tmp_path: Path) -> None:
        """renew_repair_lock returns unauthorized when lease owner mismatches."""
        lock_dir = tmp_path / "renew-wrong-owner.lock"
        live_pids = {111}

        acquired = repair_lock.acquire_repair_lock(
            lock_dir,
            session="demo-session",
            target_id="target-1",
            pid=111,
            command="arnold-repair-loop --session demo-session",
            started_at=datetime.now(timezone.utc).isoformat(),
            timeout_seconds=300,
            hostname="worker-a",
            is_pid_live=lambda pid: pid in live_pids,
        )
        assert acquired.acquired

        alien_lease = _make_test_custody_lease(
            lease_id="lease-001",
            owner_host="worker-z",
            owner_pid="999",
        )
        alien_store = FakeLeaseStore(_leases={"lease-001": alien_lease})
        result = repair_lock.renew_repair_lock(
            lock_dir,
            lease_store=alien_store,
            lease_id="lease-001",
            timeout_seconds=600,
            is_pid_live=lambda pid: pid in live_pids,
        )

        assert result.unauthorized
        assert lock_dir.exists()

        # Cleanup (owner metadata unchanged by failed renew).
        assert repair_lock.release_repair_lock(lock_dir, owner=acquired.owner)
        assert not lock_dir.exists()

    def test_renew_refuses_with_expired_lease(self, tmp_path: Path) -> None:
        """renew_repair_lock returns unauthorized when lease is expired."""
        lock_dir = tmp_path / "renew-expired.lock"
        live_pids = {111}

        acquired = repair_lock.acquire_repair_lock(
            lock_dir,
            session="demo-session",
            target_id="target-1",
            pid=111,
            command="arnold-repair-loop --session demo-session",
            started_at=datetime.now(timezone.utc).isoformat(),
            timeout_seconds=300,
            hostname="worker-a",
            is_pid_live=lambda pid: pid in live_pids,
        )
        assert acquired.acquired

        expired_lease = _make_test_custody_lease(
            lease_id="lease-001",
            owner_host="worker-a",
            owner_pid="111",
            is_expired=True,
        )
        store = FakeLeaseStore(_leases={"lease-001": expired_lease})
        result = repair_lock.renew_repair_lock(
            lock_dir,
            lease_store=store,
            lease_id="lease-001",
            timeout_seconds=600,
            is_pid_live=lambda pid: pid in live_pids,
        )

        assert result.unauthorized
        assert lock_dir.exists()

        # Cleanup (owner metadata unchanged by failed renew).
        assert repair_lock.release_repair_lock(lock_dir, owner=acquired.owner)
        assert not lock_dir.exists()

    def test_renew_refuses_on_missing_lock(self, tmp_path: Path) -> None:
        """renew_repair_lock returns missing when the lock directory doesn't exist."""
        lock_dir = tmp_path / "nonexistent.lock"

        matching_lease = _make_test_custody_lease(
            lease_id="lease-001",
            owner_host="worker-a",
            owner_pid="111",
        )
        store = FakeLeaseStore(_leases={"lease-001": matching_lease})
        result = repair_lock.renew_repair_lock(
            lock_dir,
            lease_store=store,
            lease_id="lease-001",
            timeout_seconds=600,
        )

        assert result.status == "missing"

    def test_renew_with_stale_lock_but_valid_lease_succeeds(
        self, tmp_path: Path
    ) -> None:
        """A stale lock (dead PID) can still be renewed if lease authority is valid."""
        lock_dir = tmp_path / "stale-renew.lock"
        lock_dir.mkdir()
        owner_path = repair_lock.owner_metadata_path(lock_dir)
        owner_path.write_text(
            json.dumps(
                {
                    "session": "demo-session",
                    "target_id": "target-1",
                    "pid": 111,
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

        matching_lease = _make_test_custody_lease(
            lease_id="lease-001",
            owner_host="worker-a",
            owner_pid="111",
        )
        store = FakeLeaseStore(_leases={"lease-001": matching_lease})

        result = repair_lock.renew_repair_lock(
            lock_dir,
            lease_store=store,
            lease_id="lease-001",
            timeout_seconds=600,
            now=datetime(2026, 7, 1, 18, 10, tzinfo=timezone.utc),
            is_pid_live=lambda pid: False,  # PID is dead — but lease authority valid
        )

        # Renewal succeeds because lease authority is what matters.
        assert result.acquired
        assert result.owner is not None
        assert result.owner["timeout_seconds"] == 600
        assert lock_dir.exists()

        # Cleanup.
        assert repair_lock.release_repair_lock(lock_dir, owner=result.owner)
        assert not lock_dir.exists()


class TestValidateLeaseAuthority:
    """Direct tests for the validate_lease_authority function."""

    def test_authorized_when_lease_matches(self) -> None:
        lease = _make_test_custody_lease(
            lease_id="lease-001",
            owner_host="worker-a",
            owner_pid="111",
        )
        store = FakeLeaseStore(_leases={"lease-001": lease})
        lock_owner = {"hostname": "worker-a", "pid": 111}

        authorized, diag = repair_lock.validate_lease_authority(
            store, "lease-001", lock_owner
        )
        assert authorized
        assert diag["reason"] == "authorized"
        assert diag["lease_owner_host"] == "worker-a"
        assert diag["lease_owner_pid"] == "111"

    def test_unauthorized_when_lease_missing(self) -> None:
        store = FakeLeaseStore(_leases={})
        lock_owner = {"hostname": "worker-a", "pid": 111}

        authorized, diag = repair_lock.validate_lease_authority(
            store, "lease-001", lock_owner
        )
        assert not authorized
        assert diag["reason"] == "no_lease_found"

    def test_unauthorized_when_lease_expired(self) -> None:
        lease = _make_test_custody_lease(
            lease_id="lease-001",
            owner_host="worker-a",
            owner_pid="111",
            is_expired=True,
        )
        store = FakeLeaseStore(_leases={"lease-001": lease})
        lock_owner = {"hostname": "worker-a", "pid": 111}

        authorized, diag = repair_lock.validate_lease_authority(
            store, "lease-001", lock_owner
        )
        assert not authorized
        assert diag["reason"] == "lease_expired"

    def test_unauthorized_when_host_mismatch(self) -> None:
        lease = _make_test_custody_lease(
            lease_id="lease-001",
            owner_host="worker-a",
            owner_pid="111",
        )
        store = FakeLeaseStore(_leases={"lease-001": lease})
        lock_owner = {"hostname": "worker-b", "pid": 111}

        authorized, diag = repair_lock.validate_lease_authority(
            store, "lease-001", lock_owner
        )
        assert not authorized
        assert diag["reason"] == "owner_host_mismatch"

    def test_unauthorized_when_pid_mismatch(self) -> None:
        lease = _make_test_custody_lease(
            lease_id="lease-001",
            owner_host="worker-a",
            owner_pid="111",
        )
        store = FakeLeaseStore(_leases={"lease-001": lease})
        lock_owner = {"hostname": "worker-a", "pid": 222}

        authorized, diag = repair_lock.validate_lease_authority(
            store, "lease-001", lock_owner
        )
        assert not authorized
        assert diag["reason"] == "owner_pid_mismatch"

    def test_unauthorized_when_lock_owner_is_none(self) -> None:
        lease = _make_test_custody_lease(
            lease_id="lease-001",
            owner_host="worker-a",
            owner_pid="111",
        )
        store = FakeLeaseStore(_leases={"lease-001": lease})

        authorized, diag = repair_lock.validate_lease_authority(
            store, "lease-001", None
        )
        assert not authorized
        assert diag["reason"] == "missing_lock_owner_metadata"

    def test_unauthorized_when_lease_store_is_none(self) -> None:
        lock_owner = {"hostname": "worker-a", "pid": 111}

        authorized, diag = repair_lock.validate_lease_authority(
            None, "lease-001", lock_owner  # type: ignore[arg-type]
        )
        assert not authorized
        assert diag["reason"] == "missing_lease_store_or_lease_id"

    def test_unauthorized_when_lease_id_is_empty(self) -> None:
        lease = _make_test_custody_lease(
            lease_id="lease-001",
            owner_host="worker-a",
            owner_pid="111",
        )
        store = FakeLeaseStore(_leases={"lease-001": lease})
        lock_owner = {"hostname": "worker-a", "pid": 111}

        authorized, diag = repair_lock.validate_lease_authority(
            store, "", lock_owner
        )
        assert not authorized
        assert diag["reason"] == "missing_lease_store_or_lease_id"


class TestAdmissionProjectionUnchanged:
    """The mkdir/PID lock admission and projection behavior is preserved —
    only authority is gated behind the lease store."""

    def test_acquire_still_works_for_admission_gating(self, tmp_path: Path) -> None:
        """acquire_repair_lock still serializes concurrent attempts via mkdir."""
        lock_dir = tmp_path / "admission.lock"
        live_pids = {111, 222}

        first = repair_lock.acquire_repair_lock(
            lock_dir,
            session="demo-session",
            pid=111,
            started_at=datetime.now(timezone.utc).isoformat(),
            timeout_seconds=300,
            hostname="worker-a",
            is_pid_live=lambda pid: pid in live_pids,
        )
        assert first.acquired

        second = repair_lock.acquire_repair_lock(
            lock_dir,
            session="demo-session",
            pid=222,
            started_at=datetime.now(timezone.utc).isoformat(),
            timeout_seconds=300,
            hostname="worker-b",
            is_pid_live=lambda pid: pid in live_pids,
        )
        assert second.busy  # Admission gating still works.

        # Best-effort cleanup (no lease store needed for admission cleanup).
        assert repair_lock.release_repair_lock(lock_dir, owner=first.owner)
        assert not lock_dir.exists()

    def test_inspect_still_reports_stale_as_projection_evidence(
        self, tmp_path: Path
    ) -> None:
        """inspect_repair_lock still detects stale locks as projection evidence."""
        lock_dir = tmp_path / "projection.lock"
        lock_dir.mkdir()
        owner_path = repair_lock.owner_metadata_path(lock_dir)
        owner_path.write_text(
            json.dumps(
                {
                    "session": "demo-session",
                    "target_id": "target-1",
                    "pid": 99999,
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

        result = repair_lock.inspect_repair_lock(
            lock_dir,
            now=datetime(2026, 7, 1, 18, 10, tzinfo=timezone.utc),
            is_pid_live=lambda pid: False,
        )

        assert result.stale
        # Stale evidence is projection — it's not released.
        assert lock_dir.exists()

    def test_context_manager_still_cleans_up_without_lease_store(
        self, tmp_path: Path
    ) -> None:
        """repair_lock context manager still releases on exit (admission cleanup)."""
        lock_dir = tmp_path / "ctx.lock"

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

    def test_repair_lock_result_has_unauthorized_property(self) -> None:
        """RepairLockResult.unauthorized property is accessible."""
        from arnold_pipelines.megaplan.cloud.repair_lock import RepairLockResult

        result = RepairLockResult(
            status="unauthorized",
            lock_dir=Path("/tmp/test.lock"),
            owner=None,
            stale_evidence={"reasons": ["test"]},
        )
        assert result.unauthorized
        assert not result.acquired
        assert not result.busy
        assert not result.stale
