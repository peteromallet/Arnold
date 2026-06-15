"""Simple-graph proof test (T12 / SC12).

Proves that a tiny Pipeline composed only of ``arnold.pipeline`` and
``arnold.runtime`` types runs to completion via
``arnold.pipeline.executor.run_pipeline`` using a ``NullOperationRegistry``
and returns a ``RuntimeEnvelope``.  No ``megaplan`` import appears anywhere
in this file.

This test validates the locked decision: simple plugins do not implement
operations; empty operations means ``arnold run`` uses the generic graph
executor.
"""

from __future__ import annotations

from arnold.pipeline import run_pipeline
from arnold.pipeline.types import Edge, Pipeline, Stage, StepContext, StepResult
from arnold.runtime.envelope import RuntimeEnvelope
from arnold.runtime.operations import NullOperationRegistry


# ---------------------------------------------------------------------------
# Minimal fake steps
# ---------------------------------------------------------------------------


class _HaltStep:
    """One-shot step that halts immediately."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.kind = "compute"
        self.called = False

    def run(self, ctx: StepContext) -> StepResult:
        self.called = True
        return StepResult(next="halt")


class _ForwardStep:
    """Step that forwards execution to a named edge label."""

    def __init__(self, name: str, forward: str) -> None:
        self.name = name
        self.kind = "compute"
        self._forward = forward
        self.called = False

    def run(self, ctx: StepContext) -> StepResult:
        self.called = True
        return StepResult(next=self._forward)


# ---------------------------------------------------------------------------
# Proof tests
# ---------------------------------------------------------------------------


class TestSimpleGraphProof:
    def test_single_stage_returns_runtime_envelope(self) -> None:
        step = _HaltStep("only")
        pipeline = Pipeline(
            stages={"only": Stage(name="only", step=step, edges=())},
            entry="only",
        )
        env = RuntimeEnvelope(plugin_id="proof", run_id="proof-run-1")
        result = run_pipeline(pipeline, {}, env, registry=NullOperationRegistry())

        assert isinstance(result, RuntimeEnvelope)
        assert result is env
        assert step.called

    def test_two_stage_graph_runs_to_completion(self) -> None:
        step_a = _ForwardStep("a", "proceed")
        step_b = _HaltStep("b")

        pipeline = Pipeline(
            stages={
                "stage_a": Stage(
                    name="stage_a",
                    step=step_a,
                    edges=(Edge(label="proceed", target="stage_b"),),
                ),
                "stage_b": Stage(
                    name="stage_b",
                    step=step_b,
                    edges=(),
                ),
            },
            entry="stage_a",
        )
        env = RuntimeEnvelope(plugin_id="proof", run_id="proof-run-2")
        result = run_pipeline(pipeline, {"seed": "hello"}, env)

        assert isinstance(result, RuntimeEnvelope)
        assert result is env
        assert step_a.called
        assert step_b.called

    def test_null_registry_sufficient_for_simple_graph(self) -> None:
        """Locked decision: simple plugins need not implement operations."""
        step = _HaltStep("s")
        pipeline = Pipeline(
            stages={"s": Stage(name="s", step=step, edges=())},
            entry="s",
        )
        result = run_pipeline(
            pipeline, {}, RuntimeEnvelope(), registry=NullOperationRegistry()
        )
        assert isinstance(result, RuntimeEnvelope)
        assert step.called

    def test_envelope_identity_preserved_across_run(self) -> None:
        step = _HaltStep("s")
        pipeline = Pipeline(
            stages={"s": Stage(name="s", step=step, edges=())},
            entry="s",
        )
        env = RuntimeEnvelope(plugin_id="identity-check", run_id="id-run")
        result = run_pipeline(pipeline, {}, env)
        assert result is env
        assert result.plugin_id == "identity-check"
        assert result.run_id == "id-run"

    def test_no_megaplan_import_in_this_file(self) -> None:
        """AST guard: no megaplan import in this test file."""
        import ast
        import pathlib

        src = pathlib.Path(__file__).read_text()
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("megaplan"), (
                        f"test imports megaplan directly: {alias.name!r}"
                    )
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    assert not node.module.startswith("megaplan"), (
                        f"test imports from megaplan: {node.module!r}"
                    )
