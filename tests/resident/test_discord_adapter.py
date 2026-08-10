from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from arnold_pipelines.megaplan.resident.discord import (
    DiscordInboundMessage,
    DiscordOutboundSink,
)
from arnold_pipelines.megaplan.resident.runtime import OutboundMessage


def test_discord_inbound_captures_resolved_reply_snapshot() -> None:
    referenced = SimpleNamespace(
        id="ref-1",
        content="the message being replied to",
        author=SimpleNamespace(id="author-2"),
    )
    message = SimpleNamespace(
        id="m1",
        content="my reply",
        guild=None,
        channel=SimpleNamespace(id="dm-1", parent=None),
        author=SimpleNamespace(id="author-1"),
        reference=SimpleNamespace(message_id="ref-1", resolved=referenced),
    )

    inbound = DiscordInboundMessage.from_discord_message(message)
    event = inbound.to_inbound_event()

    assert inbound.referenced_message_id == "ref-1"
    assert inbound.referenced_message_author_id == "author-2"
    assert inbound.referenced_message_content == "the message being replied to"
    assert event.raw["discord_reference_message_id"] == "ref-1"
    assert event.raw["discord_reference_author_id"] == "author-2"
    assert event.raw["discord_reference_content"] == "the message being replied to"


def test_discord_outbound_replies_to_source_message_and_adds_checkbox_reaction() -> None:
    channel = _FakeChannel()
    sink = DiscordOutboundSink(client=_FakeClient(channel))
    outbound = OutboundMessage(
        conversation_key="discord:dm:42",
        content="resident reply",
        metadata={"discord_reply_to_message_id": "1001", "discord_nonce": "stable-run-nonce"},
    )

    asyncio.run(sink.send(outbound))

    assert channel.sent == [
        {
            "content": "resident reply",
            "reference_id": 1001,
            "mention_author": False,
            "nonce": "stable-run-nonce-0",
        }
    ]
    assert channel.partial_messages[1001].reactions == ["☑️"]
    assert outbound.metadata["discord_message_id"] == "sent-1"
    assert outbound.metadata["discord_message_ids"] == ["sent-1"]


def test_discord_outbound_retry_nonce_deduplicates_reply_accepted_before_response_loss() -> None:
    class _AcceptedThenDisconnectedChannel(_FakeChannel):
        def __init__(self) -> None:
            super().__init__()
            self.accepted_by_nonce: dict[str, SimpleNamespace] = {}
            self.unique_message_count = 0
            self.disconnect_once = True

        async def send(self, content: str, **kwargs: object) -> SimpleNamespace:
            nonce = str(kwargs.get("nonce") or "")
            accepted = self.accepted_by_nonce.get(nonce)
            if accepted is None:
                self.unique_message_count += 1
                accepted = SimpleNamespace(id=f"sent-{self.unique_message_count}")
                self.accepted_by_nonce[nonce] = accepted
            if self.disconnect_once:
                self.disconnect_once = False
                raise ConnectionError("response lost after Discord accepted the message")
            return accepted

    channel = _AcceptedThenDisconnectedChannel()
    sink = DiscordOutboundSink(client=_FakeClient(channel))
    outbound = OutboundMessage(
        conversation_key="discord:dm:42",
        content="resident completion",
        metadata={"discord_reply_to_message_id": "1001", "discord_nonce": "stable-run-nonce"},
    )

    with pytest.raises(ConnectionError, match="response lost"):
        asyncio.run(sink.send(outbound))
    asyncio.run(sink.send(outbound))

    assert channel.unique_message_count == 1
    assert list(channel.accepted_by_nonce) == ["stable-run-nonce-0"]
    assert outbound.metadata["discord_message_ids"] == ["sent-1"]


def test_working_reaction_is_reconciled_to_checkbox_only_after_reply_delivery() -> None:
    channel = _FakeChannel()
    sink = DiscordOutboundSink(client=_FakeClient(channel))

    asyncio.run(
        sink.mark_processing(conversation_key="discord:dm:42", message_ids=["1001", "1001"])
    )
    assert channel.partial_messages[1001].reactions == ["⏳"]

    asyncio.run(
        sink.send(
            OutboundMessage(
                conversation_key="discord:dm:42",
                content="terminal reply",
                metadata={
                    "discord_reply_to_message_id": "1001",
                    "discord_processing_message_ids": ["1001"],
                    "discord_nonce": "terminal-reaction-nonce",
                },
            )
        )
    )

    assert channel.sent[0]["content"] == "terminal reply"
    assert channel.partial_messages[1001].reactions == ["☑️"]


def test_failed_reply_does_not_replace_working_reaction_with_completion() -> None:
    class _FailingChannel(_FakeChannel):
        async def send(self, content: str, **kwargs: object) -> SimpleNamespace:
            raise ConnectionError("Discord unavailable")

    channel = _FailingChannel()
    sink = DiscordOutboundSink(client=_FakeClient(channel))
    asyncio.run(sink.mark_processing(conversation_key="discord:dm:42", message_ids=["1001"]))

    with pytest.raises(ConnectionError, match="unavailable"):
        asyncio.run(
            sink.send(
                OutboundMessage(
                    conversation_key="discord:dm:42",
                    content="terminal reply",
                    metadata={
                        "discord_reply_to_message_id": "1001",
                        "discord_processing_message_ids": ["1001"],
                    },
                )
            )
        )

    assert channel.partial_messages[1001].reactions == ["⏳"]


def test_terminal_reaction_failure_is_retryable_without_duplicate_reply(tmp_path) -> None:
    class _FailOnceMessage(_FakePartialMessage):
        def __init__(self, message_id: int) -> None:
            super().__init__(message_id)
            self.fail_checkbox_once = True

        async def add_reaction(self, emoji: str) -> None:
            if emoji == "☑️" and self.fail_checkbox_once:
                self.fail_checkbox_once = False
                raise ConnectionError("reaction unavailable")
            await super().add_reaction(emoji)

    channel = _FakeChannel(message_type=_FailOnceMessage)
    sink = DiscordOutboundSink(client=_FakeClient(channel), reaction_effect_root=tmp_path / "effects")
    asyncio.run(sink.mark_processing(conversation_key="discord:dm:42", message_ids=["1001"]))
    outbound = OutboundMessage(
        conversation_key="discord:dm:42",
        content="terminal reply",
        metadata={
            "discord_reply_to_message_id": "1001",
            "discord_processing_message_ids": ["1001"],
            "discord_nonce": "retryable-reaction-nonce",
        },
    )

    asyncio.run(sink.send(outbound))
    # Completion was not accepted, so terminal cleanup remains fenced behind
    # it and the source never loses both transition indicators.
    assert channel.partial_messages[1001].reactions == ["⏳"]
    restarted_sink = DiscordOutboundSink(
        client=_FakeClient(channel), reaction_effect_root=tmp_path / "effects"
    )
    asyncio.run(restarted_sink.reconcile_reactions())

    assert len(channel.sent) == 1
    assert channel.partial_messages[1001].reactions == ["☑️"]


class _FakePartialMessage:
    def __init__(self, message_id: int) -> None:
        self.id = message_id
        self.reactions: list[str] = []

    async def add_reaction(self, emoji: str) -> None:
        self.reactions.append(emoji)

    async def remove_reaction(self, emoji: str) -> None:
        if emoji in self.reactions:
            self.reactions.remove(emoji)


class _FakeChannel:
    def __init__(self, message_type: type[_FakePartialMessage] = _FakePartialMessage) -> None:
        self.sent: list[dict[str, object]] = []
        self.partial_messages: dict[int, _FakePartialMessage] = {}
        self.message_type = message_type

    def get_partial_message(self, message_id: int) -> _FakePartialMessage:
        if message_id not in self.partial_messages:
            self.partial_messages[message_id] = self.message_type(message_id)
        return self.partial_messages[message_id]

    async def send(self, content: str, **kwargs: object) -> SimpleNamespace:
        reference = kwargs.get("reference")
        self.sent.append(
            {
                "content": content,
                "reference_id": getattr(reference, "id", None),
                "mention_author": kwargs.get("mention_author"),
                "nonce": kwargs.get("nonce"),
            }
        )
        return SimpleNamespace(id="sent-1")


class _FakeUser:
    def __init__(self, channel: _FakeChannel) -> None:
        self.dm_channel = channel

    async def create_dm(self) -> _FakeChannel:
        return self.dm_channel


class _FakeClient:
    def __init__(self, channel: _FakeChannel) -> None:
        self.user = _FakeUser(channel)

    def get_user(self, user_id: int) -> _FakeUser:
        return self.user
