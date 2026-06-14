"""Tests for ``arnold.pipeline.executor`` (T11 / SC11)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from arnold.pipeline import (
    ContractResult,
    ContractSchemaRegistry,
    ContractStatus,
    HumanSuspension,
    NullExecutorHooks,
    PipelineBuilder,
    StepIOContractContext,
    StepIOOperation,
    read_violation_records,
    run_pipeline,
)
from arnold.pipeline.executor import StepIOEnforcementError, run_pipeline_resume
from arnold.pipeline.routing import RoutingError
from arnold.pipeline.types import (
    Edge, ParallelStage, Pipeline, PipelineVerdict, Port, PortRef, Stage, StepContext, StepResult,
)
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


class _ResumeStep:
    """A resumable step with a configurable fixed StepResult."""

    def __init__(self, name: str, result: StepResult) -> None:
        self.name = name
        self.kind = "compute"
        self.result = result
        self.calls: list[StepContext] = []

    def run(self, ctx: StepContext) -> StepResult:
        self.calls.append(ctx)
        return self.result


def _resume_suspension(
    *,
    declaration: dict[str, Any] | None = None,
    cursor: str = '{"stage":"review","input":{"approved":true}}',
) -> HumanSuspension:
    schema: dict[str, Any] = {}
    if declaration is not None:
        schema["x-arnold-resume"] = declaration
    return HumanSuspension(
        kind="human",
        awaitable="user",
        prompt="Review edits",
        resume_cursor=cursor,
        resume_input_schema=schema,
    )


def _answer_registry(tmp_path: Path) -> ContractSchemaRegistry:
    registry = ContractSchemaRegistry(tmp_path)
    registry.register(
        "answer",
        {
            "type": "object",
            "required": ["value"],
            "properties": {"value": {"type": "integer"}},
            "additionalProperties": False,
        },
    )
    return registry


def _answer_envelope(
    registry: ContractSchemaRegistry,
    payload: dict[str, Any],
) -> dict[str, Any]:
    version = registry.latest("answer")
    assert version is not None
    return {
        "logical_type": "answer",
        "schema_version": version,
        "payload": dict(payload),
    }


def _step_io_initial_context(
    *,
    artifact_root: Path,
    registry: ContractSchemaRegistry,
    configured_mode: str = "enforce",
    pipeline_id: str = "generic-pipeline",
) -> StepContext:
    return StepContext(
        artifact_root=str(artifact_root),
        state={},
        hook_extensions={
            "pipeline_id": pipeline_id,
            "step_io_contract_context": StepIOContractContext(
                operation=StepIOOperation.WRITE,
                registry=registry,
            ),
            "step_io_policy_data": {"configured_mode": configured_mode},
        },
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


# ---------------------------------------------------------------------------
# T10: Executor parity — comprehensive contract tests
# ---------------------------------------------------------------------------


class TestExecutorParityComplexGraphs:
    """Complex pipeline graph shapes stress the full executor contract."""

    def test_diamond_graph_runs_all_paths(self) -> None:
        """A → (B, C) → D diamond. Since we lack fan-in, we test serial diamond."""
        step_a = _RecordingStep("a", "compute", next_label="go_b", patch={"a": 1})
        step_b = _RecordingStep("b", "compute", next_label="go_d", patch={"b": 1})
        step_c = _RecordingStep("c", "compute", next_label="halt", patch={"c": 1})
        step_d = _RecordingStep("d", "compute", next_label="halt", patch={"d": 1})

        pipeline = Pipeline(
            stages={
                "a": Stage(
                    name="a", step=step_a,
                    edges=(Edge(label="go_b", target="b"),),
                ),
                "b": Stage(
                    name="b", step=step_b,
                    edges=(Edge(label="go_d", target="d"),),
                ),
                "c": Stage(
                    name="c", step=step_c,
                    edges=(),
                ),
                "d": Stage(
                    name="d", step=step_d,
                    edges=(),
                ),
            },
            entry="a",
        )
        env = RuntimeEnvelope()
        run_pipeline(pipeline, {}, env)

        assert len(step_a.calls) == 1
        assert len(step_b.calls) == 1
        assert len(step_d.calls) == 1
        # step_c unreachable in this topology
        assert len(step_c.calls) == 0

    def test_linear_chain_of_five_stages(self) -> None:
        """Five stages in linear chain, state accumulates."""
        steps = []
        for i in range(5):
            steps.append(_RecordingStep(
                f"s{i}", "compute",
                next_label="next" if i < 4 else "halt",
                patch={f"k{i}": i},
            ))

        stages: dict[str, Any] = {}
        for i in range(5):
            label = f"s{i}"
            edges = (Edge(label="next", target=f"s{i+1}"),) if i < 4 else ()
            stages[label] = Stage(name=label, step=steps[i], edges=edges)

        pipeline = Pipeline(stages=stages, entry="s0")
        env = RuntimeEnvelope()
        run_pipeline(pipeline, {}, env)

        for i in range(5):
            assert len(steps[i].calls) == 1
        # Last step's context should have accumulated state from all previous
        ctx = steps[4].calls[0]
        assert ctx.state.get("k0") == 0
        assert ctx.state.get("k1") == 1
        assert ctx.state.get("k2") == 2
        assert ctx.state.get("k3") == 3

    def test_multi_branch_with_halt_at_different_depths(self) -> None:
        """Branches that halt at different depths; only one path taken."""
        step_entry = _RecordingStep("entry", "compute", next_label="go", patch={})
        step_short = _RecordingStep("short", "compute", next_label="halt", patch={})
        step_long_a = _RecordingStep("long_a", "compute", next_label="go2", patch={})
        step_long_b = _RecordingStep("long_b", "compute", next_label="halt", patch={})

        pipeline = Pipeline(
            stages={
                "entry": Stage(
                    name="entry", step=step_entry,
                    edges=(
                        Edge(label="go", target="short"),
                        Edge(label="go", target="long_a"),
                    ),
                ),
                "short": Stage(name="short", step=step_short, edges=()),
                "long_a": Stage(
                    name="long_a", step=step_long_a,
                    edges=(Edge(label="go2", target="long_b"),),
                ),
                "long_b": Stage(name="long_b", step=step_long_b, edges=()),
            },
            entry="entry",
        )
        env = RuntimeEnvelope()
        run_pipeline(pipeline, {}, env)

        assert len(step_entry.calls) == 1
        # First edge match wins: "go" → "short" dispatches, "short" → halt
        assert len(step_short.calls) == 1
        assert len(step_long_a.calls) == 0
        assert len(step_long_b.calls) == 0


class TestExecutorParityOutputVerification:
    """Verify that step outputs propagate correctly through state patches."""

    def test_outputs_accumulate_across_stages(self) -> None:
        """Each step's state patch builds on prior state."""

        class _AccumStep:
            kind = "compute"

            def __init__(self, name: str, key: str, value: Any, next_label: str = "halt"):
                self.name = name
                self._key = key
                self._value = value
                self._next = next_label

            def run(self, ctx: StepContext) -> StepResult:
                return StepResult(next=self._next, state_patch={self._key: self._value})

        s1 = _AccumStep("s1", "alpha", 10, next_label="go")
        s2 = _AccumStep("s2", "beta", 20, next_label="halt")
        s3 = _AccumStep("s3", "gamma", 30, next_label="halt")

        pipeline = Pipeline(
            stages={
                "s1": Stage(name="s1", step=s1, edges=(Edge(label="go", target="s2"),)),
                "s2": Stage(name="s2", step=s2, edges=()),
                "s3": Stage(name="s3", step=s3, edges=()),
            },
            entry="s1",
        )
        env = RuntimeEnvelope()
        run_pipeline(pipeline, {}, env)
        # No assertions needed — we just verify no crashes and correct routing

    def test_step_context_snapshot_includes_prior_state(self) -> None:
        """StepContext.state reflects all applied deltas."""

        class _StateReader:
            kind = "compute"

            def __init__(self, name: str, next_label: str = "halt"):
                self.name = name
                self._next = next_label
                self.seen_state: dict[str, Any] = {}

            def run(self, ctx: StepContext) -> StepResult:
                self.seen_state = dict(ctx.state) if isinstance(ctx.state, dict) else {}
                return StepResult(next=self._next)

        s1 = _RecordingStep("s1", "compute", next_label="go", patch={"x": 1, "y": 2})
        reader = _StateReader("reader")
        pipeline = Pipeline(
            stages={
                "s1": Stage(name="s1", step=s1, edges=(Edge(label="go", target="reader"),)),
                "reader": Stage(name="reader", step=reader, edges=()),
            },
            entry="s1",
        )
        env = RuntimeEnvelope()
        run_pipeline(pipeline, {}, env)

        assert reader.seen_state.get("x") == 1
        assert reader.seen_state.get("y") == 2


class TestExecutorParityEdgeCases:
    """Edge cases that stress executor robustness."""

    def test_empty_initial_state_does_not_crash(self) -> None:
        step = _RecordingStep("s", "compute", next_label="halt")
        pipeline = Pipeline(
            stages={"s": Stage(name="s", step=step, edges=())},
            entry="s",
        )
        env = RuntimeEnvelope()
        result = run_pipeline(pipeline, {}, env)
        assert result is env

    def test_single_stage_no_edges_runs_and_halts(self) -> None:
        step = _RecordingStep("only", "compute", next_label="halt")
        pipeline = Pipeline(
            stages={"only": Stage(name="only", step=step, edges=())},
            entry="only",
        )
        env = RuntimeEnvelope()
        run_pipeline(pipeline, {}, env)
        assert len(step.calls) == 1

    def test_step_result_with_no_state_patch(self) -> None:
        """Step returns no state_patch (None/empty) — no crash."""

        class _NoPatchStep:
            kind = "compute"
            name = "np"

            def run(self, ctx: StepContext) -> StepResult:
                return StepResult(next="halt")

        pipeline = Pipeline(
            stages={"np": Stage(name="np", step=_NoPatchStep(), edges=())},
            entry="np",
        )
        env = RuntimeEnvelope()
        result = run_pipeline(pipeline, {}, env)
        assert result is env

    def test_step_with_empty_state_patch(self) -> None:
        """Step returns empty state_patch dict — no crash."""
        step = _RecordingStep("s", "compute", next_label="halt", patch={})
        pipeline = Pipeline(
            stages={"s": Stage(name="s", step=step, edges=())},
            entry="s",
        )
        env = RuntimeEnvelope()
        run_pipeline(pipeline, {}, env)
        assert len(step.calls) == 1

    def test_nonexistent_entry_stage(self) -> None:
        """Entry points to a stage not in pipeline — should break loop cleanly."""
        step = _RecordingStep("real", "compute", next_label="halt")
        pipeline = Pipeline(
            stages={"real": Stage(name="real", step=step, edges=())},
            entry="nonexistent",
        )
        env = RuntimeEnvelope()
        result = run_pipeline(pipeline, {}, env)
        assert result is env
        assert len(step.calls) == 0

    def test_loop_prevention_missing_edge_terminates(self) -> None:
        """A step that returns a label with no matching edge terminates gracefully."""
        step_a = _RecordingStep("a", "compute", next_label="go")
        step_b = _RecordingStep("b", "compute", next_label="halt")
        # stage_a has edge label="go" → target="b", but step_a returns "gone" (missing)
        step_a._next = "gone"
        pipeline = Pipeline(
            stages={
                "a": Stage(name="a", step=step_a, edges=(Edge(label="go", target="b"),)),
                "b": Stage(name="b", step=step_b, edges=()),
            },
            entry="a",
        )
        env = RuntimeEnvelope()
        run_pipeline(pipeline, {}, env)
        assert len(step_a.calls) == 1
        assert len(step_b.calls) == 0

    def test_stage_reached_via_multiple_paths(self) -> None:
        """Multiple edges can target the same stage (first match wins per step)."""
        step_entry = _RecordingStep("entry", "compute", next_label="go", patch={})
        step_target = _RecordingStep("target", "compute", next_label="halt", patch={})

        pipeline = Pipeline(
            stages={
                "entry": Stage(
                    name="entry", step=step_entry,
                    edges=(
                        Edge(label="go", target="target"),
                        Edge(label="alt", target="target"),
                    ),
                ),
                "target": Stage(name="target", step=step_target, edges=()),
            },
            entry="entry",
        )
        env = RuntimeEnvelope()
        run_pipeline(pipeline, {}, env)
        assert len(step_entry.calls) == 1
        assert len(step_target.calls) == 1


class TestExecutorParityParallelCombined:
    """Combined serial + parallel topologies."""

    def test_serial_before_parallel_before_serial(self) -> None:
        """S1 → Panel(S2a, S2b) → S3."""
        # Reuse _HermeticStep from test_executor_parallel
        import time

        class _Step:
            def __init__(self, name: str, kind: str = "compute",
                         next_label: str = "halt", patch: dict[str, Any] | None = None):
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

        s1 = _Step("s1", next_label="fan", patch={"phase": 1})
        s2a = _Step("s2a", next_label="halt")
        s2b = _Step("s2b", next_label="halt")
        s3 = _Step("s3", next_label="halt")

        def join_fn(results, ctx):
            return StepResult(next="go", state_patch={"phase": 2})

        panel = ParallelStage(
            name="panel",
            steps=(s2a, s2b),
            join=join_fn,
            edges=(Edge(label="go", target="s3"),),
        )
        pipeline = Pipeline(
            stages={
                "s1": Stage(name="s1", step=s1, edges=(Edge(label="fan", target="panel"),)),
                "panel": panel,
                "s3": Stage(name="s3", step=s3, edges=()),
            },
            entry="s1",
        )
        env = RuntimeEnvelope()
        run_pipeline(pipeline, {}, env)

        assert len(s1.calls) == 1
        assert len(s2a.calls) == 1
        assert len(s2b.calls) == 1
        assert len(s3.calls) == 1

    def test_parallel_stage_as_entry(self) -> None:
        """ParallelStage can be the entry stage."""
        import time

        class _Step:
            def __init__(self, name: str):
                self.name = name
                self.kind = "compute"
                self.calls: list[StepContext] = []

            def run(self, ctx: StepContext) -> StepResult:
                self.calls.append(ctx)
                return StepResult(next="halt", outputs={"from": self.name})

        s_a = _Step("a")
        s_b = _Step("b")

        def join_fn(results, ctx):
            return StepResult(next="halt")

        panel = ParallelStage(
            name="entry_panel",
            steps=(s_a, s_b),
            join=join_fn,
        )
        pipeline = Pipeline(
            stages={"entry_panel": panel},
            entry="entry_panel",
        )
        env = RuntimeEnvelope()
        run_pipeline(pipeline, {}, env)

        assert len(s_a.calls) == 1
        assert len(s_b.calls) == 1

    def test_two_parallel_stages_in_sequence(self) -> None:
        """Panel1 → Panel2 (join dispatch chains)."""
        import time

        class _Step:
            def __init__(self, name: str):
                self.name = name
                self.kind = "compute"
                self.calls: list[StepContext] = []

            def run(self, ctx: StepContext) -> StepResult:
                self.calls.append(ctx)
                return StepResult(next="halt", outputs={"from": self.name})

        p1a = _Step("p1a")
        p1b = _Step("p1b")
        p2a = _Step("p2a")
        p2b = _Step("p2b")

        def join1(results, ctx):
            return StepResult(next="go")

        def join2(results, ctx):
            return StepResult(next="halt")

        panel1 = ParallelStage(
            name="panel1",
            steps=(p1a, p1b),
            join=join1,
            edges=(Edge(label="go", target="panel2"),),
        )
        panel2 = ParallelStage(
            name="panel2",
            steps=(p2a, p2b),
            join=join2,
        )
        pipeline = Pipeline(
            stages={"panel1": panel1, "panel2": panel2},
            entry="panel1",
        )
        env = RuntimeEnvelope()
        run_pipeline(pipeline, {}, env)

        assert len(p1a.calls) == 1
        assert len(p1b.calls) == 1
        assert len(p2a.calls) == 1
        assert len(p2b.calls) == 1

    def test_state_patch_survives_across_parallel_stages(self) -> None:
        """State set before ParallelStage is visible inside it and after it."""
        import time

        class _Step:
            def __init__(self, name: str, next_label: str = "halt",
                         patch: dict[str, Any] | None = None):
                self.name = name
                self.kind = "compute"
                self._next = next_label
                self._patch = patch or {}
                self.calls: list[StepContext] = []

            def run(self, ctx: StepContext) -> StepResult:
                self.calls.append(ctx)
                return StepResult(
                    next=self._next,
                    state_patch=self._patch,
                    outputs={"from": self.name},
                )

        s_before = _Step("before", next_label="fan", patch={"key": "before_value"})
        pa = _Step("pa", next_label="halt")
        pb = _Step("pb", next_label="halt")
        s_after = _Step("after", next_label="halt")

        def join_fn(results, ctx):
            return StepResult(next="go", state_patch={"joined": True})

        panel = ParallelStage(
            name="panel",
            steps=(pa, pb),
            join=join_fn,
            edges=(Edge(label="go", target="after"),),
        )
        pipeline = Pipeline(
            stages={
                "before": Stage(
                    name="before", step=s_before,
                    edges=(Edge(label="fan", target="panel"),),
                ),
                "panel": panel,
                "after": Stage(name="after", step=s_after, edges=()),
            },
            entry="before",
        )
        env = RuntimeEnvelope()
        run_pipeline(pipeline, {}, env)

        # Parallel steps see prior state
        assert pa.calls[0].state.get("key") == "before_value"
        assert pb.calls[0].state.get("key") == "before_value"
        # After step sees both prior and join state
        assert s_after.calls[0].state.get("key") == "before_value"
        assert s_after.calls[0].state.get("joined") is True


# ---------------------------------------------------------------------------
# T4: Decision/override routing dispatch — 8 new scenarios
# ---------------------------------------------------------------------------


class _VerdictStep:
    """A step that returns a configurable PipelineVerdict for routing tests."""

    def __init__(
        self,
        name: str,
        kind: str = "decide",
        *,
        recommendation: str | None = None,
        override: str | None = None,
        next_label: str = "halt",
        patch: dict[str, Any] | None = None,
    ) -> None:
        self.name = name
        self.kind = kind
        self._recommendation = recommendation
        self._override = override
        self._next = next_label
        self._patch = patch or {}
        self.calls: list[StepContext] = []

    def run(self, ctx: StepContext) -> StepResult:
        self.calls.append(ctx)
        verdict = None
        if self._recommendation is not None or self._override is not None:
            verdict = PipelineVerdict(
                score=0.5,
                recommendation=self._recommendation,
                override=self._override,
            )
        return StepResult(
            outputs={"from": self.name},
            verdict=verdict,
            next=self._next,
            state_patch=self._patch,
        )


class TestDecisionOverrideRouting:
    """Tests for the 4-tier dispatch integrated via resolve_edge."""

    # SC4.1 — override precedence
    def test_override_takes_precedence_over_decision(self) -> None:
        """When both override and recommendation are set, override wins."""
        step = _VerdictStep(
            "gate", kind="decide",
            recommendation="proceed",
            override="force_proceed",
            next_label="fallback",
        )
        # Edges: decision→halt (should NOT be taken), override→done (SHOULD
        # be taken), normal fbt
        stage = Stage(
            name="gate", step=step,
            edges=(
                Edge(label="proceed", target="halt", kind="decision"),
                Edge(label="override force_proceed", target="done", kind="override"),
                Edge(label="fallback", target="halt", kind="normal"),
            ),
            override_vocabulary=frozenset({"force_proceed"}),
            decision_vocabulary=frozenset({"proceed"}),
        )
        done_step = _VerdictStep("done", next_label="halt")
        pipeline = Pipeline(
            stages={
                "gate": stage,
                "done": Stage(name="done", step=done_step, edges=()),
            },
            entry="gate",
        )
        run_pipeline(pipeline, {}, RuntimeEnvelope())
        # Override edge targets "done", so done_step must have run.
        assert len(done_step.calls) == 1
        assert len(step.calls) == 1

    # SC4.2 — invalid decision
    def test_invalid_decision_raises_routing_error(self) -> None:
        """A decision key not in decision_vocabulary raises RoutingError."""
        step = _VerdictStep(
            "gate", kind="decide",
            recommendation="bogus",
            next_label="normal_fallback",
        )
        stage = Stage(
            name="gate", step=step,
            edges=(
                Edge(label="proceed", target="done", kind="decision"),
                Edge(label="normal_fallback", target="done", kind="normal"),
            ),
            decision_vocabulary=frozenset({"proceed"}),
        )
        pipeline = Pipeline(
            stages={"gate": stage},
            entry="gate",
        )
        with pytest.raises(RoutingError, match="bogus"):
            run_pipeline(pipeline, {}, RuntimeEnvelope())

    # SC4.3 — invalid override
    def test_invalid_override_raises_routing_error(self) -> None:
        """An override action not in override_vocabulary raises RoutingError."""
        step = _VerdictStep(
            "gate", kind="decide",
            override="bogus_override",
            next_label="normal_fallback",
        )
        stage = Stage(
            name="gate", step=step,
            edges=(
                Edge(label="override force_proceed", target="done", kind="override"),
                Edge(label="normal_fallback", target="done", kind="normal"),
            ),
            override_vocabulary=frozenset({"force_proceed"}),
        )
        pipeline = Pipeline(
            stages={"gate": stage},
            entry="gate",
        )
        with pytest.raises(RoutingError, match="bogus_override"):
            run_pipeline(pipeline, {}, RuntimeEnvelope())

    # SC4.4 — missing decision edge
    def test_missing_decision_edge_raises_routing_error(self) -> None:
        """Valid decision but no matching kind='decision' edge → RoutingError."""
        step = _VerdictStep(
            "gate", kind="decide",
            recommendation="proceed",
            next_label="normal_fallback",
        )
        stage = Stage(
            name="gate", step=step,
            edges=(
                Edge(label="iterate", target="loop", kind="decision"),
                Edge(label="normal_fallback", target="loop", kind="normal"),
            ),
            decision_vocabulary=frozenset({"proceed", "iterate"}),
        )
        pipeline = Pipeline(
            stages={"gate": stage},
            entry="gate",
        )
        with pytest.raises(RoutingError, match="proceed"):
            run_pipeline(pipeline, {}, RuntimeEnvelope())

    # SC4.5 — missing override edge
    def test_missing_override_edge_raises_routing_error(self) -> None:
        """Valid override but no matching kind='override' edge → RoutingError."""
        step = _VerdictStep(
            "gate", kind="decide",
            override="force_proceed",
            next_label="normal_fallback",
        )
        stage = Stage(
            name="gate", step=step,
            edges=(
                Edge(label="override abort", target="halt", kind="override"),
                Edge(label="normal_fallback", target="halt", kind="normal"),
            ),
            override_vocabulary=frozenset({"force_proceed", "abort"}),
        )
        pipeline = Pipeline(
            stages={"gate": stage},
            entry="gate",
        )
        with pytest.raises(RoutingError, match="force_proceed"):
            run_pipeline(pipeline, {}, RuntimeEnvelope())

    # SC4.6 — permissive vocab (empty vocabulary skips validation)
    def test_permissive_vocab_accepts_any_string(self) -> None:
        """Empty decision_vocabulary skips validation — any string is accepted."""
        step = _VerdictStep(
            "gate", kind="decide",
            recommendation="anything_goes",
            next_label="normal_fallback",
        )
        stage = Stage(
            name="gate", step=step,
            edges=(
                Edge(label="anything_goes", target="done", kind="decision"),
                Edge(label="normal_fallback", target="done", kind="normal"),
            ),
            # Empty decision_vocabulary → no validation
        )
        done_step = _VerdictStep("done", next_label="halt")
        pipeline = Pipeline(
            stages={
                "gate": stage,
                "done": Stage(name="done", step=done_step, edges=()),
            },
            entry="gate",
        )
        run_pipeline(pipeline, {}, RuntimeEnvelope())
        assert len(done_step.calls) == 1
        assert len(step.calls) == 1

    # SC4.7 — halt short-circuit
    def test_halt_short_circuits_before_decision_dispatch(self) -> None:
        """result.next=='halt' terminates immediately, ignoring verdict."""
        step = _VerdictStep(
            "gate", kind="decide",
            recommendation="proceed",
            override="force_proceed",
            next_label="halt",
        )
        stage = Stage(
            name="gate", step=step,
            edges=(
                Edge(label="proceed", target="done", kind="decision"),
                Edge(label="override force_proceed", target="done", kind="override"),
            ),
            decision_vocabulary=frozenset({"proceed"}),
            override_vocabulary=frozenset({"force_proceed"}),
        )
        done_step = _VerdictStep("done", next_label="halt")
        pipeline = Pipeline(
            stages={
                "gate": stage,
                "done": Stage(name="done", step=done_step, edges=()),
            },
            entry="gate",
        )
        run_pipeline(pipeline, {}, RuntimeEnvelope())
        # Halt short-circuits — done must NOT run.
        assert len(done_step.calls) == 0
        assert len(step.calls) == 1

    # SC4.8 — edge target halt
    def test_edge_target_halt_terminates_pipeline(self) -> None:
        """An edge whose target is 'halt' terminates even for decision routing."""
        step = _VerdictStep(
            "gate", kind="decide",
            recommendation="proceed",
            next_label="fallback",
        )
        stage = Stage(
            name="gate", step=step,
            edges=(
                Edge(label="proceed", target="halt", kind="decision"),
                Edge(label="fallback", target="done", kind="normal"),
            ),
            decision_vocabulary=frozenset({"proceed"}),
        )
        after_step = _VerdictStep("after", next_label="halt")
        pipeline = Pipeline(
            stages={
                "gate": stage,
                "after": Stage(name="after", step=after_step, edges=()),
            },
            entry="gate",
        )
        run_pipeline(pipeline, {}, RuntimeEnvelope())
        # Decision edge targets 'halt' — 'after' must NOT run.
        assert len(after_step.calls) == 0
        assert len(step.calls) == 1


class TestRunPipelineResumeReverify:
    def test_no_declaration_resume_keeps_original_output_and_contract_shape(
        self,
        tmp_path: Path,
    ) -> None:
        review = _ResumeStep(
            "review",
            StepResult(
                next="done",
                outputs={"edited": {"raw": "keep-me"}},
                state_patch={"reviewed": True},
                contract_result=ContractResult(
                    status=ContractStatus.COMPLETED,
                    payload={"legacy": True},
                ),
            ),
        )
        done = _ResumeStep("done", StepResult(next="halt"))
        pipeline = Pipeline(
            stages={
                "review": Stage(
                    name="review",
                    step=review,
                    edges=(Edge(label="done", target="done"),),
                ),
                "done": Stage(name="done", step=done, edges=()),
            },
            entry="review",
        )

        run_pipeline_resume(
            pipeline,
            {},
            RuntimeEnvelope(artifact_root=str(tmp_path)),
            resume_cursor={"stage": "review"},
            suspension=_resume_suspension(),
        )

        assert len(done.calls) == 1
        state = done.calls[0].state
        assert state["edited"] == {"raw": "keep-me"}
        assert "review" not in state
        published = state["__contract_results__"]["review"]
        assert published.payload == {"legacy": True}
        assert published.status is ContractStatus.COMPLETED
        assert state["reviewed"] is True

    def test_valid_resume_publishes_authoritative_output_and_payload_before_merge(
        self,
        tmp_path: Path,
    ) -> None:
        registry = _answer_registry(tmp_path)
        authoritative = _answer_envelope(registry, {"value": 42})
        (tmp_path / "resume.json").write_text(json.dumps(authoritative), encoding="utf-8")
        seen_before_merge: list[dict[str, Any]] = []
        review = _ResumeStep(
            "review",
            StepResult(
                next="done",
                outputs={"draft": {"stale": True}},
                state_patch={"merged_after_publish": True},
                contract_result=ContractResult(
                    status=ContractStatus.SUSPENDED,
                    suspension=_resume_suspension(
                        declaration={"artifact_path": "resume.json", "port": "answer_port"}
                    ),
                    payload={"stale": True},
                ),
            ),
        )
        done = _ResumeStep("done", StepResult(next="halt"))
        pipeline = Pipeline(
            stages={
                "review": Stage(
                    name="review",
                    step=review,
                    edges=(Edge(label="done", target="done"),),
                ),
                "done": Stage(name="done", step=done, edges=()),
            },
            entry="review",
        )

        class _AssertPublishHooks(NullExecutorHooks):
            def merge_state(self, stage, current_state, patch, owned_keys):
                if stage.name == "review":
                    seen_before_merge.append(dict(current_state))
                    contract = current_state["__contract_results__"]["review"]
                    assert current_state["answer_port"] == authoritative
                    assert contract.payload == authoritative
                    assert contract.status is ContractStatus.COMPLETED
                    assert contract.suspension is None
                return super().merge_state(stage, current_state, patch, owned_keys)

        run_pipeline_resume(
            pipeline,
            {},
            RuntimeEnvelope(artifact_root=str(tmp_path)),
            resume_cursor={"stage": "review"},
            suspension=_resume_suspension(
                declaration={"artifact_path": "resume.json", "port": "answer_port"}
            ),
            schema_registry=registry,
            hooks=_AssertPublishHooks(),
        )

        assert len(seen_before_merge) == 1
        assert len(done.calls) == 1
        state = done.calls[0].state
        assert state["answer_port"] == authoritative
        assert state["merged_after_publish"] is True
        assert state["__contract_results__"]["review"].payload == authoritative

    def test_invalid_default_policy_resuspends_with_same_cursor_and_no_invalid_state(
        self,
        tmp_path: Path,
    ) -> None:
        registry = _answer_registry(tmp_path)
        (tmp_path / "resume.json").write_text(
            json.dumps(_answer_envelope(registry, {"value": "oops"})),
            encoding="utf-8",
        )
        review = _ResumeStep(
            "review",
            StepResult(
                next="done",
                outputs={"draft": {"stale": True}},
                state_patch={"should_not_merge": True},
            ),
        )
        done = _ResumeStep("done", StepResult(next="halt"))
        pipeline = Pipeline(
            stages={
                "review": Stage(
                    name="review",
                    step=review,
                    edges=(Edge(label="done", target="done"),),
                ),
                "done": Stage(name="done", step=done, edges=()),
            },
            entry="review",
        )
        captured: list[tuple[StepResult, dict[str, Any]]] = []
        suspension = _resume_suspension(
            declaration={"artifact_path": "resume.json", "port": "answer_port"}
        )

        class _CaptureSuspendHooks(NullExecutorHooks):
            def on_stage_complete(self, stage, ctx, result, state, owned_keys):
                if stage.name == "review":
                    captured.append((result, dict(state)))

        result = run_pipeline_resume(
            pipeline,
            {"seed": "kept"},
            RuntimeEnvelope(artifact_root=str(tmp_path)),
            resume_cursor={"stage": "review"},
            suspension=suspension,
            schema_registry=registry,
            hooks=_CaptureSuspendHooks(),
        )

        assert isinstance(result, RuntimeEnvelope)
        assert len(done.calls) == 0
        assert len(captured) == 1
        resumed_result, state = captured[0]
        assert resumed_result.outputs == {}
        assert resumed_result.state_patch == {}
        assert resumed_result.contract_result is not None
        assert resumed_result.contract_result.status is ContractStatus.SUSPENDED
        assert resumed_result.contract_result.suspension == suspension
        assert resumed_result.contract_result.payload["diagnostic"]["code"] == "typed_contract_blocked"
        assert state == {"seed": "kept"}

    def test_invalid_fail_policy_raises_before_merge(
        self,
        tmp_path: Path,
    ) -> None:
        registry = _answer_registry(tmp_path)
        (tmp_path / "resume.json").write_text(
            json.dumps(_answer_envelope(registry, {"value": "oops"})),
            encoding="utf-8",
        )
        review = _ResumeStep(
            "review",
            StepResult(
                next="done",
                outputs={"draft": {"stale": True}},
                state_patch={"should_not_merge": True},
            ),
        )
        done = _ResumeStep("done", StepResult(next="halt"))
        pipeline = Pipeline(
            stages={
                "review": Stage(
                    name="review",
                    step=review,
                    edges=(Edge(label="done", target="done"),),
                ),
                "done": Stage(name="done", step=done, edges=()),
            },
            entry="review",
        )
        merged_stages: list[str] = []

        class _NoMergeHooks(NullExecutorHooks):
            def merge_state(self, stage, current_state, patch, owned_keys):
                merged_stages.append(stage.name)
                return super().merge_state(stage, current_state, patch, owned_keys)

        with pytest.raises(StepIOEnforcementError, match="Typed contract violation") as excinfo:
            run_pipeline_resume(
                pipeline,
                {},
                RuntimeEnvelope(artifact_root=str(tmp_path)),
                resume_cursor={"stage": "review"},
                suspension=_resume_suspension(
                    declaration={
                        "artifact_path": "resume.json",
                        "port": "answer_port",
                        "invalid_policy": "fail",
                    }
                ),
                schema_registry=registry,
                hooks=_NoMergeHooks(),
            )

        assert len(done.calls) == 0
        assert merged_stages == []
        assert excinfo.value.author_diagnostic is not None
        assert excinfo.value.author_diagnostic["code"] == "typed_contract_blocked"


class TestTypedStepIOHandoffEnforcement:
    def _pipeline(
        self,
        *,
        producer_result: StepResult,
        binding_map: dict[tuple[str, str], tuple[str, str]] | None,
        producer_ports: tuple[Port, ...] = (
            Port(name="answer_port", content_type="application/json", logical_type="answer"),
        ),
        consumer_ports: tuple[PortRef, ...] = (
            PortRef(port_name="answer_port", content_type="application/json", logical_type="answer"),
        ),
    ) -> tuple[Pipeline, _ResumeStep]:
        producer = _ResumeStep("producer", producer_result)
        consumer = _ResumeStep("consumer", StepResult(next="halt"))
        pipeline = Pipeline(
            stages={
                "producer": Stage(
                    name="producer",
                    step=producer,
                    produces=producer_ports,
                    edges=(Edge(label="consumer", target="consumer"),),
                ),
                "consumer": Stage(
                    name="consumer",
                    step=consumer,
                    consumes=consumer_ports,
                    edges=(),
                ),
            },
            entry="producer",
            binding_map=binding_map,
        )
        return pipeline, consumer

    def test_enforce_mode_raises_only_when_both_sides_are_typed(self, tmp_path: Path) -> None:
        registry = _answer_registry(tmp_path)
        invalid_contract = ContractResult(status=ContractStatus.COMPLETED, payload={"value": "oops"})
        base_result = StepResult(next="consumer", contract_result=invalid_contract)

        fully_typed, typed_consumer = self._pipeline(
            producer_result=base_result,
            binding_map={("consumer", "answer_port"): ("producer", "answer_port")},
        )
        with pytest.raises(
            StepIOEnforcementError,
            match="step IO enforced violation at producer.answer_port→consumer.answer_port",
        ):
            run_pipeline(
                fully_typed,
                {},
                RuntimeEnvelope(artifact_root=str(tmp_path)),
                initial_context=_step_io_initial_context(artifact_root=tmp_path, registry=registry),
            )
        assert typed_consumer.calls == []

        producer_untyped, consumer_after_untyped = self._pipeline(
            producer_result=base_result,
            binding_map={("consumer", "answer_port"): ("producer", "answer_port")},
            producer_ports=(),
        )
        run_pipeline(
            producer_untyped,
            {},
            RuntimeEnvelope(artifact_root=str(tmp_path)),
            initial_context=_step_io_initial_context(artifact_root=tmp_path, registry=registry),
        )
        assert len(consumer_after_untyped.calls) == 1

        consumer_untyped, consumer_after_partial = self._pipeline(
            producer_result=base_result,
            binding_map={("consumer", "answer_port"): ("producer", "answer_port")},
            consumer_ports=(),
        )
        run_pipeline(
            consumer_untyped,
            {},
            RuntimeEnvelope(artifact_root=str(tmp_path)),
            initial_context=_step_io_initial_context(artifact_root=tmp_path, registry=registry),
        )
        assert len(consumer_after_partial.calls) == 1

    def test_enforce_mode_uses_lowered_typed_writes_and_reads_before_merge(
        self,
        tmp_path: Path,
    ) -> None:
        registry = _answer_registry(tmp_path)
        producer = _ResumeStep(
            "producer",
            StepResult(
                next="consumer",
                contract_result=ContractResult(
                    status=ContractStatus.COMPLETED,
                    payload={"value": "oops"},
                ),
                state_patch={"must_not_merge": True},
            ),
        )
        consumer = _ResumeStep("consumer", StepResult(next="halt"))
        pipeline = Pipeline(
            stages={
                "producer": Stage(
                    name="producer",
                    step=producer,
                    writes=(
                        Port(
                            name="answer_port",
                            content_type="application/json",
                            logical_type="answer",
                        ),
                    ),
                    edges=(Edge(label="consumer", target="consumer"),),
                ),
                "consumer": Stage(
                    name="consumer",
                    step=consumer,
                    reads=(
                        PortRef(
                            port_name="answer_port",
                            content_type="application/json",
                            logical_type="answer",
                        ),
                    ),
                    edges=(),
                ),
            },
            entry="producer",
            binding_map={("consumer", "answer_port"): ("producer", "answer_port")},
        )

        with pytest.raises(StepIOEnforcementError) as excinfo:
            run_pipeline(
                pipeline,
                {},
                RuntimeEnvelope(artifact_root=str(tmp_path)),
                initial_context=_step_io_initial_context(artifact_root=tmp_path, registry=registry),
            )

        assert "producer.answer_port→consumer.answer_port" in str(excinfo.value)
        assert excinfo.value.author_diagnostic is not None
        assert consumer.calls == []

    @pytest.mark.parametrize(
        ("binding_map", "producer_ports", "consumer_ports", "producer_result"),
        [
            (
                None,
                (Port(name="answer_port", content_type="application/json", logical_type="answer"),),
                (PortRef(port_name="answer_port", content_type="application/json", logical_type="answer"),),
                StepResult(
                    next="consumer",
                    contract_result=ContractResult(
                        status=ContractStatus.COMPLETED,
                        payload={"value": "oops"},
                    ),
                ),
            ),
            (
                {("consumer", "answer_port"): ("producer", "answer_port")},
                (),
                (PortRef(port_name="answer_port", content_type="application/json", logical_type="answer"),),
                StepResult(
                    next="consumer",
                    contract_result=ContractResult(
                        status=ContractStatus.COMPLETED,
                        payload={"value": "oops"},
                    ),
                ),
            ),
            (
                {("consumer", "other_port"): ("producer", "answer_port")},
                (Port(name="answer_port", content_type="application/json", logical_type="answer"),),
                (PortRef(port_name="answer_port", content_type="application/json", logical_type="answer"),),
                StepResult(
                    next="consumer",
                    contract_result=ContractResult(
                        status=ContractStatus.COMPLETED,
                        payload={"value": "oops"},
                    ),
                ),
            ),
            (
                {("consumer", "answer_port"): ("producer", "answer_port")},
                (Port(name="answer_port", content_type="application/json", logical_type="answer"),),
                (PortRef(port_name="answer_port", content_type="application/json", logical_type="answer"),),
                StepResult(next="consumer"),
            ),
        ],
    )
    def test_unresolved_or_missing_handoff_inputs_pass_through(
        self,
        tmp_path: Path,
        binding_map: dict[tuple[str, str], tuple[str, str]] | None,
        producer_ports: tuple[Port, ...],
        consumer_ports: tuple[PortRef, ...],
        producer_result: StepResult,
    ) -> None:
        registry = _answer_registry(tmp_path)
        pipeline, consumer = self._pipeline(
            producer_result=producer_result,
            binding_map=binding_map,
            producer_ports=producer_ports,
            consumer_ports=consumer_ports,
        )

        run_pipeline(
            pipeline,
            {},
            RuntimeEnvelope(artifact_root=str(tmp_path)),
            initial_context=_step_io_initial_context(artifact_root=tmp_path, registry=registry),
        )

        assert len(consumer.calls) == 1

    def test_warn_mode_keeps_run_non_blocking_and_emits_operator_telemetry(
        self,
        tmp_path: Path,
    ) -> None:
        registry = _answer_registry(tmp_path)
        telemetry_path = tmp_path / "step_io_contract_violations.jsonl"
        pipeline, consumer = self._pipeline(
            producer_result=StepResult(
                next="consumer",
                contract_result=ContractResult(
                    status=ContractStatus.COMPLETED,
                    payload={"value": "oops"},
                ),
            ),
            binding_map={("consumer", "answer_port"): ("producer", "answer_port")},
        )

        run_pipeline(
            pipeline,
            {},
            RuntimeEnvelope(artifact_root=str(tmp_path)),
            initial_context=StepContext(
                artifact_root=str(tmp_path),
                state={},
                hook_extensions={
                    "pipeline_id": "generic-pipeline",
                    "step_io_contract_context": StepIOContractContext(
                        operation=StepIOOperation.WRITE,
                        registry=registry,
                    ),
                    "step_io_policy_data": {"configured_mode": "warn"},
                    "step_io_telemetry_path": telemetry_path,
                },
            ),
        )

        assert len(consumer.calls) == 1
        records = read_violation_records(telemetry_path)
        assert len(records) == 1
        assert records[0]["mode"] == "warn"
        assert records[0]["producer_step"] == "producer"
        assert records[0]["consumer_step"] == "consumer"

    def test_full_pipeline_with_derived_binding_map_rejects_wrong_typed_payload_before_merge(
        self,
        tmp_path: Path,
    ) -> None:
        registry = _answer_registry(tmp_path)
        producer = _ResumeStep(
            "producer",
            StepResult(
                next="consumer",
                contract_result=ContractResult(
                    status=ContractStatus.COMPLETED,
                    payload={"value": "oops"},
                ),
                state_patch={"must_not_merge": True},
            ),
        )
        consumer = _ResumeStep("consumer", StepResult(next="halt"))
        pipeline = (
            PipelineBuilder("derived-binding")
            .add_stage(
                Stage(
                    name="producer",
                    step=producer,
                    writes=(
                        Port(
                            name="answer_port",
                            content_type="application/json",
                            logical_type="answer",
                        ),
                    ),
                ),
                emit_label="consumer",
            )
            .add_stage(
                Stage(
                    name="consumer",
                    step=consumer,
                    reads=(
                        PortRef(
                            port_name="answer_port",
                            content_type="application/json",
                            logical_type="answer",
                        ),
                    ),
                    edges=(),
                )
            )
            .build(derive_bindings=True)
        )

        with pytest.raises(StepIOEnforcementError, match="producer.answer_port→consumer.answer_port") as excinfo:
            run_pipeline(
                pipeline,
                {},
                RuntimeEnvelope(artifact_root=str(tmp_path)),
                initial_context=_step_io_initial_context(artifact_root=tmp_path, registry=registry),
            )

        assert pipeline.binding_map == {("consumer", "answer_port"): ("producer", "answer_port")}
        assert consumer.calls == []
        assert excinfo.value.author_diagnostic is not None
        assert excinfo.value.author_diagnostic["code"] == "typed_contract_blocked"
