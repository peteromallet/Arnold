"""Provider-free, crash-safe occurrence-to-child migration.

This module is the narrow implementation seam for the VJ24/C116 migration.
It is deliberately a coordinator, not a replacement for any owner:

* Run Authority owns the parent compare-and-swap, quarantine, and child
  authority allocation.
* Custody owns the child lease and its epoch/owner invariants.
* WBC owns the child attempt/GLEK reservation.
* This module only derives deterministic identities, orders idempotent owner
  calls, and independently rereads every owner after each mutation.

There is no provider call here.  A caller can safely retry :meth:`commit` or
:meth:`recover` after any process crash.  Cross-owner writes are not assumed
to be atomic: a durable parent quarantine is intentionally a safe prefix, and
recovery completes missing child records from the same idempotency key.

The owner protocols are explicit because C116 has no generic Run Authority
writer API.  Production wiring must provide adapters to the canonical owner
APIs; passing a projection, cache, synthetic WBC reference, or local shadow
store is rejected by the coordinator.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol, runtime_checkable
import uuid

from arnold.workflow.attempt_ledger_store import GlobalEffectReservation
from arnold.workflow.execution_attempt_ledger import GlobalEffectIdentity
from arnold_pipelines.megaplan.custody.contracts import (
    CustodyTargetKey,
    CustodyLease,
    RepairOccurrenceKey,
)
from arnold_pipelines.run_authority.contracts import (
    CASExpectation,
    CapabilityGrant,
    Claim,
    CoordinatorFence,
    Decision,
    EvidenceEnvelope,
    QuarantineRecord,
    SubjectAttempt,
    canonical_json,
    validate_relationships,
)
from arnold_pipelines.run_authority.current_source import (
    CurrentSourceRequest,
    evaluate_current_source,
)
from arnold_pipelines.run_authority.reducer import RunAuthorityView


CHILD_MIGRATION_SCHEMA = "arnold.megaplan.occurrence_child_migration.v1"
_NAMESPACE = uuid.UUID("8e47aab1-7e31-5a12-a60e-8b266c2c57f7")


class MigrationError(RuntimeError):
    """Base class for fail-closed migration errors."""


class SelectorDrift(MigrationError):
    """The selector used at commit differs from the prepared selector."""


class SameOccurrenceQuarantined(MigrationError):
    """The parent occurrence is no longer a valid current source."""


class MigrationConflict(MigrationError):
    """An owner already contains a divergent idempotency payload."""


class MigrationIndeterminate(MigrationError):
    """An owner write may have happened but cannot be verified safely."""


class OwnerUnavailable(MigrationError):
    """A required canonical owner adapter was not supplied."""


class ProviderEffectForbidden(MigrationError):
    """Provider dispatch is outside this coordinator by design."""


class MigrationStatus(str, Enum):
    PREPARED = "prepared"
    COMMITTED = "committed"
    ALREADY_COMMITTED = "already_committed"
    INDETERMINATE = "indeterminate"


def _digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _plain(value[k]) for k in sorted(value)}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return _plain(value.to_dict())
    return value


@dataclass(frozen=True)
class ChildSelector:
    """Immutable, hashed selector for the requested child run."""

    child_revision: str
    selector: Mapping[str, Any]

    def __post_init__(self) -> None:
        if not isinstance(self.child_revision, str) or not self.child_revision.strip():
            raise ValueError("child_revision must be non-empty")
        # Force canonical serialisability at the boundary.  This also stops
        # caller mutation from changing a prepared digest later.
        frozen = json.loads(canonical_json(_plain(self.selector)))
        object.__setattr__(self, "selector", frozen)

    @property
    def selector_digest(self) -> str:
        return _digest({"child_revision": self.child_revision, "selector": self.selector})

    def to_dict(self) -> dict[str, Any]:
        return {
            "child_revision": self.child_revision,
            "selector": _plain(self.selector),
            "selector_digest": self.selector_digest,
        }


@dataclass(frozen=True)
class ParentAuthoritySnapshot:
    """The exact Run Authority projection and its owner cursor."""

    view: RunAuthorityView
    journal_cursor: int | None = None

    def __post_init__(self) -> None:
        cursor = self.view.journal_cursor if self.journal_cursor is None else self.journal_cursor
        if not isinstance(cursor, int) or isinstance(cursor, bool) or cursor < 0:
            raise ValueError("journal_cursor must be a non-negative integer")
        # Never allow a caller to substitute an unrelated cursor for the
        # projection's own authoritative cursor.
        if cursor != self.view.journal_cursor:
            raise ValueError(
                "journal_cursor must equal RunAuthorityView.journal_cursor; "
                "the migration must CAS the owner cursor, not a derived hash"
            )
        object.__setattr__(self, "journal_cursor", cursor)


@dataclass(frozen=True)
class WbcReservation:
    """Authoritative WBC store evidence; projections are never accepted."""

    attempt_id: str
    reservation: GlobalEffectReservation
    source: str = "store"

    def __post_init__(self) -> None:
        if self.source != "store":
            raise ValueError("WBC migration evidence must come from the canonical store")
        if self.attempt_id != self.reservation.attempt_id:
            raise ValueError("WBC attempt identity mismatch")

    @property
    def glek(self) -> str:
        return self.reservation.global_logical_effect_key


@dataclass(frozen=True)
class ParentEvidence:
    """Frozen, read-only evidence captured before a migration commit."""

    occurrence: RepairOccurrenceKey
    authority: ParentAuthoritySnapshot
    source_request: CurrentSourceRequest
    custody_lease: CustodyLease
    wbc: WbcReservation

    def __post_init__(self) -> None:
        if self.occurrence.occurrence_digest != self.custody_lease.occurrence_key.occurrence_digest:
            raise ValueError("parent custody lease is for a different occurrence")
        if self.occurrence.wbc_attempt_reference != self.wbc.attempt_id:
            raise ValueError("parent occurrence and WBC attempt differ")
        if self.custody_lease.wbc_attempt_reference != self.wbc.attempt_id:
            raise ValueError("parent custody lease and WBC attempt differ")
        if self.custody_lease.run_authority_grant_id != self.source_request.grant_id:
            raise ValueError("parent custody lease and Run Authority grant differ")
        if self.custody_lease.coordinator_fence_token != self.occurrence.fence_token:
            raise ValueError("parent custody lease and occurrence fence differ")
        if str(self.source_request.run_id) != str(self.occurrence.run_id):
            raise ValueError("parent source request and occurrence run differ")
        if str(self.source_request.run_revision) != str(self.occurrence.run_revision):
            raise ValueError("parent source request and occurrence revision differ")

    @property
    def cursor(self) -> int:
        return int(self.authority.journal_cursor)

    @property
    def evidence_ids(self) -> tuple[str, ...]:
        return tuple(item.evidence_id for item in self.authority.view.evidence)


@dataclass(frozen=True)
class ChildIdentity:
    """Deterministic child identity; owner-assigned fence/epoch are excluded."""

    parent_occurrence_digest: str
    selector_digest: str
    child_revision: str
    child_run_id: str
    coordinator_attempt_id: str
    subject_attempt_id: str
    wbc_attempt_id: str
    glek: str
    migration_idempotency_key: str

    def to_dict(self) -> dict[str, str]:
        return {
            "parent_occurrence_digest": self.parent_occurrence_digest,
            "selector_digest": self.selector_digest,
            "child_revision": self.child_revision,
            "child_run_id": self.child_run_id,
            "coordinator_attempt_id": self.coordinator_attempt_id,
            "subject_attempt_id": self.subject_attempt_id,
            "wbc_attempt_id": self.wbc_attempt_id,
            "glek": self.glek,
            "migration_idempotency_key": self.migration_idempotency_key,
        }


@dataclass(frozen=True)
class ChildAuthority:
    """Actual child authority records returned by the Run Authority owner."""

    fence: CoordinatorFence
    grant: CapabilityGrant
    attempt: SubjectAttempt
    claim: Claim
    evidence: tuple[EvidenceEnvelope, ...]
    decision: Decision | None = None

    def validate(self) -> None:
        validate_relationships(
            fence=self.fence,
            grant=self.grant,
            attempt=self.attempt,
            claim=self.claim,
            evidence=tuple(self.evidence),
            decision=self.decision,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "fence": self.fence.to_dict(),
            "grant": self.grant.to_dict(),
            "attempt": self.attempt.to_dict(),
            "claim": self.claim.to_dict(),
            "evidence": [item.to_dict() for item in self.evidence],
            "decision": self.decision.to_dict() if self.decision is not None else None,
        }


@dataclass(frozen=True)
class ParentCommitReceipt:
    """Receipt from the atomic RA parent CAS/quarantine operation."""

    migration_idempotency_key: str
    parent_cursor: int
    quarantine: QuarantineRecord


@dataclass(frozen=True)
class HandoffArtifact:
    path: str
    digest: str
    kind: str


@dataclass(frozen=True)
class MigrationReceipt:
    migration_idempotency_key: str
    status: MigrationStatus
    child: ChildIdentity
    parent_commit: ParentCommitReceipt
    authority: ChildAuthority
    wbc: WbcReservation
    custody: CustodyLease
    artifacts: tuple[HandoffArtifact, ...] = ()


@runtime_checkable
class RunAuthorityOwner(Protocol):
    """Canonical RA owner adapter required by the coordinator.

    ``commit_parent`` MUST atomically append the quarantine and advance the
    parent cursor under ``expected``.  It must return the owner-observed
    cursor, not the caller's proposed value.  ``allocate_child`` is an
    idempotent allocation keyed by ``migration_idempotency_key``.
    """

    def read_parent(self, run_id: str, run_revision: str) -> ParentAuthoritySnapshot: ...

    def read_parent_commit(self, migration_idempotency_key: str) -> ParentCommitReceipt | None: ...

    def commit_parent(
        self,
        *,
        expected: CASExpectation,
        migration_idempotency_key: str,
        quarantine: QuarantineRecord,
    ) -> ParentCommitReceipt: ...

    def allocate_child(
        self,
        *,
        identity: ChildIdentity,
        parent: ParentEvidence,
        migration_idempotency_key: str,
    ) -> ChildAuthority: ...

    def read_child(self, migration_idempotency_key: str) -> ChildAuthority | None: ...


@runtime_checkable
class WbcOwner(Protocol):
    """Canonical WBC attempt-ledger owner adapter."""

    def read_reservation(self, attempt_id: str, glek: str) -> WbcReservation | None: ...

    def reserve_child(
        self,
        *,
        attempt_id: str,
        effect_identity: GlobalEffectIdentity,
        migration_idempotency_key: str,
    ) -> WbcReservation: ...


@runtime_checkable
class CustodyOwner(Protocol):
    """Canonical Custody lease owner adapter."""

    def read_lease(self, lease_id: str) -> CustodyLease | None: ...

    def acquire_child(
        self,
        *,
        lease_id: str,
        occurrence: RepairOccurrenceKey,
        authority: ChildAuthority,
        wbc: WbcReservation,
        idempotency_key: str,
    ) -> CustodyLease: ...


class HandoffArtifactWriter(Protocol):
    """Evidence-only artifact sink; artifacts never authorize a mutation."""

    def write(self, *, migration_idempotency_key: str, kind: str, payload: Mapping[str, Any]) -> HandoffArtifact: ...


class FilesystemHandoffArtifactWriter:
    """Content-addressed, atomic evidence writer for handoff receipts."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def write(self, *, migration_idempotency_key: str, kind: str, payload: Mapping[str, Any]) -> HandoffArtifact:
        material = canonical_json(_plain(payload))
        digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
        safe_id = migration_idempotency_key.replace(":", "_")
        path = self.root / CHILD_MIGRATION_SCHEMA / safe_id / f"{kind}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            existing = path.read_text(encoding="utf-8")
            if existing != material:
                raise MigrationConflict(f"handoff artifact diverged: {path}")
        else:
            tmp = path.with_suffix(path.suffix + ".tmp")
            tmp.write_text(material, encoding="utf-8")
            tmp.replace(path)
        return HandoffArtifact(str(path), digest, kind)


@dataclass(frozen=True)
class PreparedMigration:
    """Side-effect-free preparation result accepted by :meth:`commit`."""

    parent: ParentEvidence
    selector: ChildSelector
    child: ChildIdentity
    effect_identity: GlobalEffectIdentity
    quarantine: QuarantineRecord
    migration_idempotency_key: str
    schema: str = CHILD_MIGRATION_SCHEMA


def _make_child_identity(parent: ParentEvidence, selector: ChildSelector) -> tuple[ChildIdentity, GlobalEffectIdentity]:
    request_identity = _digest(
        {
            "schema": CHILD_MIGRATION_SCHEMA,
            "parent_occurrence_digest": parent.occurrence.occurrence_digest,
            "selector_digest": selector.selector_digest,
            "child_revision": selector.child_revision,
        }
    )
    child_run_id = f"{parent.occurrence.run_id}:child:{request_identity[:24]}"
    coordinator_id = f"migration:{request_identity[:24]}"
    attempt_uuid = str(uuid.uuid5(_NAMESPACE, f"{CHILD_MIGRATION_SCHEMA}:{request_identity}"))
    effect_identity = GlobalEffectIdentity(
        environment_id=parent.occurrence.target.environment,
        action_target="occurrence-child-migration",
        action_version="v1",
        effect_family=CHILD_MIGRATION_SCHEMA,
        provider_target=child_run_id,
        canonical_request_identity=request_identity,
        boundary_schema_hash=hashlib.sha256(CHILD_MIGRATION_SCHEMA.encode("utf-8")).hexdigest(),
    )
    glek = effect_identity.global_logical_effect_key
    migration_key = f"{CHILD_MIGRATION_SCHEMA}:{glek}"
    child = ChildIdentity(
        parent_occurrence_digest=parent.occurrence.occurrence_digest,
        selector_digest=selector.selector_digest,
        child_revision=selector.child_revision,
        child_run_id=child_run_id,
        coordinator_attempt_id=coordinator_id,
        subject_attempt_id=attempt_uuid,
        wbc_attempt_id=attempt_uuid,
        glek=glek,
        migration_idempotency_key=migration_key,
    )
    return child, effect_identity


def _find_quarantine_ids(parent: ParentEvidence) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                parent.source_request.grant_id,
                str(parent.source_request.fence_token),
                parent.source_request.subject_attempt_id,
                parent.source_request.decision_id,
                parent.occurrence.occurrence_digest,
            }
        )
    )


def _build_quarantine(parent: ParentEvidence, selector: ChildSelector, key: str) -> QuarantineRecord:
    payload = {
        "migration_schema": CHILD_MIGRATION_SCHEMA,
        "migration_idempotency_key": key,
        "occurrence_digest": parent.occurrence.occurrence_digest,
        "selector_digest": selector.selector_digest,
        "grant_id": parent.source_request.grant_id,
        "fence_token": str(parent.source_request.fence_token),
        "subject_attempt_id": parent.source_request.subject_attempt_id,
        "decision_id": parent.source_request.decision_id,
    }
    material = canonical_json(payload)
    qid = "quarantine-" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:32]
    return QuarantineRecord(
        quarantine_id=qid,
        run_id=parent.occurrence.run_id,
        run_revision=parent.occurrence.run_revision,
        record_type="repair_occurrence",
        record_id=parent.occurrence.occurrence_digest,
        reason="occurrence_migrated_to_child",
        source=f"contract://{CHILD_MIGRATION_SCHEMA}/{key}",
        evidence_ids=parent.evidence_ids,
        payload=payload,
    )


class MigrationCoordinator:
    """Coordinate one deterministic parent-occurrence -> child migration."""

    def __init__(
        self,
        *,
        run_authority: RunAuthorityOwner,
        wbc: WbcOwner,
        custody: CustodyOwner,
        artifacts: HandoffArtifactWriter | None = None,
        after_step: Callable[[str], None] | None = None,
    ) -> None:
        self.run_authority = run_authority
        self.wbc = wbc
        self.custody = custody
        self.artifacts = artifacts
        self.after_step = after_step

    def prepare(self, parent: ParentEvidence, selector: ChildSelector) -> PreparedMigration:
        """Read/validate evidence and derive identities without mutation."""
        current = evaluate_current_source(parent.authority.view, parent.source_request)
        if not current.status.is_satisfied:
            raise SameOccurrenceQuarantined(current.reason)
        # Ensure the current projection actually contains the same occurrence
        # identity and owner cursor that will be used by CAS.
        if parent.authority.journal_cursor != parent.authority.view.journal_cursor:
            raise MigrationIndeterminate("parent cursor is not the authoritative RA cursor")
        if parent.wbc.glek.startswith("wbc-ref-") or not parent.wbc.glek.startswith("glek:"):
            raise MigrationError("synthetic or malformed WBC GLEK evidence")
        child, effect_identity = _make_child_identity(parent, selector)
        quarantine = _build_quarantine(parent, selector, child.migration_idempotency_key)
        return PreparedMigration(
            parent=parent,
            selector=selector,
            child=child,
            effect_identity=effect_identity,
            quarantine=quarantine,
            migration_idempotency_key=child.migration_idempotency_key,
        )

    def _step(self, name: str) -> None:
        if self.after_step is not None:
            self.after_step(name)

    @staticmethod
    def _assert_prepared_integrity(prepared: PreparedMigration) -> None:
        """Reject an in-memory prepared receipt whose selector was changed."""
        child, effect_identity = _make_child_identity(prepared.parent, prepared.selector)
        if child != prepared.child or effect_identity != prepared.effect_identity:
            raise SelectorDrift(
                "prepared selector/identity no longer matches the canonical request"
            )
        if prepared.quarantine.payload.get("selector_digest") != prepared.selector.selector_digest:
            raise SelectorDrift("prepared quarantine selector digest diverged")

    @staticmethod
    def _validate_parent_commit(
        prepared: PreparedMigration, parent_commit: ParentCommitReceipt
    ) -> None:
        if parent_commit.migration_idempotency_key != prepared.migration_idempotency_key:
            raise MigrationConflict("Run Authority returned a divergent migration key")
        if parent_commit.quarantine.payload.get("migration_idempotency_key") != prepared.migration_idempotency_key:
            raise MigrationConflict("Run Authority quarantine is for a different migration")
        if parent_commit.quarantine.payload.get("occurrence_digest") != prepared.parent.occurrence.occurrence_digest:
            raise MigrationConflict("Run Authority quarantine targets a different occurrence")
        if parent_commit.parent_cursor <= prepared.parent.cursor:
            raise MigrationIndeterminate("Run Authority returned a non-advanced parent cursor")

    @staticmethod
    def _validate_child_authority(prepared: PreparedMigration, authority: ChildAuthority) -> None:
        if authority.fence.run_id != prepared.child.child_run_id:
            raise MigrationConflict("child Run Authority fence has a divergent run")
        if authority.fence.run_revision != prepared.child.child_revision:
            raise MigrationConflict("child Run Authority fence has a divergent revision")
        if authority.fence.coordinator_attempt_id != prepared.child.coordinator_attempt_id:
            raise MigrationConflict("child Run Authority fence has a divergent coordinator")
        if authority.attempt.attempt_id != prepared.child.subject_attempt_id:
            raise MigrationConflict("child Run Authority attempt is not deterministic")
        authority.validate()

    def _reread_parent(self, prepared: PreparedMigration) -> ParentEvidence:
        snapshot = self.run_authority.read_parent(
            prepared.parent.occurrence.run_id,
            prepared.parent.occurrence.run_revision,
        )
        # ``prepare`` may have taken place long ago.  Re-evaluate against this
        # fresh owner read immediately before the owner CAS.
        current = evaluate_current_source(snapshot.view, prepared.parent.source_request)
        if not current.status.is_satisfied:
            raise SameOccurrenceQuarantined(current.reason)
        if snapshot.journal_cursor != prepared.parent.cursor:
            raise MigrationError(
                f"stale parent cursor: expected {prepared.parent.cursor}, got {snapshot.journal_cursor}"
            )
        custody = self.custody.read_lease(prepared.parent.custody_lease.lease_id)
        if custody is None:
            raise MigrationIndeterminate("parent Custody lease disappeared during reread")
        if (
            custody.occurrence_key.occurrence_digest
            != prepared.parent.occurrence.occurrence_digest
            or custody.run_authority_grant_id != prepared.parent.source_request.grant_id
            or custody.coordinator_fence_token != prepared.parent.occurrence.fence_token
            or custody.wbc_attempt_reference != prepared.parent.wbc.attempt_id
        ):
            raise MigrationConflict("parent Custody reread is divergent")
        wbc = self.wbc.read_reservation(
            prepared.parent.wbc.attempt_id,
            prepared.parent.wbc.glek,
        )
        if wbc is None:
            raise MigrationIndeterminate("parent WBC reservation disappeared during reread")
        if wbc.glek != prepared.parent.wbc.glek or wbc.attempt_id != prepared.parent.wbc.attempt_id:
            raise MigrationConflict("parent WBC reread is divergent")
        return ParentEvidence(
            occurrence=prepared.parent.occurrence,
            authority=snapshot,
            source_request=prepared.parent.source_request,
            custody_lease=custody,
            wbc=wbc,
        )

    def _write_artifacts(
        self,
        prepared: PreparedMigration,
        parent_commit: ParentCommitReceipt,
        authority: ChildAuthority,
        wbc: WbcReservation,
        custody: CustodyLease,
    ) -> tuple[HandoffArtifact, ...]:
        if self.artifacts is None:
            return ()
        common = {
            "schema": CHILD_MIGRATION_SCHEMA,
            "migration_idempotency_key": prepared.migration_idempotency_key,
            "parent_occurrence": prepared.parent.occurrence.to_dict(),
            "child": prepared.child.to_dict(),
            "selector": prepared.selector.to_dict(),
            "parent_commit": {
                "parent_cursor": parent_commit.parent_cursor,
                "quarantine": parent_commit.quarantine.to_dict(),
            },
            "child_authority": authority.to_dict(),
            "wbc": {
                "attempt_id": wbc.attempt_id,
                "glek": wbc.glek,
                "source": wbc.source,
            },
            "custody": custody.to_dict(),
        }
        return tuple(
            self.artifacts.write(
                migration_idempotency_key=prepared.migration_idempotency_key,
                kind=kind,
                payload={**common, "kind": kind},
            )
            for kind in ("parent-quarantine", "child-receipt", "lineage")
        )

    def commit(self, prepared: PreparedMigration) -> MigrationReceipt:
        """Commit the prepared migration, safely replayable after crashes."""
        self._assert_prepared_integrity(prepared)
        existing = self.run_authority.read_parent_commit(prepared.migration_idempotency_key)
        if existing is not None:
            parent_commit = existing
        else:
            parent = self._reread_parent(prepared)
            expected = CASExpectation(
                run_id=parent.occurrence.run_id,
                expected_revision=parent.occurrence.run_revision,
                expected_cursor=parent.cursor,
            )
            try:
                parent_commit = self.run_authority.commit_parent(
                    expected=expected,
                    migration_idempotency_key=prepared.migration_idempotency_key,
                    quarantine=prepared.quarantine,
                )
            except MigrationError:
                raise
            except Exception as exc:
                raise MigrationIndeterminate("Run Authority parent CAS outcome is unknown") from exc
            if parent_commit.parent_cursor <= parent.cursor:
                raise MigrationIndeterminate("Run Authority returned a non-advanced parent cursor")
            self._step("parent_quarantined")
        self._validate_parent_commit(prepared, parent_commit)

        authority = self.run_authority.read_child(prepared.migration_idempotency_key)
        if authority is None:
            try:
                authority = self.run_authority.allocate_child(
                    identity=prepared.child,
                    parent=prepared.parent,
                    migration_idempotency_key=prepared.migration_idempotency_key,
                )
            except MigrationError:
                raise
            except Exception as exc:
                raise MigrationIndeterminate("child Run Authority allocation outcome is unknown") from exc
            self._validate_child_authority(prepared, authority)
            self._step("child_authority_allocated")
        else:
            self._validate_child_authority(prepared, authority)

        wbc = self.wbc.read_reservation(prepared.child.wbc_attempt_id, prepared.child.glek)
        if wbc is None:
            try:
                wbc = self.wbc.reserve_child(
                    attempt_id=prepared.child.wbc_attempt_id,
                    effect_identity=prepared.effect_identity,
                    migration_idempotency_key=prepared.migration_idempotency_key,
                )
            except MigrationError:
                raise
            except Exception as exc:
                raise MigrationIndeterminate("WBC reservation outcome is unknown") from exc
            self._step("wbc_reserved")
        if wbc.attempt_id != prepared.child.wbc_attempt_id or wbc.glek != prepared.child.glek:
            raise MigrationConflict("WBC owner returned a divergent reservation")

        # A child is a new occurrence: it keeps the stable F01 target context
        # but receives a fresh attempt/fence/WBC identity from the canonical
        # owners.  The parent digest remains in the lineage receipt and the
        # parent quarantine prevents the old occurrence from being reused.
        child_target = CustodyTargetKey(
            environment=prepared.parent.occurrence.target.environment,
            session=prepared.parent.occurrence.target.session,
            chain=prepared.parent.occurrence.target.chain,
            plan_revision=prepared.child.child_revision,
            phase=prepared.parent.occurrence.target.phase,
            task=prepared.parent.occurrence.target.task,
            attempt=f"child:{prepared.child.subject_attempt_id}",
            normalized_failure_kind=prepared.parent.occurrence.target.normalized_failure_kind,
            blocker_or_phase_result_hash=prepared.parent.occurrence.target.blocker_or_phase_result_hash,
            fence=str(authority.fence.token),
            chain_identity=prepared.parent.occurrence.target.chain_identity,
        )
        child_occurrence = RepairOccurrenceKey(
            target=child_target,
            run_id=authority.fence.run_id,
            run_revision=authority.fence.run_revision,
            coordinator_attempt_id=authority.fence.coordinator_attempt_id,
            fence_token=authority.fence.token,
            wbc_attempt_reference=wbc.attempt_id,
        )
        lease_id = f"lease:{prepared.child.migration_idempotency_key}"
        custody = self.custody.read_lease(lease_id)
        if custody is None:
            try:
                custody = self.custody.acquire_child(
                    lease_id=lease_id,
                    occurrence=child_occurrence,
                    authority=authority,
                    wbc=wbc,
                    idempotency_key=prepared.migration_idempotency_key,
                )
            except MigrationError:
                raise
            except Exception as exc:
                raise MigrationIndeterminate("Custody child lease outcome is unknown") from exc
            self._step("custody_acquired")
        if custody.occurrence_key.occurrence_digest != child_occurrence.occurrence_digest:
            raise MigrationConflict("child custody lease is bound to a divergent child occurrence")
        if custody.wbc_attempt_reference != wbc.attempt_id:
            raise MigrationConflict("child custody lease and WBC attempt differ")
        if custody.run_authority_grant_id != authority.grant.grant_id:
            raise MigrationConflict("child custody lease and RA grant differ")

        artifacts = self._write_artifacts(prepared, parent_commit, authority, wbc, custody)
        self._step("artifacts_written")
        return MigrationReceipt(
            migration_idempotency_key=prepared.migration_idempotency_key,
            status=MigrationStatus.COMMITTED,
            child=prepared.child,
            parent_commit=parent_commit,
            authority=authority,
            wbc=wbc,
            custody=custody,
            artifacts=artifacts,
        )

    def recover(self, prepared: PreparedMigration) -> MigrationReceipt:
        """Resume a partially applied migration without re-running providers."""
        return self.commit(prepared)


__all__ = [
    "CHILD_MIGRATION_SCHEMA",
    "ChildAuthority",
    "ChildIdentity",
    "ChildSelector",
    "CustodyOwner",
    "FilesystemHandoffArtifactWriter",
    "HandoffArtifact",
    "HandoffArtifactWriter",
    "MigrationConflict",
    "MigrationCoordinator",
    "MigrationError",
    "MigrationIndeterminate",
    "MigrationReceipt",
    "MigrationStatus",
    "OwnerUnavailable",
    "ParentAuthoritySnapshot",
    "ParentCommitReceipt",
    "ParentEvidence",
    "PreparedMigration",
    "ProviderEffectForbidden",
    "RunAuthorityOwner",
    "SameOccurrenceQuarantined",
    "SelectorDrift",
    "WbcOwner",
    "WbcReservation",
]
