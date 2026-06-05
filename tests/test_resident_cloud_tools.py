from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import json
from pathlib import Path

import pytest

from arnold.pipelines.megaplan.resident import MegaplanResidentProfile, ResidentAuthorizer, ResidentConfig
from arnold.pipelines.megaplan.resident.cloud import CloudToolRequest, CloudToolResult, _argv_for_request, classify_cloud_payload
from arnold.pipelines.megaplan.store import CloudRunInput, FileStore, ResidentConversationInput


@dataclass
class FakeCloudBackend:
    payloads: list[object]
    requests: list[CloudToolRequest] = field(default_factory=list)

    async def run(self, request: CloudToolRequest) -> CloudToolResult:
        self.requests.append(request)
        payload = self.payloads.pop(0)
        classification = classify_cloud_payload(payload)
        return CloudToolResult(
            classification=classification,
            summary=f"{request.operation}: {classification}",
            details={"payload": payload},
        )


@pytest.mark.parametrize(
    ("payload", "classification"),
    [
        ({"status": "running", "next_step": "execute"}, "running"),
        ({"status": "blocked", "reason": "execution_blocked"}, "blocked"),
        ({"status": "failed", "error": "provider error"}, "failed"),
        ({"current_state": "state_gated", "summary": "gate pending"}, "gate-needed"),
        ({"current_state": "state_done", "result": "success"}, "completed"),
        ({"status": "unrecognized"}, "unknown"),
    ],
)
def test_cloud_payload_classifies_supported_resident_states(payload: object, classification: str) -> None:
    assert classify_cloud_payload(payload) == classification


def test_cloud_cli_backend_request_argv_includes_repo_overrides() -> None:
    argv = _argv_for_request(
        CloudToolRequest(
            operation="cloud_start_chain",
            arguments={
                "spec": "chain.yaml",
                "repo_url": "https://github.com/openai/megaplan.git",
                "repo_branch": "feature/resident",
                "repo_workspace": "/workspace/megaplan",
            },
            confirmed=True,
        )
    )

    assert argv == [
        "chain",
        "chain.yaml",
        "--repo-url",
        "https://github.com/openai/megaplan.git",
        "--repo-branch",
        "feature/resident",
        "--repo-workspace",
        "/workspace/megaplan",
    ]


def test_resident_cloud_status_persists_classification_and_progress(tmp_path: Path) -> None:
    store = FileStore(tmp_path / "store")
    epic = store.create_epic(title="Epic", goal="Goal", body="# Goal\n\nRun cloud work.\n")
    conversation = store.upsert_resident_conversation(
        conversation=ResidentConversationInput(
            conversation_key="discord:guild:g1:channel:c1",
            active_epic_id=epic.id,
            guild_id="g1",
            channel_id="c1",
        )
    )
    config = ResidentConfig(allowed_user_ids=("user",), admin_user_ids=("admin",))
    backend = FakeCloudBackend([{"status": "running", "next_step": "execute"}])
    profile = MegaplanResidentProfile(
        store=store,
        authorizer=ResidentAuthorizer(config),
        config=config,
        cloud_backend=backend,
    )

    result = asyncio.run(
        profile.tools().get("cloud_status").handler(
            profile.tools().get("cloud_status").input_model(
                actor_user_id="user",
                conversation_id=conversation.id,
                epic_id=epic.id,
                plan="plan-a",
                project_root=str(tmp_path),
            )
        )
    )

    assert result.ok is True
    assert result.data["classification"] == "running"
    assert len(backend.requests) == 1
    assert backend.requests[0].operation == "cloud_status"
    assert "exec" not in {tool.name for tool in profile.tools().list()}
    run = store.load_cloud_run(result.data["cloud_run"]["id"])
    assert run is not None
    assert run.status == "running"
    assert run.last_status["cloud_status"] == "running"
    progress = store.list_progress_events(epic_id=epic.id)
    assert len(progress) == 1
    assert progress[0].details["cloud_status"] == "running"


def test_resident_cloud_start_requires_exact_confirmation_before_side_effects(tmp_path: Path) -> None:
    store = FileStore(tmp_path / "store")
    epic = store.create_epic(title="Epic", goal="Goal", body="# Goal\n\nRun cloud work.\n")
    conversation = store.upsert_resident_conversation(
        conversation=ResidentConversationInput(
            conversation_key="discord:guild:g1:channel:c1",
            active_epic_id=epic.id,
            guild_id="g1",
            channel_id="c1",
        )
    )
    config = ResidentConfig(allowed_user_ids=("user", "admin"), admin_user_ids=("admin",))
    authorizer = ResidentAuthorizer(config)
    backend = FakeCloudBackend([{"status": "completed", "result": "success"}])
    profile = MegaplanResidentProfile(store=store, authorizer=authorizer, config=config, cloud_backend=backend)

    denied = asyncio.run(
        profile.tools().get("cloud_start_chain").handler(
            profile.tools().get("cloud_start_chain").input_model(
                actor_user_id="user",
                conversation_id=conversation.id,
                epic_id=epic.id,
                spec=str(tmp_path / "chain.yaml"),
                project_root=str(tmp_path),
            )
        )
    )
    assert denied.ok is False
    assert denied.data["authorization_denied"] is True
    assert backend.requests == []

    needs_confirmation = asyncio.run(
        profile.tools().get("cloud_start_chain").handler(
            profile.tools().get("cloud_start_chain").input_model(
                actor_user_id="admin",
                conversation_id=conversation.id,
                epic_id=epic.id,
                spec=str(tmp_path / "chain.yaml"),
                project_root=str(tmp_path),
            )
        )
    )
    assert needs_confirmation.ok is False
    assert needs_confirmation.data["confirmation_required"] is True
    assert backend.requests == []
    assert store.list_cloud_runs(conversation_id=conversation.id) == []

    started = asyncio.run(
        profile.tools().get("cloud_start_chain").handler(
            profile.tools().get("cloud_start_chain").input_model(
                actor_user_id="admin",
                conversation_id=conversation.id,
                epic_id=epic.id,
                spec=str(tmp_path / "chain.yaml"),
                project_root=str(tmp_path),
                confirmation_request_id=needs_confirmation.data["request_id"],
                confirmation_phrase=needs_confirmation.data["exact_phrase"],
            )
        )
    )

    assert started.ok is True
    assert started.data["classification"] == "completed"
    assert len(backend.requests) == 1
    assert backend.requests[0].operation == "cloud_start_chain"
    assert backend.requests[0].confirmed is True
    run = store.load_cloud_run(started.data["cloud_run"]["id"])
    assert run is not None
    assert run.operation == "chain"
    assert run.status == "completed"
    assert run.last_status["cloud_status"] == "completed"


def test_resident_archive_cloud_logs_requires_plan_target_and_confirmation(tmp_path: Path) -> None:
    store = FileStore(tmp_path / "store")
    epic = store.create_epic(title="Epic", goal="Goal", body="# Goal\n")
    plan = store.create_plan(sprint_id=None, epic_id=epic.id, name="cloud-plan", idea="run cloud")
    cloud_run = store.create_cloud_run(
        CloudRunInput(
            operation="chain",
            epic_id=epic.id,
            plan_id=plan.id,
            provider="test",
            target_id="chain.yaml",
            command_summary="cloud chain chain.yaml",
        )
    )
    config = ResidentConfig(allowed_user_ids=("admin",), admin_user_ids=("admin",))
    backend = FakeCloudBackend([{"logs": ["line 1", "line 2"], "status": "completed"}])
    profile = MegaplanResidentProfile(store=store, authorizer=ResidentAuthorizer(config), config=config, cloud_backend=backend)
    tool = profile.tools().get("archive_cloud_logs")

    needs_confirmation = asyncio.run(
        tool.handler(tool.input_model(actor_user_id="admin", cloud_run_id=cloud_run.id, project_root=str(tmp_path)))
    )
    assert needs_confirmation.ok is False
    assert needs_confirmation.data["confirmation_required"] is True
    assert backend.requests == []
    assert store.read_plan_artifact(plan.id, f"cloud-logs/{cloud_run.id}.json") is None

    archived = asyncio.run(
        tool.handler(
            tool.input_model(
                actor_user_id="admin",
                cloud_run_id=cloud_run.id,
                project_root=str(tmp_path),
                confirmation_request_id=needs_confirmation.data["request_id"],
                confirmation_phrase=needs_confirmation.data["exact_phrase"],
            )
        )
    )
    assert archived.ok is True
    assert archived.data["size_bytes"] > 0
    assert len(archived.data["sha256"]) == 64
    assert len(backend.requests) == 1
    assert backend.requests[0].operation == "cloud_logs"
    assert backend.requests[0].arguments["no_follow"] == "true"
    body = json.loads(store.read_plan_artifact(plan.id, f"cloud-logs/{cloud_run.id}.json"))
    assert body["cloud_run_id"] == cloud_run.id
    assert body["details"]["payload"]["logs"] == ["line 1", "line 2"]

    run_without_plan = store.create_cloud_run(
        CloudRunInput(operation="status", provider="test", target_id="orphan", command_summary="cloud status")
    )
    no_plan_confirmation = asyncio.run(
        tool.handler(tool.input_model(actor_user_id="admin", cloud_run_id=run_without_plan.id))
    )
    no_plan = asyncio.run(
        tool.handler(
            tool.input_model(
                actor_user_id="admin",
                cloud_run_id=run_without_plan.id,
                confirmation_request_id=no_plan_confirmation.data["request_id"],
                confirmation_phrase=no_plan_confirmation.data["exact_phrase"],
            )
        )
    )
    assert no_plan.ok is False
    assert no_plan.data["cloud_run_id"] == run_without_plan.id
    assert len(backend.requests) == 1


def test_resident_cloud_start_forwards_registered_repo_arguments(tmp_path: Path) -> None:
    store = FileStore(tmp_path / "store")
    epic = store.create_epic(title="Epic", goal="Goal", body="# Goal\n")
    codebase = store.create_codebase(
        owner="openai",
        name="megaplan",
        repo_url="https://github.com/openai/megaplan.git",
        repo_workspace="/workspace/megaplan",
        default_branch="feature/resident",
    )
    config = ResidentConfig(allowed_user_ids=("admin",), admin_user_ids=("admin",))
    backend = FakeCloudBackend([{"status": "completed", "result": "success"}])
    profile = MegaplanResidentProfile(store=store, authorizer=ResidentAuthorizer(config), config=config, cloud_backend=backend)
    tool = profile.tools().get("cloud_start_chain")

    needs_confirmation = asyncio.run(
        tool.handler(
            tool.input_model(
                actor_user_id="admin",
                epic_id=epic.id,
                spec=str(tmp_path / "chain.yaml"),
                project_root=str(tmp_path),
                codebase_id=codebase.id,
            )
        )
    )
    assert needs_confirmation.ok is False
    assert "https://github.com/openai/megaplan.git" in needs_confirmation.data["target_summary"]
    assert "feature/resident" in needs_confirmation.data["target_summary"]
    assert "/workspace/megaplan" in needs_confirmation.data["target_summary"]
    assert "https://github.com/openai/megaplan.git" in needs_confirmation.data["exact_phrase"]
    assert store.list_cloud_runs() == []
    started = asyncio.run(
        tool.handler(
            tool.input_model(
                actor_user_id="admin",
                epic_id=epic.id,
                spec=str(tmp_path / "chain.yaml"),
                project_root=str(tmp_path),
                codebase_id=codebase.id,
                confirmation_request_id=needs_confirmation.data["request_id"],
                confirmation_phrase=needs_confirmation.data["exact_phrase"],
            )
        )
    )

    assert started.ok is True
    assert backend.requests[0].arguments["repo_url"] == "https://github.com/openai/megaplan.git"
    assert backend.requests[0].arguments["repo_branch"] == "feature/resident"
    assert backend.requests[0].arguments["repo_workspace"] == "/workspace/megaplan"
