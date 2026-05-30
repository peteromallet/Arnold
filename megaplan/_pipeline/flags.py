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


def _master_on() -> bool:
    """Return ``True`` when ``MEGAPLAN_UNIFIED_DISPATCH`` env var is ``'1'``."""
    return os.getenv("MEGAPLAN_UNIFIED_DISPATCH") == "1"


def unified_dispatch_on() -> bool:
    """Return ``True`` when ``MEGAPLAN_UNIFIED_DISPATCH`` env var is ``'1'``.

    This is the master gate for the unified dispatch path (M3 hinge).
    All per-organ companion flags inherit from this when their own
    env var is unset.
    """
    return _master_on()


def _companion_on(env_name: str) -> bool:
    """Resolve a per-organ companion flag.

    When *env_name* is set, return ``True`` iff it is ``'1'``.
    When unset, inherit from ``MEGAPLAN_UNIFIED_DISPATCH``.
    """
    val = os.getenv(env_name)
    if val is None:
        return _master_on()
    return val == "1"


def conveyance_strict_on() -> bool:
    """Return ``True`` when Conveyance strict mode is active.

    Controlled by ``CONVEYANCE_STRICT`` env var.  Inherits from
    ``MEGAPLAN_UNIFIED_DISPATCH`` when ``CONVEYANCE_STRICT`` is unset.
    """
    return _companion_on("CONVEYANCE_STRICT")


def r1_authority_on() -> bool:
    """Return ``True`` when the R1 authority flip is active.

    Controlled by ``R1_AUTHORITY`` env var.  Inherits from
    ``MEGAPLAN_UNIFIED_DISPATCH`` when ``R1_AUTHORITY`` is unset.
    """
    return _companion_on("R1_AUTHORITY")


def activation_emit_on() -> bool:
    """Return ``True`` when Activation emit is active.

    Controlled by ``ACTIVATION_EMIT`` env var.  Inherits from
    ``MEGAPLAN_UNIFIED_DISPATCH`` when ``ACTIVATION_EMIT`` is unset.
    """
    return _companion_on("ACTIVATION_EMIT")
