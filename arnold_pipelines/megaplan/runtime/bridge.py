"""Bridge adapter: megaplan pipeline executor -> neutral Arnold executor.

Rehomed from ``arnold_pipelines.megaplan._pipeline._bridge`` during the M4
burn-down (T4).

Routes ``demo_judges`` through :func:`arnold.pipeline.runner.run_pipeline`
(canonical neutral walk-loop) while leaving all other pipelines on the
legacy :func:`arnold_pipelines.megaplan._pipeline.executor.run_pipeline`
unchanged.

M1 allowlist: ``_BRIDGED_PIPELINES = {'demo_judges'}`` -- hard cap for M1.
Additions require a dedicated follow-on milestone after bridge-compatibility
is verified for the target pipeline.

Design notes
------------
*SD2*: :func:`_translate_stage` and :func:`_translate_parallel_stage` use
  keyword arguments for neutral ``Stage`` / ``ParallelStage`` construction.
  The megaplan ``Stage`` places ``reads`` / ``writes`` before
  ``decision_vocabulary`` / ``override_vocabulary`` (positions 3-4 vs 10-11),
  while the neutral ``Stage`` reverses that order (positions 3-4 vs 5-6).
  Positional construction would silently misalign these fields; keyword
  construction is mandatory.

*SD3*: ``run_pipeline_dispatch`` routes on a hard-coded
  ``_BRIDGED_PIPELINES`` frozenset.  Non-``demo_judges`` pipelines (e.g.
  ``creative``, ``epic_blitz``) cannot be safely bridged in M1 because
  ``_BridgeStep`` does not yet honor ``_materialize_stage_step`` injection.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

_BRIDGED_PIPELINES: frozenset[str] = frozenset({"demo_judges"})


# ---------------------------------------------------------------------------
# _BridgeStep
# ---------------------------------------------------------------------------


class _BridgeStep:
    """Wraps a megaplan Step for execution under the neutral Arnold executor.

    Translates the neutral :class:`~arnold.pipeline.types.StepContext` into a
    megaplan :class:`~arnold_pipelines.megaplan._pipeline.types.StepContext`
    before dispatch, and converts the returned megaplan
    :class:`~arnold_pipelines.megaplan._pipeline.types.StepResult` back to
    the neutral :class:`~arnold.pipeline.types.StepResult`.

    Megaplan-specific context (``plan_dir``, ``inputs``, ``profile``,
    ``mode``, ``budget``, megaplan ``RunEnvelope``) is conveyed through the
    neutral context's ``hook_extensions`` dict (keyed ``_mp_*``) and
    reconstructed here at dispatch time.

    ``_inner_step`` exposes the original megaplan step for safety checks --
    ``MegaplanExecutorHooks.is_parallel_safe`` unwraps it to test for
    ``InProcessHandlerStep``.
    """

    def __init__(self, inner_step: Any) -> None:
        self._inner_step = inner_step
        self.name: str = inner_step.name
        self.kind: str = inner_step.kind

    def run(self, ctx: Any) -> Any:
        from arnold.runtime.envelope import EMPTY_ENVELOPE
        from arnold_pipelines.megaplan.step_types import StepContext as MpStepContext

        hook_ext: Mapping[str, Any] = ctx.hook_extensions if ctx.hook_extensions else {}
        raw_inputs: dict = dict(hook_ext.get("_mp_inputs") or {})
        # Defensive Path coercion: CLI serialises inputs as strings; convert
        # back to Path so Steps that call Path(ctx.inputs[key]).read_text()
        # see a Path-like value regardless of how the dict was serialised.
        mp_inputs: dict[str, Any] = {
            k: Path(v) if isinstance(v, str) else v for k, v in raw_inputs.items()
        }

        mp_ctx = MpStepContext(
            plan_dir=Path(ctx.artifact_root),
            state=ctx.state,
            profile=hook_ext.get("_mp_profile") or {},
            mode=str(hook_ext.get("_mp_mode") or "code"),
            inputs=mp_inputs,
            budget=hook_ext.get("_mp_budget"),
            envelope=hook_ext.get("_mp_envelope") or EMPTY_ENVELOPE,
        )

        mp_result = self._inner_step.run(mp_ctx)
        return _mp_to_neutral_result(mp_result)


# ---------------------------------------------------------------------------
# Type conversion helpers
# ---------------------------------------------------------------------------


def _mp_to_neutral_result(mp_result: Any) -> Any:
    """Convert a megaplan StepResult to a neutral arnold.pipeline StepResult."""
    from arnold.pipeline.types import PipelineVerdict as NeutralVerdict, StepResult as NeutralResult

    neutral_verdict = None
    if mp_result.verdict is not None:
        mv = mp_result.verdict
        neutral_verdict = NeutralVerdict(
            score=float(mv.score),
            flags=tuple(mv.flags) if mv.flags else (),
            notes=str(mv.notes) if mv.notes else "",
            payload=dict(mv.payload) if mv.payload else {},
            recommendation=mv.recommendation,
            override=mv.override,
        )

    return NeutralResult(
        outputs=dict(mp_result.outputs),
        verdict=neutral_verdict,
        next=mp_result.next,
        state_patch=dict(mp_result.state_patch),
        contract_result=mp_result.contract_result,
    )


def _neutral_to_mp_result(neutral_result: Any, mp_envelope: Any) -> Any:
    """Convert a neutral StepResult to a megaplan StepResult (for join wrappers)."""
    from arnold.pipeline.types import PipelineVerdict as MpVerdict
    from arnold.runtime.envelope import EMPTY_ENVELOPE
    from arnold_pipelines.megaplan.step_types import StepResult as MpResult

    mp_verdict = None
    if neutral_result.verdict is not None:
        nv = neutral_result.verdict
        mp_verdict = MpVerdict(
            score=float(nv.score),
            flags=tuple(nv.flags) if nv.flags else (),
            notes=str(nv.notes) if nv.notes else "",
            payload=dict(nv.payload) if nv.payload else {},
            recommendation=nv.recommendation,
            override=nv.override,
        )

    return MpResult(
        outputs=dict(neutral_result.outputs),
        verdict=mp_verdict,
        next=neutral_result.next,
        state_patch=dict(neutral_result.state_patch),
        contract_result=neutral_result.contract_result,
        envelope=mp_envelope or EMPTY_ENVELOPE,
    )


# ---------------------------------------------------------------------------
# Pipeline translation
# ---------------------------------------------------------------------------


def _translate_edge(mp_edge: Any) -> Any:
    """Translate a megaplan Edge to a neutral Edge."""
    from arnold.pipeline.types import Edge as NeutralEdge

    return NeutralEdge(
        label=mp_edge.label,
        target=mp_edge.target,
        kind=mp_edge.kind,
        recommendation=mp_edge.recommendation,
    )


def _translate_stage(mp_stage: Any) -> Any:
    """Translate a megaplan Stage to a neutral Stage.

    Keyword-only construction (SD2): megaplan ``Stage`` field order has
    ``reads`` / ``writes`` at positions 3-4 and ``decision_vocabulary`` /
    ``override_vocabulary`` at 10-11.  Neutral ``Stage`` reverses positions
    3-4 (``decision_vocabulary`` / ``override_vocabulary`` first).  A
    positional call would silently misalign these fields.
    """
    from arnold.pipeline.types import Stage as NeutralStage

    return NeutralStage(
        name=mp_stage.name,
        step=_BridgeStep(mp_stage.step),
        edges=tuple(_translate_edge(e) for e in mp_stage.edges),
        decision_vocabulary=mp_stage.decision_vocabulary,
        override_vocabulary=mp_stage.override_vocabulary,
        reads=mp_stage.reads,
        writes=mp_stage.writes,
        produces=mp_stage.produces,
        consumes=mp_stage.consumes,
        invocation=mp_stage.invocation,
        required_capabilities=mp_stage.required_capabilities,
        loop_condition=mp_stage.loop_condition,
    )


def _translate_parallel_stage(mp_ps: Any) -> Any:
    """Translate a megaplan ParallelStage to a neutral ParallelStage.

    Keyword-only construction (SD2): same field-ordering concern as
    :func:`_translate_stage`.

    The ``join`` callable is wrapped in ``_neutral_join`` so that the
    neutral executor supplies neutral types and receives neutral types while
    the underlying megaplan join sees only megaplan types throughout.
    """
    from arnold.pipeline.types import ParallelStage as NeutralParallelStage
    from arnold.runtime.envelope import EMPTY_ENVELOPE

    mp_join = mp_ps.join

    def _neutral_join(neutral_results: list, ctx: Any) -> Any:
        hook_ext: Mapping[str, Any] = ctx.hook_extensions if ctx.hook_extensions else {}
        mp_env = hook_ext.get("_mp_envelope") or EMPTY_ENVELOPE
        mp_results = [_neutral_to_mp_result(r, mp_env) for r in neutral_results]

        from arnold_pipelines.megaplan.step_types import StepContext as MpStepContext

        raw_inputs: dict = dict(hook_ext.get("_mp_inputs") or {})
        mp_inputs: dict[str, Any] = {
            k: Path(v) if isinstance(v, str) else v for k, v in raw_inputs.items()
        }
        mp_ctx = MpStepContext(
            plan_dir=Path(ctx.artifact_root),
            state=ctx.state,
            profile=hook_ext.get("_mp_profile") or {},
            mode=str(hook_ext.get("_mp_mode") or "code"),
            inputs=mp_inputs,
            budget=hook_ext.get("_mp_budget"),
            envelope=mp_env,
        )
        mp_joined = mp_join(mp_results, mp_ctx)
        return _mp_to_neutral_result(mp_joined)

    return NeutralParallelStage(
        name=mp_ps.name,
        steps=tuple(_BridgeStep(s) for s in mp_ps.steps),
        join=_neutral_join,
        edges=tuple(_translate_edge(e) for e in mp_ps.edges),
        max_workers=mp_ps.max_workers,
        decision_vocabulary=mp_ps.decision_vocabulary,
        override_vocabulary=mp_ps.override_vocabulary,
        reads=mp_ps.reads,
        writes=mp_ps.writes,
        produces=mp_ps.produces,
        consumes=mp_ps.consumes,
        invocation=mp_ps.invocation,
        required_capabilities=mp_ps.required_capabilities,
        loop_condition=getattr(mp_ps, "loop_condition", None),
    )


def _translate_pipeline(mp_pipeline: Any) -> Any:
    """Convert a megaplan Pipeline to a neutral Pipeline."""
    from arnold.pipeline.types import ParallelStage as NeutralParallelStage
    from arnold.pipeline.types import Pipeline as NeutralPipeline
    from arnold.pipeline.types import Stage as NeutralStage
    from arnold_pipelines.megaplan.step_types import ParallelStage as MpParallelStage

    if isinstance(mp_pipeline, NeutralPipeline) and all(
        isinstance(stage, (NeutralStage, NeutralParallelStage))
        for stage in mp_pipeline.stages.values()
    ):
        return mp_pipeline

    neutral_stages: dict = {}
    for name, stage in mp_pipeline.stages.items():
        if isinstance(stage, MpParallelStage):
            neutral_stages[name] = _translate_parallel_stage(stage)
        else:
            neutral_stages[name] = _translate_stage(stage)

    return NeutralPipeline(
        stages=neutral_stages,
        entry=mp_pipeline.entry,
        binding_map=mp_pipeline.binding_map,
        resource_bundles=mp_pipeline.resource_bundles,
        native_program=getattr(mp_pipeline, "native_program", None),
    )


# ---------------------------------------------------------------------------
# MegaplanExecutorHooks
# ---------------------------------------------------------------------------


class MegaplanExecutorHooks:
    """Lifecycle hooks bridging megaplan executor behavior into the neutral walk-loop.

    Implements the :class:`~arnold.execution.hooks.ExecutorHooks` structural
    protocol with megaplan-specific semantics:

    - ``on_stage_complete``: persists state to disk via ``executor-key-merge``
      after every stage (mirrors the megaplan executor's per-stage
      ``_merge_state_to_disk`` calls).
    - ``should_suspend``: detects the legacy ``_pipeline_paused`` flag.
    - ``merge_state``: accumulates ``owned_keys`` from each delta so the
      ``executor-key-merge`` write correctly prioritises executor-patched keys
      over stale on-disk values.
    - ``is_parallel_safe``: unwraps ``_BridgeStep._inner_step`` before testing
      for ``InProcessHandlerStep``.

    Governor charge and activation-event emission are deferred to M2 (demo_judges
    has no active governor; activation_emit_on() is off by default).
    """

    def __init__(self, plan_dir: Path) -> None:
        self.halt_reason: str | None = None
        self._plan_dir: Path = plan_dir
        self._final_stage: str | None = None
        self._final_state: Any = None

    def on_step_start(self, stage: Any, ctx: Any) -> Any:
        return ctx

    def on_step_end(self, stage: Any, ctx: Any, result: Any) -> Any:
        return result

    def on_step_error(self, stage: Any, ctx: Any, exc: BaseException) -> None:
        pass

    def merge_state(self, stage: Any, current_state: Any, patch: Any, owned_keys: Any) -> tuple:
        from arnold.pipeline.state import apply_delta

        new_state = apply_delta(current_state, patch)
        # Accumulate all keys introduced by this delta into owned_keys so that
        # on_stage_complete's executor-key-merge write prioritises our values.
        new_keys: frozenset[str] = frozenset(
            k for p in patch.patches if isinstance(p, dict) for k in p
        )
        return new_state, owned_keys | new_keys

    def join_envelope(self, stage: Any, current_envelope: Any, step_envelope: Any) -> Any:
        return step_envelope if step_envelope else current_envelope

    def join_parallel_results(self, stage: Any, ctx: Any, child_results: Any) -> Any:
        return stage.join(list(child_results), ctx)

    def should_suspend(self, stage: Any, state: Any, result: Any) -> tuple:
        if isinstance(state, dict) and state.get("_pipeline_paused"):
            return True, "awaiting_user"
        return False, None

    def should_halt_loop(self, stage: Any, state: Any, iteration: int) -> tuple:
        return False, None

    def resolve_routing_fallback(self, stage: Any, result: Any, edges: Any, error: Any) -> Any:
        return None

    def on_edge_traverse(
        self,
        producer_stage: Any,
        consumer_stage: Any,
        ctx: Any,
        result: Any,
    ) -> None:
        pass

    def on_stage_complete(
        self,
        stage: Any,
        ctx: Any,
        result: Any,
        state: Any,
        owned_keys: Any,
    ) -> None:
        self._final_stage = stage.name
        self._final_state = state
        if isinstance(state, dict):
            try:
                from arnold_pipelines.megaplan._core.state import write_plan_state

                write_plan_state(
                    self._plan_dir,
                    mode="executor-key-merge",
                    state=dict(state),
                    executor_owned_keys=set(owned_keys),
                )
            except Exception:
                pass

    def is_parallel_safe(self, step: Any) -> bool:
        inner = getattr(step, "_inner_step", step)
        try:
            from arnold_pipelines.megaplan.runtime.inprocess_step import InProcessHandlerStep

            return not isinstance(inner, InProcessHandlerStep)
        except ImportError:
            return True


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------


def run_pipeline_bridged(
    pipeline: Any,
    ctx: Any,
    *,
    artifact_root: Path,
) -> dict:
    """Run a megaplan pipeline through the neutral Arnold executor.

    Translates the megaplan ``Pipeline`` to neutral types, executes it via
    :func:`arnold.pipeline.runner.run_pipeline`, and returns the same dict
    shape as the legacy ``executor.run_pipeline`` for caller compatibility.

    Parameters
    ----------
    pipeline:
        A megaplan :class:`~arnold_pipelines.megaplan._pipeline.types.Pipeline`.
    ctx:
        A megaplan :class:`~arnold_pipelines.megaplan._pipeline.types.StepContext`
        carrying ``state``, ``inputs``, ``profile``, ``mode``, ``budget``,
        and ``envelope``.
    artifact_root:
        Root directory for pipeline artifacts (the plan_dir).
    """
    from arnold.pipeline.types import StepContext as NeutralStepContext
    from arnold.runtime.envelope import RuntimeEnvelope

    artifact_root = Path(artifact_root)
    artifact_root.mkdir(parents=True, exist_ok=True)

    initial_state: dict = dict(ctx.state) if isinstance(ctx.state, Mapping) else {}

    # Reconstruct the neutral RuntimeEnvelope.  Prefer the persisted
    # runtime_envelope blob written by run_cli._runtime_identity_block;
    # fall back to a minimal envelope when the blob is absent or invalid.
    runtime_envelope_blob = initial_state.get("runtime_envelope")
    if isinstance(runtime_envelope_blob, dict) and runtime_envelope_blob.get("artifact_root"):
        try:
            envelope = RuntimeEnvelope._from_jsonable(runtime_envelope_blob)
        except Exception:
            envelope = RuntimeEnvelope(artifact_root=str(artifact_root))
    else:
        envelope = RuntimeEnvelope(artifact_root=str(artifact_root))

    # Pack megaplan-specific context into hook_extensions so _BridgeStep and
    # _neutral_join can reconstruct the mp StepContext at dispatch time without
    # coupling to the neutral StepContext field layout.
    pipeline_name = ""
    pipeline_key = getattr(ctx.inputs, "get", lambda *_args, **_kwargs: None)("_pipeline")
    if isinstance(pipeline_key, str):
        pipeline_name = pipeline_key

    hook_extensions: dict = {
        "_mp_inputs": {
            k: str(v) if isinstance(v, Path) else v for k, v in ctx.inputs.items()
        },
        "_mp_profile": ctx.profile,
        "_mp_mode": ctx.mode,
        "_mp_budget": ctx.budget,
        "_mp_envelope": ctx.envelope,
        "plan_dir": str(artifact_root),
        "workspace_path": str(_workspace_path_for_plan_dir(artifact_root)),
        "repair_queue_root": str(
            _workspace_path_for_plan_dir(artifact_root) / ".megaplan" / "repair-queue"
        ),
        "plan_name": artifact_root.name,
        "pipeline_name": pipeline_name,
        "run_kind": "plan",
        "session": _repair_request_session_name(ctx, artifact_root),
    }
    try:
        from arnold_pipelines.megaplan.cloud.repair_requests import (
            enqueue_human_gate_repair_request,
        )

        hook_extensions["human_gate_repair_request_hook"] = enqueue_human_gate_repair_request
    except Exception:
        pass

    neutral_pipeline = _translate_pipeline(pipeline)
    hooks = MegaplanExecutorHooks(plan_dir=artifact_root)

    initial_context = NeutralStepContext(
        artifact_root=str(artifact_root),
        state=initial_state,
        hook_extensions=hook_extensions,
    )

    from arnold.pipeline.runner import run_pipeline as _neutral_run

    _neutral_run(
        neutral_pipeline,
        initial_state,
        envelope,
        hooks=hooks,
        initial_context=initial_context,
    )

    final_state = hooks._final_state if hooks._final_state is not None else initial_state
    return {
        "state": final_state,
        "final_stage": hooks._final_stage,
        "halt_reason": hooks.halt_reason,
        "envelope": envelope,
        "status": "completed",
        "contract_result": None,
    }


def _workspace_path_for_plan_dir(plan_dir: Path) -> Path:
    if plan_dir.parent.name == "plans" and plan_dir.parent.parent.name == ".megaplan":
        return plan_dir.parent.parent.parent
    return plan_dir


def _repair_request_session_name(ctx: Any, artifact_root: Path) -> str:
    state = getattr(ctx, "state", None)
    if isinstance(state, dict):
        for key in ("chain_session", "session", "plan_name"):
            value = state.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        meta = state.get("meta")
        if isinstance(meta, dict):
            for key in ("chain_session", "session", "plan_name"):
                value = meta.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
    return artifact_root.name


def run_pipeline_dispatch(
    pipeline: Any,
    ctx: Any,
    *,
    artifact_root: Path,
    pipeline_key: str,
) -> dict:
    """Route a pipeline through the surviving neutral Arnold executor.

    Parameters
    ----------
    pipeline:
        A megaplan :class:`~arnold_pipelines.megaplan._pipeline.types.Pipeline`.
    ctx:
        A megaplan :class:`~arnold_pipelines.megaplan._pipeline.types.StepContext`.
    artifact_root:
        Root directory for pipeline artifacts.
    pipeline_key:
        The registry name for the pipeline (SD1: derived at the CLI call site,
        not from ``Pipeline`` -- which has no ``name`` field).

    SD3 -- allowlist contract
    ------------------------
    ``_BRIDGED_PIPELINES = {'demo_judges'}`` is the M1 hard cap.  Any
    addition requires explicit verification that the target pipeline is
    bridge-compatible (no ``_materialize_stage_step`` dependency, no
    ``InProcessHandlerStep`` in a ``ParallelStage``, etc.).
    """
    del pipeline_key
    return run_pipeline(pipeline, ctx, artifact_root=artifact_root)


def run_pipeline(
    pipeline: Any,
    ctx: Any,
    *,
    artifact_root: Path,
) -> dict:
    """Compatibility entry point for callers that patch the executor directly."""
    return run_pipeline_bridged(pipeline, ctx, artifact_root=artifact_root)
