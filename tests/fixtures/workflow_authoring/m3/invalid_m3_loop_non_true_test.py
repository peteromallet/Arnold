from __future__ import annotations

from arnold.workflow.authoring import loop, workflow
from tests.fixtures.workflow_authoring.components import bounded_review_loop, execute, plan


@workflow(id="invalid-m3-loop-non-true-test")
def flow(brief):
    plan_output = plan(id="plan", brief=brief)
    loop(policy=bounded_review_loop, reentry_id="execute")
    while plan_output:
        execute(id="execute", plan=plan_output)
