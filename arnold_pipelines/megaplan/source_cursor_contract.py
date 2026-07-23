"""Shared source-cursor vector contract for M9 rebuildable projections.

This module defines the typed schema contract that all projection producers
and consumers depend on.  Every projection carries a source-cursor vector
that describes *which source records* were observed and *how fresh* each
dimension was at read time.

The contract is explicitly non-authoritative.  Projections may deny, block,
diagnose, emit drift, or surface uncertainty, but they are never bearer
authority for dispatch, repair, retry, completion, cancellation, publication,
or delivery.

Design rules
------------
* Cursor states are exactly ``fresh``, ``stale``, ``unknown``, or
  ``incoherent`` — never collapsed to optimistic labels.
* Each covered dimension (lifecycle, WBC, custody, Run Authority,
  work-ledger, process-correlation) carries its own version and state.
* ``incoherent`` is reserved for contradictory source evidence (e.g. two
  custody records claiming the same epoch).
* ``unknown`` means the dimension could not be read (missing adapter,
  permission, persistence gap) — it is never defaulted to fresh or stale.
* The vector carries exact version identifiers (hashes, epochs, ledger
  positions) so consumers can detect drift without re-reading.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, ClassVar, Dict, FrozenSet, Literal, Mapping, Optional, Tuple

# ── Cursor state literals ────────────────────────────────────────────────

SourceCursorState = Literal["fresh", "stale", "unknown", "incoherent"]
"""Typed cursor state for a single source dimension.

``fresh``
    The source record was read within the freshness window and its version
    matches the current projection.

``stale``
    The source record exists but its version is behind current (a newer
    source write has been observed or the freshness window has expired).

``unknown``
    The dimension could not be read (missing adapter, permission gap,
    persistence gap, or adapter reports indeterminate).  This is never
    defaulted to fresh or stale.

``incoherent``
    Contradictory source evidence was observed (e.g. two custody records
    claiming the same epoch, or a WBC receipt that conflicts with a
    grant).  The projection cannot resolve the conflict.
"""

SOURCE_CURSOR_STATES: FrozenSet[SourceCursorState] = frozenset(
    {"fresh", "stale", "unknown", "incoherent"}
)

# ── Covered dimensions ───────────────────────────────────────────────────

SourceCursorDimension = Literal[
    "lifecycle",
    "wbc",
    "custody",
    "run_authority",
    "work_ledger",
    "process_correlation",
]
"""Named dimensions covered by the source-cursor vector.

``lifecycle``
    Plan / chain / task lifecycle state from the canonical lifecycle
    store (state.json, finalize.json, phase_result.json).  The version
    identifier is typically a content hash of the lifecycle record.

``wbc``
    Workflow-Based Custody attempt ledger and boundary evidence.  The
    version identifier is the WBC attempt reference + sequence number.

``custody``
    Custody lease records (acquire, renew, transfer, release, expire,
    fence).  The version identifier is the custody epoch + lease digest.

``run_authority``
    Run Authority grant and coordinator fence.  The version identifier
    is the grant_id + fence_token pair.

``work_ledger``
    Append-only work-ledger events.  The version identifier is the
    ledger position (event count) + last event_id.

``process_correlation``
    Normalized process/tmux/heartbeat identity tuples.  The version
    identifier is the (host, pid, boot_id) triple + heartbeat sequence.
"""

SOURCE_CURSOR_DIMENSIONS: FrozenSet[SourceCursorDimension] = frozenset(
    {"lifecycle", "wbc", "custody", "run_authority", "work_ledger", "process_correlation"}
)

# Ordered for deterministic serialisation
_SORTED_DIMENSIONS: Tuple[SourceCursorDimension, ...] = (
    "lifecycle",
    "wbc",
    "custody",
    "run_authority",
    "work_ledger",
    "process_correlation",
)


# ── Per-dimension cursor entry ───────────────────────────────────────────


@dataclass(frozen=True)
class DimensionCursor:
    """Cursor state and version for a single source dimension.

    This is the atomic unit of the source-cursor vector.  Every dimension
    carries its own state and version so that consumers can independently
    assess freshness without collapsing dimensions together.
    """

    dimension: SourceCursorDimension
    """Which dimension this entry covers."""

    state: SourceCursorState
    """Cursor state: fresh, stale, unknown, or incoherent."""

    version: str
    """Exact version identifier for this dimension at read time.

    The format is dimension-specific:
    - lifecycle: ``sha256:<content_hash>``
    - wbc: ``<attempt_ref>:<seq>``
    - custody: ``<lease_epoch>:<lease_digest>``
    - run_authority: ``<grant_id>:<fence_token>``
    - work_ledger: ``<event_count>:<last_event_id>``
    - process_correlation: ``<host>:<pid>:<boot_id>:<heartbeat_seq>``

    Empty string when state is ``unknown`` or ``incoherent``.
    """

    observed_at: str
    """ISO-8601 timestamp when this dimension was read from source."""

    freshness_window_ms: Optional[int] = None
    """Maximum age in milliseconds before this entry becomes stale.
    None when the dimension has no configured freshness SLO."""

    detail: str = ""
    """Human-readable detail for diagnostics.
    E.g. ``\"stale: 120s behind current\"`` or ``\"unknown: adapter unavailable\"``."""

    evidence_id: str = ""
    """Content-addressed evidence identifier for this cursor entry.
    Computed as sha256 over (dimension, state, version) — source facts only.
    Wall-clock ``observed_at`` is excluded so that repeated reads of unchanged
    evidence produce identical evidence_ids and vector_ids."""

    def __post_init__(self) -> None:
        if self.state not in SOURCE_CURSOR_STATES:
            raise ValueError(
                f"Invalid cursor state {self.state!r}; must be one of "
                f"{sorted(SOURCE_CURSOR_STATES)}"
            )
        if self.dimension not in SOURCE_CURSOR_DIMENSIONS:
            raise ValueError(
                f"Invalid dimension {self.dimension!r}; must be one of "
                f"{sorted(SOURCE_CURSOR_DIMENSIONS)}"
            )
        if not isinstance(self.version, str):
            object.__setattr__(self, "version", "")
        if not isinstance(self.detail, str):
            object.__setattr__(self, "detail", "")
        # Compute evidence_id if not provided — observed_at excluded for stability
        if not self.evidence_id:
            raw = f"{self.dimension}\x00{self.state}\x00{self.version}"
            digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
            object.__setattr__(self, "evidence_id", f"sha256:{digest}")

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a plain dict for JSON output."""
        result: Dict[str, Any] = {
            "dimension": self.dimension,
            "state": self.state,
            "version": self.version,
            "observed_at": self.observed_at,
            "evidence_id": self.evidence_id,
        }
        if self.freshness_window_ms is not None:
            result["freshness_window_ms"] = self.freshness_window_ms
        if self.detail:
            result["detail"] = self.detail
        return result

    @classmethod
    def fresh(
        cls,
        dimension: SourceCursorDimension,
        version: str,
        observed_at: str,
        *,
        freshness_window_ms: Optional[int] = None,
        detail: str = "",
    ) -> "DimensionCursor":
        """Create a fresh cursor entry."""
        return cls(
            dimension=dimension,
            state="fresh",
            version=version,
            observed_at=observed_at,
            freshness_window_ms=freshness_window_ms,
            detail=detail,
        )

    @classmethod
    def stale(
        cls,
        dimension: SourceCursorDimension,
        version: str,
        observed_at: str,
        *,
        freshness_window_ms: Optional[int] = None,
        detail: str = "",
    ) -> "DimensionCursor":
        """Create a stale cursor entry."""
        return cls(
            dimension=dimension,
            state="stale",
            version=version,
            observed_at=observed_at,
            freshness_window_ms=freshness_window_ms,
            detail=detail,
        )

    @classmethod
    def unknown(
        cls,
        dimension: SourceCursorDimension,
        *,
        observed_at: str = "",
        detail: str = "",
    ) -> "DimensionCursor":
        """Create an unknown cursor entry."""
        return cls(
            dimension=dimension,
            state="unknown",
            version="",
            observed_at=observed_at,
            freshness_window_ms=None,
            detail=detail,
        )

    @classmethod
    def incoherent(
        cls,
        dimension: SourceCursorDimension,
        *,
        observed_at: str = "",
        detail: str = "",
    ) -> "DimensionCursor":
        """Create an incoherent cursor entry."""
        return cls(
            dimension=dimension,
            state="incoherent",
            version="",
            observed_at=observed_at,
            freshness_window_ms=None,
            detail=detail,
        )


# ── Source-cursor vector ─────────────────────────────────────────────────

SCHEMA_VERSION = 1
"""Canonical schema version for the source-cursor vector contract."""


@dataclass(frozen=True)
class SourceCursorVector:
    """The full source-cursor vector carried by every M9 projection.

    A projection's source-cursor vector describes which source records were
    observed and how fresh each dimension was at read time.  Consumers use
    this vector to:

    * Detect drift between their own read and the projection's read.
    * Decide whether to block, deny, or diagnose based on staleness.
    * Fulfill positive-control-path reread obligations by comparing
      their fresher source read against the projection's cursor.

    The vector is **non-authoritative** — it is evidence, not a grant.
    Projections carry this metadata so consumers can make informed
    decisions without the vector itself becoming bearer authority.
    """

    contract_type: ClassVar[str] = "source_cursor_vector"
    schema_version: ClassVar[int] = SCHEMA_VERSION

    cursors: Tuple[DimensionCursor, ...]
    """One cursor entry per covered dimension, in deterministic order."""

    vector_id: str = field(init=False)
    """Content-addressed identifier for the entire vector.
    Computed as sha256 over all cursor evidence_ids in order."""

    _non_authoritative: bool = field(default=True, init=False)
    """Always True — this vector is evidence, never authority."""

    def __post_init__(self) -> None:
        # Ensure cursors are sorted deterministically
        sorted_cursors = tuple(
            sorted(self.cursors, key=lambda c: _SORTED_DIMENSIONS.index(c.dimension))
        )
        object.__setattr__(self, "cursors", sorted_cursors)

        # Compute vector_id from cursor evidence_ids
        raw = "\x00".join(c.evidence_id for c in sorted_cursors)
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        object.__setattr__(self, "vector_id", f"sha256:{digest}")

        # Enforce _non_authoritative
        object.__setattr__(self, "_non_authoritative", True)

    def cursor(self, dimension: SourceCursorDimension) -> Optional[DimensionCursor]:
        """Return the cursor entry for a specific dimension, or None."""
        for c in self.cursors:
            if c.dimension == dimension:
                return c
        return None

    def has_any_stale_or_worse(self) -> bool:
        """True when any dimension is stale, unknown, or incoherent."""
        return any(c.state != "fresh" for c in self.cursors)

    def stale_dimensions(self) -> Tuple[SourceCursorDimension, ...]:
        """Return dimensions that are stale, unknown, or incoherent."""
        return tuple(c.dimension for c in self.cursors if c.state != "fresh")

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a plain dict for JSON output."""
        return {
            "contract_type": self.contract_type,
            "schema_version": self.schema_version,
            "vector_id": self.vector_id,
            "cursors": [c.to_dict() for c in self.cursors],
            "_non_authoritative": self._non_authoritative,
        }

    @classmethod
    def from_cursors(cls, *cursors: DimensionCursor) -> "SourceCursorVector":
        """Build a vector from cursor entries (order is normalised)."""
        return cls(cursors=tuple(cursors))

    @classmethod
    def all_unknown(cls, observed_at: str = "") -> "SourceCursorVector":
        """Build a vector where every dimension is unknown."""
        return cls(
            cursors=tuple(
                DimensionCursor.unknown(dim, observed_at=observed_at)
                for dim in _SORTED_DIMENSIONS
            )
        )


# ── Normalisation helpers ────────────────────────────────────────────────


def normalize_dimension_cursor(
    payload: Mapping[str, Any] | None,
) -> DimensionCursor | None:
    """Return a canonical DimensionCursor or None for invalid inputs."""
    if not isinstance(payload, Mapping):
        return None
    try:
        dim_raw = payload.get("dimension", "")
        state_raw = payload.get("state", "")
        if dim_raw not in SOURCE_CURSOR_DIMENSIONS:
            return None
        if state_raw not in SOURCE_CURSOR_STATES:
            return None
        return DimensionCursor(
            dimension=dim_raw,  # type: ignore[arg-type]
            state=state_raw,  # type: ignore[arg-type]
            version=str(payload.get("version", "")),
            observed_at=str(payload.get("observed_at", "")),
            freshness_window_ms=payload.get("freshness_window_ms"),
            detail=str(payload.get("detail", "")),
            evidence_id=str(payload.get("evidence_id", "")),
        )
    except (ValueError, TypeError):
        return None


def normalize_source_cursor_vector(
    payload: Mapping[str, Any] | None,
) -> SourceCursorVector | None:
    """Return a canonical SourceCursorVector or None for invalid inputs."""
    if not isinstance(payload, Mapping):
        return None
    cursors_raw = payload.get("cursors")
    if not isinstance(cursors_raw, (list, tuple)):
        return None
    cursors: list[DimensionCursor] = []
    for entry in cursors_raw:
        c = normalize_dimension_cursor(entry)
        if c is None:
            return None
        cursors.append(c)
    if not cursors:
        return None
    try:
        return SourceCursorVector(cursors=tuple(cursors))
    except (ValueError, TypeError):
        return None


def source_cursor_vector_digest(vector: SourceCursorVector) -> str:
    """Return the deterministic vector_id for a SourceCursorVector."""
    return vector.vector_id


# ── Convenience builders ─────────────────────────────────────────────────


def build_all_fresh_vector(
    *,
    lifecycle_version: str = "",
    wbc_version: str = "",
    custody_version: str = "",
    run_authority_version: str = "",
    work_ledger_version: str = "",
    process_correlation_version: str = "",
    observed_at: str = "",
) -> SourceCursorVector:
    """Build a source-cursor vector where every dimension is fresh.

    Each dimension version must be provided explicitly.  An empty version
    string is accepted but makes the cursor entry non-verifiable.
    """
    return SourceCursorVector(
        cursors=(
            DimensionCursor.fresh("lifecycle", lifecycle_version, observed_at),
            DimensionCursor.fresh("wbc", wbc_version, observed_at),
            DimensionCursor.fresh("custody", custody_version, observed_at),
            DimensionCursor.fresh("run_authority", run_authority_version, observed_at),
            DimensionCursor.fresh("work_ledger", work_ledger_version, observed_at),
            DimensionCursor.fresh(
                "process_correlation", process_correlation_version, observed_at
            ),
        )
    )


__all__ = [
    # ── Type literals ──
    "SourceCursorState",
    "SourceCursorDimension",
    "SOURCE_CURSOR_STATES",
    "SOURCE_CURSOR_DIMENSIONS",
    # ── Contract dataclasses ──
    "DimensionCursor",
    "SourceCursorVector",
    # ── Schema constants ──
    "SCHEMA_VERSION",
    # ── Normalisation ──
    "normalize_dimension_cursor",
    "normalize_source_cursor_vector",
    # ── Helpers ──
    "source_cursor_vector_digest",
    "build_all_fresh_vector",
]
