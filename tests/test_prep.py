from __future__ import annotations

import megaplan.cli
from megaplan.handlers import handle_prep


def test_cli_registers_prep_command() -> None:
    parser = megaplan.cli.build_parser()
    parsed = parser.parse_args(["prep", "--plan", "demo"])

    assert parsed.command == "prep"
    assert parsed.plan == "demo"
    assert megaplan.cli.COMMAND_HANDLERS["prep"] is handle_prep
