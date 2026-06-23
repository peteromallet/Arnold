from __future__ import annotations

from arnold.workflow.authoring import workflow

plan = __import__("tests.fixtures.workflow_authoring.components").plan

workflow(
    id="dynamic-import",
    steps=[
        plan(id="plan"),
    ],
)
