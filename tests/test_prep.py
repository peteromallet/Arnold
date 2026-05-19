from __future__ import annotations

import megaplan.cli
from megaplan.handlers import handle_prep


def test_cli_registers_prep_command() -> None:
    parser = megaplan.cli.build_parser()
    parsed = parser.parse_args(["prep", "--plan", "demo"])

    assert parsed.command == "prep"
    assert parsed.plan == "demo"
    assert megaplan.cli.COMMAND_HANDLERS["prep"] is handle_prep


def test_cli_prep_direction_flag_parses() -> None:
    parser = megaplan.cli.build_parser()
    parsed = parser.parse_args(
        ["prep", "--plan", "demo", "--direction", "trace shutdown path"]
    )
    assert parsed.prep_direction == "trace shutdown path"


def test_cli_prep_direction_defaults_to_none() -> None:
    parser = megaplan.cli.build_parser()
    parsed = parser.parse_args(["prep", "--plan", "demo"])
    assert parsed.prep_direction is None


def test_cli_init_prep_direction_flag_parses(tmp_path) -> None:
    parser = megaplan.cli.build_parser()
    parsed = parser.parse_args(
        [
            "init",
            "--project-dir",
            str(tmp_path),
            "--prep-direction",
            "focus on cache invalidation",
            "an idea",
        ]
    )
    assert parsed.prep_direction == "focus on cache invalidation"
