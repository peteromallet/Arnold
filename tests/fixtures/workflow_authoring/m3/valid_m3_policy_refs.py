from __future__ import annotations

from arnold.workflow.authoring import workflow
from tests.fixtures.workflow_authoring.components import (
    execute_with_artifact_capability,
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
    evidence = execute_with_artifact_capability(id="execute", plan=plan_output, policy=fast_retry)
    review(
        id="review",
        evidence=evidence,
        policies=[review_timeout, review_approval, handoff_transition],
    )
