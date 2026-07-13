from __future__ import annotations

import shutil

from agentbox.cli import build_parser, main


def test_cli_bootstrap_runs_and_emits_json(tmp_path, monkeypatch, capsys) -> None:
    workspace = tmp_path / "workspace"
    monkeypatch.setenv("AGENTBOX_CONFIG", str(tmp_path / "agentbox.yaml"))
    (tmp_path / "agentbox.yaml").write_text(
        f"workspace_root: {workspace}\n", encoding="utf-8"
    )

    result = main(["bootstrap", "--json"])

    assert result == 0
    captured = capsys.readouterr()
    assert "arnold-guardian" in captured.out


def test_cli_doctor_reports_ok_after_bootstrap(tmp_path, monkeypatch, capsys) -> None:
    workspace = tmp_path / "workspace"
    monkeypatch.setenv("AGENTBOX_CONFIG", str(tmp_path / "agentbox.yaml"))
    (tmp_path / "agentbox.yaml").write_text(
        f"workspace_root: {workspace}\n", encoding="utf-8"
    )
    main(["bootstrap", "--json"])
    monkeypatch.setattr(shutil, "which", lambda name: f"/usr/bin/{name}")

    result = main(["doctor", "--json"])
    captured = capsys.readouterr()

    assert result == 0
    assert "ok" in captured.out


def test_cli_services_list_returns_expected_names(tmp_path, monkeypatch, capsys) -> None:
    workspace = tmp_path / "workspace"
    monkeypatch.setenv("AGENTBOX_CONFIG", str(tmp_path / "agentbox.yaml"))
    (tmp_path / "agentbox.yaml").write_text(
        f"workspace_root: {workspace}\n", encoding="utf-8"
    )
    monkeypatch.setattr(shutil, "which", lambda name: None if name == "systemctl" else f"/usr/bin/{name}")

    result = main(["services", "list", "--json"])
    captured = capsys.readouterr()

    assert result == 0
    assert "arnold-guardian" in captured.out
    assert "agentbox-discord-resident" in captured.out


def test_cli_services_restart_returns_failure_when_safety_gate_refuses(
    tmp_path, monkeypatch, capsys
) -> None:
    workspace = tmp_path / "workspace"
    monkeypatch.setenv("AGENTBOX_CONFIG", str(tmp_path / "agentbox.yaml"))
    (tmp_path / "agentbox.yaml").write_text(
        f"workspace_root: {workspace}\n", encoding="utf-8"
    )
    monkeypatch.setattr(
        "agentbox.cli.restart_service",
        lambda service, **kwargs: {"ok": False, "error": "unsafe unit"},
    )

    result = main(
        ["services", "restart", "agentbox-discord-resident", "--json"]
    )

    assert result == 1
    assert "unsafe unit" in capsys.readouterr().out


def test_cli_version_outputs_version(tmp_path, monkeypatch, capsys) -> None:
    workspace = tmp_path / "workspace"
    monkeypatch.setenv("AGENTBOX_CONFIG", str(tmp_path / "agentbox.yaml"))
    (tmp_path / "agentbox.yaml").write_text(
        f"workspace_root: {workspace}\n", encoding="utf-8"
    )

    result = main(["version", "--json"])
    captured = capsys.readouterr()

    assert result == 0
    assert "agentbox" in captured.out


def test_cli_notify_test_with_mock_sink(tmp_path, monkeypatch, capsys) -> None:
    workspace = tmp_path / "workspace"
    monkeypatch.setenv("AGENTBOX_CONFIG", str(tmp_path / "agentbox.yaml"))
    (tmp_path / "agentbox.yaml").write_text(
        f"workspace_root: {workspace}\n", encoding="utf-8"
    )

    def fake_notify_test(config, *, conversation_key, dm_user_id, outbound=None):
        return {"ok": True, "conversation_key": conversation_key, "message_id": "sent"}

    monkeypatch.setattr("agentbox.cli.notify_test", fake_notify_test)

    result = main(["notify", "test", "--conversation-key", "discord:dm:123", "--json"])
    captured = capsys.readouterr()

    assert result == 0
    assert "ok" in captured.out


def test_cli_parser_has_new_commands() -> None:
    parser = build_parser()

    args = parser.parse_args(["bootstrap"])
    assert args.command == "bootstrap"

    args = parser.parse_args(["doctor", "--json"])
    assert args.command == "doctor"
    assert args.json is True

    args = parser.parse_args(["services", "list"])
    assert args.command == "services"
    assert args.services_command == "list"

    args = parser.parse_args(["services", "logs", "arnold-guardian", "--lines", "10"])
    assert args.services_command == "logs"
    assert args.service == "arnold-guardian"
    assert args.lines == 10

    args = parser.parse_args(["services", "restart", "arnold-guardian"])
    assert args.services_command == "restart"
    assert args.service == "arnold-guardian"

    args = parser.parse_args(["services", "reset-notifications", "--limit", "3"])
    assert args.services_command == "reset-notifications"
    assert args.limit == 3

    args = parser.parse_args(["notify", "test", "--dm-user-id", "123"])
    assert args.command == "notify"
    assert args.notify_command == "test"
    assert args.dm_user_id == "123"

    args = parser.parse_args(["version"])
    assert args.command == "version"
