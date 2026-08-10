"""Guardian scheduled-task worker."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Mapping
from uuid import uuid4

from arnold.runtime.durable_ops import (
    FileBackedDurableOpsStore,
    OperationLockConflict,
    OperationNotFound,
    OperationState,
    ScheduledTask,
    is_terminal_operation_state,
)

from agentbox.config import AgentBoxConfig
from agentbox.guardian.briefing import handle_briefing_task, handle_reminder_task
from agentbox.guardian.handlers import (
    MEGAPLAN_CHAIN_OPERATION_TYPE,
    GuardianHandlerRegistry,
    UnsupportedOperationTypeDiagnostic,
    default_guardian_handler_registry,
)
from agentbox.guardian.model import (
    GuardianInspectionResult,
    GuardianMaterialTransition,
    GuardianOutcome,
)
from agentbox.guardian.notifications import GuardianNotifier
from agentbox.guardian.scheduler import GUARDIAN_TASK_DEFINITIONS, GUARDIAN_TASK_IDS
from agentbox.guardian.state import GuardianStateStore
from agentbox.operations import list_agentbox_operations, update_agentbox_operation

GUARDIAN_WORKER_OWNER = "guardian:worker"
GUARDIAN_SUPERVISION_TASK_TYPES = ("guardian.liveness", "guardian.deep_supervision")
GUARDIAN_TASK_TYPES = (
    "guardian.liveness",
    "guardian.deep_supervision",
    "guardian.briefing",
    "guardian.reminders",
)
INSPECTION_TIMEOUT_SECONDS = 30.0
LEASE_SECONDS = 60
HEARTBEAT_INTERVAL_SECONDS = 30.0
MAX_CONSECUTIVE_INSPECTION_FAILURES = 3
MAX_RESUME_ATTEMPTS = 2
MAX_TRANSIENT_RETRIES = 2


@dataclass
class GuardianWorker:
    """Claims due Guardian scheduled tasks and supervises operations."""

    config: AgentBoxConfig
    operation_store: FileBackedDurableOpsStore
    handler_registry: GuardianHandlerRegistry = field(
        default_factory=default_guardian_handler_registry
    )
    notifier: GuardianNotifier | None = None
    state_store: GuardianStateStore | None = None
    inspection_timeout_seconds: float = INSPECTION_TIMEOUT_SECONDS
    lease_seconds: int = LEASE_SECONDS
    heartbeat_interval_seconds: float = HEARTBEAT_INTERVAL_SECONDS
    max_consecutive_inspection_failures: int = MAX_CONSECUTIVE_INSPECTION_FAILURES
    max_resume_attempts: int = MAX_RESUME_ATTEMPTS
    max_transient_retries: int = MAX_TRANSIENT_RETRIES

    def __post_init__(self) -> None:
        if self.state_store is None:
            self.state_store = GuardianStateStore(self.config)

    async def run_due_once(
        self,
        *,
        now: datetime | None = None,
        max_operations: int = 50,
    ) -> dict[str, Any]:
        """Claim and execute one batch of due Guardian tasks."""

        timestamp = now or datetime.now(UTC)
        tasks = self.operation_store.claim_due_scheduled_tasks(
            "guardian",
            GUARDIAN_TASK_TYPES,
            lease_owner=GUARDIAN_WORKER_OWNER,
            lease_seconds=self.lease_seconds,
            max_count=10,
            now=timestamp,
        )

        results: list[dict[str, Any]] = []
        for task in tasks:
            heartbeat_task = asyncio.create_task(
                self._heartbeat_loop(task, timestamp)
            )
            try:
                result = await self._dispatch_task(task, timestamp=timestamp)
                results.append(result)
            finally:
                heartbeat_task.cancel()
                try:
                    await heartbeat_task
                except asyncio.CancelledError:
                    pass

        supervision_results: list[dict[str, Any]] = []
        if any(
            task.task_type in GUARDIAN_SUPERVISION_TASK_TYPES for task in tasks
        ):
            supervision_results = await self._supervise_operations(
                timestamp=timestamp,
                max_operations=max_operations,
            )

        return {
            "tasks_run": len(results),
            "operations_supervised": len(supervision_results),
            "task_results": results,
            "operation_results": supervision_results,
        }

    async def _heartbeat_loop(
        self,
        task: ScheduledTask,
        start_time: datetime,
    ) -> None:
        """Keep the scheduled-task lease alive while work runs."""

        if task.lease_token is None:
            return
        deadline = start_time + timedelta(seconds=self.lease_seconds)
        while datetime.now(UTC) < deadline:
            await asyncio.sleep(self.heartbeat_interval_seconds)
            try:
                self.operation_store.heartbeat_scheduled_task(
                    task.id,
                    task.lease_token,
                    lease_seconds=self.lease_seconds,
                )
            except Exception:
                break

    async def _dispatch_task(
        self,
        task: ScheduledTask,
        *,
        timestamp: datetime,
    ) -> dict[str, Any]:
        """Run a single Guardian scheduled task and complete/fail its lease."""

        if task.lease_token is None:
            return {"task_id": task.id, "ok": False, "error": "missing lease token"}

        try:
            if task.task_type in GUARDIAN_SUPERVISION_TASK_TYPES:
                result = {"ok": True, "task_type": task.task_type}
            elif task.task_type == "guardian.briefing":
                result = handle_briefing_task(self.config, task, now=timestamp)
            elif task.task_type == "guardian.reminders":
                result = handle_reminder_task(self.config, task, now=timestamp)
            else:
                result = {"ok": True, "task_type": task.task_type, "note": "unhandled"}
            self.operation_store.complete_scheduled_task(
                task.id,
                lease_token=task.lease_token,
                result=result,
                now=timestamp,
            )
            return {"task_id": task.id, "ok": True, "result": result}
        except Exception as exc:
            self.operation_store.fail_scheduled_task(
                task.id,
                lease_token=task.lease_token,
                result={"error": f"{exc.__class__.__name__}: {exc}"},
                now=timestamp,
            )
            return {"task_id": task.id, "ok": False, "error": str(exc)}

    async def _supervise_operations(
        self,
        *,
        timestamp: datetime,
        max_operations: int,
    ) -> list[dict[str, Any]]:
        """Inspect and recover non-terminal megaplan_chain operations."""

        operations = list_agentbox_operations(
            self.config,
            operation_types=(MEGAPLAN_CHAIN_OPERATION_TYPE,),
        )
        operations = [
            run
            for run in operations
            if not is_terminal_operation_state(run.state)
        ][:max_operations]

        results: list[dict[str, Any]] = []
        for run in operations:
            result = await self._inspect_operation(run.id, timestamp=timestamp)
            results.append(result)
        return results

    async def _inspect_operation(
        self,
        operation_id: str,
        *,
        timestamp: datetime,
    ) -> dict[str, Any]:
        """Inspect a single operation, applying recovery and notification policy."""

        try:
            run = self.operation_store.load_operation_run(operation_id)
        except OperationNotFound:
            return {"operation_id": operation_id, "outcome": "not_found"}

        handler = self.handler_registry.get(run.operation_type)
        if isinstance(handler, UnsupportedOperationTypeDiagnostic):
            return {
                "operation_id": operation_id,
                "outcome": "skipped",
                "summary": f"Unsupported operation type {run.operation_type!r}",
            }

        try:
            result = await asyncio.wait_for(
                handler.inspect(self.config, operation_id),
                timeout=self.inspection_timeout_seconds,
            )
        except asyncio.TimeoutError:
            result = GuardianInspectionResult(
                operation_id=operation_id,
                outcome=GuardianOutcome.RETRY,
                material_transition=GuardianMaterialTransition.NONE,
                summary="Inspection timed out",
            )
        except Exception as exc:
            result = GuardianInspectionResult(
                operation_id=operation_id,
                outcome=GuardianOutcome.RETRY,
                material_transition=GuardianMaterialTransition.NONE,
                summary=f"Inspection error: {exc.__class__.__name__}: {exc}",
            )

        if result.outcome is GuardianOutcome.RETRY:
            failures = self.state_store.increment_counter(
                "consecutive_inspection_failures", operation_id
            )
        else:
            failures = 0
            self.state_store.set_counter(
                "consecutive_inspection_failures", operation_id, 0
            )

        if failures >= self.max_consecutive_inspection_failures:
            await self._mark_operation_failed(operation_id, result, timestamp)
            return {
                "operation_id": operation_id,
                "outcome": GuardianOutcome.FAILED.value,
                "reason": "inspection_failure_cap",
            }

        if result.material_transition in {
            GuardianMaterialTransition.COMPLETED,
            GuardianMaterialTransition.FAILED,
            GuardianMaterialTransition.STALLED,
        }:
            await self._maybe_notify(run, result, timestamp)

        if (
            result.material_transition is GuardianMaterialTransition.STALLED
            and result.outcome is GuardianOutcome.RETRY
        ):
            resume_attempts = self.state_store.increment_counter(
                "resume_attempt_counters", operation_id
            )
            if resume_attempts <= self.max_resume_attempts:
                try:
                    await handler.resume(self.config, operation_id)
                    result = await handler.inspect(self.config, operation_id)
                except Exception as exc:
                    return {
                        "operation_id": operation_id,
                        "outcome": "resume_failed",
                        "error": f"{exc.__class__.__name__}: {exc}",
                        "resume_attempt": resume_attempts,
                    }
            else:
                await self._mark_operation_failed(operation_id, result, timestamp)
                return {
                    "operation_id": operation_id,
                    "outcome": GuardianOutcome.FAILED.value,
                    "reason": "resume_attempt_cap",
                }

        return {
            "operation_id": operation_id,
            "outcome": result.outcome.value,
            "transition": result.material_transition.value,
            "summary": result.summary,
        }

    async def _maybe_notify(
        self,
        run: Any,
        result: GuardianInspectionResult,
        timestamp: datetime,
    ) -> None:
        """Emit a material-transition notification if configured."""

        if self.notifier is None:
            return
        if result.material_transition is GuardianMaterialTransition.STALLED:
            await self.notifier.notify_needs_attention(run.id, result, timestamp)
        elif result.material_transition is GuardianMaterialTransition.COMPLETED:
            await self.notifier.notify_completed(run.id, result, timestamp)
        elif result.material_transition is GuardianMaterialTransition.FAILED:
            await self.notifier.notify_failed(run.id, result, timestamp)

    async def _mark_operation_failed(
        self,
        operation_id: str,
        result: GuardianInspectionResult,
        timestamp: datetime,
    ) -> None:
        """Mark an operation FAILED after hitting a retry cap."""

        try:
            update_agentbox_operation(
                self.config,
                operation_id,
                state=OperationState.FAILED,
                metadata={
                    "guardian_failure_reason": result.summary,
                    "guardian_failed_at": timestamp.isoformat(),
                },
            )
            await self._maybe_notify(
                self.operation_store.load_operation_run(operation_id),
                GuardianInspectionResult(
                    operation_id=operation_id,
                    outcome=GuardianOutcome.FAILED,
                    material_transition=GuardianMaterialTransition.FAILED,
                    summary=result.summary,
                    inspected_at=timestamp,
                ),
                timestamp,
            )
        except OperationLockConflict:
            pass


__all__ = [
    "GuardianWorker",
    "LEASE_SECONDS",
    "HEARTBEAT_INTERVAL_SECONDS",
]
