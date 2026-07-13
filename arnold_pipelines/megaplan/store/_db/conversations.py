"""Conversation and turn mixins for DBStore."""

from __future__ import annotations

import uuid
from typing import Any, Sequence

from arnold_pipelines.megaplan.schemas import BotTurn, CodeArtifact, Codebase, Epic, Feedback, Image, Message, SecondOpinion, ToolCall
from arnold_pipelines.megaplan.store.base import HotContext, MessageSearchHit, RevisionConflict

from .common import _OBSERVATION_KINDS, _jb

class DBConversationMixin:
    def _next_invocation_message_id(self, turn_id: str) -> str:
        conn = self._get_conn()
        row = conn.execute(
            """
            SELECT count(*) AS count
            FROM messages
            WHERE bot_turn_id = %s AND direction = 'outbound'
            """,
            [turn_id],
        ).fetchone()
        return f"inv_{turn_id}_{int(row['count']) + 1}"

    def create_message(
        self,
        *,
        epic_id: str | None,
        direction: str,
        content: str,
        discord_message_id: str | None = None,
        discord_reply_provenance: dict[str, Any] | None = None,
        bot_turn_id: str | None = None,
        has_code_attachment: bool = False,
        has_image_attachment: bool = False,
        in_burst_with: Sequence[str] | None = None,
        was_voice_message: bool = False,
        audio_storage_url: str | None = None,
        transcription_metadata: dict[str, Any] | None = None,
        synthesize_outbound_id: bool = True,
        conversation_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> Message:
        conn = self._get_conn()
        if synthesize_outbound_id and direction == "outbound" and discord_message_id is None and bot_turn_id:
            discord_message_id = self._next_invocation_message_id(bot_turn_id)
        if discord_message_id is not None:
            existing = conn.execute(
                "SELECT * FROM messages WHERE discord_message_id = %s",
                [discord_message_id],
            ).fetchone()
            if existing is not None:
                changes: dict[str, Any] = {}
                if conversation_id is not None and existing["conversation_id"] is None:
                    changes["conversation_id"] = conversation_id
                if idempotency_key is not None and existing["idempotency_key"] is None:
                    changes["idempotency_key"] = idempotency_key
                if bot_turn_id is not None and existing["bot_turn_id"] is None:
                    changes["bot_turn_id"] = bot_turn_id
                if changes:
                    set_parts = [f"{column} = %s" for column in changes]
                    existing = conn.execute(
                        f"UPDATE messages SET {', '.join(set_parts)} WHERE id = %s RETURNING *",
                        [*changes.values(), existing["id"]],
                    ).fetchone()
                return Message(**existing)
        row = conn.execute(
            """
            INSERT INTO messages (
                id, epic_id, conversation_id, idempotency_key, direction, content, discord_message_id,
                discord_reply_provenance, bot_turn_id,
                has_code_attachment, has_image_attachment, in_burst_with,
                was_voice_message, audio_storage_url, transcription_metadata
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (idempotency_key) WHERE idempotency_key IS NOT NULL DO UPDATE
            SET idempotency_key = EXCLUDED.idempotency_key
            RETURNING *
            """,
            [
                str(uuid.uuid4()), epic_id, conversation_id, idempotency_key,
                direction, content, discord_message_id, _jb(discord_reply_provenance),
                bot_turn_id, has_code_attachment, has_image_attachment,
                _jb(list(in_burst_with) if in_burst_with is not None else None),
                was_voice_message, audio_storage_url, _jb(transcription_metadata),
            ],
        ).fetchone()
        return Message(**row)

    def load_message(self, message_id: str) -> Message | None:
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM messages WHERE id = %s", [message_id]).fetchone()
        return Message(**row) if row else None

    def load_messages(self, message_ids: Sequence[str]) -> list[Message]:
        conn = self._get_conn()
        if not message_ids:
            return []
        rows = conn.execute(
            "SELECT * FROM messages WHERE id = ANY(%s::text[]) ORDER BY array_position(%s::text[], id)",
            [list(message_ids), list(message_ids)],
        ).fetchall()
        return [Message(**row) for row in rows]

    def find_conversation_message_by_discord_id(
        self, conversation_id: str, discord_message_id: str
    ) -> Message | None:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM messages WHERE conversation_id = %s AND discord_message_id = %s",
            [conversation_id, discord_message_id],
        ).fetchone()
        return Message(**row) if row else None

    def update_message(self, message_id: str, *, idempotency_key: str | None = None,
        **changes: Any) -> Message:
        conn = self._get_conn()
        current = conn.execute("SELECT * FROM messages WHERE id = %s", [message_id]).fetchone()
        if current is not None and current["direction"] == "inbound":
            for field in ("discord_message_id", "discord_reply_provenance"):
                if field in changes and current[field] is not None and changes[field] != current[field]:
                    raise RevisionConflict(f"immutable inbound Discord provenance field: {field}")
        if not changes:
            if current is None:
                raise RevisionConflict(f"Message {message_id!r} not found")
            return Message(**current)
        set_parts = [f"{k} = %s" for k in changes]
        values = list(changes.values()) + [message_id]
        row = conn.execute(
            f"UPDATE messages SET {', '.join(set_parts)} WHERE id = %s RETURNING *",
            values,
        ).fetchone()
        if row is None:
            raise RevisionConflict(f"Message {message_id!r} not found")
        return Message(**row)

    def latest_outbound_message(self, *, epic_id: str | None = None) -> Message | None:
        conn = self._get_conn()
        if epic_id is not None:
            row = conn.execute(
                "SELECT * FROM messages WHERE direction = 'outbound' AND epic_id = %s ORDER BY sent_at DESC LIMIT 1",
                [epic_id],
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM messages WHERE direction = 'outbound' ORDER BY sent_at DESC LIMIT 1",
            ).fetchone()
        return Message(**row) if row else None

    def search_messages(
        self,
        *,
        query: str,
        epic_id: str | None = None,
        limit: int = 20,
    ) -> list[MessageSearchHit]:
        conn = self._get_conn()
        conditions = [
            "(to_tsvector('english', m.content) @@ websearch_to_tsquery('english', %s) "
            "OR lower(m.content) LIKE lower(%s))"
        ]
        values: list[Any] = [query, f"%{query}%"]
        if epic_id is not None:
            conditions.append("m.epic_id = %s")
            values.append(epic_id)
        where = " AND ".join(conditions)
        values = [query, query, *values, limit]
        rows = conn.execute(
            f"""
            SELECT m.*,
                   ts_headline('english', m.content, websearch_to_tsquery('english', %s)) AS snippet,
                   ts_rank(to_tsvector('english', m.content), websearch_to_tsquery('english', %s)) AS rank
            FROM messages m
            WHERE {where}
            ORDER BY rank DESC
            LIMIT %s
            """,
            values,
        ).fetchall()
        return [MessageSearchHit(**row) for row in rows]

    def list_conversation_messages(
        self,
        conversation_id: str,
        *,
        limit: int = 20,
        exclude_ids: Sequence[str] = (),
    ) -> list[Message]:
        conn = self._get_conn()
        rows = conn.execute(
            """
            SELECT * FROM (
                SELECT * FROM messages
                WHERE conversation_id = %s
                  AND NOT (id = ANY(%s::text[]))
                ORDER BY sent_at DESC, id DESC
                LIMIT %s
            ) recent
            ORDER BY sent_at ASC, id ASC
            """,
            [conversation_id, list(exclude_ids), limit],
        ).fetchall()
        return [Message(**row) for row in rows]

    def find_unprocessed_messages(
        self,
        epic_id: str,
        started_at: str,
        exclude_ids: Sequence[str],
    ) -> list[Message]:
        conn = self._get_conn()
        rows = conn.execute(
            """
            SELECT * FROM messages m
            WHERE m.epic_id = %s
              AND m.direction = 'inbound'
              AND m.bot_turn_id IS NULL
              AND m.sent_at >= %s::timestamptz
              AND NOT (m.id = ANY(%s::text[]))
            ORDER BY m.sent_at, m.id
            """,
            [epic_id, started_at, list(exclude_ids)],
        ).fetchall()
        return [Message(**row) for row in rows]

    def create_turn(
        self,
        *,
        epic_id: str | None,
        triggered_by_message_ids: Sequence[str],
        prompt_snapshot: dict[str, Any] | None = None,
        prompt_version: str | None = None,
        state_at_turn: dict[str, Any] | None = None,
        model_version: str | None = None,
        idempotency_key: str | None = None,
    ) -> BotTurn:
        conn = self._get_conn()
        row = conn.execute(
            """
            INSERT INTO bot_turns (
                id, epic_id, triggered_by_message_ids, prompt_snapshot,
                prompt_version, state_at_turn, model_version, status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'in_progress')
            RETURNING *
            """,
            [
                str(uuid.uuid4()), epic_id,
                _jb(list(triggered_by_message_ids)),
                _jb(prompt_snapshot), prompt_version,
                _jb(state_at_turn), model_version,
            ],
        ).fetchone()
        return BotTurn(**row)

    def update_turn(self, turn_id: str, *, idempotency_key: str | None = None,
        **changes: Any) -> BotTurn:
        conn = self._get_conn()
        if not changes:
            row = conn.execute("SELECT * FROM bot_turns WHERE id = %s", [turn_id]).fetchone()
            if row is None:
                raise RevisionConflict(f"Turn {turn_id!r} not found")
            return BotTurn(**row)
        jsonb_turn_cols = frozenset({
            "triggered_by_message_ids", "prompt_snapshot", "state_at_turn",
            "warnings_issued",
        })
        set_parts = [f"{k} = %s" for k in changes]
        if changes.get("status") in {"completed", "failed", "abandoned"} and "completed_at" not in changes:
            set_parts.append("completed_at = now()")
        values = [_jb(v) if k in jsonb_turn_cols else v for k, v in changes.items()]
        values.append(turn_id)
        row = conn.execute(
            f"UPDATE bot_turns SET {', '.join(set_parts)} WHERE id = %s RETURNING *",
            values,
        ).fetchone()
        if row is None:
            raise RevisionConflict(f"Turn {turn_id!r} not found")
        return BotTurn(**row)

    def find_abandoned_turns(self, older_than_seconds: int) -> list[BotTurn]:
        conn = self._get_conn()
        rows = conn.execute(
            """
            SELECT * FROM bot_turns
            WHERE status = 'in_progress'
              AND started_at < now() - make_interval(secs => %s)
            ORDER BY started_at
            """,
            [older_than_seconds],
        ).fetchall()
        return [BotTurn(**row) for row in rows]

    def list_recent_turns(
        self,
        *,
        n: int = 10,
        epic_id: str | None = None,
    ) -> list[BotTurn]:
        conn = self._get_conn()
        if epic_id is not None:
            rows = conn.execute(
                "SELECT * FROM bot_turns WHERE epic_id = %s ORDER BY started_at DESC LIMIT %s",
                [epic_id, n],
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM bot_turns ORDER BY started_at DESC LIMIT %s",
                [n],
            ).fetchall()
        return [BotTurn(**row) for row in rows]

    def load_hot_context(self, epic_id: str | None) -> HotContext:
        if epic_id is None:
            return HotContext()
        conn = self._get_conn()
        obs_kinds = ["friction", "ambiguity", "tool_failure", "confusion", "pattern_noticed"]
        with conn.transaction():
            epic_row = conn.execute(
                "SELECT * FROM epics WHERE id = %s", [epic_id]
            ).fetchone()
            msg_rows = conn.execute(
                "SELECT * FROM messages WHERE epic_id = %s ORDER BY sent_at DESC LIMIT 50",
                [epic_id],
            ).fetchall()
            tc_rows = conn.execute(
                """
                SELECT tc.* FROM tool_calls tc
                JOIN bot_turns bt ON tc.turn_id = bt.id
                WHERE bt.epic_id = %s
                ORDER BY tc.called_at DESC LIMIT 20
                """,
                [epic_id],
            ).fetchall()
            af_rows = conn.execute(
                """
                SELECT * FROM feedback
                WHERE epic_id = %s AND resolved = false AND kind != ANY(%s)
                ORDER BY created_at DESC
                """,
                [epic_id, obs_kinds],
            ).fetchall()
            uo_rows = conn.execute(
                """
                SELECT * FROM feedback
                WHERE epic_id = %s AND resolved = false AND kind = ANY(%s)
                ORDER BY created_at DESC
                """,
                [epic_id, obs_kinds],
            ).fetchall()
            sprint_rows = conn.execute(
                """
                SELECT s.*,
                       si.id                    AS si_id,
                       si.sprint_id             AS si_sprint_id,
                       si.content               AS si_content,
                       si.estimated_complexity  AS si_estimated_complexity,
                       si.status                AS si_status,
                       si.source_section        AS si_source_section,
                       si.position              AS si_position,
                       si.created_at            AS si_created_at
                FROM sprints s
                LEFT JOIN sprint_items si ON si.sprint_id = s.id
                WHERE s.epic_id = %s
                ORDER BY s.sprint_number, si.position
                """,
                [epic_id],
            ).fetchall()
            cb_rows = conn.execute(
                "SELECT * FROM codebases WHERE associated_epic_id = %s",
                [epic_id],
            ).fetchall()
            ca_rows = conn.execute(
                "SELECT * FROM code_artifacts WHERE epic_id = %s ORDER BY created_at DESC LIMIT 10",
                [epic_id],
            ).fetchall()
            img_rows = conn.execute(
                "SELECT * FROM images WHERE epic_id = %s AND active = true ORDER BY created_at DESC",
                [epic_id],
            ).fetchall()
            so_rows = conn.execute(
                "SELECT * FROM second_opinions WHERE epic_id = %s ORDER BY requested_at DESC LIMIT 10",
                [epic_id],
            ).fetchall()

        sprints_with_items = self._group_sprint_rows(sprint_rows)
        statuses = {s.status for s in sprints_with_items}
        all_sprints_pending_no_queued = (
            bool(sprints_with_items)
            and "queued" not in statuses
            and all(s.status == "pending" for s in sprints_with_items)
        )
        return HotContext(
            epic=Epic(**epic_row) if epic_row else None,
            recent_messages=[Message(**r) for r in msg_rows],
            recent_tool_calls=[ToolCall(**r) for r in tc_rows],
            active_feedback=[Feedback(**r) for r in af_rows],
            unresolved_observations=[Feedback(**r) for r in uo_rows],
            sprints=sprints_with_items,
            codebases=[Codebase(**r) for r in cb_rows],
            recent_code_artifacts=[CodeArtifact(**r) for r in ca_rows],
            active_images=[Image(**r) for r in img_rows],
            recent_second_opinions=[SecondOpinion(**r) for r in so_rows],
            all_sprints_pending_no_queued=all_sprints_pending_no_queued,
        )

__all__ = ["DBConversationMixin"]
