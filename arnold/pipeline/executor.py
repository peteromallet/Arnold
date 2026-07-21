"""Minimal neutral graph executor for Arnold pipelines.

Exposes a single ``run_pipeline`` function that walks a ``Pipeline``'s
stages by following ``Edge`` labels, invokes each stage's ``Step.run``
Protocol, applies ``StateDelta`` patches to the working state, and
accepts an optional ``OperationRegistry``.

``ParallelStage`` fan-out is implemented via :class:`concurrent.futures.ThreadPoolExecutor`.
Each step receives an isolated :class:`StepContext` snapshot.  Results
are collected in submission order and passed through the stage's
``join`` callable (via ``hooks.join_parallel_results``), which returns
a single :class:`StepResult` for dispatch.

Hook protocol
-------------

Pass an :class:`~arnold.execution.hooks.ExecutorHooks` implementation to
inject behaviour at 12 documented insertion points without importing
product-specific pipeline code from inside ``arnold/pipeline/``.  Omitting *hooks* (or
passing ``None``) produces byte-for-byte identical behaviour to the
pre-hooks path via :class:`~arnold.execution.hooks.NullExecutorHooks`.

Walk-loop terminal exits
------------------------

Exactly three terminal conditions exist:

1. **halt** — ``result.next == 'halt'`` or ``edge.target == 'halt'``.
2. **should_suspend** — ``hooks.should_suspend(stage, state, result)``
   returns ``(True, reason)``.
3. **should_halt_loop** — ``hooks.should_halt_loop(stage, state, iter)``
   returns ``(True, reason)`` (checked pre-step).

All three call ``hooks.on_stage_complete`` then return the working
envelope.  The halt reason is stashed on the hooks instance.

Boundary discipline
-------------------

No product-specific pipeline imports.  No forbidden vocabulary literals.
"""

from __future__ import annotations

import concurrent.futures
import dataclasses
import json
import os
from pathlib import Path
from typing import Any, Callable, Mapping

from arnold.execution.hooks import ExecutorHooks, NullExecutorHooks
from arnold.pipeline.native.routing import (
    RUNTIME_GRAPH,
    RUNTIME_NATIVE,
    RuntimeOwner,
    normalize_runtime_owner,
)
from arnold.pipeline.resume import read_resume_cursor
from arnold.pipeline.resume import classify_resume_cursor_payload
from arnold.pipeline.resume_validation import reverify_resume_produces
from arnold.pipeline.routing import RoutingError, resolve_edge
from arnold.pipeline.schema_registry import ContractSchemaRegistry
from arnold.pipeline.state import StateDelta, apply_delta
from arnold.pipeline.types import (
    ContractResult,
    ContractStatus,
    HumanSuspension,
    ParallelStage,
    Pipeline,
    Stage,
    StepContext,
    StepResult,
)
from arnold.runtime.envelope import RuntimeEnvelope
from arnold.execution.operations import NullOperationRegistry, OperationRegistry
from arnold.workflow.native_wbc import begin_native_wbc_attempt


def _global_runtime_kill_switch() -> RuntimeOwner | None:
    """Return an explicit runtime owner from the global kill-switch env var.

    ``ARNOLD_PIPELINE_RUNTIME=graph`` forces graph execution;
    ``ARNOLD_PIPELINE_RUNTIME=native`` forces native execution when capable.
    Returns ``None`` when the switch is unset or unrecognised.
    """

    value = os.environ.get("ARNOLD_PIPELINE_RUNTIME", "").strip().lower()
    if value in {RUNTIME_GRAPH, RUNTIME_NATIVE}:
        return value  # type: ignore[return-value]
    return None


def _should_dispatch_native(
    pipeline: Pipeline,
    marker: RuntimeOwner | None,
) -> bool:
    """Decide whether a native-capable pipeline should run natively.

    Explicit graph markers win, explicit native markers select native when
    capable, and native-capable pipelines default to native.  The deprecated
    ``ARNOLD_NATIVE_RUNTIME`` env var is ignored.
    """

    kill = _global_runtime_kill_switch()
    if kill == RUNTIME_GRAPH:
        return False
    if kill == RUNTIME_NATIVE:
        marker = RUNTIME_NATIVE

    if marker == RUNTIME_GRAPH:
        return False

    native_bundle = _find_native_bundle(pipeline)
    if native_bundle is None:
        return False

    if marker == RUNTIME_NATIVE:
        return True

    return True


def _run_native_dispatched(
    pipeline: Pipeline,
    native_bundle: Any,
    *,
    initial_state: Mapping[str, Any],
    envelope: RuntimeEnvelope,
    initial_context: StepContext | None,
    resume: bool,
    schema_registry: ContractSchemaRegistry | None = None,
    human_input: Mapping[str, Any] | str | None = None,
) -> Any:
    """Delegate execution to the native runtime or a runner adapter."""
    from arnold.pipeline.native.ir import NativeProgram
    from arnold.pipeline.native.runtime import run_native_pipeline

    attempt = begin_native_wbc_attempt(
        envelope.artifact_root,
        producer_family="arnold_pipeline",
        surface="executor.native_dispatch",
        run_id=envelope.run_id,
        plugin_id=envelope.plugin_id,
        manifest_hash=envelope.manifest_hash,
        subject={"entry": pipeline.entry, "resume": resume},
        metadata={"native_bundle": type(native_bundle).__name__},
        start_payload={"resume": resume},
    )

    # ``pipeline.native_program`` is the primary contract.  Bare
    # NativeProgram resource bundles remain supported for transitional
    # callers that predate the field.
    program = _find_native_program(pipeline)
    if program is None and isinstance(native_bundle, NativeProgram):
        program = native_bundle

    kwargs: dict[str, Any] = {
        "artifact_root": envelope.artifact_root,
        "initial_state": dict(initial_state),
        "resume": resume,
        "initial_envelope": envelope,
    }
    if schema_registry is not None:
        kwargs["schema_registry"] = schema_registry
    if human_input is not None:
        kwargs["human_input"] = human_input
    if isinstance(native_bundle, NativeProgram):
        try:
            attempt.effect(
                "dispatch_runtime",
                {"mode": "program", "program": native_bundle.name, "resume": resume},
            )
            result = run_native_pipeline(native_bundle, **kwargs)
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

    # Runner adapter path: forward the full
    # caller context so adapters can reconstruct pipeline-specific context.
    kwargs["program"] = program
    kwargs.setdefault("schema_registry", None)
    kwargs["initial_context"] = initial_context
    try:
        attempt.effect(
            "dispatch_runtime",
            {"mode": "adapter", "adapter": type(native_bundle).__name__, "resume": resume},
        )
        result = native_bundle.run_native_pipeline(**kwargs)
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


def _resolve_executor_marker(
    initial_state: Mapping[str, Any],
    artifact_root: str | Path,
) -> RuntimeOwner | None:
    """Return runtime owner using the neutral executor marker precedence."""
    persisted_state = _read_persisted_state(artifact_root)

    persisted = _modern_runtime_owner_from_state(persisted_state)
    if persisted is not None:
        return persisted

    in_memory = _modern_runtime_owner_from_state(initial_state)
    if in_memory is not None:
        return in_memory

    legacy_persisted = _legacy_runtime_owner_from_state(persisted_state)
    if legacy_persisted is not None:
        return legacy_persisted

    return _legacy_runtime_owner_from_state(initial_state)


def _resolve_resume_marker(
    initial_state: Mapping[str, Any],
    artifact_root: str | Path,
    cursor_data: Mapping[str, Any] | None,
) -> RuntimeOwner | None:
    """Return runtime owner for resume, including cursor ownership.

    Explicit graph runtime ownership remains authoritative.  Otherwise, the
    resume cursor can pin graph-born legacy runs to graph or native-born runs
    to native.  If there is no usable cursor marker, normal executor defaults
    apply.
    """

    marker = _resolve_executor_marker(initial_state, artifact_root)
    if marker == RUNTIME_GRAPH:
        return RUNTIME_GRAPH
    if marker == RUNTIME_NATIVE:
        return RUNTIME_NATIVE

    cursor_kind = classify_resume_cursor_payload(cursor_data)
    if cursor_kind == "graph":
        return RUNTIME_GRAPH
    if cursor_kind == "native":
        return RUNTIME_NATIVE
    return marker


def _read_persisted_state(artifact_root: str | Path) -> Mapping[str, Any] | None:
    """Read ``<artifact_root>/state.json`` when it contains a JSON object."""
    state_path = Path(artifact_root) / "state.json"
    if not state_path.is_file():
        return None
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if isinstance(payload, Mapping):
        return payload
    return None


def _modern_runtime_owner_from_state(
    state: Mapping[str, Any] | None,
) -> RuntimeOwner | None:
    """Resolve modern runtime markers from one state object."""
    if not isinstance(state, Mapping):
        return None

    runtime_envelope = state.get("runtime_envelope")
    if isinstance(runtime_envelope, Mapping):
        owner = normalize_runtime_owner(runtime_envelope.get("runtime"))
        if owner is not None:
            return owner

    meta = state.get("meta")
    if isinstance(meta, Mapping):
        owner = normalize_runtime_owner(meta.get("executor"))
        if owner is not None:
            return owner

    return None


def _legacy_runtime_owner_from_state(
    state: Mapping[str, Any] | None,
) -> RuntimeOwner | None:
    """Resolve deprecated ``_native_execution`` compatibility aliases."""
    if not isinstance(state, Mapping):
        return None

    native_alias = state.get("_native_execution")
    if native_alias is True:
        return RUNTIME_NATIVE
    if native_alias is False:
        return RUNTIME_GRAPH
    return None


def _find_native_bundle(pipeline: Pipeline) -> Any | None:
    """Locate native execution evidence on *pipeline*.

    ``pipeline.native_program`` is preferred over legacy bare
    :class:`~arnold.pipeline.native.ir.NativeProgram` resource bundles.
    Runner-like adapters remain supported so callers can supply a custom
    dispatch wrapper; adapters receive the
    first-class native program explicitly in :func:`_run_native_dispatched`.
    """
    from arnold.pipeline.native.ir import NativeProgram

    program = _find_native_program(pipeline)
    for bundle in getattr(pipeline, "resource_bundles", ()) or ():
        if hasattr(bundle, "run_native_pipeline"):
            return bundle
        if program is None and isinstance(bundle, NativeProgram):
            program = bundle
    return program


def _find_native_program(pipeline: Pipeline) -> Any | None:
    """Return the first-class or transitional native program for *pipeline*."""
    from arnold.pipeline.native.ir import NativeProgram

    native_program = getattr(pipeline, "native_program", None)
    if isinstance(native_program, NativeProgram):
        return native_program

    for bundle in getattr(pipeline, "resource_bundles", ()) or ():
        if isinstance(bundle, NativeProgram):
            return bundle
    return None
from arnold.kernel.fold import (
    fold_journal,
    last_state_snapshot_projector,
    read_event_journal,
)

__all__ = [
    "MediaCostAccumulator",
    "ParallelSafePredicate",
    "DEFAULT_PARALLEL_SAFE",
    "StepIOEnforcementError",
    "run_pipeline",
    "run_pipeline_resume",
]


# ---------------------------------------------------------------------------
# Media cost accumulator (AR3 — opt-in, hooks-compatible)
# ---------------------------------------------------------------------------


class MediaCostAccumulator:
    """Opt-in accumulator for media cost lines from step hook metadata.

    Hook implementations can instantiate this as an attribute and call
    :meth:`account` from their :meth:`~arnold.execution.hooks.ExecutorHooks.on_step_end`
    override.  It delegates to
    :func:`~arnold.execution.hooks.account_media_cost_from_result` and
    appends the returned ``CostResult`` lines to :attr:`lines`.

    When a hook implementation does **not** use this accumulator, no media
    accounting occurs and runs are unchanged (opt-in).

    Usage::

        class MyHooks(NullExecutorHooks):
            def __init__(self):
                super().__init__()
                self.media = MediaCostAccumulator()

            def on_step_end(self, stage, ctx, result):
                self.media.account(result, provider="openai", model="dall-e-3")
                return result

        hooks = MyHooks()
        run_pipeline(pipeline, initial_state, envelope, hooks=hooks)
        print(hooks.media.lines)  # list[CostResult]
    """

    def __init__(self) -> None:
        self.lines: list[Any] = []

    def account(
        self,
        result: StepResult,
        *,
        provider: str,
        model: str,
        pricing_rows: Any = None,
    ) -> None:
        """Account media usage from *result* and append cost lines.

        Parameters are forwarded to
        :func:`~arnold.execution.hooks.account_media_cost_from_result`.
        """
        from arnold.execution.hooks import account_media_cost_from_result

        cost_lines = account_media_cost_from_result(
            result,
            provider=provider,
            model=model,
            pricing_rows=pricing_rows,
        )
        self.lines.extend(cost_lines)


class StepIOEnforcementError(RuntimeError):
    """Raised when a typed step-IO seam is blocked under ``enforce`` policy.

    The walk loop raises this BEFORE merging ``result.outputs`` or
    ``state_patch`` into working state, so the executor's state is unchanged
    when an enforce-block fires.
    """

    def __init__(self, message: str, *, author_diagnostic: Any = None) -> None:
        super().__init__(message)
        self.author_diagnostic = author_diagnostic


def _author_diagnostic_payload(author_diagnostic: Any) -> Any:
    """Return the stable author-facing diagnostic payload for exceptions."""

    if author_diagnostic is None:
        return None
    message = getattr(author_diagnostic, "message", None)
    failure_code = getattr(author_diagnostic, "failure_code", None)
    if message is None or failure_code is None:
        return author_diagnostic
    return {
        "code": "typed_contract_blocked",
        "failure_code": str(failure_code),
        "message": str(message),
        "producer_stage": str(getattr(author_diagnostic, "producer_stage", "")),
        "consumer_stage": str(getattr(author_diagnostic, "consumer_stage", "")),
        "seam_id": getattr(author_diagnostic, "seam_id", None),
        "logical_type": str(getattr(author_diagnostic, "logical_type", "unknown")),
        "schema_version": str(getattr(author_diagnostic, "schema_version", "unknown")),
        "suggested_author_action": str(
            getattr(author_diagnostic, "suggested_author_action", "")
        ),
        "detail": str(getattr(author_diagnostic, "detail", "")),
    }


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
    hooks: ExecutorHooks | None = None,
    initial_context: StepContext | None = None,
) -> RuntimeEnvelope | Any:
    """Execute a pipeline by walking edges and invoking each step.

    Execution begins at ``pipeline.entry``.  For each stage:

    1. Check ``hooks.should_halt_loop`` (pre-step terminal exit 3).
    2. Build a :class:`~arnold.pipeline.types.StepContext` from the
       current working state and ``envelope.artifact_root``.
    3. Call ``hooks.on_step_start`` → may rewrite ctx.
    4. Call ``stage.step.run(ctx)`` → :class:`~arnold.pipeline.types.StepResult`.
    5. Call ``hooks.on_step_end`` → may rewrite result.
    6. Check ``hooks.should_suspend`` (post-step terminal exit 2).
    7. Merge ``result.outputs`` into working state.
    8. Call ``hooks.merge_state`` with the state patch.
    9. Follow the edge whose ``label`` matches ``result.next`` via
       ``resolve_edge``.  On ``RoutingError``, consult
       ``hooks.resolve_routing_fallback``.
    10. Halt terminal exit 1 fires when ``edge is None`` or
        ``edge.target == 'halt'``.
    11. On normal continuation: fire ``hooks.on_edge_traverse`` then
        ``hooks.on_stage_complete``, then advance ``current_name``.

    All three terminal exits call ``hooks.on_stage_complete`` and stash
    the halt reason on the hooks instance before returning the envelope.

    ``ParallelStage`` fan-out: each step runs concurrently in a
    :class:`~concurrent.futures.ThreadPoolExecutor`.  ``hooks.on_step_start``
    is called per child before submission; ``hooks.on_step_end`` /
    ``hooks.on_step_error`` after each future completes;
    ``hooks.join_parallel_results`` merges the ordered child list.

    ``registry`` is forwarded to future operation-dispatch hooks;
    ``None`` is equivalent to
    :class:`~arnold.runtime.operations.NullOperationRegistry`.

    Returns the ``envelope`` unchanged (or the hooks-provided return value
    when custom hooks are active).
    """
    if registry is None:
        registry = NullOperationRegistry()

    if parallel_safe is _NO_PARALLEL_SAFE:
        parallel_safe = DEFAULT_PARALLEL_SAFE

    _hooks: ExecutorHooks = hooks if hooks is not None else NullExecutorHooks()

    marker = _resolve_executor_marker(initial_state, envelope.artifact_root)
    if _should_dispatch_native(pipeline, marker):
        native_bundle = _find_native_bundle(pipeline)
        if native_bundle is not None:
            return _run_native_dispatched(
                pipeline,
                native_bundle,
                initial_state=initial_state,
                envelope=envelope,
                initial_context=initial_context,
                resume=False,
            )

    # When custom hooks are active, delegate parallel-safety to the hooks
    # instance; otherwise honour the caller's parallel_safe predicate.
    _eff_parallel_safe: ParallelSafePredicate = (
        _hooks.is_parallel_safe if hooks is not None else parallel_safe  # type: ignore[assignment]
    )

    return _step_at(
        pipeline=pipeline,
        initial_state=initial_state,
        envelope=envelope,
        registry=registry,
        eff_parallel_safe=_eff_parallel_safe,
        hooks=_hooks,
        initial_context=initial_context,
        entry_override=None,
    )


def run_pipeline_resume(
    pipeline: Pipeline,
    initial_state: Mapping[str, Any],
    envelope: RuntimeEnvelope,
    *,
    resume_cursor: "dict[str, Any] | str | None" = None,
    human_input: "dict[str, Any] | None" = None,
    suspension: HumanSuspension | None = None,
    schema_registry: ContractSchemaRegistry | None = None,
    registry: OperationRegistry | None = None,
    hooks: ExecutorHooks | None = None,
    initial_context: StepContext | None = None,
) -> RuntimeEnvelope | Any:
    """Resume pipeline execution from a prior cursor.

    Resolves *resume_cursor* (dict with ``stage`` key, bare string stage
    name, or ``None`` → read from ``<envelope.artifact_root>/resume_cursor.json``
    via :func:`arnold.pipeline.resume.read_resume_cursor`), reconstructs
    state by replaying the event journal, and re-enters the walk loop at
    the cursor stage via the ``entry_override`` parameter of
    :func:`_step_at`.

    State reconstruction
    --------------------
    Events in ``events.ndjson`` under ``envelope.artifact_root`` are
    folded with ``kind_filter='state_written'`` and
    :func:`~arnold.runtime.wal_fold.last_state_snapshot_projector`.
    The final state is ``{**initial_state, **replayed}`` (replayed wins
    on conflict).

    Cursor formats
    --------------
    * ``dict {"stage": str, "input": dict|None}`` — explicit stage + seed inputs.
    * Bare string ``stage_name`` — treated as ``{"stage": stage_name, "input": None}``.
    * ``None`` — read from ``<artifact_root>/resume_cursor.json``.

    The first stage's ``ctx.inputs`` is seeded with
    ``cursor.get('input') or {'human_input': human_input}``
    (merged into state before the walk, so the entry stage sees them via
    :func:`_build_ctx`).
    """
    attempt = begin_native_wbc_attempt(
        envelope.artifact_root,
        producer_family="arnold_pipeline",
        surface="executor.resume",
        run_id=envelope.run_id,
        plugin_id=envelope.plugin_id,
        manifest_hash=envelope.manifest_hash,
        subject={"entry": pipeline.entry},
        metadata={"entrypoint": "arnold.pipeline.executor.run_pipeline_resume"},
    )

    # ── Resolve cursor ──────────────────────────────────────────────────
    if resume_cursor is None:
        cursor_data: "dict[str, Any] | None" = read_resume_cursor(envelope.artifact_root)
    elif isinstance(resume_cursor, str):
        cursor_data = {"stage": resume_cursor, "input": None}
    else:
        cursor_data = dict(resume_cursor)

    entry_stage: str = pipeline.entry
    cursor_input: "dict[str, Any]" = {}
    if cursor_data is not None:
        stage_val = cursor_data.get("stage")
        if isinstance(stage_val, str) and stage_val:
            entry_stage = stage_val
        input_val = cursor_data.get("input")
        if isinstance(input_val, dict):
            cursor_input = input_val
    attempt.effect(
        "resume_cursor_loaded",
        {"stage": entry_stage, "cursor_present": cursor_data is not None},
    )

    # ── Reconstruct state via event journal fold ────────────────────────
    events = read_event_journal(envelope.artifact_root)
    replayed = fold_journal(
        events,
        kind_filter="state_written",
        projector=last_state_snapshot_projector,
        initial=None,
    )
    merged: "dict[str, Any]" = {
        **dict(initial_state),
        **(replayed if isinstance(replayed, dict) else {}),
    }

    # ── Seed first-stage inputs ─────────────────────────────────────────
    seed: "dict[str, Any]" = cursor_input or (
        {"human_input": human_input} if human_input is not None else {}
    )
    if seed:
        merged.update(seed)

    # ── Resolve hooks and parallel-safety ──────────────────────────────
    if registry is None:
        registry = NullOperationRegistry()
    _hooks: ExecutorHooks = hooks if hooks is not None else NullExecutorHooks()
    _eff_parallel_safe: ParallelSafePredicate = (
        _hooks.is_parallel_safe if hooks is not None else DEFAULT_PARALLEL_SAFE  # type: ignore[assignment]
    )

    marker = _resolve_resume_marker(merged, envelope.artifact_root, cursor_data)
    if _should_dispatch_native(pipeline, marker):
        native_bundle = _find_native_bundle(pipeline)
        if native_bundle is not None:
            result = _run_native_dispatched(
                pipeline,
                native_bundle,
                initial_state=merged,
                envelope=envelope,
                initial_context=initial_context,
                resume=True,
                schema_registry=schema_registry,
                human_input=human_input,
            )
            attempt.terminal(
                status="completed",
                outcome="native_resume",
                payload={"result_type": type(result).__name__},
            )
            return result

    wrapped_hooks = _wrap_resume_reverify_hooks(
        hooks=_hooks,
        target_stage=entry_stage,
        suspension=suspension,
        schema_registry=schema_registry,
    )

    result = _step_at(
        pipeline=pipeline,
        initial_state=merged,
        envelope=envelope,
        registry=registry,
        eff_parallel_safe=_eff_parallel_safe,
        hooks=wrapped_hooks,
        initial_context=initial_context,
        entry_override=entry_stage,
    )
    attempt.terminal(
        status="completed",
        outcome="graph_resume",
        payload={"result_type": type(result).__name__, "entry_stage": entry_stage},
    )
    return result


def _step_at(
    pipeline: Pipeline,
    initial_state: Mapping[str, Any],
    envelope: RuntimeEnvelope,
    registry: OperationRegistry | None,
    *,
    eff_parallel_safe: ParallelSafePredicate,
    hooks: ExecutorHooks,
    initial_context: StepContext | None,
    entry_override: str | None,
) -> RuntimeEnvelope | Any:
    """Walk the pipeline from *entry_override* (or ``pipeline.entry`` when ``None``).

    Internal helper shared by :func:`run_pipeline` and
    :func:`run_pipeline_resume`.  Callers are responsible for resolving
    hooks, parallel-safe predicate, and the entry stage before calling.

    The ``should_suspend`` branch (terminal exit 2) keeps the
    ``(bool, str|None)`` signature; suspensions ride in
    ``result.contract_result``.
    """
    state: Any = dict(initial_state)
    current_name: str | None = entry_override if entry_override is not None else pipeline.entry
    owned_keys: frozenset[str] = frozenset()
    iteration: int = 0
    _hook_extensions: Mapping[str, Any] = (
        initial_context.hook_extensions if initial_context is not None else {}
    )

    while current_name is not None:
        stage = pipeline.stages.get(current_name)
        if stage is None:
            break

        # Build pre-step context (used for should_halt_loop and parallel path)
        ctx = _build_ctx(state, envelope, _hook_extensions)

        # ── Terminal exit 3: should_halt_loop (pre-step) ──────────────
        halt_loop, halt_reason = hooks.should_halt_loop(stage, state, iteration)
        if halt_loop:
            _stash_halt_reason(hooks, halt_reason)
            hooks.on_stage_complete(stage, ctx, StepResult(), state, owned_keys)
            break

        if isinstance(stage, ParallelStage):
            result = _run_parallel_stage(
                stage, state, envelope, eff_parallel_safe, hooks,
                hook_extensions=_hook_extensions,
            )
        else:
            ctx = hooks.on_step_start(stage, ctx)
            try:
                result = stage.step.run(ctx)
            except BaseException as exc:
                hooks.on_step_error(stage, ctx, exc)
                raise
            result = hooks.on_step_end(stage, ctx, result)

        # ── Terminal exit 2: should_suspend ───────────────────────────
        suspend, halt_reason = hooks.should_suspend(stage, state, result)
        if suspend:
            _stash_halt_reason(hooks, halt_reason)
            hooks.on_stage_complete(stage, ctx, result, state, owned_keys)
            return envelope

        # ── Typed step-IO enforcement (generic executor path) ────────
        # Runs BEFORE the outputs/state merge so state is unchanged when
        # an enforce-block fires. Product-specific compatibility executors
        # can have independent enforcement and do not route through this path.
        _enforce_typed_step_io_handoff(
            pipeline=pipeline,
            stage=stage,
            result=result,
            hook_extensions=_hook_extensions,
        )

        if result.outputs:
            if isinstance(state, dict):
                state.update(result.outputs)
            else:
                state = dict(result.outputs)

        # Publish the producer's ContractResult into the routing surface so
        # downstream consumers can read the typed carrier via
        # ``StepContext.contract_results`` (snapshotted in _build_ctx).
        if result.contract_result is not None and isinstance(state, dict):
            published = state.get("__contract_results__")
            if not isinstance(published, dict):
                published = {}
                state["__contract_results__"] = published
            published[stage.name] = result.contract_result

        if result.state_patch:
            delta = StateDelta(patches=(dict(result.state_patch),))
            state, owned_keys = hooks.merge_state(stage, state, delta, owned_keys)

        # ── Route via the shared policy-neutral resolver ──────────────
        try:
            edge = resolve_edge(stage, result, result.verdict, stage.edges)
        except RoutingError as exc:
            fallback = hooks.resolve_routing_fallback(stage, result, stage.edges, exc)
            if fallback is not None:
                edge = fallback
            else:
                # For simple stages (no declared vocabularies), a missing
                # normal-label edge terminates gracefully — backward compat
                # with pre-T4 lenient dispatch.
                if not stage.decision_vocabulary and not stage.override_vocabulary:
                    break
                # Stages with declared vocabularies propagate RoutingError.
                raise

        # ── Terminal exit 1: halt ─────────────────────────────────────
        if edge is None:
            _stash_halt_reason(hooks, "halt")
            hooks.on_stage_complete(stage, ctx, result, state, owned_keys)
            break

        if edge.target == "halt":
            _stash_halt_reason(hooks, "halt")
            hooks.on_stage_complete(stage, ctx, result, state, owned_keys)
            break

        # ── Normal continuation ───────────────────────────────────────
        consumer_stage = pipeline.stages.get(edge.target)
        if consumer_stage is not None:
            hooks.on_edge_traverse(stage, consumer_stage, ctx, result)
        hooks.on_stage_complete(stage, ctx, result, state, owned_keys)
        current_name = edge.target
        iteration += 1

    return envelope


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _build_ctx(
    state: Any,
    envelope: RuntimeEnvelope,
    hook_extensions: Mapping[str, Any] | None = None,
) -> StepContext:
    """Construct a :class:`StepContext` snapshot from *state* and *envelope*."""
    state_dict = dict(state) if isinstance(state, dict) else state
    contract_results = None
    if isinstance(state_dict, dict):
        published = state_dict.get("__contract_results__")
        if isinstance(published, Mapping):
            contract_results = dict(published)
    return StepContext(
        artifact_root=envelope.artifact_root,
        state=state_dict,
        inputs=dict(state_dict) if isinstance(state_dict, dict) else {},
        hook_extensions=dict(hook_extensions) if hook_extensions else {},
        contract_results=contract_results,
    )


def _wrap_resume_reverify_hooks(
    *,
    hooks: ExecutorHooks,
    target_stage: str,
    suspension: HumanSuspension | None,
    schema_registry: ContractSchemaRegistry | None,
) -> ExecutorHooks:
    """Inject resume re-verification into the first resumed stage only.

    The wrapper is inert when *suspension* is ``None`` or the declaration is
    absent. Valid re-verification rewrites the first resumed ``StepResult``
    before merge; invalid ``resuspend`` requests ride the existing
    ``should_suspend`` terminal path; invalid ``fail`` requests raise the
    existing pre-merge enforcement surface.
    """
    if suspension is None:
        return hooks

    class _ResumeReverifyHooks(NullExecutorHooks):
        def __init__(self) -> None:
            self._consumed = False

        def on_step_start(
            self,
            stage: Stage | ParallelStage,
            ctx: StepContext,
        ) -> StepContext:
            return hooks.on_step_start(stage, ctx)

        def on_step_end(
            self,
            stage: Stage | ParallelStage,
            ctx: StepContext,
            result: StepResult,
        ) -> StepResult:
            result = hooks.on_step_end(stage, ctx, result)
            if self._consumed or stage.name != target_stage:
                return result

            self._consumed = True
            verified = reverify_resume_produces(
                suspension,
                artifact_root=ctx.artifact_root,
                schema_registry=schema_registry,
                producer_stage=stage.name,
            )
            if verified.outcome == "no_op":
                return result

            if verified.outcome == "invalid":
                if (
                    verified.declaration is not None
                    and verified.declaration.invalid_policy == "fail"
                ):
                    detail = "resume re-verification failed"
                    if isinstance(verified.diagnostic, Mapping):
                        detail = str(verified.diagnostic.get("detail") or detail)
                    raise StepIOEnforcementError(
                        detail,
                        author_diagnostic=verified.diagnostic,
                    )
                return _resume_invalid_result(result, suspension, verified.diagnostic)

            authoritative_payload = _load_resume_artifact_payload(
                verified.resolved_artifact_path,
            )
            return _resume_valid_result(
                stage_name=stage.name,
                result=result,
                declaration=verified.declaration,
                authoritative_payload=authoritative_payload,
            )

        def on_step_error(
            self,
            stage: Stage | ParallelStage,
            ctx: StepContext,
            exc: BaseException,
        ) -> None:
            hooks.on_step_error(stage, ctx, exc)

        def merge_state(
            self,
            stage: Stage | ParallelStage,
            current_state: Any,
            patch: StateDelta,
            owned_keys: frozenset[str],
        ) -> tuple[Any, frozenset[str]]:
            return hooks.merge_state(stage, current_state, patch, owned_keys)

        def join_envelope(
            self,
            stage: Stage | ParallelStage,
            current_envelope: Any,
            step_envelope: Any,
        ) -> Any:
            return hooks.join_envelope(stage, current_envelope, step_envelope)

        def join_parallel_results(
            self,
            stage: ParallelStage,
            ctx: StepContext,
            child_results: Any,
        ) -> StepResult:
            return hooks.join_parallel_results(stage, ctx, child_results)

        def should_suspend(
            self,
            stage: Stage | ParallelStage,
            state: Any,
            result: StepResult,
        ) -> tuple[bool, str | None]:
            suspend, halt_reason = hooks.should_suspend(stage, state, result)
            if suspend:
                return suspend, halt_reason
            metadata = result.hook_metadata or {}
            if metadata.get("resume_reverify_invalid"):
                return True, "resume_reverify_invalid"
            return False, None

        def should_halt_loop(
            self,
            stage: Stage | ParallelStage,
            state: Any,
            iteration: int,
        ) -> tuple[bool, str | None]:
            return hooks.should_halt_loop(stage, state, iteration)

        def resolve_routing_fallback(
            self,
            stage: Stage | ParallelStage,
            result: StepResult,
            edges: tuple[Any, ...],
            error: RoutingError,
        ) -> Any:
            return hooks.resolve_routing_fallback(stage, result, edges, error)

        def on_edge_traverse(
            self,
            producer_stage: Stage | ParallelStage,
            consumer_stage: Stage | ParallelStage,
            ctx: StepContext,
            result: StepResult,
        ) -> None:
            hooks.on_edge_traverse(producer_stage, consumer_stage, ctx, result)

        def on_stage_complete(
            self,
            stage: Stage | ParallelStage,
            ctx: StepContext,
            result: StepResult,
            state: Any,
            owned_keys: frozenset[str],
        ) -> None:
            hooks.on_stage_complete(stage, ctx, result, state, owned_keys)

        def is_parallel_safe(self, step: Any) -> bool:
            return hooks.is_parallel_safe(step)

    return _ResumeReverifyHooks()


def _resume_invalid_result(
    result: StepResult,
    suspension: HumanSuspension,
    diagnostic: Mapping[str, Any] | None,
) -> StepResult:
    contract = ContractResult(
        status=ContractStatus.SUSPENDED,
        suspension=suspension,
        payload={"diagnostic": dict(diagnostic)} if isinstance(diagnostic, Mapping) else {},
    )
    metadata = dict(result.hook_metadata)
    metadata["resume_reverify_invalid"] = True
    return dataclasses.replace(
        result,
        outputs={},
        state_patch={},
        contract_result=contract,
        hook_metadata=metadata,
    )


def _resume_valid_result(
    *,
    stage_name: str,
    result: StepResult,
    declaration: Any,
    authoritative_payload: Mapping[str, Any],
) -> StepResult:
    output_key = stage_name
    if declaration is not None and getattr(declaration, "port", None):
        output_key = str(getattr(declaration, "port"))
    outputs = dict(result.outputs)
    outputs[output_key] = authoritative_payload
    if result.contract_result is None:
        contract = ContractResult(
            status=ContractStatus.COMPLETED,
            payload=dict(authoritative_payload),
        )
    else:
        contract = dataclasses.replace(
            result.contract_result,
            status=ContractStatus.COMPLETED,
            suspension=None,
            payload=dict(authoritative_payload),
        )
    return dataclasses.replace(
        result,
        outputs=outputs,
        contract_result=contract,
    )


def _load_resume_artifact_payload(path: str | None) -> Mapping[str, Any]:
    if not isinstance(path, str) or not path:
        raise AssertionError("resume re-verification succeeded without an artifact path")
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, Mapping):
        raise AssertionError("resume re-verification payload must be a JSON object")
    return dict(data)


def _find_consumers_for_producer_port(
    pipeline: Pipeline,
    producer_step: str,
    producer_port: str,
) -> list[tuple[str, str]]:
    """Return ``[(consumer_step, consumer_port), ...]`` for *(producer_step, producer_port)*.

    Iterates ``pipeline.binding_map.items()`` and yields **every** consumer
    bound to the producer pair (multi-consumer aware: not first-match).
    Returns ``[]`` when ``binding_map`` is missing or no consumer is bound.
    """
    binding_map = getattr(pipeline, "binding_map", None)
    if not binding_map:
        return []
    target = (producer_step, producer_port)
    return [
        (consumer_step, consumer_port)
        for (consumer_step, consumer_port), producer in binding_map.items()
        if producer == target
    ]


def _enforce_typed_step_io_handoff(
    *,
    pipeline: Pipeline,
    stage: Any,
    result: StepResult,
    hook_extensions: Mapping[str, Any],
) -> None:
    """Run typed step-IO seam enforcement for *(stage → bound consumers)*.

    Falls through (no-op) when any of the following holds:
      * ``pipeline.binding_map`` is missing / empty;
      * the stage declares no ``produces`` ports;
      * the producer's ``StepResult`` carries no handoff value
        (no ``contract_result`` and no ``outputs[stage.name]``);
      * no consumer is bound to ``(stage.name, port.name)``;
      * either side lacks a typed declaration — handled inside
        ``evaluate_step_io_handoff`` (gradual-typing rule);
      * the resolved policy does not ``enforce`` — warn / shadow / off
        emit telemetry but never raise.

    Raises :class:`StepIOEnforcementError` only when the resolved policy
    enforces AND the typed handoff blocks the write.
    """
    binding_map = getattr(pipeline, "binding_map", None)
    if not binding_map:
        return
    from arnold.pipeline.declaration_lowering import lower_stage_declarations

    produces = tuple(lower_stage_declarations(stage).effective_produces)
    if not produces:
        return

    handoff_value: Any
    if result.contract_result is not None:
        handoff_value = result.contract_result
    else:
        outputs = result.outputs or {}
        stage_name = getattr(stage, "name", None)
        handoff_value = outputs.get(stage_name) if stage_name is not None else None
    if handoff_value is None:
        return

    # Lazy imports to keep the no-typed-pipelines path import-free.
    from arnold.pipeline.step_io_contract import StepIOOperation
    from arnold.pipeline.step_io_handoff import evaluate_step_io_handoff
    from arnold.pipeline.step_io_policy import effective_blocks_write

    policy_data = hook_extensions.get("step_io_policy_data") if hook_extensions else None
    context = hook_extensions.get("step_io_contract_context") if hook_extensions else None
    telemetry_path = hook_extensions.get("step_io_telemetry_path") if hook_extensions else None
    pipeline_id = (
        hook_extensions.get("pipeline_id", "pipeline") if hook_extensions else "pipeline"
    )
    read_lenient_escape = bool(
        hook_extensions.get("step_io_read_lenient_escape") if hook_extensions else False
    )

    for port in produces:
        consumers = _find_consumers_for_producer_port(pipeline, stage.name, port.name)
        if not consumers:
            continue
        for consumer_step, consumer_port_name in consumers:
            consumer_stage = pipeline.stages.get(consumer_step)
            consumer_port_decl = None
            if consumer_stage is not None:
                consumer_consumes = lower_stage_declarations(
                    consumer_stage
                ).effective_consumes
                for ref in consumer_consumes:
                    if getattr(ref, "port_name", None) == consumer_port_name:
                        consumer_port_decl = ref
                        break
            handoff = evaluate_step_io_handoff(
                handoff_value,
                operation=StepIOOperation.WRITE,
                context=context,
                pipeline=pipeline,
                pipeline_id=pipeline_id,
                consumer_step=consumer_step,
                consumer_port=consumer_port_name,
                producer_port=port,
                consumer_port_decl=consumer_port_decl,
                policy_data=policy_data,
                read_lenient_escape=read_lenient_escape,
                artifact=f"{stage.name}.{port.name}",
                telemetry_path=telemetry_path,
                producer_stage=stage.name,
            )
            if effective_blocks_write(handoff.decision, handoff.policy):
                raise StepIOEnforcementError(
                    f"step IO enforced violation at "
                    f"{stage.name}.{port.name}→{consumer_step}.{consumer_port_name}: "
                    f"{handoff.decision.block_reason}",
                    author_diagnostic=_author_diagnostic_payload(
                        handoff.author_diagnostic
                    ),
                )


def _stash_halt_reason(hooks: Any, reason: str | None) -> None:
    """Set ``hooks.halt_reason`` when the attribute exists (NullExecutorHooks pattern)."""
    try:
        hooks.halt_reason = reason
    except (AttributeError, TypeError):
        pass


def _run_serial_stage(
    stage: Stage,
    state: Any,
    envelope: RuntimeEnvelope,
) -> StepResult:
    """Execute a single-step serial stage (no-hooks legacy helper)."""
    ctx = _build_ctx(state, envelope)
    return stage.step.run(ctx)


def _run_parallel_stage(
    stage: ParallelStage,
    state: Any,
    envelope: RuntimeEnvelope,
    parallel_safe: ParallelSafePredicate,
    hooks: ExecutorHooks,
    *,
    max_workers: int | None = None,
    hook_extensions: Mapping[str, Any] | None = None,
) -> StepResult:
    """Fan-out *stage* across its steps concurrently, then join via hooks.

    Each step receives an isolated :class:`StepContext` snapshot.
    ``hooks.on_step_start`` is called per child before submission;
    ``hooks.on_step_end`` / ``hooks.on_step_error`` after each future
    completes; ``hooks.join_parallel_results`` merges the ordered child list.

    Parameters
    ----------
    max_workers:
        Fallback worker count when ``stage.max_workers`` is ``None``.
        Precedence: ``stage.max_workers`` (explicit) > *max_workers*
        (inherited) > ``len(steps)`` (unbounded default).
    """
    steps = stage.steps

    # Guard: reject any step that the parallel-safety predicate marks unsafe.
    for step in steps:
        if not parallel_safe(step):
            raise ValueError(
                f"ParallelStage {stage.name!r}: step {getattr(step, 'name', step)!r} "
                f"is not parallel-safe (rejected by the runtime's parallel_safe "
                f"predicate)"
            )

    # Build isolated context snapshots (one per step).
    state_copy = dict(state) if isinstance(state, dict) else state
    state_dict_copy = dict(state_copy) if isinstance(state_copy, dict) else {}
    _he = dict(hook_extensions) if hook_extensions else {}
    contexts: list[StepContext] = [
        StepContext(
            artifact_root=envelope.artifact_root,
            state=dict(state_copy),
            inputs=dict(state_dict_copy),
            hook_extensions=dict(_he),
        )
        for _ in steps
    ]

    # on_step_start per child before submission.
    contexts = [hooks.on_step_start(stage, ctx) for ctx in contexts]

    # Precedence: explicit stage.max_workers > inherited max_workers > len(steps)
    effective_workers = stage.max_workers
    if effective_workers is None:
        effective_workers = max_workers
    if effective_workers is None:
        effective_workers = max(1, len(steps))

    indexed: dict[int, StepResult] = {}

    with concurrent.futures.ThreadPoolExecutor(max_workers=effective_workers) as pool:
        future_to_index: dict[concurrent.futures.Future[StepResult], int] = {}
        for idx, (step, ctx) in enumerate(zip(steps, contexts)):
            future = pool.submit(step.run, ctx)
            future_to_index[future] = idx

        # on_step_end / on_step_error after each future completes.
        for future in concurrent.futures.as_completed(future_to_index):
            idx = future_to_index[future]
            ctx = contexts[idx]
            try:
                raw_result = future.result()
            except BaseException as exc:
                hooks.on_step_error(stage, ctx, exc)
                raise
            indexed[idx] = hooks.on_step_end(stage, ctx, raw_result)

    child_results: list[StepResult] = [indexed[i] for i in range(len(steps))]

    # Build the shared context for the join callable.
    join_ctx = StepContext(
        artifact_root=envelope.artifact_root,
        state=dict(state_copy),
        inputs=dict(state_dict_copy),
        hook_extensions=dict(_he),
    )
    return hooks.join_parallel_results(stage, join_ctx, child_results)
