from __future__ import annotations

import asyncio
from datetime import UTC, datetime
import json
from types import SimpleNamespace

import pytest

from arnold_pipelines.megaplan.resident.agent_loop import AgentResponse
from arnold_pipelines.megaplan.resident.auth import AuthorizationSubject, ResidentAuthorizer
from arnold_pipelines.megaplan.resident.config import ResidentConfig
from arnold_pipelines.megaplan.resident.discord import (
    DiscordDeliveryTarget,
    DiscordInboundMessage,
    ResidentDiscordService,
)
from arnold_pipelines.megaplan.resident.profile import MegaplanResidentProfile
from arnold_pipelines.megaplan.resident.runtime import InboundEvent, OutboundMessage, ResidentRuntime
from arnold_pipelines.megaplan.resident.timezone import (
    InvalidWallTime,
    TimezoneService,
    add_localized_timestamp_fields,
    format_timestamp,
    localize_wall_time,
)
from arnold_pipelines.megaplan.store import FileStore, ResidentConversationInput
from tests.resident.test_subagent_terminal_delivery_contract import (
    _AcceptedOutbound,
    _write_terminal_manifest,
)
from arnold_pipelines.megaplan.resident.subagent import sweep_managed_agent_deliveries


def test_user_preference_persists_across_store_restart(tmp_path) -> None:
    root = tmp_path / "store"
    service = TimezoneService(FileStore(root), ResidentConfig())
    service.set_user_timezone("user-1", "America/New_York")

    restarted = TimezoneService(FileStore(root), ResidentConfig())
    preference = restarted.get_user_preference("user-1")

    assert preference is not None
    assert preference.timezone_name == "America/New_York"
    assert restarted.resolve(user_id="user-1").name == "America/New_York"

    restarted.set_user_timezone("user-1", "America/Los_Angeles")
    assert TimezoneService(FileStore(root), ResidentConfig()).resolve(
        user_id="user-1"
    ).name == "America/Los_Angeles"


def test_timezone_defaults_load_from_environment() -> None:
    config = ResidentConfig.from_env(
        {
            "MEGAPLAN_RESIDENT_DEFAULT_TIMEZONE": "Europe/Paris",
            "MEGAPLAN_RESIDENT_GUILD_TIMEZONES": '{"guild-1":"Asia/Tokyo"}',
        }
    )

    assert config.default_timezone == "Europe/Paris"
    assert config.guild_timezone_defaults == {"guild-1": "Asia/Tokyo"}


def test_resolution_precedence_is_user_conversation_guild_system_utc(tmp_path) -> None:
    store = FileStore(tmp_path / "store")
    config = ResidentConfig(
        default_timezone="Europe/London",
        guild_timezone_defaults={"guild-1": "America/Chicago"},
    )
    service = TimezoneService(store, config)
    conversation = store.upsert_resident_conversation(
        ResidentConversationInput(
            conversation_key="discord:guild:guild-1:channel:channel-1",
            guild_id="guild-1",
            channel_id="channel-1",
            metadata={"timezone_name": "Asia/Tokyo", "last_subject_user_id": "user-1"},
        )
    )

    assert service.resolve(user_id=None, conversation=conversation).source == "conversation"
    assert service.resolve(user_id=None, conversation=conversation).name == "Asia/Tokyo"

    store.upsert_resident_user_preference(
        transport="discord", user_id="legacy-bad", timezone_name="bad/zone"
    )
    invalid = service.resolve(user_id="legacy-bad", conversation=conversation)
    assert (invalid.name, invalid.source) == ("UTC", "utc_fallback")

    service.set_user_timezone("user-1", "America/New_York")
    resolved = service.resolve(user_id="user-1", conversation=conversation)
    assert (resolved.name, resolved.source) == ("America/New_York", "user")

    no_conversation_override = conversation.model_copy(update={"metadata": {}})
    assert service.resolve(user_id=None, conversation=no_conversation_override).name == "America/Chicago"
    assert service.resolve(user_id=None).name == "Europe/London"
    assert TimezoneService(store, ResidentConfig(default_timezone="bad/zone")).resolve(
        user_id=None
    ).name == "UTC"


def test_dm_and_guild_resolve_same_canonical_user_preference(tmp_path) -> None:
    store = FileStore(tmp_path / "store")
    service = TimezoneService(store, ResidentConfig())
    service.set_user_timezone("user-1", "Australia/Sydney")
    dm = store.upsert_resident_conversation(
        ResidentConversationInput(
            conversation_key="discord:dm:user-1", dm_user_id="user-1"
        )
    )
    guild = store.upsert_resident_conversation(
        ResidentConversationInput(
            conversation_key="discord:guild:g1:channel:c1",
            guild_id="g1",
            channel_id="c1",
            metadata={"last_subject_user_id": "user-1"},
        )
    )

    assert service.resolve(user_id="user-1", conversation=dm).name == "Australia/Sydney"
    assert service.resolve(user_id="user-1", conversation=guild).name == "Australia/Sydney"


def test_dst_rendering_and_wall_time_gap_fold_rules() -> None:
    assert format_timestamp("2026-03-08T06:59:00Z", "America/New_York").endswith(
        "EST (UTC-05:00)"
    )
    assert format_timestamp("2026-03-08T07:01:00Z", "America/New_York").endswith(
        "EDT (UTC-04:00)"
    )

    with pytest.raises(InvalidWallTime, match="does not exist"):
        localize_wall_time(datetime(2026, 3, 8, 2, 30), "America/New_York")
    with pytest.raises(InvalidWallTime, match="ambiguous"):
        localize_wall_time(datetime(2026, 11, 1, 1, 30), "America/New_York")

    first = localize_wall_time(
        datetime(2026, 11, 1, 1, 30), "America/New_York", fold=0
    )
    second = localize_wall_time(
        datetime(2026, 11, 1, 1, 30), "America/New_York", fold=1
    )
    assert first.astimezone(UTC) != second.astimezone(UTC)


def test_structured_projection_preserves_utc_and_adds_local_display() -> None:
    source = {
        "generated_at": "2026-07-13T12:00:00Z",
        "elapsed_seconds": 90,
    }
    rendered = add_localized_timestamp_fields(source, "America/New_York")

    assert source == {"generated_at": "2026-07-13T12:00:00Z", "elapsed_seconds": 90}
    assert rendered["generated_at"] == source["generated_at"]
    assert rendered["generated_at_local"] == "2026-07-13 08:00:00 EDT (UTC-04:00)"
    assert "elapsed_seconds_local" not in rendered


def test_hot_context_prompt_output_and_delegation_share_resolved_timezone(tmp_path) -> None:
    async def run_case() -> None:
        store = FileStore(tmp_path / "store")
        config = ResidentConfig(
            allowed_user_ids=("1001",),
            burst_idle_delay_s=0,
            burst_max_delay_s=1,
            status_snapshot_path=tmp_path / "missing-status.json",
        )
        TimezoneService(store, config).set_user_timezone("1001", "America/New_York")
        authorizer = ResidentAuthorizer(config)
        runner = CapturingRunner()
        outbound = CapturingOutbound()
        runtime = ResidentRuntime(
            config=config,
            authorizer=authorizer,
            store=store,
            profile=MegaplanResidentProfile(store=store, authorizer=authorizer, config=config),
            runner=runner,
            outbound=outbound,
        )

        await runtime.receive(
            InboundEvent(
                idempotency_key="discord:message:9001",
                conversation_key="discord:dm:1001",
                subject=AuthorizationSubject(user_id="1001", channel_id="1001"),
                content="status?",
                raw={"discord_message_id": "9001", "dm_user_id": "1001"},
            )
        )
        await runtime.coalescer.flush_all()

        assert runner.request.hot_context["user_timezone"]["timezone_name"] == "America/New_York"
        assert "render every absolute user-visible time in America/New_York" in runner.request.system_prompt
        assert runner.request.launch_origin["timezone_name"] == "America/New_York"
        assert outbound.sent[-1].content == "Snapshot: 2026-07-13 08:00:00 EDT (UTC-04:00)"

        conversation = store.get_resident_conversation_by_key(
            transport="discord", conversation_key="discord:dm:1001"
        )
        assert conversation is not None
        stored = store.list_conversation_messages(conversation.id, limit=10)
        assert stored[-1].sent_at.tzinfo is not None

    class CapturingRunner:
        request = None

        async def run(self, request, tools):
            self.request = request
            return AgentResponse(final_text="Snapshot: 2026-07-13T12:00:00Z")

    class CapturingOutbound:
        def __init__(self) -> None:
            self.sent: list[OutboundMessage] = []

        async def send(self, message: OutboundMessage) -> None:
            self.sent.append(message)

    asyncio.run(run_case())


def test_authorized_discord_timezone_command_is_durable(tmp_path) -> None:
    async def run_case() -> None:
        store = FileStore(tmp_path / "store")
        config = ResidentConfig(allowed_user_ids=("1001",))
        runtime = SimpleNamespace(
            store=store,
            config=config,
            authorizer=ResidentAuthorizer(config),
        )
        service = ResidentDiscordService(runtime=runtime, token="test-token")
        channel = FakeChannel()
        message = SimpleNamespace(id=9002, channel=channel)
        inbound = DiscordInboundMessage(
            message_id="9002",
            author_id="1001",
            target=DiscordDeliveryTarget(
                guild_id=None, channel_id="1001", dm_user_id="1001"
            ),
            content="/timezone America/Los_Angeles",
        )

        assert await service._handle_timezone_command(message, inbound) is True
        assert "Timezone set to `America/Los_Angeles`" in channel.sent[0]
        assert TimezoneService(FileStore(tmp_path / "store"), config).resolve(
            user_id="1001"
        ).name == "America/Los_Angeles"

    class FakeChannel:
        def __init__(self) -> None:
            self.sent: list[str] = []

        async def send(self, content: str, **kwargs) -> None:
            self.sent.append(content)

    asyncio.run(run_case())


def test_terminal_discord_delivery_localizes_with_manifest_timezone(tmp_path) -> None:
    manifest_path = _write_terminal_manifest(
        tmp_path, status="completed", with_verified_payload=False
    )
    manifest = json.loads(manifest_path.read_text())
    manifest["launch_provenance"]["timezone_name"] = "America/New_York"
    manifest["discord_origin"]["timezone_name"] = "America/New_York"
    result_path = manifest_path.parent / "result.md"
    result_path.write_text("Finished at 2026-07-13T12:00:00Z")
    manifest_path.write_text(json.dumps(manifest))
    outbound = _AcceptedOutbound()

    result = asyncio.run(
        sweep_managed_agent_deliveries(
            outbound=outbound,
            project_root=tmp_path,
            workspace_root=None,
            now=datetime(2026, 7, 13, 13, 0, tzinfo=UTC),
        )
    )

    assert result.delivered == 1
    assert outbound.sent[0].content == "Finished at 2026-07-13 08:00:00 EDT (UTC-04:00)"
    persisted = json.loads(manifest_path.read_text())
    assert persisted["created_at"] == "2026-07-13T14:50:32+00:00"
