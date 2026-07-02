"""Native hook and continuation-surface coverage for evidence-pack."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from arnold.pipeline.native.runtime import run_native_pipeline
from arnold.pipeline.native.trace import NativeTraceHooks
from arnold.pipelines.evidence_pack.pipeline import build_pipeline
from arnold.pipelines.evidence_pack.verifier import make_evidence_pack_payload


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, sort_keys=True, indent=2), encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _events(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _passing_evidence_pack(evidence_pack_id: str) -> dict[str, Any]:
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


def _failing_evidence_pack(evidence_pack_id: str) -> dict[str, Any]:
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


def test_native_trace_hooks_emit_trace_artifacts_for_pass_run(tmp_path: Path) -> None:
    pack_path = tmp_path / "input_pack.json"
    trace_dir = tmp_path / "traces"
    _write_json(pack_path, _passing_evidence_pack("pack-hooks-pass"))

    hooks = NativeTraceHooks(trace_dir=trace_dir, artifact_root=tmp_path)
    result = run_native_pipeline(
        build_pipeline().native_program,
        artifact_root=tmp_path,
        initial_state={"evidence_pack_path": str(pack_path)},
        hooks=hooks,
    )

    assert result.suspended is False
    assert (trace_dir / "events.ndjson").exists()
    assert (trace_dir / "state.json").exists()
    assert (trace_dir / "stages.json").exists()
    assert (trace_dir / "artifacts.json").exists()
    assert (trace_dir / "checkpoint.json").exists()

    event_kinds = {event["kind"] for event in _events(trace_dir / "events.ndjson")}
    assert {"pipeline.init", "phase.start", "phase.end", "stage.complete", "checkpoint"} <= event_kinds

    state = _read_json(trace_dir / "state.json")
    checkpoint = _read_json(trace_dir / "checkpoint.json")
    artifacts = _read_json(trace_dir / "artifacts.json")

    assert "evidence_pack" in state
    assert checkpoint["final"] is True
    assert "attestation.json" in artifacts


def test_native_runtime_suspends_with_shared_human_gate_artifacts_not_graph_hooks(
    tmp_path: Path,
) -> None:
    pack_path = tmp_path / "input_pack.json"
    _write_json(pack_path, _failing_evidence_pack("pack-hooks-fail"))

    result = run_native_pipeline(
        build_pipeline().native_program,
        artifact_root=tmp_path,
        initial_state={"evidence_pack_path": str(pack_path)},
    )

    assert result.suspended is True
    cursor = _read_json(tmp_path / "resume_cursor.json")
    awaiting_user = _read_json(tmp_path / "awaiting_user.json")

    assert cursor["native"]["suspension_kind"] == "human_gate"
    assert cursor["artifact_stage"] == "human_review"
    assert awaiting_user["stage"] == "human_review_decision"
    assert not (tmp_path / "attestation.json").exists()


def test_evidence_pack_has_no_graph_hook_continuation_surface() -> None:
    package_root = Path("arnold/pipelines/evidence_pack")
    source_text = "\n".join(
        (package_root / name).read_text(encoding="utf-8")
        for name in ("__init__.py", "pipeline.py", "native.py", "resume.py", "steps.py", "verifier.py")
    )

    assert "build_continuation_pipeline" not in source_text
    assert "arnold.workflow.dsl" not in source_text
    assert "PipelineBuilder" not in source_text
    assert not (package_root / "hooks.py").exists()
