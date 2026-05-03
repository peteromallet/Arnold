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

GET_CHECKLIST_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["epic_id"],
    "properties": {
        "epic_id": {"type": "string"},
        "status": {"type": ["string", "null"]},
    },
}

RECENT_MESSAGES_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["epic_id"],
    "properties": {
        "epic_id": {"type": "string"},
        "n": {"type": "integer"},
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

LIST_EPICS_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "active_only": {"type": "boolean"},
        "limit": {"type": "integer"},
    },
}

SEARCH_EPICS_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["query"],
    "properties": {
        "query": {"type": "string"},
        "active_only": {"type": "boolean"},
        "limit": {"type": "integer"},
    },
}

SEARCH_MESSAGES_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["query"],
    "properties": {
        "query": {"type": "string"},
        "epic_id": {"type": ["string", "null"]},
        "limit": {"type": "integer"},
    },
}

SEARCH_IN_BODY_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["epic_id", "query"],
    "properties": {
        "epic_id": {"type": "string"},
        "query": {"type": "string"},
        "context_lines": {"type": "integer"},
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
    return _epic_payload(
        {**epic, "sprints": context.store.list_sprints_with_items(epic_id)},
        parsed,
        sections,
    )


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
    "get_body_outline",
    schema=EPIC_ID_SCHEMA,
    operation_kind="read",
)
def get_body_outline(context: ToolContext, epic_id: str) -> JSONDict:
    epic = context.store.load_epic(epic_id)
    if not epic:
        return {"error": "epic_not_found", "epic_id": epic_id}
    parsed = body.parse(str(epic.get("body") or ""))
    return {
        "epic_id": epic_id,
        "outline": body.outline(parsed),
    }


@register_tool(
    "search_in_body",
    schema=SEARCH_IN_BODY_SCHEMA,
    operation_kind="read",
)
def search_in_body(
    context: ToolContext,
    epic_id: str,
    query: str,
    context_lines: int = 2,
) -> JSONDict:
    epic = context.store.load_epic(epic_id)
    if not epic:
        return {"error": "epic_not_found", "epic_id": epic_id, "query": query, "results": []}
    parsed = body.parse(str(epic.get("body") or ""))
    result = body.search(parsed, query, context_lines=context_lines)
    return {
        "epic_id": epic_id,
        "query": query,
        "results": result["results"],
    }


@register_tool(
    "get_checklist",
    schema=GET_CHECKLIST_SCHEMA,
    operation_kind="read",
)
def get_checklist(
    context: ToolContext,
    epic_id: str,
    status: str | None = None,
) -> JSONDict:
    return {
        "epic_id": epic_id,
        "status": status,
        "checklist": context.store.list_checklist_items(epic_id, status=status),
    }


@register_tool(
    "get_sprints",
    schema=EPIC_ID_SCHEMA,
    operation_kind="read",
)
def get_sprints(context: ToolContext, epic_id: str) -> JSONDict:
    return {
        "epic_id": epic_id,
        "sprints": context.store.list_sprints_with_items(epic_id),
    }


@register_tool(
    "recent_messages",
    schema=RECENT_MESSAGES_SCHEMA,
    operation_kind="read",
)
def recent_messages(context: ToolContext, epic_id: str, n: int = 10) -> JSONDict:
    limit = max(0, min(n, 10))
    messages = context.store.load_hot_context(epic_id).get("recent_messages") or []
    return {
        "epic_id": epic_id,
        "requested_n": n,
        "returned_n": min(limit, len(messages)),
        "max_available": 10,
        "recent_messages": messages[-limit:] if limit else [],
    }


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
    images = context.store.list_images(epic_id=epic_id, active=True)
    second_opinions = [
        event for event in events
        if event.get("event_type") == "second_opinion_requested"
    ]
    return {
        "epic_id": epic_id,
        "goal": epic.get("goal") or parsed.goal_first_paragraph,
        "state": epic.get("state"),
        "open_checklist_count": len(open_items),
        "section_names": [section.name for section in parsed.sections],
        "goal_and_current_state": {
            "goal": epic.get("goal") or parsed.goal_first_paragraph,
            "state": epic.get("state"),
        },
        "active_checklist_items": open_items,
        "principles_captured": _section_content(parsed, ["principles", "constraints", "non-goals"]),
        "recent_decisions": list(reversed(events))[:5],
        "code_references": _section_content(parsed, ["code references", "implementation notes"]),
        "recent_images": images[:5],
        "recent_second_opinion_findings": list(reversed(second_opinions))[:5],
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
        "sprints": context.store.list_sprints_with_items(epic_id),
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
                    "state": prior_state.get("state", state["state"]),
                    "checklist": prior_state.get("checklist", state["checklist"]),
                    "sprints": prior_state.get("sprints", state["sprints"]),
                }
            )
        elif event_type in {"sprints_change", "sprint_status_change", "state_change", "forced_handoff"}:
            if "state" in prior_state:
                state["state"] = prior_state.get("state")
            if "sprints" in prior_state:
                state["sprints"] = prior_state.get("sprints", state["sprints"])
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
            "sprints": state["sprints"],
        },
        parsed,
        None,
    )
    payload["checklist"] = state["checklist"]
    payload["sprints"] = state["sprints"]
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


@register_tool(
    "list_epics",
    schema=LIST_EPICS_SCHEMA,
    operation_kind="read",
)
def list_epics(
    context: ToolContext,
    active_only: bool = True,
    limit: int = 20,
) -> JSONDict:
    return {"epics": context.store.list_epics(active_only=active_only, limit=limit)}


@register_tool(
    "search_epics",
    schema=SEARCH_EPICS_SCHEMA,
    operation_kind="read",
)
def search_epics(
    context: ToolContext,
    query: str,
    active_only: bool = True,
    limit: int = 20,
) -> JSONDict:
    return {
        "query": query,
        "epics": context.store.search_epics(
            query=query,
            active_only=active_only,
            limit=limit,
        ),
    }


@register_tool(
    "search_messages",
    schema=SEARCH_MESSAGES_SCHEMA,
    operation_kind="read",
)
def search_messages(
    context: ToolContext,
    query: str,
    epic_id: str | None = None,
    limit: int = 20,
) -> JSONDict:
    return {
        "query": query,
        "messages": context.store.search_messages(
            query=query,
            epic_id=epic_id,
            limit=limit,
        ),
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
        "planned_at": epic.get("planned_at"),
        "sprints": epic.get("sprints", []),
    }


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _section_content(parsed: body.ParsedBody, names: list[str]) -> list[JSONDict]:
    wanted = {name.lower() for name in names}
    return [
        {"section": section.name, "content": section.content}
        for section in parsed.sections
        if section.name.lower() in wanted
    ]


__all__ = [
    "get_body_outline",
    "get_checklist",
    "get_epic",
    "get_epic_at_time",
    "get_history",
    "get_recent_turns",
    "get_section_names",
    "get_self_understanding",
    "get_sprints",
    "list_epics",
    "recent_messages",
    "search_in_body",
    "search_epics",
    "search_messages",
    "search_tool_calls",
]
