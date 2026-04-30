"""Editorial write tools for epic bodies and checklists."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Sequence
from uuid import uuid4

from agent_kit import body
from agent_kit.templates import DEFAULT_BODY_TEMPLATE, DEFAULT_CHECKLIST_SEED
from agent_kit.tool_kit import ToolContext, register_tool


JSONDict = dict[str, Any]

CREATE_EPIC_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["title", "goal"],
    "properties": {
        "title": {"type": "string"},
        "goal": {"type": "string"},
    },
}

EDIT_EPIC_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["epic_id", "changes", "change_summary"],
    "properties": {
        "epic_id": {"type": "string"},
        "changes": {"type": "object"},
        "change_summary": {"type": "string"},
        "expected_diff": {"type": ["string", "null"]},
    },
}

REVERT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["epic_id"],
    "properties": {
        "epic_id": {"type": "string"},
        "event_id": {"type": ["string", "null"]},
    },
}

RENDER_EPIC_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["epic_id"],
    "properties": {
        "epic_id": {"type": "string"},
        "format": {"type": "string", "enum": ["markdown", "html"]},
    },
}

_BODY_OPS = {
    "new_content",
    "sections",
    "append",
    "add_section",
    "add_sections",
    "remove_sections",
    "rename_section",
    "reorder",
}


@register_tool(
    "create_epic",
    schema=CREATE_EPIC_SCHEMA,
    operation_kind="write",
)
def create_epic(context: ToolContext, title: str, goal: str) -> JSONDict:
    rendered = DEFAULT_BODY_TEMPLATE(title, goal)
    parsed = body.parse(rendered)
    try:
        body.validate_for_write(parsed)
    except body.BodyValidationError as exc:
        return _body_validation_error(exc)

    transaction_id = uuid4().hex
    with context.store.transaction():
        epic = context.store.create_epic(
            title=parsed.title or "",
            goal=parsed.goal_first_paragraph or "",
            body=rendered,
            state="shaping",
        )
        checklist = context.store.seed_checklist(epic["id"], DEFAULT_CHECKLIST_SEED)
        context.store.record_epic_event(
            epic_id=epic["id"],
            transaction_id=transaction_id,
            event_type="created",
            summary="Epic created with default design-doc template",
            prior_state={
                "body": rendered,
                "title": parsed.title,
                "goal": parsed.goal_first_paragraph,
                "checklist": checklist,
            },
            turn_id=context.turn_id,
        )
        inbound_message_id = context.metadata.get("inbound_message_id")
        if inbound_message_id:
            context.store.update_message(str(inbound_message_id), epic_id=epic["id"])
        context.store.update_turn(context.turn_id, epic_id=epic["id"])

    context.metadata["epic_id"] = epic["id"]
    return {
        "epic_id": epic["id"],
        "title": parsed.title,
        "goal": parsed.goal_first_paragraph,
        "section_names": [section.name for section in parsed.sections],
        "checklist_count": len(checklist),
        "transaction_id": transaction_id,
    }


@register_tool(
    "edit_epic",
    schema=EDIT_EPIC_SCHEMA,
    operation_kind="write",
)
def edit_epic(
    context: ToolContext,
    epic_id: str,
    changes: JSONDict,
    change_summary: str,
    expected_diff: str | None = None,
) -> JSONDict:
    if "sprints" in changes or "state" in changes:
        return {"error": "not_yet_supported"}
    if "meta" in changes:
        return {
            "error": "meta_not_supported",
            "hint": "Use body.sections._preamble for title or body.sections.Goal for goal.",
        }

    body_changes = _body_changes(changes)
    op_names = [name for name in _BODY_OPS if name in body_changes]
    if len(op_names) > 1:
        return {"error": "body_op_conflict", "operations": sorted(op_names)}

    epic = context.store.load_epic(epic_id)
    if not epic:
        return {"error": "epic_not_found", "epic_id": epic_id}

    old_body = str(epic.get("body") or "")
    old_parsed = body.parse(old_body)
    new_body = old_body
    new_parsed = old_parsed
    diff = ""

    if op_names:
        try:
            new_parsed = _apply_body_op(old_parsed, op_names[0], body_changes[op_names[0]])
            body.validate_for_write(new_parsed)
        except body.BodyValidationError as exc:
            return _body_validation_error(exc)
        except (body.SectionNotFound, body.SectionExists, body.InvalidPosition) as exc:
            return {"error": type(exc).__name__, "message": str(exc)}
        new_body = body.serialize(new_parsed)
        diff = body.compute_diff(old_body, new_body)
        if expected_diff is not None and not body.diffs_equivalent(expected_diff, diff):
            return {"error": "expected_diff_mismatch", "actual_diff": diff}

    checklist_changes = changes.get("checklist")
    checklist_snapshot = (
        context.store.list_checklist_items(epic_id)
        if isinstance(checklist_changes, dict)
        else None
    )

    transaction_id = uuid4().hex
    with context.store.transaction():
        if op_names and new_body != old_body:
            context.store.update_epic(
                epic_id,
                body=new_body,
                title=new_parsed.title,
                goal=new_parsed.goal_first_paragraph,
                last_edited_at=_now(),
            )
            context.store.record_epic_event(
                epic_id=epic_id,
                transaction_id=transaction_id,
                event_type="body_edit",
                summary=change_summary,
                prior_state={
                    "body": old_body,
                    "title": epic.get("title"),
                    "goal": epic.get("goal"),
                },
                turn_id=context.turn_id,
            )
        if isinstance(checklist_changes, dict):
            _apply_checklist_changes(context, epic_id, checklist_changes)
            context.store.record_epic_event(
                epic_id=epic_id,
                transaction_id=transaction_id,
                event_type="checklist_change",
                summary=change_summary,
                prior_state={"items": checklist_snapshot or []},
                turn_id=context.turn_id,
            )

    context.metadata["epic_id"] = epic_id
    return {
        "transaction_id": transaction_id,
        "diff": diff,
        "section_names": [section.name for section in new_parsed.sections],
        "change_summary": change_summary,
    }


@register_tool(
    "revert",
    schema=REVERT_SCHEMA,
    operation_kind="write",
)
def revert(context: ToolContext, epic_id: str, event_id: str | None = None) -> JSONDict:
    target_events = _target_events(context, epic_id, event_id)
    if not target_events:
        return {"error": "transaction_not_found"}

    current = context.store.load_epic(epic_id)
    if not current:
        return {"error": "epic_not_found", "epic_id": epic_id}

    reverted_transaction_id = str(target_events[0]["transaction_id"])
    prior_state = {
        "body": current.get("body"),
        "title": current.get("title"),
        "goal": current.get("goal"),
        "checklist": context.store.list_checklist_items(epic_id),
        "reverted_transaction_id": reverted_transaction_id,
        "reverted_event_ids": [event["id"] for event in target_events],
    }
    transaction_id = uuid4().hex

    with context.store.transaction():
        for event in reversed(target_events):
            event_prior = event.get("prior_state") or {}
            if event.get("event_type") == "body_edit":
                context.store.update_epic(
                    epic_id,
                    body=event_prior.get("body"),
                    title=event_prior.get("title"),
                    goal=event_prior.get("goal"),
                    last_edited_at=_now(),
                )
            elif event.get("event_type") == "checklist_change":
                context.store.replace_checklist(epic_id, event_prior.get("items") or [])
            elif event.get("event_type") == "reverted_to":
                context.store.update_epic(
                    epic_id,
                    body=event_prior.get("body"),
                    title=event_prior.get("title"),
                    goal=event_prior.get("goal"),
                    last_edited_at=_now(),
                )
                if "checklist" in event_prior:
                    context.store.replace_checklist(epic_id, event_prior["checklist"])
        context.store.record_epic_event(
            epic_id=epic_id,
            transaction_id=transaction_id,
            event_type="reverted_to",
            summary=f"Reverted transaction {reverted_transaction_id}",
            prior_state=prior_state,
            turn_id=context.turn_id,
        )

    context.metadata["epic_id"] = epic_id
    return {
        "transaction_id": transaction_id,
        "reverted_event_count": len(target_events),
        "summary": f"Reverted transaction {reverted_transaction_id}",
    }


@register_tool(
    "render_epic",
    schema=RENDER_EPIC_SCHEMA,
    operation_kind="write",
)
def render_epic(context: ToolContext, epic_id: str, format: str = "markdown") -> JSONDict:
    if format == "html":
        return {"error": "not_yet_supported"}
    epic = context.store.load_epic(epic_id)
    if not epic:
        return {"error": "epic_not_found", "epic_id": epic_id}
    return {"format": "markdown", "body": epic.get("body") or ""}


def _body_changes(changes: JSONDict) -> JSONDict:
    nested = changes.get("body")
    if isinstance(nested, dict):
        merged = dict(nested)
        for key in _BODY_OPS:
            if key in changes and key not in merged:
                merged[key] = changes[key]
        return merged
    return changes


def _apply_body_op(parsed: body.ParsedBody, op_name: str, value: Any) -> body.ParsedBody:
    if op_name == "new_content":
        return body.parse(str(value))
    if op_name == "sections":
        result = parsed
        for section_name, content in dict(value).items():
            result = body.replace_section(result, section_name, str(content))
        return result
    if op_name == "append":
        result = parsed
        for section_name, content in dict(value).items():
            result = body.append_to_section(result, section_name, str(content))
        return result
    if op_name in {"add_section", "add_sections"}:
        result = parsed
        for item in _section_additions(value):
            result = body.add_section(
                result,
                str(item["name"]),
                str(item.get("content", "")),
                str(item.get("position", "end")),
            )
        return result
    if op_name == "remove_sections":
        result = parsed
        for section_name in list(value):
            result = body.remove_section(result, str(section_name))
        return result
    if op_name == "rename_section":
        old_name, new_name = _rename_pair(value)
        return body.rename_section(parsed, old_name, new_name)
    if op_name == "reorder":
        return body.reorder(parsed, [str(name) for name in value])
    return parsed


def _section_additions(value: Any) -> list[JSONDict]:
    if isinstance(value, list):
        return [dict(item) for item in value]
    if isinstance(value, dict) and "name" in value:
        return [dict(value)]
    if isinstance(value, dict):
        return [
            {"name": name, **dict(spec)}
            for name, spec in value.items()
        ]
    return []


def _rename_pair(value: Any) -> tuple[str, str]:
    if isinstance(value, dict):
        if "old_name" in value and "new_name" in value:
            return str(value["old_name"]), str(value["new_name"])
        if len(value) == 1:
            old_name, new_name = next(iter(value.items()))
            return str(old_name), str(new_name)
    if isinstance(value, Sequence) and len(value) == 2:
        return str(value[0]), str(value[1])
    raise body.InvalidPosition("rename_section")


def _apply_checklist_changes(
    context: ToolContext,
    epic_id: str,
    changes: JSONDict,
) -> None:
    for item in changes.get("update", changes.get("updates", [])) or []:
        item = dict(item)
        item_id = str(item.pop("id"))
        context.store.update_checklist_item(item_id, **item)
    if changes.get("add"):
        context.store.add_checklist_items(epic_id, changes["add"])
    if changes.get("delete"):
        context.store.delete_checklist_items([str(item) for item in changes["delete"]])
    if changes.get("replace") is not None:
        context.store.replace_checklist(epic_id, changes["replace"])


def _target_events(
    context: ToolContext,
    epic_id: str,
    event_id: str | None,
) -> list[JSONDict]:
    if event_id is None:
        transaction_id = context.store.latest_transaction_id(epic_id)
        return context.store.events_by_transaction(transaction_id) if transaction_id else []
    for event in context.store.list_epic_events(epic_id):
        if event.get("id") == event_id:
            return context.store.events_by_transaction(str(event["transaction_id"]))
    return []


def _body_validation_error(exc: body.BodyValidationError) -> JSONDict:
    field = str(exc).split(":", 1)[-1].strip()
    return {"error": "body_missing_required_section", "field": field}


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


__all__ = [
    "create_epic",
    "edit_epic",
    "render_epic",
    "revert",
]
