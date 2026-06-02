"""Boundary tests for the Arnold pipeline skeleton.

These tests live under ``tests/arnold/`` because they guard the *Arnold
package boundary* — verifying that the neutral primitives under
``arnold/pipeline/`` remain opinion-free and structurally sound.  The
alternative locations considered were:

* ``tests/test_arnold_boundary.py`` — Flat root-level tests.  Rejected:
  the Arnold package deserves its own test root to match the package
  layout (``arnold/`` → ``tests/arnold/``), making it easy to
  colocate future Arnold tests (integration, port-in tests, etc.)
  without root-level clutter.

* ``tests/pipeline/test_boundary.py`` — Rejected: ``pipeline`` in the
  test path could be confused with Megaplan's opinionated pipeline
  tests.  The ``tests/arnold/`` root is unambiguous.

The ``tests/arnold/`` root parallels the ``arnold/`` package root one-to-one,
so any developer looking for Arnold tests can follow the same mental
directory tree.
"""

from __future__ import annotations

import ast
import inspect
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import pytest

# ---------------------------------------------------------------------------
# Helpers for static gate scanning
# ---------------------------------------------------------------------------

_PIPELINE_PKG = Path(__file__).resolve().parent.parent.parent / "arnold" / "pipeline"

FORBIDDEN_IMPORT_PREFIXES = ("import megaplan", "from megaplan")
FORBIDDEN_STRING_LITERALS = frozenset(
    {"planning", "proceed", "iterate", "tiebreaker", "escalate"}
)


def _python_source_files(root: Path) -> list[Path]:
    """Return every ``.py`` source file under *root*, excluding ``__pycache__``."""
    return sorted(
        p
        for p in root.rglob("*.py")
        if "__pycache__" not in p.parts
    )


def _ast_import_violations(file_path: Path) -> list[str]:
    """Return a list of human-readable violation strings for forbidden imports."""
    violations: list[str] = []
    try:
        tree = ast.parse(file_path.read_text(), filename=str(file_path))
    except SyntaxError as exc:
        violations.append(f"{file_path}: syntax error — {exc}")
        return violations

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] == "megaplan":
                    violations.append(
                        f"{file_path}:{node.lineno}: forbidden import — "
                        f"`import {alias.name}`"
                    )
        elif isinstance(node, ast.ImportFrom):
            if node.module is not None and node.module.split(".")[0] == "megaplan":
                names = ", ".join(a.name for a in node.names)
                violations.append(
                    f"{file_path}:{node.lineno}: forbidden import — "
                    f"`from {node.module} import {names}`"
                )
    return violations


def _ast_string_literal_violations(file_path: Path) -> list[str]:
    """Return violations for forbidden string literals found in AST constants."""
    violations: list[str] = []
    try:
        tree = ast.parse(file_path.read_text(), filename=str(file_path))
    except SyntaxError:
        return violations  # already reported by _ast_import_violations

    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if node.value in FORBIDDEN_STRING_LITERALS:
                violations.append(
                    f"{file_path}:{node.lineno}: forbidden string literal — "
                    f"'{node.value}'"
                )
    return violations


# ---------------------------------------------------------------------------
# Static gate tests
# ---------------------------------------------------------------------------


class TestStaticGateForbiddenImports:
    """No source file under ``arnold/pipeline/`` may import from megaplan."""

    def test_no_megaplan_imports_in_pipeline_sources(self) -> None:
        violations: list[str] = []
        for source_file in _python_source_files(_PIPELINE_PKG):
            violations.extend(_ast_import_violations(source_file))
        if violations:
            pytest.fail(
                f"{len(violations)} forbidden import(s) found:\n"
                + "\n".join(f"  • {v}" for v in violations)
            )


class TestStaticGateForbiddenStringLiterals:
    """No source file under ``arnold/pipeline/`` may contain forbidden literals."""

    def test_no_planning_string_literal(self) -> None:
        """The string literal ``'planning'`` must not appear in pipeline sources."""
        violations: list[str] = []
        for source_file in _python_source_files(_PIPELINE_PKG):
            for v in _ast_string_literal_violations(source_file):
                if "planning" in v:
                    violations.append(v)
        if violations:
            pytest.fail(
                f"'planning' literal(s) found:\n"
                + "\n".join(f"  • {v}" for v in violations)
            )

    def test_no_gate_recommendation_literals(self) -> None:
        """Literals 'proceed', 'iterate', 'tiebreaker', 'escalate' are forbidden."""
        gate_literals = {"proceed", "iterate", "tiebreaker", "escalate"}
        violations: list[str] = []
        for source_file in _python_source_files(_PIPELINE_PKG):
            for v in _ast_string_literal_violations(source_file):
                for literal in gate_literals:
                    if f"'{literal}'" in v:
                        violations.append(v)
                        break
        if violations:
            pytest.fail(
                f"Gate recommendation literal(s) found:\n"
                + "\n".join(f"  • {v}" for v in violations)
            )


# ---------------------------------------------------------------------------
# Concrete Step implementation for structural subtyping test
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _ConcreteStep:
    """A concrete dataclass that structurally satisfies the ``Step`` Protocol."""

    name: str
    kind: str

    def run(self, ctx: Any) -> Any:
        """Minimal no-op implementation."""
        return ctx  # pragma: no cover — structural test only


# ---------------------------------------------------------------------------
# Construction smoke tests
# ---------------------------------------------------------------------------


class TestConstructionSmoke:
    """Every neutral dataclass type must be instantiable with minimal valid args."""

    def test_edge_instantiation(self) -> None:
        from arnold.pipeline import Edge
        e = Edge(label="ok", target="next")
        assert e.label == "ok"
        assert e.target == "next"
        assert e.kind == "normal"

    def test_pipeline_verdict_accepts_arbitrary_strings(self) -> None:
        """PipelineVerdict.recommendation must accept arbitrary strings, not typed literals."""
        from arnold.pipeline import PipelineVerdict

        # Arbitrary string values — NOT restricted to a Literal type
        v = PipelineVerdict(
            score=0.85,
            recommendation="custom_vibe_check",
            override="force_rhubarb",
        )
        assert v.score == 0.85
        assert v.recommendation == "custom_vibe_check"
        assert v.override == "force_rhubarb"
        # None is also valid
        v2 = PipelineVerdict(score=0.0, recommendation=None, override=None)
        assert v2.recommendation is None
        assert v2.override is None

    def test_step_context_uses_artifact_root_not_plan_dir(self) -> None:
        """StepContext constructor uses ``artifact_root``, NOT ``plan_dir``."""
        from arnold.pipeline import StepContext

        ctx = StepContext(artifact_root="/tmp/test_root", state={"k": "v"})
        assert ctx.artifact_root == "/tmp/test_root"
        assert ctx.state == {"k": "v"}
        assert ctx.mode == "default"
        assert ctx.resource_handles == {}
        assert ctx.inputs == {}

        # Verify plan_dir is NOT a field on StepContext
        sig = inspect.signature(StepContext)
        param_names = set(sig.parameters.keys())
        assert "artifact_root" in param_names, (
            "StepContext must expose artifact_root as a constructor parameter"
        )
        assert "plan_dir" not in param_names, (
            "StepContext must NOT expose plan_dir — use artifact_root"
        )

    def test_step_result_instantiation(self) -> None:
        from arnold.pipeline import StepResult
        sr = StepResult(outputs={"out": "/tmp/foo"}, next="continue")
        assert sr.outputs == {"out": "/tmp/foo"}
        assert sr.next == "continue"
        assert sr.verdict is None
        assert sr.state_patch == {}

    def test_stage_instantiation(self) -> None:
        from arnold.pipeline import Stage, Step
        step = _ConcreteStep(name="validate", kind="judge")
        assert isinstance(step, Step), "ConcreteStep must satisfy the Step Protocol"
        s = Stage(name="validation", step=step, edges=())
        assert s.name == "validation"
        assert s.step is step
        assert s.edges == ()

    def test_parallel_stage_instantiation(self) -> None:
        from arnold.pipeline import ParallelStage, Step, StepResult, StepContext

        step_a = _ConcreteStep(name="worker_a", kind="exec")
        step_b = _ConcreteStep(name="worker_b", kind="exec")
        assert isinstance(step_a, Step)
        assert isinstance(step_b, Step)

        def join_fn(results: list[Any], ctx: Any) -> StepResult:
            return StepResult(next="halt")

        ps = ParallelStage(
            name="fanout",
            steps=(step_a, step_b),
            join=join_fn,
            edges=(),
            max_workers=4,
        )
        assert ps.name == "fanout"
        assert len(ps.steps) == 2
        assert ps.join is join_fn
        assert ps.max_workers == 4

    def test_pipeline_instantiation(self) -> None:
        from arnold.pipeline import Pipeline, Stage, Edge

        step = _ConcreteStep(name="hello", kind="exec")
        edge = Edge(label="halt", target="halt")
        stage = Stage(name="hello_stage", step=step, edges=(edge,))
        p = Pipeline(stages={"hello_stage": stage}, entry="hello_stage")
        assert p.entry == "hello_stage"
        assert "hello_stage" in p.stages
        assert p.stages["hello_stage"] is stage


class TestStateDeltaAndApplyDelta:
    """StateDelta and apply_delta operate correctly."""

    def test_state_delta_instantiation(self) -> None:
        from arnold.pipeline import StateDelta
        sd = StateDelta(patches=({"a": 1}, {"b": 2}))
        assert sd.patches == ({"a": 1}, {"b": 2})

    def test_apply_delta_applies_dict_patches_in_order(self) -> None:
        from arnold.pipeline import StateDelta, apply_delta

        state: dict[str, Any] = {"x": 0}
        delta = StateDelta(patches=({"a": 1}, {"b": 2, "x": 99}))
        result = apply_delta(state, delta)
        assert result is state  # in-place mutation for dicts
        assert result == {"x": 99, "a": 1, "b": 2}

    def test_apply_delta_with_non_dict_state_replaces(self) -> None:
        from arnold.pipeline import StateDelta, apply_delta

        delta = StateDelta(patches=({1, 2}, {"final": "yes"}))
        result = apply_delta([1, 2, 3], delta)
        # First patch replaces list with set, second replaces set with dict
        assert result == {"final": "yes"}

    def test_apply_delta_with_empty_patches_returns_state(self) -> None:
        from arnold.pipeline import StateDelta, apply_delta

        state = {"untouched": True}
        result = apply_delta(state, StateDelta(patches=()))
        assert result is state
        assert result == {"untouched": True}

    def test_apply_delta_empty_patches_on_non_dict(self) -> None:
        from arnold.pipeline import StateDelta, apply_delta

        state = 42
        result = apply_delta(state, StateDelta(patches=()))
        assert result == 42


class TestStepStructuralSubtyping:
    """The Step Protocol must accept structurally-compatible implementations."""

    def test_dataclass_satisfies_step_protocol(self) -> None:
        from arnold.pipeline import Step
        step = _ConcreteStep(name="test_step", kind="judge")
        assert isinstance(step, Step), (
            "A dataclass with name, kind, and run(ctx) must satisfy the Step Protocol"
        )

    def test_plain_class_satisfies_step_protocol(self) -> None:
        from arnold.pipeline import Step

        class PlainStep:
            name = "plain"
            kind = "exec"

            def run(self, ctx: Any) -> Any:
                return ctx

        assert isinstance(PlainStep(), Step), (
            "A plain class with name, kind, and run(ctx) must satisfy the Step Protocol"
        )

    def test_incomplete_class_does_not_satisfy_step(self) -> None:
        from arnold.pipeline import Step

        class Incomplete:
            name = "nope"
            # missing 'kind' and 'run'

        assert not isinstance(Incomplete(), Step), (
            "A class missing 'kind' and 'run' must NOT satisfy the Step Protocol"
        )

    def test_step_protocol_cannot_be_directly_instantiated(self) -> None:
        """Step is a Protocol — direct instantiation must raise TypeError."""
        from arnold.pipeline import Step
        with pytest.raises(TypeError, match="Protocols cannot be instantiated"):
            Step()  # type: ignore[abstract]
