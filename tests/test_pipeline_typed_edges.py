"""Sprint 4 Chunk A acceptance — typed verdicts + typed edges.

Pins the new shape: Verdict carries a typed recommendation; Edge has a
kind discriminator; the compiled planning Pipeline emits typed
``kind="gate"`` edges for gate transitions; the executor dispatches
on verdict.recommendation first, falling back to the legacy
``kind="normal"`` label compare. No more packed
``"gate_iterate:revise"`` strings anywhere in production code.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

from megaplan._pipeline import (
    Edge,
    Pipeline,
    Stage,
    StepContext,
    StepResult,
    Verdict,
)
from megaplan._pipeline.executor import run_pipeline
from megaplan._pipeline.planning import compile_planning_pipeline


def test_verdict_has_typed_recommendation_and_override() -> None:
    v = Verdict(score=0.5, recommendation="iterate", override="force_proceed")
    assert v.recommendation == "iterate"
    assert v.override == "force_proceed"


def test_edge_default_kind_is_normal_with_no_recommendation() -> None:
    e = Edge(label="x", target="y")
    assert e.kind == "normal"
    assert e.recommendation is None


def test_edge_typed_gate_round_trips() -> None:
    e = Edge(label="iterate", target="planned", kind="gate", recommendation="iterate")
    assert e.kind == "gate"
    assert e.recommendation == "iterate"


def test_compiled_planning_emits_typed_gate_edges() -> None:
    """Sprint 5 Chunk A canonicalised the phase-name shape, so the gate
    Step's typed recommendation edges now live on the ``gate`` stage."""
    pipeline = compile_planning_pipeline()
    gate_stage = pipeline.stages["gate"]

    gate_edges = [e for e in gate_stage.edges if e.kind == "gate"]
    recs = sorted(e.recommendation for e in gate_edges)
    assert recs == ["escalate", "iterate", "proceed", "tiebreaker"], recs

    # Override fan-out falls back to kind="normal" with bare next_step
    # labels so each remains individually addressable.
    normal_overrides = [
        e for e in gate_stage.edges
        if e.kind == "normal" and e.label.startswith("override ")
    ]
    assert sorted(e.label for e in normal_overrides) == [
        "override abort", "override force-proceed",
    ]


def test_no_duplicate_gate_recommendations_per_stage() -> None:
    pipeline = compile_planning_pipeline()
    for stage_name, stage in pipeline.stages.items():
        if not hasattr(stage, "edges"):
            continue
        recs = [e.recommendation for e in stage.edges if e.kind == "gate"]
        assert len(recs) == len(set(recs)), (
            stage_name, recs
        )


def test_no_legacy_packed_gate_labels_in_production() -> None:
    proc = subprocess.run(
        ["git", "grep", "-E", "gate_iterate:|gate_proceed:|gate_tiebreaker:|gate_escalate:", "megaplan/_pipeline/"],
        cwd=Path(__file__).resolve().parent.parent,
        capture_output=True,
        text=True,
    )
    # `git grep` returns 1 when nothing matches — that's success.
    assert proc.returncode == 1, (
        f"found legacy packed labels in _pipeline/: {proc.stdout}"
    )


@dataclass
class _SyntheticJudge:
    """A judge Step that returns a fixed verdict for testing dispatch."""
    name: str = "judge"
    kind: str = "judge"
    prompt_key = None
    slot = None
    recommendation: str = "iterate"

    def run(self, ctx: StepContext) -> StepResult:
        return StepResult(
            verdict=Verdict(score=1.0, recommendation=self.recommendation),
            next="fallback",
            state_patch={"recommended": self.recommendation},
        )


@dataclass
class _LabelStep:
    name: str = "labelled"
    kind: str = "produce"
    prompt_key = None
    slot = None
    next_label: str = "forward"

    def run(self, ctx: StepContext) -> StepResult:
        return StepResult(next=self.next_label)


def test_executor_dispatches_by_verdict_recommendation(tmp_path: Path) -> None:
    judge = _SyntheticJudge(recommendation="iterate")
    pipeline = Pipeline(
        stages={
            "judge": Stage(
                name="judge", step=judge,
                edges=(
                    Edge(label="iterate", target="iterated", kind="gate",
                         recommendation="iterate"),
                    Edge(label="proceed", target="proceeded", kind="gate",
                         recommendation="proceed"),
                ),
            ),
            "iterated": Stage(name="iterated", step=_LabelStep(next_label="halt"),
                              edges=(Edge(label="halt", target="halt"),)),
            "proceeded": Stage(name="proceeded", step=_LabelStep(next_label="halt"),
                               edges=(Edge(label="halt", target="halt"),)),
        },
        entry="judge",
    )
    ctx = StepContext(plan_dir=tmp_path, state={}, profile=None, mode="code", inputs={})
    result = run_pipeline(pipeline, ctx, artifact_root=tmp_path)
    assert result["final_stage"] == "iterated", result


def test_executor_falls_back_to_label_for_normal_edges(tmp_path: Path) -> None:
    step = _LabelStep(next_label="forward")
    pipeline = Pipeline(
        stages={
            "labelled": Stage(
                name="labelled", step=step,
                edges=(
                    Edge(label="forward", target="next"),
                    Edge(label="iterate", target="never", kind="gate",
                         recommendation="iterate"),
                ),
            ),
            "next": Stage(name="next", step=_LabelStep(next_label="halt"),
                          edges=(Edge(label="halt", target="halt"),)),
            "never": Stage(name="never", step=_LabelStep(next_label="halt"),
                           edges=(Edge(label="halt", target="halt"),)),
        },
        entry="labelled",
    )
    ctx = StepContext(plan_dir=tmp_path, state={}, profile=None, mode="code", inputs={})
    result = run_pipeline(pipeline, ctx, artifact_root=tmp_path)
    assert result["final_stage"] == "next"
