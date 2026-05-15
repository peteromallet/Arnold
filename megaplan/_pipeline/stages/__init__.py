"""Real handler-backed Steps that drive the live planning pipeline.

Sprint 3 deliverable. Each Step here delegates to ``megaplan <phase>``
via subprocess (the same dispatch ``megaplan/auto.py`` uses today). The
Step pulls its own ``state.json`` after the subprocess completes,
extracts the resulting artifact paths, and returns a ``StepResult``
whose ``next`` label matches the matching edge in the compiled
planning :class:`Pipeline`.

The key contract: these Steps DO NOT re-implement handler logic. They
shell out to the existing handler subprocess so the byte-for-byte
behaviour is preserved while the planning Pipeline becomes the
orchestration layer.
"""

from megaplan._pipeline.stages.handler_step import (
    HandlerStep,
    build_planning_steps,
)


__all__ = ["HandlerStep", "build_planning_steps"]
