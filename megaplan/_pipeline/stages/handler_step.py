"""Planning-pipeline handler-Step registry.

Sprint 5 Chunk A (T3) retired the subprocess ``HandlerStep`` wrapper.
The canonical planning Steps are the named in-process classes under
``megaplan/_pipeline/stages/`` (``PrepStep`` / ``PlanStep`` /
``CritiqueStep`` / ``GateStep`` / ``FinalizeStep`` / ``ExecuteStep``)
plus :class:`InProcessHandlerStep` wrappers for the tiebreaker pair.
``build_planning_steps()`` returns the keyed registry consumed by
``megaplan/_pipeline/planning._step_for`` for the tiebreaker lookup
(and historically by overlays — now identity transforms post-Chunk-A).
"""

from __future__ import annotations

from typing import Any, Iterable

from megaplan._pipeline.stages.inprocess_step import InProcessHandlerStep


def build_planning_steps() -> dict[str, Any]:
    """Return the canonical handler-backed Step set for the planning Pipeline.

    Keyed by legacy state name so ``planning._step_for`` (the only
    remaining consumer in the canonical phase-name graph, for the
    tiebreaker stage) can resolve ``"tiebreaker_pending"`` cleanly.
    All entries are in-process Steps; subprocess dispatch was retired
    in Sprint 5 Chunk A.
    """

    import megaplan
    from megaplan._pipeline.stages.prep import PrepStep
    from megaplan._pipeline.stages.plan import PlanStep
    from megaplan._pipeline.stages.critique import CritiqueStep
    from megaplan._pipeline.stages.gate import GateStep
    from megaplan._pipeline.stages.finalize import FinalizeStep
    from megaplan._pipeline.stages.execute import ExecuteStep

    return {
        "prepped": PrepStep(),
        "planned": PlanStep(),
        "critiqued": CritiqueStep(),
        "gated": GateStep(),
        "finalized": FinalizeStep(),
        "executed": ExecuteStep(),
        "tiebreaker_pending": InProcessHandlerStep(
            name="tiebreaker_run",
            kind="subloop",
            slot="tiebreaker_researcher",
            handler=megaplan.handlers.tiebreaker.handle_tiebreaker_run,
        ),
        "tiebreaker_ready": InProcessHandlerStep(
            name="tiebreaker_decide",
            kind="subloop",
            slot="tiebreaker_challenger",
            handler=megaplan.handlers.tiebreaker.handle_tiebreaker_decide,
        ),
    }


def attach_handler_steps(stages: Iterable[Any]) -> None:
    """No-op hook reserved for the Sprint-3 auto.py integration."""
    return None
