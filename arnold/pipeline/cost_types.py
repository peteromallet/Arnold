"""Neutral cost usage/result types shared between token and media pricing.

These types define the *cost result* contract — status, source provenance,
the ``CostResult`` dataclass, and canonical token usage — without coupling
to any specific pricing table or megaplan module.

Motivation
----------
* ``CostStatus``, ``CostSource``, ``CostResult``, and ``CanonicalUsage`` are
  the shared interface between ``estimate_usage_cost()`` (token) and
  ``compute_media_cost()`` (media).
* Extracting them into ``arnold.pipeline`` lets both pricing modules
  import the same contract without a megaplan dependency.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal, Optional

CostStatus = Literal["actual", "estimated", "included", "unknown"]
CostSource = Literal[
    "provider_cost_api",
    "provider_generation_api",
    "provider_models_api",
    "official_docs_snapshot",
    "user_override",
    "custom_contract",
    "none",
]


@dataclass(frozen=True)
class CostResult:
    """A single priced cost line — token or media.

    Fields mirror the existing megaplan ``CostResult`` contract exactly:
    """

    amount_usd: Optional[Decimal]
    status: CostStatus
    source: CostSource
    label: str
    fetched_at: Optional[datetime] = None
    pricing_version: Optional[str] = None
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class CanonicalUsage:
    """Canonical token usage buckets shared by neutral token pricing callers."""

    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    reasoning_tokens: int = 0
    request_count: int = 1
    raw_usage: Optional[dict[str, Any]] = None

    @property
    def prompt_tokens(self) -> int:
        return self.input_tokens + self.cache_read_tokens + self.cache_write_tokens

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.output_tokens
