"""Tests for the native pipeline graph projection.

Covers:
- Sequential phase projection into valid Pipeline
- Decision branching projection with correct edge labels
- While loop projection with loop_condition set on guard stage
- Pipeline validates through arnold.pipeline.validator.validate()
- Binding map derivation via derive_binding_map()
"""

from __future__ import annotations

import pytest

from arnold.pipeline.native import (
    NativeCompileError,
    compile_pipeline,
    decision,
    phase,
    pipeline,
    project_graph,
)
from arnold.pipeline.types import Pipeline, Stage
from arnold.pipeline.validator import validate


# ── helpers ───────────────────────────────────────────────────────────


def _edges_as_tuples(stage: Stage) -> list[tuple[str, str]]:
    """Return [(label, target), ...] for a stage."""
    return [(e.label, e.target) for e in stage.edges]


# ── sequential projection ─────────────────────────────────────────────


class TestSequentialProjection:
    """Graph projection for sequential phase-only pipelines."""

    def test_single_phase_pipeline(self) -> None:
        @phase
        def do_work(ctx: object) -> dict:
            return {"x": 1}

        @pipeline
        def my_pipe(ctx: object) -> dict:
            state = yield do_work(ctx)
            return state

        prog = compile_pipeline(my_pipe)
        graph = project_graph(prog)

        assert isinstance(graph, Pipeline)
        assert len(graph.stages) == 1
        stage_names = list(graph.stages.keys())
        assert "do_work" in stage_names[0]

        stage = graph.stages[stage_names[0]]
        assert stage.loop_condition is None
        # Single phase should have a halt edge
        assert ("halt", "halt") in _edges_as_tuples(stage)

    def test_two_phase_pipeline(self) -> None:
        @phase
        def step_a(ctx: object) -> dict:
            return {"a": 1}

        @phase
        def step_b(ctx: object) -> dict:
            return {"b": 2}

        @pipeline
        def my_pipe(ctx: object) -> dict:
            state = yield step_a(ctx)
            state = yield step_b(ctx)
            return state

        prog = compile_pipeline(my_pipe)
        graph = project_graph(prog)

        assert len(graph.stages) == 2
        names = list(graph.stages.keys())
        assert "step_a" in names[0]
        assert "step_b" in names[1]

        # step_a → step_b
        edges_a = _edges_as_tuples(graph.stages[names[0]])
        assert any(tgt == names[1] for _, tgt in edges_a)

        # step_b → halt
        edges_b = _edges_as_tuples(graph.stages[names[1]])
        assert ("halt", "halt") in edges_b

    def test_entry_is_first_phase(self) -> None:
        @phase
        def first(ctx: object) -> dict:
            return {}

        @phase
        def second(ctx: object) -> dict:
            return {}

        @pipeline
        def my_pipe(ctx: object) -> dict:
            state = yield first(ctx)
            state = yield second(ctx)
            return state

        prog = compile_pipeline(my_pipe)
        graph = project_graph(prog)
        assert graph.entry is not None
        assert "first" in graph.entry

    def test_phase_step_is_callable(self) -> None:
        @phase
        def do_work(ctx: object) -> dict:
            return {"x": 42}

        @pipeline
        def my_pipe(ctx: object) -> dict:
            state = yield do_work(ctx)
            return state

        prog = compile_pipeline(my_pipe)
        graph = project_graph(prog)
        stage_name = list(graph.stages.keys())[0]
        stage = graph.stages[stage_name]
        assert hasattr(stage.step, "run")
        assert hasattr(stage.step, "name")

    def test_sequential_pipeline_validates(self) -> None:
        @phase
        def a(ctx: object) -> dict:
            return {}

        @phase
        def b(ctx: object) -> dict:
            return {}

        @pipeline
        def my_pipe(ctx: object) -> dict:
            state = yield a(ctx)
            state = yield b(ctx)
            return state

        prog = compile_pipeline(my_pipe)
        graph = project_graph(prog)
        result = validate(graph)
        assert len(result.defects) == 0


# ── decision projection ───────────────────────────────────────────────


class TestDecisionProjection:
    """Graph projection for pipelines with if/decision branching."""

    def test_if_else_creates_branched_edges(self) -> None:
        @phase
        def step_a(ctx: object) -> dict:
            return {}

        @phase
        def step_b(ctx: object) -> dict:
            return {}

        @phase
        def step_c(ctx: object) -> dict:
            return {}

        @decision(vocabulary={"yes", "no"})
        def decide(ctx: object) -> str:
            return "yes"

        @pipeline
        def my_pipe(ctx: object) -> dict:
            state = yield step_a(ctx)
            if decide(ctx) == "yes":
                state = yield step_b(ctx)
            else:
                state = yield step_c(ctx)
            return state

        prog = compile_pipeline(my_pipe)
        graph = project_graph(prog)

        # Find the decision stage
        dec_stage = None
        for name, stage in graph.stages.items():
            if "decide" in name:
                dec_stage = stage
                break
        assert dec_stage is not None

        edges = _edges_as_tuples(dec_stage)
        # Should have edges for both "yes" and "no"
        labels = {label for label, _ in edges}
        assert "yes" in labels
        assert "no" in labels

        # "yes" edge should target step_b's stage
        yes_targets = [tgt for lbl, tgt in edges if lbl == "yes"]
        assert any("step_b" in t for t in yes_targets)

        # "no" edge should target step_c's stage
        no_targets = [tgt for lbl, tgt in edges if lbl == "no"]
        assert any("step_c" in t for t in no_targets)

    def test_if_no_else_branches(self) -> None:
        @phase
        def step_a(ctx: object) -> dict:
            return {}

        @phase
        def step_b(ctx: object) -> dict:
            return {}

        @decision(vocabulary={"pass", "fail"})
        def check(ctx: object) -> str:
            return "pass"

        @pipeline
        def my_pipe(ctx: object) -> dict:
            state = yield step_a(ctx)
            if check(ctx) == "pass":
                state = yield step_b(ctx)
            return state

        prog = compile_pipeline(my_pipe)
        graph = project_graph(prog)

        dec_stage = None
        for name, stage in graph.stages.items():
            if "check" in name:
                dec_stage = stage
                break
        assert dec_stage is not None

        edges = _edges_as_tuples(dec_stage)
        labels = {label for label, _ in edges}
        assert "pass" in labels
        assert "fail" in labels

    def test_decision_stage_has_decision_kind(self) -> None:
        @phase
        def step(ctx: object) -> dict:
            return {}

        @decision(vocabulary={"a", "b"})
        def dec(ctx: object) -> str:
            return "a"

        @pipeline
        def my_pipe(ctx: object) -> dict:
            if dec(ctx) == "a":
                state = yield step(ctx)
            else:
                state = yield step(ctx)
            return state

        prog = compile_pipeline(my_pipe)
        graph = project_graph(prog)

        dec_stage = None
        for name, stage in graph.stages.items():
            if "dec" in name:
                dec_stage = stage
                break
        assert dec_stage is not None
        assert dec_stage.step.kind == "native_decision"

    def test_decision_pipeline_validates(self) -> None:
        @phase
        def a(ctx: object) -> dict:
            return {}

        @phase
        def b(ctx: object) -> dict:
            return {}

        @decision(vocabulary={"left", "right"})
        def branch(ctx: object) -> str:
            return "left"

        @pipeline
        def my_pipe(ctx: object) -> dict:
            state = yield a(ctx)
            if branch(ctx) == "left":
                state = yield b(ctx)
            else:
                pass
            return state

        prog = compile_pipeline(my_pipe)
        graph = project_graph(prog)
        result = validate(graph)
        assert len(result.defects) == 0


# ── loop projection ───────────────────────────────────────────────────


class TestLoopProjection:
    """Graph projection for pipelines with while/loop constructs."""

    def test_loop_guard_has_loop_condition(self) -> None:
        @phase
        def body(ctx: object) -> dict:
            return {}

        @decision(vocabulary={"again", "done"})
        def guard(ctx: object) -> str:
            return "again"

        @pipeline
        def my_pipe(ctx: object) -> dict:
            while guard(ctx) == "again":
                state = yield body(ctx)
            return state

        prog = compile_pipeline(my_pipe)
        graph = project_graph(prog)

        # The guard stage should have loop_condition set
        guard_stage = None
        for name, stage in graph.stages.items():
            if "guard" in name:
                guard_stage = stage
                break
        assert guard_stage is not None
        assert guard_stage.loop_condition is not None
        # loop_condition should be the guard function
        assert callable(guard_stage.loop_condition)

    def test_loop_body_edges_back_to_guard(self) -> None:
        @phase
        def body(ctx: object) -> dict:
            return {}

        @decision(vocabulary={"again", "done"})
        def guard(ctx: object) -> str:
            return "again"

        @pipeline
        def my_pipe(ctx: object) -> dict:
            while guard(ctx) == "again":
                state = yield body(ctx)
            return state

        prog = compile_pipeline(my_pipe)
        graph = project_graph(prog)

        # Find body stage
        body_stage = None
        guard_name = None
        for name, stage in graph.stages.items():
            if "body" in name:
                body_stage = stage
            if "guard" in name:
                guard_name = name
        assert body_stage is not None
        assert guard_name is not None

        edges = _edges_as_tuples(body_stage)
        # Body should have an edge back to the guard
        assert any(tgt == guard_name for _, tgt in edges), f"body edges: {edges}, guard: {guard_name}"

    def test_guard_edge_exit_goes_to_halt(self) -> None:
        @phase
        def body(ctx: object) -> dict:
            return {}

        @decision(vocabulary={"loop", "exit"})
        def guard(ctx: object) -> str:
            return "loop"

        @pipeline
        def my_pipe(ctx: object) -> dict:
            while guard(ctx) == "loop":
                state = yield body(ctx)
            return state

        prog = compile_pipeline(my_pipe)
        graph = project_graph(prog)

        guard_stage = None
        for name, stage in graph.stages.items():
            if "guard" in name:
                guard_stage = stage
                break
        assert guard_stage is not None

        edges = _edges_as_tuples(guard_stage)
        # "exit" label should go to halt
        exit_targets = [tgt for lbl, tgt in edges if lbl == "exit"]
        assert any(tgt == "halt" for tgt in exit_targets)

    def test_loop_pipeline_validates(self) -> None:
        @phase
        def body(ctx: object) -> dict:
            return {}

        @decision(vocabulary={"again", "done"})
        def guard(ctx: object) -> str:
            return "again"

        @pipeline
        def my_pipe(ctx: object) -> dict:
            while guard(ctx) == "again":
                state = yield body(ctx)
            return state

        prog = compile_pipeline(my_pipe)
        graph = project_graph(prog)
        result = validate(graph)
        # Guarded cycles are valid — should have no cycle defects
        cycle_defects = [d for d in result.defects if "cycle" in str(d).lower()]
        assert len(cycle_defects) == 0, f"Unexpected cycle defects: {cycle_defects}"

    def test_loop_pipeline_has_two_stages(self) -> None:
        @phase
        def body(ctx: object) -> dict:
            return {}

        @decision(vocabulary={"again", "done"})
        def guard(ctx: object) -> str:
            return "again"

        @pipeline
        def my_pipe(ctx: object) -> dict:
            while guard(ctx) == "again":
                state = yield body(ctx)
            return state

        prog = compile_pipeline(my_pipe)
        graph = project_graph(prog)
        # Only guard and body should be stages (no jump/halt stages)
        assert len(graph.stages) == 2

    def test_loop_with_phase_before_guard(self) -> None:
        @phase
        def setup(ctx: object) -> dict:
            return {}

        @phase
        def body(ctx: object) -> dict:
            return {}

        @decision(vocabulary={"again", "done"})
        def guard(ctx: object) -> str:
            return "again"

        @pipeline
        def my_pipe(ctx: object) -> dict:
            state = yield setup(ctx)
            while guard(ctx) == "again":
                state = yield body(ctx)
            return state

        prog = compile_pipeline(my_pipe)
        graph = project_graph(prog)
        assert len(graph.stages) == 3  # setup + guard + body
        result = validate(graph)
        cycle_defects = [d for d in result.defects if "cycle" in str(d).lower()]
        assert len(cycle_defects) == 0


# ── edge cases ────────────────────────────────────────────────────────


class TestGraphProjectionEdgeCases:
    """Edge cases for graph projection."""

    def test_empty_program_raises(self) -> None:
        from arnold.pipeline.native.ir import NativeProgram

        prog = NativeProgram(name="empty")
        with pytest.raises(ValueError, match="no instructions"):
            project_graph(prog)

    def test_program_with_only_jump_and_halt_raises(self) -> None:
        from arnold.pipeline.native.ir import (
            NativeInstruction,
            NativeProgram,
        )

        prog = NativeProgram(
            name="no_real",
            instructions=(
                NativeInstruction(pc=0, op="jump", name="j"),
                NativeInstruction(pc=1, op="halt"),
            ),
        )
        with pytest.raises(ValueError, match="no phase or decision"):
            project_graph(prog)

    def test_binding_map_is_dict_or_none(self) -> None:
        @phase
        def step(ctx: object) -> dict:
            return {}

        @pipeline
        def my_pipe(ctx: object) -> dict:
            state = yield step(ctx)
            return state

        prog = compile_pipeline(my_pipe)
        graph = project_graph(prog)
        assert graph.binding_map is None or isinstance(graph.binding_map, dict)

    def test_all_stages_have_step_with_run_method(self) -> None:
        @phase
        def a(ctx: object) -> dict:
            return {}

        @phase
        def b(ctx: object) -> dict:
            return {}

        @decision(vocabulary={"x", "y"})
        def d(ctx: object) -> str:
            return "x"

        @pipeline
        def my_pipe(ctx: object) -> dict:
            state = yield a(ctx)
            if d(ctx) == "x":
                state = yield b(ctx)
            return state

        prog = compile_pipeline(my_pipe)
        graph = project_graph(prog)
        for name, stage in graph.stages.items():
            assert hasattr(stage.step, "run"), f"Stage {name} has no run method"
            assert callable(stage.step.run)


# ── port / vocabulary / routes preservation ──────────────────────────


class TestPortAndVocabularyPreservation:
    """Assert produces, consumes, decision_vocabulary, and decision_routes
    survive from decorators through compiler and graph projection."""

    def test_phase_produces_consumes_survive_projection(self) -> None:
        from arnold.pipeline.types import Port, PortRef

        port_out = Port(name="result", content_type="text/plain")
        port_in = PortRef(port_name="input", content_type="application/json")

        @phase(produces=(port_out,), consumes=(port_in,))
        def step(ctx: object) -> dict:
            return {}

        @pipeline
        def my_pipe(ctx: object) -> dict:
            state = yield step(ctx)
            return state

        prog = compile_pipeline(my_pipe)
        graph = project_graph(prog)

        # Find the step stage
        stage = None
        for name, s in graph.stages.items():
            if "step" in name:
                stage = s
                break
        assert stage is not None

        # Assert Stage.produces/consumes are preserved
        assert stage.produces == (port_out,), f"Expected produces={port_out!r}, got {stage.produces!r}"
        assert stage.consumes == (port_in,), f"Expected consumes={port_in!r}, got {stage.consumes!r}"

        # Assert step adapter produces/consumes are preserved
        assert hasattr(stage.step, "produces")
        assert stage.step.produces == (port_out,)
        assert hasattr(stage.step, "consumes")
        assert stage.step.consumes == (port_in,)

    def test_decision_vocabulary_survives_projection(self) -> None:
        @phase
        def step_a(ctx: object) -> dict:
            return {}

        @phase
        def step_b(ctx: object) -> dict:
            return {}

        @decision(vocabulary={"yes", "no"})
        def decide(ctx: object) -> str:
            return "yes"

        @pipeline
        def my_pipe(ctx: object) -> dict:
            state = yield step_a(ctx)
            if decide(ctx) == "yes":
                state = yield step_b(ctx)
            return state

        prog = compile_pipeline(my_pipe)
        graph = project_graph(prog)

        # Find the decision stage
        dec_stage = None
        for name, stage in graph.stages.items():
            if "decide" in name:
                dec_stage = stage
                break
        assert dec_stage is not None

        # Assert decision_vocabulary on the Stage
        assert dec_stage.decision_vocabulary == frozenset({"yes", "no"}), (
            f"Expected vocabulary {{'yes', 'no'}}, got {dec_stage.decision_vocabulary!r}"
        )

        # Assert decision_vocabulary on the step adapter
        assert hasattr(dec_stage.step, "decision_vocabulary")
        assert dec_stage.step.decision_vocabulary == frozenset({"yes", "no"})

    def test_decision_routes_survive_projection(self) -> None:
        @phase
        def step_a(ctx: object) -> dict:
            return {}

        @phase
        def step_b(ctx: object) -> dict:
            return {}

        @decision(vocabulary={"yes", "no"})
        def decide(ctx: object) -> str:
            return "yes"

        @pipeline
        def my_pipe(ctx: object) -> dict:
            state = yield step_a(ctx)
            if decide(ctx) == "yes":
                state = yield step_b(ctx)
            return state

        prog = compile_pipeline(my_pipe)
        graph = project_graph(prog)

        # Find the decision stage
        dec_stage = None
        for name, stage in graph.stages.items():
            if "decide" in name:
                dec_stage = stage
                break
        assert dec_stage is not None

        # Assert decision_routes maps decision keys → edge labels
        assert dec_stage.decision_routes, "decision_routes should not be empty"
        assert "yes" in dec_stage.decision_routes, (
            f"Expected 'yes' in decision_routes, got {dec_stage.decision_routes!r}"
        )
        assert "no" in dec_stage.decision_routes, (
            f"Expected 'no' in decision_routes, got {dec_stage.decision_routes!r}"
        )

        # 'yes' → edge label 'yes' (which targets step_b's stage)
        yes_route = dec_stage.decision_routes["yes"]
        assert yes_route == "yes", (
            f"Expected 'yes'→'yes', got 'yes'→{yes_route!r}"
        )

        # Assert decision_routes on step adapter matches
        assert hasattr(dec_stage.step, "decision_routes")
        assert dec_stage.step.decision_routes == dec_stage.decision_routes

    def test_decision_routes_terminate_at_halt(self) -> None:
        @phase
        def step_a(ctx: object) -> dict:
            return {}

        @decision(vocabulary={"pass", "fail"})
        def check(ctx: object) -> str:
            return "pass"

        @pipeline
        def my_pipe(ctx: object) -> dict:
            state = yield step_a(ctx)
            if check(ctx) == "pass":
                pass  # no phase after — halt
            return state

        prog = compile_pipeline(my_pipe)
        graph = project_graph(prog)

        # Find the decision stage
        dec_stage = None
        for name, stage in graph.stages.items():
            if "check" in name:
                dec_stage = stage
                break
        assert dec_stage is not None

        # Both 'pass' and 'fail' should have route entries.
        # 'pass' then-body has no phase → terminal → None
        # 'fail' else-body (merge) also has no phase → terminal → None
        assert "pass" in dec_stage.decision_routes, (
            f"Expected 'pass' in decision_routes, got {dec_stage.decision_routes!r}"
        )
        assert "fail" in dec_stage.decision_routes, (
            f"Expected 'fail' in decision_routes, got {dec_stage.decision_routes!r}"
        )
        # Both branches are terminal (no real phase follows)
        assert dec_stage.decision_routes["pass"] is None
        assert dec_stage.decision_routes["fail"] is None

    def test_binding_map_visible_when_typed_ports_present(self) -> None:
        from arnold.pipeline.types import Port

        port_out = Port(name="data", content_type="text/plain")

        @phase(produces=(port_out,))
        def producer(ctx: object) -> dict:
            return {"data": "hello"}

        @phase
        def consumer(ctx: object) -> dict:
            return {}

        @pipeline
        def my_pipe(ctx: object) -> dict:
            state = yield producer(ctx)
            state = yield consumer(ctx)
            return state

        prog = compile_pipeline(my_pipe)
        graph = project_graph(prog)

        # binding_map should be a dict (non-None) when typed ports are present
        # because derive_binding_map can see the produces/consumes declarations
        assert graph.binding_map is not None, (
            "binding_map should be non-None when typed ports are present"
        )
        assert isinstance(graph.binding_map, dict)

    def test_derive_binding_map_visibility_with_produces_and_consumes(self) -> None:
        from arnold.pipeline.declaration_lowering import derive_binding_map
        from arnold.pipeline.types import Port, PortRef

        port_out = Port(name="shared_port", content_type="text/plain")
        port_in = PortRef(port_name="shared_port", content_type="text/plain")

        @phase(produces=(port_out,))
        def producer(ctx: object) -> dict:
            return {"shared_port": "value"}

        @phase(consumes=(port_in,))
        def consumer(ctx: object) -> dict:
            return {}

        @pipeline
        def my_pipe(ctx: object) -> dict:
            state = yield producer(ctx)
            state = yield consumer(ctx)
            return state

        prog = compile_pipeline(my_pipe)
        graph = project_graph(prog)

        # Verify that derive_binding_map can operate on the projected stages
        edge_pairs = []
        for src_name, stage in graph.stages.items():
            for edge in stage.edges:
                if edge.target != "halt":
                    edge_pairs.append((src_name, edge.target))

        binding_map = derive_binding_map(graph.stages, edge_pairs)

        # With matching produces/consumes, binding_map should be a non-empty dict
        assert binding_map is not None, (
            "derive_binding_map should return non-None when typed ports match"
        )
        assert isinstance(binding_map, dict)

        # The consumer should have an entry for the shared port.
        # binding_map keys are (stage_name, port_name) tuples.
        consumer_name = None
        for name in graph.stages:
            if "consumer" in name:
                consumer_name = name
                break
        assert consumer_name is not None

        # Check that (consumer_name, 'shared_port') is in binding_map
        expected_key = (consumer_name, "shared_port")
        assert expected_key in binding_map, (
            f"Key {expected_key!r} should be in binding_map, got keys: {list(binding_map.keys())!r}"
        )


# ── phase-keyed projection ─────────────────────────────────────────────


class TestPhaseKeyedProjection:
    """Graph projection using ``key_mode='phase'`` — stage names are bare
    phase/decision names with ``__pc{N}`` disambiguation for duplicates."""

    # ── phase names ──────────────────────────────────────────────────

    def test_phase_keyed_stage_names_are_bare(self) -> None:
        """With key_mode='phase', stage names use the bare phase name."""

        @phase
        def pre_check(ctx: object) -> dict:
            return {}

        @phase
        def do_it(ctx: object) -> dict:
            return {}

        @pipeline
        def my_pipe(ctx: object) -> dict:
            state = yield pre_check(ctx)
            state = yield do_it(ctx)
            return state

        prog = compile_pipeline(my_pipe)
        graph = project_graph(prog, key_mode="phase")

        assert len(graph.stages) == 2
        assert "pre_check" in graph.stages
        assert "do_it" in graph.stages
        # No pc-prefixed clutter
        for name in graph.stages:
            assert not name.startswith("my_pipe__"), f"stage name has prefix: {name!r}"
            assert "__pc" not in name, f"stage name has pc suffix: {name!r}"

    def test_phase_keyed_entry_is_bare_name(self) -> None:
        """entry matches the bare phase name under phase-keyed projection."""

        @phase
        def first(ctx: object) -> dict:
            return {}

        @phase
        def second(ctx: object) -> dict:
            return {}

        @pipeline
        def my_pipe(ctx: object) -> dict:
            state = yield first(ctx)
            state = yield second(ctx)
            return state

        prog = compile_pipeline(my_pipe)
        graph = project_graph(prog, key_mode="phase")
        assert graph.entry == "first"

    def test_phase_keyed_pc_mode_default_unchanged(self) -> None:
        """Default (key_mode='pc') still produces pc-prefixed names."""

        @phase
        def work(ctx: object) -> dict:
            return {}

        @pipeline
        def my_pipe(ctx: object) -> dict:
            state = yield work(ctx)
            return state

        prog = compile_pipeline(my_pipe)
        graph = project_graph(prog)  # default key_mode='pc'
        stage_names = list(graph.stages.keys())
        assert len(stage_names) == 1
        assert "my_pipe__" in stage_names[0]
        assert "__pc" in stage_names[0]

    # ── consumes / produces ──────────────────────────────────────────

    def test_phase_keyed_preserves_produces_consumes(self) -> None:
        """produces and consumes survive phase-keyed projection."""

        from arnold.pipeline.types import Port, PortRef

        port_out = Port(name="result", content_type="text/plain")
        port_in = PortRef(port_name="input", content_type="application/json")

        @phase(produces=(port_out,), consumes=(port_in,))
        def step(ctx: object) -> dict:
            return {}

        @pipeline
        def my_pipe(ctx: object) -> dict:
            state = yield step(ctx)
            return state

        prog = compile_pipeline(my_pipe)
        graph = project_graph(prog, key_mode="phase")

        stage = graph.stages["step"]
        assert stage.produces == (port_out,)
        assert stage.consumes == (port_in,)
        assert stage.step.produces == (port_out,)
        assert stage.step.consumes == (port_in,)

    def test_phase_keyed_produces_consumes_no_ports(self) -> None:
        """Phases without typed ports still project cleanly under phase-keyed."""

        @phase
        def step_a(ctx: object) -> dict:
            return {}

        @phase
        def step_b(ctx: object) -> dict:
            return {}

        @pipeline
        def my_pipe(ctx: object) -> dict:
            state = yield step_a(ctx)
            state = yield step_b(ctx)
            return state

        prog = compile_pipeline(my_pipe)
        graph = project_graph(prog, key_mode="phase")

        assert graph.stages["step_a"].produces == ()
        assert graph.stages["step_a"].consumes == ()
        assert graph.stages["step_b"].produces == ()
        assert graph.stages["step_b"].consumes == ()

    # ── decisions ────────────────────────────────────────────────────

    def test_phase_keyed_decision_stage_name(self) -> None:
        """Decision stages use bare decision name under phase-keyed projection."""

        @phase
        def step_a(ctx: object) -> dict:
            return {}

        @phase
        def step_b(ctx: object) -> dict:
            return {}

        @decision(vocabulary={"yes", "no"})
        def decide(ctx: object) -> str:
            return "yes"

        @pipeline
        def my_pipe(ctx: object) -> dict:
            state = yield step_a(ctx)
            if decide(ctx) == "yes":
                state = yield step_b(ctx)
            return state

        prog = compile_pipeline(my_pipe)
        graph = project_graph(prog, key_mode="phase")

        assert "decide" in graph.stages
        dec_stage = graph.stages["decide"]
        assert dec_stage.step.kind == "native_decision"
        assert dec_stage.decision_vocabulary == frozenset({"yes", "no"})

    def test_phase_keyed_decision_vocabulary_survives(self) -> None:
        """decision_vocabulary survives phase-keyed projection intact."""

        @phase
        def step_a(ctx: object) -> dict:
            return {}

        @phase
        def step_b(ctx: object) -> dict:
            return {}

        @decision(vocabulary={"alpha", "beta", "gamma"})
        def triage(ctx: object) -> str:
            return "alpha"

        @pipeline
        def my_pipe(ctx: object) -> dict:
            state = yield step_a(ctx)
            if triage(ctx) == "alpha":
                state = yield step_b(ctx)
            return state

        prog = compile_pipeline(my_pipe)
        graph = project_graph(prog, key_mode="phase")

        # triage is a single decision instruction → bare name
        dec_stage = graph.stages["triage"]
        assert dec_stage.decision_vocabulary == frozenset({"alpha", "beta", "gamma"})
        assert dec_stage.step.decision_vocabulary == frozenset({"alpha", "beta", "gamma"})

    def test_phase_keyed_decision_routes_survive(self) -> None:
        """decision_routes survive phase-keyed projection."""

        @phase
        def step_a(ctx: object) -> dict:
            return {}

        @phase
        def step_b(ctx: object) -> dict:
            return {}

        @decision(vocabulary={"left", "right"})
        def fork(ctx: object) -> str:
            return "left"

        @pipeline
        def my_pipe(ctx: object) -> dict:
            state = yield step_a(ctx)
            if fork(ctx) == "left":
                state = yield step_b(ctx)
            return state

        prog = compile_pipeline(my_pipe)
        graph = project_graph(prog, key_mode="phase")

        dec_stage = graph.stages["fork"]
        assert "left" in dec_stage.decision_routes
        assert "right" in dec_stage.decision_routes
        # 'left' branch reaches step_b → edge label 'left'
        assert dec_stage.decision_routes["left"] == "left"
        # 'right' branch has no phase → terminal
        assert dec_stage.decision_routes["right"] is None

    # ── binding maps ─────────────────────────────────────────────────

    def test_phase_keyed_binding_map_non_none_with_typed_ports(self) -> None:
        """binding_map is non-None under phase-keyed projection when typed ports exist."""

        from arnold.pipeline.types import Port

        port_out = Port(name="data", content_type="text/plain")

        @phase(produces=(port_out,))
        def producer(ctx: object) -> dict:
            return {"data": "hi"}

        @phase
        def consumer(ctx: object) -> dict:
            return {}

        @pipeline
        def my_pipe(ctx: object) -> dict:
            state = yield producer(ctx)
            state = yield consumer(ctx)
            return state

        prog = compile_pipeline(my_pipe)
        graph = project_graph(prog, key_mode="phase")

        assert graph.binding_map is not None
        assert isinstance(graph.binding_map, dict)

    def test_phase_keyed_binding_map_keys_are_phase_names(self) -> None:
        """binding_map keys use bare phase names under phase-keyed projection."""

        from arnold.pipeline.declaration_lowering import derive_binding_map
        from arnold.pipeline.types import Port, PortRef

        port_out = Port(name="shared", content_type="text/plain")
        port_in = PortRef(port_name="shared", content_type="text/plain")

        @phase(produces=(port_out,))
        def producer(ctx: object) -> dict:
            return {"shared": "val"}

        @phase(consumes=(port_in,))
        def consumer(ctx: object) -> dict:
            return {}

        @pipeline
        def my_pipe(ctx: object) -> dict:
            state = yield producer(ctx)
            state = yield consumer(ctx)
            return state

        prog = compile_pipeline(my_pipe)
        graph = project_graph(prog, key_mode="phase")

        edge_pairs = [
            (src, edge.target)
            for src, stage in graph.stages.items()
            for edge in stage.edges
            if edge.target != "halt"
        ]
        binding_map = derive_binding_map(graph.stages, edge_pairs)

        assert binding_map is not None
        expected_key = ("consumer", "shared")
        assert expected_key in binding_map, (
            f"Key {expected_key!r} should be in binding_map, ",
            f"got keys: {list(binding_map.keys())!r}",
        )

    # ── duplicate name disambiguation ────────────────────────────────

    def test_phase_keyed_loop_duplicate_names_use_pc_fallback(self) -> None:
        """When a phase name appears multiple times (e.g. used both before
        and inside a loop), stage names fall back to ``{name}__pc{N}`` for
        disambiguation."""

        @phase
        def step(ctx: object) -> dict:
            return {}

        @decision(vocabulary={"again", "done"})
        def guard(ctx: object) -> str:
            return "again"

        @pipeline
        def my_pipe(ctx: object) -> dict:
            state = yield step(ctx)  # step before loop
            while guard(ctx) == "again":
                state = yield step(ctx)  # step inside loop → duplicate
            return state

        prog = compile_pipeline(my_pipe)
        graph = project_graph(prog, key_mode="phase")

        # 'step' appears twice → __pc fallback for both instances
        step_names = sorted(n for n in graph.stages if n.startswith("step"))
        assert len(step_names) >= 2, f"Expected ≥2 'step' stages, got: {step_names}"
        for name in step_names:
            assert "__pc" in name, f"duplicate step name should have __pc: {name!r}"

        # The guard (compiler-named 'guard_guard') is unique → bare name
        assert "guard_guard" in graph.stages

    def test_phase_keyed_loop_edge_targets_use_phase_keyed_names(self) -> None:
        """Edges reference phase-keyed stage names, not pc-prefixed names."""

        @phase
        def step(ctx: object) -> dict:
            return {}

        @decision(vocabulary={"again", "done"})
        def guard(ctx: object) -> str:
            return "again"

        @pipeline
        def my_pipe(ctx: object) -> dict:
            state = yield step(ctx)
            while guard(ctx) == "again":
                state = yield step(ctx)
            return state

        prog = compile_pipeline(my_pipe)
        graph = project_graph(prog, key_mode="phase")

        # step appears twice — once before loop, once in body
        # The first step should have bare name, second should have __pc fallback
        step_names = sorted(n for n in graph.stages if n.startswith("step"))
        assert len(step_names) >= 2, f"Expected 2 'step' stages, got: {step_names}"

        # All edge targets should reference valid stage names
        for stage_name, stage in graph.stages.items():
            for edge in stage.edges:
                if edge.target != "halt":
                    assert edge.target in graph.stages, (
                        f"Edge from {stage_name!r} targets unknown {edge.target!r}"
                    )


    # ── validation ───────────────────────────────────────────────────

    def test_phase_keyed_pipeline_validates(self) -> None:
        """Phase-keyed projection produces a validatable Pipeline."""

        @phase
        def a(ctx: object) -> dict:
            return {}

        @phase
        def b(ctx: object) -> dict:
            return {}

        @decision(vocabulary={"x", "y"})
        def d(ctx: object) -> str:
            return "x"

        @pipeline
        def my_pipe(ctx: object) -> dict:
            state = yield a(ctx)
            if d(ctx) == "x":
                state = yield b(ctx)
            return state

        prog = compile_pipeline(my_pipe)
        graph = project_graph(prog, key_mode="phase")
        result = validate(graph)
        assert len(result.defects) == 0

    # ── edge cases ──────────────────────────────────────────────────

    def test_phase_keyed_unknown_mode_raises(self) -> None:
        """Invalid key_mode raises ValueError."""

        @phase
        def step(ctx: object) -> dict:
            return {}

        @pipeline
        def my_pipe(ctx: object) -> dict:
            state = yield step(ctx)
            return state

        prog = compile_pipeline(my_pipe)
        with pytest.raises(ValueError, match="Unknown key_mode"):
            project_graph(prog, key_mode="bogus")

    def test_phase_keyed_all_stages_have_run_method(self) -> None:
        """Under phase-keyed projection every Stage.step has a callable run."""

        @phase
        def a(ctx: object) -> dict:
            return {}

        @phase
        def b(ctx: object) -> dict:
            return {}

        @decision(vocabulary={"x", "y"})
        def d(ctx: object) -> str:
            return "x"

        @pipeline
        def my_pipe(ctx: object) -> dict:
            state = yield a(ctx)
            if d(ctx) == "x":
                state = yield b(ctx)
            return state

        prog = compile_pipeline(my_pipe)
        graph = project_graph(prog, key_mode="phase")

        for name, stage in graph.stages.items():
            assert hasattr(stage.step, "run"), f"Stage {name} has no run method"
            assert callable(stage.step.run)
