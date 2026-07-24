from __future__ import annotations

from arnold.workflow.authoring import workflow
from .components import execute, plan


@workflow(id="invalid-parallel-fanout", version="1.0")
def invalid_parallel_fanout(brief: str) -> None:
    plan_output = plan(id="plan", brief=brief)
    for shard in (plan_output, plan_output):
        execute(id="execute", plan=shard)
