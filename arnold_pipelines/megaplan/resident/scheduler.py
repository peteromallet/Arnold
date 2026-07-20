"""Durable scheduled-job worker and resident job handlers."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import hashlib
import json
from typing import Any, Protocol
from uuid import uuid4

from arnold_pipelines.megaplan.cloud.redact import redact_payload
from arnold_pipelines.megaplan.schemas import CloudRun, ResidentConversation, ScheduledJob
from .timezone import TimezoneService, localize_text_timestamps
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
        retained = vp_todo.load_items(todo_path)
        pending = [
            item
            for item in retained
            if item["status"] == vp_todo.PENDING and item["task"]
        ]
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
            self._reschedule_vp_todo_sweep(job, audit_context=None)
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
            self._reschedule_vp_todo_sweep(job, audit_context=None)
            return

        audit_context = _vp_todo_audit_context(
            store=self.store,
            todo_path=todo_path,
            retained=retained,
            job=job,
        )
        unchanged_sweeps = audit_context["repeat_state"]["consecutive_unchanged_sweeps"]
        if unchanged_sweeps >= vp_todo.DEFAULT_UNCHANGED_CYCLE_ESCALATION_THRESHOLD:
            self._emit_sink().log_system_event(
                level="warn",
                category="system",
                event_type="resident_vp_todo_unchanged_cycle_escalated",
                message="VP to-do state remained unchanged across repeated scheduled sweeps",
                details={
                    "audit_id": audit_context["audit_id"],
                    "job_id": job.id,
                    "consecutive_unchanged_sweeps": unchanged_sweeps,
                    "retained_todo_digest": audit_context["repeat_state"][
                        "retained_todo_digest"
                    ],
                },
                idempotency_key=deterministic_idempotency_key(
                    "resident-vp-todo-unchanged-cycle-escalated",
                    audit_context["repeat_state"]["retained_todo_digest"],
                    unchanged_sweeps,
                ),
        )
        for item in audit_context["items"]:
            inbound = item["authoritative_inbound"]
            if not item["delegation_candidate"] or inbound["state"] == "verified":
                continue
            self._emit_sink().log_system_event(
                level="warn",
                category="system",
                event_type="resident_vp_todo_inbound_evidence_missing",
                message="VP to-do audit blocked delegation without authoritative inbound evidence",
                details={
                    "audit_id": audit_context["audit_id"],
                    "job_id": job.id,
                    "todo_item_id": item["id"],
                    "todo_updated_at": item["updated_at"],
                    "diagnostic_code": inbound["diagnostic_code"],
                    "source_record_id": inbound.get("source_record_id"),
                    "delegation_allowed": False,
                },
                idempotency_key=deterministic_idempotency_key(
                    "resident-vp-todo-inbound-diagnostic",
                    audit_context["audit_id"],
                    item["id"],
                    inbound["diagnostic_code"],
                ),
            )

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
            content=_vp_todo_sweep_prompt(audit_context),
            raw={
                "source_kind": "scheduled_turn",
                "vp_todo_sweep": True,
                "job_id": job.id,
                "pending_count": len(pending),
                "vp_todo_audit_context": audit_context,
            },
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
                "audit_id": audit_context["audit_id"],
                "retained_todo_digest": audit_context["repeat_state"][
                    "retained_todo_digest"
                ],
                "consecutive_unchanged_sweeps": audit_context["repeat_state"][
                    "consecutive_unchanged_sweeps"
                ],
                "delegation_blocked_count": audit_context["summary"][
                    "delegation_blocked_count"
                ],
            },
            idempotency_key=deterministic_idempotency_key(
                "resident-vp-todo-sweep-fire", job.id, job.attempt_count
            ),
        )
        self._reschedule_vp_todo_sweep(job, audit_context=audit_context)

    def _first_user_id(self) -> str:
        ids = self.config.allowed_user_ids or self.config.admin_user_ids
        if not ids:
            raise ValueError(
                "vp_todo_sweep requires a user id (configure allowed_user_ids "
                "or admin_user_ids, or special_requests_subject_user_id)"
            )
        return ids[0]

    def _reschedule_vp_todo_sweep(
        self,
        job: ScheduledJob,
        *,
        audit_context: Mapping[str, Any] | None,
    ) -> None:
        pending = self.store.list_scheduled_jobs(job_type="vp_todo_sweep", status="pending", limit=1)
        if pending:
            return
        interval = int(
            job.payload.get("interval_s") or self.config.special_requests_interval_s
        )
        payload = dict(job.payload)
        if audit_context is None:
            payload.pop("last_retained_todo_digest", None)
            payload.pop("consecutive_unchanged_sweeps", None)
        else:
            repeat_state = audit_context["repeat_state"]
            payload["last_retained_todo_digest"] = repeat_state[
                "retained_todo_digest"
            ]
            payload["consecutive_unchanged_sweeps"] = repeat_state[
                "consecutive_unchanged_sweeps"
            ]
        self.store.create_scheduled_job(
            ScheduledJobInput(
                job_type="vp_todo_sweep",
                conversation_id=job.conversation_id,
                payload=payload,
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
        content = self._localized_notification_text(
            conversation,
            _cloud_check_notification_text(job, run, classification, summary),
        )
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
        content = self._localized_notification_text(
            conversation,
            _cloud_notification_text(run, classification, summary),
        )
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

    def _localized_notification_text(
        self, conversation: ResidentConversation, content: str
    ) -> str:
        user_id = str(
            conversation.metadata.get("last_subject_user_id")
            or conversation.dm_user_id
            or ""
        ) or None
        resolved = TimezoneService(self.store, self.config).resolve(
            user_id=user_id,
            conversation=conversation,
            guild_id=conversation.guild_id,
        )
        return localize_text_timestamps(content, resolved.name)


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


def _vp_todo_sweep_prompt(audit_context: Mapping[str, Any]) -> str:
    rendered_context = json.dumps(audit_context, indent=2, sort_keys=True)
    return (
        "The six-hour VP special-request auditor just fired. This is a bounded audit and "
        "reconciliation turn, not fresh product authority. Read the structured snapshot below, "
        "then call `read_todo_list` with no arguments before making any decision; that tool is "
        "the authoritative full retained todo set, including failed and conditional items.\n\n"
        "Bounded mandate:\n"
        "1. Separate each item's authorized outcome from current runtime health. A launch-intent "
        "item is satisfied when canonical evidence proves the exact requested chain/run was "
        "successfully launched with the requested identity and configuration. A later blocked "
        "milestone does not make that launch intent pending again. Safely reconcile that stale "
        "bookkeeping with `reconcile_todo_item`, recording the canonical run ID, durable "
        "evidence location, and reconciliation reason.\n"
        "2. A downstream item with a non-empty `when` remains genuinely conditional until the "
        "condition itself is canonically satisfied. Do not infer completion from an upstream "
        "launch, percent complete, a stale plan-local state, or overlapping work. Leave it pending "
        "and state the missing condition evidence.\n"
        "3. Use `read_context_node` on `agents/running` and `agents/recent` (or "
        "`search_context` scope `agents`) to reconcile stable todo/request IDs with canonical "
        "run IDs, status, lineage, manifest, full-log, result, and delivery evidence. Use the "
        "status route for canonical chain state and repair evidence; chain truth beats stale "
        "plan-local or prose summaries. Never claim success from a PID, acknowledgement, or "
        "artifact path alone.\n"
        "4. Treat `consecutive_unchanged_sweeps` as a loop signal, not automatic failure. Explain "
        "whether the unchanged state is an expected unsatisfied condition, an active canonical "
        "run, a stale bookkeeping mismatch, or genuinely blocked work. Diagnose the first "
        "canonical blocker and cite exact evidence.\n"
        "5. You may repair only safe bookkeeping inconsistencies supported by canonical evidence. "
        "Do not rewrite task intent or conditions, answer product/architecture questions, merge, "
        "deploy, delete, reset, or expand the original request. Escalate any material ambiguity, "
        "destructive action, new authorization, or missing approval instead.\n"
        "6. For genuinely blocked authorized work, first avoid duplicate ownership by checking "
        "canonical running/recent agents. When the original todo authority covers diagnosis, "
        "repair, or relaunch and no equivalent owner is active, dispatch one tightly scoped durable "
        "`launch_subagent` with `request_id` equal to the todo ID, `backend=codex`, "
        "`background=true`, and `task` equal to the exact retained authoritative todo task (the "
        "tool rejects rewritten intent). Use the purpose-built description, debugging/recovery "
        "task kind, difficulty, delegated context routes, explicit non-goals, and verification to "
        "scope the recovery without expanding the task. A relaunch is allowed only when the "
        "original request or settled policy authorizes it; otherwise dispatch diagnosis only or "
        "escalate. Never use Hermes for scheduled work.\n"
        "7. If `authoritative_inbound.state` is not `verified`, delegation is forbidden. The "
        "scheduler already wrote an internal diagnostic event. Do not complete or fail the todo "
        "merely because custody is missing, and do not manufacture a user-facing completion; "
        "report an escalation with the diagnostic code.\n"
        "8. A successful `launch_subagent` call transfers the todo to "
        "`delegated_to_canonical_run` with manifest evidence, so it must not remain pending while "
        "the durable agent runs. The audit reply is a progress/reconciliation report, not the "
        "delegated agent's completion. For launches, report the returned run ID and "
        "manifest/full-log/result paths exactly.\n\n"
        "Structured audit context (redacted; UTC control-plane timestamps remain UTC):\n"
        f"```json\n{rendered_context}\n```"
    )


def _vp_todo_audit_context(
    *,
    store: Store,
    todo_path: object,
    retained: list[dict[str, Any]],
    job: ScheduledJob,
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    digest_items: list[dict[str, Any]] = []
    blocked = 0
    for item in retained:
        inbound = _todo_authoritative_inbound(store, item)
        delegation_candidate = (
            item.get("status") == vp_todo.PENDING and bool(item.get("task"))
        )
        blocked += int(
            delegation_candidate and inbound["state"] != "verified"
        )
        task = str(redact_payload(item.get("task") or ""))
        when = str(redact_payload(item.get("when") or ""))
        items.append(
            {
                "id": str(item.get("id") or ""),
                "task": task[:1200],
                "task_truncated": len(task) > 1200,
                "status": str(item.get("status") or ""),
                "updated_at": str(item.get("updated_at") or ""),
                "when": when[:600],
                "when_truncated": len(when) > 600,
                "conditional": bool(when.strip()),
                "delegation_candidate": delegation_candidate,
                "authoritative_inbound": inbound,
            }
        )
        digest_items.append(
            {
                "id": str(item.get("id") or ""),
                "task_sha256": hashlib.sha256(
                    str(item.get("task") or "").encode("utf-8")
                ).hexdigest(),
                "status": str(item.get("status") or ""),
                "updated_at": str(item.get("updated_at") or ""),
                "when": str(item.get("when") or ""),
                "inbound_state": inbound["state"],
                "inbound_diagnostic_code": inbound["diagnostic_code"],
            }
        )
    digest = hashlib.sha256(
        json.dumps(digest_items, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    previous_digest = str(job.payload.get("last_retained_todo_digest") or "")
    previous_unchanged = _nonnegative_int(
        job.payload.get("consecutive_unchanged_sweeps")
    )
    unchanged = previous_unchanged + 1 if previous_digest == digest else 0
    audit_id = deterministic_idempotency_key(
        "resident-vp-todo-audit", job.id, job.attempt_count, digest
    )
    pending_count = sum(1 for item in retained if item.get("status") == vp_todo.PENDING)
    return {
        "schema_version": "resident-vp-special-request-audit-context-v1",
        "audit_id": audit_id,
        "job": {
            "job_id": job.id,
            "attempt_count": job.attempt_count,
            "cadence_seconds": int(
                job.payload.get("interval_s") or 21600
            ),
        },
        "todo_source": {
            "path": str(todo_path),
            "authority": "read_todo_list tool over the retained VP special-request store",
            "full_list_tool": "read_todo_list",
            "full_list_arguments": {},
            "snapshot_is_redacted": True,
        },
        "summary": {
            "retained_count": len(retained),
            "pending_count": pending_count,
            "conditional_pending_count": sum(
                1
                for item in retained
                if item.get("status") == vp_todo.PENDING
                and bool(str(item.get("when") or "").strip())
            ),
            "delegation_blocked_count": blocked,
        },
        "repeat_state": {
            "retained_todo_digest": digest,
            "previous_retained_todo_digest": previous_digest or None,
            "unchanged_from_previous_sweep": previous_digest == digest,
            "consecutive_unchanged_sweeps": unchanged,
            "semantics": (
                "Digest covers retained todo identity/status/condition/update and inbound-evidence "
                "state only; canonical run/status evidence must still be read before classifying a loop."
            ),
        },
        "evidence_routes": {
            "todos": {"tool": "read_todo_list", "arguments": {}},
            "running_agents": {
                "tool": "read_context_node",
                "arguments": {"node_id": "agents/running"},
            },
            "recent_agents": {
                "tool": "read_context_node",
                "arguments": {"node_id": "agents/recent"},
            },
            "agent_search": {"tool": "search_context", "scope": "agents"},
            "canonical_status": {
                "tool": "read_context_node",
                "arguments": {"node_id": "status"},
            },
        },
        "items": items,
    }


def _todo_authoritative_inbound(
    store: Store, item: Mapping[str, Any]
) -> dict[str, Any]:
    provenance = item.get("launch_provenance")
    if not isinstance(provenance, Mapping):
        return _missing_inbound("missing_launch_provenance")
    if provenance.get("applicability") != "applicable":
        return _missing_inbound("launch_provenance_not_applicable")
    source_record_id = str(provenance.get("source_record_id") or "").strip()
    conversation_id = str(
        provenance.get("resident_conversation_id")
        or provenance.get("conversation_id")
        or ""
    ).strip()
    if not source_record_id or not conversation_id:
        return _missing_inbound(
            "incomplete_launch_provenance",
            source_record_id=source_record_id or None,
        )
    source = store.load_message(source_record_id)
    if source is None:
        return _missing_inbound(
            "source_record_missing", source_record_id=source_record_id
        )
    if source.direction != "inbound" or source.conversation_id != conversation_id:
        return _missing_inbound(
            "source_record_identity_mismatch", source_record_id=source_record_id
        )
    conversation = store.load_resident_conversation(conversation_id)
    if conversation is None:
        return _missing_inbound(
            "source_conversation_missing", source_record_id=source_record_id
        )
    reply_target = str(
        provenance.get("reply_to_message_id")
        or provenance.get("discord_message_id")
        or ""
    ).strip()
    if not source.discord_message_id or source.discord_message_id != reply_target:
        return _missing_inbound(
            "discord_reply_target_mismatch", source_record_id=source_record_id
        )
    if conversation.conversation_key != str(
        provenance.get("conversation_key") or ""
    ):
        return _missing_inbound(
            "source_conversation_identity_mismatch",
            source_record_id=source_record_id,
        )
    return {
        "state": "verified",
        "diagnostic_code": "none",
        "source_record_id": source_record_id,
        "resident_conversation_id": conversation_id,
        "reply_to_message_id": reply_target,
        "delegation_allowed": True,
    }


def _missing_inbound(
    diagnostic_code: str, *, source_record_id: str | None = None
) -> dict[str, Any]:
    return {
        "state": "missing",
        "diagnostic_code": diagnostic_code,
        "source_record_id": source_record_id,
        "delegation_allowed": False,
    }


def _nonnegative_int(value: object) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None
