from __future__ import annotations

from arnold.workflow.authoring import workflow
from tests.fixtures.workflow_authoring.components import (
    execute,
    fast_retry,
    handoff_transition,
    operator_suspend,
    plan,
    review,
    review_approval,
    review_timeout,
)


@workflow(
    id="m3-policy-refs",
    version="1.0",
    policies=[operator_suspend, review_approval, handoff_transition],
)
def flow(brief):
    plan_output = plan(id="plan", brief=brief)
    evidence = execute(id="execute", plan=plan_output, policy=fast_retry)
    review(
        id="review",
        evidence=evidence,
        policies=[review_timeout, review_approval, handoff_transition],
    )
