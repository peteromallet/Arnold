"""Shared task manifest for dynamic SWE-bench worker coordination."""

from __future__ import annotations

import fcntl
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class TaskManifest:
    """JSON-backed task manifest coordinated with a sidecar flock lock."""

    def __init__(self, path: Path, data: dict[str, Any]):
        self.path = Path(path)
        self.lock_path = self.path.parent / f"{self.path.name}.lock"
        self._data = data

    @classmethod
    def create(cls, path: str | Path, tasks: list[str]) -> "TaskManifest":
        manifest = cls(Path(path), {})
        payload = manifest._build_payload(tasks)
        with manifest._lock():
            manifest._write_unlocked(payload)
        manifest._data = payload
        return manifest

    @classmethod
    def load(cls, path: str | Path) -> "TaskManifest":
        manifest = cls(Path(path), {})
        manifest._data = manifest._read_current()
        return manifest

    @classmethod
    def load_or_create(cls, path: str | Path, tasks: list[str]) -> "TaskManifest":
        manifest = cls(Path(path), {})
        with manifest._lock():
            if manifest.path.exists():
                payload = manifest._read_unlocked()
            else:
                payload = manifest._build_payload(tasks)
                manifest._write_unlocked(payload)
        manifest._data = payload
        return manifest

    def claim_batch(self, worker_id: str, batch_size: int) -> list[str]:
        """Atomically claim up to ``batch_size`` pending tasks for a worker."""
        if batch_size < 1:
            return []

        claimed_at = _utc_now()
        with self._lock():
            payload = self._read_unlocked()
            claimed: list[str] = []
            for instance_id, task in payload["tasks"].items():
                if task.get("status") != "pending":
                    continue
                task["status"] = "claimed"
                task["worker"] = worker_id
                task["claimed_at"] = claimed_at
                claimed.append(instance_id)
                if len(claimed) >= batch_size:
                    break
            if claimed:
                self._write_unlocked(payload)
            self._data = payload
            return claimed

    def mark_done(self, instance_id: str, worker_id: str) -> None:
        done_at = _utc_now()
        with self._lock():
            payload = self._read_unlocked()
            task = _require_task(payload, instance_id)
            task["status"] = "done"
            task["worker"] = worker_id
            task["done_at"] = done_at
            self._write_unlocked(payload)
            self._data = payload

    def mark_error(self, instance_id: str, worker_id: str, error: str) -> None:
        done_at = _utc_now()
        with self._lock():
            payload = self._read_unlocked()
            task = _require_task(payload, instance_id)
            task["status"] = "error"
            task["worker"] = worker_id
            task["error"] = error
            task["done_at"] = done_at
            self._write_unlocked(payload)
            self._data = payload

    def unclaimed_count(self) -> int:
        payload = self._read_current()
        self._data = payload
        return sum(1 for task in payload["tasks"].values() if task.get("status") == "pending")

    def all_done(self) -> bool:
        payload = self._read_current()
        self._data = payload
        return not any(task.get("status") in {"pending", "claimed"} for task in payload["tasks"].values())

    def done_task_ids(self) -> set[str]:
        payload = self._read_current()
        self._data = payload
        return {
            instance_id
            for instance_id, task in payload["tasks"].items()
            if task.get("status") == "done"
        }

    def summary(self) -> dict[str, int]:
        payload = self._read_current()
        self._data = payload
        counts = {
            "total_tasks": int(payload.get("total_tasks", len(payload.get("tasks", {})))),
            "pending": 0,
            "claimed": 0,
            "done": 0,
        }
        for task in payload["tasks"].values():
            status = str(task.get("status", "pending"))
            counts[status] = counts.get(status, 0) + 1
        return counts

    def next_worker_id(self) -> str:
        payload = self._read_current()
        self._data = payload
        return self._next_worker_id_from_payload(payload)

    def reserve_specific_worker_ids(self, worker_ids: list[str]) -> list[str]:
        if not worker_ids:
            return []

        with self._lock():
            payload = self._read_unlocked()
            reserved = payload.setdefault("reserved_workers", [])
            for worker_id in worker_ids:
                if worker_id not in reserved:
                    reserved.append(worker_id)
            self._write_unlocked(payload)
            self._data = payload
        return worker_ids

    def reserve_worker_ids(self, count: int) -> list[str]:
        if count < 1:
            return []

        with self._lock():
            payload = self._read_unlocked()
            reserved = payload.setdefault("reserved_workers", [])
            allocated: list[str] = []
            for _ in range(count):
                worker_id = self._next_worker_id_from_payload(payload)
                reserved.append(worker_id)
                allocated.append(worker_id)
            self._write_unlocked(payload)
            self._data = payload
        return allocated

    def _build_payload(self, tasks: list[str]) -> dict[str, Any]:
        ordered_tasks: dict[str, dict[str, str]] = {}
        for instance_id in tasks:
            ordered_tasks.setdefault(instance_id, {"status": "pending"})
        return {
            "version": 1,
            "created_at": _utc_now(),
            "total_tasks": len(ordered_tasks),
            "reserved_workers": [],
            "tasks": ordered_tasks,
        }

    def _read_current(self) -> dict[str, Any]:
        with self._lock():
            return self._read_unlocked()

    def _read_unlocked(self) -> dict[str, Any]:
        if not self.path.exists():
            raise FileNotFoundError(f"Manifest not found: {self.path}")
        data = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"Manifest at {self.path} must contain a JSON object")
        tasks = data.get("tasks")
        if not isinstance(tasks, dict):
            raise ValueError(f"Manifest at {self.path} is missing a tasks map")
        return data

    def _write_unlocked(self, payload: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.path.parent / f"{self.path.name}.{os.getpid()}.tmp"
        tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=False), encoding="utf-8")
        tmp_path.replace(self.path)

    def _lock(self) -> _ManifestLock:
        return _ManifestLock(self.lock_path)

    def _next_worker_id_from_payload(self, payload: dict[str, Any]) -> str:
        seen: set[int] = set()
        for worker in payload.get("reserved_workers", []):
            if isinstance(worker, str) and worker.startswith("worker-"):
                suffix = worker.removeprefix("worker-")
                if suffix.isdigit():
                    seen.add(int(suffix))
        for task in payload["tasks"].values():
            worker = task.get("worker")
            if not isinstance(worker, str) or not worker.startswith("worker-"):
                continue
            suffix = worker.removeprefix("worker-")
            if suffix.isdigit():
                seen.add(int(suffix))
        return f"worker-{max(seen, default=-1) + 1}"


class _ManifestLock:
    def __init__(self, path: Path):
        self.path = path
        self._handle = None

    def __enter__(self) -> "_ManifestLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = self.path.open("a+", encoding="utf-8")
        fcntl.flock(self._handle.fileno(), fcntl.LOCK_EX)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        assert self._handle is not None
        fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
        self._handle.close()
        self._handle = None


def _require_task(payload: dict[str, Any], instance_id: str) -> dict[str, Any]:
    task = payload.get("tasks", {}).get(instance_id)
    if not isinstance(task, dict):
        raise KeyError(f"Unknown manifest task: {instance_id}")
    return task


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
