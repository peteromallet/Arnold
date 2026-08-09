from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, Sequence

from arnold_pipelines.megaplan.schemas import AutomationActor, CloudRun, ControlMessage, EpicLock, ExecutionLease, MigrationRun, ProgressEvent, ResidentConversation, ResidentUserPreference, ScheduledJob
from arnold_pipelines.megaplan.schemas.base import utc_now

from ..base import CloudRunInput, ControlMessageInput, LeaseConflict, LockConflict, ProgressEventInput, ResidentConversationInput, ScheduledJobInput
from .common import _new_id, _utc_key


class FileOperationsMixin:
    def save_migration_run(self, run: MigrationRun) -> MigrationRun:
        self._save_model(self._migration_run_path(run.id), run, journal_root=self.root)
        return run

    def create_migration_run(self, run: MigrationRun) -> MigrationRun:
        path = self._migration_run_path(run.id)
        if path.exists():
            raise FileExistsError(run.id)
        return self.save_migration_run(run)

    def load_migration_run(self, migration_id: str) -> MigrationRun | None:
        return self._load_model(self._migration_run_path(migration_id), MigrationRun)

    def update_migration_run(self, migration_id: str, **changes: Any) -> MigrationRun:
        current = self.load_migration_run(migration_id)
        if current is None:
            raise FileNotFoundError(migration_id)
        data = current.model_dump()
        data.update(changes)
        data["updated_at"] = utc_now()
        updated = MigrationRun.model_validate(data)
        self.save_migration_run(updated)
        return updated

    def heartbeat_migration(self, migration_id: str, ttl_seconds: int) -> MigrationRun:
        return self.update_migration_run(
            migration_id,
            updated_at=utc_now(),
            expires_at=datetime.now(UTC) + timedelta(seconds=ttl_seconds),
        )

    def find_active_migration_for_epic(self, epic_id: str) -> MigrationRun | None:
        """Audit-only local migration lookup; DB migration_runs coordinate correctness."""
        active = [
            run
            for run in self._migration_runs()
            if run.epic_id == epic_id
            and run.completed_at is None
            and run.expires_at > datetime.now(UTC)
        ]
        active.sort(key=lambda run: run.started_at, reverse=True)
        return active[0] if active else None

    # ------------------------------------------------------------------
    # Leases / locks
    # ------------------------------------------------------------------

    def acquire_execution_lease(
        self,
        plan_id: str,
        holder_id: str,
        worker_kind: str,
        ttl_seconds: int,
        *,
        epic_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> ExecutionLease:
        current = self.get_active_lease(plan_id)
        if current is not None and current.holder_id != holder_id:
            raise LeaseConflict(plan_id)
        plan = self.load_plan(plan_id)
        lease_epic_id = epic_id if epic_id is not None else (plan.epic_id if plan else None)
        lease = ExecutionLease(
            plan_id=plan_id,
            epic_id=lease_epic_id,
            holder_id=holder_id,
            phase=plan.current_state if plan else "unknown",
            worker_kind=worker_kind,
            acquired_at=utc_now(),
            heartbeat_at=utc_now(),
            expires_at=datetime.now(UTC) + timedelta(seconds=ttl_seconds),
        )
        self._save_model(self._lease_path(plan_id), lease, journal_root=self.root)
        return lease

    def find_active_leases_for_epic(self, epic_id: str) -> list[ExecutionLease]:
        now = datetime.now(UTC)
        leases = [
            lease
            for lease in self._iter_models(self._leases_dir(), ExecutionLease)
            if lease.epic_id == epic_id and lease.expires_at > now
        ]
        leases.sort(key=lambda lease: (lease.expires_at, lease.plan_id))
        return leases

    def heartbeat_lease(self, plan_id: str, holder_id: str,
        *,
        idempotency_key: str | None = None,
    ) -> ExecutionLease:
        lease = self.get_active_lease(plan_id)
        if lease is None or lease.holder_id != holder_id:
            raise LeaseConflict(plan_id)
        ttl_seconds = max(int((lease.expires_at - lease.heartbeat_at).total_seconds()), 60)
        return self._update_model(
            self._lease_path(plan_id),
            ExecutionLease,
            journal_root=self.root,
            heartbeat_at=utc_now(),
            expires_at=datetime.now(UTC) + timedelta(seconds=ttl_seconds),
        )

    def release_lease(self, plan_id: str, holder_id: str,
        *,
        idempotency_key: str | None = None,
    ) -> None:
        lease = self.get_active_lease(plan_id)
        if lease is None or lease.holder_id != holder_id:
            return
        self._delete_file(self._lease_path(plan_id))

    def get_active_lease(self, plan_id: str) -> ExecutionLease | None:
        lease = self._load_model(self._lease_path(plan_id), ExecutionLease)
        if lease is None:
            return None
        if lease.expires_at <= datetime.now(UTC):
            self._delete_file(self._lease_path(plan_id))
            return None
        return lease

    def acquire_lock(self, epic_id: str, holder_id: str, ttl_seconds: int,
        *,
        idempotency_key: str | None = None,
    ) -> EpicLock:
        current = self._load_model(self._lock_path(epic_id), EpicLock)
        if current is not None and current.expires_at > datetime.now(UTC) and current.holder_id != holder_id:
            raise LockConflict(epic_id)
        lock = EpicLock(
            epic_id=epic_id,
            holder_id=holder_id,
            acquired_at=utc_now(),
            expires_at=datetime.now(UTC) + timedelta(seconds=ttl_seconds),
        )
        self._save_model(self._lock_path(epic_id), lock, journal_root=self.root)
        return lock

    def release_lock(self, epic_id: str, holder_id: str,
        *,
        idempotency_key: str | None = None,
    ) -> None:
        current = self._load_model(self._lock_path(epic_id), EpicLock)
        if current is None or current.holder_id != holder_id:
            return
        self._delete_file(self._lock_path(epic_id))

    # ------------------------------------------------------------------
    # Control plane / progress
    # ------------------------------------------------------------------

    def put_control_message(self, msg: ControlMessageInput,
        *,
        idempotency_key: str | None = None,
    ) -> ControlMessage:
        msg = ControlMessageInput.model_validate(msg.model_dump() if isinstance(msg, ControlMessageInput) else msg)
        control = ControlMessage(
            id=_new_id("ctrl"),
            epic_id=msg.epic_id,
            actor_id=msg.actor_id,
            intent=msg.intent,
            target_id=msg.target_id,
            payload=msg.payload,
            idempotency_key=msg.idempotency_key,
            created_at=utc_now(),
        )
        self._save_model(self._control_message_path(control.id), control, journal_root=self.root)
        return control

    def claim_pending_control_messages(self, *, processor_id: str, max: int = 10,
        idempotency_key: str | None = None,
    ) -> list[ControlMessage]:
        pending = [
            row
            for row in self._control_messages()
            if row.claimed_at is None and row.processed_at is None
        ]
        pending.sort(key=lambda row: (_utc_key(row.created_at), row.id))
        claimed: list[ControlMessage] = []
        for row in pending[:max]:
            claimed.append(
                self._update_model(
                    self._control_message_path(row.id),
                    ControlMessage,
                    journal_root=self.root,
                    processor_id=processor_id,
                    claimed_at=utc_now(),
                )
            )
        return claimed

    def recover_stale_control_messages(
        self,
        *,
        processor_id: str,
        older_than_seconds: int,
        max: int = 10,
        idempotency_key: str | None = None,
    ) -> list[ControlMessage]:
        cutoff = datetime.now(UTC) - timedelta(seconds=older_than_seconds)
        stale = [
            row
            for row in self._control_messages()
            if row.processed_at is None
            and row.claimed_at is not None
            and row.claimed_at <= cutoff
        ]
        stale.sort(key=lambda row: (_utc_key(row.claimed_at), row.id))
        recovered: list[ControlMessage] = []
        for row in stale[:max]:
            recovered.append(
                self._update_model(
                    self._control_message_path(row.id),
                    ControlMessage,
                    journal_root=self.root,
                    processor_id=processor_id,
                    claimed_at=utc_now(),
                )
            )
        return recovered

    def list_stale_control_messages(
        self,
        *,
        older_than_seconds: int,
        limit: int = 10,
    ) -> list[ControlMessage]:
        cutoff = datetime.now(UTC) - timedelta(seconds=older_than_seconds)
        stale = [
            row
            for row in self._control_messages()
            if row.processed_at is None
            and row.claimed_at is not None
            and row.claimed_at <= cutoff
        ]
        stale.sort(key=lambda row: (_utc_key(row.claimed_at), row.id))
        return stale[:limit]

    def mark_control_message_processed(self, msg_id: str, result: dict[str, Any],
        *,
        idempotency_key: str | None = None,
    ) -> None:
        self._update_model(
            self._control_message_path(msg_id),
            ControlMessage,
            journal_root=self.root,
            result=result,
            processed_at=utc_now(),
        )

    # ------------------------------------------------------------------
    # Resident orchestration
    # ------------------------------------------------------------------

    def upsert_resident_conversation(
        self,
        conversation: ResidentConversationInput,
        *,
        idempotency_key: str | None = None,
    ) -> ResidentConversation:
        existing = self.get_resident_conversation_by_key(
            transport=conversation.transport,
            conversation_key=conversation.conversation_key,
        )
        now = utc_now()
        data = conversation.model_dump(mode="python")
        if existing is not None:
            changes = {
                key: value
                for key, value in data.items()
                if key not in {"transport", "conversation_key"} and value is not None
            }
            changes["updated_at"] = now
            return self._update_model(
                self._resident_conversation_path(existing.id),
                ResidentConversation,
                journal_root=self.root,
                **changes,
            )
        resident = ResidentConversation(
            id=_new_id("rconv"),
            **data,
            created_at=now,
            updated_at=now,
            last_active_at=now,
        )
        self._save_model(self._resident_conversation_path(resident.id), resident, journal_root=self.root)
        return resident

    def load_resident_conversation(self, conversation_id: str) -> ResidentConversation | None:
        return self._load_model(self._resident_conversation_path(conversation_id), ResidentConversation)

    def get_resident_conversation_by_key(
        self,
        *,
        transport: str,
        conversation_key: str,
    ) -> ResidentConversation | None:
        for row in self._resident_conversations():
            if row.transport == transport and row.conversation_key == conversation_key:
                return row
        return None

    def list_resident_conversations(
        self,
        *,
        transport: str | None = None,
        active_epic_id: str | None = None,
        limit: int = 50,
    ) -> list[ResidentConversation]:
        rows = self._resident_conversations()
        if transport is not None:
            rows = [row for row in rows if row.transport == transport]
        if active_epic_id is not None:
            rows = [row for row in rows if row.active_epic_id == active_epic_id]
        rows.sort(key=lambda row: (_utc_key(row.last_active_at), row.id), reverse=True)
        return rows[:limit]

    def update_resident_conversation(
        self,
        conversation_id: str,
        *,
        idempotency_key: str | None = None,
        **changes: Any,
    ) -> ResidentConversation:
        changes.setdefault("updated_at", utc_now())
        return self._update_model(
            self._resident_conversation_path(conversation_id),
            ResidentConversation,
            journal_root=self.root,
            **changes,
        )

    def load_resident_user_preference(
        self, *, transport: str, user_id: str
    ) -> ResidentUserPreference | None:
        return self._load_model(
            self._resident_user_preference_path(transport, user_id),
            ResidentUserPreference,
        )

    def upsert_resident_user_preference(
        self,
        *,
        transport: str,
        user_id: str,
        timezone_name: str | None,
        metadata: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> ResidentUserPreference:
        path = self._resident_user_preference_path(transport, user_id)
        existing = self._load_model(path, ResidentUserPreference)
        now = utc_now()
        if existing is not None:
            return self._update_model(
                path,
                ResidentUserPreference,
                journal_root=self.root,
                timezone_name=timezone_name,
                metadata=dict(metadata) if metadata is not None else existing.metadata,
                updated_at=now,
            )
        preference = ResidentUserPreference(
            transport=transport,
            user_id=user_id,
            timezone_name=timezone_name,
            metadata=dict(metadata or {}),
            created_at=now,
            updated_at=now,
        )
        self._save_model(path, preference, journal_root=self.root)
        return preference

    def create_scheduled_job(
        self,
        job: ScheduledJobInput,
        *,
        idempotency_key: str | None = None,
    ) -> ScheduledJob:
        scheduled = ScheduledJob(
            id=_new_id("job"),
            **job.model_dump(mode="python"),
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        self._save_model(self._scheduled_job_path(scheduled.id), scheduled, journal_root=self.root)
        return scheduled

    def load_scheduled_job(self, job_id: str) -> ScheduledJob | None:
        return self._load_model(self._scheduled_job_path(job_id), ScheduledJob)

    def update_scheduled_job(
        self,
        job_id: str,
        *,
        idempotency_key: str | None = None,
        **changes: Any,
    ) -> ScheduledJob:
        changes.setdefault("updated_at", utc_now())
        return self._update_model(
            self._scheduled_job_path(job_id),
            ScheduledJob,
            journal_root=self.root,
            **changes,
        )

    def claim_due_scheduled_jobs(
        self,
        *,
        worker_id: str,
        now: datetime | None = None,
        stale_after_seconds: int | None = None,
        max: int = 10,
        job_type: str | None = None,
        idempotency_key: str | None = None,
    ) -> list[ScheduledJob]:
        effective_now = now or utc_now()
        stale_cutoff = (
            effective_now - timedelta(seconds=stale_after_seconds)
            if stale_after_seconds is not None
            else None
        )
        due: list[ScheduledJob] = []
        for row in self._scheduled_jobs():
            if job_type is not None and row.job_type != job_type:
                continue
            pending_due = row.status == "pending" and row.scheduled_for <= effective_now
            stale_claim = (
                row.status == "claimed"
                and stale_cutoff is not None
                and row.claimed_at is not None
                and row.claimed_at <= stale_cutoff
            )
            if pending_due or stale_claim:
                due.append(row)
        due.sort(key=lambda row: (_utc_key(row.scheduled_for), row.id))
        claimed: list[ScheduledJob] = []
        for row in due[:max]:
            claimed.append(
                self.update_scheduled_job(
                    row.id,
                    status="claimed",
                    claimed_by=worker_id,
                    claimed_at=effective_now,
                    attempt_count=row.attempt_count + 1,
                    idempotency_key=idempotency_key,
                )
            )
        return claimed

    def list_scheduled_jobs(
        self,
        *,
        conversation_id: str | None = None,
        cloud_run_id: str | None = None,
        status: str | None = None,
        job_type: str | None = None,
        limit: int = 50,
    ) -> list[ScheduledJob]:
        rows = self._scheduled_jobs()
        if conversation_id is not None:
            rows = [row for row in rows if row.conversation_id == conversation_id]
        if cloud_run_id is not None:
            rows = [row for row in rows if row.cloud_run_id == cloud_run_id]
        if status is not None:
            rows = [row for row in rows if row.status == status]
        if job_type is not None:
            rows = [row for row in rows if row.job_type == job_type]
        rows.sort(key=lambda row: (_utc_key(row.scheduled_for), row.id), reverse=True)
        return rows[:limit]

    def create_cloud_run(
        self,
        run: CloudRunInput,
        *,
        idempotency_key: str | None = None,
    ) -> CloudRun:
        effective_key = idempotency_key or run.idempotency_key
        if effective_key is not None:
            for existing in self._cloud_runs():
                if existing.idempotency_key == effective_key:
                    return existing
        cloud_run = CloudRun(
            id=_new_id("cloud"),
            **{**run.model_dump(mode="python"), "idempotency_key": effective_key},
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        self._save_model(self._cloud_run_path(cloud_run.id), cloud_run, journal_root=self.root)
        return cloud_run

    def load_cloud_run(self, run_id: str) -> CloudRun | None:
        return self._load_model(self._cloud_run_path(run_id), CloudRun)

    def update_cloud_run(
        self,
        run_id: str,
        *,
        idempotency_key: str | None = None,
        **changes: Any,
    ) -> CloudRun:
        changes.setdefault("updated_at", utc_now())
        return self._update_model(
            self._cloud_run_path(run_id),
            CloudRun,
            journal_root=self.root,
            **changes,
        )

    def list_cloud_runs(
        self,
        *,
        conversation_id: str | None = None,
        epic_id: str | None = None,
        plan_id: str | None = None,
        sprint_id: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[CloudRun]:
        rows = self._cloud_runs()
        if conversation_id is not None:
            rows = [row for row in rows if row.conversation_id == conversation_id]
        if epic_id is not None:
            rows = [row for row in rows if row.epic_id == epic_id]
        if plan_id is not None:
            rows = [row for row in rows if row.plan_id == plan_id]
        if sprint_id is not None:
            rows = [row for row in rows if row.sprint_id == sprint_id]
        if status is not None:
            rows = [row for row in rows if row.status == status]
        rows.sort(key=lambda row: (_utc_key(row.created_at), row.id), reverse=True)
        return rows[:limit]

    def append_progress_event(self, event: ProgressEventInput,
        *,
        idempotency_key: str | None = None,
    ) -> ProgressEvent:
        effective_idempotency_key = idempotency_key or event.idempotency_key
        if effective_idempotency_key is not None:
            for existing in self._progress_events():
                if existing.idempotency_key == effective_idempotency_key:
                    return existing
        progress = ProgressEvent(
            id=_new_id("prog"),
            epic_id=event.epic_id,
            plan_id=event.plan_id,
            sprint_id=event.sprint_id,
            idempotency_key=effective_idempotency_key,
            kind=event.kind,
            summary=event.summary,
            details=event.details,
            occurred_at=utc_now(),
        )
        self._save_model(self._progress_event_path(progress.id), progress, journal_root=self.root)
        return progress

    def list_progress_events(
        self,
        *,
        plan_id: str | None = None,
        epic_id: str | None = None,
        since: datetime | None = None,
    ) -> list[ProgressEvent]:
        events = self._progress_events()
        if plan_id is not None:
            events = [row for row in events if row.plan_id == plan_id]
        if epic_id is not None:
            events = [row for row in events if row.epic_id == epic_id]
        if since is not None:
            events = [row for row in events if row.occurred_at >= since]
        events.sort(key=lambda row: (row.occurred_at, row.id))
        return events

    # ------------------------------------------------------------------
    # Automation actors
    # ------------------------------------------------------------------

    def create_automation_actor(
        self,
        *,
        actor_id: str,
        name: str,
        granted_epic_ids: str | Sequence[str],
        actor_kind: str,
        idempotency_key: str | None = None,
    ) -> AutomationActor:
        actor = AutomationActor(
            id=actor_id,
            name=name,
            granted_epic_ids=granted_epic_ids,
            actor_kind=actor_kind,
            created_at=utc_now(),
        )
        self._save_model(self._automation_actor_path(actor.id), actor, journal_root=self.root)
        return actor

    def load_automation_actor(self, actor_id: str) -> AutomationActor | None:
        return self._load_model(self._automation_actor_path(actor_id), AutomationActor)

    def update_automation_actor(self, actor_id: str, *, idempotency_key: str | None = None,
        **changes: Any) -> AutomationActor:
        if "last_active_at" not in changes:
            changes["last_active_at"] = utc_now()
        return self._update_model(self._automation_actor_path(actor_id), AutomationActor, journal_root=self.root, **changes)
