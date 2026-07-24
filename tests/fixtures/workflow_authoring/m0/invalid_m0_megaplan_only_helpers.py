from __future__ import annotations

from arnold.pipeline import step, workflow


# REJECTED — Megaplan-only helper hiding topology
# Magic-string handler return values consumed by a generic router
# are rejected under V2.

@step(id="review_handler_step", inputs={"state"}, outputs={"outcome"})
def review_handler_step(state: dict) -> str:
    ...


@workflow(id="megaplan_helper_workflow", inputs={"state"}, outputs={"outcome"})
def megaplan_helper_workflow(state: dict) -> str:
    # REJECTED — Megaplan-only helper hiding topology
    async def review_handler(state):
        if state["score"] < 0.5:
            return "REVISE"  # magic string consumed by hidden router
        return "DONE"

    outcome = review_handler_step(state)
    return outcome
