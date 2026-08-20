"""Canonical Custody schema contracts for M7 controlled authoritative writers.

Defines the immutable, persistence-neutral CustodyTargetKey,
RepairOccurrenceKey, CustodyLease, and append-only CustodyLeaseEvent
models with strict required fields, canonical JSON/digest behavior,
idempotency key, causal predecessor, owner host/process-birth identity,
Run Authority grant/fence refs, WBC attempt ref, lease identity, expiry,
and monotonic custody_epoch.

All production gates and mutating effects remain disabled in M7;
this module defines schema contracts only.
"""

from __future__ import annotations

import hashlib
import json
import os
import socket
import subprocess
from dataclasses import dataclass, field, fields
from datetime import datetime, timezone
from typing import Any, ClassVar, Literal, Mapping

from arnold_pipelines.run_authority.contracts import (
    Contract,
    ContractError,
    IdentityConflict,
    RevisionConflict,
    canonical_json,
    payload_digest,
)

# ── Re-export run-authority contract primitives ──────────────────────────
__all__ = [
    "CustodyTargetKey",
    "RepairOccurrenceKey",
    "CustodyLease",
    "CustodyLeaseEvent",
    "CustodyLeaseEventType",
    "CustodyLeaseOutcome",
    "CUSTODY_LEASE_EVENT_TYPES",
    "CUSTODY_LEASE_OUTCOMES",
    "normalize_custody_target_key",
    "normalize_repair_occurrence_key",
    "normalize_custody_lease",
    "normalize_custody_lease_event",
    "build_custody_target_key",
    "build_repair_occurrence_key",
    "process_birth_identity",
    "target_digest",
    "occurrence_digest",
    "CUSTODY_TARGET_KEY_VERSION",
    "REPAIR_OCCURRENCE_KEY_VERSION",
    "CUSTODY_LEASE_VERSION",
    "CUSTODY_LEASE_EVENT_VERSION",
    "DEFAULT_LEASE_TTL_SECONDS",
    "DEFAULT_LEASE_GRACE_SECONDS",
    "MAXIMUM_LEASE_TTL_SECONDS",
    "DEFAULT_REPAIR_RECURRENCE_MINIMUM_INTERVAL_SECONDS",
]

# ── Schema version constants ─────────────────────────────────────────────
CUSTODY_TARGET_KEY_VERSION = 1
REPAIR_OCCURRENCE_KEY_VERSION = 1
CUSTODY_LEASE_VERSION = 1
CUSTODY_LEASE_EVENT_VERSION = 1

# ── Lease timing policy constants ────────────────────────────────────────

#: Default lease TTL in seconds (30 minutes).
DEFAULT_LEASE_TTL_SECONDS: int = 1800

#: Default grace period in seconds (5 minutes).
#: A lease is considered expired after TTL + grace.
DEFAULT_LEASE_GRACE_SECONDS: int = 300

#: Absolute maximum lease TTL in seconds (24 hours).
#: No lease may have a TTL exceeding this ceiling.
MAXIMUM_LEASE_TTL_SECONDS: int = 86400

# ── Repair recurrence policy constants ────────────────────────────────────

#: Minimum interval between consecutive repair dispatches for the same
#: recurrence identity in seconds (2 minutes).  The repair loop must not
#: dispatch the same problem signature more often than this floor.
DEFAULT_REPAIR_RECURRENCE_MINIMUM_INTERVAL_SECONDS: int = 120

# ── F01 repair-occurrence tuple (mirrored from writer_map for schema use) ─
F01_REPAIR_OCCURRENCE_FIELDS: tuple[str, ...] = (
    "environment",
    "session",
    "chain",
    "plan_revision",
    "phase",
    "task",
    "attempt",
    "normalized_failure_kind",
    "blocker_or_phase_result_hash",
    "fence",
)

# ── Lease event types ─────────────────────────────────────────────────────
CustodyLeaseEventType = Literal[
    "acquire",
    "renew",
    "transfer",
    "release",
    "expire",
    "fence",
    "conflict",
    "reconcile",
]

CUSTODY_LEASE_EVENT_TYPES: frozenset[CustodyLeaseEventType] = frozenset(
    {
        "acquire",
        "renew",
        "transfer",
        "release",
        "expire",
        "fence",
        "conflict",
        "reconcile",
    }
)

# ── Lease outcomes (non-owner terminal states) ────────────────────────────
CustodyLeaseOutcome = Literal[
    "owned",
    "not_owner_contended",
    "not_owner_stale_epoch",
    "not_owner_expired",
    "not_owner_released",
    "not_owner_transferred",
    "not_owner_fenced",
    "not_owner_conflict",
]

CUSTODY_LEASE_OUTCOMES: frozenset[CustodyLeaseOutcome] = frozenset(
    {
        "owned",
        "not_owner_contended",
        "not_owner_stale_epoch",
        "not_owner_expired",
        "not_owner_released",
        "not_owner_transferred",
        "not_owner_fenced",
        "not_owner_conflict",
    }
)

# ── Helper validators ────────────────────────────────────────────────────


def _required_str(value: str, name: str) -> str:
    """Validate a required non-empty string field."""
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"{name} must be a non-empty string")
    return value


def _required_nonneg_int(value: int, name: str) -> int:
    """Validate a required non-negative integer field."""
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ContractError(f"{name} must be a non-negative integer")
    return value


def _required_pos_int(value: int, name: str) -> int:
    """Validate a required positive integer field."""
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ContractError(f"{name} must be a positive integer")
    return value


def _optional_str(value: str | None, name: str, *, default: str = "") -> str:
    """Coerce an optional string field to a non-None default."""
    if value is None:
        return default
    if not isinstance(value, str):
        raise ContractError(f"{name} must be a string or None")
    return value.strip()


def _string_tuple(values: tuple[str, ...], name: str) -> tuple[str, ...]:
    """Normalize a tuple of non-empty strings with dedup and sort."""
    if not isinstance(values, tuple):
        values = tuple(values)
    normalized = tuple(sorted({_required_str(v, name) for v in values}))
    return normalized


# ── Owner identity helpers ────────────────────────────────────────────────


def process_birth_identity() -> dict[str, str]:
    """Return the current process-birth identity: hostname, pid, and boot time.

    This is a best-effort snapshot and may be unavailable in some
    environments.  Callers treat missing fields as empty strings.
    """
    identity: dict[str, str] = {}
    try:
        identity["host"] = socket.gethostname()
    except Exception:
        identity["host"] = ""
    identity["pid"] = str(os.getpid())
    # Approximate boot id from /proc if available (Linux).
    try:
        boot_id = Path("/proc/sys/kernel/random/boot_id").read_text(encoding="utf-8").strip()
        identity["boot_id"] = boot_id
    except Exception:
        try:
            boot = subprocess.run(
                ["ps", "-o", "lstart=", "-p", "1"],
                check=False,
                capture_output=True,
                text=True,
                timeout=2,
            ).stdout.strip()
            identity["boot_id"] = f"host-process-1:{boot}" if boot else ""
        except Exception:
            identity["boot_id"] = ""
    return identity


def owner_observably_dead(
    *,
    host: str,
    pid: str,
    boot_id: str,
    current_host: str | None = None,
) -> bool:
    """True when a custody-lease owner is observably gone.

    A lease owner is reclaimable when it is dead even though its TTL has not
    lapsed (grok consult, astrid dispatch-lease wedge): a resume worker that
    dies mid-batch leaves an ACTIVE lease with a dead PID, and the acquire
    path denied it as ``active foreign`` until the 1h ``expires_at`` — wedging
    every subsequent resume.  The check is deliberately conservative:
    - A DIFFERENT host is never judged dead (foreign-host leases are never
      stolen).
    - On the same host, the PID is probed via ``os.kill(pid, 0)``; a
      ``ProcessLookupError`` means the process is gone.  ``PermissionError``
      (exists, other user) counts as ALIVE.
    - When ``boot_id`` is provided and the current process can read the host's
      boot id, a boot-id mismatch means the host rebooted since the lease was
      taken — the old owner cannot be alive; the lease is reclaimable.
    - Unparseable pids and unreadable host state fail CLOSED (return False)
      so the check never fabricates death.
    """
    current_host = current_host or _current_hostname()
    if not host or host != current_host:
        return False
    if not pid or not pid.isdigit():
        return False
    try:
        os.kill(int(pid), 0)
        alive = True
    except ProcessLookupError:
        return True
    except PermissionError:
        alive = True
    except OSError:
        return False
    if alive:
        # PID exists; the only remaining death signal is a host reboot.
        if boot_id and _current_boot_id():
            return boot_id != _current_boot_id()
        return False
    return True


def _current_hostname() -> str:
    try:
        return socket.gethostname()
    except Exception:
        return ""


def _current_boot_id() -> str:
    try:
        return (
            Path("/proc/sys/kernel/random/boot_id")
            .read_text(encoding="utf-8")
            .strip()
        )
    except Exception:
        return ""


# ── Digest helpers ────────────────────────────────────────────────────────


def target_digest(target: Mapping[str, Any]) -> str:
    """Produce a deterministic SHA-256 digest over a canonical target dict."""
    plain = _thaw_sorted(target)
    return hashlib.sha256(
        json.dumps(plain, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def occurrence_digest(
    f01_fields: Mapping[str, Any], fence_token: int, chain_identity: str = ""
) -> str:
    """Produce a deterministic SHA-256 digest over the F01 tuple, fence token, and chain identity."""
    plain_f01 = _thaw_sorted(f01_fields)
    payload = {
        "f01": dict(sorted(plain_f01.items())),
        "fence_token": fence_token,
        "chain_identity": chain_identity,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


# ── JSON freezing (mirrors run_authority._freeze_json) ──────────────────

from pathlib import Path
from types import MappingProxyType


def _freeze_json_sorted(value: Any, path: str = "payload") -> Any:
    """Freeze a JSON-compatible value, sorting dict keys deterministically."""
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        import math

        if not math.isfinite(value):
            raise ContractError(f"{path} contains a non-finite number")
        return value
    if isinstance(value, Mapping):
        frozen: dict[str, Any] = {}
        for key in sorted(value):
            if not isinstance(key, str):
                raise ContractError(f"{path} keys must be strings")
            frozen[key] = _freeze_json_sorted(value[key], f"{path}.{key}")
        return MappingProxyType(frozen)
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_json_sorted(item, f"{path}[]") for item in value)
    raise ContractError(f"{path} contains unsupported value {type(value).__name__}")


def _thaw(value: Any) -> Any:
    """Convert frozen values back to plain JSON-serializable Python."""
    if isinstance(value, Mapping):
        return {key: _thaw(value[key]) for key in sorted(value)}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


def _thaw_sorted(value: Any) -> Any:
    """Convert frozen values to plain Python with deterministic key ordering.

    This is like _thaw but explicitly sorts dict keys for digest stability
    even when the input is already a plain dict (not frozen).
    """
    if isinstance(value, Mapping):
        return {key: _thaw_sorted(value[key]) for key in sorted(value)}
    if isinstance(value, tuple):
        return [_thaw_sorted(item) for item in value]
    return value


# ═══════════════════════════════════════════════════════════════════════════
# CustodyTargetKey
# ═══════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, init=False)
class CustodyTargetKey(Contract):
    """Canonical custody target identity.

    Composed of the F01 repair-occurrence tuple plus chain identity and an
    optional dispatch discriminator.  All ten F01 fields are required
    non-empty strings; chain_identity and dispatch_key are optional (empty
    string when not yet bound).  ``dispatch_key`` names a worker-dispatch
    slice (e.g. ``critique:scope:initial``) so two dispatches that differ
    ONLY in dispatch key derive distinct target digests and can never
    collide on a custody lease.
    """

    contract_type: ClassVar[str] = "custody_target_key"
    schema_version: ClassVar[int] = CUSTODY_TARGET_KEY_VERSION

    environment: str
    session: str
    chain: str
    plan_revision: str
    phase: str
    task: str
    attempt: str
    normalized_failure_kind: str
    blocker_or_phase_result_hash: str
    fence: str
    chain_identity: str = ""
    dispatch_key: str = ""

    def __init__(self, *args: str, **kwargs: str) -> None:
        """Build either the current F01 key or the predecessor six-field key.

        M10 changed this public contract while predecessor M8/M9 consumers
        were still in the supported acceptance set.  Keep those legacy reads
        non-authoritative, but do not make them unconstructable: six positional
        values or the six legacy keyword names are mapped into a deterministic
        compatibility F01 tuple.  Current callers still must provide every F01
        field and retain the strict fail-closed validation below.
        """
        legacy_names = (
            "subject_type",
            "subject_id",
            "action",
            "target_kind",
            "target_id",
            "contract_id",
        )
        f01_names = F01_REPAIR_OCCURRENCE_FIELDS
        legacy_values: tuple[str, ...] | None = None

        if args:
            if (set(kwargs) - {"dispatch_key"}) or len(args) != len(legacy_names):
                raise TypeError(
                    "CustodyTargetKey positional construction requires the "
                    "six predecessor target fields"
                )
            legacy_values = tuple(args)
        elif any(name in kwargs for name in legacy_names):
            missing = [name for name in legacy_names if name not in kwargs]
            unknown = set(kwargs) - set(legacy_names) - {"dispatch_key"}
            if missing or unknown:
                raise TypeError(
                    "legacy CustodyTargetKey requires exactly "
                    f"{legacy_names}; missing={missing}, unknown={sorted(unknown)}"
                )
            legacy_values = tuple(kwargs[name] for name in legacy_names)

        if legacy_values is not None:
            for name, value in zip(legacy_names, legacy_values, strict=True):
                _required_str(value, name)
            compatibility_hash = hashlib.sha256(
                canonical_json(dict(zip(legacy_names, legacy_values, strict=True))).encode(
                    "utf-8"
                )
            ).hexdigest()
            mapped = {
                "environment": legacy_values[0],
                "session": legacy_values[1],
                "chain": legacy_values[2],
                "plan_revision": legacy_values[3],
                "phase": legacy_values[4],
                "task": legacy_values[5],
                "attempt": "legacy",
                "normalized_failure_kind": "legacy_target_compatibility",
                "blocker_or_phase_result_hash": compatibility_hash,
                "fence": "legacy-non-authoritative",
                "chain_identity": "",
                "dispatch_key": kwargs.get("dispatch_key", ""),
            }
            object.__setattr__(self, "_legacy_values", legacy_values)
        else:
            missing = [name for name in f01_names if name not in kwargs]
            unknown = set(kwargs) - set(f01_names) - {"chain_identity", "dispatch_key"}
            if missing or unknown:
                raise TypeError(
                    "CustodyTargetKey requires the complete F01 tuple; "
                    f"missing={missing}, unknown={sorted(unknown)}"
                )
            mapped = {name: kwargs[name] for name in f01_names}
            mapped["chain_identity"] = kwargs.get("chain_identity", "")
            mapped["dispatch_key"] = kwargs.get("dispatch_key", "")
            object.__setattr__(self, "_legacy_values", None)

        for name, value in mapped.items():
            object.__setattr__(self, name, value)
        self.__post_init__()

    def __post_init__(self) -> None:
        for name in F01_REPAIR_OCCURRENCE_FIELDS:
            _required_str(getattr(self, name), name)
        # chain_identity is optional but must be a string
        if not isinstance(self.chain_identity, str):
            raise ContractError("chain_identity must be a string")
        # dispatch_key is optional but must be a string
        if not isinstance(self.dispatch_key, str):
            raise ContractError("dispatch_key must be a string")

    @property
    def subject_type(self) -> str:
        return self._legacy_component(0, self.environment)

    @property
    def subject_id(self) -> str:
        return self._legacy_component(1, self.session)

    @property
    def action(self) -> str:
        return self._legacy_component(2, self.chain)

    @property
    def target_kind(self) -> str:
        return self._legacy_component(3, self.plan_revision)

    @property
    def target_id(self) -> str:
        return self._legacy_component(4, self.phase)

    @property
    def contract_id(self) -> str:
        return self._legacy_component(5, self.task)

    def _legacy_component(self, index: int, fallback: str) -> str:
        values = getattr(self, "_legacy_values", None)
        return values[index] if values is not None else fallback

    @property
    def key(self) -> str:
        return self.target_digest

    def to_dict(self) -> dict[str, Any]:
        values = getattr(self, "_legacy_values", None)
        if values is not None:
            names = (
                "subject_type",
                "subject_id",
                "action",
                "target_kind",
                "target_id",
                "contract_id",
            )
            legacy = dict(zip(names, values, strict=True))
            # Preserve the dispatch discriminator on legacy round trips so a
            # legacy-constructed dispatch target keeps its full identity.
            if self.dispatch_key:
                legacy["dispatch_key"] = self.dispatch_key
            return legacy
        return super().to_dict()

    def to_tuple(self) -> tuple[str, ...]:
        """Return the F01 tuple representation."""
        return tuple(getattr(self, name) for name in F01_REPAIR_OCCURRENCE_FIELDS)

    @property
    def target_digest(self) -> str:
        """Deterministic SHA-256 of the canonical key.

        Covers the F01 fields plus chain_identity and dispatch_key, so the
        full target identity — including the worker-dispatch discriminator —
        keys every custody join (lease id, outbox occurrence digest, replay).
        """
        plain: dict[str, Any] = {}
        for name in F01_REPAIR_OCCURRENCE_FIELDS:
            plain[name] = getattr(self, name)
        plain["chain_identity"] = self.chain_identity
        plain["dispatch_key"] = self.dispatch_key
        return target_digest(plain)


def normalize_custody_target_key(payload: Mapping[str, Any] | None) -> CustodyTargetKey | None:
    """Return a canonical CustodyTargetKey or None for invalid inputs."""
    if not isinstance(payload, Mapping):
        return None
    try:
        legacy_names = (
            "subject_type",
            "subject_id",
            "action",
            "target_kind",
            "target_id",
            "contract_id",
        )
        if all(name in payload for name in legacy_names):
            return CustodyTargetKey(
                **{name: str(payload[name]) for name in legacy_names},
                dispatch_key=payload.get("dispatch_key", ""),
            )
        return CustodyTargetKey(
            environment=payload.get("environment", ""),
            session=payload.get("session", ""),
            chain=payload.get("chain", ""),
            plan_revision=payload.get("plan_revision", ""),
            phase=payload.get("phase", ""),
            task=payload.get("task", ""),
            attempt=payload.get("attempt", ""),
            normalized_failure_kind=payload.get("normalized_failure_kind", ""),
            blocker_or_phase_result_hash=payload.get("blocker_or_phase_result_hash", ""),
            fence=payload.get("fence", ""),
            chain_identity=payload.get("chain_identity", ""),
            dispatch_key=payload.get("dispatch_key", ""),
        )
    except (ContractError, TypeError):
        return None


def build_custody_target_key(
    *,
    environment: str = "",
    session: str = "",
    chain: str = "",
    plan_revision: str = "",
    phase: str = "",
    task: str = "",
    attempt: str = "",
    normalized_failure_kind: str = "",
    blocker_or_phase_result_hash: str = "",
    fence: str = "",
    chain_identity: str = "",
    dispatch_key: str = "",
) -> CustodyTargetKey | None:
    """Build a CustodyTargetKey from keyword arguments; returns None if any required field is empty."""
    try:
        return CustodyTargetKey(
            environment=environment,
            session=session,
            chain=chain,
            plan_revision=plan_revision,
            phase=phase,
            task=task,
            attempt=attempt,
            normalized_failure_kind=normalized_failure_kind,
            blocker_or_phase_result_hash=blocker_or_phase_result_hash,
            fence=fence,
            chain_identity=chain_identity,
            dispatch_key=dispatch_key,
        )
    except ContractError:
        return None


# ═══════════════════════════════════════════════════════════════════════════
# RepairOccurrenceKey
# ═══════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, init=False)
class RepairOccurrenceKey(Contract):
    """Canonical repair-occurrence identity.

    Wraps the full CustodyTargetKey with the current coordinator fence
    token, run identity, WBC attempt reference, and a deterministic
    occurrence digest over the F01 fields + fence token + chain identity.
    """

    contract_type: ClassVar[str] = "repair_occurrence_key"
    schema_version: ClassVar[int] = REPAIR_OCCURRENCE_KEY_VERSION

    target: CustodyTargetKey
    run_id: str
    run_revision: str
    coordinator_attempt_id: str
    fence_token: int
    wbc_attempt_reference: str
    occurrence_digest: str = field(init=False)

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Build the current occurrence contract or its predecessor F01 form."""
        legacy_names = (
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
        current_names = (
            "target",
            "run_id",
            "run_revision",
            "coordinator_attempt_id",
            "fence_token",
            "wbc_attempt_reference",
        )
        legacy: dict[str, Any] | None = None
        if args:
            if kwargs or len(args) != len(legacy_names):
                raise TypeError(
                    "RepairOccurrenceKey positional construction requires the "
                    "ten predecessor occurrence fields"
                )
            legacy = dict(zip(legacy_names, args, strict=True))
        elif any(name in kwargs for name in legacy_names):
            missing = [name for name in legacy_names if name not in kwargs]
            unknown = sorted(set(kwargs) - set(legacy_names))
            if missing or unknown:
                raise TypeError(
                    "legacy RepairOccurrenceKey requires exactly "
                    f"{legacy_names}; missing={missing}, unknown={unknown}"
                )
            legacy = {name: kwargs[name] for name in legacy_names}

        if legacy is not None:
            for name in legacy_names:
                if name == "attempt_number":
                    _required_pos_int(legacy[name], name)
                else:
                    _required_str(legacy[name], name)
            target = CustodyTargetKey(
                environment=legacy["environment_id"],
                session=legacy["session_id"],
                chain=legacy["chain_id"],
                plan_revision=legacy["plan_revision"],
                phase=legacy["phase"],
                task=legacy["task_id"],
                attempt=str(legacy["attempt_number"]),
                normalized_failure_kind=legacy["failure_kind"],
                blocker_or_phase_result_hash=legacy["blocker_digest"],
                fence=legacy["coordinator_fence_token"],
                chain_identity=legacy["chain_id"],
            )
            mapped = {
                "target": target,
                "run_id": legacy["session_id"],
                "run_revision": legacy["plan_revision"],
                "coordinator_attempt_id": (
                    f"{legacy['task_id']}:{legacy['attempt_number']}"
                ),
                "fence_token": (
                    int(legacy["coordinator_fence_token"])
                    if str(legacy["coordinator_fence_token"]).isdigit()
                    else int.from_bytes(
                        hashlib.sha256(
                            str(legacy["coordinator_fence_token"]).encode("utf-8")
                        ).digest()[:8],
                        "big",
                    )
                ),
                "wbc_attempt_reference": legacy["blocker_digest"],
            }
            object.__setattr__(self, "_legacy_values", legacy)
            for name, value in legacy.items():
                object.__setattr__(self, name, value)
        else:
            missing = [name for name in current_names if name not in kwargs]
            unknown = sorted(set(kwargs) - set(current_names))
            if missing or unknown:
                raise TypeError(
                    "RepairOccurrenceKey requires the current occurrence fields; "
                    f"missing={missing}, unknown={unknown}"
                )
            mapped = {name: kwargs[name] for name in current_names}
            object.__setattr__(self, "_legacy_values", None)

        for name, value in mapped.items():
            object.__setattr__(self, name, value)
        self.__post_init__()

    def __post_init__(self) -> None:
        _required_str(self.run_id, "run_id")
        _required_str(self.run_revision, "run_revision")
        _required_str(self.coordinator_attempt_id, "coordinator_attempt_id")
        _required_nonneg_int(self.fence_token, "fence_token")
        _required_str(self.wbc_attempt_reference, "wbc_attempt_reference")
        # Compute deterministic occurrence digest over F01 fields only
        f01_plain: dict[str, str] = {}
        for name in F01_REPAIR_OCCURRENCE_FIELDS:
            f01_plain[name] = getattr(self.target, name)
        digest = occurrence_digest(
            f01_plain, self.fence_token, self.target.chain_identity
        )
        object.__setattr__(self, "occurrence_digest", f"sha256:{digest}")

    def to_dict(self) -> dict[str, Any]:
        legacy = getattr(self, "_legacy_values", None)
        if legacy is not None:
            return dict(legacy)
        result = {
            "contract_type": self.contract_type,
            "schema_version": self.schema_version,
            "target": self.target.to_dict(),
            "run_id": self.run_id,
            "run_revision": self.run_revision,
            "coordinator_attempt_id": self.coordinator_attempt_id,
            "fence_token": self.fence_token,
            "wbc_attempt_reference": self.wbc_attempt_reference,
            "occurrence_digest": self.occurrence_digest,
        }
        return result

    @property
    def f01_tuple(self) -> tuple[Any, ...]:
        legacy = getattr(self, "_legacy_values", None)
        if legacy is not None:
            return tuple(legacy[name] for name in (
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
            ))
        return self.target.to_tuple()

    @property
    def key(self) -> str:
        legacy = getattr(self, "_legacy_values", None)
        if legacy is not None:
            material = canonical_json(dict(legacy)).encode("utf-8")
            return hashlib.sha256(material).hexdigest()
        return self.occurrence_digest.removeprefix("sha256:")


def normalize_repair_occurrence_key(
    payload: Mapping[str, Any] | None,
) -> RepairOccurrenceKey | None:
    """Return a canonical RepairOccurrenceKey or None for invalid inputs."""
    if not isinstance(payload, Mapping):
        return None
    legacy_names = (
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
    if all(name in payload for name in legacy_names):
        try:
            return RepairOccurrenceKey(
                **{name: payload[name] for name in legacy_names}
            )
        except (ContractError, TypeError, ValueError):
            return None
    target_raw = payload.get("target")
    target = normalize_custody_target_key(target_raw)
    if target is None:
        return None
    try:
        return RepairOccurrenceKey(
            target=target,
            run_id=payload.get("run_id", ""),
            run_revision=payload.get("run_revision", ""),
            coordinator_attempt_id=payload.get("coordinator_attempt_id", ""),
            fence_token=payload.get("fence_token", 0),
            wbc_attempt_reference=payload.get("wbc_attempt_reference", ""),
        )
    except (ContractError, TypeError):
        return None


def build_repair_occurrence_key(
    *,
    target: CustodyTargetKey,
    run_id: str = "",
    run_revision: str = "",
    coordinator_attempt_id: str = "",
    fence_token: int = 0,
    wbc_attempt_reference: str = "",
) -> RepairOccurrenceKey | None:
    """Build a RepairOccurrenceKey; returns None if required fields are empty."""
    try:
        return RepairOccurrenceKey(
            target=target,
            run_id=run_id,
            run_revision=run_revision,
            coordinator_attempt_id=coordinator_attempt_id,
            fence_token=fence_token,
            wbc_attempt_reference=wbc_attempt_reference,
        )
    except ContractError:
        return None


# ═══════════════════════════════════════════════════════════════════════════
# CustodyLease
# ═══════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, init=False)
class CustodyLease(Contract):
    """Immutable custody lease record.

    A lease binds an owner identity to a repair occurrence for a bounded
    custody epoch.  It references the prerequisite Run Authority grant and
    coordinator fence, plus the WBC attempt reference.  Every lease carries
    a deterministic idempotency key and an optional causal predecessor so
    the lifecycle is auditable.

    Required fields:
      - lease_id: unique lease identifier
      - occurrence_key: the RepairOccurrenceKey this lease targets
      - owner_host: hostname of the owning process
      - owner_pid: PID of the owning process
      - owner_boot_id: boot identity (best-effort, may be empty)
      - run_authority_grant_id: the Run Authority grant that authorizes the lease
      - coordinator_fence_token: the coordinator fence token at acquisition
      - wbc_attempt_reference: the WBC attempt reference (may be empty)
      - custody_epoch: monotonic lease epoch (must be >= 1)
      - acquired_at: ISO-8601 timestamp of acquisition
      - expires_at: ISO-8601 timestamp of expiry (must be > acquired_at)
      - idempotency_key: deterministic idempotency key for CAS
      - causal_predecessor: lease_id of the predecessor (empty for initial acquire)
    """

    contract_type: ClassVar[str] = "custody_lease"
    schema_version: ClassVar[int] = CUSTODY_LEASE_VERSION

    lease_id: str
    occurrence_key: RepairOccurrenceKey
    owner_host: str
    owner_pid: str
    owner_boot_id: str
    run_authority_grant_id: str
    coordinator_fence_token: int
    wbc_attempt_reference: str
    custody_epoch: int
    acquired_at: str
    expires_at: str
    idempotency_key: str
    causal_predecessor: str = ""

    def __init__(self, **kwargs: Any) -> None:
        legacy = "target_key" in kwargs or "owner" in kwargs or "epoch" in kwargs
        if legacy:
            allowed = {
                "lease_id",
                "target_key",
                "owner",
                "epoch",
                "acquired_at",
                "expires_at",
                "fence_token",
                "status",
                "causal_predecessor",
                "run_authority_grant_id",
                "wbc_attempt_reference",
            }
            required = {
                "lease_id",
                "target_key",
                "owner",
                "epoch",
                "acquired_at",
                "expires_at",
                "fence_token",
                "status",
                "run_authority_grant_id",
                "wbc_attempt_reference",
            }
            missing = sorted(required - set(kwargs))
            unknown = sorted(set(kwargs) - allowed)
            if missing or unknown:
                raise TypeError(
                    "legacy CustodyLease fields invalid; "
                    f"missing={missing}, unknown={unknown}"
                )
            target = kwargs["target_key"]
            if not isinstance(target, CustodyTargetKey):
                raise TypeError("target_key must be a CustodyTargetKey")
            owner = tuple(kwargs["owner"])
            if len(owner) != 3:
                raise ContractError("owner must be a host/pid/boot-id tuple")
            fence = int(kwargs["fence_token"])
            grant = str(kwargs["run_authority_grant_id"])
            wbc = str(kwargs["wbc_attempt_reference"])
            occurrence = RepairOccurrenceKey(
                target=target,
                run_id=f"legacy:{grant}",
                run_revision="legacy-non-authoritative",
                coordinator_attempt_id="legacy-non-authoritative",
                fence_token=fence,
                wbc_attempt_reference=wbc,
            )
            mapped = {
                "lease_id": kwargs["lease_id"],
                "occurrence_key": occurrence,
                "owner_host": str(owner[0]),
                "owner_pid": str(owner[1]),
                "owner_boot_id": str(owner[2]),
                "run_authority_grant_id": grant,
                "coordinator_fence_token": fence,
                "wbc_attempt_reference": wbc,
                "custody_epoch": int(kwargs["epoch"]),
                "acquired_at": kwargs["acquired_at"],
                "expires_at": kwargs["expires_at"],
                "idempotency_key": hashlib.sha256(
                    canonical_json(
                        {
                            "lease_id": kwargs["lease_id"],
                            "target": target.to_dict(),
                            "epoch": int(kwargs["epoch"]),
                        }
                    ).encode("utf-8")
                ).hexdigest(),
                "causal_predecessor": kwargs.get("causal_predecessor", ""),
            }
            object.__setattr__(self, "_legacy_target_key", target)
            object.__setattr__(self, "_legacy_status", str(kwargs["status"]))
        else:
            names = {
                "lease_id",
                "occurrence_key",
                "owner_host",
                "owner_pid",
                "owner_boot_id",
                "run_authority_grant_id",
                "coordinator_fence_token",
                "wbc_attempt_reference",
                "custody_epoch",
                "acquired_at",
                "expires_at",
                "idempotency_key",
            }
            missing = sorted(names - set(kwargs))
            unknown = sorted(set(kwargs) - names - {"causal_predecessor"})
            if missing or unknown:
                raise TypeError(
                    "CustodyLease fields invalid; "
                    f"missing={missing}, unknown={unknown}"
                )
            mapped = {name: kwargs[name] for name in names}
            mapped["causal_predecessor"] = kwargs.get("causal_predecessor", "")
            object.__setattr__(self, "_legacy_target_key", None)
            object.__setattr__(self, "_legacy_status", "")
        for name, value in mapped.items():
            object.__setattr__(self, name, value)
        self.__post_init__()

    def __post_init__(self) -> None:
        _required_str(self.lease_id, "lease_id")
        _required_str(self.owner_host, "owner_host")
        _required_str(self.owner_pid, "owner_pid")
        # owner_boot_id may be empty (best-effort)
        if not isinstance(self.owner_boot_id, str):
            raise ContractError("owner_boot_id must be a string")
        _required_str(self.run_authority_grant_id, "run_authority_grant_id")
        _required_nonneg_int(self.coordinator_fence_token, "coordinator_fence_token")
        _required_str(self.wbc_attempt_reference, "wbc_attempt_reference")
        _required_pos_int(self.custody_epoch, "custody_epoch")
        _required_str(self.acquired_at, "acquired_at")
        _required_str(self.expires_at, "expires_at")
        _required_str(self.idempotency_key, "idempotency_key")
        if not isinstance(self.causal_predecessor, str):
            raise ContractError("causal_predecessor must be a string")
        # Validate temporal ordering
        try:
            acquired_dt = datetime.fromisoformat(self.acquired_at.replace("Z", "+00:00"))
            expires_dt = datetime.fromisoformat(self.expires_at.replace("Z", "+00:00"))
        except (ValueError, TypeError) as exc:
            raise ContractError(f"invalid ISO-8601 timestamp: {exc}") from exc
        if (
            expires_dt <= acquired_dt
            and getattr(self, "_legacy_target_key", None) is None
        ):
            raise ContractError("expires_at must be strictly after acquired_at")

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_type": self.contract_type,
            "schema_version": self.schema_version,
            "lease_id": self.lease_id,
            "occurrence_key": self.occurrence_key.to_dict(),
            "owner_host": self.owner_host,
            "owner_pid": self.owner_pid,
            "owner_boot_id": self.owner_boot_id,
            "run_authority_grant_id": self.run_authority_grant_id,
            "coordinator_fence_token": self.coordinator_fence_token,
            "wbc_attempt_reference": self.wbc_attempt_reference,
            "custody_epoch": self.custody_epoch,
            "acquired_at": self.acquired_at,
            "expires_at": self.expires_at,
            "idempotency_key": self.idempotency_key,
            "causal_predecessor": self.causal_predecessor,
        }

    @property
    def is_expired(self, *, now: datetime | None = None) -> bool:
        """Return True if the lease has expired."""
        ref = now if now is not None else datetime.now(timezone.utc)
        try:
            expires_dt = datetime.fromisoformat(self.expires_at.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return True
        return ref >= expires_dt

    @property
    def owner_identity(self) -> tuple[str, str, str]:
        """Return the (host, pid, boot_id) owner identity tuple."""
        return (self.owner_host, self.owner_pid, self.owner_boot_id)

    @property
    def target_key(self) -> CustodyTargetKey:
        legacy = getattr(self, "_legacy_target_key", None)
        return legacy if legacy is not None else self.occurrence_key.target

    @property
    def owner(self) -> tuple[str, str, str]:
        return self.owner_identity

    @property
    def epoch(self) -> int:
        return self.custody_epoch

    @property
    def fence_token(self) -> str:
        return str(self.coordinator_fence_token)

    @property
    def status(self) -> str:
        return getattr(self, "_legacy_status", "")

    def assert_monotonic_epoch(self, previous: CustodyLease) -> None:
        """Validate that this lease's epoch is strictly greater than the predecessor's."""
        if self.custody_epoch <= previous.custody_epoch:
            raise ContractError(
                f"custody_epoch must be monotonic: {self.custody_epoch} <= {previous.custody_epoch}"
            )
        if self.lease_id == previous.lease_id:
            raise ContractError("lease_id must differ from causal predecessor")


def normalize_custody_lease(payload: Mapping[str, Any] | None) -> CustodyLease | None:
    """Return a canonical CustodyLease or None for invalid inputs."""
    if not isinstance(payload, Mapping):
        return None
    occurrence_raw = payload.get("occurrence_key")
    occurrence_key = normalize_repair_occurrence_key(occurrence_raw)
    if occurrence_key is None:
        return None
    try:
        return CustodyLease(
            lease_id=payload.get("lease_id", ""),
            occurrence_key=occurrence_key,
            owner_host=payload.get("owner_host", ""),
            owner_pid=payload.get("owner_pid", ""),
            owner_boot_id=payload.get("owner_boot_id", ""),
            run_authority_grant_id=payload.get("run_authority_grant_id", ""),
            coordinator_fence_token=payload.get("coordinator_fence_token", 0),
            wbc_attempt_reference=payload.get("wbc_attempt_reference", ""),
            custody_epoch=payload.get("custody_epoch", 0),
            acquired_at=payload.get("acquired_at", ""),
            expires_at=payload.get("expires_at", ""),
            idempotency_key=payload.get("idempotency_key", ""),
            causal_predecessor=payload.get("causal_predecessor", ""),
        )
    except (ContractError, TypeError):
        return None


# ═══════════════════════════════════════════════════════════════════════════
# CustodyLeaseEvent
# ═══════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class CustodyLeaseEvent(Contract):
    """Append-only custody lease lifecycle event.

    Every event references exactly one lease and carries a monotonic
    sequence number within that lease's event stream.  Events are immutable
    and never mutate prior history.

    Event types:
      - acquire:  initial lease acquisition
      - renew:    lease renewal with new expiry
      - transfer: ownership transfer to a new owner identity
      - release:  voluntary lease release
      - expire:   lease expiry (auto-generated)
      - fence:    coordinator fence violation
      - conflict: concurrent lease conflict detected
      - reconcile: reconciliation event after conflict resolution
    """

    contract_type: ClassVar[str] = "custody_lease_event"
    schema_version: ClassVar[int] = CUSTODY_LEASE_EVENT_VERSION

    event_id: str
    lease_id: str
    sequence: int
    event_type: CustodyLeaseEventType
    occurred_at: str
    custody_epoch: int
    owner_host: str
    owner_pid: str
    owner_boot_id: str
    run_authority_grant_id: str
    coordinator_fence_token: int
    wbc_attempt_reference: str
    occurrence_digest: str
    idempotency_key: str
    causal_predecessor: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    payload_hash: str = field(init=False)

    def __post_init__(self) -> None:
        _required_str(self.event_id, "event_id")
        _required_str(self.lease_id, "lease_id")
        _required_pos_int(self.sequence, "sequence")
        if self.event_type not in CUSTODY_LEASE_EVENT_TYPES:
            raise ContractError(f"unknown event_type {self.event_type!r}")
        _required_str(self.occurred_at, "occurred_at")
        _required_pos_int(self.custody_epoch, "custody_epoch")
        _required_str(self.owner_host, "owner_host")
        _required_str(self.owner_pid, "owner_pid")
        if not isinstance(self.owner_boot_id, str):
            raise ContractError("owner_boot_id must be a string")
        _required_str(self.run_authority_grant_id, "run_authority_grant_id")
        _required_nonneg_int(self.coordinator_fence_token, "coordinator_fence_token")
        _required_str(self.wbc_attempt_reference, "wbc_attempt_reference")
        _required_str(self.occurrence_digest, "occurrence_digest")
        _required_str(self.idempotency_key, "idempotency_key")
        if not isinstance(self.causal_predecessor, str):
            raise ContractError("causal_predecessor must be a string")
        # Freeze and hash payload
        frozen = _freeze_json_sorted(self.payload)
        if not isinstance(frozen, Mapping):
            raise ContractError("payload must be an object")
        object.__setattr__(self, "payload", frozen)
        object.__setattr__(self, "payload_hash", payload_digest(frozen))

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_type": self.contract_type,
            "schema_version": self.schema_version,
            "event_id": self.event_id,
            "lease_id": self.lease_id,
            "sequence": self.sequence,
            "event_type": self.event_type,
            "occurred_at": self.occurred_at,
            "custody_epoch": self.custody_epoch,
            "owner_host": self.owner_host,
            "owner_pid": self.owner_pid,
            "owner_boot_id": self.owner_boot_id,
            "run_authority_grant_id": self.run_authority_grant_id,
            "coordinator_fence_token": self.coordinator_fence_token,
            "wbc_attempt_reference": self.wbc_attempt_reference,
            "occurrence_digest": self.occurrence_digest,
            "idempotency_key": self.idempotency_key,
            "causal_predecessor": self.causal_predecessor,
            "payload": _thaw(self.payload),
            "payload_hash": self.payload_hash,
        }

    @property
    def owner_identity(self) -> tuple[str, str, str]:
        """Return the (host, pid, boot_id) owner identity tuple."""
        return (self.owner_host, self.owner_pid, self.owner_boot_id)

    def assert_monotonic_sequence(self, previous: CustodyLeaseEvent) -> None:
        """Validate that this event's sequence is strictly greater than the predecessor's."""
        if self.sequence <= previous.sequence:
            raise ContractError(
                f"event sequence must be monotonic: {self.sequence} <= {previous.sequence}"
            )
        if self.lease_id != previous.lease_id:
            raise IdentityConflict(
                f"event lease_id mismatch: {self.lease_id!r} != {previous.lease_id!r}"
            )

    def assert_monotonic_epoch(self, previous: CustodyLeaseEvent) -> None:
        """Validate that the custody_epoch is non-decreasing."""
        if self.custody_epoch < previous.custody_epoch:
            raise ContractError(
                f"custody_epoch must be non-decreasing: {self.custody_epoch} < {previous.custody_epoch}"
            )


def normalize_custody_lease_event(
    payload: Mapping[str, Any] | None,
) -> CustodyLeaseEvent | None:
    """Return a canonical CustodyLeaseEvent or None for invalid inputs."""
    if not isinstance(payload, Mapping):
        return None
    try:
        return CustodyLeaseEvent(
            event_id=payload.get("event_id", ""),
            lease_id=payload.get("lease_id", ""),
            sequence=payload.get("sequence", 0),
            event_type=payload.get("event_type", "acquire"),  # type: ignore[arg-type]
            occurred_at=payload.get("occurred_at", ""),
            custody_epoch=payload.get("custody_epoch", 0),
            owner_host=payload.get("owner_host", ""),
            owner_pid=payload.get("owner_pid", ""),
            owner_boot_id=payload.get("owner_boot_id", ""),
            run_authority_grant_id=payload.get("run_authority_grant_id", ""),
            coordinator_fence_token=payload.get("coordinator_fence_token", 0),
            wbc_attempt_reference=payload.get("wbc_attempt_reference", ""),
            occurrence_digest=payload.get("occurrence_digest", ""),
            idempotency_key=payload.get("idempotency_key", ""),
            causal_predecessor=payload.get("causal_predecessor", ""),
            payload=payload.get("payload") or {},
        )
    except (ContractError, TypeError):
        return None
