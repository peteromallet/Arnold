"""Forward declarations for M2 (typed Port / RoutingKey) and M3 (realized Graph).

Every export carries a # TODO(M2/M3) marker — this module is a contract
surface, not a full implementation. M2 will formalize RoutingKey/Port;
M3 will provide the realized Graph. M5a's node library binds to these
symbols so downstream code compiles against the forward contract.

SD2: _bridge_recommendation_to_routing_key collides proceed→kind='advance'
and tiebreaker→kind='advance'. Disambiguation is via .name, which is the
primary key for downstream dispatch.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Protocol

from megaplan._pipeline.types import GateRecommendation, ReduceResult  # TODO(M2): finalize ReduceResult shape

# ── RoutingKey ─────────────────────────────────────────────────────────
# TODO(M2): M2 will freeze this as the sole routing type; see
# briefs/epic-pipeline-unification/m2-types-and-port.md:80-85.

RoutingKeyKind = Literal["advance", "revise", "restore", "escalate", "select", "custom"]


@dataclass(frozen=True)
class RoutingKey:
    """TODO(M2): Frozen routing-key type — the ONE type downstream dispatch cites.

    M2 (W10) defines this as a frozen type with content-type
    ``application/x-routing-key+json``, surfaced as a ``value``-kind Port.
    """

    name: str
    kind: RoutingKeyKind = "advance"


# ── Port Protocol ──────────────────────────────────────────────────────
# TODO(M2): M2 will ship the full typed Port; see
# briefs/epic-pipeline-unification/m2-types-and-port.md:44-51.

PortKind = Literal["value", "artifact", "stream"]


class Port(Protocol):
    """TODO(M2): Protocol for the typed Port (kind × content-type × schema)."""

    name: str
    kind: PortKind
    content_type: str
    schema: Any
    cardinality: int
    version: int


# ── Graph Protocol ─────────────────────────────────────────────────────
# TODO(M3): M3 will ship the realized graph; see
# briefs/epic-pipeline-unification/ (M3 brief TBD).

class Graph(Protocol):
    """TODO(M3): Realized graph Protocol — nodes, edges, and resolution."""


# ── restore_and_diverge sentinel ────────────────────────────────────────
# TODO(M2/M3): restore_and_diverge becomes one kind="restore" edge
# in M2's RoutingKey (EPIC §206), not a parallel map.


class _RestoreAndDivergeType:
    """Sentinel singleton for the restore-and-diverge routing edge.

    Under M2, this becomes a RoutingKey(name="restore_and_diverge", kind="restore").
    Under M3, the realized graph resolves it to the correct diverging subgraph.
    """

    _instance = None

    # TODO(M3): when M3 maps the restore_and_diverge consequence, this
    # name will become 'restore_and_diverge'.  For M5a the node-library
    # escalation edge uses the literal 'escalate' so it routes through
    # the existing gate-dispatch path.
    name: str = "escalate"

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self):
        return "restore_and_diverge"

    def to_routing_key(self) -> RoutingKey:
        """TODO(M3): project to the canonical M2 RoutingKey."""
        return RoutingKey(name="restore_and_diverge", kind="restore")


restore_and_diverge = _RestoreAndDivergeType()


# ── Bridge: legacy GateRecommendation → RoutingKey ─────────────────────
# TODO(M2/M3): This bridge converts the planning-app's 4-verdict labels
# into the typed RoutingKey surface. The planning binding (M2 W5) will
# be the authoritative producer; this bridge exists so M5a node-library
# code can compile against RoutingKey before M2 lands.
#
# Collision note (SD2): both proceed and tiebreaker map to kind='advance'.
# Disambiguation is via .name — downstream dispatch that needs kind-level
# distinction MUST read .name, not .kind alone.

def _bridge_recommendation_to_routing_key(
    recommendation: GateRecommendation,
) -> RoutingKey:
    """Convert a legacy GateRecommendation literal to a RoutingKey.

    Mapping:
      'proceed'    → RoutingKey(name='proceed',    kind='advance')
      'iterate'    → RoutingKey(name='iterate',    kind='revise')
      'tiebreaker' → RoutingKey(name='tiebreaker', kind='advance')
      'escalate'   → RoutingKey(name='escalate',   kind='escalate')

    Note: proceed and tiebreaker both map to kind='advance'. This is
    intentional — disambiguation at the dispatch level uses .name.
    """
    _MAP: dict[GateRecommendation, RoutingKey] = {
        "proceed": RoutingKey(name="proceed", kind="advance"),
        "iterate": RoutingKey(name="iterate", kind="revise"),
        "tiebreaker": RoutingKey(name="tiebreaker", kind="advance"),
        "escalate": RoutingKey(name="escalate", kind="escalate"),
    }
    if recommendation not in _MAP:
        raise ValueError(
            f"Unknown GateRecommendation {recommendation!r}; "
            f"expected one of {list(_MAP.keys())}"
        )
    return _MAP[recommendation]


__all__ = [
    "RoutingKey",
    "RoutingKeyKind",
    "Port",
    "PortKind",
    "Graph",
    "restore_and_diverge",
    "_bridge_recommendation_to_routing_key",
]
