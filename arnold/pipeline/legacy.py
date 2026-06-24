"""Compatibility namespace for graph-era pipeline symbols.

The canonical native-first surface remains :mod:`arnold.pipeline`.  This
module gives older graph-runtime callers an explicit import path without
reintroducing removed Megaplan-specific exports at the package root.
"""

from __future__ import annotations

from arnold.pipeline.builder import PipelineBuilder
from arnold.pipeline.executor import (
    DEFAULT_PARALLEL_SAFE,
    MediaCostAccumulator,
    ParallelSafePredicate,
    run_pipeline,
    run_pipeline_resume,
)
from arnold.pipeline.hooks import ExecutorHooks, NullExecutorHooks
from arnold.pipeline.state import StateDelta, apply_delta
from arnold.pipeline.types import (
    Edge,
    ParallelStage,
    Pipeline,
    PipelineVerdict,
    Stage,
    Step,
    StepContext,
    StepResult,
)

__all__ = [
    "DEFAULT_PARALLEL_SAFE",
    "Edge",
    "ExecutorHooks",
    "MediaCostAccumulator",
    "NullExecutorHooks",
    "ParallelSafePredicate",
    "ParallelStage",
    "Pipeline",
    "PipelineBuilder",
    "PipelineVerdict",
    "Stage",
    "StateDelta",
    "Step",
    "StepContext",
    "StepResult",
    "apply_delta",
    "run_pipeline",
    "run_pipeline_resume",
]
