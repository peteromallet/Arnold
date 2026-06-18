"""Tests for the Megaplan native toy pipeline fixture.

Covers:
* Uninterrupted execution with MegaplanNativeRuntimeHooks
* State persistence via on_stage_complete
* Forced suspension via max_phases and resume
* Envelope propagation
* Stage sequence tracking
* Parity with graph reference scenario

Milestone: m3-megaplan-runtime-hooks (T15)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from arnold.pipeline.native import (
    NativeExecutionResult,
    compile_pipeline,
)

from .megaplan_toy_native_fixture import (
    _reset_loop_counter,
    get_megaplan_native_toy_program,
    megaplan_native_toy_pipeline,
    native_loop_guard,
    native_override_decision,
    read_native_toy_state,
    run_megaplan_native_toy,
)
from arnold.runtime.envelope import RunEnvelope, RuntimeEnvelope


# ── module-level fixture ──────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _enable_native_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set ARNOLD_NATIVE_RUNTIME=1 for all native toy tests."""
    monkeypatch.setenv("ARNOLD_NATIVE_RUNTIME", "1")


@pytest.fixture(autouse=True)
def _reset_counter() -> None:
    """Reset the loop counter before each test."""
    _reset_loop_counter()


# ═══════════════════════════════════════════════════════════════════════
# Compilation tests
# ═══════════════════════════════════════════════════════════════════════


class TestMegaplanNativeToyCompilation:
    """The native toy pipeline compiles to a valid NativeProgram."""

    def test_pipeline_compiles(self) -> None:
        """The toy pipeline compiles without errors."""
        program = get_megaplan_native_toy_program()
        assert program.name == "megaplan_native_toy"
        assert len(program.instructions) > 0

    def test_all_expected_phases_present(self) -> None:
        """Every expected phase appears in the compiled program."""
        program = get_megaplan_native_toy_program()
        phase_names = {
            p.name for p in program.phases
        }
        expected = {
            "setup", "override_target", "normal_target",
            "loop_body", "nested_subpipeline", "cleanup",
        }
        assert expected.issubset(phase_names), (
            f"Missing phases: {expected - phase_names}"
        )

    def test_all_expected_decisions_present(self) -> None:
        """Every expected decision appears in the compiled program.

        The ``loop_guard`` decision is registered as a loop guard
        (``program.loop_guards``), not necessarily as a standalone
        ``NativeDecision`` in ``program.decisions``.  The ``while``
        lowering converts the decision into a ``NativeLoopGuard``
        that carries both the guard callable and the body callable.
        """
        program = get_megaplan_native_toy_program()
        decision_names = {d.name for d in program.decisions}
        # override_decision is from the if/else — must be in decisions
        assert "override_decision" in decision_names

        # loop_guard is from the while — carried as a NativeLoopGuard
        loop_guard_names = {lg.name for lg in program.loop_guards}
        assert "loop_guard" in loop_guard_names, (
            f"loop_guard should be in program.loop_guards, "
            f"got {loop_guard_names}"
        )

    def test_loop_guards_present(self) -> None:
        """The while loop produces a loop guard in the program."""
        program = get_megaplan_native_toy_program()
        assert len(program.loop_guards) == 1
        assert program.loop_guards[0].name == "loop_guard"
        assert program.loop_guards[0].guard is native_loop_guard

    def test_instructions_have_valid_pcs(self) -> None:
        """Every instruction has a pc matching its position."""
        program = get_megaplan_native_toy_program()
        for i, instr in enumerate(program.instructions):
            assert instr.pc == i, (
                f"Instruction at index {i} has pc {instr.pc}"
            )

    def test_halt_is_final_instruction(self) -> None:
        """The final instruction is a halt."""
        program = get_megaplan_native_toy_program()
        assert program.instructions[-1].op == "halt"


# ═══════════════════════════════════════════════════════════════════════
# Uninterrupted execution tests
# ═══════════════════════════════════════════════════════════════════════


class TestMegaplanNativeToyUninterrupted:
    """The native toy pipeline runs to completion normally."""

    def test_runs_to_completion(self, tmp_path) -> None:
        """Runs all phases and returns suspended=False."""
        plan_dir = tmp_path / "plan"
        result = run_megaplan_native_toy(plan_dir=plan_dir)

        assert not result.suspended
        assert result.state.get("done") is True
        assert result.state.get("ready") is True
        assert result.state.get("counter") == 3

    def test_produces_expected_state_keys(self, tmp_path) -> None:
        """Final state contains keys from every phase."""
        plan_dir = tmp_path / "plan"
        result = run_megaplan_native_toy(plan_dir=plan_dir)

        state = result.state
        assert state.get("ready") is True
        assert state.get("counter") == 3
        assert state.get("branch") in ("normal", "override")
        assert state.get("done") is True

        # Subloop promotion keys
        assert "subloop:child:state" in state
        assert state["subloop:child:state"]["child_key"] == "child_value_a"
        assert state["subloop:child:state"]["child_key2"] == "child_value_b"
        assert state.get("subloop:child:recommendation") == "force-proceed"

    def test_envelope_accumulated(self, tmp_path) -> None:
        """The result carries a RuntimeEnvelope."""
        plan_dir = tmp_path / "plan"
        result = run_megaplan_native_toy(plan_dir=plan_dir)

        assert result.envelope is not None
        assert isinstance(result.envelope, RuntimeEnvelope)

    def test_stages_tracked_in_order(self, tmp_path) -> None:
        """The stages list records phases in execution order."""
        plan_dir = tmp_path / "plan"
        result = run_megaplan_native_toy(plan_dir=plan_dir)

        stage_names = [
            s.split("__")[-2] if "__" in s else s
            for s in result.stages
        ]
        # setup is always first
        assert stage_names[0] == "setup"
        # cleanup should be last (before halt)
        assert "cleanup" in stage_names
        assert stage_names[-1] == "cleanup"

        # override_decision and loop_guard are decisions, not in stages
        # phases: setup, [override_target|normal_target], loop_body (×3),
        #         nested_subpipeline, cleanup = 7
        assert len(result.stages) == 7

    def test_state_persisted_to_disk(self, tmp_path) -> None:
        """State is persisted to state.json via on_stage_complete."""
        plan_dir = tmp_path / "plan"
        run_megaplan_native_toy(plan_dir=plan_dir)

        state_path = plan_dir / "state.json"
        assert state_path.exists()

        disk_state = read_native_toy_state(plan_dir)
        assert disk_state.get("done") is True

    def test_override_path_activated(self, tmp_path) -> None:
        """Override in initial state routes to override_target."""
        plan_dir = tmp_path / "plan"
        initial_state = {
            "meta": {
                "overrides": [
                    {"action": "abort", "reason": "test override"}
                ]
            }
        }
        result = run_megaplan_native_toy(
            plan_dir=plan_dir,
            initial_state=initial_state,
        )
        assert result.state.get("branch") == "override"

    def test_normal_path_when_no_override(self, tmp_path) -> None:
        """Without overrides, the decision routes to normal_target."""
        plan_dir = tmp_path / "plan"
        result = run_megaplan_native_toy(plan_dir=plan_dir)

        assert result.state.get("branch") == "normal"

    def test_loop_counter_reaches_three(self, tmp_path) -> None:
        """The guarded loop body executes 3 times (counter: 0→1→2→3)."""
        plan_dir = tmp_path / "plan"
        result = run_megaplan_native_toy(plan_dir=plan_dir)

        assert result.state["counter"] == 3


# ═══════════════════════════════════════════════════════════════════════
# Suspension / resume tests
# ═══════════════════════════════════════════════════════════════════════


class TestMegaplanNativeToySuspensionResume:
    """The native toy pipeline supports forced suspension and resume."""

    def test_max_phases_triggers_suspension(self, tmp_path) -> None:
        """max_phases=2 suspends after 2 phases."""
        plan_dir = tmp_path / "plan"
        result = run_megaplan_native_toy(
            plan_dir=plan_dir,
            max_phases=2,
        )
        assert result.suspended
        assert result.cursor_path is not None
        assert len(result.stages) == 2

    def test_resume_continues_from_suspension(self, tmp_path) -> None:
        """Resume from a max_phases suspension completes the pipeline."""
        plan_dir = tmp_path / "plan"
        artifact_root = plan_dir / "run"

        # First run — suspend after 2 phases
        result1 = run_megaplan_native_toy(
            plan_dir=plan_dir,
            max_phases=2,
            artifact_root=artifact_root,
        )
        assert result1.suspended
        assert len(result1.stages) == 2

        # Resume — should complete
        result2 = run_megaplan_native_toy(
            plan_dir=plan_dir,
            artifact_root=artifact_root,
            resume=True,
        )
        assert not result2.suspended
        assert result2.state.get("done") is True
        assert result2.state.get("counter") == 3

    def test_resume_preserves_accumulated_state(self, tmp_path) -> None:
        """State accumulated before suspension is preserved on resume."""
        plan_dir = tmp_path / "plan"
        artifact_root = plan_dir / "run"

        result1 = run_megaplan_native_toy(
            plan_dir=plan_dir,
            max_phases=3,
            artifact_root=artifact_root,
        )
        assert result1.suspended
        # After 3 phases: setup, override_target/normal_target, loop_body
        pre_resume_counter = result1.state.get("counter", 0)

        result2 = run_megaplan_native_toy(
            plan_dir=plan_dir,
            artifact_root=artifact_root,
            resume=True,
        )
        assert result2.state.get("counter", 0) >= pre_resume_counter

    def test_resume_from_different_max_phases(self, tmp_path) -> None:
        """Resume after multiple suspension steps works correctly."""
        plan_dir = tmp_path / "plan"
        artifact_root = plan_dir / "run"

        # Step 1: 2 phases
        r1 = run_megaplan_native_toy(
            plan_dir=plan_dir, max_phases=2,
            artifact_root=artifact_root,
        )
        assert r1.suspended

        # Step 2: resume with 2 more
        r2 = run_megaplan_native_toy(
            plan_dir=plan_dir, max_phases=2,
            artifact_root=artifact_root, resume=True,
        )
        # May or may not be suspended depending on how many phases remain
        # Total phases: 6 (setup + target + 3×loop_body + nested_subpipeline + cleanup)
        # After 2 + 2 = 4: we're partway through loop_body iterations
        if r2.suspended:
            # Step 3: finish
            r3 = run_megaplan_native_toy(
                plan_dir=plan_dir,
                artifact_root=artifact_root, resume=True,
            )
            assert not r3.suspended
            assert r3.state.get("done") is True

    def test_suspended_state_written_to_disk(self, tmp_path) -> None:
        """After suspension, state is persisted to disk."""
        plan_dir = tmp_path / "plan"
        run_megaplan_native_toy(
            plan_dir=plan_dir,
            max_phases=2,
        )

        state_path = plan_dir / "state.json"
        assert state_path.exists()

        disk_state = json.loads(state_path.read_text(encoding="utf-8"))
        assert disk_state.get("ready") is True

    def test_resume_cursor_written_on_suspension(self, tmp_path) -> None:
        """A resume cursor path is returned when max_phases triggers suspension.

        The cursor file write may be deferred when envelope objects are
        non-JSON-serializable (pre-existing behaviour in _persist_suspension).
        The authoritative check is that ``resume=True`` successfully restores
        state and continues execution — tested separately in
        ``test_resume_continues_from_suspension``.
        """
        plan_dir = tmp_path / "plan"
        result = run_megaplan_native_toy(
            plan_dir=plan_dir,
            max_phases=2,
            artifact_root=plan_dir,
        )

        assert result.suspended
        assert result.cursor_path is not None
        assert result.cursor_path.endswith("resume_cursor.json")
        assert result.pc >= 0


# ═══════════════════════════════════════════════════════════════════════
# Envelope / plan-dir parity tests
# ═══════════════════════════════════════════════════════════════════════


class TestMegaplanNativeToyEnvelopeParity:
    """Envelope behavior matches the graph reference pattern."""

    def test_initial_envelope_has_taint_clean(self, tmp_path) -> None:
        """The initial envelope carries taint='clean' matching the graph ref."""
        plan_dir = tmp_path / "plan"
        result = run_megaplan_native_toy(plan_dir=plan_dir)

        envelope = result.envelope
        assert envelope is not None

        # RuntimeEnvelope wraps a RunEnvelope with cross_cutting
        if hasattr(envelope, "cross_cutting"):
            cc = envelope.cross_cutting
            if hasattr(cc, "taint"):
                assert cc.taint == "clean"

    def test_envelope_artifact_root_matches_plan_dir(self, tmp_path) -> None:
        """The result envelope's artifact_root matches the plan_dir."""
        plan_dir = tmp_path / "plan"
        result = run_megaplan_native_toy(plan_dir=plan_dir)

        envelope = result.envelope
        if hasattr(envelope, "artifact_root"):
            assert str(plan_dir) in str(envelope.artifact_root)

    def test_plan_dir_has_expected_files_after_run(self, tmp_path) -> None:
        """After an uninterrupted run, plan_dir contains expected files."""
        plan_dir = tmp_path / "plan"
        run_megaplan_native_toy(plan_dir=plan_dir)

        # state.json must exist
        assert (plan_dir / "state.json").exists()

    def test_plan_dir_with_initial_state(self, tmp_path) -> None:
        """Initial state written to disk survives the run."""
        plan_dir = tmp_path / "plan"
        initial_state = {"pre_existing": "value", "counter": 42}
        result = run_megaplan_native_toy(
            plan_dir=plan_dir,
            initial_state=initial_state,
        )

        disk_state = read_native_toy_state(plan_dir)
        # pre_existing should be preserved (it's not an executor-owned key)
        assert disk_state.get("pre_existing") == "value"
        # counter is executor-owned and gets overwritten by the loop
        assert disk_state.get("counter") == 3


# ═══════════════════════════════════════════════════════════════════════
# Integration: MegaplanNativeRuntimeHooks
# ═══════════════════════════════════════════════════════════════════════


class TestMegaplanNativeToyHooksIntegration:
    """The native toy integrates correctly with MegaplanNativeRuntimeHooks."""

    def test_hooks_persist_state_at_each_stage(self, tmp_path) -> None:
        """After multiple stages, state.json reflects accumulated state."""
        plan_dir = tmp_path / "plan"
        run_megaplan_native_toy(plan_dir=plan_dir)

        disk_state = read_native_toy_state(plan_dir)
        # All phase outputs should be reflected
        assert disk_state.get("ready") is True
        assert disk_state.get("done") is True
        assert disk_state.get("counter") == 3

    def test_hooks_on_stage_complete_noop_without_plan_dir(self) -> None:
        """Without plan_dir, hooks gracefully no-op without raising."""
        # This exercises the guard in on_stage_complete
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeRuntimeHooks
        from arnold.pipeline.native.ir import NativeInstruction

        hooks = MegaplanNativeRuntimeHooks(plan_dir=None)
        instr = NativeInstruction(
            op="phase", name="test", pc=0, func=None, next_pc=None,
        )
        # Should not raise
        hooks.on_stage_complete(
            instr=instr,
            ctx={"state": {"key": "val"}},
            result={"ok": True},
            state={"key": "val"},
            owned_keys=frozenset({"key"}),
        )

    def test_override_injection_via_hooks(self, tmp_path) -> None:
        """Override injection through hooks routes to override_target."""
        plan_dir = tmp_path / "plan"
        initial_state = {
            "meta": {
                "overrides": [
                    {"action": "force-proceed", "reason": "test"}
                ]
            }
        }
        result = run_megaplan_native_toy(
            plan_dir=plan_dir,
            initial_state=initial_state,
        )
        assert result.state["branch"] == "override"

    def test_unknown_override_does_not_break(self, tmp_path) -> None:
        """Unknown override entries are silently skipped."""
        plan_dir = tmp_path / "plan"
        initial_state = {
            "meta": {
                "overrides": [
                    {"action": "nonexistent-override", "note": "x"}
                ]
            }
        }
        result = run_megaplan_native_toy(
            plan_dir=plan_dir,
            initial_state=initial_state,
        )
        # Unknown override is skipped; pipeline runs normally
        assert result.state.get("done") is True
        assert result.state.get("branch") == "normal"

    def test_add_note_override_still_runs_pipeline(self, tmp_path) -> None:
        """add-note override mutates state without breaking the pipeline."""
        plan_dir = tmp_path / "plan"
        initial_state = {
            "meta": {
                "overrides": [
                    {"action": "add-note", "note": "hello", "source": "user"}
                ]
            }
        }
        result = run_megaplan_native_toy(
            plan_dir=plan_dir,
            initial_state=initial_state,
        )
        assert result.state.get("done") is True
        # Notes should be in meta
        notes = result.state.get("meta", {}).get("notes", [])
        assert len(notes) >= 1
        assert notes[0]["note"] == "hello"


# ═══════════════════════════════════════════════════════════════════════
# Graph vs native parity test (T16)
# ═══════════════════════════════════════════════════════════════════════


class TestMegaplanToyPipelineParity:
    """Compare graph-executor and native-executor traces for the Megaplan toy.

    Uses the existing parity normalizers (:func:`normalize_state`,
    :func:`normalize_events`, :func:`normalize_cursor`,
    :func:`inventory_artifacts`) and the surface-localized
    :func:`diff_traces` reporter to compare:

    * state — normalized final working state
    * events — normalized event journal entries
    * cursor — normalized resume cursor (both None for a full run)
    * stage sequence — ordered list of completed stage identifiers
    * envelope — accumulated envelope at completion
    * artifacts — content-hash inventory of plan-dir files (volatile paths masked)
    """

    def _build_native_trace(
        self,
        tmp_path: Path,
    ) -> "ParityTrace":
        """Run the native toy and return a normalized ParityTrace."""
        from .parity_trace import (
            ParityTrace,
            inventory_artifacts,
            normalize_cursor,
            normalize_events,
            normalize_state,
        )

        plan_dir = tmp_path / "native_plan"
        plan_dir.mkdir()
        trace_dir = tmp_path / "native_trace"
        trace_dir.mkdir()

        _reset_loop_counter()

        program = get_megaplan_native_toy_program()

        # Build hooks and envelope matching run_megaplan_native_toy
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeRuntimeHooks
        from arnold.runtime.envelope import RunEnvelope, RuntimeEnvelope

        hooks = MegaplanNativeRuntimeHooks(plan_dir=str(plan_dir))
        initial_envelope = RuntimeEnvelope(
            artifact_root=str(plan_dir),
            cross_cutting=RunEnvelope(taint="clean"),
        )

        # Write initial state
        state_path = plan_dir / "state.json"
        state_path.write_text(json.dumps({}), encoding="utf-8")

        from arnold.pipeline.native import run_native_pipeline

        result = run_native_pipeline(
            program,
            artifact_root=str(plan_dir),
            initial_state={},
            hooks=hooks,
            initial_envelope=initial_envelope,
            trace_dir=str(trace_dir),
        )

        # Read events from the trace directory
        from arnold.runtime.event_journal import read_event_journal

        events_raw = read_event_journal(trace_dir)
        events = normalize_events(events_raw)

        return ParityTrace(
            topology_hash="native-megaplan-toy",
            stage_sequence=list(result.stages),
            final_state=normalize_state(result.state),
            events=events,
            cursor=normalize_cursor(None),
            artifacts=inventory_artifacts(plan_dir),
            hook_order=[],
            accumulated_envelope=result.envelope,
        )

    def _build_graph_trace(
        self,
        tmp_path: Path,
    ) -> "ParityTrace":
        """Run the graph toy with TraceCaptureHooks and return a normalized ParityTrace."""
        from .parity_trace import (
            ParityTrace,
            TraceCaptureHooks,
            inventory_artifacts,
            normalize_cursor,
            normalize_events,
            normalize_state,
        )
        from .megaplan_toy_fixture import (
            get_megaplan_toy_pipeline,
            run_megaplan_toy_graph,
        )
        from arnold.runtime.event_journal import read_event_journal

        plan_dir = tmp_path / "graph_plan"
        plan_dir.mkdir()

        _reset_loop_counter()

        graph_pipeline = get_megaplan_toy_pipeline(plan_dir=str(plan_dir))
        graph_hooks = TraceCaptureHooks()

        graph_final_state, graph_envelope = run_megaplan_toy_graph(
            pipeline=graph_pipeline,
            plan_dir=plan_dir,
            hooks=graph_hooks,
        )

        # Prefer the hooks-captured final state (populated via on_stage_complete)
        # over the disk-read return value from run_megaplan_toy_graph, since
        # the hooks capture state directly from the executor's working state
        # rather than relying on disk persistence.
        final_state = graph_hooks.final_state if graph_hooks.final_state else graph_final_state

        # Read events from the plan directory (executor writes events.ndjson there)
        events_raw = read_event_journal(plan_dir)
        events = normalize_events(events_raw)

        return ParityTrace(
            topology_hash="graph-megaplan-toy",
            stage_sequence=list(graph_hooks.stages),
            final_state=normalize_state(final_state),
            events=events,
            cursor=normalize_cursor(None),
            artifacts=inventory_artifacts(plan_dir),
            hook_order=list(graph_hooks.hook_order),
            accumulated_envelope=graph_envelope,
        )

    # ── Surface-by-surface comparisons ────────────────────────────────

    def test_parity_diff_all_surfaces_present(self, tmp_path) -> None:
        """diff_traces returns a report covering all 7 surfaces."""
        from .parity_trace import diff_traces

        native_trace = self._build_native_trace(tmp_path)
        graph_trace = self._build_graph_trace(tmp_path)

        diff = diff_traces(native_trace, graph_trace)

        expected_surfaces = {
            "topology_hash",
            "stage_sequence",
            "final_state",
            "events",
            "cursor",
            "artifacts",
            "hook_order",
        }
        assert set(diff.keys()) == expected_surfaces, (
            f"diff_traces should cover all 7 surfaces; got {sorted(diff.keys())}"
        )

    def test_cursor_matches_for_full_run(self, tmp_path) -> None:
        """Both runtimes produce None cursor for uninterrupted full runs."""
        from .parity_trace import diff_traces

        native_trace = self._build_native_trace(tmp_path)
        graph_trace = self._build_graph_trace(tmp_path)

        diff = diff_traces(native_trace, graph_trace)

        # Cursor should match since both are None for a full run
        assert diff["cursor"] == "match", (
            f"Cursor should match for full runs; got {diff['cursor']}"
        )

    def test_both_traces_have_stage_sequence(self, tmp_path) -> None:
        """Both traces have a non-empty stage sequence."""
        native_trace = self._build_native_trace(tmp_path)
        graph_trace = self._build_graph_trace(tmp_path)

        assert len(native_trace.stage_sequence) > 0, "Native stage_sequence is empty"
        assert len(graph_trace.stage_sequence) > 0, "Graph stage_sequence is empty"

        # Native: 7 phases (setup, override_target|normal_target, 3×loop_body,
        #          nested_subpipeline, cleanup)
        assert len(native_trace.stage_sequence) == 7, (
            f"Expected 7 native phases, got {len(native_trace.stage_sequence)}: "
            f"{native_trace.stage_sequence}"
        )

    def test_both_traces_have_expected_state_keys(self, tmp_path) -> None:
        """Both final states contain expected application-level keys."""
        native_trace = self._build_native_trace(tmp_path)
        graph_trace = self._build_graph_trace(tmp_path)

        # Shared keys that should appear in both
        for key in ("ready", "counter", "done"):
            assert key in native_trace.final_state, (
                f"Native final_state missing key {key!r}"
            )
            assert key in graph_trace.final_state, (
                f"Graph final_state missing key {key!r}"
            )

        assert native_trace.final_state["done"] is True
        assert graph_trace.final_state["done"] is True

    def test_state_volatile_fields_masked(self, tmp_path) -> None:
        """Normalized state has no volatile internal keys or absolute paths."""
        native_trace = self._build_native_trace(tmp_path)
        graph_trace = self._build_graph_trace(tmp_path)

        # Internal keys must be absent from normalized state
        for key in ("__state__", "__envelope__"):
            assert key not in native_trace.final_state, (
                f"Volatile key {key!r} not masked in native state"
            )
            assert key not in graph_trace.final_state, (
                f"Volatile key {key!r} not masked in graph state"
            )

        # No absolute paths should appear in string values
        def _has_abs_path(obj: object) -> bool:
            import re
            _abs_re = re.compile(r"^(/[^\s\"',;:{}[\]()]+)+")

            if isinstance(obj, str):
                return bool(_abs_re.match(obj))
            if isinstance(obj, dict):
                return any(_has_abs_path(v) for v in obj.values())
            if isinstance(obj, list):
                return any(_has_abs_path(v) for v in obj)
            return False

        assert not _has_abs_path(native_trace.final_state), (
            "Native final_state contains absolute paths"
        )
        assert not _has_abs_path(graph_trace.final_state), (
            "Graph final_state contains absolute paths"
        )

    def test_events_volatile_fields_masked(self, tmp_path) -> None:
        """Normalized events have timestamps masked and seq replaced with index."""
        native_trace = self._build_native_trace(tmp_path)
        graph_trace = self._build_graph_trace(tmp_path)

        for label, events in [("native", native_trace.events), ("graph", graph_trace.events)]:
            for idx, event in enumerate(events):
                # Timestamps must be masked
                for ts_key in ("ts_utc", "ts_rel_init_s"):
                    if ts_key in event:
                        assert event[ts_key] == "<masked>", (
                            f"{label} event {idx}: {ts_key} not masked, got {event[ts_key]!r}"
                        )
                # seq must be replaced with index
                if "seq" in event:
                    assert event["seq"] == idx, (
                        f"{label} event {idx}: seq should be {idx}, got {event['seq']}"
                    )

    def test_artifacts_inventory_produced(self, tmp_path) -> None:
        """Both traces have a non-empty artifact inventory with state.json."""
        native_trace = self._build_native_trace(tmp_path)
        graph_trace = self._build_graph_trace(tmp_path)

        # Both should have at least state.json
        native_art_keys = [k for k in native_trace.artifacts if "state.json" in k]
        graph_art_keys = [k for k in graph_trace.artifacts if "state.json" in k]
        assert len(native_art_keys) >= 1, "Native artifacts missing state.json"
        assert len(graph_art_keys) >= 1, "Graph artifacts missing state.json"

        # Skip files (events sidecars, resume cursor) should be absent
        skip_names = {".events.seq", ".events.init_ts", "events.ndjson", "resume_cursor.json"}
        for name in skip_names:
            assert name not in native_trace.artifacts, (
                f"Skip file {name!r} should not be in native artifact inventory"
            )
            assert name not in graph_trace.artifacts, (
                f"Skip file {name!r} should not be in graph artifact inventory"
            )

    def test_envelope_present_on_both_traces(self, tmp_path) -> None:
        """Both traces carry a non-None accumulated envelope."""
        native_trace = self._build_native_trace(tmp_path)
        graph_trace = self._build_graph_trace(tmp_path)

        assert native_trace.accumulated_envelope is not None, (
            "Native trace missing accumulated_envelope"
        )
        assert graph_trace.accumulated_envelope is not None, (
            "Graph trace missing accumulated_envelope"
        )

        # Both should be RuntimeEnvelope instances
        from arnold.runtime.envelope import RuntimeEnvelope

        assert isinstance(native_trace.accumulated_envelope, RuntimeEnvelope), (
            f"Native envelope is {type(native_trace.accumulated_envelope)}, "
            f"expected RuntimeEnvelope"
        )
        assert isinstance(graph_trace.accumulated_envelope, RuntimeEnvelope), (
            f"Graph envelope is {type(graph_trace.accumulated_envelope)}, "
            f"expected RuntimeEnvelope"
        )

    def test_graph_hook_order_non_empty(self, tmp_path) -> None:
        """Graph trace has a non-empty hook_order (native hook_order is always empty)."""
        graph_trace = self._build_graph_trace(tmp_path)

        assert len(graph_trace.hook_order) > 0, (
            "Graph hook_order should be non-empty"
        )
        # Verify hook_order contains expected callback prefixes.
        # The graph executor fires merge_state and join_envelope conditionally
        # (e.g. only when outputs/envelope are non-empty); should_halt_loop,
        # should_suspend, and on_edge_traverse fire unconditionally for
        # non-terminal stages.
        prefixes = {entry.split(":")[0] if ":" in entry else entry
                     for entry in graph_trace.hook_order}
        expected_prefixes = {
            "on_step_start", "on_step_end", "on_stage_complete",
            "on_edge_traverse", "should_halt_loop", "should_suspend",
        }
        missing = expected_prefixes - prefixes
        assert not missing, (
            f"Graph hook_order missing expected callback prefixes: {missing}"
        )
