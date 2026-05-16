"""Sense-check fix: the runnable Pipeline drives a real plan to done.

The legacy ``compile_planning_pipeline()`` produces a Pipeline whose
gate-recommendation edges sit on the wrong stage (``critiqued``
instead of ``gate``), preventing the runtime from following gate
verdict dispatch. ``compile_runnable_pipeline()`` is the
structurally-correct alternative — this test proves it actually
drives a real mock plan from prep all the way to ``done``.
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

from megaplan._pipeline.executor import run_pipeline_with_policy
from megaplan._pipeline.planning import compile_runnable_pipeline
from megaplan._pipeline.runtime import policy_from_cli_args
from megaplan._pipeline.types import StepContext


def _mock_plan(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    root = tmp_path / "root"
    project_dir = tmp_path / "project"
    config_path = tmp_path / "config"
    root.mkdir()
    project_dir.mkdir()
    (project_dir / ".git").mkdir()

    monkeypatch.setenv(megaplan.MOCK_ENV_VAR, "1")
    monkeypatch.setattr(
        megaplan._core.shutil, "which",
        lambda name: "/usr/bin/mock" if name in {"claude", "codex"} else None,
    )
    monkeypatch.setattr(io_module, "config_dir", lambda home=None: config_path)
    monkeypatch.setattr(megaplan.cli, "config_dir", lambda home=None: config_path)

    init_args = Namespace(
        plan=None, idea="runnable e2e", name="rn", project_dir=str(project_dir),
        auto_approve=None, robustness="robust", agent=None,
        ephemeral=False, fresh=False, persist=False,
        confirm_destructive=True, user_approved=False, confirm_self_review=False,
        batch=None, override_action=None, note=None, reason="",
        strict_notes=None, source="user",
    )
    response = megaplan.handle_init(root, init_args)
    plan_name = response["plan"]
    plan_dir = megaplan.plans_root(root) / plan_name

    megaplan.handle_override(
        root,
        Namespace(**{**vars(init_args), "plan": plan_name,
                     "override_action": "add-note", "note": "scoped"}),
    )
    return root, project_dir, plan_name, plan_dir


def test_runnable_pipeline_drives_plan_to_done(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The runnable pipeline must reach state=done via real handlers."""
    root, project_dir, plan_name, plan_dir = _mock_plan(tmp_path, monkeypatch)

    pipeline = compile_runnable_pipeline()
    ctx = StepContext(
        plan_dir=plan_dir,
        state={"name": plan_name, **json.loads((plan_dir / "state.json").read_text())},
        profile={"root": root, "project_dir": project_dir},
        mode="code",
        inputs={},
        budget=None,
    )
    policy = policy_from_cli_args(
        stall_threshold=999, max_iterations=30,
        max_cost_usd=None, on_escalate="force-proceed",
    )

    result = run_pipeline_with_policy(
        pipeline, ctx, artifact_root=plan_dir, policy=policy,
    )

    state = json.loads((plan_dir / "state.json").read_text())
    assert state["current_state"] == "done", state["current_state"]

    # Every plan deliverable landed.
    for artifact in ["prep.json", "plan_v1.md", "final.md",
                     "execution.json", "review.json"]:
        assert (plan_dir / artifact).exists(), artifact

    # Final stage hit "review" (the terminal step).
    assert result.get("final_stage") in {"review", "review_step"}


def test_runnable_pipeline_iterates_on_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When gate emits iterate, the pipeline loops critique → gate."""
    root, project_dir, plan_name, plan_dir = _mock_plan(tmp_path, monkeypatch)

    pipeline = compile_runnable_pipeline()
    ctx = StepContext(
        plan_dir=plan_dir,
        state={"name": plan_name, **json.loads((plan_dir / "state.json").read_text())},
        profile={"root": root, "project_dir": project_dir},
        mode="code",
        inputs={},
        budget=None,
    )
    policy = policy_from_cli_args(
        stall_threshold=999, max_iterations=30,
        max_cost_usd=None, on_escalate="force-proceed",
    )

    run_pipeline_with_policy(
        pipeline, ctx, artifact_root=plan_dir, policy=policy,
    )

    # The mock harness's first gate is ITERATE, so plan_v2 must land
    # (revise wrote it).
    assert (plan_dir / "plan_v2.md").exists()


def test_runnable_pipeline_uses_named_step_classes() -> None:
    """Every primary stage uses a named Step class, not a generic
    HandlerStep or _RuntimeStep placeholder."""
    from megaplan._pipeline.stages.prep import PrepStep
    from megaplan._pipeline.stages.plan import PlanStep
    from megaplan._pipeline.stages.critique import CritiqueStep
    from megaplan._pipeline.stages.gate import GateStep
    from megaplan._pipeline.stages.revise import ReviseStep
    from megaplan._pipeline.stages.finalize import FinalizeStep
    from megaplan._pipeline.stages.execute import ExecuteStep
    from megaplan._pipeline.stages.review import ReviewStep

    pipeline = compile_runnable_pipeline()
    expected = {
        "prep": PrepStep, "plan": PlanStep, "critique": CritiqueStep,
        "gate": GateStep, "revise": ReviseStep,
        "finalize": FinalizeStep, "execute": ExecuteStep,
        "review": ReviewStep,
    }
    for stage_name, cls in expected.items():
        actual = type(pipeline.stages[stage_name].step)
        assert actual is cls, (stage_name, actual, cls)


def test_runnable_pipeline_gate_has_typed_recommendation_edges() -> None:
    """The runnable pipeline's gate stage carries all four typed
    recommendation edges — proving the dispatch is on the right node."""
    pipeline = compile_runnable_pipeline()
    gate_edges = [e for e in pipeline.stages["gate"].edges if e.kind == "gate"]
    recs = sorted(e.recommendation for e in gate_edges)
    assert recs == ["escalate", "iterate", "proceed", "tiebreaker"], recs
