"""Replay-consistency tests: uninterrupted vs interrupted/resumed native runs.

Verifies that running a pipeline to completion in one shot produces the
same final state, stage sequence, envelope, and normalized trace output
as running it with ``max_phases`` interruption followed by resume.

This validates the T8 resume-aware trace behaviour end-to-end: resumed
traced runs must seed their stage sequence from the restore cursor so
the final trace is indistinguishable from an uninterrupted run.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from arnold.pipeline.native import (
    NativeExecutionResult,
    NativeProgram,
    compile_pipeline,
    decision,
    phase,
    pipeline,
    run_native_pipeline,
    workflow,
)
from arnold.pipeline.native.checkpoint import read_native_cursor

# ── module-level fixture ──────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _enable_native_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARNOLD_NATIVE_RUNTIME", "1")


# ── helpers ───────────────────────────────────────────────────────────


def _canonical_json(obj: object) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _normalize_event_line(line: str) -> str:
    """Strip non-deterministic fields from an NDJSON event line."""
    obj = json.loads(line)
    for key in ("seq", "ts_utc", "ts_rel_init_s"):
        obj.pop(key, None)
    return _canonical_json(obj)


def _normalize_events_ndjson(text: str) -> str:
    lines = text.strip().split("\n")
    normalized = [_normalize_event_line(line) for line in lines if line.strip()]
    return "\n".join(normalized) + "\n" if normalized else ""


def _compare_trace_dirs(
    dir_a: Path,
    dir_b: Path,
    *,
    skip_artifacts: bool = True,
) -> list[str]:
    """Compare two trace directories and return a list of mismatch descriptions.

    Returns an empty list when the trace directories are equivalent after
    normalization.

    Note: events.ndjson is compared as a *superset* check — the resumed run's
    events must contain all events from the uninterrupted run.  The resumed run
    may have extra events (e.g. an intermediate checkpoint from the suspension),
    which is expected and not a mismatch.
    """
    mismatches: list[str] = []

    # stages.json — must be identical
    stages_a = json.loads((dir_a / "stages.json").read_text(encoding="utf-8"))
    stages_b = json.loads((dir_b / "stages.json").read_text(encoding="utf-8"))
    if stages_a != stages_b:
        mismatches.append(
            f"stages.json differs: {len(stages_a)} vs {len(stages_b)} entries"
        )

    # state.json — must be identical
    state_a = json.loads((dir_a / "state.json").read_text(encoding="utf-8"))
    state_b = json.loads((dir_b / "state.json").read_text(encoding="utf-8"))
    if state_a != state_b:
        mismatches.append("state.json differs")

    # checkpoint.json — stage_sequence should match
    cp_a = json.loads((dir_a / "checkpoint.json").read_text(encoding="utf-8"))
    cp_b = json.loads((dir_b / "checkpoint.json").read_text(encoding="utf-8"))
    if cp_a.get("stage_sequence") != cp_b.get("stage_sequence"):
        mismatches.append("checkpoint.json stage_sequence differs")
    if cp_a.get("final") != cp_b.get("final"):
        mismatches.append("checkpoint.json final flag differs")

    # events.ndjson — resumed run must be a superset of uninterrupted run.
    # Resumed runs may have extra events (intermediate checkpoints from the
    # suspension boundary), but must contain every event from the full run.
    events_a_lines = _normalize_events_ndjson(
        (dir_a / "events.ndjson").read_text(encoding="utf-8")
    ).strip().split("\n")
    events_b_lines = _normalize_events_ndjson(
        (dir_b / "events.ndjson").read_text(encoding="utf-8")
    ).strip().split("\n")

    a_set = set(events_a_lines)
    b_set = set(events_b_lines)
    missing_from_b = a_set - b_set
    if missing_from_b:
        mismatches.append(
            f"events.ndjson: {len(missing_from_b)} event(s) missing from "
            f"resumed trace (expected all uninterrupted events to be present)"
        )

    # artifacts.json — skip by default (content hashes differ across tmp_paths)
    if not skip_artifacts:
        art_a = json.loads((dir_a / "artifacts.json").read_text(encoding="utf-8"))
        art_b = json.loads((dir_b / "artifacts.json").read_text(encoding="utf-8"))
        if art_a != art_b:
            mismatches.append("artifacts.json differs")

    return mismatches


# ── replay-consistency tests ──────────────────────────────────────────


class TestReplayConsistency:
    """Equivalent results between uninterrupted and interrupted/resumed native runs."""

    # ── state + stage parity ────────────────────────────────────────

    def test_state_and_stage_parity_simple_phases(self, tmp_path: Path) -> None:
        """Three-phase linear pipeline: full run == interrupted+resumed."""

        @phase
        def step_a(ctx: dict) -> dict:
            return {"a": 1}

        @phase
        def step_b(ctx: dict) -> dict:
            return {"b": 2}

        @phase
        def step_c(ctx: dict) -> dict:
            return {"c": 3}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            s = yield step_a(ctx)
            s = yield step_b(ctx)
            s = yield step_c(ctx)
            return s

        prog = compile_pipeline(my_pipe)

        # ── uninterrupted run ──
        full = run_native_pipeline(prog)
        assert not full.suspended
        assert full.state == {"a": 1, "b": 2, "c": 3}

        # ── interrupted + resumed run ──
        artifact_root = tmp_path / "resume_test"
        artifact_root.mkdir()
        run_native_pipeline(prog, artifact_root=artifact_root, max_phases=1)
        resumed = run_native_pipeline(prog, artifact_root=artifact_root, resume=True)
        assert not resumed.suspended

        # ── parity assertions ──
        assert resumed.state == full.state
        assert len(resumed.stages) == len(full.stages)
        assert resumed.pc == full.pc
        assert resumed.suspended == full.suspended

    def test_state_and_stage_parity_with_decisions(self, tmp_path: Path) -> None:
        """Pipeline with decisions: full run == interrupted+resumed."""

        @phase
        def setup(ctx: dict) -> dict:
            return {"ready": True, "count": 0}

        @phase
        def increment(ctx: dict) -> dict:
            c = ctx["state"].get("count", 0) + 1
            return {"count": c}

        @phase
        def finalize(ctx: dict) -> dict:
            return {"done": True}

        @decision(vocabulary={"again", "done"})
        def should_continue(ctx: dict) -> str:
            return "again" if ctx["state"].get("count", 0) < 2 else "done"

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            s = yield setup(ctx)
            while should_continue(ctx) == "again":
                s = yield increment(ctx)
            s = yield finalize(ctx)
            return s

        prog = compile_pipeline(my_pipe)

        # ── uninterrupted run ──
        full = run_native_pipeline(prog)
        assert not full.suspended
        assert full.state["done"] is True
        assert full.state["count"] == 2

        # ── interrupted + resumed run ──
        artifact_root = tmp_path / "resume_test"
        artifact_root.mkdir()
        run_native_pipeline(prog, artifact_root=artifact_root, max_phases=2)
        resumed = run_native_pipeline(prog, artifact_root=artifact_root, resume=True)
        assert not resumed.suspended

        # ── parity assertions ──
        assert resumed.state == full.state
        assert len(resumed.stages) == len(full.stages)
        assert resumed.pc == full.pc

    def test_state_and_stage_parity_with_subpipeline(self, tmp_path: Path) -> None:
        """Pipeline with a subpipeline: full run == interrupted+resumed."""

        @phase
        def child_phase(ctx: dict) -> dict:
            current = ctx["state"].get("nested", 0)
            return {"nested": current + 10}

        @workflow(name="child")
        def child(ctx: dict) -> dict:
            s = yield child_phase(ctx)
            return s

        @phase
        def parent_phase(ctx: dict) -> dict:
            return {"outer": ctx["state"]["nested"] * 2}

        @pipeline
        def parent(ctx: dict) -> dict:
            s = yield child(ctx)
            s = yield parent_phase(ctx)
            return s

        prog = compile_pipeline(parent)

        # ── uninterrupted run ──
        full = run_native_pipeline(prog)
        assert not full.suspended
        assert full.state == {"nested": 10, "outer": 20}

        # ── interrupted + resumed run ──
        artifact_root = tmp_path / "resume_test"
        artifact_root.mkdir()
        run_native_pipeline(prog, artifact_root=artifact_root, max_phases=1)
        resumed = run_native_pipeline(prog, artifact_root=artifact_root, resume=True)
        assert not resumed.suspended

        # ── parity assertions ──
        assert resumed.state == full.state
        assert len(resumed.stages) == len(full.stages)
        assert resumed.pc == full.pc

    # ── envelope parity ─────────────────────────────────────────────

    def test_envelope_parity(self, tmp_path: Path) -> None:
        """Envelope-aware phases: full run envelope == interrupted+resumed envelope."""

        @phase
        def step_a(ctx: dict) -> dict:
            return {"a": 1, "envelope": {"seq": [1]}}

        @phase
        def step_b(ctx: dict) -> dict:
            return {"b": 2, "envelope": {"seq": [2]}}

        @phase
        def step_c(ctx: dict) -> dict:
            return {"c": 3, "envelope": {"seq": [3]}}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            s = yield step_a(ctx)
            s = yield step_b(ctx)
            s = yield step_c(ctx)
            return s

        prog = compile_pipeline(my_pipe)

        # ── uninterrupted run ──
        full = run_native_pipeline(prog)
        assert not full.suspended

        # ── interrupted + resumed run ──
        artifact_root = tmp_path / "resume_test"
        artifact_root.mkdir()
        run_native_pipeline(prog, artifact_root=artifact_root, max_phases=1)
        resumed = run_native_pipeline(prog, artifact_root=artifact_root, resume=True)
        assert not resumed.suspended

        # ── envelope parity ──
        # Both runs accumulate envelopes across the same steps
        assert resumed.envelope == full.envelope

    # ── trace directory parity ──────────────────────────────────────

    def test_trace_directory_parity(self, tmp_path: Path) -> None:
        """Uninterrupted trace dir == interrupted+resumed trace dir after normalization."""

        @phase
        def step_a(ctx: dict) -> dict:
            return {"a": 1}

        @phase
        def step_b(ctx: dict) -> dict:
            return {"b": 2}

        @phase
        def step_c(ctx: dict) -> dict:
            return {"c": 3}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            s = yield step_a(ctx)
            s = yield step_b(ctx)
            s = yield step_c(ctx)
            return s

        prog = compile_pipeline(my_pipe)

        # ── uninterrupted run with trace ──
        full_artifact = tmp_path / "full_artifacts"
        full_trace = tmp_path / "full_trace"
        full_result = run_native_pipeline(
            prog,
            artifact_root=full_artifact,
            trace_dir=full_trace,
        )
        assert not full_result.suspended

        # ── interrupted + resumed run with trace ──
        resume_artifact = tmp_path / "resume_artifacts"
        resume_trace = tmp_path / "resume_trace"
        # Interrupt after 1 phase
        first = run_native_pipeline(
            prog,
            artifact_root=resume_artifact,
            max_phases=1,
            trace_dir=resume_trace,
        )
        assert first.suspended
        # Resume to completion (same trace_dir)
        resumed_result = run_native_pipeline(
            prog,
            artifact_root=resume_artifact,
            resume=True,
            trace_dir=resume_trace,
        )
        assert not resumed_result.suspended

        # ── state parity across trace dirs ──
        full_state = json.loads(
            (full_trace / "state.json").read_text(encoding="utf-8")
        )
        resumed_state = json.loads(
            (resume_trace / "state.json").read_text(encoding="utf-8")
        )
        assert resumed_state == full_state

        # ── stage sequence parity ──
        full_stages = json.loads(
            (full_trace / "stages.json").read_text(encoding="utf-8")
        )
        resumed_stages = json.loads(
            (resume_trace / "stages.json").read_text(encoding="utf-8")
        )
        # Both should use short trace form: ["step_a__pc0", "step_b__pc1", "step_c__pc2"]
        assert resumed_stages == full_stages
        assert len(resumed_stages) == 3

        # ── full trace directory comparison ──
        mismatches = _compare_trace_dirs(full_trace, resume_trace)
        assert not mismatches, "trace directories differ:\n" + "\n".join(mismatches)

    def test_trace_directory_parity_with_decisions(self, tmp_path: Path) -> None:
        """Trace parity holds when the pipeline contains decision instructions."""

        @phase
        def init(ctx: dict) -> dict:
            return {"count": 0}

        @phase
        def body(ctx: dict) -> dict:
            c = ctx["state"].get("count", 0) + 1
            return {"count": c}

        @phase
        def finish(ctx: dict) -> dict:
            return {"done": True}

        @decision(vocabulary={"again", "done"})
        def guard(ctx: dict) -> str:
            return "again" if ctx["state"].get("count", 0) < 2 else "done"

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            s = yield init(ctx)
            while guard(ctx) == "again":
                s = yield body(ctx)
            s = yield finish(ctx)
            return s

        prog = compile_pipeline(my_pipe)

        # ── uninterrupted run with trace ──
        full_trace = tmp_path / "full_trace"
        full_result = run_native_pipeline(
            prog,
            artifact_root=tmp_path / "full_artifacts",
            trace_dir=full_trace,
        )
        assert not full_result.suspended
        assert full_result.state["done"] is True

        # ── interrupted + resumed run with trace ──
        resume_trace = tmp_path / "resume_trace"
        resume_artifact = tmp_path / "resume_artifacts"
        first = run_native_pipeline(
            prog,
            artifact_root=resume_artifact,
            max_phases=1,
            trace_dir=resume_trace,
        )
        assert first.suspended
        resumed_result = run_native_pipeline(
            prog,
            artifact_root=resume_artifact,
            resume=True,
            trace_dir=resume_trace,
        )
        assert not resumed_result.suspended

        # ── state parity ──
        assert resumed_result.state == full_result.state

        # ── stage sequence parity ──
        full_stages = json.loads(
            (full_trace / "stages.json").read_text(encoding="utf-8")
        )
        resumed_stages = json.loads(
            (resume_trace / "stages.json").read_text(encoding="utf-8")
        )
        assert resumed_stages == full_stages

    def test_trace_directory_parity_multiple_suspensions(self, tmp_path: Path) -> None:
        """Multiple suspend/resume cycles still produce equivalent trace output."""

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

        # ── uninterrupted run ──
        full_trace = tmp_path / "full_trace"
        full_result = run_native_pipeline(
            prog,
            artifact_root=tmp_path / "full_artifacts",
            trace_dir=full_trace,
        )
        assert not full_result.suspended

        # ── interrupted + resumed (×3 suspensions) run ──
        resume_trace = tmp_path / "resume_trace"
        resume_artifact = tmp_path / "resume_artifacts"

        # Suspend after phase a
        r1 = run_native_pipeline(
            prog, artifact_root=resume_artifact, max_phases=1, trace_dir=resume_trace
        )
        assert r1.suspended
        # Resume, suspend after phase b
        r2 = run_native_pipeline(
            prog, artifact_root=resume_artifact, max_phases=1, resume=True, trace_dir=resume_trace
        )
        assert r2.suspended
        # Resume, suspend after phase c
        r3 = run_native_pipeline(
            prog, artifact_root=resume_artifact, max_phases=1, resume=True, trace_dir=resume_trace
        )
        assert r3.suspended
        # Resume to completion
        resumed_result = run_native_pipeline(
            prog, artifact_root=resume_artifact, resume=True, trace_dir=resume_trace
        )
        assert not resumed_result.suspended

        # ── state parity ──
        assert resumed_result.state == full_result.state
        assert resumed_result.stages == full_result.stages

        # ── stage sequence parity ──
        full_stages = json.loads(
            (full_trace / "stages.json").read_text(encoding="utf-8")
        )
        resumed_stages = json.loads(
            (resume_trace / "stages.json").read_text(encoding="utf-8")
        )
        assert resumed_stages == full_stages
        assert len(resumed_stages) == 4

    def test_replay_cursor_persistence(self, tmp_path: Path) -> None:
        """Cursor persists correctly across suspension; state carries through resume."""

        @phase
        def step_a(ctx: dict) -> dict:
            return {"a": 1}

        @phase
        def step_b(ctx: dict) -> dict:
            return {"b": 2}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            s = yield step_a(ctx)
            s = yield step_b(ctx)
            return s

        prog = compile_pipeline(my_pipe)
        artifact_root = tmp_path / "artifacts"

        # Suspend after 1 phase
        r1 = run_native_pipeline(prog, artifact_root=artifact_root, max_phases=1)
        assert r1.suspended
        cursor = read_native_cursor(artifact_root)
        assert cursor is not None
        assert cursor["native"]["pc"] == r1.pc
        assert len(cursor["stages"]) == 1
        # Suspension cursor carries the working state
        assert cursor["frames"].get("__state__") is not None

        # Resume to completion — state carries through
        r2 = run_native_pipeline(prog, artifact_root=artifact_root, resume=True)
        assert not r2.suspended
        assert r2.state == {"a": 1, "b": 2}
        # The runtime stages accumulate across both runs
        assert len(r2.stages) == 2

    def test_initial_state_preserved_on_resume(self, tmp_path: Path) -> None:
        """Initial state keys survive through suspension and resume."""

        @phase
        def step_a(ctx: dict) -> dict:
            return {"a": ctx["state"].get("base", 0) + 10}

        @phase
        def step_b(ctx: dict) -> dict:
            return {"b": ctx["state"]["a"] * 2}

        @pipeline
        def my_pipe(ctx: dict) -> dict:
            s = yield step_a(ctx)
            s = yield step_b(ctx)
            return s

        prog = compile_pipeline(my_pipe)

        # Full run with initial state
        full = run_native_pipeline(prog, initial_state={"base": 5})
        assert full.state == {"base": 5, "a": 15, "b": 30}

        # Interrupted + resumed with initial state
        artifact_root = tmp_path / "resume_test"
        artifact_root.mkdir()
        run_native_pipeline(
            prog, artifact_root=artifact_root, max_phases=1, initial_state={"base": 5}
        )
        resumed = run_native_pipeline(
            prog, artifact_root=artifact_root, resume=True, initial_state={"base": 5}
        )

        assert resumed.state == full.state

    def test_uninterrupted_and_resumed_nested_loop_parity(self, tmp_path: Path) -> None:
        """Parent loop plus child loop replay to the same nested path state."""
        counters = {"outer": 0, "inner": 0}

        @phase
        def body(ctx: dict) -> dict:
            counters["inner"] += 1
            return {
                "outer": counters["outer"],
                "inner": counters["inner"],
                "paths": [*ctx["state"].get("paths", []), ctx["run_path"]],
            }

        @decision(name="inner_loop", vocabulary={"again", "done"})
        def inner_guard(ctx: dict) -> str:
            return "again" if counters["inner"] < counters["outer"] * 2 else "done"

        @decision(name="outer_loop", vocabulary={"again", "done"})
        def outer_guard(ctx: dict) -> str:
            return "again" if counters["outer"] < 2 else "done"

        @phase
        def bump_outer(ctx: dict) -> dict:
            counters["outer"] += 1
            return {"outer": counters["outer"]}

        @workflow(name="child_loop")
        def child(ctx: dict) -> dict:
            state: dict = {}
            while inner_guard(ctx) == "again":
                state = yield body(ctx)
            return state

        @pipeline
        def nested(ctx: dict) -> dict:
            state: dict = {}
            while outer_guard(ctx) == "again":
                state = yield bump_outer(ctx)
                state = yield child(ctx, id="child_loop")
            return state

        prog = compile_pipeline(nested)
        full = run_native_pipeline(prog, artifact_root=tmp_path / "full")
        assert full.suspended is False

        counters.update({"outer": 0, "inner": 0})
        resume_root = tmp_path / "resumed"
        first = run_native_pipeline(prog, artifact_root=resume_root, max_phases=1)
        assert first.suspended is True
        resumed = run_native_pipeline(prog, artifact_root=resume_root, resume=True)

        assert resumed.suspended is False
        assert resumed.state == full.state
        assert resumed.stages == full.stages
        assert resumed.state["paths"] == [
            "root/outer_loop[1]/child_loop/inner_loop[1]",
            "root/outer_loop[1]/child_loop/inner_loop[2]",
            "root/outer_loop[2]/child_loop/inner_loop[1]",
            "root/outer_loop[2]/child_loop/inner_loop[2]",
        ]
