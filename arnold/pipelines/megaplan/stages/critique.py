"""CritiqueStep — Sprint 4 Chunk B real handler port for the critique phase."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from arnold.pipelines.megaplan.handlers import handle_critique
from arnold.pipelines.megaplan.stages.inprocess_step import InProcessHandlerStep
from megaplan._pipeline.types import StepContext, StepResult


@dataclass(frozen=True)
class CritiqueStep:
    name: str = "critique"
    kind: str = "judge"
    prompt_key: str | None = "critique"
    slot: str | None = "critique"
    arg_overrides: Mapping[str, Any] = field(default_factory=dict)

    def run(self, ctx: StepContext) -> StepResult:
        return InProcessHandlerStep(
            name=self.name,
            kind=self.kind,
            handler=handle_critique,
            prompt_key=self.prompt_key,
            slot=self.slot,
            arg_overrides=self.arg_overrides,
        ).run(ctx)
