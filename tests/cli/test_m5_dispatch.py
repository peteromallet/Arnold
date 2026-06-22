from __future__ import annotations

import argparse
import sys

import pytest

import arnold.cli as cli_package
from arnold.cli.workflow import main as workflow_main


EXPECTED_WORKFLOW_SUBCOMMANDS = [
    "check",
    "describe",
    "dot",
    "dry-run",
    "manifest",
    "resume",
    "run",
]

EXPECTED_OPERATOR_COMMANDS = ["inspect", "override", "status", "trace"]


def _workflow_parser() -> argparse.ArgumentParser:
    # workflow.main builds the parser internally; exercise it by parsing --help.
    import io

    buf = io.StringIO()
    try:
        workflow_main(["--help"], out=buf)
    except SystemExit:
        pass
    # We cannot easily get the parser object back, so build a lightweight mirror
    # by importing the module and calling its internal helper indirectly.
    import arnold.cli.workflow as workflow_mod

    return workflow_mod.main.__code__  # type: ignore[attr-defined]


def test_workflow_subcommand_surface() -> None:
    """Snapshot of workflow subcommands exposed by arnold.cli.workflow."""

    import arnold.cli.workflow as workflow_mod

    # Build the parser by calling main with a --help trap.
    parser = None
    original_parse_args = argparse.ArgumentParser.parse_args

    def capture_parser(self, args=None, namespace=None):
        nonlocal parser
        parser = self
        raise SystemExit

    argparse.ArgumentParser.parse_args = capture_parser  # type: ignore[method-assign]
    try:
        try:
            workflow_mod.main(["--help"])
        except SystemExit:
            pass
    finally:
        argparse.ArgumentParser.parse_args = original_parse_args

    assert parser is not None
    subparsers_action = next(
        action for action in parser._actions if isinstance(action, argparse._SubParsersAction)
    )
    assert sorted(subparsers_action.choices) == EXPECTED_WORKFLOW_SUBCOMMANDS


def test_top_level_dispatch_routes_workflow_without_importing_legacy_modules() -> None:
    """arnold workflow ... must not trigger an import of legacy Megaplan CLI modules."""

    before = set(sys.modules.keys())
    rc = cli_package.main(["workflow", "check", "--module", "tests.fixtures.workflow.demo_pipeline:build_pipeline"])
    imported = set(sys.modules.keys()) - before

    forbidden = {
        name
        for name in imported
        if name == "arnold_pipelines.megaplan.cli.arnold"
        or name.startswith("arnold_pipelines.megaplan.cli")
    }
    assert rc == 0
    assert not forbidden, f"workflow dispatch imported legacy modules: {forbidden}"


def test_top_level_dispatch_routes_operator_commands(capsys) -> None:
    """arnold status/trace/inspect/override route to the operators module."""

    for cmd in EXPECTED_OPERATOR_COMMANDS:
        try:
            cli_package.main([cmd, "--help"])
        except SystemExit:
            pass
        out, err = capsys.readouterr()
        combined = out + err
        assert f"usage: arnold {cmd}" in combined, f"{cmd} did not route to operators module"


