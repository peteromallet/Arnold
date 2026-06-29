from __future__ import annotations

from arnold.workflow.authoring import workflow
from tests.fixtures.workflow_authoring.components import execute_with_malformed_capability, plan


@workflow(id="invalid-m3-malformed-capability-metadata")
def flow(brief):
    plan_output = plan(id="plan", brief=brief)
    execute_with_malformed_capability(id="execute", plan=plan_output)
