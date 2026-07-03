from __future__ import annotations

from arnold.workflow.authoring import workflow
from tests.fixtures.workflow_authoring.components import plan


@workflow(id="invalid-m3-dynamic-dispatch")
def flow(brief):
    plan.__call__(id="plan", brief=brief)
