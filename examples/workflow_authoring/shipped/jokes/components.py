"""Typed components for the shipped jokes authoring scaffold."""

from __future__ import annotations

from arnold.workflow.authoring import ComponentProvenance, StepComponent


def _provenance(name: str) -> ComponentProvenance:
    return ComponentProvenance(
        module="examples.workflow_authoring.shipped.jokes.components",
        qualname=name,
        export_name=name,
    )


draft = StepComponent(id="draft", provenance=_provenance("draft"))
tighten = StepComponent(id="tighten", provenance=_provenance("tighten"))
emit = StepComponent(id="emit", provenance=_provenance("emit"))
