from __future__ import annotations

from typing import Any, Mapping

DEEPSEEK_PROMPT_CACHE_MISS_USD_PER_1M = 0.27
DEEPSEEK_PROMPT_CACHE_HIT_USD_PER_1M = 0.07
DEEPSEEK_COMPLETION_USD_PER_1M = 1.10

DEEPSEEK_COST_BASIS_EXACT = "deepseek_cache_breakout"
DEEPSEEK_COST_BASIS_UPPER_BOUND = "prompt_upper_bound_no_cache_breakout"
DEEPSEEK_COST_BASIS_MIXED = "mixed_exact_and_upper_bound"
DEEPSEEK_COST_BASIS_NOT_AVAILABLE = "not_available"

_USAGE_KEYS: tuple[str, ...] = (
    "prompt_tokens",
    "completion_tokens",
    "total_tokens",
    "prompt_cache_hit_tokens",
    "prompt_cache_miss_tokens",
    "n_calls",
)


def empty_deepseek_usage() -> dict[str, int]:
    return {key: 0 for key in _USAGE_KEYS}


def coerce_deepseek_usage(value: Any) -> dict[str, int]:
    usage = empty_deepseek_usage()
    if not isinstance(value, Mapping):
        return usage
    for key in _USAGE_KEYS:
        raw = value.get(key)
        try:
            usage[key] = max(0, int(raw or 0))
        except (TypeError, ValueError):
            usage[key] = 0
    return usage


def add_deepseek_usage(*parts: Any) -> dict[str, int]:
    total = empty_deepseek_usage()
    for part in parts:
        usage = coerce_deepseek_usage(part)
        for key in _USAGE_KEYS:
            total[key] += usage[key]
    return total


def estimate_deepseek_cost_usd(
    usage: Any,
    *,
    cache_breakout_complete: bool,
) -> tuple[float, str]:
    normalized = coerce_deepseek_usage(usage)
    prompt_tokens = normalized["prompt_tokens"]
    completion_tokens = normalized["completion_tokens"]
    cache_hit_tokens = normalized["prompt_cache_hit_tokens"]
    cache_miss_tokens = normalized["prompt_cache_miss_tokens"]
    if normalized["n_calls"] <= 0 and prompt_tokens <= 0 and completion_tokens <= 0:
        return 0.0, DEEPSEEK_COST_BASIS_NOT_AVAILABLE
    if cache_breakout_complete:
        cost = (
            (cache_miss_tokens * DEEPSEEK_PROMPT_CACHE_MISS_USD_PER_1M)
            + (cache_hit_tokens * DEEPSEEK_PROMPT_CACHE_HIT_USD_PER_1M)
            + (completion_tokens * DEEPSEEK_COMPLETION_USD_PER_1M)
        ) / 1_000_000.0
        return cost, DEEPSEEK_COST_BASIS_EXACT
    cost = (
        (prompt_tokens * DEEPSEEK_PROMPT_CACHE_MISS_USD_PER_1M)
        + (completion_tokens * DEEPSEEK_COMPLETION_USD_PER_1M)
    ) / 1_000_000.0
    return cost, DEEPSEEK_COST_BASIS_UPPER_BOUND


def combine_deepseek_cost_bases(bases: list[Any]) -> str:
    normalized = [
        str(basis)
        for basis in bases
        if isinstance(basis, str) and basis and basis != DEEPSEEK_COST_BASIS_NOT_AVAILABLE
    ]
    if not normalized:
        return DEEPSEEK_COST_BASIS_NOT_AVAILABLE
    if len(set(normalized)) == 1:
        return normalized[0]
    return DEEPSEEK_COST_BASIS_MIXED
