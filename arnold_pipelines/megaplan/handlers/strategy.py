"""CLI command handlers for ``megaplan strategy ...`` subcommands.

Each handler is a thin adapter: it unpacks an :class:`argparse.Namespace`,
routes through the shared :mod:`arnold_pipelines.megaplan.strategy.io`
service, and returns a stable JSON-serializable :class:`StepResponse`
dictionary.  No handler duplicates Markdown parsing, serialization,
diagnostic formatting, or roadmap mutation logic — all authority-sensitive
work lives in the shared strategy package.

Handlers
--------

* :func:`handle_strategy_init` — scaffold ``.megaplan/STRATEGY.md`` from the
  v1 template.
* :func:`handle_strategy_validate` — load, parse, validate, and resolve a
  strategy file; return diagnostics and a ``clean`` verdict.
* :func:`handle_strategy_show` — load a strategy and return its full
  structured representation (stable direction + roadmap + diagnostics).
* :func:`handle_strategy_list` — return a flat list of roadmap entries
  across all horizons.
* :func:`handle_strategy_project` — load and project; print JSON to stdout
  by default; write to ``strategy.projection.json`` only when ``--write``
  or ``--output`` is supplied.
* :func:`handle_strategy_add` — add a roadmap entry; write through the
  lossless service with conflict detection.
* :func:`handle_strategy_remove` — remove a roadmap entry by identity.
* :func:`handle_strategy_move` — move a roadmap entry between horizons.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from arnold_pipelines.megaplan.strategy import (
    REQUIRED_ROADMAP_SECTIONS,
    StrategyConflictError,
    add_roadmap_entry,
    format_diagnostics,
    load_strategy,
    load_strategy_for_write,
    load_strategy_projection,
    make_roadmap_entry,
    move_roadmap_entry,
    project_to_dict,
    project_to_json,
    remove_roadmap_entry,
    strategy_file_path,
    strategy_projection_file_path,
    write_projection,
    write_strategy,
)
from arnold_pipelines.megaplan.strategy.contract import (
    RoadmapEntry,
    RoadmapHorizon,
    RoadmapItemType,
    StrategyDiagnostic,
    StrategyIdentity,
)
from arnold_pipelines.megaplan.strategy.migration import (
    MigrationReport,
    inspect_strategy_migration,
)
from arnold_pipelines.megaplan.strategy.apply_migration import apply_strategy_migration
from arnold_pipelines.megaplan.strategy.versions import (
    CURRENT_SCHEMA_VERSION,
    inspect_strategy_file,
)
from arnold_pipelines.megaplan.types import CliError, StepResponse


# ---------------------------------------------------------------------------
# Template path
# ---------------------------------------------------------------------------

_TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "strategy" / "TEMPLATE.md"


def _read_template() -> str:
    """Read the v1 strategy template from the strategy package directory."""
    try:
        return _TEMPLATE_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        raise CliError(
            "strategy_template_missing",
            f"Strategy template not found at {_TEMPLATE_PATH}: {exc}",
        ) from exc


# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------


def handle_strategy_init(
    repo_root: Path,
    args: argparse.Namespace,
) -> StepResponse:
    """Scaffold ``.megaplan/STRATEGY.md`` from the v1 template.

    Parameters
    ----------
    repo_root:
        Repository root directory.
    args:
        Parsed CLI arguments.  ``--force`` (optional) allows overwriting an
        existing strategy file.

    Returns
    -------
    StepResponse
        A structured response with the written path.

    Raises
    ------
    CliError
        If the strategy file already exists and ``--force`` was not passed,
        or if the template cannot be read.
    """
    target = strategy_file_path(repo_root)
    force = bool(getattr(args, "force", False))

    if target.exists() and not force:
        raise CliError(
            "strategy_exists",
            f"Strategy file already exists: {target}\n"
            f"Use --force to overwrite, or run 'strategy validate' / "
            f"'strategy show' to inspect the existing file.",
        )

    template = _read_template()

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(template, encoding="utf-8")

    return {
        "success": True,
        "step": "strategy",
        "action": "init",
        "path": str(target),
        "summary": f"Strategy scaffold written to {target}",
    }


# ---------------------------------------------------------------------------
# validate
# ---------------------------------------------------------------------------


def handle_strategy_validate(
    repo_root: Path,
    args: argparse.Namespace,
) -> StepResponse:
    """Load, parse, validate, and resolve the strategy file.

    Parameters
    ----------
    repo_root:
        Repository root directory.
    args:
        Parsed CLI arguments.  ``--json`` (optional) returns verbose
        machine-readable output including the full diagnostic list.

    Returns
    -------
    StepResponse
        A structured response with ``clean`` verdict, error/warning counts,
        and the full diagnostic list when ``--json`` is passed.

    Raises
    ------
    CliError
        If the strategy file does not exist.
    """
    json_flag = bool(getattr(args, "json", False))

    try:
        document = load_strategy(repo_root)
    except FileNotFoundError:
        raise CliError(
            "strategy_missing",
            "No strategy file found. Run 'strategy init' first.",
        )

    diagnostics = format_diagnostics(document)

    error_count = sum(1 for d in diagnostics if d["severity"] == "error")
    warning_count = sum(1 for d in diagnostics if d["severity"] == "warning")

    response: StepResponse = {
        "success": True,
        "step": "strategy",
        "action": "validate",
        "clean": len(diagnostics) == 0,
        "error_count": error_count,
        "warning_count": warning_count,
        "total_diagnostics": len(diagnostics),
    }

    if json_flag:
        response["diagnostics"] = diagnostics

    # Exit nonzero on errors (hard diagnostics).
    if error_count > 0:
        raise CliError(
            "strategy_validation_failed",
            f"Strategy validation found {error_count} error(s) "
            f"and {warning_count} warning(s).",
            extra={
                "error_count": error_count,
                "warning_count": warning_count,
                "diagnostics": diagnostics if json_flag else None,
            },
            exit_code=1,
        )

    return response


# ---------------------------------------------------------------------------
# show
# ---------------------------------------------------------------------------


def handle_strategy_show(
    repo_root: Path,
    args: argparse.Namespace,
) -> StepResponse:
    """Load and return the full structured strategy representation.

    Parameters
    ----------
    repo_root:
        Repository root directory.
    args:
        Parsed CLI arguments.  ``--json`` (optional) returns the full
        projection dictionary instead of the summary response.

    Returns
    -------
    StepResponse
        A structured response containing stable direction, roadmap entries
        grouped by horizon, and a diagnostics summary.

    Raises
    ------
    CliError
        If the strategy file does not exist.
    """
    json_flag = bool(getattr(args, "json", False))

    try:
        document = load_strategy(repo_root)
    except FileNotFoundError:
        raise CliError(
            "strategy_missing",
            "No strategy file found. Run 'strategy init' first.",
        )

    projection = project_to_dict(document)

    if json_flag:
        return {
            "success": True,
            "step": "strategy",
            "action": "show",
            "strategy": projection,
        }

    # Build a compact summary response.
    diagnostics = format_diagnostics(document)
    error_count = sum(1 for d in diagnostics if d["severity"] == "error")
    warning_count = sum(1 for d in diagnostics if d["severity"] == "warning")

    # Stable direction titles.
    stable_titles = [
        section["title"] for section in projection.get("stable_direction", [])
    ]

    # Roadmap entry counts by horizon.
    roadmap_counts: dict[str, int] = {}
    roadmap = projection.get("roadmap", {})
    for horizon in REQUIRED_ROADMAP_SECTIONS:
        entries = roadmap.get(horizon, [])
        roadmap_counts[horizon] = len(entries)

    return {
        "success": True,
        "step": "strategy",
        "action": "show",
        "schema_version": projection.get("source_version"),
        "stable_sections": stable_titles,
        "roadmap_counts": roadmap_counts,
        "total_roadmap_entries": sum(roadmap_counts.values()),
        "clean": len(diagnostics) == 0,
        "error_count": error_count,
        "warning_count": warning_count,
    }


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------


def handle_strategy_list(
    repo_root: Path,
    args: argparse.Namespace,
) -> StepResponse:
    """Return a flat list of all roadmap entries across horizons.

    Parameters
    ----------
    repo_root:
        Repository root directory.
    args:
        Parsed CLI arguments:

        * ``--horizon`` (optional) filters entries to a specific horizon
          (``Now``, ``Next``, or ``Later``).
        * ``--type`` (optional) filters entries by artifact type
          (``ticket`` or ``epic``).
        * ``--json`` (optional) prints the full entries list as compact
          JSON to stdout instead of a summary response.

    Returns
    -------
    StepResponse
        A structured response with a flat ``entries`` list.

    Raises
    ------
    CliError
        If the strategy file does not exist, or if ``--horizon`` is not a
        valid horizon label.
    """
    horizon_filter: str | None = getattr(args, "horizon", None)
    type_filter: str | None = getattr(args, "entry_type", None)
    json_flag: bool = bool(getattr(args, "json", False))

    if horizon_filter is not None and horizon_filter not in REQUIRED_ROADMAP_SECTIONS:
        valid = ", ".join(REQUIRED_ROADMAP_SECTIONS)
        raise CliError(
            "invalid_args",
            f"Invalid horizon '{horizon_filter}'. Must be one of: {valid}",
        )

    if type_filter is not None and type_filter not in ("ticket", "epic"):
        raise CliError(
            "invalid_args",
            f"Invalid type filter '{type_filter}'. Must be 'ticket' or 'epic'.",
        )

    try:
        document = load_strategy(repo_root)
    except FileNotFoundError:
        raise CliError(
            "strategy_missing",
            "No strategy file found. Run 'strategy init' first.",
        )

    entries: list[dict[str, Any]] = []
    for horizon in REQUIRED_ROADMAP_SECTIONS:
        if horizon_filter is not None and horizon != horizon_filter:
            continue
        for entry in document.roadmap.get(horizon, []):
            if type_filter is not None and entry.identity.type != type_filter:
                continue
            entries.append({
                "type": entry.identity.type,
                "ref": entry.identity.ref,
                "title": entry.display_title,
                "horizon": entry.horizon,
                "source": {
                    "path": entry.source_location.path,
                    "line": entry.source_location.line,
                    "column": entry.source_location.column,
                },
            })

    diagnostics = format_diagnostics(document)
    error_count = sum(1 for d in diagnostics if d["severity"] == "error")
    warning_count = sum(1 for d in diagnostics if d["severity"] == "warning")

    if json_flag:
        # Return the JSON as a string — render_response prints strings directly.
        output = {
            "horizon_filter": horizon_filter,
            "type_filter": type_filter,
            "total_entries": len(entries),
            "entries": entries,
            "error_count": error_count,
            "warning_count": warning_count,
        }
        return json.dumps(output, separators=(",", ":"), ensure_ascii=False) + "\n"

    return {
        "success": True,
        "step": "strategy",
        "action": "list",
        "horizon_filter": horizon_filter,
        "type_filter": type_filter,
        "total_entries": len(entries),
        "entries": entries,
        "error_count": error_count,
        # Include a diagnostics summary for stale-title awareness.
        "warning_count": warning_count,
    }


# ---------------------------------------------------------------------------
# project
# ---------------------------------------------------------------------------


def handle_strategy_project(
    repo_root: Path,
    args: argparse.Namespace,
) -> StepResponse:
    """Load and project the strategy; print JSON to stdout by default.

    The projection is always regenerated from the authoritative Markdown.
    It is printed to ``stdout`` unless ``--write`` or ``--output <path>``
    is supplied.

    Parameters
    ----------
    repo_root:
        Repository root directory.
    args:
        Parsed CLI arguments:
        * ``--write`` — write projection to the default
          ``.megaplan/strategy.projection.json`` path.
        * ``--output <path>`` — write projection to a custom path
          (relative to *repo_root*).

    Returns
    -------
    StepResponse
        A structured response.  When neither ``--write`` nor ``--output``
        is given, the projection JSON is printed directly to stdout and the
        response indicates that.

    Raises
    ------
    CliError
        If the strategy file does not exist.
    """
    write_flag = bool(getattr(args, "write", False))
    output_path: str | None = getattr(args, "output", None)

    if write_flag and output_path:
        raise CliError(
            "invalid_args",
            "Pass either --write or --output, not both.",
        )

    try:
        document = load_strategy(repo_root)
    except FileNotFoundError:
        raise CliError(
            "strategy_missing",
            "No strategy file found. Run 'strategy init' first.",
        )

    # Fail closed: a document that parsed only with error diagnostics (for
    # example an unsupported schema version) is not a valid authority
    # document. Strict authoritative commands must refuse rather than emit
    # partial projection JSON that merely embeds the diagnostics.
    _raw_diags = (
        getattr(document, "error_diagnostics", None)
        or getattr(document, "diagnostics", None)
        or []
    )
    _error_diags = []
    for _d in _raw_diags:
        # StrategyDiagnostic exposes the level on the ``level`` attribute
        # (``DiagnosticLevel`` = Literal["error", "warning"]); the older
        # ``severity`` spelling is not present, so reading it never detected
        # error-level diagnostics and let invalid authority through.
        _sev = _d.get("level", "") if isinstance(_d, dict) else getattr(_d, "level", "")
        if str(_sev).lower() == "error":
            _error_diags.append(_d)
    if _error_diags:
        _first = _error_diags[0]
        _msg = (
            _first.get("message", "invalid strategy")
            if isinstance(_first, dict)
            else getattr(_first, "message", "invalid strategy")
        )
        raise CliError(
            "strategy_invalid",
            "Strategy file is not a valid authority document: " + str(_msg),
        )

    projection_json = project_to_json(document)

    if output_path:
        # Write to a custom path relative to repo_root.
        resolved = (Path(repo_root) / output_path).resolve()
        try:
            resolved.relative_to(Path(repo_root).resolve())
        except ValueError:
            raise CliError(
                "invalid_args",
                f"--output path must be within the repository root: {output_path}",
            )
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(projection_json, encoding="utf-8")
        return {
            "success": True,
            "step": "strategy",
            "action": "project",
            "written_to": str(resolved),
            "summary": f"Projection written to {resolved}",
        }

    if write_flag:
        # Write to the default projection path.
        output = write_projection(document, repo_root)
        return {
            "success": True,
            "step": "strategy",
            "action": "project",
            "written_to": str(output),
            "summary": f"Projection written to {output}",
        }

    # Default: return projection JSON as a string — render_response prints strings directly.
    return projection_json


# ---------------------------------------------------------------------------
# add
# ---------------------------------------------------------------------------


def handle_strategy_add(
    repo_root: Path,
    args: argparse.Namespace,
) -> StepResponse:
    """Add a roadmap entry to the strategy file.

    The write is routed through :func:`load_strategy_for_write` and
    :func:`write_strategy`, which guarantees hash/mtime conflict detection
    and lossless rewriting of only the typed roadmap bullets.

    Parameters
    ----------
    repo_root:
        Repository root directory.
    args:
        Parsed CLI arguments:

        * ``type`` — artifact type (``ticket`` or ``epic``).
        * ``ref`` — unique artifact reference (ULID or initiative slug).
        * ``title`` — human-readable display title.
        * ``horizon`` — target horizon (``Now``, ``Next``, ``Later``).

    Returns
    -------
    StepResponse
        A structured response confirming the add.

    Raises
    ------
    CliError
        * ``strategy_invalid`` — if ``type``, ``horizon``, or ``ref`` is
          missing or invalid.
        * ``strategy_entry_exists`` — if an entry with the same
          ``(type, ref)`` identity already exists in any horizon.
        * ``strategy_conflict`` — if the strategy file was modified
          concurrently.
    """
    item_type: str | None = getattr(args, "type", None)
    ref: str | None = getattr(args, "ref", None)
    title: str | None = getattr(args, "title", None)
    horizon: str | None = getattr(args, "horizon", None)

    # ---- Validate arguments -------------------------------------------------
    if item_type not in (None, "ticket", "epic") or item_type is None:
        raise CliError(
            "strategy_invalid",
            f"Invalid or missing type '{item_type}'. Must be 'ticket' or 'epic'.",
        )
    if horizon not in (None, "Now", "Next", "Later") or horizon is None:
        raise CliError(
            "strategy_invalid",
            f"Invalid or missing horizon '{horizon}'. Must be 'Now', 'Next', or 'Later'.",
        )
    if not ref or not isinstance(ref, str):
        raise CliError(
            "strategy_invalid",
            "Missing or empty ref.",
        )
    if not title or not isinstance(title, str):
        raise CliError(
            "strategy_invalid",
            "Missing or empty title.",
        )

    # ---- Load, mutate, write ------------------------------------------------
    try:
        document, file_state = load_strategy_for_write(repo_root)
    except FileNotFoundError:
        raise CliError(
            "strategy_missing",
            "No strategy file found. Run 'strategy init' first.",
        )

    # Fail closed: a strategy that only parsed with hard diagnostics (e.g. an
    # unsupported schema_version) is not a valid authority document. Strict
    # write commands must reject it before mutating the file.
    _require_valid_authority(repo_root, document)

    # ---- Preflight: reject unknown artifact references -----------------------
    _validate_artifact_exists(item_type, ref, repo_root)

    entry = make_roadmap_entry(
        type_=item_type,  # type: ignore[arg-type]
        ref=ref,
        title=title,
    )

    new_document = add_roadmap_entry(document, entry, horizon)  # type: ignore[arg-type]

    # Detect whether the add was a no-op (entry already exists).
    if new_document is document or _roadmap_unchanged(document, new_document):
        raise CliError(
            "strategy_entry_exists",
            f"Roadmap entry '{item_type}:{ref}' already exists in the strategy. "
            f"Remove it first or use 'strategy move' to relocate it.",
        )

    try:
        write_strategy(new_document, file_state, repo_root)
    except StrategyConflictError as exc:
        raise CliError(
            "strategy_conflict",
            str(exc),
        ) from exc

    return {
        "success": True,
        "step": "strategy",
        "action": "add",
        "identity": {"type": item_type, "ref": ref},
        "horizon": horizon,
        "summary": f"Added '{item_type}:{ref}' ({title}) to {horizon}.",
    }


# ---------------------------------------------------------------------------
# remove
# ---------------------------------------------------------------------------


def handle_strategy_remove(
    repo_root: Path,
    args: argparse.Namespace,
) -> StepResponse:
    """Remove a roadmap entry from the strategy by identity.

    Parameters
    ----------
    repo_root:
        Repository root directory.
    args:
        Parsed CLI arguments:

        * ``type`` — artifact type (``ticket`` or ``epic``).
        * ``ref`` — unique artifact reference.

    Returns
    -------
    StepResponse
        A structured response confirming the removal.

    Raises
    ------
    CliError
        * ``strategy_invalid`` — if ``type`` or ``ref`` is missing/invalid.
        * ``strategy_entry_missing`` — if no entry with the given identity
          exists in any horizon.
        * ``strategy_conflict`` — if the strategy file was modified
          concurrently.
    """
    item_type: str | None = getattr(args, "type", None)
    ref: str | None = getattr(args, "ref", None)

    if item_type not in (None, "ticket", "epic") or item_type is None:
        raise CliError(
            "strategy_invalid",
            f"Invalid or missing type '{item_type}'. Must be 'ticket' or 'epic'.",
        )
    if not ref or not isinstance(ref, str):
        raise CliError(
            "strategy_invalid",
            "Missing or empty ref.",
        )

    identity = StrategyIdentity(type=item_type, ref=ref)  # type: ignore[arg-type]

    try:
        document, file_state = load_strategy_for_write(repo_root)
    except FileNotFoundError:
        raise CliError(
            "strategy_missing",
            "No strategy file found. Run 'strategy init' first.",
        )

    # Fail closed: refuse to mutate an invalid strategy authority document
    # (e.g. unsupported schema_version) before any write.
    _require_valid_authority(repo_root, document)

    new_document = remove_roadmap_entry(document, identity)

    # Detect whether anything was actually removed.
    if _roadmap_unchanged(document, new_document):
        raise CliError(
            "strategy_entry_missing",
            f"Roadmap entry '{item_type}:{ref}' is not present in any horizon. "
            f"Nothing to remove.",
        )

    try:
        write_strategy(new_document, file_state, repo_root)
    except StrategyConflictError as exc:
        raise CliError(
            "strategy_conflict",
            str(exc),
        ) from exc

    return {
        "success": True,
        "step": "strategy",
        "action": "remove",
        "identity": {"type": item_type, "ref": ref},
        "summary": f"Removed '{item_type}:{ref}' from the strategy roadmap.",
    }


# ---------------------------------------------------------------------------
# move
# ---------------------------------------------------------------------------


def handle_strategy_move(
    repo_root: Path,
    args: argparse.Namespace,
) -> StepResponse:
    """Move a roadmap entry to a different horizon.

    Parameters
    ----------
    repo_root:
        Repository root directory.
    args:
        Parsed CLI arguments:

        * ``type`` — artifact type (``ticket`` or ``epic``).
        * ``ref`` — unique artifact reference.
        * ``horizon`` — destination horizon (``Now``, ``Next``, ``Later``).

    Returns
    -------
    StepResponse
        A structured response confirming the move.

    Raises
    ------
    CliError
        * ``strategy_invalid`` — if ``type``, ``ref``, or ``horizon`` is
          missing or invalid.
        * ``strategy_entry_missing`` — if no entry with the given identity
          exists in any horizon.
        * ``strategy_conflict`` — if the strategy file was modified
          concurrently.
    """
    item_type: str | None = getattr(args, "type", None)
    ref: str | None = getattr(args, "ref", None)
    horizon: str | None = getattr(args, "horizon", None)

    if item_type not in (None, "ticket", "epic") or item_type is None:
        raise CliError(
            "strategy_invalid",
            f"Invalid or missing type '{item_type}'. Must be 'ticket' or 'epic'.",
        )
    if horizon not in (None, "Now", "Next", "Later") or horizon is None:
        raise CliError(
            "strategy_invalid",
            f"Invalid or missing horizon '{horizon}'. Must be 'Now', 'Next', or 'Later'.",
        )
    if not ref or not isinstance(ref, str):
        raise CliError(
            "strategy_invalid",
            "Missing or empty ref.",
        )

    identity = StrategyIdentity(type=item_type, ref=ref)  # type: ignore[arg-type]

    try:
        document, file_state = load_strategy_for_write(repo_root)
    except FileNotFoundError:
        raise CliError(
            "strategy_missing",
            "No strategy file found. Run 'strategy init' first.",
        )

    # Fail closed: refuse to mutate an invalid strategy authority document
    # (e.g. unsupported schema_version) before any write.
    _require_valid_authority(repo_root, document)

    new_document = move_roadmap_entry(document, identity, horizon)  # type: ignore[arg-type]

    # Detect missing entry: move_roadmap_entry returns unchanged document
    # when the identity is not found in any horizon.
    if _roadmap_unchanged(document, new_document):
        # Distinguish "already there" (no-op) from "missing".
        # Check if the entry exists in the target horizon already.
        found = False
        for entry in document.roadmap.get(horizon, []):  # type: ignore[arg-type]
            if entry.identity == identity:
                found = True
                break
        if found:
            # Already in target horizon — move is a no-op.
            return {
                "success": True,
                "step": "strategy",
                "action": "move",
                "identity": {"type": item_type, "ref": ref},
                "horizon": horizon,
                "summary": (
                    f"'{item_type}:{ref}' is already in horizon '{horizon}'; "
                    f"nothing to move."
                ),
            }
        # Not found anywhere — missing entry.
        raise CliError(
            "strategy_entry_missing",
            f"Roadmap entry '{item_type}:{ref}' is not present in any horizon. "
            f"Use 'strategy add' to add it first.",
        )

    try:
        write_strategy(new_document, file_state, repo_root)
    except StrategyConflictError as exc:
        raise CliError(
            "strategy_conflict",
            str(exc),
        ) from exc

    return {
        "success": True,
        "step": "strategy",
        "action": "move",
        "identity": {"type": item_type, "ref": ref},
        "horizon": horizon,
        "summary": f"Moved '{item_type}:{ref}' to {horizon}.",
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _require_valid_authority(
    repo_root: str | Path,
    document: "StrategyDocument",
) -> None:
    """Fail closed: refuse to mutate an invalid strategy authority document.

    Strict write commands (add/move/remove/project) must not act on a strategy
    file whose authority is not currently valid. Two independent gates:

    1. **Version status must be ``current``.** The tolerant inspection surface
       (doctor/migrate) classifies legacy / missing-version / unsupported-old /
       unsupported-new / malformed states, but those are *not* valid authority
       for strict commands. The explicit version check closes this gap
       regardless of the diagnostic level the parser assigns to the version.
    2. **No hard ``error``-level diagnostics** from parsing/validation
       (``StrategyDiagnostic.level == 'error'``).

    A no-op for clean, current documents.
    """
    version_status = inspect_strategy_file(repo_root)
    if version_status != "current":
        raise CliError(
            "strategy_invalid",
            "Strategy file is not a valid current authority document "
            f"(version status: '{version_status}', current version: "
            f"'{CURRENT_SCHEMA_VERSION}'). Run 'strategy doctor' to inspect or "
            f"'strategy migrate --apply' to upgrade before editing.",
        )

    raw_diags = (
        getattr(document, "error_diagnostics", None)
        or getattr(document, "diagnostics", None)
        or []
    )
    for diag in raw_diags:
        sev = (
            diag.get("level", "")
            if isinstance(diag, dict)
            else getattr(diag, "level", "")
        )
        if str(sev).lower() == "error":
            msg = (
                diag.get("message", "invalid strategy")
                if isinstance(diag, dict)
                else getattr(diag, "message", "invalid strategy")
            )
            raise CliError(
                "strategy_invalid",
                "Strategy file is not a valid authority document: " + str(msg),
            )


def _validate_artifact_exists(
    item_type: str,
    ref: str,
    repo_root: Path,
) -> None:
    """Raise ``CliError('strategy_unknown_ref')`` if the artifact doesn't exist.

    For tickets, checks if any ``.megaplan/tickets/*.md`` file has a matching
    ULID in its frontmatter.  For epics, checks if the initiative directory
    ``.megaplan/initiatives/<ref>`` exists.
    """
    if item_type == "ticket":
        from arnold_pipelines.megaplan.tickets.files import iterate_ticket_files as _iter

        found = False
        for _fpath, fm in _iter(str(repo_root)):
            if fm.get("id") == ref:
                found = True
                break
        if not found:
            raise CliError(
                "strategy_unknown_ref",
                f"Ticket '{ref}' not found in .megaplan/tickets/. "
                f"Create the ticket first, then add it to the roadmap.",
            )
    elif item_type == "epic":
        initiatives_dir = Path(repo_root) / ".megaplan" / "initiatives" / ref
        if not initiatives_dir.is_dir():
            raise CliError(
                "strategy_unknown_ref",
                f"Epic/initiative '{ref}' not found at {initiatives_dir}. "
                f"Create the initiative first, then add it to the roadmap.",
            )


def _roadmap_unchanged(
    before: "StrategyDocument",
    after: "StrategyDocument",
) -> bool:
    """Return True if *before* and *after* have identical roadmap entries."""
    if before is after:
        return True
    for horizon in REQUIRED_ROADMAP_SECTIONS:
        b_entries = before.roadmap.get(horizon, [])
        a_entries = after.roadmap.get(horizon, [])
        if len(b_entries) != len(a_entries):
            return False
        for be, ae in zip(b_entries, a_entries):
            if be.identity != ae.identity or be.horizon != ae.horizon:
                return False
    return True


# ---------------------------------------------------------------------------
# doctor
# ---------------------------------------------------------------------------


def handle_strategy_doctor(
    repo_root: Path,
    args: argparse.Namespace,
) -> StepResponse:
    """Inspect the repository and return structured migration diagnostics.

    Tolerates absent ``.megaplan/STRATEGY.md`` — reports ``status='ok'``
    and ``safe_to_apply=False`` without raising an error.

    Parameters
    ----------
    repo_root:
        Repository root directory.
    args:
        Parsed CLI arguments.  ``--json`` (optional) returns the full
        machine-readable :class:`MigrationReport` dictionary including
        findings, blockers, proposed actions, and ``safe_to_apply``.

    Returns
    -------
    StepResponse
        A structured response.  When ``--json`` is passed the response is
        the full serialized report dictionary; otherwise a compact summary
        with status, version_status, counts, and safe_to_apply.
    """
    json_flag = bool(getattr(args, "json", False))

    report = inspect_strategy_migration(repo_root)

    if json_flag:
        return _migration_report_to_dict(report)

    error_count = sum(1 for f in report.findings if f.severity == "error")
    warning_count = sum(1 for f in report.findings if f.severity == "warning")
    info_count = sum(1 for f in report.findings if f.severity == "info")

    return {
        "success": True,
        "step": "strategy",
        "action": "doctor",
        "status": report.status,
        "version_status": report.version_status,
        "schema_version": report.schema_version,
        "current_version": report.current_version,
        "safe_to_apply": report.safe_to_apply,
        "blockers": report.blockers,
        "error_count": error_count,
        "warning_count": warning_count,
        "info_count": info_count,
        "proposed_action_count": len(report.proposed_actions),
        "tickets_dir_exists": report.tickets_dir_exists,
        "strategy_file_path": report.strategy_file_path,
    }


# ---------------------------------------------------------------------------
# migrate (dry-run by default)
# ---------------------------------------------------------------------------


def handle_strategy_migrate(
    repo_root: Path,
    args: argparse.Namespace,
) -> StepResponse:
    """Dry-run strategy migration — inspect and report without mutating.

    By default this is a dry-run: it calls
    :func:`inspect_strategy_migration` and returns machine-readable
    diagnostics, proposed actions, blockers, backup paths that would be
    used, and ``safe_to_apply``.  No files are written.

    The ``--apply`` flag performs the supported reversible rewrites (eligible
    strategy version upgrade and ticket epics normalisation) with byte-for-byte
    backups, a SHA-256 manifest, and atomic writes — never renaming ticket
    files or inventing IDs.  Without ``--apply`` the command stays read-only.

    Parameters
    ----------
    repo_root:
        Repository root directory.
    args:
        Parsed CLI arguments.  ``args.apply`` (``--apply``) enables writes.

    Returns
    -------
    StepResponse
        With ``--apply``: the :func:`apply_strategy_migration` result
        describing what was applied and where backups were written.
        Without ``--apply``: a full machine-readable report as a dictionary
        with findings, blockers, proposed actions, backup paths, and
        ``safe_to_apply``.
    """
    if getattr(args, "apply", False):
        return apply_strategy_migration(repo_root)

    report = inspect_strategy_migration(repo_root)

    # Compute backup paths that would be used for each action.
    backup_paths = _compute_backup_paths(report, repo_root)

    return _migration_report_to_dict(report, backup_paths=backup_paths, action="migrate")


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------


def _migration_report_to_dict(
    report: MigrationReport,
    backup_paths: list[str] | None = None,
    action: str = "doctor",
) -> dict[str, Any]:
    """Serialize a :class:`MigrationReport` to a stable JSON-serializable dict.

    Parameters
    ----------
    report:
        The migration report to serialize.
    backup_paths:
        Optional list of backup file paths that would be created if the
        proposed actions were applied.  Used by the ``migrate`` handler.
    action:
        Label for the ``action`` field in the output (``"doctor"`` or
        ``"migrate"``).

    Returns
    -------
    dict
        A stable dictionary with all report fields and serialized findings,
        blockers, proposed actions, and optional backup paths.
    """
    serialized_findings: list[dict[str, Any]] = []
    for f in report.findings:
        d: dict[str, Any] = {
            "kind": f.kind,
            "severity": f.severity,
            "message": f.message,
        }
        if f.source is not None:
            d["source"] = f.source
        serialized_findings.append(d)

    serialized_actions: list[dict[str, Any]] = []
    for a in report.proposed_actions:
        ad: dict[str, Any] = {
            "action_id": a.action_id,
            "kind": a.kind,
            "description": a.description,
            "safe": a.safe,
        }
        if a.target is not None:
            ad["target"] = a.target
        serialized_actions.append(ad)

    # Serialize ticket inventory summary (avoid full entry detail).
    inventory_summary: dict[str, Any] | None = None
    if report.ticket_inventory is not None:
        inv = report.ticket_inventory
        inventory_summary = {
            "total_files": inv.total_files,
            "total_with_id": inv.total_with_id,
            "total_valid_ulid": inv.total_valid_ulid,
            "total_roadmap_eligible": inv.total_roadmap_eligible,
            "total_parse_errors": inv.total_with_parse_errors,
            "total_duplicate_ids": len(inv.duplicate_ids),
        }

    result: dict[str, Any] = {
        "success": True,
        "step": "strategy",
        "action": action,
        "status": report.status,
        "version_status": report.version_status,
        "schema_version": report.schema_version,
        "current_version": report.current_version,
        "safe_to_apply": report.safe_to_apply,
        "findings": serialized_findings,
        "blockers": report.blockers,
        "proposed_actions": serialized_actions,
        "tickets_dir_exists": report.tickets_dir_exists,
        "strategy_file_path": report.strategy_file_path,
        "ticket_inventory_summary": inventory_summary,
    }

    if backup_paths is not None:
        result["backup_paths"] = backup_paths

    return result


def _compute_backup_paths(
    report: MigrationReport,
    repo_root: Path,
) -> list[str]:
    """Compute backup file paths that would be created for each proposed action.

    For each file-targeted action, we derive a ``.bak`` sibling path.
    For repo-level actions (no target), no backup path is generated.
    """
    backup_paths: list[str] = []
    seen: set[str] = set()

    for action in report.proposed_actions:
        if action.target is None:
            continue
        target_path = Path(action.target)
        bak = str(target_path.with_suffix(target_path.suffix + ".bak"))
        if bak not in seen:
            seen.add(bak)
            backup_paths.append(bak)

    # Always include strategy backup if strategy exists.
    strategy_path = Path(report.strategy_file_path)
    if strategy_path.is_file():
        strategy_bak = str(strategy_path.with_suffix(strategy_path.suffix + ".bak"))
        if strategy_bak not in seen:
            seen.add(strategy_bak)
            backup_paths.append(strategy_bak)

    return backup_paths


# ---------------------------------------------------------------------------
# Dispatcher (for CLI wiring convenience)
# ---------------------------------------------------------------------------

_STRATEGY_HANDLERS: dict[str, Any] = {
    "init": handle_strategy_init,
    "validate": handle_strategy_validate,
    "show": handle_strategy_show,
    "list": handle_strategy_list,
    "project": handle_strategy_project,
    "add": handle_strategy_add,
    "remove": handle_strategy_remove,
    "move": handle_strategy_move,
    "doctor": handle_strategy_doctor,
    "migrate": handle_strategy_migrate,
}


def handle_strategy(
    repo_root: Path,
    args: argparse.Namespace,
) -> StepResponse:
    """Dispatch ``megaplan strategy ...`` subcommands.

    Parameters
    ----------
    repo_root:
        Repository root directory.
    args:
        Parsed CLI arguments.  Must carry a ``strategy_action`` attribute
        set to one of ``init``, ``validate``, ``show``, ``list``,
        ``project``, ``add``, ``remove``, ``move``, ``doctor``, or
        ``migrate``.

    Returns
    -------
    StepResponse
        The handler's structured response.

    Raises
    ------
    CliError
        If ``strategy_action`` is missing or unknown.
    """
    action: str | None = getattr(args, "strategy_action", None)
    if action is None:
        raise CliError(
            "invalid_args",
            "Missing strategy subcommand. Expected one of: "
            + ", ".join(sorted(_STRATEGY_HANDLERS)),
        )
    if action not in _STRATEGY_HANDLERS:
        raise CliError(
            "invalid_args",
            f"Unknown strategy action: {action}. "
            f"Expected one of: {', '.join(sorted(_STRATEGY_HANDLERS))}",
        )
    return _STRATEGY_HANDLERS[action](repo_root, args)
