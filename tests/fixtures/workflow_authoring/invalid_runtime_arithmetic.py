from __future__ import annotations

from arnold.workflow.authoring import workflow
from tests.fixtures.workflow_authoring.components import execute, route


@workflow(id="invalid-runtime-arithmetic")
def flow(brief):
    decision = route(id="route", brief=brief)
    execute(id="execute", plan=decision + 1)
