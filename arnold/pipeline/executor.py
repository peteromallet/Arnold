"""Minimal neutral graph executor for Arnold pipelines.

Exposes a single ``run_pipeline`` function that walks a ``Pipeline``'s
stages by following ``Edge`` labels, invokes each stage's ``Step.run``
Protocol, applies ``StateDelta`` patches to the working state, and
accepts an optional ``OperationRegistry``.

``ParallelStage`` fan-out is implemented via :class:`concurrent.futures.ThreadPoolExecutor`.
Each step receives an isolated :class:`StepContext` snapshot.  Results
are collected in submission order and passed to the stage's ``join``
callable, which returns a single :class:`StepResult` for dispatch.

Boundary discipline
-------------------

No ``megaplan`` imports.  No forbidden vocabulary literals.
"""

from __future__ import annotations

import concurrent.futures
from typing import Any, Callable, Mapping

from arnold.pipeline.routing import RoutingError, resolve_edge
from arnold.pipeline.state import StateDelta, apply_delta
from arnold.pipeline.types import (
    ParallelStage,
    Pipeline,
    Stage,
    StepContext,
    StepResult,
)
from arnold.runtime.envelope import RuntimeEnvelope
from arnold.runtime.operations import NullOperationRegistry, OperationRegistry

__all__ = [
    "ParallelSafePredicate",
    "DEFAULT_PARALLEL_SAFE",
    "run_pipeline",
]


# ---------------------------------------------------------------------------
# Parallel-safety guard (generic — no InProcessHandlerStep mention)
# ---------------------------------------------------------------------------

ParallelSafePredicate = Callable[[Any], bool]
"""Predicate that inspects a step and returns ``True`` when it is safe for
concurrent fan-out (hermetic, no shared mutable state / plan-dir writes).

Callers supply a predicate appropriate for their runtime.  The Arnold
executor only stores the contract — it never names or inspects specific
step types.
"""


def DEFAULT_PARALLEL_SAFE(step: Any) -> bool:
    """Default parallel-safety predicate — accepts everything.

    Runtimes that know about unsafe step types MUST supply their own
    predicate via the *parallel_safe* parameter of :func:`run_pipeline`.
    """
    del step
    return True


# Internal sentinel for "no value provided" so we can distinguish
# explicit ``None`` from "use the default".
_NO_PARALLEL_SAFE: Any = object()


def run_pipeline(
    pipeline: Pipeline,
    initial_state: Mapping[str, Any],
    envelope: RuntimeEnvelope,
    registry: OperationRegistry | None = None,
    *,
    parallel_safe: ParallelSafePredicate | None = _NO_PARALLEL_SAFE,
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

    ``ParallelStage`` fan-out: each step runs concurrently in a
    :class:`~concurrent.futures.ThreadPoolExecutor`.  Every step receives
    an isolated :class:`StepContext` snapshot (defensive copy of the
    working state).  Results are collected in submission order and passed
    to the stage's ``join`` callable, which returns a single
    :class:`StepResult` whose ``next`` label dispatches like a regular
    :class:`Stage`.

    The *parallel_safe* predicate is consulted before fan-out.  When
    *parallel_safe* returns ``False`` for any step in a
    :class:`ParallelStage`, a ``ValueError`` is raised.  The default
    predicate (:func:`DEFAULT_PARALLEL_SAFE`) accepts everything; runtimes
    that know about unsafe step types (e.g. plan-dir/state-json writers)
    must supply their own.

    ``registry`` is forwarded to future operation-dispatch hooks;
    ``None`` is equivalent to
    :class:`~arnold.runtime.operations.NullOperationRegistry`.

    Returns the ``envelope`` unchanged — it is the authoritative carrier
    for this run and is not mutated by state patches.
    """
    if registry is None:
        registry = NullOperationRegistry()

    if parallel_safe is _NO_PARALLEL_SAFE:
        parallel_safe = DEFAULT_PARALLEL_SAFE

    state: Any = dict(initial_state)
    current_name: str | None = pipeline.entry

    while current_name is not None:
        stage = pipeline.stages.get(current_name)
        if stage is None:
            break

        if isinstance(stage, ParallelStage):
            result = _run_parallel_stage(
                stage, state, envelope, parallel_safe  # type: ignore[arg-type]
            )
        else:
            result = _run_serial_stage(stage, state, envelope)

        if result.state_patch:
            delta = StateDelta(patches=(dict(result.state_patch),))
            state = apply_delta(state, delta)

        # ── Route via the shared policy-neutral resolver ──────────────
        try:
            edge = resolve_edge(stage, result, result.verdict, stage.edges)
        except RoutingError:
            # For simple stages (no declared vocabularies), a missing
            # normal-label edge terminates gracefully — backward compat
            # with pre-T4 lenient dispatch.
            if not stage.decision_vocabulary and not stage.override_vocabulary:
                break
            # Stages with declared vocabularies propagate RoutingError
            # so callers can distinguish invalid signals from normal
            # dispatch misses.
            raise

        if edge is None:
            break  # explicit halt (result.next == 'halt')

        current_name = None if edge.target == "halt" else edge.target

    return envelope


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _run_serial_stage(
    stage: Stage,
    state: Any,
    envelope: RuntimeEnvelope,
) -> StepResult:
    """Execute a single-step serial stage."""
    ctx = StepContext(
        artifact_root=envelope.artifact_root,
        state=dict(state) if isinstance(state, dict) else state,
    )
    return stage.step.run(ctx)


def _run_parallel_stage(
    stage: ParallelStage,
    state: Any,
    envelope: RuntimeEnvelope,
    parallel_safe: ParallelSafePredicate,
    *,
    max_workers: int | None = None,
) -> StepResult:
    """Fan-out *stage* across its steps concurrently, then join.

    Each step receives an isolated :class:`StepContext` snapshot.
    Results are collected in submission order (the order of
    ``stage.steps``).

    Parameters
    ----------
    max_workers:
        Fallback worker count when ``stage.max_workers`` is ``None``.
        Precedence: ``stage.max_workers`` (explicit) > *max_workers*
        (inherited) > ``len(steps)`` (unbounded default).
    """
    steps = stage.steps

    # Guard: reject any step that the runtime's predicate marks unsafe.
    for step in steps:
        if not parallel_safe(step):
            raise ValueError(
                f"ParallelStage {stage.name!r}: step {getattr(step, 'name', step)!r} "
                f"is not parallel-safe (rejected by the runtime's parallel_safe "
                f"predicate)"
            )

    # Build isolated context snapshots (one per step).
    state_copy = dict(state) if isinstance(state, dict) else state
    contexts: list[StepContext] = [
        StepContext(artifact_root=envelope.artifact_root, state=dict(state_copy))
        for _ in steps
    ]

    # Precedence: explicit stage.max_workers > inherited max_workers > len(steps)
    effective_workers = stage.max_workers
    if effective_workers is None:
        effective_workers = max_workers
    if effective_workers is None:
        effective_workers = max(1, len(steps))

    results: list[StepResult] = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=effective_workers) as pool:
        future_to_index: dict[concurrent.futures.Future[StepResult], int] = {}
        for idx, (step, ctx) in enumerate(zip(steps, contexts)):
            future = pool.submit(step.run, ctx)
            future_to_index[future] = idx

        # Collect in submission order.
        indexed: dict[int, StepResult] = {}
        for future in concurrent.futures.as_completed(future_to_index):
            idx = future_to_index[future]
            indexed[idx] = future.result()

        for idx in range(len(steps)):
            results.append(indexed[idx])

    # Build the shared context for the join callable.
    join_ctx = StepContext(
        artifact_root=envelope.artifact_root,
        state=dict(state_copy),
    )
    return stage.join(results, join_ctx)
