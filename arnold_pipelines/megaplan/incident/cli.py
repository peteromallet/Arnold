"""CLI entrypoints for ``megaplan incident`` commands.

Implements ``list --active`` (stable JSON) and ``brief <id_or_session>``
with clean unknown-id failures and integrity messages that recommend
``system.integrity_repair`` without performing or implying a repair
side effect.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from arnold_pipelines.megaplan.incident.projection import build_brief, list_incidents
from arnold_pipelines.megaplan.types import CliError


def register_incident_subcommands(parser: argparse.ArgumentParser) -> None:
    """Register ``list`` and ``brief`` sub-commands on *parser*."""
    sub = parser.add_subparsers(dest="incident_action", required=True)

    list_parser = sub.add_parser(
        "list",
        help="List incidents (active by default)",
    )
    list_parser.add_argument(
        "--active",
        action="store_true",
        default=True,
        help="Only show active (non-terminal) incidents (default: True)",
    )
    list_parser.add_argument(
        "--all",
        action="store_true",
        dest="show_all",
        help="Show all incidents including terminal ones",
    )

    brief_parser = sub.add_parser(
        "brief",
        help="Build a bounded incident brief by incident or session id",
    )
    brief_parser.add_argument(
        "id_or_session",
        help="Incident id or session id to look up",
    )
    brief_parser.add_argument(
        "--now",
        default=None,
        help="ISO-8601-like reference timestamp for deadline classification",
    )


def run_incident_cli(root: Path, args: argparse.Namespace) -> int:
    """Execute the resolved incident sub-command.

    Returns an exit code (0 on success, 1 on error).  Output is emitted
    as stable JSON to stdout.
    """
    action: str = getattr(args, "incident_action", "")

    if action == "list":
        return _run_list(root, args)
    if action == "brief":
        return _run_brief(root, args)

    raise CliError(
        "invalid_args",
        f"Unknown incident action: {action!r}",
    )


# ---------------------------------------------------------------------------
# Sub-command implementations
# ---------------------------------------------------------------------------


def _run_list(root: Path, args: argparse.Namespace) -> int:
    show_all: bool = getattr(args, "show_all", False)
    active_only = not show_all

    incidents = list_incidents(active_only=active_only, root=root)
    _emit_json(incidents)
    return 0


def _run_brief(root: Path, args: argparse.Namespace) -> int:
    id_or_session: str = args.id_or_session
    now: str | None = getattr(args, "now", None)

    brief = build_brief(id_or_session=id_or_session, root=root, now=now)
    _emit_json(brief)

    # build_brief returns {"found": False, ...} for unknown ids — this is a
    # clean response, not a process error.  The caller can inspect ``found``.
    return 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _emit_json(payload: Any) -> None:
    """Write *payload* as stable (sorted-keys, indented) JSON to stdout."""
    sys.stdout.write(
        json.dumps(payload, sort_keys=True, indent=2, default=str) + "\n"
    )
