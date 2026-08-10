from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from arnold_pipelines.megaplan.resident.cloud import CloudToolRequest, CloudToolResult
from arnold_pipelines.megaplan.resident.config import ResidentConfig
from arnold_pipelines.megaplan.resident.runtime import OutboundMessage
from arnold_pipelines.megaplan.resident.scheduler import _todo_authoritative_inbound, make_store_scheduler
from arnold_pipelines.megaplan.store import (
    CloudRunInput,
    FileStore,
    ResidentConversationInput,
    ScheduledJobInput,
)


class FakeCloudBackend:
    async def run(self, request: CloudToolRequest) -> CloudToolResult:
        return CloudToolResult(
            classification="running",
            summary="chain is still running",
            details={"request": request.arguments},
        )


@dataclass
class CapturingOutbound:
    sent: list[OutboundMessage] = field(default_factory=list)

    async def send(self, message: OutboundMessage) -> None:
        self.sent.append(message)


def test_cloud_check_can_notify_every_fire(tmp_path) -> None:
    store = FileStore(tmp_path / "store")
    conversation = store.upsert_resident_conversation(
        ResidentConversationInput(
            transport="discord",
            conversation_key="discord:dm:user-1",
            dm_user_id="user-1",
        )
    )
    run = store.create_cloud_run(
        CloudRunInput(
            operation="chain",
            conversation_id=conversation.id,
            provider="megaplan-cloud-cli",
            target_id=".megaplan/initiatives/demo/chain.yaml",
            command_summary="cloud chain",
        )
    )
    run = store.update_cloud_run(run.id, status="running")
    now = datetime(2026, 6, 30, 12, 0, tzinfo=UTC)
    store.create_scheduled_job(
        ScheduledJobInput(
            job_type="cloud_check",
            conversation_id=conversation.id,
            cloud_run_id=run.id,
            payload={
                "project_root": ".",
                "cloud_yaml": "cloud.yaml",
                "check_interval_s": 21600,
                "notify_every_check": True,
            },
            scheduled_for=now - timedelta(seconds=1),
        )
    )
    outbound = CapturingOutbound()
    worker = make_store_scheduler(
        store=store,
        config=ResidentConfig(),
        cloud_backend=FakeCloudBackend(),
        outbound=outbound,
        worker_id="test-worker",
    )

    result = asyncio.run(worker.run_due_once(now=now))

    assert result.fired == 1
    assert len(outbound.sent) == 1
    sent = outbound.sent[0]
    assert sent.conversation_key == "discord:dm:user-1"
    assert "Cloud check every 6h ran" in sent.content
    assert "running" in sent.content
    messages = store.load_messages([store.load_resident_conversation(conversation.id).last_outbound_message_id])
    assert messages[0].content == sent.content


def test_authoritative_todo_inbound_exposes_reply_chain_custody(tmp_path) -> None:
    store = FileStore(tmp_path / "store")
    conversation = store.upsert_resident_conversation(
        ResidentConversationInput(
            transport="discord",
            conversation_key="discord:dm:user-1",
            dm_user_id="user-1",
        )
    )
    message = store.create_message(
        epic_id=None,
        conversation_id=conversation.id,
        direction="inbound",
        content="launch it",
        discord_message_id="discord-msg-1",
        discord_reply_provenance={
            "schema_version": "discord-reply-provenance-v1",
            "transport": "discord",
            "source_message_id": "discord-msg-1",
            "source_author_id": "user-1",
            "conversation_key": "discord:dm:user-1",
            "ancestors": [],
            "captured_ancestor_count": 0,
            "chain_complete": True,
            "capture_truncated": False,
            "termination_reason": "root",
        },
        idempotency_key="message-1",
    )

    inbound = _todo_authoritative_inbound(
        store,
        {
            "launch_provenance": {
                "applicability": "applicable",
                "resident_conversation_id": conversation.id,
                "source_record_id": message.id,
                "conversation_key": conversation.conversation_key,
                "reply_to_message_id": "discord-msg-1",
            }
        },
    )

    assert inbound["state"] == "verified"
    assert inbound["reply_chain_custody"]["source_message_id"] == "discord-msg-1"
    assert inbound["reply_chain_custody"]["termination_reason"] == "root"
