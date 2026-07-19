from __future__ import annotations

import asyncio
import inspect
from types import SimpleNamespace

import discord

from agentbox.reset_notifications import RESET_DELIVERY_EPHEMERAL_INTERACTION
from agentbox.services import DISCORD_RESIDENT_SERVICE
from arnold_pipelines.megaplan.resident import discord as discord_module
from arnold_pipelines.megaplan.resident import restart_resident as restart_module
from arnold_pipelines.megaplan.resident.auth import AuthorizationDecision
from arnold_pipelines.megaplan.resident.discord import (
    DISCORD_APPLICATION_COMMANDS,
    ResidentDiscordService,
    register_discord_application_commands,
)
from arnold_pipelines.megaplan.resident.restart_resident import (
    RESTART_RESIDENT_ACKNOWLEDGEMENT,
    restart_discord_resident,
)


class _Response:
    def __init__(self, events: list[tuple[str, str]]) -> None:
        self.events = events

    async def send_message(self, content: str, **kwargs) -> None:
        assert kwargs == {"ephemeral": True}
        self.events.append(("response", content))


def _interaction(events: list[tuple[str, str]]) -> SimpleNamespace:
    async def edit_original_response(*, content: str) -> None:
        events.append(("edit_original", content))

    return SimpleNamespace(
        user=SimpleNamespace(id=42),
        guild_id=7,
        channel=None,
        channel_id=9,
        response=_Response(events),
        edit_original_response=edit_original_response,
    )


def _command(service: ResidentDiscordService):
    client = discord.Client(intents=discord.Intents.none())
    tree = discord.app_commands.CommandTree(client)
    register_discord_application_commands(tree, service)
    return tree.get_command("restart-resident")


def test_restart_resident_command_is_registered_once_as_privileged_control() -> None:
    names = [command.name for command in DISCORD_APPLICATION_COMMANDS]

    assert names.count("restart-resident") == 1
    command = next(
        command for command in DISCORD_APPLICATION_COMMANDS
        if command.name == "restart-resident"
    )
    assert command.handler_name == "handle_restart_resident_interaction"
    assert "restart only the Discord resident" in command.description


def test_restart_resident_requires_admin_authorization_before_ack_or_invocation() -> None:
    events: list[tuple[str, str]] = []
    calls = []

    class Authorizer:
        def authorize_action(self, subject, action):
            calls.append((subject, action))
            return AuthorizationDecision(False, "admin_required")

    service = object.__new__(ResidentDiscordService)
    service.runtime = SimpleNamespace(authorizer=Authorizer())
    service.restart_operation = lambda: events.append(("operation", "called"))

    asyncio.run(_command(service).callback(_interaction(events)))

    assert calls[0][1] == "admin"
    assert calls[0][0].user_id == "42"
    assert calls[0][0].guild_id == "7"
    assert calls[0][0].channel_id == "9"
    assert events == [
        ("response", "This command requires resident administrator authorization.")
    ]


def test_acknowledgement_is_confirmed_before_canonical_restart_invocation() -> None:
    events: list[tuple[str, str]] = []

    class Authorizer:
        def authorize_action(self, _subject, action):
            assert action == "admin"
            return AuthorizationDecision(True)

    def restart_operation():
        events.append(("operation", DISCORD_RESIDENT_SERVICE))
        return {"ok": True, "accepted": True}

    service = object.__new__(ResidentDiscordService)
    service.runtime = SimpleNamespace(authorizer=Authorizer())
    service.restart_operation = restart_operation

    asyncio.run(_command(service).callback(_interaction(events)))

    assert events[0] == ("response", RESTART_RESIDENT_ACKNOWLEDGEMENT)
    assert "current resident turn can be interrupted" in events[0][1]
    assert "detached agents" in events[0][1]
    assert "tmux-backed Megaplan/cloud chains are preserved" in events[0][1]
    assert events[1] == ("operation", "agentbox-discord-resident")
    assert events[2][0] == "edit_original"
    assert "guarded resident restart was accepted" in events[2][1]
    assert "replacement health is verified" in events[2][1]


def test_application_command_uses_ephemeral_interaction_as_delivery_owner(
    monkeypatch,
) -> None:
    events: list[tuple[str, str]] = []
    calls: list[str | None] = []

    class Authorizer:
        def authorize_action(self, _subject, action):
            assert action == "admin"
            return AuthorizationDecision(True)

    def restart_operation(*, delivery_ownership=None):
        calls.append(delivery_ownership)
        return {"ok": True, "accepted": True}

    monkeypatch.setattr(
        discord_module,
        "restart_discord_resident",
        restart_operation,
    )
    service = object.__new__(ResidentDiscordService)
    service.runtime = SimpleNamespace(authorizer=Authorizer())

    asyncio.run(_command(service).callback(_interaction(events)))

    assert calls == [RESET_DELIVERY_EPHEMERAL_INTERACTION]
    assert events[0] == ("response", RESTART_RESIDENT_ACKNOWLEDGEMENT)
    assert events[1][0] == "edit_original"


def test_fail_closed_result_is_reported_without_claiming_restart() -> None:
    events: list[tuple[str, str]] = []
    service = object.__new__(ResidentDiscordService)
    service.runtime = SimpleNamespace(
        authorizer=SimpleNamespace(
            authorize_action=lambda _subject, _action: AuthorizationDecision(True)
        )
    )
    service.restart_operation = lambda: {
        "ok": False,
        "error": "installed service state is stale",
    }

    asyncio.run(_command(service).callback(_interaction(events)))

    assert events[0] == ("response", RESTART_RESIDENT_ACKNOWLEDGEMENT)
    assert events[1] == (
        "edit_original",
        "The resident restart was refused safely: installed service state is stale. "
        "No restart was performed.",
    )


def test_restart_exception_fails_closed_after_acknowledgement() -> None:
    events: list[tuple[str, str]] = []
    service = object.__new__(ResidentDiscordService)
    service.runtime = SimpleNamespace(
        authorizer=SimpleNamespace(
            authorize_action=lambda _subject, _action: AuthorizationDecision(True)
        )
    )

    def fail():
        raise RuntimeError("boom")

    service.restart_operation = fail

    asyncio.run(_command(service).callback(_interaction(events)))

    assert events[0] == ("response", RESTART_RESIDENT_ACKNOWLEDGEMENT)
    assert events[1] == (
        "edit_original",
        "The resident restart did not return a confirmed acceptance. "
        "No restart outcome is being claimed; check the durable lifecycle status.",
    )


def test_invalid_restart_result_makes_no_outcome_claim() -> None:
    events: list[tuple[str, str]] = []
    service = object.__new__(ResidentDiscordService)
    service.runtime = SimpleNamespace(
        authorizer=SimpleNamespace(
            authorize_action=lambda _subject, _action: AuthorizationDecision(True)
        )
    )
    service.restart_operation = lambda: None

    asyncio.run(_command(service).callback(_interaction(events)))

    assert events[0] == ("response", RESTART_RESIDENT_ACKNOWLEDGEMENT)
    assert events[1] == (
        "edit_original",
        "The resident restart returned no valid lifecycle result. "
        "No restart outcome is being claimed; check the durable lifecycle status.",
    )


def test_canonical_restart_wrapper_targets_only_the_named_resident(monkeypatch) -> None:
    calls: list[tuple[str, dict[str, object]]] = []
    expected = {"ok": True, "accepted": True}
    monkeypatch.setattr(
        restart_module,
        "restart_service",
        lambda service_name, **kwargs: calls.append((service_name, kwargs)) or expected,
    )

    assert restart_discord_resident() is expected
    assert calls == [
        ("agentbox-discord-resident", {"notification_delivery_ownership": None})
    ]


def test_canonical_restart_wrapper_forwards_ephemeral_delivery_ownership(
    monkeypatch,
) -> None:
    calls = []
    monkeypatch.setattr(
        restart_module,
        "restart_service",
        lambda service_name, **kwargs: calls.append((service_name, kwargs))
        or {"ok": True},
    )

    restart_discord_resident(
        delivery_ownership=RESET_DELIVERY_EPHEMERAL_INTERACTION
    )

    assert calls == [
        (
            "agentbox-discord-resident",
            {
                "notification_delivery_ownership": RESET_DELIVERY_EPHEMERAL_INTERACTION
            },
        )
    ]


def test_discord_restart_layer_contains_no_process_control_shortcuts() -> None:
    sources = "\n".join(
        (
            inspect.getsource(restart_module),
            inspect.getsource(ResidentDiscordService.handle_restart_resident_interaction),
        )
    ).casefold()
    forbidden = (
        "pkill",
        "killall",
        "systemctl",
        "kill-session",
        "kill-server",
        "respawn-pane",
        "cgroup",
    )

    assert not any(token in sources for token in forbidden)
    assert "restart_service(" in sources
    assert "discord_resident_service" in sources
