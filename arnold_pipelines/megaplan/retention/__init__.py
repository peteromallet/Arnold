"""Retention and privacy projection readers for M9 rebuildable projections.

This module provides typed, non-authoritative readers for retention,
privacy, and migration health dimensions that consumers depend on.
Every reader:

* Produces a projection — never bearer authority for lifecycle decisions.
* Requires stored payload readability where applicable; surfaces missing
  keys, holds, or interrupted migrations as typed ``Indeterminate``.
* Returns fail-closed: absent or corrupted evidence produces
  ``Indeterminate``, not an optimistic default.
* Carries source-cursor metadata for freshness evaluation.

Covered dimensions
------------------
* **expiry** — retention expiry windows and TTL status.
* **legal_hold** — litigation/audit hold status.
* **tenant_access** — tenant-scoped access enforcement.
* **encrypted_ref** — encrypted reference key presence and integrity.
* **key_version_audit** — key rotation and version audit trails.
* **tombstone** — deletion/finalization tombstone records.
* **migration_health** — migration completeness, interruption, and gap evidence.

Design rules
------------
* ``Indeterminate`` is a typed result, not an error — it means "cannot
  determine from available stored evidence".
* Every reader requires evidence of the stored payload it reads.
  If the payload is unreadable, missing, or encrypted with an unknown
  key, the result is ``Indeterminate`` with explicit diagnostics.
* ``LegalHold`` and ``ExpiryStatus`` are dimensional readers, not
  policy enforcers — they tell you what the stored records say, not
  what to do about it.
* Migration health projections surface interrupted or partial
  migrations as ``Indeterminate`` with typed diagnostics.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, FrozenSet, Mapping, Optional, Sequence, Tuple, TypeAlias

from arnold_pipelines.megaplan.source_cursor_contract import (
    DimensionCursor,
    SourceCursorDimension,
    SourceCursorVector,
)


# ── Indeterminate / typed result status ────────────────────────────────


class ReaderStatus(Enum):
    """Typed result status for retention/privacy readers.

    * ``PRESENT`` — stored evidence is readable and coherent.
    * ``INDETERMINATE`` — cannot determine from available stored evidence.
      This is not an error; it means the stored payload is unreadable,
      missing, encrypted with an unknown key, or structurally damaged.
    * ``ABSENT`` — the dimension does not apply (no record exists and
      no record is expected).
    * ``DAMAGED`` — stored evidence exists but is corrupted, truncated,
      or structurally incoherent.
    """

    PRESENT = "present"
    INDETERMINATE = "indeterminate"
    ABSENT = "absent"
    DAMAGED = "damaged"

    def to_cursor_state(self) -> str:
        mapping: Dict[ReaderStatus, str] = {
            ReaderStatus.PRESENT: "fresh",
            ReaderStatus.INDETERMINATE: "unknown",
            ReaderStatus.ABSENT: "unknown",
            ReaderStatus.DAMAGED: "incoherent",
        }
        return mapping[self]

    @property
    def is_readable(self) -> bool:
        """True when stored evidence is present and readable."""
        return self == ReaderStatus.PRESENT


# ── Shared: Indeterminate diagnostics ──────────────────────────────────


@dataclass(frozen=True)
class IndeterminateDetail:
    """Typed diagnostic for an indeterminate result.

    Carries enough context for consumers to understand *why* a read
    returned indeterminate, without fabricating a default.
    """

    reason: str
    """Why the result is indeterminate (e.g. 'missing_encryption_key')."""

    dimension: str = ""
    """Which dimension was being read."""

    missing_keys: Tuple[str, ...] = ()
    """Encryption or reference keys that were missing."""

    interrupted_migration: Optional[str] = None
    """Migration ID if an interrupted migration caused the indeterminate."""

    detail: str = ""
    """Additional human-readable detail."""

    evidence_id: str = field(init=False)
    """Content-addressed diagnostic identifier."""

    def __post_init__(self) -> None:
        raw = (
            f"{self.dimension}\\x00{self.reason}\\x00"
            f"{','.join(sorted(self.missing_keys))}\\x00"
            f"{self.interrupted_migration or ''}"
        )
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        object.__setattr__(self, "evidence_id", f"indet:sha256:{digest}")

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "reason": self.reason,
            "dimension": self.dimension,
            "evidence_id": self.evidence_id,
        }
        if self.missing_keys:
            result["missing_keys"] = list(self.missing_keys)
        if self.interrupted_migration:
            result["interrupted_migration"] = self.interrupted_migration
        if self.detail:
            result["detail"] = self.detail
        return result


# ── Expiry projection ──────────────────────────────────────────────────


@dataclass(frozen=True)
class ExpiryProjection:
    """Projection of retention expiry status from stored records.

    Reads expiry windows and TTL metadata from stored payloads.
    Does NOT authorize deletion — it only reports what stored
    evidence says about expiry.
    """

    status: ReaderStatus
    """Whether expiry data is readable."""

    expires_at_epoch_ms: Optional[float] = None
    """When the stored record says it expires (None if unknown)."""

    ttl_ms: Optional[int] = None
    """The TTL configured for this record class."""

    is_expired: bool = False
    """Whether expiry timestamp has passed according to stored records."""

    grace_period_ms: int = 0
    """Grace period after expiry before deletion is considered."""

    diagnostics: Tuple[IndeterminateDetail, ...] = ()
    """Indeterminate diagnostics if status is not PRESENT."""

    source_cursor_digest: str = ""
    """Digest of the source cursor at read time."""

    observed_at_epoch_ms: float = 0.0

    _non_authoritative: bool = field(default=True, init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_non_authoritative", True)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "expires_at_epoch_ms": self.expires_at_epoch_ms,
            "ttl_ms": self.ttl_ms,
            "is_expired": self.is_expired,
            "grace_period_ms": self.grace_period_ms,
            "diagnostics": [d.to_dict() for d in self.diagnostics],
            "source_cursor_digest": self.source_cursor_digest,
            "observed_at_epoch_ms": self.observed_at_epoch_ms,
            "_non_authoritative": self._non_authoritative,
        }

    @classmethod
    def present(
        cls,
        *,
        expires_at_epoch_ms: Optional[float] = None,
        ttl_ms: Optional[int] = None,
        grace_period_ms: int = 0,
        source_cursor_digest: str = "",
        observed_at_epoch_ms: float = 0.0,
    ) -> "ExpiryProjection":
        now = time.time() * 1000
        is_expired = False
        if expires_at_epoch_ms is not None and expires_at_epoch_ms > 0:
            is_expired = now > expires_at_epoch_ms
        return cls(
            status=ReaderStatus.PRESENT,
            expires_at_epoch_ms=expires_at_epoch_ms,
            ttl_ms=ttl_ms,
            is_expired=is_expired,
            grace_period_ms=grace_period_ms,
            source_cursor_digest=source_cursor_digest,
            observed_at_epoch_ms=observed_at_epoch_ms,
        )

    @classmethod
    def indeterminate(
        cls,
        *,
        reason: str = "",
        missing_keys: Sequence[str] = (),
        detail: str = "",
        observed_at_epoch_ms: float = 0.0,
    ) -> "ExpiryProjection":
        diag = IndeterminateDetail(
            reason=reason or "expiry_data_unreadable",
            dimension="expiry",
            missing_keys=tuple(missing_keys),
            detail=detail,
        )
        return cls(
            status=ReaderStatus.INDETERMINATE,
            diagnostics=(diag,),
            observed_at_epoch_ms=observed_at_epoch_ms,
        )

    @classmethod
    def absent(cls, *, observed_at_epoch_ms: float = 0.0) -> "ExpiryProjection":
        return cls(
            status=ReaderStatus.ABSENT,
            observed_at_epoch_ms=observed_at_epoch_ms,
        )


# ── Legal hold projection ──────────────────────────────────────────────


@dataclass(frozen=True)
class LegalHoldProjection:
    """Projection of legal/litigation hold status from stored records.

    Reads hold indicators from stored payloads.  Does NOT authorize
    or enforce holds — only reports what stored evidence says.
    """

    status: ReaderStatus
    """Whether hold data is readable."""

    holds_active: Tuple[str, ...] = ()
    """Active legal hold identifiers."""

    holds_pending: Tuple[str, ...] = ()
    """Pending (not yet active) hold identifiers."""

    holds_expired: Tuple[str, ...] = ()
    """Expired hold identifiers (kept for audit trail)."""

    diagnostics: Tuple[IndeterminateDetail, ...] = ()
    """Indeterminate diagnostics if status is not PRESENT."""

    source_cursor_digest: str = ""

    observed_at_epoch_ms: float = 0.0

    _non_authoritative: bool = field(default=True, init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_non_authoritative", True)

    @property
    def any_active(self) -> bool:
        return len(self.holds_active) > 0

    @property
    def has_holds(self) -> bool:
        return self.any_active or len(self.holds_pending) > 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "holds_active": list(self.holds_active),
            "holds_pending": list(self.holds_pending),
            "holds_expired": list(self.holds_expired),
            "any_active": self.any_active,
            "has_holds": self.has_holds,
            "diagnostics": [d.to_dict() for d in self.diagnostics],
            "source_cursor_digest": self.source_cursor_digest,
            "observed_at_epoch_ms": self.observed_at_epoch_ms,
            "_non_authoritative": self._non_authoritative,
        }

    @classmethod
    def present(
        cls,
        *,
        holds_active: Sequence[str] = (),
        holds_pending: Sequence[str] = (),
        holds_expired: Sequence[str] = (),
        source_cursor_digest: str = "",
        observed_at_epoch_ms: float = 0.0,
    ) -> "LegalHoldProjection":
        return cls(
            status=ReaderStatus.PRESENT,
            holds_active=tuple(holds_active),
            holds_pending=tuple(holds_pending),
            holds_expired=tuple(holds_expired),
            source_cursor_digest=source_cursor_digest,
            observed_at_epoch_ms=observed_at_epoch_ms,
        )

    @classmethod
    def indeterminate(
        cls,
        *,
        reason: str = "",
        missing_keys: Sequence[str] = (),
        detail: str = "",
        observed_at_epoch_ms: float = 0.0,
    ) -> "LegalHoldProjection":
        diag = IndeterminateDetail(
            reason=reason or "hold_data_unreadable",
            dimension="legal_hold",
            missing_keys=tuple(missing_keys),
            detail=detail,
        )
        return cls(
            status=ReaderStatus.INDETERMINATE,
            diagnostics=(diag,),
            observed_at_epoch_ms=observed_at_epoch_ms,
        )

    @classmethod
    def absent(cls, *, observed_at_epoch_ms: float = 0.0) -> "LegalHoldProjection":
        return cls(
            status=ReaderStatus.ABSENT,
            observed_at_epoch_ms=observed_at_epoch_ms,
        )


# ── Tenant/access enforcement projection ───────────────────────────────


@dataclass(frozen=True)
class TenantAccessProjection:
    """Projection of tenant-scoped access enforcement from stored records.

    Reads tenant access metadata from stored payloads.  Reports which
    tenants have access, which are denied, and whether access metadata
    is readable.  Does NOT enforce access — only projects stored state.
    """

    status: ReaderStatus
    """Whether access metadata is readable."""

    tenant_id: str = ""
    """The tenant scope this projection covers."""

    access_granted: bool = False
    """Whether the stored record grants access to this tenant."""

    access_level: str = ""
    """Access level (read, read_write, admin, etc.)."""

    denied_reason: str = ""
    """Reason for denial if access_granted is False."""

    diagnostics: Tuple[IndeterminateDetail, ...] = ()

    source_cursor_digest: str = ""

    observed_at_epoch_ms: float = 0.0

    _non_authoritative: bool = field(default=True, init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_non_authoritative", True)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "tenant_id": self.tenant_id,
            "access_granted": self.access_granted,
            "access_level": self.access_level,
            "denied_reason": self.denied_reason,
            "diagnostics": [d.to_dict() for d in self.diagnostics],
            "source_cursor_digest": self.source_cursor_digest,
            "observed_at_epoch_ms": self.observed_at_epoch_ms,
            "_non_authoritative": self._non_authoritative,
        }

    @classmethod
    def present(
        cls,
        *,
        tenant_id: str = "",
        access_granted: bool = False,
        access_level: str = "",
        denied_reason: str = "",
        source_cursor_digest: str = "",
        observed_at_epoch_ms: float = 0.0,
    ) -> "TenantAccessProjection":
        return cls(
            status=ReaderStatus.PRESENT,
            tenant_id=tenant_id,
            access_granted=access_granted,
            access_level=access_level,
            denied_reason=denied_reason,
            source_cursor_digest=source_cursor_digest,
            observed_at_epoch_ms=observed_at_epoch_ms,
        )

    @classmethod
    def indeterminate(
        cls,
        *,
        tenant_id: str = "",
        reason: str = "",
        missing_keys: Sequence[str] = (),
        detail: str = "",
        observed_at_epoch_ms: float = 0.0,
    ) -> "TenantAccessProjection":
        diag = IndeterminateDetail(
            reason=reason or "access_metadata_unreadable",
            dimension="tenant_access",
            missing_keys=tuple(missing_keys),
            detail=detail,
        )
        return cls(
            status=ReaderStatus.INDETERMINATE,
            tenant_id=tenant_id,
            diagnostics=(diag,),
            observed_at_epoch_ms=observed_at_epoch_ms,
        )


# ── Encrypted reference projection ─────────────────────────────────────


@dataclass(frozen=True)
class EncryptedRefProjection:
    """Projection of encrypted reference key presence and readability.

    Checks whether the stored payload's encryption reference is
    readable given available keys.  Returns INDETERMINATE when
    the reference is encrypted with an unknown or missing key.
    """

    status: ReaderStatus
    """Whether the encrypted reference is readable."""

    ref_id: str = ""
    """The reference identifier (content-addressed)."""

    key_id: str = ""
    """The key identifier used for this reference."""

    key_version: str = ""
    """The key version."""

    is_readable: bool = False
    """Whether the reference payload is readable with available keys."""

    key_available: bool = False
    """Whether the decryption key is available."""

    diagnostics: Tuple[IndeterminateDetail, ...] = ()

    source_cursor_digest: str = ""

    observed_at_epoch_ms: float = 0.0

    _non_authoritative: bool = field(default=True, init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_non_authoritative", True)
        # is_readable should be consistent with status
        if self.status == ReaderStatus.PRESENT:
            object.__setattr__(self, "is_readable", True)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "ref_id": self.ref_id,
            "key_id": self.key_id,
            "key_version": self.key_version,
            "is_readable": self.is_readable,
            "key_available": self.key_available,
            "diagnostics": [d.to_dict() for d in self.diagnostics],
            "source_cursor_digest": self.source_cursor_digest,
            "observed_at_epoch_ms": self.observed_at_epoch_ms,
            "_non_authoritative": self._non_authoritative,
        }

    @classmethod
    def present(
        cls,
        *,
        ref_id: str = "",
        key_id: str = "",
        key_version: str = "",
        source_cursor_digest: str = "",
        observed_at_epoch_ms: float = 0.0,
    ) -> "EncryptedRefProjection":
        return cls(
            status=ReaderStatus.PRESENT,
            ref_id=ref_id,
            key_id=key_id,
            key_version=key_version,
            key_available=True,
            source_cursor_digest=source_cursor_digest,
            observed_at_epoch_ms=observed_at_epoch_ms,
        )

    @classmethod
    def indeterminate(
        cls,
        *,
        ref_id: str = "",
        reason: str = "",
        missing_keys: Sequence[str] = (),
        detail: str = "",
        observed_at_epoch_ms: float = 0.0,
    ) -> "EncryptedRefProjection":
        diag = IndeterminateDetail(
            reason=reason or "encrypted_ref_unreadable",
            dimension="encrypted_ref",
            missing_keys=tuple(missing_keys),
            detail=detail,
        )
        return cls(
            status=ReaderStatus.INDETERMINATE,
            ref_id=ref_id,
            diagnostics=(diag,),
            observed_at_epoch_ms=observed_at_epoch_ms,
        )

    @classmethod
    def damaged(
        cls,
        *,
        ref_id: str = "",
        reason: str = "",
        detail: str = "",
        observed_at_epoch_ms: float = 0.0,
    ) -> "EncryptedRefProjection":
        diag = IndeterminateDetail(
            reason=reason or "encrypted_ref_corrupted",
            dimension="encrypted_ref",
            detail=detail,
        )
        return cls(
            status=ReaderStatus.DAMAGED,
            ref_id=ref_id,
            diagnostics=(diag,),
            observed_at_epoch_ms=observed_at_epoch_ms,
        )


# ── Key/version audit projection ───────────────────────────────────────


@dataclass(frozen=True)
class KeyVersionAuditProjection:
    """Projection of key rotation and version audit trail from stored records.

    Reads key version history, rotation timestamps, and integrity
    evidence.  Surfaces missing keys or gaps in the rotation log
    as INDETERMINATE with diagnostics.
    """

    status: ReaderStatus
    """Whether the key version audit trail is readable."""

    current_key_id: str = ""
    """The current active key identifier."""

    current_key_version: str = ""
    """The current key version."""

    rotated_at_epoch_ms: float = 0.0
    """When the last rotation occurred."""

    previous_versions: Tuple[str, ...] = ()
    """Previous key versions still in the audit trail."""

    rotation_count: int = 0
    """Total number of rotations recorded."""

    missing_versions: Tuple[str, ...] = ()
    """Key versions referenced but missing from the audit trail."""

    diagnostics: Tuple[IndeterminateDetail, ...] = ()

    source_cursor_digest: str = ""

    observed_at_epoch_ms: float = 0.0

    _non_authoritative: bool = field(default=True, init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_non_authoritative", True)

    @property
    def has_missing_versions(self) -> bool:
        return len(self.missing_versions) > 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "current_key_id": self.current_key_id,
            "current_key_version": self.current_key_version,
            "rotated_at_epoch_ms": self.rotated_at_epoch_ms,
            "previous_versions": list(self.previous_versions),
            "rotation_count": self.rotation_count,
            "missing_versions": list(self.missing_versions),
            "has_missing_versions": self.has_missing_versions,
            "diagnostics": [d.to_dict() for d in self.diagnostics],
            "source_cursor_digest": self.source_cursor_digest,
            "observed_at_epoch_ms": self.observed_at_epoch_ms,
            "_non_authoritative": self._non_authoritative,
        }

    @classmethod
    def present(
        cls,
        *,
        current_key_id: str = "",
        current_key_version: str = "",
        rotated_at_epoch_ms: float = 0.0,
        previous_versions: Sequence[str] = (),
        rotation_count: int = 0,
        missing_versions: Sequence[str] = (),
        source_cursor_digest: str = "",
        observed_at_epoch_ms: float = 0.0,
    ) -> "KeyVersionAuditProjection":
        return cls(
            status=ReaderStatus.PRESENT,
            current_key_id=current_key_id,
            current_key_version=current_key_version,
            rotated_at_epoch_ms=rotated_at_epoch_ms,
            previous_versions=tuple(previous_versions),
            rotation_count=rotation_count,
            missing_versions=tuple(missing_versions),
            source_cursor_digest=source_cursor_digest,
            observed_at_epoch_ms=observed_at_epoch_ms,
        )

    @classmethod
    def indeterminate(
        cls,
        *,
        reason: str = "",
        missing_keys: Sequence[str] = (),
        missing_versions: Sequence[str] = (),
        detail: str = "",
        observed_at_epoch_ms: float = 0.0,
    ) -> "KeyVersionAuditProjection":
        diag = IndeterminateDetail(
            reason=reason or "key_audit_unreadable",
            dimension="key_version_audit",
            missing_keys=tuple(missing_keys),
            detail=detail,
        )
        return cls(
            status=ReaderStatus.INDETERMINATE,
            missing_versions=tuple(missing_versions),
            diagnostics=(diag,),
            observed_at_epoch_ms=observed_at_epoch_ms,
        )


# ── Tombstone projection ───────────────────────────────────────────────


@dataclass(frozen=True)
class TombstoneProjection:
    """Projection of deletion/finalization tombstone records.

    Reads tombstone markers from stored records.  A tombstone indicates
    that a record has been finalized or deleted, leaving only audit
    metadata.  Reports whether the tombstone is readable and coherent.
    """

    status: ReaderStatus
    """Whether the tombstone record is readable."""

    tombstone_id: str = ""
    """Content-addressed tombstone identifier."""

    deleted_at_epoch_ms: Optional[float] = None
    """When the record was tombstoned."""

    deletion_reason: str = ""
    """Reason for tombstone (e.g. 'expired', 'policy', 'user_request')."""

    audit_trail_digest: str = ""
    """Digest of the audit trail that led to this tombstone."""

    diagnostics: Tuple[IndeterminateDetail, ...] = ()

    source_cursor_digest: str = ""

    observed_at_epoch_ms: float = 0.0

    _non_authoritative: bool = field(default=True, init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_non_authoritative", True)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "tombstone_id": self.tombstone_id,
            "deleted_at_epoch_ms": self.deleted_at_epoch_ms,
            "deletion_reason": self.deletion_reason,
            "audit_trail_digest": self.audit_trail_digest,
            "diagnostics": [d.to_dict() for d in self.diagnostics],
            "source_cursor_digest": self.source_cursor_digest,
            "observed_at_epoch_ms": self.observed_at_epoch_ms,
            "_non_authoritative": self._non_authoritative,
        }

    @classmethod
    def present(
        cls,
        *,
        tombstone_id: str = "",
        deleted_at_epoch_ms: Optional[float] = None,
        deletion_reason: str = "",
        audit_trail_digest: str = "",
        source_cursor_digest: str = "",
        observed_at_epoch_ms: float = 0.0,
    ) -> "TombstoneProjection":
        return cls(
            status=ReaderStatus.PRESENT,
            tombstone_id=tombstone_id,
            deleted_at_epoch_ms=deleted_at_epoch_ms,
            deletion_reason=deletion_reason,
            audit_trail_digest=audit_trail_digest,
            source_cursor_digest=source_cursor_digest,
            observed_at_epoch_ms=observed_at_epoch_ms,
        )

    @classmethod
    def indeterminate(
        cls,
        *,
        reason: str = "",
        detail: str = "",
        observed_at_epoch_ms: float = 0.0,
    ) -> "TombstoneProjection":
        diag = IndeterminateDetail(
            reason=reason or "tombstone_unreadable",
            dimension="tombstone",
            detail=detail,
        )
        return cls(
            status=ReaderStatus.INDETERMINATE,
            diagnostics=(diag,),
            observed_at_epoch_ms=observed_at_epoch_ms,
        )

    @classmethod
    def absent(cls, *, observed_at_epoch_ms: float = 0.0) -> "TombstoneProjection":
        return cls(
            status=ReaderStatus.ABSENT,
            observed_at_epoch_ms=observed_at_epoch_ms,
        )


# ── Migration health projection ────────────────────────────────────────


@dataclass(frozen=True)
class MigrationHealthProjection:
    """Projection of migration completeness and health from stored records.

    Reads migration state markers, interruption evidence, and gap
    inventories.  Surfaces interrupted or partial migrations as
    INDETERMINATE with typed diagnostics including the migration
    identifier and affected dimensions.
    """

    status: ReaderStatus
    """Whether migration health evidence is readable."""

    migration_id: str = ""
    """Identifier of the migration being assessed."""

    is_complete: bool = False
    """Whether the migration has fully completed."""

    is_interrupted: bool = False
    """Whether the migration was interrupted mid-progress."""

    interrupted_at_epoch_ms: Optional[float] = None
    """When the migration was interrupted."""

    completed_at_epoch_ms: Optional[float] = None
    """When the migration completed."""

    affected_dimensions: Tuple[str, ...] = ()
    """Dimensions affected by an incomplete/interrupted migration."""

    gap_count: int = 0
    """Number of unbackfillable gaps detected."""

    diagnostics: Tuple[IndeterminateDetail, ...] = ()

    source_cursor_digest: str = ""

    observed_at_epoch_ms: float = 0.0

    _non_authoritative: bool = field(default=True, init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_non_authoritative", True)

    @property
    def is_healthy(self) -> bool:
        """True when migration is complete and no gaps are detected."""
        return self.is_complete and not self.is_interrupted and self.gap_count == 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "migration_id": self.migration_id,
            "is_complete": self.is_complete,
            "is_interrupted": self.is_interrupted,
            "interrupted_at_epoch_ms": self.interrupted_at_epoch_ms,
            "completed_at_epoch_ms": self.completed_at_epoch_ms,
            "affected_dimensions": list(self.affected_dimensions),
            "gap_count": self.gap_count,
            "is_healthy": self.is_healthy,
            "diagnostics": [d.to_dict() for d in self.diagnostics],
            "source_cursor_digest": self.source_cursor_digest,
            "observed_at_epoch_ms": self.observed_at_epoch_ms,
            "_non_authoritative": self._non_authoritative,
        }

    @classmethod
    def present(
        cls,
        *,
        migration_id: str = "",
        is_complete: bool = False,
        completed_at_epoch_ms: Optional[float] = None,
        affected_dimensions: Sequence[str] = (),
        gap_count: int = 0,
        source_cursor_digest: str = "",
        observed_at_epoch_ms: float = 0.0,
    ) -> "MigrationHealthProjection":
        return cls(
            status=ReaderStatus.PRESENT,
            migration_id=migration_id,
            is_complete=is_complete,
            completed_at_epoch_ms=completed_at_epoch_ms,
            affected_dimensions=tuple(affected_dimensions),
            gap_count=gap_count,
            source_cursor_digest=source_cursor_digest,
            observed_at_epoch_ms=observed_at_epoch_ms,
        )

    @classmethod
    def interrupted(
        cls,
        *,
        migration_id: str = "",
        interrupted_at_epoch_ms: Optional[float] = None,
        affected_dimensions: Sequence[str] = (),
        gap_count: int = 0,
        detail: str = "",
        source_cursor_digest: str = "",
        observed_at_epoch_ms: float = 0.0,
    ) -> "MigrationHealthProjection":
        diag = IndeterminateDetail(
            reason="migration_interrupted",
            dimension="migration_health",
            interrupted_migration=migration_id,
            detail=detail or f"migration {migration_id} was interrupted",
        )
        return cls(
            status=ReaderStatus.INDETERMINATE,
            migration_id=migration_id,
            is_interrupted=True,
            interrupted_at_epoch_ms=interrupted_at_epoch_ms,
            affected_dimensions=tuple(affected_dimensions),
            gap_count=gap_count,
            diagnostics=(diag,),
            source_cursor_digest=source_cursor_digest,
            observed_at_epoch_ms=observed_at_epoch_ms,
        )

    @classmethod
    def indeterminate(
        cls,
        *,
        migration_id: str = "",
        reason: str = "",
        detail: str = "",
        observed_at_epoch_ms: float = 0.0,
    ) -> "MigrationHealthProjection":
        diag = IndeterminateDetail(
            reason=reason or "migration_health_unreadable",
            dimension="migration_health",
            interrupted_migration=migration_id,
            detail=detail,
        )
        return cls(
            status=ReaderStatus.INDETERMINATE,
            migration_id=migration_id,
            diagnostics=(diag,),
            observed_at_epoch_ms=observed_at_epoch_ms,
        )


# ── Aggregated retention/privacy snapshot ──────────────────────────────


@dataclass(frozen=True)
class RetentionPrivacySnapshot:
    """Aggregated snapshot of all retention/privacy projection dimensions.

    Collects expiry, legal hold, tenant access, encrypted ref,
    key audit, tombstone, and migration health projections into
    a single non-authoritative snapshot.
    """

    expiry: ExpiryProjection
    legal_hold: LegalHoldProjection
    tenant_access: TenantAccessProjection
    encrypted_ref: EncryptedRefProjection
    key_version_audit: KeyVersionAuditProjection
    tombstone: TombstoneProjection
    migration_health: MigrationHealthProjection

    source_cursor: Optional[SourceCursorVector] = None

    observed_at_epoch_ms: float = 0.0

    _non_authoritative: bool = field(default=True, init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_non_authoritative", True)

    @property
    def any_indeterminate(self) -> bool:
        """True when any projection dimension is indeterminate."""
        return any(
            p.status == ReaderStatus.INDETERMINATE
            for p in (
                self.expiry,
                self.legal_hold,
                self.tenant_access,
                self.encrypted_ref,
                self.key_version_audit,
                self.tombstone,
                self.migration_health,
            )
        )

    @property
    def any_damaged(self) -> bool:
        """True when any projection dimension is damaged/corrupted."""
        return any(
            p.status == ReaderStatus.DAMAGED
            for p in (
                self.expiry,
                self.legal_hold,
                self.tenant_access,
                self.encrypted_ref,
                self.key_version_audit,
                self.tombstone,
                self.migration_health,
            )
        )

    @property
    def indeterminate_dimensions(self) -> Tuple[str, ...]:
        """Names of dimensions that are indeterminate."""
        dims = {
            "expiry": self.expiry,
            "legal_hold": self.legal_hold,
            "tenant_access": self.tenant_access,
            "encrypted_ref": self.encrypted_ref,
            "key_version_audit": self.key_version_audit,
            "tombstone": self.tombstone,
            "migration_health": self.migration_health,
        }
        return tuple(
            name for name, proj in dims.items()
            if proj.status == ReaderStatus.INDETERMINATE
        )

    @property
    def all_diagnostics(self) -> Tuple[IndeterminateDetail, ...]:
        """All indeterminate diagnostics across all dimensions."""
        diags: list[IndeterminateDetail] = []
        for proj in (
            self.expiry,
            self.legal_hold,
            self.tenant_access,
            self.encrypted_ref,
            self.key_version_audit,
            self.tombstone,
            self.migration_health,
        ):
            diags.extend(proj.diagnostics)
        return tuple(diags)

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "expiry": self.expiry.to_dict(),
            "legal_hold": self.legal_hold.to_dict(),
            "tenant_access": self.tenant_access.to_dict(),
            "encrypted_ref": self.encrypted_ref.to_dict(),
            "key_version_audit": self.key_version_audit.to_dict(),
            "tombstone": self.tombstone.to_dict(),
            "migration_health": self.migration_health.to_dict(),
            "any_indeterminate": self.any_indeterminate,
            "any_damaged": self.any_damaged,
            "indeterminate_dimensions": list(self.indeterminate_dimensions),
            "all_diagnostics": [d.to_dict() for d in self.all_diagnostics],
            "observed_at_epoch_ms": self.observed_at_epoch_ms,
            "_non_authoritative": self._non_authoritative,
        }
        if self.source_cursor is not None:
            result["source_cursor"] = self.source_cursor.to_dict()
        return result

    @classmethod
    def all_indeterminate(
        cls,
        *,
        reason: str = "retention_privacy_unreadable",
        missing_keys: Sequence[str] = (),
        observed_at_epoch_ms: float = 0.0,
    ) -> "RetentionPrivacySnapshot":
        """Create a snapshot where all dimensions are indeterminate."""
        ts = observed_at_epoch_ms or (time.time() * 1000)
        return cls(
            expiry=ExpiryProjection.indeterminate(
                reason=reason, missing_keys=missing_keys,
                observed_at_epoch_ms=ts,
            ),
            legal_hold=LegalHoldProjection.indeterminate(
                reason=reason, missing_keys=missing_keys,
                observed_at_epoch_ms=ts,
            ),
            tenant_access=TenantAccessProjection.indeterminate(
                reason=reason, missing_keys=missing_keys,
                observed_at_epoch_ms=ts,
            ),
            encrypted_ref=EncryptedRefProjection.indeterminate(
                reason=reason, missing_keys=missing_keys,
                observed_at_epoch_ms=ts,
            ),
            key_version_audit=KeyVersionAuditProjection.indeterminate(
                reason=reason, missing_keys=missing_keys,
                observed_at_epoch_ms=ts,
            ),
            tombstone=TombstoneProjection.indeterminate(
                reason=reason, observed_at_epoch_ms=ts,
            ),
            migration_health=MigrationHealthProjection.indeterminate(
                reason=reason, observed_at_epoch_ms=ts,
            ),
            observed_at_epoch_ms=ts,
        )


# ── Reader function type ────────────────────────────────────────────────

StoredPayloadReader: TypeAlias = Callable[
    [str, Optional[float]],
    Optional[Mapping[str, Any]],
]
"""A function that reads a stored payload by reference ID.

Returns the payload as a mapping, or None if unreadable/missing.
The second argument is an optional observation timestamp.
"""


# ── Payload readability check ──────────────────────────────────────────


def check_payload_readability(
    reader: StoredPayloadReader,
    ref_id: str,
    *,
    required_keys: Sequence[str] = (),
    observed_at_epoch_ms: Optional[float] = None,
) -> ReaderStatus:
    """Check whether a stored payload is readable.

    Args:
        reader: Function to read the stored payload.
        ref_id: Reference identifier for the payload.
        required_keys: Keys that must be present in the payload.
        observed_at_epoch_ms: Observation timestamp.

    Returns:
        PRESENT if the payload is readable and contains the required keys,
        INDETERMINATE if unreadable, ABSENT if no payload exists.
    """
    ts = observed_at_epoch_ms or (time.time() * 1000)

    if not ref_id:
        return ReaderStatus.ABSENT

    try:
        payload = reader(ref_id, ts)
    except Exception:
        return ReaderStatus.INDETERMINATE

    if payload is None:
        return ReaderStatus.ABSENT

    if not isinstance(payload, Mapping):
        return ReaderStatus.DAMAGED

    for key in required_keys:
        if key not in payload:
            return ReaderStatus.INDETERMINATE

    return ReaderStatus.PRESENT


# ── Cross-tenant gate ──────────────────────────────────────────────────


@dataclass(frozen=True)
class CrossTenantDenial:
    """Evidence of a cross-tenant access denial — negative gate only.

    This is NEVER bearer authority for any positive action.  It only
    records that a read was blocked because the requesting tenant does
    not match the stored record's tenant scope.
    """

    requesting_tenant: str
    """The tenant that attempted the read."""

    record_tenant: str
    """The tenant that owns the stored record."""

    record_ref: str = ""
    """Reference identifier of the blocked record."""

    denied_at_epoch_ms: float = 0.0

    evidence_id: str = field(init=False)
    """Content-addressed denial evidence for audit trails."""

    _non_authoritative: bool = field(default=True, init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_non_authoritative", True)
        raw = (
            f"cross_tenant_denial\\x00"
            f"{self.requesting_tenant}\\x00{self.record_tenant}\\x00"
            f"{self.record_ref}\\x00{self.denied_at_epoch_ms}"
        )
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        object.__setattr__(self, "evidence_id", f"xtd:sha256:{digest}")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "requesting_tenant": self.requesting_tenant,
            "record_tenant": self.record_tenant,
            "record_ref": self.record_ref,
            "denied_at_epoch_ms": self.denied_at_epoch_ms,
            "evidence_id": self.evidence_id,
            "_non_authoritative": self._non_authoritative,
        }


def cross_tenant_gate(
    *,
    requesting_tenant: str,
    record_tenant: str,
    record_ref: str = "",
    observed_at_epoch_ms: Optional[float] = None,
) -> Optional[CrossTenantDenial]:
    """Check for cross-tenant access and produce a denial if blocked.

    This is a **negative gate only**: it can block reads but cannot
    authorize any action.  A None return means the requesting tenant
    matches the record tenant — the gate is open for reading.

    Args:
        requesting_tenant: The tenant requesting access.
        record_tenant: The tenant that owns the stored record.
        record_ref: Reference identifier for audit trail.
        observed_at_epoch_ms: Observation timestamp.

    Returns:
        A ``CrossTenantDenial`` if access should be blocked (negative gate
        engaged), or ``None`` if the tenant matches (gate open for reading
        only — never a positive authorization).
    """
    ts = observed_at_epoch_ms or (time.time() * 1000)

    if not requesting_tenant or not record_tenant:
        # Cannot determine tenant scope — block (fail-closed)
        return CrossTenantDenial(
            requesting_tenant=requesting_tenant or "<unknown>",
            record_tenant=record_tenant or "<unknown>",
            record_ref=record_ref,
            denied_at_epoch_ms=ts,
        )

    if requesting_tenant != record_tenant:
        return CrossTenantDenial(
            requesting_tenant=requesting_tenant,
            record_tenant=record_tenant,
            record_ref=record_ref,
            denied_at_epoch_ms=ts,
        )

    # Tenant match — gate open for reading only, never positive authority
    return None


# ── History access classification ──────────────────────────────────────


class HistoryAccessState(Enum):
    """Typed classification of stored history accessibility.

    * ``READABLE`` — stored history is present, readable, and not blocked.
    * ``TOMBSTONED`` — a tombstone marker exists; the record was finalized
      or deleted, leaving only audit metadata.
    * ``EXPIRED`` — the retention expiry window has passed; the record may
      still be readable but is past its retention period.
    * ``UNAVAILABLE`` — the stored history cannot be read due to missing
      keys, encryption gaps, migration interruption, or payload damage.
    * ``BLOCKED_CROSS_TENANT`` — the read was blocked because the requesting
      tenant does not match the record tenant.
    """

    READABLE = "readable"
    TOMBSTONED = "tombstoned"
    EXPIRED = "expired"
    UNAVAILABLE = "unavailable"
    BLOCKED_CROSS_TENANT = "blocked_cross_tenant"


@dataclass(frozen=True)
class HistoryAccessClassification:
    """Typed verdict on whether stored history can be read.

    Distinguishes tombstoned, expired, unavailable, and cross-tenant-blocked
    states with exact evidence IDs.  This is a **negative gate only** — it
    can block reads but CANNOT authorize any positive action.

    An ``accessible`` property of True means the history is readable for
    the requesting tenant given available stored evidence.  It does NOT
    imply any grant, lease, or authority.
    """

    state: HistoryAccessState
    """The classified accessibility state."""

    evidence_ids: Tuple[str, ...] = ()
    """Exact evidence IDs supporting the classification."""

    detail: str = ""
    """Human-readable detail about the classification."""

    tombstone_evidence: Optional[TombstoneProjection] = None
    """Tombstone projection if state is TOMBSTONED."""

    expiry_evidence: Optional[ExpiryProjection] = None
    """Expiry projection if state is EXPIRED."""

    cross_tenant_denial: Optional[CrossTenantDenial] = None
    """Cross-tenant denial if state is BLOCKED_CROSS_TENANT."""

    observed_at_epoch_ms: float = 0.0

    _non_authoritative: bool = field(default=True, init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_non_authoritative", True)

    @property
    def accessible(self) -> bool:
        """True when history is readable for the requesting tenant.

        This is a non-authoritative projection — it never implies
        any positive grant, lease, or authority.
        """
        return self.state == HistoryAccessState.READABLE

    @property
    def is_negative_gate(self) -> bool:
        """True when this classification blocks a read (negative gate engaged)."""
        return self.state != HistoryAccessState.READABLE

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "state": self.state.value,
            "accessible": self.accessible,
            "is_negative_gate": self.is_negative_gate,
            "evidence_ids": list(self.evidence_ids),
            "detail": self.detail,
            "observed_at_epoch_ms": self.observed_at_epoch_ms,
            "_non_authoritative": self._non_authoritative,
        }
        if self.tombstone_evidence is not None:
            result["tombstone_evidence"] = self.tombstone_evidence.to_dict()
        if self.expiry_evidence is not None:
            result["expiry_evidence"] = self.expiry_evidence.to_dict()
        if self.cross_tenant_denial is not None:
            result["cross_tenant_denial"] = self.cross_tenant_denial.to_dict()
        return result


def classify_history_access(
    *,
    snapshot: RetentionPrivacySnapshot,
    requesting_tenant: str = "",
    observed_at_epoch_ms: Optional[float] = None,
) -> HistoryAccessClassification:
    """Classify whether stored history is accessible given retention/privacy evidence.

    Evaluates the snapshot in order of precedence:
    1. Cross-tenant block (highest priority — must not leak across tenants)
    2. Tombstone (record finalized/deleted)
    3. Expiry (retention window passed)
    4. Unavailable (indeterminate or damaged evidence)
    5. Readable (all gates pass)

    This is a **negative gate only**: it can block reads but CANNOT
    authorize any positive action.  The result carries exact evidence IDs
    for every blocking condition.

    Args:
        snapshot: Aggregated retention/privacy projections.
        requesting_tenant: The tenant requesting access (empty = no tenant check).
        observed_at_epoch_ms: Observation timestamp.

    Returns:
        A ``HistoryAccessClassification`` with the accessibility verdict
        and exact evidence IDs.
    """
    ts = observed_at_epoch_ms or (time.time() * 1000)
    evidence_ids: list[str] = []

    # 1. Cross-tenant check (highest priority)
    if requesting_tenant:
        record_tenant = snapshot.tenant_access.tenant_id
        if record_tenant and requesting_tenant != record_tenant:
            denial = CrossTenantDenial(
                requesting_tenant=requesting_tenant,
                record_tenant=record_tenant,
                denied_at_epoch_ms=ts,
            )
            evidence_ids.append(denial.evidence_id)
            return HistoryAccessClassification(
                state=HistoryAccessState.BLOCKED_CROSS_TENANT,
                evidence_ids=tuple(evidence_ids),
                detail=f"Cross-tenant read blocked: {requesting_tenant} != {record_tenant}",
                cross_tenant_denial=denial,
                observed_at_epoch_ms=ts,
            )

    # 2. Tombstone check
    if snapshot.tombstone.status == ReaderStatus.PRESENT:
        tombstone_id = snapshot.tombstone.tombstone_id
        if tombstone_id:
            evidence_ids.append(f"tombstone:sha256:{tombstone_id}")
        evidence_ids.append(
            hashlib.sha256(
                f"tombstone_block\\x00{snapshot.tombstone.deleted_at_epoch_ms or 0}\\x00{ts}".encode()
            ).hexdigest()
        )
        return HistoryAccessClassification(
            state=HistoryAccessState.TOMBSTONED,
            evidence_ids=tuple(evidence_ids),
            detail=(
                f"Record tombstoned: {snapshot.tombstone.deletion_reason or 'no_reason'}"
            ),
            tombstone_evidence=snapshot.tombstone,
            observed_at_epoch_ms=ts,
        )

    # 3. Expiry check
    if snapshot.expiry.status == ReaderStatus.PRESENT and snapshot.expiry.is_expired:
        expiry_eid = hashlib.sha256(
            f"expiry_block\\x00{snapshot.expiry.expires_at_epoch_ms or 0}\\x00"
            f"{snapshot.expiry.grace_period_ms}\\x00{ts}".encode()
        ).hexdigest()
        evidence_ids.append(f"expiry:sha256:{expiry_eid}")
        return HistoryAccessClassification(
            state=HistoryAccessState.EXPIRED,
            evidence_ids=tuple(evidence_ids),
            detail=(
                f"Record expired at {snapshot.expiry.expires_at_epoch_ms}"
                f" (grace: {snapshot.expiry.grace_period_ms}ms)"
            ),
            expiry_evidence=snapshot.expiry,
            observed_at_epoch_ms=ts,
        )

    # 4. Unavailable check (indeterminate or damaged dimensions)
    if snapshot.any_indeterminate or snapshot.any_damaged:
        for diag in snapshot.all_diagnostics:
            evidence_ids.append(diag.evidence_id)
        return HistoryAccessClassification(
            state=HistoryAccessState.UNAVAILABLE,
            evidence_ids=tuple(evidence_ids),
            detail=(
                f"History unavailable: indeterminate={snapshot.indeterminate_dimensions}"
            ),
            observed_at_epoch_ms=ts,
        )

    # 5. All gates pass — readable (but never positive authority)
    return HistoryAccessClassification(
        state=HistoryAccessState.READABLE,
        evidence_ids=(),
        detail="History is readable for the requesting tenant",
        observed_at_epoch_ms=ts,
    )


__all__ = [
    # ── Types ──
    "ReaderStatus",
    "IndeterminateDetail",
    "StoredPayloadReader",
    # ── Cross-tenant ──
    "CrossTenantDenial",
    "cross_tenant_gate",
    # ── History access ──
    "HistoryAccessState",
    "HistoryAccessClassification",
    "classify_history_access",
    # ── Projections ──
    "ExpiryProjection",
    "LegalHoldProjection",
    "TenantAccessProjection",
    "EncryptedRefProjection",
    "KeyVersionAuditProjection",
    "TombstoneProjection",
    "MigrationHealthProjection",
    # ── Aggregate ──
    "RetentionPrivacySnapshot",
    # ── Helpers ──
    "check_payload_readability",
]
