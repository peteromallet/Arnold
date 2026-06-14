"""Evidence-pack verifier — model-less schema, constants, and helpers.

This module defines the schemas, named artifact constants, and deterministic
payload/helper functions for the M8 evidence-pack verifier pipeline.  The
verifier is *model-less*: it never dispatches to an LLM.  Instead it
validates persisted JSON artifacts against stable contracts.

Design constraints (from M2 expressibility guardrail):

* No megaplan labels, handlers, or registry coupling.
* No mutable globals / executor-local state.
* Fail-closed for unknown adapter kinds.
* Determinisitic payload helpers only (no StepResult-after-run reliance).
* Use ``EvidenceArtifactRef`` for by-ref multi-content artifacts.
* Collection fan-out via ``Port(cardinality='collection')`` + ``PortRef``.
* Typed verdicts in ``ContractResult``.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Mapping

from arnold.pipeline import (
    CONTRACT_RESULT_SCHEMA_VERSION,
    ContractResult,
    ContractStatus,
    EvidenceArtifactRef,
    Freshness,
    Port,
    PortRef,
    Provenance,
    Suspension,
)

# ---------------------------------------------------------------------------
# Named artifact constants
# ---------------------------------------------------------------------------

VERIFIER_ARTIFACT_EVIDENCE_PACK = "verifier.evidence_pack"
"""Primary evidence-pack JSON artifact (payload of the verification pipeline)."""

VERIFIER_ARTIFACT_ATTESTATION = "verifier.attestation"
"""Signed attestation produced after a successful verification pass."""

VERIFIER_ARTIFACT_CHECKPOINT = "verifier.checkpoint"
"""Checkpoint artifact written before any human-gate suspension."""

VERIFIER_ARTIFACT_VERDICT = "verifier.verdict"
"""Final binary verdict (PASS/FAIL) written as a standalone JSON artifact."""

# ---------------------------------------------------------------------------
# Verifier payload schemas (JSON Schema subset — model-less)
# ---------------------------------------------------------------------------

EVIDENCE_PACK_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": [
        "evidence_pack_id",
        "source_ticket",
        "checkpoints",
    ],
    "additionalProperties": False,
    "properties": {
        "evidence_pack_id": {"type": "string"},
        "source_ticket": {"type": "string"},
        "checkpoints": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["checkpoint_id", "status", "artifact_refs"],
                "additionalProperties": False,
                "properties": {
                    "checkpoint_id": {"type": "string"},
                    "status": {
                        "type": "string",
                        "enum": ["passed", "failed", "skipped", "suspended"],
                    },
                    "diagnostic": {"type": "string"},
                    "artifact_refs": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["uri", "content_type"],
                            "additionalProperties": False,
                            "properties": {
                                "uri": {"type": "string"},
                                "content_type": {"type": "string"},
                                "name": {"type": "string"},
                                "digest": {"type": "string"},
                                "size_bytes": {"type": "integer"},
                            },
                        },
                    },
                },
            },
        },
    },
}

ATTESTATION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": [
        "attestation_id",
        "evidence_pack_id",
        "verdict",
        "verifier_version",
    ],
    "additionalProperties": False,
    "properties": {
        "attestation_id": {"type": "string"},
        "evidence_pack_id": {"type": "string"},
        "verdict": {"type": "string", "enum": ["PASS", "FAIL"]},
        "verifier_version": {"type": "string"},
        "checkpoint_results": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["checkpoint_id", "status"],
                "additionalProperties": False,
                "properties": {
                    "checkpoint_id": {"type": "string"},
                    "status": {
                        "type": "string",
                        "enum": ["passed", "failed", "skipped", "suspended"],
                    },
                    "diagnostic": {"type": "string"},
                },
            },
        },
        "timestamp": {"type": "string"},
    },
}

CHECKPOINT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": [
        "checkpoint_id",
        "evidence_pack_id",
        "status",
        "checkpoint_kind",
    ],
    "additionalProperties": False,
    "properties": {
        "checkpoint_id": {"type": "string"},
        "evidence_pack_id": {"type": "string"},
        "status": {
            "type": "string",
            "enum": ["passed", "failed", "skipped", "suspended"],
        },
        "checkpoint_kind": {
            "type": "string",
            "enum": [
                "structural_audit",
                "budget_enforcement",
                "suspension_propagation",
                "by_ref_validation",
                "human_review_gate",
                "emission",
            ],
        },
        "diagnostic": {"type": "string"},
        "resume_cursor": {"type": "string"},
    },
}

VERDICT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": [
        "verdict_id",
        "evidence_pack_id",
        "verdict",
    ],
    "additionalProperties": False,
    "properties": {
        "verdict_id": {"type": "string"},
        "evidence_pack_id": {"type": "string"},
        "verdict": {"type": "string", "enum": ["PASS", "FAIL"]},
        "failed_checkpoints": {
            "type": "array",
            "items": {"type": "string"},
        },
        "timestamp": {"type": "string"},
    },
}

# ---------------------------------------------------------------------------
# Verdict discriminant
# ---------------------------------------------------------------------------


class Verdict(str, Enum):
    """Binary pass/fail verdict for the evidence-pack verifier."""

    PASS = "PASS"
    FAIL = "FAIL"


# ---------------------------------------------------------------------------
# Deterministic payload helpers
# ---------------------------------------------------------------------------


def make_evidence_pack_payload(
    *,
    evidence_pack_id: str,
    source_ticket: str,
    checkpoints: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a deterministic evidence-pack payload.

    This is a pure data constructor — no side effects, no registry lookups,
    no model dispatch.  The caller is responsible for validation.
    """
    return {
        "evidence_pack_id": evidence_pack_id,
        "source_ticket": source_ticket,
        "checkpoints": list(checkpoints or []),
    }


def make_checkpoint_payload(
    *,
    checkpoint_id: str,
    evidence_pack_id: str,
    checkpoint_kind: str,
    status: str = "passed",
    diagnostic: str | None = None,
    resume_cursor: str | None = None,
) -> dict[str, Any]:
    """Build a deterministic checkpoint payload."""
    payload: dict[str, Any] = {
        "checkpoint_id": checkpoint_id,
        "evidence_pack_id": evidence_pack_id,
        "status": status,
        "checkpoint_kind": checkpoint_kind,
    }
    if diagnostic is not None:
        payload["diagnostic"] = diagnostic
    if resume_cursor is not None:
        payload["resume_cursor"] = resume_cursor
    return payload


def make_attestation_payload(
    *,
    attestation_id: str,
    evidence_pack_id: str,
    verdict: Verdict,
    verifier_version: str = "m8/v1",
    checkpoint_results: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a deterministic attestation payload."""
    from datetime import datetime, timezone

    return {
        "attestation_id": attestation_id,
        "evidence_pack_id": evidence_pack_id,
        "verdict": verdict.value,
        "verifier_version": verifier_version,
        "checkpoint_results": list(checkpoint_results or []),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def make_verdict_payload(
    *,
    verdict_id: str,
    evidence_pack_id: str,
    verdict: Verdict,
    failed_checkpoints: list[str] | None = None,
) -> dict[str, Any]:
    """Build a deterministic verdict payload."""
    from datetime import datetime, timezone

    return {
        "verdict_id": verdict_id,
        "evidence_pack_id": evidence_pack_id,
        "verdict": verdict.value,
        "failed_checkpoints": list(failed_checkpoints or []),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Named artifact ref helpers
# ---------------------------------------------------------------------------


def evidence_artifact_ref(
    *,
    uri: str,
    content_type: str,
    name: str | None = None,
    digest: str | None = None,
    size_bytes: int | None = None,
) -> EvidenceArtifactRef:
    """Build a deterministic ``EvidenceArtifactRef`` for by-ref artifacts."""
    return EvidenceArtifactRef(
        uri=uri,
        content_type=content_type,
        name=name,
        digest=digest,
        size_bytes=size_bytes,
    )


def make_contract_result(
    *,
    status: ContractStatus = ContractStatus.COMPLETED,
    payload: Mapping[str, Any] | None = None,
    suspension: Suspension | None = None,
    evidence_refs: tuple[EvidenceArtifactRef, ...] = (),
    authority_level: str = "verified",
) -> ContractResult:
    """Build a deterministic ``ContractResult`` for the evidence-pack verifier.

    This is intentionally model-less: no megaplan labels, no registry
    coupling, no mutable state.  The caller owns the schema validation.
    """
    return ContractResult(
        payload=dict(payload or {}),
        status=status,
        schema_version=CONTRACT_RESULT_SCHEMA_VERSION,
        suspension=suspension,
        authority_level=authority_level,
        evidence_refs=evidence_refs,
        provenance=Provenance(
            sources=("evidence_pack_verifier",),
            generator="arnold.pipelines.evidence_pack.verifier",
        ),
        freshness=Freshness(),
    )


# ---------------------------------------------------------------------------
# Port construction helpers (collection fan-out primitives)
# ---------------------------------------------------------------------------


def singleton_port(name: str, content_type: str) -> Port:
    """Construct a singleton output port."""
    return Port(name=name, content_type=content_type, cardinality="singleton")


def collection_port(name: str, content_type: str) -> Port:
    """Construct a collection output port for fan-out patterns."""
    return Port(name=name, content_type=content_type, cardinality="collection")


def port_ref(name: str, content_type: str) -> PortRef:
    """Construct a port reference for consumption."""
    return PortRef(port_name=name, content_type=content_type)


# ---------------------------------------------------------------------------
# Content-hash helpers
# ---------------------------------------------------------------------------


def hash_payload_dict(payload: dict[str, Any]) -> str:
    """Deterministic SHA-256 hash of a JSON-serializable payload dict."""
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def hash_file_content(path: Path) -> str:
    """Deterministic SHA-256 hash of a file's binary content."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()
