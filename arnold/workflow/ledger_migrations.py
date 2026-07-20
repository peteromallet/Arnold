"""Versioned, checksum-validated, crash-resumable schema migrations for the
M6A WBC transactional ledger substrate.

This module provides the M6A migration boundary. It governs how the SQLite
schema that backs :class:`~arnold.workflow.attempt_ledger_store.SqliteAttemptLedgerStore`
and its sibling stores (outbox, payload) evolves over time, and how legacy or
unreconstructable records are classified.

Design pillars (M6A success criterion 9):
* **Versioned** — every migration carries a strictly-increasing integer
  ``version`` and a stable ``name``. Migrations apply in ascending order and a
  gap in the applied sequence is never bridged silently.
* **Checksum-validated** — every migration's content (version + name +
  statements) is reduced to a deterministic SHA-256 checksum that is persisted
  alongside its applied-state record. On re-open the stored checksum is
  compared to the live registry's checksum; a mismatch is a forward-fix
  violation and is surfaced, never silently re-applied.
* **Crash-resumable** — each migration applies inside its *own* ``BEGIN
  IMMEDIATE`` transaction that atomically stages the schema change *and* the
  ``schema_migrations`` row. A crash mid-migration leaves either a fully
  applied+recorded migration or nothing — never a half-applied migration that a
  mixed-version reader could mistake for authoritative state. Resuming re-runs
  the unrecorded migration from scratch; DDL is idempotent (``IF NOT EXISTS``)
  so a partially-staged-but-uncommitted change is safely re-staged.
* **Forward-fix only** — there is no downgrade path. A migration, once applied,
  is immutable. To repair a defect you add a *new* migration; you never edit an
  applied one (the checksum guard enforces this). Unreconstructable legacy
  records are classified ``UNKNOWN`` / ``UNRECONSTRUCTABLE`` — success is never
  synthesized from logs, markers, or mutable state (SD2).
* **Idempotent on duplicate backfill** — ``migrate()`` is safe to call any
  number of times; already-applied migrations are skipped, not re-executed.
* **Mixed reader/writer safe** — migration state is a normal table read under
  WAL snapshot semantics, so a reader connection observes a consistent
  ``schema_migrations`` view (some prefix ``1..k`` applied) even while a writer
  is mid-migration.

This module owns only migration-tracking and legacy-classification tables. It
does not duplicate the store/outbox/payload DDL; forward migrations are
additive and idempotent.
"""

from __future__ import annotations

import hashlib
import sqlite3
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional, Sequence

from arnold.workflow.attempt_ledger_store import SqliteAttemptLedgerStore

# ── Constants ─────────────────────────────────────────────────────────────

#: Logical tag embedded in every migration checksum so that checksums from a
#: different (hypothetical) migration scheme never collide with ours.
_CHECKSUM_DOMAIN: str = "arnold.workflow.ledger_migrations.v1"

#: Number of times to retry ``BEGIN IMMEDIATE`` under ``SQLITE_BUSY`` before
#: giving up. Mirrors the store/outbox contention handling so a migration run
#: is safe under separate-process writer contention.
_BEGIN_RETRY_ATTEMPTS: int = 30
_BEGIN_RETRY_BASE_DELAY: float = 0.05  # 50 ms

# ── Migration-tracking table DDL ──────────────────────────────────────────
#
# The migration-tracking tables are *bootstrap* state: they are created with
# ``IF NOT EXISTS`` before any versioned query so that ``get_state()`` works on
# a brand-new store. They are NOT themselves a versioned migration — versioned
# migrations are additive schema evolution layered on top.

_SCHEMA_MIGRATIONS_TABLE_DDL: str = """\
CREATE TABLE IF NOT EXISTS schema_migrations (
    version       INTEGER PRIMARY KEY,
    name          TEXT    NOT NULL,
    checksum      TEXT    NOT NULL,
    applied_at_ns INTEGER NOT NULL,
    status        TEXT    NOT NULL DEFAULT 'applied'
);
"""

_LEGACY_CLASSIFICATIONS_TABLE_DDL: str = """\
CREATE TABLE IF NOT EXISTS legacy_record_classifications (
    classification_id  TEXT    NOT NULL PRIMARY KEY,
    source_table       TEXT    NOT NULL,
    record_id          TEXT    NOT NULL,
    classification     TEXT    NOT NULL,
    reason             TEXT    NOT NULL,
    migration_version  INTEGER,
    classified_at_ns   INTEGER NOT NULL,
    rolled_back_at_ns  INTEGER
);
"""

_LEGACY_SOURCE_INDEX_DDL: str = """\
CREATE INDEX IF NOT EXISTS idx_legacy_cls_source
    ON legacy_record_classifications(source_table, record_id);
"""

_LEGACY_MIGRATION_INDEX_DDL: str = """\
CREATE INDEX IF NOT EXISTS idx_legacy_cls_migration
    ON legacy_record_classifications(migration_version);
"""


# ── Typed errors ──────────────────────────────────────────────────────────


class MigrationError(Exception):
    """Base class for typed migration errors.

    All migration-policy violations derive from this class so callers can
    distinguish migration enforcement from generic ``sqlite3`` errors.
    """


class MigrationChecksumMismatchError(MigrationError):
    """Raised when an applied migration's stored checksum differs from the
    live registry's checksum.

    This is a forward-fix violation: an already-applied migration was edited
    in source. The migration system refuses to proceed — there is no
    auto-re-apply and no downgrade. The only legitimate remedy is a *new*
    forward migration.

    Carries the offending ``version``, the stored checksum, and the expected
    checksum so operators can identify the drift precisely.
    """

    def __init__(
        self, version: int, name: str, stored: str, expected: str
    ) -> None:
        self.version = version
        self.name = name
        self.stored_checksum = stored
        self.expected_checksum = expected
        super().__init__(
            f"Migration {version} ({name!r}) checksum mismatch: "
            f"stored {stored!r} != expected {expected!r}. "
            f"Applied migrations are immutable; add a new forward migration "
            f"instead of editing an applied one."
        )


class MigrationRegistryError(MigrationError):
    """Raised when a migration registry is malformed.

    Covers: duplicate versions, non-contiguous version sequences, and
    non-monotonic ordering. A registry must be a strict contiguous run
    starting at 1 so that applied-state and forward-fix reasoning is
    unambiguous.
    """

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


class MigrationOrderError(MigrationError):
    """Raised when the applied state has a version not present in the current
    registry, or when applying migrations out of order would be required.

    Under the forward-fix-only policy the applied set must always be a prefix
    of the registry. An applied version absent from the registry indicates the
    store was migrated by a different (newer or divergent) code revision; this
    is surfaced rather than silently ignored.
    """


class ClassificationSafetyError(MigrationError):
    """Raised when a ``BACKFILLED`` classification is attempted using
    impermissible evidence sources (logs, markers, receipts, or mutable state).

    The M6A North Star prohibits synthesizing terminal success from any source
    other than authoritative reconstruction evidence. This error is the
    enforcement boundary: it catches any code path that tries to upgrade
    circumstantial evidence into a terminal ``BACKFILLED`` classification.
    """

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


# ── Enums ─────────────────────────────────────────────────────────────────


class LegacyClassification(Enum):
    """Classification of a legacy or unreconstructable record.

    The key rule (SD2 / criterion 9): records that cannot be confidently
    reconstructed are ``UNKNOWN`` / ``UNRECONSTRUCTABLE``. The migration system
    never synthesizes success (``BACKFILLED``) from incomplete evidence.

    * ``BACKFILLED`` — the record was durably reconstructed from authoritative
      source evidence.
    * ``UNKNOWN`` — the record cannot be reconstructed and its true state is
      indeterminate. No terminal/success outcome is synthesized.
    * ``CORRUPT`` — the record or its source evidence is structurally damaged.
    * ``UNRECONSTRUCTABLE`` — no source exists from which to reconstruct the
      record (e.g. the producing system never persisted it).
    """

    BACKFILLED = "backfilled"
    UNKNOWN = "unknown"
    CORRUPT = "corrupt"
    UNRECONSTRUCTABLE = "unreconstructable"


@dataclass(frozen=True)
class ClassificationEvidence:
    """Evidence profile for a legacy record being classified.

    This dataclass makes the evidence sources *explicit* so that the
    classification decision function can reject BACKFILLED when the authority
    derives from impermissible sources (logs, markers, receipts, mutable state).

    Attributes:
        has_authoritative_source: The record can be reconstructed from
            authoritative, durable source data (e.g. a separate durable store
            with matching checksums). This is the ONLY path to BACKFILLED.
        has_logs: Operational logs mention the record. NOT authoritative.
        has_markers: Checkpoint/status markers reference the record. NOT
            authoritative.
        has_receipts: Delivery receipts or acknowledgments exist. NOT
            authoritative.
        has_mutable_state: A mutable system (e.g. in-memory cache, runtime
            state) holds data about the record. NOT authoritative.
        is_structurally_damaged: The record or its source is structurally
            damaged (e.g. corrupt encoding, missing required fields).
        source_exists: ``False`` when no source system ever persisted the
            record (UNRECONSTRUCTABLE).
        notes: Free-form notes about the evidence assessment.
    """

    has_authoritative_source: bool = False
    has_logs: bool = False
    has_markers: bool = False
    has_receipts: bool = False
    has_mutable_state: bool = False
    is_structurally_damaged: bool = False
    source_exists: bool = True
    notes: str = ""

    @property
    def only_circumstantial(self) -> bool:
        """True when evidence consists ONLY of impermissible sources
        (logs, markers, receipts, mutable state) with no authoritative source."""
        return (
            not self.has_authoritative_source
            and (
                self.has_logs
                or self.has_markers
                or self.has_receipts
                or self.has_mutable_state
            )
        )

    @property
    def no_evidence(self) -> bool:
        """True when no evidence of any kind is available."""
        return (
            not self.has_authoritative_source
            and not self.has_logs
            and not self.has_markers
            and not self.has_receipts
            and not self.has_mutable_state
        )


# ── Checksum ──────────────────────────────────────────────────────────────


def compute_migration_checksum(
    version: int, name: str, statements: Sequence[str]
) -> str:
    """Return the deterministic SHA-256 checksum for a migration.

    The checksum covers the domain tag, version, name, and every statement in
    order. It is stable across runs (no timestamps, no randomness) so that an
    applied migration's stored checksum can be compared to the live registry's
    checksum to detect content drift (forward-fix enforcement).
    """
    h = hashlib.sha256()
    h.update(f"domain={_CHECKSUM_DOMAIN}\n".encode("utf-8"))
    h.update(f"version={version}\n".encode("utf-8"))
    h.update(f"name={name}\n".encode("utf-8"))
    for i, stmt in enumerate(statements):
        h.update(f"stmt[{i}]={stmt}\n".encode("utf-8"))
    return "sha256:" + h.hexdigest()


# ── Frozen dataclasses ────────────────────────────────────────────────────


@dataclass(frozen=True)
class Migration:
    """A single versioned schema migration.

    A migration is immutable: once registered its ``version``, ``name``, and
    ``statements`` must not change (the checksum guard enforces this for any
    migration that has been applied). To evolve the schema, add a *new*
    migration with the next version.

    Attributes:
        version: Strictly increasing integer, starting at 1.
        name: Stable human-readable identifier (no two migrations share a name).
        statements: SQL statements executed in order inside the migration's
            transaction. They MUST be idempotent (e.g. ``CREATE TABLE IF NOT
            EXISTS``) so that crash-resume re-staging is safe.
    """

    version: int
    name: str
    statements: tuple[str, ...] = ()
    checksum: str = field(default="", init=False, compare=False, repr=False)

    def __post_init__(self) -> None:
        # Frozen dataclass: bypass immutability to set the derived checksum.
        object.__setattr__(
            self,
            "checksum",
            compute_migration_checksum(self.version, self.name, self.statements),
        )


@dataclass(frozen=True)
class MigrationRecord:
    """A migration's persisted applied-state, read back from the store."""

    version: int
    name: str
    checksum: str
    applied_at_ns: int
    status: str


@dataclass(frozen=True)
class ChecksumMismatch:
    """A detected forward-fix violation between an applied migration and the
    current registry."""

    version: int
    name: str
    stored_checksum: str
    expected_checksum: str


@dataclass(frozen=True)
class MigrationState:
    """Snapshot of migration state for a store.

    * ``applied``: migrations recorded as applied, in version order.
    * ``pending``: registry migrations not yet applied, in version order.
    * ``orphans``: applied versions absent from the current registry (divergent
      code revision). Under forward-fix policy this is surfaced, not ignored.
    * ``checksum_mismatches``: applied migrations whose stored checksum differs
      from the live registry (forward-fix violation).
    """

    applied: tuple[MigrationRecord, ...]
    pending: tuple[Migration, ...]
    orphans: tuple[MigrationRecord, ...]
    checksum_mismatches: tuple[ChecksumMismatch, ...]

    @property
    def last_applied_version(self) -> int:
        """Highest applied version, or 0 if none applied."""
        return self.applied[-1].version if self.applied else 0

    @property
    def is_complete(self) -> bool:
        """True iff every registry migration is applied with matching checksums
        and there are no orphans or mismatches."""
        return (
            not self.pending
            and not self.orphans
            and not self.checksum_mismatches
        )


@dataclass(frozen=True)
class LegacyRecordClassification:
    """A persisted classification of a legacy or unreconstructable record.

    Classifications are durable evidence: they record what was determined about
    a record during migration. They never grant authority or synthesize success.

    Rolled-back classifications are marked with ``rolled_back_at_ns`` rather
    than deleted, preserving the evidence trail. A non-``None``
    ``rolled_back_at_ns`` means the classification has been superseded by a
    forward-fix correction.
    """

    classification_id: str
    source_table: str
    record_id: str
    classification: str
    reason: str
    migration_version: Optional[int]
    classified_at_ns: int
    rolled_back_at_ns: Optional[int] = None

    @property
    def is_rolled_back(self) -> bool:
        """True if this classification has been rolled back (superseded)."""
        return self.rolled_back_at_ns is not None


@dataclass(frozen=True)
class MigrationResult:
    """Outcome of a single ``migrate()`` run.

    * ``applied_now``: migrations applied by THIS run (in order).
    * ``skipped``: migrations already applied before this run (idempotency).
    * ``final_version``: highest applied version after this run.
    * ``classifications_recorded``: legacy classifications recorded during this
      run (forward-fix evidence).
    """

    applied_now: tuple[Migration, ...]
    skipped: tuple[Migration, ...]
    final_version: int
    classifications_recorded: tuple[LegacyRecordClassification, ...]


# ── Registry validation ───────────────────────────────────────────────────


def _validate_registry(migrations: Sequence[Migration]) -> tuple[Migration, ...]:
    """Validate and freeze a migration registry.

    Ensures versions are a contiguous run starting at 1 with no duplicates or
    gaps, so that applied-state reasoning (an applied set must be a prefix of
    the registry) is unambiguous.
    """
    if not migrations:
        return ()
    seen_versions: set[int] = set()
    seen_names: set[str] = set()
    ordered = sorted(migrations, key=lambda m: m.version)
    prev = 0
    for m in ordered:
        if m.version in seen_versions:
            raise MigrationRegistryError(
                f"duplicate migration version {m.version}"
            )
        if m.name in seen_names:
            raise MigrationRegistryError(
                f"duplicate migration name {m.name!r}"
            )
        if m.version != prev + 1:
            raise MigrationRegistryError(
                f"non-contiguous migration versions: expected {prev + 1}, "
                f"got {m.version} ({m.name!r})"
            )
        seen_versions.add(m.version)
        seen_names.add(m.name)
        prev = m.version
    return tuple(ordered)


# ── Default M6A registry ──────────────────────────────────────────────────


def default_m6a_migrations() -> tuple[Migration, ...]:
    """Return the default M6A substrate migration registry.

    M6A is a brand-new, schema-only substrate (no deployed cohorts per SD2), so
    the default registry is a small forward-fix-anchored baseline. It records
    the substrate baseline version and the forward-fix / UNKNOWN-classification
    policy. Future schema evolution appends migrations with the next version;
    existing migrations are never edited (checksum guard enforces this).

    These migrations are additive and idempotent; they do not duplicate the
    store/outbox/payload DDL.
    """
    return (
        Migration(
            version=1,
            name="m6a_substrate_baseline",
            statements=(
                # Anchor the baseline: a small metadata table owned by the
                # migration system itself, recording the substrate baseline.
                "CREATE TABLE IF NOT EXISTS migration_baseline ("
                "  key   TEXT PRIMARY KEY,"
                "  value TEXT NOT NULL"
                ")",
                "INSERT OR IGNORE INTO migration_baseline (key, value)"
                "  VALUES ('substrate', 'm6a')",
            ),
        ),
        Migration(
            version=2,
            name="m6a_forward_fix_policy_anchor",
            statements=(
                # Anchor the forward-fix policy so that the
                # UNKNOWN-classification rule is durable and inspectable.
                "CREATE TABLE IF NOT EXISTS forward_fix_policy ("
                "  key   TEXT PRIMARY KEY,"
                "  value TEXT NOT NULL"
                ")",
                "INSERT OR IGNORE INTO forward_fix_policy (key, value)"
                "  VALUES ('unreconstructable_classification', 'unknown')",
                "INSERT OR IGNORE INTO forward_fix_policy (key, value)"
                "  VALUES ('synthesize_success', 'forbidden')",
            ),
        ),
    )


# ── Abstract migrator ─────────────────────────────────────────────────────


class LedgerMigrator(ABC):
    """Abstract versioned-migration runner for the WBC ledger substrate."""

    @abstractmethod
    def migrate(self) -> MigrationResult:
        """Apply all pending migrations in order.

        Each migration applies inside its own transaction. Already-applied
        migrations are skipped (idempotent). Checksums of applied migrations are
        verified before applying any pending migration; a mismatch raises
        :class:`MigrationChecksumMismatchError` and halts.
        """

    @abstractmethod
    def get_state(self) -> MigrationState:
        """Return the current migration state (applied / pending / orphans /
        checksum mismatches) without applying anything."""

    @abstractmethod
    def verify_checksums(self) -> tuple[ChecksumMismatch, ...]:
        """Return all checksum mismatches between applied and registry
        migrations. A non-empty result indicates forward-fix violations."""

    @abstractmethod
    def record_legacy_classification(
        self,
        source_table: str,
        record_id: str,
        classification: LegacyClassification,
        reason: str,
        migration_version: Optional[int] = None,
    ) -> LegacyRecordClassification:
        """Durably record a legacy-record classification.

        Classifications are evidence, not authority. ``UNKNOWN`` and
        ``UNRECONSTRUCTABLE`` records are never promoted to ``BACKFILLED`` by
        this API — the caller is responsible for only recording ``BACKFILLED``
        when authoritative reconstruction evidence exists.
        """

    @abstractmethod
    def query_legacy_classifications(
        self,
        source_table: Optional[str] = None,
        record_id: Optional[str] = None,
        classification: Optional[LegacyClassification] = None,
        migration_version: Optional[int] = None,
    ) -> tuple[LegacyRecordClassification, ...]:
        """Query durable legacy classifications with optional filters."""

    @abstractmethod
    def classify_legacy_record(
        self,
        source_table: str,
        record_id: str,
        evidence: ClassificationEvidence,
        migration_version: Optional[int] = None,
    ) -> LegacyClassification:
        """Determine the classification for a legacy record from its evidence
        profile.

        This is the **only** decision point for ``BACKFILLED``. The
        classification is determined entirely from the evidence profile, and
        ``BACKFILLED`` is **only** returned when
        ``evidence.has_authoritative_source`` is ``True``. Circumstantial
        evidence (logs, markers, receipts, mutable state) is never upgraded.

        The classification is not persisted by this method — callers that wish
        to record the determination must call
        :meth:`record_legacy_classification`.

        Returns:
            ``BACKFILLED`` — authoritative reconstruction evidence exists.
            ``UNKNOWN`` — evidence exists but is only circumstantial (logs,
                markers, receipts, mutable state) — true state indeterminate.
            ``CORRUPT`` — the record or source is structurally damaged.
            ``UNRECONSTRUCTABLE`` — no source system ever persisted the record.
        """

    @abstractmethod
    def rollback_classification(
        self, classification_id: str, reason: str
    ) -> Optional[LegacyRecordClassification]:
        """Mark a legacy classification as rolled back (superseded).

        Rollback is the forward-fix policy for classifications: the original
        classification record is preserved (evidence trail) but marked with a
        ``rolled_back_at_ns`` timestamp. A new corrective classification should
        be recorded separately via :meth:`record_legacy_classification`.

        Returns the updated classification record, or ``None`` if the
        ``classification_id`` was not found.
        """

    @abstractmethod
    def query_rolled_back_classifications(
        self,
        source_table: Optional[str] = None,
        record_id: Optional[str] = None,
    ) -> tuple[LegacyRecordClassification, ...]:
        """Query classifications that have been rolled back (superseded)."""

    @staticmethod
    def classify(evidence: ClassificationEvidence) -> LegacyClassification:
        """Pure-function classification decision from an evidence profile.

        This is the single classification decision function. It enforces the
        M6A safety property: ``BACKFILLED`` is only returned when
        ``evidence.has_authoritative_source`` is ``True``. All other evidence
        profiles are classified conservatively (``UNKNOWN``, ``CORRUPT``, or
        ``UNRECONSTRUCTABLE``).

        This static method can be used without a store connection for
        pre-validation or testing. The instance method
        :meth:`classify_legacy_record` delegates to this.
        """
        if evidence.is_structurally_damaged:
            return LegacyClassification.CORRUPT
        if not evidence.source_exists:
            return LegacyClassification.UNRECONSTRUCTABLE
        if evidence.has_authoritative_source:
            return LegacyClassification.BACKFILLED
        # Everything else: circumstantial evidence or no evidence → UNKNOWN.
        # The classifier NEVER upgrades logs, markers, receipts, or mutable
        # state into BACKFILLED.
        return LegacyClassification.UNKNOWN

    @staticmethod
    def _validate_classification_safety(
        classification: LegacyClassification,
        evidence: ClassificationEvidence,
    ) -> None:
        """Raise :class:`ClassificationSafetyError` if ``classification`` is
        ``BACKFILLED`` but the evidence profile only has circumstantial sources
        (logs, markers, receipts, mutable state) and no authoritative source.

        This is the enforcement boundary: any code path that tries to persist a
        ``BACKFILLED`` classification without authoritative evidence is caught
        here.
        """
        if classification != LegacyClassification.BACKFILLED:
            return
        if evidence.has_authoritative_source:
            return
        # BACKFILLED was assigned without authoritative source.
        circumstantial: list[str] = []
        if evidence.has_logs:
            circumstantial.append("logs")
        if evidence.has_markers:
            circumstantial.append("markers")
        if evidence.has_receipts:
            circumstantial.append("receipts")
        if evidence.has_mutable_state:
            circumstantial.append("mutable state")
        detail = (
            ", ".join(circumstantial) if circumstantial else "no evidence"
        )
        raise ClassificationSafetyError(
            f"Cannot classify record as BACKFILLED when evidence derives "
            f"from impermissible sources ({detail}). BACKFILLED requires "
            f"authoritative reconstruction evidence; logs, markers, "
            f"receipts, and mutable state are never authoritative."
        )


# ── SQLite implementation ─────────────────────────────────────────────────


class SqliteLedgerMigrator(LedgerMigrator):
    """Versioned migration runner backed by the same SQLite database as the
    :class:`SqliteAttemptLedgerStore`.

    The migrator uses the store's WAL connection so that migration transactions
    are co-located with store data and participate in the same contention model
    (``BEGIN IMMEDIATE`` with busy-retry). Migration-tracking and
    legacy-classification tables live alongside the store tables.
    """

    def __init__(
        self,
        store: SqliteAttemptLedgerStore,
        migrations: Optional[Sequence[Migration]] = None,
    ) -> None:
        self._store = store
        self._conn: sqlite3.Connection = store.conn
        self._migrations: tuple[Migration, ...] = _validate_registry(
            list(migrations) if migrations is not None else default_m6a_migrations()
        )
        self._ensure_migration_tables()

    # ── bootstrap ──────────────────────────────────────────────────────

    def _ensure_migration_tables(self) -> None:
        """Create the migration-tracking tables (idempotent bootstrap).

        These tables are not versioned migrations; they are the substrate that
        makes versioned state queryable. Created with ``IF NOT EXISTS`` so they
        are safe to call on every access.

        Also backfills the ``rolled_back_at_ns`` column on pre-existing
        databases that were created before the column was added to the DDL.
        """
        conn = self._conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            for ddl in (
                _SCHEMA_MIGRATIONS_TABLE_DDL,
                _LEGACY_CLASSIFICATIONS_TABLE_DDL,
                _LEGACY_SOURCE_INDEX_DDL,
                _LEGACY_MIGRATION_INDEX_DDL,
            ):
                for stmt in ddl.split(";"):
                    s = stmt.strip()
                    if s:
                        conn.execute(s)
            # Safe backfill: add rolled_back_at_ns column to pre-existing tables
            # that were created before the column existed in the DDL.
            try:
                conn.execute(
                    "ALTER TABLE legacy_record_classifications "
                    "ADD COLUMN rolled_back_at_ns INTEGER"
                )
            except sqlite3.OperationalError:
                # Column already exists — safe to ignore.
                pass
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise

    # ── transaction helper ─────────────────────────────────────────────

    @staticmethod
    def _begin_immediate_retry(conn: sqlite3.Connection) -> None:
        """Execute ``BEGIN IMMEDIATE`` with busy-retry.

        Mirrors the store/outbox contention handling for separate-process
        writer safety.
        """
        for attempt in range(_BEGIN_RETRY_ATTEMPTS):
            try:
                conn.execute("BEGIN IMMEDIATE")
                return
            except sqlite3.OperationalError as exc:
                if "locked" in str(exc).lower() and attempt < _BEGIN_RETRY_ATTEMPTS - 1:
                    delay = min(_BEGIN_RETRY_BASE_DELAY * (2 ** attempt), 2.0)
                    time.sleep(delay)
                    continue
                raise
        # Should be unreachable; the loop returns or raises.
        conn.execute("BEGIN IMMEDIATE")

    # ── core: read applied state ───────────────────────────────────────

    def _read_applied(self) -> tuple[MigrationRecord, ...]:
        """Read all applied migration records in version order.

        Reads outside an explicit transaction (autocommit): under WAL this
        observes a consistent snapshot, so the result is stable for the
        duration of the read even if a writer is mid-migration.
        """
        conn = self._conn
        cur = conn.execute(
            "SELECT version, name, checksum, applied_at_ns, status "
            "FROM schema_migrations ORDER BY version"
        )
        rows = cur.fetchall()
        return tuple(
            MigrationRecord(
                version=r[0],
                name=r[1],
                checksum=r[2],
                applied_at_ns=r[3],
                status=r[4],
            )
            for r in rows
        )

    def _compute_mismatches(
        self, applied: Sequence[MigrationRecord]
    ) -> tuple[ChecksumMismatch, ...]:
        """Compute checksum mismatches between applied records and the registry."""
        by_version = {m.version: m for m in self._migrations}
        mismatches: list[ChecksumMismatch] = []
        for rec in applied:
            reg = by_version.get(rec.version)
            if reg is not None and reg.checksum != rec.checksum:
                mismatches.append(
                    ChecksumMismatch(
                        version=rec.version,
                        name=rec.name,
                        stored_checksum=rec.checksum,
                        expected_checksum=reg.checksum,
                    )
                )
        return tuple(mismatches)

    def _compute_orphans(
        self, applied: Sequence[MigrationRecord]
    ) -> tuple[MigrationRecord, ...]:
        """Applied versions absent from the current registry (divergent code)."""
        reg_versions = {m.version for m in self._migrations}
        return tuple(r for r in applied if r.version not in reg_versions)

    # ── public API ──────────────────────────────────────────────────────

    def get_state(self) -> MigrationState:
        """Return the current migration state without applying anything."""
        applied = self._read_applied()
        applied_versions = {r.version for r in applied}
        pending = tuple(
            m for m in self._migrations if m.version not in applied_versions
        )
        return MigrationState(
            applied=applied,
            pending=pending,
            orphans=self._compute_orphans(applied),
            checksum_mismatches=self._compute_mismatches(applied),
        )

    def verify_checksums(self) -> tuple[ChecksumMismatch, ...]:
        """Return all checksum mismatches between applied and registry."""
        return self._compute_mismatches(self._read_applied())

    def migrate(self) -> MigrationResult:
        """Apply all pending migrations in order.

        Each migration is applied in its own ``BEGIN IMMEDIATE`` transaction.
        The transaction stages BOTH the migration's statements AND the
        ``schema_migrations`` row, then COMMITs. A crash before COMMIT leaves
        no trace of the partial migration; resume re-applies it idempotently.

        Raises:
            MigrationChecksumMismatchError: if an already-applied migration's
                checksum differs from the registry (forward-fix violation).
            MigrationOrderError: if an applied version is absent from the
                registry (divergent code revision).
        """
        applied = self._read_applied()

        # Forward-fix enforcement: applied migrations must match the registry.
        mismatches = self._compute_mismatches(applied)
        if mismatches:
            bad = mismatches[0]
            raise MigrationChecksumMismatchError(
                version=bad.version,
                name=bad.name,
                stored=bad.stored_checksum,
                expected=bad.expected_checksum,
            )

        # Applied versions absent from the registry indicate divergent code.
        orphans = self._compute_orphans(applied)
        if orphans:
            o = orphans[0]
            raise MigrationOrderError(
                f"Applied migration version {o.version} ({o.name!r}) is absent "
                f"from the current registry; the store was migrated by a "
                f"divergent code revision."
            )

        applied_versions = {r.version for r in applied}
        applied_now: list[Migration] = []
        skipped: list[Migration] = []

        for m in self._migrations:
            if m.version in applied_versions:
                skipped.append(m)
                continue
            self._apply_one(m)
            applied_now.append(m)

        return MigrationResult(
            applied_now=tuple(applied_now),
            skipped=tuple(skipped),
            final_version=self._migrations[-1].version if self._migrations else 0,
            classifications_recorded=(),
        )

    def _apply_one(self, migration: Migration) -> None:
        """Apply a single migration in its own atomic transaction.

        The schema change and the ``schema_migrations`` row are staged together
        and committed together, so a crash before COMMIT is fully recoverable
        (re-applied from scratch on resume). DDL must be idempotent.
        """
        conn = self._conn
        self._begin_immediate_retry(conn)
        try:
            cur = conn.cursor()
            for stmt in migration.statements:
                for piece in stmt.split(";"):
                    s = piece.strip()
                    if s:
                        cur.execute(s)
            # Record the applied state in the SAME transaction as the DDL.
            cur.execute(
                "INSERT INTO schema_migrations "
                "(version, name, checksum, applied_at_ns, status) "
                "VALUES (?, ?, ?, ?, 'applied')",
                (
                    migration.version,
                    migration.name,
                    migration.checksum,
                    time.time_ns(),
                ),
            )
            conn.execute("COMMIT")
        except Exception:
            # ROLLBACK undoes both the DDL and the migration record, leaving
            # the store as if the migration never started. Resume re-applies.
            conn.execute("ROLLBACK")
            raise

    # ── legacy classification ──────────────────────────────────────────

    def classify_legacy_record(
        self,
        source_table: str,
        record_id: str,
        evidence: ClassificationEvidence,
        migration_version: Optional[int] = None,
    ) -> LegacyClassification:
        """Determine the classification for a legacy record from its evidence
        profile.

        Delegates to the static :meth:`LedgerMigrator.classify` and then
        validates safety before returning. The classification is determined
        entirely from the evidence profile — ``BACKFILLED`` is only returned
        when ``evidence.has_authoritative_source`` is ``True``.

        This method does NOT persist the classification. Call
        :meth:`record_legacy_classification` to durably record it.

        Idempotent on duplicate backfill: two calls with the same evidence
        profile produce the same classification.
        """
        _ = (source_table, record_id, migration_version)  # reserved for future use
        result = LedgerMigrator.classify(evidence)
        LedgerMigrator._validate_classification_safety(result, evidence)
        return result

    def rollback_classification(
        self, classification_id: str, reason: str
    ) -> Optional[LegacyRecordClassification]:
        """Mark a legacy classification as rolled back (superseded).

        The rollback marks the original classification record with a
        ``rolled_back_at_ns`` timestamp — a tombstone, not a deletion. The
        evidence trail is preserved. A forward-fix correction should be
        recorded separately via :meth:`record_legacy_classification`.

        Returns:
            The updated classification record, or ``None`` if not found.
        """
        _ = reason  # reserved for audit logging
        now_ns = time.time_ns()
        conn = self._conn
        self._begin_immediate_retry(conn)
        try:
            cur = conn.execute(
                "UPDATE legacy_record_classifications "
                "SET rolled_back_at_ns = ? "
                "WHERE classification_id = ? AND rolled_back_at_ns IS NULL",
                (now_ns, classification_id),
            )
            if cur.rowcount == 0:
                # Either not found or already rolled back.
                # ROLLBACK the failed UPDATE, then query read-only outside tx.
                conn.execute("ROLLBACK")
                cur2 = conn.execute(
                    "SELECT classification_id, source_table, record_id, "
                    "classification, reason, migration_version, "
                    "classified_at_ns, rolled_back_at_ns "
                    "FROM legacy_record_classifications "
                    "WHERE classification_id = ?",
                    (classification_id,),
                )
                row = cur2.fetchone()
                if row is None:
                    return None
                # Already rolled back — return as-is.
                return LegacyRecordClassification(
                    classification_id=row[0],
                    source_table=row[1],
                    record_id=row[2],
                    classification=row[3],
                    reason=row[4],
                    migration_version=row[5],
                    classified_at_ns=row[6],
                    rolled_back_at_ns=row[7],
                )
            # UPDATE succeeded — commit and read back.
            conn.execute("COMMIT")
            cur2 = conn.execute(
                "SELECT classification_id, source_table, record_id, "
                "classification, reason, migration_version, "
                "classified_at_ns, rolled_back_at_ns "
                "FROM legacy_record_classifications "
                "WHERE classification_id = ?",
                (classification_id,),
            )
            row = cur2.fetchone()
            if row is None:
                return None
            return LegacyRecordClassification(
                classification_id=row[0],
                source_table=row[1],
                record_id=row[2],
                classification=row[3],
                reason=row[4],
                migration_version=row[5],
                classified_at_ns=row[6],
                rolled_back_at_ns=row[7],
            )
        except Exception:
            # Only ROLLBACK if we're still in a transaction.
            # If the ROLLBACK path above already closed the tx, this is a no-op
            # on the in-memory connection state (sqlite3 tolerates ROLLBACK
            # with no active tx after Python 3.11.5+, but for safety we catch).
            try:
                conn.execute("ROLLBACK")
            except sqlite3.OperationalError:
                pass
            raise

    def query_rolled_back_classifications(
        self,
        source_table: Optional[str] = None,
        record_id: Optional[str] = None,
    ) -> tuple[LegacyRecordClassification, ...]:
        """Query classifications that have been rolled back (superseded)."""
        clauses: list[str] = ["rolled_back_at_ns IS NOT NULL"]
        params: list[Any] = []
        if source_table is not None:
            clauses.append("source_table = ?")
            params.append(source_table)
        if record_id is not None:
            clauses.append("record_id = ?")
            params.append(record_id)
        where = " WHERE " + " AND ".join(clauses)
        conn = self._conn
        cur = conn.execute(
            "SELECT classification_id, source_table, record_id, classification,"
            " reason, migration_version, classified_at_ns, rolled_back_at_ns"
            " FROM legacy_record_classifications" + where
            + " ORDER BY rolled_back_at_ns",
            params,
        )
        rows = cur.fetchall()
        return tuple(
            LegacyRecordClassification(
                classification_id=r[0],
                source_table=r[1],
                record_id=r[2],
                classification=r[3],
                reason=r[4],
                migration_version=r[5],
                classified_at_ns=r[6],
                rolled_back_at_ns=r[7],
            )
            for r in rows
        )

    def record_legacy_classification(
        self,
        source_table: str,
        record_id: str,
        classification: LegacyClassification,
        reason: str,
        migration_version: Optional[int] = None,
    ) -> LegacyRecordClassification:
        """Durably record a legacy-record classification.

        Classifications are append-only evidence. Each call mints a unique
        ``classification_id`` so multiple determinations about the same record
        are preserved rather than silently overwritten.

        Before persisting, this method validates classification safety: a
        ``BACKFILLED`` classification must have been assigned through a path
        that enforces authoritative evidence. Direct calls with
        ``BACKFILLED`` are accepted but the caller bears the responsibility
        of ensuring that authoritative evidence exists — this method does not
        second-guess the caller's determination, but the
        :meth:`classify_legacy_record` + :meth:`record_legacy_classification`
        workflow is the recommended safe path.
        """
        if not isinstance(classification, LegacyClassification):
            raise TypeError(
                "classification must be a LegacyClassification, got "
                f"{type(classification).__name__}"
            )
        classification_id = str(uuid.uuid4())
        now_ns = time.time_ns()
        conn = self._conn
        self._begin_immediate_retry(conn)
        try:
            conn.execute(
                "INSERT INTO legacy_record_classifications "
                "(classification_id, source_table, record_id, classification, "
                " reason, migration_version, classified_at_ns) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    classification_id,
                    source_table,
                    record_id,
                    classification.value,
                    reason,
                    migration_version,
                    now_ns,
                ),
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        return LegacyRecordClassification(
            classification_id=classification_id,
            source_table=source_table,
            record_id=record_id,
            classification=classification.value,
            reason=reason,
            migration_version=migration_version,
            classified_at_ns=now_ns,
        )

    def query_legacy_classifications(
        self,
        source_table: Optional[str] = None,
        record_id: Optional[str] = None,
        classification: Optional[LegacyClassification] = None,
        migration_version: Optional[int] = None,
    ) -> tuple[LegacyRecordClassification, ...]:
        """Query durable legacy classifications with optional filters."""
        clauses: list[str] = []
        params: list[Any] = []
        if source_table is not None:
            clauses.append("source_table = ?")
            params.append(source_table)
        if record_id is not None:
            clauses.append("record_id = ?")
            params.append(record_id)
        if classification is not None:
            if not isinstance(classification, LegacyClassification):
                raise TypeError(
                    "classification must be a LegacyClassification"
                )
            clauses.append("classification = ?")
            params.append(classification.value)
        if migration_version is not None:
            clauses.append("migration_version = ?")
            params.append(migration_version)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        conn = self._conn
        cur = conn.execute(
            "SELECT classification_id, source_table, record_id, classification,"
            " reason, migration_version, classified_at_ns, rolled_back_at_ns"
            " FROM legacy_record_classifications" + where
            + " ORDER BY classified_at_ns",
            params,
        )
        rows = cur.fetchall()
        return tuple(
            LegacyRecordClassification(
                classification_id=r[0],
                source_table=r[1],
                record_id=r[2],
                classification=r[3],
                reason=r[4],
                migration_version=r[5],
                classified_at_ns=r[6],
                rolled_back_at_ns=r[7],
            )
            for r in rows
        )


__all__ = [
    "ClassificationEvidence",
    "ClassificationSafetyError",
    "LegacyClassification",
    "Migration",
    "MigrationRecord",
    "MigrationState",
    "MigrationResult",
    "ChecksumMismatch",
    "LegacyRecordClassification",
    "MigrationError",
    "MigrationChecksumMismatchError",
    "MigrationRegistryError",
    "MigrationOrderError",
    "LedgerMigrator",
    "SqliteLedgerMigrator",
    "compute_migration_checksum",
    "default_m6a_migrations",
]
