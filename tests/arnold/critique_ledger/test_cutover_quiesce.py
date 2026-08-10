"""Tests for durable cutover quiesce and in-flight drain (CL5 Step 12b).

Coverage:

* ``list_in_flight_attempts`` enumerates only attempts without a terminal event.
* ``quiesce`` atomically engages the durable admission fence and enumerates the
  in-flight set.
* The engaged fence rejects NEW admissions (both ``reserve_attempt`` and the
  first event of a new stream) while still ALLOWING continuations of existing
  in-flight attempts (the natural terminal drain).
* ``drain`` waits for draining attempts within the timeout and marks every
  remaining attempt ``INDETERMINATE`` (fail-closed), including the
  ``PERSISTENCE_FAILED`` fail-closed category.
* The ``cutover_in_progress`` fence survives a store reopen (crash).
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

import pytest

from arnold.critique_ledger.cutover.drain_map import DrainCategory
from arnold.critique_ledger.cutover.quiesce import (
    drain,
    quiesce,
)
from arnold.workflow.attempt_ledger_store import (
    CutoverInProgressError,
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

# ── Event helpers (mirror tests/arnold/workflow/test_attempt_ledger_store.py) ──


def _aid() -> str:
    return str(uuid.uuid4())


def _make_identity(attempt_id: str) -> AttemptIdentity:
    return AttemptIdentity(
        workflow_id="wf-1",
        run_id="run-1",
        graph_revision="rev-1",
        attempt_ordinal=1,
        attempt_id=attempt_id,
    )


def _make_provenance() -> AttemptProvenance:
    return AttemptProvenance(
        parent_attempt_id=None,
        causal_lineage=(),
        actor_id=None,
        tool_id=None,
    )


def _make_event(
    attempt_id: str,
    sequence: int,
    event_type: AttemptEventType,
    idempotency_key: str,
    causal_predecessor_sequence: int | None = None,
    *,
    outcome: AttemptOutcome | None = None,
    persistence_status: PersistenceStatus = PersistenceStatus.DURABLE,
) -> LedgerEvent:
    cps = sequence - 1 if causal_predecessor_sequence is None else causal_predecessor_sequence
    return LedgerEvent(
        idempotency_key=idempotency_key,
        event_type=event_type,
        identity=_make_identity(attempt_id),
        provenance=_make_provenance(),
        adapter=RuntimeAdapter(adapter_kind=AdapterKind.NATIVE, adapter_version="1"),
        versions=VersionSet(code_version="c1"),
        grant_ref=GrantRef(grant_id="grant-1"),
        sequence=sequence,
        causal_predecessor_sequence=cps,
        append_position=sequence - 1,
        occurred_at=f"2025-01-01T00:00:{sequence:02d}Z",
        observed_at=f"2025-01-01T00:00:{sequence:02d}Z",
        outcome=outcome,
        persistence_status=persistence_status,
    )


def _make_terminal_event(
    attempt_id: str,
    sequence: int,
    event_type: AttemptEventType,
    idempotency_key: str,
    outcome: AttemptOutcome,
    causal_predecessor_sequence: int | None = None,
) -> LedgerEvent:
    return _make_event(
        attempt_id,
        sequence,
        event_type,
        idempotency_key,
        causal_predecessor_sequence,
        outcome=outcome,
    )


def _seed_in_flight(store: SqliteAttemptLedgerStore, attempt_id: str) -> None:
    """Seed an attempt with a STARTED event (in-flight, no terminal)."""
    store.append_started(
        attempt_id,
        _make_event(attempt_id, sequence=1, event_type=AttemptEventType.STARTED, idempotency_key="k-start"),
    )


def _seed_terminal(store: SqliteAttemptLedgerStore, attempt_id: str) -> None:
    """Seed an attempt that has already drained to COMPLETED."""
    store.append_started(
        attempt_id,
        _make_event(attempt_id, sequence=1, event_type=AttemptEventType.STARTED, idempotency_key="k-start"),
    )
    store.append_completed(
        attempt_id,
        _make_terminal_event(
            attempt_id,
            sequence=2,
            event_type=AttemptEventType.COMPLETED,
            idempotency_key="k-done",
            outcome=AttemptOutcome.SUCCEEDED,
        ),
    )


# ── list_in_flight_attempts ─────────────────────────────────────────────────


class TestListInFlightAttempts:
    def test_returns_only_attempts_without_a_terminal_event(self, tmp_path: Path) -> None:
        store = SqliteAttemptLedgerStore(tmp_path / "s.sqlite3")
        in_flight_1, in_flight_2, drained = _aid(), _aid(), _aid()
        _seed_in_flight(store, in_flight_1)
        _seed_in_flight(store, in_flight_2)
        _seed_terminal(store, drained)

        listed = store.list_in_flight_attempts()

        assert set(listed) == {in_flight_1, in_flight_2}
        assert drained not in listed
        # Deterministic ordering for stable enumeration.
        assert listed == sorted(listed)
        store.close()

    def test_empty_store_lists_nothing(self, tmp_path: Path) -> None:
        store = SqliteAttemptLedgerStore(tmp_path / "s.sqlite3")
        assert store.list_in_flight_attempts() == []
        store.close()


# ── quiesce ─────────────────────────────────────────────────────────────────


class TestQuiesce:
    def test_engages_fence_and_enumerates_in_flight(self, tmp_path: Path) -> None:
        store = SqliteAttemptLedgerStore(tmp_path / "s.sqlite3")
        a, b = _aid(), _aid()
        _seed_in_flight(store, a)
        _seed_terminal(store, b)

        result = quiesce(store)

        assert result.cutover_in_progress is True
        assert result.previously_in_progress is False
        assert store.is_cutover_in_progress() is True
        enumerated_ids = {x.attempt_id for x in result.in_flight}
        assert enumerated_ids == {a}
        # The drained attempt is excluded from the in-flight enumeration.
        assert b not in enumerated_ids
        # The single in-flight attempt is classified via the drain map.
        assert len(result.in_flight) == 1
        assert result.in_flight[0].last_event_type is AttemptEventType.STARTED
        assert result.in_flight[0].drain_category is DrainCategory.INDETERMINATE
        store.close()

    def test_quiesce_is_idempotent_and_reports_resumption(self, tmp_path: Path) -> None:
        store = SqliteAttemptLedgerStore(tmp_path / "s.sqlite3")
        assert quiesce(store).previously_in_progress is False
        # Second quiesce reports the fence was already engaged (resumption).
        assert quiesce(store).previously_in_progress is True
        store.close()


# ── admission fence: new admissions rejected ────────────────────────────────


class TestAdmissionFence:
    def test_reserve_new_attempt_rejected_after_quiesce(self, tmp_path: Path) -> None:
        store = SqliteAttemptLedgerStore(tmp_path / "s.sqlite3")
        quiesce(store)
        with pytest.raises(CutoverInProgressError):
            store.reserve_attempt(_aid())
        store.close()

    def test_append_first_event_of_new_stream_rejected_after_quiesce(self, tmp_path: Path) -> None:
        store = SqliteAttemptLedgerStore(tmp_path / "s.sqlite3")
        quiesce(store)
        new_id = _aid()
        with pytest.raises(CutoverInProgressError):
            store.append_started(
                new_id,
                _make_event(new_id, sequence=1, event_type=AttemptEventType.STARTED, idempotency_key="k"),
            )
        store.close()

    def test_rereserve_of_existing_attempt_allowed_after_quiesce(self, tmp_path: Path) -> None:
        store = SqliteAttemptLedgerStore(tmp_path / "s.sqlite3")
        existing = _aid()
        _seed_in_flight(store, existing)
        quiesce(store)
        # Re-reserving an EXISTING attempt is a continuation, not a new admission.
        reservation = store.reserve_attempt(existing)
        assert reservation.attempt_id == existing
        store.close()

    def test_continuation_append_to_in_flight_attempt_allows_terminal_drain(self, tmp_path: Path) -> None:
        store = SqliteAttemptLedgerStore(tmp_path / "s.sqlite3")
        in_flight = _aid()
        _seed_in_flight(store, in_flight)
        quiesce(store)
        # The terminal drain of an existing in-flight attempt MUST be allowed
        # so the cutover can reach a quiescent state.
        store.append_completed(
            in_flight,
            _make_terminal_event(
                in_flight,
                sequence=2,
                event_type=AttemptEventType.COMPLETED,
                idempotency_key="k-done",
                outcome=AttemptOutcome.SUCCEEDED,
            ),
        )
        assert store.has_terminal_event(in_flight)
        assert in_flight not in store.list_in_flight_attempts()
        store.close()


# ── drain ───────────────────────────────────────────────────────────────────


class TestDrain:
    def test_marks_remaining_attempts_indeterminate_on_timeout(self, tmp_path: Path) -> None:
        store = SqliteAttemptLedgerStore(tmp_path / "s.sqlite3")
        a, b = _aid(), _aid()
        _seed_in_flight(store, a)
        _seed_in_flight(store, b)
        store.set_cutover_in_progress()

        # Inject a constant clock so the deadline is immediately reached.
        result = drain(store, timeout_seconds=0.0, clock=lambda: 0.0, sleep=lambda _s: None)

        assert set(result.drained) == set()
        assert {m.attempt_id for m in result.marked_indeterminate} == {a, b}
        assert result.timed_out is True
        for mark in result.marked_indeterminate:
            assert mark.resolved_outcome == AttemptOutcome.INDETERMINATE.value
            assert mark.drain_category == DrainCategory.INDETERMINATE.value
        # The marks are durable.
        durable = store.get_cutover_indeterminate_marks()
        assert {m.attempt_id for m in durable} == {a, b}
        for m in durable:
            assert m.resolved_outcome == AttemptOutcome.INDETERMINATE.value
        store.close()

    def test_drain_waits_for_attempt_that_terminates_within_timeout(self, tmp_path: Path) -> None:
        store = SqliteAttemptLedgerStore(tmp_path / "s.sqlite3")
        drainer, staller = _aid(), _aid()
        _seed_in_flight(store, drainer)
        _seed_in_flight(store, staller)
        store.set_cutover_in_progress()

        appended_terminal: list[bool] = []

        def fake_sleep(_seconds: float) -> None:
            # On the first sleep, the "drainer" attempt reaches a terminal
            # event (simulating a natural drain during the wait window).
            if not appended_terminal:
                store.append_completed(
                    drainer,
                    _make_terminal_event(
                        drainer,
                        sequence=2,
                        event_type=AttemptEventType.COMPLETED,
                        idempotency_key="k-done",
                        outcome=AttemptOutcome.SUCCEEDED,
                    ),
                )
                appended_terminal.append(True)

        # clock: 0.0 (entry) → 0.0 (first poll, before sleep) → 10.0 (past deadline)
        ticks = iter([0.0, 0.0, 10.0])

        def fake_clock() -> float:
            return next(ticks)

        result = drain(
            store,
            timeout_seconds=5.0,
            clock=fake_clock,
            sleep=fake_sleep,
        )

        assert drainer in result.drained
        assert staller not in result.drained
        staller_mark = [m for m in result.marked_indeterminate if m.attempt_id == staller]
        assert len(staller_mark) == 1
        assert staller_mark[0].resolved_outcome == AttemptOutcome.INDETERMINATE.value
        store.close()

    def test_drain_marks_persistence_failed_with_fail_closed_category(self, tmp_path: Path) -> None:
        store = SqliteAttemptLedgerStore(tmp_path / "s.sqlite3")
        pf = _aid()
        _seed_in_flight(store, pf)
        # Append a PERSISTENCE_FAILED event (no required predecessor) so the
        # attempt's last event is fail-closed.
        store.append_event(
            pf,
            _make_event(
                pf,
                sequence=2,
                event_type=AttemptEventType.PERSISTENCE_FAILED,
                idempotency_key="k-pf",
                persistence_status=PersistenceStatus.PERSISTENCE_FAILED,
            ),
        )
        store.set_cutover_in_progress()

        result = drain(store, timeout_seconds=0.0, clock=lambda: 0.0, sleep=lambda _s: None)

        assert len(result.marked_indeterminate) == 1
        mark = result.marked_indeterminate[0]
        assert mark.attempt_id == pf
        assert mark.drain_category == DrainCategory.PERSISTENCE_FAIL_CLOSED.value
        assert mark.resolved_outcome == AttemptOutcome.INDETERMINATE.value
        assert mark.last_event_type == AttemptEventType.PERSISTENCE_FAILED.value
        store.close()

    def test_drain_with_no_in_flight_marks_nothing(self, tmp_path: Path) -> None:
        store = SqliteAttemptLedgerStore(tmp_path / "s.sqlite3")
        store.set_cutover_in_progress()
        result = drain(store, timeout_seconds=0.0, clock=lambda: 0.0, sleep=lambda _s: None)
        assert result.drained == ()
        assert result.marked_indeterminate == ()
        assert result.timed_out is False
        store.close()


# ── crash preservation of the durable fence ────────────────────────────────


class TestCrashPreservation:
    def test_fence_survives_store_reopen_and_keeps_rejecting_admissions(
        self, tmp_path: Path
    ) -> None:
        db_path = tmp_path / "s.sqlite3"
        in_flight = _aid()
        store = SqliteAttemptLedgerStore(db_path)
        _seed_in_flight(store, in_flight)
        quiesce(store)
        assert store.is_cutover_in_progress() is True
        store.close()

        # Simulate a crash by reopening the SAME database file.
        reopened = SqliteAttemptLedgerStore(db_path)
        assert reopened.is_cutover_in_progress() is True
        # The fence still rejects new admissions after the crash.
        with pytest.raises(CutoverInProgressError):
            reopened.reserve_attempt(_aid())
        new_id = _aid()
        with pytest.raises(CutoverInProgressError):
            reopened.append_started(
                new_id,
                _make_event(new_id, sequence=1, event_type=AttemptEventType.STARTED, idempotency_key="k"),
            )
        # The surviving in-flight set is still enumerable.
        assert in_flight in reopened.list_in_flight_attempts()
        # The fence can be cleared after the cutover completes.
        assert reopened.clear_cutover_in_progress() is True
        assert reopened.is_cutover_in_progress() is False
        # After clearing, new admissions are accepted again.
        reopened.reserve_attempt(_aid())
        reopened.close()
