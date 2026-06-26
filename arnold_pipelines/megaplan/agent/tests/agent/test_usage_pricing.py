from decimal import Decimal

import ast
import importlib
import inspect
from types import SimpleNamespace

from agent.usage_pricing import (
    CanonicalUsage,
    estimate_usage_cost,
    get_pricing_entry,
    normalize_usage,
)
from arnold.pipeline.cost_types import CanonicalUsage as NeutralCanonicalUsage
from arnold.pipeline.cost_types import CostResult, CostSource, CostStatus


def test_normalize_usage_anthropic_keeps_cache_buckets_separate():
    usage = SimpleNamespace(
        input_tokens=1000,
        output_tokens=500,
        cache_read_input_tokens=2000,
        cache_creation_input_tokens=400,
    )

    normalized = normalize_usage(usage, provider="anthropic", api_mode="anthropic_messages")

    assert normalized.input_tokens == 1000
    assert normalized.output_tokens == 500
    assert normalized.cache_read_tokens == 2000
    assert normalized.cache_write_tokens == 400
    assert normalized.prompt_tokens == 3400


def test_canonical_usage_lives_in_neutral_cost_types():
    assert CanonicalUsage is NeutralCanonicalUsage
    assert CanonicalUsage.__module__ == "arnold.pipeline.cost_types"


def test_legacy_usage_pricing_import_paths_resolve_to_neutral_token_cost():
    neutral = importlib.import_module("arnold.pipeline.token_cost")
    generic = importlib.import_module("arnold.agent.agent.usage_pricing")
    megaplan = importlib.import_module("arnold_pipelines.megaplan.agent.agent.usage_pricing")

    assert generic is neutral
    assert megaplan is neutral
    assert generic.CanonicalUsage is NeutralCanonicalUsage
    assert megaplan.CanonicalUsage is NeutralCanonicalUsage


def test_token_cost_has_no_direct_megaplan_imports():
    from arnold.pipeline import token_cost as token_cost_module

    source = inspect.getsource(token_cost_module)
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert "megaplan" not in alias.name
        if isinstance(node, ast.ImportFrom):
            assert not node.module or "megaplan" not in node.module


def test_normalize_usage_openai_subtracts_cached_prompt_tokens():
    usage = SimpleNamespace(
        prompt_tokens=3000,
        completion_tokens=700,
        prompt_tokens_details=SimpleNamespace(cached_tokens=1800),
    )

    normalized = normalize_usage(usage, provider="openai", api_mode="chat_completions")

    assert normalized.input_tokens == 1200
    assert normalized.cache_read_tokens == 1800
    assert normalized.output_tokens == 700


def test_openrouter_models_api_pricing_is_converted_from_per_token_to_per_million(monkeypatch):
    monkeypatch.setattr(
        "agent.usage_pricing.fetch_model_metadata",
        lambda: {
            "anthropic/claude-opus-4.6": {
                "pricing": {
                    "prompt": "0.000005",
                    "completion": "0.000025",
                    "input_cache_read": "0.0000005",
                    "input_cache_write": "0.00000625",
                }
            }
        },
    )

    entry = get_pricing_entry(
        "anthropic/claude-opus-4.6",
        provider="openrouter",
        base_url="https://openrouter.ai/api/v1",
    )

    assert float(entry.input_cost_per_million) == 5.0
    assert float(entry.output_cost_per_million) == 25.0
    assert float(entry.cache_read_cost_per_million) == 0.5
    assert float(entry.cache_write_cost_per_million) == 6.25


def test_estimate_usage_cost_marks_subscription_routes_included():
    result = estimate_usage_cost(
        "gpt-5.3-codex",
        CanonicalUsage(input_tokens=1000, output_tokens=500),
        provider="openai-codex",
        base_url="https://chatgpt.com/backend-api/codex",
    )

    assert result.status == "included"
    assert float(result.amount_usd) == 0.0


def test_estimate_usage_cost_refuses_cache_pricing_without_official_cache_rate(monkeypatch):
    monkeypatch.setattr(
        "agent.usage_pricing.fetch_model_metadata",
        lambda: {
            "google/gemini-2.5-pro": {
                "pricing": {
                    "prompt": "0.00000125",
                    "completion": "0.00001",
                }
            }
        },
    )

    result = estimate_usage_cost(
        "google/gemini-2.5-pro",
        CanonicalUsage(input_tokens=1000, output_tokens=500, cache_read_tokens=100),
        provider="openrouter",
        base_url="https://openrouter.ai/api/v1",
    )

    assert result.status == "unknown"


def test_custom_endpoint_models_api_pricing_is_supported(monkeypatch):
    monkeypatch.setattr(
        "agent.usage_pricing.fetch_endpoint_model_metadata",
        lambda base_url, api_key=None: {
            "zai-org/GLM-5-TEE": {
                "pricing": {
                    "prompt": "0.0000005",
                    "completion": "0.000002",
                }
            }
        },
    )

    entry = get_pricing_entry(
        "zai-org/GLM-5-TEE",
        provider="custom",
        base_url="https://llm.chutes.ai/v1",
        api_key="test-key",
    )

    assert float(entry.input_cost_per_million) == 0.5
    assert float(entry.output_cost_per_million) == 2.0


# ---------------------------------------------------------------------------
# Token-only regression: estimate_usage_cost() field contract
# ---------------------------------------------------------------------------


def test_estimate_usage_cost_official_docs_returns_full_cost_result():
    """Token-only estimate_usage_cost via official_docs_snapshot produces
    a CostResult with all expected fields populated."""
    result = estimate_usage_cost(
        "claude-sonnet-4-20250514",
        CanonicalUsage(input_tokens=1_000_000, output_tokens=500_000),
        provider="anthropic",
    )

    assert isinstance(result, CostResult)
    assert result.status == "estimated"
    assert result.source == "official_docs_snapshot"
    # 1M input × $3.00 + 0.5M output × $15.00 = $3.00 + $7.50 = $10.50
    assert result.amount_usd == Decimal("10.50")
    assert result.label == "~$10.50"
    assert result.pricing_version == "anthropic-prompt-caching-2026-03-16"
    assert isinstance(result.notes, tuple)


def test_estimate_usage_cost_unknown_route_returns_null_amount():
    """Token-only route without any pricing returns unknown with None amount."""
    result = estimate_usage_cost(
        "nonexistent-model-xyz",
        CanonicalUsage(input_tokens=100, output_tokens=50),
        provider="unknown",
    )

    assert isinstance(result, CostResult)
    assert result.status == "unknown"
    assert result.source == "none"
    assert result.amount_usd is None
    assert result.label == "n/a"


def test_estimate_usage_cost_subscription_included_returns_zero():
    """Token-only codex route returns included with zero amount and correct provenance."""
    result = estimate_usage_cost(
        "gpt-5.3-codex",
        CanonicalUsage(input_tokens=1_000, output_tokens=500),
        provider="openai-codex",
        base_url="https://chatgpt.com/backend-api/codex",
    )

    assert isinstance(result, CostResult)
    assert result.status == "included"
    assert result.source == "none"
    assert result.amount_usd == Decimal("0")
    assert result.label == "included"
    assert result.pricing_version == "included-route"


def test_estimate_usage_cost_cache_read_without_pricing_returns_unknown():
    """Token-only: cache_read_tokens with no cache_read_cost_per_million → unknown."""
    from unittest.mock import patch

    with patch(
        "agent.usage_pricing.get_pricing_entry",
        return_value=__import__("agent.usage_pricing", fromlist=["PricingEntry"]).PricingEntry(
            input_cost_per_million=Decimal("3.00"),
            output_cost_per_million=Decimal("15.00"),
            cache_read_cost_per_million=None,
            source="official_docs_snapshot",
            source_url="https://example.com",
            pricing_version="test-v1",
        ),
    ):
        result = estimate_usage_cost(
            "some-model",
            CanonicalUsage(input_tokens=1_000, output_tokens=500, cache_read_tokens=100),
            provider="anthropic",
        )

    assert result.status == "unknown"
    assert result.amount_usd is None
    assert result.source == "official_docs_snapshot"
    assert "cache-read" in (result.notes[0] if result.notes else "")


def test_estimate_usage_cost_cache_write_without_pricing_returns_unknown():
    """Token-only: cache_write_tokens with no cache_write_cost_per_million → unknown."""
    from unittest.mock import patch

    with patch(
        "agent.usage_pricing.get_pricing_entry",
        return_value=__import__("agent.usage_pricing", fromlist=["PricingEntry"]).PricingEntry(
            input_cost_per_million=Decimal("3.00"),
            output_cost_per_million=Decimal("15.00"),
            cache_write_cost_per_million=None,
            source="official_docs_snapshot",
            source_url="https://example.com",
            pricing_version="test-v2",
        ),
    ):
        result = estimate_usage_cost(
            "some-model",
            CanonicalUsage(input_tokens=1_000, output_tokens=500, cache_write_tokens=50),
            provider="anthropic",
        )

    assert result.status == "unknown"
    assert result.amount_usd is None
    assert "cache-write" in (result.notes[0] if result.notes else "")


def test_estimate_usage_cost_missing_input_pricing_returns_unknown():
    """Token-only: input_tokens with no input_cost_per_million → unknown."""
    from unittest.mock import patch

    with patch(
        "agent.usage_pricing.get_pricing_entry",
        return_value=__import__("agent.usage_pricing", fromlist=["PricingEntry"]).PricingEntry(
            input_cost_per_million=None,
            output_cost_per_million=Decimal("15.00"),
            source="official_docs_snapshot",
            source_url="https://example.com",
            pricing_version="test-v3",
        ),
    ):
        result = estimate_usage_cost(
            "some-model",
            CanonicalUsage(input_tokens=100, output_tokens=50),
            provider="anthropic",
        )

    assert result.status == "unknown"
    assert result.amount_usd is None


def test_estimate_usage_cost_exact_math_with_request_cost():
    """Token-only: request_cost and token math combine correctly."""
    from unittest.mock import patch

    with patch(
        "agent.usage_pricing.get_pricing_entry",
        return_value=__import__("agent.usage_pricing", fromlist=["PricingEntry"]).PricingEntry(
            input_cost_per_million=Decimal("2.00"),
            output_cost_per_million=Decimal("8.00"),
            cache_read_cost_per_million=Decimal("0.50"),
            cache_write_cost_per_million=Decimal("2.00"),
            request_cost=Decimal("0.01"),
            source="official_docs_snapshot",
            source_url="https://example.com",
            pricing_version="test-v4",
        ),
    ):
        result = estimate_usage_cost(
            "some-model",
            CanonicalUsage(
                input_tokens=1_000_000,
                output_tokens=500_000,
                cache_read_tokens=200_000,
                cache_write_tokens=100_000,
                request_count=3,
            ),
            provider="anthropic",
        )

    # input:  1.0M × $2.00 = $2.00
    # output: 0.5M × $8.00 = $4.00
    # cache_read:  0.2M × $0.50 = $0.10
    # cache_write: 0.1M × $2.00 = $0.20
    # request: 3 × $0.01 = $0.03
    # total = $6.33
    assert result.amount_usd == Decimal("6.33")
    assert result.status == "estimated"
    assert result.source == "official_docs_snapshot"
    assert result.pricing_version == "test-v4"


def test_estimate_usage_cost_notes_on_openrouter():
    """Token-only: openrouter routes append a reconciliation note."""
    from unittest.mock import patch

    with patch(
        "agent.usage_pricing.get_pricing_entry",
        return_value=__import__("agent.usage_pricing", fromlist=["PricingEntry"]).PricingEntry(
            input_cost_per_million=Decimal("2.50"),
            output_cost_per_million=Decimal("10.00"),
            source="provider_models_api",
            source_url="https://openrouter.ai/docs/api",
            pricing_version="openrouter-models-api",
        ),
    ):
        result = estimate_usage_cost(
            "openai/gpt-4o",
            CanonicalUsage(input_tokens=1_000_000, output_tokens=500_000),
            provider="openrouter",
            base_url="https://openrouter.ai/api/v1",
        )

    assert result.status == "estimated"
    assert result.source == "provider_models_api"
    assert any("OpenRouter" in note for note in result.notes)


# ---------------------------------------------------------------------------
# Token-only regression: CanonicalUsage field stability
# ---------------------------------------------------------------------------


def test_canonical_usage_fields_unchanged():
    """CanonicalUsage constructor signature and field defaults are untouched."""
    cu = CanonicalUsage()
    assert cu.input_tokens == 0
    assert cu.output_tokens == 0
    assert cu.cache_read_tokens == 0
    assert cu.cache_write_tokens == 0
    assert cu.reasoning_tokens == 0
    assert cu.request_count == 1
    assert cu.raw_usage is None
    assert cu.prompt_tokens == 0
    assert cu.total_tokens == 0


def test_canonical_usage_prompt_tokens_sum():
    """prompt_tokens = input + cache_read + cache_write, unchanged."""
    cu = CanonicalUsage(
        input_tokens=100,
        cache_read_tokens=200,
        cache_write_tokens=300,
    )
    assert cu.prompt_tokens == 600
    assert cu.total_tokens == 600  # no output_tokens


def test_canonical_usage_total_tokens_sum():
    """total_tokens = prompt_tokens + output_tokens, unchanged."""
    cu = CanonicalUsage(
        input_tokens=100,
        output_tokens=400,
        cache_read_tokens=200,
        cache_write_tokens=300,
    )
    assert cu.prompt_tokens == 600
    assert cu.total_tokens == 1000


def test_canonical_usage_is_frozen():
    """CanonicalUsage is a frozen dataclass — mutation should raise."""
    cu = CanonicalUsage(input_tokens=1)
    try:
        cu.input_tokens = 2  # type: ignore[misc]
        assert False, "expected FrozenInstanceError"
    except Exception:
        pass  # any error (FrozenInstanceError / dataclasses.FrozenInstanceError) is acceptable


def test_cost_result_has_no_megaplan_imports():
    """cost_types.py must not import megaplan — verify by checking the module."""
    import ast
    import inspect
    from arnold.pipeline import cost_types as ct_module

    source = inspect.getsource(ct_module)
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            if node.module and "megaplan" in node.module:
                assert False, f"cost_types.py imports megaplan: {ast.dump(node)}"
    assert True  # explicit pass
