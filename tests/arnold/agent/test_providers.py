from __future__ import annotations

import json
import os
from pathlib import Path

from arnold.agent.providers.env_loader import load_hermes_dotenv
from arnold.agent.providers.pool import KeyPool, minimax_openrouter_model
from arnold.security.llm_proxy import broker_production_mode_requested


class _StaticKeyPathSource:
    def __init__(self, path: Path) -> None:
        self._path = path

    def keys_path(self) -> Path:
        return self._path


def test_key_pool_acquires_lru_env_keys(monkeypatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "primary")
    monkeypatch.setenv("DEEPSEEK_API_KEY_2", "secondary")
    pool = KeyPool(ttl_seconds=0)

    first = pool.acquire("deepseek")
    second = pool.acquire("deepseek")

    assert {first, second} == {"primary", "secondary"}


def test_key_pool_cooldown_and_failure(monkeypatch) -> None:
    monkeypatch.setenv("FIREWORKS_API_KEY", "fw")
    pool = KeyPool(ttl_seconds=0)

    assert pool.acquire("fireworks") == "fw"
    pool.report_429("fireworks", "fw", cooldown_secs=60)
    assert pool.acquire("fireworks") == ""
    pool.report_failure("fireworks", "fw")
    assert pool.has_keys("fireworks") is True


def test_key_pool_acquires_mimo_env_key(monkeypatch) -> None:
    monkeypatch.setenv("MIMO_API_KEY", "mimo-key")
    pool = KeyPool(ttl_seconds=0)

    assert pool.acquire("mimo") == "mimo-key"


def test_key_pool_broker_mode_returns_scoped_token_and_proxy_url(monkeypatch) -> None:
    class _FakeBrokerClient:
        def __init__(self) -> None:
            self.requests: list[tuple[str, str, str]] = []

        def issue_llm_proxy_credential(
            self,
            *,
            provider: str,
            proxy_base_url: str,
            upstream_base_url: str,
        ):
            self.requests.append((provider, proxy_base_url, upstream_base_url))
            from arnold.security.llm_proxy import LlmProxyCredential

            return LlmProxyCredential(
                provider=provider,
                base_url=proxy_base_url.rstrip("/"),
                broker_auth="arnold-broker-scoped-token",
                upstream_base_url=upstream_base_url,
                expires_at=None,
            )

    broker = _FakeBrokerClient()
    monkeypatch.setenv("ARNOLD_BROKER_SOCKET", "/tmp/arnold-broker.sock")
    monkeypatch.setenv("ARNOLD_LLM_PROXY_BASE_URL", "http://broker.local/llm")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "raw-deepseek-key")
    monkeypatch.setattr(
        "arnold.security.broker_client.BrokerClient.from_environment",
        staticmethod(lambda **_: broker),
    )
    pool = KeyPool(ttl_seconds=0)

    assert broker_production_mode_requested() is True
    assert pool.acquire("deepseek") == "arnold-broker-scoped-token"
    assert pool.resolve_base_url("deepseek") == "http://broker.local/llm/deepseek"
    assert broker.requests == [
        ("deepseek", "http://broker.local/llm/deepseek", "https://api.deepseek.com")
    ]


def test_key_pool_broker_mode_does_not_return_raw_keys_from_hermes_or_json(
    tmp_path: Path,
    monkeypatch,
) -> None:
    hermes_home = tmp_path / "home"
    (hermes_home / ".hermes").mkdir(parents=True)
    (hermes_home / ".hermes" / ".env").write_text(
        "ZHIPU_API_KEY=hermes-zhipu-secret\n",
        encoding="utf-8",
    )
    key_file = tmp_path / "api_keys.json"
    key_file.write_text(
        json.dumps([{"key": "json-zhipu-secret"}]),
        encoding="utf-8",
    )
    monkeypatch.setattr("arnold.agent.providers.pool.Path.home", staticmethod(lambda: hermes_home))
    monkeypatch.setenv("ARNOLD_BROKER_SOCKET", "/tmp/arnold-broker.sock")
    monkeypatch.setenv("ARNOLD_LLM_PROXY_BASE_URL", "http://broker.local/llm")
    monkeypatch.delenv("ZHIPU_API_KEY", raising=False)
    monkeypatch.setattr(
        "arnold.security.broker_client.BrokerClient.from_environment",
        staticmethod(lambda **_: (_ for _ in ()).throw(AssertionError("broker unreachable"))),
    )
    pool = KeyPool(ttl_seconds=0, keys_path_source=_StaticKeyPathSource(key_file))

    assert pool.acquire("zhipu") == ""
    assert pool.get_api_credential("ZHIPU_API_KEY") == ""
    assert pool.load_hermes_env() == {}


def test_load_hermes_dotenv_uses_user_env_precedence(tmp_path: Path, monkeypatch) -> None:
    hermes_home = tmp_path / "hermes"
    hermes_home.mkdir()
    user_env = hermes_home / ".env"
    user_env.write_text("DEEPSEEK_API_KEY=user\n", encoding="utf-8")
    project_env = tmp_path / "project.env"
    project_env.write_text("DEEPSEEK_API_KEY=project\nFIREWORKS_API_KEY=fw\n", encoding="utf-8")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("FIREWORKS_API_KEY", raising=False)

    loaded = load_hermes_dotenv(hermes_home=hermes_home, project_env=project_env)

    assert loaded == [user_env, project_env]
    assert os.environ["DEEPSEEK_API_KEY"] == "user"
    assert os.environ["FIREWORKS_API_KEY"] == "fw"


def test_minimax_openrouter_model_mapping() -> None:
    assert minimax_openrouter_model("MiniMax-M2") == "minimax/minimax-m2"
    assert minimax_openrouter_model("custom") == "minimax/custom"
