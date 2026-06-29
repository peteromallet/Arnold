from __future__ import annotations

from arnold.workflow.authoring import workflow
from tests.fixtures.workflow_authoring.components import execute, plan, reprompt_guard


@workflow(id="invalid-m3-unsupported-step-policy-carrier")
def flow(brief):
    plan_output = plan(id="plan", brief=brief)
    execute(id="execute", plan=plan_output, policy=reprompt_guard)
