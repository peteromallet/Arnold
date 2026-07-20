"""Durable Custody outbox for single-owner writes and cross-owner references.

Provides local CAS-backed single-owner Custody writes and durable
cross-owner outbox records that reference WBC attempts or Run Authority
decisions without duplicating their state.  Includes reconciliation by
rereading source records and moving unresolved failures to a dead-letter
record with joinable diagnostics.

Storage layout under ``<base_dir>/``::

    <outbox_id>.record.json       — the outbox record (canonical JSON)
    <outbox_id>.history.jsonl     — append-only event stream
    <outbox_id>.lock              — fcntl.flock serialization gate
    dead_letter/
      <dead_letter_id>.json       — dead-letter record with diagnostics

Principles
----------
* **Single-owner writes** — The outbox writes only Custody-owned state.
  Cross-owner references (WBC attempt ids, Run Authority grant ids,
  coordinator fence tokens) are read-only pointers, never duplicate
  ledgers.
* **Durable cross-owner records** — Every outbox record carries typed
  references (lease_id, wbc_attempt_reference, run_authority_grant_id,
  coordinator_fence_token) so downstream consumers can join without
  re-requesting each source.
* **Reconciliation** — ``reconcile_outbox_record`` re-reads the source
  records (lease store, WBC attempts, Run Authority decisions) and
  determines whether each reference is resolved, stale, or
  contradictory.
* **Dead-letter** — Unresolved failures are moved to a dead-letter
  record under ``dead_letter/``.  Each dead-letter record carries the
  original outbox record, reconciliation diagnostics, and join keys
  (lease_id, wbc_attempt_reference, run_authority_grant_id) so operators
  can trace back to the source records.

All production gates and mutating effects remain disabled in M7;
this module runs in shadow/report-only mode.
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType
from typing import Any, Iterator, Mapping, Sequence

from arnold_pipelines.megaplan.custody.contracts import (
    CustodyLease,
    CustodyLeaseEvent,
    CustodyTargetKey,
    RepairOccurrenceKey,
    normalize_custody_lease,
    normalize_repair_occurrence_key,
    payload_digest as _payload_digest,
)
from arnold_pipelines.run_authority.contracts import (
    Contract,
    ContractError,
    canonical_json,
)


# ── Schema version constant ────────────────────────────────────────────────

OUTBOX_SCHEMA_VERSION = 1
DEAD_LETTER_SCHEMA_VERSION = 1


# ── Enums ──────────────────────────────────────────────────────────────────


class OutboxRecordStatus(StrEnum):
    """Lifecycle status of an outbox record."""

    PENDING = "pending"
    DELIVERED = "delivered"
    RECONCILED = "reconciled"
    DEAD_LETTER = "dead_letter"
    CANCELLED = "cancelled"


class OutboxRecordType(StrEnum):
    """Semantic type of an outbox record."""

    LEASE_ACQUIRE = "lease_acquire"
    LEASE_RENEW = "lease_renew"
    LEASE_TRANSFER = "lease_transfer"
    LEASE_RELEASE = "lease_release"
    LEASE_EXPIRE = "lease_expire"
    LEASE_FENCE = "lease_fence"
    LEASE_CONFLICT = "lease_conflict"
    LEASE_RECONCILE = "lease_reconcile"
    CROSS_OWNER_ATTEMPT = "cross_owner_attempt"
    CROSS_OWNER_GRANT = "cross_owner_grant"
    CROSS_OWNER_FENCE = "cross_owner_fence"
    RECONCILIATION_RESULT = "reconciliation_result"


class ReconciliationDisposition(StrEnum):
    """Outcome of reconciling a cross-owner reference."""

    RESOLVED = "resolved"
    STALE = "stale"
    CONTRADICTORY = "contradictory"
    MISSING = "missing"
    INDETERMINATE = "indeterminate"


# ── Required-field helper ──────────────────────────────────────────────────


def _required_str(value: str, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"{name} must be a non-empty string")
    return value


def _required_int(value: int, name: str, *, min_val: int = 0) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < min_val:
        raise ContractError(f"{name} must be an integer >= {min_val}")
    return value


# ── Outbox record ─────────────────────────────────────────────────────────


@dataclass(frozen=True)
class OutboxRecord(Contract):
    """Durable outbox record for Custody-owned writes with cross-owner references.

    Every outbox record carries typed references to the source records it
    depends on: a custody lease, a WBC attempt, a Run Authority grant, and
    a coordinator fence token.  These are read-only pointers — the outbox
    never duplicates the source state.

    Required fields:
      - outbox_id: unique outbox record identifier
      - lease_id: the custody lease this record references
      - record_type: semantic type (see OutboxRecordType)
      - status: lifecycle status (see OutboxRecordStatus)
      - occurred_at: ISO-8601 creation timestamp
      - idempotency_key: deterministic key for CAS

    Optional cross-owner references:
      - wbc_attempt_reference: the WBC attempt id (empty if none)
      - run_authority_grant_id: the Run Authority grant id (empty if none)
      - coordinator_fence_token: the coordinator fence token
      - occurrence_digest: the repair occurrence digest
      - custody_epoch: the custody epoch at time of record creation
    """

    contract_type: str = field(default="custody_outbox_record", init=False)
    schema_version: int = field(default=OUTBOX_SCHEMA_VERSION, init=False)

    outbox_id: str
    lease_id: str
    record_type: OutboxRecordType
    status: OutboxRecordStatus = OutboxRecordStatus.PENDING
    occurred_at: str = ""
    idempotency_key: str = ""
    wbc_attempt_reference: str = ""
    run_authority_grant_id: str = ""
    coordinator_fence_token: int = 0
    occurrence_digest: str = ""
    custody_epoch: int = 0
    causal_predecessor: str = ""
    payload: Mapping[str, Any] = field(default_factory=dict)
    payload_hash: str = field(init=False)

    def __post_init__(self) -> None:
        _required_str(self.outbox_id, "outbox_id")
        _required_str(self.lease_id, "lease_id")
        if not isinstance(self.record_type, OutboxRecordType):
            raise ContractError("record_type must be an OutboxRecordType")
        if not isinstance(self.status, OutboxRecordStatus):
            raise ContractError("status must be an OutboxRecordStatus")
        if not isinstance(self.occurred_at, str):
            raise ContractError("occurred_at must be a string")
        if not self.occurred_at.strip():
            object.__setattr__(self, "occurred_at",
                               datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
        _required_str(self.idempotency_key, "idempotency_key")
        if not isinstance(self.wbc_attempt_reference, str):
            raise ContractError("wbc_attempt_reference must be a string")
        if not isinstance(self.run_authority_grant_id, str):
            raise ContractError("run_authority_grant_id must be a string")
        if not isinstance(self.coordinator_fence_token, int) or isinstance(self.coordinator_fence_token, bool):
            raise ContractError("coordinator_fence_token must be an integer")
        if not isinstance(self.occurrence_digest, str):
            raise ContractError("occurrence_digest must be a string")
        if not isinstance(self.custody_epoch, int) or isinstance(self.custody_epoch, bool) or self.custody_epoch < 0:
            raise ContractError("custody_epoch must be a non-negative integer")
        if not isinstance(self.causal_predecessor, str):
            raise ContractError("causal_predecessor must be a string")
        # Freeze and hash payload
        from arnold_pipelines.megaplan.custody.contracts import _freeze_json_sorted as _freeze
        frozen = _freeze(self.payload)
        if not isinstance(frozen, Mapping):
            raise ContractError("payload must be an object")
        object.__setattr__(self, "payload", frozen)
        try:
            ph = _payload_digest(frozen)
        except Exception:
            ph = hashlib.sha256(
                canonical_json(dict(frozen)).encode("utf-8")
            ).hexdigest()
        object.__setattr__(self, "payload_hash", ph)

    def to_dict(self) -> dict[str, Any]:
        from arnold_pipelines.megaplan.custody.contracts import _thaw
        return {
            "contract_type": self.contract_type,
            "schema_version": self.schema_version,
            "outbox_id": self.outbox_id,
            "lease_id": self.lease_id,
            "record_type": self.record_type.value,
            "status": self.status.value,
            "occurred_at": self.occurred_at,
            "idempotency_key": self.idempotency_key,
            "wbc_attempt_reference": self.wbc_attempt_reference,
            "run_authority_grant_id": self.run_authority_grant_id,
            "coordinator_fence_token": self.coordinator_fence_token,
            "occurrence_digest": self.occurrence_digest,
            "custody_epoch": self.custody_epoch,
            "causal_predecessor": self.causal_predecessor,
            "payload": _thaw(self.payload),
            "payload_hash": self.payload_hash,
        }

    def to_json(self) -> str:
        return canonical_json(self.to_dict())


# ── Dead-letter record ────────────────────────────────────────────────────


@dataclass(frozen=True)
class DeadLetterRecord(Contract):
    """Dead-letter record for an unresolved outbox failure.

    Stores the original outbox record plus reconciliation diagnostics
    and join keys so operators can trace back to the source records
    (lease store, WBC attempt, Run Authority grant) for diagnosis.

    Required fields:
      - dead_letter_id: unique dead-letter identifier
      - original_outbox: the original OutboxRecord that failed reconciliation
      - disposition: the reconciliation disposition (stale/contradictory/missing/indeterminate)
      - diagnostics: human-readable and machine-readable diagnostics
      - occurred_at: ISO-8601 timestamp when the record was dead-lettered

    Join keys (for tracing back to source records):
      - lease_id
      - wbc_attempt_reference
      - run_authority_grant_id
      - coordinator_fence_token
      - occurrence_digest
    """

    contract_type: str = field(default="custody_dead_letter_record", init=False)
    schema_version: int = field(default=DEAD_LETTER_SCHEMA_VERSION, init=False)

    dead_letter_id: str
    original_outbox: OutboxRecord
    disposition: ReconciliationDisposition
    diagnostics: Mapping[str, Any]
    occurred_at: str = ""
    lease_id: str = ""
    wbc_attempt_reference: str = ""
    run_authority_grant_id: str = ""
    coordinator_fence_token: int = 0
    occurrence_digest: str = ""

    def __post_init__(self) -> None:
        _required_str(self.dead_letter_id, "dead_letter_id")
        if not isinstance(self.original_outbox, OutboxRecord):
            raise ContractError("original_outbox must be an OutboxRecord")
        if not isinstance(self.disposition, ReconciliationDisposition):
            raise ContractError("disposition must be a ReconciliationDisposition")
        if not isinstance(self.diagnostics, Mapping):
            raise ContractError("diagnostics must be a dict")
        if not isinstance(self.occurred_at, str) or not self.occurred_at.strip():
            object.__setattr__(self, "occurred_at",
                               datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
        # Derive join keys from original outbox if not explicitly set
        if not self.lease_id:
            object.__setattr__(self, "lease_id", self.original_outbox.lease_id)
        if not self.wbc_attempt_reference:
            object.__setattr__(self, "wbc_attempt_reference", self.original_outbox.wbc_attempt_reference)
        if not self.run_authority_grant_id:
            object.__setattr__(self, "run_authority_grant_id", self.original_outbox.run_authority_grant_id)
        if self.coordinator_fence_token == 0:
            object.__setattr__(self, "coordinator_fence_token", self.original_outbox.coordinator_fence_token)
        if not self.occurrence_digest:
            object.__setattr__(self, "occurrence_digest", self.original_outbox.occurrence_digest)

    @property
    def join_keys(self) -> dict[str, Any]:
        """Return the join keys for tracing back to source records."""
        return {
            "lease_id": self.lease_id,
            "wbc_attempt_reference": self.wbc_attempt_reference,
            "run_authority_grant_id": self.run_authority_grant_id,
            "coordinator_fence_token": self.coordinator_fence_token,
            "occurrence_digest": self.occurrence_digest,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_type": self.contract_type,
            "schema_version": self.schema_version,
            "dead_letter_id": self.dead_letter_id,
            "original_outbox": self.original_outbox.to_dict(),
            "disposition": self.disposition.value,
            "diagnostics": dict(self.diagnostics),
            "occurred_at": self.occurred_at,
            "join_keys": self.join_keys,
        }

    def to_json(self) -> str:
        return canonical_json(self.to_dict())


# ── Reconciliation result ──────────────────────────────────────────────────


@dataclass(frozen=True)
class ReconciliationResult:
    """Result of reconciling a single cross-owner reference."""

    reference_type: str  # "lease", "wbc_attempt", "run_authority_grant", "coordinator_fence"
    disposition: ReconciliationDisposition
    expected_value: Any
    observed_value: Any
    detail: str = ""
    source_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "reference_type": self.reference_type,
            "disposition": self.disposition.value,
            "expected_value": self.expected_value,
            "observed_value": self.observed_value,
            "detail": self.detail,
            "source_path": self.source_path,
        }


# ── Outbox store ───────────────────────────────────────────────────────────


def _record_path(base_dir: Path, outbox_id: str) -> Path:
    return base_dir / f"{outbox_id}.record.json"


def _history_path(base_dir: Path, outbox_id: str) -> Path:
    return base_dir / f"{outbox_id}.history.jsonl"


def _lock_path(base_dir: Path, outbox_id: str) -> Path:
    return base_dir / f"{outbox_id}.lock"


def _dead_letter_path(base_dir: Path, dead_letter_id: str) -> Path:
    return base_dir / "dead_letter" / f"{dead_letter_id}.json"


def _atomic_write(path: Path, content: str) -> None:
    """Write *content* to *path* atomically via temp-file + rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        fh.write(content)
    os.replace(tmp, path)


def _atomic_append(path: Path, line: str) -> None:
    """Append a single line to *path* atomically via temp-file + rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = ""
    if path.exists():
        try:
            existing = path.read_text(encoding="utf-8")
        except (FileNotFoundError, OSError):
            existing = ""
    _atomic_write(path, existing + line)


@dataclass
class CustodyOutbox:
    """Durable custody outbox store for single-owner writes and cross-owner references.

    Construct via :func:`open_outbox`.  Each instance manages outbox records
    under a single ``base_dir``.
    """

    base_dir: Path
    flock: bool = True

    def write_record(self, record: OutboxRecord) -> OutboxRecord:
        """Write an outbox record to durable storage.

        If a record with the same outbox_id already exists and has the same
        idempotency_key and payload_hash, this is a no-op (idempotent repeat).
        If the idempotency_key matches but the payload_hash differs, raises
        an error.

        Returns the record as written.
        """
        if not isinstance(record, OutboxRecord):
            raise ContractError("record must be an OutboxRecord")

        rec_path = _record_path(self.base_dir, record.outbox_id)

        # Check for existing record
        existing = self._read_record(record.outbox_id)
        if existing is not None:
            if existing.idempotency_key == record.idempotency_key:
                if existing.payload_hash == record.payload_hash:
                    # Idempotent repeat — no-op
                    return existing
                raise ContractError(
                    f"idempotency key {record.idempotency_key!r} maps to "
                    f"different payloads for outbox record {record.outbox_id!r}"
                )
            raise ContractError(
                f"outbox record {record.outbox_id!r} already exists with "
                f"different idempotency key"
            )

        # Serialize write
        if self.flock:
            self._write_flock(record)
        else:
            self._write_inproc(record)

        # Append to history
        if self.flock:
            self._append_history_flock(record)
        else:
            self._append_history_inproc(record)

        return record

    def update_status(self, outbox_id: str, new_status: OutboxRecordStatus) -> OutboxRecord:
        """Atomically update the status of an existing outbox record.

        Raises ContractError if the record does not exist.
        """
        existing = self._read_record(outbox_id)
        if existing is None:
            raise ContractError(f"outbox record {outbox_id!r} not found")

        updated = replace(existing, status=new_status)
        if self.flock:
            self._write_flock(updated)
        else:
            self._write_inproc(updated)
        self._append_history_inproc(updated)
        return updated

    def read_record(self, outbox_id: str) -> OutboxRecord | None:
        """Read an outbox record by id."""
        return self._read_record(outbox_id)

    def list_records(self) -> tuple[OutboxRecord, ...]:
        """List all outbox records in the store."""
        records: list[OutboxRecord] = []
        if not self.base_dir.exists():
            return ()
        for path in sorted(self.base_dir.glob("*.record.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (FileNotFoundError, OSError, json.JSONDecodeError):
                continue
            record = _normalize_outbox_record(data)
            if record is not None:
                records.append(record)
        return tuple(records)

    def records_by_status(self, status: OutboxRecordStatus) -> tuple[OutboxRecord, ...]:
        """Return all outbox records with a given status."""
        return tuple(r for r in self.list_records() if r.status == status)

    def records_by_lease(self, lease_id: str) -> tuple[OutboxRecord, ...]:
        """Return all outbox records for a given lease."""
        return tuple(r for r in self.list_records() if r.lease_id == lease_id)

    def move_to_dead_letter(
        self,
        record: OutboxRecord,
        disposition: ReconciliationDisposition,
        diagnostics: Mapping[str, Any],
        *,
        dead_letter_id: str | None = None,
    ) -> DeadLetterRecord:
        """Move an outbox record to the dead-letter store with joinable diagnostics.

        This atomically updates the record status to DEAD_LETTER and writes a
        dead-letter record with the original outbox data, reconciliation
        diagnostics, and join keys.
        """
        dl_id = dead_letter_id or f"dl-{record.outbox_id}-{uuid.uuid4().hex[:12]}"

        dl_record = DeadLetterRecord(
            dead_letter_id=dl_id,
            original_outbox=record,
            disposition=disposition,
            diagnostics=MappingProxyType(dict(diagnostics)),
        )

        # Write dead-letter record
        dl_path = _dead_letter_path(self.base_dir, dl_id)
        _atomic_write(dl_path, dl_record.to_json())

        # Update outbox record status
        self.update_status(record.outbox_id, OutboxRecordStatus.DEAD_LETTER)

        return dl_record

    def read_dead_letter(self, dead_letter_id: str) -> DeadLetterRecord | None:
        """Read a dead-letter record by id."""
        dl_path = _dead_letter_path(self.base_dir, dead_letter_id)
        if not dl_path.exists():
            return None
        try:
            data = json.loads(dl_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return None
        return _normalize_dead_letter(data)

    def list_dead_letters(self) -> tuple[DeadLetterRecord, ...]:
        """List all dead-letter records."""
        dl_dir = self.base_dir / "dead_letter"
        if not dl_dir.exists():
            return ()
        records: list[DeadLetterRecord] = []
        for path in sorted(dl_dir.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (FileNotFoundError, OSError, json.JSONDecodeError):
                continue
            r = _normalize_dead_letter(data)
            if r is not None:
                records.append(r)
        return tuple(records)

    def dead_letters_by_lease(self, lease_id: str) -> tuple[DeadLetterRecord, ...]:
        """Return dead-letter records joinable by lease_id."""
        return tuple(r for r in self.list_dead_letters() if r.lease_id == lease_id)

    def dead_letters_by_wbc_attempt(self, wbc_attempt_reference: str) -> tuple[DeadLetterRecord, ...]:
        """Return dead-letter records joinable by wbc_attempt_reference."""
        return tuple(
            r for r in self.list_dead_letters()
            if r.wbc_attempt_reference == wbc_attempt_reference
        )

    def dead_letters_by_grant(self, run_authority_grant_id: str) -> tuple[DeadLetterRecord, ...]:
        """Return dead-letter records joinable by run_authority_grant_id."""
        return tuple(
            r for r in self.list_dead_letters()
            if r.run_authority_grant_id == run_authority_grant_id
        )

    # -- internal helpers ----------------------------------------------------

    def _read_record(self, outbox_id: str) -> OutboxRecord | None:
        rec_path = _record_path(self.base_dir, outbox_id)
        if not rec_path.exists():
            return None
        try:
            data = json.loads(rec_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return None
        return _normalize_outbox_record(data)

    def _write_flock(self, record: OutboxRecord) -> None:
        import fcntl
        lock_p = _lock_path(self.base_dir, record.outbox_id)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        fd = os.open(lock_p, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            _atomic_write(_record_path(self.base_dir, record.outbox_id), record.to_json())
        finally:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            finally:
                os.close(fd)

    def _write_inproc(self, record: OutboxRecord) -> None:
        _atomic_write(_record_path(self.base_dir, record.outbox_id), record.to_json())

    def _append_history_flock(self, record: OutboxRecord) -> None:
        import fcntl
        lock_p = _lock_path(self.base_dir, record.outbox_id)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        fd = os.open(lock_p, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            _atomic_append(
                _history_path(self.base_dir, record.outbox_id),
                record.to_json() + "\n",
            )
        finally:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            finally:
                os.close(fd)

    def _append_history_inproc(self, record: OutboxRecord) -> None:
        _atomic_append(
            _history_path(self.base_dir, record.outbox_id),
            record.to_json() + "\n",
        )


# ── Normalize helpers ──────────────────────────────────────────────────────


def _normalize_outbox_record(data: Mapping[str, Any] | None) -> OutboxRecord | None:
    if not isinstance(data, Mapping):
        return None
    try:
        record_type_raw = data.get("record_type", "cross_owner_attempt")
        try:
            record_type = OutboxRecordType(record_type_raw)
        except ValueError:
            record_type = OutboxRecordType.CROSS_OWNER_ATTEMPT

        status_raw = data.get("status", "pending")
        try:
            status = OutboxRecordStatus(status_raw)
        except ValueError:
            status = OutboxRecordStatus.PENDING

        return OutboxRecord(
            outbox_id=data.get("outbox_id", ""),
            lease_id=data.get("lease_id", ""),
            record_type=record_type,
            status=status,
            occurred_at=data.get("occurred_at", ""),
            idempotency_key=data.get("idempotency_key", ""),
            wbc_attempt_reference=data.get("wbc_attempt_reference", ""),
            run_authority_grant_id=data.get("run_authority_grant_id", ""),
            coordinator_fence_token=data.get("coordinator_fence_token", 0),
            occurrence_digest=data.get("occurrence_digest", ""),
            custody_epoch=data.get("custody_epoch", 0),
            causal_predecessor=data.get("causal_predecessor", ""),
            payload=data.get("payload") or {},
        )
    except (ContractError, TypeError):
        return None


def _normalize_dead_letter(data: Mapping[str, Any] | None) -> DeadLetterRecord | None:
    if not isinstance(data, Mapping):
        return None
    try:
        original = _normalize_outbox_record(data.get("original_outbox"))
        if original is None:
            return None

        disp_raw = data.get("disposition", "indeterminate")
        try:
            disposition = ReconciliationDisposition(disp_raw)
        except ValueError:
            disposition = ReconciliationDisposition.INDETERMINATE

        return DeadLetterRecord(
            dead_letter_id=data.get("dead_letter_id", ""),
            original_outbox=original,
            disposition=disposition,
            diagnostics=data.get("diagnostics") or {},
            occurred_at=data.get("occurred_at", ""),
            lease_id=data.get("lease_id", ""),
            wbc_attempt_reference=data.get("wbc_attempt_reference", ""),
            run_authority_grant_id=data.get("run_authority_grant_id", ""),
            coordinator_fence_token=data.get("coordinator_fence_token", 0),
            occurrence_digest=data.get("occurrence_digest", ""),
        )
    except (ContractError, TypeError):
        return None


# ── Reconciliation ─────────────────────────────────────────────────────────


def reconcile_outbox_record(
    outbox: CustodyOutbox,
    record: OutboxRecord,
    *,
    lease_store: Any | None = None,
    wbc_attempt_reader: Any | None = None,
    run_authority_reader: Any | None = None,
) -> tuple[OutboxRecord, tuple[ReconciliationResult, ...]]:
    """Reconcile an outbox record by rereading source records.

    Parameters
    ----------
    outbox:
        The custody outbox store.
    record:
        The outbox record to reconcile.
    lease_store:
        Optional custody lease store (for reading lease state).  If None,
        lease references are not checked.
    wbc_attempt_reader:
        Optional callable ``(wbc_attempt_reference: str) -> dict | None``
        that reads a WBC attempt by reference.  If None, WBC references
        are not checked.
    run_authority_reader:
        Optional callable ``(grant_id: str) -> dict | None`` that reads a
        Run Authority grant by id.  If None, grant references are not
        checked.

    Returns
    -------
    (updated_record, results):
        The outbox record with updated status (RECONCILED or DEAD_LETTER)
        and a tuple of per-reference reconciliation results.
    """
    results: list[ReconciliationResult] = []

    # 1. Reconcile lease reference
    if lease_store is not None and record.lease_id:
        try:
            lease = lease_store.current_lease(record.lease_id)
        except Exception as exc:
            results.append(ReconciliationResult(
                reference_type="lease",
                disposition=ReconciliationDisposition.INDETERMINATE,
                expected_value=record.lease_id,
                observed_value=None,
                detail=f"failed to read lease: {exc}",
            ))
        else:
            if lease is None:
                results.append(ReconciliationResult(
                    reference_type="lease",
                    disposition=ReconciliationDisposition.MISSING,
                    expected_value=record.lease_id,
                    observed_value=None,
                    detail=f"lease {record.lease_id!r} not found in lease store",
                ))
            elif lease.lease_id != record.lease_id:
                results.append(ReconciliationResult(
                    reference_type="lease",
                    disposition=ReconciliationDisposition.CONTRADICTORY,
                    expected_value=record.lease_id,
                    observed_value=lease.lease_id,
                    detail="lease_id mismatch in lease store",
                ))
            elif lease.custody_epoch < record.custody_epoch:
                results.append(ReconciliationResult(
                    reference_type="lease",
                    disposition=ReconciliationDisposition.STALE,
                    expected_value=record.custody_epoch,
                    observed_value=lease.custody_epoch,
                    detail=f"lease epoch is behind outbox record: "
                           f"{lease.custody_epoch} < {record.custody_epoch}",
                ))
            else:
                results.append(ReconciliationResult(
                    reference_type="lease",
                    disposition=ReconciliationDisposition.RESOLVED,
                    expected_value=record.lease_id,
                    observed_value=lease.lease_id,
                    detail="lease reference resolved",
                ))

    # 2. Reconcile WBC attempt reference
    if wbc_attempt_reader is not None and record.wbc_attempt_reference:
        try:
            wbc_data = wbc_attempt_reader(record.wbc_attempt_reference)
        except Exception as exc:
            results.append(ReconciliationResult(
                reference_type="wbc_attempt",
                disposition=ReconciliationDisposition.INDETERMINATE,
                expected_value=record.wbc_attempt_reference,
                observed_value=None,
                detail=f"failed to read WBC attempt: {exc}",
            ))
        else:
            if wbc_data is None:
                results.append(ReconciliationResult(
                    reference_type="wbc_attempt",
                    disposition=ReconciliationDisposition.MISSING,
                    expected_value=record.wbc_attempt_reference,
                    observed_value=None,
                    detail=f"WBC attempt {record.wbc_attempt_reference!r} not found",
                ))
            else:
                results.append(ReconciliationResult(
                    reference_type="wbc_attempt",
                    disposition=ReconciliationDisposition.RESOLVED,
                    expected_value=record.wbc_attempt_reference,
                    observed_value=wbc_data.get("attempt_id", record.wbc_attempt_reference),
                    detail="WBC attempt reference resolved",
                ))

    # 3. Reconcile Run Authority grant reference
    if run_authority_reader is not None and record.run_authority_grant_id:
        try:
            grant_data = run_authority_reader(record.run_authority_grant_id)
        except Exception as exc:
            results.append(ReconciliationResult(
                reference_type="run_authority_grant",
                disposition=ReconciliationDisposition.INDETERMINATE,
                expected_value=record.run_authority_grant_id,
                observed_value=None,
                detail=f"failed to read grant: {exc}",
            ))
        else:
            if grant_data is None:
                results.append(ReconciliationResult(
                    reference_type="run_authority_grant",
                    disposition=ReconciliationDisposition.MISSING,
                    expected_value=record.run_authority_grant_id,
                    observed_value=None,
                    detail=f"grant {record.run_authority_grant_id!r} not found",
                ))
            else:
                expected_fence = record.coordinator_fence_token
                observed_fence = grant_data.get("coordinator_fence_token", 0)
                if expected_fence != 0 and observed_fence != expected_fence:
                    results.append(ReconciliationResult(
                        reference_type="run_authority_grant",
                        disposition=ReconciliationDisposition.CONTRADICTORY,
                        expected_value=expected_fence,
                        observed_value=observed_fence,
                        detail=f"coordinator fence token mismatch: "
                               f"{expected_fence} != {observed_fence}",
                    ))
                else:
                    results.append(ReconciliationResult(
                        reference_type="run_authority_grant",
                        disposition=ReconciliationDisposition.RESOLVED,
                        expected_value=record.run_authority_grant_id,
                        observed_value=grant_data.get("grant_id", record.run_authority_grant_id),
                        detail="run authority grant reference resolved",
                    ))

    # Determine overall disposition
    dispositions = {r.disposition for r in results}
    if ReconciliationDisposition.CONTRADICTORY in dispositions:
        overall = ReconciliationDisposition.CONTRADICTORY
    elif ReconciliationDisposition.MISSING in dispositions:
        overall = ReconciliationDisposition.MISSING
    elif ReconciliationDisposition.STALE in dispositions:
        overall = ReconciliationDisposition.STALE
    elif ReconciliationDisposition.INDETERMINATE in dispositions:
        overall = ReconciliationDisposition.INDETERMINATE
    else:
        overall = ReconciliationDisposition.RESOLVED

    if overall == ReconciliationDisposition.RESOLVED:
        updated = outbox.update_status(record.outbox_id, OutboxRecordStatus.RECONCILED)
    else:
        diagnostics: dict[str, Any] = {
            "reconciliation_results": [r.to_dict() for r in results],
            "overall_disposition": overall.value,
            "original_outbox_id": record.outbox_id,
        }
        outbox.move_to_dead_letter(record, overall, diagnostics)
        updated = replace(record, status=OutboxRecordStatus.DEAD_LETTER)

    return updated, tuple(results)


def reconcile_all_pending(
    outbox: CustodyOutbox,
    *,
    lease_store: Any | None = None,
    wbc_attempt_reader: Any | None = None,
    run_authority_reader: Any | None = None,
) -> tuple[tuple[OutboxRecord, ...], tuple[DeadLetterRecord, ...]]:
    """Reconcile all pending outbox records.

    Returns (reconciled_records, dead_letter_records).
    """
    pending = outbox.records_by_status(OutboxRecordStatus.PENDING)
    reconciled: list[OutboxRecord] = []
    dead: list[DeadLetterRecord] = []

    for record in pending:
        updated, results = reconcile_outbox_record(
            outbox, record,
            lease_store=lease_store,
            wbc_attempt_reader=wbc_attempt_reader,
            run_authority_reader=run_authority_reader,
        )
        if updated.status == OutboxRecordStatus.RECONCILED:
            reconciled.append(updated)
        else:
            # Find the corresponding dead-letter record
            dl_records = outbox.list_dead_letters()
            for dl in dl_records:
                if dl.original_outbox.outbox_id == record.outbox_id:
                    dead.append(dl)
                    break

    return tuple(reconciled), tuple(dead)


# ── Factory ────────────────────────────────────────────────────────────────


def open_outbox(
    base_dir: Path | None = None,
    *,
    flock: bool = True,
) -> CustodyOutbox:
    """Open a custody outbox store rooted at *base_dir*.

    If *base_dir* is ``None``, defaults to ``~/.megaplan/custody/outbox``.
    """
    import os as _os
    base = (base_dir or Path(_os.path.expanduser("~/.megaplan/custody/outbox"))).resolve()
    return CustodyOutbox(base_dir=base, flock=flock)


# ── Convenience: build an outbox record from a lease event ─────────────────


def build_outbox_record_from_event(
    event: CustodyLeaseEvent,
    *,
    outbox_id: str | None = None,
) -> OutboxRecord:
    """Build an outbox record from a custody lease event.

    The record_type is derived from the event's event_type.
    Cross-owner references (wbc_attempt_reference, run_authority_grant_id,
    coordinator_fence_token) are copied from the event.
    """
    _event_type_to_record_type: dict[str, OutboxRecordType] = {
        "acquire": OutboxRecordType.LEASE_ACQUIRE,
        "renew": OutboxRecordType.LEASE_RENEW,
        "transfer": OutboxRecordType.LEASE_TRANSFER,
        "release": OutboxRecordType.LEASE_RELEASE,
        "expire": OutboxRecordType.LEASE_EXPIRE,
        "fence": OutboxRecordType.LEASE_FENCE,
        "conflict": OutboxRecordType.LEASE_CONFLICT,
        "reconcile": OutboxRecordType.LEASE_RECONCILE,
    }

    record_type = _event_type_to_record_type.get(
        event.event_type, OutboxRecordType.CROSS_OWNER_ATTEMPT
    )

    return OutboxRecord(
        outbox_id=outbox_id or f"ob-{event.event_id}",
        lease_id=event.lease_id,
        record_type=record_type,
        status=OutboxRecordStatus.PENDING,
        occurred_at=event.occurred_at,
        idempotency_key=event.idempotency_key,
        wbc_attempt_reference=event.wbc_attempt_reference,
        run_authority_grant_id=event.run_authority_grant_id,
        coordinator_fence_token=event.coordinator_fence_token,
        occurrence_digest=event.occurrence_digest,
        custody_epoch=event.custody_epoch,
        causal_predecessor=event.causal_predecessor,
        payload=dict(event.payload) if event.payload else {},
    )


# ── Public API ─────────────────────────────────────────────────────────────


__all__ = [
    "CustodyOutbox",
    "DeadLetterRecord",
    "OutboxRecord",
    "OutboxRecordStatus",
    "OutboxRecordType",
    "ReconciliationDisposition",
    "ReconciliationResult",
    "build_outbox_record_from_event",
    "open_outbox",
    "reconcile_all_pending",
    "reconcile_outbox_record",
]
