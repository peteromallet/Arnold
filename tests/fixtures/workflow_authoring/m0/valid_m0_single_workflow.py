from __future__ import annotations

from arnold.pipeline import step, workflow


@step(id="plan", inputs={"brief"}, outputs={"plan_doc"})
def plan(brief: str) -> str:
    """Produce a plan document from a brief."""
    ...


@step(id="execute", inputs={"plan_doc"}, outputs={"output"})
def execute(plan_doc: str) -> str:
    """Execute the plan and produce output."""
    ...


@step(id="review", inputs={"output"}, outputs={"verdict"})
def review(output: str) -> str:
    """Review the output and return a verdict."""
    ...


@workflow(id="simple_pipeline", inputs={"brief"}, outputs={"verdict"})
def simple_pipeline(brief: str) -> str:
    plan_doc = plan(brief)
    output = execute(plan_doc)
    verdict = review(output)
    return verdict
