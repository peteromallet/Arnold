from __future__ import annotations

from arnold.workflow.authoring import workflow
from tests.fixtures.workflow_authoring.components import plan


def wrapped_plan(brief):
    return plan(id="plan", brief=brief)


@workflow(id="invalid-m3-single-handler-wrapper")
def flow(brief):
    wrapped_plan(brief)
