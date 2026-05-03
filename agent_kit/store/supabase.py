"""Supabase/Postgres Store adapter for resident mode."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
import os
from typing import Any, Iterator, Sequence
from uuid import uuid4

from agent_kit.code_redaction import redact_code_secrets

JSONDict = dict[str, Any]
_ACTIVE_EPIC_STATES = ("shaping", "sprinting", "planned", "paused")

_JSON_COLUMNS = {"arguments", "context_snapshot", "details", "error_details", "focus_areas", "in_burst_with", "line_range", "metadata", "prompt_snapshot", "prior_state", "provider_response_summary", "request_body", "request_summary", "result", "resulting_checklist_item_ids", "state_at_turn", "transcription_metadata", "triggered_by_message_ids", "warnings_issued"}


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

    def latest_outbound_message(self, *, epic_id: str | None = None) -> JSONDict | None:
        clauses = ["direction = 'outbound'"]
        params: list[Any] = []
        if epic_id is not None:
            clauses.append("epic_id = %s")
            params.append(epic_id)
        return _normalize(
            self._conn.execute(
                f"SELECT * FROM messages WHERE {' AND '.join(clauses)} ORDER BY sent_at DESC, id DESC LIMIT 1",
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
            (
                tool_call_id,
                turn_id,
                tool_name,
                operation_kind,
                _json(redact_code_secrets(arguments)),
                _json(redact_code_secrets(result)),
                duration_ms,
            ),
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
            (
                log_id,
                level,
                category,
                event_type,
                message,
                _json(redact_code_secrets(details or {})),
                turn_id,
                epic_id,
            ),
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

    def load_hot_context(self, epic_id: str | None) -> JSONDict:
        epic = None
        messages: list[JSONDict] = []
        tool_calls: list[JSONDict] = []
        sprints: list[JSONDict] = []
        if epic_id is not None:
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

    def list_active_images(self, epic_id: str) -> list[JSONDict]:
        return self.list_images(epic_id=epic_id, active=True)

    def load_active_image_by_reference(self, epic_id: str, reference_key: str) -> JSONDict | None:
        return _normalize(
            self._conn.execute(
                "SELECT * FROM images WHERE epic_id = %s AND reference_key = %s AND active = true ORDER BY created_at DESC, id DESC LIMIT 1",
                (epic_id, reference_key),
            ).fetchone()
        )

    def active_image_reference_exists(self, epic_id: str, reference_key: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM images WHERE epic_id = %s AND reference_key = %s AND active = true LIMIT 1",
            (epic_id, reference_key),
        ).fetchone()
        return row is not None

    def deactivate_active_image_reference(self, epic_id: str, reference_key: str) -> list[JSONDict]:
        rows = _normalize_rows(
            self._conn.execute(
                "SELECT * FROM images WHERE epic_id = %s AND reference_key = %s AND active = true ORDER BY created_at DESC, id DESC",
                (epic_id, reference_key),
            ).fetchall()
        )
        self._conn.execute(
            "UPDATE images SET active = false WHERE epic_id = %s AND reference_key = %s AND active = true",
            (epic_id, reference_key),
        )
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
            "INSERT INTO second_opinions (id, epic_id, requested_by, focus_areas, raw_response, score, summary, verdict, resulting_checklist_item_ids, model_used) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                opinion_id,
                epic_id,
                requested_by,
                _json(list(focus_areas)),
                raw_response,
                int(score),
                summary,
                verdict,
                _json(list(resulting_checklist_item_ids or [])),
                model_used,
            ),
        )
        return self._load_second_opinion(opinion_id) or {}

    def list_second_opinions(self, epic_id: str, *, limit: int | None = None) -> list[JSONDict]:
        sql = "SELECT * FROM second_opinions WHERE epic_id = %s ORDER BY requested_at DESC, id DESC"
        params: list[Any] = [epic_id]
        if limit is not None:
            sql += " LIMIT %s"
            params.append(int(limit))
        return _normalize_rows(self._conn.execute(sql, params).fetchall())

    def set_second_opinion_checklist_items(
        self,
        second_opinion_id: str,
        checklist_item_ids: Sequence[str],
    ) -> JSONDict:
        self._conn.execute(
            "UPDATE second_opinions SET resulting_checklist_item_ids = %s WHERE id = %s",
            (_json(list(checklist_item_ids)), second_opinion_id),
        )
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
            "INSERT INTO codebases (id, owner, name, default_branch, scope, group_name, associated_epic_id, added_via, verified_accessible_at, notes) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
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
        return _normalize(self._conn.execute("SELECT * FROM codebases WHERE id = %s", (codebase_id,)).fetchone())

    def find_codebase(self, owner: str, name: str) -> JSONDict | None:
        normalized_owner, normalized_name = _normalize_repo_key(owner, name)
        return _normalize(
            self._conn.execute(
                "SELECT * FROM codebases WHERE owner = %s AND name = %s ORDER BY added_at DESC, id DESC LIMIT 1",
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
            clauses.append("scope = %s")
            params.append(scope)
        if group_name is not None:
            clauses.append("group_name = %s")
            params.append(group_name)
        if epic_id is not None:
            if include_global:
                clauses.append("(associated_epic_id = %s OR scope = 'global')")
            else:
                clauses.append("associated_epic_id = %s")
            params.append(epic_id)
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        return _normalize_rows(
            self._conn.execute(
                f"SELECT * FROM codebases {where_sql} ORDER BY group_name IS NULL, group_name, owner, name",
                params,
            ).fetchall()
        )

    def update_codebase(self, codebase_id: str, **changes: Any) -> JSONDict:
        normalized = dict(changes)
        if "owner" in normalized or "name" in normalized:
            current = self.load_codebase(codebase_id) or {}
            owner = str(normalized.get("owner", current.get("owner", "")))
            name = str(normalized.get("name", current.get("name", "")))
            normalized["owner"], normalized["name"] = _normalize_repo_key(owner, name)
        return self._update("codebases", "id", codebase_id, normalized, _CODEBASE_COLUMNS, self.load_codebase)

    def remove_codebase(self, codebase_id: str) -> None:
        self._conn.execute("DELETE FROM codebases WHERE id = %s", (codebase_id,))

    def touch_codebase_accessed(self, codebase_id: str, *, accessed_at: str | None = None) -> JSONDict:
        return self.update_codebase(codebase_id, last_accessed_at=accessed_at or datetime.now(UTC))

    def mark_codebase_verified(
        self,
        codebase_id: str,
        *,
        verified_at: str | None = None,
        default_branch: str | None = None,
    ) -> JSONDict:
        changes: dict[str, Any] = {"verified_accessible_at": verified_at or datetime.now(UTC)}
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
            "INSERT INTO code_artifacts (id, codebase_id, epic_id, kind, source, file_path, line_range, scope, content, content_summary, metadata, expires_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                artifact_id,
                codebase_id,
                epic_id,
                kind,
                source,
                file_path,
                _json(line_range) if line_range is not None else None,
                scope,
                safe_content,
                safe_summary,
                _json(safe_metadata),
                expires_at,
            ),
        )
        return self.load_code_artifact(artifact_id) or {}

    def load_code_artifact(self, artifact_id: str) -> JSONDict | None:
        return _normalize(self._conn.execute("SELECT * FROM code_artifacts WHERE id = %s", (artifact_id,)).fetchone())

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
            clauses.append("codebase_id = %s")
            params.append(codebase_id)
        if epic_id is not None:
            clauses.append("epic_id = %s")
            params.append(epic_id)
        if kind is not None:
            clauses.append("kind = %s")
            params.append(kind)
        if source is not None:
            clauses.append("source = %s")
            params.append(source)
        if file_path is not None:
            clauses.append("file_path = %s")
            params.append(file_path)
        if scope is not None:
            clauses.append("scope = %s")
            params.append(scope)
        if not include_expired:
            clauses.append("(expires_at IS NULL OR expires_at > %s)")
            params.append(datetime.now(UTC))
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        limit_sql = " LIMIT %s" if limit is not None else ""
        if limit is not None:
            params.append(int(limit))
        return _normalize_rows(
            self._conn.execute(
                f"SELECT * FROM code_artifacts {where_sql} ORDER BY created_at DESC, id DESC{limit_sql}",
                params,
            ).fetchall()
        )

    def update_code_artifact(self, artifact_id: str, **changes: Any) -> JSONDict:
        return self._update("code_artifacts", "id", artifact_id, changes, _CODE_ARTIFACT_COLUMNS, self.load_code_artifact)

    def delete_code_artifact(self, artifact_id: str) -> None:
        self._conn.execute("DELETE FROM code_artifacts WHERE id = %s", (artifact_id,))

    def touch_code_artifact_used(self, artifact_id: str, *, used_at: str | None = None) -> JSONDict:
        return self.update_code_artifact(artifact_id, last_used_at=used_at or datetime.now(UTC))

    def get_api_cache(
        self,
        cache_key: str,
        *,
        now: str | None = None,
        touch: bool = True,
    ) -> JSONDict | None:
        checked_at = now or datetime.now(UTC)
        row = _normalize(
            self._conn.execute(
                "SELECT * FROM code_artifacts WHERE kind = 'api_cache' AND metadata->>'cache_key' = %s AND (expires_at IS NULL OR expires_at > %s) ORDER BY created_at DESC, id DESC LIMIT 1",
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
        expires_at = expires_at or datetime.now(UTC) + timedelta(seconds=ttl_seconds)
        existing = _normalize(
            self._conn.execute(
                "SELECT * FROM code_artifacts WHERE kind = 'api_cache' AND metadata->>'cache_key' = %s ORDER BY created_at DESC, id DESC LIMIT 1",
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
            last_used_at=datetime.now(UTC),
        )

    def cleanup_expired_api_cache(self, *, now: str | None = None) -> int:
        checked_at = now or datetime.now(UTC)
        cursor = self._conn.execute(
            "DELETE FROM code_artifacts WHERE kind = 'api_cache' AND expires_at IS NOT NULL AND expires_at < %s",
            (checked_at,),
        )
        return int(getattr(cursor, "rowcount", 0) or 0)

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
            "INSERT INTO epics (id, title, goal, body, state) VALUES (%s, %s, %s, %s, %s)",
            (epic_id, title, goal, body, state),
        )
        return self.load_epic(epic_id) or {}

    def load_epic(self, epic_id: str) -> JSONDict | None:
        return _normalize(self._conn.execute("SELECT * FROM epics WHERE id = %s", (epic_id,)).fetchone())

    def list_epics(self, *, active_only: bool = True, limit: int = 20) -> list[JSONDict]:
        clauses: list[str] = []
        params: list[Any] = []
        if active_only:
            clauses.append(f"state IN ({', '.join('%s' for _ in _ACTIVE_EPIC_STATES)})")
            params.extend(_ACTIVE_EPIC_STATES)
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(int(limit))
        return [
            _epic_result(row)
            for row in self._conn.execute(
                f"SELECT epics.*, substring(body from 1 for 240) AS snippet FROM epics {where_sql} ORDER BY last_edited_at DESC, id DESC LIMIT %s",
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
        clauses = ["(lower(title) LIKE %s OR lower(goal) LIKE %s OR lower(body) LIKE %s)"]
        params: list[Any] = [like, like, like]
        if active_only:
            clauses.append(f"state IN ({', '.join('%s' for _ in _ACTIVE_EPIC_STATES)})")
            params.extend(_ACTIVE_EPIC_STATES)
        params.append(int(limit))
        return [
            _epic_result(row)
            for row in self._conn.execute(
                f"""
                SELECT epics.*,
                       substring(body from 1 for 240) AS snippet,
                       CASE
                         WHEN lower(title) LIKE %s THEN 3
                         WHEN lower(goal) LIKE %s THEN 2
                         ELSE 1
                       END AS rank
                FROM epics
                WHERE {' AND '.join(clauses)}
                ORDER BY rank DESC, last_edited_at DESC, id DESC
                LIMIT %s
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
        clauses = ["to_tsvector('english', content) @@ websearch_to_tsquery('english', %s)"]
        params: list[Any] = [query]
        if epic_id is not None:
            clauses.append("epic_id = %s")
            params.append(epic_id)
        params.append(int(limit))
        return [
            _message_result(row)
            for row in self._conn.execute(
                f"""
                SELECT *,
                       ts_rank_cd(to_tsvector('english', content), websearch_to_tsquery('english', %s)) AS rank,
                       ts_headline('english', content, websearch_to_tsquery('english', %s), 'StartSel=[, StopSel=], MaxWords=12') AS snippet
                FROM messages
                WHERE {' AND '.join(clauses)}
                ORDER BY rank DESC, sent_at DESC, id DESC
                LIMIT %s
                """,
                [query, query, *params],
            ).fetchall()
        ]

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
        clauses = ["epic_id = %s"]
        params: list[Any] = [epic_id]
        if status is not None:
            clauses.append("status = %s")
            params.append(status)
        return _normalize_rows(
            self._conn.execute(
                f"SELECT * FROM checklist_items WHERE {' AND '.join(clauses)} ORDER BY position, id",
                params,
            ).fetchall()
        )

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
        max_position_row = self._conn.execute(
            "SELECT COALESCE(MAX(position), 0) AS max_position FROM checklist_items WHERE epic_id = %s",
            (epic_id,),
        ).fetchone()
        max_position = int(max_position_row["max_position"] or 0)
        for offset, item in enumerate(items, start=1):
            item_id = str(item.get("id") or _new_id("check"))
            self._conn.execute(
                """
                INSERT INTO checklist_items (
                    id, epic_id, content, status, position, source,
                    skip_reason, superseded_by_item_id, created_at, completed_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, COALESCE(%s, now()), %s)
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
        return added

    def delete_checklist_items(self, item_ids: Sequence[str]) -> None:
        if not item_ids:
            return
        self._conn.execute(
            "DELETE FROM checklist_items WHERE id = ANY(%s)",
            (list(item_ids),),
        )

    def replace_checklist(self, epic_id: str, items: Sequence[JSONDict]) -> list[JSONDict]:
        with self.transaction():
            self._conn.execute("DELETE FROM checklist_items WHERE epic_id = %s", (epic_id,))
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
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                event_id,
                epic_id,
                transaction_id,
                event_type,
                summary,
                _json(prior_state) if prior_state is not None else None,
                turn_id,
            ),
        )
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
        clauses = ["epic_id = %s"]
        params: list[Any] = [epic_id]
        if since is not None:
            clauses.append("occurred_at >= %s")
            params.append(since)
        if until is not None:
            clauses.append("occurred_at <= %s")
            params.append(until)
        if kinds:
            clauses.append("event_type = ANY(%s)")
            params.append(list(kinds))
        limit_sql = " LIMIT %s" if limit is not None else ""
        if limit is not None:
            params.append(int(limit))
        return _normalize_rows(
            self._conn.execute(
                f"SELECT * FROM epic_events WHERE {' AND '.join(clauses)} ORDER BY occurred_at, id{limit_sql}",
                params,
            ).fetchall()
        )

    def latest_transaction_id(self, epic_id: str) -> str | None:
        row = self._conn.execute(
            """
            SELECT transaction_id FROM epic_events
            WHERE epic_id = %s
            ORDER BY occurred_at DESC, id DESC
            LIMIT 1
            """,
            (epic_id,),
        ).fetchone()
        return str(row["transaction_id"]) if row is not None else None

    def events_by_transaction(self, transaction_id: str) -> list[JSONDict]:
        return _normalize_rows(
            self._conn.execute(
                """
                SELECT * FROM epic_events
                WHERE transaction_id = %s
                ORDER BY occurred_at, id
                """,
                (transaction_id,),
            ).fetchall()
        )

    def list_recent_turns(self, *, n: int = 10, epic_id: str | None = None) -> list[JSONDict]:
        clauses: list[str] = []
        params: list[Any] = []
        if epic_id is not None:
            clauses.append("epic_id = %s")
            params.append(epic_id)
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(int(n))
        return _normalize_rows(
            self._conn.execute(
                f"SELECT * FROM bot_turns {where_sql} ORDER BY started_at DESC, id DESC LIMIT %s",
                params,
            ).fetchall()
        )

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
            clauses.append("tool_calls.tool_name = %s")
            params.append(tool_name)
        if epic_id is not None:
            clauses.append("bot_turns.epic_id = %s")
            params.append(epic_id)
        if since is not None:
            clauses.append("tool_calls.called_at >= %s")
            params.append(since)
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(int(limit))
        return _normalize_rows(
            self._conn.execute(
                f"""
                SELECT tool_calls.*
                FROM tool_calls
                JOIN bot_turns ON bot_turns.id = tool_calls.turn_id
                {where_sql}
                ORDER BY tool_calls.called_at DESC, tool_calls.id DESC
                LIMIT %s
                """,
                params,
            ).fetchall()
        )

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
            "INSERT INTO feedback (id, kind, content, source, source_message_id, epic_id, turn_id, context_snapshot) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (
                feedback_id,
                kind,
                content,
                source,
                source_message_id,
                epic_id,
                turn_id,
                _json(context_snapshot) if context_snapshot is not None else None,
            ),
        )
        return self.load_feedback(feedback_id) or {}

    def load_feedback(self, feedback_id: str) -> JSONDict | None:
        return _normalize(self._conn.execute("SELECT * FROM feedback WHERE id = %s", (feedback_id,)).fetchone())

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
        clauses = ["kind = ANY(%s)"]
        params: list[Any] = [["style", "process", "epic_specific"]]
        if epic_id is None:
            clauses.append("epic_id IS NULL")
            clauses.append("kind = ANY(%s)")
            params.append(["style", "process"])
        else:
            clauses.append("((epic_id IS NULL AND kind = ANY(%s)) OR epic_id = %s)")
            params.append(["style", "process"])
            params.append(epic_id)
        if active is not None:
            clauses.append("active = %s")
            params.append(active)
        if kinds:
            clauses.append("kind = ANY(%s)")
            params.append(list(kinds))
        limit_sql = " LIMIT %s" if limit is not None else ""
        if limit is not None:
            params.append(int(limit))
        return _normalize_rows(
            self._conn.execute(
                f"SELECT * FROM feedback WHERE {' AND '.join(clauses)} ORDER BY created_at DESC, id DESC{limit_sql}",
                params,
            ).fetchall()
        )

    def list_observations(
        self,
        *,
        resolved: bool | None = None,
        limit: int | None = None,
    ) -> list[JSONDict]:
        clauses = ["kind = ANY(%s)"]
        params: list[Any] = [[
            "friction",
            "ambiguity",
            "tool_failure",
            "confusion",
            "pattern_noticed",
        ]]
        if resolved is not None:
            clauses.append("resolved = %s")
            params.append(resolved)
        limit_sql = " LIMIT %s" if limit is not None else ""
        if limit is not None:
            params.append(int(limit))
        return _normalize_rows(
            self._conn.execute(
                f"SELECT * FROM feedback WHERE {' AND '.join(clauses)} ORDER BY created_at DESC, id DESC{limit_sql}",
                params,
            ).fetchall()
        )

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
            "INSERT INTO sprints (id, epic_id, sprint_number, name, goal, status, queue_position, pending_reason, target_weeks, queued_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, CASE WHEN %s = 'queued' THEN now() ELSE NULL END)",
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
                status,
            ),
        )
        return self.load_sprint(sprint_id) or {}

    def load_sprint(self, sprint_id: str) -> JSONDict | None:
        return _normalize(self._conn.execute("SELECT * FROM sprints WHERE id = %s", (sprint_id,)).fetchone())

    def list_sprints(self, epic_id: str) -> list[JSONDict]:
        return _normalize_rows(
            self._conn.execute(
                "SELECT * FROM sprints WHERE epic_id = %s ORDER BY sprint_number, id",
                (epic_id,),
            ).fetchall()
        )

    def update_sprint(self, sprint_id: str, **changes: Any) -> JSONDict:
        normalized = dict(changes)
        if normalized.get("status") == "queued" and "queued_at" not in normalized:
            normalized["queued_at"] = datetime.now(UTC)
        if normalized:
            normalized.setdefault("updated_at", datetime.now(UTC))
        return self._update("sprints", "id", sprint_id, normalized, _SPRINT_COLUMNS, self.load_sprint)

    def delete_sprint(self, sprint_id: str) -> None:
        self._conn.execute("DELETE FROM sprints WHERE id = %s", (sprint_id,))

    def replace_sprint_items(self, sprint_id: str, items: Sequence[JSONDict]) -> list[JSONDict]:
        with self.transaction():
            self._conn.execute("DELETE FROM sprint_items WHERE sprint_id = %s", (sprint_id,))
            added: list[JSONDict] = []
            for offset, item in enumerate(items, start=1):
                item_id = str(item.get("id") or _new_id("sitem"))
                self._conn.execute(
                    "INSERT INTO sprint_items (id, sprint_id, content, estimated_complexity, status, source_section, position, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, COALESCE(%s, now()))",
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
        return _normalize_rows(
            self._conn.execute(
                "SELECT * FROM sprint_items WHERE sprint_id = %s ORDER BY position, id",
                (sprint_id,),
            ).fetchall()
        )

    def list_sprints_with_items(self, epic_id: str) -> list[JSONDict]:
        return [
            {**sprint, "items": self.list_sprint_items(str(sprint["id"]))}
            for sprint in self.list_sprints(epic_id)
        ]

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
        values = [
            _to_sql_value(key, _redacted_update_value(table, key, value))
            for key, value in changes.items()
        ]
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
        if source == "user_uploaded":
            prefix = "img_user_upload"
        elif source == "caller_uploaded":
            prefix = "img_caller_upload"
        else:
            prefix = "img_agent"
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

    def _load_second_opinion(self, opinion_id: str) -> JSONDict | None:
        return _normalize(self._conn.execute("SELECT * FROM second_opinions WHERE id = %s", (opinion_id,)).fetchone())

    def _load_checklist_item(self, item_id: str) -> JSONDict | None:
        return _normalize(self._conn.execute("SELECT * FROM checklist_items WHERE id = %s", (item_id,)).fetchone())

    def _load_epic_event(self, event_id: str) -> JSONDict | None:
        return _normalize(self._conn.execute("SELECT * FROM epic_events WHERE id = %s", (event_id,)).fetchone())

    def _load_sprint_item(self, item_id: str) -> JSONDict | None:
        return _normalize(self._conn.execute("SELECT * FROM sprint_items WHERE id = %s", (item_id,)).fetchone())


_MESSAGE_COLUMNS = {"epic_id", "discord_message_id", "content", "audio_storage_url", "transcription_metadata", "has_image_attachment", "has_code_attachment", "in_burst_with", "was_voice_message", "bot_turn_id"}
_TURN_COLUMNS = {"epic_id", "triggered_by_message_ids", "prompt_snapshot", "prompt_version", "reasoning", "final_output_message_id", "status_message_id", "status", "state_at_turn", "plan_edited", "code_consulted", "image_generated", "second_opinion_requested", "message_sent", "warnings_issued", "current_activity", "completed_at", "model_version"}
_IMAGE_COLUMNS = {"prompt", "storage_url", "quality", "size", "reference_key", "description", "caption", "in_body", "active", "discord_attachment_id"}
_CODEBASE_COLUMNS = {"owner", "name", "default_branch", "scope", "group_name", "associated_epic_id", "added_via", "last_accessed_at", "verified_accessible_at", "notes"}
_CODE_ARTIFACT_COLUMNS = {"codebase_id", "epic_id", "kind", "source", "file_path", "line_range", "scope", "content", "content_summary", "metadata", "last_used_at", "expires_at"}
_EPIC_COLUMNS = {"title", "goal", "body", "state", "last_edited_at", "last_active_at", "planned_at"}
_CHECKLIST_COLUMNS = {"content", "status", "position", "skip_reason", "superseded_by_item_id", "completed_at"}
_FEEDBACK_COLUMNS = {"kind", "content", "source", "source_message_id", "epic_id", "turn_id", "context_snapshot", "active", "deactivation_reason", "resolved", "resolution_note", "resolved_at", "last_referenced_at", "last_applied_at"}
_SPRINT_COLUMNS = {"sprint_number", "name", "goal", "status", "queue_position", "pending_reason", "target_weeks", "updated_at", "queued_at"}


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
    try:
        from psycopg.types.json import Jsonb
    except ImportError:
        return value

    return Jsonb(value)


def _normalize_repo_key(owner: str, name: str) -> tuple[str, str]:
    normalized_owner = owner.strip().lower()
    normalized_name = name.strip().lower()
    if not normalized_owner or not normalized_name:
        raise ValueError("owner and name are required")
    return normalized_owner, normalized_name


def _to_sql_value(key: str, value: Any) -> Any:
    if key in _JSON_COLUMNS and value is not None:
        return _json(value)
    return value


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


def _epic_result(row: Any) -> JSONDict:
    decoded = _normalize(row) or {}
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


def _message_result(row: Any) -> JSONDict:
    decoded = _normalize(row) or {}
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


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


__all__ = ["SupabaseStore"]
