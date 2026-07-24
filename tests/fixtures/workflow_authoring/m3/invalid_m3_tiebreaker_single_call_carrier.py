from __future__ import annotations

from arnold.workflow.authoring import workflow
from arnold_pipelines.megaplan.workflows.components import SOURCE_TIEBREAKER_WORKFLOW


@workflow(id="invalid-m3-tiebreaker-single-call-carrier")
def flow(gate_payload):
    SOURCE_TIEBREAKER_WORKFLOW(id="tiebreaker_child", gate_payload=gate_payload)
