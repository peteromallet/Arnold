"""Process-safe adapter wrapping ``SqliteAttemptLedgerStore``.

This module provides :class:`LedgerStoreAdapter`, a Python process-safe
wrapper that adds retry/backoff for transient SQLite locks, safe close on
SIGTERM/SIGINT, and crash-reopen consistency checks.

The adapter does NOT redefine ledger semantics — it delegates all
operations to the wrapped :class:`~arnold.workflow.attempt_ledger_store.SqliteAttemptLedgerStore`
and only adds process-lifecycle and locking resilience.

Key safety property: required-write persistence failures are **never**
caught or suppressed.  Retry/backoff applies only to transient SQLite
lock errors (``SQLITE_BUSY`` / "database is locked"), not to logical
errors, schema violations, or data integrity failures.
"""

from __future__ import annotations

import atexit
import logging
import os
import signal
import sqlite3
import time
from pathlib import Path
from typing import Any, Callable, Optional, TypeVar

from arnold.workflow.attempt_ledger_store import (
    AppendResult,
    AttemptLedgerError,
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
    AttemptEventType,
    ExecutionAttemptLedger,
    LedgerEvent,
)

logger = logging.getLogger(__name__)

_F = TypeVar("_F", bound=Callable[..., Any])

# ── Transient SQLite lock error detection ──────────────────────────────────

# Error messages that indicate a transient lock (SQLITE_BUSY).
_TRANSIENT_LOCK_SUBSTRINGS: tuple[str, ...] = (
    "database is locked",
    "database table is locked",
    "sqlite_busy",
)

# SQLite error codes that indicate a transient condition.
_TRANSIENT_SQLITE_CODES: tuple[int, ...] = (
    5,   # SQLITE_BUSY
    261, # SQLITE_BUSY_RECOVERY
    517, # SQLITE_BUSY_SNAPSHOT
)


def _is_transient_lock_error(exc: Exception) -> bool:
    """Return ``True`` if *exc* is a transient SQLite lock/busy error.

    These are the only errors the adapter will retry.  All other
    exceptions — including logical errors, schema violations, data
    corruption, and disk I/O errors — are immediately propagated.
    """
    if not isinstance(exc, sqlite3.OperationalError):
        return False
    msg = str(exc).lower()
    for substr in _TRANSIENT_LOCK_SUBSTRINGS:
        if substr in msg:
            return True
    # Also check the sqlite3 error code if available.
    if hasattr(exc, "sqlite_errorcode"):
        code = exc.sqlite_errorcode  # type: ignore[attr-defined]
        if code in _TRANSIENT_SQLITE_CODES:
            return True
    return False


# ── Typed errors ───────────────────────────────────────────────────────────


class AdapterError(Exception):
    """Base class for adapter-level errors."""


class AdapterClosedError(AdapterError):
    """Raised when an operation is attempted on a closed adapter."""


class CrashReopenIntegrityError(AdapterError):
    """Raised when crash-reopen consistency checks fail.

    Indicates that the database file on disk is not consistent with the
    adapter's expectations — e.g. wrong contract version, missing
    metadata tables, or WAL file damage.
    """


class MaxRetriesExceededError(AdapterError):
    """Raised when the adapter exhausts its retry budget for a transient lock.

    This is raised only after ``max_retries`` attempts to acquire a
    lock have failed.  The underlying operation was never executed, so
    no partial state exists.
    """


# ── Adapter ────────────────────────────────────────────────────────────────


class LedgerStoreAdapter:
    """Process-safe adapter around :class:`SqliteAttemptLedgerStore`.

    Adds three layers around the underlying store:

    1. **Retry/backoff** — transient SQLite lock errors (SQLITE_BUSY,
       "database is locked") are retried with exponential backoff up to
       ``max_retries``.  Logical errors, data corruption, and disk I/O
       failures are never retried.

    2. **Signal-safe close** — registers handlers for SIGTERM and
       SIGINT that close the underlying SQLite connection cleanly,
       preventing WAL corruption on abrupt process termination.

    3. **Crash-reopen consistency** — each operation that touches the
       database first verifies that the adapter is open and that the
       database is consistent with the expected contract version and
       store metadata.  If a crash (or ungraceful close) left the
       database in an inconsistent state, the adapter raises
       :class:`CrashReopenIntegrityError` rather than silently
       continuing.

    **Critical invariant**: required-write persistence failures are
    **never** caught or suppressed.  If ``append_event`` (or any typed
    append helper) raises a non-transient error (e.g.
    :class:`PostTerminalAppendError`, :class:`MonotonicSequenceError`,
    ``ValueError``, ``sqlite3.IntegrityError``), the adapter
    propagates it immediately.  Only transient lock errors are
    retried, and when the retry budget is exhausted the adapter raises
    :class:`MaxRetriesExceededError`.

    Usage::

        adapter = LedgerStoreAdapter("/path/to/store.db")
        adapter.open()
        try:
            reservation = adapter.reserve_attempt("attempt-1")
            result = adapter.append_started("attempt-1", event)
        finally:
            adapter.close()
    """

    def __init__(
        self,
        db_path: str | Path,
        max_retries: int = 10,
        base_delay: float = 0.05,
        max_delay: float = 2.0,
        consistency_check_on_every_call: bool = False,
    ) -> None:
        """Initialize the adapter.

        Args:
            db_path: Path to the SQLite database file.
            max_retries: Maximum retry attempts for transient lock errors.
            base_delay: Initial backoff delay in seconds.
            max_delay: Maximum backoff delay in seconds (exponential cap).
            consistency_check_on_every_call: If ``True``, run full
                crash-reopen consistency checks before every delegated
                operation.  Defaults to ``False`` (checks only on open
                and after a detected close).
        """
        self._db_path = Path(db_path) if isinstance(db_path, str) else db_path
        self._max_retries = max_retries
        self._base_delay = base_delay
        self._max_delay = max_delay
        self._consistency_check_on_every_call = consistency_check_on_every_call

        self._store: Optional[SqliteAttemptLedgerStore] = None
        self._closed: bool = True
        self._original_sigterm: Any = signal.SIG_DFL
        self._original_sigint: Any = signal.SIG_DFL
        self._atexit_registered: bool = False

    # ── lifecycle ──────────────────────────────────────────────────────

    def open(self) -> None:
        """Open the adapter, initialize the store, and register signal handlers.

        Idempotent — safe to call multiple times.
        """
        if not self._closed:
            return

        self._store = SqliteAttemptLedgerStore(self._db_path)
        self._closed = False

        # Perform crash-reopen consistency check.
        self._check_crash_reopen_consistency()

        # Register signal handlers for clean shutdown.
        self._original_sigterm = signal.signal(signal.SIGTERM, self._signal_handler)
        self._original_sigint = signal.signal(signal.SIGINT, self._signal_handler)

        # Register atexit handler as a fallback.
        if not self._atexit_registered:
            atexit.register(self._atexit_handler)
            self._atexit_registered = True

        logger.debug("LedgerStoreAdapter opened: %s", self._db_path)

    def close(self) -> None:
        """Close the adapter and restore original signal handlers.

        Idempotent — safe to call multiple times, including from signal
        handlers and atexit.
        """
        if self._closed:
            return

        # Restore signal handlers in reverse order.
        try:
            signal.signal(signal.SIGINT, self._original_sigint)
        except Exception:
            pass
        try:
            signal.signal(signal.SIGTERM, self._original_sigterm)
        except Exception:
            pass

        if self._store is not None:
            try:
                self._store.close()
            except Exception:
                pass
            self._store = None

        self._closed = True
        logger.debug("LedgerStoreAdapter closed: %s", self._db_path)

    @property
    def is_closed(self) -> bool:
        """Return ``True`` if the adapter has been closed."""
        return self._closed

    # ── signal / atexit handlers ───────────────────────────────────────

    def _signal_handler(self, signum: int, frame: Any) -> None:
        """Handle SIGTERM/SIGINT: close the adapter, then re-raise."""
        logger.warning(
            "LedgerStoreAdapter received signal %d, closing.", signum
        )
        self.close()
        # Restore and re-send the signal so the process terminates as
        # expected after a clean store close.
        signal.signal(signum, signal.SIG_DFL)
        os.kill(os.getpid(), signum)

    def _atexit_handler(self) -> None:
        """Fallback close on normal process exit."""
        if not self._closed:
            self.close()

    # ── crash-reopen consistency ───────────────────────────────────────

    def _check_crash_reopen_consistency(self) -> None:
        """Verify database integrity after a possible crash.

        Checks:
        1. The database file exists (it must by this point).
        2. Contract version matches ``LEDGER_SCHEMA_VERSION``.
        3. Store metadata table exists and has expected keys.
        4. WAL file can be accessed (basic sanity).

        Raises :class:`CrashReopenIntegrityError` if any check fails.
        """
        if self._store is None:
            raise AdapterClosedError("Adapter is closed.")

        try:
            store = self._store
            # Check 2: Contract version.
            contract_ver = store.get_contract_version()
            if contract_ver != LEDGER_SCHEMA_VERSION:
                raise CrashReopenIntegrityError(
                    f"Contract version mismatch: store has "
                    f"{contract_ver!r}, adapter expects "
                    f"{LEDGER_SCHEMA_VERSION!r}."
                )

            # Check 3: Store metadata integrity.
            store_ver = store.get_store_version()
            if not store_ver:
                raise CrashReopenIntegrityError(
                    "Store metadata is missing or empty."
                )

            # Check 4: Basic WAL file sanity (if it exists).
            wal_path = self._db_path.with_suffix(
                self._db_path.suffix + "-wal"
            )
            if wal_path.exists():
                # Verify the WAL file is readable.
                try:
                    wal_path.stat()
                except OSError as exc:
                    raise CrashReopenIntegrityError(
                        f"WAL file exists but is not accessible: {exc}"
                    )

        except CrashReopenIntegrityError:
            raise
        except Exception as exc:
            raise CrashReopenIntegrityError(
                f"Crash-reopen consistency check failed: {exc}"
            )

    def _ensure_open(self) -> SqliteAttemptLedgerStore:
        """Return the underlying store, ensuring the adapter is open.

        Raises :class:`AdapterClosedError` if the adapter has been closed.
        """
        if self._closed or self._store is None:
            raise AdapterClosedError("Adapter is closed. Call open() first.")
        if self._consistency_check_on_every_call:
            self._check_crash_reopen_consistency()
        return self._store

    # ── retry/backoff ──────────────────────────────────────────────────

    def _retry_on_transient_lock(
        self, operation: Callable[[], _F], operation_name: str
    ) -> _F:
        """Execute *operation*, retrying only on transient SQLite lock errors.

        The retry budget is ``self._max_retries`` with exponential
        backoff from ``self._base_delay`` capped at ``self._max_delay``.

        Args:
            operation: A zero-argument callable that performs the store
                operation.  Must be re-entrant — each retry re-invokes it.
            operation_name: Human-readable name for logging.

        Returns:
            The return value of *operation*.

        Raises:
            MaxRetriesExceededError: If all retries are exhausted.
            Any non-transient exception from *operation* is propagated
            immediately without retry.
        """
        last_exc: Optional[Exception] = None
        for attempt in range(self._max_retries + 1):
            try:
                return operation()
            except sqlite3.OperationalError as exc:
                if _is_transient_lock_error(exc) and attempt < self._max_retries:
                    last_exc = exc
                    delay = min(
                        self._base_delay * (2 ** attempt), self._max_delay
                    )
                    logger.debug(
                        "Retry %d/%d for %s after transient lock: %s "
                        "(waiting %.3fs)",
                        attempt + 1,
                        self._max_retries,
                        operation_name,
                        exc,
                        delay,
                    )
                    time.sleep(delay)
                    continue
                # Either not transient or out of retries.
                if _is_transient_lock_error(exc):
                    # Transient but exhausted — raise bounded error.
                    last_exc = exc
                    break
                # Non-transient — propagate immediately.  This is the
                # critical safety property: required-write failures are
                # never caught or suppressed.
                raise
            except Exception:
                # Non-OperationalError — propagate immediately.
                raise

        # All retries exhausted.
        raise MaxRetriesExceededError(
            f"Exhausted {self._max_retries} retries for {operation_name}: "
            f"{last_exc}"
        )

    # ── delegated operations ───────────────────────────────────────────

    def initialize_attempt(self, attempt_id: str) -> None:
        """Prepare durable storage for *attempt_id* (idempotent)."""
        store = self._ensure_open()
        self._retry_on_transient_lock(
            lambda: store.initialize_attempt(attempt_id),
            "initialize_attempt",
        )

    def reserve_attempt(self, attempt_id: str) -> AttemptReservation:
        """Reserve *attempt_id* and return its observable state."""
        store = self._ensure_open()
        return self._retry_on_transient_lock(
            lambda: store.reserve_attempt(attempt_id),
            "reserve_attempt",
        )

    def append_event(
        self, attempt_id: str, event: LedgerEvent
    ) -> AppendResult:
        """Append *event* with all Step 4 invariants.

        Required-write persistence failures (PostTerminalAppendError,
        MonotonicSequenceError, ValueError, etc.) are **never** retried
        or suppressed — they propagate immediately.
        """
        store = self._ensure_open()
        return self._retry_on_transient_lock(
            lambda: store.append_event(attempt_id, event),
            "append_event",
        )

    def append_started(
        self, attempt_id: str, event: LedgerEvent
    ) -> AppendResult:
        """Append a STARTED event."""
        store = self._ensure_open()
        return self._retry_on_transient_lock(
            lambda: store.append_started(attempt_id, event),
            "append_started",
        )

    def append_completed(
        self, attempt_id: str, event: LedgerEvent
    ) -> AppendResult:
        """Append a COMPLETED event."""
        store = self._ensure_open()
        return self._retry_on_transient_lock(
            lambda: store.append_completed(attempt_id, event),
            "append_completed",
        )

    def append_failed(
        self, attempt_id: str, event: LedgerEvent
    ) -> AppendResult:
        """Append a FAILED event."""
        store = self._ensure_open()
        return self._retry_on_transient_lock(
            lambda: store.append_failed(attempt_id, event),
            "append_failed",
        )

    def append_cancelled(
        self, attempt_id: str, event: LedgerEvent
    ) -> AppendResult:
        """Append a CANCELLED event."""
        store = self._ensure_open()
        return self._retry_on_transient_lock(
            lambda: store.append_cancelled(attempt_id, event),
            "append_cancelled",
        )

    def read_events(self, attempt_id: str) -> list[LedgerEvent]:
        """Return all events for *attempt_id* in append order."""
        store = self._ensure_open()
        return self._retry_on_transient_lock(
            lambda: store.read_events(attempt_id),
            "read_events",
        )

    def read_ledger(self, attempt_id: str) -> ExecutionAttemptLedger:
        """Return a fully reconstructed ``ExecutionAttemptLedger``."""
        store = self._ensure_open()
        return self._retry_on_transient_lock(
            lambda: store.read_ledger(attempt_id),
            "read_ledger",
        )

    def event_count(self, attempt_id: str) -> int:
        """Return the number of persisted events for *attempt_id*."""
        store = self._ensure_open()
        return self._retry_on_transient_lock(
            lambda: store.event_count(attempt_id),
            "event_count",
        )

    def has_terminal_event(self, attempt_id: str) -> bool:
        """Return ``True`` when a terminal event exists."""
        store = self._ensure_open()
        return self._retry_on_transient_lock(
            lambda: store.has_terminal_event(attempt_id),
            "has_terminal_event",
        )

    def last_sequence(self, attempt_id: str) -> int:
        """Return the highest persisted sequence number (0 if empty)."""
        store = self._ensure_open()
        return self._retry_on_transient_lock(
            lambda: store.last_sequence(attempt_id),
            "last_sequence",
        )

    def get_reservation(
        self, attempt_id: str
    ) -> Optional[AttemptReservation]:
        """Return the current reservation projection or ``None``."""
        store = self._ensure_open()
        return self._retry_on_transient_lock(
            lambda: store.get_reservation(attempt_id),
            "get_reservation",
        )

    def get_terminal_event(
        self, attempt_id: str
    ) -> Optional[LedgerEvent]:
        """Return the terminal event for *attempt_id*, if any."""
        store = self._ensure_open()
        return self._retry_on_transient_lock(
            lambda: store.get_terminal_event(attempt_id),
            "get_terminal_event",
        )

    def start_verified(self, attempt_id: str) -> StartGateResult:
        """Verify a STARTED event is durably persisted."""
        store = self._ensure_open()
        return self._retry_on_transient_lock(
            lambda: store.start_verified(attempt_id),
            "start_verified",
        )

    def terminal_or_indeterminate_verified(
        self, attempt_id: str
    ) -> TerminalGateResult:
        """Verify a terminal event is durably persisted."""
        store = self._ensure_open()
        return self._retry_on_transient_lock(
            lambda: store.terminal_or_indeterminate_verified(attempt_id),
            "terminal_or_indeterminate_verified",
        )

    # ── diagnostic operations ──────────────────────────────────────────

    def record_persistence_failure_diagnostic(
        self, attempt_id: str, diagnostic: Any
    ) -> None:
        """Persist a ``PersistenceFailureDiagnostic`` as evidence."""
        store = self._ensure_open()
        self._retry_on_transient_lock(
            lambda: store.record_persistence_failure_diagnostic(
                attempt_id, diagnostic
            ),
            "record_persistence_failure_diagnostic",
        )

    def record_reconciliation_diagnostic(
        self, attempt_id: str, diagnostic: Any
    ) -> None:
        """Persist a ``ReconciliationDiagnostic`` as evidence."""
        store = self._ensure_open()
        self._retry_on_transient_lock(
            lambda: store.record_reconciliation_diagnostic(
                attempt_id, diagnostic
            ),
            "record_reconciliation_diagnostic",
        )

    def query_gaps(self, attempt_id: str) -> list[Any]:
        """Return sequence gaps in the persisted event stream."""
        store = self._ensure_open()
        return self._retry_on_transient_lock(
            lambda: store.query_gaps(attempt_id),
            "query_gaps",
        )

    def query_persistence_diagnostics(
        self, attempt_id: str
    ) -> list[Any]:
        """Return all ``PersistenceFailureDiagnostic`` records."""
        store = self._ensure_open()
        return self._retry_on_transient_lock(
            lambda: store.query_persistence_diagnostics(attempt_id),
            "query_persistence_diagnostics",
        )

    def query_reconciliation_state(
        self, attempt_id: str
    ) -> list[Any]:
        """Return all ``ReconciliationDiagnostic`` records."""
        store = self._ensure_open()
        return self._retry_on_transient_lock(
            lambda: store.query_reconciliation_state(attempt_id),
            "query_reconciliation_state",
        )

    def query_source_cursor(
        self, attempt_id: str, cursor_key: str = "default"
    ) -> Optional[Any]:
        """Return the source cursor position for *attempt_id*."""
        store = self._ensure_open()
        return self._retry_on_transient_lock(
            lambda: store.query_source_cursor(attempt_id, cursor_key),
            "query_source_cursor",
        )

    def update_source_cursor(
        self,
        attempt_id: str,
        last_sequence: int,
        cursor_key: str = "default",
        last_position: str | None = None,
    ) -> Any:
        """Record (or update) the source cursor position."""
        store = self._ensure_open()
        return self._retry_on_transient_lock(
            lambda: store.update_source_cursor(
                attempt_id, last_sequence, cursor_key, last_position
            ),
            "update_source_cursor",
        )

    # ── metadata introspection ─────────────────────────────────────────

    def get_contract_version(self) -> str:
        """Return the pinned contract version from metadata."""
        store = self._ensure_open()
        return self._retry_on_transient_lock(
            lambda: store.get_contract_version(),
            "get_contract_version",
        )

    def get_store_version(self) -> str:
        """Return the store version from metadata."""
        store = self._ensure_open()
        return self._retry_on_transient_lock(
            lambda: store.get_store_version(),
            "get_store_version",
        )

    # ── context manager support ────────────────────────────────────────

    def __enter__(self) -> "LedgerStoreAdapter":
        self.open()
        return self

    def __exit__(
        self, exc_type: Any, exc_val: Any, exc_tb: Any
    ) -> None:
        self.close()
