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
- Control-override short-circuit (body skipped) vs additive-override (body called)
- Override application recording via body-call counters
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
    parallel,
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


# ── Executor-owned key merge: CAS (typed-ports-on) ────────────────────


class TestMergeStateCAS:
    """merge_state with CAS semantics (typed-ports-on behaviour).

    Proves that a Megaplan-aware merge_state hook applies each output key
    through versioned StateDelta replacement, tracks _state_meta.versions,
    and rejects stale writes with StateDeltaConflict.
    """

    def test_cas_merge_tracks_versions(self) -> None:
        """merge_state via CAS bumps _state_meta.versions for each key."""
        from arnold.pipelines.megaplan._pipeline.types import (
            StateDelta,
            apply_delta,
        )

        class CASHooks(NullNativeRuntimeHooks):
            def merge_state(self, instr, state, outputs, owned_keys):
                state = dict(state)
                new_owned = set(owned_keys)
                for k, v in outputs.items():
                    versions = (
                        state.get("_state_meta", {}).get("versions", {})
                        if isinstance(state, dict)
                        else {}
                    )
                    current_ver = int(versions.get(k, 0))
                    state, _ = apply_delta(
                        state,
                        StateDelta(
                            op="replace", key=k, value=v, version=current_ver
                        ),
                    )
                    new_owned.add(k)
                return state, frozenset(new_owned)

        hooks = CASHooks()

        @phase
        def step_a(ctx: dict) -> dict:
            return {"x": 1, "y": "hello"}

        @phase
        def step_b(ctx: dict) -> dict:
            return {"x": 2, "z": [1, 2]}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            s = yield step_a(ctx)
            s = yield step_b(ctx)
            return s

        prog = compile_pipeline(my_pipe)
        result = run_native_pipeline(prog, hooks=hooks)

        assert result.state["x"] == 2
        assert result.state["y"] == "hello"
        assert result.state["z"] == [1, 2]

        meta = result.state.get("_state_meta", {})
        versions = meta.get("versions", {})
        # x was written twice (step_a→1, step_b→2), version should be 2
        assert versions["x"] == 2
        # y was written once, version should be 1
        assert versions["y"] == 1
        # z was written once, version should be 1
        assert versions["z"] == 1

    def test_cas_merge_accumulates_owned_keys(self) -> None:
        """merge_state via CAS adds each merged key to owned_keys."""
        from arnold.pipelines.megaplan._pipeline.types import (
            StateDelta,
            apply_delta,
        )

        recorded_owned: list[frozenset[str]] = []

        class CASHooks(NullNativeRuntimeHooks):
            def on_stage_complete(self, instr, ctx, result, state, owned_keys):
                recorded_owned.append(frozenset(owned_keys))

            def merge_state(self, instr, state, outputs, owned_keys):
                state = dict(state)
                new_owned = set(owned_keys)
                for k, v in outputs.items():
                    versions = (
                        state.get("_state_meta", {}).get("versions", {})
                        if isinstance(state, dict)
                        else {}
                    )
                    current_ver = int(versions.get(k, 0))
                    state, _ = apply_delta(
                        state,
                        StateDelta(
                            op="replace", key=k, value=v, version=current_ver
                        ),
                    )
                    new_owned.add(k)
                return state, frozenset(new_owned)

        hooks = CASHooks()

        @phase
        def step_a(ctx: dict) -> dict:
            return {"a": 1}

        @phase
        def step_b(ctx: dict) -> dict:
            return {"b": 2}

        @phase
        def step_c(ctx: dict) -> dict:
            return {"c": 3, "a": 99}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            s = yield step_a(ctx)
            s = yield step_b(ctx)
            s = yield step_c(ctx)
            return s

        prog = compile_pipeline(my_pipe)
        run_native_pipeline(prog, hooks=hooks)

        assert len(recorded_owned) == 3
        assert recorded_owned[0] == frozenset({"a"})
        assert recorded_owned[1] == frozenset({"a", "b"})
        assert recorded_owned[2] == frozenset({"a", "b", "c"})

    def test_cas_stale_write_rejected(self) -> None:
        """A stale-version write through merge_state raises StateDeltaConflict.

        The native runtime pre-applies ``state.update(outputs)`` before
        calling ``merge_state``, so the value is already present.  The
        CAS hook's role is to detect the stale version and refuse to bump
        ``_state_meta.versions`` — proving the conflict-detection path
        is exercised without crashing the pipeline.
        """
        from arnold.pipelines.megaplan._pipeline.types import (
            StateDelta,
            StateDeltaConflict,
            apply_delta,
        )

        # Simulate a hook that always passes version=0 — the second write
        # should conflict because _state_meta.versions[x] is already 1.
        stale_attempted: list[bool] = []

        class StaleCASHooks(NullNativeRuntimeHooks):
            def merge_state(self, instr, state, outputs, owned_keys):
                state = dict(state)
                new_owned = set(owned_keys)
                for k, v in outputs.items():
                    try:
                        state, _ = apply_delta(
                            state,
                            StateDelta(
                                op="replace", key=k, value=v, version=0
                            ),
                        )
                        new_owned.add(k)
                    except StateDeltaConflict:
                        stale_attempted.append(True)
                        # Do not mutate state or add to owned_keys on conflict
                return state, frozenset(new_owned)

        hooks = StaleCASHooks()

        @phase
        def step_a(ctx: dict) -> dict:
            return {"x": "first"}

        @phase
        def step_b(ctx: dict) -> dict:
            return {"x": "second"}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            s = yield step_a(ctx)
            s = yield step_b(ctx)
            return s

        prog = compile_pipeline(my_pipe)
        result = run_native_pipeline(prog, hooks=hooks)

        # The stale write was attempted and rejected
        assert len(stale_attempted) == 1
        # Version should be 1 (only the first CAS write succeeded;
        # the runtime's pre-apply put the value in state but the CAS
        # hook refused to bump the version on the stale attempt).
        assert result.state["_state_meta"]["versions"]["x"] == 1

    def test_cas_bootstrap_version_zero(self) -> None:
        """First write to a key with version=0 succeeds and sets version to 1."""
        from arnold.pipelines.megaplan._pipeline.types import (
            StateDelta,
            apply_delta,
        )

        class CASHooks(NullNativeRuntimeHooks):
            def merge_state(self, instr, state, outputs, owned_keys):
                state = dict(state)
                new_owned = set(owned_keys)
                for k, v in outputs.items():
                    versions = (
                        state.get("_state_meta", {}).get("versions", {})
                        if isinstance(state, dict)
                        else {}
                    )
                    current_ver = int(versions.get(k, 0))
                    state, _ = apply_delta(
                        state,
                        StateDelta(
                            op="replace", key=k, value=v, version=current_ver
                        ),
                    )
                    new_owned.add(k)
                return state, frozenset(new_owned)

        hooks = CASHooks()

        @phase
        def step(ctx: dict) -> dict:
            return {"key": "value"}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            s = yield step(ctx)
            return s

        prog = compile_pipeline(my_pipe)
        result = run_native_pipeline(prog, hooks=hooks)

        assert result.state["key"] == "value"
        assert result.state["_state_meta"]["versions"]["key"] == 1


# ── Executor-owned key merge: plain dict.update (typed-ports-off) ─────


class TestMergeStatePlainUpdate:
    """merge_state with plain dict.update (typed-ports-off behaviour).

    Proves that when typed ports are off, state merge is a simple
    dict.update — no _state_meta tracking, no CAS, no conflict detection.
    """

    def test_plain_update_no_versions(self) -> None:
        """merge_state via dict.update does not create _state_meta."""
        class PlainUpdateHooks(NullNativeRuntimeHooks):
            def merge_state(self, instr, state, outputs, owned_keys):
                state = dict(state)
                state.update(outputs)
                new_owned = set(owned_keys) | set(outputs.keys())
                return state, frozenset(new_owned)

        hooks = PlainUpdateHooks()

        @phase
        def step_a(ctx: dict) -> dict:
            return {"x": 1, "y": 2}

        @phase
        def step_b(ctx: dict) -> dict:
            return {"x": 99, "z": 3}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            s = yield step_a(ctx)
            s = yield step_b(ctx)
            return s

        prog = compile_pipeline(my_pipe)
        result = run_native_pipeline(prog, hooks=hooks)

        # Values are correct (last-writer-wins)
        assert result.state["x"] == 99
        assert result.state["y"] == 2
        assert result.state["z"] == 3

        # No _state_meta tracking
        assert "_state_meta" not in result.state

    def test_plain_update_accumulates_owned_keys(self) -> None:
        """merge_state via dict.update adds all output keys to owned_keys."""
        recorded_owned: list[frozenset[str]] = []

        class PlainUpdateHooks(NullNativeRuntimeHooks):
            def on_stage_complete(self, instr, ctx, result, state, owned_keys):
                recorded_owned.append(frozenset(owned_keys))

            def merge_state(self, instr, state, outputs, owned_keys):
                state = dict(state)
                state.update(outputs)
                new_owned = set(owned_keys) | set(outputs.keys())
                return state, frozenset(new_owned)

        hooks = PlainUpdateHooks()

        @phase
        def step_a(ctx: dict) -> dict:
            return {"a": 1}

        @phase
        def step_b(ctx: dict) -> dict:
            return {"b": 2, "c": 3}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            s = yield step_a(ctx)
            s = yield step_b(ctx)
            return s

        prog = compile_pipeline(my_pipe)
        run_native_pipeline(prog, hooks=hooks)

        assert len(recorded_owned) == 2
        assert recorded_owned[0] == frozenset({"a"})
        assert recorded_owned[1] == frozenset({"a", "b", "c"})

    def test_plain_update_silent_overwrite(self) -> None:
        """Plain update silently overwrites — no conflict detection."""
        class PlainUpdateHooks(NullNativeRuntimeHooks):
            def merge_state(self, instr, state, outputs, owned_keys):
                state = dict(state)
                state.update(outputs)
                new_owned = set(owned_keys) | set(outputs.keys())
                return state, frozenset(new_owned)

        hooks = PlainUpdateHooks()

        @phase
        def step_a(ctx: dict) -> dict:
            return {"x": "first"}

        @phase
        def step_b(ctx: dict) -> dict:
            return {"x": "second"}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            s = yield step_a(ctx)
            s = yield step_b(ctx)
            return s

        prog = compile_pipeline(my_pipe)
        result = run_native_pipeline(prog, hooks=hooks)

        # Last writer wins silently — no error, no version tracking
        assert result.state["x"] == "second"
        assert "_state_meta" not in result.state

    def test_plain_update_versus_cas_consistency(self) -> None:
        """Same pipeline yields identical key-values with both merge modes."""
        from arnold.pipelines.megaplan._pipeline.types import (
            StateDelta,
            apply_delta,
        )

        class CASHooks(NullNativeRuntimeHooks):
            def merge_state(self, instr, state, outputs, owned_keys):
                state = dict(state)
                new_owned = set(owned_keys)
                for k, v in outputs.items():
                    versions = (
                        state.get("_state_meta", {}).get("versions", {})
                        if isinstance(state, dict)
                        else {}
                    )
                    current_ver = int(versions.get(k, 0))
                    state, _ = apply_delta(
                        state,
                        StateDelta(
                            op="replace", key=k, value=v, version=current_ver
                        ),
                    )
                    new_owned.add(k)
                return state, frozenset(new_owned)

        class PlainHooks(NullNativeRuntimeHooks):
            def merge_state(self, instr, state, outputs, owned_keys):
                state = dict(state)
                state.update(outputs)
                new_owned = set(owned_keys) | set(outputs.keys())
                return state, frozenset(new_owned)

        @phase
        def step_a(ctx: dict) -> dict:
            return {"x": 1, "y": "a"}

        @phase
        def step_b(ctx: dict) -> dict:
            return {"x": 2, "z": [1, 2, 3]}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            s = yield step_a(ctx)
            s = yield step_b(ctx)
            return s

        prog = compile_pipeline(my_pipe)

        cas_result = run_native_pipeline(prog, hooks=CASHooks())
        plain_result = run_native_pipeline(prog, hooks=PlainHooks())

        # Both modes produce the same final values for non-meta keys
        for key in ("x", "y", "z"):
            assert cas_result.state[key] == plain_result.state[key], (
                f"key {key!r} differs: CAS={cas_result.state[key]!r} "
                f"vs plain={plain_result.state[key]!r}"
            )

        # But only CAS tracks _state_meta
        assert "_state_meta" in cas_result.state
        assert "_state_meta" not in plain_result.state


# ── Control-override vs additive-override behaviour ────────────────────


class TestControlOverrideShortCircuit:
    """Control overrides skip the decision body; additive overrides do not."""

    def test_control_override_skips_decision_body(self) -> None:
        """When __override_route__ is set, the decision body is NOT called."""
        body_calls: list[str] = []

        @phase
        def on_left(ctx: dict) -> dict:
            return {"path": "left"}

        @phase
        def on_override(ctx: dict) -> dict:
            return {"path": "override"}

        @decision(vocabulary={"left", "right", "override"})
        def decide(ctx: dict) -> str:
            body_calls.append("decide")
            return "left"

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            if decide(ctx) == "left":
                s = yield on_left(ctx)
            elif decide(ctx) == "right":
                s = yield on_left(ctx)
            elif decide(ctx) == "override":
                s = yield on_override(ctx)
            else:
                s = {}
            return s

        prog = compile_pipeline(my_pipe)

        # Hook that injects a control override via __override_route__
        class ControlOverrideHook(NullNativeRuntimeHooks):
            def on_step_start(self, instr, ctx):
                if instr.op == "decision":
                    ctx["__override_route__"] = "override"
                return ctx

        hooks = ControlOverrideHook()
        result = run_native_pipeline(prog, hooks=hooks)

        # Decision body was NEVER called
        assert body_calls == [], (
            f"Decision body was called {len(body_calls)} time(s); "
            f"control override should short-circuit it"
        )

        # Override route was followed
        assert result.state.get("path") == "override"

    def test_additive_override_still_calls_body(self) -> None:
        """Additive overrides mutate state but the decision body IS called."""
        body_calls: list[str] = []

        @phase
        def step_a(ctx: dict) -> dict:
            return {"before": True}

        @phase
        def step_b(ctx: dict) -> dict:
            return {"after": True}

        @decision(vocabulary={"yes", "no"})
        def decide(ctx: dict) -> str:
            body_calls.append("decide")
            state = ctx.get("state", {})
            # Additive override should have set this
            if state.get("meta", {}).get("note_added"):
                return "yes"
            return "no"

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            s = yield step_a(ctx)
            if decide(ctx) == "yes":
                s = yield step_b(ctx)
            return s

        prog = compile_pipeline(my_pipe)

        # Hook that applies an additive override (mutates state, no
        # __override_route__ set).
        class AdditiveOverrideHook(NullNativeRuntimeHooks):
            def on_step_start(self, instr, ctx):
                if instr.op == "decision":
                    state = ctx.get("state")
                    if isinstance(state, dict):
                        state.setdefault("meta", {})["note_added"] = True
                        ctx["state"] = state
                return ctx

        hooks = AdditiveOverrideHook()
        result = run_native_pipeline(prog, hooks=hooks)

        # Decision body WAS called (the additive override caused it to
        # choose "yes" based on the modified state)
        assert body_calls == ["decide"], (
            f"Decision body calls: {body_calls}; "
            f"additive override should NOT short-circuit the body"
        )

        # The additive override's state mutation was effective
        assert result.state.get("before") is True
        assert result.state.get("after") is True

    def test_override_application_is_recorded(self) -> None:
        """When a control override fires, its application is observable."""
        override_record: list[dict[str, object]] = []

        @phase
        def final(ctx: dict) -> dict:
            return {"done": True}

        @decision(vocabulary={"pass", "override"})
        def decide(ctx: dict) -> str:
            return "pass"

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            if decide(ctx) == "pass":
                s = yield final(ctx)
            elif decide(ctx) == "override":
                s = yield final(ctx)
            return s

        prog = compile_pipeline(my_pipe)

        class RecordingOverrideHook(NullNativeRuntimeHooks):
            def on_step_start(self, instr, ctx):
                if instr.op == "decision":
                    ctx["__override_route__"] = "override"
                    override_record.append({
                        "action": "override",
                        "phase": instr.name,
                    })
                return ctx

            def on_step_end(self, instr, ctx, result):
                if isinstance(result, dict) and "__override_route__" in result:
                    override_record.append({
                        "action": result["__override_route__"],
                        "phase": instr.name,
                        "event": "on_step_end",
                    })
                return result

        hooks = RecordingOverrideHook()
        result = run_native_pipeline(prog, hooks=hooks)

        # Override was recorded in on_step_start
        assert any(
            e.get("action") == "override" and e.get("phase") == "decide"
            for e in override_record
        ), f"No override_record entry for on_step_start: {override_record}"

        # The synthetic result from the short-circuit carries the override
        # metadata and is visible in on_step_end.
        assert any(
            e.get("event") == "on_step_end"
            for e in override_record
        ), f"No on_step_end entry in override_record: {override_record}"

        # Final state confirms the pipeline completed
        assert result.state.get("done") is True

    def test_control_override_falls_back_to_override_label(self) -> None:
        """When the action name is not in the vocabulary, 'override' is used."""
        body_calls: list[str] = []

        @phase
        def on_pass(ctx: dict) -> dict:
            return {"branch": "pass"}

        @phase
        def on_override(ctx: dict) -> dict:
            return {"branch": "override"}

        @decision(vocabulary={"pass", "override"})
        def decide(ctx: dict) -> str:
            body_calls.append("decide")
            return "pass"

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            if decide(ctx) == "pass":
                s = yield on_pass(ctx)
            elif decide(ctx) == "override":
                s = yield on_override(ctx)
            return s

        prog = compile_pipeline(my_pipe)

        # Inject an action name that is NOT in the vocabulary
        class FallbackOverrideHook(NullNativeRuntimeHooks):
            def on_step_start(self, instr, ctx):
                if instr.op == "decision":
                    # "abort" is not in {"pass", "override"} vocabulary
                    ctx["__override_route__"] = "abort"
                return ctx

        hooks = FallbackOverrideHook()
        result = run_native_pipeline(prog, hooks=hooks)

        # Body was NOT called — the override short-circuit fired,
        # fell back to "override" label.
        assert body_calls == [], (
            f"Decision body was called {len(body_calls)} time(s)"
        )

        # The "override" branch was taken
        assert result.state.get("branch") == "override"

    def test_control_override_with_matching_action_label(self) -> None:
        """When the action name IS in the vocabulary, it is used directly."""
        body_calls: list[str] = []

        @phase
        def on_pass(ctx: dict) -> dict:
            return {"branch": "pass"}

        @phase
        def on_abort(ctx: dict) -> dict:
            return {"branch": "abort"}

        @decision(vocabulary={"pass", "abort"})
        def decide(ctx: dict) -> str:
            body_calls.append("decide")
            return "pass"

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            if decide(ctx) == "pass":
                s = yield on_pass(ctx)
            elif decide(ctx) == "abort":
                s = yield on_abort(ctx)
            return s

        prog = compile_pipeline(my_pipe)

        class ExactMatchOverrideHook(NullNativeRuntimeHooks):
            def on_step_start(self, instr, ctx):
                if instr.op == "decision":
                    # "abort" IS in the vocabulary — used as-is
                    ctx["__override_route__"] = "abort"
                return ctx

        hooks = ExactMatchOverrideHook()
        result = run_native_pipeline(prog, hooks=hooks)

        assert body_calls == [], (
            f"Decision body was called {len(body_calls)} time(s)"
        )
        assert result.state.get("branch") == "abort"

    def test_no_override_falls_through_to_normal_execution(self) -> None:
        """When __override_route__ is not set, decisions execute normally."""
        body_calls: list[str] = []

        @phase
        def on_yes(ctx: dict) -> dict:
            return {"branch": "yes"}

        @decision(vocabulary={"yes", "no"})
        def decide(ctx: dict) -> str:
            body_calls.append("decide")
            return "yes"

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            if decide(ctx) == "yes":
                s = yield on_yes(ctx)
            return s

        prog = compile_pipeline(my_pipe)

        # Null hooks (no override) — decisions execute normally
        result = run_native_pipeline(prog, hooks=NullNativeRuntimeHooks())

        assert body_calls == ["decide"]
        assert result.state.get("branch") == "yes"


# ── parallel fan-out / fan-in runtime (M5a baseline) ──────────────────


class TestParallelRuntime:
    """Runtime executes parallel blocks compiled from ``for x in parallel(...)``."""

    def test_parallel_branches_run_sequentially(self) -> None:
        @phase
        def branch_a(ctx: dict) -> dict:
            return {"a": 1}

        @phase
        def branch_b(ctx: dict) -> dict:
            return {"b": 2}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            for branch in parallel([branch_a, branch_b]):
                state = yield branch(ctx)
            return state

        prog = compile_pipeline(my_pipe)
        result = run_native_pipeline(prog)
        assert result.state == {"a": 1, "b": 2}
        assert len(result.stages) == 2

    def test_parallel_with_reducer(self) -> None:
        @phase
        def branch_a(ctx: dict) -> dict:
            return {"value": 1}

        @phase
        def branch_b(ctx: dict) -> dict:
            return {"value": 2}

        def reducer(results: list[dict]) -> dict:
            return {"total": sum(r["value"] for r in results)}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            for branch in parallel([branch_a, branch_b], reducer=reducer):
                state = yield branch(ctx)
            return state

        prog = compile_pipeline(my_pipe)
        result = run_native_pipeline(prog)
        # Reducer is currently stored in IR; the no-op sequential runtime does
        # not invoke it automatically, so state is the last branch's output.
        # This test documents the current M5a contract.
        assert "value" in result.state

    def test_yield_parallel_call_rejected(self) -> None:
        @phase
        def branch_a(ctx: dict) -> dict:
            return {"a": 1}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            state = yield parallel([branch_a])  # type: ignore[misc]
            return state

        from arnold.pipeline.native import NativeCompileError
        with pytest.raises(NativeCompileError) as exc_info:
            compile_pipeline(my_pipe)
        assert "for branch in parallel" in str(exc_info.value)
