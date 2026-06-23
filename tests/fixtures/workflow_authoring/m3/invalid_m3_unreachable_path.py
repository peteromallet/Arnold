from __future__ import annotations

from arnold.workflow.authoring import halt, workflow
from tests.fixtures.workflow_authoring.components import execute, route


@workflow(id="invalid-m3-unreachable-path")
def flow(brief):
    decision = route(id="route", brief=brief)
    if decision == "approve":
        halt(id="approved-stop", trigger_ref="route.approve")
    else:
        halt(id="fallback-stop", trigger_ref="route.fallback")
    execute(id="unreachable", plan=decision)
