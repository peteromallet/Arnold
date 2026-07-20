from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
import json

from arnold_pipelines.megaplan.resident import vp_todo
from arnold_pipelines.megaplan.resident.config import ResidentConfig
from arnold_pipelines.megaplan.resident.scheduler import make_store_scheduler
from arnold_pipelines.megaplan.store import (
    FileStore,
    ResidentConversationInput,
    ScheduledJobInput,
)

NOW = datetime(2026, 7, 1, 12, 0, tzinfo=UTC)


@dataclass
class FakeRuntime:
    received: list = field(default_factory=list)

    async def receive(self, event) -> None:
        self.received.append(event)


def _payload(**overrides) -> dict:
    base = {
        "conversation_key": "discord:guild:g:channel:c",
        "subject_user_id": "admin-1",
        "guild_id": "g",
        "channel_id": "c",
        "interval_s": 21600,
    }
    base.update(overrides)
    return base


def _worker(store, config, runtime):
    return make_store_scheduler(
        store=store,
        config=config,
        cloud_backend=None,
        runtime=runtime,
        worker_id="test-worker",
    )


def _seed(store, payload, *, scheduled_for=None) -> None:
    store.create_scheduled_job(
        ScheduledJobInput(
            job_type="vp_todo_sweep",
            payload=payload,
            scheduled_for=scheduled_for or (NOW - timedelta(seconds=1)),
        )
    )


def _authoritative_origin(store: FileStore) -> dict:
    conversation = store.upsert_resident_conversation(
        ResidentConversationInput(
            conversation_key="discord:guild:g:channel:c",
            guild_id="g",
            channel_id="c",
        )
    )
    source = store.create_message(
        epic_id=None,
        conversation_id=conversation.id,
        direction="inbound",
        content="Launch the canonical corrective chain.",
        discord_message_id="1526528478990696579",
        idempotency_key="vp-audit-source",
    )
    return {
        "transport": "discord",
        "applicability": "applicable",
        "resident_conversation_id": conversation.id,
        "conversation_id": conversation.id,
        "source_record_id": source.id,
        "conversation_key": conversation.conversation_key,
        "discord_message_id": source.discord_message_id,
        "reply_to_message_id": source.discord_message_id,
        "guild_id": "g",
        "channel_id": "c",
        "source_kind": "discord_inbound_message",
    }


def test_sweep_skipped_when_disabled_but_reschedules(tmp_path) -> None:
    store = FileStore(tmp_path / "store")
    config = ResidentConfig(
        special_requests_enabled=False,
        special_requests_todo_path=tmp_path / "todo.json",
    )
    runtime = FakeRuntime()
    worker = _worker(store, config, runtime)
    _seed(store, _payload())

    result = asyncio.run(worker.run_due_once(now=NOW))

    assert result.fired == 1
    assert runtime.received == []
    assert len(store.list_scheduled_jobs(job_type="vp_todo_sweep", status="pending")) == 1


def test_sweep_noop_when_no_pending(tmp_path) -> None:
    store = FileStore(tmp_path / "store")
    config = ResidentConfig(
        special_requests_enabled=True,
        special_requests_todo_path=tmp_path / "todo.json",
    )
    runtime = FakeRuntime()
    worker = _worker(store, config, runtime)
    _seed(store, _payload())

    result = asyncio.run(worker.run_due_once(now=NOW))

    assert result.fired == 1
    assert runtime.received == []
    assert len(store.list_scheduled_jobs(job_type="vp_todo_sweep", status="pending")) == 1


def test_sweep_dispatches_when_pending(tmp_path) -> None:
    store = FileStore(tmp_path / "store")
    todo = tmp_path / "todo.json"
    vp_todo.add_item(todo, "summarize the top file")
    vp_todo.add_item(todo, "second item")
    config = ResidentConfig(
        special_requests_enabled=True,
        special_requests_todo_path=todo,
    )
    runtime = FakeRuntime()
    worker = _worker(store, config, runtime)
    _seed(store, _payload())

    result = asyncio.run(worker.run_due_once(now=NOW))

    assert result.fired == 1
    assert len(runtime.received) == 1
    event = runtime.received[0]
    assert event.conversation_key == "discord:guild:g:channel:c"
    assert event.subject.user_id == "admin-1"
    assert event.subject.guild_id == "g"
    assert event.subject.channel_id == "c"
    assert event.idempotency_key
    assert "launch_subagent" in event.content
    assert "reconcile_todo_item" in event.content
    assert "backend=codex" in event.content
    assert "background=true" in event.content
    assert "request_id" in event.content
    assert "Never use Hermes" in event.content
    assert '"pending_count": 2' in event.content
    assert "read_todo_list" in event.content
    assert "consecutive_unchanged_sweeps" in event.content
    assert "launch-intent" in event.content
    assert "genuinely conditional" in event.content
    assert "Escalate any material ambiguity" in event.content
    context = event.raw["vp_todo_audit_context"]
    assert context["schema_version"] == "resident-vp-special-request-audit-context-v1"
    assert context["summary"]["retained_count"] == 2
    assert context["summary"]["delegation_blocked_count"] == 2
    assert context["evidence_routes"]["running_agents"]["arguments"] == {
        "node_id": "agents/running"
    }
    # rescheduled exactly once
    assert len(store.list_scheduled_jobs(job_type="vp_todo_sweep", status="pending")) == 1


def test_sweep_does_not_duplicate_when_pending_job_exists(tmp_path) -> None:
    store = FileStore(tmp_path / "store")
    todo = tmp_path / "todo.json"
    vp_todo.add_item(todo, "x")
    config = ResidentConfig(
        special_requests_enabled=True,
        special_requests_todo_path=todo,
    )
    runtime = FakeRuntime()
    worker = _worker(store, config, runtime)
    # a future pending sweep already exists
    _seed(store, _payload(), scheduled_for=NOW + timedelta(hours=6))
    _seed(store, _payload())  # the due one

    asyncio.run(worker.run_due_once(now=NOW))

    pending = store.list_scheduled_jobs(job_type="vp_todo_sweep", status="pending")
    assert len(pending) == 1  # deduped, not duplicated


def test_sweep_missing_subject_fails_job(tmp_path) -> None:
    store = FileStore(tmp_path / "store")
    todo = tmp_path / "todo.json"
    vp_todo.add_item(todo, "x")
    config = ResidentConfig(
        special_requests_enabled=True,
        special_requests_todo_path=todo,
        special_requests_conversation_key=None,
    )  # no admin_user_ids and no subject configured
    runtime = FakeRuntime()
    worker = _worker(store, config, runtime)
    _seed(store, _payload(subject_user_id=None, conversation_key=None))

    result = asyncio.run(worker.run_due_once(now=NOW))

    assert result.fired == 0
    assert result.cancelled + result.retried == 1
    assert runtime.received == []


def test_sweep_defaults_to_dm_when_no_conversation_key(tmp_path) -> None:
    store = FileStore(tmp_path / "store")
    todo = tmp_path / "todo.json"
    vp_todo.add_item(todo, "x")
    config = ResidentConfig(
        special_requests_enabled=True,
        special_requests_todo_path=todo,
    )
    runtime = FakeRuntime()
    worker = _worker(store, config, runtime)
    _seed(store, _payload(conversation_key=None, guild_id=None, channel_id=None))

    asyncio.run(worker.run_due_once(now=NOW))

    assert len(runtime.received) == 1
    event = runtime.received[0]
    assert event.conversation_key == "discord:dm:admin-1"
    assert event.subject.user_id == "admin-1"
    assert event.subject.guild_id is None
    assert event.subject.channel_id is None


def test_sweep_subject_uses_allowlist_user(tmp_path) -> None:
    store = FileStore(tmp_path / "store")
    todo = tmp_path / "todo.json"
    vp_todo.add_item(todo, "x")
    config = ResidentConfig(
        special_requests_enabled=True,
        special_requests_todo_path=todo,
        allowed_user_ids=("owner-1", "owner-2"),
        admin_user_ids=("admin-9",),
    )
    runtime = FakeRuntime()
    worker = _worker(store, config, runtime)
    _seed(store, _payload(subject_user_id=None))  # falls back to allowed_user_ids[0]

    asyncio.run(worker.run_due_once(now=NOW))

    assert len(runtime.received) == 1
    assert runtime.received[0].subject.user_id == "owner-1"


def test_sweep_prompt_surfaces_when_condition(tmp_path) -> None:
    store = FileStore(tmp_path / "store")
    todo = tmp_path / "todo.json"
    vp_todo.add_item(todo, "ship it", when="once epic ABC is done")
    config = ResidentConfig(
        special_requests_enabled=True,
        special_requests_todo_path=todo,
    )
    runtime = FakeRuntime()
    worker = _worker(store, config, runtime)
    _seed(store, _payload())

    asyncio.run(worker.run_due_once(now=NOW))

    assert len(runtime.received) == 1
    content = runtime.received[0].content
    assert '"when": "once epic ABC is done"' in content
    assert "remains genuinely conditional" in content


def test_sweep_context_includes_full_retained_set_and_verified_custody(tmp_path) -> None:
    store = FileStore(tmp_path / "store")
    todo = tmp_path / "todo.json"
    provenance = _authoritative_origin(store)
    vp_todo.add_item(
        todo,
        "launch the canonical chain",
        launch_provenance=provenance,
    )
    failed = vp_todo.add_item(todo, "retained failed diagnostic")
    vp_todo.fail_item(todo, failed["id"], "canonical worker failed")
    vp_todo.add_item(
        todo,
        "launch downstream work",
        when="only after canonical chain completion",
        launch_provenance=provenance,
    )
    config = ResidentConfig(
        special_requests_enabled=True,
        special_requests_todo_path=todo,
    )
    runtime = FakeRuntime()
    worker = _worker(store, config, runtime)
    _seed(store, _payload())

    asyncio.run(worker.run_due_once(now=NOW))

    context = runtime.received[0].raw["vp_todo_audit_context"]
    assert context["summary"] == {
        "retained_count": 3,
        "pending_count": 2,
        "conditional_pending_count": 1,
        "delegation_blocked_count": 0,
    }
    by_task = {item["task"]: item for item in context["items"]}
    assert by_task["launch the canonical chain"]["authoritative_inbound"]["state"] == "verified"
    assert by_task["retained failed diagnostic"]["status"] == "failed"
    assert by_task["launch downstream work"]["conditional"] is True
    assert context["todo_source"]["full_list_tool"] == "read_todo_list"


def test_sweep_missing_inbound_writes_internal_diagnostic(tmp_path) -> None:
    store = FileStore(tmp_path / "store")
    todo = tmp_path / "todo.json"
    item = vp_todo.add_item(todo, "legacy request without custody")
    config = ResidentConfig(
        special_requests_enabled=True,
        special_requests_todo_path=todo,
    )
    runtime = FakeRuntime()
    worker = _worker(store, config, runtime)
    _seed(store, _payload())

    asyncio.run(worker.run_due_once(now=NOW))

    logs = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in (tmp_path / "store" / "system_logs").glob("*.json")
    ]
    diagnostic = next(
        row
        for row in logs
        if row["event_type"] == "resident_vp_todo_inbound_evidence_missing"
    )
    assert diagnostic["details"]["todo_item_id"] == item["id"]
    assert diagnostic["details"]["diagnostic_code"] == "missing_launch_provenance"
    assert diagnostic["details"]["delegation_allowed"] is False
    assert "do not manufacture a user-facing completion" in runtime.received[0].content


def test_sweep_persists_consecutive_unchanged_observation_state(tmp_path) -> None:
    store = FileStore(tmp_path / "store")
    todo = tmp_path / "todo.json"
    vp_todo.add_item(todo, "unchanged conditional", when="after external approval")
    config = ResidentConfig(
        special_requests_enabled=True,
        special_requests_todo_path=todo,
    )
    runtime = FakeRuntime()
    worker = _worker(store, config, runtime)
    _seed(store, _payload())

    asyncio.run(worker.run_due_once(now=NOW))
    first = runtime.received[-1].raw["vp_todo_audit_context"]["repeat_state"]
    assert first["unchanged_from_previous_sweep"] is False
    assert first["consecutive_unchanged_sweeps"] == 0

    asyncio.run(worker.run_due_once(now=datetime.now(UTC) + timedelta(hours=7)))
    second = runtime.received[-1].raw["vp_todo_audit_context"]["repeat_state"]
    assert second["retained_todo_digest"] == first["retained_todo_digest"]
    assert second["unchanged_from_previous_sweep"] is True
    assert second["consecutive_unchanged_sweeps"] == 1

    base = datetime.now(UTC)
    asyncio.run(worker.run_due_once(now=base + timedelta(hours=14)))
    asyncio.run(worker.run_due_once(now=base + timedelta(hours=21)))
    fourth = runtime.received[-1].raw["vp_todo_audit_context"]["repeat_state"]
    assert fourth["consecutive_unchanged_sweeps"] == 3
    logs = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in (tmp_path / "store" / "system_logs").glob("*.json")
    ]
    escalation = next(
        row
        for row in logs
        if row["event_type"] == "resident_vp_todo_unchanged_cycle_escalated"
    )
    assert escalation["details"]["consecutive_unchanged_sweeps"] == 3
    assert escalation["details"]["retained_todo_digest"] == fourth[
        "retained_todo_digest"
    ]
