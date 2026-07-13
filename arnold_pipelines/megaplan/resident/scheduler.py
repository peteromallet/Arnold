"""Durable scheduled-job worker and resident job handlers."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol
from uuid import uuid4

from arnold_pipelines.megaplan.schemas import CloudRun, ResidentConversation, ScheduledJob
from arnold_pipelines.megaplan.store import ProgressEventInput, ScheduledJobInput, Store, deterministic_idempotency_key

from .auth import AuthorizationSubject, ConfirmationManager
from .cloud import (
    CloudClassification,
    CloudToolBackend,
    CloudToolRequest,
    CloudToolResult,
    cloud_run_status_for_classification,
    progress_kind_for_classification,
)
from .config import ResidentConfig
from .runtime import EmitProtocol, InboundEvent, OutboundMessage, OutboundSink, ResidentRuntime
from . import vp_todo

JobHandler = Callable[[dict[str, Any]], Awaitable[None]]
TERMINAL_OR_INPUT_NEEDED: frozenset[CloudClassification] = frozenset(
    {"blocked", "failed", "gate-needed", "completed"}
)


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class SchedulerRunResult:
    claimed: int = 0
    fired: int = 0
    retried: int = 0
    cancelled: int = 0


class ScheduledJobBackend(Protocol):
    async def claim_due_jobs(self, *, worker_id: str, now: datetime) -> list[dict[str, Any]]:
        """Atomically claim due jobs and return job payloads."""

    async def mark_fired(self, job_id: str, *, now: datetime) -> None:
        """Mark a claimed job as fired."""

    async def mark_failed(self, job_id: str, error: str, *, now: datetime) -> bool:
        """Record failure and return whether the job will be retried."""


class StoreScheduledJobBackend:
    """Store-backed scheduled-job claiming and retry/cancel policy."""

    def __init__(
        self,
        store: Store,
        *,
        stale_after_seconds: int,
        batch_size: int,
        retry_delay_seconds: int | None = None,
    ) -> None:
        self.store = store
        self.stale_after_seconds = stale_after_seconds
        self.batch_size = batch_size
        self.retry_delay_seconds = retry_delay_seconds or 30

    async def claim_due_jobs(self, *, worker_id: str, now: datetime) -> list[dict[str, Any]]:
        jobs = self.store.claim_due_scheduled_jobs(
            worker_id=worker_id,
            now=now,
            stale_after_seconds=self.stale_after_seconds,
            max=self.batch_size,
            idempotency_key=deterministic_idempotency_key("resident-scheduler-claim", worker_id, now.isoformat()),
        )
        return [job.model_dump(mode="json") for job in jobs]

    async def mark_fired(self, job_id: str, *, now: datetime) -> None:
        self.store.update_scheduled_job(
            job_id,
            status="fired",
            fired_at=now,
            claimed_by=None,
            claimed_at=None,
            idempotency_key=deterministic_idempotency_key("resident-scheduler-fired", job_id),
        )

    async def mark_failed(self, job_id: str, error: str, *, now: datetime) -> bool:
        job = self.store.load_scheduled_job(job_id)
        if job is None:
            return False
        retrying = job.attempt_count < job.max_attempts
        if retrying:
            self.store.update_scheduled_job(
                job.id,
                status="pending",
                scheduled_for=now + timedelta(seconds=self.retry_delay_seconds),
                claimed_by=None,
                claimed_at=None,
                last_error=error,
                idempotency_key=deterministic_idempotency_key("resident-scheduler-retry", job.id, job.attempt_count, error),
            )
        else:
            self.store.update_scheduled_job(
                job.id,
                status="cancelled",
                cancelled_at=now,
                claimed_by=None,
                claimed_at=None,
                last_error=error,
                idempotency_key=deterministic_idempotency_key("resident-scheduler-cancel", job.id, job.attempt_count, error),
            )
        return retrying


class ScheduledJobWorker:
    """Runtime scheduler shell; storage-specific claiming arrives in store code."""

    def __init__(
        self,
        backend: ScheduledJobBackend,
        *,
        handlers: dict[str, JobHandler] | None = None,
        worker_id: str | None = None,
    ) -> None:
        self.backend = backend
        self.worker_id = worker_id or f"resident-scheduler-{uuid4()}"
        self.handlers = handlers or {}

    async def run_due_once(self, *, now: datetime | None = None) -> SchedulerRunResult:
        now = now or utc_now()
        jobs = await self.backend.claim_due_jobs(worker_id=self.worker_id, now=now)
        fired = retried = cancelled = 0
        for job in jobs:
            job_type = str(job.get("job_type") or job.get("type") or "")
            handler = self.handlers.get(job_type)
            if handler is None:
                retrying = await self.backend.mark_failed(str(job["id"]), f"no handler for {job_type}", now=now)
                retried += int(retrying)
                cancelled += int(not retrying)
                continue
            try:
                await handler(job)
            except Exception as exc:
                retrying = await self.backend.mark_failed(str(job["id"]), str(exc), now=now)
                retried += int(retrying)
                cancelled += int(not retrying)
            else:
                await self.backend.mark_fired(str(job["id"]), now=now)
                fired += 1
        return SchedulerRunResult(claimed=len(jobs), fired=fired, retried=retried, cancelled=cancelled)


@dataclass
class ResidentJobHandlers:
    """Handlers for resident durable scheduled jobs."""

    store: Store
    config: ResidentConfig
    cloud_backend: CloudToolBackend
    outbound: OutboundSink | None = None
    confirmation_manager: ConfirmationManager | None = None
    runtime_flush: Callable[[], Awaitable[None]] | None = None
    runtime: ResidentRuntime | None = None
    worker_id: str = "resident-scheduler"
    reschedule_interval_s: int | None = None

    def handlers(self) -> dict[str, JobHandler]:
        return {
            "cloud_check": self.handle_cloud_check,
            "deferred_turn": self.handle_deferred_turn,
            "heartbeat": self.handle_heartbeat,
            "confirmation_expiry": self.handle_confirmation_expiry,
            "vp_todo_sweep": self.handle_vp_todo_sweep,
        }

    async def handle_cloud_check(self, job_payload: dict[str, Any]) -> None:
        job = _job_from_payload(job_payload)
        if not job.cloud_run_id:
            raise ValueError("cloud_check job requires cloud_run_id")
        if not job.conversation_id:
            raise ValueError("cloud_check job requires conversation_id")
        run = self.store.load_cloud_run(job.cloud_run_id)
        if run is None:
            raise ValueError(f"cloud run {job.cloud_run_id!r} was not found")
        conversation = self.store.load_resident_conversation(job.conversation_id)
        if conversation is None:
            raise ValueError(f"resident conversation {job.conversation_id!r} was not found")

        result = await self.cloud_backend.run(_cloud_request_for_job(job, run))
        previous_status = run.status
        updated = self._persist_cloud_result(run, result)
        classification = result.classification
        if bool(job.payload.get("notify_every_check", False)):
            await self._notify_cloud_check_fire(
                conversation=conversation,
                job=job,
                run=updated,
                classification=classification,
                summary=result.summary,
            )
        if classification == "running":
            self._reschedule_cloud_check(job, updated)
        elif classification in TERMINAL_OR_INPUT_NEEDED:
            await self._notify_cloud_transition(
                conversation=conversation,
                run=updated,
                classification=classification,
                summary=result.summary,
            )
        self._log_cloud_check(job, updated, result, previous_status=previous_status)

    async def handle_deferred_turn(self, job_payload: dict[str, Any]) -> None:
        job = _job_from_payload(job_payload)
        if self.runtime_flush is not None:
            await self.runtime_flush()
        self._emit_sink().log_system_event(
            level="info",
            category="system",
            event_type="resident_deferred_turn",
            message="Resident deferred turn job processed",
            details={"job_id": job.id, "conversation_id": job.conversation_id},
            idempotency_key=deterministic_idempotency_key("resident-deferred-turn", job.id, job.attempt_count),
        )

    async def handle_heartbeat(self, job_payload: dict[str, Any]) -> None:
        job = _job_from_payload(job_payload)
        self._emit_sink().log_system_event(
            level="info",
            category="system",
            event_type="resident_scheduler_heartbeat",
            message="Resident scheduler heartbeat",
            details={"job_id": job.id, "worker_id": self.worker_id},
            idempotency_key=deterministic_idempotency_key("resident-heartbeat", job.id, job.attempt_count),
        )

    async def handle_confirmation_expiry(self, job_payload: dict[str, Any]) -> None:
        job = _job_from_payload(job_payload)
        expired = self.confirmation_manager.expire_due() if self.confirmation_manager is not None else []
        self._emit_sink().log_system_event(
            level="info",
            category="system",
            event_type="resident_confirmation_expiry",
            message="Expired resident confirmation requests",
            details={"job_id": job.id, "expired_request_ids": [request.id for request in expired]},
            idempotency_key=deterministic_idempotency_key("resident-confirmation-expiry", job.id, job.attempt_count),
        )

    async def handle_vp_todo_sweep(self, job_payload: dict[str, Any]) -> None:
        job = _job_from_payload(job_payload)
        todo_path = self.config.special_requests_todo_path
        pending = vp_todo.pending_items(todo_path)
        if self.runtime is None or not self.config.special_requests_enabled:
            self._emit_sink().log_system_event(
                level="info",
                category="system",
                event_type="resident_vp_todo_sweep",
                message="VP to-do sweep skipped (disabled or no runtime)",
                details={"job_id": job.id, "pending": len(pending)},
                idempotency_key=deterministic_idempotency_key(
                    "resident-vp-todo-sweep-skip", job.id, job.attempt_count
                ),
            )
            self._reschedule_vp_todo_sweep(job)
            return
        if not pending:
            self._emit_sink().log_system_event(
                level="info",
                category="system",
                event_type="resident_vp_todo_sweep",
                message="VP to-do sweep had no pending items",
                details={"job_id": job.id, "pending": 0},
                idempotency_key=deterministic_idempotency_key(
                    "resident-vp-todo-sweep-empty", job.id, job.attempt_count
                ),
            )
            self._reschedule_vp_todo_sweep(job)
            return

        subject_user_id = str(
            job.payload.get("subject_user_id")
            or self.config.special_requests_subject_user_id
            or self._first_user_id()
        )
        conversation_key = str(
            job.payload.get("conversation_key")
            or self.config.special_requests_conversation_key
            or f"discord:dm:{subject_user_id}"
        )
        subject = AuthorizationSubject(
            user_id=subject_user_id,
            guild_id=_optional_str(job.payload.get("guild_id")),
            channel_id=_optional_str(job.payload.get("channel_id")),
        )
        event = InboundEvent(
            idempotency_key=deterministic_idempotency_key(
                "resident-vp-todo-sweep", job.id, job.attempt_count
            ),
            conversation_key=conversation_key,
            subject=subject,
            content=_vp_todo_sweep_prompt(todo_path, pending),
            raw={"vp_todo_sweep": True, "job_id": job.id, "pending_count": len(pending)},
        )
        await self.runtime.receive(event)
        self._emit_sink().log_system_event(
            level="info",
            category="system",
            event_type="resident_vp_todo_sweep",
            message="VP to-do sweep dispatched to resident agent",
            details={
                "job_id": job.id,
                "pending": len(pending),
                "conversation_key": conversation_key,
            },
            idempotency_key=deterministic_idempotency_key(
                "resident-vp-todo-sweep-fire", job.id, job.attempt_count
            ),
        )
        self._reschedule_vp_todo_sweep(job)

    def _first_user_id(self) -> str:
        ids = self.config.allowed_user_ids or self.config.admin_user_ids
        if not ids:
            raise ValueError(
                "vp_todo_sweep requires a user id (configure allowed_user_ids "
                "or admin_user_ids, or special_requests_subject_user_id)"
            )
        return ids[0]

    def _reschedule_vp_todo_sweep(self, job: ScheduledJob) -> None:
        pending = self.store.list_scheduled_jobs(job_type="vp_todo_sweep", status="pending", limit=1)
        if pending:
            return
        interval = int(
            job.payload.get("interval_s") or self.config.special_requests_interval_s
        )
        self.store.create_scheduled_job(
            ScheduledJobInput(
                job_type="vp_todo_sweep",
                conversation_id=job.conversation_id,
                payload=dict(job.payload),
                scheduled_for=utc_now() + timedelta(seconds=max(1, interval)),
                max_attempts=job.max_attempts,
            ),
            idempotency_key=deterministic_idempotency_key(
                "resident-vp-todo-sweep-reschedule", job.id, job.attempt_count
            ),
        )

    def _persist_cloud_result(
        self,
        run: CloudRun,
        result: CloudToolResult,
    ) -> CloudRun:
        now = utc_now()
        status = cloud_run_status_for_classification(result.classification)
        last_status = {
            "cloud_status": result.classification,
            "summary": result.summary,
            "details": result.details,
            "checked_at": now.isoformat().replace("+00:00", "Z"),
        }
        changes: dict[str, Any] = {
            "status": status,
            "progress_summary": result.summary,
            "last_status": last_status,
            "last_checked_at": now,
        }
        if status in {"completed", "failed", "blocked", "gate-needed"}:
            changes["completed_at"] = now
        updated = self.store.update_cloud_run(
            run.id,
            **changes,
            idempotency_key=deterministic_idempotency_key(
                "resident-cloud-check-status",
                run.id,
                result.classification,
                result.summary,
            ),
        )
        should_append_progress = run.status != updated.status or not run.last_status
        if should_append_progress and updated.epic_id:
            self._emit_sink().append_progress_event(
                ProgressEventInput(
                    epic_id=updated.epic_id,
                    plan_id=updated.plan_id,
                    sprint_id=updated.sprint_id,
                    kind=progress_kind_for_classification(result.classification),
                    summary=result.summary,
                    details={
                        "cloud_status": result.classification,
                        "cloud_run_id": updated.id,
                        "operation": updated.operation,
                    },
                ),
                idempotency_key=deterministic_idempotency_key(
                    "resident-cloud-check-progress",
                    updated.id,
                    result.classification,
                    updated.status,
                ),
            )
        return updated

    async def _notify_cloud_check_fire(
        self,
        *,
        conversation: ResidentConversation,
        job: ScheduledJob,
        run: CloudRun,
        classification: CloudClassification,
        summary: str,
    ) -> None:
        content = _cloud_check_notification_text(job, run, classification, summary)
        idempotency_key = deterministic_idempotency_key("resident-cloud-check-notification", job.id, job.attempt_count)
        message = self.store.create_message(
            epic_id=run.epic_id,
            conversation_id=conversation.id,
            direction="outbound",
            content=content,
            idempotency_key=idempotency_key,
        )
        self.store.update_resident_conversation(
            conversation.id,
            last_outbound_message_id=message.id,
            delivery_cursor=message.id,
            last_active_at=utc_now(),
            idempotency_key=deterministic_idempotency_key("resident-cloud-check-notification-pointer", conversation.id, message.id),
        )
        if self.outbound is not None:
            await self.outbound.send(
                OutboundMessage(
                    conversation_key=conversation.conversation_key,
                    content=content,
                    idempotency_key=idempotency_key,
                    metadata={
                        "conversation_id": conversation.id,
                        "message_id": message.id,
                        "scheduled_job_id": job.id,
                        "cloud_run_id": run.id,
                        "cloud_status": classification,
                    },
                )
            )

    def _reschedule_cloud_check(self, job: ScheduledJob, run: CloudRun) -> None:
        pending = self.store.list_scheduled_jobs(
            conversation_id=job.conversation_id,
            cloud_run_id=run.id,
            status="pending",
            job_type="cloud_check",
            limit=1,
        )
        if pending:
            return
        interval = int(job.payload.get("check_interval_s") or self.reschedule_interval_s or self.config.scheduler_poll_interval_s)
        self.store.create_scheduled_job(
            ScheduledJobInput(
                job_type="cloud_check",
                conversation_id=job.conversation_id,
                cloud_run_id=run.id,
                epic_id=run.epic_id or job.epic_id,
                payload=dict(job.payload),
                scheduled_for=utc_now() + timedelta(seconds=max(1, interval)),
                max_attempts=job.max_attempts,
            ),
            idempotency_key=deterministic_idempotency_key(
                "resident-cloud-check-reschedule",
                run.id,
                job.attempt_count,
                run.last_checked_at.isoformat() if run.last_checked_at else "",
            ),
        )

    async def _notify_cloud_transition(
        self,
        *,
        conversation: ResidentConversation,
        run: CloudRun,
        classification: CloudClassification,
        summary: str,
    ) -> None:
        idempotency_key = deterministic_idempotency_key("resident-cloud-notification", run.id, classification)
        notifications = dict(run.metadata.get("notifications") or {})
        already_persisted = classification in notifications
        content = _cloud_notification_text(run, classification, summary)
        message = self.store.create_message(
            epic_id=run.epic_id,
            conversation_id=conversation.id,
            direction="outbound",
            content=content,
            idempotency_key=idempotency_key,
        )
        self.store.update_resident_conversation(
            conversation.id,
            last_outbound_message_id=message.id,
            delivery_cursor=message.id,
            last_active_at=utc_now(),
            idempotency_key=deterministic_idempotency_key("resident-cloud-notification-pointer", conversation.id, message.id),
        )
        notifications[classification] = message.id
        self.store.update_cloud_run(
            run.id,
            metadata={**dict(run.metadata), "notifications": notifications},
            idempotency_key=deterministic_idempotency_key("resident-cloud-notification-mark", run.id, classification),
        )
        if self.outbound is not None and not already_persisted:
            await self.outbound.send(
                OutboundMessage(
                    conversation_key=conversation.conversation_key,
                    content=content,
                    idempotency_key=idempotency_key,
                    metadata={
                        "conversation_id": conversation.id,
                        "message_id": message.id,
                        "cloud_run_id": run.id,
                        "cloud_status": classification,
                    },
                )
            )

    def _log_cloud_check(
        self,
        job: ScheduledJob,
        run: CloudRun,
        result: CloudToolResult,
        *,
        previous_status: str,
    ) -> None:
        self._emit_sink().log_system_event(
            level="info",
            category="system",
            event_type="resident_cloud_check",
            message="Resident cloud check processed",
            details={
                "job_id": job.id,
                "cloud_run_id": run.id,
                "previous_status": previous_status,
                "status": run.status,
                "cloud_status": result.classification,
            },
            idempotency_key=deterministic_idempotency_key(
                "resident-cloud-check-log",
                job.id,
                job.attempt_count,
                result.classification,
            ),
        )

    def _emit_sink(self) -> EmitProtocol:
        return self.store


def make_store_scheduler(
    *,
    store: Store,
    config: ResidentConfig,
    cloud_backend: CloudToolBackend,
    outbound: OutboundSink | None = None,
    confirmation_manager: ConfirmationManager | None = None,
    runtime_flush: Callable[[], Awaitable[None]] | None = None,
    runtime: ResidentRuntime | None = None,
    worker_id: str | None = None,
) -> ScheduledJobWorker:
    worker_name = worker_id or f"resident-scheduler-{uuid4()}"
    handlers = ResidentJobHandlers(
        store=store,
        config=config,
        cloud_backend=cloud_backend,
        outbound=outbound,
        confirmation_manager=confirmation_manager,
        runtime_flush=runtime_flush,
        runtime=runtime,
        worker_id=worker_name,
    )
    backend = StoreScheduledJobBackend(
        store,
        stale_after_seconds=int(config.stale_claim_timeout_s),
        batch_size=config.scheduler_batch_size,
    )
    return ScheduledJobWorker(backend, handlers=handlers.handlers(), worker_id=worker_name)


def _cloud_request_for_job(job: ScheduledJob, run: CloudRun) -> CloudToolRequest:
    payload = dict(job.payload)
    operation = str(payload.get("cloud_operation") or "")
    if operation not in {"cloud_status", "cloud_status_chain"}:
        operation = "cloud_status_chain" if run.operation == "chain" else "cloud_status"
    arguments = {
        "project_root": str(payload.get("project_root") or "."),
        "cloud_yaml": str(payload.get("cloud_yaml") or "cloud.yaml"),
    }
    if plan := (payload.get("plan") or run.plan_id):
        arguments["plan"] = str(plan)
    if remote_spec := (payload.get("remote_spec") or (run.target_id if run.operation == "chain" else None)):
        arguments["remote_spec"] = str(remote_spec)
    return CloudToolRequest(
        operation=operation,  # type: ignore[arg-type]
        target_id=run.target_id,
        arguments=arguments,
        confirmed=True,
        launch_provenance=(
            run.metadata.get("resident_delegation")
            if isinstance(run.metadata, dict)
            and isinstance(run.metadata.get("resident_delegation"), dict)
            else None
        ),
    )


def _job_from_payload(payload: dict[str, Any]) -> ScheduledJob:
    return ScheduledJob.model_validate(payload)


def _cloud_notification_text(run: CloudRun, classification: CloudClassification, summary: str) -> str:
    target = run.target_id or run.plan_id or run.sprint_id or run.id
    return f"Cloud run {target} is {classification}: {summary}"


def _cloud_check_notification_text(
    job: ScheduledJob,
    run: CloudRun,
    classification: CloudClassification,
    summary: str,
) -> str:
    target = run.target_id or run.plan_id or run.sprint_id or run.id
    interval = int(job.payload.get("check_interval_s") or 0)
    cadence = f" every {interval // 3600}h" if interval and interval % 3600 == 0 else (f" every {interval}s" if interval else "")
    return f"Cloud check{cadence} ran for {target}: {classification}. {summary}"


def _vp_todo_sweep_prompt(todo_path: object, pending: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for item in pending:
        line = f"- id={item['id']}: {item['task']}"
        if item.get("when"):
            line += f"  (when: {item['when']})"
        lines.append(line)
    bullets = "\n".join(lines)
    return (
        f"The VP special-requests sweep just fired. There are {len(pending)} pending "
        f"item(s) in the to-do list at `{todo_path}`:\n{bullets}\n\n"
        "You were given a hot-context `plan_activity_summary` as a system message this "
        "turn (current `active_working` / `should_be_working_but_needs_attention` / "
        "`recently_completed` chains) — treat it as your first source of truth so you "
        "don't re-derive state you already have. Work through each pending item:\n"
        "1. Check for overlap first: scan `active_working` and `recently_completed` in "
        "the hot context for work that already covers this item's task. If the task is "
        "already in-flight or was just completed, skip it for now (leave it pending) and "
        "note the overlap in your reply.\n"
        "2. If the item has a `when` condition, verify it is satisfied — first from the "
        "hot context (e.g. the epic/chain it gates on), falling back to your tools (e.g. "
        "`read_epic`, `cloud_status`) only if the hot context doesn't already show it. "
        "If the condition is NOT yet satisfied, skip that item for now (leave it pending) "
        "and move to the next one.\n"
        "3. Reconcile the item id against `resident_agents` in hot context. If its managed "
        "agent is running, leave the item pending and report the manifest/full-log/result paths. "
        "If it recently completed or failed, use its result/manifest paths to report the durable "
        "outcome and then call `complete_todo_item` or `fail_todo_item` as appropriate.\n"
        "4. If no managed agent exists for the item, call `launch_subagent` with its task, "
        "`request_id` set to the item id, and the canonical defaults `backend=codex`, "
        "`background=true`. Leave the item pending while that agent runs.\n"
        "5. Never use the legacy Hermes override for scheduled special-request work.\n\n"
        "Your reply to the channel must give the canonical manifest, full-log, and result "
        "locations for every launched or reconciled task. Include the actual result for a "
        "completed task when available. Also list any items you skipped because of an "
        "overlap with in-flight/recently-completed work or because their `when` condition "
        "was not yet met."
    )


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None
