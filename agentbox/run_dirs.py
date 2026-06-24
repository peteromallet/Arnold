"""AgentBox operation run directory helpers."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

from arnold.runtime.durable_ops import (
    ResourceType,
    TypedResource,
    TypedResourceAlreadyExists,
)

from agentbox.config import AgentBoxConfig
from agentbox.operations import open_operation_store, operation_run_dir


EVENTS_FILENAME = "events.ndjson"
METADATA_FILENAME = "metadata.json"
STDOUT_FILENAME = "stdout.log"
STDERR_FILENAME = "stderr.log"


@dataclass(frozen=True)
class RunDirPaths:
    """Filesystem paths owned by one AgentBox operation run."""

    operation_id: str
    root: Path
    events_path: Path
    stdout_path: Path
    stderr_path: Path
    metadata_path: Path


def run_dir_paths(config: AgentBoxConfig, operation_id: str) -> RunDirPaths:
    """Return conventional paths under ``runs_root/<operation_id>``."""

    root = operation_run_dir(config, operation_id)
    return RunDirPaths(
        operation_id=operation_id,
        root=root,
        events_path=root / EVENTS_FILENAME,
        stdout_path=root / STDOUT_FILENAME,
        stderr_path=root / STDERR_FILENAME,
        metadata_path=root / METADATA_FILENAME,
    )


def ensure_run_dir(
    config: AgentBoxConfig,
    operation_id: str,
    *,
    metadata: Mapping[str, Any] | None = None,
) -> RunDirPaths:
    """Create the run directory, logs, journal, and metadata file if needed."""

    paths = run_dir_paths(config, operation_id)
    paths.root.mkdir(parents=True, exist_ok=True)
    for path in (paths.events_path, paths.stdout_path, paths.stderr_path):
        path.touch(exist_ok=True)
    if metadata is not None or not paths.metadata_path.exists():
        write_metadata(paths, metadata or {})
    return paths


def append_event(
    paths: RunDirPaths,
    event_type: str,
    *,
    payload: Mapping[str, Any] | None = None,
    event_id: str | None = None,
) -> dict[str, Any]:
    """Append one JSON line to ``events.ndjson`` and return the stored record."""

    if not event_type:
        raise ValueError("event_type is required")
    record = {
        "id": event_id or str(uuid4()),
        "operation_id": paths.operation_id,
        "event_type": event_type,
        "payload": dict(payload or {}),
    }
    paths.events_path.parent.mkdir(parents=True, exist_ok=True)
    with paths.events_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
    return record


def read_metadata(paths: RunDirPaths) -> dict[str, Any]:
    """Read ``metadata.json`` as a JSON object."""

    if not paths.metadata_path.exists():
        return {}
    raw = json.loads(paths.metadata_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("metadata.json must contain a JSON object")
    return raw


def write_metadata(paths: RunDirPaths, metadata: Mapping[str, Any]) -> dict[str, Any]:
    """Replace ``metadata.json`` with a stable JSON object."""

    paths.root.mkdir(parents=True, exist_ok=True)
    data = dict(metadata)
    tmp_path = paths.metadata_path.with_suffix(".json.tmp")
    tmp_path.write_text(
        json.dumps(data, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp_path.replace(paths.metadata_path)
    return data


def append_stdout(paths: RunDirPaths, text: str) -> None:
    """Append text to ``stdout.log``."""

    _append_text(paths.stdout_path, text)


def append_stderr(paths: RunDirPaths, text: str) -> None:
    """Append text to ``stderr.log``."""

    _append_text(paths.stderr_path, text)


def record_log_resources(
    config: AgentBoxConfig,
    operation_id: str,
) -> tuple[TypedResource, TypedResource]:
    """Record stdout and stderr log files as durable LOG typed resources."""

    paths = ensure_run_dir(config, operation_id)
    store = open_operation_store(config)
    return (
        _create_log_resource(
            store,
            operation_id=operation_id,
            stream="stdout",
            path=paths.stdout_path,
            root=paths.root,
        ),
        _create_log_resource(
            store,
            operation_id=operation_id,
            stream="stderr",
            path=paths.stderr_path,
            root=paths.root,
        ),
    )


def _create_log_resource(
    store: Any,
    *,
    operation_id: str,
    stream: str,
    path: Path,
    root: Path,
) -> TypedResource:
    resource_id = f"{operation_id}:{stream}-log"
    resource = TypedResource(
        id=resource_id,
        operation_id=operation_id,
        resource_type=ResourceType.LOG,
        name=f"{stream}.log",
        details={
            "stream": stream,
            "path": str(path),
            "relative_path": path.relative_to(root).as_posix(),
        },
    )
    try:
        return store.create_typed_resource(resource)
    except TypedResourceAlreadyExists:
        for existing in store.list_typed_resources(operation_id):
            if existing.id == resource_id:
                return existing
        raise


def _append_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(text)


__all__ = [
    "EVENTS_FILENAME",
    "METADATA_FILENAME",
    "STDERR_FILENAME",
    "STDOUT_FILENAME",
    "RunDirPaths",
    "append_event",
    "append_stderr",
    "append_stdout",
    "ensure_run_dir",
    "read_metadata",
    "record_log_resources",
    "run_dir_paths",
    "write_metadata",
]
