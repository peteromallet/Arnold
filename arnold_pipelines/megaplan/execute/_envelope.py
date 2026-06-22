"""Execute envelope: unified-execute feature flag.

One read, one cached value per process — set before any tier-resolution
code runs and never re-read.
"""

from __future__ import annotations

import os

_CACHED: bool | None = None


def unified_execute_enabled() -> bool:
    """Return ``True`` when ``MEGAPLAN_UNIFIED_EXECUTE`` is set to a truthy value.

    Defaults to OFF (``False``) when the variable is unset, empty, ``"0"``,
    or ``"false"`` (case-insensitive).
    """
    global _CACHED
    if _CACHED is None:
        val = os.environ.get("MEGAPLAN_UNIFIED_EXECUTE", "")
        _CACHED = val not in ("", "0", "false", "False", "FALSE")
    return _CACHED
