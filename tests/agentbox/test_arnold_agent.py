"""Tests for the ``arnold`` console entry (omp named-agent runner)."""

from __future__ import annotations

import os

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
        "--print",
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

    err = capsys.readouterr().err
    assert '--agent requires a value (e.g. arnold --agent scout "hi")' in err


def test_leading_flags_pass_through_and_message_implies_print(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_execvp(_file: str, argv: list[str]) -> None:
        captured["argv"] = argv

    monkeypatch.setattr(arnold_agent.os, "execvp", fake_execvp)
    monkeypatch.setattr(arnold_agent, "_find_launcher", lambda: Path("/l/agent"))

    arnold_agent.main(["-c", "follow-up question"])

    assert captured["argv"] == ["/l/agent", "run", "arnold", "-c", "--print", "follow-up question"]


def test_value_flag_consumes_its_argument(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_execvp(_file: str, argv: list[str]) -> None:
        captured["argv"] = argv

    monkeypatch.setattr(arnold_agent.os, "execvp", fake_execvp)
    monkeypatch.setattr(arnold_agent, "_find_launcher", lambda: Path("/l/agent"))

    arnold_agent.main(["--resume", "abc123"])

    assert captured["argv"] == ["/l/agent", "run", "arnold", "--resume", "abc123"]


def test_help_flag_prints_usage_without_exec(monkeypatch, capsys) -> None:
    def fail_execvp(*_args: object) -> None:
        raise AssertionError("execvp must not run for --help")

    monkeypatch.setattr(arnold_agent.os, "execvp", fail_execvp)

    assert arnold_agent.main(["-h"]) == 0
    assert arnold_agent.main(["--agent", "scout", "--help"]) == 0

    out = capsys.readouterr().out
    assert "usage: arnold [flags] [message...]" in out
    assert "--agent NAME" in out


def test_flags_after_message_are_rejected(monkeypatch, capsys) -> None:
    def fail_execvp(*_args: object) -> None:
        raise AssertionError("execvp must not run for misplaced flags")

    monkeypatch.setattr(arnold_agent.os, "execvp", fail_execvp)
    monkeypatch.setattr(arnold_agent, "_find_launcher", lambda: Path("/l/agent"))

    assert arnold_agent.main(["follow-up", "-c"]) == 1

    assert "flags must precede the message" in capsys.readouterr().err


class _FakeStderr:
    """Minimal write-only stream with a controllable isatty."""

    def __init__(self, isatty: bool) -> None:
        self._isatty = isatty
        self.parts: list[str] = []

    def isatty(self) -> bool:
        return self._isatty

    def write(self, text: str) -> int:
        self.parts.append(text)
        return len(text)

    def flush(self) -> None:
        pass


def test_identity_label_default_and_custom_agents() -> None:
    assert arnold_agent._identity_label("arnold") == "AgentBox Operator"
    assert arnold_agent._identity_label("scout") == "agent · scout"


def test_one_shot_header_brands_stderr_and_tab_title_on_a_tty() -> None:
    stream = _FakeStderr(isatty=True)
    arnold_agent._print_one_shot_header("arnold", stream=stream)
    rendered = "".join(stream.parts)
    assert "\x1b]0;arnold · AgentBox Operator\x07" in rendered
    assert "\x1b[1marnold · AgentBox Operator\x1b[0m" in rendered


def test_one_shot_header_uses_custom_agent_label() -> None:
    stream = _FakeStderr(isatty=True)
    arnold_agent._print_one_shot_header("scout", stream=stream)
    assert "agent · scout" in "".join(stream.parts)


def test_one_shot_header_skipped_when_not_a_tty() -> None:
    stream = _FakeStderr(isatty=False)
    arnold_agent._print_one_shot_header("arnold", stream=stream)
    assert stream.parts == []

def test_select_omp_bin_prefers_branded_build(monkeypatch, tmp_path) -> None:
    branded = tmp_path / "omp"
    branded.write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setattr(arnold_agent, "_BRANDED_OMP", branded)
    monkeypatch.delenv("OMP_BIN", raising=False)
    monkeypatch.delenv("ARNOLD_STOCK_OMP", raising=False)

    arnold_agent._select_omp_bin()

    assert os.environ["OMP_BIN"] == str(branded)


def test_select_omp_bin_keeps_existing_override(monkeypatch, tmp_path) -> None:
    branded = tmp_path / "omp"
    branded.write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setattr(arnold_agent, "_BRANDED_OMP", branded)
    monkeypatch.setenv("OMP_BIN", "/custom/omp")
    monkeypatch.delenv("ARNOLD_STOCK_OMP", raising=False)

    arnold_agent._select_omp_bin()

    assert os.environ["OMP_BIN"] == "/custom/omp"


def test_select_omp_bin_stock_opt_out(monkeypatch, tmp_path) -> None:
    branded = tmp_path / "omp"
    branded.write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setattr(arnold_agent, "_BRANDED_OMP", branded)
    monkeypatch.delenv("OMP_BIN", raising=False)
    monkeypatch.setenv("ARNOLD_STOCK_OMP", "1")

    arnold_agent._select_omp_bin()

    assert "OMP_BIN" not in os.environ
