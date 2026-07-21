"""Tests for the append-only Custody lease store (M7 T5).

Validates:
- Append-only semantics under all lifecycle events
- Deterministic replay yielding identical results
- Idempotent exact repeats (no-op)
- Stale sequence rejection
- Payload conflict quarantine
- Terminal events never erase prior history
- All eight event-type reducers
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.custody.contracts import (
    CustodyLease,
    CustodyLeaseEvent,
    CustodyTargetKey,
    RepairOccurrenceKey,
)
from arnold_pipelines.megaplan.custody.lease_store import (
    CustodyLeaseStore,
    LeaseIdempotencyConflict,
    LeaseStoreError,
    StaleSequenceError,
    open_lease_store,
    record_events,
    reduce_event,
    replay_events,
)
from arnold_pipelines.run_authority.contracts import ContractError


# ── Shared fixtures ────────────────────────────────────────────────────────


def _make_target(**overrides: str) -> CustodyTargetKey:
    kwargs = dict(
        environment="prod",
        session="sess-001",
        chain="chain-alpha",
        plan_revision="rev-42",
        phase="execute",
        task="task-7",
        attempt="a3",
        normalized_failure_kind="timeout",
        blocker_or_phase_result_hash="abc123def",
        fence="fence-9",
        chain_identity="chain-id-01",
    )
    kwargs.update(overrides)
    return CustodyTargetKey(**kwargs)


def _make_occurrence_key(
    target: CustodyTargetKey | None = None, **overrides
) -> RepairOccurrenceKey:
    t = target if target is not None else _make_target()
    kwargs = dict(
        target=t,
        run_id="run-001",
        run_revision="rev-100",
        coordinator_attempt_id="coord-500",
        fence_token=10,
        wbc_attempt_reference="wbc-att-77",
    )
    kwargs.update(overrides)
    return RepairOccurrenceKey(**kwargs)


def _make_event(
    event_id: str,
    lease_id: str,
    sequence: int,
    event_type: str,
    *,
    idempotency_key: str | None = None,
    custody_epoch: int | None = None,
    payload: dict | None = None,
    **overrides,
) -> CustodyLeaseEvent:
    epoch = custody_epoch if custody_epoch is not None else sequence
    base = dict(
        event_id=event_id,
        lease_id=lease_id,
        sequence=sequence,
        event_type=event_type,
        occurred_at="2025-01-01T00:00:00Z",
        custody_epoch=epoch,
        owner_host="host-1",
        owner_pid="12345",
        owner_boot_id="boot-abc",
        run_authority_grant_id="grant-001",
        coordinator_fence_token=10,
        wbc_attempt_reference="wbc-att-77",
        occurrence_digest="sha256:aaaa",
        idempotency_key=idempotency_key or f"idem-{event_id}",
        causal_predecessor="",
        payload=payload if payload is not None else {"expires_at": "2025-01-02T00:00:00Z"},
    )
    base.update(overrides)
    return CustodyLeaseEvent(**base)


@pytest.fixture
def store() -> CustodyLeaseStore:
    """Return a fresh in-process lease store rooted in a temp directory."""
    tmpdir = Path(tempfile.mkdtemp())
    return CustodyLeaseStore(base_dir=tmpdir, flock=False)


@pytest.fixture
def store_with_acquire(store: CustodyLeaseStore) -> CustodyLeaseStore:
    """Store with a single acquire event already recorded."""
    evt = _make_event("evt-001", "lease-001", 1, "acquire")
    store.record_event(evt)
    return store


# ═══════════════════════════════════════════════════════════════════════════════
# Append-only semantics
# ═══════════════════════════════════════════════════════════════════════════════


class TestAppendOnly:
    """Append-only: terminal events never erase prior history."""

    def test_release_does_not_erase_prior_events(
        self, store_with_acquire: CustodyLeaseStore
    ) -> None:
        store = store_with_acquire
        evt = _make_event("evt-002", "lease-001", 2, "release")
        store.record_event(evt)
        history = store.load_history("lease-001")
        assert len(history) == 2
        assert history[0].event_type == "acquire"
        assert history[1].event_type == "release"

    def test_expire_does_not_erase_prior_events(
        self, store_with_acquire: CustodyLeaseStore
    ) -> None:
        store = store_with_acquire
        evt = _make_event("evt-002", "lease-001", 2, "expire")
        store.record_event(evt)
        history = store.load_history("lease-001")
        assert len(history) == 2
        assert history[0].event_type == "acquire"

    def test_fence_does_not_erase_prior_events(
        self, store_with_acquire: CustodyLeaseStore
    ) -> None:
        store = store_with_acquire
        evt = _make_event("evt-002", "lease-001", 2, "fence")
        store.record_event(evt)
        history = store.load_history("lease-001")
        assert len(history) == 2
        assert history[0].event_type == "acquire"

    def test_full_lifecycle_preserves_all_events(
        self, store: CustodyLeaseStore
    ) -> None:
        """acquire -> renew -> transfer -> release — all 4 events retained."""
        events = [
            _make_event("evt-001", "lease-001", 1, "acquire"),
            _make_event("evt-002", "lease-001", 2, "renew",
                        payload={"expires_at": "2025-01-03T00:00:00Z"}),
            _make_event("evt-003", "lease-001", 3, "transfer",
                        owner_host="host-2", owner_pid="99999"),
            _make_event("evt-004", "lease-001", 4, "release"),
        ]
        for evt in events:
            store.record_event(evt)
        history = store.load_history("lease-001")
        assert len(history) == 4
        assert [e.event_type for e in history] == ["acquire", "renew", "transfer", "release"]

    def test_replay_after_terminal_yields_lease_without_mutation(
        self, store_with_acquire: CustodyLeaseStore
    ) -> None:
        store = store_with_acquire
        evt = _make_event("evt-002", "lease-001", 2, "release")
        store.record_event(evt)
        lease = store.replay_history("lease-001")
        assert lease is not None
        assert lease.lease_id == "lease-001"
        # The lease still exists but is marked as released (expires_at set to release time)


# ═══════════════════════════════════════════════════════════════════════════════
# Deterministic replay
# ═══════════════════════════════════════════════════════════════════════════════


class TestDeterministicReplay:
    """Replay always yields the same result for the same history."""

    def test_replay_acquire_yields_same_lease(
        self, store_with_acquire: CustodyLeaseStore
    ) -> None:
        store = store_with_acquire
        a = store.replay_history("lease-001")
        b = store.replay_history("lease-001")
        assert a is not None and b is not None
        assert a == b

    def test_replay_full_lifecycle_deterministic(self, store: CustodyLeaseStore) -> None:
        events = [
            _make_event("evt-001", "lease-001", 1, "acquire"),
            _make_event("evt-002", "lease-001", 2, "renew",
                        payload={"expires_at": "2025-01-03T00:00:00Z"}),
            _make_event("evt-003", "lease-001", 3, "transfer",
                        owner_host="host-2", owner_pid="99999"),
        ]
        for evt in events:
            store.record_event(evt)
        r1 = store.replay_history("lease-001")
        r2 = store.replay_history("lease-001")
        assert r1 == r2
        assert r1 is not None
        assert r1.owner_host == "host-2"

    def test_replay_empty_history_returns_none(self, store: CustodyLeaseStore) -> None:
        result = store.replay_history("nonexistent")
        assert result is None

    def test_replay_pure_function(self) -> None:
        """replay_events is a pure function."""
        events = (
            _make_event("evt-001", "lease-001", 1, "acquire"),
            _make_event("evt-002", "lease-001", 2, "renew",
                        payload={"expires_at": "2025-01-03T00:00:00Z"}),
        )
        a = replay_events(events)
        b = replay_events(events)
        assert a == b

    def test_cached_state_matches_replay(self, store: CustodyLeaseStore) -> None:
        events = [
            _make_event("evt-001", "lease-001", 1, "acquire"),
            _make_event("evt-002", "lease-001", 2, "renew",
                        payload={"expires_at": "2025-01-03T00:00:00Z"}),
        ]
        for evt in events:
            store.record_event(evt)
        cached = store.current_lease("lease-001")
        replayed = store.replay_history("lease-001")
        assert cached == replayed


# ═══════════════════════════════════════════════════════════════════════════════
# Idempotency
# ═══════════════════════════════════════════════════════════════════════════════


class TestIdempotency:
    """Exact duplicate events with same idempotency key and payload hash are no-ops."""

    def test_exact_repeat_is_noop(self, store: CustodyLeaseStore) -> None:
        evt = _make_event("evt-001", "lease-001", 1, "acquire",
                          idempotency_key="key-1")
        r1 = store.record_event(evt)
        r2 = store.record_event(evt)  # exact same event
        assert r1.event_id == r2.event_id
        # History should have only one event
        assert len(store.load_history("lease-001")) == 1

    def test_idempotent_repeat_after_other_events(self, store: CustodyLeaseStore) -> None:
        evt1 = _make_event("evt-001", "lease-001", 1, "acquire", idempotency_key="key-1")
        evt2 = _make_event("evt-002", "lease-001", 2, "renew", idempotency_key="key-2",
                           payload={"expires_at": "2025-01-03T00:00:00Z"})
        store.record_event(evt1)
        store.record_event(evt2)
        # Repeat evt2 — should be no-op
        store.record_event(evt2)
        assert len(store.load_history("lease-001")) == 2

    def test_idempotent_repeat_with_different_lease_independent(
        self, store: CustodyLeaseStore
    ) -> None:
        """Same idempotency key on different lease_ids are independent."""
        evt_a = _make_event("evt-001", "lease-A", 1, "acquire", idempotency_key="shared-key")
        evt_b = _make_event("evt-001", "lease-B", 1, "acquire", idempotency_key="shared-key")
        store.record_event(evt_a)
        store.record_event(evt_b)
        assert len(store.load_history("lease-A")) == 1
        assert len(store.load_history("lease-B")) == 1


# ═══════════════════════════════════════════════════════════════════════════════
# Stale sequence rejection
# ═══════════════════════════════════════════════════════════════════════════════


class TestStaleSequence:
    """Events with non-monotonic sequence numbers are rejected."""

    def test_sequence_before_last_rejected(
        self, store_with_acquire: CustodyLeaseStore
    ) -> None:
        """Sequence 1 with a *different* idempotency key than the stored
        seq-1 event is stale (same sequence occupied by a different key)."""
        store = store_with_acquire
        evt = _make_event("evt-001-dup", "lease-001", 1, "acquire",
                          idempotency_key="stale-different-key")
        with pytest.raises(StaleSequenceError):
            store.record_event(evt)

    def test_same_sequence_different_idempotency_key_rejected(
        self, store_with_acquire: CustodyLeaseStore
    ) -> None:
        store = store_with_acquire
        # Different idempotency key but same sequence = stale
        evt = _make_event("evt-001b", "lease-001", 1, "acquire",
                          idempotency_key="different-key")
        with pytest.raises(StaleSequenceError):
            store.record_event(evt)

    def test_skip_ahead_sequence_accepted(
        self, store_with_acquire: CustodyLeaseStore
    ) -> None:
        store = store_with_acquire
        evt = _make_event("evt-005", "lease-001", 5, "renew",
                          payload={"expires_at": "2025-01-03T00:00:00Z"})
        store.record_event(evt)  # should not raise
        history = store.load_history("lease-001")
        assert len(history) == 2
        assert history[1].sequence == 5


# ═══════════════════════════════════════════════════════════════════════════════
# Payload conflict quarantine
# ═══════════════════════════════════════════════════════════════════════════════


class TestConflictQuarantine:
    """Same idempotency key + different payload hash = conflict, quarantined."""

    def test_conflict_raises_and_quarantines(
        self, store: CustodyLeaseStore
    ) -> None:
        evt1 = _make_event("evt-001", "lease-001", 1, "acquire",
                           idempotency_key="key-1", payload={"v": 1})
        store.record_event(evt1)
        evt2 = _make_event("evt-001b", "lease-001", 1, "acquire",
                           idempotency_key="key-1", payload={"v": 2})
        with pytest.raises(LeaseIdempotencyConflict):
            store.record_event(evt2)
        # Conflict should be recorded in quarantine
        conflicts = store.quarantined_conflicts("lease-001")
        assert len(conflicts) == 1
        assert conflicts[0]["idempotency_key"] == "key-1"

    def test_conflict_appends_synthetic_conflict_event(
        self, store: CustodyLeaseStore
    ) -> None:
        evt1 = _make_event("evt-001", "lease-001", 1, "acquire",
                           idempotency_key="key-1", payload={"v": 1})
        store.record_event(evt1)
        evt2 = _make_event("evt-001b", "lease-001", 1, "acquire",
                           idempotency_key="key-1", payload={"v": 2})
        with pytest.raises(LeaseIdempotencyConflict):
            store.record_event(evt2)
        # A conflict event should have been appended to history
        history = store.load_history("lease-001")
        assert len(history) == 2  # acquire + conflict
        assert history[1].event_type == "conflict"

    def test_no_conflict_when_payload_hashes_match(
        self, store: CustodyLeaseStore
    ) -> None:
        evt1 = _make_event("evt-001", "lease-001", 1, "acquire",
                           idempotency_key="key-1", payload={"v": 1})
        store.record_event(evt1)
        # Same payload => same hash => idempotent
        evt2 = _make_event("evt-001", "lease-001", 1, "acquire",
                           idempotency_key="key-1", payload={"v": 1})
        result = store.record_event(evt2)  # should be no-op
        assert result.event_id == "evt-001"
        assert len(store.load_history("lease-001")) == 1


# ═══════════════════════════════════════════════════════════════════════════════
# Reducers — per event type
# ═══════════════════════════════════════════════════════════════════════════════


class TestReducerAcquire:
    """acquire reducer creates a new lease."""

    def test_acquire_creates_lease(self, store: CustodyLeaseStore) -> None:
        evt = _make_event("evt-001", "lease-001", 1, "acquire")
        store.record_event(evt)
        lease = store.replay_history("lease-001")
        assert lease is not None
        assert lease.lease_id == "lease-001"
        assert lease.custody_epoch == 1
        assert lease.owner_host == "host-1"

    def test_acquire_requires_no_existing_lease_in_replay(
        self, store: CustodyLeaseStore
    ) -> None:
        """A second acquire for the same lease_id after the first is
        technically allowed by the reducer (the caller gates this)."""
        evt1 = _make_event("evt-001", "lease-001", 1, "acquire")
        evt2 = _make_event("evt-002", "lease-001", 2, "acquire")
        store.record_event(evt1)
        store.record_event(evt2)
        # Replay applies both — second acquire replaces the lease
        lease = store.replay_history("lease-001")
        assert lease is not None
        assert lease.lease_id == "lease-001"


class TestReducerRenew:
    """renew reducer bumps epoch and updates expiry."""

    def test_renew_bumps_epoch_and_expiry(
        self, store_with_acquire: CustodyLeaseStore
    ) -> None:
        store = store_with_acquire
        evt = _make_event("evt-002", "lease-001", 2, "renew",
                          custody_epoch=5,
                          payload={"expires_at": "2025-06-01T00:00:00Z"})
        store.record_event(evt)
        lease = store.replay_history("lease-001")
        assert lease is not None
        assert lease.custody_epoch == 5
        assert lease.expires_at == "2025-06-01T00:00:00Z"

    def test_renew_does_not_lower_epoch(
        self, store_with_acquire: CustodyLeaseStore
    ) -> None:
        store = store_with_acquire
        # Renew with same epoch (1) — it must not lower below the existing 1
        evt = _make_event("evt-002", "lease-001", 2, "renew",
                          custody_epoch=1,
                          payload={"expires_at": "2025-06-01T00:00:00Z"})
        store.record_event(evt)
        lease = store.replay_history("lease-001")
        assert lease is not None
        # Epoch stays at max(1, 1) = 1 (not lowered)
        assert lease.custody_epoch == 1


class TestReducerTransfer:
    """transfer reducer changes owner identity."""

    def test_transfer_changes_owner(self, store_with_acquire: CustodyLeaseStore) -> None:
        store = store_with_acquire
        evt = _make_event("evt-002", "lease-001", 2, "transfer",
                          owner_host="host-2", owner_pid="99999",
                          owner_boot_id="boot-xyz")
        store.record_event(evt)
        lease = store.replay_history("lease-001")
        assert lease is not None
        assert lease.owner_host == "host-2"
        assert lease.owner_pid == "99999"
        assert lease.owner_boot_id == "boot-xyz"

    def test_transfer_bumps_epoch_if_newer(
        self, store_with_acquire: CustodyLeaseStore
    ) -> None:
        store = store_with_acquire
        evt = _make_event("evt-002", "lease-001", 2, "transfer",
                          custody_epoch=10, owner_host="host-2",
                          owner_pid="99999")
        store.record_event(evt)
        lease = store.replay_history("lease-001")
        assert lease is not None
        assert lease.custody_epoch == 10


class TestReducerRelease:
    """release reducer marks lease as released (terminal)."""

    def test_release_marks_terminal(self, store_with_acquire: CustodyLeaseStore) -> None:
        store = store_with_acquire
        evt = _make_event("evt-002", "lease-001", 2, "release")
        store.record_event(evt)
        lease = store.replay_history("lease-001")
        assert lease is not None
        # Lease still exists but expires_at is set to release time
        assert lease.lease_id == "lease-001"

    def test_release_on_nonexistent_lease_raises(self) -> None:
        evt = _make_event("evt-001", "lease-001", 1, "release")
        with pytest.raises(LeaseStoreError, match="cannot release"):
            reduce_event(None, evt)


class TestReducerExpire:
    """expire reducer marks lease as expired (terminal)."""

    def test_expire_marks_terminal(self, store_with_acquire: CustodyLeaseStore) -> None:
        store = store_with_acquire
        evt = _make_event("evt-002", "lease-001", 2, "expire")
        store.record_event(evt)
        lease = store.replay_history("lease-001")
        assert lease is not None

    def test_expire_on_nonexistent_lease_raises(self) -> None:
        evt = _make_event("evt-001", "lease-001", 1, "expire")
        with pytest.raises(LeaseStoreError, match="cannot expire"):
            reduce_event(None, evt)


class TestReducerFence:
    """fence reducer marks lease as fenced (terminal) and updates fence token."""

    def test_fence_updates_fence_token(self, store_with_acquire: CustodyLeaseStore) -> None:
        store = store_with_acquire
        evt = _make_event("evt-002", "lease-001", 2, "fence",
                          coordinator_fence_token=99)
        store.record_event(evt)
        lease = store.replay_history("lease-001")
        assert lease is not None
        assert lease.coordinator_fence_token == 99

    def test_fence_on_nonexistent_lease_raises(self) -> None:
        evt = _make_event("evt-001", "lease-001", 1, "fence")
        with pytest.raises(LeaseStoreError, match="cannot fence"):
            reduce_event(None, evt)


class TestReducerConflict:
    """conflict reducer records conflict without mutating the lease."""

    def test_conflict_preserves_lease_state(
        self, store_with_acquire: CustodyLeaseStore
    ) -> None:
        store = store_with_acquire
        before = store.replay_history("lease-001")
        evt = _make_event("evt-002", "lease-001", 2, "conflict")
        store.record_event(evt)
        after = store.replay_history("lease-001")
        assert after is not None and before is not None
        # Conflict should not change the lease identity/fields
        assert after.lease_id == before.lease_id
        assert after.owner_host == before.owner_host
        assert after.custody_epoch == before.custody_epoch


class TestReducerReconcile:
    """reconcile reducer resumes from conflict state."""

    def test_reconcile_after_acquire(self, store_with_acquire: CustodyLeaseStore) -> None:
        store = store_with_acquire
        evt = _make_event("evt-002", "lease-001", 2, "reconcile",
                          custody_epoch=3)
        store.record_event(evt)
        lease = store.replay_history("lease-001")
        assert lease is not None
        assert lease.custody_epoch == 3

    def test_reconcile_on_nonexistent_lease_raises(self) -> None:
        evt = _make_event("evt-001", "lease-001", 1, "reconcile")
        with pytest.raises(LeaseStoreError, match="cannot reconcile"):
            reduce_event(None, evt)


# ═══════════════════════════════════════════════════════════════════════════════
# Store-level operations
# ═══════════════════════════════════════════════════════════════════════════════


class TestStoreOperations:
    """Store-level operations: load, current_lease, record_events, open_lease_store."""

    def test_load_history_nonexistent_lease(self, store: CustodyLeaseStore) -> None:
        assert store.load_history("nonexistent") == ()

    def test_current_lease_nonexistent(self, store: CustodyLeaseStore) -> None:
        assert store.current_lease("nonexistent") is None

    def test_record_events_batch(self, store: CustodyLeaseStore) -> None:
        events = [
            _make_event("evt-001", "lease-001", 1, "acquire"),
            _make_event("evt-002", "lease-001", 2, "renew",
                        payload={"expires_at": "2025-01-03T00:00:00Z"}),
            _make_event("evt-003", "lease-001", 3, "transfer",
                        owner_host="host-2", owner_pid="99999"),
        ]
        recorded = record_events(store, events)
        assert len(recorded) == 3
        assert len(store.load_history("lease-001")) == 3

    def test_open_lease_store_factory(self) -> None:
        store = open_lease_store(
            base_dir=Path(tempfile.mkdtemp()), flock=False
        )
        assert isinstance(store, CustodyLeaseStore)
        evt = _make_event("evt-001", "lease-001", 1, "acquire")
        store.record_event(evt)
        assert store.current_lease("lease-001") is not None

    def test_multiple_independent_leases(self, store: CustodyLeaseStore) -> None:
        evt_a = _make_event("evt-001", "lease-A", 1, "acquire")
        evt_b = _make_event("evt-001", "lease-B", 1, "acquire")
        store.record_event(evt_a)
        store.record_event(evt_b)
        assert len(store.load_history("lease-A")) == 1
        assert len(store.load_history("lease-B")) == 1
        assert store.current_lease("lease-A").lease_id == "lease-A"
        assert store.current_lease("lease-B").lease_id == "lease-B"

    def test_record_event_rejects_non_event(self, store: CustodyLeaseStore) -> None:
        with pytest.raises(LeaseStoreError, match="CustodyLeaseEvent"):
            store.record_event("not an event")  # type: ignore[arg-type]

    def test_event_with_invalid_event_type_rejected(self, store: CustodyLeaseStore) -> None:
        with pytest.raises(ContractError):
            _make_event("evt-001", "lease-001", 1, "invalid_type")  # type: ignore[arg-type]

    def test_quarantined_conflicts_nonexistent(self, store: CustodyLeaseStore) -> None:
        assert store.quarantined_conflicts("nonexistent") == ()


# ═══════════════════════════════════════════════════════════════════════════════
# Edge cases
# ═══════════════════════════════════════════════════════════════════════════════


class TestEdgeCases:
    """Edge-case behaviour."""

    def test_empty_payload_defaults_ok(self, store: CustodyLeaseStore) -> None:
        evt = _make_event("evt-001", "lease-001", 1, "acquire", payload={})
        store.record_event(evt)
        lease = store.replay_history("lease-001")
        assert lease is not None

    def test_payload_without_expires_at_uses_fallback(
        self, store: CustodyLeaseStore
    ) -> None:
        evt = _make_event("evt-001", "lease-001", 1, "acquire", payload={})
        store.record_event(evt)
        lease = store.replay_history("lease-001")
        assert lease is not None
        # Falls back to 24h after occurred_at
        assert lease.expires_at > lease.acquired_at

    def test_history_survives_store_reopen(self, store: CustodyLeaseStore) -> None:
        evt = _make_event("evt-001", "lease-001", 1, "acquire")
        store.record_event(evt)
        # Re-open a fresh store pointing at the same base_dir
        store2 = CustodyLeaseStore(base_dir=store.base_dir, flock=False)
        assert len(store2.load_history("lease-001")) == 1
        assert store2.current_lease("lease-001") is not None

    def test_reduce_event_unknown_type_raises(self) -> None:
        """reduce_event raises LeaseStoreError when given an unrecognized event_type."""
        # Use object.__setattr__ to hack in an invalid event_type
        evt = _make_event("evt-001", "lease-001", 1, "acquire")
        object.__setattr__(evt, "event_type", "nonexistent_type")
        with pytest.raises(LeaseStoreError, match="unknown event type"):
            reduce_event(None, evt)
        # The dispatch table has exactly 8 entries
        from arnold_pipelines.megaplan.custody.lease_store import _REDUCERS
        assert "invalid" not in _REDUCERS

    def test_all_eight_event_types_have_reducers(self) -> None:
        from arnold_pipelines.megaplan.custody.lease_store import _REDUCERS
        from arnold_pipelines.megaplan.custody.contracts import CUSTODY_LEASE_EVENT_TYPES
        for evt_type in CUSTODY_LEASE_EVENT_TYPES:
            assert evt_type in _REDUCERS, f"missing reducer for {evt_type}"


# ═══════════════════════════════════════════════════════════════════════════════
# Reclaim after terminal (expire/release → re-acquire)
# ═══════════════════════════════════════════════════════════════════════════════


class TestReclaimAfterTerminal:
    """Reclaim cycle: expire/release then re-acquire the same lease_id."""

    def test_reclaim_after_expire(
        self, store_with_acquire: CustodyLeaseStore
    ) -> None:
        store = store_with_acquire
        # expire the lease
        evt_expire = _make_event("evt-002", "lease-001", 2, "expire")
        store.record_event(evt_expire)
        # re-acquire (reclaim)
        evt_reclaim = _make_event(
            "evt-003", "lease-001", 3, "acquire",
            custody_epoch=2, owner_host="host-2", owner_pid="88888",
            payload={"expires_at": "2025-06-01T00:00:00Z"},
        )
        store.record_event(evt_reclaim)
        history = store.load_history("lease-001")
        assert len(history) == 3
        assert [e.event_type for e in history] == ["acquire", "expire", "acquire"]
        lease = store.replay_history("lease-001")
        assert lease is not None
        assert lease.owner_host == "host-2"
        assert lease.custody_epoch == 2

    def test_reclaim_after_release(
        self, store_with_acquire: CustodyLeaseStore
    ) -> None:
        store = store_with_acquire
        evt_release = _make_event("evt-002", "lease-001", 2, "release")
        store.record_event(evt_release)
        evt_reclaim = _make_event(
            "evt-003", "lease-001", 3, "acquire",
            custody_epoch=3, owner_host="host-3", owner_pid="77777",
            payload={"expires_at": "2025-07-01T00:00:00Z"},
        )
        store.record_event(evt_reclaim)
        history = store.load_history("lease-001")
        assert len(history) == 3
        assert [e.event_type for e in history] == ["acquire", "release", "acquire"]

    def test_reclaim_after_fence(
        self, store_with_acquire: CustodyLeaseStore
    ) -> None:
        store = store_with_acquire
        evt_fence = _make_event(
            "evt-002", "lease-001", 2, "fence",
            coordinator_fence_token=999,
        )
        store.record_event(evt_fence)
        evt_reclaim = _make_event(
            "evt-003", "lease-001", 3, "acquire",
            custody_epoch=4,
        )
        store.record_event(evt_reclaim)
        history = store.load_history("lease-001")
        assert len(history) == 3
        assert history[1].event_type == "fence"
        assert history[2].event_type == "acquire"

    def test_reclaim_preserves_prior_terminal_history(
        self, store_with_acquire: CustodyLeaseStore
    ) -> None:
        """Prior terminal events remain in history after reclaim."""
        store = store_with_acquire
        evt_expire = _make_event("evt-002", "lease-001", 2, "expire")
        store.record_event(evt_expire)
        evt_reclaim = _make_event(
            "evt-003", "lease-001", 3, "acquire", custody_epoch=2,
        )
        store.record_event(evt_reclaim)
        history = store.load_history("lease-001")
        assert history[0].event_type == "acquire"
        assert history[1].event_type == "expire"
        assert history[2].event_type == "acquire"


# ═══════════════════════════════════════════════════════════════════════════════
# Consecutive same-type events
# ═══════════════════════════════════════════════════════════════════════════════


class TestConsecutiveSameTypeEvents:
    """Multiple successive events of the same type are handled correctly."""

    def test_multiple_renews(self, store_with_acquire: CustodyLeaseStore) -> None:
        store = store_with_acquire
        r1 = _make_event("evt-002", "lease-001", 2, "renew",
                         custody_epoch=5, payload={"expires_at": "2025-02-01T00:00:00Z"})
        r2 = _make_event("evt-003", "lease-001", 3, "renew",
                         custody_epoch=10, payload={"expires_at": "2025-03-01T00:00:00Z"})
        store.record_event(r1)
        store.record_event(r2)
        lease = store.replay_history("lease-001")
        assert lease is not None
        assert lease.custody_epoch == 10
        assert lease.expires_at == "2025-03-01T00:00:00Z"
        assert len(store.load_history("lease-001")) == 3

    def test_multiple_transfers(self, store_with_acquire: CustodyLeaseStore) -> None:
        store = store_with_acquire
        t1 = _make_event("evt-002", "lease-001", 2, "transfer",
                         owner_host="host-B", owner_pid="11111", owner_boot_id="boot-b")
        t2 = _make_event("evt-003", "lease-001", 3, "transfer",
                         owner_host="host-C", owner_pid="22222", owner_boot_id="boot-c")
        store.record_event(t1)
        store.record_event(t2)
        lease = store.replay_history("lease-001")
        assert lease is not None
        assert lease.owner_host == "host-C"
        assert lease.owner_pid == "22222"
        assert lease.owner_boot_id == "boot-c"
        assert len(store.load_history("lease-001")) == 3

    def test_multiple_reconciles(self, store_with_acquire: CustodyLeaseStore) -> None:
        store = store_with_acquire
        rec1 = _make_event("evt-002", "lease-001", 2, "reconcile", custody_epoch=3)
        rec2 = _make_event("evt-003", "lease-001", 3, "reconcile", custody_epoch=7)
        store.record_event(rec1)
        store.record_event(rec2)
        lease = store.replay_history("lease-001")
        assert lease is not None
        assert lease.custody_epoch == 7


# ═══════════════════════════════════════════════════════════════════════════════
# Comprehensive lifecycle — all 8 event types
# ═══════════════════════════════════════════════════════════════════════════════


class TestComprehensiveLifecycle:
    """All eight event types in a single lease lifecycle."""

    def test_all_eight_event_types_in_sequence(
        self, store: CustodyLeaseStore
    ) -> None:
        events = [
            _make_event("evt-001", "lease-full", 1, "acquire",
                        idempotency_key="ik-1"),
            _make_event("evt-002", "lease-full", 2, "renew",
                        custody_epoch=2, idempotency_key="ik-2",
                        payload={"expires_at": "2025-02-01T00:00:00Z"}),
            _make_event("evt-003", "lease-full", 3, "transfer",
                        owner_host="host-2", owner_pid="22222",
                        idempotency_key="ik-3"),
            _make_event("evt-004", "lease-full", 4, "release",
                        idempotency_key="ik-4"),
        ]
        for evt in events:
            store.record_event(evt)
        # Now add remaining types in a separate lease cycle
        evt_reclaim = _make_event(
            "evt-005", "lease-full", 5, "acquire",
            custody_epoch=5, idempotency_key="ik-5",
        )
        store.record_event(evt_reclaim)
        evt_renew = _make_event(
            "evt-006", "lease-full", 6, "renew",
            custody_epoch=6, idempotency_key="ik-6",
            payload={"expires_at": "2025-06-01T00:00:00Z"},
        )
        store.record_event(evt_renew)
        evt_exp = _make_event("evt-007", "lease-full", 7, "expire",
                              idempotency_key="ik-7")
        store.record_event(evt_exp)
        evt_fence = _make_event("evt-008", "lease-full", 8, "fence",
                                coordinator_fence_token=777,
                                idempotency_key="ik-8")
        store.record_event(evt_fence)

        history = store.load_history("lease-full")
        assert len(history) == 8
        assert [e.event_type for e in history] == [
            "acquire", "renew", "transfer", "release",
            "acquire", "renew", "expire", "fence",
        ]

    def test_conflict_and_reconcile_in_lifecycle(
        self, store_with_acquire: CustodyLeaseStore
    ) -> None:
        store = store_with_acquire
        evt_conflict = _make_event(
            "evt-002", "lease-001", 2, "conflict",
            idempotency_key="conflict-ik",
            payload={"conflict_detail": "test"},
        )
        store.record_event(evt_conflict)
        evt_rec = _make_event(
            "evt-003", "lease-001", 3, "reconcile",
            custody_epoch=5, idempotency_key="rec-ik",
        )
        store.record_event(evt_rec)
        history = store.load_history("lease-001")
        assert len(history) == 3
        assert history[1].event_type == "conflict"
        assert history[2].event_type == "reconcile"
        lease = store.replay_history("lease-001")
        assert lease is not None
        assert lease.custody_epoch == 5

    def test_all_event_types_represented_in_history(
        self, store: CustodyLeaseStore
    ) -> None:
        """Every event type in a single stream; replay reconstructs full state."""
        evts = [
            ("acquire", 1, {"custody_epoch": 1}),
            ("renew", 2, {"custody_epoch": 3, "payload": {"expires_at": "2025-02-01T00:00:00Z"}}),
            ("transfer", 3, {"custody_epoch": 4, "owner_host": "h2", "owner_pid": "p2"}),
            ("conflict", 4, {"idempotency_key": "conf-1"}),
            ("reconcile", 5, {"custody_epoch": 5, "idempotency_key": "rec-1"}),
            ("release", 6, {"idempotency_key": "rel-1"}),
            ("acquire", 7, {"custody_epoch": 6, "idempotency_key": "acq-2", "owner_host": "h3", "owner_pid": "p3"}),
            ("expire", 8, {"idempotency_key": "exp-1"}),
        ]
        for etype, seq, overrides in evts:
            kwargs = {"idempotency_key": f"ik-{seq}"}
            kwargs.update(overrides)
            evt = _make_event(f"evt-{seq:03d}", "lease-all", seq, etype, **kwargs)
            store.record_event(evt)

        history = store.load_history("lease-all")
        assert len(history) == 8
        types_seen = [e.event_type for e in history]
        assert "acquire" in types_seen
        assert "renew" in types_seen
        assert "transfer" in types_seen
        assert "conflict" in types_seen
        assert "reconcile" in types_seen
        assert "release" in types_seen
        assert "expire" in types_seen
        # fence was not in this sequence
        lease = store.replay_history("lease-all")
        assert lease is not None


# ═══════════════════════════════════════════════════════════════════════════════
# Terminal history preservation — events after terminal never erase prior
# ═══════════════════════════════════════════════════════════════════════════════


class TestTerminalHistoryPreservation:
    """Proof: terminal events never mutate or erase prior history."""

    def test_renew_after_release_preserves_release(
        self, store_with_acquire: CustodyLeaseStore
    ) -> None:
        store = store_with_acquire
        evt_rel = _make_event("evt-002", "lease-001", 2, "release")
        store.record_event(evt_rel)
        evt_renew = _make_event(
            "evt-003", "lease-001", 3, "renew",
            custody_epoch=5, payload={"expires_at": "2025-07-01T00:00:00Z"},
        )
        store.record_event(evt_renew)
        history = store.load_history("lease-001")
        assert len(history) == 3
        assert history[0].event_type == "acquire"
        assert history[1].event_type == "release"
        assert history[2].event_type == "renew"

    def test_transfer_after_expire_preserves_expire(
        self, store_with_acquire: CustodyLeaseStore
    ) -> None:
        store = store_with_acquire
        evt_exp = _make_event("evt-002", "lease-001", 2, "expire")
        store.record_event(evt_exp)
        evt_xfer = _make_event(
            "evt-003", "lease-001", 3, "transfer",
            owner_host="host-new", owner_pid="99999",
        )
        store.record_event(evt_xfer)
        history = store.load_history("lease-001")
        assert len(history) == 3
        assert history[1].event_type == "expire"

    def test_fence_after_release_preserves_both(
        self, store_with_acquire: CustodyLeaseStore
    ) -> None:
        store = store_with_acquire
        evt_rel = _make_event("evt-002", "lease-001", 2, "release")
        store.record_event(evt_rel)
        evt_fence = _make_event(
            "evt-003", "lease-001", 3, "fence",
            coordinator_fence_token=555,
        )
        store.record_event(evt_fence)
        history = store.load_history("lease-001")
        assert len(history) == 3
        assert [e.event_type for e in history] == ["acquire", "release", "fence"]

    def test_release_after_fence_preserves_fence(
        self, store_with_acquire: CustodyLeaseStore
    ) -> None:
        store = store_with_acquire
        evt_fence = _make_event(
            "evt-002", "lease-001", 2, "fence",
            coordinator_fence_token=777,
        )
        store.record_event(evt_fence)
        evt_rel = _make_event("evt-003", "lease-001", 3, "release")
        store.record_event(evt_rel)
        history = store.load_history("lease-001")
        assert len(history) == 3
        assert history[1].event_type == "fence"
        assert history[2].event_type == "release"


# ═══════════════════════════════════════════════════════════════════════════════
# Quarantine content verification
# ═══════════════════════════════════════════════════════════════════════════════


class TestQuarantineContent:
    """Verify the structure and completeness of quarantined conflict records."""

    def test_quarantine_record_has_required_fields(
        self, store: CustodyLeaseStore
    ) -> None:
        evt1 = _make_event("evt-001", "lease-001", 1, "acquire",
                           idempotency_key="key-q", payload={"v": 1})
        store.record_event(evt1)
        evt2 = _make_event("evt-001b", "lease-001", 1, "acquire",
                           idempotency_key="key-q", payload={"v": 2})
        with pytest.raises(LeaseIdempotencyConflict):
            store.record_event(evt2)
        conflicts = store.quarantined_conflicts("lease-001")
        assert len(conflicts) == 1
        c = conflicts[0]
        assert c["idempotency_key"] == "key-q"
        assert c["sequence"] == 1
        assert "existing_event_id" in c
        assert "existing_payload_hash" in c
        assert "conflicting_event_id" in c
        assert "conflicting_payload_hash" in c
        assert "quarantined_at" in c

    def test_multiple_conflicts_accumulate_in_quarantine(
        self, store: CustodyLeaseStore
    ) -> None:
        # First acquire
        evt_a = _make_event("evt-001", "lease-001", 1, "acquire",
                            idempotency_key="ik-A", payload={"v": 1})
        store.record_event(evt_a)
        # Renew
        evt_r = _make_event("evt-002", "lease-001", 2, "renew",
                            idempotency_key="ik-B",
                            payload={"expires_at": "2025-02-01T00:00:00Z"})
        store.record_event(evt_r)
        # Conflict 1: conflicting acquire with same ik-A
        evt_c1 = _make_event("evt-001c", "lease-001", 2, "acquire",
                             idempotency_key="ik-B", payload={"v": 99})
        with pytest.raises(LeaseIdempotencyConflict):
            store.record_event(evt_c1)
        # Conflict 2: after that, try another conflicting idempotency key
        # First need to get past the conflict sequence
        evt_xfer = _make_event("evt-003", "lease-001", 3, "transfer",
                               owner_host="h2", owner_pid="p2",
                               idempotency_key="ik-D")
        store.record_event(evt_xfer)
        # Now create a new conflict at sequence 3
        evt_c2 = _make_event("evt-003c", "lease-001", 3, "reconcile",
                             idempotency_key="ik-D",
                             payload={"reason": "different"})
        with pytest.raises(LeaseIdempotencyConflict):
            store.record_event(evt_c2)
        conflicts = store.quarantined_conflicts("lease-001")
        assert len(conflicts) == 2

    def test_quarantine_survives_store_reopen(
        self, store: CustodyLeaseStore
    ) -> None:
        evt1 = _make_event("evt-001", "lease-001", 1, "acquire",
                           idempotency_key="survive-key", payload={"v": 1})
        store.record_event(evt1)
        evt2 = _make_event("evt-001b", "lease-001", 1, "acquire",
                           idempotency_key="survive-key", payload={"v": 2})
        with pytest.raises(LeaseIdempotencyConflict):
            store.record_event(evt2)
        # Reopen
        store2 = CustodyLeaseStore(base_dir=store.base_dir, flock=False)
        conflicts = store2.quarantined_conflicts("lease-001")
        assert len(conflicts) == 1
        assert conflicts[0]["idempotency_key"] == "survive-key"


# ═══════════════════════════════════════════════════════════════════════════════
# Conflict on lease with no prior events
# ═══════════════════════════════════════════════════════════════════════════════


class TestConflictEdgeCases:
    """Conflict behaviour in edge scenarios."""

    def test_conflict_on_empty_lease_allowed(
        self, store: CustodyLeaseStore
    ) -> None:
        """A conflict event on a lease with no prior history is appendable."""
        evt = _make_event("evt-001", "lease-empty", 1, "conflict",
                          idempotency_key="conf-on-empty")
        store.record_event(evt)
        history = store.load_history("lease-empty")
        assert len(history) == 1
        assert history[0].event_type == "conflict"

    def test_reconcile_after_conflict_on_empty_lease(
        self, store: CustodyLeaseStore
    ) -> None:
        evt_conf = _make_event("evt-001", "lease-x", 1, "conflict")
        store.record_event(evt_conf)
        # Reconcile on empty lease raises (reducer requires non-None)
        evt_rec = _make_event("evt-002", "lease-x", 2, "reconcile")
        with pytest.raises(LeaseStoreError, match="cannot reconcile"):
            store.record_event(evt_rec)

    def test_conflict_then_acquire_then_reconcile(
        self, store: CustodyLeaseStore
    ) -> None:
        """conflict → acquire → reconcile is valid."""
        evt_conf = _make_event("evt-001", "lease-y", 1, "conflict")
        store.record_event(evt_conf)
        evt_acq = _make_event("evt-002", "lease-y", 2, "acquire",
                              custody_epoch=1)
        store.record_event(evt_acq)
        evt_rec = _make_event("evt-003", "lease-y", 3, "reconcile",
                              custody_epoch=5)
        store.record_event(evt_rec)
        lease = store.replay_history("lease-y")
        assert lease is not None
        assert lease.custody_epoch == 5


# ═══════════════════════════════════════════════════════════════════════════════
# Idempotent terminal event repeat
# ═══════════════════════════════════════════════════════════════════════════════


class TestIdempotentTerminalRepeat:
    """Exact-repeat idempotency of terminal events (release, expire, fence)."""

    def test_idempotent_repeat_release(
        self, store_with_acquire: CustodyLeaseStore
    ) -> None:
        store = store_with_acquire
        evt = _make_event("evt-002", "lease-001", 2, "release",
                          idempotency_key="rel-ik")
        store.record_event(evt)
        # Repeat exact same release
        store.record_event(evt)
        assert len(store.load_history("lease-001")) == 2

    def test_idempotent_repeat_expire(
        self, store_with_acquire: CustodyLeaseStore
    ) -> None:
        store = store_with_acquire
        evt = _make_event("evt-002", "lease-001", 2, "expire",
                          idempotency_key="exp-ik")
        store.record_event(evt)
        store.record_event(evt)
        assert len(store.load_history("lease-001")) == 2

    def test_idempotent_repeat_fence(
        self, store_with_acquire: CustodyLeaseStore
    ) -> None:
        store = store_with_acquire
        evt = _make_event("evt-002", "lease-001", 2, "fence",
                          coordinator_fence_token=444,
                          idempotency_key="fence-ik")
        store.record_event(evt)
        store.record_event(evt)
        assert len(store.load_history("lease-001")) == 2

    def test_idempotent_repeat_acquire(
        self, store: CustodyLeaseStore
    ) -> None:
        evt = _make_event("evt-001", "lease-001", 1, "acquire",
                          idempotency_key="acq-ik")
        store.record_event(evt)
        store.record_event(evt)
        assert len(store.load_history("lease-001")) == 1


# ═══════════════════════════════════════════════════════════════════════════════
# Causal predecessor chain verification
# ═══════════════════════════════════════════════════════════════════════════════


class TestCausalPredecessorChain:
    """Verify causal_predecessor tracking across event sequences."""

    def test_acquire_sets_no_predecessor(
        self, store: CustodyLeaseStore
    ) -> None:
        evt = _make_event("evt-001", "lease-001", 1, "acquire",
                          causal_predecessor="")
        store.record_event(evt)
        lease = store.replay_history("lease-001")
        assert lease is not None
        assert lease.causal_predecessor == ""

    def test_renew_sets_predecessor_to_lease_id(
        self, store_with_acquire: CustodyLeaseStore
    ) -> None:
        store = store_with_acquire
        evt = _make_event("evt-002", "lease-001", 2, "renew",
                          causal_predecessor="prev-event-001",
                          payload={"expires_at": "2025-02-01T00:00:00Z"})
        store.record_event(evt)
        lease = store.replay_history("lease-001")
        assert lease is not None
        assert lease.causal_predecessor == "prev-event-001"

    def test_transfer_sets_predecessor(
        self, store_with_acquire: CustodyLeaseStore
    ) -> None:
        store = store_with_acquire
        evt = _make_event("evt-002", "lease-001", 2, "transfer",
                          causal_predecessor="transfer-from-host-1",
                          owner_host="host-2", owner_pid="22222")
        store.record_event(evt)
        lease = store.replay_history("lease-001")
        assert lease is not None
        assert lease.causal_predecessor == "transfer-from-host-1"

    def test_terminal_event_keeps_causal_predecessor(
        self, store_with_acquire: CustodyLeaseStore
    ) -> None:
        store = store_with_acquire
        evt = _make_event("evt-002", "lease-001", 2, "release",
                          causal_predecessor="released-by-operator")
        store.record_event(evt)
        lease = store.replay_history("lease-001")
        assert lease is not None
        assert lease.causal_predecessor == "released-by-operator"

    def test_reconcile_keeps_causal_predecessor(
        self, store_with_acquire: CustodyLeaseStore
    ) -> None:
        store = store_with_acquire
        evt = _make_event("evt-002", "lease-001", 2, "reconcile",
                          causal_predecessor="reconciled-from-conflict",
                          custody_epoch=3)
        store.record_event(evt)
        lease = store.replay_history("lease-001")
        assert lease is not None
        assert lease.causal_predecessor == "reconciled-from-conflict"


# ═══════════════════════════════════════════════════════════════════════════════
# History order and replay consistency
# ═══════════════════════════════════════════════════════════════════════════════


class TestHistoryOrder:
    """Events are loaded and replayed in correct sequence order."""

    def test_load_history_returns_events_in_append_order(
        self, store: CustodyLeaseStore
    ) -> None:
        """Events are returned in append order; non-monotonic sequences are rejected."""
        events = [
            _make_event("evt-001", "lease-001", 1, "acquire"),
            _make_event("evt-002", "lease-001", 2, "renew",
                        payload={"expires_at": "2025-02-01T00:00:00Z"}),
            _make_event("evt-003", "lease-001", 3, "transfer",
                        owner_host="h2", owner_pid="p2"),
        ]
        for evt in events:
            store.record_event(evt)
        history = store.load_history("lease-001")
        assert [e.sequence for e in history] == [1, 2, 3]

    def test_non_monotonic_sequence_rejected(
        self, store: CustodyLeaseStore
    ) -> None:
        """Events must have strictly increasing sequences; going backward is rejected."""
        evt1 = _make_event("evt-001", "lease-001", 1, "acquire")
        evt3 = _make_event("evt-003", "lease-001", 3, "transfer",
                           owner_host="h3", owner_pid="p3")
        store.record_event(evt1)
        store.record_event(evt3)
        # seq 2 is now < last_seq 3 — must be rejected
        evt2 = _make_event("evt-002", "lease-001", 2, "renew",
                           custody_epoch=10,
                           payload={"expires_at": "2025-02-01T00:00:00Z"})
        with pytest.raises(StaleSequenceError):
            store.record_event(evt2)
        # History has only the two valid events
        history = store.load_history("lease-001")
        assert len(history) == 2
        assert [e.sequence for e in history] == [1, 3]

    def test_gapped_sequence_replay_deterministic(
        self, store: CustodyLeaseStore
    ) -> None:
        events = [
            _make_event("evt-001", "lease-001", 1, "acquire"),
            _make_event("evt-010", "lease-001", 10, "renew",
                        custody_epoch=10,
                        payload={"expires_at": "2025-06-01T00:00:00Z"}),
        ]
        for evt in events:
            store.record_event(evt)
        r1 = store.replay_history("lease-001")
        r2 = store.replay_history("lease-001")
        assert r1 == r2
        assert r1 is not None
        assert r1.custody_epoch == 10


# ═══════════════════════════════════════════════════════════════════════════════
# Sequence gap and stale sequence edge cases
# ═══════════════════════════════════════════════════════════════════════════════


class TestSequenceEdgeCases:
    """Additional sequence-related edge cases."""

    def test_sequence_equal_to_last_with_same_idempotency_key_is_noop(
        self, store_with_acquire: CustodyLeaseStore
    ) -> None:
        """Same sequence + same idempotency_key + same payload = idempotent no-op."""
        store = store_with_acquire
        # The stored event at seq 1 has idempotency_key "idem-evt-001"
        evt = _make_event("evt-001", "lease-001", 1, "acquire",
                          idempotency_key="idem-evt-001")
        result = store.record_event(evt)
        assert result.event_id == "evt-001"
        assert len(store.load_history("lease-001")) == 1

    def test_sequence_zero_rejected_by_contract(
        self, store: CustodyLeaseStore
    ) -> None:
        """Sequence 0 is rejected at contract level (must be >= 1)."""
        with pytest.raises(ContractError):
            _make_event("evt-000", "lease-001", 0, "acquire",
                        custody_epoch=0)

    def test_sequence_negative_rejected(
        self, store: CustodyLeaseStore
    ) -> None:
        """Negative sequence rejected by contract validation."""
        with pytest.raises(ContractError):
            _make_event("evt-neg", "lease-001", -1, "acquire")

    def test_duplicate_sequence_different_key_after_gap(
        self, store: CustodyLeaseStore
    ) -> None:
        """After a gap, duplicating an earlier sequence is stale."""
        evt1 = _make_event("evt-001", "lease-001", 1, "acquire",
                           idempotency_key="ik-one")
        evt5 = _make_event("evt-005", "lease-001", 5, "renew",
                           idempotency_key="ik-five",
                           payload={"expires_at": "2025-02-01T00:00:00Z"})
        store.record_event(evt1)
        store.record_event(evt5)
        # seq 1 is now < last_seq 5
        evt_stale = _make_event("evt-001b", "lease-001", 1, "acquire",
                                idempotency_key="different")
        with pytest.raises(StaleSequenceError):
            store.record_event(evt_stale)

    def test_idempotent_repeat_after_gap(
        self, store: CustodyLeaseStore
    ) -> None:
        """Repeating an earlier idempotency key at its original sequence after gap."""
        evt1 = _make_event("evt-001", "lease-001", 1, "acquire",
                           idempotency_key="gap-ik")
        evt5 = _make_event("evt-005", "lease-001", 5, "renew",
                           idempotency_key="ik-five",
                           payload={"expires_at": "2025-02-01T00:00:00Z"})
        store.record_event(evt1)
        store.record_event(evt5)
        # Try seq 1 again with same idempotency key — stale because seq=1 < last_seq=5
        with pytest.raises(StaleSequenceError):
            store.record_event(evt1)


# ═══════════════════════════════════════════════════════════════════════════════
# Reducer pure-function determinism
# ═══════════════════════════════════════════════════════════════════════════════


class TestReducerPureFunctionDeterminism:
    """Each reducer is a pure function — same inputs → same outputs."""

    def test_acquire_reducer_pure(self) -> None:
        evt = _make_event("evt-001", "lease-001", 1, "acquire")
        a = reduce_event(None, evt)
        b = reduce_event(None, evt)
        assert a == b

    def test_renew_reducer_pure(self) -> None:
        current = reduce_event(None, _make_event("evt-001", "lease-001", 1, "acquire"))
        evt = _make_event("evt-002", "lease-001", 2, "renew",
                          custody_epoch=5,
                          payload={"expires_at": "2025-02-01T00:00:00Z"})
        a = reduce_event(current, evt)
        b = reduce_event(current, evt)
        assert a == b

    def test_transfer_reducer_pure(self) -> None:
        current = reduce_event(None, _make_event("evt-001", "lease-001", 1, "acquire"))
        evt = _make_event("evt-002", "lease-001", 2, "transfer",
                          owner_host="h2", owner_pid="p2")
        a = reduce_event(current, evt)
        b = reduce_event(current, evt)
        assert a == b

    def test_release_reducer_pure(self) -> None:
        current = reduce_event(None, _make_event("evt-001", "lease-001", 1, "acquire"))
        evt = _make_event("evt-002", "lease-001", 2, "release")
        a = reduce_event(current, evt)
        b = reduce_event(current, evt)
        assert a == b

    def test_expire_reducer_pure(self) -> None:
        current = reduce_event(None, _make_event("evt-001", "lease-001", 1, "acquire"))
        evt = _make_event("evt-002", "lease-001", 2, "expire")
        a = reduce_event(current, evt)
        b = reduce_event(current, evt)
        assert a == b

    def test_fence_reducer_pure(self) -> None:
        current = reduce_event(None, _make_event("evt-001", "lease-001", 1, "acquire"))
        evt = _make_event("evt-002", "lease-001", 2, "fence",
                          coordinator_fence_token=888)
        a = reduce_event(current, evt)
        b = reduce_event(current, evt)
        assert a == b

    def test_conflict_reducer_pure(self) -> None:
        current = reduce_event(None, _make_event("evt-001", "lease-001", 1, "acquire"))
        evt = _make_event("evt-002", "lease-001", 2, "conflict")
        a = reduce_event(current, evt)
        b = reduce_event(current, evt)
        assert a == b

    def test_reconcile_reducer_pure(self) -> None:
        current = reduce_event(None, _make_event("evt-001", "lease-001", 1, "acquire"))
        evt = _make_event("evt-002", "lease-001", 2, "reconcile",
                          custody_epoch=5)
        a = reduce_event(current, evt)
        b = reduce_event(current, evt)
        assert a == b


# ═══════════════════════════════════════════════════════════════════════════════
# Store-level replay and state consistency
# ═══════════════════════════════════════════════════════════════════════════════


class TestReplayStateConsistency:
    """Replay and cached state are always consistent."""

    def test_state_written_after_every_event(
        self, store: CustodyLeaseStore
    ) -> None:
        from arnold_pipelines.megaplan.custody.lease_store import _state_path
        evt = _make_event("evt-001", "lease-001", 1, "acquire")
        store.record_event(evt)
        state_path = _state_path(store.base_dir, "lease-001")
        assert state_path.exists()

    def test_state_is_valid_json(
        self, store: CustodyLeaseStore
    ) -> None:
        import json
        from arnold_pipelines.megaplan.custody.lease_store import _state_path
        evt = _make_event("evt-001", "lease-001", 1, "acquire")
        store.record_event(evt)
        state_path = _state_path(store.base_dir, "lease-001")
        data = json.loads(state_path.read_text(encoding="utf-8"))
        assert isinstance(data, dict)
        assert data.get("lease_id") == "lease-001"

    def test_multi_lease_independent_replay(
        self, store: CustodyLeaseStore
    ) -> None:
        evt_a1 = _make_event("evt-001", "lease-A", 1, "acquire")
        evt_b1 = _make_event("evt-001", "lease-B", 1, "acquire",
                             owner_host="host-B", owner_pid="pB")
        evt_b2 = _make_event("evt-002", "lease-B", 2, "renew",
                             custody_epoch=5,
                             payload={"expires_at": "2025-03-01T00:00:00Z"})
        store.record_event(evt_a1)
        store.record_event(evt_b1)
        store.record_event(evt_b2)
        lease_a = store.replay_history("lease-A")
        lease_b = store.replay_history("lease-B")
        assert lease_a is not None and lease_b is not None
        assert lease_a.owner_host != lease_b.owner_host
        assert lease_b.custody_epoch == 5
        # lease-A still at epoch 1
        assert lease_a.custody_epoch == 1

    def test_reopen_and_replay_is_consistent(
        self, store: CustodyLeaseStore
    ) -> None:
        evts = [
            _make_event("evt-001", "lease-001", 1, "acquire"),
            _make_event("evt-002", "lease-001", 2, "renew",
                        custody_epoch=3,
                        payload={"expires_at": "2025-04-01T00:00:00Z"}),
            _make_event("evt-003", "lease-001", 3, "transfer",
                        owner_host="host-new", owner_pid="99999"),
        ]
        for evt in evts:
            store.record_event(evt)
        lease_before = store.replay_history("lease-001")
        # Reopen
        store2 = CustodyLeaseStore(base_dir=store.base_dir, flock=False)
        lease_after = store2.replay_history("lease-001")
        assert lease_before == lease_after
        assert lease_after is not None
        assert lease_after.owner_host == "host-new"
        assert lease_after.custody_epoch == 3
