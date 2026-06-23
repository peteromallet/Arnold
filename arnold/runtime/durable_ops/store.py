"""Operation-run store protocol slice for durable operations."""

from __future__ import annotations

import json
import os
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Lock
from typing import Any
from typing import Protocol, runtime_checkable

from .events import OperationEvent
from .operation import OperationRun, OperationState, RetryMetadata
from .scheduled_task import ScheduledTask, ScheduledTaskState
from .typed_resources import ResourceType, TypedResource

__all__ = [
    "DurableOpsStore",
    "FileBackedDurableOpsStore",
    "OperationAlreadyExists",
    "OperationLockConflict",
    "OperationNotFound",
    "OperationEventAlreadyExists",
    "ScheduledTaskAlreadyExists",
    "ScheduledTaskNotFound",
    "ScheduledTaskLeaseConflict",
    "ScheduledTaskLeaseTokenMismatch",
    "TypedResourceAlreadyExists",
]


class OperationAlreadyExists(ValueError):
    """Raised when creating an operation run would overwrite an existing run."""


class OperationNotFound(KeyError):
    """Raised when an operation run cannot be found."""


class OperationLockConflict(RuntimeError):
    """Raised when an optimistic update uses a stale lock version."""


class TypedResourceAlreadyExists(ValueError):
    """Raised when creating a typed resource would overwrite an existing resource."""


class OperationEventAlreadyExists(ValueError):
    """Raised when appending an operation event would overwrite an existing event."""


class ScheduledTaskAlreadyExists(ValueError):
    """Raised when creating a scheduled task would overwrite an existing task."""


class ScheduledTaskNotFound(KeyError):
    """Raised when a scheduled task cannot be found."""


class ScheduledTaskLeaseConflict(RuntimeError):
    """Raised when a scheduled task cannot be claimed because its lease is active."""


class ScheduledTaskLeaseTokenMismatch(RuntimeError):
    """Raised when completing or failing a task with the wrong lease token."""


class FileBackedDurableOpsStore:
    """JSON current-state store for operation runs, resources, and events."""

    def __init__(self, root: str | os.PathLike[str]) -> None:
        self._root = Path(root)
        self._path = self._root / "operation_runs.json"
        self._lock = Lock()

    def create_operation_run(self, run: OperationRun) -> OperationRun:
        with self._lock:
            data = self._read_data()
            runs = data["operation_runs"]
            if run.id in runs:
                raise OperationAlreadyExists(run.id)
            stored = replace(run, lock_version=0)
            runs[stored.id] = _operation_run_to_json(stored)
            self._write_data(data)
            return stored

    def load_operation_run(self, operation_id: str) -> OperationRun:
        with self._lock:
            return self._load_operation_run_unlocked(operation_id)

    def list_operation_runs(self) -> tuple[OperationRun, ...]:
        with self._lock:
            data = self._read_data()
            return tuple(
                _operation_run_from_json(data["operation_runs"][operation_id])
                for operation_id in sorted(data["operation_runs"])
            )

    def update_operation_run(
        self,
        run: OperationRun,
        *,
        expected_lock_version: int,
    ) -> OperationRun:
        with self._lock:
            data = self._read_data()
            runs = data["operation_runs"]
            try:
                current = _operation_run_from_json(runs[run.id])
            except KeyError as exc:
                raise OperationNotFound(run.id) from exc
            if current.lock_version != expected_lock_version:
                raise OperationLockConflict(run.id)
            stored = replace(run, lock_version=current.lock_version + 1)
            runs[stored.id] = _operation_run_to_json(stored)
            self._write_data(data)
            return stored

    def create_typed_resource(self, resource: TypedResource) -> TypedResource:
        with self._lock:
            data = self._read_data()
            self._load_operation_run_unlocked(resource.operation_id, data=data)
            resources = data["typed_resources"]
            if resource.id in resources:
                raise TypedResourceAlreadyExists(resource.id)
            resources[resource.id] = _typed_resource_to_json(resource)
            self._write_data(data)
            return resource

    def list_typed_resources(self, operation_id: str) -> tuple[TypedResource, ...]:
        with self._lock:
            data = self._read_data()
            return tuple(
                _typed_resource_from_json(data["typed_resources"][resource_id])
                for resource_id in sorted(data["typed_resources"])
                if data["typed_resources"][resource_id].get("operation_id")
                == operation_id
            )

    def append_operation_event(self, event: OperationEvent) -> OperationEvent:
        with self._lock:
            data = self._read_data()
            self._load_operation_run_unlocked(event.operation_id, data=data)
            events = data["operation_events"]
            if event.id in events:
                raise OperationEventAlreadyExists(event.id)
            sequence = _next_event_sequence(events, operation_id=event.operation_id)
            stored = replace(event, sequence=sequence)
            events[stored.id] = _operation_event_to_json(stored)
            self._write_data(data)
            return stored

    def list_operation_events(self, operation_id: str) -> tuple[OperationEvent, ...]:
        with self._lock:
            data = self._read_data()
            events = (
                _operation_event_from_json(raw)
                for raw in data["operation_events"].values()
                if raw.get("operation_id") == operation_id
            )
            return tuple(sorted(events, key=lambda event: event.sequence))

    def create_scheduled_task(self, task: ScheduledTask) -> ScheduledTask:
        with self._lock:
            data = self._read_data()
            tasks = data["scheduled_tasks"]
            if task.id in tasks:
                raise ScheduledTaskAlreadyExists(task.id)
            stored = replace(task, lock_version=0)
            tasks[stored.id] = _scheduled_task_to_json(stored)
            self._write_data(data)
            return stored

    def load_scheduled_task(self, task_id: str) -> ScheduledTask:
        with self._lock:
            return self._load_scheduled_task_unlocked(task_id)

    def list_scheduled_tasks(self) -> tuple[ScheduledTask, ...]:
        with self._lock:
            data = self._read_data()
            return tuple(
                _scheduled_task_from_json(data["scheduled_tasks"][task_id])
                for task_id in sorted(data["scheduled_tasks"])
            )

    def claim_scheduled_task(
        self,
        task_id: str,
        *,
        lease_owner: str,
        lease_token: str,
        lease_seconds: int,
        now: datetime | None = None,
    ) -> ScheduledTask:
        with self._lock:
            data = self._read_data()
            task = self._load_scheduled_task_unlocked(task_id, data=data)
            timestamp = now or _utc_now()
            if lease_seconds <= 0:
                raise ScheduledTaskLeaseConflict(task_id)
            if task.has_active_lease(timestamp):
                raise ScheduledTaskLeaseConflict(task_id)
            try:
                claimed = task.claim(
                    lease_owner=lease_owner,
                    lease_token=lease_token,
                    lease_expires_at=timestamp + timedelta(seconds=lease_seconds),
                    now=timestamp,
                )
            except ValueError as exc:
                raise ScheduledTaskLeaseConflict(task_id) from exc
            stored = replace(claimed, lock_version=task.lock_version + 1)
            data["scheduled_tasks"][stored.id] = _scheduled_task_to_json(stored)
            self._write_data(data)
            return stored

    def complete_scheduled_task(
        self,
        task_id: str,
        *,
        lease_token: str,
        result: dict[str, Any] | None = None,
        now: datetime | None = None,
    ) -> ScheduledTask:
        with self._lock:
            data = self._read_data()
            raw = self._load_scheduled_task_json_unlocked(task_id, data=data)
            task = _scheduled_task_from_json(raw)
            if raw.get("_last_completed_lease_token") == lease_token:
                return task
            try:
                completed = task.complete(
                    lease_token=lease_token,
                    result=result,
                    now=now,
                )
            except ValueError as exc:
                raise ScheduledTaskLeaseTokenMismatch(task_id) from exc
            stored = replace(completed, lock_version=task.lock_version + 1)
            data["scheduled_tasks"][stored.id] = {
                **_scheduled_task_to_json(stored),
                "_last_completed_lease_token": lease_token,
            }
            self._write_data(data)
            return stored

    def fail_scheduled_task(
        self,
        task_id: str,
        *,
        lease_token: str,
        result: dict[str, Any],
        now: datetime | None = None,
    ) -> ScheduledTask:
        with self._lock:
            data = self._read_data()
            task = self._load_scheduled_task_unlocked(task_id, data=data)
            try:
                failed = task.fail(
                    lease_token=lease_token,
                    result=result,
                    now=now,
                )
            except ValueError as exc:
                raise ScheduledTaskLeaseTokenMismatch(task_id) from exc
            stored = replace(failed, lock_version=task.lock_version + 1)
            data["scheduled_tasks"][stored.id] = _scheduled_task_to_json(stored)
            self._write_data(data)
            return stored

    def cancel_scheduled_task(
        self,
        task_id: str,
        *,
        now: datetime | None = None,
    ) -> ScheduledTask:
        with self._lock:
            data = self._read_data()
            task = self._load_scheduled_task_unlocked(task_id, data=data)
            cancelled = task.cancel(now=now)
            stored = replace(cancelled, lock_version=task.lock_version + 1)
            data["scheduled_tasks"][stored.id] = _scheduled_task_to_json(stored)
            self._write_data(data)
            return stored

    def _load_operation_run_unlocked(
        self,
        operation_id: str,
        *,
        data: dict[str, dict[str, dict[str, Any]]] | None = None,
    ) -> OperationRun:
        data = data or self._read_data()
        try:
            return _operation_run_from_json(data["operation_runs"][operation_id])
        except KeyError as exc:
            raise OperationNotFound(operation_id) from exc

    def _load_scheduled_task_unlocked(
        self,
        task_id: str,
        *,
        data: dict[str, dict[str, dict[str, Any]]] | None = None,
    ) -> ScheduledTask:
        raw = self._load_scheduled_task_json_unlocked(task_id, data=data)
        return _scheduled_task_from_json(raw)

    def _load_scheduled_task_json_unlocked(
        self,
        task_id: str,
        *,
        data: dict[str, dict[str, dict[str, Any]]] | None = None,
    ) -> dict[str, Any]:
        data = data or self._read_data()
        try:
            return data["scheduled_tasks"][task_id]
        except KeyError as exc:
            raise ScheduledTaskNotFound(task_id) from exc

    def _read_data(self) -> dict[str, dict[str, dict[str, Any]]]:
        if not self._path.exists():
            return {
                "operation_runs": {},
                "typed_resources": {},
                "operation_events": {},
                "scheduled_tasks": {},
            }
        with self._path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
        data = {
            "operation_runs": raw.get("operation_runs", {}),
            "typed_resources": raw.get("typed_resources", {}),
            "operation_events": raw.get("operation_events", {}),
            "scheduled_tasks": raw.get("scheduled_tasks", {}),
        }
        for key, value in data.items():
            if not isinstance(value, dict):
                raise ValueError(f"{key} must be a JSON object")
        return data

    def _write_data(self, data: dict[str, dict[str, dict[str, Any]]]) -> None:
        self._root.mkdir(parents=True, exist_ok=True)
        tmp_path = self._path.with_suffix(".json.tmp")
        with tmp_path.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, sort_keys=True)
            handle.write("\n")
        tmp_path.replace(self._path)


@runtime_checkable
class DurableOpsStore(Protocol):
    """Operation-run current-state, resource, and event store."""

    def create_operation_run(self, run: OperationRun) -> OperationRun:  # pragma: no cover - protocol
        ...

    def load_operation_run(self, operation_id: str) -> OperationRun:  # pragma: no cover - protocol
        ...

    def list_operation_runs(self) -> tuple[OperationRun, ...]:  # pragma: no cover - protocol
        ...

    def update_operation_run(
        self,
        run: OperationRun,
        *,
        expected_lock_version: int,
    ) -> OperationRun:  # pragma: no cover - protocol
        ...

    def create_typed_resource(self, resource: TypedResource) -> TypedResource:  # pragma: no cover - protocol
        ...

    def list_typed_resources(self, operation_id: str) -> tuple[TypedResource, ...]:  # pragma: no cover - protocol
        ...

    def append_operation_event(self, event: OperationEvent) -> OperationEvent:  # pragma: no cover - protocol
        ...

    def list_operation_events(self, operation_id: str) -> tuple[OperationEvent, ...]:  # pragma: no cover - protocol
        ...

    def create_scheduled_task(self, task: ScheduledTask) -> ScheduledTask:  # pragma: no cover - protocol
        ...

    def load_scheduled_task(self, task_id: str) -> ScheduledTask:  # pragma: no cover - protocol
        ...

    def list_scheduled_tasks(self) -> tuple[ScheduledTask, ...]:  # pragma: no cover - protocol
        ...

    def claim_scheduled_task(
        self,
        task_id: str,
        *,
        lease_owner: str,
        lease_token: str,
        lease_seconds: int,
        now: datetime | None = None,
    ) -> ScheduledTask:  # pragma: no cover - protocol
        ...

    def complete_scheduled_task(
        self,
        task_id: str,
        *,
        lease_token: str,
        result: dict[str, Any] | None = None,
        now: datetime | None = None,
    ) -> ScheduledTask:  # pragma: no cover - protocol
        ...

    def fail_scheduled_task(
        self,
        task_id: str,
        *,
        lease_token: str,
        result: dict[str, Any],
        now: datetime | None = None,
    ) -> ScheduledTask:  # pragma: no cover - protocol
        ...

    def cancel_scheduled_task(
        self,
        task_id: str,
        *,
        now: datetime | None = None,
    ) -> ScheduledTask:  # pragma: no cover - protocol
        ...


def _operation_run_to_json(run: OperationRun) -> dict[str, Any]:
    return {
        "id": run.id,
        "operation_type": run.operation_type,
        "state": run.state.value,
        "parent_operation_id": run.parent_operation_id,
        "operation_dir": run.operation_dir,
        "retry": {
            "attempt": run.retry.attempt,
            "max_attempts": run.retry.max_attempts,
            "last_error": run.retry.last_error,
        },
        "idempotency_key": run.idempotency_key,
        "metadata": dict(run.metadata),
        "created_at": _datetime_to_json(run.created_at),
        "updated_at": _datetime_to_json(run.updated_at),
        "started_at": _datetime_to_json(run.started_at),
        "completed_at": _datetime_to_json(run.completed_at),
        "lock_version": run.lock_version,
    }


def _operation_run_from_json(data: dict[str, Any]) -> OperationRun:
    retry_data = data.get("retry", {})
    return OperationRun(
        id=data["id"],
        operation_type=data["operation_type"],
        state=OperationState(data["state"]),
        parent_operation_id=data.get("parent_operation_id"),
        operation_dir=data.get("operation_dir"),
        retry=RetryMetadata(
            attempt=retry_data.get("attempt", 0),
            max_attempts=retry_data.get("max_attempts", 1),
            last_error=retry_data.get("last_error"),
        ),
        idempotency_key=data.get("idempotency_key"),
        metadata=data.get("metadata", {}),
        created_at=_datetime_from_json(data["created_at"]),
        updated_at=_datetime_from_json(data["updated_at"]),
        started_at=_datetime_from_json(data.get("started_at")),
        completed_at=_datetime_from_json(data.get("completed_at")),
        lock_version=data.get("lock_version", 0),
    )


def _typed_resource_to_json(resource: TypedResource) -> dict[str, Any]:
    return {
        "id": resource.id,
        "operation_id": resource.operation_id,
        "resource_type": resource.resource_type.value,
        "name": resource.name,
        "details": dict(resource.details),
        "created_at": _datetime_to_json(resource.created_at),
        "updated_at": _datetime_to_json(resource.updated_at),
    }


def _typed_resource_from_json(data: dict[str, Any]) -> TypedResource:
    return TypedResource(
        id=data["id"],
        operation_id=data["operation_id"],
        resource_type=ResourceType(data["resource_type"]),
        name=data["name"],
        details=data.get("details", {}),
        created_at=_datetime_from_json(data["created_at"]),
        updated_at=_datetime_from_json(data["updated_at"]),
    )


def _operation_event_to_json(event: OperationEvent) -> dict[str, Any]:
    return {
        "id": event.id,
        "operation_id": event.operation_id,
        "sequence": event.sequence,
        "event_type": event.event_type,
        "summary": event.summary,
        "payload": dict(event.payload),
        "artifact_paths": list(event.artifact_paths),
        "debug_paths": list(event.debug_paths),
        "occurred_at": _datetime_to_json(event.occurred_at),
    }


def _operation_event_from_json(data: dict[str, Any]) -> OperationEvent:
    return OperationEvent(
        id=data["id"],
        operation_id=data["operation_id"],
        sequence=data.get("sequence", 0),
        event_type=data["event_type"],
        summary=data["summary"],
        payload=data.get("payload", {}),
        artifact_paths=tuple(data.get("artifact_paths", ())),
        debug_paths=tuple(data.get("debug_paths", ())),
        occurred_at=_datetime_from_json(data["occurred_at"]),
    )


def _scheduled_task_to_json(task: ScheduledTask) -> dict[str, Any]:
    return {
        "id": task.id,
        "task_type": task.task_type,
        "owner_id": task.owner_id,
        "state": task.state.value,
        "operation_id": task.operation_id,
        "schedule": task.schedule,
        "recurring_interval_seconds": task.recurring_interval_seconds,
        "retry_delay_seconds": task.retry_delay_seconds,
        "jitter_seconds": task.jitter_seconds,
        "payload": dict(task.payload),
        "next_run_at": _datetime_to_json(task.next_run_at),
        "last_result": None if task.last_result is None else dict(task.last_result),
        "failure_count": task.failure_count,
        "max_failures": task.max_failures,
        "lease_owner": task.lease_owner,
        "lease_token": task.lease_token,
        "lease_expires_at": _datetime_to_json(task.lease_expires_at),
        "idempotency_key": task.idempotency_key,
        "created_at": _datetime_to_json(task.created_at),
        "updated_at": _datetime_to_json(task.updated_at),
        "lock_version": task.lock_version,
    }


def _scheduled_task_from_json(data: dict[str, Any]) -> ScheduledTask:
    return ScheduledTask(
        id=data["id"],
        task_type=data["task_type"],
        owner_id=data["owner_id"],
        state=ScheduledTaskState(data["state"]),
        operation_id=data.get("operation_id"),
        schedule=data.get("schedule"),
        recurring_interval_seconds=data.get("recurring_interval_seconds"),
        retry_delay_seconds=data.get("retry_delay_seconds"),
        jitter_seconds=data.get("jitter_seconds", 0),
        payload=data.get("payload", {}),
        next_run_at=_datetime_from_json(data.get("next_run_at")),
        last_result=data.get("last_result"),
        failure_count=data.get("failure_count", 0),
        max_failures=data.get("max_failures", 1),
        lease_owner=data.get("lease_owner"),
        lease_token=data.get("lease_token"),
        lease_expires_at=_datetime_from_json(data.get("lease_expires_at")),
        idempotency_key=data.get("idempotency_key"),
        created_at=_datetime_from_json(data["created_at"]),
        updated_at=_datetime_from_json(data["updated_at"]),
        lock_version=data.get("lock_version", 0),
    )


def _next_event_sequence(
    events: dict[str, dict[str, Any]],
    *,
    operation_id: str,
) -> int:
    sequences = [
        raw.get("sequence", 0)
        for raw in events.values()
        if raw.get("operation_id") == operation_id
    ]
    return max(sequences, default=0) + 1


def _datetime_to_json(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _datetime_from_json(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(value)


def _utc_now() -> datetime:
    return datetime.now(UTC)
