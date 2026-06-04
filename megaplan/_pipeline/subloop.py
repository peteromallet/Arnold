"""Subloop primitive.

A :class:`SubloopStep` is the executor-level primitive: it carries a
nested :class:`Pipeline`, runs it as a child via the Megaplan executor
(:func:`megaplan._pipeline.executor.run_pipeline`), normalises the result
into a :class:`arnold.pipeline.subpipeline.ChildRunResult`, and then
promotes the child's final state into a :class:`PipelineVerdict` on the
parent.

Two promotion modes are supported:

* **Legacy** :attr:`promote` — ``Callable[[dict], RoutingKey|str]`` —
  maps the child's final state dict to a routing key for the parent's
  PipelineVerdict.  This preserves full backward compatibility with
  tiebreaker, pattern_topology, and builder consumers.

* **Opt-in** :meth:`promote_delta` — ``Callable[[ChildRunResult, StepContext], StateDelta]`` —
  returns a neutral :class:`~arnold.pipeline.state.StateDelta` that the
  caller applies to parent state.  When set, the ``state_patch`` keys
  ``subloop:<name>:recommendation`` and ``subloop:<name>:state`` are
  still emitted for backward compatibility.

Relationships:

* :class:`SubloopStep` (this module) is the **primitive**.
* :class:`arnold.pipelines.megaplan.stages.tiebreaker.TiebreakerStep` is the
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
from typing import Any, Callable, Mapping

from arnold.pipeline.state import StateDelta
from arnold.pipeline.subpipeline import ChildRunResult

from megaplan._pipeline._forward_m2_m3 import RoutingKey  # TODO(M2/M3)
from megaplan._pipeline.types import (
    Pipeline,
    Port,
    PortRef,
    StepContext,
    StepResult,
    PipelineVerdict,
)

from megaplan._pipeline.pattern_types import PromoteFn

# Opt-in promote_delta signature
PromoteDeltaFn = Callable[[ChildRunResult, StepContext], StateDelta]

_DEFAULT_PROMOTE: PromoteFn = lambda state: RoutingKey(name="proceed", kind="advance")


@dataclass(frozen=True)
class SubloopStep:
    """A Step that runs a nested Pipeline and promotes its final state.

    ``child_pipeline``: the inner pipeline to run.
    ``promote``: callable that maps the child's final state dict to a
    :class:`RoutingKey` for the parent's PipelineVerdict.
    ``promote_delta``: optional callable that maps the
    :class:`~arnold.pipeline.subpipeline.ChildRunResult` and parent context
    to a neutral :class:`~arnold.pipeline.state.StateDelta`.  When set,
    the delta is computed *in addition to* the legacy promote path; both
    results are merged into the final ``StepResult.state_patch``.
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
    promote_delta: PromoteDeltaFn | None = None
    artifact_subdir: str | None = None
    produces: tuple[Port, ...] = field(default_factory=tuple)
    consumes: tuple[PortRef, ...] = field(default_factory=tuple)

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

        # Normalise the Megaplan executor result into Arnold ChildRunResult
        child_run_result = ChildRunResult(
            final_state=child_state,
            final_stage=result.get("final_stage"),
            artifacts=result.get("artifacts", {}),
            status=result.get("status", "completed"),
            status_detail=result.get("status_detail"),
        )

        # ── Legacy promote path ──────────────────────────────────────
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

        # ── Build state_patch ────────────────────────────────────────
        state_patch: dict[str, Any] = {
            f"subloop:{self.name}:recommendation": _name,
            f"subloop:{self.name}:state": child_state,
        }

        # ── Opt-in promote_delta path ────────────────────────────────
        if self.promote_delta is not None:
            delta = self.promote_delta(child_run_result, ctx)
            if isinstance(delta, StateDelta):
                for patch in delta.patches:
                    if isinstance(patch, dict):
                        state_patch.update(patch)

        return StepResult(
            outputs={},
            verdict=verdict,
            next=_name,  # textual fallback if no kind="gate" edge matches
            state_patch=state_patch,
        )
