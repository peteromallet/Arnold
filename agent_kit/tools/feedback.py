"""Feedback and agent-observation tools."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from agent_kit.tool_kit import ToolContext, register_tool


JSONDict = dict[str, Any]

USER_FEEDBACK_KINDS = {"style", "process", "epic_specific"}
OBSERVATION_KINDS = {
    "friction",
    "ambiguity",
    "tool_failure",
    "confusion",
    "pattern_noticed",
}
USER_FEEDBACK_SOURCES = {
    "user_volunteered",
    "agent_proposed_user_confirmed",
    "explicit_save_request",
}
OBSERVATION_SOURCE = "agent_observation"

SAVE_FEEDBACK_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["kind", "content"],
    "properties": {
        "kind": {"type": "string"},
        "content": {"type": "string"},
        "source": {"type": "string"},
        "source_message_id": {"type": ["string", "null"]},
        "epic_id": {"type": ["string", "null"]},
        "context_snapshot": {"type": ["object", "null"]},
    },
}

FEEDBACK_ID_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["feedback_id"],
    "properties": {
        "feedback_id": {"type": "string"},
    },
}

DEACTIVATE_FEEDBACK_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["feedback_id", "reason"],
    "properties": {
        "feedback_id": {"type": "string"},
        "reason": {"type": "string"},
    },
}

LIST_FEEDBACK_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "epic_id": {"type": ["string", "null"]},
        "active": {"type": ["boolean", "null"]},
        "kinds": {"type": ["array", "null"], "items": {"type": "string"}},
        "limit": {"type": ["integer", "null"]},
    },
}

RECORD_OBSERVATION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["kind", "content"],
    "properties": {
        "kind": {"type": "string"},
        "content": {"type": "string"},
        "epic_id": {"type": ["string", "null"]},
        "bot_action_being_critiqued": {"type": ["string", "null"]},
        "context_snapshot": {"type": ["object", "null"]},
    },
}

LIST_OBSERVATIONS_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "resolved": {"type": ["boolean", "null"]},
        "limit": {"type": ["integer", "null"]},
    },
}

MARK_OBSERVATION_RESOLVED_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["feedback_id", "resolution_note"],
    "properties": {
        "feedback_id": {"type": "string"},
        "resolution_note": {"type": "string"},
    },
}


@register_tool(
    "save_feedback",
    schema=SAVE_FEEDBACK_SCHEMA,
    operation_kind="write",
)
def save_feedback(
    context: ToolContext,
    kind: str,
    content: str,
    source: str = "explicit_save_request",
    source_message_id: str | None = None,
    epic_id: str | None = None,
    context_snapshot: JSONDict | None = None,
) -> JSONDict:
    if kind not in USER_FEEDBACK_KINDS:
        return {
            "error": "invalid_feedback_kind",
            "kind": kind,
            "allowed_kinds": sorted(USER_FEEDBACK_KINDS),
        }
    if source not in USER_FEEDBACK_SOURCES:
        return {
            "error": "invalid_feedback_source",
            "source": source,
            "allowed_sources": sorted(USER_FEEDBACK_SOURCES),
        }

    target_epic_id = epic_id
    if kind == "epic_specific" and target_epic_id is None:
        target_epic_id = _metadata_string(context, "epic_id")
    feedback = context.store.create_feedback(
        kind=kind,
        content=content,
        source=source,
        source_message_id=source_message_id or _metadata_string(context, "inbound_message_id"),
        epic_id=target_epic_id,
        turn_id=context.turn_id,
        context_snapshot=context_snapshot or _context_snapshot(context),
    )
    return {"feedback": feedback}


@register_tool(
    "apply_feedback",
    schema=FEEDBACK_ID_SCHEMA,
    operation_kind="write",
)
def apply_feedback(context: ToolContext, feedback_id: str) -> JSONDict:
    feedback = context.store.load_feedback(feedback_id)
    if not feedback:
        return {"error": "feedback_not_found", "feedback_id": feedback_id}
    if str(feedback.get("kind")) not in USER_FEEDBACK_KINDS:
        return {"error": "invalid_feedback_kind", "feedback_id": feedback_id}
    now = _now()
    updated = context.store.update_feedback(
        feedback_id,
        last_applied_at=now,
        last_referenced_at=now,
    )
    return {"feedback": updated}


@register_tool(
    "deactivate_feedback",
    schema=DEACTIVATE_FEEDBACK_SCHEMA,
    operation_kind="write",
)
def deactivate_feedback(
    context: ToolContext,
    feedback_id: str,
    reason: str,
) -> JSONDict:
    feedback = context.store.load_feedback(feedback_id)
    if not feedback:
        return {"error": "feedback_not_found", "feedback_id": feedback_id}
    if str(feedback.get("kind")) not in USER_FEEDBACK_KINDS:
        return {"error": "invalid_feedback_kind", "feedback_id": feedback_id}
    updated = context.store.update_feedback(
        feedback_id,
        active=False,
        deactivation_reason=reason,
        last_referenced_at=_now(),
    )
    return {"feedback": updated}


@register_tool(
    "list_feedback",
    schema=LIST_FEEDBACK_SCHEMA,
    operation_kind="write",
)
def list_feedback(
    context: ToolContext,
    epic_id: str | None = None,
    active: bool | None = True,
    kinds: list[str] | None = None,
    limit: int | None = None,
) -> JSONDict:
    invalid_kinds = sorted(set(kinds or []) - USER_FEEDBACK_KINDS)
    if invalid_kinds:
        return {
            "error": "invalid_feedback_kind",
            "kinds": invalid_kinds,
            "allowed_kinds": sorted(USER_FEEDBACK_KINDS),
        }
    rows = context.store.list_feedback(
        epic_id=epic_id,
        active=active,
        kinds=kinds,
        limit=limit,
    )
    referenced = _mark_referenced(context, rows)
    return {"feedback": referenced}


@register_tool(
    "record_observation",
    schema=RECORD_OBSERVATION_SCHEMA,
    operation_kind="write",
)
def record_observation(
    context: ToolContext,
    kind: str,
    content: str,
    epic_id: str | None = None,
    bot_action_being_critiqued: str | None = None,
    context_snapshot: JSONDict | None = None,
) -> JSONDict:
    if kind not in OBSERVATION_KINDS:
        return {
            "error": "invalid_observation_kind",
            "kind": kind,
            "allowed_kinds": sorted(OBSERVATION_KINDS),
        }
    observation = context.store.create_feedback(
        kind=kind,
        content=content,
        source=OBSERVATION_SOURCE,
        epic_id=epic_id or _metadata_string(context, "epic_id"),
        turn_id=context.turn_id,
        context_snapshot=context_snapshot
        or _context_snapshot(
            context,
            bot_action_being_critiqued=bot_action_being_critiqued,
        ),
    )
    return {"observation": observation}


@register_tool(
    "list_observations",
    schema=LIST_OBSERVATIONS_SCHEMA,
    operation_kind="write",
)
def list_observations(
    context: ToolContext,
    resolved: bool | None = False,
    limit: int | None = None,
) -> JSONDict:
    rows = context.store.list_observations(resolved=resolved, limit=limit)
    referenced = _mark_referenced(context, rows)
    return {"observations": referenced}


@register_tool(
    "mark_observation_resolved",
    schema=MARK_OBSERVATION_RESOLVED_SCHEMA,
    operation_kind="write",
)
def mark_observation_resolved(
    context: ToolContext,
    feedback_id: str,
    resolution_note: str,
) -> JSONDict:
    observation = context.store.load_feedback(feedback_id)
    if not observation:
        return {"error": "observation_not_found", "feedback_id": feedback_id}
    if str(observation.get("kind")) not in OBSERVATION_KINDS:
        return {"error": "invalid_observation_kind", "feedback_id": feedback_id}
    now = _now()
    updated = context.store.update_feedback(
        feedback_id,
        resolved=True,
        resolution_note=resolution_note,
        resolved_at=now,
        last_referenced_at=now,
    )
    return {"observation": updated}


def _mark_referenced(context: ToolContext, rows: list[JSONDict]) -> list[JSONDict]:
    if not rows:
        return []
    now = _now()
    return [
        context.store.update_feedback(str(row["id"]), last_referenced_at=now)
        for row in rows
    ]


def _context_snapshot(
    context: ToolContext,
    *,
    bot_action_being_critiqued: str | None = None,
) -> JSONDict:
    return {
        "user_message": context.metadata.get("user_message"),
        "bot_action_being_critiqued": bot_action_being_critiqued,
    }


def _metadata_string(context: ToolContext, key: str) -> str | None:
    value = context.metadata.get(key)
    return value if isinstance(value, str) and value else None


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace(
        "+00:00",
        "Z",
    )


__all__ = [
    "OBSERVATION_KINDS",
    "OBSERVATION_SOURCE",
    "USER_FEEDBACK_KINDS",
    "USER_FEEDBACK_SOURCES",
    "apply_feedback",
    "deactivate_feedback",
    "list_feedback",
    "list_observations",
    "mark_observation_resolved",
    "record_observation",
    "save_feedback",
]
