from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from agentbox.config import AgentBoxConfig
from agentbox.notify import notify_test


@pytest.fixture
def config(tmp_path: Path) -> AgentBoxConfig:
    return AgentBoxConfig(workspace_root=tmp_path / "workspace")


def test_notify_test_returns_fix_command_when_token_missing(config: AgentBoxConfig, monkeypatch) -> None:
    monkeypatch.delenv("DISCORD_BOT_TOKEN", raising=False)

    result = notify_test(config)

    assert result["ok"] is False
    assert "DISCORD_BOT_TOKEN" in result["error"]
    assert result["fix_command"] == "set DISCORD_BOT_TOKEN"


def test_notify_test_returns_ok_with_mock_sink(config: AgentBoxConfig, monkeypatch) -> None:
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "fake-token")

    mock_sink = AsyncMock()

    result = notify_test(config, conversation_key="discord:dm:12345", outbound=mock_sink)

    assert result["ok"] is True
    assert result["conversation_key"] == "discord:dm:12345"
    mock_sink.send.assert_awaited_once()
    message = mock_sink.send.await_args[0][0]
    assert "AgentBox notify test" in message.content


def test_notify_test_returns_no_target_without_key_or_store(config: AgentBoxConfig, monkeypatch) -> None:
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "fake-token")

    result = notify_test(config)

    assert result["ok"] is False
    assert result.get("reason") == "no target"
