"""Subloop primitive.

A :class:`SubloopStep` is the executor-level primitive: it carries a
nested :class:`Pipeline`, runs it as a child via
:func:`run_pipeline`, and then promotes the child's final state into
a :class:`PipelineVerdict` on the parent. The parent's PipelineVerdict.recommendation
is set from the child pipeline's terminal stage by a configurable
:attr:`promote` callable.

Relationships:

* :class:`SubloopStep` (this module) is the **primitive**.
* :class:`megaplan._pipeline.stages.tiebreaker.TiebreakerStep` is the
  concrete planning use — it collapses the legacy two-state
  tiebreaker pair into a single Step whose child Pipeline runs
  researcher → challenger → synthesis.
* :func:`megaplan._pipeline.patterns.subpipeline_call` is the
  **recommended construction path** for future user pipelines: it is a
  thin builder-friendly wrapper around :class:`SubloopStep` and is the
  surface :class:`PipelineBuilder.subpipeline` plumbs onto.

State-flow contract: the child runs with a *copy* of ``ctx.state``
(``state=dict(ctx.state)``). Child state mutations therefore do not
propagate back to the parent state map directly — only the
``promote`` callable's :class:`RoutingKey` flows up via
:class:`PipelineVerdict`, plus the two ``subloop:<name>:recommendation`` /
``subloop:<name>:state`` keys emitted as ``state_patch`` on the
parent. Downstream handlers that need to observe child results
should read them from on-disk artifacts (the child writes under
``ctx.plan_dir / artifact_subdir``), not from in-process state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from megaplan._pipeline._forward_m2_m3 import RoutingKey  # TODO(M2/M3)
from megaplan._pipeline.types import (
    Pipeline,
    StepContext,
    StepResult,
    PipelineVerdict,
)

from megaplan._pipeline.pattern_types import PromoteFn


_DEFAULT_PROMOTE: PromoteFn = lambda state: RoutingKey(name="proceed", kind="advance")


@dataclass(frozen=True)
class SubloopStep:
    """A Step that runs a nested Pipeline and promotes its final state.

    ``child_pipeline``: the inner pipeline to run.
    ``promote``: callable that maps the child's final state dict to a
    :class:`RoutingKey` for the parent's PipelineVerdict.
    ``artifact_subdir``: subdir under ``ctx.plan_dir`` where the child
    pipeline's state.json + per-stage artifacts land. Defaults to the
    Step's name.
    """

    name: str = "subloop"
    kind: str = "subloop"
    prompt_key: str | None = None
    slot: str | None = None
    child_pipeline: Pipeline | None = None
    promote: PromoteFn = field(default=_DEFAULT_PROMOTE)
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
        _name = getattr(recommendation, 'name', recommendation)
        verdict = PipelineVerdict(
            score=float(child_state.get("score", 1.0)),
            recommendation=_name,
            payload={
                "subloop_final_stage": result.get("final_stage"),
                "subloop_state": child_state,
            },
        )

        return StepResult(
            outputs={},
            verdict=verdict,
            next=_name,  # textual fallback if no kind="gate" edge matches
            state_patch={
                f"subloop:{self.name}:recommendation": _name,
                f"subloop:{self.name}:state": child_state,
            },
        )
