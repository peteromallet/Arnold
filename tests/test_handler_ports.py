"""Sprint 4 Chunk B acceptance — each ported Step works in isolation.

Pins the contract that eight named Step classes exist, each one is a
proper Step (passes the runtime_checkable Protocol), and each one
can be invoked in isolation under MEGAPLAN_MOCK_WORKERS=1.
"""

from __future__ import annotations

from argparse import Namespace
from pathlib import Path
from typing import Any

import pytest

import megaplan
import megaplan._core
import megaplan._core.io as io_module
import megaplan.cli

from arnold.pipelines.megaplan.stages import (
    CritiqueStep,
    ExecuteStep,
    FinalizeStep,
    GateStep,
    PlanStep,
    PrepStep,
    ReviewStep,
    ReviseStep,
)
from megaplan._pipeline.types import Step, StepContext


@pytest.fixture
def mock_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
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

    init_args = Namespace(
        plan=None, idea="handler port test", name="ports", project_dir=str(project_dir),
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
        Namespace(**{**vars(init_args), "plan": plan_name, "override_action": "add-note", "note": "scoped"}),
    )
    return root, project_dir, plan_name, plan_dir


def _ctx(plan_dir: Path, root: Path, project_dir: Path, plan_name: str) -> StepContext:
    return StepContext(
        plan_dir=plan_dir,
        state={"name": plan_name},
        profile={"root": root, "project_dir": project_dir},
        mode="code",
        inputs={},
        budget=None,
    )


def test_each_step_class_satisfies_protocol() -> None:
    for cls in [PrepStep, PlanStep, CritiqueStep, GateStep,
                ReviseStep, FinalizeStep, ExecuteStep, ReviewStep]:
        instance = cls()
        assert isinstance(instance, Step), cls.__name__


def test_prep_step_transitions_to_prepped(mock_root) -> None:
    root, project_dir, plan_name, plan_dir = mock_root
    PrepStep().run(_ctx(plan_dir, root, project_dir, plan_name))
    assert (plan_dir / "prep.json").exists()


def test_plan_step_emits_plan_v1(mock_root) -> None:
    root, project_dir, plan_name, plan_dir = mock_root
    PrepStep().run(_ctx(plan_dir, root, project_dir, plan_name))
    PlanStep().run(_ctx(plan_dir, root, project_dir, plan_name))
    assert (plan_dir / "plan_v1.md").exists()


def test_gate_step_emits_typed_verdict(mock_root) -> None:
    root, project_dir, plan_name, plan_dir = mock_root
    PrepStep().run(_ctx(plan_dir, root, project_dir, plan_name))
    PlanStep().run(_ctx(plan_dir, root, project_dir, plan_name))
    CritiqueStep().run(_ctx(plan_dir, root, project_dir, plan_name))
    result = GateStep().run(_ctx(plan_dir, root, project_dir, plan_name))
    assert result.verdict is not None
    assert result.verdict.recommendation in {"proceed", "iterate", "tiebreaker", "escalate"}


def test_execute_step_defaults_user_approved(mock_root) -> None:
    """ExecuteStep should auto-pass user_approved=True so the Pipeline
    can dispatch without the legacy CLI confirmation prompt."""
    root, project_dir, plan_name, plan_dir = mock_root
    PrepStep().run(_ctx(plan_dir, root, project_dir, plan_name))
    PlanStep().run(_ctx(plan_dir, root, project_dir, plan_name))
    CritiqueStep().run(_ctx(plan_dir, root, project_dir, plan_name))
    g1 = GateStep().run(_ctx(plan_dir, root, project_dir, plan_name))
    if g1.verdict is not None and g1.verdict.recommendation == "iterate":
        ReviseStep().run(_ctx(plan_dir, root, project_dir, plan_name))
        CritiqueStep().run(_ctx(plan_dir, root, project_dir, plan_name))
        GateStep().run(_ctx(plan_dir, root, project_dir, plan_name))
    FinalizeStep().run(_ctx(plan_dir, root, project_dir, plan_name))
    ExecuteStep().run(_ctx(plan_dir, root, project_dir, plan_name))
    assert (plan_dir / "execution.json").exists()


def test_review_step_transitions_to_done(mock_root) -> None:
    root, project_dir, plan_name, plan_dir = mock_root
    PrepStep().run(_ctx(plan_dir, root, project_dir, plan_name))
    PlanStep().run(_ctx(plan_dir, root, project_dir, plan_name))
    CritiqueStep().run(_ctx(plan_dir, root, project_dir, plan_name))
    g1 = GateStep().run(_ctx(plan_dir, root, project_dir, plan_name))
    if g1.verdict is not None and g1.verdict.recommendation == "iterate":
        ReviseStep().run(_ctx(plan_dir, root, project_dir, plan_name))
        CritiqueStep().run(_ctx(plan_dir, root, project_dir, plan_name))
        GateStep().run(_ctx(plan_dir, root, project_dir, plan_name))
    FinalizeStep().run(_ctx(plan_dir, root, project_dir, plan_name))
    ExecuteStep().run(_ctx(plan_dir, root, project_dir, plan_name))
    ReviewStep().run(_ctx(plan_dir, root, project_dir, plan_name))
    import json
    state = json.loads((plan_dir / "state.json").read_text())
    assert state["current_state"] == "done"
