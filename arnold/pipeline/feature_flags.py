"""Feature flags for the Arnold pipeline unification.

Centralizes flag lookups so consumers never inline ``os.environ.get``.
Gate warning: consumers MUST import from here, never read the environment
variable directly.
"""

from __future__ import annotations

import os

# ── Unified dispatch flag ───────────────────────────────────────────────
# When ``ARNOLD_UNIFIED_DISPATCH=1``, the M2 typed-Port dispatch path is
# active instead of the legacy string/state-dict path.  The flag is
# default-OFF per the strangler discipline — old path stays default-ON
# until the M2 merge gate.


def arnold_unified_dispatch_on() -> bool:
    """Return True when the unified M2/M3 dispatch path should be active.

    Centralized here so consumers never inline ``os.environ.get``.
    """
    return os.environ.get("ARNOLD_UNIFIED_DISPATCH", "0") == "1"

__all__ = [
    "arnold_unified_dispatch_on",
]

