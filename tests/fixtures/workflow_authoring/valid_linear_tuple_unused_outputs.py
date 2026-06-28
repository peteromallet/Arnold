from __future__ import annotations

from arnold.workflow.authoring import workflow
from .components import execute, plan, review


@workflow(id="linear-tuple-unused-outputs", version="1.0")
def linear_tuple_unused_outputs(brief: str) -> None:
    plan_output = plan(id="plan", brief=brief)
    execute_output, evidence = execute(id="execute", plan=plan_output)
    review(id="review", evidence=evidence)
