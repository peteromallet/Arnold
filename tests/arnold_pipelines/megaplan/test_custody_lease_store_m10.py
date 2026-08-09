"""Tests for the M10 custody lease lifecycle helpers and Step 11A/11C
invariants (T18).

Covers:
- Step 11A: token-guarded ``record_event`` and routing of lifecycle callers
  through the blessed helpers (acquire / renew / transfer / release / expire /
  fence / reclaim).
- Step 11C: owner/process-birth identity, monotonic epoch (old-epoch fencing),
  TTL ceiling, terminal-state rejection, and idempotent-repeat preservation.
"""

from __future__ import annotations

import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.custody import lease_store as ls_mod
from arnold_pipelines.megaplan.custody.lease_store import (
    CustodyLeaseStore,
    LeaseNotFoundError,
    LeaseOwnerMismatchError,
    LeaseStoreError,
    LeaseTtlCeilingError,
    StaleEpochError,
    TerminalLeaseError,
    _last_lifecycle_event_type,
    open_lease_store,
    utc_now,
)


# ── Fixtures ────────────────────────────────────────────────────────────────

OWNER_A = ("host-a", "111", "boot-a")
OWNER_B = ("host-b", "222", "boot-b")
GRANT = "grant-xyz"
FENCE = 7
WBC = "wbc-ref-1"
DIGEST = "sha256:deadbeef"


def _open_store() -> CustodyLeaseStore:
    tmpdir = Path(tempfile.mkdtemp())
    return CustodyLeaseStore(base_dir=tmpdir, flock=False)


def _acquire(
    store: CustodyLeaseStore,
    lease_id: str = "lease-1",
    *,
    owner=OWNER_A,
    custody_epoch: int = 1,
    sequence: int = 1,
    occurred_at: str = "2025-01-01T00:00:00Z",
    expires_at: str | None = "2025-01-01T01:00:00Z",
    idempotency_key: str | None = None,
):
    return store.acquire(
        lease_id=lease_id,
        owner_host=owner[0],
        owner_pid=owner[1],
        owner_boot_id=owner[2],
        run_authority_grant_id=GRANT,
        coordinator_fence_token=FENCE,
        wbc_attempt_reference=WBC,
        occurrence_digest=DIGEST,
        custody_epoch=custody_epoch,
        sequence=sequence,
        occurred_at=occurred_at,
        expires_at=expires_at,
        idempotency_key=idempotency_key,
    )


# ── Step 11A: token guard & routing ─────────────────────────────────────────


class TestRecordEventTokenGuard:
    def test_record_event_remains_callable_as_low_level_primitive(self) -> None:
        # Backward compatibility: the raw primitive still appends. The blessed
        # helpers use the private _record_event; record_event delegates.
        store = _open_store()
        from arnold_pipelines.megaplan.custody.contracts import CustodyLeaseEvent

        ev = CustodyLeaseEvent(
            event_id="e1",
            lease_id="raw-1",
            sequence=1,
            event_type="acquire",
            occurred_at="2025-01-01T00:00:00Z",
            custody_epoch=1,
            owner_host=OWNER_A[0],
            owner_pid=OWNER_A[1],
            owner_boot_id=OWNER_A[2],
            run_authority_grant_id=GRANT,
            coordinator_fence_token=FENCE,
            wbc_attempt_reference=WBC,
            occurrence_digest=DIGEST,
            idempotency_key="idem-raw-1",
            causal_predecessor="",
            payload={"expires_at": "2025-01-02T00:00:00Z"},
        )
        recorded = store.record_event(ev)
        assert recorded.event_id == "e1"
        assert store.replay_history("raw-1") is not None

    def test_writer_token_sentinel_is_a_private_singleton(self) -> None:
        token = ls_mod._LEASE_WRITER_TOKEN
        assert token is not None
        # A second lookup yields the same object identity.
        assert ls_mod._LEASE_WRITER_TOKEN is token

    def test_repair_requests_does_not_call_record_event_directly(self) -> None:
        """Step 11A static guard: the production lifecycle caller must route
        through lease helpers, not construct raw events + record_event."""
        src = Path(ls_mod.__file__)
        # Walk up to the repair_requests module.
        repair_path = (
            src.parent.parent / "cloud" / "repair_requests.py"
        )
        text = repair_path.read_text(encoding="utf-8")
        # No direct low-level append of a raw event.
        assert "lease_store.record_event(" not in text, (
            "repair_requests.py must not call lease_store.record_event(...) "
            "directly; route through the acquire/renew/... helpers (Step 11A)."
        )
        # And it should use the blessed helper.
        assert "lease_store.acquire(" in text


# ── Step 11C: acquire ───────────────────────────────────────────────────────


class TestAcquireHelper:
    def test_acquire_records_event_and_is_replayable(self) -> None:
        store = _open_store()
        ev = _acquire(store)
        assert ev.event_type == "acquire"
        lease = store.replay_history("lease-1")
        assert lease is not None
        assert lease.owner_host == OWNER_A[0]

    def test_acquire_collision_on_active_lease_raises(self) -> None:
        store = _open_store()
        _acquire(store, "lease-1")
        with pytest.raises(LeaseStoreError):
            _acquire(store, "lease-1", owner=OWNER_B, idempotency_key="other")

    def test_acquire_idempotent_repeat_is_noop(self) -> None:
        store = _open_store()
        first = _acquire(store, "lease-1", idempotency_key="idem-x")
        second = _acquire(store, "lease-1", idempotency_key="idem-x")
        assert second.event_id == first.event_id
        # Only one event in history.
        assert len(store.load_history("lease-1")) == 1

    def test_acquire_after_terminal_succeeds(self) -> None:
        store = _open_store()
        _acquire(store, "lease-1")
        store.release(
            lease_id="lease-1",
            owner_host=OWNER_A[0],
            owner_pid=OWNER_A[1],
            owner_boot_id=OWNER_A[2],
        )
        # Fresh acquisition after release is allowed.
        ev = _acquire(store, "lease-1", owner=OWNER_B, custody_epoch=2, sequence=3)
        assert ev.event_type == "acquire"

    def test_acquire_ttl_ceiling_raises(self) -> None:
        store = _open_store()
        with pytest.raises(LeaseTtlCeilingError):
            _acquire(
                store,
                "lease-1",
                occurred_at="2025-01-01T00:00:00Z",
                expires_at="2025-01-03T00:00:00Z",  # 2 days > 1 day max
            )


# ── Step 11C: renew ────────────────────────────────────────────────────────


class TestRenewHelper:
    def test_renew_requires_owner_match(self) -> None:
        store = _open_store()
        _acquire(store, "lease-1")
        with pytest.raises(LeaseOwnerMismatchError):
            store.renew(
                lease_id="lease-1",
                owner_host=OWNER_B[0],
                owner_pid=OWNER_B[1],
                owner_boot_id=OWNER_B[2],
                custody_epoch=2,
            )

    def test_renew_rejects_non_monotonic_epoch(self) -> None:
        store = _open_store()
        _acquire(store, "lease-1", custody_epoch=3)
        with pytest.raises(StaleEpochError):
            store.renew(
                lease_id="lease-1",
                owner_host=OWNER_A[0],
                owner_pid=OWNER_A[1],
                owner_boot_id=OWNER_A[2],
                custody_epoch=3,  # not strictly greater
            )

    def test_renew_on_terminal_raises(self) -> None:
        store = _open_store()
        _acquire(store, "lease-1")
        store.expire(lease_id="lease-1")
        with pytest.raises(TerminalLeaseError):
            store.renew(
                lease_id="lease-1",
                owner_host=OWNER_A[0],
                owner_pid=OWNER_A[1],
                owner_boot_id=OWNER_A[2],
                custody_epoch=5,
            )

    def test_renew_nonexistent_raises(self) -> None:
        store = _open_store()
        with pytest.raises(LeaseNotFoundError):
            store.renew(
                lease_id="ghost",
                owner_host=OWNER_A[0],
                owner_pid=OWNER_A[1],
                owner_boot_id=OWNER_A[2],
                custody_epoch=2,
            )

    def test_renew_success_advances_epoch(self) -> None:
        store = _open_store()
        _acquire(store, "lease-1", custody_epoch=1)
        store.renew(
            lease_id="lease-1",
            owner_host=OWNER_A[0],
            owner_pid=OWNER_A[1],
            owner_boot_id=OWNER_A[2],
            custody_epoch=2,
        )
        lease = store.replay_history("lease-1")
        assert lease is not None
        assert lease.custody_epoch == 2


# ── Step 11C: transfer ──────────────────────────────────────────────────────


class TestTransferHelper:
    def test_transfer_requires_owner_match(self) -> None:
        store = _open_store()
        _acquire(store, "lease-1")
        with pytest.raises(LeaseOwnerMismatchError):
            store.transfer(
                lease_id="lease-1",
                owner_host=OWNER_B[0],
                owner_pid=OWNER_B[1],
                owner_boot_id=OWNER_B[2],
                new_owner_host=OWNER_A[0],
                new_owner_pid=OWNER_A[1],
                new_owner_boot_id=OWNER_A[2],
                custody_epoch=2,
            )

    def test_transfer_rejects_stale_epoch(self) -> None:
        store = _open_store()
        _acquire(store, "lease-1", custody_epoch=5)
        with pytest.raises(StaleEpochError):
            store.transfer(
                lease_id="lease-1",
                owner_host=OWNER_A[0],
                owner_pid=OWNER_A[1],
                owner_boot_id=OWNER_A[2],
                new_owner_host=OWNER_B[0],
                new_owner_pid=OWNER_B[1],
                new_owner_boot_id=OWNER_B[2],
                custody_epoch=5,
            )

    def test_transfer_success_changes_owner(self) -> None:
        store = _open_store()
        _acquire(store, "lease-1", custody_epoch=1)
        store.transfer(
            lease_id="lease-1",
            owner_host=OWNER_A[0],
            owner_pid=OWNER_A[1],
            owner_boot_id=OWNER_A[2],
            new_owner_host=OWNER_B[0],
            new_owner_pid=OWNER_B[1],
            new_owner_boot_id=OWNER_B[2],
            custody_epoch=2,
        )
        lease = store.replay_history("lease-1")
        assert lease is not None
        assert lease.owner_host == OWNER_B[0]


# ── Step 11C: release / expire / fence ─────────────────────────────────────


class TestTerminalHelpers:
    def test_release_requires_owner_match(self) -> None:
        store = _open_store()
        _acquire(store, "lease-1")
        with pytest.raises(LeaseOwnerMismatchError):
            store.release(
                lease_id="lease-1",
                owner_host=OWNER_B[0],
                owner_pid=OWNER_B[1],
                owner_boot_id=OWNER_B[2],
            )

    def test_release_marks_terminal_then_blocks_renew(self) -> None:
        store = _open_store()
        _acquire(store, "lease-1")
        store.release(
            lease_id="lease-1",
            owner_host=OWNER_A[0],
            owner_pid=OWNER_A[1],
            owner_boot_id=OWNER_A[2],
        )
        with pytest.raises(TerminalLeaseError):
            store.renew(
                lease_id="lease-1",
                owner_host=OWNER_A[0],
                owner_pid=OWNER_A[1],
                owner_boot_id=OWNER_A[2],
                custody_epoch=9,
            )

    def test_release_idempotent_repeat_returns_last(self) -> None:
        store = _open_store()
        _acquire(store, "lease-1")
        first = store.release(
            lease_id="lease-1",
            owner_host=OWNER_A[0],
            owner_pid=OWNER_A[1],
            owner_boot_id=OWNER_A[2],
        )
        second = store.release(
            lease_id="lease-1",
            owner_host=OWNER_A[0],
            owner_pid=OWNER_A[1],
            owner_boot_id=OWNER_A[2],
        )
        assert second.event_id == first.event_id

    def test_release_on_different_terminal_raises(self) -> None:
        store = _open_store()
        _acquire(store, "lease-1")
        store.expire(lease_id="lease-1")
        with pytest.raises(TerminalLeaseError):
            store.release(
                lease_id="lease-1",
                owner_host=OWNER_A[0],
                owner_pid=OWNER_A[1],
                owner_boot_id=OWNER_A[2],
            )

    def test_expire_does_not_require_owner(self) -> None:
        # System-driven expiry must not be gated on owner identity.
        store = _open_store()
        _acquire(store, "lease-1")
        ev = store.expire(lease_id="lease-1")
        assert ev.event_type == "expire"

    def test_fence_requires_owner_and_records_token(self) -> None:
        store = _open_store()
        _acquire(store, "lease-1")
        ev = store.fence(
            lease_id="lease-1",
            owner_host=OWNER_A[0],
            owner_pid=OWNER_A[1],
            owner_boot_id=OWNER_A[2],
            coordinator_fence_token=42,
        )
        assert ev.event_type == "fence"
        lease = store.replay_history("lease-1")
        assert lease is not None
        assert lease.coordinator_fence_token == 42

    def test_fence_wrong_owner_raises(self) -> None:
        store = _open_store()
        _acquire(store, "lease-1")
        with pytest.raises(LeaseOwnerMismatchError):
            store.fence(
                lease_id="lease-1",
                owner_host=OWNER_B[0],
                owner_pid=OWNER_B[1],
                owner_boot_id=OWNER_B[2],
                coordinator_fence_token=42,
            )


# ── Step 11C: reclaim (old-epoch fencing) ──────────────────────────────────


class TestReclaimHelper:
    def test_reclaim_on_active_lease_raises(self) -> None:
        store = _open_store()
        _acquire(store, "lease-1", custody_epoch=1)
        with pytest.raises(LeaseStoreError):
            store.reclaim(
                lease_id="lease-1",
                owner_host=OWNER_B[0],
                owner_pid=OWNER_B[1],
                owner_boot_id=OWNER_B[2],
                run_authority_grant_id=GRANT,
                coordinator_fence_token=FENCE,
                wbc_attempt_reference=WBC,
                occurrence_digest=DIGEST,
                custody_epoch=2,
            )

    def test_reclaim_after_release_succeeds(self) -> None:
        store = _open_store()
        _acquire(store, "lease-1", custody_epoch=1)
        store.expire(lease_id="lease-1")
        ev = store.reclaim(
            lease_id="lease-1",
            owner_host=OWNER_B[0],
            owner_pid=OWNER_B[1],
            owner_boot_id=OWNER_B[2],
            run_authority_grant_id=GRANT,
            coordinator_fence_token=FENCE,
            wbc_attempt_reference=WBC,
            occurrence_digest=DIGEST,
            custody_epoch=2,
        )
        assert ev.event_type == "acquire"
        lease = store.replay_history("lease-1")
        assert lease is not None
        assert lease.owner_host == OWNER_B[0]

    def test_reclaim_rejects_stale_epoch(self) -> None:
        store = _open_store()
        _acquire(store, "lease-1", custody_epoch=4)
        store.release(
            lease_id="lease-1",
            owner_host=OWNER_A[0],
            owner_pid=OWNER_A[1],
            owner_boot_id=OWNER_A[2],
        )
        with pytest.raises(StaleEpochError):
            store.reclaim(
                lease_id="lease-1",
                owner_host=OWNER_B[0],
                owner_pid=OWNER_B[1],
                owner_boot_id=OWNER_B[2],
                run_authority_grant_id=GRANT,
                coordinator_fence_token=FENCE,
                wbc_attempt_reference=WBC,
                occurrence_digest=DIGEST,
                custody_epoch=4,  # not strictly greater than prior 4
            )

    def test_reclaim_nonexistent_raises(self) -> None:
        store = _open_store()
        with pytest.raises(LeaseNotFoundError):
            store.reclaim(
                lease_id="ghost",
                owner_host=OWNER_B[0],
                owner_pid=OWNER_B[1],
                owner_boot_id=OWNER_B[2],
                run_authority_grant_id=GRANT,
                coordinator_fence_token=FENCE,
                wbc_attempt_reference=WBC,
                occurrence_digest=DIGEST,
                custody_epoch=1,
            )


# ── Terminal detection helper ───────────────────────────────────────────────


class TestLastLifecycleEventType:
    def test_returns_none_for_empty(self) -> None:
        from arnold_pipelines.megaplan.custody.contracts import CustodyLeaseEvent

        assert _last_lifecycle_event_type(()) is None

    def test_skips_trailing_conflict_events(self) -> None:
        from arnold_pipelines.megaplan.custody.contracts import CustodyLeaseEvent

        def mk(etype: str) -> CustodyLeaseEvent:
            return CustodyLeaseEvent(
                event_id=f"e-{etype}",
                lease_id="l",
                sequence=1,
                event_type=etype,
                occurred_at="2025-01-01T00:00:00Z",
                custody_epoch=1,
                owner_host=OWNER_A[0],
                owner_pid=OWNER_A[1],
                owner_boot_id=OWNER_A[2],
                run_authority_grant_id=GRANT,
                coordinator_fence_token=FENCE,
                wbc_attempt_reference=WBC,
                occurrence_digest=DIGEST,
                idempotency_key=f"idem-{etype}",
                causal_predecessor="",
                payload={},
            )

        events = (mk("acquire"), mk("release"), mk("conflict"))
        assert _last_lifecycle_event_type(events) == "release"


def test_utc_now_returns_canonical_format() -> None:
    ts = utc_now()
    # Round-trips through the store's timestamp parser.
    parsed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    assert parsed.tzinfo is not None
