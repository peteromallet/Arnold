from __future__ import annotations

import asyncio
import inspect
from pathlib import Path
from types import SimpleNamespace

import discord
import pytest

from arnold_pipelines.megaplan.resident import discord as discord_module
from arnold_pipelines.megaplan.resident import discord_follow_up as module
from arnold_pipelines.megaplan.resident.auth import AuthorizationDecision
from arnold_pipelines.megaplan.resident.discord import (
    ResidentDiscordService,
    register_discord_application_commands,
)
from arnold_pipelines.megaplan.resident.subagent import SubagentFollowupResult


RUN_ID = "subagent-20260722-191551-60596066"
SUFFIX = "191551-60596066"


def _provenance() -> dict:
    return {
        "schema_version": "arnold-resident-delegation-provenance-v1",
        "applicability": "applicable",
        "transport": "discord",
        "resident_conversation_id": "rconv_followupcommand",
        "source_record_id": "msg_originalrequest",
        "conversation_key": "discord:dm:42",
        "discord_message_id": "1001",
        "reply_to_message_id": "1001",
        "dm_user_id": "42",
        "source_kind": "discord_inbound_message",
    }


def _row(
    run_id: str = RUN_ID,
    *,
    live: bool = True,
    status: str = "running",
    manifest_path: str | None = None,
) -> dict:
    return {
        "run_id": run_id,
        "live": live,
        "status": status,
        "manifest_path": manifest_path or f"/workspace/project/{run_id}/manifest.json",
        "launch_provenance": _provenance(),
    }


def _inventory(*rows: dict) -> dict:
    return {
        "running": [row for row in rows if row["live"]],
        "queued": [],
        "recent": [row for row in rows if not row["live"]],
    }


def test_command_registration_has_exactly_two_required_string_inputs() -> None:
    service = object.__new__(ResidentDiscordService)
    tree = discord.app_commands.CommandTree(
        discord.Client(intents=discord.Intents.none())
    )

    registered = register_discord_application_commands(tree, service)
    command = tree.get_command("follow-up")

    assert registered.count("follow-up") == 1
    assert command is not None
    assert list(inspect.signature(command.callback).parameters) == [
        "interaction",
        "agent",
        "message",
    ]
    assert [(parameter.name, parameter.required) for parameter in command.parameters] == [
        ("agent", True),
        ("message", True),
    ]


@pytest.mark.parametrize("selector", [RUN_ID, SUFFIX])
def test_full_and_displayed_suffix_resolve_to_the_one_live_run(
    tmp_path: Path, monkeypatch, selector: str
) -> None:
    monkeypatch.setattr(
        module,
        "list_managed_resident_agents",
        lambda **_kwargs: _inventory(_row()),
    )

    target = module.resolve_live_managed_agent(
        selector, project_root=tmp_path, workspace_root=None
    )

    assert target.run_id == RUN_ID
    assert target.status == "running"


def test_missing_terminal_and_ambiguous_selectors_are_rejected_truthfully(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(
        module,
        "list_managed_resident_agents",
        lambda **_kwargs: _inventory(),
    )
    with pytest.raises(module.DiscordFollowUpError, match="no resident-managed run"):
        module.resolve_live_managed_agent(
            SUFFIX, project_root=tmp_path, workspace_root=None
        )

    monkeypatch.setattr(
        module,
        "list_managed_resident_agents",
        lambda **_kwargs: _inventory(_row(live=False, status="completed")),
    )
    with pytest.raises(module.DiscordFollowUpError, match="not live.*completed"):
        module.resolve_live_managed_agent(
            RUN_ID, project_root=tmp_path, workspace_root=None
        )

    other = "subagent-20260723-191551-60596066"
    monkeypatch.setattr(
        module,
        "list_managed_resident_agents",
        lambda **_kwargs: _inventory(_row(), _row(other)),
    )
    with pytest.raises(module.DiscordFollowUpError, match="ambiguous"):
        module.resolve_live_managed_agent(
            SUFFIX, project_root=tmp_path, workspace_root=None
        )


class _Response:
    def __init__(self) -> None:
        self.deferred: list[dict] = []
        self.sent: list[tuple[str, dict]] = []

    async def defer(self, **kwargs) -> None:
        self.deferred.append(kwargs)

    async def send_message(self, content: str, **kwargs) -> None:
        self.sent.append((content, kwargs))


class _Followup:
    def __init__(self) -> None:
        self.sent: list[tuple[str, dict]] = []

    async def send(self, content: str, **kwargs) -> None:
        self.sent.append((content, kwargs))


def _interaction() -> SimpleNamespace:
    return SimpleNamespace(
        id=9001,
        user=SimpleNamespace(id=42),
        guild_id=None,
        channel=None,
        channel_id=42,
        response=_Response(),
        followup=_Followup(),
    )


def test_invocation_forwards_exact_message_provenance_and_renders_interrupt_receipt(
    tmp_path: Path, monkeypatch
) -> None:
    target = module.LiveManagedAgentTarget(
        run_id=RUN_ID,
        manifest_path=str(tmp_path / "manifest.json"),
        launch_provenance=_provenance(),
        status="running",
    )
    monkeypatch.setattr(
        discord_module, "resolve_live_managed_agent", lambda *args, **kwargs: target
    )
    captured: dict = {}

    def fake_follow_up(**kwargs):
        captured.update(kwargs)
        return SubagentFollowupResult(
            ok=True,
            followup_id="followup-durable-receipt",
            target_run_id=RUN_ID,
            parent_run_id=RUN_ID,
            lineage_root_run_id=RUN_ID,
            continuation_run_id="subagent-20260722-192000-aaaaaaaa",
            status="continuation_started",
            evidence_path="/durable/followup.json",
            message_path="/durable/followup.md",
            continuation_manifest_path="/durable/manifest.json",
        )

    monkeypatch.setattr(
        discord_module, "follow_up_managed_subagent", fake_follow_up
    )
    service = object.__new__(ResidentDiscordService)
    service.runtime = SimpleNamespace(
        authorizer=SimpleNamespace(
            authorize_inbound=lambda _subject: AuthorizationDecision(True)
        ),
        project_root=tmp_path,
    )
    interaction = _interaction()
    exact_message = "  Preserve these exact leading and trailing spaces.  "

    asyncio.run(
        service.handle_follow_up_interaction(
            interaction, agent=SUFFIX, message=exact_message
        )
    )

    assert captured["run_id"] == RUN_ID
    assert captured["message"] == exact_message
    assert captured["require_live"] is True
    assert captured["idempotency_key"] == "discord-interaction:9001"
    provenance = captured["caller_provenance"]
    assert provenance["source_record_id"] == "msg_originalrequest"
    assert provenance["discord_message_id"] == "1001"
    assert provenance["discord_interaction_id"] == "9001"
    assert provenance["discord_operator_user_id"] == "42"
    assert provenance["discord_application_command"] == "follow-up"
    assert provenance["source_kind"] == "discord_application_command"
    assert interaction.response.deferred == [{"thinking": True, "ephemeral": True}]
    [(receipt, options)] = interaction.followup.sent
    assert RUN_ID in receipt
    assert "subagent-20260722-192000-aaaaaaaa" in receipt
    assert "followup-durable-receipt" in receipt
    assert "continuation_started" in receipt
    assert "completion is not claimed" in receipt
    assert "completed" not in receipt
    assert options == {"ephemeral": True}


def test_empty_message_is_rejected_before_resolution(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(
        discord_module,
        "resolve_live_managed_agent",
        lambda *args, **kwargs: pytest.fail("empty message resolved a target"),
    )
    service = object.__new__(ResidentDiscordService)
    service.runtime = SimpleNamespace(
        authorizer=SimpleNamespace(
            authorize_inbound=lambda _subject: AuthorizationDecision(True)
        ),
        project_root=tmp_path,
    )
    interaction = _interaction()

    asyncio.run(
        service.handle_follow_up_interaction(
            interaction, agent=SUFFIX, message="   "
        )
    )

    assert interaction.response.sent == [
        (
            "Follow-up rejected: message must not be empty. No instruction was attached.",
            {"ephemeral": True},
        )
    ]
    assert interaction.followup.sent == []
