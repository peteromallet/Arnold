from __future__ import annotations

from arnold.workflow.authoring import loop, workflow
from tests.fixtures.workflow_authoring.components import execute, plan, unbounded_review_loop


@workflow(id="invalid-m3-loop-missing-bounds")
def flow(brief):
    plan_output = plan(id="plan", brief=brief)
    loop(policy=unbounded_review_loop, reentry_id="execute")
    while True:
        execute(id="execute", plan=plan_output)
