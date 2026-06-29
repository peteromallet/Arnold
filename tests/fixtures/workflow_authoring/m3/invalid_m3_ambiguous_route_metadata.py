from __future__ import annotations

from arnold.workflow.authoring import workflow
from tests.fixtures.workflow_authoring.components import execute, route_with_duplicate_bindings


@workflow(id="invalid-m3-ambiguous-route-metadata")
def flow(brief):
    decision = route_with_duplicate_bindings(id="route", brief=brief)
    if decision == "approve":
        execute(id="execute", plan=decision)
    else:
        execute(id="fallback", plan=decision)
