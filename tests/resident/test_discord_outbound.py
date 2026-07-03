from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

from arnold_pipelines.megaplan.resident.discord import (
    DISCORD_MESSAGE_LIMIT,
    DiscordInboundMessage,
    DiscordOutboundSink,
    split_discord_message,
)
from arnold_pipelines.megaplan.resident.runtime import OutboundMessage


def test_split_discord_message_keeps_chunks_under_limit() -> None:
    text = ("alpha " * 900) + "\n\n" + ("beta " * 900)

    chunks = split_discord_message(text)

    assert len(chunks) > 1
    assert all(0 < len(chunk) <= DISCORD_MESSAGE_LIMIT for chunk in chunks)
    assert "alpha" in chunks[0]
    assert "beta" in chunks[-1]


def test_discord_outbound_sink_sends_long_messages_in_chunks() -> None:
    async def run_case() -> None:
        channel = FakeChannel()
        sink = DiscordOutboundSink(FakeClient(channel))
        metadata: dict[str, object] = {}

        await sink.send(
            OutboundMessage(
                conversation_key="discord:dm:123",
                content="x" * 4500,
                metadata=metadata,
            )
        )

        assert len(channel.sent) == 3
        assert all(len(content) <= DISCORD_MESSAGE_LIMIT for content in channel.sent)
        assert metadata["discord_message_id"] == "discord-1"
        assert metadata["discord_message_ids"] == ["discord-1", "discord-2", "discord-3"]

    class FakeChannel:
        def __init__(self) -> None:
            self.sent: list[str] = []

        async def send(self, content: str) -> SimpleNamespace:
            self.sent.append(content)
            return SimpleNamespace(id=f"discord-{len(self.sent)}")

    class FakeUser:
        def __init__(self, channel: FakeChannel) -> None:
            self.dm_channel = channel

        async def create_dm(self) -> FakeChannel:
            return self.dm_channel

    class FakeClient:
        def __init__(self, channel: FakeChannel) -> None:
            self.user = FakeUser(channel)

        def get_user(self, user_id: int) -> FakeUser:
            assert user_id == 123
            return self.user

    asyncio.run(run_case())


def test_discord_inbound_reply_resolves_escalation_id_from_referenced_message(tmp_path, monkeypatch) -> None:
    repair_data_dir = tmp_path / "repair-data"
    ledger_dir = repair_data_dir / "escalations"
    ledger_dir.mkdir(parents=True)
    (ledger_dir / "escalations.jsonl").write_text(
        json.dumps(
            {
                "event": "delivered",
                "session": "demo-session",
                "escalation_id": "esc-ref-1",
                "message_ids": ["bot-msg-1", "bot-msg-2"],
                "channel_id": "channel-1",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("MEGAPLAN_RESIDENT_REPAIR_DATA_DIR", str(repair_data_dir))

    message = SimpleNamespace(
        id="reply-1",
        content="I approve this.",
        author=SimpleNamespace(id="user-1"),
        guild=None,
        channel=SimpleNamespace(id="channel-1", parent=None),
        reference=SimpleNamespace(message_id="bot-msg-2"),
    )

    inbound = DiscordInboundMessage.from_discord_message(message)
    event = inbound.to_inbound_event()

    assert inbound.referenced_message_id == "bot-msg-2"
    assert inbound.escalation_id == "esc-ref-1"
    assert event.escalation_id == "esc-ref-1"
    assert event.conversation_key == "discord:dm:user-1"
    assert event.raw["discord_reference_message_id"] == "bot-msg-2"


def test_discord_inbound_reply_falls_back_to_escalation_tag(monkeypatch) -> None:
    monkeypatch.delenv("MEGAPLAN_RESIDENT_REPAIR_DATA_DIR", raising=False)
    monkeypatch.delenv("CLOUD_WATCHDOG_REPAIR_DATA_DIR", raising=False)

    message = SimpleNamespace(
        id="reply-2",
        content="[escalation:esc-tag-9] proceed",
        author=SimpleNamespace(id="user-9"),
        guild=None,
        channel=SimpleNamespace(id="channel-9", parent=None),
        reference=None,
    )

    inbound = DiscordInboundMessage.from_discord_message(message)
    event = inbound.to_inbound_event()

    assert inbound.escalation_id == "esc-tag-9"
    assert event.escalation_id == "esc-tag-9"
    assert event.conversation_key == "discord:dm:user-9"


def test_discord_inbound_without_escalation_context_preserves_conversation_key(monkeypatch) -> None:
    monkeypatch.delenv("MEGAPLAN_RESIDENT_REPAIR_DATA_DIR", raising=False)
    monkeypatch.delenv("CLOUD_WATCHDOG_REPAIR_DATA_DIR", raising=False)

    message = SimpleNamespace(
        id="reply-3",
        content="plain reply",
        author=SimpleNamespace(id="user-3"),
        guild=SimpleNamespace(id="guild-1"),
        channel=SimpleNamespace(id="channel-3", parent=None),
        reference=None,
    )

    inbound = DiscordInboundMessage.from_discord_message(message)
    event = inbound.to_inbound_event()

    assert inbound.escalation_id is None
    assert event.escalation_id is None
    assert event.conversation_key == "discord:guild:guild-1:channel:channel-3"
