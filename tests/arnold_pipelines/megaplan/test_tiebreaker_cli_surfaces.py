from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from arnold_pipelines.megaplan import cli
from arnold_pipelines.megaplan.handlers import (
    handle_tiebreaker_decide,
    handle_tiebreaker_run,
)
from arnold_pipelines.megaplan.prompts import tiebreaker_orchestrator


def test_parser_accepts_auto_tiebreaker_commands() -> None:
    parser = cli.build_parser()

    run_args = parser.parse_args(["tiebreaker-run", "--plan", "demo"])
    decide_args = parser.parse_args(
        [
            "tiebreaker",
            "decide",
            "--plan",
            "demo",
            "--pick",
            "option-a",
            "--rationale",
            "Evidence supports option A.",
        ]
    )

    assert run_args.command == "tiebreaker-run"
    assert run_args.plan == "demo"
    assert decide_args.command == "tiebreaker"
    assert decide_args.tiebreaker_action == "decide"
    assert decide_args.pick == "option-a"


def test_parser_rejects_split_tiebreaker_aliases() -> None:
    parser = cli.build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["tiebreaker"])
    with pytest.raises(SystemExit):
        parser.parse_args(
            [
                "tiebreaker",
                "decide",
                "--plan",
                "demo",
                "--pick",
                "option-a",
            ]
        )
    with pytest.raises(SystemExit):
        parser.parse_args(["tiebreaker-decide", "--plan", "demo"])


def test_tiebreaker_run_dispatches_existing_canonical_handler(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def fake_handler(root: Path, args: argparse.Namespace) -> dict[str, object]:
        seen["root"] = root
        seen["args"] = args
        return {"success": True, "step": "tiebreaker_run"}

    monkeypatch.setattr(cli, "maybe_auto_sync_repo_editor_support", lambda _root: None)
    monkeypatch.setattr(cli, "pre_commit_hook_status", lambda _root: ("missing", None))
    monkeypatch.setattr(cli, "_auto_sync_installed_skills", lambda: None)
    monkeypatch.setattr(cli, "_resolve_project_root", lambda _args: Path("/tmp/demo"))
    monkeypatch.setattr(cli, "ensure_runtime_layout", lambda _root: None)
    monkeypatch.setitem(cli.COMMAND_HANDLERS, "tiebreaker-run", fake_handler)

    rc = cli.main(["tiebreaker-run", "--plan", "demo"])

    assert rc == 0
    assert seen["root"] == Path("/tmp/demo")
    args = seen["args"]
    assert isinstance(args, argparse.Namespace)
    assert args.command == "tiebreaker-run"
    assert args.plan == "demo"


def test_tiebreaker_decide_dispatches_existing_canonical_handler(
    monkeypatch,
    tmp_path: Path,
) -> None:
    seen: dict[str, object] = {}
    plan_dir = tmp_path / ".megaplan" / "plans" / "demo"

    def fake_handler(root: Path, args: argparse.Namespace) -> dict[str, object]:
        seen["root"] = root
        seen["args"] = args
        return {"success": True, "step": "tiebreaker_decision"}

    monkeypatch.setattr(
        tiebreaker_orchestrator,
        "resolve_plan_dir",
        lambda _root, _plan: plan_dir,
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan._core.io.read_plan_state_cached",
        lambda _plan_dir, mode: {"name": "demo"},
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.handlers.handle_tiebreaker_decide",
        fake_handler,
    )
    args = cli.build_parser().parse_args(
        [
            "tiebreaker",
            "decide",
            "--plan",
            "demo",
            "--escalate",
            "--rationale",
            "A human decision is required.",
        ]
    )

    rc = tiebreaker_orchestrator.run_tiebreaker_cli(tmp_path, args)

    assert rc == 0
    assert seen["root"] == tmp_path
    assert seen["args"] is args


def test_command_table_uses_exported_handler_without_alias() -> None:
    assert cli.COMMAND_HANDLERS["tiebreaker-run"] is handle_tiebreaker_run
    assert handle_tiebreaker_decide is not handle_tiebreaker_run
    assert "tiebreaker-decide" not in cli.COMMAND_HANDLERS
