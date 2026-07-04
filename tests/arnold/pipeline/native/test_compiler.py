"""Tests for the native pipeline AST compiler.

Covers:
- Sequential phase lowering with explicit PCs
- if/decision lowering with branch labels
- while/guard lowering with loop headers and back-edges
- NativeCompileError for unsupported constructs (naming AST node type)
- NativeProgram / NativeInstruction dataclass construction
"""

from __future__ import annotations

import pytest

from arnold.pipeline.native import (
    DynamicMapMetadata,
    NativeCompileError,
    NativeDecision,
    NativeInstruction,
    NativeLoopGuard,
    NativePhase,
    NativePipeline,
    NativeProgram,
    NativeTopology,
    ParallelInstruction,
    ParallelMapInstruction,
    compile_pipeline,
    derive_topology,
    decision,
    parallel,
    parallel_map,
    phase,
    pipeline,
    step as _step,
    workflow as _workflow,
)


# ── sequential pipeline ───────────────────────────────────────────────


class TestSequentialCompilation:
    """Compiler lowers sequential ``yield <phase>(ctx)`` to PC-ordered instructions."""

    def test_single_phase(self) -> None:
        @phase
        def do_work(ctx: object) -> dict:
            return {"status": "ok"}

        @pipeline
        def my_pipe(ctx: object) -> dict:
            state = yield do_work(ctx)
            return state

        prog = compile_pipeline(my_pipe)
        assert prog.name == "my_pipe"
        assert len(prog.instructions) == 2  # phase + halt
        assert prog.instructions[0].pc == 0
        assert prog.instructions[0].op == "phase"
        assert prog.instructions[0].name == "do_work"
        assert prog.instructions[0].next_pc == 1
        assert prog.instructions[1].op == "halt"
        assert len(prog.phases) == 1
        assert prog.phases[0].name == "do_work"

    def test_two_phases(self) -> None:
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
        assert len(prog.instructions) == 3  # phase + phase + halt
        assert prog.instructions[0].name == "step_a"
        assert prog.instructions[0].next_pc == 1
        assert prog.instructions[1].name == "step_b"
        assert prog.instructions[1].next_pc == 2
        assert prog.instructions[2].op == "halt"
        assert [p.name for p in prog.phases] == ["step_a", "step_b"]

    def test_three_phases(self) -> None:
        @phase
        def a(ctx: object) -> dict:
            return {}

        @phase
        def b(ctx: object) -> dict:
            return {}

        @phase
        def c(ctx: object) -> dict:
            return {}

        @pipeline
        def my_pipe(ctx: object) -> dict:
            state = yield a(ctx)
            state = yield b(ctx)
            state = yield c(ctx)
            return state

        prog = compile_pipeline(my_pipe)
        assert len(prog.instructions) == 4
        assert [i.name for i in prog.instructions if i.op == "phase"] == ["a", "b", "c"]

    def test_phase_func_is_callable(self) -> None:
        @phase
        def do_work(ctx: object) -> dict:
            return {"x": 42}

        @pipeline
        def my_pipe(ctx: object) -> dict:
            state = yield do_work(ctx)
            return state

        prog = compile_pipeline(my_pipe)
        assert prog.instructions[0].func is do_work

    def test_bare_yield_without_assignment(self) -> None:
        @phase
        def do_work(ctx: object) -> dict:
            return {}

        @pipeline
        def my_pipe(ctx: object) -> dict:
            yield do_work(ctx)
            return {}

        prog = compile_pipeline(my_pipe)
        assert len(prog.instructions) == 2
        assert prog.instructions[0].op == "phase"

    def test_pipeline_name_from_meta(self) -> None:
        @phase
        def step(ctx: object) -> dict:
            return {}

        @pipeline(name="custom_pipe")
        def my_pipe(ctx: object) -> dict:
            state = yield step(ctx)
            return state

        prog = compile_pipeline(my_pipe)
        assert prog.name == "custom_pipe"

    def test_phase_name_from_meta(self) -> None:
        @phase(name="custom_phase")
        def step(ctx: object) -> dict:
            return {}

        @pipeline
        def my_pipe(ctx: object) -> dict:
            state = yield step(ctx)
            return state

        prog = compile_pipeline(my_pipe)
        assert prog.phases[0].name == "custom_phase"
        assert prog.instructions[0].name == "custom_phase"

    def test_phase_invocable_metadata_propagates_to_ir(self) -> None:
        @phase(
            name="custom_phase",
            id="step.stable",
            inputs={"type": "object", "required": ["prompt"]},
            outputs={"type": "object", "required": ["draft"]},
        )
        def step(ctx: object) -> dict:
            return {}

        @pipeline
        def my_pipe(ctx: object) -> dict:
            state = yield step(ctx)
            return state

        prog = compile_pipeline(my_pipe)
        phase_ir = prog.phases[0]
        assert phase_ir.name == "custom_phase"
        assert phase_ir.stable_id == "step.stable"
        assert phase_ir.inputs_schema == {"type": "object", "required": ["prompt"]}
        assert phase_ir.outputs_schema == {"type": "object", "required": ["draft"]}

    def test_pipeline_invocable_metadata_propagates_to_ir(self) -> None:
        @phase
        def step(ctx: object) -> dict:
            return {}

        @pipeline(
            name="custom_pipe",
            id="workflow.stable",
            inputs={"type": "object", "required": ["query"]},
            outputs={"type": "object", "required": ["answer"]},
        )
        def my_pipe(ctx: object) -> dict:
            state = yield step(ctx)
            return state

        prog = compile_pipeline(my_pipe)
        assert prog.name == "custom_pipe"
        assert prog.stable_id == "workflow.stable"
        assert prog.inputs_schema == {"type": "object", "required": ["query"]}
        assert prog.outputs_schema == {"type": "object", "required": ["answer"]}

    def test_yielded_child_workflow_compiles_to_subpipeline_instruction(self) -> None:
        @phase
        def child_step(ctx: object) -> dict:
            return {"child": "done"}

        @_workflow(
            name="child_workflow",
            id="workflow.child",
            inputs={"type": "object", "required": ["seed"]},
            outputs={"type": "object", "required": ["child"]},
        )
        def child(ctx: object) -> dict:
            state = yield child_step(ctx)
            return state

        @phase
        def parent_step(ctx: object) -> dict:
            return {"parent": "done"}

        @pipeline
        def parent(ctx: object) -> dict:
            state = yield child(ctx)
            state = yield parent_step(ctx)
            return state

        prog = compile_pipeline(parent)
        assert [instr.op for instr in prog.instructions] == ["subpipeline", "phase", "halt"]
        child_instr = prog.instructions[0]
        assert child_instr.name == "child_workflow"
        assert child_instr.next_pc == 1
        assert child_instr.subprogram is not None
        assert isinstance(child_instr.subprogram, NativeProgram)
        assert child_instr.subprogram.name == "child_workflow"
        assert child_instr.subprogram.stable_id == "workflow.child"
        assert child_instr.subprogram.inputs_schema == {"type": "object", "required": ["seed"]}
        assert child_instr.subprogram.outputs_schema == {"type": "object", "required": ["child"]}
        assert [instr.op for instr in child_instr.subprogram.instructions] == ["phase", "halt"]

    def test_yielded_dynamic_child_workflow_expression_is_rejected(self) -> None:
        @phase
        def child_step(ctx: object) -> dict:
            return {"child": "done"}

        @_workflow
        def child(ctx: object) -> dict:
            state = yield child_step(ctx)
            return state

        def select_child() -> object:
            return child

        @pipeline
        def parent(ctx: object) -> dict:
            state = yield select_child()(ctx)
            return state

        with pytest.raises(NativeCompileError) as exc_info:
            compile_pipeline(parent)
        assert "dynamic expressions are not supported" in str(exc_info.value)

    def test_step_alias_compiles(self) -> None:
        """@step is an alias for @phase; compilation is identical."""

        @_step
        def do_work(ctx: object) -> dict:
            return {"status": "ok"}

        @pipeline
        def my_pipe(ctx: object) -> dict:
            state = yield do_work(ctx)
            return state

        prog = compile_pipeline(my_pipe)
        assert len(prog.instructions) == 2
        assert prog.instructions[0].op == "phase"
        assert prog.instructions[0].name == "do_work"
        assert prog.instructions[0].next_pc == 1
        assert prog.instructions[1].op == "halt"
        assert len(prog.phases) == 1
        assert prog.phases[0].name == "do_work"

    def test_step_alias_with_metadata_compiles(self) -> None:
        """@step(id=..., inputs=..., outputs=...) propagates into IR."""

        @_step(
            name="typed_step",
            id="my.step",
            inputs={"type": "object"},
            outputs={"type": "object"},
        )
        def do_work(ctx: object) -> dict:
            return {}

        @pipeline
        def my_pipe(ctx: object) -> dict:
            state = yield do_work(ctx)
            return state

        prog = compile_pipeline(my_pipe)
        phase_ir = prog.phases[0]
        assert phase_ir.name == "typed_step"
        assert phase_ir.stable_id == "my.step"
        assert phase_ir.inputs_schema == {"type": "object"}
        assert phase_ir.outputs_schema == {"type": "object"}

    def test_workflow_alias_compiles(self) -> None:
        """@workflow is an alias for @pipeline; compilation is identical."""

        @phase
        def do_work(ctx: object) -> dict:
            return {"status": "ok"}

        @_workflow
        def my_wf(ctx: object) -> dict:
            state = yield do_work(ctx)
            return state

        prog = compile_pipeline(my_wf)
        assert prog.name == "my_wf"
        assert len(prog.instructions) == 2
        assert prog.instructions[0].op == "phase"
        assert prog.instructions[0].name == "do_work"
        assert prog.instructions[1].op == "halt"

    def test_workflow_alias_with_name_metadata(self) -> None:
        """@workflow(name=...) propagates name into program."""

        @phase
        def do_work(ctx: object) -> dict:
            return {}

        @_workflow(name="custom_workflow")
        def my_wf(ctx: object) -> dict:
            state = yield do_work(ctx)
            return state

        prog = compile_pipeline(my_wf)
        assert prog.name == "custom_workflow"


# ── if / decision compilation ─────────────────────────────────────────


class TestDecisionCompilation:
    """Compiler lowers ``if <decision>(ctx)`` with branch labels."""

    def test_if_decision_with_vocabulary(self) -> None:
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
        assert len(prog.decisions) == 1
        assert prog.decisions[0].name == "decide"
        assert prog.decisions[0].vocabulary == frozenset({"yes", "no"})

        # Find the decision instruction
        dec_instr = [i for i in prog.instructions if i.op == "decision"][0]
        assert dec_instr.name == "decide"
        assert "yes" in dec_instr.branches
        assert "no" in dec_instr.branches
        # yes goes to then-body, no goes to else-body
        assert dec_instr.branches["yes"] != dec_instr.branches["no"]

    def test_if_decision_no_else(self) -> None:
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
        dec_instr = [i for i in prog.instructions if i.op == "decision"][0]
        assert dec_instr.name == "check"
        assert dec_instr.branches["pass"] != dec_instr.branches["fail"]

    def test_if_decision_no_vocabulary(self) -> None:
        @phase
        def step_a(ctx: object) -> dict:
            return {}

        @phase
        def step_b(ctx: object) -> dict:
            return {}

        @decision
        def decide(ctx: object) -> str:
            return "ok"

        @pipeline
        def my_pipe(ctx: object) -> dict:
            state = yield step_a(ctx)
            if decide(ctx):
                state = yield step_b(ctx)
            return state

        prog = compile_pipeline(my_pipe)
        dec_instr = [i for i in prog.instructions if i.op == "decision"][0]
        # Without vocabulary and without compare label, uses truthy/falsy
        assert "__truthy__" in dec_instr.branches or "ok" in dec_instr.branches

    def test_if_decision_then_jump_skips_else(self) -> None:
        @phase
        def a(ctx: object) -> dict:
            return {}

        @phase
        def b(ctx: object) -> dict:
            return {}

        @phase
        def c(ctx: object) -> dict:
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
                state = yield c(ctx)
            return state

        prog = compile_pipeline(my_pipe)
        # After then-body, there should be a jump that skips the else-body
        jumps = [i for i in prog.instructions if i.op == "jump"]
        assert len(jumps) == 1
        # Jump target should be after the else body
        else_phase_pc = [i.pc for i in prog.instructions if i.name == "c"][0]
        assert jumps[0].next_pc is not None
        assert jumps[0].next_pc > else_phase_pc

    def test_decision_instruction_has_branches_not_next_pc(self) -> None:
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
        dec_instr = [i for i in prog.instructions if i.op == "decision"][0]
        # Decisions should use branches, not next_pc for routing
        assert len(dec_instr.branches) >= 2


# ── while / loop compilation ──────────────────────────────────────────


class TestLoopCompilation:
    """Compiler lowers ``while <guard>(ctx)`` with loop header and back-edge."""

    def test_while_guard_basic(self) -> None:
        @phase
        def step_a(ctx: object) -> dict:
            return {}

        @phase
        def body(ctx: object) -> dict:
            return {}

        @decision(vocabulary={"again", "done"})
        def guard(ctx: object) -> str:
            return "again"

        @pipeline
        def my_pipe(ctx: object) -> dict:
            state = yield step_a(ctx)
            while guard(ctx) == "again":
                state = yield body(ctx)
            return state

        prog = compile_pipeline(my_pipe)
        assert len(prog.loop_guards) == 1
        assert prog.loop_guards[0].name == "guard"
        assert prog.loop_guards[0].guard is guard
        assert prog.loop_guards[0].body is body

    def test_while_has_jump_back(self) -> None:
        @phase
        def body(ctx: object) -> dict:
            return {}

        @decision
        def guard(ctx: object) -> str:
            return "yes"

        @pipeline
        def my_pipe(ctx: object) -> dict:
            while guard(ctx):
                state = yield body(ctx)
            return state

        prog = compile_pipeline(my_pipe)
        # Should have a jump that loops back to the header
        jumps = [i for i in prog.instructions if i.op == "jump"]
        assert len(jumps) >= 1
        # The jump should point back to the guard/decision instruction
        header = [i for i in prog.instructions if i.op == "decision"][0]
        loop_back = jumps[-1]  # last jump is the loop back
        assert loop_back.next_pc == header.pc

    def test_while_guard_header_has_branches(self) -> None:
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
        header = [i for i in prog.instructions if i.op == "decision"][0]
        assert "loop" in header.branches
        assert "exit" in header.branches
        # loop → body, exit → after loop
        body_instr = [i for i in prog.instructions if i.op == "phase" and i.name == "body"][0]
        assert header.branches["loop"] == body_instr.pc
        # exit should go past the jump
        assert header.branches["exit"] > body_instr.pc

    def test_while_loop_guard_in_program(self) -> None:
        @phase
        def body(ctx: object) -> dict:
            return {}

        @decision
        def guard(ctx: object) -> str:
            return "ok"

        @pipeline
        def my_pipe(ctx: object) -> dict:
            while guard(ctx):
                state = yield body(ctx)
            return state

        prog = compile_pipeline(my_pipe)
        assert len(prog.loop_guards) == 1
        assert isinstance(prog.loop_guards[0], NativeLoopGuard)


# ── NativeCompileError rejection tests ────────────────────────────────


class TestCompileErrors:
    """Compiler rejects unsupported constructs with NativeCompileError naming AST type."""

    def test_not_a_pipeline(self) -> None:
        def plain(ctx: object) -> None:
            pass

        with pytest.raises(NativeCompileError) as exc_info:
            compile_pipeline(plain)  # type: ignore[arg-type]
        assert "pipeline" in str(exc_info.value).lower()

    def test_for_loop_rejected(self) -> None:
        @phase
        def step(ctx: object) -> dict:
            return {}

        @pipeline
        def my_pipe(ctx: object) -> dict:
            for i in range(3):
                state = yield step(ctx)
            return state

        with pytest.raises(NativeCompileError) as exc_info:
            compile_pipeline(my_pipe)
        assert "For" in str(exc_info.value)

    def test_bare_yield_rejected(self) -> None:
        @pipeline
        def my_pipe(ctx: object) -> dict:
            yield
            return {}

        with pytest.raises(NativeCompileError) as exc_info:
            compile_pipeline(my_pipe)
        assert "yield" in str(exc_info.value).lower()

    def test_yield_non_call_rejected(self) -> None:
        @pipeline
        def my_pipe(ctx: object) -> dict:
            state = yield 42  # type: ignore[misc]
            return state

        with pytest.raises(NativeCompileError) as exc_info:
            compile_pipeline(my_pipe)
        assert "Constant" in str(exc_info.value)

    def test_yield_non_phase_rejected(self) -> None:
        def not_a_phase(ctx: object) -> dict:
            return {}

        @pipeline
        def my_pipe(ctx: object) -> dict:
            state = yield not_a_phase(ctx)
            return state

        with pytest.raises(NativeCompileError) as exc_info:
            compile_pipeline(my_pipe)
        assert "not a @phase" in str(exc_info.value)

    def test_if_non_decision_rejected(self) -> None:
        @phase
        def step(ctx: object) -> dict:
            return {}

        @pipeline
        def my_pipe(ctx: object) -> dict:
            if step(ctx):
                state = yield step(ctx)
            return state

        with pytest.raises(NativeCompileError) as exc_info:
            compile_pipeline(my_pipe)
        assert "not a @decision" in str(exc_info.value)

    def test_while_phase_as_guard_rejected(self) -> None:
        @phase
        def step(ctx: object) -> dict:
            return {}

        @phase
        def body(ctx: object) -> dict:
            return {}

        @pipeline
        def my_pipe(ctx: object) -> dict:
            while step(ctx):
                state = yield body(ctx)
            return state

        with pytest.raises(NativeCompileError) as exc_info:
            compile_pipeline(my_pipe)
        assert "not a @decision or guard" in str(exc_info.value)

    def test_while_no_body_phase_rejected(self) -> None:
        @decision
        def guard(ctx: object) -> str:
            return "ok"

        @pipeline
        def my_pipe(ctx: object) -> dict:
            while guard(ctx):
                x = 1
            return {}

        with pytest.raises(NativeCompileError) as exc_info:
            compile_pipeline(my_pipe)
        assert "must contain at least one yield" in str(exc_info.value)

    def test_if_compare_without_decision_rejected(self) -> None:
        @pipeline
        def my_pipe(ctx: object) -> dict:
            if ctx == "test":
                pass
            return {}

        with pytest.raises(NativeCompileError) as exc_info:
            compile_pipeline(my_pipe)
        # The Compare wrapping fails because the left isn't a Call
        assert "Compare" in str(exc_info.value)

    def test_attribute_call_rejected(self) -> None:
        @pipeline
        def my_pipe(ctx: object) -> dict:
            state = yield ctx.something()  # type: ignore[attr-defined]
            return state

        with pytest.raises(NativeCompileError) as exc_info:
            compile_pipeline(my_pipe)
        assert "Attribute" in str(exc_info.value) or "not supported" in str(exc_info.value)


# ── async def rejection (M4 settled decision) ─────────────────────────


class TestAsyncRejection:
    """Compiler rejects ``async def`` pipelines with a clear diagnostic.

    M4 uses the existing sync generator subset for native pipelines.
    Literal ``async def`` support is not required for milestone 4.
    """

    def test_async_def_pipeline_rejected(self) -> None:
        """An async def pipeline is rejected with NativeCompileError."""

        @phase
        def _do_work(ctx: object) -> dict:
            return {}

        @pipeline
        async def _async_pipe(ctx: object) -> dict:
            state = yield _do_work(ctx)

        with pytest.raises(NativeCompileError) as exc_info:
            compile_pipeline(_async_pipe)
        assert "async" in str(exc_info.value).lower()
        assert "_async_pipe" in str(exc_info.value)

    def test_async_def_error_mentions_sync_generator(self) -> None:
        """The error message guides users to use sync generator syntax."""

        @phase
        def _step(ctx: object) -> dict:
            return {}

        @pipeline(name="async_test_pipe")
        async def _async_test(ctx: object) -> dict:
            state = yield _step(ctx)

        with pytest.raises(NativeCompileError) as exc_info:
            compile_pipeline(_async_test)
        msg = str(exc_info.value)
        assert "M4" in msg
        assert "sync" in msg.lower() or "generator" in msg.lower()
        assert "def" in msg.lower()

    def test_async_def_without_yield_rejected(self) -> None:
        """An async def pipeline without phases is also rejected clearly."""

        @pipeline
        async def _empty_async(ctx: object) -> dict:
            return {}

        with pytest.raises(NativeCompileError) as exc_info:
            compile_pipeline(_empty_async)
        assert "async" in str(exc_info.value).lower()
        assert "_empty_async" in str(exc_info.value)


# ── NativeInstruction / NativeProgram dataclass tests ─────────────────


class TestInstructionDataclass:
    """NativeInstruction and NativeProgram are constructable and frozen."""

    def test_instruction_construction(self) -> None:
        instr = NativeInstruction(pc=0, op="phase", name="test")
        assert instr.pc == 0
        assert instr.op == "phase"
        assert instr.name == "test"
        assert instr.func is None
        assert instr.next_pc is None
        assert instr.branches == {}

    def test_instruction_with_func(self) -> None:
        def my_func(ctx: object) -> dict:
            return {}

        instr = NativeInstruction(pc=1, op="phase", name="p1", func=my_func)
        assert instr.func is my_func

    def test_instruction_with_branches(self) -> None:
        instr = NativeInstruction(
            pc=2, op="decision", name="d1", branches={"yes": 3, "no": 5}
        )
        assert instr.branches == {"yes": 3, "no": 5}

    def test_instruction_frozen(self) -> None:
        instr = NativeInstruction(pc=0, op="phase", name="t")
        with pytest.raises(Exception):
            instr.pc = 1  # type: ignore[misc]

    def test_program_construction(self) -> None:
        instrs = (
            NativeInstruction(pc=0, op="phase", name="a", next_pc=1),
            NativeInstruction(pc=1, op="halt"),
        )
        prog = NativeProgram(
            name="test_prog",
            stable_id="workflow.test",
            inputs_schema={"type": "object"},
            outputs_schema={"type": "object"},
            instructions=instrs,
            description="A test",
        )
        assert prog.name == "test_prog"
        assert prog.stable_id == "workflow.test"
        assert prog.inputs_schema == {"type": "object"}
        assert prog.outputs_schema == {"type": "object"}
        assert len(prog.instructions) == 2
        assert prog.description == "A test"
        assert prog.phases == ()
        assert prog.decisions == ()
        assert prog.loop_guards == ()

    def test_program_frozen(self) -> None:
        prog = NativeProgram(name="p")
        with pytest.raises(Exception):
            prog.name = "other"  # type: ignore[misc]


# ── cross-cutting: compile + IR round-trip ────────────────────────────


class TestCompileIRTrip:
    """Compiled program contains correct IR references."""

    def test_phases_in_program_match_instructions(self) -> None:
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
        phase_names = [p.name for p in prog.phases]
        instr_names = [i.name for i in prog.instructions if i.op == "phase"]
        assert phase_names == instr_names

    def test_decisions_in_program_have_vocabulary(self) -> None:
        @phase
        def step(ctx: object) -> dict:
            return {}

        @decision(vocabulary={"red", "green", "blue"})
        def color(ctx: object) -> str:
            return "red"

        @pipeline
        def my_pipe(ctx: object) -> dict:
            if color(ctx) == "red":
                state = yield step(ctx)
            else:
                state = yield step(ctx)
            return state

        prog = compile_pipeline(my_pipe)
        assert len(prog.decisions) == 1
        assert prog.decisions[0].vocabulary == frozenset({"red", "green", "blue"})

    def test_pcs_are_monotonic(self) -> None:
        @phase
        def a(ctx: object) -> dict:
            return {}

        @phase
        def b(ctx: object) -> dict:
            return {}

        @phase
        def c(ctx: object) -> dict:
            return {}

        @pipeline
        def my_pipe(ctx: object) -> dict:
            state = yield a(ctx)
            state = yield b(ctx)
            state = yield c(ctx)
            return state

        prog = compile_pipeline(my_pipe)
        pcs = [i.pc for i in prog.instructions]
        assert pcs == sorted(pcs)
        assert pcs == list(range(len(pcs)))


# ── parallel fan-out / fan-in compilation ─────────────────────────────


class TestParallelCompilation:
    """Compiler lowers ``for x in parallel([...])`` to parallel IR."""

    def test_yield_parallel_basic(self) -> None:
        @phase
        def branch_a(ctx: object) -> dict:
            return {"a": 1}

        @phase
        def branch_b(ctx: object) -> dict:
            return {"b": 2}

        @phase
        def downstream(ctx: object) -> dict:
            return {"done": True}

        @pipeline
        def my_pipe(ctx: object) -> dict:
            state = yield parallel([branch_a, branch_b], name="ab")
            state = yield downstream(ctx)
            return state

        prog = compile_pipeline(my_pipe)
        parallel_instrs = [i for i in prog.instructions if i.op == "parallel"]
        assert len(parallel_instrs) == 1
        instr = parallel_instrs[0]
        assert instr.name == "ab"
        assert instr.next_pc == 1
        assert instr.branches == {}
        assert instr.subprogram is prog.parallel_blocks[0]
        assert instr.subprogram is not None
        assert instr.subprogram.branches == ("branch_a", "branch_b")
        assert instr.subprogram.branch_funcs == (branch_a, branch_b)
        assert instr.subprogram.merge_pc == instr.next_pc
        assert [i.op for i in prog.instructions] == ["parallel", "phase", "halt"]

    def test_yield_parallel_branch_order_preserved(self) -> None:
        @phase
        def first(ctx: object) -> dict:
            return {}

        @phase
        def second(ctx: object) -> dict:
            return {}

        @phase
        def third(ctx: object) -> dict:
            return {}

        @pipeline
        def my_pipe(ctx: object) -> dict:
            state = yield parallel([first, second, third])
            return state

        prog = compile_pipeline(my_pipe)
        assert prog.parallel_blocks[0].branches == ("first", "second", "third")
        assert prog.parallel_blocks[0].branch_funcs == (first, second, third)

    def test_yield_parallel_non_callable_reducer_rejected(self) -> None:
        @phase
        def branch_a(ctx: object) -> dict:
            return {"a": 1}

        @pipeline
        def my_pipe(ctx: object) -> dict:
            state = yield parallel([branch_a], reducer=42)  # type: ignore[arg-type]
            return state

        with pytest.raises(NativeCompileError) as exc_info:
            compile_pipeline(my_pipe)
        assert "reducer" in str(exc_info.value)

    def test_yield_parallel_unresolvable_reducer_rejected(self) -> None:
        @phase
        def branch_a(ctx: object) -> dict:
            return {"a": 1}

        @pipeline
        def my_pipe(ctx: object) -> dict:
            state = yield parallel([branch_a], reducer=missing_reducer)  # type: ignore[name-defined]
            return state

        with pytest.raises(NativeCompileError) as exc_info:
            compile_pipeline(my_pipe)
        assert "reducer" in str(exc_info.value)

    def test_yield_parallel_non_phase_target_rejected(self) -> None:
        def plain_branch(ctx: object) -> dict:
            return {"plain": True}

        @pipeline
        def my_pipe(ctx: object) -> dict:
            state = yield parallel([plain_branch])  # type: ignore[list-item]
            return state

        with pytest.raises(NativeCompileError) as exc_info:
            compile_pipeline(my_pipe)
        assert "not a @phase-decorated function" in str(exc_info.value)

    def test_parallel_static_branches_compile(self) -> None:
        @phase
        def branch_a(ctx: object) -> dict:
            return {"a": 1}

        @phase
        def branch_b(ctx: object) -> dict:
            return {"b": 2}

        @pipeline
        def my_pipe(ctx: object) -> dict:
            for branch in parallel([branch_a, branch_b], name="ab"):
                state = yield branch(ctx)
            return state

        prog = compile_pipeline(my_pipe)
        assert len(prog.parallel_blocks) == 1
        block = prog.parallel_blocks[0]
        assert isinstance(block, ParallelInstruction)
        assert block.name == "ab"
        assert block.branches == ("branch_a", "branch_b")
        assert block.branch_funcs == (branch_a, branch_b)
        assert block.merge_pc is not None

        # A parallel op should appear in the instruction stream.
        parallel_instr = [i for i in prog.instructions if i.op == "parallel"]
        assert len(parallel_instr) == 1
        assert parallel_instr[0].name == "ab"

    def test_parallel_block_default_name(self) -> None:
        @phase
        def only(ctx: object) -> dict:
            return {}

        @pipeline
        def my_pipe(ctx: object) -> dict:
            for branch in parallel([only]):
                state = yield branch(ctx)
            return state

        prog = compile_pipeline(my_pipe)
        assert prog.parallel_blocks[0].name == "parallel_0"

    def test_parallel_reducer_stored(self) -> None:
        @phase
        def branch_a(ctx: object) -> dict:
            return {"a": 1}

        @phase
        def branch_b(ctx: object) -> dict:
            return {"b": 2}

        def reducer(results: list[object]) -> dict:
            return {}

        @pipeline
        def my_pipe(ctx: object) -> dict:
            for branch in parallel([branch_a, branch_b], reducer=reducer):
                state = yield branch(ctx)
            return state

        prog = compile_pipeline(my_pipe)
        assert prog.parallel_blocks[0].reducer is reducer

    def test_parallel_branch_order_preserved(self) -> None:
        @phase
        def first(ctx: object) -> dict:
            return {}

        @phase
        def second(ctx: object) -> dict:
            return {}

        @phase
        def third(ctx: object) -> dict:
            return {}

        @pipeline
        def my_pipe(ctx: object) -> dict:
            for branch in parallel([first, second, third]):
                state = yield branch(ctx)
            return state

        prog = compile_pipeline(my_pipe)
        assert prog.parallel_blocks[0].branches == ("first", "second", "third")

    def test_parallel_empty_rejected_at_declaration(self) -> None:
        with pytest.raises(ValueError, match="at least one branch"):
            parallel([])  # type: ignore[arg-type]

    def test_parallel_duplicate_branch_rejected(self) -> None:
        @phase
        def dup(ctx: object) -> dict:
            return {}

        with pytest.raises(ValueError, match="duplicate branch"):
            parallel([dup, dup])

    def test_parallel_non_phase_branch_rejected(self) -> None:
        def not_a_phase(ctx: object) -> dict:
            return {}

        with pytest.raises(TypeError, match="not a @phase"):
            parallel([not_a_phase])  # type: ignore[list-item]

    def test_parallel_non_callable_branch_rejected(self) -> None:
        with pytest.raises(TypeError, match="not callable"):
            parallel([42])  # type: ignore[list-item]

    def test_parallel_dynamic_branches_rejected_at_compile(self) -> None:
        @phase
        def branch_a(ctx: object) -> dict:
            return {}

        dynamic = [branch_a]

        @pipeline
        def my_pipe(ctx: object) -> dict:
            for branch in parallel(dynamic):  # type: ignore[arg-type]
                state = yield branch(ctx)
            return state

        with pytest.raises(NativeCompileError) as exc_info:
            compile_pipeline(my_pipe)
        assert "parallel() argument must be a literal list or tuple" in str(exc_info.value)

    def test_parallel_non_callable_iterable_rejected_at_compile(self) -> None:
        @phase
        def branch_a(ctx: object) -> dict:
            return {}

        @pipeline
        def my_pipe(ctx: object) -> dict:
            for branch in parallel(branch_a):  # type: ignore[arg-type]
                state = yield branch(ctx)
            return state

        with pytest.raises(NativeCompileError) as exc_info:
            compile_pipeline(my_pipe)
        assert "literal list or tuple" in str(exc_info.value)

    def test_parallel_returns_list_like_with_metadata(self) -> None:
        @phase
        def branch_a(ctx: object) -> dict:
            return {}

        @phase
        def branch_b(ctx: object) -> dict:
            return {}

        result = parallel([branch_a, branch_b], name="ab")
        assert list(result) == [branch_a, branch_b]
        assert result.__parallel_branches__ == (branch_a, branch_b)
        assert result.__parallel_name__ == "ab"


class TestParallelMapCompilation:
    def test_yielded_parallel_map_compiles_to_single_instruction(self) -> None:
        @phase
        def critique(ctx: object) -> dict:
            return {"finding": "ok"}

        def reduce_findings(results: list[dict]) -> dict:
            return {"findings": results}

        @pipeline
        def my_pipe(ctx: object) -> dict:
            state = yield parallel_map(
                items="checks",
                step=critique,
                reducer=reduce_findings,
                path_template="critique/{item_id}",
                name="critique_batch",
            )
            return state

        prog = compile_pipeline(my_pipe)
        assert [instr.op for instr in prog.instructions] == ["parallel_map", "halt"]
        instr = prog.instructions[0]
        assert instr.name == "critique_batch"
        assert instr.call_site_path == ("critique_batch",)
        assert instr.parallel_map_index == 0
        assert instr.parallel_index is None
        assert isinstance(instr.subprogram, ParallelMapInstruction)
        assert instr.subprogram.items_ref == "checks"
        assert instr.subprogram.mapper is critique
        assert instr.subprogram.mapper_name == "critique"
        assert instr.subprogram.reducer is reduce_findings
        assert instr.subprogram.path_template == "critique/{item_id}"
        assert prog.parallel_map_blocks == (instr.subprogram,)

    def test_parallel_map_accepts_workflow_mapper(self) -> None:
        @phase
        def child_step(ctx: object) -> dict:
            return {"child": "ok"}

        @_workflow
        def child(ctx: object) -> dict:
            state = yield child_step(ctx)
            return state

        @pipeline
        def parent(ctx: object) -> dict:
            state = yield parallel_map(items="items", step=child, name="batch")
            return state

        prog = compile_pipeline(parent)
        instr = prog.instructions[0]
        assert instr.op == "parallel_map"
        assert isinstance(instr.subprogram, ParallelMapInstruction)
        assert instr.subprogram.mapper is child

    def test_parallel_map_rejects_dynamic_step_expression(self) -> None:
        @phase
        def mapper(ctx: object) -> dict:
            return {}

        def select_step() -> object:
            return mapper

        @pipeline
        def my_pipe(ctx: object) -> dict:
            state = yield parallel_map(items="checks", step=select_step(), name="batch")
            return state

        with pytest.raises(NativeCompileError) as exc_info:
            compile_pipeline(my_pipe)
        assert "direct named callable" in str(exc_info.value)

    def test_parallel_map_rejects_dynamic_reducer_expression(self) -> None:
        @phase
        def mapper(ctx: object) -> dict:
            return {}

        def make_reducer() -> object:
            return mapper

        @pipeline
        def my_pipe(ctx: object) -> dict:
            state = yield parallel_map(
                items="checks",
                step=mapper,
                reducer=make_reducer(),
                name="batch",
            )
            return state

        with pytest.raises(NativeCompileError) as exc_info:
            compile_pipeline(my_pipe)
        assert "reducer must be a direct named callable" in str(exc_info.value)

    def test_parallel_map_rejects_dynamic_path_template_expression(self) -> None:
        @phase
        def mapper(ctx: object) -> dict:
            return {}

        template = "critique/{item_id}"

        @pipeline
        def my_pipe(ctx: object) -> dict:
            state = yield parallel_map(
                items="checks",
                step=mapper,
                path_template=template,
                name="batch",
            )
            return state

        with pytest.raises(NativeCompileError) as exc_info:
            compile_pipeline(my_pipe)
        assert "path_template must be a string literal" in str(exc_info.value)


class TestNestedWorkflowMetadataCompilation:
    def test_subpipeline_emits_call_site_path_and_schema_ports(self) -> None:
        @phase
        def child_step(ctx: object) -> dict:
            return {"result": "ok"}

        @_workflow(
            name="child",
            inputs={"type": "object", "required": ["seed"]},
            outputs={"type": "object", "required": ["result"]},
        )
        def child(ctx: object) -> dict:
            state = yield child_step(ctx)
            return state

        @pipeline
        def parent(ctx: object) -> dict:
            state = yield child(ctx, id="child_call")
            return state

        prog = compile_pipeline(parent)
        instr = prog.instructions[0]
        assert instr.op == "subpipeline"
        assert instr.call_site_path == ("child_call",)
        assert tuple(port.port_name for port in instr.consumes) == ("seed",)
        assert tuple(port.name for port in instr.produces) == ("result",)

    def test_subpipeline_preserves_explicit_output_bindings(self) -> None:
        @phase
        def child_step(ctx: object) -> dict:
            return {"result": "ok"}

        @_workflow(
            name="child",
            outputs={"type": "object", "required": ["result"]},
        )
        def child(ctx: object) -> dict:
            state = yield child_step(ctx)
            return state

        @pipeline
        def parent(ctx: object) -> dict:
            state = yield child(ctx, id="child_call", outputs={"result": "child_result"})
            return state

        prog = compile_pipeline(parent)
        instr = prog.instructions[0]
        assert instr.op == "subpipeline"
        assert dict(instr.output_bindings) == {"result": "child_result"}

    def test_direct_self_call_cycle_is_rejected(self) -> None:
        @pipeline
        def parent(ctx: object) -> dict:
            state = yield parent(ctx)
            return state

        with pytest.raises(NativeCompileError) as exc_info:
            compile_pipeline(parent)
        assert "Workflow cycle detected: parent -> parent" in str(exc_info.value)

    def test_transitive_cycle_is_rejected(self) -> None:
        @pipeline
        def alpha(ctx: object) -> dict:
            state = yield beta(ctx)
            return state

        @pipeline
        def beta(ctx: object) -> dict:
            state = yield alpha(ctx)
            return state

        with pytest.raises(NativeCompileError) as exc_info:
            compile_pipeline(alpha)
        assert "Workflow cycle detected: alpha -> beta -> alpha" in str(exc_info.value)


class TestDerivedTopologyCompilation:
    def test_compile_pipeline_populates_static_topology_without_execution(self) -> None:
        executed: list[str] = []

        @phase(
            id="draft.phase",
            inputs={"type": "object", "required": ["prompt"]},
            outputs={"type": "object", "required": ["draft"]},
        )
        def draft(ctx: object) -> dict:
            executed.append("draft")
            return {"draft": "ok"}

        @decision(name="route.decision", vocabulary={"ship", "revise", "defer"})
        def route(ctx: object) -> str:
            executed.append("route")
            return "ship"

        @phase
        def child_step(ctx: object) -> dict:
            executed.append("child_step")
            return {"child": True}

        @_workflow(
            name="child",
            id="workflow.child",
            inputs={"type": "object", "required": ["seed"]},
            outputs={"type": "object", "required": ["child"]},
        )
        def child(ctx: object) -> dict:
            state = yield child_step(ctx)
            return state

        @decision(name="loop.guard", vocabulary={"again", "done"})
        def guard(ctx: object) -> str:
            executed.append("guard")
            return "done"

        @phase(
            inputs={"type": "object", "required": ["item"]},
            outputs={"type": "object", "required": ["verdict"]},
        )
        def mapper(ctx: object) -> dict:
            executed.append("mapper")
            return {"verdict": "ok"}

        def reduce_results(results: list[dict[str, str]]) -> dict:
            return {"results": results}

        @pipeline
        def parent(ctx: object) -> dict:
            state = yield draft(ctx)
            if route(ctx) == "ship":
                state = yield child(ctx, id="child.call")
            while guard(ctx) == "again":
                state = yield draft(ctx)
            state = yield parallel_map(
                items="checks",
                step=mapper,
                reducer=reduce_results,
                path_template="item/{item_id}",
                name="review_batch",
                id="review.batch",
            )
            return state

        program = compile_pipeline(parent)

        assert executed == []
        assert isinstance(program.topology, NativeTopology)
        assert derive_topology(program) == program.topology

        nodes_by_kind: dict[str, list[object]] = {}
        for node in program.topology.nodes:
            nodes_by_kind.setdefault(node.kind, []).append(node)

        phase_paths = {node.path for node in nodes_by_kind["phase"]}
        assert "root/draft.phase" in phase_paths
        assert "root/review.batch/item/{item_id}" in phase_paths

        decision_node = nodes_by_kind["decision"][0]
        assert decision_node.path == "root/route.decision"
        assert decision_node.metadata["vocabulary"] == ["defer", "revise", "ship"]

        loop_node = nodes_by_kind["loop"][0]
        assert loop_node.path == "root/loop.guard"
        assert loop_node.metadata["loop_stable_id"] == "loop.guard"
        assert loop_node.metadata["guard_name"] == "guard"

        child_node = nodes_by_kind["child_workflow"][0]
        assert child_node.path == "root/child.call"
        assert child_node.metadata["child_stable_id"] == "workflow.child"
        assert child_node.metadata["inputs_schema"] == {
            "type": "object",
            "required": ["seed"],
        }
        assert child_node.metadata["outputs_schema"] == {
            "type": "object",
            "required": ["child"],
        }

        dynamic_map_node = nodes_by_kind["dynamic_map"][0]
        dynamic_map_metadata = dynamic_map_node.metadata["dynamic_map_metadata"]
        assert isinstance(dynamic_map_metadata, DynamicMapMetadata)
        assert dynamic_map_metadata.items_ref == "checks"
        assert dynamic_map_metadata.mapper_name == "mapper"
        assert dynamic_map_metadata.path_template == "item/{item_id}"
        assert dynamic_map_metadata.collection_schema == {
            "type": "object",
            "required": ["item"],
        }
        assert dynamic_map_metadata.reducer_name == "reduce_results"
        assert dynamic_map_metadata.fan_in is True

    def test_repeated_child_call_sites_keep_distinct_topology_paths(self) -> None:
        @phase
        def child_step(ctx: object) -> dict:
            return {"child": "ok"}

        @_workflow
        def child(ctx: object) -> dict:
            state = yield child_step(ctx)
            return state

        @pipeline
        def parent(ctx: object) -> dict:
            state = yield child(ctx, id="child.first")
            state = yield child(ctx, id="child.second")
            return state

        program = compile_pipeline(parent)
        child_paths = [
            node.path
            for node in program.topology.nodes
            if node.kind == "child_workflow"
        ]
        assert child_paths == ["root/child.first", "root/child.second"]
