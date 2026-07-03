from __future__ import annotations

from arnold.workflow.authoring import workflow
from tests.fixtures.workflow_authoring.components import execute, plan, review_subflow


@workflow(id="m0-repeated-call-sites")
def flow(brief):
    plan_output = plan(id="plan", brief=brief)
    evidence_a = execute(id="execute-a", plan=plan_output)
    review_subflow(id="nested-review-a", evidence=evidence_a)
    evidence_b = execute(id="execute-b", plan=plan_output)
    review_subflow(id="nested-review-b", evidence=evidence_b)
