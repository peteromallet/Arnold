"""Guardian recurring scheduled-task registration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from arnold.runtime.durable_ops import (
    ScheduledTask,
    ScheduledTaskAlreadyExists,
    ScheduledTaskNotFound,
)

from agentbox.config import AgentBoxConfig
from agentbox.operations import open_operation_store

GUARDIAN_OWNER_ID = "guardian"
GUARDIAN_TASK_IDS = (
    "guardian:liveness",
    "guardian:deep-supervision",
    "guardian:briefing",
    "guardian:reminders",
)


@dataclass(frozen=True)
class GuardianTaskDefinition:
    task_id: str
    task_type: str
    interval_seconds: int


GUARDIAN_TASK_DEFINITIONS = (
    GuardianTaskDefinition("guardian:liveness", "guardian.liveness", 60),
    GuardianTaskDefinition("guardian:deep-supervision", "guardian.deep_supervision", 300),
    GuardianTaskDefinition("guardian:briefing", "guardian.briefing", 900),
    GuardianTaskDefinition("guardian:reminders", "guardian.reminders", 300),
)


def ensure_guardian_tasks(
    config: AgentBoxConfig,
    now: datetime | None = None,
) -> tuple[ScheduledTask, ...]:
    """Idempotently ensure the four global Guardian recurring tasks exist."""

    timestamp = now or datetime.now(UTC)
    store = open_operation_store(config)
    ensured: list[ScheduledTask] = []
    for definition in GUARDIAN_TASK_DEFINITIONS:
        try:
            ensured.append(store.load_scheduled_task(definition.task_id))
            continue
        except ScheduledTaskNotFound:
            pass
        task = ScheduledTask(
            id=definition.task_id,
            task_type=definition.task_type,
            owner_id=GUARDIAN_OWNER_ID,
            recurring_interval_seconds=definition.interval_seconds,
            retry_delay_seconds=definition.interval_seconds,
            max_failures=3,
            next_run_at=timestamp,
            idempotency_key=definition.task_id,
            payload={"guardian_global": True},
            created_at=timestamp,
            updated_at=timestamp,
        )
        try:
            ensured.append(store.create_scheduled_task(task))
        except ScheduledTaskAlreadyExists:
            ensured.append(store.load_scheduled_task(definition.task_id))
    return tuple(sorted(ensured, key=lambda task: task.id))
