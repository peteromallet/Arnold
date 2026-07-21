"""Projection rebuild registry with source cursor vectors and ordered view digesting.

Provides a registry for in-scope projection builders, source cursor vectors
that capture the state of all underlying evidence, ordered view digesting for
deterministic comparison, and delete/rebuild comparison that **never mutates
source evidence**.

The registry crosses multiple projection families (custody, observability,
incident) and creates the common proof mechanism for rebuild parity.  It
reuses reducer (fold/accumulate) patterns from incident and observability
event projections, but stays read-only with respect to source evidence —
every builder receives source records as input rather than reaching into
the source ledger itself.

Design rules
------------

* **Never mutates source evidence** — every registered builder is a pure
  function of the source records it receives.  The registry itself performs
  no writes to source paths.
* **Deterministic ordered-view digest** — ``compute_projection_digest()``
  produces a stable SHA-256 digest over the canonical JSON representation of
  a projection view, enabling byte-for-byte comparison.
* **Source cursor vectors** — ``capture_source_cursor_vector()`` computes a
  ``ProjectionCursor`` for every registered source path, producing a
  snapshot of all evidence at rebuild time.
* **Delete/rebuild comparison** — ``compare_rebuild()`` rebuilds a projection
  from source records, discards any stale cached output, and compares the
  ordered-view digest of the rebuild against the current stored projection,
  returning a parity report without touching source data.

Usage::

    from arnold_pipelines.megaplan.observability.projection_rebuild import (
        ProjectionRegistry,
        capture_source_cursor_vector,
        compute_projection_digest,
        compare_rebuild,
        rebuild_projection,
    )

    registry = ProjectionRegistry()
    registry.register("custody", build_custody_projection, source_path=Path("..."))

    report = compare_rebuild(registry, "custody", source_records)
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional, Sequence, Tuple

from arnold_pipelines.megaplan._core.io import (
    ProjectionCursor,
    _projection_canonical_dumps,
    _projection_cursor_from_path,
    now_utc,
)


# ── Types ──────────────────────────────────────────────────────────────────

#: A projection builder is a pure function that takes source records (as a
#: sequence of dicts read from the source ledger) and returns a projection
#: view dict.  It MUST NOT mutate its input.
ProjectionBuilderFn = Callable[[Sequence[Mapping[str, Any]]], Dict[str, Any]]

#: A source-record loader is a callable that returns the raw source records
#: from a given path.  Separated so tests can inject mock records without
#: touching the filesystem.
SourceLoaderFn = Callable[[Path], Sequence[Mapping[str, Any]]]


# ── Registry entry ─────────────────────────────────────────────────────────


@dataclass
class _RegistryEntry:
    """Internal registry bookkeeping for one registered projection."""

    projection_id: str
    builder: ProjectionBuilderFn
    source_path: Path
    source_loader: SourceLoaderFn


# ── Projection registry ────────────────────────────────────────────────────


class ProjectionRegistry:
    """Registry of in-scope projection builders keyed by projection ID.

    Each entry maps a ``projection_id`` to a builder function, a source
    evidence path, and an optional custom source-record loader.  The registry
    is the central lookup for rebuild operations: clients ask it to rebuild a
    projection and it dispatches to the correct builder.

    Thread-safety: not guaranteed — callers should serialize registration
    (typically done once at module load) before any rebuilds are attempted.
    """

    def __init__(self) -> None:
        self._entries: Dict[str, _RegistryEntry] = {}

    # -- registration ---------------------------------------------------------

    def register(
        self,
        projection_id: str,
        builder: ProjectionBuilderFn,
        *,
        source_path: Path,
        source_loader: SourceLoaderFn | None = None,
    ) -> None:
        """Register a projection builder.

        Parameters
        ----------
        projection_id:
            Unique identifier for this projection (e.g. ``"custody"``,
            ``"observability"``, ``"incident"``).
        builder:
            Pure function ``(records) -> projection_view_dict``. Must be
            deterministic — given the same records it must produce the same
            view.
        source_path:
            Path to the accepted-source-record ledger that drives this
            projection.  Used for cursor computation.
        source_loader:
            Optional callable ``(path) -> list[dict]`` that loads raw source
            records.  When ``None``, a default JSONL loader is used that reads
            newline-delimited JSON records.

        Raises
        ------
        ValueError
            If *projection_id* is already registered.
        """
        if projection_id in self._entries:
            raise ValueError(
                f"Projection '{projection_id}' is already registered"
            )
        loader = source_loader or _default_jsonl_loader
        self._entries[projection_id] = _RegistryEntry(
            projection_id=projection_id,
            builder=builder,
            source_path=Path(source_path),
            source_loader=loader,
        )

    def unregister(self, projection_id: str) -> None:
        """Remove a previously registered projection (idempotent)."""
        self._entries.pop(projection_id, None)

    # -- queries --------------------------------------------------------------

    def is_registered(self, projection_id: str) -> bool:
        """Return ``True`` when *projection_id* has a registered builder."""
        return projection_id in self._entries

    def list_registered(self) -> Tuple[str, ...]:
        """Return the sorted tuple of registered projection IDs."""
        return tuple(sorted(self._entries.keys()))

    def source_path(self, projection_id: str) -> Path:
        """Return the source evidence path for *projection_id*.

        Raises
        ------
        KeyError
            If *projection_id* is not registered.
        """
        return self._entries[projection_id].source_path

    def builder(self, projection_id: str) -> ProjectionBuilderFn:
        """Return the builder function for *projection_id*.

        Raises
        ------
        KeyError
            If *projection_id* is not registered.
        """
        return self._entries[projection_id].builder

    def source_loader(self, projection_id: str) -> SourceLoaderFn:
        """Return the source-record loader for *projection_id*.

        Raises
        ------
        KeyError
            If *projection_id* is not registered.
        """
        return self._entries[projection_id].source_loader

    # -- rebuild operations ---------------------------------------------------

    def rebuild(
        self,
        projection_id: str,
        *,
        source_records: Sequence[Mapping[str, Any]] | None = None,
    ) -> Dict[str, Any]:
        """Rebuild a projection from source records via its registered builder.

        Parameters
        ----------
        projection_id:
            Which projection to rebuild.
        source_records:
            Pre-loaded source records.  When ``None``, records are loaded
            from the registered ``source_path``.

        Returns
        -------
        dict
            The rebuilt projection view dict.

        Raises
        ------
        KeyError
            If *projection_id* is not registered.
        """
        entry = self._entries[projection_id]
        if source_records is None:
            source_records = entry.source_loader(entry.source_path)
        return entry.builder(source_records)


# ── Source cursor vectors ──────────────────────────────────────────────────


def capture_source_cursor_vector(
    registry: ProjectionRegistry,
) -> Dict[str, ProjectionCursor]:
    """Compute a :class:`ProjectionCursor` for every registered source path.

    Returns a mapping ``{projection_id: ProjectionCursor}`` that captures
    the state of all source evidence at a point in time.  This vector can
    be stored alongside a rebuild report to prove which source state was
    used.

    This function is **read-only** — it computes cursors without touching
    source data.

    Parameters
    ----------
    registry:
        A populated :class:`ProjectionRegistry`.

    Returns
    -------
    dict
        ``{projection_id: ProjectionCursor}`` for every registered projection.
    """
    cursors: Dict[str, ProjectionCursor] = {}
    for pid in registry.list_registered():
        cursors[pid] = _projection_cursor_from_path(registry.source_path(pid))
    return cursors


# ── Ordered view digesting ─────────────────────────────────────────────────


def compute_projection_digest(projection_view: Mapping[str, Any]) -> str:
    """Compute a deterministic SHA-256 digest of a projection view.

    The digest is computed over the **canonical** (stable, sorted-key,
    no-whitespace) JSON representation of *projection_view*, making it
    byte-for-byte comparable across rebuilds.

    Parameters
    ----------
    projection_view:
        A projection view dict (as returned by a registered builder).

    Returns
    -------
    str
        ``"sha256:<hex>"`` digest string.
    """
    canonical = _projection_canonical_dumps(dict(projection_view))
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ── Delete / rebuild comparison ────────────────────────────────────────────


@dataclass(frozen=True)
class RebuildComparisonReport:
    """Result of a delete/rebuild comparison for one projection.

    Attributes
    ----------
    projection_id:
        The projection that was compared.
    parity:
        ``True`` when the rebuild digest equals the existing projection
        digest.
    rebuild_digest:
        SHA-256 digest of the freshly rebuilt projection view.
    existing_digest:
        SHA-256 digest of the currently stored projection view, or
        ``None`` when no existing view was available.
    source_cursor:
        ``ProjectionCursor`` capturing the source evidence state at rebuild
        time (or ``None`` when cursor computation was skipped).
    diagnostics:
        Human-readable diagnostic messages.
    """

    projection_id: str
    parity: bool
    rebuild_digest: str
    existing_digest: str | None
    source_cursor: ProjectionCursor | None
    diagnostics: Tuple[str, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "projection_id": self.projection_id,
            "parity": self.parity,
            "rebuild_digest": self.rebuild_digest,
        }
        if self.existing_digest is not None:
            result["existing_digest"] = self.existing_digest
        if self.source_cursor is not None:
            result["source_cursor"] = self.source_cursor.to_dict()
        if self.diagnostics:
            result["diagnostics"] = list(self.diagnostics)
        return result


def compare_rebuild(
    registry: ProjectionRegistry,
    projection_id: str,
    source_records: Sequence[Mapping[str, Any]] | None = None,
    *,
    existing_projection_view: Mapping[str, Any] | None = None,
) -> RebuildComparisonReport:
    """Rebuild a projection and compare its digest against the existing view.

    This is the primary proof mechanism for rebuild parity:

    1. Loads source records (or uses pre-loaded records).
    2. Rebuilds the projection via the registered builder.
    3. Computes the ordered-view digest of the rebuild.
    4. Compares against *existing_projection_view* digest.
    5. Returns a :class:`RebuildComparisonReport`.

    **Never mutates source evidence** — this function is read-only with
    respect to source paths.  Existing projection views are passed in rather
    than read from disk so the caller controls which view is compared.

    Parameters
    ----------
    registry:
        A populated :class:`ProjectionRegistry`.
    projection_id:
        Which projection to rebuild and compare.
    source_records:
        Pre-loaded source records (optional; loaded from registered source
        path when ``None``).
    existing_projection_view:
        The currently stored projection view to compare against.  When
        ``None``, no existing-digest comparison is performed (report will
        have ``existing_digest=None`` and ``parity=False``).

    Returns
    -------
    RebuildComparisonReport
        The comparison result with digests, parity flag, source cursor,
        and diagnostics.
    """
    diagnostics: list[str] = []
    entry = registry._entries.get(projection_id)
    if entry is None:
        return RebuildComparisonReport(
            projection_id=projection_id,
            parity=False,
            rebuild_digest="",
            existing_digest=None,
            source_cursor=None,
            diagnostics=(f"Projection '{projection_id}' is not registered.",),
        )

    # Load source records if not provided
    if source_records is None:
        try:
            source_records = entry.source_loader(entry.source_path)
        except (OSError, ValueError) as exc:
            diagnostics.append(f"Failed to load source records: {exc}")
            return RebuildComparisonReport(
                projection_id=projection_id,
                parity=False,
                rebuild_digest="",
                existing_digest=None,
                source_cursor=None,
                diagnostics=tuple(diagnostics),
            )

    # Compute source cursor (read-only)
    try:
        source_cursor = _projection_cursor_from_path(entry.source_path)
    except OSError as exc:
        diagnostics.append(f"Failed to compute source cursor: {exc}")
        source_cursor = None

    # Rebuild from source
    try:
        rebuilt_view = entry.builder(source_records)
    except Exception as exc:
        diagnostics.append(f"Builder raised {type(exc).__name__}: {exc}")
        return RebuildComparisonReport(
            projection_id=projection_id,
            parity=False,
            rebuild_digest="",
            existing_digest=None,
            source_cursor=source_cursor,
            diagnostics=tuple(diagnostics),
        )

    rebuild_digest = compute_projection_digest(rebuilt_view)

    # Compare
    if existing_projection_view is not None:
        existing_digest = compute_projection_digest(existing_projection_view)
        parity = rebuild_digest == existing_digest
        if not parity:
            diagnostics.append(
                f"Digest mismatch: rebuild={rebuild_digest[:16]}... "
                f"vs existing={existing_digest[:16]}..."
            )
    else:
        existing_digest = None
        parity = False
        diagnostics.append("No existing projection view to compare against.")

    return RebuildComparisonReport(
        projection_id=projection_id,
        parity=parity,
        rebuild_digest=rebuild_digest,
        existing_digest=existing_digest,
        source_cursor=source_cursor,
        diagnostics=tuple(diagnostics),
    )


def rebuild_all_projections(
    registry: ProjectionRegistry,
) -> Dict[str, Dict[str, Any]]:
    """Rebuild every registered projection from its source records.

    Returns a mapping ``{projection_id: rebuilt_view}``.  This is a
    convenience bulk-rebuild that loads source records from each
    registered source path.

    Never mutates source evidence.

    Parameters
    ----------
    registry:
        A populated :class:`ProjectionRegistry`.

    Returns
    -------
    dict
        ``{projection_id: projection_view_dict}`` for every registered
        projection.
    """
    results: Dict[str, Dict[str, Any]] = {}
    for pid in registry.list_registered():
        results[pid] = registry.rebuild(pid)
    return results


def compare_all_projections(
    registry: ProjectionRegistry,
    *,
    existing_views: Dict[str, Mapping[str, Any]] | None = None,
) -> Dict[str, RebuildComparisonReport]:
    """Rebuild and compare every registered projection.

    For each registered projection, loads source records, rebuilds via its
    builder, computes the ordered-view digest, and compares against the
    corresponding entry in *existing_views* (if provided).

    Never mutates source evidence.

    Parameters
    ----------
    registry:
        A populated :class:`ProjectionRegistry`.
    existing_views:
        Optional mapping ``{projection_id: existing_projection_view}``.
        Projections not present in this mapping will have
        ``existing_digest=None`` in their report.

    Returns
    -------
    dict
        ``{projection_id: RebuildComparisonReport}`` for every registered
        projection.
    """
    existing = existing_views or {}
    reports: Dict[str, RebuildComparisonReport] = {}
    for pid in registry.list_registered():
        entry = registry._entries[pid]
        try:
            source_records = entry.source_loader(entry.source_path)
        except (OSError, ValueError):
            source_records = None
        reports[pid] = compare_rebuild(
            registry,
            pid,
            source_records=source_records,
            existing_projection_view=existing.get(pid),
        )
    return reports


# ── Default source-record loader ───────────────────────────────────────────


def _default_jsonl_loader(path: Path) -> Sequence[Mapping[str, Any]]:
    """Load newline-delimited JSON records from *path*.

    Returns an empty tuple when the file does not exist.
    """
    if not path.exists():
        return ()
    import json

    records: list[Mapping[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict):
            records.append(record)
    return tuple(records)


# ── Public exports ─────────────────────────────────────────────────────────

__all__ = [
    "ProjectionBuilderFn",
    "ProjectionRegistry",
    "RebuildComparisonReport",
    "SourceLoaderFn",
    "capture_source_cursor_vector",
    "compare_all_projections",
    "compare_rebuild",
    "compute_projection_digest",
    "rebuild_all_projections",
]
