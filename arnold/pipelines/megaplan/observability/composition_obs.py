"""M4 T25 — CompositionObservability interface.

A non-plan composition (a chain step, a bake-off arm, anything that
runs without a plan_dir) needs to emit the same observability beats a
plan-scoped pipeline emits.  This module defines the shared interface
those non-plan composers can route through; the legacy plan-scoped
read path in :mod:`megaplan.observability.trace` is preserved
verbatim behind the ``UNIFIED_EMIT`` flag.

Interface beats
~~~~~~~~~~~~~~~
* :meth:`CompositionObservability.step_boundary` — start/end of a step
* :meth:`CompositionObservability.decision`     — gate / classify outcome
* :meth:`CompositionObservability.retry`        — retry + class
* :meth:`CompositionObservability.budget_delta` — spend / lease delta
* :meth:`CompositionObservability.piece_identity` — which composable piece
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional, Protocol


class CompositionObservability(Protocol):
    def step_boundary(self, *, name: str, kind: str, payload: Optional[dict] = None) -> None: ...
    def decision(self, *, name: str, rationale: str, payload: Optional[dict] = None) -> None: ...
    def retry(self, *, retry_class: str, payload: Optional[dict] = None) -> None: ...
    def budget_delta(self, *, kind: str, delta_usd: float, payload: Optional[dict] = None) -> None: ...
    def piece_identity(self, *, piece_id: str, payload: Optional[dict] = None) -> None: ...


@dataclass
class InMemoryCompositionObs:
    """Reference implementation used by tests + non-plan composers.

    Stores beats in-memory so callers (and :mod:`trace`) can read the
    composition's history without a plan_dir.
    """

    events: List[dict] = field(default_factory=list)

    def _emit(self, kind: str, payload: Optional[dict]) -> None:
        self.events.append({"kind": kind, "payload": dict(payload or {})})

    def step_boundary(self, *, name: str, kind: str, payload: Optional[dict] = None) -> None:
        pl = {"name": name, "boundary": kind, **(payload or {})}
        self._emit("step_boundary", pl)

    def decision(self, *, name: str, rationale: str, payload: Optional[dict] = None) -> None:
        pl = {"name": name, "rationale": rationale, **(payload or {})}
        self._emit("decision", pl)

    def retry(self, *, retry_class: str, payload: Optional[dict] = None) -> None:
        self._emit("retry", {"retry_class": retry_class, **(payload or {})})

    def budget_delta(self, *, kind: str, delta_usd: float, payload: Optional[dict] = None) -> None:
        self._emit("budget_delta", {"kind": kind, "delta_usd": float(delta_usd), **(payload or {})})

    def piece_identity(self, *, piece_id: str, payload: Optional[dict] = None) -> None:
        self._emit("piece_identity", {"piece_id": piece_id, **(payload or {})})


def trace_from_composition(obs: InMemoryCompositionObs) -> List[dict]:
    """Read trace beats out of an in-memory CompositionObservability.

    The legacy ``trace.read_events`` + ``find_plan_dir`` path stays live
    when ``UNIFIED_EMIT=0`` (or unset); this read surface is the
    flag-on alternative for non-plan compositions.
    """
    return list(obs.events)


__all__ = [
    "CompositionObservability",
    "InMemoryCompositionObs",
    "trace_from_composition",
]
