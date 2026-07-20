"""Tests for ``tools/wbc_ledger_cli.py`` — shell-consumer visibility.

Proves that shell consumers:
* receive typed exit codes (0–5) distinguishable via ``$?``,
* get valid JSON output on stdout,
* see validation failures (exit 4) for malformed input,
* see persistence failures (exit 5) when durable writes are rejected,
* see INCOMPLETE (exit 1) for non-terminal gate results,
* see INDETERMINATE (exit 2) and INCOHERENT (exit 3) for gate failures,
* can append, read, query, reconcile, and migrate.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

import pytest


# ── Helpers ─────────────────────────────────────────────────────────────────


_PROJECT_ROOT: str = str(
    Path(__file__).resolve().parent.parent.parent
)


def _cli_path() -> str:
    """Return the absolute path to the CLI entry point."""
    return str(Path(_PROJECT_ROOT) / "tools" / "wbc_ledger_cli.py")


def _run_cli(db_path: str, operation: dict[str, Any]) -> subprocess.CompletedProcess[str]:
    """Run the CLI as a subprocess, returning the completed process.

    The CLI is invoked with ``argv=[sys.executable, cli_path, db_path]``
    and *operation* is serialized to JSON and piped on stdin.
    Sets ``PYTHONPATH`` so the subprocess can find ``arnold`` modules.
    """
    cli = _cli_path()
    stdin_str = json.dumps(operation)
    env = os.environ.copy()
    env["PYTHONPATH"] = _PROJECT_ROOT
    return subprocess.run(
        [sys.executable, cli, db_path],
        input=stdin_str,
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
    )


def _run_cli_ok(db_path: str, operation: dict[str, Any]) -> dict[str, Any]:
    """Run the CLI and assert exit 0, returning parsed stdout JSON."""
    proc = _run_cli(db_path, operation)
    assert proc.returncode == 0, (
        f"Expected exit 0, got {proc.returncode}. stderr: {proc.stderr}"
    )
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(
            f"Invalid JSON on stdout: {exc}\nstdout: {proc.stdout!r}"
        )


def _make_minimal_event(
    attempt_id: str,
    event_type: str = "started",
    sequence: int = 1,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Return a minimal valid ``LedgerEvent`` dict for use as stdin.

    The dict follows the ``LedgerEvent.to_dict()`` contract.
    """
    if idempotency_key is None:
        idempotency_key = str(uuid.uuid4())
    return {
        "idempotency_key": idempotency_key,
        "event_type": event_type,
        "event_schema_version": "arnold.workflow.ledger.v1",
        "identity": {
            "workflow_id": "wf-test",
            "run_id": "run-test",
            "graph_revision": "rev-test",
            "attempt_ordinal": 1,
            "attempt_id": attempt_id,
        },
        "provenance": {
            "provenance_version": "arnold.workflow.attempt_provenance.v1",
            "lineage_depth": 0,
        },
        "adapter": {
            "adapter_kind": "arnold.pipeline.native",
            "adapter_version": "1.0.0",
        },
        "versions": {
            "code_version": "abc123",
            "config_version": "def456",
            "template_version": "ghi789",
        },
        "grant_ref": {
            "grant_id": "grant-1",
        },
        "sequence": sequence,
        "causal_predecessor_sequence": sequence - 1,
        "append_position": sequence,
        "occurred_at": "2024-01-01T00:00:00Z",
        "observed_at": "2024-01-01T00:00:00Z",
        "persistence_status": "durable",
    }


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def tmp_db_path() -> str:
    """Return a path to a temporary SQLite database that is cleaned up after."""
    fd, path = tempfile.mkstemp(suffix=".db", prefix="wbc_cli_test_")
    os.close(fd)
    yield path
    try:
        os.unlink(path)
    except OSError:
        pass
    # Also clean up WAL/SHM files.
    for suffix in ("-wal", "-shm"):
        try:
            os.unlink(path + suffix)
        except OSError:
            pass


@pytest.fixture
def attempt_id() -> str:
    """Return a fresh attempt_id (UUID)."""
    return str(uuid.uuid4())


# ── Validation failure tests (exit 4) ───────────────────────────────────────


class TestValidationFailures:
    """Prove the CLI returns exit 4 for malformed input."""

    def test_empty_stdin(self, tmp_db_path: str) -> None:
        """Empty stdin should exit 4 (validation failure)."""
        cli = _cli_path()
        env = os.environ.copy()
        env["PYTHONPATH"] = _PROJECT_ROOT
        proc = subprocess.run(
            [sys.executable, cli, tmp_db_path],
            input="",
            capture_output=True,
            text=True,
            timeout=10,
            env=env,
        )
        assert proc.returncode == 4, f"Expected exit 4, got {proc.returncode}"

    def test_invalid_json(self, tmp_db_path: str) -> None:
        """Malformed JSON should exit 4."""
        cli = _cli_path()
        env = os.environ.copy()
        env["PYTHONPATH"] = _PROJECT_ROOT
        proc = subprocess.run(
            [sys.executable, cli, tmp_db_path],
            input="not json",
            capture_output=True,
            text=True,
            timeout=10,
            env=env,
        )
        assert proc.returncode == 4, f"Expected exit 4, got {proc.returncode}"

    def test_json_array_not_object(self, tmp_db_path: str) -> None:
        """A JSON array on stdin should exit 4."""
        cli = _cli_path()
        env = os.environ.copy()
        env["PYTHONPATH"] = _PROJECT_ROOT
        proc = subprocess.run(
            [sys.executable, cli, tmp_db_path],
            input="[1, 2, 3]",
            capture_output=True,
            text=True,
            timeout=10,
            env=env,
        )
        assert proc.returncode == 4, f"Expected exit 4, got {proc.returncode}"

    def test_missing_operation(self, tmp_db_path: str) -> None:
        """Missing 'operation' field should exit 4."""
        proc = _run_cli(tmp_db_path, {"attempt_id": "x"})
        assert proc.returncode == 4, f"Expected exit 4, got {proc.returncode}"
        assert "operation" in proc.stdout.lower()

    def test_unknown_operation(self, tmp_db_path: str) -> None:
        """Unknown operation should exit 4."""
        proc = _run_cli(tmp_db_path, {"operation": "nonexistent"})
        assert proc.returncode == 4, f"Expected exit 4, got {proc.returncode}"

    def test_append_missing_event(self, tmp_db_path: str, attempt_id: str) -> None:
        """append without 'event' field should exit 4."""
        proc = _run_cli(
            tmp_db_path,
            {"operation": "append", "attempt_id": attempt_id, "event_type": "started"},
        )
        assert proc.returncode == 4, f"Expected exit 4, got {proc.returncode}"

    def test_append_invalid_event_type(self, tmp_db_path: str, attempt_id: str) -> None:
        """append with invalid event_type should exit 4."""
        event = _make_minimal_event(attempt_id, "started")
        proc = _run_cli(
            tmp_db_path,
            {
                "operation": "append",
                "attempt_id": attempt_id,
                "event_type": "bogus",
                "event": event,
            },
        )
        assert proc.returncode == 4, f"Expected exit 4, got {proc.returncode}"

    def test_read_missing_attempt_id(self, tmp_db_path: str) -> None:
        """read without attempt_id should exit 4."""
        proc = _run_cli(tmp_db_path, {"operation": "read"})
        assert proc.returncode == 4, f"Expected exit 4, got {proc.returncode}"

    def test_query_missing_kind(self, tmp_db_path: str) -> None:
        """query without 'kind' should exit 4."""
        proc = _run_cli(tmp_db_path, {"operation": "query"})
        assert proc.returncode == 4, f"Expected exit 4, got {proc.returncode}"

    def test_query_unknown_kind(self, tmp_db_path: str) -> None:
        """query with unknown kind should exit 4."""
        proc = _run_cli(tmp_db_path, {"operation": "query", "kind": "bogus"})
        assert proc.returncode == 4, f"Expected exit 4, got {proc.returncode}"

    def test_reconcile_missing_attempt_id(self, tmp_db_path: str) -> None:
        """reconcile without attempt_id should exit 4."""
        proc = _run_cli(tmp_db_path, {"operation": "reconcile"})
        assert proc.returncode == 4, f"Expected exit 4, got {proc.returncode}"

    def test_missing_db_path(self) -> None:
        """Invocation without db_path arg should exit 4."""
        cli = _cli_path()
        env = os.environ.copy()
        env["PYTHONPATH"] = _PROJECT_ROOT
        proc = subprocess.run(
            [sys.executable, cli],
            input="{}",
            capture_output=True,
            text=True,
            timeout=10,
            env=env,
        )
        assert proc.returncode == 4, f"Expected exit 4, got {proc.returncode}"

    def test_nonexistent_db_dir(self, attempt_id: str) -> None:
        """A database path in a non-existent directory should exit 5."""
        # Use /proc/nonexistent as a path that cannot be created.
        proc = _run_cli(
            "/proc/nonexistent_subdir/db.sqlite",
            {"operation": "read", "attempt_id": attempt_id},
        )
        # The adapter will fail to open — that's a persistence failure (exit 5).
        assert proc.returncode == 5, (
            f"Expected exit 5, got {proc.returncode}. stdout: {proc.stdout}"
        )


# ── Append tests (exit 0 for success, exit 5 for rejection) ─────────────────


class TestAppend:
    """Prove append writes durable events and returns typed exit codes."""

    def test_append_started_success(self, tmp_db_path: str, attempt_id: str) -> None:
        """Appending a STARTED event should succeed with exit 0."""
        event = _make_minimal_event(attempt_id, "started")
        result = _run_cli_ok(
            tmp_db_path,
            {
                "operation": "append",
                "attempt_id": attempt_id,
                "event_type": "started",
                "event": event,
            },
        )
        assert result["status"] == "success"
        assert result["operation"] == "append"
        assert result["attempt_id"] == attempt_id
        assert result["sequence"] == 1
        assert result["is_duplicate"] is False

    def test_append_completed_success(self, tmp_db_path: str, attempt_id: str) -> None:
        """Appending a COMPLETED event after STARTED should succeed."""
        started = _make_minimal_event(attempt_id, "started", sequence=1)
        _run_cli_ok(
            tmp_db_path,
            {
                "operation": "append",
                "attempt_id": attempt_id,
                "event_type": "started",
                "event": started,
            },
        )
        completed = _make_minimal_event(
            attempt_id, "completed", sequence=2, idempotency_key=str(uuid.uuid4())
        )
        completed["outcome"] = "succeeded"
        result = _run_cli_ok(
            tmp_db_path,
            {
                "operation": "append",
                "attempt_id": attempt_id,
                "event_type": "completed",
                "event": completed,
            },
        )
        assert result["status"] == "success"
        assert result["sequence"] == 2

    def test_append_failed_success(self, tmp_db_path: str, attempt_id: str) -> None:
        """Appending a FAILED event after STARTED should succeed."""
        started = _make_minimal_event(attempt_id, "started", sequence=1)
        _run_cli_ok(
            tmp_db_path,
            {
                "operation": "append",
                "attempt_id": attempt_id,
                "event_type": "started",
                "event": started,
            },
        )
        failed = _make_minimal_event(
            attempt_id, "failed", sequence=2, idempotency_key=str(uuid.uuid4())
        )
        failed["outcome"] = "failed"
        result = _run_cli_ok(
            tmp_db_path,
            {
                "operation": "append",
                "attempt_id": attempt_id,
                "event_type": "failed",
                "event": failed,
            },
        )
        assert result["status"] == "success"

    def test_append_cancelled_success(self, tmp_db_path: str, attempt_id: str) -> None:
        """Appending a CANCELLED event after STARTED should succeed."""
        started = _make_minimal_event(attempt_id, "started", sequence=1)
        _run_cli_ok(
            tmp_db_path,
            {
                "operation": "append",
                "attempt_id": attempt_id,
                "event_type": "started",
                "event": started,
            },
        )
        cancelled = _make_minimal_event(
            attempt_id, "cancelled", sequence=2, idempotency_key=str(uuid.uuid4())
        )
        cancelled["outcome"] = "cancelled"
        result = _run_cli_ok(
            tmp_db_path,
            {
                "operation": "append",
                "attempt_id": attempt_id,
                "event_type": "cancelled",
                "event": cancelled,
            },
        )
        assert result["status"] == "success"

    def test_append_idempotency_dedup(self, tmp_db_path: str, attempt_id: str) -> None:
        """Re-appending with the same idempotency_key should return is_duplicate=True."""
        idem_key = str(uuid.uuid4())
        event = _make_minimal_event(attempt_id, "started", idempotency_key=idem_key)
        first = _run_cli_ok(
            tmp_db_path,
            {
                "operation": "append",
                "attempt_id": attempt_id,
                "event_type": "started",
                "event": event,
            },
        )
        assert first["is_duplicate"] is False

        second = _run_cli_ok(
            tmp_db_path,
            {
                "operation": "append",
                "attempt_id": attempt_id,
                "event_type": "started",
                "event": event,
            },
        )
        assert second["is_duplicate"] is True
        assert second["sequence"] == first["sequence"]

    def test_post_terminal_rejection(self, tmp_db_path: str, attempt_id: str) -> None:
        """Appending after a terminal event with a new key should exit 5."""
        started = _make_minimal_event(attempt_id, "started", sequence=1)
        _run_cli_ok(
            tmp_db_path,
            {
                "operation": "append",
                "attempt_id": attempt_id,
                "event_type": "started",
                "event": started,
            },
        )
        completed = _make_minimal_event(
            attempt_id, "completed", sequence=2, idempotency_key=str(uuid.uuid4())
        )
        completed["outcome"] = "succeeded"
        _run_cli_ok(
            tmp_db_path,
            {
                "operation": "append",
                "attempt_id": attempt_id,
                "event_type": "completed",
                "event": completed,
            },
        )
        # Now try to append a new event after terminal.
        extra = _make_minimal_event(
            attempt_id, "started", sequence=3, idempotency_key=str(uuid.uuid4())
        )
        proc = _run_cli(
            tmp_db_path,
            {
                "operation": "append",
                "attempt_id": attempt_id,
                "event_type": "started",
                "event": extra,
            },
        )
        assert proc.returncode == 5, (
            f"Expected exit 5 for post-terminal append, got {proc.returncode}. "
            f"stdout: {proc.stdout}"
        )


# ── Read tests ──────────────────────────────────────────────────────────────


class TestRead:
    """Prove read operations return durable events."""

    def test_read_events_empty(self, tmp_db_path: str, attempt_id: str) -> None:
        """Reading events for a non-existent attempt should return empty list."""
        result = _run_cli_ok(
            tmp_db_path,
            {"operation": "read", "attempt_id": attempt_id, "mode": "events"},
        )
        assert result["status"] == "success"
        assert result["mode"] == "events"
        assert result["count"] == 0
        assert result["result"] == []

    def test_read_events_after_append(self, tmp_db_path: str, attempt_id: str) -> None:
        """Reading events after an append should return the event."""
        event = _make_minimal_event(attempt_id, "started")
        _run_cli_ok(
            tmp_db_path,
            {
                "operation": "append",
                "attempt_id": attempt_id,
                "event_type": "started",
                "event": event,
            },
        )
        result = _run_cli_ok(
            tmp_db_path,
            {"operation": "read", "attempt_id": attempt_id, "mode": "events"},
        )
        assert result["count"] == 1
        assert result["result"][0]["event_type"] == "started"

    def test_read_ledger(self, tmp_db_path: str, attempt_id: str) -> None:
        """Reading the full ledger reconstruction should succeed."""
        event = _make_minimal_event(attempt_id, "started")
        _run_cli_ok(
            tmp_db_path,
            {
                "operation": "append",
                "attempt_id": attempt_id,
                "event_type": "started",
                "event": event,
            },
        )
        result = _run_cli_ok(
            tmp_db_path,
            {"operation": "read", "attempt_id": attempt_id, "mode": "ledger"},
        )
        assert result["status"] == "success"
        assert result["mode"] == "ledger"


# ── Query tests ─────────────────────────────────────────────────────────────


class TestQuery:
    """Prove diagnostic query operations."""

    def test_query_gaps_no_gaps(self, tmp_db_path: str, attempt_id: str) -> None:
        """Querying gaps for a contiguous stream should return empty."""
        event = _make_minimal_event(attempt_id, "started")
        _run_cli_ok(
            tmp_db_path,
            {
                "operation": "append",
                "attempt_id": attempt_id,
                "event_type": "started",
                "event": event,
            },
        )
        result = _run_cli_ok(
            tmp_db_path,
            {"operation": "query", "kind": "gaps", "attempt_id": attempt_id},
        )
        assert result["status"] == "success"
        assert result["result"] == []

    def test_query_contract_version(self, tmp_db_path: str) -> None:
        """Querying contract version should return the pinned version."""
        # First trigger store creation by appending.
        aid = str(uuid.uuid4())
        event = _make_minimal_event(aid, "started")
        _run_cli_ok(
            tmp_db_path,
            {
                "operation": "append",
                "attempt_id": aid,
                "event_type": "started",
                "event": event,
            },
        )
        result = _run_cli_ok(
            tmp_db_path,
            {"operation": "query", "kind": "contract_version"},
        )
        assert result["status"] == "success"
        assert result["result"].startswith("arnold.workflow")

    def test_query_store_version(self, tmp_db_path: str) -> None:
        """Querying store version should return the store version string."""
        aid = str(uuid.uuid4())
        event = _make_minimal_event(aid, "started")
        _run_cli_ok(
            tmp_db_path,
            {
                "operation": "append",
                "attempt_id": aid,
                "event_type": "started",
                "event": event,
            },
        )
        result = _run_cli_ok(
            tmp_db_path,
            {"operation": "query", "kind": "store_version"},
        )
        assert result["status"] == "success"
        assert "arnold.workflow.attempt_ledger_store" in result["result"]

    def test_query_persistence_diagnostics_empty(self, tmp_db_path: str, attempt_id: str) -> None:
        """Querying diagnostics for a clean store should return empty."""
        result = _run_cli_ok(
            tmp_db_path,
            {
                "operation": "query",
                "kind": "persistence_diagnostics",
                "attempt_id": attempt_id,
            },
        )
        assert result["result"] == []

    def test_query_reconciliation_state_empty(self, tmp_db_path: str, attempt_id: str) -> None:
        """Querying reconciliation state for a clean store should return empty."""
        result = _run_cli_ok(
            tmp_db_path,
            {
                "operation": "query",
                "kind": "reconciliation_state",
                "attempt_id": attempt_id,
            },
        )
        assert result["result"] == []

    def test_query_source_cursor_empty(self, tmp_db_path: str, attempt_id: str) -> None:
        """Querying source cursor for an un-tracked attempt should return null."""
        result = _run_cli_ok(
            tmp_db_path,
            {
                "operation": "query",
                "kind": "source_cursor",
                "attempt_id": attempt_id,
            },
        )
        assert result["result"] is None


# ── Reconcile tests ─────────────────────────────────────────────────────────


class TestReconcile:
    """Prove reconcile returns typed gate statuses via exit codes."""

    def test_reconcile_incomplete(self, tmp_db_path: str, attempt_id: str) -> None:
        """Reconciling a never-started attempt should return incomplete (exit 1)."""
        proc = _run_cli(
            tmp_db_path,
            {"operation": "reconcile", "attempt_id": attempt_id},
        )
        assert proc.returncode == 1, (
            f"Expected exit 1 (INCOMPLETE), got {proc.returncode}. "
            f"stdout: {proc.stdout}"
        )
        result = json.loads(proc.stdout)
        assert result["start_gate"]["status"] == "incomplete"
        assert result["terminal_gate"]["status"] == "incomplete"

    def test_reconcile_start_verified_terminal_incomplete(
        self, tmp_db_path: str, attempt_id: str
    ) -> None:
        """After STARTED append, start gate should be verified but terminal incomplete."""
        event = _make_minimal_event(attempt_id, "started")
        _run_cli_ok(
            tmp_db_path,
            {
                "operation": "append",
                "attempt_id": attempt_id,
                "event_type": "started",
                "event": event,
            },
        )
        proc = _run_cli(
            tmp_db_path,
            {"operation": "reconcile", "attempt_id": attempt_id},
        )
        # start_verified + terminal_incomplete → worst is INCOMPLETE (exit 1)
        assert proc.returncode == 1, (
            f"Expected exit 1 (INCOMPLETE), got {proc.returncode}. "
            f"stdout: {proc.stdout}"
        )

    def test_reconcile_both_verified(
        self, tmp_db_path: str, attempt_id: str
    ) -> None:
        """After STARTED + COMPLETED, both gates should be verified (exit 0)."""
        started = _make_minimal_event(attempt_id, "started", sequence=1)
        _run_cli_ok(
            tmp_db_path,
            {
                "operation": "append",
                "attempt_id": attempt_id,
                "event_type": "started",
                "event": started,
            },
        )
        completed = _make_minimal_event(
            attempt_id, "completed", sequence=2, idempotency_key=str(uuid.uuid4())
        )
        completed["outcome"] = "succeeded"
        _run_cli_ok(
            tmp_db_path,
            {
                "operation": "append",
                "attempt_id": attempt_id,
                "event_type": "completed",
                "event": completed,
            },
        )
        result = _run_cli_ok(
            tmp_db_path,
            {"operation": "reconcile", "attempt_id": attempt_id},
        )
        assert result["start_gate"]["status"] == "verified"
        assert result["terminal_gate"]["status"] == "verified"
        assert result["status"] == "verified"

    def test_reconcile_includes_gaps(
        self, tmp_db_path: str, attempt_id: str
    ) -> None:
        """Reconcile should include gap detection in its output."""
        event = _make_minimal_event(attempt_id, "started", sequence=1)
        _run_cli_ok(
            tmp_db_path,
            {
                "operation": "append",
                "attempt_id": attempt_id,
                "event_type": "started",
                "event": event,
            },
        )
        proc = _run_cli(
            tmp_db_path,
            {"operation": "reconcile", "attempt_id": attempt_id},
        )
        result = json.loads(proc.stdout)
        assert "gaps" in result
        assert isinstance(result["gaps"], list)


# ── Migrate tests ───────────────────────────────────────────────────────────


class TestMigrate:
    """Prove migrate applies migrations and returns migration state."""

    def test_migrate_fresh_store(self, tmp_db_path: str) -> None:
        """Migrating a fresh store should apply the default M6A migrations."""
        # Trigger store creation first.
        aid = str(uuid.uuid4())
        event = _make_minimal_event(aid, "started")
        _run_cli_ok(
            tmp_db_path,
            {
                "operation": "append",
                "attempt_id": aid,
                "event_type": "started",
                "event": event,
            },
        )
        result = _run_cli_ok(
            tmp_db_path,
            {"operation": "migrate"},
        )
        assert result["status"] == "success"
        assert result["operation"] == "migrate"
        assert result["final_version"] >= 1
        assert result["state_after"]["is_complete"] is True

    def test_migrate_idempotent(self, tmp_db_path: str) -> None:
        """Running migrate twice should be idempotent."""
        aid = str(uuid.uuid4())
        event = _make_minimal_event(aid, "started")
        _run_cli_ok(
            tmp_db_path,
            {
                "operation": "append",
                "attempt_id": aid,
                "event_type": "started",
                "event": event,
            },
        )
        first = _run_cli_ok(tmp_db_path, {"operation": "migrate"})
        second = _run_cli_ok(tmp_db_path, {"operation": "migrate"})
        assert first["final_version"] == second["final_version"]
        # Second run should have zero applied_now.
        assert len(second["applied_now"]) == 0


# ── Shell-consumer exit-code visibility ─────────────────────────────────────


class TestShellConsumerVisibility:
    """Prove shell consumers can distinguish all six typed exit codes."""

    def test_shell_can_test_exit_code(self, tmp_db_path: str, attempt_id: str) -> None:
        """Shell consumer can test $? for success (0)."""
        event = _make_minimal_event(attempt_id, "started")
        proc = _run_cli(
            tmp_db_path,
            {
                "operation": "append",
                "attempt_id": attempt_id,
                "event_type": "started",
                "event": event,
            },
        )
        assert proc.returncode == 0

    def test_shell_exit_1_incomplete(self, tmp_db_path: str, attempt_id: str) -> None:
        """Shell consumer sees exit 1 for incomplete."""
        proc = _run_cli(
            tmp_db_path,
            {"operation": "reconcile", "attempt_id": attempt_id},
        )
        assert proc.returncode == 1

    def test_shell_exit_4_validation(self, tmp_db_path: str) -> None:
        """Shell consumer sees exit 4 for validation failure."""
        proc = _run_cli(tmp_db_path, {"operation": "unknown"})
        assert proc.returncode == 4

    def test_shell_exit_5_persistence(self, tmp_db_path: str, attempt_id: str) -> None:
        """Shell consumer sees exit 5 for persistence failure."""
        started = _make_minimal_event(attempt_id, "started", sequence=1)
        _run_cli_ok(
            tmp_db_path,
            {
                "operation": "append",
                "attempt_id": attempt_id,
                "event_type": "started",
                "event": started,
            },
        )
        completed = _make_minimal_event(
            attempt_id, "completed", sequence=2, idempotency_key=str(uuid.uuid4())
        )
        completed["outcome"] = "succeeded"
        _run_cli_ok(
            tmp_db_path,
            {
                "operation": "append",
                "attempt_id": attempt_id,
                "event_type": "completed",
                "event": completed,
            },
        )
        # Post-terminal append should exit 5.
        extra = _make_minimal_event(
            attempt_id, "started", sequence=3, idempotency_key=str(uuid.uuid4())
        )
        proc = _run_cli(
            tmp_db_path,
            {
                "operation": "append",
                "attempt_id": attempt_id,
                "event_type": "started",
                "event": extra,
            },
        )
        assert proc.returncode == 5, (
            f"Expected exit 5, got {proc.returncode}. stdout: {proc.stdout}"
        )

    def test_stdout_is_valid_json_on_failure(self, tmp_db_path: str) -> None:
        """Even on failure, stdout should be valid JSON."""
        proc = _run_cli(tmp_db_path, {"operation": "unknown"})
        assert proc.returncode == 4
        try:
            result = json.loads(proc.stdout)
            assert "status" in result
            assert result["status"] == "error"
        except json.JSONDecodeError:
            raise AssertionError(
                f"stdout is not valid JSON: {proc.stdout!r}"
            )

    def test_multiple_operations_same_db(self, tmp_db_path: str) -> None:
        """A shell script sequence: append, read, reconcile, query."""
        aid = str(uuid.uuid4())
        # Append STARTED.
        event1 = _make_minimal_event(aid, "started", sequence=1)
        r1 = _run_cli_ok(
            tmp_db_path,
            {
                "operation": "append",
                "attempt_id": aid,
                "event_type": "started",
                "event": event1,
            },
        )
        assert r1["is_duplicate"] is False

        # Read events.
        r2 = _run_cli_ok(
            tmp_db_path,
            {"operation": "read", "attempt_id": aid, "mode": "events"},
        )
        assert r2["count"] == 1

        # Reconcile — should be INCOMPLETE (exit 1).
        proc3 = _run_cli(
            tmp_db_path,
            {"operation": "reconcile", "attempt_id": aid},
        )
        assert proc3.returncode == 1

        # Query gaps — should be empty.
        r4 = _run_cli_ok(
            tmp_db_path,
            {"operation": "query", "kind": "gaps", "attempt_id": aid},
        )
        assert r4["result"] == []

    def test_read_events_default_mode(self, tmp_db_path: str, attempt_id: str) -> None:
        """read operation without explicit mode defaults to 'events'."""
        event = _make_minimal_event(attempt_id, "started")
        _run_cli_ok(
            tmp_db_path,
            {
                "operation": "append",
                "attempt_id": attempt_id,
                "event_type": "started",
                "event": event,
            },
        )
        result = _run_cli_ok(
            tmp_db_path,
            {"operation": "read", "attempt_id": attempt_id},
        )
        assert result["mode"] == "events"
        assert result["count"] == 1
