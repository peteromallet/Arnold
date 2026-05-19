"""Cost-fallback wiring for the Hermes worker.

When hermes_cli reports ``estimated_cost_usd=0`` (the current state for
Fireworks-hosted models), the worker falls back to the local
``megaplan.pricing.fireworks`` table. The fallback must pass
``cache_read_tokens`` through as ``cached_prompt_tokens`` so cached prefix
tokens are billed at the cheaper cached rate, not the full uncached input
rate. These tests pin that wiring.
"""

from __future__ import annotations

from megaplan.pricing import fireworks as fireworks_pricing
from megaplan.workers.hermes import _resolve_hermes_cost


_FIREWORKS_DEEPSEEK = "accounts/fireworks/models/deepseek-v4-pro"


def test_resolve_hermes_cost_trusts_nonzero_hermes_estimate() -> None:
    """If hermes_cli reports a positive cost, we use it verbatim."""
    cost, p, c, t = _resolve_hermes_cost(
        {
            "estimated_cost_usd": 0.42,
            "prompt_tokens": 1000,
            "completion_tokens": 200,
            "total_tokens": 1200,
            "cache_read_tokens": 800,
            "model": _FIREWORKS_DEEPSEEK,
        }
    )
    assert cost == 0.42
    assert (p, c, t) == (1000, 200, 1200)


def test_resolve_hermes_cost_falls_back_when_hermes_reports_zero() -> None:
    """Zero from hermes_cli triggers the local pricing fallback."""
    cost, _, _, _ = _resolve_hermes_cost(
        {
            "estimated_cost_usd": 0.0,
            "prompt_tokens": 10_000,
            "completion_tokens": 1_000,
            "total_tokens": 11_000,
            "cache_read_tokens": 0,
            "model": _FIREWORKS_DEEPSEEK,
        }
    )
    expected = fireworks_pricing.cost_from_usage(
        10_000, 1_000, _FIREWORKS_DEEPSEEK
    )
    assert cost == expected
    assert cost > 0.0


def test_resolve_hermes_cost_passes_cache_read_to_pricing() -> None:
    """The regression: cached prefix must be billed at the cached rate.

    Without the wiring, all 9000 cached tokens would be billed at the full
    1.74/MTok input rate; with the wiring, they're billed at the 0.145/MTok
    cached rate — roughly 12× cheaper for the cached portion.
    """
    result = {
        "estimated_cost_usd": 0.0,
        "prompt_tokens": 10_000,
        "completion_tokens": 1_000,
        "total_tokens": 11_000,
        "cache_read_tokens": 9_000,
        "model": _FIREWORKS_DEEPSEEK,
    }
    cost, _, _, _ = _resolve_hermes_cost(result)
    cached_aware = fireworks_pricing.cost_from_usage(
        10_000, 1_000, _FIREWORKS_DEEPSEEK, cached_prompt_tokens=9_000
    )
    cached_blind = fireworks_pricing.cost_from_usage(
        10_000, 1_000, _FIREWORKS_DEEPSEEK
    )
    assert cost == cached_aware
    assert cost < cached_blind, "cached-aware cost must be strictly cheaper"


def test_resolve_hermes_cost_skips_fallback_when_no_tokens() -> None:
    """Empty calls (no tokens, no cost from hermes) stay at $0."""
    cost, p, c, t = _resolve_hermes_cost(
        {
            "estimated_cost_usd": 0.0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "model": _FIREWORKS_DEEPSEEK,
        }
    )
    assert cost == 0.0
    assert (p, c, t) == (0, 0, 0)


def test_resolve_hermes_cost_handles_missing_model() -> None:
    """If model is missing we cannot bill — return zero, don't crash."""
    cost, _, _, _ = _resolve_hermes_cost(
        {
            "estimated_cost_usd": 0.0,
            "prompt_tokens": 1_000,
            "completion_tokens": 100,
            "total_tokens": 1_100,
        }
    )
    assert cost == 0.0
