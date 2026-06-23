from __future__ import annotations

from arnold.workflow.authoring import workflow
from .components import missing

workflow(
    id="unknown-component",
    steps=[
        missing(id="plan"),
    ],
)
