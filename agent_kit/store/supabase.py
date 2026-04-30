"""Supabase/Postgres Store adapter for resident mode."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
import os
from typing import Any, Iterator, Sequence
from uuid import uuid4
JSONDict = dict[str, Any]

_JSON_COLUMNS = {"arguments", "details", "error_details", "in_burst_with", "prompt_snapshot", "provider_response_summary", "request_body", "request_summary", "result", "state_at_turn", "transcription_metadata", "triggered_by_message_ids", "warnings_issued"}


class SupabaseStore:
    def __init__(self, dsn: str | None = None, *, connection: Any = None) -> None:
        if connection is None:
            dsn = dsn or os.environ["SUPABASE_DB_URL"]
            self._conn = _connect(dsn)
            self._owns_connection = True
        else:
            self._conn = connection
            self._owns_connection = False
        self._transaction_depth = 0

    @classmethod
    def from_env(cls) -> "SupabaseStore":
        return cls(os.environ["SUPABASE_DB_URL"])

    def close(self) -> None:
        if self._owns_connection:
            self._conn.close()

    @contextmanager
    def transaction(self) -> Iterator[None]:
        self._transaction_depth += 1
        try:
            with self._conn.transaction():
                yield
        finally:
            self._transaction_depth -= 1

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
        transcription_metadata: JSONDict | None = None,
        synthesize_outbound_id: bool = True,
    ) -> JSONDict:
        message_id = _new_id("msg")
        if (
            synthesize_outbound_id
            and direction == "outbound"
            and discord_message_id is None
            and bot_turn_id
        ):
            discord_message_id = self._next_invocation_message_id(bot_turn_id)
        self._conn.execute(
            "INSERT INTO messages (id, epic_id, direction, content, discord_message_id, has_code_attachment, has_image_attachment, in_burst_with, was_voice_message, audio_storage_url, transcription_metadata, bot_turn_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                message_id,
                epic_id,
                direction,
                content,
                discord_message_id,
                has_code_attachment,
                has_image_attachment,
                _json(list(in_burst_with)) if in_burst_with else None,
                was_voice_message,
                audio_storage_url,
                _json(transcription_metadata) if transcription_metadata else None,
                bot_turn_id,
            ),
        )
        return self.load_message(message_id) or {}

    def load_message(self, message_id: str) -> JSONDict | None:
        return _normalize(self._conn.execute("SELECT * FROM messages WHERE id = %s", (message_id,)).fetchone())

    def load_messages(self, message_ids: Sequence[str]) -> list[JSONDict]:
        if not message_ids:
            return []
        rows = self._conn.execute(
            "SELECT * FROM messages WHERE id = ANY(%s)",
            (list(message_ids),),
        ).fetchall()
        by_id = {row["id"]: _normalize(row) for row in rows}
        return [by_id[item] for item in message_ids if item in by_id]

    def update_message(self, message_id: str, **changes: Any) -> JSONDict:
        return self._update("messages", "id", message_id, changes, _MESSAGE_COLUMNS, self.load_message)

    def create_turn(
        self,
        *,
        epic_id: str,
        triggered_by_message_ids: Sequence[str],
        prompt_snapshot: JSONDict | None = None,
        prompt_version: str | None = None,
        state_at_turn: JSONDict | None = None,
        model_version: str | None = None,
    ) -> JSONDict:
        turn_id = _new_id("turn")
        self._conn.execute(
            "INSERT INTO bot_turns (id, epic_id, triggered_by_message_ids, prompt_snapshot, prompt_version, status, state_at_turn, model_version) VALUES (%s, %s, %s, %s, %s, 'in_progress', %s, %s)",
            (
                turn_id,
                epic_id,
                _json(list(triggered_by_message_ids)),
                _json(prompt_snapshot) if prompt_snapshot is not None else None,
                prompt_version,
                _json(state_at_turn) if state_at_turn is not None else None,
                model_version,
            ),
        )
        return self._load_turn(turn_id) or {}

    def update_turn(self, turn_id: str, **changes: Any) -> JSONDict:
        if changes.get("status") in {"completed", "failed", "abandoned"} and "completed_at" not in changes:
            changes = {**changes, "completed_at": datetime.now(UTC)}
        return self._update("bot_turns", "id", turn_id, changes, _TURN_COLUMNS, self._load_turn)

    def find_abandoned_turns(self, older_than_seconds: int) -> list[JSONDict]:
        return _normalize_rows(
            self._conn.execute(
                "SELECT * FROM bot_turns WHERE status = 'in_progress' AND started_at <= now() - (%s * interval '1 second') ORDER BY started_at",
                (older_than_seconds,),
            ).fetchall()
        )

    def record_tool_call(
        self,
        *,
        turn_id: str,
        tool_name: str,
        operation_kind: str,
        arguments: JSONDict,
        result: JSONDict,
        duration_ms: int,
    ) -> JSONDict:
        tool_call_id = _new_id("tool")
        self._conn.execute(
            "INSERT INTO tool_calls (id, turn_id, tool_name, operation_kind, arguments, result, duration_ms) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (tool_call_id, turn_id, tool_name, operation_kind, _json(arguments), _json(result), duration_ms),
        )
        return self._load_tool_call(tool_call_id) or {}

    def log_system_event(
        self,
        *,
        level: str,
        category: str,
        event_type: str,
        message: str,
        details: JSONDict | None = None,
        turn_id: str | None = None,
        epic_id: str | None = None,
    ) -> JSONDict:
        log_id = _new_id("log")
        self._conn.execute(
            "INSERT INTO system_logs (id, level, category, event_type, message, details, turn_id, epic_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (log_id, level, category, event_type, message, _json(details or {}), turn_id, epic_id),
        )
        return self._load_system_log(log_id) or {}

    def acquire_epic_lock(self, epic_id: str, *, holder_id: str, timeout_seconds: int = 60) -> bool:
        row = self._conn.execute(
            "INSERT INTO epic_locks (epic_id, holder_id, acquired_at, expires_at) VALUES (%s, %s, now(), now() + (%s * interval '1 second')) ON CONFLICT (epic_id) DO UPDATE SET holder_id = EXCLUDED.holder_id, acquired_at = now(), expires_at = EXCLUDED.expires_at WHERE epic_locks.expires_at <= now() OR epic_locks.holder_id = EXCLUDED.holder_id RETURNING holder_id",
            (epic_id, holder_id, timeout_seconds),
        ).fetchone()
        return bool(row and row["holder_id"] == holder_id)

    def release_epic_lock(self, epic_id: str, *, holder_id: str) -> None:
        self._conn.execute(
            "DELETE FROM epic_locks WHERE epic_id = %s AND holder_id = %s",
            (epic_id, holder_id),
        )

    def load_hot_context(self, epic_id: str) -> JSONDict:
        epic = _normalize(self._conn.execute("SELECT * FROM epics WHERE id = %s", (epic_id,)).fetchone())
        messages = _normalize_rows(
            self._conn.execute(
                "SELECT * FROM messages WHERE epic_id = %s ORDER BY sent_at DESC LIMIT 10",
                (epic_id,),
            ).fetchall()
        )
        tool_calls = _normalize_rows(
            self._conn.execute(
                "SELECT tool_calls.* FROM tool_calls JOIN bot_turns ON bot_turns.id = tool_calls.turn_id WHERE bot_turns.epic_id = %s ORDER BY tool_calls.called_at DESC LIMIT 10",
                (epic_id,),
            ).fetchall()
        )
        return {"epic": epic, "recent_messages": list(reversed(messages)), "recent_tool_calls": list(reversed(tool_calls))}

    def find_unprocessed_messages(self, epic_id: str, started_at: str, exclude_ids: Sequence[str]) -> list[JSONDict]:
        return _normalize_rows(
            self._conn.execute(
                "SELECT * FROM messages WHERE epic_id = %s AND direction = 'inbound' AND sent_at >= %s AND NOT (id = ANY(%s)) ORDER BY sent_at, id",
                (epic_id, started_at, list(exclude_ids)),
            ).fetchall()
        )

    def insert_pending(
        self,
        *,
        idempotency_key: str,
        provider: str,
        endpoint: str,
        request_summary: JSONDict,
        request_body: JSONDict | None = None,
        turn_id: str | None = None,
        tool_call_id: str | None = None,
    ) -> JSONDict:
        request_id = _new_id("ext")
        self._conn.execute(
            "INSERT INTO external_requests (id, idempotency_key, provider, endpoint, tool_call_id, turn_id, request_summary, request_body, status) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'pending')",
            (request_id, idempotency_key, provider, endpoint, tool_call_id, turn_id, _json(request_summary), _json(request_body) if request_body is not None else None),
        )
        return self._load_external_request(request_id) or {}

    def find_pending_external_requests(self, older_than_seconds: int) -> list[JSONDict]:
        return _normalize_rows(
            self._conn.execute(
                "SELECT * FROM external_requests WHERE status IN ('pending', 'sent') AND last_attempted_at <= now() - (%s * interval '1 second') ORDER BY last_attempted_at, id",
                (older_than_seconds,),
            ).fetchall()
        )

    def mark_confirmed(self, request_id: str, *, provider_request_id: str | None = None, provider_response_summary: JSONDict | None = None) -> JSONDict:
        return self._mark_request(request_id, "confirmed", provider_request_id, provider_response_summary, None)

    def mark_failed(self, request_id: str, *, error_details: JSONDict) -> JSONDict:
        return self._mark_request(request_id, "failed", None, None, error_details)

    def mark_orphaned(self, request_id: str, *, error_details: JSONDict) -> JSONDict:
        return self._mark_request(request_id, "orphaned", None, None, error_details)

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
    ) -> JSONDict:
        image_id = _new_id("img")
        reference_key = reference_key or self._next_image_reference_key(epic_id, source)
        self._conn.execute(
            "INSERT INTO images (id, epic_id, source, prompt, storage_url, quality, size, reference_key, description, caption, in_body, active, discord_attachment_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (image_id, epic_id, source, prompt, storage_url, quality, size, reference_key, description, caption, in_body, active, discord_attachment_id),
        )
        return self.load_image(image_id) or {}

    def load_image(self, image_id: str) -> JSONDict | None:
        return _normalize(self._conn.execute("SELECT * FROM images WHERE id = %s", (image_id,)).fetchone())

    def list_images(self, *, epic_id: str, source: str | None = None, active: bool | None = True) -> list[JSONDict]:
        clauses = ["epic_id = %s"]
        params: list[Any] = [epic_id]
        if source is not None:
            clauses.append("source = %s")
            params.append(source)
        if active is not None:
            clauses.append("active = %s")
            params.append(active)
        return _normalize_rows(
            self._conn.execute(
                f"SELECT * FROM images WHERE {' AND '.join(clauses)} ORDER BY created_at DESC, id DESC",
                params,
            ).fetchall()
        )

    def update_image(self, image_id: str, **changes: Any) -> JSONDict:
        return self._update("images", "id", image_id, changes, _IMAGE_COLUMNS, self.load_image)

    def _mark_request(
        self,
        request_id: str,
        status: str,
        provider_request_id: str | None,
        provider_response_summary: JSONDict | None,
        error_details: JSONDict | None,
    ) -> JSONDict:
        self._conn.execute(
            "UPDATE external_requests SET status = %s, provider_request_id = %s, provider_response_summary = %s, completed_at = now(), error_details = %s WHERE id = %s",
            (status, provider_request_id, _json(provider_response_summary) if provider_response_summary is not None else None, _json(error_details) if error_details is not None else None, request_id),
        )
        return self._load_external_request(request_id) or {}

    def _update(self, table: str, key_column: str, row_id: str, changes: dict[str, Any], allowed: set[str], loader) -> JSONDict:
        if not changes:
            return loader(row_id) or {}
        unknown = set(changes) - allowed
        if unknown:
            raise ValueError(f"unsupported {table} columns: {', '.join(sorted(unknown))}")
        assignments = ", ".join(f"{key} = %s" for key in changes)
        values = [_to_sql_value(key, value) for key, value in changes.items()]
        self._conn.execute(
            f"UPDATE {table} SET {assignments} WHERE {key_column} = %s",
            [*values, row_id],
        )
        return loader(row_id) or {}

    def _next_invocation_message_id(self, turn_id: str) -> str:
        row = self._conn.execute(
            "SELECT COUNT(*) AS count FROM messages WHERE bot_turn_id = %s AND direction = 'outbound'",
            (turn_id,),
        ).fetchone()
        return f"inv_{turn_id}_{int(row['count']) + 1}"

    def _next_image_reference_key(self, epic_id: str, source: str) -> str:
        prefix = "img_user_upload" if source == "user_uploaded" else "img_agent"
        rows = self._conn.execute(
            "SELECT reference_key FROM images WHERE epic_id = %s AND reference_key LIKE %s AND active = true",
            (epic_id, f"{prefix}_%"),
        ).fetchall()
        used = {row["reference_key"] for row in rows}
        index = 1
        while f"{prefix}_{index}" in used:
            index += 1
        return f"{prefix}_{index}"

    def _load_turn(self, turn_id: str) -> JSONDict | None:
        return _normalize(self._conn.execute("SELECT * FROM bot_turns WHERE id = %s", (turn_id,)).fetchone())

    def _load_tool_call(self, tool_call_id: str) -> JSONDict | None:
        return _normalize(self._conn.execute("SELECT * FROM tool_calls WHERE id = %s", (tool_call_id,)).fetchone())

    def _load_system_log(self, log_id: str) -> JSONDict | None:
        return _normalize(self._conn.execute("SELECT * FROM system_logs WHERE id = %s", (log_id,)).fetchone())

    def _load_external_request(self, request_id: str) -> JSONDict | None:
        return _normalize(self._conn.execute("SELECT * FROM external_requests WHERE id = %s", (request_id,)).fetchone())


_MESSAGE_COLUMNS = {"discord_message_id", "content", "audio_storage_url", "transcription_metadata", "has_image_attachment", "has_code_attachment", "in_burst_with", "was_voice_message", "bot_turn_id"}
_TURN_COLUMNS = {"triggered_by_message_ids", "prompt_snapshot", "prompt_version", "reasoning", "final_output_message_id", "status_message_id", "status", "state_at_turn", "plan_edited", "code_consulted", "image_generated", "second_opinion_requested", "message_sent", "warnings_issued", "current_activity", "completed_at", "model_version"}
_IMAGE_COLUMNS = {"prompt", "storage_url", "quality", "size", "reference_key", "description", "caption", "in_body", "active", "discord_attachment_id"}


def _connect(dsn: str) -> Any:
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError as exc:
        raise RuntimeError("psycopg is required for SupabaseStore") from exc
    conn = psycopg.connect(dsn, row_factory=dict_row)
    conn.autocommit = True
    return conn


def _json(value: Any) -> Any:
    from psycopg.types.json import Jsonb

    return Jsonb(value)


def _to_sql_value(key: str, value: Any) -> Any:
    if key in _JSON_COLUMNS and value is not None:
        return _json(value)
    return value


def _normalize(row: Any) -> JSONDict | None:
    if row is None:
        return None
    normalized = dict(row)
    for key, value in list(normalized.items()):
        if isinstance(value, datetime):
            normalized[key] = value.isoformat().replace("+00:00", "Z")
    return normalized


def _normalize_rows(rows: Sequence[Any]) -> list[JSONDict]:
    return [item for item in (_normalize(row) for row in rows) if item is not None]


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


__all__ = ["SupabaseStore"]
