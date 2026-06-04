"""Megaplan-owned planning decision literals and routing helpers.

This module is the **only** home for Megaplan planning decision literals
in the generic routing layer.  Every planning decision key, override
spelling mapping, and gate-edge construction helper lives here.

Consumers (builder, compilers, pattern_topology) import these helpers
instead of constructing ``kind='gate'`` edges with ``Edge.label=''``
by hand.

Uses Arnold's policy-neutral :func:`~arnold.pipeline.pattern_topology.decision_edges`
to build edges — no local ``Edge`` construction for decision/override
dispatch.
"""

from __future__ import annotations

from typing import Mapping

from arnold.pipeline.pattern_topology import decision_edges
from arnold.pipeline.types import Edge

# ---------------------------------------------------------------------------
# Planning decision literals
# ---------------------------------------------------------------------------

PLAN_PROCEED: str = "proceed"
PLAN_ITERATE: str = "iterate"
PLAN_TIEBREAKER: str = "tiebreaker"
PLAN_ESCALATE: str = "escalate"

PLANNING_DECISIONS: tuple[str, str, str, str] = (
    PLAN_PROCEED,
    PLAN_ITERATE,
    PLAN_TIEBREAKER,
    PLAN_ESCALATE,
)

# ---------------------------------------------------------------------------
# Override spelling — internal id ↔ CLI label
# ---------------------------------------------------------------------------

OVERRIDE_FORCE_PROCEED: str = "force_proceed"
OVERRIDE_FORCE_PROCEED_CLI: str = "force-proceed"

# Map internal override ids → CLI labels.
OVERRIDE_SPELLING: dict[str, str] = {
    OVERRIDE_FORCE_PROCEED: OVERRIDE_FORCE_PROCEED_CLI,
}

# Reverse mapping: CLI label → internal id.
_OVERRIDE_SPELLING_REVERSE: dict[str, str] = {
    v: k for k, v in OVERRIDE_SPELLING.items()
}


def cli_to_internal_override(cli_label: str) -> str:
    """Map a CLI override label (e.g. ``'force-proceed'``) to the
    internal id (``'force_proceed'``).  Returns *cli_label* unchanged
    when no mapping exists."""
    return _OVERRIDE_SPELLING_REVERSE.get(cli_label, cli_label)


def internal_to_cli_override(internal_id: str) -> str:
    """Map an internal override id (e.g. ``'force_proceed'``) to the
    CLI label (``'force-proceed'``).  Returns *internal_id* unchanged
    when no mapping exists."""
    return OVERRIDE_SPELLING.get(internal_id, internal_id)


# ---------------------------------------------------------------------------
# Four-way planning gate edges
# ---------------------------------------------------------------------------


def planning_gate_edges(
    *,
    on_proceed: str,
    on_iterate: str,
    on_tiebreaker: str,
    on_escalate: str,
    gate_extra_edges: tuple[Edge, ...] = (),
) -> tuple[Edge, ...]:
    """Build the four planning-gate decision edges.

    Returns ``kind='decision'`` edges for all four planning labels,
    plus any *gate_extra_edges* appended at the end.

    Args:
        on_proceed: Target stage for the ``proceed`` decision.
        on_iterate: Target stage for the ``iterate`` decision.
        on_tiebreaker: Target stage for the ``tiebreaker`` decision.
        on_escalate: Target stage for the ``escalate`` decision.
        gate_extra_edges: Additional edges appended after the four
            decision edges.

    Returns:
        A tuple of :class:`Edge` objects (decision edges first, then
        *gate_extra_edges*).
    """
    return decision_edges(
        decisions={
            PLAN_PROCEED: on_proceed,
            PLAN_ITERATE: on_iterate,
            PLAN_TIEBREAKER: on_tiebreaker,
            PLAN_ESCALATE: on_escalate,
        },
        fallback_edges=gate_extra_edges,
    )


# ---------------------------------------------------------------------------
# Tiebreaker edges — populated labels (NOT empty strings)
# ---------------------------------------------------------------------------


def tiebreaker_edges(
    *,
    on_iterate: str,
    on_proceed: str,
    on_escalate: str,
) -> tuple[Edge, ...]:
    """Build tiebreaker decision edges with populated labels.

    The tiebreaker produces one of three recommendations: *iterate*,
    *proceed*, or *escalate*.  Each edge carries ``kind='decision'``
    and a populated ``label`` (never an empty string).

    Args:
        on_iterate: Target stage for the ``iterate`` tiebreaker result.
        on_proceed: Target stage for the ``proceed`` tiebreaker result.
        on_escalate: Target stage for the ``escalate`` tiebreaker result.

    Returns:
        A tuple of three :class:`Edge` objects with
        ``kind='decision'`` and populated labels.
    """
    return decision_edges(
        decisions={
            PLAN_ITERATE: on_iterate,
            PLAN_PROCEED: on_proceed,
            PLAN_ESCALATE: on_escalate,
        },
    )


# ---------------------------------------------------------------------------
# Planning override edges
# ---------------------------------------------------------------------------


def planning_override_edges(
    overrides: Mapping[str, str],
) -> tuple[Edge, ...]:
    """Build override edges from a mapping of internal override ids → targets.

    Each override edge carries ``kind='override'`` with
    ``label='override <internal_id>'``.

    Args:
        overrides: Mapping of internal override id (e.g.
            ``'force_proceed'``) → target stage name.

    Returns:
        A tuple of ``kind='override'`` :class:`Edge` objects.
    """
    return decision_edges(decisions={}, overrides=overrides)


# ---------------------------------------------------------------------------
# Critique / revise / gate wrapper
# ---------------------------------------------------------------------------


def critique_revise_gate_routing(
    *,
    on_proceed: str,
    on_iterate: str,
    on_tiebreaker: str,
    on_escalate: str,
    on_revise: str = "critique",
    gate_extra_edges: tuple[Edge, ...] = (),
) -> dict[str, tuple[Edge, ...]]:
    """Return routing edge tuples for the critique→gate→revise cycle.

    Does **not** construct :class:`Stage` objects — returns only the
    edge tuples that callers wire into their pipeline.  This keeps the
    module focused on routing policy; stage construction stays in the
    caller (builder / pattern_topology).

    Returns a ``dict`` with keys ``'critique'``, ``'gate'``, and
    ``'revise'``, each mapping to a ``tuple[Edge, ...]``:

    * ``critique``: a single ``kind='normal'`` edge targeting ``'gate'``.
    * ``gate``: the four planning decision edges (via
      :func:`planning_gate_edges`) plus any *gate_extra_edges*.
    * ``revise``: a single ``kind='normal'`` edge targeting
      *on_revise* (default ``'critique'``, forming the loop).

    Args:
        on_proceed: Target for ``proceed`` decision.
        on_iterate: Target for ``iterate`` decision.
        on_tiebreaker: Target for ``tiebreaker`` decision.
        on_escalate: Target for ``escalate`` decision.
        on_revise: Target for the revise stage's edge (default
            ``'critique'``).
        gate_extra_edges: Extra edges for the gate stage.

    Returns:
        A ``dict[str, tuple[Edge, ...]]`` with keys ``critique``,
        ``gate``, and ``revise``.
    """
    return {
        "critique": (Edge(label="gate", target="gate", kind="normal"),),
        "gate": planning_gate_edges(
            on_proceed=on_proceed,
            on_iterate=on_iterate,
            on_tiebreaker=on_tiebreaker,
            on_escalate=on_escalate,
            gate_extra_edges=gate_extra_edges,
        ),
        "revise": (Edge(label="critique", target=on_revise, kind="normal"),),
    }


__all__ = [
    "OVERRIDE_FORCE_PROCEED",
    "OVERRIDE_FORCE_PROCEED_CLI",
    "OVERRIDE_SPELLING",
    "PLANNING_DECISIONS",
    "PLAN_ESCALATE",
    "PLAN_ITERATE",
    "PLAN_PROCEED",
    "PLAN_TIEBREAKER",
    "cli_to_internal_override",
    "critique_revise_gate_routing",
    "internal_to_cli_override",
    "planning_gate_edges",
    "planning_override_edges",
    "tiebreaker_edges",
]
