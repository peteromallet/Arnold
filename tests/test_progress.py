from __future__ import annotations

import json
import os

from megaplan.orchestration.progress import (
    ENV_ACTOR_ID,
    ENV_BACKEND,
    ENV_DSN_ENV,
    ENV_ENABLED,
    ENV_EPIC_ID,
    ENV_FILE_ROOT,
    ENV_PLAN_ID,
    ENV_PROJECT_ROOT,
    ENV_RUN_ID,
    ENV_SPRINT_ID,
    ProgressContext,
    ProgressEmitter,
    strip_progress_env,
)
from megaplan.store import FileStore
from megaplan.worktrees.identity import make_task_identity


def test_progress_emitter_noops_without_store_or_context() -> None:
    assert ProgressEmitter.disabled().phase_start("plan") is None
    assert ProgressEmitter.from_env({}).phase_start("plan") is None


def test_progress_emitter_appends_idempotent_structured_events(tmp_path) -> None:
    store = FileStore(tmp_path / "store")
    epic = store.create_epic(title="Epic", goal="Goal", body="Body")
    emitter = ProgressEmitter(
        store,
        epic_id=epic.id,
        plan_id="plan-1",
        sprint_id="sprint-1",
        run_id="run-1",
    )

    first = emitter.phase_start("execute", worker="codex")
    duplicate = emitter.phase_start("execute", worker="codex")
    identity = make_task_identity("T2")
    done = emitter.task_complete(
        identity.task_key,
        task_id="T2",
        task_id_encoded=identity.original_task_id_encoded,
        status="done",
    )

    events = store.list_progress_events(epic_id=epic.id, plan_id="plan-1")
    assert first is not None
    assert duplicate is not None
    assert done is not None
    assert duplicate.id == first.id
    assert [event.kind for event in events] == ["phase_start", "task_complete"]
    assert events[0].details == {"phase": "execute", "worker": "codex", "run_id": "run-1"}
    assert events[1].details == {
        "task_key": identity.task_key,
        "task_id": "T2",
        "task_id_encoded": identity.original_task_id_encoded,
        "status": "done",
        "run_id": "run-1",
    }
    assert all(event.idempotency_key for event in events)


def test_progress_emitter_retains_legacy_batch_complete_event(tmp_path) -> None:
    store = FileStore(tmp_path / "store")
    epic = store.create_epic(title="Epic", goal="Goal", body="Body")
    emitter = ProgressEmitter(store, epic_id=epic.id, plan_id="plan-1", run_id="run-1")

    event = emitter.batch_complete("batch-1", task_ids=["T2"])

    assert event is not None
    events = store.list_progress_events(epic_id=epic.id, plan_id="plan-1")
    assert [row.kind for row in events] == ["batch_complete"]
    assert events[0].details == {
        "batch_id": "batch-1",
        "task_ids": ["T2"],
        "run_id": "run-1",
    }


def test_progress_context_serializes_only_non_secret_env_values(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SUPABASE_DB_URL", "postgresql://user:password@example/db")
    context = ProgressContext(
        backend="multi",
        project_root=str(tmp_path / "project"),
        file_root=str(tmp_path / "store"),
        actor_id="actor-1",
        dsn_env="SUPABASE_DB_URL",
        epic_id="epic-1",
        plan_id="plan-1",
        sprint_id="sprint-1",
        run_id="run-1",
    )

    env = context.to_env()

    assert env == {
        ENV_ENABLED: "1",
        ENV_BACKEND: "multi",
        ENV_PROJECT_ROOT: str(tmp_path / "project"),
        ENV_FILE_ROOT: str(tmp_path / "store"),
        ENV_ACTOR_ID: "actor-1",
        ENV_DSN_ENV: "SUPABASE_DB_URL",
        ENV_EPIC_ID: "epic-1",
        ENV_PLAN_ID: "plan-1",
        ENV_SPRINT_ID: "sprint-1",
        ENV_RUN_ID: "run-1",
    }
    assert "password" not in repr(env)
    assert ProgressContext.from_env(env) == context


def test_progress_emitter_reconstructs_file_store_from_env(tmp_path) -> None:
    file_root = tmp_path / "store"
    setup_store = FileStore(file_root)
    epic = setup_store.create_epic(title="Epic", goal="Goal", body="Body")
    env = ProgressContext(
        backend="file",
        file_root=str(file_root),
        epic_id=epic.id,
        plan_id="plan-1",
        run_id="run-1",
    ).to_env()

    event = ProgressEmitter.from_env(env).gate_pending("gate-1")

    assert event is not None
    events = setup_store.list_progress_events(epic_id=epic.id, plan_id="plan-1")
    assert len(events) == 1
    assert events[0].kind == "gate_pending"
    assert events[0].details == {"gate_id": "gate-1", "run_id": "run-1"}


def test_strip_progress_env_removes_only_progress_keys() -> None:
    env = {
        ENV_ENABLED: "1",
        ENV_EPIC_ID: "epic-1",
        "OPENAI_API_KEY": "secret",
        "PATH": os.environ.get("PATH", ""),
    }

    assert strip_progress_env(env) == {
        "OPENAI_API_KEY": "secret",
        "PATH": os.environ.get("PATH", ""),
    }


def test_cli_handler_gets_progress_emitter_from_env(tmp_path, monkeypatch) -> None:
    from megaplan import cli

    setup_store = FileStore(tmp_path / "store")
    epic = setup_store.create_epic(title="Epic", goal="Goal", body="Body")
    env = ProgressContext(
        backend="file",
        file_root=str(tmp_path / "store"),
        epic_id=epic.id,
        plan_id="demo",
    ).to_env()
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    monkeypatch.chdir(tmp_path)
    captured = {}

    def fake_status(root, args):
        captured["root"] = root
        captured["emitter"] = args.progress_emitter
        return {"success": True, "step": "status"}

    monkeypatch.setitem(cli.COMMAND_HANDLERS, "status", fake_status)

    assert cli.main(["status", "--plan", "demo"]) == 0
    event = captured["emitter"].phase_end("status")

    assert event is not None
    events = setup_store.list_progress_events(epic_id=epic.id, plan_id="demo")
    assert [row.kind for row in events] == ["phase_end"]


def test_cli_phase_command_emits_lifecycle_events_from_runtime(tmp_path, monkeypatch) -> None:
    from megaplan import cli

    setup_store = FileStore(tmp_path / "store")
    epic = setup_store.create_epic(title="Epic", goal="Goal", body="Body")
    env = ProgressContext(
        backend="file",
        file_root=str(tmp_path / "store"),
        epic_id=epic.id,
        plan_id="demo",
        run_id="run-1",
    ).to_env()
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    monkeypatch.chdir(tmp_path)

    def fake_plan(root, args):
        del root, args
        return {"success": True, "step": "plan", "summary": "done", "state": "done", "next_step": None}

    monkeypatch.setitem(cli.COMMAND_HANDLERS, "plan", fake_plan)

    assert cli.main(["plan", "--plan", "demo"]) == 0

    events = setup_store.list_progress_events(epic_id=epic.id, plan_id="demo")
    assert [row.kind for row in events] == ["phase_start", "phase_end", "plan_done"]
    assert events[0].details == {"phase": "plan", "plan": "demo", "run_id": "run-1"}
    assert events[1].details["success"] is True
    assert events[1].details["state"] == "done"
    assert events[2].details == {"phase": "plan", "run_id": "run-1"}


def test_auto_lifecycle_failure_emits_progress_without_losing_resume_cursor(tmp_path, monkeypatch) -> None:
    from megaplan import auto
    from megaplan._core import atomic_write_json

    setup_store = FileStore(tmp_path / "store")
    epic = setup_store.create_epic(title="Epic", goal="Goal", body="Body")
    plan_dir = tmp_path / ".megaplan" / "plans" / "demo"
    plan_dir.mkdir(parents=True)
    atomic_write_json(
        plan_dir / "state.json",
        {
            "name": "demo",
            "current_state": "initialized",
            "iteration": 1,
            "meta": {"epic_id": epic.id},
            "config": {"project_dir": str(tmp_path)},
            "history": [],
        },
    )
    env = ProgressContext(
        backend="file",
        file_root=str(tmp_path / "store"),
        epic_id=epic.id,
        plan_id="demo",
        run_id="run-1",
    ).to_env()

    def fail_status(*args, **kwargs):
        del args, kwargs
        raise RuntimeError("status broke")

    monkeypatch.setattr(auto, "_status", fail_status)

    outcome = auto.drive("demo", cwd=tmp_path, max_iterations=1, progress_env=env, poll_sleep=0)

    assert outcome.status == "failed"
    state = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    assert state["current_state"] == "failed"
    assert state["latest_failure"]["kind"] == "status_lookup_failed"
    assert state["resume_cursor"] == {"phase": "status", "retry_strategy": "rerun_status"}
    events = setup_store.list_progress_events(epic_id=epic.id, plan_id="demo")
    assert [row.kind for row in events] == ["plan_failed"]
    assert events[0].details["kind"] == "status_lookup_failed"
    assert events[0].details["run_id"] == "run-1"
