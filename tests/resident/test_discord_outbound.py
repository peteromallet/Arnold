from __future__ import annotations

import asyncio
import json
import sys
from types import SimpleNamespace

from arnold_pipelines.megaplan.resident.agent_loop import FakeAgentRunner, FakeAgentStep
from arnold_pipelines.megaplan.resident.auth import AuthorizationSubject, ResidentAuthorizer
from arnold_pipelines.megaplan.resident.config import ResidentConfig
from arnold_pipelines.megaplan.resident.discord import (
    DISCORD_MESSAGE_LIMIT,
    DiscordInboundMessage,
    DiscordOutboundSink,
    ResidentDiscordService,
    split_discord_message,
)
from arnold_pipelines.megaplan.resident import discord as discord_module
from arnold_pipelines.megaplan.resident.cli import _resident_store
from arnold_pipelines.megaplan.resident.profile import MegaplanResidentProfile
from arnold_pipelines.megaplan.resident.runtime import InboundEvent, ResidentRuntime
from arnold_pipelines.megaplan.resident.runtime import OutboundMessage
from arnold_pipelines.megaplan.store import FileStore


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

        async def send(self, content: str, **_kwargs: object) -> SimpleNamespace:
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


def test_test_bot_boundary_refuses_operational_outbox_messages() -> None:
    class ExplodingClient:
        def get_user(self, _user_id: int) -> object:
            raise AssertionError("test delivery must fail before resolving a Discord user")

    for environment, bot_role in (("dev", "test"), ("dev", "production"), ("production", "test")):
        for marker in ("resident_reset_notification", "completion_delivery"):
            sink = DiscordOutboundSink(
                ExplodingClient(),
                delivery_environment=environment,
                bot_role=bot_role,
            )
            message = OutboundMessage(
                conversation_key="discord:dm:123",
                content="must not be user-visible",
                metadata={marker: True},
            )

            try:
                asyncio.run(sink.send(message))
            except RuntimeError as exc:
                assert "production bot boundary" in str(exc)
            else:
                raise AssertionError("non-production sink accepted operational Discord delivery")


def test_operational_delivery_requires_production_mode_and_production_bot_role() -> None:
    assert not ResidentConfig(mode="dev", discord_bot_role="test").allows_operational_discord_delivery
    assert not ResidentConfig(
        mode="dev", discord_bot_role="production"
    ).allows_operational_discord_delivery
    assert not ResidentConfig(
        mode="production", discord_bot_role="test"
    ).allows_operational_discord_delivery
    assert ResidentConfig(
        mode="production", discord_bot_role="production"
    ).allows_operational_discord_delivery


def test_production_bot_boundary_allows_operational_outbox_messages() -> None:
    async def run_case() -> None:
        channel = FakeChannel()
        sink = DiscordOutboundSink(
            FakeClient(channel),
            delivery_environment="production",
            bot_role="production",
        )
        await sink.send(
            OutboundMessage(
                conversation_key="discord:dm:123",
                content="verified production delivery",
                metadata={"completion_delivery": True},
            )
        )
        assert channel.sent == ["verified production delivery"]

    class FakeChannel:
        def __init__(self) -> None:
            self.sent: list[str] = []

        async def send(self, content: str, **_kwargs: object) -> SimpleNamespace:
            self.sent.append(content)
            return SimpleNamespace(id="discord-1")

    class FakeUser:
        def __init__(self, channel: FakeChannel) -> None:
            self.dm_channel = channel

    class FakeClient:
        def __init__(self, channel: FakeChannel) -> None:
            self.user = FakeUser(channel)

        def get_user(self, user_id: int) -> FakeUser:
            assert user_id == 123
            return self.user

    asyncio.run(run_case())


def test_ready_sweeps_completion_and_reset_outboxes_before_poll_loop(monkeypatch, tmp_path) -> None:
    calls: list[str] = []

    async def sweep_completions(**_kwargs):
        calls.append("completion")
        return SimpleNamespace(scanned=1, delivered=1, retry_pending=0, failed=0)

    async def sweep_resets(**_kwargs):
        calls.append("reset")
        return SimpleNamespace(
            scanned=1,
            delivered=1,
            retry_pending=0,
            waiting_for_target=0,
            failed=0,
        )

    monkeypatch.setattr(discord_module, "sweep_managed_agent_deliveries", sweep_completions)
    monkeypatch.setattr("agentbox.reset_notifications.sweep_reset_notifications", sweep_resets)
    monkeypatch.chdir(tmp_path)

    class Runtime:
        config = ResidentConfig(mode="production", discord_bot_role="production")
        outbound = DiscordOutboundSink(
            delivery_environment="production",
            bot_role="production",
        )
        store = object()

        async def recover_abandoned_turns(self):
            return 0

    class FakeClient:
        def __init__(self, *, intents):
            self.events = {}
            self.user = SimpleNamespace(id=1)
            self.guilds = []
            self.loop = asyncio.get_running_loop()

        def event(self, callback):
            self.events[callback.__name__] = callback
            return callback

        async def start(self, _token):
            await self.events["on_ready"]()
            await asyncio.sleep(0)

        def is_closed(self):
            return True

    class FakeCommandTree:
        def __init__(self, _client):
            self.registered = []

        def command(self, *, name, description):
            def decorate(callback):
                self.registered.append((name, description, callback))
                return callback

            return decorate

        async def sync(self):
            calls.append("command-sync")
            return [
                SimpleNamespace(name=name)
                for name, _description, _callback in self.registered
            ]

    fake_discord = SimpleNamespace(
        Intents=SimpleNamespace(default=lambda: SimpleNamespace(message_content=False)),
        Client=FakeClient,
        app_commands=SimpleNamespace(CommandTree=FakeCommandTree),
    )
    monkeypatch.setitem(sys.modules, "discord", fake_discord)

    service = ResidentDiscordService(runtime=Runtime(), token="test-token", transcriber=object())
    asyncio.run(service.start())

    assert calls == ["command-sync", "completion", "reset"]


def test_production_container_can_explicitly_reuse_durable_file_store(monkeypatch, tmp_path) -> None:
    store_root = tmp_path / "resident-state"
    monkeypatch.setenv("MEGAPLAN_RESIDENT_STORE_ROOT", str(store_root))

    store = _resident_store(
        tmp_path,
        SimpleNamespace(store_root=None, mode="production", profile=None),
    )

    assert isinstance(store, FileStore)
    assert store.root == store_root.resolve()


def test_discord_outbound_sink_replies_to_referenced_inbound_message() -> None:
    async def run_case() -> None:
        channel = FakeChannel()
        sink = DiscordOutboundSink(FakeClient(channel))
        metadata: dict[str, object] = {"discord_reply_to_message_id": "456"}

        await sink.send(
            OutboundMessage(
                conversation_key="discord:dm:123",
                content="reply",
                metadata=metadata,
            )
        )

        assert channel.sent == [("reply", {"reference": "partial:456", "mention_author": False})]
        assert metadata["discord_message_id"] == "discord-1"

    class FakeChannel:
        def __init__(self) -> None:
            self.sent: list[tuple[str, dict[str, object]]] = []

        def get_partial_message(self, message_id: int) -> str:
            return f"partial:{message_id}"

        async def send(self, content: str, **kwargs: object) -> SimpleNamespace:
            self.sent.append((content, kwargs))
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


def test_resident_runtime_sets_discord_reply_target_on_final_response(tmp_path) -> None:
    async def run_case() -> None:
        store = FileStore(tmp_path / "store")
        config = ResidentConfig(allowed_user_ids=("user-1",), burst_idle_delay_s=0, burst_max_delay_s=1)
        authorizer = ResidentAuthorizer(config)
        outbound = CapturingOutbound()
        runtime = ResidentRuntime(
            config=config,
            authorizer=authorizer,
            store=store,
            profile=MegaplanResidentProfile(store=store, authorizer=authorizer, config=config),
            runner=FakeAgentRunner([FakeAgentStep.final("bot reply")]),
            outbound=outbound,
        )

        await runtime.receive(
            InboundEvent(
                idempotency_key="discord:message:456",
                conversation_key="discord:dm:user-1",
                subject=AuthorizationSubject(user_id="user-1", guild_id=None, channel_id="user-1"),
                content="hello",
                raw={"discord_message_id": "456", "dm_user_id": "user-1"},
            )
        )
        await runtime.coalescer.flush_all()

        assert outbound.sent
        assert outbound.sent[-1].metadata["discord_reply_to_message_id"] == "456"
        assert outbound.processing == [("discord:dm:user-1", ["456"])]
        assert outbound.sent[-1].metadata["discord_processing_message_ids"] == ["456"]

    class CapturingOutbound:
        def __init__(self) -> None:
            self.sent: list[OutboundMessage] = []
            self.processing: list[tuple[str, list[str]]] = []

        async def mark_processing(
            self, *, conversation_key: str, message_ids: list[str], turn_id: str | None = None
        ) -> None:
            self.processing.append((conversation_key, message_ids))

        async def send(self, message: OutboundMessage) -> None:
            self.sent.append(message)

    asyncio.run(run_case())


def test_rejected_inbound_never_starts_a_working_reaction(tmp_path) -> None:
    async def run_case() -> None:
        store = FileStore(tmp_path / "store")
        config = ResidentConfig(allowed_user_ids=("user-1",), burst_idle_delay_s=0, burst_max_delay_s=1)
        authorizer = ResidentAuthorizer(config)

        class CapturingOutbound:
            def __init__(self) -> None:
                self.processing: list[tuple[str, list[str]]] = []

            async def mark_processing(
                self, *, conversation_key: str, message_ids: list[str], turn_id: str | None = None
            ) -> None:
                self.processing.append((conversation_key, message_ids))

            async def send(self, message: OutboundMessage) -> None:
                raise AssertionError("rejected inbound must not send a reply")

        outbound = CapturingOutbound()
        runtime = ResidentRuntime(
            config=config,
            authorizer=authorizer,
            store=store,
            profile=MegaplanResidentProfile(store=store, authorizer=authorizer, config=config),
            runner=FakeAgentRunner([FakeAgentStep.final("must not run")]),
            outbound=outbound,
        )

        await runtime.receive(
            InboundEvent(
                idempotency_key="discord:message:rejected",
                conversation_key="discord:dm:user-2",
                subject=AuthorizationSubject(user_id="user-2", guild_id=None, channel_id="user-2"),
                content="not authorized",
                raw={"discord_message_id": "rejected", "dm_user_id": "user-2"},
            )
        )
        await runtime.coalescer.flush_all()
        assert outbound.processing == []

    asyncio.run(run_case())


def test_discord_outbound_sink_replies_and_reacts_to_source_message() -> None:
    async def run_case() -> None:
        source = FakePartialMessage()
        channel = FakeChannel(source)
        sink = DiscordOutboundSink(FakeClient(channel))
        metadata: dict[str, object] = {"discord_reply_to_message_id": "456"}

        await sink.send(
            OutboundMessage(
                conversation_key="discord:dm:123",
                content="reply text",
                metadata=metadata,
            )
        )

        assert channel.partial_message_ids == [456, 456, 456]
        assert channel.sent == [("reply text", {"reference": source, "mention_author": False})]
        assert source.reactions == ["☑️"]

    class FakePartialMessage:
        def __init__(self) -> None:
            self.reactions: list[str] = []

        async def add_reaction(self, emoji: str) -> None:
            self.reactions.append(emoji)

        async def remove_reaction(self, emoji: str) -> None:
            if emoji in self.reactions:
                self.reactions.remove(emoji)

    class FakeChannel:
        def __init__(self, source: FakePartialMessage) -> None:
            self.source = source
            self.partial_message_ids: list[int] = []
            self.sent: list[tuple[str, dict[str, object]]] = []

        def get_partial_message(self, message_id: int) -> FakePartialMessage:
            self.partial_message_ids.append(message_id)
            return self.source

        async def send(self, content: str, **kwargs: object) -> SimpleNamespace:
            self.sent.append((content, kwargs))
            return SimpleNamespace(id="discord-reply")

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
