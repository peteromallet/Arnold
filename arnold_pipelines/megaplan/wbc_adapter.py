"""Shared WBC (Workflow Boundary Contract) consumer adapter layer.

WBC owns exact-version attempt/boundary evidence but grants no authority.
This module provides a declarative adapter that wraps exact-version WBC
attempt and boundary queries for projections and control-path rereads.

Every result is typed as VERIFIED, INCOMPLETE, INDETERMINATE, or INCOHERENT.
There is no implicit-latest fallback — persistence or migration gaps are
surfaced as INDETERMINATE, never silently defaulted to a stale or optimistic
result.

Design rules
------------
* All results carry ``_non_authoritative: True`` — WBC evidence is never
  bearer authority for dispatch, repair, or completion.
* Exact-version queries require an attempt_ref and version; callers must
  provide both.  Best-effort queries may fall back to INDETERMINATE.
* The adapter is reusable across local, cloud, resident, and repair consumers.
* Indeterminate and incoherent results carry typed diagnostics for caller
  inspection.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, FrozenSet, Literal, Mapping, Optional, Sequence, Tuple, TypeAlias

from arnold_pipelines.megaplan.source_cursor_contract import (
    DimensionCursor,
    SourceCursorDimension,
    SourceCursorState,
    SourceCursorVector,
)

# ── WBC adapter result status ──────────────────────────────────────────────


class WbcAdapterStatus(Enum):
    """Typed result status for WBC adapter queries.

    Maps onto the source-cursor ``wbc`` dimension states:
    * VERIFIED = "fresh" (exact version bound, evidence coherent)
    * INCOMPLETE = "stale" (source coherent but required evidence absent)
    * INDETERMINATE = "unknown" (cannot read or version-bind the source)
    * INCOHERENT = "incoherent" (evidence exists but contradicts the contract)
    """

    VERIFIED = "verified"
    INCOMPLETE = "incomplete"
    INDETERMINATE = "indeterminate"
    INCOHERENT = "incoherent"

    def to_cursor_state(self) -> SourceCursorState:
        """Map adapter status to source-cursor state."""
        mapping: Dict[WbcAdapterStatus, SourceCursorState] = {
            WbcAdapterStatus.VERIFIED: "fresh",
            WbcAdapterStatus.INCOMPLETE: "stale",
            WbcAdapterStatus.INDETERMINATE: "unknown",
            WbcAdapterStatus.INCOHERENT: "incoherent",
        }
        return mapping[self]


# ── WBC attempt reference ──────────────────────────────────────────────────


@dataclass(frozen=True)
class WbcAttemptRef:
    """Exact reference to a WBC attempt.

    An attempt is identified by its ``attempt_id`` plus an optional
    ``version`` (sequence number or digest).  Exact-version queries
    require both.
    """

    attempt_id: str
    """Unique identifier for the attempt."""

    version: str = ""
    """Exact version: sequence number, attempt digest, or empty for best-effort."""

    kind: str = ""
    """Attempt kind: custody, delivery, publication, repair, etc."""

    @property
    def is_exact_version(self) -> bool:
        """True when both attempt_id and version are provided."""
        return bool(self.attempt_id) and bool(self.version)

    @property
    def ref_digest(self) -> str:
        """Content-addressed evidence identifier for this reference."""
        raw = f"{self.attempt_id}\x00{self.version}\x00{self.kind}"
        return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "attempt_id": self.attempt_id,
            "version": self.version,
            "kind": self.kind,
            "is_exact_version": self.is_exact_version,
            "ref_digest": self.ref_digest,
        }

    @classmethod
    def exact(cls, attempt_id: str, version: str, *, kind: str = "") -> "WbcAttemptRef":
        """Create an exact-version attempt reference."""
        return cls(attempt_id=attempt_id, version=version, kind=kind)

    @classmethod
    def best_effort(cls, attempt_id: str, *, kind: str = "") -> "WbcAttemptRef":
        """Create a best-effort reference (no version → INDETERMINATE on gap)."""
        return cls(attempt_id=attempt_id, version="", kind=kind)


# ── WBC boundary evidence ──────────────────────────────────────────────────


@dataclass(frozen=True)
class WbcBoundaryEvidence:
    """Immutable, non-authoritative view of WBC boundary evidence.

    Carries the attempt reference, boundary events (start/terminal), and
    exact version cursor.  This is evidence only — it never authorizes
    dispatch, repair, or completion.
    """

    attempt_ref: WbcAttemptRef
    """Exact attempt reference."""

    status: WbcAdapterStatus
    """Verified, incomplete, indeterminate, or incoherent."""

    start_event_digest: str = ""
    """Content digest of the start/boundary event (empty if unavailable)."""

    terminal_event_digest: str = ""
    """Content digest of the terminal event (empty if unavailable)."""

    last_sequence: int = 0
    """Last observed sequence number in the attempt ledger."""

    source_cursor_digest: str = ""
    """Digest of the source cursor at read time."""

    diagnostics: Tuple[str, ...] = ()
    """Diagnostic detail for non-verified results."""

    observed_at_epoch_ms: Optional[float] = None
    """When this boundary was read from source."""

    _non_authoritative: bool = field(default=True, init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_non_authoritative", True)

    @property
    def is_verified(self) -> bool:
        return self.status == WbcAdapterStatus.VERIFIED

    @property
    def is_blocking(self) -> bool:
        """True when the result blocks downstream action."""
        return self.status != WbcAdapterStatus.VERIFIED

    def to_dict(self) -> Dict[str, Any]:
        return {
            "attempt_ref": self.attempt_ref.to_dict(),
            "status": self.status.value,
            "cursor_state": self.status.to_cursor_state(),
            "start_event_digest": self.start_event_digest,
            "terminal_event_digest": self.terminal_event_digest,
            "last_sequence": self.last_sequence,
            "source_cursor_digest": self.source_cursor_digest,
            "diagnostics": list(self.diagnostics),
            "observed_at_epoch_ms": self.observed_at_epoch_ms,
            "is_verified": self.is_verified,
            "is_blocking": self.is_blocking,
            "_non_authoritative": self._non_authoritative,
        }

    def to_dimension_cursor(self) -> DimensionCursor:
        """Convert to a source-cursor ``wbc`` dimension entry."""
        observed_at = ""
        if self.observed_at_epoch_ms is not None:
            from datetime import datetime, timezone

            observed_at = datetime.fromtimestamp(
                self.observed_at_epoch_ms / 1000, tz=timezone.utc
            ).isoformat()

        version = ""
        if self.attempt_ref.is_exact_version:
            version = f"{self.attempt_ref.attempt_id}:{self.attempt_ref.version}"

        detail = "; ".join(self.diagnostics) if self.diagnostics else ""

        cursor_state = self.status.to_cursor_state()

        if cursor_state == "fresh":
            return DimensionCursor.fresh(
                "wbc", version, observed_at, detail=detail
            )
        elif cursor_state == "stale":
            return DimensionCursor.stale(
                "wbc", version, observed_at, detail=detail
            )
        elif cursor_state == "incoherent":
            return DimensionCursor.incoherent(
                "wbc", observed_at=observed_at, detail=detail
            )
        else:
            return DimensionCursor.unknown(
                "wbc", observed_at=observed_at, detail=detail
            )

    @classmethod
    def verified(
        cls,
        attempt_ref: WbcAttemptRef,
        *,
        start_event_digest: str = "",
        terminal_event_digest: str = "",
        last_sequence: int = 0,
        source_cursor_digest: str = "",
        observed_at_epoch_ms: Optional[float] = None,
    ) -> "WbcBoundaryEvidence":
        """Create verified boundary evidence."""
        return cls(
            attempt_ref=attempt_ref,
            status=WbcAdapterStatus.VERIFIED,
            start_event_digest=start_event_digest,
            terminal_event_digest=terminal_event_digest,
            last_sequence=last_sequence,
            source_cursor_digest=source_cursor_digest,
            observed_at_epoch_ms=observed_at_epoch_ms,
        )

    @classmethod
    def indeterminate(
        cls,
        attempt_ref: WbcAttemptRef,
        *,
        diagnostics: Sequence[str] = (),
        observed_at_epoch_ms: Optional[float] = None,
    ) -> "WbcBoundaryEvidence":
        """Create indeterminate evidence (cannot read or version-bind)."""
        return cls(
            attempt_ref=attempt_ref,
            status=WbcAdapterStatus.INDETERMINATE,
            diagnostics=tuple(diagnostics),
            observed_at_epoch_ms=observed_at_epoch_ms,
        )

    @classmethod
    def incomplete(
        cls,
        attempt_ref: WbcAttemptRef,
        *,
        start_event_digest: str = "",
        last_sequence: int = 0,
        diagnostics: Sequence[str] = (),
        observed_at_epoch_ms: Optional[float] = None,
    ) -> "WbcBoundaryEvidence":
        """Create incomplete evidence (source coherent but missing terminal)."""
        return cls(
            attempt_ref=attempt_ref,
            status=WbcAdapterStatus.INCOMPLETE,
            start_event_digest=start_event_digest,
            last_sequence=last_sequence,
            diagnostics=tuple(diagnostics),
            observed_at_epoch_ms=observed_at_epoch_ms,
        )

    @classmethod
    def incoherent(
        cls,
        attempt_ref: WbcAttemptRef,
        *,
        diagnostics: Sequence[str] = (),
        observed_at_epoch_ms: Optional[float] = None,
    ) -> "WbcBoundaryEvidence":
        """Create incoherent evidence (contract violation detected)."""
        return cls(
            attempt_ref=attempt_ref,
            status=WbcAdapterStatus.INCOHERENT,
            diagnostics=tuple(diagnostics),
            observed_at_epoch_ms=observed_at_epoch_ms,
        )


# ── WBC adapter query protocol ─────────────────────────────────────────────


WbcQueryFn: TypeAlias = Callable[
    [WbcAttemptRef, Optional[float]],
    WbcBoundaryEvidence,
]
"""Signature for a WBC adapter query function.

Takes an attempt reference and optional observation timestamp,
returns boundary evidence (always non-authoritative).
"""


# ── WBC adapter ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class WbcAdapter:
    """Declarative WBC adapter for projections and control-path rereads.

    Centralizes exact-version WBC reads behind typed, non-authoritative
    boundary evidence.  Every query returns VERIFIED, INCOMPLETE,
    INDETERMINATE, or INCOHERENT — no implicit-latest fallback.

    The adapter is stateless: it delegates to pluggable query functions.
    This makes it testable and reusable across local, cloud, resident,
    and repair consumers.
    """

    query_fn: WbcQueryFn
    """Pluggable query function that reads from the WBC store."""

    default_freshness_window_ms: int = 30_000
    """Default freshness window for WBC reads (30s)."""

    def query(
        self,
        attempt_ref: WbcAttemptRef,
        *,
        observed_at_epoch_ms: Optional[float] = None,
    ) -> WbcBoundaryEvidence:
        """Query WBC boundary evidence for an exact-version attempt.

        Args:
            attempt_ref: Exact or best-effort attempt reference.
            observed_at_epoch_ms: When the query was initiated.

        Returns:
            WbcBoundaryEvidence with typed status.  Best-effort references
            without a version produce INDETERMINATE for persistence/migration
            gaps.
        """
        # Best-effort reference without version → INDETERMINATE
        if not attempt_ref.is_exact_version:
            return WbcBoundaryEvidence.indeterminate(
                attempt_ref,
                diagnostics=(
                    "no exact version provided; cannot bind to a specific attempt state",
                ),
                observed_at_epoch_ms=observed_at_epoch_ms,
            )

        ts = observed_at_epoch_ms or (time.time() * 1000)
        return self.query_fn(attempt_ref, ts)

    def query_or_indeterminate(
        self,
        attempt_ref: WbcAttemptRef | None,
        *,
        observed_at_epoch_ms: Optional[float] = None,
    ) -> WbcBoundaryEvidence:
        """Query WBC boundary evidence, returning INDETERMINATE for None refs.

        This is the safe entry point for consumers that may not have a
        WBC reference available (e.g. pre-WBC plans, migration gaps).
        """
        if attempt_ref is None:
            return WbcBoundaryEvidence.indeterminate(
                WbcAttemptRef.best_effort(""),
                diagnostics=("no WBC attempt reference available",),
                observed_at_epoch_ms=observed_at_epoch_ms,
            )
        return self.query(attempt_ref, observed_at_epoch_ms=observed_at_epoch_ms)

    def query_to_cursor(
        self,
        attempt_ref: WbcAttemptRef | None,
        *,
        observed_at_epoch_ms: Optional[float] = None,
    ) -> DimensionCursor:
        """Query WBC and return a source-cursor ``wbc`` dimension entry.

        Convenience for projection builders that need to populate the
        source-cursor vector's ``wbc`` dimension.
        """
        evidence = self.query_or_indeterminate(
            attempt_ref, observed_at_epoch_ms=observed_at_epoch_ms
        )
        return evidence.to_dimension_cursor()


# ── Composite WBC adapter (multi-attempt) ──────────────────────────────────


@dataclass(frozen=True)
class WbcCompositeAdapter:
    """Adapter that queries multiple WBC attempts and aggregates results.

    Useful for consumers that need to check custody, delivery, and repair
    WBC attempts in a single call.
    """

    adapters: Dict[str, WbcAdapter]
    """Named adapters keyed by attempt kind (custody, delivery, repair, etc.)."""

    def query_all(
        self,
        refs: Mapping[str, WbcAttemptRef | None],
        *,
        observed_at_epoch_ms: Optional[float] = None,
    ) -> Dict[str, WbcBoundaryEvidence]:
        """Query all named adapters and return aggregated evidence.

        Args:
            refs: Mapping from kind to attempt reference (None = skip).
            observed_at_epoch_ms: Observation timestamp.

        Returns:
            Mapping from kind to boundary evidence.  Kinds without an
            adapter or with a None ref produce INDETERMINATE.
        """
        results: Dict[str, WbcBoundaryEvidence] = {}
        ts = observed_at_epoch_ms or (time.time() * 1000)

        for kind, adapter in self.adapters.items():
            ref = refs.get(kind)
            results[kind] = adapter.query_or_indeterminate(
                ref, observed_at_epoch_ms=ts
            )

        return results

    def cursors_for_dimension(
        self,
        refs: Mapping[str, WbcAttemptRef | None],
        *,
        observed_at_epoch_ms: Optional[float] = None,
    ) -> Tuple[DimensionCursor, ...]:
        """Query all adapters and return ``wbc`` dimension cursors.

        Each result becomes a DimensionCursor.  If all cursors are fresh,
        the ``wbc`` dimension is fresh; otherwise the best available state
        is used.
        """
        evidence_map = self.query_all(refs, observed_at_epoch_ms=observed_at_epoch_ms)
        cursors = tuple(
            ev.to_dimension_cursor() for ev in evidence_map.values()
        )
        return cursors

    def aggregate_wbc_cursor(
        self,
        refs: Mapping[str, WbcAttemptRef | None],
        *,
        observed_at_epoch_ms: Optional[float] = None,
    ) -> DimensionCursor:
        """Query all adapters and produce a single aggregate ``wbc`` cursor.

        * If all results are VERIFIED → fresh
        * If any result is INCOHERENT → incoherent
        * If any result is INDETERMINATE (and none VERIFIED) → unknown
        * If any result is INCOMPLETE (and none INDETERMINATE/INCOHERENT) → stale
        """
        evidence_map = self.query_all(refs, observed_at_epoch_ms=observed_at_epoch_ms)

        if not evidence_map:
            return DimensionCursor.unknown("wbc", detail="no WBC adapters configured")

        statuses = [ev.status for ev in evidence_map.values()]

        if all(s == WbcAdapterStatus.VERIFIED for s in statuses):
            # All verified → fresh with aggregate version
            versions = [
                f"{ev.attempt_ref.attempt_id}:{ev.attempt_ref.version}"
                for ev in evidence_map.values()
            ]
            version_str = "; ".join(versions)
            from datetime import datetime, timezone

            ts = observed_at_epoch_ms or (time.time() * 1000)
            observed_at = datetime.fromtimestamp(
                ts / 1000, tz=timezone.utc
            ).isoformat()
            return DimensionCursor.fresh("wbc", version_str, observed_at)

        if any(s == WbcAdapterStatus.INCOHERENT for s in statuses):
            details = []
            for ev in evidence_map.values():
                if ev.status == WbcAdapterStatus.INCOHERENT:
                    details.extend(ev.diagnostics)
            return DimensionCursor.incoherent(
                "wbc", detail="; ".join(details) if details else "incoherent WBC evidence"
            )

        if any(s == WbcAdapterStatus.INDETERMINATE for s in statuses):
            indeterminate_kinds = [
                ev.attempt_ref.kind
                for ev in evidence_map.values()
                if ev.status == WbcAdapterStatus.INDETERMINATE
            ]
            has_verified = any(s == WbcAdapterStatus.VERIFIED for s in statuses)
            if has_verified:
                return DimensionCursor.stale(
                    "wbc",
                    "partial",
                    "",
                    detail=f"partial WBC: indeterminate for {', '.join(indeterminate_kinds)}",
                )
            return DimensionCursor.unknown(
                "wbc",
                detail=f"indeterminate WBC for: {', '.join(indeterminate_kinds)}",
            )

        # All remaining: INCOMPLETE or mix → stale
        return DimensionCursor.stale(
            "wbc", "incomplete", "", detail="WBC evidence incomplete"
        )


# ── No-op adapter (for migration gaps / pre-WBC plans) ────────────────────


def _noop_query(attempt_ref: WbcAttemptRef, observed_at_epoch_ms: Optional[float]) -> WbcBoundaryEvidence:
    """No-op query that always returns INDETERMINATE."""
    return WbcBoundaryEvidence.indeterminate(
        attempt_ref,
        diagnostics=("WBC store not available (migration gap or pre-WBC plan)",),
        observed_at_epoch_ms=observed_at_epoch_ms,
    )


NOOP_WBC_ADAPTER = WbcAdapter(query_fn=_noop_query)
"""A no-op adapter that always returns INDETERMINATE.

Used for pre-WBC plans or migration gaps where the WBC store is not
available.  This ensures consumers always get a typed INDETERMINATE
result rather than None or a default.
"""


# ── Convenience: build source-cursor wbc dimension from adapter ────────────


def wbc_cursor_from_adapter(
    adapter: WbcAdapter,
    attempt_ref: WbcAttemptRef | None,
    *,
    observed_at_epoch_ms: Optional[float] = None,
) -> DimensionCursor:
    """Build a ``wbc`` source-cursor dimension from a WBC adapter query.

    Convenience function for projection builders.  Returns a
    ``DimensionCursor`` suitable for inclusion in a ``SourceCursorVector``.
    """
    return adapter.query_to_cursor(attempt_ref, observed_at_epoch_ms=observed_at_epoch_ms)


# ── Adapter factory: wrap existing wbc_queries module ──────────────────────


def make_wbc_adapter_from_store(
    attempt_store: Any,
    *,
    freshness_window_ms: int = 30_000,
) -> WbcAdapter:
    """Build a WBC adapter backed by an existing WBC attempt store.

    Args:
        attempt_store: An object with a ``get_attempt`` or ``query_attempt`` method
            that returns (LedgerEvent | None) for a given attempt_ref.
        freshness_window_ms: Default freshness window for reads.

    Returns:
        A WbcAdapter that delegates to the store.
    """
    def _store_query(attempt_ref: WbcAttemptRef, observed_at_epoch_ms: Optional[float]) -> WbcBoundaryEvidence:
        ts = observed_at_epoch_ms or (time.time() * 1000)

        try:
            # Try get_attempt first (exact version)
            get_fn = getattr(attempt_store, "get_attempt", None) or getattr(
                attempt_store, "query_attempt", None
            )
            if get_fn is None:
                return WbcBoundaryEvidence.indeterminate(
                    attempt_ref,
                    diagnostics=("attempt store has no query method",),
                    observed_at_epoch_ms=ts,
                )

            result = get_fn(attempt_ref.attempt_id, attempt_ref.version)
            if result is None:
                return WbcBoundaryEvidence.indeterminate(
                    attempt_ref,
                    diagnostics=(f"no result for {attempt_ref.attempt_id} @ {attempt_ref.version}",),
                    observed_at_epoch_ms=ts,
                )

            # If result is already WbcBoundaryEvidence, return it
            if isinstance(result, WbcBoundaryEvidence):
                return result

            # If result has status/start_event/terminal_event attributes, convert
            if hasattr(result, "status"):
                status_str = str(getattr(result, "status", ""))
                if status_str == "verified":
                    return WbcBoundaryEvidence.verified(
                        attempt_ref,
                        start_event_digest=str(getattr(result, "start_event_digest", "")),
                        terminal_event_digest=str(getattr(result, "terminal_event_digest", "")),
                        last_sequence=int(getattr(result, "last_sequence", 0)),
                        source_cursor_digest=str(getattr(result, "source_cursor_digest", "")),
                        observed_at_epoch_ms=ts,
                    )
                elif status_str == "incomplete":
                    return WbcBoundaryEvidence.incomplete(
                        attempt_ref,
                        diagnostics=(str(getattr(result, "diagnostics", "")),),
                        observed_at_epoch_ms=ts,
                    )
                elif status_str == "incoherent":
                    return WbcBoundaryEvidence.incoherent(
                        attempt_ref,
                        diagnostics=(str(getattr(result, "diagnostics", "")),),
                        observed_at_epoch_ms=ts,
                    )
                else:
                    return WbcBoundaryEvidence.indeterminate(
                        attempt_ref,
                        diagnostics=(f"unknown status: {status_str}",),
                        observed_at_epoch_ms=ts,
                    )

            # Fallback: indeterminate
            return WbcBoundaryEvidence.indeterminate(
                attempt_ref,
                diagnostics=("unexpected result type from store",),
                observed_at_epoch_ms=ts,
            )

        except Exception as exc:
            return WbcBoundaryEvidence.indeterminate(
                attempt_ref,
                diagnostics=(f"store query failed: {exc}",),
                observed_at_epoch_ms=ts,
            )

    return WbcAdapter(
        query_fn=_store_query,
        default_freshness_window_ms=freshness_window_ms,
    )


__all__ = [
    # ── Types ──
    "WbcAdapterStatus",
    "WbcAttemptRef",
    "WbcBoundaryEvidence",
    "WbcQueryFn",
    # ── Adapters ──
    "WbcAdapter",
    "WbcCompositeAdapter",
    "NOOP_WBC_ADAPTER",
    # ── Convenience ──
    "wbc_cursor_from_adapter",
    "make_wbc_adapter_from_store",
]
