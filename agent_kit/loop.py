"""Transport-agnostic turn loop entry points."""

from __future__ import annotations

import asyncio
import json
from threading import Event as ThreadingEvent
from typing import Callable, Sequence
from uuid import uuid4

from agent_kit import body
from agent_kit.envelope import Envelope, EnvelopeError, Event, StateDelta
from agent_kit.ledger import Ledger
from agent_kit.logging import log
from agent_kit.ports import Blob, JSONDict, Model, ProviderError, PushTransport, Store
from agent_kit.tool_kit import ToolContext, registry
import agent_kit.tools.communication  # noqa: F401
import agent_kit.tools.editorial  # noqa: F401
import agent_kit.tools.editorial_reads  # noqa: F401
import agent_kit.tools.images  # noqa: F401


ANTHROPIC_MESSAGES_ENDPOINT = "POST /v1/messages"
ANTHROPIC_MAX_TOKENS = 4096
DEFAULT_PROMPT_VERSION = "sprint1a"


def run_turn(
    *,
    epic_id: str | None = None,
    input: str,
    store: Store,
    model: Model,
    model_id: str = "claude-opus-4-7",
    on_event=None,
    cancel_event: ThreadingEvent | None = None,
    triggered_by_message_ids: Sequence[str] | None = None,
    recovered_input_messages: Sequence[JSONDict] | None = None,
    on_turn_start: Callable[[JSONDict], None] | None = None,
    mid_turn_message_check: Callable[[JSONDict], list[JSONDict] | None] | None = None,
    transport: PushTransport | None = None,
    blob: Blob | None = None,
    channel_id: str | None = None,
) -> Envelope:
    holder_id = f"turn_holder_{uuid4().hex}"
    active_epic_id: str | None = epic_id
    lock_acquired = False
    if epic_id is not None:
        lock_acquired = store.acquire_epic_lock(epic_id, holder_id=holder_id, timeout_seconds=60)
        if not lock_acquired:
            log(
                store,
                "warn",
                "system",
                "epic_lock_contended",
                "Epic is already locked by another turn.",
                epic_id=active_epic_id,
            )
            return Envelope(
                turn_id=f"turn_lock_{uuid4().hex}",
                epic_id=active_epic_id,
                epic_state_before="unknown",
                epic_state_after="unknown",
                reply="",
                state_delta=StateDelta(),
                outcome="errored",
                error=EnvelopeError(
                    code="epic_locked",
                    message="Epic is already locked by another turn.",
                    retryable=True,
                ),
            )

    turn = None
    events: list[Event] = []
    reply_buffer: list[str] = []
    context: ToolContext | None = None
    state_before = "unknown"
    try:
        if recovered_input_messages is not None:
            initial_user_prompt = _messages_prompt(recovered_input_messages)
        else:
            initial_user_prompt = input

        if triggered_by_message_ids is None:
            inbound = store.create_message(
                epic_id=active_epic_id,
                direction="inbound",
                content=input,
                discord_message_id=f"inv_in_{uuid4().hex}",
            )
            turn_message_ids = [inbound["id"]]
        else:
            turn_message_ids = list(triggered_by_message_ids)

        hot_context = (
            store.load_hot_context(active_epic_id)
            if active_epic_id is not None
            else {"epic": None, "recent_messages": [], "recent_tool_calls": []}
        )
        epic = hot_context.get("epic") or {}
        state_before = epic.get("state", "unknown")
        turn = store.create_turn(
            epic_id=active_epic_id,
            triggered_by_message_ids=turn_message_ids,
            prompt_snapshot={
                "input": initial_user_prompt,
                "hot_context": _summarize_hot_context(hot_context),
            },
            prompt_version=DEFAULT_PROMPT_VERSION,
            state_at_turn={"epic_state": state_before},
            model_version=model_id,
        )
        if on_turn_start is not None:
            on_turn_start(turn)
        ledger = Ledger(store)
        context = ToolContext(
            store=store,
            turn_id=turn["id"],
            events=events,
            on_event=on_event,
            reply_buffer=reply_buffer,
            metadata={
                "epic_id": active_epic_id,
                "outcome": "completed",
                "questions": [],
                "channel_id": channel_id,
            },
            transport=transport,
            blob=blob,
        )
        if triggered_by_message_ids is None:
            context.metadata["inbound_message_id"] = inbound["id"]

        if _is_cancelled(cancel_event):
            return _abort_turn(store, turn, active_epic_id, state_before, events, reply_buffer)

        model_call_seq = 0
        messages = [{"role": "user", "content": initial_user_prompt}]
        while True:
            model_call_seq += 1
            tool_definitions = list(registry.definitions())
            request_body = {
                "model": model_id,
                "messages": list(messages),
                "tools": tool_definitions,
                "max_tokens": ANTHROPIC_MAX_TOKENS,
            }
            request_summary = {
                "model": model_id,
                "message_count": len(messages),
                "tool_names": [definition["name"] for definition in tool_definitions],
                "input_length": len(input),
                "system_seq": model_call_seq,
            }
            request_id, idempotency_key = ledger.record_pending(
                provider="anthropic",
                endpoint=ANTHROPIC_MESSAGES_ENDPOINT,
                request_summary=request_summary,
                request_body=request_body,
                turn_id=turn["id"],
                system_seq=model_call_seq,
            )
            try:
                result = model.complete_turn(
                    model_id=model_id,
                    messages=messages,
                    tools=tool_definitions,
                    hot_context=hot_context,
                    idempotency_key=idempotency_key,
                )
            except ProviderError as exc:
                ledger.mark_failed(request_id, exc.error_details)
                log(
                    store,
                    "error",
                    "llm",
                    "provider_error",
                    "Model provider returned an error.",
                    turn_id=turn["id"],
                    epic_id=active_epic_id,
                    error_details=exc.error_details,
                    provider_request_id=exc.provider_request_id,
                )
                store.update_turn(turn["id"], status="failed", reasoning=str(exc.error_details))
                return _envelope(
                    turn_id=turn["id"],
                    epic_id=active_epic_id,
                    state_before=state_before,
                    state_after=state_before,
                    reply_buffer=reply_buffer,
                    events=events,
                    outcome="errored",
                    error=EnvelopeError(
                        code="provider_error",
                        message="Model provider returned an error.",
                        retryable=True,
                    ),
                )
            except Exception as exc:
                log(
                    store,
                    "error",
                    "llm",
                    "transport_error",
                    "Model transport or SDK call failed.",
                    turn_id=turn["id"],
                    epic_id=active_epic_id,
                    error_type=type(exc).__name__,
                )
                store.update_turn(turn["id"], status="failed", reasoning=str(exc))
                return _envelope(
                    turn_id=turn["id"],
                    epic_id=active_epic_id,
                    state_before=state_before,
                    state_after=state_before,
                    reply_buffer=reply_buffer,
                    events=events,
                    outcome="errored",
                    error=EnvelopeError(
                        code="model_error",
                        message=str(exc),
                        retryable=True,
                    ),
                )

            ledger.mark_confirmed(
                request_id,
                result.provider_request_id,
                result.response_summary,
            )
            store.update_turn(
                turn["id"],
                prompt_snapshot=request_summary,
                reasoning=result.reasoning,
                model_version=model_id,
            )

            if _is_cancelled(cancel_event):
                return _abort_turn(store, turn, active_epic_id, state_before, events, reply_buffer)

            if result.tool_requests:
                reenter_model_loop = False
                for tool_request in result.tool_requests:
                    if _is_cancelled(cancel_event):
                        return _abort_turn(
                            store,
                            turn,
                            active_epic_id,
                            state_before,
                            events,
                            reply_buffer,
                        )
                    updated_turn = None
                    if tool_request.name == "send_message":
                        # Resident mode gives late inbound messages one more model pass before posting.
                        updated_turn = _append_mid_turn_messages(
                            store=store,
                            turn=turn,
                            messages=messages,
                            mid_turn_message_check=mid_turn_message_check,
                        )
                    if updated_turn is not None:
                        turn = updated_turn
                        reenter_model_loop = True
                        break
                    try:
                        invocation = registry.invoke(
                            tool_request.name,
                            context,
                            tool_request.arguments,
                        )
                        active_epic_id = context.metadata.get("epic_id", active_epic_id)
                    except Exception as exc:
                        log(
                            store,
                            "error",
                            "tool",
                            "tool_call_failed",
                            "Tool invocation failed.",
                            turn_id=turn["id"],
                            epic_id=active_epic_id,
                            tool_name=tool_request.name,
                            error_type=type(exc).__name__,
                        )
                        store.update_turn(turn["id"], status="failed", reasoning=str(exc))
                        return _envelope(
                            turn_id=turn["id"],
                            epic_id=active_epic_id,
                            state_before=state_before,
                            state_after=state_before,
                            reply_buffer=reply_buffer,
                            events=events,
                            outcome="errored",
                            error=EnvelopeError(
                                code="tool_error",
                                message=str(exc),
                                retryable=False,
                            ),
                        )
                    messages.append(
                        {
                            "role": "user",
                            "content": _tool_result_content(
                                tool_request.name,
                                invocation.result,
                            ),
                        }
                    )
                    if context.metadata.get("stop_requested"):
                        questions = list(context.metadata.get("questions", []))
                        store.update_turn(turn["id"], status="completed")
                        _log_epic_outline_if_needed(store, active_epic_id, turn, events)
                        return _envelope(
                            turn_id=turn["id"],
                            epic_id=active_epic_id,
                            state_before=state_before,
                            state_after=state_before,
                            reply_buffer=reply_buffer,
                            events=events,
                            outcome="blocked_on_caller",
                            questions=questions,
                        )
                if reenter_model_loop:
                    continue
                continue

            if result.final_text is not None:
                final_text = result.final_text or "Done."
                updated_turn = _append_mid_turn_messages(
                    store=store,
                    turn=turn,
                    messages=messages,
                    mid_turn_message_check=mid_turn_message_check,
                )
                if updated_turn is not None:
                    turn = updated_turn
                    continue
                if not reply_buffer:
                    registry.invoke(
                        "send_message",
                        context,
                        {"content": final_text},
                    )
                    active_epic_id = context.metadata.get("epic_id", active_epic_id)
                store.update_turn(turn["id"], status="completed")
                _log_epic_outline_if_needed(store, active_epic_id, turn, events)
                return _envelope(
                    turn_id=turn["id"],
                    epic_id=active_epic_id,
                    state_before=state_before,
                    state_after=state_before,
                    reply_buffer=reply_buffer,
                    events=events,
                    outcome="completed",
                )

            store.update_turn(turn["id"], status="failed", reasoning="model returned no action")
            return _envelope(
                turn_id=turn["id"],
                epic_id=active_epic_id,
                state_before=state_before,
                state_after=state_before,
                reply_buffer=reply_buffer,
                events=events,
                outcome="errored",
                error=EnvelopeError(
                    code="empty_model_response",
                    message="Model returned neither final text nor tool requests.",
                    retryable=True,
                ),
            )
    finally:
        if lock_acquired and epic_id is not None:
            store.release_epic_lock(epic_id, holder_id=holder_id)


async def arun_turn(*args, **kwargs) -> Envelope:
    return await asyncio.to_thread(run_turn, *args, **kwargs)


__all__ = ["Envelope", "arun_turn", "run_turn"]


def _abort_turn(
    store: Store,
    turn: dict,
    epic_id: str | None,
    state_before: str,
    events: list[Event],
    reply_buffer: list[str],
) -> Envelope:
    store.update_turn(turn["id"], status="abandoned")
    return _envelope(
        turn_id=turn["id"],
        epic_id=epic_id,
        state_before=state_before,
        state_after=state_before,
        reply_buffer=reply_buffer,
        events=events,
        outcome="aborted",
    )


def _envelope(
    *,
    turn_id: str,
    epic_id: str | None,
    state_before: str,
    state_after: str,
    reply_buffer: list[str],
    events: list[Event],
    outcome: str,
    questions: list[str] | None = None,
    error: EnvelopeError | None = None,
) -> Envelope:
    return Envelope(
        turn_id=turn_id,
        epic_id=epic_id,
        epic_state_before=state_before,
        epic_state_after=state_after,
        reply="\n\n".join(reply_buffer),
        state_delta=StateDelta(),
        questions=questions or [],
        events=events,
        tool_call_count=sum(1 for event in events if event.tool_call_id),
        outcome=outcome,  # type: ignore[arg-type]
        error=error,
    )


def _is_cancelled(cancel_event: ThreadingEvent | None) -> bool:
    return bool(cancel_event and cancel_event.is_set())


def _messages_prompt(message_rows: Sequence[JSONDict]) -> str:
    ordered = sorted(message_rows, key=lambda row: row.get("sent_at") or "")
    return "\n\n".join(str(row.get("content") or "") for row in ordered)


def _append_mid_turn_messages(
    *,
    store: Store,
    turn: JSONDict,
    messages: list[JSONDict],
    mid_turn_message_check: Callable[[JSONDict], list[JSONDict] | None] | None,
) -> JSONDict | None:
    if mid_turn_message_check is None:
        return None

    new_rows = mid_turn_message_check(turn) or []
    existing_ids = list(turn.get("triggered_by_message_ids") or [])
    existing_id_set = set(existing_ids)
    fresh_rows = [
        row for row in new_rows
        if row.get("id") is not None and row.get("id") not in existing_id_set
    ]
    if not fresh_rows:
        return None

    ordered = sorted(fresh_rows, key=lambda row: row.get("sent_at") or "")
    new_ids = [str(row["id"]) for row in ordered]
    messages.append(
        {
            "role": "user",
            "content": _mid_turn_prompt(ordered),
        }
    )
    return store.update_turn(
        turn["id"],
        triggered_by_message_ids=existing_ids + new_ids,
    )


def _mid_turn_prompt(message_rows: Sequence[JSONDict]) -> str:
    lines = ["[Mid-turn messages — arrived after this turn started]"]
    for row in message_rows:
        content = str(row.get("content") or "")
        sent_at = row.get("sent_at")
        prefix = f"- {sent_at}: " if sent_at else "- "
        lines.append(prefix + content)
    return "\n".join(lines)


def _tool_result_content(tool_name: str, result: JSONDict) -> JSONDict | list[JSONDict]:
    if result.get("media_type") and result.get("image_bytes_b64"):
        metadata = {
            key: value
            for key, value in result.items()
            if key != "image_bytes_b64"
        }
        return [
            {
                "type": "text",
                "text": f"Tool result from {tool_name}:",
            },
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": result["media_type"],
                    "data": result["image_bytes_b64"],
                },
            },
            {
                "type": "text",
                "text": json.dumps(metadata, sort_keys=True),
            },
        ]
    return {
        "tool_name": tool_name,
        "result": result,
    }


def _log_epic_outline_if_needed(
    store: Store,
    active_epic_id: str | None,
    turn: JSONDict,
    events: list[Event],
) -> None:
    if active_epic_id is None:
        return
    if not any(
        event.name in {"create_epic", "edit_epic", "revert"}
        and event.tool_call_id is not None
        for event in events
    ):
        return
    epic = store.load_epic(active_epic_id)
    if not epic:
        return
    parsed = body.parse(str(epic.get("body") or ""))
    details = body.outline(parsed)
    store.log_system_event(
        level="info",
        category="application",
        event_type="epic_outline",
        message=f"Epic outline: {parsed.title or '(untitled)'}",
        details=details,
        turn_id=turn["id"],
        epic_id=active_epic_id,
    )


def _summarize_hot_context(hot_context: dict) -> dict:
    epic = hot_context.get("epic") or {}
    return {
        "epic_id": epic.get("id"),
        "epic_state": epic.get("state"),
        "recent_message_count": len(hot_context.get("recent_messages", [])),
        "recent_tool_call_count": len(hot_context.get("recent_tool_calls", [])),
    }
