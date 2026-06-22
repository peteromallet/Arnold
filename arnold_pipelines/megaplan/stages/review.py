"""ReviewStep — Sprint 4 Chunk B real handler port for the review phase."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from arnold_pipelines.megaplan.handlers import handle_review
from arnold_pipelines.megaplan.stages.inprocess_step import InProcessHandlerStep
from arnold_pipelines.megaplan._pipeline.types import StepContext, StepMixinProperty, StepResult


@dataclass(frozen=True)
class ReviewStep(StepMixinProperty):
    name: str = "review"
    kind: str = "judge"
    prompt_key: str | None = "review"
    slot: str | None = "review"
    arg_overrides: Mapping[str, Any] = field(default_factory=dict)

    def run(self, ctx: StepContext) -> StepResult:
        return InProcessHandlerStep(
            name=self.name,
            kind=self.kind,
            handler=handle_review,
            prompt_key=self.prompt_key,
            slot=self.slot,
            arg_overrides=self.arg_overrides,
        ).run(ctx)
