"""Prompting and parsing helpers for GPT second opinions."""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any, Sequence


JSONDict = dict[str, Any]
_SCORE_RE = re.compile(r"Score:\s*(\d{1,2})\s*/\s*10", re.IGNORECASE)
_VERDICT_RE = re.compile(r"Verdict:\s*(.+)", re.IGNORECASE)


@dataclass(frozen=True)
class ParsedSecondOpinion:
    score: int
    summary: str
    verdict: str
    strengths: list[str]
    holes: list[JSONDict]


def build_second_opinion_payload(
    *,
    epic: JSONDict,
    checklist: Sequence[JSONDict],
    sprints: Sequence[JSONDict],
    recent_feedback: Sequence[JSONDict],
    focus_areas: Sequence[str] | None = None,
    scoring_override: str | None = None,
) -> JSONDict:
    focus = [str(item).strip() for item in focus_areas or [] if str(item).strip()]
    rubric = scoring_override or (
        "Score PM-handoff readiness from 0 to 10. 9-10 means a PM can pick it up cold; "
        "7-8 means mostly usable; 5-6 means material gaps; 3-4 means push it back; "
        "0-2 means foundational rethink."
    )
    user_payload = {
        "task": "Audit this epic as a second-opinion reviewer.",
        "required_output": {
            "score": "integer 0-10",
            "summary": "1-3 sentence distillation",
            "verdict": "one-line verdict",
            "strengths": ["2-4 concise strengths"],
            "holes": [
                {
                    "gap": "specific gap",
                    "why_it_matters": "impact on PM handoff",
                    "suggested_fix": "concrete fix",
                    "severity": "low|medium|high",
                }
            ],
        },
        "scoring_rubric": rubric,
        "focus_areas": focus,
        "epic": {
            "id": epic.get("id"),
            "title": epic.get("title"),
            "goal": epic.get("goal"),
            "state": epic.get("state"),
            "body": epic.get("body"),
        },
        "checklist": [
            {
                "content": item.get("content"),
                "status": item.get("status"),
                "skip_reason": item.get("skip_reason"),
            }
            for item in checklist
        ],
        "sprints": sprints,
        "recent_feedback": [
            {
                "kind": item.get("kind"),
                "content": item.get("content"),
                "source": item.get("source"),
            }
            for item in recent_feedback
        ],
    }
    return {
        "input": [
            {
                "role": "system",
                "content": (
                    "You are an exacting product-planning auditor. Return only JSON matching "
                    "the requested structure; do not include markdown fences."
                ),
            },
            {"role": "user", "content": json.dumps(user_payload, sort_keys=True)},
        ]
    }


def parse_second_opinion(raw_response: str) -> ParsedSecondOpinion:
    raw = raw_response.strip()
    if not raw:
        raise ValueError("second-opinion response was empty")
    try:
        parsed = json.loads(_strip_json_fence(raw))
    except json.JSONDecodeError:
        return _parse_text_response(raw)
    if not isinstance(parsed, dict):
        raise ValueError("second-opinion response must be an object")
    return _parse_mapping(parsed)


def proposed_checklist_items(
    holes: Sequence[JSONDict],
    *,
    source_second_opinion_id: str | None = None,
) -> list[JSONDict]:
    items: list[JSONDict] = []
    for hole in holes:
        gap = str(hole.get("gap") or "").strip()
        fix = str(hole.get("suggested_fix") or "").strip()
        if not gap and not fix:
            continue
        content = fix or f"Address second-opinion gap: {gap}"
        items.append(
            {
                "content": content,
                "status": "open",
                "source": "second_opinion",
                "source_second_opinion_id": source_second_opinion_id,
                "rationale": gap,
                "severity": hole.get("severity") or "medium",
            }
        )
    return items


def _parse_mapping(value: JSONDict) -> ParsedSecondOpinion:
    score = value.get("score")
    if not isinstance(score, int) or isinstance(score, bool) or score < 0 or score > 10:
        raise ValueError("second-opinion score must be an integer from 0 to 10")
    verdict = str(value.get("verdict") or "").strip()
    if not verdict:
        raise ValueError("second-opinion verdict is required")
    holes_value = value.get("holes")
    if not isinstance(holes_value, list):
        raise ValueError("second-opinion holes must be a list")
    strengths_value = value.get("strengths") or []
    if not isinstance(strengths_value, list):
        raise ValueError("second-opinion strengths must be a list")
    holes = [_normalize_hole(item) for item in holes_value]
    summary = str(value.get("summary") or _summary_from(verdict, holes)).strip()
    if not summary:
        raise ValueError("second-opinion summary is required")
    return ParsedSecondOpinion(
        score=score,
        summary=summary,
        verdict=verdict,
        strengths=[str(item).strip() for item in strengths_value if str(item).strip()],
        holes=holes,
    )


def _parse_text_response(raw: str) -> ParsedSecondOpinion:
    score_match = _SCORE_RE.search(raw)
    if not score_match:
        raise ValueError("second-opinion score must be present as Score: X/10")
    score = int(score_match.group(1))
    if score < 0 or score > 10:
        raise ValueError("second-opinion score must be an integer from 0 to 10")
    verdict_match = _VERDICT_RE.search(raw)
    verdict = verdict_match.group(1).strip() if verdict_match else ""
    if not verdict:
        raise ValueError("second-opinion verdict is required")
    strengths = _bullet_section(raw, "Strengths")
    hole_lines = _bullet_section(raw, "Holes")
    holes = [_normalize_hole(line) for line in hole_lines]
    return ParsedSecondOpinion(
        score=score,
        summary=_summary_from(verdict, holes),
        verdict=verdict,
        strengths=strengths,
        holes=holes,
    )


def _normalize_hole(value: Any) -> JSONDict:
    if isinstance(value, str):
        text = value.strip()
        if not text:
            raise ValueError("second-opinion holes cannot contain empty items")
        gap, why, fix = _split_hole_text(text)
        return {
            "gap": gap,
            "why_it_matters": why,
            "suggested_fix": fix,
            "severity": "medium",
        }
    if not isinstance(value, dict):
        raise ValueError("second-opinion holes must be strings or objects")
    gap = str(value.get("gap") or value.get("title") or "").strip()
    why = str(value.get("why_it_matters") or value.get("why") or "").strip()
    fix = str(value.get("suggested_fix") or value.get("fix") or "").strip()
    severity = str(value.get("severity") or "medium").strip().lower()
    if not gap or not fix:
        raise ValueError("second-opinion hole objects require gap and suggested_fix")
    if severity not in {"low", "medium", "high"}:
        severity = "medium"
    return {
        "gap": gap,
        "why_it_matters": why,
        "suggested_fix": fix,
        "severity": severity,
    }


def _split_hole_text(text: str) -> tuple[str, str, str]:
    pieces = [piece.strip() for piece in re.split(r";", text, maxsplit=2)]
    gap_part = pieces[0]
    gap, sep, why = gap_part.partition(":")
    fix = pieces[2] if len(pieces) > 2 else (pieces[1] if len(pieces) > 1 else "")
    return (gap.strip(), why.strip() if sep else "", fix.strip() or text)


def _bullet_section(raw: str, name: str) -> list[str]:
    pattern = re.compile(
        rf"^{re.escape(name)}:\s*$([\s\S]*?)(?=^[A-Za-z][A-Za-z ]+:\s*$|\Z)",
        re.IGNORECASE | re.MULTILINE,
    )
    match = pattern.search(raw)
    if not match:
        return []
    lines = []
    for line in match.group(1).splitlines():
        stripped = line.strip()
        if stripped.startswith(("-", "*")):
            item = stripped[1:].strip()
            if item:
                lines.append(item)
    return lines


def _summary_from(verdict: str, holes: Sequence[JSONDict]) -> str:
    if holes:
        return f"{verdict} Key gaps: " + "; ".join(str(hole.get("gap")) for hole in holes[:3])
    return verdict


def _strip_json_fence(raw: str) -> str:
    if raw.startswith("```"):
        lines = raw.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return raw


__all__ = [
    "ParsedSecondOpinion",
    "build_second_opinion_payload",
    "parse_second_opinion",
    "proposed_checklist_items",
]
