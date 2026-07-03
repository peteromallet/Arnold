from __future__ import annotations

from arnold.pipeline import step, workflow


# ── Shared child workflow ────────────────────────────────────────────────


@step(id="review_step", inputs={"draft"}, outputs={"findings"})
def review_step(draft: str) -> str:
    ...


@step(id="verdict_step", inputs={"findings"}, outputs={"verdict"})
def verdict_step(findings: str) -> str:
    ...


@workflow(id="review", inputs={"draft"}, outputs={"verdict"})
def review(draft: str) -> str:
    findings = review_step(id="review_step", draft=draft)
    return verdict_step(id="verdict_step", findings=findings)


# ── Step used between the two review sites ───────────────────────────────


@step(id="revise", inputs={"draft", "findings"}, outputs={"revised_draft"})
def revise(draft: str, findings: str) -> str:
    ...


# ── Parent workflow with two review call sites ───────────────────────────


@workflow(id="multi_review", inputs={"draft"}, outputs={"verdict"})
def multi_review(draft: str) -> str:
    first_verdict = review(id="first_review", draft=draft)
    revised = revise(id="revise", draft=draft, findings=first_verdict)
    second_verdict = review(id="second_review", draft=revised)
    return second_verdict
