"""Tests for ``LedgerOutbox`` and ``SqliteLedgerOutbox``.

Focused coverage:
* Atomic ledger-event + outbox-record creation in one transaction
* Prepare boundary: both writes staged before COMMIT
* Commit boundary: both writes visible after COMMIT
* Rollback boundary: neither write visible after ROLLBACK
* Split-brain prevention: cannot have event without outbox or outbox without event
* Duplicate handling: no duplicate outbox records on dedup
* Lifecycle operations: mark_dispatched, mark_failed
* Query operations: get_pending, get_records_for_attempt
"""

from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import uuid
from typing import Any

import pytest

from arnold.workflow.attempt_ledger_store import (
    AppendResult,
    MonotonicSequenceError,
    PostTerminalAppendError,
    SqliteAttemptLedgerStore,
)
from arnold.workflow.execution_attempt_ledger import (
    LEDGER_SCHEMA_VERSION,
    AdapterKind,
    AttemptEventType,
    AttemptIdentity,
    AttemptOutcome,
    AttemptProvenance,
    GrantRef,
    LedgerEvent,
    RuntimeAdapter,
    VersionSet,
)
from arnold.workflow.ledger_outbox import (
    MAX_RETRY_COUNT,
    AppendWithOutboxResult,
    LedgerOutbox,
    OutboxRecord,
    OutboxStatus,
    RetryLimitExceededError,
    SqliteLedgerOutbox,
)


# ── Helpers ───────────────────────────────────────────────────────────────


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
) -> LedgerEvent:
    aid = attempt_id if attempt_id is not None else _aid()
    return LedgerEvent(
        idempotency_key=idempotency_key,
        event_type=event_type,
        identity=_make_identity(attempt_id=aid),
        provenance=_make_provenance(),
        adapter=RuntimeAdapter(
            adapter_kind=AdapterKind.NATIVE, adapter_version="1"
        ),
        versions=VersionSet(code_version="c1"),
        grant_ref=GrantRef(grant_id="grant-1"),
        sequence=sequence,
        causal_predecessor_sequence=causal_predecessor_sequence,
        append_position=append_position,
        occurred_at="2025-01-01T00:00:00Z",
        observed_at="2025-01-01T00:00:01Z",
    )


def _make_completed_event(
    attempt_id: str | None = None,
    sequence: int = 2,
    idempotency_key: str = "idem-2",
) -> LedgerEvent:
    aid = attempt_id if attempt_id is not None else _aid()
    cps = sequence - 1
    return LedgerEvent(
        idempotency_key=idempotency_key,
        event_type=AttemptEventType.COMPLETED,
        identity=_make_identity(attempt_id=aid),
        provenance=_make_provenance(),
        adapter=RuntimeAdapter(
            adapter_kind=AdapterKind.NATIVE, adapter_version="1"
        ),
        versions=VersionSet(code_version="c1"),
        grant_ref=GrantRef(grant_id="grant-1"),
        sequence=sequence,
        causal_predecessor_sequence=cps,
        append_position=1,
        occurred_at="2025-01-01T00:00:10Z",
        observed_at="2025-01-01T00:00:11Z",
        outcome=AttemptOutcome.SUCCEEDED,
    )


def _store_path() -> str:
    fd, path = tempfile.mkstemp(suffix=".db", prefix="test_outbox_")
    os.close(fd)
    return path


def _make_outbox_payloads(
    destinations: list[str] | None = None,
) -> list[dict[str, Any]]:
    if destinations is None:
        destinations = ["effect.shell.v1"]
    return [
        {"destination": d, "payload": {"key": f"val-{i}", "ts": "2025-01-01T00:00:00Z"}}
        for i, d in enumerate(destinations)
    ]


# ── Atomicity: prepare / commit / rollback boundaries ────────────────────


class TestOutboxAtomicity:
    """Prove that ledger events and outbox records are committed or
    rolled back atomically within the same SQLite transaction.

    This directly addresses sense check SC7.
    """

    # ── Commit boundary ──────────────────────────────────────────────

    def test_commit_both_visible(self):
        """After COMMIT, both the event and outbox records are visible."""
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            outbox = SqliteLedgerOutbox(store)
            aid = _aid()
            event = _make_event(attempt_id=aid, sequence=1)
            payloads = _make_outbox_payloads(["topic.a", "topic.b"])

            result = outbox.append_event_with_outbox(aid, event, payloads)

            # Event is visible.
            assert store.event_count(aid) == 1
            events = store.read_events(aid)
            assert len(events) == 1
            assert events[0].idempotency_key == event.idempotency_key

            # Outbox records are visible.
            records = outbox.get_records_for_attempt(aid)
            assert len(records) == 2
            assert all(r.status == OutboxStatus.PENDING.value for r in records)
            assert {r.destination for r in records} == {"topic.a", "topic.b"}

            # Result carries both.
            assert result.is_duplicate is False
            assert result.sequence == 1
            assert len(result.outbox_records) == 2

            store.close()
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_commit_single_outbox_record(self):
        """Single outbox record is committed atomically with the event."""
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            outbox = SqliteLedgerOutbox(store)
            aid = _aid()
            event = _make_event(attempt_id=aid, sequence=1)
            payloads = _make_outbox_payloads(["effect.shell.v1"])

            result = outbox.append_event_with_outbox(aid, event, payloads)

            assert store.event_count(aid) == 1
            records = outbox.get_records_for_attempt(aid)
            assert len(records) == 1
            assert records[0].destination == "effect.shell.v1"
            assert records[0].event_sequence == 1
            assert records[0].event_idempotency_key == event.idempotency_key

            store.close()
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_commit_zero_outbox_records(self):
        """Appending with empty outbox payloads still commits the event."""
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            outbox = SqliteLedgerOutbox(store)
            aid = _aid()
            event = _make_event(attempt_id=aid, sequence=1)
            payloads: list[dict[str, str]] = []

            result = outbox.append_event_with_outbox(aid, event, payloads)

            assert store.event_count(aid) == 1
            records = outbox.get_records_for_attempt(aid)
            assert len(records) == 0
            assert len(result.outbox_records) == 0
            assert result.is_duplicate is False

            store.close()
        finally:
            if os.path.exists(path):
                os.unlink(path)

    # ── Rollback boundary ─────────────────────────────────────────────

    def test_rollback_post_terminal_rejection(self):
        """Post-terminal rejection rolls back both event and outbox writes."""
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            outbox = SqliteLedgerOutbox(store)
            aid = _aid()

            # First, append and complete the attempt via plain store.
            e1 = _make_event(attempt_id=aid, sequence=1, idempotency_key="k1")
            store.append_event(aid, e1)
            e2 = _make_completed_event(attempt_id=aid, sequence=2, idempotency_key="k2")
            store.append_event(aid, e2)

            # Now try to append a post-terminal event with outbox records.
            e3 = _make_event(attempt_id=aid, sequence=3, idempotency_key="k3")
            payloads = _make_outbox_payloads(["topic.c"])

            with pytest.raises(PostTerminalAppendError):
                outbox.append_event_with_outbox(aid, e3, payloads)

            # Neither the event nor the outbox records should exist.
            assert store.event_count(aid) == 2  # Only the first two.
            records = outbox.get_records_for_attempt(aid)
            assert len(records) == 0

            store.close()
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_rollback_monotonic_sequence_error(self):
        """Monotonic sequence error rolls back both event and outbox writes."""
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            outbox = SqliteLedgerOutbox(store)
            aid = _aid()

            # Establish the contiguous stream required by the M7 gap guard.
            e1 = _make_event(attempt_id=aid, sequence=1, idempotency_key="k1")
            store.append_event(aid, e1)

            # Reuse sequence 1 with a different idempotency key (regression).
            e2 = _make_event(attempt_id=aid, sequence=1, idempotency_key="k2")
            payloads = _make_outbox_payloads(["topic.d"])

            with pytest.raises(MonotonicSequenceError):
                outbox.append_event_with_outbox(aid, e2, payloads)

            # Only the first event exists.
            assert store.event_count(aid) == 1
            records = outbox.get_records_for_attempt(aid)
            assert len(records) == 0

            store.close()
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_rollback_mismatched_attempt_id(self):
        """Mismatched attempt_id raises before transaction, nothing written."""
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            outbox = SqliteLedgerOutbox(store)
            aid_store = _aid()
            aid_event = _aid()
            assert aid_store != aid_event

            event = _make_event(attempt_id=aid_event, sequence=1)
            payloads = _make_outbox_payloads()

            with pytest.raises(ValueError, match="does not match"):
                outbox.append_event_with_outbox(aid_store, event, payloads)

            # Nothing persisted for either ID.
            assert store.event_count(aid_store) == 0
            assert store.event_count(aid_event) == 0
            records = outbox.get_records_for_attempt(aid_store)
            assert len(records) == 0

            store.close()
        finally:
            if os.path.exists(path):
                os.unlink(path)

    # ── Prepare boundary ──────────────────────────────────────────────

    def test_prepare_boundary_not_visible_outside_transaction(self):
        """Writes inside BEGIN IMMEDIATE are not visible to other connections
        until COMMIT.

        We simulate this by using the same connection's own read methods
        outside the transaction. Since the store uses ``isolation_level=None``
        (autocommit), a separate read after BEGIN but before COMMIT on a
        different connection would see nothing. We use a second connection
        to prove the prepare boundary.
        """
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            outbox = SqliteLedgerOutbox(store)
            aid = _aid()

            # We'll do a manual transaction to show the prepare boundary.
            conn = store.conn
            # First, do a normal append through outbox to set up state.
            # Then use raw connection to demonstrate prepare/commit boundary.

            event = _make_event(attempt_id=aid, sequence=1)
            payloads = _make_outbox_payloads(["topic.prepare"])

            # Open a second connection to observe prepare boundary.
            conn2 = sqlite3.connect(path, timeout=5.0)

            # Start transaction on main connection.
            conn.execute("BEGIN IMMEDIATE")
            try:
                cur = conn.cursor()
                event_json = json.dumps(event.to_dict(), sort_keys=True, ensure_ascii=False)
                now_ns = 1_000_000_000_000_000
                cur.execute(
                    "INSERT INTO attempt_events"
                    " (attempt_id, sequence, idempotency_key, event_type, event_json, appended_at_ns)"
                    " VALUES (?, ?, ?, ?, ?, ?)",
                    (aid, event.sequence, event.idempotency_key, event.event_type.value, event_json, now_ns),
                )
                cur.execute(
                    "INSERT INTO outbox_records"
                    " (outbox_id, attempt_id, event_sequence, event_idempotency_key,"
                    "  destination, payload_json, status, created_at_ns)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    ("ob-1", aid, 1, event.idempotency_key, "topic.prepare",
                     json.dumps({"k": "v"}), "pending", now_ns),
                )

                # Before COMMIT, second connection sees nothing.
                cur2 = conn2.cursor()
                cur2.execute("SELECT COUNT(1) FROM attempt_events WHERE attempt_id = ?", (aid,))
                assert cur2.fetchone()[0] == 0
                cur2.execute("SELECT COUNT(1) FROM outbox_records WHERE attempt_id = ?", (aid,))
                assert cur2.fetchone()[0] == 0

                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise
            finally:
                conn2.close()

            # After COMMIT, both are visible.
            assert store.event_count(aid) == 1
            records = outbox.get_records_for_attempt(aid)
            assert len(records) == 1

            store.close()
        finally:
            if os.path.exists(path):
                os.unlink(path)

    # ── Split-brain prevention ────────────────────────────────────────

    def test_cannot_have_event_without_outbox_when_outbox_intended(self):
        """When using append_event_with_outbox with payloads, the event
        and outbox records always land together. After a successful call,
        both must be present.
        """
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            outbox = SqliteLedgerOutbox(store)
            aid = _aid()

            event = _make_event(attempt_id=aid, sequence=1)
            payloads = _make_outbox_payloads(["topic.x", "topic.y"])

            result = outbox.append_event_with_outbox(aid, event, payloads)

            # Event count is 1.
            assert store.event_count(aid) == 1
            # Outbox count is exactly the number of payloads.
            records = outbox.get_records_for_attempt(aid)
            assert len(records) == 2

            # Each outbox record references the correct event.
            for rec in records:
                assert rec.event_sequence == event.sequence
                assert rec.event_idempotency_key == event.idempotency_key
                assert rec.attempt_id == aid

            store.close()
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_cannot_have_outbox_without_event(self):
        """The only way to create outbox records is through
        append_event_with_outbox, which atomically writes both. There is
        no public API to create orphan outbox records.
        """
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            outbox = SqliteLedgerOutbox(store)
            aid = _aid()

            # Query before any append — no outbox records.
            records = outbox.get_records_for_attempt(aid)
            assert len(records) == 0

            # Append event WITHOUT outbox via plain store.
            event = _make_event(attempt_id=aid, sequence=1)
            store.append_event(aid, event)

            # Outbox is still empty — no orphan records.
            records = outbox.get_records_for_attempt(aid)
            assert len(records) == 0

            store.close()
        finally:
            if os.path.exists(path):
                os.unlink(path)

    # ── Duplicate handling ────────────────────────────────────────────

    def test_duplicate_event_does_not_create_outbox_records(self):
        """Dedup returns existing event with empty outbox records."""
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            outbox = SqliteLedgerOutbox(store)
            aid = _aid()

            event = _make_event(attempt_id=aid, sequence=1, idempotency_key="dup-key")
            payloads = _make_outbox_payloads(["topic.1"])

            # First append — creates event + outbox.
            r1 = outbox.append_event_with_outbox(aid, event, payloads)
            assert r1.is_duplicate is False
            assert len(r1.outbox_records) == 1

            # Second append with same idempotency key — dedup.
            r2 = outbox.append_event_with_outbox(aid, event, payloads)
            assert r2.is_duplicate is True
            assert len(r2.outbox_records) == 0

            # Only one set of outbox records exists.
            records = outbox.get_records_for_attempt(aid)
            assert len(records) == 1

            store.close()
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_duplicate_different_payloads_returns_original(self):
        """When an idempotency key matches but outbox payloads differ,
        the original event is returned and no new outbox records are created.
        """
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            outbox = SqliteLedgerOutbox(store)
            aid = _aid()

            event = _make_event(attempt_id=aid, sequence=1, idempotency_key="dup-key")

            # First append with payload A.
            r1 = outbox.append_event_with_outbox(
                aid, event, [{"destination": "topic.a", "payload": {"v": 1}}]
            )
            assert r1.is_duplicate is False
            assert len(r1.outbox_records) == 1
            assert r1.outbox_records[0].destination == "topic.a"

            # Second append with same idempotency key but different payload.
            r2 = outbox.append_event_with_outbox(
                aid, event, [{"destination": "topic.b", "payload": {"v": 2}}]
            )
            assert r2.is_duplicate is True
            assert len(r2.outbox_records) == 0

            # Only the original outbox record exists.
            records = outbox.get_records_for_attempt(aid)
            assert len(records) == 1
            assert records[0].destination == "topic.a"

            store.close()
        finally:
            if os.path.exists(path):
                os.unlink(path)


# ── Lifecycle operations ──────────────────────────────────────────────────


class TestOutboxLifecycle:
    """Test mark_dispatched, mark_failed, and query operations."""

    def test_mark_dispatched_updates_status(self):
        """Marking a record as dispatched changes its status and timestamp."""
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            outbox = SqliteLedgerOutbox(store)
            aid = _aid()

            event = _make_event(attempt_id=aid, sequence=1)
            payloads = _make_outbox_payloads(["topic.dispatch"])
            result = outbox.append_event_with_outbox(aid, event, payloads)
            ob_id = result.outbox_records[0].outbox_id

            # Initially pending.
            records = outbox.get_records_for_attempt(aid)
            assert records[0].status == OutboxStatus.PENDING.value
            assert records[0].dispatched_at_ns is None

            # Mark dispatched.
            outbox.mark_dispatched(ob_id)

            # Now dispatched.
            records = outbox.get_records_for_attempt(aid)
            assert records[0].status == OutboxStatus.DISPATCHED.value
            assert records[0].dispatched_at_ns is not None

            store.close()
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_mark_dispatched_is_idempotent(self):
        """Marking an already-dispatched record is safe."""
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            outbox = SqliteLedgerOutbox(store)
            aid = _aid()

            event = _make_event(attempt_id=aid, sequence=1)
            payloads = _make_outbox_payloads(["topic.idem-dispatch"])
            result = outbox.append_event_with_outbox(aid, event, payloads)
            ob_id = result.outbox_records[0].outbox_id

            outbox.mark_dispatched(ob_id)
            outbox.mark_dispatched(ob_id)  # No error.

            records = outbox.get_records_for_attempt(aid)
            assert records[0].status == OutboxStatus.DISPATCHED.value

            store.close()
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_mark_failed_increments_count(self):
        """Marking a record as failed increments failure_count."""
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            outbox = SqliteLedgerOutbox(store)
            aid = _aid()

            event = _make_event(attempt_id=aid, sequence=1)
            payloads = _make_outbox_payloads(["topic.fail"])
            result = outbox.append_event_with_outbox(aid, event, payloads)
            ob_id = result.outbox_records[0].outbox_id

            outbox.mark_failed(ob_id, "connection refused")
            records = outbox.get_records_for_attempt(aid)
            assert records[0].status == OutboxStatus.FAILED.value
            assert records[0].failure_count == 1
            assert records[0].last_failure_reason == "connection refused"
            assert records[0].last_failure_at_ns is not None

            # Second failure increments.
            outbox.mark_failed(ob_id, "timeout")
            records = outbox.get_records_for_attempt(aid)
            assert records[0].failure_count == 2
            assert records[0].last_failure_reason == "timeout"

            store.close()
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_get_pending_returns_only_pending(self):
        """get_pending filters by status and respects limit."""
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            outbox = SqliteLedgerOutbox(store)

            # Create records for two different attempts.
            for i in range(3):
                aid = _aid()
                event = _make_event(attempt_id=aid, sequence=1, idempotency_key=f"k-{i}")
                payloads = _make_outbox_payloads([f"topic.{i}"])
                outbox.append_event_with_outbox(aid, event, payloads)

            # All 3 are pending.
            pending = outbox.get_pending(limit=10)
            assert len(pending) == 3
            assert all(r.status == OutboxStatus.PENDING.value for r in pending)

            # Dispatch the first one.
            outbox.mark_dispatched(pending[0].outbox_id)

            # Now only 2 pending.
            pending = outbox.get_pending(limit=10)
            assert len(pending) == 2

            # Limit works.
            pending_limited = outbox.get_pending(limit=1)
            assert len(pending_limited) == 1

            store.close()
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_get_records_for_attempt_ordered(self):
        """Records are returned ordered by event_sequence then created_at_ns."""
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            outbox = SqliteLedgerOutbox(store)
            aid = _aid()

            # Append two events with outbox records.
            e1 = _make_event(attempt_id=aid, sequence=1, idempotency_key="k1")
            outbox.append_event_with_outbox(aid, e1, [{"destination": "t1", "payload": {}}])

            e2 = _make_completed_event(attempt_id=aid, sequence=2, idempotency_key="k2")
            outbox.append_event_with_outbox(aid, e2, [{"destination": "t2", "payload": {}}])

            records = outbox.get_records_for_attempt(aid)
            assert len(records) == 2
            assert records[0].event_sequence == 1
            assert records[1].event_sequence == 2

            store.close()
        finally:
            if os.path.exists(path):
                os.unlink(path)


# ── Integration: existing store invariants preserved ─────────────────────


class TestOutboxStoreIntegration:
    """Prove that append_event_with_outbox preserves all existing store
    invariants from the SqliteAttemptLedgerStore.
    """

    def test_monotonic_sequence_enforced(self):
        """Sequence regression is rejected."""
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            outbox = SqliteLedgerOutbox(store)
            aid = _aid()

            e1 = _make_event(attempt_id=aid, sequence=10, idempotency_key="k1")
            outbox.append_event_with_outbox(aid, e1, _make_outbox_payloads())

            e2 = _make_event(attempt_id=aid, sequence=5, idempotency_key="k2")
            with pytest.raises(MonotonicSequenceError):
                outbox.append_event_with_outbox(aid, e2, _make_outbox_payloads())

            store.close()
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_post_terminal_rejection_enforced(self):
        """No appends after terminal event."""
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            outbox = SqliteLedgerOutbox(store)
            aid = _aid()

            e1 = _make_event(attempt_id=aid, sequence=1, idempotency_key="k1")
            outbox.append_event_with_outbox(aid, e1, _make_outbox_payloads())

            e2 = _make_completed_event(attempt_id=aid, sequence=2, idempotency_key="k2")
            outbox.append_event_with_outbox(aid, e2, _make_outbox_payloads())

            e3 = _make_event(attempt_id=aid, sequence=3, idempotency_key="k3")
            with pytest.raises(PostTerminalAppendError):
                outbox.append_event_with_outbox(aid, e3, _make_outbox_payloads())

            store.close()
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_dedup_wins_over_post_terminal_rejection(self):
        """Dedup returns existing event even after terminal, no outbox records."""
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            outbox = SqliteLedgerOutbox(store)
            aid = _aid()

            e1 = _make_event(attempt_id=aid, sequence=1, idempotency_key="k1")
            outbox.append_event_with_outbox(aid, e1, _make_outbox_payloads(["t1"]))

            e2 = _make_completed_event(attempt_id=aid, sequence=2, idempotency_key="k2")
            outbox.append_event_with_outbox(aid, e2, _make_outbox_payloads(["t2"]))

            # Retry of e2 — dedup returns existing event, no new outbox records.
            r3 = outbox.append_event_with_outbox(aid, e2, _make_outbox_payloads(["t3"]))
            assert r3.is_duplicate is True
            assert len(r3.outbox_records) == 0

            # Only 2 outbox records total (one per unique event).
            records = outbox.get_records_for_attempt(aid)
            assert len(records) == 2

            store.close()
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_idempotency_key_uniqueness(self):
        """Same idempotency key cannot create two different events."""
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            outbox = SqliteLedgerOutbox(store)
            aid = _aid()

            event = _make_event(attempt_id=aid, sequence=1, idempotency_key="unique-key")
            r1 = outbox.append_event_with_outbox(aid, event, _make_outbox_payloads(["t1"]))
            assert r1.is_duplicate is False

            # Same key, same event — dedup.
            r2 = outbox.append_event_with_outbox(aid, event, _make_outbox_payloads(["t2"]))
            assert r2.is_duplicate is True

            store.close()
        finally:
            if os.path.exists(path):
                os.unlink(path)


# ── Cross-connection visibility ──────────────────────────────────────────


class TestOutboxCrossConnectionVisibility:
    """Prove that committed outbox records are visible to new connections."""

    def test_outbox_visible_to_new_store_instance(self):
        """After closing and reopening, outbox records are durable."""
        path = _store_path()
        try:
            aid = _aid()

            # Create and populate.
            store1 = SqliteAttemptLedgerStore(path)
            outbox1 = SqliteLedgerOutbox(store1)
            event = _make_event(attempt_id=aid, sequence=1)
            outbox1.append_event_with_outbox(aid, event, _make_outbox_payloads(["t1", "t2"]))
            store1.close()

            # Reopen and verify.
            store2 = SqliteAttemptLedgerStore(path)
            outbox2 = SqliteLedgerOutbox(store2)
            records = outbox2.get_records_for_attempt(aid)
            assert len(records) == 2
            assert store2.event_count(aid) == 1
            store2.close()
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_pending_visible_across_connections(self):
        """Pending records created in one connection are visible in another."""
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            outbox = SqliteLedgerOutbox(store)
            aid = _aid()

            event = _make_event(attempt_id=aid, sequence=1)
            outbox.append_event_with_outbox(aid, event, _make_outbox_payloads(["pending-topic"]))

            # Open a second connection and check.
            conn2 = sqlite3.connect(path, timeout=5.0)
            cur2 = conn2.cursor()
            cur2.execute(
                "SELECT COUNT(1) FROM outbox_records WHERE status = ?",
                (OutboxStatus.PENDING.value,),
            )
            assert cur2.fetchone()[0] == 1
            conn2.close()

            store.close()
        finally:
            if os.path.exists(path):
                os.unlink(path)


# ── Retry: retry_failed lifecycle ─────────────────────────────────────────


class TestOutboxRetry:
    """Prove at-least-once retry with idempotency-key dedupe and
    bounded max-retry enforcement on the outbox delivery path."""

    def test_retry_failed_transitions_back_to_pending(self):
        """A FAILED record can be retried and becomes PENDING again."""
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            outbox = SqliteLedgerOutbox(store)
            aid = _aid()

            event = _make_event(attempt_id=aid, sequence=1)
            result = outbox.append_event_with_outbox(
                aid, event, _make_outbox_payloads(["topic.retry"])
            )
            ob_id = result.outbox_records[0].outbox_id

            # Mark failed.
            outbox.mark_failed(ob_id, "transient error")
            records = outbox.get_records_for_attempt(aid)
            assert records[0].status == OutboxStatus.FAILED.value
            assert records[0].failure_count == 1

            # Retry.
            updated = outbox.retry_failed(ob_id)
            assert updated.status == OutboxStatus.PENDING.value
            # failure_count is NOT reset — it continues to accumulate.
            assert updated.failure_count == 1

            # Can now dispatch successfully.
            outbox.mark_dispatched(ob_id)
            records = outbox.get_records_for_attempt(aid)
            assert records[0].status == OutboxStatus.DISPATCHED.value

            store.close()
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_retry_failed_raises_on_non_failed_status(self):
        """retry_failed only works on FAILED records."""
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            outbox = SqliteLedgerOutbox(store)
            aid = _aid()

            event = _make_event(attempt_id=aid, sequence=1)
            result = outbox.append_event_with_outbox(
                aid, event, _make_outbox_payloads(["topic.retry-status"])
            )
            ob_id = result.outbox_records[0].outbox_id

            # Still PENDING — retry_failed should raise.
            with pytest.raises(ValueError, match="expected 'failed'"):
                outbox.retry_failed(ob_id)

            # Mark dispatched — retry_failed should raise.
            outbox.mark_dispatched(ob_id)
            with pytest.raises(ValueError, match="expected 'failed'"):
                outbox.retry_failed(ob_id)

            store.close()
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_retry_failed_raises_on_nonexistent_id(self):
        """retry_failed on unknown outbox_id raises ValueError."""
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            outbox = SqliteLedgerOutbox(store)

            with pytest.raises(ValueError, match="not found"):
                outbox.retry_failed("nonexistent-id")

            store.close()
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_retry_failed_respects_max_retries(self):
        """When failure_count >= max_retries, retry_failed raises
        RetryLimitExceededError."""
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            outbox = SqliteLedgerOutbox(store)
            aid = _aid()

            event = _make_event(attempt_id=aid, sequence=1)
            result = outbox.append_event_with_outbox(
                aid, event, _make_outbox_payloads(["topic.max-retry"])
            )
            ob_id = result.outbox_records[0].outbox_id

            max_retries = 3
            # Simulate failing max_retries times.
            for i in range(max_retries):
                outbox.mark_failed(ob_id, f"attempt {i + 1}")
                if i < max_retries - 1:
                    outbox.retry_failed(ob_id, max_retries=max_retries)

            # Now failure_count == max_retries, so retry should be rejected.
            with pytest.raises(RetryLimitExceededError) as exc_info:
                outbox.retry_failed(ob_id, max_retries=max_retries)
            assert exc_info.value.outbox_id == ob_id
            assert exc_info.value.failure_count == max_retries

            # Record remains FAILED.
            records = outbox.get_records_for_attempt(aid)
            assert records[0].status == OutboxStatus.FAILED.value
            assert records[0].failure_count == max_retries

            store.close()
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_retry_max_retries_uses_constant_default(self):
        """retry_failed uses MAX_RETRY_COUNT as the default max_retries."""
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            outbox = SqliteLedgerOutbox(store)
            aid = _aid()

            event = _make_event(attempt_id=aid, sequence=1)
            result = outbox.append_event_with_outbox(
                aid, event, _make_outbox_payloads(["topic.default-max"])
            )
            ob_id = result.outbox_records[0].outbox_id

            # Fail exactly MAX_RETRY_COUNT times.
            for i in range(MAX_RETRY_COUNT):
                outbox.mark_failed(ob_id, f"failure {i + 1}")
                if i < MAX_RETRY_COUNT - 1:
                    outbox.retry_failed(ob_id)  # Uses default MAX_RETRY_COUNT

            # Now at the limit.
            with pytest.raises(RetryLimitExceededError):
                outbox.retry_failed(ob_id)

            store.close()
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_retry_then_dispatch_full_cycle(self):
        """Full at-least-once cycle: append → fail → retry → dispatch.

        The same event must not result in duplicate accepted effects.
        """
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            outbox = SqliteLedgerOutbox(store)
            aid = _aid()

            event = _make_event(attempt_id=aid, sequence=1, idempotency_key="at-least-once-1")
            result = outbox.append_event_with_outbox(
                aid, event, _make_outbox_payloads(["effect.v1"])
            )
            ob_id = result.outbox_records[0].outbox_id

            # Simulate delivery attempt 1: fails.
            outbox.mark_failed(ob_id, "network timeout")
            records = outbox.get_records_for_attempt(aid)
            assert records[0].status == OutboxStatus.FAILED.value

            # Retry (re-queue).
            retried = outbox.retry_failed(ob_id)
            assert retried.status == OutboxStatus.PENDING.value

            # Simulate delivery attempt 2: succeeds.
            outbox.mark_dispatched(ob_id)
            records = outbox.get_records_for_attempt(aid)
            assert records[0].status == OutboxStatus.DISPATCHED.value
            assert records[0].failure_count == 1  # Retained for audit.

            # Verify: only ONE outbox record exists — no duplicates.
            assert len(records) == 1
            # Verify: the event itself was NOT duplicated (idempotency-key dedup).
            assert store.event_count(aid) == 1

            store.close()
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_retry_idempotency_key_dedup_prevents_duplicate_effects(self):
        """Even with retries, the idempotency key ensures no duplicate
        accepted effects. A second append with the same key returns
        the existing event and creates no new outbox records."""
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            outbox = SqliteLedgerOutbox(store)
            aid = _aid()

            event = _make_event(attempt_id=aid, sequence=1, idempotency_key="dedup-effect-1")
            r1 = outbox.append_event_with_outbox(
                aid, event, _make_outbox_payloads(["effect.v1"])
            )
            assert r1.is_duplicate is False
            assert len(r1.outbox_records) == 1

            # Dispatch.
            outbox.mark_dispatched(r1.outbox_records[0].outbox_id)

            # Replay the same event (crash recovery re-submit).
            r2 = outbox.append_event_with_outbox(
                aid, event, _make_outbox_payloads(["effect.v1"])
            )
            assert r2.is_duplicate is True
            assert len(r2.outbox_records) == 0

            # Only one outbox record, one event.
            assert store.event_count(aid) == 1
            records = outbox.get_records_for_attempt(aid)
            assert len(records) == 1
            assert records[0].status == OutboxStatus.DISPATCHED.value

            store.close()
        finally:
            if os.path.exists(path):
                os.unlink(path)


# ── Crash recovery and stale pending ───────────────────────────────────────


class TestOutboxCrashRecovery:
    """Prove at-least-once delivery survives crash scenarios via
    stale-pending detection and re-delivery."""

    def test_stale_pending_detects_unacked_records(self):
        """Pending records older than a threshold are returned as stale."""
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            outbox = SqliteLedgerOutbox(store)

            # Create records at different timestamps.
            import time as _time
            t0 = _time.time_ns()
            for i in range(3):
                aid = _aid()
                event = _make_event(attempt_id=aid, sequence=1, idempotency_key=f"stale-{i}")
                outbox.append_event_with_outbox(
                    aid, event, _make_outbox_payloads([f"topic.{i}"])
                )
            t1 = _time.time_ns()

            # All should be stale relative to t1.
            stale = outbox.get_stale_pending(before_ns=t1, limit=10)
            assert len(stale) == 3

            # None should be stale relative to t0-1.
            stale_before = outbox.get_stale_pending(before_ns=t0 - 1, limit=10)
            assert len(stale_before) == 0

            store.close()
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_stale_pending_excludes_dispatched_and_failed(self):
        """get_stale_pending only returns records with status='pending'."""
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            outbox = SqliteLedgerOutbox(store)

            # Create two records.
            import time as _time
            aid1 = _aid()
            e1 = _make_event(attempt_id=aid1, sequence=1, idempotency_key="stale-1")
            r1 = outbox.append_event_with_outbox(aid1, e1, _make_outbox_payloads(["t1"]))
            outbox.mark_dispatched(r1.outbox_records[0].outbox_id)

            aid2 = _aid()
            e2 = _make_event(attempt_id=aid2, sequence=1, idempotency_key="stale-2")
            r2 = outbox.append_event_with_outbox(aid2, e2, _make_outbox_payloads(["t2"]))
            outbox.mark_failed(r2.outbox_records[0].outbox_id, "error")

            # All non-pending, so stale query returns empty.
            t_now = _time.time_ns()
            stale = outbox.get_stale_pending(before_ns=t_now, limit=10)
            assert len(stale) == 0

            store.close()
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_crash_recovery_re_delivery_cycle(self):
        """Simulate crash: append event with outbox intent, crash before
        delivery, recover via stale-pending, then deliver successfully."""
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            outbox = SqliteLedgerOutbox(store)
            aid = _aid()

            import time as _time

            # Append with outbox intent but DO NOT deliver (simulate crash).
            t0 = _time.time_ns()
            event = _make_event(attempt_id=aid, sequence=1, idempotency_key="crash-recover-1")
            result = outbox.append_event_with_outbox(
                aid, event, _make_outbox_payloads(["effect.recover"])
            )
            ob_id = result.outbox_records[0].outbox_id
            t1 = _time.time_ns()

            # "Crash" — close and reopen (simulate process restart).
            store.close()

            store2 = SqliteAttemptLedgerStore(path)
            outbox2 = SqliteLedgerOutbox(store2)

            # Recovery: detect stale pending records.
            stale = outbox2.get_stale_pending(before_ns=t1, limit=10)
            assert len(stale) == 1
            assert stale[0].outbox_id == ob_id
            assert stale[0].status == OutboxStatus.PENDING.value

            # Re-deliver the stale record.
            outbox2.mark_dispatched(stale[0].outbox_id)
            records = outbox2.get_records_for_attempt(aid)
            assert records[0].status == OutboxStatus.DISPATCHED.value

            # Event is intact.
            assert store2.event_count(aid) == 1

            store2.close()
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_crash_recovery_idempotent_dedup(self):
        """After crash recovery and re-delivery, replaying the same event
        (same idempotency key) does not create duplicate outbox records
        or duplicate events — dedup prevents duplicate accepted effects."""
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            outbox = SqliteLedgerOutbox(store)
            aid = _aid()

            event = _make_event(attempt_id=aid, sequence=1, idempotency_key="crash-dedup-1")
            r1 = outbox.append_event_with_outbox(
                aid, event, _make_outbox_payloads(["effect.dedup"])
            )
            ob_id = r1.outbox_records[0].outbox_id

            # Dispatch the effect.
            outbox.mark_dispatched(ob_id)

            # Simulate crash + re-submit of the same event.
            r2 = outbox.append_event_with_outbox(
                aid, event, _make_outbox_payloads(["effect.dedup-replay"])
            )
            assert r2.is_duplicate is True
            assert len(r2.outbox_records) == 0

            # One event, one outbox record — no duplication.
            assert store.event_count(aid) == 1
            records = outbox.get_records_for_attempt(aid)
            assert len(records) == 1
            assert records[0].status == OutboxStatus.DISPATCHED.value

            store.close()
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_stale_pending_respects_limit(self):
        """get_stale_pending respects the limit parameter."""
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            outbox = SqliteLedgerOutbox(store)

            import time as _time
            for i in range(5):
                aid = _aid()
                event = _make_event(attempt_id=aid, sequence=1, idempotency_key=f"limit-{i}")
                outbox.append_event_with_outbox(
                    aid, event, _make_outbox_payloads([f"topic.{i}"])
                )
            t1 = _time.time_ns()

            stale = outbox.get_stale_pending(before_ns=t1, limit=3)
            assert len(stale) == 3

            store.close()
        finally:
            if os.path.exists(path):
                os.unlink(path)


# ── Reconciliation queries ─────────────────────────────────────────────────


class TestOutboxReconciliation:
    """Prove reconciliation queries provide visibility into outbox state
    without duplicating accepted effects."""

    def test_get_failed_returns_only_failed(self):
        """get_failed returns only FAILED records, ordered by creation."""
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            outbox = SqliteLedgerOutbox(store)

            # Create 3 records, mark 2 as failed.
            for i, fail in enumerate([True, False, True]):
                aid = _aid()
                event = _make_event(attempt_id=aid, sequence=1, idempotency_key=f"f-{i}")
                r = outbox.append_event_with_outbox(
                    aid, event, _make_outbox_payloads([f"topic.{i}"])
                )
                if fail:
                    outbox.mark_failed(r.outbox_records[0].outbox_id, f"reason {i}")

            failed = outbox.get_failed(limit=10)
            assert len(failed) == 2
            assert all(r.status == OutboxStatus.FAILED.value for r in failed)
            # Ordered by created_at_ns.
            assert failed[0].created_at_ns <= failed[1].created_at_ns

            store.close()
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_get_failed_respects_limit(self):
        """get_failed respects the limit parameter."""
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            outbox = SqliteLedgerOutbox(store)

            for i in range(5):
                aid = _aid()
                event = _make_event(attempt_id=aid, sequence=1, idempotency_key=f"fl-{i}")
                r = outbox.append_event_with_outbox(
                    aid, event, _make_outbox_payloads([f"topic.{i}"])
                )
                outbox.mark_failed(r.outbox_records[0].outbox_id, f"err {i}")

            failed = outbox.get_failed(limit=3)
            assert len(failed) == 3

            store.close()
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_get_outbox_summary_all_statuses(self):
        """get_outbox_summary returns correct counts by status."""
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            outbox = SqliteLedgerOutbox(store)
            aid = _aid()

            # Append 3 events with outbox payloads.
            e1 = _make_event(attempt_id=aid, sequence=1, idempotency_key="sum-1")
            r1 = outbox.append_event_with_outbox(aid, e1, _make_outbox_payloads(["t1"]))
            outbox.mark_dispatched(r1.outbox_records[0].outbox_id)

            e2 = _make_event(attempt_id=aid, sequence=2, idempotency_key="sum-2")
            r2 = outbox.append_event_with_outbox(aid, e2, _make_outbox_payloads(["t2"]))
            outbox.mark_failed(r2.outbox_records[0].outbox_id, "reason")

            e3 = _make_event(attempt_id=aid, sequence=3, idempotency_key="sum-3")
            outbox.append_event_with_outbox(aid, e3, _make_outbox_payloads(["t3"]))
            # e3's record stays PENDING.

            summary = outbox.get_outbox_summary(aid)
            assert summary["pending"] == 1
            assert summary["dispatched"] == 1
            assert summary["failed"] == 1
            assert summary["total"] == 3

            store.close()
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_get_outbox_summary_empty_attempt(self):
        """get_outbox_summary returns zeros for an attempt with no records."""
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            outbox = SqliteLedgerOutbox(store)
            aid = _aid()

            summary = outbox.get_outbox_summary(aid)
            assert summary == {"pending": 0, "dispatched": 0, "failed": 0, "total": 0}

            store.close()
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_reconciliation_does_not_duplicate_accepted_effects(self):
        """Reconciliation queries are read-only projections — they never
        create or modify outbox records. Verifying via summary across
        the at-least-once delivery cycle."""
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            outbox = SqliteLedgerOutbox(store)
            aid = _aid()

            # Create event + outbox.
            event = _make_event(attempt_id=aid, sequence=1, idempotency_key="recon-1")
            result = outbox.append_event_with_outbox(
                aid, event, _make_outbox_payloads(["effect.recon"])
            )
            ob_id = result.outbox_records[0].outbox_id

            # Initial state: 1 pending.
            s1 = outbox.get_outbox_summary(aid)
            assert s1 == {"pending": 1, "dispatched": 0, "failed": 0, "total": 1}

            # Fail.
            outbox.mark_failed(ob_id, "transient")
            s2 = outbox.get_outbox_summary(aid)
            assert s2 == {"pending": 0, "dispatched": 0, "failed": 1, "total": 1}

            # Retry.
            outbox.retry_failed(ob_id)
            s3 = outbox.get_outbox_summary(aid)
            assert s3 == {"pending": 1, "dispatched": 0, "failed": 0, "total": 1}

            # Dispatch.
            outbox.mark_dispatched(ob_id)
            s4 = outbox.get_outbox_summary(aid)
            assert s4 == {"pending": 0, "dispatched": 1, "failed": 0, "total": 1}

            # Total is always 1 — no duplicates.
            assert s1["total"] == s2["total"] == s3["total"] == s4["total"] == 1

            store.close()
        finally:
            if os.path.exists(path):
                os.unlink(path)
