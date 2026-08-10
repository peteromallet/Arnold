"""No-op Guardian briefing and reminder task handlers."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from arnold.runtime.durable_ops import ScheduledTask

from agentbox.config import AgentBoxConfig
from agentbox.guardian.state import GuardianStateStore


def handle_briefing_task(
    config: AgentBoxConfig,
    task: ScheduledTask,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Record that the Guardian briefing task was reached."""

    timestamp = now or datetime.now(UTC)
    result = {
        "ok": True,
        "handler": "guardian.briefing",
        "task_id": task.id,
        "recorded_at": timestamp.isoformat(),
    }
    GuardianStateStore(config).record_task_run(task.task_type, now=timestamp, result=result)
    return result


def handle_reminder_task(
    config: AgentBoxConfig,
    task: ScheduledTask,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Record that the Guardian reminder task was reached."""

    timestamp = now or datetime.now(UTC)
    result = {
        "ok": True,
        "handler": "guardian.reminders",
        "task_id": task.id,
        "recorded_at": timestamp.isoformat(),
    }
    GuardianStateStore(config).record_task_run(task.task_type, now=timestamp, result=result)
    return result
