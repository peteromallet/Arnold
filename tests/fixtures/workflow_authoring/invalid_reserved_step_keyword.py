from __future__ import annotations

from arnold.workflow.authoring import workflow
from .components import plan


@workflow(id="reserved-step-keyword")
def reserved(brief: str) -> None:
    plan_output = plan(id="plan", policy=brief)
    plan(id="schema-step", schema=plan_output)
    plan(id="policies-step", policies=brief)
