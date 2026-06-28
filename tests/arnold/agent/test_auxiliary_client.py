from __future__ import annotations

from openai import OpenAI

from arnold.agent.agent import auxiliary_client


def test_resolve_provider_client_falls_back_to_auto_for_missing_explicit_api_key_provider(
    monkeypatch,
    caplog,
) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("KIMI_API_KEY", "kimi-key")

    fallback_client = OpenAI(api_key="kimi-key", base_url="https://api.kimi.com/v1")
    calls: list[str] = []

    def fake_resolve_auto():
        calls.append("auto")
        return fallback_client, "kimi-k2-turbo-preview"

    monkeypatch.setattr(auxiliary_client, "_resolve_auto", fake_resolve_auto)

    client, model = auxiliary_client.resolve_provider_client(
        "deepseek",
        model="deepseek-v4-pro",
    )

    assert calls == ["auto"]
    assert client is fallback_client
    assert model == "kimi-k2-turbo-preview"
    assert "provider deepseek has no API key configured" in caplog.text
    assert "falling back to auto" in caplog.text
