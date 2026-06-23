from __future__ import annotations

from arnold.workflow.authoring import workflow
from tests.fixtures.workflow_authoring.components import execute, route


@workflow(id="invalid-m3-non-literal-routing")
def flow(brief, selected_route):
    decision = route(id="route", brief=brief)
    if decision == selected_route:
        execute(id="execute", plan=decision)

