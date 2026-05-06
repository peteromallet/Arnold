"""Database-backed store for Sprint 2."""

from __future__ import annotations

import base64
import hashlib
import functools
import json
import os
import uuid
from collections import OrderedDict
from contextlib import contextmanager
from datetime import UTC, datetime
from types import TracebackType
from typing import Any, Generator, Mapping, Sequence

# Lazy import guard: defers ImportError to _get_conn(), not module import,
# so that `from megaplan.store import DBStore` works without psycopg installed.
try:
    import psycopg
    from psycopg.rows import dict_row
    from psycopg.types.json import Jsonb as _Jsonb
    _psycopg_import_error: ImportError | None = None
except ImportError as _e:
    psycopg = None  # type: ignore[assignment]
    dict_row = None  # type: ignore[assignment]
    _Jsonb = None  # type: ignore[assignment]
    _psycopg_import_error = ImportError(
        "psycopg is required for DBStore. "
        "Install with: pip install 'megaplan-harness[db]'"
    )
    _psycopg_import_error.__cause__ = _e

from megaplan.schemas import (
    AutomationActor,
    BotTurn,
    ChecklistItem,
    CodeArtifact,
    Codebase,
    ControlMessage,
    CloudRun,
    Epic,
    EpicEvent,
    EpicLock,
    EpicSnapshot,
    ExecutionLease,
    ExternalRequest,
    Feedback,
    Image,
    Message,
    MigrationRun,
    Plan,
    PlanArtifact,
    ProgressEvent,
    ResidentConversation,
    ScheduledJob,
    SecondOpinion,
    Sprint,
    SprintItem,
    SystemLog,
    ToolCall,
)
from megaplan.store.base import (
    ArtifactRef,
    ArtifactStat,
    ChecklistItemInput,
    ControlMessageInput,
    CloudRunInput,
    EpicSummary,
    HotContext,
    LeaseConflict,
    LockConflict,
    MessageSearchHit,
    ProgressEventInput,
    ResidentConversationInput,
    RevisionConflict,
    ScheduledJobInput,
    SprintItemInput,
    SprintWithItems,
    StoreError,
    validate_plan_artifact_name,
)
from megaplan.store.blob import LocalDirBlobStore, SupabaseStorageBlobStore
from megaplan.store.snapshot import canonical_json_dumps, canonical_sha256, capture_epic_snapshot


_BOOTSTRAP_ACTOR_ID = "__bootstrap__"
_BOOTSTRAP_IDEMPOTENT_MUTATORS = frozenset({"create_automation_actor"})
_IDEMPOTENT_MUTATORS = frozenset({
    "create_epic",
    "update_epic",
    "update_body",
    "seed_checklist",
    "add_checklist_items",
    "update_checklist_item",
    "delete_checklist_items",
    "replace_checklist",
    "create_sprint",
    "update_sprint",
    "delete_sprint",
    "replace_sprint_items",
    "set_sprint_queue",
    "insert_pending",
    "mark_confirmed",
    "mark_failed",
    "mark_orphaned",
    "create_image",
    "update_image",
    "deactivate_active_image_reference",
    "create_second_opinion",
    "set_second_opinion_checklist_items",
    "record_tool_call",
    "log_system_event",
    "create_codebase",
    "upsert_codebase",
    "update_codebase",
    "remove_codebase",
    "touch_codebase_accessed",
    "mark_codebase_verified",
    "create_code_artifact",
    "update_code_artifact",
    "delete_code_artifact",
    "touch_code_artifact_used",
    "upsert_api_cache",
    "cleanup_expired_api_cache",
    "create_feedback",
    "update_feedback",
    "record_epic_event",
    "revert",
    "attach_image",
    "create_message",
    "update_message",
    "upsert_resident_conversation",
    "update_resident_conversation",
    "create_scheduled_job",
    "update_scheduled_job",
    "claim_due_scheduled_jobs",
    "create_cloud_run",
    "update_cloud_run",
    "create_turn",
    "update_turn",
    "create_plan",
    "update_plan",
    "write_plan_artifact",
    "acquire_execution_lease",
    "heartbeat_lease",
    "release_lease",
    "acquire_lock",
    "release_lock",
    "put_control_message",
    "claim_pending_control_messages",
    "mark_control_message_processed",
    "append_progress_event",
    "update_automation_actor",
    "create_migration_run",
    "update_migration_run",
    "heartbeat_migration",
    "claim_expired_migration",
})
_REPLAY_MODEL_TYPES = {
    model.__name__: model
    for model in (
        AutomationActor,
        BotTurn,
        ChecklistItem,
        CodeArtifact,
        Codebase,
        ControlMessage,
        CloudRun,
        Epic,
        EpicEvent,
        EpicLock,
        ExecutionLease,
        ExternalRequest,
        Feedback,
        Image,
        Message,
        Plan,
        PlanArtifact,
        ProgressEvent,
        ResidentConversation,
        ScheduledJob,
        SecondOpinion,
        Sprint,
        SprintItem,
        SystemLog,
        ToolCall,
        MigrationRun,
    )
}


def _jb(value: Any) -> Any:
    """Wrap a Python dict/list for JSONB column insertion."""
    if value is None:
        return None
    if _Jsonb is not None:
        return _Jsonb(value)
    return value


def _parse_datetime(value: datetime | str) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


_PLAN_COLUMNS = (
    "id", "name", "epic_id", "sprint_id", "revision", "idea", "current_state",
    "iteration", "config", "sessions", "plan_versions", "history", "meta",
    "last_gate", "active_step", "clarification", "latest_finalize",
    "latest_review", "latest_execution", "latest_failure", "resume_cursor", "created_at", "updated_at",
)
_PLAN_JSONB = frozenset({
    "config", "sessions", "plan_versions", "history", "meta", "last_gate",
    "active_step", "clarification", "latest_finalize", "latest_review",
    "latest_execution", "latest_failure", "resume_cursor",
})
_ARTIFACT_VALID_FIELDS = frozenset({
    "name", "kind", "role", "version", "batch", "phase",
    "content_text", "content_base64", "sha256", "created_at", "updated_at",
})

_MIGRATION_RUN_COLUMNS = (
    "id", "epic_id", "source_backend", "target_backend", "phase", "manifest",
    "copied_ids", "blob_copy_progress", "started_at", "updated_at",
    "completed_at", "holder_id", "expires_at",
)
_MIGRATION_RUN_JSONB = frozenset({"manifest", "copied_ids", "blob_copy_progress"})

_COPY_TABLE_COLUMNS: dict[str, frozenset[str]] = {
    "automation_actors": frozenset({"id", "name", "granted_epic_ids", "actor_kind", "created_at", "last_active_at"}),
    "bot_turns": frozenset({"id", "epic_id", "triggered_by_message_ids", "prompt_snapshot", "prompt_version", "state_at_turn", "status", "started_at", "completed_at", "model_version", "warnings_issued"}),
    "checklist_items": frozenset({"id", "epic_id", "content", "status", "position", "source", "skip_reason", "superseded_by_item_id", "created_at", "completed_at"}),
    "code_artifacts": frozenset({"id", "codebase_id", "epic_id", "kind", "source", "file_path", "line_range", "scope", "content", "content_summary", "metadata", "created_at", "last_used_at", "expires_at"}),
    "codebases": frozenset({"id", "owner", "name", "repo_url", "repo_workspace", "default_branch", "scope", "group_name", "associated_epic_id", "added_at", "added_via", "last_accessed_at", "verified_accessible_at", "notes"}),
    "control_messages": frozenset({"id", "epic_id", "actor_id", "intent", "target_id", "payload", "idempotency_key", "created_at", "processor_id", "claimed_at", "processed_at", "result"}),
    "cloud_runs": frozenset({"id", "operation", "status", "conversation_id", "epic_id", "sprint_id", "plan_id", "provider", "provider_run_id", "target_id", "command_summary", "progress_summary", "last_status", "metadata", "idempotency_key", "started_by_actor_id", "started_at", "last_checked_at", "completed_at", "created_at", "updated_at"}),
    "epic_events": frozenset({
        "id", "epic_id", "transaction_id", "event_type", "summary",
        "prior_state", "pre_state", "post_state",
        "pre_state_canonical_json", "post_state_canonical_json",
        "pre_state_sha256", "post_state_sha256", "turn_id", "occurred_at",
    }),
    "epics": frozenset({"id", "title", "goal", "body", "state", "home_backend", "migrated_to", "revision", "created_at", "last_edited_at"}),
    "external_requests": frozenset({"id", "idempotency_key", "provider", "endpoint", "tool_call_id", "turn_id", "request_summary", "request_body", "status", "provider_request_id", "provider_response_summary", "attempt_count", "first_attempted_at", "last_attempted_at", "completed_at", "error_details"}),
    "feedback": frozenset({"id", "kind", "content", "source", "source_message_id", "epic_id", "turn_id", "context_snapshot", "active", "deactivation_reason", "resolved", "resolution_note", "resolved_at", "created_at", "last_referenced_at", "last_applied_at"}),
    "images": frozenset({
        "id", "epic_id", "source", "prompt", "storage_url", "quality", "size",
        "created_at", "reference_key", "description", "caption", "in_body",
        "active", "discord_attachment_id", "blob_backend", "blob_id",
        "blob_sha256", "blob_size_bytes", "content_type",
    }),
    "messages": frozenset({"id", "epic_id", "conversation_id", "idempotency_key", "direction", "content", "discord_message_id", "bot_turn_id", "has_code_attachment", "has_image_attachment", "in_burst_with", "was_voice_message", "audio_storage_url", "transcription_metadata", "sent_at"}),
    "plan_artifacts": frozenset({
        "plan_id", "name", "kind", "role", "version", "batch", "phase",
        "content_text", "content_bytes", "sha256", "created_at", "updated_at",
    }),
    "plans": frozenset(_PLAN_COLUMNS),
    "progress_events": frozenset({"id", "epic_id", "plan_id", "sprint_id", "idempotency_key", "kind", "summary", "details", "occurred_at"}),
    "resident_conversations": frozenset({"id", "transport", "conversation_key", "active_epic_id", "guild_id", "channel_id", "thread_id", "dm_user_id", "last_inbound_message_id", "last_outbound_message_id", "delivery_cursor", "metadata", "created_at", "updated_at", "last_active_at"}),
    "scheduled_jobs": frozenset({"id", "job_type", "status", "conversation_id", "cloud_run_id", "epic_id", "payload", "scheduled_for", "attempt_count", "max_attempts", "claimed_by", "claimed_at", "fired_at", "cancelled_at", "last_error", "created_at", "updated_at"}),
    "second_opinions": frozenset({"id", "epic_id", "requested_at", "requested_by", "focus_areas", "raw_response", "score", "summary", "verdict", "resulting_checklist_item_ids", "model_used"}),
    "sprint_items": frozenset({"id", "sprint_id", "content", "estimated_complexity", "status", "source_section", "position", "created_at"}),
    "sprints": frozenset({"id", "epic_id", "sprint_number", "name", "goal", "status", "queue_position", "pending_reason", "target_weeks", "revision", "created_at", "updated_at", "queued_at"}),
    "system_logs": frozenset({"id", "level", "category", "event_type", "message", "details", "turn_id", "epic_id", "occurred_at"}),
    "tool_calls": frozenset({"id", "turn_id", "tool_name", "operation_kind", "arguments", "result", "duration_ms", "called_at"}),
}
_COPY_JSONB_COLUMNS = frozenset({
    "active_step", "arguments", "blob_copy_progress", "clarification", "config",
    "context_snapshot", "copied_ids", "details", "error_details", "focus_areas",
    "granted_epic_ids", "history", "in_burst_with", "last_gate", "last_status",
    "latest_execution", "latest_failure", "latest_finalize", "latest_review",
    "line_range", "manifest", "meta", "metadata", "payload",
    "plan_versions", "post_state", "pre_state", "prior_state", "prompt_snapshot",
    "provider_response_summary", "request_body", "request_summary", "result",
    "resulting_checklist_item_ids", "sessions", "state_at_turn",
    "transcription_metadata", "triggered_by_message_ids", "warnings_issued",
})
_SOURCE_REFERENCE_PREFIX = {
    "user_uploaded": "img_user_upload",
    "caller_uploaded": "img_caller_upload",
    "agent_generated": "img_agent_generated",
}


class _DBTransaction:
    """Thin wrapper yielded by DBStore.transaction().

    The actual psycopg transaction is managed by the surrounding
    conn.transaction() context manager; this object just satisfies
    the Transaction protocol so callers can type-annotate correctly.
    """

    def __enter__(self) -> _DBTransaction:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        pass


class DBStore:
    """Full psycopg3-backed implementation of the Store protocol (Sprint 2).

    Connection is opened lazily on first use and cached for the lifetime of
    the store instance. Use as a context manager to ensure clean close():

        with DBStore(actor_id="...") as store:
            epic = store.load_epic(epic_id)

    autocommit=True is mandatory: each statement commits immediately.
    Multi-statement atomicity uses conn.transaction() (explicit BEGIN/COMMIT).
    Never call conn.commit() directly.
    """

    def __init__(
        self,
        *,
        actor_id: str | None = None,
        dsn: str | None = None,
    ) -> None:
        if actor_id == _BOOTSTRAP_ACTOR_ID:
            raise ValueError(f"actor_id {_BOOTSTRAP_ACTOR_ID!r} is reserved for bootstrap idempotency")
        # Use .get() (not []) so DBStore() without SUPABASE_DB_URL doesn't raise
        # at instantiation time; the error is deferred to _get_conn().
        self._actor_id = actor_id
        self._dsn = dsn or os.environ.get("SUPABASE_DB_URL")
        self._conn: psycopg.Connection | None = None  # type: ignore[type-arg]
        storage_bucket = os.environ.get("SUPABASE_STORAGE_BUCKET") or os.environ.get("SUPABASE_BUCKET")
        storage_secret_key = "SUPABASE_" + "SERVICE_" + "ROLE_KEY"
        if os.environ.get("SUPABASE_URL") and os.environ.get(storage_secret_key) and storage_bucket:
            self.blobs = SupabaseStorageBlobStore(
                supabase_url=os.environ["SUPABASE_URL"],
                service_role_key=os.environ[storage_secret_key],
                bucket=storage_bucket,
            )
        else:
            self.blobs = LocalDirBlobStore(os.environ.get("MEGAPLAN_DB_BLOB_ROOT", ".megaplan/db-blobs"))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_conn(self) -> psycopg.Connection:  # type: ignore[type-arg]
        """Return cached connection, creating it on first call."""
        if self._conn is not None:
            return self._conn
        if _psycopg_import_error is not None:
            raise _psycopg_import_error
        if self._dsn is None:
            raise RuntimeError(
                "SUPABASE_DB_URL is not set. "
                "Set it before using DBStore: "
                "export SUPABASE_DB_URL=postgresql://postgres:[pw]@[host]:5432/postgres"
            )
        conn = psycopg.connect(self._dsn, autocommit=True, row_factory=dict_row)
        if self._actor_id is not None:
            conn.execute("SELECT set_actor(%s)", [self._actor_id])
        self._conn = conn
        return conn

    def _require_actor(self) -> str:
        """Return actor_id or raise RuntimeError if not set."""
        if self._actor_id is None:
            raise RuntimeError(
                "This operation requires an actor ID. "
                "Pass actor_id= to DBStore() or set MEGAPLAN_ACTOR_ID."
            )
        return self._actor_id

    def __getattribute__(self, name: str) -> Any:
        attr = object.__getattribute__(self, name)
        if name in _IDEMPOTENT_MUTATORS or name in _BOOTSTRAP_IDEMPOTENT_MUTATORS:
            if not callable(attr):
                return attr

            @functools.wraps(attr)
            def _wrapped(*args: Any, **kwargs: Any) -> Any:
                return self._run_idempotent_mutation(name, attr, args, kwargs)

            return _wrapped
        return attr

    def _request_hash(self, operation: str, args: tuple[Any, ...], kwargs: Mapping[str, Any]) -> str:
        payload = {
            "operation": operation,
            "args": args,
            "kwargs": kwargs,
        }
        encoded = json.dumps(payload, default=self._json_default, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    def _json_default(self, value: Any) -> Any:
        if hasattr(value, "model_dump"):
            return value.model_dump(mode="json")
        if isinstance(value, (set, tuple)):
            return list(value)
        return str(value)

    def _encode_idempotent_response(self, value: Any) -> Any:
        if hasattr(value, "model_dump"):
            return {
                "kind": "model",
                "model": value.__class__.__name__,
                "data": value.model_dump(mode="json"),
            }
        if isinstance(value, list):
            return {
                "kind": "list",
                "items": [self._encode_idempotent_response(item) for item in value],
            }
        if isinstance(value, tuple):
            return {
                "kind": "tuple",
                "items": [self._encode_idempotent_response(item) for item in value],
            }
        return {"kind": "plain", "data": value}

    def _decode_idempotent_response(self, payload: Any) -> Any:
        if payload is None:
            return None
        kind = payload.get("kind") if isinstance(payload, Mapping) else None
        if kind == "model":
            model_cls = _REPLAY_MODEL_TYPES.get(str(payload.get("model")))
            data = payload.get("data")
            return model_cls.model_validate(data) if model_cls is not None else data
        if kind in {"list", "tuple"}:
            items = [self._decode_idempotent_response(item) for item in payload.get("items", [])]
            return tuple(items) if kind == "tuple" else items
        if kind == "plain":
            return payload.get("data")
        return payload

    def _run_idempotent_mutation(
        self,
        operation: str,
        func: Any,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> Any:
        ledger_actor_id = _BOOTSTRAP_ACTOR_ID if operation in _BOOTSTRAP_IDEMPOTENT_MUTATORS else self._require_actor()
        idempotency_key = kwargs.get("idempotency_key")
        if not idempotency_key and operation == "append_progress_event" and args:
            idempotency_key = getattr(args[0], "idempotency_key", None)
        if not idempotency_key:
            raise ValueError(f"idempotency_key is required for DBStore.{operation}")
        target_actor_id = kwargs.get("actor_id") if "actor_id" in kwargs else (args[0] if args else None)
        if operation in {"create_automation_actor", "update_automation_actor"} and target_actor_id == _BOOTSTRAP_ACTOR_ID:
            raise ValueError(f"automation actor ID {_BOOTSTRAP_ACTOR_ID!r} is reserved")

        request_kwargs = dict(kwargs)
        request_kwargs.pop("idempotency_key", None)
        request_hash = self._request_hash(operation, args, request_kwargs)
        conn = self._get_conn()

        with conn.transaction():
            row = conn.execute(
                """
                SELECT actor_id, operation, request_hash, response_json, status
                FROM db_idempotency_keys
                WHERE idempotency_key = %s
                FOR UPDATE
                """,
                [idempotency_key],
            ).fetchone()
            if row is not None:
                if (
                    row["actor_id"] != ledger_actor_id
                    or row["operation"] != operation
                    or row["request_hash"] != request_hash
                ):
                    raise ValueError(f"idempotency_key {idempotency_key!r} was reused with a different request")
                if row["status"] == "complete":
                    return self._decode_idempotent_response(row["response_json"])
                raise RuntimeError(f"idempotency_key {idempotency_key!r} has incomplete status {row['status']!r}")

            conn.execute(
                """
                INSERT INTO db_idempotency_keys
                    (idempotency_key, actor_id, operation, request_hash, status)
                VALUES (%s, %s, %s, %s, 'in_progress')
                """,
                [idempotency_key, ledger_actor_id, operation, request_hash],
            )
            try:
                result = func(*args, **kwargs)
            except Exception:
                conn.execute(
                    """
                    UPDATE db_idempotency_keys
                    SET status = 'failed', updated_at = now()
                    WHERE idempotency_key = %s
                    """,
                    [idempotency_key],
                )
                raise
            conn.execute(
                """
                UPDATE db_idempotency_keys
                SET status = 'complete', response_json = %s, updated_at = now()
                WHERE idempotency_key = %s
                """,
                [_jb(self._encode_idempotent_response(result)), idempotency_key],
            )
            return result

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> DBStore:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Transaction
    # ------------------------------------------------------------------

    @contextmanager
    def transaction(
        self, epic_id: str | None = None
    ) -> Generator[_DBTransaction, None, None]:
        """Execute a block atomically using psycopg's explicit transaction.

        autocommit=True means normal statements auto-commit; conn.transaction()
        issues real BEGIN/COMMIT so multi-statement blocks are atomic.
        """
        conn = self._get_conn()
        with conn.transaction():
            yield _DBTransaction()

    # ------------------------------------------------------------------
    # T4: Epic + Body + Search
    # ------------------------------------------------------------------

    def create_epic(
        self,
        *,
        title: str,
        goal: str,
        body: str,
        state: str = "shaping",
        home_backend: str = "file",
        idempotency_key: str | None = None,
    ) -> Epic:
        self._require_actor()
        conn = self._get_conn()
        row = conn.execute(
            """
            INSERT INTO epics (id, title, goal, body, state, home_backend, revision)
            VALUES (%s, %s, %s, %s, %s, %s, 1)
            RETURNING *
            """,
            [str(uuid.uuid4()), title, goal, body, state, home_backend],
        ).fetchone()
        return Epic(**row)

    def load_epic(self, epic_id: str) -> Epic | None:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM epics WHERE id = %s", [epic_id]
        ).fetchone()
        return Epic(**row) if row else None

    def update_epic(
        self,
        epic_id: str,
        *,
        expected_revision: int,
        idempotency_key: str | None = None,
        **changes: Any,
    ) -> Epic:
        conn = self._get_conn()
        if not changes:
            row = conn.execute(
                "SELECT * FROM epics WHERE id = %s", [epic_id]
            ).fetchone()
            if row is None:
                raise RevisionConflict(f"Epic {epic_id!r} not found")
            return Epic(**row)
        set_parts = [f"{k} = %s" for k in changes]
        set_parts.append("revision = revision + 1")
        values = list(changes.values()) + [epic_id, expected_revision, expected_revision]
        row = conn.execute(
            f"""
            UPDATE epics
            SET {', '.join(set_parts)}
            WHERE id = %s AND (%s IS NULL OR revision = %s)
            RETURNING *
            """,
            values,
        ).fetchone()
        if row is None:
            raise RevisionConflict(f"Revision conflict on epic {epic_id!r}")
        return Epic(**row)

    def list_epics(
        self,
        *,
        active_only: bool = True,
        limit: int = 50,
        home_backend: str | None = None,
    ) -> list[EpicSummary]:
        conn = self._get_conn()
        conditions: list[str] = []
        values: list[Any] = []
        if active_only:
            conditions.append("state != 'archived'")
        conditions.append("migrated_to IS NULL")
        if home_backend is not None:
            conditions.append("home_backend = %s")
            values.append(home_backend)
        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        values.append(limit)
        rows = conn.execute(
            f"SELECT * FROM epics{where} ORDER BY last_edited_at DESC LIMIT %s",
            values,
        ).fetchall()
        return [EpicSummary(**row) for row in rows]

    def search_epics(
        self,
        *,
        query: str,
        active_only: bool = True,
        limit: int = 20,
    ) -> list[EpicSummary]:
        conn = self._get_conn()
        state_filter = "AND state != 'archived'" if active_only else ""
        rows = conn.execute(
            f"""
            SELECT *,
                   ts_rank(
                       to_tsvector('english', coalesce(title, '') || ' ' || coalesce(goal, '') || ' ' || coalesce(body, '')),
                       plainto_tsquery('english', %s)
                   ) AS rank,
                   CASE
                       WHEN lower(title) LIKE lower(%s) THEN 3
                       WHEN lower(goal) LIKE lower(%s) THEN 2
                       ELSE 1
                   END AS match_tier,
                   'db' AS backend
            FROM epics
            WHERE to_tsvector('english', coalesce(title, '') || ' ' || coalesce(goal, '') || ' ' || coalesce(body, ''))
                  @@ plainto_tsquery('english', %s)
              AND migrated_to IS NULL
              {state_filter}
            ORDER BY match_tier DESC, rank DESC, last_edited_at DESC, id DESC
            LIMIT %s
            """,
            [query, f"%{query}%", f"%{query}%", query, limit],
        ).fetchall()
        return [EpicSummary(**row) for row in rows]

    def load_body(self, epic_id: str) -> str:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT body FROM epics WHERE id = %s", [epic_id]
        ).fetchone()
        if row is None:
            raise KeyError(f"Epic {epic_id!r} not found")
        return row["body"]

    def capture_epic_snapshot(self, epic_id: str) -> EpicSnapshot:
        return capture_epic_snapshot(self, epic_id)

    def _event_snapshot(self, event: EpicEvent, *, field: str) -> EpicSnapshot:
        payload = event.pre_state if field == "pre" else event.post_state
        if payload is None:
            raise StoreError(
                f"Event {event.id!r} from transaction {event.transaction_id!r} lacks {field}_state snapshot"
            )
        return EpicSnapshot.model_validate(payload)

    def _insert_snapshot_rows(self, table: str, rows: Sequence[dict[str, Any]]) -> None:
        allowed_columns = _COPY_TABLE_COLUMNS[table]
        jsonb_columns = _COPY_JSONB_COLUMNS
        conn = self._get_conn()
        for raw in rows:
            row = {key: value for key, value in raw.items() if key in allowed_columns}
            columns = list(row)
            if not columns:
                continue
            values = [_jb(row[column]) if column in jsonb_columns else row[column] for column in columns]
            placeholders = ", ".join(["%s"] * len(columns))
            conn.execute(
                f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})",
                values,
            )

    def _restore_epic_snapshot(self, snapshot: EpicSnapshot, *, new_revision: int) -> Epic:
        conn = self._get_conn()
        now = "now()"
        epic_data = {
            key: value
            for key, value in dict(snapshot.epic).items()
            if key in _COPY_TABLE_COLUMNS["epics"]
        }
        epic_data.update({"id": snapshot.epic_id, "body": snapshot.body, "revision": new_revision})
        set_columns = [column for column in epic_data if column != "id"]
        values = [epic_data[column] for column in set_columns]
        values.append(snapshot.epic_id)
        row = conn.execute(
            f"""
            UPDATE epics
            SET {', '.join(f'{column} = %s' for column in set_columns)},
                last_edited_at = {now}
            WHERE id = %s
            RETURNING *
            """,
            values,
        ).fetchone()
        if row is None:
            raise FileNotFoundError(snapshot.epic_id)

        sprint_ids = [str(raw["id"]) for raw in snapshot.sprints if "id" in raw]
        conn.execute(
            "DELETE FROM sprint_items WHERE sprint_id IN (SELECT id FROM sprints WHERE epic_id = %s)",
            [snapshot.epic_id],
        )
        conn.execute("DELETE FROM sprints WHERE epic_id = %s", [snapshot.epic_id])
        conn.execute("DELETE FROM checklist_items WHERE epic_id = %s", [snapshot.epic_id])
        conn.execute("DELETE FROM images WHERE epic_id = %s", [snapshot.epic_id])
        conn.execute("DELETE FROM second_opinions WHERE epic_id = %s", [snapshot.epic_id])

        self._insert_snapshot_rows("checklist_items", [dict(raw) for raw in snapshot.checklist_items])
        self._insert_snapshot_rows("sprints", [dict(raw) for raw in snapshot.sprints])
        sprint_id_set = set(sprint_ids)
        invalid_items = [
            raw
            for raw in snapshot.sprint_items
            if str(raw.get("sprint_id")) not in sprint_id_set
        ]
        if invalid_items:
            raise StoreError("Snapshot contains sprint items without restored sprint rows")
        self._insert_snapshot_rows("sprint_items", [dict(raw) for raw in snapshot.sprint_items])
        self._insert_snapshot_rows("images", [dict(raw) for raw in snapshot.images])
        self._insert_snapshot_rows("second_opinions", [dict(raw) for raw in snapshot.second_opinions])
        return Epic(**row)

    def revert(
        self,
        epic_id: str,
        to_transaction_id: str,
        *,
        expected_revision: int,
        idempotency_key: str | None = None,
    ) -> Epic:
        conn = self._get_conn()
        current_row = conn.execute(
            "SELECT * FROM epics WHERE id = %s",
            [epic_id],
        ).fetchone()
        if current_row is None:
            raise FileNotFoundError(epic_id)
        current = Epic(**current_row)
        if current.revision != expected_revision:
            raise RevisionConflict(f"Revision conflict on epic {epic_id!r}")
        target_rows = conn.execute(
            """
            SELECT * FROM epic_events
            WHERE epic_id = %s AND transaction_id = %s
            ORDER BY occurred_at ASC, id ASC
            """,
            [epic_id, to_transaction_id],
        ).fetchall()
        if not target_rows:
            raise FileNotFoundError(to_transaction_id)
        target = EpicEvent(**target_rows[0])
        restore_snapshot = self._event_snapshot(target, field="pre")
        if restore_snapshot.epic_id != epic_id:
            raise StoreError(f"Snapshot epic_id {restore_snapshot.epic_id!r} does not match {epic_id!r}")

        with conn.transaction():
            locked_row = conn.execute(
                "SELECT * FROM epics WHERE id = %s FOR UPDATE",
                [epic_id],
            ).fetchone()
            locked = Epic(**locked_row)
            if locked.revision != expected_revision:
                raise RevisionConflict(f"Revision conflict on epic {epic_id!r}")
            pre_snapshot = self.capture_epic_snapshot(epic_id)
            restored = self._restore_epic_snapshot(restore_snapshot, new_revision=locked.revision + 1)
            post_snapshot = self.capture_epic_snapshot(epic_id)
            self.record_epic_event(
                epic_id=epic_id,
                transaction_id=str(uuid.uuid4()),
                event_type="reverted_to",
                summary=f"Reverted to transaction {to_transaction_id}",
                prior_state={
                    "reverted_to_transaction_id": to_transaction_id,
                    "target_event_id": target.id,
                    "from_revision": locked.revision,
                    "to_revision": restored.revision,
                },
                pre_state=pre_snapshot.model_dump(mode="json"),
                post_state=post_snapshot.model_dump(mode="json"),
                pre_state_canonical_json=canonical_json_dumps(pre_snapshot),
                post_state_canonical_json=canonical_json_dumps(post_snapshot),
                pre_state_sha256=canonical_sha256(pre_snapshot),
                post_state_sha256=canonical_sha256(post_snapshot),
                idempotency_key=idempotency_key,
            )
        return restored

    def get_epic_at_time(self, epic_id: str, when: datetime | str) -> EpicSnapshot | None:
        cutoff = _parse_datetime(when)
        conn = self._get_conn()
        rows = conn.execute(
            """
            SELECT * FROM epic_events
            WHERE epic_id = %s AND occurred_at <= %s
            ORDER BY occurred_at ASC, id ASC
            """,
            [epic_id, cutoff],
        ).fetchall()
        if not rows:
            current = self.load_epic(epic_id)
            if current is not None and current.created_at <= cutoff:
                return self.capture_epic_snapshot(epic_id)
            return None
        return self._event_snapshot(EpicEvent(**rows[-1]), field="post")

    def update_body(self, epic_id: str, body: str, *, expected_revision: int, idempotency_key: str | None = None) -> Epic:
        self._require_actor()
        conn = self._get_conn()
        row = conn.execute(
            """
            UPDATE epics
            SET body = %s, revision = revision + 1, last_edited_at = now()
            WHERE id = %s AND (%s IS NULL OR revision = %s)
            RETURNING *
            """,
            [body, epic_id, expected_revision, expected_revision],
        ).fetchone()
        if row is None:
            raise RevisionConflict(f"Revision conflict on epic {epic_id!r}")
        return Epic(**row)

    # ------------------------------------------------------------------
    # T5: Checklist
    # ------------------------------------------------------------------

    def seed_checklist(self, epic_id: str, items: Sequence[str],
        *,
        idempotency_key: str | None = None,
    ) -> list[ChecklistItem]:
        self._require_actor()
        conn = self._get_conn()
        result = []
        for i, content in enumerate(items, 1):
            row = conn.execute(
                """
                INSERT INTO checklist_items
                    (id, epic_id, content, status, position, source)
                VALUES (%s, %s, %s, 'open', %s, 'default_seed')
                RETURNING *
                """,
                [str(uuid.uuid4()), epic_id, content, i],
            ).fetchone()
            result.append(ChecklistItem(**row))
        return result

    def list_checklist_items(
        self,
        epic_id: str,
        *,
        status: str | None = None,
    ) -> list[ChecklistItem]:
        conn = self._get_conn()
        if status is not None:
            rows = conn.execute(
                "SELECT * FROM checklist_items WHERE epic_id = %s AND status = %s ORDER BY position",
                [epic_id, status],
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM checklist_items WHERE epic_id = %s ORDER BY position",
                [epic_id],
            ).fetchall()
        return [ChecklistItem(**row) for row in rows]

    def add_checklist_items(
        self,
        epic_id: str,
        items: Sequence[ChecklistItemInput],
        *,
        idempotency_key: str | None = None,
    ) -> list[ChecklistItem]:
        self._require_actor()
        conn = self._get_conn()
        max_row = conn.execute(
            "SELECT COALESCE(MAX(position), 0) AS max_pos FROM checklist_items WHERE epic_id = %s",
            [epic_id],
        ).fetchone()
        base_pos = max_row["max_pos"]
        result = []
        moved: list[tuple[str, int]] = []
        auto_idx = 0
        for item in items:
            item_id = item.id or str(uuid.uuid4())
            if item.position is not None:
                position = item.position
            else:
                auto_idx += 1
                position = base_pos + auto_idx
            row = conn.execute(
                """
                INSERT INTO checklist_items
                    (id, epic_id, content, status, position, source,
                     skip_reason, superseded_by_item_id, completed_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING *
                """,
                [
                    item_id, epic_id, item.content, item.status, position,
                    item.source, item.skip_reason, item.superseded_by_item_id,
                    item.completed_at,
                ],
            ).fetchone()
            result.append(ChecklistItem(**row))
            moved.append((item_id, position))
        self._normalize_checklist_positions_db(epic_id, moved=moved)
        by_id = {item.id: item for item in self.list_checklist_items(epic_id)}
        return [by_id[item.id] for item in result if item.id in by_id]

    def update_checklist_item(self, item_id: str, *, idempotency_key: str | None = None,
        **changes: Any) -> ChecklistItem:
        conn = self._get_conn()
        current = conn.execute(
            "SELECT * FROM checklist_items WHERE id = %s",
            [item_id],
        ).fetchone()
        if current is None:
            raise FileNotFoundError(item_id)
        if not changes:
            return ChecklistItem(**current)
        moved_position = changes.get("position")
        set_parts = [f"{k} = %s" for k in changes]
        values = list(changes.values())
        if changes.get("status") == "done" and "completed_at" not in changes:
            set_parts.append("completed_at = now()")
        values.append(item_id)
        row = conn.execute(
            f"UPDATE checklist_items SET {', '.join(set_parts)} WHERE id = %s RETURNING *",
            values,
        ).fetchone()
        updated = ChecklistItem(**row)
        self._normalize_checklist_positions_db(
            updated.epic_id,
            moved=[(updated.id, int(moved_position))] if moved_position is not None else None,
        )
        row = conn.execute(
            "SELECT * FROM checklist_items WHERE id = %s",
            [item_id],
        ).fetchone()
        return ChecklistItem(**row)

    def delete_checklist_items(self, item_ids: Sequence[str],
        *,
        idempotency_key: str | None = None,
    ) -> None:
        if not item_ids:
            return
        conn = self._get_conn()
        epic_rows = conn.execute(
            "SELECT DISTINCT epic_id FROM checklist_items WHERE id = ANY(%s)",
            [list(item_ids)],
        ).fetchall()
        conn.execute(
            "DELETE FROM checklist_items WHERE id = ANY(%s)",
            [list(item_ids)],
        )
        for row in epic_rows:
            self._normalize_checklist_positions_db(str(row["epic_id"]))

    def replace_checklist(
        self,
        epic_id: str,
        items: Sequence[ChecklistItemInput],
        *,
        idempotency_key: str | None = None,
    ) -> list[ChecklistItem]:
        self._require_actor()
        conn = self._get_conn()
        result = []
        with conn.transaction():
            conn.execute(
                "DELETE FROM checklist_items WHERE epic_id = %s", [epic_id]
            )
            for i, item in enumerate(items, 1):
                item_id = item.id or str(uuid.uuid4())
                position = item.position if item.position is not None else i
                row = conn.execute(
                    """
                    INSERT INTO checklist_items
                        (id, epic_id, content, status, position, source,
                         skip_reason, superseded_by_item_id, completed_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING *
                    """,
                    [
                        item_id, epic_id, item.content, item.status, position,
                        item.source, item.skip_reason, item.superseded_by_item_id,
                        item.completed_at,
                    ],
                ).fetchone()
                result.append(ChecklistItem(**row))
            self._normalize_checklist_positions_db(epic_id, moved=[(item.id, item.position) for item in result])
        by_id = {item.id: item for item in self.list_checklist_items(epic_id)}
        return [by_id[item.id] for item in result if item.id in by_id]

    def _normalize_checklist_positions_db(
        self,
        epic_id: str,
        *,
        moved: Sequence[tuple[str, int]] | None = None,
    ) -> list[ChecklistItem]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM checklist_items WHERE epic_id = %s ORDER BY position, created_at, id",
            [epic_id],
        ).fetchall()
        ordered = [ChecklistItem(**row) for row in rows]
        by_id = {item.id: item for item in ordered}
        if moved:
            for item_id, requested_position in moved:
                item = by_id.get(item_id)
                if item is None:
                    continue
                ordered = [row for row in ordered if row.id != item_id]
                index = max(0, min(int(requested_position) - 1, len(ordered)))
                ordered.insert(index, item)
        result: list[ChecklistItem] = []
        for position, item in enumerate(ordered, start=1):
            if item.position != position:
                row = conn.execute(
                    "UPDATE checklist_items SET position = %s WHERE id = %s RETURNING *",
                    [position, item.id],
                ).fetchone()
                result.append(ChecklistItem(**row))
            else:
                result.append(item)
        return result

    # ------------------------------------------------------------------
    # T6: Sprints
    # ------------------------------------------------------------------

    def _group_sprint_rows(self, rows: list[dict]) -> list[SprintWithItems]:
        """Collapse LEFT JOIN rows (one per sprint_item) into SprintWithItems."""
        sprints: OrderedDict[str, dict] = OrderedDict()
        items_by_sprint: dict[str, list[SprintItem]] = {}
        for row in rows:
            sid = row["id"]
            if sid not in sprints:
                sprint_fields = {k: v for k, v in row.items() if not k.startswith("si_")}
                sprints[sid] = sprint_fields
                items_by_sprint[sid] = []
            if row.get("si_id") is not None:
                items_by_sprint[sid].append(
                    SprintItem(
                        id=row["si_id"],
                        sprint_id=row["si_sprint_id"],
                        content=row["si_content"],
                        estimated_complexity=row["si_estimated_complexity"],
                        status=row["si_status"],
                        source_section=row["si_source_section"],
                        position=row["si_position"],
                        created_at=row["si_created_at"],
                    )
                )
        return [
            SprintWithItems(**sprints[sid], items=items_by_sprint[sid])
            for sid in sprints
        ]

    def create_sprint(
        self,
        *,
        epic_id: str,
        sprint_number: int,
        name: str,
        goal: str,
        status: str = "proposed",
        queue_position: int | None = None,
        pending_reason: str | None = None,
        target_weeks: int = 2,
        idempotency_key: str | None = None,
    ) -> Sprint:
        self._require_actor()
        conn = self._get_conn()
        row = conn.execute(
            """
            INSERT INTO sprints
                (id, epic_id, sprint_number, name, goal, status,
                 queue_position, pending_reason, target_weeks, revision)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 1)
            RETURNING *
            """,
            [
                str(uuid.uuid4()), epic_id, sprint_number, name, goal, status,
                queue_position, pending_reason, target_weeks,
            ],
        ).fetchone()
        return Sprint(**row)

    def load_sprint(self, sprint_id: str) -> Sprint | None:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM sprints WHERE id = %s", [sprint_id]
        ).fetchone()
        return Sprint(**row) if row else None

    def list_sprints(self, epic_id: str, *, status: str | None = None) -> list[Sprint]:
        conn = self._get_conn()
        if status is not None:
            rows = conn.execute(
                "SELECT * FROM sprints WHERE epic_id = %s AND status = %s ORDER BY sprint_number",
                [epic_id, status],
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM sprints WHERE epic_id = %s ORDER BY sprint_number",
                [epic_id],
            ).fetchall()
        return [Sprint(**row) for row in rows]

    def list_sprints_with_items(self, epic_id: str) -> list[SprintWithItems]:
        conn = self._get_conn()
        rows = conn.execute(
            """
            SELECT s.*,
                   si.id               AS si_id,
                   si.sprint_id        AS si_sprint_id,
                   si.content          AS si_content,
                   si.estimated_complexity AS si_estimated_complexity,
                   si.status           AS si_status,
                   si.source_section   AS si_source_section,
                   si.position         AS si_position,
                   si.created_at       AS si_created_at
            FROM sprints s
            LEFT JOIN sprint_items si ON si.sprint_id = s.id
            WHERE s.epic_id = %s
            ORDER BY s.sprint_number, si.position
            """,
            [epic_id],
        ).fetchall()
        return self._group_sprint_rows(rows)

    def update_sprint(
        self,
        sprint_id: str,
        *,
        expected_revision: int,
        idempotency_key: str | None = None,
        **changes: Any,
    ) -> Sprint:
        conn = self._get_conn()
        if not changes:
            row = conn.execute(
                "SELECT * FROM sprints WHERE id = %s", [sprint_id]
            ).fetchone()
            if row is None:
                raise RevisionConflict(f"Sprint {sprint_id!r} not found")
            return Sprint(**row)
        set_parts = [f"{k} = %s" for k in changes]
        set_parts.extend(["revision = revision + 1", "updated_at = now()"])
        values = list(changes.values()) + [sprint_id, expected_revision, expected_revision]
        row = conn.execute(
            f"""
            UPDATE sprints
            SET {', '.join(set_parts)}
            WHERE id = %s AND (%s IS NULL OR revision = %s)
            RETURNING *
            """,
            values,
        ).fetchone()
        if row is None:
            raise RevisionConflict(f"Revision conflict on sprint {sprint_id!r}")
        return Sprint(**row)

    def delete_sprint(self, sprint_id: str,
        *,
        idempotency_key: str | None = None,
    ) -> None:
        conn = self._get_conn()
        conn.execute("DELETE FROM sprints WHERE id = %s", [sprint_id])

    def replace_sprint_items(
        self,
        sprint_id: str,
        items: Sequence[SprintItemInput],
        *,
        idempotency_key: str | None = None,
    ) -> list[SprintItem]:
        conn = self._get_conn()
        result = []
        with conn.transaction():
            conn.execute(
                "DELETE FROM sprint_items WHERE sprint_id = %s", [sprint_id]
            )
            for i, item in enumerate(items, 1):
                item_id = item.id or str(uuid.uuid4())
                position = item.position if item.position is not None else i
                row = conn.execute(
                    """
                    INSERT INTO sprint_items
                        (id, sprint_id, content, estimated_complexity, status,
                         source_section, position)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING *
                    """,
                    [
                        item_id, sprint_id, item.content, item.estimated_complexity,
                        item.status, item.source_section, position,
                    ],
                ).fetchone()
                result.append(SprintItem(**row))
        return result

    def list_sprint_items(self, sprint_id: str) -> list[SprintItem]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM sprint_items WHERE sprint_id = %s ORDER BY position",
            [sprint_id],
        ).fetchall()
        return [SprintItem(**row) for row in rows]

    def set_sprint_queue(
        self,
        epic_id: str,
        ordered_sprint_ids: Sequence[str],
        pending: Mapping[str, str],
        *,
        idempotency_key: str | None = None,
    ) -> list[Sprint]:
        conn = self._get_conn()
        ordered_ids = [str(sprint_id) for sprint_id in ordered_sprint_ids]
        pending_map = {str(sprint_id): str(reason) for sprint_id, reason in pending.items()}
        if len(set(ordered_ids)) != len(ordered_ids):
            raise ValueError("Duplicate queued sprint IDs are not allowed")
        overlap = set(ordered_ids) & set(pending_map)
        if overlap:
            raise ValueError(f"Sprints cannot be both queued and pending: {sorted(overlap)}")
        rows = conn.execute(
            "SELECT * FROM sprints WHERE epic_id = %s ORDER BY sprint_number",
            [epic_id],
        ).fetchall()
        known_ids = {str(row["id"]) for row in rows}
        unknown = sorted((set(ordered_ids) | set(pending_map)) - known_ids)
        if unknown:
            raise FileNotFoundError(f"Unknown sprint IDs for epic {epic_id!r}: {unknown}")
        missing_reason_ids = sorted(sprint_id for sprint_id, reason in pending_map.items() if not reason.strip())
        if missing_reason_ids:
            raise ValueError(f"Pending sprints require a reason: {missing_reason_ids}")
        with conn.transaction():
            for row in rows:
                sprint_id = str(row["id"])
                if sprint_id in ordered_ids:
                    conn.execute(
                        """
                        UPDATE sprints
                        SET status = 'queued', queue_position = %s, pending_reason = NULL,
                            queued_at = now(), revision = revision + 1, updated_at = now()
                        WHERE id = %s AND epic_id = %s
                        """,
                        [ordered_ids.index(sprint_id) + 1, sprint_id, epic_id],
                    )
                elif sprint_id in pending_map:
                    conn.execute(
                        """
                        UPDATE sprints
                        SET status = 'pending', pending_reason = %s,
                            queue_position = NULL, queued_at = NULL,
                            revision = revision + 1, updated_at = now()
                        WHERE id = %s AND epic_id = %s
                        """,
                        [pending_map[sprint_id], sprint_id, epic_id],
                    )
                else:
                    conn.execute(
                        """
                        UPDATE sprints
                        SET status = CASE WHEN status IN ('queued', 'pending') THEN 'proposed' ELSE status END,
                            queue_position = NULL, pending_reason = NULL, queued_at = NULL,
                            revision = revision + 1, updated_at = now()
                        WHERE id = %s AND epic_id = %s
                        """,
                        [sprint_id, epic_id],
                    )
        rows = conn.execute(
            "SELECT * FROM sprints WHERE epic_id = %s ORDER BY COALESCE(queue_position, 9999), sprint_number, id",
            [epic_id],
        ).fetchall()
        return [Sprint(**row) for row in rows]

    # ------------------------------------------------------------------
    # T8: External Requests
    # ------------------------------------------------------------------

    def insert_pending(
        self,
        *,
        idempotency_key: str,
        provider: str,
        endpoint: str,
        request_summary: dict,
        request_body: dict | None = None,
        turn_id: str | None = None,
        tool_call_id: str | None = None,
    ) -> ExternalRequest:
        self._require_actor()
        conn = self._get_conn()
        row = conn.execute(
            """
            INSERT INTO external_requests
                (id, idempotency_key, provider, endpoint, request_summary,
                 request_body, turn_id, tool_call_id, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'pending')
            RETURNING *
            """,
            [
                str(uuid.uuid4()), idempotency_key, provider, endpoint,
                _jb(request_summary), _jb(request_body),
                turn_id, tool_call_id,
            ],
        ).fetchone()
        return ExternalRequest(**row)

    def mark_confirmed(
        self,
        request_id: str,
        *,
        provider_request_id: str | None = None,
        provider_response_summary: dict | None = None,
        idempotency_key: str | None = None,
    ) -> ExternalRequest:
        conn = self._get_conn()
        row = conn.execute(
            """
            UPDATE external_requests
            SET status = 'confirmed',
                provider_request_id = %s,
                provider_response_summary = %s,
                completed_at = now()
            WHERE id = %s
            RETURNING *
            """,
            [provider_request_id, _jb(provider_response_summary), request_id],
        ).fetchone()
        return ExternalRequest(**row)

    def mark_failed(self, request_id: str, *, error_details: dict,
        idempotency_key: str | None = None,
    ) -> ExternalRequest:
        conn = self._get_conn()
        row = conn.execute(
            """
            UPDATE external_requests
            SET status = 'failed', error_details = %s, completed_at = now()
            WHERE id = %s
            RETURNING *
            """,
            [_jb(error_details), request_id],
        ).fetchone()
        return ExternalRequest(**row)

    def find_pending_external_requests(
        self, older_than_seconds: int
    ) -> list[ExternalRequest]:
        conn = self._get_conn()
        rows = conn.execute(
            """
            SELECT * FROM external_requests
            WHERE status = 'pending'
              AND first_attempted_at < now() - (interval '1 second' * %s)
            ORDER BY first_attempted_at
            """,
            [older_than_seconds],
        ).fetchall()
        return [ExternalRequest(**row) for row in rows]

    def mark_orphaned(self, request_id: str, *, error_details: dict,
        idempotency_key: str | None = None,
    ) -> ExternalRequest:
        conn = self._get_conn()
        row = conn.execute(
            """
            UPDATE external_requests
            SET status = 'orphaned', error_details = %s, completed_at = now()
            WHERE id = %s
            RETURNING *
            """,
            [_jb(error_details), request_id],
        ).fetchone()
        return ExternalRequest(**row)

    # ------------------------------------------------------------------
    # T8: Images
    # ------------------------------------------------------------------

    def _next_image_reference(self, epic_id: str, source: str) -> str:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT count(*) AS count FROM images WHERE epic_id = %s AND source = %s",
            [epic_id, source],
        ).fetchone()
        prefix = _SOURCE_REFERENCE_PREFIX.get(source, f"img_{source}")
        return f"{prefix}_{int(row['count']) + 1}"

    def create_image(
        self,
        *,
        epic_id: str,
        source: str,
        storage_url: str,
        prompt: str | None = None,
        quality: str | None = None,
        size: str | None = None,
        reference_key: str | None = None,
        description: str | None = None,
        caption: str | None = None,
        in_body: bool = False,
        active: bool = True,
        discord_attachment_id: str | None = None,
        blob_backend: str | None = None,
        blob_id: str | None = None,
        blob_sha256: str | None = None,
        blob_size_bytes: int | None = None,
        content_type: str | None = None,
        idempotency_key: str | None = None,
    ) -> Image:
        conn = self._get_conn()
        img_id = str(uuid.uuid4())
        ref_key = reference_key or self._next_image_reference(epic_id, source)
        if active:
            DBStore.deactivate_active_image_reference(self, epic_id, ref_key)
        row = conn.execute(
            """
            INSERT INTO images
                (id, epic_id, source, prompt, storage_url, quality, size,
                 reference_key, description, caption, in_body, active,
                 discord_attachment_id, blob_backend, blob_id, blob_sha256,
                 blob_size_bytes, content_type)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            [
                img_id, epic_id, source, prompt, storage_url, quality, size,
                ref_key, description, caption, in_body, active, discord_attachment_id,
                blob_backend, blob_id, blob_sha256, blob_size_bytes, content_type,
            ],
        ).fetchone()
        return Image(**row)

    def attach_image(
        self,
        *,
        epic_id: str,
        content: bytes,
        content_type: str,
        reference_key: str,
        source: str = "user_uploaded",
        prompt: str | None = None,
        quality: str | None = None,
        size: str | None = None,
        description: str | None = None,
        caption: str | None = None,
        in_body: bool = True,
        idempotency_key: str | None = None,
    ) -> Image:
        digest = hashlib.sha256(content).hexdigest()
        blob_id = f"{epic_id}/{reference_key}/{digest}"
        ref = self.blobs.put(blob_id, content, content_type=content_type)
        return self.create_image(
            epic_id=epic_id,
            source=source,
            storage_url=ref.storage_url or f"mp://blob/{blob_id}",
            prompt=prompt,
            quality=quality,
            size=size,
            reference_key=reference_key,
            description=description,
            caption=caption,
            in_body=in_body,
            active=True,
            blob_backend="supabase_storage",
            blob_id=blob_id,
            blob_sha256=digest,
            blob_size_bytes=len(content),
            content_type=content_type,
            idempotency_key=idempotency_key,
        )

    def resolve_image_reference(
        self,
        epic_id: str,
        reference: str,
        *,
        signed: bool = False,
        ttl: int = 3600,
    ) -> str | None:
        key = reference.removeprefix("mp://image/").removeprefix("image:")
        image = self.load_active_image_by_reference(epic_id, key)
        if image is None:
            return None
        if image.blob_id:
            return self.blobs.url(image.blob_id, signed=signed, ttl=ttl)
        return image.storage_url

    def load_image(self, image_id: str) -> Image | None:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM images WHERE id = %s", [image_id]
        ).fetchone()
        return Image(**row) if row else None

    def list_images(
        self,
        *,
        epic_id: str,
        source: str | None = None,
        active: bool | None = True,
    ) -> list[Image]:
        conn = self._get_conn()
        conditions = ["epic_id = %s"]
        values: list[Any] = [epic_id]
        if source is not None:
            conditions.append("source = %s")
            values.append(source)
        if active is not None:
            conditions.append("active = %s")
            values.append(active)
        rows = conn.execute(
            f"SELECT * FROM images WHERE {' AND '.join(conditions)} ORDER BY created_at DESC",
            values,
        ).fetchall()
        return [Image(**row) for row in rows]

    def update_image(self, image_id: str, *, idempotency_key: str | None = None,
        **changes: Any) -> Image:
        conn = self._get_conn()
        set_parts = [f"{k} = %s" for k in changes]
        values = list(changes.values()) + [image_id]
        row = conn.execute(
            f"UPDATE images SET {', '.join(set_parts)} WHERE id = %s RETURNING *",
            values,
        ).fetchone()
        return Image(**row)

    def list_active_images(self, epic_id: str) -> list[Image]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM images WHERE epic_id = %s AND active = true ORDER BY created_at DESC",
            [epic_id],
        ).fetchall()
        return [Image(**row) for row in rows]

    def load_active_image_by_reference(
        self, epic_id: str, reference_key: str
    ) -> Image | None:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM images WHERE epic_id = %s AND reference_key = %s AND active = true",
            [epic_id, reference_key],
        ).fetchone()
        return Image(**row) if row else None

    def active_image_reference_exists(
        self, epic_id: str, reference_key: str
    ) -> bool:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT 1 FROM images WHERE epic_id = %s AND reference_key = %s AND active = true LIMIT 1",
            [epic_id, reference_key],
        ).fetchone()
        return row is not None

    def deactivate_active_image_reference(
        self, epic_id: str, reference_key: str,
        *,
        idempotency_key: str | None = None,
    ) -> list[Image]:
        conn = self._get_conn()
        rows = conn.execute(
            """
            UPDATE images SET active = false
            WHERE epic_id = %s AND reference_key = %s AND active = true
            RETURNING *
            """,
            [epic_id, reference_key],
        ).fetchall()
        return [Image(**row) for row in rows]

    # ------------------------------------------------------------------
    # T8: Second Opinions
    # ------------------------------------------------------------------

    def create_second_opinion(
        self,
        *,
        epic_id: str,
        requested_by: str,
        focus_areas: Sequence[str],
        raw_response: str,
        score: int,
        summary: str,
        verdict: str,
        model_used: str,
        resulting_checklist_item_ids: Sequence[str] | None = None,
        idempotency_key: str | None = None,
    ) -> SecondOpinion:
        conn = self._get_conn()
        row = conn.execute(
            """
            INSERT INTO second_opinions
                (id, epic_id, requested_by, focus_areas, raw_response, score,
                 summary, verdict, model_used, resulting_checklist_item_ids)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            [
                str(uuid.uuid4()), epic_id, requested_by,
                _jb(list(focus_areas)), raw_response, score, summary, verdict,
                model_used, _jb(list(resulting_checklist_item_ids or [])),
            ],
        ).fetchone()
        return SecondOpinion(**row)

    def list_second_opinions(
        self, epic_id: str, *, limit: int | None = None
    ) -> list[SecondOpinion]:
        conn = self._get_conn()
        sql = "SELECT * FROM second_opinions WHERE epic_id = %s ORDER BY requested_at DESC"
        values: list[Any] = [epic_id]
        if limit is not None:
            sql += " LIMIT %s"
            values.append(limit)
        rows = conn.execute(sql, values).fetchall()
        return [SecondOpinion(**row) for row in rows]

    def set_second_opinion_checklist_items(
        self, second_opinion_id: str, checklist_item_ids: Sequence[str],
        *,
        idempotency_key: str | None = None,
    ) -> SecondOpinion:
        conn = self._get_conn()
        row = conn.execute(
            """
            UPDATE second_opinions
            SET resulting_checklist_item_ids = %s
            WHERE id = %s
            RETURNING *
            """,
            [_jb(list(checklist_item_ids)), second_opinion_id],
        ).fetchone()
        return SecondOpinion(**row)

    # ------------------------------------------------------------------
    # T8: Tool Calls
    # ------------------------------------------------------------------

    def record_tool_call(
        self,
        *,
        turn_id: str,
        tool_name: str,
        operation_kind: str,
        arguments: dict,
        result: dict,
        duration_ms: int,
        idempotency_key: str | None = None,
    ) -> ToolCall:
        conn = self._get_conn()
        row = conn.execute(
            """
            INSERT INTO tool_calls
                (id, turn_id, tool_name, operation_kind, arguments, result, duration_ms)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            [
                str(uuid.uuid4()), turn_id, tool_name, operation_kind,
                _jb(arguments), _jb(result), duration_ms,
            ],
        ).fetchone()
        return ToolCall(**row)

    def search_tool_calls_by(
        self,
        *,
        tool_name: str | None = None,
        epic_id: str | None = None,
        since: str | None = None,
        limit: int = 20,
    ) -> list[ToolCall]:
        conn = self._get_conn()
        conditions: list[str] = []
        values: list[Any] = []
        if tool_name is not None:
            conditions.append("tc.tool_name = %s")
            values.append(tool_name)
        if epic_id is not None:
            conditions.append("bt.epic_id = %s")
            values.append(epic_id)
        if since is not None:
            conditions.append("tc.called_at >= %s")
            values.append(since)
        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        values.append(limit)
        rows = conn.execute(
            f"""
            SELECT tc.*
            FROM tool_calls tc
            JOIN bot_turns bt ON tc.turn_id = bt.id
            {where}
            ORDER BY tc.called_at DESC
            LIMIT %s
            """,
            values,
        ).fetchall()
        return [ToolCall(**row) for row in rows]

    # ------------------------------------------------------------------
    # T8: System Logs
    # ------------------------------------------------------------------

    def log_system_event(
        self,
        *,
        level: str,
        category: str,
        event_type: str,
        message: str,
        details: dict | None = None,
        turn_id: str | None = None,
        epic_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> SystemLog:
        conn = self._get_conn()
        row = conn.execute(
            """
            INSERT INTO system_logs
                (id, level, category, event_type, message, details, turn_id, epic_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            [
                str(uuid.uuid4()), level, category, event_type, message,
                _jb(details or {}), turn_id, epic_id,
            ],
        ).fetchone()
        return SystemLog(**row)

    # ------------------------------------------------------------------
    # T9: Codebases
    # ------------------------------------------------------------------

    def create_codebase(
        self,
        *,
        owner: str,
        name: str,
        default_branch: str,
        repo_url: str | None = None,
        repo_workspace: str | None = None,
        scope: str = "global",
        group_name: str | None = None,
        associated_epic_id: str | None = None,
        added_via: str = "manual",
        verified_accessible_at: str | None = None,
        notes: str | None = None,
        codebase_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> Codebase:
        conn = self._get_conn()
        row = conn.execute(
            """
            INSERT INTO codebases
                (id, owner, name, repo_url, repo_workspace, default_branch, scope, group_name,
                 associated_epic_id, added_via, verified_accessible_at, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            [
                codebase_id or str(uuid.uuid4()),
                owner.lower(), name.lower(), repo_url, repo_workspace, default_branch, scope, group_name,
                associated_epic_id, added_via, verified_accessible_at, notes,
            ],
        ).fetchone()
        return Codebase(**row)

    def upsert_codebase(
        self,
        *,
        owner: str,
        name: str,
        default_branch: str,
        repo_url: str | None = None,
        repo_workspace: str | None = None,
        scope: str = "global",
        group_name: str | None = None,
        associated_epic_id: str | None = None,
        added_via: str = "manual",
        verified_accessible_at: str | None = None,
        notes: str | None = None,
        idempotency_key: str | None = None,
    ) -> Codebase:
        conn = self._get_conn()
        row = conn.execute(
            """
            INSERT INTO codebases
                (id, owner, name, repo_url, repo_workspace, default_branch, scope, group_name,
                 associated_epic_id, added_via, verified_accessible_at, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (lower(owner), lower(name)) DO UPDATE SET
                repo_url             = EXCLUDED.repo_url,
                repo_workspace       = EXCLUDED.repo_workspace,
                default_branch       = EXCLUDED.default_branch,
                scope                = EXCLUDED.scope,
                group_name           = EXCLUDED.group_name,
                associated_epic_id   = EXCLUDED.associated_epic_id,
                added_via            = EXCLUDED.added_via,
                verified_accessible_at = EXCLUDED.verified_accessible_at,
                notes                = EXCLUDED.notes
            RETURNING *
            """,
            [
                str(uuid.uuid4()),
                owner.lower(), name.lower(), repo_url, repo_workspace, default_branch, scope, group_name,
                associated_epic_id, added_via, verified_accessible_at, notes,
            ],
        ).fetchone()
        return Codebase(**row)

    def load_codebase(self, codebase_id: str) -> Codebase | None:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM codebases WHERE id = %s", [codebase_id]
        ).fetchone()
        return Codebase(**row) if row else None

    def find_codebase(self, owner: str, name: str) -> Codebase | None:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM codebases WHERE lower(owner) = lower(%s) AND lower(name) = lower(%s)",
            [owner, name],
        ).fetchone()
        return Codebase(**row) if row else None

    def list_codebases(
        self,
        *,
        scope: str | None = None,
        group_name: str | None = None,
        epic_id: str | None = None,
        include_global: bool = True,
    ) -> list[Codebase]:
        conn = self._get_conn()
        conditions: list[str] = []
        values: list[Any] = []
        if scope is not None:
            conditions.append("scope = %s")
            values.append(scope)
        if group_name is not None:
            conditions.append("group_name = %s")
            values.append(group_name)
        if epic_id is not None:
            if include_global:
                conditions.append("(associated_epic_id = %s OR scope = 'global')")
                values.append(epic_id)
            else:
                conditions.append("associated_epic_id = %s")
                values.append(epic_id)
        elif not include_global:
            conditions.append("scope != 'global'")
        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        rows = conn.execute(
            f"SELECT * FROM codebases{where} ORDER BY owner, name",
            values,
        ).fetchall()
        return [Codebase(**row) for row in rows]

    def update_codebase(self, codebase_id: str, *, idempotency_key: str | None = None,
        **changes: Any) -> Codebase:
        conn = self._get_conn()
        set_parts = [f"{k} = %s" for k in changes]
        values = list(changes.values()) + [codebase_id]
        row = conn.execute(
            f"UPDATE codebases SET {', '.join(set_parts)} WHERE id = %s RETURNING *",
            values,
        ).fetchone()
        return Codebase(**row)

    def remove_codebase(self, codebase_id: str,
        *,
        idempotency_key: str | None = None,
    ) -> None:
        conn = self._get_conn()
        conn.execute("DELETE FROM codebases WHERE id = %s", [codebase_id])

    def touch_codebase_accessed(
        self, codebase_id: str, *, accessed_at: str | None = None,
        idempotency_key: str | None = None,
    ) -> Codebase:
        conn = self._get_conn()
        if accessed_at is not None:
            row = conn.execute(
                "UPDATE codebases SET last_accessed_at = %s WHERE id = %s RETURNING *",
                [accessed_at, codebase_id],
            ).fetchone()
        else:
            row = conn.execute(
                "UPDATE codebases SET last_accessed_at = now() WHERE id = %s RETURNING *",
                [codebase_id],
            ).fetchone()
        return Codebase(**row)

    def mark_codebase_verified(
        self,
        codebase_id: str,
        *,
        verified_at: str | None = None,
        default_branch: str | None = None,
        idempotency_key: str | None = None,
    ) -> Codebase:
        conn = self._get_conn()
        set_parts = ["verified_accessible_at = " + ("%s" if verified_at else "now()")]
        values: list[Any] = [verified_at] if verified_at else []
        if default_branch is not None:
            set_parts.append("default_branch = %s")
            values.append(default_branch)
        values.append(codebase_id)
        row = conn.execute(
            f"UPDATE codebases SET {', '.join(set_parts)} WHERE id = %s RETURNING *",
            values,
        ).fetchone()
        return Codebase(**row)

    # ------------------------------------------------------------------
    # T9: Code Artifacts
    # ------------------------------------------------------------------

    def create_code_artifact(
        self,
        *,
        kind: str,
        source: str,
        content: str,
        codebase_id: str | None = None,
        epic_id: str | None = None,
        file_path: str | None = None,
        line_range: Any = None,
        scope: str | None = None,
        content_summary: str | None = None,
        metadata: dict | None = None,
        expires_at: str | None = None,
        artifact_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> CodeArtifact:
        conn = self._get_conn()
        row = conn.execute(
            """
            INSERT INTO code_artifacts
                (id, codebase_id, epic_id, kind, source, file_path, line_range,
                 scope, content, content_summary, metadata, expires_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            [
                artifact_id or str(uuid.uuid4()),
                codebase_id, epic_id, kind, source, file_path,
                _jb(line_range), scope, content, content_summary,
                _jb(metadata or {}), expires_at,
            ],
        ).fetchone()
        return CodeArtifact(**row)

    def load_code_artifact(self, artifact_id: str) -> CodeArtifact | None:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM code_artifacts WHERE id = %s", [artifact_id]
        ).fetchone()
        return CodeArtifact(**row) if row else None

    def list_code_artifacts(
        self,
        *,
        codebase_id: str | None = None,
        epic_id: str | None = None,
        kind: str | None = None,
        source: str | None = None,
        file_path: str | None = None,
        scope: str | None = None,
        include_expired: bool = True,
        limit: int | None = 50,
    ) -> list[CodeArtifact]:
        conn = self._get_conn()
        conditions: list[str] = []
        values: list[Any] = []
        if codebase_id is not None:
            conditions.append("codebase_id = %s")
            values.append(codebase_id)
        if epic_id is not None:
            conditions.append("epic_id = %s")
            values.append(epic_id)
        if kind is not None:
            conditions.append("kind = %s")
            values.append(kind)
        if source is not None:
            conditions.append("source = %s")
            values.append(source)
        if file_path is not None:
            conditions.append("file_path = %s")
            values.append(file_path)
        if scope is not None:
            conditions.append("scope = %s")
            values.append(scope)
        if not include_expired:
            conditions.append("(expires_at IS NULL OR expires_at > now())")
        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        sql = f"SELECT * FROM code_artifacts{where} ORDER BY created_at DESC"
        if limit is not None:
            sql += " LIMIT %s"
            values.append(limit)
        rows = conn.execute(sql, values).fetchall()
        return [CodeArtifact(**row) for row in rows]

    def update_code_artifact(self, artifact_id: str, *, idempotency_key: str | None = None,
        **changes: Any) -> CodeArtifact:
        conn = self._get_conn()
        set_parts = [f"{k} = %s" for k in changes]
        values = list(changes.values()) + [artifact_id]
        row = conn.execute(
            f"UPDATE code_artifacts SET {', '.join(set_parts)} WHERE id = %s RETURNING *",
            values,
        ).fetchone()
        return CodeArtifact(**row)

    def delete_code_artifact(self, artifact_id: str,
        *,
        idempotency_key: str | None = None,
    ) -> None:
        conn = self._get_conn()
        conn.execute("DELETE FROM code_artifacts WHERE id = %s", [artifact_id])

    def touch_code_artifact_used(
        self, artifact_id: str, *, used_at: str | None = None,
        idempotency_key: str | None = None,
    ) -> CodeArtifact:
        conn = self._get_conn()
        if used_at is not None:
            row = conn.execute(
                "UPDATE code_artifacts SET last_used_at = %s WHERE id = %s RETURNING *",
                [used_at, artifact_id],
            ).fetchone()
        else:
            row = conn.execute(
                "UPDATE code_artifacts SET last_used_at = now() WHERE id = %s RETURNING *",
                [artifact_id],
            ).fetchone()
        return CodeArtifact(**row)

    # ------------------------------------------------------------------
    # T9: API Cache (kind='api_cache' rows in code_artifacts)
    # ------------------------------------------------------------------

    def get_api_cache(
        self,
        cache_key: str,
        *,
        now: str | None = None,
        touch: bool = True,
    ) -> CodeArtifact | None:
        conn = self._get_conn()
        now_expr = "%s" if now else "now()"
        now_values: list[Any] = [now] if now else []
        row = conn.execute(
            f"""
            SELECT * FROM code_artifacts
            WHERE kind = 'api_cache'
              AND metadata->>'cache_key' = %s
              AND (expires_at IS NULL OR expires_at > {now_expr})
            LIMIT 1
            """,
            [cache_key] + now_values,
        ).fetchone()
        if row is None:
            return None
        if touch:
            row = conn.execute(
                "UPDATE code_artifacts SET last_used_at = now() WHERE id = %s RETURNING *",
                [row["id"]],
            ).fetchone()
        return CodeArtifact(**row)

    def upsert_api_cache(
        self,
        *,
        cache_key: str,
        content: str,
        content_summary: str | None = None,
        metadata: dict | None = None,
        codebase_id: str | None = None,
        epic_id: str | None = None,
        file_path: str | None = None,
        scope: str | None = None,
        expires_at: str | None = None,
        ttl_seconds: int = 3600,
        idempotency_key: str | None = None,
    ) -> CodeArtifact:
        conn = self._get_conn()
        full_meta = dict(metadata or {})
        full_meta["cache_key"] = cache_key
        expires_expr = "%s" if expires_at else "now() + interval '1 second' * %s"
        expires_val: Any = expires_at if expires_at else ttl_seconds
        existing = conn.execute(
            "SELECT id FROM code_artifacts WHERE kind = 'api_cache' AND metadata->>'cache_key' = %s LIMIT 1",
            [cache_key],
        ).fetchone()
        if existing:
            row = conn.execute(
                f"""
                UPDATE code_artifacts
                SET content = %s, content_summary = %s, metadata = %s,
                    codebase_id = %s, epic_id = %s, file_path = %s,
                    scope = %s, expires_at = {expires_expr}, last_used_at = now()
                WHERE id = %s
                RETURNING *
                """,
                [
                    content, content_summary, _jb(full_meta),
                    codebase_id, epic_id, file_path, scope,
                    expires_val, existing["id"],
                ],
            ).fetchone()
        else:
            row = conn.execute(
                f"""
                INSERT INTO code_artifacts
                    (id, kind, source, content, content_summary, metadata,
                     codebase_id, epic_id, file_path, scope, expires_at)
                VALUES (%s, 'api_cache', 'conversation', %s, %s, %s, %s, %s, %s, %s, {expires_expr})
                RETURNING *
                """,
                [
                    str(uuid.uuid4()), content, content_summary, _jb(full_meta),
                    codebase_id, epic_id, file_path, scope, expires_val,
                ],
            ).fetchone()
        return CodeArtifact(**row)

    def cleanup_expired_api_cache(self, *, now: str | None = None,
        idempotency_key: str | None = None,
    ) -> int:
        conn = self._get_conn()
        now_expr = "%s" if now else "now()"
        values: list[Any] = [now] if now else []
        cur = conn.execute(
            f"""
            DELETE FROM code_artifacts
            WHERE kind = 'api_cache'
              AND expires_at IS NOT NULL
              AND expires_at < {now_expr}
            """,
            values,
        )
        return cur.rowcount

    # ------------------------------------------------------------------
    # T9: Feedback
    # ------------------------------------------------------------------

    def create_feedback(
        self,
        *,
        kind: str,
        content: str,
        source: str,
        source_message_id: str | None = None,
        epic_id: str | None = None,
        turn_id: str | None = None,
        context_snapshot: dict | None = None,
        idempotency_key: str | None = None,
    ) -> Feedback:
        conn = self._get_conn()
        row = conn.execute(
            """
            INSERT INTO feedback
                (id, kind, content, source, source_message_id, epic_id,
                 turn_id, context_snapshot)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            [
                str(uuid.uuid4()), kind, content, source, source_message_id,
                epic_id, turn_id, _jb(context_snapshot),
            ],
        ).fetchone()
        return Feedback(**row)

    def load_feedback(self, feedback_id: str) -> Feedback | None:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM feedback WHERE id = %s", [feedback_id]
        ).fetchone()
        return Feedback(**row) if row else None

    def update_feedback(self, feedback_id: str, *, idempotency_key: str | None = None,
        **changes: Any) -> Feedback:
        conn = self._get_conn()
        set_parts = [f"{k} = %s" for k in changes]
        values = list(changes.values())
        if changes.get("resolved") is True and "resolved_at" not in changes:
            set_parts.append("resolved_at = now()")
        values.append(feedback_id)
        row = conn.execute(
            f"UPDATE feedback SET {', '.join(set_parts)} WHERE id = %s RETURNING *",
            values,
        ).fetchone()
        return Feedback(**row)

    def list_feedback(
        self,
        *,
        epic_id: str | None = None,
        active: bool | None = None,
        kinds: Sequence[str] | None = None,
        limit: int | None = None,
    ) -> list[Feedback]:
        conn = self._get_conn()
        conditions: list[str] = []
        values: list[Any] = []
        if epic_id is not None:
            conditions.append("epic_id = %s")
            values.append(epic_id)
        if active is not None:
            conditions.append("active = %s")
            values.append(active)
        if kinds is not None:
            conditions.append("kind = ANY(%s)")
            values.append(list(kinds))
        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        sql = f"SELECT * FROM feedback{where} ORDER BY created_at DESC"
        if limit is not None:
            sql += " LIMIT %s"
            values.append(limit)
        rows = conn.execute(sql, values).fetchall()
        return [Feedback(**row) for row in rows]

    def list_observations(
        self,
        *,
        resolved: bool | None = None,
        limit: int | None = None,
    ) -> list[Feedback]:
        conn = self._get_conn()
        obs_kinds = ["friction", "ambiguity", "tool_failure", "confusion", "pattern_noticed"]
        conditions = ["kind = ANY(%s)"]
        values: list[Any] = [obs_kinds]
        if resolved is not None:
            conditions.append("resolved = %s")
            values.append(resolved)
        sql = f"SELECT * FROM feedback WHERE {' AND '.join(conditions)} ORDER BY created_at DESC"
        if limit is not None:
            sql += " LIMIT %s"
            values.append(limit)
        rows = conn.execute(sql, values).fetchall()
        return [Feedback(**row) for row in rows]

    # ------------------------------------------------------------------
    # T7 — Events
    # ------------------------------------------------------------------

    def record_epic_event(
        self,
        *,
        epic_id: str,
        transaction_id: str,
        event_type: str,
        summary: str,
        prior_state: dict[str, Any] | None,
        pre_state: dict[str, Any] | None = None,
        post_state: dict[str, Any] | None = None,
        pre_state_canonical_json: str | None = None,
        post_state_canonical_json: str | None = None,
        pre_state_sha256: str | None = None,
        post_state_sha256: str | None = None,
        turn_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> EpicEvent:
        conn = self._get_conn()
        row = conn.execute(
            """
            INSERT INTO epic_events (
                id, epic_id, transaction_id, event_type, summary, prior_state,
                pre_state, post_state, pre_state_canonical_json,
                post_state_canonical_json, pre_state_sha256, post_state_sha256,
                turn_id
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            [
                str(uuid.uuid4()), epic_id, transaction_id, event_type, summary,
                _jb(prior_state), _jb(pre_state), _jb(post_state),
                pre_state_canonical_json, post_state_canonical_json,
                pre_state_sha256, post_state_sha256, turn_id,
            ],
        ).fetchone()
        return EpicEvent(**row)

    def list_epic_events(
        self,
        epic_id: str,
        *,
        since: str | None = None,
        until: str | None = None,
        kinds: Sequence[str] | None = None,
        limit: int | None = None,
    ) -> list[EpicEvent]:
        conn = self._get_conn()
        conditions = ["epic_id = %s"]
        values: list[Any] = [epic_id]
        if since is not None:
            conditions.append("occurred_at >= %s::timestamptz")
            values.append(since)
        if until is not None:
            conditions.append("occurred_at <= %s::timestamptz")
            values.append(until)
        if kinds is not None:
            conditions.append("event_type = ANY(%s)")
            values.append(list(kinds))
        sql = f"SELECT * FROM epic_events WHERE {' AND '.join(conditions)} ORDER BY occurred_at DESC"
        if limit is not None:
            sql += " LIMIT %s"
            values.append(limit)
        rows = conn.execute(sql, values).fetchall()
        return [EpicEvent(**row) for row in rows]

    def list_epic_events_for_replay(self, epic_id: str) -> list[EpicEvent]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM epic_events WHERE epic_id = %s ORDER BY occurred_at ASC, id ASC",
            [epic_id],
        ).fetchall()
        return [EpicEvent(**row) for row in rows]

    def latest_transaction_id(self, epic_id: str) -> str | None:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT transaction_id FROM epic_events WHERE epic_id = %s ORDER BY occurred_at DESC, id DESC LIMIT 1",
            [epic_id],
        ).fetchone()
        return row["transaction_id"] if row else None

    def events_by_transaction(self, transaction_id: str) -> list[EpicEvent]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM epic_events WHERE transaction_id = %s ORDER BY occurred_at",
            [transaction_id],
        ).fetchall()
        return [EpicEvent(**row) for row in rows]

    # ------------------------------------------------------------------
    # T7 — Messages
    # ------------------------------------------------------------------

    def _next_invocation_message_id(self, turn_id: str) -> str:
        conn = self._get_conn()
        row = conn.execute(
            """
            SELECT count(*) AS count
            FROM messages
            WHERE bot_turn_id = %s AND direction = 'outbound'
            """,
            [turn_id],
        ).fetchone()
        return f"inv_{turn_id}_{int(row['count']) + 1}"

    def create_message(
        self,
        *,
        epic_id: str | None,
        direction: str,
        content: str,
        discord_message_id: str | None = None,
        bot_turn_id: str | None = None,
        has_code_attachment: bool = False,
        has_image_attachment: bool = False,
        in_burst_with: Sequence[str] | None = None,
        was_voice_message: bool = False,
        audio_storage_url: str | None = None,
        transcription_metadata: dict[str, Any] | None = None,
        synthesize_outbound_id: bool = True,
        conversation_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> Message:
        conn = self._get_conn()
        if synthesize_outbound_id and direction == "outbound" and discord_message_id is None and bot_turn_id:
            discord_message_id = self._next_invocation_message_id(bot_turn_id)
        if discord_message_id is not None:
            existing = conn.execute(
                "SELECT * FROM messages WHERE discord_message_id = %s",
                [discord_message_id],
            ).fetchone()
            if existing is not None:
                changes: dict[str, Any] = {}
                if conversation_id is not None and existing["conversation_id"] is None:
                    changes["conversation_id"] = conversation_id
                if idempotency_key is not None and existing["idempotency_key"] is None:
                    changes["idempotency_key"] = idempotency_key
                if bot_turn_id is not None and existing["bot_turn_id"] is None:
                    changes["bot_turn_id"] = bot_turn_id
                if changes:
                    set_parts = [f"{column} = %s" for column in changes]
                    existing = conn.execute(
                        f"UPDATE messages SET {', '.join(set_parts)} WHERE id = %s RETURNING *",
                        [*changes.values(), existing["id"]],
                    ).fetchone()
                return Message(**existing)
        row = conn.execute(
            """
            INSERT INTO messages (
                id, epic_id, conversation_id, idempotency_key, direction, content, discord_message_id, bot_turn_id,
                has_code_attachment, has_image_attachment, in_burst_with,
                was_voice_message, audio_storage_url, transcription_metadata
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (idempotency_key) WHERE idempotency_key IS NOT NULL DO UPDATE
            SET idempotency_key = EXCLUDED.idempotency_key
            RETURNING *
            """,
            [
                str(uuid.uuid4()), epic_id, conversation_id, idempotency_key,
                direction, content, discord_message_id,
                bot_turn_id, has_code_attachment, has_image_attachment,
                _jb(list(in_burst_with) if in_burst_with is not None else None),
                was_voice_message, audio_storage_url, _jb(transcription_metadata),
            ],
        ).fetchone()
        return Message(**row)

    def load_message(self, message_id: str) -> Message | None:
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM messages WHERE id = %s", [message_id]).fetchone()
        return Message(**row) if row else None

    def load_messages(self, message_ids: Sequence[str]) -> list[Message]:
        conn = self._get_conn()
        if not message_ids:
            return []
        rows = conn.execute(
            "SELECT * FROM messages WHERE id = ANY(%s::text[]) ORDER BY array_position(%s::text[], id)",
            [list(message_ids), list(message_ids)],
        ).fetchall()
        return [Message(**row) for row in rows]

    def update_message(self, message_id: str, *, idempotency_key: str | None = None,
        **changes: Any) -> Message:
        conn = self._get_conn()
        if not changes:
            row = conn.execute("SELECT * FROM messages WHERE id = %s", [message_id]).fetchone()
            if row is None:
                raise RevisionConflict(f"Message {message_id!r} not found")
            return Message(**row)
        set_parts = [f"{k} = %s" for k in changes]
        values = list(changes.values()) + [message_id]
        row = conn.execute(
            f"UPDATE messages SET {', '.join(set_parts)} WHERE id = %s RETURNING *",
            values,
        ).fetchone()
        if row is None:
            raise RevisionConflict(f"Message {message_id!r} not found")
        return Message(**row)

    def latest_outbound_message(self, *, epic_id: str | None = None) -> Message | None:
        conn = self._get_conn()
        if epic_id is not None:
            row = conn.execute(
                "SELECT * FROM messages WHERE direction = 'outbound' AND epic_id = %s ORDER BY sent_at DESC LIMIT 1",
                [epic_id],
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM messages WHERE direction = 'outbound' ORDER BY sent_at DESC LIMIT 1",
            ).fetchone()
        return Message(**row) if row else None

    def search_messages(
        self,
        *,
        query: str,
        epic_id: str | None = None,
        limit: int = 20,
    ) -> list[MessageSearchHit]:
        conn = self._get_conn()
        conditions = [
            "(to_tsvector('english', m.content) @@ websearch_to_tsquery('english', %s) "
            "OR lower(m.content) LIKE lower(%s))"
        ]
        values: list[Any] = [query, f"%{query}%"]
        if epic_id is not None:
            conditions.append("m.epic_id = %s")
            values.append(epic_id)
        where = " AND ".join(conditions)
        values = [query, query, *values, limit]
        rows = conn.execute(
            f"""
            SELECT m.*,
                   ts_headline('english', m.content, websearch_to_tsquery('english', %s)) AS snippet,
                   ts_rank(to_tsvector('english', m.content), websearch_to_tsquery('english', %s)) AS rank
            FROM messages m
            WHERE {where}
            ORDER BY rank DESC
            LIMIT %s
            """,
            values,
        ).fetchall()
        return [MessageSearchHit(**row) for row in rows]

    def find_unprocessed_messages(
        self,
        epic_id: str,
        started_at: str,
        exclude_ids: Sequence[str],
    ) -> list[Message]:
        conn = self._get_conn()
        rows = conn.execute(
            """
            SELECT * FROM messages m
            WHERE m.epic_id = %s
              AND m.direction = 'inbound'
              AND m.bot_turn_id IS NULL
              AND m.sent_at >= %s::timestamptz
              AND NOT (m.id = ANY(%s::text[]))
            ORDER BY m.sent_at, m.id
            """,
            [epic_id, started_at, list(exclude_ids)],
        ).fetchall()
        return [Message(**row) for row in rows]

    # ------------------------------------------------------------------
    # T7 — Turns
    # ------------------------------------------------------------------

    def create_turn(
        self,
        *,
        epic_id: str | None,
        triggered_by_message_ids: Sequence[str],
        prompt_snapshot: dict[str, Any] | None = None,
        prompt_version: str | None = None,
        state_at_turn: dict[str, Any] | None = None,
        model_version: str | None = None,
        idempotency_key: str | None = None,
    ) -> BotTurn:
        conn = self._get_conn()
        row = conn.execute(
            """
            INSERT INTO bot_turns (
                id, epic_id, triggered_by_message_ids, prompt_snapshot,
                prompt_version, state_at_turn, model_version, status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'in_progress')
            RETURNING *
            """,
            [
                str(uuid.uuid4()), epic_id,
                _jb(list(triggered_by_message_ids)),
                _jb(prompt_snapshot), prompt_version,
                _jb(state_at_turn), model_version,
            ],
        ).fetchone()
        return BotTurn(**row)

    def update_turn(self, turn_id: str, *, idempotency_key: str | None = None,
        **changes: Any) -> BotTurn:
        conn = self._get_conn()
        if not changes:
            row = conn.execute("SELECT * FROM bot_turns WHERE id = %s", [turn_id]).fetchone()
            if row is None:
                raise RevisionConflict(f"Turn {turn_id!r} not found")
            return BotTurn(**row)
        jsonb_turn_cols = frozenset({
            "triggered_by_message_ids", "prompt_snapshot", "state_at_turn",
            "warnings_issued",
        })
        set_parts = [f"{k} = %s" for k in changes]
        if changes.get("status") in {"completed", "failed", "abandoned"} and "completed_at" not in changes:
            set_parts.append("completed_at = now()")
        values = [_jb(v) if k in jsonb_turn_cols else v for k, v in changes.items()]
        values.append(turn_id)
        row = conn.execute(
            f"UPDATE bot_turns SET {', '.join(set_parts)} WHERE id = %s RETURNING *",
            values,
        ).fetchone()
        if row is None:
            raise RevisionConflict(f"Turn {turn_id!r} not found")
        return BotTurn(**row)

    def find_abandoned_turns(self, older_than_seconds: int) -> list[BotTurn]:
        conn = self._get_conn()
        rows = conn.execute(
            """
            SELECT * FROM bot_turns
            WHERE status = 'in_progress'
              AND started_at < now() - make_interval(secs => %s)
            ORDER BY started_at
            """,
            [older_than_seconds],
        ).fetchall()
        return [BotTurn(**row) for row in rows]

    def list_recent_turns(
        self,
        *,
        n: int = 10,
        epic_id: str | None = None,
    ) -> list[BotTurn]:
        conn = self._get_conn()
        if epic_id is not None:
            rows = conn.execute(
                "SELECT * FROM bot_turns WHERE epic_id = %s ORDER BY started_at DESC LIMIT %s",
                [epic_id, n],
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM bot_turns ORDER BY started_at DESC LIMIT %s",
                [n],
            ).fetchall()
        return [BotTurn(**row) for row in rows]

    # ------------------------------------------------------------------
    # T7 — Hot context
    # ------------------------------------------------------------------

    def load_hot_context(self, epic_id: str | None) -> HotContext:
        if epic_id is None:
            return HotContext()
        conn = self._get_conn()
        obs_kinds = ["friction", "ambiguity", "tool_failure", "confusion", "pattern_noticed"]
        with conn.transaction():
            epic_row = conn.execute(
                "SELECT * FROM epics WHERE id = %s", [epic_id]
            ).fetchone()
            msg_rows = conn.execute(
                "SELECT * FROM messages WHERE epic_id = %s ORDER BY sent_at DESC LIMIT 50",
                [epic_id],
            ).fetchall()
            tc_rows = conn.execute(
                """
                SELECT tc.* FROM tool_calls tc
                JOIN bot_turns bt ON tc.turn_id = bt.id
                WHERE bt.epic_id = %s
                ORDER BY tc.called_at DESC LIMIT 20
                """,
                [epic_id],
            ).fetchall()
            af_rows = conn.execute(
                """
                SELECT * FROM feedback
                WHERE epic_id = %s AND resolved = false AND kind != ANY(%s)
                ORDER BY created_at DESC
                """,
                [epic_id, obs_kinds],
            ).fetchall()
            uo_rows = conn.execute(
                """
                SELECT * FROM feedback
                WHERE epic_id = %s AND resolved = false AND kind = ANY(%s)
                ORDER BY created_at DESC
                """,
                [epic_id, obs_kinds],
            ).fetchall()
            sprint_rows = conn.execute(
                """
                SELECT s.*,
                       si.id                    AS si_id,
                       si.sprint_id             AS si_sprint_id,
                       si.content               AS si_content,
                       si.estimated_complexity  AS si_estimated_complexity,
                       si.status                AS si_status,
                       si.source_section        AS si_source_section,
                       si.position              AS si_position,
                       si.created_at            AS si_created_at
                FROM sprints s
                LEFT JOIN sprint_items si ON si.sprint_id = s.id
                WHERE s.epic_id = %s
                ORDER BY s.sprint_number, si.position
                """,
                [epic_id],
            ).fetchall()
            cb_rows = conn.execute(
                "SELECT * FROM codebases WHERE associated_epic_id = %s",
                [epic_id],
            ).fetchall()
            ca_rows = conn.execute(
                "SELECT * FROM code_artifacts WHERE epic_id = %s ORDER BY created_at DESC LIMIT 10",
                [epic_id],
            ).fetchall()
            img_rows = conn.execute(
                "SELECT * FROM images WHERE epic_id = %s AND active = true ORDER BY created_at DESC",
                [epic_id],
            ).fetchall()
            so_rows = conn.execute(
                "SELECT * FROM second_opinions WHERE epic_id = %s ORDER BY requested_at DESC LIMIT 10",
                [epic_id],
            ).fetchall()

        sprints_with_items = self._group_sprint_rows(sprint_rows)
        statuses = {s.status for s in sprints_with_items}
        all_sprints_pending_no_queued = (
            bool(sprints_with_items)
            and "queued" not in statuses
            and all(s.status == "pending" for s in sprints_with_items)
        )
        return HotContext(
            epic=Epic(**epic_row) if epic_row else None,
            recent_messages=[Message(**r) for r in msg_rows],
            recent_tool_calls=[ToolCall(**r) for r in tc_rows],
            active_feedback=[Feedback(**r) for r in af_rows],
            unresolved_observations=[Feedback(**r) for r in uo_rows],
            sprints=sprints_with_items,
            codebases=[Codebase(**r) for r in cb_rows],
            recent_code_artifacts=[CodeArtifact(**r) for r in ca_rows],
            active_images=[Image(**r) for r in img_rows],
            recent_second_opinions=[SecondOpinion(**r) for r in so_rows],
            all_sprints_pending_no_queued=all_sprints_pending_no_queued,
        )

    # ------------------------------------------------------------------
    # T10 — Plans
    # ------------------------------------------------------------------

    def _load_plan_artifacts(
        self, conn: Any, plan_id: str
    ) -> list[PlanArtifact]:
        rows = conn.execute(
            "SELECT * FROM plan_artifacts WHERE plan_id = %s ORDER BY created_at",
            [plan_id],
        ).fetchall()
        artifacts = []
        for row in rows:
            data = {k: v for k, v in row.items() if k in _ARTIFACT_VALID_FIELDS}
            content_bytes = row.get("content_bytes")
            if content_bytes is not None:
                data["content_base64"] = base64.b64encode(bytes(content_bytes)).decode("ascii")
            artifacts.append(PlanArtifact(**data))
        return artifacts

    def _plan_artifact_bytes(self, row: Mapping[str, Any]) -> bytes:
        content_bytes = row.get("content_bytes")
        if content_bytes is not None:
            return bytes(content_bytes)
        content_text = row.get("content_text")
        if content_text is None:
            return b""
        return content_text.encode("utf-8")

    def create_plan(
        self,
        *,
        sprint_id: str | None,
        epic_id: str | None,
        name: str,
        idea: str,
        idempotency_key: str | None = None,
        **fields: Any,
    ) -> Plan:
        conn = self._get_conn()
        plan_id = str(uuid.uuid4())
        data: dict[str, Any] = {
            "id": plan_id,
            "name": name,
            "epic_id": epic_id,
            "sprint_id": sprint_id,
            "idea": idea,
        }
        for k, v in fields.items():
            if k in _PLAN_COLUMNS:
                data[k] = v
        cols = list(data.keys())
        vals = [_jb(v) if k in _PLAN_JSONB else v for k, v in data.items()]
        col_str = ", ".join(cols)
        placeholders = ", ".join(["%s"] * len(cols))
        returning = ", ".join(_PLAN_COLUMNS)
        row = conn.execute(
            f"INSERT INTO plans ({col_str}) VALUES ({placeholders}) RETURNING {returning}",
            vals,
        ).fetchone()
        artifacts = self._load_plan_artifacts(conn, plan_id)
        return Plan(**row, artifacts=artifacts)

    def load_plan(self, plan_id: str) -> Plan | None:
        conn = self._get_conn()
        col_str = ", ".join(_PLAN_COLUMNS)
        row = conn.execute(
            f"SELECT {col_str} FROM plans WHERE id = %s",
            [plan_id],
        ).fetchone()
        if row is None:
            return None
        artifacts = self._load_plan_artifacts(conn, plan_id)
        return Plan(**row, artifacts=artifacts)

    def update_plan(
        self,
        plan_id: str,
        *,
        expected_revision: int,
        idempotency_key: str | None = None,
        **changes: Any,
    ) -> Plan:
        conn = self._get_conn()
        if not changes:
            plan = self.load_plan(plan_id)
            if plan is None:
                raise RevisionConflict(f"Plan {plan_id!r} not found")
            return plan
        set_parts = [f"{k} = %s" for k in changes]
        set_parts.extend(["revision = revision + 1", "updated_at = now()"])
        col_str = ", ".join(_PLAN_COLUMNS)
        values = [_jb(v) if k in _PLAN_JSONB else v for k, v in changes.items()]
        values += [plan_id, expected_revision, expected_revision]
        row = conn.execute(
            f"""
            UPDATE plans
            SET {', '.join(set_parts)}
            WHERE id = %s AND (%s IS NULL OR revision = %s)
            RETURNING {col_str}
            """,
            values,
        ).fetchone()
        if row is None:
            raise RevisionConflict(f"Revision conflict on plan {plan_id!r}")
        artifacts = self._load_plan_artifacts(conn, plan_id)
        return Plan(**row, artifacts=artifacts)

    def list_plans(
        self,
        *,
        sprint_id: str | None = None,
        epic_id: str | None = None,
        include_orphans: bool = False,
    ) -> list[Plan]:
        conn = self._get_conn()
        col_str = ", ".join(_PLAN_COLUMNS)
        conditions: list[str] = []
        values: list[Any] = []
        if sprint_id is not None:
            conditions.append("sprint_id = %s")
            values.append(sprint_id)
        if epic_id is not None:
            conditions.append("epic_id = %s")
            values.append(epic_id)
        if not include_orphans:
            conditions.append("(epic_id IS NOT NULL OR sprint_id IS NOT NULL)")
        where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
        rows = conn.execute(
            f"SELECT {col_str} FROM plans{where} ORDER BY created_at DESC",
            values,
        ).fetchall()
        result = []
        for row in rows:
            artifacts = self._load_plan_artifacts(conn, row["id"])
            result.append(Plan(**row, artifacts=artifacts))
        return result

    # ------------------------------------------------------------------
    # T10 — Plan artifacts
    # ------------------------------------------------------------------

    def write_plan_artifact(
        self,
        plan_id: str,
        name: str,
        data: bytes,
        *,
        expected_revision: int | None = None,
        idempotency_key: str | None = None,
    ) -> ArtifactRef:
        name = validate_plan_artifact_name(name)
        conn = self._get_conn()
        sha256 = hashlib.sha256(data).hexdigest()
        try:
            content_text: str | None = data.decode("utf-8")
        except UnicodeDecodeError:
            content_text = None
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        kind_map = {"json": "json", "md": "markdown", "jsonl": "jsonl"}
        kind = kind_map.get(ext, "raw_text")
        stem = name.rsplit("/", 1)[-1].split(".")[0]
        if stem.startswith("plan_v"):
            role = "plan_version"
        elif stem in ("gate_signals", "gate"):
            role = "gate_signals"
        elif stem.startswith("critique"):
            role = "critique"
        elif stem.startswith("step_receipt"):
            role = "step_receipt"
        elif stem.startswith("execute"):
            role = "execution_output"
        elif stem.startswith("finalize"):
            role = "finalize"
        elif stem.startswith("faults"):
            role = "faults"
        else:
            role = "template"
        row = conn.execute(
            """
            INSERT INTO plan_artifacts (plan_id, name, kind, role, sha256, content_text, content_bytes)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (plan_id, name) DO UPDATE SET
                sha256 = EXCLUDED.sha256,
                content_text = EXCLUDED.content_text,
                content_bytes = EXCLUDED.content_bytes,
                kind = EXCLUDED.kind,
                role = EXCLUDED.role,
                updated_at = now()
            RETURNING plan_id, name, kind, role, sha256, updated_at,
                      COALESCE(octet_length(content_bytes), octet_length(content_text), 0) AS size_bytes
            """,
            [plan_id, name, kind, role, sha256, content_text, data],
        ).fetchone()
        return ArtifactRef(
            plan_id=row["plan_id"],
            name=row["name"],
            kind=row["kind"],
            role=row["role"],
            sha256=row["sha256"],
            size_bytes=row["size_bytes"],
            updated_at=row["updated_at"],
        )

    def read_plan_artifact(self, plan_id: str, name: str) -> bytes | None:
        name = validate_plan_artifact_name(name)
        conn = self._get_conn()
        row = conn.execute(
            "SELECT content_text, content_bytes FROM plan_artifacts WHERE plan_id = %s AND name = %s",
            [plan_id, name],
        ).fetchone()
        if row is None:
            return None
        return self._plan_artifact_bytes(row)

    def list_plan_artifacts(self, plan_id: str) -> list[ArtifactRef]:
        conn = self._get_conn()
        rows = conn.execute(
            """
            SELECT plan_id, name, kind, role, sha256, updated_at,
                   COALESCE(octet_length(content_bytes), octet_length(content_text), 0) AS size_bytes
            FROM plan_artifacts
            WHERE plan_id = %s
            ORDER BY name
            """,
            [plan_id],
        ).fetchall()
        return [
            ArtifactRef(
                plan_id=row["plan_id"],
                name=row["name"],
                kind=row["kind"],
                role=row["role"],
                sha256=row["sha256"],
                size_bytes=row["size_bytes"],
                updated_at=row["updated_at"],
            )
            for row in rows
        ]

    def stat_plan_artifact(self, plan_id: str, name: str) -> ArtifactStat | None:
        name = validate_plan_artifact_name(name)
        conn = self._get_conn()
        row = conn.execute(
            """
            SELECT plan_id, name, sha256, updated_at,
                   COALESCE(octet_length(content_bytes), octet_length(content_text), 0) AS size_bytes
            FROM plan_artifacts
            WHERE plan_id = %s AND name = %s
            """,
            [plan_id, name],
        ).fetchone()
        if row is None:
            return None
        return ArtifactStat(
            plan_id=row["plan_id"],
            name=row["name"],
            sha256=row["sha256"],
            size_bytes=row["size_bytes"],
            updated_at=row["updated_at"],
        )

    # ------------------------------------------------------------------
    # T11 — Execution Leases
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
        conn = self._get_conn()
        if epic_id is None:
            plan_row = conn.execute("SELECT epic_id FROM plans WHERE id = %s", [plan_id]).fetchone()
            epic_id = plan_row["epic_id"] if plan_row else None
        try:
            with conn.transaction():
                conn.execute(
                    "DELETE FROM execution_leases WHERE plan_id = %s AND expires_at <= now()",
                    [plan_id],
                )
                row = conn.execute(
                    """
                    INSERT INTO execution_leases (plan_id, epic_id, holder_id, worker_kind, phase, expires_at)
                    VALUES (%s, %s, %s, %s, 'active', now() + make_interval(secs => %s))
                    RETURNING *
                    """,
                    [plan_id, epic_id, holder_id, worker_kind, ttl_seconds],
                ).fetchone()
        except Exception as exc:
            if getattr(exc, "pgcode", None) == "23505":
                raise LeaseConflict(
                    f"Execution lease already held for plan {plan_id!r}"
                ) from exc
            raise
        return ExecutionLease(**row)

    def heartbeat_lease(self, plan_id: str, holder_id: str,
        *,
        idempotency_key: str | None = None,
    ) -> ExecutionLease:
        conn = self._get_conn()
        row = conn.execute(
            """
            UPDATE execution_leases
            SET heartbeat_at = now(),
                expires_at = now() + (expires_at - heartbeat_at)
            WHERE plan_id = %s AND holder_id = %s
            RETURNING *
            """,
            [plan_id, holder_id],
        ).fetchone()
        if row is None:
            raise LeaseConflict(f"No active lease for plan {plan_id!r} holder {holder_id!r}")
        return ExecutionLease(**row)

    def release_lease(self, plan_id: str, holder_id: str,
        *,
        idempotency_key: str | None = None,
    ) -> None:
        conn = self._get_conn()
        conn.execute(
            "DELETE FROM execution_leases WHERE plan_id = %s AND holder_id = %s",
            [plan_id, holder_id],
        )

    def get_active_lease(self, plan_id: str) -> ExecutionLease | None:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM execution_leases WHERE plan_id = %s AND expires_at > now()",
            [plan_id],
        ).fetchone()
        return ExecutionLease(**row) if row else None

    def find_active_leases_for_epic(self, epic_id: str) -> list[ExecutionLease]:
        conn = self._get_conn()
        rows = conn.execute(
            """
            SELECT * FROM execution_leases
            WHERE epic_id = %s AND expires_at > now()
            ORDER BY expires_at, plan_id
            """,
            [epic_id],
        ).fetchall()
        return [ExecutionLease(**row) for row in rows]

    # ------------------------------------------------------------------
    # T11 — Locks
    # ------------------------------------------------------------------

    def acquire_lock(self, epic_id: str, holder_id: str, ttl_seconds: int,
        *,
        idempotency_key: str | None = None,
    ) -> EpicLock:
        conn = self._get_conn()
        row = conn.execute(
            """
            INSERT INTO epic_locks (epic_id, holder_id, expires_at)
            VALUES (%s, %s, now() + make_interval(secs => %s))
            ON CONFLICT (epic_id) DO UPDATE
            SET holder_id = EXCLUDED.holder_id,
                acquired_at = now(),
                expires_at = EXCLUDED.expires_at
            WHERE epic_locks.expires_at <= now()
               OR epic_locks.holder_id = EXCLUDED.holder_id
            RETURNING *
            """,
            [epic_id, holder_id, ttl_seconds],
        ).fetchone()
        if row is None:
            raise LockConflict(f"Epic lock already held for epic {epic_id!r}")
        return EpicLock(**row)

    def release_lock(self, epic_id: str, holder_id: str,
        *,
        idempotency_key: str | None = None,
    ) -> None:
        conn = self._get_conn()
        conn.execute(
            "DELETE FROM epic_locks WHERE epic_id = %s AND holder_id = %s",
            [epic_id, holder_id],
        )

    # ------------------------------------------------------------------
    # T11 — Control Plane
    # ------------------------------------------------------------------

    def put_control_message(self, msg: ControlMessageInput,
        *,
        idempotency_key: str | None = None,
    ) -> ControlMessage:
        self._require_actor()
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

    # ------------------------------------------------------------------
    # Resident orchestration
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # T11 — Progress Events
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # T11 — Automation Actors
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

    # ------------------------------------------------------------------
    # Migration runs and migration-private copy helpers
    # ------------------------------------------------------------------

    def _migration_run_from_row(self, row: Mapping[str, Any] | None) -> MigrationRun | None:
        return MigrationRun(**row) if row else None

    def create_migration_run(
        self,
        run: MigrationRun,
        *,
        idempotency_key: str | None = None,
    ) -> MigrationRun:
        self._require_actor()
        conn = self._get_conn()
        data = run.model_dump()
        columns = [column for column in _MIGRATION_RUN_COLUMNS if column in data]
        values = [_jb(data[column]) if column in _MIGRATION_RUN_JSONB else data[column] for column in columns]
        row = conn.execute(
            f"""
            INSERT INTO migration_runs ({', '.join(columns)})
            VALUES ({', '.join(['%s'] * len(columns))})
            RETURNING {', '.join(_MIGRATION_RUN_COLUMNS)}
            """,
            values,
        ).fetchone()
        return MigrationRun(**row)

    def load_migration_run(self, migration_id: str) -> MigrationRun | None:
        conn = self._get_conn()
        row = conn.execute(
            f"SELECT {', '.join(_MIGRATION_RUN_COLUMNS)} FROM migration_runs WHERE id = %s",
            [migration_id],
        ).fetchone()
        return self._migration_run_from_row(row)

    def update_migration_run(
        self,
        migration_id: str,
        *,
        idempotency_key: str | None = None,
        **changes: Any,
    ) -> MigrationRun:
        self._require_actor()
        if not changes:
            current = self.load_migration_run(migration_id)
            if current is None:
                raise KeyError(f"Migration run {migration_id!r} not found")
            return current
        invalid = set(changes) - set(_MIGRATION_RUN_COLUMNS)
        if invalid:
            raise ValueError(f"Invalid migration_run columns: {', '.join(sorted(invalid))}")
        conn = self._get_conn()
        set_parts = [f"{column} = %s" for column in changes]
        set_parts.append("updated_at = now()")
        values = [
            _jb(value) if column in _MIGRATION_RUN_JSONB else value
            for column, value in changes.items()
        ]
        values.append(migration_id)
        row = conn.execute(
            f"""
            UPDATE migration_runs
            SET {', '.join(set_parts)}
            WHERE id = %s
            RETURNING {', '.join(_MIGRATION_RUN_COLUMNS)}
            """,
            values,
        ).fetchone()
        if row is None:
            raise KeyError(f"Migration run {migration_id!r} not found")
        return MigrationRun(**row)

    def heartbeat_migration(
        self,
        migration_id: str,
        holder_id: str,
        ttl_seconds: int,
        *,
        idempotency_key: str | None = None,
    ) -> MigrationRun:
        self._require_actor()
        conn = self._get_conn()
        row = conn.execute(
            f"""
            UPDATE migration_runs
            SET updated_at = now(),
                expires_at = now() + make_interval(secs => %s)
            WHERE id = %s
              AND holder_id = %s
              AND completed_at IS NULL
            RETURNING {', '.join(_MIGRATION_RUN_COLUMNS)}
            """,
            [ttl_seconds, migration_id, holder_id],
        ).fetchone()
        if row is None:
            raise LeaseConflict(f"Migration {migration_id!r} is not held by {holder_id!r}")
        return MigrationRun(**row)

    def find_active_migration_for_epic(self, epic_id: str) -> MigrationRun | None:
        conn = self._get_conn()
        row = conn.execute(
            f"""
            SELECT {', '.join(_MIGRATION_RUN_COLUMNS)}
            FROM migration_runs
            WHERE epic_id = %s
              AND completed_at IS NULL
              AND phase NOT IN ('complete', 'aborted')
              AND expires_at > now()
            ORDER BY started_at DESC
            LIMIT 1
            """,
            [epic_id],
        ).fetchone()
        return self._migration_run_from_row(row)

    def claim_expired_migration(
        self,
        migration_id: str,
        holder_id: str,
        ttl_seconds: int,
        *,
        idempotency_key: str | None = None,
    ) -> MigrationRun:
        self._require_actor()
        conn = self._get_conn()
        row = conn.execute(
            f"""
            UPDATE migration_runs
            SET holder_id = %s,
                updated_at = now(),
                expires_at = now() + make_interval(secs => %s)
            WHERE id = %s
              AND completed_at IS NULL
              AND phase NOT IN ('complete', 'aborted')
              AND expires_at <= now()
            RETURNING {', '.join(_MIGRATION_RUN_COLUMNS)}
            """,
            [holder_id, ttl_seconds, migration_id],
        ).fetchone()
        if row is None:
            raise LeaseConflict(f"Migration {migration_id!r} is still active or does not exist")
        return MigrationRun(**row)

    def _copy_sql_identifiers(self, names: Sequence[str]) -> Any:
        if psycopg is None:
            raise _psycopg_import_error
        return psycopg.sql.SQL(", ").join(psycopg.sql.Identifier(name) for name in names)

    def copy_rows_idempotent(self, table: str, rows: list[dict[str, Any]]) -> int:
        """Migration-private copy path for ID-addressed tables.

        Plan artifacts are deliberately excluded because their durable identity is
        ``(plan_id, name)``; use copy_plan_artifacts_idempotent() for those rows.
        """
        self._require_actor()
        if table == "plan_artifacts":
            raise ValueError("plan_artifacts must be copied with copy_plan_artifacts_idempotent")
        allowed_columns = _COPY_TABLE_COLUMNS.get(table)
        if allowed_columns is None:
            raise ValueError(f"Table {table!r} is not supported for migration copy")
        if not rows:
            return 0
        if psycopg is None:
            raise _psycopg_import_error
        conn = self._get_conn()
        inserted = 0
        with conn.transaction():
            for raw_row in rows:
                row = dict(raw_row)
                if "id" not in row:
                    raise ValueError(f"Cannot copy row for {table!r} without id")
                columns = [column for column in row if column in allowed_columns]
                if not columns:
                    raise ValueError(f"Row for {table!r} has no supported columns")
                values = [_jb(row[column]) if column in _COPY_JSONB_COLUMNS else row[column] for column in columns]
                query = psycopg.sql.SQL(
                    "INSERT INTO {table} ({columns}) VALUES ({placeholders}) "
                    "ON CONFLICT (id) DO NOTHING"
                ).format(
                    table=psycopg.sql.Identifier(table),
                    columns=self._copy_sql_identifiers(columns),
                    placeholders=psycopg.sql.SQL(", ").join(psycopg.sql.Placeholder() for _ in columns),
                )
                cur = conn.execute(query, values)
                inserted += cur.rowcount
        return inserted

    def copy_plan_artifacts_idempotent(
        self,
        plan_id: str,
        artifacts: list[PlanArtifact],
    ) -> int:
        self._require_actor()
        if not artifacts:
            return 0
        conn = self._get_conn()
        inserted = 0
        with conn.transaction():
            for artifact in artifacts:
                data = artifact.model_dump()
                name = validate_plan_artifact_name(data["name"])
                row = {
                    "plan_id": plan_id,
                    "name": name,
                    "kind": data["kind"],
                    "role": data["role"],
                    "version": data.get("version"),
                    "batch": data.get("batch"),
                    "phase": data.get("phase"),
                    "content_text": data.get("content_text"),
                    "content_bytes": (
                        base64.b64decode(data["content_base64"])
                        if data.get("content_base64") is not None
                        else None
                    ),
                    "sha256": data["sha256"],
                    "created_at": data.get("created_at"),
                    "updated_at": data.get("updated_at"),
                }
                columns = [column for column, value in row.items() if value is not None]
                values = [row[column] for column in columns]
                query = psycopg.sql.SQL(
                    "INSERT INTO plan_artifacts ({columns}) VALUES ({placeholders}) "
                    "ON CONFLICT (plan_id, name) DO NOTHING"
                ).format(
                    columns=self._copy_sql_identifiers(columns),
                    placeholders=psycopg.sql.SQL(", ").join(psycopg.sql.Placeholder() for _ in columns),
                )
                cur = conn.execute(query, values)
                inserted += cur.rowcount
        return inserted


__all__ = ["DBStore"]
