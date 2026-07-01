from __future__ import annotations

from types import SimpleNamespace

import pytest

from arnold_pipelines.megaplan.resident.discord import (
    DISCORD_MESSAGE_LIMIT,
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


@pytest.mark.asyncio
async def test_discord_outbound_sink_sends_long_messages_in_chunks() -> None:
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
