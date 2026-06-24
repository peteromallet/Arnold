"""File-backed Guardian state ledger."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Mapping

from arnold.runtime.durable_ops import OperationLockConflict, OperationNotFound
from arnold.runtime.durable_ops.store import interprocess_json_lock, write_json_atomically

from agentbox.config import AgentBoxConfig
from agentbox.operations import open_operation_store

GUARDIAN_STATE_FILENAME = "guardian_state.json"
GUARDIAN_LOCK_FILENAME = "operation_runs.lock"


class GuardianStateStore:
    """JSON ledger for Guardian global state and per-operation dedupe/counters."""

    lock_timeout_seconds = 30.0

    def __init__(self, config: AgentBoxConfig) -> None:
        self._root = Path(config.ops_store_root)
        self._path = self._root / GUARDIAN_STATE_FILENAME
        self._lock_path = self._root / GUARDIAN_LOCK_FILENAME
        self._operation_store = open_operation_store(config)

    def read(self) -> dict[str, Any]:
        with interprocess_json_lock(self._lock_path, timeout_seconds=self.lock_timeout_seconds):
            return self._read_unlocked()

    def update(self, mutator: Callable[[dict[str, Any]], None]) -> dict[str, Any]:
        with interprocess_json_lock(self._lock_path, timeout_seconds=self.lock_timeout_seconds):
            data = self._read_unlocked()
            mutator(data)
            data["updated_at"] = _datetime_to_json(_utc_now())
            self._write_unlocked(data)
            return data

    def set_global_pause(
        self,
        paused: bool,
        *,
        reason: str | None = None,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        timestamp = now or _utc_now()

        def mutate(data: dict[str, Any]) -> None:
            data["global_pause"] = {
                "paused": paused,
                "reason": reason,
                "updated_at": _datetime_to_json(timestamp),
            }

        return self.update(mutate)

    def mark_notification_sent(
        self,
        operation_id: str,
        notification_key: str,
        *,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        timestamp = now or _utc_now()

        def mutate(data: dict[str, Any]) -> None:
            dedupe = data["operation_notification_dedupe"].setdefault(operation_id, {})
            dedupe[notification_key] = _datetime_to_json(timestamp)

        return self.update(mutate)

    def notification_was_sent(self, operation_id: str, notification_key: str) -> bool:
        data = self.read()
        return (
            notification_key
            in data["operation_notification_dedupe"].get(operation_id, {})
        )

    def record_task_run(
        self,
        task_type: str,
        *,
        now: datetime | None = None,
        result: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        timestamp = now or _utc_now()

        def mutate(data: dict[str, Any]) -> None:
            data["last_recurring_task_runs"][task_type] = {
                "recorded_at": _datetime_to_json(timestamp),
                "result": dict(result or {}),
            }

        return self.update(mutate)

    def set_counter(
        self,
        bucket: str,
        key: str,
        value: int,
    ) -> dict[str, Any]:
        if value < 0:
            raise ValueError("counter value must be non-negative")
        if bucket not in {
            "consecutive_inspection_failures",
            "resume_attempt_counters",
            "transient_retry_counters",
        }:
            raise ValueError(f"unknown Guardian counter bucket: {bucket}")

        def mutate(data: dict[str, Any]) -> None:
            if value:
                data[bucket][key] = value
            else:
                data[bucket].pop(key, None)

        return self.update(mutate)

    def increment_counter(self, bucket: str, key: str) -> int:
        next_value = 0

        def mutate(data: dict[str, Any]) -> None:
            nonlocal next_value
            current = int(data[bucket].get(key, 0))
            next_value = current + 1
            data[bucket][key] = next_value

        self.update(mutate)
        return next_value

    def merge_operation_metadata(
        self,
        operation_id: str,
        metadata: Mapping[str, Any],
        *,
        expected_lock_version: int | None = None,
    ) -> Any:
        """Merge metadata onto an operation using the durable store lock version."""

        current = self._operation_store.load_operation_run(operation_id)
        if expected_lock_version is not None and current.lock_version != expected_lock_version:
            raise OperationLockConflict(operation_id)
        updated_metadata = dict(current.metadata)
        updated_metadata.update(dict(metadata))
        updated = replace(current, metadata=updated_metadata)
        return self._operation_store.update_operation_run(
            updated,
            expected_lock_version=current.lock_version,
        )

    def merge_operation_metadata_if_present(
        self,
        operation_id: str,
        metadata: Mapping[str, Any],
    ) -> Any | None:
        try:
            return self.merge_operation_metadata(operation_id, metadata)
        except OperationNotFound:
            return None

    def _read_unlocked(self) -> dict[str, Any]:
        if not self._path.exists():
            return _default_state()
        with self._path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
        data = _default_state()
        for key in data:
            value = raw.get(key, data[key])
            data[key] = value if isinstance(value, type(data[key])) else data[key]
        return data

    def _write_unlocked(self, data: Mapping[str, Any]) -> None:
        write_json_atomically(self._path, dict(data))


def _default_state() -> dict[str, Any]:
    now = _datetime_to_json(_utc_now())
    return {
        "schema_version": 1,
        "global_pause": {
            "paused": False,
            "reason": None,
            "updated_at": None,
        },
        "operation_notification_dedupe": {},
        "consecutive_inspection_failures": {},
        "resume_attempt_counters": {},
        "transient_retry_counters": {},
        "last_recurring_task_runs": {},
        "created_at": now,
        "updated_at": now,
    }


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _datetime_to_json(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()
