from __future__ import annotations

from arnold.workflow.authoring import workflow
from tests.fixtures.workflow_authoring.components import execute, malformed_timing, plan


@workflow(id="invalid-m3-malformed-timing-policy-config")
def flow(brief):
    plan_output = plan(id="plan", brief=brief)
    execute(id="execute", plan=plan_output, policy=malformed_timing)
