"""SQLite Store adapter for invocation-mode Arnold runs."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
import sqlite3
from typing import Any, Iterator, Sequence
from uuid import uuid4

from agent_kit.code_redaction import redact_code_secrets


JSONDict = dict[str, Any]
_MIGRATIONS_DIR = Path(__file__).parent / "migrations" / "sqlite"
_ACTIVE_EPIC_STATES = ("shaping", "sprinting", "planned", "paused")

_JSON_COLUMNS = {
    "arguments",
    "context_snapshot",
    "details",
    "error_details",
    "in_burst_with",
    "prompt_snapshot",
    "prior_state",
    "provider_response_summary",
    "request_body",
    "request_summary",
    "result",
    "resulting_checklist_item_ids",
    "state_at_turn",
    "transcription_metadata",
    "triggered_by_message_ids",
    "warnings_issued",
    "focus_areas",
    "line_range",
    "metadata",
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
        return self._update("messages", "id", message_id, changes, _MESSAGE_COLUMNS, self.load_message)

    def latest_outbound_message(self, *, epic_id: str | None = None) -> JSONDict | None:
        clauses = ["direction = 'outbound'"]
        params: list[Any] = []
        if epic_id is not None:
            clauses.append("epic_id = ?")
            params.append(epic_id)
        return _decode_row(
            self._conn.execute(
                f"""
                SELECT * FROM messages
                WHERE {' AND '.join(clauses)}
                ORDER BY sent_at DESC, id DESC
                LIMIT 1
                """,
                params,
            ).fetchone()
        )

    def create_turn(
        self,
        *,
        epic_id: str | None,
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
        normalized = dict(changes)
        if (
            normalized.get("status") in {"completed", "failed", "abandoned"}
            and "completed_at" not in normalized
        ):
            normalized["completed_at"] = _now()
        return self._update("bot_turns", "id", turn_id, normalized, _TURN_COLUMNS, self._load_turn)

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
                _json_dumps(redact_code_secrets(arguments)),
                _json_dumps(redact_code_secrets(result)),
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
                _json_dumps(redact_code_secrets(details or {})),
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

    def load_hot_context(self, epic_id: str | None) -> JSONDict:
        epic = None
        messages: list[JSONDict | None] = []
        tool_calls: list[JSONDict | None] = []
        sprints: list[JSONDict] = []
        if epic_id is not None:
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
            sprints = self.list_sprints_with_items(epic_id)
            active_images = self.list_active_images(epic_id)
            recent_second_opinions = self.list_second_opinions(epic_id, limit=2)
        else:
            active_images = []
            recent_second_opinions = []
        queued_count = sum(1 for sprint in sprints if sprint.get("status") == "queued")
        pending_count = sum(1 for sprint in sprints if sprint.get("status") == "pending")
        return {
            "epic": epic,
            "recent_messages": list(reversed(messages)),
            "recent_tool_calls": list(reversed(tool_calls)),
            "active_feedback": self.list_feedback(epic_id=epic_id, active=True),
            "unresolved_observations": self.list_observations(resolved=False, limit=5),
            "sprints": sprints,
            "codebases": [
                _hot_context_codebase(row)
                for row in self.list_codebases(epic_id=epic_id, include_global=True)
            ],
            "recent_code_artifacts": [
                _hot_context_code_artifact(row)
                for row in self.list_code_artifacts(
                    epic_id=epic_id,
                    include_expired=False,
                    limit=5,
                )
            ],
            "active_images": [_hot_context_image(row) for row in active_images],
            "recent_second_opinions": [
                _hot_context_second_opinion(row)
                for row in recent_second_opinions
            ],
            "all_sprints_pending_no_queued": bool(sprints)
            and pending_count == len(sprints)
            and queued_count == 0,
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
        return self._update("images", "id", image_id, changes, _IMAGE_COLUMNS, self.load_image)

    def list_active_images(self, epic_id: str) -> list[JSONDict]:
        return self.list_images(epic_id=epic_id, active=True)

    def load_active_image_by_reference(
        self,
        epic_id: str,
        reference_key: str,
    ) -> JSONDict | None:
        return _decode_row(
            self._conn.execute(
                """
                SELECT * FROM images
                WHERE epic_id = ? AND reference_key = ? AND active = 1
                ORDER BY created_at DESC, id DESC
                LIMIT 1
                """,
                (epic_id, reference_key),
            ).fetchone()
        )

    def active_image_reference_exists(self, epic_id: str, reference_key: str) -> bool:
        row = self._conn.execute(
            """
            SELECT 1 FROM images
            WHERE epic_id = ? AND reference_key = ? AND active = 1
            LIMIT 1
            """,
            (epic_id, reference_key),
        ).fetchone()
        return row is not None

    def deactivate_active_image_reference(
        self,
        epic_id: str,
        reference_key: str,
    ) -> list[JSONDict]:
        rows = [
            _decode_row(row) or {}
            for row in self._conn.execute(
                """
                SELECT * FROM images
                WHERE epic_id = ? AND reference_key = ? AND active = 1
                ORDER BY created_at DESC, id DESC
                """,
                (epic_id, reference_key),
            ).fetchall()
        ]
        self._conn.execute(
            """
            UPDATE images
            SET active = 0
            WHERE epic_id = ? AND reference_key = ? AND active = 1
            """,
            (epic_id, reference_key),
        )
        self._commit_if_needed()
        return rows

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
    ) -> JSONDict:
        opinion_id = _new_id("opinion")
        self._conn.execute(
            """
            INSERT INTO second_opinions (
                id, epic_id, requested_by, focus_areas, raw_response, score,
                summary, verdict, resulting_checklist_item_ids, model_used
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                opinion_id,
                epic_id,
                requested_by,
                _json_dumps(list(focus_areas)),
                raw_response,
                int(score),
                summary,
                verdict,
                _json_dumps(list(resulting_checklist_item_ids or [])),
                model_used,
            ),
        )
        self._commit_if_needed()
        return self._load_second_opinion(opinion_id) or {}

    def list_second_opinions(
        self,
        epic_id: str,
        *,
        limit: int | None = None,
    ) -> list[JSONDict]:
        limit_sql = "LIMIT ?" if limit is not None else ""
        params: list[Any] = [epic_id]
        if limit is not None:
            params.append(int(limit))
        return [
            _decode_row(row) or {}
            for row in self._conn.execute(
                f"""
                SELECT * FROM second_opinions
                WHERE epic_id = ?
                ORDER BY requested_at DESC, id DESC
                {limit_sql}
                """,
                params,
            ).fetchall()
        ]

    def set_second_opinion_checklist_items(
        self,
        second_opinion_id: str,
        checklist_item_ids: Sequence[str],
    ) -> JSONDict:
        self._conn.execute(
            """
            UPDATE second_opinions
            SET resulting_checklist_item_ids = ?
            WHERE id = ?
            """,
            (_json_dumps(list(checklist_item_ids)), second_opinion_id),
        )
        self._commit_if_needed()
        return self._load_second_opinion(second_opinion_id) or {}

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
    ) -> JSONDict:
        normalized_owner, normalized_name = _normalize_repo_key(owner, name)
        codebase_id = codebase_id or _new_id("codebase")
        self._conn.execute(
            """
            INSERT INTO codebases (
                id, owner, name, default_branch, scope, group_name,
                associated_epic_id, added_via, verified_accessible_at, notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                codebase_id,
                normalized_owner,
                normalized_name,
                default_branch,
                scope,
                group_name,
                associated_epic_id,
                added_via,
                verified_accessible_at,
                notes,
            ),
        )
        self._commit_if_needed()
        return self.load_codebase(codebase_id) or {}

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
    ) -> JSONDict:
        existing = self.find_codebase(owner, name)
        if existing is None:
            return self.create_codebase(
                owner=owner,
                name=name,
                default_branch=default_branch,
                scope=scope,
                group_name=group_name,
                associated_epic_id=associated_epic_id,
                added_via=added_via,
                verified_accessible_at=verified_accessible_at,
                notes=notes,
            )
        changes = {
            "default_branch": default_branch,
            "scope": scope,
            "group_name": group_name,
            "associated_epic_id": associated_epic_id,
            "added_via": added_via,
            "notes": notes,
        }
        if verified_accessible_at is not None:
            changes["verified_accessible_at"] = verified_accessible_at
        return self.update_codebase(str(existing["id"]), **changes)

    def load_codebase(self, codebase_id: str) -> JSONDict | None:
        return _decode_row(
            self._conn.execute(
                "SELECT * FROM codebases WHERE id = ?",
                (codebase_id,),
            ).fetchone()
        )

    def find_codebase(self, owner: str, name: str) -> JSONDict | None:
        normalized_owner, normalized_name = _normalize_repo_key(owner, name)
        return _decode_row(
            self._conn.execute(
                """
                SELECT * FROM codebases
                WHERE owner = ? AND name = ?
                ORDER BY added_at DESC, id DESC
                LIMIT 1
                """,
                (normalized_owner, normalized_name),
            ).fetchone()
        )

    def list_codebases(
        self,
        *,
        scope: str | None = None,
        group_name: str | None = None,
        epic_id: str | None = None,
        include_global: bool = True,
    ) -> list[JSONDict]:
        clauses: list[str] = []
        params: list[Any] = []
        if scope is not None:
            clauses.append("scope = ?")
            params.append(scope)
        if group_name is not None:
            clauses.append("group_name = ?")
            params.append(group_name)
        if epic_id is not None:
            if include_global:
                clauses.append("(associated_epic_id = ? OR scope = 'global')")
            else:
                clauses.append("associated_epic_id = ?")
            params.append(epic_id)
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        return [
            _decode_row(row) or {}
            for row in self._conn.execute(
                f"""
                SELECT * FROM codebases
                {where_sql}
                ORDER BY group_name IS NULL, group_name, owner, name
                """,
                params,
            ).fetchall()
        ]

    def update_codebase(self, codebase_id: str, **changes: Any) -> JSONDict:
        normalized = dict(changes)
        if "owner" in normalized or "name" in normalized:
            current = self.load_codebase(codebase_id) or {}
            owner = str(normalized.get("owner", current.get("owner", "")))
            name = str(normalized.get("name", current.get("name", "")))
            normalized["owner"], normalized["name"] = _normalize_repo_key(owner, name)
        return self._update("codebases", "id", codebase_id, normalized, _CODEBASE_COLUMNS, self.load_codebase)

    def remove_codebase(self, codebase_id: str) -> None:
        self._conn.execute("DELETE FROM codebases WHERE id = ?", (codebase_id,))
        self._commit_if_needed()

    def touch_codebase_accessed(
        self,
        codebase_id: str,
        *,
        accessed_at: str | None = None,
    ) -> JSONDict:
        return self.update_codebase(codebase_id, last_accessed_at=accessed_at or _now())

    def mark_codebase_verified(
        self,
        codebase_id: str,
        *,
        verified_at: str | None = None,
        default_branch: str | None = None,
    ) -> JSONDict:
        changes: dict[str, Any] = {"verified_accessible_at": verified_at or _now()}
        if default_branch is not None:
            changes["default_branch"] = default_branch
        return self.update_codebase(codebase_id, **changes)

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
        metadata: JSONDict | None = None,
        expires_at: str | None = None,
        artifact_id: str | None = None,
    ) -> JSONDict:
        artifact_id = artifact_id or _new_id("artifact")
        safe_content = redact_code_secrets(content)
        safe_summary = redact_code_secrets(content_summary)
        safe_metadata = redact_code_secrets(metadata or {})
        self._conn.execute(
            """
            INSERT INTO code_artifacts (
                id, codebase_id, epic_id, kind, source, file_path, line_range,
                scope, content, content_summary, metadata, expires_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                artifact_id,
                codebase_id,
                epic_id,
                kind,
                source,
                file_path,
                _json_dumps(line_range) if line_range is not None else None,
                scope,
                safe_content,
                safe_summary,
                _json_dumps(safe_metadata),
                expires_at,
            ),
        )
        self._commit_if_needed()
        return self.load_code_artifact(artifact_id) or {}

    def load_code_artifact(self, artifact_id: str) -> JSONDict | None:
        return _decode_row(
            self._conn.execute(
                "SELECT * FROM code_artifacts WHERE id = ?",
                (artifact_id,),
            ).fetchone()
        )

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
    ) -> list[JSONDict]:
        clauses: list[str] = []
        params: list[Any] = []
        if codebase_id is not None:
            clauses.append("codebase_id = ?")
            params.append(codebase_id)
        if epic_id is not None:
            clauses.append("epic_id = ?")
            params.append(epic_id)
        if kind is not None:
            clauses.append("kind = ?")
            params.append(kind)
        if source is not None:
            clauses.append("source = ?")
            params.append(source)
        if file_path is not None:
            clauses.append("file_path = ?")
            params.append(file_path)
        if scope is not None:
            clauses.append("scope = ?")
            params.append(scope)
        if not include_expired:
            clauses.append("(expires_at IS NULL OR expires_at > ?)")
            params.append(_now())
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        limit_sql = "LIMIT ?" if limit is not None else ""
        if limit is not None:
            params.append(int(limit))
        return [
            _decode_row(row) or {}
            for row in self._conn.execute(
                f"""
                SELECT * FROM code_artifacts
                {where_sql}
                ORDER BY created_at DESC, id DESC
                {limit_sql}
                """,
                params,
            ).fetchall()
        ]

    def update_code_artifact(self, artifact_id: str, **changes: Any) -> JSONDict:
        return self._update(
            "code_artifacts",
            "id",
            artifact_id,
            changes,
            _CODE_ARTIFACT_COLUMNS,
            self.load_code_artifact,
        )

    def delete_code_artifact(self, artifact_id: str) -> None:
        self._conn.execute("DELETE FROM code_artifacts WHERE id = ?", (artifact_id,))
        self._commit_if_needed()

    def touch_code_artifact_used(
        self,
        artifact_id: str,
        *,
        used_at: str | None = None,
    ) -> JSONDict:
        return self.update_code_artifact(artifact_id, last_used_at=used_at or _now())

    def get_api_cache(
        self,
        cache_key: str,
        *,
        now: str | None = None,
        touch: bool = True,
    ) -> JSONDict | None:
        checked_at = now or _now()
        row = _decode_row(
            self._conn.execute(
                """
                SELECT * FROM code_artifacts
                WHERE kind = 'api_cache'
                  AND json_extract(metadata, '$.cache_key') = ?
                  AND (expires_at IS NULL OR expires_at > ?)
                ORDER BY created_at DESC, id DESC
                LIMIT 1
                """,
                (cache_key, checked_at),
            ).fetchone()
        )
        if row is not None and touch:
            return self.touch_code_artifact_used(str(row["id"]), used_at=checked_at)
        return row

    def upsert_api_cache(
        self,
        *,
        cache_key: str,
        content: str,
        content_summary: str | None = None,
        metadata: JSONDict | None = None,
        codebase_id: str | None = None,
        epic_id: str | None = None,
        file_path: str | None = None,
        scope: str | None = None,
        expires_at: str | None = None,
        ttl_seconds: int = 3600,
    ) -> JSONDict:
        cache_metadata = {**(metadata or {}), "cache_key": cache_key}
        expires_at = expires_at or _format_datetime(datetime.now(UTC) + timedelta(seconds=ttl_seconds))
        existing = _decode_row(
            self._conn.execute(
                """
                SELECT * FROM code_artifacts
                WHERE kind = 'api_cache'
                  AND json_extract(metadata, '$.cache_key') = ?
                ORDER BY created_at DESC, id DESC
                LIMIT 1
                """,
                (cache_key,),
            ).fetchone()
        )
        if existing is None:
            return self.create_code_artifact(
                kind="api_cache",
                source="codebase",
                content=content,
                codebase_id=codebase_id,
                epic_id=epic_id,
                file_path=file_path,
                scope=scope,
                content_summary=content_summary,
                metadata=cache_metadata,
                expires_at=expires_at,
            )
        return self.update_code_artifact(
            str(existing["id"]),
            codebase_id=codebase_id,
            epic_id=epic_id,
            file_path=file_path,
            scope=scope,
            content=content,
            content_summary=content_summary,
            metadata=cache_metadata,
            expires_at=expires_at,
            last_used_at=_now(),
        )

    def cleanup_expired_api_cache(self, *, now: str | None = None) -> int:
        checked_at = now or _now()
        cursor = self._conn.execute(
            """
            DELETE FROM code_artifacts
            WHERE kind = 'api_cache'
              AND expires_at IS NOT NULL
              AND expires_at < ?
            """,
            (checked_at,),
        )
        self._commit_if_needed()
        return int(cursor.rowcount or 0)

    def create_epic(
        self,
        *,
        title: str,
        goal: str,
        body: str,
        state: str = "shaping",
    ) -> JSONDict:
        epic_id = _new_id("epic")
        self._conn.execute(
            """
            INSERT INTO epics (id, title, goal, body, state)
            VALUES (?, ?, ?, ?, ?)
            """,
            (epic_id, title, goal, body, state),
        )
        self._commit_if_needed()
        return self.load_epic(epic_id) or {}

    def load_epic(self, epic_id: str) -> JSONDict | None:
        return _decode_row(
            self._conn.execute(
                "SELECT * FROM epics WHERE id = ?",
                (epic_id,),
            ).fetchone()
        )

    def list_epics(self, *, active_only: bool = True, limit: int = 20) -> list[JSONDict]:
        clauses: list[str] = []
        params: list[Any] = []
        if active_only:
            clauses.append(f"state IN ({', '.join('?' for _ in _ACTIVE_EPIC_STATES)})")
            params.extend(_ACTIVE_EPIC_STATES)
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(int(limit))
        return [
            _epic_result(row)
            for row in self._conn.execute(
                f"""
                SELECT epics.*,
                       substr(body, 1, 240) AS snippet
                FROM epics
                {where_sql}
                ORDER BY last_edited_at DESC, id DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
        ]

    def search_epics(
        self,
        *,
        query: str,
        active_only: bool = True,
        limit: int = 20,
    ) -> list[JSONDict]:
        like = f"%{query.lower()}%"
        clauses = [
            "(lower(title) LIKE ? OR lower(goal) LIKE ? OR lower(body) LIKE ?)"
        ]
        params: list[Any] = [like, like, like]
        if active_only:
            clauses.append(f"state IN ({', '.join('?' for _ in _ACTIVE_EPIC_STATES)})")
            params.extend(_ACTIVE_EPIC_STATES)
        params.append(int(limit))
        return [
            _epic_result(row)
            for row in self._conn.execute(
                f"""
                SELECT epics.*,
                       substr(body, 1, 240) AS snippet,
                       CASE
                         WHEN lower(title) LIKE ? THEN 3
                         WHEN lower(goal) LIKE ? THEN 2
                         ELSE 1
                       END AS rank
                FROM epics
                WHERE {' AND '.join(clauses)}
                ORDER BY rank DESC, last_edited_at DESC, id DESC
                LIMIT ?
                """,
                [like, like, *params],
            ).fetchall()
        ]

    def search_messages(
        self,
        *,
        query: str,
        epic_id: str | None = None,
        limit: int = 20,
    ) -> list[JSONDict]:
        clauses: list[str] = []
        params: list[Any] = [query]
        if epic_id is not None:
            clauses.append("messages.epic_id = ?")
            params.append(epic_id)
        where_sql = f"AND {' AND '.join(clauses)}" if clauses else ""
        params.append(int(limit))
        rows = self._conn.execute(
            f"""
            SELECT messages.*,
                   bm25(messages_fts) AS rank,
                   snippet(messages_fts, 1, '[', ']', '...', 12) AS snippet
            FROM messages_fts
            JOIN messages ON messages.id = messages_fts.message_id
            WHERE messages_fts MATCH ?
            {where_sql}
            ORDER BY rank, messages.sent_at DESC, messages.id DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
        return [_message_result(row) for row in rows]

    def update_epic(self, epic_id: str, **changes: Any) -> JSONDict:
        return self._update("epics", "id", epic_id, changes, _EPIC_COLUMNS, self.load_epic)

    def seed_checklist(self, epic_id: str, items: Sequence[str]) -> list[JSONDict]:
        rows = [
            {
                "content": content,
                "status": "open",
                "position": position,
                "source": "default_seed",
            }
            for position, content in enumerate(items, start=1)
        ]
        return self.add_checklist_items(epic_id, rows)

    def list_checklist_items(self, epic_id: str, *, status: str | None = None) -> list[JSONDict]:
        params: list[Any] = [epic_id]
        status_sql = ""
        if status is not None:
            status_sql = " AND status = ?"
            params.append(status)
        return [
            _decode_row(row) or {}
            for row in self._conn.execute(
                f"""
                SELECT * FROM checklist_items
                WHERE epic_id = ?{status_sql}
                ORDER BY position, id
                """,
                params,
            ).fetchall()
        ]

    def update_checklist_item(self, item_id: str, **changes: Any) -> JSONDict:
        return self._update(
            "checklist_items",
            "id",
            item_id,
            changes,
            _CHECKLIST_COLUMNS,
            self._load_checklist_item,
        )

    def add_checklist_items(self, epic_id: str, items: Sequence[JSONDict]) -> list[JSONDict]:
        added: list[JSONDict] = []
        max_position = self._conn.execute(
            "SELECT COALESCE(MAX(position), 0) FROM checklist_items WHERE epic_id = ?",
            (epic_id,),
        ).fetchone()[0]
        for offset, item in enumerate(items, start=1):
            item_id = str(item.get("id") or _new_id("check"))
            self._conn.execute(
                """
                INSERT INTO checklist_items (
                    id, epic_id, content, status, position, source,
                    skip_reason, superseded_by_item_id, created_at, completed_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, COALESCE(?, strftime('%Y-%m-%dT%H:%M:%fZ', 'now')), ?)
                """,
                (
                    item_id,
                    epic_id,
                    item["content"],
                    item.get("status", "open"),
                    item.get("position", max_position + offset),
                    item.get("source", "bot_inferred"),
                    item.get("skip_reason"),
                    item.get("superseded_by_item_id"),
                    item.get("created_at"),
                    item.get("completed_at"),
                ),
            )
            added.append(self._load_checklist_item(item_id) or {})
        self._commit_if_needed()
        return added

    def delete_checklist_items(self, item_ids: Sequence[str]) -> None:
        if not item_ids:
            return
        placeholders = ", ".join("?" for _ in item_ids)
        self._conn.execute(
            f"DELETE FROM checklist_items WHERE id IN ({placeholders})",
            list(item_ids),
        )
        self._commit_if_needed()

    def replace_checklist(self, epic_id: str, items: Sequence[JSONDict]) -> list[JSONDict]:
        with self.transaction():
            self._conn.execute("DELETE FROM checklist_items WHERE epic_id = ?", (epic_id,))
            return self.add_checklist_items(epic_id, items)

    def record_epic_event(
        self,
        *,
        epic_id: str,
        transaction_id: str,
        event_type: str,
        summary: str,
        prior_state: JSONDict | None,
        turn_id: str | None,
    ) -> JSONDict:
        event_id = _new_id("evt")
        self._conn.execute(
            """
            INSERT INTO epic_events (
                id, epic_id, transaction_id, event_type, summary, prior_state,
                turn_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                epic_id,
                transaction_id,
                event_type,
                summary,
                _json_dumps(prior_state) if prior_state is not None else None,
                turn_id,
            ),
        )
        self._commit_if_needed()
        return self._load_epic_event(event_id) or {}

    def list_epic_events(
        self,
        epic_id: str,
        *,
        since: str | None = None,
        until: str | None = None,
        kinds: Sequence[str] | None = None,
        limit: int | None = None,
    ) -> list[JSONDict]:
        clauses = ["epic_id = ?"]
        params: list[Any] = [epic_id]
        if since is not None:
            clauses.append("occurred_at >= ?")
            params.append(since)
        if until is not None:
            clauses.append("occurred_at <= ?")
            params.append(until)
        if kinds:
            placeholders = ", ".join("?" for _ in kinds)
            clauses.append(f"event_type IN ({placeholders})")
            params.extend(kinds)
        limit_sql = f" LIMIT {int(limit)}" if limit is not None else ""
        return [
            _decode_row(row) or {}
            for row in self._conn.execute(
                f"""
                SELECT * FROM epic_events
                WHERE {' AND '.join(clauses)}
                ORDER BY occurred_at, id
                {limit_sql}
                """,
                params,
            ).fetchall()
        ]

    def latest_transaction_id(self, epic_id: str) -> str | None:
        row = self._conn.execute(
            """
            SELECT transaction_id FROM epic_events
            WHERE epic_id = ?
            ORDER BY occurred_at DESC, id DESC
            LIMIT 1
            """,
            (epic_id,),
        ).fetchone()
        return str(row["transaction_id"]) if row is not None else None

    def events_by_transaction(self, transaction_id: str) -> list[JSONDict]:
        return [
            _decode_row(row) or {}
            for row in self._conn.execute(
                """
                SELECT * FROM epic_events
                WHERE transaction_id = ?
                ORDER BY occurred_at, id
                """,
                (transaction_id,),
            ).fetchall()
        ]

    def list_recent_turns(self, *, n: int = 10, epic_id: str | None = None) -> list[JSONDict]:
        params: list[Any] = []
        where_sql = ""
        if epic_id is not None:
            where_sql = "WHERE epic_id = ?"
            params.append(epic_id)
        params.append(int(n))
        return [
            _decode_row(row) or {}
            for row in self._conn.execute(
                f"""
                SELECT * FROM bot_turns
                {where_sql}
                ORDER BY started_at DESC, id DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
        ]

    def search_tool_calls_by(
        self,
        *,
        tool_name: str | None = None,
        epic_id: str | None = None,
        since: str | None = None,
        limit: int = 20,
    ) -> list[JSONDict]:
        clauses: list[str] = []
        params: list[Any] = []
        if tool_name is not None:
            clauses.append("tool_calls.tool_name = ?")
            params.append(tool_name)
        if epic_id is not None:
            clauses.append("bot_turns.epic_id = ?")
            params.append(epic_id)
        if since is not None:
            clauses.append("tool_calls.called_at >= ?")
            params.append(since)
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(int(limit))
        return [
            _decode_row(row) or {}
            for row in self._conn.execute(
                f"""
                SELECT tool_calls.*
                FROM tool_calls
                JOIN bot_turns ON bot_turns.id = tool_calls.turn_id
                {where_sql}
                ORDER BY tool_calls.called_at DESC, tool_calls.id DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
        ]

    def create_feedback(
        self,
        *,
        kind: str,
        content: str,
        source: str,
        source_message_id: str | None = None,
        epic_id: str | None = None,
        turn_id: str | None = None,
        context_snapshot: JSONDict | None = None,
    ) -> JSONDict:
        feedback_id = _new_id("fb")
        self._conn.execute(
            """
            INSERT INTO feedback (
                id, kind, content, source, source_message_id, epic_id, turn_id,
                context_snapshot
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                feedback_id,
                kind,
                content,
                source,
                source_message_id,
                epic_id,
                turn_id,
                _json_dumps(context_snapshot) if context_snapshot is not None else None,
            ),
        )
        self._commit_if_needed()
        return self.load_feedback(feedback_id) or {}

    def load_feedback(self, feedback_id: str) -> JSONDict | None:
        return _decode_row(
            self._conn.execute(
                "SELECT * FROM feedback WHERE id = ?",
                (feedback_id,),
            ).fetchone()
        )

    def update_feedback(self, feedback_id: str, **changes: Any) -> JSONDict:
        return self._update("feedback", "id", feedback_id, changes, _FEEDBACK_COLUMNS, self.load_feedback)

    def list_feedback(
        self,
        *,
        epic_id: str | None = None,
        active: bool | None = None,
        kinds: Sequence[str] | None = None,
        limit: int | None = None,
    ) -> list[JSONDict]:
        clauses = ["kind IN ('style', 'process', 'epic_specific')"]
        params: list[Any] = []
        if epic_id is None:
            clauses.append("epic_id IS NULL")
            clauses.append("kind IN ('style', 'process')")
        else:
            clauses.append("((epic_id IS NULL AND kind IN ('style', 'process')) OR epic_id = ?)")
            params.append(epic_id)
        if active is not None:
            clauses.append("active = ?")
            params.append(int(active))
        if kinds:
            placeholders = ", ".join("?" for _ in kinds)
            clauses.append(f"kind IN ({placeholders})")
            params.extend(kinds)
        limit_sql = f" LIMIT {int(limit)}" if limit is not None else ""
        return [
            _decode_row(row) or {}
            for row in self._conn.execute(
                f"""
                SELECT * FROM feedback
                WHERE {' AND '.join(clauses)}
                ORDER BY created_at DESC, id DESC
                {limit_sql}
                """,
                params,
            ).fetchall()
        ]

    def list_observations(
        self,
        *,
        resolved: bool | None = None,
        limit: int | None = None,
    ) -> list[JSONDict]:
        clauses = [
            """
            kind IN (
                'friction',
                'ambiguity',
                'tool_failure',
                'confusion',
                'pattern_noticed'
            )
            """
        ]
        params: list[Any] = []
        if resolved is not None:
            clauses.append("resolved = ?")
            params.append(int(resolved))
        limit_sql = f" LIMIT {int(limit)}" if limit is not None else ""
        return [
            _decode_row(row) or {}
            for row in self._conn.execute(
                f"""
                SELECT * FROM feedback
                WHERE {' AND '.join(clauses)}
                ORDER BY created_at DESC, id DESC
                {limit_sql}
                """,
                params,
            ).fetchall()
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
    ) -> JSONDict:
        sprint_id = _new_id("sprint")
        self._conn.execute(
            """
            INSERT INTO sprints (
                id, epic_id, sprint_number, name, goal, status, queue_position,
                pending_reason, target_weeks, queued_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                sprint_id,
                epic_id,
                int(sprint_number),
                name,
                goal,
                status,
                queue_position,
                pending_reason,
                int(target_weeks),
                _now() if status == "queued" else None,
            ),
        )
        self._commit_if_needed()
        return self.load_sprint(sprint_id) or {}

    def load_sprint(self, sprint_id: str) -> JSONDict | None:
        return _decode_row(
            self._conn.execute("SELECT * FROM sprints WHERE id = ?", (sprint_id,)).fetchone()
        )

    def list_sprints(self, epic_id: str) -> list[JSONDict]:
        return [
            _decode_row(row) or {}
            for row in self._conn.execute(
                """
                SELECT * FROM sprints
                WHERE epic_id = ?
                ORDER BY sprint_number, id
                """,
                (epic_id,),
            ).fetchall()
        ]

    def update_sprint(self, sprint_id: str, **changes: Any) -> JSONDict:
        normalized = dict(changes)
        if normalized.get("status") == "queued" and "queued_at" not in normalized:
            normalized["queued_at"] = _now()
        if normalized:
            normalized.setdefault("updated_at", _now())
        return self._update("sprints", "id", sprint_id, normalized, _SPRINT_COLUMNS, self.load_sprint)

    def delete_sprint(self, sprint_id: str) -> None:
        self._conn.execute("DELETE FROM sprints WHERE id = ?", (sprint_id,))
        self._commit_if_needed()

    def replace_sprint_items(self, sprint_id: str, items: Sequence[JSONDict]) -> list[JSONDict]:
        with self.transaction():
            self._conn.execute("DELETE FROM sprint_items WHERE sprint_id = ?", (sprint_id,))
            added: list[JSONDict] = []
            for offset, item in enumerate(items, start=1):
                item_id = str(item.get("id") or _new_id("sitem"))
                self._conn.execute(
                    """
                    INSERT INTO sprint_items (
                        id, sprint_id, content, estimated_complexity, status,
                        source_section, position, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, COALESCE(?, strftime('%Y-%m-%dT%H:%M:%fZ', 'now')))
                    """,
                    (
                        item_id,
                        sprint_id,
                        item["content"],
                        item.get("estimated_complexity", "medium"),
                        item.get("status", "open"),
                        item.get("source_section"),
                        int(item.get("position", offset)),
                        item.get("created_at"),
                    ),
                )
                added.append(self._load_sprint_item(item_id) or {})
            return added

    def list_sprint_items(self, sprint_id: str) -> list[JSONDict]:
        return [
            _decode_row(row) or {}
            for row in self._conn.execute(
                """
                SELECT * FROM sprint_items
                WHERE sprint_id = ?
                ORDER BY position, id
                """,
                (sprint_id,),
            ).fetchall()
        ]

    def list_sprints_with_items(self, epic_id: str) -> list[JSONDict]:
        return [
            {**sprint, "items": self.list_sprint_items(str(sprint["id"]))}
            for sprint in self.list_sprints(epic_id)
        ]

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
        if source == "user_uploaded":
            prefix = "img_user_upload"
        elif source == "caller_uploaded":
            prefix = "img_caller_upload"
        else:
            prefix = "img_agent"
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

    def _load_second_opinion(self, opinion_id: str) -> JSONDict | None:
        return _decode_row(
            self._conn.execute(
                "SELECT * FROM second_opinions WHERE id = ?",
                (opinion_id,),
            ).fetchone()
        )

    def _load_codebase(self, codebase_id: str) -> JSONDict | None:
        return self.load_codebase(codebase_id)

    def _load_code_artifact(self, artifact_id: str) -> JSONDict | None:
        return self.load_code_artifact(artifact_id)

    def _load_checklist_item(self, item_id: str) -> JSONDict | None:
        return _decode_row(
            self._conn.execute(
                "SELECT * FROM checklist_items WHERE id = ?",
                (item_id,),
            ).fetchone()
        )

    def _load_epic_event(self, event_id: str) -> JSONDict | None:
        return _decode_row(
            self._conn.execute(
                "SELECT * FROM epic_events WHERE id = ?",
                (event_id,),
            ).fetchone()
        )

    def _load_sprint_item(self, item_id: str) -> JSONDict | None:
        return _decode_row(
            self._conn.execute(
                "SELECT * FROM sprint_items WHERE id = ?",
                (item_id,),
            ).fetchone()
        )

    def _update(
        self,
        table: str,
        key_column: str,
        row_id: str,
        changes: dict[str, Any],
        allowed: set[str],
        loader,
    ) -> JSONDict:
        if not changes:
            return loader(row_id) or {}
        unknown = set(changes) - allowed
        if unknown:
            raise ValueError(f"unsupported {table} columns: {', '.join(sorted(unknown))}")
        normalized = {
            key: _to_sql_value(key, _redacted_update_value(table, key, value))
            for key, value in changes.items()
        }
        assignments = ", ".join(f"{key} = ?" for key in normalized)
        values = list(normalized.values()) + [row_id]
        self._conn.execute(
            f"UPDATE {table} SET {assignments} WHERE {key_column} = ?",
            values,
        )
        self._commit_if_needed()
        return loader(row_id) or {}

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


def _epic_result(row: sqlite3.Row) -> JSONDict:
    decoded = _decode_row(row) or {}
    return {
        "id": decoded.get("id"),
        "title": decoded.get("title"),
        "goal": decoded.get("goal"),
        "state": decoded.get("state"),
        "snippet": decoded.get("snippet"),
        "created_at": decoded.get("created_at"),
        "last_edited_at": decoded.get("last_edited_at"),
        "last_active_at": decoded.get("last_active_at"),
        "rank": decoded.get("rank"),
        "disambiguation": {
            "label": decoded.get("title"),
            "updated": decoded.get("last_edited_at"),
        },
    }


def _message_result(row: sqlite3.Row) -> JSONDict:
    decoded = _decode_row(row) or {}
    return {
        "id": decoded.get("id"),
        "epic_id": decoded.get("epic_id"),
        "direction": decoded.get("direction"),
        "snippet": decoded.get("snippet"),
        "content": decoded.get("content"),
        "sent_at": decoded.get("sent_at"),
        "rank": decoded.get("rank"),
        "disambiguation": {
            "direction": decoded.get("direction"),
            "sent_at": decoded.get("sent_at"),
        },
    }


def _hot_context_image(row: JSONDict) -> JSONDict:
    return {
        "id": row.get("id"),
        "reference_key": row.get("reference_key"),
        "source": row.get("source"),
        "description": row.get("description"),
        "caption": row.get("caption"),
        "storage_url": row.get("storage_url"),
        "quality": row.get("quality"),
        "size": row.get("size"),
        "created_at": row.get("created_at"),
    }


def _hot_context_codebase(row: JSONDict) -> JSONDict:
    return {
        "id": row.get("id"),
        "owner": row.get("owner"),
        "name": row.get("name"),
        "scope": row.get("scope"),
        "group_name": row.get("group_name"),
        "notes": row.get("notes"),
        "verified_accessible_at": row.get("verified_accessible_at"),
    }


def _hot_context_code_artifact(row: JSONDict) -> JSONDict:
    return {
        "id": row.get("id"),
        "kind": row.get("kind"),
        "source": row.get("source"),
        "file_path": row.get("file_path"),
        "line_range": row.get("line_range"),
        "scope": row.get("scope"),
        "content_summary": row.get("content_summary"),
        "metadata": row.get("metadata"),
    }


def _hot_context_second_opinion(row: JSONDict) -> JSONDict:
    return {
        "id": row.get("id"),
        "requested_at": row.get("requested_at"),
        "requested_by": row.get("requested_by"),
        "focus_areas": row.get("focus_areas") or [],
        "score": row.get("score"),
        "summary": row.get("summary"),
        "verdict": row.get("verdict"),
        "model_used": row.get("model_used"),
        "resulting_checklist_item_ids": row.get("resulting_checklist_item_ids") or [],
    }


def _to_sql_value(key: str, value: Any) -> Any:
    if key in _JSON_COLUMNS and value is not None:
        return _json_dumps(value)
    if isinstance(value, bool):
        return int(value)
    return value


def _json_dumps(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _redacted_update_value(table: str, key: str, value: Any) -> Any:
    if table in {"tool_calls", "system_logs", "code_artifacts"} and key in {
        "arguments",
        "result",
        "details",
        "content",
        "content_summary",
        "metadata",
    }:
        return redact_code_secrets(value)
    return value


def _normalize_repo_key(owner: str, name: str) -> tuple[str, str]:
    normalized_owner = owner.strip().lower()
    normalized_name = name.strip().lower()
    if not normalized_owner or not normalized_name:
        raise ValueError("owner and name are required")
    return normalized_owner, normalized_name


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def _now() -> str:
    return _format_datetime(datetime.now(UTC))


def _format_datetime(value: datetime) -> str:
    return value.isoformat(timespec="milliseconds").replace("+00:00", "Z")


_MESSAGE_COLUMNS = {
    "epic_id",
    "discord_message_id",
    "content",
    "audio_storage_url",
    "transcription_metadata",
    "has_image_attachment",
    "has_code_attachment",
    "in_burst_with",
    "was_voice_message",
    "bot_turn_id",
}
_TURN_COLUMNS = {
    "epic_id",
    "triggered_by_message_ids",
    "prompt_snapshot",
    "prompt_version",
    "reasoning",
    "final_output_message_id",
    "status_message_id",
    "status",
    "state_at_turn",
    "plan_edited",
    "code_consulted",
    "image_generated",
    "second_opinion_requested",
    "message_sent",
    "warnings_issued",
    "current_activity",
    "completed_at",
    "model_version",
}
_IMAGE_COLUMNS = {
    "prompt",
    "storage_url",
    "quality",
    "size",
    "reference_key",
    "description",
    "caption",
    "in_body",
    "active",
    "discord_attachment_id",
}
_SECOND_OPINION_COLUMNS = {
    "resulting_checklist_item_ids",
}
_CODEBASE_COLUMNS = {
    "owner",
    "name",
    "default_branch",
    "scope",
    "group_name",
    "associated_epic_id",
    "added_via",
    "last_accessed_at",
    "verified_accessible_at",
    "notes",
}
_CODE_ARTIFACT_COLUMNS = {
    "codebase_id",
    "epic_id",
    "kind",
    "source",
    "file_path",
    "line_range",
    "scope",
    "content",
    "content_summary",
    "metadata",
    "last_used_at",
    "expires_at",
}
_EPIC_COLUMNS = {
    "title",
    "goal",
    "body",
    "state",
    "last_edited_at",
    "last_active_at",
    "planned_at",
}
_CHECKLIST_COLUMNS = {
    "content",
    "status",
    "position",
    "skip_reason",
    "superseded_by_item_id",
    "completed_at",
}
_FEEDBACK_COLUMNS = {
    "kind",
    "content",
    "source",
    "source_message_id",
    "epic_id",
    "turn_id",
    "context_snapshot",
    "active",
    "deactivation_reason",
    "resolved",
    "resolution_note",
    "resolved_at",
    "last_referenced_at",
    "last_applied_at",
}
_SPRINT_COLUMNS = {
    "sprint_number",
    "name",
    "goal",
    "status",
    "queue_position",
    "pending_reason",
    "target_weeks",
    "updated_at",
    "queued_at",
}
