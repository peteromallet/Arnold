"""CLI command registration and parser tests.

Verify that automation commands are properly registered in both the
argument parser and the handler dispatch table.
"""

from __future__ import annotations

from arnold_pipelines.megaplan.cli import COMMAND_HANDLERS, build_parser


def test_automation_commands_registered_in_parser_and_handler_table() -> None:
    parser = build_parser()
    subparsers_action = next(
        action for action in parser._actions if action.dest == "command"
    )
    parser_commands = set(subparsers_action.choices)
    automation_commands = {
        "status",
        "audit",
        "progress",
        "watch",
        "resume",
        "verify-human",
        "audit-verifiability",
    }

    assert automation_commands <= set(COMMAND_HANDLERS)
    assert automation_commands <= parser_commands


def test_status_command_accepts_plan_flag() -> None:
    args = build_parser().parse_args(["status", "--plan", "demo-plan"])

    assert args.command == "status"
    assert args.plan == "demo-plan"
