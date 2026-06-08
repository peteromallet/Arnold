"""PlanStep — Sprint 4 Chunk B real handler port for the plan phase."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from arnold.pipelines.megaplan.handlers import handle_plan
from arnold.pipelines.megaplan.stages.inprocess_step import InProcessHandlerStep
from arnold.pipelines.megaplan._pipeline.types import StepContext, StepMixinProperty, StepResult


@dataclass(frozen=True)
class PlanStep(StepMixinProperty):
    name: str = "plan"
    kind: str = "produce"
    prompt_key: str | None = "plan"
    slot: str | None = "plan"
    arg_overrides: Mapping[str, Any] = field(default_factory=dict)

    def run(self, ctx: StepContext) -> StepResult:
        return InProcessHandlerStep(
            name=self.name,
            kind=self.kind,
            handler=handle_plan,
            prompt_key=self.prompt_key,
            slot=self.slot,
            arg_overrides=self.arg_overrides,
        ).run(ctx)
