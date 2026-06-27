from __future__ import annotations

from arnold.workflow.authoring import workflow
from tests.fixtures.workflow_authoring.components import execute, route


@workflow(id="invalid-runtime-truthiness")
def flow(brief):
    decision = route(id="route", brief=brief)
    if decision:
        execute(id="execute", plan=decision)
