"""TiebreakerStep — Sprint 4 Chunk D follow-up.

Collapses the legacy two-state tiebreaker pair (``tiebreaker_pending``
→ tiebreaker-run → ``tiebreaker_ready`` → tiebreaker-decide →
``critiqued``) into a single :class:`SubloopStep` whose child Pipeline
runs the run-and-decide pair in sequence.

The parent's PipelineVerdict.recommendation is derived from the child's final
state.json: when ``current_state`` advances back to ``critiqued`` the
tiebreaker resolved; the parent emits ``"iterate"`` so the planning
critique loop can continue with the resolved decision.
"""

from __future__ import annotations

from argparse import Namespace
from dataclasses import dataclass, field
from typing import Any, Mapping

from megaplan._pipeline.stages.inprocess_step import InProcessHandlerStep
from megaplan._pipeline.subloop import SubloopStep
from megaplan._pipeline.types import (
    Edge,
    Pipeline,
    Port,
    PortRef,
    Stage,
    StepContext,
    StepResult,
)


def _build_tiebreaker_child_pipeline() -> Pipeline:
    import megaplan

    run_step = InProcessHandlerStep(
        name="tiebreaker_run", kind="produce",
        slot="tiebreaker_researcher",
        handler=megaplan.handlers.tiebreaker.handle_tiebreaker_run,
    )
    decide_step = InProcessHandlerStep(
        name="tiebreaker_decide", kind="produce",
        slot="tiebreaker_challenger",
        handler=megaplan.handlers.tiebreaker.handle_tiebreaker_decide,
    )

    stages: dict[str, Stage] = {
        "run": Stage(name="run", step=run_step,
                     edges=(Edge(label="tiebreaker_decide", target="decide"),)),
        "decide": Stage(name="decide", step=decide_step,
                        edges=(Edge(label="halt", target="halt"),)),
    }
    return Pipeline(stages=stages, entry="run")


def _promote_from_child_state(state: dict[str, Any]) -> str:
    """Map the child pipeline's final state to a parent PipelineVerdict.

    The child writes to ``current_state``; after a successful
    tiebreaker run+decide the state transitions back to ``critiqued``
    (the tiebreaker decision flows through the standard gate loop).

    Returns a :class:`RoutingKey` bridged from the legacy
    recommendation literal via
    :func:`_bridge_recommendation_to_routing_key`.  # TODO(M2/M3)
    """
    final = state.get("current_state", "")
    if final == "critiqued":
        return "iterate"
    if final == "aborted":
        return "escalate"
    return "proceed"


@dataclass(frozen=True)
class TiebreakerStep:
    """Single-Step tiebreaker — runs both legacy phases as a child pipeline."""

    name: str = "tiebreaker"
    kind: str = "subloop"
    prompt_key: str | None = None
    slot: str | None = "tiebreaker_researcher"
    arg_overrides: Mapping[str, Any] = field(default_factory=dict)
    produces: tuple[Port, ...] = field(default_factory=tuple)
    consumes: tuple[PortRef, ...] = field(default_factory=tuple)

    def run(self, ctx: StepContext) -> StepResult:
        subloop = SubloopStep(
            name=self.name,
            child_pipeline=_build_tiebreaker_child_pipeline(),
            promote=_promote_from_child_state,
            artifact_subdir="tiebreaker",
        )
        return subloop.run(ctx)
