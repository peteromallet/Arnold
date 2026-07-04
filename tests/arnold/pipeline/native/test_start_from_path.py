from __future__ import annotations

import json
from pathlib import Path

import pytest

from arnold.pipeline import start_from_trace as pipeline_start_from_trace
from arnold.pipeline.native import (
    NativeProgram,
    compile_pipeline,
    phase,
    pipeline,
    run_native_pipeline,
    start_from_trace,
)


def _build_suspended_trace(tmp_path: Path) -> tuple[NativeProgram, Path, str]:
    @phase
    def seed(ctx: dict) -> dict:
        return {"seed": 41}

    @phase(
        inputs={
            "type": "object",
            "required": ["seed"],
            "properties": {"seed": {"type": "integer"}},
        }
    )
    def finish(ctx: dict) -> dict:
        value = ctx["state"]["seed"] + 1
        Path(ctx["artifact_root"], "answer.txt").write_text(str(value), encoding="utf-8")
        return {"answer": value}

    @pipeline(
        inputs={
            "type": "object",
            "properties": {"seed": {"type": "integer"}},
        }
    )
    def replayable(ctx: dict) -> dict:
        state = yield seed(ctx)
        state = yield finish(ctx)
        return state

    program = compile_pipeline(replayable)
    source_root = tmp_path / "source"
    trace_dir = source_root / "trace"
    result = run_native_pipeline(
        program,
        artifact_root=source_root,
        trace_dir=trace_dir,
        max_phases=1,
    )
    assert result.suspended is True
    checkpoint = json.loads(
        (trace_dir / "checkpoint.json").read_text(encoding="utf-8")
    )
    target_path = checkpoint["step_path"]
    assert isinstance(target_path, str)
    return program, trace_dir, target_path


def test_start_from_trace_is_reexported() -> None:
    assert pipeline_start_from_trace is start_from_trace


def test_start_from_trace_replays_into_fresh_artifact_root_without_mutating_source(
    tmp_path: Path,
) -> None:
    program, trace_dir, target_path = _build_suspended_trace(tmp_path)
    source_root = trace_dir.parent
    source_snapshot = {
        "resume_cursor": (source_root / "resume_cursor.json").read_text(encoding="utf-8"),
        "trace_state": (trace_dir / "state.json").read_text(encoding="utf-8"),
        "trace_checkpoint": (trace_dir / "checkpoint.json").read_text(encoding="utf-8"),
    }

    replay_root = tmp_path / "replay"
    replayed = start_from_trace(program, trace_dir, target_path, replay_root)

    assert replayed.suspended is False
    assert replayed.state["answer"] == 42
    assert (replay_root / "answer.txt").read_text(encoding="utf-8") == "42"
    assert not (source_root / "answer.txt").exists()
    assert (replay_root / "trace" / "checkpoint.json").exists()
    assert (source_root / "resume_cursor.json").read_text(
        encoding="utf-8"
    ) == source_snapshot["resume_cursor"]
    assert (trace_dir / "state.json").read_text(encoding="utf-8") == source_snapshot["trace_state"]
    assert (trace_dir / "checkpoint.json").read_text(
        encoding="utf-8"
    ) == source_snapshot["trace_checkpoint"]


def test_start_from_trace_requires_debug_guard_for_injected_state(
    tmp_path: Path,
) -> None:
    program, trace_dir, target_path = _build_suspended_trace(tmp_path)

    with pytest.raises(ValueError, match="debug/test-only"):
        start_from_trace(
            program,
            trace_dir,
            target_path,
            tmp_path / "replay",
            debug=False,
            injected_state={"seed": 5},
        )


def test_start_from_trace_validates_injected_state_against_declared_schemas(
    tmp_path: Path,
) -> None:
    program, trace_dir, target_path = _build_suspended_trace(tmp_path)

    with pytest.raises(ValueError, match="schema validation"):
        start_from_trace(
            program,
            trace_dir,
            target_path,
            tmp_path / "replay",
            injected_state={"seed": "bad"},
        )
