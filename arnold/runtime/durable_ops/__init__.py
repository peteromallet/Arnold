"""Neutral durable operation contracts owned by Arnold runtime core."""

from __future__ import annotations

from .approval import ApprovalLink
from .events import OperationEvent
from .handler import OperationHandler
from .operation import (
    InvalidOperationTransition,
    OperationRun,
    OperationState,
    RetryMetadata,
    can_transition_operation,
    ensure_operation_transition,
    is_terminal_operation_state,
)
from .scheduled_task import (
    InvalidScheduledTaskTransition,
    ScheduledTask,
    ScheduledTaskState,
    can_transition_scheduled_task,
    ensure_scheduled_task_transition,
    is_terminal_scheduled_task_state,
)
from .store import (
    DurableOpsStore,
    FileBackedDurableOpsStore,
    OperationAlreadyExists,
    OperationEventAlreadyExists,
    OperationLockConflict,
    OperationNotFound,
    ScheduledTaskAlreadyExists,
    ScheduledTaskLeaseConflict,
    ScheduledTaskLeaseTokenMismatch,
    ScheduledTaskNotFound,
    TypedResourceAlreadyExists,
)
from .typed_resources import ResourceType, TypedResource

__all__ = [
    "ApprovalLink",
    "DurableOpsStore",
    "FileBackedDurableOpsStore",
    "InvalidOperationTransition",
    "InvalidScheduledTaskTransition",
    "OperationAlreadyExists",
    "OperationEvent",
    "OperationEventAlreadyExists",
    "OperationHandler",
    "OperationLockConflict",
    "OperationNotFound",
    "OperationRun",
    "OperationState",
    "ResourceType",
    "RetryMetadata",
    "ScheduledTask",
    "ScheduledTaskAlreadyExists",
    "ScheduledTaskLeaseConflict",
    "ScheduledTaskLeaseTokenMismatch",
    "ScheduledTaskNotFound",
    "ScheduledTaskState",
    "TypedResource",
    "TypedResourceAlreadyExists",
    "can_transition_operation",
    "can_transition_scheduled_task",
    "ensure_operation_transition",
    "ensure_scheduled_task_transition",
    "is_terminal_operation_state",
    "is_terminal_scheduled_task_state",
]
