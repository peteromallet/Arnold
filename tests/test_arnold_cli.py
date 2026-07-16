"""Current top-level Arnold CLI coverage at the historical selector path."""

from __future__ import annotations

from arnold import cli


def test_top_level_help_names_only_current_command_families(capsys) -> None:
    assert cli.main(["--help"]) == 0

    output = capsys.readouterr().out
    assert "arnold workflow" in output
    assert "status,trace,inspect,override" in output
    assert "pipelines" not in output
    assert "megaplan" not in output


def test_unknown_legacy_command_fails_closed(capsys) -> None:
    assert cli.main(["pipelines", "list"]) == 2

    error = capsys.readouterr().err
    assert "unknown command 'pipelines'" in error
    assert "usage: arnold workflow" in error
