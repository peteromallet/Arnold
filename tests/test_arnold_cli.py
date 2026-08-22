"""Current top-level Arnold CLI coverage at the historical selector path."""

from __future__ import annotations

import sys
from pathlib import Path

from arnold import cli


def _expected_prog() -> str:
    # The dispatcher derives its usage prefix from argv0, like the console
    # script name it ships as (``megaplan``).
    return Path(sys.argv[0]).stem or "arnold"


def test_top_level_help_names_only_current_command_families(capsys) -> None:
    assert cli.main(["--help"]) == 0

    output = capsys.readouterr().out
    assert f"{_expected_prog()} workflow" in output
    assert "status,trace,inspect,override" in output
    assert "pipelines" not in output
    assert "megaplan" not in output


def test_unknown_legacy_command_fails_closed(capsys) -> None:
    assert cli.main(["pipelines", "list"]) == 2

    error = capsys.readouterr().err
    assert "unknown command 'pipelines'" in error
    assert f"usage: {_expected_prog()} workflow" in error
