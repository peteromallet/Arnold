from __future__ import annotations

from arnold.workflow.authoring import loop, workflow
from tests.fixtures.workflow_authoring.components import bounded_review_loop, execute, plan


def choose_loop_policy():
    return bounded_review_loop


@workflow(id="invalid-m3-loop-dynamic-bounds")
def flow(brief):
    plan_output = plan(id="plan", brief=brief)
    loop(policy=choose_loop_policy(), reentry_id="execute")
    while True:
        execute(id="execute", plan=plan_output)
