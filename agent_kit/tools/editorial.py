"""Editorial write tools for epic bodies and checklists."""

from __future__ import annotations

from datetime import UTC, datetime
import re
from typing import Any, Sequence
from uuid import uuid4

from agent_kit import body
from agent_kit.gating import evaluate_state_transition
from agent_kit.sprints import SprintValidationError, apply_sprint_changes, restore_sprints
from agent_kit.templates import DEFAULT_BODY_TEMPLATE, DEFAULT_CHECKLIST_SEED
from agent_kit.tool_kit import ToolContext, register_tool


JSONDict = dict[str, Any]
_IMAGE_REFERENCE_RE = re.compile(r"!\[([^\]]*)\]\(image:([a-z][a-z0-9_]{0,63})\)")


class _EditBlocked(Exception):
    def __init__(self, payload: JSONDict) -> None:
        super().__init__(str(payload.get("error") or "edit_blocked"))
        self.payload = payload

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
        "force": {"type": "boolean"},
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
    force: bool = False,
) -> JSONDict:
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
    sprint_payload = changes.get("sprints")
    sprint_snapshot = context.store.list_sprints_with_items(epic_id)
    state_target = _state_target(changes.get("state"))
    state_before = str(epic.get("state") or "shaping")

    transaction_id = uuid4().hex
    sprint_changes: list[JSONDict] = []
    state_transition: JSONDict | None = None
    second_opinion_advisory: JSONDict | None = None
    bypassed_blockers: list[JSONDict] = []
    try:
        with context.store.transaction():
            created_checklist_items: list[JSONDict] = []
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
                created_checklist_items = _apply_checklist_changes(
                    context,
                    epic_id,
                    checklist_changes,
                )
                context.store.record_epic_event(
                    epic_id=epic_id,
                    transaction_id=transaction_id,
                    event_type="checklist_change",
                    summary=change_summary,
                    prior_state={"items": checklist_snapshot or []},
                    turn_id=context.turn_id,
                )
            if isinstance(sprint_payload, dict):
                try:
                    sprint_changes = apply_sprint_changes(context.store, epic_id, sprint_payload)
                except SprintValidationError as exc:
                    raise _EditBlocked({"error": "invalid_sprints", "blockers": list(exc.errors)})
                context.store.record_epic_event(
                    epic_id=epic_id,
                    transaction_id=transaction_id,
                    event_type="sprints_change",
                    summary=change_summary,
                    prior_state={"sprints": sprint_snapshot},
                    turn_id=context.turn_id,
                )
                if any(change.get("kind") in {"lock_in", "queue", "pend", "reorder"} for change in sprint_changes):
                    context.store.record_epic_event(
                        epic_id=epic_id,
                        transaction_id=transaction_id,
                        event_type="sprint_status_change",
                        summary=change_summary,
                        prior_state={"sprints": sprint_snapshot},
                        turn_id=context.turn_id,
                    )
            if state_target is not None:
                gate = evaluate_state_transition(
                    from_state=state_before,
                    target_state=state_target,
                    epic=context.store.load_epic(epic_id) or epic,
                    checklist=context.store.list_checklist_items(epic_id),
                    sprints=context.store.list_sprints_with_items(epic_id),
                )
                if not gate.allowed and not force:
                    raise _EditBlocked(
                        {
                            "error": "state_transition_blocked",
                            "transition": {"from": state_before, "to": state_target},
                            "blockers": list(gate.blockers),
                        }
                    )
                bypassed_blockers = list(gate.blockers)
                epic_changes: JSONDict = {"state": state_target}
                if state_target == "planned":
                    epic_changes["planned_at"] = _now()
                context.store.update_epic(epic_id, **epic_changes)
                state_transition = {
                    "from": state_before,
                    "to": state_target,
                    "forced": bool(force and bypassed_blockers),
                    "blockers": bypassed_blockers,
                }
                second_opinion_advisory = _state_gate_second_opinion_advisory(
                    context,
                    epic_id=epic_id,
                    transition=state_transition,
                )
                context.store.record_epic_event(
                    epic_id=epic_id,
                    transaction_id=transaction_id,
                    event_type="state_change",
                    summary=change_summary,
                    prior_state={
                        "state": state_before,
                        "planned_at": epic.get("planned_at"),
                        "sprints": sprint_snapshot,
                    },
                    turn_id=context.turn_id,
                )
                if force and bypassed_blockers:
                    context.store.record_epic_event(
                        epic_id=epic_id,
                        transaction_id=transaction_id,
                        event_type="forced_handoff",
                        summary=change_summary,
                        prior_state={
                            "state": state_before,
                            "planned_at": epic.get("planned_at"),
                            "bypassed_blockers": bypassed_blockers,
                            "sprints": sprint_snapshot,
                        },
                        turn_id=context.turn_id,
                    )
    except _EditBlocked as exc:
        return exc.payload

    context.metadata["epic_id"] = epic_id
    return {
        "transaction_id": transaction_id,
        "diff": diff,
        "section_names": [section.name for section in new_parsed.sections],
        "change_summary": change_summary,
        "sprint_changes": sprint_changes,
        "state_transition": state_transition,
        "second_opinion_advisory": second_opinion_advisory,
        "forced_blockers": bypassed_blockers,
        "created_checklist_items": created_checklist_items,
        "created_checklist_item_ids": [
            str(item["id"]) for item in created_checklist_items if item.get("id")
        ],
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
        "state": current.get("state"),
        "planned_at": current.get("planned_at"),
        "checklist": context.store.list_checklist_items(epic_id),
        "sprints": context.store.list_sprints_with_items(epic_id),
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
            elif event.get("event_type") in {
                "sprints_change",
                "sprint_status_change",
                "state_change",
                "forced_handoff",
            }:
                if "state" in event_prior:
                    context.store.update_epic(
                        epic_id,
                        state=event_prior.get("state"),
                        planned_at=event_prior.get("planned_at"),
                        last_edited_at=_now(),
                    )
                if "sprints" in event_prior:
                    restore_sprints(context.store, epic_id, event_prior.get("sprints") or [])
            elif event.get("event_type") == "reverted_to":
                context.store.update_epic(
                    epic_id,
                    body=event_prior.get("body"),
                    title=event_prior.get("title"),
                    goal=event_prior.get("goal"),
                    state=event_prior.get("state", current.get("state")),
                    planned_at=event_prior.get("planned_at"),
                    last_edited_at=_now(),
                )
                if "checklist" in event_prior:
                    context.store.replace_checklist(epic_id, event_prior["checklist"])
                if "sprints" in event_prior:
                    restore_sprints(context.store, epic_id, event_prior["sprints"])
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
    raw_body = str(epic.get("body") or "")
    rendered_body, resolved, missing = _resolve_body_image_references(
        context,
        epic_id,
        raw_body,
    )
    return {
        "format": "markdown",
        "body": rendered_body,
        "raw_body": raw_body,
        "resolved_image_references": resolved,
        "missing_image_references": missing,
    }


def _resolve_body_image_references(
    context: ToolContext,
    epic_id: str,
    markdown: str,
) -> tuple[str, list[JSONDict], list[JSONDict]]:
    resolved: list[JSONDict] = []
    missing: list[JSONDict] = []

    def replace(match: re.Match[str]) -> str:
        caption = match.group(1)
        reference_key = match.group(2)
        image = context.store.load_active_image_by_reference(epic_id, reference_key)
        if image is None:
            placeholder = f"missing-image:{reference_key}"
            missing.append(
                {
                    "reference_key": reference_key,
                    "caption": caption,
                    "placeholder": placeholder,
                }
            )
            return f"![{caption}]({placeholder})"
        storage_url = str(image.get("storage_url") or "")
        resolved.append(
            {
                "reference_key": reference_key,
                "caption": caption,
                "image_id": image.get("id"),
                "source": image.get("source"),
                "storage_url": storage_url,
            }
        )
        return f"![{caption}]({storage_url})"

    return _IMAGE_REFERENCE_RE.sub(replace, markdown), resolved, missing


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
) -> list[JSONDict]:
    created_items: list[JSONDict] = []
    for item in changes.get("update", changes.get("updates", [])) or []:
        item = dict(item)
        item_id = str(item.pop("id"))
        context.store.update_checklist_item(item_id, **item)
    if changes.get("add"):
        add_items = list(changes["add"])
        created_items = context.store.add_checklist_items(epic_id, add_items)
        _link_created_checklist_items_to_second_opinions(
            context,
            epic_id,
            add_items,
            created_items,
        )
    if changes.get("delete"):
        context.store.delete_checklist_items([str(item) for item in changes["delete"]])
    if changes.get("replace") is not None:
        context.store.replace_checklist(epic_id, changes["replace"])
    return created_items


def _state_gate_second_opinion_advisory(
    context: ToolContext,
    *,
    epic_id: str,
    transition: JSONDict,
) -> JSONDict | None:
    if context.metadata.get("second_opinion_requested_this_turn"):
        return None
    user_message = str(context.metadata.get("user_message") or "")
    if _declines_state_gate_second_opinion(user_message):
        return {
            "status": "declined",
            "reason": "user_declined",
            "decline_phrase": "skip second opinion until I ask",
        }
    return {
        "status": "recommended",
        "default_on": True,
        "requested_by": "auto_state_gate",
        "message": (
            "Before treating this state advance as settled, offer the default-on "
            "second-opinion audit. The user may decline with 'skip second opinion until I ask'."
        ),
        "tool": {
            "name": "request_second_opinion",
            "arguments": {
                "epic_id": epic_id,
                "requested_by": "auto_state_gate",
                "focus_areas": [
                    "state gate readiness",
                    f"{transition.get('from')} to {transition.get('to')} handoff risk",
                ],
            },
        },
    }


def _declines_state_gate_second_opinion(user_message: str) -> bool:
    lowered = user_message.lower()
    decline_phrases = (
        "skip second opinion until i ask",
        "skip second opinions until i ask",
        "no second opinion",
        "don't get a second opinion",
        "do not get a second opinion",
        "decline second opinion",
    )
    return any(phrase in lowered for phrase in decline_phrases)


def _link_created_checklist_items_to_second_opinions(
    context: ToolContext,
    epic_id: str,
    add_items: Sequence[JSONDict],
    created_items: Sequence[JSONDict],
) -> None:
    created_ids_by_opinion: dict[str, list[str]] = {}
    for requested_item, created_item in zip(add_items, created_items, strict=False):
        source_id = requested_item.get("source_second_opinion_id")
        created_id = created_item.get("id")
        if source_id and created_id:
            created_ids_by_opinion.setdefault(str(source_id), []).append(str(created_id))
    if not created_ids_by_opinion:
        return

    opinions_by_id = {
        str(opinion["id"]): opinion
        for opinion in context.store.list_second_opinions(epic_id)
        if opinion.get("id")
    }
    for opinion_id, created_ids in created_ids_by_opinion.items():
        opinion = opinions_by_id.get(opinion_id)
        if opinion is None:
            raise _EditBlocked(
                {
                    "error": "source_second_opinion_not_found",
                    "source_second_opinion_id": opinion_id,
                    "epic_id": epic_id,
                }
            )
        linked_ids = [
            str(item_id)
            for item_id in opinion.get("resulting_checklist_item_ids", [])
        ]
        for created_id in created_ids:
            if created_id not in linked_ids:
                linked_ids.append(created_id)
        context.store.set_second_opinion_checklist_items(opinion_id, linked_ids)


def _state_target(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        target = value.get("target")
        return str(target) if target is not None else None
    return str(value)


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
