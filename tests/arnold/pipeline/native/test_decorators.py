"""Tests for native pipeline decorators and IR dataclasses.

Covers:
- Importability of ``pipeline``, ``phase``, ``decision`` from ``arnold.pipeline.native``
- Metadata attachment on wrapped callables
- Callable behavior preservation
- Type/introspection helpers (``is_pipeline``, ``is_phase``, ``is_decision``)
- Frozen IR dataclass construction and immutability
"""

from __future__ import annotations

import pytest

from arnold.pipeline.native import (
    NativeDecision,
    NativeLoopGuard,
    NativePhase,
    NativePipeline,
    decision,
    get_decision_meta,
    get_phase_meta,
    get_pipeline_meta,
    is_decision,
    is_phase,
    is_pipeline,
    phase,
    pipeline,
)


# ── import smoke tests ────────────────────────────────────────────────


class TestImports:
    """All public symbols must be importable from arnold.pipeline.native."""

    def test_pipeline_importable(self) -> None:
        assert pipeline is not None
        assert callable(pipeline)

    def test_phase_importable(self) -> None:
        assert phase is not None
        assert callable(phase)

    def test_decision_importable(self) -> None:
        assert decision is not None
        assert callable(decision)

    def test_helpers_importable(self) -> None:
        assert is_pipeline is not None
        assert is_phase is not None
        assert is_decision is not None
        assert get_pipeline_meta is not None
        assert get_phase_meta is not None
        assert get_decision_meta is not None

    def test_ir_types_importable(self) -> None:
        assert NativePipeline is not None
        assert NativePhase is not None
        assert NativeDecision is not None
        assert NativeLoopGuard is not None


# ── @pipeline decorator tests ─────────────────────────────────────────


class TestPipelineDecorator:
    """``@pipeline`` attaches metadata and preserves callable behavior."""

    def test_no_parens_attaches_metadata(self) -> None:
        @pipeline
        def my_pipe(ctx: object) -> str:
            return "done"

        assert is_pipeline(my_pipe) is True
        meta = get_pipeline_meta(my_pipe)
        assert meta is not None
        assert meta["name"] == "my_pipe"
        assert meta["description"] == ""
        assert meta["phases"] == []
        assert meta["decisions"] == []

    def test_with_parens_and_name(self) -> None:
        @pipeline(name="custom_name", description="A test pipeline")
        def my_pipe(ctx: object) -> str:
            return "done"

        meta = get_pipeline_meta(my_pipe)
        assert meta is not None
        assert meta["name"] == "custom_name"
        assert meta["description"] == "A test pipeline"

    def test_callable_behavior_preserved(self) -> None:
        @pipeline
        def add(a: int, b: int) -> int:
            return a + b

        assert add(2, 3) == 5

    def test_not_pipeline_for_undecorated(self) -> None:
        def plain() -> None:
            pass

        assert is_pipeline(plain) is False
        assert get_pipeline_meta(plain) is None


# ── @phase decorator tests ────────────────────────────────────────────


class TestPhaseDecorator:
    """``@phase`` attaches metadata and preserves callable behavior."""

    def test_no_parens_attaches_metadata(self) -> None:
        @phase
        def do_work(ctx: object) -> dict:
            return {"x": 1}

        assert is_phase(do_work) is True
        meta = get_phase_meta(do_work)
        assert meta is not None
        assert meta["name"] == "do_work"

    def test_with_name_override(self) -> None:
        @phase(name="custom_phase")
        def do_work(ctx: object) -> dict:
            return {"x": 1}

        meta = get_phase_meta(do_work)
        assert meta is not None
        assert meta["name"] == "custom_phase"

    def test_callable_behavior_preserved(self) -> None:
        @phase
        def multiply(a: int, b: int) -> int:
            return a * b

        assert multiply(3, 4) == 12

    def test_not_phase_for_undecorated(self) -> None:
        def plain() -> None:
            pass

        assert is_phase(plain) is False
        assert get_phase_meta(plain) is None

    def test_phase_is_not_pipeline(self) -> None:
        @phase
        def step(ctx: object) -> dict:
            return {}

        assert is_pipeline(step) is False


# ── @decision decorator tests ─────────────────────────────────────────


class TestDecisionDecorator:
    """``@decision`` attaches metadata including vocabulary."""

    def test_no_parens_attaches_metadata(self) -> None:
        @decision
        def check(ctx: object) -> str:
            return "yes"

        assert is_decision(check) is True
        meta = get_decision_meta(check)
        assert meta is not None
        assert meta["name"] == "check"
        assert meta["vocabulary"] == frozenset()

    def test_with_vocabulary(self) -> None:
        @decision(vocabulary={"yes", "no"})
        def check(ctx: object) -> str:
            return "yes"

        meta = get_decision_meta(check)
        assert meta is not None
        assert meta["vocabulary"] == frozenset({"yes", "no"})

    def test_with_name_and_vocabulary(self) -> None:
        @decision(name="my_check", vocabulary={"pass", "fail", "retry"})
        def check(ctx: object) -> str:
            return "pass"

        meta = get_decision_meta(check)
        assert meta is not None
        assert meta["name"] == "my_check"
        assert meta["vocabulary"] == frozenset({"pass", "fail", "retry"})

    def test_vocabulary_is_frozenset(self) -> None:
        @decision(vocabulary=["a", "b"])
        def decide(ctx: object) -> str:
            return "a"

        meta = get_decision_meta(decide)
        assert meta is not None
        assert isinstance(meta["vocabulary"], frozenset)
        assert meta["vocabulary"] == frozenset({"a", "b"})

    def test_callable_behavior_preserved(self) -> None:
        @decision(vocabulary={"low", "high"})
        def classify(value: int) -> str:
            return "low" if value < 5 else "high"

        assert classify(3) == "low"
        assert classify(7) == "high"

    def test_not_decision_for_undecorated(self) -> None:
        def plain() -> str:
            return "x"

        assert is_decision(plain) is False
        assert get_decision_meta(plain) is None

    def test_decision_is_not_pipeline(self) -> None:
        @decision
        def decide(ctx: object) -> str:
            return "ok"

        assert is_pipeline(decide) is False


# ── metadata helpers: cross-cutting tests ─────────────────────────────


class TestMetadataHelpersCrossCutting:
    """Metadata helpers correctly distinguish decorator kinds."""

    def test_mixed_decorators_correct_kinds(self) -> None:
        @pipeline
        def pipe(ctx: object) -> str:
            return "done"

        @phase
        def step(ctx: object) -> dict:
            return {}

        @decision
        def decide(ctx: object) -> str:
            return "x"

        # Pipeline
        assert is_pipeline(pipe) is True
        assert is_phase(pipe) is False
        assert is_decision(pipe) is False

        # Phase
        assert is_pipeline(step) is False
        assert is_phase(step) is True
        assert is_decision(step) is False

        # Decision
        assert is_pipeline(decide) is False
        assert is_phase(decide) is False
        assert is_decision(decide) is True


# ── IR dataclass tests ────────────────────────────────────────────────


class TestNativePhase:
    """:class:`NativePhase` frozen dataclass."""

    def test_construction(self) -> None:
        def my_func(ctx: object) -> dict:
            return {}

        np = NativePhase(name="test_phase", func=my_func)
        assert np.name == "test_phase"
        assert np.func is my_func

    def test_frozen(self) -> None:
        def my_func(ctx: object) -> dict:
            return {}

        np = NativePhase(name="p", func=my_func)
        with pytest.raises(Exception):  # dataclasses.FrozenInstanceError or similar
            np.name = "other"  # type: ignore[misc]


class TestNativeDecision:
    """:class:`NativeDecision` frozen dataclass."""

    def test_construction(self) -> None:
        def my_func(ctx: object) -> str:
            return "yes"

        nd = NativeDecision(
            name="d1",
            func=my_func,
            vocabulary=frozenset({"yes", "no"}),
        )
        assert nd.name == "d1"
        assert nd.func is my_func
        assert nd.vocabulary == frozenset({"yes", "no"})

    def test_default_vocabulary(self) -> None:
        def my_func(ctx: object) -> str:
            return "x"

        nd = NativeDecision(name="d2", func=my_func)
        assert nd.vocabulary == frozenset()

    def test_frozen(self) -> None:
        def my_func(ctx: object) -> str:
            return "x"

        nd = NativeDecision(name="d", func=my_func)
        with pytest.raises(Exception):
            nd.vocabulary = frozenset({"a"})  # type: ignore[misc]


class TestNativeLoopGuard:
    """:class:`NativeLoopGuard` frozen dataclass."""

    def test_construction(self) -> None:
        def guard_fn(ctx: object) -> bool:
            return True

        def body_fn(ctx: object) -> dict:
            return {}

        ng = NativeLoopGuard(guard=guard_fn, body=body_fn, name="loop1")
        assert ng.guard is guard_fn
        assert ng.body is body_fn
        assert ng.name == "loop1"

    def test_default_name(self) -> None:
        def guard_fn(ctx: object) -> bool:
            return True

        def body_fn(ctx: object) -> dict:
            return {}

        ng = NativeLoopGuard(guard=guard_fn, body=body_fn)
        assert ng.name == ""

    def test_frozen(self) -> None:
        def guard_fn(ctx: object) -> bool:
            return True

        def body_fn(ctx: object) -> dict:
            return {}

        ng = NativeLoopGuard(guard=guard_fn, body=body_fn)
        with pytest.raises(Exception):
            ng.name = "other"  # type: ignore[misc]


class TestNativePipeline:
    """:class:`NativePipeline` frozen dataclass."""

    def test_construction_minimal(self) -> None:
        def pipe_fn(ctx: object) -> str:
            return "ok"

        p = NativePipeline(name="test_pipe", func=pipe_fn)
        assert p.name == "test_pipe"
        assert p.func is pipe_fn
        assert p.phases == ()
        assert p.decisions == ()
        assert p.loop_guards == ()
        assert p.description == ""

    def test_construction_full(self) -> None:
        def pipe_fn(ctx: object) -> str:
            return "ok"

        def phase_fn(ctx: object) -> dict:
            return {}

        def dec_fn(ctx: object) -> str:
            return "yes"

        def guard_fn(ctx: object) -> bool:
            return True

        def body_fn(ctx: object) -> dict:
            return {}

        phases = (NativePhase(name="step1", func=phase_fn),)
        decisions = (NativeDecision(name="d1", func=dec_fn, vocabulary=frozenset({"yes"})),)
        loops = (NativeLoopGuard(guard=guard_fn, body=body_fn, name="l1"),)

        p = NativePipeline(
            name="full_pipe",
            func=pipe_fn,
            phases=phases,
            decisions=decisions,
            loop_guards=loops,
            description="A full pipeline",
        )
        assert p.phases == phases
        assert p.decisions == decisions
        assert p.loop_guards == loops
        assert p.description == "A full pipeline"

    def test_frozen(self) -> None:
        def pipe_fn(ctx: object) -> str:
            return "ok"

        p = NativePipeline(name="p", func=pipe_fn)
        with pytest.raises(Exception):
            p.name = "other"  # type: ignore[misc]


# ── decorator-with-IR round-trip smoke tests ──────────────────────────


class TestDecoratorToIR:
    """Smoke test that decorator metadata can feed IR construction."""

    def test_phase_to_native_phase(self) -> None:
        @phase(name="my_step")
        def step(ctx: object) -> dict:
            return {"status": "ok"}

        meta = get_phase_meta(step)
        assert meta is not None

        ir_phase = NativePhase(name=meta["name"], func=step)
        assert ir_phase.name == "my_step"
        assert ir_phase.func is step
        # callable still works
        assert step(None) == {"status": "ok"}

    def test_decision_to_native_decision(self) -> None:
        @decision(name="branch", vocabulary={"left", "right"})
        def branch(ctx: object) -> str:
            return "left"

        meta = get_decision_meta(branch)
        assert meta is not None

        ir_dec = NativeDecision(
            name=meta["name"],
            func=branch,
            vocabulary=meta["vocabulary"],
        )
        assert ir_dec.name == "branch"
        assert ir_dec.vocabulary == frozenset({"left", "right"})
        assert branch(None) == "left"

    def test_pipeline_to_native_pipeline_minimal(self) -> None:
        @pipeline(name="demo", description="demo pipeline")
        def demo(ctx: object) -> str:
            return "finished"

        meta = get_pipeline_meta(demo)
        assert meta is not None

        ir_pipe = NativePipeline(
            name=meta["name"],
            func=demo,
            description=meta["description"],
        )
        assert ir_pipe.name == "demo"
        assert ir_pipe.description == "demo pipeline"
        assert demo(None) == "finished"
