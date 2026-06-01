"""Planning-only bindings for the four-literal recommendation type.

Outside of :mod:`megaplan._pipeline.types` (the definition site) and
:mod:`megaplan._pipeline.validator` (the structural validator), this
is the ONLY module in the SDK allowed to name the planning binding's
recommendation literal.

The planning subloop (``SubloopStep``) and the planning tiebreaker
(``TiebreakerStep``) carry typed-``Any`` ``promote`` callables; when a
caller wants the legacy typed literal mapping they route through
:func:`planning_promote` (state → recommendation) or
:func:`planning_reduce` (fan-out :class:`ReduceResult` → recommendation).
"""

from __future__ import annotations

from typing import Any

from megaplan._pipeline.types import GateRecommendation, ReduceResult

EVALUAND_GATE_ARTIFACT_KEY = "evaluand"
"""Adapter key for planning GateResult consumers that read Evaluand artifacts."""

__all__ = [
    "EVALUAND_GATE_ARTIFACT_KEY",
    "GateRecommendation",
    "planning_promote",
    "planning_reduce",
]


_LITERALS: frozenset[str] = frozenset(
    {"proceed", "iterate", "tiebreaker", "escalate"}
)


def planning_promote(state: dict[str, Any]) -> GateRecommendation:
    """Map a planning child pipeline's terminal state to a typed literal.

    Mirrors the legacy planning subloop mapping:

    * ``current_state == "critiqued"`` → ``"iterate"``
    * ``current_state == "aborted"``  → ``"escalate"``
    * otherwise                         → ``"proceed"``

    Any other ``current_state`` value falls back to ``"proceed"`` so
    callers always receive one of the four typed literals.
    """
    final = state.get("current_state", "")
    if final == "critiqued":
        return "iterate"
    if final == "aborted":
        return "escalate"
    return "proceed"


def planning_reduce(aggregate: ReduceResult) -> GateRecommendation:
    """Collapse a fan-out :class:`ReduceResult` into a planning literal.

    Reads ``aggregate.label`` first, then the largest entry in
    ``aggregate.tally``.  Any value not in
    ``{"proceed", "iterate", "tiebreaker", "escalate"}`` falls back to
    ``"proceed"``.
    """
    candidate: Any = aggregate.label
    if candidate is None and aggregate.tally:
        candidate = max(aggregate.tally.items(), key=lambda kv: kv[1])[0]
    if isinstance(candidate, str) and candidate in _LITERALS:
        return candidate  # type: ignore[return-value]
    return "proceed"
