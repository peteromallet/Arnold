from __future__ import annotations

import asyncio
from types import SimpleNamespace

import discord
import pytest

from arnold_pipelines.megaplan.resident.auth import AuthorizationDecision
from arnold_pipelines.megaplan.resident.discord import (
    DISCORD_APPLICATION_COMMANDS,
    ResidentDiscordService,
    register_discord_application_commands,
)
from arnold_pipelines.megaplan.resident.dropped_threads import (
    DEFAULT_DROPPED_THREADS_LOOKBACK,
    InvalidLookback,
    dropped_threads_prompt,
    parse_dropped_threads_lookback,
)


class _Response:
    def __init__(self) -> None:
        self.events: list[tuple[str, object]] = []

    async def send_message(self, content: str, **kwargs: object) -> None:
        self.events.append(("send", (content, kwargs)))

    async def defer(self, **kwargs: object) -> None:
        self.events.append(("defer", kwargs))


def _interaction(response: _Response, *, interaction_id: int = 123) -> SimpleNamespace:
    return SimpleNamespace(
        id=interaction_id,
        user=SimpleNamespace(id=42),
        guild_id=7,
        channel=None,
        channel_id=9,
        response=response,
    )


def _command(service: ResidentDiscordService):
    client = discord.Client(intents=discord.Intents.none())
    tree = discord.app_commands.CommandTree(client)
    register_discord_application_commands(tree, service)
    return tree.get_command("dropped-threads")


def test_dropped_threads_registers_a_single_optional_lookback_command() -> None:
    command = next(item for item in DISCORD_APPLICATION_COMMANDS if item.name == "dropped-threads")

    assert command.handler_name == "handle_dropped_threads_interaction"
    assert command.has_lookback_option is True
    assert "dropped" in command.description

    class Service:
        async def handle_currently_running_interaction(self, _interaction):
            pass

        async def handle_restart_resident_interaction(self, _interaction):
            pass

        async def handle_dropped_threads_interaction(self, _interaction, *, lookback=None):
            pass

    client = discord.Client(intents=discord.Intents.none())
    tree = discord.app_commands.CommandTree(client)
    registered = register_discord_application_commands(tree, Service())
    command = tree.get_command("dropped-threads")

    assert registered.count("dropped-threads") == 1
    assert [(option.name, option.required) for option in command.parameters] == [
        ("lookback", False)
    ]


def test_default_lookback_is_six_hours_and_is_in_the_resident_prompt() -> None:
    assert parse_dropped_threads_lookback(None) == DEFAULT_DROPPED_THREADS_LOOKBACK
    prompt = dropped_threads_prompt(DEFAULT_DROPPED_THREADS_LOOKBACK)

    assert "last 6h" in prompt
    assert "authoritative persisted conversation" in prompt
    assert "Do not rely only on hot-context excerpts" in prompt
    assert "pending or conditional" in prompt
    assert "timezone abbreviation, and UTC offset" in prompt


def test_duration_parser_accepts_minutes_hours_days_and_caps_at_seven_days() -> None:
    assert str(parse_dropped_threads_lookback("30m")) == "0:30:00"
    assert str(parse_dropped_threads_lookback("6h")) == "6:00:00"
    assert str(parse_dropped_threads_lookback("1d")) == "1 day, 0:00:00"
    with pytest.raises(InvalidLookback, match="7d"):
        parse_dropped_threads_lookback("8d")


def test_custom_valid_duration_is_parsed_and_dispatched_through_runtime_receive() -> None:
    response = _Response()
    received = []

    class Authorizer:
        def authorize_inbound(self, subject):
            assert subject.user_id == "42"
            return AuthorizationDecision(True)

    class Runtime:
        authorizer = Authorizer()

        async def receive(self, event, *, authorization_decision):
            received.append((event, authorization_decision))

    service = object.__new__(ResidentDiscordService)
    service.runtime = Runtime()

    asyncio.run(_command(service).callback(_interaction(response), "30m"))

    assert response.events == [("defer", {"thinking": True})]
    assert len(received) == 1
    event, decision = received[0]
    assert decision.allowed is True
    assert event.idempotency_key == "discord:interaction:123"
    assert event.raw["source_kind"] == "discord_application_command"
    assert event.raw["discord_interaction_id"] == "123"
    assert "discord_message_id" not in event.raw
    assert "last 30m" in event.content


def test_invalid_duration_returns_one_clear_ephemeral_response_without_dispatch() -> None:
    response = _Response()

    class Runtime:
        authorizer = SimpleNamespace(authorize_inbound=lambda _subject: AuthorizationDecision(True))

        async def receive(self, *_args, **_kwargs):
            raise AssertionError("invalid lookback must not reach the resident")

    service = object.__new__(ResidentDiscordService)
    service.runtime = Runtime()

    asyncio.run(_command(service).callback(_interaction(response), "0h"))

    assert response.events == [
        ("send", ("Invalid lookback: use a positive duration such as `30m`, `6h`, or `1d`. Maximum is `7d`.", {"ephemeral": True}))
    ]
