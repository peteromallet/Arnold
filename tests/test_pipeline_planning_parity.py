"""Sprint 5 Chunk A — end-to-end parity for the canonical planning Pipeline.

The legacy byte-for-byte WORKFLOW parity test (which asserted edge-by-
edge equivalence between the compiled Pipeline and the legacy state-name
``WORKFLOW`` dict) has been retired in Sprint 5 Chunk A. The Pipeline
shape is intentionally different now: stages are keyed by phase name
(``prep / plan / critique / gate / revise / finalize / execute / review
/ tiebreaker``) and the gate Step's recommendation edges sit directly
on the ``gate`` stage. Asserting structural equivalence with the legacy
state-name shape would be hostile to the refactor.

This test asserts the post-Sprint-5 parity contract:

1. The compiled Pipeline contains the expected phase-name nodes with
   the entry on ``prep``.
2. Driving a mock-worker planning run through ``run_pipeline_with_policy``
   reaches ``current_state == "done"`` — the only behavioural parity that
   matters now that the legacy state machine is no longer the spec.
"""

from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

import pytest

import megaplan
import megaplan._core
import megaplan._core.io as io_module
import megaplan.cli

from megaplan._pipeline.executor import run_pipeline_with_policy
from megaplan._pipeline.planning import compile_planning_pipeline
from megaplan._pipeline.runtime import policy_from_cli_args
from megaplan._pipeline.types import StepContext


EXPECTED_PHASE_STAGES = {
    "prep", "plan", "critique", "gate", "revise",
    "finalize", "execute", "review", "tiebreaker",
}


def test_base_pipeline_has_canonical_phase_nodes() -> None:
    pipeline = compile_planning_pipeline()
    assert set(pipeline.stages.keys()) == EXPECTED_PHASE_STAGES
    assert pipeline.entry == "prep"


def test_gate_stage_carries_typed_recommendation_edges() -> None:
    pipeline = compile_planning_pipeline()
    gate_edges = [e for e in pipeline.stages["gate"].edges if e.kind == "gate"]
    recs = sorted(e.recommendation for e in gate_edges)
    assert recs == ["escalate", "iterate", "proceed", "tiebreaker"], recs


def test_gate_stage_total_edge_count_locks_extras() -> None:
    """T11 parity: the gate stage carries exactly 8 edges — the four
    ``kind='gate'`` recommendation edges plus the four label-only
    fallback/override edges (revise, gate, override force-proceed,
    override abort)."""
    pipeline = compile_planning_pipeline()
    gate_stage = pipeline.stages["gate"]
    assert len(gate_stage.edges) == 8, gate_stage.edges
    label_only = [e for e in gate_stage.edges if e.kind == "normal"]
    label_targets = {(e.label, e.target) for e in label_only}
    assert label_targets == {
        ("revise", "revise"),
        ("gate", "finalize"),
        ("override force-proceed", "finalize"),
        ("override abort", "halt"),
    }, label_targets


def test_tiebreaker_stage_edges_are_three_gate_recommendation_edges() -> None:
    """T11 LOAD-BEARING: the tiebreaker stage carries exactly three
    ``kind='gate'`` recommendation edges with the mapping
    ``{iterate→critique, proceed→finalize, escalate→finalize}``. The
    legacy label-only edges (``critique→critique``,
    ``tiebreaker_decide→critique``) are gone."""
    pipeline = compile_planning_pipeline()
    tb_stage = pipeline.stages["tiebreaker"]
    assert len(tb_stage.edges) == 3, tb_stage.edges
    for e in tb_stage.edges:
        assert e.kind == "gate", e
    mapping = {e.recommendation: e.target for e in tb_stage.edges}
    assert mapping == {
        "iterate": "critique",
        "proceed": "finalize",
        "escalate": "finalize",
    }, mapping


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
        plan=None, idea="planning parity", name="pp", project_dir=str(project_dir),
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


def test_compiled_pipeline_drives_a_run_to_done(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End-to-end behavioural parity: a mock planning run driven by the
    canonical compiled Pipeline reaches ``current_state == 'done'``."""
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

    state = json.loads((plan_dir / "state.json").read_text())
    assert state["current_state"] == "done", state["current_state"]
