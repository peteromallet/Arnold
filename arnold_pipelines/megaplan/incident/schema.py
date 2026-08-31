"""Incident event schema — validation and normalization for M1.

Exports
-------
* ``validate_incident_event(event)`` — validate and return a normalized
  shallow copy.  Preserves unknown fields, rejects missing or malformed
  required fields with field-specific ``ValueError``, and enforces
  ``schema_version == 1``, ISO-8601-like timestamps, string IDs,
  list-shaped ``evidence`` and ``parent_event_ids`` fields, and a
  ``summary`` length cap of 2048 characters.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone
from typing import Any, ClassVar

from arnold_pipelines.megaplan.cloud.redact import redact_payload, redact_text
from arnold_pipelines.megaplan.maintenance.identity import (
    MAINTENANCE_SCHEMA_VERSION,
    canonical_json,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REQUIRED_M1_FIELDS: tuple[str, ...] = (
    "event_id",
    "ts",
    "type",
    "actor",
    "scope",
    "outcome",
    "summary",
)

REQUIRED_LIST_FIELDS: tuple[str, ...] = (
    "evidence",
    "parent_event_ids",
)

REQUIRED_NULLABLE_STRING_FIELDS: tuple[str, ...] = (
    "next_expected_event",
    "deadline_ts",
    "trigger_event_id",
)

OPTIONAL_NULLABLE_STRING_FIELDS: tuple[str, ...] = (
    "incident_id",
    "session_id",
    "initiative",
    "plan",
    "problem_id",
    "supersedes_event_id",
    "attempt_id",
)

#: Maintenance event kinds routed through the strict Maintenance codec.
#: These exactly mirror the closed Maintenance ``EventKind`` vocabulary
#: (detection / efficiency_analysis / audit_report).  An incident event whose
#: ``type`` is one of these AND whose payload carries the canonical
#: Maintenance occurrence identity is routed through the strict codec
#: (``strict_loads`` on the Maintenance event contract) instead of the legacy
#: permissive M1 validation; every other event keeps the legacy behavior
#: unchanged, including unknown-field preservation.
MAINTENANCE_EVENT_TYPES: frozenset[str] = frozenset(
    {"detection", "efficiency_analysis", "audit_report"}
)

#: Legacy occurrence-only row kinds.  Detection / efficiency_analysis /
#: audit_report rows keep the occurrence-only idempotency key so legacy M2
#: detection, analysis, and audit consumers (and M2 replay) remain
#: byte-compatible.  Only Operational lifecycle rows (see
#: :func:`is_operational_lifecycle_row`) derive the strict action key.
LEGACY_OCCURRENCE_ONLY_KINDS: frozenset[str] = frozenset(
    {"detection", "efficiency_analysis", "audit_report"}
)

#: The five frozen coordinates every canonical operational action key binds:
#: schema version, canonical occurrence digest, action type, policy version,
#: and target identity.  The tuple is the persisted compatibility contract;
#: it must never be reordered or re-keyed.
OPERATIONAL_KEY_COORDINATES: tuple[str, ...] = (
    "schema_version",
    "occurrence_digest",
    "action_kind",
    "policy_version",
    "target",
)

_SHA256_HEX = frozenset("0123456789abcdef")

# ---------------------------------------------------------------------------
# NBF strict records (kept beside, but deliberately independent from, the
# permissive M1 envelope).  These records are closed contracts: callers may
# extend ``evidence`` but may not silently add top-level fields.
# ---------------------------------------------------------------------------

NBF_SCHEMA_VERSION = 1


def _required(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _strict_record_fields(payload: dict[str, Any], fields: set[str], name: str) -> None:
    unknown = set(payload) - fields
    if unknown:
        raise ValueError(f"{name} unknown fields: {sorted(unknown)}")
    missing = fields - set(payload)
    if missing:
        raise ValueError(f"{name} missing fields: {sorted(missing)}")


def _strict_record_fields_with_optional(
    payload: dict[str, Any],
    required: set[str],
    optional: set[str],
    name: str,
) -> None:
    """Validate a closed record with explicitly optional top-level fields."""
    unknown = set(payload) - required - optional
    if unknown:
        raise ValueError(f"{name} unknown fields: {sorted(unknown)}")
    missing = required - set(payload)
    if missing:
        raise ValueError(f"{name} missing fields: {sorted(missing)}")


def _sha256_identity(value: Any, name: str) -> None:
    if not isinstance(value, str) or len(value) != 64 or any(c not in _SHA256_HEX for c in value):
        raise ValueError(f"{name} must be a canonical sha256 identity")


def _positive_pid(value: Any, name: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")


def _finite_nonnegative(value: Any, name: str) -> None:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) or value < 0:
        raise ValueError(f"{name} must be finite and non-negative")


def _iso_timestamp(value: Any, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be an ISO-8601 timestamp")
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{name} must be an ISO-8601 timestamp") from exc


def _digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _positive_cgroup_delta(value: Any) -> bool:
    """Return true only for explicit, positive cgroup accounting evidence."""
    if not isinstance(value, dict) or value.get("positive") is not True:
        return False
    delta = value.get("delta_bytes", value.get("delta"))
    return isinstance(delta, (int, float)) and not isinstance(delta, bool) and math.isfinite(delta) and delta > 0


def _typed_worker_identity(value: Any, name: str = "worker_identity") -> None:
    """Validate the minimum durable process/RPC identity shape.

    A truthy string or arbitrary mapping is not enough to correlate a death
    with an admitted worker.  The watchdog's ``WorkerIdentity`` serializes
    this same host/pid/boot triple (and may include richer optional fields).
    """
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be a typed object")
    for field_name in ("host", "pid", "boot_id"):
        if field_name not in value:
            raise ValueError(f"{name}.{field_name} is required")
    if not isinstance(value["host"], str) or not value["host"].strip():
        raise ValueError(f"{name}.host must be non-empty")
    _positive_pid(value["pid"], f"{name}.pid")
    if not isinstance(value["boot_id"], str) or not value["boot_id"].strip():
        raise ValueError(f"{name}.boot_id must be non-empty")
    if "identity_digest" in value:
        digest = value["identity_digest"]
        if isinstance(digest, str) and digest.startswith("sha256:"):
            digest = digest[7:]
        _sha256_identity(digest, f"{name}.identity_digest")


class DispositionMode(str, Enum):
    in_band = "in_band"
    observed = "observed"


class DispositionSubject(str, Enum):
    worker = "worker"
    external_process = "external_process"
    non_worker_lifecycle = "non_worker_lifecycle"


class Signal(str, Enum):
    SIGINT = "SIGINT"
    SIGTERM = "SIGTERM"
    SIGKILL = "SIGKILL"


class KillerKind(str, Enum):
    launcher_timeout = "launcher_timeout"
    resident_supervisor = "resident_supervisor"
    watchdog = "watchdog"
    ensure_watchdog = "ensure_watchdog"
    kernel_cgroup_oom = "kernel_cgroup_oom"
    external_unknown = "external_unknown"
    lifecycle_supervisor = "lifecycle_supervisor"


class CauseKind(str, Enum):
    timeout = "timeout"
    terminate = "terminate"
    escalation = "escalation"
    wedge = "wedge"
    restack = "restack"
    cgroup_oom = "cgroup_oom"
    observed_dead_unknown = "observed_dead_unknown"
    lifecycle_shutdown = "lifecycle_shutdown"


@dataclass(frozen=True)
class SemanticDispatchFingerprint:
    value: str
    components: dict[str, Any] = field(default_factory=dict)
    schema_version: int = NBF_SCHEMA_VERSION

    FIELDS = {"schema_version", "value", "components"}
    VOLATILE = frozenset({"logical_dispatch_id", "dispatch_family_id", "admission_attempt", "attempt", "route_liveness_digest", "route_liveness_generation", "timestamp", "retry_count", "pid", "process_incarnation", "provider_probe_observation"})

    @classmethod
    def derive(cls, *, phase: str, selected_spec: str, model_family: str, **components: Any) -> "SemanticDispatchFingerprint":
        durable = {"phase": phase, "selected_spec": selected_spec.strip(), "model_family": model_family}
        durable.update({k: v for k, v in components.items() if k not in cls.VOLATILE})
        return cls(_digest(durable), durable)

    compute = derive
    from_components = derive

    def to_dict(self) -> dict[str, Any]:
        return {"schema_version": self.schema_version, "value": self.value, "components": dict(self.components)}

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SemanticDispatchFingerprint":
        _strict_record_fields(payload, cls.FIELDS, cls.__name__)
        obj = cls(**payload)
        if not isinstance(obj.value, str) or len(obj.value) != 64:
            raise ValueError("semantic fingerprint value must be sha256")
        if _digest({k: v for k, v in obj.components.items()}) != obj.value and obj.components:
            # derive() includes all canonical components; tolerate legacy value
            # records with no components, but never accept malformed identities.
            raise ValueError("semantic fingerprint does not match components")
        if any(key in obj.components for key in cls.VOLATILE):
            raise ValueError("semantic fingerprint contains volatile identity")
        return obj


@dataclass(frozen=True)
class ProviderFailureKey:
    value: str
    phase: str
    selected_spec: str
    provider_failure_class: str
    provider_epoch_identity: str
    version: int = 1

    FIELDS = {"version", "value", "phase", "selected_spec", "provider_failure_class", "provider_epoch_identity"}

    @classmethod
    def derive(cls, *, phase: str, selected_spec: str, provider_failure_class: str, provider_epoch_identity: str, version: int = 1) -> "ProviderFailureKey":
        material = {"version": version, "phase": phase, "selected_spec": selected_spec.strip(), "provider_failure_class": provider_failure_class, "provider_epoch_identity": provider_epoch_identity}
        return cls(_digest(material), **{k: material[k] for k in ("phase", "selected_spec", "provider_failure_class", "provider_epoch_identity")}, version=version)

    compute = derive

    def to_dict(self) -> dict[str, Any]:
        return {"version": self.version, "value": self.value, "phase": self.phase, "selected_spec": self.selected_spec, "provider_failure_class": self.provider_failure_class, "provider_epoch_identity": self.provider_epoch_identity}

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ProviderFailureKey":
        _strict_record_fields(payload, cls.FIELDS, cls.__name__)
        obj = cls(**payload)
        expected = cls.derive(phase=obj.phase, selected_spec=obj.selected_spec, provider_failure_class=obj.provider_failure_class, provider_epoch_identity=obj.provider_epoch_identity, version=obj.version)
        if obj.value != expected.value:
            raise ValueError("provider failure key does not match canonical components")
        if any(not _required(getattr(obj, k), k) for k in ("phase", "selected_spec", "provider_failure_class", "provider_epoch_identity")):
            raise ValueError("provider failure key has incomplete identity")
        return obj


@dataclass(frozen=True)
class WorkerDisposition:
    disposition_id: str
    mode: str
    plan_id: str
    phase: str
    dispatch_family_id: str
    logical_dispatch_id: str
    admission_receipt_id: str
    semantic_dispatch_fingerprint: str
    selected_spec: str
    killer_kind: str
    killer_identity: str
    cause_kind: str
    signal: str
    elapsed_s: float
    worker_identity: Any
    observed_at: str
    evidence: Any
    victim_pid: int | None = None
    victim_process_start_identity: str | None = None
    process_group_identity: str | None = None
    timeout_source: str | None = None
    ladder_step: str | None = None
    confirmation_event_id: str | None = None
    schema_version: int = NBF_SCHEMA_VERSION
    event_type: str = "worker_disposition"

    FIELDS = {"schema_version", "event_type", "disposition_id", "mode", "plan_id", "phase", "dispatch_family_id", "logical_dispatch_id", "admission_receipt_id", "semantic_dispatch_fingerprint", "selected_spec", "killer_kind", "killer_identity", "cause_kind", "signal", "elapsed_s", "worker_identity", "victim_pid", "victim_process_start_identity", "process_group_identity", "timeout_source", "ladder_step", "confirmation_event_id", "observed_at", "evidence"}

    def __post_init__(self) -> None:
        if self.schema_version != NBF_SCHEMA_VERSION:
            raise ValueError("unsupported WorkerDisposition schema_version")
        if self.event_type != "worker_disposition":
            raise ValueError("WorkerDisposition event_type is fixed")
        for n in ("disposition_id", "plan_id", "phase", "dispatch_family_id", "logical_dispatch_id", "admission_receipt_id", "semantic_dispatch_fingerprint", "selected_spec", "killer_identity", "observed_at"):
            _required(getattr(self, n), f"WorkerDisposition.{n}")
        if self.mode not in {m.value for m in DispositionMode} or self.signal not in {s.value for s in Signal} or self.killer_kind not in {k.value for k in KillerKind} or self.cause_kind not in {c.value for c in CauseKind}:
            raise ValueError("WorkerDisposition contains an invalid enum")
        _typed_worker_identity(self.worker_identity)
        _sha256_identity(self.semantic_dispatch_fingerprint, "semantic_dispatch_fingerprint")
        _finite_nonnegative(self.elapsed_s, "elapsed_s")
        if self.victim_pid is not None:
            _positive_pid(self.victim_pid, "victim_pid")
        if self.victim_pid is not None and self.victim_process_start_identity is not None:
            _required(self.victim_process_start_identity, "victim_process_start_identity")
        _iso_timestamp(self.observed_at, "observed_at")
        if self.killer_kind == KillerKind.kernel_cgroup_oom.value and not _positive_cgroup_delta(self.evidence):
            raise ValueError("cgroup OOM requires positive evidence")

    def to_dict(self) -> dict[str, Any]:
        return {name: getattr(self, name) for name in ("schema_version", "event_type", "disposition_id", "mode", "plan_id", "phase", "dispatch_family_id", "logical_dispatch_id", "admission_receipt_id", "semantic_dispatch_fingerprint", "selected_spec", "killer_kind", "killer_identity", "cause_kind", "signal", "elapsed_s", "worker_identity", "victim_pid", "victim_process_start_identity", "process_group_identity", "timeout_source", "ladder_step", "confirmation_event_id", "observed_at", "evidence")}

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "WorkerDisposition":
        _strict_record_fields(payload, cls.FIELDS, cls.__name__)
        return cls(**payload)

    @classmethod
    def deterministic_id(cls, *, receipt: str, signal: str, ladder_step: str | None = None) -> str:
        return _digest({"schema_version": NBF_SCHEMA_VERSION, "receipt": receipt, "signal": signal, "ladder_step": ladder_step})


@dataclass(frozen=True)
class ObservedProcessDeath:
    observation_id: str
    subject: str
    observation_source: str
    known_context_fields: dict[str, Any]
    unknown_context_fields: tuple[str, ...]
    victim_identity_evidence: Any
    cause_kind: str
    killer_kind: str
    signal: str | None
    positive_cgroup_delta: Any
    observed_at: str
    evidence: Any
    schema_version: int = NBF_SCHEMA_VERSION
    event_type: str = "observed_process_death"
    FIELDS = {"schema_version", "event_type", "observation_id", "subject", "observation_source", "known_context_fields", "unknown_context_fields", "victim_identity_evidence", "cause_kind", "killer_kind", "signal", "positive_cgroup_delta", "observed_at", "evidence"}

    def __post_init__(self) -> None:
        if self.schema_version != NBF_SCHEMA_VERSION or self.event_type != "observed_process_death":
            raise ValueError("invalid observed process death schema")
        _required(self.observation_id, "observation_id")
        if self.subject not in {DispositionSubject.worker.value, DispositionSubject.external_process.value}:
            raise ValueError("ObservedProcessDeath subject must be worker or external_process")
        if self.cause_kind not in {CauseKind.observed_dead_unknown.value, CauseKind.cgroup_oom.value}:
            raise ValueError("observed death must remain an explicit unknown/OOM cause")
        if not isinstance(self.observation_source, str) or not self.observation_source:
            raise ValueError("observation source is required")
        if not isinstance(self.known_context_fields, dict) or not isinstance(self.unknown_context_fields, (tuple, list)):
            raise ValueError("observed death context must be typed")
        if not isinstance(self.victim_identity_evidence, dict):
            raise ValueError("victim identity evidence must be a typed object")
        if not self.victim_identity_evidence:
            raise ValueError("victim identity evidence is required")
        if any(not isinstance(item, str) or not item for item in self.unknown_context_fields):
            raise ValueError("unknown context fields must be non-empty strings")
        _iso_timestamp(self.observed_at, "observed_at")
        if self.cause_kind == CauseKind.cgroup_oom.value:
            if self.killer_kind != KillerKind.kernel_cgroup_oom.value or not _positive_cgroup_delta(self.positive_cgroup_delta):
                raise ValueError("cgroup OOM requires positive cgroup evidence")
        else:
            if self.killer_kind != KillerKind.external_unknown.value or self.signal is not None:
                raise ValueError("unknown death must use external_unknown and no signal")

    def to_dict(self) -> dict[str, Any]:
        return {n: getattr(self, n) for n in ("schema_version", "event_type", "observation_id", "subject", "observation_source", "known_context_fields", "unknown_context_fields", "victim_identity_evidence", "cause_kind", "killer_kind", "signal", "positive_cgroup_delta", "observed_at", "evidence")}

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ObservedProcessDeath":
        _strict_record_fields(payload, cls.FIELDS, cls.__name__)
        return cls(**payload)


@dataclass(frozen=True)
class NonWorkerSignalDisposition:
    disposition_id: str
    subject: str
    lifecycle_identity: str
    killer_identity: str
    cause_kind: str
    signal: str
    victim_pid_or_group: str
    victim_process_start_identity: str
    observed_at: str
    evidence: Any
    confirmation_event_id: str | None = None
    schema_version: int = NBF_SCHEMA_VERSION
    event_type: str = "non_worker_signal_disposition"
    FIELDS = {"schema_version", "event_type", "disposition_id", "subject", "lifecycle_identity", "killer_identity", "cause_kind", "signal", "victim_pid_or_group", "victim_process_start_identity", "confirmation_event_id", "observed_at", "evidence"}

    def __post_init__(self) -> None:
        if self.schema_version != NBF_SCHEMA_VERSION or self.event_type != "non_worker_signal_disposition":
            raise ValueError("invalid non-worker disposition schema")
        if self.subject != DispositionSubject.non_worker_lifecycle.value or self.signal not in {s.value for s in Signal} or self.cause_kind not in {CauseKind.lifecycle_shutdown.value}:
            raise ValueError("invalid non-worker disposition subject or signal")
        for n in ("disposition_id", "lifecycle_identity", "killer_identity", "victim_pid_or_group", "victim_process_start_identity", "observed_at"):
            _required(getattr(self, n), n)
        _iso_timestamp(self.observed_at, "observed_at")

    def to_dict(self) -> dict[str, Any]:
        return {n: getattr(self, n) for n in ("schema_version", "event_type", "disposition_id", "subject", "lifecycle_identity", "killer_identity", "cause_kind", "signal", "victim_pid_or_group", "victim_process_start_identity", "confirmation_event_id", "observed_at", "evidence")}

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "NonWorkerSignalDisposition":
        _strict_record_fields(payload, cls.FIELDS, cls.__name__)
        return cls(**payload)


@dataclass(frozen=True)
class ChangedPrecondition:
    event_id: str
    producer_kind: str
    producer_version: str
    plan_id: str
    phase: str
    reason: str
    authoritative_subject: str
    before_content_id: str
    after_content_id: str
    evidence_event_id: str
    evidence_digest: str
    recorded_at: str
    actor: str
    dispatch_family_id: str | None = None
    logical_dispatch_id: str | None = None
    source_revision: str | None = None
    runtime_vector: Any = None
    interpreter_identity: str | None = None
    route_identity: str | None = None
    timeout_policy_identity: str | None = None
    repair_commit_sha: str | None = None
    provider_failure_key_before: str | None = None
    provider_failure_key_after: str | None = None
    # Keep the authoritative source material in the event.  This is not a
    # trust boundary: it lets replay recompute the content identities instead
    # of accepting a caller's well-formed hexadecimal digest.
    before_snapshot: Any = None
    after_snapshot: Any = None
    evidence_snapshot: Any = None
    schema_version: int = NBF_SCHEMA_VERSION
    event_type: str = "changed_precondition"
    # This is deliberately not part of the wire record.  A producer-created
    # object carries the typed source handles that were actually read; a
    # caller cannot manufacture an authoritative event by round-tripping a
    # dictionary of hashes and snapshots.
    _source_handles: tuple[Any, Any] | None = field(default=None, init=False, repr=False, compare=False)
    ALLOWED_REASONS = frozenset({"source_revision_changed", "runtime_generation_changed", "seed_or_interpreter_binding_changed", "timeout_policy_changed", "authorized_route_changed", "provider_recovery_verified", "verified_repair_committed"})

    def __post_init__(self) -> None:
        if self.schema_version != NBF_SCHEMA_VERSION:
            raise ValueError("unsupported changed-precondition schema_version")
        if self.event_type != "changed_precondition" or self.reason not in self.ALLOWED_REASONS:
            raise ValueError("unsupported changed-precondition reason")
        for n in ("event_id", "producer_kind", "producer_version", "plan_id", "phase", "authoritative_subject", "before_content_id", "after_content_id", "evidence_event_id", "evidence_digest", "recorded_at", "actor"):
            _required(getattr(self, n), n)
        if self.before_content_id == self.after_content_id:
            raise ValueError("changed precondition requires unequal authoritative identities")
        for n in ("before_content_id", "after_content_id", "evidence_digest"):
            _sha256_identity(getattr(self, n), n)
        if self.before_snapshot is None or self.after_snapshot is None or self.evidence_snapshot is None:
            raise ValueError("changed precondition requires authoritative snapshots")
        if _digest(self.before_snapshot) != self.before_content_id:
            raise ValueError("before content identity does not match authoritative source")
        if _digest(self.after_snapshot) != self.after_content_id:
            raise ValueError("after content identity does not match authoritative source")
        if _digest(self.evidence_snapshot) != self.evidence_digest:
            raise ValueError("evidence identity does not match authoritative source")
        for n in ("provider_failure_key_before", "provider_failure_key_after"):
            value = getattr(self, n)
            if value is not None:
                _sha256_identity(value, n)
        if self.provider_failure_key_before is not None or self.provider_failure_key_after is not None:
            for snapshot, key_name, field_name in (
                (self.before_snapshot, self.provider_failure_key_before, "provider_failure_key_before"),
                (self.after_snapshot, self.provider_failure_key_after, "provider_failure_key_after"),
            ):
                if not isinstance(snapshot, dict) or snapshot.get("provider_failure_key") != key_name:
                    raise ValueError(f"{field_name} is not derived from its authoritative source")
        _iso_timestamp(self.recorded_at, "recorded_at")
        expected_event = _digest({"reason": self.reason, "before": self.before_content_id, "after": self.after_content_id, "evidence": self.evidence_event_id})
        if self.event_id != expected_event:
            raise ValueError("changed precondition event identity does not match content/evidence")
        fixed = {
            "source_revision_changed": ("source_revision", "1"),
            "runtime_generation_changed": ("runtime_generation", "1"),
            "seed_or_interpreter_binding_changed": ("seed_or_interpreter_binding", "1"),
            "timeout_policy_changed": ("timeout_policy", "1"),
            "authorized_route_changed": ("authorized_route", "1"),
            "provider_recovery_verified": ("provider_probe", "1"),
            "verified_repair_committed": ("verified_repair", "1"),
        }
        if (self.producer_kind, self.producer_version) != fixed[self.reason]:
            raise ValueError("producer identity is fixed by reason")
        if self.reason == "provider_recovery_verified" and self.provider_failure_key_before != self.provider_failure_key_after:
            raise ValueError("provider recovery cannot change provider failure key")

    def to_dict(self) -> dict[str, Any]:
        return {"schema_version": self.schema_version, "event_type": self.event_type, **{n: getattr(self, n) for n in ("event_id", "producer_kind", "producer_version", "plan_id", "phase", "dispatch_family_id", "logical_dispatch_id", "reason", "authoritative_subject", "before_content_id", "after_content_id", "evidence_event_id", "evidence_digest", "source_revision", "runtime_vector", "interpreter_identity", "route_identity", "timeout_policy_identity", "repair_commit_sha", "provider_failure_key_before", "provider_failure_key_after", "before_snapshot", "after_snapshot", "evidence_snapshot", "recorded_at", "actor")}}

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ChangedPrecondition":
        fields = {f.name for f in cls.__dataclass_fields__.values()}
        _strict_record_fields(payload, fields, cls.__name__)
        raise ValueError("changed precondition requires a typed authoritative source handle")

    @classmethod
    def produce(cls, **_: Any) -> "ChangedPrecondition":
        raise ValueError("ChangedPrecondition.produce is not an authoritative producer; use a reason-specific producer")


def _validate_changed_precondition_wire(
    payload: dict[str, Any],
    *,
    authoritative_event: ChangedPrecondition | None = None,
    allow_persisted: bool = False,
) -> dict[str, Any]:
    """Validate the persisted shape without treating wire data as authority.

    The authoritative handles are intentionally process-local producer state,
    so persisted replay can validate integrity and identity but cannot mint a
    new producer object from a caller dictionary.
    """
    if authoritative_event is None and not allow_persisted:
        raise ValueError("changed precondition requires a typed authoritative source handle")
    fields = {f.name for f in ChangedPrecondition.__dataclass_fields__.values() if f.init}
    _strict_record_fields(payload, fields, ChangedPrecondition.__name__)
    if payload.get("schema_version") != NBF_SCHEMA_VERSION or payload.get("event_type") != "changed_precondition":
        raise ValueError("invalid changed-precondition schema")
    if payload.get("reason") not in ChangedPrecondition.ALLOWED_REASONS:
        raise ValueError("unsupported changed-precondition reason")
    for name in ("event_id", "producer_kind", "producer_version", "plan_id", "phase", "authoritative_subject", "before_content_id", "after_content_id", "evidence_event_id", "evidence_digest", "recorded_at", "actor"):
        _required(payload.get(name), f"changed_precondition.{name}")
    for name in ("before_content_id", "after_content_id", "evidence_digest"):
        _sha256_identity(payload.get(name), name)
    if payload["before_content_id"] == payload["after_content_id"]:
        raise ValueError("changed precondition requires unequal authoritative identities")
    for snapshot_name, identity_name in (("before_snapshot", "before_content_id"), ("after_snapshot", "after_content_id")):
        snapshot = payload.get(snapshot_name)
        if snapshot is None or _digest(snapshot) != payload[identity_name]:
            raise ValueError(f"{snapshot_name} does not match its content identity")
        if not isinstance(snapshot, dict) or snapshot.get("authority_kind") != payload["reason"]:
            raise ValueError(f"{snapshot_name} is not reason-specific")
        _required(snapshot.get("source_version"), f"{snapshot_name}.source_version")
        _required(snapshot.get("source_identity"), f"{snapshot_name}.source_identity")
        if snapshot.get("subject") != payload["authoritative_subject"]:
            raise ValueError(f"{snapshot_name} subject mismatch")
    evidence = payload.get("evidence_snapshot")
    if evidence is None or _digest(evidence) != payload["evidence_digest"] or evidence.get("event_id") != payload["evidence_event_id"] if isinstance(evidence, dict) else True:
        raise ValueError("evidence snapshot does not match its identity")
    expected_event = _digest({"reason": payload["reason"], "before": payload["before_content_id"], "after": payload["after_content_id"], "evidence": payload["evidence_event_id"]})
    if payload["event_id"] != expected_event:
        raise ValueError("changed precondition event identity does not match content/evidence")
    if (payload["producer_kind"], payload["producer_version"]) != _PRECONDITION_PRODUCERS[payload["reason"]]:
        raise ValueError("producer identity is fixed by reason")
    for snapshot, key_name, field_name in ((payload["before_snapshot"], payload.get("provider_failure_key_before"), "provider_failure_key_before"), (payload["after_snapshot"], payload.get("provider_failure_key_after"), "provider_failure_key_after")):
        if key_name is not None:
            _sha256_identity(key_name, field_name)
            if snapshot.get("provider_failure_key") != key_name:
                raise ValueError(f"{field_name} is not derived from its source snapshot")
    if payload["reason"] == "provider_recovery_verified" and payload.get("provider_failure_key_before") != payload.get("provider_failure_key_after"):
        raise ValueError("provider recovery cannot change provider failure key")
    if authoritative_event is not None:
        if not isinstance(authoritative_event, ChangedPrecondition):
            raise ValueError("changed precondition authority must be a typed event")
        _validate_producer_binding(authoritative_event)
        if authoritative_event.to_dict() != payload:
            raise ValueError("changed precondition is not producer-derived")
    _iso_timestamp(payload["recorded_at"], "changed_precondition.recorded_at")
    return dict(payload)


_PRECONDITION_PRODUCERS = {
    "source_revision_changed": ("source_revision", "1"),
    "runtime_generation_changed": ("runtime_generation", "1"),
    "seed_or_interpreter_binding_changed": ("seed_or_interpreter_binding", "1"),
    "timeout_policy_changed": ("timeout_policy", "1"),
    "authorized_route_changed": ("authorized_route", "1"),
    "provider_recovery_verified": ("provider_probe", "1"),
    "verified_repair_committed": ("verified_repair", "1"),
}


@dataclass(frozen=True)
class _AuthoritativeSourceHandle:
    """Typed input read by one closed changed-precondition producer.

    ``content`` is fixture/source material, not a pre-digested event.  The
    reason-specific identity and version are part of the handle so the reader
    controls the canonical wire snapshot and provider-key binding.
    """

    reason: ClassVar[str]
    source_version: str
    authoritative_subject: str
    source_identity: str
    content: Any
    provider_failure_key: str | None = None

    def read(self) -> dict[str, Any]:
        _required(self.source_version, "source_version")
        _required(self.authoritative_subject, "authoritative_subject")
        _required(self.source_identity, "source_identity")
        if self.provider_failure_key is not None:
            _sha256_identity(self.provider_failure_key, "provider_failure_key")
        return {
            "authority_kind": self.reason,
            "source_version": self.source_version,
            "source_identity": self.source_identity,
            "subject": self.authoritative_subject,
            "content": self.content,
            **({"provider_failure_key": self.provider_failure_key} if self.provider_failure_key is not None else {}),
        }


@dataclass(frozen=True)
class SourceRevisionSource(_AuthoritativeSourceHandle):
    reason: ClassVar[str] = "source_revision_changed"


@dataclass(frozen=True)
class RuntimeGenerationSource(_AuthoritativeSourceHandle):
    reason: ClassVar[str] = "runtime_generation_changed"


@dataclass(frozen=True)
class SeedInterpreterBindingSource(_AuthoritativeSourceHandle):
    reason: ClassVar[str] = "seed_or_interpreter_binding_changed"


@dataclass(frozen=True)
class TimeoutPolicySource(_AuthoritativeSourceHandle):
    reason: ClassVar[str] = "timeout_policy_changed"


@dataclass(frozen=True)
class AuthorizedRouteSource(_AuthoritativeSourceHandle):
    reason: ClassVar[str] = "authorized_route_changed"


@dataclass(frozen=True)
class ProviderRecoverySource(_AuthoritativeSourceHandle):
    reason: ClassVar[str] = "provider_recovery_verified"


@dataclass(frozen=True)
class VerifiedRepairSource(_AuthoritativeSourceHandle):
    reason: ClassVar[str] = "verified_repair_committed"


# ``Handle`` aliases make the boundary explicit to callers without creating a
# second producer API.
SourceRevisionHandle = SourceRevisionSource
RuntimeGenerationHandle = RuntimeGenerationSource
SeedInterpreterBindingHandle = SeedInterpreterBindingSource
TimeoutPolicyHandle = TimeoutPolicySource
AuthorizedRouteHandle = AuthorizedRouteSource
ProviderRecoveryHandle = ProviderRecoverySource
VerifiedRepairHandle = VerifiedRepairSource


def _authoritative_source(reason: str, source: Any, side: str) -> dict[str, Any]:
    if not isinstance(source, _AuthoritativeSourceHandle) or source.reason != reason:
        raise ValueError(f"{reason} {side} source must be the matching typed handle")
    return source.read()


def _source_handles_for(obj: ChangedPrecondition) -> tuple[_AuthoritativeSourceHandle, _AuthoritativeSourceHandle]:
    handles = getattr(obj, "_source_handles", None)
    if not isinstance(handles, tuple) or len(handles) != 2 or not all(isinstance(item, _AuthoritativeSourceHandle) for item in handles):
        raise ValueError("changed precondition has no producer-bound source handles")
    before, after = handles
    if before.reason != obj.reason or after.reason != obj.reason:
        raise ValueError("changed precondition source reason is not fixed")
    return before, after


def _validate_producer_binding(obj: ChangedPrecondition) -> None:
    before_handle, after_handle = _source_handles_for(obj)
    if before_handle.authoritative_subject != obj.authoritative_subject or after_handle.authoritative_subject != obj.authoritative_subject:
        raise ValueError("changed precondition subject is not producer-bound")
    if before_handle.read() != obj.before_snapshot or after_handle.read() != obj.after_snapshot:
        raise ValueError("changed precondition snapshots are not producer-derived")
    if before_handle.provider_failure_key != obj.provider_failure_key_before or after_handle.provider_failure_key != obj.provider_failure_key_after:
        raise ValueError("changed precondition provider keys are not producer-derived")


def _produce_authoritative(
    reason: str,
    *,
    plan_id: str,
    phase: str,
    authoritative_subject: str,
    before: Any,
    after: Any,
    evidence_event_id: str,
    evidence: Any,
    actor: str,
    dispatch_family_id: str | None = None,
    logical_dispatch_id: str | None = None,
    provider_failure_key_before: str | None = None,
    provider_failure_key_after: str | None = None,
) -> ChangedPrecondition:
    producer_kind, producer_version = _PRECONDITION_PRODUCERS.get(reason, (None, None))
    if producer_kind is None:
        raise ValueError("unsupported changed-precondition reason")
    before_handle, after_handle = before, after
    before_source = _authoritative_source(reason, before_handle, "before")
    after_source = _authoritative_source(reason, after_handle, "after")
    if before_source["subject"] != after_source["subject"]:
        raise ValueError("authoritative source subject changed")
    if authoritative_subject != before_source["subject"]:
        raise ValueError("authoritative subject is not producer-bound")
    if not isinstance(evidence, dict) or evidence.get("event_id") != evidence_event_id:
        raise ValueError("evidence must be the cited authoritative event")
    before_key = before_source.get("provider_failure_key")
    after_key = after_source.get("provider_failure_key")
    supplied_keys = (provider_failure_key_before, provider_failure_key_after)
    if any(value is not None for value in supplied_keys):
        raise ValueError("provider-failure keys must be derived from authoritative sources")
    if reason == "provider_recovery_verified":
        if not isinstance(before_key, str) or before_key != after_key:
            raise ValueError("provider recovery requires one unchanged provider failure key")
    before_id, after_id = _digest(before_source), _digest(after_source)
    if before_id == after_id:
        raise ValueError("changed precondition requires changed authoritative content")
    subject = before_source["subject"]
    result = ChangedPrecondition(
        event_id=_digest({"reason": reason, "before": before_id, "after": after_id, "evidence": evidence_event_id}),
        producer_kind=producer_kind,
        producer_version=producer_version,
        plan_id=plan_id,
        phase=phase,
        reason=reason,
        authoritative_subject=subject,
        before_content_id=before_id,
        after_content_id=after_id,
        evidence_event_id=evidence_event_id,
        evidence_digest=_digest(evidence),
        recorded_at=datetime.now(timezone.utc).isoformat(),
        actor=actor,
        dispatch_family_id=dispatch_family_id,
        logical_dispatch_id=logical_dispatch_id,
        provider_failure_key_before=before_key,
        provider_failure_key_after=after_key,
        before_snapshot=before_source,
        after_snapshot=after_source,
        evidence_snapshot=evidence,
    )
    object.__setattr__(result, "_source_handles", (before_handle, after_handle))
    _validate_producer_binding(result)
    return result


@dataclass(frozen=True)
class ReservationReconciled:
    reconciliation_id: str
    plan_id: str
    phase: str
    projection_key: str
    logical_dispatch_id: str
    admission_receipt_id: str
    reservation_event_id: str
    semantic_dispatch_fingerprint: str
    resolution: str
    evidence_kind: str
    evidence_event_ids: tuple[str, ...]
    launch_state_identity: str
    observed_at: str
    recorded_at: str
    actor: str
    worker_identity: Any = None
    victim_pid: int | None = None
    victim_process_start_identity: str | None = None
    running_receipt_identity: str | None = None
    terminal_outcome_event_id: str | None = None
    schema_version: int = NBF_SCHEMA_VERSION
    event_type: str = "reservation_reconciled"
    event_id: str | None = None
    RESOLUTIONS = frozenset({"released_no_launch", "terminal_outcome_recovered", "permanent_hold_ambiguous"})

    def __post_init__(self) -> None:
        if self.schema_version != NBF_SCHEMA_VERSION or self.event_type != "reservation_reconciled":
            raise ValueError("invalid reconciliation schema")
        if self.resolution not in self.RESOLUTIONS:
            raise ValueError("invalid reconciliation resolution")
        for n in ("reconciliation_id", "plan_id", "phase", "projection_key", "logical_dispatch_id", "admission_receipt_id", "reservation_event_id", "semantic_dispatch_fingerprint", "evidence_kind", "launch_state_identity", "observed_at", "recorded_at", "actor"):
            _required(getattr(self, n), n)
        if not isinstance(self.evidence_event_ids, (tuple, list)) or not self.evidence_event_ids or any(not isinstance(x, str) or not x for x in self.evidence_event_ids):
            raise ValueError("reconciliation requires positive evidence event IDs")
        if self.resolution == "released_no_launch" and self.launch_state_identity != "not_started":
            raise ValueError("released_no_launch requires positive not_started evidence")
        if self.resolution == "terminal_outcome_recovered" and not self.terminal_outcome_event_id:
            raise ValueError("terminal recovery requires terminal outcome identity")

    def to_dict(self) -> dict[str, Any]:
        return {"schema_version": self.schema_version, "event_type": self.event_type, "event_id": self.event_id or self.reconciliation_id, **{n: (list(getattr(self, n)) if n == "evidence_event_ids" else getattr(self, n)) for n in ("reconciliation_id", "plan_id", "phase", "projection_key", "logical_dispatch_id", "admission_receipt_id", "reservation_event_id", "semantic_dispatch_fingerprint", "resolution", "evidence_kind", "evidence_event_ids", "launch_state_identity", "worker_identity", "victim_pid", "victim_process_start_identity", "running_receipt_identity", "terminal_outcome_event_id", "observed_at", "recorded_at", "actor")}}

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ReservationReconciled":
        _strict_record_fields(payload, {f.name for f in cls.__dataclass_fields__.values()}, cls.__name__)
        payload = dict(payload)
        payload["evidence_event_ids"] = tuple(payload["evidence_event_ids"])
        return cls(**payload)


def confirmation_ttl_s(scan_interval_s: float) -> float:
    if not isinstance(scan_interval_s, (int, float)) or isinstance(scan_interval_s, bool) or not math.isfinite(scan_interval_s) or scan_interval_s <= 0:
        raise ValueError("scan_interval_s must be finite and positive")
    return min(max(2.0 * scan_interval_s, 30.0), 300.0)


def semantic_dispatch_fingerprint(**kwargs: Any) -> str:
    phase = kwargs.pop("phase")
    selected_spec = kwargs.pop("selected_spec")
    family = kwargs.pop("model_family", kwargs.pop("family", ""))
    return SemanticDispatchFingerprint.derive(phase=phase, selected_spec=selected_spec, model_family=family, **kwargs).value


def provider_failure_key(**kwargs: Any) -> str:
    return ProviderFailureKey.derive(**kwargs).value


def produce_changed_precondition(
    reason: str,
    *,
    plan_id: str,
    phase: str,
    authoritative_subject: str,
    before: Any,
    after: Any,
    evidence_event_id: str,
    evidence: Any,
    actor: str,
    dispatch_family_id: str | None = None,
    logical_dispatch_id: str | None = None,
    source_revision: str | None = None,
    runtime_vector: Any = None,
    interpreter_identity: str | None = None,
    route_identity: str | None = None,
    timeout_policy_identity: str | None = None,
    repair_commit_sha: str | None = None,
    provider_failure_key_before: str | None = None,
    provider_failure_key_after: str | None = None,
) -> ChangedPrecondition:
    raise ValueError("generic changed-precondition production is not an authority; use a reason-specific producer")


def _produce_reason_specific(
    reason: str,
    *,
    plan_id: str,
    phase: str,
    authoritative_subject: str,
    before: Any,
    after: Any,
    evidence_event_id: str,
    evidence: Any,
    actor: str,
    dispatch_family_id: str | None = None,
    logical_dispatch_id: str | None = None,
    source_revision: str | None = None,
    runtime_vector: Any = None,
    interpreter_identity: str | None = None,
    route_identity: str | None = None,
    timeout_policy_identity: str | None = None,
    repair_commit_sha: str | None = None,
    provider_failure_key_before: str | None = None,
    provider_failure_key_after: str | None = None,
) -> ChangedPrecondition:
    return _produce_authoritative(
        reason,
        plan_id=plan_id,
        phase=phase,
        authoritative_subject=authoritative_subject,
        before=before,
        after=after,
        evidence_event_id=evidence_event_id,
        evidence=evidence,
        actor=actor,
        dispatch_family_id=dispatch_family_id,
        logical_dispatch_id=logical_dispatch_id,
        provider_failure_key_before=provider_failure_key_before,
        provider_failure_key_after=provider_failure_key_after,
    )


def produce_source_revision_changed(*, plan_id: str, phase: str, authoritative_subject: str, before: Any, after: Any, evidence_event_id: str, evidence: Any, actor: str, dispatch_family_id: str | None = None, logical_dispatch_id: str | None = None, source_revision: str | None = None, runtime_vector: Any = None, interpreter_identity: str | None = None, route_identity: str | None = None, timeout_policy_identity: str | None = None, repair_commit_sha: str | None = None, provider_failure_key_before: str | None = None, provider_failure_key_after: str | None = None) -> ChangedPrecondition:
    return _produce_reason_specific("source_revision_changed", plan_id=plan_id, phase=phase, authoritative_subject=authoritative_subject, before=before, after=after, evidence_event_id=evidence_event_id, evidence=evidence, actor=actor, dispatch_family_id=dispatch_family_id, logical_dispatch_id=logical_dispatch_id, source_revision=source_revision, runtime_vector=runtime_vector, interpreter_identity=interpreter_identity, route_identity=route_identity, timeout_policy_identity=timeout_policy_identity, repair_commit_sha=repair_commit_sha, provider_failure_key_before=provider_failure_key_before, provider_failure_key_after=provider_failure_key_after)


def produce_runtime_generation_changed(*, plan_id: str, phase: str, authoritative_subject: str, before: Any, after: Any, evidence_event_id: str, evidence: Any, actor: str, dispatch_family_id: str | None = None, logical_dispatch_id: str | None = None, source_revision: str | None = None, runtime_vector: Any = None, interpreter_identity: str | None = None, route_identity: str | None = None, timeout_policy_identity: str | None = None, repair_commit_sha: str | None = None, provider_failure_key_before: str | None = None, provider_failure_key_after: str | None = None) -> ChangedPrecondition:
    return _produce_reason_specific("runtime_generation_changed", plan_id=plan_id, phase=phase, authoritative_subject=authoritative_subject, before=before, after=after, evidence_event_id=evidence_event_id, evidence=evidence, actor=actor, dispatch_family_id=dispatch_family_id, logical_dispatch_id=logical_dispatch_id, source_revision=source_revision, runtime_vector=runtime_vector, interpreter_identity=interpreter_identity, route_identity=route_identity, timeout_policy_identity=timeout_policy_identity, repair_commit_sha=repair_commit_sha, provider_failure_key_before=provider_failure_key_before, provider_failure_key_after=provider_failure_key_after)


def produce_seed_or_interpreter_binding_changed(*, plan_id: str, phase: str, authoritative_subject: str, before: Any, after: Any, evidence_event_id: str, evidence: Any, actor: str, dispatch_family_id: str | None = None, logical_dispatch_id: str | None = None, source_revision: str | None = None, runtime_vector: Any = None, interpreter_identity: str | None = None, route_identity: str | None = None, timeout_policy_identity: str | None = None, repair_commit_sha: str | None = None, provider_failure_key_before: str | None = None, provider_failure_key_after: str | None = None) -> ChangedPrecondition:
    return _produce_reason_specific("seed_or_interpreter_binding_changed", plan_id=plan_id, phase=phase, authoritative_subject=authoritative_subject, before=before, after=after, evidence_event_id=evidence_event_id, evidence=evidence, actor=actor, dispatch_family_id=dispatch_family_id, logical_dispatch_id=logical_dispatch_id, source_revision=source_revision, runtime_vector=runtime_vector, interpreter_identity=interpreter_identity, route_identity=route_identity, timeout_policy_identity=timeout_policy_identity, repair_commit_sha=repair_commit_sha, provider_failure_key_before=provider_failure_key_before, provider_failure_key_after=provider_failure_key_after)


def produce_timeout_policy_changed(*, plan_id: str, phase: str, authoritative_subject: str, before: Any, after: Any, evidence_event_id: str, evidence: Any, actor: str, dispatch_family_id: str | None = None, logical_dispatch_id: str | None = None, source_revision: str | None = None, runtime_vector: Any = None, interpreter_identity: str | None = None, route_identity: str | None = None, timeout_policy_identity: str | None = None, repair_commit_sha: str | None = None, provider_failure_key_before: str | None = None, provider_failure_key_after: str | None = None) -> ChangedPrecondition:
    return _produce_reason_specific("timeout_policy_changed", plan_id=plan_id, phase=phase, authoritative_subject=authoritative_subject, before=before, after=after, evidence_event_id=evidence_event_id, evidence=evidence, actor=actor, dispatch_family_id=dispatch_family_id, logical_dispatch_id=logical_dispatch_id, source_revision=source_revision, runtime_vector=runtime_vector, interpreter_identity=interpreter_identity, route_identity=route_identity, timeout_policy_identity=timeout_policy_identity, repair_commit_sha=repair_commit_sha, provider_failure_key_before=provider_failure_key_before, provider_failure_key_after=provider_failure_key_after)


def produce_authorized_route_changed(*, plan_id: str, phase: str, authoritative_subject: str, before: Any, after: Any, evidence_event_id: str, evidence: Any, actor: str, dispatch_family_id: str | None = None, logical_dispatch_id: str | None = None, source_revision: str | None = None, runtime_vector: Any = None, interpreter_identity: str | None = None, route_identity: str | None = None, timeout_policy_identity: str | None = None, repair_commit_sha: str | None = None, provider_failure_key_before: str | None = None, provider_failure_key_after: str | None = None) -> ChangedPrecondition:
    return _produce_reason_specific("authorized_route_changed", plan_id=plan_id, phase=phase, authoritative_subject=authoritative_subject, before=before, after=after, evidence_event_id=evidence_event_id, evidence=evidence, actor=actor, dispatch_family_id=dispatch_family_id, logical_dispatch_id=logical_dispatch_id, source_revision=source_revision, runtime_vector=runtime_vector, interpreter_identity=interpreter_identity, route_identity=route_identity, timeout_policy_identity=timeout_policy_identity, repair_commit_sha=repair_commit_sha, provider_failure_key_before=provider_failure_key_before, provider_failure_key_after=provider_failure_key_after)


def produce_provider_recovery_verified(*, plan_id: str, phase: str, authoritative_subject: str, before: Any, after: Any, evidence_event_id: str, evidence: Any, actor: str, dispatch_family_id: str | None = None, logical_dispatch_id: str | None = None, source_revision: str | None = None, runtime_vector: Any = None, interpreter_identity: str | None = None, route_identity: str | None = None, timeout_policy_identity: str | None = None, repair_commit_sha: str | None = None, provider_failure_key_before: str | None = None, provider_failure_key_after: str | None = None) -> ChangedPrecondition:
    return _produce_reason_specific("provider_recovery_verified", plan_id=plan_id, phase=phase, authoritative_subject=authoritative_subject, before=before, after=after, evidence_event_id=evidence_event_id, evidence=evidence, actor=actor, dispatch_family_id=dispatch_family_id, logical_dispatch_id=logical_dispatch_id, source_revision=source_revision, runtime_vector=runtime_vector, interpreter_identity=interpreter_identity, route_identity=route_identity, timeout_policy_identity=timeout_policy_identity, repair_commit_sha=repair_commit_sha, provider_failure_key_before=provider_failure_key_before, provider_failure_key_after=provider_failure_key_after)


def produce_verified_repair_committed(*, plan_id: str, phase: str, authoritative_subject: str, before: Any, after: Any, evidence_event_id: str, evidence: Any, actor: str, dispatch_family_id: str | None = None, logical_dispatch_id: str | None = None, source_revision: str | None = None, runtime_vector: Any = None, interpreter_identity: str | None = None, route_identity: str | None = None, timeout_policy_identity: str | None = None, repair_commit_sha: str | None = None, provider_failure_key_before: str | None = None, provider_failure_key_after: str | None = None) -> ChangedPrecondition:
    return _produce_reason_specific("verified_repair_committed", plan_id=plan_id, phase=phase, authoritative_subject=authoritative_subject, before=before, after=after, evidence_event_id=evidence_event_id, evidence=evidence, actor=actor, dispatch_family_id=dispatch_family_id, logical_dispatch_id=logical_dispatch_id, source_revision=source_revision, runtime_vector=runtime_vector, interpreter_identity=interpreter_identity, route_identity=route_identity, timeout_policy_identity=timeout_policy_identity, repair_commit_sha=repair_commit_sha, provider_failure_key_before=provider_failure_key_before, provider_failure_key_after=provider_failure_key_after)


@dataclass(frozen=True)
class SupervisionConfirmation:
    """Durable two-scan proof identity and policy state."""
    confirmation_id: str
    site_id: str
    subject_class: str
    victim_pid: int
    victim_process_start_identity: str
    relevant_progress_identity: str
    supervisor_incarnation_identity: str
    cause_kind: str
    scan_interval_s: float
    first_observed_at: str
    expires_at: float
    evidence_digest: str
    plan_id: str | None = None
    admission_receipt_id: str | None = None
    confirmation_policy_identity: str = "default-v1"
    schema_version: int = NBF_SCHEMA_VERSION

    FIELDS = {"schema_version", "confirmation_id", "site_id", "subject_class", "plan_id", "admission_receipt_id", "victim_pid", "victim_process_start_identity", "relevant_progress_identity", "supervisor_incarnation_identity", "cause_kind", "scan_interval_s", "confirmation_policy_identity", "first_observed_at", "expires_at", "evidence_digest"}

    def __post_init__(self) -> None:
        if self.schema_version != NBF_SCHEMA_VERSION:
            raise ValueError("unsupported supervision confirmation schema_version")
        for n in ("confirmation_id", "site_id", "subject_class", "victim_process_start_identity", "relevant_progress_identity", "supervisor_incarnation_identity", "cause_kind", "first_observed_at", "evidence_digest"):
            _required(getattr(self, n), n)
        if not isinstance(self.victim_pid, int) or isinstance(self.victim_pid, bool) or self.victim_pid <= 0:
            raise ValueError("victim_pid must be positive")
        if not isinstance(self.scan_interval_s, (int, float)) or isinstance(self.scan_interval_s, bool) or not math.isfinite(self.scan_interval_s) or self.scan_interval_s <= 0:
            raise ValueError("scan_interval_s must be finite and positive")
        if not isinstance(self.expires_at, (int, float)) or isinstance(self.expires_at, bool) or not math.isfinite(self.expires_at) or self.expires_at <= 0:
            raise ValueError("expires_at must be positive")
        _iso_timestamp(self.first_observed_at, "first_observed_at")
        _sha256_identity(self.evidence_digest, "evidence_digest")
        expected_ttl = confirmation_ttl_s(self.scan_interval_s)
        first_ts = datetime.fromisoformat(self.first_observed_at.replace("Z", "+00:00")).timestamp()
        if not math.isclose(self.expires_at, first_ts + expected_ttl, rel_tol=0.0, abs_tol=1e-6):
            raise ValueError("expires_at does not match the confirmation TTL policy")
        expected = _digest({"confirmation_schema_version": self.schema_version, "site_id": self.site_id, "subject_class": self.subject_class, "victim_pid": self.victim_pid, "victim_process_start_identity": self.victim_process_start_identity, "relevant_progress_identity": self.relevant_progress_identity, "supervisor_incarnation_identity": self.supervisor_incarnation_identity, "cause_kind": self.cause_kind})
        if self.confirmation_id != expected:
            raise ValueError("confirmation identity does not match proof fields")

    def to_dict(self) -> dict[str, Any]:
        return {n: getattr(self, n) for n in ("schema_version", "confirmation_id", "site_id", "subject_class", "plan_id", "admission_receipt_id", "victim_pid", "victim_process_start_identity", "relevant_progress_identity", "supervisor_incarnation_identity", "cause_kind", "scan_interval_s", "confirmation_policy_identity", "first_observed_at", "expires_at", "evidence_digest")}

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SupervisionConfirmation":
        _strict_record_fields(payload, cls.FIELDS, cls.__name__)
        return cls(**payload)


def validate_nbf_event(
    payload: dict[str, Any],
    *,
    _changed_precondition: ChangedPrecondition | None = None,
    _allow_persisted_changed_precondition: bool = False,
) -> dict[str, Any]:
    """Validate one NBF event and return a defensive canonical copy."""
    if not isinstance(payload, dict):
        raise ValueError("NBF event must be an object")
    typ = payload.get("event_type")
    if typ == "worker_disposition":
        return WorkerDisposition.from_dict(payload).to_dict()
    if typ == "observed_process_death":
        return ObservedProcessDeath.from_dict(payload).to_dict()
    if typ == "non_worker_signal_disposition":
        return NonWorkerSignalDisposition.from_dict(payload).to_dict()
    if typ == "changed_precondition":
        return _validate_changed_precondition_wire(
            payload,
            authoritative_event=_changed_precondition,
            allow_persisted=_allow_persisted_changed_precondition,
        )
    if typ == "reservation_reconciled":
        return ReservationReconciled.from_dict(payload).to_dict()
    # Transaction records are intentionally closed but their payloads are
    # simple scalar identity maps.  Reject unknown fields while allowing
    # forward-compatible evidence under the event-specific ``extra`` map.
    required: dict[str, set[str]] = {
        "admission_reserved": {"schema_version", "event_type", "event_id", "plan_id", "phase", "projection_key", "reservation_key", "semantic_dispatch_fingerprint", "logical_dispatch_id", "dispatch_family_id", "physical_door_id", "selected_spec", "expected_projection_version", "changed_precondition_event_id", "recorded_at", "actor"},
        "worker_terminal_outcome": {"schema_version", "event_type", "event_id", "terminal_outcome_id", "outcome_kind", "plan_id", "phase", "projection_key", "reservation_key", "dispatch_family_id", "logical_dispatch_id", "admission_receipt_id", "reservation_event_id", "semantic_dispatch_fingerprint", "selected_spec", "physical_door_id", "launch_state", "worker_identity", "started_at", "finished_at", "success_payload", "terminal_failure", "provider_evidence", "provider_failure_key", "disposition_id", "execution_context_identity", "recorded_at", "actor"},
        "provider_route_child_reserved": {"schema_version", "event_type", "event_id", "plan_id", "phase", "projection_key", "reservation_key", "expected_projection_version", "transition_kind", "from_spec", "to_spec", "parent_logical_dispatch_id", "parent_terminal_event_id", "authorizing_event_id", "configured_fallback_chain_identity", "precondition_identity", "child_dispatch_family_id", "child_logical_dispatch_id", "child_physical_door_id", "child_semantic_dispatch_fingerprint", "child_route_liveness_identity", "consumed_changed_precondition_event_id", "receipt_derivation_version", "recorded_at", "actor"},
        "changed_precondition_consumed": {"schema_version", "event_type", "event_id", "changed_precondition_event_id", "recorded_at", "actor"},
        "supervision_confirmation_observed": {"schema_version", "event_type", "event_id", "confirmation_id", "site_id", "subject_class", "plan_id", "admission_receipt_id", "victim_pid", "victim_process_start_identity", "relevant_progress_identity", "supervisor_incarnation_identity", "cause_kind", "scan_interval_s", "confirmation_policy_identity", "first_observed_at", "expires_at", "evidence_digest", "recorded_at", "actor"},
        "supervision_confirmation_consumed": {"schema_version", "event_type", "event_id", "confirmation_id", "prior_confirmation_event_id", "site_id", "replacement_reason", "second_observed_at", "second_evidence_digest", "victim_pid", "victim_process_start_identity", "relevant_progress_identity", "supervisor_incarnation_identity", "cause_kind", "scan_interval_s", "expires_at", "confirmation_policy_identity", "disposition_id", "recorded_at", "actor"},
        "supervision_confirmation_replaced": {"schema_version", "event_type", "event_id", "confirmation_id", "prior_confirmation_event_id", "site_id", "replacement_reason", "second_observed_at", "second_evidence_digest", "victim_pid", "victim_process_start_identity", "relevant_progress_identity", "supervisor_incarnation_identity", "cause_kind", "disposition_id", "recorded_at", "actor", "subject_class", "plan_id", "admission_receipt_id", "scan_interval_s", "confirmation_policy_identity", "first_observed_at", "expires_at", "evidence_digest"},
        "supervision_confirmation_expired": {"schema_version", "event_type", "event_id", "confirmation_id", "prior_confirmation_event_id", "site_id", "replacement_reason", "second_observed_at", "second_evidence_digest", "victim_pid", "victim_process_start_identity", "relevant_progress_identity", "supervisor_incarnation_identity", "cause_kind", "disposition_id", "recorded_at", "actor"},
        "provider_observation": {"schema_version", "event_type", "event_id", "observation_id", "provider_failure_key", "selected_spec", "phase", "provider_failure_class", "provider_epoch_identity", "recorded_at", "actor"},
        "provider_probe_started": {"schema_version", "event_type", "event_id", "probe_lease_id", "provider_failure_key", "expires_at", "recorded_at", "actor"},
        "provider_probe_result": {"schema_version", "event_type", "event_id", "probe_lease_id", "provider_failure_key", "passed", "evidence_digest", "recorded_at", "actor"},
        "provider_recovery_verified": {"schema_version", "event_type", "event_id", "changed_precondition_event_id", "provider_failure_key_before", "provider_failure_key_after", "recorded_at", "actor"},
        "controlled_adapter_state": {"schema_version", "event_type", "event_id", "reservation_event_id", "admission_receipt_id", "physical_door_id", "launch_state_identity", "recorded_at", "actor"},
    }
    fields = required.get(typ)
    if fields is None:
        raise ValueError(f"unsupported NBF event_type: {typ!r}")
    if typ == "admission_reserved":
        _strict_record_fields_with_optional(
            payload,
            fields | {"admission_receipt_id"},
            {"primary_spec", "configured_fallback_chain_identity", "execution_context_identity"},
            str(typ),
        )
    elif typ == "worker_terminal_outcome":
        unknown = set(payload) - (fields | {
            "primary_spec", "configured_fallback_chain_identity",
            # Context fields were added after the first terminal ledger
            # format.  They are accepted on new records while old records
            # remain readable for replay/projection compatibility.
            "provider", "route_liveness_kind", "route_liveness_identity",
            "route_liveness_digest",
        })
        missing = fields - set(payload)
        if unknown:
            raise ValueError(f"{typ} unknown fields: {sorted(unknown)}")
        if missing:
            raise ValueError(f"{typ} missing fields: {sorted(missing)}")
        for n in ("provider", "route_liveness_kind", "route_liveness_identity", "route_liveness_digest"):
            if n in payload and payload[n] is not None and not isinstance(payload[n], str):
                raise ValueError(f"{typ}.{n} must be a string or null")
    elif typ == "controlled_adapter_state":
        _strict_record_fields_with_optional(
            payload,
            fields,
            {"phase", "selected_spec", "primary_spec", "logical_dispatch_id", "worker_identity", "started_at", "finished_at", "operation_evidence", "physical_operation_evidence"},
            str(typ),
        )
    elif typ in {"provider_probe_started", "provider_probe_result"}:
        _strict_record_fields_with_optional(
            payload,
            fields,
            {"parent_reservation_event_id", "phase", "route_identity"},
            str(typ),
        )
    elif typ == "provider_route_child_reserved":
        _strict_record_fields_with_optional(
            payload,
            fields,
            {"execution_context_identity"},
            str(typ),
        )
    else:
        _strict_record_fields(payload, fields, str(typ))
    if payload.get("schema_version") != NBF_SCHEMA_VERSION:
        raise ValueError("unsupported NBF schema version")
    for n in ("event_id", "event_type", "recorded_at", "actor"):
        _required(payload.get(n), f"{typ}.{n}")
    if typ not in {"supervision_confirmation_observed", "supervision_confirmation_replaced", "supervision_confirmation_consumed", "supervision_confirmation_expired"}:
        _iso_timestamp(payload["recorded_at"], f"{typ}.recorded_at")
    if typ in {"admission_reserved", "worker_terminal_outcome", "provider_route_child_reserved"}:
        for n in ("plan_id", "phase", "projection_key"):
            _required(payload.get(n), f"{typ}.{n}")
        _sha256_identity(payload["semantic_dispatch_fingerprint"] if typ != "provider_route_child_reserved" else payload["child_semantic_dispatch_fingerprint"], f"{typ}.semantic_dispatch_fingerprint")
        if typ == "admission_reserved":
            for n in ("reservation_key", "logical_dispatch_id", "dispatch_family_id", "physical_door_id", "selected_spec", "admission_receipt_id"):
                _required(payload.get(n), f"{typ}.{n}")
            if not isinstance(payload.get("expected_projection_version"), int) or payload["expected_projection_version"] < 0:
                raise ValueError("admission_reserved expected_projection_version must be non-negative")
        elif typ == "provider_route_child_reserved":
            for n in ("reservation_key", "transition_kind", "from_spec", "to_spec", "parent_logical_dispatch_id", "parent_terminal_event_id", "authorizing_event_id", "configured_fallback_chain_identity", "precondition_identity", "child_dispatch_family_id", "child_logical_dispatch_id", "child_physical_door_id", "child_route_liveness_identity", "receipt_derivation_version"):
                _required(payload.get(n), f"{typ}.{n}")
            if not isinstance(payload.get("expected_projection_version"), int) or payload["expected_projection_version"] < 0:
                raise ValueError("provider_route_child_reserved expected_projection_version must be non-negative")
    if typ == "worker_terminal_outcome" and payload.get("outcome_kind") not in {"success", "ordinary_terminal_failure", "provider_exhausted", "worker_disposition"}:
        raise ValueError("invalid terminal outcome kind")
    if typ == "worker_terminal_outcome":
        kind = payload.get("outcome_kind")
        if payload.get("launch_state") != "accepted":
            raise ValueError("terminal outcome requires accepted launch")
        for n in ("terminal_outcome_id", "reservation_key", "dispatch_family_id", "logical_dispatch_id", "admission_receipt_id", "reservation_event_id", "selected_spec", "physical_door_id", "worker_identity", "started_at", "finished_at"):
            if n in {"worker_identity"}:
                _typed_worker_identity(payload.get(n), f"{typ}.{n}")
            else:
                _required(payload.get(n), f"{typ}.{n}")
        _iso_timestamp(payload["started_at"], f"{typ}.started_at")
        _iso_timestamp(payload["finished_at"], f"{typ}.finished_at")
        if kind == "worker_disposition" and (not payload.get("disposition_id") or payload.get("provider_evidence") or payload.get("terminal_failure")):
            raise ValueError("invalid worker disposition terminal payload")
        if kind == "worker_disposition" and payload.get("success_payload") is not None:
            raise ValueError("invalid worker disposition success payload")
        if kind == "success" and (payload.get("provider_evidence") or payload.get("terminal_failure") or payload.get("disposition_id")):
            raise ValueError("invalid success terminal payload")
        if kind != "success" and payload.get("success_payload") is not None:
            raise ValueError("success_payload is only valid for success terminals")
        if kind == "ordinary_terminal_failure" and (payload.get("provider_evidence") or payload.get("disposition_id")):
            raise ValueError("invalid ordinary terminal payload")
        if kind == "ordinary_terminal_failure" and payload.get("success_payload") is not None:
            raise ValueError("invalid ordinary terminal success payload")
        if kind == "provider_exhausted" and payload.get("terminal_failure") is not None:
            raise ValueError("invalid provider terminal failure payload")
        if kind == "provider_exhausted":
            provider = payload.get("provider_evidence")
            if not isinstance(provider, dict):
                raise ValueError("provider terminal requires structured evidence")
            for n in ("observation_id", "retryability_class", "exhausted_attempt_count", "terminal_provider_evidence_id", "precondition_identity", "provider_epoch_identity", "provider_failure_key", "observed_at"):
                if n != "exhausted_attempt_count":
                    _required(provider.get(n), f"{typ}.provider_evidence.{n}")
            attempts = provider.get("exhausted_attempt_count")
            if not isinstance(attempts, int) or isinstance(attempts, bool) or attempts < 1:
                raise ValueError(f"{typ}.provider_evidence.exhausted_attempt_count must be positive")
            _sha256_identity(provider["provider_failure_key"], f"{typ}.provider_evidence.provider_failure_key")
            _iso_timestamp(provider["observed_at"], f"{typ}.provider_evidence.observed_at")
            if payload.get("provider_failure_key") not in (None, provider["provider_failure_key"]):
                raise ValueError("terminal provider failure key disagrees with evidence")
        elif payload.get("provider_evidence") not in (None, {}):
            raise ValueError("non-provider terminal cannot carry provider evidence")
        if payload.get("provider_failure_key") is not None:
            _sha256_identity(payload["provider_failure_key"], f"{typ}.provider_failure_key")
        _typed_worker_identity(payload.get("worker_identity"), f"{typ}.worker_identity")
        if kind == "worker_disposition":
            _required(payload.get("disposition_id"), f"{typ}.disposition_id")
        elif payload.get("disposition_id") is not None:
            raise ValueError("only worker disposition terminals carry disposition_id")
    if typ == "supervision_confirmation_observed":
        confirmation_fields = {k: payload[k] for k in SupervisionConfirmation.FIELDS}
        SupervisionConfirmation.from_dict(confirmation_fields)
    if typ == "supervision_confirmation_replaced":
        confirmation_fields = {k: payload[k] for k in SupervisionConfirmation.FIELDS}
        SupervisionConfirmation.from_dict(confirmation_fields)
    if typ in {"supervision_confirmation_consumed", "supervision_confirmation_expired"}:
        for n in ("confirmation_id", "prior_confirmation_event_id", "site_id", "second_observed_at", "victim_process_start_identity", "relevant_progress_identity", "supervisor_incarnation_identity", "cause_kind"):
            _required(payload.get(n), f"{typ}.{n}")
        _positive_pid(payload.get("victim_pid"), f"{typ}.victim_pid")
        _iso_timestamp(payload["second_observed_at"], f"{typ}.second_observed_at")
        _sha256_identity(payload["second_evidence_digest"], f"{typ}.second_evidence_digest")
    if typ == "provider_route_child_reserved" and "child_admission_receipt_id" in payload:
        raise ValueError("composite reservation cannot contain child receipt ID")
    if typ in {"provider_probe_started", "provider_probe_result"}:
        _sha256_identity(payload["provider_failure_key"], f"{typ}.provider_failure_key")
        if typ == "provider_probe_result":
            if not isinstance(payload.get("passed"), bool):
                raise ValueError("provider probe result passed must be boolean")
            _sha256_identity(payload["evidence_digest"], f"{typ}.evidence_digest")
    if typ == "controlled_adapter_state":
        # ``ambiguous`` is retained solely so pre-attempt-6 ledgers can be
        # projected and reconciled as permanent holds. New controlled-door
        # appends reject it in the ledger; it is not a lifecycle state.
        if payload.get("launch_state_identity") not in {"not_started", "entered", "accepted", "closed", "ambiguous"}:
            raise ValueError("controlled adapter state is invalid")
        _required(payload.get("reservation_event_id"), f"{typ}.reservation_event_id")
        _required(payload.get("admission_receipt_id"), f"{typ}.admission_receipt_id")
        _required(payload.get("physical_door_id"), f"{typ}.physical_door_id")
        if payload.get("launch_state_identity") == "accepted":
            for n in ("phase", "selected_spec", "primary_spec", "logical_dispatch_id", "worker_identity", "started_at", "finished_at"):
                if n not in payload:
                    raise ValueError(f"{typ}.{n} is required for accepted launch")
            _required(payload.get("phase"), f"{typ}.phase")
            _required(payload.get("selected_spec"), f"{typ}.selected_spec")
            _required(payload.get("primary_spec"), f"{typ}.primary_spec")
            _required(payload.get("logical_dispatch_id"), f"{typ}.logical_dispatch_id")
            _typed_worker_identity(payload.get("worker_identity"), f"{typ}.worker_identity")
            _iso_timestamp(payload.get("started_at"), f"{typ}.started_at")
            _iso_timestamp(payload.get("finished_at"), f"{typ}.finished_at")
    return dict(payload)


def receipt_id(*, reservation_event_id: str, plan_id: str, phase: str, dispatch_family_id: str, logical_dispatch_id: str, physical_door_id: str, semantic_dispatch_fingerprint: str, derivation_version: str = "1") -> str:
    return _digest({"receipt_derivation_version": derivation_version, "reservation_event_id": reservation_event_id, "plan_id": plan_id, "phase": phase, "dispatch_family_id": dispatch_family_id, "logical_dispatch_id": logical_dispatch_id, "physical_door_id": physical_door_id, "semantic_dispatch_fingerprint": semantic_dispatch_fingerprint})


def _record_to_json(self: Any) -> str:
    return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _record_from_json(cls: Any, raw: str) -> Any:
    try:
        value = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{cls.__name__} JSON must be one object") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{cls.__name__} JSON must be one object")
    return cls.from_dict(value)


for _record_type in (WorkerDisposition, ObservedProcessDeath, NonWorkerSignalDisposition, ChangedPrecondition, ReservationReconciled, SupervisionConfirmation, ProviderFailureKey, SemanticDispatchFingerprint):
    _record_type.to_json = _record_to_json  # type: ignore[attr-defined]
    _record_type.from_json = classmethod(_record_from_json)  # type: ignore[attr-defined]


def is_maintenance_event(event: dict[str, Any]) -> bool:
    """Return whether *event* is a strict Maintenance event (codec-routed).

    A Maintenance event is recognized by its closed kind vocabulary plus the
    canonical occurrence identity / event-kind markers that only the strict
    Maintenance contract carries.  Legacy incident events (including watchdog
    detections that predate the Maintenance contract) never carry
    ``occurrence_id``/``event_kind`` and therefore keep the legacy path.
    """
    return (
        isinstance(event, dict)
        and (
            event.get("type") in MAINTENANCE_EVENT_TYPES
            or event.get("event_kind") in MAINTENANCE_EVENT_TYPES
        )
        and "occurrence_id" in event
    )


# ---------------------------------------------------------------------------
# Lifecycle action idempotency keys (M3 Step 2, incident schema boundary)
# ---------------------------------------------------------------------------
# Operational lifecycle records (repair request, source change, installation,
# retrigger, progress observation, checkpoint verification, terminal
# verification, recurrence, human escalation) coexist for one canonical
# occurrence.  Their persisted idempotency keys are derived from the five
# frozen coordinates — schema version, canonical occurrence digest, action
# type, policy version, and target identity — so distinct actions for one
# occurrence get distinct keys while an exact retry reproduces the same key.
# Legacy detection / efficiency_analysis / audit_report rows keep the
# occurrence-only key (M2 compatibility): exactly one record per occurrence.


def _require_operational_coordinate(value: Any, *, what: str) -> str:
    """Return *value* when it is a non-empty string, else fail closed."""
    if not isinstance(value, str) or not value:
        raise ValueError(f"operational lifecycle row requires {what}")
    return value


def operational_action_key(
    *,
    schema_version: int,
    occurrence_digest: str,
    action_kind: str,
    policy_version: str,
    target: str,
) -> str:
    """Derive the canonical lifecycle action idempotency key.

    The key is the sha256 of the canonical JSON encoding of the five frozen
    coordinates (:data:`OPERATIONAL_KEY_COORDINATES`): schema version,
    canonical occurrence digest, action type, policy version, and target
    identity.  Distinct lifecycle actions for one occurrence therefore
    coexist with distinct keys, an exact retry reproduces the same key, and a
    change in any coordinate produces a different key.  Malformed or missing
    coordinates raise ``ValueError`` — a key is never derived from guessed
    values.

    This is the persisted compatibility contract consumed by the shared
    incident journal (T4): legacy rows keep occurrence-only keys via
    :func:`legacy_occurrence_idempotency_key`.
    """
    if schema_version != MAINTENANCE_SCHEMA_VERSION:
        raise ValueError(
            "operational action key requires schema_version "
            f"{MAINTENANCE_SCHEMA_VERSION}, got {schema_version!r}"
        )
    occurrence_digest = _require_operational_coordinate(
        occurrence_digest, what="occurrence digest"
    )
    if len(occurrence_digest) != 64 or any(
        char not in _SHA256_HEX for char in occurrence_digest
    ):
        raise ValueError(
            "operational action key requires a 64-character lowercase "
            "sha256 occurrence digest"
        )
    action_kind = _require_operational_coordinate(action_kind, what="action kind")
    policy_version = _require_operational_coordinate(
        policy_version, what="policy version"
    )
    target = _require_operational_coordinate(target, what="target identity")
    material = canonical_json(
        {
            "schema_version": schema_version,
            "occurrence_digest": occurrence_digest,
            "action_kind": action_kind,
            "policy_version": policy_version,
            "target": target,
        }
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def is_operational_lifecycle_row(event: Any) -> bool:
    """Return whether *event* is a persisted operational lifecycle row.

    An operational row carries the closed ``action_kind`` plus the canonical
    ``occurrence`` coordinate object (with ``canonical_digest``); legacy
    detection / efficiency_analysis / audit_report rows carry a plain
    occurrence-only ``occurrence_id`` and are never misread as operational.
    """
    return (
        isinstance(event, dict)
        and isinstance(event.get("action_kind"), str)
        and isinstance(event.get("occurrence"), dict)
        and isinstance(event["occurrence"].get("canonical_digest"), str)
    )


def legacy_occurrence_idempotency_key(event: Any) -> str:
    """Return the occurrence-only key retained for legacy rows.

    Legacy detection / efficiency_analysis / audit_report rows stay keyed by
    the occurrence identity alone (M2 compatibility): exactly one record per
    occurrence, and detection/analysis/audit consumers keep their lookups.
    A malformed row raises ``ValueError`` instead of guessing.
    """
    if not isinstance(event, dict):
        raise ValueError(
            "legacy occurrence idempotency key requires a dict event"
        )
    occurrence_id = event.get("occurrence_id")
    if not isinstance(occurrence_id, str) or not occurrence_id:
        raise ValueError(
            "legacy occurrence idempotency key requires a non-empty "
            "occurrence_id"
        )
    return occurrence_id


def _checkpoint_window_key(base_key: str, window: str) -> str:
    """Fold one canonical checkpoint window into a checkpoint action key.

    A policy-required checkpoint window is a distinct stable lifecycle
    identity: the four ``checkpoint_verification`` actions for one occurrence
    coexist (immediate / five_minute / one_hour / next_three_hour), while an
    exact retry of the SAME window reproduces the SAME key (dedup by window
    identity, never rewrite).  Applies ONLY to ``checkpoint_verification``
    rows; the five-coordinate action-key contract is unchanged for every
    other action and for direct callers.
    """
    return hashlib.sha256(
        canonical_json(
            {"base_key": base_key, "checkpoint_window": window}
        ).encode("utf-8")
    ).hexdigest()


def lifecycle_idempotency_key(event: Any) -> str:
    """Return the canonical persisted lifecycle idempotency key for *event*.

    Operational lifecycle rows derive the strict action key from schema
    version, canonical occurrence digest, action type, policy version, and
    target identity (see :func:`operational_action_key`); legacy
    detection / efficiency_analysis / audit_report rows keep the
    occurrence-only key.  The discriminator is exact: an operational row
    always carries ``action_kind`` plus the canonical ``occurrence``
    coordinate object, so a legacy row can never be routed to the strict key
    and an operational row can never collapse onto the occurrence-only key.
    """
    if is_operational_lifecycle_row(event):
        occurrence = event["occurrence"]
        policy = event.get("policy")
        target = event.get("target")
        if not isinstance(policy, dict) or not isinstance(target, dict):
            raise ValueError(
                "operational lifecycle row requires policy and target "
                "coordinate objects"
            )
        schema_version = event.get("schema_version")
        if schema_version != MAINTENANCE_SCHEMA_VERSION:
            raise ValueError(
                "operational lifecycle row requires schema_version "
                f"{MAINTENANCE_SCHEMA_VERSION}, got {schema_version!r}"
            )
        key = operational_action_key(
            schema_version=schema_version,
            occurrence_digest=occurrence["canonical_digest"],
            action_kind=event["action_kind"],
            policy_version=_require_operational_coordinate(
                policy.get("policy_version"), what="policy version"
            ),
            target=_require_operational_coordinate(
                target.get("target"), what="target identity"
            ),
        )
        if event["action_kind"] == "checkpoint_verification":
            payload = event.get("payload")
            if not isinstance(payload, dict):
                raise ValueError(
                    "checkpoint verification requires a payload object"
                )
            return _checkpoint_window_key(
                key,
                _require_operational_coordinate(
                    payload.get("checkpoint"), what="checkpoint window"
                ),
            )
        return key
    return legacy_occurrence_idempotency_key(event)


def operational_event_action_key(event: Any) -> str:
    """Derive the canonical action key for an ``OperationalEvent`` model.

    *event* must expose the frozen operational coordinates (``schema_version``,
    ``occurrence.canonical_digest``, ``action_kind.value``,
    ``policy.policy_version``, ``target.target``).  The function is
    duck-typed so the incident schema never imports the operational event
    envelope at module scope.
    """
    key = operational_action_key(
        schema_version=event.schema_version,
        occurrence_digest=event.occurrence.canonical_digest,
        action_kind=event.action_kind.value,
        policy_version=event.policy.policy_version,
        target=event.target.target,
    )
    if event.action_kind.value == "checkpoint_verification":
        return _checkpoint_window_key(
            key, _require_operational_coordinate(
                event.payload.checkpoint.value, what="checkpoint window"
            )
        )
    return key


def validate_maintenance_event(event: dict[str, Any]) -> dict[str, Any]:
    """Strict-route *event* through the canonical Maintenance codec.

    The event is decoded with ``strict_loads`` against the closed
    Maintenance event contract (missing/unknown fields and identity
    mismatches fail) and re-encoded canonically, so the stored payload is
    byte-stable and the canonical digest is reproducible.  Unknown fields
    are accepted ONLY inside the explicit ``extensions`` map.
    """
    from arnold_pipelines.megaplan.maintenance.events import MaintenanceEvent
    from arnold_pipelines.megaplan.maintenance.identity import (
        MaintenanceCodecError,
        canonical_dumps,
        strict_loads,
    )

    try:
        model = strict_loads(MaintenanceEvent, event)
    except MaintenanceCodecError as exc:
        raise ValueError(
            "maintenance event strict decode failed for type "
            f"{event.get('type')!r}: {exc}"
        ) from exc
    return json.loads(canonical_dumps(model))

MAX_SUMMARY_LENGTH: int = 2048
MAX_COMMITTED_OUTPUT_BYTES: int = 50 * 1024
MAX_STRUCTURED_FIELD_BYTES: int = 64 * 1024
_ALWAYS_ON_REDACTION_ENV: dict[str, str] = {}
_COMMITTED_OUTPUT_TRUNCATION_TEMPLATE = (
    "\n[truncated {omitted} bytes to satisfy the 50KB committed-output cap]"
)


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _check_required_field(
    event: dict[str, Any],
    field: str,
) -> None:
    """Raise ``ValueError`` if *field* is missing or not a non-empty string."""
    if field not in event:
        raise ValueError(f"incident event requires '{field}'")
    value = event[field]
    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"incident event '{field}' must be a non-empty string"
        )


def _check_list_field(
    event: dict[str, Any],
    field: str,
) -> None:
    """Raise ``ValueError`` if *field* is missing or not a list."""
    if field not in event:
        raise ValueError(f"incident event requires '{field}'")
    value = event[field]
    if not isinstance(value, list):
        raise ValueError(
            f"incident event '{field}' must be a list"
        )


def _check_string_or_none_field(
    event: dict[str, Any],
    field: str,
    *,
    required: bool,
) -> None:
    """Raise ``ValueError`` if *field* is missing or malformed."""
    if field not in event:
        if required:
            raise ValueError(f"incident event requires '{field}'")
        return
    value = event[field]
    if value is None:
        return
    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"incident event '{field}' must be a non-empty string or null"
        )


def _check_object_or_none_field(
    event: dict[str, Any],
    field: str,
) -> None:
    """Raise ``ValueError`` if an optional field is present but malformed."""
    if field not in event:
        return
    value = event[field]
    if value is None or isinstance(value, dict):
        return
    raise ValueError(
        f"incident event '{field}' must be an object or null"
    )


def _check_timestamp(value: str, field: str) -> None:
    """Loosely validate an ISO-8601-like timestamp.

    Requires at minimum ``YYYY-MM-DD`` with optional ``T`` time and
    ``Z``/offset suffix.  This is intentionally more permissive than
    ``datetime.fromisoformat`` to accept common variants.
    """
    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"incident event '{field}' must be an ISO-8601-like timestamp string"
        )
    stripped = value.strip()
    # Must have at least YYYY-MM-DD
    if len(stripped) < 10 or stripped[4] != "-" or stripped[7] != "-":
        raise ValueError(
            f"incident event '{field}' must be an ISO-8601-like timestamp (got {value!r})"
        )
    # The date portion must be digits (basic check)
    try:
        int(stripped[:4])
        int(stripped[5:7])
        int(stripped[8:10])
    except (ValueError, IndexError):
        raise ValueError(
            f"incident event '{field}' must be an ISO-8601-like timestamp (got {value!r})"
        )


def redact_incident_event(event: dict[str, Any]) -> dict[str, Any]:
    """Return a copy with write-path/publication fields redacted.

    Redaction is intentionally always-on for ledger/publication paths, even when
    cloud log redaction has been disabled via environment flags.
    """
    redacted = dict(event)
    if "summary" in redacted:
        redacted["summary"] = redact_text(
            redacted["summary"],
            env=_ALWAYS_ON_REDACTION_ENV,
        )
    for field in ("evidence", "links", "decision", "actions"):
        if field in redacted:
            redacted[field] = redact_payload(
                redacted[field],
                env=_ALWAYS_ON_REDACTION_ENV,
            )
    return redacted


def cap_committed_output_text(
    text: str,
    *,
    limit_bytes: int = MAX_COMMITTED_OUTPUT_BYTES,
) -> str:
    """Return *text* capped to *limit_bytes* UTF-8 bytes with a marker."""
    if limit_bytes <= 0:
        raise ValueError("limit_bytes must be positive")
    if not isinstance(text, str):
        raise ValueError("committed output must be a string")
    encoded = text.encode("utf-8")
    if len(encoded) <= limit_bytes:
        return text
    omitted = len(encoded) - limit_bytes
    suffix = _COMMITTED_OUTPUT_TRUNCATION_TEMPLATE.format(omitted=omitted)
    suffix_bytes = suffix.encode("utf-8")
    if len(suffix_bytes) >= limit_bytes:
        return suffix_bytes[:limit_bytes].decode("utf-8", errors="ignore")
    allowed = limit_bytes - len(suffix_bytes)
    truncated = encoded[:allowed].decode("utf-8", errors="ignore")
    while len((truncated + suffix).encode("utf-8")) > limit_bytes and truncated:
        truncated = truncated[:-1]
    return truncated + suffix


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def validate_incident_event(event: dict[str, Any]) -> dict[str, Any]:
    """Validate an incident event and return a normalized shallow copy.

    Validation rules (M1)
    ----------------------
    * *event* must be a ``dict``.
    * ``schema_version`` must be exactly ``1``.
    * Required string fields: ``event_id``, ``ts``, ``type``, ``actor``,
      ``scope``, ``outcome``, ``summary``.
    * Required nullable string fields: ``next_expected_event``,
      ``deadline_ts``, ``trigger_event_id``.
    * ``ts`` and present ``deadline_ts`` values must be ISO-8601-like
      (``YYYY-MM-DD...``).
    * ``summary`` length must be <= 2048 characters.
    * Required list fields: ``evidence``, ``parent_event_ids``.

    Forward compatibility
    ---------------------
    Unknown fields present in *event* are preserved in the returned
    shallow copy.

    Returns
    -------
    dict
        A shallow copy of *event* with all original keys intact.

    Raises
    ------
    ValueError
        If any validation rule is violated.  The message always names
        the offending field.
    """
    if not isinstance(event, dict):
        raise ValueError("incident event must be a dict")
    # Route only Maintenance event kinds through the strict codec; everything
    # else (including legacy extensions) keeps the permissive M1 path below.
    if is_maintenance_event(event):
        return validate_maintenance_event(event)
    # Reject expanding evidence before recursive regex redaction. This keeps a
    # malformed historical auditor event from consuming gigabytes while the
    # projection layer validates it, and prevents recursive report/decision
    # embedding from entering the append-only ledger in the first place.
    structured_bytes = 0
    for field in ("evidence", "links", "decision", "actions"):
        if field not in event:
            continue
        try:
            encoded = json.dumps(
                event[field],
                sort_keys=True,
                separators=(",", ":"),
                default=str,
            ).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"incident event '{field}' must be JSON serializable"
            ) from exc
        if len(encoded) > MAX_STRUCTURED_FIELD_BYTES:
            raise ValueError(
                f"incident event '{field}' must be <= {MAX_STRUCTURED_FIELD_BYTES} bytes "
                f"(got {len(encoded)})"
            )
        structured_bytes += len(encoded)
    if structured_bytes > MAX_STRUCTURED_FIELD_BYTES:
        raise ValueError(
            "incident event structured fields must be <= "
            f"{MAX_STRUCTURED_FIELD_BYTES} bytes in aggregate (got {structured_bytes})"
        )
    event = redact_incident_event(event)

    # ── schema_version ──────────────────────────────────────────────
    sv = event.get("schema_version")
    if sv != 1:
        raise ValueError(
            f"incident event schema_version must be 1 (got {sv!r})"
        )

    # ── required string fields ──────────────────────────────────────
    for field in REQUIRED_M1_FIELDS:
        _check_required_field(event, field)

    # ── summary length cap ──────────────────────────────────────────
    summary = event["summary"]
    if len(summary) > MAX_SUMMARY_LENGTH:
        raise ValueError(
            f"incident event 'summary' must be <= {MAX_SUMMARY_LENGTH} "
            f"characters (got {len(summary)})"
        )

    # ── required nullable string fields ─────────────────────────────
    for field in REQUIRED_NULLABLE_STRING_FIELDS:
        _check_string_or_none_field(event, field, required=True)

    for field in OPTIONAL_NULLABLE_STRING_FIELDS:
        _check_string_or_none_field(event, field, required=False)

    _check_object_or_none_field(event, "links")

    # ── timestamps ──────────────────────────────────────────────────
    _check_timestamp(event["ts"], "ts")
    deadline_ts = event["deadline_ts"]
    if deadline_ts is not None:
        _check_timestamp(deadline_ts, "deadline_ts")

    # ── required list fields ────────────────────────────────────────
    for field in REQUIRED_LIST_FIELDS:
        _check_list_field(event, field)

    # ── return normalized shallow copy (preserve unknown fields) ────
    return dict(event)
