from __future__ import annotations

from arnold.workflow.authoring import workflow
from .components import plan


@workflow(id="invalid-dynamic-component-construction", version="1.0")
def invalid_dynamic_component_construction(brief: str) -> None:
    plan.__class__(
        id="dynamic",
        provenance=plan.provenance,
    )(id="dynamic", brief=brief)
