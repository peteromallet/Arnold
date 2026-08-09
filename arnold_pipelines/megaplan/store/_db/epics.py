"""Epic and snapshot mixins for DBStore."""

from __future__ import annotations

import uuid
from typing import Any, Sequence

from arnold_pipelines.megaplan.schemas import Epic, EpicEvent, EpicSnapshot
from arnold_pipelines.megaplan.store.base import EpicSummary, RevisionConflict, StoreError, validate_epic_update_fields
from arnold_pipelines.megaplan.store.snapshot import canonical_json_dumps, canonical_sha256, capture_epic_snapshot

from .common import _COPY_JSONB_COLUMNS, _COPY_TABLE_COLUMNS, _jb, _parse_datetime

class DBEpicMixin:
    def create_epic(
        self,
        *,
        title: str,
        goal: str,
        body: str,
        state: str = "shaping",
        home_backend: str = "file",
        idempotency_key: str | None = None,
        epic_id: str | None = None,
    ) -> Epic:
        self._require_actor()
        conn = self._get_conn()
        if epic_id is None:
            epic_id = str(uuid.uuid4())
        row = conn.execute(
            """
            INSERT INTO epics (id, title, goal, body, state, home_backend, revision)
            VALUES (%s, %s, %s, %s, %s, %s, 1)
            RETURNING *
            """,
            [epic_id, title, goal, body, state, home_backend],
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
        validate_epic_update_fields(changes)
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

__all__ = ["DBEpicMixin"]
