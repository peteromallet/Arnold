from __future__ import annotations

import json

from arnold.security import (
    REDACTED,
    ActionRequest,
    ActionResult,
    ActionVerdict,
    SecurityPolicy,
    redact_mapping,
    redact_text,
)


def test_action_result_sanitizes_summary_and_metadata() -> None:
    result = ActionResult(
        verdict=ActionVerdict.ALLOW,
        summary="broker used Authorization: Bearer sk-secret-token-1234567890",
        action_id="act_123",
        metadata={
            "api_key": "sk-secret-token-1234567890",
            "detail": "token=sk-secret-token-1234567890",
            "nested": {"password": "super-secret"},
        },
    )

    payload = result.to_json()
    serialized = json.dumps(payload)

    assert "sk-secret-token-1234567890" not in serialized
    assert "super-secret" not in serialized
    assert payload["summary"].endswith(REDACTED)
    assert payload["metadata"]["api_key"] == REDACTED
    assert payload["metadata"]["detail"] == f"token={REDACTED}"
    assert payload["metadata"]["nested"]["password"] == REDACTED


def test_security_policy_denies_push_to_protected_branch() -> None:
    policy = SecurityPolicy()

    decision = policy.evaluate(
        ActionRequest(
            action_type="git_push",
            repo="acme/service",
            branch="refs/heads/main",
        )
    )

    assert decision.verdict is ActionVerdict.DENY
    assert decision.metadata["branch"] == "main"
    assert "protected branch main" in decision.summary


def test_security_policy_requires_approval_for_force_push() -> None:
    policy = SecurityPolicy()

    decision = policy.evaluate(
        ActionRequest(
            action_type="git_push",
            repo="acme/service",
            branch="feature/demo",
            force=True,
        )
    )

    assert decision.verdict is ActionVerdict.APPROVAL_REQUIRED
    assert decision.metadata["force"] is True
    assert "requires approval" in decision.summary


def test_redaction_helpers_scrub_nested_payloads_and_text() -> None:
    payload = redact_mapping(
        {
            "detail": "Authorization: Bearer bearer-secret-value",
            "github_token": "ghp_abcdefghijklmnopqrstuvwxyz123456",
            "nested": [{"secret": "plain-secret"}, "api_key=sk-abcdefghijklmnopqrstuvwxyz"],
        }
    )
    text = redact_text("password=hunter2 and github_pat_abcdefghijklmnopqrstuvwxyz")

    rendered = json.dumps(payload)

    assert "bearer-secret-value" not in rendered
    assert "abcdefghijklmnopqrstuvwxyz" not in rendered
    assert payload["detail"] == f"Authorization: Bearer {REDACTED}"
    assert payload["github_token"] == REDACTED
    assert payload["nested"][0]["secret"] == REDACTED
    assert payload["nested"][1] == f"api_key={REDACTED}"
    assert text == f"password={REDACTED} and {REDACTED}"
