"""Database-backed store for Sprint 2."""

from __future__ import annotations

import hashlib
import os
import uuid
from collections import OrderedDict
from contextlib import contextmanager
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
    EpicSummary,
    HotContext,
    LeaseConflict,
    LockConflict,
    MessageSearchHit,
    ProgressEventInput,
    RevisionConflict,
    SprintItemInput,
    SprintWithItems,
)


def _jb(value: Any) -> Any:
    """Wrap a Python dict/list for JSONB column insertion."""
    if value is None:
        return None
    if _Jsonb is not None:
        return _Jsonb(value)
    return value


_PLAN_COLUMNS = (
    "id", "name", "epic_id", "sprint_id", "revision", "idea", "current_state",
    "iteration", "config", "sessions", "plan_versions", "history", "meta",
    "last_gate", "active_step", "clarification", "latest_finalize",
    "latest_review", "latest_execution", "latest_failure", "created_at", "updated_at",
)
_PLAN_JSONB = frozenset({
    "config", "sessions", "plan_versions", "history", "meta", "last_gate",
    "active_step", "clarification", "latest_finalize", "latest_review",
    "latest_execution", "latest_failure",
})
_ARTIFACT_VALID_FIELDS = frozenset({
    "name", "kind", "role", "version", "batch", "phase",
    "content_text", "sha256", "created_at", "updated_at",
})


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
        # Use .get() (not []) so DBStore() without SUPABASE_DB_URL doesn't raise
        # at instantiation time; the error is deferred to _get_conn().
        self._actor_id = actor_id
        self._dsn = dsn or os.environ.get("SUPABASE_DB_URL")
        self._conn: psycopg.Connection | None = None  # type: ignore[type-arg]

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
        expected_revision: int | None = None,
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
                       to_tsvector('english', title || ' ' || goal || ' ' || body),
                       plainto_tsquery('english', %s)
                   ) AS rank
            FROM epics
            WHERE to_tsvector('english', title || ' ' || goal || ' ' || body)
                  @@ plainto_tsquery('english', %s)
              {state_filter}
            ORDER BY rank DESC
            LIMIT %s
            """,
            [query, query, limit],
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

    def update_body(self, epic_id: str, body: str, *, expected_revision: int) -> Epic:
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

    def seed_checklist(self, epic_id: str, items: Sequence[str]) -> list[ChecklistItem]:
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
    ) -> list[ChecklistItem]:
        self._require_actor()
        conn = self._get_conn()
        max_row = conn.execute(
            "SELECT COALESCE(MAX(position), 0) AS max_pos FROM checklist_items WHERE epic_id = %s",
            [epic_id],
        ).fetchone()
        base_pos = max_row["max_pos"]
        result = []
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
        return result

    def update_checklist_item(self, item_id: str, **changes: Any) -> ChecklistItem:
        conn = self._get_conn()
        set_parts = [f"{k} = %s" for k in changes]
        values = list(changes.values())
        if changes.get("status") == "done" and "completed_at" not in changes:
            set_parts.append("completed_at = now()")
        values.append(item_id)
        row = conn.execute(
            f"UPDATE checklist_items SET {', '.join(set_parts)} WHERE id = %s RETURNING *",
            values,
        ).fetchone()
        return ChecklistItem(**row)

    def delete_checklist_items(self, item_ids: Sequence[str]) -> None:
        if not item_ids:
            return
        conn = self._get_conn()
        conn.execute(
            "DELETE FROM checklist_items WHERE id = ANY(%s)",
            [list(item_ids)],
        )

    def replace_checklist(
        self,
        epic_id: str,
        items: Sequence[ChecklistItemInput],
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
        expected_revision: int | None = None,
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

    def delete_sprint(self, sprint_id: str) -> None:
        conn = self._get_conn()
        conn.execute("DELETE FROM sprints WHERE id = %s", [sprint_id])

    def replace_sprint_items(
        self,
        sprint_id: str,
        items: Sequence[SprintItemInput],
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
    ) -> list[Sprint]:
        conn = self._get_conn()
        with conn.transaction():
            # pending leg: sprints transitioning out of queue (need a reason)
            for sprint_id, reason in pending.items():
                conn.execute(
                    """
                    UPDATE sprints
                    SET status = 'pending', pending_reason = %s,
                        queue_position = NULL, updated_at = now()
                    WHERE id = %s AND epic_id = %s
                    """,
                    [reason, sprint_id, epic_id],
                )
            # ordered leg: sprints being placed in queue
            for i, sprint_id in enumerate(ordered_sprint_ids, 1):
                conn.execute(
                    """
                    UPDATE sprints
                    SET status = 'queued', queue_position = %s,
                        queued_at = now(), updated_at = now()
                    WHERE id = %s AND epic_id = %s
                    """,
                    [i, sprint_id, epic_id],
                )
        rows = conn.execute(
            "SELECT * FROM sprints WHERE epic_id = %s ORDER BY sprint_number",
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

    def mark_failed(self, request_id: str, *, error_details: dict) -> ExternalRequest:
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

    def mark_orphaned(self, request_id: str, *, error_details: dict) -> ExternalRequest:
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
    ) -> Image:
        conn = self._get_conn()
        img_id = str(uuid.uuid4())
        ref_key = reference_key or img_id
        row = conn.execute(
            """
            INSERT INTO images
                (id, epic_id, source, prompt, storage_url, quality, size,
                 reference_key, description, caption, in_body, active,
                 discord_attachment_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            [
                img_id, epic_id, source, prompt, storage_url, quality, size,
                ref_key, description, caption, in_body, active, discord_attachment_id,
            ],
        ).fetchone()
        return Image(**row)

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

    def update_image(self, image_id: str, **changes: Any) -> Image:
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
        self, epic_id: str, reference_key: str
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
        self, second_opinion_id: str, checklist_item_ids: Sequence[str]
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
        scope: str = "global",
        group_name: str | None = None,
        associated_epic_id: str | None = None,
        added_via: str = "manual",
        verified_accessible_at: str | None = None,
        notes: str | None = None,
        codebase_id: str | None = None,
    ) -> Codebase:
        conn = self._get_conn()
        row = conn.execute(
            """
            INSERT INTO codebases
                (id, owner, name, default_branch, scope, group_name,
                 associated_epic_id, added_via, verified_accessible_at, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            [
                codebase_id or str(uuid.uuid4()),
                owner.lower(), name.lower(), default_branch, scope, group_name,
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
        scope: str = "global",
        group_name: str | None = None,
        associated_epic_id: str | None = None,
        added_via: str = "manual",
        verified_accessible_at: str | None = None,
        notes: str | None = None,
    ) -> Codebase:
        conn = self._get_conn()
        row = conn.execute(
            """
            INSERT INTO codebases
                (id, owner, name, default_branch, scope, group_name,
                 associated_epic_id, added_via, verified_accessible_at, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (lower(owner), lower(name)) DO UPDATE SET
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
                owner.lower(), name.lower(), default_branch, scope, group_name,
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

    def update_codebase(self, codebase_id: str, **changes: Any) -> Codebase:
        conn = self._get_conn()
        set_parts = [f"{k} = %s" for k in changes]
        values = list(changes.values()) + [codebase_id]
        row = conn.execute(
            f"UPDATE codebases SET {', '.join(set_parts)} WHERE id = %s RETURNING *",
            values,
        ).fetchone()
        return Codebase(**row)

    def remove_codebase(self, codebase_id: str) -> None:
        conn = self._get_conn()
        conn.execute("DELETE FROM codebases WHERE id = %s", [codebase_id])

    def touch_codebase_accessed(
        self, codebase_id: str, *, accessed_at: str | None = None
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

    def update_code_artifact(self, artifact_id: str, **changes: Any) -> CodeArtifact:
        conn = self._get_conn()
        set_parts = [f"{k} = %s" for k in changes]
        values = list(changes.values()) + [artifact_id]
        row = conn.execute(
            f"UPDATE code_artifacts SET {', '.join(set_parts)} WHERE id = %s RETURNING *",
            values,
        ).fetchone()
        return CodeArtifact(**row)

    def delete_code_artifact(self, artifact_id: str) -> None:
        conn = self._get_conn()
        conn.execute("DELETE FROM code_artifacts WHERE id = %s", [artifact_id])

    def touch_code_artifact_used(
        self, artifact_id: str, *, used_at: str | None = None
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

    def cleanup_expired_api_cache(self, *, now: str | None = None) -> int:
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

    def update_feedback(self, feedback_id: str, **changes: Any) -> Feedback:
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
        turn_id: str | None,
    ) -> EpicEvent:
        conn = self._get_conn()
        row = conn.execute(
            """
            INSERT INTO epic_events (id, epic_id, transaction_id, event_type, summary, prior_state, turn_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            [
                str(uuid.uuid4()), epic_id, transaction_id, event_type, summary,
                _jb(prior_state), turn_id,
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

    def latest_transaction_id(self, epic_id: str) -> str | None:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT transaction_id FROM epic_events WHERE epic_id = %s ORDER BY occurred_at DESC LIMIT 1",
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
    ) -> Message:
        conn = self._get_conn()
        row = conn.execute(
            """
            INSERT INTO messages (
                id, epic_id, direction, content, discord_message_id, bot_turn_id,
                has_code_attachment, has_image_attachment, in_burst_with,
                was_voice_message, audio_storage_url, transcription_metadata
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            [
                str(uuid.uuid4()), epic_id, direction, content, discord_message_id,
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
            "SELECT * FROM messages WHERE id = ANY(%s::text[]) ORDER BY sent_at",
            [list(message_ids)],
        ).fetchall()
        return [Message(**row) for row in rows]

    def update_message(self, message_id: str, **changes: Any) -> Message:
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
        conditions = ["m.content @@ websearch_to_tsquery('english', %s)"]
        values: list[Any] = [query]
        if epic_id is not None:
            conditions.append("m.epic_id = %s")
            values.append(epic_id)
        where = " AND ".join(conditions)
        values.extend([query, query, limit])
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
              AND m.sent_at >= %s::timestamptz
              AND NOT (m.id = ANY(%s::text[]))
              AND NOT EXISTS (
                  SELECT 1 FROM bot_turns bt
                  WHERE bt.triggered_by_message_ids @> jsonb_build_array(m.id)
              )
            ORDER BY m.sent_at
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

    def update_turn(self, turn_id: str, **changes: Any) -> BotTurn:
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
        return [
            PlanArtifact(**{k: v for k, v in row.items() if k in _ARTIFACT_VALID_FIELDS})
            for row in rows
        ]

    def create_plan(
        self,
        *,
        sprint_id: str | None,
        epic_id: str | None,
        name: str,
        idea: str,
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
        expected_revision: int | None = None,
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
    ) -> ArtifactRef:
        conn = self._get_conn()
        sha256 = hashlib.sha256(data).hexdigest()
        content_text = data.decode("utf-8")
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        kind_map = {"json": "json", "md": "markdown", "jsonl": "jsonl"}
        kind = kind_map.get(ext, "raw_text")
        stem = name.split(".")[0]
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
            INSERT INTO plan_artifacts (plan_id, name, kind, role, sha256, content_text)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (plan_id, name) DO UPDATE SET
                sha256 = EXCLUDED.sha256,
                content_text = EXCLUDED.content_text,
                kind = EXCLUDED.kind,
                role = EXCLUDED.role,
                updated_at = now()
            RETURNING plan_id, name, kind, role, sha256, updated_at,
                      octet_length(content_text) AS size_bytes
            """,
            [plan_id, name, kind, role, sha256, content_text],
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
        conn = self._get_conn()
        row = conn.execute(
            "SELECT content_text FROM plan_artifacts WHERE plan_id = %s AND name = %s",
            [plan_id, name],
        ).fetchone()
        if row is None:
            return None
        return row["content_text"].encode("utf-8")

    def list_plan_artifacts(self, plan_id: str) -> list[ArtifactRef]:
        conn = self._get_conn()
        rows = conn.execute(
            """
            SELECT plan_id, name, kind, role, sha256, updated_at,
                   octet_length(content_text) AS size_bytes
            FROM plan_artifacts
            WHERE plan_id = %s
            ORDER BY created_at
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
        conn = self._get_conn()
        row = conn.execute(
            """
            SELECT plan_id, name, sha256, updated_at,
                   octet_length(content_text) AS size_bytes
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
    ) -> ExecutionLease:
        conn = self._get_conn()
        try:
            with conn.transaction():
                conn.execute(
                    "DELETE FROM execution_leases WHERE plan_id = %s AND expires_at <= now()",
                    [plan_id],
                )
                row = conn.execute(
                    """
                    INSERT INTO execution_leases (plan_id, holder_id, worker_kind, phase, expires_at)
                    VALUES (%s, %s, %s, 'active', now() + make_interval(secs => %s))
                    RETURNING *
                    """,
                    [plan_id, holder_id, worker_kind, ttl_seconds],
                ).fetchone()
        except Exception as exc:
            if getattr(exc, "pgcode", None) == "23505":
                raise LeaseConflict(
                    f"Execution lease already held for plan {plan_id!r}"
                ) from exc
            raise
        return ExecutionLease(**row)

    def heartbeat_lease(self, plan_id: str, holder_id: str) -> ExecutionLease:
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

    def release_lease(self, plan_id: str, holder_id: str) -> None:
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

    # ------------------------------------------------------------------
    # T11 — Locks
    # ------------------------------------------------------------------

    def acquire_lock(self, epic_id: str, holder_id: str, ttl_seconds: int) -> EpicLock:
        conn = self._get_conn()
        try:
            row = conn.execute(
                """
                INSERT INTO epic_locks (epic_id, holder_id, expires_at)
                VALUES (%s, %s, now() + make_interval(secs => %s))
                RETURNING *
                """,
                [epic_id, holder_id, ttl_seconds],
            ).fetchone()
        except Exception as exc:
            if getattr(exc, "pgcode", None) == "23505":
                raise LockConflict(f"Epic lock already held for epic {epic_id!r}") from exc
            raise
        return EpicLock(**row)

    def release_lock(self, epic_id: str, holder_id: str) -> None:
        conn = self._get_conn()
        conn.execute(
            "DELETE FROM epic_locks WHERE epic_id = %s AND holder_id = %s",
            [epic_id, holder_id],
        )

    # ------------------------------------------------------------------
    # T11 — Control Plane
    # ------------------------------------------------------------------

    def put_control_message(self, msg: ControlMessageInput) -> ControlMessage:
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
        self, msg_id: str, result: dict[str, Any]
    ) -> None:
        conn = self._get_conn()
        conn.execute(
            "UPDATE control_messages SET processed_at = now(), result = %s WHERE id = %s",
            [_jb(result), msg_id],
        )

    # ------------------------------------------------------------------
    # T11 — Progress Events
    # ------------------------------------------------------------------

    def append_progress_event(self, event: ProgressEventInput) -> ProgressEvent:
        self._require_actor()
        conn = self._get_conn()
        row = conn.execute(
            """
            INSERT INTO progress_events (id, epic_id, plan_id, sprint_id, kind, summary, details)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            [
                str(uuid.uuid4()), event.epic_id, event.plan_id, event.sprint_id,
                event.kind, event.summary, _jb(dict(event.details)),
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

    def update_automation_actor(self, actor_id: str, **changes: Any) -> AutomationActor:
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


__all__ = ["DBStore"]
