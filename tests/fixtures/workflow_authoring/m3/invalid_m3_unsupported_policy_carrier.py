from __future__ import annotations

from arnold.workflow.authoring import workflow
from tests.fixtures.workflow_authoring.components import dynamic_model_router, execute, plan


@workflow(id="invalid-m3-unsupported-policy-carrier")
def flow(brief):
    plan_output = plan(id="plan", brief=brief)
    execute(id="execute", plan=plan_output, policy=dynamic_model_router)

