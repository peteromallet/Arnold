from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta

from agentbox.reset_notifications import (
    RESET_FALLBACK_CONVERSATION_ENV,
    list_reset_notifications,
    mark_reset_succeeded,
    prepare_reset_notification,
    sweep_reset_notifications,
)
from arnold_pipelines.megaplan.resident.provenance import DELEGATION_CONTEXT_ENV


def _discord_provenance() -> dict[str, object]:
    return {
        "schema_version": "arnold-resident-delegation-provenance-v1",
        "applicability": "applicable",
        "transport": "discord",
        "resident_conversation_id": "rconv-source",
        "source_record_id": "msg-source",
        "conversation_key": "discord:dm:301463647895683072",
        "discord_message_id": "1525445255711952977",
        "reply_to_message_id": "1525445255711952977",
        "dm_user_id": "301463647895683072",
        "source_kind": "discord_inbound_message",
    }


class _Outbound:
    def __init__(self, *, fail_once: bool = False) -> None:
        self.fail_once = fail_once
        self.sent = []

    async def send(self, message) -> None:
        self.sent.append(message)
        if self.fail_once:
            self.fail_once = False
            raise ConnectionError("provider connection dropped token=not-persisted")
        message.metadata["discord_message_ids"] = [f"reply-{len(self.sent)}"]


def test_reset_confirmation_preserves_discord_provenance_and_is_not_duplicated(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv(DELEGATION_CONTEXT_ENV, json.dumps(_discord_provenance()))
    now = datetime(2026, 7, 11, tzinfo=UTC)
    reservation = prepare_reset_notification(notification_root=tmp_path, now=now)
    mark_reset_succeeded(
        reservation,
        restart_evidence={"service": "agentbox-discord-resident", "backend": "tmux"},
        now=now,
    )
    outbound = _Outbound()

    first = asyncio.run(
        sweep_reset_notifications(outbound=outbound, notification_root=tmp_path, now=now)
    )
    second = asyncio.run(
        sweep_reset_notifications(
            outbound=outbound,
            notification_root=tmp_path,
            now=now + timedelta(minutes=1),
        )
    )

    assert first.delivered == 1
    assert second.delivered == 0
    assert len(outbound.sent) == 1
    message = outbound.sent[0]
    assert message.conversation_key == "discord:dm:301463647895683072"
    assert message.metadata["discord_reply_to_message_id"] == "1525445255711952977"
    assert message.metadata["resident_reset_notification"] is True
    assert message.content == "Discord resident reset complete."
    state = list_reset_notifications(notification_root=tmp_path)
    assert state["delivery_status_counts"] == {"delivered": 1}
    assert state["records"][0]["delivery"]["discord_message_ids"] == ["reply-1"]


def test_manual_reset_uses_truthful_non_reply_fallback(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv(DELEGATION_CONTEXT_ENV, raising=False)
    monkeypatch.setenv(RESET_FALLBACK_CONVERSATION_ENV, "discord:dm:301463647895683072")
    now = datetime(2026, 7, 11, tzinfo=UTC)
    reservation = prepare_reset_notification(notification_root=tmp_path, now=now)
    mark_reset_succeeded(reservation, restart_evidence={"backend": "systemd"}, now=now)
    outbound = _Outbound()

    result = asyncio.run(
        sweep_reset_notifications(outbound=outbound, notification_root=tmp_path, now=now)
    )

    assert result.delivered == 1
    assert outbound.sent[0].conversation_key == "discord:dm:301463647895683072"
    assert "discord_reply_to_message_id" not in outbound.sent[0].metadata
    assert "fallback notification" in outbound.sent[0].content
    state = list_reset_notifications(notification_root=tmp_path)["records"][0]
    assert state["provenance_mode"] == "manual_or_non_discord"
    assert state["delivery"]["status"] == "delivered"


def test_reset_delivery_retry_persists_state_and_reuses_nonce(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv(DELEGATION_CONTEXT_ENV, json.dumps(_discord_provenance()))
    first_now = datetime(2026, 7, 11, tzinfo=UTC)
    reservation = prepare_reset_notification(notification_root=tmp_path, now=first_now)
    mark_reset_succeeded(reservation, restart_evidence={"backend": "tmux"}, now=first_now)
    outbound = _Outbound(fail_once=True)

    first = asyncio.run(
        sweep_reset_notifications(outbound=outbound, notification_root=tmp_path, now=first_now)
    )
    retry = list_reset_notifications(notification_root=tmp_path)["records"][0]["delivery"]
    second = asyncio.run(
        sweep_reset_notifications(
            outbound=outbound,
            notification_root=tmp_path,
            now=first_now + timedelta(seconds=31),
        )
    )
    delivered = list_reset_notifications(notification_root=tmp_path)["records"][0]["delivery"]

    assert first.retry_pending == 1
    assert retry["status"] == "retry_pending"
    assert retry["attempt_count"] == 1
    assert "not-persisted" not in retry["last_error"]
    assert second.delivered == 1
    assert delivered["status"] == "delivered"
    assert delivered["attempt_count"] == 2
    assert outbound.sent[0].metadata["discord_nonce"] == outbound.sent[1].metadata["discord_nonce"]
