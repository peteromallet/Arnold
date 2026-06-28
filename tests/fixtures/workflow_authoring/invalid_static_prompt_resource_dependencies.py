from __future__ import annotations

from arnold.workflow.authoring import workflow
from .components import static_prompt_missing, static_resource_missing


workflow(
    id="invalid-static-prompt-resource-dependencies",
    steps=[
        static_prompt_missing(id="draft"),
        static_resource_missing(id="execute"),
    ],
)
