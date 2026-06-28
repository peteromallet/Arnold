"""Typed components for the shipped live-supervisor authoring scaffold."""

from __future__ import annotations

from arnold.workflow.authoring import ComponentProvenance, StepComponent


def _provenance(name: str) -> ComponentProvenance:
    return ComponentProvenance(
        module="examples.workflow_authoring.shipped.live_supervisor.components",
        qualname=name,
        export_name=name,
    )


classify = StepComponent(id="classify", provenance=_provenance("classify"))
diagnose = StepComponent(id="diagnose", provenance=_provenance("diagnose"))
repair_decision = StepComponent(
    id="repair_decision", provenance=_provenance("repair_decision")
)
recheck_emit = StepComponent(id="recheck_emit", provenance=_provenance("recheck_emit"))
