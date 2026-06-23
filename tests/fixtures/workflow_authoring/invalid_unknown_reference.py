from __future__ import annotations

from arnold.workflow.authoring import workflow
from .components import plan, execute

@workflow(id="unknown-reference", version="1.0")
def unknown_reference(brief: str) -> None:
    plan_output = plan(id="plan", brief=brief)
    execute(id="execute", plan=missing_output)
