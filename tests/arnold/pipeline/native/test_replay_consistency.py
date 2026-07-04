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
from arnold.pipeline.native.audit import AuditHooks
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


# ── depth-2+ replay consistency ────────────────────────────────────────


class TestDepth2PlusReplayConsistency:
    """Interrupted/resumed depth-2+ child execution with audit and path stability."""

    # ── helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _read_audit_ndjson(audit_dir: Path) -> list[dict[str, Any]]:
        audit_file = audit_dir / "audit.ndjson"
        if not audit_file.exists():
            return []
        records: list[dict[str, Any]] = []
        for line in audit_file.read_text(encoding="utf-8").strip().splitlines():
            if line.strip():
                records.append(json.loads(line))
        return records

    @staticmethod
    def _step_audit_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [r for r in records if "attempt_id" in r]

    # ── depth-2 state + stage parity ───────────────────────────────────

    def test_depth2_nested_workflow_state_and_stage_parity(
        self, tmp_path: Path
    ) -> None:
        """Pipeline→child→grandchild: full run == interrupted+resumed for state, stages, envelope.

        Subpipeline phases (leaf, middle) run atomically within the child workflow call
        and do NOT appear in the parent stages list; only top-level phases do.
        State propagates through declared ``outputs`` schemas on workflows.
        """

        @phase
        def leaf(ctx: dict) -> dict:
            return {"leaf": "done", "run_path": ctx["run_path"]}

        @workflow(name="grandchild", outputs={"type": "object", "required": ["leaf", "run_path"]})
        def grandchild(ctx: dict) -> dict:
            state = yield leaf(ctx)
            return state

        @phase
        def middle(ctx: dict) -> dict:
            return {"middle": "ok", "child_run_path": ctx["run_path"]}

        @workflow(
            name="child",
            outputs={"type": "object", "required": ["leaf", "run_path", "middle", "child_run_path"]},
        )
        def child(ctx: dict) -> dict:
            state = yield grandchild(ctx, id="grand")
            state = yield middle(ctx)
            return state

        @phase
        def root_phase(ctx: dict) -> dict:
            return {"root": "done", "root_run_path": ctx["run_path"]}

        @pipeline
        def root(ctx: dict) -> dict:
            state = yield child(ctx, id="child_call")
            state = yield root_phase(ctx)
            return state

        prog = compile_pipeline(root)

        # ── uninterrupted run ──
        full = run_native_pipeline(prog)
        assert not full.suspended
        assert full.state["leaf"] == "done"
        assert full.state["middle"] == "ok"
        assert full.state["root"] == "done"

        # ── interrupted + resumed run ──
        # max_phases limits top-level phases; the subpipeline runs atomically
        artifact_root = tmp_path / "resume_test"
        artifact_root.mkdir()
        first = run_native_pipeline(prog, artifact_root=artifact_root, max_phases=1)
        assert first.suspended
        # Since the subpipeline runs atomically before the top-level phase is counted,
        # the intermediate state carries all subpipeline outputs
        assert first.state.get("leaf") == "done"
        assert first.state.get("middle") == "ok"
        assert first.state.get("root") == "done"

        resumed = run_native_pipeline(prog, artifact_root=artifact_root, resume=True)
        assert not resumed.suspended

        # ── state parity ──
        assert resumed.state == full.state

        # ── stage sequence parity ──
        # Only the single top-level phase appears in parent stages
        assert len(resumed.stages) == len(full.stages)
        assert resumed.stages == full.stages
        assert len(resumed.stages) == 1  # root_phase only (subpipeline phases are internal)

        # ── envelope parity ──
        assert resumed.envelope == full.envelope

        # ── pc parity ──
        assert resumed.pc == full.pc
        assert resumed.suspended == full.suspended

    def test_depth2_multiple_toplevel_phases_parity(self, tmp_path: Path) -> None:
        """Depth-2 pipeline with multiple top-level phases converges through suspend/resume.

        Uses three top-level ``phase`` instructions so ``max_phases=1`` suspends
        after the first, leaving later phases unexecuted.  Subpipeline calls are NOT
        phases — only direct ``phase`` instructions count against ``max_phases``.
        """

        @phase
        def step_a(ctx: dict) -> dict:
            return {"a": 1}

        @phase
        def leaf(ctx: dict) -> dict:
            v = ctx["state"].get("counter", 0) + ctx["state"].get("a", 0)
            return {"counter": v, "leaf_done": True}

        @workflow(
            name="grandchild",
            inputs={"type": "object", "required": ["a"]},
            outputs={"type": "object", "required": ["counter", "leaf_done"]},
        )
        def grandchild(ctx: dict) -> dict:
            state = yield leaf(ctx)
            return state

        @phase
        def middle(ctx: dict) -> dict:
            c = ctx["state"].get("counter", 0) + 1
            return {"counter": c, "middle_done": True}

        @workflow(
            name="child",
            inputs={"type": "object", "required": ["a"]},
            outputs={"type": "object", "required": ["counter", "leaf_done", "middle_done"]},
        )
        def child(ctx: dict) -> dict:
            state = yield grandchild(ctx, id="grand")
            state = yield middle(ctx)
            return state

        @phase
        def step_c(ctx: dict) -> dict:
            return {"c": ctx["state"].get("counter", 0) * 10}

        @pipeline
        def root(ctx: dict) -> dict:
            state = yield step_a(ctx)
            state = yield child(ctx, id="child_call")
            state = yield step_c(ctx)
            return state

        prog = compile_pipeline(root)

        # Full run: step_a(=1) → child(subpipeline: leaf(→counter=1), middle(→counter=2)) → step_c(→c=20)
        full = run_native_pipeline(prog)
        assert not full.suspended
        assert full.state["a"] == 1
        assert full.state["counter"] == 2
        assert full.state["leaf_done"] is True
        assert full.state["middle_done"] is True
        assert full.state["c"] == 20

        # Suspend after 1 phase (step_a), child subpipeline not yet executed
        artifact_root = tmp_path / "resume_test"
        artifact_root.mkdir()
        r1 = run_native_pipeline(prog, artifact_root=artifact_root, max_phases=1)
        assert r1.suspended
        assert r1.state.get("a") == 1
        # Child subpipeline hasn't run yet
        assert "leaf_done" not in r1.state
        assert "counter" not in r1.state

        resumed = run_native_pipeline(prog, artifact_root=artifact_root, resume=True)
        assert not resumed.suspended

        assert resumed.state == full.state
        assert resumed.stages == full.stages
        assert resumed.pc == full.pc

    # ── audit side-effect record parity ────────────────────────────────

    def test_depth2_audit_side_effect_parity(self, tmp_path: Path) -> None:
        """Depth-2 interrupted+resumed produces equivalent committed audit records.

        Audit hooks capture all phases including subpipeline steps, producing
        stable step_path/run_path/parent_run_path across replay.
        """

        @phase
        def leaf(ctx: dict) -> dict:
            return {"leaf": 1}

        @workflow(name="grandchild", outputs={"type": "object", "required": ["leaf"]})
        def grandchild(ctx: dict) -> dict:
            state = yield leaf(ctx)
            return state

        @phase
        def middle(ctx: dict) -> dict:
            return {"middle": 2}

        @workflow(
            name="child",
            outputs={"type": "object", "required": ["leaf", "middle"]},
        )
        def child(ctx: dict) -> dict:
            state = yield grandchild(ctx, id="grand")
            state = yield middle(ctx)
            return state

        @phase
        def root_phase(ctx: dict) -> dict:
            return {"root": 3}

        @pipeline
        def root(ctx: dict) -> dict:
            state = yield child(ctx, id="child_call")
            state = yield root_phase(ctx)
            return state

        prog = compile_pipeline(root)

        # ── uninterrupted run with audit ──
        full_audit = tmp_path / "full_audit"
        full_hooks = AuditHooks(audit_dir=full_audit)
        full = run_native_pipeline(prog, hooks=full_hooks)
        assert not full.suspended

        full_records = self._read_audit_ndjson(full_audit)
        full_step_recs = self._step_audit_records(full_records)

        # ── interrupted + resumed run with audit ──
        resume_audit = tmp_path / "resume_audit"
        resume_hooks = AuditHooks(audit_dir=resume_audit)
        artifact_root = tmp_path / "resume_artifacts"

        first = run_native_pipeline(
            prog,
            artifact_root=artifact_root,
            max_phases=1,
            hooks=resume_hooks,
        )
        assert first.suspended

        resumed = run_native_pipeline(
            prog,
            artifact_root=artifact_root,
            resume=True,
            hooks=resume_hooks,
        )
        assert not resumed.suspended

        resumed_records = self._read_audit_ndjson(resume_audit)
        resumed_step_recs = self._step_audit_records(resumed_records)

        # ── audit record count parity ──
        # Both runs execute the same number of phases (leaf, middle, root_phase)
        assert len(resumed_step_recs) == len(full_step_recs)
        assert len(full_step_recs) >= 2  # at least leaf + root_phase

        # ── each record carries required skeleton fields ──
        for rec in resumed_step_recs:
            assert "attempt_id" in rec
            assert isinstance(rec["attempt_id"], str)
            assert len(rec["attempt_id"]) == 32
            assert "run_path" in rec
            assert isinstance(rec["run_path"], str)
            assert len(rec["run_path"]) > 0
            assert "parent_run_path" in rec
            assert "call_site_path" in rec
            assert isinstance(rec["step_path"], str)
            assert len(rec["step_path"]) > 0
            assert rec["status"] == "success"
            assert "started_at" in rec
            assert "ended_at" in rec

        # ── same step_paths appear in both audit trails ──
        full_paths = {r["step_path"] for r in full_step_recs}
        resumed_paths = {r["step_path"] for r in resumed_step_recs}
        assert full_paths == resumed_paths

        # ── all records share same run_id (within each run) ──
        full_run_ids = {r["run_id"] for r in full_step_recs}
        resumed_run_ids = {r["run_id"] for r in resumed_step_recs}
        assert len(full_run_ids) == 1
        assert len(resumed_run_ids) == 1

        # ── state parity still holds ──
        assert resumed.state == full.state
        assert resumed.stages == full.stages

    # ── nested path stability ──────────────────────────────────────────

    def test_depth2_nested_path_stability(self, tmp_path: Path) -> None:
        """Nested run_path/step_paths are stable through replay, not just coincidental.

        Uses ``ctx["run_path"]`` captured inside phases to prove that the tree-shaped
        path addressing is identical between uninterrupted and interrupted+resumed runs.
        """

        captured_paths: dict[str, list[str]] = {"full": [], "resumed": []}

        @phase
        def leaf(ctx: dict) -> dict:
            captured_paths["full"].append(ctx["run_path"])
            return {"leaf_path": ctx["run_path"]}

        @workflow(
            name="grandchild",
            outputs={"type": "object", "required": ["leaf_path"]},
        )
        def grandchild(ctx: dict) -> dict:
            state = yield leaf(ctx)
            return state

        @phase
        def middle(ctx: dict) -> dict:
            captured_paths["full"].append(ctx["run_path"])
            return {"middle_path": ctx["run_path"]}

        @workflow(
            name="child",
            outputs={"type": "object", "required": ["leaf_path", "middle_path"]},
        )
        def child(ctx: dict) -> dict:
            state = yield grandchild(ctx, id="grand")
            state = yield middle(ctx)
            return state

        @phase
        def root_phase(ctx: dict) -> dict:
            captured_paths["full"].append(ctx["run_path"])
            return {"root_path": ctx["run_path"]}

        @pipeline
        def root(ctx: dict) -> dict:
            state = yield child(ctx, id="child_call")
            state = yield root_phase(ctx)
            return state

        prog = compile_pipeline(root)

        # ── uninterrupted run (captures paths) ──
        full = run_native_pipeline(prog)
        assert not full.suspended

        # ── interrupted + resumed run (captures paths via separate pipeline) ──
        @phase
        def leaf_r(ctx: dict) -> dict:
            captured_paths["resumed"].append(ctx["run_path"])
            return {"leaf_path": ctx["run_path"]}

        @phase
        def middle_r(ctx: dict) -> dict:
            captured_paths["resumed"].append(ctx["run_path"])
            return {"middle_path": ctx["run_path"]}

        @phase
        def root_phase_r(ctx: dict) -> dict:
            captured_paths["resumed"].append(ctx["run_path"])
            return {"root_path": ctx["run_path"]}

        @workflow(
            name="grandchild_r",
            outputs={"type": "object", "required": ["leaf_path"]},
        )
        def grandchild_r(ctx: dict) -> dict:
            state = yield leaf_r(ctx)
            return state

        @workflow(
            name="child_r",
            outputs={"type": "object", "required": ["leaf_path", "middle_path"]},
        )
        def child_r(ctx: dict) -> dict:
            state = yield grandchild_r(ctx, id="grand")
            state = yield middle_r(ctx)
            return state

        @pipeline
        def root_r(ctx: dict) -> dict:
            state = yield child_r(ctx, id="child_call")
            state = yield root_phase_r(ctx)
            return state

        prog_r = compile_pipeline(root_r)

        artifact_root = tmp_path / "resume_paths"
        artifact_root.mkdir()
        first = run_native_pipeline(prog_r, artifact_root=artifact_root, max_phases=1)
        assert first.suspended

        resumed = run_native_pipeline(prog_r, artifact_root=artifact_root, resume=True)
        assert not resumed.suspended

        # ── nested path stability assertions ──
        # The run_paths captured during full and resumed runs must be identical
        assert captured_paths["full"] == captured_paths["resumed"], (
            f"run_paths diverge: full={captured_paths['full']} "
            f"vs resumed={captured_paths['resumed']}"
        )

        # ── explicit path shape assertions ──
        full_paths = captured_paths["full"]
        assert len(full_paths) == 3

        # leaf runs inside child → grandchild, so its run_path should be deeper
        leaf_path = full_paths[0]
        middle_path = full_paths[1]
        root_path = full_paths[2]

        # root phase runs at root level
        assert root_path == "root"

        # middle runs inside child, so its run_path contains child_call
        assert "child_call" in middle_path
        assert middle_path.startswith("root/")

        # leaf runs inside child→grandchild, so it's deeper than middle
        assert "grand" in leaf_path
        assert leaf_path.startswith(middle_path.rsplit("/", 1)[0])
        # leaf is strictly deeper than middle (more path segments)
        assert leaf_path.count("/") > middle_path.count("/")

        # ── state parity (ignore differently-named pipeline stage names) ──
        assert resumed.state == full.state

    def test_depth2_audit_path_correlation(self, tmp_path: Path) -> None:
        """Audit records for depth-2 runs carry correct parent_run_path and call_site_path.

        Verifies that committed side-effect records (audit) capture stable parent_lineage
        and call-site addressing, not just flat step-level coincidence.
        """

        @phase
        def leaf(ctx: dict) -> dict:
            return {"leaf": 1}

        @workflow(name="grandchild", outputs={"type": "object", "required": ["leaf"]})
        def grandchild(ctx: dict) -> dict:
            state = yield leaf(ctx)
            return state

        @phase
        def middle(ctx: dict) -> dict:
            return {"middle": 2}

        @workflow(
            name="child",
            outputs={"type": "object", "required": ["leaf", "middle"]},
        )
        def child(ctx: dict) -> dict:
            state = yield grandchild(ctx, id="grand")
            state = yield middle(ctx)
            return state

        @phase
        def root_phase(ctx: dict) -> dict:
            return {"root": 3}

        @pipeline
        def root(ctx: dict) -> dict:
            state = yield child(ctx, id="child_call")
            state = yield root_phase(ctx)
            return state

        prog = compile_pipeline(root)

        audit_dir = tmp_path / "audit"
        hooks = AuditHooks(audit_dir=audit_dir)
        result = run_native_pipeline(prog, hooks=hooks)
        assert not result.suspended

        records = self._read_audit_ndjson(audit_dir)
        step_recs = self._step_audit_records(records)
        # leaf, middle, root_phase
        assert len(step_recs) >= 2

        # Collect by step_path suffix for inspection
        by_name: dict[str, dict[str, Any]] = {}
        for rec in step_recs:
            name = rec["step_path"].rsplit("/", 1)[-1]
            by_name[name] = rec

        # root_phase runs at root level
        root_rec = by_name.get("root_phase", {})
        if root_rec:
            assert root_rec["run_path"] == "root", (
                f"root_phase run_path: {root_rec['run_path']}"
            )

        # middle: runs inside child_call
        middle_rec = by_name.get("middle", {})
        if middle_rec:
            assert "child_call" in middle_rec["run_path"], (
                f"middle run_path missing child_call: {middle_rec['run_path']}"
            )
            assert "parent_run_path" in middle_rec
            assert "call_site_path" in middle_rec

        # leaf: runs inside child_call→grand, deepest nesting
        leaf_rec = by_name.get("leaf", {})
        if leaf_rec:
            assert "grand" in leaf_rec["run_path"], (
                f"leaf run_path missing grand: {leaf_rec['run_path']}"
            )
            assert "child_call" in leaf_rec["run_path"], (
                f"leaf run_path missing child_call: {leaf_rec['run_path']}"
            )
            # parent_run_path should point to grandchild's run context
            assert leaf_rec.get("parent_run_path") is not None
            # call_site_path should include child_call and grand segments
            assert len(leaf_rec.get("call_site_path", [])) >= 1
