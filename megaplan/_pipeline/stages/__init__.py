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

from megaplan._pipeline.stages.handler_step import build_planning_steps
from megaplan._pipeline.stages.prep import PrepStep
from megaplan._pipeline.stages.plan import PlanStep
from megaplan._pipeline.stages.critique import CritiqueStep
from megaplan._pipeline.stages.gate import GateStep
from megaplan._pipeline.stages.revise import ReviseStep
from megaplan._pipeline.stages.finalize import FinalizeStep
from megaplan._pipeline.stages.execute import ExecuteStep
from megaplan._pipeline.stages.review import ReviewStep


__all__ = [
    "build_planning_steps",
    "PrepStep",
    "PlanStep",
    "CritiqueStep",
    "GateStep",
    "ReviseStep",
    "FinalizeStep",
    "ExecuteStep",
    "ReviewStep",
]
