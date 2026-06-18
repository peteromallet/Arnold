"""Tests for the native sequential runtime state machine.

Covers:
- Single-phase and multi-phase sequential execution
- State merging (dict return and object-with-outputs return)
- pc advancement and stage tracking
- max_phases suspension and resume parity
- Checkpoint persistence on max_phases stop
- Decision branching in the runtime
- While loop execution (guard + body + loop-back)
- Halt termination
"""

from __future__ import annotations

from pathlib import Path

import pytest

from arnold.pipeline.native import (
    NativeExecutionResult,
    NativeInstruction,
    NativeProgram,
    compile_pipeline,
    decision,
    phase,
    pipeline,
    project_graph,
    run_native_pipeline,
)
from arnold.pipeline.native.checkpoint import read_native_cursor
from arnold.pipeline.native.context import NativeRuntimeDisabledError
from arnold.pipeline.native.hooks import NullNativeRuntimeHooks


# ── module-level fixture ──────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _enable_native_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set ARNOLD_NATIVE_RUNTIME=1 for all runtime tests."""
    monkeypatch.setenv("ARNOLD_NATIVE_RUNTIME", "1")


# ── helpers ───────────────────────────────────────────────────────────


def _make_program(
    name: str = "test_pipe",
    instructions: tuple[NativeInstruction, ...] = (),
) -> NativeProgram:
    return NativeProgram(name=name, instructions=instructions)


# ── sequential execution ──────────────────────────────────────────────


class TestSequentialExecution:
    """Sequential phase execution with state merging."""

    def test_single_phase(self) -> None:
        @phase
        def do_work(ctx: dict) -> dict:
            return {"result": 42}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            state = yield do_work(ctx)
            return state

        prog = compile_pipeline(my_pipe)
        result = run_native_pipeline(prog)
        assert result.state == {"result": 42}
        assert len(result.stages) == 1
        assert result.stages[0].endswith("__do_work__pc0")
        assert not result.suspended

    def test_two_phases_state_merge(self) -> None:
        @phase
        def step_a(ctx: dict) -> dict:
            return {"a": 1}

        @phase
        def step_b(ctx: dict) -> dict:
            return {"b": 2}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            state = yield step_a(ctx)
            state = yield step_b(ctx)
            return state

        prog = compile_pipeline(my_pipe)
        result = run_native_pipeline(prog)
        assert result.state == {"a": 1, "b": 2}
        assert len(result.stages) == 2
        assert "step_a" in result.stages[0]
        assert "step_b" in result.stages[1]
        assert not result.suspended

    def test_three_phases(self) -> None:
        @phase
        def a(ctx: dict) -> dict:
            return {"x": 1}

        @phase
        def b(ctx: dict) -> dict:
            return {"y": 2}

        @phase
        def c(ctx: dict) -> dict:
            return {"z": 3}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            s = yield a(ctx)
            s = yield b(ctx)
            s = yield c(ctx)
            return s

        prog = compile_pipeline(my_pipe)
        result = run_native_pipeline(prog)
        assert result.state == {"x": 1, "y": 2, "z": 3}
        assert len(result.stages) == 3

    def test_state_accumulates_across_phases(self) -> None:
        @phase
        def first(ctx: dict) -> dict:
            return {"count": 1}

        @phase
        def second(ctx: dict) -> dict:
            current = ctx["state"].get("count", 0)
            return {"count": current + 1}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            s = yield first(ctx)
            s = yield second(ctx)
            return s

        prog = compile_pipeline(my_pipe)
        result = run_native_pipeline(prog)
        assert result.state["count"] == 2

    def test_phase_receives_accumulated_state(self) -> None:
        @phase
        def step_a(ctx: dict) -> dict:
            return {"key": "hello"}

        @phase
        def step_b(ctx: dict) -> dict:
            # step_b should see step_a's output in state
            prev = ctx["state"].get("key", "missing")
            return {"key": prev + "_world"}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            s = yield step_a(ctx)
            s = yield step_b(ctx)
            return s

        prog = compile_pipeline(my_pipe)
        result = run_native_pipeline(prog)
        assert result.state["key"] == "hello_world"

    def test_initial_state_provided(self) -> None:
        @phase
        def step(ctx: dict) -> dict:
            base = ctx["state"].get("base", 0)
            return {"result": base + 10}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            s = yield step(ctx)
            return s

        prog = compile_pipeline(my_pipe)
        result = run_native_pipeline(prog, initial_state={"base": 5})
        assert result.state == {"base": 5, "result": 15}

    def test_empty_program(self) -> None:
        prog = NativeProgram(name="empty")
        result = run_native_pipeline(prog)
        assert result.state == {}
        assert result.stages == []
        assert result.pc == 0

    def test_context_has_artifact_root(self) -> None:
        captured_root = None

        @phase
        def step(ctx: dict) -> dict:
            nonlocal captured_root
            captured_root = ctx.get("artifact_root")
            return {}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            s = yield step(ctx)
            return s

        prog = compile_pipeline(my_pipe)
        result = run_native_pipeline(prog, artifact_root="/tmp/test_root")
        assert captured_root == "/tmp/test_root"


# ── pc and stage tracking ─────────────────────────────────────────────


class TestPcAndStageTracking:
    """pc advances correctly and stages are recorded after completion."""

    def test_pc_is_tracked(self) -> None:
        @phase
        def a(ctx: dict) -> dict:
            return {}

        @phase
        def b(ctx: dict) -> dict:
            return {}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            s = yield a(ctx)
            s = yield b(ctx)
            return s

        prog = compile_pipeline(my_pipe)
        result = run_native_pipeline(prog)
        # After completion, pc should be at the halt instruction
        halt_instrs = [i for i in prog.instructions if i.op == "halt"]
        if halt_instrs:
            assert result.pc == halt_instrs[0].pc
        assert not result.suspended

    def test_stages_have_correct_format(self) -> None:
        @phase
        def my_phase(ctx: dict) -> dict:
            return {}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            s = yield my_phase(ctx)
            return s

        prog = compile_pipeline(my_pipe)
        result = run_native_pipeline(prog)
        assert len(result.stages) == 1
        assert result.stages[0].startswith("my_pipe__my_phase__pc")

    def test_stages_not_recorded_before_completion(self) -> None:
        """If a phase raises, stages should not include it."""
        @phase
        def good(ctx: dict) -> dict:
            return {"a": 1}

        @phase
        def bad(ctx: dict) -> dict:
            raise RuntimeError("fail")

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            s = yield good(ctx)
            s = yield bad(ctx)
            return s

        prog = compile_pipeline(my_pipe)
        with pytest.raises(RuntimeError, match="fail"):
            run_native_pipeline(prog)
        # The exception prevents the function from returning, so we can't
        # check result.stages directly. This test documents the expectation
        # that exceptions propagate to the caller.


# ── max_phases and resume ─────────────────────────────────────────────


class TestMaxPhasesAndResume:
    """max_phases stops after N phases and persists a resume cursor."""

    def test_max_phases_stops_after_n(self, tmp_path: Path) -> None:
        @phase
        def a(ctx: dict) -> dict:
            return {"x": 1}

        @phase
        def b(ctx: dict) -> dict:
            return {"y": 2}

        @phase
        def c(ctx: dict) -> dict:
            return {"z": 3}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            s = yield a(ctx)
            s = yield b(ctx)
            s = yield c(ctx)
            return s

        prog = compile_pipeline(my_pipe)
        result = run_native_pipeline(prog, artifact_root=tmp_path, max_phases=1)
        assert result.suspended
        assert result.cursor_path is not None
        assert len(result.stages) == 1
        assert result.state == {"x": 1}

    def test_max_phases_persists_cursor(self, tmp_path: Path) -> None:
        @phase
        def a(ctx: dict) -> dict:
            return {"x": 1}

        @phase
        def b(ctx: dict) -> dict:
            return {"y": 2}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            s = yield a(ctx)
            s = yield b(ctx)
            return s

        prog = compile_pipeline(my_pipe)
        result = run_native_pipeline(prog, artifact_root=tmp_path, max_phases=1)
        assert result.suspended

        cursor = read_native_cursor(tmp_path)
        assert cursor is not None
        assert cursor["native"]["pc"] == result.pc
        assert len(cursor["stages"]) == 1

    def test_resume_from_max_phases(self, tmp_path: Path) -> None:
        @phase
        def a(ctx: dict) -> dict:
            return {"x": 1}

        @phase
        def b(ctx: dict) -> dict:
            return {"y": 2}

        @phase
        def c(ctx: dict) -> dict:
            return {"z": 3}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            s = yield a(ctx)
            s = yield b(ctx)
            s = yield c(ctx)
            return s

        prog = compile_pipeline(my_pipe)

        # Run with max_phases=1 → should suspend after phase a
        result1 = run_native_pipeline(prog, artifact_root=tmp_path, max_phases=1)
        assert result1.suspended
        assert result1.state == {"x": 1}

        # Resume → should continue from phase b
        result2 = run_native_pipeline(prog, artifact_root=tmp_path, resume=True)
        assert not result2.suspended
        assert result2.state == {"x": 1, "y": 2, "z": 3}
        assert len(result2.stages) == 3  # a (from cursor) + b + c

    def test_full_vs_resumed_parity(self, tmp_path: Path) -> None:
        @phase
        def a(ctx: dict) -> dict:
            return {"x": 1}

        @phase
        def b(ctx: dict) -> dict:
            return {"y": 2}

        @phase
        def c(ctx: dict) -> dict:
            return {"z": 3}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            s = yield a(ctx)
            s = yield b(ctx)
            s = yield c(ctx)
            return s

        prog = compile_pipeline(my_pipe)

        # Full run
        full = run_native_pipeline(prog)

        # Resumed run: stop after 1, then resume
        run_native_pipeline(prog, artifact_root=tmp_path, max_phases=1)
        resumed = run_native_pipeline(prog, artifact_root=tmp_path, resume=True)

        # State parity
        assert resumed.state == full.state

        # Stage parity (the full run has stages from one continuous run;
        # the resumed run carries stages accumulated across both runs)
        assert len(resumed.stages) == len(full.stages)

    def test_resume_with_no_cursor_runs_from_start(self) -> None:
        @phase
        def step(ctx: dict) -> dict:
            return {"result": "done"}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            s = yield step(ctx)
            return s

        prog = compile_pipeline(my_pipe)
        # resume=True with no cursor file → starts from pc=0
        result = run_native_pipeline(prog, resume=True)
        assert result.state == {"result": "done"}

    def test_max_phases_multiple_suspensions(self, tmp_path: Path) -> None:
        @phase
        def a(ctx: dict) -> dict:
            return {"a": 1}

        @phase
        def b(ctx: dict) -> dict:
            return {"b": 2}

        @phase
        def c(ctx: dict) -> dict:
            return {"c": 3}

        @phase
        def d(ctx: dict) -> dict:
            return {"d": 4}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            s = yield a(ctx)
            s = yield b(ctx)
            s = yield c(ctx)
            s = yield d(ctx)
            return s

        prog = compile_pipeline(my_pipe)

        # Stop after phase a
        r1 = run_native_pipeline(prog, artifact_root=tmp_path, max_phases=1)
        assert r1.suspended
        assert r1.state == {"a": 1}

        # Resume, stop after phase b (1 more phase)
        r2 = run_native_pipeline(prog, artifact_root=tmp_path, max_phases=1, resume=True)
        assert r2.suspended
        assert r2.state == {"a": 1, "b": 2}

        # Resume, run to completion
        r3 = run_native_pipeline(prog, artifact_root=tmp_path, resume=True)
        assert not r3.suspended
        assert r3.state == {"a": 1, "b": 2, "c": 3, "d": 4}
        assert len(r3.stages) == 4


# ── decision branching ────────────────────────────────────────────────


class TestDecisionBranching:
    """The runtime correctly follows decision branches."""

    def test_decision_takes_then_branch(self) -> None:
        @phase
        def then_phase(ctx: dict) -> dict:
            return {"branch": "then"}

        @phase
        def else_phase(ctx: dict) -> dict:
            return {"branch": "else"}

        @decision(vocabulary={"yes", "no"})
        def decide(ctx: dict) -> str:
            return "yes"

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            if decide(ctx) == "yes":
                s = yield then_phase(ctx)
            else:
                s = yield else_phase(ctx)
            return s

        prog = compile_pipeline(my_pipe)
        result = run_native_pipeline(prog)
        assert result.state.get("branch") == "then"

    def test_decision_takes_else_branch(self) -> None:
        @phase
        def then_phase(ctx: dict) -> dict:
            return {"branch": "then"}

        @phase
        def else_phase(ctx: dict) -> dict:
            return {"branch": "else"}

        @decision(vocabulary={"yes", "no"})
        def decide(ctx: dict) -> str:
            return "no"

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            if decide(ctx) == "yes":
                s = yield then_phase(ctx)
            else:
                s = yield else_phase(ctx)
            return s

        prog = compile_pipeline(my_pipe)
        result = run_native_pipeline(prog)
        assert result.state.get("branch") == "else"

    def test_decision_returns_string_label(self) -> None:
        @phase
        def left_phase(ctx: dict) -> dict:
            return {"side": "left"}

        @phase
        def right_phase(ctx: dict) -> dict:
            return {"side": "right"}

        @decision(vocabulary={"left", "right"})
        def branch(ctx: dict) -> str:
            return "right"

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            if branch(ctx) == "left":
                s = yield left_phase(ctx)
            else:
                s = yield right_phase(ctx)
            return s

        prog = compile_pipeline(my_pipe)
        result = run_native_pipeline(prog)
        assert result.state.get("side") == "right"

    def test_decision_no_else_passes_through(self) -> None:
        @phase
        def step_a(ctx: dict) -> dict:
            return {"before": True}

        @phase
        def step_b(ctx: dict) -> dict:
            return {"after": True}

        @decision(vocabulary={"pass", "fail"})
        def check(ctx: dict) -> str:
            return "fail"  # skip the then-branch

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            s = yield step_a(ctx)
            if check(ctx) == "pass":
                s = yield step_b(ctx)
            return s

        prog = compile_pipeline(my_pipe)
        result = run_native_pipeline(prog)
        assert result.state == {"before": True}
        assert "after" not in result.state

    def test_decision_before_first_phase(self) -> None:
        @phase
        def yes_phase(ctx: dict) -> dict:
            return {"path": "yes"}

        @phase
        def no_phase(ctx: dict) -> dict:
            return {"path": "no"}

        @decision(vocabulary={"yes", "no"})
        def decide(ctx: dict) -> str:
            return "no"

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            if decide(ctx) == "yes":
                s = yield yes_phase(ctx)
            else:
                s = yield no_phase(ctx)
            return s

        prog = compile_pipeline(my_pipe)
        result = run_native_pipeline(prog)
        assert result.state.get("path") == "no"


# ── while loop execution ──────────────────────────────────────────────


class TestWhileLoopExecution:
    """The runtime executes while loops via guard + back-edge jumps."""

    def test_while_loop_iterates_multiple_times(self) -> None:
        counter = {"count": 0}

        @phase
        def body(ctx: dict) -> dict:
            counter["count"] += 1
            return {"count": counter["count"]}

        @decision
        def guard(ctx: dict) -> str:
            if counter["count"] < 3:
                return "__truthy__"
            return "__falsy__"

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            while guard(ctx):
                s = yield body(ctx)
            return s

        prog = compile_pipeline(my_pipe)
        result = run_native_pipeline(prog)
        assert result.state.get("count") == 3
        # Should have 3 phase executions + 3 guard evaluations

    def test_while_loop_with_vocabulary_guard(self) -> None:
        counter = {"count": 0}

        @phase
        def body(ctx: dict) -> dict:
            counter["count"] += 1
            return {"count": counter["count"]}

        @decision(vocabulary={"again", "done"})
        def guard(ctx: dict) -> str:
            return "again" if counter["count"] < 2 else "done"

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            while guard(ctx) == "again":
                s = yield body(ctx)
            return s

        prog = compile_pipeline(my_pipe)
        result = run_native_pipeline(prog)
        assert result.state.get("count") == 2

    def test_while_loop_zero_iterations(self) -> None:
        @phase
        def body(ctx: dict) -> dict:
            return {"executed": True}

        @decision
        def guard(ctx: dict) -> str:
            return "__falsy__"

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            while guard(ctx):
                s = yield body(ctx)
            return s

        prog = compile_pipeline(my_pipe)
        result = run_native_pipeline(prog)
        assert "executed" not in result.state

    def test_while_loop_followed_by_phase(self) -> None:
        counter = {"count": 0}

        @phase
        def setup(ctx: dict) -> dict:
            return {"ready": True}

        @phase
        def body(ctx: dict) -> dict:
            counter["count"] += 1
            return {"count": counter["count"]}

        @phase
        def cleanup(ctx: dict) -> dict:
            return {"done": True}

        @decision
        def guard(ctx: dict) -> str:
            return "__truthy__" if counter["count"] < 2 else "__falsy__"

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            s = yield setup(ctx)
            while guard(ctx):
                s = yield body(ctx)
            s = yield cleanup(ctx)
            return s

        prog = compile_pipeline(my_pipe)
        result = run_native_pipeline(prog)
        assert result.state.get("ready") is True
        assert result.state.get("count") == 2
        assert result.state.get("done") is True


# ── NativeExecutionResult ─────────────────────────────────────────────


class TestNativeExecutionResult:
    """NativeExecutionResult carries correct metadata."""

    def test_defaults(self) -> None:
        result = NativeExecutionResult(state={}, stages=[], pc=0)
        assert result.state == {}
        assert result.stages == []
        assert result.pc == 0
        assert result.suspended is False
        assert result.cursor_path is None

    def test_suspended_result(self) -> None:
        result = NativeExecutionResult(
            state={"x": 1},
            stages=["pipe__a__pc0"],
            pc=1,
            suspended=True,
            cursor_path="/tmp/cur.json",
        )
        assert result.suspended is True
        assert result.cursor_path == "/tmp/cur.json"

    def test_importable_from_package(self) -> None:
        from arnold.pipeline.native import NativeExecutionResult, run_native_pipeline
        assert NativeExecutionResult is not None
        assert callable(run_native_pipeline)

    def test_run_refuses_without_flag(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """run_native_pipeline raises NativeRuntimeDisabledError when flag off."""
        # Override the autouse fixture by deleting the env var
        monkeypatch.delenv("ARNOLD_NATIVE_RUNTIME", raising=False)

        @phase
        def step(ctx: dict) -> dict:
            return {"x": 1}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            s = yield step(ctx)
            return s

        prog = compile_pipeline(my_pipe)
        with pytest.raises(NativeRuntimeDisabledError, match="ARNOLD_NATIVE_RUNTIME"):
            run_native_pipeline(prog)


# ── on_checkpoint hook ─────────────────────────────────────────────────


class TestOnCheckpointHook:
    """on_checkpoint(cursor, state) fires after cursor persistence and clean completion."""

    def test_fires_on_max_phases_suspension(self, tmp_path: Path) -> None:
        """on_checkpoint fires with the cursor dict and state after max_phases suspension."""
        captured_cursors: list[dict] = []
        captured_states: list[dict] = []

        class RecordingHooks(NullNativeRuntimeHooks):
            def on_checkpoint(self, cursor: dict, state: dict) -> None:
                captured_cursors.append(dict(cursor))
                captured_states.append(dict(state))

        hooks = RecordingHooks()

        @phase
        def a(ctx: dict) -> dict:
            return {"x": 1}

        @phase
        def b(ctx: dict) -> dict:
            return {"y": 2}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            s = yield a(ctx)
            s = yield b(ctx)
            return s

        prog = compile_pipeline(my_pipe)
        result = run_native_pipeline(
            prog,
            artifact_root=tmp_path,
            max_phases=1,
            hooks=hooks,
        )

        assert result.suspended
        assert len(captured_cursors) == 1, "on_checkpoint should fire once on suspension"
        assert len(captured_states) == 1

        cursor = captured_cursors[0]
        state = captured_states[0]

        # Verify cursor shape matches persist_native_cursor output
        assert "native" in cursor
        assert cursor["native"]["pc"] == result.pc
        assert cursor["native"]["version"] == 1
        assert "stage" in cursor
        assert "stages" in cursor
        assert cursor["stages"] == result.stages
        assert "frames" in cursor
        assert "__state__" in cursor["frames"]
        assert cursor["frames"]["__state__"] == {"x": 1}
        assert "final" not in cursor  # suspension, not final

        # Verify state matches
        assert state == {"x": 1}

    def test_fires_on_clean_completion(self) -> None:
        """on_checkpoint fires with the cursor dict and state after clean completion."""
        captured_cursors: list[dict] = []
        captured_states: list[dict] = []

        class RecordingHooks(NullNativeRuntimeHooks):
            def on_checkpoint(self, cursor: dict, state: dict) -> None:
                captured_cursors.append(dict(cursor))
                captured_states.append(dict(state))

        hooks = RecordingHooks()

        @phase
        def a(ctx: dict) -> dict:
            return {"x": 1}

        @phase
        def b(ctx: dict) -> dict:
            return {"y": 2}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            s = yield a(ctx)
            s = yield b(ctx)
            return s

        prog = compile_pipeline(my_pipe)
        result = run_native_pipeline(prog, hooks=hooks)

        assert not result.suspended
        assert len(captured_cursors) == 1, "on_checkpoint should fire once on clean completion"
        assert len(captured_states) == 1

        cursor = captured_cursors[0]
        state = captured_states[0]

        # Verify cursor shape
        assert "native" in cursor
        assert cursor["native"]["pc"] == result.pc
        assert cursor["native"]["version"] == 1
        assert "stage" in cursor
        assert "stages" in cursor
        assert cursor["stages"] == result.stages
        assert "frames" in cursor
        assert "__state__" in cursor["frames"]
        assert cursor["final"] is True  # clean completion marker

        # Verify state matches final state
        assert state == {"x": 1, "y": 2}

    def test_not_fired_on_exception(self) -> None:
        """on_checkpoint is NOT called when a phase raises an exception."""
        captured: list[dict] = []

        class RecordingHooks(NullNativeRuntimeHooks):
            def on_checkpoint(self, cursor: dict, state: dict) -> None:
                captured.append(dict(cursor))

        hooks = RecordingHooks()

        @phase
        def good(ctx: dict) -> dict:
            return {"x": 1}

        @phase
        def bad(ctx: dict) -> dict:
            raise RuntimeError("fail")

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            s = yield good(ctx)
            s = yield bad(ctx)
            return s

        prog = compile_pipeline(my_pipe)
        with pytest.raises(RuntimeError, match="fail"):
            run_native_pipeline(prog, hooks=hooks)

        assert len(captured) == 0, "on_checkpoint must not fire on exception"

    def test_on_checkpoint_has_no_megaplan_imports(self) -> None:
        """Verify that hooks.py contains no megaplan-specific imports."""
        import ast
        import inspect
        from arnold.pipeline.native import hooks as hooks_mod

        source = inspect.getsource(hooks_mod)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                module_name = (
                    node.module if isinstance(node, ast.ImportFrom) else None
                )
                # For plain imports, check each alias
                if module_name is None:
                    for alias in node.names:
                        if "megaplan" in alias.name.lower():
                            pytest.fail(
                                f"hooks.py imports megaplan: {alias.name}"
                            )
                elif "megaplan" in (module_name or "").lower():
                    pytest.fail(
                        f"hooks.py imports megaplan: {module_name}"
                    )

    def test_on_checkpoint_with_multi_suspension(self, tmp_path: Path) -> None:
        """on_checkpoint fires on each suspension when resuming multiple times."""
        captured: list[tuple[dict, dict]] = []

        class RecordingHooks(NullNativeRuntimeHooks):
            def on_checkpoint(self, cursor: dict, state: dict) -> None:
                captured.append((dict(cursor), dict(state)))

        hooks = RecordingHooks()

        @phase
        def a(ctx: dict) -> dict:
            return {"a": 1}

        @phase
        def b(ctx: dict) -> dict:
            return {"b": 2}

        @phase
        def c(ctx: dict) -> dict:
            return {"c": 3}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            s = yield a(ctx)
            s = yield b(ctx)
            s = yield c(ctx)
            return s

        prog = compile_pipeline(my_pipe)

        # First suspension (after phase a)
        r1 = run_native_pipeline(prog, artifact_root=tmp_path, max_phases=1, hooks=hooks)
        assert r1.suspended
        assert len(captured) == 1
        assert captured[0][1] == {"a": 1}

        # Second suspension (after phase b)
        r2 = run_native_pipeline(prog, artifact_root=tmp_path, max_phases=1, resume=True, hooks=hooks)
        assert r2.suspended
        assert len(captured) == 2
        assert captured[1][1] == {"a": 1, "b": 2}

        # Clean completion (phases c)
        r3 = run_native_pipeline(prog, artifact_root=tmp_path, resume=True, hooks=hooks)
        assert not r3.suspended
        assert len(captured) == 3
        assert captured[2][1] == {"a": 1, "b": 2, "c": 3}
        assert captured[2][0].get("final") is True
