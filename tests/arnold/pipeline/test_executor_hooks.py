"""Tests for ExecutorHooks protocol, NullExecutorHooks, and media accounting (T10 / T11 / SC10 / SC11)."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any, Sequence

import pytest

from arnold.pipeline.cost_types import CostResult, CostSource, CostStatus
from arnold.pipeline.executor import DEFAULT_PARALLEL_SAFE, MediaCostAccumulator, run_pipeline, run_pipeline_resume
from arnold.execution.hooks import ExecutorHooks, NullExecutorHooks, account_media_cost_from_result
from arnold.agent.costing.media_cost import DEFAULT_MEDIA_PRICING, MediaPricingEntry, MediaUsage, compute_media_cost
from arnold.pipeline.resume_validation import ResumeReverifyResult
from arnold.pipeline.routing import RoutingError
from arnold.pipeline.state import StateDelta
from arnold.pipeline.types import (
    Edge,
    HumanSuspension,
    ParallelStage,
    Pipeline,
    Stage,
    StepContext,
    StepResult,
)
from arnold.runtime.envelope import RuntimeEnvelope


# ---------------------------------------------------------------------------
# Minimal step helpers
# ---------------------------------------------------------------------------


class _SimpleStep:
    def __init__(self, name: str, next_label: str = "halt", patch: dict | None = None) -> None:
        self.name = name
        self.kind = "compute"
        self._next = next_label
        self._patch = patch or {}
        self.calls: list[StepContext] = []

    def run(self, ctx: StepContext) -> StepResult:
        self.calls.append(ctx)
        return StepResult(next=self._next, state_patch=self._patch, outputs={"from": self.name})


class _ErrorStep:
    def __init__(self, name: str) -> None:
        self.name = name
        self.kind = "compute"

    def run(self, ctx: StepContext) -> StepResult:
        raise RuntimeError("step exploded")


def _two_stage_pipeline(step_a: Any, step_b: Any) -> Pipeline:
    return Pipeline(
        stages={
            "a": Stage(name="a", step=step_a, edges=(Edge(label="next", target="b"),)),
            "b": Stage(name="b", step=step_b, edges=()),
        },
        entry="a",
    )


def _single_stage_pipeline(step: Any) -> Pipeline:
    return Pipeline(
        stages={"s": Stage(name="s", step=step, edges=())},
        entry="s",
    )


def _make_env() -> RuntimeEnvelope:
    return RuntimeEnvelope(plugin_id="test", run_id="r1")


def _simple_join(results: list[StepResult], ctx: StepContext) -> StepResult:
    return StepResult(next="halt", outputs={"count": len(results)})


# ---------------------------------------------------------------------------
# SC3 presence check — all 12 callbacks on NullExecutorHooks
# ---------------------------------------------------------------------------


class TestNullExecutorHooksSurface:
    def test_all_12_callbacks_present(self) -> None:
        h = NullExecutorHooks()
        callbacks = [
            "on_step_start",
            "on_step_end",
            "on_step_error",
            "merge_state",
            "join_envelope",
            "join_parallel_results",
            "should_suspend",
            "should_halt_loop",
            "resolve_routing_fallback",
            "on_edge_traverse",
            "on_stage_complete",
            "is_parallel_safe",
        ]
        for cb in callbacks:
            assert hasattr(h, cb), f"NullExecutorHooks missing callback: {cb}"

    def test_isinstance_executiorhooks(self) -> None:
        assert isinstance(NullExecutorHooks(), ExecutorHooks)

    def test_on_step_start_returns_ctx_unchanged(self) -> None:
        h = NullExecutorHooks()
        env = _make_env()
        ctx = StepContext(artifact_root=env.artifact_root, state={})
        stage = Stage(name="s", step=_SimpleStep("x"))
        assert h.on_step_start(stage, ctx) is ctx

    def test_on_step_end_returns_result_unchanged(self) -> None:
        h = NullExecutorHooks()
        stage = Stage(name="s", step=_SimpleStep("x"))
        ctx = StepContext(artifact_root="/", state={})
        result = StepResult(next="halt")
        assert h.on_step_end(stage, ctx, result) is result

    def test_on_step_error_does_nothing(self) -> None:
        h = NullExecutorHooks()
        stage = Stage(name="s", step=_SimpleStep("x"))
        ctx = StepContext(artifact_root="/", state={})
        h.on_step_error(stage, ctx, RuntimeError("x"))  # must not raise

    def test_merge_state_applies_delta_unchanged_owned_keys(self) -> None:
        h = NullExecutorHooks()
        stage = Stage(name="s", step=_SimpleStep("x"))
        state = {"a": 1}
        delta = StateDelta(patches=({"b": 2},))
        new_state, new_keys = h.merge_state(stage, state, delta, frozenset())
        assert new_state["b"] == 2
        assert new_keys == frozenset()

    def test_should_suspend_returns_false(self) -> None:
        h = NullExecutorHooks()
        stage = Stage(name="s", step=_SimpleStep("x"))
        assert h.should_suspend(stage, {}, StepResult()) == (False, None)

    def test_should_halt_loop_returns_false(self) -> None:
        h = NullExecutorHooks()
        stage = Stage(name="s", step=_SimpleStep("x"))
        assert h.should_halt_loop(stage, {}, 0) == (False, None)

    def test_resolve_routing_fallback_returns_none(self) -> None:
        h = NullExecutorHooks()
        stage = Stage(name="s", step=_SimpleStep("x"))
        err = RoutingError("nope")
        assert h.resolve_routing_fallback(stage, StepResult(), (), err) is None

    def test_on_edge_traverse_does_nothing(self) -> None:
        h = NullExecutorHooks()
        stage = Stage(name="s", step=_SimpleStep("x"))
        ctx = StepContext(artifact_root="/", state={})
        h.on_edge_traverse(stage, stage, ctx, StepResult())

    def test_on_stage_complete_does_nothing(self) -> None:
        h = NullExecutorHooks()
        stage = Stage(name="s", step=_SimpleStep("x"))
        ctx = StepContext(artifact_root="/", state={})
        h.on_stage_complete(stage, ctx, StepResult(), {}, frozenset())

    def test_is_parallel_safe_returns_true(self) -> None:
        h = NullExecutorHooks()
        assert h.is_parallel_safe(object()) is True

    def test_join_envelope_returns_step_when_truthy(self) -> None:
        h = NullExecutorHooks()
        stage = Stage(name="s", step=_SimpleStep("x"))
        assert h.join_envelope(stage, "old", "new") == "new"
        assert h.join_envelope(stage, "old", None) == "old"


# ---------------------------------------------------------------------------
# Three terminal exits
# ---------------------------------------------------------------------------


class TestTerminalExitHalt:
    def test_halt_via_result_next(self) -> None:
        """result.next == 'halt' terminates cleanly."""
        step = _SimpleStep("s", next_label="halt")
        pipeline = _single_stage_pipeline(step)
        env = _make_env()
        result = run_pipeline(pipeline, {}, env)
        assert result is env

    def test_halt_via_edge_target(self) -> None:
        """edge.target == 'halt' terminates cleanly."""
        step = _SimpleStep("s", next_label="go")
        pipeline = Pipeline(
            stages={
                "s": Stage(
                    name="s",
                    step=step,
                    edges=(Edge(label="go", target="halt"),),
                ),
            },
            entry="s",
        )
        env = _make_env()
        result = run_pipeline(pipeline, {}, env)
        assert result is env

    def test_halt_calls_on_stage_complete(self) -> None:
        """on_stage_complete fires on halt."""
        completed: list[str] = []

        class _TrackHooks(NullExecutorHooks):
            def on_stage_complete(self, stage, ctx, result, state, owned_keys):
                completed.append(stage.name)

        step = _SimpleStep("s", next_label="halt")
        pipeline = _single_stage_pipeline(step)
        env = _make_env()
        run_pipeline(pipeline, {}, env, hooks=_TrackHooks())
        assert completed == ["s"]

    def test_halt_stashes_halt_reason(self) -> None:
        hooks = NullExecutorHooks()
        step = _SimpleStep("s", next_label="halt")
        pipeline = _single_stage_pipeline(step)
        run_pipeline(pipeline, {}, _make_env(), hooks=hooks)
        assert hooks.halt_reason == "halt"


class TestTerminalExitShouldSuspend:
    def test_should_suspend_returns_envelope(self) -> None:
        class _SuspendHooks(NullExecutorHooks):
            def should_suspend(self, stage, state, result):
                return True, "awaiting_human"

        step = _SimpleStep("s", next_label="continue")
        pipeline = Pipeline(
            stages={
                "s": Stage(name="s", step=step, edges=(Edge(label="continue", target="s2"),)),
                "s2": Stage(name="s2", step=_SimpleStep("s2")),
            },
            entry="s",
        )
        env = _make_env()
        hooks = _SuspendHooks()
        result = run_pipeline(pipeline, {}, env, hooks=hooks)
        assert result is env

    def test_should_suspend_calls_on_stage_complete(self) -> None:
        completed: list[str] = []

        class _SuspendHooks(NullExecutorHooks):
            def should_suspend(self, stage, state, result):
                return True, "suspended"

            def on_stage_complete(self, stage, ctx, result, state, owned_keys):
                completed.append(stage.name)

        step = _SimpleStep("s")
        pipeline = _single_stage_pipeline(step)
        run_pipeline(pipeline, {}, _make_env(), hooks=_SuspendHooks())
        assert completed == ["s"]

    def test_should_suspend_stashes_halt_reason(self) -> None:
        class _SuspendHooks(NullExecutorHooks):
            def should_suspend(self, stage, state, result):
                return True, "awaiting_user"

        hooks = _SuspendHooks()
        run_pipeline(pipeline=_single_stage_pipeline(_SimpleStep("s")), initial_state={}, envelope=_make_env(), hooks=hooks)
        assert hooks.halt_reason == "awaiting_user"

    def test_should_suspend_stops_before_next_stage(self) -> None:
        """Stage b must NOT run when stage a suspends."""
        step_a = _SimpleStep("a", next_label="next")
        step_b = _SimpleStep("b")

        class _SuspendFirst(NullExecutorHooks):
            def should_suspend(self, stage, state, result):
                return stage.name == "a", "suspended"

        pipeline = _two_stage_pipeline(step_a, step_b)
        run_pipeline(pipeline, {}, _make_env(), hooks=_SuspendFirst())
        assert len(step_b.calls) == 0


class TestTerminalExitShouldHaltLoop:
    def test_should_halt_loop_fires_pre_step(self) -> None:
        """Step must NOT run when should_halt_loop returns True."""
        step = _SimpleStep("s")

        class _HaltFirst(NullExecutorHooks):
            def should_halt_loop(self, stage, state, iteration):
                return True, "max_iterations"

        run_pipeline(pipeline=_single_stage_pipeline(step), initial_state={}, envelope=_make_env(), hooks=_HaltFirst())
        assert len(step.calls) == 0

    def test_should_halt_loop_calls_on_stage_complete(self) -> None:
        completed: list[str] = []

        class _HaltHooks(NullExecutorHooks):
            def should_halt_loop(self, stage, state, iteration):
                return True, "cost"

            def on_stage_complete(self, stage, ctx, result, state, owned_keys):
                completed.append(stage.name)

        run_pipeline(pipeline=_single_stage_pipeline(_SimpleStep("s")), initial_state={}, envelope=_make_env(), hooks=_HaltHooks())
        assert completed == ["s"]

    def test_should_halt_loop_stashes_reason(self) -> None:
        class _HaltHooks(NullExecutorHooks):
            def should_halt_loop(self, stage, state, iteration):
                return True, "stall"

        hooks = _HaltHooks()
        run_pipeline(pipeline=_single_stage_pipeline(_SimpleStep("s")), initial_state={}, envelope=_make_env(), hooks=hooks)
        assert hooks.halt_reason == "stall"


# ---------------------------------------------------------------------------
# Callback fire order and rewrites
# ---------------------------------------------------------------------------


class TestCallbackFiringOrder:
    def test_on_step_start_fires_before_run(self) -> None:
        fired: list[str] = []

        class _TrackHooks(NullExecutorHooks):
            def on_step_start(self, stage, ctx):
                fired.append("start")
                return ctx

            def on_step_end(self, stage, ctx, result):
                fired.append("end")
                return result

        step = _SimpleStep("s")
        run_pipeline(pipeline=_single_stage_pipeline(step), initial_state={}, envelope=_make_env(), hooks=_TrackHooks())
        assert fired == ["start", "end"]
        assert len(step.calls) == 1

    def test_on_step_start_can_rewrite_ctx(self) -> None:
        """on_step_start may return a different StepContext; the new one is used."""
        received: list[StepContext] = []

        class _RewriteHooks(NullExecutorHooks):
            def on_step_start(self, stage, ctx):
                new_ctx = StepContext(
                    artifact_root="/rewritten",
                    state=ctx.state,
                    inputs=ctx.inputs,
                )
                return new_ctx

        class _RecordStep:
            name = "r"
            kind = "compute"

            def run(self, ctx: StepContext) -> StepResult:
                received.append(ctx)
                return StepResult()

        pipeline = _single_stage_pipeline(_RecordStep())
        run_pipeline(pipeline, {}, _make_env(), hooks=_RewriteHooks())
        assert received[0].artifact_root == "/rewritten"

    def test_on_step_end_can_rewrite_result(self) -> None:
        """on_step_end may return a different StepResult."""
        class _RewriteResult(NullExecutorHooks):
            def on_step_end(self, stage, ctx, result):
                return StepResult(next="halt", outputs={"rewritten": True})

        step = _SimpleStep("s", next_label="halt")
        pipeline = _single_stage_pipeline(step)
        run_pipeline(pipeline, {}, _make_env(), hooks=_RewriteResult())

    def test_on_step_error_fires_on_exception(self) -> None:
        errors: list[BaseException] = []

        class _ErrHooks(NullExecutorHooks):
            def on_step_error(self, stage, ctx, exc):
                errors.append(exc)

        pipeline = _single_stage_pipeline(_ErrorStep("e"))
        with pytest.raises(RuntimeError):
            run_pipeline(pipeline, {}, _make_env(), hooks=_ErrHooks())
        assert len(errors) == 1
        assert isinstance(errors[0], RuntimeError)

    def test_merge_state_receives_owned_keys(self) -> None:
        received_keys: list[frozenset] = []

        class _KeyHooks(NullExecutorHooks):
            def merge_state(self, stage, current_state, patch, owned_keys):
                received_keys.append(owned_keys)
                new_state, _ = super().merge_state(stage, current_state, patch, frozenset())
                new_keys = owned_keys | frozenset(patch.patches[0].keys())
                return new_state, new_keys

        step = _SimpleStep("s", patch={"x": 1})
        pipeline = _single_stage_pipeline(step)
        run_pipeline(pipeline, {}, _make_env(), hooks=_KeyHooks())
        assert frozenset() in received_keys  # first call starts empty

    def test_on_edge_traverse_fires_between_stages(self) -> None:
        traversals: list[tuple[str, str]] = []

        class _TraverseHooks(NullExecutorHooks):
            def on_edge_traverse(self, producer, consumer, ctx, result):
                traversals.append((producer.name, consumer.name))

        step_a = _SimpleStep("a", next_label="next")
        step_b = _SimpleStep("b")
        pipeline = _two_stage_pipeline(step_a, step_b)
        run_pipeline(pipeline, {}, _make_env(), hooks=_TraverseHooks())
        assert traversals == [("a", "b")]

    def test_on_stage_complete_fires_at_every_normal_stage(self) -> None:
        completed: list[str] = []

        class _CompleteHooks(NullExecutorHooks):
            def on_stage_complete(self, stage, ctx, result, state, owned_keys):
                completed.append(stage.name)

        step_a = _SimpleStep("a", next_label="next")
        step_b = _SimpleStep("b")
        pipeline = _two_stage_pipeline(step_a, step_b)
        run_pipeline(pipeline, {}, _make_env(), hooks=_CompleteHooks())
        assert completed == ["a", "b"]

    def test_on_stage_complete_receives_owned_keys(self) -> None:
        seen_owned: list[frozenset] = []

        class _TrackHooks(NullExecutorHooks):
            def on_stage_complete(self, stage, ctx, result, state, owned_keys):
                seen_owned.append(owned_keys)

        step = _SimpleStep("s")
        run_pipeline(pipeline=_single_stage_pipeline(step), initial_state={}, envelope=_make_env(), hooks=_TrackHooks())
        assert len(seen_owned) == 1
        assert isinstance(seen_owned[0], frozenset)


# ---------------------------------------------------------------------------
# resolve_routing_fallback
# ---------------------------------------------------------------------------


class TestResolveRoutingFallback:
    def test_fallback_edge_redirects(self) -> None:
        """resolve_routing_fallback may return an edge to redirect on RoutingError."""
        step_a = _SimpleStep("a", next_label="unknown_label")
        step_b = _SimpleStep("b")

        class _FallbackHooks(NullExecutorHooks):
            def resolve_routing_fallback(self, stage, result, edges, error):
                for edge in edges:
                    if edge.label == "force":
                        return edge
                return None

        pipeline = Pipeline(
            stages={
                "a": Stage(
                    name="a",
                    step=step_a,
                    edges=(Edge(label="force", target="b"),),
                    decision_vocabulary=frozenset({"normal_key"}),
                ),
                "b": Stage(name="b", step=step_b),
            },
            entry="a",
        )
        env = _make_env()
        run_pipeline(pipeline, {}, env, hooks=_FallbackHooks())
        assert len(step_b.calls) == 1

    def test_fallback_none_propagates_routing_error(self) -> None:
        step_a = _SimpleStep("a", next_label="ghost")
        pipeline = Pipeline(
            stages={
                "a": Stage(
                    name="a",
                    step=step_a,
                    edges=(Edge(label="real", target="halt"),),
                    decision_vocabulary=frozenset({"real"}),
                ),
            },
            entry="a",
        )
        with pytest.raises(RoutingError):
            run_pipeline(pipeline, {}, _make_env())


# ---------------------------------------------------------------------------
# join_parallel_results receives the full child list
# ---------------------------------------------------------------------------


class TestJoinParallelResults:
    def test_join_parallel_results_receives_full_child_list(self) -> None:
        received_children: list[list[StepResult]] = []

        class _JoinHooks(NullExecutorHooks):
            def join_parallel_results(self, stage, ctx, child_results):
                received_children.append(list(child_results))
                return stage.join(list(child_results), ctx)

        steps = [_SimpleStep(f"c{i}", next_label="halt") for i in range(3)]
        stage = ParallelStage(
            name="par",
            steps=tuple(steps),
            join=_simple_join,
        )
        pipeline = Pipeline(stages={"par": stage}, entry="par")
        run_pipeline(pipeline, {}, _make_env(), hooks=_JoinHooks())
        assert len(received_children) == 1
        assert len(received_children[0]) == 3

    def test_on_step_start_fires_per_parallel_child(self) -> None:
        starts: list[str] = []

        class _TrackHooks(NullExecutorHooks):
            def on_step_start(self, stage, ctx):
                starts.append(stage.name)
                return ctx

        steps = [_SimpleStep(f"c{i}") for i in range(3)]
        par = ParallelStage(name="par", steps=tuple(steps), join=_simple_join)
        pipeline = Pipeline(stages={"par": par}, entry="par")
        run_pipeline(pipeline, {}, _make_env(), hooks=_TrackHooks())
        assert starts.count("par") == 3

    def test_on_step_end_fires_per_parallel_child(self) -> None:
        ends: list[str] = []

        class _TrackHooks(NullExecutorHooks):
            def on_step_end(self, stage, ctx, result):
                ends.append(stage.name)
                return result

        steps = [_SimpleStep(f"c{i}") for i in range(2)]
        par = ParallelStage(name="par", steps=tuple(steps), join=_simple_join)
        pipeline = Pipeline(stages={"par": par}, entry="par")
        run_pipeline(pipeline, {}, _make_env(), hooks=_TrackHooks())
        assert ends.count("par") == 2


# ---------------------------------------------------------------------------
# NullExecutorHooks produces byte-for-byte identical behavior
# ---------------------------------------------------------------------------


class TestNullHooksPreservesExistingBehavior:
    def _run_without_hooks(self, pipeline: Pipeline, state: dict) -> RuntimeEnvelope:
        env = RuntimeEnvelope(plugin_id="p", run_id="r")
        return run_pipeline(pipeline, state, env)

    def _run_with_null_hooks(self, pipeline: Pipeline, state: dict) -> RuntimeEnvelope:
        env = RuntimeEnvelope(plugin_id="p", run_id="r")
        return run_pipeline(pipeline, state, env, hooks=NullExecutorHooks())

    def test_two_stage_returns_envelope(self) -> None:
        step_a = _SimpleStep("a", next_label="next")
        step_b = _SimpleStep("b")
        pipeline = _two_stage_pipeline(step_a, step_b)
        env1 = self._run_without_hooks(pipeline, {})
        step_a2 = _SimpleStep("a", next_label="next")
        step_b2 = _SimpleStep("b")
        env2 = self._run_with_null_hooks(_two_stage_pipeline(step_a2, step_b2), {})
        assert isinstance(env1, RuntimeEnvelope)
        assert isinstance(env2, RuntimeEnvelope)
        assert len(step_a.calls) == len(step_a2.calls) == 1
        assert len(step_b.calls) == len(step_b2.calls) == 1

    def test_parallel_stage_returns_envelope(self) -> None:
        steps = [_SimpleStep(f"c{i}") for i in range(3)]
        par = ParallelStage(name="par", steps=tuple(steps), join=_simple_join)
        pipeline = Pipeline(stages={"par": par}, entry="par")
        env1 = self._run_without_hooks(pipeline, {})
        steps2 = [_SimpleStep(f"c{i}") for i in range(3)]
        par2 = ParallelStage(name="par", steps=tuple(steps2), join=_simple_join)
        pipeline2 = Pipeline(stages={"par": par2}, entry="par")
        env2 = self._run_with_null_hooks(pipeline2, {})
        assert isinstance(env1, RuntimeEnvelope)
        assert isinstance(env2, RuntimeEnvelope)

    def test_state_patches_identical(self) -> None:
        """State patches observed from on_step_start ctx.state match no-hooks path."""
        states_seen: list[dict] = []

        class _CapState(NullExecutorHooks):
            def on_step_start(self, stage, ctx):
                states_seen.append(dict(ctx.state) if isinstance(ctx.state, dict) else {})
                return ctx

        step_a = _SimpleStep("a", next_label="next", patch={"key": "val"})
        step_b = _SimpleStep("b")
        pipeline = _two_stage_pipeline(step_a, step_b)
        run_pipeline(pipeline, {"init": 1}, _make_env(), hooks=_CapState())
        # step b sees the patch from step a
        assert states_seen[1].get("key") == "val"

    def test_null_hooks_byte_identical_to_no_hooks_serial(self) -> None:
        """NullExecutorHooks produces byte-identical output to hooks=None (serial)."""
        pipeline = _two_stage_pipeline(
            _SimpleStep("a", next_label="next", patch={"shared": "x"}),
            _SimpleStep("b", patch={"extra": "y"}),
        )
        env1 = _make_env()
        env2 = _make_env()
        # Two separate runs with same state
        r1 = run_pipeline(pipeline, {"init": 1}, env1, hooks=None)
        r2 = run_pipeline(pipeline, {"init": 1}, env2, hooks=NullExecutorHooks())
        # Both return the RuntimeEnvelope unchanged
        assert r1 is env1
        assert r2 is env2
        assert type(r1) is type(r2)

    def test_null_hooks_byte_identical_to_no_hooks_parallel(self) -> None:
        """NullExecutorHooks produces byte-identical output to hooks=None (parallel)."""
        steps1 = [_SimpleStep(f"c{i}") for i in range(3)]
        par1 = ParallelStage(name="par", steps=tuple(steps1), join=_simple_join)
        pipeline1 = Pipeline(stages={"par": par1}, entry="par")

        steps2 = [_SimpleStep(f"c{i}") for i in range(3)]
        par2 = ParallelStage(name="par", steps=tuple(steps2), join=_simple_join)
        pipeline2 = Pipeline(stages={"par": par2}, entry="par")

        env1 = _make_env()
        env2 = _make_env()
        r1 = run_pipeline(pipeline1, {}, env1, hooks=None)
        r2 = run_pipeline(pipeline2, {}, env2, hooks=NullExecutorHooks())
        assert r1 is env1
        assert r2 is env2

    def test_null_hooks_halt_reason_cleared(self) -> None:
        """NullExecutorHooks halt_reason is set on halt and stays from prior run."""
        hooks = NullExecutorHooks()
        assert hooks.halt_reason is None
        step = _SimpleStep("s", next_label="halt")
        pipeline = _single_stage_pipeline(step)
        run_pipeline(pipeline, {}, _make_env(), hooks=hooks)
        assert hooks.halt_reason == "halt"


# ---------------------------------------------------------------------------
# is_parallel_safe integration — hooks override the parallel_safe predicate
# ---------------------------------------------------------------------------


class TestIsParallelSafeIntegration:
    def test_custom_hooks_uses_is_parallel_safe(self) -> None:
        """When custom hooks are provided, is_parallel_safe governs parallel safety."""
        safe_checked: list[object] = []

        class _SafeHooks(NullExecutorHooks):
            def is_parallel_safe(self, step):
                safe_checked.append(step)
                return True

        steps = [_SimpleStep(f"c{i}") for i in range(2)]
        par = ParallelStage(name="par", steps=tuple(steps), join=_simple_join)
        pipeline = Pipeline(stages={"par": par}, entry="par")
        run_pipeline(pipeline, {}, _make_env(), hooks=_SafeHooks())
        assert len(safe_checked) == 2

    def test_custom_hooks_rejects_unsafe_step(self) -> None:
        """is_parallel_safe returning False raises ValueError."""
        class _RejectHooks(NullExecutorHooks):
            def is_parallel_safe(self, step):
                return False

        steps = [_SimpleStep("c0")]
        par = ParallelStage(name="par", steps=tuple(steps), join=_simple_join)
        pipeline = Pipeline(stages={"par": par}, entry="par")
        with pytest.raises(ValueError, match="not parallel-safe"):
            run_pipeline(pipeline, {}, _make_env(), hooks=_RejectHooks())


# ---------------------------------------------------------------------------
# on_step_error in parallel fan-out
# ---------------------------------------------------------------------------


class TestParallelStepError:
    def test_on_step_error_fires_per_failed_parallel_child(self) -> None:
        """When a parallel child raises, on_step_error fires exactly once for that child."""
        errors: list[BaseException] = []

        class _ErrHooks(NullExecutorHooks):
            def on_step_error(self, stage, ctx, exc):
                errors.append(exc)

        steps = (
            _SimpleStep("ok"),
            _ErrorStep("bad"),
        )
        par = ParallelStage(name="par", steps=steps, join=_simple_join)
        pipeline = Pipeline(stages={"par": par}, entry="par")
        with pytest.raises(RuntimeError, match="step exploded"):
            run_pipeline(pipeline, {}, _make_env(), hooks=_ErrHooks())
        assert len(errors) == 1
        assert isinstance(errors[0], RuntimeError)


# ---------------------------------------------------------------------------
# Terminal exits with parallel stages
# ---------------------------------------------------------------------------


class TestTerminalExitsWithParallelStage:
    def test_should_suspend_after_parallel_returns_envelope(self) -> None:
        """should_suspend after a parallel stage returns envelope immediately."""
        class _SuspendHooks(NullExecutorHooks):
            def should_suspend(self, stage, state, result):
                return True, "suspended_parallel"

        steps = [_SimpleStep(f"c{i}") for i in range(2)]
        par = ParallelStage(name="par", steps=tuple(steps), join=_simple_join)
        pipeline = Pipeline(stages={"par": par}, entry="par")
        env = _make_env()
        hooks = _SuspendHooks()
        result = run_pipeline(pipeline, {}, env, hooks=hooks)
        assert result is env
        assert hooks.halt_reason == "suspended_parallel"

    def test_should_halt_loop_before_parallel(self) -> None:
        """should_halt_loop fires before parallel stage runs any child."""
        class _HaltHooks(NullExecutorHooks):
            def should_halt_loop(self, stage, state, iteration):
                return True, "premature_halt"

        steps = [_SimpleStep("c0")]
        par = ParallelStage(name="par", steps=tuple(steps), join=_simple_join)
        pipeline = Pipeline(stages={"par": par}, entry="par")
        hooks = _HaltHooks()
        run_pipeline(pipeline, {}, _make_env(), hooks=hooks)
        # The step should never have been called
        assert len(steps[0].calls) == 0
        assert hooks.halt_reason == "premature_halt"

    def test_halt_via_parallel_join_result(self) -> None:
        """When the parallel join result says 'halt', the walk loop terminates."""
        def _halt_join(results: list[StepResult], ctx: StepContext) -> StepResult:
            return StepResult(next="halt", outputs={"count": len(results)})

        steps = [_SimpleStep(f"c{i}") for i in range(2)]
        par = ParallelStage(name="par", steps=tuple(steps), join=_halt_join)
        pipeline = Pipeline(stages={"par": par}, entry="par")
        hooks = NullExecutorHooks()
        env = _make_env()
        result = run_pipeline(pipeline, {}, env, hooks=hooks)
        assert result is env
        assert hooks.halt_reason == "halt"


# ---------------------------------------------------------------------------
# merge_state owned_keys threading across multiple stages
# ---------------------------------------------------------------------------


class TestMergeStateOwnedKeysThreading:
    def test_owned_keys_accumulates_across_stages(self) -> None:
        """merge_state can grow owned_keys from multiple steps; executor threads them."""
        accumulated: list[frozenset] = []

        class _KeyHooks(NullExecutorHooks):
            def merge_state(self, stage, current_state, patch, owned_keys):
                new_state, _ = super().merge_state(stage, current_state, patch, frozenset())
                # Track the key from this stage's patch
                new_keys = owned_keys | frozenset(patch.patches[0].keys())
                accumulated.append(new_keys)
                return new_state, new_keys

        step_a = _SimpleStep("a", next_label="next", patch={"key_a": 1})
        step_b = _SimpleStep("b", patch={"key_b": 2})
        pipeline = _two_stage_pipeline(step_a, step_b)
        run_pipeline(pipeline, {}, _make_env(), hooks=_KeyHooks())
        # After stage a: owned_keys = {"key_a"}
        # After stage b: owned_keys = {"key_a", "key_b"}
        assert accumulated == [frozenset({"key_a"}), frozenset({"key_a", "key_b"})]

    def test_owned_keys_survives_no_patch_stage(self) -> None:
        """When a step produces no state_patch, merge_state is not called; owned_keys unchanged."""
        accumulated: list[frozenset] = []

        class _KeyHooks(NullExecutorHooks):
            def merge_state(self, stage, current_state, patch, owned_keys):
                accumulated.append(owned_keys)
                return super().merge_state(stage, current_state, patch, owned_keys)

        step_a = _SimpleStep("a", next_label="next", patch={"key_a": 1})
        # step b has no patch → merge_state is not called for it
        step_b = _SimpleStep("b")
        pipeline = _two_stage_pipeline(step_a, step_b)
        run_pipeline(pipeline, {}, _make_env(), hooks=_KeyHooks())
        # merge_state called once (for step_a's patch); step_b had no patch
        assert len(accumulated) == 1
        assert isinstance(accumulated[0], frozenset)


# ---------------------------------------------------------------------------
# on_stage_complete receives correct arguments
# ---------------------------------------------------------------------------


class TestOnStageCompleteArgs:
    def test_on_stage_complete_receives_correct_args_on_normal_exit(self) -> None:
        """on_stage_complete receives stage, ctx, result, state, and owned_keys."""
        captures: list[dict[str, Any]] = []

        class _CaptureHooks(NullExecutorHooks):
            def on_stage_complete(self, stage, ctx, result, state, owned_keys):
                captures.append({
                    "stage_name": stage.name,
                    "ctx_type": type(ctx).__name__,
                    "result_type": type(result).__name__,
                    "state_type": type(state).__name__,
                    "owned_keys_type": type(owned_keys).__name__,
                })

        step_a = _SimpleStep("a", next_label="next")
        step_b = _SimpleStep("b")
        pipeline = _two_stage_pipeline(step_a, step_b)
        run_pipeline(pipeline, {}, _make_env(), hooks=_CaptureHooks())
        assert len(captures) == 2
        assert captures[0]["stage_name"] == "a"
        assert captures[0]["ctx_type"] == "StepContext"
        assert captures[0]["result_type"] == "StepResult"
        assert isinstance(captures[0]["state_type"], str)
        assert captures[0]["owned_keys_type"] == "frozenset"
        assert captures[1]["stage_name"] == "b"

    def test_on_stage_complete_receives_state_after_merge(self) -> None:
        """on_stage_complete state reflects the merged outputs/patches."""
        states_seen: list[Any] = []

        class _StateHooks(NullExecutorHooks):
            def on_stage_complete(self, stage, ctx, result, state, owned_keys):
                states_seen.append(dict(state) if isinstance(state, dict) else state)

        step_a = _SimpleStep("a", next_label="next", patch={"key_a": "val_a"})
        step_b = _SimpleStep("b", patch={"key_b": "val_b"})
        pipeline = _two_stage_pipeline(step_a, step_b)
        run_pipeline(pipeline, {"init": 0}, _make_env(), hooks=_StateHooks())
        # After stage a: init + outputs + patch = {"init": 0, "from": "a", "key_a": "val_a"}
        assert states_seen[0].get("key_a") == "val_a"
        # After stage b: previous + outputs + patch
        assert states_seen[1].get("key_b") == "val_b"
        assert states_seen[1].get("key_a") == "val_a"


# ---------------------------------------------------------------------------
# parallel_safe default predicate preserves no-hook behavior
# ---------------------------------------------------------------------------


class TestParallelSafeDefaultBehavior:
    def test_default_parallel_safe_accepts_anything(self) -> None:
        """DEFAULT_PARALLEL_SAFE returns True for any step."""
        assert DEFAULT_PARALLEL_SAFE(object()) is True
        assert DEFAULT_PARALLEL_SAFE(None) is True
        assert DEFAULT_PARALLEL_SAFE(_SimpleStep("x")) is True

    def test_no_hooks_parallel_uses_default_safe(self) -> None:
        """Without hooks, the parallel_safe predicate (or DEFAULT) is used."""
        steps = [_SimpleStep(f"c{i}") for i in range(3)]
        par = ParallelStage(name="par", steps=tuple(steps), join=_simple_join)
        pipeline = Pipeline(stages={"par": par}, entry="par")
        env = _make_env()
        result = run_pipeline(pipeline, {}, env, hooks=None)
        assert result is env
        # All three steps were called (proving parallel safety check passed)
        assert all(len(s.calls) == 1 for s in steps)


class TestResumeReverifyHookWrapping:
    def test_resume_reverify_runs_only_for_first_resumed_stage(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        artifact = tmp_path / "resume.json"
        artifact.write_text(json.dumps({"value": 42}), encoding="utf-8")
        calls: list[str] = []
        stage_a = _SimpleStep("a", next_label="next")
        stage_b = _SimpleStep("b", next_label="halt")
        pipeline = _two_stage_pipeline(stage_a, stage_b)
        suspension = HumanSuspension(
            kind="human",
            awaitable="user",
            prompt="Resume",
            resume_input_schema={"x-arnold-resume": {"artifact_path": "resume.json"}},
        )

        def _fake_reverify(
            supplied_suspension: HumanSuspension,
            *,
            artifact_root: str,
            schema_registry: Any,
            producer_stage: str | None = None,
        ) -> ResumeReverifyResult:
            assert supplied_suspension is suspension
            assert artifact_root == str(tmp_path)
            assert schema_registry is None
            calls.append(str(producer_stage))
            return ResumeReverifyResult(
                outcome="valid",
                declaration=None,
                resolved_artifact_path=str(artifact),
            )

        monkeypatch.setattr(
            "arnold.pipeline.executor.reverify_resume_produces",
            _fake_reverify,
        )

        run_pipeline_resume(
            pipeline,
            {},
            RuntimeEnvelope(artifact_root=str(tmp_path)),
            resume_cursor={"stage": "a"},
            suspension=suspension,
        )

        assert calls == ["a"]
        assert len(stage_a.calls) == 1
        assert len(stage_b.calls) == 1


# ---------------------------------------------------------------------------
# T10: Media accounting tests (account_media_cost_from_result + MediaCostAccumulator)
# ---------------------------------------------------------------------------


class TestAccountMediaCostFromResultNoMedia:
    """No-media no-op behaviour: empty tuple when no media_usage present."""

    def test_no_hook_metadata_key_returns_empty(self) -> None:
        """When hook_metadata has no 'media_usage' key, return ()."""
        result = StepResult(hook_metadata={"other": "stuff"})
        lines = account_media_cost_from_result(result, provider="openai", model="dall-e-3")
        assert lines == ()

    def test_empty_hook_metadata_returns_empty(self) -> None:
        """When hook_metadata is empty dict, return ()."""
        result = StepResult(hook_metadata={})
        lines = account_media_cost_from_result(result, provider="openai", model="dall-e-3")
        assert lines == ()

    def test_none_hook_metadata_returns_empty(self) -> None:
        """When hook_metadata is None, return ()."""
        result = StepResult(hook_metadata=None)
        lines = account_media_cost_from_result(result, provider="openai", model="dall-e-3")
        assert lines == ()

    def test_media_usage_none_value_returns_empty(self) -> None:
        """When hook_metadata['media_usage'] is None, return ()."""
        result = StepResult(hook_metadata={"media_usage": None})
        lines = account_media_cost_from_result(result, provider="openai", model="dall-e-3")
        assert lines == ()

    def test_empty_provider_returns_empty(self) -> None:
        """When provider is empty string, return ()."""
        usage = MediaUsage(unit="image", count=1)
        result = StepResult(hook_metadata={"media_usage": usage})
        lines = account_media_cost_from_result(result, provider="", model="dall-e-3")
        assert lines == ()

    def test_empty_model_returns_empty(self) -> None:
        """When model is empty string, return ()."""
        usage = MediaUsage(unit="image", count=1)
        result = StepResult(hook_metadata={"media_usage": usage})
        lines = account_media_cost_from_result(result, provider="openai", model="")
        assert lines == ()


class TestAccountMediaCostFromResultPriced:
    """Priced media: valid media_usage with known pricing rows."""

    def test_single_image_priced(self) -> None:
        """One image usage with known pricing produces a priced CostResult."""
        usage = MediaUsage(unit="image", count=1)
        result = StepResult(hook_metadata={"media_usage": usage})
        lines = account_media_cost_from_result(result, provider="openai",
                                                model="dall-e-3",
                                                pricing_rows=DEFAULT_MEDIA_PRICING)
        assert len(lines) == 1
        cr = lines[0]
        assert cr.amount_usd == Decimal("0.040")
        assert cr.status == "estimated"
        assert cr.source == "official_docs_snapshot"
        assert "image" in cr.label

    def test_single_image_hd_priced(self) -> None:
        """One image_hd usage with known pricing."""
        usage = MediaUsage(unit="image_hd", count=1)
        result = StepResult(hook_metadata={"media_usage": usage})
        lines = account_media_cost_from_result(result, provider="openai",
                                                model="dall-e-3",
                                                pricing_rows=DEFAULT_MEDIA_PRICING)
        assert len(lines) == 1
        assert lines[0].amount_usd == Decimal("0.080")

    def test_multiple_image_priced(self) -> None:
        """Multiple images — count 3 * $0.040 = $0.120."""
        usage = MediaUsage(unit="image", count=3)
        result = StepResult(hook_metadata={"media_usage": usage})
        lines = account_media_cost_from_result(result, provider="openai",
                                                model="dall-e-3",
                                                pricing_rows=DEFAULT_MEDIA_PRICING)
        assert len(lines) == 1
        assert lines[0].amount_usd == Decimal("0.120")
        assert lines[0].label == "image (3)"

    def test_song_priced(self) -> None:
        """One song usage with tts-1 pricing."""
        usage = MediaUsage(unit="song", count=1)
        result = StepResult(hook_metadata={"media_usage": usage})
        lines = account_media_cost_from_result(result, provider="openai",
                                                model="tts-1",
                                                pricing_rows=DEFAULT_MEDIA_PRICING)
        assert len(lines) == 1
        assert lines[0].amount_usd == Decimal("0.015")
        assert lines[0].label == "song (1)"

    def test_multiple_usage_items_tuple(self) -> None:
        """Tuple of two MediaUsage items."""
        usages = (
            MediaUsage(unit="image", count=1),
            MediaUsage(unit="image_hd", count=2),
        )
        result = StepResult(hook_metadata={"media_usage": usages})
        lines = account_media_cost_from_result(result, provider="openai",
                                                model="dall-e-3",
                                                pricing_rows=DEFAULT_MEDIA_PRICING)
        assert len(lines) == 2
        assert lines[0].amount_usd == Decimal("0.040")
        assert lines[1].amount_usd == Decimal("0.160")

    def test_multiple_usage_items_list(self) -> None:
        """List of two MediaUsage items (list normalized to tuple)."""
        usages = [
            MediaUsage(unit="image", count=1),
            MediaUsage(unit="image_hd", count=1),
        ]
        result = StepResult(hook_metadata={"media_usage": usages})
        lines = account_media_cost_from_result(result, provider="openai",
                                                model="dall-e-3",
                                                pricing_rows=DEFAULT_MEDIA_PRICING)
        assert len(lines) == 2

    def test_pricing_version_propagates(self) -> None:
        """CostResult carries pricing_version from the matched row."""
        usage = MediaUsage(unit="image", count=1)
        result = StepResult(hook_metadata={"media_usage": usage})
        lines = account_media_cost_from_result(result, provider="openai",
                                                model="dall-e-3",
                                                pricing_rows=DEFAULT_MEDIA_PRICING)
        assert lines[0].pricing_version == "ar3-media-snapshot-2026-06"

    def test_case_insensitive_provider_model_match(self) -> None:
        """Case-insensitive provider/model matching."""
        usage = MediaUsage(unit="image", count=1)
        result = StepResult(hook_metadata={"media_usage": usage})
        lines = account_media_cost_from_result(result, provider="OpenAI",
                                                model="DALL-E-3",
                                                pricing_rows=DEFAULT_MEDIA_PRICING)
        assert len(lines) == 1
        assert lines[0].amount_usd == Decimal("0.040")


class TestAccountMediaCostFromResultUnknown:
    """Unknown pricing: units with no matching row return unknown CostResult."""

    def test_unknown_unit_yields_unknown(self) -> None:
        """A unit not in the pricing table returns unknown with notes."""
        usage = MediaUsage(unit="video_second", count=10)
        result = StepResult(hook_metadata={"media_usage": usage})
        lines = account_media_cost_from_result(result, provider="openai",
                                                model="dall-e-3",
                                                pricing_rows=DEFAULT_MEDIA_PRICING)
        assert len(lines) == 1
        cr = lines[0]
        assert cr.amount_usd is None
        assert cr.status == "unknown"
        assert cr.source == "none"
        assert cr.label == "n/a"
        assert len(cr.notes) == 1
        assert "No media pricing row" in cr.notes[0]
        assert "video_second" in cr.notes[0]

    def test_unknown_provider_yields_unknown(self) -> None:
        """Unknown provider returns unknown (no matching row)."""
        usage = MediaUsage(unit="image", count=1)
        result = StepResult(hook_metadata={"media_usage": usage})
        lines = account_media_cost_from_result(result, provider="unknown_corp",
                                                model="dall-e-3",
                                                pricing_rows=DEFAULT_MEDIA_PRICING)
        assert len(lines) == 1
        assert lines[0].status == "unknown"
        assert lines[0].amount_usd is None

    def test_unknown_model_yields_unknown(self) -> None:
        """Unknown model returns unknown."""
        usage = MediaUsage(unit="image", count=1)
        result = StepResult(hook_metadata={"media_usage": usage})
        lines = account_media_cost_from_result(result, provider="openai",
                                                model="unknown-model",
                                                pricing_rows=DEFAULT_MEDIA_PRICING)
        assert len(lines) == 1
        assert lines[0].status == "unknown"

    def test_mixed_priced_and_unknown(self) -> None:
        """Mix of priced and unknown units — all returned in order."""
        usages = (
            MediaUsage(unit="image", count=2),
            MediaUsage(unit="video_second", count=30),
        )
        result = StepResult(hook_metadata={"media_usage": usages})
        lines = account_media_cost_from_result(result, provider="openai",
                                                model="dall-e-3",
                                                pricing_rows=DEFAULT_MEDIA_PRICING)
        assert len(lines) == 2
        assert lines[0].status == "estimated"
        assert lines[0].amount_usd == Decimal("0.080")
        assert lines[1].status == "unknown"
        assert lines[1].amount_usd is None

    def test_unknown_line_preserved_not_omitted(self) -> None:
        """Unknown lines are preserved (not silently dropped)."""
        usage = MediaUsage(unit="video_second", count=1)
        result = StepResult(hook_metadata={"media_usage": usage})
        lines = account_media_cost_from_result(result, provider="openai",
                                                model="dall-e-3",
                                                pricing_rows=DEFAULT_MEDIA_PRICING)
        assert len(lines) == 1
        # Unknown but present — not omitted
        assert lines[0].status == "unknown"

    def test_custom_pricing_rows_used(self) -> None:
        """Custom pricing_rows override is respected."""
        custom = (
            MediaPricingEntry(
                provider="test_corp",
                model="test_model",
                unit="widget",
                cost_per_unit=Decimal("0.001"),
                source="custom_contract",
                pricing_version="custom-v1",
                status="actual",
            ),
        )
        usage = MediaUsage(unit="widget", count=100)
        result = StepResult(hook_metadata={"media_usage": usage})
        lines = account_media_cost_from_result(result, provider="test_corp",
                                                model="test_model",
                                                pricing_rows=custom)
        assert len(lines) == 1
        assert lines[0].amount_usd == Decimal("0.100")
        assert lines[0].status == "actual"
        assert lines[0].source == "custom_contract"


class TestAccountMediaCostFromResultMalformed:
    """Malformed metadata handled nonfatally (TypeError → unknown CostResult)."""

    def test_malformed_string_value_nonfatal(self) -> None:
        """A string in media_usage triggers TypeError → nonfatal unknown."""
        result = StepResult(hook_metadata={"media_usage": "not_a_media_usage"})
        lines = account_media_cost_from_result(result, provider="openai",
                                                model="dall-e-3")
        assert len(lines) == 1
        cr = lines[0]
        assert cr.amount_usd is None
        assert cr.status == "unknown"
        assert cr.source == "none"
        assert cr.label == "n/a"
        assert len(cr.notes) == 1
        assert "Malformed" in cr.notes[0]
        assert "openai" in cr.notes[0]
        assert "dall-e-3" in cr.notes[0]

    def test_malformed_int_value_nonfatal(self) -> None:
        """An int in media_usage triggers TypeError → nonfatal unknown."""
        result = StepResult(hook_metadata={"media_usage": 42})
        lines = account_media_cost_from_result(result, provider="openai",
                                                model="dall-e-3")
        assert len(lines) == 1
        assert lines[0].status == "unknown"

    def test_malformed_dict_value_nonfatal(self) -> None:
        """A dict in media_usage triggers TypeError → nonfatal unknown."""
        result = StepResult(hook_metadata={"media_usage": {"unit": "image", "count": 1}})
        lines = account_media_cost_from_result(result, provider="openai",
                                                model="dall-e-3")
        assert len(lines) == 1
        assert lines[0].status == "unknown"

    def test_malformed_list_with_non_mediausage_item(self) -> None:
        """A list containing a non-MediaUsage item triggers TypeError → nonfatal."""
        result = StepResult(hook_metadata={"media_usage": [MediaUsage(unit="image", count=1), "bad_item"]})
        lines = account_media_cost_from_result(result, provider="openai",
                                                model="dall-e-3")
        assert len(lines) == 1
        assert lines[0].status == "unknown"
        assert "Malformed" in lines[0].notes[0]

    def test_malformed_never_raises(self) -> None:
        """All malformed cases must not raise — the function is nonfatal."""
        malformed_values = [
            123,
            "string",
            {"key": "val"},
            [1, 2, 3],
            (MediaUsage(unit="image", count=1), "bad"),
            object(),
        ]
        for val in malformed_values:
            result = StepResult(hook_metadata={"media_usage": val})
            # Must not raise
            lines = account_media_cost_from_result(result, provider="openai",
                                                    model="dall-e-3")
            assert isinstance(lines, tuple)
            assert len(lines) == 1
            assert lines[0].status == "unknown"

    def test_empty_usage_tuple_returns_empty(self) -> None:
        """An empty tuple of media_usage returns () — no malformed handling needed."""
        result = StepResult(hook_metadata={"media_usage": ()})
        lines = account_media_cost_from_result(result, provider="openai",
                                                model="dall-e-3")
        assert lines == ()

    def test_empty_usage_list_returns_empty(self) -> None:
        """An empty list of media_usage returns ()."""
        result = StepResult(hook_metadata={"media_usage": []})
        lines = account_media_cost_from_result(result, provider="openai",
                                                model="dall-e-3")
        assert lines == ()


class TestMediaCostAccumulatorIntegration:
    """MediaCostAccumulator integration: account(), line accumulation, opt-in behaviour."""

    def test_account_priced_appends_to_lines(self) -> None:
        """account() with valid media usage populates lines."""
        acc = MediaCostAccumulator()
        usage = MediaUsage(unit="image", count=2)
        result = StepResult(hook_metadata={"media_usage": usage})
        acc.account(result, provider="openai", model="dall-e-3",
                    pricing_rows=DEFAULT_MEDIA_PRICING)
        assert len(acc.lines) == 1
        assert acc.lines[0].amount_usd == Decimal("0.080")

    def test_account_no_media_leaves_lines_empty(self) -> None:
        """account() with no media_usage leaves lines unchanged."""
        acc = MediaCostAccumulator()
        result = StepResult(hook_metadata={})
        acc.account(result, provider="openai", model="dall-e-3")
        assert acc.lines == []

    def test_multiple_account_calls_accumulate(self) -> None:
        """Multiple account() calls accumulate lines in order."""
        acc = MediaCostAccumulator()
        r1 = StepResult(hook_metadata={"media_usage": MediaUsage(unit="image", count=1)})
        r2 = StepResult(hook_metadata={"media_usage": MediaUsage(unit="image_hd", count=3)})
        acc.account(r1, provider="openai", model="dall-e-3",
                    pricing_rows=DEFAULT_MEDIA_PRICING)
        acc.account(r2, provider="openai", model="dall-e-3",
                    pricing_rows=DEFAULT_MEDIA_PRICING)
        assert len(acc.lines) == 2
        assert acc.lines[0].amount_usd == Decimal("0.040")
        assert acc.lines[1].amount_usd == Decimal("0.240")

    def test_account_unknown_appends_unknown_line(self) -> None:
        """account() with unknown unit appends unknown CostResult — not omitted."""
        acc = MediaCostAccumulator()
        usage = MediaUsage(unit="video_second", count=120)
        result = StepResult(hook_metadata={"media_usage": usage})
        acc.account(result, provider="openai", model="dall-e-3",
                    pricing_rows=DEFAULT_MEDIA_PRICING)
        assert len(acc.lines) == 1
        assert acc.lines[0].status == "unknown"
        assert acc.lines[0].amount_usd is None

    def test_account_malformed_nonfatal(self) -> None:
        """account() with malformed metadata appends unknown line — does not raise."""
        acc = MediaCostAccumulator()
        result = StepResult(hook_metadata={"media_usage": "malformed_string"})
        acc.account(result, provider="openai", model="dall-e-3")
        assert len(acc.lines) == 1
        assert acc.lines[0].status == "unknown"

    def test_account_custom_pricing_rows(self) -> None:
        """account() forwards pricing_rows override."""
        acc = MediaCostAccumulator()
        custom = (
            MediaPricingEntry(
                provider="acme", model="gen1", unit="render",
                cost_per_unit=Decimal("0.500"),
                source="custom_contract", status="actual",
            ),
        )
        usage = MediaUsage(unit="render", count=4)
        result = StepResult(hook_metadata={"media_usage": usage})
        acc.account(result, provider="acme", model="gen1", pricing_rows=custom)
        assert len(acc.lines) == 1
        assert acc.lines[0].amount_usd == Decimal("2.000")

    def test_accumulator_starts_empty(self) -> None:
        """Fresh MediaCostAccumulator has empty lines."""
        acc = MediaCostAccumulator()
        assert acc.lines == []

    def test_accumulator_opt_in_not_called_no_media_accounting(self) -> None:
        """When hooks don't call MediaCostAccumulator, lines remain empty."""
        acc = MediaCostAccumulator()
        # Never called — still empty
        assert acc.lines == []


# ---------------------------------------------------------------------------
# Hook integration: media accounting via custom hooks in run_pipeline
# ---------------------------------------------------------------------------


class TestMediaAccountingHookIntegration:
    """End-to-end: custom hooks accumulate media cost during run_pipeline."""

    def test_custom_hooks_with_media_accumulator(self) -> None:
        """Custom hooks that use MediaCostAccumulator in on_step_end."""

        class _MediaAwareStep:
            name = "media_step"
            kind = "compute"

            def run(self, ctx: StepContext) -> StepResult:
                usage = MediaUsage(unit="image", count=1)
                return StepResult(
                    next="halt",
                    hook_metadata={"media_usage": usage},
                )

        class _MediaHooks(NullExecutorHooks):
            def __init__(self) -> None:
                super().__init__()
                self.media = MediaCostAccumulator()

            def on_step_end(self, stage, ctx, result):
                self.media.account(result, provider="openai", model="dall-e-3",
                                   pricing_rows=DEFAULT_MEDIA_PRICING)
                return result

        pipeline = Pipeline(
            stages={"s": Stage(name="s", step=_MediaAwareStep(), edges=())},
            entry="s",
        )
        hooks = _MediaHooks()
        run_pipeline(pipeline, {}, RuntimeEnvelope(plugin_id="test", run_id="r1"),
                     hooks=hooks)
        assert len(hooks.media.lines) == 1
        assert hooks.media.lines[0].amount_usd == Decimal("0.040")

    def test_custom_hooks_no_media_no_lines(self) -> None:
        """Custom hooks where step has no media_usage → accumulator stays empty."""

        class _NoMediaStep:
            name = "no_media_step"
            kind = "compute"

            def run(self, ctx: StepContext) -> StepResult:
                return StepResult(next="halt")

        class _MediaHooks(NullExecutorHooks):
            def __init__(self) -> None:
                super().__init__()
                self.media = MediaCostAccumulator()

            def on_step_end(self, stage, ctx, result):
                self.media.account(result, provider="openai", model="dall-e-3",
                                   pricing_rows=DEFAULT_MEDIA_PRICING)
                return result

        pipeline = Pipeline(
            stages={"s": Stage(name="s", step=_NoMediaStep(), edges=())},
            entry="s",
        )
        hooks = _MediaHooks()
        run_pipeline(pipeline, {}, RuntimeEnvelope(plugin_id="test", run_id="r1"),
                     hooks=hooks)
        assert hooks.media.lines == []

    def test_null_hooks_no_media_accounting(self) -> None:
        """NullExecutorHooks does nothing — no media accounting occurs."""
        step = _SimpleStep("x", next_label="halt")
        pipeline = _single_stage_pipeline(step)
        env = RuntimeEnvelope(plugin_id="test", run_id="r1")
        # hooks=None uses NullExecutorHooks internally, which never calls
        # account_media_cost_from_result
        result = run_pipeline(pipeline, {}, env)  # hooks=None
        assert result is env
