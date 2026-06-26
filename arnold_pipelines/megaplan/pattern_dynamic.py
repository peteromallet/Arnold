"""Minimal canonical dynamic fan-out bridge for migrated pipelines.

This module replaces the legacy ``arnold_pipelines.megaplan._pipeline.patterns``
surface for the small set of canonical pipelines that still rely on the
``dynamic_fanout`` constructor. It delegates the core mechanics to the neutral
Arnold implementation in :mod:`arnold.pipeline.pattern_dynamic` and exposes a
runnable step object compatible with the legacy graph shell.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from arnold.pipeline.pattern_dynamic import run_fanout


@dataclass(frozen=True)
class _DynamicFanoutStep:
    """Step-like object that runs a generator → specs → fan-out → join chain."""

    name: str = "dynamic_fanout"
    kind: str = "fanout"
    prompt_key: str | None = None
    slot: str | None = None
    generator: Any = None
    base_prompt: Any = None
    join_fn: Callable[[list[Any], Any], Any] | None = None
    produces: tuple[Any, ...] = field(default_factory=tuple)
    consumes: tuple[Any, ...] = field(default_factory=tuple)

    def run(self, ctx: Any) -> Any:
        if self.generator is None:
            raise ValueError(f"dynamic_fanout {self.name!r}: generator is None")
        if self.base_prompt is None:
            raise ValueError(f"dynamic_fanout {self.name!r}: base_prompt is None")
        if self.join_fn is None:
            raise ValueError(f"dynamic_fanout {self.name!r}: join is None")

        return run_fanout(
            generator=self.generator,
            base_step=self.base_prompt,
            join_fn=self.join_fn,
            ctx=ctx,
            typed_ports=False,
        )


def dynamic_fanout(
    generator: Any,
    base_prompt: Any,
    join: Callable[[list[Any], Any], Any],
    *,
    name: str,
) -> _DynamicFanoutStep:
    """Run *generator* once, consume specs, and fan out *base_prompt* per spec."""

    return _DynamicFanoutStep(
        name=name,
        generator=generator,
        base_prompt=base_prompt,
        join_fn=join,
    )


__all__ = ["dynamic_fanout"]
