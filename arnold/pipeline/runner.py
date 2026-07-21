"""Thin runner API for Arnold pipelines (Step 8 / T12).

Provides a stable namespace for the canonical executor's ``run_pipeline``
entry-point.  This module is intentionally minimal — ``run_step`` and
``next_steps`` are deferred to a follow-up milestone where they have a
real consumer.

The signature is backward-compatible: existing callers passing only
``(pipeline, initial_state, envelope)`` work unchanged.
"""

from __future__ import annotations

from typing import Any, Mapping

from arnold.pipeline.executor import (
    DEFAULT_PARALLEL_SAFE,
    ParallelSafePredicate,
    run_pipeline as _executor_run_pipeline,
)
from arnold.execution.hooks import ExecutorHooks
from arnold.pipeline.types import Pipeline, StepContext
from arnold.runtime.envelope import RuntimeEnvelope
from arnold.execution.operations import OperationRegistry
from arnold.workflow.native_wbc import begin_native_wbc_attempt

__all__ = [
    "run_pipeline",
]


def run_pipeline(
    pipeline: Pipeline,
    initial_state: Mapping[str, Any],
    envelope: RuntimeEnvelope,
    registry: OperationRegistry | None = None,
    *,
    parallel_safe: ParallelSafePredicate | None = None,
    hooks: ExecutorHooks | None = None,
    initial_context: StepContext | None = None,
) -> RuntimeEnvelope | Any:
    """Execute a pipeline by walking edges and invoking each step.

    Thin re-export of :func:`arnold.pipeline.executor.run_pipeline`.  See
    that function for full documentation of the walk-loop and hook insertion
    points.

    .. note::

        ``run_step`` and ``next_steps`` are NOT present in this module.
        They are deferred to a follow-up milestone where they have a real
        consumer (``auto.py`` convergence).
    """
    attempt = begin_native_wbc_attempt(
        envelope.artifact_root,
        producer_family="arnold_pipeline",
        surface="runner",
        run_id=envelope.run_id,
        plugin_id=envelope.plugin_id,
        manifest_hash=envelope.manifest_hash,
        subject={"entry": pipeline.entry, "native": pipeline.native_program is not None},
        metadata={"entrypoint": "arnold.pipeline.run_pipeline"},
    )
    try:
        attempt.effect(
            "dispatch_executor",
            {"native": pipeline.native_program is not None, "entry": pipeline.entry},
        )
        result = _executor_run_pipeline(
            pipeline,
            initial_state,
            envelope,
            registry=registry,
            parallel_safe=parallel_safe,
            hooks=hooks,
            initial_context=initial_context,
        )
    except BaseException as exc:
        attempt.terminal(
            status="failed",
            outcome="error",
            payload={"error_type": exc.__class__.__name__, "error": str(exc)},
        )
        raise
    attempt.terminal(
        status="completed",
        outcome="result",
        payload={"result_type": type(result).__name__},
    )
    return result
