from __future__ import annotations

from arnold.workflow.authoring import workflow
from tests.fixtures.workflow_authoring.components import execute, plan, review_subflow


@workflow(id="invalid-m3-dynamic-subflow-identity")
def flow(brief, manifest_hash):
    plan_output = plan(id="plan", brief=brief)
    evidence = execute(id="execute", plan=plan_output)
    review_subflow(id="nested-review", manifest_hash=manifest_hash, evidence=evidence)

