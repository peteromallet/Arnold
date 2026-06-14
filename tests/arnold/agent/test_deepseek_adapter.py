from __future__ import annotations

import urllib.error
from decimal import Decimal
from typing import Any, Mapping

import pytest

from arnold.agent import AgentRequest, BackendAdapter
from arnold.agent.adapters.deepseek import DeepSeekAdapter
from arnold.pipeline.token_cost import PricingEntry


class _FakeKeyPool:
    def __init__(self, key: str = "key-1") -> None:
        self.key = key
        self.acquired: list[str] = []
        self.cooldowns: list[tuple[str, str]] = []
        self.failures: list[tuple[str, str]] = []

    def acquire(self, provider: str) -> str:
        self.acquired.append(provider)
        return self.key

    def report_429(self, provider: str, key: str, cooldown_secs: float = 60) -> None:
        del cooldown_secs
        self.cooldowns.append((provider, key))

    def report_failure(self, provider: str, key: str) -> None:
        self.failures.append((provider, key))


def _response(**overrides: Any) -> dict[str, Any]:
    result: dict[str, Any] = {
        "model": "deepseek-chat",
        "choices": [{"message": {"content": "hello"}}],
        "usage": {
            "prompt_tokens": 1000,
            "completion_tokens": 500,
            "total_tokens": 1500,
        },
    }
    result.update(overrides)
    return result


def test_deepseek_adapter_is_backend_adapter_protocol() -> None:
    adapter = DeepSeekAdapter(key_pool=_FakeKeyPool(), transport=lambda *args: _response())

    assert isinstance(adapter, BackendAdapter)


def test_deepseek_adapter_posts_openai_compatible_payload_and_projects_result() -> None:
    calls: list[tuple[str, Mapping[str, Any], Mapping[str, str], float | None]] = []

    def transport(
        url: str,
        payload: Mapping[str, Any],
        headers: Mapping[str, str],
        timeout: float | None,
    ) -> Mapping[str, Any]:
        calls.append((url, payload, headers, timeout))
        return _response()

    adapter = DeepSeekAdapter(
        key_pool=_FakeKeyPool(),
        base_url="https://deepseek.test/",
        transport=transport,
        pricing_rows={
            ("deepseek", "deepseek-chat"): PricingEntry(
                input_cost_per_million=Decimal("2.00"),
                output_cost_per_million=Decimal("8.00"),
                source="user_override",
                pricing_version="test-prices",
            )
        },
    )

    result = adapter(
        AgentRequest(
            agent="deepseek",
            mode="unit",
            model="deepseek-chat",
            effort="high",
            prompt="Say hi",
            system_prompt="Be terse",
            timeout_seconds=12.5,
            metadata={"temperature": 0.2},
        )
    )

    url, payload, headers, timeout = calls[0]
    assert url == "https://deepseek.test/v1/chat/completions"
    assert headers["Authorization"] == "Bearer key-1"
    assert timeout == 12.5
    assert payload["model"] == "deepseek-chat"
    assert payload["reasoning_effort"] == "high"
    assert payload["temperature"] == 0.2
    assert payload["messages"] == [
        {"role": "system", "content": "Be terse"},
        {"role": "user", "content": "Say hi"},
    ]

    assert result.raw_output == "hello"
    assert result.payload == {"response": "hello", "completed": True}
    assert result.prompt_tokens == 1000
    assert result.completion_tokens == 500
    assert result.total_tokens == 1500
    assert result.cost_usd == pytest.approx(0.006)
    assert result.metadata["cost_status"] == "estimated"
    assert result.metadata["pricing_version"] == "test-prices"
    assert result.provenance is not None
    assert result.provenance.metadata == {"provider": "deepseek"}


def test_deepseek_adapter_routes_mimo_provider_prefix() -> None:
    calls: list[tuple[str, Mapping[str, Any], Mapping[str, str], float | None]] = []

    def transport(
        url: str,
        payload: Mapping[str, Any],
        headers: Mapping[str, str],
        timeout: float | None,
    ) -> Mapping[str, Any]:
        calls.append((url, payload, headers, timeout))
        return _response(model="mimo-v2.5-pro-ultraspeed")

    key_pool = _FakeKeyPool(key="mimo-key")
    adapter = DeepSeekAdapter(key_pool=key_pool, transport=transport)

    result = adapter(
        AgentRequest(
            agent="hermes",
            mode="unit",
            model="mimo:mimo-v2.5-pro-ultraspeed",
            prompt="Say hi",
        )
    )

    url, payload, headers, _ = calls[0]
    assert key_pool.acquired == ["mimo"]
    assert url == "https://api.xiaomimimo.com/v1/chat/completions"
    assert payload["model"] == "mimo-v2.5-pro-ultraspeed"
    assert headers["Authorization"] == "Bearer mimo-key"
    assert headers["api-key"] == "mimo-key"
    assert result.provenance is not None
    assert result.provenance.metadata == {"provider": "mimo"}


def test_deepseek_adapter_reports_rate_limit_to_key_pool() -> None:
    key_pool = _FakeKeyPool()

    def transport(*args: Any) -> Mapping[str, Any]:
        raise urllib.error.HTTPError(
            url="https://deepseek.test/v1/chat/completions",
            code=429,
            msg="rate limited",
            hdrs={},
            fp=None,
        )

    adapter = DeepSeekAdapter(key_pool=key_pool, transport=transport)

    with pytest.raises(urllib.error.HTTPError):
        adapter(AgentRequest(agent="deepseek", mode="unit", prompt="hi"))

    assert key_pool.cooldowns == [("deepseek", "key-1")]
    assert key_pool.failures == []


def test_deepseek_adapter_reports_auth_failure_to_key_pool() -> None:
    key_pool = _FakeKeyPool()

    def transport(*args: Any) -> Mapping[str, Any]:
        raise urllib.error.HTTPError(
            url="https://deepseek.test/v1/chat/completions",
            code=401,
            msg="unauthorized",
            hdrs={},
            fp=None,
        )

    adapter = DeepSeekAdapter(key_pool=key_pool, transport=transport)

    with pytest.raises(urllib.error.HTTPError):
        adapter(AgentRequest(agent="deepseek", mode="unit", prompt="hi"))

    assert key_pool.cooldowns == []
    assert key_pool.failures == [("deepseek", "key-1")]


def test_deepseek_adapter_fails_closed_without_available_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("HERMES_API_KEY", raising=False)
    adapter = DeepSeekAdapter(key_pool=_FakeKeyPool(key=""), transport=lambda *args: _response())

    with pytest.raises(LookupError, match="no DeepSeek API key available"):
        adapter(AgentRequest(agent="deepseek", mode="unit", prompt="hi"))
