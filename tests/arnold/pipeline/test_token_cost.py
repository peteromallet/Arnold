from __future__ import annotations

import ast
import inspect
from dataclasses import dataclass
from decimal import Decimal

from arnold.pipeline.cost_types import CanonicalUsage
from arnold.pipeline.token_cost import (
    PricingEntry,
    estimate_cost_usd,
    estimate_usage_cost,
    format_duration_compact,
    format_token_count_compact,
    get_pricing_entry,
    has_known_pricing,
    normalize_usage,
    resolve_billing_route,
)


_PRICING = {
    ("test", "model-a"): PricingEntry(
        input_cost_per_million=Decimal("2.00"),
        output_cost_per_million=Decimal("8.00"),
        cache_read_cost_per_million=Decimal("0.50"),
        cache_write_cost_per_million=Decimal("3.00"),
        request_cost=Decimal("0.01"),
        source="user_override",
        pricing_version="test-token-v1",
    )
}


@dataclass
class _Details:
    cached_tokens: int = 0
    cache_creation_tokens: int = 0
    cache_write_tokens: int = 0
    reasoning_tokens: int = 0


@dataclass
class _Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0
    prompt_tokens_details: _Details | None = None
    input_tokens_details: _Details | None = None
    output_tokens_details: _Details | None = None


def test_resolve_billing_route_infers_provider_prefix() -> None:
    route = resolve_billing_route("openai/gpt-4o-mini")

    assert route.provider == "openai"
    assert route.model == "gpt-4o-mini"
    assert route.billing_mode == "official_docs_snapshot"


def test_estimate_usage_cost_prices_all_token_buckets_and_request_cost() -> None:
    result = estimate_usage_cost(
        "model-a",
        CanonicalUsage(
            input_tokens=1_000,
            output_tokens=500,
            cache_read_tokens=200,
            cache_write_tokens=100,
            request_count=2,
        ),
        provider="test",
        pricing_rows=_PRICING,
    )

    assert result.amount_usd == Decimal("0.0264")
    assert result.status == "estimated"
    assert result.source == "user_override"
    assert result.pricing_version == "test-token-v1"


def test_estimate_usage_cost_returns_unknown_when_required_cache_price_missing() -> None:
    result = estimate_usage_cost(
        "model-b",
        CanonicalUsage(cache_write_tokens=1),
        provider="test",
        pricing_rows={
            ("test", "model-b"): PricingEntry(
                input_cost_per_million=Decimal("1"),
                output_cost_per_million=Decimal("1"),
                source="user_override",
            )
        },
    )

    assert result.amount_usd is None
    assert result.status == "unknown"
    assert result.notes == ("cache-write pricing unavailable for route",)


def test_estimate_usage_cost_marks_subscription_route_included() -> None:
    result = estimate_usage_cost(
        "gpt-4o-mini",
        CanonicalUsage(input_tokens=1_000, output_tokens=500),
        provider="openai-codex",
    )

    assert result.amount_usd == Decimal("0")
    assert result.status == "included"
    assert result.label == "included"


def test_openrouter_metadata_pricing_is_injected_not_imported() -> None:
    def fetch_metadata() -> dict[str, dict[str, object]]:
        return {
            "vendor/model": {
                "pricing": {
                    "prompt": "0.000001",
                    "completion": "0.000002",
                    "cache_read": "0.0000001",
                }
            }
        }

    entry = get_pricing_entry(
        "vendor/model",
        provider="openrouter",
        model_metadata_fetcher=fetch_metadata,
    )

    assert entry is not None
    assert entry.input_cost_per_million == Decimal("1.000000")
    assert entry.output_cost_per_million == Decimal("2.000000")
    assert entry.cache_read_cost_per_million == Decimal("0.1000000")
    assert entry.source == "provider_models_api"


def test_has_known_pricing_uses_snapshot_and_custom_rows() -> None:
    assert has_known_pricing("gpt-4o-mini", provider="openai")
    assert has_known_pricing("model-a", provider="test", pricing_rows=_PRICING)
    assert not has_known_pricing("missing", provider="test", pricing_rows=_PRICING)


def test_legacy_estimate_cost_usd_uses_non_cached_token_buckets() -> None:
    assert estimate_cost_usd(
        "model-a",
        1_000,
        500,
        provider="test",
        pricing_rows=_PRICING,
    ) == 0.016


def test_normalize_usage_for_openai_chat_subtracts_cached_prompt_tokens() -> None:
    usage = normalize_usage(
        _Usage(
            prompt_tokens=100,
            completion_tokens=20,
            prompt_tokens_details=_Details(cached_tokens=30, cache_write_tokens=10),
        )
    )

    assert usage.input_tokens == 60
    assert usage.output_tokens == 20
    assert usage.cache_read_tokens == 30
    assert usage.cache_write_tokens == 10
    assert usage.total_tokens == 120


def test_normalize_usage_for_anthropic_preserves_cache_creation_tokens() -> None:
    usage = normalize_usage(
        _Usage(
            input_tokens=100,
            output_tokens=20,
            cache_read_input_tokens=30,
            cache_creation_input_tokens=10,
        ),
        provider="anthropic",
    )

    assert usage.input_tokens == 100
    assert usage.output_tokens == 20
    assert usage.cache_read_tokens == 30
    assert usage.cache_write_tokens == 10


def test_format_helpers_are_stable_for_compact_display() -> None:
    assert format_duration_compact(90) == "2m"
    assert format_duration_compact(7_200) == "2h"
    assert format_token_count_compact(1_250) == "1.25K"
    assert format_token_count_compact(2_500_000) == "2.5M"


def test_token_cost_module_has_no_megaplan_imports() -> None:
    import arnold.pipeline.token_cost as token_cost

    tree = ast.parse(inspect.getsource(token_cost))
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            module = node.module or ""
            assert "megaplan" not in module
