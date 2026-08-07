"""Concurrent atomic append and crash-recovery atomicity fixtures (Step 8).

Covers four crash/concurrency scenarios against ONE WAL-backed SQLite file:

1. ``test_concurrent_atomic_append`` — two independent
   ``SqliteAttemptLedgerStore`` connections racing on the same idempotency
   key yield exactly one successful append and one idempotent rejection, with
   no partial or duplicate records and monotonic sequences.

2. ``test_crash_during_append_rolls_back`` — an exception injected inside the
   append transaction (after INSERT, before COMMIT) is rolled back, leaving no
   partial record.

3. ``test_reservation_before_start_classified_persistence_failed`` — an
   attempt reserved but never STARTED reconciles to ``persistence_failed`` on
   restart.

4. ``test_direct_sql_sequence_gap_detected_by_query_gaps_only`` — non-
   contiguous sequences 1, 2, 4 injected via direct SQL prove
   ``validate_ledger_event_ordering`` stays empty (strict monotonicity, no
   gap detection) while ``query_gaps`` and ``reconcile_on_restart`` surface
   ``sequence_gap`` with no incomplete projection published.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from typing import Any

import pytest

from arnold.critique_ledger.persistence_service import (
    LedgerEventContext,
    LedgerEventMapper,
    LedgerPersistenceService,
    LedgerReconciliationResult,
    RECONCILE_STATUS_PERSISTENCE_FAILED,
    RECONCILE_STATUS_SEQUENCE_GAP,
)
from arnold.workflow.attempt_ledger_store import (
    GapEntry,
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
    RuntimeAdapter,
    VersionSet,
    validate_ledger_event_ordering,
)


def _context(attempt_id: str) -> LedgerEventContext:
    return LedgerEventContext(
        identity=AttemptIdentity(
            workflow_id="wf-cl2",
            run_id="run-cl2",
            graph_revision="rev-cl2",
            attempt_id=attempt_id,
        ),
        provenance=AttemptProvenance(),
        adapter=RuntimeAdapter(AdapterKind.NATIVE, "cl2-crash-test"),
        versions=VersionSet(code_version="c116f38cc83"),
        grant_ref=GrantRef(grant_id="bridge-no-positive-authority"),
        occurred_at="2026-08-06T00:00:00+00:00",
        observed_at="2026-08-06T00:00:01+00:00",
    )


def _lifecycle_event(
    context: LedgerEventContext,
    event_type: AttemptEventType,
    sequence: int,
    idempotency_key: str,
    *,
    payload: dict[str, Any] | None = None,
    outcome: AttemptOutcome | None = None,
    causal_predecessor: int | None = None,
    append_position: int | None = None,
) -> LedgerEvent:
    if causal_predecessor is None:
        causal_predecessor = sequence - 1
    if append_position is None:
        append_position = sequence - 1
    return LedgerEvent(
        idempotency_key=idempotency_key,
        event_type=event_type,
        identity=context.identity,
        provenance=context.provenance,
        adapter=context.adapter,
        versions=context.versions,
        grant_ref=context.grant_ref,
        sequence=sequence,
        causal_predecessor_sequence=causal_predecessor,
        append_position=append_position,
        occurred_at=context.occurred_at,
        observed_at=context.observed_at,
        payload=payload if payload is not None else {},
        outcome=outcome,
    )


def _inject_directly(
    store: SqliteAttemptLedgerStore, attempt_id: str, event: LedgerEvent
) -> None:
    """Append an event via direct SQL, bypassing ``_append_tx`` invariants.

    Used only to inject corruption (sequence gaps) that the public append path
    can never produce.  The event is serialized exactly as the store does so
    ``read_events`` round-trips it.
    """
    store.conn.execute(
        """
INSERT INTO attempt_events
    (attempt_id, sequence, idempotency_key, event_type, event_json, appended_at_ns)
VALUES (?, ?, ?, ?, ?, ?)
""",
        (
            attempt_id,
            event.sequence,
            event.idempotency_key,
            event.event_type.value,
            json.dumps(event.to_dict(), sort_keys=True, ensure_ascii=False),
            time.time_ns(),
        ),
    )
    store.conn.commit()


# ── 1. concurrent atomic append (two independent connections) ───────────────


def test_concurrent_atomic_append(tmp_path: Any) -> None:
    """Two independent WAL connections racing on one idempotency key.

    One append succeeds (``is_duplicate=False``), the other is an idempotent
    rejection (``is_duplicate=True``).  No partial or duplicate records; the
    final sequence is monotonic.
    """
    db_path = tmp_path / "race.sqlite"
    attempt_id = str(uuid.uuid4())
    context = _context(attempt_id)

    # Connection A performs all setup and commits.
    store_a = SqliteAttemptLedgerStore(db_path)
    service_a = LedgerPersistenceService(store_a)
    store_a.reserve_attempt(attempt_id)
    store_a.append_started(
        attempt_id,
        _lifecycle_event(context, AttemptEventType.STARTED, 1, "started"),
    )
    service_a.record_intent(
        attempt_id, {"briefing_ref": "ref"}, idempotency_key="intent", context=context
    )
    # Force a WAL checkpoint so connection B sees committed state.
    store_a.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    pre_count = store_a.event_count(attempt_id)
    assert pre_count == 2  # STARTED + INTENT

    # Connection B is an independent process-equivalent connection to the same
    # WAL file.  Both compute the next sequence from the shared durable state.
    store_b = SqliteAttemptLedgerStore(db_path)
    service_b = LedgerPersistenceService(store_b)
    # Ensure B sees A's committed events.
    assert store_b.event_count(attempt_id) == 2
    next_seq = store_b.last_sequence(attempt_id) + 1
    assert next_seq == 3

    # Both threads append the SAME outcome event (same idempotency key, same
    # sequence).  The shared ``BEGIN IMMEDIATE`` write lock serializes them.
    shared_event = _lifecycle_event(
        context,
        AttemptEventType.EXTERNAL_EFFECT_OUTCOME,
        next_seq,
        "race-outcome",
        payload={"cl2_kind": "occurrence", "envelope": {"occurrence_id": "occ-race"}},
    )

    results: list[Any] = []
    errors: list[BaseException] = []
    start_gate = threading.Event()

    def _append(store: SqliteAttemptLedgerStore) -> None:
        try:
            start_gate.wait(timeout=5.0)
            # Re-create the event per store so neither mutates shared state.
            results.append(
                store.append_event(
                    attempt_id,
                    _lifecycle_event(
                        context,
                        AttemptEventType.EXTERNAL_EFFECT_OUTCOME,
                        next_seq,
                        "race-outcome",
                        payload={
                            "cl2_kind": "occurrence",
                            "envelope": {"occurrence_id": "occ-race"},
                        },
                    ),
                )
            )
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    t_a = threading.Thread(target=_append, args=(store_a,))
    t_b = threading.Thread(target=_append, args=(store_b,))
    t_a.start()
    t_b.start()
    start_gate.set()
    t_a.join(timeout=15.0)
    t_b.join(timeout=15.0)

    assert errors == [], f"threads raised: {errors!r}"
    assert len(results) == 2

    dup_flags = sorted(r.is_duplicate for r in results)
    # Exactly one successful append and one idempotent rejection.
    assert dup_flags == [False, True]

    # No partial or duplicate records: exactly one event carries the racing
    # idempotency key, and the total count rose by exactly one.
    assert store_a.event_count(attempt_id) == pre_count + 1
    assert store_b.event_count(attempt_id) == pre_count + 1

    events = store_a.read_events(attempt_id)
    race_events = [e for e in events if e.idempotency_key == "race-outcome"]
    assert len(race_events) == 1
    # Sequences remain monotonic.
    seqs = [e.sequence for e in events]
    assert seqs == sorted(seqs)
    assert seqs == [1, 2, 3]


# ── 2. crash during append proves rollback ──────────────────────────────────


class _CrashOnCommitConnection:
    """Connection proxy that raises on COMMIT to simulate a mid-tx crash.

    All other calls delegate to the wrapped ``sqlite3.Connection`` so the
    store's real ``_append_tx`` logic runs through to the INSERT; the crash at
    COMMIT then exercises the store's own ``except`` handler, which issues
    ``ROLLBACK``.  This proves atomicity: a crash after INSERT leaves no
    partial record.
    """

    def __init__(self, real: sqlite3.Connection) -> None:
        self._real = real

    def execute(self, sql: Any, *args: Any, **kwargs: Any) -> Any:
        if isinstance(sql, str) and sql.strip().upper() == "COMMIT":
            raise sqlite3.OperationalError("simulated crash during COMMIT")
        return self._real.execute(sql, *args, **kwargs)

    def cursor(self) -> Any:
        return self._real.cursor()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._real, name)


def test_crash_during_append_rolls_back(tmp_path: Any) -> None:
    """An exception inside the append transaction rolls back; no partial record.

    The crash is injected after the INSERT statement runs but before COMMIT, so
    the only way the ledger stays clean is the store's transactional rollback.
    """
    store = SqliteAttemptLedgerStore(tmp_path / "crash.sqlite")
    attempt_id = str(uuid.uuid4())
    context = _context(attempt_id)
    service = LedgerPersistenceService(store)

    store.reserve_attempt(attempt_id)
    store.append_started(
        attempt_id,
        _lifecycle_event(context, AttemptEventType.STARTED, 1, "started"),
    )
    service.record_intent(
        attempt_id, {"briefing_ref": "ref"}, idempotency_key="intent", context=context
    )
    baseline_count = store.event_count(attempt_id)
    assert baseline_count == 2

    # Swap in the crash-on-commit proxy over the store's real connection.
    real_conn = store._conn
    assert real_conn is not None
    store._conn = _CrashOnCommitConnection(real_conn)  # type: ignore[assignment]

    crash_event = _lifecycle_event(
        context,
        AttemptEventType.EXTERNAL_EFFECT_OUTCOME,
        store.last_sequence(attempt_id) + 1,
        "crash-outcome",
        payload={"cl2_kind": "occurrence", "envelope": {"occurrence_id": "occ-crash"}},
    )
    with pytest.raises(sqlite3.OperationalError, match="simulated crash"):
        store.append_event(attempt_id, crash_event)

    # Restore the real connection before assertions.
    store._conn = real_conn  # type: ignore[assignment]

    # Rollback proof: no partial record survived the crash.
    assert store.event_count(attempt_id) == baseline_count
    remaining = store.read_events(attempt_id)
    assert all(e.idempotency_key != "crash-outcome" for e in remaining)
    # The high-water sequence is unchanged (the INSERT was rolled back).
    assert store.last_sequence(attempt_id) == 2


# ── 3. reservation-before-START restart classification ─────────────────────


def test_reservation_before_start_classified_persistence_failed(
    tmp_path: Any,
) -> None:
    """An attempt reserved but never STARTED reconciles to persistence_failed.

    Simulates a crash between ``reserve_attempt`` and ``append_started``: the
    reservation is durable but no STARTED event exists, so the restart worker
    classifies the stream as a failed start (not in-flight, not complete).
    """
    store = SqliteAttemptLedgerStore(tmp_path / "unstarted.sqlite")
    attempt_id = str(uuid.uuid4())

    # Reserve durably but do NOT append STARTED (crash before START).
    reservation = store.reserve_attempt(attempt_id)
    assert reservation.is_new is True
    assert reservation.reservation_count == 1
    assert store.event_count(attempt_id) == 0

    # Simulate restart with a fresh service over the same store.
    service = LedgerPersistenceService(store)
    result = service.reconcile_on_restart(attempt_id)

    assert isinstance(result, LedgerReconciliationResult)
    assert result.status == RECONCILE_STATUS_PERSISTENCE_FAILED
    assert result.issues == []
    snap = result.event_snapshot
    assert snap["is_reserved"] is True
    assert snap["has_started"] is False
    assert snap["has_terminal"] is False
    assert snap["event_count"] == 0


# ── 4. direct-SQL sequence gap: ordering stays empty, query_gaps reports ────


def test_direct_sql_sequence_gap_detected_by_query_gaps_only(
    tmp_path: Any,
) -> None:
    """Non-contiguous sequences 1, 2, 4 are detected by query_gaps only.

    The gap (missing sequence 3) is injected via direct SQL through
    ``store.conn`` because the public ``_append_tx`` path always generates
    contiguous sequences.  ``validate_ledger_event_ordering`` returns an EMPTY
    list (it checks strict monotonicity, not contiguity), while
    ``query_gaps`` returns one ``GapEntry`` and ``reconcile_on_restart``
    surfaces ``sequence_gap`` — so no incomplete projection is published.
    """
    store = SqliteAttemptLedgerStore(tmp_path / "gapped.sqlite")
    attempt_id = str(uuid.uuid4())
    context = _context(attempt_id)

    store.reserve_attempt(attempt_id)
    _inject_directly(
        store,
        attempt_id,
        _lifecycle_event(context, AttemptEventType.STARTED, 1, "started"),
    )
    _inject_directly(
        store,
        attempt_id,
        _lifecycle_event(
            context, AttemptEventType.EXTERNAL_EFFECT_INTENT, 2, "intent"
        ),
    )
    # Sequence 4 with a VALID causal chain referencing the persisted seq 2
    # (not the missing seq 3) so the monotonicity/causal check cannot see the
    # gap.  Sequence 3 is deliberately omitted.
    _inject_directly(
        store,
        attempt_id,
        _lifecycle_event(
            context,
            AttemptEventType.EXTERNAL_EFFECT_OUTCOME,
            4,
            "outcome-after-gap",
            causal_predecessor=2,
            append_position=3,
            payload={"cl2_kind": "occurrence", "envelope": {"occurrence_id": "occ-gap"}},
        ),
    )

    events = store.read_events(attempt_id)
    assert [e.sequence for e in events] == [1, 2, 4]

    # NEGATIVE: ordering validation stays empty — it does not detect the
    # non-contiguous gap (strict monotonicity only).
    assert validate_ledger_event_ordering(events) == []

    # POSITIVE: query_gaps detects the missing sequence 3.
    gaps = store.query_gaps(attempt_id)
    assert gaps == [
        GapEntry(
            attempt_id=attempt_id,
            gap_start=2,
            gap_end=4,
            missing_count=1,
        )
    ]

    # POSITIVE: reconcile_on_restart surfaces sequence_gap, so a restart worker
    # halts rather than publishing an incomplete projection.
    service = LedgerPersistenceService(store)
    result = service.reconcile_on_restart(attempt_id)
    assert result.status == RECONCILE_STATUS_SEQUENCE_GAP
    # Actually-missing range formatted as gap_start+1..gap_end-1 (here 3..3).
    assert result.issues == ["gap 3..3 (missing 1)"]
    # The gap status means no complete/indeterminate projection is published —
    # the stream is flagged for recovery, not replayed as-is.
    assert result.status not in ("complete", "indeterminate")
