from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
import tarfile
from pathlib import Path
from types import SimpleNamespace

from megaplan.resident import (
    EmitProtocol,
    FakeAgentRunner,
    FakeAgentStep,
    MegaplanResidentProfile,
    OutboundMessage,
    ResidentAuthorizer,
    ResidentConfig,
    ResidentRuntime,
    ToolRegistration,
)
from megaplan.resident.discord import DiscordDeliveryTarget, DiscordInboundMessage
from megaplan.resident.tool_schemas import ToolInput, ToolResult
from megaplan.store import CloudRunInput, FileStore, ResidentConversationInput


@dataclass
class MemoryOutbound:
    messages: list[OutboundMessage] = field(default_factory=list)

    async def send(self, message: OutboundMessage) -> None:
        self.messages.append(message)


class EchoInput(ToolInput):
    text: str


def test_resident_runtime_persists_idempotent_discord_turn_and_outbound(tmp_path: Path) -> None:
    store = FileStore(tmp_path / "store")
    config = ResidentConfig(
        allowed_user_ids=("u1",),
        allowed_guild_ids=("g1",),
        allowed_channel_ids=("c1",),
        burst_idle_delay_s=60,
        burst_max_delay_s=120,
    )
    authorizer = ResidentAuthorizer(config)
    profile = MegaplanResidentProfile()
    profile.tools().register(
        ToolRegistration(
            name="echo",
            description="Echo",
            operation_kind="read",
            input_model=EchoInput,
            output_model=ToolResult,
            handler=lambda payload: ToolResult(ok=True, message="echoed", data={"text": payload.text}),
        )
    )
    outbound = MemoryOutbound()
    runtime = ResidentRuntime(
        config=config,
        authorizer=authorizer,
        store=store,
        profile=profile,
        runner=FakeAgentRunner([FakeAgentStep.call("echo", {"text": "hi"}), FakeAgentStep.final("done")]),
        outbound=outbound,
    )
    message = DiscordInboundMessage(
        message_id="m1",
        author_id="u1",
        target=DiscordDeliveryTarget(guild_id="g1", channel_id="c1"),
        content="hello",
    )

    async def run() -> None:
        await runtime.receive(message.to_inbound_event())
        await runtime.receive(message.to_inbound_event())
        await runtime.coalescer.flush_all()
        await runtime.receive(message.to_inbound_event())
        await runtime.coalescer.flush_all()

    asyncio.run(run())

    conversation = store.get_resident_conversation_by_key(
        transport="discord",
        conversation_key="discord:guild:g1:channel:c1",
    )
    assert conversation is not None
    messages = [row for row in store.search_messages(query="", limit=20) if row.conversation_id == conversation.id]
    inbound = [row for row in messages if row.direction == "inbound"]
    outbound_rows = [row for row in messages if row.direction == "outbound"]
    assert len(inbound) == 1
    assert inbound[0].idempotency_key == "discord:message:m1"
    assert inbound[0].bot_turn_id is not None
    assert len(outbound_rows) == 1
    assert outbound_rows[0].idempotency_key is not None
    assert conversation.last_inbound_message_id == inbound[0].id
    assert (store.load_resident_conversation(conversation.id) or conversation).last_outbound_message_id == outbound_rows[0].id
    assert len(outbound.messages) == 1
    turns = store.list_recent_turns()
    assert len(turns) == 1
    assert turns[0].status == "completed"
    tool_calls = store.search_tool_calls_by(turn_id=turns[0].id) if False else store.search_tool_calls_by(tool_name="echo")
    assert len(tool_calls) == 1
    assert tool_calls[0].result["ok"] is True


def test_resident_runtime_denies_unauthorized_inbound_before_persistence(tmp_path: Path) -> None:
    store = FileStore(tmp_path / "store")
    config = ResidentConfig(allowed_user_ids=("allowed",), burst_idle_delay_s=60, burst_max_delay_s=120)
    runtime = ResidentRuntime(
        config=config,
        authorizer=ResidentAuthorizer(config),
        store=store,
        profile=MegaplanResidentProfile(),
        runner=FakeAgentRunner([FakeAgentStep.final("should not run")]),
        outbound=MemoryOutbound(),
    )

    async def run() -> None:
        await runtime.receive(
            DiscordInboundMessage(
                message_id="m2",
                author_id="blocked",
                target=DiscordDeliveryTarget(guild_id="g1", channel_id="c1"),
                content="hello",
            ).to_inbound_event()
        )
        await runtime.coalescer.flush_all()

    asyncio.run(run())

    assert store.get_resident_conversation_by_key(transport="discord", conversation_key="discord:guild:g1:channel:c1") is None
    assert store.search_messages(query="", limit=20) == []
    assert store.list_recent_turns() == []


def test_resident_runtime_emit_sites_are_bound_to_emit_protocol(tmp_path: Path) -> None:
    store = FileStore(tmp_path / "store")
    runtime = ResidentRuntime(
        config=ResidentConfig(),
        authorizer=ResidentAuthorizer(ResidentConfig()),
        store=store,
        profile=MegaplanResidentProfile(),
        runner=FakeAgentRunner([FakeAgentStep.final("done")]),
        outbound=MemoryOutbound(),
    )

    emitter: EmitProtocol = runtime.emitter

    assert emitter is store
    assert callable(getattr(emitter, "log_system_event"))
    assert callable(getattr(emitter, "append_progress_event"))


def test_discord_adapter_normalizes_guild_thread_and_dm_targets() -> None:
    guild_message = SimpleNamespace(
        id=101,
        content="guild",
        guild=SimpleNamespace(id=1),
        author=SimpleNamespace(id=2),
        channel=SimpleNamespace(id=3, parent=None),
    )
    guild = DiscordInboundMessage.from_discord_message(guild_message)
    assert guild.target.conversation_key == "discord:guild:1:channel:3"
    assert guild.to_inbound_event().subject.channel_id == "3"

    thread_message = SimpleNamespace(
        id=102,
        content="thread",
        guild=SimpleNamespace(id=1),
        author=SimpleNamespace(id=2),
        channel=SimpleNamespace(id=4, parent=SimpleNamespace(id=3)),
    )
    thread = DiscordInboundMessage.from_discord_message(thread_message)
    assert thread.target.conversation_key == "discord:guild:1:channel:3:thread:4"
    assert DiscordDeliveryTarget.from_conversation_key(thread.target.conversation_key) == thread.target

    dm_message = SimpleNamespace(
        id=103,
        content="dm",
        guild=None,
        author=SimpleNamespace(id=2),
        channel=SimpleNamespace(id=9, parent=None),
    )
    dm = DiscordInboundMessage.from_discord_message(dm_message)
    assert dm.target.conversation_key == "discord:dm:2"
    assert dm.to_inbound_event().raw["dm_user_id"] == "2"


def test_megaplan_profile_editorial_and_control_tools_validate_and_deny(tmp_path: Path) -> None:
    store = FileStore(tmp_path / "store")
    config = ResidentConfig(
        allowed_user_ids=("user", "admin"),
        admin_user_ids=("admin",),
    )
    authorizer = ResidentAuthorizer(config)
    epic = store.create_epic(
        title="Epic",
        goal="Goal",
        body="# Goal\n\nA sufficiently clear starting body.\n\n# Deliverable\n\nShip it.\n",
    )
    conversation = store.upsert_resident_conversation(
        conversation=ResidentConversationInput(
            conversation_key="discord:guild:g1:channel:c1",
            active_epic_id=epic.id,
            guild_id="g1",
            channel_id="c1",
        )
    )
    profile = MegaplanResidentProfile(store=store, authorizer=authorizer)
    names = {tool.name for tool in profile.tools().list()}
    assert {"read_epic", "edit_epic_body", "run_sprint_on_cloud", "approve_gate", "reject_gate"}.issubset(names)
    assert {
        "search_messages",
        "search_epics",
        "search_plans",
        "search_code_artifacts",
        "list_codebases",
        "register_codebase",
        "add_repo",
        "reconcile_epic",
        "reconcile_plan_storage",
        "list_repos",
        "read_plan_artifact",
        "write_plan_artifact",
        "export_epic_bundle",
        "archive_cloud_logs",
        "cloud_start_chain",
        "cloud_bootstrap",
    }.issubset(names)
    assert not {"shell", "remote_shell", "exec", "remote_exec", "clone", "remote_command", "filesystem_write"} & names

    catalog = {tool.name: tool for tool in profile.tools().list()}
    assert catalog["register_codebase"].operation_kind == "repo_write"
    assert catalog["write_plan_artifact"].operation_kind == "artifact_write"
    assert catalog["export_epic_bundle"].operation_kind == "export"
    assert catalog["archive_cloud_logs"].operation_kind == "archive_logs"
    assert catalog["reconcile_epic"].operation_kind == "reconcile_apply"

    select = profile.tools().get("select_epic").handler(
        profile.tools().get("select_epic").input_model(
            actor_user_id="user",
            conversation_id=conversation.id,
            epic_id=epic.id,
        )
    )
    assert select.ok is True
    loaded_context = asyncio.run(profile.load_hot_context(conversation.id))
    assert loaded_context["active_epic"]["id"] == epic.id

    edited = profile.tools().get("edit_epic_body").handler(
        profile.tools().get("edit_epic_body").input_model(
            actor_user_id="user",
            epic_id=epic.id,
            expected_revision=epic.revision,
            body="# Goal\n\nUpdated body with decisions.\n\n# Deliverable\n\nUpdated delivery.\n",
        )
    )
    assert edited.ok is True
    stale = profile.tools().get("edit_epic_body").handler(
        profile.tools().get("edit_epic_body").input_model(
            actor_user_id="user",
            epic_id=epic.id,
            expected_revision=epic.revision,
            body="# Goal\n\nStale write.\n\n# Deliverable\n\nNope.\n",
        )
    )
    assert stale.ok is False

    sprint_result = profile.tools().get("create_or_update_sprints").handler(
        profile.tools().get("create_or_update_sprints").input_model(
            actor_user_id="user",
            epic_id=epic.id,
            sprints=[
                {
                    "sprint_number": 1,
                    "name": "First",
                    "goal": "Run the first sprint",
                    "items": [{"content": "Do the work"}],
                }
            ],
        )
    )
    assert sprint_result.ok is True
    sprint_id = sprint_result.data["sprints"][0]["id"]

    denied = profile.tools().get("run_sprint_on_cloud").handler(
        profile.tools().get("run_sprint_on_cloud").input_model(
            actor_user_id="user",
            epic_id=epic.id,
            target_id=sprint_id,
            project_root=str(tmp_path),
        )
    )
    assert denied.ok is False
    assert denied.data["authorization_denied"] is True
    assert authorizer.denials[-1].reason == "admin_required"
    assert store.claim_pending_control_messages(processor_id="test") == []

    needs_confirmation = profile.tools().get("run_sprint_on_cloud").handler(
        profile.tools().get("run_sprint_on_cloud").input_model(
            actor_user_id="admin",
            conversation_id=conversation.id,
            epic_id=epic.id,
            target_id=sprint_id,
            project_root=str(tmp_path),
        )
    )
    assert needs_confirmation.ok is False
    assert needs_confirmation.data["confirmation_required"] is True
    assert store.claim_pending_control_messages(processor_id="test") == []

    queued = profile.tools().get("run_sprint_on_cloud").handler(
        profile.tools().get("run_sprint_on_cloud").input_model(
            actor_user_id="admin",
            conversation_id=conversation.id,
            epic_id=epic.id,
            target_id=sprint_id,
            project_root=str(tmp_path),
            confirmation_request_id=needs_confirmation.data["request_id"],
            confirmation_phrase=needs_confirmation.data["exact_phrase"],
        )
    )
    assert queued.ok is True
    claimed = store.claim_pending_control_messages(processor_id="test")
    assert len(claimed) == 1
    assert claimed[0].intent == "run_sprint"
    assert claimed[0].payload["resident_cloud"] is True
    assert claimed[0].payload["cloud_run_id"]
    cloud_run = store.load_cloud_run(claimed[0].payload["cloud_run_id"])
    assert cloud_run is not None
    assert cloud_run.operation == "sprint"
    assert cloud_run.status == "queued"
    assert cloud_run.conversation_id == conversation.id

    invalid_needs_confirmation = profile.tools().get("run_sprint_on_cloud").handler(
        profile.tools().get("run_sprint_on_cloud").input_model(
            actor_user_id="admin",
            conversation_id=conversation.id,
            epic_id=epic.id,
            target_id="missing-sprint",
            project_root=str(tmp_path),
        )
    )
    invalid = profile.tools().get("run_sprint_on_cloud").handler(
        profile.tools().get("run_sprint_on_cloud").input_model(
            actor_user_id="admin",
            conversation_id=conversation.id,
            epic_id=epic.id,
            target_id="missing-sprint",
            project_root=str(tmp_path),
            confirmation_request_id=invalid_needs_confirmation.data["request_id"],
            confirmation_phrase=invalid_needs_confirmation.data["exact_phrase"],
        )
    )
    assert invalid.ok is False
    assert store.list_cloud_runs(conversation_id=conversation.id, limit=10) == [cloud_run]


def test_megaplan_profile_cloud_check_tools_are_durable_and_authorized(tmp_path: Path) -> None:
    store = FileStore(tmp_path / "store")
    config = ResidentConfig(
        allowed_user_ids=("user", "admin"),
        admin_user_ids=("admin",),
        cloud_yaml_path=tmp_path / "cloud.yaml",
    )
    authorizer = ResidentAuthorizer(config)
    epic = store.create_epic(
        title="Cloud Epic",
        goal="Watch cloud work",
        body="# Goal\n\nWatch cloud work.\n\n# Deliverable\n\nA durable check.\n",
    )
    conversation = store.upsert_resident_conversation(
        conversation=ResidentConversationInput(
            conversation_key="discord:guild:g1:channel:c1",
            active_epic_id=epic.id,
            guild_id="g1",
            channel_id="c1",
        )
    )
    run = store.create_cloud_run(
        CloudRunInput(
            operation="chain",
            conversation_id=conversation.id,
            epic_id=epic.id,
            provider="fake-cloud",
            target_id="chain.yaml",
            command_summary="cloud chain chain.yaml",
            started_by_actor_id="admin",
        )
    )
    profile = MegaplanResidentProfile(store=store, authorizer=authorizer, config=config)
    names = {tool.name for tool in profile.tools().list()}
    assert {"schedule_cloud_check", "cancel_cloud_check", "list_cloud_checks"}.issubset(names)

    schedule_tool = profile.tools().get("schedule_cloud_check")
    denied = schedule_tool.handler(
        schedule_tool.input_model(
            actor_user_id="user",
            conversation_id=conversation.id,
            cloud_run_id=run.id,
            project_root=str(tmp_path),
        )
    )
    assert denied.ok is False
    assert denied.data["authorization_denied"] is True
    assert store.list_scheduled_jobs(job_type="cloud_check") == []

    scheduled_for = datetime(2026, 5, 6, 12, 0, tzinfo=UTC)
    scheduled = schedule_tool.handler(
        schedule_tool.input_model(
            actor_user_id="admin",
            conversation_id=conversation.id,
            cloud_run_id=run.id,
            project_root=str(tmp_path),
            scheduled_for=scheduled_for,
            interval_seconds=45,
            payload={"remote_spec": "chain.yaml"},
        )
    )
    assert scheduled.ok is True
    job_id = scheduled.data["scheduled_job"]["id"]
    job = store.load_scheduled_job(job_id)
    assert job is not None
    assert job.job_type == "cloud_check"
    assert job.conversation_id == conversation.id
    assert job.cloud_run_id == run.id
    assert job.epic_id == epic.id
    assert job.scheduled_for == scheduled_for
    assert job.payload["check_interval_s"] == 45
    assert job.payload["cloud_yaml"] == str(config.cloud_yaml_path)
    assert job.payload["remote_spec"] == "chain.yaml"

    list_tool = profile.tools().get("list_cloud_checks")
    listed = list_tool.handler(
        list_tool.input_model(
            actor_user_id="user",
            conversation_id=conversation.id,
            status="pending",
        )
    )
    assert listed.ok is True
    assert [row["id"] for row in listed.data["scheduled_jobs"]] == [job_id]

    cancel_tool = profile.tools().get("cancel_cloud_check")
    cancel_denied = cancel_tool.handler(cancel_tool.input_model(actor_user_id="user", scheduled_job_id=job_id))
    assert cancel_denied.ok is False
    assert store.load_scheduled_job(job_id).status == "pending"

    cancelled = cancel_tool.handler(cancel_tool.input_model(actor_user_id="admin", scheduled_job_id=job_id))
    assert cancelled.ok is True
    assert cancelled.data["scheduled_job"]["status"] == "cancelled"
    assert store.load_scheduled_job(job_id).cancelled_at is not None

    cancelled_list = list_tool.handler(
        list_tool.input_model(
            actor_user_id="user",
            cloud_run_id=run.id,
            status="cancelled",
        )
    )
    assert [row["id"] for row in cancelled_list.data["scheduled_jobs"]] == [job_id]


def test_megaplan_profile_store_search_and_code_artifact_results_are_bounded(tmp_path: Path) -> None:
    store = FileStore(tmp_path / "store")
    config = ResidentConfig(allowed_user_ids=("user",), admin_user_ids=("admin",))
    profile = MegaplanResidentProfile(store=store, authorizer=ResidentAuthorizer(config), config=config)
    epic = store.create_epic(title="Search Epic", goal="Find resident data", body="Body mentions needle")
    conversation = store.upsert_resident_conversation(
        conversation=ResidentConversationInput(conversation_key="discord:guild:g:channel:c", active_epic_id=epic.id)
    )
    store.create_message(epic_id=epic.id, conversation_id=conversation.id, direction="inbound", content="needle in a message")
    plan = store.create_plan(sprint_id=None, epic_id=epic.id, name="needle-plan", idea="plan idea needle")
    codebase = store.create_codebase(
        owner="openai",
        name="megaplan",
        default_branch="main",
        repo_url="https://github.com/openai/megaplan.git",
    )
    artifact = store.create_code_artifact(
        kind="excerpt",
        source="codebase",
        content="needle secret full content should not be returned " * 20,
        codebase_id=codebase.id,
        epic_id=epic.id,
        file_path="src/app.py",
        content_summary="summary needle",
        metadata={"language": "python", "unsafe_nested": {"secret": "nope"}},
    )

    messages = profile.tools().get("search_messages").handler(
        profile.tools().get("search_messages").input_model(actor_user_id="user", query="needle", conversation_id=conversation.id)
    )
    epics = profile.tools().get("search_epics").handler(
        profile.tools().get("search_epics").input_model(actor_user_id="user", query="needle")
    )
    plans = profile.tools().get("search_plans").handler(
        profile.tools().get("search_plans").input_model(actor_user_id="user", query="needle", epic_id=epic.id)
    )
    codebases = profile.tools().get("list_codebases").handler(
        profile.tools().get("list_codebases").input_model(actor_user_id="user")
    )
    repos = profile.tools().get("list_repos").handler(profile.tools().get("list_repos").input_model(actor_user_id="user"))
    artifacts = profile.tools().get("search_code_artifacts").handler(
        profile.tools().get("search_code_artifacts").input_model(actor_user_id="user", query="needle", epic_id=epic.id)
    )

    assert messages.ok is True and messages.data["messages"][0]["conversation_id"] == conversation.id
    assert epics.ok is True and epics.data["epics"][0]["id"] == epic.id
    assert plans.ok is True and plans.data["plans"][0]["id"] == plan.id
    assert codebases.ok is True and codebases.data["codebases"][0]["repo_url"] == "https://github.com/openai/megaplan.git"
    assert repos.ok is True and repos.data["repos"][0]["repo_url"] == "https://github.com/openai/megaplan.git"
    assert artifacts.ok is True
    result = artifacts.data["artifacts"][0]
    assert result["id"] == artifact.id
    assert "content" not in result
    assert len(result["snippet"]) <= 323
    assert result["metadata"] == {"language": "python"}
    assert "unsafe_nested" in result["metadata_keys"]


def test_megaplan_profile_register_repo_requires_confirmation_and_validates_url(tmp_path: Path) -> None:
    store = FileStore(tmp_path / "store")
    config = ResidentConfig(allowed_user_ids=("user", "admin"), admin_user_ids=("admin",))
    profile = MegaplanResidentProfile(store=store, authorizer=ResidentAuthorizer(config), config=config)
    tool = profile.tools().get("register_codebase")

    denied = tool.handler(
        tool.input_model(actor_user_id="user", owner="openai", name="megaplan", repo_url="https://github.com/openai/megaplan.git")
    )
    assert denied.ok is False
    assert denied.data["authorization_denied"] is True

    invalid = tool.handler(
        tool.input_model(actor_user_id="admin", owner="openai", name="megaplan", repo_url="file:///tmp/repo")
    )
    assert invalid.ok is False
    assert invalid.data["validation_error"] is True

    needs_confirmation = tool.handler(
        tool.input_model(
            actor_user_id="admin",
            owner="openai",
            name="megaplan",
            repo_url="git@github.com:openai/megaplan.git",
            repo_workspace="/workspace/megaplan",
            default_branch="main",
        )
    )
    assert needs_confirmation.ok is False
    assert needs_confirmation.data["confirmation_required"] is True
    assert store.find_codebase("openai", "megaplan") is None

    registered = tool.handler(
        tool.input_model(
            actor_user_id="admin",
            owner="openai",
            name="megaplan",
            repo_url="git@github.com:openai/megaplan.git",
            repo_workspace="/workspace/megaplan",
            default_branch="main",
            confirmation_request_id=needs_confirmation.data["request_id"],
            confirmation_phrase=needs_confirmation.data["exact_phrase"],
        )
    )
    assert registered.ok is True
    persisted = store.find_codebase("openai", "megaplan")
    assert persisted.repo_url == "git@github.com:openai/megaplan.git"
    assert persisted.repo_workspace == "/workspace/megaplan"


def test_megaplan_profile_plan_artifacts_export_and_reconcile_are_guarded(tmp_path: Path) -> None:
    store = FileStore(tmp_path / "store")
    config = ResidentConfig(
        allowed_user_ids=("user", "admin"),
        admin_user_ids=("admin",),
        resident_export_root=tmp_path / "exports",
    )
    profile = MegaplanResidentProfile(store=store, authorizer=ResidentAuthorizer(config), config=config)
    epic = store.create_epic(title="Artifact Epic", goal="Artifacts", body="body")
    plan = store.create_plan(sprint_id=None, epic_id=epic.id, name="artifact-plan", idea="artifact idea")

    write_tool = profile.tools().get("write_plan_artifact")
    read_tool = profile.tools().get("read_plan_artifact")
    export_tool = profile.tools().get("export_epic_bundle")
    reconcile_tool = profile.tools().get("reconcile_epic")
    storage_tool = profile.tools().get("reconcile_plan_storage")

    needs_write_confirmation = write_tool.handler(
        write_tool.input_model(actor_user_id="admin", plan_id=plan.id, name="notes/state.txt", content_text="hello")
    )
    assert needs_write_confirmation.ok is False
    assert store.read_plan_artifact(plan.id, "notes/state.txt") is None

    written = write_tool.handler(
        write_tool.input_model(
            actor_user_id="admin",
            plan_id=plan.id,
            name="notes/state.txt",
            content_text="hello",
            confirmation_request_id=needs_write_confirmation.data["request_id"],
            confirmation_phrase=needs_write_confirmation.data["exact_phrase"],
        )
    )
    assert written.ok is True

    read = read_tool.handler(read_tool.input_model(actor_user_id="user", plan_id=plan.id, name="notes/state.txt"))
    assert read.ok is True
    assert read.data["artifact"]["content_text"] == "hello"

    binary_ref = store.write_plan_artifact(plan.id, "binary.bin", b"\x00\xff")
    binary = read_tool.handler(read_tool.input_model(actor_user_id="user", plan_id=plan.id, name=binary_ref.name))
    assert binary.ok is True
    assert binary.data["artifact"]["binary"] is True
    assert "content_text" not in binary.data["artifact"]

    dry_run = reconcile_tool.handler(reconcile_tool.input_model(actor_user_id="user", epic_id=epic.id))
    assert dry_run.ok is True
    assert dry_run.data["summary"]["plan_count"] == 1
    storage_dry_run = storage_tool.handler(storage_tool.input_model(actor_user_id="user", plan_id=plan.id))
    assert storage_dry_run.ok is True
    assert storage_dry_run.data["summary"]["plans"][0]["artifacts"]

    needs_export_confirmation = export_tool.handler(export_tool.input_model(actor_user_id="admin", epic_id=epic.id))
    assert needs_export_confirmation.ok is False
    assert not list((tmp_path / "exports").glob("*.tar"))
    exported = export_tool.handler(
        export_tool.input_model(
            actor_user_id="admin",
            epic_id=epic.id,
            confirmation_request_id=needs_export_confirmation.data["request_id"],
            confirmation_phrase=needs_export_confirmation.data["exact_phrase"],
        )
    )
    assert exported.ok is True
    export_path = Path(exported.data["export"]["path"])
    assert export_path.parent == (tmp_path / "exports").resolve()
    with tarfile.open(export_path) as tar:
        assert "manifest.json" in tar.getnames()

    needs_apply_confirmation = storage_tool.handler(storage_tool.input_model(actor_user_id="admin", plan_id=plan.id, apply=True))
    assert needs_apply_confirmation.ok is False
    applied = storage_tool.handler(
        storage_tool.input_model(
            actor_user_id="admin",
            plan_id=plan.id,
            apply=True,
            confirmation_request_id=needs_apply_confirmation.data["request_id"],
            confirmation_phrase=needs_apply_confirmation.data["exact_phrase"],
        )
    )
    assert applied.ok is True
    assert applied.data["applied"] is True
