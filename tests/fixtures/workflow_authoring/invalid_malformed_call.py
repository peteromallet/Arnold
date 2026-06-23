from __future__ import annotations

from arnold.workflow.authoring import workflow
from .components import plan

workflow(
    id="malformed-call",
    steps=[
        plan("plan"),
    ],
)
