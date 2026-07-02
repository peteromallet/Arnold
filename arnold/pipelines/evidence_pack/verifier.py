"""Evidence-pack artifact constants, schemas, and JSON helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from arnold.pipeline.contract_validation import validate_payload_against_schema
from arnold.runtime.state_persistence import atomic_write_json


VERIFIER_ARTIFACT_EVIDENCE_PACK = "verifier.evidence_pack"
VERIFIER_ARTIFACT_ATTESTATION = "verifier.attestation"
VERIFIER_ARTIFACT_CHECKPOINT = "verifier.checkpoint"
VERIFIER_ARTIFACT_VERDICT = "verifier.verdict"

VALIDATOR_KIND_STRUCTURAL_AUDIT = "structural_audit"
VALIDATOR_KIND_BUDGET_ENFORCEMENT = "budget_enforcement"
VALIDATOR_KIND_SUSPENSION_PROPAGATION = "suspension_propagation"
VALIDATOR_KIND_BY_REF_VALIDATION = "by_ref_validation"
VALIDATOR_KIND_HUMAN_REVIEW_GATE = "human_review_gate"

VALIDATOR_KINDS = (
    VALIDATOR_KIND_STRUCTURAL_AUDIT,
    VALIDATOR_KIND_BUDGET_ENFORCEMENT,
    VALIDATOR_KIND_SUSPENSION_PROPAGATION,
    VALIDATOR_KIND_BY_REF_VALIDATION,
    VALIDATOR_KIND_HUMAN_REVIEW_GATE,
)

# Backward-compatible alias referenced by archived docs and tests.
_VALIDATOR_KINDS = VALIDATOR_KINDS

CHECKPOINT_STATUS_PASSED = "passed"
CHECKPOINT_STATUS_FAILED = "failed"
CHECKPOINT_STATUS_SUSPENDED = "suspended"
CHECKPOINT_STATUSES = (
    CHECKPOINT_STATUS_PASSED,
    CHECKPOINT_STATUS_FAILED,
    CHECKPOINT_STATUS_SUSPENDED,
)

VERDICT_PASS = "PASS"
VERDICT_FAIL = "FAIL"
VERDICTS = (VERDICT_PASS, VERDICT_FAIL)

_JSON_SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"

_ARTIFACT_REF_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "uri": {"type": "string"},
        "content_type": {"type": "string"},
        "name": {"type": "string"},
    },
    "required": ["uri", "content_type"],
}

_EVIDENCE_PACK_CHECKPOINT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "checkpoint_id": {"type": "string"},
        "status": {"type": "string", "enum": list(CHECKPOINT_STATUSES)},
        "artifact_refs": {
            "type": "array",
            "items": _ARTIFACT_REF_SCHEMA,
        },
    },
    "required": ["checkpoint_id", "status", "artifact_refs"],
}

CHECKPOINT_SCHEMA: dict[str, Any] = {
    "$schema": _JSON_SCHEMA_DIALECT,
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "checkpoint_id": {"type": "string"},
        "evidence_pack_id": {"type": "string"},
        "checkpoint_kind": {"type": "string", "enum": list(VALIDATOR_KINDS)},
        "status": {"type": "string", "enum": list(CHECKPOINT_STATUSES)},
        "diagnostic": {"type": "string"},
        "resume_cursor": {"type": "string"},
        "artifact_refs": {
            "type": "array",
            "items": _ARTIFACT_REF_SCHEMA,
        },
    },
    "required": [
        "checkpoint_id",
        "evidence_pack_id",
        "checkpoint_kind",
        "status",
        "artifact_refs",
    ],
}

EVIDENCE_PACK_SCHEMA: dict[str, Any] = {
    "$schema": _JSON_SCHEMA_DIALECT,
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "evidence_pack_id": {"type": "string"},
        "source_ticket": {"type": "string"},
        "checkpoints": {
            "type": "array",
            "items": _EVIDENCE_PACK_CHECKPOINT_SCHEMA,
        },
    },
    "required": ["evidence_pack_id", "source_ticket", "checkpoints"],
}

VERDICT_SCHEMA: dict[str, Any] = {
    "$schema": _JSON_SCHEMA_DIALECT,
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "verdict_id": {"type": "string"},
        "evidence_pack_id": {"type": "string"},
        "verdict": {"type": "string", "enum": list(VERDICTS)},
        "failed_checkpoints": {
            "type": "array",
            "items": {"type": "string"},
        },
        "timestamp": {"type": "string"},
    },
    "required": ["verdict_id", "evidence_pack_id", "verdict"],
}

ATTESTATION_SCHEMA: dict[str, Any] = {
    "$schema": _JSON_SCHEMA_DIALECT,
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "attestation_id": {"type": "string"},
        "evidence_pack_id": {"type": "string"},
        "verdict": {"type": "string", "enum": list(VERDICTS)},
        "timestamp": {"type": "string"},
        "checkpoint_results": {
            "type": "array",
            "items": CHECKPOINT_SCHEMA,
        },
    },
    "required": [
        "attestation_id",
        "evidence_pack_id",
        "verdict",
        "timestamp",
        "checkpoint_results",
    ],
}


def _validate_payload(
    payload: Mapping[str, Any],
    *,
    schema: Mapping[str, Any],
    name: str,
) -> dict[str, Any]:
    result = validate_payload_against_schema(payload, schema)
    if result.ok:
        return dict(payload)
    diagnostics = "; ".join(
        f"{item.code} at {item.payload_pointer or '/'}: {item.message}"
        for item in result.diagnostics
    )
    raise ValueError(f"invalid {name} payload: {diagnostics}")


def _stringify_timestamp(timestamp: str | None) -> str:
    return timestamp or "1970-01-01T00:00:00Z"


@dataclass(frozen=True)
class Verdict:
    """Structured verdict value object used by reduce/attestation steps."""

    verdict: str
    evidence_pack_id: str
    verdict_id: str
    failed_checkpoints: tuple[str, ...] = ()
    timestamp: str = "1970-01-01T00:00:00Z"

    def to_payload(self) -> dict[str, Any]:
        return make_verdict_payload(
            evidence_pack_id=self.evidence_pack_id,
            verdict=self.verdict,
            verdict_id=self.verdict_id,
            failed_checkpoints=list(self.failed_checkpoints),
            timestamp=self.timestamp,
        )


def make_evidence_pack_payload(
    evidence_pack_id: str,
    source_ticket: str,
    checkpoints: list[dict[str, Any]],
) -> dict[str, Any]:
    normalized_checkpoints = [
        {
            "checkpoint_id": checkpoint["checkpoint_id"],
            "status": checkpoint["status"],
            "artifact_refs": list(checkpoint.get("artifact_refs") or []),
        }
        for checkpoint in checkpoints
    ]
    return _validate_payload(
        {
            "evidence_pack_id": evidence_pack_id,
            "source_ticket": source_ticket,
            "checkpoints": normalized_checkpoints,
        },
        schema=EVIDENCE_PACK_SCHEMA,
        name="evidence_pack",
    )


def make_checkpoint_payload(
    checkpoint_id: str,
    evidence_pack_id: str,
    checkpoint_kind: str,
    status: str = CHECKPOINT_STATUS_PASSED,
    diagnostic: str | None = None,
    resume_cursor: str | None = None,
    artifact_refs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "checkpoint_id": checkpoint_id,
        "evidence_pack_id": evidence_pack_id,
        "checkpoint_kind": checkpoint_kind,
        "status": status,
        "artifact_refs": list(artifact_refs or []),
    }
    if diagnostic is not None:
        payload["diagnostic"] = diagnostic
    if resume_cursor is not None:
        payload["resume_cursor"] = resume_cursor
    return _validate_payload(
        payload,
        schema=CHECKPOINT_SCHEMA,
        name="checkpoint",
    )


def make_verdict_payload(
    evidence_pack_id: str,
    verdict: str,
    *,
    verdict_id: str | None = None,
    failed_checkpoints: list[str] | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    return _validate_payload(
        {
            "verdict_id": verdict_id or f"{evidence_pack_id}.verdict",
            "evidence_pack_id": evidence_pack_id,
            "verdict": verdict,
            "failed_checkpoints": list(failed_checkpoints or []),
            "timestamp": _stringify_timestamp(timestamp),
        },
        schema=VERDICT_SCHEMA,
        name="verdict",
    )


def make_attestation_payload(
    evidence_pack_id: str,
    verdict: str,
    checkpoint_results: list[dict[str, Any]],
    *,
    attestation_id: str | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    return _validate_payload(
        {
            "attestation_id": attestation_id or f"{evidence_pack_id}.attestation",
            "evidence_pack_id": evidence_pack_id,
            "verdict": verdict,
            "timestamp": _stringify_timestamp(timestamp),
            "checkpoint_results": list(checkpoint_results),
        },
        schema=ATTESTATION_SCHEMA,
        name="attestation",
    )


def read_json_artifact(path: str | Path) -> dict[str, Any]:
    artifact_path = Path(path)
    data = json.loads(artifact_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"artifact at {artifact_path} did not decode to a JSON object")
    return data


def write_json_artifact(
    path: str | Path,
    payload: Mapping[str, Any],
    *,
    schema: Mapping[str, Any] | None = None,
) -> Path:
    artifact_path = Path(path)
    data = dict(payload)
    if schema is not None:
        _validate_payload(data, schema=schema, name=str(artifact_path.name))
    atomic_write_json(artifact_path, data)
    return artifact_path


__all__ = [
    "ATTESTATION_SCHEMA",
    "CHECKPOINT_SCHEMA",
    "CHECKPOINT_STATUSES",
    "CHECKPOINT_STATUS_FAILED",
    "CHECKPOINT_STATUS_PASSED",
    "CHECKPOINT_STATUS_SUSPENDED",
    "EVIDENCE_PACK_SCHEMA",
    "VALIDATOR_KIND_BUDGET_ENFORCEMENT",
    "VALIDATOR_KIND_BY_REF_VALIDATION",
    "VALIDATOR_KIND_HUMAN_REVIEW_GATE",
    "VALIDATOR_KIND_STRUCTURAL_AUDIT",
    "VALIDATOR_KIND_SUSPENSION_PROPAGATION",
    "VALIDATOR_KINDS",
    "VERDICT_FAIL",
    "VERDICT_PASS",
    "VERDICT_SCHEMA",
    "VERDICTS",
    "VERIFIER_ARTIFACT_ATTESTATION",
    "VERIFIER_ARTIFACT_CHECKPOINT",
    "VERIFIER_ARTIFACT_EVIDENCE_PACK",
    "VERIFIER_ARTIFACT_VERDICT",
    "Verdict",
    "_VALIDATOR_KINDS",
    "make_attestation_payload",
    "make_checkpoint_payload",
    "make_evidence_pack_payload",
    "make_verdict_payload",
    "read_json_artifact",
    "write_json_artifact",
]
