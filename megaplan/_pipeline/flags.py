"""Feature flag helpers for megaplan._pipeline.

Centralized single source of truth for MEGAPLAN_TYPED_PORTS and future
feature flags.  All callers must import from here rather than calling
``os.getenv`` directly.
"""

from __future__ import annotations

import os


def typed_ports_on() -> bool:
    """Return ``True`` when ``MEGAPLAN_TYPED_PORTS`` env var is ``'1'``."""
    return os.getenv("MEGAPLAN_TYPED_PORTS") == "1"
