from __future__ import annotations

from arnold_pipelines.megaplan.cli import build_parser


def test_recovery_commands_are_registered_on_megaplan_parser() -> None:
    parser = build_parser()

    override = parser.parse_args(
        [
            "override",
            "add-note",
            "--plan",
            "demo-plan",
            "--source",
            "repair-loop-dev-fix",
            "--note",
            "Prep clarification answers: use surviving workflow modules.",
        ]
    )
    assert override.command == "override"
    assert override.override_action == "add-note"
    assert override.source == "repair-loop-dev-fix"

    resume = parser.parse_args(["override", "resume-clarify", "--plan", "demo-plan"])
    assert resume.command == "override"
    assert resume.override_action == "resume-clarify"

    user_action = parser.parse_args(
        [
            "user-action",
            "resolve",
            "--plan",
            "demo-plan",
            "--action-id",
            "ua-1",
            "--resolution",
            "satisfied",
            "--reason",
            "Evidence already exists.",
        ]
    )
    assert user_action.command == "user-action"
    assert user_action.user_action_action == "resolve"
    assert user_action.action_id == "ua-1"

    quality_gate = parser.parse_args(
        [
            "quality-gate",
            "resolve",
            "--plan",
            "demo-plan",
            "--blocker-id",
            "quality:coverage",
            "--resolution",
            "fixed",
        ]
    )
    assert quality_gate.command == "quality-gate"
    assert quality_gate.quality_gate_action == "resolve"
    assert quality_gate.blocker_id == "quality:coverage"
