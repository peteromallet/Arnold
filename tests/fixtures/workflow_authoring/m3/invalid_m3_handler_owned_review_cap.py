from __future__ import annotations

from arnold.pipeline import parallel_map
from arnold.workflow.authoring import workflow
from arnold_pipelines.megaplan.outcomes import ReviewOutcome
from arnold_pipelines.megaplan.workflows.components import (
    AUTHORING_EXECUTE,
    AUTHORING_FINALIZE,
    AUTHORING_HALT,
    AUTHORING_REVIEW,
    DEFAULT_POLICY,
    EXECUTE_BATCH_WORKFLOW,
    REVIEW_PANEL_WORKFLOW,
)


@workflow(id="invalid-m3-handler-owned-review-cap", version="1", policy=DEFAULT_POLICY)
def flow(gate_payload: str) -> None:
    finalize_payload = AUTHORING_FINALIZE(id="finalize", gate_payload=gate_payload)
    execute_payload = parallel_map(
        id="execute-batches",
        items="megaplan.execute.batches",
        step=EXECUTE_BATCH_WORKFLOW,
        reducer=AUTHORING_EXECUTE,
        path_template="execute/{index}",
    )
    review_route_signal = parallel_map(
        id="review-fan-in",
        items=execute_payload,
        step=REVIEW_PANEL_WORKFLOW,
        reducer=AUTHORING_REVIEW,
        path_template="review/{item_id}",
    )
    if review_route_signal == ReviewOutcome.PASS:
        AUTHORING_HALT(id="halt", review_payload=review_route_signal)
    else:
        AUTHORING_HALT(id="review_halt", review_payload=review_route_signal)
