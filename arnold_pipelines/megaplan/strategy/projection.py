"""Deterministic JSON projection for v1 strategy documents.

This module produces a disposable, rebuildable JSON representation of a
parsed and validated :class:`StrategyDocument`.  The projection is **never**
read as an authority source — it exists only as a convenience for tooling
that cannot consume the canonical Markdown directly.

Design rules
------------

* **Deterministic output**: given the same document, ``project_strategy``
  produces byte-for-byte equivalent JSON (sorted keys, no trailing newline
  variance, stable field ordering).
* **Visibly non-authoritative**: the projection declares its own schema
  version and the source document version, making it clear that the JSON is
  derived.
* **No artifact bodies or lifecycle status**: the projection includes
  identity (type/ref), display title, horizon, and source location, but
  never duplicates ticket/epic bodies, status fields, or completion evidence.
* **Validation summary**: diagnostics from parsing, validation, and
  resolution are included so downstream consumers can surface issues without
  re-running the full pipeline.
* **Core functions are side-effect free** — only the explicit
  :func:`write_strategy_projection` helper touches the filesystem.
* **Rebuild metadata**: :func:`compute_strategy_projection_digest` and
  :func:`capture_strategy_source_cursor` provide stable digests and source
  cursors for rebuild parity. :func:`project_strategy_with_metadata` adds
  freshness, lag, and cursor fields while keeping the core reducer pure.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List

from arnold_pipelines.megaplan._core.io import (
    ProjectionCursor,
    _projection_canonical_dumps,
    now_utc,
)
from arnold_pipelines.megaplan.strategy.contract import (
    SCHEMA_VERSION,
    PROJECTION_SCHEMA_VERSION,
    REQUIRED_ROADMAP_SECTIONS,
    RoadmapEntry,
    RoadmapHorizon,
    StrategyDiagnostic,
    StrategyDocument,
    StrategySection,
)

REBUILD_METADATA_SCHEMA_VERSION = 1

# ---------------------------------------------------------------------------
# Public API - pure projection (side-effect free)
# ---------------------------------------------------------------------------


def project_strategy(document: StrategyDocument) -> dict[str, Any]:
    """Project *document* into a deterministic JSON-serializable dictionary.

    The returned dictionary is safe to pass to :func:`json.dumps` with
    ``sort_keys=True`` and ``indent=2`` for stable byte-for-byte output.

    Parameters
    ----------
    document:
        A parsed, validated, and resolved :class:`StrategyDocument`.

    Returns
    -------
    dict
        A dictionary with ordered keys representing the projection.
    """
    # Build diagnostics summary: count by level plus the full list.
    error_count = sum(1 for d in document.diagnostics if d.level == "error")
    warning_count = sum(1 for d in document.diagnostics if d.level == "warning")

    # Build stable direction summary: each section with title, body, and
    # source location.  We intentionally include the body here because
    # stable-direction sections (Mission, Principles, etc.) are strategy
    # prose, not artifact bodies.
    stable_direction: list[dict[str, Any]] = []
    for section in document.stable_direction:
        stable_direction.append(
            _project_section(section)
        )

    # Build roadmap with ordered horizons.
    roadmap: dict[str, list[dict[str, Any]]] = {}
    for horizon in REQUIRED_ROADMAP_SECTIONS:
        entries = document.roadmap.get(horizon, [])
        roadmap[horizon] = [
            _project_roadmap_entry(entry) for entry in entries
        ]

    # Build diagnostics list for the projection.
    diagnostics: list[dict[str, Any]] = []
    for diag in document.diagnostics:
        diagnostics.append(_project_diagnostic(diag))

    return {
        "schema_version": PROJECTION_SCHEMA_VERSION,
        "source_version": document.schema_version or SCHEMA_VERSION,
        "stable_direction": stable_direction,
        "roadmap": roadmap,
        "diagnostics": diagnostics,
        "validation_summary": {
            "error_count": error_count,
            "warning_count": warning_count,
            "total_diagnostics": len(document.diagnostics),
            "clean": len(document.diagnostics) == 0,
        },
    }


def serialize_strategy_projection(document: StrategyDocument) -> str:
    """Serialize *document* to a deterministic JSON string.

    The output is a single line-terminated JSON string with sorted keys,
    2-space indentation, and no trailing whitespace variance.  Given the
    same document, two calls to this function produce byte-for-byte
    identical output.

    Parameters
    ----------
    document:
        A parsed, validated, and resolved :class:`StrategyDocument`.

    Returns
    -------
    str
        A deterministic JSON string ending with a single newline.
    """
    projection = project_strategy(document)
    return json.dumps(projection, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


# ---------------------------------------------------------------------------
# Write helper (the only function with filesystem side effects)
# ---------------------------------------------------------------------------


def write_strategy_projection(
    document: StrategyDocument,
    repo_root: str | Path,
) -> Path:
    """Write the strategy projection to ``.megaplan/strategy.projection.json``.

    This is the **only** function in this module that touches the
    filesystem.  All other functions are pure computations.

    Parameters
    ----------
    document:
        A parsed, validated, and resolved :class:`StrategyDocument`.
    repo_root:
        The repository root path.  The projection is written to
        ``<repo_root>/.megaplan/strategy.projection.json``.

    Returns
    -------
    Path
        The absolute path of the written file.
    """
    from arnold_pipelines.megaplan.layout import strategy_projection_file_path

    output_path = strategy_projection_file_path(repo_root)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    json_text = serialize_strategy_projection(document)
    output_path.write_text(json_text, encoding="utf-8")
    return output_path


# ---------------------------------------------------------------------------
# Rebuild metadata & digest helpers (pure, no side effects)
# ---------------------------------------------------------------------------


def compute_strategy_projection_digest(document: StrategyDocument) -> str:
    """Compute a deterministic SHA-256 digest of the strategy projection.

    The digest is computed over the canonical (stable, sorted-key,
    no-whitespace) JSON representation of ``project_strategy(document)``,
    making it byte-for-byte comparable across rebuilds.

    Parameters
    ----------
    document:
        A parsed, validated, and resolved :class:`StrategyDocument`.

    Returns
    -------
    str
        ``"sha256:<hex>"`` digest string.
    """
    projection = project_strategy(document)
    canonical = _projection_canonical_dumps(projection)
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def capture_strategy_source_cursor(source_path: str | Path) -> ProjectionCursor:
    """Capture a :class:`ProjectionCursor` for the strategy Markdown source.

    This function is **read-only** — it never mutates the source file.

    Parameters
    ----------
    source_path:
        Path to the strategy Markdown source (e.g. ``STRATEGY.md``).

    Returns
    -------
    ProjectionCursor
        An immutable cursor capturing the source file state.
    """
    from arnold_pipelines.megaplan._core.io import _projection_cursor_from_path

    return _projection_cursor_from_path(Path(source_path))


def strategy_rebuild_metadata(
    source_path: str | Path,
    *,
    projection_digest: str = "",
    computed_at: str | None = None,
) -> dict[str, Any]:
    """Produce rebuild metadata for a strategy projection.

    Pure function — never mutates source evidence.  The caller is
    responsible for attaching the returned metadata to a projection view.

    Parameters
    ----------
    source_path:
        Path to the strategy Markdown source file.
    projection_digest:
        Pre-computed digest of the projection view.
    computed_at:
        ISO-8601 rebuild timestamp (default: ``now_utc()``).

    Returns
    -------
    dict
        Metadata dict with ``source_cursor``, ``rebuilt_at``,
        ``freshness_seconds``, ``lag_seconds``, optional
        ``projection_digest``, and ``rebuild_schema_version``.
    """
    from datetime import datetime

    cursor = capture_strategy_source_cursor(source_path)
    rebuilt_at = computed_at or now_utc()

    freshness_seconds = 0.0

    try:
        source_path_obj = Path(source_path)
        if source_path_obj.exists():
            source_mtime = source_path_obj.stat().st_mtime
            rebuild_epoch = datetime.fromisoformat(rebuilt_at).timestamp()
            lag_seconds = max(0.0, rebuild_epoch - source_mtime)
        else:
            lag_seconds = 0.0
    except (OSError, ValueError):
        lag_seconds = 0.0

    metadata: dict[str, Any] = {
        "rebuild_schema_version": REBUILD_METADATA_SCHEMA_VERSION,
        "source_cursor": cursor.to_dict(),
        "rebuilt_at": rebuilt_at,
        "freshness_seconds": freshness_seconds,
        "lag_seconds": lag_seconds,
    }
    if projection_digest:
        metadata["projection_digest"] = projection_digest

    return metadata


def project_strategy_with_metadata(
    document: StrategyDocument,
    *,
    source_path: str | Path | None = None,
) -> dict[str, Any]:
    """Project *document* with rebuild metadata attached.

    Returns the same projection as :func:`project_strategy` plus a
    top-level ``rebuild_metadata`` block containing the source cursor,
    freshness, lag, and rebuild digest when *source_path* is provided.

    The core projection is unchanged — metadata is additive and does not
    affect the original fields.

    Parameters
    ----------
    document:
        A parsed, validated, and resolved :class:`StrategyDocument`.
    source_path:
        Optional path to the strategy Markdown source.  When ``None``,
        ``rebuild_metadata`` is omitted.

    Returns
    -------
    dict
        The projection dict with an optional ``rebuild_metadata`` key.
    """
    projection = project_strategy(document)
    if source_path is not None:
        digest = compute_strategy_projection_digest(document)
        metadata = strategy_rebuild_metadata(
            source_path, projection_digest=digest
        )
        result: dict[str, Any] = dict(projection)
        result["rebuild_metadata"] = metadata
        return result
    return projection


# ---------------------------------------------------------------------------
# Internal projection helpers (pure)
# ---------------------------------------------------------------------------


def _project_section(section: StrategySection) -> dict[str, Any]:
    """Project a stable-direction section to a JSON-safe dict."""
    return {
        "title": section.title,
        "body": section.body,
        "source": {
            "path": section.source_location.path,
            "line": section.source_location.line,
            "column": section.source_location.column,
        },
    }


def _project_roadmap_entry(entry: RoadmapEntry) -> dict[str, Any]:
    """Project a roadmap entry to a JSON-safe dict.

    Includes identity (type/ref), display title, horizon, and source
    location.  Does **not** include artifact bodies or lifecycle status.
    """
    return {
        "type": entry.identity.type,
        "ref": entry.identity.ref,
        "title": entry.display_title,
        "horizon": entry.horizon,
        "source": {
            "path": entry.source_location.path,
            "line": entry.source_location.line,
            "column": entry.source_location.column,
        },
    }


def _project_diagnostic(diagnostic: StrategyDiagnostic) -> dict[str, Any]:
    """Project a diagnostic to a JSON-safe dict."""
    result: dict[str, Any] = {
        "level": diagnostic.level,
        "message": diagnostic.message,
    }
    if diagnostic.source_location is not None:
        result["source"] = {
            "path": diagnostic.source_location.path,
            "line": diagnostic.source_location.line,
            "column": diagnostic.source_location.column,
        }
    else:
        result["source"] = None
    return result
