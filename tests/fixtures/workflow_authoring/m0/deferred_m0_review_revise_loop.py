from __future__ import annotations

from arnold.pipeline import step, workflow


@step(id="review_loop_step", inputs={"draft"}, outputs={"findings", "passed"})
def review_loop_step(draft: str) -> dict:
    """Review a draft. Returns findings and a boolean passed flag."""
    ...


@step(id="revise_loop_step", inputs={"draft", "findings"}, outputs={"revised"})
def revise_loop_step(draft: str, findings: str) -> str:
    """Revise the draft based on review findings."""
    ...


@workflow(
    id="review_loop",
    inputs={"draft"},
    outputs={"final_draft"},
)
def review_loop(draft: str, max_attempts: int = 3) -> str:
    for _ in range(max_attempts):
        result = review_loop_step(draft)
        if result["passed"]:
            break
        draft = revise_loop_step(draft, result["findings"])
    return draft
