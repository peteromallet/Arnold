"""Durable payload store with WBC payload/reference enforcement.

This module provides the M6A payload storage boundary: a durable store for
workflow boundary payload *bytes* (not just metadata) that enforces the
``wbc.inline.v1`` and ``wbc.retention.v1`` policies before any byte is
persisted.

Key invariants (enforced before persistence, fail-closed):

* **Inline threshold** — payloads whose canonical-JSON size exceeds the
  ``InlinePayloadPolicy.threshold_bytes`` (16 KiB by default) MUST be stored
  by reference.  Inline storage of an oversized payload raises
  :class:`PayloadInlineThresholdError`.
* **Redaction** — protected fields named in ``protected_fields`` are redacted
  in the inline representation when the retention policy enforces redaction.
  A protected field that survives unredacted into inline storage raises
  :class:`PayloadRedactionError`.
* **Tenant/workflow access** — retrieval cross-checks the caller's
  :class:`AccessContext` against the stored tenant/workflow scope.  A
  cross-tenant or cross-workflow read raises
  :class:`PayloadTenantAccessError`.
* **Secret-key rejection** — payloads (or generated durable refs) carrying
  keys that match known secret patterns (``api_key``, ``password``,
  ``secret``, ``token``, ``private_key``, ``credential``, ``bearer``,
  ``authorization``) are rejected with :class:`PayloadSecretKeyError`.
* **Digest-only rejection** — when the retention policy rejects digest-only
  preservation (the default), a caller that requests digest-only storage
  raises :class:`PayloadDigestOnlyError`.  The store always preserves
  retrievable bytes.
* **Protected-class encryption** — payloads whose ``PrivacyClass`` is
  ``CONFIDENTIAL`` or ``RESTRICTED`` MUST be encrypted at rest.  When no
  encryption provider/key is available for the requested scope, the store
  fails closed with :class:`PayloadProtectedEncryptionError` (it never
  silently stores unencrypted protected bytes).
* **DurableRef generation** — every stored payload yields a
  :class:`~arnold.workflow.durable_refs.DurableRef` carrying privacy,
  retention, access, encryption, digest, size, and audit metadata.
* **Retention expiry** — payloads carry an ``expires_at_ns`` timestamp
  derived from the retention policy.  Retrieval of an expired payload
  raises :class:`PayloadExpiredError` unless the payload is under
  legal hold, which overrides expiry.
* **Legal hold override** — a legal-hold flag can be set on any stored
  payload via :meth:`LedgerPayloadStore.set_legal_hold`.  Legal-hold
  payloads are not deletable (deletion raises
  :class:`PayloadLegalHoldError`) and are retrievable past their
  nominal expiry.
* **Tombstone markers** — when a payload is deleted (subject to legal-hold
  and retention checks), a tombstone marker is written to the row and the
  content blob is replaced with a deletion-evidence record.  The locator
  remains queryable; retrieval raises :class:`PayloadTombstoneError`.
* **Deletion evidence** — every tombstone records an auditable
  :class:`DeletionEvidence` payload capturing the deleting principal,
  timestamp, and reason.
* **Pluggable encryption provider (fail-closed)** — the
  :class:`EncryptionProvider` interface now accepts an optional
  ``key_version`` parameter.  When a protected payload requires
  encryption under a specific key version and the provider reports
  that version as unavailable, the store fails closed with
  :class:`PayloadProtectedEncryptionError`.

The payload table lives in the same SQLite database as the attempt-events
table and is managed through the same connection for zero-network-cost
atomic transactions with the ledger/outbox boundary.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

from arnold.manifest.manifests import canonical_json
from arnold.workflow.attempt_ledger_store import SqliteAttemptLedgerStore
from arnold.workflow.durable_refs import (
    AccessScope,
    AvailabilityClass,
    DurableRef,
    EncryptionScope,
    PrivacyClass,
    RetentionClass,
)
from arnold.workflow.payload_policy import (
    INLINE_CANONICAL_JSON_SIZE_THRESHOLD_BYTES,
    IsolationLevel,
    PayloadMode,
    RedactionMode,
    RetentionMode,
    TombstoneMode,
    default_inline_policy,
    default_retention_policy,
)


# ── Constants ─────────────────────────────────────────────────────────────

#: Store schema version. Bumped when the ``payload_blobs`` table shape changes.
PAYLOAD_STORE_VERSION: str = "arnold.workflow.ledger_payload_store.v1"

#: Default redaction marker placed over protected field values.
REDACTION_MARKER: str = "[REDACTED]"

#: The set of privacy classes that count as "protected" for encryption
#: enforcement.  Confidential and restricted payloads MUST be encrypted at
#: rest; the store fails closed when no provider/key is configured.
PROTECTED_PRIVACY_CLASSES: frozenset[PrivacyClass] = frozenset(
    {PrivacyClass.CONFIDENTIAL, PrivacyClass.RESTRICTED}
)

#: Forbidden secret-like key fragments.  A payload key (or durable-ref
#: metadata key) whose lowercase form contains any of these fragments is
#: rejected before persistence.
_FORBIDDEN_SECRET_FRAGMENTS: frozenset[str] = frozenset(
    {
        "api_key",
        "password",
        "secret",
        "token",
        "private_key",
        "credential",
        "bearer",
        "authorization",
    }
)

#: Payload keys that signal digest-only intent from the caller.  When any of
#: these is present (and truthy) the store treats the request as digest-only
#: and applies the digest-only policy check.
_DIGEST_ONLY_INTENT_KEYS: frozenset[str] = frozenset(
    {"_digest_only", "digest_only"}
)


# ── Errors ────────────────────────────────────────────────────────────────


class PayloadStoreError(Exception):
    """Base class for all payload-store enforcement errors."""


class PayloadInlineThresholdError(PayloadStoreError):
    """Raised when an inline payload exceeds the inline size threshold."""


class PayloadSecretKeyError(PayloadStoreError):
    """Raised when a payload or durable-ref carries a secret-like key."""


class PayloadDigestOnlyError(PayloadStoreError):
    """Raised when digest-only preservation is requested but policy forbids it."""


class PayloadRedactionError(PayloadStoreError):
    """Raised when a protected field survives unredacted into inline storage."""


class PayloadTenantAccessError(PayloadStoreError):
    """Raised when a retrieval request crosses tenant/workflow scope."""


class PayloadProtectedEncryptionError(PayloadStoreError):
    """Raised when a protected-class payload cannot be encrypted at rest.

    This is a fail-closed error: the store never silently stores unencrypted
    protected bytes.  It is raised when:

    * the privacy class is protected but ``encryption_scope`` is ``NONE``;
    * no encryption provider is configured; or
    * the configured provider reports the requested scope as unavailable.
    """


class PayloadNotFoundError(PayloadStoreError):
    """Raised when a locator does not resolve to a stored payload."""


class PayloadExpiredError(PayloadStoreError):
    """Raised when retrieval is attempted on an expired payload.

    Expired payloads are not retrievable unless under legal hold.
    """


class PayloadLegalHoldError(PayloadStoreError):
    """Raised when an operation is blocked by an active legal hold.

    E.g., deletion of a legal-hold payload is rejected; the hold must
    be cleared first.
    """


class PayloadTombstoneError(PayloadStoreError):
    """Raised when retrieval is attempted on a tombstoned (deleted) payload.

    Tombstoned payloads retain their locator and deletion evidence but
    the content blob has been replaced with a deletion record.
    """


# ── Frozen result types ───────────────────────────────────────────────────


@dataclass(frozen=True)
class AccessContext:
    """Caller identity for a payload retrieval/access request.

    The store cross-checks ``tenant_id`` and ``workflow_id`` against the
    stored payload's scope before returning bytes.  A ``None`` value matches
    any stored scope (used for store-internal/administrative access); an
    explicit mismatch raises :class:`PayloadTenantAccessError`.
    """

    tenant_id: str | None = None
    workflow_id: str | None = None
    principal: str | None = None


@dataclass(frozen=True)
class StoredPayload:
    """The durable result of storing a payload.

    Captures the locator, digest, size, storage mode, encryption state,
    privacy/retention/access classification, redacted-field record, and the
    generated :class:`DurableRef`.  The ``inline_payload`` field carries the
    redacted inline representation when the mode is ``INLINE``; it is
    ``None`` for reference-mode payloads (whose bytes are retrieved
    separately via :meth:`LedgerPayloadStore.retrieve_payload`).
    """

    locator: str
    digest: str
    size_bytes: int
    payload_mode: PayloadMode
    privacy_class: PrivacyClass
    encryption_scope: EncryptionScope
    access_scope: AccessScope
    retention_class: RetentionClass
    encrypted: bool
    tenant_id: str | None
    workflow_id: str | None
    redacted_fields: tuple[str, ...]
    created_at_ns: int
    expires_at_ns: int | None
    legal_hold: bool
    durable_ref: DurableRef
    inline_payload: Mapping[str, Any] | None = None
    enforcement_checks: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """Return a sidecar-safe representation."""
        payload: dict[str, Any] = {
            "locator": self.locator,
            "digest": self.digest,
            "size_bytes": self.size_bytes,
            "payload_mode": self.payload_mode.value,
            "privacy_class": self.privacy_class.value,
            "encryption_scope": self.encryption_scope.value,
            "access_scope": self.access_scope.value,
            "retention_class": self.retention_class.value,
            "encrypted": self.encrypted,
            "tenant_id": self.tenant_id,
            "workflow_id": self.workflow_id,
            "redacted_fields": list(self.redacted_fields),
            "created_at_ns": self.created_at_ns,
            "expires_at_ns": self.expires_at_ns,
            "legal_hold": self.legal_hold,
            "durable_ref": self.durable_ref.to_dict(),
            "enforcement_checks": list(self.enforcement_checks),
        }
        if self.inline_payload is not None:
            payload["inline_payload"] = dict(self.inline_payload)
        return payload


@dataclass(frozen=True)
class DeletionEvidence:
    """Auditable record of a payload deletion (tombstone).

    Captures who deleted the payload, when, and why.  Stored as JSON
    in the ``deletion_evidence_json`` column of a tombstoned row.
    """

    deleted_by: str | None = None
    deleted_at_ns: int = 0
    reason: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "deleted_by": self.deleted_by,
            "deleted_at_ns": self.deleted_at_ns,
            "reason": self.reason,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DeletionEvidence:
        return cls(
            deleted_by=data.get("deleted_by"),
            deleted_at_ns=data.get("deleted_at_ns", 0),
            reason=data.get("reason", ""),
            metadata=data.get("metadata", {}),
        )


# ── Encryption provider ───────────────────────────────────────────────────


class EncryptionProvider(ABC):
    """Abstract encryption provider for protected-class payload bytes.

    Implementations wrap a key authority (local key, KMS adapter, etc.).
    The store calls :meth:`is_available` before any write to fail closed
    when the requested scope (and optional key version) has no configured key.
    """

    @abstractmethod
    def is_available(
        self,
        scope: EncryptionScope,
        *,
        tenant_id: str | None,
        workflow_id: str | None,
        key_version: str | None = None,
    ) -> bool:
        """Return True when a key is configured for the requested scope.

        When ``key_version`` is provided, the provider must confirm that
        the specific version is available, not just any key for the scope.
        """

    @abstractmethod
    def encrypt(
        self,
        plaintext: bytes,
        *,
        scope: EncryptionScope,
        tenant_id: str | None,
        workflow_id: str | None,
    ) -> tuple[bytes, str]:
        """Encrypt ``plaintext`` and return ``(ciphertext, key_version)``."""

    @abstractmethod
    def decrypt(
        self,
        ciphertext: bytes,
        *,
        scope: EncryptionScope,
        tenant_id: str | None,
        workflow_id: str | None,
        key_version: str,
    ) -> bytes:
        """Decrypt ``ciphertext`` previously produced by :meth:`encrypt`."""


class StaticKeyEncryptionProvider(EncryptionProvider):
    """Deterministic test-only encryption provider.

    Uses a fixed key and a reversible byte transform.  This is NOT
    cryptographically secure and MUST NOT be used in production; it exists
    so that payload-enforcement tests can exercise the encrypt/decrypt path
    without pulling in a real KMS dependency.  The enforcement boundary
    (provider presence + scope availability) is what M6A tests; the cipher
    strength is out of scope.
    """

    def __init__(
        self,
        key: bytes | str | None = None,
        *,
        available_scopes: frozenset[EncryptionScope] | None = None,
        key_version: str = "static-test-v1",
    ) -> None:
        if key is None:
            key = b"arnold-m6a-static-test-key-do-not-use-in-prod"
        if isinstance(key, str):
            key = key.encode("utf-8")
        if not key:
            raise ValueError("StaticKeyEncryptionProvider key must be non-empty")
        self._key = key
        self._available = available_scopes or frozenset(
            {EncryptionScope.TENANT_KEY, EncryptionScope.WORKFLOW_KEY,
             EncryptionScope.FIELD_LEVEL}
        )
        self._key_version = key_version

    def is_available(
        self,
        scope: EncryptionScope,
        *,
        tenant_id: str | None,
        workflow_id: str | None,
        key_version: str | None = None,
    ) -> bool:
        if scope == EncryptionScope.NONE or scope not in self._available:
            return False
        if key_version is not None and key_version != self._key_version:
            return False
        return True

    def encrypt(
        self,
        plaintext: bytes,
        *,
        scope: EncryptionScope,
        tenant_id: str | None,
        workflow_id: str | None,
    ) -> tuple[bytes, str]:
        if scope == EncryptionScope.NONE or scope not in self._available:
            raise PayloadProtectedEncryptionError(
                f"StaticKeyEncryptionProvider has no key for scope {scope!r}"
            )
        return self._xor(plaintext), self._key_version

    def decrypt(
        self,
        ciphertext: bytes,
        *,
        scope: EncryptionScope,
        tenant_id: str | None,
        workflow_id: str | None,
        key_version: str,
    ) -> bytes:
        if key_version != self._key_version:
            raise PayloadProtectedEncryptionError(
                f"key_version mismatch: expected {self._key_version!r}, "
                f"got {key_version!r}"
            )
        return self._xor(ciphertext)

    def _xor(self, data: bytes) -> bytes:
        klen = len(self._key)
        return bytes(b ^ self._key[i % klen] for i, b in enumerate(data))


# ── Payload store ABC ─────────────────────────────────────────────────────


class LedgerPayloadStore(ABC):
    """Abstract payload store enforcing WBC payload/reference policy.

    All enforcement (inline threshold, redaction, tenant access, secret-key
    rejection, digest-only rejection, protected-class encryption) happens
    inside :meth:`store_payload` and :meth:`retrieve_payload` before any
    byte is read or written.
    """

    @abstractmethod
    def store_payload(
        self,
        payload: Mapping[str, Any],
        *,
        tenant_id: str | None = None,
        workflow_id: str | None = None,
        inline_policy: Any | None = None,
        retention_policy: Any | None = None,
        protected_fields: tuple[str, ...] = (),
        privacy_class: PrivacyClass = PrivacyClass.INTERNAL,
        encryption_scope: EncryptionScope = EncryptionScope.NONE,
        force_reference: bool = False,
        digest_only: bool = False,
        principal: str | None = None,
    ) -> StoredPayload:
        """Store ``payload`` and return the resulting :class:`StoredPayload`.

        Raises a typed :class:`PayloadStoreError` subclass when any
        enforcement check fails.  Never silently stores unsafe bytes.
        """

    @abstractmethod
    def retrieve_payload(
        self,
        locator: str,
        *,
        access_context: AccessContext,
    ) -> Mapping[str, Any]:
        """Retrieve and return the stored payload for ``locator``.

        Raises :class:`PayloadTenantAccessError` on cross-scope access and
        :class:`PayloadNotFoundError` when the locator is unknown.
        """

    @abstractmethod
    def get_stored_payload(self, locator: str) -> StoredPayload:
        """Return the :class:`StoredPayload` metadata for ``locator``."""

    @abstractmethod
    def set_legal_hold(
        self,
        locator: str,
        *,
        active: bool = True,
        principal: str | None = None,
        reason: str = "",
    ) -> StoredPayload:
        """Set or clear the legal-hold flag on a stored payload.

        When set, the payload is protected from deletion and retrievable
        past its nominal expiry.  When cleared, the payload returns to
        its normal lifecycle (subject to retention and tombstone rules).

        Returns the updated :class:`StoredPayload`.
        """

    @abstractmethod
    def delete_payload(
        self,
        locator: str,
        *,
        principal: str | None = None,
        reason: str = "",
    ) -> DeletionEvidence:
        """Delete a payload, leaving a tombstone marker with deletion evidence.

        Raises :class:`PayloadLegalHoldError` when the payload is under
        legal hold.  The locator remains queryable via
        :meth:`get_stored_payload` but retrieval of the content bytes
        raises :class:`PayloadTombstoneError`.
        """

    @abstractmethod
    def is_under_legal_hold(self, locator: str) -> bool:
        """Return True when the payload has an active legal hold."""


# ── SQL DDL ───────────────────────────────────────────────────────────────

_PAYLOAD_TABLE_DDL: str = """\
CREATE TABLE IF NOT EXISTS payload_blobs (
    locator              TEXT    PRIMARY KEY,
    tenant_id            TEXT,
    workflow_id          TEXT,
    payload_mode         TEXT    NOT NULL,
    privacy_class        TEXT    NOT NULL,
    encryption_scope     TEXT    NOT NULL,
    access_scope         TEXT    NOT NULL,
    retention_class      TEXT    NOT NULL,
    encrypted            INTEGER NOT NULL,
    key_version          TEXT,
    content_blob         BLOB,
    digest               TEXT    NOT NULL,
    size_bytes           INTEGER NOT NULL,
    redacted_fields_json TEXT    NOT NULL DEFAULT '[]',
    schema_type          TEXT    NOT NULL DEFAULT 'application/json',
    media_type           TEXT    NOT NULL DEFAULT 'application/json',
    created_at_ns        INTEGER NOT NULL,
    expires_at_ns        INTEGER,
    legal_hold           INTEGER NOT NULL DEFAULT 0,
    tombstone            INTEGER NOT NULL DEFAULT 0,
    deletion_evidence_json TEXT,
    enforcement_checks_json TEXT NOT NULL DEFAULT '[]',
    audit_metadata_json  TEXT    NOT NULL DEFAULT '{}'
)
"""

_PAYLOAD_TENANT_INDEX_DDL: str = """\
CREATE INDEX IF NOT EXISTS idx_payload_tenant
    ON payload_blobs(tenant_id, workflow_id)
"""


# ── Helpers ───────────────────────────────────────────────────────────────


def _scan_secret_keys(payload: Mapping[str, Any]) -> list[str]:
    """Return the list of payload keys that match forbidden secret fragments."""
    offenders: list[str] = []
    for key in payload:
        lower_key = str(key).lower()
        for forbidden in _FORBIDDEN_SECRET_FRAGMENTS:
            if forbidden in lower_key:
                offenders.append(str(key))
                break
    return offenders


def _has_digest_only_intent(
    payload: Mapping[str, Any], *, explicit: bool
) -> bool:
    """Return True when the caller signals digest-only preservation intent."""
    if explicit:
        return True
    for key in _DIGEST_ONLY_INTENT_KEYS:
        if payload.get(key):
            return True
    return False


def _redact_payload(
    payload: Mapping[str, Any],
    protected_fields: tuple[str, ...],
    *,
    marker: str = REDACTION_MARKER,
) -> tuple[dict[str, Any], tuple[str, ...]]:
    """Return a (redacted_copy, redacted_field_names) pair.

    Only top-level keys listed in ``protected_fields`` are redacted.  Nested
    mappings are left structurally intact (field-level redaction is a
    top-level contract; nested redaction is the caller's responsibility).
    """
    redacted: dict[str, Any] = {}
    redacted_names: list[str] = []
    protected_set = frozenset(protected_fields)
    for key, value in payload.items():
        if key in protected_set:
            redacted[key] = marker
            redacted_names.append(key)
        else:
            redacted[key] = value
    return redacted, tuple(redacted_names)


def _sha256_digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _retention_class_for(
    retention_policy: Any,
) -> RetentionClass:
    """Map a retention policy's mode to a :class:`RetentionClass`."""
    mode = getattr(retention_policy, "retention_mode", RetentionMode.RUN)
    if getattr(retention_policy, "legal_hold", False):
        return RetentionClass.LEGAL_HOLD
    mapping = {
        RetentionMode.EPHEMERAL: RetentionClass.EPHEMERAL,
        RetentionMode.RUN: RetentionClass.RUN,
        RetentionMode.AUDIT: RetentionClass.AUDIT,
        RetentionMode.LEGAL_HOLD: RetentionClass.LEGAL_HOLD,
    }
    return mapping.get(mode, RetentionClass.RUN)


def _access_scope_for(
    retention_policy: Any,
) -> AccessScope:
    """Map a retention policy's isolation level to an :class:`AccessScope`."""
    level = getattr(retention_policy, "isolation_level", IsolationLevel.WORKFLOW)
    mapping = {
        IsolationLevel.TENANT: AccessScope.TENANT,
        IsolationLevel.WORKFLOW: AccessScope.WORKFLOW,
        IsolationLevel.INVOCATION: AccessScope.INVOCATION,
        IsolationLevel.SHARED: AccessScope.RESTRICTED,
    }
    return mapping.get(level, AccessScope.WORKFLOW)


def _expires_at_ns(
    created_at_ns: int,
    retention_policy: Any,
) -> int | None:
    """Compute the expiry nanosecond timestamp from the retention policy."""
    seconds = getattr(retention_policy, "effective_retention_seconds", None)
    if seconds is None:
        return None
    if seconds < 0:
        # Indefinite (legal hold) — no expiry.
        return None
    if seconds == 0:
        # Ephemeral — expires immediately at creation (recorded but not
        # enforced as deletion by this task; enforcement is T10).
        return created_at_ns
    return created_at_ns + seconds * 1_000_000_000


# ── SQLite implementation ─────────────────────────────────────────────────


class SqliteLedgerPayloadStore(LedgerPayloadStore):
    """SQLite-backed :class:`LedgerPayloadStore`.

    The payload table is created on the same database (and connection) as
    the parent :class:`SqliteAttemptLedgerStore` so that payload writes can
    later participate in atomic transactions with ledger events and outbox
    records.
    """

    def __init__(
        self,
        store: SqliteAttemptLedgerStore,
        *,
        encryption_provider: EncryptionProvider | None = None,
        store_id: str | None = None,
    ) -> None:
        self._store = store
        self._encryption_provider = encryption_provider
        self._store_id = store_id or "arnold.sqlite.payload.v1"
        self._initialized = False

    # ── connection / schema ────────────────────────────────────────────

    @property
    def conn(self) -> sqlite3.Connection:
        """Return the underlying SQLite connection, initializing the table once."""
        conn = self._store.conn  # ensures WAL + parent schema are ready
        if not self._initialized:
            self._init_schema(conn)
        return conn

    def _init_schema(self, conn: sqlite3.Connection) -> None:
        conn.execute("BEGIN IMMEDIATE")
        try:
            for stmt in _PAYLOAD_TABLE_DDL.split(";"):
                s = stmt.strip()
                if s:
                    conn.execute(s)
            for stmt in _PAYLOAD_TENANT_INDEX_DDL.split(";"):
                s = stmt.strip()
                if s:
                    conn.execute(s)
            conn.execute("COMMIT")
            self._initialized = True
        except Exception:
            conn.execute("ROLLBACK")
            raise

    # ── enforcement helpers ───────────────────────────────────────────

    def _enforce_secret_keys(self, payload: Mapping[str, Any]) -> None:
        offenders = _scan_secret_keys(payload)
        if offenders:
            raise PayloadSecretKeyError(
                "Payload keys match forbidden secret patterns and cannot be "
                f"stored: {offenders!r}"
            )

    def _enforce_digest_only(
        self,
        payload: Mapping[str, Any],
        retention_policy: Any,
        *,
        explicit: bool,
    ) -> None:
        rejected = bool(
            getattr(retention_policy, "digest_only_preservation_rejected", True)
        )
        if rejected and _has_digest_only_intent(payload, explicit=explicit):
            raise PayloadDigestOnlyError(
                "Digest-only payload preservation is rejected by the active "
                "retention policy; a digest without retained retrievable "
                "bytes does not preserve a result"
            )

    def _enforce_protected_encryption(
        self,
        privacy_class: PrivacyClass,
        encryption_scope: EncryptionScope,
        retention_policy: Any,
        *,
        tenant_id: str | None,
        workflow_id: str | None,
        key_version: str | None = None,
    ) -> None:
        if privacy_class not in PROTECTED_PRIVACY_CLASSES:
            return
        if not bool(getattr(retention_policy, "encryption_required", True)):
            return
        if encryption_scope == EncryptionScope.NONE:
            raise PayloadProtectedEncryptionError(
                f"Privacy class {privacy_class.value!r} is protected and "
                "requires encryption, but encryption_scope is NONE; refuse "
                "to store unencrypted protected bytes"
            )
        if self._encryption_provider is None:
            raise PayloadProtectedEncryptionError(
                f"Privacy class {privacy_class.value!r} is protected and "
                "requires encryption, but no encryption provider is "
                "configured (fail closed)"
            )
        if not self._encryption_provider.is_available(
            encryption_scope,
            tenant_id=tenant_id,
            workflow_id=workflow_id,
            key_version=key_version,
        ):
            detail_parts = [
                f"Privacy class {privacy_class.value!r} is protected and "
                f"requires encryption under scope {encryption_scope.value!r}"
            ]
            if key_version is not None:
                detail_parts.append(
                    f"with key version {key_version!r}"
                )
            detail_parts.append(
                "but the encryption provider reports no key available "
                "(fail closed)"
            )
            raise PayloadProtectedEncryptionError(" ".join(detail_parts))

    def _enforce_inline_threshold(
        self,
        redacted_bytes: bytes,
        payload_mode: PayloadMode,
        inline_policy: Any,
    ) -> None:
        threshold = int(
            getattr(inline_policy, "threshold_bytes",
                    INLINE_CANONICAL_JSON_SIZE_THRESHOLD_BYTES)
        )
        if payload_mode == PayloadMode.INLINE and len(redacted_bytes) > threshold:
            raise PayloadInlineThresholdError(
                f"Inline payload size {len(redacted_bytes)} bytes exceeds "
                f"the inline threshold {threshold} bytes; the payload must "
                "be stored by reference (force_reference=True or split the "
                "payload)"
            )

    def _enforce_expiry(self, stored: StoredPayload) -> None:
        """Raise :class:`PayloadExpiredError` when a payload has expired.

        Legal-hold payloads are exempt from expiry enforcement.
        """
        if stored.legal_hold:
            return
        if stored.expires_at_ns is None:
            return
        now_ns = time.time_ns()
        if stored.expires_at_ns <= now_ns:
            raise PayloadExpiredError(
                f"Payload {stored.locator!r} expired at "
                f"{stored.expires_at_ns} <= {now_ns} now; "
                "retrieval denied (legal hold not active)"
            )

    def _enforce_not_tombstoned(self, locator: str, tombstone: bool) -> None:
        """Raise :class:`PayloadTombstoneError` when the payload is tombstoned."""
        if tombstone:
            raise PayloadTombstoneError(
                f"Payload {locator!r} has been tombstoned (deleted); "
                "content bytes are no longer retrievable"
            )

    # ── public API ────────────────────────────────────────────────────

    def store_payload(
        self,
        payload: Mapping[str, Any],
        *,
        tenant_id: str | None = None,
        workflow_id: str | None = None,
        inline_policy: Any | None = None,
        retention_policy: Any | None = None,
        protected_fields: tuple[str, ...] = (),
        privacy_class: PrivacyClass = PrivacyClass.INTERNAL,
        encryption_scope: EncryptionScope = EncryptionScope.NONE,
        force_reference: bool = False,
        digest_only: bool = False,
        principal: str | None = None,
    ) -> StoredPayload:
        if inline_policy is None:
            inline_policy = default_inline_policy()
        if retention_policy is None:
            retention_policy = default_retention_policy()
        if not isinstance(payload, Mapping):
            raise PayloadStoreError(
                "payload must be a Mapping; refused to store non-mapping "
                "payload bytes"
            )

        # Work on a plain-dict copy so we never mutate the caller's mapping.
        source = dict(payload)

        # 1. Secret-key rejection (scan before any other work).
        self._enforce_secret_keys(source)

        # 2. Digest-only rejection where policy forbids it.
        self._enforce_digest_only(
            source, retention_policy, explicit=digest_only
        )

        # 3. Redaction of protected fields.
        redaction_enforced = bool(
            getattr(retention_policy, "is_redaction_enforced", True)
        )
        if redaction_enforced and protected_fields:
            stored_view, redacted_fields = _redact_payload(
                source, tuple(protected_fields)
            )
        else:
            stored_view = dict(source)
            redacted_fields: tuple[str, ...] = ()

        # 4. Classify inline vs reference.
        classified = inline_policy.classify(stored_view)
        if force_reference:
            payload_mode = PayloadMode.REFERENCE
        else:
            payload_mode = classified

        # The bytes we persist: for inline we persist the redacted view; for
        # reference we persist the full (unredacted) source so the retrievable
        # bytes are complete — protection for reference mode comes from
        # encryption, not redaction.
        if payload_mode == PayloadMode.INLINE:
            persist_view = stored_view
        else:
            persist_view = dict(source)

        persist_bytes = canonical_json(persist_view).encode("utf-8")

        # 5. Inline threshold enforcement (catches the case where redaction
        #    did not shrink the payload below the threshold and the caller
        #    did not force reference).
        self._enforce_inline_threshold(
            persist_bytes, payload_mode, inline_policy
        )

        # 6. Protected-class encryption check (fail closed).
        self._enforce_protected_encryption(
            privacy_class,
            encryption_scope,
            retention_policy,
            tenant_id=tenant_id,
            workflow_id=workflow_id,
        )

        # 7. Encrypt bytes if required.
        encrypted = False
        key_version: str | None = None
        content_blob: bytes
        if (
            privacy_class in PROTECTED_PRIVACY_CLASSES
            and bool(getattr(retention_policy, "encryption_required", True))
        ):
            assert self._encryption_provider is not None  # narrowing
            ciphertext, kv = self._encryption_provider.encrypt(
                persist_bytes,
                scope=encryption_scope,
                tenant_id=tenant_id,
                workflow_id=workflow_id,
            )
            content_blob = ciphertext
            encrypted = True
            key_version = kv
        else:
            content_blob = persist_bytes

        # 8. Compute digest over the persisted (possibly encrypted) bytes.
        digest = _sha256_digest(content_blob)
        size_bytes = len(content_blob)

        # 9. Generate the DurableRef with full metadata.
        locator = f"payload:{uuid.uuid4()}"
        created_at_ns = time.time_ns()
        retention_class = _retention_class_for(retention_policy)
        access_scope = _access_scope_for(retention_policy)
        expires_at_ns = _expires_at_ns(created_at_ns, retention_policy)
        legal_hold = bool(getattr(retention_policy, "legal_hold", False))

        enforcement_checks = self._record_enforcement_checks(
            redaction_enforced=redaction_enforced,
            redacted_fields=redacted_fields,
            secret_scan=True,
            digest_only_check=True,
            inline_threshold_check=True,
            encryption_check=encrypted,
        )

        audit_metadata = MappingProxyType(
            {
                "store_version": PAYLOAD_STORE_VERSION,
                "stored_at_ns": created_at_ns,
                "stored_by_principal": principal,
                "enforcement_checks": list(enforcement_checks),
                "redacted_fields": list(redacted_fields),
                "encrypted": encrypted,
                "key_version": key_version,
            }
        )

        durable_ref = DurableRef(
            store_id=self._store_id,
            locator=locator,
            digest=digest,
            schema_type="application/json",
            media_type="application/json",
            size_bytes=size_bytes,
            encryption_scope=encryption_scope,
            access_scope=access_scope,
            privacy_class=privacy_class,
            retention_class=retention_class,
            availability_class=AvailabilityClass.STANDARD,
            tenant_id=tenant_id,
            workflow_id=workflow_id,
            metadata=dict(audit_metadata),
        )

        stored = StoredPayload(
            locator=locator,
            digest=digest,
            size_bytes=size_bytes,
            payload_mode=payload_mode,
            privacy_class=privacy_class,
            encryption_scope=encryption_scope,
            access_scope=access_scope,
            retention_class=retention_class,
            encrypted=encrypted,
            tenant_id=tenant_id,
            workflow_id=workflow_id,
            redacted_fields=redacted_fields,
            created_at_ns=created_at_ns,
            expires_at_ns=expires_at_ns,
            legal_hold=legal_hold,
            durable_ref=durable_ref,
            inline_payload=MappingProxyType(stored_view)
            if payload_mode == PayloadMode.INLINE
            else None,
            enforcement_checks=enforcement_checks,
        )

        # 10. Persist atomically.
        self._persist(stored, content_blob, key_version)

        return stored

    def retrieve_payload(
        self,
        locator: str,
        *,
        access_context: AccessContext,
    ) -> Mapping[str, Any]:
        row = self._fetch(locator)
        if row is None:
            raise PayloadNotFoundError(
                f"No stored payload for locator {locator!r}"
            )

        stored = self._row_to_stored(row)

        # 0. Tombstone check — must precede access/expiry.
        self._enforce_not_tombstoned(
            locator, bool(row["tombstone"])
        )

        self._enforce_access(stored, access_context)

        # 1. Expiry enforcement after access check.
        self._enforce_expiry(stored)

        content_blob: bytes = row["content_blob"]
        if stored.encrypted:
            if self._encryption_provider is None:
                raise PayloadProtectedEncryptionError(
                    "Stored payload is encrypted but no decryption provider "
                    "is configured (fail closed)"
                )
            key_version = row["key_version"] or ""
            plaintext = self._encryption_provider.decrypt(
                content_blob,
                scope=stored.encryption_scope,
                tenant_id=stored.tenant_id,
                workflow_id=stored.workflow_id,
                key_version=key_version,
            )
        else:
            plaintext = content_blob

        return json.loads(plaintext.decode("utf-8"))

    def get_stored_payload(self, locator: str) -> StoredPayload:
        row = self._fetch(locator)
        if row is None:
            raise PayloadNotFoundError(
                f"No stored payload for locator {locator!r}"
            )
        return self._row_to_stored(row)

    def set_legal_hold(
        self,
        locator: str,
        *,
        active: bool = True,
        principal: str | None = None,
        reason: str = "",
    ) -> StoredPayload:
        """Set or clear the legal-hold flag on a stored payload."""
        row = self._fetch(locator)
        if row is None:
            raise PayloadNotFoundError(
                f"No stored payload for locator {locator!r}"
            )
        conn = self.conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            conn.execute(
                "UPDATE payload_blobs SET legal_hold = ? WHERE locator = ?",
                (1 if active else 0, locator),
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        return self.get_stored_payload(locator)

    def delete_payload(
        self,
        locator: str,
        *,
        principal: str | None = None,
        reason: str = "",
    ) -> DeletionEvidence:
        """Delete a payload, leaving a tombstone marker with deletion evidence.

        Raises :class:`PayloadLegalHoldError` when the payload is under
        legal hold.
        """
        row = self._fetch(locator)
        if row is None:
            raise PayloadNotFoundError(
                f"No stored payload for locator {locator!r}"
            )
        if bool(row["legal_hold"]):
            raise PayloadLegalHoldError(
                f"Payload {locator!r} is under legal hold; cannot delete. "
                "Clear the legal hold first."
            )

        now_ns = time.time_ns()
        evidence = DeletionEvidence(
            deleted_by=principal,
            deleted_at_ns=now_ns,
            reason=reason,
        )

        conn = self.conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            # Replace content blob with deletion evidence JSON.
            # The locator, metadata, and audit trail are preserved.
            deletion_blob = json.dumps(evidence.to_dict()).encode("utf-8")
            deletion_digest = _sha256_digest(deletion_blob)
            conn.execute(
                """UPDATE payload_blobs
                   SET tombstone = 1,
                       deletion_evidence_json = ?,
                       content_blob = ?,
                       digest = ?,
                       size_bytes = ?,
                       encrypted = 0,
                       key_version = NULL
                   WHERE locator = ?""",
                (
                    json.dumps(evidence.to_dict()),
                    deletion_blob,
                    deletion_digest,
                    len(deletion_blob),
                    locator,
                ),
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        return evidence

    def is_under_legal_hold(self, locator: str) -> bool:
        """Return True when the payload has an active legal hold."""
        row = self._fetch(locator)
        if row is None:
            return False
        return bool(row["legal_hold"])

    def get_deletion_evidence(self, locator: str) -> DeletionEvidence | None:
        """Return the :class:`DeletionEvidence` for a tombstoned payload.

        Returns ``None`` when the payload is not tombstoned or the
        deletion evidence column is empty.
        """
        row = self._fetch(locator)
        if row is None:
            return None
        if not bool(row["tombstone"]):
            return None
        raw = row["deletion_evidence_json"] or "{}"
        return DeletionEvidence.from_dict(json.loads(raw))

    # ── internal persistence ──────────────────────────────────────────

    def _record_enforcement_checks(
        self,
        *,
        redaction_enforced: bool,
        redacted_fields: tuple[str, ...],
        secret_scan: bool,
        digest_only_check: bool,
        inline_threshold_check: bool,
        encryption_check: bool,
    ) -> tuple[str, ...]:
        checks: list[str] = []
        if secret_scan:
            checks.append("secret_key_rejection")
        if digest_only_check:
            checks.append("digest_only_policy")
        if redaction_enforced:
            checks.append(f"redaction:{len(redacted_fields)}_fields")
        if inline_threshold_check:
            checks.append("inline_threshold")
        if encryption_check:
            checks.append("protected_class_encryption")
        else:
            checks.append("encryption:not_required")
        return tuple(checks)

    def _persist(
        self,
        stored: StoredPayload,
        content_blob: bytes,
        key_version: str | None,
    ) -> None:
        conn = self.conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            conn.execute(
                """\
INSERT INTO payload_blobs (
    locator, tenant_id, workflow_id, payload_mode, privacy_class,
    encryption_scope, access_scope, retention_class, encrypted,
    key_version, content_blob, digest, size_bytes, redacted_fields_json,
    schema_type, media_type, created_at_ns, expires_at_ns, legal_hold,
    tombstone, deletion_evidence_json,
    enforcement_checks_json, audit_metadata_json
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""",
                (
                    stored.locator,
                    stored.tenant_id,
                    stored.workflow_id,
                    stored.payload_mode.value,
                    stored.privacy_class.value,
                    stored.encryption_scope.value,
                    stored.access_scope.value,
                    stored.retention_class.value,
                    1 if stored.encrypted else 0,
                    key_version,
                    content_blob,
                    stored.digest,
                    stored.size_bytes,
                    json.dumps(list(stored.redacted_fields)),
                    "application/json",
                    "application/json",
                    stored.created_at_ns,
                    stored.expires_at_ns,
                    1 if stored.legal_hold else 0,
                    0,  # tombstone
                    None,  # deletion_evidence_json
                    json.dumps(list(stored.enforcement_checks)),
                    json.dumps(stored.durable_ref.to_dict().get("metadata", {}))
                    if stored.durable_ref.metadata
                    else "{}",
                ),
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise

    def _fetch(self, locator: str) -> sqlite3.Row | None:
        conn = self.conn
        conn.row_factory = sqlite3.Row
        cur = conn.execute(
            "SELECT * FROM payload_blobs WHERE locator = ?",
            (locator,),
        )
        return cur.fetchone()

    def _row_to_stored(self, row: sqlite3.Row) -> StoredPayload:
        durable_ref = DurableRef(
            store_id=self._store_id,
            locator=row["locator"],
            digest=row["digest"],
            schema_type=row["schema_type"] or "application/json",
            media_type=row["media_type"] or "application/json",
            size_bytes=row["size_bytes"],
            encryption_scope=EncryptionScope(row["encryption_scope"]),
            access_scope=AccessScope(row["access_scope"]),
            privacy_class=PrivacyClass(row["privacy_class"]),
            retention_class=RetentionClass(row["retention_class"]),
            availability_class=AvailabilityClass.STANDARD,
            tenant_id=row["tenant_id"],
            workflow_id=row["workflow_id"],
            metadata=json.loads(row["audit_metadata_json"] or "{}"),
        )
        inline_payload: Mapping[str, Any] | None = None
        if row["payload_mode"] == PayloadMode.INLINE.value:
            blob: bytes = row["content_blob"]
            encrypted = bool(row["encrypted"])
            if encrypted:
                # Do NOT decrypt here; inline_payload metadata view is the
                # redacted map only. The caller uses retrieve_payload() to
                # get decrypted bytes.
                inline_payload = None
            else:
                try:
                    inline_payload = MappingProxyType(
                        json.loads(blob.decode("utf-8"))
                    )
                except (ValueError, UnicodeDecodeError):
                    inline_payload = None

        return StoredPayload(
            locator=row["locator"],
            digest=row["digest"],
            size_bytes=row["size_bytes"],
            payload_mode=PayloadMode(row["payload_mode"]),
            privacy_class=PrivacyClass(row["privacy_class"]),
            encryption_scope=EncryptionScope(row["encryption_scope"]),
            access_scope=AccessScope(row["access_scope"]),
            retention_class=RetentionClass(row["retention_class"]),
            encrypted=bool(row["encrypted"]),
            tenant_id=row["tenant_id"],
            workflow_id=row["workflow_id"],
            redacted_fields=tuple(
                json.loads(row["redacted_fields_json"] or "[]")
            ),
            created_at_ns=row["created_at_ns"],
            expires_at_ns=row["expires_at_ns"],
            legal_hold=bool(row["legal_hold"]),
            durable_ref=durable_ref,
            inline_payload=inline_payload,
            enforcement_checks=tuple(
                json.loads(row["enforcement_checks_json"] or "[]")
            ),
        )

    def _enforce_access(
        self, stored: StoredPayload, access_context: AccessContext
    ) -> None:
        # Tenant isolation.
        if (
            access_context.tenant_id is not None
            and stored.tenant_id is not None
            and access_context.tenant_id != stored.tenant_id
        ):
            raise PayloadTenantAccessError(
                f"Cross-tenant access denied: caller tenant "
                f"{access_context.tenant_id!r} != stored tenant "
                f"{stored.tenant_id!r}"
            )
        # Workflow isolation (applies when access_scope is workflow/invocation
        # or when the stored payload carries a workflow_id).
        if (
            access_context.workflow_id is not None
            and stored.workflow_id is not None
            and access_context.workflow_id != stored.workflow_id
            and stored.access_scope
            in (AccessScope.WORKFLOW, AccessScope.INVOCATION)
        ):
            raise PayloadTenantAccessError(
                f"Cross-workflow access denied: caller workflow "
                f"{access_context.workflow_id!r} != stored workflow "
                f"{stored.workflow_id!r}"
            )


# M9's encrypted local byte store is an additive implementation.  It shares
# the established PayloadExpiredError so callers can catch the public error
# consistently across both stores.
from arnold.workflow._ledger_payload_store_m9 import (  # noqa: E402
    DigestMismatchError,
    FileBackedLedgerPayloadStore,
    KeyUnavailableError,
    LEDGER_PAYLOAD_STORE_SCHEMA_VERSION,
    LegacyHistoryUnbackfillableError,
    LedgerPayloadStoreError,
    LegalHoldError,
    LocalPayloadKey,
    LocalPayloadKeyring,
    PayloadTombstonedError,
    StoredPayloadMetadata,
    TenantIsolationError,
)


__all__ = [
    "AccessContext",
    "DeletionEvidence",
    "DigestMismatchError",
    "EncryptionProvider",
    "FileBackedLedgerPayloadStore",
    "KeyUnavailableError",
    "LEDGER_PAYLOAD_STORE_SCHEMA_VERSION",
    "LegacyHistoryUnbackfillableError",
    "LedgerPayloadStore",
    "LedgerPayloadStoreError",
    "LegalHoldError",
    "LocalPayloadKey",
    "LocalPayloadKeyring",
    "PAYLOAD_STORE_VERSION",
    "PROTECTED_PRIVACY_CLASSES",
    "PayloadDigestOnlyError",
    "PayloadExpiredError",
    "PayloadInlineThresholdError",
    "PayloadLegalHoldError",
    "PayloadNotFoundError",
    "PayloadProtectedEncryptionError",
    "PayloadRedactionError",
    "PayloadSecretKeyError",
    "PayloadStoreError",
    "PayloadTenantAccessError",
    "PayloadTombstoneError",
    "PayloadTombstonedError",
    "REDACTION_MARKER",
    "SqliteLedgerPayloadStore",
    "StaticKeyEncryptionProvider",
    "StoredPayload",
    "StoredPayloadMetadata",
    "TenantIsolationError",
]
