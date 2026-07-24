from __future__ import annotations

from datetime import UTC, datetime

from agentbox.config import AgentBoxConfig
from agentbox.guardian.briefing import handle_briefing_task, handle_reminder_task
from agentbox.guardian.scheduler import ensure_guardian_tasks
from agentbox.guardian.state import GuardianStateStore
from agentbox.operations import open_operation_store


def test_ensure_guardian_tasks_is_idempotent(tmp_path) -> None:
    config = AgentBoxConfig(workspace_root=tmp_path / "agentbox")
    now = datetime(2026, 1, 1, tzinfo=UTC)

    first = ensure_guardian_tasks(config, now)
    second = ensure_guardian_tasks(config, now)

    assert [task.id for task in first] == [
        "guardian:briefing",
        "guardian:deep-supervision",
        "guardian:liveness",
        "guardian:reminders",
    ]
    assert [task.id for task in second] == [task.id for task in first]
    assert len(open_operation_store(config).list_scheduled_tasks()) == 4
    assert {task.idempotency_key for task in second} == {task.id for task in second}


def test_guardian_briefing_and_reminder_handlers_record_last_run(tmp_path) -> None:
    config = AgentBoxConfig(workspace_root=tmp_path / "agentbox")
    now = datetime(2026, 1, 1, tzinfo=UTC)
    tasks = {task.id: task for task in ensure_guardian_tasks(config, now)}

    briefing_result = handle_briefing_task(config, tasks["guardian:briefing"], now=now)
    reminder_result = handle_reminder_task(config, tasks["guardian:reminders"], now=now)
    state = GuardianStateStore(config).read()

    assert briefing_result["ok"] is True
    assert reminder_result["ok"] is True
    assert state["last_recurring_task_runs"]["guardian.briefing"]["result"]["ok"] is True
    assert state["last_recurring_task_runs"]["guardian.reminders"]["result"]["ok"] is True


def test_guardian_state_tracks_pause_dedupe_and_counters(tmp_path) -> None:
    config = AgentBoxConfig(workspace_root=tmp_path / "agentbox")
    ledger = GuardianStateStore(config)

    ledger.set_global_pause(True, reason="operator")
    ledger.mark_notification_sent("op-1", "stalled")
    counter = ledger.increment_counter("consecutive_inspection_failures", "op-1")
    state = ledger.read()

    assert state["global_pause"]["paused"] is True
    assert state["global_pause"]["reason"] == "operator"
    assert ledger.notification_was_sent("op-1", "stalled")
    assert counter == 1
    assert state["consecutive_inspection_failures"]["op-1"] == 1
