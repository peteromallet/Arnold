from __future__ import annotations

from arnold.agent.run_agent import AIAgent


def _agent(*, tools: list[dict] | None, base_url: str = "https://api.fireworks.ai") -> AIAgent:
    agent = object.__new__(AIAgent)
    agent.api_mode = "chat_completions"
    agent._base_url_lower = base_url.lower()
    agent.tools = tools or []
    return agent


def test_response_format_is_omitted_when_function_tools_are_enabled() -> None:
    agent = _agent(
        tools=[
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ]
    )

    assert agent._supports_response_format() is False


def test_response_format_remains_available_without_function_tools() -> None:
    assert _agent(tools=[])._supports_response_format() is True
