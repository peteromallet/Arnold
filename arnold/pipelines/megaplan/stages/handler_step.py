"""Planning-pipeline handler-Step registry.

Sprint 5 Chunk A (T3) retired the subprocess ``HandlerStep`` wrapper.
The canonical planning Steps are the named in-process classes under
``megaplan/_pipeline/stages/`` (``PrepStep`` / ``PlanStep`` /
``CritiqueStep`` / ``GateStep`` / ``FinalizeStep`` / ``ExecuteStep``).
``build_planning_steps()`` remains for tests and manual state-machine
drivers that map persisted state names to in-process handler steps.
"""

from __future__ import annotations

from typing import Any

from arnold.pipelines.megaplan.stages.inprocess_step import InProcessHandlerStep


def build_planning_steps() -> dict[str, Any]:
    """Return the canonical handler-backed Step set for the planning Pipeline.

    Keyed by legacy state name for manual state-machine drivers. All
    entries are in-process Steps; subprocess dispatch was retired in
    Sprint 5 Chunk A.
    """

    from arnold.pipelines.megaplan.handlers.tiebreaker import (
        handle_tiebreaker_run,
        handle_tiebreaker_decide,
    )
    from arnold.pipelines.megaplan.stages.prep import PrepStep
    from arnold.pipelines.megaplan.stages.plan import PlanStep
    from arnold.pipelines.megaplan.stages.critique import CritiqueStep
    from arnold.pipelines.megaplan.stages.gate import GateStep
    from arnold.pipelines.megaplan.stages.finalize import FinalizeStep
    from arnold.pipelines.megaplan.stages.execute import ExecuteStep

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
            handler=handle_tiebreaker_run,
        ),
        "tiebreaker_ready": InProcessHandlerStep(
            name="tiebreaker_decide",
            kind="subloop",
            slot="tiebreaker_challenger",
            handler=handle_tiebreaker_decide,
        ),
    }
