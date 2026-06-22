"""Thin re-export shell for the planning pipeline stage steps.

Consumers that need a stable import path under
``megaplan.pipelines.planning.steps`` can import from here;
the canonical implementations live in ``arnold_pipelines.megaplan.runtime.inprocess_step``
and this module's handler-backed ``TiebreakerStep``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from arnold.pipeline.types import PipelineVerdict
from arnold_pipelines.megaplan.handlers.tiebreaker import (
    handle_tiebreaker_decide,
    handle_tiebreaker_run,
)
from arnold_pipelines.megaplan.runtime.inprocess_step import InProcessHandlerStep
from arnold_pipelines.megaplan.step_types import StepContext, StepMixinProperty, StepResult


def _promote_from_child_state(state: Mapping[str, Any]) -> str:
    final = state.get("current_state", "")
    if final == "critiqued":
        return "iterate"
    if final == "aborted":
        return "escalate"
    return "proceed"


@dataclass(frozen=True)
class TiebreakerStep(StepMixinProperty):
    """Single-Step tiebreaker backed by the existing run/decide handlers."""

    name: str = "tiebreaker"
    kind: str = "subloop"
    prompt_key: str | None = None
    slot: str | None = "tiebreaker_researcher"
    arg_overrides: Mapping[str, Any] = field(default_factory=dict)

    def run(self, ctx: StepContext) -> StepResult:
        run_step = InProcessHandlerStep(
            name="tiebreaker_run",
            kind="produce",
            slot="tiebreaker_researcher",
            handler=handle_tiebreaker_run,
            arg_overrides=self.arg_overrides,
        )
        decide_step = InProcessHandlerStep(
            name="tiebreaker_decide",
            kind="produce",
            slot="tiebreaker_challenger",
            handler=handle_tiebreaker_decide,
            arg_overrides=self.arg_overrides,
        )
        run_step.run(ctx)
        decided = decide_step.run(ctx)
        state = ctx.state if isinstance(ctx.state, Mapping) else {}
        recommendation = _promote_from_child_state(state)
        return StepResult(
            outputs=decided.outputs,
            verdict=PipelineVerdict(score=0.0, recommendation=recommendation),
            next=recommendation,
            state_patch=decided.state_patch,
            contract_result=decided.contract_result,
            envelope=decided.envelope,
        )

# ── Stage wrapper classes ──────────────────────────────────────────────
# Retired: the thin adapter classes (PrepStep, PlanStep, CritiqueStep,
# GateStep, ReviseStep, FinalizeStep, ExecuteStep, ReviewStep) that
# delegated to InProcessHandlerStep were historical authoring-only and
# are not used by any production code. Use InProcessHandlerStep directly
# or the canonical explicit-node DSL in ``megaplan.pipeline`` instead.
#
# The builder functions that construct InProcessHandlerStep instances
# from handler refs remain available via:
#   from arnold_pipelines.megaplan.runtime.inprocess_step import (
#       build_inprocess_planning_steps,
#       build_revise_step,
#       build_review_step,
#   )

__all__ = [
    "InProcessHandlerStep",
    "TiebreakerStep",
]
