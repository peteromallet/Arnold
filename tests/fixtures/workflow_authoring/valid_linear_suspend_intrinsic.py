from __future__ import annotations

from arnold.workflow.authoring import suspend, workflow
from .components import execute, plan


@workflow(id="linear-suspend-intrinsic", version="1.0")
def linear_suspend(brief: str) -> None:
    plan_output = plan(id="plan", brief=brief)
    execute(id="execute", plan=plan_output)
    suspend(
        route_id="operator",
        capability_id="human.review",
        reentry_id="execute",
        resume_schema_ref="operator.resume",
    )
