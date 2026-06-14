from __future__ import annotations

import os
from pathlib import Path

from arnold.agent.providers.env_loader import load_hermes_dotenv
from arnold.agent.providers.pool import KeyPool, minimax_openrouter_model


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
