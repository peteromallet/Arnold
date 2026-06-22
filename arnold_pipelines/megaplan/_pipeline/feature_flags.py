"""Feature flags for the megaplan pipeline unification (M5a).

Centralizes flag lookups so consumers never inline ``os.environ.get``.
Gate warning #2: resume.py and validator.py MUST import from here,
never read the environment variable directly.
"""

from __future__ import annotations

import os

# ── Unified dispatch flag ───────────────────────────────────────────────
# TODO(M2/M3): When ``MEGAPLAN_UNIFIED_DISPATCH=1``, the M2 typed-Port
# dispatch path is active instead of the legacy string/state-dict path.
# The flag is default-OFF per the strangler discipline — old path stays
# default-ON until the M2 merge gate (PROGRAM:122).


def megaplan_unified_dispatch_on() -> bool:
    """Return True when the unified M2/M3 dispatch path should be active.

    Centralized here so consumers (resume.py, validator.py, etc.) never
    inline ``os.environ.get`` — see gate warning #2 in the M5a plan.
    """
    return os.environ.get("MEGAPLAN_UNIFIED_DISPATCH", "0") == "1"
