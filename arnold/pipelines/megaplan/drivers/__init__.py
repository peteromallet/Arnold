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
    - ``scoped_legacy_audit()``: scoped audit over ``megaplan/_pipeline/`` and
    ``megaplan/drivers/`` only. Returns the count of forbidden direct-legacy
    escapes (``_legacy_subprocess`` imports / ``legacy_supervise_subprocess``
    / ``legacy_phase_command`` references) found in those two trees.  The
    driver layer is the sole boundary; any non-zero count is a leak.
"""

from __future__ import annotations

import re
from pathlib import Path
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


_FORBIDDEN_PATTERNS = (
    re.compile(r"from\s+arnold\.pipelines\.megaplan\._legacy_subprocess"),
    re.compile(r"import\s+arnold\.pipelines\.megaplan\._legacy_subprocess"),
    re.compile(r"\blegacy_supervise_subprocess\b"),
    re.compile(r"\blegacy_phase_command\b"),
)

_AUDIT_SCOPES = (
    "arnold/pipelines/megaplan/_pipeline",
    "arnold/pipelines/megaplan/drivers",
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def scoped_legacy_audit() -> int:
    """Scoped one-shot audit over ``megaplan/_pipeline/`` and ``megaplan/drivers/``.

    Counts occurrences of forbidden direct-legacy escapes:
      - ``from megaplan._legacy_subprocess`` / ``import megaplan._legacy_subprocess``
      - ``legacy_supervise_subprocess`` / ``legacy_phase_command``

    The driver layer is the sole boundary between the pipeline and the legacy
    subprocess supervision path; references to the legacy module must live in
    ``megaplan/auto.py`` and friends, never in the two scoped trees.

    Returns:
        Total count of forbidden hits found in the scoped trees.  ``0`` is
        the gate condition for the unified-dispatch path.
    """
    root = _repo_root()
    self_path = Path(__file__).resolve()
    hits = 0
    for scope in _AUDIT_SCOPES:
        base = root / scope
        if not base.exists():
            continue
        for path in base.rglob("*.py"):
            if path.resolve() == self_path:
                continue  # audit module references the patterns by definition
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            for pat in _FORBIDDEN_PATTERNS:
                hits += len(pat.findall(text))
    return hits


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
    "scoped_legacy_audit",
]
