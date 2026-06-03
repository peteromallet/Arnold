"""Deprecated re-export bridge for megaplan._pipeline._forward_m2_m3.

Forward declarations have been canonicalized in
:mod:`arnold.pipeline.types` (``RoutingKey``, ``RoutingKeyKind``).

Import from there directly.  The ``_bridge_recommendation_to_routing_key``
bridge function and ``restore_and_diverge`` sentinel are kept local
in this module for backward compatibility.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Any, Literal, Protocol

warnings.warn(
    "megaplan._pipeline._forward_m2_m3 is deprecated; "
    "import RoutingKey/RoutingKeyKind from arnold.pipeline.types instead.",
    DeprecationWarning,
    stacklevel=2,
)

# ── Canonical RoutingKey from arnold ───────────────────────────────────
from arnold.pipeline.types import RoutingKey, RoutingKeyKind  # noqa: E402, F401

# ── Local imports for bridge function ──────────────────────────────────
from megaplan._pipeline.types import (  # noqa: E402
    GateRecommendation,
    ReduceResult,
)

# ── Port Protocol (kept local; arnold has a different Port dataclass) ──

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

class Graph(Protocol):
    """TODO(M3): Realized graph Protocol — nodes, edges, and resolution."""


# ── restore_and_diverge sentinel ────────────────────────────────────────

class _RestoreAndDivergeType:
    """Sentinel singleton for the restore-and-diverge routing edge.

    Under M2, this becomes a RoutingKey(name="restore_and_diverge", kind="restore").
    Under M3, the realized graph resolves it to the correct diverging subgraph.
    """

    _instance = None

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
