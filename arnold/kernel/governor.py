"""Budget and governor carrier contracts.

The governor is journal-folded: every reservation, settlement, and release is
recorded as an event, and the current budget state is derived by folding those
events. Caps declared in the manifest are enforced before execution advances.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from arnold.kernel.events import EventEnvelope


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


@dataclass(frozen=True)
class BudgetReservation:
    """Pre-execution reservation against a budget cap."""

    node_ref: str
    cost: float = 0.0
    seconds: float = 0.0
    tokens: int = 0


@dataclass(frozen=True)
class BudgetSettlement:
    """Post-execution settlement of a prior reservation."""

    node_ref: str
    reservation_id: str
    actual_cost: float = 0.0
    actual_seconds: float = 0.0
    actual_tokens: int = 0


@dataclass(frozen=True)
class BudgetRelease:
    """Release of an unused reservation."""

    node_ref: str
    reservation_id: str
    released_cost: float = 0.0
    released_seconds: float = 0.0
    released_tokens: int = 0


@dataclass
class GovernorState:
    """Folded budget state derived from a journal."""

    reservations: dict[str, BudgetReservation] = field(default_factory=dict)
    consumed_cost: float = 0.0
    consumed_seconds: float = 0.0
    consumed_tokens: int = 0
    released_cost: float = 0.0
    released_seconds: float = 0.0
    released_tokens: int = 0

    @property
    def net_cost(self) -> float:
        return self.consumed_cost - self.released_cost

    @property
    def net_seconds(self) -> float:
        return self.consumed_seconds - self.released_seconds

    @property
    def net_tokens(self) -> int:
        return self.consumed_tokens - self.released_tokens

    def check(self, budget: GovernorBudget, coordinate: str = "") -> GovernorProjection:
        """Return a projection and raise if any cap is exceeded."""

        projection = GovernorProjection(
            coordinate=coordinate,
            budget=budget,
            consumed_cost=self.net_cost,
            consumed_seconds=self.net_seconds,
            consumed_tokens=self.net_tokens,
        )
        if budget.cost_limit is not None and self.net_cost >= budget.cost_limit:
            raise BudgetExceeded(
                f"cost cap exceeded at {coordinate}: "
                f"{self.net_cost} >= {budget.cost_limit}"
            )
        if budget.seconds_limit is not None and self.net_seconds >= budget.seconds_limit:
            raise BudgetExceeded(
                f"seconds cap exceeded at {coordinate}: "
                f"{self.net_seconds} >= {budget.seconds_limit}"
            )
        if budget.token_limit is not None and self.net_tokens >= budget.token_limit:
            raise BudgetExceeded(
                f"token cap exceeded at {coordinate}: "
                f"{self.net_tokens} >= {budget.token_limit}"
            )
        return projection


class BudgetExceeded(Exception):
    """Raised when a budget cap would be exceeded."""


GOVERNOR_EVENT_KINDS = frozenset({
    "budget_reserved",
    "budget_settled",
    "budget_released",
})


def reservation_payload(reservation: BudgetReservation) -> Mapping[str, Any]:
    return {
        "node_ref": reservation.node_ref,
        "reservation_id": f"{reservation.node_ref}:reserve",
        "cost": reservation.cost,
        "seconds": reservation.seconds,
        "tokens": reservation.tokens,
    }


def settlement_payload(settlement: BudgetSettlement) -> Mapping[str, Any]:
    return {
        "node_ref": settlement.node_ref,
        "reservation_id": settlement.reservation_id,
        "actual_cost": settlement.actual_cost,
        "actual_seconds": settlement.actual_seconds,
        "actual_tokens": settlement.actual_tokens,
    }


def release_payload(release: BudgetRelease) -> Mapping[str, Any]:
    return {
        "node_ref": release.node_ref,
        "reservation_id": release.reservation_id,
        "released_cost": release.released_cost,
        "released_seconds": release.released_seconds,
        "released_tokens": release.released_tokens,
    }


def _extract_float(payload: Mapping[str, Any], key: str) -> float:
    value = payload.get(key, 0.0)
    if isinstance(value, (int, float)):
        return float(value)
    return 0.0


def _extract_int(payload: Mapping[str, Any], key: str) -> int:
    value = payload.get(key, 0)
    if isinstance(value, int):
        return value
    return 0


def fold_governor_state(events: tuple[EventEnvelope, ...]) -> GovernorState:
    """Fold budget state from a sequence of governor events."""

    state = GovernorState()
    for event in events:
        if event.kind not in GOVERNOR_EVENT_KINDS:
            continue
        payload = event.payload
        node_ref = payload.get("node_ref", "")
        reservation_id = payload.get("reservation_id", f"{node_ref}:reserve")

        if event.kind == "budget_reserved":
            state.reservations[reservation_id] = BudgetReservation(
                node_ref=node_ref,
                cost=_extract_float(payload, "cost"),
                seconds=_extract_float(payload, "seconds"),
                tokens=_extract_int(payload, "tokens"),
            )
        elif event.kind == "budget_settled":
            state.reservations.pop(reservation_id, None)
            state.consumed_cost += _extract_float(payload, "actual_cost")
            state.consumed_seconds += _extract_float(payload, "actual_seconds")
            state.consumed_tokens += _extract_int(payload, "actual_tokens")
        elif event.kind == "budget_released":
            state.reservations.pop(reservation_id, None)
            state.released_cost += _extract_float(payload, "released_cost")
            state.released_seconds += _extract_float(payload, "released_seconds")
            state.released_tokens += _extract_int(payload, "released_tokens")

    return state


def node_budget_policy(
    manifest_budget: GovernorBudget | None,
    node_budget: GovernorBudget | None,
) -> GovernorBudget:
    """Merge manifest-level and node-level budgets; node values take precedence."""

    base = manifest_budget or GovernorBudget()
    override = node_budget or GovernorBudget()
    return GovernorBudget(
        cost_limit=override.cost_limit if override.cost_limit is not None else base.cost_limit,
        seconds_limit=override.seconds_limit if override.seconds_limit is not None else base.seconds_limit,
        token_limit=override.token_limit if override.token_limit is not None else base.token_limit,
    )


__all__ = [
    "BudgetExceeded",
    "BudgetRelease",
    "BudgetReservation",
    "BudgetSettlement",
    "GovernorBudget",
    "GovernorProjection",
    "GovernorState",
    "fold_governor_state",
    "node_budget_policy",
    "release_payload",
    "reservation_payload",
    "settlement_payload",
]
