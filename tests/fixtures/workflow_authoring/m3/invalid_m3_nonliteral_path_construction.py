from __future__ import annotations

from arnold.workflow.authoring import workflow
from tests.fixtures.workflow_authoring.components import plan


@workflow(id="invalid-m3-nonliteral-path-construction")
def flow(brief):
    path = f"review/{brief}"
    plan(id="plan", brief=brief)
