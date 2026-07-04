from __future__ import annotations

import logging

from arnold.agent.agent import auxiliary_client
from arnold.security.broker_service import BrokerService, PROTOCOL_VERSION
from arnold.security.llm_proxy import (
    LLM_PROXY_BASE_URL_ENV,
    LlmProxyCredential,
    broker_llm_proxy_base_url,
    broker_production_mode_requested,
    resolve_brokered_llm_proxy,
    warn_deferred_oauth_provider,
)


class _FakeBrokerClient:
    def __init__(self) -> None:
        self.requests: list[dict[str, str]] = []

    def issue_llm_proxy_credential(
        self,
        *,
        provider: str,
        proxy_base_url: str,
        upstream_base_url: str,
    ) -> LlmProxyCredential:
        self.requests.append(
            {
                "provider": provider,
                "proxy_base_url": proxy_base_url,
                "upstream_base_url": upstream_base_url,
            }
        )
        return LlmProxyCredential(
            provider=provider,
            base_url=proxy_base_url,
            broker_auth="arnold-broker-scoped-test",
            upstream_base_url=upstream_base_url,
            expires_at=123,
        )


def test_llm_proxy_resolution_uses_broker_scoped_auth(monkeypatch) -> None:
    monkeypatch.setenv("ARNOLD_BROKER_SOCKET", "/tmp/arnold-broker.sock")
    monkeypatch.setenv(LLM_PROXY_BASE_URL_ENV, "http://127.0.0.1:8765/llm")
    broker = _FakeBrokerClient()

    credential = resolve_brokered_llm_proxy(
        "deepseek",
        "https://api.deepseek.com",
        broker_client=broker,
    )

    assert credential is not None
    assert credential.base_url == "http://127.0.0.1:8765/llm/deepseek"
    assert credential.broker_auth == "arnold-broker-scoped-test"
    assert broker.requests == [
        {
            "provider": "deepseek",
            "proxy_base_url": "http://127.0.0.1:8765/llm/deepseek",
            "upstream_base_url": "https://api.deepseek.com",
        }
    ]


def test_broker_service_issues_proxy_credential_without_upstream_secret() -> None:
    raw_secret = "sk-raw-provider-secret-1234567890"
    service = BrokerService()

    response = service.handle_payload(
        {
            "version": PROTOCOL_VERSION,
            "operation": "issue_llm_proxy_credential",
            "provider": "custom",
            "proxy_base_url": "http://127.0.0.1:8765/llm/custom",
            "upstream_base_url": "https://llm.example.test/v1",
            "api_key": raw_secret,
        }
    )

    assert response["ok"] is True
    credential = response["proxy"]
    assert credential["base_url"] == "http://127.0.0.1:8765/llm/custom"
    assert credential["broker_auth"].startswith("arnold-broker-")
    assert raw_secret not in str(response)


def test_auxiliary_custom_provider_uses_broker_proxy(monkeypatch) -> None:
    raw_secret = "sk-raw-provider-secret-1234567890"
    broker = _FakeBrokerClient()
    monkeypatch.setenv("ARNOLD_BROKER_URL", "http://broker.local")
    monkeypatch.setenv(LLM_PROXY_BASE_URL_ENV, "http://127.0.0.1:8765/llm")
    monkeypatch.setattr(
        "arnold.security.broker_client.BrokerClient.from_environment",
        staticmethod(lambda environ=None: broker),
    )

    client, model = auxiliary_client.resolve_provider_client(
        "custom",
        model="qwen-local",
        explicit_base_url="https://llm.example.test/v1",
        explicit_api_key=raw_secret,
    )

    assert client is not None
    assert model == "qwen-local"
    assert client.api_key == "arnold-broker-scoped-test"
    assert raw_secret != client.api_key
    assert str(client.base_url).rstrip("/") == "http://127.0.0.1:8765/llm/custom"


def test_auxiliary_openrouter_preserves_headers_through_broker(monkeypatch) -> None:
    broker = _FakeBrokerClient()
    monkeypatch.setenv("ARNOLD_BROKER_URL", "http://broker.local")
    monkeypatch.setenv(LLM_PROXY_BASE_URL_ENV, "http://127.0.0.1:8765/llm")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-openrouter-secret-1234567890")
    monkeypatch.setattr(
        "arnold.security.broker_client.BrokerClient.from_environment",
        staticmethod(lambda environ=None: broker),
    )

    client, model = auxiliary_client.resolve_provider_client("openrouter")

    assert client is not None
    assert model == "google/gemini-3-flash-preview"
    assert client.api_key == "arnold-broker-scoped-test"
    assert getattr(client, "_arnold_default_headers")["X-OpenRouter-Title"] == "Hermes Agent"


def test_deferred_oauth_provider_warns_in_broker_mode(monkeypatch, caplog) -> None:
    monkeypatch.setenv("ARNOLD_BROKER_SOCKET", "/tmp/arnold-broker.sock")
    caplog.set_level(logging.WARNING, logger="arnold.security.llm_proxy")

    warn_deferred_oauth_provider("nous")

    assert broker_production_mode_requested() is True
    assert broker_llm_proxy_base_url() is None
    assert "deferred from M2 broker production coverage" in caplog.text
