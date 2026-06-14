"""Minimal pure-Python pricing table for DeepSeek / Fireworks / Hermes models.

Returns ``None`` for unknown models so callers can fall back to whatever
telemetry the upstream agent already produced.

No imports from ``arnold.pipelines.megaplan`` (zero-leak gate).
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Per-model pricing (USD per 1M tokens)
# ---------------------------------------------------------------------------

# DeepSeek direct models (api.deepseek.com)
_DEEPSEEK_PRICES: dict[str, tuple[float, float]] = {
    # model_lower -> (prompt_per_1M, completion_per_1M)
    "deepseek-chat": (0.27, 1.10),
    "deepseek-reasoner": (0.55, 2.19),
    "deepseek-v3": (0.27, 1.10),
    "deepseek-r1": (0.55, 2.19),
    "deepseek-r1-0528": (0.55, 2.19),
}

# Fireworks models — accessed via OpenRouter typically, but listed for
# completeness if direct Fireworks API keys are in play.
_FIREWORKS_PRICES: dict[str, float] = {
    # OpenRouter pricing for Fireworks-provided models (prompt+completion blended per 1M)
    "accounts/fireworks/models/deepseek-v3": 1.25,
    "accounts/fireworks/models/deepseek-r1": 3.00,
    "accounts/fireworks/models/deepseek-r1-0528": 3.00,
    "accounts/fireworks/models/llama-4-maverick": 0.90,
    "accounts/fireworks/models/llama-4-scout": 0.20,
}

# Hermes-specific fallbacks (when no provider/model granularity applies)
_HERMES_DEFAULT_PROMPT_PER_1M = 0.35
_HERMES_DEFAULT_COMPLETION_PER_1M = 1.20


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def pricing_for(model: str | None) -> tuple[float, float] | None:
    """Return ``(prompt_per_1M, completion_per_1M)`` or ``None``.

    The caller multiplies *prompt_tokens / 1e6* and *completion_tokens / 1e6*
    to get the total cost in USD.
    """
    if not model:
        return None

    lowered = model.lower()

    # Exact match on known DeepSeek direct models
    if lowered in _DEEPSEEK_PRICES:
        return _DEEPSEEK_PRICES[lowered]

    # Fireworks models — if the model string contains "fireworks/models/",
    # try an exact match first, then a blended fallback.
    if "fireworks/models/" in lowered:
        if lowered in _FIREWORKS_PRICES:
            blend = _FIREWORKS_PRICES[lowered]
            return (blend, blend)
        # Generic Fireworks fallback
        return (0.40, 1.60)

    # DeepSeek prefix match (catches versioned variants like deepseek-chat-v3-0324)
    if lowered.startswith("deepseek"):
        return (0.35, 1.40)

    # Hermes family default
    if "hermes" in lowered:
        return (_HERMES_DEFAULT_PROMPT_PER_1M, _HERMES_DEFAULT_COMPLETION_PER_1M)

    return None


def estimate_cost_usd(
    model: str | None,
    prompt_tokens: int,
    completion_tokens: int,
) -> float | None:
    """Return estimated cost in USD using the inline pricing table.

    Returns ``None`` when the model cannot be priced.
    """
    prices = pricing_for(model)
    if prices is None:
        return None
    prompt_per_1M, completion_per_1M = prices
    return (prompt_tokens / 1_000_000.0) * prompt_per_1M + (
        completion_tokens / 1_000_000.0
    ) * completion_per_1M
