from __future__ import annotations

from arnold.workflow.authoring import halt, workflow
from .components import execute, plan


@workflow(id="linear-halt-intrinsic", version="1.0")
def linear_halt(brief: str) -> None:
    plan_output = plan(id="plan", brief=brief)
    execute(id="execute", plan=plan_output)
    halt(
        id="operator-stop",
        trigger_ref="operator.stop",
        payload_schema_hash="sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    )
