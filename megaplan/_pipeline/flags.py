"""Feature flag helpers for megaplan._pipeline.

Centralized single source of truth for MEGAPLAN_TYPED_PORTS and future
feature flags.  All callers must import from here rather than calling
``os.getenv`` directly.

M4 T5 — Companion flags
-----------------------
The seven companion flags introduced for the unified-dispatch strangler
(``UNIFIED_EMIT``, ``UNIFIED_EVIDENCE``, ``UNIFIED_CONFIG``, ``EFFECT_LEDGER``,
``UNIFIED_RECOVERY``, ``UNIFIED_BUDGET``, ``UNIFIED_EVALUAND`` / ``R5_UNIFIED``)
are deliberately **NOT** entries in the long-lived ``FLAG-*`` catalog.  Their
lifecycle is tied to the strangler pattern — each flips once its organ has
migrated and then disappears.  Treat them as scaffold, not as feature gates.

Each companion inherits from ``MEGAPLAN_UNIFIED_DISPATCH`` (the master gate)
when its own env var is unset, so a single master flip exercises every organ
simultaneously while still allowing per-organ overrides for debugging.
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


# ---------------------------------------------------------------------------
# M4 T5 — Companion flags for the unified-dispatch strangler.
# These are intentionally NOT entries in the long-lived FLAG-* catalog; see
# the module docstring above.
# ---------------------------------------------------------------------------


def unified_emit_on() -> bool:
    """``UNIFIED_EMIT`` — observability emit re-home companion."""
    return _companion_on("UNIFIED_EMIT")


def unified_evidence_on() -> bool:
    """``UNIFIED_EVIDENCE`` — evidence-attribution re-home companion."""
    return _companion_on("UNIFIED_EVIDENCE")


def unified_config_on() -> bool:
    """``UNIFIED_CONFIG`` — N-layer ConfigResolver companion."""
    return _companion_on("UNIFIED_CONFIG")


def effect_ledger_on() -> bool:
    """``EFFECT_LEDGER`` — journal-then-execute Effect-Ledger companion."""
    return _companion_on("EFFECT_LEDGER")


def unified_recovery_on() -> bool:
    """``UNIFIED_RECOVERY`` — RecoveryPolicy.classify companion."""
    return _companion_on("UNIFIED_RECOVERY")


def unified_budget_on() -> bool:
    """``UNIFIED_BUDGET`` — BudgetAuthority capacity-grant companion."""
    return _companion_on("UNIFIED_BUDGET")


def unified_evaluand_on() -> bool:
    """``UNIFIED_EVALUAND`` (alias ``R5_UNIFIED``) — Evaluand scaffold companion."""
    val = os.getenv("UNIFIED_EVALUAND")
    if val is None:
        val = os.getenv("R5_UNIFIED")
    if val is None:
        return _master_on()
    return val == "1"


def calibration_query_route_on() -> bool:
    """Return ``True`` only when ``MEGAPLAN_CALIBRATION_QUERY_ROUTE=1``.

    This flag is deliberately independent of the unified-dispatch master gate
    and all companion inheritance helpers. Calibration query routing stays
    default-off until this exact env var is flipped.
    """
    return os.getenv("MEGAPLAN_CALIBRATION_QUERY_ROUTE") == "1"


def control_interface_routing_on() -> bool:
    """Return ``True`` only when ``MEGAPLAN_CONTROL_INTERFACE_ROUTING=1``.

    The M5c control-interface route is a strangler path and remains
    independent from the unified-dispatch master gate until explicitly flipped.
    """

    return os.getenv("MEGAPLAN_CONTROL_INTERFACE_ROUTING") == "1"


# Alias for the master gate, exposed under the conventional name used by the
# M4 brief / consumers ("is the unified dispatch path enabled?").
def unified_dispatch_enabled() -> bool:
    """Return ``True`` when the master ``MEGAPLAN_UNIFIED_DISPATCH`` flag is on."""
    return _master_on()
