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
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

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
