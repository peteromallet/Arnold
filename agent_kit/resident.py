"""Resident-mode orchestration for push transports."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from resident_chat_runtime.coalescing import BurstBatch

from agent_kit.envelope import Envelope, Event
from agent_kit.epic_routing import select_epic_for_message
from agent_kit.ledger import Ledger, Reconciler
from agent_kit.loop import run_turn
from agent_kit.ports import Blob, JSONDict, Model, PushTransport, Store


DispatchCallable = Callable[[str, list[str]], Any | Awaitable[Any]]


@dataclass
class _Burst:
    message_ids: list[str] = field(default_factory=list)
    first_seen: float = 0.0
    timer: asyncio.TimerHandle | None = None


class MessageCoalescer:
    def __init__(
        self,
        dispatch: DispatchCallable,
        *,
        window_seconds: float = 10.0,
        hard_cap_seconds: float = 30.0,
        max_messages: int = 10,
    ) -> None:
        self.dispatch = dispatch
        self.window_seconds = window_seconds
        self.hard_cap_seconds = hard_cap_seconds
        self.max_messages = max_messages
        self.in_flight: set[str] = set()
        self._bursts: dict[str, _Burst] = {}

    def add(self, epic_id: str, message_id: str) -> None:
        loop = asyncio.get_running_loop()
        burst = self._bursts.get(epic_id)
        if burst is None:
            burst = _Burst(first_seen=loop.time())
            self._bursts[epic_id] = burst
        burst.message_ids.append(message_id)
        if burst.timer is not None:
            burst.timer.cancel()
        elapsed = loop.time() - burst.first_seen
        if len(burst.message_ids) >= self.max_messages or elapsed >= self.hard_cap_seconds:
            self.flush(epic_id)
            return
        remaining_hard_cap = max(0.0, self.hard_cap_seconds - elapsed)
        delay = min(self.window_seconds, remaining_hard_cap)
        burst.timer = loop.call_later(delay, self.flush, epic_id)

    def flush(self, epic_id: str) -> None:
        burst = self._bursts.pop(epic_id, None)
        if burst is None:
            return
        if burst.timer is not None:
            burst.timer.cancel()
        if epic_id in self.in_flight:
            return
        batch = BurstBatch(key=epic_id, items=tuple(burst.message_ids))
        asyncio.create_task(self._dispatch_batch(batch))

    async def _dispatch_batch(self, batch: BurstBatch[str, str]) -> None:
        await self._dispatch(batch.key, list(batch.items))

    async def _dispatch(self, epic_id: str, message_ids: list[str]) -> None:
        result = self.dispatch(epic_id, message_ids)
        if hasattr(result, "__await__"):
            await result  # type: ignore[misc]


class ResidentRunner:
    def __init__(
        self,
        *,
        store: Store,
        model: Model,
        model_id: str,
        transport: PushTransport,
        blob: Blob | None,
        ledger: Ledger,
        reconciler: Reconciler,
        status_debounce_seconds: float = 1.0,
    ) -> None:
        self.store = store
        self.model = model
        self.model_id = model_id
        self.transport = transport
        self.blob = blob
        self.ledger = ledger
        self.reconciler = reconciler
        self.status_debounce_seconds = status_debounce_seconds
        self.coalescer = MessageCoalescer(self.dispatch_turn)
        self.channel_ids: dict[str, str] = {}
        self.status_message_ids: dict[str, str] = {}
        self.turn_rows: dict[str, JSONDict] = {}
        self.current_activity: dict[str, str] = {}
        self.last_status_edit_at: dict[str, float] = {}
        self.mid_turn_notes: dict[str, list[str]] = {}
        self.previous_epic_by_channel: dict[str, str] = {}
        self._recovery_task: asyncio.Task | None = None

    def handle_transport_message(self, payload: JSONDict) -> None:
        message_ids = [str(message_id) for message_id in payload.get("message_ids") or []]
        if not message_ids:
            message_ids = [str(payload["message_id"])]
            payload["message_ids"] = message_ids
        message_id = str(payload.get("message_id") or message_ids[0])
        original_epic_id = str(payload["epic_id"])
        channel_id = payload.get("channel_id")
        rows = self.store.load_messages(message_ids)
        content = "\n".join(str(row.get("content") or "") for row in rows)
        decision = select_epic_for_message(
            content,
            self.store.list_epics(active_only=True, limit=50),
            previous_epic_id=self.previous_epic_by_channel.get(str(channel_id or "")),
        )
        if decision.needs_clarification:
            if channel_id is not None:
                self.transport.post_message(
                    str(channel_id),
                    "Which epic should I use for this?",
                )
            return
        epic_id = decision.epic_id or original_epic_id
        if epic_id != original_epic_id:
            for queued_message_id in message_ids:
                self.store.update_message(queued_message_id, epic_id=epic_id)
            payload["epic_id"] = epic_id
        if channel_id is not None:
            self.channel_ids[epic_id] = str(channel_id)
            self.previous_epic_by_channel[str(channel_id)] = epic_id
        if decision.switch_announcement and channel_id is not None:
            self.transport.post_message(str(channel_id), decision.switch_announcement)
        for queued_message_id in message_ids:
            self.coalescer.add(epic_id, queued_message_id)

    async def dispatch_turn(self, epic_id: str, message_ids: Sequence[str]) -> Envelope:
        self.coalescer.in_flight.add(epic_id)
        rows = self.store.load_messages(message_ids)
        try:
            turn_kwargs = {
                "epic_id": epic_id,
                "input": _messages_prompt(rows),
                "store": self.store,
                "model": self.model,
                "model_id": self.model_id,
                "on_event": self._on_event,
                "triggered_by_message_ids": list(message_ids),
                "recovered_input_messages": rows,
                "on_turn_start": self._on_turn_start,
                "mid_turn_message_check": self._mid_turn_check,
                "transport": self.transport,
                "blob": self.blob,
                "channel_id": self.channel_ids.get(epic_id),
            }
            if getattr(self.transport, "_loop", None) is not None:
                envelope = await asyncio.to_thread(run_turn, **turn_kwargs)
            else:
                envelope = run_turn(**turn_kwargs)
            self.turn_rows[envelope.turn_id] = self.store.update_turn(envelope.turn_id)
            self._edit_status(envelope.turn_id, force=True)
            return envelope
        finally:
            self.coalescer.in_flight.discard(epic_id)

    def start(self) -> None:
        self.transport.start(self.handle_transport_message)
        self._recovery_task = asyncio.create_task(self._recovery_loop())

    def stop(self) -> None:
        if self._recovery_task is not None:
            self._recovery_task.cancel()
        self.transport.stop()

    async def _recovery_loop(self) -> None:
        await self._run_recovery_once()
        while True:
            await asyncio.sleep(300)
            await self._run_recovery_once()

    async def _run_recovery_once(self) -> None:
        result = self.reconciler.run_once()
        for message_id in result.get("requeued_message_ids", []):
            row = self.store.load_message(str(message_id))
            if row and row.get("epic_id"):
                await self.dispatch_turn(str(row["epic_id"]), [str(message_id)])

    def _on_turn_start(self, turn: JSONDict) -> None:
        epic_id = str(turn["epic_id"])
        channel_id = self.channel_ids.get(epic_id, "")
        if self._quiet_status_mode():
            self.turn_rows[turn["id"]] = turn
            if channel_id:
                self.transport.set_typing(channel_id, True)
            return
        content = format_status(turn, [], turn.get("current_activity"), _now_ts())
        request_id, _ = self.ledger.record_pending(
            provider="discord",
            endpoint=f"POST /channels/{channel_id}/messages",
            request_summary={
                "channel_id": channel_id,
                "content_preview": content[:100],
                "status": "turn_start",
            },
            request_body={"content": content},
            turn_id=turn["id"],
            system_seq=0,
        )
        try:
            response = self.transport.post_message(channel_id, content)
        except Exception as exc:
            self.ledger.mark_failed(
                request_id,
                {"error_type": type(exc).__name__, "message": str(exc)},
            )
            raise
        message_id = str(
            response.get("discord_message_id")
            or response.get("id")
            or response.get("message_id")
            or ""
        )
        self.ledger.mark_confirmed(request_id, message_id or None, response)
        updated = self.store.update_turn(turn["id"], status_message_id=message_id)
        self.turn_rows[turn["id"]] = updated
        self.status_message_ids[turn["id"]] = message_id

    def _quiet_status_mode(self) -> bool:
        return bool(getattr(self.transport, "quiet_status_updates", False)) or getattr(
            self.transport, "_loop", None
        ) is not None

    def _on_event(self, event: Event) -> None:
        if event.kind not in {"tool_call", "activity"}:
            return
        turn_id = _event_turn_id(event)
        if turn_id is None and len(self.turn_rows) == 1:
            turn_id = next(iter(self.turn_rows))
        if turn_id is None or turn_id not in self.turn_rows:
            return
        if event.kind == "activity" and event.text:
            self.current_activity[turn_id] = event.text
        if not self._status_edit_due(turn_id):
            return
        self._edit_status(turn_id)

    def _mid_turn_check(self, turn: JSONDict) -> list[JSONDict] | None:
        rows = self.store.find_unprocessed_messages(
            epic_id=turn["epic_id"],
            started_at=turn["started_at"],
            exclude_ids=turn.get("triggered_by_message_ids") or [],
        )
        if not rows:
            return None
        turn_id = str(turn["id"])
        notes = self.mid_turn_notes.setdefault(turn_id, [])
        for row in rows:
            notes.append(f'📥 Received "{_preview(row.get("content"))}"')
        self._edit_status(turn_id, force=True)
        return rows

    def _status_edit_due(self, turn_id: str) -> bool:
        now = time.monotonic()
        last = self.last_status_edit_at.get(turn_id, 0.0)
        if now - last < self.status_debounce_seconds:
            return False
        self.last_status_edit_at[turn_id] = now
        return True

    def _edit_status(self, turn_id: str, *, force: bool = False) -> None:
        if force:
            self.last_status_edit_at[turn_id] = time.monotonic()
        turn = self.turn_rows.get(turn_id)
        status_message_id = self.status_message_ids.get(turn_id)
        if not turn or not status_message_id:
            return
        hot_context = self.store.load_hot_context(str(turn["epic_id"]))
        recent_tool_calls = hot_context.get("recent_tool_calls", [])[-3:]
        content = format_status(
            turn,
            recent_tool_calls,
            self.current_activity.get(turn_id) or turn.get("current_activity"),
            _now_ts(),
        )
        notes = self.mid_turn_notes.get(turn_id, [])
        if notes:
            content = content + "\n" + "\n".join(notes[-3:])
        self.transport.edit_message(
            self.channel_ids.get(str(turn["epic_id"]), ""),
            status_message_id,
            content,
        )


def format_status(
    turn_row: JSONDict,
    recent_tool_calls: Sequence[JSONDict],
    current_activity: str | None,
    last_call_ts: int | float | None,
) -> str:
    ts = int(last_call_ts or _now_ts())
    tool_count = len(recent_tool_calls)
    status = turn_row.get("status")
    if status == "completed":
        return f"✅ Done. {tool_count} tool calls. <t:{ts}:R>"
    if status == "failed":
        reason = str(turn_row.get("reasoning") or "unknown error")
        return f"❌ Failed. {reason}"

    lines = [
        "Planning turn in progress.",
        f"Activity: {current_activity or 'Thinking'}",
        f"Tool calls: {tool_count}",
    ]
    if recent_tool_calls:
        names = [
            str(call.get("tool_name") or call.get("name") or "tool")
            for call in recent_tool_calls[-3:]
        ]
        lines.append("Recent: " + ", ".join(names))
    lines.append(f"Updated <t:{ts}:R>")
    return "\n".join(lines)


def _messages_prompt(message_rows: Sequence[JSONDict]) -> str:
    ordered = sorted(message_rows, key=lambda row: row.get("sent_at") or "")
    return "\n\n".join(str(row.get("content") or "") for row in ordered)


def _preview(value: Any) -> str:
    text = str(value or "")
    if len(text) <= 60:
        return text
    return text[:60] + "..."


def _now_ts() -> int:
    return int(datetime.now(UTC).timestamp())


def _event_turn_id(event: Event) -> str | None:
    value = event.details.get("turn_id") if event.details else None
    return str(value) if value else None


__all__ = ["MessageCoalescer", "ResidentRunner", "format_status"]
