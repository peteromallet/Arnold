"""End-to-end tests for the native-first evidence-pack pipeline.

These tests exercise the full PASS path via :func:`run_native_pipeline` and
verify that attestation emission completes without human-review suspension.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from arnold.pipeline.native.runtime import run_native_pipeline
from arnold_pipelines.evidence_pack.pipeline import build_pipeline
from arnold_pipelines.evidence_pack.resume import resume_evidence_pack
from arnold_pipelines.evidence_pack.verifier import make_evidence_pack_payload


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, sort_keys=True, indent=2), encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _passing_evidence_pack_fixture(evidence_pack_id: str = "pack-001") -> dict[str, Any]:
    """Return a valid evidence pack payload that should pass all validators."""
    return make_evidence_pack_payload(
        evidence_pack_id=evidence_pack_id,
        source_ticket="01KT50AZRMK5X890TQ565DDB5V",
        checkpoints=[
            {
                "checkpoint_id": f"{evidence_pack_id}.structural_audit",
                "status": "passed",
                "artifact_refs": [],
            },
            {
                "checkpoint_id": f"{evidence_pack_id}.budget_enforcement",
                "status": "passed",
                "artifact_refs": [],
            },
        ],
    )


def _failing_evidence_pack_fixture(evidence_pack_id: str = "pack-001") -> dict[str, Any]:
    """Return a valid evidence pack payload that fails budget enforcement."""
    return make_evidence_pack_payload(
        evidence_pack_id=evidence_pack_id,
        source_ticket="",
        checkpoints=[
            {
                "checkpoint_id": f"{evidence_pack_id}.structural_audit",
                "status": "passed",
                "artifact_refs": [],
            },
        ],
    )


def _run_pass(artifact_root: Path, evidence_pack_id: str) -> Any:
    """Run a PASS evidence pack through attestation emission."""
    pack_path = artifact_root / "input_pack.json"
    _write_json(pack_path, _passing_evidence_pack_fixture(evidence_pack_id))
    program = build_pipeline().native_program
    return run_native_pipeline(
        program,
        artifact_root=artifact_root,
        initial_state={"evidence_pack_path": str(pack_path)},
    )


def _run_fail_to_suspension(artifact_root: Path, evidence_pack_id: str) -> Any:
    """Run a FAIL evidence pack to the human-review suspension point."""
    pack_path = artifact_root / "input_pack.json"
    _write_json(pack_path, _failing_evidence_pack_fixture(evidence_pack_id))
    program = build_pipeline().native_program
    return run_native_pipeline(
        program,
        artifact_root=artifact_root,
        initial_state={"evidence_pack_path": str(pack_path)},
    )


# ---------------------------------------------------------------------------
# PASS pipeline completion
# ---------------------------------------------------------------------------


class TestPassPipelineCompletion:
    """The PASS path emits attestation and never enters human_review."""

    def test_pass_emits_attestation_through_emit_attestation(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="ep_e2e_pass_"))
        result = _run_pass(root, "pack-001")

        assert result.suspended is False
        assert any(
            "emit_attestation" in stage for stage in result.stages
        ), "PASS path did not execute emit_attestation"

        att_path = root / "attestation.json"
        assert att_path.exists(), (
            f"attestation.json must exist after PASS completion; "
            f"contents of {root}: {sorted(p.name for p in root.iterdir())}"
        )
        attestation = _read_json(att_path)
        assert attestation["evidence_pack_id"] == "pack-001"
        assert attestation["verdict"] == "PASS"

    def test_pass_does_not_write_resume_cursor(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="ep_e2e_pass_"))
        result = _run_pass(root, "pack-002")

        assert result.suspended is False
        assert result.cursor_path is None
        assert not (root / "resume_cursor.json").exists()

    def test_pass_does_not_write_suspended_human_review_checkpoint(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="ep_e2e_pass_"))
        result = _run_pass(root, "pack-003")

        assert result.suspended is False
        assert all("__human_review__" not in stage for stage in result.stages)

        cp_path = root / "checkpoint_pack-003.human_review_gate.json"
        assert cp_path.exists(), "validator human-review checkpoint missing"
        checkpoint = _read_json(cp_path)
        assert checkpoint["checkpoint_kind"] == "human_review_gate"
        assert checkpoint["status"] == "passed"
        assert "resume_cursor" not in checkpoint

    def test_pass_preserves_evidence_pack_and_verdict_artifacts(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="ep_e2e_pass_"))
        _run_pass(root, "pack-004")

        ep_path = root / "evidence_pack.json"
        assert ep_path.exists(), "evidence_pack.json missing after ingestion"

        verdict_path = root / "verdict.json"
        assert verdict_path.exists(), "verdict.json missing after reduce"
        verdict = _read_json(verdict_path)
        assert verdict["verdict"] == "PASS"


# ---------------------------------------------------------------------------
# FAIL pipeline suspension and resume
# ---------------------------------------------------------------------------


class TestFailPipelineResume:
    """The FAIL path suspends at human_review and resumes from that gate."""

    def test_fail_suspends_with_human_review_cursor_and_checkpoint(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="ep_e2e_fail_"))
        result = _run_fail_to_suspension(root, "pack-fail-001")

        assert result.suspended is True
        assert result.cursor_path == str(root / "resume_cursor.json")
        assert not (root / "attestation.json").exists()

        cursor = _read_json(root / "resume_cursor.json")
        assert "human_review" in str(cursor.get("stage", ""))
        assert cursor["resume_cursor"] == "pack-fail-001.human_review_gate"
        native = cursor.get("native", {})
        assert native.get("suspension_kind") == "phase_suspended"

        checkpoint = _read_json(root / "checkpoint_pack-fail-001.human_review_gate.json")
        assert checkpoint["checkpoint_kind"] == "human_review_gate"
        assert checkpoint["status"] == "suspended"
        assert checkpoint["resume_cursor"] == "pack-fail-001.human_review_gate"

    def test_fail_approval_resume_emits_attestation(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="ep_e2e_fail_"))
        _run_fail_to_suspension(root, "pack-fail-002")

        result = resume_evidence_pack(
            root,
            human_input={"approved": True, "comment": "approved"},
        )

        assert result.resumed is True
        assert "human_review" in str(result.cursor.get("stage", ""))

        checkpoint = _read_json(root / "checkpoint_pack-fail-002.human_review_gate.json")
        assert checkpoint["status"] == "passed"
        assert checkpoint["diagnostic"] == "human review: approved"

        attestation = _read_json(root / "attestation.json")
        assert attestation["evidence_pack_id"] == "pack-fail-002"
        assert attestation["verdict"] == "FAIL"

    def test_fail_rejection_resume_writes_failed_review_without_attestation(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="ep_e2e_fail_"))
        _run_fail_to_suspension(root, "pack-fail-003")

        result = resume_evidence_pack(
            root,
            human_input={"approved": False, "comment": "needs work"},
        )

        assert result.resumed is True
        assert not (root / "attestation.json").exists()

        checkpoint = _read_json(root / "checkpoint_pack-fail-003.human_review_gate.json")
        assert checkpoint["checkpoint_kind"] == "human_review_gate"
        assert checkpoint["status"] == "failed"
        assert checkpoint["diagnostic"] == "human review: needs work"
        assert "resume_cursor" not in checkpoint
