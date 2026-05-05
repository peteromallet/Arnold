"""Arnold-style review lockdown checks for Store-backed editorial flows."""

from __future__ import annotations

import re
from dataclasses import dataclass

LOCKDOWN_REVIEW_STATES = frozenset({"planned", "archived"})
LOCKDOWN_PHRASE_RE = re.compile(
    r"\b("
    r"TBD|to be decided|to be determined|we'll see|figure out later|"
    r"tunable|depends on what surfaces|can adjust later|decide later"
    r")\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class LockdownFinding:
    phrase: str
    line: int


def _is_open_questions_heading(line: str) -> bool:
    return bool(re.match(r"^#{1,6}\s+open questions\s*$", line.strip(), re.IGNORECASE))


def _is_heading(line: str) -> bool:
    return bool(re.match(r"^#{1,6}\s+", line.strip()))


def scan_lockdown_phrases(body: str) -> list[LockdownFinding]:
    """Find lockdown-blocking placeholder phrases outside code/open questions."""

    findings: list[LockdownFinding] = []
    in_fence = False
    in_open_questions = False
    for index, line in enumerate(body.splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if _is_open_questions_heading(line):
            in_open_questions = True
            continue
        if in_open_questions and _is_heading(line):
            in_open_questions = False
        if in_open_questions:
            continue
        for match in LOCKDOWN_PHRASE_RE.finditer(line):
            findings.append(LockdownFinding(phrase=match.group(0), line=index))
    return findings


def ensure_unlocked_for_edit(*, epic_state: str, operation: str) -> None:
    """Reject mutating operations that Arnold freezes after review handoff."""

    from .errors import EditorialWorkflowError

    if epic_state in LOCKDOWN_REVIEW_STATES:
        raise EditorialWorkflowError(
            f"{operation} is locked while epic is in state '{epic_state}'",
            details={"state": epic_state, "operation": operation},
        )
