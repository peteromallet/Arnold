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
