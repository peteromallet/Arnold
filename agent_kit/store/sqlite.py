"""SQLite Store adapter for invocation-mode Arnold runs."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
import sqlite3
from typing import Any, Iterator, Sequence
from uuid import uuid4


JSONDict = dict[str, Any]
_MIGRATIONS_DIR = Path(__file__).parent / "migrations" / "sqlite"

_JSON_COLUMNS = {
    "arguments",
    "details",
    "error_details",
    "in_burst_with",
    "prompt_snapshot",
    "provider_response_summary",
    "request_body",
    "request_summary",
    "result",
    "state_at_turn",
    "transcription_metadata",
    "triggered_by_message_ids",
    "warnings_issued",
}


class SQLiteStore:
    def __init__(self, database: str | Path | sqlite3.Connection):
        if isinstance(database, sqlite3.Connection):
            self._conn = database
            self._owns_connection = False
        else:
            self._conn = sqlite3.connect(str(database))
            self._owns_connection = True
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._transaction_depth = 0
        self.apply_migrations()

    def close(self) -> None:
        if self._owns_connection:
            self._conn.close()

    def apply_migrations(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                name TEXT PRIMARY KEY,
                applied_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
            )
            """
        )
        for migration in sorted(_MIGRATIONS_DIR.glob("*.sql")):
            already_applied = self._conn.execute(
                "SELECT 1 FROM schema_migrations WHERE name = ?",
                (migration.name,),
            ).fetchone()
            if already_applied:
                continue
            self._conn.executescript(migration.read_text())
            self._conn.execute(
                "INSERT INTO schema_migrations (name) VALUES (?)",
                (migration.name,),
            )
        self._conn.commit()

    @contextmanager
    def transaction(self) -> Iterator[None]:
        if self._transaction_depth == 0:
            self._conn.execute("BEGIN")
            self._transaction_depth += 1
            try:
                yield
            except Exception:
                self._conn.rollback()
                raise
            else:
                self._conn.commit()
            finally:
                self._transaction_depth -= 1
            return

        savepoint = f"sp_{self._transaction_depth}"
        self._conn.execute(f"SAVEPOINT {savepoint}")
        self._transaction_depth += 1
        try:
            yield
        except Exception:
            self._conn.execute(f"ROLLBACK TO {savepoint}")
            self._conn.execute(f"RELEASE {savepoint}")
            raise
        else:
            self._conn.execute(f"RELEASE {savepoint}")
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
            """
            INSERT INTO messages (
                id, epic_id, direction, content, discord_message_id,
                has_code_attachment, has_image_attachment, in_burst_with,
                was_voice_message, audio_storage_url, transcription_metadata,
                bot_turn_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                message_id,
                epic_id,
                direction,
                content,
                discord_message_id,
                int(has_code_attachment),
                int(has_image_attachment),
                _json_dumps(list(in_burst_with)) if in_burst_with else None,
                int(was_voice_message),
                audio_storage_url,
                _json_dumps(transcription_metadata) if transcription_metadata else None,
                bot_turn_id,
            ),
        )
        self._commit_if_needed()
        return self.load_message(message_id) or {}

    def load_message(self, message_id: str) -> JSONDict | None:
        row = self._conn.execute(
            "SELECT * FROM messages WHERE id = ?",
            (message_id,),
        ).fetchone()
        return _decode_row(row)

    def load_messages(self, message_ids: Sequence[str]) -> list[JSONDict]:
        if not message_ids:
            return []
        placeholders = ", ".join("?" for _ in message_ids)
        rows = self._conn.execute(
            f"SELECT * FROM messages WHERE id IN ({placeholders})",
            list(message_ids),
        ).fetchall()
        by_id = {
            row["id"]: _decode_row(row)
            for row in rows
        }
        return [
            by_id[message_id]
            for message_id in message_ids
            if by_id.get(message_id) is not None
        ]

    def update_message(self, message_id: str, **changes: Any) -> JSONDict:
        if not changes:
            return self.load_message(message_id) or {}
        normalized = {
            key: _to_sql_value(key, value)
            for key, value in changes.items()
        }
        assignments = ", ".join(f"{key} = ?" for key in normalized)
        values = list(normalized.values()) + [message_id]
        self._conn.execute(
            f"UPDATE messages SET {assignments} WHERE id = ?",
            values,
        )
        self._commit_if_needed()
        return self.load_message(message_id) or {}

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
            """
            INSERT INTO bot_turns (
                id, epic_id, triggered_by_message_ids, prompt_snapshot,
                prompt_version, status, state_at_turn, model_version
            )
            VALUES (?, ?, ?, ?, ?, 'in_progress', ?, ?)
            """,
            (
                turn_id,
                epic_id,
                _json_dumps(list(triggered_by_message_ids)),
                _json_dumps(prompt_snapshot) if prompt_snapshot is not None else None,
                prompt_version,
                _json_dumps(state_at_turn) if state_at_turn is not None else None,
                model_version,
            ),
        )
        self._commit_if_needed()
        return self._load_turn(turn_id) or {}

    def update_turn(self, turn_id: str, **changes: Any) -> JSONDict:
        if not changes:
            return self._load_turn(turn_id) or {}
        normalized = {
            key: _to_sql_value(key, value)
            for key, value in changes.items()
        }
        if (
            normalized.get("status") in {"completed", "failed", "abandoned"}
            and "completed_at" not in normalized
        ):
            normalized["completed_at"] = _now()
        assignments = ", ".join(f"{key} = ?" for key in normalized)
        values = list(normalized.values()) + [turn_id]
        self._conn.execute(
            f"UPDATE bot_turns SET {assignments} WHERE id = ?",
            values,
        )
        self._commit_if_needed()
        return self._load_turn(turn_id) or {}

    def find_abandoned_turns(self, older_than_seconds: int) -> list[JSONDict]:
        cutoff = _format_datetime(
            datetime.now(UTC) - timedelta(seconds=older_than_seconds)
        )
        return [
            _decode_row(row) or {}
            for row in self._conn.execute(
                """
                SELECT * FROM bot_turns
                WHERE status = 'in_progress' AND started_at <= ?
                ORDER BY started_at
                """,
                (cutoff,),
            ).fetchall()
        ]

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
            """
            INSERT INTO tool_calls (
                id, turn_id, tool_name, operation_kind, arguments, result,
                duration_ms
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                tool_call_id,
                turn_id,
                tool_name,
                operation_kind,
                _json_dumps(arguments),
                _json_dumps(result),
                duration_ms,
            ),
        )
        self._commit_if_needed()
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
            """
            INSERT INTO system_logs (
                id, level, category, event_type, message, details, turn_id,
                epic_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                log_id,
                level,
                category,
                event_type,
                message,
                _json_dumps(details or {}),
                turn_id,
                epic_id,
            ),
        )
        self._commit_if_needed()
        return self._load_system_log(log_id) or {}

    def acquire_epic_lock(
        self,
        epic_id: str,
        *,
        holder_id: str,
        timeout_seconds: int = 60,
    ) -> bool:
        now = _now()
        expires_at = _format_datetime(
            datetime.now(UTC) + timedelta(seconds=timeout_seconds)
        )
        with self.transaction():
            self._conn.execute(
                "DELETE FROM epic_locks WHERE epic_id = ? AND expires_at <= ?",
                (epic_id, now),
            )
            try:
                self._conn.execute(
                    """
                    INSERT INTO epic_locks (
                        epic_id, holder_id, acquired_at, expires_at
                    )
                    VALUES (?, ?, ?, ?)
                    """,
                    (epic_id, holder_id, now, expires_at),
                )
            except sqlite3.IntegrityError:
                row = self._conn.execute(
                    """
                    SELECT holder_id FROM epic_locks
                    WHERE epic_id = ? AND holder_id = ?
                    """,
                    (epic_id, holder_id),
                ).fetchone()
                if row is None:
                    return False
                self._conn.execute(
                    """
                    UPDATE epic_locks
                    SET acquired_at = ?, expires_at = ?
                    WHERE epic_id = ? AND holder_id = ?
                    """,
                    (now, expires_at, epic_id, holder_id),
                )
        return True

    def release_epic_lock(self, epic_id: str, *, holder_id: str) -> None:
        self._conn.execute(
            "DELETE FROM epic_locks WHERE epic_id = ? AND holder_id = ?",
            (epic_id, holder_id),
        )
        self._commit_if_needed()

    def load_hot_context(self, epic_id: str) -> JSONDict:
        epic = _decode_row(
            self._conn.execute(
                "SELECT * FROM epics WHERE id = ?",
                (epic_id,),
            ).fetchone()
        )
        messages = [
            _decode_row(row)
            for row in self._conn.execute(
                """
                SELECT * FROM messages
                WHERE epic_id = ?
                ORDER BY sent_at DESC
                LIMIT 10
                """,
                (epic_id,),
            ).fetchall()
        ]
        tool_calls = [
            _decode_row(row)
            for row in self._conn.execute(
                """
                SELECT tool_calls.*
                FROM tool_calls
                JOIN bot_turns ON bot_turns.id = tool_calls.turn_id
                WHERE bot_turns.epic_id = ?
                ORDER BY tool_calls.called_at DESC
                LIMIT 10
                """,
                (epic_id,),
            ).fetchall()
        ]
        return {
            "epic": epic,
            "recent_messages": list(reversed(messages)),
            "recent_tool_calls": list(reversed(tool_calls)),
        }

    def find_unprocessed_messages(
        self,
        epic_id: str,
        started_at: str,
        exclude_ids: Sequence[str],
    ) -> list[JSONDict]:
        params: list[Any] = [epic_id, started_at]
        exclusion_sql = ""
        if exclude_ids:
            placeholders = ", ".join("?" for _ in exclude_ids)
            exclusion_sql = f" AND id NOT IN ({placeholders})"
            params.extend(exclude_ids)
        return [
            _decode_row(row) or {}
            for row in self._conn.execute(
                f"""
                SELECT * FROM messages
                WHERE epic_id = ?
                  AND direction = 'inbound'
                  AND sent_at >= ?
                  {exclusion_sql}
                ORDER BY sent_at, id
                """,
                params,
            ).fetchall()
        ]

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
            """
            INSERT INTO external_requests (
                id, idempotency_key, provider, endpoint, tool_call_id,
                turn_id, request_summary, request_body, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending')
            """,
            (
                request_id,
                idempotency_key,
                provider,
                endpoint,
                tool_call_id,
                turn_id,
                _json_dumps(request_summary),
                _json_dumps(request_body) if request_body is not None else None,
            ),
        )
        self._commit_if_needed()
        return self._load_external_request(request_id) or {}

    def find_pending_external_requests(
        self,
        older_than_seconds: int,
    ) -> list[JSONDict]:
        cutoff = _format_datetime(
            datetime.now(UTC) - timedelta(seconds=older_than_seconds)
        )
        return [
            _decode_row(row) or {}
            for row in self._conn.execute(
                """
                SELECT * FROM external_requests
                WHERE status IN ('pending', 'sent') AND last_attempted_at <= ?
                ORDER BY last_attempted_at, id
                """,
                (cutoff,),
            ).fetchall()
        ]

    def mark_confirmed(
        self,
        request_id: str,
        *,
        provider_request_id: str | None = None,
        provider_response_summary: JSONDict | None = None,
    ) -> JSONDict:
        self._conn.execute(
            """
            UPDATE external_requests
            SET status = 'confirmed',
                provider_request_id = ?,
                provider_response_summary = ?,
                completed_at = ?,
                error_details = NULL
            WHERE id = ?
            """,
            (
                provider_request_id,
                _json_dumps(provider_response_summary)
                if provider_response_summary is not None
                else None,
                _now(),
                request_id,
            ),
        )
        self._commit_if_needed()
        return self._load_external_request(request_id) or {}

    def mark_failed(
        self,
        request_id: str,
        *,
        error_details: JSONDict,
    ) -> JSONDict:
        self._conn.execute(
            """
            UPDATE external_requests
            SET status = 'failed',
                error_details = ?,
                completed_at = ?
            WHERE id = ?
            """,
            (_json_dumps(error_details), _now(), request_id),
        )
        self._commit_if_needed()
        return self._load_external_request(request_id) or {}

    def mark_orphaned(
        self,
        request_id: str,
        *,
        error_details: JSONDict,
    ) -> JSONDict:
        self._conn.execute(
            """
            UPDATE external_requests
            SET status = 'orphaned',
                error_details = ?,
                completed_at = ?
            WHERE id = ?
            """,
            (_json_dumps(error_details), _now(), request_id),
        )
        self._commit_if_needed()
        return self._load_external_request(request_id) or {}

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
        if reference_key is None:
            reference_key = self._next_image_reference_key(epic_id, source)
        self._conn.execute(
            """
            INSERT INTO images (
                id, epic_id, source, prompt, storage_url, quality, size,
                reference_key, description, caption, in_body, active,
                discord_attachment_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                image_id,
                epic_id,
                source,
                prompt,
                storage_url,
                quality,
                size,
                reference_key,
                description,
                caption,
                int(in_body),
                int(active),
                discord_attachment_id,
            ),
        )
        self._commit_if_needed()
        return self.load_image(image_id) or {}

    def load_image(self, image_id: str) -> JSONDict | None:
        return _decode_row(
            self._conn.execute(
                "SELECT * FROM images WHERE id = ?",
                (image_id,),
            ).fetchone()
        )

    def list_images(
        self,
        *,
        epic_id: str,
        source: str | None = None,
        active: bool | None = True,
    ) -> list[JSONDict]:
        clauses = ["epic_id = ?"]
        params: list[Any] = [epic_id]
        if source is not None:
            clauses.append("source = ?")
            params.append(source)
        if active is not None:
            clauses.append("active = ?")
            params.append(int(active))
        where_sql = " AND ".join(clauses)
        return [
            _decode_row(row) or {}
            for row in self._conn.execute(
                f"""
                SELECT * FROM images
                WHERE {where_sql}
                ORDER BY created_at DESC, id DESC
                """,
                params,
            ).fetchall()
        ]

    def update_image(self, image_id: str, **changes: Any) -> JSONDict:
        if not changes:
            return self.load_image(image_id) or {}
        normalized = {
            key: _to_sql_value(key, value)
            for key, value in changes.items()
        }
        assignments = ", ".join(f"{key} = ?" for key in normalized)
        values = list(normalized.values()) + [image_id]
        self._conn.execute(
            f"UPDATE images SET {assignments} WHERE id = ?",
            values,
        )
        self._commit_if_needed()
        return self.load_image(image_id) or {}

    def _next_invocation_message_id(self, turn_id: str) -> str:
        count = self._conn.execute(
            """
            SELECT COUNT(*) FROM messages
            WHERE bot_turn_id = ? AND direction = 'outbound'
            """,
            (turn_id,),
        ).fetchone()[0]
        return f"inv_{turn_id}_{count + 1}"

    def _next_image_reference_key(self, epic_id: str, source: str) -> str:
        prefix = (
            "img_user_upload"
            if source == "user_uploaded"
            else "img_agent"
        )
        rows = self._conn.execute(
            """
            SELECT reference_key FROM images
            WHERE epic_id = ? AND reference_key LIKE ? AND active = 1
            """,
            (epic_id, f"{prefix}_%"),
        ).fetchall()
        used = {row["reference_key"] for row in rows}
        index = 1
        while f"{prefix}_{index}" in used:
            index += 1
        return f"{prefix}_{index}"

    def _load_turn(self, turn_id: str) -> JSONDict | None:
        return _decode_row(
            self._conn.execute(
                "SELECT * FROM bot_turns WHERE id = ?",
                (turn_id,),
            ).fetchone()
        )

    def _load_tool_call(self, tool_call_id: str) -> JSONDict | None:
        return _decode_row(
            self._conn.execute(
                "SELECT * FROM tool_calls WHERE id = ?",
                (tool_call_id,),
            ).fetchone()
        )

    def _load_system_log(self, log_id: str) -> JSONDict | None:
        return _decode_row(
            self._conn.execute(
                "SELECT * FROM system_logs WHERE id = ?",
                (log_id,),
            ).fetchone()
        )

    def _load_external_request(self, request_id: str) -> JSONDict | None:
        return _decode_row(
            self._conn.execute(
                "SELECT * FROM external_requests WHERE id = ?",
                (request_id,),
            ).fetchone()
        )

    def _commit_if_needed(self) -> None:
        if self._transaction_depth == 0:
            self._conn.commit()


def _decode_row(row: sqlite3.Row | None) -> JSONDict | None:
    if row is None:
        return None
    decoded = dict(row)
    for key in list(decoded):
        if key in _JSON_COLUMNS and decoded[key] is not None:
            decoded[key] = json.loads(decoded[key])
    return decoded


def _to_sql_value(key: str, value: Any) -> Any:
    if key in _JSON_COLUMNS and value is not None:
        return _json_dumps(value)
    if isinstance(value, bool):
        return int(value)
    return value


def _json_dumps(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def _now() -> str:
    return _format_datetime(datetime.now(UTC))


def _format_datetime(value: datetime) -> str:
    return value.isoformat(timespec="milliseconds").replace("+00:00", "Z")
