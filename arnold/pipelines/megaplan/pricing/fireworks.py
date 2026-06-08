"""Fireworks AI pricing table (USD per million tokens).

Sourced from https://docs.fireworks.ai/serverless/pricing (Standard tier).
Verified 2026-05-12. Update when Fireworks revises rates.

Each model entry is ``(input, cached_input, output)`` per 1M tokens.

Note on cached input: hermes_worker currently passes a single
``prompt_tokens`` count (uncached + cached summed). We don't yet have a
breakdown of cached vs. uncached at the megaplan layer, so
``cost_from_usage`` uses the full ``input`` rate for everything in
``prompt_tokens``. This OVER-estimates cost for cache-heavy runs. If
hermes starts surfacing a `cached_input_tokens` field, switch to billing
those separately at the cached rate.
"""

from __future__ import annotations

from typing import Any  # noqa: F401  (kept for parity with codex_pricing.py)

# {model_name_or_prefix: (input_per_mtok_usd, cached_input_per_mtok_usd, output_per_mtok_usd)}
# Match by the *trailing* segment of model_actual: e.g.
# "accounts/fireworks/models/deepseek-v4-pro" -> "deepseek-v4-pro".
FIREWORKS_PRICING: dict[str, tuple[float, float, float]] = {
    "deepseek-v4-pro": (1.74, 0.145, 3.48),
    "kimi-k2p6": (0.95, 0.16, 4.00),
    # Add others as needed.
}

DEFAULT_PRICING: tuple[float, float, float] = (0.0, 0.0, 0.0)


def cost_from_usage(
    prompt_tokens: int,
    completion_tokens: int,
    model: str | None,
    *,
    cached_prompt_tokens: int = 0,
) -> float:
    """Compute USD cost from a token count + model name.

    ``model`` can be a full Fireworks path like
    ``accounts/fireworks/models/deepseek-v4-pro`` or just the trailing
    segment. Unknown models return ``0.0`` (caller should log/flag).
    Zero tokens always return ``0.0``.

    ``cached_prompt_tokens`` is optional — if the caller has a breakdown
    of cached vs. uncached input, pass the cached count here and the
    cheaper rate is applied to it. If unset (default), everything in
    ``prompt_tokens`` is billed at the full input rate.
    """
    if not model:
        return 0.0
    short = model.rsplit("/", 1)[-1]
    rates = FIREWORKS_PRICING.get(short, DEFAULT_PRICING)
    in_rate, cached_rate, out_rate = rates
    try:
        prompt = int(prompt_tokens or 0)
        completion = int(completion_tokens or 0)
        cached = int(cached_prompt_tokens or 0)
    except (TypeError, ValueError):
        return 0.0
    cached = max(0, min(cached, prompt))  # cached can't exceed prompt total
    uncached = prompt - cached
    return (uncached * in_rate + cached * cached_rate + completion * out_rate) / 1_000_000
