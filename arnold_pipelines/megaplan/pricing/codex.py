"""Pricing table and cost calculation for OpenAI codex (GPT-5.x) sessions.

Codex CLI runs on a subscription bundle in day-to-day operator usage, but for
fair multi-arm bake-off comparisons we want a real USD cost per token. The
codex CLI persists per-session token counters to a JSONL rollout under
``~/.codex/sessions``; this module turns those counters into dollars.

Rates are USD per 1M tokens. ``cached`` covers OpenAI's prefix-cache hit price
(input prefix that the API already saw), which is roughly 90% off the full
input rate. ``reasoning_output_tokens`` is billed at the same rate as regular
output, so we add the two before applying the output rate.

## API shape

``cost_from_usage(prompt_tokens, completion_tokens, model, *,
cached_prompt_tokens=0)`` matches :mod:`megaplan.pricing.claude` and
:mod:`megaplan.pricing.fireworks`. ``prompt_tokens`` is the full input
count (including any cached prefix) and ``cached_prompt_tokens`` is the
portion of that input billed at the cheaper cached rate.

If a caller has the raw codex ``total_token_usage`` dict (with
``input_tokens`` / ``cached_input_tokens`` / ``output_tokens`` /
``reasoning_output_tokens``), use :func:`cost_from_codex_usage_dict` to
extract counts and bill in one call.

Models without a canonical entry in :data:`PRICING` are returned as
``None``/unpriced; rates are never borrowed from an older model family.
"""

from __future__ import annotations

from typing import Any

PRICING: dict[str, dict[str, float]] = {
    # GPT-5 baseline (verified against OpenAI public pricing).
    "gpt-5": {"input": 1.25, "cached": 0.125, "output": 10.00},
    # GPT-5.5 historical rate. Newer unknown models remain explicitly unpriced.
    "gpt-5.5": {"input": 5.00, "cached": 0.50, "output": 30.00},
}

# Kept as a compatibility export for callers that explicitly choose a priced
# default. Cost functions no longer substitute this rate for an unknown model.
DEFAULT_MODEL = "gpt-5.5"


def is_model_priced(model: str | None) -> bool:
    """Return whether *model* has a canonical rate in this table."""

    return bool(model) and model in PRICING


def cost_from_usage(
    prompt_tokens: int,
    completion_tokens: int,
    model: str | None,
    *,
    cached_prompt_tokens: int = 0,
) -> float | None:
    """Compute USD cost from a token count + model name.

    ``prompt_tokens`` is the full input token count (including any cached
    prefix). ``cached_prompt_tokens`` is the portion of that input billed
    at the cheaper cached rate; if unset, everything in ``prompt_tokens``
    is billed at the full input rate.

    ``completion_tokens`` should be the sum of regular output and any
    reasoning-output tokens (both billed at the output rate).

    Unknown, ``None``, and empty model IDs return ``None`` (explicitly
    unpriced). Returns ``0.0`` on token-count parse error for a known model.
    """
    rates = PRICING.get(model) if model else None
    if rates is None:
        return None
    try:
        prompt = int(prompt_tokens or 0)
        completion = int(completion_tokens or 0)
        cached = int(cached_prompt_tokens or 0)
    except (TypeError, ValueError):
        return 0.0
    cached = max(0, min(cached, prompt))  # cached can't exceed prompt total
    uncached = prompt - cached
    return (
        uncached * rates["input"]
        + cached * rates["cached"]
        + completion * rates["output"]
    ) / 1_000_000


def cost_from_codex_usage_dict(
    usage: dict[str, Any] | None,
    model: str | None = None,
) -> float | None:
    """Return the USD cost for a codex ``total_token_usage`` blob.

    ``usage`` is the dict under ``info.total_token_usage`` in a codex
    ``token_count`` event, e.g.::

        {"input_tokens": 66607, "cached_input_tokens": 4864,
         "output_tokens": 1089, "reasoning_output_tokens": 230,
         "total_tokens": 67696}

    Missing keys default to 0. Returns ``0.0`` for ``None`` / empty usage and
    a known model; returns ``None`` when the model itself is unpriced.
    """
    if not isinstance(usage, dict):
        return None if not model or model not in PRICING else 0.0
    try:
        prompt_tokens = int(usage.get("input_tokens", 0) or 0)
        cached_prompt_tokens = int(usage.get("cached_input_tokens", 0) or 0)
        output_tokens = int(usage.get("output_tokens", 0) or 0)
        reasoning_tokens = int(usage.get("reasoning_output_tokens", 0) or 0)
    except (TypeError, ValueError):
        return 0.0
    return cost_from_usage(
        prompt_tokens=prompt_tokens,
        completion_tokens=output_tokens + reasoning_tokens,
        model=model,
        cached_prompt_tokens=cached_prompt_tokens,
    )
