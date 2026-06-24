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
    native_panel,
    parallel,
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


# ── native_panel tests ─────────────────────────────────────────────────


class TestNativePanel:
    """Tests for :func:`native_panel` — the native parallel-panel helper."""

    def test_returns_parallel_branch_list(self) -> None:
        @phase
        def reviewer_a(ctx: object) -> dict:
            return {"draft": "/tmp/a.md"}

        result = native_panel("panel", (("alice", reviewer_a),))
        assert isinstance(result, list)
        assert list(result) == [reviewer_a]
        assert result.__parallel_branches__ == (reviewer_a,)
        assert result.__parallel_name__ == "panel"
        assert result.__parallel_reducer__ is not None

    def test_multiple_reviewers_fan_out(self) -> None:
        @phase
        def r1(ctx: object) -> dict:
            return {}

        @phase
        def r2(ctx: object) -> dict:
            return {}

        @phase
        def r3(ctx: object) -> dict:
            return {}

        result = native_panel("panel", (("a", r1), ("b", r2), ("c", r3)))
        assert len(result) == 3
        assert result.__parallel_branches__ == (r1, r2, r3)

    def test_reviewer_order_preserved(self) -> None:
        """Reviewer order in native_panel matches declaration order."""
        @phase
        def first(ctx: object) -> dict:
            return {}

        @phase
        def second(ctx: object) -> dict:
            return {}

        @phase
        def third(ctx: object) -> dict:
            return {}

        result = native_panel("p", (("z", first), ("a", second), ("m", third)))
        assert list(result) == [first, second, third]

    def test_reducer_collates_per_reviewer_outputs(self) -> None:
        """The built-in reducer prefixes each reviewer's outputs with reviewer_id."""
        @phase
        def alice_review(ctx: object) -> dict:
            return {"draft": "/tmp/d1.md", "score": 0.9}

        @phase
        def bob_review(ctx: object) -> dict:
            return {"draft": "/tmp/d2.md"}

        result = native_panel("panel", (("alice", alice_review), ("bob", bob_review)))
        reducer = result.__parallel_reducer__
        assert reducer is not None

        # Simulate the reducer receiving branch results in order
        merged = reducer([
            {"draft": "/tmp/d1.md", "score": 0.9},
            {"draft": "/tmp/d2.md"},
        ])
        assert merged == {
            "alice.draft": "/tmp/d1.md",
            "alice.score": 0.9,
            "bob.draft": "/tmp/d2.md",
        }

    def test_reducer_handles_non_dict_results(self) -> None:
        """Reducer skips non-dict results gracefully."""
        @phase
        def good_review(ctx: object) -> dict:
            return {"draft": "/tmp/good.md"}

        @phase
        def bad_review(ctx: object) -> int:
            return 42

        result = native_panel("panel", (("good", good_review), ("bad", bad_review)))
        reducer = result.__parallel_reducer__
        merged = reducer([{"draft": "/tmp/good.md"}, 42])
        assert merged == {"good.draft": "/tmp/good.md"}

    def test_empty_reviewers_rejected(self) -> None:
        with pytest.raises(ValueError, match="at least one reviewer"):
            native_panel("empty", ())

    def test_duplicate_reviewer_ids_rejected(self) -> None:
        @phase
        def r1(ctx: object) -> dict:
            return {}

        with pytest.raises(ValueError, match="duplicate reviewer id"):
            native_panel("p", (("same", r1), ("same", r1)))

    def test_non_tuple_pair_rejected(self) -> None:
        with pytest.raises(TypeError, match=r"must be a \(str, callable\) pair"):
            native_panel("p", (("only",),))  # type: ignore[arg-type]

    def test_non_string_reviewer_id_rejected(self) -> None:
        @phase
        def r1(ctx: object) -> dict:
            return {}

        with pytest.raises(TypeError, match="must be a non-empty str"):
            native_panel("p", (((123, r1),)))  # type: ignore[arg-type,list-item]

    def test_empty_string_reviewer_id_rejected(self) -> None:
        @phase
        def r1(ctx: object) -> dict:
            return {}

        with pytest.raises(TypeError, match="must be a non-empty str"):
            native_panel("p", (("", r1),))

    def test_compiles_in_pipeline(self) -> None:
        """native_panel(...) can be used inline in a @pipeline for-loop."""
        from arnold.pipeline.native import compile_pipeline

        @phase
        def reviewer_a(ctx: object) -> dict:
            return {"draft": "/tmp/a.md"}

        @phase
        def reviewer_b(ctx: object) -> dict:
            return {"draft": "/tmp/b.md"}

        @pipeline
        def my_pipe(ctx: object) -> dict:
            for branch in native_panel(
                "panel", (("alice", reviewer_a), ("bob", reviewer_b))
            ):
                state = yield branch(ctx)
            return state

        prog = compile_pipeline(my_pipe)
        assert len(prog.parallel_blocks) == 1
        block = prog.parallel_blocks[0]
        assert block.name == "panel"
        assert block.branches == ("reviewer_a", "reviewer_b")
        assert block.reducer is not None


# ── Synthetic comparison against panel_parallel output shape ────────────


class TestNativePanelVsPanelParallel:
    """Verify native_panel matches panel_parallel(merge="none") output shape."""

    def test_same_cardinality(self) -> None:
        """Both produce the same number of reviewer branches."""
        from arnold.pipelines.megaplan._pipeline.pattern_topology import panel_parallel
        from arnold.pipeline.types import Step, StepContext, StepResult

        # Build equivalent reviewers for both APIs
        class _ReviewerStep:
            def __init__(self, name: str, outputs: dict | None = None):
                self.name = name
                self.kind = "review"
                self._outputs = outputs or {}

            def run(self, ctx: StepContext) -> StepResult:
                return StepResult(outputs=self._outputs, next="halt")

        rs1 = _ReviewerStep("rs1", {"draft": "/tmp/r1.md"})
        rs2 = _ReviewerStep("rs2", {"draft": "/tmp/r2.md"})

        # panel_parallel (non-native)
        pp_stage = panel_parallel("panel", (("alice", rs1), ("bob", rs2)))
        assert len(pp_stage.steps) == 2

        # native_panel
        @phase
        def r1(ctx: object) -> dict:
            return {"draft": "/tmp/r1.md"}

        @phase
        def r2(ctx: object) -> dict:
            return {"draft": "/tmp/r2.md"}

        np_result = native_panel("panel", (("alice", r1), ("bob", r2)))
        assert len(np_result) == 2

    def test_same_reviewer_ordering(self) -> None:
        """Both preserve reviewer declaration order."""
        from arnold.pipelines.megaplan._pipeline.pattern_topology import panel_parallel
        from arnold.pipeline.types import Step, StepContext, StepResult

        class _ReviewerStep:
            def __init__(self, name: str):
                self.name = name
                self.kind = "review"

            def run(self, ctx: StepContext) -> StepResult:
                return StepResult(outputs={}, next="halt")

        rs_a = _ReviewerStep("a")
        rs_b = _ReviewerStep("b")
        rs_c = _ReviewerStep("c")

        pp_stage = panel_parallel("p", (("z", rs_a), ("y", rs_b), ("x", rs_c)))
        pp_names = [s.name for s in pp_stage.steps]
        assert pp_names == ["a", "b", "c"]

        @phase
        def ra(ctx: object) -> dict:
            return {}

        @phase
        def rb(ctx: object) -> dict:
            return {}

        @phase
        def rc(ctx: object) -> dict:
            return {}

        np_result = native_panel("p", (("z", ra), ("y", rb), ("x", rc)))
        np_names = [f.__name__ for f in np_result]
        assert np_names == ["ra", "rb", "rc"]

    def test_same_collation_shape(self) -> None:
        """Reducer collation matches panel_parallel join output shape."""
        from arnold.pipelines.megaplan._pipeline.pattern_topology import panel_parallel
        from arnold.pipeline.types import Step, StepContext, StepResult

        class _ReviewerStep:
            def __init__(self, name: str, outputs: dict | None = None):
                self.name = name
                self.kind = "review"
                self._outputs = outputs or {}

            def run(self, ctx: StepContext) -> StepResult:
                return StepResult(outputs=self._outputs, next="halt")

        rs1 = _ReviewerStep("rs1", {"draft": "/tmp/d1.md", "score": 0.8})
        rs2 = _ReviewerStep("rs2", {"draft": "/tmp/d2.md"})

        pp_stage = panel_parallel("panel", (("alice", rs1), ("bob", rs2)))
        ctx = StepContext(artifact_root="/tmp", state={})
        pp_result = pp_stage.join([
            StepResult(outputs={"draft": "/tmp/d1.md", "score": 0.8}, next="halt"),
            StepResult(outputs={"draft": "/tmp/d2.md"}, next="halt"),
        ], ctx)
        pp_outputs = pp_result.outputs
        # panel_parallel prefixes outputs with reviewer_id
        assert pp_outputs["alice.draft"] == "/tmp/d1.md"
        assert pp_outputs["alice.score"] == 0.8
        assert pp_outputs["bob.draft"] == "/tmp/d2.md"

        # native_panel reducer should produce same shape
        @phase
        def r1(ctx: object) -> dict:
            return {"draft": "/tmp/d1.md", "score": 0.8}

        @phase
        def r2(ctx: object) -> dict:
            return {"draft": "/tmp/d2.md"}

        np_result = native_panel("panel", (("alice", r1), ("bob", r2)))
        reducer = np_result.__parallel_reducer__
        np_reduced = reducer([
            {"draft": "/tmp/d1.md", "score": 0.8},
            {"draft": "/tmp/d2.md"},
        ])
        # Same shape: reviewer_id.label -> value
        assert np_reduced == dict(pp_outputs)
        assert np_reduced["alice.draft"] == "/tmp/d1.md"
        assert np_reduced["alice.score"] == 0.8
        assert np_reduced["bob.draft"] == "/tmp/d2.md"

    def test_single_reviewer_shape(self) -> None:
        """Single-reviewer panel produces same shape in both APIs."""
        from arnold.pipelines.megaplan._pipeline.pattern_topology import panel_parallel
        from arnold.pipeline.types import Step, StepContext, StepResult

        class _ReviewerStep:
            def __init__(self, name: str, outputs: dict | None = None):
                self.name = name
                self.kind = "review"
                self._outputs = outputs or {}

            def run(self, ctx: StepContext) -> StepResult:
                return StepResult(outputs=self._outputs, next="halt")

        rs = _ReviewerStep("rs", {"x": 1})
        pp_stage = panel_parallel("p", (("only", rs),))
        ctx = StepContext(artifact_root="/tmp", state={})
        pp_result = pp_stage.join(
            [StepResult(outputs={"x": 1}, next="halt")], ctx
        )
        assert pp_result.outputs == {"only.x": 1}

        @phase
        def r(ctx: object) -> dict:
            return {"x": 1}

        np_result = native_panel("p", (("only", r),))
        reducer = np_result.__parallel_reducer__
        np_reduced = reducer([{"x": 1}])
        assert np_reduced == {"only.x": 1}


# ── Human-gate decision metadata tests ────────────────────────────────


class TestDecisionHumanGateMetadata:
    """Human-gate decision metadata exposed via decorator, get_decision_meta,
    and NativeDecision IR construction.

    Verifies:
    - Ordinary decisions remain unchanged (human-gate fields at defaults).
    - Human-gate decisions carry ``artifact_stage``, ``choices``,
      ``resume_input_schema``, and optional ``override_routes``.
    - Round-trip: decorator → get_decision_meta → NativeDecision.
    """

    # ── Ordinary decisions: no human-gate leakage ─────────────────

    def test_ordinary_decision_has_no_human_gate(self) -> None:
        """Ordinary @decision has human_gate=False and all human-gate
        fields at their defaults."""

        @decision(vocabulary={"pass", "fail"})
        def ordinary(ctx: object) -> str:
            return "pass"

        meta = get_decision_meta(ordinary)
        assert meta is not None
        # Core fields unchanged
        assert meta["name"] == "ordinary"
        assert meta["vocabulary"] == frozenset({"pass", "fail"})
        # Human-gate fields are all at defaults
        assert meta["human_gate"] is False
        assert meta["artifact_stage"] == ""
        assert meta["choices"] == ()
        assert meta["resume_input_schema"] is None
        assert meta["override_routes"] is None

    def test_ordinary_decision_ir_construction_unchanged(self) -> None:
        """Ordinary decision → NativeDecision IR is byte-identical to
        pre-human-gate construction (human-gate fields at defaults)."""

        @decision(vocabulary={"yes", "no"})
        def plain(ctx: object) -> str:
            return "yes"

        meta = get_decision_meta(plain)
        assert meta is not None

        nd = NativeDecision(
            name=meta["name"],
            func=plain,
            vocabulary=meta["vocabulary"],
        )
        # Core identity unchanged
        assert nd.name == "plain"
        assert nd.vocabulary == frozenset({"yes", "no"})
        # Human-gate fields are all off by default in IR
        assert nd.human_gate is False
        assert nd.artifact_stage == ""
        assert nd.choices == ()
        assert nd.resume_input_schema == {}
        assert nd.override_routes == {}

    def test_ordinary_decision_callable_unchanged(self) -> None:
        """Ordinary @decision callable still works as before."""

        @decision(vocabulary={"low", "high"})
        def classify(value: int) -> str:
            return "low" if value < 5 else "high"

        assert classify(3) == "low"
        assert classify(7) == "high"

    # ── Human-gate decisions: metadata surfaces correctly ─────────

    def test_human_gate_decision_exposes_all_metadata(self) -> None:
        """Human-gate @decision exposes artifact_stage, choices,
        resume_input_schema, and override_routes via get_decision_meta."""

        schema = {
            "type": "object",
            "properties": {
                "choice": {"type": "string", "enum": ["continue", "stop"]}
            },
            "required": ["choice"],
        }
        routes = {"continue": "panel_review", "stop": "halt"}

        @decision(
            name="human_review",
            vocabulary={"continue", "stop"},
            human_gate=True,
            artifact_stage="draft_writer",
            choices=("continue", "stop"),
            resume_input_schema=schema,
            override_routes=routes,
        )
        def gate(ctx: object) -> str:
            return "continue"

        meta = get_decision_meta(gate)
        assert meta is not None
        assert meta["name"] == "human_review"
        assert meta["vocabulary"] == frozenset({"continue", "stop"})
        assert meta["human_gate"] is True
        assert meta["artifact_stage"] == "draft_writer"
        assert meta["choices"] == ("continue", "stop")
        assert meta["resume_input_schema"] == schema
        assert meta["override_routes"] == routes

    def test_human_gate_decision_ir_round_trip(self) -> None:
        """Human-gate @decision → get_decision_meta → NativeDecision
        carries all human-gate fields."""

        schema = {"type": "object", "properties": {"action": {"type": "string"}}}
        routes = {"ship": "done", "reject": "halt"}

        @decision(
            name="final_gate",
            vocabulary={"ship", "reject"},
            human_gate=True,
            artifact_stage="final_writer",
            choices=("ship", "reject"),
            resume_input_schema=schema,
            override_routes=routes,
        )
        def gate(ctx: object) -> str:
            return "ship"

        meta = get_decision_meta(gate)
        assert meta is not None

        nd = NativeDecision(
            name=meta["name"],
            func=gate,
            vocabulary=meta["vocabulary"],
            human_gate=meta["human_gate"],
            artifact_stage=meta["artifact_stage"],
            choices=meta["choices"],
            resume_input_schema=meta["resume_input_schema"] or {},
            override_routes=meta["override_routes"] or {},
        )
        assert nd.name == "final_gate"
        assert nd.vocabulary == frozenset({"ship", "reject"})
        assert nd.human_gate is True
        assert nd.artifact_stage == "final_writer"
        assert nd.choices == ("ship", "reject")
        assert nd.resume_input_schema == schema
        assert nd.override_routes == routes

    def test_human_gate_decision_minimal_defaults(self) -> None:
        """A human-gate decision with only human_gate=True uses defaults
        for all optional metadata fields."""

        @decision(
            vocabulary={"continue", "stop"},
            human_gate=True,
        )
        def minimal_gate(ctx: object) -> str:
            return "continue"

        meta = get_decision_meta(minimal_gate)
        assert meta is not None
        assert meta["human_gate"] is True
        assert meta["artifact_stage"] == ""
        assert meta["choices"] == ()
        assert meta["resume_input_schema"] is None
        assert meta["override_routes"] is None

    def test_human_gate_decision_ir_minimal_defaults(self) -> None:
        """NativeDecision constructed with only human_gate=True
        defaults the remaining human-gate fields."""

        def fn(ctx: object) -> str:
            return "ok"

        nd = NativeDecision(
            name="minimal",
            func=fn,
            vocabulary=frozenset({"ok"}),
            human_gate=True,
        )
        assert nd.human_gate is True
        assert nd.artifact_stage == ""
        assert nd.choices == ()
        assert nd.resume_input_schema == {}
        assert nd.override_routes == {}

    def test_human_gate_choices_independent_of_vocabulary(self) -> None:
        """choices and vocabulary can differ — vocabulary is the runtime
        dispatch set, choices is the human-interaction label set."""

        @decision(
            vocabulary={"pass", "fail", "error"},
            human_gate=True,
            choices=("continue", "stop"),
        )
        def gate(ctx: object) -> str:
            return "pass"

        meta = get_decision_meta(gate)
        assert meta is not None
        assert meta["vocabulary"] == frozenset({"pass", "fail", "error"})
        assert meta["choices"] == ("continue", "stop")

    def test_override_routes_partial_override(self) -> None:
        """override_routes may specify routes for only some choices;
        unspecified choices fall back to decision_routes."""

        routes = {"continue": "panel_review"}
        # Only 'continue' is overridden; 'stop' is not

        @decision(
            vocabulary={"continue", "stop"},
            human_gate=True,
            choices=("continue", "stop"),
            override_routes=routes,
        )
        def gate(ctx: object) -> str:
            return "continue"

        meta = get_decision_meta(gate)
        assert meta is not None
        assert meta["override_routes"] == routes
        assert "continue" in meta["override_routes"]
        assert "stop" not in meta["override_routes"]

    def test_ordinary_and_human_gate_coexist(self) -> None:
        """An ordinary decision and a human-gate decision can coexist
        in the same test, proving no cross-contamination."""

        @decision(vocabulary={"a", "b"})
        def ordinary(ctx: object) -> str:
            return "a"

        @decision(
            vocabulary={"x", "y"},
            human_gate=True,
            artifact_stage="writer",
            choices=("x", "y"),
        )
        def gate(ctx: object) -> str:
            return "x"

        ordinary_meta = get_decision_meta(ordinary)
        gate_meta = get_decision_meta(gate)

        assert ordinary_meta is not None
        assert gate_meta is not None

        # Ordinary: no human-gate leakage
        assert ordinary_meta["human_gate"] is False
        assert ordinary_meta["artifact_stage"] == ""
        assert ordinary_meta["choices"] == ()

        # Human-gate: full metadata
        assert gate_meta["human_gate"] is True
        assert gate_meta["artifact_stage"] == "writer"
        assert gate_meta["choices"] == ("x", "y")

    def test_human_gate_decision_frozen_ir(self) -> None:
        """Human-gate NativeDecision is frozen — fields cannot be mutated."""

        def fn(ctx: object) -> str:
            return "ok"

        nd = NativeDecision(
            name="frozen_gate",
            func=fn,
            vocabulary=frozenset({"ok"}),
            human_gate=True,
            artifact_stage="writer",
            choices=("ok",),
        )
        with pytest.raises(Exception):
            nd.human_gate = False  # type: ignore[misc]
        with pytest.raises(Exception):
            nd.artifact_stage = "other"  # type: ignore[misc]
        with pytest.raises(Exception):
            nd.choices = ("other",)  # type: ignore[misc]
        with pytest.raises(Exception):
            nd.resume_input_schema = {"x": 1}  # type: ignore[misc]
        with pytest.raises(Exception):
            nd.override_routes = {"ok": "halt"}  # type: ignore[misc]
