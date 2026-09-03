"""Typed ChainControlJournal facade over the one IncidentLedger append door.

NBF-08 records are a ``chain_control.*`` suffix in the existing
``events.jsonl`` / ``.events.seq`` journal. This module owns schema, hashing,
strict replay, lock-ordered transactions, and the public CLI. Physical append
always goes through ``_IncidentEventJournal._emit_locked``.
"""

from __future__ import annotations

import argparse
import contextvars
import fcntl
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

ABSENT: dict[str, bool] = {"__nbf08_absent__": True}
ABSENT_KEY = "__nbf08_absent__"
_UNSET_STATE_REVISION = object()
SCHEMA_VERSION = "nbf08-chain-control-v1"
RESERVATION_SCHEMA = "nbf08-sequence-reservation-v1"
EVENT_DOMAIN = b"NBF08-CHAIN-CONTROL-EVENT-V1\x00"
PAYLOAD_DOMAIN = b"NBF08-CHAIN-CONTROL-PAYLOAD-V1\x00"
PHYSICAL_DOMAIN = b"NBF08-PHYSICAL-RECORD-V1\x00"
ZERO_DIGEST = "0" * 64
TRAILING_COLLISION_MIGRATION_SCHEMA = "nbf08-trailing-sequence-collision-migration-v1"
TRAILING_COLLISION_RECEIPT_SCHEMA = "nbf08-trailing-sequence-collision-receipt-v1"
INCIDENT_EVENTS_FILE = "events.jsonl"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_MIGRATION_OCCUPANCY_KEYS = frozenset(
    {
        "owner",
        "runner",
        "tmux_session",
        "chain_pid",
        "worker_pid",
        "fixer_owner",
        "fixer_pid",
        "provider_owner",
        "provider_pid",
        "provider_session",
    }
)

ENVELOPE_FIELDS: tuple[str, ...] = (
    "schema_version",
    "event_id",
    "event_kind",
    "operation_id",
    "causation_id",
    "correlation_id",
    "recovery_id",
    "chain_id",
    "parent_chain_id",
    "child_id",
    "run_id",
    "actor",
    "authority_mode",
    "ledger_id",
    "created_at",
    "physical_sequence",
    "evidence_sequence",
    "semantic_sequence",
    "previous_physical_digest",
    "previous_evidence_digest",
    "payload_digest",
    "event_hash",
    "intent",
    "semantic_effect",
    "expected_cursor",
    "expected_revision",
    "actual_cursor",
    "actual_revision",
    "pre_state_digest",
    "post_state_digest",
    "source_identity",
    "spec_identity",
    "config_identity",
    "runtime_identity",
    "linked_receipts",
    "outcome",
    "failure_class",
    "claim_class",
    "payload",
)

SEMANTIC_EFFECTS = frozenset({"advance", "metadata_only", "no_change"})
CLAIM_CLASSES = frozenset({"required", "linked", "evidence-only", "claimless-read", "held"})
AUTHORITY_TO_CLAIM = {
    "chain-authoritative": "required",
    "linked-domain": "linked",
    "read-only": "claimless-read",
    "external-unknown": "held",
}
SEMANTIC_KINDS = frozenset(
    {
        "chain_control.authority_selection",
        "chain_control.suffix_rebound",
        "chain_control.committed",
        "chain_control.reconciled",
        "chain_control.hold_released",
        "chain_control.source_rebound",
        "chain_control.config_rebound",
        "chain_control.runtime_rebound",
        "chain_control.hold_context_attested",
        "chain_control.backend_rebound",
        # A legacy restart receipt is immutable external evidence.  The
        # attestation is a real chain-control semantic transition because it
        # records the modern guard in chain state, but it never replays the
        # retired attempt.
        "chain_control.restart_receipt_attested",
    }
)
CLAIMLESS_KINDS = frozenset(
    {
        "chain_control.genesis_accepted",
        "chain_control.legacy_imported",
        "chain_control.sequence_reserved_tombstone",
        "chain_control.rejected",
        "chain_control.cas_conflict",
        "chain_control.tamper_detected",
        "chain_control.hold",
        "chain_control.hold_reconciled",
        "chain_control.hold_context_attested",
        "chain_control.replay",
        "chain_control.authority_validated",
        "chain_control.restart_receipt_attested",
        "chain_control.trailing_sequence_collision_quarantined",
    }
)
REQUIRES_CLAIM_KINDS = frozenset(
    {
        "chain_control.committed",
        "chain_control.authority_selection",
        "chain_control.suffix_rebound",
        "chain_control.source_rebound",
        "chain_control.config_rebound",
        "chain_control.runtime_rebound",
        "chain_control.backend_rebound",
        "chain_control.restart_receipt_attested",
        "chain_control.reconciled",
        "chain_control.external_effect_intent",
    }
)
ALL_KINDS = (
    SEMANTIC_KINDS
    | CLAIMLESS_KINDS
    | REQUIRES_CLAIM_KINDS
    | {
        "chain_control.intent",
        "chain_control.claimed",
        "chain_control.external_effect_result",
        "chain_control.reconcile_required",
        "chain_control.hold_released",
        "chain_control.hold_reconciled",
        "chain_control.hold_context_attested",
    }
)

_ACTIVE_TXN: contextvars.ContextVar[LockedChainControlTransaction | None] = contextvars.ContextVar(
    "nbf08_active_chain_control_txn", default=None
)
_SCOPE_LOCKS: contextvars.ContextVar[tuple[str, ...] | None] = contextvars.ContextVar(
    "nbf08_held_scope_locks", default=None
)


class ChainControlError(Exception):
    """Base typed chain-control failure."""

    def __init__(self, code: str, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.details = details or {}


class ChainControlHold(ChainControlError):
    """Fail-closed hold; no cursor advance or inferred success."""


class DurabilityUnknown(ChainControlHold):
    """Uncertain cutpoint; further effects are forbidden until reconcile."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__("DURABILITY_UNKNOWN", message, details=details)


class ChainControlCasConflict(ChainControlHold):
    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__("cas_conflict", message, details=details)


class ChainControlTamper(ChainControlHold):
    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__("tamper_detected", message, details=details)


class UnattributedStateChange(ChainControlHold):
    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__("unattributed_state_change", message, details=details)


def u64be(n: int) -> bytes:
    if not isinstance(n, int) or isinstance(n, bool) or n < 0 or n >= 2**64:
        raise ValueError("U64BE requires an unsigned 64-bit integer")
    return n.to_bytes(8, "big")


def frame_utf8(value: str) -> bytes:
    if not isinstance(value, str):
        raise ValueError("F() requires a UTF-8 string")
    encoded = value.encode("utf-8")
    return u64be(len(encoded)) + encoded


def frame_bytes(value: bytes) -> bytes:
    if not isinstance(value, (bytes, bytearray)):
        raise ValueError("F_BYTES requires raw bytes")
    raw = bytes(value)
    return u64be(len(raw)) + raw


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def payload_digest_for(payload: Any) -> str:
    return sha256_hex(PAYLOAD_DOMAIN + canonical_json(payload))


def event_preimage(
    *,
    authority_mode: str,
    ledger_id: str,
    chain_id: str,
    physical_sequence: int,
    evidence_sequence: int,
    semantic_sequence: int,
    event_id: str,
    event_kind: str,
    operation_id: str,
    causation_id: str,
    correlation_id: str,
    recovery_id: str,
    previous_physical_digest: str,
    previous_evidence_digest: str,
    payload: Any,
) -> bytes:
    digest = payload_digest_for(payload)
    return (
        EVENT_DOMAIN
        + frame_utf8(authority_mode)
        + frame_utf8(ledger_id)
        + frame_utf8(chain_id)
        + u64be(physical_sequence)
        + u64be(evidence_sequence)
        + u64be(semantic_sequence)
        + frame_utf8(event_id)
        + frame_utf8(event_kind)
        + frame_utf8(operation_id)
        + frame_utf8(causation_id)
        + frame_utf8(correlation_id)
        + frame_utf8(recovery_id)
        + frame_utf8(previous_physical_digest)
        + frame_utf8(previous_evidence_digest)
        + frame_utf8(digest)
        + frame_utf8(canonical_json(payload).decode("utf-8"))
    )


def compute_event_hash(**kwargs: Any) -> str:
    return sha256_hex(event_preimage(**kwargs))


def decode_hex_digest(value: str) -> bytes:
    if not isinstance(value, str) or len(value) != 64:
        raise ChainControlHold("malformed_digest", "digest must be 64 lowercase hex chars")
    try:
        raw = bytes.fromhex(value)
    except ValueError as exc:
        raise ChainControlHold("malformed_digest", "digest is not hex") from exc
    if value != value.lower():
        raise ChainControlHold("malformed_digest", "digest must be lowercase hex")
    return raw


def physical_record_digest(
    *,
    ledger_id: str,
    physical_sequence: int,
    record_type: str,
    stored_record_bytes: bytes,
    previous_physical_digest: str,
) -> str:
    previous_raw = decode_hex_digest(previous_physical_digest)
    preimage = (
        PHYSICAL_DOMAIN
        + frame_utf8(ledger_id)
        + u64be(physical_sequence)
        + frame_utf8(record_type)
        + frame_bytes(stored_record_bytes)
        + frame_bytes(previous_raw)
    )
    return sha256_hex(preimage)


def record_type_for(kind: str) -> str:
    text = str(kind or "")
    if text.startswith("chain_control."):
        return "chain_control"
    return "incident"


def claim_class_for_authority(authority_class: str) -> str:
    mapped = AUTHORITY_TO_CLAIM.get(authority_class)
    if mapped is None:
        raise ChainControlHold("invalid_claim_class", f"unknown authority_class {authority_class!r}")
    return mapped


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stable_id(*parts: str) -> str:
    return hashlib.sha256(canonical_json(list(parts))).hexdigest()


def _required_sha256(value: str, label: str) -> str:
    value = str(value or "").strip().lower()
    if _SHA256_RE.fullmatch(value) is None:
        raise ChainControlHold("invalid_migration_guard", f"{label} must be a full lowercase SHA-256")
    return value


def _path_sha256(path: Path, label: str) -> str:
    try:
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode):
            raise ChainControlHold("migration_guard_mismatch", f"{label} must be a regular file")
        return sha256_hex(path.read_bytes())
    except FileNotFoundError as exc:
        raise ChainControlHold("migration_guard_mismatch", f"{label} is missing") from exc


def _atomic_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        _fsync_dir(path.parent)
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def _fsync_dir(path: Path) -> None:
    """Make a preceding create/rename/unlink durable in *path*."""
    fd = os.open(str(path), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _durable_file(path: Path, data: bytes) -> None:
    """Create one staged file and persist its bytes before publication."""
    with open(path, "xb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


def workspace_snapshot_sha256(
    workspace: Path,
    *,
    excluded: Sequence[Path] = (),
) -> str:
    """Content-address a workspace without trusting mtimes or status prose."""
    workspace = Path(workspace).expanduser().resolve(strict=False)
    excluded_paths = tuple(Path(item).expanduser().resolve(strict=False) for item in excluded)

    def is_excluded(path: Path) -> bool:
        resolved = path.resolve(strict=False)
        return any(resolved == item or item in resolved.parents for item in excluded_paths)

    if not workspace.is_dir():
        raise ChainControlHold("migration_guard_mismatch", "workspace is not a directory")
    rows: list[dict[str, Any]] = []
    for path in sorted(workspace.rglob("*"), key=lambda item: item.as_posix()):
        if is_excluded(path) or ".git" in path.relative_to(workspace).parts:
            continue
        relative = path.relative_to(workspace).as_posix()
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode):
            rows.append({"path": relative, "kind": "symlink", "target": os.readlink(path)})
        elif stat.S_ISREG(info.st_mode):
            rows.append(
                {
                    "path": relative,
                    "kind": "file",
                    "size": info.st_size,
                    "sha256": sha256_hex(path.read_bytes()),
                }
            )
        elif stat.S_ISDIR(info.st_mode):
            rows.append({"path": relative, "kind": "directory"})
        else:
            rows.append({"path": relative, "kind": "other", "mode": stat.S_IFMT(info.st_mode)})
    return sha256_hex(b"NBF08-WORKSPACE-SNAPSHOT-V1\x00" + canonical_json(rows))


def _live_occupancy_path(value: Any, prefix: str = "") -> str | None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if str(key) in _MIGRATION_OCCUPANCY_KEYS and child not in (None, False, "", [], {}, 0):
                return path
            found = _live_occupancy_path(child, path)
            if found is not None:
                return found
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found = _live_occupancy_path(child, f"{prefix}[{index}]")
            if found is not None:
                return found
    return None


def ledger_id_for(ledger_dir: Path) -> str:
    return "ledger-" + hashlib.sha256(str(ledger_dir.resolve()).encode("utf-8")).hexdigest()[:16]


def chain_id_for_spec(spec_path: Path) -> str:
    resolved = spec_path.resolve(strict=False)
    return "chain-" + hashlib.sha256(str(resolved).encode("utf-8")).hexdigest()[:16]


def state_digest_for(payload: Any) -> str:
    return sha256_hex(b"NBF08-CHAIN-STATE-V1\x00" + canonical_json(payload))


def validate_payload(payload: Any) -> Any:
    if not isinstance(payload, dict):
        raise ChainControlHold("invalid_payload", "payload must be an object")
    if ABSENT_KEY in payload:
        raise ChainControlHold("reserved_absent_key", "user payloads may not use the reserved absent marker")
    return payload


def semantic_effect_for(kind: str, *, pre_digest: Any, post_digest: Any) -> str:
    if kind in SEMANTIC_KINDS:
        if pre_digest != post_digest and pre_digest is not ABSENT and post_digest is not ABSENT:
            return "advance"
        if kind in {"chain_control.authority_selection", "chain_control.suffix_rebound"}:
            return "metadata_only"
        return "no_change"
    return "no_change"


def build_envelope(
    *,
    event_kind: str,
    operation_id: str,
    causation_id: str,
    correlation_id: str,
    recovery_id: str,
    chain_id: str,
    authority_mode: str,
    ledger_id: str,
    physical_sequence: int,
    evidence_sequence: int,
    semantic_sequence: int,
    previous_physical_digest: str,
    previous_evidence_digest: str,
    payload: dict[str, Any],
    event_id: str | None = None,
    parent_chain_id: Any = None,
    child_id: Any = None,
    run_id: Any = None,
    actor: Any = None,
    created_at: str | None = None,
    intent: Any = None,
    semantic_effect: str,
    expected_cursor: Any = None,
    expected_revision: Any = None,
    actual_cursor: Any = None,
    actual_revision: Any = None,
    pre_state_digest: Any = None,
    post_state_digest: Any = None,
    source_identity: Any = None,
    spec_identity: Any = None,
    config_identity: Any = None,
    runtime_identity: Any = None,
    linked_receipts: Any = None,
    outcome: Any = None,
    failure_class: Any = None,
    claim_class: str,
) -> dict[str, Any]:
    if event_kind not in ALL_KINDS:
        raise ChainControlHold("invalid_event_kind", f"unknown event kind {event_kind!r}")
    if semantic_effect not in SEMANTIC_EFFECTS:
        raise ChainControlHold("invalid_semantic_effect", f"invalid semantic_effect {semantic_effect!r}")
    if claim_class not in CLAIM_CLASSES:
        raise ChainControlHold("invalid_claim_class", f"invalid claim_class {claim_class!r}")
    lineage = (operation_id, causation_id, correlation_id, recovery_id, authority_mode, ledger_id)
    if event_kind == "chain_control.sequence_reserved_tombstone":
        if not all(item is None or (isinstance(item, str) and item) for item in (operation_id, causation_id, correlation_id)):
            raise ChainControlHold("missing_lineage", "tombstone lineage must be null or a non-empty string")
        if not all(isinstance(item, str) and item for item in (recovery_id, authority_mode, ledger_id)):
            raise ChainControlHold("missing_lineage", "tombstone recovery/authority identities must be non-empty strings")
    elif not all(isinstance(item, str) and item for item in lineage + (chain_id,)):
        raise ChainControlHold("missing_lineage", "mandatory lineage identities must be non-empty strings")
    payload = validate_payload(payload)
    digest = payload_digest_for(payload)
    event_id = event_id or _stable_id(event_kind, operation_id, str(physical_sequence), digest)
    envelope = {
        "schema_version": SCHEMA_VERSION,
        "event_id": event_id,
        "event_kind": event_kind,
        "operation_id": operation_id,
        "causation_id": causation_id,
        "correlation_id": correlation_id,
        "recovery_id": recovery_id,
        "chain_id": chain_id,
        "parent_chain_id": parent_chain_id,
        "child_id": child_id,
        "run_id": run_id,
        "actor": actor,
        "authority_mode": authority_mode,
        "ledger_id": ledger_id,
        "created_at": created_at or _now(),
        "physical_sequence": physical_sequence,
        "evidence_sequence": evidence_sequence,
        "semantic_sequence": semantic_sequence,
        "previous_physical_digest": previous_physical_digest,
        "previous_evidence_digest": previous_evidence_digest,
        "payload_digest": digest,
        "event_hash": "",
        "intent": intent,
        "semantic_effect": semantic_effect,
        "expected_cursor": expected_cursor,
        "expected_revision": expected_revision,
        "actual_cursor": actual_cursor,
        "actual_revision": actual_revision,
        "pre_state_digest": pre_state_digest,
        "post_state_digest": post_state_digest,
        "source_identity": source_identity,
        "spec_identity": spec_identity,
        "config_identity": config_identity,
        "runtime_identity": runtime_identity,
        "linked_receipts": linked_receipts if linked_receipts is not None else [],
        "outcome": outcome,
        "failure_class": failure_class,
        "claim_class": claim_class,
        "payload": payload,
    }
    missing = [key for key in ENVELOPE_FIELDS if key not in envelope]
    if missing:
        raise ChainControlHold("incomplete_envelope", f"missing envelope keys {missing}")
    envelope["event_hash"] = compute_event_hash(
        authority_mode=authority_mode,
        ledger_id=ledger_id,
        chain_id=chain_id or "chainless",
        physical_sequence=physical_sequence,
        evidence_sequence=evidence_sequence,
        semantic_sequence=semantic_sequence,
        event_id=event_id,
        event_kind=event_kind,
        operation_id=operation_id,
        causation_id=causation_id,
        correlation_id=correlation_id,
        recovery_id=recovery_id,
        previous_physical_digest=previous_physical_digest,
        previous_evidence_digest=previous_evidence_digest,
        payload=payload,
    )
    return envelope


def reservation_digest_for(envelope: Mapping[str, Any]) -> str:
    body = {key: value for key, value in envelope.items() if key != "reservation_digest"}
    return sha256_hex(b"NBF08-SEQUENCE-RESERVATION-V1\x00" + canonical_json(body))


def empty_reservation(*, ledger_id: str, physical_sequence: int, status: str, previous_physical_digest: str) -> dict[str, Any]:
    envelope = {
        "schema_version": RESERVATION_SCHEMA,
        "reservation_id": _stable_id("reservation", ledger_id, str(physical_sequence), status),
        "ledger_id": ledger_id,
        "authority_mode": "file",
        "physical_sequence": physical_sequence,
        "status": status,
        "scope": "chainless",
        "chain_id": None,
        "event_id": None,
        "event_kind": None,
        "operation_id": None,
        "causation_id": None,
        "correlation_id": None,
        "recovery_id": "none",
        "evidence_sequence": None,
        "semantic_sequence": None,
        "record_type": "incident",
        "intended_record_sha256": ZERO_DIGEST,
        "previous_physical_digest": previous_physical_digest,
        "byte_offset": 0,
        "line_number": 0,
        "created_at": _now(),
        "reservation_digest": "",
    }
    envelope["reservation_digest"] = reservation_digest_for(envelope)
    return envelope


def parse_sidecar_bytes(raw: bytes) -> tuple[str, Any]:
    stripped = raw.strip()
    if not stripped:
        return "empty", None
    try:
        as_text = stripped.decode("ascii")
    except UnicodeDecodeError as exc:
        raise DurabilityUnknown("sequence sidecar is not ASCII", details={"bytes": len(raw)}) from exc
    if as_text.isdigit() and "\n" not in as_text and "\r" not in as_text:
        return "integer", int(as_text)
    try:
        parsed = json.loads(as_text)
    except json.JSONDecodeError as exc:
        raise DurabilityUnknown("sequence sidecar is neither integer nor reservation JSON") from exc
    if not isinstance(parsed, dict) or parsed.get("schema_version") != RESERVATION_SCHEMA:
        raise DurabilityUnknown("sequence sidecar JSON is not nbf08-sequence-reservation-v1")
    return "reservation", parsed


def migrate_integer_sidecar(
    *,
    raw: bytes,
    current: int,
    highest_complete: int,
    ledger_id: str,
    previous_physical_digest: str,
) -> dict[str, Any]:
    if current < 0:
        raise DurabilityUnknown("legacy sequence sidecar is negative")
    if current < highest_complete:
        raise DurabilityUnknown(
            "legacy sequence sidecar is stale",
            details={"sidecar": current, "highest_complete": highest_complete},
        )
    if current > highest_complete + 1:
        raise DurabilityUnknown(
            "legacy sequence sidecar is ahead of the ledger",
            details={"sidecar": current, "highest_complete": highest_complete},
        )
    reservation = empty_reservation(
        ledger_id=ledger_id,
        physical_sequence=current,
        status="committed" if current == highest_complete else "reserved",
        previous_physical_digest=previous_physical_digest,
    )
    reservation["migration_receipt"] = {
        "original_bytes_hex": raw.hex(),
        "original_integer": current,
        "highest_complete": highest_complete,
    }
    reservation["reservation_digest"] = reservation_digest_for(
        {key: value for key, value in reservation.items() if key != "reservation_digest"}
    )
    return reservation


def write_sidecar_locked(seq_fd: int, payload: bytes) -> None:
    os.lseek(seq_fd, 0, os.SEEK_SET)
    os.write(seq_fd, payload)
    os.ftruncate(seq_fd, os.lseek(seq_fd, 0, os.SEEK_CUR))
    os.fsync(seq_fd)


def write_reservation_locked(seq_fd: int, reservation: Mapping[str, Any]) -> None:
    body = dict(reservation)
    body["reservation_digest"] = reservation_digest_for(body)
    write_sidecar_locked(seq_fd, canonical_json(body))


def read_sidecar_locked(seq_fd: int) -> bytes:
    os.lseek(seq_fd, 0, os.SEEK_SET)
    chunks: list[bytes] = []
    while True:
        piece = os.read(seq_fd, 65536)
        if not piece:
            break
        chunks.append(piece)
    return b"".join(chunks)


def validate_reservation_integrity(
    reservation: Mapping[str, Any],
    *,
    ledger_id: str,
) -> None:
    """Validate the self-authenticating portion of a sequence reservation."""
    if reservation.get("schema_version") != RESERVATION_SCHEMA:
        raise DurabilityUnknown("sequence reservation has the wrong schema")
    if reservation.get("ledger_id") != ledger_id:
        raise DurabilityUnknown("sequence reservation belongs to another ledger")
    sequence = reservation.get("physical_sequence")
    if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < -1:
        raise DurabilityUnknown("sequence reservation has an invalid physical_sequence")
    supplied = reservation.get("reservation_digest")
    expected = reservation_digest_for(reservation)
    if supplied != expected:
        raise DurabilityUnknown("sequence reservation digest mismatch")


def validate_reservation_tip(
    reservation: Mapping[str, Any],
    *,
    ledger_id: str,
    physical: Sequence[PhysicalRecord],
) -> None:
    """Require a committed sidecar to describe the exact complete file tip.

    The sidecar is recovery evidence, not a second sequence allocator.  A
    writer may proceed only when its committed reservation names the final
    complete record, its bytes, and that record's predecessor digest.
    """
    validate_reservation_integrity(reservation, ledger_id=ledger_id)
    if reservation.get("status") not in {"committed", "tombstoned"}:
        raise DurabilityUnknown(
            "sequence reservation is not committed",
            details={"status": reservation.get("status")},
        )
    complete = [item for item in physical if not item.torn]
    highest = highest_complete_seq(complete)
    sequence = int(reservation["physical_sequence"])
    if sequence != highest:
        raise DurabilityUnknown(
            "committed sequence reservation is stale",
            details={"reservation": sequence, "highest_complete": highest},
        )
    if highest < 0:
        expected_previous = ZERO_DIGEST
        expected_line = ZERO_DIGEST
    else:
        matches = [item for item in complete if item.record.get("seq") == highest]
        if len(matches) != 1 or matches[0] is not complete[-1]:
            raise DurabilityUnknown("committed sequence reservation does not name one final record")
        expected_previous = (
            physical_digest_after(ledger_id, complete, upto_seq=highest - 1)
            if len(complete) > 1
            else ZERO_DIGEST
        )
        expected_line = stored_line_sha256(matches[0].raw)
    if reservation.get("previous_physical_digest") != expected_previous:
        raise DurabilityUnknown("committed sequence reservation predecessor is stale")
    if reservation.get("intended_record_sha256") != expected_line:
        raise DurabilityUnknown("committed sequence reservation record hash is stale")


def canonical_committed_reservation(
    reservation: Mapping[str, Any],
    *,
    ledger_id: str,
    physical: Sequence[PhysicalRecord],
) -> dict[str, Any]:
    """Upgrade a just-migrated integer sidecar to exact tip evidence."""
    complete = [item for item in physical if not item.torn]
    highest = highest_complete_seq(complete)
    body = dict(reservation)
    if highest < 0:
        body["previous_physical_digest"] = ZERO_DIGEST
        body["intended_record_sha256"] = ZERO_DIGEST
    else:
        final = complete[-1]
        if final.record.get("seq") != highest:
            raise DurabilityUnknown("integer sidecar migration has a non-final highest sequence")
        body["previous_physical_digest"] = (
            physical_digest_after(ledger_id, complete, upto_seq=highest - 1)
            if len(complete) > 1
            else ZERO_DIGEST
        )
        body["intended_record_sha256"] = stored_line_sha256(final.raw)
    body["reservation_digest"] = reservation_digest_for(body)
    return body


@dataclass
class PhysicalRecord:
    line_number: int
    byte_offset: int
    raw: bytes
    record: dict[str, Any]
    torn: bool = False


def read_physical_lines(path: Path) -> list[PhysicalRecord]:
    if not path.exists():
        return []
    data = path.read_bytes()
    records: list[PhysicalRecord] = []
    offset = 0
    line_number = 0
    if not data:
        return records
    parts = data.split(b"\n")
    trailing_newline = data.endswith(b"\n")
    complete = parts[:-1] if trailing_newline else parts[:-1]
    remainder = b"" if trailing_newline else parts[-1]
    for index, raw in enumerate(complete):
        line_number = index + 1
        if raw == b"":
            raise ChainControlHold("malformed_line", "empty complete line is not a torn tail")
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ChainControlHold("malformed_line", "malformed complete JSON line") from exc
        if not isinstance(parsed, dict):
            raise ChainControlHold("malformed_line", "complete record is not an object")
        records.append(PhysicalRecord(line_number=line_number, byte_offset=offset, raw=raw, record=parsed))
        offset += len(raw) + 1
    if remainder:
        line_number = len(complete) + 1
        try:
            parsed = json.loads(remainder.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            records.append(
                PhysicalRecord(
                    line_number=line_number,
                    byte_offset=offset,
                    raw=remainder,
                    record={},
                    torn=True,
                )
            )
            return records
        if not trailing_newline:
            records.append(
                PhysicalRecord(
                    line_number=line_number,
                    byte_offset=offset,
                    raw=remainder,
                    record=parsed if isinstance(parsed, dict) else {},
                    torn=True,
                )
            )
            return records
        if not isinstance(parsed, dict):
            raise ChainControlHold("malformed_line", "complete record is not an object")
        records.append(PhysicalRecord(line_number=line_number, byte_offset=offset, raw=remainder, record=parsed))
    return records


def highest_complete_seq(records: Sequence[PhysicalRecord]) -> int:
    highest = -1
    for item in records:
        if item.torn:
            continue
        seq = item.record.get("seq")
        if isinstance(seq, int) and not isinstance(seq, bool):
            highest = max(highest, seq)
    return highest


def physical_digest_after(
    ledger_id: str,
    records: Sequence[PhysicalRecord],
    *,
    upto_seq: int | None = None,
) -> str:
    previous = ZERO_DIGEST
    for item in records:
        if item.torn:
            continue
        seq = item.record.get("seq")
        if not isinstance(seq, int) or isinstance(seq, bool):
            continue
        if upto_seq is not None and seq > upto_seq:
            break
        previous = physical_record_digest(
            ledger_id=ledger_id,
            physical_sequence=seq,
            record_type=record_type_for(str(item.record.get("kind") or "")),
            stored_record_bytes=item.raw,
            previous_physical_digest=previous,
        )
        if upto_seq is not None and seq == upto_seq:
            break
    return previous


def stored_line_sha256(raw: bytes) -> str:
    return sha256_hex(raw)


def replay_tuple_for(
    *,
    authority_mode: Any,
    chain_id: Any,
    operation_id: Any,
    intent_kind: Any,
    expected_revision: Any,
) -> tuple[Any, Any, Any, Any, Any]:
    return (authority_mode, chain_id, operation_id, intent_kind, expected_revision)


def envelope_replay_tuple(envelope: Mapping[str, Any]) -> tuple[Any, Any, Any, Any, Any]:
    intent = envelope.get("intent")
    if intent is None and isinstance(envelope.get("payload"), dict):
        intent = envelope["payload"].get("intent_kind")
    return replay_tuple_for(
        authority_mode=envelope.get("authority_mode"),
        chain_id=envelope.get("chain_id"),
        operation_id=envelope.get("operation_id"),
        intent_kind=intent,
        expected_revision=envelope.get("expected_revision"),
    )


REPLAYABLE_OPERATION_KINDS = frozenset(
    {
        "chain_control.committed",
        "chain_control.rejected",
        "chain_control.cas_conflict",
        "chain_control.genesis_accepted",
        "chain_control.suffix_rebound",
        "chain_control.runtime_rebound",
        "chain_control.hold_released",
        "chain_control.hold_reconciled",
        "chain_control.hold_context_attested",
        "chain_control.restart_receipt_attested",
        "chain_control.trailing_sequence_collision_quarantined",
    }
)


def _operation_statuses(replay: Mapping[str, Any], chain_id: str) -> dict[str, str]:
    """Return the durable terminal-or-incomplete status for each chain operation."""
    statuses: dict[str, str] = {}
    for event in replay.get("accepted") or []:
        if event.get("chain_id") != chain_id:
            continue
        operation_id = event.get("operation_id")
        if not isinstance(operation_id, str) or not operation_id:
            continue
        event_kind = str(event.get("event_kind") or "")
        if operation_id not in statuses or event_kind in REPLAYABLE_OPERATION_KINDS:
            statuses[operation_id] = event_kind
    return statuses


def _incomplete_operation_statuses(replay: Mapping[str, Any], chain_id: str) -> dict[str, str]:
    return {
        operation_id: event_kind
        for operation_id, event_kind in _operation_statuses(replay, chain_id).items()
        if event_kind not in REPLAYABLE_OPERATION_KINDS
    }


def observed_repo_base_sha256(start: Path | None = None) -> str:
    cwd = Path.cwd() if start is None else Path(start)
    try:
        head = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=str(cwd),
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ChainControlHold("missing_repo_base", "unable to observe repository HEAD") from exc
    if not re.fullmatch(r"[0-9a-f]{40}", head):
        raise ChainControlHold("invalid_repo_base", "repository HEAD is not a 40-char SHA")
    return sha256_hex(head.encode("utf-8"))


def recorded_authority_for(replay: Mapping[str, Any], chain_id: str) -> str:
    recorded = "file"
    for event in replay.get("accepted") or []:
        if event.get("chain_id") != chain_id:
            continue
        kind = event.get("event_kind")
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        if kind == "chain_control.genesis_accepted":
            recorded = str(payload.get("authority_mode") or event.get("authority_mode") or recorded)
        elif kind == "chain_control.suffix_rebound":
            recorded = str(payload.get("to_authority") or recorded)
        elif kind == "chain_control.authority_selection":
            recorded = str(payload.get("authority_mode") or event.get("authority_mode") or recorded)
    return recorded


def _inject_nbf08_dependency_text(raw: bytes, *, kind: str) -> bytes:
    text = raw.decode("utf-8")
    if "NBF-08" in text:
        return raw
    if kind == "tasklist":
        suffix = "" if text.endswith("\n") else "\n"
        return (text + suffix + "depends: NBF-08\n").encode("utf-8")
    suffix = "" if text.endswith("\n") else "\n"
    return (text + suffix + "dependencies:\n  - NBF-08\n").encode("utf-8")


def cas_chain_state_effect(
    txn: "LockedChainControlTransaction",
    spec_path: Path,
    payload: Mapping[str, Any],
    *,
    expected_revision: Any = None,
) -> dict[str, Any]:
    from arnold_pipelines.megaplan.chain.spec import _state_path_for

    state_path = _state_path_for(spec_path)
    adapter = ChainStateAdapter(txn, state_path)
    before = adapter.read_expected()
    verify_bound_state_matches_journal(spec_path, before)
    pre = state_digest_for(before) if before is not None else ZERO_DIGEST
    revision = expected_revision
    if revision is None:
        revision = None if before is None else (before.get("metadata") or {}).get("_nbf08_revision")
    written = adapter.cas_write(payload, expected_revision=revision)
    return {
        "pre_state_digest": pre,
        "post_state_digest": state_digest_for(written),
        "actual_revision": (written.get("metadata") or {}).get("_nbf08_revision"),
        "actual_cursor": written.get("current_milestone_index"),
    }


class ChainStateAdapter:
    """Read/CAS helper. May not append events or acquire locks."""

    def __init__(self, txn: LockedChainControlTransaction, state_path: Path) -> None:
        self._txn = txn
        self.state_path = state_path

    def read_expected(self) -> dict[str, Any] | None:
        self._txn.assert_open()
        if not self.state_path.exists():
            return None
        text = self.state_path.read_text(encoding="utf-8").strip()
        if not text:
            return None
        return json.loads(text)

    def cas_write(self, payload: Mapping[str, Any], *, expected_revision: Any) -> dict[str, Any]:
        self._txn.assert_open()
        current = self.read_expected()
        current_revision = None if current is None else current.get("metadata", {}).get("_nbf08_revision")
        if expected_revision != current_revision:
            raise ChainControlCasConflict(
                "stale chain-state revision",
                details={"expected": expected_revision, "actual": current_revision},
            )
        body = dict(payload)
        metadata = dict(body.get("metadata") or {})
        next_revision = 0 if current_revision is None else int(current_revision) + 1
        metadata["_nbf08_revision"] = next_revision
        body["metadata"] = metadata
        encoded = json.dumps(body, indent=2) + "\n"
        tmp = self.state_path.with_suffix(".tmp")
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(encoded, encoding="utf-8")
        tmp.replace(self.state_path)
        return body


class EpicStateAdapter(ChainStateAdapter):
    """Epic-state CAS helper. Same constraints as ChainStateAdapter."""


class LockedChainControlTransaction:
    """Lock-ordered chain-control transaction over the IncidentLedger flock."""

    def __init__(
        self,
        journal: ChainControlJournal,
        *,
        chain_ids: Sequence[str],
        state_paths: Sequence[Path],
        expected_revision: Any,
        operation_id: str,
        actor: Any,
    ) -> None:
        self.journal = journal
        self.chain_ids = tuple(sorted({str(item) for item in chain_ids if item}))
        self.state_paths = tuple(sorted({Path(item).resolve(strict=False) for item in state_paths}))
        self.expected_revision = expected_revision
        self.operation_id = operation_id
        self.actor = actor
        self._journal_lock_fd: int | None = None
        self._seq_fd: int | None = None
        self._lock_fds: list[int] = []
        self._token: contextvars.Token | None = None
        self._scope_token: contextvars.Token | None = None
        self._open = False
        self.records: list[dict[str, Any]] = []
        self.result: dict[str, Any] | None = None

    def assert_open(self) -> None:
        if not self._open:
            raise ChainControlHold("transaction_closed", "LockedChainControlTransaction is not active")

    def __enter__(self) -> LockedChainControlTransaction:
        if _SCOPE_LOCKS.get():
            raise ChainControlHold("lock_reentry", "public writer re-entry under an existing lock stack is forbidden")
        lock_fd = self.journal.ledger._journal.open_journal_lock()
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        self._journal_lock_fd = lock_fd
        try:
            self._seq_fd = self.journal.ledger._journal.open_sequence_after_lock()
            fcntl.flock(self._seq_fd, fcntl.LOCK_EX)
            self.journal.recover_reservations_locked(self._seq_fd)
            for chain_id in self.chain_ids:
                lock_path = self.journal.scope_lock_path(chain_id)
                lock_path.parent.mkdir(parents=True, exist_ok=True)
                lock_fd = os.open(str(lock_path), os.O_RDWR | os.O_CREAT, 0o644)
                fcntl.flock(lock_fd, fcntl.LOCK_EX)
                self._lock_fds.append(lock_fd)
            for state_path in self.state_paths:
                state_path.parent.mkdir(parents=True, exist_ok=True)
                lock_fd = os.open(str(state_path), os.O_RDWR | os.O_CREAT, 0o644)
                fcntl.flock(lock_fd, fcntl.LOCK_EX)
                self._lock_fds.append(lock_fd)
            self.records = self.journal.ledger._journal._read_records()
            self._open = True
            self._token = _ACTIVE_TXN.set(self)
            self._scope_token = _SCOPE_LOCKS.set(self.chain_ids)
            return self
        except Exception:
            self._release()
            raise

    def __exit__(self, exc_type, exc, tb) -> None:
        self._release()

    def _release(self) -> None:
        self._open = False
        if self._token is not None:
            _ACTIVE_TXN.reset(self._token)
            self._token = None
        if self._scope_token is not None:
            _SCOPE_LOCKS.reset(self._scope_token)
            self._scope_token = None
        for lock_fd in reversed(self._lock_fds):
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
            except OSError:
                pass
            try:
                os.close(lock_fd)
            except OSError:
                pass
        self._lock_fds = []
        if self._seq_fd is not None:
            try:
                fcntl.flock(self._seq_fd, fcntl.LOCK_UN)
            except OSError:
                pass
            try:
                os.close(self._seq_fd)
            except OSError:
                pass
            self._seq_fd = None
        if self._journal_lock_fd is not None:
            try:
                fcntl.flock(self._journal_lock_fd, fcntl.LOCK_UN)
            except OSError:
                pass
            try:
                os.close(self._journal_lock_fd)
            except OSError:
                pass
            self._journal_lock_fd = None

    def append(self, envelope: dict[str, Any]) -> dict[str, Any]:
        self.assert_open()
        if self._seq_fd is None:
            raise DurabilityUnknown("sequence lock missing during append")
        record = self.journal.ledger._append_nbf_locked(
            self._seq_fd,
            envelope,
            self.records,
            _chain_control=envelope,
        )
        self.records = self.journal.ledger._journal._read_records()
        return record


class ChainControlJournal:
    """Facade over IncidentLedger.events.jsonl and its sequence lock."""

    def __init__(self, ledger: Any) -> None:
        self.ledger = ledger
        self.ledger_id = ledger_id_for(ledger.ledger_dir)

    def scope_lock_path(self, chain_id: str) -> Path:
        return self.ledger.ledger_dir / ".nbf08-locks" / f"chain.{chain_id}.lock"

    def transaction(
        self,
        *,
        chain_ids: Sequence[str],
        state_paths: Sequence[Path] = (),
        expected_revision: Any = None,
        operation_id: str,
        actor: Any = None,
    ) -> LockedChainControlTransaction:
        return LockedChainControlTransaction(
            self,
            chain_ids=chain_ids,
            state_paths=state_paths,
            expected_revision=expected_revision,
            operation_id=operation_id,
            actor=actor,
        )

    def recover_reservations_locked(self, seq_fd: int) -> dict[str, Any] | None:
        raw = read_sidecar_locked(seq_fd)
        kind, parsed = parse_sidecar_bytes(raw)
        all_physical = read_physical_lines(self.ledger.events_path)
        torn = [item for item in all_physical if item.torn]
        physical = [item for item in all_physical if not item.torn]
        highest = highest_complete_seq(physical)
        previous = physical_digest_after(self.ledger_id, physical)
        if kind == "empty":
            return None
        if kind == "integer":
            if parsed > highest + 1:
                raise DurabilityUnknown(
                    "legacy sequence sidecar is ahead of the ledger",
                    details={"sidecar": parsed, "highest_complete": highest},
                )
            reservation = migrate_integer_sidecar(
                raw=raw,
                current=parsed,
                highest_complete=highest,
                ledger_id=self.ledger_id,
                previous_physical_digest=previous,
            )
            if reservation.get("status") == "committed":
                reservation = canonical_committed_reservation(
                    reservation,
                    ledger_id=self.ledger_id,
                    physical=physical,
                )
            write_reservation_locked(seq_fd, reservation)
            if reservation.get("status") == "reserved":
                return self._recover_reserved_locked(seq_fd, reservation, physical, previous, torn=torn)
            if torn:
                raise DurabilityUnknown("journal has a torn tail without an active reservation")
            validate_reservation_tip(
                reservation,
                ledger_id=self.ledger_id,
                physical=physical,
            )
            return reservation
        reservation = parsed
        validate_reservation_integrity(reservation, ledger_id=self.ledger_id)
        status = reservation.get("status")
        if status == "reserved":
            return self._recover_reserved_locked(seq_fd, reservation, physical, previous, torn=torn)
        if torn:
            raise DurabilityUnknown("journal has a torn tail without an active reservation")
        if status == "committed":
            validate_reservation_tip(
                reservation,
                ledger_id=self.ledger_id,
                physical=physical,
            )
            return reservation
        if status == "tombstoned":
            validate_reservation_tip(
                reservation,
                ledger_id=self.ledger_id,
                physical=physical,
            )
            return reservation
        raise DurabilityUnknown("reservation sidecar has an unknown status", details={"status": status})

    def _recover_reserved_locked(
        self,
        seq_fd: int,
        reservation: dict[str, Any],
        physical: Sequence[PhysicalRecord],
        previous: str,
        *,
        torn: Sequence[PhysicalRecord] = (),
    ) -> dict[str, Any]:
        reserved_seq = reservation.get("physical_sequence")
        matching = [item for item in physical if item.record.get("seq") == reserved_seq]
        reservation_id = reservation.get("reservation_id")
        intended = reservation.get("intended_record_sha256")
        highest = highest_complete_seq(physical)
        if reserved_seq not in {highest, highest + 1}:
            raise DurabilityUnknown(
                "reserved sequence is stale or ahead of the verified journal prefix",
                details={"reservation": reserved_seq, "highest_complete": highest},
            )
        expected_previous = (
            physical_digest_after(self.ledger_id, physical, upto_seq=int(reserved_seq) - 1)
            if matching
            else previous
        )
        if reservation.get("previous_physical_digest") != expected_previous:
            raise DurabilityUnknown("reserved sequence predecessor is stale")
        if torn:
            if len(torn) != 1 or matching:
                raise DurabilityUnknown("reserved sequence has ambiguous torn-tail evidence")
            tail = torn[0]
            if (
                tail.line_number != reservation.get("line_number")
                or tail.byte_offset != reservation.get("byte_offset")
                or tail.line_number != len(physical) + 1
            ):
                raise DurabilityUnknown(
                    "torn tail does not match the reserved write position",
                    details={
                        "tail_line": tail.line_number,
                        "tail_offset": tail.byte_offset,
                        "reserved_line": reservation.get("line_number"),
                        "reserved_offset": reservation.get("byte_offset"),
                    },
                )
            custody_root = self.ledger.ledger_dir / ".nbf08-torn-custody"
            custody_root.mkdir(parents=True, exist_ok=True)
            tail_sha = sha256_hex(tail.raw)
            custody_path = custody_root / f"{reservation_id}.{tail_sha}.partial"
            if custody_path.exists():
                if custody_path.is_symlink() or custody_path.read_bytes() != tail.raw:
                    raise DurabilityUnknown("torn-tail custody conflicts with reserved bytes")
            else:
                _durable_file(custody_path, tail.raw)
                custody_path.chmod(0o444)
                _fsync_dir(custody_root)
            journal_path = self.ledger.events_path
            with open(journal_path, "r+b") as handle:
                handle.seek(tail.byte_offset)
                if handle.read() != tail.raw:
                    raise DurabilityUnknown("journal torn tail changed before truncation")
                handle.truncate(tail.byte_offset)
                handle.flush()
                os.fsync(handle.fileno())
            _fsync_dir(journal_path.parent)
            torn = ()
        if matching:
            if len(matching) != 1 or matching[0] is not physical[-1]:
                raise DurabilityUnknown("reserved sequence collides with more than one physical record")
            record = matching[0]
            line_sha = stored_line_sha256(record.raw)
            payload = record.record.get("payload") if isinstance(record.record.get("payload"), dict) else {}
            if str(record.record.get("kind") or "") == "chain_control.sequence_reserved_tombstone":
                payload_id = payload.get("reservation_id")
                if reservation_id and payload_id not in {None, reservation_id}:
                    raise DurabilityUnknown(
                        "reservation tombstone identity collision",
                        details={"reservation_id": reservation_id, "payload_id": payload_id},
                    )
                reservation["status"] = "tombstoned"
                reservation["reservation_digest"] = reservation_digest_for(reservation)
                write_reservation_locked(seq_fd, reservation)
                return reservation
            if not intended or intended == ZERO_DIGEST:
                raise DurabilityUnknown("complete reserved record has no authenticated intended hash")
            if intended != line_sha:
                raise DurabilityUnknown(
                    "reservation intended_record_sha256 does not match complete line",
                    details={"reservation_id": reservation_id, "intended": intended, "actual": line_sha},
                )
            payload_id = payload.get("reservation_id") if isinstance(payload, dict) else None
            if reservation_id and payload_id not in {None, reservation_id}:
                raise DurabilityUnknown(
                    "reservation_id collision at reserved sequence",
                    details={"reservation_id": reservation_id, "payload_id": payload_id},
                )
            if reservation.get("scope") == "chain_control" and (
                record.record.get("kind") != reservation.get("event_kind")
                or record.record.get("idempotency_key") != reservation.get("event_id")
                or payload.get("event_id") != reservation.get("event_id")
                or payload.get("event_kind") != reservation.get("event_kind")
                or payload.get("operation_id") != reservation.get("operation_id")
                or payload.get("chain_id") != reservation.get("chain_id")
                or payload.get("physical_sequence") != reserved_seq
                or payload.get("previous_physical_digest") != reservation.get("previous_physical_digest")
            ):
                raise DurabilityUnknown("complete chain-control record contradicts its reservation lineage")
            reservation["status"] = "committed"
            reservation["intended_record_sha256"] = line_sha
            reservation["reservation_digest"] = reservation_digest_for(reservation)
            write_reservation_locked(seq_fd, reservation)
            validate_reservation_tip(
                reservation,
                ledger_id=self.ledger_id,
                physical=physical,
            )
            return reservation
        tombstone = self._append_tombstone_locked(seq_fd, reservation, previous_physical_digest=previous)
        after = [item for item in read_physical_lines(self.ledger.events_path) if not item.torn]
        if not after or after[-1].record.get("seq") != reserved_seq:
            raise DurabilityUnknown("tombstone append did not become the verified journal tip")
        reservation["status"] = "tombstoned"
        reservation["intended_record_sha256"] = stored_line_sha256(after[-1].raw)
        reservation["previous_physical_digest"] = previous
        reservation["reservation_digest"] = reservation_digest_for(reservation)
        write_reservation_locked(seq_fd, reservation)
        return tombstone

    def _append_tombstone_locked(
        self,
        seq_fd: int,
        reservation: Mapping[str, Any],
        *,
        previous_physical_digest: str,
    ) -> dict[str, Any]:
        scope = reservation.get("scope") or "chainless"
        chain_id = reservation.get("chain_id") if scope == "chain_control" else None
        envelope = build_envelope(
            event_kind="chain_control.sequence_reserved_tombstone",
            operation_id=reservation.get("operation_id") or "none",
            causation_id=reservation.get("causation_id") or "none",
            correlation_id=reservation.get("correlation_id") or "none",
            recovery_id=str(reservation.get("recovery_id") or "none"),
            chain_id=str(chain_id or "chainless"),
            authority_mode="file",
            ledger_id=self.ledger_id,
            physical_sequence=int(reservation["physical_sequence"]),
            evidence_sequence=int(reservation.get("evidence_sequence") or 0),
            semantic_sequence=int(reservation.get("semantic_sequence") or 0),
            previous_physical_digest=previous_physical_digest,
            previous_evidence_digest=ZERO_DIGEST,
            payload={
                "reservation_id": reservation.get("reservation_id"),
                "reservation_status": "tombstoned",
                "reason": "crash_before_append",
                "lineage_class": "physical_reservation" if scope == "chainless" else "chain_control",
                "physical_lineage": {
                    "ledger_id": self.ledger_id,
                    "reservation_id": reservation.get("reservation_id"),
                    "physical_sequence": reservation.get("physical_sequence"),
                    "previous_physical_digest": previous_physical_digest,
                    "recovery_id": reservation.get("recovery_id") or "none",
                },
            },
            event_id=_stable_id("tombstone", str(reservation.get("reservation_id"))),
            semantic_effect="no_change",
            claim_class="evidence-only",
            outcome="tombstoned",
            failure_class="crash_before_append",
            actor={"id": "ledger", "class": "system"},
        )
        if scope == "chainless":
            envelope["chain_id"] = None
            envelope["operation_id"] = None
            envelope["causation_id"] = None
            envelope["correlation_id"] = None
        return self.ledger._journal._emit_locked(
            seq_fd,
            kind="chain_control.sequence_reserved_tombstone",
            payload=envelope,
            idempotency_key=str(reservation.get("reservation_id")),
            init_ts=self.ledger._journal._load_init_ts(),
            nbf08_reservation=dict(reservation),
            allocated_seq=int(reservation["physical_sequence"]),
        )

    def replay_strict(self) -> dict[str, Any]:
        return self._replay_physical_strict(read_physical_lines(self.ledger.events_path))

    def _replay_physical_strict(
        self,
        physical: Sequence[PhysicalRecord],
    ) -> dict[str, Any]:
        """Strict replay over an already captured physical generation."""
        physical = list(physical)
        complete = [item for item in physical if not item.torn]
        torn = [item for item in physical if item.torn]
        if len(torn) > 1:
            raise ChainControlHold("multiple_torn_tails", "strict replay allows one incomplete final line only")
        if torn and torn[0] is not physical[-1]:
            raise ChainControlHold("torn_non_tail", "incomplete JSON is only legal as the final line")
        previous_digest = ZERO_DIGEST
        seen_ids: set[str] = set()
        seen_seq: set[int] = set()
        expected_seq = None
        evidence_by_chain: dict[str, int] = {}
        semantic_by_chain: dict[str, int] = {}
        evidence_digest_by_chain: dict[str, str] = {}
        genesis_by_chain: dict[str, dict[str, Any]] = {}
        nbf01_prefix_tip = -1
        nbf01_prefix_digest = ZERO_DIGEST
        accepted: list[dict[str, Any]] = []
        operations: dict[str, dict[str, Any]] = {}
        holds: list[dict[str, Any]] = []
        for item in complete:
            seq = item.record.get("seq")
            if not isinstance(seq, int) or isinstance(seq, bool):
                raise ChainControlHold("missing_seq", "physical record lacks integer seq")
            if seq in seen_seq:
                raise ChainControlHold("duplicate_seq", f"duplicate physical sequence {seq}")
            if expected_seq is None:
                expected_seq = seq
            elif seq != expected_seq:
                raise ChainControlHold("gap_or_fork", f"physical sequence gap/fork at {seq}, expected {expected_seq}")
            expected_seq = seq + 1
            seen_seq.add(seq)
            kind = str(item.record.get("kind") or "")
            digest = physical_record_digest(
                ledger_id=self.ledger_id,
                physical_sequence=seq,
                record_type=record_type_for(kind),
                stored_record_bytes=item.raw,
                previous_physical_digest=previous_digest,
            )
            payload = item.record.get("payload")
            if kind.startswith("chain_control."):
                if not isinstance(payload, dict):
                    raise ChainControlHold("malformed_envelope", "chain-control payload must be an object")
                chain_id = payload.get("chain_id") or "chainless"
                self._verify_envelope(
                    payload,
                    expected_physical=seq,
                    previous_physical_digest=previous_digest,
                    previous_evidence_digest=evidence_digest_by_chain.get(chain_id, ZERO_DIGEST),
                    previous_evidence_sequence=evidence_by_chain.get(chain_id, 0),
                    previous_semantic_sequence=semantic_by_chain.get(chain_id, 0),
                    genesis=genesis_by_chain.get(chain_id),
                    nbf01_prefix_tip=nbf01_prefix_tip,
                    nbf01_prefix_digest=nbf01_prefix_digest,
                )
                event_id = payload["event_id"]
                if event_id in seen_ids:
                    raise ChainControlHold("duplicate_event", f"duplicate event_id {event_id}")
                seen_ids.add(event_id)
                evidence_by_chain[chain_id] = payload["evidence_sequence"]
                semantic_by_chain[chain_id] = payload["semantic_sequence"]
                evidence_digest_by_chain[chain_id] = payload["event_hash"]
                accepted.append(payload)
                if payload.get("event_kind") in {"chain_control.genesis_accepted", "chain_control.legacy_imported"}:
                    genesis_by_chain[chain_id] = payload
                op_id = payload.get("operation_id")
                if isinstance(op_id, str) and op_id:
                    event_kind = payload.get("event_kind")
                    if event_kind in {
                        "chain_control.committed",
                        "chain_control.runtime_rebound",
                        "chain_control.rejected",
                        "chain_control.cas_conflict",
                        "chain_control.hold",
                        "chain_control.hold_released",
                        "chain_control.hold_reconciled",
                        "chain_control.hold_context_attested",
                        "chain_control.restart_receipt_attested",
                        "chain_control.genesis_accepted",
                        "chain_control.suffix_rebound",
                    } or op_id not in operations:
                        operations[op_id] = payload
                if payload["event_kind"] in {"chain_control.hold", "chain_control.tamper_detected", "chain_control.reconcile_required"}:
                    holds.append(payload)
            else:
                event_id = str((payload or {}).get("event_id") or item.record.get("idempotency_key") or f"seq-{seq}")
                if event_id in seen_ids:
                    raise ChainControlHold("duplicate_event", f"duplicate event_id {event_id}")
                seen_ids.add(event_id)
                nbf01_prefix_tip = seq
                nbf01_prefix_digest = digest
            previous_digest = digest
        return {
            "physical_tip_digest": previous_digest,
            "physical_sequence": highest_complete_seq(complete),
            "accepted": accepted,
            "operations": operations,
            "holds": holds,
            "evidence_by_chain": evidence_by_chain,
            "semantic_by_chain": semantic_by_chain,
            "evidence_digest_by_chain": evidence_digest_by_chain,
            "genesis_by_chain": genesis_by_chain,
            "nbf01_prefix_tip": nbf01_prefix_tip,
            "nbf01_prefix_digest": nbf01_prefix_digest,
            "torn_tail": bool(torn),
        }

    def _verify_envelope(
        self,
        envelope: Mapping[str, Any],
        *,
        expected_physical: int,
        previous_physical_digest: str | None = None,
        previous_evidence_digest: str | None = None,
        previous_evidence_sequence: int | None = None,
        previous_semantic_sequence: int | None = None,
        genesis: Mapping[str, Any] | None = None,
        nbf01_prefix_tip: int | None = None,
        nbf01_prefix_digest: str | None = None,
    ) -> None:
        missing = [key for key in ENVELOPE_FIELDS if key not in envelope]
        if missing:
            raise ChainControlHold("incomplete_envelope", f"missing envelope keys {missing}")
        if envelope.get("physical_sequence") != expected_physical:
            raise ChainControlHold("source_mismatch", "envelope physical_sequence does not match journal seq")
        recomputed = compute_event_hash(
            authority_mode=str(envelope["authority_mode"]),
            ledger_id=str(envelope["ledger_id"]),
            chain_id=str(envelope["chain_id"] or "chainless"),
            physical_sequence=int(envelope["physical_sequence"]),
            evidence_sequence=int(envelope["evidence_sequence"]),
            semantic_sequence=int(envelope["semantic_sequence"]),
            event_id=str(envelope["event_id"]),
            event_kind=str(envelope["event_kind"]),
            operation_id=str(envelope["operation_id"] or "none"),
            causation_id=str(envelope["causation_id"] or "none"),
            correlation_id=str(envelope["correlation_id"] or "none"),
            recovery_id=str(envelope["recovery_id"] or "none"),
            previous_physical_digest=str(envelope["previous_physical_digest"]),
            previous_evidence_digest=str(envelope["previous_evidence_digest"]),
            payload=envelope["payload"],
        )
        if recomputed != envelope.get("event_hash"):
            raise ChainControlTamper("event hash mismatch")
        if envelope.get("ledger_id") != self.ledger_id:
            raise ChainControlHold("source_mismatch", "envelope ledger_id does not match this journal")
        kind = str(envelope.get("event_kind") or "")
        chain_id = envelope.get("chain_id") or "chainless"
        if previous_physical_digest is not None and envelope.get("previous_physical_digest") != previous_physical_digest:
            raise ChainControlHold(
                "predecessor_mismatch",
                "previous_physical_digest does not match running physical_record_digest",
            )
        is_tombstone = kind == "chain_control.sequence_reserved_tombstone"
        if previous_evidence_digest is not None and envelope.get("previous_evidence_digest") != previous_evidence_digest:
            raise ChainControlHold(
                "evidence_predecessor_mismatch",
                "previous_evidence_digest does not match the prior evidence tip",
            )
        if previous_evidence_sequence is not None:
            actual_evidence = int(envelope["evidence_sequence"])
            if is_tombstone:
                if actual_evidence != previous_evidence_sequence:
                    raise ChainControlHold(
                        "evidence_sequence_mismatch",
                        "sequence_reserved_tombstone must leave evidence_sequence unchanged",
                    )
            elif actual_evidence != previous_evidence_sequence + 1:
                raise ChainControlHold(
                    "evidence_sequence_mismatch",
                    "evidence_sequence must advance by exactly one",
                )
        if previous_semantic_sequence is not None:
            actual_semantic = int(envelope["semantic_sequence"])
            effect = str(envelope.get("semantic_effect") or "no_change")
            frozen = semantic_effect_for(
                kind,
                pre_digest=envelope.get("pre_state_digest"),
                post_digest=envelope.get("post_state_digest"),
            )
            if effect != frozen:
                raise ChainControlHold(
                    "semantic_eligibility_mismatch",
                    "semantic_effect is not the frozen eligibility for this event kind",
                )
            if kind in SEMANTIC_KINDS and effect == "advance":
                if actual_semantic != previous_semantic_sequence + 1:
                    raise ChainControlHold("semantic_cursor_mismatch", "semantic_sequence must advance by exactly one")
            elif actual_semantic != previous_semantic_sequence:
                raise ChainControlHold("semantic_cursor_mismatch", "semantic_sequence must remain unchanged")
        if chain_id != "chainless":
            if kind in {"chain_control.genesis_accepted", "chain_control.legacy_imported"}:
                payload = envelope.get("payload") if isinstance(envelope.get("payload"), dict) else {}
                if nbf01_prefix_tip is not None and payload.get("prefix_tip_seq") != nbf01_prefix_tip:
                    raise ChainControlHold(
                        "genesis_prefix_mismatch",
                        "genesis NBF01 accepted-prefix tip does not match the incident prefix",
                    )
                if nbf01_prefix_digest is not None and payload.get("prefix_digest") != nbf01_prefix_digest:
                    raise ChainControlHold(
                        "genesis_prefix_mismatch",
                        "genesis NBF01 accepted-prefix digest does not match the incident prefix",
                    )
            elif genesis is None and kind not in {"chain_control.sequence_reserved_tombstone"}:
                raise ChainControlHold(
                    "semantics_before_genesis",
                    "chain-control semantics require a verified genesis NBF01 accepted prefix",
                )

    def operation_result(self, operation_id: str) -> dict[str, Any] | None:
        replay = self.replay_strict()
        return replay["operations"].get(operation_id)

    def is_bound(self, chain_id: str) -> bool:
        replay = self.replay_strict()
        return any(
            event.get("chain_id") == chain_id and event.get("event_kind") == "chain_control.genesis_accepted"
            for event in replay["accepted"]
        )

    def quarantine_trailing_sequence_collision(
        self,
        *,
        expected_journal_sha256: str,
        expected_sidecar_sha256: str,
        expected_prefix_sequence: int,
        expected_prefix_line_sha256: str,
        expected_prefix_digest: str,
        expected_offending_line_sha256: str,
        expected_operation_id: str,
        expected_event_id: str,
        marker_path: Path,
        expected_marker_sha256: str,
        manifest_path: Path,
        expected_manifest_sha256: str,
        spec_path: Path,
        expected_spec_sha256: str,
        workspace_path: Path,
        expected_workspace_sha256: str,
        custody_dir: Path,
        receipt_path: Path,
        actor: str,
        fault_injector: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        """Quarantine one exact trailing outer/envelope sequence collision.

        This is an offline, content-addressed migration authority, not a
        general journal repair API.  The only accepted damage shape is a
        valid strict prefix ending at ``N`` followed by one complete trailing
        ``chain_control.intent`` whose outer sequence collides at ``N`` while
        its independently valid envelope names ``N + 1``.  The invalid source
        generation remains in immutable custody and the replacement generation
        records the no-effect quarantine at ``N + 1``.
        """
        guarded_hashes = {
            "journal": _required_sha256(expected_journal_sha256, "journal SHA-256"),
            "sidecar": _required_sha256(expected_sidecar_sha256, "sidecar SHA-256"),
            "prefix_line": _required_sha256(expected_prefix_line_sha256, "prefix line SHA-256"),
            "prefix_digest": _required_sha256(expected_prefix_digest, "prefix digest"),
            "offending_line": _required_sha256(expected_offending_line_sha256, "offending line SHA-256"),
            "marker": _required_sha256(expected_marker_sha256, "marker SHA-256"),
            "manifest": _required_sha256(expected_manifest_sha256, "manifest SHA-256"),
            "spec": _required_sha256(expected_spec_sha256, "spec SHA-256"),
            "workspace": _required_sha256(expected_workspace_sha256, "workspace SHA-256"),
        }
        if not isinstance(expected_prefix_sequence, int) or isinstance(expected_prefix_sequence, bool) or expected_prefix_sequence < 0:
            raise ChainControlHold("invalid_migration_guard", "prefix sequence must be a non-negative integer")
        expected_operation_id = _required_sha256(expected_operation_id, "offending operation id")
        expected_event_id = _required_sha256(expected_event_id, "offending event id")
        if not actor:
            raise ChainControlHold("invalid_migration_guard", "actor identity is required")

        marker_path = Path(marker_path).expanduser().resolve(strict=False)
        manifest_path = Path(manifest_path).expanduser().resolve(strict=False)
        spec_path = Path(spec_path).expanduser().resolve(strict=False)
        workspace_path = Path(workspace_path).expanduser().resolve(strict=False)
        custody_dir = Path(custody_dir).expanduser().resolve(strict=False)
        receipt_path = Path(receipt_path).expanduser().resolve(strict=False)
        generation_root = self.ledger.ledger_dir / ".nbf08-generations"
        active_generation_path = self.ledger.ledger_dir / ".active-generation.json"
        workspace_excluded = (self.ledger.ledger_dir, custody_dir, receipt_path)
        guarded_identity = {
            "prefix_sequence": expected_prefix_sequence,
            "operation_id": expected_operation_id,
            "event_id": expected_event_id,
            "marker_path": str(marker_path),
            "manifest_path": str(manifest_path),
            "spec_path": str(spec_path),
            "workspace_path": str(workspace_path),
            "custody_dir": str(custody_dir),
        }
        generation_id = "seq-collision-" + _stable_id(
            guarded_hashes["journal"], guarded_hashes["sidecar"], guarded_hashes["offending_line"]
        )[:24]
        final_custody = custody_dir / generation_id
        final_generation = generation_root / generation_id

        def overlaps(left: Path, right: Path) -> bool:
            return left == right or left in right.parents or right in left.parents

        ledger_dir = self.ledger.ledger_dir.resolve(strict=False)
        if not workspace_path.is_dir() or workspace_path.is_symlink():
            raise ChainControlHold("invalid_migration_guard", "workspace must be a regular directory")
        if workspace_path == ledger_dir or ledger_dir in workspace_path.parents:
            raise ChainControlHold("invalid_migration_guard", "workspace cannot be inside the excluded ledger")
        if workspace_path == custody_dir or custody_dir in workspace_path.parents:
            raise ChainControlHold("invalid_migration_guard", "workspace cannot be inside the excluded custody root")
        if overlaps(ledger_dir, custody_dir):
            raise ChainControlHold("invalid_migration_guard", "ledger and custody roots must be disjoint")
        forbidden_receipts = {
            marker_path,
            manifest_path,
            spec_path,
            active_generation_path,
            ledger_dir / INCIDENT_EVENTS_FILE,
            ledger_dir / ".events.seq",
            final_custody / "manifest.json",
            final_custody / "original-events.jsonl",
            final_custody / "original-sidecar",
            final_custody / "offending-line.jsonl",
            final_generation / "manifest.json",
            final_generation / INCIDENT_EVENTS_FILE,
            final_generation / ".events.seq",
            final_generation / "initial-sidecar",
        }
        if receipt_path in forbidden_receipts or receipt_path == ledger_dir or receipt_path == custody_dir:
            raise ChainControlHold("invalid_migration_guard", "receipt path overlaps guarded or migration state")
        if overlaps(receipt_path, ledger_dir) or overlaps(receipt_path, custody_dir):
            raise ChainControlHold("invalid_migration_guard", "receipt must be outside the ledger and custody roots")
        if receipt_path == workspace_path:
            raise ChainControlHold("invalid_migration_guard", "receipt path cannot be the workspace")

        def inject(point: str) -> None:
            if fault_injector is not None:
                fault_injector(point)

        def read_json_guard(path: Path, expected: str, label: str) -> dict[str, Any]:
            if _path_sha256(path, label) != expected:
                raise ChainControlHold("migration_guard_mismatch", f"{label} bytes changed")
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise ChainControlHold("migration_guard_mismatch", f"{label} is not valid JSON") from exc
            if not isinstance(value, dict):
                raise ChainControlHold("migration_guard_mismatch", f"{label} must contain an object")
            return value

        def verify_custody(path: Path) -> tuple[dict[str, Any], str]:
            manifest_file = path / "manifest.json"
            try:
                body = json.loads(manifest_file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise ChainControlHold("migration_custody_invalid", "custody manifest is unreadable") from exc
            if (
                not isinstance(body, dict)
                or body.get("schema") != TRAILING_COLLISION_MIGRATION_SCHEMA
                or body.get("generation_id") != generation_id
                or body.get("original_journal_sha256") != guarded_hashes["journal"]
                or body.get("original_sidecar_sha256") != guarded_hashes["sidecar"]
                or body.get("offending_line_sha256") != guarded_hashes["offending_line"]
                or body.get("offending_operation_id") != expected_operation_id
                or body.get("offending_event_id") != expected_event_id
            ):
                raise ChainControlHold("migration_custody_invalid", "custody manifest contradicts the guarded collision")
            original_events = path / "original-events.jsonl"
            original_sidecar = path / "original-sidecar"
            offending_line = path / "offending-line.jsonl"
            if (
                _path_sha256(original_events, "custody journal") != guarded_hashes["journal"]
                or _path_sha256(original_sidecar, "custody sidecar") != guarded_hashes["sidecar"]
            ):
                raise ChainControlHold("migration_custody_invalid", "custody source bytes changed")
            offending_bytes = offending_line.read_bytes()
            if not offending_bytes.endswith(b"\n") or sha256_hex(offending_bytes[:-1]) != guarded_hashes["offending_line"]:
                raise ChainControlHold("migration_custody_invalid", "custody offending line changed")
            return body, _path_sha256(manifest_file, "custody manifest")

        def verify_generation(path: Path) -> tuple[dict[str, Any], dict[str, Any], str]:
            manifest_file = path / "manifest.json"
            try:
                body = json.loads(manifest_file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise ChainControlHold("migration_generation_invalid", "generation manifest is unreadable") from exc
            if (
                not isinstance(body, dict)
                or body.get("schema") != TRAILING_COLLISION_MIGRATION_SCHEMA
                or body.get("generation_id") != generation_id
                or body.get("guarded_hashes") != guarded_hashes
                or body.get("guarded_identity") != guarded_identity
            ):
                raise ChainControlHold("migration_generation_invalid", "generation manifest contradicts the guarded collision")
            generation_events = path / INCIDENT_EVENTS_FILE
            generation_sidecar = path / ".events.seq"
            initial_sidecar = path / "initial-sidecar"
            if (
                body.get("parent_events_sha256") != guarded_hashes["journal"]
                or body.get("parent_sidecar_sha256") != guarded_hashes["sidecar"]
                or _path_sha256(initial_sidecar, "initial generation sidecar") != body.get("sidecar_sha256")
            ):
                raise ChainControlHold("migration_generation_invalid", "canonical generation lineage changed")
            physical = read_physical_lines(generation_events)
            replay = self._replay_physical_strict(physical)
            migration_event_id = body.get("migration_event_id")
            migration = next(
                (
                    event
                    for event in replay["accepted"]
                    if event.get("event_id") == migration_event_id
                    and event.get("event_kind") == "chain_control.trailing_sequence_collision_quarantined"
                ),
                None,
            )
            if (
                not isinstance(migration, dict)
                or migration.get("physical_sequence") != expected_prefix_sequence + 1
                or migration.get("payload", {}).get("offending_event_id") != expected_event_id
                or migration.get("payload", {}).get("offending_line_sha256") != guarded_hashes["offending_line"]
                or migration.get("payload", {}).get("disposition") != "quarantined_no_effect"
            ):
                raise ChainControlHold("migration_generation_invalid", "canonical migration event is absent or contradictory")
            through_migration = [
                item for item in physical if not item.torn and item.record.get("seq") <= expected_prefix_sequence + 1
            ]
            initial_bytes = b"\n".join(item.raw for item in through_migration) + b"\n"
            if sha256_hex(initial_bytes) != body.get("events_sha256"):
                raise ChainControlHold("migration_generation_invalid", "canonical migration prefix changed")
            sidecar_raw = generation_sidecar.read_bytes()
            sidecar_kind, sidecar = parse_sidecar_bytes(sidecar_raw)
            if sidecar_kind != "reservation" or not isinstance(sidecar, dict):
                raise ChainControlHold("migration_generation_invalid", "canonical generation sidecar is malformed")
            validate_reservation_tip(sidecar, ledger_id=self.ledger_id, physical=physical)
            return body, replay, _path_sha256(manifest_file, "generation manifest")

        def verify_zero_effect(*, conflict_code: str) -> tuple[dict[str, Any], dict[str, Any], Path]:
            current_marker = read_json_guard(marker_path, guarded_hashes["marker"], "marker")
            current_manifest = read_json_guard(manifest_path, guarded_hashes["manifest"], "manifest")
            launch_outcome = current_marker.get("launch_outcome")
            from arnold_pipelines.megaplan.chain.spec import _state_path_for

            state_path = _state_path_for(spec_path)
            if (
                _path_sha256(spec_path, "spec") != guarded_hashes["spec"]
                or workspace_snapshot_sha256(workspace_path, excluded=workspace_excluded) != guarded_hashes["workspace"]
                or _live_occupancy_path({"marker": current_marker, "manifest": current_manifest}) is not None
                or not isinstance(launch_outcome, Mapping)
                or str(launch_outcome.get("status") or "").lower() != "failed"
                or str(launch_outcome.get("code") or "").lower() not in {"failed", "launch_not_advanced"}
                or state_path.exists()
            ):
                raise ChainControlHold(conflict_code, "zero-effect guard changed")
            return current_marker, current_manifest, state_path

        def active_pointer() -> tuple[dict[str, Any], bytes] | None:
            if not active_generation_path.exists():
                return None
            try:
                raw = active_generation_path.read_bytes()
                body = json.loads(raw)
            except (OSError, json.JSONDecodeError) as exc:
                raise ChainControlHold("migration_existing_state", "active generation pointer is unreadable") from exc
            if not isinstance(body, dict):
                raise ChainControlHold("migration_existing_state", "active generation pointer is malformed")
            return body, raw

        def receipt_for(
            generation_manifest: Mapping[str, Any],
            generation_manifest_sha: str,
            custody_manifest_sha: str,
        ) -> dict[str, Any]:
            return {
                "schema": TRAILING_COLLISION_RECEIPT_SCHEMA,
                "outcome": "committed",
                "external_effect": False,
                "generation_id": generation_id,
                "migration_event_id": generation_manifest["migration_event_id"],
                "migration_operation_id": generation_manifest["migration_operation_id"],
                "guarded_hashes": guarded_hashes,
                "guarded_identity": guarded_identity,
                "old_journal_sha256": guarded_hashes["journal"],
                "old_sidecar_sha256": guarded_hashes["sidecar"],
                "new_journal_sha256": generation_manifest["events_sha256"],
                "new_sidecar_sha256": generation_manifest["sidecar_sha256"],
                "custody_manifest": str(final_custody / "manifest.json"),
                "custody_manifest_sha256": custody_manifest_sha,
                "generation_manifest": str(final_generation / "manifest.json"),
                "generation_manifest_sha256": generation_manifest_sha,
                "created_at": generation_manifest["created_at"],
                "actor": generation_manifest["actor"],
            }

        journal_lock_fd = self.ledger._journal.open_journal_lock()
        seq_fd: int | None = None
        chain_lock_fd: int | None = None
        staged_roots: list[Path] = []
        finalized_roots: list[Path] = []
        old_events: bytes | None = None
        old_sidecar: bytes | None = None
        published_pointer: bytes | None = None
        switched = False
        try:
            fcntl.flock(journal_lock_fd, fcntl.LOCK_EX)
            events_path = self.ledger.events_path
            sidecar_path = self.ledger._journal.sequence_path()
            if (
                not events_path.is_file()
                or events_path.is_symlink()
                or not sidecar_path.is_file()
                or sidecar_path.is_symlink()
            ):
                raise ChainControlHold("migration_guard_mismatch", "journal and regular sidecar must already exist")
            seq_fd = self.ledger._journal.open_sequence_after_lock()
            fcntl.flock(seq_fd, fcntl.LOCK_EX)
            # A prior commit is replayable after later legitimate appends: the
            # immutable generation/custody manifests prove the migration
            # prefix, while strict replay proves the current mutable tip.
            if receipt_path.is_file():
                try:
                    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError) as exc:
                    raise ChainControlHold("migration_receipt_invalid", "migration receipt is unreadable") from exc
                expected_guard = receipt.get("guarded_hashes") if isinstance(receipt, dict) else None
                if (
                    receipt.get("schema") != TRAILING_COLLISION_RECEIPT_SCHEMA
                    or expected_guard != guarded_hashes
                    or receipt.get("guarded_identity") != guarded_identity
                    or receipt.get("generation_id") != generation_id
                ):
                    raise ChainControlHold("migration_receipt_conflict", "migration replay guard differs from receipt")
                pointer = active_pointer()
                if (
                    pointer is None
                    or pointer[0].get("generation_id") != generation_id
                    or pointer[0].get("generation_manifest_sha256") != receipt.get("generation_manifest_sha256")
                ):
                    raise ChainControlHold("migration_receipt_conflict", "active generation differs from migration receipt")
                custody_body, custody_sha = verify_custody(final_custody)
                generation_body, replay, generation_sha = verify_generation(final_generation)
                if (
                    custody_sha != receipt.get("custody_manifest_sha256")
                    or generation_sha != receipt.get("generation_manifest_sha256")
                    or generation_body.get("custody_manifest_sha256") != custody_sha
                    or generation_body.get("migration_event_id") != receipt.get("migration_event_id")
                    or custody_body.get("generation_id") != generation_id
                ):
                    raise ChainControlHold("migration_receipt_conflict", "preserved migration evidence changed")
                verify_zero_effect(conflict_code="migration_receipt_conflict")
                for path in final_custody.rglob("*"):
                    if path.is_file():
                        path.chmod(0o444)
                final_custody.chmod(0o555)
                receipt_path.chmod(0o444)
                return {"outcome": "replay", "external_effect": False, "receipt": receipt, "replay": replay}

            # A process may have died after the one atomic pointer publication
            # and before writing the receipt.  The pointer plus both immutable
            # manifests is sufficient to finish that exact transaction.
            pointer = active_pointer()
            if pointer is not None:
                pointer_body, _pointer_raw = pointer
                if pointer_body.get("generation_id") != generation_id:
                    raise ChainControlHold("migration_existing_state", "another active migration generation exists")
                custody_body, custody_sha = verify_custody(final_custody)
                generation_body, replay, generation_sha = verify_generation(final_generation)
                if (
                    pointer_body.get("generation_manifest_sha256") != generation_sha
                    or generation_body.get("custody_manifest_sha256") != custody_sha
                    or custody_body.get("generation_id") != generation_id
                ):
                    raise ChainControlHold("migration_existing_state", "unreceipted generation evidence conflicts")
                verify_zero_effect(conflict_code="migration_concurrent_change")
                receipt = receipt_for(generation_body, generation_sha, custody_sha)
                _atomic_bytes(receipt_path, canonical_json(receipt) + b"\n")
                for path in final_custody.rglob("*"):
                    if path.is_file():
                        path.chmod(0o444)
                final_custody.chmod(0o555)
                receipt_path.chmod(0o444)
                return {"outcome": "recovered", "external_effect": False, "receipt": receipt, "replay": replay}

            old_events = events_path.read_bytes()
            old_sidecar = read_sidecar_locked(seq_fd)
            if sha256_hex(old_events) != guarded_hashes["journal"] or sha256_hex(old_sidecar) != guarded_hashes["sidecar"]:
                raise ChainControlHold("migration_guard_mismatch", "journal or sidecar bytes changed")
            marker = read_json_guard(marker_path, guarded_hashes["marker"], "marker")
            manifest = read_json_guard(manifest_path, guarded_hashes["manifest"], "manifest")
            if _path_sha256(spec_path, "spec") != guarded_hashes["spec"]:
                raise ChainControlHold("migration_guard_mismatch", "spec bytes changed")
            observed_workspace = workspace_snapshot_sha256(workspace_path, excluded=workspace_excluded)
            if observed_workspace != guarded_hashes["workspace"]:
                raise ChainControlHold("migration_guard_mismatch", "workspace bytes changed")
            occupied = _live_occupancy_path({"marker": marker, "manifest": manifest})
            if occupied is not None:
                raise ChainControlHold("migration_live_authority", f"live owner/tmux/provider/fixer evidence at {occupied}")
            launch_outcome = marker.get("launch_outcome")
            if (
                not isinstance(launch_outcome, Mapping)
                or str(launch_outcome.get("status") or "").lower() != "failed"
                or str(launch_outcome.get("code") or "").lower() not in {"failed", "launch_not_advanced"}
            ):
                raise ChainControlHold(
                    "migration_effect_unknown",
                    "marker does not prove a failed, non-advanced launch",
                )
            from arnold_pipelines.megaplan.chain.spec import _state_path_for

            state_path = _state_path_for(spec_path)
            if state_path.exists():
                raise ChainControlHold("migration_chain_state_present", "chain state exists; no-effect migration refused")

            physical = read_physical_lines(events_path)
            if len(physical) < 2 or any(item.torn for item in physical):
                raise ChainControlHold("migration_shape_mismatch", "migration requires one complete trailing collision")
            try:
                self._replay_physical_strict(physical)
            except ChainControlHold as full_failure:
                if full_failure.code != "duplicate_seq":
                    raise ChainControlHold(
                        "migration_shape_mismatch",
                        "full replay did not fail on the exact trailing sequence collision",
                        details={"failure": full_failure.code},
                    ) from full_failure
            else:
                raise ChainControlHold("migration_shape_mismatch", "full replay succeeds; migration is not authorized")
            prefix = physical[:-1]
            offending = physical[-1]
            try:
                prefix_replay = self._replay_physical_strict(prefix)
            except ChainControlHold as prefix_failure:
                raise ChainControlHold(
                    "migration_shape_mismatch",
                    "strict prefix replay failed; collision is multiple or interior",
                    details={"failure": prefix_failure.code},
                ) from prefix_failure
            if prefix_replay["physical_sequence"] != expected_prefix_sequence:
                raise ChainControlHold("migration_guard_mismatch", "prefix sequence differs from the guarded tip")
            if stored_line_sha256(prefix[-1].raw) != guarded_hashes["prefix_line"]:
                raise ChainControlHold("migration_guard_mismatch", "prefix tip line hash differs")
            if prefix_replay["physical_tip_digest"] != guarded_hashes["prefix_digest"]:
                raise ChainControlHold("migration_guard_mismatch", "prefix physical digest differs")
            if stored_line_sha256(offending.raw) != guarded_hashes["offending_line"]:
                raise ChainControlHold("migration_guard_mismatch", "offending line hash differs")
            outer_sequence = offending.record.get("seq")
            envelope = offending.record.get("payload")
            if (
                outer_sequence != expected_prefix_sequence
                or not isinstance(envelope, dict)
                or envelope.get("physical_sequence") != expected_prefix_sequence + 1
                or envelope.get("event_kind") != "chain_control.intent"
                or offending.record.get("kind") != envelope.get("event_kind")
                or offending.record.get("idempotency_key") != envelope.get("event_id")
                or envelope.get("operation_id") != expected_operation_id
                or envelope.get("event_id") != expected_event_id
                or envelope.get("semantic_effect") != "no_change"
                or envelope.get("claim_class") != "required"
            ):
                raise ChainControlHold("migration_shape_mismatch", "trailing record is not the exact no-effect outer/envelope collision")
            chain_id = str(envelope.get("chain_id") or "")
            if not chain_id or chain_id == "chainless":
                raise ChainControlHold("migration_shape_mismatch", "offending intent has no chain identity")
            self._verify_envelope(
                envelope,
                expected_physical=expected_prefix_sequence + 1,
                previous_physical_digest=prefix_replay["physical_tip_digest"],
                previous_evidence_digest=prefix_replay["evidence_digest_by_chain"].get(chain_id, ZERO_DIGEST),
                previous_evidence_sequence=prefix_replay["evidence_by_chain"].get(chain_id, 0),
                previous_semantic_sequence=prefix_replay["semantic_by_chain"].get(chain_id, 0),
                genesis=prefix_replay["genesis_by_chain"].get(chain_id),
                nbf01_prefix_tip=prefix_replay["nbf01_prefix_tip"],
                nbf01_prefix_digest=prefix_replay["nbf01_prefix_digest"],
            )
            sidecar_kind, sidecar = parse_sidecar_bytes(old_sidecar)
            if sidecar_kind != "reservation" or not isinstance(sidecar, dict):
                raise ChainControlHold("migration_shape_mismatch", "collision migration requires the exact structured stale reservation")
            validate_reservation_integrity(sidecar, ledger_id=self.ledger_id)
            if sidecar.get("status") != "reserved" or sidecar.get("physical_sequence") != expected_prefix_sequence:
                raise ChainControlHold("migration_shape_mismatch", "stale reservation does not name the collided sequence")

            chain_lock = self.scope_lock_path(chain_id)
            chain_lock.parent.mkdir(parents=True, exist_ok=True)
            chain_lock_fd = os.open(str(chain_lock), os.O_RDWR | os.O_CREAT, 0o644)
            fcntl.flock(chain_lock_fd, fcntl.LOCK_EX)
            # Re-check all independently mutable evidence after taking the
            # complete authority lock stack.
            if events_path.read_bytes() != old_events or read_sidecar_locked(seq_fd) != old_sidecar:
                raise ChainControlHold("migration_concurrent_change", "journal changed while acquiring migration locks")
            if (
                _path_sha256(marker_path, "marker") != guarded_hashes["marker"]
                or _path_sha256(manifest_path, "manifest") != guarded_hashes["manifest"]
                or _path_sha256(spec_path, "spec") != guarded_hashes["spec"]
                or workspace_snapshot_sha256(workspace_path, excluded=workspace_excluded) != guarded_hashes["workspace"]
                or state_path.exists()
            ):
                raise ChainControlHold("migration_concurrent_change", "guard evidence changed while acquiring migration locks")

            generation_id = "seq-collision-" + _stable_id(
                guarded_hashes["journal"], guarded_hashes["sidecar"], guarded_hashes["offending_line"]
            )[:24]
            final_custody = custody_dir / generation_id
            final_generation = generation_root / generation_id
            if final_custody.exists() != final_generation.exists():
                # A kill between the two directory renames leaves one exact,
                # unreferenced half. Verify it before removal, then rebuild
                # both halves from the still-guarded legacy source.
                partial = final_custody if final_custody.exists() else final_generation
                if partial == final_custody:
                    verify_custody(partial)
                else:
                    verify_generation(partial)
                partial.chmod(0o755)
                for path in partial.rglob("*"):
                    if path.is_file():
                        path.chmod(0o644)
                shutil.rmtree(partial)
                _fsync_dir(partial.parent)
            if final_custody.exists() and final_generation.exists():
                if not final_custody.is_dir() or not final_generation.is_dir():
                    raise ChainControlHold("migration_existing_state", "invalid unreceipted migration state exists")
                custody_body, custody_sha = verify_custody(final_custody)
                generation_body, replay, generation_sha = verify_generation(final_generation)
                if (
                    custody_body.get("generation_id") != generation_id
                    or generation_body.get("custody_manifest_sha256") != custody_sha
                ):
                    raise ChainControlHold("migration_existing_state", "unreceipted migration state conflicts")
                for path in final_custody.rglob("*"):
                    if path.is_file():
                        path.chmod(0o444)
                final_custody.chmod(0o555)
                (final_generation / "manifest.json").chmod(0o444)
                (final_generation / "initial-sidecar").chmod(0o444)
                active_generation = {
                    "schema": TRAILING_COLLISION_MIGRATION_SCHEMA,
                    "generation_id": generation_id,
                    "generation_manifest": str(final_generation / "manifest.json"),
                    "generation_manifest_sha256": generation_sha,
                }
                published_pointer = canonical_json(active_generation) + b"\n"
                _atomic_bytes(active_generation_path, published_pointer)
                switched = True
                inject("after_events_switch")
                inject("after_sidecar_switch")
                verify_zero_effect(conflict_code="migration_concurrent_change")
                receipt = receipt_for(generation_body, generation_sha, custody_sha)
                _atomic_bytes(receipt_path, canonical_json(receipt) + b"\n")
                inject("after_receipt")
                receipt_path.chmod(0o444)
                return {"outcome": "recovered", "external_effect": False, "receipt": receipt, "replay": replay}
            if active_generation_path.exists():
                raise ChainControlHold("migration_existing_state", "unreceipted migration pointer appeared")
            custody_dir.mkdir(parents=True, exist_ok=True)
            generation_root.mkdir(parents=True, exist_ok=True)
            custody_stage = Path(tempfile.mkdtemp(prefix=generation_id + ".", dir=str(custody_dir)))
            generation_stage = Path(tempfile.mkdtemp(prefix=generation_id + ".", dir=str(generation_root)))
            staged_roots.extend([custody_stage, generation_stage])
            (custody_stage / "original-events.jsonl").write_bytes(old_events)
            (custody_stage / "original-sidecar").write_bytes(old_sidecar)
            (custody_stage / "offending-line.jsonl").write_bytes(offending.raw + b"\n")
            custody_manifest = {
                "schema": TRAILING_COLLISION_MIGRATION_SCHEMA,
                "generation_id": generation_id,
                "ledger_id": self.ledger_id,
                "original_journal_sha256": guarded_hashes["journal"],
                "original_sidecar_sha256": guarded_hashes["sidecar"],
                "prefix_sequence": expected_prefix_sequence,
                "prefix_line_sha256": guarded_hashes["prefix_line"],
                "prefix_digest": guarded_hashes["prefix_digest"],
                "offending_line_sha256": guarded_hashes["offending_line"],
                "offending_operation_id": expected_operation_id,
                "offending_event_id": expected_event_id,
                "disposition": "quarantined_no_effect",
            }
            (custody_stage / "manifest.json").write_bytes(canonical_json(custody_manifest) + b"\n")
            custody_manifest_sha = sha256_hex((custody_stage / "manifest.json").read_bytes())

            migration_operation_id = _stable_id("quarantine-trailing-sequence-collision", generation_id)
            migration_envelope = build_envelope(
                event_kind="chain_control.trailing_sequence_collision_quarantined",
                operation_id=migration_operation_id,
                causation_id=expected_event_id,
                correlation_id=expected_operation_id,
                recovery_id=migration_operation_id,
                chain_id=chain_id,
                authority_mode="file",
                ledger_id=self.ledger_id,
                physical_sequence=expected_prefix_sequence + 1,
                evidence_sequence=prefix_replay["evidence_by_chain"].get(chain_id, 0) + 1,
                semantic_sequence=prefix_replay["semantic_by_chain"].get(chain_id, 0),
                previous_physical_digest=prefix_replay["physical_tip_digest"],
                previous_evidence_digest=prefix_replay["evidence_digest_by_chain"].get(chain_id, ZERO_DIGEST),
                payload={
                    "schema": TRAILING_COLLISION_MIGRATION_SCHEMA,
                    "generation_id": generation_id,
                    "disposition": "quarantined_no_effect",
                    "offending_operation_id": expected_operation_id,
                    "offending_event_id": expected_event_id,
                    "offending_line_sha256": guarded_hashes["offending_line"],
                    "original_journal_sha256": guarded_hashes["journal"],
                    "original_sidecar_sha256": guarded_hashes["sidecar"],
                    "prefix_sequence": expected_prefix_sequence,
                    "prefix_line_sha256": guarded_hashes["prefix_line"],
                    "prefix_digest": guarded_hashes["prefix_digest"],
                    "custody_manifest": str(final_custody / "manifest.json"),
                    "custody_manifest_sha256": custody_manifest_sha,
                    "zero_effect_guards": {
                        "marker_sha256": guarded_hashes["marker"],
                        "manifest_sha256": guarded_hashes["manifest"],
                        "spec_sha256": guarded_hashes["spec"],
                        "workspace_sha256": guarded_hashes["workspace"],
                        "chain_state": "absent",
                        "live_authority": "absent",
                    },
                },
                semantic_effect="no_change",
                claim_class="evidence-only",
                actor={"id": actor, "class": "operator"},
                intent="quarantine-trailing-sequence-collision",
                outcome="quarantined_no_effect",
                failure_class="outer_envelope_sequence_collision",
                linked_receipts=[str(final_custody / "manifest.json")],
                spec_identity=str(spec_path),
                source_identity={"journal_sha256": guarded_hashes["journal"]},
            )
            ts_utc = datetime.now(timezone.utc)
            migration_record = {
                "seq": expected_prefix_sequence + 1,
                "schema_version": 1,
                "ts_utc": ts_utc.isoformat(),
                "ts_rel_init_s": None,
                "kind": migration_envelope["event_kind"],
                "payload": migration_envelope,
                "idempotency_key": migration_envelope["event_id"],
            }
            migration_line = canonical_json(migration_record)
            canonical_events = b"\n".join(item.raw for item in prefix) + b"\n" + migration_line + b"\n"
            committed_sidecar = empty_reservation(
                ledger_id=self.ledger_id,
                physical_sequence=expected_prefix_sequence + 1,
                status="committed",
                previous_physical_digest=prefix_replay["physical_tip_digest"],
            )
            committed_sidecar.update(
                {
                    "scope": "chain_control",
                    "chain_id": chain_id,
                    "event_id": migration_envelope["event_id"],
                    "event_kind": migration_envelope["event_kind"],
                    "operation_id": migration_operation_id,
                    "causation_id": expected_event_id,
                    "correlation_id": expected_operation_id,
                    "recovery_id": migration_operation_id,
                    "evidence_sequence": migration_envelope["evidence_sequence"],
                    "semantic_sequence": migration_envelope["semantic_sequence"],
                    "record_type": "chain_control",
                    "intended_record_sha256": sha256_hex(migration_line),
                }
            )
            committed_sidecar["reservation_digest"] = reservation_digest_for(committed_sidecar)
            canonical_sidecar = canonical_json(committed_sidecar)
            new_journal_sha = sha256_hex(canonical_events)
            new_sidecar_sha = sha256_hex(canonical_sidecar)
            generation_manifest = {
                "schema": TRAILING_COLLISION_MIGRATION_SCHEMA,
                "generation_id": generation_id,
                "ledger_id": self.ledger_id,
                "guarded_hashes": guarded_hashes,
                "guarded_identity": guarded_identity,
                "events_sha256": new_journal_sha,
                "sidecar_sha256": new_sidecar_sha,
                "parent_events_sha256": guarded_hashes["journal"],
                "parent_sidecar_sha256": guarded_hashes["sidecar"],
                "custody_manifest": str(final_custody / "manifest.json"),
                "custody_manifest_sha256": custody_manifest_sha,
                "migration_event_id": migration_envelope["event_id"],
                "migration_operation_id": migration_operation_id,
                "tip_sequence": expected_prefix_sequence + 1,
                "tip_event_id": migration_envelope["event_id"],
                "created_at": ts_utc.isoformat(),
                "actor": actor,
            }
            _durable_file(generation_stage / INCIDENT_EVENTS_FILE, canonical_events)
            _durable_file(generation_stage / ".events.seq", canonical_sidecar)
            _durable_file(generation_stage / "initial-sidecar", canonical_sidecar)
            _durable_file(generation_stage / "manifest.json", canonical_json(generation_manifest) + b"\n")
            _fsync_dir(generation_stage)
            for path in custody_stage.iterdir():
                with open(path, "rb") as handle:
                    os.fsync(handle.fileno())
            _fsync_dir(custody_stage)
            inject("after_stage")
            if events_path.read_bytes() != old_events or read_sidecar_locked(seq_fd) != old_sidecar:
                raise ChainControlHold("migration_concurrent_change", "journal changed before generation switch")
            os.replace(custody_stage, final_custody)
            _fsync_dir(custody_dir)
            staged_roots.remove(custody_stage)
            finalized_roots.append(final_custody)
            inject("after_custody_ready")
            os.replace(generation_stage, final_generation)
            _fsync_dir(generation_root)
            staged_roots.remove(generation_stage)
            finalized_roots.append(final_generation)
            inject("after_generation_ready")
            for path in final_custody.rglob("*"):
                if path.is_file():
                    path.chmod(0o444)
            final_custody.chmod(0o555)
            (final_generation / "manifest.json").chmod(0o444)
            (final_generation / "initial-sidecar").chmod(0o444)
            generation_manifest_sha = _path_sha256(final_generation / "manifest.json", "generation manifest")
            active_generation = {
                "schema": TRAILING_COLLISION_MIGRATION_SCHEMA,
                "generation_id": generation_id,
                "generation_manifest": str(final_generation / "manifest.json"),
                "generation_manifest_sha256": generation_manifest_sha,
            }
            published_pointer = canonical_json(active_generation) + b"\n"
            _atomic_bytes(active_generation_path, published_pointer)
            switched = True
            inject("after_events_switch")
            inject("after_sidecar_switch")
            generation_body, replay, verified_generation_sha = verify_generation(final_generation)
            _custody_body, verified_custody_sha = verify_custody(final_custody)
            if verified_generation_sha != generation_manifest_sha or generation_body.get("custody_manifest_sha256") != verified_custody_sha:
                raise ChainControlHold("migration_verification_failed", "published generation evidence is inconsistent")
            if replay["physical_sequence"] != expected_prefix_sequence + 1:
                raise ChainControlHold("migration_verification_failed", "canonical generation has the wrong tip")
            if (
                _path_sha256(marker_path, "marker") != guarded_hashes["marker"]
                or _path_sha256(manifest_path, "manifest") != guarded_hashes["manifest"]
                or _path_sha256(spec_path, "spec") != guarded_hashes["spec"]
                or workspace_snapshot_sha256(workspace_path, excluded=workspace_excluded) != guarded_hashes["workspace"]
                or state_path.exists()
            ):
                raise ChainControlHold("migration_concurrent_change", "zero-effect guard changed before receipt")
            receipt = receipt_for(generation_body, verified_generation_sha, verified_custody_sha)
            _atomic_bytes(receipt_path, canonical_json(receipt) + b"\n")
            inject("after_receipt")
            receipt_path.chmod(0o444)
            return {"outcome": "committed", "external_effect": False, "receipt": receipt, "replay": replay}
        except BaseException as original_error:
            concurrent_after_publish = False
            if switched and published_pointer is not None:
                try:
                    pointer_unchanged = active_generation_path.read_bytes() == published_pointer
                    generation_unchanged = (
                        (final_generation / INCIDENT_EVENTS_FILE).read_bytes() == canonical_events
                        and (final_generation / ".events.seq").read_bytes() == canonical_sidecar
                    )
                except OSError:
                    pointer_unchanged = generation_unchanged = False
                if pointer_unchanged and generation_unchanged:
                    try:
                        receipt_path.chmod(0o600)
                    except OSError:
                        pass
                    try:
                        receipt_path.unlink()
                        _fsync_dir(receipt_path.parent)
                    except FileNotFoundError:
                        pass
                    active_generation_path.unlink()
                    _fsync_dir(active_generation_path.parent)
                else:
                    concurrent_after_publish = True
            if not concurrent_after_publish:
                for root in reversed(staged_roots + finalized_roots):
                    if root == final_custody and root.exists():
                        root.chmod(0o755)
                        for path in root.rglob("*"):
                            if path.is_file():
                                path.chmod(0o644)
                    shutil.rmtree(root, ignore_errors=True)
            if concurrent_after_publish:
                raise DurabilityUnknown(
                    "migration generation changed after atomic publication",
                    details={"generation_id": generation_id},
                ) from original_error
            raise
        finally:
            if chain_lock_fd is not None:
                try:
                    fcntl.flock(chain_lock_fd, fcntl.LOCK_UN)
                finally:
                    os.close(chain_lock_fd)
            if seq_fd is not None:
                try:
                    fcntl.flock(seq_fd, fcntl.LOCK_UN)
                finally:
                    os.close(seq_fd)
            try:
                fcntl.flock(journal_lock_fd, fcntl.LOCK_UN)
            finally:
                os.close(journal_lock_fd)

    def append_under_lock(
        self,
        txn: LockedChainControlTransaction,
        *,
        event_kind: str,
        chain_id: str,
        operation_id: str,
        causation_id: str,
        correlation_id: str,
        recovery_id: str = "none",
        payload: dict[str, Any],
        semantic_effect: str,
        claim_class: str,
        **fields: Any,
    ) -> dict[str, Any]:
        replay = self.replay_strict()
        physical_seq = replay["physical_sequence"] + 1 if replay["physical_sequence"] >= 0 else 0
        evidence_seq = replay["evidence_by_chain"].get(chain_id, 0) + 1
        semantic_seq = replay["semantic_by_chain"].get(chain_id, 0)
        if event_kind in SEMANTIC_KINDS and semantic_effect == "advance":
            semantic_seq += 1
        previous_physical = replay["physical_tip_digest"] if replay["physical_sequence"] >= 0 else ZERO_DIGEST
        previous_evidence = replay["evidence_digest_by_chain"].get(chain_id, ZERO_DIGEST)
        envelope = build_envelope(
            event_kind=event_kind,
            operation_id=operation_id,
            causation_id=causation_id,
            correlation_id=correlation_id,
            recovery_id=recovery_id,
            chain_id=chain_id,
            authority_mode="file",
            ledger_id=self.ledger_id,
            physical_sequence=physical_seq,
            evidence_sequence=evidence_seq,
            semantic_sequence=semantic_seq,
            previous_physical_digest=previous_physical,
            previous_evidence_digest=previous_evidence,
            payload=payload,
            semantic_effect=semantic_effect,
            claim_class=claim_class,
            **fields,
        )
        return txn.append(envelope)

    def mutate(
        self,
        *,
        chain_id: str,
        operation_id: str,
        intent_kind: str,
        actor: Any,
        expected_revision: Any = None,
        expected_cursor: Any = None,
        state_paths: Sequence[Path] = (),
        parent_chain_id: str | None = None,
        effect: Callable[[LockedChainControlTransaction], dict[str, Any]] | None = None,
        claim_class: str = "required",
        linked_receipts: list[Any] | None = None,
        spec_identity: Any = None,
        source_identity: Any = None,
        committed_event_kind: str = "chain_control.committed",
        intent_context: Mapping[str, Any] | None = None,
        on_commit_failure: Callable[[LockedChainControlTransaction, BaseException], Mapping[str, Any] | None] | None = None,
    ) -> dict[str, Any]:
        authority_mode = "file"
        key = replay_tuple_for(
            authority_mode=authority_mode,
            chain_id=chain_id,
            operation_id=operation_id,
            intent_kind=intent_kind,
            expected_revision=expected_revision,
        )
        replay = self.replay_strict()
        existing = replay["operations"].get(operation_id)
        if existing is not None and envelope_replay_tuple(existing) != key:
            raise ChainControlHold(
                "replay_key_mismatch",
                "mutate replay key must match the frozen tuple "
                "authority_mode, chain_id, operation_id, intent_kind, expected_revision",
                details={"expected": list(key), "actual": list(envelope_replay_tuple(existing))},
            )
        if existing is not None:
            existing_kind = str(existing.get("event_kind") or "")
            if existing_kind not in REPLAYABLE_OPERATION_KINDS:
                raise DurabilityUnknown(
                    "operation has no durable terminal result; reconcile before retry",
                    details={"operation_id": operation_id, "event_kind": existing_kind},
                )
        incomplete = _incomplete_operation_statuses(replay, chain_id)
        if incomplete:
            raise DurabilityUnknown(
                "chain has an incomplete operation; reconcile before starting another operation",
                details={"operations": incomplete},
            )
        if existing is not None:
            replay_event = None
            chain_ids = [chain_id] + ([parent_chain_id] if parent_chain_id else [])
            with self.transaction(
                chain_ids=chain_ids,
                state_paths=state_paths,
                expected_revision=expected_revision,
                operation_id=operation_id,
                actor=actor,
            ) as txn:
                replay_event = self.append_under_lock(
                    txn,
                    event_kind="chain_control.replay",
                    chain_id=chain_id,
                    operation_id=operation_id,
                    causation_id=str(existing.get("event_id") or operation_id),
                    correlation_id=str(existing.get("correlation_id") or operation_id),
                    payload={
                        "original_event_id": existing.get("event_id"),
                        "original_outcome": existing.get("outcome"),
                        "intent_kind": intent_kind,
                    },
                    semantic_effect="no_change",
                    claim_class="evidence-only",
                    actor=actor,
                    outcome="replay",
                    intent=intent_kind,
                    expected_revision=expected_revision,
                    expected_cursor=expected_cursor,
                    linked_receipts=linked_receipts or existing.get("linked_receipts") or [],
                    spec_identity=spec_identity,
                    source_identity=source_identity,
                    parent_chain_id=parent_chain_id,
                )
            return {
                "outcome": "replay",
                "result": existing,
                "replay_event": replay_event,
                "external_effect": False,
            }
        chain_ids = [chain_id] + ([parent_chain_id] if parent_chain_id else [])
        with self.transaction(
            chain_ids=chain_ids,
            state_paths=state_paths,
            expected_revision=expected_revision,
            operation_id=operation_id,
            actor=actor,
        ) as txn:
            context = dict(intent_context or {})
            intent = self.append_under_lock(
                txn,
                event_kind="chain_control.intent",
                chain_id=chain_id,
                operation_id=operation_id,
                causation_id=operation_id,
                correlation_id=operation_id,
                payload={"intent_kind": intent_kind, "expected_revision": expected_revision, **context},
                semantic_effect="no_change",
                claim_class=claim_class,
                actor=actor,
                intent=intent_kind,
                expected_revision=expected_revision,
                expected_cursor=expected_cursor,
                spec_identity=spec_identity,
                source_identity=source_identity,
                parent_chain_id=parent_chain_id,
            )
            validated = self.append_under_lock(
                txn,
                event_kind="chain_control.authority_validated",
                chain_id=chain_id,
                operation_id=operation_id,
                causation_id=intent["payload"]["event_id"],
                correlation_id=operation_id,
                payload={"intent_kind": intent_kind, **context},
                semantic_effect="no_change",
                claim_class=claim_class,
                actor=actor,
                intent=intent_kind,
                expected_cursor=expected_cursor,
                parent_chain_id=parent_chain_id,
            )
            claimed = self.append_under_lock(
                txn,
                event_kind="chain_control.claimed",
                chain_id=chain_id,
                operation_id=operation_id,
                causation_id=validated["payload"]["event_id"],
                correlation_id=operation_id,
                payload={"intent_kind": intent_kind, "claim": "single-use", **context},
                semantic_effect="no_change",
                claim_class=claim_class,
                actor=actor,
                intent=intent_kind,
                expected_cursor=expected_cursor,
                parent_chain_id=parent_chain_id,
            )
            try:
                effect_result = effect(txn) if effect is not None else {"changed": True}
            except ChainControlCasConflict as exc:
                conflict = self.append_under_lock(
                    txn,
                    event_kind="chain_control.cas_conflict",
                    chain_id=chain_id,
                    operation_id=operation_id,
                    causation_id=claimed["payload"]["event_id"],
                    correlation_id=operation_id,
                    payload={"reason": str(exc), "details": exc.details},
                    semantic_effect="no_change",
                    claim_class="evidence-only",
                    actor=actor,
                    outcome="cas_conflict",
                    failure_class="cas_conflict",
                    expected_revision=expected_revision,
                    expected_cursor=expected_cursor,
                    parent_chain_id=parent_chain_id,
                )
                return {"outcome": "cas_conflict", "result": conflict, "error": exc}
            except ChainControlHold as exc:
                tamper = isinstance(exc, ChainControlTamper)
                hold = self.append_under_lock(
                    txn,
                    event_kind="chain_control.tamper_detected" if tamper else "chain_control.hold",
                    chain_id=chain_id,
                    operation_id=operation_id,
                    causation_id=claimed["payload"]["event_id"],
                    correlation_id=operation_id,
                    payload={"reason": str(exc), "code": exc.code, "details": exc.details, **context},
                    semantic_effect="no_change",
                    claim_class="held" if isinstance(exc, DurabilityUnknown) else "evidence-only",
                    actor=actor,
                    outcome="tamper" if tamper else "hold",
                    failure_class=exc.code,
                    expected_cursor=expected_cursor,
                    parent_chain_id=parent_chain_id,
                )
                return {"outcome": "tamper" if tamper else "hold", "result": hold, "error": exc}
            pre_digest = effect_result.get("pre_state_digest")
            post_digest = effect_result.get("post_state_digest")
            try:
                committed = self.append_under_lock(
                    txn,
                    event_kind=committed_event_kind,
                    chain_id=chain_id,
                    operation_id=operation_id,
                    causation_id=claimed["payload"]["event_id"],
                    correlation_id=operation_id,
                    payload={"intent_kind": intent_kind, "effect": {key: value for key, value in effect_result.items() if key != "state"}},
                    semantic_effect=semantic_effect_for(committed_event_kind, pre_digest=pre_digest, post_digest=post_digest),
                    claim_class=claim_class,
                    actor=actor,
                    outcome="committed",
                    intent=intent_kind,
                    expected_revision=expected_revision,
                    expected_cursor=expected_cursor,
                    actual_cursor=effect_result.get("actual_cursor", expected_cursor),
                    actual_revision=effect_result.get("actual_revision"),
                    pre_state_digest=pre_digest,
                    post_state_digest=post_digest,
                    linked_receipts=linked_receipts or effect_result.get("linked_receipts") or [],
                    runtime_identity=effect_result.get("runtime_identity"),
                    spec_identity=spec_identity,
                    source_identity=source_identity,
                    parent_chain_id=parent_chain_id,
                )
            except BaseException as exc:
                # The effect may have crossed an external write boundary before
                # the final journal append.  Give the operation one locked
                # finalizer so it can restore authority and leave a durable
                # hold instead of an unaccounted-for claimed operation.
                rollback_result: Mapping[str, Any] | None = None
                if on_commit_failure is not None:
                    try:
                        rollback_result = on_commit_failure(txn, exc)
                    except BaseException as rollback_exc:
                        raise DurabilityUnknown(
                            "committed-event failure could not be rolled back",
                            details={"error_type": type(rollback_exc).__name__},
                        ) from rollback_exc
                # A low-level fsync failure can leave a reserved sequence
                # whose line is either complete or absent.  Reconcile that
                # reservation while the sequence lock is still held before
                # appending the deterministic recovery hold.
                try:
                    if txn._seq_fd is not None:
                        txn.journal.recover_reservations_locked(txn._seq_fd)
                except BaseException as reservation_exc:
                    raise DurabilityUnknown(
                        "committed-event failure left sequence recovery unknown",
                        details={"error_type": type(reservation_exc).__name__},
                    ) from reservation_exc
                try:
                    hold = self.append_under_lock(
                        txn,
                        event_kind="chain_control.hold",
                        chain_id=chain_id,
                        operation_id=operation_id,
                        causation_id=claimed["payload"]["event_id"],
                        correlation_id=operation_id,
                        payload={
                            "intent_kind": intent_kind,
                            "reason": "committed event append failed",
                            "error_type": type(exc).__name__,
                            "rollback": dict(rollback_result or {}),
                        },
                        semantic_effect="no_change",
                        claim_class="evidence-only",
                        actor=actor,
                        outcome="hold",
                        failure_class="committed_event_append_failed",
                        expected_revision=expected_revision,
                        expected_cursor=expected_cursor,
                        parent_chain_id=parent_chain_id,
                    )
                except BaseException as hold_exc:
                    raise DurabilityUnknown(
                        "committed-event failure left journal recovery unknown",
                        details={"error_type": type(hold_exc).__name__},
                    ) from hold_exc
                return {"outcome": "hold", "result": hold, "error": exc}
            txn.result = committed
            return {
                "outcome": "committed",
                "result": committed.get("payload", committed),
                "event": committed.get("payload", committed),
                "effect": effect_result,
            }

    def release_hold(
        self,
        *,
        chain_id: str,
        operation_id: str,
        expected_hold_event_hash: str,
        expected_chain_spec_sha256: str,
        spec_path: Path,
        expected_state_digest: str,
        expected_cursor: int,
        expected_current_milestone: str,
        expected_current_plan: str,
        recovery_evidence: Path,
        actor: str,
        reason: str,
        expected_state_revision: int | None | object = _UNSET_STATE_REVISION,
        expect_missing_state_revision: bool = False,
    ) -> dict[str, Any]:
        """Release one exact durable hold without changing chain state.

        The hold remains immutable evidence.  The release sequence uses the
        held operation id with a distinct recovery id, making the held
        operation terminal for replay while retaining its original lineage.
        """
        from arnold_pipelines.megaplan._core.io import find_plan_dir
        from arnold_pipelines.megaplan.chain.spec import _state_path_for, load_spec
        from arnold_pipelines.megaplan.chain.target_rebind import _assert_pause

        if chain_id != chain_id_for_spec(spec_path):
            raise ChainControlHold("chain_mismatch", "release-hold chain id does not match the spec")
        if not re.fullmatch(r"[0-9a-f]{64}", expected_hold_event_hash):
            raise ChainControlHold("invalid_hold_hash", "held event hash must be a SHA-256")
        if not re.fullmatch(r"[0-9a-f]{64}", expected_chain_spec_sha256):
            raise ChainControlHold("invalid_spec_hash", "chain spec hash must be a SHA-256")
        if not re.fullmatch(r"[0-9a-f]{64}", expected_state_digest):
            raise ChainControlHold("invalid_state_digest", "state digest must be a SHA-256")
        if not actor.strip() or not reason.strip() or not expected_current_plan.strip():
            raise ChainControlHold("missing_release_guard", "actor, reason, and current plan are required")
        if expect_missing_state_revision:
            if expected_state_revision not in (_UNSET_STATE_REVISION, None):
                raise ChainControlHold(
                    "revision_expectation_conflict",
                    "missing-revision mode cannot be combined with an expected state revision",
                )
            state_revision_expectation = "absent"
            expected_revision_value = None
        else:
            if expected_state_revision is _UNSET_STATE_REVISION:
                raise ChainControlHold(
                    "missing_revision_expectation",
                    "release-hold requires an expected state revision or explicit missing-revision mode",
                )
            if expected_state_revision is None:
                # Preserve the legacy API's explicit ``None`` representation
                # of an unversioned state; omission remains an error.
                state_revision_expectation = "absent"
                expected_revision_value = None
            elif not isinstance(expected_state_revision, int) or isinstance(expected_state_revision, bool):
                raise ChainControlHold(
                    "invalid_state_revision",
                    "expected state revision must be an integer",
                )
            else:
                state_revision_expectation = "value"
                expected_revision_value = expected_state_revision
        if not recovery_evidence.is_file():
            raise ChainControlHold("missing_recovery_evidence", "recovery evidence is unavailable")
        evidence_sha = hashlib.sha256(recovery_evidence.read_bytes()).hexdigest()
        state_path = _state_path_for(spec_path)
        # The project root is derived exactly as the chain module derives it;
        # avoid accepting a plan authority from an unrelated checkout.
        project_root = spec_path.resolve()
        for parent in project_root.parents:
            if parent.name == ".megaplan":
                project_root = parent.parent
                break
        plan_dir = find_plan_dir(project_root, expected_current_plan)
        plan_state_path = plan_dir / "state.json" if plan_dir is not None else None
        if plan_state_path is None or not plan_state_path.is_file():
            raise ChainControlHold("missing_plan_state", "canonical paused plan state is unavailable")

        recovery_epoch = _stable_id(
            "release-hold",
            chain_id,
            operation_id,
            expected_hold_event_hash,
        )

        def _release(txn: LockedChainControlTransaction) -> dict[str, Any]:
            replay = self.replay_strict()
            for event in replay["accepted"]:
                payload = event.get("payload")
                if (
                    event.get("event_kind") == "chain_control.hold_released"
                    and isinstance(payload, Mapping)
                    and payload.get("chain_id") == chain_id
                    and payload.get("target_operation_id") == operation_id
                    and payload.get("held_event_hash") == expected_hold_event_hash
                    and payload.get("release_operation_id") == recovery_epoch
                ):
                    return {"replay_event": event, "existing": True}
            # A release is uniquely identified by the exact held operation
            # tuple.  The held operation must still project to that hold: a
            # later terminal event is evidence that another recovery path has
            # already resolved it and must never be laundered by a release.
            operation_events = [
                event
                for event in replay["accepted"]
                if event.get("chain_id") == chain_id
                and event.get("operation_id") == operation_id
            ]
            latest = operation_events[-1] if operation_events else None
            holds = [
                event
                for event in replay["accepted"]
                if event.get("chain_id") == chain_id
                and event.get("operation_id") == operation_id
                and event.get("event_kind") == "chain_control.hold"
                and event.get("event_hash") == expected_hold_event_hash
            ]
            if (
                len(holds) != 1
                or not isinstance(latest, Mapping)
                or latest.get("chain_id") != chain_id
                or latest.get("event_kind") != "chain_control.hold"
                or latest.get("event_hash") != expected_hold_event_hash
            ):
                raise ChainControlHold(
                    "hold_target_mismatch",
                    "release-hold target is not the latest exact durable chain hold",
                )
            current = ChainStateAdapter(txn, state_path).read_expected()
            if not isinstance(current, Mapping):
                raise ChainControlHold("missing_chain_state", "canonical chain state is unavailable")
            metadata = current.get("metadata") or {}
            if hashlib.sha256(spec_path.read_bytes()).hexdigest() != expected_chain_spec_sha256:
                raise ChainControlHold("spec_cas_conflict", "chain spec SHA-256 changed")
            if str(metadata.get("chain_spec_sha256") or "") != expected_chain_spec_sha256:
                raise ChainControlHold("spec_cas_conflict", "persisted chain spec SHA-256 changed")
            if state_digest_for(current) != expected_state_digest:
                raise ChainControlCasConflict("chain state digest changed")
            observed_revision = metadata.get("_nbf08_revision")
            if state_revision_expectation == "absent":
                if observed_revision is not None:
                    raise ChainControlCasConflict(
                        "chain state revision is present; missing-revision guard failed"
                    )
            elif observed_revision != expected_revision_value:
                raise ChainControlCasConflict("chain state revision changed")
            if current.get("current_milestone_index") != expected_cursor:
                raise ChainControlCasConflict("chain cursor changed")
            if str(current.get("current_plan_name") or "") != expected_current_plan:
                raise ChainControlCasConflict("chain current plan changed")
            spec = load_spec(spec_path)
            if not (0 <= expected_cursor < len(spec.milestones)):
                raise ChainControlHold("cursor_mismatch", "current cursor is outside the frozen spec")
            if spec.milestones[expected_cursor].label != expected_current_milestone:
                raise ChainControlHold("milestone_mismatch", "current milestone does not match the frozen spec")
            try:
                plan_state = json.loads(plan_state_path.read_text(encoding="utf-8"))
                _assert_pause(current, plan_state, expected_plan=expected_current_plan)
            except (OSError, json.JSONDecodeError) as exc:
                raise ChainControlHold("pause_unreadable", "canonical paused plan state is unreadable") from exc
            except Exception as exc:
                if isinstance(exc, ChainControlError):
                    raise
                raise ChainControlHold("pause_mismatch", str(exc)) from exc

            base = {
                "target_operation_id": operation_id,
                "held_event_hash": expected_hold_event_hash,
                "held_event_id": holds[0].get("event_id"),
                "release_operation_id": recovery_epoch,
                "recovery_epoch": recovery_epoch,
                "chain_id": chain_id,
                "chain_spec_sha256": expected_chain_spec_sha256,
                "state_digest": expected_state_digest,
                "state_revision": expected_revision_value,
                **(
                    {
                        "expected_state_revision": None,
                        "state_revision_expectation": state_revision_expectation,
                    }
                    if state_revision_expectation == "absent"
                    else {}
                ),
                "cursor": expected_cursor,
                "current_milestone": expected_current_milestone,
                "current_plan": expected_current_plan,
                "recovery_evidence": {"path": str(recovery_evidence.resolve()), "sha256": evidence_sha},
                "reason": reason,
            }
            intent = self.append_under_lock(
                txn, event_kind="chain_control.intent", chain_id=chain_id,
                operation_id=operation_id, causation_id=recovery_epoch,
                correlation_id=recovery_epoch, recovery_id=recovery_epoch,
                payload={"intent_kind": "release-hold", **base}, semantic_effect="no_change",
                claim_class="evidence-only", actor=actor, intent="release-hold",
                expected_cursor=expected_cursor, expected_revision=expected_revision_value,
                linked_receipts=[str(recovery_evidence.resolve())], spec_identity=str(spec_path.resolve()),
            )
            validated = self.append_under_lock(
                txn, event_kind="chain_control.authority_validated", chain_id=chain_id,
                operation_id=operation_id, causation_id=intent["payload"]["event_id"],
                correlation_id=recovery_epoch, recovery_id=recovery_epoch,
                payload={"intent_kind": "release-hold", **base}, semantic_effect="no_change",
                claim_class="evidence-only", actor=actor, intent="release-hold",
            )
            claimed = self.append_under_lock(
                txn, event_kind="chain_control.claimed", chain_id=chain_id,
                operation_id=operation_id, causation_id=validated["payload"]["event_id"],
                correlation_id=recovery_epoch, recovery_id=recovery_epoch,
                payload={"intent_kind": "release-hold", "claim": "single-use", **base}, semantic_effect="no_change",
                claim_class="evidence-only", actor=actor, intent="release-hold",
            )
            released = self.append_under_lock(
                txn, event_kind="chain_control.hold_released", chain_id=chain_id,
                operation_id=operation_id, causation_id=claimed["payload"]["event_id"],
                correlation_id=recovery_epoch, recovery_id=recovery_epoch,
                payload=base, semantic_effect="no_change", claim_class="evidence-only",
                actor=actor, intent="release-hold", outcome="hold_released",
                failure_class="chain_control.hold", expected_cursor=expected_cursor,
                expected_revision=expected_revision_value, actual_cursor=expected_cursor,
                actual_revision=expected_revision_value, pre_state_digest=expected_state_digest,
                post_state_digest=expected_state_digest,
                linked_receipts=[str(recovery_evidence.resolve())], spec_identity=str(spec_path.resolve()),
            )
            return {
                # ``append_under_lock`` returns the physical record wrapper;
                # expose its canonical chain-control envelope to match replay.
                "event": released.get("payload", released),
                "release_operation_id": recovery_epoch,
                "existing": False,
            }

        with self.transaction(
            chain_ids=[chain_id],
            state_paths=[state_path, plan_state_path],
            expected_revision=None,
            operation_id=operation_id,
            actor={"id": actor, "class": "operator"},
        ) as txn:
            result = _release(txn)
        if result.get("existing"):
            replay_event = result["replay_event"]
            return {
                "outcome": "replay",
                # Keep the replay receipt byte/semantic-compatible with the
                # committed result.  The full envelope is required by the
                # released-hold receipt consumer and carries its event hash.
                "event": replay_event,
                "release_operation_id": recovery_epoch,
            }
        # Both first-write and replay expose the canonical full envelope.
        # Consumers may persist either result as the released-hold receipt.
        return {"outcome": "committed", **result}

    def ensure_genesis(
        self,
        *,
        chain_id: str,
        actor: Any,
        spec_identity: Any = None,
        source_identity: Any = None,
        parent_chain_id: str | None = None,
    ) -> dict[str, Any]:
        if self.is_bound(chain_id):
            replay = self.replay_strict()
            for event in replay["accepted"]:
                if event.get("chain_id") == chain_id and event.get("event_kind") == "chain_control.genesis_accepted":
                    return event
        operation_id = _stable_id("genesis", chain_id, self.ledger_id)
        with self.transaction(chain_ids=[chain_id], operation_id=operation_id, actor=actor) as txn:
            physical = [item for item in read_physical_lines(self.ledger.events_path) if not item.torn]
            last_nbf01 = None
            for item in physical:
                if not str(item.record.get("kind") or "").startswith("chain_control."):
                    last_nbf01 = item
            if last_nbf01 is None:
                prefix_tip = -1
                prefix_digest = ZERO_DIGEST
            else:
                prefix_tip = last_nbf01.record.get("seq")
                prefix_digest = physical_digest_after(self.ledger_id, physical, upto_seq=int(prefix_tip))
            return self.append_under_lock(
                txn,
                event_kind="chain_control.genesis_accepted",
                chain_id=chain_id,
                operation_id=operation_id,
                causation_id=operation_id,
                correlation_id=operation_id,
                payload={
                    "prefix_tip_seq": prefix_tip,
                    "prefix_digest": prefix_digest,
                    "authority_mode": "file",
                    "schema_version": SCHEMA_VERSION,
                },
                semantic_effect="no_change",
                claim_class="required",
                actor=actor,
                outcome="committed",
                spec_identity=spec_identity,
                source_identity=source_identity,
                parent_chain_id=parent_chain_id,
            )["payload"]

    def rebind_suffix(
        self,
        *,
        chain_id: str,
        expected_physical_tip: str,
        expected_control_tip: str,
        from_authority: str,
        to_authority: str,
        source_manifest: Path,
        expected_base_sha256: str,
        expected_source_sha256: str,
        expected_manifest_sha256: str,
        reason: str,
        actor: str,
        receipt: Path,
    ) -> dict[str, Any]:
        replay = self.replay_strict()
        physical_tip = f"{replay['physical_sequence']}/{replay['physical_tip_digest']}"
        control_tip = replay["evidence_digest_by_chain"].get(chain_id, ZERO_DIGEST)
        observed_manifest = sha256_hex(source_manifest.read_bytes()) if source_manifest.exists() else ZERO_DIGEST
        observed_source = sha256_hex(self.ledger.events_path.read_bytes()) if self.ledger.events_path.exists() else ZERO_DIGEST
        observed_base = observed_repo_base_sha256(Path.cwd())
        recorded_authority = recorded_authority_for(replay, chain_id)
        if (
            physical_tip != expected_physical_tip
            or control_tip != expected_control_tip
            or observed_manifest != expected_manifest_sha256
            or observed_source != expected_source_sha256
            or observed_base != expected_base_sha256
            or recorded_authority != from_authority
        ):
            hold = {
                "outcome": "hold",
                "reason": "suffix_rebind_drift",
                "old_authority": recorded_authority,
                "from_authority": from_authority,
                "expected_physical_tip": expected_physical_tip,
                "actual_physical_tip": physical_tip,
                "expected_base_sha256": expected_base_sha256,
                "observed_base_sha256": observed_base,
            }
            receipt.parent.mkdir(parents=True, exist_ok=True)
            receipt.write_text(json.dumps(hold, indent=2) + "\n", encoding="utf-8")
            raise ChainControlHold("suffix_rebind_drift", "suffix rebind refused; old authority untouched", details=hold)
        operation_id = _stable_id("rebind-suffix", chain_id, expected_physical_tip, expected_control_tip)
        existing = self.operation_result(operation_id)
        if existing is not None:
            body = {
                "outcome": "replay",
                "expected_base_sha256": expected_base_sha256,
                "expected_source_sha256": expected_source_sha256,
                "expected_manifest_sha256": expected_manifest_sha256,
                "base_sha256": observed_base,
                "source_sha256": observed_source,
                "manifest_sha256": observed_manifest,
                "actor": actor,
                "operation_id": operation_id,
                "from_authority": from_authority,
                "to_authority": to_authority,
                "reason": reason,
            }
            receipt.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
            return body
        result = self.mutate(
            chain_id=chain_id,
            operation_id=operation_id,
            intent_kind="suffix_rebind",
            actor={"id": actor, "class": "operator"},
            effect=lambda txn: {
                "pre_state_digest": control_tip,
                "post_state_digest": control_tip,
                "actual_cursor": control_tip,
                "from_authority": from_authority,
                "to_authority": to_authority,
            },
        )
        with self.transaction(chain_ids=[chain_id], operation_id=operation_id + ":suffix", actor=actor) as txn:
            rebound = self.append_under_lock(
                txn,
                event_kind="chain_control.suffix_rebound",
                chain_id=chain_id,
                operation_id=operation_id,
                causation_id=str(result["result"].get("event_id") or operation_id),
                correlation_id=operation_id,
                payload={
                    "from_authority": from_authority,
                    "to_authority": to_authority,
                    "reason": reason,
                    "unexecuted_suffix_only": True,
                },
                semantic_effect="metadata_only",
                claim_class="required",
                actor={"id": actor, "class": "operator"},
                outcome="committed",
            )
        body = {
            "outcome": "committed",
            "expected_base_sha256": expected_base_sha256,
            "expected_source_sha256": expected_source_sha256,
            "expected_manifest_sha256": expected_manifest_sha256,
            "base_sha256": observed_base,
            "source_sha256": observed_source,
            "manifest_sha256": observed_manifest,
            "actor": actor,
            "operation_id": operation_id,
            "idempotency_key": operation_id,
            "suffix_tip": rebound["payload"]["event_hash"],
            "from_authority": from_authority,
            "to_authority": to_authority,
            "reason": reason,
        }
        receipt.parent.mkdir(parents=True, exist_ok=True)
        receipt.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
        return body

    def rebind_nbf07_dependency(
        self,
        *,
        chain_id: str,
        tasklist: Path,
        chain_spec: Path,
        expected_tasklist_sha256: str,
        expected_chain_spec_sha256: str,
        suffix_tip: str,
        expected_base_sha256: str,
        expected_source_sha256: str,
        expected_manifest_sha256: str,
        candidate_sha: str,
        inventory_sha256: str,
        framed_diff_sha256: str,
        actor: str,
        receipt: Path,
    ) -> dict[str, Any]:
        replay = self.replay_strict()
        rebound = [
            event
            for event in replay["accepted"]
            if event.get("event_kind") == "chain_control.suffix_rebound" and event.get("chain_id") == chain_id
        ]
        if not rebound:
            raise ChainControlHold("rebind_nbf07_gated", "rebind-nbf07-dependency is unavailable until suffix verification passes")
        if rebound[-1]["event_hash"] != suffix_tip:
            raise ChainControlHold("suffix_tip_mismatch", "dependency rebind suffix tip does not match")
        observed_tasklist = sha256_hex(tasklist.read_bytes())
        observed_spec = sha256_hex(chain_spec.read_bytes()) if chain_spec.exists() else ZERO_DIGEST
        if observed_tasklist != expected_tasklist_sha256 or observed_spec != expected_chain_spec_sha256:
            raise ChainControlHold("dependency_digest_drift", "tasklist/spec digest drift; no mutation")
        operation_id = _stable_id("rebind-nbf07", chain_id, suffix_tip, expected_tasklist_sha256)
        existing = self.operation_result(operation_id)

        def _cas_temp_dependencies(txn: LockedChainControlTransaction) -> dict[str, Any]:
            txn.assert_open()
            current_tasklist = tasklist.read_bytes()
            current_spec = chain_spec.read_bytes() if chain_spec.exists() else b""
            if sha256_hex(current_tasklist) != expected_tasklist_sha256 or sha256_hex(current_spec) != expected_chain_spec_sha256:
                raise ChainControlHold("dependency_digest_drift", "tasklist/spec digest drift; no mutation")
            new_tasklist = _inject_nbf08_dependency_text(current_tasklist, kind="tasklist")
            new_spec = _inject_nbf08_dependency_text(current_spec, kind="spec")
            tasklist.write_bytes(new_tasklist)
            chain_spec.write_bytes(new_spec)
            return {
                "pre_state_digest": expected_tasklist_sha256,
                "post_state_digest": sha256_hex(new_tasklist),
                "tasklist_sha256": sha256_hex(new_tasklist),
                "chain_spec_sha256": sha256_hex(new_spec),
                "gated": True,
            }

        if existing is None:
            mutated = self.mutate(
                chain_id=chain_id,
                operation_id=operation_id,
                intent_kind="rebind_nbf07_dependency",
                actor={"id": actor, "class": "operator"},
                effect=_cas_temp_dependencies,
            )
            observed_tasklist = sha256_hex(tasklist.read_bytes())
            observed_spec = sha256_hex(chain_spec.read_bytes()) if chain_spec.exists() else ZERO_DIGEST
            _ = mutated
        body = {
            "outcome": "replay" if existing is not None else "committed",
            "expected_base_sha256": expected_base_sha256,
            "expected_source_sha256": expected_source_sha256,
            "expected_manifest_sha256": expected_manifest_sha256,
            "base_sha256": expected_base_sha256,
            "source_sha256": expected_source_sha256,
            "manifest_sha256": expected_manifest_sha256,
            "actor": actor,
            "operation_id": operation_id,
            "idempotency_key": operation_id,
            "suffix_tip": suffix_tip,
            "candidate_sha": candidate_sha,
            "inventory_sha256": inventory_sha256,
            "framed_diff_sha256": framed_diff_sha256,
            "tasklist_sha256": observed_tasklist,
            "chain_spec_sha256": observed_spec,
        }
        receipt.parent.mkdir(parents=True, exist_ok=True)
        receipt.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
        return body


def journal_for(root: Path) -> ChainControlJournal:
    from arnold_pipelines.megaplan.incident.ledger import IncidentLedger

    return ChainControlJournal(IncidentLedger(root))


def active_transaction() -> LockedChainControlTransaction | None:
    return _ACTIVE_TXN.get()


def require_bound_context(spec_path: Path, *, root: Path | None = None) -> ChainControlJournal | None:
    project_root = root
    if project_root is None:
        resolved = spec_path.resolve(strict=False)
        for parent in resolved.parents:
            if parent.name == ".megaplan":
                project_root = parent.parent
                break
        if project_root is None:
            project_root = resolved.parent
    journal = journal_for(project_root)
    chain_id = chain_id_for_spec(spec_path)
    if journal.is_bound(chain_id):
        return journal
    return None


_SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")


def _committed_state_digest(journal: ChainControlJournal, chain_id: str) -> str | None:
    replay = journal.replay_strict()
    committed = [
        event
        for event in replay["accepted"]
        if event.get("chain_id") == chain_id
        and event.get("event_kind") in {
            "chain_control.committed",
            "chain_control.runtime_rebound",
        }
        and event.get("semantic_effect") == "advance"
        and isinstance(event.get("post_state_digest"), str)
        and _SHA256_HEX.match(event["post_state_digest"] or "")
    ]
    if not committed:
        return None
    return committed[-1]["post_state_digest"]


def verify_bound_state_matches_journal(spec_path: Path, payload: Mapping[str, Any] | None = None) -> None:
    """Raise ChainControlTamper when a bound chain file diverges from the journal."""
    journal = require_bound_context(spec_path)
    if journal is None:
        return
    chain_id = chain_id_for_spec(spec_path)
    replay = journal.replay_strict()
    incomplete = _incomplete_operation_statuses(replay, chain_id)
    active = active_transaction()
    if active is not None and active.journal.ledger_id == journal.ledger_id:
        incomplete.pop(active.operation_id, None)
    if incomplete:
        raise DurabilityUnknown(
            "chain has an incomplete operation; state verification requires reconciliation",
            details={"operations": incomplete, "chain_id": chain_id},
        )
    expected = _committed_state_digest(journal, chain_id)
    if expected is None:
        return
    current = payload
    if current is None:
        from arnold_pipelines.megaplan.chain.spec import _state_path_for

        state_path = _state_path_for(spec_path)
        if not state_path.exists():
            return
        current = json.loads(state_path.read_text(encoding="utf-8"))
    actual = state_digest_for(current)
    if actual != expected:
        raise ChainControlTamper(
            "raw chain state edit diverges from journal",
            details={"expected": expected, "actual": actual, "chain_id": chain_id},
        )


def persist_bound_chain_state(
    spec_path: Path,
    payload: Mapping[str, Any],
    *,
    state_path: Path,
    operation_id: str,
    intent_kind: str,
    actor: Any = None,
    expected_revision: Any = None,
    linked_receipts: list[Any] | None = None,
) -> dict[str, Any]:
    journal = require_bound_context(spec_path)
    txn = active_transaction()
    if journal is None and txn is None:
        return {"outcome": "unbound"}
    if journal is None:
        journal = txn.journal
    chain_id = chain_id_for_spec(spec_path)

    def _write(active: LockedChainControlTransaction) -> dict[str, Any]:
        adapter = ChainStateAdapter(active, state_path)
        before = adapter.read_expected()
        verify_bound_state_matches_journal(spec_path, before)
        pre = state_digest_for(before) if before is not None else ZERO_DIGEST
        written = adapter.cas_write(payload, expected_revision=expected_revision if expected_revision is not None else (None if before is None else before.get("metadata", {}).get("_nbf08_revision")))
        return {
            "pre_state_digest": pre,
            "post_state_digest": state_digest_for(written),
            "actual_revision": written.get("metadata", {}).get("_nbf08_revision"),
            "actual_cursor": written.get("current_milestone_index"),
            "linked_receipts": linked_receipts or [],
        }

    if txn is not None:
        return _write(txn)
    result = journal.mutate(
        chain_id=chain_id,
        operation_id=operation_id,
        intent_kind=intent_kind,
        actor=actor or {"id": "chain", "class": "system"},
        expected_revision=expected_revision,
        state_paths=[state_path],
        spec_identity=str(spec_path.resolve(strict=False)),
        linked_receipts=linked_receipts,
        effect=_write,
    )
    error = result.get("error")
    if error is not None:
        raise error
    return result


def apply_chain_lifecycle(
    spec_path: Path,
    root: Path,
    *,
    intent_kind: str,
    actor: Any,
    operation_id: str | None = None,
    expected_revision: Any = None,
    expected_cursor: Any = None,
    linked_receipts: list[Any] | None = None,
    parent_chain_id: str | None = None,
    effect: Callable[[LockedChainControlTransaction], dict[str, Any]] | None = None,
    state_paths: Sequence[Path] = (),
    committed_event_kind: str = "chain_control.committed",
    intent_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    journal = journal_for(root)
    chain_id = chain_id_for_spec(spec_path)
    journal.ensure_genesis(
        chain_id=chain_id,
        actor=actor,
        spec_identity=str(spec_path.resolve(strict=False)),
        parent_chain_id=parent_chain_id,
    )
    from arnold_pipelines.megaplan.chain.spec import _state_path_for

    state_path = _state_path_for(spec_path)
    op_id = operation_id or _stable_id(intent_kind, chain_id, str(expected_revision))
    return journal.mutate(
        chain_id=chain_id,
        operation_id=op_id,
        intent_kind=intent_kind,
        actor=actor,
        expected_revision=expected_revision,
        expected_cursor=expected_cursor,
        state_paths=[state_path, *state_paths],
        parent_chain_id=parent_chain_id,
        spec_identity=str(spec_path.resolve(strict=False)),
        linked_receipts=linked_receipts,
        effect=effect,
        committed_event_kind=committed_event_kind,
        intent_context=intent_context,
    )


def reject_context_free_bound_save(spec_path: Path, *, direct: bool = False) -> None:
    if not direct:
        return
    journal = require_bound_context(spec_path)
    if journal is not None and active_transaction() is None:
        raise UnattributedStateChange("context-free bound save_chain_state is forbidden")


def projection_rebuild(journal: ChainControlJournal) -> dict[str, Any]:
    replay = journal.replay_strict()
    return {
        "authority": "file",
        "physical_sequence": replay["physical_sequence"],
        "physical_tip_digest": replay["physical_tip_digest"],
        "operations": sorted(replay["operations"]),
        "holds": [event["event_id"] for event in replay["holds"]],
        "semantic_by_chain": replay["semantic_by_chain"],
    }


def _cli(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="arnold_pipelines.megaplan.incident.chain_control")
    sub = parser.add_subparsers(dest="action", required=True)
    rebound = sub.add_parser("rebind-suffix")
    rebound.add_argument("--ledger", required=True)
    rebound.add_argument("--chain-id", required=True)
    rebound.add_argument("--expected-physical-tip", required=True)
    rebound.add_argument("--expected-control-tip", required=True)
    rebound.add_argument("--from-authority", required=True)
    rebound.add_argument("--to-authority", required=True)
    rebound.add_argument("--source-manifest", required=True)
    rebound.add_argument("--expected-base-sha256", required=True)
    rebound.add_argument("--expected-source-sha256", required=True)
    rebound.add_argument("--expected-manifest-sha256", required=True)
    rebound.add_argument("--reason", required=True)
    rebound.add_argument("--actor", required=True)
    rebound.add_argument("--receipt", required=True)
    dep = sub.add_parser("rebind-nbf07-dependency")
    dep.add_argument("--ledger", required=True)
    dep.add_argument("--chain-id", required=True)
    dep.add_argument("--tasklist", required=True)
    dep.add_argument("--chain-spec", required=True)
    dep.add_argument("--expected-tasklist-sha256", required=True)
    dep.add_argument("--expected-chain-spec-sha256", required=True)
    dep.add_argument("--suffix-tip", required=True)
    dep.add_argument("--expected-base-sha256", required=True)
    dep.add_argument("--expected-source-sha256", required=True)
    dep.add_argument("--expected-manifest-sha256", required=True)
    dep.add_argument("--candidate-sha", required=True)
    dep.add_argument("--inventory-sha256", required=True)
    dep.add_argument("--framed-diff-sha256", required=True)
    dep.add_argument("--actor", required=True)
    dep.add_argument("--receipt", required=True)
    quarantine = sub.add_parser("quarantine-trailing-sequence-collision")
    quarantine.add_argument("--ledger", required=True)
    quarantine.add_argument("--expected-journal-sha256", required=True)
    quarantine.add_argument("--expected-sidecar-sha256", required=True)
    quarantine.add_argument("--expected-prefix-sequence", required=True, type=int)
    quarantine.add_argument("--expected-prefix-line-sha256", required=True)
    quarantine.add_argument("--expected-prefix-digest", required=True)
    quarantine.add_argument("--expected-offending-line-sha256", required=True)
    quarantine.add_argument("--expected-operation-id", required=True)
    quarantine.add_argument("--expected-event-id", required=True)
    quarantine.add_argument("--marker", required=True)
    quarantine.add_argument("--expected-marker-sha256", required=True)
    quarantine.add_argument("--manifest", required=True)
    quarantine.add_argument("--expected-manifest-sha256", required=True)
    quarantine.add_argument("--spec", required=True)
    quarantine.add_argument("--expected-spec-sha256", required=True)
    quarantine.add_argument("--workspace", required=True)
    quarantine.add_argument("--expected-workspace-sha256", required=True)
    quarantine.add_argument("--custody-dir", required=True)
    quarantine.add_argument("--receipt", required=True)
    quarantine.add_argument("--actor", required=True)
    args = parser.parse_args(argv)
    from arnold_pipelines.megaplan.incident.ledger import IncidentLedger

    journal = ChainControlJournal(IncidentLedger(Path(args.ledger)))
    try:
        if args.action == "rebind-suffix":
            journal.rebind_suffix(
                chain_id=args.chain_id,
                expected_physical_tip=args.expected_physical_tip,
                expected_control_tip=args.expected_control_tip,
                from_authority=args.from_authority,
                to_authority=args.to_authority,
                source_manifest=Path(args.source_manifest),
                expected_base_sha256=args.expected_base_sha256,
                expected_source_sha256=args.expected_source_sha256,
                expected_manifest_sha256=args.expected_manifest_sha256,
                reason=args.reason,
                actor=args.actor,
                receipt=Path(args.receipt),
            )
            return 0
        if args.action == "quarantine-trailing-sequence-collision":
            result = journal.quarantine_trailing_sequence_collision(
                expected_journal_sha256=args.expected_journal_sha256,
                expected_sidecar_sha256=args.expected_sidecar_sha256,
                expected_prefix_sequence=args.expected_prefix_sequence,
                expected_prefix_line_sha256=args.expected_prefix_line_sha256,
                expected_prefix_digest=args.expected_prefix_digest,
                expected_offending_line_sha256=args.expected_offending_line_sha256,
                expected_operation_id=args.expected_operation_id,
                expected_event_id=args.expected_event_id,
                marker_path=Path(args.marker),
                expected_marker_sha256=args.expected_marker_sha256,
                manifest_path=Path(args.manifest),
                expected_manifest_sha256=args.expected_manifest_sha256,
                spec_path=Path(args.spec),
                expected_spec_sha256=args.expected_spec_sha256,
                workspace_path=Path(args.workspace),
                expected_workspace_sha256=args.expected_workspace_sha256,
                custody_dir=Path(args.custody_dir),
                receipt_path=Path(args.receipt),
                actor=args.actor,
            )
            sys.stdout.write(json.dumps(result["receipt"], sort_keys=True) + "\n")
            return 0
        journal.rebind_nbf07_dependency(
            chain_id=args.chain_id,
            tasklist=Path(args.tasklist),
            chain_spec=Path(args.chain_spec),
            expected_tasklist_sha256=args.expected_tasklist_sha256,
            expected_chain_spec_sha256=args.expected_chain_spec_sha256,
            suffix_tip=args.suffix_tip,
            expected_base_sha256=args.expected_base_sha256,
            expected_source_sha256=args.expected_source_sha256,
            expected_manifest_sha256=args.expected_manifest_sha256,
            candidate_sha=args.candidate_sha,
            inventory_sha256=args.inventory_sha256,
            framed_diff_sha256=args.framed_diff_sha256,
            actor=args.actor,
            receipt=Path(args.receipt),
        )
        return 0
    except ChainControlHold as exc:
        sys.stderr.write(f"{exc.code}: {exc}\n")
        return 2


def main() -> None:
    raise SystemExit(_cli())


if __name__ == "__main__":
    main()
