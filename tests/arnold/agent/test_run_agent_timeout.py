from __future__ import annotations

from arnold.agent.run_agent import (
    AIAgent,
    DEFAULT_API_TIMEOUT_SECONDS,
    DEFAULT_DEEPSEEK_API_TIMEOUT_SECONDS,
)


def _bare_agent(base_url: str) -> AIAgent:
    agent = object.__new__(AIAgent)
    agent._base_url_lower = base_url.lower()
    agent._streaming_timeout_streak = 0
    agent._streaming_timeout_wall_start_monotonic = None
    return agent


def test_nonfinite_general_request_timeout_falls_back_to_finite_default(
    monkeypatch,
) -> None:
    monkeypatch.setenv("HERMES_API_TIMEOUT", "inf")

    timeout = _bare_agent("https://open.bigmodel.cn/api/coding/paas/v4")._api_timeout_seconds()

    assert timeout == DEFAULT_API_TIMEOUT_SECONDS


def test_nonfinite_deepseek_request_timeout_falls_back_to_finite_default(
    monkeypatch,
) -> None:
    monkeypatch.setenv("HERMES_API_TIMEOUT", "inf")
    monkeypatch.setenv("HERMES_DEEPSEEK_API_TIMEOUT", "infinity")

    timeout = _bare_agent("https://api.deepseek.com/v1")._api_timeout_seconds()

    assert timeout == DEFAULT_DEEPSEEK_API_TIMEOUT_SECONDS
