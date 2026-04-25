"""CLI entrypoints for megaplan bake-off commands."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Callable

from megaplan.types import CliError


BAKEOFF_UNSUPPORTED_MODE_MESSAGE = (
    "bake-off v1 supports --mode code only; doc/joke/metaplan require "
    "--output pass-through, deferred to a follow-up."
)


def _register_bakeoff_subcommands(bakeoff_parser: argparse.ArgumentParser) -> None:
    bakeoff_sub = bakeoff_parser.add_subparsers(dest="bakeoff_action", required=True)

    run_parser = bakeoff_sub.add_parser(
        "run",
        help="Run the same idea through multiple profiles concurrently",
    )
    run_parser.add_argument("--idea-file", required=True, help="Path to the idea file")
    run_parser.add_argument(
        "--profiles",
        nargs="+",
        required=True,
        help="Profile names to compare",
    )
    run_parser.add_argument(
        "--mode",
        default="code",
        help="Bake-off mode (v1 supports code only)",
    )
    run_parser.add_argument("--exp-id", default=None, help="Optional experiment id")
    run_parser.add_argument(
        "--detach",
        action="store_true",
        help="Launch and return without streaming live status",
    )
    run_parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="Allow starting from a dirty main worktree",
    )

    status_parser = bakeoff_sub.add_parser("status", help="Show bake-off status")
    status_parser.add_argument("--exp", default=None, help="Experiment id")

    tail_parser = bakeoff_sub.add_parser("tail", help="Tail bake-off logs")
    tail_parser.add_argument("--exp", required=True, help="Experiment id")
    tail_parser.add_argument("--profile", default=None, help="Profile to tail")

    compare_parser = bakeoff_sub.add_parser(
        "compare",
        help="Collect metrics and optionally run a judge",
    )
    compare_parser.add_argument("--exp", required=True, help="Experiment id")
    compare_parser.add_argument(
        "--judge",
        default=None,
        help="Judge model, 'auto', or omit to skip judging",
    )
    compare_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing comparison",
    )

    pick_parser = bakeoff_sub.add_parser("pick", help="Record the human-selected winner")
    pick_parser.add_argument("--exp", required=True, help="Experiment id")
    pick_parser.add_argument("--profile", required=True, help="Chosen profile")
    pick_parser.add_argument("--rationale", default=None, help="Selection rationale")

    merge_parser = bakeoff_sub.add_parser("merge", help="Merge the selected profile")
    merge_parser.add_argument("--exp", required=True, help="Experiment id")

    resume_parser = bakeoff_sub.add_parser("resume", help="Resume unfinished profiles")
    resume_parser.add_argument("--exp", required=True, help="Experiment id")

    abandon_parser = bakeoff_sub.add_parser("abandon", help="Remove worktrees and keep audit data")
    abandon_parser.add_argument("--exp", required=True, help="Experiment id")


def run_bakeoff_cli(root: Path, args: argparse.Namespace) -> int:
    action = getattr(args, "bakeoff_action")

    if action == "run":
        if getattr(args, "mode", "code") != "code":
            raise CliError("bakeoff_unsupported_mode", BAKEOFF_UNSUPPORTED_MODE_MESSAGE)
        from megaplan.bakeoff.orchestrator import run_bakeoff_run_handler

        return run_bakeoff_run_handler(root, args)

    handlers: dict[str, Callable[[Path, argparse.Namespace], int]] = _load_handlers()
    handler = handlers.get(action)
    if handler is None:
        raise CliError("invalid_args", f"Unknown bakeoff action: {action}")
    return handler(root, args)


def build_bakeoff_parser(subparsers: Any) -> None:
    bakeoff_parser = subparsers.add_parser(
        "bakeoff",
        help="Run concurrent multi-profile bake-offs",
    )
    _register_bakeoff_subcommands(bakeoff_parser)


def _load_handlers() -> dict[str, Callable[[Path, argparse.Namespace], int]]:
    from megaplan.bakeoff.handlers import (
        handle_abandon,
        handle_compare,
        handle_merge,
        handle_pick,
        handle_resume,
        handle_status,
        handle_tail,
    )

    return {
        "abandon": handle_abandon,
        "compare": handle_compare,
        "merge": handle_merge,
        "pick": handle_pick,
        "resume": handle_resume,
        "status": handle_status,
        "tail": handle_tail,
    }
