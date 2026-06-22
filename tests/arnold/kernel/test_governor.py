from __future__ import annotations

import pytest

from arnold.kernel import (
    BudgetExceeded,
    BudgetRelease,
    BudgetReservation,
    BudgetSettlement,
    EventEnvelope,
    EventFamily,
    GovernorBudget,
    GovernorProjection,
    GovernorState,
    ManifestReference,
    fold_governor_state,
    node_budget_policy,
    release_payload,
    reservation_payload,
    settlement_payload,
)


def _event(kind: str, payload: dict) -> EventEnvelope:
    return EventEnvelope(
        event_id=f"evt:{kind}",
        family=EventFamily.NODE_LIFECYCLE,
        kind=kind,
        manifest=ManifestReference(alias="demo", manifest_hash="sha256:" + "a" * 64),
        run_id="run-1",
        payload_schema_hash="sha256:" + "b" * 64,
        payload=payload,
    )


def test_reservation_is_journaled_before_execution() -> None:
    reservation = BudgetReservation(node_ref="n1", cost=1.0, seconds=2.0, tokens=10)
    event = _event("budget_reserved", reservation_payload(reservation))

    state = fold_governor_state((event,))
    assert "n1:reserve" in state.reservations
    assert state.reservations["n1:reserve"].cost == 1.0


def test_settlement_consumes_reservation_after_execution() -> None:
    reservation = BudgetReservation(node_ref="n1", cost=1.0, seconds=2.0, tokens=10)
    settlement = BudgetSettlement(
        node_ref="n1",
        reservation_id="n1:reserve",
        actual_cost=1.0,
        actual_seconds=2.0,
        actual_tokens=10,
    )
    events = (
        _event("budget_reserved", reservation_payload(reservation)),
        _event("budget_settled", settlement_payload(settlement)),
    )

    state = fold_governor_state(events)
    assert "n1:reserve" not in state.reservations
    assert state.net_cost == 1.0
    assert state.net_seconds == 2.0
    assert state.net_tokens == 10


def test_release_frees_unused_reservation() -> None:
    reservation = BudgetReservation(node_ref="n1", cost=5.0)
    release = BudgetRelease(
        node_ref="n1",
        reservation_id="n1:reserve",
        released_cost=5.0,
    )
    events = (
        _event("budget_reserved", reservation_payload(reservation)),
        _event("budget_released", release_payload(release)),
    )

    state = fold_governor_state(events)
    assert "n1:reserve" not in state.reservations
    assert state.net_cost == -5.0


def test_node_cost_cap_blocks_execution() -> None:
    state = GovernorState(consumed_cost=5.0)
    budget = GovernorBudget(cost_limit=5.0)

    with pytest.raises(BudgetExceeded, match="cost cap exceeded"):
        state.check(budget, coordinate="n1")


def test_manifest_cost_cap_blocks_execution() -> None:
    state = GovernorState(consumed_cost=9.5)
    budget = GovernorBudget(cost_limit=10.0)

    # Under cap succeeds.
    projection = state.check(budget)
    assert isinstance(projection, GovernorProjection)

    # Reaching the cap fails.
    state.consumed_cost = 10.0
    with pytest.raises(BudgetExceeded, match="cost cap exceeded"):
        state.check(budget)


def test_seconds_cap_blocks_execution() -> None:
    state = GovernorState(consumed_seconds=60.0)
    budget = GovernorBudget(seconds_limit=60.0)

    with pytest.raises(BudgetExceeded, match="seconds cap exceeded"):
        state.check(budget, coordinate="n1")


def test_token_cap_blocks_execution() -> None:
    state = GovernorState(consumed_tokens=100)
    budget = GovernorBudget(token_limit=100)

    with pytest.raises(BudgetExceeded, match="token cap exceeded"):
        state.check(budget, coordinate="n1")


def test_node_budget_overrides_manifest_budget() -> None:
    manifest_budget = GovernorBudget(cost_limit=100.0, seconds_limit=60.0)
    node_budget = GovernorBudget(cost_limit=50.0)

    merged = node_budget_policy(manifest_budget, node_budget)
    assert merged.cost_limit == 50.0
    assert merged.seconds_limit == 60.0
    assert merged.token_limit is None


def test_governor_ignores_non_governor_events() -> None:
    events = (
        _event("node_started", {"node_ref": "n1"}),
        _event("node_completed", {"node_ref": "n1"}),
    )
    state = fold_governor_state(events)
    assert state.net_cost == 0.0
    assert not state.reservations


def test_projection_reports_consumed_values() -> None:
    state = GovernorState(consumed_cost=3.0, consumed_seconds=1.5, consumed_tokens=7)
    projection = state.check(GovernorBudget(cost_limit=10.0))

    assert projection.consumed_cost == 3.0
    assert projection.consumed_seconds == 1.5
    assert projection.consumed_tokens == 7
