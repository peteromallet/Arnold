"""Lifecycle-hook tests for the native-first evidence-pack pipeline.

The M4 migration replaces the graph-only ``EvidencePackHooks`` with the shared
native runtime's optional :class:`~arnold.pipeline.native.trace.NativeTraceHooks`.
These tests verify that trace emission and resume-cursor persistence work for
native execution.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from arnold.pipeline.native.runtime import run_native_pipeline
from arnold.pipeline.native.trace import NativeTraceHooks
from arnold_pipelines.evidence_pack.pipeline import build_pipeline
from arnold_pipelines.evidence_pack.verifier import make_evidence_pack_payload


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, sort_keys=True, indent=2), encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _passing_evidence_pack(evidence_pack_id: str = "pack-hooks") -> dict[str, Any]:
    return make_evidence_pack_payload(
        evidence_pack_id=evidence_pack_id,
        source_ticket="ticket-1",
        checkpoints=[
            {
                "checkpoint_id": f"{evidence_pack_id}.structural_audit",
                "status": "passed",
                "artifact_refs": [],
            }
        ],
    )


def _failing_evidence_pack(evidence_pack_id: str = "pack-hooks") -> dict[str, Any]:
    return make_evidence_pack_payload(
        evidence_pack_id=evidence_pack_id,
        source_ticket="",
        checkpoints=[
            {
                "checkpoint_id": f"{evidence_pack_id}.structural_audit",
                "status": "passed",
                "artifact_refs": [],
            }
        ],
    )


def test_native_trace_hooks_write_pass_events_and_state(tmp_path: Path) -> None:
    trace_dir = tmp_path / "traces"
    program = build_pipeline().native_program
    pack = _passing_evidence_pack()
    pack_path = tmp_path / "input_pack.json"
    _write_json(pack_path, pack)

    hooks = NativeTraceHooks(trace_dir=trace_dir, artifact_root=tmp_path)
    run_native_pipeline(
        program,
        artifact_root=tmp_path,
        initial_state={"evidence_pack_path": str(pack_path)},
        hooks=hooks,
    )

    assert not (tmp_path / "resume_cursor.json").exists()

    events_path = trace_dir / "events.ndjson"
    assert events_path.exists()
    events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    kinds = [event["kind"] for event in events]
    assert "phase.start" in kinds
    assert "phase.end" in kinds
    assert "stage.complete" in kinds
    assert "checkpoint" in kinds

    state_path = trace_dir / "state.json"
    assert state_path.exists()
    state = _read_json(state_path)
    assert "evidence_pack" in state


def test_native_runtime_persists_resume_cursor_on_fail_suspension(tmp_path: Path) -> None:
    program = build_pipeline().native_program
    pack = _failing_evidence_pack()
    pack_path = tmp_path / "input_pack.json"
    _write_json(pack_path, pack)

    result = run_native_pipeline(
        program,
        artifact_root=tmp_path,
        initial_state={"evidence_pack_path": str(pack_path)},
    )

    assert result.suspended is True
    cursor_path = tmp_path / "resume_cursor.json"
    assert cursor_path.exists()
    cursor = _read_json(cursor_path)
    assert "human_review" in str(cursor.get("stage", ""))
    native = cursor.get("native", {})
    assert native.get("suspension_kind") == "phase_suspended"
