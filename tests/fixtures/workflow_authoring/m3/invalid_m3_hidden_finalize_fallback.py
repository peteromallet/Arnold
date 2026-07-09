from __future__ import annotations

from arnold.workflow.authoring import workflow
from arnold_pipelines.megaplan.workflows.components import (
    AUTHORING_FINALIZE,
    DEFAULT_POLICY,
)


@workflow(id="invalid-m3-hidden-finalize-fallback", version="1", policy=DEFAULT_POLICY)
def flow(gate_payload: str) -> None:
    AUTHORING_FINALIZE(id="finalize", gate_payload=gate_payload)
