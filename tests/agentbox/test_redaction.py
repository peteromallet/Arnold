from __future__ import annotations

from agentbox.redaction import redact_payload, redact_text


def test_redact_text_masks_bearer_token() -> None:
    text = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    assert redact_text(text) == "Authorization: Bearer <REDACTED_BEARER_TOKEN>"


def test_redact_text_masks_github_token() -> None:
    token = "ghp_1234567890abcdef1234567890abcdef123456"
    text = f"github token: {token}"
    assert redact_text(text) == "github token: <REDACTED_GITHUB_TOKEN>"


def test_redact_text_masks_discord_bot_token() -> None:
    token = "MTAxMi4xMjM0NTY3ODkw.aBcDeF.ghijklmnopqrstuvwxyz1234"
    text = f"discord token: {token}"
    assert redact_text(text) == "discord token: <REDACTED_DISCORD_BOT_TOKEN>"


def test_redact_text_masks_api_keys() -> None:
    claude = "sk-ant-api03-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    codex = "sk-proj-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    text = f"claude={claude} codex={codex}"
    redacted = redact_text(text)
    assert "<REDACTED_API_KEY>" in redacted
    assert claude not in redacted
    assert codex not in redacted


def test_redact_text_masks_private_key_block() -> None:
    key = (
        "-----BEGIN OPENSSH PRIVATE KEY-----\n"
        "b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAAAMwAAAAtzc2gtZW\n"
        "QyNTUxOQAAACB8JbH5Yq7s2g9k7g4f1z2a3b4c5d6e7f8g9h0i1j2k3l4m5n6o7p8q9r0s1t2u3\n"
        "-----END OPENSSH PRIVATE KEY-----"
    )
    text = f"leaked key:\n{key}"
    redacted = redact_text(text)
    assert "<REDACTED_PRIVATE_KEY>" in redacted
    assert "OPENSSH PRIVATE KEY" not in redacted


def test_redact_text_masks_env_file_paths() -> None:
    text = "loaded secrets from /home/user/project/.env and /tmp/.env.local"
    expected = "loaded secrets from <REDACTED_ENV_PATH> and <REDACTED_ENV_PATH>"
    assert redact_text(text) == expected


def test_redact_payload_recursively_masks_values() -> None:
    payload = {
        "message": "token ghp_1234567890abcdef1234567890abcdef123456 here",
        "nested": {
            "path": "/etc/app/.env",
            "items": [
                "Bearer secret.token.value",
                "safe text",
            ],
        },
    }
    redacted = redact_payload(payload)
    assert "<REDACTED_GITHUB_TOKEN>" in redacted["message"]
    assert "ghp_" not in redacted["message"]
    assert redacted["nested"]["path"] == "<REDACTED_ENV_PATH>"
    assert redacted["nested"]["items"][0] == "Bearer <REDACTED_BEARER_TOKEN>"
    assert redacted["nested"]["items"][1] == "safe text"
