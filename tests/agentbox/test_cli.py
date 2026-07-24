from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from agentbox.cli import build_parser, main
from agentbox.config import AgentBoxConfig
from agentbox.guardian.scheduler import ensure_guardian_tasks
from agentbox.guardian.state import GuardianStateStore


def test_cli_guardian_run_once_executes_one_tick_and_exits(tmp_path, monkeypatch) -> None:
    config = AgentBoxConfig(workspace_root=tmp_path / "agentbox")
    monkeypatch.setenv("AGENTBOX_CONFIG", str(tmp_path / "agentbox.yaml"))
    config.workspace_root.mkdir(parents=True, exist_ok=True)
    (tmp_path / "agentbox.yaml").write_text(
        f"workspace_root: {tmp_path / 'agentbox'}\n", encoding="utf-8"
    )

    ensure_guardian_tasks(config, datetime(2026, 1, 1, tzinfo=UTC))

    result = main(["guardian", "run-once", "--json"])

    assert result == 0


def test_cli_guardian_pause_and_resume_persist_across_invocations(
    tmp_path, monkeypatch
) -> None:
    config = AgentBoxConfig(workspace_root=tmp_path / "agentbox")
    monkeypatch.setenv("AGENTBOX_CONFIG", str(tmp_path / "agentbox.yaml"))
    config.workspace_root.mkdir(parents=True, exist_ok=True)
    (tmp_path / "agentbox.yaml").write_text(
        f"workspace_root: {tmp_path / 'agentbox'}\n", encoding="utf-8"
    )

    pause_result = main(["guardian", "pause", "--json"])
    assert pause_result == 0

    state = GuardianStateStore(config).read()
    assert state["global_pause"]["paused"] is True

    resume_result = main(["guardian", "resume", "--json"])
    assert resume_result == 0

    state = GuardianStateStore(config).read()
    assert state["global_pause"]["paused"] is False


def test_cli_guardian_status_outputs_valid_json(tmp_path, monkeypatch) -> None:
    config = AgentBoxConfig(workspace_root=tmp_path / "agentbox")
    monkeypatch.setenv("AGENTBOX_CONFIG", str(tmp_path / "agentbox.yaml"))
    config.workspace_root.mkdir(parents=True, exist_ok=True)
    (tmp_path / "agentbox.yaml").write_text(
        f"workspace_root: {tmp_path / 'agentbox'}\n", encoding="utf-8"
    )

    ensure_guardian_tasks(config, datetime(2026, 1, 1, tzinfo=UTC))

    result = main(["guardian", "status", "--json"])

    assert result == 0


def test_cli_guardian_parser_has_all_subcommands() -> None:
    parser = build_parser()
    args = parser.parse_args(["guardian", "run-once"])
    assert args.command == "guardian"
    assert args.guardian_command == "run-once"

    args = parser.parse_args(["guardian", "run", "--poll-interval", "30"])
    assert args.guardian_command == "run"
    assert args.poll_interval == 30.0

    args = parser.parse_args(["guardian", "pause"])
    assert args.guardian_command == "pause"

    args = parser.parse_args(["guardian", "resume"])
    assert args.guardian_command == "resume"

    args = parser.parse_args(["guardian", "status", "--json"])
    assert args.guardian_command == "status"
    assert args.json is True
