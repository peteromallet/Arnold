from __future__ import annotations

from arnold.workflow.authoring import workflow
from .components import review_prompt

workflow(
    id="wrong-component-kind",
    steps=[
        review_prompt(id="plan"),
    ],
)
