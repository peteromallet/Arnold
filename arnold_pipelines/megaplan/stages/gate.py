"""GateStep — Sprint 4 Chunk B real handler port for the gate phase.

The gate Step is a ``decide`` kind. It produces a typed
:class:`PipelineVerdict` with ``recommendation`` set, which the executor
dispatches against ``kind="gate"`` edges.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from arnold_pipelines.megaplan.handlers import handle_gate
from arnold_pipelines.megaplan.stages.inprocess_step import InProcessHandlerStep
from arnold_pipelines.megaplan._pipeline.types import StepContext, StepMixinProperty, StepResult


@dataclass(frozen=True)
class GateStep(StepMixinProperty):
    name: str = "gate"
    kind: str = "decide"
    prompt_key: str | None = "gate"
    slot: str | None = "gate"
    arg_overrides: Mapping[str, Any] = field(default_factory=dict)

    def run(self, ctx: StepContext) -> StepResult:
        return InProcessHandlerStep(
            name=self.name,
            kind=self.kind,
            handler=handle_gate,
            prompt_key=self.prompt_key,
            slot=self.slot,
            arg_overrides=self.arg_overrides,
        ).run(ctx)
