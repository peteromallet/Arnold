"""Minimal invocation-mode communication tools."""

from __future__ import annotations

from typing import Any

from agent_kit.end_of_turn import ensure_reframing_suggestion
from agent_kit.logging import log
from agent_kit.tool_kit import ExternalSpec, ToolContext, register_tool


SEND_MESSAGE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["content"],
    "properties": {
        "content": {"type": "string"},
        "attach_files": {
            "type": ["array", "null"],
            "items": {"type": "string"},
        },
    },
}

SET_ACTIVITY_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["description"],
    "properties": {
        "description": {"type": "string"},
    },
}

SET_TYPING_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["on"],
    "properties": {
        "on": {"type": "boolean"},
    },
}

DEFER_TO_CALLER_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["questions"],
    "properties": {
        "questions": {
            "type": "array",
            "items": {"type": "string"},
        },
        "reason": {"type": ["string", "null"]},
    },
}


@register_tool(
    "send_message",
    schema=SEND_MESSAGE_SCHEMA,
    event_kind="tool_call",
    operation_kind="write",
)
def send_message(
    context: ToolContext,
    content: str,
    attach_files: list[str] | None = None,
) -> str:
    del attach_files
    content = ensure_reframing_suggestion(
        content,
        low_score_details=context.metadata.get("low_second_opinion"),
    )
    context.reply_buffer.append(content)
    is_resident = context.transport is not None
    # Resident sends must wait for Discord confirmation before filling the external id.
    message = context.store.create_message(
        epic_id=context.metadata.get("epic_id"),
        direction="outbound",
        content=content,
        bot_turn_id=context.turn_id,
        synthesize_outbound_id=not is_resident,
    )
    if not is_resident:
        return message["discord_message_id"]

    channel_id = str(context.metadata.get("channel_id") or "")
    endpoint = f"POST /channels/{channel_id}/messages"

    def _post_and_update():
        response = context.transport.post_message(channel_id, content)  # type: ignore[union-attr]
        discord_message_id = (
            response.get("discord_message_id")
            or response.get("id")
            or response.get("message_id")
        )
        if discord_message_id is not None:
            context.store.update_message(
                message["id"],
                discord_message_id=str(discord_message_id),
            )
        return (
            str(discord_message_id) if discord_message_id is not None else None,
            response,
        )

    if context.external_queue is None:
        context.external_queue = []
    context.external_queue.append(
        (
            ExternalSpec(
                provider="discord",
                endpoint=endpoint,
                request_summary={
                    "content_preview": content[:100],
                    "channel_id": channel_id,
                    "message_row_id": message["id"],
                },
            ),
            _post_and_update,
        )
    )
    return message["id"]


@register_tool(
    "set_activity",
    schema=SET_ACTIVITY_SCHEMA,
    event_kind="activity",
    operation_kind="write",
)
def set_activity(context: ToolContext, description: str) -> dict[str, str]:
    if len(description) > 80:
        original_length = len(description)
        description = description[:80]
        log(
            context.store,
            "warn",
            "tool",
            "activity_truncated",
            "Activity description exceeded 80 characters and was truncated.",
            turn_id=context.turn_id,
            epic_id=context.metadata.get("epic_id"),
            original_length=original_length,
            truncated_length=len(description),
        )
    context.store.update_turn(context.turn_id, current_activity=description)
    return {"description": description}


@register_tool(
    "set_typing",
    schema=SET_TYPING_SCHEMA,
    event_kind="tool_call",
    operation_kind="write",
)
def set_typing(context: ToolContext, on: bool) -> dict[str, Any]:
    if context.transport is None:
        return {"typing": bool(on), "mode": "invocation", "noop": True}

    channel_id = str(context.metadata.get("channel_id") or "")
    set_typing_method = getattr(context.transport, "set_typing", None)
    if callable(set_typing_method):
        set_typing_method(channel_id, bool(on))
    return {"typing": bool(on), "mode": "resident"}


@register_tool(
    "defer_to_caller",
    schema=DEFER_TO_CALLER_SCHEMA,
    event_kind="tool_call",
    operation_kind="write",
)
def defer_to_caller(
    context: ToolContext,
    questions: list[str],
    reason: str | None = None,
) -> dict[str, Any]:
    context.metadata["outcome"] = "blocked_on_caller"
    context.metadata["questions"] = list(questions)
    context.metadata["defer_reason"] = reason
    context.metadata["stop_requested"] = True
    return {"questions": list(questions), "reason": reason}


__all__ = [
    "DEFER_TO_CALLER_SCHEMA",
    "SEND_MESSAGE_SCHEMA",
    "SET_ACTIVITY_SCHEMA",
    "SET_TYPING_SCHEMA",
    "defer_to_caller",
    "send_message",
    "set_activity",
    "set_typing",
]
