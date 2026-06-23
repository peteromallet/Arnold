from __future__ import annotations

from arnold.workflow.authoring import workflow
from .components import plan

workflow = object()

workflow(
    id="intrinsic-shadowing",
    steps=[
        plan(id="plan"),
    ],
)
