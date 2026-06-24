"""End-to-end tests for the native-first evidence-pack pipeline.

These tests exercise the full pipeline via :func:`run_native_pipeline` and
verify suspension/continuation state through persisted artifacts.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

import pytest

from arnold.pipeline.native.runtime import run_native_pipeline
from arnold.pipelines.evidence_pack.pipeline import build_pipeline
from arnold.pipelines.evidence_pack.verifier import (
    EVIDENCE_PACK_SCHEMA,
    make_evidence_pack_payload,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, sort_keys=True, indent=2), encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _valid_evidence_pack_fixture(evidence_pack_id: str = "pack-001") -> dict[str, Any]:
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


def _run_initial(artifact_root: Path, evidence_pack_id: str) -> Any:
    """Run the pipeline from ingest until it suspends at human_review."""
    pack_path = artifact_root / "input_pack.json"
    _write_json(pack_path, _valid_evidence_pack_fixture(evidence_pack_id))
    program = build_pipeline().native_program
    return run_native_pipeline(
        program,
        artifact_root=artifact_root,
        initial_state={"evidence_pack_path": str(pack_path)},
    )


# ---------------------------------------------------------------------------
# Initial pipeline suspension
# ---------------------------------------------------------------------------


class TestInitialPipelineSuspension:
    """The initial pipeline suspends at human_review; verify via persisted artifacts."""

    def test_suspension_writes_human_review_checkpoint(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="ep_e2e_init_"))
        result = _run_initial(root, "pack-001")
        assert result.suspended is True

        cp_path = root / "checkpoint_pack-001.human_review_gate.json"
        assert cp_path.exists(), (
            f"Expected human review checkpoint at {cp_path}; "
            f"contents of {root}: {list(root.iterdir())}"
        )
        checkpoint = _read_json(cp_path)
        assert checkpoint["status"] == "suspended"
        assert checkpoint["checkpoint_kind"] == "human_review_gate"
        assert checkpoint["resume_cursor"] == "pack-001.human_review_gate"

    def test_suspension_attestation_absent(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="ep_e2e_init_"))
        _run_initial(root, "pack-002")

        att_path = root / "attestation.json"
        assert not att_path.exists(), (
            f"attestation.json must NOT exist after suspension; "
            f"found at {att_path}"
        )

    def test_suspension_preserves_evidence_pack_and_verdict(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="ep_e2e_init_"))
        _run_initial(root, "pack-003")

        ep_path = root / "evidence_pack.json"
        assert ep_path.exists(), "evidence_pack.json missing after ingestion"

        verdict_path = root / "verdict.json"
        assert verdict_path.exists(), "verdict.json missing after reduce"


# ---------------------------------------------------------------------------
# Native resume
# ---------------------------------------------------------------------------


class TestNativeResume:
    """Resume from the native cursor with human_input."""

    def test_resume_approval_writes_attestation(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="ep_e2e_cont_"))
        _run_initial(root, "pack-004")

        program = build_pipeline().native_program
        result = run_native_pipeline(
            program,
            artifact_root=root,
            resume=True,
            initial_state={
                "human_input": {"approved": True, "comment": "approved by reviewer"},
            },
        )
        assert result.suspended is False

        att_path = root / "attestation.json"
        assert att_path.exists(), (
            f"attestation.json must exist after approval; "
            f"contents of {root}: {sorted(p.name for p in root.iterdir())}"
        )
        attestation = _read_json(att_path)
        assert attestation["verdict"] in ("PASS", "FAIL")
        assert attestation["evidence_pack_id"] == "pack-004"

    def test_resume_rejection_no_attestation(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="ep_e2e_cont_"))
        _run_initial(root, "pack-005")

        program = build_pipeline().native_program
        run_native_pipeline(
            program,
            artifact_root=root,
            resume=True,
            initial_state={
                "human_input": {"approved": False, "comment": "rejected by reviewer"},
            },
        )

        att_path = root / "attestation.json"
        assert not att_path.exists(), (
            "attestation.json must NOT exist after rejection"
        )

    def test_resume_preserves_existing_artifacts(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="ep_e2e_cont_"))
        _run_initial(root, "pack-006")

        ep_before = _read_json(root / "evidence_pack.json")
        verdict_before = _read_json(root / "verdict.json")

        program = build_pipeline().native_program
        run_native_pipeline(
            program,
            artifact_root=root,
            resume=True,
            initial_state={
                "human_input": {"approved": True, "comment": "approved"},
            },
        )

        ep_after = _read_json(root / "evidence_pack.json")
        assert ep_after == ep_before, "evidence_pack.json was modified by resume"

        verdict_after = _read_json(root / "verdict.json")
        assert verdict_after == verdict_before, "verdict.json was modified by resume"

    def test_resume_without_initial_suspension_fails(self) -> None:
        """Running resume without a native cursor does not crash."""
        root = Path(tempfile.mkdtemp(prefix="ep_e2e_cont_"))
        pack = _valid_evidence_pack_fixture("pack-007")
        _write_json(root / "evidence_pack.json", pack)

        program = build_pipeline().native_program
        # No cursor exists, so resume=True starts from pc 0 with the provided state.
        run_native_pipeline(
            program,
            artifact_root=root,
            resume=True,
            initial_state={
                "evidence_pack": str(root / "evidence_pack.json"),
                "human_input": {"approved": True, "comment": "approved anyway"},
            },
        )
