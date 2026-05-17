"""GateStep — Sprint 4 Chunk B real handler port for the gate phase.

The gate Step is a ``decide`` kind. It produces a typed
:class:`Verdict` with ``recommendation`` set, which the executor
dispatches against ``kind="gate"`` edges.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from megaplan._pipeline.stages.inprocess_step import InProcessHandlerStep
from megaplan._pipeline.types import StepContext, StepResult


@dataclass(frozen=True)
class GateStep:
    name: str = "gate"
    kind: str = "decide"
    prompt_key: str | None = "gate"
    slot: str | None = "gate"
    arg_overrides: Mapping[str, Any] = field(default_factory=dict)

    def run(self, ctx: StepContext) -> StepResult:
        import megaplan

        return InProcessHandlerStep(
            name=self.name,
            kind=self.kind,
            handler=megaplan.handle_gate,
            prompt_key=self.prompt_key,
            slot=self.slot,
            arg_overrides=self.arg_overrides,
        ).run(ctx)
