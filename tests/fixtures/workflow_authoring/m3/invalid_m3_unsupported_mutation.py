from __future__ import annotations

from arnold.workflow.authoring import workflow
from tests.fixtures.workflow_authoring.components import execute, route


@workflow(id="invalid-m3-unsupported-mutation")
def flow(brief):
    decision = route(id="route", brief=brief)
    decision = execute(id="mutates-decision", plan=decision)
    if decision == "approve":
        execute(id="execute", plan=decision)

