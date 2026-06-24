"""Creative stance validation helpers."""

from __future__ import annotations

import re
from typing import Any

STANCE_HEDGING_VERBS = (
    "considered",
    "tried",
    "attempted",
    "sought to",
    "aimed to",
    "worked to",
)

STANCE_CLAIM_MARKERS = (
    "because",
    "refused",
    "chose",
    "killed",
    "kept",
    "fought",
    "insisted",
    "picked",
)

_FIRST_PERSON_RE = re.compile(r"\b(i|me|my|mine|we|us|our|ours)\b", re.IGNORECASE)


def _stance_text(stance: dict[str, Any]) -> str:
    return " ".join(
        str(stance.get(field, "")).strip()
        for field in ("challenge_engaged", "angle_taken", "what_changed")
        if str(stance.get(field, "")).strip()
    )


def validate_stance(stance: dict[str, Any]) -> list[str]:
    """Return soft validation violations for a creative-work stance."""
    if not isinstance(stance, dict):
        return ["stance must be a structured object"]
    text = _stance_text(stance)
    lowered = text.lower()
    violations: list[str] = []
    if len(text.split()) > 50:
        violations.append("stance exceeds 50 words")
    if not _FIRST_PERSON_RE.search(text):
        violations.append("stance must use first person")
    for verb in STANCE_HEDGING_VERBS:
        if re.search(rf"\b{re.escape(verb)}\b", lowered):
            violations.append(f"stance uses hedging verb: {verb}")
    if not any(re.search(rf"\b{re.escape(marker)}\b", lowered) for marker in STANCE_CLAIM_MARKERS):
        violations.append("stance must include a claim marker")
    return violations


__all__ = ["STANCE_CLAIM_MARKERS", "STANCE_HEDGING_VERBS", "validate_stance"]
