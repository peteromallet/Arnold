"""File-backed encrypted storage for ledger payload bytes.

This module operationalizes byte-level retention checks for local tests and
runtime wiring. Metadata validators can describe the policy, but this store
is where bytes are actually encrypted, scoped, audited, expired, tombstoned,
and deleted.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from arnold.manifest.manifests import canonical_json
from arnold.workflow.durable_refs import (
    AccessScope,
    DurableRef,
    EncryptionScope,
    RetentionClass,
)
from arnold.workflow.ledger_trace import FileLedgerTrace, LedgerTraceEvent
from arnold.workflow.ledger_payload_store import PayloadExpiredError
from arnold.workflow.payload_policy import RetentionMode, RetentionPayloadPolicy


LEDGER_PAYLOAD_STORE_SCHEMA_VERSION = "arnold.workflow.ledger_payload_store.v1"
_CIPHERTEXT_PREFIX = b"arnold-ledger-payload-v1\n"


class LedgerPayloadStoreError(Exception):
    """Base class for stored-byte policy failures."""


class TenantIsolationError(LedgerPayloadStoreError):
    """Raised when a ref is read or deleted outside its tenant/workflow."""


class LegalHoldError(LedgerPayloadStoreError):
    """Raised when deletion is attempted for legal-hold bytes."""


class KeyUnavailableError(LedgerPayloadStoreError):
    """Raised when a stored ref's key version cannot be resolved."""



class PayloadTombstonedError(LedgerPayloadStoreError):
    """Raised when bytes have been tombstoned or deleted."""


class DigestMismatchError(LedgerPayloadStoreError):
    """Raised when decrypted bytes do not match the ref digest."""


class LegacyHistoryUnbackfillableError(LedgerPayloadStoreError):
    """Raised for legacy histories that have no recoverable byte backing."""


@dataclass(frozen=True)
class LocalPayloadKey:
    key_id: str
    key_version: int
    material: bytes

    def __post_init__(self) -> None:
        if not self.key_id.strip():
            raise ValueError("LocalPayloadKey.key_id must be non-empty")
        if self.key_version < 1:
            raise ValueError("LocalPayloadKey.key_version must be >= 1")
        if not self.material:
            raise ValueError("LocalPayloadKey.material must be non-empty")


class LocalPayloadKeyring:
    """In-memory key/version registry for local byte-store tests."""

    def __init__(self) -> None:
        self._keys: dict[tuple[str, int], LocalPayloadKey] = {}
        self._primary: tuple[str, int] | None = None

    def add_key(
        self,
        key_id: str,
        key_version: int,
        material: bytes,
        *,
        primary: bool = False,
    ) -> LocalPayloadKey:
        key = LocalPayloadKey(
            key_id=key_id,
            key_version=key_version,
            material=bytes(material),
        )
        self._keys[(key_id, key_version)] = key
        if primary or self._primary is None:
            self._primary = (key_id, key_version)
        return key

    @property
    def primary_key(self) -> LocalPayloadKey:
        if self._primary is None:
            raise KeyUnavailableError("No primary payload encryption key configured")
        return self.resolve(*self._primary)

    def resolve(self, key_id: str, key_version: int) -> LocalPayloadKey:
        try:
            return self._keys[(key_id, key_version)]
        except KeyError as exc:
            raise KeyUnavailableError(
                f"No payload key for {key_id!r} version {key_version}"
            ) from exc


@dataclass(frozen=True)
class StoredPayloadMetadata:
    locator: str
    tenant_id: str
    workflow_id: str
    digest: str
    size_bytes: int
    key_id: str
    key_version: int
    created_at_ns: int
    expires_at_ns: int | None
    legal_hold: bool
    tombstoned_at_ns: int | None = None
    schema_version: str = LEDGER_PAYLOAD_STORE_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "locator": self.locator,
            "tenant_id": self.tenant_id,
            "workflow_id": self.workflow_id,
            "digest": self.digest,
            "size_bytes": self.size_bytes,
            "key_id": self.key_id,
            "key_version": self.key_version,
            "created_at_ns": self.created_at_ns,
            "legal_hold": self.legal_hold,
            "schema_version": self.schema_version,
        }
        if self.expires_at_ns is not None:
            payload["expires_at_ns"] = self.expires_at_ns
        if self.tombstoned_at_ns is not None:
            payload["tombstoned_at_ns"] = self.tombstoned_at_ns
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "StoredPayloadMetadata":
        return cls(
            locator=payload["locator"],
            tenant_id=payload["tenant_id"],
            workflow_id=payload["workflow_id"],
            digest=payload["digest"],
            size_bytes=payload["size_bytes"],
            key_id=payload["key_id"],
            key_version=payload["key_version"],
            created_at_ns=payload["created_at_ns"],
            expires_at_ns=payload.get("expires_at_ns"),
            legal_hold=payload.get("legal_hold", False),
            tombstoned_at_ns=payload.get("tombstoned_at_ns"),
            schema_version=payload.get(
                "schema_version", LEDGER_PAYLOAD_STORE_SCHEMA_VERSION
            ),
        )


class FileBackedLedgerPayloadStore:
    """Local encrypted byte store with durable ref lifecycle enforcement."""

    store_id = "arnold.workflow.ledger_payload_store.local"

    def __init__(
        self,
        root: str | Path,
        keyring: LocalPayloadKeyring,
        *,
        trace: FileLedgerTrace | None = None,
    ) -> None:
        self.root = Path(root)
        self.keyring = keyring
        self.trace = trace
        (self.root / "objects").mkdir(parents=True, exist_ok=True)

    def put_bytes(
        self,
        data: bytes,
        *,
        tenant_id: str,
        workflow_id: str,
        retention_policy: RetentionPayloadPolicy | None = None,
        media_type: str = "application/octet-stream",
        now_ns: int | None = None,
    ) -> DurableRef:
        if retention_policy is None:
            retention_policy = RetentionPayloadPolicy()
        if not retention_policy.encryption_required:
            raise ValueError("Stored payload bytes require encryption")
        if not tenant_id.strip() or not workflow_id.strip():
            raise ValueError("tenant_id and workflow_id must be non-empty")

        now = time.time_ns() if now_ns is None else now_ns
        key = self.keyring.primary_key
        digest = _digest(data)
        locator = _new_locator()
        expires_at_ns = _expiry_from_policy(retention_policy, now)
        ciphertext = _encrypt(data, key.material)
        data_path = self._data_path(locator)
        metadata = StoredPayloadMetadata(
            locator=locator,
            tenant_id=tenant_id,
            workflow_id=workflow_id,
            digest=digest,
            size_bytes=len(data),
            key_id=key.key_id,
            key_version=key.key_version,
            created_at_ns=now,
            expires_at_ns=expires_at_ns,
            legal_hold=retention_policy.legal_hold
            or retention_policy.retention_mode == RetentionMode.LEGAL_HOLD,
        )

        data_path.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write_bytes(data_path, ciphertext)
        _atomic_write_text(
            self._metadata_path(locator),
            canonical_json(metadata.to_dict()),
        )
        self._trace(
            "write",
            metadata,
            "stored",
            "bytes encrypted and written",
        )
        return self._ref_from_metadata(metadata, media_type=media_type)

    def read_bytes(
        self,
        ref: DurableRef,
        *,
        tenant_id: str,
        workflow_id: str,
        now_ns: int | None = None,
    ) -> bytes:
        self._reject_unbackfillable(ref)
        metadata = self._load_metadata(ref.locator)
        self._assert_scope(ref, metadata, tenant_id=tenant_id, workflow_id=workflow_id)
        self._assert_live(ref, metadata, now_ns=now_ns)
        key_id = ref.key_id or metadata.key_id
        key_version = ref.key_version or metadata.key_version
        key = self.keyring.resolve(key_id, key_version)
        data_path = self._data_path(ref.locator)
        if not data_path.exists():
            self._trace("read", metadata, "denied", "bytes missing")
            raise PayloadTombstonedError("Stored payload bytes are absent")
        plaintext = _decrypt(data_path.read_bytes(), key.material)
        if _digest(plaintext) != ref.digest:
            self._trace("read", metadata, "denied", "digest mismatch")
            raise DigestMismatchError("Stored payload digest does not match ref")
        self._trace("read", metadata, "allowed", "bytes decrypted")
        return plaintext

    def delete_bytes(
        self,
        ref: DurableRef,
        *,
        tenant_id: str,
        workflow_id: str,
        now_ns: int | None = None,
    ) -> DurableRef:
        self._reject_unbackfillable(ref)
        metadata = self._load_metadata(ref.locator)
        self._assert_scope(ref, metadata, tenant_id=tenant_id, workflow_id=workflow_id)
        if ref.is_legal_hold or metadata.legal_hold:
            self._trace("delete", metadata, "denied", "legal hold active")
            raise LegalHoldError("Legal-hold payload bytes cannot be deleted")

        tombstone_ns = time.time_ns() if now_ns is None else now_ns
        data_path = self._data_path(ref.locator)
        if data_path.exists():
            data_path.unlink()
        tombstoned = StoredPayloadMetadata(
            locator=metadata.locator,
            tenant_id=metadata.tenant_id,
            workflow_id=metadata.workflow_id,
            digest=metadata.digest,
            size_bytes=metadata.size_bytes,
            key_id=metadata.key_id,
            key_version=metadata.key_version,
            created_at_ns=metadata.created_at_ns,
            expires_at_ns=metadata.expires_at_ns,
            legal_hold=metadata.legal_hold,
            tombstoned_at_ns=tombstone_ns,
            schema_version=metadata.schema_version,
        )
        _atomic_write_text(
            self._metadata_path(ref.locator),
            canonical_json(tombstoned.to_dict()),
        )
        self._trace("delete", tombstoned, "tombstoned", "bytes deleted")
        return self._ref_from_metadata(
            tombstoned,
            media_type=ref.media_type,
            extra_metadata=dict(ref.metadata),
        )

    def metadata_for_ref(self, ref: DurableRef) -> StoredPayloadMetadata:
        self._reject_unbackfillable(ref)
        return self._load_metadata(ref.locator)

    def _data_path(self, locator: str) -> Path:
        _validate_locator(locator)
        return self.root / "objects" / f"{locator}.bin"

    def _metadata_path(self, locator: str) -> Path:
        _validate_locator(locator)
        return self.root / "objects" / f"{locator}.json"

    def _load_metadata(self, locator: str) -> StoredPayloadMetadata:
        path = self._metadata_path(locator)
        if not path.exists():
            raise PayloadTombstonedError("Stored payload metadata is absent")
        return StoredPayloadMetadata.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def _assert_scope(
        self,
        ref: DurableRef,
        metadata: StoredPayloadMetadata,
        *,
        tenant_id: str,
        workflow_id: str,
    ) -> None:
        if ref.tenant_id != tenant_id or metadata.tenant_id != tenant_id:
            self._trace("scope_check", metadata, "denied", "tenant mismatch")
            raise TenantIsolationError("DurableRef tenant does not match caller")
        if ref.workflow_id != workflow_id or metadata.workflow_id != workflow_id:
            self._trace("scope_check", metadata, "denied", "workflow mismatch")
            raise TenantIsolationError("DurableRef workflow does not match caller")

    def _assert_live(
        self,
        ref: DurableRef,
        metadata: StoredPayloadMetadata,
        *,
        now_ns: int | None,
    ) -> None:
        if ref.is_tombstoned or metadata.tombstoned_at_ns is not None:
            self._trace("read", metadata, "denied", "tombstoned")
            raise PayloadTombstonedError("Stored payload bytes are tombstoned")
        if metadata.expires_at_ns is not None:
            now = time.time_ns() if now_ns is None else now_ns
            if now > metadata.expires_at_ns:
                self._trace("read", metadata, "denied", "expired")
                raise PayloadExpiredError("Stored payload bytes have expired")

    def _reject_unbackfillable(self, ref: DurableRef) -> None:
        if ref.metadata.get("legacy_history") == "unbackfillable" or ref.metadata.get(
            "legacy_history_unbackfillable"
        ):
            raise LegacyHistoryUnbackfillableError(
                "Legacy history has no recoverable stored bytes"
            )

    def _ref_from_metadata(
        self,
        stored_metadata: StoredPayloadMetadata,
        *,
        media_type: str,
        extra_metadata: dict[str, Any] | None = None,
    ) -> DurableRef:
        durable_metadata = {
            "ledger_payload_store_schema": stored_metadata.schema_version,
        }
        if extra_metadata is not None:
            durable_metadata.update(extra_metadata)
        return DurableRef(
            store_id=self.store_id,
            locator=stored_metadata.locator,
            digest=stored_metadata.digest,
            media_type=media_type,
            size_bytes=stored_metadata.size_bytes,
            encryption_scope=EncryptionScope.TENANT_KEY,
            access_scope=AccessScope.WORKFLOW,
            retention_class=(
                RetentionClass.LEGAL_HOLD if stored_metadata.legal_hold else RetentionClass.RUN
            ),
            tenant_id=stored_metadata.tenant_id,
            workflow_id=stored_metadata.workflow_id,
            key_id=stored_metadata.key_id,
            key_version=stored_metadata.key_version,
            created_at_ns=stored_metadata.created_at_ns,
            expires_at_ns=stored_metadata.expires_at_ns,
            legal_hold=stored_metadata.legal_hold,
            tombstoned_at_ns=stored_metadata.tombstoned_at_ns,
            metadata=durable_metadata,
        )

    def _trace(
        self,
        event_type: str,
        metadata: StoredPayloadMetadata,
        outcome: str,
        reason: str,
    ) -> None:
        if self.trace is None:
            return
        self.trace.append(
            LedgerTraceEvent(
                event_type=event_type,
                tenant_id=metadata.tenant_id,
                workflow_id=metadata.workflow_id,
                locator=metadata.locator,
                outcome=outcome,
                reason=reason,
                key_id=metadata.key_id,
                key_version=metadata.key_version,
                ref_digest=metadata.digest,
            )
        )


def _digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _new_locator() -> str:
    return uuid.uuid4().hex


def _validate_locator(locator: str) -> None:
    if not locator or "/" in locator or "\\" in locator or locator in {".", ".."}:
        raise ValueError("Invalid ledger payload locator")


def _expiry_from_policy(
    policy: RetentionPayloadPolicy, created_at_ns: int
) -> int | None:
    if policy.legal_hold or policy.retention_mode == RetentionMode.LEGAL_HOLD:
        return None
    seconds = policy.effective_retention_seconds
    if seconds < 0:
        return None
    return created_at_ns + seconds * 1_000_000_000


def _encrypt(data: bytes, material: bytes) -> bytes:
    nonce = os.urandom(16)
    stream = _key_stream(material, nonce, len(data))
    ciphertext = bytes(left ^ right for left, right in zip(data, stream))
    tag = hmac.new(material, nonce + ciphertext, hashlib.sha256).digest()
    return _CIPHERTEXT_PREFIX + nonce + tag + ciphertext


def _decrypt(encoded: bytes, material: bytes) -> bytes:
    if not encoded.startswith(_CIPHERTEXT_PREFIX):
        raise DigestMismatchError("Stored payload ciphertext header is invalid")
    body = encoded[len(_CIPHERTEXT_PREFIX):]
    nonce = body[:16]
    tag = body[16:48]
    ciphertext = body[48:]
    expected = hmac.new(material, nonce + ciphertext, hashlib.sha256).digest()
    if not hmac.compare_digest(tag, expected):
        raise DigestMismatchError("Stored payload ciphertext tag is invalid")
    stream = _key_stream(material, nonce, len(ciphertext))
    return bytes(left ^ right for left, right in zip(ciphertext, stream))


def _key_stream(material: bytes, nonce: bytes, size: int) -> bytes:
    chunks: list[bytes] = []
    counter = 0
    while sum(len(chunk) for chunk in chunks) < size:
        chunks.append(
            hmac.new(
                material,
                nonce + counter.to_bytes(8, "big"),
                hashlib.sha256,
            ).digest()
        )
        counter += 1
    return b"".join(chunks)[:size]


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def _atomic_write_text(path: Path, data: str) -> None:
    tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    tmp.write_text(data, encoding="utf-8")
    os.replace(tmp, path)


__all__ = [
    "DigestMismatchError",
    "FileBackedLedgerPayloadStore",
    "KeyUnavailableError",
    "LEDGER_PAYLOAD_STORE_SCHEMA_VERSION",
    "LegacyHistoryUnbackfillableError",
    "LedgerPayloadStoreError",
    "LegalHoldError",
    "LocalPayloadKey",
    "LocalPayloadKeyring",
    "PayloadExpiredError",
    "PayloadTombstonedError",
    "StoredPayloadMetadata",
    "TenantIsolationError",
]
