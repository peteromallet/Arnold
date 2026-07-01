"""M1 graph-era compatibility namespace — delegates to canonical implementations.

This module exists as a single import surface for all graph-era symbols
that legacy callers imported from scattered modules.  Every name here is a
thin re-export from its authoritative, policy-neutral canonical module.

.. attention::
   This is a temporary M1 compatibility namespace.  It will be removed
   during M7 when the graph-era surface is fully purged.

Usage::

    from arnold.pipeline.legacy import (
        Edge, Stage, ParallelStage,
        PipelineBuilder, PipelineRegistry,
        validate,
        StepInvocation,
        ExecutorHooks, NullExecutorHooks,
        run_pipeline, run_pipeline_resume,
    )
"""

from __future__ import annotations

# -- graph structural types ---------------------------------------------------
from arnold.pipeline.types import Edge, ParallelStage, Stage

# -- builder & registry -------------------------------------------------------
from arnold.workflow.builder import PipelineBuilder
from arnold.workflow.registry import PipelineRegistry

# -- validator ----------------------------------------------------------------
from arnold.workflow.validator import validate

# -- step invocation ----------------------------------------------------------
from arnold.execution.step_invocation import StepInvocation

# -- executor hooks -----------------------------------------------------------
from arnold.execution.hooks import ExecutorHooks, NullExecutorHooks

# -- runtime entrypoints ------------------------------------------------------
from arnold.pipeline.executor import run_pipeline, run_pipeline_resume

__all__ = [
    "Edge",
    "ExecutorHooks",
    "NullExecutorHooks",
    "ParallelStage",
    "PipelineBuilder",
    "PipelineRegistry",
    "Stage",
    "StepInvocation",
    "run_pipeline",
    "run_pipeline_resume",
    "validate",
]
