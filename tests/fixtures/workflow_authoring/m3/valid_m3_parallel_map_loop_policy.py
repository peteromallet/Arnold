from __future__ import annotations

from arnold.pipeline import parallel_map
from arnold.workflow.authoring import loop, workflow
from tests.fixtures.workflow_authoring.components import bounded_review_loop, plan, review, review_timeout


@workflow(id="m3-parallel-map-loop-policy", version="1.0")
def flow(briefs):
    findings = parallel_map(
        id="review-all",
        items=briefs,
        step=plan,
        reducer=review,
        path_template="reviews/{item_id}",
    )
    loop(policy=bounded_review_loop, reentry_id="review-all")
    while True:
        verdict = review(id="review", evidence=findings, policy=review_timeout)
        if verdict == "approved":
            break
        findings = parallel_map(
            id="revise-all",
            items=briefs,
            step=plan,
            reducer=review,
            path_template="revise/{index}",
        )
