from __future__ import annotations

from arnold.workflow.authoring import workflow
from .components import execute, plan

workflow(id="first", steps=[plan(id="plan")])
workflow(id="second", steps=[execute(id="execute")])
