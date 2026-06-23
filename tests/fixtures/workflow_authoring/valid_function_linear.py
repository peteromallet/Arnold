from __future__ import annotations

from arnold.workflow.authoring import workflow
from .components import plan, execute, review

@workflow(id="linear-function", version="1.0")
def linear(brief: str) -> None:
    plan_output = plan(id="plan", brief=brief)
    execute_output, evidence = execute(id="execute", plan=plan_output)
    review(id="review", evidence=evidence)
