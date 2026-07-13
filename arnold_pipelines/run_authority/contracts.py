"""Immutable, persistence-neutral contracts for run authority.

The types in this module deliberately describe only generic authority
mechanics.  Domain policy belongs in bindings built on top of these records.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields
import hashlib
import json
import math
from types import MappingProxyType
from typing import Any, ClassVar, Mapping, TypeVar


JSONValue = None | bool | int | float | str | tuple["JSONValue", ...] | Mapping[str, "JSONValue"]


class ContractError(ValueError):
    """Base class for invalid authority contracts."""


class IdentityConflict(ContractError):
    """Raised when linked contracts identify different authority contexts."""


class RevisionConflict(ContractError):
    """Raised when a compare-and-swap expectation is stale."""


class IdempotencyConflict(ContractError):
    """Raised when one idempotency key names different payloads."""


class PayloadConflict(ContractError):
    """Raised when serialized payload bytes do not match their digest."""


def _required(value: str, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"{name} must be a non-empty string")
    return value


def _string_tuple(values: tuple[str, ...], name: str, *, nonempty: bool = False) -> tuple[str, ...]:
    if not isinstance(values, tuple):
        values = tuple(values)
    normalized = tuple(sorted({_required(value, name) for value in values}))
    if nonempty and not normalized:
        raise ContractError(f"{name} must not be empty")
    return normalized


def _freeze_json(value: Any, path: str = "payload") -> JSONValue:
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ContractError(f"{path} contains a non-finite number")
        return value
    if isinstance(value, Mapping):
        frozen: dict[str, JSONValue] = {}
        for key in sorted(value):
            if not isinstance(key, str):
                raise ContractError(f"{path} keys must be strings")
            frozen[key] = _freeze_json(value[key], f"{path}.{key}")
        return MappingProxyType(frozen)
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_json(item, f"{path}[]") for item in value)
    raise ContractError(f"{path} contains unsupported value {type(value).__name__}")


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _plain(value[key]) for key in sorted(value)}
    if isinstance(value, tuple):
        return [_plain(item) for item in value]
    return value


def canonical_json(value: Mapping[str, Any]) -> str:
    """Return the canonical JSON representation used by all contracts."""

    return json.dumps(_plain(value), ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":"))


def payload_digest(payload: Mapping[str, Any]) -> str:
    """Hash a JSON payload using its canonical representation."""

    frozen = _freeze_json(payload)
    if not isinstance(frozen, Mapping):  # defensive; the public type is a mapping
        raise ContractError("payload must be an object")
    return hashlib.sha256(canonical_json(frozen).encode("utf-8")).hexdigest()


ContractT = TypeVar("ContractT", bound="Contract")


class Contract:
    """Canonical serialization shared by all immutable contract records."""

    contract_type: ClassVar[str]
    schema_version: ClassVar[int] = 1

    def to_dict(self) -> dict[str, Any]:
        result = {
            "contract_type": self.contract_type,
            "schema_version": self.schema_version,
        }
        result.update({field.name: _plain(getattr(self, field.name)) for field in fields(self)})
        return result

    def to_json(self) -> str:
        return canonical_json(self.to_dict())

    def digest(self) -> str:
        return hashlib.sha256(self.to_json().encode("utf-8")).hexdigest()

    @classmethod
    def from_dict(cls: type[ContractT], value: Mapping[str, Any]) -> ContractT:
        if not isinstance(value, Mapping):
            raise ContractError(f"{cls.__name__} must be decoded from an object")
        expected = {field.name for field in fields(cls)} | {"contract_type", "schema_version"}
        unknown = set(value) - expected
        missing = expected - set(value)
        if unknown or missing:
            raise ContractError(
                f"invalid {cls.__name__} fields; missing={sorted(missing)}, unknown={sorted(unknown)}"
            )
        if value["contract_type"] != cls.contract_type:
            raise ContractError(f"expected contract_type {cls.contract_type!r}")
        if value["schema_version"] != cls.schema_version:
            raise ContractError(f"unsupported schema_version {value['schema_version']!r}")
        init_fields = [field for field in fields(cls) if field.init]
        kwargs = {field.name: value[field.name] for field in init_fields}
        instance = cls(**kwargs)
        supplied_hash = value.get("payload_hash")
        if supplied_hash is not None and supplied_hash != getattr(instance, "payload_hash", None):
            raise PayloadConflict("payload_hash does not match canonical payload")
        return instance

    @classmethod
    def from_json(cls: type[ContractT], value: str) -> ContractT:
        try:
            decoded = json.loads(value)
        except (TypeError, json.JSONDecodeError) as exc:
            raise ContractError(f"invalid JSON for {cls.__name__}") from exc
        return cls.from_dict(decoded)


def _initialize_payload(record: Any) -> None:
    frozen = _freeze_json(record.payload)
    if not isinstance(frozen, Mapping):
        raise ContractError("payload must be an object")
    object.__setattr__(record, "payload", frozen)
    object.__setattr__(record, "payload_hash", payload_digest(frozen))


@dataclass(frozen=True)
class EvidenceEnvelope(Contract):
    contract_type: ClassVar[str] = "evidence"
    evidence_id: str
    run_id: str
    run_revision: str
    evidence_type: str
    source: str
    payload: Mapping[str, JSONValue]
    payload_hash: str = field(init=False)

    def __post_init__(self) -> None:
        for name in ("evidence_id", "run_id", "run_revision", "evidence_type", "source"):
            _required(getattr(self, name), name)
        _initialize_payload(self)


@dataclass(frozen=True)
class ObservationEnvelope(Contract):
    contract_type: ClassVar[str] = "observation"
    observation_id: str
    run_id: str
    run_revision: str
    observation_type: str
    source: str
    evidence_ids: tuple[str, ...]
    payload: Mapping[str, JSONValue]
    payload_hash: str = field(init=False)

    def __post_init__(self) -> None:
        for name in ("observation_id", "run_id", "run_revision", "observation_type", "source"):
            _required(getattr(self, name), name)
        object.__setattr__(self, "evidence_ids", _string_tuple(self.evidence_ids, "evidence_ids"))
        _initialize_payload(self)


@dataclass(frozen=True)
class CoordinatorFence(Contract):
    contract_type: ClassVar[str] = "coordinator_fence"
    run_id: str
    run_revision: str
    coordinator_attempt_id: str
    token: int

    def __post_init__(self) -> None:
        for name in ("run_id", "run_revision", "coordinator_attempt_id"):
            _required(getattr(self, name), name)
        if not isinstance(self.token, int) or isinstance(self.token, bool) or self.token < 0:
            raise ContractError("token must be a non-negative integer")


@dataclass(frozen=True)
class CapabilityGrant(Contract):
    contract_type: ClassVar[str] = "capability_grant"
    grant_id: str
    run_id: str
    run_revision: str
    coordinator_attempt_id: str
    fence_token: int
    subject_ids: tuple[str, ...]
    capabilities: tuple[str, ...]
    evidence_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("grant_id", "run_id", "run_revision", "coordinator_attempt_id"):
            _required(getattr(self, name), name)
        if not isinstance(self.fence_token, int) or isinstance(self.fence_token, bool) or self.fence_token < 0:
            raise ContractError("fence_token must be a non-negative integer")
        object.__setattr__(self, "subject_ids", _string_tuple(self.subject_ids, "subject_ids", nonempty=True))
        object.__setattr__(self, "capabilities", _string_tuple(self.capabilities, "capabilities", nonempty=True))
        object.__setattr__(self, "evidence_ids", _string_tuple(self.evidence_ids, "evidence_ids"))


@dataclass(frozen=True)
class SubjectAttempt(Contract):
    contract_type: ClassVar[str] = "subject_attempt"
    attempt_id: str
    run_id: str
    run_revision: str
    subject_id: str
    grant_id: str
    coordinator_attempt_id: str
    fence_token: int
    ordinal: int

    def __post_init__(self) -> None:
        for name in (
            "attempt_id", "run_id", "run_revision", "subject_id", "grant_id", "coordinator_attempt_id"
        ):
            _required(getattr(self, name), name)
        if not isinstance(self.fence_token, int) or isinstance(self.fence_token, bool) or self.fence_token < 0:
            raise ContractError("fence_token must be a non-negative integer")
        if not isinstance(self.ordinal, int) or isinstance(self.ordinal, bool) or self.ordinal < 1:
            raise ContractError("ordinal must be a positive integer")


@dataclass(frozen=True)
class IdempotencyKey(Contract):
    contract_type: ClassVar[str] = "idempotency_key"
    value: str
    payload_hash: str

    def __post_init__(self) -> None:
        _required(self.value, "value")
        _required(self.payload_hash, "payload_hash")

    def assert_compatible(self, other: "IdempotencyKey") -> None:
        if self.value == other.value and self.payload_hash != other.payload_hash:
            raise IdempotencyConflict(f"idempotency key {self.value!r} has conflicting payloads")


@dataclass(frozen=True)
class Claim(Contract):
    contract_type: ClassVar[str] = "claim"
    claim_id: str
    run_id: str
    run_revision: str
    subject_id: str
    attempt_id: str
    grant_id: str
    coordinator_attempt_id: str
    fence_token: int
    claim_type: str
    evidence_ids: tuple[str, ...]
    idempotency_key: str
    payload: Mapping[str, JSONValue]
    payload_hash: str = field(init=False)

    def __post_init__(self) -> None:
        for name in (
            "claim_id", "run_id", "run_revision", "subject_id", "attempt_id", "grant_id",
            "coordinator_attempt_id", "claim_type", "idempotency_key",
        ):
            _required(getattr(self, name), name)
        if not isinstance(self.fence_token, int) or isinstance(self.fence_token, bool) or self.fence_token < 0:
            raise ContractError("fence_token must be a non-negative integer")
        object.__setattr__(self, "evidence_ids", _string_tuple(self.evidence_ids, "evidence_ids", nonempty=True))
        _initialize_payload(self)

    @property
    def idempotency(self) -> IdempotencyKey:
        return IdempotencyKey(self.idempotency_key, self.payload_hash)


@dataclass(frozen=True)
class Decision(Contract):
    contract_type: ClassVar[str] = "decision"
    decision_id: str
    run_id: str
    run_revision: str
    subject_id: str
    attempt_id: str
    grant_id: str
    coordinator_attempt_id: str
    fence_token: int
    claim_id: str
    outcome: str
    evidence_ids: tuple[str, ...]
    idempotency_key: str
    payload: Mapping[str, JSONValue]
    payload_hash: str = field(init=False)

    def __post_init__(self) -> None:
        for name in (
            "decision_id", "run_id", "run_revision", "subject_id", "attempt_id", "grant_id",
            "coordinator_attempt_id", "claim_id", "idempotency_key",
        ):
            _required(getattr(self, name), name)
        if self.outcome not in {"accepted", "rejected", "quarantined", "superseded"}:
            raise ContractError(f"unsupported decision outcome {self.outcome!r}")
        if not isinstance(self.fence_token, int) or isinstance(self.fence_token, bool) or self.fence_token < 0:
            raise ContractError("fence_token must be a non-negative integer")
        object.__setattr__(self, "evidence_ids", _string_tuple(self.evidence_ids, "evidence_ids", nonempty=True))
        _initialize_payload(self)

    @property
    def idempotency(self) -> IdempotencyKey:
        return IdempotencyKey(self.idempotency_key, self.payload_hash)


@dataclass(frozen=True)
class QuarantineRecord(Contract):
    contract_type: ClassVar[str] = "quarantine"
    quarantine_id: str
    run_id: str
    run_revision: str
    record_type: str
    record_id: str
    reason: str
    source: str
    evidence_ids: tuple[str, ...]
    payload: Mapping[str, JSONValue]
    payload_hash: str = field(init=False)

    def __post_init__(self) -> None:
        for name in ("quarantine_id", "run_id", "run_revision", "record_type", "record_id", "reason", "source"):
            _required(getattr(self, name), name)
        object.__setattr__(self, "evidence_ids", _string_tuple(self.evidence_ids, "evidence_ids"))
        _initialize_payload(self)


@dataclass(frozen=True)
class ProjectionMetadata(Contract):
    contract_type: ClassVar[str] = "projection_metadata"
    run_id: str
    run_revision: str
    journal_cursor: int
    evidence_set_digest: str
    view_hash: str

    def __post_init__(self) -> None:
        for name in ("run_id", "run_revision", "evidence_set_digest", "view_hash"):
            _required(getattr(self, name), name)
        if not isinstance(self.journal_cursor, int) or isinstance(self.journal_cursor, bool) or self.journal_cursor < 0:
            raise ContractError("journal_cursor must be a non-negative integer")


@dataclass(frozen=True)
class CASExpectation(Contract):
    contract_type: ClassVar[str] = "cas_expectation"
    run_id: str
    expected_revision: str
    expected_cursor: int | None = None

    def __post_init__(self) -> None:
        _required(self.run_id, "run_id")
        _required(self.expected_revision, "expected_revision")
        if self.expected_cursor is not None and (
            not isinstance(self.expected_cursor, int)
            or isinstance(self.expected_cursor, bool)
            or self.expected_cursor < 0
        ):
            raise ContractError("expected_cursor must be a non-negative integer or null")

    def assert_matches(self, *, run_id: str, revision: str, cursor: int | None = None) -> None:
        if run_id != self.run_id:
            raise IdentityConflict(f"CAS run mismatch: expected {self.run_id!r}, got {run_id!r}")
        if revision != self.expected_revision:
            raise RevisionConflict(
                f"stale revision: expected {self.expected_revision!r}, got {revision!r}"
            )
        if self.expected_cursor is not None and cursor != self.expected_cursor:
            raise RevisionConflict(f"stale cursor: expected {self.expected_cursor!r}, got {cursor!r}")


CONTRACT_TYPES: Mapping[str, type[Contract]] = MappingProxyType({
    contract.contract_type: contract
    for contract in (
        EvidenceEnvelope, ObservationEnvelope, CoordinatorFence, CapabilityGrant,
        SubjectAttempt, IdempotencyKey, Claim, Decision, QuarantineRecord,
        ProjectionMetadata, CASExpectation,
    )
})


def contract_from_dict(value: Mapping[str, Any]) -> Contract:
    """Decode one contract using its explicit versioned discriminator."""

    contract_type = value.get("contract_type") if isinstance(value, Mapping) else None
    try:
        cls = CONTRACT_TYPES[contract_type]
    except (KeyError, TypeError) as exc:
        raise ContractError(f"unknown contract_type {contract_type!r}") from exc
    return cls.from_dict(value)


def assert_idempotent(existing: Claim | Decision, candidate: Claim | Decision) -> None:
    """Apply the store-style duplicate-key rule to payload-bearing records."""

    existing.idempotency.assert_compatible(candidate.idempotency)


def validate_relationships(
    *,
    fence: CoordinatorFence,
    grant: CapabilityGrant,
    attempt: SubjectAttempt,
    claim: Claim,
    evidence: tuple[EvidenceEnvelope, ...],
    decision: Decision | None = None,
) -> None:
    """Validate the complete identity chain required by an authority claim."""

    records: tuple[Contract, ...] = (grant, attempt, claim) + (() if decision is None else (decision,))
    for record in records:
        if record.run_id != fence.run_id:
            raise IdentityConflict(f"run mismatch for {record.contract_type}")
        if record.run_revision != fence.run_revision:
            raise RevisionConflict(f"revision mismatch for {record.contract_type}")
        if record.coordinator_attempt_id != fence.coordinator_attempt_id:
            raise IdentityConflict(f"coordinator attempt mismatch for {record.contract_type}")
        if record.fence_token != fence.token:
            raise IdentityConflict(f"fence mismatch for {record.contract_type}")

    if attempt.grant_id != grant.grant_id or claim.grant_id != grant.grant_id:
        raise IdentityConflict("grant mismatch")
    if attempt.subject_id not in grant.subject_ids:
        raise IdentityConflict("attempt subject is outside grant scope")
    if claim.subject_id != attempt.subject_id or claim.attempt_id != attempt.attempt_id:
        raise IdentityConflict("claim attempt mismatch")

    evidence_by_id = {item.evidence_id: item for item in evidence}
    if len(evidence_by_id) != len(evidence):
        raise IdentityConflict("duplicate evidence identity")
    required_evidence = set(grant.evidence_ids) | set(claim.evidence_ids)
    if decision is not None:
        if (
            decision.claim_id != claim.claim_id
            or decision.subject_id != claim.subject_id
            or decision.attempt_id != claim.attempt_id
            or decision.grant_id != claim.grant_id
        ):
            raise IdentityConflict("decision claim mismatch")
        required_evidence.update(decision.evidence_ids)
    missing = sorted(required_evidence - evidence_by_id.keys())
    if missing:
        raise IdentityConflict(f"missing evidence: {', '.join(missing)}")
    for evidence_id in sorted(required_evidence):
        item = evidence_by_id[evidence_id]
        if item.run_id != fence.run_id:
            raise IdentityConflict(f"evidence run mismatch: {evidence_id}")
        if item.run_revision != fence.run_revision:
            raise RevisionConflict(f"evidence revision mismatch: {evidence_id}")


__all__ = [
    "CASExpectation", "CapabilityGrant", "Claim", "Contract", "ContractError",
    "CoordinatorFence", "Decision", "EvidenceEnvelope", "IdempotencyConflict",
    "IdempotencyKey", "IdentityConflict", "ObservationEnvelope", "PayloadConflict",
    "ProjectionMetadata", "QuarantineRecord", "RevisionConflict", "SubjectAttempt",
    "assert_idempotent", "canonical_json", "contract_from_dict", "payload_digest",
    "validate_relationships",
]
