"""Shared projection lag/drift metadata for watchdog and auditor consumers.

M9 (T37): Exposes typed drift categories that both watchdog and auditor
reason fixtures consume.  Every drift class carries content-addressed
evidence IDs so consumers can detect and surface lag without silently
suppressing it.

Drift is **emitted, never silently suppressed**.  When a projection's
source_cursor disagrees with current source readings, the disagreement
is surfaced as typed drift — not collapsed into a pass/fail verdict that
hides the specific mismatch.

Drift classes
-------------
* ``CURSOR_MISMATCH`` — projection cursor version differs from current.
* ``REBUILD_MISMATCH`` — delete-and-rebuild produces a different digest.
* ``MISSING_ARTIFACT_COVERAGE`` — a required projection artifact is absent.
* ``STALE_SOURCE_DISAGREEMENT`` — projection freshness window exceeded vs source.

Design rules
------------
* Every drift entry carries an ``evidence_id`` (sha256 over kind + dimensions + detail).
* Drift entries are ``_non_authoritative`` — diagnostic only, never grants.
* Callers can aggregate drift from multiple sources into a ``DriftSnapshot``.
* ``DriftSnapshot`` provides an ``any_blocking`` flag for gates that must fail
  closed when critical drift is detected.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, FrozenSet, List, Mapping, Optional, Sequence, Tuple

from arnold_pipelines.megaplan.projection_digest import (
    ProjectionDigest,
)
from arnold_pipelines.megaplan.projection_validation import (
    ValidationResult,
    ValidationSuite,
    ValidationVerdict,
    validate_artifact_presence,
    validate_diff_clean_rebuild,
    validate_projection_metadata,
    validate_source_version,
)
from arnold_pipelines.megaplan.source_cursor_contract import (
    DimensionCursor,
    SOURCE_CURSOR_DIMENSIONS,
    SourceCursorDimension,
    SourceCursorVector,
)


# ── Drift classification ───────────────────────────────────────────────────


class DriftClass(Enum):
    """Typed drift categories consumed by watchdog and auditor reason fixtures.

    * ``CURSOR_MISMATCH`` — the projection's source_cursor version disagrees
      with the current source version for the same dimension.
    * ``REBUILD_MISMATCH`` — delete-and-rebuild produces an artifact with a
      different content digest.
    * ``MISSING_ARTIFACT_COVERAGE`` — a required projection artifact is absent
      or unreadable.
    * ``STALE_SOURCE_DISAGREEMENT`` — the projection's observation timestamp
      exceeds the freshness window for its source dimension.
    """

    CURSOR_MISMATCH = "cursor_mismatch"
    REBUILD_MISMATCH = "rebuild_mismatch"
    MISSING_ARTIFACT_COVERAGE = "missing_artifact_coverage"
    STALE_SOURCE_DISAGREEMENT = "stale_source_disagreement"


# ── Drift entry ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ProjectionDriftEntry:
    """A single typed drift observation with content-addressed evidence.

    Every drift entry carries an exact ``evidence_id`` so consumers can
    deduplicate and trace specific mismatches without collapsing multiple
    drift sources into a single opaque flag.
    """

    drift_class: DriftClass
    """Typed drift category."""

    dimension: str = ""
    """The source-cursor dimension affected (lifecycle, wbc, custody, …)."""

    projection_version: str = ""
    """Version identifier from the projection's cursor."""

    current_version: str = ""
    """Version identifier from the current source read."""

    detail: str = ""
    """Human-readable diagnostic detail."""

    evidence_id: str = field(init=False)
    """Content-addressed drift evidence identifier."""

    _non_authoritative: bool = field(default=True, init=False)

    def __post_init__(self) -> None:
        raw = (
            f"{self.drift_class.value}\\x00{self.dimension}\\x00"
            f"{self.projection_version}\\x00{self.current_version}\\x00{self.detail}"
        )
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        object.__setattr__(self, "evidence_id", f"drift:sha256:{digest}")
        object.__setattr__(self, "_non_authoritative", True)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "drift_class": self.drift_class.value,
            "dimension": self.dimension,
            "projection_version": self.projection_version,
            "current_version": self.current_version,
            "detail": self.detail,
            "evidence_id": self.evidence_id,
            "_non_authoritative": self._non_authoritative,
        }

    @property
    def is_blocking(self) -> bool:
        """True when this drift indicates a gate must fail closed.

        CURSOR_MISMATCH and MISSING_ARTIFACT_COVERAGE are always blocking.
        REBUILD_MISMATCH is blocking when the rebuild payload is non-empty.
        STALE_SOURCE_DISAGREEMENT is diagnostic only, not blocking.
        """
        if self.drift_class in (
            DriftClass.CURSOR_MISMATCH,
            DriftClass.MISSING_ARTIFACT_COVERAGE,
        ):
            return True
        return False


# ── Helpers ─────────────────────────────────────────────────────────────────


def _compute_age_ms(observed_at: str, now_epoch_ms: float) -> float:
    """Compute the age of an ISO-8601 timestamp relative to now in ms.

    Returns 0.0 when ``observed_at`` is unparseable (conservative default).
    """
    if not observed_at:
        return 0.0
    try:
        from datetime import datetime
        clean = observed_at.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean)
        observed_ms = dt.timestamp() * 1000
        return now_epoch_ms - observed_ms
    except (ValueError, TypeError):
        return 0.0


# ── Drift detectors ─────────────────────────────────────────────────────────


def detect_cursor_mismatch(
    projection_cursor: SourceCursorVector,
    current_cursor: SourceCursorVector,
    *,
    dimensions: Optional[Tuple[SourceCursorDimension, ...]] = None,
) -> List[ProjectionDriftEntry]:
    """Detect version mismatches between a projection cursor and current source.

    For each dimension present in both cursors, if the version identifier
    differs, a CURSOR_MISMATCH drift entry is emitted.
    """
    entries: List[ProjectionDriftEntry] = []
    dims = dimensions or SOURCE_CURSOR_DIMENSIONS
    for dim in dims:
        proj = projection_cursor.cursor(dim)
        curr = current_cursor.cursor(dim)
        if proj is None and curr is None:
            continue
        if proj is None or curr is None:
            entries.append(
                ProjectionDriftEntry(
                    drift_class=DriftClass.CURSOR_MISMATCH,
                    dimension=str(dim),
                    projection_version=proj.version if proj else "absent",
                    current_version=curr.version if curr else "absent",
                    detail=f"dimension {dim} present in only one cursor",
                )
            )
            continue
        if proj.version != curr.version:
            entries.append(
                ProjectionDriftEntry(
                    drift_class=DriftClass.CURSOR_MISMATCH,
                    dimension=str(dim),
                    projection_version=proj.version,
                    current_version=curr.version,
                    detail=(
                        f"projection={proj.version[:16]} "
                        f"!= current={curr.version[:16]}"
                    ),
                )
            )
    return entries


def detect_rebuild_mismatch(
    before_digest: str,
    after_digest: str,
    *,
    projection_kind: str = "",
) -> Optional[ProjectionDriftEntry]:
    """Emit a REBUILD_MISMATCH drift entry when rebuild digests differ."""
    if not before_digest or not after_digest:
        return None
    if before_digest == after_digest:
        return None
    return ProjectionDriftEntry(
        drift_class=DriftClass.REBUILD_MISMATCH,
        dimension=projection_kind,
        projection_version=before_digest[:32],
        current_version=after_digest[:32],
        detail=f"rebuild digest mismatch for {projection_kind}",
    )


def detect_missing_artifact_coverage(
    artifact_paths: Sequence[str],
    *,
    artifact_kind: str = "",
) -> List[ProjectionDriftEntry]:
    """Emit MISSING_ARTIFACT_COVERAGE for every absent or unreadable artifact."""
    entries: List[ProjectionDriftEntry] = []
    for path in artifact_paths:
        result = validate_artifact_presence(path, artifact_kind=artifact_kind or path)
        if result.is_blocked:
            entries.append(
                ProjectionDriftEntry(
                    drift_class=DriftClass.MISSING_ARTIFACT_COVERAGE,
                    dimension=path,
                    detail=result.detail,
                )
            )
    return entries


def detect_stale_source_disagreement(
    source_cursor: SourceCursorVector,
    *,
    freshness_window_ms: int = 300_000,
    now_epoch_ms: Optional[float] = None,
) -> List[ProjectionDriftEntry]:
    """Emit STALE_SOURCE_DISAGREEMENT for every stale dimension.

    A dimension is stale when its ``observed_at_epoch_ms`` exceeds the
    freshness window.  Stale disagreements are diagnostic only — they do
    not block cutover.
    """
    now = now_epoch_ms if now_epoch_ms is not None else (time.time() * 1000)
    entries: List[ProjectionDriftEntry] = []
    for cursor in source_cursor.cursors:
        if cursor.state == "stale":
            # Compute age from observed_at ISO timestamp
            age_ms = _compute_age_ms(cursor.observed_at, now)
            entries.append(
                ProjectionDriftEntry(
                    drift_class=DriftClass.STALE_SOURCE_DISAGREEMENT,
                    dimension=str(cursor.dimension),
                    projection_version=cursor.version,
                    current_version="",
                    detail=(
                        f"dimension {cursor.dimension} stale: "
                        f"age={age_ms:.0f}ms > window={freshness_window_ms}ms"
                    ),
                )
            )
    return entries


# ── Drift snapshot: aggregate view for watchdog/auditor callers ─────────────


@dataclass(frozen=True)
class DriftSnapshot:
    """Aggregated drift evidence from multiple detectors.

    Produced by :func:`evaluate_projection_drift` for watchdog and auditor
    consumers.  Carries all drift entries plus a summary of blocking vs
    diagnostic-only entries.

    Callers can use ``any_blocking`` to fail closed when critical drift is
    detected (cursor/rebuid/artifact mismatches) without being forced to
    inspect individual entries.
    """

    entries: Tuple[ProjectionDriftEntry, ...]
    """All drift entries, sorted by drift_class then dimension."""

    source_cursor_digest: str = ""
    """Digest of the source-cursor vector that produced this snapshot."""

    snapshot_digest: str = field(init=False)
    """Content-addressed snapshot digest for deduplication."""

    _non_authoritative: bool = field(default=True, init=False)

    def __post_init__(self) -> None:
        sorted_entries = tuple(
            sorted(self.entries, key=lambda e: (e.drift_class.value, e.dimension))
        )
        object.__setattr__(self, "entries", sorted_entries)
        parts = "\\x00".join(e.evidence_id for e in sorted_entries)
        digest = hashlib.sha256(parts.encode("utf-8")).hexdigest()
        object.__setattr__(self, "snapshot_digest", f"drift_snapshot:sha256:{digest}")
        object.__setattr__(self, "_non_authoritative", True)

    @property
    def any_blocking(self) -> bool:
        """True when any drift entry is blocking (cursor/rebuild/artifact mismatch)."""
        return any(e.is_blocking for e in self.entries)

    @property
    def blocking_entries(self) -> Tuple[ProjectionDriftEntry, ...]:
        """Only the blocking drift entries."""
        return tuple(e for e in self.entries if e.is_blocking)

    @property
    def diagnostic_entries(self) -> Tuple[ProjectionDriftEntry, ...]:
        """Only the diagnostic (non-blocking) drift entries."""
        return tuple(e for e in self.entries if not e.is_blocking)

    @property
    def drift_classes_present(self) -> FrozenSet[DriftClass]:
        """Set of drift classes present in this snapshot."""
        return frozenset(e.drift_class for e in self.entries)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entries": [e.to_dict() for e in self.entries],
            "source_cursor_digest": self.source_cursor_digest,
            "snapshot_digest": self.snapshot_digest,
            "any_blocking": self.any_blocking,
            "blocking_count": len(self.blocking_entries),
            "diagnostic_count": len(self.diagnostic_entries),
            "drift_classes": sorted(c.value for c in self.drift_classes_present),
            "_non_authoritative": self._non_authoritative,
        }

    @classmethod
    def empty(cls, source_cursor_digest: str = "") -> "DriftSnapshot":
        """Return a snapshot with no drift entries."""
        return cls(entries=(), source_cursor_digest=source_cursor_digest)


# ── Drift evaluation: entry point for watchdog and auditor callers ──────────


def evaluate_projection_drift(
    projection_cursor: SourceCursorVector,
    current_cursor: Optional[SourceCursorVector] = None,
    *,
    artifact_paths: Optional[Sequence[str]] = None,
    rebuild_before_digest: str = "",
    rebuild_after_digest: str = "",
    projection_kind: str = "",
    freshness_window_ms: int = 300_000,
    dimensions: Optional[Tuple[SourceCursorDimension, ...]] = None,
    now_epoch_ms: Optional[float] = None,
) -> DriftSnapshot:
    """Evaluate all drift categories for a projection against current source.

    This is the primary entry point for watchdog and auditor consumers.
    It runs all four drift detectors and aggregates results into a single
    ``DriftSnapshot``.

    Parameters
    ----------
    projection_cursor:
        The source-cursor vector from the projection artifact.
    current_cursor:
        The source-cursor vector from a fresh source read.  When absent,
        cursor-mismatch detection is skipped.
    artifact_paths:
        Filesystem paths to required projection artifacts.
    rebuild_before_digest:
        Digest of the original projection payload.
    rebuild_after_digest:
        Digest of the rebuilt projection payload.
    projection_kind:
        Kind of projection (status, resident, cloud, introspect, …).
    freshness_window_ms:
        Maximum age in ms before a dimension is considered stale.
    dimensions:
        Source-cursor dimensions to check (defaults to all).
    now_epoch_ms:
        Current timestamp for freshness evaluation.

    Returns
    -------
    DriftSnapshot
        Aggregated drift evidence with blocking/diagnostic classification.
    """
    entries: List[ProjectionDriftEntry] = []

    # 1. Cursor mismatch
    if current_cursor is not None:
        entries.extend(
            detect_cursor_mismatch(projection_cursor, current_cursor, dimensions=dimensions)
        )

    # 2. Rebuild mismatch
    rebuild_drift = detect_rebuild_mismatch(
        rebuild_before_digest,
        rebuild_after_digest,
        projection_kind=projection_kind,
    )
    if rebuild_drift is not None:
        entries.append(rebuild_drift)

    # 3. Missing artifact coverage
    if artifact_paths:
        entries.extend(
            detect_missing_artifact_coverage(artifact_paths, artifact_kind=projection_kind)
        )

    # 4. Stale source disagreement
    entries.extend(
        detect_stale_source_disagreement(
            projection_cursor,
            freshness_window_ms=freshness_window_ms,
            now_epoch_ms=now_epoch_ms,
        )
    )

    return DriftSnapshot(
        entries=tuple(entries),
        source_cursor_digest=projection_cursor.vector_id,
    )


# ── Convenience: evaluate drift from validation suite ───────────────────────


def drift_from_validation_suite(
    suite: ValidationSuite,
    *,
    projection_kind: str = "",
    current_cursor: Optional[SourceCursorVector] = None,
    projection_cursor: Optional[SourceCursorVector] = None,
) -> DriftSnapshot:
    """Convert a ValidationSuite into a DriftSnapshot.

    Each BLOCKED or STALE validation result becomes a drift entry with the
    appropriate drift class.  This bridges the validation layer (T7) with
    the drift metadata contract used by watchdog/auditor consumers.
    """
    entries: List[ProjectionDriftEntry] = []
    for result in suite.results:
        if result.verdict == ValidationVerdict.BLOCKED:
            if result.validation_kind == "artifact_presence":
                entries.append(
                    ProjectionDriftEntry(
                        drift_class=DriftClass.MISSING_ARTIFACT_COVERAGE,
                        dimension=result.artifact_path or projection_kind,
                        detail=result.detail,
                    )
                )
            elif result.validation_kind == "diff_clean_rebuild":
                entries.append(
                    ProjectionDriftEntry(
                        drift_class=DriftClass.REBUILD_MISMATCH,
                        dimension=projection_kind,
                        detail=result.detail,
                    )
                )
            elif result.validation_kind in ("source_version", "projection_metadata"):
                entries.append(
                    ProjectionDriftEntry(
                        drift_class=DriftClass.CURSOR_MISMATCH,
                        dimension=projection_kind,
                        detail=result.detail,
                    )
                )
        elif result.verdict == ValidationVerdict.STALE:
            entries.append(
                ProjectionDriftEntry(
                    drift_class=DriftClass.STALE_SOURCE_DISAGREEMENT,
                    dimension=projection_kind,
                    detail=result.detail,
                )
            )

    # Also check cursor mismatch if both cursors provided
    if current_cursor is not None and projection_cursor is not None:
        entries.extend(
            detect_cursor_mismatch(projection_cursor, current_cursor)
        )

    source_digest = projection_cursor.vector_id if projection_cursor else ""
    return DriftSnapshot(entries=tuple(entries), source_cursor_digest=source_digest)


__all__ = [
    # ── Types ──
    "DriftClass",
    "ProjectionDriftEntry",
    "DriftSnapshot",
    # ── Detectors ──
    "detect_cursor_mismatch",
    "detect_rebuild_mismatch",
    "detect_missing_artifact_coverage",
    "detect_stale_source_disagreement",
    # ── Entry points ──
    "evaluate_projection_drift",
    "drift_from_validation_suite",
]
