"""Tests for ``arnold.pipeline.executor`` (T10 / SC10)."""

from __future__ import annotations

from typing import Any

import pytest

from arnold.pipeline import run_pipeline
from arnold.pipeline.types import Edge, ParallelStage, Pipeline, Stage, StepContext, StepResult
from arnold.runtime.envelope import RuntimeEnvelope
from arnold.runtime.operations import NullOperationRegistry


# ---------------------------------------------------------------------------
# Fake steps
# ---------------------------------------------------------------------------


class _RecordingStep:
    """Records each call and returns configurable outputs."""

    def __init__(
        self,
        name: str,
        kind: str,
        next_label: str = "halt",
        patch: dict[str, Any] | None = None,
    ) -> None:
        self.name = name
        self.kind = kind
        self._next = next_label
        self._patch = patch or {}
        self.calls: list[StepContext] = []

    def run(self, ctx: StepContext) -> StepResult:
        self.calls.append(ctx)
        return StepResult(
            outputs={"from": self.name},
            next=self._next,
            state_patch=self._patch,
        )


# ---------------------------------------------------------------------------
# Core execution tests
# ---------------------------------------------------------------------------


class TestRunPipeline:
    def test_two_stage_two_step_runs_to_completion(self) -> None:
        step_a = _RecordingStep("a", "compute", next_label="go", patch={"a_ran": True})
        step_b = _RecordingStep("b", "compute", next_label="halt", patch={"b_ran": True})

        pipeline = Pipeline(
            stages={
                "stage_a": Stage(
                    name="stage_a",
                    step=step_a,
                    edges=(Edge(label="go", target="stage_b"),),
                ),
                "stage_b": Stage(
                    name="stage_b",
                    step=step_b,
                    edges=(),
                ),
            },
            entry="stage_a",
        )
        env = RuntimeEnvelope(plugin_id="test", run_id="run-1")
        result = run_pipeline(pipeline, {}, env, registry=NullOperationRegistry())

        assert isinstance(result, RuntimeEnvelope)
        assert result is env
        assert len(step_a.calls) == 1
        assert len(step_b.calls) == 1

    def test_state_patches_applied_sequentially(self) -> None:
        step_a = _RecordingStep("a", "compute", next_label="next", patch={"key": "from_a"})
        step_b = _RecordingStep("b", "compute", next_label="halt", patch={"key": "from_b"})

        pipeline = Pipeline(
            stages={
                "stage_a": Stage(
                    name="stage_a",
                    step=step_a,
                    edges=(Edge(label="next", target="stage_b"),),
                ),
                "stage_b": Stage(
                    name="stage_b",
                    step=step_b,
                    edges=(),
                ),
            },
            entry="stage_a",
        )
        env = RuntimeEnvelope(plugin_id="p", run_id="r")
        run_pipeline(pipeline, {}, env)

        assert len(step_b.calls) == 1
        assert step_b.calls[0].state.get("key") == "from_a"

    def test_initial_state_is_available_to_first_step(self) -> None:
        step = _RecordingStep("s", "compute", next_label="halt", patch={})
        pipeline = Pipeline(
            stages={"s": Stage(name="s", step=step, edges=())},
            entry="s",
        )
        env = RuntimeEnvelope()
        run_pipeline(pipeline, {"seed": 99}, env)

        assert step.calls[0].state.get("seed") == 99

    def test_null_registry_accepted_without_error(self) -> None:
        step = _RecordingStep("s", "compute", next_label="halt", patch={})
        pipeline = Pipeline(
            stages={"s": Stage(name="s", step=step, edges=())},
            entry="s",
        )
        result = run_pipeline(pipeline, {}, RuntimeEnvelope(), registry=NullOperationRegistry())
        assert isinstance(result, RuntimeEnvelope)

    def test_none_registry_treated_as_null(self) -> None:
        step = _RecordingStep("s", "compute", next_label="halt", patch={})
        pipeline = Pipeline(
            stages={"s": Stage(name="s", step=step, edges=())},
            entry="s",
        )
        result = run_pipeline(pipeline, {}, RuntimeEnvelope(), registry=None)
        assert isinstance(result, RuntimeEnvelope)

    def test_halt_edge_target_stops_before_next_stage(self) -> None:
        step_a = _RecordingStep("a", "compute", next_label="stop", patch={})
        step_b = _RecordingStep("b", "compute", next_label="halt", patch={})

        pipeline = Pipeline(
            stages={
                "stage_a": Stage(
                    name="stage_a",
                    step=step_a,
                    edges=(Edge(label="stop", target="halt"),),
                ),
                "stage_b": Stage(
                    name="stage_b",
                    step=step_b,
                    edges=(),
                ),
            },
            entry="stage_a",
        )
        run_pipeline(pipeline, {}, RuntimeEnvelope())

        assert len(step_a.calls) == 1
        assert len(step_b.calls) == 0

    def test_halt_step_next_stops_without_edge(self) -> None:
        step = _RecordingStep("s", "compute", next_label="halt", patch={})
        pipeline = Pipeline(
            stages={"s": Stage(name="s", step=step, edges=())},
            entry="s",
        )
        run_pipeline(pipeline, {}, RuntimeEnvelope())
        assert len(step.calls) == 1

    def test_missing_edge_terminates_gracefully(self) -> None:
        step = _RecordingStep("s", "compute", next_label="no_such_edge", patch={})
        pipeline = Pipeline(
            stages={"s": Stage(name="s", step=step, edges=())},
            entry="s",
        )
        run_pipeline(pipeline, {}, RuntimeEnvelope())
        assert len(step.calls) == 1

    def test_envelope_returned_unchanged(self) -> None:
        step = _RecordingStep("s", "compute", next_label="halt", patch={"x": 1})
        pipeline = Pipeline(
            stages={"s": Stage(name="s", step=step, edges=())},
            entry="s",
        )
        env = RuntimeEnvelope(plugin_id="p", run_id="r-orig")
        result = run_pipeline(pipeline, {}, env)
        assert result is env
        assert result.plugin_id == "p"


# ---------------------------------------------------------------------------
# Zero-megaplan-imports guard
# ---------------------------------------------------------------------------


class TestExecutorBoundary:
    def test_executor_module_has_no_megaplan_import(self) -> None:
        import ast
        import importlib.util
        import pathlib

        src = pathlib.Path(__file__).parents[3] / "arnold" / "pipeline" / "executor.py"
        tree = ast.parse(src.read_text())
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        assert not alias.name.startswith("megaplan"), (
                            f"executor.py imports megaplan: {alias.name!r}"
                        )
                else:
                    assert node.module is None or not node.module.startswith("megaplan"), (
                        f"executor.py imports from megaplan: {node.module!r}"
                    )

    def test_run_pipeline_reexported_from_arnold_pipeline(self) -> None:
        from arnold.pipeline import run_pipeline as rp
        assert rp is run_pipeline
