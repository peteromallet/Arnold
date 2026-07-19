from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

from arnold.runtime.durable_ops import OperationState
from agentbox.config import AgentBoxConfig
from agentbox.operations import (
    create_agentbox_operation,
    load_agentbox_operation,
    update_agentbox_operation,
)
from agentbox.resident_profile import (
    AGENTBOX_OPERATOR_TOOL_NAMES,
    AgentBoxOperatorProfile,
)
from agentbox.run_dirs import append_stdout, ensure_run_dir
from arnold_pipelines.megaplan.resident.cli import (
    _register_resident_subcommands,
    _resident_config,
    _resident_discord,
    _resident_profile,
)
from arnold_pipelines.megaplan.resident.agent_loop import (
    AgentRequest,
    AgentResponse,
    FakeAgentRunner,
    FakeAgentStep,
)
from arnold_pipelines.megaplan.resident.auth import AuthorizationSubject, ConfirmationManager, ResidentAuthorizer
from arnold_pipelines.megaplan.resident.config import ResidentConfig
from arnold_pipelines.megaplan.resident.runtime import InboundEvent, OutboundMessage, ResidentRuntime
from arnold_pipelines.megaplan.store import FileStore, ResidentConversationInput


def test_agentbox_operator_profile_registers_exact_v0_tool_catalog(
    tmp_path: Path,
) -> None:
    profile = AgentBoxOperatorProfile(
        store=FileStore(tmp_path / "store"),
        agentbox_config_factory=lambda: AgentBoxConfig(workspace_root=tmp_path / "agentbox"),
    )

    tools = profile.tools().list()

    assert tuple(tool.name for tool in tools) == AGENTBOX_OPERATOR_TOOL_NAMES
    assert {field for tool in tools for field in tool.input_model.model_fields} >= {
        "title",
        "repo",
        "spec",
        "operation",
        "stream",
        "lines",
        "kind",
        "query",
    }
    assert "actor_user_id" not in {
        field for tool in tools for field in tool.input_model.model_fields
    }
    assert "guild_id" not in {
        field for tool in tools for field in tool.input_model.model_fields
    }
    assert "channel_id" not in {
        field for tool in tools for field in tool.input_model.model_fields
    }


def test_agentbox_operator_help_lists_v0_capabilities_without_slash_commands(
    tmp_path: Path,
) -> None:
    profile = AgentBoxOperatorProfile(
        store=FileStore(tmp_path / "store"),
        agentbox_config_factory=lambda: AgentBoxConfig(workspace_root=tmp_path / "agentbox"),
    )
    runner = FakeAgentRunner(
        [
            FakeAgentStep.call("help", {}),
            FakeAgentStep.final("done"),
        ]
    )

    response = asyncio.run(
        runner.run(
            AgentRequest(
                conversation_id="conversation-1",
                messages=({"role": "user", "content": "help"},),
                system_prompt="test",
            ),
            profile.tools(),
        )
    )

    result = response.tool_calls[0].result

    assert result["ok"] is True
    assert result["data"] == {
        "profile": "agentbox_operator",
        "action": "help",
        "next_state": "choose_v0_tool",
        "tools": [
            {
                "name": "ticket_new",
                "capability": "create a tracked AgentBox ticket",
                "required_fields": ["title"],
                "optional_fields": ["body", "tags", "repo", "codebase_id"],
            },
            {
                "name": "chain_launch",
                "capability": "launch a Megaplan chain through AgentBox",
                "required_fields": ["repo", "spec"],
                "optional_fields": [
                    "operation_id",
                    "base_ref",
                    "confirmation_request_id",
                    "confirmation_phrase",
                ],
            },
            {
                "name": "status",
                "capability": "inspect AgentBox operation status",
                "required_fields": [],
                "optional_fields": ["operation"],
            },
            {
                "name": "logs",
                "capability": "read bounded AgentBox operation logs",
                "required_fields": ["operation"],
                "optional_fields": ["stream", "lines"],
            },
            {
                "name": "help",
                "capability": "list AgentBox Operator v0 tool capabilities",
                "required_fields": [],
                "optional_fields": [],
            },
            {
                "name": "resolve",
                "capability": "resolve operation, repo, or ticket references without side effects",
                "required_fields": ["query"],
                "optional_fields": ["kind"],
            },
        ],
    }
    assert "slash" not in str(result["data"]).lower()


def test_agentbox_operator_profile_loads_bounded_hot_context(
    tmp_path: Path,
) -> None:
    store = FileStore(tmp_path / "store")
    conversation = store.upsert_resident_conversation(
        ResidentConversationInput(
            conversation_key="discord:guild:g1:channel:c1",
            guild_id="g1",
            channel_id="c1",
        )
    )
    for index in range(7):
        message = store.create_message(
            epic_id=None,
            conversation_id=conversation.id,
            direction="inbound",
            content=f"message {index}",
        )
        turn = store.create_turn(
            epic_id=None,
            triggered_by_message_ids=[message.id],
        )
        store.record_tool_call(
            turn_id=turn.id,
            tool_name="help",
            operation_kind="read",
            arguments={},
            result={"ok": True, "index": index},
            duration_ms=1,
        )
    agentbox_config = AgentBoxConfig(workspace_root=tmp_path / "agentbox")
    for index in range(7):
        create_agentbox_operation(agentbox_config, f"op-{index}", command="echo hi")
    profile = AgentBoxOperatorProfile(
        store=store,
        agentbox_config_factory=lambda: agentbox_config,
    )

    context = asyncio.run(profile.load_hot_context(conversation.id))

    assert context["profile"] == "agentbox_operator"
    assert context["conversation"]["id"] == conversation.id
    assert len(context["recent_messages"]) == 5
    assert len(context["recent_tool_calls"]) == 5
    assert len(context["recent_operations"]) == 5
    assert all("text" not in entry for op in context["recent_operations"] for entry in op["logs"])


def test_agentbox_operator_profile_selected_by_config_and_discord_cli(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.delenv("MEGAPLAN_RESIDENT_MODEL_PROVIDER", raising=False)
    monkeypatch.delenv("MEGAPLAN_RESIDENT_MODEL", raising=False)
    parser = argparse.ArgumentParser()
    _register_resident_subcommands(parser)
    args = parser.parse_args(
        [
            "discord",
            "--store-root",
            str(tmp_path / "store"),
            "--profile",
            "agentbox_operator",
            "--dry-run",
        ]
    )

    config = _resident_config(args)
    dry_run = _resident_discord(
        tmp_path,
        FileStore(tmp_path / "store"),
        config,
        dry_run=True,
    )
    selected = _resident_profile(
        store=FileStore(tmp_path / "profile-store"),
        authorizer=None,
        config=config,
    )
    env_config = ResidentConfig.from_env({"MEGAPLAN_RESIDENT_PROFILE": "agentbox_operator"})

    assert config.profile == "agentbox_operator"
    assert dry_run["profile"] == "agentbox_operator"
    assert dry_run["model_provider"] == "hermes"
    assert dry_run["model"] == "zhipu:glm-5.2"
    assert isinstance(selected, AgentBoxOperatorProfile)
    assert ResidentConfig().profile == "megaplan"
    assert ResidentConfig().model_provider == "hermes"
    assert ResidentConfig().model_name == "zhipu:glm-5.2"
    assert env_config.profile == "agentbox_operator"


def test_agentbox_operator_runs_through_resident_runtime_persistence_and_outbound_sink(
    tmp_path: Path,
) -> None:
    store = FileStore(tmp_path / "store")
    codebase = store.create_codebase(
        owner="owner",
        name="repo",
        default_branch="main",
        codebase_id="codebase-1",
    )
    config = ResidentConfig(
        profile="agentbox_operator",
        allowed_user_ids=("user-1",),
        burst_idle_delay_s=0,
        burst_max_delay_s=1,
    )
    outbound = _FakeOutboundSink()
    runtime = ResidentRuntime(
        config=config,
        authorizer=ResidentAuthorizer(config),
        store=store,
        profile=AgentBoxOperatorProfile(
            store=store,
            authorizer=ResidentAuthorizer(config),
            agentbox_config_factory=lambda: AgentBoxConfig(workspace_root=tmp_path / "agentbox"),
        ),
        runner=FakeAgentRunner(
            [
                FakeAgentStep.call(
                    "ticket_new",
                    {
                        "repo": "owner/repo",
                        "title": "Runtime Persistence",
                        "body": "Exercise the resident runtime path.",
                        "tags": ["discord", "runtime"],
                    },
                ),
                FakeAgentStep.final("ticket filed"),
            ]
        ),
        outbound=outbound,
    )
    subject = AuthorizationSubject(user_id="user-1", guild_id="g1", channel_id="c1")

    asyncio.run(
        _receive_and_flush(
            runtime,
            InboundEvent(
                idempotency_key="discord:message:m1",
                conversation_key="discord:guild:g1:channel:c1",
                subject=subject,
                content="file a ticket",
                raw={"discord_message_id": "m1", "conversation_metadata": {"source": "test"}},
            ),
        )
    )

    conversations = store.list_resident_conversations(transport="discord")
    assert len(conversations) == 1
    conversation = conversations[0]
    assert conversation.conversation_key == "discord:guild:g1:channel:c1"
    assert conversation.guild_id == "g1"
    assert conversation.channel_id == "c1"
    assert conversation.metadata["last_subject_user_id"] == "user-1"
    assert conversation.metadata["source"] == "test"

    turns = store.list_recent_turns(n=1)
    assert len(turns) == 1
    turn = turns[0]
    assert turn.status == "completed"
    assert turn.message_sent is True
    assert turn.final_output_message_id == conversation.last_outbound_message_id
    assert turn.state_at_turn["profile"] == "agentbox_operator"

    inbound_messages = store.load_messages(turn.triggered_by_message_ids)
    assert len(inbound_messages) == 1
    assert inbound_messages[0].direction == "inbound"
    assert inbound_messages[0].content == "file a ticket"
    assert inbound_messages[0].bot_turn_id == turn.id

    outbound_message = store.latest_outbound_message()
    assert outbound_message is not None
    assert outbound_message.id == turn.final_output_message_id
    assert outbound_message.conversation_id == conversation.id
    assert outbound_message.content == "ticket filed"
    assert outbound.sent == [
        OutboundMessage(
            conversation_key="discord:guild:g1:channel:c1",
            content="ticket filed",
            idempotency_key=outbound_message.idempotency_key,
                metadata={
                    "conversation_id": conversation.id,
                    "message_id": outbound_message.id,
                    "turn_id": turn.id,
                    "discord_reply_to_message_id": "m1",
                    "discord_processing_message_ids": ["m1"],
                    "discord_processing_turn_id": turn.id,
                    "discord_processing_continues": False,
                },
        )
    ]

    tool_calls = store.search_tool_calls_by(tool_name="ticket_new", limit=10)
    assert len(tool_calls) == 1
    assert tool_calls[0].turn_id == turn.id
    assert tool_calls[0].result["ok"] is True
    ticket_id = tool_calls[0].result["data"]["ticket_id"]
    ticket = store.load_ticket(ticket_id)
    assert ticket is not None
    assert ticket.title == "Runtime Persistence"
    assert ticket.codebase_id == codebase.id
    assert ticket.filed_by_actor_id == "user-1"


def test_resident_runtime_includes_replied_to_discord_message_in_runner_context(
    tmp_path: Path,
) -> None:
    store = FileStore(tmp_path / "store")
    config = ResidentConfig(
        profile="agentbox_operator",
        allowed_user_ids=("user-1",),
        burst_idle_delay_s=0,
        burst_max_delay_s=1,
    )
    authorizer = ResidentAuthorizer(config)
    runner = _RecordingFakeRunner([FakeAgentStep.final("handled")])
    outbound = _FakeOutboundSink()
    runtime = ResidentRuntime(
        config=config,
        authorizer=authorizer,
        store=store,
        profile=AgentBoxOperatorProfile(
            store=store,
            authorizer=authorizer,
            agentbox_config_factory=lambda: AgentBoxConfig(workspace_root=tmp_path / "agentbox"),
        ),
        runner=runner,
        outbound=outbound,
    )
    conversation = store.upsert_resident_conversation(
        ResidentConversationInput(
            transport="discord",
            conversation_key="discord:guild:g1:channel:c1",
            guild_id="g1",
            channel_id="c1",
        ),
        idempotency_key="conversation-1",
    )
    store.create_message(
        epic_id=None,
        conversation_id=conversation.id,
        direction="inbound",
        content="prior message body",
        discord_message_id="discord-prior",
        idempotency_key="prior-message",
    )

    asyncio.run(
        _receive_and_flush(
            runtime,
            InboundEvent(
                idempotency_key="discord:message:reply-m1",
                conversation_key="discord:guild:g1:channel:c1",
                subject=AuthorizationSubject(user_id="user-1", guild_id="g1", channel_id="c1"),
                content="answering that",
                raw={
                    "discord_message_id": "reply-m1",
                    "discord_reference_message_id": "discord-prior",
                },
            ),
        )
    )

    assert runner.captured_request is not None
    prompt = runner.captured_request.messages[-1]
    assert prompt["role"] == "user"
    assert "[Discord reply ancestry — nearest parent first; current message excluded]" in prompt["content"]
    assert "Discord message id: discord-prior" in prompt["content"]
    assert "prior message body" in prompt["content"]
    assert prompt["content"].endswith("Content truncated: no\nanswering that")
    assert outbound.sent[-1].metadata["discord_reply_to_message_id"] == "reply-m1"


def test_agentbox_operator_resident_runtime_denies_non_allowlisted_discord_author_before_execution(
    tmp_path: Path,
) -> None:
    store = FileStore(tmp_path / "store")
    config = ResidentConfig(
        profile="agentbox_operator",
        allowed_user_ids=("user-1",),
        burst_idle_delay_s=0,
        burst_max_delay_s=1,
    )
    authorizer = ResidentAuthorizer(config)
    outbound = _FakeOutboundSink()
    runtime = ResidentRuntime(
        config=config,
        authorizer=authorizer,
        store=store,
        profile=AgentBoxOperatorProfile(
            store=store,
            authorizer=authorizer,
            agentbox_config_factory=lambda: AgentBoxConfig(workspace_root=tmp_path / "agentbox"),
        ),
        runner=_ExplodingAgentRunner(),
        outbound=outbound,
    )

    asyncio.run(
        _receive_and_flush(
            runtime,
            InboundEvent(
                idempotency_key="discord:message:denied-m1",
                conversation_key="discord:guild:g1:channel:c1",
                subject=AuthorizationSubject(user_id="user-2", guild_id="g1", channel_id="c1"),
                content="file a ticket",
                raw={"discord_message_id": "denied-m1"},
            ),
        )
    )

    assert outbound.sent == []
    assert store.list_resident_conversations(transport="discord") == []
    assert store.list_recent_turns(n=10) == []
    assert store.search_tool_calls_by(limit=10) == []
    assert store.latest_outbound_message() is None

    assert len(authorizer.denials) == 1
    denial = authorizer.denials[0]
    assert denial.user_id == "user-2"
    assert denial.guild_id == "g1"
    assert denial.channel_id == "c1"
    assert denial.action == "inbound"
    assert denial.reason == "user_not_allowed"

    log_files = list((tmp_path / "store" / "system_logs").glob("*.json"))
    assert len(log_files) == 1
    log = json.loads(log_files[0].read_text(encoding="utf-8"))
    assert log["level"] == "warn"
    assert log["category"] == "system"
    assert log["event_type"] == "resident_inbound_denied"
    assert log["message"] == "Resident inbound event denied before execution"
    assert log["details"]["reason"] == "user_not_allowed"
    assert log["details"]["audit"] | {"occurred_at": "<dynamic>"} == {
        "user_id": "user-2",
        "guild_id": "g1",
        "channel_id": "c1",
        "action": "inbound",
        "reason": "user_not_allowed",
        "occurred_at": "<dynamic>",
    }


def test_agentbox_operator_ticket_new_uses_runtime_subject_for_actor_and_slug(
    tmp_path: Path,
) -> None:
    store = FileStore(tmp_path / "store")
    codebase = store.create_codebase(
        owner="owner",
        name="repo",
        default_branch="main",
        codebase_id="codebase-1",
    )
    profile = AgentBoxOperatorProfile(
        store=store,
        authorizer=ResidentAuthorizer(ResidentConfig(allowed_user_ids=("user-1",))),
        agentbox_config_factory=lambda: AgentBoxConfig(workspace_root=tmp_path / "agentbox"),
    )
    runner = FakeAgentRunner(
        [
            FakeAgentStep.call(
                "ticket_new",
                {
                    "repo": "owner/repo",
                    "title": "Fix Discord Thin Path",
                    "body": "Keep the ticket concise.",
                    "tags": ["discord", "agentbox"],
                },
            ),
            FakeAgentStep.final("done"),
        ]
    )

    response = asyncio.run(
        runner.run(
            AgentRequest(
                conversation_id="conversation-1",
                messages=({"role": "user", "content": "file a ticket"},),
                system_prompt="test",
                subject=AuthorizationSubject(user_id="user-1", guild_id="g1", channel_id="c1"),
            ),
            profile.tools(),
        )
    )

    result = response.tool_calls[0].result
    ticket_id = result["data"]["ticket"]["id"]
    ticket = store.load_ticket(ticket_id)

    assert result["ok"] is True
    assert result["data"]["ticket"] == {
        "id": ticket_id,
        "title": "Fix Discord Thin Path",
        "status": "open",
        "codebase_id": codebase.id,
        "slug": "fix-discord-thin-path",
        "tags": ["discord", "agentbox"],
        "filed_by_actor_id": "user-1",
    }
    assert result["data"]["action"] == "ticket_new"
    assert result["data"]["ticket_id"] == ticket_id
    assert result["data"]["next_state"] == "ticket_open"
    assert ticket is not None
    assert ticket.slug == "fix-discord-thin-path"
    assert ticket.filed_by_actor_id == "user-1"
    assert ticket.codebase_id == codebase.id


def test_agentbox_operator_ticket_new_rejects_unauthorized_runtime_subject(
    tmp_path: Path,
) -> None:
    store = FileStore(tmp_path / "store")
    store.create_codebase(
        owner="owner",
        name="repo",
        default_branch="main",
        codebase_id="codebase-1",
    )
    profile = AgentBoxOperatorProfile(
        store=store,
        authorizer=ResidentAuthorizer(ResidentConfig(allowed_user_ids=("user-1",))),
        agentbox_config_factory=lambda: AgentBoxConfig(workspace_root=tmp_path / "agentbox"),
    )
    runner = FakeAgentRunner(
        [
            FakeAgentStep.call("ticket_new", {"repo": "owner/repo", "title": "Denied"}),
            FakeAgentStep.final("done"),
        ]
    )

    response = asyncio.run(
        runner.run(
            AgentRequest(
                conversation_id="conversation-1",
                messages=({"role": "user", "content": "file a ticket"},),
                system_prompt="test",
                subject=AuthorizationSubject(user_id="user-2", guild_id="g1", channel_id="c1"),
            ),
            profile.tools(),
        )
    )

    result = response.tool_calls[0].result

    assert result["ok"] is False
    assert result["data"]["authorization_denied"] is True
    assert store.list_tickets(codebase_id="codebase-1") == []


def test_agentbox_operator_chain_launch_requires_cloud_start_confirmation(
    tmp_path: Path,
) -> None:
    profile = AgentBoxOperatorProfile(
        authorizer=ResidentAuthorizer(
            ResidentConfig(
                allowed_user_ids=("admin-1",),
                admin_user_ids=("admin-1",),
            )
        ),
        confirmation_manager=ConfirmationManager(ResidentConfig()),
        agentbox_config_factory=lambda: AgentBoxConfig(workspace_root=tmp_path / "agentbox"),
    )
    runner = FakeAgentRunner(
        [
            FakeAgentStep.call(
                "chain_launch",
                {"repo": "owner/repo", "spec": "plans/chain.yaml", "operation_id": "chain-1"},
            ),
            FakeAgentStep.final("done"),
        ]
    )

    response = asyncio.run(
        runner.run(
            AgentRequest(
                conversation_id="conversation-1",
                messages=({"role": "user", "content": "launch chain"},),
                system_prompt="test",
                subject=AuthorizationSubject(user_id="admin-1", guild_id="g1", channel_id="c1"),
            ),
            profile.tools(),
        )
    )

    result = response.tool_calls[0].result

    assert result["ok"] is False
    assert result["data"]["confirmation_required"] is True
    assert result["data"]["target_summary"] == "owner/repo plans/chain.yaml"
    assert "confirm cloud_start" in result["data"]["exact_phrase"]


def test_agentbox_operator_chain_launch_rejects_non_admin_runtime_subject(
    tmp_path: Path,
) -> None:
    profile = AgentBoxOperatorProfile(
        authorizer=ResidentAuthorizer(
            ResidentConfig(
                allowed_user_ids=("user-1",),
                admin_user_ids=("admin-1",),
            )
        ),
        confirmation_manager=ConfirmationManager(ResidentConfig(require_cloud_start_confirmation=False)),
        agentbox_config_factory=lambda: AgentBoxConfig(workspace_root=tmp_path / "agentbox"),
    )
    runner = FakeAgentRunner(
        [
            FakeAgentStep.call(
                "chain_launch",
                {"repo": "owner/repo", "spec": "plans/chain.yaml", "operation_id": "chain-1"},
            ),
            FakeAgentStep.final("done"),
        ]
    )

    response = asyncio.run(
        runner.run(
            AgentRequest(
                conversation_id="conversation-1",
                messages=({"role": "user", "content": "launch chain"},),
                system_prompt="test",
                subject=AuthorizationSubject(user_id="user-1", guild_id="g1", channel_id="c1"),
            ),
            profile.tools(),
        )
    )

    result = response.tool_calls[0].result

    assert result["ok"] is False
    assert result["data"]["authorization_denied"] is True
    assert result["data"]["reason"] == "admin_required"


def test_agentbox_operator_chain_launch_invokes_adapter_after_confirmation(
    tmp_path: Path,
    monkeypatch,
) -> None:
    agentbox_config = AgentBoxConfig(workspace_root=tmp_path / "agentbox")
    handler = _FakeChainLaunchHandler(agentbox_config)
    monkeypatch.setattr("agentbox.resident_profile.load_operation_adapter", lambda kind: handler)
    resident_config = ResidentConfig(
        allowed_user_ids=("admin-1",),
        admin_user_ids=("admin-1",),
    )
    confirmation_manager = ConfirmationManager(resident_config)
    profile = AgentBoxOperatorProfile(
        authorizer=ResidentAuthorizer(resident_config),
        confirmation_manager=confirmation_manager,
        agentbox_config_factory=lambda: agentbox_config,
    )
    subject = AuthorizationSubject(user_id="admin-1", guild_id="g1", channel_id="c1")
    request = confirmation_manager.request_confirmation(
        subject=subject,
        action="cloud_start",
        target_summary="owner/repo plans/chain.yaml",
        metadata={"tool": "chain_launch"},
    )
    runner = FakeAgentRunner(
        [
            FakeAgentStep.call(
                "chain_launch",
                {
                    "repo": "owner/repo",
                    "spec": "plans/chain.yaml",
                    "operation_id": "chain-1",
                    "base_ref": "main",
                    "confirmation_request_id": request.id,
                    "confirmation_phrase": request.exact_phrase,
                },
            ),
            FakeAgentStep.final("done"),
        ]
    )

    response = asyncio.run(
        runner.run(
            AgentRequest(
                conversation_id="conversation-1",
                messages=({"role": "user", "content": "launch chain"},),
                system_prompt="test",
                subject=subject,
            ),
            profile.tools(),
        )
    )

    result = response.tool_calls[0].result

    assert result["ok"] is True
    assert handler.launch_calls == [
        {
            "operation_id": "chain-1",
            "repo_name": "owner/repo",
            "spec_path": Path("plans/chain.yaml"),
            "base_ref": "main",
        }
    ]
    assert result["data"] == {
        "profile": "agentbox_operator",
        "action": "chain_launch",
        "next_state": "operation_running",
        "operation_id": "chain-1",
        "operation_type": "megaplan_chain",
        "operation_state": "running",
        "launch_state": "running",
        "repo": "owner/repo",
        "resolved_spec_path": str(agentbox_config.workspace_root / "resolved-chain.yaml"),
        "validation": {
            "status": "passed",
            "spec_path": str(agentbox_config.workspace_root / "resolved-chain.yaml"),
        },
        "diagnostics": {"session": "agentbox-chain-1"},
    }


def test_agentbox_operator_chain_launch_returns_validation_diagnostics(
    tmp_path: Path,
    monkeypatch,
) -> None:
    agentbox_config = AgentBoxConfig(workspace_root=tmp_path / "agentbox")
    handler = _FakeChainLaunchHandler(
        agentbox_config,
        error_diagnostics={"kind": "missing_spec", "message": "spec not found"},
    )
    monkeypatch.setattr("agentbox.resident_profile.load_operation_adapter", lambda kind: handler)
    profile = AgentBoxOperatorProfile(
        authorizer=ResidentAuthorizer(
            ResidentConfig(
                allowed_user_ids=("admin-1",),
                admin_user_ids=("admin-1",),
                require_cloud_start_confirmation=False,
            )
        ),
        agentbox_config_factory=lambda: agentbox_config,
    )
    runner = FakeAgentRunner(
        [
            FakeAgentStep.call(
                "chain_launch",
                {"repo": "owner/repo", "spec": "missing.yaml", "operation_id": "chain-1"},
            ),
            FakeAgentStep.final("done"),
        ]
    )

    response = asyncio.run(
        runner.run(
            AgentRequest(
                conversation_id="conversation-1",
                messages=({"role": "user", "content": "launch chain"},),
                system_prompt="test",
                subject=AuthorizationSubject(user_id="admin-1", guild_id="g1", channel_id="c1"),
            ),
            profile.tools(),
        )
    )

    result = response.tool_calls[0].result

    assert result["ok"] is False
    assert result["data"]["operation_id"] == "chain-1"
    assert result["data"]["operation_state"] == "failed"
    assert result["data"]["launch_state"] == "failed_before_running"
    assert result["data"]["repo"] == "owner/repo"
    assert result["data"]["validation"] == {"status": "failed"}
    assert result["data"]["diagnostics"] == {"kind": "missing_spec", "message": "spec not found"}


def test_agentbox_operator_chain_launch_persists_guardian_notification_metadata(
    tmp_path: Path,
    monkeypatch,
) -> None:
    agentbox_config = AgentBoxConfig(workspace_root=tmp_path / "agentbox")
    handler = _FakeChainLaunchHandler(agentbox_config)
    monkeypatch.setattr("agentbox.resident_profile.load_operation_adapter", lambda kind: handler)
    store = FileStore(tmp_path / "store")
    conversation = store.upsert_resident_conversation(
        ResidentConversationInput(
            conversation_key="discord:guild:g1:channel:c1",
            active_epic_id="epic-1",
        ),
        idempotency_key="conversation-1",
    )
    profile = AgentBoxOperatorProfile(
        store=store,
        authorizer=ResidentAuthorizer(
            ResidentConfig(
                allowed_user_ids=("admin-1",),
                admin_user_ids=("admin-1",),
                require_cloud_start_confirmation=False,
            )
        ),
        agentbox_config_factory=lambda: agentbox_config,
    )
    runner = FakeAgentRunner(
        [
            FakeAgentStep.call(
                "chain_launch",
                {"repo": "owner/repo", "spec": "plans/chain.yaml", "operation_id": "chain-1"},
            ),
            FakeAgentStep.final("done"),
        ]
    )

    response = asyncio.run(
        runner.run(
            AgentRequest(
                conversation_id=conversation.id,
                messages=({"role": "user", "content": "launch chain"},),
                system_prompt="test",
                subject=AuthorizationSubject(user_id="admin-1", guild_id="g1", channel_id="c1"),
            ),
            profile.tools(),
        )
    )

    result = response.tool_calls[0].result
    run = load_agentbox_operation(agentbox_config, "chain-1")

    assert result["ok"] is True
    assert run.metadata["guardian_notification_conversation_id"] == conversation.id
    assert (
        run.metadata["guardian_notification_conversation_key"]
        == "discord:guild:g1:channel:c1"
    )
    assert run.metadata["guardian_notifications_disabled"] is False


def test_agentbox_operator_chain_launch_disables_guardian_notifications_without_conversation(
    tmp_path: Path,
    monkeypatch,
) -> None:
    agentbox_config = AgentBoxConfig(workspace_root=tmp_path / "agentbox")
    handler = _FakeChainLaunchHandler(agentbox_config)
    monkeypatch.setattr("agentbox.resident_profile.load_operation_adapter", lambda kind: handler)
    store = FileStore(tmp_path / "store")
    profile = AgentBoxOperatorProfile(
        store=store,
        authorizer=ResidentAuthorizer(
            ResidentConfig(
                allowed_user_ids=("admin-1",),
                admin_user_ids=("admin-1",),
                require_cloud_start_confirmation=False,
            )
        ),
        agentbox_config_factory=lambda: agentbox_config,
    )
    runner = FakeAgentRunner(
        [
            FakeAgentStep.call(
                "chain_launch",
                {"repo": "owner/repo", "spec": "plans/chain.yaml", "operation_id": "chain-1"},
            ),
            FakeAgentStep.final("done"),
        ]
    )

    response = asyncio.run(
        runner.run(
            AgentRequest(
                conversation_id="missing-conversation",
                messages=({"role": "user", "content": "launch chain"},),
                system_prompt="test",
                subject=AuthorizationSubject(user_id="admin-1", guild_id="g1", channel_id="c1"),
            ),
            profile.tools(),
        )
    )

    result = response.tool_calls[0].result
    run = load_agentbox_operation(agentbox_config, "chain-1")

    assert result["ok"] is True
    assert run.metadata["guardian_notification_conversation_id"] == "missing-conversation"
    assert run.metadata["guardian_notifications_disabled"] is True
    assert (
        run.metadata["guardian_notifications_disabled_reason"]
        == "resident_conversation_not_found"
    )


def test_agentbox_operator_status_resolves_operation_before_shared_status_view(
    tmp_path: Path,
) -> None:
    agentbox_config = AgentBoxConfig(workspace_root=tmp_path / "agentbox")
    create_agentbox_operation(
        agentbox_config,
        "chain-running",
        command="echo running",
        repo_names=["owner/repo"],
        launch_state="running",
        metadata={"resolved_spec_path": "owner/repo/chain.yaml"},
    )
    update_agentbox_operation(agentbox_config, "chain-running", state=OperationState.RUNNING)
    profile = AgentBoxOperatorProfile(agentbox_config_factory=lambda: agentbox_config)
    runner = FakeAgentRunner(
        [
            FakeAgentStep.call("status", {"operation": "owner/repo"}),
            FakeAgentStep.final("done"),
        ]
    )

    response = asyncio.run(
        runner.run(
            AgentRequest(
                conversation_id="conversation-1",
                messages=({"role": "user", "content": "status owner/repo"},),
                system_prompt="test",
            ),
            profile.tools(),
        )
    )

    result = response.tool_calls[0].result

    assert result["ok"] is True
    assert result["data"]["resolve"]["status"] == "single"
    assert result["data"]["resolve"]["operation"]["operation_id"] == "chain-running"
    assert result["data"]["status"]["operation_id"] == "chain-running"
    assert result["data"]["status"]["operation_state"] == "running"
    assert result["data"]["status"]["repo_names"] == ["owner/repo"]


def test_agentbox_operator_logs_resolves_operation_and_returns_bounded_metadata(
    tmp_path: Path,
) -> None:
    agentbox_config = AgentBoxConfig(workspace_root=tmp_path / "agentbox")
    create_agentbox_operation(
        agentbox_config,
        "chain-logs",
        command="echo logs",
        repo_names=["owner/repo"],
        metadata={"resolved_spec_path": "owner/repo/chain.yaml"},
    )
    paths = ensure_run_dir(agentbox_config, "chain-logs")
    append_stdout(paths, "one\n")
    append_stdout(paths, "two\n")
    append_stdout(paths, "three\n")
    profile = AgentBoxOperatorProfile(agentbox_config_factory=lambda: agentbox_config)
    runner = FakeAgentRunner(
        [
            FakeAgentStep.call(
                "logs",
                {"operation": "owner/repo", "stream": "stdout", "lines": 2},
            ),
            FakeAgentStep.final("done"),
        ]
    )

    response = asyncio.run(
        runner.run(
            AgentRequest(
                conversation_id="conversation-1",
                messages=({"role": "user", "content": "logs owner/repo"},),
                system_prompt="test",
            ),
            profile.tools(),
        )
    )

    result = response.tool_calls[0].result

    assert result["ok"] is True
    assert result["data"]["resolve"]["status"] == "single"
    assert result["data"]["logs"]["operation_id"] == "chain-logs"
    assert result["data"]["logs"]["logs"][0]["text"] == "two\nthree\n"
    assert result["data"]["logs"]["logs"][0]["requested_lines"] == 2
    assert result["data"]["logs"]["logs"][0]["returned_lines"] == 2
    assert result["data"]["logs"]["logs"][0]["truncated"] is True
    assert result["data"]["logs"]["logs"][0]["source"] == "file"


def test_agentbox_operator_status_and_resolve_ask_one_clarifying_question_on_ambiguity(
    tmp_path: Path,
) -> None:
    agentbox_config = AgentBoxConfig(workspace_root=tmp_path / "agentbox")
    create_agentbox_operation(
        agentbox_config,
        "alpha-chain",
        command="echo alpha",
        metadata={"resolved_spec_path": "shared/chain.yaml"},
    )
    create_agentbox_operation(
        agentbox_config,
        "beta-chain",
        command="echo beta",
        metadata={"resolved_spec_path": "shared/chain.yaml"},
    )
    create_agentbox_operation(
        agentbox_config,
        "gamma-chain",
        command="echo gamma",
        repo_names=["owner/repo"],
        launch_state="running",
        metadata={"resolved_spec_path": "unique/chain.yaml"},
    )
    profile = AgentBoxOperatorProfile(agentbox_config_factory=lambda: agentbox_config)
    runner = FakeAgentRunner(
        [
            FakeAgentStep.call("status", {"operation": "shared"}),
            FakeAgentStep.call("resolve", {"kind": "operation", "query": "gamma-chain"}),
            FakeAgentStep.call("resolve", {"kind": "operation", "query": "shared"}),
            FakeAgentStep.call("resolve", {"kind": "operation", "query": "missing"}),
            FakeAgentStep.final("done"),
        ]
    )

    response = asyncio.run(
        runner.run(
            AgentRequest(
                conversation_id="conversation-1",
                messages=({"role": "user", "content": "status shared"},),
                system_prompt="test",
            ),
            profile.tools(),
        )
    )

    status_result = response.tool_calls[0].result
    resolve_single = response.tool_calls[1].result
    resolve_ambiguous = response.tool_calls[2].result
    resolve_missing = response.tool_calls[3].result

    assert status_result["ok"] is False
    assert status_result["message"] == "Which operation did you mean: alpha-chain, beta-chain?"
    assert status_result["data"]["resolve"]["status"] == "ambiguous"
    assert [row["operation_id"] for row in status_result["data"]["resolve"]["candidates"]] == [
        "alpha-chain",
        "beta-chain",
    ]
    assert resolve_single["ok"] is True
    assert resolve_single["message"] == "gamma-chain"
    assert resolve_single["data"]["operation_id"] == "gamma-chain"
    assert resolve_single["data"]["next_state"] == "resolved"
    assert resolve_single["data"]["resolve"] == {
        "status": "single",
        "query": "gamma-chain",
        "operation": {
            "operation_id": "gamma-chain",
            "operation_type": "agentbox_host",
            "operation_state": "pending",
            "launch_state": "running",
            "repo_names": ["owner/repo"],
            "matched_by": "operation_id_exact",
        },
        "candidates": [],
        "question": None,
    }
    assert resolve_ambiguous["ok"] is False
    assert resolve_ambiguous["message"] == "Which operation did you mean: alpha-chain, beta-chain?"
    assert resolve_ambiguous["data"]["resolve"] == status_result["data"]["resolve"]
    assert resolve_ambiguous["data"]["action"] == "resolve"
    assert resolve_ambiguous["data"]["next_state"] == "needs_clarification"
    assert resolve_missing["ok"] is False
    assert resolve_missing["message"] == "No AgentBox operation matched 'missing'. Which operation id should I use?"
    assert resolve_missing["data"]["next_state"] == "not_found"
    assert resolve_missing["data"]["resolve"] == {
        "status": "no_match",
        "query": "missing",
        "operation": None,
        "candidates": [],
        "question": "No AgentBox operation matched 'missing'. Which operation id should I use?",
    }


def test_agentbox_operator_resolve_shapes_repo_and_ticket_results_without_side_effects(
    tmp_path: Path,
) -> None:
    store = FileStore(tmp_path / "store")
    codebase = store.create_codebase(
        owner="owner",
        name="repo",
        default_branch="main",
        codebase_id="codebase-1",
    )
    other_codebase = store.create_codebase(
        owner="owner",
        name="repo-tools",
        default_branch="main",
        codebase_id="codebase-2",
    )
    ticket = store.create_ticket(
        codebase_id=codebase.id,
        title="Fix Discord Thin Path",
        body="Keep it thin.",
        tags=["discord"],
        slug="fix-discord-thin-path",
    )
    other_ticket = store.create_ticket(
        codebase_id=codebase.id,
        title="Fix Discord Fixtures",
        body="Keep fixtures thin.",
        tags=["discord"],
        slug="fix-discord-fixtures",
    )
    profile = AgentBoxOperatorProfile(
        store=store,
        agentbox_config_factory=lambda: AgentBoxConfig(workspace_root=tmp_path / "agentbox"),
    )
    runner = FakeAgentRunner(
        [
            FakeAgentStep.call("resolve", {"kind": "repo", "query": "owner/repo"}),
            FakeAgentStep.call("resolve", {"kind": "repo", "query": "repo"}),
            FakeAgentStep.call("resolve", {"kind": "ticket", "query": ticket.id}),
            FakeAgentStep.call("resolve", {"kind": "ticket", "query": "discord"}),
            FakeAgentStep.call("resolve", {"kind": "ticket", "query": "missing"}),
            FakeAgentStep.final("done"),
        ]
    )

    response = asyncio.run(
        runner.run(
            AgentRequest(
                conversation_id="conversation-1",
                messages=({"role": "user", "content": "resolve things"},),
                system_prompt="test",
            ),
            profile.tools(),
        )
    )

    repo_single = response.tool_calls[0].result
    repo_ambiguous = response.tool_calls[1].result
    ticket_single = response.tool_calls[2].result
    ticket_ambiguous = response.tool_calls[3].result
    ticket_missing = response.tool_calls[4].result

    assert repo_single["ok"] is True
    assert repo_single["data"] == {
        "profile": "agentbox_operator",
        "action": "resolve",
        "next_state": "resolved",
        "resolve": {
            "status": "single",
            "kind": "repo",
            "query": "owner/repo",
            "repo": {
                "codebase_id": codebase.id,
                "repo": "owner/repo",
                "owner": "owner",
                "name": "repo",
                "default_branch": "main",
            },
            "candidates": [],
            "question": None,
        },
    }
    assert repo_ambiguous["ok"] is False
    assert repo_ambiguous["data"]["resolve"]["status"] == "ambiguous"
    assert [row["codebase_id"] for row in repo_ambiguous["data"]["resolve"]["candidates"]] == [
        codebase.id,
        other_codebase.id,
    ]
    assert ticket_single["ok"] is True
    assert ticket_single["data"]["ticket_id"] == ticket.id
    assert ticket_single["data"]["resolve"]["ticket"]["title"] == "Fix Discord Thin Path"
    assert ticket_ambiguous["ok"] is False
    assert ticket_ambiguous["data"]["next_state"] == "needs_clarification"
    assert [row["ticket_id"] for row in ticket_ambiguous["data"]["resolve"]["candidates"]] == [
        other_ticket.id,
        ticket.id,
    ]
    assert ticket_missing["ok"] is False
    assert ticket_missing["data"]["next_state"] == "not_found"
    assert ticket_missing["data"]["resolve"] == {
        "status": "no_match",
        "kind": "ticket",
        "query": "missing",
        "ticket": None,
        "candidates": [],
        "question": "No AgentBox ticket matched 'missing'. Which ticket id should I use?",
    }


def test_agentbox_operator_runtime_exercises_all_six_v0_tools(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = FileStore(tmp_path / "store")
    store.create_codebase(
        owner="owner",
        name="repo",
        default_branch="main",
        codebase_id="codebase-1",
    )
    agentbox_config = AgentBoxConfig(workspace_root=tmp_path / "agentbox")
    handler = _FakeChainLaunchHandler(agentbox_config)
    monkeypatch.setattr("agentbox.resident_profile.load_operation_adapter", lambda kind: handler)

    create_agentbox_operation(
        agentbox_config,
        "op-chain-1",
        operation_type="megaplan_chain",
        command=("fake", "chain"),
        repo_names=("owner/repo",),
        launch_state="running",
        metadata={"resolved_spec_path": str(agentbox_config.workspace_root / "resolved-chain.yaml")},
    )
    update_agentbox_operation(agentbox_config, "op-chain-1", state=OperationState.RUNNING)
    create_agentbox_operation(
        agentbox_config,
        "op-other",
        operation_type="megaplan_chain",
        command=("fake", "chain"),
        repo_names=("owner/repo",),
        launch_state="running",
        metadata={"resolved_spec_path": str(agentbox_config.workspace_root / "other-chain.yaml")},
    )
    update_agentbox_operation(agentbox_config, "op-other", state=OperationState.RUNNING)

    config = ResidentConfig(
        profile="agentbox_operator",
        allowed_user_ids=("admin-1",),
        admin_user_ids=("admin-1",),
        burst_idle_delay_s=0,
        burst_max_delay_s=1,
    )
    authorizer = ResidentAuthorizer(config)
    confirmation_manager = ConfirmationManager(config)
    subject = AuthorizationSubject(user_id="admin-1", guild_id="g1", channel_id="c1")
    request = confirmation_manager.request_confirmation(
        subject=subject,
        action="cloud_start",
        target_summary="owner/repo plans/chain.yaml",
        metadata={"tool": "chain_launch"},
    )

    outbound = _FakeOutboundSink()
    runtime = ResidentRuntime(
        config=config,
        authorizer=authorizer,
        store=store,
        profile=AgentBoxOperatorProfile(
            store=store,
            authorizer=authorizer,
            confirmation_manager=confirmation_manager,
            agentbox_config_factory=lambda: agentbox_config,
        ),
        runner=FakeAgentRunner(
            [
                FakeAgentStep.call(
                    "ticket_new",
                    {
                        "repo": "owner/repo",
                        "title": "Runtime coverage",
                        "body": "Exercise all six v0 tools.",
                        "tags": ["runtime"],
                    },
                ),
                FakeAgentStep.call(
                    "chain_launch",
                    {
                        "repo": "owner/repo",
                        "spec": "plans/chain.yaml",
                        "operation_id": "chain-1",
                        "confirmation_request_id": request.id,
                        "confirmation_phrase": request.exact_phrase,
                    },
                ),
                FakeAgentStep.call("status", {"operation": "chain-1"}),
                FakeAgentStep.call("logs", {"operation": "chain-1", "lines": 10}),
                FakeAgentStep.call("resolve", {"kind": "operation", "query": "op-chain-1"}),
                FakeAgentStep.call("resolve", {"kind": "operation", "query": "op"}),
                FakeAgentStep.call("help", {}),
                FakeAgentStep.final("all tools exercised"),
            ]
        ),
        outbound=outbound,
    )

    asyncio.run(
        _receive_and_flush(
            runtime,
            InboundEvent(
                idempotency_key="discord:message:all-tools",
                conversation_key="discord:guild:g1:channel:c1",
                subject=subject,
                content="run all tools",
                raw={
                    "discord_message_id": "all-tools",
                    "conversation_metadata": {"source": "test"},
                },
            ),
        )
    )

    turns = store.list_recent_turns(n=1)
    assert len(turns) == 1
    turn = turns[0]
    assert turn.status == "completed"

    ticket_call = store.search_tool_calls_by(tool_name="ticket_new", limit=1)[0]
    ticket_id = ticket_call.result["data"]["ticket_id"]
    assert ticket_id is not None
    ticket = store.load_ticket(ticket_id)
    assert ticket.title == "Runtime coverage"
    assert ticket.filed_by_actor_id == "admin-1"

    chain_call = store.search_tool_calls_by(tool_name="chain_launch", limit=1)[0]
    assert chain_call.result["ok"] is True
    assert chain_call.result["data"]["operation_id"] == "chain-1"
    assert chain_call.result["data"]["next_state"] == "operation_running"
    assert handler.launch_calls == [
        {
            "operation_id": "chain-1",
            "repo_name": "owner/repo",
            "spec_path": Path("plans/chain.yaml"),
            "base_ref": None,
        }
    ]

    status_call = store.search_tool_calls_by(tool_name="status", limit=1)[0]
    assert status_call.result["data"]["operation_id"] == "chain-1"
    assert status_call.result["data"]["next_state"] == "inspected_operation"

    logs_call = store.search_tool_calls_by(tool_name="logs", limit=1)[0]
    assert logs_call.result["data"]["operation_id"] == "chain-1"
    assert logs_call.result["data"]["next_state"] == "inspected_logs"

    resolve_calls = store.search_tool_calls_by(tool_name="resolve", limit=2)
    single_results = [
        call for call in resolve_calls
        if call.result["data"]["resolve"]["status"] == "single"
    ]
    ambiguous_results = [
        call for call in resolve_calls
        if call.result["data"]["resolve"]["status"] == "ambiguous"
    ]
    assert len(single_results) == 1
    assert len(ambiguous_results) == 1
    single_result = single_results[0].result
    ambiguous_result = ambiguous_results[0].result
    assert single_result["data"]["operation_id"] == "op-chain-1"
    assert single_result["data"]["next_state"] == "resolved"
    assert ambiguous_result["data"]["resolve"]["status"] == "ambiguous"
    assert ambiguous_result["data"]["next_state"] == "needs_clarification"
    assert "question" in ambiguous_result["data"]["resolve"]
    assert len(ambiguous_result["data"]["resolve"]["candidates"]) >= 2

    help_call = store.search_tool_calls_by(tool_name="help", limit=1)[0]
    assert help_call.result["data"]["next_state"] == "choose_v0_tool"
    assert any(tool["name"] == "chain_launch" for tool in help_call.result["data"]["tools"])

    assert outbound.sent
    assert outbound.sent[0].content == "all tools exercised"


def test_resident_runtime_injects_conversation_history_before_current_burst(
    tmp_path: Path,
) -> None:
    store = FileStore(tmp_path / "store")
    conversation = store.upsert_resident_conversation(
        ResidentConversationInput(
            conversation_key="discord:guild:g1:channel:c1",
            guild_id="g1",
            channel_id="c1",
        )
    )
    store.create_message(
        epic_id=None,
        conversation_id=conversation.id,
        direction="inbound",
        content="earlier user message",
    )
    store.create_message(
        epic_id=None,
        conversation_id=conversation.id,
        direction="outbound",
        content="earlier bot reply",
    )
    config = ResidentConfig(
        profile="agentbox_operator",
        allowed_user_ids=("user-1",),
        history_window=10,
        burst_idle_delay_s=0,
        burst_max_delay_s=1,
    )
    authorizer = ResidentAuthorizer(config)
    runner = _RecordingFakeRunner([FakeAgentStep.final("ok")])
    runtime = ResidentRuntime(
        config=config,
        authorizer=authorizer,
        store=store,
        profile=AgentBoxOperatorProfile(
            store=store,
            authorizer=authorizer,
            agentbox_config_factory=lambda: AgentBoxConfig(workspace_root=tmp_path / "agentbox"),
        ),
        runner=runner,
        outbound=_FakeOutboundSink(),
    )

    asyncio.run(
        _receive_and_flush(
            runtime,
            InboundEvent(
                idempotency_key="discord:message:h1",
                conversation_key="discord:guild:g1:channel:c1",
                subject=AuthorizationSubject(user_id="user-1", guild_id="g1", channel_id="c1"),
                content="current burst message",
                raw={"discord_message_id": "h1"},
            ),
        )
    )

    messages = runner.captured_request.messages
    assert [(message["role"], message["content"]) for message in messages[:2]] == [
        ("user", "earlier user message"),
        ("assistant", "earlier bot reply"),
    ]
    assert messages[2]["role"] == "user"
    assert "No parent message" in messages[2]["content"]
    assert messages[2]["content"].endswith(
        "Content truncated: no\ncurrent burst message"
    )
    # The already-persisted current burst is excluded from history (no double-count).
    assert sum(1 for m in messages if m["content"].endswith("\ncurrent burst message")) == 1


def test_resident_runtime_skips_history_when_window_is_zero(tmp_path: Path) -> None:
    store = FileStore(tmp_path / "store")
    conversation = store.upsert_resident_conversation(
        ResidentConversationInput(
            conversation_key="discord:guild:g1:channel:c1",
            guild_id="g1",
            channel_id="c1",
        )
    )
    store.create_message(
        epic_id=None,
        conversation_id=conversation.id,
        direction="inbound",
        content="ignored history",
    )
    config = ResidentConfig(
        profile="agentbox_operator",
        allowed_user_ids=("user-1",),
        history_window=0,
        burst_idle_delay_s=0,
        burst_max_delay_s=1,
    )
    authorizer = ResidentAuthorizer(config)
    runner = _RecordingFakeRunner([FakeAgentStep.final("ok")])
    runtime = ResidentRuntime(
        config=config,
        authorizer=authorizer,
        store=store,
        profile=AgentBoxOperatorProfile(
            store=store,
            authorizer=authorizer,
            agentbox_config_factory=lambda: AgentBoxConfig(workspace_root=tmp_path / "agentbox"),
        ),
        runner=runner,
        outbound=_FakeOutboundSink(),
    )

    asyncio.run(
        _receive_and_flush(
            runtime,
            InboundEvent(
                idempotency_key="discord:message:h0",
                conversation_key="discord:guild:g1:channel:c1",
                subject=AuthorizationSubject(user_id="user-1", guild_id="g1", channel_id="c1"),
                content="current burst message",
                raw={"discord_message_id": "h0"},
            ),
        )
    )

    assert len(runner.captured_request.messages) == 1
    assert runner.captured_request.messages[0]["content"].endswith(
        "Content truncated: no\ncurrent burst message"
    )


def test_agentbox_search_messages_scopes_to_current_conversation(tmp_path: Path) -> None:
    store = FileStore(tmp_path / "store")
    c1 = store.upsert_resident_conversation(
        ResidentConversationInput(
            conversation_key="discord:guild:g1:channel:c1", guild_id="g1", channel_id="c1"
        )
    )
    c2 = store.upsert_resident_conversation(
        ResidentConversationInput(
            conversation_key="discord:guild:g1:channel:c2", guild_id="g1", channel_id="c2"
        )
    )
    store.create_message(
        epic_id=None, conversation_id=c1.id, direction="inbound", content="deploy the alpha service"
    )
    store.create_message(
        epic_id=None, conversation_id=c2.id, direction="inbound", content="deploy the beta service"
    )
    profile = AgentBoxOperatorProfile(
        store=store,
        authorizer=ResidentAuthorizer(ResidentConfig(allowed_user_ids=("user-1",))),
        agentbox_config_factory=lambda: AgentBoxConfig(workspace_root=tmp_path / "agentbox"),
    )
    runner = FakeAgentRunner(
        [FakeAgentStep.call("search_messages", {"query": "deploy"}), FakeAgentStep.final("done")]
    )

    response = asyncio.run(
        runner.run(
            AgentRequest(
                conversation_id=c1.id,
                messages=({"role": "user", "content": "search deploy"},),
                system_prompt="test",
                subject=AuthorizationSubject(user_id="user-1", guild_id="g1", channel_id="c1"),
            ),
            profile.tools(),
        )
    )

    result = response.tool_calls[0].result
    assert result["ok"] is True
    assert result["data"]["action"] == "search_messages"
    assert [m["content"] for m in result["data"]["messages"]] == ["deploy the alpha service"]


def test_agentbox_subagent_returns_inline_result_on_configured_model(
    tmp_path: Path,
) -> None:
    config = ResidentConfig(
        allowed_user_ids=("user-1",),
        subagent_model_name="deepseek:deepseek-chat",
        subagent_models=("kimi:kimi-k2",),
    )
    store = FileStore(tmp_path / "store")
    profile = AgentBoxOperatorProfile(
        store=store,
        authorizer=ResidentAuthorizer(config),
        config=config,
        agentbox_config_factory=lambda: AgentBoxConfig(workspace_root=tmp_path / "agentbox"),
    )
    fake_sub = _FakeSubRunner(AgentResponse(final_text="found 3 stale chains", tool_calls=()))
    profile._build_subagent_runner = lambda chosen, sub_config, max_calls: (fake_sub, "deepseek-chat")

    runner = FakeAgentRunner(
        [FakeAgentStep.call("subagent", {"prompt": "find stale chains"}), FakeAgentStep.final("summarized")]
    )

    response = asyncio.run(
        runner.run(
            AgentRequest(
                conversation_id="conversation-1",
                messages=({"role": "user", "content": "investigate"},),
                system_prompt="test",
                subject=AuthorizationSubject(user_id="user-1", guild_id="g1", channel_id="c1"),
            ),
            profile.tools(),
        )
    )

    result = response.tool_calls[0].result
    assert result["ok"] is True
    assert result["data"]["action"] == "subagent"
    assert result["data"]["final_text"] == "found 3 stale chains"
    assert result["data"]["model"] == "deepseek-chat"
    # The subagent ran on the default model and got a registry WITHOUT subagent (no recursion).
    assert fake_sub.received_request.messages == ({"role": "user", "content": "find stale chains"},)
    assert "subagent" not in {t.name for t in fake_sub.received_tools.list()}


def test_agentbox_subagent_allows_allowlisted_model_override(tmp_path: Path) -> None:
    config = ResidentConfig(
        allowed_user_ids=("user-1",),
        subagent_model_name="deepseek:deepseek-chat",
        subagent_models=("kimi:kimi-k2",),
    )
    store = FileStore(tmp_path / "store")
    profile = AgentBoxOperatorProfile(
        store=store,
        authorizer=ResidentAuthorizer(config),
        config=config,
        agentbox_config_factory=lambda: AgentBoxConfig(workspace_root=tmp_path / "agentbox"),
    )
    fake_sub = _FakeSubRunner(AgentResponse(final_text="kimi answers", tool_calls=()))
    captured: dict[str, object] = {}

    def build(chosen, sub_config, max_calls):
        captured["chosen"] = chosen
        captured["max_calls"] = max_calls
        return fake_sub, "kimi-k2"

    profile._build_subagent_runner = build

    runner = FakeAgentRunner(
        [FakeAgentStep.call("subagent", {"prompt": "x", "model": "kimi:kimi-k2"}), FakeAgentStep.final("done")]
    )

    response = asyncio.run(
        runner.run(
            AgentRequest(
                conversation_id="conversation-1",
                messages=({"role": "user", "content": "go"},),
                system_prompt="test",
                subject=AuthorizationSubject(user_id="user-1", guild_id="g1", channel_id="c1"),
            ),
            profile.tools(),
        )
    )

    result = response.tool_calls[0].result
    assert result["ok"] is True
    assert captured["chosen"] == "kimi:kimi-k2"
    assert result["data"]["model"] == "kimi-k2"


def test_agentbox_subagent_rejects_model_outside_allowlist(tmp_path: Path) -> None:
    config = ResidentConfig(
        allowed_user_ids=("user-1",),
        subagent_model_name="deepseek:deepseek-chat",
        subagent_models=("kimi:kimi-k2",),
    )
    store = FileStore(tmp_path / "store")
    profile = AgentBoxOperatorProfile(
        store=store,
        authorizer=ResidentAuthorizer(config),
        config=config,
        agentbox_config_factory=lambda: AgentBoxConfig(workspace_root=tmp_path / "agentbox"),
    )

    runner = FakeAgentRunner(
        [FakeAgentStep.call("subagent", {"prompt": "x", "model": "claude:opus"}), FakeAgentStep.final("done")]
    )

    response = asyncio.run(
        runner.run(
            AgentRequest(
                conversation_id="conversation-1",
                messages=({"role": "user", "content": "go"},),
                system_prompt="test",
                subject=AuthorizationSubject(user_id="user-1", guild_id="g1", channel_id="c1"),
            ),
            profile.tools(),
        )
    )

    result = response.tool_calls[0].result
    assert result["ok"] is False
    assert result["data"]["requested"] == "claude:opus"
    assert result["data"]["default"] == "deepseek:deepseek-chat"
    assert result["data"]["allowed"] == ["kimi:kimi-k2"]


def test_agentbox_subagent_registry_excludes_subagent_tool(tmp_path: Path) -> None:
    profile = AgentBoxOperatorProfile(
        agentbox_config_factory=lambda: AgentBoxConfig(workspace_root=tmp_path / "agentbox")
    )
    names = {tool.name for tool in profile._build_subagent_registry().list()}
    assert "subagent" not in names
    assert "search_messages" in names
    assert len(names) == len(AGENTBOX_OPERATOR_TOOL_NAMES) - 1


def test_file_store_list_conversation_messages_orders_and_excludes(tmp_path: Path) -> None:
    store = FileStore(tmp_path / "store")
    c1 = store.upsert_resident_conversation(
        ResidentConversationInput(
            conversation_key="discord:guild:g1:channel:c1", guild_id="g1", channel_id="c1"
        )
    )
    c2 = store.upsert_resident_conversation(
        ResidentConversationInput(
            conversation_key="discord:guild:g1:channel:c2", guild_id="g1", channel_id="c2"
        )
    )
    ids = []
    for index in range(4):
        message = store.create_message(
            epic_id=None, conversation_id=c1.id, direction="inbound", content=f"msg-{index}"
        )
        ids.append(message.id)
    store.create_message(
        epic_id=None, conversation_id=c2.id, direction="inbound", content="other-convo msg-0"
    )

    rows = store.list_conversation_messages(c1.id, limit=10)
    assert [r.content for r in rows] == ["msg-0", "msg-1", "msg-2", "msg-3"]
    assert all(r.conversation_id == c1.id for r in rows)

    excluded = store.list_conversation_messages(c1.id, limit=10, exclude_ids=[ids[0]])
    assert [r.content for r in excluded] == ["msg-1", "msg-2", "msg-3"]

    last_two = store.list_conversation_messages(c1.id, limit=2)
    assert [r.content for r in last_two] == ["msg-2", "msg-3"]


class _FakeChainLaunchHandler:
    def __init__(
        self,
        config: AgentBoxConfig,
        *,
        error_diagnostics: dict[str, object] | None = None,
    ) -> None:
        self.config = config
        self.error_diagnostics = error_diagnostics
        self.launch_calls: list[dict[str, object]] = []

    def launch(
        self,
        config: AgentBoxConfig,
        operation_id: str,
        *,
        repo_name: str,
        spec_path: Path,
        base_ref: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> object:
        assert config == self.config
        self.launch_calls.append(
            {
                "operation_id": operation_id,
                "repo_name": repo_name,
                "spec_path": spec_path,
                "base_ref": base_ref,
            }
        )
        if self.error_diagnostics is not None:
            create_agentbox_operation(
                config,
                operation_id,
                operation_type="megaplan_chain",
                command=("fake", "chain"),
                repo_names=(repo_name,),
                launch_state="failed_before_running",
            metadata={
                **dict(metadata or {}),
                "validation": {"status": "failed"},
                "launch_diagnostics": dict(self.error_diagnostics),
            },
            )
            update_agentbox_operation(config, operation_id, state=OperationState.FAILED)
            raise _FakeChainLaunchError(
                str(self.error_diagnostics["message"]),
                diagnostics=dict(self.error_diagnostics),
            )

        resolved_spec_path = config.workspace_root / "resolved-chain.yaml"
        create_agentbox_operation(
            config,
            operation_id,
            operation_type="megaplan_chain",
            command=("fake", "chain"),
            repo_names=(repo_name,),
            launch_state="running",
            metadata={
                **dict(metadata or {}),
                "resolved_spec_path": str(resolved_spec_path),
                "validation": {
                    "status": "passed",
                    "spec_path": str(resolved_spec_path),
                },
            },
        )
        update_agentbox_operation(config, operation_id, state=OperationState.RUNNING)
        return SimpleNamespace(
            operation_id=operation_id,
            launch_state="running",
            resolved_spec_path=resolved_spec_path,
            host_result=SimpleNamespace(diagnostics={"session": f"agentbox-{operation_id}"}),
        )


class _FakeChainLaunchError(RuntimeError):
    def __init__(self, message: str, *, diagnostics: dict[str, object]) -> None:
        super().__init__(message)
        self.diagnostics = diagnostics


class _FakeOutboundSink:
    def __init__(self) -> None:
        self.sent: list[OutboundMessage] = []

    async def send(self, message: OutboundMessage) -> None:
        self.sent.append(message)


class _ExplodingAgentRunner:
    async def run(self, request: AgentRequest, tools: object) -> object:
        raise AssertionError("resident runner should not execute for denied inbound events")


class _RecordingFakeRunner(FakeAgentRunner):
    """FakeAgentRunner that captures the AgentRequest it was handed."""

    def __init__(self, steps: list[FakeAgentStep]) -> None:
        super().__init__(steps)
        self.captured_request: AgentRequest | None = None

    async def run(self, request: AgentRequest, tools: object) -> AgentResponse:
        self.captured_request = request
        return await super().run(request, tools)


class _FakeSubRunner:
    """Stand-in for a resolved subagent runner; returns a scripted response."""

    def __init__(self, response: AgentResponse) -> None:
        self.response = response
        self.received_request: AgentRequest | None = None
        self.received_tools: object | None = None

    async def run(self, request: AgentRequest, tools: object) -> AgentResponse:
        self.received_request = request
        self.received_tools = tools
        return self.response


async def _receive_and_flush(runtime: ResidentRuntime, event: InboundEvent) -> None:
    await runtime.receive(event)
    await runtime.coalescer.flush_all()
