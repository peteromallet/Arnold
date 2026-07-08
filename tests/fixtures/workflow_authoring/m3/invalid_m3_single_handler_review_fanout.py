from __future__ import annotations

from arnold.workflow.authoring import workflow
from arnold_pipelines.megaplan.workflows.components import (
    DEFAULT_POLICY,
    SOURCE_FINALIZE,
    SOURCE_REVIEW_PANEL_WORKFLOW,
)


@workflow(id="invalid-m3-single-handler-review-fanout", version="1", policy=DEFAULT_POLICY)
def flow(execute_payload: str, gate_payload: str) -> None:
    SOURCE_FINALIZE(id="finalize", gate_payload=gate_payload)
    SOURCE_REVIEW_PANEL_WORKFLOW(id="review", execute_payload=execute_payload)
