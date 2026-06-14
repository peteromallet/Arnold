"""Sprint 3 acceptance test #6 — legacy phase CLI subcommands still work.

The brief commits to "CLI subcommands unchanged — megaplan
plan/critique/gate/finalize/execute/review remain." This test exercises
each standalone phase subcommand on a mock-worker plan and asserts the
expected state transitions land.

Today these handlers are wired via ``megaplan.cli`` — each
``handle_<phase>`` is the in-process entry point. The Sprint-3
Pipeline port adds a Step wrapper alongside, but does not change the
handler signatures. This test pins that.
"""

from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path
from typing import Any

import pytest

import arnold.pipelines.megaplan as megaplan

from tests.conftest import make_args_factory


def _make_args(plan_name: str, project_dir: Path, **overrides: Any) -> Namespace:
    defaults: dict[str, Any] = {
        "plan": plan_name,
        "idea": "legacy cli compat",
        "name": plan_name,
        "robustness": "robust",
    }
    defaults.update(overrides)
    return make_args_factory(project_dir)(**defaults)


@pytest.fixture
def cli_plan(bootstrap_fixture: tuple[Path, Path]):
    root, project_dir = bootstrap_fixture

    init_args = _make_args(plan_name="cli-compat", project_dir=project_dir, plan=None)
    response = megaplan.handle_init(root, init_args)
    plan_name = response["plan"]
    plan_dir = megaplan.plans_root(root) / plan_name

    megaplan.handle_override(
        root,
        _make_args(plan_name=plan_name, project_dir=project_dir,
                   plan=plan_name, override_action="add-note", note="cli compat"),
    )
    return root, project_dir, plan_name, plan_dir


def test_prep_subcommand_transitions_to_prepped(cli_plan) -> None:
    root, project_dir, plan_name, plan_dir = cli_plan
    response = megaplan.handlers.handle_prep(root, _make_args(plan_name, project_dir))
    assert response["state"] == "prepped"
    assert (plan_dir / "prep.json").exists()


def test_plan_subcommand_transitions_to_planned(cli_plan) -> None:
    root, project_dir, plan_name, plan_dir = cli_plan
    megaplan.handlers.handle_prep(root, _make_args(plan_name, project_dir))
    response = megaplan.handle_plan(root, _make_args(plan_name, project_dir))
    assert response["state"] == "planned"
    assert (plan_dir / "plan_v1.md").exists()


def test_critique_subcommand_transitions_to_critiqued(cli_plan) -> None:
    root, project_dir, plan_name, plan_dir = cli_plan
    megaplan.handlers.handle_prep(root, _make_args(plan_name, project_dir))
    megaplan.handle_plan(root, _make_args(plan_name, project_dir))
    response = megaplan.handle_critique(root, _make_args(plan_name, project_dir))
    assert response["state"] == "critiqued"


def test_gate_subcommand_returns_recommendation(cli_plan) -> None:
    root, project_dir, plan_name, plan_dir = cli_plan
    megaplan.handlers.handle_prep(root, _make_args(plan_name, project_dir))
    megaplan.handle_plan(root, _make_args(plan_name, project_dir))
    megaplan.handle_critique(root, _make_args(plan_name, project_dir))
    response = megaplan.handle_gate(root, _make_args(plan_name, project_dir))
    assert response["recommendation"] in {"PROCEED", "ITERATE", "ESCALATE", "TIEBREAKER"}


def test_finalize_execute_review_full_cycle(cli_plan) -> None:
    root, project_dir, plan_name, plan_dir = cli_plan
    # Walk to gate-proceed using the standard mock-worker sequence.
    megaplan.handlers.handle_prep(root, _make_args(plan_name, project_dir))
    megaplan.handle_plan(root, _make_args(plan_name, project_dir))
    megaplan.handle_critique(root, _make_args(plan_name, project_dir))
    gate1 = megaplan.handle_gate(root, _make_args(plan_name, project_dir))
    if gate1["recommendation"] == "ITERATE":
        megaplan.handle_revise(root, _make_args(plan_name, project_dir))
        megaplan.handle_critique(root, _make_args(plan_name, project_dir))
        megaplan.handle_gate(root, _make_args(plan_name, project_dir))

    fin = megaplan.handle_finalize(root, _make_args(plan_name, project_dir))
    assert fin["state"] == "finalized"
    exe = megaplan.handle_execute(
        root,
        _make_args(plan_name, project_dir, user_approved=True, confirm_destructive=True),
    )
    assert exe["state"] == "executed"
    rev = megaplan.handle_review(root, _make_args(plan_name, project_dir))
    assert rev["state"] == "done"
    assert (plan_dir / "review.json").exists()
    state = json.loads((plan_dir / "state.json").read_text())
    assert state["current_state"] == "done"
