from __future__ import annotations

from arnold.workflow.authoring import workflow
from .components import plan

@workflow(id="invalid-function-header", version="1.0")
async def invalid_header(brief: str) -> None:
    plan_output = plan(id="plan", brief=brief)
