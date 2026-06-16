"""Regression: silent OpenRouter fallback for Claude must be refused.

The harness historically defaulted ``resolve_model(None)`` and bare
``anthropic/claude-*`` model names to OpenRouter's
``anthropic/claude-opus-4.6`` endpoint. That route consumes
``OPENROUTER_API_KEY`` quota instead of the operator's Claude Code (shannon)
subscription, and the fallback was completely silent. These tests pin the
new behaviour: refuse the silent path, allow the explicit
``openrouter:`` opt-in.
"""

from __future__ import annotations

import pytest

from arnold.pipelines.megaplan.runtime.key_pool import resolve_model
from arnold.pipelines.megaplan.types import CliError


def test_resolve_model_none_raises_claude_via_openrouter_blocked() -> None:
    with pytest.raises(CliError) as excinfo:
        resolve_model(None)
    assert excinfo.value.code == "claude_via_openrouter_blocked"
    assert "shannon" in excinfo.value.message
    assert "OpenRouter" in excinfo.value.message


def test_resolve_model_empty_string_raises_claude_via_openrouter_blocked() -> None:
    with pytest.raises(CliError) as excinfo:
        resolve_model("   ")
    assert excinfo.value.code == "claude_via_openrouter_blocked"


def test_resolve_model_bare_anthropic_claude_raises() -> None:
    """A non-prefixed ``anthropic/claude-*`` model must NOT silently fall
    through to OpenRouter."""
    with pytest.raises(CliError) as excinfo:
        resolve_model("anthropic/claude-opus-4.6")
    assert excinfo.value.code == "claude_via_openrouter_blocked"


def test_resolve_model_bare_claude_dash_raises() -> None:
    with pytest.raises(CliError) as excinfo:
        resolve_model("claude-opus-4.6")
    assert excinfo.value.code == "claude_via_openrouter_blocked"


def test_resolve_model_explicit_openrouter_claude_allowed(monkeypatch) -> None:
    """The documented escape hatch: explicit ``openrouter:`` prefix opts in."""
    # acquire_key may return "" if no OPENROUTER_API_KEY is set; that's fine —
    # the path just shouldn't *raise*. We only verify the routing decision.
    resolved, kwargs = resolve_model("openrouter:anthropic/claude-opus-4.6")
    assert resolved == "anthropic/claude-opus-4.6"
    assert kwargs.get("base_url") == "https://openrouter.ai/api/v1"


def test_resolve_model_non_claude_bare_model_requires_explicit_provider() -> None:
    """Bare non-native models must not silently fall through to OpenRouter."""
    with pytest.raises(CliError) as excinfo:
        resolve_model("qwen/qwen3-235b")
    assert excinfo.value.code == "openrouter_blocked"
    assert "openrouter:" in excinfo.value.message


def test_resolve_model_zhipu_prefix_unaffected() -> None:
    resolved, kwargs = resolve_model("zhipu:glm-5.1")
    assert resolved == "glm-5.1"
    # base_url should be zhipu-shaped, never openrouter
    assert "openrouter" not in kwargs.get("base_url", "")


def test_resolve_model_fireworks_deepseek_routes_to_official_deepseek() -> None:
    resolved, kwargs = resolve_model(
        "fireworks:accounts/fireworks/models/deepseek-v4-pro"
    )

    assert resolved == "deepseek-v4-pro"
    assert "fireworks" not in kwargs.get("base_url", "")
    assert "deepseek" in kwargs.get("base_url", "")


def test_resolve_model_mimo_prefix_routes_to_mimo(monkeypatch) -> None:
    monkeypatch.setenv("MIMO_API_KEY", "mimo-key")
    from arnold.pipelines.megaplan.runtime import key_pool

    monkeypatch.setattr(key_pool._pool, "_next_reload", 0.0)

    resolved, kwargs = resolve_model("mimo:mimo-v2.5-pro-ultraspeed")

    assert resolved == "mimo-v2.5-pro-ultraspeed"
    assert kwargs["base_url"] == "https://api.xiaomimimo.com/v1"
    assert kwargs["api_key"] == "mimo-key"


def test_resolve_model_kimi_prefix_routes_to_kimi_coding_for_kimi_keys() -> None:
    """A ``kimi:`` prefix routes sk-kimi keys to Kimi coding, not OpenRouter."""
    resolved, kwargs = resolve_model("kimi:kimi-k2.7-code")
    assert resolved == "kimi-k2.7-code"
    assert kwargs.get("base_url") == "https://api.kimi.com/coding/v1"
    assert "openrouter" not in kwargs.get("base_url", "")


def test_resolve_model_kimi_prefix_uses_kimi_api_key(monkeypatch) -> None:
    monkeypatch.setenv("KIMI_API_KEY", "kimi-secret")
    from arnold.pipelines.megaplan.runtime import key_pool

    monkeypatch.setattr(key_pool._pool, "_next_reload", 0.0)

    resolved, kwargs = resolve_model("kimi:kimi-k2.7-code")
    assert resolved == "kimi-k2.7-code"
    assert kwargs["api_key"] == "kimi-secret"


def test_resolve_model_kimi_prefix_accepts_moonshot_api_key_alias(monkeypatch) -> None:
    """MOONSHOT_API_KEY is a valid fallback alias when KIMI_API_KEY is absent."""
    from arnold.pipelines.megaplan.runtime import key_pool
    from arnold.agent.providers.pool import KeyEntry

    # Prevent reload from overwriting the injected test state.
    monkeypatch.setattr(key_pool._pool, "_next_reload", float("inf"))
    monkeypatch.setattr(
        key_pool._pool,
        "_entries",
        {"kimi": [KeyEntry(key="moonshot-secret")]},
    )

    resolved, kwargs = resolve_model("kimi:kimi-k2.7-code")
    assert resolved == "kimi-k2.7-code"
    assert kwargs["api_key"] == "moonshot-secret"
