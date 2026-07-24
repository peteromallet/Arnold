from __future__ import annotations

from arnold.workflow.authoring import workflow
from .components import execute, plan, review_subflow


@workflow(id="invalid-nested-subflow", version="1.0")
def invalid_nested_subflow(brief: str) -> None:
    plan_output = plan(id="plan", brief=brief)
    evidence = execute(id="execute", plan=plan_output)
    review_subflow(id="nested-review", manifest_hash=evidence, evidence=evidence)
