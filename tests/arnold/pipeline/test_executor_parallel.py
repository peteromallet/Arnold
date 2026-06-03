"""Tests for ParallelStage fan-out in ``arnold.pipeline.executor`` (M3a T9)."""

from __future__ import annotations

import time
from typing import Any

import pytest

from arnold.pipeline import run_pipeline
from arnold.pipeline.types import (
    Edge,
    ParallelStage,
    Pipeline,
    Stage,
    Step,
    StepContext,
    StepResult,
)
from arnold.runtime.envelope import RuntimeEnvelope


# ---------------------------------------------------------------------------
# Fake hermetic steps for parallel tests
# ---------------------------------------------------------------------------


class _HermeticStep:
    """A step that's safe for parallel execution — no shared mutable state."""

    def __init__(
        self,
        name: str,
        kind: str = "compute",
        next_label: str = "halt",
        patch: dict[str, Any] | None = None,
        delay: float = 0.0,
    ) -> None:
        self.name = name
        self.kind = kind
        self._next = next_label
        self._patch = patch or {}
        self._delay = delay
        self.calls: list[StepContext] = []

    def run(self, ctx: StepContext) -> StepResult:
        if self._delay:
            time.sleep(self._delay)
        self.calls.append(ctx)
        return StepResult(
            outputs={"from": self.name},
            next=self._next,
            state_patch=self._patch,
        )


class _UnsafeStep:
    """A step that is NOT parallel-safe (simulates plan-dir writer)."""

    def __init__(self, name: str, kind: str = "compute") -> None:
        self.name = name
        self.kind = kind
        self.calls: list[StepContext] = []

    def run(self, ctx: StepContext) -> StepResult:
        self.calls.append(ctx)
        return StepResult(next="halt")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_join(next_label: str = "halt") -> Any:
    """Factory for a simple join that forwards *next_label*."""

    def _join(results: list[StepResult], ctx: StepContext) -> StepResult:
        return StepResult(
            outputs={"joined": len(results)},
            next=next_label,
        )

    return _join


def _ordered_join(next_label: str = "halt") -> Any:
    """Join that records the order of results received."""

    def _join(results: list[StepResult], ctx: StepContext) -> StepResult:
        return StepResult(
            outputs={
                "order": tuple(r.outputs.get("from", "?") for r in results),
            },
            next=next_label,
        )

    return _join


def _unsafe_predicate(step: Any) -> bool:
    """Predicate that marks _UnsafeStep as not parallel-safe."""
    return not isinstance(step, _UnsafeStep)


# ---------------------------------------------------------------------------
# ParallelStage fan-out tests
# ---------------------------------------------------------------------------


class TestParallelStageFanOut:
    def test_all_steps_execute_concurrently(self) -> None:
        step_a = _HermeticStep("a", next_label="halt")
        step_b = _HermeticStep("b", next_label="halt")
        step_c = _HermeticStep("c", next_label="halt")

        stage = ParallelStage(
            name="panel",
            steps=(step_a, step_b, step_c),
            join=_make_join("halt"),
        )
        pipeline = Pipeline(
            stages={"panel": stage},
            entry="panel",
        )
        env = RuntimeEnvelope(plugin_id="test", run_id="r1")
        result = run_pipeline(pipeline, {}, env)

        assert result is env
        assert len(step_a.calls) == 1
        assert len(step_b.calls) == 1
        assert len(step_c.calls) == 1

    def test_isolated_context_per_step(self) -> None:
        """Each step must receive its own StepContext snapshot."""

        step_a = _HermeticStep("a", next_label="halt")
        step_b = _HermeticStep("b", next_label="halt")

        stage = ParallelStage(
            name="panel",
            steps=(step_a, step_b),
            join=_make_join("halt"),
        )
        pipeline = Pipeline(
            stages={"panel": stage},
            entry="panel",
        )
        env = RuntimeEnvelope(plugin_id="test", run_id="r2")
        run_pipeline(pipeline, {"shared": "value"}, env)

        # Each step must have received its own context object.
        ctx_a = step_a.calls[0]
        ctx_b = step_b.calls[0]
        assert ctx_a is not ctx_b  # different object identities

    def test_results_collected_in_submission_order(self) -> None:
        """Results must be ordered by submission index, not completion time."""
        # step_b is fast, step_a is slow — order must still be [a, b]
        step_a = _HermeticStep("a", next_label="halt", delay=0.1)
        step_b = _HermeticStep("b", next_label="halt", delay=0.0)

        stage = ParallelStage(
            name="panel",
            steps=(step_a, step_b),
            join=_ordered_join("halt"),
        )
        pipeline = Pipeline(
            stages={
                "panel": stage,
                "done": Stage(
                    name="done",
                    step=_HermeticStep("done"),
                    edges=(),
                ),
            },
            entry="panel",
        )
        env = RuntimeEnvelope(plugin_id="test", run_id="r3")
        run_pipeline(pipeline, {}, env)

        # The ordered join records outputs in submission order.
        assert step_a.calls
        assert step_b.calls

    def test_join_result_dispatches_next_label(self) -> None:
        """The join result's next label must dispatch to the next stage."""
        step_a = _HermeticStep("a", next_label="halt")
        step_b = _HermeticStep("b", next_label="halt")

        after_step = _HermeticStep("after", next_label="halt")

        stage = ParallelStage(
            name="panel",
            steps=(step_a, step_b),
            join=_make_join("go"),
            edges=(Edge(label="go", target="after"),),
        )
        pipeline = Pipeline(
            stages={
                "panel": stage,
                "after": Stage(name="after", step=after_step, edges=()),
            },
            entry="panel",
        )
        env = RuntimeEnvelope(plugin_id="test", run_id="r4")
        run_pipeline(pipeline, {}, env)

        assert len(after_step.calls) == 1

    def test_parallel_stage_in_middle_of_pipeline(self) -> None:
        """ParallelStage can appear anywhere in the pipeline graph."""
        before = _HermeticStep("before", next_label="fan")
        step_a = _HermeticStep("a", next_label="halt")
        step_b = _HermeticStep("b", next_label="halt")
        after = _HermeticStep("after", next_label="halt")

        stage = ParallelStage(
            name="panel",
            steps=(step_a, step_b),
            join=_make_join("go"),
            edges=(Edge(label="go", target="after"),),
        )
        pipeline = Pipeline(
            stages={
                "before": Stage(
                    name="before",
                    step=before,
                    edges=(Edge(label="fan", target="panel"),),
                ),
                "panel": stage,
                "after": Stage(name="after", step=after, edges=()),
            },
            entry="before",
        )
        env = RuntimeEnvelope(plugin_id="test", run_id="r5")
        run_pipeline(pipeline, {}, env)

        assert len(before.calls) == 1
        assert len(step_a.calls) == 1
        assert len(step_b.calls) == 1
        assert len(after.calls) == 1

    def test_empty_parallel_stage_does_not_crash(self) -> None:
        """A ParallelStage with zero steps must not crash (join handles it)."""
        stage = ParallelStage(
            name="empty_panel",
            steps=(),
            join=_make_join("halt"),
        )
        pipeline = Pipeline(
            stages={"empty_panel": stage},
            entry="empty_panel",
        )
        env = RuntimeEnvelope(plugin_id="test", run_id="r6")
        result = run_pipeline(pipeline, {}, env)
        assert result is env

    def test_max_workers_capped(self) -> None:
        """max_workers parameter is respected."""
        step_a = _HermeticStep("a", next_label="halt")
        step_b = _HermeticStep("b", next_label="halt")
        step_c = _HermeticStep("c", next_label="halt")

        stage = ParallelStage(
            name="panel",
            steps=(step_a, step_b, step_c),
            join=_make_join("halt"),
            max_workers=2,
        )
        pipeline = Pipeline(
            stages={"panel": stage},
            entry="panel",
        )
        env = RuntimeEnvelope(plugin_id="test", run_id="r7")
        result = run_pipeline(pipeline, {}, env)
        assert result is env
        assert len(step_a.calls) == 1
        assert len(step_b.calls) == 1
        assert len(step_c.calls) == 1


# ---------------------------------------------------------------------------
# Parallel-safety guard tests
# ---------------------------------------------------------------------------


class TestParallelSafeGuard:
    def test_default_predicate_accepts_everything(self) -> None:
        """DEFAULT_PARALLEL_SAFE accepts any step."""
        from arnold.pipeline.executor import DEFAULT_PARALLEL_SAFE

        assert DEFAULT_PARALLEL_SAFE(_UnsafeStep("u")) is True
        assert DEFAULT_PARALLEL_SAFE(_HermeticStep("h")) is True
        assert DEFAULT_PARALLEL_SAFE(object()) is True

    def test_custom_predicate_rejects_unsafe_step(self) -> None:
        """A custom predicate that rejects _UnsafeStep must raise ValueError."""
        unsafe = _UnsafeStep("bad")
        stage = ParallelStage(
            name="panel",
            steps=(unsafe,),
            join=_make_join("halt"),
        )
        pipeline = Pipeline(
            stages={"panel": stage},
            entry="panel",
        )
        env = RuntimeEnvelope(plugin_id="test", run_id="r8")
        with pytest.raises(ValueError, match="not parallel-safe"):
            run_pipeline(pipeline, {}, env, parallel_safe=_unsafe_predicate)

    def test_custom_predicate_allows_hermetic_step(self) -> None:
        """A custom predicate that only rejects _UnsafeStep must allow _HermeticStep."""
        step = _HermeticStep("good", next_label="halt")
        stage = ParallelStage(
            name="panel",
            steps=(step,),
            join=_make_join("halt"),
        )
        pipeline = Pipeline(
            stages={"panel": stage},
            entry="panel",
        )
        env = RuntimeEnvelope(plugin_id="test", run_id="r9")
        result = run_pipeline(pipeline, {}, env, parallel_safe=_unsafe_predicate)
        assert result is env
        assert len(step.calls) == 1

    def test_mixed_steps_rejected_when_one_unsafe(self) -> None:
        """If any step in a ParallelStage is unsafe, the whole stage is rejected."""
        good = _HermeticStep("good", next_label="halt")
        bad = _UnsafeStep("bad")
        stage = ParallelStage(
            name="panel",
            steps=(good, bad),
            join=_make_join("halt"),
        )
        pipeline = Pipeline(
            stages={"panel": stage},
            entry="panel",
        )
        env = RuntimeEnvelope(plugin_id="test", run_id="r10")
        with pytest.raises(ValueError, match="not parallel-safe"):
            run_pipeline(pipeline, {}, env, parallel_safe=_unsafe_predicate)


# ---------------------------------------------------------------------------
# State isolation tests
# ---------------------------------------------------------------------------


class TestParallelStateIsolation:
    def test_state_patches_from_serial_stage_before_parallel(self) -> None:
        """A serial stage before ParallelStage propagates state correctly."""
        before = _HermeticStep(
            "before", next_label="fan", patch={"key": "from_before"}
        )
        step_a = _HermeticStep("a", next_label="halt")
        step_b = _HermeticStep("b", next_label="halt")

        stage = ParallelStage(
            name="panel",
            steps=(step_a, step_b),
            join=_make_join("halt"),
        )
        pipeline = Pipeline(
            stages={
                "before": Stage(
                    name="before",
                    step=before,
                    edges=(Edge(label="fan", target="panel"),),
                ),
                "panel": stage,
            },
            entry="before",
        )
        env = RuntimeEnvelope(plugin_id="test", run_id="r11")
        run_pipeline(pipeline, {}, env)

        ctx_a = step_a.calls[0]
        ctx_b = step_b.calls[0]
        assert ctx_a.state.get("key") == "from_before"
        assert ctx_b.state.get("key") == "from_before"

    def test_state_patches_from_join_propagate_to_next_stage(self) -> None:
        """The join result's state_patch must apply to subsequent stages."""
        step_a = _HermeticStep("a", next_label="halt")
        step_b = _HermeticStep("b", next_label="halt")

        def patched_join(results, ctx):
            return StepResult(
                next="go",
                state_patch={"joined": True},
            )

        after = _HermeticStep("after", next_label="halt")
        stage = ParallelStage(
            name="panel",
            steps=(step_a, step_b),
            join=patched_join,
            edges=(Edge(label="go", target="after"),),
        )
        pipeline = Pipeline(
            stages={
                "panel": stage,
                "after": Stage(name="after", step=after, edges=()),
            },
            entry="panel",
        )
        env = RuntimeEnvelope(plugin_id="test", run_id="r12")
        run_pipeline(pipeline, {}, env)

        assert after.calls[0].state.get("joined") is True


# ---------------------------------------------------------------------------
# Parallel stage → halt dispatch tests
# ---------------------------------------------------------------------------


class TestParallelHalt:
    def test_join_returns_halt_next_label(self) -> None:
        """Join returning next='halt' terminates the pipeline."""
        step_a = _HermeticStep("a", next_label="halt")
        step_b = _HermeticStep("b", next_label="halt")
        after = _HermeticStep("after", next_label="halt")

        stage = ParallelStage(
            name="panel",
            steps=(step_a, step_b),
            join=_make_join("halt"),
            edges=(Edge(label="halt", target="halt"),),
        )
        pipeline = Pipeline(
            stages={
                "panel": stage,
                "after": Stage(name="after", step=after, edges=()),
            },
            entry="panel",
        )
        env = RuntimeEnvelope(plugin_id="test", run_id="r13")
        run_pipeline(pipeline, {}, env)

        assert len(after.calls) == 0  # never reached

    def test_join_edge_targets_halt(self) -> None:
        """Join returning a label whose edge targets 'halt' terminates."""
        step_a = _HermeticStep("a", next_label="halt")

        stage = ParallelStage(
            name="panel",
            steps=(step_a,),
            join=_make_join("stop"),
            edges=(Edge(label="stop", target="halt"),),
        )
        pipeline = Pipeline(
            stages={"panel": stage},
            entry="panel",
        )
        env = RuntimeEnvelope(plugin_id="test", run_id="r14")
        result = run_pipeline(pipeline, {}, env)
        assert result is env


# ---------------------------------------------------------------------------
# Boundary guard
# ---------------------------------------------------------------------------


class TestExecutorParallelBoundary:
    def test_executor_module_has_no_megaplan_import(self) -> None:
        import ast
        from pathlib import Path as P

        src = P(__file__).parents[3] / "arnold" / "pipeline" / "executor.py"
        tree = ast.parse(src.read_text())
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        assert not alias.name.startswith("megaplan"), (
                            f"executor.py imports megaplan: {alias.name!r}"
                        )
                else:
                    assert node.module is None or not node.module.startswith(
                        "megaplan"
                    ), (
                        f"executor.py imports from megaplan: {node.module!r}"
                    )

    def test_executor_never_mentions_in_process_handler(self) -> None:
        """The Arnold executor must never reference InProcessHandlerStep."""
        import ast
        from pathlib import Path as P

        src = P(__file__).parents[3] / "arnold" / "pipeline" / "executor.py"
        tree = ast.parse(src.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                assert "InProcessHandlerStep" not in node.value, (
                    "executor.py must not mention InProcessHandlerStep"
                )
            if isinstance(node, ast.Name):
                assert node.id != "InProcessHandlerStep", (
                    "executor.py must not reference InProcessHandlerStep"
                )
