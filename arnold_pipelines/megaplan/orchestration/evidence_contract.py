"""Canonical evidence and transition-decision schema vocabulary.

Evidence in megaplan is reference-oriented: records should point at durable
artifacts and provider facts instead of copying large logs or inventing a
second verifier. ``completion_contract`` remains the evidence nucleus for M1;
``PhaseResult`` reports phase-boundary outcomes; ``TransitionDecision`` is only
the schema for a future routing decision record. This module deliberately does
not persist decisions, run providers, or change routing behavior.

The compatibility invariant is that all typed evidence reads deserialize
through :meth:`EvidenceRef.from_dict`, which delegates status coercion to
:func:`normalize_evidence_status`. Legacy ``fail-not-success`` remains a
blocking ``unsatisfied`` signal, with the original value preserved as
diagnostic detail.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

EVIDENCE_CONTRACT_SCHEMA = "megaplan.evidence_contract"
EVIDENCE_CONTRACT_SCHEMA_VERSION = 1

EVIDENCE_REF_SCHEMA = "megaplan.evidence_ref"
EVIDENCE_REF_SCHEMA_VERSION = 1

ARTIFACT_REF_SCHEMA = "megaplan.artifact_ref"
ARTIFACT_REF_SCHEMA_VERSION = 1

TRANSITION_DECISION_SCHEMA = "megaplan.transition_decision"
TRANSITION_DECISION_SCHEMA_VERSION = 1


from arnold.pipeline.types import EvidenceStatus, TrustClass

LEGACY_EVIDENCE_STATUS_ALIASES: dict[str, EvidenceStatus] = {
    "not_evaluated": EvidenceStatus.unknown,
    "fail-not-success": EvidenceStatus.unsatisfied,
}

CANONICAL_EVIDENCE_STATUSES: frozenset[str] = frozenset(status.value for status in EvidenceStatus)


@dataclass(frozen=True)
class EvidenceStatusNormalization:
    """Result of status normalization with compatibility diagnostics."""

    status: EvidenceStatus
    diagnostics: dict[str, Any] = field(default_factory=dict)


def normalize_evidence_status(value: Any) -> EvidenceStatusNormalization:
    """Normalize current and legacy evidence statuses.

    Missing, non-string, and unknown values normalize to ``unknown``. Legacy
    aliases normalize to canonical statuses and preserve the raw value in
    diagnostics so typed reads can surface compatibility facts without treating
    old artifacts as parse failures.
    """

    if isinstance(value, EvidenceStatus):
        return EvidenceStatusNormalization(value)

    if value is None:
        return EvidenceStatusNormalization(
            EvidenceStatus.unknown,
            {"status_normalization": "missing", "canonical_status": EvidenceStatus.unknown.value},
        )

    if not isinstance(value, str):
        return EvidenceStatusNormalization(
            EvidenceStatus.unknown,
            {
                "status_normalization": "invalid_type",
                "legacy_status": value,
                "canonical_status": EvidenceStatus.unknown.value,
            },
        )

    try:
        return EvidenceStatusNormalization(EvidenceStatus(value))
    except ValueError:
        pass

    if value in LEGACY_EVIDENCE_STATUS_ALIASES:
        status = LEGACY_EVIDENCE_STATUS_ALIASES[value]
        return EvidenceStatusNormalization(
            status,
            {
                "status_normalization": "legacy_alias",
                "legacy_status": value,
                "canonical_status": status.value,
            },
        )

    return EvidenceStatusNormalization(
        EvidenceStatus.unknown,
        {
            "status_normalization": "unknown",
            "legacy_status": value,
            "canonical_status": EvidenceStatus.unknown.value,
        },
    )


@dataclass(frozen=True)
class ArtifactRef:
    """Reference to an artifact that backs an evidence or routing record."""

    path: str
    sha256: str | None = None
    artifact_type: str | None = None
    schema: str | None = None
    schema_version: int | None = None
    uri: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "schema_version": self.schema_version,
            "path": self.path,
            "sha256": self.sha256,
            "artifact_type": self.artifact_type,
            "uri": self.uri,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ArtifactRef":
        return cls(
            path=str(d.get("path", "")),
            sha256=_optional_str(d.get("sha256")),
            artifact_type=_optional_str(d.get("artifact_type")),
            schema=_optional_str(d.get("schema")),
            schema_version=_optional_int(d.get("schema_version")),
            uri=_optional_str(d.get("uri")),
        )


@dataclass(frozen=True)
class EvidenceRef:
    """One evidence class's observation for a subject.

    The first four fields preserve the old constructor contract:
    ``EvidenceRef(kind, status, summary, details)``. New provenance fields are
    optional and default to absent.
    """

    kind: str
    status: EvidenceStatus
    summary: str
    details: dict[str, Any] = field(default_factory=dict)
    trust_class: TrustClass | None = None
    provider: str | None = None
    provider_version: str | None = None
    artifact: ArtifactRef | None = None
    artifacts: tuple[ArtifactRef, ...] = ()
    source: str | None = None
    subject: str | None = None
    observed_at: str | None = None
    code_hash: str | None = None
    schema: str = EVIDENCE_REF_SCHEMA
    schema_version: int = EVIDENCE_REF_SCHEMA_VERSION
    evidence_contract_version: int = EVIDENCE_CONTRACT_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "schema": self.schema,
            "schema_version": self.schema_version,
            "evidence_contract_version": self.evidence_contract_version,
            "kind": self.kind,
            "status": self.status.value,
            "summary": self.summary,
            "details": dict(self.details),
        }
        if self.trust_class is not None:
            d["trust_class"] = self.trust_class.value
        for key in (
            "provider",
            "provider_version",
            "source",
            "subject",
            "observed_at",
            "code_hash",
        ):
            value = getattr(self, key)
            if value is not None:
                d[key] = value
        if self.artifact is not None:
            d["artifact"] = self.artifact.to_dict()
        if self.artifacts:
            d["artifacts"] = [artifact.to_dict() for artifact in self.artifacts]
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "EvidenceRef":
        normalized = normalize_evidence_status(d.get("status"))
        details = d.get("details")
        clean_details = dict(details) if isinstance(details, dict) else {}
        if normalized.diagnostics:
            clean_details.setdefault("diagnostics", {}).update(normalized.diagnostics)

        artifacts = _artifact_refs_from_value(d.get("artifacts"))
        artifact = _artifact_ref_from_value(d.get("artifact"))
        if artifact is None and artifacts:
            artifact = artifacts[0]

        return cls(
            kind=str(d.get("kind", "?")),
            status=normalized.status,
            summary=str(d.get("summary", "")),
            details=clean_details,
            trust_class=_trust_class_from_value(d.get("trust_class")),
            provider=_optional_str(d.get("provider")),
            provider_version=_optional_str(d.get("provider_version")),
            artifact=artifact,
            artifacts=artifacts,
            source=_optional_str(d.get("source")),
            subject=_optional_str(d.get("subject")),
            observed_at=_optional_str(d.get("observed_at")),
            code_hash=_optional_str(d.get("code_hash")),
            schema=str(d.get("schema", EVIDENCE_REF_SCHEMA)),
            schema_version=_optional_int(d.get("schema_version")) or 0,
            evidence_contract_version=_optional_int(d.get("evidence_contract_version")) or 0,
        )


@dataclass(frozen=True)
class TransitionDecision:
    """Schema-only routing decision record.

    M1 defines this durable shape without adding decision persistence or
    changing transition routing.

    S2 extends this with boundary evidence provenance: ``boundary_id``,
    ``checked_evidence_refs``, and ``authority_record_refs`` let
    review-to-done decisions carry durable boundary contract and authority
    references.  All three fields are optional so legacy serialized
    decisions without them still deserialize cleanly.
    """

    decision_id: str
    subject: str
    from_state: str | None
    to_state: str
    action: str
    status: str
    evidence: tuple[EvidenceRef, ...] = ()
    would_block_reasons: tuple[str, ...] = ()
    invocation_id: str | None = None
    phase: str | None = None
    iteration: int | None = None
    base_sha: str | None = None
    head_sha: str | None = None
    code_hash: str | None = None
    routing_provider: str | None = None
    routing_provenance: dict[str, Any] = field(default_factory=dict)
    boundary_id: str | None = None
    checked_evidence_refs: tuple[str, ...] = ()
    authority_record_refs: tuple[str, ...] = ()
    schema: str = TRANSITION_DECISION_SCHEMA
    schema_version: int = TRANSITION_DECISION_SCHEMA_VERSION
    evidence_contract_version: int = EVIDENCE_CONTRACT_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema": self.schema,
            "schema_version": self.schema_version,
            "evidence_contract_version": self.evidence_contract_version,
            "decision_id": self.decision_id,
            "subject": self.subject,
            "from_state": self.from_state,
            "to_state": self.to_state,
            "action": self.action,
            "status": self.status,
            "evidence": [ref.to_dict() for ref in self.evidence],
            "would_block_reasons": list(self.would_block_reasons),
            "invocation_id": self.invocation_id,
            "phase": self.phase,
            "iteration": self.iteration,
            "base_sha": self.base_sha,
            "head_sha": self.head_sha,
            "code_hash": self.code_hash,
            "routing_provider": self.routing_provider,
            "routing_provenance": dict(self.routing_provenance),
        }
        if self.boundary_id is not None:
            payload["boundary_id"] = self.boundary_id
        if self.checked_evidence_refs:
            payload["checked_evidence_refs"] = list(self.checked_evidence_refs)
        if self.authority_record_refs:
            payload["authority_record_refs"] = list(self.authority_record_refs)
        return payload

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "TransitionDecision":
        evidence = d.get("evidence")
        reasons = d.get("would_block_reasons")
        checked = d.get("checked_evidence_refs")
        authority = d.get("authority_record_refs")
        return cls(
            decision_id=str(d.get("decision_id", "")),
            subject=str(d.get("subject", "")),
            from_state=_optional_str(d.get("from_state")),
            to_state=str(d.get("to_state", "")),
            action=str(d.get("action", "")),
            status=str(d.get("status", "")),
            evidence=tuple(
                EvidenceRef.from_dict(ref) for ref in evidence if isinstance(ref, dict)
            )
            if isinstance(evidence, list)
            else (),
            would_block_reasons=tuple(str(reason) for reason in reasons)
            if isinstance(reasons, list)
            else (),
            invocation_id=_optional_str(d.get("invocation_id")),
            phase=_optional_str(d.get("phase")),
            iteration=_optional_int(d.get("iteration")),
            base_sha=_optional_str(d.get("base_sha")),
            head_sha=_optional_str(d.get("head_sha")),
            code_hash=_optional_str(d.get("code_hash")),
            routing_provider=_optional_str(d.get("routing_provider")),
            routing_provenance=dict(d.get("routing_provenance"))
            if isinstance(d.get("routing_provenance"), dict)
            else {},
            boundary_id=_optional_str(d.get("boundary_id")),
            checked_evidence_refs=tuple(str(ref) for ref in checked)
            if isinstance(checked, list)
            else (),
            authority_record_refs=tuple(str(ref) for ref in authority)
            if isinstance(authority, list)
            else (),
            schema=str(d.get("schema", TRANSITION_DECISION_SCHEMA)),
            schema_version=_optional_int(d.get("schema_version")) or 0,
            evidence_contract_version=_optional_int(d.get("evidence_contract_version")) or 0,
        )


def _artifact_ref_from_value(value: Any) -> ArtifactRef | None:
    if isinstance(value, ArtifactRef):
        return value
    if isinstance(value, dict):
        return ArtifactRef.from_dict(value)
    return None


def _artifact_refs_from_value(value: Any) -> tuple[ArtifactRef, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(ref for item in value if (ref := _artifact_ref_from_value(item)) is not None)


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _optional_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    return None


def _trust_class_from_value(value: Any) -> TrustClass | None:
    if isinstance(value, TrustClass):
        return value
    if not isinstance(value, str):
        return None
    try:
        return TrustClass(value)
    except ValueError:
        return None
