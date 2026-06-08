"""Step-level tests for concrete evidence-pack Step classes.

These tests exercise each step in isolation using ``StepContext`` with
a temporary artifact root.  They verify:

- Ingest: loads, validates, and writes evidence pack
- Content validators: run per-kind checks and write checkpoint artifacts
- Reduce: aggregates checkpoint results into a verdict
- Human review: suspends on first run, resumes with human input
- Emit attestation: emits signed attestation artifact

All tests use deterministic payloads and file-based artifact I/O.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

import pytest

from arnold.pipeline.types import (
    ContractStatus,
    StepContext,
)

from arnold.pipelines.evidence_pack.verifier import (
    EVIDENCE_PACK_SCHEMA,
    Verdict,
    make_checkpoint_payload,
    make_evidence_pack_payload,
)

from arnold.pipelines.evidence_pack.steps import (
    ContentValidatorStep,
    EmitAttestationStep,
    HumanReviewStep,
    IngestStep,
    ReduceStep,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _temp_artifact_root() -> str:
    return tempfile.mkdtemp(prefix="evidence_pack_test_")


def _make_ctx(
    artifact_root: str | None = None,
    inputs: dict[str, Any] | None = None,
) -> StepContext:
    return StepContext(
        artifact_root=artifact_root or _temp_artifact_root(),
        state={},
        inputs=inputs or {},
    )


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, sort_keys=True, indent=2), encoding="utf-8")


def _valid_evidence_pack(evidence_pack_id: str = "pack-001") -> dict[str, Any]:
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


# ---------------------------------------------------------------------------
# IngestStep tests
# ---------------------------------------------------------------------------


class TestIngestStep:
    """IngestStep loads, validates, and writes evidence pack artifacts."""

    def test_ingest_valid_pack_succeeds(self) -> None:
        """A valid evidence pack is ingested successfully."""
        root = _temp_artifact_root()
        pack_path = Path(root) / "input_pack.json"
        pack = _valid_evidence_pack()
        _write_json(pack_path, pack)

        step = IngestStep()
        ctx = _make_ctx(root, {"evidence_pack_path": str(pack_path)})
        result = step.run(ctx)

        assert result.next == "validators"
        assert result.contract_result is not None
        assert result.contract_result.status == ContractStatus.COMPLETED
        assert result.contract_result.payload["evidence_pack_id"] == "pack-001"
        assert result.contract_result.payload["checkpoint_count"] == 2

        # Verify artifact was written
        out_path = Path(root) / "evidence_pack.json"
        assert out_path.exists()
        written = json.loads(out_path.read_text(encoding="utf-8"))
        assert written["evidence_pack_id"] == "pack-001"

    def test_ingest_missing_path_fails(self) -> None:
        """Missing evidence_pack_path in inputs returns FAILED."""
        step = IngestStep()
        ctx = _make_ctx(inputs={})
        result = step.run(ctx)

        assert result.next == "failed"
        assert result.contract_result is not None
        assert result.contract_result.status == ContractStatus.FAILED

    def test_ingest_nonexistent_file_fails(self) -> None:
        """A nonexistent file path returns FAILED."""
        step = IngestStep()
        ctx = _make_ctx(inputs={"evidence_pack_path": "/nonexistent/pack.json"})
        result = step.run(ctx)

        assert result.next == "failed"
        assert result.contract_result is not None
        assert result.contract_result.status == ContractStatus.FAILED

    def test_ingest_invalid_json_fails(self) -> None:
        """A file with invalid JSON returns FAILED."""
        root = _temp_artifact_root()
        bad_path = Path(root) / "bad.json"
        bad_path.write_text("not json", encoding="utf-8")

        step = IngestStep()
        ctx = _make_ctx(root, {"evidence_pack_path": str(bad_path)})
        result = step.run(ctx)

        assert result.next == "failed"
        assert result.contract_result is not None
        assert result.contract_result.status == ContractStatus.FAILED

    def test_ingest_schema_violation_fails(self) -> None:
        """A pack that fails schema validation returns FAILED."""
        root = _temp_artifact_root()
        pack_path = Path(root) / "bad_pack.json"
        # Missing required "evidence_pack_id"
        _write_json(pack_path, {"checkpoints": []})

        step = IngestStep()
        ctx = _make_ctx(root, {"evidence_pack_path": str(pack_path)})
        result = step.run(ctx)

        assert result.next == "failed"
        assert result.contract_result is not None
        assert result.contract_result.status == ContractStatus.FAILED


# ---------------------------------------------------------------------------
# ContentValidatorStep tests
# ---------------------------------------------------------------------------


class TestContentValidatorStep:
    """ContentValidatorStep runs per-kind checks and writes checkpoint artifacts."""

    def test_structural_audit_passes_for_valid_pack(self) -> None:
        """Structural audit passes for a valid evidence pack."""
        root = _temp_artifact_root()
        pack_path = Path(root) / "evidence_pack.json"
        _write_json(pack_path, _valid_evidence_pack())

        step = ContentValidatorStep(
            name="structural_audit",
            checkpoint_kind="structural_audit",
        )
        ctx = _make_ctx(root, {"evidence_pack": str(pack_path)})
        result = step.run(ctx)

        assert result.next == "passed"
        assert result.contract_result is not None
        assert result.contract_result.status == ContractStatus.COMPLETED
        assert result.contract_result.payload["checkpoint_kind"] == "structural_audit"
        assert result.contract_result.payload["status"] == "passed"

        # Verify checkpoint artifact
        cp_path = Path(root) / "checkpoint_pack-001.structural_audit.json"
        assert cp_path.exists()
        cp = json.loads(cp_path.read_text(encoding="utf-8"))
        assert cp["status"] == "passed"

    def test_structural_audit_fails_for_bad_checkpoints(self) -> None:
        """Structural audit fails when checkpoints are malformed."""
        root = _temp_artifact_root()
        pack_path = Path(root) / "evidence_pack.json"
        _write_json(pack_path, {
            "evidence_pack_id": "pack-001",
            "source_ticket": "TICKET",
            "checkpoints": [{"not_a_valid_checkpoint": True}],
        })

        step = ContentValidatorStep(
            name="structural_audit",
            checkpoint_kind="structural_audit",
        )
        ctx = _make_ctx(root, {"evidence_pack": str(pack_path)})
        result = step.run(ctx)

        assert result.next == "failed"
        assert result.contract_result is not None
        assert result.contract_result.status == ContractStatus.FAILED

    def test_budget_enforcement_passes(self) -> None:
        """Budget enforcement passes when source_ticket is present."""
        root = _temp_artifact_root()
        pack_path = Path(root) / "evidence_pack.json"
        _write_json(pack_path, _valid_evidence_pack())

        step = ContentValidatorStep(
            name="budget",
            checkpoint_kind="budget_enforcement",
        )
        ctx = _make_ctx(root, {"evidence_pack": str(pack_path)})
        result = step.run(ctx)

        assert result.next == "passed"
        assert result.contract_result is not None
        assert result.contract_result.status == ContractStatus.COMPLETED

    def test_budget_enforcement_fails_without_source_ticket(self) -> None:
        """Budget enforcement fails when source_ticket is missing."""
        root = _temp_artifact_root()
        pack_path = Path(root) / "evidence_pack.json"
        _write_json(pack_path, {
            "evidence_pack_id": "pack-001",
            "checkpoints": [],
        })

        step = ContentValidatorStep(
            name="budget",
            checkpoint_kind="budget_enforcement",
        )
        ctx = _make_ctx(root, {"evidence_pack": str(pack_path)})
        result = step.run(ctx)

        assert result.next == "failed"

    def test_suspension_propagation_passes(self) -> None:
        """Suspension propagation passes for suspended checkpoints with diagnostics."""
        root = _temp_artifact_root()
        pack_path = Path(root) / "evidence_pack.json"
        _write_json(pack_path, make_evidence_pack_payload(
            evidence_pack_id="pack-001",
            source_ticket="TICKET",
            checkpoints=[
                make_checkpoint_payload(
                    checkpoint_id="pack-001.suspended",
                    evidence_pack_id="pack-001",
                    checkpoint_kind="human_review_gate",
                    status="suspended",
                    diagnostic="awaiting review",
                    resume_cursor="pack-001.suspended",
                ),
            ],
        ))

        step = ContentValidatorStep(
            name="suspension",
            checkpoint_kind="suspension_propagation",
        )
        ctx = _make_ctx(root, {"evidence_pack": str(pack_path)})
        result = step.run(ctx)

        assert result.next == "passed"

    def test_by_ref_validation_passes(self) -> None:
        """By-ref validation passes for valid artifact refs."""
        root = _temp_artifact_root()
        pack_path = Path(root) / "evidence_pack.json"
        _write_json(pack_path, make_evidence_pack_payload(
            evidence_pack_id="pack-001",
            source_ticket="TICKET",
            checkpoints=[
                {
                    "checkpoint_id": "pack-001.refs",
                    "status": "passed",
                    "artifact_refs": [
                        {"uri": "s3://bucket/artifact.json", "content_type": "application/json"},
                    ],
                },
            ],
        ))

        step = ContentValidatorStep(
            name="by_ref",
            checkpoint_kind="by_ref_validation",
        )
        ctx = _make_ctx(root, {"evidence_pack": str(pack_path)})
        result = step.run(ctx)

        assert result.next == "passed"

    def test_unknown_checkpoint_kind_fails(self) -> None:
        """An unknown checkpoint kind returns FAILED."""
        root = _temp_artifact_root()
        pack_path = Path(root) / "evidence_pack.json"
        _write_json(pack_path, _valid_evidence_pack())

        step = ContentValidatorStep(
            name="unknown",
            checkpoint_kind="nonexistent_kind",
        )
        ctx = _make_ctx(root, {"evidence_pack": str(pack_path)})
        result = step.run(ctx)

        assert result.next == "failed"

    def test_missing_evidence_pack_fails(self) -> None:
        """Missing evidence_pack input returns FAILED."""
        step = ContentValidatorStep()
        ctx = _make_ctx(inputs={})
        result = step.run(ctx)

        assert result.next == "failed"
        assert result.contract_result is not None
        assert result.contract_result.status == ContractStatus.FAILED


# ---------------------------------------------------------------------------
# ReduceStep tests
# ---------------------------------------------------------------------------


class TestReduceStep:
    """ReduceStep aggregates checkpoint results into a verdict."""

    def test_reduce_all_passed_returns_pass(self) -> None:
        """When all checkpoints pass, the verdict is PASS."""
        root = _temp_artifact_root()
        pack_path = Path(root) / "evidence_pack.json"
        _write_json(pack_path, _valid_evidence_pack())

        # Write two passed checkpoint artifacts
        cp1 = make_checkpoint_payload(
            checkpoint_id="pack-001.structural_audit",
            evidence_pack_id="pack-001",
            checkpoint_kind="structural_audit",
            status="passed",
        )
        cp2 = make_checkpoint_payload(
            checkpoint_id="pack-001.budget_enforcement",
            evidence_pack_id="pack-001",
            checkpoint_kind="budget_enforcement",
            status="passed",
        )
        cp1_path = Path(root) / "checkpoint_pack-001.structural_audit.json"
        cp2_path = Path(root) / "checkpoint_pack-001.budget_enforcement.json"
        _write_json(cp1_path, cp1)
        _write_json(cp2_path, cp2)

        step = ReduceStep()
        ctx = _make_ctx(root, {
            "evidence_pack": str(pack_path),
            "pack-001.structural_audit": str(cp1_path),
            "pack-001.budget_enforcement": str(cp2_path),
        })
        result = step.run(ctx)

        assert result.next == "emit"
        assert result.contract_result is not None
        assert result.contract_result.status == ContractStatus.COMPLETED
        assert result.contract_result.payload["verdict"] == "PASS"

    def test_reduce_with_failed_checkpoint_returns_fail(self) -> None:
        """When any checkpoint fails, the verdict is FAIL."""
        root = _temp_artifact_root()
        pack_path = Path(root) / "evidence_pack.json"
        _write_json(pack_path, _valid_evidence_pack())

        cp1 = make_checkpoint_payload(
            checkpoint_id="pack-001.structural_audit",
            evidence_pack_id="pack-001",
            checkpoint_kind="structural_audit",
            status="passed",
        )
        cp2 = make_checkpoint_payload(
            checkpoint_id="pack-001.budget_enforcement",
            evidence_pack_id="pack-001",
            checkpoint_kind="budget_enforcement",
            status="failed",
            diagnostic="budget overflow",
        )
        cp1_path = Path(root) / "checkpoint_pack-001.structural_audit.json"
        cp2_path = Path(root) / "checkpoint_pack-001.budget_enforcement.json"
        _write_json(cp1_path, cp1)
        _write_json(cp2_path, cp2)

        step = ReduceStep()
        ctx = _make_ctx(root, {
            "evidence_pack": str(pack_path),
            "pack-001.structural_audit": str(cp1_path),
            "pack-001.budget_enforcement": str(cp2_path),
        })
        result = step.run(ctx)

        assert result.next == "human_review"
        assert result.contract_result is not None
        assert result.contract_result.status == ContractStatus.FAILED
        assert result.contract_result.payload["verdict"] == "FAIL"
        assert "pack-001.budget_enforcement" in result.contract_result.payload["failed_checkpoints"]

    def test_reduce_missing_evidence_pack_fails(self) -> None:
        """Missing evidence_pack input returns FAILED."""
        step = ReduceStep()
        ctx = _make_ctx(inputs={})
        result = step.run(ctx)

        assert result.next == "failed"

    def test_reduce_writes_verdict_artifact(self) -> None:
        """Reduce writes a verdict.json artifact."""
        root = _temp_artifact_root()
        pack_path = Path(root) / "evidence_pack.json"
        _write_json(pack_path, _valid_evidence_pack())

        cp1 = make_checkpoint_payload(
            checkpoint_id="pack-001.structural_audit",
            evidence_pack_id="pack-001",
            checkpoint_kind="structural_audit",
            status="passed",
        )
        cp1_path = Path(root) / "checkpoint_pack-001.structural_audit.json"
        _write_json(cp1_path, cp1)

        step = ReduceStep()
        ctx = _make_ctx(root, {
            "evidence_pack": str(pack_path),
            "pack-001.structural_audit": str(cp1_path),
        })
        result = step.run(ctx)

        verdict_path = Path(root) / "verdict.json"
        assert verdict_path.exists()
        verdict = json.loads(verdict_path.read_text(encoding="utf-8"))
        assert verdict["verdict"] == "PASS"


# ---------------------------------------------------------------------------
# HumanReviewStep tests
# ---------------------------------------------------------------------------


class TestHumanReviewStep:
    """HumanReviewStep suspends on first run and resumes with human input."""

    def test_suspend_on_first_run(self) -> None:
        """First run without human_input returns SUSPENDED with a Suspension."""
        root = _temp_artifact_root()
        pack_path = Path(root) / "evidence_pack.json"
        _write_json(pack_path, _valid_evidence_pack())

        step = HumanReviewStep()
        ctx = _make_ctx(root, {"evidence_pack": str(pack_path)})
        result = step.run(ctx)

        assert result.next == "suspended"
        assert result.contract_result is not None
        assert result.contract_result.status == ContractStatus.SUSPENDED
        assert result.contract_result.suspension is not None
        assert result.contract_result.suspension.kind == "human"
        assert result.contract_result.suspension.default_action == "reject"

        # Verify checkpoint artifact was written
        cp_path = Path(root) / "checkpoint_pack-001.human_review_gate.json"
        assert cp_path.exists()
        cp = json.loads(cp_path.read_text(encoding="utf-8"))
        assert cp["status"] == "suspended"
        assert cp["resume_cursor"] == "pack-001.human_review_gate"

    def test_resume_with_approval(self) -> None:
        """Resuming with approved=True returns COMPLETED."""
        root = _temp_artifact_root()
        pack_path = Path(root) / "evidence_pack.json"
        _write_json(pack_path, _valid_evidence_pack())

        step = HumanReviewStep()
        ctx = _make_ctx(root, {
            "evidence_pack": str(pack_path),
            "human_input": {"approved": True, "comment": "looks good"},
        })
        result = step.run(ctx)

        assert result.next == "emit"
        assert result.contract_result is not None
        assert result.contract_result.status == ContractStatus.COMPLETED
        assert result.contract_result.payload["status"] == "passed"

        # Verify checkpoint artifact was written with passed status
        cp_path = Path(root) / "checkpoint_pack-001.human_review_gate.json"
        assert cp_path.exists()
        cp = json.loads(cp_path.read_text(encoding="utf-8"))
        assert cp["status"] == "passed"

    def test_resume_with_rejection(self) -> None:
        """Resuming with approved=False returns FAILED."""
        root = _temp_artifact_root()
        pack_path = Path(root) / "evidence_pack.json"
        _write_json(pack_path, _valid_evidence_pack())

        step = HumanReviewStep()
        ctx = _make_ctx(root, {
            "evidence_pack": str(pack_path),
            "human_input": {"approved": False, "comment": "needs work"},
        })
        result = step.run(ctx)

        assert result.next == "failed"
        assert result.contract_result is not None
        assert result.contract_result.status == ContractStatus.FAILED
        assert result.contract_result.payload["status"] == "failed"

    def test_resume_with_invalid_human_input_fails(self) -> None:
        """Resuming with non-dict human_input returns FAILED."""
        root = _temp_artifact_root()
        pack_path = Path(root) / "evidence_pack.json"
        _write_json(pack_path, _valid_evidence_pack())

        step = HumanReviewStep()
        ctx = _make_ctx(root, {
            "evidence_pack": str(pack_path),
            "human_input": "not a dict",
        })
        result = step.run(ctx)

        assert result.next == "failed"


# ---------------------------------------------------------------------------
# EmitAttestationStep tests
# ---------------------------------------------------------------------------


class TestEmitAttestationStep:
    """EmitAttestationStep emits a signed attestation artifact."""

    def test_emit_attestation_for_pass_verdict(self) -> None:
        """A PASS verdict produces a completed attestation."""
        root = _temp_artifact_root()
        pack_path = Path(root) / "evidence_pack.json"
        _write_json(pack_path, _valid_evidence_pack("pack-001"))

        # Write a PASS verdict
        verdict_path = Path(root) / "verdict.json"
        _write_json(verdict_path, {
            "verdict_id": "pack-001.verdict",
            "evidence_pack_id": "pack-001",
            "verdict": "PASS",
            "failed_checkpoints": [],
            "timestamp": "2026-06-07T00:00:00Z",
        })

        # Write passed checkpoint artifacts
        cp1 = make_checkpoint_payload(
            checkpoint_id="pack-001.structural_audit",
            evidence_pack_id="pack-001",
            checkpoint_kind="structural_audit",
            status="passed",
        )
        cp1_path = Path(root) / "checkpoint_pack-001.structural_audit.json"
        _write_json(cp1_path, cp1)

        step = EmitAttestationStep()
        ctx = _make_ctx(root, {
            "evidence_pack": str(pack_path),
            "verdict": str(verdict_path),
            "pack-001.structural_audit": str(cp1_path),
        })
        result = step.run(ctx)

        assert result.next == "halt"
        assert result.contract_result is not None
        assert result.contract_result.status == ContractStatus.COMPLETED
        assert result.contract_result.payload["verdict"] == "PASS"

        # Verify attestation artifact
        att_path = Path(root) / "attestation.json"
        assert att_path.exists()
        att = json.loads(att_path.read_text(encoding="utf-8"))
        assert att["attestation_id"] == "pack-001.attestation"
        assert att["verdict"] == "PASS"
        assert "timestamp" in att

    def test_emit_attestation_for_fail_verdict(self) -> None:
        """A FAIL verdict produces an attestation with FAIL verdict."""
        root = _temp_artifact_root()
        pack_path = Path(root) / "evidence_pack.json"
        _write_json(pack_path, _valid_evidence_pack("pack-001"))

        verdict_path = Path(root) / "verdict.json"
        _write_json(verdict_path, {
            "verdict_id": "pack-001.verdict",
            "evidence_pack_id": "pack-001",
            "verdict": "FAIL",
            "failed_checkpoints": ["pack-001.structural_audit"],
            "timestamp": "2026-06-07T00:00:00Z",
        })

        step = EmitAttestationStep()
        ctx = _make_ctx(root, {
            "evidence_pack": str(pack_path),
            "verdict": str(verdict_path),
        })
        result = step.run(ctx)

        assert result.next == "halt"
        assert result.contract_result.payload["verdict"] == "FAIL"

        att_path = Path(root) / "attestation.json"
        assert att_path.exists()
        att = json.loads(att_path.read_text(encoding="utf-8"))
        assert att["verdict"] == "FAIL"

    def test_emit_attestation_missing_evidence_pack_fails(self) -> None:
        """Missing evidence_pack input returns FAILED."""
        step = EmitAttestationStep()
        ctx = _make_ctx(inputs={})
        result = step.run(ctx)

        assert result.next == "failed"
        assert result.contract_result is not None
        assert result.contract_result.status == ContractStatus.FAILED

    def test_emit_attestation_with_failed_checkpoint_in_results(self) -> None:
        """A checkpoint with status=failed flips verdict to FAIL."""
        root = _temp_artifact_root()
        pack_path = Path(root) / "evidence_pack.json"
        _write_json(pack_path, _valid_evidence_pack("pack-001"))

        cp_failed = make_checkpoint_payload(
            checkpoint_id="pack-001.structural_audit",
            evidence_pack_id="pack-001",
            checkpoint_kind="structural_audit",
            status="failed",
            diagnostic="structure violation",
        )
        cp_path = Path(root) / "checkpoint_pack-001.structural_audit.json"
        _write_json(cp_path, cp_failed)

        step = EmitAttestationStep()
        ctx = _make_ctx(root, {
            "evidence_pack": str(pack_path),
            "pack-001.structural_audit": str(cp_path),
        })
        result = step.run(ctx)

        assert result.contract_result.payload["verdict"] == "FAIL"
        att_path = Path(root) / "attestation.json"
        att = json.loads(att_path.read_text(encoding="utf-8"))
        assert att["verdict"] == "FAIL"

    def test_emit_attestation_includes_checkpoint_results(self) -> None:
        """Attestation includes checkpoint_results array."""
        root = _temp_artifact_root()
        pack_path = Path(root) / "evidence_pack.json"
        _write_json(pack_path, _valid_evidence_pack("pack-001"))

        cp1 = make_checkpoint_payload(
            checkpoint_id="pack-001.structural_audit",
            evidence_pack_id="pack-001",
            checkpoint_kind="structural_audit",
            status="passed",
        )
        cp1_path = Path(root) / "checkpoint_pack-001.structural_audit.json"
        _write_json(cp1_path, cp1)

        step = EmitAttestationStep()
        ctx = _make_ctx(root, {
            "evidence_pack": str(pack_path),
            "pack-001.structural_audit": str(cp1_path),
        })
        step.run(ctx)

        att_path = Path(root) / "attestation.json"
        att = json.loads(att_path.read_text(encoding="utf-8"))
        assert len(att["checkpoint_results"]) >= 1
        assert att["checkpoint_results"][0]["checkpoint_id"] == "pack-001.structural_audit"
