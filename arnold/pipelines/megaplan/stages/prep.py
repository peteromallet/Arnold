"""PrepStep — Sprint 4 Chunk B real handler port.

A typed Step that performs the prep phase via the existing
``handle_prep`` entrypoint. Unlike :class:`InProcessHandlerStep`,
``PrepStep`` exposes a single named class per phase so downstream
callers can subclass / override / register it through a clean public
surface.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from arnold.pipelines.megaplan.handlers import handle_prep
from arnold.pipelines.megaplan.stages.inprocess_step import InProcessHandlerStep
from arnold.pipelines.megaplan._pipeline.types import StepContext, StepMixinProperty, StepResult


@dataclass(frozen=True)
class PrepStep(StepMixinProperty):
    """The prep phase as a real, typed Step."""

    name: str = "prep"
    kind: str = "produce"
    prompt_key: str | None = "prep"
    slot: str | None = "prep"
    arg_overrides: Mapping[str, Any] = field(default_factory=dict)

    def run(self, ctx: StepContext) -> StepResult:
        return InProcessHandlerStep(
            name=self.name,
            kind=self.kind,
            handler=handle_prep,
            prompt_key=self.prompt_key,
            slot=self.slot,
            arg_overrides=self.arg_overrides,
        ).run(ctx)
