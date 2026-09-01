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
import subprocess
import sys
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator, Mapping, Sequence

ABSENT: dict[str, bool] = {"__nbf08_absent__": True}
ABSENT_KEY = "__nbf08_absent__"
SCHEMA_VERSION = "nbf08-chain-control-v1"
RESERVATION_SCHEMA = "nbf08-sequence-reservation-v1"
EVENT_DOMAIN = b"NBF08-CHAIN-CONTROL-EVENT-V1\x00"
PAYLOAD_DOMAIN = b"NBF08-CHAIN-CONTROL-PAYLOAD-V1\x00"
PHYSICAL_DOMAIN = b"NBF08-PHYSICAL-RECORD-V1\x00"
ZERO_DIGEST = "0" * 64

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
        "chain_control.backend_rebound",
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
        "chain_control.replay",
        "chain_control.authority_validated",
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
        seq_path = self.journal.ledger._journal._seq_path
        seq_path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(seq_path), os.O_RDWR | os.O_CREAT, 0o644)
        fcntl.flock(fd, fcntl.LOCK_EX)
        self._seq_fd = fd
        try:
            self.journal.recover_reservations_locked(fd)
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
        physical = [item for item in read_physical_lines(self.ledger.events_path) if not item.torn]
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
            write_reservation_locked(seq_fd, reservation)
            if reservation.get("status") == "reserved":
                return self._recover_reserved_locked(seq_fd, reservation, physical, previous)
            return reservation
        reservation = parsed
        status = reservation.get("status")
        if status == "reserved":
            return self._recover_reserved_locked(seq_fd, reservation, physical, previous)
        if status in {"committed", "tombstoned"}:
            return reservation
        raise DurabilityUnknown("reservation sidecar has an unknown status", details={"status": status})

    def _recover_reserved_locked(
        self,
        seq_fd: int,
        reservation: dict[str, Any],
        physical: Sequence[PhysicalRecord],
        previous: str,
    ) -> dict[str, Any]:
        reserved_seq = reservation.get("physical_sequence")
        matching = [item for item in physical if item.record.get("seq") == reserved_seq]
        reservation_id = reservation.get("reservation_id")
        intended = reservation.get("intended_record_sha256")
        if matching:
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
                write_reservation_locked(seq_fd, reservation)
                return reservation
            if intended and intended != ZERO_DIGEST and intended != line_sha:
                raise DurabilityUnknown(
                    "reservation intended_record_sha256 does not match complete line",
                    details={"reservation_id": reservation_id, "intended": intended, "actual": line_sha},
                )
            payload_id = payload.get("reservation_id") if isinstance(payload, dict) else None
            if reservation_id and payload_id not in {None, reservation_id} and payload.get("reservation_id") not in {None, reservation_id}:
                raise DurabilityUnknown(
                    "reservation_id collision at reserved sequence",
                    details={"reservation_id": reservation_id, "payload_id": payload_id},
                )
            reservation["status"] = "committed"
            reservation["intended_record_sha256"] = line_sha
            write_reservation_locked(seq_fd, reservation)
            return reservation
        tombstone = self._append_tombstone_locked(seq_fd, reservation, previous_physical_digest=previous)
        reservation["status"] = "tombstoned"
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
        physical = read_physical_lines(self.ledger.events_path)
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
            intent = self.append_under_lock(
                txn,
                event_kind="chain_control.intent",
                chain_id=chain_id,
                operation_id=operation_id,
                causation_id=operation_id,
                correlation_id=operation_id,
                payload={"intent_kind": intent_kind, "expected_revision": expected_revision},
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
                payload={"intent_kind": intent_kind},
                semantic_effect="no_change",
                claim_class=claim_class,
                actor=actor,
                intent=intent_kind,
                parent_chain_id=parent_chain_id,
            )
            claimed = self.append_under_lock(
                txn,
                event_kind="chain_control.claimed",
                chain_id=chain_id,
                operation_id=operation_id,
                causation_id=validated["payload"]["event_id"],
                correlation_id=operation_id,
                payload={"intent_kind": intent_kind, "claim": "single-use"},
                semantic_effect="no_change",
                claim_class=claim_class,
                actor=actor,
                intent=intent_kind,
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
                    payload={"reason": str(exc), "code": exc.code, "details": exc.details},
                    semantic_effect="no_change",
                    claim_class="held" if isinstance(exc, DurabilityUnknown) else "evidence-only",
                    actor=actor,
                    outcome="tamper" if tamper else "hold",
                    failure_class=exc.code,
                    parent_chain_id=parent_chain_id,
                )
                return {"outcome": "tamper" if tamper else "hold", "result": hold, "error": exc}
            pre_digest = effect_result.get("pre_state_digest")
            post_digest = effect_result.get("post_state_digest")
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
            txn.result = committed
            return {
                "outcome": "committed",
                "result": committed.get("payload", committed),
                "event": committed.get("payload", committed),
                "effect": effect_result,
            }

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
        and event.get("event_kind") == "chain_control.committed"
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
