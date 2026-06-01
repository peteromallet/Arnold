"""T5: Verify that envelope.join() is called at every main-loop merge in
run_pipeline so the sink envelope's taint equals the union of source taints.

Three synthetic steps, each emitting a distinct taint value.  After the
pipeline completes the returned envelope must carry all three taints
joined via the semilattice rules.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from megaplan._pipeline.envelope import EMPTY_ENVELOPE, RunEnvelope, make_envelope
from megaplan._pipeline.executor import run_pipeline
from megaplan._pipeline.types import (
    Edge,
    Pipeline,
    Stage,
    StepContext,
    StepResult,
)


# ---------------------------------------------------------------------------
# Minimal Step helpers
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class _TaintStep:
    """A step that returns a StepResult with a specific taint and next label."""

    name: str
    kind: str = "produce"
    prompt_key: str | None = None
    slot: str | None = None
    produces: tuple = ()
    consumes: tuple = ()

    taint: str = "clean"
    cost: float = 0.0
    next_label: str = "ok"

    def run(self, ctx: StepContext) -> StepResult:
        env = make_envelope(taint=self.taint, cost=self.cost)
        return StepResult(next=self.next_label, envelope=env)


def _make_linear_pipeline(*steps: _TaintStep) -> Pipeline:
    """Build a linear pipeline: step[0] → step[1] → … → halt."""
    stages: dict[str, Stage | object] = {}
    for i, step in enumerate(steps):
        is_last = i == len(steps) - 1
        if is_last:
            edges = [Edge(kind="normal", label="ok", target="halt")]
        else:
            edges = [Edge(kind="normal", label="ok", target=steps[i + 1].name)]
        stages[step.name] = Stage(name=step.name, step=step, edges=edges)

    return Pipeline(
        entry=steps[0].name,
        stages=stages,  # type: ignore[arg-type]
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_sink_taint_is_union_of_source_taints(tmp_path: Path) -> None:
    """Sink envelope taint == join of all three steps' taints."""
    step_a = _TaintStep(name="step_a", taint="clean", next_label="ok")
    step_b = _TaintStep(name="step_b", taint="tainted", next_label="ok")
    step_c = _TaintStep(name="step_c", taint="clean", next_label="ok")

    pipeline = _make_linear_pipeline(step_a, step_b, step_c)
    ctx = StepContext(plan_dir=tmp_path, state={}, profile=None, mode="test")

    result = run_pipeline(pipeline, ctx, artifact_root=tmp_path / "artifacts")

    env: RunEnvelope = result["envelope"]
    # "tainted" dominates "clean" in the semilattice
    assert env.taint == "tainted", f"expected 'tainted', got {env.taint!r}"


def test_sink_taint_all_clean(tmp_path: Path) -> None:
    """All-clean steps produce a clean sink envelope."""
    steps = [_TaintStep(name=f"s{i}", taint="clean") for i in range(3)]
    pipeline = _make_linear_pipeline(*steps)
    ctx = StepContext(plan_dir=tmp_path, state={}, profile=None, mode="test")

    result = run_pipeline(pipeline, ctx, artifact_root=tmp_path / "artifacts")
    assert result["envelope"].taint == "clean"


def test_cost_accumulates_across_three_steps(tmp_path: Path) -> None:
    """Cost in the sink envelope equals the sum across all three steps."""
    steps = [
        _TaintStep(name="s0", cost=1.0),
        _TaintStep(name="s1", cost=2.5),
        _TaintStep(name="s2", cost=0.5),
    ]
    pipeline = _make_linear_pipeline(*steps)
    ctx = StepContext(plan_dir=tmp_path, state={}, profile=None, mode="test")

    result = run_pipeline(pipeline, ctx, artifact_root=tmp_path / "artifacts")
    assert abs(result["envelope"].cost - 4.0) < 1e-9


def test_initial_ctx_envelope_is_seeded_into_accumulator(tmp_path: Path) -> None:
    """If ctx already carries an envelope, the accumulator starts from it."""
    seed = make_envelope(taint="tainted", cost=10.0)
    step = _TaintStep(name="only_step", taint="clean", cost=1.0)
    pipeline = _make_linear_pipeline(step)
    ctx = StepContext(
        plan_dir=tmp_path, state={}, profile=None, mode="test", envelope=seed
    )

    result = run_pipeline(pipeline, ctx, artifact_root=tmp_path / "artifacts")
    env = result["envelope"]
    # seed taint dominates
    assert env.taint == "tainted"
    # seed cost + step cost
    assert abs(env.cost - 11.0) < 1e-9


def test_envelope_threaded_into_each_step_ctx(tmp_path: Path) -> None:
    """Each step receives the envelope accumulated so far via ctx.envelope."""
    received: list[RunEnvelope] = []

    @dataclasses.dataclass
    class _CapturingStep:
        name: str
        kind: str = "produce"
        prompt_key: str | None = None
        slot: str | None = None
        produces: tuple = ()
        consumes: tuple = ()
        taint: str = "clean"

        def run(self, ctx: StepContext) -> StepResult:
            received.append(ctx.envelope)
            return StepResult(next="ok", envelope=make_envelope(taint=self.taint, cost=1.0))

    step_a = _CapturingStep(name="a", taint="tainted")
    step_b = _CapturingStep(name="b", taint="clean")
    step_c = _CapturingStep(name="c", taint="clean")

    pipeline = _make_linear_pipeline(step_a, step_b, step_c)  # type: ignore[arg-type]
    ctx = StepContext(plan_dir=tmp_path, state={}, profile=None, mode="test")
    run_pipeline(pipeline, ctx, artifact_root=tmp_path / "artifacts")

    # step_a sees EMPTY_ENVELOPE (nothing accumulated yet)
    assert received[0] == EMPTY_ENVELOPE
    # step_b sees the join of seed + step_a result (tainted, cost=1.0)
    assert received[1].taint == "tainted"
    assert abs(received[1].cost - 1.0) < 1e-9
    # step_c sees join of all prior (still tainted, cost=2.0)
    assert received[2].taint == "tainted"
    assert abs(received[2].cost - 2.0) < 1e-9
