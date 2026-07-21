"""Tests for ``SqliteLedgerPayloadStore`` payload/reference enforcement.

Focused coverage (SC9):

* Inline threshold enforcement (16 KiB boundary, ``force_reference``).
* Redaction of protected fields in the inline representation; unredacted
  protected fields are rejected.
* Tenant/workflow access control on retrieval (cross-tenant and
  cross-workflow reads are denied).
* Secret-like stored-byte rejection (forbidden key fragments).
* Digest-only preservation rejection where the retention policy forbids it.
* Protected-class encryption checks (confidential/restricted payloads MUST
  be encrypted at rest; fail closed with no provider/key/scope).
* ``DurableRef`` generation carrying privacy, retention, access, encryption,
  digest, size, and audit metadata.
"""

from __future__ import annotations

import json
import tempfile
import uuid
from pathlib import Path

import pytest

from arnold.workflow.attempt_ledger_store import SqliteAttemptLedgerStore
from arnold.workflow.durable_refs import (
    AccessScope,
    DurableRef,
    EncryptionScope,
    PrivacyClass,
    RetentionClass,
)
from arnold.workflow.ledger_payload_store import (
    AccessContext,
    PAYLOAD_STORE_VERSION,
    DeletionEvidence,
    PayloadDigestOnlyError,
    PayloadExpiredError,
    PayloadInlineThresholdError,
    PayloadLegalHoldError,
    PayloadNotFoundError,
    PayloadProtectedEncryptionError,
    PayloadRedactionError,
    PayloadSecretKeyError,
    PayloadStoreError,
    PayloadTenantAccessError,
    PayloadTombstoneError,
    REDACTION_MARKER,
    SqliteLedgerPayloadStore,
    StaticKeyEncryptionProvider,
    StoredPayload,
)
from arnold.workflow.payload_policy import (
    INLINE_CANONICAL_JSON_SIZE_THRESHOLD_BYTES,
    InlinePayloadPolicy,
    PayloadMode,
    RedactionMode,
    RetentionMode,
    RetentionPayloadPolicy,
    default_inline_policy,
    default_retention_policy,
)


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "payload_store.db"


@pytest.fixture
def store(db_path: Path) -> SqliteLedgerPayloadStore:
    backing = SqliteAttemptLedgerStore(db_path)
    return SqliteLedgerPayloadStore(backing)


@pytest.fixture
def store_with_crypto(db_path: Path) -> SqliteLedgerPayloadStore:
    backing = SqliteAttemptLedgerStore(db_path)
    provider = StaticKeyEncryptionProvider()
    return SqliteLedgerPayloadStore(backing, encryption_provider=provider)


@pytest.fixture
def store_no_crypto(db_path: Path) -> SqliteLedgerPayloadStore:
    """A store with NO encryption provider — used to prove fail-closed."""
    backing = SqliteAttemptLedgerStore(db_path)
    return SqliteLedgerPayloadStore(backing, encryption_provider=None)


def _small_payload() -> dict:
    return {"step": "compute", "value": 42, "ok": True}


def _oversized_payload() -> dict:
    """A payload whose canonical JSON clearly exceeds the 16 KiB threshold."""
    big = "x" * (INLINE_CANONICAL_JSON_SIZE_THRESHOLD_BYTES + 1024)
    return {"step": "compute", "blob": big}


# ── 1. Inline threshold enforcement ───────────────────────────────────────


class TestInlineThresholdEnforcement:
    """Inline-vs-reference boundary at the 16 KiB canonical-JSON threshold."""

    def test_small_payload_stored_inline(self, store: SqliteLedgerPayloadStore):
        result = store.store_payload(
            _small_payload(), tenant_id="t1", workflow_id="w1"
        )
        assert result.payload_mode == PayloadMode.INLINE
        assert result.size_bytes <= INLINE_CANONICAL_JSON_SIZE_THRESHOLD_BYTES
        assert result.inline_payload is not None
        assert result.inline_payload["step"] == "compute"

    def test_oversized_payload_rejected_inline_without_force(
        self, store: SqliteLedgerPayloadStore
    ):
        # An oversized payload classifies as REFERENCE, so without
        # force_reference it MUST be stored by reference.  The store enforces
        # this by raising PayloadInlineThresholdError when the classified
        # mode is INLINE but the bytes exceed the threshold.  Here the
        # classification already yields REFERENCE so storage succeeds in
        # reference mode.
        result = store.store_payload(
            _oversized_payload(), tenant_id="t1", workflow_id="w1"
        )
        assert result.payload_mode == PayloadMode.REFERENCE
        assert result.size_bytes > INLINE_CANONICAL_JSON_SIZE_THRESHOLD_BYTES
        assert result.inline_payload is None

    def test_force_reference_on_small_payload(self, store: SqliteLedgerPayloadStore):
        result = store.store_payload(
            _small_payload(),
            tenant_id="t1",
            workflow_id="w1",
            force_reference=True,
        )
        assert result.payload_mode == PayloadMode.REFERENCE
        assert result.inline_payload is None

    def test_inline_threshold_error_when_classified_inline_but_oversized(
        self, store: SqliteLedgerPayloadStore
    ):
        # Construct a policy with a tiny threshold so the payload classifies
        # as REFERENCE; then craft a payload just above a low threshold and
        # verify the inline guard trips when we force it inline by lowering
        # the threshold and then bumping the payload past it.
        tiny_policy = InlinePayloadPolicy(
            threshold_bytes=INLINE_CANONICAL_JSON_SIZE_THRESHOLD_BYTES
        )
        # A payload sized ABOVE the default threshold will classify as
        # REFERENCE; we cannot force INLINE through the public API. Instead
        # verify the guard directly: craft a payload above threshold and
        # confirm the store's inline guard raises when persist_bytes exceed
        # the threshold while mode is INLINE.
        oversized = _oversized_payload()
        from arnold.manifest.manifests import canonical_json

        persist_bytes = canonical_json(oversized).encode("utf-8")
        with pytest.raises(PayloadInlineThresholdError):
            store._enforce_inline_threshold(
                persist_bytes,
                PayloadMode.INLINE,
                tiny_policy,
            )

    def test_force_reference_oversized_succeeds(self, store: SqliteLedgerPayloadStore):
        result = store.store_payload(
            _oversized_payload(),
            tenant_id="t1",
            workflow_id="w1",
            force_reference=True,
        )
        assert result.payload_mode == PayloadMode.REFERENCE
        assert result.durable_ref.locator.startswith("payload:")


# ── 2. Redaction of protected fields ──────────────────────────────────────


class TestRedactionEnforcement:
    """Protected-field redaction in the inline representation."""

    def test_protected_field_redacted_inline(self, store: SqliteLedgerPayloadStore):
        result = store.store_payload(
            {"step": "compute", "ssn": "123-45-6789", "note": "ok"},
            tenant_id="t1",
            workflow_id="w1",
            protected_fields=("ssn",),
        )
        assert result.payload_mode == PayloadMode.INLINE
        assert "ssn" in result.redacted_fields
        assert result.inline_payload is not None
        assert result.inline_payload["ssn"] == REDACTION_MARKER
        assert result.inline_payload["note"] == "ok"

    def test_multiple_protected_fields_redacted(
        self, store: SqliteLedgerPayloadStore
    ):
        result = store.store_payload(
            {"a": "secret-a", "b": "secret-b", "c": "keep"},
            tenant_id="t1",
            workflow_id="w1",
            protected_fields=("a", "b"),
        )
        assert set(result.redacted_fields) == {"a", "b"}
        assert result.inline_payload["a"] == REDACTION_MARKER
        assert result.inline_payload["b"] == REDACTION_MARKER
        assert result.inline_payload["c"] == "keep"

    def test_redaction_off_keeps_field(self, store: SqliteLedgerPayloadStore):
        policy = RetentionPayloadPolicy(redaction_mode=RedactionMode.NONE)
        result = store.store_payload(
            {"ssn": "123-45-6789"},
            tenant_id="t1",
            workflow_id="w1",
            protected_fields=("ssn",),
            retention_policy=policy,
        )
        assert result.redacted_fields == ()
        assert result.inline_payload["ssn"] == "123-45-6789"

    def test_redaction_recorded_in_durable_ref_audit(
        self, store: SqliteLedgerPayloadStore
    ):
        result = store.store_payload(
            {"ssn": "123-45-6789"},
            tenant_id="t1",
            workflow_id="w1",
            protected_fields=("ssn",),
        )
        meta = dict(result.durable_ref.metadata)
        assert "redacted_fields" in meta
        assert list(meta["redacted_fields"]) == ["ssn"]


# ── 3. Tenant/workflow access control ─────────────────────────────────────


class TestTenantWorkflowAccess:
    """Cross-tenant and cross-workflow reads are denied."""

    def test_same_tenant_retrieves(self, store: SqliteLedgerPayloadStore):
        result = store.store_payload(
            _small_payload(), tenant_id="t1", workflow_id="w1"
        )
        retrieved = store.retrieve_payload(
            result.locator, access_context=AccessContext(tenant_id="t1",
                                                         workflow_id="w1")
        )
        assert retrieved["step"] == "compute"

    def test_cross_tenant_denied(self, store: SqliteLedgerPayloadStore):
        result = store.store_payload(
            _small_payload(), tenant_id="t1", workflow_id="w1"
        )
        with pytest.raises(PayloadTenantAccessError):
            store.retrieve_payload(
                result.locator,
                access_context=AccessContext(tenant_id="other-tenant",
                                             workflow_id="w1"),
            )

    def test_cross_workflow_denied(self, store: SqliteLedgerPayloadStore):
        result = store.store_payload(
            _small_payload(), tenant_id="t1", workflow_id="w1"
        )
        with pytest.raises(PayloadTenantAccessError):
            store.retrieve_payload(
                result.locator,
                access_context=AccessContext(tenant_id="t1",
                                             workflow_id="other-wf"),
            )

    def test_admin_none_tenant_context_allowed(
        self, store: SqliteLedgerPayloadStore
    ):
        # A None tenant_id in the access context is permitted (store-internal
        # / administrative access).
        result = store.store_payload(
            _small_payload(), tenant_id="t1", workflow_id="w1"
        )
        retrieved = store.retrieve_payload(
            result.locator,
            access_context=AccessContext(tenant_id=None, workflow_id=None),
        )
        assert retrieved["step"] == "compute"

    def test_unscoped_payload_no_tenant_check(
        self, store: SqliteLedgerPayloadStore
    ):
        # A payload stored without tenant_id is accessible from any context
        # (no stored scope to violate).
        result = store.store_payload(_small_payload())
        retrieved = store.retrieve_payload(
            result.locator,
            access_context=AccessContext(tenant_id="any", workflow_id="any"),
        )
        assert retrieved["step"] == "compute"

    def test_unknown_locator_raises_not_found(self, store: SqliteLedgerPayloadStore):
        with pytest.raises(PayloadNotFoundError):
            store.retrieve_payload(
                "payload:does-not-exist",
                access_context=AccessContext(tenant_id="t1"),
            )


# ── 4. Secret-key rejection ───────────────────────────────────────────────


class TestSecretKeyRejection:
    """Payloads carrying forbidden secret-like keys are rejected."""

    @pytest.mark.parametrize(
        "key",
        [
            "api_key",
            "password",
            "secret",
            "token",
            "private_key",
            "credential",
            "bearer",
            "authorization",
            "user_api_key",   # substring match
            "MY_PASSWORD",    # case-insensitive
        ],
    )
    def test_forbidden_key_rejected(
        self, store: SqliteLedgerPayloadStore, key: str
    ):
        with pytest.raises(PayloadSecretKeyError):
            store.store_payload(
                {key: "value"}, tenant_id="t1", workflow_id="w1"
            )

    def test_safe_payload_accepted(self, store: SqliteLedgerPayloadStore):
        result = store.store_payload(
            {"step": "compute", "count": 10, "items": ["a", "b"]},
            tenant_id="t1",
            workflow_id="w1",
        )
        assert result.payload_mode == PayloadMode.INLINE


# ── 5. Digest-only rejection ──────────────────────────────────────────────


class TestDigestOnlyRejection:
    """Digest-only preservation is rejected where the policy forbids it."""

    def test_explicit_digest_only_rejected_default_policy(
        self, store: SqliteLedgerPayloadStore
    ):
        with pytest.raises(PayloadDigestOnlyError):
            store.store_payload(
                _small_payload(),
                tenant_id="t1",
                workflow_id="w1",
                digest_only=True,
            )

    def test_payload_digest_only_marker_rejected_default_policy(
        self, store: SqliteLedgerPayloadStore
    ):
        with pytest.raises(PayloadDigestOnlyError):
            store.store_payload(
                {"step": "compute", "_digest_only": True},
                tenant_id="t1",
                workflow_id="w1",
            )

    def test_digest_only_allowed_when_policy_permits(
        self, store: SqliteLedgerPayloadStore
    ):
        policy = RetentionPayloadPolicy(
            digest_only_preservation_rejected=False
        )
        # When the policy permits digest-only intent, the store accepts the
        # payload (it still stores retrievable bytes — the policy just no
        # longer rejects the intent marker).
        result = store.store_payload(
            {"step": "compute"},
            tenant_id="t1",
            workflow_id="w1",
            retention_policy=policy,
            digest_only=True,
        )
        assert result.payload_mode == PayloadMode.INLINE


# ── 6. Protected-class encryption checks ──────────────────────────────────


class TestProtectedClassEncryption:
    """Confidential/restricted payloads MUST be encrypted at rest (fail closed)."""

    def test_confidential_without_provider_fails_closed(
        self, store_no_crypto: SqliteLedgerPayloadStore
    ):
        with pytest.raises(PayloadProtectedEncryptionError):
            store_no_crypto.store_payload(
                _small_payload(),
                tenant_id="t1",
                workflow_id="w1",
                privacy_class=PrivacyClass.CONFIDENTIAL,
                encryption_scope=EncryptionScope.WORKFLOW_KEY,
            )

    def test_restricted_without_provider_fails_closed(
        self, store_no_crypto: SqliteLedgerPayloadStore
    ):
        with pytest.raises(PayloadProtectedEncryptionError):
            store_no_crypto.store_payload(
                _small_payload(),
                tenant_id="t1",
                workflow_id="w1",
                privacy_class=PrivacyClass.RESTRICTED,
                encryption_scope=EncryptionScope.TENANT_KEY,
            )

    def test_protected_with_none_scope_fails_closed(
        self, store_with_crypto: SqliteLedgerPayloadStore
    ):
        with pytest.raises(PayloadProtectedEncryptionError):
            store_with_crypto.store_payload(
                _small_payload(),
                tenant_id="t1",
                workflow_id="w1",
                privacy_class=PrivacyClass.CONFIDENTIAL,
                encryption_scope=EncryptionScope.NONE,
            )

    def test_protected_with_unavailable_scope_fails_closed(
        self, db_path: Path
    ):
        backing = SqliteAttemptLedgerStore(db_path)
        provider = StaticKeyEncryptionProvider(
            available_scopes=frozenset({EncryptionScope.TENANT_KEY})
        )
        store = SqliteLedgerPayloadStore(backing, encryption_provider=provider)
        with pytest.raises(PayloadProtectedEncryptionError):
            store.store_payload(
                _small_payload(),
                tenant_id="t1",
                workflow_id="w1",
                privacy_class=PrivacyClass.CONFIDENTIAL,
                encryption_scope=EncryptionScope.WORKFLOW_KEY,
            )

    def test_confidential_with_provider_encrypts(
        self, store_with_crypto: SqliteLedgerPayloadStore
    ):
        result = store_with_crypto.store_payload(
            _small_payload(),
            tenant_id="t1",
            workflow_id="w1",
            privacy_class=PrivacyClass.CONFIDENTIAL,
            encryption_scope=EncryptionScope.WORKFLOW_KEY,
        )
        assert result.encrypted is True
        assert result.privacy_class == PrivacyClass.CONFIDENTIAL
        assert result.encryption_scope == EncryptionScope.WORKFLOW_KEY

    def test_encrypted_payload_round_trips(
        self, store_with_crypto: SqliteLedgerPayloadStore
    ):
        original = {"step": "compute", "value": 42}
        result = store_with_crypto.store_payload(
            original,
            tenant_id="t1",
            workflow_id="w1",
            privacy_class=PrivacyClass.RESTRICTED,
            encryption_scope=EncryptionScope.TENANT_KEY,
        )
        assert result.encrypted is True
        retrieved = store_with_crypto.retrieve_payload(
            result.locator,
            access_context=AccessContext(tenant_id="t1", workflow_id="w1"),
        )
        assert retrieved == original

    def test_internal_class_not_encrypted_without_provider(
        self, store_no_crypto: SqliteLedgerPayloadStore
    ):
        # Non-protected classes do not require encryption.
        result = store_no_crypto.store_payload(
            _small_payload(),
            tenant_id="t1",
            workflow_id="w1",
            privacy_class=PrivacyClass.INTERNAL,
        )
        assert result.encrypted is False

    def test_public_class_not_encrypted(
        self, store_with_crypto: SqliteLedgerPayloadStore
    ):
        result = store_with_crypto.store_payload(
            _small_payload(),
            tenant_id="t1",
            workflow_id="w1",
            privacy_class=PrivacyClass.PUBLIC,
        )
        assert result.encrypted is False

    def test_encryption_required_false_allows_unencrypted_protected(
        self, store_no_crypto: SqliteLedgerPayloadStore
    ):
        # When the retention policy explicitly disables encryption_required,
        # a protected payload is accepted without encryption (operator
        # opt-out, not the default).
        policy = RetentionPayloadPolicy(encryption_required=False)
        result = store_no_crypto.store_payload(
            _small_payload(),
            tenant_id="t1",
            workflow_id="w1",
            privacy_class=PrivacyClass.CONFIDENTIAL,
            retention_policy=policy,
        )
        assert result.encrypted is False


# ── 7. DurableRef generation metadata ─────────────────────────────────────


class TestDurableRefGeneration:
    """Every stored payload yields a DurableRef with full metadata."""

    def test_durable_ref_carries_required_metadata(
        self, store: SqliteLedgerPayloadStore
    ):
        result = store.store_payload(
            _small_payload(), tenant_id="t1", workflow_id="w1"
        )
        ref = result.durable_ref
        assert isinstance(ref, DurableRef)
        # Privacy metadata.
        assert ref.privacy_class == PrivacyClass.INTERNAL
        # Retention metadata.
        assert ref.retention_class == RetentionClass.RUN
        # Access metadata.
        assert ref.access_scope == AccessScope.WORKFLOW
        # Encryption metadata.
        assert ref.encryption_scope == EncryptionScope.NONE
        # Digest metadata.
        assert ref.digest.startswith("sha256:")
        assert len(ref.digest) == len("sha256:") + 64
        # Size metadata.
        assert ref.size_bytes is not None
        assert ref.size_bytes > 0
        # Tenant/workflow binding.
        assert ref.tenant_id == "t1"
        assert ref.workflow_id == "w1"
        # Retrievability.
        assert ref.is_retrievable is True

    def test_durable_ref_audit_metadata(
        self, store: SqliteLedgerPayloadStore
    ):
        result = store.store_payload(
            {"ssn": "123-45-6789"},
            tenant_id="t1",
            workflow_id="w1",
            protected_fields=("ssn",),
            principal="agent-007",
        )
        meta = dict(result.durable_ref.metadata)
        assert meta["store_version"] == PAYLOAD_STORE_VERSION
        assert meta["stored_by_principal"] == "agent-007"
        assert meta["encrypted"] is False
        assert "redacted_fields" in meta
        assert list(meta["redacted_fields"]) == ["ssn"]
        assert "enforcement_checks" in meta
        checks = meta["enforcement_checks"]
        assert any("secret_key" in c for c in checks)
        assert any("digest_only" in c for c in checks)
        assert any("inline_threshold" in c for c in checks)

    def test_durable_ref_encryption_scope_reflected(
        self, store_with_crypto: SqliteLedgerPayloadStore
    ):
        result = store_with_crypto.store_payload(
            _small_payload(),
            tenant_id="t1",
            workflow_id="w1",
            privacy_class=PrivacyClass.CONFIDENTIAL,
            encryption_scope=EncryptionScope.TENANT_KEY,
        )
        ref = result.durable_ref
        assert ref.encryption_scope == EncryptionScope.TENANT_KEY
        assert ref.is_encrypted is True

    def test_durable_ref_legal_hold_retention(
        self, store: SqliteLedgerPayloadStore
    ):
        policy = RetentionPayloadPolicy(
            retention_mode=RetentionMode.LEGAL_HOLD, legal_hold=True
        )
        result = store.store_payload(
            _small_payload(),
            tenant_id="t1",
            workflow_id="w1",
            retention_policy=policy,
        )
        assert result.legal_hold is True
        assert result.durable_ref.retention_class == RetentionClass.LEGAL_HOLD
        assert result.durable_ref.is_legal_hold is True

    def test_durable_ref_digest_matches_content(
        self, store: SqliteLedgerPayloadStore
    ):
        import hashlib

        payload = _small_payload()
        result = store.store_payload(
            payload, tenant_id="t1", workflow_id="w1"
        )
        from arnold.manifest.manifests import canonical_json

        expected = "sha256:" + hashlib.sha256(
            canonical_json(payload).encode("utf-8")
        ).hexdigest()
        assert result.digest == expected
        assert result.durable_ref.digest == expected


# ── 8. Persistence and retrieval round-trip ───────────────────────────────


class TestPersistenceRoundTrip:
    """Stored payloads survive a reopen and retrieve correctly."""

    def test_inline_round_trip(self, db_path: Path):
        backing = SqliteAttemptLedgerStore(db_path)
        store = SqliteLedgerPayloadStore(backing)
        result = store.store_payload(
            {"step": "compute", "value": 7},
            tenant_id="t1",
            workflow_id="w1",
        )
        locator = result.locator

        # Reopen the same database file with a fresh store instance.
        backing2 = SqliteAttemptLedgerStore(db_path)
        store2 = SqliteLedgerPayloadStore(backing2)
        retrieved = store2.retrieve_payload(
            locator,
            access_context=AccessContext(tenant_id="t1", workflow_id="w1"),
        )
        assert retrieved["step"] == "compute"
        assert retrieved["value"] == 7

        meta = store2.get_stored_payload(locator)
        assert meta.locator == locator
        assert meta.payload_mode == PayloadMode.INLINE

    def test_reference_round_trip(self, db_path: Path):
        backing = SqliteAttemptLedgerStore(db_path)
        store = SqliteLedgerPayloadStore(backing)
        result = store.store_payload(
            _oversized_payload(),
            tenant_id="t1",
            workflow_id="w1",
        )
        locator = result.locator

        backing2 = SqliteAttemptLedgerStore(db_path)
        store2 = SqliteLedgerPayloadStore(backing2)
        retrieved = store2.retrieve_payload(
            locator,
            access_context=AccessContext(tenant_id="t1", workflow_id="w1"),
        )
        assert retrieved["step"] == "compute"
        assert "blob" in retrieved

    def test_encrypted_round_trip_across_reopen(self, db_path: Path):
        backing = SqliteAttemptLedgerStore(db_path)
        provider = StaticKeyEncryptionProvider()
        store = SqliteLedgerPayloadStore(backing, encryption_provider=provider)
        original = {"step": "compute", "hidden_value": "data"}
        result = store.store_payload(
            original,
            tenant_id="t1",
            workflow_id="w1",
            privacy_class=PrivacyClass.CONFIDENTIAL,
            encryption_scope=EncryptionScope.WORKFLOW_KEY,
        )
        locator = result.locator

        backing2 = SqliteAttemptLedgerStore(db_path)
        store2 = SqliteLedgerPayloadStore(
            backing2, encryption_provider=provider
        )
        retrieved = store2.retrieve_payload(
            locator,
            access_context=AccessContext(tenant_id="t1", workflow_id="w1"),
        )
        assert retrieved == original


# ── 9. Non-mapping payload rejection ──────────────────────────────────────


class TestNonMappingRejection:
    def test_non_mapping_payload_rejected(self, store: SqliteLedgerPayloadStore):
        with pytest.raises(PayloadStoreError):
            store.store_payload(  # type: ignore[arg-type]
                "not-a-mapping",
                tenant_id="t1",
                workflow_id="w1",
            )


# ── 10. Retention expiry enforcement ──────────────────────────────────────


class TestRetentionExpiry:
    """Expired payloads are not retrievable unless under legal hold."""

    def test_expired_payload_rejected(self, store: SqliteLedgerPayloadStore):
        from arnold.workflow.payload_policy import RetentionPayloadPolicy, RetentionMode

        policy = RetentionPayloadPolicy(
            retention_mode=RetentionMode.EPHEMERAL,
            max_retention_seconds=0,
        )
        result = store.store_payload(
            _small_payload(),
            tenant_id="t1",
            workflow_id="w1",
            retention_policy=policy,
        )
        # Ephemeral payload with 0 retention — expires immediately.
        with pytest.raises(PayloadExpiredError):
            store.retrieve_payload(
                result.locator,
                access_context=AccessContext(tenant_id="t1", workflow_id="w1"),
            )

    def test_payload_not_yet_expired_retrieves(
        self, store: SqliteLedgerPayloadStore
    ):
        from arnold.workflow.payload_policy import RetentionPayloadPolicy

        # A far-future retention (90 days in seconds).
        policy = RetentionPayloadPolicy(max_retention_seconds=7776000)
        result = store.store_payload(
            _small_payload(),
            tenant_id="t1",
            workflow_id="w1",
            retention_policy=policy,
        )
        retrieved = store.retrieve_payload(
            result.locator,
            access_context=AccessContext(tenant_id="t1", workflow_id="w1"),
        )
        assert retrieved["step"] == "compute"

    def test_no_expiry_retrieves(self, store: SqliteLedgerPayloadStore):
        from arnold.workflow.payload_policy import RetentionPayloadPolicy

        # Use a policy with no explicit max retention — the default
        # RUN retention gives 24 hours, which is far in the future.
        result = store.store_payload(
            _small_payload(), tenant_id="t1", workflow_id="w1"
        )
        # Default policy creates a future expiry.
        assert result.expires_at_ns is not None
        assert result.expires_at_ns > 0
        retrieved = store.retrieve_payload(
            result.locator,
            access_context=AccessContext(tenant_id="t1", workflow_id="w1"),
        )
        assert retrieved["step"] == "compute"

    def test_legal_hold_overrides_expiry(self, store: SqliteLedgerPayloadStore):
        from arnold.workflow.payload_policy import RetentionPayloadPolicy, RetentionMode

        policy = RetentionPayloadPolicy(
            retention_mode=RetentionMode.EPHEMERAL,
            max_retention_seconds=0,
            legal_hold=True,
        )
        result = store.store_payload(
            _small_payload(),
            tenant_id="t1",
            workflow_id="w1",
            retention_policy=policy,
        )
        assert result.legal_hold is True
        # Legal hold overrides expiry — retrieval should succeed.
        retrieved = store.retrieve_payload(
            result.locator,
            access_context=AccessContext(tenant_id="t1", workflow_id="w1"),
        )
        assert retrieved["step"] == "compute"

    def test_legal_hold_set_after_storage_overrides_expiry(
        self, store: SqliteLedgerPayloadStore
    ):
        from arnold.workflow.payload_policy import RetentionPayloadPolicy, RetentionMode

        policy = RetentionPayloadPolicy(
            retention_mode=RetentionMode.EPHEMERAL,
            max_retention_seconds=0,
        )
        result = store.store_payload(
            _small_payload(),
            tenant_id="t1",
            workflow_id="w1",
            retention_policy=policy,
        )
        # Set legal hold after storage.
        store.set_legal_hold(result.locator, active=True, principal="admin")
        retrieved = store.retrieve_payload(
            result.locator,
            access_context=AccessContext(tenant_id="t1", workflow_id="w1"),
        )
        assert retrieved["step"] == "compute"


# ── 11. Legal hold override ────────────────────────────────────────────────


class TestLegalHoldOverride:
    """set_legal_hold, is_under_legal_hold, and deletion blocking."""

    def test_set_legal_hold_returns_updated_payload(
        self, store: SqliteLedgerPayloadStore
    ):
        result = store.store_payload(
            _small_payload(), tenant_id="t1", workflow_id="w1"
        )
        assert result.legal_hold is False
        updated = store.set_legal_hold(
            result.locator, active=True, principal="auditor"
        )
        assert updated.legal_hold is True

    def test_clear_legal_hold(self, store: SqliteLedgerPayloadStore):
        from arnold.workflow.payload_policy import RetentionPayloadPolicy

        policy = RetentionPayloadPolicy(legal_hold=True)
        result = store.store_payload(
            _small_payload(),
            tenant_id="t1",
            workflow_id="w1",
            retention_policy=policy,
        )
        assert result.legal_hold is True
        updated = store.set_legal_hold(result.locator, active=False)
        assert updated.legal_hold is False

    def test_is_under_legal_hold(self, store: SqliteLedgerPayloadStore):
        from arnold.workflow.payload_policy import RetentionPayloadPolicy

        policy = RetentionPayloadPolicy(legal_hold=True)
        result = store.store_payload(
            _small_payload(),
            tenant_id="t1",
            workflow_id="w1",
            retention_policy=policy,
        )
        assert store.is_under_legal_hold(result.locator) is True

        # Non-legal-hold payload.
        result2 = store.store_payload(
            _small_payload(), tenant_id="t1", workflow_id="w2"
        )
        assert store.is_under_legal_hold(result2.locator) is False

    def test_is_under_legal_hold_unknown_locator(self, store: SqliteLedgerPayloadStore):
        assert store.is_under_legal_hold("payload:nonexistent") is False

    def test_set_legal_hold_unknown_locator_raises(
        self, store: SqliteLedgerPayloadStore
    ):
        with pytest.raises(PayloadNotFoundError):
            store.set_legal_hold(
                "payload:nonexistent", active=True, principal="admin"
            )


# ── 12. Tombstone markers ──────────────────────────────────────────────────


class TestTombstoneMarkers:
    """Deletion creates tombstone markers; retrieval of tombstoned payloads fails."""

    def test_delete_creates_tombstone(self, store: SqliteLedgerPayloadStore):
        result = store.store_payload(
            _small_payload(), tenant_id="t1", workflow_id="w1"
        )
        evidence = store.delete_payload(
            result.locator, principal="admin", reason="cleanup"
        )
        assert isinstance(evidence, DeletionEvidence)
        assert evidence.deleted_by == "admin"
        assert evidence.reason == "cleanup"

    def test_tombstoned_payload_rejected_on_retrieval(
        self, store: SqliteLedgerPayloadStore
    ):
        result = store.store_payload(
            _small_payload(), tenant_id="t1", workflow_id="w1"
        )
        store.delete_payload(result.locator, principal="admin")
        with pytest.raises(PayloadTombstoneError):
            store.retrieve_payload(
                result.locator,
                access_context=AccessContext(tenant_id="t1", workflow_id="w1"),
            )

    def test_tombstoned_payload_still_queryable(
        self, store: SqliteLedgerPayloadStore
    ):
        result = store.store_payload(
            _small_payload(), tenant_id="t1", workflow_id="w1"
        )
        store.delete_payload(result.locator, principal="admin")
        # get_stored_payload should still work for tombstoned payloads.
        stored = store.get_stored_payload(result.locator)
        assert stored.locator == result.locator
        # The digest has changed (content replaced with deletion evidence).
        assert stored.digest != result.digest

    def test_legal_hold_blocks_deletion(self, store: SqliteLedgerPayloadStore):
        from arnold.workflow.payload_policy import RetentionPayloadPolicy

        policy = RetentionPayloadPolicy(legal_hold=True)
        result = store.store_payload(
            _small_payload(),
            tenant_id="t1",
            workflow_id="w1",
            retention_policy=policy,
        )
        with pytest.raises(PayloadLegalHoldError):
            store.delete_payload(result.locator, principal="admin")

    def test_legal_hold_set_via_method_blocks_deletion(
        self, store: SqliteLedgerPayloadStore
    ):
        result = store.store_payload(
            _small_payload(), tenant_id="t1", workflow_id="w1"
        )
        store.set_legal_hold(result.locator, active=True, principal="lawyer")
        with pytest.raises(PayloadLegalHoldError):
            store.delete_payload(result.locator, principal="admin")

    def test_clear_legal_hold_allows_deletion(
        self, store: SqliteLedgerPayloadStore
    ):
        result = store.store_payload(
            _small_payload(), tenant_id="t1", workflow_id="w1"
        )
        store.set_legal_hold(result.locator, active=True)
        store.set_legal_hold(result.locator, active=False)
        # Should succeed now.
        evidence = store.delete_payload(
            result.locator, principal="admin", reason="cleared hold"
        )
        assert evidence.deleted_by == "admin"

    def test_delete_unknown_locator_raises(self, store: SqliteLedgerPayloadStore):
        with pytest.raises(PayloadNotFoundError):
            store.delete_payload("payload:nonexistent", principal="admin")


# ── 13. Deletion evidence ──────────────────────────────────────────────────


class TestDeletionEvidence:
    """DeletionEvidence records who deleted, when, and why."""

    def test_deletion_evidence_captures_principal(
        self, store: SqliteLedgerPayloadStore
    ):
        result = store.store_payload(
            _small_payload(), tenant_id="t1", workflow_id="w1"
        )
        evidence = store.delete_payload(
            result.locator, principal="agent-007", reason="policy cleanup"
        )
        assert evidence.deleted_by == "agent-007"
        assert evidence.reason == "policy cleanup"
        assert evidence.deleted_at_ns > 0

    def test_get_deletion_evidence_returns_none_for_live_payload(
        self, store: SqliteLedgerPayloadStore
    ):
        result = store.store_payload(
            _small_payload(), tenant_id="t1", workflow_id="w1"
        )
        evidence = store.get_deletion_evidence(result.locator)
        assert evidence is None

    def test_get_deletion_evidence_returns_record_for_tombstone(
        self, store: SqliteLedgerPayloadStore
    ):
        result = store.store_payload(
            _small_payload(), tenant_id="t1", workflow_id="w1"
        )
        store.delete_payload(
            result.locator, principal="auditor", reason="compliance"
        )
        evidence = store.get_deletion_evidence(result.locator)
        assert evidence is not None
        assert evidence.deleted_by == "auditor"
        assert evidence.reason == "compliance"

    def test_get_deletion_evidence_none_for_unknown_locator(
        self, store: SqliteLedgerPayloadStore
    ):
        assert store.get_deletion_evidence("payload:nonexistent") is None


# ── 14. Fail-closed encryption with key version ────────────────────────────


class TestFailClosedEncryptionKeyVersion:
    """Encryption provider fails closed when a specific key version is unavailable.

    The key-version check in :meth:`EncryptionProvider.is_available` rejects
    protected payloads when an explicit key version does not match the
    provider's configured version.  When no key version is specified
    (``None``), the check falls through to scope availability only.
    """

    def test_protected_with_wrong_key_version_explicit_fails_closed(
        self, db_path: Path
    ):
        backing = SqliteAttemptLedgerStore(db_path)
        provider = StaticKeyEncryptionProvider(key_version="v2")
        store = SqliteLedgerPayloadStore(backing, encryption_provider=provider)
        # Call is_available with an explicit mismatched key_version.
        result = provider.is_available(
            EncryptionScope.TENANT_KEY,
            tenant_id="t1",
            workflow_id="w1",
            key_version="v1",
        )
        assert result is False

    def test_protected_with_matching_key_version_succeeds(
        self, db_path: Path
    ):
        backing = SqliteAttemptLedgerStore(db_path)
        provider = StaticKeyEncryptionProvider(key_version="v2")
        store = SqliteLedgerPayloadStore(backing, encryption_provider=provider)
        # Matching key_version — available.
        result = provider.is_available(
            EncryptionScope.TENANT_KEY,
            tenant_id="t1",
            workflow_id="w1",
            key_version="v2",
        )
        assert result is True

    def test_protected_with_no_key_version_specified_succeeds(
        self, db_path: Path
    ):
        backing = SqliteAttemptLedgerStore(db_path)
        provider = StaticKeyEncryptionProvider(key_version="v2")
        store = SqliteLedgerPayloadStore(backing, encryption_provider=provider)
        # No explicit key_version — scope check passes.
        result = provider.is_available(
            EncryptionScope.TENANT_KEY,
            tenant_id="t1",
            workflow_id="w1",
        )
        assert result is True
