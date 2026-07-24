from __future__ import annotations

from arnold.workflow.authoring import workflow
from .components import plan, execute, review

workflow(
    id="linear-direct",
    version="1.0",
    steps=[
        plan(id="plan"),
        execute(id="execute"),
        review(id="review"),
    ],
)
