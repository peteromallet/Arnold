from __future__ import annotations

from arnold.workflow.authoring import workflow
from .components import plan as first_step

workflow(
    id="alias-provenance-loss",
    steps=[
        first_step(id="plan"),
    ],
)
