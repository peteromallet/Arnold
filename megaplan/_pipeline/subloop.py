"""Subloop primitive — Sprint 4 Chunk D.

A :class:`SubloopStep` carries a nested :class:`Pipeline` that the
executor runs as a child, then promotes the child's final state into
a :class:`Verdict` on the parent. The parent's Verdict.recommendation
is set from the child pipeline's terminal stage by a configurable
:attr:`promote` callable.

This is the elegance fix for tiebreaker: today's two states
(``tiebreaker_pending`` / ``tiebreaker_ready``) collapse into a
single Step whose nested Pipeline runs researcher → challenger →
synthesis, with the synthesis output becoming the parent's gate-style
verdict.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping

from megaplan._pipeline.types import (
    GateRecommendation,
    Pipeline,
    StepContext,
    StepResult,
    Verdict,
)


_DEFAULT_PROMOTE: Callable[[dict[str, Any]], GateRecommendation] = lambda state: "proceed"


@dataclass(frozen=True)
class SubloopStep:
    """A Step that runs a nested Pipeline and promotes its final state.

    ``child_pipeline``: the inner pipeline to run.
    ``promote``: callable that maps the child's final state dict to a
    :class:`GateRecommendation` for the parent's Verdict.
    ``artifact_subdir``: subdir under ``ctx.plan_dir`` where the child
    pipeline's state.json + per-stage artifacts land. Defaults to the
    Step's name.
    """

    name: str = "subloop"
    kind: str = "subloop"
    prompt_key: str | None = None
    slot: str | None = None
    child_pipeline: Pipeline | None = None
    promote: Callable[[dict[str, Any]], GateRecommendation] = field(default=_DEFAULT_PROMOTE)
    artifact_subdir: str | None = None

    def run(self, ctx: StepContext) -> StepResult:
        from megaplan._pipeline.executor import run_pipeline

        if self.child_pipeline is None:
            raise ValueError(f"SubloopStep {self.name!r} has no child_pipeline")

        subdir = self.artifact_subdir or self.name
        child_root = Path(ctx.plan_dir) / subdir
        child_root.mkdir(parents=True, exist_ok=True)

        import dataclasses

        child_ctx = dataclasses.replace(ctx, plan_dir=child_root, state=dict(ctx.state) if isinstance(ctx.state, Mapping) else {})
        result = run_pipeline(self.child_pipeline, child_ctx, artifact_root=child_root)
        child_state: dict[str, Any] = result.get("state", {})

        recommendation = self.promote(child_state)
        verdict = Verdict(
            score=float(child_state.get("score", 1.0)),
            recommendation=recommendation,
            payload={
                "subloop_final_stage": result.get("final_stage"),
                "subloop_state": child_state,
            },
        )

        return StepResult(
            outputs={},
            verdict=verdict,
            next=recommendation,  # textual fallback if no kind="gate" edge matches
            state_patch={
                f"subloop:{self.name}:recommendation": recommendation,
                f"subloop:{self.name}:state": child_state,
            },
        )
