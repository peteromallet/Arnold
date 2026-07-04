from __future__ import annotations

from arnold.workflow.authoring import workflow
from tests.fixtures.workflow_authoring.components import execute, plan

workflow(
    id="m0-single",
    steps=[
        plan(id="plan"),
        execute(id="execute"),
    ],
)
