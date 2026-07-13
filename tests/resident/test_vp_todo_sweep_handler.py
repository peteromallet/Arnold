from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from arnold_pipelines.megaplan.resident import vp_todo
from arnold_pipelines.megaplan.resident.config import ResidentConfig
from arnold_pipelines.megaplan.resident.scheduler import make_store_scheduler
from arnold_pipelines.megaplan.store import FileStore, ScheduledJobInput

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
    assert "complete_todo_item" in event.content
    assert "fail_todo_item" in event.content
    assert "backend=codex" in event.content
    assert "background=true" in event.content
    assert "request_id" in event.content
    assert "Never use the legacy Hermes" in event.content
    assert "2 pending" in event.content
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
    assert "when: once epic ABC is done" in content
    assert "verify it is satisfied" in content
