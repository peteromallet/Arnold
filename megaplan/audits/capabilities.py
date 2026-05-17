"""Re-export shim — canonical implementation lives in :mod:`megaplan.runtime.capabilities`.

This module used to hold a byte-identical copy of the capability registry. The
duplicate was deduped (T12 of the file-organization plan); the file is kept as
a thin re-export so external callers like
``from megaplan.audits.capabilities import X`` keep working.
"""

from __future__ import annotations

from megaplan.runtime.capabilities import *  # noqa: F401,F403

__all__ = [
    "ALL_CAPABILITIES",
    "CONTAINER_CAPABILITIES",
    "DEFAULT_AGENT_ROUTING",
    "DEFAULT_CONTAINER_CAPABILITIES",
    "DEFAULT_HUMAN_CAPABILITIES",
    "HUMAN_CAPABILITIES",
    "get_worker_capabilities",
    "union_verifies",
    "validate_capabilities",
]
