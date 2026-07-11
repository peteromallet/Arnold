"""Megaplan names and policy constraints over generic authority contracts.

The subclasses deliberately retain the generic wire contract.  They add only
Megaplan vocabulary and validation; persistence and reduction remain owned by
``arnold_pipelines.run_authority``.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Any, Mapping

from arnold_pipelines.run_authority import (
    CASExpectation,
    CapabilityGrant,
    Claim,
    ContractError,
    CoordinatorFence,
    Decision,
    EvidenceEnvelope,
    IdempotencyKey,
    IdentityConflict,
    RevisionConflict,
    SubjectAttempt,
    canonical_json,
    validate_relationships,
)


TASK_RESULT_CAPABILITY = "megaplan.task.result"
SENSE_CHECK_RESULT_CAPABILITY = "megaplan.sense_check.result"
TASK_COMPLETION_CLAIM = "megaplan.task.completion"
SENSE_CHECK_ACK_CLAIM = "megaplan.sense_check.acknowledgment"
DISPATCH_IDENTITY_SCHEMA_VERSION = 1
RESULT_ENVELOPE_SCHEMA_VERSION = 1


def _required(value: str, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"{name} must be a non-empty string")
    return value


def _contract_dict(value: Any, name: str) -> dict[str, Any]:
    if not hasattr(value, "to_dict"):
        raise ContractError(f"{name} must be an authority contract")
    return value.to_dict()


def _contract_digest(value: Any) -> str:
    if not hasattr(value, "to_json"):
        raise ContractError("wrapped value must be an authority contract")
    return hashlib.sha256(value.to_json().encode("utf-8")).hexdigest()


def _decode_optional_cas(value: Mapping[str, Any] | None) -> CASExpectation | None:
    if value is None:
        return None
    return CASExpectation.from_dict(value)


@dataclass(frozen=True)
class DispatchGrant(CapabilityGrant):
    """A capability grant whose scope was dispatched by Megaplan."""

    def __post_init__(self) -> None:
        super().__post_init__()
        allowed = {TASK_RESULT_CAPABILITY, SENSE_CHECK_RESULT_CAPABILITY}
        unknown = set(self.capabilities) - allowed
        if unknown:
            raise ContractError(f"unsupported Megaplan dispatch capabilities: {sorted(unknown)}")

    @property
    def dispatch_id(self) -> str:
        return self.grant_id

    @property
    def plan_revision(self) -> str:
        return self.run_revision


@dataclass(frozen=True)
class DispatchIdentity:
    """Megaplan dispatch metadata around generic fence, grant, and CAS records."""

    grant: DispatchGrant
    fence: CoordinatorFence
    prerequisite_digest: str
    worker_id: str
    cas_expectation: CASExpectation | None = None
    schema_version: int = DISPATCH_IDENTITY_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _required(self.prerequisite_digest, "prerequisite_digest")
        _required(self.worker_id, "worker_id")
        if self.schema_version != DISPATCH_IDENTITY_SCHEMA_VERSION:
            raise ContractError(f"unsupported dispatch identity schema_version {self.schema_version!r}")
        if self.grant.run_id != self.fence.run_id:
            raise IdentityConflict("dispatch grant/fence run mismatch")
        if self.grant.run_revision != self.fence.run_revision:
            raise RevisionConflict("dispatch grant/fence revision mismatch")
        if self.grant.coordinator_attempt_id != self.fence.coordinator_attempt_id:
            raise IdentityConflict("dispatch grant/fence coordinator mismatch")
        if self.grant.fence_token != self.fence.token:
            raise IdentityConflict("dispatch grant/fence token mismatch")
        if self.cas_expectation is not None:
            self.cas_expectation.assert_matches(
                run_id=self.grant.run_id,
                revision=self.grant.run_revision,
                cursor=self.cas_expectation.expected_cursor,
            )

    @property
    def dispatch_id(self) -> str:
        return self.grant.dispatch_id

    @property
    def run_id(self) -> str:
        return self.grant.run_id

    @property
    def run_revision(self) -> str:
        return self.grant.run_revision

    @property
    def plan_revision(self) -> str:
        return self.grant.run_revision

    @property
    def coordinator_attempt_id(self) -> str:
        return self.grant.coordinator_attempt_id

    @property
    def fence_token(self) -> int:
        return self.grant.fence_token

    @property
    def subject_ids(self) -> tuple[str, ...]:
        return self.grant.subject_ids

    @property
    def capabilities(self) -> tuple[str, ...]:
        return self.grant.capabilities

    @property
    def evidence_ids(self) -> tuple[str, ...]:
        return self.grant.evidence_ids

    @property
    def worker_identity(self) -> str:
        return self.worker_id

    @property
    def prerequisite_set_digest(self) -> str:
        return self.prerequisite_digest

    @classmethod
    def create(
        cls,
        *,
        dispatch_id: str,
        run_id: str,
        run_revision: str,
        coordinator_attempt_id: str,
        fence_token: int,
        subject_ids: tuple[str, ...],
        capabilities: tuple[str, ...],
        prerequisite_digest: str,
        worker_id: str,
        evidence_ids: tuple[str, ...] = (),
        expected_cursor: int | None = None,
    ) -> "DispatchIdentity":
        grant = DispatchGrant(
            dispatch_id,
            run_id,
            run_revision,
            coordinator_attempt_id,
            fence_token,
            subject_ids,
            capabilities,
            evidence_ids,
        )
        fence = CoordinatorFence(run_id, run_revision, coordinator_attempt_id, fence_token)
        cas = CASExpectation(run_id, run_revision, expected_cursor)
        return cls(grant, fence, prerequisite_digest, worker_id, cas)

    @classmethod
    def from_records(
        cls,
        grant: DispatchGrant | CapabilityGrant,
        fence: CoordinatorFence,
        prerequisite_digest: str,
        worker_id: str,
        cas_expectation: CASExpectation | None = None,
    ) -> "DispatchIdentity":
        dispatch_grant = grant if isinstance(grant, DispatchGrant) else DispatchGrant.from_dict(grant.to_dict())
        return cls(dispatch_grant, fence, prerequisite_digest, worker_id, cas_expectation)

    from_grant = from_records

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "DispatchIdentity":
        if not isinstance(value, Mapping):
            raise ContractError("DispatchIdentity must be decoded from an object")
        allowed = {
            "schema_version",
            "grant",
            "fence",
            "prerequisite_digest",
            "worker_id",
            "cas_expectation",
        }
        unknown = set(value) - allowed
        missing = allowed - {"cas_expectation"} - set(value)
        if unknown or missing:
            raise ContractError(
                f"invalid DispatchIdentity fields; missing={sorted(missing)}, unknown={sorted(unknown)}"
            )
        return cls(
            grant=DispatchGrant.from_dict(value["grant"]),
            fence=CoordinatorFence.from_dict(value["fence"]),
            prerequisite_digest=value["prerequisite_digest"],
            worker_id=value["worker_id"],
            cas_expectation=_decode_optional_cas(value.get("cas_expectation")),
            schema_version=value["schema_version"],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "grant": self.grant.to_dict(),
            "fence": self.fence.to_dict(),
            "prerequisite_digest": self.prerequisite_digest,
            "worker_id": self.worker_id,
            "cas_expectation": (
                None if self.cas_expectation is None else self.cas_expectation.to_dict()
            ),
        }

    def to_json(self) -> str:
        return canonical_json(self.to_dict())

    def digest(self) -> str:
        return hashlib.sha256(self.to_json().encode("utf-8")).hexdigest()

    def authority_records(self) -> tuple[CoordinatorFence, DispatchGrant] | tuple[CoordinatorFence, DispatchGrant, CASExpectation]:
        records: tuple[CoordinatorFence, DispatchGrant] = (self.fence, self.grant)
        if self.cas_expectation is None:
            return records
        return (*records, self.cas_expectation)

    def to_authority_records(self) -> tuple[CoordinatorFence, DispatchGrant] | tuple[CoordinatorFence, DispatchGrant, CASExpectation]:
        return self.authority_records()


@dataclass(frozen=True)
class TaskAttempt(SubjectAttempt):
    """Megaplan task-attempt name over a generic subject attempt."""

    @property
    def task_id(self) -> str:
        return self.subject_id

    @property
    def dispatch_id(self) -> str:
        return self.grant_id

    @property
    def plan_revision(self) -> str:
        return self.run_revision


@dataclass(frozen=True)
class SenseCheckAttempt(SubjectAttempt):
    """Megaplan sense-check attempt name over a generic subject attempt."""

    @property
    def sense_check_id(self) -> str:
        return self.subject_id

    @property
    def dispatch_id(self) -> str:
        return self.grant_id

    @property
    def plan_revision(self) -> str:
        return self.run_revision


@dataclass(frozen=True)
class TaskClaim(Claim):
    """A task completion claim; it is not an accepted completion itself."""

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.claim_type != TASK_COMPLETION_CLAIM:
            raise ContractError(f"TaskClaim requires claim_type {TASK_COMPLETION_CLAIM!r}")

    @property
    def task_id(self) -> str:
        return self.subject_id

    @property
    def dispatch_id(self) -> str:
        return self.grant_id

    @property
    def plan_revision(self) -> str:
        return self.run_revision


@dataclass(frozen=True)
class SenseCheckClaim(Claim):
    """A sense-check acknowledgment claim; acceptance still requires a decision."""

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.claim_type != SENSE_CHECK_ACK_CLAIM:
            raise ContractError(f"SenseCheckClaim requires claim_type {SENSE_CHECK_ACK_CLAIM!r}")

    @property
    def sense_check_id(self) -> str:
        return self.subject_id

    @property
    def dispatch_id(self) -> str:
        return self.grant_id

    @property
    def plan_revision(self) -> str:
        return self.run_revision


@dataclass(frozen=True)
class TaskValidationDecision(Decision):
    """Megaplan validation of one task claim."""

    @property
    def task_id(self) -> str:
        return self.subject_id

    @property
    def dispatch_id(self) -> str:
        return self.grant_id

    @property
    def plan_revision(self) -> str:
        return self.run_revision


@dataclass(frozen=True)
class SenseCheckValidationDecision(Decision):
    """Megaplan validation of one sense-check acknowledgment claim."""

    @property
    def sense_check_id(self) -> str:
        return self.subject_id

    @property
    def dispatch_id(self) -> str:
        return self.grant_id

    @property
    def plan_revision(self) -> str:
        return self.run_revision


MegaplanAttempt = TaskAttempt | SenseCheckAttempt
MegaplanClaim = TaskClaim | SenseCheckClaim
MegaplanDecision = TaskValidationDecision | SenseCheckValidationDecision
AuthorityRecord = (
    CoordinatorFence
    | DispatchGrant
    | MegaplanAttempt
    | MegaplanClaim
    | MegaplanDecision
    | EvidenceEnvelope
    | IdempotencyKey
    | CASExpectation
)


@dataclass(frozen=True)
class ResultEnvelope:
    """Megaplan worker result wrapped around generic authority records."""

    dispatch: DispatchIdentity
    attempt: MegaplanAttempt
    claim: MegaplanClaim
    evidence: tuple[EvidenceEnvelope, ...]
    decision: MegaplanDecision | None = None
    cas_expectation: CASExpectation | None = None
    schema_version: int = RESULT_ENVELOPE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != RESULT_ENVELOPE_SCHEMA_VERSION:
            raise ContractError(f"unsupported result envelope schema_version {self.schema_version!r}")
        object.__setattr__(self, "evidence", tuple(sorted(self.evidence, key=lambda item: item.evidence_id)))
        if self.cas_expectation is not None:
            self.cas_expectation.assert_matches(
                run_id=self.dispatch.run_id,
                revision=self.dispatch.run_revision,
                cursor=self.cas_expectation.expected_cursor,
            )
        if self.attempt.grant_id != self.dispatch.dispatch_id:
            raise IdentityConflict("attempt dispatch mismatch")
        if self.attempt.subject_id not in self.dispatch.subject_ids:
            raise IdentityConflict("attempt subject is outside dispatch scope")
        if self.claim.grant_id != self.dispatch.dispatch_id:
            raise IdentityConflict("claim dispatch mismatch")
        expected_capability = (
            TASK_RESULT_CAPABILITY
            if isinstance(self.claim, TaskClaim)
            else SENSE_CHECK_RESULT_CAPABILITY
        )
        if expected_capability not in self.dispatch.capabilities:
            raise IdentityConflict(f"dispatch lacks required capability {expected_capability!r}")
        validate_relationships(
            fence=self.dispatch.fence,
            grant=self.dispatch.grant,
            attempt=self.attempt,
            claim=self.claim,
            evidence=self.evidence,
            decision=self.decision,
        )

    @property
    def dispatch_id(self) -> str:
        return self.dispatch.dispatch_id

    @property
    def run_id(self) -> str:
        return self.dispatch.run_id

    @property
    def run_revision(self) -> str:
        return self.dispatch.run_revision

    @property
    def plan_revision(self) -> str:
        return self.dispatch.run_revision

    @property
    def worker_id(self) -> str:
        return self.dispatch.worker_id

    @property
    def worker_identity(self) -> str:
        return self.dispatch.worker_identity

    @property
    def prerequisite_digest(self) -> str:
        return self.dispatch.prerequisite_digest

    @property
    def prerequisite_set_digest(self) -> str:
        return self.dispatch.prerequisite_set_digest

    @property
    def subject_id(self) -> str:
        return self.attempt.subject_id

    @property
    def evidence_ids(self) -> tuple[str, ...]:
        evidence_ids = {*self.dispatch.evidence_ids, *self.claim.evidence_ids}
        if self.decision is not None:
            evidence_ids.update(self.decision.evidence_ids)
        return tuple(sorted(evidence_ids))

    @property
    def idempotency_keys(self) -> tuple[IdempotencyKey, ...]:
        keys = [self.claim.idempotency]
        if self.decision is not None:
            keys.append(self.decision.idempotency)
        return tuple(keys)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ResultEnvelope":
        if not isinstance(value, Mapping):
            raise ContractError("ResultEnvelope must be decoded from an object")
        allowed = {
            "schema_version",
            "dispatch",
            "attempt",
            "claim",
            "decision",
            "evidence",
            "cas_expectation",
        }
        unknown = set(value) - allowed
        missing = allowed - {"decision", "cas_expectation"} - set(value)
        if unknown or missing:
            raise ContractError(
                f"invalid ResultEnvelope fields; missing={sorted(missing)}, unknown={sorted(unknown)}"
            )
        claim = _decode_claim(value["claim"])
        return cls(
            dispatch=DispatchIdentity.from_dict(value["dispatch"]),
            attempt=_decode_attempt(value["attempt"], claim),
            claim=claim,
            evidence=tuple(EvidenceEnvelope.from_dict(item) for item in value["evidence"]),
            decision=_decode_decision(value.get("decision"), claim),
            cas_expectation=_decode_optional_cas(value.get("cas_expectation")),
            schema_version=value["schema_version"],
        )

    @classmethod
    def from_records(
        cls,
        dispatch: DispatchIdentity,
        attempt: SubjectAttempt,
        claim: Claim,
        evidence: tuple[EvidenceEnvelope, ...],
        decision: Decision | None = None,
        cas_expectation: CASExpectation | None = None,
    ) -> "ResultEnvelope":
        claim_value = claim if isinstance(claim, (TaskClaim, SenseCheckClaim)) else _decode_claim(claim.to_dict())
        attempt_value = (
            attempt
            if isinstance(attempt, (TaskAttempt, SenseCheckAttempt))
            else _decode_attempt(attempt.to_dict(), claim_value)
        )
        decision_value = (
            decision
            if isinstance(decision, (TaskValidationDecision, SenseCheckValidationDecision))
            else _decode_decision(None if decision is None else decision.to_dict(), claim_value)
        )
        return cls(
            dispatch=dispatch,
            attempt=attempt_value,
            claim=claim_value,
            evidence=evidence,
            decision=decision_value,
            cas_expectation=cas_expectation,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "dispatch": self.dispatch.to_dict(),
            "attempt": _contract_dict(self.attempt, "attempt"),
            "claim": _contract_dict(self.claim, "claim"),
            "decision": None if self.decision is None else _contract_dict(self.decision, "decision"),
            "evidence": [item.to_dict() for item in self.evidence],
            "cas_expectation": (
                None if self.cas_expectation is None else self.cas_expectation.to_dict()
            ),
        }

    def to_json(self) -> str:
        return canonical_json(self.to_dict())

    def digest(self) -> str:
        return hashlib.sha256(self.to_json().encode("utf-8")).hexdigest()

    def authority_records(self) -> tuple[AuthorityRecord, ...]:
        records: list[AuthorityRecord] = [
            self.dispatch.fence,
            self.dispatch.grant,
            *self.evidence,
            self.attempt,
            self.claim.idempotency,
            self.claim,
        ]
        if self.decision is not None:
            records.extend((self.decision.idempotency, self.decision))
        if self.dispatch.cas_expectation is not None:
            records.append(self.dispatch.cas_expectation)
        if self.cas_expectation is not None and (
            self.dispatch.cas_expectation is None
            or _contract_digest(self.cas_expectation) != _contract_digest(self.dispatch.cas_expectation)
        ):
            records.append(self.cas_expectation)
        return tuple(records)

    def to_authority_records(self) -> tuple[AuthorityRecord, ...]:
        return self.authority_records()


DispatchResultEnvelope = ResultEnvelope
MegaplanDispatchIdentity = DispatchIdentity


def _decode_claim(value: Mapping[str, Any]) -> MegaplanClaim:
    generic = Claim.from_dict(value)
    if generic.claim_type == TASK_COMPLETION_CLAIM:
        return TaskClaim.from_dict(value)
    if generic.claim_type == SENSE_CHECK_ACK_CLAIM:
        return SenseCheckClaim.from_dict(value)
    raise ContractError(f"unsupported Megaplan claim_type {generic.claim_type!r}")


def _decode_attempt(value: Mapping[str, Any], claim: MegaplanClaim) -> MegaplanAttempt:
    if isinstance(claim, TaskClaim):
        return TaskAttempt.from_dict(value)
    return SenseCheckAttempt.from_dict(value)


def _decode_decision(value: Mapping[str, Any] | None, claim: MegaplanClaim) -> MegaplanDecision | None:
    if value is None:
        return None
    if isinstance(claim, TaskClaim):
        return TaskValidationDecision.from_dict(value)
    return SenseCheckValidationDecision.from_dict(value)


__all__ = [
    "DISPATCH_IDENTITY_SCHEMA_VERSION",
    "DispatchGrant",
    "DispatchIdentity",
    "DispatchResultEnvelope",
    "MegaplanDispatchIdentity",
    "MegaplanAttempt",
    "MegaplanClaim",
    "MegaplanDecision",
    "AuthorityRecord",
    "SENSE_CHECK_ACK_CLAIM",
    "SENSE_CHECK_RESULT_CAPABILITY",
    "RESULT_ENVELOPE_SCHEMA_VERSION",
    "ResultEnvelope",
    "SenseCheckAttempt",
    "SenseCheckClaim",
    "SenseCheckValidationDecision",
    "TASK_COMPLETION_CLAIM",
    "TASK_RESULT_CAPABILITY",
    "TaskAttempt",
    "TaskClaim",
    "TaskValidationDecision",
]
