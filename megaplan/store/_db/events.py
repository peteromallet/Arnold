"""Event mixin for DBStore."""

from __future__ import annotations

import uuid
from typing import Any, Sequence

from megaplan.schemas import EpicEvent
from megaplan.store.base import StoredEvent

from .common import _jb

class DBEventMixin:
    def events_for_plan(self, plan_id: str):
        conn = self._get_conn()
        rows = conn.execute(
            """
            SELECT id, event_type, prior_state, pre_state, post_state, occurred_at
            FROM epic_events
            WHERE epic_id = %s
            ORDER BY occurred_at ASC, id ASC
            """,
            [plan_id],
        ).fetchall()
        events: list[StoredEvent] = []
        for row in rows:
            payload = row["post_state"] or row["pre_state"] or row["prior_state"] or {}
            phase = None
            kind = str(row["event_type"] or "epic_event")
            if isinstance(payload, dict):
                envelope = payload.get("event")
                if isinstance(envelope, dict):
                    events.append(_stored_from_envelope(envelope, row["occurred_at"], row["id"], "record_epic_event"))
                    continue
                else:
                    raw_phase = payload.get("phase")
                    phase = str(raw_phase) if raw_phase is not None else None
            events.append(
                StoredEvent(
                    kind=kind,
                    phase=phase,
                    payload=payload if isinstance(payload, dict) else {},
                    occurred_at=row["occurred_at"],
                    id=row["id"],
                    source="record_epic_event",
                )
            )

        telemetry_rows = conn.execute(
            """
            SELECT id, event_type, details, occurred_at
            FROM system_logs
            WHERE event_type LIKE 'telemetry.%'
              AND (
                epic_id = %s
                OR details->>'scope' = %s
                OR details->'payload'->>'scope' = %s
              )
            ORDER BY occurred_at ASC, id ASC
            """,
            [plan_id, plan_id, plan_id],
        ).fetchall()
        for row in telemetry_rows:
            details = row["details"] or {}
            payload = details.get("payload") if isinstance(details, dict) else {}
            if isinstance(payload, dict) and isinstance(payload.get("event"), dict):
                events.append(
                    _stored_from_envelope(
                        payload["event"],
                        row["occurred_at"],
                        row["id"],
                        "append_telemetry_event",
                    )
                )
                continue
            payload = dict(payload) if isinstance(payload, dict) else {}
            raw_phase = details.get("phase") if isinstance(details, dict) else None
            if raw_phase is None:
                raw_phase = payload.pop("phase", None)
            kind = str(details.get("kind") or str(row["event_type"]).removeprefix("telemetry."))
            events.append(
                StoredEvent(
                    kind=kind,
                    phase=raw_phase if isinstance(raw_phase, str) else None,
                    payload=payload,
                    occurred_at=row["occurred_at"],
                    id=row["id"],
                    run_id=details.get("run_id") if isinstance(details.get("run_id"), str) else None,
                    source="append_telemetry_event",
                )
            )

        system_rows = conn.execute(
            """
            SELECT id, event_type, details, occurred_at
            FROM system_logs
            WHERE epic_id = %s
              AND details ? 'event'
            ORDER BY occurred_at ASC, id ASC
            """,
            [plan_id],
        ).fetchall()
        for row in system_rows:
            details = row["details"] or {}
            envelope = details.get("event") if isinstance(details, dict) else None
            if isinstance(envelope, dict):
                events.append(
                    _stored_from_envelope(
                        envelope,
                        row["occurred_at"],
                        row["id"],
                        "log_system_event",
                    )
                )
        events.sort(key=_stored_event_sort_key)
        return iter(events)

    def append_telemetry_event(
        self,
        kind: str,
        payload: dict[str, Any],
        *,
        scope: str | None = None,
    ) -> dict[str, Any]:
        event = {"kind": kind, "payload": dict(payload), "scope": scope}
        log = self.log_system_event(
            level="debug",
            category="system",
            event_type=f"telemetry.{kind}",
            message=f"telemetry event {kind}",
            details=event,
        )
        event["id"] = log.id
        event["occurred_at"] = log.occurred_at.isoformat()
        return event

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


def _stored_from_envelope(
    envelope: dict[str, Any],
    occurred_at: Any,
    event_id: str | None,
    source: str,
) -> StoredEvent:
    raw_phase = envelope.get("phase")
    raw_payload = envelope.get("payload")
    return StoredEvent(
        kind=str(envelope.get("kind") or source),
        phase=raw_phase if isinstance(raw_phase, str) else None,
        payload=raw_payload if isinstance(raw_payload, dict) else {},
        occurred_at=envelope.get("ts_utc") or occurred_at,
        id=event_id,
        seq=envelope.get("seq") if isinstance(envelope.get("seq"), int) else None,
        run_id=envelope.get("run_id") if isinstance(envelope.get("run_id"), str) else None,
        source=str(envelope.get("store_method") or source),
    )


def _stored_event_sort_key(event: StoredEvent) -> tuple[str, int, str, str]:
    seq = event.seq if event.seq is not None else 10**12
    return (str(event.occurred_at or ""), seq, event.source or "", event.id or "")
