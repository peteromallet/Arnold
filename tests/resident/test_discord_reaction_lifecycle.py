from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
import json
from types import SimpleNamespace

from agentbox.reset_notifications import (
    RESET_NOTIFICATION_ENV,
    mark_reset_succeeded,
    prepare_reset_notification,
)
from arnold_pipelines.megaplan.resident.agent_loop import AgentResponse
from arnold_pipelines.megaplan.resident.auth import AuthorizationSubject, ResidentAuthorizer
from arnold_pipelines.megaplan.resident.config import ResidentConfig
from arnold_pipelines.megaplan.resident.discord import DiscordOutboundSink
from arnold_pipelines.megaplan.resident.profile import MegaplanResidentProfile
from arnold_pipelines.megaplan.resident.runtime import InboundEvent, OutboundMessage, ResidentRuntime
from arnold_pipelines.megaplan.store import FileStore, ResidentConversationInput
from arnold_pipelines.megaplan.resident.provenance import DELEGATION_CONTEXT_ENV


class _Message:
    def __init__(self, message_id: int) -> None:
        self.id = message_id
        self.reactions: list[str] = []
        self.add_calls: list[str] = []
        self.fail_add_once: set[str] = set()

    async def add_reaction(self, emoji: str) -> None:
        self.add_calls.append(emoji)
        if emoji in self.fail_add_once:
            self.fail_add_once.remove(emoji)
            raise ConnectionError(f"{emoji} reaction unavailable")
        if emoji not in self.reactions:
            self.reactions.append(emoji)

    async def remove_reaction(self, emoji: str, _actor: object = None) -> None:
        if emoji in self.reactions:
            self.reactions.remove(emoji)


class _Channel:
    def __init__(self) -> None:
        self.messages: dict[int, _Message] = {}
        self.sent: list[dict[str, object]] = []

    def get_partial_message(self, message_id: int) -> _Message:
        return self.messages.setdefault(message_id, _Message(message_id))

    async def send(self, content: str, **kwargs: object) -> SimpleNamespace:
        self.sent.append({"content": content, **kwargs})
        return SimpleNamespace(id=f"reply-{len(self.sent)}")


class _User:
    def __init__(self, channel: _Channel) -> None:
        self.dm_channel = channel

    async def create_dm(self) -> _Channel:
        return self.dm_channel


class _Client:
    def __init__(self, channel: _Channel) -> None:
        self.user = _User(channel)

    def get_user(self, _user_id: int) -> _User:
        return self.user


class _BlockingRunner:
    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.calls = 0
        self.message_count = 0

    async def run(self, request, _tools) -> AgentResponse:
        self.calls += 1
        self.message_count = len(request.messages)
        self.started.set()
        await self.release.wait()
        return AgentResponse(final_text="finished")


class _ImmediateRunner:
    def __init__(self) -> None:
        self.calls = 0

    async def run(self, _request, _tools) -> AgentResponse:
        self.calls += 1
        return AgentResponse(final_text="replayed exactly once")


def _runtime(tmp_path, sink: object, runner: object) -> ResidentRuntime:
    store = FileStore(tmp_path / "store")
    config = ResidentConfig(
        allowed_user_ids=("42",),
        burst_idle_delay_s=3600,
        burst_max_delay_s=3600,
    )
    authorizer = ResidentAuthorizer(config)
    return ResidentRuntime(
        config=config,
        authorizer=authorizer,
        store=store,
        profile=MegaplanResidentProfile(store=store, authorizer=authorizer, config=config),
        runner=runner,
        outbound=sink,
    )


def _event(message_id: str, content: str = "work") -> InboundEvent:
    return InboundEvent(
        idempotency_key=f"discord:message:{message_id}",
        conversation_key="discord:dm:42",
        subject=AuthorizationSubject(user_id="42", guild_id=None, channel_id="42"),
        content=content,
        raw={"discord_message_id": message_id, "dm_user_id": "42"},
    )


def test_working_starts_at_execution_not_receipt_and_duplicate_event_is_fenced(tmp_path) -> None:
    async def run_case() -> None:
        channel = _Channel()
        sink = DiscordOutboundSink(
            _Client(channel), reaction_effect_root=tmp_path / "reaction-effects"
        )
        runner = _BlockingRunner()
        runtime = _runtime(tmp_path, sink, runner)

        await runtime.receive(_event("1001"))
        await runtime.receive(_event("1001"))
        assert 1001 not in channel.messages  # accepted and coalescing, not processing

        processing = asyncio.create_task(runtime.coalescer.flush_all())
        await runner.started.wait()
        assert channel.messages[1001].reactions == ["⏳"]
        assert runner.calls == 1
        assert runner.message_count == 1

        runner.release.set()
        await processing
        assert channel.messages[1001].reactions == ["☑️"]

        await runtime.receive(_event("1001"))
        await runtime.coalescer.flush_all()
        assert runner.calls == 1
        assert channel.messages[1001].reactions == ["☑️"]

    asyncio.run(run_case())


def test_reaction_failure_is_durable_and_restart_replay_is_idempotent(tmp_path) -> None:
    async def run_case() -> None:
        root = tmp_path / "reaction-effects"
        channel = _Channel()
        source = channel.get_partial_message(1001)
        source.fail_add_once.add("⏳")
        first = DiscordOutboundSink(_Client(channel), reaction_effect_root=root)

        await first.mark_processing(
            conversation_key="discord:dm:42", message_ids=["1001"], turn_id="turn-1"
        )
        assert source.reactions == []
        effect_path = next((root / "effects").glob("*.json"))
        failed = json.loads(effect_path.read_text())
        assert failed["status"] == "pending"
        assert failed["attempt_count"] == 1
        assert failed["last_error_class"] == "ConnectionError"

        restarted = DiscordOutboundSink(_Client(channel), reaction_effect_root=root)
        replay = await restarted.reconcile_reactions()
        duplicate = await asyncio.gather(
            restarted.reconcile_reactions(), restarted.reconcile_reactions()
        )
        assert replay.applied == 1
        assert sum(result.applied for result in duplicate) == 0
        assert source.reactions == ["⏳"]
        assert source.add_calls.count("⏳") == 2  # one failed call, one replay

    asyncio.run(run_case())


def test_burst_marks_every_source_but_completes_only_reply_target(tmp_path) -> None:
    async def run_case() -> None:
        channel = _Channel()
        sink = DiscordOutboundSink(
            _Client(channel), reaction_effect_root=tmp_path / "reaction-effects"
        )
        runner = _BlockingRunner()
        runtime = _runtime(tmp_path, sink, runner)
        await runtime.receive(_event("1001", "first"))
        await runtime.receive(_event("1002", "second"))

        processing = asyncio.create_task(runtime.coalescer.flush_all())
        await runner.started.wait()
        assert channel.messages[1001].reactions == ["⏳"]
        assert channel.messages[1002].reactions == ["⏳"]
        runner.release.set()
        await processing

        assert channel.messages[1001].reactions == []
        assert channel.messages[1002].reactions == ["☑️"]
        assert getattr(channel.sent[0]["reference"], "id") == 1002

    asyncio.run(run_case())


def test_abandoned_turn_restart_cleanup_never_adds_completion(tmp_path) -> None:
    async def run_case() -> None:
        channel = _Channel()
        sink = DiscordOutboundSink(
            _Client(channel), reaction_effect_root=tmp_path / "reaction-effects"
        )
        runtime = _runtime(tmp_path, sink, _BlockingRunner())
        store = runtime.store
        conversation = store.upsert_resident_conversation(
            ResidentConversationInput(
                transport="discord", conversation_key="discord:dm:42", dm_user_id="42"
            ),
            idempotency_key="conversation-42",
        )
        message = store.create_message(
            epic_id=None,
            conversation_id=conversation.id,
            direction="inbound",
            content="interrupted",
            discord_message_id="1001",
            idempotency_key="discord:message:1001",
        )
        turn = store.create_turn(
            epic_id=None,
            triggered_by_message_ids=[message.id],
            idempotency_key="turn-abandoned",
        )
        store.update_message(message.id, bot_turn_id=turn.id)
        store.update_turn(turn.id, started_at=datetime.now(UTC) - timedelta(hours=1))
        await sink.mark_processing(
            conversation_key=conversation.conversation_key,
            message_ids=["1001"],
            turn_id=turn.id,
        )
        assert channel.messages[1001].reactions == ["⏳"]

        recovered = await runtime.recover_abandoned_turns()
        assert recovered == 1
        assert channel.messages[1001].reactions == []
        assert "☑️" not in channel.messages[1001].add_calls

    asyncio.run(run_case())


def test_restart_interrupted_side_effectful_turn_is_consumed_without_model_replay(
    tmp_path, monkeypatch
) -> None:
    async def run_case() -> None:
        notification_root = tmp_path / "restart-transactions"
        monkeypatch.setenv(RESET_NOTIFICATION_ENV, str(notification_root))
        channel = _Channel()
        sink = DiscordOutboundSink(
            _Client(channel), reaction_effect_root=tmp_path / "reaction-effects"
        )
        runner = _ImmediateRunner()
        runtime = _runtime(tmp_path, sink, runner)
        store = runtime.store
        conversation = store.upsert_resident_conversation(
            ResidentConversationInput(
                transport="discord",
                conversation_key="discord:dm:42",
                dm_user_id="42",
                metadata={"last_subject_user_id": "42"},
            ),
            idempotency_key="conversation-restart-replay",
        )
        message = store.create_message(
            epic_id=None,
            conversation_id=conversation.id,
            direction="inbound",
            content="finish this after restart",
            discord_message_id="1001",
            discord_reply_provenance={
                "source_author_id": "42",
                "source_message_id": "1001",
                "conversation_key": conversation.conversation_key,
                "ancestors": [],
                "chain_complete": True,
                "termination_reason": "root",
            },
            idempotency_key="discord:message:1001",
        )
        turn = store.create_turn(
            epic_id=None,
            triggered_by_message_ids=[message.id],
            idempotency_key="interrupted-turn",
        )
        store.update_message(message.id, bot_turn_id=turn.id)
        provenance = {
            "schema_version": "arnold-resident-delegation-provenance-v1",
            "applicability": "applicable",
            "transport": "discord",
            "resident_conversation_id": conversation.id,
            "resident_turn_id": turn.id,
            "source_record_id": message.id,
            "conversation_key": conversation.conversation_key,
            "discord_message_id": "1001",
            "reply_to_message_id": "1001",
            "dm_user_id": "42",
            "source_kind": "discord_inbound_message",
        }
        monkeypatch.setenv(DELEGATION_CONTEXT_ENV, json.dumps(provenance))
        reservation = prepare_reset_notification(
            notification_root=notification_root,
            restart_request={
                "backend": "tmux",
                "old_identity": {"backend": "tmux", "pane_pid": 10},
            },
        )
        mark_reset_succeeded(
            reservation,
            restart_evidence={
                "backend": "tmux",
                "health": {"pane_pid": 20, "identity_changed": True},
            },
        )

        first = await runtime.recover_restart_interrupted_turns(
            {"backend": "tmux", "pane_pid": 20}
        )
        second = await runtime.recover_restart_interrupted_turns(
            {"backend": "tmux", "pane_pid": 20}
        )

        assert first == 1
        assert second == 0
        assert runner.calls == 0
        assert channel.sent == []
        old_turn = next(row for row in store.list_recent_turns(n=20) if row.id == turn.id)
        assert old_turn.status == "abandoned"
        assert any(
            "automatic model replay suppressed" in warning
            for warning in old_turn.warnings_issued
        )
        replacement_message = store.load_message(message.id)
        assert replacement_message is not None
        assert replacement_message.bot_turn_id == turn.id

    asyncio.run(run_case())


def test_restart_recovery_reuses_persisted_outbound_without_duplicate_execution(
    tmp_path, monkeypatch
) -> None:
    async def run_case() -> None:
        notification_root = tmp_path / "restart-transactions"
        monkeypatch.setenv(RESET_NOTIFICATION_ENV, str(notification_root))
        channel = _Channel()
        sink = DiscordOutboundSink(
            _Client(channel), reaction_effect_root=tmp_path / "reaction-effects"
        )
        runner = _ImmediateRunner()
        runtime = _runtime(tmp_path, sink, runner)
        store = runtime.store
        conversation = store.upsert_resident_conversation(
            ResidentConversationInput(
                transport="discord",
                conversation_key="discord:dm:42",
                dm_user_id="42",
                metadata={"last_subject_user_id": "42"},
            ),
            idempotency_key="conversation-existing-outbound",
        )
        message = store.create_message(
            epic_id=None,
            conversation_id=conversation.id,
            direction="inbound",
            content="do not execute twice",
            discord_message_id="1002",
            discord_reply_provenance={"source_author_id": "42"},
            idempotency_key="discord:message:1002",
        )
        turn = store.create_turn(
            epic_id=None,
            triggered_by_message_ids=[message.id],
            idempotency_key="turn-existing-outbound",
        )
        store.update_message(message.id, bot_turn_id=turn.id)
        outbound = store.create_message(
            epic_id=None,
            conversation_id=conversation.id,
            direction="outbound",
            content="already computed response",
            bot_turn_id=turn.id,
            idempotency_key="resident-outbound:stable-existing",
        )
        monkeypatch.setenv(
            DELEGATION_CONTEXT_ENV,
            json.dumps(
                {
                    "schema_version": "arnold-resident-delegation-provenance-v1",
                    "applicability": "applicable",
                    "transport": "discord",
                    "resident_conversation_id": conversation.id,
                    "resident_turn_id": turn.id,
                    "source_record_id": message.id,
                    "conversation_key": conversation.conversation_key,
                    "discord_message_id": "1002",
                    "reply_to_message_id": "1002",
                    "dm_user_id": "42",
                    "source_kind": "discord_inbound_message",
                }
            ),
        )
        reservation = prepare_reset_notification(
            notification_root=notification_root,
            restart_request={
                "backend": "tmux",
                "old_identity": {"backend": "tmux", "pane_pid": 10},
            },
        )
        mark_reset_succeeded(
            reservation,
            restart_evidence={"backend": "tmux", "health": {"pane_pid": 20}},
        )

        first = await runtime.recover_restart_interrupted_turns(
            {"backend": "tmux", "pane_pid": 20}
        )
        second = await runtime.recover_restart_interrupted_turns(
            {"backend": "tmux", "pane_pid": 20}
        )

        assert first == 1
        assert second == 0
        assert runner.calls == 0
        assert [item["content"] for item in channel.sent] == [outbound.content]
        assert getattr(channel.sent[0]["reference"], "id") == 1002
        assert channel.sent[0]["nonce"]
        completed = next(row for row in store.list_recent_turns(n=20) if row.id == turn.id)
        assert completed.status == "completed"
        assert completed.final_output_message_id == outbound.id

    asyncio.run(run_case())


def test_detached_acknowledgement_keeps_working_until_managed_terminal_reply(tmp_path) -> None:
    async def run_case() -> None:
        channel = _Channel()
        sink = DiscordOutboundSink(
            _Client(channel), reaction_effect_root=tmp_path / "reaction-effects"
        )
        await sink.mark_processing(
            conversation_key="discord:dm:42", message_ids=["1001"], turn_id="turn-1"
        )
        await sink.send(
            OutboundMessage(
                conversation_key="discord:dm:42",
                content="Started it.",
                metadata={
                    "discord_reply_to_message_id": "1001",
                    "discord_processing_message_ids": ["1001"],
                    "discord_processing_turn_id": "turn-1",
                    "discord_processing_continues": True,
                },
            )
        )
        assert channel.messages[1001].reactions == ["⏳"]

        await sink.send(
            OutboundMessage(
                conversation_key="discord:dm:42",
                content="Terminal verified result.",
                metadata={
                    "managed_agent_run_id": "run-1",
                    "discord_reply_to_message_id": "1001",
                    "discord_processing_message_ids": ["1001"],
                    "discord_processing_turn_id": "turn-1",
                },
            )
        )
        assert channel.messages[1001].reactions == ["☑️"]
        assert len(channel.sent) == 2

    asyncio.run(run_case())


def test_non_discord_outbound_has_no_reaction_lifecycle_calls(tmp_path) -> None:
    class Sink:
        def __init__(self) -> None:
            self.lifecycle_calls: list[str] = []
            self.sent: list[OutboundMessage] = []

        async def mark_processing(self, **_kwargs) -> None:
            self.lifecycle_calls.append("working")

        async def mark_processing_interrupted(self, **_kwargs) -> None:
            self.lifecycle_calls.append("interrupted")

        async def send(self, message: OutboundMessage) -> None:
            self.sent.append(message)

    async def run_case() -> None:
        sink = Sink()
        runner = _BlockingRunner()
        runtime = _runtime(tmp_path, sink, runner)
        event = InboundEvent(
            idempotency_key="internal:event:1",
            conversation_key="internal:conversation:1",
            subject=AuthorizationSubject(user_id="42", guild_id=None, channel_id=None),
            content="scheduled work",
            raw={},
        )
        await runtime.receive(event)
        processing = asyncio.create_task(runtime.coalescer.flush_all())
        await runner.started.wait()
        runner.release.set()
        await processing
        assert sink.lifecycle_calls == []
        assert len(sink.sent) == 1
        assert sink.sent[0].metadata["discord_reply_to_message_id"] is None

    asyncio.run(run_case())
