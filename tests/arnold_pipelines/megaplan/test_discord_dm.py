from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from arnold_pipelines.megaplan.discord_dm import DISCORD_MESSAGE_LIMIT, render_discord_dm, send_discord_dm


def test_render_discord_dm_formats_fields_links_and_next_action() -> None:
    payload = {
        "title": "Megaplan chain complete - chain-1",
        "summary": "Operation chain-1 completed with state succeeded.",
        "fields": [
            {"label": "Operation", "value": "chain-1", "style": "code"},
            {"label": "State", "value": "succeeded", "style": "code"},
            {"label": "Tiers tried", "value": ["deepseek:flash", "codex:gpt-5.5"], "style": "code_list", "joiner": " -> "},
        ],
        "links": [{"label": "PR", "url": "https://github.com/example/repo/pull/42"}],
        "next_action": "Review the PR and run `agentbox cleanup survey`.",
    }

    rendered = render_discord_dm(payload)

    assert rendered == [
        "\n".join(
            [
                "Megaplan chain complete - chain-1",
                "",
                "Operation chain-1 completed with state succeeded.",
                "**Operation:** `chain-1`",
                "**State:** `succeeded`",
                "**Tiers tried:** `deepseek:flash` -> `codex:gpt-5.5`",
                "**Links:** PR: <https://github.com/example/repo/pull/42>",
                "**Next action:** Review the PR and run `agentbox cleanup survey`.",
            ]
        )
    ]


def test_render_discord_dm_splits_messages_over_discord_limit() -> None:
    payload = {
        "title": "Megaplan needs human review - demo",
        "fields": [
            {"label": "Summary", "value": "x" * (DISCORD_MESSAGE_LIMIT + 300)},
        ],
        "next_action": "Inspect the failure.",
    }

    rendered = render_discord_dm(payload)

    assert len(rendered) >= 2
    assert all(len(chunk) <= DISCORD_MESSAGE_LIMIT for chunk in rendered)
    assert rendered[0].startswith("Megaplan needs human review - demo")
    assert rendered[-1].endswith("**Next action:** Inspect the failure.")


def test_render_discord_dm_redacts_secret_values_in_rendered_chunks() -> None:
    payload = {
        "title": "Megaplan needs human review - demo",
        "summary": "Authorization: Bearer bearer-secret-token-value",
        "fields": [
            {"label": "Command", "value": "export API_TOKEN=supersecret"},
            {"label": "URL", "value": "https://example.test?token=abcdef1234567890"},
        ],
    }

    rendered = render_discord_dm(payload)
    joined = "\n".join(rendered)

    assert "bearer-secret-token-value" not in joined
    assert "supersecret" not in joined
    assert "abcdef1234567890" not in joined
    assert "***REDACTED***" in joined


def test_send_discord_dm_degrades_when_config_missing() -> None:
    result = send_discord_dm({"title": "Megaplan test"}, env={})

    assert result["ok"] is False
    assert result["reason"] == "missing_config"
    assert result["missing"] == ["DISCORD_BOT_TOKEN", "DISCORD_DM_USER_ID"]


def test_send_discord_dm_suppresses_pytest_fixture_before_network() -> None:
    def exploding_opener(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("test fixture notification reached the network")

    result = send_discord_dm(
        {
            "title": "Megaplan needs human review - demo-chain",
            "workspace": "/tmp/pytest-of-root/pytest-411/test_gate0/ws",
        },
        env={"DISCORD_BOT_TOKEN": "configured", "DISCORD_DM_USER_ID": "123"},
        opener=exploding_opener,
    )

    assert result["ok"] is False
    assert result["reason"] == "test_execution_suppressed"
    assert result["suppression_reason"] == "pytest_workspace:workspace"


def test_send_discord_dm_posts_dm_channel_then_messages() -> None:
    requests: list[dict[str, Any]] = []

    class _FakeResponse:
        def __init__(self, payload: dict[str, Any]) -> None:
            self._payload = payload

        def read(self) -> bytes:
            return json.dumps(self._payload).encode("utf-8")

        def __enter__(self) -> "_FakeResponse":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    def fake_urlopen(req, timeout=10):
        requests.append(
            {
                "url": req.full_url,
                "auth": req.get_header("Authorization"),
                "body": json.loads(req.data.decode("utf-8")),
                "timeout": timeout,
            }
        )
        if req.full_url.endswith("/users/@me/channels"):
            return _FakeResponse({"id": "dm-channel-1"})
        return _FakeResponse({"id": f"msg-{len(requests)}"})

    result = send_discord_dm(
        {
            "title": "Megaplan chain complete - chain-1",
            "fields": [{"label": "Operation", "value": "chain-1", "style": "code"}],
        },
        env={
            "DISCORD_BOT_TOKEN": "token-123",
            "DISCORD_DM_USER_ID": "user-456",
        },
        opener=fake_urlopen,
    )

    assert result == {
        "ok": True,
        "channel_id": "dm-channel-1",
        "message_ids": ["msg-2"],
        "message_count": 1,
    }
    assert requests[0]["url"].endswith("/users/@me/channels")
    assert requests[0]["body"] == {"recipient_id": "user-456"}
    assert requests[1]["url"].endswith("/channels/dm-channel-1/messages")
    assert requests[1]["auth"] == "Bot token-123"
    assert "Megaplan chain complete - chain-1" in requests[1]["body"]["content"]


def test_send_discord_dm_redacts_payload_before_delivery() -> None:
    requests: list[dict[str, Any]] = []

    class _FakeResponse:
        def __init__(self, payload: dict[str, Any]) -> None:
            self._payload = payload

        def read(self) -> bytes:
            return json.dumps(self._payload).encode("utf-8")

        def __enter__(self) -> "_FakeResponse":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    def fake_urlopen(req, timeout=10):
        requests.append(json.loads(req.data.decode("utf-8")))
        if req.full_url.endswith("/users/@me/channels"):
            return _FakeResponse({"id": "dm-channel-1"})
        return _FakeResponse({"id": f"msg-{len(requests)}"})

    result = send_discord_dm(
        {
            "title": "Megaplan needs human review - chain-1",
            "summary": "Authorization: Bearer bearer-secret-token-value",
            "fields": [{"label": "Token", "value": "export API_TOKEN=supersecret"}],
        },
        env={
            "DISCORD_BOT_TOKEN": "token-123",
            "DISCORD_DM_USER_ID": "user-456",
        },
        opener=fake_urlopen,
    )

    assert result["ok"] is True
    delivered = requests[1]["content"]
    assert "bearer-secret-token-value" not in delivered
    assert "supersecret" not in delivered
    assert "***REDACTED***" in delivered


def test_send_discord_dm_returns_chunked_message_ids_without_secret_bearing_fields() -> None:
    requests: list[dict[str, Any]] = []
    payload = {
        "title": "Megaplan needs human review - chain-1",
        "summary": "Authorization: Bearer bearer-secret-token-value",
        "fields": [
            {"label": "Summary", "value": "x" * (DISCORD_MESSAGE_LIMIT + 300)},
            {"label": "Token", "value": "export API_TOKEN=supersecret"},
        ],
    }
    expected_messages = render_discord_dm(payload)

    class _FakeResponse:
        def __init__(self, payload: dict[str, Any]) -> None:
            self._payload = payload

        def read(self) -> bytes:
            return json.dumps(self._payload).encode("utf-8")

        def __enter__(self) -> "_FakeResponse":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    def fake_urlopen(req, timeout=10):
        requests.append(
            {
                "url": req.full_url,
                "headers": dict(req.header_items()),
                "body": json.loads(req.data.decode("utf-8")),
                "timeout": timeout,
            }
        )
        if req.full_url.endswith("/users/@me/channels"):
            return _FakeResponse({"id": "dm-channel-1"})
        return _FakeResponse({"id": f"msg-{len(requests) - 1}"})

    result = send_discord_dm(
        payload,
        env={
            "DISCORD_BOT_TOKEN": "token-123",
            "DISCORD_DM_USER_ID": "user-456",
        },
        opener=fake_urlopen,
    )

    assert result["ok"] is True
    assert result["channel_id"] == "dm-channel-1"
    assert result["message_ids"] == [f"msg-{idx}" for idx in range(1, len(expected_messages) + 1)]
    assert result["message_count"] == len(expected_messages)
    assert "Authorization" not in result
    assert "headers" not in result
    assert "body" not in result
    assert "token-123" not in json.dumps(result)
    assert "supersecret" not in json.dumps(result)
    assert "bearer-secret-token-value" not in json.dumps(result)
