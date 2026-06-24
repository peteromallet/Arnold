from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest

from arnold.runtime.durable_ops import FileBackedDurableOpsStore, OperationState
from agentbox.config import AgentBoxConfig
from agentbox.guardian.handlers import (
    MEGAPLAN_CHAIN_OPERATION_TYPE,
    GuardianHandler,
    GuardianHandlerRegistry,
)
from agentbox.guardian.model import (
    GuardianInspectionResult,
    GuardianMaterialTransition,
    GuardianOutcome,
)
from agentbox.guardian.scheduler import ensure_guardian_tasks
from agentbox.guardian.state import GuardianStateStore
from agentbox.guardian.worker import GuardianWorker
from agentbox.operations import create_agentbox_operation, update_agentbox_operation


@dataclass
class FakeHandler:
    operation_type: str
    inspect_result: GuardianInspectionResult
    inspect_delay: float = 0.0
    resume_delay: float = 0.0
    resume_result: Any = None
    inspect_calls: list[str] = field(default_factory=list)
    resume_calls: list[str] = field(default_factory=list)

    async def inspect(self, config: AgentBoxConfig, operation_id: str) -> GuardianInspectionResult:
        self.inspect_calls.append(operation_id)
        if self.inspect_delay:
            await asyncio.sleep(self.inspect_delay)
        result = self.inspect_result
        if result.operation_id is None:
            return GuardianInspectionResult(
                operation_id=operation_id,
                outcome=result.outcome,
                material_transition=result.material_transition,
                summary=result.summary,
            )
        return result

    async def resume(self, config: AgentBoxConfig, operation_id: str) -> Any:
        self.resume_calls.append(operation_id)
        if self.resume_delay:
            await asyncio.sleep(self.resume_delay)
        if isinstance(self.resume_result, Exception):
            raise self.resume_result
        return self.resume_result or SimpleNamespace(id=operation_id)

    def notification_summary(self, result: GuardianInspectionResult) -> str:
        return result.summary


def _noop_result(operation_id: str | None = None) -> GuardianInspectionResult:
    return GuardianInspectionResult(
        operation_id=operation_id,
        outcome=GuardianOutcome.OK,
        material_transition=GuardianMaterialTransition.NONE,
        summary="ok",
    )


def _completed_result(operation_id: str | None = None) -> GuardianInspectionResult:
    return GuardianInspectionResult(
        operation_id=operation_id,
        outcome=GuardianOutcome.OK,
        material_transition=GuardianMaterialTransition.COMPLETED,
        summary="completed",
    )


def _stalled_result(operation_id: str | None = None) -> GuardianInspectionResult:
    return GuardianInspectionResult(
        operation_id=operation_id,
        outcome=GuardianOutcome.RETRY,
        material_transition=GuardianMaterialTransition.STALLED,
        summary="stalled",
    )


def test_worker_runs_due_guardian_tasks_and_supervises_operations(tmp_path) -> None:
    config = AgentBoxConfig(workspace_root=tmp_path / "agentbox")
    store = FileBackedDurableOpsStore(config.ops_store_root)
    now = datetime(2026, 1, 1, tzinfo=UTC)
    ensure_guardian_tasks(config, now)

    create_agentbox_operation(
        config,
        "chain-1",
        operation_type=MEGAPLAN_CHAIN_OPERATION_TYPE,
        command=("fake",),
    )
    update_agentbox_operation(config, "chain-1", state=OperationState.RUNNING)

    handler = FakeHandler(MEGAPLAN_CHAIN_OPERATION_TYPE, _completed_result())
    registry = GuardianHandlerRegistry({MEGAPLAN_CHAIN_OPERATION_TYPE: handler})
    worker = GuardianWorker(
        config=config,
        operation_store=store,
        handler_registry=registry,
        lease_seconds=2,
    )

    result = asyncio.run(worker.run_due_once(now=now))

    assert result["tasks_run"] >= 1
    assert result["operations_supervised"] == 1
    assert handler.inspect_calls == ["chain-1"]


def test_worker_timeout_does_not_block_next_operation(tmp_path) -> None:
    config = AgentBoxConfig(workspace_root=tmp_path / "agentbox")
    store = FileBackedDurableOpsStore(config.ops_store_root)
    now = datetime(2026, 1, 1, tzinfo=UTC)
    ensure_guardian_tasks(config, now)

    create_agentbox_operation(
        config,
        "chain-slow",
        operation_type=MEGAPLAN_CHAIN_OPERATION_TYPE,
        command=("fake",),
    )
    update_agentbox_operation(config, "chain-slow", state=OperationState.RUNNING)
    create_agentbox_operation(
        config,
        "chain-fast",
        operation_type=MEGAPLAN_CHAIN_OPERATION_TYPE,
        command=("fake",),
    )
    update_agentbox_operation(config, "chain-fast", state=OperationState.RUNNING)

    class RoutingHandler:
        operation_type = MEGAPLAN_CHAIN_OPERATION_TYPE
        calls: list[str] = []

        async def inspect(self, config: AgentBoxConfig, operation_id: str) -> GuardianInspectionResult:
            self.calls.append(operation_id)
            if operation_id == "chain-slow":
                await asyncio.sleep(5)
            return _completed_result(operation_id)

        async def resume(self, config: AgentBoxConfig, operation_id: str) -> Any:
            return SimpleNamespace(id=operation_id)

        def notification_summary(self, result: GuardianInspectionResult) -> str:
            return result.summary

    handler = RoutingHandler()
    registry = GuardianHandlerRegistry({MEGAPLAN_CHAIN_OPERATION_TYPE: handler})
    worker = GuardianWorker(
        config=config,
        operation_store=store,
        handler_registry=registry,
        inspection_timeout_seconds=0.1,
        lease_seconds=2,
    )

    result = asyncio.run(worker.run_due_once(now=now))

    assert result["operations_supervised"] == 2
    assert "chain-fast" in handler.calls
    assert "chain-slow" in handler.calls


def test_worker_skips_unsupported_operation_types(tmp_path) -> None:
    config = AgentBoxConfig(workspace_root=tmp_path / "agentbox")
    store = FileBackedDurableOpsStore(config.ops_store_root)
    now = datetime(2026, 1, 1, tzinfo=UTC)
    ensure_guardian_tasks(config, now)

    create_agentbox_operation(
        config,
        "host-1",
        operation_type="agentbox_host",
        command=("echo",),
    )
    create_agentbox_operation(
        config,
        "chain-1",
        operation_type=MEGAPLAN_CHAIN_OPERATION_TYPE,
        command=("fake",),
    )
    update_agentbox_operation(config, "chain-1", state=OperationState.RUNNING)

    handler = FakeHandler(MEGAPLAN_CHAIN_OPERATION_TYPE, _completed_result())
    registry = GuardianHandlerRegistry({MEGAPLAN_CHAIN_OPERATION_TYPE: handler})
    worker = GuardianWorker(
        config=config,
        operation_store=store,
        handler_registry=registry,
    )
    result = asyncio.run(worker.run_due_once(now=now))

    assert result["operations_supervised"] == 1
    assert handler.inspect_calls == ["chain-1"]
    assert "host-1" not in handler.inspect_calls


def test_worker_stops_resuming_after_two_attempts(tmp_path) -> None:
    config = AgentBoxConfig(workspace_root=tmp_path / "agentbox")
    store = FileBackedDurableOpsStore(config.ops_store_root)
    state = GuardianStateStore(config)
    now = datetime(2026, 1, 1, tzinfo=UTC)
    ensure_guardian_tasks(config, now)

    create_agentbox_operation(
        config,
        "chain-stuck",
        operation_type=MEGAPLAN_CHAIN_OPERATION_TYPE,
        command=("fake",),
    )
    update_agentbox_operation(config, "chain-stuck", state=OperationState.RUNNING)

    handler = FakeHandler(MEGAPLAN_CHAIN_OPERATION_TYPE, _stalled_result())
    registry = GuardianHandlerRegistry({MEGAPLAN_CHAIN_OPERATION_TYPE: handler})
    worker = GuardianWorker(
        config=config,
        operation_store=store,
        handler_registry=registry,
        state_store=state,
        lease_seconds=2,
    )

    for index in range(3):
        asyncio.run(worker.run_due_once(now=now + timedelta(seconds=index * 100)))

    assert len(handler.resume_calls) == 2
    run = store.load_operation_run("chain-stuck")
    assert run.state is OperationState.FAILED


def test_worker_records_repeated_inspection_failures_then_marks_failed(tmp_path) -> None:
    config = AgentBoxConfig(workspace_root=tmp_path / "agentbox")
    store = FileBackedDurableOpsStore(config.ops_store_root)
    state = GuardianStateStore(config)
    now = datetime(2026, 1, 1, tzinfo=UTC)
    ensure_guardian_tasks(config, now)

    create_agentbox_operation(
        config,
        "chain-flaky",
        operation_type=MEGAPLAN_CHAIN_OPERATION_TYPE,
        command=("fake",),
    )
    update_agentbox_operation(config, "chain-flaky", state=OperationState.RUNNING)

    class FailingHandler:
        operation_type = MEGAPLAN_CHAIN_OPERATION_TYPE

        async def inspect(self, config: AgentBoxConfig, operation_id: str) -> GuardianInspectionResult:
            raise RuntimeError("inspection error")

        async def resume(self, config: AgentBoxConfig, operation_id: str) -> Any:
            return SimpleNamespace(id=operation_id)

        def notification_summary(self, result: GuardianInspectionResult) -> str:
            return result.summary

    registry = GuardianHandlerRegistry({MEGAPLAN_CHAIN_OPERATION_TYPE: FailingHandler()})
    worker = GuardianWorker(
        config=config,
        operation_store=store,
        handler_registry=registry,
        state_store=state,
        lease_seconds=2,
    )

    for index in range(3):
        asyncio.run(worker.run_due_once(now=now + timedelta(seconds=index * 100)))

    run = store.load_operation_run("chain-flaky")
    assert run.state is OperationState.FAILED


def test_worker_heartbeats_lease_during_batch_processing(tmp_path) -> None:
    config = AgentBoxConfig(workspace_root=tmp_path / "agentbox")
    store = FileBackedDurableOpsStore(config.ops_store_root)
    now = datetime(2026, 1, 1, tzinfo=UTC)
    ensure_guardian_tasks(config, now)

    class SlowHandler:
        operation_type = MEGAPLAN_CHAIN_OPERATION_TYPE
        calls: list[str] = []

        async def inspect(self, config: AgentBoxConfig, operation_id: str) -> GuardianInspectionResult:
            self.calls.append(operation_id)
            await asyncio.sleep(0.4)
            return _completed_result(operation_id)

        async def resume(self, config: AgentBoxConfig, operation_id: str) -> Any:
            return SimpleNamespace(id=operation_id)

        def notification_summary(self, result: GuardianInspectionResult) -> str:
            return result.summary

    create_agentbox_operation(
        config,
        "chain-slow",
        operation_type=MEGAPLAN_CHAIN_OPERATION_TYPE,
        command=("fake",),
    )
    update_agentbox_operation(config, "chain-slow", state=OperationState.RUNNING)

    registry = GuardianHandlerRegistry({MEGAPLAN_CHAIN_OPERATION_TYPE: SlowHandler()})
    worker = GuardianWorker(
        config=config,
        operation_store=store,
        handler_registry=registry,
        lease_seconds=2,
        heartbeat_interval_seconds=0.2,
    )

    asyncio.run(worker.run_due_once(now=now))

    task = store.list_scheduled_tasks()[0]
    if task.lease_expires_at is not None:
        assert task.lease_expires_at > now + timedelta(seconds=1)


def test_worker_dispatches_liveness_and_deep_supervision_tasks(tmp_path) -> None:
    config = AgentBoxConfig(workspace_root=tmp_path / "agentbox")
    store = FileBackedDurableOpsStore(config.ops_store_root)
    now = datetime(2026, 1, 1, tzinfo=UTC)
    ensure_guardian_tasks(config, now)

    worker = GuardianWorker(
        config=config,
        operation_store=store,
        lease_seconds=2,
    )

    result = asyncio.run(worker.run_due_once(now=now))

    assert result["tasks_run"] == 4
    task_types = {task.task_type for task in store.list_scheduled_tasks()}
    assert "guardian.liveness" in task_types
    assert "guardian.deep_supervision" in task_types
    assert "guardian.briefing" in task_types
    assert "guardian.reminders" in task_types
