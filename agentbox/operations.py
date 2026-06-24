"""AgentBox durable operation helpers."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from arnold.runtime.durable_ops import (
    FileBackedDurableOpsStore,
    OperationRun,
    OperationState,
    RetryMetadata,
)

from agentbox.config import AgentBoxConfig


AGENTBOX_HOST_OPERATION_TYPE = "agentbox_host"


class AgentBoxOperationError(ValueError):
    """Raised when a durable operation is not an AgentBox host operation."""


def open_operation_store(config: AgentBoxConfig) -> FileBackedDurableOpsStore:
    """Open the AgentBox durable operation store for ``config``."""

    return FileBackedDurableOpsStore(config.ops_store_root)


def operation_run_dir(config: AgentBoxConfig, operation_id: str) -> Path:
    """Return the run directory path reserved for ``operation_id``."""

    return config.runs_root / operation_id


def create_agentbox_operation(
    config: AgentBoxConfig,
    operation_id: str,
    *,
    command: Sequence[str] | str,
    repo_names: Iterable[str] = (),
    launch_intent: str = "host_local",
    launch_state: str = "created",
    parent_operation_id: str | None = None,
    idempotency_key: str | None = None,
    max_attempts: int = 1,
    metadata: Mapping[str, Any] | None = None,
) -> OperationRun:
    """Create an AgentBox host operation run with launch metadata."""

    launch_metadata = build_launch_metadata(
        config,
        operation_id,
        command=command,
        repo_names=repo_names,
        launch_intent=launch_intent,
        launch_state=launch_state,
        metadata=metadata,
    )
    run = OperationRun(
        id=operation_id,
        operation_type=AGENTBOX_HOST_OPERATION_TYPE,
        parent_operation_id=parent_operation_id,
        operation_dir=str(operation_run_dir(config, operation_id)),
        retry=RetryMetadata(max_attempts=max_attempts),
        idempotency_key=idempotency_key,
        metadata=launch_metadata,
    )
    return open_operation_store(config).create_operation_run(run)


def load_agentbox_operation(config: AgentBoxConfig, operation_id: str) -> OperationRun:
    """Load one AgentBox host operation run and reject other operation types."""

    run = open_operation_store(config).load_operation_run(operation_id)
    return ensure_agentbox_operation(run)


def list_agentbox_operations(config: AgentBoxConfig) -> tuple[OperationRun, ...]:
    """List persisted AgentBox host operation runs ordered by operation id."""

    return tuple(
        run
        for run in open_operation_store(config).list_operation_runs()
        if run.operation_type == AGENTBOX_HOST_OPERATION_TYPE
    )


def update_agentbox_operation(
    config: AgentBoxConfig,
    operation_id: str,
    *,
    metadata: Mapping[str, Any] | None = None,
    launch_state: str | None = None,
    state: OperationState | str | None = None,
    expected_lock_version: int | None = None,
) -> OperationRun:
    """Merge metadata and optionally transition an AgentBox host operation."""

    store = open_operation_store(config)
    current = ensure_agentbox_operation(store.load_operation_run(operation_id))
    if expected_lock_version is None:
        expected_lock_version = current.lock_version

    updated_metadata = dict(current.metadata)
    if metadata:
        updated_metadata.update(metadata)
    if launch_state is not None:
        updated_metadata["launch_state"] = launch_state

    updated = replace(current, metadata=updated_metadata)
    if state is not None and OperationState(state) != current.state:
        updated = updated.transition_to(OperationState(state))

    return ensure_agentbox_operation(
        store.update_operation_run(
            updated,
            expected_lock_version=expected_lock_version,
        )
    )


def build_launch_metadata(
    config: AgentBoxConfig,
    operation_id: str,
    *,
    command: Sequence[str] | str,
    repo_names: Iterable[str],
    launch_intent: str,
    launch_state: str,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build JSON-ready launch metadata for an AgentBox host run."""

    launch_metadata = dict(metadata or {})
    launch_metadata.update(
        {
            "command": _command_to_metadata(command),
            "repo_names": list(repo_names),
            "run_dir": str(operation_run_dir(config, operation_id)),
            "launch_intent": launch_intent,
            "launch_state": launch_state,
        }
    )
    return launch_metadata


def ensure_agentbox_operation(run: OperationRun) -> OperationRun:
    """Return ``run`` when it belongs to AgentBox, otherwise raise."""

    if run.operation_type != AGENTBOX_HOST_OPERATION_TYPE:
        raise AgentBoxOperationError(
            f"operation {run.id!r} has type {run.operation_type!r}, "
            f"expected {AGENTBOX_HOST_OPERATION_TYPE!r}"
        )
    return run


def _command_to_metadata(command: Sequence[str] | str) -> str | list[str]:
    if isinstance(command, str):
        return command
    return list(command)


__all__ = [
    "AGENTBOX_HOST_OPERATION_TYPE",
    "AgentBoxOperationError",
    "build_launch_metadata",
    "create_agentbox_operation",
    "ensure_agentbox_operation",
    "list_agentbox_operations",
    "load_agentbox_operation",
    "open_operation_store",
    "operation_run_dir",
    "update_agentbox_operation",
]
