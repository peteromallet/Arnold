from __future__ import annotations

from arnold.workflow.authoring import workflow
from tests.fixtures.workflow_authoring.components import execute, review, route


@workflow(id="invalid-m3-repeated-route-comparison")
def flow(brief):
    decision = route(id="route", brief=brief)
    if decision == "approve":
        execute(id="execute", plan=decision)
    elif decision == "approve":
        review(id="review", evidence=decision)
    else:
        review(id="fallback", evidence=decision)
