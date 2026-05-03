"""Deterministic Sprint 3 routing, reference, and response policy helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import re
from typing import Any, Sequence


JSONDict = dict[str, Any]
ACTIVE_EPIC_STATES = {"shaping", "sprinting", "planned", "paused"}
DEFAULT_RECENCY_HOURS = 24
GAP_ACKNOWLEDGMENT_HOURS = 24


@dataclass(frozen=True)
class EpicRouteDecision:
    epic_id: str | None
    epic_title: str | None
    action: str
    reason: str
    needs_clarification: bool = False
    switch_announcement: str | None = None


def select_epic_for_message(
    message: str,
    epics: Sequence[JSONDict],
    *,
    previous_epic_id: str | None = None,
    now: datetime | None = None,
) -> EpicRouteDecision:
    now = now or datetime.now(UTC)
    text = message.strip()
    lower = text.lower()
    active_epics = [epic for epic in epics if str(epic.get("state")) in ACTIVE_EPIC_STATES]

    matches = [
        epic for epic in active_epics
        if _title_matches(lower, str(epic.get("title") or ""))
    ]
    if len(matches) == 1:
        return _decision_for_epic(matches[0], previous_epic_id, "explicit_match")
    if len(matches) > 1:
        return EpicRouteDecision(
            epic_id=None,
            epic_title=None,
            action="clarify",
            reason="multiple_explicit_matches",
            needs_clarification=True,
        )

    if _is_meta_instruction(lower):
        return EpicRouteDecision(
            epic_id=previous_epic_id,
            epic_title=_title_for(active_epics, previous_epic_id),
            action="meta",
            reason="meta_instruction",
        )

    recent = [
        epic for epic in active_epics
        if _within_recent_window(epic.get("last_edited_at"), now)
    ]
    recent.sort(
        key=lambda epic: (
            str(epic.get("last_edited_at") or ""),
            str(epic.get("id") or ""),
        ),
        reverse=True,
    )
    if len(recent) == 1:
        return _decision_for_epic(recent[0], previous_epic_id, "single_recent_default")
    if previous_epic_id and any(str(epic.get("id")) == previous_epic_id for epic in active_epics):
        return _decision_for_epic(
            next(epic for epic in active_epics if str(epic.get("id")) == previous_epic_id),
            previous_epic_id,
            "previous_context",
        )
    return EpicRouteDecision(
        epic_id=None,
        epic_title=None,
        action="clarify",
        reason="unclear_context",
        needs_clarification=True,
    )


def detect_user_mode(message: str) -> str:
    lower = message.lower()
    if any(token in lower for token in ["spitball", "brainstorm", "what about", "could we"]):
        return "brainstorming"
    if any(token in lower for token in ["let's just", "decide for me", "ship it", "do it", "asap"]):
        return "executing"
    if len(message.split()) >= 45 or any(token in lower for token in ["why", "what if", "nail this down"]):
        return "deep-thinking"
    return "deep-thinking"


def conversation_gap_acknowledgment(
    last_message_at: str | None,
    *,
    now: datetime | None = None,
) -> JSONDict:
    if not last_message_at:
        return {"should_acknowledge": False, "hours": 0}
    now = now or datetime.now(UTC)
    previous = _parse_datetime(last_message_at)
    if previous is None:
        return {"should_acknowledge": False, "hours": 0}
    hours = int((now - previous).total_seconds() // 3600)
    return {
        "should_acknowledge": hours >= GAP_ACKNOWLEDGMENT_HOURS,
        "hours": max(0, hours),
        "threshold_hours": GAP_ACKNOWLEDGMENT_HOURS,
    }


def resolve_reference(message: str, last_outbound: str | None) -> JSONDict:
    if not last_outbound:
        return {"resolved": False, "reason": "no_last_outbound"}
    items = _extract_items(last_outbound)
    if not items:
        return {"resolved": False, "reason": "no_structure"}

    lower = message.lower()
    ordinal = _ordinal_from_text(lower)
    if ordinal is not None:
        index = ordinal - 1
        if 0 <= index < len(items):
            return {"resolved": True, "target": items[index], "index": ordinal, "items": items}
        return {"resolved": False, "reason": "ordinal_out_of_range", "items": items}
    if "last" in lower and any(token in lower for token in ["option", "one", "point", "item"]):
        return {"resolved": True, "target": items[-1], "index": len(items), "items": items}
    if "that point" in lower or "that one" in lower:
        if len(items) == 1:
            return {"resolved": True, "target": items[0], "index": 1, "items": items}
        return {"resolved": False, "reason": "ambiguous_deictic", "items": items}
    return {"resolved": False, "reason": "no_reference_signal", "items": items}


def _decision_for_epic(
    epic: JSONDict,
    previous_epic_id: str | None,
    reason: str,
) -> EpicRouteDecision:
    epic_id = str(epic.get("id"))
    title = str(epic.get("title") or epic_id)
    switching = previous_epic_id is not None and previous_epic_id != epic_id
    return EpicRouteDecision(
        epic_id=epic_id,
        epic_title=title,
        action="switch" if switching else "proceed",
        reason=reason,
        switch_announcement=f"Switching to {title}." if switching else None,
    )


def _title_for(epics: Sequence[JSONDict], epic_id: str | None) -> str | None:
    if epic_id is None:
        return None
    for epic in epics:
        if str(epic.get("id")) == epic_id:
            return str(epic.get("title") or epic_id)
    return None


def _title_matches(text: str, title: str) -> bool:
    normalized = title.strip().lower()
    return bool(normalized) and normalized in text


def _is_meta_instruction(text: str) -> bool:
    return text.startswith(("help", "what can you do", "list epics", "search epics"))


def _within_recent_window(value: Any, now: datetime) -> bool:
    parsed = _parse_datetime(str(value)) if value else None
    return parsed is not None and parsed >= now - timedelta(hours=DEFAULT_RECENCY_HOURS)


def _parse_datetime(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _ordinal_from_text(text: str) -> int | None:
    words = {
        "first": 1,
        "second": 2,
        "third": 3,
        "fourth": 4,
        "fifth": 5,
        "sixth": 6,
        "seventh": 7,
        "eighth": 8,
        "ninth": 9,
        "tenth": 10,
    }
    for word, value in words.items():
        if re.search(rf"\b{word}\b", text):
            return value
    match = re.search(r"\b(\d+)(?:st|nd|rd|th)?\b", text)
    return int(match.group(1)) if match else None


def _extract_items(text: str) -> list[JSONDict]:
    items: list[JSONDict] = []
    patterns = [
        re.compile(r"^\s*(\d+)[.)]\s+(.+?)\s*$"),
        re.compile(r"^\s*[-*]\s+(.+?)\s*$"),
        re.compile(r"^\s*#{1,6}\s+(.+?)\s*$"),
    ]
    for line in text.splitlines():
        for pattern in patterns:
            match = pattern.match(line)
            if not match:
                continue
            content = match.group(match.lastindex or 1).strip()
            items.append({"index": len(items) + 1, "text": content})
            break
    if items:
        return items
    candidates = [part.strip() for part in re.split(r"\s*;\s*|\n+", text) if part.strip()]
    if 1 < len(candidates) <= 6:
        return [{"index": index, "text": item} for index, item in enumerate(candidates, start=1)]
    return []


__all__ = [
    "ACTIVE_EPIC_STATES",
    "DEFAULT_RECENCY_HOURS",
    "EpicRouteDecision",
    "conversation_gap_acknowledgment",
    "detect_user_mode",
    "resolve_reference",
    "select_epic_for_message",
]
