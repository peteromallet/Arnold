from __future__ import annotations

from arnold.pipeline import step, workflow
from arnold.pipeline.native.ir import NativeProgram

# REJECTED — Pipeline.native_program source-truth projection
# native_program is a dispatch substrate, not canonical source truth.
# Deriving topology primarily from native_program is non-conformant.

native = NativeProgram(
    instructions=[],
    phases={},
    pipelines={},
)

# Treating native_program as the source-authoritative representation:
# the product semantics are derived from this dispatch substrate
# rather than from the decorated source below.

@step(id="plan", inputs={"brief"}, outputs={"plan_doc"})
def plan(brief: str) -> str:
    ...


@workflow(id="native_program_projection_workflow", inputs={"brief"}, outputs={"plan_doc"})
def native_program_projection_workflow(brief: str) -> str:
    return plan(brief)
