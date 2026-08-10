from __future__ import annotations

from arnold.workflow.authoring import workflow
from .components import plan


@workflow(id="unsupported-control-flow", version="1.0")
def unsupported(brief: str) -> None:
    # V1 does not support arbitrary for-loops.
    for section in brief.split():
        plan(id="plan", brief=section)
