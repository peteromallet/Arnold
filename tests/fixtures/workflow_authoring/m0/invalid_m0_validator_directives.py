from __future__ import annotations

from arnold.pipeline import step, workflow


@step(id="score", inputs={"output"}, outputs={"score"})
def score(output: str) -> float:
    ...


@workflow(id="validator_directive_workflow", inputs={"output"}, outputs={"score"})
def validator_directive_workflow(output: str) -> float:
    # REJECTED — validator directive in source
    validate(lambda state: state["score"] > 0.8, on_fail="escalate")
    result = score(output)
    return result
