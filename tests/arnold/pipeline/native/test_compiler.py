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
    NativeCompileError,
    NativeDecision,
    NativeInstruction,
    NativeLoopGuard,
    NativePhase,
    NativeProgram,
    compile_pipeline,
    decision,
    phase,
    pipeline,
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
            instructions=instrs,
            description="A test",
        )
        assert prog.name == "test_prog"
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
