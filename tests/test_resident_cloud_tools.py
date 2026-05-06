from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from megaplan.resident import MegaplanResidentProfile, ResidentAuthorizer, ResidentConfig
from megaplan.resident.cloud import CloudToolRequest, CloudToolResult, classify_cloud_payload
from megaplan.store import FileStore, ResidentConversationInput


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
