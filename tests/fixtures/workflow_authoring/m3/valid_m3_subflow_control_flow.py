from __future__ import annotations

from arnold.workflow.authoring import workflow
from tests.fixtures.workflow_authoring.components import execute, review_subflow, route


@workflow(id="m3-subflow-control-flow", version="1.0")
def flow(brief):
    decision = route(id="route", brief=brief)
    if decision == "review":
        review_subflow(
            id="nested-review",
            manifest_hash="sha256:1111111111111111111111111111111111111111111111111111111111111111",
            alias="review",
            evidence=decision,
        )
    else:
        execute(id="execute", plan=decision)
