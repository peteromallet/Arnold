"""Production owner adapters for ``occurrence_child_migration.v1``.

The coordinator is intentionally storage-neutral, but a cloud launch must
bind it to the *actual* owners.  This module provides those small bindings:

* :class:`RunAuthorityJournalOwner` delegates to the canonical
  ``RunAuthorityJournal`` supplied by the runtime.  C116's checkout contains
  the Run Authority contracts and reducer but no journal writer, so a missing
  journal is an explicit :class:`OwnerUnavailable` rather than permission to
  manufacture a child from r5 projections.
* :class:`CustodyLeaseStoreOwner` delegates lifecycle writes to
  :class:`CustodyLeaseStore`.
* :class:`AttemptLedgerWbcOwner` delegates GLEK reservation/read to the
  canonical :class:`AttemptLedgerStore`.

None of these adapters calls a provider.  ``RunAuthorityJournal`` is a
protocol for the runtime-owned implementation; this package does not create
a parallel authority journal merely to make a migration appear successful.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol, runtime_checkable

from arnold.workflow.attempt_ledger_store import AttemptLedgerStore
from arnold.workflow.execution_attempt_ledger import GlobalEffectIdentity
from arnold_pipelines.megaplan.custody.contracts import (
    CustodyLease,
    RepairOccurrenceKey,
    process_birth_identity,
)
from arnold_pipelines.megaplan.custody.lease_store import (
    CustodyLeaseStore,
    LeaseStoreError,
)
from arnold_pipelines.megaplan.migration.occurrence_child_migration import (
    ChildAuthority,
    ChildIdentity,
    CustodyOwner,
    MigrationError,
    MigrationIndeterminate,
    OwnerUnavailable,
    ParentAuthoritySnapshot,
    ParentCommitReceipt,
    ParentEvidence,
    RunAuthorityOwner,
    WbcOwner,
    WbcReservation,
)
from arnold_pipelines.run_authority.contracts import CASExpectation, QuarantineRecord


@runtime_checkable
class RunAuthorityJournal(Protocol):
    """Canonical RA journal contract required by the migration.

    The concrete cloud implementation owns locking, cursor assignment,
    append-only records, and idempotency.  It must not be a reducer projection
    or a status sidecar.  Method names intentionally differ from the
    coordinator's generic owner names so an accidental projection cannot be
    passed without an explicit adapter.
    """

    def snapshot(self, run_id: str, run_revision: str) -> ParentAuthoritySnapshot: ...

    def migration_receipt(self, migration_idempotency_key: str) -> ParentCommitReceipt | None: ...

    def compare_and_swap_parent(
        self,
        *,
        expected: CASExpectation,
        migration_idempotency_key: str,
        quarantine: QuarantineRecord,
    ) -> ParentCommitReceipt: ...

    def child_authority(self, migration_idempotency_key: str) -> ChildAuthority | None: ...

    def append_child_authority(
        self,
        *,
        identity: ChildIdentity,
        parent: ParentEvidence,
        migration_idempotency_key: str,
    ) -> ChildAuthority: ...


def _require_method(owner: Any, name: str) -> Any:
    method = getattr(owner, name, None)
    if not callable(method):
        raise OwnerUnavailable(
            "canonical RunAuthorityJournal is unavailable or does not expose "
            f"{name}(); r5 projections cannot mint a fresh child"
        )
    return method


@dataclass
class RunAuthorityJournalOwner(RunAuthorityOwner):
    """Bind coordinator calls to one canonical runtime RA journal."""

    journal: RunAuthorityJournal | None

    def __post_init__(self) -> None:
        if self.journal is None:
            raise OwnerUnavailable(
                "no canonical RunAuthorityJournal is configured for C116; "
                "old r5 owner records are absent, so a fresh child must not "
                "pretend to migrate the stalled occurrence"
            )
        required = (
            "snapshot",
            "migration_receipt",
            "compare_and_swap_parent",
            "child_authority",
            "append_child_authority",
        )
        missing = [name for name in required if not callable(getattr(self.journal, name, None))]
        if missing:
            raise OwnerUnavailable(
                "canonical RunAuthorityJournal is incomplete; missing "
                + ", ".join(missing)
            )

    def read_parent(self, run_id: str, run_revision: str) -> ParentAuthoritySnapshot:
        assert self.journal is not None
        try:
            return self.journal.snapshot(run_id, run_revision)
        except (FileNotFoundError, KeyError) as exc:
            raise OwnerUnavailable(
                "canonical RunAuthorityJournal has no authoritative parent "
                "records; refusing to migrate an r5 projection"
            ) from exc

    def read_parent_commit(self, migration_idempotency_key: str) -> ParentCommitReceipt | None:
        assert self.journal is not None
        return self.journal.migration_receipt(migration_idempotency_key)

    def commit_parent(
        self,
        *,
        expected: CASExpectation,
        migration_idempotency_key: str,
        quarantine: QuarantineRecord,
    ) -> ParentCommitReceipt:
        assert self.journal is not None
        return self.journal.compare_and_swap_parent(
            expected=expected,
            migration_idempotency_key=migration_idempotency_key,
            quarantine=quarantine,
        )

    def allocate_child(
        self,
        *,
        identity: ChildIdentity,
        parent: ParentEvidence,
        migration_idempotency_key: str,
    ) -> ChildAuthority:
        assert self.journal is not None
        try:
            return self.journal.append_child_authority(
                identity=identity,
                parent=parent,
                migration_idempotency_key=migration_idempotency_key,
            )
        except (FileNotFoundError, KeyError) as exc:
            raise OwnerUnavailable(
                "canonical RunAuthorityJournal cannot allocate a child "
                "because authoritative parent records are absent"
            ) from exc

    def read_child(self, migration_idempotency_key: str) -> ChildAuthority | None:
        assert self.journal is not None
        return self.journal.child_authority(migration_idempotency_key)


@dataclass
class AttemptLedgerWbcOwner(WbcOwner):
    """Bind WBC reservations to the canonical attempt-ledger store."""

    store: AttemptLedgerStore

    def __post_init__(self) -> None:
        if not isinstance(self.store, AttemptLedgerStore):
            raise OwnerUnavailable(
                "WBC migration requires the canonical AttemptLedgerStore; "
                "a projection or synthetic store is not an owner"
            )
        required = ("initialize_attempt", "reserve_global_effect", "get_global_effect_reservation")
        missing = [name for name in required if not callable(getattr(self.store, name, None))]
        if missing:
            raise OwnerUnavailable(
                "canonical AttemptLedgerStore is incomplete; missing " + ", ".join(missing)
            )

    def read_reservation(self, attempt_id: str, glek: str) -> WbcReservation | None:
        reservation = self.store.get_global_effect_reservation(attempt_id, glek)
        if reservation is None:
            return None
        if reservation.attempt_id != attempt_id or reservation.global_logical_effect_key != glek:
            raise MigrationError("canonical WBC store returned a divergent reservation")
        return WbcReservation(attempt_id=attempt_id, reservation=reservation)

    def reserve_child(
        self,
        *,
        attempt_id: str,
        effect_identity: GlobalEffectIdentity,
        migration_idempotency_key: str,
    ) -> WbcReservation:
        try:
            self.store.initialize_attempt(attempt_id)
            reservation = self.store.reserve_global_effect(attempt_id, effect_identity)
        except Exception as exc:
            raise MigrationIndeterminate("canonical WBC reservation outcome is unknown") from exc
        if reservation.global_logical_effect_key != effect_identity.global_logical_effect_key:
            raise MigrationError("canonical WBC store returned a divergent GLEK")
        return WbcReservation(attempt_id=attempt_id, reservation=reservation)


@dataclass
class CustodyLeaseStoreOwner(CustodyOwner):
    """Bind child lease lifecycle to the canonical CustodyLeaseStore."""

    store: CustodyLeaseStore
    lease_ttl_seconds: int = 1800
    owner_host: str | None = None
    owner_pid: str | None = None
    owner_boot_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.store, CustodyLeaseStore):
            raise OwnerUnavailable(
                "Custody migration requires the canonical CustodyLeaseStore; "
                "a writer-map projection is not an owner"
            )
        if self.lease_ttl_seconds < 1:
            raise ValueError("lease_ttl_seconds must be positive")
        identity = process_birth_identity()
        self.owner_host = self.owner_host if self.owner_host is not None else identity.get("host", "")
        self.owner_pid = self.owner_pid if self.owner_pid is not None else identity.get("pid", "")
        self.owner_boot_id = self.owner_boot_id if self.owner_boot_id is not None else identity.get("boot_id", "")
        if not self.owner_host or not self.owner_pid:
            raise OwnerUnavailable("Custody owner process identity is unavailable")

    def read_lease(self, lease_id: str) -> CustodyLease | None:
        return self.store.current_lease(lease_id)

    def acquire_child(
        self,
        *,
        lease_id: str,
        occurrence: RepairOccurrenceKey,
        authority: ChildAuthority,
        wbc: WbcReservation,
        idempotency_key: str,
    ) -> CustodyLease:
        now = datetime.now(timezone.utc)
        expires = now + timedelta(seconds=self.lease_ttl_seconds)
        try:
            self.store.acquire(
                lease_id=lease_id,
                owner_host=self.owner_host or "",
                owner_pid=self.owner_pid or "",
                owner_boot_id=self.owner_boot_id or "",
                run_authority_grant_id=authority.grant.grant_id,
                coordinator_fence_token=authority.fence.token,
                wbc_attempt_reference=wbc.attempt_id,
                occurrence_digest=occurrence.occurrence_digest,
                custody_epoch=1,
                expires_at=expires.isoformat().replace("+00:00", "Z"),
                idempotency_key=idempotency_key,
                payload={
                    "schema": "arnold.megaplan.occurrence_child_migration.v1",
                    "migration_idempotency_key": idempotency_key,
                    "occurrence_digest": occurrence.occurrence_digest,
                    "occurrence_key": occurrence.to_dict(),
                },
            )
        except LeaseStoreError as exc:
            raise MigrationIndeterminate("canonical Custody lease outcome is unknown") from exc
        lease = self.store.current_lease(lease_id)
        if lease is None:
            raise MigrationIndeterminate("canonical Custody lease was not readable after acquire")
        return lease


__all__ = [
    "AttemptLedgerWbcOwner",
    "CustodyLeaseStoreOwner",
    "RunAuthorityJournal",
    "RunAuthorityJournalOwner",
]
