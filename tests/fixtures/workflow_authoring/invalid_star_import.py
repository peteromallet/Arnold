from __future__ import annotations

from arnold.workflow.authoring import workflow
from .components import *

workflow(
    id="star-import",
    steps=[
        plan(id="plan"),
    ],
)
