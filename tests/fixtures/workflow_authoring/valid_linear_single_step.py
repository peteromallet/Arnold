from __future__ import annotations

from arnold.workflow.authoring import workflow
from .components import plan


@workflow(id="linear-single-step", version="1.0")
def linear_single_step(brief: str) -> None:
    plan(id="plan", brief=brief)
