"""Unit tests for megaplan.pricing.fireworks.cost_from_usage."""

from __future__ import annotations

import pytest

from arnold.pipelines.megaplan.pricing.fireworks import FIREWORKS_PRICING, cost_from_usage


def test_cost_from_usage_known_model() -> None:
    # deepseek-v4-pro: (1.74 input / 0.145 cached / 3.48 output) per million.
    # 1M prompt (uncached) + 1M completion = 1.74 + 3.48 = 5.22
    cost = cost_from_usage(1_000_000, 1_000_000, "deepseek-v4-pro")
    assert cost == pytest.approx(5.22)


def test_cost_from_usage_full_fireworks_path() -> None:
    # Full path should resolve to the trailing segment.
    cost_short = cost_from_usage(500_000, 250_000, "deepseek-v4-pro")
    cost_full = cost_from_usage(
        500_000, 250_000, "accounts/fireworks/models/deepseek-v4-pro"
    )
    assert cost_short == cost_full
    assert cost_full > 0.0


def test_cost_from_usage_unknown_model_returns_zero() -> None:
    assert cost_from_usage(1_000_000, 1_000_000, "totally-made-up-model") == 0.0


def test_cost_from_usage_no_model_returns_zero() -> None:
    assert cost_from_usage(1_000_000, 1_000_000, None) == 0.0
    assert cost_from_usage(1_000_000, 1_000_000, "") == 0.0


def test_cost_from_usage_zero_tokens_returns_zero() -> None:
    assert cost_from_usage(0, 0, "deepseek-v4-pro") == 0.0


def test_cost_from_usage_kimi_known() -> None:
    # kimi-k2p6: (0.95 input / 0.16 cached / 4.00 output) per million.
    assert "kimi-k2p6" in FIREWORKS_PRICING
    cost = cost_from_usage(2_000_000, 1_000_000, "kimi-k2p6")
    # 2M uncached input + 1M output = 2 * 0.95 + 1 * 4.00 = 5.90
    assert cost == pytest.approx(5.90)


def test_cost_from_usage_with_cached_prompt_tokens() -> None:
    # deepseek-v4-pro: 1M prompt of which 800k cached, 100k output.
    # uncached: 200k * 1.74e-6 = 0.348
    # cached:   800k * 0.145e-6 = 0.116
    # output:   100k * 3.48e-6 = 0.348
    # total: 0.812
    cost = cost_from_usage(
        1_000_000,
        100_000,
        "deepseek-v4-pro",
        cached_prompt_tokens=800_000,
    )
    assert cost == pytest.approx(0.812)


def test_cached_tokens_cannot_exceed_prompt_total() -> None:
    # Defensive: if caller claims cached > prompt, clamp to prompt.
    # Should bill all 100k as cached, none uncached.
    cost_clamped = cost_from_usage(
        100_000, 0, "deepseek-v4-pro", cached_prompt_tokens=999_000
    )
    cost_max_cached = cost_from_usage(
        100_000, 0, "deepseek-v4-pro", cached_prompt_tokens=100_000
    )
    assert cost_clamped == pytest.approx(cost_max_cached)


def test_cost_from_usage_handles_none_tokens() -> None:
    # Defensive: hermes may pass through None on degenerate paths.
    assert cost_from_usage(None, None, "deepseek-v4-pro") == 0.0  # type: ignore[arg-type]
