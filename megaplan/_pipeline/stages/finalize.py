"""FinalizeStep — Sprint 4 Chunk B real handler port for the finalize phase."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from megaplan._pipeline.stages.inprocess_step import InProcessHandlerStep
from megaplan._pipeline.types import StepContext, StepResult


@dataclass(frozen=True)
class FinalizeStep:
    name: str = "finalize"
    kind: str = "produce"
    prompt_key: str | None = "finalize"
    slot: str | None = "finalize"
    arg_overrides: Mapping[str, Any] = field(default_factory=dict)
    produces: tuple = field(default_factory=tuple)
    consumes: tuple = field(default_factory=tuple)

    def run(self, ctx: StepContext) -> StepResult:
        import megaplan

        return InProcessHandlerStep(
            name=self.name,
            kind=self.kind,
            handler=megaplan.handle_finalize,
            prompt_key=self.prompt_key,
            slot=self.slot,
            arg_overrides=self.arg_overrides,
        ).run(ctx)
