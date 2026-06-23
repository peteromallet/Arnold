from __future__ import annotations

from arnold.workflow.authoring import (
    ComponentProvenance,
    PromptComponent,
    SchemaComponent,
    StepComponent,
)


def _provenance(name: str) -> ComponentProvenance:
    return ComponentProvenance(
        module="tests.fixtures.workflow_authoring.components",
        qualname=name,
        export_name=name,
    )


plan_output = SchemaComponent(
    id="plan_output",
    provenance=_provenance("plan_output"),
    schema_type="python-type",
    schema={"type": "Plan"},
)
review_prompt = PromptComponent(
    id="review_prompt",
    provenance=_provenance("review_prompt"),
    template="Review the execution evidence.",
    parameters=("evidence",),
)

plan = StepComponent(id="plan", provenance=_provenance("plan"), output_schema=plan_output)
execute = StepComponent(id="execute", provenance=_provenance("execute"))
review = StepComponent(id="review", provenance=_provenance("review"), prompt=review_prompt)
