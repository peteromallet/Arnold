from __future__ import annotations

from arnold.workflow.authoring import workflow
from tests.fixtures.workflow_authoring.components import execute, route


@workflow(id="invalid-runtime-iteration")
def flow(brief):
    decision = route(id="route", brief=brief)
    for item in decision:
        execute(id="execute", plan=item)
