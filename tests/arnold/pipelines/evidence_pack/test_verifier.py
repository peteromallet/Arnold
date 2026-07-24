"""Focused verifier and step-helper tests for the canonical evidence-pack package.

These tests import from ``arnold.pipelines.evidence_pack`` (the canonical
package) and cover:

* Strict schema rejection (additionalProperties: false, enum constraints,
  missing required fields)
* Artifact payload constructors
* Verdict value object
* JSON read/write helpers
* Artifact-kind mappings and phase-order constants (step helpers)

No native execution is required — all checks are pure unit tests that
validate the contract surfaces defined in ``verifier.py`` and ``steps.py``.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

import pytest

from arnold.pipelines.evidence_pack.verifier import (
    ATTESTATION_SCHEMA,
    CHECKPOINT_SCHEMA,
    CHECKPOINT_STATUS_FAILED,
    CHECKPOINT_STATUS_PASSED,
    CHECKPOINT_STATUS_SUSPENDED,
    CHECKPOINT_STATUSES,
    EVIDENCE_PACK_SCHEMA,
    VALIDATOR_KIND_BUDGET_ENFORCEMENT,
    VALIDATOR_KIND_BY_REF_VALIDATION,
    VALIDATOR_KIND_HUMAN_REVIEW_GATE,
    VALIDATOR_KIND_STRUCTURAL_AUDIT,
    VALIDATOR_KIND_SUSPENSION_PROPAGATION,
    VALIDATOR_KINDS,
    VERDICT_FAIL,
    VERDICT_PASS,
    VERDICT_SCHEMA,
    VERDICTS,
    VERIFIER_ARTIFACT_ATTESTATION,
    VERIFIER_ARTIFACT_CHECKPOINT,
    VERIFIER_ARTIFACT_EVIDENCE_PACK,
    VERIFIER_ARTIFACT_VERDICT,
    Verdict,
    _VALIDATOR_KINDS,
    make_attestation_payload,
    make_checkpoint_payload,
    make_evidence_pack_payload,
    make_verdict_payload,
    read_json_artifact,
    write_json_artifact,
)

from arnold.pipelines.evidence_pack.steps import (
    EvidencePackStep,
    _ARTIFACT_KIND_BY_STAGE,
    _NATIVE_PHASE_ORDER,
)

from arnold.pipeline.contract_validation import validate_payload_against_schema


# ── Helpers ─────────────────────────────────────────────────────────────────


def _temp_dir() -> str:
    return tempfile.mkdtemp(prefix="ep_verifier_test_")


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, sort_keys=True, indent=2), encoding="utf-8")


# ── Schema strictness: additionalProperties ─────────────────────────────────


class TestAdditionalPropertiesFalse:
    """Every object-level schema must set additionalProperties: False."""

    def test_evidence_pack_schema_rejects_extra(self) -> None:
        assert EVIDENCE_PACK_SCHEMA.get("additionalProperties") is False

    def test_checkpoint_schema_rejects_extra(self) -> None:
        assert CHECKPOINT_SCHEMA.get("additionalProperties") is False

    def test_verdict_schema_rejects_extra(self) -> None:
        assert VERDICT_SCHEMA.get("additionalProperties") is False

    def test_attestation_schema_rejects_extra(self) -> None:
        assert ATTESTATION_SCHEMA.get("additionalProperties") is False


# ── EVIDENCE_PACK_SCHEMA tests ──────────────────────────────────────────────


class TestEvidencePackSchema:
    """Strict schema checks for EVIDENCE_PACK_SCHEMA."""

    def test_valid_payload_passes(self) -> None:
        result = validate_payload_against_schema(
            {
                "evidence_pack_id": "ep-001",
                "source_ticket": "TICKET-1",
                "checkpoints": [
                    {
                        "checkpoint_id": "ep-001.ck1",
                        "status": "passed",
                        "artifact_refs": [],
                    }
                ],
            },
            EVIDENCE_PACK_SCHEMA,
        )
        assert result.ok, f"Valid pack rejected: {result.diagnostics}"

    def test_missing_required_fields_rejected(self) -> None:
        result = validate_payload_against_schema(
            {"evidence_pack_id": "ep-001"},
            EVIDENCE_PACK_SCHEMA,
        )
        assert not result.ok

    def test_extra_property_rejected(self) -> None:
        result = validate_payload_against_schema(
            {
                "evidence_pack_id": "ep-001",
                "source_ticket": "TICKET-1",
                "checkpoints": [],
                "extra_key": "nope",
            },
            EVIDENCE_PACK_SCHEMA,
        )
        assert not result.ok

    def test_checkpoint_missing_required_rejected(self) -> None:
        result = validate_payload_against_schema(
            {
                "evidence_pack_id": "ep-001",
                "source_ticket": "TICKET-1",
                "checkpoints": [{"checkpoint_id": "bad"}],
            },
            EVIDENCE_PACK_SCHEMA,
        )
        assert not result.ok

    def test_checkpoint_wrong_status_rejected(self) -> None:
        result = validate_payload_against_schema(
            {
                "evidence_pack_id": "ep-001",
                "source_ticket": "TICKET-1",
                "checkpoints": [
                    {
                        "checkpoint_id": "ep-001.ck1",
                        "status": "INVALID_STATUS",
                        "artifact_refs": [],
                    }
                ],
            },
            EVIDENCE_PACK_SCHEMA,
        )
        assert not result.ok


# ── CHECKPOINT_SCHEMA tests ─────────────────────────────────────────────────


class TestCheckpointSchema:
    """Strict schema checks for CHECKPOINT_SCHEMA."""

    def test_valid_payload_passes(self) -> None:
        result = validate_payload_against_schema(
            {
                "checkpoint_id": "ep-001.structural_audit",
                "evidence_pack_id": "ep-001",
                "checkpoint_kind": "structural_audit",
                "status": "passed",
                "artifact_refs": [],
            },
            CHECKPOINT_SCHEMA,
        )
        assert result.ok, f"Valid checkpoint rejected: {result.diagnostics}"

    def test_valid_with_optional_fields_passes(self) -> None:
        result = validate_payload_against_schema(
            {
                "checkpoint_id": "ep-001.ck1",
                "evidence_pack_id": "ep-001",
                "checkpoint_kind": "budget_enforcement",
                "status": "failed",
                "diagnostic": "budget overrun",
                "resume_cursor": "ep-001.ck1",
                "artifact_refs": [],
            },
            CHECKPOINT_SCHEMA,
        )
        assert result.ok, f"Valid checkpoint with optionals rejected: {result.diagnostics}"

    def test_missing_required_fields_rejected(self) -> None:
        result = validate_payload_against_schema(
            {"checkpoint_id": "ep-001.ck1"},
            CHECKPOINT_SCHEMA,
        )
        assert not result.ok

    def test_extra_property_rejected(self) -> None:
        result = validate_payload_against_schema(
            {
                "checkpoint_id": "ep-001.ck1",
                "evidence_pack_id": "ep-001",
                "checkpoint_kind": "structural_audit",
                "status": "passed",
                "artifact_refs": [],
                "bonus": "field",
            },
            CHECKPOINT_SCHEMA,
        )
        assert not result.ok

    def test_wrong_checkpoint_kind_enum_rejected(self) -> None:
        result = validate_payload_against_schema(
            {
                "checkpoint_id": "ep-001.ck1",
                "evidence_pack_id": "ep-001",
                "checkpoint_kind": "not_a_real_kind",
                "status": "passed",
                "artifact_refs": [],
            },
            CHECKPOINT_SCHEMA,
        )
        assert not result.ok

    def test_wrong_status_enum_rejected(self) -> None:
        result = validate_payload_against_schema(
            {
                "checkpoint_id": "ep-001.ck1",
                "evidence_pack_id": "ep-001",
                "checkpoint_kind": "structural_audit",
                "status": "maybe",
                "artifact_refs": [],
            },
            CHECKPOINT_SCHEMA,
        )
        assert not result.ok


# ── VERDICT_SCHEMA tests ────────────────────────────────────────────────────


class TestVerdictSchema:
    """Strict schema checks for VERDICT_SCHEMA."""

    def test_valid_pass_payload_passes(self) -> None:
        result = validate_payload_against_schema(
            {
                "verdict_id": "v-001",
                "evidence_pack_id": "ep-001",
                "verdict": "PASS",
                "failed_checkpoints": [],
                "timestamp": "2026-01-01T00:00:00Z",
            },
            VERDICT_SCHEMA,
        )
        assert result.ok, f"Valid PASS rejected: {result.diagnostics}"

    def test_valid_fail_payload_passes(self) -> None:
        result = validate_payload_against_schema(
            {
                "verdict_id": "v-002",
                "evidence_pack_id": "ep-002",
                "verdict": "FAIL",
                "failed_checkpoints": ["ck-1", "ck-2"],
                "timestamp": "2026-01-01T00:00:00Z",
            },
            VERDICT_SCHEMA,
        )
        assert result.ok, f"Valid FAIL rejected: {result.diagnostics}"

    def test_missing_required_fields_rejected(self) -> None:
        result = validate_payload_against_schema(
            {"verdict": "PASS"},
            VERDICT_SCHEMA,
        )
        assert not result.ok

    def test_unknown_verdict_enum_rejected(self) -> None:
        result = validate_payload_against_schema(
            {
                "verdict_id": "v-003",
                "evidence_pack_id": "ep-003",
                "verdict": "MAYBE",
                "timestamp": "2026-01-01T00:00:00Z",
            },
            VERDICT_SCHEMA,
        )
        assert not result.ok

    def test_extra_property_rejected(self) -> None:
        result = validate_payload_against_schema(
            {
                "verdict_id": "v-004",
                "evidence_pack_id": "ep-004",
                "verdict": "PASS",
                "unexpected_field": "should not pass",
            },
            VERDICT_SCHEMA,
        )
        assert not result.ok


# ── ATTESTATION_SCHEMA tests ────────────────────────────────────────────────


class TestAttestationSchema:
    """Strict schema checks for ATTESTATION_SCHEMA."""

    def test_valid_payload_passes(self) -> None:
        result = validate_payload_against_schema(
            {
                "attestation_id": "att-001",
                "evidence_pack_id": "ep-001",
                "verdict": "PASS",
                "timestamp": "2026-01-01T00:00:00Z",
                "checkpoint_results": [
                    {
                        "checkpoint_id": "ep-001.ck1",
                        "evidence_pack_id": "ep-001",
                        "checkpoint_kind": "structural_audit",
                        "status": "passed",
                        "artifact_refs": [],
                    }
                ],
            },
            ATTESTATION_SCHEMA,
        )
        assert result.ok, f"Valid attestation rejected: {result.diagnostics}"

    def test_missing_required_fields_rejected(self) -> None:
        result = validate_payload_against_schema(
            {"attestation_id": "att-001"},
            ATTESTATION_SCHEMA,
        )
        assert not result.ok

    def test_wrong_verdict_enum_rejected(self) -> None:
        result = validate_payload_against_schema(
            {
                "attestation_id": "att-002",
                "evidence_pack_id": "ep-001",
                "verdict": "UNCLEAR",
                "timestamp": "2026-01-01T00:00:00Z",
                "checkpoint_results": [],
            },
            ATTESTATION_SCHEMA,
        )
        assert not result.ok

    def test_extra_property_rejected(self) -> None:
        result = validate_payload_against_schema(
            {
                "attestation_id": "att-003",
                "evidence_pack_id": "ep-001",
                "verdict": "FAIL",
                "timestamp": "2026-01-01T00:00:00Z",
                "checkpoint_results": [],
                "extra": "no",
            },
            ATTESTATION_SCHEMA,
        )
        assert not result.ok


# ── Payload constructors ────────────────────────────────────────────────────


class TestMakeEvidencePackPayload:
    """make_evidence_pack_payload constructor tests."""

    def test_valid_minimal(self) -> None:
        payload = make_evidence_pack_payload(
            evidence_pack_id="ep-001",
            source_ticket="TICKET-1",
            checkpoints=[],
        )
        assert payload["evidence_pack_id"] == "ep-001"
        assert payload["source_ticket"] == "TICKET-1"
        assert payload["checkpoints"] == []

    def test_valid_with_checkpoints(self) -> None:
        payload = make_evidence_pack_payload(
            evidence_pack_id="ep-001",
            source_ticket="TICKET-1",
            checkpoints=[
                {
                    "checkpoint_id": "ep-001.ck1",
                    "status": "passed",
                    "artifact_refs": [],
                }
            ],
        )
        assert len(payload["checkpoints"]) == 1

    def test_invalid_checkpoints_raises(self) -> None:
        with pytest.raises(ValueError, match="invalid evidence_pack payload"):
            make_evidence_pack_payload(
                evidence_pack_id="ep-001",
                source_ticket="TICKET-1",
                checkpoints=[{"not_valid": True}],
            )


class TestMakeCheckpointPayload:
    """make_checkpoint_payload constructor tests."""

    def test_valid_minimal(self) -> None:
        payload = make_checkpoint_payload(
            checkpoint_id="ep-001.structural_audit",
            evidence_pack_id="ep-001",
            checkpoint_kind="structural_audit",
        )
        assert payload["status"] == "passed"
        assert payload["artifact_refs"] == []

    def test_valid_with_all_fields(self) -> None:
        payload = make_checkpoint_payload(
            checkpoint_id="ep-001.ck1",
            evidence_pack_id="ep-001",
            checkpoint_kind="budget_enforcement",
            status="failed",
            diagnostic="budget exceeded",
            resume_cursor="ep-001.ck1",
            artifact_refs=[{"uri": "s3://b/f.json", "content_type": "application/json"}],
        )
        assert payload["status"] == "failed"
        assert payload["diagnostic"] == "budget exceeded"
        assert payload["resume_cursor"] == "ep-001.ck1"

    def test_invalid_kind_raises(self) -> None:
        with pytest.raises(ValueError, match="invalid checkpoint payload"):
            make_checkpoint_payload(
                checkpoint_id="ep-001.bad",
                evidence_pack_id="ep-001",
                checkpoint_kind="bad_kind",
            )

    def test_invalid_status_raises(self) -> None:
        with pytest.raises(ValueError, match="invalid checkpoint payload"):
            make_checkpoint_payload(
                checkpoint_id="ep-001.bad",
                evidence_pack_id="ep-001",
                checkpoint_kind="structural_audit",
                status="unknown_status",
            )


class TestMakeVerdictPayload:
    """make_verdict_payload constructor tests."""

    def test_valid_pass(self) -> None:
        payload = make_verdict_payload(
            evidence_pack_id="ep-001",
            verdict="PASS",
        )
        assert payload["verdict"] == "PASS"
        assert payload["evidence_pack_id"] == "ep-001"
        assert payload["verdict_id"] == "ep-001.verdict"
        assert payload["failed_checkpoints"] == []

    def test_valid_fail(self) -> None:
        payload = make_verdict_payload(
            evidence_pack_id="ep-001",
            verdict="FAIL",
            verdict_id="custom-verdict",
            failed_checkpoints=["ck-1", "ck-2"],
            timestamp="2026-07-01T12:00:00Z",
        )
        assert payload["verdict"] == "FAIL"
        assert payload["verdict_id"] == "custom-verdict"
        assert payload["failed_checkpoints"] == ["ck-1", "ck-2"]
        assert payload["timestamp"] == "2026-07-01T12:00:00Z"

    def test_invalid_verdict_raises(self) -> None:
        with pytest.raises(ValueError, match="invalid verdict payload"):
            make_verdict_payload(
                evidence_pack_id="ep-001",
                verdict="MAYBE",
            )

    def test_default_timestamp(self) -> None:
        payload = make_verdict_payload(
            evidence_pack_id="ep-001",
            verdict="PASS",
        )
        assert payload["timestamp"] == "1970-01-01T00:00:00Z"


class TestMakeAttestationPayload:
    """make_attestation_payload constructor tests."""

    def test_valid_pass(self) -> None:
        payload = make_attestation_payload(
            evidence_pack_id="ep-001",
            verdict="PASS",
            checkpoint_results=[],
        )
        assert payload["verdict"] == "PASS"
        assert payload["attestation_id"] == "ep-001.attestation"

    def test_valid_with_checkpoints(self) -> None:
        ck = make_checkpoint_payload(
            checkpoint_id="ep-001.ck1",
            evidence_pack_id="ep-001",
            checkpoint_kind="structural_audit",
        )
        payload = make_attestation_payload(
            evidence_pack_id="ep-001",
            verdict="PASS",
            checkpoint_results=[ck],
            attestation_id="custom-att",
            timestamp="2026-01-01T00:00:00Z",
        )
        assert payload["attestation_id"] == "custom-att"
        assert len(payload["checkpoint_results"]) == 1

    def test_invalid_verdict_raises(self) -> None:
        with pytest.raises(ValueError, match="invalid attestation payload"):
            make_attestation_payload(
                evidence_pack_id="ep-001",
                verdict="UNKNOWN",
                checkpoint_results=[],
            )


# ── Verdict value object ────────────────────────────────────────────────────


class TestVerdictValueObject:
    """Verdict frozen dataclass tests."""

    def test_pass_verdict(self) -> None:
        v = Verdict(
            verdict="PASS",
            evidence_pack_id="ep-001",
            verdict_id="v-001",
        )
        assert v.verdict == "PASS"
        assert v.failed_checkpoints == ()

    def test_fail_verdict(self) -> None:
        v = Verdict(
            verdict="FAIL",
            evidence_pack_id="ep-001",
            verdict_id="v-001",
            failed_checkpoints=("ck-1",),
        )
        assert v.verdict == "FAIL"
        assert v.failed_checkpoints == ("ck-1",)

    def test_frozen(self) -> None:
        v = Verdict(verdict="PASS", evidence_pack_id="ep-001", verdict_id="v-001")
        with pytest.raises(Exception):
            v.verdict = "FAIL"  # type: ignore[misc]

    def test_to_payload(self) -> None:
        v = Verdict(
            verdict="FAIL",
            evidence_pack_id="ep-001",
            verdict_id="v-001",
            failed_checkpoints=("ck-1", "ck-2"),
            timestamp="2026-07-01T00:00:00Z",
        )
        payload = v.to_payload()
        assert payload["verdict"] == "FAIL"
        assert payload["failed_checkpoints"] == ["ck-1", "ck-2"]
        assert payload["timestamp"] == "2026-07-01T00:00:00Z"


# ── JSON read/write helpers ─────────────────────────────────────────────────


class TestReadJsonArtifact:
    """read_json_artifact tests."""

    def test_reads_valid_dict(self) -> None:
        root = _temp_dir()
        path = Path(root) / "data.json"
        _write_json(path, {"key": "value", "num": 42})
        result = read_json_artifact(path)
        assert result == {"key": "value", "num": 42}

    def test_reads_nested_structure(self) -> None:
        root = _temp_dir()
        path = Path(root) / "nested.json"
        _write_json(path, {"outer": {"inner": [1, 2, 3]}})
        result = read_json_artifact(path)
        assert result["outer"]["inner"] == [1, 2, 3]

    def test_non_dict_raises(self) -> None:
        root = _temp_dir()
        path = Path(root) / "list.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
        with pytest.raises(ValueError, match="did not decode to a JSON object"):
            read_json_artifact(path)

    def test_invalid_json_raises(self) -> None:
        root = _temp_dir()
        path = Path(root) / "bad.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("not json at all", encoding="utf-8")
        with pytest.raises(Exception):
            read_json_artifact(path)


class TestWriteJsonArtifact:
    """write_json_artifact tests."""

    def test_writes_and_returns_path(self) -> None:
        root = _temp_dir()
        path = Path(root) / "out.json"
        result = write_json_artifact(path, {"a": 1, "b": 2})
        assert result == path
        assert path.exists()
        written = json.loads(path.read_text(encoding="utf-8"))
        assert written == {"a": 1, "b": 2}

    def test_with_schema_validation_passes(self) -> None:
        root = _temp_dir()
        path = Path(root) / "validated.json"
        result = write_json_artifact(
            path,
            {
                "verdict_id": "v-001",
                "evidence_pack_id": "ep-001",
                "verdict": "PASS",
                "timestamp": "2026-01-01T00:00:00Z",
            },
            schema=VERDICT_SCHEMA,
        )
        assert result == path

    def test_with_schema_validation_fails(self) -> None:
        root = _temp_dir()
        path = Path(root) / "bad.json"
        with pytest.raises(ValueError, match="invalid"):
            write_json_artifact(
                path,
                {"verdict": "MAYBE"},
                schema=VERDICT_SCHEMA,
            )
        assert not path.exists()

    def test_atomic_write_prevents_partial(self) -> None:
        root = _temp_dir()
        path = Path(root) / "atomic.json"
        write_json_artifact(path, {"stable": True})
        assert path.exists()
        written = json.loads(path.read_text(encoding="utf-8"))
        assert written == {"stable": True}


# ── Verifier constants ──────────────────────────────────────────────────────


class TestVerifierArtifactConstants:
    """Four named verifier artifact constants."""

    EXPECTED = {
        "VERIFIER_ARTIFACT_EVIDENCE_PACK": "verifier.evidence_pack",
        "VERIFIER_ARTIFACT_ATTESTATION": "verifier.attestation",
        "VERIFIER_ARTIFACT_CHECKPOINT": "verifier.checkpoint",
        "VERIFIER_ARTIFACT_VERDICT": "verifier.verdict",
    }

    def test_all_four_exist_and_are_strings(self) -> None:
        for name, expected_val in self.EXPECTED.items():
            val = getattr(
                __import__("arnold.pipelines.evidence_pack.verifier", fromlist=[name]),
                name,
            )
            assert isinstance(val, str), f"{name} not a str: {type(val)}"
            assert val == expected_val, f"{name} = {val!r}, expected {expected_val!r}"


class TestValidatorKindConstants:
    """Five validator kind constants plus tuple aliases."""

    def test_five_kinds_defined(self) -> None:
        kinds = {
            VALIDATOR_KIND_STRUCTURAL_AUDIT,
            VALIDATOR_KIND_BUDGET_ENFORCEMENT,
            VALIDATOR_KIND_SUSPENSION_PROPAGATION,
            VALIDATOR_KIND_BY_REF_VALIDATION,
            VALIDATOR_KIND_HUMAN_REVIEW_GATE,
        }
        assert len(kinds) == 5

    def test_validator_kinds_tuple(self) -> None:
        assert VALIDATOR_KINDS == (
            VALIDATOR_KIND_STRUCTURAL_AUDIT,
            VALIDATOR_KIND_BUDGET_ENFORCEMENT,
            VALIDATOR_KIND_SUSPENSION_PROPAGATION,
            VALIDATOR_KIND_BY_REF_VALIDATION,
            VALIDATOR_KIND_HUMAN_REVIEW_GATE,
        )

    def test_backward_compat_alias(self) -> None:
        assert _VALIDATOR_KINDS == VALIDATOR_KINDS


class TestCheckpointStatusConstants:
    """Checkpoint status constants."""

    def test_three_statuses(self) -> None:
        assert CHECKPOINT_STATUSES == (
            CHECKPOINT_STATUS_PASSED,
            CHECKPOINT_STATUS_FAILED,
            CHECKPOINT_STATUS_SUSPENDED,
        )

    def test_values(self) -> None:
        assert CHECKPOINT_STATUS_PASSED == "passed"
        assert CHECKPOINT_STATUS_FAILED == "failed"
        assert CHECKPOINT_STATUS_SUSPENDED == "suspended"


class TestVerdictConstants:
    """Verdict value constants."""

    def test_pass_fail_only(self) -> None:
        assert VERDICT_PASS == "PASS"
        assert VERDICT_FAIL == "FAIL"
        assert VERDICTS == (VERDICT_PASS, VERDICT_FAIL)


# ── Step-helper constants ───────────────────────────────────────────────────


class TestNativePhaseOrder:
    """_NATIVE_PHASE_ORDER from steps.py."""

    def test_has_five_phases(self) -> None:
        assert len(_NATIVE_PHASE_ORDER) == 5

    def test_starts_with_ingest(self) -> None:
        assert _NATIVE_PHASE_ORDER[0] == ("ingest", "content_validators")

    def test_ends_with_halt(self) -> None:
        assert _NATIVE_PHASE_ORDER[-1] == ("emit_attestation", "halt")

    def test_phase_names_are_strings(self) -> None:
        for stage_name, next_label in _NATIVE_PHASE_ORDER:
            assert isinstance(stage_name, str)
            assert isinstance(next_label, str)


class TestArtifactKindByStage:
    """_ARTIFACT_KIND_BY_STAGE from steps.py."""

    def test_maps_all_five_stages(self) -> None:
        expected_stages = {"ingest", "content_validators", "reduce", "human_review", "emit_attestation"}
        assert set(_ARTIFACT_KIND_BY_STAGE.keys()) == expected_stages

    def test_values_are_verifier_artifacts(self) -> None:
        expected_values = {
            VERIFIER_ARTIFACT_EVIDENCE_PACK,
            VERIFIER_ARTIFACT_CHECKPOINT,
            VERIFIER_ARTIFACT_VERDICT,
            VERIFIER_ARTIFACT_ATTESTATION,
        }
        assert set(_ARTIFACT_KIND_BY_STAGE.values()) == expected_values

    def test_ingest_maps_to_evidence_pack(self) -> None:
        assert _ARTIFACT_KIND_BY_STAGE["ingest"] == VERIFIER_ARTIFACT_EVIDENCE_PACK

    def test_validators_map_to_checkpoint(self) -> None:
        assert _ARTIFACT_KIND_BY_STAGE["content_validators"] == VERIFIER_ARTIFACT_CHECKPOINT

    def test_reduce_maps_to_verdict(self) -> None:
        assert _ARTIFACT_KIND_BY_STAGE["reduce"] == VERIFIER_ARTIFACT_VERDICT

    def test_human_review_maps_to_checkpoint(self) -> None:
        assert _ARTIFACT_KIND_BY_STAGE["human_review"] == VERIFIER_ARTIFACT_CHECKPOINT

    def test_emit_maps_to_attestation(self) -> None:
        assert _ARTIFACT_KIND_BY_STAGE["emit_attestation"] == VERIFIER_ARTIFACT_ATTESTATION


# ── EvidencePackStep placeholder ────────────────────────────────────────────


class TestEvidencePackStep:
    """Placeholder EvidencePackStep tests."""

    def test_default_kind(self) -> None:
        step = EvidencePackStep(name="test", next_label="halt")
        assert step.kind == "verify"

    def test_run_returns_halt(self) -> None:
        from arnold.pipeline.types import StepContext
        step = EvidencePackStep(name="test", next_label="halt")
        ctx = StepContext(
            artifact_root=_temp_dir(),
            state={},
            inputs={},
        )
        result = step.run(ctx)
        assert result.next == "halt"
        assert result.state_patch == {}
