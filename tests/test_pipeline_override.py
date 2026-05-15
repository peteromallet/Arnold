"""Sprint 4 Chunk D — Override edges as first-class escape paths."""

from __future__ import annotations

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
from megaplan._pipeline.override import find_override_edge, override_edge


@dataclass
class _Halt:
    name: str = "halt_step"
    kind: str = "produce"
    prompt_key = None
    slot = None

    def run(self, ctx: StepContext) -> StepResult:
        return StepResult(next="halt")


@dataclass
class _Escapes:
    """A Step that escapes via Verdict.override."""

    name: str = "escapes"
    kind: str = "decide"
    prompt_key = None
    slot = None
    action: str = "force_proceed"

    def run(self, ctx: StepContext) -> StepResult:
        return StepResult(
            verdict=Verdict(score=0.0, override=self.action),
            next="fallback",
        )


def test_override_edge_helper_builds_correct_edge() -> None:
    e = override_edge("force_proceed", target="forced")
    assert e.kind == "override"
    assert e.label == "override force_proceed"
    assert e.target == "forced"


def test_find_override_edge_matches_by_label() -> None:
    edges = (
        Edge(label="ignored", target="x"),
        override_edge("force_proceed", target="forced"),
        override_edge("abort", target="aborted"),
    )
    assert find_override_edge(edges, "force_proceed").target == "forced"
    assert find_override_edge(edges, "abort").target == "aborted"
    assert find_override_edge(edges, "replan") is None


def test_executor_dispatches_override_edge(tmp_path: Path) -> None:
    pipeline = Pipeline(
        stages={
            "escapes": Stage(name="escapes", step=_Escapes(action="force_proceed"),
                             edges=(
                                 Edge(label="fallback", target="bad"),
                                 override_edge("force_proceed", target="forced"),
                             )),
            "forced": Stage(name="forced", step=_Halt(),
                            edges=(Edge(label="halt", target="halt"),)),
            "bad": Stage(name="bad", step=_Halt(),
                         edges=(Edge(label="halt", target="halt"),)),
        },
        entry="escapes",
    )
    ctx = StepContext(plan_dir=tmp_path, state={}, profile=None, mode="code", inputs={})
    result = run_pipeline(pipeline, ctx, artifact_root=tmp_path)
    assert result["final_stage"] == "forced"


def test_executor_override_takes_precedence_over_gate_rec(tmp_path: Path) -> None:
    """When both override and recommendation are set, override wins."""

    @dataclass
    class _Both:
        name: str = "both"
        kind: str = "decide"
        prompt_key = None
        slot = None

        def run(self, ctx: StepContext) -> StepResult:
            return StepResult(
                verdict=Verdict(score=0.0, recommendation="iterate",
                                override="abort"),
                next="fallback",
            )

    pipeline = Pipeline(
        stages={
            "both": Stage(name="both", step=_Both(),
                          edges=(
                              Edge(label="iterate", target="iter_done", kind="gate", recommendation="iterate"),
                              override_edge("abort", target="abort_done"),
                          )),
            "iter_done": Stage(name="iter_done", step=_Halt(),
                               edges=(Edge(label="halt", target="halt"),)),
            "abort_done": Stage(name="abort_done", step=_Halt(),
                                edges=(Edge(label="halt", target="halt"),)),
        },
        entry="both",
    )
    ctx = StepContext(plan_dir=tmp_path, state={}, profile=None, mode="code", inputs={})
    result = run_pipeline(pipeline, ctx, artifact_root=tmp_path)
    assert result["final_stage"] == "abort_done"
