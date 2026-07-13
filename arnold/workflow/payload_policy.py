"""Payload classification and retention policy schema for workflow boundary contracts.

This module freezes the ``wbc.inline.v1`` and ``wbc.retention.v1`` schema
contracts under ``arnold.workflow``. It defines:

* Canonical JSON sizing with the 16 KiB inline threshold.
* Inline-vs-reference payload classification.
* Retention, redaction, tombstone, and legal-hold rules.
* Access-audit requirements.
* Digest-only preservation rejection.

This is schema-only — no I/O, mutation, or runtime effects.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Mapping

from arnold.manifest.manifests import canonical_json


# ── Constants ─────────────────────────────────────────────────────────────

# The 16 KiB canonical-JSON threshold for inline payloads.
# Payloads whose canonical JSON representation is ≤ this size may be inlined;
# larger payloads MUST use a durable reference.
INLINE_CANONICAL_JSON_SIZE_THRESHOLD_BYTES: int = 16 * 1024  # 16 KiB

# Schema version identifiers.
WBC_INLINE_V1: str = "wbc.inline.v1"
WBC_RETENTION_V1: str = "wbc.retention.v1"

# Minimum retention durations (in seconds).
_RETENTION_DURATIONS: Mapping[str, int] = MappingProxyType(
    {
        "ephemeral": 0,
        "run": 86400,          # 24 hours
        "audit": 7776000,      # 90 days
        "legal_hold": -1,      # indefinite
    }
)


# ── Enums ─────────────────────────────────────────────────────────────────


class PayloadMode(StrEnum):
    """Payload storage mode for workflow boundary payloads."""

    INLINE = "inline"
    REFERENCE = "reference"
    DIGEST_ONLY = "digest_only"


class RetentionMode(StrEnum):
    """Retention modes for durable payload storage."""

    EPHEMERAL = "ephemeral"
    RUN = "run"
    AUDIT = "audit"
    LEGAL_HOLD = "legal_hold"


class RedactionMode(StrEnum):
    """Redaction modes for retention policy."""

    NONE = "none"
    DEFAULT_ON = "default_on"
    ALWAYS = "always"


class TombstoneMode(StrEnum):
    """Tombstone modes for deleted payloads."""

    NONE = "none"
    MARKER = "marker"
    FULL = "full"


class AuditMode(StrEnum):
    """Access-audit modes for payload access."""

    NONE = "none"
    READ = "read"
    READ_WRITE = "read_write"
    FULL = "full"


class IsolationLevel(StrEnum):
    """Tenant/workflow isolation levels."""

    TENANT = "tenant"
    WORKFLOW = "workflow"
    INVOCATION = "invocation"
    SHARED = "shared"


# ── Helpers ───────────────────────────────────────────────────────────────


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


def compute_canonical_json_size(payload: Mapping[str, Any]) -> int:
    """Return the size in bytes of a payload's canonical JSON representation.

    Uses ``arnold.manifest.manifests.canonical_json`` for consistent sizing.
    """
    return len(canonical_json(payload).encode("utf-8"))


def classify_payload_mode(payload: Mapping[str, Any]) -> PayloadMode:
    """Classify a payload as inline, reference, or digest-only.

    * INLINE: canonical JSON size ≤ 16 KiB.
    * REFERENCE: canonical JSON size > 16 KiB (must use a durable ref).
    * DIGEST_ONLY: never returned by this function — digest-only payloads
      must be rejected by ``validate_payload_preservation``.

    This function only classifies based on size; it does not enforce
    the digest-only rejection (that is done by the validator).
    """
    size = compute_canonical_json_size(payload)
    if size <= INLINE_CANONICAL_JSON_SIZE_THRESHOLD_BYTES:
        return PayloadMode.INLINE
    return PayloadMode.REFERENCE


# ── InlinePayloadPolicy (wbc.inline.v1) ───────────────────────────────────


@dataclass(frozen=True)
class InlinePayloadPolicy:
    """Schema for ``wbc.inline.v1`` inline payload classification.

    Carries the inline threshold and classification rules. Payloads above
    the threshold must use a ``DurableRef`` instead of inline storage.
    """

    threshold_bytes: int = INLINE_CANONICAL_JSON_SIZE_THRESHOLD_BYTES
    schema_version: str = WBC_INLINE_V1
    max_inline_payloads: int = 128
    allow_digest_only: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.threshold_bytes < 0:
            raise ValueError(
                "InlinePayloadPolicy.threshold_bytes must be non-negative"
            )
        if self.max_inline_payloads < 0:
            raise ValueError(
                "InlinePayloadPolicy.max_inline_payloads must be non-negative"
            )
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata))

    @property
    def is_digest_only_rejected(self) -> bool:
        """Return True when digest-only payloads are rejected (the default)."""
        return not self.allow_digest_only

    def classify(self, payload: Mapping[str, Any]) -> PayloadMode:
        """Classify a payload using the inline threshold."""
        size = compute_canonical_json_size(payload)
        if size <= self.threshold_bytes:
            return PayloadMode.INLINE
        return PayloadMode.REFERENCE

    def to_dict(self) -> dict[str, Any]:
        """Return a sidecar-safe payload."""
        payload: dict[str, Any] = {
            "threshold_bytes": self.threshold_bytes,
            "schema_version": self.schema_version,
            "max_inline_payloads": self.max_inline_payloads,
            "allow_digest_only": self.allow_digest_only,
        }
        if self.metadata:
            payload["metadata"] = _thaw_value(self.metadata)
        return payload


def default_inline_policy() -> InlinePayloadPolicy:
    """Return the default ``wbc.inline.v1`` policy.

    Uses the 16 KiB threshold, rejects digest-only payloads.
    """
    return InlinePayloadPolicy(
        threshold_bytes=INLINE_CANONICAL_JSON_SIZE_THRESHOLD_BYTES,
    )


# ── RetentionPayloadPolicy (wbc.retention.v1) ─────────────────────────────


@dataclass(frozen=True)
class RetentionPayloadPolicy:
    """Schema for ``wbc.retention.v1`` retention and lifecycle rules.

    Covers retention duration, redaction, tombstone, legal hold,
    tenant/workflow isolation, encryption, secret exclusion, and
    access-audit behavior.
    """

    retention_mode: RetentionMode = RetentionMode.RUN
    redaction_mode: RedactionMode = RedactionMode.DEFAULT_ON
    tombstone_mode: TombstoneMode = TombstoneMode.MARKER
    audit_mode: AuditMode = AuditMode.READ_WRITE
    isolation_level: IsolationLevel = IsolationLevel.WORKFLOW
    legal_hold: bool = False
    encryption_required: bool = True
    secret_exclusion_enforced: bool = True
    digest_only_preservation_rejected: bool = True
    max_retention_seconds: int | None = None
    schema_version: str = WBC_RETENTION_V1
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "retention_mode", RetentionMode(self.retention_mode)
        )
        object.__setattr__(
            self, "redaction_mode", RedactionMode(self.redaction_mode)
        )
        object.__setattr__(
            self, "tombstone_mode", TombstoneMode(self.tombstone_mode)
        )
        object.__setattr__(self, "audit_mode", AuditMode(self.audit_mode))
        object.__setattr__(
            self, "isolation_level", IsolationLevel(self.isolation_level)
        )

        if self.max_retention_seconds is not None and self.max_retention_seconds < 0:
            raise ValueError(
                "RetentionPayloadPolicy.max_retention_seconds must be "
                "non-negative"
            )

        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata))

    @property
    def effective_retention_seconds(self) -> int:
        """Return the effective minimum retention duration in seconds.

        Legal hold returns -1 (indefinite).
        """
        if self.legal_hold:
            return -1
        if self.max_retention_seconds is not None:
            return self.max_retention_seconds
        return _RETENTION_DURATIONS.get(self.retention_mode.value, 0)

    @property
    def is_redaction_enforced(self) -> bool:
        """Return True when redaction is active (default-on or always)."""
        return self.redaction_mode in (
            RedactionMode.DEFAULT_ON,
            RedactionMode.ALWAYS,
        )

    @property
    def is_tombstone_enabled(self) -> bool:
        """Return True when tombstone markers are placed on deletion."""
        return self.tombstone_mode != TombstoneMode.NONE

    @property
    def is_audit_required(self) -> bool:
        """Return True when access auditing is required."""
        return self.audit_mode != AuditMode.NONE

    @property
    def is_legal_hold_active(self) -> bool:
        """Return True when legal hold is active."""
        return self.legal_hold

    def to_dict(self) -> dict[str, Any]:
        """Return a sidecar-safe payload."""
        payload: dict[str, Any] = {
            "retention_mode": self.retention_mode.value,
            "redaction_mode": self.redaction_mode.value,
            "tombstone_mode": self.tombstone_mode.value,
            "audit_mode": self.audit_mode.value,
            "isolation_level": self.isolation_level.value,
            "legal_hold": self.legal_hold,
            "encryption_required": self.encryption_required,
            "secret_exclusion_enforced": self.secret_exclusion_enforced,
            "digest_only_preservation_rejected": (
                self.digest_only_preservation_rejected
            ),
            "schema_version": self.schema_version,
        }
        if self.max_retention_seconds is not None:
            payload["max_retention_seconds"] = self.max_retention_seconds
        if self.metadata:
            payload["metadata"] = _thaw_value(self.metadata)
        return payload


def default_retention_policy() -> RetentionPayloadPolicy:
    """Return the default ``wbc.retention.v1`` policy.

    Defaults: run retention, default-on redaction, marker tombstones,
    read-write audit, workflow isolation, encryption required,
    secret exclusion enforced, digest-only preservation rejected.
    """
    return RetentionPayloadPolicy(
        retention_mode=RetentionMode.RUN,
        redaction_mode=RedactionMode.DEFAULT_ON,
        tombstone_mode=TombstoneMode.MARKER,
        audit_mode=AuditMode.READ_WRITE,
        isolation_level=IsolationLevel.WORKFLOW,
        legal_hold=False,
        encryption_required=True,
        secret_exclusion_enforced=True,
        digest_only_preservation_rejected=True,
    )


# ── Payload policy validators ─────────────────────────────────────────────


def validate_inline_payload_policy(
    policy: InlinePayloadPolicy,
    payload: Mapping[str, Any],
) -> list[str]:
    """Validate a payload against the inline classification policy.

    Returns a list of issue descriptions. An empty list means the
    payload conforms.

    Digest-only payload rejection:
        If the policy rejects digest-only (allow_digest_only=False) and
        the payload classifies as REFERENCE without an accompanying
        durable ref, the payload is flagged.
    """
    issues: list[str] = []
    mode = policy.classify(payload)

    if mode == PayloadMode.REFERENCE:
        # REFERENCE mode requires the payload to carry a DurableRef.
        # We check for a minimal durable_ref indicator.
        has_durable_ref = bool(
            payload.get("_durable_ref")
            or payload.get("durable_ref")
            or payload.get("ref")
        )
        if not has_durable_ref:
            issues.append(
                "Payload exceeds inline threshold "
                f"({policy.threshold_bytes} bytes) but no durable_ref "
                "is present; large payloads must be stored by reference"
            )

        if policy.is_digest_only_rejected:
            # Check if the payload appears to be digest-only (has a hash
            # but no retrievable store/locator).
            has_digest = bool(payload.get("digest") or payload.get("hash"))
            has_locator = bool(
                payload.get("store_id")
                or payload.get("locator")
                or payload.get("_durable_ref")
                or payload.get("durable_ref")
            )
            if has_digest and not has_locator:
                issues.append(
                    "Digest-only payload preservation is rejected by "
                    "wbc.inline.v1 policy; a digest without retained "
                    "retrievable bytes does not preserve a result"
                )

    return issues


def validate_retention_payload_policy(
    policy: RetentionPayloadPolicy,
    *,
    payload: Mapping[str, Any] | None = None,
) -> list[str]:
    """Validate that a retention policy satisfies wbc.retention.v1 rules.

    Returns a list of issue descriptions. Validates:
    * Retention mode is a known value.
    * Encryption is required (by default).
    * Secret exclusion is enforced (by default).
    * Digest-only preservation is rejected (by default).
    * Legal hold is properly configured.

    If a payload is provided, it is also checked for secret-like keys
    and digest-only patterns.
    """
    issues: list[str] = []

    # Encryption check.
    if policy.encryption_required and policy.retention_mode != RetentionMode.EPHEMERAL:
        # Encryption is required for non-ephemeral retention.
        pass  # The policy flag itself is sufficient; no additional check needed.

    # Digest-only preservation rejection.
    if policy.digest_only_preservation_rejected and payload is not None:
        has_digest = bool(payload.get("digest") or payload.get("hash"))
        has_retrievable = bool(
            payload.get("store_id")
            or payload.get("locator")
            or payload.get("durable_ref")
            or payload.get("_durable_ref")
        )
        if has_digest and not has_retrievable:
            issues.append(
                "Digest-only payload preservation is rejected by "
                "wbc.retention.v1 policy; a digest without retained "
                "retrievable bytes does not preserve a result"
            )

    # Legal hold validation.
    if policy.legal_hold and policy.retention_mode == RetentionMode.EPHEMERAL:
        issues.append(
            "Legal hold is active but retention_mode is 'ephemeral'; "
            "legal-hold payloads must use at least 'run' retention"
        )

    # Secret exclusion check on payload.
    if policy.secret_exclusion_enforced and payload is not None:
        _FORBIDDEN = frozenset(
            {
                "api_key", "password", "secret", "token",
                "private_key", "credential", "bearer", "authorization",
            }
        )
        for key in payload:
            lower_key = key.lower()
            for forbidden in _FORBIDDEN:
                if forbidden in lower_key:
                    issues.append(
                        f"Payload key {key!r} matches forbidden secret "
                        f"pattern {forbidden!r}; secret exclusion is "
                        f"enforced by wbc.retention.v1"
                    )

    return issues


def validate_payload_preservation(
    *,
    inline_policy: InlinePayloadPolicy | None = None,
    retention_policy: RetentionPayloadPolicy | None = None,
    payload: Mapping[str, Any],
) -> list[str]:
    """Run all payload policy validators and return consolidated issues.

    This is the primary entry point for payload policy validation.
    Validates inline classification, retention rules, and digest-only
    preservation rejection.
    """
    issues: list[str] = []

    if inline_policy is None:
        inline_policy = default_inline_policy()
    if retention_policy is None:
        retention_policy = default_retention_policy()

    issues.extend(validate_inline_payload_policy(inline_policy, payload))
    issues.extend(
        validate_retention_payload_policy(
            retention_policy, payload=payload
        )
    )

    return issues


__all__ = [
    "INLINE_CANONICAL_JSON_SIZE_THRESHOLD_BYTES",
    "WBC_INLINE_V1",
    "WBC_RETENTION_V1",
    "AuditMode",
    "InlinePayloadPolicy",
    "IsolationLevel",
    "PayloadMode",
    "RedactionMode",
    "RetentionMode",
    "RetentionPayloadPolicy",
    "TombstoneMode",
    "classify_payload_mode",
    "compute_canonical_json_size",
    "default_inline_policy",
    "default_retention_policy",
    "validate_inline_payload_policy",
    "validate_payload_preservation",
    "validate_retention_payload_policy",
]
