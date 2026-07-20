"""Durable SQLite-backed store for ``ExecutionAttemptLedger`` event streams.

This module provides the M6A transactional store boundary for WBC ledger
events. It does NOT modify the ``ExecutionAttemptLedger`` schema — it reads
and writes the same frozen dataclasses via their existing ``to_dict()``
serialization contract.

Key invariants:
* SQLite WAL mode for concurrent readers and atomic writes.
* Contract-version binding to ``LEDGER_SCHEMA_VERSION`` in metadata.
* Durable serialization uses ``LedgerEvent.to_dict()`` and json.
* Readback reconstructs ``LedgerEvent`` and ``ExecutionAttemptLedger``
  without mutating schema fields.

Step 4 transactional append invariants (enforced inside ONE SQLite
``BEGIN IMMEDIATE`` transaction per append):

* **Monotonic sequence** — an appended event's ``sequence`` must be
  strictly greater than the largest persisted sequence for the same
  ``attempt_id``. A regression raises :class:`MonotonicSequenceError`.
* **Idempotency-key uniqueness with dedup** — appending an event whose
  ``(attempt_id, idempotency_key)`` already exists does not raise; the
  store returns the existing persisted event with ``is_duplicate=True``.
  Two different events with the same idempotency key can never coexist.
* **Exactly one terminal event** — once a terminal event
  (``completed``/``failed``/``cancelled``) is persisted for an attempt,
  any further append with a new idempotency key raises
  :class:`PostTerminalAppendError`. A second terminal therefore cannot
  land, and neither can any post-terminal non-terminal event.
* **Dedup wins over rejection** — when a duplicate idempotency key is
  presented, the existing event is returned even if the attempt has
  since reached a terminal state. Retries of the same logical append
  are therefore safe and observable.
"""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Optional

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

# ── Store metadata constants ──────────────────────────────────────────────

_STORE_VERSION: str = "arnold.workflow.attempt_ledger_store.v1"
_METADATA_TABLE_DDL: str = """\
CREATE TABLE IF NOT EXISTS _store_metadata (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

_EVENTS_TABLE_DDL: str = """\
CREATE TABLE IF NOT EXISTS attempt_events (
    attempt_id         TEXT    NOT NULL,
    sequence           INTEGER NOT NULL,
    idempotency_key    TEXT    NOT NULL,
    event_type         TEXT    NOT NULL,
    event_json         TEXT    NOT NULL,
    appended_at_ns     INTEGER NOT NULL,
    PRIMARY KEY (attempt_id, sequence)
);
"""

_EVENTS_IDEMPOTENCY_INDEX_DDL: str = """\
CREATE UNIQUE INDEX IF NOT EXISTS idx_attempt_events_idempotency
    ON attempt_events(attempt_id, idempotency_key);
"""

# Reservations are coordination state, not authority. They record that a
# caller has declared intent to start (or has already started) an attempt
# stream. They never mint completion, dispatch, or authority decisions.
_RESERVATIONS_TABLE_DDL: str = """\
CREATE TABLE IF NOT EXISTS attempt_reservations (
    attempt_id         TEXT    PRIMARY KEY,
    first_reserved_ns  INTEGER NOT NULL,
    last_reserved_ns   INTEGER NOT NULL,
    reservation_count  INTEGER NOT NULL DEFAULT 1
);
"""

# ── Diagnostic tables (Step 8) ────────────────────────────────────────────
#
# These tables persist ``PersistenceFailureDiagnostic`` and
# ``ReconciliationDiagnostic`` payloads as evidence, not authority.
# They are joinable to the event stream via ``attempt_id`` but never
# grant append or completion power — they are observable projections
# that the store records when persistence operations fail or are
# reconciled.
#
# Source-cursor tracking records where the source system has observed
# the attempt stream up to, enabling gap detection and reconciliation
# resumption without requiring re-scan of the full event history.

_PERSISTENCE_FAILURE_DIAGNOSTICS_TABLE_DDL: str = """\
CREATE TABLE IF NOT EXISTS persistence_failure_diagnostics (
    attempt_id              TEXT    NOT NULL,
    diagnostic_id           TEXT    NOT NULL PRIMARY KEY,
    target_event_sequence   INTEGER NOT NULL,
    failure_mode            TEXT    NOT NULL,
    observed_error          TEXT    NOT NULL,
    diagnostic_json         TEXT    NOT NULL,
    recorded_at_ns          INTEGER NOT NULL
);
"""

_RECONCILIATION_DIAGNOSTICS_TABLE_DDL: str = """\
CREATE TABLE IF NOT EXISTS reconciliation_diagnostics (
    attempt_id                   TEXT    NOT NULL,
    diagnostic_id                TEXT    NOT NULL PRIMARY KEY,
    reconciled_event_sequence    INTEGER NOT NULL,
    outcome                      TEXT    NOT NULL,
    outcome_detail               TEXT    NOT NULL,
    diagnostic_json              TEXT    NOT NULL,
    recorded_at_ns               INTEGER NOT NULL
);
"""

_SOURCE_CURSORS_TABLE_DDL: str = """\
CREATE TABLE IF NOT EXISTS source_cursors (
    attempt_id    TEXT    NOT NULL,
    cursor_key    TEXT    NOT NULL DEFAULT 'default',
    last_sequence INTEGER NOT NULL DEFAULT 0,
    last_position TEXT,
    updated_at_ns INTEGER NOT NULL,
    PRIMARY KEY (attempt_id, cursor_key)
);
"""

# String literal set of terminal event types. Mirrors the schema-private
# ``_TERMINAL_EVENT_TYPES`` frozenset (COMPLETED/FAILED/CANCELLED) but is
# kept as SQL string literals so it is fully self-contained in DML.
_TERMINAL_EVENT_TYPE_VALUES: tuple[str, ...] = (
    AttemptEventType.COMPLETED.value,
    AttemptEventType.FAILED.value,
    AttemptEventType.CANCELLED.value,
)


# ── Typed errors ──────────────────────────────────────────────────────────


class AttemptLedgerError(Exception):
    """Base class for typed attempt-ledger store errors.

    All store-generated invariant violations derive from this class so
    callers can distinguish store policy enforcement from generic
    ``sqlite3`` errors or schema ``ValueError`` raises.
    """


class MonotonicSequenceError(AttemptLedgerError):
    """Raised when an appended event violates strict sequence monotonicity.

    The appended event's ``sequence`` must be greater than the highest
    sequence already persisted for the same ``attempt_id``.
    """


class PostTerminalAppendError(AttemptLedgerError):
    """Raised when any append is attempted after a terminal event.

    Covers both second-terminal attempts and post-terminal non-terminal
    events. The single terminal event is final.
    """


# ── Gate types (Step 5: durable start and terminal verification) ───────────


class GateStatus(Enum):
    """Outcome of a durable gate verification.

    Gates never return optimistic defaults — they require durable evidence
    and fail closed when evidence is missing, ambiguous, or contradictory.
    """

    VERIFIED = "verified"
    """Durable evidence confirms the gate condition — a matching event exists
    and its persisted fields are coherent."""

    INCOMPLETE = "incomplete"
    """The gate condition has not been met — no matching event is present
    in the durable store. This is a normal non-terminal state, not a failure."""

    INDETERMINATE = "indeterminate"
    """Persistence is ambiguous — the store may have a matching row but its
    content cannot be verified (corrupt JSON, unexpected schema, etc.), or
    the query itself could not be completed. Callers must not treat this as
    success or as a definitive empty result."""

    INCOHERENT = "incoherent"
    """Durable evidence contradicts the gate's contract — for example,
    multiple events of a type that should appear at most once. This indicates
    a store invariant violation or bypass and must be surfaced, never
    silently resolved."""


@dataclass(frozen=True)
class StartGateResult:
    """Result of ``start_verified`` — a durable gate on the STARTED event.

    This is a non-authoritative projection. It does not grant dispatch or
    completion power — it only reports whether durable evidence for the
    STARTED event exists and is coherent.

    When ``status`` is ``VERIFIED``, ``started_event`` carries the
    deserialized and type-checked STARTED event. For all other statuses,
    ``started_event`` is ``None`` and ``evidence`` describes the reason.
    """

    attempt_id: str
    status: GateStatus
    started_event: Optional[LedgerEvent]
    evidence: str


@dataclass(frozen=True)
class TerminalGateResult:
    """Result of ``terminal_or_indeterminate_verified`` — a durable gate on
    the terminal event.

    This is a non-authoritative projection. It does not grant completion or
    dispatch power — it only reports whether durable evidence for a terminal
    event exists and is coherent.

    When ``status`` is ``VERIFIED``, ``terminal_event`` carries the
    deserialized and type-checked terminal event (COMPLETED, FAILED, or
    CANCELLED). For ``INCOMPLETE`` the attempt is still in-flight.
    ``INDETERMINATE`` and ``INCOHERENT`` signal that the durable store
    cannot be trusted for this attempt and the caller must not proceed.
    """

    attempt_id: str
    status: GateStatus
    terminal_event: Optional[LedgerEvent]
    evidence: str


# ── Result types ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class AttemptReservation:
    """Result of reserving an attempt_id in the durable store.

    Captures the post-reservation observable state so callers can decide
    whether to proceed with ``append_started`` or short-circuit. This is
    evidence/projection only — it does not grant authority, dispatch, or
    completion.
    """

    attempt_id: str
    is_new: bool
    event_count: int
    last_sequence: int
    has_terminal: bool
    first_reserved_ns: int
    last_reserved_ns: int
    reservation_count: int


@dataclass(frozen=True)
class AppendResult:
    """Result of an append operation.

    ``event`` is the persisted event (the existing one when
    ``is_duplicate`` is True) so callers always see what is durable.
    """

    attempt_id: str
    event: LedgerEvent
    sequence: int
    is_duplicate: bool


# ── Diagnostic result types (Step 8) ───────────────────────────────────────


@dataclass(frozen=True)
class GapEntry:
    """A detected gap in the event sequence for an attempt.

    This is evidence only — it does not grant authority, dispatch, or
    completion.  Gaps are derived from comparing persisted ``sequence``
    values against the expected monotonic range.
    """

    attempt_id: str
    gap_start: int
    """The highest persisted sequence before the gap (0 if gap starts at 1)."""

    gap_end: int
    """The lowest persisted sequence after the gap (exclusive bound)."""

    missing_count: int
    """Number of sequences missing in this gap (``gap_end - gap_start - 1``)."""


@dataclass(frozen=True)
class SourceCursor:
    """A source cursor tracking observed upstream progress for an attempt.

    The cursor records where the source system has observed the event
    stream up to.  It is evidence, not authority — it does not grant
    append or completion power.  Callers use it to detect gaps, resume
    reconciliation, or determine whether the source has observed a
    terminal event.
    """

    attempt_id: str
    cursor_key: str
    last_sequence: int
    last_position: str | None
    updated_at_ns: int


# ── Public API ─────────────────────────────────────────────────────────────


class AttemptLedgerStore(ABC):
    """Abstract interface for durable attempt-ledger storage.

    Implementations must bind to the pinned ``LEDGER_SCHEMA_VERSION`` and
    round-trip ``LedgerEvent`` / ``ExecutionAttemptLedger`` without mutating
    any frozen dataclasses.

    Step 4 transactional semantics:

    * ``reserve_attempt`` is a coordination primitive. It does NOT mint
      authority, dispatch, or completion — it records intent and returns
      the current observable event state so callers can decide whether to
      proceed.
    * ``append_event`` is the authoritative append. It returns an
      :class:`AppendResult`. The result's ``is_duplicate`` flag is ``True``
      and ``event`` is the existing persisted event when an event with the
      same ``(attempt_id, idempotency_key)`` is already present. Otherwise
      the event is appended and ``is_duplicate`` is ``False``.
    * The four Step 4 invariants — monotonic sequence, idempotency-key
      uniqueness, exactly one terminal, and post-terminal rejection — are
      enforced inside a single transaction per append. Dedup is checked
      before any rejection, so a duplicate of an event that has since
      become post-terminal still returns the existing event rather than
      raising.
    """

    @abstractmethod
    def initialize_attempt(self, attempt_id: str) -> None:
        """Prepare durable storage for *attempt_id*.

        Must be idempotent — safe to call more than once per attempt.
        """
        ...

    @abstractmethod
    def reserve_attempt(self, attempt_id: str) -> AttemptReservation:
        """Reserve *attempt_id* and return its current observable state.

        Idempotent. Repeated calls for the same ``attempt_id`` increment
        ``reservation_count`` and refresh ``last_reserved_ns`` but never
        raise for normal re-reservation.

        The returned :class:`AttemptReservation` is a non-authoritative
        projection of the current event stream (count, last sequence,
        has-terminal). It carries no grant, dispatch, or completion power.
        """
        ...

    @abstractmethod
    def append_event(
        self, attempt_id: str, event: LedgerEvent
    ) -> AppendResult:
        """Append *event* to the durable event stream.

        Enforces, inside a single SQLite transaction:

        * ``event.identity.attempt_id == attempt_id`` (else ``ValueError``);
        * monotonic sequence — ``event.sequence`` must be strictly greater
          than the largest persisted sequence for *attempt_id*
          (else :class:`MonotonicSequenceError`);
        * exactly one terminal event — once a terminal event is persisted,
          any further append with a new idempotency key raises
          :class:`PostTerminalAppendError`;
        * idempotency-key dedup — if ``(attempt_id, idempotency_key)``
          already exists, returns the existing event with
          ``is_duplicate=True`` and does NOT raise, even when the attempt
          is already terminal (dedup wins over post-terminal rejection).

        Returns:
            AppendResult whose ``event`` is the persisted event (the
            existing one when ``is_duplicate`` is True).
        """
        ...

    @abstractmethod
    def append_started(
        self, attempt_id: str, event: LedgerEvent
    ) -> AppendResult:
        """Append a ``STARTED`` event via :meth:`append_event`.

        Validates ``event.event_type == AttemptEventType.STARTED`` before
        delegating, then enforces all Step 4 transactional invariants.
        """
        ...

    @abstractmethod
    def append_completed(
        self, attempt_id: str, event: LedgerEvent
    ) -> AppendResult:
        """Append a ``COMPLETED`` event via :meth:`append_event`.

        Validates ``event.event_type == AttemptEventType.COMPLETED`` before
        delegating. Post-terminal rejection applies — a second terminal
        raises :class:`PostTerminalAppendError`.
        """
        ...

    @abstractmethod
    def append_failed(
        self, attempt_id: str, event: LedgerEvent
    ) -> AppendResult:
        """Append a ``FAILED`` event via :meth:`append_event`.

        Validates ``event.event_type == AttemptEventType.FAILED`` before
        delegating. Post-terminal rejection applies.
        """
        ...

    @abstractmethod
    def append_cancelled(
        self, attempt_id: str, event: LedgerEvent
    ) -> AppendResult:
        """Append a ``CANCELLED`` event via :meth:`append_event`.

        Validates ``event.event_type == AttemptEventType.CANCELLED`` before
        delegating. Post-terminal rejection applies.
        """
        ...

    @abstractmethod
    def read_events(
        self, attempt_id: str
    ) -> list[LedgerEvent]:
        """Return all events for *attempt_id* in append order (`sequence`)."""
        ...

    @abstractmethod
    def read_ledger(
        self, attempt_id: str
    ) -> ExecutionAttemptLedger:
        """Return a fully reconstructed ``ExecutionAttemptLedger``.

        The returned ledger carries the pinned ``ledger_schema_version``.
        """
        ...

    @abstractmethod
    def event_count(self, attempt_id: str) -> int:
        """Return the number of persisted events for *attempt_id*."""
        ...

    @abstractmethod
    def has_terminal_event(self, attempt_id: str) -> bool:
        """Return ``True`` when a terminal event exists for *attempt_id*."""
        ...

    @abstractmethod
    def last_sequence(self, attempt_id: str) -> int:
        """Return the highest persisted sequence number (0 if empty)."""
        ...

    @abstractmethod
    def get_reservation(
        self, attempt_id: str
    ) -> Optional[AttemptReservation]:
        """Return the current :class:`AttemptReservation` or ``None``.

        Does not reserve. Returns the persisted reservation projection
        without bumping ``reservation_count``.
        """
        ...

    @abstractmethod
    def get_terminal_event(
        self, attempt_id: str
    ) -> Optional[LedgerEvent]:
        """Return the single terminal event for *attempt_id*, if any.

        Returns ``None`` if no terminal event has been persisted.
        """
        ...

    # ── Step 8: diagnostic persistence and queries ──────────────────────

    @abstractmethod
    def record_persistence_failure_diagnostic(
        self, attempt_id: str, diagnostic: Any
    ) -> None:
        """Persist a :class:`PersistenceFailureDiagnostic` as evidence.

        The diagnostic is stored alongside the event stream and is
        joinable via ``attempt_id``.  It does NOT grant append or
        completion authority — it is observable evidence only.

        Raises:
            ValueError: if *diagnostic* is not a
                ``PersistenceFailureDiagnostic``.

        """
        ...

    @abstractmethod
    def record_reconciliation_diagnostic(
        self, attempt_id: str, diagnostic: Any
    ) -> None:
        """Persist a :class:`ReconciliationDiagnostic` as evidence.

        The diagnostic is stored alongside the event stream and is
        joinable via ``attempt_id``.  It does NOT grant append or
        completion authority.

        Raises:
            ValueError: if *diagnostic* is not a
                ``ReconciliationDiagnostic``.

        """
        ...

    @abstractmethod
    def query_gaps(self, attempt_id: str) -> list[GapEntry]:
        """Return sequence gaps in the persisted event stream.

        Gaps are detected by comparing persisted ``sequence`` values
        against the expected monotonic range [1, max_sequence].  Each
        :class:`GapEntry` describes one contiguous range of missing
        sequences.  An empty list means no gaps exist.

        This is evidence only — it does not grant authority.
        """
        ...

    @abstractmethod
    def query_persistence_diagnostics(
        self, attempt_id: str
    ) -> list[Any]:
        """Return all :class:`PersistenceFailureDiagnostic` records for
        *attempt_id*, ordered by ``recorded_at_ns``.

        Returns an empty list when no diagnostics have been recorded.
        """
        ...

    @abstractmethod
    def query_reconciliation_state(
        self, attempt_id: str
    ) -> list[Any]:
        """Return all :class:`ReconciliationDiagnostic` records for
        *attempt_id*, ordered by ``recorded_at_ns``.

        Returns an empty list when no reconciliation has been recorded.
        """
        ...

    @abstractmethod
    def query_source_cursor(
        self, attempt_id: str, cursor_key: str = "default"
    ) -> Optional[SourceCursor]:
        """Return the source cursor position for *attempt_id*.

        Returns ``None`` when no cursor has been recorded for the
        given ``cursor_key``.  The cursor is evidence only — it does
        not grant append or completion authority.
        """
        ...

    @abstractmethod
    def update_source_cursor(
        self,
        attempt_id: str,
        last_sequence: int,
        cursor_key: str = "default",
        last_position: str | None = None,
    ) -> SourceCursor:
        """Record (or update) the source cursor position for *attempt_id*.

        Returns the :class:`SourceCursor` as persisted.  The cursor is
        evidence only.
        """
        ...

    # ── Step 5: durable gates ──────────────────────────────────────────

    def start_verified(self, attempt_id: str) -> StartGateResult:
        """Verify that a STARTED event is durably persisted for *attempt_id*.

        This is a **durable gate** — it reads the persisted event stream and
        returns a typed :class:`StartGateResult`. It never returns an
        optimistic default:

        * ``VERIFIED`` — exactly one STARTED event exists and its deserialized
          ``event_type`` matches ``AttemptEventType.STARTED``.
        * ``INCOMPLETE`` — no STARTED event has been persisted yet. The attempt
          may still be in-flight (or may never have been started).
        * ``INDETERMINATE`` — the store has rows that *might* be a STARTED
          event but the evidence is ambiguous (corrupt JSON, unexpected
          event type after deserialization, or a query error).
        * ``INCOHERENT`` — multiple STARTED events exist for the same
          attempt, violating the ledger contract.

        The default implementation delegates to :meth:`read_events`.
        Subclasses may override for efficiency (e.g. a targeted SQL query).
        """
        try:
            events = self.read_events(attempt_id)
        except Exception as exc:
            return StartGateResult(
                attempt_id=attempt_id,
                status=GateStatus.INDETERMINATE,
                started_event=None,
                evidence=f"Failed to read events: {exc}",
            )

        started_events = [
            e for e in events if e.event_type == AttemptEventType.STARTED
        ]

        if len(started_events) == 0:
            return StartGateResult(
                attempt_id=attempt_id,
                status=GateStatus.INCOMPLETE,
                started_event=None,
                evidence="No STARTED event found in durable store.",
            )
        elif len(started_events) == 1:
            return StartGateResult(
                attempt_id=attempt_id,
                status=GateStatus.VERIFIED,
                started_event=started_events[0],
                evidence="Exactly one STARTED event verified in durable store.",
            )
        else:
            return StartGateResult(
                attempt_id=attempt_id,
                status=GateStatus.INCOHERENT,
                started_event=None,
                evidence=(
                    f"Found {len(started_events)} STARTED events; "
                    f"expected at most one."
                ),
            )

    def terminal_or_indeterminate_verified(
        self, attempt_id: str
    ) -> TerminalGateResult:
        """Verify whether a terminal event is durably persisted for *attempt_id*.

        This is a **durable gate** that reads the persisted event stream and
        returns a typed :class:`TerminalGateResult`. It never returns an
        optimistic default:

        * ``VERIFIED`` — exactly one terminal event (COMPLETED, FAILED, or
          CANCELLED) exists and its deserialized ``event_type`` is confirmed
          as terminal.
        * ``INCOMPLETE`` — no terminal event has been persisted yet. The
          attempt is still in-flight.
        * ``INDETERMINATE`` — the store has rows that *might* be terminal but
          the evidence is ambiguous (corrupt JSON, unexpected event type, or
          a query error).
        * ``INCOHERENT`` — multiple terminal events exist for the same
          attempt, violating the single-terminal invariant.

        The default implementation delegates to :meth:`read_events`.
        Subclasses may override for efficiency.
        """
        _TERMINAL = frozenset({
            AttemptEventType.COMPLETED,
            AttemptEventType.FAILED,
            AttemptEventType.CANCELLED,
        })

        try:
            events = self.read_events(attempt_id)
        except Exception as exc:
            return TerminalGateResult(
                attempt_id=attempt_id,
                status=GateStatus.INDETERMINATE,
                terminal_event=None,
                evidence=f"Failed to read events: {exc}",
            )

        terminal_events = [e for e in events if e.event_type in _TERMINAL]

        if len(terminal_events) == 0:
            return TerminalGateResult(
                attempt_id=attempt_id,
                status=GateStatus.INCOMPLETE,
                terminal_event=None,
                evidence="No terminal event found in durable store.",
            )
        elif len(terminal_events) == 1:
            return TerminalGateResult(
                attempt_id=attempt_id,
                status=GateStatus.VERIFIED,
                terminal_event=terminal_events[0],
                evidence="Exactly one terminal event verified in durable store.",
            )
        else:
            return TerminalGateResult(
                attempt_id=attempt_id,
                status=GateStatus.INCOHERENT,
                terminal_event=None,
                evidence=(
                    f"Found {len(terminal_events)} terminal events; "
                    f"expected at most one."
                ),
            )


# ── SQLite implementation ──────────────────────────────────────────────────


class SqliteAttemptLedgerStore(AttemptLedgerStore):
    """Durable ``AttemptLedgerStore`` backed by a local SQLite database.

    * WAL mode is enabled on open for concurrent readers + single writer.
    * Each ``LedgerEvent`` is serialized via ``event.to_dict()``, stored as
      JSON text, and deserialized back into frozen dataclass instances.
    * The store metadata table captures the pinned contract version
      (``LEDGER_SCHEMA_VERSION``) so readers can detect drift.
    """

    def __init__(self, db_path: str | Path) -> None:
        db_path = Path(db_path) if isinstance(db_path, str) else db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)

        self._db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        self._contract_version: str = LEDGER_SCHEMA_VERSION

    # ── connection management ──────────────────────────────────────────

    @property
    def conn(self) -> sqlite3.Connection:
        """Lazily open + initialize the database connection.

        The connection uses ``isolation_level=None`` (autocommit) so that
        Step 4 transactional appends can issue an explicit ``BEGIN
        IMMEDIATE`` and guarantee atomic all-or-nothing enforcement of
        monotonic-sequence, idempotency-dedup, single-terminal, and
        post-terminal-rejection invariants within ONE transaction.
        """
        if self._conn is None:
            self._conn = sqlite3.connect(
                str(self._db_path),
                check_same_thread=False,
                timeout=10.0,
                isolation_level=None,  # explicit BEGIN IMMEDIATE control
            )
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=OFF")
            self._init_schema()
        return self._conn

    def close(self) -> None:
        """Close the underlying SQLite connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    # ── schema initialization ──────────────────────────────────────────

    def _init_schema(self) -> None:
        """Create tables and write metadata if first open.

        All schema statements are issued inside one ``BEGIN IMMEDIATE``
        transaction so the store's tables either all exist or none do.
        We use individual ``execute()`` calls (not ``executescript``)
        because ``executescript`` issues an implicit ``COMMIT`` before
        executing, which would defeat the surrounding transaction.

        Retry-on-busy: when multiple processes race to open the database
        for the first time, ``BEGIN IMMEDIATE`` may encounter
        ``SQLITE_BUSY``.  We retry with exponential backoff (capped at
        the connection's busy timeout) so the store is safe to open
        concurrently from independent processes.
        """
        max_attempts = 20
        base_delay = 0.05  # 50 ms
        conn = self._conn  # type: ignore[union-attr]

        for attempt in range(max_attempts):
            try:
                conn.execute("BEGIN IMMEDIATE")
                break
            except sqlite3.OperationalError as exc:
                if "locked" in str(exc).lower() and attempt < max_attempts - 1:
                    delay = min(base_delay * (2 ** attempt), 2.0)
                    time.sleep(delay)
                    continue
                raise

        try:
            cur = conn.cursor()
            # Individual execute() calls (NOT executescript, which COMMITs
            # first and would escape our BEGIN IMMEDIATE).
            for ddl in (
                _METADATA_TABLE_DDL,
                _EVENTS_TABLE_DDL,
                _EVENTS_IDEMPOTENCY_INDEX_DDL,
                _RESERVATIONS_TABLE_DDL,
                _PERSISTENCE_FAILURE_DIAGNOSTICS_TABLE_DDL,
                _RECONCILIATION_DIAGNOSTICS_TABLE_DDL,
                _SOURCE_CURSORS_TABLE_DDL,
            ):
                for stmt in ddl.split(";"):
                    s = stmt.strip()
                    if s:
                        cur.execute(s)

            # Ensure metadata is populated.
            cur.execute("SELECT value FROM _store_metadata WHERE key = 'store_version'")
            row = cur.fetchone()
            if row is None:
                cur.execute(
                    "INSERT INTO _store_metadata (key, value) VALUES (?, ?)",
                    ("store_version", _STORE_VERSION),
                )
            cur.execute(
                "SELECT value FROM _store_metadata WHERE key = 'contract_version'"
            )
            row = cur.fetchone()
            if row is None:
                cur.execute(
                    "INSERT INTO _store_metadata (key, value) VALUES (?, ?)",
                    ("contract_version", self._contract_version),
                )
            cur.execute(
                "SELECT value FROM _store_metadata WHERE key = 'created_at_ns'"
            )
            row = cur.fetchone()
            if row is None:
                cur.execute(
                    "INSERT INTO _store_metadata (key, value) VALUES (?, ?)",
                    ("created_at_ns", str(time.time_ns())),
                )
            conn.execute("COMMIT")
        except Exception:
            try:
                conn.execute("ROLLBACK")
            except Exception:
                pass
            raise

    # ── public interface ───────────────────────────────────────────────

    def initialize_attempt(self, attempt_id: str) -> None:
        """Idempotent no-op — table creation happens at DB open time.

        The attempt_id is validated on first append, not here.
        """
        # Touch connection to ensure schema exists.
        _ = self.conn

    # ── reservation ────────────────────────────────────────────────────

    def reserve_attempt(self, attempt_id: str) -> AttemptReservation:
        """Reserve *attempt_id* and return its current observable state.

        Atomicity: the reservation INSERT (or UPDATE on re-reservation)
        and the snapshot read of current event state happen inside one
        ``BEGIN IMMEDIATE`` transaction, so the returned projection is
        consistent with the reservation write.
        """
        conn = self.conn
        self._begin_immediate_retry(conn)
        try:
            now_ns = time.time_ns()
            cur = conn.cursor()

            # Try insert; if it exists, update.
            cur.execute(
                "SELECT first_reserved_ns, reservation_count FROM attempt_reservations WHERE attempt_id = ?",
                (attempt_id,),
            )
            existing = cur.fetchone()
            if existing is None:
                is_new = True
                cur.execute(
                    "INSERT INTO attempt_reservations (attempt_id, first_reserved_ns, last_reserved_ns, reservation_count) VALUES (?, ?, ?, 1)",
                    (attempt_id, now_ns, now_ns),
                )
                first_reserved_ns = now_ns
                reservation_count = 1
            else:
                is_new = False
                first_reserved_ns = existing[0]
                reservation_count = existing[1] + 1
                cur.execute(
                    "UPDATE attempt_reservations SET last_reserved_ns = ?, reservation_count = ? WHERE attempt_id = ?",
                    (now_ns, reservation_count, attempt_id),
                )

            # Snapshot current event state inside the same transaction.
            cur.execute(
                "SELECT COALESCE(MAX(sequence), 0), COUNT(1) FROM attempt_events WHERE attempt_id = ?",
                (attempt_id,),
            )
            seq_row = cur.fetchone()
            last_sequence = int(seq_row[0]) if seq_row is not None else 0
            event_count = int(seq_row[1]) if seq_row is not None else 0

            cur.execute(
                f"SELECT 1 FROM attempt_events WHERE attempt_id = ? AND event_type IN ({','.join('?' * len(_TERMINAL_EVENT_TYPE_VALUES))}) LIMIT 1",
                (attempt_id, *_TERMINAL_EVENT_TYPE_VALUES),
            )
            has_terminal = cur.fetchone() is not None

            conn.execute("COMMIT")
        except Exception:
            try:
                conn.execute("ROLLBACK")
            except Exception:
                pass
            raise

        return AttemptReservation(
            attempt_id=attempt_id,
            is_new=is_new,
            event_count=event_count,
            last_sequence=last_sequence,
            has_terminal=has_terminal,
            first_reserved_ns=first_reserved_ns,
            last_reserved_ns=now_ns,
            reservation_count=reservation_count,
        )

    def get_reservation(
        self, attempt_id: str
    ) -> Optional[AttemptReservation]:
        """Return the persisted reservation projection without reserving.

        Read-only. Returns ``None`` if no reservation exists.
        """
        conn = self.conn
        cur = conn.cursor()
        cur.execute(
            "SELECT first_reserved_ns, last_reserved_ns, reservation_count FROM attempt_reservations WHERE attempt_id = ?",
            (attempt_id,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        first_reserved_ns = int(row[0])
        last_reserved_ns = int(row[1])
        reservation_count = int(row[2])

        # Snapshot current event state (read-only).
        cur.execute(
            "SELECT COALESCE(MAX(sequence), 0), COUNT(1) FROM attempt_events WHERE attempt_id = ?",
            (attempt_id,),
        )
        seq_row = cur.fetchone()
        last_sequence = int(seq_row[0]) if seq_row is not None else 0
        event_count = int(seq_row[1]) if seq_row is not None else 0

        cur.execute(
            f"SELECT 1 FROM attempt_events WHERE attempt_id = ? AND event_type IN ({','.join('?' * len(_TERMINAL_EVENT_TYPE_VALUES))}) LIMIT 1",
            (attempt_id, *_TERMINAL_EVENT_TYPE_VALUES),
        )
        has_terminal = cur.fetchone() is not None

        return AttemptReservation(
            attempt_id=attempt_id,
            is_new=False,
            event_count=event_count,
            last_sequence=last_sequence,
            has_terminal=has_terminal,
            first_reserved_ns=first_reserved_ns,
            last_reserved_ns=last_reserved_ns,
            reservation_count=reservation_count,
        )

    # ── append (transactional core) ────────────────────────────────────

    def _begin_immediate_retry(self, conn: sqlite3.Connection) -> None:
        """Execute ``BEGIN IMMEDIATE`` with busy-retry for separate-process contention.

        When two independent connections race to acquire the write lock,
        ``BEGIN IMMEDIATE`` may encounter ``SQLITE_BUSY``.  We retry with
        exponential backoff inside a short window so the store surface is
        safe under concurrent writers without relying solely on the
        connection-level busy timeout (which may behave inconsistently
        across Python SQLite builds and WAL lock primitives).
        """
        max_attempts = 30
        base_delay = 0.01  # 10 ms
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

    def _append_tx(
        self, attempt_id: str, event: LedgerEvent
    ) -> AppendResult:
        """Enforce all Step 4 invariants inside ONE ``BEGIN IMMEDIATE``.

        Order of checks (dedup wins over rejection):

        1. attempt_id match (``ValueError`` outside the transaction).
        2. ``BEGIN IMMEDIATE`` — acquire the write lock for this attempt
           (with embedded busy-retry for separate-process contention).
        3. Idempotency-key dedup — if ``(attempt_id, idempotency_key)``
           already exists, return the existing event (no raise).
        4. Post-terminal rejection — if any terminal event exists for
           ``attempt_id``, raise :class:`PostTerminalAppendError`.
        5. Monotonic sequence — ``event.sequence`` must exceed the
           current max sequence, else :class:`MonotonicSequenceError`.
        6. INSERT + COMMIT.
        """
        if event.identity.attempt_id != attempt_id:
            raise ValueError(
                f"Event attempt_id {event.identity.attempt_id!r} "
                f"does not match store attempt_id {attempt_id!r}"
            )

        event_json = json.dumps(event.to_dict(), sort_keys=True, ensure_ascii=False)
        conn = self.conn

        self._begin_immediate_retry(conn)
        try:
            cur = conn.cursor()

            # (3) Idempotency-key dedup. Checked BEFORE any rejection so
            #     retries of an event that has since become post-terminal
            #     still return the existing event rather than raising.
            cur.execute(
                "SELECT event_json FROM attempt_events WHERE attempt_id = ? AND idempotency_key = ?",
                (attempt_id, event.idempotency_key),
            )
            dup_row = cur.fetchone()
            if dup_row is not None:
                # Roll back the empty write transaction before returning.
                conn.execute("ROLLBACK")
                existing = _deserialize_ledger_event(json.loads(dup_row[0]))
                return AppendResult(
                    attempt_id=attempt_id,
                    event=existing,
                    sequence=existing.sequence,
                    is_duplicate=True,
                )

            # (4) Post-terminal rejection — once terminal, no new events.
            cur.execute(
                f"SELECT 1 FROM attempt_events WHERE attempt_id = ? AND event_type IN ({','.join('?' * len(_TERMINAL_EVENT_TYPE_VALUES))}) LIMIT 1",
                (attempt_id, *_TERMINAL_EVENT_TYPE_VALUES),
            )
            if cur.fetchone() is not None:
                conn.execute("ROLLBACK")
                raise PostTerminalAppendError(
                    f"Attempt {attempt_id!r} already has a terminal event; "
                    f"further appends are rejected (idempotency_key={event.idempotency_key!r})."
                )

            # (5) Monotonic sequence — strictly greater than max.
            cur.execute(
                "SELECT COALESCE(MAX(sequence), 0) FROM attempt_events WHERE attempt_id = ?",
                (attempt_id,),
            )
            last_seq_row = cur.fetchone()
            last_seq = int(last_seq_row[0]) if last_seq_row is not None else 0
            if event.sequence <= last_seq:
                conn.execute("ROLLBACK")
                raise MonotonicSequenceError(
                    f"Event sequence {event.sequence} for attempt {attempt_id!r} "
                    f"is not strictly greater than the current max {last_seq}."
                )

            # (6) INSERT.
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
                    time.time_ns(),
                ),
            )
            conn.execute("COMMIT")
        except (PostTerminalAppendError, MonotonicSequenceError, ValueError):
            # Transaction already rolled back inside the handler for
            # typed store errors and pre-condition ValueErrors.
            raise
        except Exception as exc:
            try:
                conn.execute("ROLLBACK")
            except Exception:
                pass
            # Attempt to capture a PersistenceFailureDiagnostic in a
            # separate transaction.  This is best-effort evidence — if
            # it also fails the original exception is still raised.
            _try_record_append_failure_diagnostic(
                self, attempt_id, event.sequence, str(exc)
            )
            raise

        return AppendResult(
            attempt_id=attempt_id,
            event=event,
            sequence=event.sequence,
            is_duplicate=False,
        )

    def append_event(
        self, attempt_id: str, event: LedgerEvent
    ) -> AppendResult:
        """Persist a single ``LedgerEvent`` with all Step 4 invariants.

        See :meth:`AttemptLedgerStore.append_event` for the full contract.

        Returns:
            AppendResult whose ``event`` is the persisted event (the
            existing one when ``is_duplicate`` is True).
        """
        return self._append_tx(attempt_id, event)

    # ── typed append helpers ───────────────────────────────────────────

    @staticmethod
    def _require_event_type(
        event: LedgerEvent, expected: AttemptEventType
    ) -> None:
        """Raise ``ValueError`` if event.event_type does not match."""
        if event.event_type != expected:
            raise ValueError(
                f"Expected event_type {expected.value!r}, got "
                f"{event.event_type.value!r}."
            )

    def append_started(
        self, attempt_id: str, event: LedgerEvent
    ) -> AppendResult:
        """Append a STARTED event. Validates type before delegating."""
        self._require_event_type(event, AttemptEventType.STARTED)
        return self._append_tx(attempt_id, event)

    def append_completed(
        self, attempt_id: str, event: LedgerEvent
    ) -> AppendResult:
        """Append a COMPLETED event. Validates type before delegating."""
        self._require_event_type(event, AttemptEventType.COMPLETED)
        return self._append_tx(attempt_id, event)

    def append_failed(
        self, attempt_id: str, event: LedgerEvent
    ) -> AppendResult:
        """Append a FAILED event. Validates type before delegating."""
        self._require_event_type(event, AttemptEventType.FAILED)
        return self._append_tx(attempt_id, event)

    def append_cancelled(
        self, attempt_id: str, event: LedgerEvent
    ) -> AppendResult:
        """Append a CANCELLED event. Validates type before delegating."""
        self._require_event_type(event, AttemptEventType.CANCELLED)
        return self._append_tx(attempt_id, event)

    def read_events(self, attempt_id: str) -> list[LedgerEvent]:
        """Return all events for *attempt_id* ordered by sequence."""
        cur = self.conn.cursor()
        cur.execute(
            """\
SELECT event_json
FROM   attempt_events
WHERE  attempt_id = ?
ORDER  BY sequence ASC
""",
            (attempt_id,),
        )
        rows = cur.fetchall()
        return [_deserialize_ledger_event(json.loads(row[0])) for row in rows]

    def read_ledger(self, attempt_id: str) -> ExecutionAttemptLedger:
        """Reconstruct an ``ExecutionAttemptLedger`` from stored events.

        The returned ledger binds ``ledger_schema_version`` to the pinned
        ``LEDGER_SCHEMA_VERSION`` (identical to how ``ExecutionAttemptLedger``
        defaults at construction time).
        """
        events = tuple(self.read_events(attempt_id))
        return ExecutionAttemptLedger(
            attempt_id=attempt_id,
            events=events,
            ledger_schema_version=LEDGER_SCHEMA_VERSION,
        )

    def event_count(self, attempt_id: str) -> int:
        """Return the number of persisted events for *attempt_id*."""
        cur = self.conn.cursor()
        cur.execute(
            "SELECT COUNT(1) FROM attempt_events WHERE attempt_id = ?",
            (attempt_id,),
        )
        return cur.fetchone()[0]

    def has_terminal_event(self, attempt_id: str) -> bool:
        """Return ``True`` when a terminal event exists for *attempt_id*."""
        cur = self.conn.cursor()
        cur.execute(
            f"SELECT 1 FROM attempt_events WHERE attempt_id = ? AND event_type IN ({','.join('?' * len(_TERMINAL_EVENT_TYPE_VALUES))}) LIMIT 1",
            (attempt_id, *_TERMINAL_EVENT_TYPE_VALUES),
        )
        return cur.fetchone() is not None

    def last_sequence(self, attempt_id: str) -> int:
        """Return the highest persisted sequence number (0 if empty)."""
        cur = self.conn.cursor()
        cur.execute(
            """\
SELECT COALESCE(MAX(sequence), 0)
FROM   attempt_events
WHERE  attempt_id = ?
""",
            (attempt_id,),
        )
        return cur.fetchone()[0]

    def get_terminal_event(
        self, attempt_id: str
    ) -> Optional[LedgerEvent]:
        """Return the single terminal event for *attempt_id*, if any.

        Returns ``None`` if no terminal event has been persisted. The
        store enforces at most one terminal event, so the returned event
        is unique when present.
        """
        cur = self.conn.cursor()
        cur.execute(
            f"SELECT event_json FROM attempt_events WHERE attempt_id = ? AND event_type IN ({','.join('?' * len(_TERMINAL_EVENT_TYPE_VALUES))}) ORDER BY sequence ASC LIMIT 1",
            (attempt_id, *_TERMINAL_EVENT_TYPE_VALUES),
        )
        row = cur.fetchone()
        if row is None:
            return None
        return _deserialize_ledger_event(json.loads(row[0]))

    # ── Step 5: durable gates (SQLite-optimized) ───────────────────────

    def start_verified(self, attempt_id: str) -> StartGateResult:
        """Verify a STARTED event is durably persisted (SQLite-optimized).

        Uses a targeted query on ``attempt_events`` filtered by
        ``event_type = 'STARTED'``.  After deserialization, the event's
        ``event_type`` is cross-checked to guard against schema drift or
        data corruption.

        Fail-closed semantics:
        * Any query error → ``INDETERMINATE``.
        * Deserialization failure on a matching row → ``INDETERMINATE``.
        * Deserialized event_type ≠ STARTED → ``INDETERMINATE``.
        * Multiple STARTED rows → ``INCOHERENT``.
        * Zero rows → ``INCOMPLETE``.
        * Exactly one coherent row → ``VERIFIED``.
        """
        try:
            cur = self.conn.cursor()
            cur.execute(
                "SELECT event_json FROM attempt_events"
                " WHERE attempt_id = ? AND event_type = ?"
                " ORDER BY sequence ASC",
                (attempt_id, AttemptEventType.STARTED.value),
            )
            rows = cur.fetchall()
        except Exception as exc:
            return StartGateResult(
                attempt_id=attempt_id,
                status=GateStatus.INDETERMINATE,
                started_event=None,
                evidence=f"Query failed: {exc}",
            )

        if len(rows) == 0:
            return StartGateResult(
                attempt_id=attempt_id,
                status=GateStatus.INCOMPLETE,
                started_event=None,
                evidence="No STARTED event found in durable store.",
            )

        if len(rows) > 1:
            return StartGateResult(
                attempt_id=attempt_id,
                status=GateStatus.INCOHERENT,
                started_event=None,
                evidence=(
                    f"Found {len(rows)} STARTED rows; expected at most one."
                ),
            )

        # Exactly one row — verify it round-trips correctly.
        try:
            event = _deserialize_ledger_event(json.loads(rows[0][0]))
        except Exception as exc:
            return StartGateResult(
                attempt_id=attempt_id,
                status=GateStatus.INDETERMINATE,
                started_event=None,
                evidence=f"Deserialization failed for STARTED row: {exc}",
            )

        if event.event_type != AttemptEventType.STARTED:
            return StartGateResult(
                attempt_id=attempt_id,
                status=GateStatus.INDETERMINATE,
                started_event=None,
                evidence=(
                    f"Deserialized event_type={event.event_type.value!r}, "
                    f"expected 'STARTED'; possible store corruption."
                ),
            )

        return StartGateResult(
            attempt_id=attempt_id,
            status=GateStatus.VERIFIED,
            started_event=event,
            evidence="Exactly one STARTED event verified in durable store.",
        )

    def terminal_or_indeterminate_verified(
        self, attempt_id: str
    ) -> TerminalGateResult:
        """Verify a terminal event is durably persisted (SQLite-optimized).

        Uses a targeted query on ``attempt_events`` filtered by terminal
        ``event_type`` values.  After deserialization the event is
        cross-checked to confirm it is genuinely terminal.

        Fail-closed semantics:
        * Any query error → ``INDETERMINATE``.
        * Deserialization failure on a matching row → ``INDETERMINATE``.
        * Deserialized event_type is not terminal → ``INDETERMINATE``.
        * Multiple terminal rows → ``INCOHERENT``.
        * Zero rows → ``INCOMPLETE``.
        * Exactly one coherent terminal row → ``VERIFIED``.
        """
        _TERMINAL_SET = frozenset({
            AttemptEventType.COMPLETED,
            AttemptEventType.FAILED,
            AttemptEventType.CANCELLED,
        })

        try:
            cur = self.conn.cursor()
            cur.execute(
                f"SELECT event_json FROM attempt_events"
                f" WHERE attempt_id = ? AND event_type IN ({','.join('?' * len(_TERMINAL_EVENT_TYPE_VALUES))})"
                f" ORDER BY sequence ASC",
                (attempt_id, *_TERMINAL_EVENT_TYPE_VALUES),
            )
            rows = cur.fetchall()
        except Exception as exc:
            return TerminalGateResult(
                attempt_id=attempt_id,
                status=GateStatus.INDETERMINATE,
                terminal_event=None,
                evidence=f"Query failed: {exc}",
            )

        if len(rows) == 0:
            return TerminalGateResult(
                attempt_id=attempt_id,
                status=GateStatus.INCOMPLETE,
                terminal_event=None,
                evidence="No terminal event found in durable store.",
            )

        if len(rows) > 1:
            return TerminalGateResult(
                attempt_id=attempt_id,
                status=GateStatus.INCOHERENT,
                terminal_event=None,
                evidence=(
                    f"Found {len(rows)} terminal rows; expected at most one."
                ),
            )

        # Exactly one row — verify it round-trips correctly.
        try:
            event = _deserialize_ledger_event(json.loads(rows[0][0]))
        except Exception as exc:
            return TerminalGateResult(
                attempt_id=attempt_id,
                status=GateStatus.INDETERMINATE,
                terminal_event=None,
                evidence=f"Deserialization failed for terminal row: {exc}",
            )

        if event.event_type not in _TERMINAL_SET:
            return TerminalGateResult(
                attempt_id=attempt_id,
                status=GateStatus.INDETERMINATE,
                terminal_event=None,
                evidence=(
                    f"Deserialized event_type={event.event_type.value!r}, "
                    f"not a terminal type; possible store corruption."
                ),
            )

        return TerminalGateResult(
            attempt_id=attempt_id,
            status=GateStatus.VERIFIED,
            terminal_event=event,
            evidence="Exactly one terminal event verified in durable store.",
        )

    # ── Step 8: diagnostic persistence and queries ──────────────────────

    def record_persistence_failure_diagnostic(
        self, attempt_id: str, diagnostic: Any
    ) -> None:
        """Persist a ``PersistenceFailureDiagnostic`` as evidence.

        The diagnostic is written in its own transaction, independent
        of the append transaction that failed.  It is joinable via
        ``attempt_id`` and is evidence only — it never grants append or
        completion authority.

        Raises:
            ValueError: if *diagnostic* is not a
                ``PersistenceFailureDiagnostic``.
        """
        from arnold.workflow.execution_attempt_ledger import (
            PersistenceFailureDiagnostic,
        )

        if not isinstance(diagnostic, PersistenceFailureDiagnostic):
            raise ValueError(
                f"Expected PersistenceFailureDiagnostic, got {type(diagnostic).__name__}"
            )

        diag_id = str(uuid.uuid4())
        diag_json = json.dumps(
            diagnostic.to_dict(), sort_keys=True, ensure_ascii=False
        )
        now_ns = time.time_ns()

        conn = self.conn
        self._begin_immediate_retry(conn)
        try:
            cur = conn.cursor()
            cur.execute(
                """\
INSERT INTO persistence_failure_diagnostics
    (attempt_id, diagnostic_id, target_event_sequence,
     failure_mode, observed_error, diagnostic_json, recorded_at_ns)
VALUES (?, ?, ?, ?, ?, ?, ?)
""",
                (
                    attempt_id,
                    diag_id,
                    diagnostic.target_event_sequence,
                    diagnostic.failure_mode.value,
                    diagnostic.observed_error,
                    diag_json,
                    now_ns,
                ),
            )
            conn.execute("COMMIT")
        except Exception:
            try:
                conn.execute("ROLLBACK")
            except Exception:
                pass
            raise

    def record_reconciliation_diagnostic(
        self, attempt_id: str, diagnostic: Any
    ) -> None:
        """Persist a ``ReconciliationDiagnostic`` as evidence.

        The diagnostic is written in its own transaction, joinable via
        ``attempt_id``, and is evidence only.

        Raises:
            ValueError: if *diagnostic* is not a
                ``ReconciliationDiagnostic``.
        """
        from arnold.workflow.execution_attempt_ledger import (
            ReconciliationDiagnostic,
        )

        if not isinstance(diagnostic, ReconciliationDiagnostic):
            raise ValueError(
                f"Expected ReconciliationDiagnostic, got {type(diagnostic).__name__}"
            )

        diag_id = str(uuid.uuid4())
        diag_json = json.dumps(
            diagnostic.to_dict(), sort_keys=True, ensure_ascii=False
        )
        now_ns = time.time_ns()

        conn = self.conn
        self._begin_immediate_retry(conn)
        try:
            cur = conn.cursor()
            cur.execute(
                """\
INSERT INTO reconciliation_diagnostics
    (attempt_id, diagnostic_id, reconciled_event_sequence,
     outcome, outcome_detail, diagnostic_json, recorded_at_ns)
VALUES (?, ?, ?, ?, ?, ?, ?)
""",
                (
                    attempt_id,
                    diag_id,
                    diagnostic.reconciled_event_sequence,
                    diagnostic.outcome.value,
                    diagnostic.outcome_detail,
                    diag_json,
                    now_ns,
                ),
            )
            conn.execute("COMMIT")
        except Exception:
            try:
                conn.execute("ROLLBACK")
            except Exception:
                pass
            raise

    def query_gaps(self, attempt_id: str) -> list[GapEntry]:
        """Return sequence gaps in the persisted event stream.

        Gaps are detected by comparing the ordered persisted sequences
        against the monotonic range [1, max_sequence].  An empty list
        means no gaps.
        """
        cur = self.conn.cursor()
        cur.execute(
            "SELECT sequence FROM attempt_events"
            " WHERE attempt_id = ?"
            " ORDER BY sequence ASC",
            (attempt_id,),
        )
        rows = cur.fetchall()
        if not rows:
            return []

        sequences = [int(r[0]) for r in rows]
        gaps: list[GapEntry] = []

        # Gap before first expected sequence 1.
        if sequences[0] > 1:
            missing = sequences[0] - 1
            gaps.append(
                GapEntry(
                    attempt_id=attempt_id,
                    gap_start=0,
                    gap_end=sequences[0],
                    missing_count=missing,
                )
            )

        # Internal gaps.
        for i in range(len(sequences) - 1):
            expected_next = sequences[i] + 1
            actual_next = sequences[i + 1]
            if actual_next > expected_next:
                missing = actual_next - expected_next
                gaps.append(
                    GapEntry(
                        attempt_id=attempt_id,
                        gap_start=sequences[i],
                        gap_end=actual_next,
                        missing_count=missing,
                    )
                )

        return gaps

    def query_persistence_diagnostics(
        self, attempt_id: str
    ) -> list[Any]:
        """Return all ``PersistenceFailureDiagnostic`` records for *attempt_id*."""
        from arnold.workflow.execution_attempt_ledger import (
            PersistenceFailureDiagnostic,
        )

        cur = self.conn.cursor()
        cur.execute(
            "SELECT diagnostic_json FROM persistence_failure_diagnostics"
            " WHERE attempt_id = ?"
            " ORDER BY recorded_at_ns ASC",
            (attempt_id,),
        )
        rows = cur.fetchall()
        result: list[Any] = []
        for row in rows:
            try:
                d = json.loads(row[0])
                result.append(
                    _deserialize_persistence_failure_diagnostic(d)
                )
            except Exception:
                # Corrupt diagnostic — skip; caller can detect gaps
                # via query_gaps if needed.
                pass
        return result

    def query_reconciliation_state(
        self, attempt_id: str
    ) -> list[Any]:
        """Return all ``ReconciliationDiagnostic`` records for *attempt_id*."""
        from arnold.workflow.execution_attempt_ledger import (
            ReconciliationDiagnostic,
        )

        cur = self.conn.cursor()
        cur.execute(
            "SELECT diagnostic_json FROM reconciliation_diagnostics"
            " WHERE attempt_id = ?"
            " ORDER BY recorded_at_ns ASC",
            (attempt_id,),
        )
        rows = cur.fetchall()
        result: list[Any] = []
        for row in rows:
            try:
                d = json.loads(row[0])
                result.append(
                    _deserialize_reconciliation_diagnostic(d)
                )
            except Exception:
                pass
        return result

    def query_source_cursor(
        self, attempt_id: str, cursor_key: str = "default"
    ) -> Optional[SourceCursor]:
        """Return the source cursor position for *attempt_id*."""
        cur = self.conn.cursor()
        cur.execute(
            "SELECT last_sequence, last_position, updated_at_ns"
            " FROM source_cursors"
            " WHERE attempt_id = ? AND cursor_key = ?",
            (attempt_id, cursor_key),
        )
        row = cur.fetchone()
        if row is None:
            return None
        return SourceCursor(
            attempt_id=attempt_id,
            cursor_key=cursor_key,
            last_sequence=int(row[0]),
            last_position=row[1],
            updated_at_ns=int(row[2]),
        )

    def update_source_cursor(
        self,
        attempt_id: str,
        last_sequence: int,
        cursor_key: str = "default",
        last_position: str | None = None,
    ) -> SourceCursor:
        """Record (or update) the source cursor position for *attempt_id*."""
        now_ns = time.time_ns()
        conn = self.conn
        self._begin_immediate_retry(conn)
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO source_cursors"
                " (attempt_id, cursor_key, last_sequence, last_position, updated_at_ns)"
                " VALUES (?, ?, ?, ?, ?)"
                " ON CONFLICT(attempt_id, cursor_key) DO UPDATE SET"
                " last_sequence = excluded.last_sequence,"
                " last_position = excluded.last_position,"
                " updated_at_ns = excluded.updated_at_ns",
                (attempt_id, cursor_key, last_sequence, last_position, now_ns),
            )
            conn.execute("COMMIT")
        except Exception:
            try:
                conn.execute("ROLLBACK")
            except Exception:
                pass
            raise
        return SourceCursor(
            attempt_id=attempt_id,
            cursor_key=cursor_key,
            last_sequence=last_sequence,
            last_position=last_position,
            updated_at_ns=now_ns,
        )

    # ── metadata introspection ─────────────────────────────────────────

    def get_contract_version(self) -> str:
        """Return the pinned contract version from metadata."""
        cur = self.conn.cursor()
        cur.execute(
            "SELECT value FROM _store_metadata WHERE key = 'contract_version'"
        )
        row = cur.fetchone()
        if row is None:
            return self._contract_version
        return row[0]

    def get_store_version(self) -> str:
        """Return the store version from metadata."""
        cur = self.conn.cursor()
        cur.execute(
            "SELECT value FROM _store_metadata WHERE key = 'store_version'"
        )
        row = cur.fetchone()
        if row is None:
            return _STORE_VERSION
        return row[0]


# ── Deserialization helpers ────────────────────────────────────────────────


def _try_record_append_failure_diagnostic(
    store: Any,
    attempt_id: str,
    target_sequence: int,
    error_message: str,
) -> None:
    """Best-effort capture of a persistence-failure diagnostic.

    Called from inside ``_append_tx`` after the original transaction has
    been rolled back.  The diagnostic is written in a fresh transaction
    so it is not lost with the failed append.  If the diagnostic write
    also fails the error is silently discarded — the original append
    exception is still raised to the caller.
    """
    try:
        from arnold.workflow.execution_attempt_ledger import (
            PersistenceFailureDiagnostic,
            PersistenceFailureMode,
        )

        diag = PersistenceFailureDiagnostic(
            failure_mode=PersistenceFailureMode.WRITE_FAILED,
            target_event_sequence=target_sequence,
            observed_error=error_message,
        )
        store.record_persistence_failure_diagnostic(attempt_id, diag)
    except Exception:
        # Diagnostic capture is best-effort only.
        pass


def _deserialize_ledger_event(d: dict[str, Any]) -> LedgerEvent:
    """Reconstruct a ``LedgerEvent`` from its ``to_dict()`` representation.

    This function is the inverse of ``LedgerEvent.to_dict()`` and does NOT
    mutate the ``LedgerEvent`` or ``ExecutionAttemptLedger`` schema.
    """
    event_type = AttemptEventType(d["event_type"])
    persistence_status = PersistenceStatus(d["persistence_status"])
    outcome = AttemptOutcome(d["outcome"]) if d.get("outcome") is not None else None

    # Identity
    ident = d["identity"]
    identity = AttemptIdentity(
        workflow_id=ident["workflow_id"],
        run_id=ident["run_id"],
        graph_revision=ident["graph_revision"],
        attempt_ordinal=ident.get("attempt_ordinal", 1),
        attempt_id=ident["attempt_id"],
        step_id=ident.get("step_id"),
        boundary_id=ident.get("boundary_id"),
        invocation_id=ident.get("invocation_id"),
    )

    # Provenance
    prov = d["provenance"]
    causal_lineage_raw = prov.get("causal_lineage", [])
    if isinstance(causal_lineage_raw, list):
        causal_lineage = tuple(causal_lineage_raw)
    else:
        causal_lineage = ()
    provenance = AttemptProvenance(
        parent_attempt_id=prov.get("parent_attempt_id"),
        causal_lineage=causal_lineage,
        actor_id=prov.get("actor_id"),
        tool_id=prov.get("tool_id"),
    )

    # Adapter
    adp = d["adapter"]
    adapter_kind = AdapterKind(adp["adapter_kind"])
    adapter = RuntimeAdapter(
        adapter_kind=adapter_kind,
        adapter_version=adp["adapter_version"],
    )

    # Versions
    ver = d["versions"]
    versions = VersionSet(
        code_version=ver.get("code_version", ""),
        config_version=ver.get("config_version", ""),
        template_version=ver.get("template_version", ""),
    )

    # GrantRef
    gr = d["grant_ref"]
    grant_ref = GrantRef(
        grant_id=gr["grant_id"],
        decision_id=gr.get("decision_id"),
    )

    # Payload (may be None, a dict, or a DurableRef dict)
    payload_raw = d.get("payload")
    if payload_raw is not None and isinstance(payload_raw, dict) and "store_id" in payload_raw:
        from arnold.workflow.durable_refs import DurableRef
        payload = DurableRef(
            store_id=payload_raw["store_id"],
            locator=payload_raw["locator"],
            digest=payload_raw.get("digest", ""),
            schema_type=payload_raw.get("schema_type", "application/json"),
            visibility_class=payload_raw.get("visibility_class"),
            encryption_scope=payload_raw.get("encryption_scope"),
        )
    else:
        payload = payload_raw

    return LedgerEvent(
        idempotency_key=d["idempotency_key"],
        event_type=event_type,
        identity=identity,
        provenance=provenance,
        adapter=adapter,
        versions=versions,
        grant_ref=grant_ref,
        sequence=d["sequence"],
        causal_predecessor_sequence=d["causal_predecessor_sequence"],
        append_position=d["append_position"],
        occurred_at=d["occurred_at"],
        observed_at=d["observed_at"],
        persistence_status=persistence_status,
        outcome=outcome,
        payload=payload,
        payload_policy_ref=d.get("payload_policy_ref"),
        event_schema_version=d.get("event_schema_version", LEDGER_SCHEMA_VERSION),
    )


def _deserialize_durable_ref(d: dict[str, Any]) -> Any:
    """Reconstruct a ``DurableRef`` from its ``to_dict()`` representation."""
    from arnold.workflow.durable_refs import DurableRef

    return DurableRef(
        store_id=d["store_id"],
        locator=d["locator"],
        digest=d.get("digest", ""),
        schema_type=d.get("schema_type", "application/octet-stream"),
        media_type=d.get("media_type", "application/octet-stream"),
        size_bytes=d.get("size_bytes"),
        encryption_scope=d.get("encryption_scope", "none"),
        access_scope=d.get("access_scope", "workflow"),
        privacy_class=d.get("privacy_class", "internal"),
        retention_class=d.get("retention_class", "run"),
        availability_class=d.get("availability_class", "standard"),
        tenant_id=d.get("tenant_id"),
        workflow_id=d.get("workflow_id"),
        ref_version=d.get("ref_version", "arnold.workflow.durable_ref.v1"),
        metadata=d.get("metadata", {}),
    )


def _deserialize_persistence_failure_diagnostic(
    d: dict[str, Any],
) -> Any:
    """Reconstruct a ``PersistenceFailureDiagnostic`` from its ``to_dict()``."""
    from arnold.workflow.execution_attempt_ledger import (
        PersistenceFailureDiagnostic,
        PersistenceFailureMode,
    )

    recovery_evidence_ref: Any = None
    if "recovery_evidence_ref" in d and d["recovery_evidence_ref"] is not None:
        recovery_evidence_ref = _deserialize_durable_ref(
            d["recovery_evidence_ref"]
        )

    return PersistenceFailureDiagnostic(
        failure_mode=PersistenceFailureMode(d["failure_mode"]),
        target_event_sequence=d["target_event_sequence"],
        observed_error=d["observed_error"],
        recovery_evidence_ref=recovery_evidence_ref,
        quarantined_authority_advance=d.get(
            "quarantined_authority_advance", False
        ),
        quarantine_reason=d.get("quarantine_reason"),
        diagnostic_schema_version=d.get(
            "diagnostic_schema_version",
            "arnold.workflow.ledger.persistence_failure_diagnostic.v1",
        ),
    )


def _deserialize_reconciliation_diagnostic(
    d: dict[str, Any],
) -> Any:
    """Reconstruct a ``ReconciliationDiagnostic`` from its ``to_dict()``."""
    from arnold.workflow.execution_attempt_ledger import (
        ReconciliationDiagnostic,
        ReconciliationOutcome,
    )

    recovered_refs_raw = d.get("recovered_evidence_refs", [])
    if isinstance(recovered_refs_raw, list):
        recovered_refs: tuple[Any, ...] = tuple(
            _deserialize_durable_ref(r) for r in recovered_refs_raw
        )
    else:
        recovered_refs = ()

    return ReconciliationDiagnostic(
        reconciled_event_sequence=d["reconciled_event_sequence"],
        outcome=ReconciliationOutcome(d["outcome"]),
        outcome_detail=d["outcome_detail"],
        recovered_evidence_refs=recovered_refs,
        authority_disposition=d.get("authority_disposition"),
        diagnostic_schema_version=d.get(
            "diagnostic_schema_version",
            "arnold.workflow.ledger.reconciliation_diagnostic.v1",
        ),
    )


# ── Public API surface ─────────────────────────────────────────────────────


__all__ = [
    "AppendResult",
    "AttemptLedgerError",
    "AttemptLedgerStore",
    "AttemptReservation",
    "GapEntry",
    "GateStatus",
    "MonotonicSequenceError",
    "PostTerminalAppendError",
    "SourceCursor",
    "SqliteAttemptLedgerStore",
    "StartGateResult",
    "TerminalGateResult",
]
