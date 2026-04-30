"""Editorial read tools for epic bodies, history, and tool-call search."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from agent_kit import body
from agent_kit.tool_kit import ToolContext, register_tool


JSONDict = dict[str, Any]

EPIC_ID_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["epic_id"],
    "properties": {
        "epic_id": {"type": "string"},
    },
}

GET_EPIC_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["epic_id"],
    "properties": {
        "epic_id": {"type": "string"},
        "sections": {
            "type": ["array", "null"],
            "items": {"type": "string"},
        },
    },
}

GET_HISTORY_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["epic_id"],
    "properties": {
        "epic_id": {"type": "string"},
        "kind": {"type": ["string", "null"]},
        "since": {"type": ["string", "null"]},
    },
}

GET_EPIC_AT_TIME_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["epic_id", "timestamp"],
    "properties": {
        "epic_id": {"type": "string"},
        "timestamp": {"type": "string"},
    },
}

GET_RECENT_TURNS_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "n": {"type": "integer"},
        "epic_id": {"type": ["string", "null"]},
    },
}

SEARCH_TOOL_CALLS_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "tool_name": {"type": ["string", "null"]},
        "epic_id": {"type": ["string", "null"]},
        "since": {"type": ["string", "null"]},
        "limit": {"type": "integer"},
    },
}


@register_tool(
    "get_epic",
    schema=GET_EPIC_SCHEMA,
    operation_kind="read",
)
def get_epic(
    context: ToolContext,
    epic_id: str,
    sections: list[str] | None = None,
) -> JSONDict:
    epic = context.store.load_epic(epic_id)
    if not epic:
        return {"error": "epic_not_found", "epic_id": epic_id}
    parsed = body.parse(str(epic.get("body") or ""))
    return _epic_payload(epic, parsed, sections)


@register_tool(
    "get_section_names",
    schema=EPIC_ID_SCHEMA,
    operation_kind="read",
)
def get_section_names(context: ToolContext, epic_id: str) -> JSONDict:
    epic = context.store.load_epic(epic_id)
    if not epic:
        return {"error": "epic_not_found", "epic_id": epic_id}
    parsed = body.parse(str(epic.get("body") or ""))
    return {"section_names": [section.name for section in parsed.sections]}


@register_tool(
    "get_history",
    schema=GET_HISTORY_SCHEMA,
    operation_kind="read",
)
def get_history(
    context: ToolContext,
    epic_id: str,
    kind: str | None = None,
    since: str | None = None,
) -> JSONDict:
    events = context.store.list_epic_events(
        epic_id,
        since=since,
        kinds=[kind] if kind else None,
    )
    return {"events": list(reversed(events))}


@register_tool(
    "get_self_understanding",
    schema=EPIC_ID_SCHEMA,
    operation_kind="read",
)
def get_self_understanding(context: ToolContext, epic_id: str) -> JSONDict:
    epic = context.store.load_epic(epic_id)
    if not epic:
        return {"error": "epic_not_found", "epic_id": epic_id}
    parsed = body.parse(str(epic.get("body") or ""))
    open_items = context.store.list_checklist_items(epic_id, status="open")
    events = context.store.list_epic_events(epic_id)
    return {
        "goal": epic.get("goal") or parsed.goal_first_paragraph,
        "state": epic.get("state"),
        "open_checklist_count": len(open_items),
        "section_names": [section.name for section in parsed.sections],
        "recent_events": list(reversed(events))[:3],
        "note": "The full seven-section self-understanding structure lights up incrementally.",
    }


@register_tool(
    "get_epic_at_time",
    schema=GET_EPIC_AT_TIME_SCHEMA,
    operation_kind="read",
)
def get_epic_at_time(context: ToolContext, epic_id: str, timestamp: str) -> JSONDict:
    epic = context.store.load_epic(epic_id)
    if not epic:
        return {"error": "epic_not_found", "epic_id": epic_id}

    state = {
        "body": epic.get("body") or "",
        "title": epic.get("title"),
        "goal": epic.get("goal"),
        "state": epic.get("state"),
        "checklist": context.store.list_checklist_items(epic_id),
    }
    events = context.store.list_epic_events(epic_id)
    target = _parse_time(timestamp)
    for event in sorted(events, key=lambda item: (item.get("occurred_at") or "", item.get("id") or ""), reverse=True):
        occurred_at = event.get("occurred_at")
        if not occurred_at or _parse_time(str(occurred_at)) <= target:
            continue
        prior_state = event.get("prior_state") or {}
        event_type = event.get("event_type")
        if event_type == "body_edit":
            state.update(
                {
                    "body": prior_state.get("body", state["body"]),
                    "title": prior_state.get("title", state["title"]),
                    "goal": prior_state.get("goal", state["goal"]),
                }
            )
        elif event_type == "checklist_change":
            state["checklist"] = prior_state.get("items", state["checklist"])
        elif event_type == "reverted_to":
            state.update(
                {
                    "body": prior_state.get("body", state["body"]),
                    "title": prior_state.get("title", state["title"]),
                    "goal": prior_state.get("goal", state["goal"]),
                    "checklist": prior_state.get("checklist", state["checklist"]),
                }
            )
        elif event_type == "created":
            state.update(
                {
                    "body": prior_state.get("body", state["body"]),
                    "title": prior_state.get("title", state["title"]),
                    "goal": prior_state.get("goal", state["goal"]),
                    "checklist": prior_state.get("checklist", state["checklist"]),
                }
            )
            break

    parsed = body.parse(str(state["body"] or ""))
    payload = _epic_payload(
        {
            "title": state["title"],
            "goal": state["goal"],
            "body": state["body"],
            "state": state["state"],
        },
        parsed,
        None,
    )
    payload["checklist"] = state["checklist"]
    return payload


@register_tool(
    "get_recent_turns",
    schema=GET_RECENT_TURNS_SCHEMA,
    operation_kind="read",
)
def get_recent_turns(
    context: ToolContext,
    n: int = 10,
    epic_id: str | None = None,
) -> JSONDict:
    turns = context.store.list_recent_turns(n=n, epic_id=epic_id)
    event_cache: dict[str, list[JSONDict]] = {}
    enriched = []
    for turn in turns:
        turn_epic_id = turn.get("epic_id")
        summaries: list[str] = []
        if turn_epic_id:
            if turn_epic_id not in event_cache:
                event_cache[turn_epic_id] = context.store.list_epic_events(str(turn_epic_id))
            summaries = [
                str(event.get("summary") or "")
                for event in event_cache[turn_epic_id]
                if event.get("turn_id") == turn.get("id")
            ]
        enriched.append({**turn, "change_summary": "; ".join(item for item in summaries if item)})
    return {"turns": enriched}


@register_tool(
    "search_tool_calls",
    schema=SEARCH_TOOL_CALLS_SCHEMA,
    operation_kind="read",
)
def search_tool_calls(
    context: ToolContext,
    tool_name: str | None = None,
    epic_id: str | None = None,
    since: str | None = None,
    limit: int = 20,
) -> JSONDict:
    return {
        "tool_calls": context.store.search_tool_calls_by(
            tool_name=tool_name,
            epic_id=epic_id,
            since=since,
            limit=limit,
        )
    }


def _epic_payload(
    epic: JSONDict,
    parsed: body.ParsedBody,
    requested_sections: list[str] | None,
) -> JSONDict:
    sections = {section.name: section.content for section in parsed.sections}
    if requested_sections is not None:
        sections = {
            name: parsed.preamble if name == "_preamble" else sections.get(name)
            for name in requested_sections
        }
    return {
        "title": epic.get("title") or parsed.title,
        "goal": epic.get("goal") or parsed.goal_first_paragraph,
        "body_full": epic.get("body") or body.serialize(parsed),
        "sections": sections,
        "section_names": [section.name for section in parsed.sections],
        "state": epic.get("state"),
    }


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


__all__ = [
    "get_epic",
    "get_epic_at_time",
    "get_history",
    "get_recent_turns",
    "get_section_names",
    "get_self_understanding",
    "search_tool_calls",
]
