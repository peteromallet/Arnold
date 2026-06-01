"""M4 T5 — Dispatcher Protocol + DispatchRequest/DispatchResult.

The Dispatcher is the single seam every downstream backend (Hermes, Codex,
Shannon, Bash, local-tool) must implement once the unified-dispatch strangler
fully lands.  Today this module only defines the shapes — wiring happens in
later M4 tasks.

DispatchRequest deliberately carries *only* the data a dispatcher needs to run
one envelope:

* ``envelope`` — the :class:`megaplan._pipeline.envelope.RunEnvelope` (carries
  taint, cost, lineage, deadline, lease, fencing, capacity_grant — and so the
  Dispatcher does NOT need separate cost / rate / recovery "god-fields").
* ``prompt_override`` — optional caller-side prompt body.
* ``shim_state`` — opaque dict consumed by the dispatcher's shim layer.
* ``liveness_sink`` — callable that receives liveness heartbeats so the
  caller can keep idle-watchdogs ticking.  This is the ONE cross-cutting
  channel a dispatcher exposes back to the caller.

Notably *absent* from DispatchRequest: ``cost``, ``rate_limit``, ``recovery``,
``budget``.  These belong to the Governor, BudgetAuthority and RecoveryPolicy
seams respectively — bundling them into the Dispatcher contract is the exact
god-field anti-pattern this protocol exists to prevent.

DispatchResult carries the typed result, the realized ``cost``, and an opaque
``session_ref`` the caller can use to reconnect or cancel.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Protocol

from megaplan._pipeline.envelope import RunEnvelope


LivenessSink = Callable[[dict], None]


@dataclass(frozen=True)
class DispatchRequest:
    """Inputs a Dispatcher consumes for one envelope run.

    No cost / rate / recovery / budget fields — those are carried elsewhere
    (Governor / BudgetAuthority / RecoveryPolicy).
    """

    envelope: RunEnvelope
    prompt_override: Optional[str] = None
    shim_state: dict = field(default_factory=dict)
    liveness_sink: Optional[LivenessSink] = None


@dataclass(frozen=True)
class DispatchResult:
    """Outputs from one Dispatcher.run() call."""

    result: Any
    cost: float = 0.0
    session_ref: Any = None


class Dispatcher(Protocol):
    """Every downstream dispatch backend implements this single method."""

    def run(self, request: DispatchRequest) -> DispatchResult:  # pragma: no cover
        ...
