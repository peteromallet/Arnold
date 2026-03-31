from __future__ import annotations

import pytest

from model_tools import get_tool_definitions
from run_agent import AIAgent
from toolsets import resolve_toolset


def _sample_schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "summary": {"type": "string"},
        },
        "required": ["summary"],
        "additionalProperties": False,
    }


def test_set_response_format_builds_chat_completions_envelope() -> None:
    agent = AIAgent(
        api_mode="chat_completions",
        enabled_toolsets=[],
        quiet_mode=True,
        skip_context_files=True,
        skip_memory=True,
    )

    response_format = agent.set_response_format(_sample_schema(), name="plan")
    kwargs = agent._build_api_kwargs([{"role": "user", "content": "hi"}])

    assert kwargs["response_format"] == response_format
    assert kwargs["response_format"]["json_schema"]["name"] == "plan"


def test_response_format_not_sent_to_anthropic_messages() -> None:
    agent = AIAgent(
        api_mode="anthropic_messages",
        provider="anthropic",
        enabled_toolsets=[],
        quiet_mode=True,
        skip_context_files=True,
        skip_memory=True,
    )

    agent.set_response_format(_sample_schema(), name="plan")
    kwargs = agent._build_api_kwargs([{"role": "user", "content": "hi"}])

    assert "response_format" not in kwargs


def test_response_format_translates_for_codex_responses() -> None:
    agent = AIAgent(
        api_mode="codex_responses",
        enabled_toolsets=[],
        quiet_mode=True,
        skip_context_files=True,
        skip_memory=True,
    )

    agent.set_response_format(_sample_schema(), name="plan")
    kwargs = agent._build_api_kwargs([{"role": "user", "content": "hi"}])

    assert kwargs["text"]["format"] == {
        "type": "json_schema",
        "name": "plan",
        "schema": _sample_schema(),
        "strict": True,
    }


def test_run_conversation_restores_response_format_on_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    agent = AIAgent(
        api_mode="chat_completions",
        enabled_toolsets=[],
        quiet_mode=True,
        skip_context_files=True,
        skip_memory=True,
    )
    original = agent.set_response_format(_sample_schema(), name="original")
    override = {
        "type": "json_schema",
        "json_schema": {
            "name": "override",
            "strict": True,
            "schema": _sample_schema(),
        },
    }

    def _boom(_system_message: str | None) -> str:
        raise RuntimeError("boom")

    monkeypatch.setattr(agent, "_build_system_prompt", _boom)

    with pytest.raises(RuntimeError, match="boom"):
        agent.run_conversation("hello", response_format=override)

    assert agent.response_format == original


def test_empty_enabled_toolsets_return_no_tools() -> None:
    assert get_tool_definitions(enabled_toolsets=[], quiet_mode=True) == []


def test_none_enabled_toolsets_still_returns_tools() -> None:
    assert len(get_tool_definitions(enabled_toolsets=None, quiet_mode=True)) > 0


def test_file_readonly_toolset_contains_only_read_and_search() -> None:
    assert set(resolve_toolset("file-readonly")) == {"read_file", "search_files"}
