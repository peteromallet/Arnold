"""Shared strategy I/O service — the single authority-aware entry point.

This module provides the canonical read and projection surface that every
CLI command handler, ticket workflow, and promotion path must route through.
It **never** consults ``.megaplan/strategy.projection.json`` as an authority
source — the projection is always regenerated from the authoritative typed
Markdown and durable artifact storage.

Public API
----------

Core loading
    * :func:`load_strategy` — load, parse, validate, and resolve a strategy
      document in one call.
    * :func:`load_strategy_projection` — load and project a strategy document
      to a JSON-serializable dictionary.
    * :func:`load_strategy_for_write` — load a strategy and capture file state
      (hash + mtime) for safe, lossless writes.

Lossless write
    * :func:`write_strategy` — write a :class:`StrategyDocument` back to
      ``.megaplan/STRATEGY.md`` using block-level roadmap rewriting that
      preserves all non-roadmap prose, comments, and formatting.
    * :class:`StrategyConflictError` — raised when hash/mtime preconditions
      detect a concurrent modification before any bytes are overwritten.

Diagnostic formatting
    * :func:`format_diagnostics` — format all diagnostics as stable,
      machine-readable dictionaries.
    * :func:`format_diagnostic` — format a single diagnostic.

Projection
    * :func:`project_to_dict` — project a document to a dict (pure).
    * :func:`project_to_json` — project and serialize to JSON string (pure).
    * :func:`write_projection` — write projection JSON to disk.

Path helpers
    * :func:`strategy_file_path` — absolute path to ``.megaplan/STRATEGY.md``.
    * :func:`strategy_projection_file_path` — absolute path to
      ``.megaplan/strategy.projection.json``.
"""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from arnold_pipelines.megaplan.layout import (
    strategy_file_path,
    strategy_projection_file_path,
)
from arnold_pipelines.megaplan.strategy.contract import (
    REQUIRED_ROADMAP_SECTIONS,
    RoadmapHorizon,
    StrategyDiagnostic,
    StrategyDocument,
)
from arnold_pipelines.megaplan.strategy.parser import (
    parse_strategy,
)
from arnold_pipelines.megaplan.strategy.projection import (
    project_strategy,
    serialize_strategy_projection,
    write_strategy_projection,
)
from arnold_pipelines.megaplan.strategy.resolver import (
    resolve_strategy,
)
from arnold_pipelines.megaplan.strategy.validation import (
    validate_strategy,
)

# Re-export path helpers for convenience.
__all__ = [
    "StrategyConflictError",
    "StrategyFileState",
    "format_diagnostic",
    "format_diagnostics",
    "load_strategy",
    "load_strategy_for_write",
    "load_strategy_projection",
    "project_to_dict",
    "project_to_json",
    "strategy_file_path",
    "strategy_projection_file_path",
    "write_projection",
    "write_strategy",
]


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class StrategyConflictError(Exception):
    """Raised when a concurrent modification is detected during strategy write.

    The write path checks both SHA-256 hash and filesystem mtime of
    ``.megaplan/STRATEGY.md`` before overwriting any bytes.  If either
    differs from the values captured at load time, this exception is
    raised *before* the file is touched — no partial writes occur.
    """


# ---------------------------------------------------------------------------
# File state for write preconditions
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StrategyFileState:
    """Captured file identity used to detect concurrent modifications.

    Attributes:
        source_text: The full file text as read during :func:`load_strategy_for_write`.
        sha256: Hex-encoded SHA-256 digest of *source_text*.
        mtime: ``st_mtime`` as a float (platform resolution).
    """

    source_text: str
    sha256: str
    mtime: float


# ---------------------------------------------------------------------------
# Core loading
# ---------------------------------------------------------------------------


def load_strategy(
    repo_root: str | Path,
    *,
    store: Any | None = None,
) -> StrategyDocument:
    """Load, parse, validate, and resolve the authoritative strategy document.

    This is the single entry point for reading the typed Markdown strategy.
    It chains the full authority pipeline:

    1. Read ``.megaplan/STRATEGY.md`` from *repo_root*.
    2. Parse into a :class:`StrategyDocument` via :func:`parse_strategy`.
    3. Validate ref formats and duplicates via :func:`validate_strategy`.
    4. Resolve artifact references via :func:`resolve_strategy`.

    The returned document carries diagnostics from every stage.  An empty
    ``document.diagnostics`` list means the document is fully clean.

    Parameters
    ----------
    repo_root:
        Repository root path.  ``.megaplan/STRATEGY.md`` is resolved
        relative to this root.
    store:
        Optional :class:`Store` instance passed through to
        :func:`resolve_strategy` for epic state and relationship queries.

    Returns
    -------
    StrategyDocument
        The fully processed (frozen) strategy document.

    Raises
    ------
    FileNotFoundError
        If ``.megaplan/STRATEGY.md`` does not exist at *repo_root*.
    """
    path = strategy_file_path(repo_root)
    if not path.is_file():
        raise FileNotFoundError(
            f"Strategy file not found: {path}\n"
            f"Run 'python -P -m arnold_pipelines.megaplan strategy init' "
            f"to create one."
        )

    source = path.read_text(encoding="utf-8")
    repo_rel = _repo_relative_path(path, repo_root)

    document = parse_strategy(source, repo_rel)
    document = validate_strategy(document)
    document = resolve_strategy(document, repo_root, store=store)

    return document


def load_strategy_for_write(
    repo_root: str | Path,
    *,
    store: Any | None = None,
) -> tuple[StrategyDocument, StrategyFileState]:
    """Load a strategy and capture its file state for safe writes.

    This is the companion to :func:`write_strategy`.  It reads the file
    once and captures everything needed for the write precondition check:
    source text, SHA-256 hash, and filesystem mtime.

    Parameters
    ----------
    repo_root:
        Repository root path.
    store:
        Optional :class:`Store` instance for artifact resolution.

    Returns
    -------
    tuple[StrategyDocument, StrategyFileState]
        The fully processed document and its captured file state.

    Raises
    ------
    FileNotFoundError
        If ``.megaplan/STRATEGY.md`` does not exist.
    """
    path = strategy_file_path(repo_root)
    if not path.is_file():
        raise FileNotFoundError(
            f"Strategy file not found: {path}\n"
            f"Run 'python -P -m arnold_pipelines.megaplan strategy init' "
            f"to create one."
        )

    source = path.read_text(encoding="utf-8")
    stat = path.stat()
    file_state = StrategyFileState(
        source_text=source,
        sha256=_compute_sha256(source),
        mtime=stat.st_mtime,
    )

    repo_rel = _repo_relative_path(path, repo_root)

    document = parse_strategy(source, repo_rel)
    document = validate_strategy(document)
    document = resolve_strategy(document, repo_root, store=store)

    return document, file_state


def load_strategy_projection(
    repo_root: str | Path,
    *,
    store: Any | None = None,
) -> dict[str, Any]:
    """Load and project the strategy document to a JSON-serializable dictionary.

    Convenience wrapper around :func:`load_strategy` + :func:`project_to_dict`.

    Parameters
    ----------
    repo_root:
        Repository root path.
    store:
        Optional :class:`Store` instance for artifact resolution.

    Returns
    -------
    dict
        The projected strategy as a stable dictionary (see
        :func:`project_strategy` for the schema).
    """
    document = load_strategy(repo_root, store=store)
    return project_to_dict(document)


# ---------------------------------------------------------------------------
# Lossless write
# ---------------------------------------------------------------------------


def write_strategy(
    document: StrategyDocument,
    file_state: StrategyFileState,
    repo_root: str | Path,
) -> None:
    """Write *document* back to ``.megaplan/STRATEGY.md`` with conflict detection.

    The write is **lossless**: only typed roadmap bullets under ``## Now``,
    ``## Next``, and ``## Later`` are rewritten.  All other content —
    frontmatter, stable-direction prose, comments, blank lines, and
    formatting — is preserved byte-for-byte.

    Before touching the file, preconditions are checked:

    * The file's current SHA-256 hash must match *file_state.sha256*.
    * The file's current ``st_mtime`` must match *file_state.mtime*.

    If either check fails, :class:`StrategyConflictError` is raised and
    **no bytes are written**.

    Parameters
    ----------
    document:
        The mutated strategy document to persist.
    file_state:
        Captured file state from a preceding :func:`load_strategy_for_write`
        call.
    repo_root:
        Repository root path.

    Raises
    ------
    StrategyConflictError
        If the file on disk has changed since *file_state* was captured.
    FileNotFoundError
        If ``.megaplan/STRATEGY.md`` does not exist.
    """
    path = strategy_file_path(repo_root)

    if not path.is_file():
        raise FileNotFoundError(
            f"Strategy file not found: {path}\n"
            f"Run 'python -P -m arnold_pipelines.megaplan strategy init' "
            f"to create one."
        )

    # ---- Precondition: hash and mtime must match captured state ----------
    current_text = path.read_text(encoding="utf-8")
    current_hash = _compute_sha256(current_text)
    current_mtime = path.stat().st_mtime

    hash_ok = (
        current_hash == file_state.sha256
        and _timestamps_equal(current_mtime, file_state.mtime)
    )

    if not hash_ok:
        raise StrategyConflictError(
            f"Strategy file '{path}' was modified since it was loaded. "
            f"Expected SHA-256 {file_state.sha256[:12]}..., "
            f"got {current_hash[:12]}...\n"
            f"Re-load the strategy, re-apply your changes, and try again."
        )

    # ---- Rewrite roadmap sections losslessly -----------------------------
    new_text = _rewrite_roadmap_sections(file_state.source_text, document)
    path.write_text(new_text, encoding="utf-8")


# ---------------------------------------------------------------------------
# Diagnostic formatting
# ---------------------------------------------------------------------------


def format_diagnostics(
    document: StrategyDocument,
) -> list[dict[str, Any]]:
    """Format all diagnostics in *document* as stable machine-readable dicts.

    Each diagnostic dict has the shape::

        {
            "kind": "<machine-readable-identifier>",
            "severity": "error" | "warning",
            "message": "<human-readable message>",
            "source": {"path": "...", "line": N, "column": N} | null
        }

    Parameters
    ----------
    document:
        A parsed/validated/resolved :class:`StrategyDocument`.

    Returns
    -------
    list[dict]
        Ordered list of diagnostic dicts (preserving the document's
        diagnostic order).
    """
    return [format_diagnostic(d) for d in document.diagnostics]


def format_diagnostic(
    diagnostic: StrategyDiagnostic,
) -> dict[str, Any]:
    """Format a single diagnostic as a stable machine-readable dict.

    Parameters
    ----------
    diagnostic:
        A :class:`StrategyDiagnostic` to format.

    Returns
    -------
    dict
        Stable diagnostic dict with keys ``kind``, ``severity``, ``message``,
        and ``source``.
    """
    result: dict[str, Any] = {
        "kind": _diagnostic_kind(diagnostic),
        "severity": diagnostic.level,
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


# ---------------------------------------------------------------------------
# Projection helpers (pure)
# ---------------------------------------------------------------------------


def project_to_dict(document: StrategyDocument) -> dict[str, Any]:
    """Project *document* to a deterministic JSON-serializable dictionary.

    This is a thin wrapper around :func:`project_strategy` that provides a
    stable, predictable shape for CLI output.  The projection is always
    generated from the authoritative Markdown — it never reads
    ``.megaplan/strategy.projection.json``.

    Parameters
    ----------
    document:
        A parsed, validated, and resolved :class:`StrategyDocument`.

    Returns
    -------
    dict
        The projection dictionary (see :func:`project_strategy` for schema).
    """
    return project_strategy(document)


def project_to_json(document: StrategyDocument) -> str:
    """Serialize *document* to a deterministic JSON string.

    Parameters
    ----------
    document:
        A parsed, validated, and resolved :class:`StrategyDocument`.

    Returns
    -------
    str
        Deterministic JSON string ending with a single newline.
    """
    return serialize_strategy_projection(document)


def write_projection(
    document: StrategyDocument,
    repo_root: str | Path,
) -> Path:
    """Write the strategy projection to ``.megaplan/strategy.projection.json``.

    This is the **only** filesystem-write helper for projections in this
    module.  The projection is always rebuilt from the authoritative
    Markdown source.

    Parameters
    ----------
    document:
        A parsed, validated, and resolved :class:`StrategyDocument`.
    repo_root:
        Repository root path.  The projection is written to
        ``<repo_root>/.megaplan/strategy.projection.json``.

    Returns
    -------
    Path
        Absolute path of the written file.
    """
    return write_strategy_projection(document, repo_root)


# ---------------------------------------------------------------------------
# Internal helpers — file identity
# ---------------------------------------------------------------------------


def _compute_sha256(text: str) -> str:
    """Return the hex-encoded SHA-256 digest of *text*."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _timestamps_equal(a: float, b: float) -> bool:
    """Compare two mtime floats for equality within platform resolution.

    Some filesystems round mtime to whole seconds; others track
    nanoseconds.  We use exact equality because the hash check is the
    primary guard — mtime is a secondary fast-fail hint.
    """
    return a == b


# ---------------------------------------------------------------------------
# Internal helpers — lossless roadmap rewriting
# ---------------------------------------------------------------------------

# Regex for typed roadmap bullets: ``- [type:ref] <title>``
_BULLET_RE = re.compile(r"^- \[([a-z][a-z_]*):([^\]]*)\]\s+(.*)$")


def _rewrite_roadmap_sections(
    source_text: str,
    document: StrategyDocument,
) -> str:
    """Rewrite only typed roadmap bullets, preserving all other content.

    This is the core lossless-write algorithm.  It:

    1. Splits *source_text* into lines.
    2. Locates every ``## <title>`` heading.
    3. For each roadmap horizon (``Now``, ``Next``, ``Later``), finds
       all typed bullet lines within that section.
    4. Replaces those bullet lines with the current entries from
       *document.roadmap*.
    5. Preserves every other byte — frontmatter, stable-direction prose,
       comments, blank lines within roadmap sections, and formatting.

    Parameters
    ----------
    source_text:
        The original file content captured at load time.
    document:
        The mutated strategy document whose roadmap should be written.

    Returns
    -------
    str
        The rewritten Markdown text.
    """
    lines = source_text.split("\n")

    # ---- Phase 1: locate all ``## <title>`` headings --------------------
    heading_positions: dict[str, int] = {}
    for i, line in enumerate(lines):
        if line.startswith("## "):
            title = line[3:].strip()
            if title not in heading_positions:
                heading_positions[title] = i

    # Sort by position for section-range computation.
    sorted_headings = sorted(heading_positions.items(), key=lambda x: x[1])

    # Build section ranges: (start_idx, end_idx_exclusive)
    section_ranges: dict[str, tuple[int, int]] = {}
    for j, (title, start) in enumerate(sorted_headings):
        if j + 1 < len(sorted_headings):
            end = sorted_headings[j + 1][1]
        else:
            end = len(lines)
        section_ranges[title] = (start, end)

    # ---- Phase 2: collect replacement spans for each roadmap horizon ----
    # Replacements are (start_idx, end_idx_exclusive, new_lines).
    # Processed in reverse order so indices stay valid.
    replacements: list[tuple[int, int, list[str]]] = []

    for horizon in REQUIRED_ROADMAP_SECTIONS:
        if horizon not in section_ranges:
            continue

        section_start, section_end = section_ranges[horizon]

        # Find all typed bullet lines within this section body.
        bullet_indices: list[int] = []
        for i in range(section_start + 1, section_end):
            stripped = lines[i].strip()
            if _BULLET_RE.match(stripped):
                bullet_indices.append(i)

        # Generate new bullet lines from the document.
        entries = document.roadmap.get(horizon, [])
        new_bullets: list[str] = []
        for entry in entries:
            new_bullets.append(
                f"- [{entry.identity.type}:{entry.identity.ref}]"
                f" {entry.display_title}"
            )

        if bullet_indices:
            # Replace the contiguous span from first to last typed bullet.
            first = bullet_indices[0]
            last = bullet_indices[-1] + 1  # exclusive
            replacements.append((first, last, new_bullets))
        elif new_bullets:
            # No existing typed bullets — insert after the heading's
            # trailing blank line (or at section end if none).
            insert_at = section_start + 2  # heading + blank
            if insert_at > section_end:
                insert_at = section_end
            replacements.append((insert_at, insert_at, new_bullets))
        # else: no bullets before or after — nothing to do.

    # ---- Phase 3: apply replacements in reverse order -------------------
    replacements.sort(key=lambda x: x[0], reverse=True)
    for start, end, new_lines in replacements:
        lines[start:end] = new_lines

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Internal helpers — misc
# ---------------------------------------------------------------------------


def _repo_relative_path(path: Path, repo_root: str | Path) -> str:
    """Return *path* as a string relative to *repo_root*, or the full path."""
    try:
        return path.resolve().relative_to(Path(repo_root).resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _diagnostic_kind(diagnostic: StrategyDiagnostic) -> str:
    """Derive a stable machine-readable kind from a diagnostic message.

    The kind is a short, stable identifier that CLI handlers can use for
    error classification without parsing human-readable messages.  Kinds
    are derived by inspecting the diagnostic message for known substrings
    in priority order.

    Diagnostics without a recognized pattern fall back to ``"unknown"``.

    Returns
    -------
    str
        A stable machine-readable kind identifier.
    """
    msg = diagnostic.message

    # Frontmatter errors
    if "Missing frontmatter" in msg:
        return "missing_frontmatter"
    if "Unclosed frontmatter" in msg:
        return "unclosed_frontmatter"
    if "Invalid YAML in frontmatter" in msg:
        return "invalid_frontmatter_yaml"
    if "Frontmatter must be a YAML mapping" in msg:
        return "invalid_frontmatter_type"
    if "Unsupported schema_version" in msg:
        return "unsupported_schema_version"

    # Section errors
    if "Unsupported section" in msg:
        return "unsupported_section"
    if "Missing required" in msg and "section" in msg:
        return "missing_required_section"
    if "Out-of-order" in msg and "section" in msg:
        return "out_of_order_section"

    # Stable section ordering
    if "must appear before roadmap sections" in msg:
        return "stable_after_roadmap"

    # Typed bullets outside roadmap
    if "found outside a roadmap section" in msg:
        return "typed_bullet_outside_roadmap"

    # Malformed bullets
    if "Malformed roadmap bullet" in msg:
        return "malformed_roadmap_bullet"

    # Duplicate detection
    if msg.startswith("Duplicate roadmap entry:"):
        return "duplicate_roadmap_entry"

    # Missing ref
    if "Missing reference in roadmap entry" in msg:
        return "missing_ref"

    # Unsupported item type
    if "Unsupported item type" in msg:
        return "unsupported_item_type"

    # Invalid refs
    if msg.startswith("Invalid ticket ref"):
        return "invalid_ticket_ref"
    if msg.startswith("Invalid epic ref"):
        return "invalid_epic_ref"
    if "Non-canonical epic ref" in msg:
        return "non_canonical_epic_ref"

    # Missing artifacts (resolver)
    if msg.startswith("Missing ticket reference:"):
        return "missing_ticket_artifact"
    if msg.startswith("Missing epic reference:"):
        return "missing_epic_artifact"

    # Stale titles
    if "Stale display title" in msg:
        return "stale_display_title"

    # Lifecycle warnings
    if "Dismissed ticket in roadmap" in msg:
        return "dismissed_ticket_in_roadmap"
    if "Addressed ticket in roadmap" in msg:
        return "addressed_ticket_in_roadmap"
    if "Superseded ticket in roadmap" in msg:
        return "superseded_ticket_in_roadmap"
    if "Completed epic in roadmap" in msg:
        return "completed_epic_in_roadmap"

    # Duplicate intent (ticket+epic)
    if "Duplicate intent" in msg:
        return "duplicate_intent"

    # Mutation diagnostics
    if "already exists in horizon" in msg:
        return "strategy_entry_exists"

    # Promotion diagnostics
    if "not present in any roadmap horizon" in msg:
        return "promotion_ticket_not_in_roadmap"

    return "unknown"
