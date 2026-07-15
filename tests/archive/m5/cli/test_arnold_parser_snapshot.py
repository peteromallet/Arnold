"""Archived with the deliberately deleted umbrella ``arnold`` CLI facade."""

from __future__ import annotations

import argparse

from arnold_pipelines.megaplan.cli import arnold, build_parser


EXPECTED_SURFACE = {
    "top_level": ["auto", "override", "pipelines", "run", "<module>"],
    "discovered_modules": [
        "creative",
        "doc",
        "epic-blitz",
        "evidence-pack",
        "jokes",
        "live-supervisor",
        "megaplan",
        "select-tournament",
        "writing-panel-strict",
    ],
    "pipelines_actions": ["check", "describe", "doctor", "list", "new"],
    "module_verbs": ["run", "check", "doctor", "describe", "auto"],
    "planning_module_verbs": ["run", "check", "doctor", "describe", "auto", "override"],
    "umbrella_override_actions": [
        "abort",
        "add-note",
        "set-robustness",
        "set-profile",
        "set-model",
        "set-vendor",
    ],
    "planning_override_actions": [
        "force-proceed",
        "replan",
        "recover-blocked",
        "resume-clarify",
    ],
    "megaplan_override_actions": [
        "abort",
        "adopt-execution",
        "force-proceed",
        "add-note",
        "replan",
        "recover-blocked",
        "resume-clarify",
        "set-robustness",
        "set-profile",
        "set-model",
        "set-vendor",
    ],
    "megaplan_override_options": {
        "effort": {"option_strings": ["--effort"], "choices": None, "action": "_StoreAction"},
        "expires_after_runs": {
            "option_strings": ["--expires-after-runs"],
            "choices": None,
            "action": "_StoreAction",
        },
        "model": {"option_strings": ["--model"], "choices": None, "action": "_StoreAction"},
        "note": {"option_strings": ["--note"], "choices": None, "action": "_StoreAction"},
        "phase": {"option_strings": ["--phase"], "choices": None, "action": "_StoreAction"},
        "plan": {"option_strings": ["--plan"], "choices": None, "action": "_StoreAction"},
        "profile": {"option_strings": ["--profile"], "choices": None, "action": "_StoreAction"},
        "project_dir": {
            "option_strings": ["--project-dir"],
            "choices": None,
            "action": "_StoreAction",
        },
        "reason": {"option_strings": ["--reason"], "choices": None, "action": "_StoreAction"},
        "robustness": {
            "option_strings": ["--robustness"],
            "choices": [
                "bare",
                "light",
                "full",
                "thorough",
                "extreme",
                "tiny",
                "standard",
                "robust",
                "superrobust",
            ],
            "action": "_StoreAction",
        },
        "source": {
            "option_strings": ["--source"],
            "choices": ["user", "driver"],
            "action": "_StoreAction",
        },
        "user_approved": {
            "option_strings": ["--user-approved"],
            "choices": None,
            "action": "_StoreTrueAction",
        },
        "target_root": {
            "option_strings": ["--target-root"],
            "choices": None,
            "action": "_StoreAction",
        },
        "vendor": {"option_strings": ["--vendor"], "choices": None, "action": "_StoreAction"},
    },
}


def _megaplan_override_parser() -> argparse.ArgumentParser:
    root = build_parser()
    subparsers = next(
        action for action in root._actions if isinstance(action, argparse._SubParsersAction)
    )
    return subparsers.choices["override"]


def _megaplan_override_choices() -> list[str]:
    parser = _megaplan_override_parser()
    positional = next(action for action in parser._actions if action.dest == "override_action")
    return list(positional.choices or [])


def _megaplan_override_options() -> dict[str, dict[str, object]]:
    parser = _megaplan_override_parser()
    surface: dict[str, dict[str, object]] = {}
    for action in parser._actions:
        if not action.option_strings or isinstance(action, argparse._HelpAction):
            continue
        surface[action.dest] = {
            "option_strings": sorted(action.option_strings),
            "choices": list(action.choices) if action.choices is not None else None,
            "action": type(action).__name__,
        }
    return surface


def _current_surface() -> dict[str, object]:
    return {
        "top_level": ["auto", "override", "pipelines", "run", "<module>"],
        "discovered_modules": sorted(arnold._discovered_module_names()),
        "pipelines_actions": list(arnold.PIPELINES_ACTIONS),
        "module_verbs": list(arnold.MODULE_VERBS),
        "planning_module_verbs": list(arnold.PLANNING_MODULE_VERBS),
        "umbrella_override_actions": list(arnold.UMBRELLA_OVERRIDE_ACTIONS),
        "planning_override_actions": list(arnold.PLANNING_OVERRIDE_ACTIONS),
        "megaplan_override_actions": _megaplan_override_choices(),
        "megaplan_override_options": _megaplan_override_options(),
    }


def test_arnold_parser_surface_snapshot_auto_fails_on_drift() -> None:
    assert _current_surface() == EXPECTED_SURFACE


def test_arnold_override_dispatch_split(monkeypatch, capsys) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(arnold, "_megaplan_main", lambda argv: calls.append(list(argv)) or 0)

    assert arnold.main(["override", "add-note", "--plan", "demo", "--note", "context"]) == 0
    assert arnold.main(["megaplan", "override", "force-proceed", "--plan", "demo"]) == 0
    assert calls == [
        ["override", "add-note", "--plan", "demo", "--note", "context"],
        ["override", "force-proceed", "--plan", "demo"],
    ]

    assert arnold.main(["override", "force-proceed", "--plan", "demo"]) == 2
    assert arnold.main(["megaplan", "override", "add-note", "--plan", "demo"]) == 2
    assert calls == [
        ["override", "add-note", "--plan", "demo", "--note", "context"],
        ["override", "force-proceed", "--plan", "demo"],
    ]

    err = capsys.readouterr().err
    assert "use 'arnold megaplan override force-proceed'" in err
    assert "use 'arnold override add-note'" in err
