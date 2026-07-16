"""Current CLI surface at the historical parser-selection path.

The M5 lifecycle contract selected this path before the legacy umbrella CLI was
retired.  Keep the path as an active conformance test without reviving the
deleted ``arnold_pipelines.megaplan.cli.arnold`` implementation.
"""

from __future__ import annotations

import argparse
import importlib.util

from arnold.cli.workflow import build_parser


EXPECTED_WORKFLOW_COMMANDS = {
    "check",
    "compile",
    "describe",
    "dot",
    "dry-run",
    "explain",
    "graph",
    "inspect",
    "manifest",
    "resume",
    "run",
}


def test_current_workflow_parser_surface_is_explicit() -> None:
    parser = build_parser()
    commands = next(
        action
        for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
    )

    assert set(commands.choices) == EXPECTED_WORKFLOW_COMMANDS


def test_retired_umbrella_cli_is_not_silently_restored() -> None:
    assert importlib.util.find_spec("arnold_pipelines.megaplan.cli.arnold") is None
