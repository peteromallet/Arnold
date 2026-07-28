"""Compatibility projection wrappers for historical consumers.

Compatibility bridges are allowed only as explicitly non-authoritative
projections.  This module provides bounded mixed-version wrappers for
historical consumers reading older schemas.  Every wrapper is:

* **Non-authoritative** — carries ``_non_authoritative: True`` explicitly.
* **Source-versioned** — carries the exact source-cursor vector that produced it.
* **Expiry-scoped** — carries an ``expires_at`` field after which the wrapper
  must not be consumed.
* **Gated by zero-reader deletion evidence** — a wrapper must not be deleted
  until all consumers have migrated off it.  Deletion requires reader-count
  or zero-reader evidence.

Design rules
------------
* Wrappers are adapters, not authority — they translate projection shapes
  without adding or removing evidence.
* Every wrapper declares its schema version (``schema_in`` → ``schema_out``).
* Expiry is metadata-driven: consumers check ``expires_at`` before reading.
* Deletion gates prevent premature removal: ``deletion_blocked_until`` carries
  the earliest safe deletion timestamp, and ``deletion_requires_zero_readers``
  is always True until explicit evidence is provided.
* Wrappers never refresh liveness or source data — they only reshape existing
  projection content.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, FrozenSet, List, Mapping, Optional, Sequence, Tuple

from arnold_pipelines.megaplan.source_cursor_contract import (
    DimensionCursor,
    SourceCursorDimension,
    SourceCursorVector,
)
from arnold_pipelines.megaplan.projection_digest import (
    ProjectionDigest,
    digest_hex,
    projection_digest,
    sort_payload_keys,
)


# ── Compatibility wrapper metadata ─────────────────────────────────────────


class WrapperStatus(Enum):
    """Lifecycle status of a compatibility wrapper.

    * ``ACTIVE`` — wrapper is in service, consumers may read.
    * ``DEPRECATED`` — wrapper is scheduled for deletion, only existing consumers.
    * ``EXPIRED`` — wrapper has passed its expiry, consumers must not read.
    * ``DELETED`` — wrapper has been removed (zero-reader evidence provided).
    """

    ACTIVE = "active"
    DEPRECATED = "deprecated"
    EXPIRED = "expired"
    DELETED = "deleted"


@dataclass(frozen=True)
class CompatibilityWrapperMeta:
    """Metadata for a single compatibility projection wrapper.

    Carries the source/target schema versions, expiry, deletion gate state,
    and non-authoritative marker.
    """

    wrapper_id: str
    """Unique identifier for this wrapper (content-addressed)."""

    schema_in: str
    """Source schema version this wrapper translates FROM."""

    schema_out: str
    """Target schema version this wrapper translates TO."""

    status: WrapperStatus = WrapperStatus.ACTIVE
    """Current lifecycle status."""

    expires_at_epoch_ms: float = 0.0
    """Epoch ms after which the wrapper must not be consumed."""

    deprecated_at_epoch_ms: float = 0.0
    """Epoch ms when the wrapper was marked deprecated."""

    deletion_blocked_until_epoch_ms: float = 0.0
    """Epoch ms before which deletion is blocked (reader grace period)."""

    deletion_requires_zero_readers: bool = True
    """True until explicit zero-reader evidence is provided."""

    reader_count: int = -1
    """Known reader count (-1 = unknown, must be 0 for deletion)."""

    source_cursor_digest: str = ""
    """Digest of the source-cursor vector that produced the wrapped projection."""

    wrapper_digest: str = field(init=False)
    """Content-addressed digest of this wrapper metadata."""

    _non_authoritative: bool = field(default=True, init=False)

    def __post_init__(self) -> None:
        raw = (
            f"{self.wrapper_id}\x00{self.schema_in}\x00{self.schema_out}\x00"
            f"{self.status.value}\x00{self.expires_at_epoch_ms}\x00"
            f"{self.source_cursor_digest}"
        )
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        object.__setattr__(self, "wrapper_digest", f"sha256:{digest}")
        object.__setattr__(self, "_non_authoritative", True)

    @property
    def is_expired(self) -> bool:
        """True when the wrapper has passed its expiry."""
        if self.expires_at_epoch_ms <= 0:
            return False
        return time.time() * 1000 > self.expires_at_epoch_ms

    @property
    def can_delete(self) -> bool:
        """True when deletion is safe (zero readers or explicit evidence)."""
        if self.deletion_requires_zero_readers and self.reader_count != 0:
            return False
        now = time.time() * 1000
        if self.deletion_blocked_until_epoch_ms > now:
            return False
        return True

    @property
    def should_deprecate(self) -> bool:
        """True when the wrapper should be marked deprecated."""
        if self.status == WrapperStatus.DEPRECATED:
            return False
        if self.is_expired:
            return True
        return False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "wrapper_id": self.wrapper_id,
            "schema_in": self.schema_in,
            "schema_out": self.schema_out,
            "status": self.status.value,
            "expires_at_epoch_ms": self.expires_at_epoch_ms,
            "deprecated_at_epoch_ms": self.deprecated_at_epoch_ms,
            "deletion_blocked_until_epoch_ms": self.deletion_blocked_until_epoch_ms,
            "deletion_requires_zero_readers": self.deletion_requires_zero_readers,
            "reader_count": self.reader_count,
            "source_cursor_digest": self.source_cursor_digest,
            "wrapper_digest": self.wrapper_digest,
            "is_expired": self.is_expired,
            "can_delete": self.can_delete,
            "should_deprecate": self.should_deprecate,
            "_non_authoritative": self._non_authoritative,
        }

    @classmethod
    def create(
        cls,
        wrapper_id: str,
        schema_in: str,
        schema_out: str,
        *,
        expires_at_epoch_ms: float = 0.0,
        source_cursor_digest: str = "",
        reader_count: int = -1,
    ) -> "CompatibilityWrapperMeta":
        """Create a new active compatibility wrapper."""
        return cls(
            wrapper_id=wrapper_id,
            schema_in=schema_in,
            schema_out=schema_out,
            status=WrapperStatus.ACTIVE,
            expires_at_epoch_ms=expires_at_epoch_ms,
            source_cursor_digest=source_cursor_digest,
            reader_count=reader_count,
        )

    def mark_deprecated(self, *, blocked_until_epoch_ms: float = 0.0) -> "CompatibilityWrapperMeta":
        """Return a new wrapper metadata with DEPRECATED status."""
        now = time.time() * 1000
        return CompatibilityWrapperMeta(
            wrapper_id=self.wrapper_id,
            schema_in=self.schema_in,
            schema_out=self.schema_out,
            status=WrapperStatus.DEPRECATED,
            expires_at_epoch_ms=self.expires_at_epoch_ms,
            deprecated_at_epoch_ms=now,
            deletion_blocked_until_epoch_ms=max(self.deletion_blocked_until_epoch_ms, blocked_until_epoch_ms),
            deletion_requires_zero_readers=self.deletion_requires_zero_readers,
            reader_count=self.reader_count,
            source_cursor_digest=self.source_cursor_digest,
        )

    def mark_expired(self) -> "CompatibilityWrapperMeta":
        """Return a new wrapper metadata with EXPIRED status."""
        return CompatibilityWrapperMeta(
            wrapper_id=self.wrapper_id,
            schema_in=self.schema_in,
            schema_out=self.schema_out,
            status=WrapperStatus.EXPIRED,
            expires_at_epoch_ms=self.expires_at_epoch_ms,
            deprecated_at_epoch_ms=self.deprecated_at_epoch_ms,
            deletion_blocked_until_epoch_ms=self.deletion_blocked_until_epoch_ms,
            deletion_requires_zero_readers=self.deletion_requires_zero_readers,
            reader_count=self.reader_count,
            source_cursor_digest=self.source_cursor_digest,
        )

    def mark_deleted(self) -> "CompatibilityWrapperMeta":
        """Return a new wrapper metadata with DELETED status.

        Only allowed when ``can_delete`` is True and reader_count is 0.
        """
        if not self.can_delete:
            raise ValueError(
                f"cannot delete wrapper {self.wrapper_id}: "
                f"deletion not safe (reader_count={self.reader_count})"
            )
        return CompatibilityWrapperMeta(
            wrapper_id=self.wrapper_id,
            schema_in=self.schema_in,
            schema_out=self.schema_out,
            status=WrapperStatus.DELETED,
            expires_at_epoch_ms=self.expires_at_epoch_ms,
            deprecated_at_epoch_ms=self.deprecated_at_epoch_ms,
            deletion_blocked_until_epoch_ms=self.deletion_blocked_until_epoch_ms,
            deletion_requires_zero_readers=False,
            reader_count=0,
            source_cursor_digest=self.source_cursor_digest,
        )

    def with_reader_count(self, count: int) -> "CompatibilityWrapperMeta":
        """Return a new wrapper metadata with updated reader count.

        A count of 0 satisfies the zero-reader deletion requirement when
        ``deletion_blocked_until_epoch_ms`` has passed.
        """
        return CompatibilityWrapperMeta(
            wrapper_id=self.wrapper_id,
            schema_in=self.schema_in,
            schema_out=self.schema_out,
            status=self.status,
            expires_at_epoch_ms=self.expires_at_epoch_ms,
            deprecated_at_epoch_ms=self.deprecated_at_epoch_ms,
            deletion_blocked_until_epoch_ms=self.deletion_blocked_until_epoch_ms,
            deletion_requires_zero_readers=self.deletion_requires_zero_readers,
            reader_count=count,
            source_cursor_digest=self.source_cursor_digest,
        )


# ── Compatibility projection wrapper ───────────────────────────────────────


@dataclass(frozen=True)
class CompatibilityProjection:
    """A single compatibility projection wrapping a source projection.

    The wrapper translates from ``schema_in`` to ``schema_out`` by applying
    a transformation function.  The wrapped projection carries explicit
    non-authoritative markers, source-cursor evidence, and expiry metadata.

    The wrapper itself is a projection — it does not authorize, grant, or
    refresh source data.
    """

    meta: CompatibilityWrapperMeta
    """Metadata describing this wrapper."""

    wrapped_payload: Dict[str, Any]
    """The transformed payload in the target schema."""

    source_cursor: Optional[SourceCursorVector] = None
    """Source-cursor vector from the original projection."""

    _non_authoritative: bool = field(default=True, init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_non_authoritative", True)

    @property
    def projection_digest(self) -> ProjectionDigest:
        """Content-addressed digest of the wrapped projection."""
        sorted_payload = sort_payload_keys(self.wrapped_payload)
        payload_json = __import__("json").dumps(
            sorted_payload, sort_keys=True, separators=(",", ":")
        )
        payload_digest = digest_hex(projection_digest(payload_json))
        return ProjectionDigest(
            kind=f"compatibility:{self.meta.schema_in}->{self.meta.schema_out}",
            payload_digest=payload_digest,
            source_cursor_digest=self.meta.source_cursor_digest,
        )

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "meta": self.meta.to_dict(),
            "wrapped_payload": self.wrapped_payload,
            "_non_authoritative": self._non_authoritative,
        }
        if self.source_cursor is not None:
            result["source_cursor"] = self.source_cursor.to_dict()
        return result

    @classmethod
    def wrap(
        cls,
        source_projection: Mapping[str, Any],
        *,
        schema_in: str,
        schema_out: str,
        transform: Callable[[Mapping[str, Any]], Dict[str, Any]],
        source_cursor: Optional[SourceCursorVector] = None,
        expires_in_ms: int = 86_400_000,  # 24 hours default
        wrapper_id: str = "",
    ) -> "CompatibilityProjection":
        """Create a compatibility wrapper around a source projection.

        Args:
            source_projection: The original projection in schema_in format.
            schema_in: Source schema version.
            schema_out: Target schema version.
            transform: Function that maps schema_in payload to schema_out payload.
            source_cursor: Source-cursor vector from the original projection.
            expires_in_ms: Milliseconds until this wrapper expires.
            wrapper_id: Unique wrapper identifier (auto-generated if empty).

        Returns:
            A CompatibilityProjection with the wrapped payload.
        """
        if not wrapper_id:
            raw = f"{schema_in}\x00{schema_out}\x00{time.time()}"
            wrapper_id = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

        cursor_digest = source_cursor.vector_id if source_cursor else ""

        now = time.time() * 1000
        meta = CompatibilityWrapperMeta.create(
            wrapper_id=wrapper_id,
            schema_in=schema_in,
            schema_out=schema_out,
            expires_at_epoch_ms=now + expires_in_ms,
            source_cursor_digest=cursor_digest,
        )

        wrapped = transform(source_projection)
        # Ensure wrapped payload has non-authoritative marker
        if "_non_authoritative" not in wrapped:
            wrapped["_non_authoritative"] = True

        return cls(
            meta=meta,
            wrapped_payload=wrapped,
            source_cursor=source_cursor,
        )


# ── Wrapper registry (tracks active wrappers for deletion gating) ──────────


@dataclass(frozen=True)
class WrapperRegistry:
    """Registry of active compatibility wrappers with deletion gate tracking.

    Tracks which wrappers exist, their status, and whether they can be
    safely deleted.  Deletion is gated by zero-reader evidence.
    """

    wrappers: Tuple[CompatibilityWrapperMeta, ...]
    """All registered wrappers, sorted by wrapper_id."""

    registry_digest: str = field(init=False)

    _non_authoritative: bool = field(default=True, init=False)

    def __post_init__(self) -> None:
        sorted_wrappers = tuple(sorted(self.wrappers, key=lambda w: w.wrapper_id))
        object.__setattr__(self, "wrappers", sorted_wrappers)
        parts = "\x00".join(w.wrapper_digest for w in sorted_wrappers)
        digest = hashlib.sha256(parts.encode("utf-8")).hexdigest()
        object.__setattr__(self, "registry_digest", f"sha256:{digest}")
        object.__setattr__(self, "_non_authoritative", True)

    @property
    def active_wrappers(self) -> Tuple[CompatibilityWrapperMeta, ...]:
        """Wrappers that are ACTIVE."""
        return tuple(w for w in self.wrappers if w.status == WrapperStatus.ACTIVE)

    @property
    def deprecated_wrappers(self) -> Tuple[CompatibilityWrapperMeta, ...]:
        """Wrappers that are DEPRECATED."""
        return tuple(w for w in self.wrappers if w.status == WrapperStatus.DEPRECATED)

    @property
    def expired_wrappers(self) -> Tuple[CompatibilityWrapperMeta, ...]:
        """Wrappers that are EXPIRED."""
        return tuple(w for w in self.wrappers if w.status == WrapperStatus.EXPIRED)

    @property
    def deletable_wrappers(self) -> Tuple[CompatibilityWrapperMeta, ...]:
        """Wrappers that can be safely deleted (zero readers, grace period passed)."""
        return tuple(w for w in self.wrappers if w.can_delete and w.status != WrapperStatus.DELETED)

    @property
    def deleted_wrappers(self) -> Tuple[CompatibilityWrapperMeta, ...]:
        """Wrappers that have been deleted."""
        return tuple(w for w in self.wrappers if w.status == WrapperStatus.DELETED)

    def has_active_wrapper_for(self, schema_in: str, schema_out: str) -> bool:
        """True when an active wrapper exists for the given schema pair."""
        return any(
            w.schema_in == schema_in and w.schema_out == schema_out and w.status == WrapperStatus.ACTIVE
            for w in self.wrappers
        )

    def by_schema_pair(self, schema_in: str, schema_out: str) -> Tuple[CompatibilityWrapperMeta, ...]:
        """Return wrappers for a specific schema pair."""
        return tuple(
            w for w in self.wrappers
            if w.schema_in == schema_in and w.schema_out == schema_out
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "wrappers": [w.to_dict() for w in self.wrappers],
            "active_count": len(self.active_wrappers),
            "deprecated_count": len(self.deprecated_wrappers),
            "expired_count": len(self.expired_wrappers),
            "deletable_count": len(self.deletable_wrappers),
            "deleted_count": len(self.deleted_wrappers),
            "registry_digest": self.registry_digest,
            "_non_authoritative": self._non_authoritative,
        }

    @classmethod
    def empty(cls) -> "WrapperRegistry":
        """Create an empty registry."""
        return cls(wrappers=())

    def register(self, meta: CompatibilityWrapperMeta) -> "WrapperRegistry":
        """Return a new registry with the wrapper added."""
        existing = [w for w in self.wrappers if w.wrapper_id != meta.wrapper_id]
        return WrapperRegistry(wrappers=tuple(existing) + (meta,))

    def update_reader_count(self, wrapper_id: str, count: int) -> "WrapperRegistry":
        """Return a new registry with updated reader count for a wrapper."""
        updated: list[CompatibilityWrapperMeta] = []
        for w in self.wrappers:
            if w.wrapper_id == wrapper_id:
                updated.append(w.with_reader_count(count))
            else:
                updated.append(w)
        return WrapperRegistry(wrappers=tuple(updated))

    def delete_if_safe(self, wrapper_id: str) -> "WrapperRegistry":
        """Return a new registry with the wrapper marked DELETED if safe.

        Raises ValueError if deletion is not safe.
        """
        updated: list[CompatibilityWrapperMeta] = []
        for w in self.wrappers:
            if w.wrapper_id == wrapper_id:
                updated.append(w.mark_deleted())
            else:
                updated.append(w)
        return WrapperRegistry(wrappers=tuple(updated))


# ── Convenience: common transformation helpers ─────────────────────────────


def identity_transform(payload: Mapping[str, Any]) -> Dict[str, Any]:
    """Pass-through transform (same schema in/out)."""
    return dict(payload)


def strip_unknown_fields(
    payload: Mapping[str, Any],
    *,
    known_fields: Tuple[str, ...],
) -> Dict[str, Any]:
    """Transform that keeps only known fields (for forward-compat stripping)."""
    return {k: payload[k] for k in known_fields if k in payload}


def rename_fields(
    payload: Mapping[str, Any],
    *,
    field_map: Mapping[str, str],
) -> Dict[str, Any]:
    """Transform that renames fields according to a mapping."""
    result = dict(payload)
    for old_name, new_name in field_map.items():
        if old_name in result:
            result[new_name] = result.pop(old_name)
    return result


def add_defaults(
    payload: Mapping[str, Any],
    *,
    defaults: Mapping[str, Any],
) -> Dict[str, Any]:
    """Transform that adds default values for missing fields."""
    result = dict(payload)
    for key, value in defaults.items():
        if key not in result:
            result[key] = value
    return result


def compose_transforms(
    *transforms: Callable[[Mapping[str, Any]], Dict[str, Any]],
) -> Callable[[Mapping[str, Any]], Dict[str, Any]]:
    """Compose multiple transforms into a single transform."""
    def composed(payload: Mapping[str, Any]) -> Dict[str, Any]:
        result: Dict[str, Any] = dict(payload)
        for t in transforms:
            result = t(result)
        return result
    return composed


__all__ = [
    # ── Types ──
    "WrapperStatus",
    "CompatibilityWrapperMeta",
    "CompatibilityProjection",
    "WrapperRegistry",
    # ── Transform helpers ──
    "identity_transform",
    "strip_unknown_fields",
    "rename_fields",
    "add_defaults",
    "compose_transforms",
]
