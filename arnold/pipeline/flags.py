"""Feature flags for the Arnold neutral pipeline boundary.

Centralizes flag lookups so consumers never inline ``os.environ.get``.
This module has zero Megaplan imports and zero env var reads — it is
a pure structural skeleton returning constant defaults only per the
strangler discipline (old path default-ON, new path default-OFF).
"""

from __future__ import annotations


def typed_ports_on() -> bool:
    """Return whether typed ports are active.

    Always returns ``False`` unconditionally — the typed-ports feature
    is a Megaplan opinion gated behind ``MEGAPLAN_TYPED_PORTS``.
    Arnold's neutral boundary unconditionally returns ``False``.
    """
    return False

__all__ = [
    "typed_ports_on",
]

