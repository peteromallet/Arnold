from __future__ import annotations

import arnold
from arnold.workflow.authoring import workflow
from .components import plan

workflow(
    id="forbidden-root-import",
    steps=[
        plan(id="plan"),
    ],
)
