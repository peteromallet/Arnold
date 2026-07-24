"""Unit tests for arnold.workflow.durable_refs — DurableRef schema contracts."""

from __future__ import annotations

import pytest

from arnold.workflow import (
    AccessScope,
    AvailabilityClass,
    DurableRef,
    EncryptionScope,
    PrivacyClass,
    RetentionClass,
    validate_durable_ref,
    validate_durable_ref_retrievability,
    validate_durable_ref_secret_exclusion,
    validate_durable_ref_tenant_scope,
)

VALID_SHA256 = "sha256:" + "a" * 64
VALID_SHA256_B = "sha256:" + "b" * 64


# ── DurableRef construction ──────────────────────────────────────────────


class TestDurableRefConstruction:
    """Valid and invalid DurableRef construction paths."""

    def test_minimal_valid_ref(self) -> None:
        ref = DurableRef(
            store_id="s3",
            locator="bucket/object",
            digest=VALID_SHA256,
        )
        assert ref.store_id == "s3"
        assert ref.locator == "bucket/object"
        assert ref.digest == VALID_SHA256
        assert ref.is_retrievable is True

    def test_full_valid_ref(self) -> None:
        ref = DurableRef(
            store_id="gcs",
            locator="my-bucket/path/to/file.json",
            digest=VALID_SHA256,
            schema_type="application/json",
            media_type="application/json",
            size_bytes=1024,
            encryption_scope=EncryptionScope.TENANT_KEY,
            access_scope=AccessScope.TENANT,
            privacy_class=PrivacyClass.CONFIDENTIAL,
            retention_class=RetentionClass.AUDIT,
            availability_class=AvailabilityClass.STANDARD,
            tenant_id="tenant-42",
            workflow_id="wf-7",
        )
        assert ref.store_id == "gcs"
        assert ref.size_bytes == 1024
        assert ref.encryption_scope == EncryptionScope.TENANT_KEY
        assert ref.access_scope == AccessScope.TENANT
        assert ref.privacy_class == PrivacyClass.CONFIDENTIAL
        assert ref.retention_class == RetentionClass.AUDIT
        assert ref.tenant_id == "tenant-42"
        assert ref.workflow_id == "wf-7"
        assert ref.is_encrypted is True
        assert ref.is_legal_hold is False

    def test_empty_store_id_raises(self) -> None:
        with pytest.raises(ValueError, match="store_id"):
            DurableRef(store_id="", locator="x", digest=VALID_SHA256)
        with pytest.raises(ValueError, match="store_id"):
            DurableRef(store_id="   ", locator="x", digest=VALID_SHA256)

    def test_empty_locator_raises(self) -> None:
        with pytest.raises(ValueError, match="locator"):
            DurableRef(store_id="s3", locator="", digest=VALID_SHA256)
        with pytest.raises(ValueError, match="locator"):
            DurableRef(store_id="s3", locator="   ", digest=VALID_SHA256)

    def test_empty_digest_raises(self) -> None:
        with pytest.raises(ValueError, match="digest"):
            DurableRef(store_id="s3", locator="x", digest="")
        with pytest.raises(ValueError, match="digest"):
            DurableRef(store_id="s3", locator="x", digest="   ")

    def test_invalid_digest_format_raises(self) -> None:
        bad_digests = [
            "sha256:abc",  # too short
            "sha256:" + "g" * 64,  # non-hex
            "sha512:" + "a" * 128,
            "md5:" + "a" * 32,
            VALID_SHA256.upper(),  # uppercase
            "plaintext",
            "",
        ]
        for bad in bad_digests:
            with pytest.raises(ValueError, match="digest"):
                DurableRef(store_id="s3", locator="x", digest=bad)

    def test_empty_schema_type_raises(self) -> None:
        with pytest.raises(ValueError, match="schema_type"):
            DurableRef(
                store_id="s3", locator="x", digest=VALID_SHA256, schema_type=""
            )

    def test_negative_size_bytes_raises(self) -> None:
        with pytest.raises(ValueError, match="size_bytes"):
            DurableRef(
                store_id="s3", locator="x", digest=VALID_SHA256, size_bytes=-1
            )

    def test_size_bytes_none_accepted(self) -> None:
        ref = DurableRef(
            store_id="s3", locator="x", digest=VALID_SHA256, size_bytes=None
        )
        assert ref.size_bytes is None

    def test_size_bytes_zero_accepted(self) -> None:
        ref = DurableRef(
            store_id="s3", locator="x", digest=VALID_SHA256, size_bytes=0
        )
        assert ref.size_bytes == 0


# ── Enum enforcement ─────────────────────────────────────────────────────


class TestDurableRefEnumEnforcement:
    """Enum coercion and invalid enum rejection."""

    def test_encryption_scope_string_coerced(self) -> None:
        ref = DurableRef(
            store_id="s3",
            locator="x",
            digest=VALID_SHA256,
            encryption_scope="tenant_key",
        )
        assert ref.encryption_scope == EncryptionScope.TENANT_KEY
        assert isinstance(ref.encryption_scope, EncryptionScope)

    def test_invalid_encryption_scope_raises(self) -> None:
        with pytest.raises(ValueError):
            DurableRef(
                store_id="s3",
                locator="x",
                digest=VALID_SHA256,
                encryption_scope="bogus",
            )

    def test_invalid_access_scope_raises(self) -> None:
        with pytest.raises(ValueError):
            DurableRef(
                store_id="s3",
                locator="x",
                digest=VALID_SHA256,
                access_scope="bogus",
            )

    def test_invalid_privacy_class_raises(self) -> None:
        with pytest.raises(ValueError):
            DurableRef(
                store_id="s3",
                locator="x",
                digest=VALID_SHA256,
                privacy_class="bogus",
            )

    def test_invalid_retention_class_raises(self) -> None:
        with pytest.raises(ValueError):
            DurableRef(
                store_id="s3",
                locator="x",
                digest=VALID_SHA256,
                retention_class="bogus",
            )

    def test_invalid_availability_class_raises(self) -> None:
        with pytest.raises(ValueError):
            DurableRef(
                store_id="s3",
                locator="x",
                digest=VALID_SHA256,
                availability_class="bogus",
            )


# ── Secret exclusion ─────────────────────────────────────────────────────


class TestDurableRefSecretExclusion:
    """Secret-like metadata keys must be rejected."""

    def test_api_key_metadata_rejected(self) -> None:
        with pytest.raises(ValueError, match="api_key"):
            DurableRef(
                store_id="s3",
                locator="x",
                digest=VALID_SHA256,
                metadata={"api_key": "sk-123"},
            )

    def test_password_metadata_rejected(self) -> None:
        with pytest.raises(ValueError, match="password"):
            DurableRef(
                store_id="s3",
                locator="x",
                digest=VALID_SHA256,
                metadata={"password": "hunter2"},
            )

    def test_secret_metadata_rejected(self) -> None:
        with pytest.raises(ValueError, match="secret"):
            DurableRef(
                store_id="s3",
                locator="x",
                digest=VALID_SHA256,
                metadata={"my_secret": "xyz"},
            )

    def test_token_metadata_rejected(self) -> None:
        with pytest.raises(ValueError, match="token"):
            DurableRef(
                store_id="s3",
                locator="x",
                digest=VALID_SHA256,
                metadata={"access_token": "tok"},
            )

    def test_private_key_metadata_rejected(self) -> None:
        with pytest.raises(ValueError, match="private_key"):
            DurableRef(
                store_id="s3",
                locator="x",
                digest=VALID_SHA256,
                metadata={"private_key": "-----BEGIN..."},
            )

    def test_credential_metadata_rejected(self) -> None:
        with pytest.raises(ValueError, match="credential"):
            DurableRef(
                store_id="s3",
                locator="x",
                digest=VALID_SHA256,
                metadata={"credential": "x"},
            )

    def test_bearer_metadata_rejected(self) -> None:
        with pytest.raises(ValueError, match="bearer"):
            DurableRef(
                store_id="s3",
                locator="x",
                digest=VALID_SHA256,
                metadata={"bearer": "x"},
            )

    def test_authorization_metadata_rejected(self) -> None:
        with pytest.raises(ValueError, match="authorization"):
            DurableRef(
                store_id="s3",
                locator="x",
                digest=VALID_SHA256,
                metadata={"authorization": "Bearer x"},
            )

    def test_safe_metadata_accepted(self) -> None:
        ref = DurableRef(
            store_id="s3",
            locator="x",
            digest=VALID_SHA256,
            metadata={"content_type": "json", "version": "1", "owner": "team-a"},
        )
        assert ref.metadata["content_type"] == "json"
        assert ref.metadata["owner"] == "team-a"

    def test_case_insensitive_match(self) -> None:
        with pytest.raises(ValueError, match="Api_Key"):
            DurableRef(
                store_id="s3",
                locator="x",
                digest=VALID_SHA256,
                metadata={"Api_Key": "x"},
            )


# ── Properties ───────────────────────────────────────────────────────────


class TestDurableRefProperties:
    """Property accessors on DurableRef."""

    def test_is_retrievable(self) -> None:
        assert DurableRef(
            store_id="s3", locator="x", digest=VALID_SHA256
        ).is_retrievable is True

    def test_is_encrypted_true(self) -> None:
        ref = DurableRef(
            store_id="s3",
            locator="x",
            digest=VALID_SHA256,
            encryption_scope=EncryptionScope.TENANT_KEY,
        )
        assert ref.is_encrypted is True

    def test_is_encrypted_false(self) -> None:
        ref = DurableRef(
            store_id="s3",
            locator="x",
            digest=VALID_SHA256,
            encryption_scope=EncryptionScope.NONE,
        )
        assert ref.is_encrypted is False

    def test_is_legal_hold_true(self) -> None:
        ref = DurableRef(
            store_id="s3",
            locator="x",
            digest=VALID_SHA256,
            retention_class=RetentionClass.LEGAL_HOLD,
        )
        assert ref.is_legal_hold is True

    def test_is_legal_hold_false(self) -> None:
        ref = DurableRef(
            store_id="s3",
            locator="x",
            digest=VALID_SHA256,
            retention_class=RetentionClass.RUN,
        )
        assert ref.is_legal_hold is False


# ── to_dict ──────────────────────────────────────────────────────────────


class TestDurableRefToDict:
    """Serialization to sidecar-safe dict."""

    def test_minimal_to_dict(self) -> None:
        ref = DurableRef(store_id="s3", locator="key", digest=VALID_SHA256)
        d = ref.to_dict()
        assert d["store_id"] == "s3"
        assert d["locator"] == "key"
        assert d["digest"] == VALID_SHA256
        assert d["schema_type"] == "application/octet-stream"
        assert d["ref_version"] == "arnold.workflow.durable_ref.v1"
        assert "size_bytes" not in d
        assert "tenant_id" not in d

    def test_full_to_dict(self) -> None:
        ref = DurableRef(
            store_id="gcs",
            locator="b/k",
            digest=VALID_SHA256,
            size_bytes=42,
            tenant_id="t1",
            workflow_id="w1",
            metadata={"k": "v"},
        )
        d = ref.to_dict()
        assert d["size_bytes"] == 42
        assert d["tenant_id"] == "t1"
        assert d["workflow_id"] == "w1"
        assert d["metadata"] == {"k": "v"}
        # Enum values are string-encoded
        assert d["encryption_scope"] == "none"
        assert d["access_scope"] == "workflow"

    def test_to_dict_roundtrip_metadata(self) -> None:
        ref = DurableRef(
            store_id="s3",
            locator="x",
            digest=VALID_SHA256,
            metadata={"nested": {"a": 1}, "list": [1, 2, 3]},
        )
        d = ref.to_dict()
        assert d["metadata"]["nested"] == {"a": 1}
        assert d["metadata"]["list"] == [1, 2, 3]


# ── validate_durable_ref_retrievability ──────────────────────────────────


class TestValidateDurableRefRetrievability:
    def test_valid_ref_passes(self) -> None:
        ref = DurableRef(store_id="s3", locator="x", digest=VALID_SHA256)
        assert validate_durable_ref_retrievability(ref) == []

    def test_empty_store_id_fails(self) -> None:
        # Must create an instance that bypasses __post_init__ to test validator
        ref = DurableRef(store_id="s3", locator="x", digest=VALID_SHA256)
        object.__setattr__(ref, "store_id", "")
        issues = validate_durable_ref_retrievability(ref)
        assert len(issues) > 0
        assert any("store_id" in i.lower() for i in issues)

    def test_bad_digest_format_fails(self) -> None:
        ref = DurableRef(store_id="s3", locator="x", digest=VALID_SHA256)
        object.__setattr__(ref, "digest", "bad-hash")
        issues = validate_durable_ref_retrievability(ref)
        assert len(issues) > 0
        assert any("digest" in i.lower() for i in issues)


# ── validate_durable_ref_tenant_scope ────────────────────────────────────


class TestValidateDurableRefTenantScope:
    def test_matching_tenant_passes(self) -> None:
        ref = DurableRef(
            store_id="s3",
            locator="x",
            digest=VALID_SHA256,
            tenant_id="t1",
            workflow_id="w1",
        )
        issues = validate_durable_ref_tenant_scope(ref, expected_tenant_id="t1")
        assert issues == []

    def test_mismatched_tenant_fails(self) -> None:
        ref = DurableRef(
            store_id="s3",
            locator="x",
            digest=VALID_SHA256,
            tenant_id="t1",
        )
        issues = validate_durable_ref_tenant_scope(ref, expected_tenant_id="t2")
        assert len(issues) > 0
        assert any("tenant_id" in i for i in issues)

    def test_matching_workflow_passes(self) -> None:
        ref = DurableRef(
            store_id="s3",
            locator="x",
            digest=VALID_SHA256,
            workflow_id="w1",
        )
        issues = validate_durable_ref_tenant_scope(ref, expected_workflow_id="w1")
        assert issues == []

    def test_mismatched_workflow_fails(self) -> None:
        ref = DurableRef(
            store_id="s3",
            locator="x",
            digest=VALID_SHA256,
            workflow_id="w1",
        )
        issues = validate_durable_ref_tenant_scope(ref, expected_workflow_id="w2")
        assert len(issues) > 0
        assert any("workflow_id" in i for i in issues)

    def test_tenant_scope_without_tenant_id_fails(self) -> None:
        ref = DurableRef(
            store_id="s3",
            locator="x",
            digest=VALID_SHA256,
            access_scope=AccessScope.TENANT,
            tenant_id=None,
        )
        issues = validate_durable_ref_tenant_scope(ref)
        assert len(issues) > 0
        assert any("tenant" in i.lower() for i in issues)

    def test_workflow_scope_without_workflow_id_fails(self) -> None:
        ref = DurableRef(
            store_id="s3",
            locator="x",
            digest=VALID_SHA256,
            access_scope=AccessScope.WORKFLOW,
            workflow_id=None,
        )
        issues = validate_durable_ref_tenant_scope(ref)
        assert len(issues) > 0
        assert any("workflow" in i.lower() for i in issues)

    def test_no_expected_values_passes(self) -> None:
        ref = DurableRef(
            store_id="s3", locator="x", digest=VALID_SHA256, workflow_id="w1"
        )
        issues = validate_durable_ref_tenant_scope(ref)
        assert issues == []


# ── validate_durable_ref_secret_exclusion ────────────────────────────────


class TestValidateDurableRefSecretExclusion:
    def test_clean_metadata_passes(self) -> None:
        ref = DurableRef(
            store_id="s3",
            locator="x",
            digest=VALID_SHA256,
            metadata={"ok": "fine"},
        )
        assert validate_durable_ref_secret_exclusion(ref) == []

    def test_secret_key_detected(self) -> None:
        # Bypass __post_init__ to test the validator directly
        ref = DurableRef(store_id="s3", locator="x", digest=VALID_SHA256)
        object.__setattr__(ref, "metadata", {"api_key": "sk-123"})
        issues = validate_durable_ref_secret_exclusion(ref)
        assert len(issues) > 0
        assert any("api_key" in i for i in issues)

    def test_empty_metadata_passes(self) -> None:
        ref = DurableRef(store_id="s3", locator="x", digest=VALID_SHA256)
        assert validate_durable_ref_secret_exclusion(ref) == []


# ── validate_durable_ref (composite) ─────────────────────────────────────


class TestValidateDurableRef:
    def test_valid_ref_passes_all(self) -> None:
        ref = DurableRef(
            store_id="s3", locator="x", digest=VALID_SHA256, workflow_id="w1"
        )
        assert validate_durable_ref(ref) == []

    def test_composite_catches_retrievability(self) -> None:
        ref = DurableRef(store_id="s3", locator="x", digest=VALID_SHA256)
        object.__setattr__(ref, "store_id", "")
        issues = validate_durable_ref(ref)
        assert len(issues) > 0

    def test_composite_catches_scope(self) -> None:
        ref = DurableRef(
            store_id="s3",
            locator="x",
            digest=VALID_SHA256,
            access_scope=AccessScope.TENANT,
            tenant_id=None,
        )
        issues = validate_durable_ref(ref)
        assert len(issues) > 0
        assert any("tenant" in i.lower() for i in issues)

    def test_composite_catches_secret(self) -> None:
        ref = DurableRef(store_id="s3", locator="x", digest=VALID_SHA256)
        object.__setattr__(ref, "metadata", {"secret_key": "x"})
        issues = validate_durable_ref(ref)
        assert len(issues) > 0
        assert any("secret" in i.lower() for i in issues)

    def test_composite_passes_expected_tenant(self) -> None:
        ref = DurableRef(
            store_id="s3",
            locator="x",
            digest=VALID_SHA256,
            tenant_id="t1",
            workflow_id="w1",
        )
        issues = validate_durable_ref(ref, expected_tenant_id="t1")
        assert issues == []

    def test_composite_fails_mismatched_tenant(self) -> None:
        ref = DurableRef(
            store_id="s3",
            locator="x",
            digest=VALID_SHA256,
            tenant_id="t1",
        )
        issues = validate_durable_ref(ref, expected_tenant_id="t2")
        assert len(issues) > 0


# ── Frozen dataclass ─────────────────────────────────────────────────────


class TestDurableRefImmutability:
    def test_ref_is_frozen(self) -> None:
        ref = DurableRef(store_id="s3", locator="x", digest=VALID_SHA256)
        with pytest.raises(Exception):
            ref.store_id = "new"  # type: ignore[misc]

    def test_metadata_is_readonly(self) -> None:
        ref = DurableRef(
            store_id="s3",
            locator="x",
            digest=VALID_SHA256,
            metadata={"key": "value"},
        )
        with pytest.raises(TypeError):
            ref.metadata["key"] = "other"  # type: ignore[index]


# ── Enum completeness ────────────────────────────────────────────────────


class TestDurableRefEnums:
    def test_privacy_class_values(self) -> None:
        assert PrivacyClass.PUBLIC == "public"
        assert PrivacyClass.INTERNAL == "internal"
        assert PrivacyClass.CONFIDENTIAL == "confidential"
        assert PrivacyClass.RESTRICTED == "restricted"

    def test_availability_class_values(self) -> None:
        assert AvailabilityClass.IMMEDIATE == "immediate"
        assert AvailabilityClass.STANDARD == "standard"
        assert AvailabilityClass.ARCHIVE == "archive"
        assert AvailabilityClass.COLD == "cold"

    def test_encryption_scope_values(self) -> None:
        assert EncryptionScope.NONE == "none"
        assert EncryptionScope.TENANT_KEY == "tenant_key"
        assert EncryptionScope.WORKFLOW_KEY == "workflow_key"
        assert EncryptionScope.FIELD_LEVEL == "field_level"

    def test_retention_class_values(self) -> None:
        assert RetentionClass.EPHEMERAL == "ephemeral"
        assert RetentionClass.RUN == "run"
        assert RetentionClass.AUDIT == "audit"
        assert RetentionClass.LEGAL_HOLD == "legal_hold"

    def test_access_scope_values(self) -> None:
        assert AccessScope.TENANT == "tenant"
        assert AccessScope.WORKFLOW == "workflow"
        assert AccessScope.INVOCATION == "invocation"
        assert AccessScope.RESTRICTED == "restricted"


# ── Default values ───────────────────────────────────────────────────────


class TestDurableRefDefaults:
    def test_default_encryption_scope(self) -> None:
        ref = DurableRef(store_id="s3", locator="x", digest=VALID_SHA256)
        assert ref.encryption_scope == EncryptionScope.NONE

    def test_default_access_scope(self) -> None:
        ref = DurableRef(store_id="s3", locator="x", digest=VALID_SHA256)
        assert ref.access_scope == AccessScope.WORKFLOW

    def test_default_privacy_class(self) -> None:
        ref = DurableRef(store_id="s3", locator="x", digest=VALID_SHA256)
        assert ref.privacy_class == PrivacyClass.INTERNAL

    def test_default_retention_class(self) -> None:
        ref = DurableRef(store_id="s3", locator="x", digest=VALID_SHA256)
        assert ref.retention_class == RetentionClass.RUN

    def test_default_availability_class(self) -> None:
        ref = DurableRef(store_id="s3", locator="x", digest=VALID_SHA256)
        assert ref.availability_class == AvailabilityClass.STANDARD

    def test_default_ref_version(self) -> None:
        ref = DurableRef(store_id="s3", locator="x", digest=VALID_SHA256)
        assert ref.ref_version == "arnold.workflow.durable_ref.v1"

    def test_default_tenant_workflow_ids(self) -> None:
        ref = DurableRef(store_id="s3", locator="x", digest=VALID_SHA256)
        assert ref.tenant_id is None
        assert ref.workflow_id is None
