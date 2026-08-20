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


def test_config_command_restores_complete_parser_contract() -> None:
    parser = build_parser()

    show = parser.parse_args(["config", "show"])
    set_value = parser.parse_args(
        ["config", "set", "execution.auto_approve", "true"]
    )
    reset = parser.parse_args(["config", "reset"])
    profiles_list = parser.parse_args(["config", "profiles", "list"])
    profiles_show = parser.parse_args(
        ["config", "profiles", "show", "partnered-5"]
    )
    use_profile = parser.parse_args(
        ["config", "use-profile", "partnered-5"]
    )

    assert (show.command, show.config_action) == ("config", "show")
    assert (set_value.key, set_value.value) == (
        "execution.auto_approve",
        "true",
    )
    assert reset.config_action == "reset"
    assert profiles_list.profiles_action == "list"
    assert profiles_show.profiles_action == "show"
    assert profiles_show.name == "partnered-5"
    assert use_profile.config_action == "use-profile"
    assert use_profile.name == "partnered-5"
