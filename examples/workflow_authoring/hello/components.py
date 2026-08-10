"""Typed components for the hello-world example workflow."""

from __future__ import annotations

from arnold.workflow.authoring import ComponentProvenance, StepComponent


def _provenance(name: str) -> ComponentProvenance:
    return ComponentProvenance(
        module="examples.workflow_authoring.hello.components",
        qualname=name,
        export_name=name,
    )


greet = StepComponent(id="greet", provenance=_provenance("greet"))
respond = StepComponent(id="respond", provenance=_provenance("respond"))
