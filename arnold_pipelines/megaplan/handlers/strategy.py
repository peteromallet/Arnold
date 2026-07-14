"""Read-only CLI command handlers for ``megaplan strategy ...`` subcommands.

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
    format_diagnostics,
    load_strategy,
    load_strategy_projection,
    project_to_dict,
    project_to_json,
    strategy_file_path,
    strategy_projection_file_path,
    write_projection,
)
from arnold_pipelines.megaplan.strategy.contract import (
    RoadmapEntry,
    RoadmapHorizon,
    StrategyDiagnostic,
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

    document = load_strategy(repo_root)
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

    document = load_strategy(repo_root)
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
        Parsed CLI arguments.  ``--horizon`` (optional) filters entries to
        a specific horizon (``Now``, ``Next``, or ``Later``).

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

    if horizon_filter is not None and horizon_filter not in REQUIRED_ROADMAP_SECTIONS:
        valid = ", ".join(REQUIRED_ROADMAP_SECTIONS)
        raise CliError(
            "invalid_args",
            f"Invalid horizon '{horizon_filter}'. Must be one of: {valid}",
        )

    document = load_strategy(repo_root)

    entries: list[dict[str, Any]] = []
    for horizon in REQUIRED_ROADMAP_SECTIONS:
        if horizon_filter is not None and horizon != horizon_filter:
            continue
        for entry in document.roadmap.get(horizon, []):
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

    return {
        "success": True,
        "step": "strategy",
        "action": "list",
        "horizon_filter": horizon_filter,
        "total_entries": len(entries),
        "entries": entries,
        "error_count": error_count,
        # Include a diagnostics summary for stale-title awareness.
        "warning_count": sum(
            1 for d in diagnostics if d["severity"] == "warning"
        ),
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

    document = load_strategy(repo_root)
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

    # Default: print to stdout.
    print(projection_json, end="")
    return {
        "success": True,
        "step": "strategy",
        "action": "project",
        "output": "stdout",
    }


# ---------------------------------------------------------------------------
# Dispatcher (for CLI wiring convenience)
# ---------------------------------------------------------------------------

_STRATEGY_HANDLERS: dict[str, Any] = {
    "init": handle_strategy_init,
    "validate": handle_strategy_validate,
    "show": handle_strategy_show,
    "list": handle_strategy_list,
    "project": handle_strategy_project,
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
        set to one of ``init``, ``validate``, ``show``, ``list``, or
        ``project``.

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
