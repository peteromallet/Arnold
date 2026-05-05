"""Pricing table and cost calculation for OpenAI codex (GPT-5.x) sessions.

Codex CLI runs on a subscription bundle in day-to-day operator usage, but for
fair multi-arm bake-off comparisons we want a real USD cost per token. The
codex CLI persists per-session token counters to a JSONL rollout under
``~/.codex/sessions``; this module turns those counters into dollars.

Rates are USD per 1M tokens. ``cached`` covers OpenAI's prefix-cache hit price
(input prefix that the API already saw), which is roughly 90% off the full
input rate. ``reasoning_output_tokens`` is billed at the same rate as regular
output, so we add the two before applying the output rate.
"""

from __future__ import annotations

from typing import Any

PRICING: dict[str, dict[str, float]] = {
    # GPT-5 baseline (verified against OpenAI public pricing).
    "gpt-5": {"input": 1.25, "cached": 0.125, "output": 10.00},
    # GPT-5.5 — current default for codex high-effort runs.
    "gpt-5.5": {"input": 5.00, "cached": 0.50, "output": 30.00},
}

DEFAULT_MODEL = "gpt-5.5"


def cost_from_usage(usage: dict[str, Any] | None, model: str | None = None) -> float:
    """Return the USD cost for a codex ``total_token_usage`` blob.

    ``usage`` is the dict under ``info.total_token_usage`` in a codex
    ``token_count`` event, e.g.::

        {"input_tokens": 66607, "cached_input_tokens": 4864,
         "output_tokens": 1089, "reasoning_output_tokens": 230,
         "total_tokens": 67696}

    Missing keys default to 0. Unknown ``model`` falls back to
    :data:`DEFAULT_MODEL`. Returns ``0.0`` for ``None`` / empty input.
    """
    if not isinstance(usage, dict):
        return 0.0
    rates = PRICING.get(model or DEFAULT_MODEL, PRICING[DEFAULT_MODEL])
    try:
        input_tokens = int(usage.get("input_tokens", 0) or 0)
        cached = int(usage.get("cached_input_tokens", 0) or 0)
        output_tokens = int(usage.get("output_tokens", 0) or 0)
        reasoning = int(usage.get("reasoning_output_tokens", 0) or 0)
    except (TypeError, ValueError):
        return 0.0
    full_in = max(input_tokens - cached, 0)
    out = output_tokens + reasoning
    cost = (
        full_in * rates["input"]
        + cached * rates["cached"]
        + out * rates["output"]
    ) / 1_000_000
    return float(cost)
