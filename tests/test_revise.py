from __future__ import annotations

from pathlib import Path

import pytest

import megaplan
from tests.conftest import PlanFixture, _make_plan_fixture_with_robustness, load_state


def test_light_revise_routes_to_finalize(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan_fixture = _make_plan_fixture_with_robustness(tmp_path, monkeypatch, robustness="light")
    make_args = plan_fixture.make_args

    megaplan.handle_plan(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    response = megaplan.handle_revise(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    state = load_state(plan_fixture.plan_dir)

    assert response["next_step"] == "finalize"
    assert state["current_state"] == megaplan.STATE_GATED


def test_standard_revise_routes_to_critique_and_clears_last_gate(plan_fixture: PlanFixture) -> None:
    make_args = plan_fixture.make_args

    megaplan.handle_plan(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    gate = megaplan.handle_gate(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    response = megaplan.handle_revise(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    state = load_state(plan_fixture.plan_dir)

    assert gate["recommendation"] == "ITERATE"
    assert response["state"] == megaplan.STATE_PLANNED
    assert response["next_step"] == "critique"
    assert state["current_state"] == megaplan.STATE_PLANNED
    assert state["last_gate"] == {}


def test_handle_revise_requires_prior_iterate_gate(plan_fixture: PlanFixture) -> None:
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))

    with pytest.raises(megaplan.CliError, match="ITERATE"):
        megaplan.handle_revise(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))


def test_replan_from_gated_resets_to_planned(plan_fixture: PlanFixture) -> None:
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    megaplan.handle_override(
        plan_fixture.root,
        plan_fixture.make_args(
            plan=plan_fixture.plan_name,
            override_action="force-proceed",
            reason="test gate override",
        ),
    )
    response = megaplan.handle_override(
        plan_fixture.root,
        plan_fixture.make_args(
            plan=plan_fixture.plan_name,
            override_action="replan",
            reason="edit directly",
            note="expand the verification section",
        ),
    )
    state = load_state(plan_fixture.plan_dir)

    assert response["state"] == megaplan.STATE_PLANNED
    assert state["last_gate"] == {}
    assert response["next_step"] == "critique"
