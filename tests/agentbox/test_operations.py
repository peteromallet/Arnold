from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from agentbox.config import AgentBoxConfig
from agentbox.operations import (
    AGENTBOX_HOST_OPERATION_TYPE,
    AgentBoxOperationError,
    create_agentbox_operation,
    list_agentbox_operations,
    load_agentbox_operation,
    open_operation_store,
    update_agentbox_operation,
)
from arnold.runtime.durable_ops import (
    OperationLockConflict,
    OperationRun,
    OperationState,
)


def test_create_agentbox_operation_persists_host_launch_metadata(tmp_path: Path) -> None:
    config = AgentBoxConfig(workspace_root=tmp_path / "workspace")

    created = create_agentbox_operation(
        config,
        "op-1",
        command=("python", "-m", "agentbox_worker"),
        repo_names=("app", "infra"),
        launch_intent="test-launch",
        launch_state="prepared",
        idempotency_key="idem-op-1",
        max_attempts=3,
        metadata={"requested_by": "test"},
    )
    reopened = open_operation_store(config).load_operation_run("op-1")

    assert created.operation_type == AGENTBOX_HOST_OPERATION_TYPE
    assert created.operation_dir == str(config.runs_root / "op-1")
    assert reopened == created
    assert reopened.retry.max_attempts == 3
    assert reopened.idempotency_key == "idem-op-1"
    assert reopened.metadata == {
        "command": ["python", "-m", "agentbox_worker"],
        "repo_names": ["app", "infra"],
        "requested_by": "test",
        "run_dir": str(config.runs_root / "op-1"),
        "launch_intent": "test-launch",
        "launch_state": "prepared",
    }


def test_load_and_list_only_return_agentbox_host_operations(tmp_path: Path) -> None:
    config = AgentBoxConfig(workspace_root=tmp_path / "workspace")
    store = open_operation_store(config)
    other = store.create_operation_run(OperationRun(id="foreign", operation_type="other"))
    first = create_agentbox_operation(config, "a", command="echo a")
    second = create_agentbox_operation(config, "b", command="echo b")

    assert list_agentbox_operations(config) == (first, second)
    assert load_agentbox_operation(config, "a") == first
    assert other.operation_type == "other"
    with pytest.raises(AgentBoxOperationError, match="expected 'agentbox_host'"):
        load_agentbox_operation(config, "foreign")


def test_update_agentbox_operation_merges_metadata_and_transitions_state(tmp_path: Path) -> None:
    config = AgentBoxConfig(workspace_root=tmp_path / "workspace")
    created = create_agentbox_operation(
        config,
        "op",
        command="sleep 10",
        repo_names=("app",),
        launch_state="prepared",
    )

    updated = update_agentbox_operation(
        config,
        "op",
        metadata={"session_name": "agentbox-op"},
        launch_state="running",
        state=OperationState.RUNNING,
        expected_lock_version=created.lock_version,
    )
    reopened = load_agentbox_operation(config, "op")

    assert updated.lock_version == created.lock_version + 1
    assert reopened == updated
    assert updated.state is OperationState.RUNNING
    assert updated.started_at is not None
    assert updated.metadata["command"] == "sleep 10"
    assert updated.metadata["repo_names"] == ["app"]
    assert updated.metadata["launch_state"] == "running"
    assert updated.metadata["session_name"] == "agentbox-op"


def test_update_agentbox_operation_rejects_stale_lock_version(tmp_path: Path) -> None:
    config = AgentBoxConfig(workspace_root=tmp_path / "workspace")
    created = create_agentbox_operation(config, "op", command="echo hi")
    update_agentbox_operation(
        config,
        "op",
        metadata={"first": True},
        expected_lock_version=created.lock_version,
    )

    with pytest.raises(OperationLockConflict):
        update_agentbox_operation(
            config,
            "op",
            metadata={"stale": True},
            expected_lock_version=created.lock_version,
        )


def test_update_agentbox_operation_rejects_foreign_operation(tmp_path: Path) -> None:
    config = AgentBoxConfig(workspace_root=tmp_path / "workspace")
    store = open_operation_store(config)
    foreign = store.create_operation_run(OperationRun(id="foreign", operation_type="other"))

    with pytest.raises(AgentBoxOperationError):
        update_agentbox_operation(config, foreign.id, metadata={"bad": True})


def test_agentbox_operations_module_has_no_megaplan_imports() -> None:
    source = Path("agentbox/operations.py").read_text(encoding="utf-8")

    assert "megaplan" not in source.lower()
