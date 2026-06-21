"""Budget and governor carrier contracts."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GovernorBudget:
    """Budget carrier consumed by future governors."""

    cost_limit: float | None = None
    seconds_limit: float | None = None
    token_limit: int | None = None


@dataclass(frozen=True)
class GovernorProjection:
    """Projected budget state at a workflow coordinate."""

    coordinate: str
    budget: GovernorBudget
    consumed_cost: float = 0.0
    consumed_seconds: float = 0.0
    consumed_tokens: int = 0
