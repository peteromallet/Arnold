from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from agentbox.config import AgentBoxConfig
from agentbox.operations import (
    AGENTBOX_HOST_OPERATION_TYPE,
    AgentBoxOperationError,
    create_agentbox_operation,
    ensure_agentbox_operation,
    ensure_agentbox_operation_type,
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


def test_create_agentbox_operation_accepts_registered_adapter_operation_type(
    tmp_path: Path,
) -> None:
    config = AgentBoxConfig(workspace_root=tmp_path / "workspace")

    created = create_agentbox_operation(
        config,
        "chain",
        operation_type="megaplan_chain",
        command=("megaplan", "chain", "start", "spec.yaml"),
        repo_names=("app",),
        launch_intent="chain_local",
        launch_state="inspecting",
    )

    assert created.operation_type == "megaplan_chain"
    assert created.operation_dir == str(config.runs_root / "chain")
    assert created.metadata == {
        "command": ["megaplan", "chain", "start", "spec.yaml"],
        "repo_names": ["app"],
        "run_dir": str(config.runs_root / "chain"),
        "launch_intent": "chain_local",
        "launch_state": "inspecting",
    }
    assert load_agentbox_operation(
        config,
        "chain",
        operation_types=("megaplan_chain",),
    ) == created


def test_create_agentbox_operation_rejects_unregistered_operation_type(
    tmp_path: Path,
) -> None:
    config = AgentBoxConfig(workspace_root=tmp_path / "workspace")

    with pytest.raises(AgentBoxOperationError, match="not managed by AgentBox"):
        create_agentbox_operation(
            config,
            "foreign",
            operation_type="foreign",
            command="echo no",
        )


def test_load_and_list_return_agentbox_managed_operations(tmp_path: Path) -> None:
    config = AgentBoxConfig(workspace_root=tmp_path / "workspace")
    store = open_operation_store(config)
    other = store.create_operation_run(OperationRun(id="foreign", operation_type="other"))
    first = create_agentbox_operation(config, "a", command="echo a")
    chain = store.create_operation_run(OperationRun(id="chain", operation_type="megaplan_chain"))
    second = create_agentbox_operation(config, "b", command="echo b")

    assert list_agentbox_operations(config) == (first, second, chain)
    assert load_agentbox_operation(config, "a") == first
    assert load_agentbox_operation(config, "chain") == chain
    assert other.operation_type == "other"
    with pytest.raises(AgentBoxOperationError, match="AgentBox-managed operation type"):
        load_agentbox_operation(config, "foreign")


def test_load_and_list_can_be_scoped_to_explicit_registered_operation_types(
    tmp_path: Path,
) -> None:
    config = AgentBoxConfig(workspace_root=tmp_path / "workspace")
    store = open_operation_store(config)
    host = create_agentbox_operation(config, "host", command="echo host")
    chain = create_agentbox_operation(
        config,
        "chain",
        operation_type="megaplan_chain",
        command="echo chain",
    )
    store.create_operation_run(OperationRun(id="foreign", operation_type="other"))

    assert list_agentbox_operations(
        config,
        operation_types=("megaplan_chain",),
    ) == (chain,)
    assert list_agentbox_operations(
        config,
        operation_types=(AGENTBOX_HOST_OPERATION_TYPE,),
    ) == (host,)
    assert load_agentbox_operation(
        config,
        "chain",
        operation_types=("megaplan_chain",),
    ) == chain
    with pytest.raises(AgentBoxOperationError, match="AgentBox-managed operation type"):
        load_agentbox_operation(
            config,
            "host",
            operation_types=("megaplan_chain",),
        )
    with pytest.raises(AgentBoxOperationError, match="not managed by AgentBox"):
        list_agentbox_operations(config, operation_types=("other",))


def test_operation_type_validation_fails_closed_for_foreign_runs() -> None:
    assert ensure_agentbox_operation_type(AGENTBOX_HOST_OPERATION_TYPE) == "agentbox_host"
    with pytest.raises(AgentBoxOperationError, match="not managed by AgentBox"):
        ensure_agentbox_operation_type("other")
    with pytest.raises(AgentBoxOperationError, match="AgentBox-managed operation type"):
        ensure_agentbox_operation(
            OperationRun(id="foreign", operation_type="other"),
            operation_types=("megaplan_chain",),
        )


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
    source = (Path(__file__).resolve().parents[2] / "agentbox/operations.py").read_text(
        encoding="utf-8"
    )

    assert "megaplan" not in source.lower()
