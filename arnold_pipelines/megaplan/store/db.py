"""Database-backed store for Sprint 2."""

from __future__ import annotations

import functools
import hashlib
import json
import os
from contextlib import contextmanager
from types import TracebackType
from typing import Any, Generator, Mapping

# Lazy import guard: defers ImportError to _get_conn(), not module import,
# so that `from arnold_pipelines.megaplan.store import DBStore` works without psycopg installed.
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
        "Install with: pip install 'arnold[db]'"
    )
    _psycopg_import_error.__cause__ = _e

from arnold_pipelines.megaplan.schemas import (
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
    MigrationRun,
    Plan,
    PlanArtifact,
    ProgressEvent,
    ResidentConversation,
    ResidentUserPreference,
    ScheduledJob,
    SecondOpinion,
    Sprint,
    SprintItem,
    SystemLog,
    Ticket,
    TicketEpicLink,
    ToolCall,
)
from arnold_pipelines.megaplan.store.blob import LocalDirBlobStore, SupabaseStorageBlobStore

from ._db import common as _db_common
from ._db import (
    DBAssetMixin,
    DBChecklistMixin,
    DBConversationMixin,
    DBEpicMixin,
    DBEventMixin,
    DBMigrationMixin,
    DBOperationsMixin,
    DBPlanMixin,
    DBRuntimeMixin,
    DBSprintMixin,
)
from ._db.common import (
    _ARTIFACT_VALID_FIELDS,
    _COPY_JSONB_COLUMNS,
    _COPY_TABLE_COLUMNS,
    _DBTransaction,
    _MIGRATION_RUN_COLUMNS,
    _MIGRATION_RUN_JSONB,
    _OBSERVATION_KINDS,
    _PLAN_COLUMNS,
    _PLAN_JSONB,
    _SOURCE_REFERENCE_PREFIX,
    _jb,
    _parse_datetime,
)

_db_common._JSONB_WRAPPER = _Jsonb

_BOOTSTRAP_ACTOR_ID = "__bootstrap__"
_BOOTSTRAP_IDEMPOTENT_MUTATORS = frozenset({"create_automation_actor"})
# When adding mutating methods to _db/ slice mixins, also add the method name here.
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
    "upsert_resident_user_preference",
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
    "create_ticket",
    "update_ticket",
    "link_ticket_to_epic",
    "unlink_ticket_from_epic",
    "address_tickets_resolved_by_epic",
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
        ResidentUserPreference,
        ScheduledJob,
        SecondOpinion,
        Sprint,
        SprintItem,
        SystemLog,
        Ticket,
        TicketEpicLink,
        ToolCall,
        MigrationRun,
    )
}


class DBStore(
    DBEpicMixin,
    DBChecklistMixin,
    DBSprintMixin,
    DBRuntimeMixin,
    DBAssetMixin,
    DBEventMixin,
    DBConversationMixin,
    DBPlanMixin,
    DBOperationsMixin,
    DBMigrationMixin,
):
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
        if operation == "update_epic":
            validate_epic_update_fields({key: value for key, value in request_kwargs.items() if key != "expected_revision"})
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


__all__ = ["DBStore"]
