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
    DROPPED_THREAD_CLASSIFICATIONS,
    DROPPED_THREADS_OUTPUT_FIELDS,
    InvalidLookback,
    STRATEGIC_ACTION_GAP_CATEGORIES,
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
    assert "strategic action gaps" in command.description
    assert len(command.description) <= 100

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
    assert "search_messages" in prompt
    assert "pending or conditional" in prompt
    assert "timezone abbreviation, and numeric UTC offset" in prompt


def test_taxonomy_and_output_contract_are_bounded_and_classified() -> None:
    assert DROPPED_THREAD_CLASSIFICATIONS == (
        "explicit_dropped_thread",
        "strategic_action_gap",
    )
    assert STRATEGIC_ACTION_GAP_CATEGORIES == (
        "identified_defect_or_risk",
        "necessary_follow_up",
        "actionable_evidence_or_recommendation",
        "partial_fix_residual_risk",
    )
    assert DROPPED_THREADS_OUTPUT_FIELDS == (
        "classification",
        "category",
        "thread",
        "evidence",
        "why_action_was_expected",
        "missing_disposition_evidence",
        "confidence",
        "recommended_next_action",
    )

    prompt = dropped_threads_prompt(DEFAULT_DROPPED_THREADS_LOOKBACK)
    for classification in DROPPED_THREAD_CLASSIFICATIONS:
        assert classification in prompt
    for category in STRATEGIC_ACTION_GAP_CATEGORIES:
        assert category in prompt
    for field in DROPPED_THREADS_OUTPUT_FIELDS:
        assert field in prompt


def test_prompt_covers_user_bug_and_necessary_follow_up_examples() -> None:
    prompt = dropped_threads_prompt(DEFAULT_DROPPED_THREADS_LOOKBACK)

    # User example 1: spotting a concrete bug does not count as closure when no
    # investigation, fix, or explicit disposition follows.
    assert "concrete bug, defect, failure, or material risk was identified" in prompt
    assert "no investigation, fix, or explicit disposition followed" in prompt

    # User example 2: completed work can make a follow-up necessary even when
    # nobody made a separate explicit promise to do it.
    assert "completed work created an obvious necessary follow-up" in prompt
    assert "no action, owner, durable todo/ticket/plan" in prompt
    assert "no explicit promise is required" in prompt


def test_prompt_covers_action_only_reporting_and_partial_fix_residuals() -> None:
    prompt = dropped_threads_prompt(DEFAULT_DROPPED_THREADS_LOOKBACK)

    assert "evidence or a recommendation called for action" in prompt
    assert "acknowledgement or reporting only" in prompt
    assert "partial fix or workaround left a stated root cause or residual risk untreated" in prompt


def test_prompt_requires_actionability_and_missing_disposition_evidence() -> None:
    prompt = dropped_threads_prompt(DEFAULT_DROPPED_THREADS_LOOKBACK)

    assert "evidence supports both" in prompt
    assert "materially actionable implication" in prompt
    assert "absence of a satisfactory disposition" in prompt
    assert "what later scope was checked and any uncertainty" in prompt
    assert "never turn uncertainty into an assertion" in prompt


def test_prompt_rejects_speculation_optional_ideas_and_explicit_deferrals() -> None:
    prompt = dropped_threads_prompt(DEFAULT_DROPPED_THREADS_LOOKBACK)

    assert "do not flag a suggestion, hypothetical, optional enhancement, observation" in prompt
    assert "pending or conditional work that is not due" in prompt
    assert "reasoned deferral" in prompt
    assert "explicit rejection" in prompt
    assert "delegation to a durable owner" in prompt
    assert "durable ticket/todo/initiative/plan" in prompt
    assert "supersession is a disposition" in prompt
    assert "Prefer omitting low-confidence candidates" in prompt


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
