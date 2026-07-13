"""Pure, deterministic projection of generic run-authority records."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from types import MappingProxyType
from typing import Any, Iterable, Mapping, TypeAlias

from .contracts import (
    CapabilityGrant,
    Claim,
    Contract,
    ContractError,
    CoordinatorFence,
    Decision,
    EvidenceEnvelope,
    IdempotencyKey,
    ObservationEnvelope,
    QuarantineRecord,
    SubjectAttempt,
    canonical_json,
)


AuthorityInput: TypeAlias = (
    EvidenceEnvelope
    | ObservationEnvelope
    | CoordinatorFence
    | CapabilityGrant
    | SubjectAttempt
    | IdempotencyKey
    | Claim
    | Decision
    | QuarantineRecord
)


@dataclass(frozen=True, order=True)
class AuthorityDiagnostic:
    """Stable explanation for a record that did not become authority."""

    code: str
    record_type: str
    record_id: str
    reason: str
    source: str

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "record_type": self.record_type,
            "record_id": self.record_id,
            "reason": self.reason,
            "source": self.source,
        }


def _record_sort_key(record: Contract) -> tuple[str, str]:
    return record.contract_type, record.to_json()


def _records_dict(records: tuple[Contract, ...]) -> list[dict[str, Any]]:
    return [record.to_dict() for record in records]


@dataclass(frozen=True)
class RunAuthorityView:
    """Immutable result of reducing one run revision's supplied records."""

    schema_version: int
    run_id: str
    run_revision: str
    journal_cursor: int
    evidence_set_digest: str
    evidence: tuple[EvidenceEnvelope, ...]
    observations: tuple[ObservationEnvelope, ...]
    fences: tuple[CoordinatorFence, ...]
    grants: tuple[CapabilityGrant, ...]
    attempts: tuple[SubjectAttempt, ...]
    claims: tuple[Claim, ...]
    decisions: tuple[Decision, ...]
    quarantines: tuple[QuarantineRecord, ...]
    diagnostics: tuple[AuthorityDiagnostic, ...]
    view_hash: str

    def _payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "run_revision": self.run_revision,
            "journal_cursor": self.journal_cursor,
            "evidence_set_digest": self.evidence_set_digest,
            "evidence": _records_dict(self.evidence),
            "observations": _records_dict(self.observations),
            "fences": _records_dict(self.fences),
            "grants": _records_dict(self.grants),
            "attempts": _records_dict(self.attempts),
            "claims": _records_dict(self.claims),
            "decisions": _records_dict(self.decisions),
            "quarantines": _records_dict(self.quarantines),
            "diagnostics": [item.to_dict() for item in self.diagnostics],
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self._payload(), "view_hash": self.view_hash}

    def to_json(self) -> str:
        return canonical_json(self.to_dict())


def _identity(record: AuthorityInput) -> tuple[str, str]:
    if isinstance(record, EvidenceEnvelope):
        return record.contract_type, record.evidence_id
    if isinstance(record, ObservationEnvelope):
        return record.contract_type, record.observation_id
    if isinstance(record, CoordinatorFence):
        key = f"{record.run_id}:{record.run_revision}:{record.coordinator_attempt_id}:{record.token}"
        return record.contract_type, key
    if isinstance(record, CapabilityGrant):
        return record.contract_type, record.grant_id
    if isinstance(record, SubjectAttempt):
        return record.contract_type, record.attempt_id
    if isinstance(record, IdempotencyKey):
        return record.contract_type, record.value
    if isinstance(record, Claim):
        return record.contract_type, record.claim_id
    if isinstance(record, Decision):
        return record.contract_type, record.decision_id
    if isinstance(record, QuarantineRecord):
        return record.contract_type, record.quarantine_id
    raise ContractError(f"unsupported reducer input {type(record).__name__}")


def _source(record: AuthorityInput) -> str:
    if isinstance(record, (EvidenceEnvelope, ObservationEnvelope, QuarantineRecord)):
        return record.source
    record_type, record_id = _identity(record)
    return f"contract://{record_type}/{record_id}"


def _deduplicate(
    records: tuple[AuthorityInput, ...],
) -> tuple[tuple[AuthorityInput, ...], tuple[AuthorityDiagnostic, ...]]:
    grouped: dict[tuple[str, str], dict[str, AuthorityInput]] = {}
    for record in records:
        key = _identity(record)
        grouped.setdefault(key, {})[record.to_json()] = record

    unique: list[AuthorityInput] = []
    diagnostics: list[AuthorityDiagnostic] = []
    for (record_type, record_id), variants in sorted(grouped.items()):
        if len(variants) == 1:
            unique.append(next(iter(variants.values())))
            continue
        sources = sorted({_source(record) for record in variants.values()})
        diagnostics.append(AuthorityDiagnostic(
            code="conflicting_duplicate_key",
            record_type=record_type,
            record_id=record_id,
            reason=f"{len(variants)} distinct payloads share one record identity",
            source=",".join(sources),
        ))
    return tuple(sorted(unique, key=_record_sort_key)), tuple(sorted(diagnostics))


def _generated_quarantine(
    record: Claim | Decision,
    *,
    run_id: str,
    run_revision: str,
    reason: str,
) -> QuarantineRecord:
    material = canonical_json({
        "record_type": record.contract_type,
        "record_id": record.claim_id if isinstance(record, Claim) else record.decision_id,
        "record_digest": record.digest(),
        "reason": reason,
        "run_id": run_id,
        "run_revision": run_revision,
    })
    record_id = record.claim_id if isinstance(record, Claim) else record.decision_id
    return QuarantineRecord(
        quarantine_id=f"reducer-{hashlib.sha256(material.encode('utf-8')).hexdigest()[:24]}",
        run_id=run_id,
        run_revision=run_revision,
        record_type=record.contract_type,
        record_id=record_id,
        reason=reason,
        source=_source(record),
        evidence_ids=record.evidence_ids,
        payload={"record_digest": record.digest()},
    )


def _claim_reason(
    claim: Claim,
    *,
    run_id: str,
    run_revision: str,
    evidence: Mapping[str, EvidenceEnvelope],
    fences: Mapping[tuple[str, int], CoordinatorFence],
    grants: Mapping[str, CapabilityGrant],
    attempts: Mapping[str, SubjectAttempt],
    idempotency: Mapping[str, IdempotencyKey],
) -> str | None:
    if claim.run_id != run_id:
        return "run_identity_mismatch"
    if claim.run_revision != run_revision:
        return "missing_matching_revision"
    attempt = attempts.get(claim.attempt_id)
    if attempt is None:
        return "missing_matching_attempt"
    grant = grants.get(claim.grant_id)
    if grant is None:
        return "missing_matching_grant"
    fence = fences.get((claim.coordinator_attempt_id, claim.fence_token))
    if fence is None:
        return "missing_matching_fence"
    key = idempotency.get(claim.idempotency_key)
    if key is None or key.payload_hash != claim.payload_hash:
        return "missing_matching_idempotency_identity"
    missing_evidence = [item for item in claim.evidence_ids if item not in evidence]
    missing_evidence.extend(item for item in grant.evidence_ids if item not in evidence)
    if missing_evidence:
        return "missing_matching_evidence"

    common = (attempt, grant, fence)
    if any(item.run_id != run_id for item in common):
        return "run_identity_mismatch"
    if any(item.run_revision != run_revision for item in common):
        return "missing_matching_revision"
    if (
        attempt.subject_id != claim.subject_id
        or attempt.grant_id != grant.grant_id
        or claim.subject_id not in grant.subject_ids
        or attempt.coordinator_attempt_id != claim.coordinator_attempt_id
        or grant.coordinator_attempt_id != claim.coordinator_attempt_id
        or fence.coordinator_attempt_id != claim.coordinator_attempt_id
        or attempt.fence_token != claim.fence_token
        or grant.fence_token != claim.fence_token
    ):
        return "authority_identity_mismatch"
    required = set(claim.evidence_ids) | set(grant.evidence_ids)
    if any(
        evidence[item].run_id != run_id or evidence[item].run_revision != run_revision
        for item in required
    ):
        return "evidence_identity_mismatch"
    return None


def _decision_reason(
    decision: Decision,
    *,
    run_id: str,
    run_revision: str,
    claims: Mapping[str, Claim],
    evidence: Mapping[str, EvidenceEnvelope],
    idempotency: Mapping[str, IdempotencyKey],
) -> str | None:
    if decision.run_id != run_id:
        return "run_identity_mismatch"
    if decision.run_revision != run_revision:
        return "missing_matching_revision"
    claim = claims.get(decision.claim_id)
    if claim is None:
        return "missing_authoritative_claim"
    key = idempotency.get(decision.idempotency_key)
    if key is None or key.payload_hash != decision.payload_hash:
        return "missing_matching_idempotency_identity"
    if any(item not in evidence for item in decision.evidence_ids):
        return "missing_matching_evidence"
    if (
        decision.subject_id != claim.subject_id
        or decision.attempt_id != claim.attempt_id
        or decision.grant_id != claim.grant_id
        or decision.coordinator_attempt_id != claim.coordinator_attempt_id
        or decision.fence_token != claim.fence_token
    ):
        return "decision_claim_identity_mismatch"
    if any(
        evidence[item].run_id != run_id or evidence[item].run_revision != run_revision
        for item in decision.evidence_ids
    ):
        return "evidence_identity_mismatch"
    return None


def _by_id(records: Iterable[Any], attribute: str) -> Mapping[str, Any]:
    return MappingProxyType({getattr(record, attribute): record for record in records})


def reduce_run_authority(
    inputs: Iterable[AuthorityInput],
    *,
    run_id: str,
    run_revision: str,
    journal_cursor: int | None = None,
) -> RunAuthorityView:
    """Fold supplied records into a canonical view without external reads.

    The caller supplies the journal boundary explicitly.  Exact repeated records
    are idempotent; every identity with conflicting payloads is excluded rather
    than resolved by input order.
    """

    if not isinstance(run_id, str) or not run_id.strip():
        raise ContractError("run_id must be a non-empty string")
    if not isinstance(run_revision, str) or not run_revision.strip():
        raise ContractError("run_revision must be a non-empty string")
    materialized = tuple(inputs)
    if any(not isinstance(record, Contract) for record in materialized):
        bad = next(record for record in materialized if not isinstance(record, Contract))
        raise ContractError(f"unsupported reducer input {type(bad).__name__}")
    cursor = len(materialized) if journal_cursor is None else journal_cursor
    if not isinstance(cursor, int) or isinstance(cursor, bool) or cursor < 0:
        raise ContractError("journal_cursor must be a non-negative integer")

    unique, duplicate_diagnostics = _deduplicate(materialized)
    typed = tuple(unique)
    evidence_items = tuple(
        record for record in typed
        if isinstance(record, EvidenceEnvelope)
        and record.run_id == run_id and record.run_revision == run_revision
    )
    observations = tuple(
        record for record in typed
        if isinstance(record, ObservationEnvelope) and record.run_id == run_id
    )
    fences_items = tuple(
        record for record in typed
        if isinstance(record, CoordinatorFence)
        and record.run_id == run_id and record.run_revision == run_revision
    )
    grants_items = tuple(
        record for record in typed
        if isinstance(record, CapabilityGrant)
        and record.run_id == run_id and record.run_revision == run_revision
    )
    attempts_items = tuple(
        record for record in typed
        if isinstance(record, SubjectAttempt)
        and record.run_id == run_id and record.run_revision == run_revision
    )
    idempotency_items = tuple(record for record in typed if isinstance(record, IdempotencyKey))
    evidence = _by_id(evidence_items, "evidence_id")
    grants = _by_id(grants_items, "grant_id")
    attempts = _by_id(attempts_items, "attempt_id")
    idempotency = _by_id(idempotency_items, "value")
    fences = MappingProxyType({
        (record.coordinator_attempt_id, record.token): record for record in fences_items
    })

    accepted_claims: list[Claim] = []
    generated: list[QuarantineRecord] = []
    diagnostics = list(duplicate_diagnostics)
    for claim in (record for record in typed if isinstance(record, Claim)):
        reason = _claim_reason(
            claim,
            run_id=run_id,
            run_revision=run_revision,
            evidence=evidence,
            fences=fences,
            grants=grants,
            attempts=attempts,
            idempotency=idempotency,
        )
        if reason is None:
            accepted_claims.append(claim)
        else:
            quarantine = _generated_quarantine(
                claim, run_id=run_id, run_revision=run_revision, reason=reason
            )
            generated.append(quarantine)
            diagnostics.append(AuthorityDiagnostic(
                "quarantined_incomplete_link", "claim", claim.claim_id,
                reason, quarantine.source,
            ))

    claims = _by_id(accepted_claims, "claim_id")
    accepted_decisions: list[Decision] = []
    for decision in (record for record in typed if isinstance(record, Decision)):
        reason = _decision_reason(
            decision,
            run_id=run_id,
            run_revision=run_revision,
            claims=claims,
            evidence=evidence,
            idempotency=idempotency,
        )
        if reason is None:
            accepted_decisions.append(decision)
        else:
            quarantine = _generated_quarantine(
                decision, run_id=run_id, run_revision=run_revision, reason=reason
            )
            generated.append(quarantine)
            diagnostics.append(AuthorityDiagnostic(
                "quarantined_incomplete_link", "decision", decision.decision_id,
                reason, quarantine.source,
            ))

    supplied_quarantines = tuple(
        record for record in typed
        if isinstance(record, QuarantineRecord) and record.run_id == run_id
    )
    all_quarantines, quarantine_conflicts = _deduplicate(supplied_quarantines + tuple(generated))
    diagnostics.extend(quarantine_conflicts)
    evidence_digest_payload = [
        {"evidence_id": record.evidence_id, "digest": record.digest()}
        for record in sorted(evidence_items, key=_record_sort_key)
    ]
    evidence_set_digest = hashlib.sha256(
        canonical_json({"evidence": evidence_digest_payload}).encode("utf-8")
    ).hexdigest()

    values: dict[str, Any] = {
        "schema_version": 1,
        "run_id": run_id,
        "run_revision": run_revision,
        "journal_cursor": cursor,
        "evidence_set_digest": evidence_set_digest,
        "evidence": tuple(sorted(evidence_items, key=_record_sort_key)),
        "observations": tuple(sorted(observations, key=_record_sort_key)),
        "fences": tuple(sorted(fences_items, key=_record_sort_key)),
        "grants": tuple(sorted(grants_items, key=_record_sort_key)),
        "attempts": tuple(sorted(attempts_items, key=_record_sort_key)),
        "claims": tuple(sorted(accepted_claims, key=_record_sort_key)),
        "decisions": tuple(sorted(accepted_decisions, key=_record_sort_key)),
        "quarantines": tuple(sorted(all_quarantines, key=_record_sort_key)),
        "diagnostics": tuple(sorted(set(diagnostics))),
    }
    unsigned = RunAuthorityView(**values, view_hash="pending")
    view_hash = hashlib.sha256(canonical_json(unsigned._payload()).encode("utf-8")).hexdigest()
    return RunAuthorityView(**values, view_hash=view_hash)


__all__ = [
    "AuthorityDiagnostic", "AuthorityInput", "RunAuthorityView", "reduce_run_authority",
]
