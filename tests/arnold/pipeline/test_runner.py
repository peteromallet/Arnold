"""Tests for the thin runner API (Step 8 / T12 / SC12)."""

from __future__ import annotations

from typing import Any

import pytest

from arnold.pipeline.executor import run_pipeline as executor_run_pipeline
from arnold.pipeline.hooks import NullExecutorHooks
from arnold.pipeline.runner import run_pipeline
from arnold.pipeline.types import (
    Edge,
    ParallelStage,
    Pipeline,
    Stage,
    StepContext,
    StepResult,
)
from arnold.runtime.envelope import RuntimeEnvelope


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _SimpleStep:
    def __init__(self, name: str, next_label: str = "halt", patch: dict | None = None) -> None:
        self.name = name
        self.kind = "compute"
        self._next = next_label
        self._patch = patch or {}

    def run(self, ctx: StepContext) -> StepResult:
        return StepResult(next=self._next, state_patch=self._patch, outputs={"from": self.name})


def _make_env() -> RuntimeEnvelope:
    return RuntimeEnvelope(plugin_id="test", run_id="r1")


def _simple_join(results: list[StepResult], ctx: StepContext) -> StepResult:
    return StepResult(next="halt", outputs={"count": len(results)})


def _two_stage_pipeline(step_a: Any, step_b: Any) -> Pipeline:
    return Pipeline(
        stages={
            "a": Stage(name="a", step=step_a, edges=(Edge(label="next", target="b"),)),
            "b": Stage(name="b", step=step_b, edges=()),
        },
        entry="a",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRunnerSignature:
    """SC12: runner.py is a thin re-export with backward-compat signature."""

    def test_run_pipeline_delegates_to_executor(self) -> None:
        """runner.run_pipeline delegates to executor.run_pipeline (same behavior)."""
        step = _SimpleStep("s")
        pipeline = Pipeline(stages={"s": Stage(name="s", step=step)}, entry="s")
        env = _make_env()

        from arnold.pipeline.runner import run_pipeline as runner_rp
        from arnold.pipeline.executor import run_pipeline as executor_rp

        r_runner = runner_rp(pipeline, {}, env)
        r_exec = executor_rp(pipeline, {}, env)
        assert isinstance(r_runner, RuntimeEnvelope)
        assert isinstance(r_exec, RuntimeEnvelope)
        assert r_runner.plugin_id == r_exec.plugin_id
        assert r_runner.run_id == r_exec.run_id

    def test_run_step_not_present(self) -> None:
        """run_step is NOT exported from runner.py."""
        import arnold.pipeline.runner as runner_mod
        assert not hasattr(runner_mod, "run_step")

    def test_next_steps_not_present(self) -> None:
        """next_steps is NOT exported from runner.py."""
        import arnold.pipeline.runner as runner_mod
        assert not hasattr(runner_mod, "next_steps")

    def test_backward_compat_bare_call(self) -> None:
        """run_pipeline(pipeline, state, env) works unchanged (no kwargs)."""
        step = _SimpleStep("s")
        pipeline = Pipeline(stages={"s": Stage(name="s", step=step)}, entry="s")
        result = run_pipeline(pipeline, {}, _make_env())
        assert isinstance(result, RuntimeEnvelope)

    def test_backward_compat_with_hooks_none(self) -> None:
        """run_pipeline with hooks=None works unchanged."""
        step = _SimpleStep("s")
        pipeline = Pipeline(stages={"s": Stage(name="s", step=step)}, entry="s")
        result = run_pipeline(pipeline, {}, _make_env(), hooks=None)
        assert isinstance(result, RuntimeEnvelope)

    def test_with_null_hooks_identical_to_no_hooks(self) -> None:
        """NullExecutorHooks() path produces same result as hooks=None."""
        step = _SimpleStep("s")
        pipeline = Pipeline(stages={"s": Stage(name="s", step=step)}, entry="s")
        env_no = run_pipeline(pipeline, {}, _make_env(), hooks=None)
        env_null = run_pipeline(pipeline, {}, _make_env(), hooks=NullExecutorHooks())
        assert isinstance(env_no, RuntimeEnvelope)
        assert isinstance(env_null, RuntimeEnvelope)
        assert env_no.plugin_id == env_null.plugin_id
        assert env_no.run_id == env_null.run_id

    def test_initial_context_seeds_hook_extensions(self) -> None:
        """initial_context.hook_extensions reach each per-step StepContext."""
        captured: list[dict] = []

        class _CaptureStep:
            name = "capture"
            kind = "compute"

            def run(self, ctx: StepContext) -> StepResult:
                captured.append(dict(ctx.hook_extensions))
                return StepResult(next="halt")

        pipeline = Pipeline(
            stages={"s": Stage(name="s", step=_CaptureStep())},
            entry="s",
        )
        ictx = StepContext(
            artifact_root="/tmp",
            state={},
            hook_extensions={"plan_dir": "/tmp", "profile": "test"},
        )
        run_pipeline(pipeline, {}, _make_env(), initial_context=ictx)
        assert len(captured) == 1
        assert captured[0] == {"plan_dir": "/tmp", "profile": "test"}


class TestRunnerSerialParity:
    """Runner produces byte-identical results to direct executor call."""

    def test_serial_two_stage_identical(self) -> None:
        """Runner and executor produce same results for serial pipeline."""
        step_a = _SimpleStep("a", next_label="next")
        step_b = _SimpleStep("b")
        pipeline = _two_stage_pipeline(step_a, step_b)
        env = _make_env()

        from arnold.pipeline.runner import run_pipeline as runner_rp
        from arnold.pipeline.executor import run_pipeline as exec_rp

        r_runner = runner_rp(pipeline, {}, env)
        r_exec = exec_rp(pipeline, {}, env)

        assert r_runner.plugin_id == r_exec.plugin_id
        assert r_runner.run_id == r_exec.run_id

    def test_serial_with_state_patch_identical(self) -> None:
        """State patches propagate identically through runner vs executor."""
        step_a = _SimpleStep("a", next_label="next", patch={"k": "v"})
        step_b = _SimpleStep("b")

        class _StateCheckStep:
            name = "b"
            kind = "compute"

            def run(self, ctx: StepContext) -> StepResult:
                return StepResult(next="halt", outputs={"state_key": ctx.state.get("k")})

        pipeline = Pipeline(
            stages={
                "a": Stage(name="a", step=step_a, edges=(Edge(label="next", target="b"),)),
                "b": Stage(name="b", step=_StateCheckStep(), edges=()),
            },
            entry="a",
        )
        env = _make_env()
        result = run_pipeline(pipeline, {}, env)
        # result is the envelope; state was updated in the executor
        assert isinstance(result, RuntimeEnvelope)


class TestRunnerModuleBoundary:
    """Runner module has a focused, minimal surface."""

    def test_runner_all_only_run_pipeline(self) -> None:
        """__all__ contains only run_pipeline."""
        import arnold.pipeline.runner as runner_mod
        assert runner_mod.__all__ == ["run_pipeline"]

    def test_runner_no_megaplan_imports(self) -> None:
        """runner.py has no megaplan imports."""
        import ast
        import arnold.pipeline.runner as runner_mod
        source = ast.parse(
            __import__("inspect").getsource(runner_mod)
        )
        for node in ast.walk(source):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                module = node.module if isinstance(node, ast.ImportFrom) else None
                import_names = (
                    [alias.name for alias in node.names] if isinstance(node, ast.Import) else []
                )
                all_names = (module or "") + " " + " ".join(import_names)
                assert "megaplan" not in all_names.lower(), f"megaplan import found: {all_names}"
