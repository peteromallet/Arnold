"""Tests for ``LedgerStoreAdapter`` — process-safe store wrapper.

Coverage:
* Retry/backoff for transient SQLite locks
* Bounded retries (MaxRetriesExceededError after budget exhausted)
* Required-write persistence failures are never caught or suppressed
* SIGTERM/SIGINT safe close
* Crash-reopen consistency checks
* Context manager support
* Delegation correctness (operations pass through to underlying store)
"""

from __future__ import annotations

import multiprocessing
import os
import signal
import sqlite3
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

import pytest

from arnold.adapters.ledger_store_adapter import (
    AdapterClosedError,
    CrashReopenIntegrityError,
    LedgerStoreAdapter,
    MaxRetriesExceededError,
    _is_transient_lock_error,
)
from arnold.workflow.attempt_ledger_store import (
    AppendResult,
    AttemptReservation,
    GateStatus,
    MonotonicSequenceError,
    PostTerminalAppendError,
    SqliteAttemptLedgerStore,
    StartGateResult,
    TerminalGateResult,
)
from arnold.workflow.execution_attempt_ledger import (
    LEDGER_SCHEMA_VERSION,
    AdapterKind,
    AttemptEventType,
    AttemptIdentity,
    AttemptOutcome,
    AttemptProvenance,
    ExecutionAttemptLedger,
    GrantRef,
    LedgerEvent,
    PersistenceStatus,
    RuntimeAdapter,
    VersionSet,
)

# ── Helpers ────────────────────────────────────────────────────────────────


def _aid() -> str:
    """Generate a fresh UUID for attempt_id."""
    return str(uuid.uuid4())


def _make_identity(
    workflow_id: str = "wf-1",
    run_id: str = "run-1",
    attempt_id: str | None = None,
) -> AttemptIdentity:
    return AttemptIdentity(
        workflow_id=workflow_id,
        run_id=run_id,
        graph_revision="rev-1",
        attempt_ordinal=1,
        attempt_id=attempt_id if attempt_id is not None else _aid(),
    )


def _make_provenance() -> AttemptProvenance:
    return AttemptProvenance(
        parent_attempt_id=None,
        causal_lineage=(),
        actor_id=None,
        tool_id=None,
    )


def _make_event(
    attempt_id: str | None = None,
    sequence: int = 1,
    event_type: AttemptEventType = AttemptEventType.STARTED,
    idempotency_key: str = "idem-1",
    causal_predecessor_sequence: int = 0,
    append_position: int = 0,
    outcome: AttemptOutcome | None = None,
) -> LedgerEvent:
    aid = attempt_id if attempt_id is not None else _aid()
    cps = causal_predecessor_sequence
    return LedgerEvent(
        idempotency_key=idempotency_key,
        event_type=event_type,
        identity=_make_identity(attempt_id=aid),
        provenance=_make_provenance(),
        adapter=RuntimeAdapter(
            adapter_kind=AdapterKind.NATIVE, adapter_version="1"
        ),
        versions=VersionSet(code_version="c1"),
        grant_ref=GrantRef(grant_id="g1"),
        sequence=sequence,
        causal_predecessor_sequence=cps,
        append_position=append_position,
        occurred_at="2025-01-01T00:00:00Z",
        observed_at="2025-01-01T00:00:01Z",
        outcome=outcome,
    )


def _temp_db_path() -> Path:
    """Return a path for a temporary SQLite database."""
    return Path(tempfile.mkdtemp()) / "test.db"


# ── Transient lock detection tests ────────────────────────────────────────


class TestTransientLockDetection:
    """Prove that ``_is_transient_lock_error`` correctly classifies errors."""

    def test_database_is_locked_is_transient(self):
        """'database is locked' OperationalError is transient."""
        exc = sqlite3.OperationalError("database is locked")
        assert _is_transient_lock_error(exc) is True

    def test_database_table_is_locked_is_transient(self):
        """'database table is locked' is transient."""
        exc = sqlite3.OperationalError("database table is locked")
        assert _is_transient_lock_error(exc) is True

    def test_sqlite_busy_in_message_is_transient(self):
        """SQLITE_BUSY substring is transient."""
        exc = sqlite3.OperationalError("SQLITE_BUSY: contention")
        assert _is_transient_lock_error(exc) is True

    def test_non_operational_error_is_not_transient(self):
        """A ValueError is not transient."""
        exc = ValueError("database is locked")  # wrong type
        assert _is_transient_lock_error(exc) is False

    def test_operational_error_without_lock_substring_is_not_transient(self):
        """An OperationalError without lock keywords is not transient."""
        exc = sqlite3.OperationalError("no such table: foo")
        assert _is_transient_lock_error(exc) is False

    def test_disk_io_error_is_not_transient(self):
        """Disk I/O errors are not transient."""
        exc = sqlite3.OperationalError("disk I/O error")
        assert _is_transient_lock_error(exc) is False

    def test_corrupt_error_is_not_transient(self):
        """Database corrupt errors are not transient."""
        exc = sqlite3.OperationalError("database disk image is malformed")
        assert _is_transient_lock_error(exc) is False


# ── Basic adapter lifecycle ───────────────────────────────────────────────


class TestAdapterLifecycle:
    """Open, close, context manager, and signal-safety basics."""

    def test_open_and_close(self):
        """Adapter opens and closes cleanly."""
        db_path = _temp_db_path()
        adapter = LedgerStoreAdapter(db_path)
        assert adapter.is_closed is True

        adapter.open()
        assert adapter.is_closed is False

        adapter.close()
        assert adapter.is_closed is True

    def test_double_open_is_idempotent(self):
        """open() called twice is safe."""
        db_path = _temp_db_path()
        adapter = LedgerStoreAdapter(db_path)
        adapter.open()
        adapter.open()  # second open — should not raise
        assert adapter.is_closed is False
        adapter.close()

    def test_double_close_is_idempotent(self):
        """close() called twice is safe."""
        db_path = _temp_db_path()
        adapter = LedgerStoreAdapter(db_path)
        adapter.open()
        adapter.close()
        adapter.close()  # second close — should not raise
        assert adapter.is_closed is True

    def test_closed_adapter_raises_on_operation(self):
        """Operations on a closed adapter raise AdapterClosedError."""
        db_path = _temp_db_path()
        adapter = LedgerStoreAdapter(db_path)
        adapter.open()
        adapter.close()

        with pytest.raises(AdapterClosedError):
            adapter.reserve_attempt("attempt-1")

        with pytest.raises(AdapterClosedError):
            adapter.read_events("attempt-1")

        with pytest.raises(AdapterClosedError):
            adapter.event_count("attempt-1")

    def test_context_manager(self):
        """Context manager opens and closes automatically."""
        db_path = _temp_db_path()
        with LedgerStoreAdapter(db_path) as adapter:
            assert adapter.is_closed is False
            reservation = adapter.reserve_attempt("attempt-1")
            assert reservation.attempt_id == "attempt-1"
        assert adapter.is_closed is True

    def test_context_manager_closes_on_exception(self):
        """Context manager closes even when an exception is raised."""
        db_path = _temp_db_path()
        adapter = LedgerStoreAdapter(db_path)
        try:
            with adapter:
                raise RuntimeError("simulated error")
        except RuntimeError:
            pass
        assert adapter.is_closed is True

    def test_signal_handler_closes_adapter(self):
        """Direct invocation of signal handler closes the adapter.

        We test by directly calling the handler with a signal number
        and verifying the adapter is closed afterward.  We wrap the
        call to catch the os.kill re-raise that the real handler would
        perform.
        """
        db_path = _temp_db_path()
        adapter = LedgerStoreAdapter(db_path)
        adapter.open()
        assert adapter.is_closed is False

        # Directly invoke the signal handler logic for SIGTERM.
        # The real handler calls os.kill after close, so we catch that.
        caught_signal: list[int] = []

        # Save the original os.kill so we can intercept.
        import os as os_module
        _original_kill = os_module.kill

        def _fake_kill(pid: int, sig: int) -> None:
            caught_signal.append(sig)

        os_module.kill = _fake_kill  # type: ignore[attr-defined]

        try:
            adapter._signal_handler(signal.SIGTERM, None)
        finally:
            os_module.kill = _original_kill  # type: ignore[attr-defined]

        assert adapter.is_closed is True
        # The handler should have attempted to re-send SIGTERM.
        assert caught_signal == [signal.SIGTERM]

        # Restore signal handlers for cleanup (already done by handler,
        # but close is idempotent).
        adapter.close()


# ── Crash-reopen consistency tests ────────────────────────────────────────


class TestCrashReopenConsistency:
    """Crash-reopen integrity verification."""

    def test_open_passes_consistency_check(self):
        """A fresh database passes crash-reopen consistency."""
        db_path = _temp_db_path()
        adapter = LedgerStoreAdapter(db_path)
        adapter.open()
        # Should not raise.
        assert adapter.get_contract_version() == LEDGER_SCHEMA_VERSION
        adapter.close()

    def test_reopen_passes_consistency(self):
        """Close and reopen passes consistency check."""
        db_path = _temp_db_path()
        adapter = LedgerStoreAdapter(db_path)
        adapter.open()
        adapter.close()

        # Reopen — consistency check should pass.
        adapter2 = LedgerStoreAdapter(db_path)
        adapter2.open()
        assert adapter2.get_contract_version() == LEDGER_SCHEMA_VERSION
        adapter2.close()

    def test_corrupt_db_raises_on_open(self):
        """A corrupted database (not SQLite) raises CrashReopenIntegrityError."""
        db_path = _temp_db_path()
        # Write garbage to the database file.
        db_path.parent.mkdir(parents=True, exist_ok=True)
        db_path.write_text("this is not a valid SQLite database")

        adapter = LedgerStoreAdapter(db_path)
        with pytest.raises(CrashReopenIntegrityError):
            adapter.open()

    def test_consistency_check_after_close_and_reopen(self):
        """After an explicit close, reopening should re-verify consistency."""
        db_path = _temp_db_path()
        adapter = LedgerStoreAdapter(db_path)
        adapter.open()
        # Write some data.
        adapter.reserve_attempt("attempt-1")
        adapter.close()

        # Reopen — should succeed.
        adapter2 = LedgerStoreAdapter(db_path)
        adapter2.open()
        assert adapter2.event_count("attempt-1") == 0  # no events, just reservation
        adapter2.close()


# ── Retry/backoff tests ───────────────────────────────────────────────────


class TestRetryBounded:
    """Prove that retries are bounded and transient lock errors are retried.

    These tests exercise ``_retry_on_transient_lock`` directly with
    controlled callables rather than contending on a real database lock,
    which would otherwise be dominated by the underlying store's own
    internal ``_begin_immediate_retry`` (up to 30 attempts with
    exponential backoff).
    """

    def test_retries_bounded_by_max_retries(self):
        """After max_retries transient errors, MaxRetriesExceededError is raised.

        We provide a callable that always raises a transient lock error.
        The adapter must retry up to max_retries and then raise
        MaxRetriesExceededError.
        """
        db_path = _temp_db_path()
        adapter = LedgerStoreAdapter(
            db_path, max_retries=3, base_delay=0.01, max_delay=0.05
        )
        adapter.open()
        try:
            transient_error = sqlite3.OperationalError("database is locked")

            def _always_locked() -> int:
                raise transient_error

            with pytest.raises(MaxRetriesExceededError):
                adapter._retry_on_transient_lock(_always_locked, "test-op")
        finally:
            adapter.close()

    def test_non_transient_error_propagates_immediately(self):
        """A non-transient OperationalError propagates without retry.

        The adapter must NOT retry non-lock OperationalErrors like
        'no such table' or 'disk I/O error'.
        """
        db_path = _temp_db_path()
        adapter = LedgerStoreAdapter(
            db_path, max_retries=3, base_delay=0.01, max_delay=0.05
        )
        adapter.open()
        try:
            call_count = [0]
            non_transient = sqlite3.OperationalError("no such table: foo")

            def _raise_non_transient() -> int:
                call_count[0] += 1
                raise non_transient

            with pytest.raises(sqlite3.OperationalError) as exc_info:
                adapter._retry_on_transient_lock(
                    _raise_non_transient, "test-op"
                )
            # The error should be the original, NOT a MaxRetriesExceededError.
            assert "no such table" in str(exc_info.value)
            # Only called once — no retry.
            assert call_count[0] == 1
        finally:
            adapter.close()

    def test_eventual_success_after_transient_errors(self):
        """When transient errors resolve, the operation succeeds.

        The callable raises transient errors for the first N calls, then
        returns a successful result.  The adapter must retry and
        eventually return the result.
        """
        db_path = _temp_db_path()
        adapter = LedgerStoreAdapter(
            db_path, max_retries=5, base_delay=0.01, max_delay=0.05
        )
        adapter.open()
        try:
            call_count = [0]

            def _fail_twice_then_succeed() -> str:
                call_count[0] += 1
                if call_count[0] <= 2:
                    raise sqlite3.OperationalError("database is locked")
                return "success"

            result = adapter._retry_on_transient_lock(
                _fail_twice_then_succeed, "test-op"
            )
            assert result == "success"
            assert call_count[0] == 3  # 2 failures + 1 success
        finally:
            adapter.close()

    def test_retry_count_exactly_max_retries_plus_one(self):
        """With max_retries=N, the callable is invoked at most N+1 times."""
        db_path = _temp_db_path()
        adapter = LedgerStoreAdapter(
            db_path, max_retries=2, base_delay=0.01, max_delay=0.03
        )
        adapter.open()
        try:
            call_count = [0]
            transient_error = sqlite3.OperationalError("database is locked")

            def _always_locked() -> int:
                call_count[0] += 1
                raise transient_error

            with pytest.raises(MaxRetriesExceededError):
                adapter._retry_on_transient_lock(_always_locked, "test-op")

            # max_retries=2 => 3 total attempts (initial + 2 retries).
            assert call_count[0] == 3
        finally:
            adapter.close()

    def test_zero_max_retries_no_retry(self):
        """With max_retries=0, the first transient error propagates as
        MaxRetriesExceededError with no retry."""
        db_path = _temp_db_path()
        adapter = LedgerStoreAdapter(
            db_path, max_retries=0, base_delay=0.01, max_delay=0.05
        )
        adapter.open()
        try:
            call_count = [0]
            transient_error = sqlite3.OperationalError("database is locked")

            def _always_locked() -> int:
                call_count[0] += 1
                raise transient_error

            with pytest.raises(MaxRetriesExceededError):
                adapter._retry_on_transient_lock(_always_locked, "test-op")

            assert call_count[0] == 1  # only initial attempt, no retries
        finally:
            adapter.close()


# ── Non-suppression of required-write failures ────────────────────────────


class TestRequiredWriteFailuresNotSuppressed:
    """Prove that persistence failures are never caught or suppressed."""

    def test_post_terminal_append_error_propagates(self):
        """PostTerminalAppendError is propagated immediately, never retried."""
        db_path = _temp_db_path()
        adapter = LedgerStoreAdapter(db_path, max_retries=5)
        adapter.open()
        try:
            aid = _aid()
            adapter.reserve_attempt(aid)

            # Append a terminal event.
            term_event = _make_event(
                attempt_id=aid, sequence=1,
                event_type=AttemptEventType.COMPLETED,
                idempotency_key="terminal-1",
                outcome=AttemptOutcome.SUCCEEDED,
            )
            adapter.append_completed(aid, term_event)

            # Now try to append a non-terminal event after terminal.
            post_event = _make_event(
                attempt_id=aid, sequence=2,
                event_type=AttemptEventType.STARTED,
                idempotency_key="post-terminal-1",
            )
            with pytest.raises(PostTerminalAppendError):
                adapter.append_started(aid, post_event)
        finally:
            adapter.close()

    def test_monotonic_sequence_error_propagates(self):
        """MonotonicSequenceError is propagated immediately, never retried."""
        db_path = _temp_db_path()
        adapter = LedgerStoreAdapter(db_path, max_retries=5)
        adapter.open()
        try:
            aid = _aid()
            adapter.reserve_attempt(aid)

            # Append event at sequence 1.
            ev1 = _make_event(
                attempt_id=aid, sequence=1,
                event_type=AttemptEventType.STARTED,
                idempotency_key="ev-1",
            )
            adapter.append_started(aid, ev1)

            # Try to append another event at sequence 1 (not > 1).
            ev2 = _make_event(
                attempt_id=aid, sequence=1,  # same sequence — monotonic violation
                event_type=AttemptEventType.STARTED,
                idempotency_key="ev-2",
            )
            with pytest.raises(MonotonicSequenceError):
                adapter.append_started(aid, ev2)
        finally:
            adapter.close()

    def test_value_error_propagates(self):
        """ValueError (attempt_id mismatch) propagates immediately."""
        db_path = _temp_db_path()
        adapter = LedgerStoreAdapter(db_path, max_retries=5)
        adapter.open()
        try:
            event = _make_event(
                attempt_id=_aid(), sequence=1,
                event_type=AttemptEventType.STARTED,
                idempotency_key="ev-1",
            )
            # Use a different but valid UUID as the store attempt_id.
            with pytest.raises(ValueError):
                adapter.append_started(_aid(), event)
        finally:
            adapter.close()

    def test_event_type_validation_error_propagates(self):
        """Appending STARTED via append_completed raises ValueError immediately."""
        db_path = _temp_db_path()
        adapter = LedgerStoreAdapter(db_path, max_retries=5)
        adapter.open()
        try:
            aid = _aid()
            adapter.reserve_attempt(aid)
            event = _make_event(
                attempt_id=aid, sequence=1,
                event_type=AttemptEventType.STARTED,
                idempotency_key="ev-1",
            )
            with pytest.raises(ValueError):
                adapter.append_completed(aid, event)
        finally:
            adapter.close()

    def test_append_success_returns_correct_result(self):
        """A successful append returns AppendResult, not swallowed."""
        db_path = _temp_db_path()
        adapter = LedgerStoreAdapter(db_path, max_retries=5)
        adapter.open()
        try:
            aid = _aid()
            adapter.reserve_attempt(aid)
            event = _make_event(
                attempt_id=aid, sequence=1,
                event_type=AttemptEventType.STARTED,
                idempotency_key="ev-1",
            )
            result = adapter.append_started(aid, event)
            assert isinstance(result, AppendResult)
            assert result.attempt_id == aid
            assert result.sequence == 1
            assert result.is_duplicate is False
            assert result.event.event_type == AttemptEventType.STARTED
        finally:
            adapter.close()


# ── Delegation correctness tests ──────────────────────────────────────────


class TestDelegationCorrectness:
    """Verify operations pass through correctly to the underlying store."""

    def test_reserve_attempt_delegates(self):
        """reserve_attempt returns an AttemptReservation."""
        db_path = _temp_db_path()
        with LedgerStoreAdapter(db_path) as adapter:
            result = adapter.reserve_attempt("attempt-1")
            assert isinstance(result, AttemptReservation)
            assert result.attempt_id == "attempt-1"
            assert result.is_new is True
            assert result.event_count == 0
            assert result.last_sequence == 0
            assert result.has_terminal is False

    def test_append_event_delegates(self):
        """append_event returns correct AppendResult."""
        db_path = _temp_db_path()
        with LedgerStoreAdapter(db_path) as adapter:
            aid = _aid()
            adapter.reserve_attempt(aid)
            event = _make_event(
                attempt_id=aid, sequence=1,
                event_type=AttemptEventType.STARTED,
                idempotency_key="ev-1",
            )
            result = adapter.append_event(aid, event)
            assert isinstance(result, AppendResult)
            assert result.sequence == 1
            assert result.is_duplicate is False

    def test_read_events_delegates(self):
        """read_events returns persisted events in order."""
        db_path = _temp_db_path()
        with LedgerStoreAdapter(db_path) as adapter:
            aid = _aid()
            adapter.reserve_attempt(aid)

            ev1 = _make_event(
                attempt_id=aid, sequence=1,
                event_type=AttemptEventType.STARTED,
                idempotency_key="ev-1",
            )
            adapter.append_started(aid, ev1)

            ev2 = _make_event(
                attempt_id=aid, sequence=2,
                event_type=AttemptEventType.COMPLETED,
                idempotency_key="ev-2",
                outcome=AttemptOutcome.SUCCEEDED,
            )
            adapter.append_completed(aid, ev2)

            events = adapter.read_events(aid)
            assert len(events) == 2
            assert events[0].sequence == 1
            assert events[1].sequence == 2

    def test_read_ledger_delegates(self):
        """read_ledger returns an ExecutionAttemptLedger."""
        db_path = _temp_db_path()
        with LedgerStoreAdapter(db_path) as adapter:
            aid = _aid()
            adapter.reserve_attempt(aid)
            ev = _make_event(
                attempt_id=aid, sequence=1,
                event_type=AttemptEventType.STARTED,
                idempotency_key="ev-1",
            )
            adapter.append_started(aid, ev)

            ledger = adapter.read_ledger(aid)
            assert isinstance(ledger, ExecutionAttemptLedger)
            assert ledger.attempt_id == aid
            assert len(ledger.events) == 1

    def test_event_count_delegates(self):
        """event_count returns the correct number."""
        db_path = _temp_db_path()
        with LedgerStoreAdapter(db_path) as adapter:
            aid = _aid()
            adapter.reserve_attempt(aid)
            assert adapter.event_count(aid) == 0

            ev = _make_event(
                attempt_id=aid, sequence=1,
                event_type=AttemptEventType.STARTED,
                idempotency_key="ev-1",
            )
            adapter.append_started(aid, ev)
            assert adapter.event_count(aid) == 1

    def test_has_terminal_event_delegates(self):
        """has_terminal_event works correctly."""
        db_path = _temp_db_path()
        with LedgerStoreAdapter(db_path) as adapter:
            aid = _aid()
            adapter.reserve_attempt(aid)
            assert adapter.has_terminal_event(aid) is False

            ev = _make_event(
                attempt_id=aid, sequence=1,
                event_type=AttemptEventType.COMPLETED,
                idempotency_key="ev-1",
                outcome=AttemptOutcome.SUCCEEDED,
            )
            adapter.append_completed(aid, ev)
            assert adapter.has_terminal_event(aid) is True

    def test_last_sequence_delegates(self):
        """last_sequence returns correct value."""
        db_path = _temp_db_path()
        with LedgerStoreAdapter(db_path) as adapter:
            aid = _aid()
            adapter.reserve_attempt(aid)
            assert adapter.last_sequence(aid) == 0

            ev = _make_event(
                attempt_id=aid, sequence=3,
                event_type=AttemptEventType.STARTED,
                idempotency_key="ev-1",
            )
            adapter.append_started(aid, ev)
            assert adapter.last_sequence(aid) == 3

    def test_gates_delegate(self):
        """start_verified and terminal_or_indeterminate_verified work."""
        db_path = _temp_db_path()
        with LedgerStoreAdapter(db_path) as adapter:
            aid = _aid()
            adapter.reserve_attempt(aid)

            # Before STARTED: INCOMPLETE.
            sg = adapter.start_verified(aid)
            assert isinstance(sg, StartGateResult)
            assert sg.status == GateStatus.INCOMPLETE

            # Append STARTED.
            ev = _make_event(
                attempt_id=aid, sequence=1,
                event_type=AttemptEventType.STARTED,
                idempotency_key="ev-1",
            )
            adapter.append_started(aid, ev)

            # Now VERIFIED.
            sg = adapter.start_verified(aid)
            assert sg.status == GateStatus.VERIFIED
            assert sg.started_event is not None

            # Terminal: INCOMPLETE before terminal.
            tg = adapter.terminal_or_indeterminate_verified(aid)
            assert tg.status == GateStatus.INCOMPLETE

    def test_get_reservation_delegates(self):
        """get_reservation returns correct info."""
        db_path = _temp_db_path()
        with LedgerStoreAdapter(db_path) as adapter:
            # reserve_attempt first.
            adapter.reserve_attempt("attempt-1")
            res = adapter.get_reservation("attempt-1")
            assert res is not None
            assert res.attempt_id == "attempt-1"

            # Non-existent attempt returns None.
            res2 = adapter.get_reservation("nonexistent")
            assert res2 is None

    def test_get_terminal_event_delegates(self):
        """get_terminal_event returns correct event."""
        db_path = _temp_db_path()
        with LedgerStoreAdapter(db_path) as adapter:
            aid = _aid()
            adapter.reserve_attempt(aid)

            # No terminal yet.
            assert adapter.get_terminal_event(aid) is None

            ev = _make_event(
                attempt_id=aid, sequence=1,
                event_type=AttemptEventType.FAILED,
                idempotency_key="ev-1",
                outcome=AttemptOutcome.FAILED,
            )
            adapter.append_failed(aid, ev)

            term = adapter.get_terminal_event(aid)
            assert term is not None
            assert term.event_type == AttemptEventType.FAILED

    def test_metadata_introspection_delegates(self):
        """get_contract_version and get_store_version delegate."""
        db_path = _temp_db_path()
        with LedgerStoreAdapter(db_path) as adapter:
            assert adapter.get_contract_version() == LEDGER_SCHEMA_VERSION
            assert len(adapter.get_store_version()) > 0

    def test_initialize_attempt_delegates(self):
        """initialize_attempt is idempotent and safe."""
        db_path = _temp_db_path()
        with LedgerStoreAdapter(db_path) as adapter:
            adapter.initialize_attempt("attempt-1")
            adapter.initialize_attempt("attempt-1")  # idempotent
            # Should not raise.


# ── Idempotency-key dedup through adapter ─────────────────────────────────


class TestIdempotencyThroughAdapter:
    """Idempotency-key dedup works through the adapter layer."""

    def test_duplicate_idempotency_key_returns_existing(self):
        """Same idempotency key returns existing event with is_duplicate=True."""
        db_path = _temp_db_path()
        with LedgerStoreAdapter(db_path) as adapter:
            aid = _aid()
            adapter.reserve_attempt(aid)

            ev = _make_event(
                attempt_id=aid, sequence=1,
                event_type=AttemptEventType.STARTED,
                idempotency_key="my-key",
            )
            r1 = adapter.append_started(aid, ev)
            assert r1.is_duplicate is False

            # Same key — should dedup.
            ev2 = _make_event(
                attempt_id=aid, sequence=2,
                event_type=AttemptEventType.COMPLETED,
                idempotency_key="my-key",  # same key
                outcome=AttemptOutcome.SUCCEEDED,
            )
            r2 = adapter.append_event(aid, ev2)
            assert r2.is_duplicate is True
            # The returned event is the original (STARTED), not the new
            # (COMPLETED) one.
            assert r2.event.event_type == AttemptEventType.STARTED
            assert r2.sequence == 1


# ── Concurrent adapter instances (separate connections) ───────────────────


class TestConcurrentAdapterInstances:
    """Two adapter instances on the same DB file behave correctly."""

    def test_two_adapters_read_each_others_writes(self):
        """Adapter A writes, Adapter B sees it."""
        db_path = _temp_db_path()
        aid = _aid()

        adapter_a = LedgerStoreAdapter(db_path)
        adapter_a.open()
        try:
            adapter_a.reserve_attempt(aid)
            ev = _make_event(
                attempt_id=aid, sequence=1,
                event_type=AttemptEventType.STARTED,
                idempotency_key="ev-1",
            )
            adapter_a.append_started(aid, ev)
        finally:
            adapter_a.close()

        # Open second adapter on same DB.
        adapter_b = LedgerStoreAdapter(db_path)
        adapter_b.open()
        try:
            events = adapter_b.read_events(aid)
            assert len(events) == 1
            assert events[0].sequence == 1
        finally:
            adapter_b.close()
