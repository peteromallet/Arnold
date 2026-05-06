from __future__ import annotations

import asyncio
import argparse
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

from megaplan.resident import (
    AuthorizationSubject,
    ConfirmationManager,
    OutboundMessage,
    ResidentConfig,
    StoreBackedConfirmationManager,
)
from megaplan.resident.cloud import CloudToolRequest, CloudToolResult, classify_cloud_payload
from megaplan.resident.cli import run_resident_cli
from megaplan.resident.scheduler import (
    ResidentJobHandlers,
    ScheduledJobWorker,
    StoreScheduledJobBackend,
    make_store_scheduler,
)
from megaplan.store import CloudRunInput, FileStore, ResidentConversationInput, ScheduledJobInput


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


@dataclass
class MemoryOutbound:
    messages: list[OutboundMessage] = field(default_factory=list)

    async def send(self, message: OutboundMessage) -> None:
        self.messages.append(message)


def _resident_store(tmp_path: Path) -> tuple[FileStore, str, str, str]:
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
    run = store.create_cloud_run(
        CloudRunInput(
            operation="status",
            conversation_id=conversation.id,
            epic_id=epic.id,
            target_id="plan-a",
            command_summary="cloud status",
        )
    )
    run = store.update_cloud_run(run.id, status="running")
    return store, epic.id, conversation.id, run.id


def test_cloud_check_fresh_scheduler_notifies_once_across_restart(tmp_path: Path) -> None:
    store, epic_id, conversation_id, run_id = _resident_store(tmp_path)
    due = datetime.now(UTC) - timedelta(seconds=1)
    store.create_scheduled_job(
        ScheduledJobInput(
            job_type="cloud_check",
            conversation_id=conversation_id,
            cloud_run_id=run_id,
            epic_id=epic_id,
            payload={"project_root": str(tmp_path), "plan": "plan-a"},
            scheduled_for=due,
        )
    )
    first_outbound = MemoryOutbound()
    first_backend = FakeCloudBackend([{"status": "completed", "result": "success"}])
    first = make_store_scheduler(
        store=store,
        config=ResidentConfig(scheduler_poll_interval_s=1),
        cloud_backend=first_backend,
        outbound=first_outbound,
        worker_id="worker-one",
    )

    first_result = asyncio.run(first.run_due_once(now=datetime.now(UTC)))

    assert first_result.claimed == 1
    assert first_result.fired == 1
    assert len(first_backend.requests) == 1
    run = store.load_cloud_run(run_id)
    assert run is not None
    assert run.status == "completed"
    assert run.last_status["cloud_status"] == "completed"
    assert len(first_outbound.messages) == 1
    assert first_outbound.messages[0].metadata["cloud_run_id"] == run_id
    assert first_outbound.messages[0].metadata["cloud_status"] == "completed"

    store.create_scheduled_job(
        ScheduledJobInput(
            job_type="cloud_check",
            conversation_id=conversation_id,
            cloud_run_id=run_id,
            epic_id=epic_id,
            payload={"project_root": str(tmp_path), "plan": "plan-a"},
            scheduled_for=due,
        )
    )
    second_outbound = MemoryOutbound()
    second_backend = FakeCloudBackend([{"status": "completed", "result": "success"}])
    second = make_store_scheduler(
        store=store,
        config=ResidentConfig(scheduler_poll_interval_s=1),
        cloud_backend=second_backend,
        outbound=second_outbound,
        worker_id="worker-two",
    )

    second_result = asyncio.run(second.run_due_once(now=datetime.now(UTC)))

    assert second_result.claimed == 1
    assert second_result.fired == 1
    assert len(second_backend.requests) == 1
    assert second_outbound.messages == []
    outbound_rows = [
        row
        for row in store.search_messages(query="Cloud run", epic_id=epic_id, limit=20)
        if row.idempotency_key == first_outbound.messages[0].idempotency_key
    ]
    assert len(outbound_rows) == 1


def test_cloud_check_reschedules_running_work_without_duplicate_pending_jobs(tmp_path: Path) -> None:
    store, epic_id, conversation_id, run_id = _resident_store(tmp_path)
    due = datetime.now(UTC) - timedelta(seconds=1)
    store.create_scheduled_job(
        ScheduledJobInput(
            job_type="cloud_check",
            conversation_id=conversation_id,
            cloud_run_id=run_id,
            epic_id=epic_id,
            payload={"project_root": str(tmp_path), "check_interval_s": 5},
            scheduled_for=due,
        )
    )
    worker = make_store_scheduler(
        store=store,
        config=ResidentConfig(scheduler_poll_interval_s=1),
        cloud_backend=FakeCloudBackend([{"status": "running", "next_step": "execute"}]),
        worker_id="worker-running",
    )

    result = asyncio.run(worker.run_due_once(now=datetime.now(UTC)))

    assert result.fired == 1
    pending = store.list_scheduled_jobs(
        conversation_id=conversation_id,
        cloud_run_id=run_id,
        status="pending",
        job_type="cloud_check",
        limit=10,
    )
    assert len(pending) == 1
    assert pending[0].scheduled_for > datetime.now(UTC)
    assert store.load_cloud_run(run_id).status == "running"


def test_store_scheduler_retries_then_cancels_unhandled_jobs(tmp_path: Path) -> None:
    store = FileStore(tmp_path / "store")
    due = datetime.now(UTC) - timedelta(seconds=1)
    job = store.create_scheduled_job(
        ScheduledJobInput(
            job_type="heartbeat",
            scheduled_for=due,
            max_attempts=2,
        )
    )
    backend = StoreScheduledJobBackend(store, stale_after_seconds=60, batch_size=10, retry_delay_seconds=1)
    worker = ScheduledJobWorker(backend, handlers={}, worker_id="retry-worker")

    first = asyncio.run(worker.run_due_once(now=datetime.now(UTC)))
    retried = store.load_scheduled_job(job.id)
    assert first.retried == 1
    assert retried.status == "pending"

    store.update_scheduled_job(job.id, scheduled_for=due)
    second = asyncio.run(worker.run_due_once(now=datetime.now(UTC)))
    cancelled = store.load_scheduled_job(job.id)
    assert second.cancelled == 1
    assert cancelled.status == "cancelled"


def test_scheduler_support_handlers_for_housekeeping_jobs(tmp_path: Path) -> None:
    store = FileStore(tmp_path / "store")
    due = datetime.now(UTC) - timedelta(seconds=1)
    for job_type in ("heartbeat", "deferred_turn", "confirmation_expiry"):
        store.create_scheduled_job(ScheduledJobInput(job_type=job_type, scheduled_for=due))
    flushed = {"count": 0}

    async def flush() -> None:
        flushed["count"] += 1

    config = ResidentConfig(confirmation_expiry_s=1)
    manager = ConfirmationManager(config)
    request = manager.request_confirmation(
        subject=AuthorizationSubject(user_id="admin"),
        action="cloud_start",
        target_summary="test",
        now=datetime.now(UTC) - timedelta(seconds=10),
    )
    handlers = ResidentJobHandlers(
        store=store,
        config=config,
        cloud_backend=FakeCloudBackend([]),
        confirmation_manager=manager,
        runtime_flush=flush,
    )
    backend = StoreScheduledJobBackend(store, stale_after_seconds=60, batch_size=10)
    worker = ScheduledJobWorker(backend, handlers=handlers.handlers(), worker_id="housekeeping-worker")

    result = asyncio.run(worker.run_due_once(now=datetime.now(UTC)))

    assert result.fired == 3
    assert flushed["count"] == 1
    assert request.id not in {pending.id for pending in manager.pending()}
    assert store.list_scheduled_jobs(status="fired", limit=10)


def test_resident_cli_health_and_scheduler_once_use_durable_store(tmp_path: Path) -> None:
    store_root = tmp_path / "resident-store"
    store = FileStore(store_root)
    due = datetime.now(UTC) - timedelta(seconds=1)
    conversation = store.upsert_resident_conversation(
        ResidentConversationInput(
            conversation_key="discord:guild:g1:channel:c1",
            guild_id="g1",
            channel_id="c1",
        )
    )
    store.create_scheduled_job(
        ScheduledJobInput(
            job_type="heartbeat",
            conversation_id=conversation.id,
            scheduled_for=due,
        )
    )
    confirmation = StoreBackedConfirmationManager(ResidentConfig(), store).request_confirmation(
        subject=AuthorizationSubject(user_id="admin", guild_id="g1", channel_id="c1"),
        action="cloud_start",
        target_summary="chain",
    )

    health = run_resident_cli(
        tmp_path,
        argparse.Namespace(resident_action="health", store_root=str(store_root), mode="dev", limit=5),
    )
    assert health["success"] is True
    assert health["scheduled_backlog"]["pending"] == 2
    assert health["resident_conversations"][0]["conversation_key"] == "discord:guild:g1:channel:c1"
    assert health["stale_control_messages"]["count"] == 0
    assert health["pending_cloud_confirmations"][0]["id"] == confirmation.id

    once = run_resident_cli(
        tmp_path,
        argparse.Namespace(
            resident_action="scheduler-once",
            store_root=str(store_root),
            mode="dev",
            worker_id="test-resident-cli",
        ),
    )
    assert once["success"] is True
    assert once["result"]["claimed"] == 1
    assert once["result"]["fired"] == 1

    dry_run = run_resident_cli(
        tmp_path,
        argparse.Namespace(resident_action="discord", store_root=str(store_root), mode="dev", dry_run=True),
    )
    assert dry_run["success"] is True
    assert dry_run["dry_run"] is True
    assert dry_run["conversation_count"] == 1
