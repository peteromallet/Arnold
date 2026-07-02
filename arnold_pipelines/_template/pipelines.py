"""Native pipeline declaration example for the ``_template`` package.

Demonstrates a simple two-phase native pipeline (draft → publish)
using :func:`~arnold.pipeline.native.decorators.phase` wrappers and the
:func:`~arnold.pipeline.native.decorators.pipeline` topology decorator.

Copy this directory (renamed without the leading underscore), replace the
skeleton phases with real logic, and the package is ready for native
execution.
"""

from __future__ import annotations

from typing import Any

from arnold.pipeline import StepContext, StepResult
from arnold.pipeline.native import compile_pipeline, phase, pipeline
from arnold.pipeline.native.ir import NativeProgram


@phase(name="draft")
def draft(ctx: object) -> StepResult:
    """Produce an initial draft artifact.

    Replace with real model invocation or transformation logic.
    """
    del ctx
    return StepResult(outputs={"draft": "TODO"}, next="publish")


@phase(name="publish")
def publish(ctx: object) -> StepResult:
    """Finalize and publish the result.

    Replace with real output / side-effect logic.
    """
    del ctx
    return StepResult(outputs={"final_artifact": "TODO"}, next="halt")


@pipeline(name="my-pipeline", description="Template native pipeline: draft → publish")
def my_pipeline_native(ctx: object) -> Any:
    """Compile-time topology for the template native pipeline."""
    state = yield draft(ctx)
    state = yield publish(ctx)
    return state


def build_native_program() -> NativeProgram:
    """Compile and return the native program for the template pipeline."""
    return compile_pipeline(my_pipeline_native)
