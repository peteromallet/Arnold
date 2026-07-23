"""Historical and mixed-version WBC compatibility adapters.

Extends the compatibility wrapper framework (:mod:`arnold_pipelines.megaplan.compatibility`)
with WBC-specific adapters for bridging historical, pre-M6A, and mixed-version
WBC schemas.  Every adapter is:

* **Non-authoritative** — carries ``_non_authoritative: True`` explicitly.
* **Source-versioned** — binds to an exact WBC attempt/version.
* **Gap-aware** — unbackfillable legacy gaps are represented as typed
  ``LegacyGap`` entries, not silently collapsed.
* **Expiry-scoped** — carries ``expires_at`` metadata; consumers must not
  read expired wrappers.
* **Deletion-gated** — requires zero-reader evidence before removal.

Design rules
------------
* Historical gaps are first-class: a ``LegacyGap`` is evidence of absence,
  not a default-to-fresh shortcut.
* Mixed-version bridges declare source and target WBC schema versions.
* Every adapter carries a ``WbcCompatAdapterStatus`` that maps to the
  source-cursor ``wbc`` dimension states.
* Deletion requires ``reader_count == 0`` and ``deletion_blocked_until``
  to have passed.  Adapters track reader counts explicitly.
* Compatibility adapters must not reintroduce raw evidence authority.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, FrozenSet, Mapping, Optional, Sequence, Tuple

from arnold_pipelines.megaplan.compatibility import (
    CompatibilityProjection,
    CompatibilityWrapperMeta,
    WrapperRegistry,
    WrapperStatus,
)
from arnold_pipelines.megaplan.source_cursor_contract import (
    DimensionCursor,
    SourceCursorDimension,
    SourceCursorVector,
)
from arnold_pipelines.megaplan.wbc_adapter import (
    WbcAdapter,
    WbcAdapterStatus,
    WbcAttemptRef,
    WbcBoundaryEvidence,
)


# ── WBC compatibility adapter status ───────────────────────────────────


class WbcCompatAdapterStatus(Enum):
    """Lifecycle status of a WBC compatibility adapter.

    * ``ACTIVE`` — adapter is in service, consumers may use it.
    * ``LEGACY_GAP`` — adapter exists but no source evidence is backfillable;
      explicit gap marker only.
    * ``DEPRECATED`` — adapter is scheduled for removal.
    * ``EXPIRED`` — adapter has passed its expiry; consumers must not use it.
    * ``DELETED`` — adapter removed (zero-reader evidence provided).
    """

    ACTIVE = "active"
    LEGACY_GAP = "legacy_gap"
    DEPRECATED = "deprecated"
    EXPIRED = "expired"
    DELETED = "deleted"

    def to_cursor_state(self) -> str:
        mapping: Dict[WbcCompatAdapterStatus, str] = {
            WbcCompatAdapterStatus.ACTIVE: "fresh",
            WbcCompatAdapterStatus.LEGACY_GAP: "unknown",
            WbcCompatAdapterStatus.DEPRECATED: "stale",
            WbcCompatAdapterStatus.EXPIRED: "stale",
            WbcCompatAdapterStatus.DELETED: "unknown",
        }
        return mapping[self]

    @property
    def is_consumable(self) -> bool:
        """True when a consumer may still read through this adapter."""
        return self in (WbcCompatAdapterStatus.ACTIVE, WbcCompatAdapterStatus.LEGACY_GAP)


# ── Legacy gap evidence ────────────────────────────────────────────────


@dataclass(frozen=True)
class LegacyGap:
    """Explicit evidence of a non-backfillable historical gap.

    A ``LegacyGap`` is evidence of absence — it carries enough metadata
    for consumers to understand *what* is missing and *why*, without
    fabricating a default or optimistic result.

    Legacy gaps are surfaced as ``INDETERMINATE`` source-cursor entries
    so downstream consumers cannot mistake them for complete evidence.
    """

    gap_id: str
    """Content-addressed identifier for this gap (sha256 over kind + reason + version_range)."""

    kind: str
    """What kind of evidence is missing (e.g. 'custody_boundary', 'delivery_receipt')."""

    reason: str
    """Why the gap is not backfillable (e.g. 'pre-WBC plan', 'migration_cutoff')."""

    version_range: str = ""
    """Schema version range the gap covers (e.g. 'pre-M6A', '2024Q1-2024Q3')."""

    observed_at_epoch_ms: float = 0.0
    """When the gap was identified."""

    evidence_ids: Tuple[str, ...] = ()
    """Evidence IDs of any related records that confirmed the gap."""

    _non_authoritative: bool = field(default=True, init=False)

    def __post_init__(self) -> None:
        if not self.gap_id:
            raw = (
                f"{self.kind}\\x00{self.reason}\\x00{self.version_range}\\x00"
                f"{self.observed_at_epoch_ms}"
            )
            digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
            object.__setattr__(self, "gap_id", f"gap:sha256:{digest}")
        object.__setattr__(self, "_non_authoritative", True)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gap_id": self.gap_id,
            "kind": self.kind,
            "reason": self.reason,
            "version_range": self.version_range,
            "observed_at_epoch_ms": self.observed_at_epoch_ms,
            "evidence_ids": list(self.evidence_ids),
            "_non_authoritative": self._non_authoritative,
        }

    def to_dimension_cursor(self) -> DimensionCursor:
        """Produce an INDETERMINATE wbc cursor from this gap."""
        from datetime import datetime, timezone

        observed_at = ""
        if self.observed_at_epoch_ms > 0:
            observed_at = datetime.fromtimestamp(
                self.observed_at_epoch_ms / 1000, tz=timezone.utc
            ).isoformat()
        return DimensionCursor.unknown(
            "wbc",
            observed_at=observed_at,
            detail=f"legacy_gap:{self.kind}: {self.reason}",
        )

    @classmethod
    def pre_wbc(cls, *, kind: str = "wbc_boundary", observed_at_epoch_ms: float = 0.0) -> "LegacyGap":
        """Create a gap for a pre-WBC plan that has no backfillable evidence."""
        return cls(
            gap_id="",
            kind=kind,
            reason="pre-WBC plan; no attempt ledger available",
            version_range="pre-M6A",
            observed_at_epoch_ms=observed_at_epoch_ms or (time.time() * 1000),
        )

    @classmethod
    def migration_cutoff(
        cls,
        *,
        kind: str = "wbc_boundary",
        cutoff_version: str = "",
        observed_at_epoch_ms: float = 0.0,
    ) -> "LegacyGap":
        """Create a gap for a migration cutoff boundary."""
        return cls(
            gap_id="",
            kind=kind,
            reason=f"migration cutoff at {cutoff_version or 'unknown'}",
            version_range=cutoff_version,
            observed_at_epoch_ms=observed_at_epoch_ms or (time.time() * 1000),
        )

    @classmethod
    def missing_receipt(
        cls,
        *,
        kind: str = "delivery_receipt",
        attempt_id: str = "",
        observed_at_epoch_ms: float = 0.0,
    ) -> "LegacyGap":
        """Create a gap for a missing receipt in an otherwise valid attempt."""
        return cls(
            gap_id="",
            kind=kind,
            reason=f"receipt missing for attempt {attempt_id or 'unknown'}",
            version_range="",
            observed_at_epoch_ms=observed_at_epoch_ms or (time.time() * 1000),
        )


# ── WBC compatibility adapter metadata ─────────────────────────────────


@dataclass(frozen=True)
class WbcCompatAdapterMeta:
    """Metadata for a single WBC compatibility adapter.

    Carries source/target schema versions, legacy gap inventory,
    expiry, and zero-reader deletion gates.
    """

    adapter_id: str
    """Unique content-addressed identifier."""

    schema_in: str
    """Source WBC schema version (e.g. 'pre-M6A', 'M6A', 'M9')."""

    schema_out: str
    """Target WBC schema version."""

    status: WbcCompatAdapterStatus = WbcCompatAdapterStatus.ACTIVE

    expires_at_epoch_ms: float = 0.0
    """Epoch ms after which the adapter must not be consumed."""

    deprecated_at_epoch_ms: float = 0.0
    """Epoch ms when the adapter was marked deprecated."""

    deletion_blocked_until_epoch_ms: float = 0.0
    """Epoch ms before which deletion is blocked."""

    deletion_requires_zero_readers: bool = True
    """True until explicit zero-reader evidence is provided."""

    reader_count: int = -1
    """Known reader count (-1 = unknown, must be 0 for deletion)."""

    legacy_gaps: Tuple[LegacyGap, ...] = ()
    """Explicit inventory of non-backfillable gaps this adapter covers."""

    source_cursor_digest: str = ""
    """Digest of the source-cursor vector at adapter creation time."""

    adapter_digest: str = field(init=False)

    _non_authoritative: bool = field(default=True, init=False)

    def __post_init__(self) -> None:
        raw = (
            f"{self.adapter_id}\\x00{self.schema_in}\\x00{self.schema_out}\\x00"
            f"{self.status.value}\\x00{self.expires_at_epoch_ms}\\x00"
            f"{self.reader_count}\\x00{len(self.legacy_gaps)}\\x00"
            f"{self.source_cursor_digest}"
        )
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        object.__setattr__(self, "adapter_digest", f"sha256:{digest}")
        object.__setattr__(self, "_non_authoritative", True)

    @property
    def is_expired(self) -> bool:
        if self.expires_at_epoch_ms <= 0:
            return False
        return time.time() * 1000 > self.expires_at_epoch_ms

    @property
    def can_delete(self) -> bool:
        if self.deletion_requires_zero_readers and self.reader_count != 0:
            return False
        now = time.time() * 1000
        if self.deletion_blocked_until_epoch_ms > now:
            return False
        return True

    @property
    def has_legacy_gaps(self) -> bool:
        return len(self.legacy_gaps) > 0

    @property
    def is_consumable(self) -> bool:
        """True when a consumer may still read through this adapter."""
        if self.status in (WbcCompatAdapterStatus.ACTIVE, WbcCompatAdapterStatus.LEGACY_GAP):
            return not self.is_expired
        return False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "adapter_id": self.adapter_id,
            "schema_in": self.schema_in,
            "schema_out": self.schema_out,
            "status": self.status.value,
            "cursor_state": self.status.to_cursor_state(),
            "expires_at_epoch_ms": self.expires_at_epoch_ms,
            "deprecated_at_epoch_ms": self.deprecated_at_epoch_ms,
            "deletion_blocked_until_epoch_ms": self.deletion_blocked_until_epoch_ms,
            "deletion_requires_zero_readers": self.deletion_requires_zero_readers,
            "reader_count": self.reader_count,
            "legacy_gaps": [g.to_dict() for g in self.legacy_gaps],
            "has_legacy_gaps": self.has_legacy_gaps,
            "source_cursor_digest": self.source_cursor_digest,
            "adapter_digest": self.adapter_digest,
            "is_expired": self.is_expired,
            "can_delete": self.can_delete,
            "is_consumable": self.is_consumable,
            "_non_authoritative": self._non_authoritative,
        }

    @classmethod
    def create(
        cls,
        adapter_id: str,
        schema_in: str,
        schema_out: str,
        *,
        expires_at_epoch_ms: float = 0.0,
        legacy_gaps: Sequence[LegacyGap] = (),
        source_cursor_digest: str = "",
        reader_count: int = -1,
    ) -> "WbcCompatAdapterMeta":
        return cls(
            adapter_id=adapter_id,
            schema_in=schema_in,
            schema_out=schema_out,
            status=WbcCompatAdapterStatus.ACTIVE,
            expires_at_epoch_ms=expires_at_epoch_ms,
            legacy_gaps=tuple(legacy_gaps),
            source_cursor_digest=source_cursor_digest,
            reader_count=reader_count,
        )

    @classmethod
    def legacy_gap_only(
        cls,
        adapter_id: str,
        schema_in: str,
        schema_out: str,
        *,
        legacy_gaps: Sequence[LegacyGap] = (),
        source_cursor_digest: str = "",
    ) -> "WbcCompatAdapterMeta":
        """Create an adapter whose only purpose is to surface legacy gaps."""
        return cls(
            adapter_id=adapter_id,
            schema_in=schema_in,
            schema_out=schema_out,
            status=WbcCompatAdapterStatus.LEGACY_GAP,
            legacy_gaps=tuple(legacy_gaps),
            source_cursor_digest=source_cursor_digest,
            reader_count=-1,
        )

    def with_reader_count(self, count: int) -> "WbcCompatAdapterMeta":
        return WbcCompatAdapterMeta(
            adapter_id=self.adapter_id,
            schema_in=self.schema_in,
            schema_out=self.schema_out,
            status=self.status,
            expires_at_epoch_ms=self.expires_at_epoch_ms,
            deprecated_at_epoch_ms=self.deprecated_at_epoch_ms,
            deletion_blocked_until_epoch_ms=self.deletion_blocked_until_epoch_ms,
            deletion_requires_zero_readers=self.deletion_requires_zero_readers,
            reader_count=count,
            legacy_gaps=self.legacy_gaps,
            source_cursor_digest=self.source_cursor_digest,
        )

    def mark_deprecated(self, *, blocked_until_epoch_ms: float = 0.0) -> "WbcCompatAdapterMeta":
        now = time.time() * 1000
        return WbcCompatAdapterMeta(
            adapter_id=self.adapter_id,
            schema_in=self.schema_in,
            schema_out=self.schema_out,
            status=WbcCompatAdapterStatus.DEPRECATED,
            expires_at_epoch_ms=self.expires_at_epoch_ms,
            deprecated_at_epoch_ms=now,
            deletion_blocked_until_epoch_ms=max(self.deletion_blocked_until_epoch_ms, blocked_until_epoch_ms),
            deletion_requires_zero_readers=self.deletion_requires_zero_readers,
            reader_count=self.reader_count,
            legacy_gaps=self.legacy_gaps,
            source_cursor_digest=self.source_cursor_digest,
        )

    def mark_expired(self) -> "WbcCompatAdapterMeta":
        return WbcCompatAdapterMeta(
            adapter_id=self.adapter_id,
            schema_in=self.schema_in,
            schema_out=self.schema_out,
            status=WbcCompatAdapterStatus.EXPIRED,
            expires_at_epoch_ms=self.expires_at_epoch_ms,
            deprecated_at_epoch_ms=self.deprecated_at_epoch_ms,
            deletion_blocked_until_epoch_ms=self.deletion_blocked_until_epoch_ms,
            deletion_requires_zero_readers=self.deletion_requires_zero_readers,
            reader_count=self.reader_count,
            legacy_gaps=self.legacy_gaps,
            source_cursor_digest=self.source_cursor_digest,
        )

    def mark_deleted(self) -> "WbcCompatAdapterMeta":
        if not self.can_delete:
            raise ValueError(
                f"cannot delete adapter {self.adapter_id}: "
                f"deletion not safe (reader_count={self.reader_count})"
            )
        return WbcCompatAdapterMeta(
            adapter_id=self.adapter_id,
            schema_in=self.schema_in,
            schema_out=self.schema_out,
            status=WbcCompatAdapterStatus.DELETED,
            expires_at_epoch_ms=self.expires_at_epoch_ms,
            deprecated_at_epoch_ms=self.deprecated_at_epoch_ms,
            deletion_blocked_until_epoch_ms=self.deletion_blocked_until_epoch_ms,
            deletion_requires_zero_readers=False,
            reader_count=0,
            legacy_gaps=self.legacy_gaps,
            source_cursor_digest=self.source_cursor_digest,
        )


# ── WBC compatibility result ───────────────────────────────────────────


@dataclass(frozen=True)
class WbcCompatResult:
    """Result of a WBC compatibility adapter query.

    Carries the adapted boundary evidence, any legacy gaps that affect
    this query, and explicit expiry/deletion metadata.
    """

    meta: WbcCompatAdapterMeta
    """The adapter that produced this result."""

    evidence: WbcBoundaryEvidence
    """The WBC boundary evidence (may be INDETERMINATE for gaps)."""

    gaps_applicable: Tuple[LegacyGap, ...] = ()
    """Legacy gaps that apply to this specific query."""

    source_cursor: Optional[SourceCursorVector] = None
    """Source-cursor vector at query time."""

    _non_authoritative: bool = field(default=True, init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_non_authoritative", True)

    @property
    def is_consumable(self) -> bool:
        """True when the result is safe to consume (adapter active + not expired)."""
        return self.meta.is_consumable

    @property
    def effective_status(self) -> WbcAdapterStatus:
        """The effective WBC adapter status considering gaps."""
        if self.gaps_applicable:
            # Gaps that affect this query degrade the result
            if self.evidence.status == WbcAdapterStatus.VERIFIED:
                return WbcAdapterStatus.INCOMPLETE  # Verified with gaps → incomplete
        return self.evidence.status

    def to_dict(self) -> Dict[str, Any]:
        return {
            "meta": self.meta.to_dict(),
            "evidence": self.evidence.to_dict(),
            "effective_status": self.effective_status.value,
            "gaps_applicable": [g.to_dict() for g in self.gaps_applicable],
            "is_consumable": self.is_consumable,
            "_non_authoritative": self._non_authoritative,
        }

    def to_dimension_cursor(self) -> DimensionCursor:
        """Produce a wbc DimensionCursor from this result, respecting gaps."""
        effective = self.effective_status
        if effective == WbcAdapterStatus.VERIFIED:
            return self.evidence.to_dimension_cursor()
        elif self.gaps_applicable:
            gap_details = "; ".join(
                f"{g.kind}: {g.reason}" for g in self.gaps_applicable
            )
            return DimensionCursor.unknown(
                "wbc",
                detail=f"legacy_gaps: {gap_details}",
            )
        return self.evidence.to_dimension_cursor()


# ── WBC compatibility adapter ──────────────────────────────────────────


@dataclass(frozen=True)
class WbcCompatAdapter:
    """Historical / mixed-version WBC compatibility adapter.

    Bridges WBC schema versions while explicitly representing
    non-backfillable legacy gaps.  Delegates to an underlying
    ``WbcAdapter`` for actual queries and layers compatibility
    metadata, expiry, and deletion gating on top.

    The adapter is a projection — it does not authorize, grant,
    or refresh source data.
    """

    meta: WbcCompatAdapterMeta
    """Adapter metadata (schema versions, gaps, expiry)."""

    wbc_adapter: WbcAdapter
    """Underlying WBC adapter for actual queries."""

    _non_authoritative: bool = field(default=True, init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_non_authoritative", True)

    def query(
        self,
        attempt_ref: WbcAttemptRef | None,
        *,
        observed_at_epoch_ms: Optional[float] = None,
    ) -> WbcCompatResult:
        """Query WBC boundary evidence through the compatibility adapter.

        Args:
            attempt_ref: WBC attempt reference (None → INDETERMINATE).
            observed_at_epoch_ms: Observation timestamp.

        Returns:
            WbcCompatResult with adapted evidence and applicable gaps.
        """
        ts = observed_at_epoch_ms or (time.time() * 1000)

        # Check adapter expiry
        if self.meta.is_expired:
            return WbcCompatResult(
                meta=self.meta,
                evidence=WbcBoundaryEvidence.indeterminate(
                    WbcAttemptRef.best_effort(""),
                    diagnostics=(f"adapter {self.meta.adapter_id} is expired",),
                    observed_at_epoch_ms=ts,
                ),
                gaps_applicable=self.meta.legacy_gaps,
            )

        # Query the underlying WBC adapter
        evidence = self.wbc_adapter.query_or_indeterminate(
            attempt_ref, observed_at_epoch_ms=ts
        )

        # Determine which legacy gaps apply to this query
        applicable_gaps: list[LegacyGap] = []
        if attempt_ref is None or not attempt_ref.is_exact_version:
            # No exact version → any pre-WBC gaps apply
            applicable_gaps.extend(
                g for g in self.meta.legacy_gaps if g.version_range == "pre-M6A"
            )

        # If WBC adapter returned INDETERMINATE, surface relevant gaps
        if evidence.status == WbcAdapterStatus.INDETERMINATE:
            applicable_gaps.extend(
                g for g in self.meta.legacy_gaps
                if g not in applicable_gaps
            )

        return WbcCompatResult(
            meta=self.meta,
            evidence=evidence,
            gaps_applicable=tuple(applicable_gaps),
        )

    def query_to_cursor(
        self,
        attempt_ref: WbcAttemptRef | None,
        *,
        observed_at_epoch_ms: Optional[float] = None,
    ) -> DimensionCursor:
        """Query and return a wbc DimensionCursor."""
        result = self.query(attempt_ref, observed_at_epoch_ms=observed_at_epoch_ms)
        return result.to_dimension_cursor()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "meta": self.meta.to_dict(),
            "_non_authoritative": self._non_authoritative,
        }


# ── WBC compatibility adapter registry ─────────────────────────────────


@dataclass(frozen=True)
class WbcCompatAdapterRegistry:
    """Registry of WBC compatibility adapters with deletion gate tracking.

    Tracks active, deprecated, expired, and legacy-gap-only adapters.
    Deletion is gated by zero-reader evidence.
    """

    adapters: Tuple[WbcCompatAdapterMeta, ...]
    """All registered adapters, sorted by adapter_id."""

    registry_digest: str = field(init=False)

    _non_authoritative: bool = field(default=True, init=False)

    def __post_init__(self) -> None:
        sorted_adapters = tuple(sorted(self.adapters, key=lambda a: a.adapter_id))
        object.__setattr__(self, "adapters", sorted_adapters)
        parts = "\\x00".join(a.adapter_digest for a in sorted_adapters)
        digest = hashlib.sha256(parts.encode("utf-8")).hexdigest()
        object.__setattr__(self, "registry_digest", f"sha256:{digest}")
        object.__setattr__(self, "_non_authoritative", True)

    @property
    def active_adapters(self) -> Tuple[WbcCompatAdapterMeta, ...]:
        return tuple(a for a in self.adapters if a.status == WbcCompatAdapterStatus.ACTIVE)

    @property
    def legacy_gap_adapters(self) -> Tuple[WbcCompatAdapterMeta, ...]:
        return tuple(a for a in self.adapters if a.status == WbcCompatAdapterStatus.LEGACY_GAP)

    @property
    def consumable_adapters(self) -> Tuple[WbcCompatAdapterMeta, ...]:
        return tuple(a for a in self.adapters if a.is_consumable)

    @property
    def expired_adapters(self) -> Tuple[WbcCompatAdapterMeta, ...]:
        return tuple(a for a in self.adapters if a.status == WbcCompatAdapterStatus.EXPIRED)

    @property
    def deletable_adapters(self) -> Tuple[WbcCompatAdapterMeta, ...]:
        return tuple(
            a for a in self.adapters
            if a.can_delete and a.status != WbcCompatAdapterStatus.DELETED
        )

    @property
    def deleted_adapters(self) -> Tuple[WbcCompatAdapterMeta, ...]:
        return tuple(a for a in self.adapters if a.status == WbcCompatAdapterStatus.DELETED)

    def all_gaps(self) -> Tuple[LegacyGap, ...]:
        """Return all legacy gaps across all adapters, deduplicated by gap_id."""
        seen: set[str] = set()
        gaps: list[LegacyGap] = []
        for a in self.adapters:
            for g in a.legacy_gaps:
                if g.gap_id not in seen:
                    seen.add(g.gap_id)
                    gaps.append(g)
        return tuple(gaps)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "adapters": [a.to_dict() for a in self.adapters],
            "active_count": len(self.active_adapters),
            "legacy_gap_count": len(self.legacy_gap_adapters),
            "consumable_count": len(self.consumable_adapters),
            "expired_count": len(self.expired_adapters),
            "deletable_count": len(self.deletable_adapters),
            "deleted_count": len(self.deleted_adapters),
            "all_gaps_count": len(self.all_gaps()),
            "registry_digest": self.registry_digest,
            "_non_authoritative": self._non_authoritative,
        }

    @classmethod
    def empty(cls) -> "WbcCompatAdapterRegistry":
        return cls(adapters=())

    def register(self, meta: WbcCompatAdapterMeta) -> "WbcCompatAdapterRegistry":
        existing = [a for a in self.adapters if a.adapter_id != meta.adapter_id]
        return WbcCompatAdapterRegistry(adapters=tuple(existing) + (meta,))

    def update_reader_count(self, adapter_id: str, count: int) -> "WbcCompatAdapterRegistry":
        updated: list[WbcCompatAdapterMeta] = []
        for a in self.adapters:
            if a.adapter_id == adapter_id:
                updated.append(a.with_reader_count(count))
            else:
                updated.append(a)
        return WbcCompatAdapterRegistry(adapters=tuple(updated))

    def delete_if_safe(self, adapter_id: str) -> "WbcCompatAdapterRegistry":
        updated: list[WbcCompatAdapterMeta] = []
        found = False
        for a in self.adapters:
            if a.adapter_id == adapter_id:
                updated.append(a.mark_deleted())
                found = True
            else:
                updated.append(a)
        if not found:
            raise KeyError(f"adapter {adapter_id} not found in registry")
        return WbcCompatAdapterRegistry(adapters=tuple(updated))


# ── Convenience: pre-built historical adapters ─────────────────────────


def make_pre_wbc_adapter(
    *,
    adapter_id: str = "",
    wbc_adapter: WbcAdapter | None = None,
) -> WbcCompatAdapter:
    """Build an adapter for pre-WBC plans (no backfillable evidence).

    The adapter surfaces a ``LegacyGap`` explicitly, so consumers
    get ``INDETERMINATE`` rather than a fabricated result.
    """
    if not adapter_id:
        adapter_id = hashlib.sha256(b"pre-wbc-adapter").hexdigest()[:16]

    gap = LegacyGap.pre_wbc()

    meta = WbcCompatAdapterMeta.legacy_gap_only(
        adapter_id=adapter_id,
        schema_in="pre-M6A",
        schema_out="M9",
        legacy_gaps=(gap,),
    )

    from arnold_pipelines.megaplan.wbc_adapter import NOOP_WBC_ADAPTER

    return WbcCompatAdapter(
        meta=meta,
        wbc_adapter=wbc_adapter or NOOP_WBC_ADAPTER,
    )


def make_migration_cutoff_adapter(
    *,
    adapter_id: str = "",
    cutoff_version: str = "",
    wbc_adapter: WbcAdapter | None = None,
    additional_gaps: Sequence[LegacyGap] = (),
) -> WbcCompatAdapter:
    """Build an adapter for a migration cutoff boundary.

    Plans before the cutoff have no backfillable WBC evidence.
    Plans after the cutoff use the provided wbc_adapter directly.
    """
    if not adapter_id:
        adapter_id = hashlib.sha256(f"migration-cutoff:{cutoff_version}".encode()).hexdigest()[:16]

    gap = LegacyGap.migration_cutoff(cutoff_version=cutoff_version)
    gaps = (gap,) + tuple(additional_gaps)

    meta = WbcCompatAdapterMeta.legacy_gap_only(
        adapter_id=adapter_id,
        schema_in=f"pre-{cutoff_version}" if cutoff_version else "mixed",
        schema_out="M9",
        legacy_gaps=gaps,
    )

    from arnold_pipelines.megaplan.wbc_adapter import NOOP_WBC_ADAPTER

    return WbcCompatAdapter(
        meta=meta,
        wbc_adapter=wbc_adapter or NOOP_WBC_ADAPTER,
    )


def make_mixed_version_adapter(
    *,
    adapter_id: str = "",
    schema_in: str = "",
    schema_out: str = "M9",
    wbc_adapter: WbcAdapter,
    legacy_gaps: Sequence[LegacyGap] = (),
    expires_in_ms: int = 86_400_000,
) -> WbcCompatAdapter:
    """Build a mixed-version WBC adapter bridging two schema versions.

    Args:
        adapter_id: Unique adapter identifier (auto-generated if empty).
        schema_in: Source WBC schema version.
        schema_out: Target WBC schema version.
        wbc_adapter: The underlying WBC adapter for actual queries.
        legacy_gaps: Legacy gaps this adapter surfaces.
        expires_in_ms: Milliseconds until this adapter expires (default 24h).

    Returns:
        A WbcCompatAdapter with expiry metadata.
    """
    if not adapter_id:
        raw = f"{schema_in}\\x00{schema_out}\\x00{time.time()}"
        adapter_id = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    expires_at = time.time() * 1000 + expires_in_ms

    meta = WbcCompatAdapterMeta.create(
        adapter_id=adapter_id,
        schema_in=schema_in,
        schema_out=schema_out,
        expires_at_epoch_ms=expires_at,
        legacy_gaps=tuple(legacy_gaps),
    )

    return WbcCompatAdapter(meta=meta, wbc_adapter=wbc_adapter)


# ── Query wrapper: safe consumer entry point ───────────────────────────


def compat_query_wbc(
    adapter: WbcCompatAdapter,
    attempt_ref: WbcAttemptRef | None,
    *,
    observed_at_epoch_ms: Optional[float] = None,
) -> WbcCompatResult:
    """Safe consumer entry point for WBC compatibility queries.

    * Checks adapter expiry before querying.
    * Surfaces legacy gaps alongside WBC evidence.
    * Returns INDETERMINATE when adapter is not consumable.
    """
    if not adapter.meta.is_consumable:
        return WbcCompatResult(
            meta=adapter.meta,
            evidence=WbcBoundaryEvidence.indeterminate(
                WbcAttemptRef.best_effort(""),
                diagnostics=(f"adapter {adapter.meta.adapter_id} is not consumable (status={adapter.meta.status.value})",),
                observed_at_epoch_ms=observed_at_epoch_ms,
            ),
            gaps_applicable=adapter.meta.legacy_gaps,
        )
    return adapter.query(attempt_ref, observed_at_epoch_ms=observed_at_epoch_ms)


__all__ = [
    # ── Types ──
    "WbcCompatAdapterStatus",
    "LegacyGap",
    "WbcCompatAdapterMeta",
    "WbcCompatResult",
    "WbcCompatAdapter",
    "WbcCompatAdapterRegistry",
    # ── Factory helpers ──
    "make_pre_wbc_adapter",
    "make_migration_cutoff_adapter",
    "make_mixed_version_adapter",
    # ── Safe consumer entry ──
    "compat_query_wbc",
]
