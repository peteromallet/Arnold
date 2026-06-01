"""Event mixin for DBStore."""

from __future__ import annotations

import uuid
from typing import Any, Sequence

from megaplan.schemas import EpicEvent

from .common import _jb

class DBEventMixin:
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
        event = EpicEvent(**row)

        # Auto-address hook: flip tickets linked with resolves_on_complete=true
        if (
            event_type == "state_change"
            and post_state
            and post_state.get("state") == "done"
        ):
            from megaplan.tickets import address_resolved_by_epic

            cb = self.load_codebase_by_associated_epic(epic_id)
            repo_root = cb.repo_workspace if cb else None
            address_resolved_by_epic(epic_id, store=self, repo_root=repo_root)

        return event

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

__all__ = ["DBEventMixin"]
