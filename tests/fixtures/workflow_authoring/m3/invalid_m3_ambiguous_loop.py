from __future__ import annotations

from arnold.workflow.authoring import workflow
from tests.fixtures.workflow_authoring.components import execute, plan


@workflow(id="invalid-m3-ambiguous-loop")
def flow(brief):
    plan_output = plan(id="plan", brief=brief)
    while True:
        execute(id="execute", plan=plan_output)

