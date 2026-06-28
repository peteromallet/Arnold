from __future__ import annotations

from arnold.workflow.authoring import workflow
from tests.fixtures.workflow_authoring.components import plan, robustness_guard


@workflow(id="invalid-m3-unsupported-workflow-policy-carrier", policy=robustness_guard)
def flow(brief):
    plan(id="plan", brief=brief)
