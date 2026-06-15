from __future__ import annotations

from arnold.pipeline.cost_types import CanonicalUsage, CostResult


def test_canonical_usage_exposes_prompt_and_total_token_counts() -> None:
    usage = CanonicalUsage(
        input_tokens=100,
        output_tokens=50,
        cache_read_tokens=25,
        cache_write_tokens=10,
    )

    assert usage.prompt_tokens == 135
    assert usage.total_tokens == 185


def test_cost_result_preserves_unknown_amount_and_notes() -> None:
    result = CostResult(
        amount_usd=None,
        status="unknown",
        source="none",
        label="n/a",
        notes=("pricing missing",),
    )

    assert result.amount_usd is None
    assert result.status == "unknown"
    assert result.notes == ("pricing missing",)
