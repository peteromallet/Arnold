from __future__ import annotations

from arnold.workflow.authoring import workflow
from .components import plan, execute

@workflow(id="duplicate-local-assignment", version="1.0")
def duplicate_local(brief: str) -> None:
    result = plan(id="plan", brief=brief)
    result = execute(id="execute", plan=result)
