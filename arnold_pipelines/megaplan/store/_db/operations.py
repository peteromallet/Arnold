"""Operational orchestration mixins for DBStore."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from arnold_pipelines.megaplan.schemas import AutomationActor, CloudRun, ControlMessage, ProgressEvent, ResidentConversation, ResidentUserPreference, ScheduledJob
from arnold_pipelines.megaplan.store.base import CloudRunInput, ControlMessageInput, ProgressEventInput, ResidentConversationInput, RevisionConflict, ScheduledJobInput

from .common import _jb

class DBOperationsMixin:
    def put_control_message(self, msg: ControlMessageInput,
        *,
        idempotency_key: str | None = None,
    ) -> ControlMessage:
        self._require_actor()
        msg = ControlMessageInput.model_validate(msg.model_dump() if isinstance(msg, ControlMessageInput) else msg)
        conn = self._get_conn()
        row = conn.execute(
            """
            INSERT INTO control_messages (id, epic_id, actor_id, intent, target_id, payload, idempotency_key)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (idempotency_key) DO UPDATE SET id = EXCLUDED.id
            RETURNING *
            """,
            [
                str(uuid.uuid4()), msg.epic_id, msg.actor_id, msg.intent,
                msg.target_id, _jb(dict(msg.payload)), msg.idempotency_key,
            ],
        ).fetchone()
        return ControlMessage(**row)

    def claim_pending_control_messages(
        self,
        *,
        processor_id: str,
        max: int = 10,
        idempotency_key: str | None = None,
    ) -> list[ControlMessage]:
        conn = self._get_conn()
        rows = conn.execute(
            """
            UPDATE control_messages
            SET claimed_at = now(), processor_id = %s
            WHERE id IN (
                SELECT id FROM control_messages
                WHERE claimed_at IS NULL
                ORDER BY created_at
                LIMIT %s
                FOR UPDATE SKIP LOCKED
            )
            RETURNING *
            """,
            [processor_id, max],
        ).fetchall()
        return [ControlMessage(**row) for row in rows]

    def mark_control_message_processed(
        self, msg_id: str, result: dict[str, Any],
        *,
        idempotency_key: str | None = None,
    ) -> None:
        conn = self._get_conn()
        conn.execute(
            "UPDATE control_messages SET processed_at = now(), result = %s WHERE id = %s",
            [_jb(result), msg_id],
        )

    def recover_stale_control_messages(
        self,
        *,
        processor_id: str,
        older_than_seconds: int,
        max: int = 10,
        idempotency_key: str | None = None,
    ) -> list[ControlMessage]:
        conn = self._get_conn()
        rows = conn.execute(
            """
            UPDATE control_messages
            SET claimed_at = now(), processor_id = %s
            WHERE id IN (
                SELECT id FROM control_messages
                WHERE processed_at IS NULL
                  AND claimed_at IS NOT NULL
                  AND claimed_at < now() - make_interval(secs => %s)
                ORDER BY claimed_at, created_at
                LIMIT %s
                FOR UPDATE SKIP LOCKED
            )
            RETURNING *
            """,
            [processor_id, older_than_seconds, max],
        ).fetchall()
        return [ControlMessage(**row) for row in rows]

    def list_stale_control_messages(
        self,
        *,
        older_than_seconds: int,
        limit: int = 10,
    ) -> list[ControlMessage]:
        conn = self._get_conn()
        rows = conn.execute(
            """
            SELECT * FROM control_messages
            WHERE processed_at IS NULL
              AND claimed_at IS NOT NULL
              AND claimed_at < now() - make_interval(secs => %s)
            ORDER BY claimed_at, created_at
            LIMIT %s
            """,
            [older_than_seconds, limit],
        ).fetchall()
        return [ControlMessage(**row) for row in rows]

    def upsert_resident_conversation(
        self,
        conversation: ResidentConversationInput,
        *,
        idempotency_key: str | None = None,
    ) -> ResidentConversation:
        conn = self._get_conn()
        row = conn.execute(
            """
            INSERT INTO resident_conversations (
                id, transport, conversation_key, active_epic_id, guild_id,
                channel_id, thread_id, dm_user_id, metadata, last_active_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, now())
            ON CONFLICT (transport, conversation_key) DO UPDATE SET
                active_epic_id = COALESCE(EXCLUDED.active_epic_id, resident_conversations.active_epic_id),
                guild_id = COALESCE(EXCLUDED.guild_id, resident_conversations.guild_id),
                channel_id = COALESCE(EXCLUDED.channel_id, resident_conversations.channel_id),
                thread_id = COALESCE(EXCLUDED.thread_id, resident_conversations.thread_id),
                dm_user_id = COALESCE(EXCLUDED.dm_user_id, resident_conversations.dm_user_id),
                metadata = EXCLUDED.metadata,
                updated_at = now(),
                last_active_at = now()
            RETURNING *
            """,
            [
                str(uuid.uuid4()), conversation.transport, conversation.conversation_key,
                conversation.active_epic_id, conversation.guild_id, conversation.channel_id,
                conversation.thread_id, conversation.dm_user_id, _jb(dict(conversation.metadata)),
            ],
        ).fetchone()
        return ResidentConversation(**row)

    def load_resident_conversation(self, conversation_id: str) -> ResidentConversation | None:
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM resident_conversations WHERE id = %s", [conversation_id]).fetchone()
        return ResidentConversation(**row) if row else None

    def get_resident_conversation_by_key(
        self,
        *,
        transport: str,
        conversation_key: str,
    ) -> ResidentConversation | None:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM resident_conversations WHERE transport = %s AND conversation_key = %s",
            [transport, conversation_key],
        ).fetchone()
        return ResidentConversation(**row) if row else None

    def list_resident_conversations(
        self,
        *,
        transport: str | None = None,
        active_epic_id: str | None = None,
        limit: int = 50,
    ) -> list[ResidentConversation]:
        conn = self._get_conn()
        conditions: list[str] = []
        values: list[Any] = []
        for column, value in (
            ("transport", transport),
            ("active_epic_id", active_epic_id),
        ):
            if value is not None:
                conditions.append(f"{column} = %s")
                values.append(value)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        rows = conn.execute(
            f"SELECT * FROM resident_conversations {where} ORDER BY last_active_at DESC, id DESC LIMIT %s",
            [*values, limit],
        ).fetchall()
        return [ResidentConversation(**row) for row in rows]

    def update_resident_conversation(
        self,
        conversation_id: str,
        *,
        idempotency_key: str | None = None,
        **changes: Any,
    ) -> ResidentConversation:
        conn = self._get_conn()
        if not changes:
            row = conn.execute("SELECT * FROM resident_conversations WHERE id = %s", [conversation_id]).fetchone()
            if row is None:
                raise RevisionConflict(f"Resident conversation {conversation_id!r} not found")
            return ResidentConversation(**row)
        jsonb_cols = frozenset({"metadata"})
        set_parts = [f"{key} = %s" for key in changes]
        set_parts.append("updated_at = now()")
        values = [_jb(value) if key in jsonb_cols else value for key, value in changes.items()]
        values.append(conversation_id)
        row = conn.execute(
            f"UPDATE resident_conversations SET {', '.join(set_parts)} WHERE id = %s RETURNING *",
            values,
        ).fetchone()
        if row is None:
            raise RevisionConflict(f"Resident conversation {conversation_id!r} not found")
        return ResidentConversation(**row)

    def load_resident_user_preference(
        self, *, transport: str, user_id: str
    ) -> ResidentUserPreference | None:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM resident_user_preferences WHERE transport = %s AND user_id = %s",
            [transport, user_id],
        ).fetchone()
        return ResidentUserPreference(**row) if row else None

    def upsert_resident_user_preference(
        self,
        *,
        transport: str,
        user_id: str,
        timezone_name: str | None,
        metadata: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> ResidentUserPreference:
        conn = self._get_conn()
        row = conn.execute(
            """
            INSERT INTO resident_user_preferences (
                transport, user_id, timezone_name, metadata
            ) VALUES (%s, %s, %s, %s)
            ON CONFLICT (transport, user_id) DO UPDATE SET
                timezone_name = EXCLUDED.timezone_name,
                metadata = CASE
                    WHEN %s THEN EXCLUDED.metadata
                    ELSE resident_user_preferences.metadata
                END,
                updated_at = now()
            RETURNING *
            """,
            [
                transport,
                user_id,
                timezone_name,
                _jb(dict(metadata or {})),
                metadata is not None,
            ],
        ).fetchone()
        return ResidentUserPreference(**row)

    def create_scheduled_job(
        self,
        job: ScheduledJobInput,
        *,
        idempotency_key: str | None = None,
    ) -> ScheduledJob:
        conn = self._get_conn()
        row = conn.execute(
            """
            INSERT INTO scheduled_jobs (
                id, job_type, conversation_id, cloud_run_id, epic_id, payload,
                scheduled_for, max_attempts
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            [
                str(uuid.uuid4()), job.job_type, job.conversation_id,
                job.cloud_run_id, job.epic_id, _jb(dict(job.payload)),
                job.scheduled_for, job.max_attempts,
            ],
        ).fetchone()
        return ScheduledJob(**row)

    def load_scheduled_job(self, job_id: str) -> ScheduledJob | None:
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM scheduled_jobs WHERE id = %s", [job_id]).fetchone()
        return ScheduledJob(**row) if row else None

    def update_scheduled_job(
        self,
        job_id: str,
        *,
        idempotency_key: str | None = None,
        **changes: Any,
    ) -> ScheduledJob:
        conn = self._get_conn()
        if not changes:
            row = conn.execute("SELECT * FROM scheduled_jobs WHERE id = %s", [job_id]).fetchone()
            if row is None:
                raise RevisionConflict(f"Scheduled job {job_id!r} not found")
            return ScheduledJob(**row)
        jsonb_cols = frozenset({"payload"})
        set_parts = [f"{key} = %s" for key in changes]
        set_parts.append("updated_at = now()")
        if changes.get("status") == "fired" and "fired_at" not in changes:
            set_parts.append("fired_at = now()")
        if changes.get("status") == "cancelled" and "cancelled_at" not in changes:
            set_parts.append("cancelled_at = now()")
        values = [_jb(value) if key in jsonb_cols else value for key, value in changes.items()]
        values.append(job_id)
        row = conn.execute(
            f"UPDATE scheduled_jobs SET {', '.join(set_parts)} WHERE id = %s RETURNING *",
            values,
        ).fetchone()
        if row is None:
            raise RevisionConflict(f"Scheduled job {job_id!r} not found")
        return ScheduledJob(**row)

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
        conn = self._get_conn()
        values: list[Any] = [worker_id, now, now]
        stale_clause = ""
        if stale_after_seconds is not None:
            stale_clause = """
                OR (
                    status = 'claimed'
                    AND claimed_at IS NOT NULL
                    AND claimed_at < COALESCE(%s::timestamptz, now()) - make_interval(secs => %s)
                )
            """
            values.extend([now, stale_after_seconds])
        type_clause = ""
        if job_type is not None:
            type_clause = "AND job_type = %s"
            values.append(job_type)
        rows = conn.execute(
            f"""
            UPDATE scheduled_jobs
            SET status = 'claimed',
                claimed_by = %s,
                claimed_at = COALESCE(%s::timestamptz, now()),
                attempt_count = attempt_count + 1,
                updated_at = now()
            WHERE id IN (
                SELECT id FROM scheduled_jobs
                WHERE (
                    (status = 'pending' AND scheduled_for <= COALESCE(%s::timestamptz, now()))
                    {stale_clause}
                )
                {type_clause}
                ORDER BY scheduled_for, id
                LIMIT %s
                FOR UPDATE SKIP LOCKED
            )
            RETURNING *
            """,
            [*values, max],
        ).fetchall()
        return [ScheduledJob(**row) for row in rows]

    def list_scheduled_jobs(
        self,
        *,
        conversation_id: str | None = None,
        cloud_run_id: str | None = None,
        status: str | None = None,
        job_type: str | None = None,
        limit: int = 50,
    ) -> list[ScheduledJob]:
        conn = self._get_conn()
        conditions: list[str] = []
        values: list[Any] = []
        for column, value in (
            ("conversation_id", conversation_id),
            ("cloud_run_id", cloud_run_id),
            ("status", status),
            ("job_type", job_type),
        ):
            if value is not None:
                conditions.append(f"{column} = %s")
                values.append(value)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        rows = conn.execute(
            f"SELECT * FROM scheduled_jobs {where} ORDER BY scheduled_for DESC, id DESC LIMIT %s",
            [*values, limit],
        ).fetchall()
        return [ScheduledJob(**row) for row in rows]

    def create_cloud_run(
        self,
        run: CloudRunInput,
        *,
        idempotency_key: str | None = None,
    ) -> CloudRun:
        conn = self._get_conn()
        effective_key = idempotency_key or run.idempotency_key
        row = conn.execute(
            """
            INSERT INTO cloud_runs (
                id, operation, conversation_id, epic_id, sprint_id, plan_id,
                provider, provider_run_id, target_id, command_summary,
                metadata, idempotency_key, started_by_actor_id
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (idempotency_key) WHERE idempotency_key IS NOT NULL DO UPDATE
            SET idempotency_key = EXCLUDED.idempotency_key
            RETURNING *
            """,
            [
                str(uuid.uuid4()), run.operation, run.conversation_id, run.epic_id,
                run.sprint_id, run.plan_id, run.provider, run.provider_run_id,
                run.target_id, run.command_summary, _jb(dict(run.metadata)),
                effective_key, run.started_by_actor_id,
            ],
        ).fetchone()
        return CloudRun(**row)

    def load_cloud_run(self, run_id: str) -> CloudRun | None:
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM cloud_runs WHERE id = %s", [run_id]).fetchone()
        return CloudRun(**row) if row else None

    def update_cloud_run(
        self,
        run_id: str,
        *,
        idempotency_key: str | None = None,
        **changes: Any,
    ) -> CloudRun:
        conn = self._get_conn()
        if not changes:
            row = conn.execute("SELECT * FROM cloud_runs WHERE id = %s", [run_id]).fetchone()
            if row is None:
                raise RevisionConflict(f"Cloud run {run_id!r} not found")
            return CloudRun(**row)
        jsonb_cols = frozenset({"last_status", "metadata"})
        set_parts = [f"{key} = %s" for key in changes]
        set_parts.append("updated_at = now()")
        if changes.get("status") in {"completed", "failed", "blocked", "cancelled"} and "completed_at" not in changes:
            set_parts.append("completed_at = now()")
        values = [_jb(value) if key in jsonb_cols else value for key, value in changes.items()]
        values.append(run_id)
        row = conn.execute(
            f"UPDATE cloud_runs SET {', '.join(set_parts)} WHERE id = %s RETURNING *",
            values,
        ).fetchone()
        if row is None:
            raise RevisionConflict(f"Cloud run {run_id!r} not found")
        return CloudRun(**row)

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
        conn = self._get_conn()
        conditions: list[str] = []
        values: list[Any] = []
        for column, value in (
            ("conversation_id", conversation_id),
            ("epic_id", epic_id),
            ("plan_id", plan_id),
            ("sprint_id", sprint_id),
            ("status", status),
        ):
            if value is not None:
                conditions.append(f"{column} = %s")
                values.append(value)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        rows = conn.execute(
            f"SELECT * FROM cloud_runs {where} ORDER BY created_at DESC, id DESC LIMIT %s",
            [*values, limit],
        ).fetchall()
        return [CloudRun(**row) for row in rows]

    def append_progress_event(self, event: ProgressEventInput,
        *,
        idempotency_key: str | None = None,
    ) -> ProgressEvent:
        self._require_actor()
        effective_idempotency_key = idempotency_key or event.idempotency_key
        conn = self._get_conn()
        row = conn.execute(
            """
            INSERT INTO progress_events (id, epic_id, plan_id, sprint_id, idempotency_key, kind, summary, details)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (idempotency_key) WHERE idempotency_key IS NOT NULL DO UPDATE
            SET idempotency_key = EXCLUDED.idempotency_key
            RETURNING *
            """,
            [
                str(uuid.uuid4()), event.epic_id, event.plan_id, event.sprint_id,
                effective_idempotency_key, event.kind, event.summary, _jb(dict(event.details)),
            ],
        ).fetchone()
        return ProgressEvent(**row)

    def list_progress_events(
        self,
        *,
        plan_id: str | None = None,
        epic_id: str | None = None,
        since: Any = None,
    ) -> list[ProgressEvent]:
        conn = self._get_conn()
        conditions: list[str] = []
        values: list[Any] = []
        if plan_id is not None:
            conditions.append("plan_id = %s")
            values.append(plan_id)
        if epic_id is not None:
            conditions.append("epic_id = %s")
            values.append(epic_id)
        if since is not None:
            conditions.append("occurred_at >= %s")
            values.append(since)
        where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
        rows = conn.execute(
            f"SELECT * FROM progress_events{where} ORDER BY occurred_at DESC",
            values,
        ).fetchall()
        return [ProgressEvent(**row) for row in rows]

    def create_automation_actor(
        self,
        *,
        actor_id: str,
        name: str,
        granted_epic_ids: str | Sequence[str],
        actor_kind: str,
        idempotency_key: str | None = None,
    ) -> AutomationActor:
        conn = self._get_conn()
        gei: Any = list(granted_epic_ids) if not isinstance(granted_epic_ids, str) else granted_epic_ids
        row = conn.execute(
            """
            INSERT INTO automation_actors (id, name, granted_epic_ids, actor_kind)
            VALUES (%s, %s, %s, %s)
            RETURNING *
            """,
            [actor_id, name, _jb(gei), actor_kind],
        ).fetchone()
        return AutomationActor(**row)

    def load_automation_actor(self, actor_id: str) -> AutomationActor | None:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM automation_actors WHERE id = %s", [actor_id]
        ).fetchone()
        return AutomationActor(**row) if row else None

    def update_automation_actor(self, actor_id: str, *, idempotency_key: str | None = None,
        **changes: Any) -> AutomationActor:
        conn = self._get_conn()
        if not changes:
            row = conn.execute(
                "SELECT * FROM automation_actors WHERE id = %s", [actor_id]
            ).fetchone()
            if row is None:
                raise RevisionConflict(f"AutomationActor {actor_id!r} not found")
            return AutomationActor(**row)
        jsonb_actor_cols = frozenset({"granted_epic_ids"})
        set_parts = [f"{k} = %s" for k in changes]
        values = [_jb(v) if k in jsonb_actor_cols else v for k, v in changes.items()]
        values.append(actor_id)
        row = conn.execute(
            f"UPDATE automation_actors SET {', '.join(set_parts)} WHERE id = %s RETURNING *",
            values,
        ).fetchone()
        if row is None:
            raise RevisionConflict(f"AutomationActor {actor_id!r} not found")
        return AutomationActor(**row)

__all__ = ["DBOperationsMixin"]
