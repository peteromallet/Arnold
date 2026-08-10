"""Unit tests for arnold.workflow.payload_policy — payload classification and retention."""

from __future__ import annotations

import pytest

from arnold.workflow import (
    INLINE_CANONICAL_JSON_SIZE_THRESHOLD_BYTES,
    WBC_INLINE_V1,
    WBC_RETENTION_V1,
    AuditMode,
    InlinePayloadPolicy,
    IsolationLevel,
    PayloadMode,
    RedactionMode,
    RetentionMode,
    RetentionPayloadPolicy,
    TombstoneMode,
    classify_payload_mode,
    compute_canonical_json_size,
    default_inline_policy,
    default_retention_policy,
    validate_inline_payload_policy,
    validate_payload_preservation,
    validate_retention_payload_policy,
)


# ── Constants ────────────────────────────────────────────────────────────


class TestConstants:
    def test_inline_threshold_is_16_kib(self) -> None:
        assert INLINE_CANONICAL_JSON_SIZE_THRESHOLD_BYTES == 16384

    def test_schema_version_strings(self) -> None:
        assert WBC_INLINE_V1 == "wbc.inline.v1"
        assert WBC_RETENTION_V1 == "wbc.retention.v1"


# ── compute_canonical_json_size ──────────────────────────────────────────


class TestComputeCanonicalJsonSize:
    def test_empty_payload(self) -> None:
        from arnold.manifest.manifests import canonical_json

        size = compute_canonical_json_size({})
        assert size == len(canonical_json({}).encode("utf-8"))

    def test_small_payload(self) -> None:
        from arnold.manifest.manifests import canonical_json

        payload = {"key": "value", "num": 42}
        size = compute_canonical_json_size(payload)
        expected = len(canonical_json(payload).encode("utf-8"))
        assert size == expected

    def test_nested_payload(self) -> None:
        payload = {"a": {"b": [1, 2, 3], "c": "hello"}}
        size = compute_canonical_json_size(payload)
        assert size > 0

    def test_size_increases_with_content(self) -> None:
        small = compute_canonical_json_size({"x": "y"})
        large = compute_canonical_json_size({"x": "y" * 1000})
        assert large > small


# ── classify_payload_mode ────────────────────────────────────────────────


class TestClassifyPayloadMode:
    def test_small_payload_is_inline(self) -> None:
        mode = classify_payload_mode({"k": "v"})
        assert mode == PayloadMode.INLINE

    def test_large_payload_is_reference(self) -> None:
        big_value = "x" * (INLINE_CANONICAL_JSON_SIZE_THRESHOLD_BYTES + 100)
        mode = classify_payload_mode({"data": big_value})
        assert mode == PayloadMode.REFERENCE

    def test_exactly_at_threshold_is_inline(self) -> None:
        # Build a payload that lands exactly at the threshold
        # {"k":"<padding>"} needs to be exactly 16384 bytes canonical JSON
        # Try with a key of length 1, value padded
        overhead = len('{"k":""}')
        needed = INLINE_CANONICAL_JSON_SIZE_THRESHOLD_BYTES - overhead
        payload = {"k": "x" * needed}
        assert compute_canonical_json_size(payload) == INLINE_CANONICAL_JSON_SIZE_THRESHOLD_BYTES
        mode = classify_payload_mode(payload)
        assert mode == PayloadMode.INLINE

    def test_one_byte_over_threshold_is_reference(self) -> None:
        overhead = len('{"k":""}')
        needed = INLINE_CANONICAL_JSON_SIZE_THRESHOLD_BYTES - overhead + 1
        payload = {"k": "x" * needed}
        assert compute_canonical_json_size(payload) > INLINE_CANONICAL_JSON_SIZE_THRESHOLD_BYTES
        mode = classify_payload_mode(payload)
        assert mode == PayloadMode.REFERENCE


# ── InlinePayloadPolicy ──────────────────────────────────────────────────


class TestInlinePayloadPolicyConstruction:
    def test_default_policy(self) -> None:
        policy = InlinePayloadPolicy()
        assert policy.threshold_bytes == 16384
        assert policy.schema_version == "wbc.inline.v1"
        assert policy.max_inline_payloads == 128
        assert policy.allow_digest_only is False
        assert policy.is_digest_only_rejected is True

    def test_custom_threshold(self) -> None:
        policy = InlinePayloadPolicy(threshold_bytes=4096)
        assert policy.threshold_bytes == 4096

    def test_negative_threshold_raises(self) -> None:
        with pytest.raises(ValueError, match="threshold_bytes"):
            InlinePayloadPolicy(threshold_bytes=-1)

    def test_negative_max_inline_payloads_raises(self) -> None:
        with pytest.raises(ValueError, match="max_inline_payloads"):
            InlinePayloadPolicy(max_inline_payloads=-1)

    def test_allow_digest_only(self) -> None:
        policy = InlinePayloadPolicy(allow_digest_only=True)
        assert policy.allow_digest_only is True
        assert policy.is_digest_only_rejected is False

    def test_metadata_frozen(self) -> None:
        policy = InlinePayloadPolicy(metadata={"a": 1})
        with pytest.raises(TypeError):
            policy.metadata["a"] = 2  # type: ignore[index]

    def test_frozen_dataclass(self) -> None:
        policy = InlinePayloadPolicy()
        with pytest.raises(Exception):
            policy.threshold_bytes = 0  # type: ignore[misc]


class TestInlinePayloadPolicyClassify:
    def test_classify_small_payload(self) -> None:
        policy = InlinePayloadPolicy()
        assert policy.classify({"k": "v"}) == PayloadMode.INLINE

    def test_classify_large_payload(self) -> None:
        policy = InlinePayloadPolicy()
        big = "x" * (INLINE_CANONICAL_JSON_SIZE_THRESHOLD_BYTES + 100)
        assert policy.classify({"data": big}) == PayloadMode.REFERENCE

    def test_classify_with_custom_threshold(self) -> None:
        policy = InlinePayloadPolicy(threshold_bytes=100)
        assert policy.classify({"k": "v"}) == PayloadMode.INLINE
        assert policy.classify({"k": "x" * 200}) == PayloadMode.REFERENCE

    def test_classify_at_custom_threshold_boundary(self) -> None:
        policy = InlinePayloadPolicy(threshold_bytes=50)
        overhead = len('{"k":""}')
        needed = 50 - overhead
        payload = {"k": "x" * needed}
        assert policy.classify(payload) == PayloadMode.INLINE

        payload2 = {"k": "x" * (needed + 1)}
        assert policy.classify(payload2) == PayloadMode.REFERENCE


class TestInlinePayloadPolicyToDict:
    def test_default_to_dict(self) -> None:
        policy = InlinePayloadPolicy()
        d = policy.to_dict()
        assert d["threshold_bytes"] == 16384
        assert d["schema_version"] == "wbc.inline.v1"
        assert d["max_inline_payloads"] == 128
        assert d["allow_digest_only"] is False
        assert "metadata" not in d

    def test_with_metadata(self) -> None:
        policy = InlinePayloadPolicy(metadata={"k": "v"})
        d = policy.to_dict()
        assert d["metadata"] == {"k": "v"}


# ── RetentionPayloadPolicy ───────────────────────────────────────────────


class TestRetentionPayloadPolicyConstruction:
    def test_default_policy(self) -> None:
        policy = RetentionPayloadPolicy()
        assert policy.retention_mode == RetentionMode.RUN
        assert policy.redaction_mode == RedactionMode.DEFAULT_ON
        assert policy.tombstone_mode == TombstoneMode.MARKER
        assert policy.audit_mode == AuditMode.READ_WRITE
        assert policy.isolation_level == IsolationLevel.WORKFLOW
        assert policy.legal_hold is False
        assert policy.encryption_required is True
        assert policy.secret_exclusion_enforced is True
        assert policy.digest_only_preservation_rejected is True
        assert policy.schema_version == "wbc.retention.v1"

    def test_enum_string_coercion(self) -> None:
        policy = RetentionPayloadPolicy(
            retention_mode="audit",
            redaction_mode="always",
            tombstone_mode="full",
            audit_mode="full",
            isolation_level="tenant",
        )
        assert policy.retention_mode == RetentionMode.AUDIT
        assert policy.redaction_mode == RedactionMode.ALWAYS
        assert policy.tombstone_mode == TombstoneMode.FULL
        assert policy.audit_mode == AuditMode.FULL
        assert policy.isolation_level == IsolationLevel.TENANT

    def test_invalid_enum_raises(self) -> None:
        with pytest.raises(ValueError):
            RetentionPayloadPolicy(retention_mode="bogus")
        with pytest.raises(ValueError):
            RetentionPayloadPolicy(redaction_mode="bogus")
        with pytest.raises(ValueError):
            RetentionPayloadPolicy(tombstone_mode="bogus")
        with pytest.raises(ValueError):
            RetentionPayloadPolicy(audit_mode="bogus")
        with pytest.raises(ValueError):
            RetentionPayloadPolicy(isolation_level="bogus")

    def test_negative_max_retention_seconds_raises(self) -> None:
        with pytest.raises(ValueError, match="max_retention_seconds"):
            RetentionPayloadPolicy(max_retention_seconds=-1)

    def test_frozen_dataclass(self) -> None:
        policy = RetentionPayloadPolicy()
        with pytest.raises(Exception):
            policy.retention_mode = RetentionMode.AUDIT  # type: ignore[misc]

    def test_metadata_frozen(self) -> None:
        policy = RetentionPayloadPolicy(metadata={"k": "v"})
        with pytest.raises(TypeError):
            policy.metadata["k"] = "new"  # type: ignore[index]


class TestRetentionPayloadPolicyProperties:
    def test_effective_retention_run(self) -> None:
        policy = RetentionPayloadPolicy(retention_mode=RetentionMode.RUN)
        assert policy.effective_retention_seconds == 86400

    def test_effective_retention_ephemeral(self) -> None:
        policy = RetentionPayloadPolicy(retention_mode=RetentionMode.EPHEMERAL)
        assert policy.effective_retention_seconds == 0

    def test_effective_retention_audit(self) -> None:
        policy = RetentionPayloadPolicy(retention_mode=RetentionMode.AUDIT)
        assert policy.effective_retention_seconds == 7776000

    def test_effective_retention_legal_hold(self) -> None:
        policy = RetentionPayloadPolicy(
            retention_mode=RetentionMode.RUN, legal_hold=True
        )
        assert policy.effective_retention_seconds == -1

    def test_effective_retention_custom_max(self) -> None:
        policy = RetentionPayloadPolicy(
            retention_mode=RetentionMode.RUN, max_retention_seconds=3600
        )
        assert policy.effective_retention_seconds == 3600

    def test_legal_hold_overrides_max(self) -> None:
        policy = RetentionPayloadPolicy(
            retention_mode=RetentionMode.RUN,
            legal_hold=True,
            max_retention_seconds=3600,
        )
        assert policy.effective_retention_seconds == -1

    def test_is_redaction_enforced(self) -> None:
        assert RetentionPayloadPolicy(redaction_mode=RedactionMode.DEFAULT_ON).is_redaction_enforced is True
        assert RetentionPayloadPolicy(redaction_mode=RedactionMode.ALWAYS).is_redaction_enforced is True
        assert RetentionPayloadPolicy(redaction_mode=RedactionMode.NONE).is_redaction_enforced is False

    def test_is_tombstone_enabled(self) -> None:
        assert RetentionPayloadPolicy(tombstone_mode=TombstoneMode.MARKER).is_tombstone_enabled is True
        assert RetentionPayloadPolicy(tombstone_mode=TombstoneMode.FULL).is_tombstone_enabled is True
        assert RetentionPayloadPolicy(tombstone_mode=TombstoneMode.NONE).is_tombstone_enabled is False

    def test_is_audit_required(self) -> None:
        assert RetentionPayloadPolicy(audit_mode=AuditMode.READ).is_audit_required is True
        assert RetentionPayloadPolicy(audit_mode=AuditMode.READ_WRITE).is_audit_required is True
        assert RetentionPayloadPolicy(audit_mode=AuditMode.FULL).is_audit_required is True
        assert RetentionPayloadPolicy(audit_mode=AuditMode.NONE).is_audit_required is False

    def test_is_legal_hold_active(self) -> None:
        assert RetentionPayloadPolicy(legal_hold=True).is_legal_hold_active is True
        assert RetentionPayloadPolicy(legal_hold=False).is_legal_hold_active is False


class TestRetentionPayloadPolicyToDict:
    def test_default_to_dict(self) -> None:
        policy = RetentionPayloadPolicy()
        d = policy.to_dict()
        assert d["retention_mode"] == "run"
        assert d["redaction_mode"] == "default_on"
        assert d["tombstone_mode"] == "marker"
        assert d["audit_mode"] == "read_write"
        assert d["isolation_level"] == "workflow"
        assert d["legal_hold"] is False
        assert d["encryption_required"] is True
        assert d["secret_exclusion_enforced"] is True
        assert d["digest_only_preservation_rejected"] is True
        assert d["schema_version"] == "wbc.retention.v1"
        assert "max_retention_seconds" not in d
        assert "metadata" not in d

    def test_full_to_dict(self) -> None:
        policy = RetentionPayloadPolicy(
            max_retention_seconds=7200, metadata={"custom": "yes"}
        )
        d = policy.to_dict()
        assert d["max_retention_seconds"] == 7200
        assert d["metadata"] == {"custom": "yes"}


# ── Default policy factories ─────────────────────────────────────────────


class TestDefaultPolicies:
    def test_default_inline_policy(self) -> None:
        policy = default_inline_policy()
        assert policy.threshold_bytes == 16384
        assert policy.allow_digest_only is False
        assert policy.schema_version == "wbc.inline.v1"

    def test_default_retention_policy(self) -> None:
        policy = default_retention_policy()
        assert policy.retention_mode == RetentionMode.RUN
        assert policy.redaction_mode == RedactionMode.DEFAULT_ON
        assert policy.encryption_required is True
        assert policy.secret_exclusion_enforced is True
        assert policy.digest_only_preservation_rejected is True


# ── validate_inline_payload_policy ───────────────────────────────────────


class TestValidateInlinePayloadPolicy:
    def test_small_inline_payload_passes(self) -> None:
        policy = InlinePayloadPolicy()
        issues = validate_inline_payload_policy(policy, {"k": "v"})
        assert issues == []

    def test_large_payload_without_durable_ref_reports_issue(self) -> None:
        policy = InlinePayloadPolicy()
        big = "x" * (INLINE_CANONICAL_JSON_SIZE_THRESHOLD_BYTES + 100)
        issues = validate_inline_payload_policy(policy, {"data": big})
        assert len(issues) > 0
        assert any("exceeds inline threshold" in i.lower() for i in issues)

    def test_large_payload_with_durable_ref_passes(self) -> None:
        policy = InlinePayloadPolicy()
        big = "x" * (INLINE_CANONICAL_JSON_SIZE_THRESHOLD_BYTES + 100)
        issues = validate_inline_payload_policy(
            policy, {"data": big, "_durable_ref": "ref-1"}
        )
        # Should not produce the "exceeds inline threshold" issue
        threshold_issues = [
            i for i in issues if "exceeds inline threshold" in i.lower()
        ]
        assert len(threshold_issues) == 0

    def test_digest_only_payload_rejected(self) -> None:
        policy = InlinePayloadPolicy(allow_digest_only=False)
        issues = validate_inline_payload_policy(
            policy,
            {
                "digest": "sha256:" + "a" * 64,
                "data": "x" * (INLINE_CANONICAL_JSON_SIZE_THRESHOLD_BYTES + 10),
            },
        )
        assert len(issues) > 0
        assert any("digest-only" in i.lower() for i in issues)

    def test_digest_only_allowed_when_policy_permits(self) -> None:
        policy = InlinePayloadPolicy(allow_digest_only=True)
        # Even with a digest-only-looking payload, if allow_digest_only=True
        # the policy won't flag it as digest-only rejection
        issues = validate_inline_payload_policy(
            policy,
            {
                "digest": "sha256:" + "a" * 64,
                "data": "x" * (INLINE_CANONICAL_JSON_SIZE_THRESHOLD_BYTES + 10),
            },
        )
        digest_issues = [i for i in issues if "digest-only" in i.lower()]
        assert len(digest_issues) == 0

    def test_reference_with_durable_ref_and_store_locator_passes_digest_check(self) -> None:
        policy = InlinePayloadPolicy()
        big = "x" * (INLINE_CANONICAL_JSON_SIZE_THRESHOLD_BYTES + 10)
        issues = validate_inline_payload_policy(
            policy,
            {
                "data": big,
                "digest": "sha256:" + "a" * 64,
                "store_id": "s3",
                "locator": "bucket/key",
            },
        )
        # Has store_id + locator, so not flagged as digest-only
        digest_issues = [i for i in issues if "digest-only" in i.lower()]
        assert len(digest_issues) == 0

    def test_durable_ref_via_ref_key_passes(self) -> None:
        policy = InlinePayloadPolicy()
        big = "x" * (INLINE_CANONICAL_JSON_SIZE_THRESHOLD_BYTES + 10)
        issues = validate_inline_payload_policy(
            policy, {"data": big, "ref": "dref-1"}
        )
        threshold_issues = [
            i for i in issues if "exceeds inline threshold" in i.lower()
        ]
        assert len(threshold_issues) == 0


# ── validate_retention_payload_policy ────────────────────────────────────


class TestValidateRetentionPayloadPolicy:
    def test_default_policy_passes(self) -> None:
        policy = RetentionPayloadPolicy()
        issues = validate_retention_payload_policy(policy)
        assert issues == []

    def test_legal_hold_with_ephemeral_raises_issue(self) -> None:
        policy = RetentionPayloadPolicy(
            retention_mode=RetentionMode.EPHEMERAL, legal_hold=True
        )
        issues = validate_retention_payload_policy(policy)
        assert len(issues) > 0
        assert any("legal hold" in i.lower() for i in issues)

    def test_legal_hold_with_run_passes(self) -> None:
        policy = RetentionPayloadPolicy(
            retention_mode=RetentionMode.RUN, legal_hold=True
        )
        issues = validate_retention_payload_policy(policy)
        # Legal hold with RUN is fine; no issue about ephemeral
        ephemeral_issues = [
            i for i in issues if "ephemeral" in i.lower()
        ]
        assert len(ephemeral_issues) == 0

    def test_digest_only_payload_rejected(self) -> None:
        policy = RetentionPayloadPolicy(digest_only_preservation_rejected=True)
        payload = {"digest": "sha256:" + "a" * 64}
        issues = validate_retention_payload_policy(policy, payload=payload)
        assert len(issues) > 0
        assert any("digest-only" in i.lower() for i in issues)

    def test_digest_with_store_id_passes(self) -> None:
        policy = RetentionPayloadPolicy(digest_only_preservation_rejected=True)
        payload = {
            "digest": "sha256:" + "a" * 64,
            "store_id": "s3",
            "locator": "b/k",
        }
        issues = validate_retention_payload_policy(policy, payload=payload)
        digest_issues = [i for i in issues if "digest-only" in i.lower()]
        assert len(digest_issues) == 0

    def test_digest_only_not_rejected_when_disabled(self) -> None:
        policy = RetentionPayloadPolicy(digest_only_preservation_rejected=False)
        payload = {"digest": "sha256:" + "a" * 64}
        issues = validate_retention_payload_policy(policy, payload=payload)
        digest_issues = [i for i in issues if "digest-only" in i.lower()]
        assert len(digest_issues) == 0

    def test_secret_keys_in_payload_rejected(self) -> None:
        policy = RetentionPayloadPolicy(secret_exclusion_enforced=True)
        payload = {"api_key": "sk-123", "data": "ok"}
        issues = validate_retention_payload_policy(policy, payload=payload)
        assert len(issues) > 0
        assert any("api_key" in i for i in issues)

    def test_multiple_secret_keys_all_reported(self) -> None:
        policy = RetentionPayloadPolicy(secret_exclusion_enforced=True)
        payload = {"api_key": "x", "password": "y", "ok": "fine"}
        issues = validate_retention_payload_policy(policy, payload=payload)
        assert len(issues) >= 2

    def test_clean_payload_passes(self) -> None:
        policy = RetentionPayloadPolicy(secret_exclusion_enforced=True)
        payload = {"data": "ok", "meta": "info"}
        issues = validate_retention_payload_policy(policy, payload=payload)
        assert issues == []

    def test_no_payload_passes(self) -> None:
        policy = RetentionPayloadPolicy()
        issues = validate_retention_payload_policy(policy)
        assert issues == []

    def test_secret_exclusion_disabled_skips_check(self) -> None:
        policy = RetentionPayloadPolicy(secret_exclusion_enforced=False)
        payload = {"api_key": "sk-123"}
        issues = validate_retention_payload_policy(policy, payload=payload)
        secret_issues = [i for i in issues if "secret" in i.lower()]
        assert len(secret_issues) == 0


# ── validate_payload_preservation (composite) ────────────────────────────


class TestValidatePayloadPreservation:
    def test_small_clean_payload_passes(self) -> None:
        issues = validate_payload_preservation(payload={"k": "v"})
        assert issues == []

    def test_large_payload_without_ref_reports_issues(self) -> None:
        big = "x" * (INLINE_CANONICAL_JSON_SIZE_THRESHOLD_BYTES + 100)
        issues = validate_payload_preservation(payload={"data": big})
        assert len(issues) > 0
        assert any("exceeds inline threshold" in i.lower() for i in issues)

    def test_digest_only_payload_rejected(self) -> None:
        issues = validate_payload_preservation(
            payload={"digest": "sha256:" + "a" * 64}
        )
        assert len(issues) > 0
        assert any("digest-only" in i.lower() for i in issues)

    def test_secret_keys_rejected(self) -> None:
        issues = validate_payload_preservation(
            payload={"api_key": "sk-123", "data": "ok"}
        )
        assert len(issues) > 0
        assert any("api_key" in i for i in issues)

    def test_custom_policies_used(self) -> None:
        inline = InlinePayloadPolicy(threshold_bytes=50, allow_digest_only=True)
        retention = RetentionPayloadPolicy(
            digest_only_preservation_rejected=False,
            secret_exclusion_enforced=False,
        )
        # Large payload that exceeds custom very small threshold
        issues = validate_payload_preservation(
            inline_policy=inline,
            retention_policy=retention,
            payload={"data": "x" * 200},
        )
        # Should have threshold exceed issue but NOT digest-only (allow_digest_only=True)
        threshold_issues = [
            i for i in issues if "exceeds inline threshold" in i.lower()
        ]
        assert len(threshold_issues) > 0
        # But no digest-only rejection (disabled in both policies)
        digest_issues = [i for i in issues if "digest-only" in i.lower()]
        assert len(digest_issues) == 0

    def test_empty_payload_passes_all(self) -> None:
        issues = validate_payload_preservation(payload={})
        assert issues == []


# ── PayloadMode enum ─────────────────────────────────────────────────────


class TestPayloadMode:
    def test_values(self) -> None:
        assert PayloadMode.INLINE == "inline"
        assert PayloadMode.REFERENCE == "reference"
        assert PayloadMode.DIGEST_ONLY == "digest_only"


# ── Other enums ──────────────────────────────────────────────────────────


class TestEnums:
    def test_retention_mode_values(self) -> None:
        assert RetentionMode.EPHEMERAL == "ephemeral"
        assert RetentionMode.RUN == "run"
        assert RetentionMode.AUDIT == "audit"
        assert RetentionMode.LEGAL_HOLD == "legal_hold"

    def test_redaction_mode_values(self) -> None:
        assert RedactionMode.NONE == "none"
        assert RedactionMode.DEFAULT_ON == "default_on"
        assert RedactionMode.ALWAYS == "always"

    def test_tombstone_mode_values(self) -> None:
        assert TombstoneMode.NONE == "none"
        assert TombstoneMode.MARKER == "marker"
        assert TombstoneMode.FULL == "full"

    def test_audit_mode_values(self) -> None:
        assert AuditMode.NONE == "none"
        assert AuditMode.READ == "read"
        assert AuditMode.READ_WRITE == "read_write"
        assert AuditMode.FULL == "full"

    def test_isolation_level_values(self) -> None:
        assert IsolationLevel.TENANT == "tenant"
        assert IsolationLevel.WORKFLOW == "workflow"
        assert IsolationLevel.INVOCATION == "invocation"
        assert IsolationLevel.SHARED == "shared"
