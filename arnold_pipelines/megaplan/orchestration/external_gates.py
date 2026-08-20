"""Shared external human-gate classification (review + execute parity).

A *human gate* is a blocking review obligation that is genuinely external to
the machine: it fails by design until an operator records a real acceptance
decision (e.g. North Star action NSA-1, ``add_human_halt``). Such gates must
never consume the review rework budget, must never be silently discarded, and
must never permit ``done``. Both the review handler (``handlers/review.py``)
and the execute rework admission (``orchestration/rework_admission.py``) use
this module so the two phases cannot develop different definitions of the
same gate.

Classification is field-aware and tolerant of case / ``-`` / ``_`` spelling
(``nsa-1``, ``NSA_1``, ``north-star-human-halt``). It deliberately matches
only the whole semantic markers — arbitrary prose containing the word
"human" is NOT a gate.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

HUMAN_GATE_MARKERS: frozenset[str] = frozenset(
    {"human_halt", "add_human_halt", "nsa-1"}
)

# Whole-marker matcher over normalized (lowercased, "-"->"_") text. The
# normalized forms are: human_halt, add_human_halt, nsa_1. Boundaries are
# non-alphanumeric so "nsa_10" or "non_human_haltx" never match.
_MARKER_RE = re.compile(
    r"(?:^|[^a-z0-9])(human_halt|add_human_halt|nsa_1)(?:$|[^a-z0-9])"
)

_GATE_STRING_FIELDS = ("id", "flag", "source", "action_type")


def _normalize(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_")


def contains_human_gate_marker(*values: Any) -> bool:
    """Return ``True`` if any value carries a whole human-gate marker.

    Mappings and nested sequences are recursed over their relevant string
    fields; plain strings are normalized and regex-matched.
    """
    for value in values:
        if isinstance(value, Mapping):
            for key in _GATE_STRING_FIELDS:
                if contains_human_gate_marker(value.get(key)):
                    return True
            continue
        if isinstance(value, (list, tuple, set, frozenset)):
            if any(contains_human_gate_marker(item) for item in value):
                return True
            continue
        normalized = _normalize(value)
        if not normalized:
            continue
        if _MARKER_RE.search(normalized):
            return True
    return False


def is_external_human_rework_item(item: Mapping[str, Any]) -> bool:
    """Classify a blocking rework item as an external human gate.

    Mirrors the execute-side admission markers (id/flag/source containing
    ``human_halt`` / ``nsa-1``) plus the north-star action surface.
    """
    target = item.get("target")
    target_id = target.get("id") if isinstance(target, Mapping) else None
    return contains_human_gate_marker(
        item.get("id"),
        target_id,
        item.get("flag_id"),
        item.get("source"),
        item.get("action_type"),
        item.get("criterion_id"),
        item.get("north_star_action_id"),
        item.get("issue"),
    )


def is_external_human_north_star_action(action: Mapping[str, Any]) -> bool:
    """Classify an unresolved North Star action as an external human gate.

    Only unresolved actions qualify; an action whose status is resolved /
    addressed / accepted is not a gate. ``add_human_halt`` is the canonical
    marker but ``nsa-1`` ids and human-halt sources are also recognized.
    """
    if action.get("resolved") is True:
        return False
    status = str(action.get("status") or "").strip().lower()
    if status in {"resolved", "addressed", "accepted"}:
        return False
    return contains_human_gate_marker(
        action.get("id"),
        action.get("flag"),
        action.get("source"),
        action.get("action_type"),
    )


def as_external_gate(
    item: Mapping[str, Any],
    *,
    criterion_id: str | None = None,
) -> dict[str, Any]:
    """Normalize a human-gate rework item / North Star action into a gate record."""
    raw_id = str(
        item.get("id")
        or item.get("criterion_id")
        or item.get("north_star_action_id")
        or ""
    )
    resolved_criterion = (
        criterion_id
        or str(item.get("criterion_id") or "")
        or raw_id
        or "NSA-1"
    )
    return {
        "id": raw_id or resolved_criterion,
        "criterion_id": resolved_criterion,
        "action_type": str(item.get("action_type") or "add_human_halt"),
        "agent_actionable": False,
        "classification": "external_gate",
        "status": "deferred_human",
        "reason": "requires an explicit human acceptance decision",
    }


def dedupe_external_gates(
    gates: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Return gates keyed by criterion id (first occurrence wins)."""
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for gate in gates:
        key = str(gate.get("criterion_id") or gate.get("id") or "")
        if key in seen:
            continue
        seen.add(key)
        result.append(dict(gate))
    return result


__all__ = [
    "HUMAN_GATE_MARKERS",
    "as_external_gate",
    "contains_human_gate_marker",
    "dedupe_external_gates",
    "is_external_human_north_star_action",
    "is_external_human_rework_item",
]
