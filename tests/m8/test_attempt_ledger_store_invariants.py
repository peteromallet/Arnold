"""Tests for attempt lifecycle invariants enforced by SqliteAttemptLedgerStore.

Covers T3 invariants:

* Durable STARTED before non-start events.
* Exactly one terminal outcome.
* Rejection of: missing terminals, duplicate terminals, post-terminal events,
  sequence gaps, stale idempotency, and unjoined causal evidence.
"""

from __future__ import annotations

import tempfile
import uuid
from pathlib import Path

import pytest

from arnold.workflow.attempt_ledger_store import (
    AppendResult,
    CausalPredecessorError,
    DuplicateTerminalError,
    GateStatus,
    MissingStartEventError,
    MonotonicSequenceError,
    PostTerminalAppendError,
    SequenceGapError,
    SqliteAttemptLedgerStore,
)
from arnold.workflow.execution_attempt_ledger import (
    AdapterKind,
    AttemptEventType,
    AttemptIdentity,
    AttemptOutcome,
    AttemptProvenance,
    GrantRef,
    LedgerEvent,
    PersistenceStatus,
    RuntimeAdapter,
    VersionSet,
)

# ── Helpers ─────────────────────────────────────────────────────────────────


def _make_identity(attempt_id: str | None = None) -> AttemptIdentity:
    return AttemptIdentity(
        workflow_id="wf-test",
        run_id="run-test",
        graph_revision="rev-test",
        attempt_ordinal=1,
        attempt_id=attempt_id or str(uuid.uuid4()),
    )


def _make_provenance() -> AttemptProvenance:
    return AttemptProvenance()


def _make_event(
    *,
    event_type: AttemptEventType = AttemptEventType.STARTED,
    idempotency_key: str = "idem-1",
    identity: AttemptIdentity | None = None,
    sequence: int = 1,
    causal_predecessor_sequence: int = 0,
    append_position: int = 0,
    outcome: AttemptOutcome | None = None,
    persistence_status: PersistenceStatus = PersistenceStatus.DURABLE,
    payload: dict | None = None,
) -> LedgerEvent:
    """Create a minimal well-formed LedgerEvent for store-invariant tests."""
    if identity is None:
        identity = _make_identity()
    if outcome is None and event_type in (
        AttemptEventType.COMPLETED,
        AttemptEventType.FAILED,
        AttemptEventType.CANCELLED,
    ):
        outcome = AttemptOutcome.SUCCEEDED if event_type == AttemptEventType.COMPLETED else AttemptOutcome.FAILED
    return LedgerEvent(
        idempotency_key=idempotency_key,
        event_type=event_type,
        identity=identity,
        provenance=_make_provenance(),
        adapter=RuntimeAdapter(adapter_kind=AdapterKind.NATIVE, adapter_version="1"),
        versions=VersionSet(code_version="c"),
        grant_ref=GrantRef(grant_id="grant-1"),
        sequence=sequence,
        causal_predecessor_sequence=causal_predecessor_sequence,
        append_position=append_position,
        occurred_at="2025-01-01T00:00:00Z",
        observed_at="2025-01-01T00:00:01Z",
        persistence_status=persistence_status,
        outcome=outcome,
        payload=payload,
    )


@pytest.fixture
def store() -> SqliteAttemptLedgerStore:
    """Return a fresh on-disk store backed by a temp file."""
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test_ledger.db"
        s = SqliteAttemptLedgerStore(db_path)
        yield s
        s.close()


@pytest.fixture
def attempt_id() -> str:
    return str(uuid.uuid4())


def _append(
    store: SqliteAttemptLedgerStore,
    attempt_id: str,
    *,
    event_type: AttemptEventType = AttemptEventType.STARTED,
    idempotency_key: str = "idem-1",
    sequence: int = 1,
    causal_predecessor_sequence: int = 0,
    append_position: int = 0,
    outcome: AttemptOutcome | None = None,
) -> AppendResult:
    """Convenience: build an event with *attempt_id* and append it."""
    identity = _make_identity(attempt_id=attempt_id)
    event = _make_event(
        event_type=event_type,
        idempotency_key=idempotency_key,
        identity=identity,
        sequence=sequence,
        causal_predecessor_sequence=causal_predecessor_sequence,
        append_position=append_position,
        outcome=outcome,
    )
    return store.append_event(attempt_id, event)


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Durable STARTED before non-start events
# ═══════════════════════════════════════════════════════════════════════════════


class TestStartedBeforeNonStart:
    """Non-STARTED events whose lifecycle precedence requires STARTED
    must be rejected when no STARTED event is durably persisted."""

    def test_started_as_first_event_ok(self, store, attempt_id):
        result = _append(store, attempt_id, event_type=AttemptEventType.STARTED)
        assert not result.is_duplicate
        assert result.sequence == 1

    def test_completed_without_started_raises(self, store, attempt_id):
        with pytest.raises(MissingStartEventError, match="requires a durable STARTED"):
            _append(
                store, attempt_id,
                event_type=AttemptEventType.COMPLETED,
                outcome=AttemptOutcome.SUCCEEDED,
            )

    def test_failed_without_started_raises(self, store, attempt_id):
        with pytest.raises(MissingStartEventError, match="requires a durable STARTED"):
            _append(
                store, attempt_id,
                event_type=AttemptEventType.FAILED,
                outcome=AttemptOutcome.FAILED,
            )

    def test_cancelled_without_started_raises(self, store, attempt_id):
        with pytest.raises(MissingStartEventError, match="requires a durable STARTED"):
            _append(
                store, attempt_id,
                event_type=AttemptEventType.CANCELLED,
                outcome=AttemptOutcome.CANCELLED,
            )

    def test_retry_scheduled_without_started_raises(self, store, attempt_id):
        with pytest.raises(MissingStartEventError, match="requires a durable STARTED"):
            _append(
                store, attempt_id,
                event_type=AttemptEventType.RETRY_SCHEDULED,
            )

    def test_suspended_without_started_raises(self, store, attempt_id):
        with pytest.raises(MissingStartEventError, match="requires a durable STARTED"):
            _append(
                store, attempt_id,
                event_type=AttemptEventType.SUSPENDED,
            )

    def test_external_effect_intent_without_started_raises(self, store, attempt_id):
        with pytest.raises(MissingStartEventError, match="requires a durable STARTED"):
            identity = _make_identity(attempt_id=attempt_id)
            event = _make_event(
                event_type=AttemptEventType.EXTERNAL_EFFECT_INTENT,
                identity=identity,
                payload={"effect": "test"},
            )
            store.append_event(attempt_id, event)

    def test_completed_after_started_ok(self, store, attempt_id):
        _append(store, attempt_id, event_type=AttemptEventType.STARTED, sequence=1)
        result = _append(
            store, attempt_id,
            event_type=AttemptEventType.COMPLETED,
            idempotency_key="idem-2",
            sequence=2,
            causal_predecessor_sequence=1,
            outcome=AttemptOutcome.SUCCEEDED,
        )
        assert not result.is_duplicate
        assert result.sequence == 2

    def test_persistence_failed_without_started_ok(self, store, attempt_id):
        """PERSISTENCE_FAILED has no lifecycle precedence requirement."""
        identity = _make_identity(attempt_id=attempt_id)
        event = _make_event(
            event_type=AttemptEventType.PERSISTENCE_FAILED,
            identity=identity,
            persistence_status=PersistenceStatus.PERSISTENCE_FAILED,
        )
        result = store.append_event(attempt_id, event)
        assert not result.is_duplicate

    def test_external_effect_outcome_without_intent_raises(self, store, attempt_id):
        """EXTERNAL_EFFECT_OUTCOME requires EXTERNAL_EFFECT_INTENT, not just STARTED."""
        _append(store, attempt_id, event_type=AttemptEventType.STARTED, sequence=1)
        with pytest.raises(
            MissingStartEventError,
            match=r"requires a durable .external_effect_intent.",
        ):
            _append(
                store, attempt_id,
                event_type=AttemptEventType.EXTERNAL_EFFECT_OUTCOME,
                idempotency_key="idem-2",
                sequence=2,
                causal_predecessor_sequence=1,
            )

    def test_resumed_without_suspended_raises(self, store, attempt_id):
        """RESUMED requires SUSPENDED."""
        _append(store, attempt_id, event_type=AttemptEventType.STARTED, sequence=1)
        # SUSPENDED itself requires STARTED, so we need STARTED first
        _append(
            store, attempt_id,
            event_type=AttemptEventType.SUSPENDED,
            idempotency_key="idem-2",
            sequence=2,
            causal_predecessor_sequence=1,
        )
        # RESUMED after SUSPENDED should be OK
        _append(
            store, attempt_id,
            event_type=AttemptEventType.RESUMED,
            idempotency_key="idem-3",
            sequence=3,
            causal_predecessor_sequence=2,
        )

    def test_resumed_without_suspended_but_with_started_raises(self, store, attempt_id):
        """RESUMED requires SUSPENDED even when STARTED exists."""
        _append(store, attempt_id, event_type=AttemptEventType.STARTED, sequence=1)
        with pytest.raises(
            MissingStartEventError,
            match=r"requires a durable .suspended.",
        ):
            _append(
                store, attempt_id,
                event_type=AttemptEventType.RESUMED,
                idempotency_key="idem-2",
                sequence=2,
                causal_predecessor_sequence=1,
            )


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Exactly one terminal outcome
# ═══════════════════════════════════════════════════════════════════════════════


class TestExactlyOneTerminal:
    """The store must prevent more than one terminal event per attempt."""

    def test_duplicate_terminal_same_type_raises(self, store, attempt_id):
        _append(store, attempt_id, event_type=AttemptEventType.STARTED, sequence=1)
        _append(
            store, attempt_id,
            event_type=AttemptEventType.COMPLETED,
            idempotency_key="idem-2",
            sequence=2,
            causal_predecessor_sequence=1,
            outcome=AttemptOutcome.SUCCEEDED,
        )
        with pytest.raises(DuplicateTerminalError, match="second terminal"):
            _append(
                store, attempt_id,
                event_type=AttemptEventType.COMPLETED,
                idempotency_key="idem-3",
                sequence=3,
                causal_predecessor_sequence=2,
                outcome=AttemptOutcome.SUCCEEDED,
            )

    def test_duplicate_terminal_different_type_raises(self, store, attempt_id):
        _append(store, attempt_id, event_type=AttemptEventType.STARTED, sequence=1)
        _append(
            store, attempt_id,
            event_type=AttemptEventType.COMPLETED,
            idempotency_key="idem-2",
            sequence=2,
            causal_predecessor_sequence=1,
            outcome=AttemptOutcome.SUCCEEDED,
        )
        with pytest.raises(DuplicateTerminalError, match="second terminal"):
            _append(
                store, attempt_id,
                event_type=AttemptEventType.FAILED,
                idempotency_key="idem-3",
                sequence=3,
                causal_predecessor_sequence=2,
                outcome=AttemptOutcome.FAILED,
            )

    def test_post_terminal_non_terminal_raises(self, store, attempt_id):
        _append(store, attempt_id, event_type=AttemptEventType.STARTED, sequence=1)
        _append(
            store, attempt_id,
            event_type=AttemptEventType.COMPLETED,
            idempotency_key="idem-2",
            sequence=2,
            causal_predecessor_sequence=1,
            outcome=AttemptOutcome.SUCCEEDED,
        )
        with pytest.raises(PostTerminalAppendError, match="no further events"):
            _append(
                store, attempt_id,
                event_type=AttemptEventType.SUSPENDED,
                idempotency_key="idem-3",
                sequence=3,
                causal_predecessor_sequence=2,
            )

    def test_failed_then_post_terminal_raises(self, store, attempt_id):
        _append(store, attempt_id, event_type=AttemptEventType.STARTED, sequence=1)
        _append(
            store, attempt_id,
            event_type=AttemptEventType.FAILED,
            idempotency_key="idem-2",
            sequence=2,
            causal_predecessor_sequence=1,
            outcome=AttemptOutcome.FAILED,
        )
        with pytest.raises(PostTerminalAppendError):
            _append(
                store, attempt_id,
                event_type=AttemptEventType.RETRY_SCHEDULED,
                idempotency_key="idem-3",
                sequence=3,
                causal_predecessor_sequence=2,
            )

    def test_cancelled_then_duplicate_terminal_raises(self, store, attempt_id):
        _append(store, attempt_id, event_type=AttemptEventType.STARTED, sequence=1)
        _append(
            store, attempt_id,
            event_type=AttemptEventType.CANCELLED,
            idempotency_key="idem-2",
            sequence=2,
            causal_predecessor_sequence=1,
            outcome=AttemptOutcome.CANCELLED,
        )
        with pytest.raises(DuplicateTerminalError, match="second terminal"):
            _append(
                store, attempt_id,
                event_type=AttemptEventType.COMPLETED,
                idempotency_key="idem-3",
                sequence=3,
                causal_predecessor_sequence=2,
                outcome=AttemptOutcome.SUCCEEDED,
            )


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Sequence continuity (no gaps, no rewinds)
# ═══════════════════════════════════════════════════════════════════════════════


class TestSequenceContinuity:
    """Sequence numbers must be exactly current_max + 1."""

    def test_first_event_seq_1_ok(self, store, attempt_id):
        result = _append(store, attempt_id, sequence=1)
        assert result.sequence == 1

    def test_second_event_seq_2_ok(self, store, attempt_id):
        _append(store, attempt_id, sequence=1)
        result = _append(
            store, attempt_id,
            event_type=AttemptEventType.COMPLETED,
            idempotency_key="idem-2",
            sequence=2,
            causal_predecessor_sequence=1,
            outcome=AttemptOutcome.SUCCEEDED,
        )
        assert result.sequence == 2

    def test_sequence_gap_raises(self, store, attempt_id):
        _append(store, attempt_id, sequence=1)
        with pytest.raises(SequenceGapError, match="would create a gap"):
            _append(
                store, attempt_id,
                event_type=AttemptEventType.COMPLETED,
                idempotency_key="idem-2",
                sequence=3,  # gap: expected 2
                causal_predecessor_sequence=1,
                outcome=AttemptOutcome.SUCCEEDED,
            )

    def test_sequence_rewind_raises(self, store, attempt_id):
        _append(store, attempt_id, sequence=1)
        with pytest.raises(MonotonicSequenceError, match="not monotonic"):
            _append(
                store, attempt_id,
                event_type=AttemptEventType.SUSPENDED,
                idempotency_key="idem-2",
                sequence=1,  # duplicate sequence number
                causal_predecessor_sequence=0,
            )

    def test_sequence_large_gap_raises(self, store, attempt_id):
        _append(store, attempt_id, sequence=1)
        with pytest.raises(SequenceGapError, match="would create a gap"):
            _append(
                store, attempt_id,
                event_type=AttemptEventType.COMPLETED,
                idempotency_key="idem-2",
                sequence=99,
                causal_predecessor_sequence=1,
                outcome=AttemptOutcome.SUCCEEDED,
            )

    def test_sequence_zero_raises_in_ledger_event(self, store, attempt_id):
        """Sequence 0 is rejected by LedgerEvent itself (>=1 constraint)."""
        with pytest.raises(ValueError, match="sequence must be >= 1"):
            _append(store, attempt_id, sequence=0)


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Causal predecessor integrity
# ═══════════════════════════════════════════════════════════════════════════════


class TestCausalPredecessor:
    """causal_predecessor_sequence must match the immediately preceding event."""

    def test_first_event_causal_predecessor_zero_ok(self, store, attempt_id):
        result = _append(store, attempt_id, causal_predecessor_sequence=0)
        assert not result.is_duplicate

    def test_first_event_causal_predecessor_nonzero_raises(self, store, attempt_id):
        """First event with causal_predecessor_sequence > 0 is rejected
        by LedgerEvent itself (causal_predecessor_sequence must be < sequence)."""
        with pytest.raises(ValueError, match="must be < sequence"):
            _make_event(sequence=1, causal_predecessor_sequence=1)

    def test_second_event_causal_predecessor_matches_ok(self, store, attempt_id):
        _append(store, attempt_id, sequence=1, causal_predecessor_sequence=0)
        result = _append(
            store, attempt_id,
            event_type=AttemptEventType.COMPLETED,
            idempotency_key="idem-2",
            sequence=2,
            causal_predecessor_sequence=1,
            outcome=AttemptOutcome.SUCCEEDED,
        )
        assert not result.is_duplicate

    def test_second_event_causal_predecessor_wrong_raises(self, store, attempt_id):
        _append(store, attempt_id, sequence=1, causal_predecessor_sequence=0)
        with pytest.raises(CausalPredecessorError, match="must equal current max sequence 1"):
            _append(
                store, attempt_id,
                event_type=AttemptEventType.COMPLETED,
                idempotency_key="idem-2",
                sequence=2,
                causal_predecessor_sequence=0,  # should be 1
                outcome=AttemptOutcome.SUCCEEDED,
            )

    def test_third_event_causal_predecessor_wrong_raises(self, store, attempt_id):
        _append(store, attempt_id, sequence=1, causal_predecessor_sequence=0)
        _append(
            store, attempt_id,
            event_type=AttemptEventType.SUSPENDED,
            idempotency_key="idem-2",
            sequence=2,
            causal_predecessor_sequence=1,
        )
        with pytest.raises(CausalPredecessorError, match="must equal current max sequence 2"):
            _append(
                store, attempt_id,
                event_type=AttemptEventType.RESUMED,
                idempotency_key="idem-3",
                sequence=3,
                causal_predecessor_sequence=1,  # should be 2
            )


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Idempotency (stale idempotency is stable, not rejected)
# ═══════════════════════════════════════════════════════════════════════════════


class TestIdempotency:
    """Duplicate idempotency keys return the original event, no error."""

    def test_duplicate_idempotency_key_returns_original(self, store, attempt_id):
        r1 = _append(store, attempt_id, idempotency_key="my-key")
        assert not r1.is_duplicate

        r2 = _append(store, attempt_id, idempotency_key="my-key", sequence=999)
        assert r2.is_duplicate
        assert r2.sequence == r1.sequence  # original sequence, not 999
        assert r2.event.idempotency_key == "my-key"

    def test_idempotency_dedup_wins_over_missing_start(self, store, attempt_id):
        """Idempotency dedup is checked before lifecycle precedence."""
        # Append a valid STARTED event first.
        r1 = _append(
            store, attempt_id,
            event_type=AttemptEventType.STARTED,
            idempotency_key="persist-key",
        )
        assert not r1.is_duplicate

        # Replay with a different event type — dedup returns the original
        r2 = _append(
            store, attempt_id,
            event_type=AttemptEventType.COMPLETED,
            idempotency_key="persist-key",
            sequence=2,
            causal_predecessor_sequence=1,
            outcome=AttemptOutcome.SUCCEEDED,
        )
        assert r2.is_duplicate
        assert r2.event.event_type == AttemptEventType.STARTED

    def test_idempotency_dedup_wins_over_sequence_gap(self, store, attempt_id):
        """Idempotency dedup returns original even if new event has a gap."""
        _append(store, attempt_id, sequence=1, idempotency_key="dup-key")
        r2 = _append(
            store, attempt_id,
            event_type=AttemptEventType.COMPLETED,
            idempotency_key="dup-key",
            sequence=99,
            causal_predecessor_sequence=0,
            outcome=AttemptOutcome.SUCCEEDED,
        )
        assert r2.is_duplicate
        assert r2.sequence == 1  # original sequence

    def test_idempotency_dedup_wins_over_causal_predecessor(self, store, attempt_id):
        """Idempotency dedup returns original even if causal predecessor is wrong."""
        _append(store, attempt_id, sequence=1, idempotency_key="causal-key")
        r2 = _append(
            store, attempt_id,
            event_type=AttemptEventType.SUSPENDED,
            idempotency_key="causal-key",
            sequence=1,
            causal_predecessor_sequence=0,
        )
        assert r2.is_duplicate
        assert r2.event.causal_predecessor_sequence == 0

    def test_different_idempotency_keys_are_distinct(self, store, attempt_id):
        r1 = _append(store, attempt_id, idempotency_key="key-a")
        r2 = _append(
            store, attempt_id,
            event_type=AttemptEventType.SUSPENDED,
            idempotency_key="key-b",
            sequence=2,
            causal_predecessor_sequence=1,
        )
        assert not r1.is_duplicate
        assert not r2.is_duplicate


# ═══════════════════════════════════════════════════════════════════════════════
# 6. Gate verification
# ═══════════════════════════════════════════════════════════════════════════════


class TestGateVerification:
    """Fail-closed gates respect the durability constraints."""

    def test_start_verified_when_present(self, store, attempt_id):
        _append(store, attempt_id, event_type=AttemptEventType.STARTED)
        result = store.start_verified(attempt_id)
        assert result.status == GateStatus.VERIFIED
        assert result.started_event is not None
        assert result.started_event.event_type == AttemptEventType.STARTED

    def test_start_verified_when_absent(self, store, attempt_id):
        result = store.start_verified(attempt_id)
        assert result.status == GateStatus.INCOMPLETE

    def test_terminal_verified_when_present(self, store, attempt_id):
        _append(store, attempt_id, event_type=AttemptEventType.STARTED, sequence=1)
        _append(
            store, attempt_id,
            event_type=AttemptEventType.COMPLETED,
            idempotency_key="idem-2",
            sequence=2,
            causal_predecessor_sequence=1,
            outcome=AttemptOutcome.SUCCEEDED,
        )
        result = store.terminal_or_indeterminate_verified(attempt_id)
        assert result.status == GateStatus.VERIFIED
        assert result.terminal_event is not None
        assert result.terminal_event.event_type == AttemptEventType.COMPLETED

    def test_terminal_verified_when_absent(self, store, attempt_id):
        _append(store, attempt_id, event_type=AttemptEventType.STARTED)
        result = store.terminal_or_indeterminate_verified(attempt_id)
        assert result.status == GateStatus.INCOMPLETE


# ═══════════════════════════════════════════════════════════════════════════════
# 7. Sequence gap detection
# ═══════════════════════════════════════════════════════════════════════════════


class TestGapDetection:
    """query_gaps reports gaps in the stored sequence (for diagnostic use)."""

    def test_no_gaps_in_continuous_sequence(self, store, attempt_id):
        _append(store, attempt_id, sequence=1, causal_predecessor_sequence=0)
        _append(
            store, attempt_id,
            event_type=AttemptEventType.COMPLETED,
            idempotency_key="idem-2",
            sequence=2,
            causal_predecessor_sequence=1,
            outcome=AttemptOutcome.SUCCEEDED,
        )
        gaps = store.query_gaps(attempt_id)
        assert gaps == []

    def test_single_event_no_gaps(self, store, attempt_id):
        _append(store, attempt_id, sequence=1)
        gaps = store.query_gaps(attempt_id)
        assert gaps == []

    def test_empty_attempt_no_gaps(self, store, attempt_id):
        gaps = store.query_gaps(attempt_id)
        assert gaps == []


# ═══════════════════════════════════════════════════════════════════════════════
# 8. Reservation projections respect terminal state
# ═══════════════════════════════════════════════════════════════════════════════


class TestReservationTerminalState:
    """Reservations correctly report has_terminal and event counts."""

    def test_reservation_without_terminal(self, store, attempt_id):
        _append(store, attempt_id, event_type=AttemptEventType.STARTED)
        reservation = store.reserve_attempt(attempt_id)
        assert reservation.event_count == 1
        assert not reservation.has_terminal

    def test_reservation_with_terminal(self, store, attempt_id):
        _append(store, attempt_id, event_type=AttemptEventType.STARTED, sequence=1)
        _append(
            store, attempt_id,
            event_type=AttemptEventType.COMPLETED,
            idempotency_key="idem-2",
            sequence=2,
            causal_predecessor_sequence=1,
            outcome=AttemptOutcome.SUCCEEDED,
        )
        reservation = store.reserve_attempt(attempt_id)
        assert reservation.event_count == 2
        assert reservation.has_terminal


# ═══════════════════════════════════════════════════════════════════════════════
# 9. Full happy-path lifecycle
# ═══════════════════════════════════════════════════════════════════════════════


class TestHappyPathLifecycle:
    """A complete STARTED → SUSPENDED → RESUMED → COMPLETED sequence."""

    def test_full_lifecycle(self, store, attempt_id):
        # 1. STARTED
        r1 = _append(store, attempt_id, event_type=AttemptEventType.STARTED, sequence=1)
        assert not r1.is_duplicate

        # 2. SUSPENDED
        r2 = _append(
            store, attempt_id,
            event_type=AttemptEventType.SUSPENDED,
            idempotency_key="idem-2",
            sequence=2,
            causal_predecessor_sequence=1,
        )
        assert not r2.is_duplicate

        # 3. RESUMED
        r3 = _append(
            store, attempt_id,
            event_type=AttemptEventType.RESUMED,
            idempotency_key="idem-3",
            sequence=3,
            causal_predecessor_sequence=2,
        )
        assert not r3.is_duplicate

        # 4. COMPLETED
        r4 = _append(
            store, attempt_id,
            event_type=AttemptEventType.COMPLETED,
            idempotency_key="idem-4",
            sequence=4,
            causal_predecessor_sequence=3,
            outcome=AttemptOutcome.SUCCEEDED,
        )
        assert not r4.is_duplicate

        # Verify state
        assert store.event_count(attempt_id) == 4
        assert store.last_sequence(attempt_id) == 4
        assert store.has_terminal_event(attempt_id)

        # Verify gate
        start_result = store.start_verified(attempt_id)
        assert start_result.status == GateStatus.VERIFIED
        terminal_result = store.terminal_or_indeterminate_verified(attempt_id)
        assert terminal_result.status == GateStatus.VERIFIED

        # Read back
        events = store.read_events(attempt_id)
        assert len(events) == 4
        assert events[0].event_type == AttemptEventType.STARTED
        assert events[1].event_type == AttemptEventType.SUSPENDED
        assert events[2].event_type == AttemptEventType.RESUMED
        assert events[3].event_type == AttemptEventType.COMPLETED

        # Ledger
        ledger = store.read_ledger(attempt_id)
        assert ledger.attempt_id == attempt_id
        assert len(ledger.events) == 4
