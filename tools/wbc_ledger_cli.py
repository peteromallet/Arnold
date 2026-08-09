#!/usr/bin/env python3
"""WBC Transactional Ledger CLI — JSON stdin/stdout shell adapter.

This CLI exposes the M6A ledger substrate to shell consumers via typed
exit codes. All input is read as one JSON object on stdin; all output is
written as one JSON object on stdout.

Operations
----------
append   — persist a ledger event (started/completed/failed/cancelled).
           Requires ``attempt_id``, ``event_type``, and ``event`` (a
           ``LedgerEvent`` dict).
read     — return all durable events for an ``attempt_id`` or reconstruct
           the full ``ExecutionAttemptLedger``.
query    — diagnostic projections: gaps, persistence_failure_diagnostics,
           reconciliation_state, source_cursor.
reconcile — run start/terminal gate verification and gap detection for an
            attempt_id.
migrate  — apply pending schema migrations (idempotent).

Exit codes (shell-observable typed statuses)
--------------------------------------------
0  SUCCESS             — durable operation completed; result JSON is
                         authoritative evidence.
1  INCOMPLETE          — normal non-terminal state (e.g. start gate not
                         yet satisfied).  The shell caller should retry
                         or wait.
2  INDETERMINATE       — persistence is ambiguous; the durable store
                         cannot be trusted for this attempt.  Do NOT
                         proceed.
3  INCOHERENT          — durable evidence contradicts the gate contract.
                         Store invariant may be violated.
4  VALIDATION_FAILURE  — input is malformed, missing required fields, or
                         violates the CLI contract.
5  PERSISTENCE_FAILURE — a write to the durable store failed.
"""

from __future__ import annotations

import json
import os
import sys
from enum import Enum, IntEnum
from pathlib import Path
from typing import Any, Optional

from arnold.adapters.ledger_store_adapter import (
    AdapterClosedError,
    LedgerStoreAdapter,
    MaxRetriesExceededError,
)
from arnold.workflow.attempt_ledger_store import (
    GateStatus,
    MonotonicSequenceError,
    PostTerminalAppendError,
    SqliteAttemptLedgerStore,
    _deserialize_ledger_event,
)
from arnold.workflow.execution_attempt_ledger import (
    AttemptEventType,
    LedgerEvent,
)
from arnold.workflow.ledger_migrations import SqliteLedgerMigrator


# ── Typed exit codes ───────────────────────────────────────────────────────


class ExitCode(IntEnum):
    """Shell-observable typed exit statuses.

    Shell consumers can test ``$?`` against these values to distinguish
    durable success from the various non-success states.
    """

    SUCCESS = 0
    """Durable operation completed; result is authoritative evidence."""

    INCOMPLETE = 1
    """Normal non-terminal state — gate not yet satisfied."""

    INDETERMINATE = 2
    """Persistence ambiguity — durable store cannot be trusted."""

    INCOHERENT = 3
    """Durable evidence contradicts the contract."""

    VALIDATION_FAILURE = 4
    """Input is malformed or violates the CLI contract."""

    PERSISTENCE_FAILURE = 5
    """A write to the durable store failed."""


# ── Gate-status to exit-code mapping ────────────────────────────────────────

_GATE_TO_EXIT: dict[GateStatus, ExitCode] = {
    GateStatus.VERIFIED: ExitCode.SUCCESS,
    GateStatus.INCOMPLETE: ExitCode.INCOMPLETE,
    GateStatus.INDETERMINATE: ExitCode.INDETERMINATE,
    GateStatus.INCOHERENT: ExitCode.INCOHERENT,
}


# ── Helpers ─────────────────────────────────────────────────────────────────


def _emit(result: dict[str, Any], code: ExitCode) -> None:
    """Write *result* as JSON to stdout and exit with *code*."""
    sys.stdout.write(json.dumps(result, default=str, indent=None))
    sys.stdout.write("\n")
    sys.exit(int(code))


def _fail(msg: str, code: ExitCode = ExitCode.VALIDATION_FAILURE) -> None:
    """Emit a failure envelope and exit."""
    _emit({"status": "error", "error": msg}, code)


def _require_fields(obj: dict[str, Any], *fields: str) -> None:
    """Raise (via _fail) if *obj* is missing any of *fields*."""
    missing = [f for f in fields if f not in obj]
    if missing:
        _fail(
            f"Missing required field(s): {', '.join(missing)}",
            ExitCode.VALIDATION_FAILURE,
        )


def _parse_ledger_event(event_dict: dict[str, Any]) -> LedgerEvent:
    """Parse a ``LedgerEvent`` from its ``to_dict()`` representation.

    Delegates to the store's well-tested ``_deserialize_ledger_event``
    so that the CLI and store always agree on the serialization contract.
    """
    return _deserialize_ledger_event(event_dict)


def _serialize(obj: Any) -> Any:
    """Return a JSON-serializable representation of *obj*."""
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    if hasattr(obj, "__dataclass_fields__"):
        # Generic dataclass serialization.
        result: dict[str, Any] = {}
        for field_name in obj.__dataclass_fields__:
            value = getattr(obj, field_name)
            result[field_name] = _serialize(value)
        return result
    if isinstance(obj, (list, tuple)):
        return [_serialize(item) for item in obj]
    if isinstance(obj, dict):
        return {str(k): _serialize(v) for k, v in obj.items()}
    if isinstance(obj, Enum):
        return obj.value
    return obj


# ── Operation handlers ─────────────────────────────────────────────────────


def _handle_append(adapter: LedgerStoreAdapter, req: dict[str, Any]) -> None:
    """Handle an ``append`` operation."""
    _require_fields(req, "attempt_id", "event_type", "event")
    attempt_id: str = req["attempt_id"]
    event_type_str: str = req["event_type"]
    event_dict: dict[str, Any] = req["event"]

    # Validate event_type.
    try:
        event_type = AttemptEventType(event_type_str)
    except ValueError:
        _fail(
            f"Invalid event_type: {event_type_str!r}. "
            f"Must be one of: started, completed, failed, cancelled.",
            ExitCode.VALIDATION_FAILURE,
        )

    # Parse the ledger event.
    try:
        event = _parse_ledger_event(event_dict)
    except (KeyError, TypeError, ValueError) as exc:
        _fail(
            f"Invalid event payload: {exc}",
            ExitCode.VALIDATION_FAILURE,
        )

    # Route to the typed append helper.
    try:
        if event_type == AttemptEventType.STARTED:
            result = adapter.append_started(attempt_id, event)
        elif event_type == AttemptEventType.COMPLETED:
            result = adapter.append_completed(attempt_id, event)
        elif event_type == AttemptEventType.FAILED:
            result = adapter.append_failed(attempt_id, event)
        elif event_type == AttemptEventType.CANCELLED:
            result = adapter.append_cancelled(attempt_id, event)
        else:
            _fail(f"Unsupported event_type: {event_type_str}", ExitCode.VALIDATION_FAILURE)
            return
    except (MonotonicSequenceError, PostTerminalAppendError) as exc:
        _fail(
            f"Append rejected by store invariant: {exc}",
            ExitCode.PERSISTENCE_FAILURE,
        )
    except MaxRetriesExceededError as exc:
        _fail(
            f"Transient lock retries exhausted: {exc}",
            ExitCode.PERSISTENCE_FAILURE,
        )
    except AdapterClosedError as exc:
        _fail(f"Adapter is closed: {exc}", ExitCode.PERSISTENCE_FAILURE)
    except Exception as exc:
        _fail(
            f"Unexpected append failure: {exc}",
            ExitCode.PERSISTENCE_FAILURE,
        )

    _emit(
        {
            "status": "success",
            "operation": "append",
            "attempt_id": attempt_id,
            "sequence": result.sequence,
            "is_duplicate": result.is_duplicate,
            "event": _serialize(result.event),
        },
        ExitCode.SUCCESS,
    )


def _handle_read(adapter: LedgerStoreAdapter, req: dict[str, Any]) -> None:
    """Handle a ``read`` operation."""
    _require_fields(req, "attempt_id")
    attempt_id: str = req["attempt_id"]
    mode: str = req.get("mode", "events")  # 'events' or 'ledger'

    try:
        if mode == "ledger":
            ledger = adapter.read_ledger(attempt_id)
            _emit(
                {
                    "status": "success",
                    "operation": "read",
                    "attempt_id": attempt_id,
                    "mode": "ledger",
                    "result": _serialize(ledger),
                },
                ExitCode.SUCCESS,
            )
        else:
            events = adapter.read_events(attempt_id)
            _emit(
                {
                    "status": "success",
                    "operation": "read",
                    "attempt_id": attempt_id,
                    "mode": "events",
                    "count": len(events),
                    "result": _serialize(events),
                },
                ExitCode.SUCCESS,
            )
    except Exception as exc:
        _fail(f"Read failed: {exc}", ExitCode.PERSISTENCE_FAILURE)


def _handle_query(adapter: LedgerStoreAdapter, req: dict[str, Any]) -> None:
    """Handle a ``query`` operation."""
    _require_fields(req, "kind")
    kind: str = req["kind"]
    attempt_id: str | None = req.get("attempt_id")

    try:
        if kind == "gaps":
            if not attempt_id:
                _fail("'gaps' query requires attempt_id", ExitCode.VALIDATION_FAILURE)
            result = adapter.query_gaps(attempt_id)
            _emit(
                {
                    "status": "success",
                    "operation": "query",
                    "kind": "gaps",
                    "attempt_id": attempt_id,
                    "result": _serialize(result),
                },
                ExitCode.SUCCESS,
            )
        elif kind == "persistence_diagnostics":
            if not attempt_id:
                _fail(
                    "'persistence_diagnostics' query requires attempt_id",
                    ExitCode.VALIDATION_FAILURE,
                )
            result = adapter.query_persistence_diagnostics(attempt_id)
            _emit(
                {
                    "status": "success",
                    "operation": "query",
                    "kind": "persistence_diagnostics",
                    "attempt_id": attempt_id,
                    "result": _serialize(result),
                },
                ExitCode.SUCCESS,
            )
        elif kind == "reconciliation_state":
            if not attempt_id:
                _fail(
                    "'reconciliation_state' query requires attempt_id",
                    ExitCode.VALIDATION_FAILURE,
                )
            result = adapter.query_reconciliation_state(attempt_id)
            _emit(
                {
                    "status": "success",
                    "operation": "query",
                    "kind": "reconciliation_state",
                    "attempt_id": attempt_id,
                    "result": _serialize(result),
                },
                ExitCode.SUCCESS,
            )
        elif kind == "source_cursor":
            if not attempt_id:
                _fail(
                    "'source_cursor' query requires attempt_id",
                    ExitCode.VALIDATION_FAILURE,
                )
            cursor_key = req.get("cursor_key", "default")
            result = adapter.query_source_cursor(attempt_id, cursor_key)
            _emit(
                {
                    "status": "success",
                    "operation": "query",
                    "kind": "source_cursor",
                    "attempt_id": attempt_id,
                    "cursor_key": cursor_key,
                    "result": _serialize(result) if result is not None else None,
                },
                ExitCode.SUCCESS,
            )
        elif kind == "contract_version":
            result = adapter.get_contract_version()
            _emit(
                {
                    "status": "success",
                    "operation": "query",
                    "kind": "contract_version",
                    "result": result,
                },
                ExitCode.SUCCESS,
            )
        elif kind == "store_version":
            result = adapter.get_store_version()
            _emit(
                {
                    "status": "success",
                    "operation": "query",
                    "kind": "store_version",
                    "result": result,
                },
                ExitCode.SUCCESS,
            )
        else:
            _fail(
                f"Unknown query kind: {kind!r}. "
                f"Valid: gaps, persistence_diagnostics, reconciliation_state, "
                f"source_cursor, contract_version, store_version.",
                ExitCode.VALIDATION_FAILURE,
            )
    except Exception as exc:
        _fail(f"Query failed: {exc}", ExitCode.PERSISTENCE_FAILURE)


def _handle_reconcile(adapter: LedgerStoreAdapter, req: dict[str, Any]) -> None:
    """Handle a ``reconcile`` operation.

    Runs start_verified and terminal_or_indeterminate_verified gates,
    plus gap detection for the given attempt_id. The exit code reflects
    the most severe status across all checks.
    """
    _require_fields(req, "attempt_id")
    attempt_id: str = req["attempt_id"]

    try:
        start_result = adapter.start_verified(attempt_id)
        terminal_result = adapter.terminal_or_indeterminate_verified(attempt_id)
        gaps = adapter.query_gaps(attempt_id)

        # Determine the overall exit code: the most severe status wins.
        # Severity order: INCOHERENT > INDETERMINATE > INCOMPLETE > VERIFIED
        statuses: list[GateStatus] = [
            start_result.status,
            terminal_result.status,
        ]
        severity_order = [
            GateStatus.VERIFIED,
            GateStatus.INCOMPLETE,
            GateStatus.INDETERMINATE,
            GateStatus.INCOHERENT,
        ]
        # Find the highest-severity status (last in the order).
        worst_status = GateStatus.VERIFIED
        for status in reversed(severity_order):
            if status in statuses:
                worst_status = status
                break

        _emit(
            {
                "status": worst_status.value,
                "operation": "reconcile",
                "attempt_id": attempt_id,
                "start_gate": {
                    "status": start_result.status.value,
                    "evidence": start_result.evidence,
                },
                "terminal_gate": {
                    "status": terminal_result.status.value,
                    "evidence": terminal_result.evidence,
                },
                "gaps": _serialize(gaps),
            },
            _GATE_TO_EXIT.get(worst_status, ExitCode.INDETERMINATE),
        )
    except Exception as exc:
        _fail(f"Reconciliation failed: {exc}", ExitCode.PERSISTENCE_FAILURE)


def _handle_migrate(adapter: LedgerStoreAdapter, req: dict[str, Any]) -> None:
    """Handle a ``migrate`` operation.

    Applies pending schema migrations. The adapter's underlying store
    connection is used to construct a ``SqliteLedgerMigrator``.
    """
    try:
        # Access the underlying store from the adapter.
        store: SqliteAttemptLedgerStore = adapter._store  # type: ignore[attr-defined]
        if store is None:
            _fail("Adapter not open — underlying store unavailable.", ExitCode.PERSISTENCE_FAILURE)
        migrator = SqliteLedgerMigrator(store)
        state_before = migrator.get_state()
        result = migrator.migrate()
        state_after = migrator.get_state()

        _emit(
            {
                "status": "success",
                "operation": "migrate",
                "applied_now": _serialize(result.applied_now),
                "skipped": _serialize(result.skipped),
                "final_version": result.final_version,
                "state_before": {
                    "last_applied_version": state_before.last_applied_version,
                    "pending_count": len(state_before.pending),
                    "is_complete": state_before.is_complete,
                },
                "state_after": {
                    "last_applied_version": state_after.last_applied_version,
                    "pending_count": len(state_after.pending),
                    "is_complete": state_after.is_complete,
                },
            },
            ExitCode.SUCCESS,
        )
    except Exception as exc:
        _fail(f"Migration failed: {exc}", ExitCode.PERSISTENCE_FAILURE)


# ── Dispatch table ─────────────────────────────────────────────────────────

_OPERATIONS: dict[str, Any] = {
    "append": _handle_append,
    "read": _handle_read,
    "query": _handle_query,
    "reconcile": _handle_reconcile,
    "migrate": _handle_migrate,
}


# ── Main ───────────────────────────────────────────────────────────────────


def main(argv: Optional[list[str]] = None) -> None:
    """Entry point. Reads JSON from stdin, dispatches, writes JSON to stdout.

    Args:
        argv: Command-line arguments. Expects ``argv[1]`` to be the database
            path. Defaults to ``sys.argv``.

    Exit codes are typed — see :class:`ExitCode`.
    """
    if argv is None:
        argv = sys.argv

    if len(argv) < 2:
        _fail(
            "Usage: wbc_ledger_cli.py <db_path>\n"
            "  Reads operation JSON from stdin, writes result JSON to stdout.",
            ExitCode.VALIDATION_FAILURE,
        )

    db_path: str = argv[1]

    # Read exactly one JSON object from stdin.
    try:
        raw = sys.stdin.read()
    except Exception as exc:
        _fail(f"Failed to read stdin: {exc}", ExitCode.VALIDATION_FAILURE)

    if not raw.strip():
        _fail("Empty stdin — expected a JSON operation object.", ExitCode.VALIDATION_FAILURE)

    try:
        req: dict[str, Any] = json.loads(raw)
    except json.JSONDecodeError as exc:
        _fail(
            f"Invalid JSON on stdin: {exc}",
            ExitCode.VALIDATION_FAILURE,
        )

    if not isinstance(req, dict):
        _fail(
            "Expected a JSON object on stdin, got a JSON array or scalar.",
            ExitCode.VALIDATION_FAILURE,
        )

    operation: str | None = req.get("operation")
    if not operation:
        _fail(
            "Missing required field: 'operation'. "
            f"Valid operations: {', '.join(sorted(_OPERATIONS))}.",
            ExitCode.VALIDATION_FAILURE,
        )

    handler = _OPERATIONS.get(operation)
    if handler is None:
        _fail(
            f"Unknown operation: {operation!r}. "
            f"Valid operations: {', '.join(sorted(_OPERATIONS))}.",
            ExitCode.VALIDATION_FAILURE,
        )

    # Open the adapter.
    adapter = LedgerStoreAdapter(db_path)
    try:
        adapter.open()
    except Exception as exc:
        _fail(
            f"Failed to open database at {db_path!r}: {exc}",
            ExitCode.PERSISTENCE_FAILURE,
        )

    try:
        handler(adapter, req)
    finally:
        adapter.close()


if __name__ == "__main__":
    main()
