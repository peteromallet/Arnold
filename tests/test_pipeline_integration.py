"""Post-Sprint-4 integration tests — every elegance property holds at once.

Drives a real planning flow through the Pipeline using the named Step
classes (PrepStep / PlanStep / CritiqueStep / GateStep / ReviseStep /
FinalizeStep / ExecuteStep / ReviewStep), with a mid-pipeline profile
swap to prove on-the-fly model rebinding works during a live walk.
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

from megaplan._pipeline.profile import Profile, load_profile
from arnold.pipelines.megaplan.stages.critique import CritiqueStep
from arnold.pipelines.megaplan.stages.execute import ExecuteStep
from arnold.pipelines.megaplan.stages.finalize import FinalizeStep
from arnold.pipelines.megaplan.stages.gate import GateStep
from arnold.pipelines.megaplan.stages.plan import PlanStep
from arnold.pipelines.megaplan.stages.prep import PrepStep
from arnold.pipelines.megaplan.stages.review import ReviewStep
from arnold.pipelines.megaplan.stages.revise import ReviseStep
from megaplan._pipeline.types import StepContext


@pytest.fixture
def mock_plan(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
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
        plan=None, idea="integration test", name="int", project_dir=str(project_dir),
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


def _ctx(plan_dir, root, project_dir, plan_name, profile):
    return StepContext(
        plan_dir=plan_dir,
        state={"name": plan_name, **json.loads((plan_dir / "state.json").read_text())},
        profile=profile,
        mode="code",
        inputs={},
        budget=None,
    )


def test_full_planning_run_through_named_steps(mock_plan) -> None:
    """End-to-end drive: every phase via the named Step class. No
    HandlerStep subprocess, no InProcessHandlerStep generic wrapper at
    the call site — just `PrepStep().run(ctx)` etc."""
    root, project_dir, plan_name, plan_dir = mock_plan
    pr_profile = {"root": root, "project_dir": project_dir}

    PrepStep().run(_ctx(plan_dir, root, project_dir, plan_name, pr_profile))
    PlanStep().run(_ctx(plan_dir, root, project_dir, plan_name, pr_profile))
    CritiqueStep().run(_ctx(plan_dir, root, project_dir, plan_name, pr_profile))
    g = GateStep().run(_ctx(plan_dir, root, project_dir, plan_name, pr_profile))
    if g.verdict and g.verdict.recommendation == "iterate":
        ReviseStep().run(_ctx(plan_dir, root, project_dir, plan_name, pr_profile))
        CritiqueStep().run(_ctx(plan_dir, root, project_dir, plan_name, pr_profile))
        GateStep().run(_ctx(plan_dir, root, project_dir, plan_name, pr_profile))
    FinalizeStep().run(_ctx(plan_dir, root, project_dir, plan_name, pr_profile))
    ExecuteStep().run(_ctx(plan_dir, root, project_dir, plan_name, pr_profile))
    ReviewStep().run(_ctx(plan_dir, root, project_dir, plan_name, pr_profile))

    state = json.loads((plan_dir / "state.json").read_text())
    assert state["current_state"] == "done"

    # Every plan deliverable landed.
    for expected in ["plan_v1.md", "prep.json", "final.md", "execution.json",
                     "review.json"]:
        assert (plan_dir / expected).exists(), expected


def test_named_steps_are_what_planning_pipeline_uses() -> None:
    """The compiled planning Pipeline uses the named Step classes, not
    legacy HandlerStep subprocess wrappers."""
    from megaplan._pipeline.planning import compile_planning_pipeline

    pipeline = compile_planning_pipeline()
    type_map = {
        "prep": "PrepStep",
        "plan": "PlanStep",
        "critique": "CritiqueStep",
        "gate": "GateStep",
        "finalize": "FinalizeStep",
        "execute": "ExecuteStep",
    }
    for stage_name, expected_class in type_map.items():
        actual = type(pipeline.stages[stage_name].step).__name__
        assert actual == expected_class, (stage_name, actual, expected_class)


def test_mid_pipeline_profile_swap_during_real_run(mock_plan) -> None:
    """Swap the profile between phases of a real (mock-worker) plan.
    Confirms the on-the-fly rebind survives a live walk."""
    root, project_dir, plan_name, plan_dir = mock_plan

    profile_a = Profile(name="custom-A", slots={
        "prep": "claude", "plan": "claude", "critique": "claude",
        "gate": "claude", "revise": "claude", "finalize": "claude",
        "execute": "claude", "review": "claude", "feedback": "claude",
        # carrying the test fixture pointers
        "root": root, "project_dir": project_dir,
    })

    # Phase 1 with profile A.
    profile_payload = {"root": root, "project_dir": project_dir, "_pipeline_profile": profile_a}
    PrepStep().run(_ctx(plan_dir, root, project_dir, plan_name, profile_payload))

    # Swap to profile B (different model spec on critique).
    profile_b = profile_a.with_slot("critique", "hermes:openai/gpt-5")
    profile_payload_b = {"root": root, "project_dir": project_dir, "_pipeline_profile": profile_b}

    PlanStep().run(_ctx(plan_dir, root, project_dir, plan_name, profile_payload_b))
    CritiqueStep().run(_ctx(plan_dir, root, project_dir, plan_name, profile_payload_b))

    # The profile object itself is immutable across the swap.
    assert profile_a.model_for("critique") == "claude"
    assert profile_b.model_for("critique") == "hermes:openai/gpt-5"
    assert profile_a is not profile_b

    state = json.loads((plan_dir / "state.json").read_text())
    assert state["current_state"] == "critiqued"


def test_planning_pipeline_carries_typed_gate_edges() -> None:
    """The wired-up production Pipeline still has the typed gate edges
    Chunk A introduced — no regression in elegance. Sprint 5 Chunk A
    canonicalised the phase-name shape, so the gate-recommendation edges
    now sit on the ``gate`` stage (not the legacy ``critiqued`` state)."""
    from megaplan._pipeline.planning import compile_planning_pipeline

    pipeline = compile_planning_pipeline()
    gate_edges = [e for e in pipeline.stages["gate"].edges if e.kind == "gate"]
    assert {e.recommendation for e in gate_edges} == {"iterate", "proceed", "tiebreaker", "escalate"}
