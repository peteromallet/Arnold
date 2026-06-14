"""Executor hook protocol for Arnold pipelines.

``ExecutorHooks`` is the single extension point through which runtimes inject
behaviour into the canonical walk-loop without importing megaplan from inside
``arnold/pipeline/``.

All 12 callbacks have documented insertion points and explicit no-op defaults
in ``NullExecutorHooks``.  The surface is FROZEN here — downstream slices
(Steps 4–7b, 9, 10) code against it and may not add callbacks.

Media cost accounting (AR3)
---------------------------

:func:`account_media_cost_from_result` is an **opt-in** helper that reads
``StepResult.hook_metadata['media_usage']``, computes priced and unknown
cost lines via :func:`~arnold.pipeline.media_cost.compute_media_cost`, and
returns them.  It is a pure function — it never modifies state and never
raises on malformed metadata.  Hook implementations that want media
accounting call it from their ``on_step_end`` override and accumulate the
returned ``CostResult`` lines wherever they see fit (e.g. an in-memory list
on the hooks instance).

When hooks are not configured (i.e. ``NullExecutorHooks`` or ``hooks=None``),
no media accounting occurs — the helper is never invoked and runs are
unchanged.

Boundary discipline
-------------------

No ``megaplan`` imports.  No forbidden vocabulary literals.
"""

from __future__ import annotations

from typing import Any, Protocol, Sequence, runtime_checkable

from arnold.pipeline.media_cost import (
    MediaPricingEntry,
    compute_media_cost,
    media_usage_from_hook_metadata,
)
from arnold.pipeline.routing import RoutingError
from arnold.pipeline.state import StateDelta, apply_delta
from arnold.pipeline.types import (
    Edge,
    ParallelStage,
    Stage,
    StepContext,
    StepResult,
)

__all__ = [
    "ExecutorHooks",
    "NullExecutorHooks",
    "account_media_cost_from_result",
]


@runtime_checkable
class ExecutorHooks(Protocol):
    """Structural protocol for canonical executor extension points.

    Every method is called by the canonical executor at the documented
    insertion point.  Implementations that only need a subset of callbacks
    may inherit from :class:`NullExecutorHooks` and override what they need.

    **Frozen surface** — no new callbacks may be added after Step 3.
    """

    def on_step_start(
        self,
        stage: Stage | ParallelStage,
        ctx: StepContext,
    ) -> StepContext:
        """Insertion point: immediately before ``stage.step.run(ctx)``.

        May return a rewritten ``StepContext`` (e.g. to inject per-step
        resources or rewrite the bound step).

        No-op default: returns ``ctx`` unchanged.
        """
        ...

    def on_step_end(
        self,
        stage: Stage | ParallelStage,
        ctx: StepContext,
        result: StepResult,
    ) -> StepResult:
        """Insertion point: immediately after ``stage.step.run(ctx)`` returns.

        May return a rewritten ``StepResult`` (e.g. to verify outputs or
        inject metadata).

        No-op default: returns ``result`` unchanged.
        """
        ...

    def on_step_error(
        self,
        stage: Stage | ParallelStage,
        ctx: StepContext,
        exc: BaseException,
    ) -> None:
        """Insertion point: when ``stage.step.run(ctx)`` raises an exception.

        The exception propagates from the executor regardless; this callback
        is for telemetry and error-record writing only.

        No-op default: does nothing.
        """
        ...

    def merge_state(
        self,
        stage: Stage | ParallelStage,
        current_state: Any,
        patch: StateDelta,
        owned_keys: frozenset[str],
    ) -> tuple[Any, frozenset[str]]:
        """Insertion point: after ``result.outputs`` are merged, before edge resolution.

        Receives the executor's per-run owned-key accumulator; returns
        ``(new_state, new_owned_keys)``.

        No-op default: applies the delta via ``apply_delta`` and returns
        ``owned_keys`` unchanged.
        """
        ...

    def join_envelope(
        self,
        stage: Stage | ParallelStage,
        current_envelope: Any,
        step_envelope: Any,
    ) -> Any:
        """Insertion point: envelope accumulation after each step completes.

        No-op default: returns ``step_envelope`` when truthy, else
        ``current_envelope``.
        """
        ...

    def join_parallel_results(
        self,
        stage: ParallelStage,
        ctx: StepContext,
        child_results: Sequence[StepResult],
    ) -> StepResult:
        """Insertion point: after all parallel children complete, before dispatch.

        Receives the full ordered child-result list (submission order).  The
        hook replaces the ``stage.join`` call for the hooks path; the default
        delegates back to ``stage.join`` to preserve existing behavior.

        No-op default: delegates to ``stage.join(list(child_results), ctx)``.
        """
        ...

    def should_suspend(
        self,
        stage: Stage | ParallelStage,
        state: Any,
        result: StepResult,
    ) -> tuple[bool, str | None]:
        """Insertion point: after each step result, before state patching.

        One of the three terminal walk-loop exits.  Returns
        ``(should_suspend, halt_reason)``; the executor stashes ``halt_reason``
        on the hooks instance before returning the working envelope.

        No-op default: returns ``(False, None)``.
        """
        ...

    def should_halt_loop(
        self,
        stage: Stage | ParallelStage,
        state: Any,
        iteration: int,
    ) -> tuple[bool, str | None]:
        """Insertion point: at the start of each walk-loop iteration (pre-step).

        One of the three terminal walk-loop exits.  Covers ``loop_condition``,
        ``policy.stall``, ``policy.cost.should_abort``, and ``max_iterations``.

        No-op default: returns ``(False, None)``.
        """
        ...

    def resolve_routing_fallback(
        self,
        stage: Stage | ParallelStage,
        result: StepResult,
        edges: tuple[Edge, ...],
        error: RoutingError,
    ) -> Edge | None:
        """Insertion point: when ``resolve_edge`` raises a :class:`RoutingError`.

        Returns an :class:`Edge` to use as a fallback, or ``None`` to let the
        executor apply its default ``RoutingError`` handling (break for
        vocabulary-less stages, re-raise for vocabulary stages).

        No-op default: returns ``None``.
        """
        ...

    def on_edge_traverse(
        self,
        producer_stage: Stage | ParallelStage,
        consumer_stage: Stage | ParallelStage,
        ctx: StepContext,
        result: StepResult,
    ) -> None:
        """Insertion point: after ``resolve_edge`` returns a non-halt target.

        Called with the resolved producer and consumer stage objects before the
        walk-loop advances to the next stage.  Used for step-IO handoff
        validation and cursor propagation.

        No-op default: does nothing.
        """
        ...

    def on_stage_complete(
        self,
        stage: Stage | ParallelStage,
        ctx: StepContext,
        result: StepResult,
        state: Any,
        owned_keys: frozenset[str],
    ) -> None:
        """Insertion point: at every walk-loop terminal exit.

        Called for all three terminal conditions — halt, ``should_suspend``,
        and ``should_halt_loop`` — with the final state and owned-keys
        accumulator.  Also called at each normal stage completion before
        advancing to the next stage.  Covers state-merge-to-disk, telemetry,
        and suspension-cursor persistence.

        No-op default: does nothing.
        """
        ...

    def is_parallel_safe(self, step: Any) -> bool:
        """Insertion point: parallel-safety predicate for each step in a fan-out.

        Overrides :func:`~arnold.pipeline.executor.DEFAULT_PARALLEL_SAFE` when
        custom hooks are provided.

        No-op default: returns ``True`` (accepts everything).
        """
        ...


class NullExecutorHooks:
    """No-op reference implementation of :class:`ExecutorHooks`.

    Every method implements the documented no-op default.  Passing an instance
    to :func:`arnold.pipeline.executor.run_pipeline` produces byte-for-byte
    identical behavior to the ``hooks=None`` path.

    ``halt_reason`` is set by the executor when any terminal exit fires; the
    compat shim reads it to reconstruct the legacy result dict.
    """

    halt_reason: str | None

    def __init__(self) -> None:
        self.halt_reason = None

    def on_step_start(
        self,
        stage: Stage | ParallelStage,
        ctx: StepContext,
    ) -> StepContext:
        return ctx

    def on_step_end(
        self,
        stage: Stage | ParallelStage,
        ctx: StepContext,
        result: StepResult,
    ) -> StepResult:
        return result

    def on_step_error(
        self,
        stage: Stage | ParallelStage,
        ctx: StepContext,
        exc: BaseException,
    ) -> None:
        pass

    def merge_state(
        self,
        stage: Stage | ParallelStage,
        current_state: Any,
        patch: StateDelta,
        owned_keys: frozenset[str],
    ) -> tuple[Any, frozenset[str]]:
        return apply_delta(current_state, patch), owned_keys

    def join_envelope(
        self,
        stage: Stage | ParallelStage,
        current_envelope: Any,
        step_envelope: Any,
    ) -> Any:
        return step_envelope if step_envelope else current_envelope

    def join_parallel_results(
        self,
        stage: ParallelStage,
        ctx: StepContext,
        child_results: Sequence[StepResult],
    ) -> StepResult:
        return stage.join(list(child_results), ctx)

    def should_suspend(
        self,
        stage: Stage | ParallelStage,
        state: Any,
        result: StepResult,
    ) -> tuple[bool, str | None]:
        return False, None

    def should_halt_loop(
        self,
        stage: Stage | ParallelStage,
        state: Any,
        iteration: int,
    ) -> tuple[bool, str | None]:
        return False, None

    def resolve_routing_fallback(
        self,
        stage: Stage | ParallelStage,
        result: StepResult,
        edges: tuple[Edge, ...],
        error: RoutingError,
    ) -> Edge | None:
        return None

    def on_edge_traverse(
        self,
        producer_stage: Stage | ParallelStage,
        consumer_stage: Stage | ParallelStage,
        ctx: StepContext,
        result: StepResult,
    ) -> None:
        pass

    def on_stage_complete(
        self,
        stage: Stage | ParallelStage,
        ctx: StepContext,
        result: StepResult,
        state: Any,
        owned_keys: frozenset[str],
    ) -> None:
        pass

    def is_parallel_safe(self, step: Any) -> bool:
        return True


# ---------------------------------------------------------------------------
# Media cost accounting helper (AR3 — opt-in, nonfatal)
# ---------------------------------------------------------------------------


def account_media_cost_from_result(
    result: StepResult,
    *,
    provider: str,
    model: str,
    pricing_rows: tuple[MediaPricingEntry, ...] | None = None,
) -> "tuple[Any, ...]":
    """Read media usage from *result* and compute cost lines (opt-in, nonfatal).

    Hook implementations call this from their :meth:`ExecutorHooks.on_step_end`
    override to account for media usage attached to a ``StepResult`` via
    ``hook_metadata['media_usage']``.

    Parameters
    ----------
    result:
        The ``StepResult`` produced by a step invocation.
    provider:
        Provider name passed to :func:`~arnold.pipeline.media_cost.compute_media_cost`
        (e.g. ``"openai"``).
    model:
        Model name passed to ``compute_media_cost`` (e.g. ``"dall-e-3"``).
    pricing_rows:
        Pricing table to search.  When ``None`` (the default),
        :data:`~arnold.pipeline.media_cost.DEFAULT_MEDIA_PRICING` is used.

    Returns
    -------
    tuple of ``CostResult``
        One cost line per ``MediaUsage`` item found in hook metadata.
        Returns an empty tuple ``()`` when ``hook_metadata`` has no
        ``'media_usage'`` key.

    Error handling
    --------------
    Malformed ``hook_metadata['media_usage']`` (e.g. a value that is not
    ``None``, ``MediaUsage``, or a list/tuple of ``MediaUsage``) is handled
    **nonfatally**: the function catches ``TypeError`` and returns a single
    ``CostResult`` with ``status='unknown'`` and a descriptive note.  No
    exception propagates to the caller, so a misconfigured adapter cannot
    abort a pipeline run.

    When *provider* or *model* is ``None`` or empty, the function returns
    an empty tuple.

    Notes
    -----
    This is an **opt-in** helper.  When a hook implementation does not call
    it, or when only :class:`NullExecutorHooks` is active, no media
    accounting occurs and runs are unchanged.
    """
    from arnold.pipeline.cost_types import CostResult

    # Guard: no provider/model → nothing to price.
    if not provider or not model:
        return ()

    # Read and normalise media_usage from hook metadata.
    raw = result.hook_metadata.get("media_usage") if result.hook_metadata else None
    if raw is None:
        return ()

    try:
        usage = media_usage_from_hook_metadata(raw)
    except TypeError as exc:
        return (
            CostResult(
                amount_usd=None,
                status="unknown",
                source="none",
                label="n/a",
                notes=(
                    f"Malformed hook_metadata['media_usage'] for "
                    f"provider={provider!r} model={model!r}: {exc}",
                ),
            ),
        )

    if not usage:
        return ()

    if pricing_rows is None:
        from arnold.pipeline.media_cost import DEFAULT_MEDIA_PRICING

        pricing_rows = DEFAULT_MEDIA_PRICING

    return compute_media_cost(provider, model, usage, pricing_rows=pricing_rows)
