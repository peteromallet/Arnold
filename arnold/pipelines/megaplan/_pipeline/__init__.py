"""Compatibility shim for the legacy ``megaplan._pipeline`` package.

The active runtime behavior has moved to canonical locations under
``arnold.pipelines.megaplan`` (e.g. ``schema_registry_adapter``,
``step_io_policy_adapter``, ``registry``). This module retains only the
graph-era primitive re-exports that existing tests and demos still import.
"""

from __future__ import annotations

from arnold.pipelines.megaplan._pipeline.types import (  # noqa: E402
    Edge,
    Overlay,
    ParallelStage,
    Pipeline,
    PipelineVerdict,
    Stage,
    Step,
    StepContext,
    StepResult,
)

__all__ = [
    "Edge",
    "Overlay",
    "ParallelStage",
    "Pipeline",
    "PipelineVerdict",
    "Stage",
    "Step",
    "StepContext",
    "StepResult",
]
