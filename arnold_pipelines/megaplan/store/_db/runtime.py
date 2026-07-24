"""Runtime-side request and media mixins for DBStore."""

from __future__ import annotations

import hashlib
import uuid
from typing import Any, Sequence

from arnold_pipelines.megaplan.schemas import ExternalRequest, Image, SecondOpinion, SystemLog, ToolCall

from .common import _SOURCE_REFERENCE_PREFIX, _jb

class DBRuntimeMixin:
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
        idempotency_key: str | None = None,
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

    def mark_failed(self, request_id: str, *, error_details: dict,
        idempotency_key: str | None = None,
    ) -> ExternalRequest:
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

    def mark_orphaned(self, request_id: str, *, error_details: dict,
        idempotency_key: str | None = None,
    ) -> ExternalRequest:
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

    def _next_image_reference(self, epic_id: str, source: str) -> str:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT count(*) AS count FROM images WHERE epic_id = %s AND source = %s",
            [epic_id, source],
        ).fetchone()
        prefix = _SOURCE_REFERENCE_PREFIX.get(source, f"img_{source}")
        return f"{prefix}_{int(row['count']) + 1}"

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
        blob_backend: str | None = None,
        blob_id: str | None = None,
        blob_sha256: str | None = None,
        blob_size_bytes: int | None = None,
        content_type: str | None = None,
        idempotency_key: str | None = None,
    ) -> Image:
        conn = self._get_conn()
        img_id = str(uuid.uuid4())
        ref_key = reference_key or self._next_image_reference(epic_id, source)
        if active:
            self.deactivate_active_image_reference(epic_id, ref_key)
        row = conn.execute(
            """
            INSERT INTO images
                (id, epic_id, source, prompt, storage_url, quality, size,
                 reference_key, description, caption, in_body, active,
                 discord_attachment_id, blob_backend, blob_id, blob_sha256,
                 blob_size_bytes, content_type)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            [
                img_id, epic_id, source, prompt, storage_url, quality, size,
                ref_key, description, caption, in_body, active, discord_attachment_id,
                blob_backend, blob_id, blob_sha256, blob_size_bytes, content_type,
            ],
        ).fetchone()
        return Image(**row)

    def attach_image(
        self,
        *,
        epic_id: str,
        content: bytes,
        content_type: str,
        reference_key: str,
        source: str = "user_uploaded",
        prompt: str | None = None,
        quality: str | None = None,
        size: str | None = None,
        description: str | None = None,
        caption: str | None = None,
        in_body: bool = True,
        idempotency_key: str | None = None,
    ) -> Image:
        digest = hashlib.sha256(content).hexdigest()
        blob_id = f"{epic_id}/{reference_key}/{digest}"
        ref = self.blobs.put(blob_id, content, content_type=content_type)
        return self.create_image(
            epic_id=epic_id,
            source=source,
            storage_url=ref.storage_url or f"mp://blob/{blob_id}",
            prompt=prompt,
            quality=quality,
            size=size,
            reference_key=reference_key,
            description=description,
            caption=caption,
            in_body=in_body,
            active=True,
            blob_backend="supabase_storage",
            blob_id=blob_id,
            blob_sha256=digest,
            blob_size_bytes=len(content),
            content_type=content_type,
            idempotency_key=idempotency_key,
        )

    def resolve_image_reference(
        self,
        epic_id: str,
        reference: str,
        *,
        signed: bool = False,
        ttl: int = 3600,
    ) -> str | None:
        key = reference.removeprefix("mp://image/").removeprefix("image:")
        image = self.load_active_image_by_reference(epic_id, key)
        if image is None:
            return None
        if image.blob_id:
            return self.blobs.url(image.blob_id, signed=signed, ttl=ttl)
        return image.storage_url

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

    def update_image(self, image_id: str, *, idempotency_key: str | None = None,
        **changes: Any) -> Image:
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
        self, epic_id: str, reference_key: str,
        *,
        idempotency_key: str | None = None,
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
        idempotency_key: str | None = None,
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
        self, second_opinion_id: str, checklist_item_ids: Sequence[str],
        *,
        idempotency_key: str | None = None,
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

    def record_tool_call(
        self,
        *,
        turn_id: str,
        tool_name: str,
        operation_kind: str,
        arguments: dict,
        result: dict,
        duration_ms: int,
        idempotency_key: str | None = None,
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
        idempotency_key: str | None = None,
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

__all__ = ["DBRuntimeMixin"]
