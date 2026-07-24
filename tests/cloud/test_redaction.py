from __future__ import annotations

from arnold_pipelines.megaplan.cloud.redact import (
    REDACTION,
    redact_payload,
    redact_text,
    redaction_enabled,
    stream_redact,
)


class _FakeStdout:
    def __init__(self, chunks: list[str]) -> None:
        self._chunks = list(chunks)
        self._tail = ""

    def readline(self) -> str:
        if self._chunks:
            return self._chunks.pop(0)
        return ""

    def read(self) -> str:
        tail = self._tail
        self._tail = ""
        return tail


class _FakeProc:
    def __init__(self, chunks: list[str]) -> None:
        self.stdout = _FakeStdout(chunks)


def test_redaction_enabled_defaults_on_and_supports_explicit_opt_out() -> None:
    assert redaction_enabled({}) is True
    assert redaction_enabled({"ARNOLD_REDACTION_ENABLED": "1"}) is True
    assert redaction_enabled({"ARNOLD_REDACTION_ENABLED": "false"}) is False

    text = "Authorization: Bearer sk-proj-abcdefghijklmnopqrstuvwxyz123456"
    assert redact_text(text, env={"ARNOLD_REDACTION_ENABLED": "0"}) == text


def test_redact_text_masks_secret_patterns() -> None:
    private_key = (
        "-----BEGIN OPENSSH PRIVATE KEY-----\n"
        "private-material\n"
        "-----END OPENSSH PRIVATE KEY-----"
    )
    text = "\n".join(
        [
            "curl --api-key sk-proj-abcdefghijklmnopqrstuvwxyz123456",
            "Authorization: Bearer bearer-secret-token-value",
            "postgres://arnold:supersecret@db.example.internal/repair",
            "https://example.com/hook?access_token=abc123token&mode=repair",
            "bot123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi",
            "discord=MTAxMi4xMjM0NTY3ODkw.aBcDeF.ghijklmnopqrstuvwxyz1234",
            private_key,
            "export OPENAI_API_KEY=sk-live-abcdefghijklmnopqrstuvwxyz123456",
        ]
    )

    redacted = redact_text(text)

    assert "sk-proj-abcdefghijklmnopqrstuvwxyz123456" not in redacted
    assert "bearer-secret-token-value" not in redacted
    assert "supersecret" not in redacted
    assert "abc123token" not in redacted
    assert "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi" not in redacted
    assert "ghijklmnopqrstuvwxyz1234" not in redacted
    assert "OPENSSH PRIVATE KEY" not in redacted
    assert REDACTION in redacted


def test_redact_text_masks_secret_names_and_env_shaped_strings() -> None:
    env = {"DEPLOY_TOKEN": "literal-secret-value-12345"}
    text = (
        "DEPLOY_TOKEN=literal-secret-value-12345 "
        "export CUSTOM_SECRET=secondary-secret "
        "cmd --token literal-secret-value-12345"
    )

    redacted = redact_text(text, secret_names=["DEPLOY_TOKEN"], env=env)

    assert "literal-secret-value-12345" not in redacted
    assert "secondary-secret" not in redacted
    assert "DEPLOY_TOKEN" in redacted
    assert "--token" in redacted


def test_redact_payload_recursively_masks_nested_values() -> None:
    payload = {
        "summary": "Authorization: Bearer bearer-secret-token-value",
        "nested": {
            "command": "python repair.py --password topsecret",
            "env": ["API_TOKEN=abc1234567890", "safe"],
            "conn": "postgresql://arnold:swordfish@localhost:5432/app",
        },
    }

    redacted = redact_payload(payload)

    assert "bearer-secret-token-value" not in redacted["summary"]
    assert "topsecret" not in redacted["nested"]["command"]
    assert "abc1234567890" not in redacted["nested"]["env"][0]
    assert "swordfish" not in redacted["nested"]["conn"]
    assert redacted["nested"]["env"][1] == "safe"


def test_stream_redact_masks_each_chunk() -> None:
    proc = _FakeProc(
        [
            "Authorization: Bearer bearer-secret-token-value\n",
            "cmd --password swordfish\n",
        ]
    )

    chunks = list(stream_redact(proc, secret_names=[]))

    assert len(chunks) == 2
    assert "bearer-secret-token-value" not in "".join(chunks)
    assert "swordfish" not in "".join(chunks)
