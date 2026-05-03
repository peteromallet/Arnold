"""Server-side epic state gates for Sprint 4."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from agent_kit import body


JSONDict = dict[str, Any]
LOCKDOWN_RE = re.compile(
    r"\b(TBD|to be decided|to be determined|we'll see|figure out later|tunable|depends on what surfaces|can adjust later|decide later)\b",
    re.IGNORECASE,
)
DONE_CHECKLIST_STATUSES = {"done", "skipped", "superseded"}


@dataclass(frozen=True)
class GateResult:
    allowed: bool
    blockers: tuple[JSONDict, ...]

    def to_dict(self) -> JSONDict:
        return {"allowed": self.allowed, "blockers": list(self.blockers)}


def evaluate_state_transition(
    *,
    from_state: str,
    target_state: str,
    epic: JSONDict,
    checklist: list[JSONDict],
    sprints: list[JSONDict],
) -> GateResult:
    if from_state == target_state:
        return GateResult(True, ())
    if from_state == "shaping" and target_state == "sprinting":
        return _shaping_to_sprinting(epic, checklist)
    if from_state == "sprinting" and target_state == "planned":
        return _sprinting_to_planned(epic, checklist, sprints)
    return GateResult(
        False,
        ({"code": "unsupported_transition", "message": f"Cannot advance {from_state} -> {target_state}."},),
    )


def scan_lockdown_phrases(markdown: str) -> list[JSONDict]:
    parsed = body.parse(markdown)
    spans = _section_line_spans(markdown)
    blocked: list[JSONDict] = []
    fence: str | None = None
    for line_number, line in enumerate(markdown.splitlines(), start=1):
        stripped = line.strip()
        if fence:
            if stripped.startswith(fence):
                fence = None
            continue
        if stripped.startswith("```") or stripped.startswith("~~~"):
            fence = stripped[:3]
            continue
        section = _section_for_line(spans, line_number)
        if section == "Open Questions":
            continue
        for match in LOCKDOWN_RE.finditer(line):
            blocked.append(
                {
                    "code": "unresolved_decision_phrase",
                    "phrase": match.group(0),
                    "section": section,
                    "line_number": line_number,
                    "message": f"Unresolved decision phrase outside Open Questions: {match.group(0)}",
                }
            )
    if not parsed.sections and blocked:
        for item in blocked:
            item["section"] = None
    return blocked


def _shaping_to_sprinting(epic: JSONDict, checklist: list[JSONDict]) -> GateResult:
    markdown = str(epic.get("body") or "")
    parsed = body.parse(markdown)
    blockers: list[JSONDict] = []
    if len(markdown) <= 500:
        blockers.append({"code": "body_too_short", "message": "Body must be more than 500 characters."})
    names = {section.name for section in parsed.sections}
    for required in ("Goal", "Deliverable"):
        if required not in names:
            blockers.append({"code": "missing_section", "section": required, "message": f"Missing required section: {required}"})
    unresolved = [
        item for item in checklist
        if str(item.get("status") or "open") not in DONE_CHECKLIST_STATUSES
    ]
    if checklist and len(unresolved) > max(1, len(checklist) // 3):
        blockers.append(
            {
                "code": "checklist_not_mostly_resolved",
                "open_count": len(unresolved),
                "total_count": len(checklist),
                "message": "Checklist must be mostly resolved before sprinting.",
            }
        )
    return GateResult(not blockers, tuple(blockers))


def _sprinting_to_planned(
    epic: JSONDict,
    checklist: list[JSONDict],
    sprints: list[JSONDict],
) -> GateResult:
    blockers: list[JSONDict] = []
    markdown = str(epic.get("body") or "")
    parsed = body.parse(markdown)
    if len(markdown) <= 500:
        blockers.append({"code": "body_too_short", "message": "Body must be more than 500 characters."})
    names = {section.name for section in parsed.sections}
    for required in ("Goal", "Deliverable"):
        if required not in names:
            blockers.append({"code": "missing_section", "section": required, "message": f"Missing required section: {required}"})
    unfinished = [
        item for item in checklist
        if str(item.get("status") or "open") not in DONE_CHECKLIST_STATUSES
    ]
    if unfinished:
        blockers.append(
            {
                "code": "checklist_unfinished",
                "open_count": len(unfinished),
                "message": "Checklist items must be done, skipped, or superseded.",
            }
        )
    if not sprints:
        blockers.append({"code": "missing_sprints", "message": "At least one sprint is required."})
    for sprint in sprints:
        status = str(sprint.get("status") or "")
        if status not in {"queued", "pending"}:
            blockers.append(
                {
                    "code": "sprint_not_locked",
                    "sprint_number": sprint.get("sprint_number"),
                    "status": status,
                    "message": "Every sprint must be queued or pending.",
                }
            )
        if status == "queued" and sprint.get("queue_position") is None:
            blockers.append(
                {
                    "code": "queued_sprint_missing_position",
                    "sprint_number": sprint.get("sprint_number"),
                    "message": "Queued sprint is missing queue_position.",
                }
            )
        if status == "pending" and not sprint.get("pending_reason"):
            blockers.append(
                {
                    "code": "pending_sprint_missing_reason",
                    "sprint_number": sprint.get("sprint_number"),
                    "message": "Pending sprint is missing pending_reason.",
                }
            )
    if not _pm_handoff_fidelity(parsed, sprints):
        blockers.append(
            {
                "code": "pm_handoff_fidelity",
                "message": "Body needs Goal, Key Decisions, Deliverable detail, and PM-level sprint items.",
            }
        )
    blockers.extend(scan_lockdown_phrases(markdown))
    return GateResult(not blockers, tuple(blockers))


def _pm_handoff_fidelity(parsed: body.ParsedBody, sprints: list[JSONDict]) -> bool:
    names = {section.name for section in parsed.sections}
    if not {"Goal", "Key Decisions", "Deliverable"} <= names:
        return False
    return all(sprint.get("items") for sprint in sprints)


def _section_line_spans(markdown: str) -> list[JSONDict]:
    parsed = body.parse(markdown)
    spans: list[JSONDict] = []
    lines = markdown.splitlines()
    for section in parsed.sections:
        heading = section.heading.rstrip("\r\n")
        start = next(
            (
                index
                for index, line in enumerate(lines, start=1)
                if line.strip() == heading.strip()
            ),
            None,
        )
        if start is not None:
            spans.append({"name": section.name, "start": start})
    for index, span in enumerate(spans):
        span["end"] = spans[index + 1]["start"] - 1 if index + 1 < len(spans) else len(lines)
    return spans


def _section_for_line(spans: list[JSONDict], line_number: int) -> str | None:
    for span in spans:
        if int(span["start"]) <= line_number <= int(span["end"]):
            return str(span["name"])
    return None


__all__ = [
    "GateResult",
    "evaluate_state_transition",
    "scan_lockdown_phrases",
]
