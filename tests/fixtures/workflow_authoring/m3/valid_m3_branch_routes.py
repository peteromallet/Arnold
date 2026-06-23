from __future__ import annotations

from arnold.workflow.authoring import workflow
from tests.fixtures.workflow_authoring.components import execute, plan, review, route


@workflow(id="m3-branch-routes", version="1.0")
def flow(brief):
    decision = route(id="route", brief=brief)
    if decision == "approve":
        execute_output = execute(id="execute", plan=decision)
        review(id="review-approved", evidence=execute_output)
    elif decision == "revise":
        plan_output = plan(id="revise-plan", brief=brief)
        review(id="review-revised", evidence=plan_output)
    else:
        review(id="review-fallback", evidence=decision)

