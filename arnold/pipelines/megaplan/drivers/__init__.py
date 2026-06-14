"""Driver selection surface for the unified-dispatch path (M3 Step 10).

Exposes:
    - ``Substrate``  : Literal["in_process", "subprocess_isolated"]
    - ``Topology``   : Literal["linear", "fanout", "dag"]
    - ``SUBSTRATES`` / ``TOPOLOGIES``: frozenset of valid literals
    - ``select_driver(substrate, topology)``: gated on ``unified_dispatch_on()``.
      Returns ``None`` when the master flag is OFF (preserves legacy behavior);
      otherwise returns a driver instance and **populates** the module-level
      ``current_substrate()`` accessor.
    - ``current_substrate() -> Substrate | None``: static read of the substrate
      pinned by the most recent successful ``select_driver`` call (cleared by
      ``reset_substrate()``). Available from step 0 onward; ``None`` before any
      selection.
"""

from __future__ import annotations

from typing import Literal, Optional

from arnold.pipelines.megaplan._pipeline.flags import unified_dispatch_on

from .in_process import InProcessDriver
from .subprocess_isolated import SubprocessIsolatedDriver

Substrate = Literal["in_process", "subprocess_isolated"]
Topology = Literal["linear", "fanout", "dag"]

SUBSTRATES: frozenset[str] = frozenset({"in_process", "subprocess_isolated"})
TOPOLOGIES: frozenset[str] = frozenset({"linear", "fanout", "dag"})

_current_substrate: Optional[str] = None


def current_substrate() -> Optional[str]:
    """Return the substrate pinned by the last successful ``select_driver``.

    ``None`` before any selection or after ``reset_substrate()``.  Static —
    not derived from runtime state; populated at select time.
    """
    return _current_substrate


def reset_substrate() -> None:
    """Clear the pinned substrate (test-only convenience)."""
    global _current_substrate
    _current_substrate = None


def select_driver(substrate: str, topology: str):
    """Select a driver for ``(substrate, topology)``.

    Gated on :func:`megaplan._pipeline.flags.unified_dispatch_on`.  When the
    master flag is OFF, returns ``None`` and does **not** mutate
    ``current_substrate()`` — legacy subprocess-supervision path stays
    authoritative.

    When ON, validates the literals, pins ``current_substrate()`` to
    *substrate*, and returns an instance of the corresponding driver.
    """
    if substrate not in SUBSTRATES:
        raise ValueError(f"unknown substrate: {substrate!r}")
    if topology not in TOPOLOGIES:
        raise ValueError(f"unknown topology: {topology!r}")
    if not unified_dispatch_on():
        return None
    global _current_substrate
    _current_substrate = substrate
    if substrate == "in_process":
        return InProcessDriver()
    return SubprocessIsolatedDriver()



__all__ = [
    "Substrate",
    "Topology",
    "SUBSTRATES",
    "TOPOLOGIES",
    "InProcessDriver",
    "SubprocessIsolatedDriver",
    "current_substrate",
    "reset_substrate",
    "select_driver",
]
