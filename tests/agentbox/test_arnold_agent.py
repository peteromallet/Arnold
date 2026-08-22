"""Tests for the ``arnold`` console entry (omp named-agent runner)."""

from __future__ import annotations

from pathlib import Path


from agentbox import arnold_agent


def test_missing_launcher_is_a_clean_error(monkeypatch, capsys) -> None:
    monkeypatch.delenv("ARNOLD_AGENT_LAUNCHER", raising=False)
    monkeypatch.setattr(arnold_agent, "_LAUNCHER_CANDIDATES", (Path("/nonexistent/agent"),))
    monkeypatch.setattr(arnold_agent.shutil, "which", lambda _: None)

    assert arnold_agent.main(["hello"]) == 1

    err = capsys.readouterr().err
    assert "could not locate the omp agent launcher" in err


def test_launcher_resolution_prefers_bun_and_skips_grok(monkeypatch, tmp_path) -> None:
    bun = tmp_path / "bun" / "agent"
    bun.parent.mkdir(parents=True, exist_ok=True)
    bun.write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setattr(arnold_agent, "_LAUNCHER_CANDIDATES", (bun,))
    monkeypatch.setattr(
        arnold_agent.shutil, "which", lambda _: str(tmp_path / ".grok" / "bin" / "agent")
    )

    resolved = arnold_agent._find_launcher()

    assert resolved == bun


def test_env_override_selects_launcher(monkeypatch, tmp_path) -> None:
    override = tmp_path / "custom-agent"
    override.write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setenv("ARNOLD_AGENT_LAUNCHER", str(override))

    assert arnold_agent._find_launcher() == override


def test_main_execs_run_with_default_agent(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_execvp(file: str, argv: list[str]) -> None:
        captured["file"] = file
        captured["argv"] = argv

    monkeypatch.setattr(arnold_agent.os, "execvp", fake_execvp)
    monkeypatch.setattr(
        arnold_agent,
        "_find_launcher",
        lambda: Path("/Users/fake/.bun/bin/agent"),
    )

    arnold_agent.main(["What is running?"])

    assert captured["file"] == "/Users/fake/.bun/bin/agent"
    assert captured["argv"] == [
        "/Users/fake/.bun/bin/agent",
        "run",
        "arnold",
        "What is running?",
    ]


def test_main_supports_agent_switch_and_flag_forwarding(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_execvp(_file: str, argv: list[str]) -> None:
        captured["argv"] = argv

    monkeypatch.setattr(arnold_agent.os, "execvp", fake_execvp)
    monkeypatch.setattr(arnold_agent, "_find_launcher", lambda: Path("/l/agent"))

    arnold_agent.main(["--agent", "scout", "--resume", "message"])

    assert captured["argv"] == ["/l/agent", "run", "scout", "--resume", "message"]


def test_main_rejects_dangling_agent_flag(monkeypatch, capsys) -> None:
    monkeypatch.setattr(arnold_agent.os, "execvp", lambda *_: None)
    monkeypatch.setattr(arnold_agent, "_find_launcher", lambda: Path("/l/agent"))

    assert arnold_agent.main(["--agent"]) == 1

    assert "--agent requires a value" in capsys.readouterr().err
