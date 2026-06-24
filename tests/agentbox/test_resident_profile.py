from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
from types import SimpleNamespace

from arnold.runtime.durable_ops import OperationState
from agentbox.config import AgentBoxConfig
from agentbox.operations import create_agentbox_operation, update_agentbox_operation
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
from arnold_pipelines.megaplan.resident.agent_loop import AgentRequest, FakeAgentRunner, FakeAgentStep
from arnold_pipelines.megaplan.resident.auth import AuthorizationSubject, ConfirmationManager, ResidentAuthorizer
from arnold_pipelines.megaplan.resident.config import ResidentConfig
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
    assert isinstance(selected, AgentBoxOperatorProfile)
    assert ResidentConfig().profile == "megaplan"
    assert env_config.profile == "agentbox_operator"


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
    profile = AgentBoxOperatorProfile(agentbox_config_factory=lambda: agentbox_config)
    runner = FakeAgentRunner(
        [
            FakeAgentStep.call("status", {"operation": "shared"}),
            FakeAgentStep.call("resolve", {"kind": "operation", "query": "shared"}),
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
    resolve_result = response.tool_calls[1].result

    assert status_result["ok"] is False
    assert status_result["message"] == "Which operation did you mean: alpha-chain, beta-chain?"
    assert status_result["data"]["resolve"]["status"] == "ambiguous"
    assert [row["operation_id"] for row in status_result["data"]["resolve"]["candidates"]] == [
        "alpha-chain",
        "beta-chain",
    ]
    assert resolve_result["ok"] is False
    assert resolve_result["message"] == "Which operation did you mean: alpha-chain, beta-chain?"
    assert resolve_result["data"]["resolve"] == status_result["data"]["resolve"]
    assert resolve_result["data"]["action"] == "resolve"
    assert resolve_result["data"]["next_state"] == "needs_clarification"


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
