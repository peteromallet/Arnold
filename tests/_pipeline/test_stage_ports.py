"""Unit tests for Stage / ParallelStage typed-port fields (M2 / T1b)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from arnold.pipelines.megaplan._pipeline.types import (
    ParallelStage,
    Port,
    PortRef,
    Stage,
    StepContext,
    StepResult,
)


@dataclass
class _FakeStep:
    name: str = "fake"
    kind: str = "produce"
    prompt_key: str | None = None
    slot: str | None = None
    produces: tuple[Port, ...] = field(default_factory=tuple)
    consumes: tuple[PortRef, ...] = field(default_factory=tuple)

    def run(self, ctx: StepContext) -> StepResult:  # pragma: no cover
        return StepResult()


def _read_ports(obj) -> tuple[tuple[Port, ...], tuple[PortRef, ...]]:
    """Mimic the binder fallback: stage-level override else step-level."""
    if isinstance(obj, ParallelStage):
        step_produces: tuple[Port, ...] = ()
        step_consumes: tuple[PortRef, ...] = ()
    else:
        step_produces = obj.step.produces
        step_consumes = obj.step.consumes
    produces = obj.produces if obj.produces else step_produces
    consumes = obj.consumes if obj.consumes else step_consumes
    return produces, consumes


class TestStageProducesOverride:
    def test_explicit_stage_produces_overrides_step(self) -> None:
        step = _FakeStep(
            produces=(Port("from_step", "text/markdown"),),
        )
        stage_port = Port("from_stage", "image/png")
        stage = Stage(
            name="s",
            step=step,
            produces=(stage_port,),
        )
        produces, _ = _read_ports(stage)
        assert produces == (stage_port,)


class TestParallelStageProduces:
    def test_parallel_stage_carrying_produces_is_read_by_binder(self) -> None:
        step = _FakeStep()
        port = Port("reduce_result", "application/x-fanout-results+json")
        pstage = ParallelStage(
            name="p",
            steps=(step,),
            join=lambda rs, ctx: StepResult(),
            produces=(port,),
        )
        produces, _ = _read_ports(pstage)
        assert produces == (port,)


class TestStageFallsBackToStep:
    def test_empty_stage_falls_back_to_step_level_tuples(self) -> None:
        step_port = Port("step_port", "text/markdown")
        step_ref = PortRef("upstream", "text/markdown")
        step = _FakeStep(produces=(step_port,), consumes=(step_ref,))
        stage = Stage(name="s", step=step)
        produces, consumes = _read_ports(stage)
        assert produces == (step_port,)
        assert consumes == (step_ref,)

    def test_stage_produces_default_is_empty_tuple(self) -> None:
        step = _FakeStep()
        stage = Stage(name="s", step=step)
        assert stage.produces == ()
        assert stage.consumes == ()
