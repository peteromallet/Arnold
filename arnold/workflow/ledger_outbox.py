"""Transactional outbox for WBC ledger events.

This module provides the M6A outbox boundary: a durable, append-only record
of delivery-intent side effects created atomically with their parent ledger
events inside the same SQLite transaction.

Key invariants:
* An outbox record is NEVER created without its parent ledger event, and
  a ledger event with outbox intent is NEVER committed without its outbox
  records — both land or neither lands (atomicity).
* Outbox records are append-only projection state. They do not grant
  dispatch authority — they record that delivery MUST eventually happen.
* The outbox table lives in the same SQLite database as the attempt_events
  table and is managed through the same connection for zero-network-cost
  atomic transactions.
"""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

from arnold.workflow.attempt_ledger_store import (
    _TERMINAL_EVENT_TYPE_VALUES,
    AppendResult,
    MonotonicSequenceError,
    PostTerminalAppendError,
    SqliteAttemptLedgerStore,
)
from arnold.workflow.execution_attempt_ledger import (
    AttemptEventType,
    LedgerEvent,
)

# ── Constants ──────────────────────────────────────────────────────────────

#: Maximum number of delivery retries before a record is considered
#: permanently failed. The delivery agent may still manually re-queue
#: records beyond this limit via operator intervention.
MAX_RETRY_COUNT: int = 10

# ── Outbox table DDL ───────────────────────────────────────────────────────

_OUTBOX_TABLE_DDL: str = """\
CREATE TABLE IF NOT EXISTS outbox_records (
    outbox_id              TEXT    PRIMARY KEY,
    attempt_id             TEXT    NOT NULL,
    event_sequence         INTEGER NOT NULL,
    event_idempotency_key  TEXT    NOT NULL,
    destination            TEXT    NOT NULL,
    payload_json           TEXT    NOT NULL,
    status                 TEXT    NOT NULL DEFAULT 'pending',
    created_at_ns          INTEGER NOT NULL,
    dispatched_at_ns       INTEGER,
    failure_count          INTEGER NOT NULL DEFAULT 0,
    last_failure_at_ns     INTEGER,
    last_failure_reason    TEXT
);
"""

_OUTBOX_ATTEMPT_INDEX_DDL: str = """\
CREATE INDEX IF NOT EXISTS idx_outbox_attempt_id
    ON outbox_records(attempt_id, event_sequence);
"""

_OUTBOX_STATUS_INDEX_DDL: str = """\
CREATE INDEX IF NOT EXISTS idx_outbox_status
    ON outbox_records(status, created_at_ns);
"""


# ── Types ──────────────────────────────────────────────────────────────────


class OutboxStatus(Enum):
    """Lifecycle states for an outbox record.

    * ``PENDING`` — created, not yet dispatched. The delivery agent must
      eventually pick this up.
    * ``DISPATCHED`` — successfully delivered. Terminal.
    * ``FAILED`` — delivery attempt(s) failed. The record remains in the
      outbox for retry or operator intervention.
    """

    PENDING = "pending"
    DISPATCHED = "dispatched"
    DELIVERED = "delivered"
    FAILED = "failed"
    TOMBSTONED = "tombstoned"


@dataclass(frozen=True)
class OutboxRecord:
    """A durable record of delivery intent for a ledger event.

    Outbox records are created atomically with their parent ledger event
    and carry the minimum fields needed for at-least-once delivery:
    destination routing, serialized payload, and idempotency tracking
    via the parent event's sequence and idempotency key.
    """

    outbox_id: str
    attempt_id: str
    event_sequence: int
    event_idempotency_key: str
    destination: str
    payload_json: str
    status: str
    created_at_ns: int
    dispatched_at_ns: Optional[int] = None
    failure_count: int = 0
    last_failure_at_ns: Optional[int] = None
    last_failure_reason: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dict for JSON round-tripping."""
        return {
            "outbox_id": self.outbox_id,
            "attempt_id": self.attempt_id,
            "event_sequence": self.event_sequence,
            "event_idempotency_key": self.event_idempotency_key,
            "destination": self.destination,
            "payload_json": self.payload_json,
            "status": self.status,
            "created_at_ns": self.created_at_ns,
            "dispatched_at_ns": self.dispatched_at_ns,
            "failure_count": self.failure_count,
            "last_failure_at_ns": self.last_failure_at_ns,
            "last_failure_reason": self.last_failure_reason,
        }


@dataclass(frozen=True)
class AppendWithOutboxResult:
    """Result of appending a ledger event with outbox records atomically.

    Combines the ``AppendResult`` for the ledger event with the list of
    created :class:`OutboxRecord` instances. When ``is_duplicate`` is
    ``True`` the outbox records are empty — duplicates do not re-create
    outbox records.
    """

    attempt_id: str
    event: LedgerEvent
    sequence: int
    is_duplicate: bool
    outbox_records: tuple[OutboxRecord, ...] = ()


# ── Errors ──────────────────────────────────────────────────────────────────


class RetryLimitExceededError(Exception):
    """Raised when a retry is attempted on a record that has exceeded
    the maximum retry count."""

    def __init__(self, outbox_id: str, failure_count: int, max_retries: int) -> None:
        super().__init__(
            f"Outbox record {outbox_id!r} has {failure_count} failures"
            f" (max {max_retries} retries allowed)"
        )
        self.outbox_id = outbox_id
        self.failure_count = failure_count
        self.max_retries = max_retries


# ── Abstract interface ─────────────────────────────────────────────────────


class LedgerOutbox(ABC):
    """Abstract interface for the transactional outbox.

    Implementations must guarantee that outbox records are created
    atomically with their parent ledger event — both committed or both
    rolled back within the same transaction.
    """

    @abstractmethod
    def append_event_with_outbox(
        self,
        attempt_id: str,
        event: LedgerEvent,
        outbox_payloads: list[dict[str, str]],
    ) -> AppendWithOutboxResult:
        """Append *event* and create outbox records atomically.

        Each entry in *outbox_payloads* must be a dict with at minimum:
        ``{"destination": "<routing-key>", "payload": <any>}``.
        The payload is serialized to JSON for durable storage.

        The event append enforces all Step 4 invariants (monotonic
        sequence, idempotency-key dedup, single terminal, post-terminal
        rejection). Outbox records are ONLY created when the event is
        genuinely new (not a duplicate).

        Returns:
            An :class:`AppendWithOutboxResult` with the persisted event
            and the set of created outbox records. On duplicate the
            outbox records tuple is empty.
        """
        ...

    @abstractmethod
    def mark_dispatched(self, outbox_id: str) -> None:
        """Mark an outbox record as successfully dispatched."""
        ...

    @abstractmethod
    def mark_failed(self, outbox_id: str, reason: str) -> None:
        """Mark an outbox record as failed with a reason.

        Increments ``failure_count`` and records the failure timestamp
        and reason.
        """
        ...

    @abstractmethod
    def retry_failed(
        self,
        outbox_id: str,
        max_retries: int = MAX_RETRY_COUNT,
    ) -> OutboxRecord:
        """Transition a FAILED outbox record back to PENDING for re-delivery.

        Only records with ``status='failed'`` can be retried. The
        *max_retries* parameter bounds how many total failures are
        allowed before the record is considered permanently failed.
        If ``failure_count >= max_retries``, raises
        :class:`RetryLimitExceededError`.

        Returns:
            The updated :class:`OutboxRecord` with ``status='pending'``.
        """
        ...

    @abstractmethod
    def get_pending(self, limit: int = 100) -> list[OutboxRecord]:
        """Return pending outbox records ordered by creation time.

        Only returns records with ``status == 'pending'``. The *limit*
        caps the number of records returned so the delivery agent can
        process work in bounded batches.
        """
        ...

    @abstractmethod
    def get_failed(self, limit: int = 100) -> list[OutboxRecord]:
        """Return failed outbox records ordered by creation time.

        Only returns records with ``status == 'failed'``. Useful for
        monitoring and retry-triggering.
        """
        ...

    @abstractmethod
    def get_stale_pending(
        self,
        before_ns: int,
        limit: int = 100,
    ) -> list[OutboxRecord]:
        """Return pending records older than *before_ns* (nanoseconds).

        Stale pending records indicate a crash or delivery agent
        failure — the event was committed with outbox intent but the
        delivery agent never acknowledged. These records must be
        re-delivered for at-least-once semantics.
        """
        ...

    @abstractmethod
    def get_outbox_summary(
        self, attempt_id: str
    ) -> dict[str, int]:
        """Return a reconciliation summary of outbox record counts by status.

        Returns a dict with keys ``pending``, ``dispatched``, ``failed``
        and the count for each. The ``total`` key holds the sum.
        """
        ...

    @abstractmethod
    def get_records_for_attempt(
        self, attempt_id: str
    ) -> list[OutboxRecord]:
        """Return all outbox records for *attempt_id* ordered by sequence."""
        ...


# ── SQLite implementation ──────────────────────────────────────────────────


class SqliteLedgerOutbox(LedgerOutbox):
    """Transactional outbox backed by the same SQLite database as the
    :class:`SqliteAttemptLedgerStore`.

    Construction takes an already-opened store and creates the outbox
    table on the store's connection. All writes go through the store's
    connection so that the outbox table and the attempt_events table can
    participate in the same ``BEGIN IMMEDIATE`` / ``COMMIT`` transaction.

    Atomicity guarantee:
        ``append_event_with_outbox`` executes inside ONE ``BEGIN IMMEDIATE``
        transaction. The ledger event INSERT and all outbox record INSERTs
        are committed together or rolled back together. A split-brain where
        the event lands but the outbox records do not (or vice versa) is
        impossible by construction.
    """

    def __init__(self, store: SqliteAttemptLedgerStore) -> None:
        self._store = store
        self._conn: sqlite3.Connection = store.conn
        self._init_outbox_schema()

    # ── schema initialization ──────────────────────────────────────────

    def _init_outbox_schema(self) -> None:
        """Create the outbox table and indexes if they do not exist.

        Since the store's connection may already be in use, we execute
        the DDL outside a transaction — ``CREATE TABLE IF NOT EXISTS``
        is idempotent and safe to call multiple times.
        """
        cur = self._conn.cursor()
        for ddl in (_OUTBOX_TABLE_DDL, _OUTBOX_ATTEMPT_INDEX_DDL, _OUTBOX_STATUS_INDEX_DDL):
            for stmt in ddl.split(";"):
                s = stmt.strip()
                if s:
                    cur.execute(s)

    # ── public interface ───────────────────────────────────────────────

    def append_event_with_outbox(
        self,
        attempt_id: str,
        event: LedgerEvent,
        outbox_payloads: list[dict[str, str]],
    ) -> AppendWithOutboxResult:
        """Append *event* and create outbox records in one transaction.

        See :meth:`LedgerOutbox.append_event_with_outbox` for the full contract.

        Atomicity:
            1. ``BEGIN IMMEDIATE``
            2. Idempotency-key dedup check (dedup wins over rejection)
            3. Post-terminal rejection check
            4. Monotonic sequence check
            5. INSERT into ``attempt_events``
            6. For each outbox payload: INSERT into ``outbox_records``
            7. ``COMMIT`` (or ``ROLLBACK`` on any failure)

        If *event* is a duplicate, only steps 1-2 execute and the
        transaction is rolled back before returning the existing event
        with ``is_duplicate=True`` and empty outbox records.
        """
        if event.identity.attempt_id != attempt_id:
            raise ValueError(
                f"Event attempt_id {event.identity.attempt_id!r} "
                f"does not match store attempt_id {attempt_id!r}"
            )

        event_json = json.dumps(event.to_dict(), sort_keys=True, ensure_ascii=False)
        conn = self._conn
        now_ns = time.time_ns()

        self._begin_immediate_retry(conn)
        try:
            cur = conn.cursor()

            # (2) Idempotency-key dedup.
            cur.execute(
                "SELECT event_json FROM attempt_events"
                " WHERE attempt_id = ? AND idempotency_key = ?",
                (attempt_id, event.idempotency_key),
            )
            dup_row = cur.fetchone()
            if dup_row is not None:
                conn.execute("ROLLBACK")
                from arnold.workflow.attempt_ledger_store import (
                    _deserialize_ledger_event,
                )

                existing = _deserialize_ledger_event(json.loads(dup_row[0]))
                return AppendWithOutboxResult(
                    attempt_id=attempt_id,
                    event=existing,
                    sequence=existing.sequence,
                    is_duplicate=True,
                    outbox_records=(),
                )

            # (3) Post-terminal rejection.
            cur.execute(
                f"SELECT 1 FROM attempt_events WHERE attempt_id = ?"
                f" AND event_type IN ({','.join('?' * len(_TERMINAL_EVENT_TYPE_VALUES))})"
                f" LIMIT 1",
                (attempt_id, *_TERMINAL_EVENT_TYPE_VALUES),
            )
            if cur.fetchone() is not None:
                conn.execute("ROLLBACK")
                raise PostTerminalAppendError(
                    f"Attempt {attempt_id!r} already has a terminal event; "
                    f"further appends are rejected"
                    f" (idempotency_key={event.idempotency_key!r})."
                )

            # (4) Monotonic sequence.
            cur.execute(
                "SELECT COALESCE(MAX(sequence), 0) FROM attempt_events"
                " WHERE attempt_id = ?",
                (attempt_id,),
            )
            last_seq_row = cur.fetchone()
            last_seq = int(last_seq_row[0]) if last_seq_row is not None else 0
            if event.sequence <= last_seq:
                conn.execute("ROLLBACK")
                raise MonotonicSequenceError(
                    f"Event sequence {event.sequence} for attempt"
                    f" {attempt_id!r} is not strictly greater than the"
                    f" current max {last_seq}."
                )

            # (5) INSERT event.
            cur.execute(
                """\
INSERT INTO attempt_events
    (attempt_id, sequence, idempotency_key, event_type, event_json, appended_at_ns)
VALUES (?, ?, ?, ?, ?, ?)
""",
                (
                    attempt_id,
                    event.sequence,
                    event.idempotency_key,
                    event.event_type.value,
                    event_json,
                    now_ns,
                ),
            )

            # (6) INSERT outbox records.
            records: list[OutboxRecord] = []
            for payload_spec in outbox_payloads:
                destination = payload_spec["destination"]
                payload = payload_spec["payload"]
                payload_json = json.dumps(payload, sort_keys=True, ensure_ascii=False)
                outbox_id = str(uuid.uuid4())
                cur.execute(
                    """\
INSERT INTO outbox_records
    (outbox_id, attempt_id, event_sequence, event_idempotency_key,
     destination, payload_json, status, created_at_ns)
VALUES (?, ?, ?, ?, ?, ?, ?, ?)
""",
                    (
                        outbox_id,
                        attempt_id,
                        event.sequence,
                        event.idempotency_key,
                        destination,
                        payload_json,
                        OutboxStatus.PENDING.value,
                        now_ns,
                    ),
                )
                records.append(
                    OutboxRecord(
                        outbox_id=outbox_id,
                        attempt_id=attempt_id,
                        event_sequence=event.sequence,
                        event_idempotency_key=event.idempotency_key,
                        destination=destination,
                        payload_json=payload_json,
                        status=OutboxStatus.PENDING.value,
                        created_at_ns=now_ns,
                    )
                )

            # (7) COMMIT — event + outbox records land together.
            conn.execute("COMMIT")
        except (PostTerminalAppendError, MonotonicSequenceError):
            # Transaction already rolled back inside the handler.
            raise
        except Exception:
            try:
                conn.execute("ROLLBACK")
            except Exception:
                pass
            raise

        return AppendWithOutboxResult(
            attempt_id=attempt_id,
            event=event,
            sequence=event.sequence,
            is_duplicate=False,
            outbox_records=tuple(records),
        )

    def mark_dispatched(self, outbox_id: str) -> None:
        """Mark *outbox_id* as dispatched.

        Sets ``status='dispatched'`` and records ``dispatched_at_ns``.
        Idempotent — calling on an already-dispatched record is a no-op
        that updates the timestamp.
        """
        now_ns = time.time_ns()
        cur = self._conn.cursor()
        cur.execute(
            """\
UPDATE outbox_records
SET status = ?, dispatched_at_ns = ?
WHERE outbox_id = ?
""",
            (OutboxStatus.DISPATCHED.value, now_ns, outbox_id),
        )

    def mark_failed(self, outbox_id: str, reason: str) -> None:
        """Mark *outbox_id* as failed.

        Increments ``failure_count`` and records the failure timestamp
        and reason. The record remains ``status='failed'`` for retry or
        operator intervention.
        """
        now_ns = time.time_ns()
        cur = self._conn.cursor()
        cur.execute(
            """\
UPDATE outbox_records
SET status = ?,
    failure_count = failure_count + 1,
    last_failure_at_ns = ?,
    last_failure_reason = ?
WHERE outbox_id = ?
""",
            (OutboxStatus.FAILED.value, now_ns, reason, outbox_id),
        )

    def retry_failed(
        self,
        outbox_id: str,
        max_retries: int = MAX_RETRY_COUNT,
    ) -> OutboxRecord:
        """Transition a FAILED outbox record back to PENDING for re-delivery.

        Only records with ``status='failed'`` can be retried. The
        *max_retries* parameter bounds how many total failures are
        allowed. If ``failure_count >= max_retries``, raises
        :class:`RetryLimitExceededError`.

        The record must exist and be in FAILED state. This method does
        NOT reset ``failure_count`` — the count continues to accumulate
        so the max-retry guard remains effective across retry cycles.
        """
        conn = self._conn
        self._begin_immediate_retry(conn)
        try:
            cur = conn.cursor()
            # Read current state under transaction.
            cur.execute(
                """\
SELECT outbox_id, attempt_id, event_sequence, event_idempotency_key,
       destination, payload_json, status, created_at_ns,
       dispatched_at_ns, failure_count, last_failure_at_ns,
       last_failure_reason
FROM outbox_records
WHERE outbox_id = ?
""",
                (outbox_id,),
            )
            row = cur.fetchone()
            if row is None:
                conn.execute("ROLLBACK")
                raise ValueError(
                    f"Outbox record {outbox_id!r} not found"
                )

            record = _row_to_outbox_record(row)

            if record.status != OutboxStatus.FAILED.value:
                conn.execute("ROLLBACK")
                raise ValueError(
                    f"Outbox record {outbox_id!r} has status"
                    f" {record.status!r}, expected 'failed'"
                )

            if record.failure_count >= max_retries:
                conn.execute("ROLLBACK")
                raise RetryLimitExceededError(
                    outbox_id, record.failure_count, max_retries
                )

            # Transition back to PENDING.
            cur.execute(
                """\
UPDATE outbox_records
SET status = ?
WHERE outbox_id = ?
""",
                (OutboxStatus.PENDING.value, outbox_id),
            )

            conn.execute("COMMIT")
        except (ValueError, RetryLimitExceededError):
            # Transaction already rolled back.
            raise
        except Exception:
            try:
                conn.execute("ROLLBACK")
            except Exception:
                pass
            raise

        # Return updated record.
        return self._get_record_by_id(outbox_id)

    def get_pending(self, limit: int = 100) -> list[OutboxRecord]:
        """Return up to *limit* pending outbox records ordered by creation."""
        cur = self._conn.cursor()
        cur.execute(
            """\
SELECT outbox_id, attempt_id, event_sequence, event_idempotency_key,
       destination, payload_json, status, created_at_ns,
       dispatched_at_ns, failure_count, last_failure_at_ns,
       last_failure_reason
FROM outbox_records
WHERE status = ?
ORDER BY created_at_ns ASC
LIMIT ?
""",
            (OutboxStatus.PENDING.value, limit),
        )
        return [_row_to_outbox_record(row) for row in cur.fetchall()]

    def get_failed(self, limit: int = 100) -> list[OutboxRecord]:
        """Return up to *limit* failed outbox records ordered by creation."""
        cur = self._conn.cursor()
        cur.execute(
            """\
SELECT outbox_id, attempt_id, event_sequence, event_idempotency_key,
       destination, payload_json, status, created_at_ns,
       dispatched_at_ns, failure_count, last_failure_at_ns,
       last_failure_reason
FROM outbox_records
WHERE status = ?
ORDER BY created_at_ns ASC
LIMIT ?
""",
            (OutboxStatus.FAILED.value, limit),
        )
        return [_row_to_outbox_record(row) for row in cur.fetchall()]

    def get_stale_pending(
        self,
        before_ns: int,
        limit: int = 100,
    ) -> list[OutboxRecord]:
        """Return pending records created before *before_ns*.

        These records represent outbox intent that was never delivered
        — typically because the delivery agent crashed after the event
        was committed. They must be re-delivered for at-least-once
        semantics.
        """
        cur = self._conn.cursor()
        cur.execute(
            """\
SELECT outbox_id, attempt_id, event_sequence, event_idempotency_key,
       destination, payload_json, status, created_at_ns,
       dispatched_at_ns, failure_count, last_failure_at_ns,
       last_failure_reason
FROM outbox_records
WHERE status = ? AND created_at_ns < ?
ORDER BY created_at_ns ASC
LIMIT ?
""",
            (OutboxStatus.PENDING.value, before_ns, limit),
        )
        return [_row_to_outbox_record(row) for row in cur.fetchall()]

    def get_outbox_summary(
        self, attempt_id: str
    ) -> dict[str, int]:
        """Return a reconciliation summary of outbox record counts by status.

        Returns a dict with keys ``pending``, ``dispatched``, ``failed``
        and the count for each. The ``total`` key holds the sum.
        """
        cur = self._conn.cursor()
        cur.execute(
            """\
SELECT status, COUNT(1)
FROM outbox_records
WHERE attempt_id = ?
GROUP BY status
""",
            (attempt_id,),
        )
        counts: dict[str, int] = {
            "pending": 0,
            "dispatched": 0,
            "failed": 0,
            "total": 0,
        }
        for status, cnt in cur.fetchall():
            counts[status] = cnt
            counts["total"] += cnt
        return counts

    def get_records_for_attempt(
        self, attempt_id: str
    ) -> list[OutboxRecord]:
        """Return all outbox records for *attempt_id* ordered by sequence."""
        cur = self._conn.cursor()
        cur.execute(
            """\
SELECT outbox_id, attempt_id, event_sequence, event_idempotency_key,
       destination, payload_json, status, created_at_ns,
       dispatched_at_ns, failure_count, last_failure_at_ns,
       last_failure_reason
FROM outbox_records
WHERE attempt_id = ?
ORDER BY event_sequence ASC, created_at_ns ASC
""",
            (attempt_id,),
        )
        return [_row_to_outbox_record(row) for row in cur.fetchall()]

    # ── internal helpers ───────────────────────────────────────────────

    def _get_record_by_id(self, outbox_id: str) -> OutboxRecord:
        """Fetch a single outbox record by its primary key."""
        cur = self._conn.cursor()
        cur.execute(
            """\
SELECT outbox_id, attempt_id, event_sequence, event_idempotency_key,
       destination, payload_json, status, created_at_ns,
       dispatched_at_ns, failure_count, last_failure_at_ns,
       last_failure_reason
FROM outbox_records
WHERE outbox_id = ?
""",
            (outbox_id,),
        )
        row = cur.fetchone()
        if row is None:
            raise ValueError(
                f"Outbox record {outbox_id!r} not found"
            )
        return _row_to_outbox_record(row)

    @staticmethod
    def _begin_immediate_retry(conn: sqlite3.Connection) -> None:
        """Execute ``BEGIN IMMEDIATE`` with busy-retry.

        Mirrors the store's ``_begin_immediate_retry`` for separate-process
        contention safety.
        """
        max_attempts = 30
        base_delay = 0.01
        for attempt in range(max_attempts):
            try:
                conn.execute("BEGIN IMMEDIATE")
                return
            except sqlite3.OperationalError as exc:
                if "locked" in str(exc).lower() and attempt < max_attempts - 1:
                    delay = min(base_delay * (2 ** attempt), 1.0)
                    time.sleep(delay)
                    continue
                raise


def _row_to_outbox_record(row: tuple[Any, ...]) -> OutboxRecord:
    """Convert a SQLite row tuple to an :class:`OutboxRecord`."""
    return OutboxRecord(
        outbox_id=row[0],
        attempt_id=row[1],
        event_sequence=row[2],
        event_idempotency_key=row[3],
        destination=row[4],
        payload_json=row[5],
        status=row[6],
        created_at_ns=row[7],
        dispatched_at_ns=row[8],
        failure_count=row[9],
        last_failure_at_ns=row[10],
        last_failure_reason=row[11],
    )


# M9 adds a small file-backed payload-publication outbox alongside the
# transactional M6 outbox.  Keep the established M6 API intact and expose the
# additive implementation under distinct type names.
from arnold.workflow._ledger_outbox_m9 import (  # noqa: E402
    FileBackedLedgerOutbox,
    LEDGER_OUTBOX_SCHEMA_VERSION,
    LedgerOutboxRecord,
)


# ── Public API surface ─────────────────────────────────────────────────────

__all__ = [
    "AppendWithOutboxResult",
    "FileBackedLedgerOutbox",
    "LEDGER_OUTBOX_SCHEMA_VERSION",
    "LedgerOutbox",
    "LedgerOutboxRecord",
    "MAX_RETRY_COUNT",
    "OutboxRecord",
    "OutboxStatus",
    "RetryLimitExceededError",
    "SqliteLedgerOutbox",
]
