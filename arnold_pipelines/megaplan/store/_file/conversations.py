from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, Sequence

from arnold_pipelines.megaplan._core.io import normalize_text
from arnold_pipelines.megaplan.schemas import BotTurn, Message, SystemLog, ToolCall
from arnold_pipelines.megaplan.schemas.base import utc_now

from ..base import HotContext, MessageSearchHit
from .common import _new_id, _parse_datetime, _utc_key


class FileConversationMixin:
    def _next_invocation_message_id(self, turn_id: str) -> str:
        count = sum(1 for row in self._messages() if row.bot_turn_id == turn_id and row.direction == "outbound")
        return f"inv_{turn_id}_{count + 1}"

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
        if idempotency_key is not None:
            for existing in self._messages():
                if existing.idempotency_key == idempotency_key:
                    return existing
        if synthesize_outbound_id and direction == "outbound" and discord_message_id is None and bot_turn_id:
            discord_message_id = self._next_invocation_message_id(bot_turn_id)
        message = Message(
            id=_new_id("msg"),
            epic_id=epic_id,
            conversation_id=conversation_id,
            idempotency_key=idempotency_key,
            direction=direction,
            content=content,
            sent_at=utc_now(),
            discord_message_id=discord_message_id,
            discord_reply_provenance=discord_reply_provenance,
            has_code_attachment=has_code_attachment,
            has_image_attachment=has_image_attachment,
            in_burst_with=list(in_burst_with or []),
            was_voice_message=was_voice_message,
            audio_storage_url=audio_storage_url,
            transcription_metadata=transcription_metadata,
            bot_turn_id=bot_turn_id,
        )
        self._save_model(self._message_path(message.id), message, journal_root=self.root)
        return message

    def load_message(self, message_id: str) -> Message | None:
        return self._load_model(self._message_path(message_id), Message)

    def load_messages(self, message_ids: Sequence[str]) -> list[Message]:
        by_id = {message.id: message for message in self._messages()}
        return [by_id[msg_id] for msg_id in message_ids if msg_id in by_id]

    def find_conversation_message_by_discord_id(
        self, conversation_id: str, discord_message_id: str
    ) -> Message | None:
        matches = [
            message
            for message in self._messages()
            if message.conversation_id == conversation_id
            and message.discord_message_id == discord_message_id
        ]
        matches.sort(key=lambda message: (_utc_key(message.sent_at), message.id), reverse=True)
        return matches[0] if matches else None

    def update_message(self, message_id: str, *, idempotency_key: str | None = None,
        **changes: Any) -> Message:
        current = self.load_message(message_id)
        if current is not None and current.direction == "inbound":
            for field in ("discord_message_id", "discord_reply_provenance"):
                if (
                    field in changes
                    and getattr(current, field) is not None
                    and changes[field] != getattr(current, field)
                ):
                    raise ValueError(f"immutable inbound Discord provenance field: {field}")
        return self._update_model(
            self._message_path(message_id),
            Message,
            journal_root=self.root,
            **changes,
        )

    def latest_outbound_message(self, *, epic_id: str | None = None) -> Message | None:
        messages = [row for row in self._messages() if row.direction == "outbound"]
        if epic_id is not None:
            messages = [row for row in messages if row.epic_id == epic_id]
        messages.sort(key=lambda row: (_utc_key(row.sent_at), row.id), reverse=True)
        return messages[0] if messages else None

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
        turn = BotTurn(
            id=_new_id("turn"),
            epic_id=epic_id,
            triggered_by_message_ids=list(triggered_by_message_ids),
            prompt_snapshot=prompt_snapshot,
            prompt_version=prompt_version,
            status="in_progress",
            state_at_turn=state_at_turn,
            model_version=model_version,
            started_at=utc_now(),
        )
        self._save_model(self._turn_path(turn.id), turn, journal_root=self.root)
        return turn

    def update_turn(self, turn_id: str, *, idempotency_key: str | None = None,
        **changes: Any) -> BotTurn:
        return self._update_model(self._turn_path(turn_id), BotTurn, journal_root=self.root, **changes)

    def find_abandoned_turns(self, older_than_seconds: int) -> list[BotTurn]:
        cutoff = datetime.now(UTC) - timedelta(seconds=older_than_seconds)
        return sorted(
            [
                turn
                for turn in self._turns()
                if turn.status == "in_progress" and turn.started_at <= cutoff
            ],
            key=lambda turn: (turn.started_at, turn.id),
        )

    def list_recent_turns(self, *, n: int = 10, epic_id: str | None = None) -> list[BotTurn]:
        turns = self._turns()
        if epic_id is not None:
            turns = [turn for turn in turns if turn.epic_id == epic_id]
        turns.sort(key=lambda turn: (_utc_key(turn.started_at), turn.id), reverse=True)
        return turns[:n]

    def search_messages(self, *, query: str, epic_id: str | None = None, limit: int = 20) -> list[MessageSearchHit]:
        needle = normalize_text(query)
        hits: list[tuple[int, Message]] = []
        for message in self._messages():
            if epic_id is not None and message.epic_id != epic_id:
                continue
            content = normalize_text(message.content)
            if needle in content:
                hits.append((content.count(needle), message))
        hits.sort(key=lambda item: (-item[0], item[1].id))
        return [
            MessageSearchHit.model_validate({**msg.model_dump(mode="json"), "rank": score})
            for score, msg in hits[:limit]
        ]

    def list_conversation_messages(
        self,
        conversation_id: str,
        *,
        limit: int = 20,
        exclude_ids: Sequence[str] = (),
    ) -> list[Message]:
        exclude = set(exclude_ids)
        rows = [
            message
            for message in self._messages()
            if message.conversation_id == conversation_id and message.id not in exclude
        ]
        rows.sort(key=lambda message: (_utc_key(message.sent_at), message.id))
        return rows[-limit:] if limit else []

    def record_tool_call(
        self,
        *,
        turn_id: str,
        tool_name: str,
        operation_kind: str,
        arguments: dict[str, Any],
        result: dict[str, Any],
        duration_ms: int,
        idempotency_key: str | None = None,
    ) -> ToolCall:
        tool_call = ToolCall(
            id=_new_id("tool"),
            turn_id=turn_id,
            tool_name=tool_name,
            operation_kind=operation_kind,
            arguments=arguments,
            result=result,
            duration_ms=duration_ms,
            called_at=utc_now(),
        )
        self._save_model(self._tool_call_path(tool_call.id), tool_call, journal_root=self.root)
        return tool_call

    def search_tool_calls_by(
        self,
        *,
        tool_name: str | None = None,
        epic_id: str | None = None,
        since: str | None = None,
        limit: int = 20,
    ) -> list[ToolCall]:
        since_dt = _parse_datetime(since)
        turns_by_id = {turn.id: turn for turn in self._turns()}
        matches: list[ToolCall] = []
        for row in self._tool_calls():
            if tool_name is not None and row.tool_name != tool_name:
                continue
            if epic_id is not None and turns_by_id.get(row.turn_id, BotTurn(id="", status="in_progress")).epic_id != epic_id:
                continue
            if since_dt and row.called_at < since_dt:
                continue
            matches.append(row)
        matches.sort(key=lambda row: (_utc_key(row.called_at), row.id), reverse=True)
        return matches[:limit]

    def log_system_event(
        self,
        *,
        level: str,
        category: str,
        event_type: str,
        message: str,
        details: dict[str, Any] | None = None,
        turn_id: str | None = None,
        epic_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> SystemLog:
        log = SystemLog(
            id=_new_id("log"),
            level=level,
            category=category,
            event_type=event_type,
            message=message,
            details=details or {},
            turn_id=turn_id,
            epic_id=epic_id,
            occurred_at=utc_now(),
        )
        self._save_model(self._system_log_path(log.id), log, journal_root=self.root)
        return log

    def load_hot_context(self, epic_id: str | None) -> HotContext:
        recent_messages = self.search_messages(query="", epic_id=epic_id, limit=10) if False else []
        messages = [msg for msg in self._messages() if msg.epic_id == epic_id]
        messages.sort(key=lambda msg: (_utc_key(msg.sent_at), msg.id), reverse=True)
        tool_calls = self.search_tool_calls_by(epic_id=epic_id, limit=10)
        feedback = self.list_feedback(epic_id=epic_id, active=True, limit=20)
        unresolved = [
            item
            for item in self.list_observations(resolved=False, limit=20)
            if item.epic_id == epic_id
        ]
        sprints = self.list_sprints_with_items(epic_id) if epic_id else []
        active_images = self.list_active_images(epic_id) if epic_id else []
        opinions = self.list_second_opinions(epic_id, limit=10) if epic_id else []
        all_pending = bool(sprints) and all(sprint.status == "pending" for sprint in sprints)
        return HotContext(
            epic=self.load_epic(epic_id) if epic_id else None,
            recent_messages=messages[:10],
            recent_tool_calls=tool_calls,
            active_feedback=feedback,
            unresolved_observations=unresolved,
            sprints=sprints,
            codebases=self.list_codebases(epic_id=epic_id),
            recent_code_artifacts=self.list_code_artifacts(epic_id=epic_id, limit=10),
            active_images=active_images,
            recent_second_opinions=opinions,
            all_sprints_pending_no_queued=all_pending and not any(sprint.status == "queued" for sprint in sprints),
        )

    def find_unprocessed_messages(self, epic_id: str, started_at: str, exclude_ids: Sequence[str]) -> list[Message]:
        start_dt = _parse_datetime(started_at)
        return sorted(
            [
                msg
                for msg in self._messages()
                if msg.epic_id == epic_id
                and msg.direction == "inbound"
                and msg.bot_turn_id is None
                and msg.id not in set(exclude_ids)
                and (start_dt is None or msg.sent_at >= start_dt)
            ],
            key=lambda msg: (msg.sent_at, msg.id),
        )
