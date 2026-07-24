"""Artifact-observed end-to-end coverage for native evidence-pack runs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from arnold.pipeline.native.runtime import run_native_pipeline
from arnold.pipelines.evidence_pack.pipeline import build_pipeline
from arnold.pipelines.evidence_pack.resume import resume_evidence_pack
from arnold.pipelines.evidence_pack.verifier import make_evidence_pack_payload


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, sort_keys=True, indent=2), encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


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


def _run_native(artifact_root: Path, payload: dict[str, Any]) -> Any:
    pack_path = artifact_root / "input_pack.json"
    _write_json(pack_path, payload)
    return run_native_pipeline(
        build_pipeline().native_program,
        artifact_root=artifact_root,
        initial_state={"evidence_pack_path": str(pack_path)},
    )


def test_native_pass_run_persists_evidence_pack_verdict_and_attestation_json(
    tmp_path: Path,
) -> None:
    result = _run_native(tmp_path, _passing_evidence_pack("pack-pass"))

    assert result.suspended is False
    assert not (tmp_path / "resume_cursor.json").exists()
    assert not (tmp_path / "awaiting_user.json").exists()

    evidence_pack = _read_json(tmp_path / "evidence_pack.json")
    verdict = _read_json(tmp_path / "verdict.json")
    attestation = _read_json(tmp_path / "attestation.json")
    human_gate = _read_json(tmp_path / "checkpoint_pack-pass.human_review_gate.json")

    assert evidence_pack["evidence_pack_id"] == "pack-pass"
    assert verdict["verdict"] == "PASS"
    assert attestation["evidence_pack_id"] == "pack-pass"
    assert attestation["verdict"] == "PASS"
    assert human_gate["status"] == "passed"


def test_native_fail_run_suspends_with_persisted_cursor_checkpoint_and_verdict_json(
    tmp_path: Path,
) -> None:
    result = _run_native(tmp_path, _failing_evidence_pack("pack-fail"))

    assert result.suspended is True
    assert not (tmp_path / "attestation.json").exists()

    evidence_pack = _read_json(tmp_path / "evidence_pack.json")
    verdict = _read_json(tmp_path / "verdict.json")
    checkpoint = _read_json(tmp_path / "checkpoint_pack-fail.human_review_gate.json")
    awaiting_user = _read_json(tmp_path / "awaiting_user.json")
    cursor = _read_json(tmp_path / "resume_cursor.json")

    assert evidence_pack["evidence_pack_id"] == "pack-fail"
    assert verdict["verdict"] == "FAIL"
    assert checkpoint["status"] == "suspended"
    assert checkpoint["resume_cursor"] == "pack-fail.human_review_gate"
    assert awaiting_user["artifact_stage"] == "human_review"
    assert cursor["artifact_stage"] == "human_review"
    assert cursor["native"]["suspension_kind"] == "human_gate"


def test_native_resume_approval_clears_cursor_and_emits_attestation_json(
    tmp_path: Path,
) -> None:
    _run_native(tmp_path, _failing_evidence_pack("pack-approve"))

    result = resume_evidence_pack(
        tmp_path,
        human_input={"approved": True, "comment": "ship it"},
    )

    assert result.resumed is True
    assert not (tmp_path / "resume_cursor.json").exists()
    assert not (tmp_path / "awaiting_user.json").exists()

    verdict = _read_json(tmp_path / "verdict.json")
    attestation = _read_json(tmp_path / "attestation.json")
    checkpoint = _read_json(tmp_path / "checkpoint_pack-approve.human_review_gate.json")

    assert verdict["verdict"] == "FAIL"
    assert attestation["evidence_pack_id"] == "pack-approve"
    assert attestation["verdict"] == "FAIL"
    assert checkpoint["status"] == "suspended"


def test_native_resume_rejection_clears_cursor_without_attestation_json(
    tmp_path: Path,
) -> None:
    _run_native(tmp_path, _failing_evidence_pack("pack-reject"))

    result = resume_evidence_pack(
        tmp_path,
        human_input={"approved": False, "comment": "needs work"},
    )

    assert result.resumed is True
    assert not (tmp_path / "resume_cursor.json").exists()
    assert not (tmp_path / "awaiting_user.json").exists()
    assert not (tmp_path / "attestation.json").exists()

    verdict = _read_json(tmp_path / "verdict.json")
    checkpoint = _read_json(tmp_path / "checkpoint_pack-reject.human_review_gate.json")

    assert verdict["verdict"] == "FAIL"
    assert checkpoint["status"] == "suspended"
