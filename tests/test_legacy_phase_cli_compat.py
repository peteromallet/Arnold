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

import megaplan
import megaplan._core
import megaplan._core.io as io_module
import megaplan.cli


def _make_args(plan_name: str, project_dir: Path, **overrides: Any) -> Namespace:
    base = {
        "plan": plan_name,
        "idea": "legacy cli compat",
        "name": plan_name,
        "project_dir": str(project_dir),
        "auto_approve": None,
        "robustness": "robust",
        "agent": None,
        "ephemeral": False,
        "fresh": False,
        "persist": False,
        "confirm_destructive": True,
        "user_approved": False,
        "confirm_self_review": False,
        "batch": None,
        "override_action": None,
        "note": None,
        "reason": "",
        "strict_notes": None,
        "source": "user",
    }
    base.update(overrides)
    return Namespace(**base)


@pytest.fixture
def cli_plan(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    root = tmp_path / "root"
    project_dir = tmp_path / "project"
    config_path = tmp_path / "config"
    root.mkdir()
    project_dir.mkdir()
    (project_dir / ".git").mkdir()

    monkeypatch.setenv(megaplan.MOCK_ENV_VAR, "1")
    monkeypatch.setattr(
        megaplan._core.shutil,
        "which",
        lambda name: "/usr/bin/mock" if name in {"claude", "codex"} else None,
    )
    monkeypatch.setattr(io_module, "config_dir", lambda home=None: config_path)
    monkeypatch.setattr(megaplan.cli, "config_dir", lambda home=None: config_path)

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
