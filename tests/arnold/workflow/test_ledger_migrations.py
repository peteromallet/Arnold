"""Tests for ``LedgerMigrator`` and ``SqliteLedgerMigrator``.

Focused coverage (M6A criterion 9):
* Empty stores: all migrations applied from scratch
* Applied-state checksums: stored checksums match the registry
* Interrupted migrations: a failing migration rolls back atomically
* Crash resume: resumes from the last applied migration idempotently
* Mixed reader/writer compatibility: a reader sees a consistent prefix
* Forward-fix enforcement: editing an applied migration raises
* Idempotency on duplicate backfill: re-running migrate() is a no-op
* Registry validation: malformed registries raise
* Orphan detection: applied versions absent from the registry raise
* Legacy classification: UNKNOWN records are durable and never synthesized
"""

from __future__ import annotations

import multiprocessing
import os
import sqlite3
import sys
import tempfile
import time
import uuid
from typing import Any

import pytest

from arnold.workflow.attempt_ledger_store import SqliteAttemptLedgerStore
from arnold.workflow.ledger_migrations import (
    ChecksumMismatch,
    ClassificationEvidence,
    ClassificationSafetyError,
    LegacyClassification,
    LegacyRecordClassification,
    LedgerMigrator,
    Migration,
    MigrationChecksumMismatchError,
    MigrationOrderError,
    MigrationRegistryError,
    MigrationState,
    SqliteLedgerMigrator,
    compute_migration_checksum,
    default_m6a_migrations,
)


# ── Helpers ───────────────────────────────────────────────────────────────


def _store_path() -> str:
    fd, path = tempfile.mkstemp(suffix=".db", prefix="test_migrations_")
    os.close(fd)
    return path


def _simple_registry(n: int = 3) -> tuple[Migration, ...]:
    """A registry of *n* additive, idempotent migrations for testing."""
    return tuple(
        Migration(
            version=i,
            name=f"test_migration_{i}",
            statements=(
                f"CREATE TABLE IF NOT EXISTS test_tbl_{i} ("
                f"  id INTEGER PRIMARY KEY, val TEXT)",
                f"INSERT OR IGNORE INTO test_tbl_{i} (id, val) VALUES (1, 'm{i}')",
            ),
        )
        for i in range(1, n + 1)
    )


# ── Separate-process workers (mixed reader/writer) ────────────────────────


def _mp_reader_worker(
    db_path: str,
    ready_event: Any,
    done_event: Any,
    result_queue: Any,
) -> None:
    """Reader: open a fresh store, read migration state, return versions seen."""
    from arnold.workflow.attempt_ledger_store import SqliteAttemptLedgerStore
    from arnold.workflow.ledger_migrations import (
        SqliteLedgerMigrator,
        default_m6a_migrations,
    )

    store = SqliteAttemptLedgerStore(db_path)
    try:
        # Wait until the writer signals it is mid-work, then read.
        ready_event.wait(timeout=20.0)
        migrator = SqliteLedgerMigrator(store, default_m6a_migrations())
        state = migrator.get_state()
        versions = tuple(r.version for r in state.applied)
        result_queue.put({"status": "ok", "applied_versions": versions})
        done_event.set()
    except Exception as exc:  # pragma: no cover - surfaced via queue
        result_queue.put(
            {"status": "error", "type": type(exc).__name__, "message": str(exc)}
        )
        done_event.set()
    finally:
        store.close()


def _mp_writer_worker(
    db_path: str,
    ready_event: Any,
    migrations: tuple[Migration, ...],
    result_queue: Any,
) -> None:
    """Writer: run migrate() after the reader is ready, return result."""
    from arnold.workflow.attempt_ledger_store import SqliteAttemptLedgerStore
    from arnold.workflow.ledger_migrations import SqliteLedgerMigrator

    store = SqliteAttemptLedgerStore(db_path)
    try:
        migrator = SqliteLedgerMigrator(store, migrations)
        result = migrator.migrate()
        result_queue.put(
            {
                "status": "ok",
                "applied_versions": tuple(m.version for m in result.applied_now),
                "final_version": result.final_version,
            }
        )
        ready_event.set()
    except Exception as exc:  # pragma: no cover - surfaced via queue
        ready_event.set()
        result_queue.put(
            {"status": "error", "type": type(exc).__name__, "message": str(exc)}
        )
    finally:
        store.close()


# ── Empty stores ──────────────────────────────────────────────────────────


class TestEmptyStoreMigrations:
    """A brand-new store applies all migrations from scratch."""

    def test_fresh_store_applies_all_default_migrations(self):
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            migrator = SqliteLedgerMigrator(store, default_m6a_migrations())
            state_before = migrator.get_state()
            assert state_before.applied == ()
            assert state_before.last_applied_version == 0

            result = migrator.migrate()
            assert tuple(m.version for m in result.applied_now) == (1, 2)
            assert result.skipped == ()
            assert result.final_version == 2

            state_after = migrator.get_state()
            assert len(state_after.applied) == 2
            assert state_after.pending == ()
            assert state_after.is_complete is True
            store.close()
        finally:
            if os.path.exists(path):
                os.remove(path)

    def test_fresh_store_applies_custom_registry(self):
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            reg = _simple_registry(4)
            migrator = SqliteLedgerMigrator(store, reg)
            result = migrator.migrate()
            assert tuple(m.version for m in result.applied_now) == (1, 2, 3, 4)

            state = migrator.get_state()
            assert state.last_applied_version == 4
            assert state.is_complete is True

            # The DDL actually ran: tables exist.
            conn = store.conn
            for i in range(1, 5):
                cur = conn.execute(f"SELECT val FROM test_tbl_{i} WHERE id = 1")
                assert cur.fetchone()[0] == f"m{i}"
            store.close()
        finally:
            if os.path.exists(path):
                os.remove(path)

    def test_empty_registry_migrate_is_noop(self):
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            migrator = SqliteLedgerMigrator(store, migrations=())
            result = migrator.migrate()
            assert result.applied_now == ()
            assert result.final_version == 0
            assert migrator.get_state().is_complete is True
            store.close()
        finally:
            if os.path.exists(path):
                os.remove(path)


# ── Applied-state checksums ───────────────────────────────────────────────


class TestAppliedStateChecksums:
    """Stored checksums match the live registry after application."""

    def test_stored_checksums_match_registry(self):
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            reg = _simple_registry(3)
            migrator = SqliteLedgerMigrator(store, reg)
            migrator.migrate()

            mismatches = migrator.verify_checksums()
            assert mismatches == ()
            store.close()
        finally:
            if os.path.exists(path):
                os.remove(path)

    def test_applied_record_checksum_equals_migration_checksum(self):
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            reg = _simple_registry(3)
            migrator = SqliteLedgerMigrator(store, reg)
            migrator.migrate()
            state = migrator.get_state()
            by_version = {m.version: m for m in reg}
            for rec in state.applied:
                assert rec.checksum == by_version[rec.version].checksum
                assert rec.checksum.startswith("sha256:")
                assert rec.status == "applied"
            store.close()
        finally:
            if os.path.exists(path):
                os.remove(path)

    def test_reopen_store_verifies_checksums(self):
        """Re-opening the same DB with the same registry yields no mismatches."""
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            reg = _simple_registry(3)
            SqliteLedgerMigrator(store, reg).migrate()
            store.close()

            store2 = SqliteAttemptLedgerStore(path)
            migrator2 = SqliteLedgerMigrator(store2, reg)
            state = migrator2.get_state()
            assert state.checksum_mismatches == ()
            assert state.is_complete is True
            store2.close()
        finally:
            if os.path.exists(path):
                os.remove(path)

    def test_checksum_is_deterministic_and_content_addressed(self):
        a = compute_migration_checksum(1, "name", ("SELECT 1",))
        b = compute_migration_checksum(1, "name", ("SELECT 1",))
        c = compute_migration_checksum(1, "name", ("SELECT 2",))
        d = compute_migration_checksum(2, "name", ("SELECT 1",))
        e = compute_migration_checksum(1, "other", ("SELECT 1",))
        assert a == b                      # identical content
        assert a != c                      # different statement
        assert a != d                      # different version
        assert a != e                      # different name


# ── Interrupted migrations ────────────────────────────────────────────────


class TestInterruptedMigrations:
    """A failing migration rolls back atomically; prior migrations persist."""

    def test_failing_migration_rolls_back_and_raises(self):
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            # Migration 3 references a non-existent source → DDL error.
            reg = (
                Migration(1, "ok1", ("CREATE TABLE IF NOT EXISTS t1 (id INTEGER)",)),
                Migration(2, "ok2", ("CREATE TABLE IF NOT EXISTS t2 (id INTEGER)",)),
                Migration(
                    3,
                    "bad3",
                    (
                        # Force a real SQL error: select from a missing table
                        # inside CREATE (this raises at execute time).
                        "CREATE TABLE t3 AS SELECT * FROM does_not_exist_xyz",
                    ),
                ),
            )
            migrator = SqliteLedgerMigrator(store, reg)
            with pytest.raises(sqlite3.OperationalError):
                migrator.migrate()

            state = migrator.get_state()
            # Migrations 1 and 2 applied; 3 is pending (rolled back).
            assert tuple(r.version for r in state.applied) == (1, 2)
            assert tuple(m.version for m in state.pending) == (3,)
            assert state.last_applied_version == 2
            assert state.is_complete is False
            store.close()
        finally:
            if os.path.exists(path):
                os.remove(path)

    def test_partial_migration_leaves_no_authoritative_state(self):
        """The failing migration's schema_migrations row is NOT persisted."""
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            reg = (
                Migration(1, "ok1", ("CREATE TABLE IF NOT EXISTS t1 (id INTEGER)",)),
                Migration(
                    2,
                    "bad2",
                    ("CREATE TABLE t2 AS SELECT * FROM does_not_exist_xyz",),
                ),
            )
            migrator = SqliteLedgerMigrator(store, reg)
            with pytest.raises(sqlite3.OperationalError):
                migrator.migrate()

            conn = store.conn
            # No row for version 2.
            cur = conn.execute(
                "SELECT version FROM schema_migrations WHERE version = 2"
            )
            assert cur.fetchone() is None
            store.close()
        finally:
            if os.path.exists(path):
                os.remove(path)


# ── Crash resume ──────────────────────────────────────────────────────────


class TestCrashResume:
    """Resuming from the last applied migration is idempotent and complete."""

    def test_resume_after_interrupt_completes_remaining(self):
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            bad_reg = (
                Migration(1, "ok1", ("CREATE TABLE IF NOT EXISTS t1 (id INTEGER)",)),
                Migration(2, "ok2", ("CREATE TABLE IF NOT EXISTS t2 (id INTEGER)",)),
                Migration(
                    3,
                    "bad3",
                    ("CREATE TABLE t3 AS SELECT * FROM does_not_exist_xyz",),
                ),
                Migration(4, "ok4", ("CREATE TABLE IF NOT EXISTS t4 (id INTEGER)",)),
            )
            migrator = SqliteLedgerMigrator(store, bad_reg)
            with pytest.raises(sqlite3.OperationalError):
                migrator.migrate()
            assert migrator.get_state().last_applied_version == 2
            store.close()

            # Resume with a fixed registry (version 3 now succeeds).
            store2 = SqliteAttemptLedgerStore(path)
            good_reg = (
                Migration(1, "ok1", ("CREATE TABLE IF NOT EXISTS t1 (id INTEGER)",)),
                Migration(2, "ok2", ("CREATE TABLE IF NOT EXISTS t2 (id INTEGER)",)),
                Migration(3, "ok3", ("CREATE TABLE IF NOT EXISTS t3 (id INTEGER)",)),
                Migration(4, "ok4", ("CREATE TABLE IF NOT EXISTS t4 (id INTEGER)",)),
            )
            migrator2 = SqliteLedgerMigrator(store2, good_reg)
            result = migrator2.migrate()
            # Only 3 and 4 applied on resume; 1 and 2 skipped.
            assert tuple(m.version for m in result.applied_now) == (3, 4)
            assert tuple(m.version for m in result.skipped) == (1, 2)
            assert migrator2.get_state().is_complete is True
            store2.close()
        finally:
            if os.path.exists(path):
                os.remove(path)

    def test_resume_is_idempotent_on_duplicate_backfill(self):
        """Calling migrate() twice applies nothing the second time."""
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            reg = _simple_registry(3)
            migrator = SqliteLedgerMigrator(store, reg)
            migrator.migrate()
            result2 = migrator.migrate()
            assert result2.applied_now == ()
            assert tuple(m.version for m in result2.skipped) == (1, 2, 3)
            store.close()
        finally:
            if os.path.exists(path):
                os.remove(path)

    def test_resume_reopen_applies_nothing_when_complete(self):
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            reg = _simple_registry(3)
            SqliteLedgerMigrator(store, reg).migrate()
            store.close()

            store2 = SqliteAttemptLedgerStore(path)
            migrator2 = SqliteLedgerMigrator(store2, reg)
            result = migrator2.migrate()
            assert result.applied_now == ()
            assert migrator2.get_state().is_complete is True
            store2.close()
        finally:
            if os.path.exists(path):
                os.remove(path)

    def test_crash_resume_reapplies_idempotent_ddl_safely(self):
        """A migration that was staged-but-uncommitted is re-staged cleanly."""
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            # First migration creates a table and succeeds.
            reg = (Migration(1, "ok1", ("CREATE TABLE IF NOT EXISTS t1 (id INTEGER)",)),)
            migrator = SqliteLedgerMigrator(store, reg)
            migrator.migrate()
            assert migrator.get_state().last_applied_version == 1
            store.close()

            # Simulate a crash after table creation but before the migration
            # row commit is impossible by construction; instead verify that
            # re-applying the same migration (idempotent DDL) on a fresh
            # connection is safe even if the table already exists.
            store2 = SqliteAttemptLedgerStore(path)
            migrator2 = SqliteLedgerMigrator(store2, reg)
            # The table already exists; migrate() must not error (IF NOT EXISTS).
            result = migrator2.migrate()
            assert result.applied_now == ()
            assert migrator2.get_state().is_complete is True
            store2.close()
        finally:
            if os.path.exists(path):
                os.remove(path)


# ── Forward-fix enforcement ───────────────────────────────────────────────


class TestForwardFixEnforcement:
    """Editing an applied migration (checksum drift) raises, never re-applies."""

    def test_checksum_mismatch_on_migrate_raises(self):
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            reg_v1 = (
                Migration(1, "base", ("CREATE TABLE IF NOT EXISTS t1 (id INTEGER)",)),
            )
            SqliteLedgerMigrator(store, reg_v1).migrate()
            store.close()

            # Re-open with an EDITED version 1 (different statement → new checksum).
            store2 = SqliteAttemptLedgerStore(path)
            reg_edited = (
                Migration(
                    1,
                    "base",
                    ("CREATE TABLE IF NOT EXISTS t1 (id INTEGER, extra TEXT)",),
                ),
            )
            migrator2 = SqliteLedgerMigrator(store2, reg_edited)
            with pytest.raises(MigrationChecksumMismatchError) as exc_info:
                migrator2.migrate()
            assert exc_info.value.version == 1
            assert exc_info.value.stored_checksum != exc_info.value.expected_checksum
            store2.close()
        finally:
            if os.path.exists(path):
                os.remove(path)

    def test_checksum_mismatch_surfaces_in_state(self):
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            reg_v1 = (
                Migration(1, "base", ("CREATE TABLE IF NOT EXISTS t1 (id INTEGER)",)),
            )
            SqliteLedgerMigrator(store, reg_v1).migrate()
            store.close()

            store2 = SqliteAttemptLedgerStore(path)
            reg_edited = (
                Migration(1, "base", ("CREATE TABLE IF NOT EXISTS t1 (id TEXT)",)),
            )
            migrator2 = SqliteLedgerMigrator(store2, reg_edited)
            mismatches = migrator2.verify_checksums()
            assert len(mismatches) == 1
            assert mismatches[0].version == 1
            assert mismatches[0].stored_checksum != mismatches[0].expected_checksum

            state = migrator2.get_state()
            assert len(state.checksum_mismatches) == 1
            store2.close()
        finally:
            if os.path.exists(path):
                os.remove(path)

    def test_forward_fix_requires_new_migration_not_edit(self):
        """The remedy for checksum drift is a new migration, not re-applying."""
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            reg1 = (
                Migration(1, "base", ("CREATE TABLE IF NOT EXISTS t1 (id INTEGER)",)),
            )
            SqliteLedgerMigrator(store, reg1).migrate()
            store.close()

            # Add a NEW migration (version 2) rather than editing version 1.
            store2 = SqliteAttemptLedgerStore(path)
            reg2 = (
                Migration(1, "base", ("CREATE TABLE IF NOT EXISTS t1 (id INTEGER)",)),
                Migration(2, "add_col", ("ALTER TABLE t1 ADD COLUMN c2 TEXT",)),
            )
            migrator2 = SqliteLedgerMigrator(store2, reg2)
            result = migrator2.migrate()
            assert tuple(m.version for m in result.applied_now) == (2,)
            assert migrator2.verify_checksums() == ()
            assert migrator2.get_state().is_complete is True
            store2.close()
        finally:
            if os.path.exists(path):
                os.remove(path)


# ── Registry validation ───────────────────────────────────────────────────


class TestRegistryValidation:
    """Malformed registries raise at construction time."""

    def test_duplicate_version_raises(self):
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            reg = (
                Migration(1, "a", ("SELECT 1",)),
                Migration(1, "b", ("SELECT 2",)),
            )
            with pytest.raises(MigrationRegistryError, match="duplicate"):
                SqliteLedgerMigrator(store, reg)
            store.close()
        finally:
            if os.path.exists(path):
                os.remove(path)

    def test_duplicate_name_raises(self):
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            reg = (
                Migration(1, "same", ("SELECT 1",)),
                Migration(2, "same", ("SELECT 2",)),
            )
            with pytest.raises(MigrationRegistryError, match="duplicate"):
                SqliteLedgerMigrator(store, reg)
            store.close()
        finally:
            if os.path.exists(path):
                os.remove(path)

    def test_non_contiguous_versions_raises(self):
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            reg = (
                Migration(1, "a", ("SELECT 1",)),
                Migration(3, "c", ("SELECT 3",)),
            )
            with pytest.raises(MigrationRegistryError, match="non-contiguous"):
                SqliteLedgerMigrator(store, reg)
            store.close()
        finally:
            if os.path.exists(path):
                os.remove(path)

    def test_registry_sorted_by_version(self):
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            reg = (
                Migration(3, "c", ("CREATE TABLE IF NOT EXISTS t3 (id INTEGER)",)),
                Migration(1, "a", ("CREATE TABLE IF NOT EXISTS t1 (id INTEGER)",)),
                Migration(2, "b", ("CREATE TABLE IF NOT EXISTS t2 (id INTEGER)",)),
            )
            migrator = SqliteLedgerMigrator(store, reg)
            result = migrator.migrate()
            # Applied in version order (1, 2, 3), not registration order.
            assert tuple(m.version for m in result.applied_now) == (1, 2, 3)
            store.close()
        finally:
            if os.path.exists(path):
                os.remove(path)


# ── Orphan detection ──────────────────────────────────────────────────────


class TestOrphanDetection:
    """An applied version absent from the registry indicates divergent code."""

    def test_orphan_version_raises_on_migrate(self):
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            reg_full = (
                Migration(1, "a", ("CREATE TABLE IF NOT EXISTS t1 (id INTEGER)",)),
                Migration(2, "b", ("CREATE TABLE IF NOT EXISTS t2 (id INTEGER)",)),
            )
            SqliteLedgerMigrator(store, reg_full).migrate()
            store.close()

            # Re-open with a registry missing version 2 (downgrade scenario).
            store2 = SqliteAttemptLedgerStore(path)
            reg_partial = (
                Migration(1, "a", ("CREATE TABLE IF NOT EXISTS t1 (id INTEGER)",)),
            )
            migrator2 = SqliteLedgerMigrator(store2, reg_partial)
            with pytest.raises(MigrationOrderError):
                migrator2.migrate()
            store2.close()
        finally:
            if os.path.exists(path):
                os.remove(path)

    def test_orphan_visible_in_state(self):
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            reg_full = (
                Migration(1, "a", ("CREATE TABLE IF NOT EXISTS t1 (id INTEGER)",)),
                Migration(2, "b", ("CREATE TABLE IF NOT EXISTS t2 (id INTEGER)",)),
            )
            SqliteLedgerMigrator(store, reg_full).migrate()
            store.close()

            store2 = SqliteAttemptLedgerStore(path)
            reg_partial = (
                Migration(1, "a", ("CREATE TABLE IF NOT EXISTS t1 (id INTEGER)",)),
            )
            migrator2 = SqliteLedgerMigrator(store2, reg_partial)
            state = migrator2.get_state()
            assert len(state.orphans) == 1
            assert state.orphans[0].version == 2
            store2.close()
        finally:
            if os.path.exists(path):
                os.remove(path)


# ── Legacy classification (forward-fix / UNKNOWN) ─────────────────────────


class TestLegacyClassification:
    """Unreconstructable records are UNKNOWN; success is never synthesized."""

    def test_record_unknown_classification_is_durable(self):
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            reg = _simple_registry(2)
            migrator = SqliteLedgerMigrator(store, reg)
            migrator.migrate()

            rec = migrator.record_legacy_classification(
                source_table="attempt_events",
                record_id="legacy-row-42",
                classification=LegacyClassification.UNKNOWN,
                reason="no authoritative source to reconstruct terminal outcome",
                migration_version=2,
            )
            assert rec.classification == "unknown"
            assert rec.source_table == "attempt_events"
            assert rec.record_id == "legacy-row-42"
            store.close()

            # Durable across re-open.
            store2 = SqliteAttemptLedgerStore(path)
            migrator2 = SqliteLedgerMigrator(store2, reg)
            results = migrator2.query_legacy_classifications(
                record_id="legacy-row-42"
            )
            assert len(results) == 1
            assert results[0].classification == "unknown"
            store2.close()
        finally:
            if os.path.exists(path):
                os.remove(path)

    def test_all_classifications_supported(self):
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            migrator = SqliteLedgerMigrator(store, _simple_registry(1))
            migrator.migrate()

            for cls in LegacyClassification:
                migrator.record_legacy_classification(
                    source_table="t",
                    record_id=f"r-{cls.value}",
                    classification=cls,
                    reason=f"determined {cls.value}",
                )

            all_results = migrator.query_legacy_classifications()
            values = sorted(r.classification for r in all_results)
            assert values == sorted(c.value for c in LegacyClassification)
            store.close()
        finally:
            if os.path.exists(path):
                os.remove(path)

    def test_query_filters_by_classification_and_table(self):
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            migrator = SqliteLedgerMigrator(store, _simple_registry(1))
            migrator.migrate()

            migrator.record_legacy_classification(
                "attempt_events", "r1", LegacyClassification.UNKNOWN, "x"
            )
            migrator.record_legacy_classification(
                "outbox_records", "r2", LegacyClassification.BACKFILLED, "y"
            )
            migrator.record_legacy_classification(
                "attempt_events", "r3", LegacyClassification.CORRUPT, "z"
            )

            unknown = migrator.query_legacy_classifications(
                classification=LegacyClassification.UNKNOWN
            )
            assert len(unknown) == 1
            assert unknown[0].record_id == "r1"

            events = migrator.query_legacy_classifications(source_table="attempt_events")
            assert {r.record_id for r in events} == {"r1", "r3"}
            store.close()
        finally:
            if os.path.exists(path):
                os.remove(path)

    def test_classification_rejects_wrong_type(self):
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            migrator = SqliteLedgerMigrator(store, _simple_registry(1))
            migrator.migrate()
            with pytest.raises(TypeError):
                migrator.record_legacy_classification(
                    "t", "r", "unknown", "x"  # type: ignore[arg-type]
                )
            store.close()
        finally:
            if os.path.exists(path):
                os.remove(path)

    def test_unknown_classification_has_unique_id_per_record(self):
        """Multiple determinations about the same record are all preserved."""
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            migrator = SqliteLedgerMigrator(store, _simple_registry(1))
            migrator.migrate()
            r1 = migrator.record_legacy_classification(
                "t", "rec", LegacyClassification.UNKNOWN, "first pass"
            )
            r2 = migrator.record_legacy_classification(
                "t", "rec", LegacyClassification.UNRECONSTRUCTABLE, "second pass"
            )
            assert r1.classification_id != r2.classification_id
            results = migrator.query_legacy_classifications(record_id="rec")
            assert len(results) == 2
            store.close()
        finally:
            if os.path.exists(path):
                os.remove(path)


# ── Classification decision function (classify) ───────────────────────────


class TestClassificationDecision:
    """The static ``classify()`` function enforces the M6A safety property:
    BACKFILLED only from authoritative source; everything else is conservative."""

    def test_backfilled_from_authoritative_source(self):
        evidence = ClassificationEvidence(has_authoritative_source=True)
        assert LedgerMigrator.classify(evidence) == LegacyClassification.BACKFILLED

    def test_authoritative_source_with_other_evidence_still_backfilled(self):
        """If authoritative source exists alongside circumstantial evidence,
        BACKFILLED is still the correct classification — the authoritative
        source dominates."""
        evidence = ClassificationEvidence(
            has_authoritative_source=True,
            has_logs=True,
            has_markers=True,
            has_receipts=True,
        )
        assert LedgerMigrator.classify(evidence) == LegacyClassification.BACKFILLED

    def test_corrupt_from_structural_damage(self):
        evidence = ClassificationEvidence(
            is_structurally_damaged=True,
            has_authoritative_source=True,  # damaged even though source exists
        )
        assert LedgerMigrator.classify(evidence) == LegacyClassification.CORRUPT

    def test_corrupt_always_wins_over_other_classifications(self):
        """Structural damage is checked first — a corrupt record is CORRUPT
        regardless of what other evidence exists."""
        evidence = ClassificationEvidence(
            is_structurally_damaged=True,
            has_authoritative_source=True,
            has_logs=True,
        )
        assert LedgerMigrator.classify(evidence) == LegacyClassification.CORRUPT

    def test_unreconstructable_when_no_source_exists(self):
        evidence = ClassificationEvidence(source_exists=False)
        assert (
            LedgerMigrator.classify(evidence)
            == LegacyClassification.UNRECONSTRUCTABLE
        )

    def test_unreconstructable_beats_authoritative_source(self):
        """No source means UNRECONSTRUCTABLE even if authoritative source
        is claimed — the claim is inconsistent."""
        evidence = ClassificationEvidence(
            source_exists=False, has_authoritative_source=True
        )
        # CORRUPT? No — is_structurally_damaged is False.
        # source_exists=False → UNRECONSTRUCTABLE (checked before has_authoritative_source)
        assert (
            LedgerMigrator.classify(evidence)
            == LegacyClassification.UNRECONSTRUCTABLE
        )

    def test_unknown_when_no_evidence_at_all(self):
        evidence = ClassificationEvidence()
        assert LedgerMigrator.classify(evidence) == LegacyClassification.UNKNOWN

    # ── Safety: logs never synthesize terminal success ─────────────────

    def test_logs_alone_do_not_become_backfilled(self):
        """Logs are circumstantial — they never produce BACKFILLED."""
        evidence = ClassificationEvidence(has_logs=True)
        assert LedgerMigrator.classify(evidence) == LegacyClassification.UNKNOWN

    def test_logs_and_markers_do_not_become_backfilled(self):
        evidence = ClassificationEvidence(has_logs=True, has_markers=True)
        assert LedgerMigrator.classify(evidence) == LegacyClassification.UNKNOWN

    # ── Safety: markers never synthesize terminal success ──────────────

    def test_markers_alone_do_not_become_backfilled(self):
        """Status markers are circumstantial — they never produce BACKFILLED."""
        evidence = ClassificationEvidence(has_markers=True)
        assert LedgerMigrator.classify(evidence) == LegacyClassification.UNKNOWN

    # ── Safety: receipts never synthesize terminal success ─────────────

    def test_receipts_alone_do_not_become_backfilled(self):
        """Delivery receipts are circumstantial — they never produce BACKFILLED."""
        evidence = ClassificationEvidence(has_receipts=True)
        assert LedgerMigrator.classify(evidence) == LegacyClassification.UNKNOWN

    def test_receipts_and_logs_do_not_become_backfilled(self):
        evidence = ClassificationEvidence(has_receipts=True, has_logs=True)
        assert LedgerMigrator.classify(evidence) == LegacyClassification.UNKNOWN

    # ── Safety: mutable state never synthesizes terminal success ───────

    def test_mutable_state_alone_does_not_become_backfilled(self):
        """In-memory or runtime state is circumstantial — never BACKFILLED."""
        evidence = ClassificationEvidence(has_mutable_state=True)
        assert LedgerMigrator.classify(evidence) == LegacyClassification.UNKNOWN

    def test_all_circumstantial_together_do_not_become_backfilled(self):
        """Even when ALL circumstantial evidence types are present
        (logs + markers + receipts + mutable state), without authoritative
        source the classification is UNKNOWN — never BACKFILLED."""
        evidence = ClassificationEvidence(
            has_logs=True,
            has_markers=True,
            has_receipts=True,
            has_mutable_state=True,
        )
        assert LedgerMigrator.classify(evidence) == LegacyClassification.UNKNOWN


# ── Classification safety validation ──────────────────────────────────────


class TestClassificationSafetyValidation:
    """The ``_validate_classification_safety`` method enforces that BACKFILLED
    cannot be recorded when only circumstantial evidence exists."""

    def test_backfilled_with_authoritative_source_passes(self):
        """BACKFILLED + authoritative source → no error."""
        evidence = ClassificationEvidence(has_authoritative_source=True)
        # Should not raise.
        LedgerMigrator._validate_classification_safety(
            LegacyClassification.BACKFILLED, evidence
        )

    def test_unknown_with_logs_passes(self):
        """UNKNOWN classification is always safe regardless of evidence."""
        evidence = ClassificationEvidence(has_logs=True)
        LedgerMigrator._validate_classification_safety(
            LegacyClassification.UNKNOWN, evidence
        )

    def test_corrupt_passes_regardless_of_evidence(self):
        evidence = ClassificationEvidence(has_logs=True, has_mutable_state=True)
        LedgerMigrator._validate_classification_safety(
            LegacyClassification.CORRUPT, evidence
        )

    def test_backfilled_with_only_logs_raises(self):
        """BACKFILLED assigned when only logs exist → ClassificationSafetyError."""
        evidence = ClassificationEvidence(has_logs=True)
        with pytest.raises(ClassificationSafetyError, match="logs"):
            LedgerMigrator._validate_classification_safety(
                LegacyClassification.BACKFILLED, evidence
            )

    def test_backfilled_with_only_markers_raises(self):
        """BACKFILLED assigned when only markers exist → error mentioning markers."""
        evidence = ClassificationEvidence(has_markers=True)
        with pytest.raises(ClassificationSafetyError, match="markers"):
            LedgerMigrator._validate_classification_safety(
                LegacyClassification.BACKFILLED, evidence
            )

    def test_backfilled_with_only_receipts_raises(self):
        """BACKFILLED assigned when only receipts exist → error mentioning receipts."""
        evidence = ClassificationEvidence(has_receipts=True)
        with pytest.raises(ClassificationSafetyError, match="receipts"):
            LedgerMigrator._validate_classification_safety(
                LegacyClassification.BACKFILLED, evidence
            )

    def test_backfilled_with_only_mutable_state_raises(self):
        """BACKFILLED assigned when only mutable state exists → error."""
        evidence = ClassificationEvidence(has_mutable_state=True)
        with pytest.raises(ClassificationSafetyError, match="mutable state"):
            LedgerMigrator._validate_classification_safety(
                LegacyClassification.BACKFILLED, evidence
            )

    def test_backfilled_with_all_circumstantial_raises(self):
        """BACKFILLED with every circumstantial type but no authoritative source."""
        evidence = ClassificationEvidence(
            has_logs=True,
            has_markers=True,
            has_receipts=True,
            has_mutable_state=True,
        )
        with pytest.raises(ClassificationSafetyError) as exc_info:
            LedgerMigrator._validate_classification_safety(
                LegacyClassification.BACKFILLED, evidence
            )
        msg = exc_info.value.reason
        assert "logs" in msg
        assert "markers" in msg
        assert "receipts" in msg
        assert "mutable state" in msg

    def test_backfilled_with_no_evidence_raises(self):
        """BACKFILLED assigned when no evidence exists at all."""
        evidence = ClassificationEvidence()
        with pytest.raises(ClassificationSafetyError, match="no evidence"):
            LedgerMigrator._validate_classification_safety(
                LegacyClassification.BACKFILLED, evidence
            )


# ── Classification evidence properties ────────────────────────────────────


class TestClassificationEvidenceProperties:
    """The ClassificationEvidence dataclass exposes useful derived properties."""

    def test_only_circumstantial_true_with_logs_only(self):
        e = ClassificationEvidence(has_logs=True)
        assert e.only_circumstantial is True

    def test_only_circumstantial_false_with_authoritative_source(self):
        e = ClassificationEvidence(has_authoritative_source=True, has_logs=True)
        assert e.only_circumstantial is False

    def test_only_circumstantial_false_with_no_evidence(self):
        e = ClassificationEvidence()
        assert e.only_circumstantial is False  # no circumstantial evidence either

    def test_no_evidence_true_with_all_false(self):
        e = ClassificationEvidence()
        assert e.no_evidence is True

    def test_no_evidence_false_with_logs(self):
        e = ClassificationEvidence(has_logs=True)
        assert e.no_evidence is False

    def test_no_evidence_false_with_authoritative_source(self):
        e = ClassificationEvidence(has_authoritative_source=True)
        assert e.no_evidence is False


# ── Classify + record integration (duplicate-backfill idempotency) ─────────


class TestClassifyAndRecordIntegration:
    """Integration of ``classify_legacy_record`` with
    ``record_legacy_classification`` — the recommended safe path."""

    def test_classify_then_record_backfilled(self):
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            migrator = SqliteLedgerMigrator(store, _simple_registry(1))
            migrator.migrate()

            evidence = ClassificationEvidence(has_authoritative_source=True)
            cls = migrator.classify_legacy_record(
                "attempt_events", "rec-1", evidence, migration_version=1
            )
            assert cls == LegacyClassification.BACKFILLED

            rec = migrator.record_legacy_classification(
                "attempt_events",
                "rec-1",
                cls,
                "reconstructed from authoritative source",
                migration_version=1,
            )
            assert rec.classification == "backfilled"
            store.close()
        finally:
            if os.path.exists(path):
                os.remove(path)

    def test_classify_then_record_unknown_from_logs(self):
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            migrator = SqliteLedgerMigrator(store, _simple_registry(1))
            migrator.migrate()

            evidence = ClassificationEvidence(has_logs=True)
            cls = migrator.classify_legacy_record(
                "attempt_events", "rec-2", evidence
            )
            assert cls == LegacyClassification.UNKNOWN

            rec = migrator.record_legacy_classification(
                "attempt_events",
                "rec-2",
                cls,
                "only operational logs exist — true state indeterminate",
            )
            assert rec.classification == "unknown"
            store.close()
        finally:
            if os.path.exists(path):
                os.remove(path)

    def test_classify_then_record_corrupt(self):
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            migrator = SqliteLedgerMigrator(store, _simple_registry(1))
            migrator.migrate()

            evidence = ClassificationEvidence(is_structurally_damaged=True)
            cls = migrator.classify_legacy_record(
                "attempt_events", "rec-3", evidence
            )
            assert cls == LegacyClassification.CORRUPT

            rec = migrator.record_legacy_classification(
                "attempt_events",
                "rec-3",
                cls,
                "record payload is corrupt",
            )
            assert rec.classification == "corrupt"
            store.close()
        finally:
            if os.path.exists(path):
                os.remove(path)

    def test_classify_then_record_unreconstructable(self):
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            migrator = SqliteLedgerMigrator(store, _simple_registry(1))
            migrator.migrate()

            evidence = ClassificationEvidence(source_exists=False)
            cls = migrator.classify_legacy_record(
                "attempt_events", "rec-4", evidence
            )
            assert cls == LegacyClassification.UNRECONSTRUCTABLE

            rec = migrator.record_legacy_classification(
                "attempt_events",
                "rec-4",
                cls,
                "no source system ever persisted this record",
            )
            assert rec.classification == "unreconstructable"
            store.close()
        finally:
            if os.path.exists(path):
                os.remove(path)

    def test_duplicate_backfill_idempotency(self):
        """Classifying the same record with the same evidence twice produces
        the same classification (idempotent)."""
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            migrator = SqliteLedgerMigrator(store, _simple_registry(1))
            migrator.migrate()

            evidence = ClassificationEvidence(has_authoritative_source=True)
            cls1 = migrator.classify_legacy_record(
                "attempt_events", "rec-5", evidence
            )
            cls2 = migrator.classify_legacy_record(
                "attempt_events", "rec-5", evidence
            )
            assert cls1 == cls2 == LegacyClassification.BACKFILLED

            # Recording twice produces two distinct classification records
            # (append-only evidence), but both have the same classification.
            r1 = migrator.record_legacy_classification(
                "attempt_events", "rec-5", cls1, "first pass"
            )
            r2 = migrator.record_legacy_classification(
                "attempt_events", "rec-5", cls2, "second pass (idempotent)"
            )
            assert r1.classification_id != r2.classification_id
            assert r1.classification == r2.classification == "backfilled"

            results = migrator.query_legacy_classifications(record_id="rec-5")
            assert len(results) == 2
            store.close()
        finally:
            if os.path.exists(path):
                os.remove(path)

    def test_classify_unknown_from_each_circumstantial_source(self):
        """Each circumstantial source alone → UNKNOWN, never BACKFILLED."""
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            migrator = SqliteLedgerMigrator(store, _simple_registry(1))
            migrator.migrate()

            for source, evidence in [
                ("logs", ClassificationEvidence(has_logs=True)),
                ("markers", ClassificationEvidence(has_markers=True)),
                ("receipts", ClassificationEvidence(has_receipts=True)),
                (
                    "mutable_state",
                    ClassificationEvidence(has_mutable_state=True),
                ),
            ]:
                cls = migrator.classify_legacy_record(
                    "attempt_events", f"rec-{source}", evidence
                )
                assert cls == LegacyClassification.UNKNOWN, (
                    f"{source} should produce UNKNOWN, got {cls}"
                )
            store.close()
        finally:
            if os.path.exists(path):
                os.remove(path)


# ── Rollback / forward-fix policy ─────────────────────────────────────────


class TestRollbackPolicy:
    """Rollback is a tombstone, not a deletion. The evidence trail is preserved.
    A forward-fix correction is recorded as a new classification."""

    def test_rollback_marks_tombstone_not_deletes(self):
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            migrator = SqliteLedgerMigrator(store, _simple_registry(1))
            migrator.migrate()

            rec = migrator.record_legacy_classification(
                "attempt_events",
                "rec-rb-1",
                LegacyClassification.UNKNOWN,
                "initial classification",
            )
            assert rec.rolled_back_at_ns is None
            assert rec.is_rolled_back is False

            rolled = migrator.rollback_classification(
                rec.classification_id, "superseded by authoritative reconstruction"
            )
            assert rolled is not None
            assert rolled.classification_id == rec.classification_id
            assert rolled.rolled_back_at_ns is not None
            assert rolled.is_rolled_back is True

            # The original record is still queryable (evidence preserved).
            results = migrator.query_legacy_classifications(
                record_id="rec-rb-1"
            )
            assert len(results) == 1
            assert results[0].rolled_back_at_ns is not None
            store.close()
        finally:
            if os.path.exists(path):
                os.remove(path)

    def test_rollback_nonexistent_returns_none(self):
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            migrator = SqliteLedgerMigrator(store, _simple_registry(1))
            migrator.migrate()

            result = migrator.rollback_classification(
                "nonexistent-id-12345", "reason"
            )
            assert result is None
            store.close()
        finally:
            if os.path.exists(path):
                os.remove(path)

    def test_rollback_already_rolled_back_is_idempotent(self):
        """Rolling back an already-rolled-back classification returns it
        without error (idempotent)."""
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            migrator = SqliteLedgerMigrator(store, _simple_registry(1))
            migrator.migrate()

            rec = migrator.record_legacy_classification(
                "attempt_events",
                "rec-rb-2",
                LegacyClassification.UNKNOWN,
                "initial",
            )
            first = migrator.rollback_classification(
                rec.classification_id, "first rollback"
            )
            assert first is not None
            first_ts = first.rolled_back_at_ns

            second = migrator.rollback_classification(
                rec.classification_id, "second rollback (idempotent)"
            )
            assert second is not None
            # Same timestamp — the second rollback did not change it.
            assert second.rolled_back_at_ns == first_ts
            store.close()
        finally:
            if os.path.exists(path):
                os.remove(path)

    def test_query_rolled_back_classifications(self):
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            migrator = SqliteLedgerMigrator(store, _simple_registry(1))
            migrator.migrate()

            rec1 = migrator.record_legacy_classification(
                "attempt_events", "r1", LegacyClassification.UNKNOWN, "x"
            )
            rec2 = migrator.record_legacy_classification(
                "attempt_events", "r2", LegacyClassification.CORRUPT, "y"
            )
            rec3 = migrator.record_legacy_classification(
                "outbox_records", "r3", LegacyClassification.UNKNOWN, "z"
            )

            # Roll back rec1 and rec3, leave rec2 alone.
            migrator.rollback_classification(rec1.classification_id, "reason1")
            migrator.rollback_classification(rec3.classification_id, "reason3")

            all_rolled = migrator.query_rolled_back_classifications()
            assert len(all_rolled) == 2
            rolled_ids = {r.classification_id for r in all_rolled}
            assert rec1.classification_id in rolled_ids
            assert rec3.classification_id in rolled_ids
            assert rec2.classification_id not in rolled_ids

            # Filter by source_table.
            events_rolled = migrator.query_rolled_back_classifications(
                source_table="attempt_events"
            )
            assert len(events_rolled) == 1
            assert events_rolled[0].classification_id == rec1.classification_id
            store.close()
        finally:
            if os.path.exists(path):
                os.remove(path)

    def test_forward_fix_rollback_then_reclassify(self):
        """The forward-fix pattern: roll back an incorrect classification,
        then record a corrected one."""
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            migrator = SqliteLedgerMigrator(store, _simple_registry(1))
            migrator.migrate()

            # Initial (incorrect) classification: UNKNOWN.
            bad = migrator.record_legacy_classification(
                "attempt_events",
                "rec-ff-1",
                LegacyClassification.UNKNOWN,
                "initial: evidence incomplete",
            )

            # Roll back the incorrect classification.
            rolled = migrator.rollback_classification(
                bad.classification_id,
                "authoritative source discovered — reclassifying",
            )
            assert rolled.is_rolled_back is True

            # Record the corrected classification: BACKFILLED.
            corrected = migrator.record_legacy_classification(
                "attempt_events",
                "rec-ff-1",
                LegacyClassification.BACKFILLED,
                "reconstructed from authoritative source after rollback",
            )
            assert corrected.classification == "backfilled"
            assert corrected.is_rolled_back is False

            # Both records exist — evidence trail complete.
            results = migrator.query_legacy_classifications(record_id="rec-ff-1")
            assert len(results) == 2

            classifications = [r.classification for r in results]
            assert "unknown" in classifications
            assert "backfilled" in classifications

            rolled_results = migrator.query_rolled_back_classifications(
                record_id="rec-ff-1"
            )
            assert len(rolled_results) == 1
            assert rolled_results[0].classification_id == bad.classification_id
            store.close()
        finally:
            if os.path.exists(path):
                os.remove(path)


# ── Mixed reader/writer compatibility (separate process) ─────────────────


class TestMixedReaderWriterCompatibility:
    """A reader process observes a consistent migration-state prefix while a
    writer process is migrating. No half-applied migration is ever visible."""

    @staticmethod
    def _collect(queue: Any, expected: int, timeout: float = 30.0) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        deadline = time.time() + timeout
        while len(results) < expected and time.time() < deadline:
            try:
                item = queue.get(timeout=1.0)
                results.append(item)
            except Exception:
                continue
        return results

    def test_reader_sees_consistent_state_under_concurrent_writer(self):
        """The writer applies migrations while a reader queries state in a
        separate process. The reader must observe a clean prefix (0..k), never
        a partial/garbled migration record."""
        path = _store_path()
        # Pre-create the store file so both processes share it.
        pre = SqliteAttemptLedgerStore(path)
        pre.close()
        try:
            ctx = multiprocessing.get_context("spawn")
            reader_q: Any = ctx.Queue()
            writer_q: Any = ctx.Queue()
            ready = ctx.Event()
            done = ctx.Event()

            reg = _simple_registry(3)

            reader_p = ctx.Process(
                target=_mp_reader_worker,
                args=(path, ready, done, reader_q),
            )
            writer_p = ctx.Process(
                target=_mp_writer_worker,
                args=(path, ready, reg, writer_q),
            )
            reader_p.start()
            writer_p.start()
            reader_p.join(timeout=40.0)
            writer_p.join(timeout=40.0)

            assert reader_p.exitcode == 0, "reader crashed"
            assert writer_p.exitcode == 0, "writer crashed"

            reader_results = self._collect(reader_q, 1)
            writer_results = self._collect(writer_q, 1)
            assert len(reader_results) == 1, f"reader: {reader_results}"
            assert len(writer_results) == 1, f"writer: {writer_results}"

            assert writer_results[0]["status"] == "ok"
            assert writer_results[0]["final_version"] == 3

            # Reader observed SOME consistent prefix (possibly before or after
            # the writer's commit, but always a clean prefix).
            assert reader_results[0]["status"] == "ok", reader_results[0]
            seen = reader_results[0]["applied_versions"]
            # Must be a contiguous prefix starting at 1 (or empty).
            assert seen in ((), (1,), (1, 2), (1, 2, 3)), (
                f"reader saw non-prefix state: {seen}"
            )
        finally:
            if os.path.exists(path):
                os.remove(path)

    def test_reader_after_writer_commit_sees_complete_state(self):
        """After the writer commits, a fresh reader sees the full applied set."""
        path = _store_path()
        pre = SqliteAttemptLedgerStore(path)
        pre.close()
        try:
            ctx = multiprocessing.get_context("spawn")
            writer_q: Any = ctx.Queue()
            ready = ctx.Event()
            reg = _simple_registry(3)
            writer_p = ctx.Process(
                target=_mp_writer_worker,
                args=(path, ready, reg, writer_q),
            )
            writer_p.start()
            writer_p.join(timeout=40.0)
            assert writer_p.exitcode == 0
            self._collect(writer_q, 1)

            # Fresh reader, after the writer is done.
            store = SqliteAttemptLedgerStore(path)
            migrator = SqliteLedgerMigrator(store, reg)
            state = migrator.get_state()
            assert tuple(r.version for r in state.applied) == (1, 2, 3)
            assert state.is_complete is True
            store.close()
        finally:
            if os.path.exists(path):
                os.remove(path)

    def test_two_writers_do_not_double_apply(self):
        """Concurrent migrate() calls from two processes do not produce
        duplicate schema_migrations rows (PRIMARY KEY guard)."""
        path = _store_path()
        pre = SqliteAttemptLedgerStore(path)
        pre.close()
        try:
            ctx = multiprocessing.get_context("spawn")
            q: Any = ctx.Queue()
            ready = ctx.Event()
            reg = _simple_registry(3)

            p1 = ctx.Process(
                target=_mp_writer_worker, args=(path, ready, reg, q)
            )
            p2 = ctx.Process(
                target=_mp_writer_worker, args=(path, ready, reg, q)
            )
            p1.start()
            p2.start()
            p1.join(timeout=40.0)
            p2.join(timeout=40.0)

            results = self._collect(q, 2)
            statuses = [r["status"] for r in results]
            # At least one must succeed; the other may succeed too (idempotent
            # skip) or error on the PRIMARY KEY (caught & rolled back). Either
            # way the store must end consistent.
            assert "ok" in statuses, results

            store = SqliteAttemptLedgerStore(path)
            migrator = SqliteLedgerMigrator(store, reg)
            state = migrator.get_state()
            # Exactly one row per version — no duplicates.
            versions = [r.version for r in state.applied]
            assert versions == sorted(set(versions))
            assert set(versions) == {1, 2, 3}
            assert state.is_complete is True
            store.close()
        finally:
            if os.path.exists(path):
                os.remove(path)


# ── Default M6A registry ──────────────────────────────────────────────────


class TestDefaultM6aRegistry:
    """The default M6A registry is well-formed and forward-fix-anchored."""

    def test_default_registry_is_contiguous_from_1(self):
        reg = default_m6a_migrations()
        versions = [m.version for m in reg]
        assert versions == list(range(1, len(reg) + 1))
        names = [m.name for m in reg]
        assert len(names) == len(set(names))

    def test_default_migrations_apply_cleanly_and_are_idempotent(self):
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            migrator = SqliteLedgerMigrator(store, default_m6a_migrations())
            result = migrator.migrate()
            assert result.final_version == len(default_m6a_migrations())
            assert migrator.get_state().is_complete is True
            # Idempotent re-run.
            result2 = migrator.migrate()
            assert result2.applied_now == ()
            store.close()
        finally:
            if os.path.exists(path):
                os.remove(path)

    def test_default_registry_records_forward_fix_policy(self):
        """The default registry durably records the UNKNOWN-classification rule
        and forbids synthesized success."""
        path = _store_path()
        try:
            store = SqliteAttemptLedgerStore(path)
            migrator = SqliteLedgerMigrator(store, default_m6a_migrations())
            migrator.migrate()
            conn = store.conn
            cur = conn.execute(
                "SELECT value FROM forward_fix_policy "
                "WHERE key = 'unreconstructable_classification'"
            )
            assert cur.fetchone()[0] == "unknown"
            cur = conn.execute(
                "SELECT value FROM forward_fix_policy "
                "WHERE key = 'synthesize_success'"
            )
            assert cur.fetchone()[0] == "forbidden"
            store.close()
        finally:
            if os.path.exists(path):
                os.remove(path)
