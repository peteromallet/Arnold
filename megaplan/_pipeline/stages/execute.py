"""ExecuteStep — Sprint 4 Chunk B real handler port for the execute phase.

By default this Step passes ``user_approved=True`` so the executor
can dispatch without the legacy CLI confirmation prompt; callers
that want explicit user approval pass ``arg_overrides={"user_approved": False}``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from megaplan._pipeline.stages.inprocess_step import InProcessHandlerStep
from megaplan._pipeline.types import StepContext, StepResult


_DEFAULTS: Mapping[str, Any] = {
    "user_approved": True,
    "confirm_destructive": True,
}


@dataclass(frozen=True)
class ExecuteStep:
    name: str = "execute"
    kind: str = "produce"
    prompt_key: str | None = "execute"
    slot: str | None = "execute"
    arg_overrides: Mapping[str, Any] = field(default_factory=lambda: dict(_DEFAULTS))
    produces: tuple = field(default_factory=tuple)
    consumes: tuple = field(default_factory=tuple)

    def run(self, ctx: StepContext) -> StepResult:
        import megaplan

        merged = {**_DEFAULTS, **self.arg_overrides}
        return InProcessHandlerStep(
            name=self.name,
            kind=self.kind,
            handler=megaplan.handle_execute,
            prompt_key=self.prompt_key,
            slot=self.slot,
            arg_overrides=merged,
        ).run(ctx)
