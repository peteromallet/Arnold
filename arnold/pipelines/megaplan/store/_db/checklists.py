"""Checklist mixin for DBStore."""

from __future__ import annotations

import uuid
from typing import Any, Sequence

from arnold.pipelines.megaplan.schemas import ChecklistItem
from arnold.pipelines.megaplan.store.base import ChecklistItemInput

class DBChecklistMixin:
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
        items = [
            ChecklistItemInput.model_validate(item.model_dump() if isinstance(item, ChecklistItemInput) else item)
            for item in items
        ]
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
        ChecklistItem.model_validate({**dict(current), **changes})
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
        items = [
            ChecklistItemInput.model_validate(item.model_dump() if isinstance(item, ChecklistItemInput) else item)
            for item in items
        ]
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

__all__ = ["DBChecklistMixin"]
