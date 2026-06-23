from __future__ import annotations

from arnold.workflow.authoring import loop, workflow
from tests.fixtures.workflow_authoring.components import bounded_review_loop, execute, plan, review


@workflow(id="m3-bounded-loop", version="1.0")
def flow(brief):
    plan_output = plan(id="plan", brief=brief)
    loop(policy=bounded_review_loop, reentry_id="execute")
    while True:
        evidence = execute(id="execute", plan=plan_output)
        verdict = review(id="review", evidence=evidence)
        if verdict == "approved":
            return None
        plan_output = plan(id="revise", brief=verdict)

