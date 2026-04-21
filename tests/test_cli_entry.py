from __future__ import annotations

import argparse
import sys

import pytest

from megaplan.cli import cli_entry
from megaplan.cloud.cli import _register_cloud_subcommands, build_cloud_parser


def _invoke_cli_entry() -> None:
    cli_entry()


def _subcommands(parser: argparse.ArgumentParser) -> set[str]:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return set(action.choices)
    raise AssertionError("parser did not register any subcommands")


def _subparser(parser: argparse.ArgumentParser, name: str) -> argparse.ArgumentParser:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return action.choices[name]
    raise AssertionError(f"parser did not register subcommand {name!r}")


def test_build_cloud_parser_matches_register_cloud_subcommands() -> None:
    top_level = argparse.ArgumentParser()
    top_level_subparsers = top_level.add_subparsers(dest="command", required=True)
    build_cloud_parser(top_level_subparsers)

    standalone = argparse.ArgumentParser(prog="megaplan cloud")
    _register_cloud_subcommands(standalone)

    cloud_parser = _subparser(top_level, "cloud")
    assert _subcommands(cloud_parser) == _subcommands(standalone)


def test_cli_entry_lazy_cloud_help(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(sys, "argv", ["megaplan", "cloud", "status", "--help"])

    with pytest.raises(SystemExit) as info:
        _invoke_cli_entry()

    assert info.value.code == 0
    output = capsys.readouterr().out
    assert "usage: megaplan cloud status" in output
    assert "--plan" in output
