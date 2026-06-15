"""Anthropic Claude pricing table and token estimation helpers.

Rates verified against `megaplan/agent/agent/usage_pricing.py` (which carries
the official Anthropic prompt-caching pricing snapshot) and treated as stable
across the Claude 4.x line: Anthropic's published Opus/Sonnet/Haiku per-token
rates have not changed within the 4.x release series.

Each entry: ``(input, cached_read, cached_write, output)`` per 1M tokens, USD.

## Forward billing

Use ``cost_from_usage(prompt_tokens, completion_tokens, model)`` (matches the
shape of ``codex_pricing`` and ``fireworks_pricing``).

## Reverse estimation

For historical receipts that captured ``cost_usd`` but not ``prompt_tokens`` /
``completion_tokens`` (the bug we just fixed), use
``estimate_tokens_from_cost(cost, model, ratio)`` to back out approximate
counts assuming a fixed prompt:completion ratio.

This is **lossy** — there is one equation and two unknowns. The estimate is
useful for aggregate analytics ("how many tokens did Q2 megaplan runs burn")
but not for billing reconciliation. Default ratio is 10:1, which is a
reasonable middle ground for megaplan-style usage (long contextual prompts,
modest structured outputs). Override per-call if you have a better prior.
"""

from __future__ import annotations

# {model_match: (input, cached_read, cached_write, output)} per 1M tokens, USD.
#
# Match is by *prefix* on the trailing path segment, so:
#   "claude-opus-4-20250514"       -> matches "claude-opus-4"
#   "anthropic/claude-opus-4-7"    -> matches "claude-opus-4"
#   "claude-opus-4.6"              -> matches "claude-opus-4"
# Use the longest prefix that still distinguishes the model family.
CLAUDE_PRICING: dict[str, tuple[float, float, float, float]] = {
    "claude-opus-4": (15.00, 1.50, 18.75, 75.00),
    "claude-sonnet-4": (3.00, 0.30, 3.75, 15.00),
    "claude-haiku-4": (0.25, 0.025, 0.3125, 1.25),
    # Older / fallback families.
    "claude-3-opus": (15.00, 1.50, 18.75, 75.00),
    "claude-3-5-sonnet": (3.00, 0.30, 3.75, 15.00),
    "claude-3-5-haiku": (0.80, 0.08, 1.00, 4.00),
}

DEFAULT_MODEL_FAMILY = "claude-opus-4"
"""Family to assume when model_actual is missing or generic.

Megaplan's default ``claude`` profile slot resolves to Opus, so historical
receipts with ``model_actual=None`` or ``model_configured='claude'`` are
overwhelmingly Opus runs.
"""

DEFAULT_PROMPT_COMPLETION_RATIO = 10.0
"""Default assumption for reverse estimation: prompts are 10× completions.

Calibrated against live megaplan receipts where input:output runs ~10-60:1
for plan/critique phases. 10:1 is conservative (under-estimates total tokens
for very prompt-heavy runs).
"""


def _resolve_rates(model: str | None) -> tuple[float, float, float, float] | None:
    """Return ``(input, cached_read, cached_write, output)`` for a model, or None."""
    if not model:
        return None
    short = model.rsplit("/", 1)[-1].lower()
    # Strip date suffix like "-20250514" or version suffix like "-7" so the
    # prefix match handles "claude-opus-4-7" / "claude-opus-4.6" / etc.
    for prefix, rates in CLAUDE_PRICING.items():
        if short.startswith(prefix):
            return rates
    return None


def cost_from_usage(
    prompt_tokens: int,
    completion_tokens: int,
    model: str | None,
    *,
    cached_read_tokens: int = 0,
    cached_write_tokens: int = 0,
) -> float:
    """Compute USD cost from a token count + model name.

    ``cached_read_tokens`` and ``cached_write_tokens`` are optional. If unset,
    everything in ``prompt_tokens`` is billed at the full input rate.
    Otherwise the cached counts are billed at the cheaper rates and only the
    remainder of ``prompt_tokens`` is billed at the full input rate.
    """
    rates = _resolve_rates(model)
    if rates is None:
        return 0.0
    in_rate, cr_rate, cw_rate, out_rate = rates
    try:
        p = int(prompt_tokens or 0)
        c = int(completion_tokens or 0)
        cr = int(cached_read_tokens or 0)
        cw = int(cached_write_tokens or 0)
    except (TypeError, ValueError):
        return 0.0
    cr = max(0, min(cr, p))
    cw = max(0, min(cw, p - cr))
    uncached = max(0, p - cr - cw)
    return (uncached * in_rate + cr * cr_rate + cw * cw_rate + c * out_rate) / 1_000_000


def estimate_tokens_from_cost(
    cost_usd: float,
    model: str | None = None,
    *,
    ratio: float = DEFAULT_PROMPT_COMPLETION_RATIO,
) -> tuple[int, int] | None:
    """Back out approximate ``(prompt_tokens, completion_tokens)`` from a cost.

    Lossy reverse of ``cost_from_usage`` — assumes ``prompt = ratio *
    completion`` and that all input is uncached (worst case for the
    estimate, since uncached input is the most expensive input rate).

    Returns ``None`` if the model can't be resolved or the cost is zero.

    Example: $0.225 of Opus 4 at the default 10:1 ratio yields roughly
    1000 completion + 10000 prompt = 11000 tokens estimated.
    """
    if cost_usd <= 0:
        return None
    rates = _resolve_rates(model or DEFAULT_MODEL_FAMILY)
    if rates is None:
        return None
    in_rate, _cr, _cw, out_rate = rates
    # cost = (P * in_rate + C * out_rate) / 1M, with P = ratio * C
    # => C = cost * 1M / (ratio * in_rate + out_rate)
    denominator = ratio * in_rate + out_rate
    if denominator <= 0:
        return None
    completion = (cost_usd * 1_000_000) / denominator
    prompt = ratio * completion
    return int(round(prompt)), int(round(completion))
