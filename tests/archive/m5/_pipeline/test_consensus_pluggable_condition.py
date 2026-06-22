"""T9c — _ConsensusStep accepts pluggable condition."""
from __future__ import annotations

from pathlib import Path

from arnold.pipelines.megaplan._pipeline.pattern_dynamic import _ConsensusStep
from arnold.pipelines.megaplan._pipeline.types import (
    PipelineVerdict,
    StepContext,
    StepResult,
)


class _Panel:
    name = "panel"
    kind = "produce"
    prompt_key = None
    slot = None
    produces = ()
    consumes = ()

    def __init__(self):
        self.calls = 0

    def run(self, ctx: StepContext) -> StepResult:
        self.calls += 1
        return StepResult(
            verdict=PipelineVerdict(
                score=1.0,
                payload={"per_reviewer_recommendations": ["a", "b", "c"]},  # ratio < 0.8
            ),
            next="halt",
        )


def test_user_condition_terminates_after_two(tmp_path: Path):
    panel = _Panel()
    step = _ConsensusStep(
        name="cs",
        panel=panel,
        min_agreement=0.99,  # never satisfied
        max_iters=10,
        condition=lambda ls: ls.iteration >= 2,
    )
    ctx = StepContext(plan_dir=tmp_path, state={}, profile=None, mode="t")
    out = step.run(ctx)
    assert panel.calls == 2
    assert out.state_patch["consensus:cs:iterations"] == 2


def test_default_uses_agreement_ratio(tmp_path: Path):
    class _AgreePanel:
        name = "p"; kind = "produce"; prompt_key = None; slot = None
        produces = (); consumes = ()
        def run(self, ctx):
            return StepResult(
                verdict=PipelineVerdict(
                    score=1.0,
                    payload={"per_reviewer_recommendations": ["a", "a", "a"]},
                ),
                next="halt",
            )

    step = _ConsensusStep(name="cs", panel=_AgreePanel(), min_agreement=0.8, max_iters=5)
    ctx = StepContext(plan_dir=tmp_path, state={}, profile=None, mode="t")
    out = step.run(ctx)
    assert out.state_patch["consensus:cs:iterations"] == 1
