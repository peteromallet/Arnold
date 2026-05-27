"""Sprint mixin for DBStore."""

from __future__ import annotations

import uuid
from collections import OrderedDict
from typing import Any, Sequence

from megaplan.schemas import Sprint, SprintItem
from megaplan.store.base import RevisionConflict, SprintItemInput, SprintWithItems

class DBSprintMixin:
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
        items = [
            SprintItemInput.model_validate(item.model_dump() if isinstance(item, SprintItemInput) else item)
            for item in items
        ]
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

__all__ = ["DBSprintMixin"]
