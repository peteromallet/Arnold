"""Unit tests for megaplan.claude_pricing."""

from __future__ import annotations

import pytest

from megaplan.claude_pricing import (
    CLAUDE_PRICING,
    DEFAULT_PROMPT_COMPLETION_RATIO,
    cost_from_usage,
    estimate_tokens_from_cost,
)


def test_opus_4_cost_simple() -> None:
    # 1M prompt + 1M completion at Opus rates = $15 + $75 = $90
    assert cost_from_usage(1_000_000, 1_000_000, "claude-opus-4-7") == pytest.approx(90.0)


def test_sonnet_4_cost() -> None:
    # 1M prompt + 1M completion at Sonnet 4 rates = $3 + $15 = $18
    assert cost_from_usage(1_000_000, 1_000_000, "claude-sonnet-4-6") == pytest.approx(18.0)


def test_opus_4_with_dated_suffix() -> None:
    # Prefix match should handle Anthropic's dated model ids.
    assert cost_from_usage(
        1_000_000, 0, "claude-opus-4-20250514"
    ) == pytest.approx(15.0)


def test_full_path_prefix() -> None:
    short = cost_from_usage(500_000, 100_000, "claude-opus-4-7")
    full = cost_from_usage(500_000, 100_000, "anthropic/claude-opus-4-7")
    assert short == full
    assert short > 0


def test_unknown_model_returns_zero() -> None:
    assert cost_from_usage(1_000_000, 1_000_000, "made-up-model") == 0.0


def test_none_model_returns_zero() -> None:
    assert cost_from_usage(1_000_000, 1_000_000, None) == 0.0


def test_cached_tokens_billed_cheaper() -> None:
    # 1M prompt of which 800k cached_read, 0 completion at Opus.
    # uncached: 200k * 15 = $3
    # cached_read: 800k * 1.5 = $1.2
    # total: $4.20
    assert cost_from_usage(
        1_000_000, 0, "claude-opus-4-7", cached_read_tokens=800_000
    ) == pytest.approx(4.20)


def test_estimate_round_trip_default_ratio() -> None:
    # If we encode tokens at the default 10:1 ratio, compute cost,
    # then estimate back — we should get the same tokens out.
    p_in = 10_000
    c_in = 1_000
    cost = cost_from_usage(p_in, c_in, "claude-opus-4-7")
    result = estimate_tokens_from_cost(cost, "claude-opus-4-7", ratio=10.0)
    assert result is not None
    p_out, c_out = result
    assert p_out == pytest.approx(p_in, abs=1)
    assert c_out == pytest.approx(c_in, abs=1)


def test_estimate_returns_none_for_zero_cost() -> None:
    assert estimate_tokens_from_cost(0.0, "claude-opus-4-7") is None
    assert estimate_tokens_from_cost(-1.0, "claude-opus-4-7") is None


def test_estimate_returns_none_for_unknown_model() -> None:
    # Even with a valid cost, can't estimate if model can't be priced.
    assert estimate_tokens_from_cost(1.0, "unknown-model") is None


def test_estimate_falls_back_to_default_family_when_model_none() -> None:
    # No model given -> defaults to opus (the megaplan default).
    result = estimate_tokens_from_cost(0.225, None, ratio=10.0)
    assert result is not None
    # $0.225 of Opus at 10:1 = ~1000 completion / 10000 prompt
    p, c = result
    assert c == pytest.approx(1000, abs=5)
    assert p == pytest.approx(10000, abs=50)


def test_known_families_have_4_field_rates() -> None:
    for family, rates in CLAUDE_PRICING.items():
        assert len(rates) == 4, f"{family!r} should be (input, cached_read, cached_write, output)"
        in_, cr, cw, out = rates
        assert 0 < cr < in_ < cw < out or 0 < cr < in_ <= cw <= out, (
            f"{family!r} unexpected rate ordering: {rates}"
        )


def test_default_ratio_is_documented() -> None:
    assert DEFAULT_PROMPT_COMPLETION_RATIO == 10.0
