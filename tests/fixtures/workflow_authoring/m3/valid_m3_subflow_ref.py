from __future__ import annotations

from arnold.workflow.authoring import workflow
from tests.fixtures.workflow_authoring.components import execute, plan, review_subflow


@workflow(id="m3-subflow-ref", version="1.0")
def flow(brief):
    plan_output = plan(id="plan", brief=brief)
    evidence = execute(id="execute", plan=plan_output)
    review_subflow(
        id="nested-review",
        manifest_hash="sha256:1111111111111111111111111111111111111111111111111111111111111111",
        alias="review",
        evidence=evidence,
    )

