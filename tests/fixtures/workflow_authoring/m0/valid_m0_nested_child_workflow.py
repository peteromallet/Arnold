from __future__ import annotations

from arnold.workflow.authoring import workflow
from tests.fixtures.workflow_authoring.components import execute, plan, review_subflow


@workflow(id="m0-nested-child")
def flow(brief):
    plan_output = plan(id="plan", brief=brief)
    evidence = execute(id="execute", plan=plan_output)
    review_subflow(id="nested-review", evidence=evidence)
