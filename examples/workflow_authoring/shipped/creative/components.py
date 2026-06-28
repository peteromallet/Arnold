"""Typed components for the shipped creative authoring scaffold."""

from __future__ import annotations

from arnold.workflow.authoring import ComponentProvenance, StepComponent


def _provenance(name: str) -> ComponentProvenance:
    return ComponentProvenance(
        module="examples.workflow_authoring.shipped.creative.components",
        qualname=name,
        export_name=name,
    )


prep = StepComponent(id="prep", provenance=_provenance("prep"))
execute_creative = StepComponent(
    id="execute_creative", provenance=_provenance("execute_creative")
)
critique_creative = StepComponent(
    id="critique_creative", provenance=_provenance("critique_creative")
)
revise_creative = StepComponent(
    id="revise_creative", provenance=_provenance("revise_creative")
)
finalize = StepComponent(id="finalize", provenance=_provenance("finalize"))
