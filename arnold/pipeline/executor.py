"""Minimal neutral graph executor for Arnold pipelines.

Exposes a single ``run_pipeline`` function that walks a ``Pipeline``'s
stages by following ``Edge`` labels, invokes each stage's ``Step.run``
Protocol, applies ``StateDelta`` patches to the working state, and
accepts an optional ``OperationRegistry``.

``ParallelStage`` fan-out semantics are deferred to M2b — encountering
one raises ``NotImplementedError``.

Boundary discipline
-------------------

No ``megaplan`` imports.  No forbidden vocabulary literals.
"""

from __future__ import annotations

from typing import Any, Mapping

from arnold.pipeline.state import StateDelta, apply_delta
from arnold.pipeline.types import ParallelStage, Pipeline, StepContext
from arnold.runtime.envelope import RuntimeEnvelope
from arnold.runtime.operations import NullOperationRegistry, OperationRegistry

__all__ = ["run_pipeline"]


def run_pipeline(
    pipeline: Pipeline,
    initial_state: Mapping[str, Any],
    envelope: RuntimeEnvelope,
    registry: OperationRegistry | None = None,
) -> RuntimeEnvelope:
    """Execute a pipeline by walking edges and invoking each step.

    Execution begins at ``pipeline.entry``.  For each stage:

    1. Build a :class:`~arnold.pipeline.types.StepContext` from the
       current working state and ``envelope.artifact_root``.
    2. Call ``stage.step.run(ctx)`` → :class:`~arnold.pipeline.types.StepResult`.
    3. Wrap ``result.state_patch`` in a :class:`~arnold.pipeline.state.StateDelta`
       and apply it via :func:`~arnold.pipeline.state.apply_delta`.
    4. Follow the edge whose ``label`` matches ``result.next``.  The
       reserved label ``"halt"`` and any edge whose ``target`` is
       ``"halt"`` terminate the run immediately.  A missing edge also
       terminates (defensive).

    ``registry`` is forwarded to future operation-dispatch hooks;
    ``None`` is equivalent to :class:`~arnold.runtime.operations.NullOperationRegistry`.

    Returns the ``envelope`` unchanged — it is the authoritative carrier
    for this run and is not mutated by state patches.
    """
    if registry is None:
        registry = NullOperationRegistry()

    state: Any = dict(initial_state)
    current_name: str | None = pipeline.entry

    while current_name is not None:
        stage = pipeline.stages.get(current_name)
        if stage is None:
            break

        if isinstance(stage, ParallelStage):
            raise NotImplementedError(
                "ParallelStage fan-out is deferred to M2b; "
                f"stage {current_name!r} cannot be executed by the M2a executor."
            )

        ctx = StepContext(
            artifact_root=envelope.artifact_root,
            state=dict(state) if isinstance(state, dict) else state,
        )

        result = stage.step.run(ctx)

        if result.state_patch:
            delta = StateDelta(patches=(dict(result.state_patch),))
            state = apply_delta(state, delta)

        next_label = result.next
        if next_label == "halt":
            break

        next_name: str | None = None
        for edge in stage.edges:
            if edge.label == next_label:
                next_name = None if edge.target == "halt" else edge.target
                break

        current_name = next_name

    return envelope
