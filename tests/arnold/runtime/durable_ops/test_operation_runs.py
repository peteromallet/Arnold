from __future__ import annotations

import ast
from dataclasses import fields
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import get_type_hints

import pytest

from arnold.runtime.durable_ops import (
    ApprovalLink,
    DurableOpsStore,
    FileBackedDurableOpsStore,
    InvalidOperationTransition,
    OperationAlreadyExists,
    OperationEvent,
    OperationHandler,
    OperationLockConflict,
    OperationNotFound,
    OperationRun,
    OperationState,
    ResourceType,
    RetryMetadata,
    ScheduledTask,
    ScheduledTaskAlreadyExists,
    ScheduledTaskLeaseConflict,
    ScheduledTaskLeaseTokenMismatch,
    ScheduledTaskNotFound,
    ScheduledTaskState,
    TypedResource,
    can_transition_operation,
    can_transition_scheduled_task,
    is_terminal_operation_state,
    is_terminal_scheduled_task_state,
)


FORBIDDEN_DURABLE_OPS_IMPORT_TOKENS = (
    "arnold_pipelines",
    "resident",
    "AgentBox",
    "Discord",
    "tmux",
    "systemd",
    "Hetzner",
)


class FakeOperationStore:
    def __init__(self) -> None:
        self._runs: dict[str, OperationRun] = {}
        self._resources: dict[str, TypedResource] = {}
        self._events: dict[str, OperationEvent] = {}
        self._tasks: dict[str, ScheduledTask] = {}

    def create_operation_run(self, run: OperationRun) -> OperationRun:
        if run.id in self._runs:
            raise OperationAlreadyExists(run.id)
        stored = replace(run, lock_version=0)
        self._runs[run.id] = stored
        return stored

    def load_operation_run(self, operation_id: str) -> OperationRun:
        try:
            return self._runs[operation_id]
        except KeyError as exc:
            raise OperationNotFound(operation_id) from exc

    def list_operation_runs(self) -> tuple[OperationRun, ...]:
        return tuple(self._runs[key] for key in sorted(self._runs))

    def update_operation_run(
        self,
        run: OperationRun,
        *,
        expected_lock_version: int,
    ) -> OperationRun:
        current = self.load_operation_run(run.id)
        if current.lock_version != expected_lock_version:
            raise OperationLockConflict(run.id)
        stored = replace(run, lock_version=current.lock_version + 1)
        self._runs[run.id] = stored
        return stored

    def create_typed_resource(self, resource: TypedResource) -> TypedResource:
        self.load_operation_run(resource.operation_id)
        self._resources[resource.id] = resource
        return resource

    def list_typed_resources(self, operation_id: str) -> tuple[TypedResource, ...]:
        return tuple(
            self._resources[key]
            for key in sorted(self._resources)
            if self._resources[key].operation_id == operation_id
        )

    def append_operation_event(self, event: OperationEvent) -> OperationEvent:
        self.load_operation_run(event.operation_id)
        sequence = (
            max(
                (
                    stored.sequence
                    for stored in self._events.values()
                    if stored.operation_id == event.operation_id
                ),
                default=0,
            )
            + 1
        )
        stored = replace(event, sequence=sequence)
        self._events[stored.id] = stored
        return stored

    def list_operation_events(self, operation_id: str) -> tuple[OperationEvent, ...]:
        return tuple(
            sorted(
                (
                    event
                    for event in self._events.values()
                    if event.operation_id == operation_id
                ),
                key=lambda event: event.sequence,
            )
        )

    def create_scheduled_task(self, task: ScheduledTask) -> ScheduledTask:
        if task.id in self._tasks:
            raise ScheduledTaskAlreadyExists(task.id)
        stored = replace(task, lock_version=0)
        self._tasks[stored.id] = stored
        return stored

    def load_scheduled_task(self, task_id: str) -> ScheduledTask:
        try:
            return self._tasks[task_id]
        except KeyError as exc:
            raise ScheduledTaskNotFound(task_id) from exc

    def list_scheduled_tasks(self) -> tuple[ScheduledTask, ...]:
        return tuple(self._tasks[key] for key in sorted(self._tasks))

    def claim_scheduled_task(
        self,
        task_id: str,
        *,
        lease_owner: str,
        lease_token: str,
        lease_seconds: int,
        now: datetime | None = None,
    ) -> ScheduledTask:
        task = self.load_scheduled_task(task_id)
        timestamp = now or datetime.now(UTC)
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
        self._tasks[stored.id] = stored
        return stored

    def complete_scheduled_task(
        self,
        task_id: str,
        *,
        lease_token: str,
        result: dict[str, object] | None = None,
        now: datetime | None = None,
    ) -> ScheduledTask:
        task = self.load_scheduled_task(task_id)
        try:
            completed = task.complete(
                lease_token=lease_token,
                result=result,
                now=now,
            )
        except ValueError as exc:
            raise ScheduledTaskLeaseTokenMismatch(task_id) from exc
        stored = replace(completed, lock_version=task.lock_version + 1)
        self._tasks[stored.id] = stored
        return stored

    def fail_scheduled_task(
        self,
        task_id: str,
        *,
        lease_token: str,
        result: dict[str, object],
        now: datetime | None = None,
    ) -> ScheduledTask:
        task = self.load_scheduled_task(task_id)
        try:
            failed = task.fail(
                lease_token=lease_token,
                result=result,
                now=now,
            )
        except ValueError as exc:
            raise ScheduledTaskLeaseTokenMismatch(task_id) from exc
        stored = replace(failed, lock_version=task.lock_version + 1)
        self._tasks[stored.id] = stored
        return stored

    def cancel_scheduled_task(
        self,
        task_id: str,
        *,
        now: datetime | None = None,
    ) -> ScheduledTask:
        task = self.load_scheduled_task(task_id)
        cancelled = task.cancel(now=now)
        stored = replace(cancelled, lock_version=task.lock_version + 1)
        self._tasks[stored.id] = stored
        return stored


class SampleOperationHandler:
    def launch(self, run: OperationRun) -> OperationRun:
        return run.transition_to(OperationState.RUNNING)

    def tick(self, run: OperationRun) -> OperationRun:
        return run

    def resume(self, run: OperationRun) -> OperationRun:
        return run.transition_to(OperationState.RUNNING)

    def summarize(self, run: OperationRun) -> str:
        return f"{run.id}:{run.state.value}"

    def cleanup_descriptor(self, run: OperationRun) -> dict[str, object]:
        return {"operation_id": run.id, "state": run.state.value}


def test_fake_store_satisfies_operation_run_protocol_shape() -> None:
    assert isinstance(FakeOperationStore(), DurableOpsStore)
    protocol_names = {
        name for name in dir(DurableOpsStore) if not name.startswith("_")
    }
    assert protocol_names == {
        "append_operation_event",
        "cancel_scheduled_task",
        "claim_scheduled_task",
        "complete_scheduled_task",
        "create_operation_run",
        "create_scheduled_task",
        "create_typed_resource",
        "fail_scheduled_task",
        "list_operation_events",
        "list_operation_runs",
        "list_scheduled_tasks",
        "list_typed_resources",
        "load_operation_run",
        "load_scheduled_task",
        "update_operation_run",
    }

    resource_hints = get_type_hints(DurableOpsStore.create_typed_resource)
    event_hints = get_type_hints(DurableOpsStore.append_operation_event)
    create_task_hints = get_type_hints(DurableOpsStore.create_scheduled_task)
    claim_task_hints = get_type_hints(DurableOpsStore.claim_scheduled_task)
    complete_task_hints = get_type_hints(DurableOpsStore.complete_scheduled_task)
    fail_task_hints = get_type_hints(DurableOpsStore.fail_scheduled_task)
    assert resource_hints["resource"] is TypedResource
    assert resource_hints["return"] is TypedResource
    assert event_hints["event"] is OperationEvent
    assert event_hints["return"] is OperationEvent
    assert create_task_hints["task"] is ScheduledTask
    assert create_task_hints["return"] is ScheduledTask
    assert claim_task_hints["lease_token"] is str
    assert claim_task_hints["return"] is ScheduledTask
    assert complete_task_hints["lease_token"] is str
    assert complete_task_hints["return"] is ScheduledTask
    assert fail_task_hints["lease_token"] is str
    assert fail_task_hints["return"] is ScheduledTask


def test_approval_link_serialization_pairs_with_awaiting_approval() -> None:
    link = ApprovalLink(
        provider_label="resident",
        external_confirmation_request_id="confirmation-expiry-job-123",
    )
    run = OperationRun(
        id="approval",
        operation_type="protected_action",
        metadata={"approval": link.to_json()},
    )

    awaiting = run.transition_to(OperationState.AWAITING_APPROVAL)
    reloaded = ApprovalLink.from_json(dict(awaiting.metadata["approval"]))

    assert awaiting.state is OperationState.AWAITING_APPROVAL
    assert awaiting.started_at is None
    assert fields(ApprovalLink)[0].name == "provider_label"
    assert fields(ApprovalLink)[1].name == "external_confirmation_request_id"
    assert len(fields(ApprovalLink)) == 2
    assert link.to_json() == {
        "provider_label": "resident",
        "external_confirmation_request_id": "confirmation-expiry-job-123",
    }
    assert reloaded == link


def test_durable_ops_approval_and_handler_contracts_have_no_host_imports() -> None:
    durable_ops_dir = Path(__file__).parents[4] / "arnold" / "runtime" / "durable_ops"
    for path in sorted(durable_ops_dir.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported_modules = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        imported_modules.update(
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module is not None
        )
        for token in FORBIDDEN_DURABLE_OPS_IMPORT_TOKENS:
            assert not any(
                imported == token or imported.startswith(f"{token}.")
                for imported in imported_modules
            ), f"{path.name} should not import {token}"


def test_sample_operation_handler_satisfies_protocol_structurally() -> None:
    handler = SampleOperationHandler()
    run = OperationRun(id="handler", operation_type="sample")

    assert isinstance(handler, OperationHandler)
    assert handler.launch(run).state is OperationState.RUNNING
    assert handler.tick(run) == run
    resumed = handler.resume(run.transition_to(OperationState.AWAITING_APPROVAL))
    assert resumed.state is OperationState.RUNNING
    assert handler.summarize(run) == "handler:pending"
    assert handler.cleanup_descriptor(run) == {
        "operation_id": "handler",
        "state": "pending",
    }

    protocol_names = {
        name for name in dir(OperationHandler) if not name.startswith("_")
    }
    assert protocol_names == {
        "cleanup_descriptor",
        "launch",
        "resume",
        "summarize",
        "tick",
    }


def test_operation_run_model_shape_and_store_create_update_list_load() -> None:
    store = FakeOperationStore()
    parent = OperationRun(id="parent", operation_type="agentbox_host")
    child = OperationRun(
        id="child",
        operation_type="agentbox_host",
        parent_operation_id=parent.id,
        operation_dir="/tmp/operation-child",
        idempotency_key="idem-child",
        metadata={"purpose": "test"},
    )

    stored_parent = store.create_operation_run(parent)
    stored_child = store.create_operation_run(child)
    updated_child = store.update_operation_run(
        stored_child.transition_to(OperationState.RUNNING),
        expected_lock_version=stored_child.lock_version,
    )

    assert stored_parent.state is OperationState.PENDING
    assert updated_child.lock_version == 1
    assert updated_child.parent_operation_id == "parent"
    assert updated_child.operation_dir == "/tmp/operation-child"
    assert updated_child.idempotency_key == "idem-child"
    assert updated_child.started_at is not None
    assert store.load_operation_run("child") == updated_child
    assert store.list_operation_runs() == (updated_child, stored_parent)


def test_pending_can_transition_to_awaiting_approval_before_launch() -> None:
    run = OperationRun(id="approval", operation_type="protected_action")

    awaiting = run.transition_to(OperationState.AWAITING_APPROVAL)

    assert awaiting.state is OperationState.AWAITING_APPROVAL
    assert awaiting.started_at is None
    assert can_transition_operation(OperationState.AWAITING_APPROVAL, OperationState.RUNNING)


def test_invalid_operation_transition_is_rejected() -> None:
    run = OperationRun(id="invalid", operation_type="protected_action")

    with pytest.raises(InvalidOperationTransition):
        run.transition_to(OperationState.SUCCEEDED)


def test_terminal_operation_state_rejects_future_transitions() -> None:
    running = OperationRun(id="done", operation_type="protected_action").transition_to(
        OperationState.RUNNING
    )
    succeeded = running.transition_to(OperationState.SUCCEEDED)

    assert is_terminal_operation_state(succeeded.state)
    with pytest.raises(InvalidOperationTransition):
        succeeded.transition_to(OperationState.RUNNING)


def test_stale_lock_version_conflict_is_rejected() -> None:
    store = FakeOperationStore()
    created = store.create_operation_run(
        OperationRun(id="locked", operation_type="protected_action")
    )
    first_update = store.update_operation_run(
        created.transition_to(OperationState.RUNNING),
        expected_lock_version=created.lock_version,
    )

    with pytest.raises(OperationLockConflict):
        store.update_operation_run(
            replace(first_update, metadata={"stale": True}),
            expected_lock_version=created.lock_version,
        )


def test_file_backed_store_round_trips_operation_runs(tmp_path) -> None:
    store = FileBackedDurableOpsStore(tmp_path)
    run = OperationRun(
        id="persisted",
        operation_type="agentbox_host",
        parent_operation_id="parent",
        operation_dir="/tmp/persisted",
        retry=RetryMetadata(attempt=1, max_attempts=3, last_error="boot failed"),
        idempotency_key="idem-persisted",
        metadata={"nested": {"ok": True}, "count": 2},
    ).transition_to(OperationState.RUNNING)

    created = store.create_operation_run(run)
    updated = store.update_operation_run(
        replace(created, metadata={"nested": {"ok": False}, "count": 3}),
        expected_lock_version=created.lock_version,
    )
    reopened = FileBackedDurableOpsStore(tmp_path)

    assert created.lock_version == 0
    assert updated.lock_version == 1
    assert reopened.load_operation_run("persisted") == updated
    assert reopened.list_operation_runs() == (updated,)
    assert updated.state is OperationState.RUNNING
    assert updated.started_at is not None
    assert updated.retry.attempt == 1
    assert updated.retry.max_attempts == 3
    assert updated.retry.last_error == "boot failed"


def test_file_backed_store_orders_list_by_operation_id(tmp_path) -> None:
    store = FileBackedDurableOpsStore(tmp_path)
    second = store.create_operation_run(OperationRun(id="b", operation_type="host"))
    first = store.create_operation_run(OperationRun(id="a", operation_type="host"))

    assert store.list_operation_runs() == (first, second)


def test_file_backed_store_rejects_duplicate_and_missing_operations(tmp_path) -> None:
    store = FileBackedDurableOpsStore(tmp_path)
    run = OperationRun(id="unique", operation_type="host")
    store.create_operation_run(run)

    with pytest.raises(OperationAlreadyExists):
        store.create_operation_run(run)
    with pytest.raises(OperationNotFound):
        store.load_operation_run("missing")
    with pytest.raises(OperationNotFound):
        store.update_operation_run(
            OperationRun(id="missing", operation_type="host"),
            expected_lock_version=0,
        )


def test_file_backed_store_rejects_stale_lock_version(tmp_path) -> None:
    store = FileBackedDurableOpsStore(tmp_path)
    created = store.create_operation_run(OperationRun(id="locked", operation_type="host"))
    current = store.update_operation_run(
        created.transition_to(OperationState.RUNNING),
        expected_lock_version=created.lock_version,
    )

    with pytest.raises(OperationLockConflict):
        store.update_operation_run(
            replace(current, metadata={"stale": True}),
            expected_lock_version=created.lock_version,
        )


def test_file_backed_store_satisfies_operation_run_protocol_only(tmp_path) -> None:
    store = FileBackedDurableOpsStore(tmp_path)

    assert isinstance(store, DurableOpsStore)
    protocol_names = {
        name for name in dir(DurableOpsStore) if not name.startswith("_")
    }
    assert protocol_names == {
        "append_operation_event",
        "cancel_scheduled_task",
        "claim_scheduled_task",
        "complete_scheduled_task",
        "create_operation_run",
        "create_scheduled_task",
        "create_typed_resource",
        "fail_scheduled_task",
        "list_operation_events",
        "list_operation_runs",
        "list_scheduled_tasks",
        "list_typed_resources",
        "load_operation_run",
        "load_scheduled_task",
        "update_operation_run",
    }


def test_typed_resource_requires_stable_resource_type_tag_and_json_details() -> None:
    resource = TypedResource(
        id="worktree",
        operation_id="op",
        resource_type="git_worktree",
        name="primary checkout",
        details={"path": "/repo", "labels": ["canonical"], "ready": True},
    )

    assert resource.resource_type is ResourceType.GIT_WORKTREE
    assert resource.resource_type.value == "git_worktree"
    assert {resource_type.value for resource_type in ResourceType} == {
        "git_worktree",
        "process_session",
        "log",
        "data_volume",
        "external_service",
    }
    with pytest.raises(ValueError):
        TypedResource(
            id="bad",
            operation_id="op",
            resource_type=ResourceType.LOG,
            name="bad",
            details={"not_json": object()},
        )


def test_operation_event_requires_json_payload_and_path_tuples() -> None:
    event = OperationEvent(
        id="event-1",
        operation_id="op",
        event_type="launch.started",
        summary="launch started",
        payload={"attempt": 1, "nested": {"ok": True}},
        artifact_paths=["artifacts/launch.json"],
        debug_paths=["debug/launch.log"],
    )

    assert event.sequence == 0
    assert event.artifact_paths == ("artifacts/launch.json",)
    assert event.debug_paths == ("debug/launch.log",)
    with pytest.raises(ValueError):
        OperationEvent(
            id="bad-event",
            operation_id="op",
            event_type="bad",
            summary="bad",
            payload={"not_json": object()},
        )


def test_file_backed_store_round_trips_resources_and_queries_by_operation(tmp_path) -> None:
    store = FileBackedDurableOpsStore(tmp_path)
    store.create_operation_run(OperationRun(id="op-a", operation_type="host"))
    store.create_operation_run(OperationRun(id="op-b", operation_type="host"))
    worktree = store.create_typed_resource(
        TypedResource(
            id="b-worktree",
            operation_id="op-a",
            resource_type=ResourceType.GIT_WORKTREE,
            name="worktree",
            details={"path": "/tmp/op-a"},
        )
    )
    log = store.create_typed_resource(
        TypedResource(
            id="a-log",
            operation_id="op-a",
            resource_type=ResourceType.LOG,
            name="stdout",
            details={"path": "logs/stdout.log"},
        )
    )
    store.create_typed_resource(
        TypedResource(
            id="z-other",
            operation_id="op-b",
            resource_type=ResourceType.DATA_VOLUME,
            name="volume",
        )
    )

    reopened = FileBackedDurableOpsStore(tmp_path)

    assert reopened.list_typed_resources("op-a") == (log, worktree)
    assert reopened.list_typed_resources("op-b")[0].resource_type is ResourceType.DATA_VOLUME


def test_file_backed_store_appends_events_in_operation_sequence_order(tmp_path) -> None:
    store = FileBackedDurableOpsStore(tmp_path)
    store.create_operation_run(OperationRun(id="op-a", operation_type="host"))
    store.create_operation_run(OperationRun(id="op-b", operation_type="host"))

    second = store.append_operation_event(
        OperationEvent(
            id="event-b",
            operation_id="op-a",
            event_type="launch.finished",
            summary="finished",
        )
    )
    first = store.append_operation_event(
        OperationEvent(
            id="event-a",
            operation_id="op-a",
            event_type="launch.started",
            summary="started",
        )
    )
    other = store.append_operation_event(
        OperationEvent(
            id="event-other",
            operation_id="op-b",
            event_type="launch.started",
            summary="other started",
        )
    )

    reopened = FileBackedDurableOpsStore(tmp_path)

    assert (second.sequence, first.sequence, other.sequence) == (1, 2, 1)
    assert reopened.list_operation_events("op-a") == (second, first)
    assert reopened.list_operation_events("op-b") == (other,)


def test_scheduled_task_model_defines_claimable_and_leased_semantics() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    task = ScheduledTask(
        id="task",
        task_type="heartbeat",
        owner_id="runtime",
        next_run_at=now,
        payload={"operation_id": "op", "attempt": 1},
    )

    claimed = task.claim(
        lease_owner="worker-a",
        lease_token="token-a",
        lease_expires_at=now + timedelta(seconds=30),
        now=now,
    )

    assert task.is_claimable(now)
    assert claimed.state is ScheduledTaskState.LEASED
    assert claimed.has_active_lease(now + timedelta(seconds=10))
    assert not claimed.is_claimable(now + timedelta(seconds=10))
    assert claimed.is_claimable(now + timedelta(seconds=31))
    assert can_transition_scheduled_task(
        ScheduledTaskState.PENDING,
        ScheduledTaskState.LEASED,
    )


def test_scheduled_task_terminal_states_are_never_claimable() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    task = ScheduledTask(
        id="task",
        task_type="heartbeat",
        owner_id="runtime",
        next_run_at=now,
    ).cancel(now=now)

    assert task.state is ScheduledTaskState.CANCELLED
    assert is_terminal_scheduled_task_state(task.state)
    assert not task.is_claimable(now + timedelta(days=1))
    with pytest.raises(ValueError):
        task.claim(
            lease_owner="worker-a",
            lease_token="token-a",
            lease_expires_at=now + timedelta(days=1),
            now=now,
        )


def test_scheduled_task_completion_handles_one_shot_and_recurring() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    one_shot = ScheduledTask(
        id="once",
        task_type="cleanup",
        owner_id="runtime",
        next_run_at=now,
    ).claim(
        lease_owner="worker-a",
        lease_token="once-token",
        lease_expires_at=now + timedelta(minutes=1),
        now=now,
    )
    recurring = ScheduledTask(
        id="recurring",
        task_type="cleanup",
        owner_id="runtime",
        next_run_at=now,
        recurring_interval_seconds=300,
    ).claim(
        lease_owner="worker-a",
        lease_token="recurring-token",
        lease_expires_at=now + timedelta(minutes=1),
        now=now,
    )

    completed_once = one_shot.complete(
        lease_token="once-token",
        result={"ok": True},
        now=now,
    )
    completed_recurring = recurring.complete(
        lease_token="recurring-token",
        result={"ok": True},
        now=now,
    )

    assert completed_once.state is ScheduledTaskState.SUCCEEDED
    assert completed_once.next_run_at is None
    assert completed_once.lease_token is None
    assert completed_recurring.state is ScheduledTaskState.PENDING
    assert completed_recurring.next_run_at == now + timedelta(seconds=300)
    assert completed_recurring.lease_token is None


def test_scheduled_task_failure_retries_then_reaches_terminal_failed() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    first_claim = ScheduledTask(
        id="retry",
        task_type="cleanup",
        owner_id="runtime",
        next_run_at=now,
        retry_delay_seconds=60,
        max_failures=2,
    ).claim(
        lease_owner="worker-a",
        lease_token="token-a",
        lease_expires_at=now + timedelta(minutes=1),
        now=now,
    )

    retry = first_claim.fail(
        lease_token="token-a",
        result={"error": "transient"},
        now=now,
    )
    final_claim = retry.claim(
        lease_owner="worker-a",
        lease_token="token-b",
        lease_expires_at=now + timedelta(minutes=2),
        now=now + timedelta(seconds=61),
    )
    failed = final_claim.fail(
        lease_token="token-b",
        result={"error": "permanent"},
        now=now + timedelta(seconds=61),
    )

    assert retry.state is ScheduledTaskState.PENDING
    assert retry.failure_count == 1
    assert retry.next_run_at == now + timedelta(seconds=60)
    assert failed.state is ScheduledTaskState.FAILED
    assert failed.failure_count == 2
    assert failed.next_run_at is None
    assert is_terminal_scheduled_task_state(failed.state)


def test_fake_store_enforces_scheduled_task_lease_token_contract() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    store = FakeOperationStore()
    created = store.create_scheduled_task(
        ScheduledTask(
            id="task",
            task_type="heartbeat",
            owner_id="runtime",
            next_run_at=now,
        )
    )
    claimed = store.claim_scheduled_task(
        created.id,
        lease_owner="worker-a",
        lease_token="token-a",
        lease_seconds=30,
        now=now,
    )

    with pytest.raises(ScheduledTaskLeaseConflict):
        store.claim_scheduled_task(
            claimed.id,
            lease_owner="worker-b",
            lease_token="token-b",
            lease_seconds=30,
            now=now + timedelta(seconds=1),
        )
    with pytest.raises(ScheduledTaskLeaseTokenMismatch):
        store.complete_scheduled_task(
            claimed.id,
            lease_token="wrong-token",
            result={"ok": True},
            now=now + timedelta(seconds=2),
        )

    completed = store.complete_scheduled_task(
        claimed.id,
        lease_token="token-a",
        result={"ok": True},
        now=now + timedelta(seconds=2),
    )

    assert completed.state is ScheduledTaskState.SUCCEEDED
    assert completed.lease_token is None


def test_file_backed_store_claims_only_due_scheduled_tasks(tmp_path) -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    store = FileBackedDurableOpsStore(tmp_path)
    due = store.create_scheduled_task(
        ScheduledTask(
            id="a-due",
            task_type="heartbeat",
            owner_id="runtime",
            next_run_at=now,
        )
    )
    future = store.create_scheduled_task(
        ScheduledTask(
            id="b-future",
            task_type="heartbeat",
            owner_id="runtime",
            next_run_at=now + timedelta(minutes=5),
        )
    )

    claimed = store.claim_scheduled_task(
        due.id,
        lease_owner="worker-a",
        lease_token="token-a",
        lease_seconds=30,
        now=now,
    )
    reopened = FileBackedDurableOpsStore(tmp_path)

    assert claimed.state is ScheduledTaskState.LEASED
    assert claimed.lease_expires_at == now + timedelta(seconds=30)
    assert claimed.lock_version == 1
    assert reopened.load_scheduled_task(due.id) == claimed
    assert reopened.list_scheduled_tasks() == (claimed, future)
    with pytest.raises(ScheduledTaskLeaseConflict):
        reopened.claim_scheduled_task(
            future.id,
            lease_owner="worker-a",
            lease_token="token-future",
            lease_seconds=30,
            now=now,
        )


def test_file_backed_store_excludes_active_lease_and_reclaims_expired_lease(
    tmp_path,
) -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    store = FileBackedDurableOpsStore(tmp_path)
    created = store.create_scheduled_task(
        ScheduledTask(
            id="lease",
            task_type="heartbeat",
            owner_id="runtime",
            next_run_at=now,
        )
    )
    first_claim = store.claim_scheduled_task(
        created.id,
        lease_owner="worker-a",
        lease_token="token-a",
        lease_seconds=30,
        now=now,
    )

    with pytest.raises(ScheduledTaskLeaseConflict):
        store.claim_scheduled_task(
            first_claim.id,
            lease_owner="worker-b",
            lease_token="token-b",
            lease_seconds=30,
            now=now + timedelta(seconds=10),
        )

    reclaimed = store.claim_scheduled_task(
        first_claim.id,
        lease_owner="worker-b",
        lease_token="token-b",
        lease_seconds=30,
        now=now + timedelta(seconds=31),
    )

    assert reclaimed.lease_owner == "worker-b"
    assert reclaimed.lease_token == "token-b"
    assert reclaimed.lock_version == 2


def test_file_backed_store_enforces_token_and_idempotent_same_token_completion(
    tmp_path,
) -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    store = FileBackedDurableOpsStore(tmp_path)
    created = store.create_scheduled_task(
        ScheduledTask(
            id="complete",
            task_type="heartbeat",
            owner_id="runtime",
            next_run_at=now,
        )
    )
    claimed = store.claim_scheduled_task(
        created.id,
        lease_owner="worker-a",
        lease_token="token-a",
        lease_seconds=30,
        now=now,
    )

    with pytest.raises(ScheduledTaskLeaseTokenMismatch):
        store.complete_scheduled_task(
            claimed.id,
            lease_token="wrong-token",
            result={"ok": True},
            now=now + timedelta(seconds=1),
        )

    completed = store.complete_scheduled_task(
        claimed.id,
        lease_token="token-a",
        result={"ok": True},
        now=now + timedelta(seconds=1),
    )
    completed_again = store.complete_scheduled_task(
        claimed.id,
        lease_token="token-a",
        result={"ok": True},
        now=now + timedelta(seconds=2),
    )

    assert completed.state is ScheduledTaskState.SUCCEEDED
    assert completed.lease_token is None
    assert completed_again == completed
    with pytest.raises(ScheduledTaskLeaseTokenMismatch):
        store.complete_scheduled_task(
            claimed.id,
            lease_token="wrong-token",
            result={"ok": True},
            now=now + timedelta(seconds=3),
        )


def test_file_backed_store_recurring_completion_reschedules(tmp_path) -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    store = FileBackedDurableOpsStore(tmp_path)
    created = store.create_scheduled_task(
        ScheduledTask(
            id="recurring",
            task_type="heartbeat",
            owner_id="runtime",
            next_run_at=now,
            recurring_interval_seconds=300,
        )
    )
    claimed = store.claim_scheduled_task(
        created.id,
        lease_owner="worker-a",
        lease_token="token-a",
        lease_seconds=30,
        now=now,
    )

    completed = store.complete_scheduled_task(
        claimed.id,
        lease_token="token-a",
        result={"ok": True},
        now=now + timedelta(seconds=1),
    )

    assert completed.state is ScheduledTaskState.PENDING
    assert completed.next_run_at == now + timedelta(seconds=301)
    assert completed.lease_token is None
    assert completed.failure_count == 0


def test_file_backed_store_terminal_scheduled_tasks_are_not_reclaimed(tmp_path) -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    store = FileBackedDurableOpsStore(tmp_path)
    created = store.create_scheduled_task(
        ScheduledTask(
            id="terminal",
            task_type="heartbeat",
            owner_id="runtime",
            next_run_at=now,
        )
    )
    cancelled = store.cancel_scheduled_task(created.id, now=now)

    assert cancelled.state is ScheduledTaskState.CANCELLED
    assert cancelled.next_run_at is None
    with pytest.raises(ScheduledTaskLeaseConflict):
        store.claim_scheduled_task(
            cancelled.id,
            lease_owner="worker-a",
            lease_token="token-a",
            lease_seconds=30,
            now=now + timedelta(days=1),
        )
