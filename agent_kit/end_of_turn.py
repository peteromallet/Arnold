"""Pure end-of-turn checks for editorial turns."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


DEFAULT_END_OF_TURN_ACKNOWLEDGMENT = "Done."


@dataclass(frozen=True)
class EndOfTurnToolCall:
    name: str
    operation_kind: str
    result: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EndOfTurnFinding:
    category: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EndOfTurnDecision:
    findings: tuple[EndOfTurnFinding, ...]
    should_send_default_acknowledgment: bool
    should_error_empty_response: bool


def evaluate_end_of_turn(
    *,
    user_message: str,
    response_text: str | None,
    reply_sent: bool,
    tool_calls: list[EndOfTurnToolCall],
    body_before: str | None,
    body_after: str | None,
    checklist_before: list[dict[str, Any]],
    checklist_after: list[dict[str, Any]],
) -> EndOfTurnDecision:
    """Return deterministic end-of-turn findings without side effects."""

    normalized_response = (response_text or "").strip()
    body_changed = (body_before or "") != (body_after or "")
    checklist_changed = _checklist_signature(checklist_before) != _checklist_signature(
        checklist_after
    )
    progress_made = body_changed or checklist_changed or _has_substantive_tool_work(tool_calls)
    message_will_be_sent = reply_sent or bool(normalized_response)

    findings: list[EndOfTurnFinding] = []
    if not message_will_be_sent:
        findings.append(
            EndOfTurnFinding(
                category="no_message_sent",
                message="Turn reached completion without an outbound message.",
            )
        )
    if not tool_calls and not body_changed and not checklist_changed:
        findings.append(
            EndOfTurnFinding(
                category="no_tool_calls_or_progress",
                message="Turn produced no tool calls or persisted progress.",
            )
        )
    if not normalized_response:
        findings.append(
            EndOfTurnFinding(
                category="empty_response",
                message="Model response text was empty.",
                details={"response_was_none": response_text is None},
            )
        )
    if _expects_body_change(user_message, tool_calls) and not body_changed:
        findings.append(
            EndOfTurnFinding(
                category="body_unchanged_when_expected",
                message="User intent or tool plan implied a body edit, but the body did not change.",
            )
        )
    if _expects_checklist_progress(user_message, checklist_before) and not checklist_changed:
        findings.append(
            EndOfTurnFinding(
                category="checklist_stall",
                message="Checklist progress was expected, but checklist state did not change.",
                details={"open_items": _open_checklist_count(checklist_before)},
            )
        )

    return EndOfTurnDecision(
        findings=tuple(findings),
        should_send_default_acknowledgment=not message_will_be_sent and progress_made,
        should_error_empty_response=not normalized_response and not progress_made,
    )


def _has_substantive_tool_work(tool_calls: list[EndOfTurnToolCall]) -> bool:
    for call in tool_calls:
        if call.operation_kind != "write":
            continue
        if call.name in {
            "send_message",
            "set_activity",
            "defer_to_caller",
            "list_feedback",
            "list_observations",
        }:
            continue
        if isinstance(call.result, dict) and call.result.get("error"):
            continue
        return True
    return False


def _expects_body_change(
    user_message: str,
    tool_calls: list[EndOfTurnToolCall],
) -> bool:
    if any(call.name in {"create_epic", "edit_epic"} for call in tool_calls):
        return True
    lowered = user_message.lower()
    edit_verbs = (
        "add ",
        "change ",
        "delete ",
        "edit ",
        "expand ",
        "remove ",
        "rewrite ",
        "tighten ",
        "update ",
    )
    body_targets = (
        "body",
        "copy",
        "description",
        "draft",
        "epic",
        "goal",
        "section",
        "part about",
    )
    return any(verb in lowered for verb in edit_verbs) and any(
        target in lowered for target in body_targets
    )


def _expects_checklist_progress(
    user_message: str,
    checklist_before: list[dict[str, Any]],
) -> bool:
    if not _open_checklist_count(checklist_before):
        return False
    lowered = user_message.lower()
    checklist_terms = ("checklist", "mark", "complete", "finish", "done")
    item_terms = ("item", "task", "todo", "next")
    return any(term in lowered for term in checklist_terms) and any(
        term in lowered for term in item_terms
    )


def _open_checklist_count(items: list[dict[str, Any]]) -> int:
    return sum(1 for item in items if str(item.get("status") or "open") != "done")


def _checklist_signature(items: list[dict[str, Any]]) -> tuple[tuple[str, str, str], ...]:
    return tuple(
        sorted(
            (
                str(item.get("id") or ""),
                str(item.get("label") or item.get("title") or ""),
                str(item.get("status") or ""),
            )
            for item in items
        )
    )


__all__ = [
    "DEFAULT_END_OF_TURN_ACKNOWLEDGMENT",
    "EndOfTurnDecision",
    "EndOfTurnFinding",
    "EndOfTurnToolCall",
    "evaluate_end_of_turn",
]
