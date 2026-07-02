from __future__ import annotations

from arnold.pipeline import step, workflow


# ── Child workflow ───────────────────────────────────────────────────────


@step(id="critique", inputs={"draft"}, outputs={"findings"})
def critique(draft: str) -> str:
    ...


@step(id="score", inputs={"findings"}, outputs={"score"})
def score(findings: str) -> float:
    ...


@workflow(id="review_subprocess", inputs={"draft"}, outputs={"score"})
def review_subprocess(draft: str) -> float:
    findings = critique(draft)
    return score(findings)


# ── Parent workflow ──────────────────────────────────────────────────────


@step(id="plan_parent", inputs={"brief"}, outputs={"plan_doc"})
def plan_parent(brief: str) -> str:
    ...


@step(id="finalize_parent", inputs={"score"}, outputs={"final"})
def finalize_parent(score: float) -> str:
    ...


@workflow(id="parent_pipeline", inputs={"brief"}, outputs={"final"})
def parent_pipeline(brief: str) -> str:
    plan_doc = plan_parent(brief)
    child_score = review_subprocess(plan_doc)
    return finalize_parent(child_score)
