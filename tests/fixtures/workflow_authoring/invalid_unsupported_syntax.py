from __future__ import annotations

from arnold.workflow.authoring import workflow
from .components import plan

@workflow(id="unsupported-syntax", version="1.0")
def unsupported(brief: str) -> None:
    if brief:
        plan(id="plan")
