"""Tests for the standalone redaction-policy validator.

Covers:

* DEFAULT_ON and ALWAYS dual-hash behaviour (both redacted + raw prompt hashes
  required);
* NONE imposes no dual-hash requirement;
* ``validate_retention_payload_policy`` with an explicit
  :class:`RetentionPayloadPolicy` rejects every forbidden secret key;
* the validator's standalone status (not wired into CL2 persistence) is
  unmistakable.
"""

from __future__ import annotations

from typing import Any

import pytest

from arnold.critique_ledger.redaction import (
    WIRED_INTO_CL2_PERSISTENCE,
    is_dual_hash_required,
    validate_redaction_policy,
)
from arnold.workflow.payload_policy import (
    RedactionMode,
    RetentionPayloadPolicy,
    validate_retention_payload_policy,
)

# Forbidden secret-key substrings enforced by validate_retention_payload_policy.
_FORBIDDEN_SECRET_KEYS = (
    "api_key",
    "password",
    "secret",
    "token",
    "private_key",
    "credential",
    "bearer",
    "authorization",
)


# ── standalone status ───────────────────────────────────────────────────────


def test_redaction_policy_is_not_wired_into_cl2_persistence() -> None:
    """The standalone status must be explicit and unmistakable."""
    assert WIRED_INTO_CL2_PERSISTENCE is False


def test_validate_redaction_policy_is_importable_and_pure() -> None:
    """validate_redaction_policy is a side-effect-free function."""
    policy = RetentionPayloadPolicy(redaction_mode=RedactionMode.DEFAULT_ON)
    # No payload -> no issues, no side effects.
    assert validate_redaction_policy(policy) == []


# ── DEFAULT_ON dual-hash behaviour ──────────────────────────────────────────


def test_default_on_dual_hash_present_is_clean() -> None:
    policy = RetentionPayloadPolicy(redaction_mode=RedactionMode.DEFAULT_ON)
    payload = {
        "redacted_prompt_hash": "sha256:redacted",
        "raw_prompt_hash": "sha256:raw",
    }
    assert validate_redaction_policy(policy, payload=payload) == []
    assert is_dual_hash_required(policy) is True


def test_default_on_missing_redacted_hash_is_flagged() -> None:
    policy = RetentionPayloadPolicy(redaction_mode=RedactionMode.DEFAULT_ON)
    payload = {"raw_prompt_hash": "sha256:raw"}
    issues = validate_redaction_policy(policy, payload=payload)
    assert len(issues) == 1
    assert "redacted_prompt_hash" in issues[0]


def test_default_on_missing_raw_hash_is_flagged() -> None:
    policy = RetentionPayloadPolicy(redaction_mode=RedactionMode.DEFAULT_ON)
    payload = {"redacted_prompt_hash": "sha256:redacted"}
    issues = validate_redaction_policy(policy, payload=payload)
    assert len(issues) == 1
    assert "raw_prompt_hash" in issues[0]


def test_default_on_both_hashes_missing_yields_two_issues() -> None:
    policy = RetentionPayloadPolicy(redaction_mode=RedactionMode.DEFAULT_ON)
    issues = validate_redaction_policy(policy, payload={})
    assert len(issues) == 2
    joined = " ".join(issues)
    assert "redacted_prompt_hash" in joined
    assert "raw_prompt_hash" in joined


def test_default_on_empty_string_hash_treated_as_missing() -> None:
    policy = RetentionPayloadPolicy(redaction_mode=RedactionMode.DEFAULT_ON)
    payload = {"redacted_prompt_hash": "   ", "raw_prompt_hash": ""}
    issues = validate_redaction_policy(policy, payload=payload)
    assert len(issues) == 2


# ── ALWAYS dual-hash behaviour ──────────────────────────────────────────────


def test_always_dual_hash_present_is_clean() -> None:
    policy = RetentionPayloadPolicy(redaction_mode=RedactionMode.ALWAYS)
    payload = {
        "redacted_prompt_hash": "sha256:redacted",
        "raw_prompt_hash": "sha256:raw",
    }
    assert validate_redaction_policy(policy, payload=payload) == []
    assert is_dual_hash_required(policy) is True


def test_always_missing_redacted_hash_is_flagged() -> None:
    policy = RetentionPayloadPolicy(redaction_mode=RedactionMode.ALWAYS)
    payload = {"raw_prompt_hash": "sha256:raw"}
    issues = validate_redaction_policy(policy, payload=payload)
    assert len(issues) == 1
    assert "redacted_prompt_hash" in issues[0]


def test_always_missing_raw_hash_is_flagged() -> None:
    policy = RetentionPayloadPolicy(redaction_mode=RedactionMode.ALWAYS)
    payload = {"redacted_prompt_hash": "sha256:redacted"}
    issues = validate_redaction_policy(policy, payload=payload)
    assert len(issues) == 1
    assert "raw_prompt_hash" in issues[0]


# ── NONE mode: no dual-hash requirement ─────────────────────────────────────


def test_none_mode_imposes_no_dual_hash_requirement() -> None:
    policy = RetentionPayloadPolicy(redaction_mode=RedactionMode.NONE)
    assert is_dual_hash_required(policy) is False
    # Empty payload is fine under NONE.
    assert validate_redaction_policy(policy, payload={}) == []
    # Even a payload missing both hashes is fine under NONE.
    assert validate_redaction_policy(
        policy, payload={"unrelated": "value"}
    ) == []


# ── validate_retention_payload_policy: forbidden secret keys ────────────────


@pytest.mark.parametrize("forbidden_key", _FORBIDDEN_SECRET_KEYS)
def test_retention_policy_rejects_every_forbidden_secret_key(
    forbidden_key: str,
) -> None:
    """validate_retention_payload_policy with an explicit
    RetentionPayloadPolicy must reject every forbidden secret key."""
    policy = RetentionPayloadPolicy(secret_exclusion_enforced=True)
    payload = {forbidden_key: "leaked-secret-value"}
    issues = validate_retention_payload_policy(policy, payload=payload)
    assert issues, f"forbidden key {forbidden_key!r} was not rejected"
    assert any(forbidden_key in issue for issue in issues)


def test_retention_policy_clean_payload_has_no_secret_issues() -> None:
    policy = RetentionPayloadPolicy(secret_exclusion_enforced=True)
    payload = {
        "redacted_prompt_hash": "sha256:redacted",
        "raw_prompt_hash": "sha256:raw",
        "finding_id": "finding-1",
    }
    secret_issues = [
        i for i in validate_retention_payload_policy(policy, payload=payload)
        if "secret" in i.lower() or "forbidden" in i.lower()
    ]
    assert secret_issues == []


def test_forbidden_secret_keys_are_case_insensitive() -> None:
    """The forbidden-substring match is case-insensitive (lower_key)."""
    policy = RetentionPayloadPolicy(secret_exclusion_enforced=True)
    issues = validate_retention_payload_policy(
        policy, payload={"API_KEY": "x"}
    )
    assert issues
    assert any("API_KEY" in i for i in issues)
