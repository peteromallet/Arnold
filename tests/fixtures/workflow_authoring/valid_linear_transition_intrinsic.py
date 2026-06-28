from __future__ import annotations

from arnold.workflow.authoring import transition, workflow
from .components import execute, plan


@workflow(id="linear-transition-intrinsic", version="1.0")
def linear_transition(brief: str) -> None:
    plan_output = plan(id="plan", brief=brief)
    execute(id="execute", plan=plan_output)
    transition(
        id="operator-resume",
        type="override",
        trigger_ref="operator.resume",
        target_ref="execute",
        policy_ref="review_approval",
    )
