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


def _provenance(*, conversation_key: str = "discord:dm:42") -> dict:
    return {
        "schema_version": "arnold-resident-delegation-provenance-v1",
        "applicability": "applicable",
        "transport": "discord",
        "resident_conversation_id": "rconv_followupcommand",
        "source_record_id": "msg_originalrequest",
        "conversation_key": conversation_key,
        "discord_message_id": "1001",
        "reply_to_message_id": "1001",
        "dm_user_id": "42" if conversation_key == "discord:dm:42" else None,
        "guild_id": None if conversation_key == "discord:dm:42" else "7",
        "channel_id": None if conversation_key == "discord:dm:42" else "8",
        "source_kind": "discord_inbound_message",
    }


def _row(
    run_id: str = RUN_ID,
    *,
    evidence_class: str = "canonical",
    provenance: dict | None = None,
) -> dict:
    return {
        "run_id": run_id,
        "live": True,
        "status": "running",
        "evidence_class": evidence_class,
        "manifest_path": f"/workspace/project/{run_id}/manifest.json",
        "launch_provenance": provenance or _provenance(),
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
def test_full_and_displayed_suffix_resolve_from_only_live_canonical_rows(
    tmp_path: Path, monkeypatch, selector: str
) -> None:
    captured: dict = {}

    def inventory(**kwargs):
        captured.update(kwargs)
        return {
            "running": [
                _row(evidence_class="legacy_compatibility"),
                _row(),
            ],
            "queued": [{"run_id": RUN_ID}],
            "recent": [{"run_id": RUN_ID}],
        }

    monkeypatch.setattr(module, "list_managed_resident_agents", inventory)

    target = module.resolve_live_managed_agent(
        selector, project_root=tmp_path, workspace_root=None
    )

    assert target.run_id == RUN_ID
    assert target.status == "running"
    assert captured["recent_limit"] == 0
    assert captured["queue_limit"] == 0


def test_missing_noncanonical_and_ambiguous_live_selectors_fail_closed(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(
        module,
        "list_managed_resident_agents",
        lambda **_kwargs: {"running": [_row(evidence_class="legacy_compatibility")]},
    )
    with pytest.raises(module.DiscordFollowUpError, match="no live canonical"):
        module.resolve_live_managed_agent(
            RUN_ID, project_root=tmp_path, workspace_root=None
        )

    other = "subagent-20260723-191551-60596066"
    monkeypatch.setattr(
        module,
        "list_managed_resident_agents",
        lambda **_kwargs: {"running": [_row(), _row(other)]},
    )
    with pytest.raises(module.DiscordFollowUpError, match="ambiguous"):
        module.resolve_live_managed_agent(
            SUFFIX, project_root=tmp_path, workspace_root=None
        )


def test_command_provenance_requires_exact_conversation_custody() -> None:
    target = module.LiveManagedAgentTarget(
        run_id=RUN_ID,
        manifest_path="/durable/manifest.json",
        launch_provenance=_provenance(),
        status="running",
    )

    with pytest.raises(module.DiscordFollowUpError, match="different Discord conversation"):
        module.command_control_provenance(
            target,
            interaction_id="9001",
            operator_user_id="42",
            conversation_key="discord:guild:7:channel:8",
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


def test_invocation_forwards_exact_message_provenance_and_interrupt_receipt(
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
