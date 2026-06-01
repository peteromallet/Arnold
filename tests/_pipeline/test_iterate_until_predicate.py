"""T9b — iterate_until threads a predicate through to the executor."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from megaplan._pipeline.executor import run_pipeline
from megaplan._pipeline.pattern_stops import LoopState
from megaplan._pipeline.pattern_topology import iterate_until
from megaplan._pipeline.types import (
    Edge,
    Pipeline,
    Stage,
    StepContext,
    StepResult,
)


@dataclass
class _Counter:
    name: str = "loopstep"
    kind: str = "produce"
    prompt_key: str | None = None
    slot: str | None = None
    produces: tuple = ()
    consumes: tuple = ()
    calls: int = 0
    history: list = field(default_factory=list)

    def run(self, ctx: StepContext) -> StepResult:
        self.calls += 1
        # Mutate state to simulate convergence in last_fanout_results.
        history = list(ctx.state.get("history", []))
        history.append(self.calls)
        return StepResult(
            next="iterate",
            state_patch={
                "history": history,
                "last_fanout_results": {"score": min(1.0, self.calls * 0.5)},
            },
        )


def _build_pipeline(step, *, condition=None, max_iterations=10):
    base = Stage(
        name="loopstep",
        step=step,
        edges=(Edge(label="done", target="halt"),),
    )
    looped = iterate_until(
        base, condition=condition, max_iterations=max_iterations
    )
    return Pipeline(stages={"loopstep": looped}, entry="loopstep")


def _ctx(tmp_path: Path) -> StepContext:
    return StepContext(plan_dir=tmp_path, state={}, profile=None, mode="test")


def test_iterate_until_stores_predicate_on_stage(tmp_path: Path):
    step = _Counter()

    def cond(ls: LoopState) -> bool:
        return ls.iteration >= 3

    pipe = _build_pipeline(step, condition=cond)
    # T16: iterate_until now constructs a LoopNode under the hood; the
    # Stage's loop_condition is the node's should_halt method (which
    # composes cap + budget + predicate).  Identity of the raw cond is
    # therefore not preserved — behavior is.
    assert pipe.stages["loopstep"].loop_condition is not None
    result = run_pipeline(pipe, _ctx(tmp_path), artifact_root=tmp_path)
    assert result.get("halt_reason") == "loop_condition"
    assert step.calls == 3


def test_iterate_until_plateau_predicate_exits(tmp_path: Path):
    step = _Counter()

    def plateau(ls: LoopState) -> bool:
        # exit when last_fanout_results score reaches 1.0
        lfr = ls.last_fanout_results or {}
        return float(lfr.get("score", 0.0)) >= 1.0

    pipe = _build_pipeline(step, condition=plateau)
    result = run_pipeline(pipe, _ctx(tmp_path), artifact_root=tmp_path)
    assert result.get("halt_reason") == "loop_condition"
    # score reaches 1.0 at call 2 (0.5, 1.0)
    assert step.calls == 2


def test_iterate_until_default_uses_max_iterations(tmp_path: Path):
    step = _Counter()
    pipe = _build_pipeline(step, condition=None, max_iterations=4)
    # default condition stored is iteration >= max_iterations
    assert pipe.stages["loopstep"].loop_condition is not None
    result = run_pipeline(pipe, _ctx(tmp_path), artifact_root=tmp_path)
    assert result.get("halt_reason") == "loop_condition"
    assert step.calls == 4
