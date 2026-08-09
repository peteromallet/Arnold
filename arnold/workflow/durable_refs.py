"""Durable object reference schema for workflow boundary contracts.

This module freezes a public schema contract under ``arnold.workflow``.
Every ``DurableRef`` requires retrievable durable object metadata and
rejects digest-only result preservation and secret payloads.

This is schema-only — no I/O, mutation, or runtime effects.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Mapping


# ── Enums ─────────────────────────────────────────────────────────────────


class PrivacyClass(StrEnum):
    """Privacy classification for durable object references."""

    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


class AvailabilityClass(StrEnum):
    """Availability tier for durable object references."""

    IMMEDIATE = "immediate"
    STANDARD = "standard"
    ARCHIVE = "archive"
    COLD = "cold"


class EncryptionScope(StrEnum):
    """Encryption scope for durable object references."""

    NONE = "none"
    TENANT_KEY = "tenant_key"
    WORKFLOW_KEY = "workflow_key"
    FIELD_LEVEL = "field_level"


class RetentionClass(StrEnum):
    """Retention class for durable object references."""

    EPHEMERAL = "ephemeral"
    RUN = "run"
    AUDIT = "audit"
    LEGAL_HOLD = "legal_hold"


class AccessScope(StrEnum):
    """Access scope for durable object references."""

    TENANT = "tenant"
    WORKFLOW = "workflow"
    INVOCATION = "invocation"
    RESTRICTED = "restricted"


# ── Digest validation ─────────────────────────────────────────────────────

_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")

# Forbidden secret-like field keys that must never appear in a DurableRef.
_FORBIDDEN_SECRET_KEYS: frozenset[str] = frozenset(
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


def _require_digest(value: str) -> str:
    """Validate a canonical digest string."""
    if not isinstance(value, str) or not _DIGEST_RE.fullmatch(value):
        raise ValueError(
            f"digest must be 'sha256:' followed by 64 lowercase hex chars, "
            f"got {value!r}"
        )
    return value


def _reject_secret_keys(metadata: Mapping[str, Any]) -> None:
    """Reject any metadata keys that could carry secrets."""
    for key in metadata:
        lower_key = key.lower()
        for forbidden in _FORBIDDEN_SECRET_KEYS:
            if forbidden in lower_key:
                raise ValueError(
                    f"DurableRef metadata key {key!r} matches forbidden "
                    f"secret pattern {forbidden!r}; durable refs must not "
                    f"carry secrets"
                )


def _freeze_mapping(value: Mapping[str, Any]) -> Mapping[str, Any]:
    return MappingProxyType(
        {str(key): _freeze_value(subvalue) for key, subvalue in value.items()}
    )


def _freeze_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _freeze_mapping(value)
    if isinstance(value, list):
        return tuple(_freeze_value(item) for item in value)
    if isinstance(value, tuple):
        return tuple(_freeze_value(item) for item in value)
    return value


def _thaw_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _thaw_value(subvalue) for key, subvalue in value.items()}
    if isinstance(value, tuple):
        return [_thaw_value(item) for item in value]
    return value


# ── DurableRef ────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class DurableRef:
    """A durable object reference with required retrievability metadata.

    Every ``DurableRef`` must carry enough information to retrieve the
    object from a durable store. A digest alone is *not* sufficient —
    the store identity and locator are required to preserve the result.

    Secret payloads are rejected: metadata keys matching known secret
    patterns cause construction to fail.
    """

    store_id: str
    locator: str
    digest: str
    schema_type: str = "application/octet-stream"
    media_type: str = "application/octet-stream"
    size_bytes: int | None = None
    encryption_scope: EncryptionScope = EncryptionScope.NONE
    access_scope: AccessScope = AccessScope.WORKFLOW
    privacy_class: PrivacyClass = PrivacyClass.INTERNAL
    retention_class: RetentionClass = RetentionClass.RUN
    availability_class: AvailabilityClass = AvailabilityClass.STANDARD
    tenant_id: str | None = None
    workflow_id: str | None = None
    key_id: str | None = None
    key_version: int | None = None
    created_at_ns: int | None = None
    expires_at_ns: int | None = None
    legal_hold: bool = False
    tombstoned_at_ns: int | None = None
    ref_version: str = "arnold.workflow.durable_ref.v1"
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Required fields must be non-empty.
        if not self.store_id.strip():
            raise ValueError("DurableRef.store_id must be non-empty")
        if not self.locator.strip():
            raise ValueError("DurableRef.locator must be non-empty")

        # Digest is required AND must be a valid sha256 hex digest.
        if not self.digest.strip():
            raise ValueError(
                "DurableRef.digest must be non-empty; "
                "a digest without retained retrievable bytes does not "
                "preserve a result"
            )
        _require_digest(self.digest)

        # Enforce enums.
        object.__setattr__(
            self, "encryption_scope", EncryptionScope(self.encryption_scope)
        )
        object.__setattr__(self, "access_scope", AccessScope(self.access_scope))
        object.__setattr__(self, "privacy_class", PrivacyClass(self.privacy_class))
        object.__setattr__(
            self, "retention_class", RetentionClass(self.retention_class)
        )
        object.__setattr__(
            self, "availability_class", AvailabilityClass(self.availability_class)
        )

        # Schema type must be non-empty.
        if not self.schema_type.strip():
            raise ValueError("DurableRef.schema_type must be non-empty")

        # Reject secret payloads in metadata.
        _reject_secret_keys(self.metadata)
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata))

        # Size must be non-negative if provided.
        if self.size_bytes is not None and self.size_bytes < 0:
            raise ValueError("DurableRef.size_bytes must be non-negative")
        if self.key_id is not None and not self.key_id.strip():
            raise ValueError("DurableRef.key_id must be non-empty when set")
        if self.key_version is not None and self.key_version < 1:
            raise ValueError("DurableRef.key_version must be >= 1 when set")
        if self.key_id is not None and self.key_version is None:
            raise ValueError("DurableRef.key_version is required when key_id is set")
        if self.key_version is not None and self.key_id is None:
            raise ValueError("DurableRef.key_id is required when key_version is set")
        if self.created_at_ns is not None and self.created_at_ns < 0:
            raise ValueError("DurableRef.created_at_ns must be non-negative")
        if self.expires_at_ns is not None and self.expires_at_ns < 0:
            raise ValueError("DurableRef.expires_at_ns must be non-negative")
        if self.tombstoned_at_ns is not None and self.tombstoned_at_ns < 0:
            raise ValueError("DurableRef.tombstoned_at_ns must be non-negative")

    @property
    def is_retrievable(self) -> bool:
        """Return True when the ref carries enough information to retrieve
        the durable object from its store.

        A digest without a store_id and locator is not retrievable.
        """
        return bool(self.store_id.strip() and self.locator.strip())

    @property
    def is_encrypted(self) -> bool:
        """Return True when the ref requires encryption at rest."""
        return self.encryption_scope != EncryptionScope.NONE

    @property
    def is_legal_hold(self) -> bool:
        """Return True when the ref is under legal hold retention."""
        return self.legal_hold or self.retention_class == RetentionClass.LEGAL_HOLD

    @property
    def is_tombstoned(self) -> bool:
        """Return True when the stored bytes have been tombstoned."""
        return self.tombstoned_at_ns is not None

    def to_dict(self) -> dict[str, Any]:
        """Return a sidecar-safe payload with primitive values."""
        payload: dict[str, Any] = {
            "store_id": self.store_id,
            "locator": self.locator,
            "digest": self.digest,
            "schema_type": self.schema_type,
            "media_type": self.media_type,
            "encryption_scope": self.encryption_scope.value,
            "access_scope": self.access_scope.value,
            "privacy_class": self.privacy_class.value,
            "retention_class": self.retention_class.value,
            "availability_class": self.availability_class.value,
            "ref_version": self.ref_version,
        }
        if self.size_bytes is not None:
            payload["size_bytes"] = self.size_bytes
        if self.tenant_id is not None:
            payload["tenant_id"] = self.tenant_id
        if self.workflow_id is not None:
            payload["workflow_id"] = self.workflow_id
        if self.key_id is not None:
            payload["key_id"] = self.key_id
        if self.key_version is not None:
            payload["key_version"] = self.key_version
        if self.created_at_ns is not None:
            payload["created_at_ns"] = self.created_at_ns
        if self.expires_at_ns is not None:
            payload["expires_at_ns"] = self.expires_at_ns
        if self.legal_hold:
            payload["legal_hold"] = self.legal_hold
        if self.tombstoned_at_ns is not None:
            payload["tombstoned_at_ns"] = self.tombstoned_at_ns
        if self.metadata:
            payload["metadata"] = _thaw_value(self.metadata)
        return payload


# ── DurableRef validators ─────────────────────────────────────────────────


def validate_durable_ref_retrievability(ref: DurableRef) -> list[str]:
    """Validate that a DurableRef is retrievable.

    Returns a list of human-readable issue descriptions. An empty list
    means the ref passes all retrievability checks.

    A digest-only ref (no store_id or locator) is rejected because a
    digest without retained retrievable bytes does not preserve a result.
    """
    issues: list[str] = []

    if not ref.store_id.strip():
        issues.append(
            "DurableRef.store_id is empty; cannot locate the durable store"
        )
    if not ref.locator.strip():
        issues.append(
            "DurableRef.locator is empty; cannot retrieve the object "
            "from the store"
        )
    if not ref.digest.strip():
        issues.append(
            "DurableRef.digest is empty; integrity verification is "
            "impossible without a digest"
        )
    else:
        try:
            _require_digest(ref.digest)
        except ValueError:
            issues.append(
                f"DurableRef.digest {ref.digest!r} is not a valid "
                f"sha256 hex digest"
            )

    return issues


def validate_durable_ref_tenant_scope(
    ref: DurableRef,
    *,
    expected_tenant_id: str | None = None,
    expected_workflow_id: str | None = None,
) -> list[str]:
    """Validate tenant/workflow isolation scope for a DurableRef.

    If expected values are provided, the ref must match them.
    """
    issues: list[str] = []

    if expected_tenant_id is not None and ref.tenant_id != expected_tenant_id:
        issues.append(
            f"DurableRef.tenant_id {ref.tenant_id!r} does not match "
            f"expected {expected_tenant_id!r}"
        )
    if expected_workflow_id is not None and ref.workflow_id != expected_workflow_id:
        issues.append(
            f"DurableRef.workflow_id {ref.workflow_id!r} does not match "
            f"expected {expected_workflow_id!r}"
        )

    if ref.access_scope == AccessScope.TENANT and ref.tenant_id is None:
        issues.append(
            "DurableRef.access_scope is 'tenant' but tenant_id is None"
        )
    if ref.access_scope == AccessScope.WORKFLOW and ref.workflow_id is None:
        issues.append(
            "DurableRef.access_scope is 'workflow' but workflow_id is None"
        )

    return issues


def validate_durable_ref_secret_exclusion(ref: DurableRef) -> list[str]:
    """Validate that a DurableRef does not carry secret payloads.

    Checks metadata keys against known secret patterns.
    """
    issues: list[str] = []

    for key in ref.metadata:
        lower_key = key.lower()
        for forbidden in _FORBIDDEN_SECRET_KEYS:
            if forbidden in lower_key:
                issues.append(
                    f"DurableRef metadata key {key!r} matches forbidden "
                    f"secret pattern {forbidden!r}"
                )

    return issues


def validate_durable_ref_byte_access_schema(ref: DurableRef) -> list[str]:
    """Validate byte-access schema fields without reading stored bytes.

    Stored-byte policy enforcement happens in ``ledger_payload_store`` when
    encrypted bytes are read, expired, tombstoned, or deleted. This validator
    deliberately checks only reference metadata shape.
    """
    issues: list[str] = []

    if ref.is_encrypted and (ref.key_id is None or ref.key_version is None):
        issues.append(
            "Encrypted DurableRef requires key_id and key_version metadata"
        )
    if ref.expires_at_ns is not None and ref.created_at_ns is not None:
        if ref.expires_at_ns < ref.created_at_ns:
            issues.append(
                "DurableRef.expires_at_ns is earlier than created_at_ns"
            )
    if ref.is_legal_hold and ref.expires_at_ns is not None:
        issues.append(
            "Legal-hold DurableRef must not carry expires_at_ns"
        )
    return issues


def validate_durable_ref(
    ref: DurableRef,
    *,
    expected_tenant_id: str | None = None,
    expected_workflow_id: str | None = None,
) -> list[str]:
    """Run all DurableRef validators and return consolidated issues.

    This is the primary entry point for DurableRef validation. It runs
    retrievability, tenant/workflow scope, and secret-exclusion checks.
    """
    issues: list[str] = []
    issues.extend(validate_durable_ref_retrievability(ref))
    issues.extend(
        validate_durable_ref_tenant_scope(
            ref,
            expected_tenant_id=expected_tenant_id,
            expected_workflow_id=expected_workflow_id,
        )
    )
    issues.extend(validate_durable_ref_secret_exclusion(ref))
    issues.extend(validate_durable_ref_byte_access_schema(ref))
    return issues


__all__ = [
    "AccessScope",
    "AvailabilityClass",
    "DurableRef",
    "EncryptionScope",
    "PrivacyClass",
    "RetentionClass",
    "validate_durable_ref",
    "validate_durable_ref_byte_access_schema",
    "validate_durable_ref_retrievability",
    "validate_durable_ref_secret_exclusion",
    "validate_durable_ref_tenant_scope",
]
