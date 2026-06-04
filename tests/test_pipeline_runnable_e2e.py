"""The canonical planning Pipeline drives a real plan to done.

These tests pin the phase-keyed ``compile_planning_pipeline()`` shape:
gate recommendation edges live on the ``gate`` stage, named handler
steps are used for primary phases, and a real mock plan can run from
prep to ``done``.
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
from megaplan._pipeline.planning import compile_planning_pipeline
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

    pipeline = compile_planning_pipeline()
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

    pipeline = compile_planning_pipeline()
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
    handler placeholder."""
    from arnold.pipelines.megaplan.stages.prep import PrepStep
    from arnold.pipelines.megaplan.stages.plan import PlanStep
    from arnold.pipelines.megaplan.stages.critique import CritiqueStep
    from arnold.pipelines.megaplan.stages.gate import GateStep
    from arnold.pipelines.megaplan.stages.revise import ReviseStep
    from arnold.pipelines.megaplan.stages.finalize import FinalizeStep
    from arnold.pipelines.megaplan.stages.execute import ExecuteStep
    from arnold.pipelines.megaplan.stages.review import ReviewStep

    pipeline = compile_planning_pipeline()
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
    pipeline = compile_planning_pipeline()
    gate_edges = [e for e in pipeline.stages["gate"].edges if e.kind == "gate"]
    recs = sorted(e.recommendation for e in gate_edges)
    assert recs == ["escalate", "iterate", "proceed", "tiebreaker"], recs
