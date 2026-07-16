"""Durable scheduled-job worker and resident job handlers."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import hashlib
import json
from pathlib import Path
import re
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
        retained, reconciliation_receipts = _reconcile_retired_todo_targets(
            todo_path, retained
        )
        pending = [
            item
            for item in retained
            if item["status"] == vp_todo.PENDING and item["task"]
        ]
        for receipt in reconciliation_receipts:
            self._emit_sink().log_system_event(
                level="info",
                category="system",
                event_type="resident_vp_todo_canonical_supersession",
                message="VP todo intent superseded by canonical initiative retirement",
                details={"job_id": job.id, **receipt},
                idempotency_key=deterministic_idempotency_key(
                    "resident-vp-todo-canonical-supersession",
                    receipt["todo_item_id"],
                    receipt["canonical_record_id"],
                    receipt["evidence"],
                ),
            )
        if not pending:
            self._emit_sink().log_system_event(
                level="info",
                category="system",
                event_type="resident_vp_todo_sweep",
                message="VP to-do sweep had no pending items",
                details={
                    "job_id": job.id,
                    "pending": 0,
                    "todo_reconciliation_count": len(reconciliation_receipts),
                },
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
            reconciliation_receipts=reconciliation_receipts,
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
                "report_only": True,
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
            payload.pop("last_audit_scope_digest", None)
            payload.pop("consecutive_unchanged_sweeps", None)
        else:
            repeat_state = audit_context["repeat_state"]
            payload["last_retained_todo_digest"] = repeat_state[
                "retained_todo_digest"
            ]
            payload["last_audit_scope_digest"] = repeat_state[
                "audit_scope_digest"
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
        "The scheduled six-hour VP special-request todo audit just fired. This is not a general "
        "project status report and it grants no execution authority. Read the structured snapshot below, "
        "then call `read_todo_list` with no arguments before making any decision; that tool is "
        "the authoritative full retained todo set, including failed and conditional items.\n\n"
        "Bounded mandate:\n"
        "1. Open the report with the exact scheduled scope label from `report_contract.scope_label`. "
        "Use separate `Current blockers`, `Pending bookkeeping reconciliation`, and `Historical "
        "bookkeeping` sections. Never phrase a historical or reconciliation-only item as current work.\n"
        "2. Separate each item's authorized outcome from current runtime health. A launch-intent "
        "item is satisfied when canonical evidence proves the exact requested chain/run was "
        "successfully launched with the requested identity and configuration. A later blocked "
        "milestone does not make that launch intent pending again. Safely reconcile that stale "
        "bookkeeping with `reconcile_todo_item`, recording the canonical run ID, durable "
        "evidence location, and reconciliation reason.\n"
        "3. A downstream item with a non-empty `when` remains genuinely conditional until the "
        "condition itself is canonically satisfied. Do not infer completion from an upstream "
        "launch, percent complete, a stale plan-local state, or overlapping work. Leave it pending "
        "and state the missing condition evidence.\n"
        "4. Use `read_context_node` on `agents/running` and `agents/recent` (or "
        "`search_context` scope `agents`) to reconcile stable todo/request IDs with canonical "
        "run IDs, status, lineage, manifest, full-log, result, and delivery evidence. Use the "
        "status route for canonical chain state and repair evidence; chain truth beats stale "
        "plan-local or prose summaries. Never claim success from a PID, acknowledgement, or "
        "artifact path alone.\n"
        "5. Treat `consecutive_unchanged_sweeps` as a loop signal, not automatic failure. Explain "
        "whether the unchanged state is an expected unsatisfied condition, an active canonical "
        "run, a stale bookkeeping mismatch, or genuinely blocked work. Diagnose the first "
        "canonical blocker and cite exact evidence.\n"
        "6. This audit is report-only. Do not launch or follow up agents, start/resume cloud work, "
        "edit audited workspaces, commit, merge, deploy, delete, reset, or expand the original "
        "request. Todo transitions happen only through the separately authorized reconciliation "
        "mechanism after durable evidence is validated.\n"
        "7. If `authoritative_inbound.state` is not `verified`, execution is forbidden. The "
        "scheduler already wrote an internal diagnostic event. Do not complete or fail the todo "
        "merely because custody is missing, and do not manufacture a user-facing completion; "
        "report an escalation with the diagnostic code.\n"
        "8. A canonical initiative-retirement record is proof of supersession only, not proof of "
        "completion. Report `completion_asserted: false` explicitly and cite the exact missing proof.\n\n"
        "Structured audit context (redacted; UTC control-plane timestamps remain UTC):\n"
        f"```json\n{rendered_context}\n```"
    )


def _vp_todo_audit_context(
    *,
    store: Store,
    todo_path: object,
    retained: list[dict[str, Any]],
    job: ScheduledJob,
    reconciliation_receipts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    digest_items: list[dict[str, Any]] = []
    blocked = 0
    for item in retained:
        inbound = _todo_authoritative_inbound(store, item)
        retirement_evidence = _todo_initiative_retirement_evidence(
            todo_path, item
        )
        target_slugs = _todo_initiative_chain_slugs(item)
        report_scope = _todo_report_scope(
            item, retirement_evidence, target_slugs=target_slugs
        )
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
                "report_scope": report_scope,
                "current_blocker": report_scope == "current_blocker",
                "historical_bookkeeping": report_scope == "historical_bookkeeping",
                "gather_reasons": (
                    ["canonical_target_initiative_retired"]
                    if retirement_evidence else []
                ),
                "initiative_retirement_evidence": retirement_evidence,
                "explicit_target_initiatives": target_slugs,
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
                "report_scope": report_scope,
                "retirement_evidence_sha256": [
                    row["source_sha256"] for row in retirement_evidence
                ],
            }
        )
    retained_digest = hashlib.sha256(
        json.dumps(digest_items, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    audit_scope_digest = hashlib.sha256(
        json.dumps(
            [
                item
                for item in digest_items
                if item["report_scope"] != "historical_bookkeeping"
            ],
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    previous_digest = str(
        job.payload.get("last_audit_scope_digest")
        or job.payload.get("last_retained_todo_digest")
        or ""
    )
    previous_unchanged = _nonnegative_int(
        job.payload.get("consecutive_unchanged_sweeps")
    )
    unchanged = previous_unchanged + 1 if previous_digest == audit_scope_digest else 0
    audit_id = deterministic_idempotency_key(
        "resident-vp-todo-audit", job.id, job.attempt_count, audit_scope_digest
    )
    pending_count = sum(1 for item in retained if item.get("status") == vp_todo.PENDING)
    current_blocker_ids = [
        item["id"] for item in items if item["report_scope"] == "current_blocker"
    ]
    pending_reconciliation_ids = [
        item["id"]
        for item in items
        if item["report_scope"] == "pending_reconciliation"
    ]
    historical_ids = [
        item["id"]
        for item in items
        if item["report_scope"] == "historical_bookkeeping"
    ]
    return {
        "schema_version": "resident-vp-special-request-audit-context-v2",
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
            "current_blocker_count": len(current_blocker_ids),
            "pending_reconciliation_count": len(pending_reconciliation_ids),
            "historical_bookkeeping_count": len(historical_ids),
            "current_blocker_ids": current_blocker_ids,
            "pending_reconciliation_ids": pending_reconciliation_ids,
            "historical_bookkeeping_ids": historical_ids,
        },
        "repeat_state": {
            "retained_todo_digest": retained_digest,
            "audit_scope_digest": audit_scope_digest,
            "previous_retained_todo_digest": previous_digest or None,
            "unchanged_from_previous_sweep": previous_digest == audit_scope_digest,
            "consecutive_unchanged_sweeps": unchanged,
            "semantics": (
                "The audit-scope digest excludes historical bookkeeping and covers current/reconciliation "
                "identity, status, condition, update, and inbound-evidence state. The retained digest "
                "still accounts for every item. Canonical run/status evidence must still be read before "
                "classifying a loop."
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
        "report_contract": {
            "scope_label": "Scheduled VP special-request todo audit (not general project status)",
            "sections": [
                "Current blockers",
                "Pending bookkeeping reconciliation",
                "Historical bookkeeping",
            ],
            "current_claim_rule": (
                "Only items with report_scope=current_blocker may be described as current blockers."
            ),
            "retirement_rule": (
                "Canonical retirement proves supersession, never completion, unless the record "
                "explicitly asserts completion with durable evidence."
            ),
        },
        "dispatch_summary": {
            "mode": "report_only",
            "agent_launches": 0,
            "cloud_starts_or_resumes": 0,
            "audited_workspace_edits": 0,
            "git_mutations": 0,
            "allowed_mutation": "separately authorized todo reconciliation only",
            "todo_reconciliations": list(reconciliation_receipts or []),
        },
        "items": items,
    }


_INITIATIVE_CHAIN_REF = re.compile(
    r"(?:^|[\s`'\"])(?:\./)?\.megaplan/initiatives/"
    r"(?P<slug>[a-z0-9][a-z0-9-]*)/chain\.yaml(?:$|[\s`'\",;)])"
)


def _todo_project_root(todo_path: object) -> Path:
    resolved = Path(todo_path).expanduser().resolve()
    megaplan_dir = next(
        (parent for parent in resolved.parents if parent.name == ".megaplan"),
        None,
    )
    return megaplan_dir.parent if megaplan_dir is not None else resolved.parent


def _todo_initiative_retirement_evidence(
    todo_path: object, item: Mapping[str, Any]
) -> list[dict[str, Any]]:
    """Gather exact initiative retirement markers referenced as launch targets."""

    slugs = _todo_initiative_chain_slugs(item)
    root = _todo_project_root(todo_path)
    evidence: list[dict[str, Any]] = []
    for slug in slugs:
        marker = root / ".megaplan" / "initiatives" / slug / ".retired"
        try:
            raw = marker.read_bytes()
            payload = json.loads(raw)
        except (OSError, ValueError, TypeError):
            continue
        if not isinstance(payload, Mapping):
            continue
        if payload.get("status") != "retired" or payload.get("initiative") != slug:
            continue
        truthfulness = payload.get("truthfulness")
        evidence.append(
            {
                "initiative": slug,
                "state": "retired",
                "retirement_id": str(payload.get("retirement_id") or ""),
                "superseded_by": str(payload.get("superseded_by") or ""),
                "completion_asserted": bool(
                    isinstance(truthfulness, Mapping)
                    and truthfulness.get("completion_asserted") is True
                ),
                "source_ref": str(marker),
                "source_sha256": hashlib.sha256(raw).hexdigest(),
                "gather_reason": "canonical_target_initiative_retired",
            }
        )
    return evidence


def _todo_initiative_chain_slugs(item: Mapping[str, Any]) -> list[str]:
    text = "\n".join(str(item.get(key) or "") for key in ("task", "when"))
    return sorted(
        {match.group("slug") for match in _INITIATIVE_CHAIN_REF.finditer(text)}
    )


def _reconcile_retired_todo_targets(
    todo_path: object, retained: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Apply only exact, evidence-backed initiative-retirement supersessions."""

    receipts: list[dict[str, Any]] = []
    for item in retained:
        if item.get("status") != vp_todo.PENDING:
            continue
        target_slugs = _todo_initiative_chain_slugs(item)
        retirement = _todo_initiative_retirement_evidence(todo_path, item)
        if not target_slugs or len(retirement) != len(target_slugs):
            continue
        if any(
            not row["retirement_id"] or not row["superseded_by"]
            for row in retirement
        ):
            continue
        canonical_record_id = "+".join(
            f"initiative-retirement:{row['retirement_id']}->{row['superseded_by']}"
            for row in retirement
        )
        evidence = ";".join(
            f"{row['source_ref']}#sha256={row['source_sha256']}"
            for row in retirement
        )
        resolution = (
            "Every explicit target initiative has a canonical retirement record with a "
            "replacement owner; this supersedes the retained launch intent without asserting "
            "completion."
        )
        resolved = vp_todo.supersede_by_record(
            Path(todo_path),
            str(item.get("id") or ""),
            canonical_record_id=canonical_record_id,
            evidence=evidence,
            resolution=resolution,
        )
        if resolved is None:
            continue
        receipts.append(
            {
                "todo_item_id": resolved["id"],
                "transition": f"{vp_todo.PENDING}->{vp_todo.SUPERSEDED_BY_RECORD}",
                "canonical_record_id": canonical_record_id,
                "evidence": evidence,
                "completion_asserted": False,
            }
        )
    return vp_todo.load_items(Path(todo_path)), receipts


def _todo_report_scope(
    item: Mapping[str, Any],
    retirement_evidence: list[dict[str, Any]],
    *,
    target_slugs: list[str],
) -> str:
    status = str(item.get("status") or "")
    if status == vp_todo.PENDING:
        if target_slugs and len(retirement_evidence) == len(target_slugs):
            return "pending_reconciliation"
        return "current_blocker"
    if status == vp_todo.BLOCKED:
        return "current_blocker"
    if status == vp_todo.DELEGATED:
        return "active_external_custody"
    return "historical_bookkeeping"


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
