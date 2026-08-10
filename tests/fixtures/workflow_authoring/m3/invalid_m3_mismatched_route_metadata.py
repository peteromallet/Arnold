from __future__ import annotations

from arnold.workflow.authoring import workflow
from tests.fixtures.workflow_authoring.components import execute, route_with_mismatched_binding


@workflow(id="invalid-m3-mismatched-route-metadata")
def flow(brief):
    decision = route_with_mismatched_binding(id="route", brief=brief)
    if decision == "approve":
        execute(id="execute", plan=decision)
    else:
        execute(id="fallback", plan=decision)
