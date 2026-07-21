from __future__ import annotations

from dataclasses import dataclass, field, fields
from datetime import datetime, timezone
from enum import StrEnum
import hashlib
import json
import os
from pathlib import Path
import socket
from types import MappingProxyType
from typing import Any, ClassVar, Mapping

from arnold_pipelines.run_authority import canonical_json, payload_digest


CUSTODY_TARGET_KEY_VERSION = 1
REPAIR_OCCURRENCE_KEY_VERSION = 1
CUSTODY_LEASE_VERSION = 1
CUSTODY_LEASE_EVENT_VERSION = 1
F01_REPAIR_OCCURRENCE_FIELDS = (
    "environment_id",
    "session_id",
    "chain_id",
    "plan_revision",
    "phase",
    "task_id",
    "attempt_number",
    "failure_kind",
    "blocker_digest",
    "coordinator_fence_token",
)


def _required(value: str, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value.strip()


def _freeze_mapping(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return MappingProxyType({str(key): payload[key] for key in sorted(payload)})


def _freeze_json_sorted(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze_json_sorted(value[key]) for key in sorted(value)})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_json_sorted(item) for item in value)
    raise TypeError(f"unsupported JSON value {type(value).__name__}")


def target_digest(target: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(dict(target)).encode("utf-8")).hexdigest()


def occurrence_digest(f01_fields: Mapping[str, Any], fence_token: str, chain_identity: str) -> str:
    material = {
        "f01_fields": {name: f01_fields.get(name) for name in F01_REPAIR_OCCURRENCE_FIELDS},
        "fence_token": str(fence_token),
        "chain_identity": str(chain_identity),
    }
    return hashlib.sha256(canonical_json(material).encode("utf-8")).hexdigest()


def process_birth_identity() -> dict[str, str]:
    boot_id = ""
    try:
        boot_id = Path("/proc/sys/kernel/random/boot_id").read_text(encoding="utf-8").strip()
    except OSError:
        pass
    return {
        "host": socket.gethostname(),
        "pid": str(os.getpid()),
        "boot_id": boot_id,
    }


class CustodyLeaseEventType(StrEnum):
    ACQUIRE = "acquire"
    RENEW = "renew"
    TRANSFER = "transfer"
    RELEASE = "release"
    EXPIRE = "expire"
    FENCE = "fence"
    CONFLICT = "conflict"
    RECONCILE = "reconcile"
    QUARANTINE = "quarantine"
    RECLAIM = "reclaim"


class CustodyLeaseOutcome(StrEnum):
    ACQUIRE = "acquire"
    RENEW = "renew"
    TRANSFER = "transfer"
    RELEASE = "release"
    EXPIRE = "expire"
    FENCE = "fence"
    CONFLICT = "conflict"
    RECONCILE = "reconcile"
    QUARANTINE = "quarantine"
    RECLAIM = "reclaim"


CUSTODY_LEASE_EVENT_TYPES = tuple(item.value for item in CustodyLeaseEventType)
CUSTODY_LEASE_OUTCOMES = tuple(item.value for item in CustodyLeaseOutcome)


@dataclass(frozen=True)
class CustodyTargetKey:
    subject_type: str
    subject_id: str
    action: str
    target_kind: str
    target_id: str
    contract_id: str

    def __post_init__(self) -> None:
        for name in ("subject_type", "subject_id", "action", "target_kind", "target_id", "contract_id"):
            object.__setattr__(self, name, _required(getattr(self, name), name))

    @property
    def key(self) -> str:
        return target_digest(self.to_dict())

    @property
    def target_digest(self) -> str:
        return self.key

    def to_dict(self) -> dict[str, str]:
        return {field.name: getattr(self, field.name) for field in fields(self)}


@dataclass(frozen=True)
class RepairOccurrenceKey:
    environment_id: str
    session_id: str
    chain_id: str
    plan_revision: str
    phase: str
    task_id: str
    attempt_number: int
    failure_kind: str
    blocker_digest: str
    coordinator_fence_token: str

    def __post_init__(self) -> None:
        for name in (
            "environment_id",
            "session_id",
            "chain_id",
            "plan_revision",
            "phase",
            "task_id",
            "failure_kind",
            "blocker_digest",
            "coordinator_fence_token",
        ):
            object.__setattr__(self, name, _required(getattr(self, name), name))
        if not isinstance(self.attempt_number, int) or isinstance(self.attempt_number, bool) or self.attempt_number < 1:
            raise ValueError("attempt_number must be a positive integer")

    @property
    def f01_tuple(self) -> tuple[Any, ...]:
        return tuple(getattr(self, name) for name in F01_REPAIR_OCCURRENCE_FIELDS)

    @property
    def key(self) -> str:
        return occurrence_digest(self.to_dict(), self.coordinator_fence_token, self.chain_id)

    def to_dict(self) -> dict[str, Any]:
        return {field.name: getattr(self, field.name) for field in fields(self)}


@dataclass(frozen=True)
class CustodyLease:
    lease_id: str
    target_key: CustodyTargetKey | None = None
    occurrence_key: RepairOccurrenceKey | None = None
    owner: tuple[str, str, str] = field(default_factory=tuple)
    epoch: int = 0
    acquired_at: str = ""
    expires_at: str = ""
    fence_token: str = ""
    status: str = ""
    causal_predecessor: str = ""
    run_authority_grant_id: str = ""
    wbc_attempt_reference: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "lease_id", _required(self.lease_id, "lease_id"))
        if self.target_key is not None and not isinstance(self.target_key, CustodyTargetKey):
            raise TypeError("target_key must be a CustodyTargetKey")
        if self.occurrence_key is not None and not isinstance(self.occurrence_key, RepairOccurrenceKey):
            raise TypeError("occurrence_key must be a RepairOccurrenceKey")
        owner = tuple(str(item) for item in self.owner)
        if owner and len(owner) != 3:
            raise ValueError("owner must be a 3-tuple of host, pid, boot_id")
        object.__setattr__(self, "owner", owner or ("", "", ""))
        if not isinstance(self.epoch, int) or isinstance(self.epoch, bool) or self.epoch < 0:
            raise ValueError("epoch must be a non-negative integer")
        object.__setattr__(self, "fence_token", str(self.fence_token))
        object.__setattr__(self, "status", str(self.status))
        object.__setattr__(self, "causal_predecessor", str(self.causal_predecessor))
        object.__setattr__(self, "run_authority_grant_id", str(self.run_authority_grant_id))
        object.__setattr__(self, "wbc_attempt_reference", str(self.wbc_attempt_reference))

    @property
    def custody_epoch(self) -> int:
        return self.epoch

    @property
    def target_digest(self) -> str:
        return self.target_key.target_digest if self.target_key is not None else ""

    @property
    def owner_host(self) -> str:
        return self.owner[0]

    @property
    def owner_pid(self) -> str:
        return self.owner[1]

    @property
    def owner_boot_id(self) -> str:
        return self.owner[2]

    @property
    def owner_identity(self) -> tuple[str, str, str]:
        return self.owner

    @property
    def is_expired(self) -> bool:
        if not self.expires_at:
            return False
        try:
            expires = datetime.fromisoformat(self.expires_at.replace("Z", "+00:00"))
        except ValueError:
            return False
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return expires <= datetime.now(timezone.utc)

    def to_dict(self) -> dict[str, Any]:
        return {
            "lease_id": self.lease_id,
            "target_key": None if self.target_key is None else self.target_key.to_dict(),
            "occurrence_key": None if self.occurrence_key is None else self.occurrence_key.to_dict(),
            "owner": list(self.owner),
            "epoch": self.epoch,
            "acquired_at": self.acquired_at,
            "expires_at": self.expires_at,
            "fence_token": self.fence_token,
            "status": self.status,
            "causal_predecessor": self.causal_predecessor,
            "run_authority_grant_id": self.run_authority_grant_id,
            "wbc_attempt_reference": self.wbc_attempt_reference,
        }


@dataclass(frozen=True)
class CustodyLeaseEvent:
    lease_id: str
    event_type: CustodyLeaseEventType = CustodyLeaseEventType.ACQUIRE
    occurred_at: str = ""
    payload: Mapping[str, Any] = field(default_factory=dict)
    sequence: int = 0
    causal_predecessor: str = ""
    idempotency_key: str = ""
    payload_hash: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "lease_id", _required(self.lease_id, "lease_id"))
        if not isinstance(self.event_type, CustodyLeaseEventType):
            object.__setattr__(self, "event_type", CustodyLeaseEventType(str(self.event_type)))
        object.__setattr__(self, "payload", _freeze_mapping(dict(self.payload)))
        if not isinstance(self.sequence, int) or isinstance(self.sequence, bool) or self.sequence < 0:
            raise ValueError("sequence must be a non-negative integer")
        object.__setattr__(self, "causal_predecessor", str(self.causal_predecessor))
        object.__setattr__(self, "idempotency_key", str(self.idempotency_key))
        object.__setattr__(self, "payload_hash", str(self.payload_hash))

    def to_dict(self) -> dict[str, Any]:
        return {
            "lease_id": self.lease_id,
            "event_type": self.event_type.value,
            "occurred_at": self.occurred_at,
            "payload": dict(self.payload),
            "sequence": self.sequence,
            "causal_predecessor": self.causal_predecessor,
            "idempotency_key": self.idempotency_key,
            "payload_hash": self.payload_hash,
        }


def normalize_custody_target_key(payload: Any) -> CustodyTargetKey | None:
    if isinstance(payload, CustodyTargetKey):
        return payload
    if not isinstance(payload, Mapping):
        return None
    try:
        return CustodyTargetKey(
            subject_type=str(payload["subject_type"]),
            subject_id=str(payload["subject_id"]),
            action=str(payload["action"]),
            target_kind=str(payload["target_kind"]),
            target_id=str(payload["target_id"]),
            contract_id=str(payload["contract_id"]),
        )
    except (KeyError, TypeError, ValueError):
        return None


def build_custody_target_key(
    subject_type: str = "",
    subject_id: str = "",
    action: str = "",
    target_kind: str = "",
    target_id: str = "",
    contract_id: str = "",
) -> CustodyTargetKey | None:
    try:
        return CustodyTargetKey(subject_type, subject_id, action, target_kind, target_id, contract_id)
    except ValueError:
        return None


def normalize_repair_occurrence_key(payload: Any) -> RepairOccurrenceKey | None:
    if isinstance(payload, RepairOccurrenceKey):
        return payload
    if not isinstance(payload, Mapping):
        return None
    try:
        return RepairOccurrenceKey(
            environment_id=str(payload["environment_id"]),
            session_id=str(payload["session_id"]),
            chain_id=str(payload["chain_id"]),
            plan_revision=str(payload["plan_revision"]),
            phase=str(payload["phase"]),
            task_id=str(payload["task_id"]),
            attempt_number=int(payload["attempt_number"]),
            failure_kind=str(payload["failure_kind"]),
            blocker_digest=str(payload["blocker_digest"]),
            coordinator_fence_token=str(payload["coordinator_fence_token"]),
        )
    except (KeyError, TypeError, ValueError):
        return None


def build_repair_occurrence_key(
    environment_id: str = "",
    session_id: str = "",
    chain_id: str = "",
    plan_revision: str = "",
    phase: str = "",
    task_id: str = "",
    attempt_number: int = 0,
    failure_kind: str = "",
    blocker_digest: str = "",
    coordinator_fence_token: str = "",
) -> RepairOccurrenceKey | None:
    try:
        return RepairOccurrenceKey(
            environment_id,
            session_id,
            chain_id,
            plan_revision,
            phase,
            task_id,
            attempt_number,
            failure_kind,
            blocker_digest,
            coordinator_fence_token,
        )
    except ValueError:
        return None


def normalize_custody_lease(payload: Any) -> CustodyLease | None:
    if isinstance(payload, CustodyLease):
        return payload
    if not isinstance(payload, Mapping):
        return None
    try:
        return CustodyLease(
            lease_id=str(payload["lease_id"]),
            target_key=normalize_custody_target_key(payload.get("target_key")),
            occurrence_key=normalize_repair_occurrence_key(payload.get("occurrence_key")),
            owner=tuple(payload.get("owner") or ("", "", "")),
            epoch=int(payload.get("epoch", 0)),
            acquired_at=str(payload.get("acquired_at", "")),
            expires_at=str(payload.get("expires_at", "")),
            fence_token=str(payload.get("fence_token", "")),
            status=str(payload.get("status", "")),
            causal_predecessor=str(payload.get("causal_predecessor", "")),
            run_authority_grant_id=str(payload.get("run_authority_grant_id", "")),
            wbc_attempt_reference=str(payload.get("wbc_attempt_reference", "")),
        )
    except (KeyError, TypeError, ValueError):
        return None


def normalize_custody_lease_event(payload: Any) -> CustodyLeaseEvent | None:
    if isinstance(payload, CustodyLeaseEvent):
        return payload
    if not isinstance(payload, Mapping):
        return None
    try:
        return CustodyLeaseEvent(
            lease_id=str(payload["lease_id"]),
            event_type=CustodyLeaseEventType(str(payload.get("event_type", CustodyLeaseEventType.ACQUIRE.value))),
            occurred_at=str(payload.get("occurred_at", "")),
            payload=dict(payload.get("payload") or {}),
            sequence=int(payload.get("sequence", 0)),
            causal_predecessor=str(payload.get("causal_predecessor", "")),
            idempotency_key=str(payload.get("idempotency_key", "")),
            payload_hash=str(payload.get("payload_hash", "")),
        )
    except (KeyError, TypeError, ValueError):
        return None


__all__ = [
    "Any",
    "CUSTODY_LEASE_EVENT_TYPES",
    "CUSTODY_LEASE_EVENT_VERSION",
    "CUSTODY_LEASE_OUTCOMES",
    "CUSTODY_LEASE_VERSION",
    "CUSTODY_TARGET_KEY_VERSION",
    "ClassVar",
    "CustodyLease",
    "CustodyLeaseEvent",
    "CustodyLeaseEventType",
    "CustodyLeaseOutcome",
    "CustodyTargetKey",
    "F01_REPAIR_OCCURRENCE_FIELDS",
    "Mapping",
    "MappingProxyType",
    "Path",
    "REPAIR_OCCURRENCE_KEY_VERSION",
    "RepairOccurrenceKey",
    "build_custody_target_key",
    "build_repair_occurrence_key",
    "dataclass",
    "datetime",
    "field",
    "fields",
    "hashlib",
    "json",
    "normalize_custody_lease",
    "normalize_custody_lease_event",
    "normalize_custody_target_key",
    "normalize_repair_occurrence_key",
    "occurrence_digest",
    "os",
    "payload_digest",
    "process_birth_identity",
    "socket",
    "target_digest",
    "timezone",
]
