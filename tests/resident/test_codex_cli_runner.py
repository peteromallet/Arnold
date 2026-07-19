from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.resident.agent_loop import (
    AgentPromptTooLargeError,
    AgentRequest,
    AgentTimeoutError,
    CodexCliAgentRunner,
)
from arnold_pipelines.megaplan.resident.config import ResidentConfig
from arnold_pipelines.megaplan.resident.tool_registry import ToolRegistry
from arnold_pipelines.megaplan.resident.provenance import DELEGATION_CONTEXT_ENV


def test_resident_config_defaults_to_codex() -> None:
    config = ResidentConfig()
    env_config = ResidentConfig.from_env({})

    assert config.model_provider == "codex"
    assert config.model_name == "gpt-5.6-sol"
    assert config.codex_reasoning_effort == "low"
    assert env_config.model_provider == "codex"
    assert env_config.model_name == "gpt-5.6-sol"
    assert env_config.codex_reasoning_effort == "low"


def test_codex_cli_runner_uses_output_last_message_and_medium_effort(
    tmp_path: Path,
    monkeypatch,
) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    calls = tmp_path / "calls.txt"
    codex = bin_dir / "codex"
    codex.write_text(
        "#!/usr/bin/env bash\n"
        "printf '%s\\n' \"$@\" > \"$CODEX_CALLS\"\n"
        "while [[ $# -gt 0 ]]; do\n"
        "  if [[ \"$1\" == \"--output-last-message\" ]]; then\n"
        "    shift\n"
        "    printf 'codex resident reply\\n' > \"$1\"\n"
        "  fi\n"
        "  shift || true\n"
        "done\n"
        "cat >/dev/null\n",
        encoding="utf-8",
    )
    codex.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")
    monkeypatch.setenv("CODEX_CALLS", str(calls))
    config = ResidentConfig(model_provider="codex", model_name="gpt-5.5", codex_reasoning_effort="medium")
    runner = CodexCliAgentRunner(config, cwd=tmp_path)

    response = asyncio.run(
        runner.run(
            AgentRequest(
                conversation_id="conversation-1",
                messages=({"role": "user", "content": "hello"},),
                system_prompt="system prompt",
            ),
            ToolRegistry(),
        )
    )

    assert response.final_text == "codex resident reply"
    assert response.metadata["runner"] == "codex_cli"
    call_text = calls.read_text(encoding="utf-8")
    assert "--model\ngpt-5.5" in call_text
    assert 'model_reasoning_effort="medium"' in call_text
    assert "--sandbox\nworkspace-write" in call_text


def test_codex_cli_runner_uses_configured_sandbox(tmp_path: Path) -> None:
    config = ResidentConfig(
        model_provider="codex",
        model_name="gpt-5.5",
        codex_sandbox="danger-full-access",
    )
    runner = CodexCliAgentRunner(config, cwd=tmp_path)

    assert runner.sandbox == "danger-full-access"


def test_codex_cli_runner_forces_read_only_for_report_only_request(
    tmp_path: Path, monkeypatch
) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    calls = tmp_path / "calls.txt"
    codex = bin_dir / "codex"
    codex.write_text(
        "#!/usr/bin/env bash\n"
        "printf '%s\\n' \"$@\" > \"$CODEX_CALLS\"\n"
        "while [[ $# -gt 0 ]]; do\n"
        "  if [[ \"$1\" == \"--output-last-message\" ]]; then shift; printf 'audit\\n' > \"$1\"; fi\n"
        "  shift || true\n"
        "done\n"
        "cat >/dev/null\n",
        encoding="utf-8",
    )
    codex.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")
    monkeypatch.setenv("CODEX_CALLS", str(calls))
    runner = CodexCliAgentRunner(
        ResidentConfig(model_provider="codex", codex_sandbox="danger-full-access"),
        cwd=tmp_path,
    )

    response = asyncio.run(
        runner.run(
            AgentRequest(
                conversation_id="audit-conversation",
                messages=({"role": "user", "content": "audit"},),
                system_prompt="system",
                report_only=True,
            ),
            ToolRegistry(),
        )
    )

    assert "--sandbox\nread-only" in calls.read_text(encoding="utf-8")
    assert response.metadata["sandbox"] == "read-only"
    assert response.metadata["report_only"] is True


def test_codex_cli_runner_recovers_same_invocation_after_initial_timeout(
    tmp_path: Path, monkeypatch
) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    calls = tmp_path / "calls.txt"
    codex = bin_dir / "codex"
    codex.write_text(
        "#!/usr/bin/env bash\n"
        "printf x >> \"$CODEX_CALLS\"\n"
        "output=\n"
        "while [[ $# -gt 0 ]]; do\n"
        "  if [[ \"$1\" == \"--output-last-message\" ]]; then shift; output=$1; fi\n"
        "  shift || true\n"
        "done\n"
        "cat >/dev/null\n"
        "sleep 0.12\n"
        "printf 'recovered resident reply\\n' > \"$output\"\n",
        encoding="utf-8",
    )
    codex.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")
    monkeypatch.setenv("CODEX_CALLS", str(calls))
    runner = CodexCliAgentRunner(
        ResidentConfig(
            model_provider="codex",
            model_timeout_s=0.05,
            model_timeout_recovery_grace_s=0.5,
        ),
        cwd=tmp_path,
    )

    response = asyncio.run(
        runner.run(
            AgentRequest(
                conversation_id="conversation-timeout-recovery",
                messages=({"role": "user", "content": "read only"},),
                system_prompt="system prompt",
            ),
            ToolRegistry(),
        )
    )

    assert response.final_text == "recovered resident reply"
    assert calls.read_text() == "x"  # same process continued; no replay
    assert response.metadata["timeout_recovery"]["mode"] == "same_process_grace"
    assert response.metadata["timeout_recovery"]["continuations"] == 1
    assert response.metadata["timeout_recovery"]["invocation_replays"] == 0


def test_codex_cli_runner_exhausts_recovery_and_kills_process_group(
    tmp_path: Path, monkeypatch
) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    calls = tmp_path / "calls.txt"
    orphan_marker = tmp_path / "orphaned.txt"
    codex = bin_dir / "codex"
    codex.write_text(
        "#!/usr/bin/env bash\n"
        "printf x >> \"$CODEX_CALLS\"\n"
        "cat >/dev/null\n"
        "(sleep 0.25; printf orphaned > \"$ORPHAN_MARKER\") &\n"
        "wait\n",
        encoding="utf-8",
    )
    codex.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")
    monkeypatch.setenv("CODEX_CALLS", str(calls))
    monkeypatch.setenv("ORPHAN_MARKER", str(orphan_marker))
    runner = CodexCliAgentRunner(
        ResidentConfig(
            model_provider="codex",
            model_timeout_s=0.03,
            model_timeout_recovery_grace_s=0.04,
        ),
        cwd=tmp_path,
    )

    with pytest.raises(AgentTimeoutError) as raised:
        asyncio.run(
            runner.run(
                AgentRequest(
                    conversation_id="conversation-timeout-exhausted",
                    messages=({"role": "user", "content": "read only"},),
                    system_prompt="system prompt",
                ),
                ToolRegistry(),
            )
        )

    assert "continuations=1" in str(raised.value)
    assert "process group terminated; no invocation replayed" in str(raised.value)
    assert calls.read_text() == "x"
    time.sleep(0.3)
    assert not orphan_marker.exists()


def test_codex_cli_prompt_requires_safe_path_for_resident_commands(tmp_path: Path) -> None:
    runner = CodexCliAgentRunner(ResidentConfig(model_provider="codex"), cwd=tmp_path)
    prompt = runner._prompt(
        AgentRequest(
            conversation_id="conversation-safe-path",
            messages=({"role": "user", "content": "launch it"},),
            system_prompt="system prompt",
        ),
        ToolRegistry(),
    )

    assert "python -P -m arnold_pipelines.megaplan.resident.subagent launch" in prompt
    assert "python -P -m arnold_pipelines.megaplan resident read-reply-chain" in prompt
    assert "`-P` isolation flag is mandatory" in prompt


def test_codex_cli_prompt_uses_compact_tool_catalog(tmp_path: Path) -> None:
    from arnold_pipelines.megaplan.resident.tool_registry import ToolRegistration
    from arnold_pipelines.megaplan.resident.tool_schemas import ToolInput, ToolResult

    class LargeInput(ToolInput):
        value: str

    tools = ToolRegistry()
    tools.register(
        ToolRegistration(
            "large_tool",
            "A useful tool.",
            "read",
            LargeInput,
            ToolResult,
            lambda _payload: ToolResult(ok=True, message="ok"),
        )
    )
    runner = CodexCliAgentRunner(ResidentConfig(model_provider="codex"), cwd=tmp_path)

    prompt = runner._prompt(
        AgentRequest(
            conversation_id="conversation-tools",
            messages=({"role": "user", "content": "hello"},),
            system_prompt="system prompt",
        ),
        tools,
    )

    assert '"arguments": ["value"]' in prompt
    assert '"input_schema"' not in prompt


def test_codex_cli_prompt_fails_locally_before_transport_limit(tmp_path: Path) -> None:
    runner = CodexCliAgentRunner(
        ResidentConfig(model_provider="codex", max_prompt_chars=2_000), cwd=tmp_path
    )

    with pytest.raises(AgentPromptTooLargeError, match="safe pre-dispatch budget"):
        runner._prompt(
            AgentRequest(
                conversation_id="conversation-budget",
                messages=({"role": "user", "content": "x" * 4_000},),
                system_prompt="system prompt",
            ),
            ToolRegistry(),
        )


def test_codex_cli_compatibility_process_receives_validated_launch_provenance(
    tmp_path: Path, monkeypatch
) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    captured = tmp_path / "delegation.json"
    codex = bin_dir / "codex"
    codex.write_text(
        "#!/usr/bin/env bash\n"
        f"printf '%s' \"${{{DELEGATION_CONTEXT_ENV}}}\" > \"{captured}\"\n"
        "while [[ $# -gt 0 ]]; do\n"
        "  if [[ \"$1\" == \"--output-last-message\" ]]; then shift; printf ok > \"$1\"; fi\n"
        "  shift || true\n"
        "done\n"
        "cat >/dev/null\n",
        encoding="utf-8",
    )
    codex.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")
    runner = CodexCliAgentRunner(ResidentConfig(model_provider="codex"), cwd=tmp_path)
    origin = {
        "transport": "discord",
        "applicability": "applicable",
        "resident_conversation_id": "rconv_cli_context1",
        "source_record_id": "msg_cli_context123",
        "conversation_key": "discord:dm:42",
        "discord_message_id": "1525300000000000066",
        "reply_to_message_id": "1525300000000000066",
        "guild_id": None,
        "channel_id": "dm-channel",
        "thread_id": None,
        "dm_user_id": "42",
        "message_content": "must not cross process boundary",
    }

    asyncio.run(
        runner.run(
            AgentRequest(
                conversation_id="rconv_cli_context1",
                messages=({"role": "user", "content": "launch it"},),
                system_prompt="system prompt",
                launch_origin=origin,
            ),
            ToolRegistry(),
        )
    )
    propagated = json.loads(captured.read_text())
    assert propagated["source_record_id"] == "msg_cli_context123"
    assert propagated["reply_to_message_id"] == "1525300000000000066"
    assert "message_content" not in propagated
