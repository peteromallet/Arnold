"""Centralized env-backed feature-flag defaults for the cloud-safe repair substrate.

In M1 every behaviour-changing path is **disabled by default** unless the
env var is explicitly set to ``"1"``.  The *observe-only* resolver and
redaction are **enabled by default** because they are additive diagnostics
and security boundaries, not behavior changes.

Flags
-----

====================  ============================  =========  ===================
Flag                  Env Var                       Default    Purpose
====================  ============================  =========  ===================
resolver-observe      ARNOLD_RESOLVER_OBSERVE       1 (on)     Capture resolver
                                                                evidence alongside
                                                                legacy decisions.
resolver-enforcement  ARNOLD_RESOLVER_ENFORCEMENT   0 (off)    Make resolver output
                                                                authoritative for
                                                                target selection /
                                                                state clearing.
escalation-ledger     ARNOLD_ESCALATION_LEDGER      0 (off)    Enable append-only
                                                                escalation ledger
                                                                writes.
autonomy              ARNOLD_AUTONOMY               0 (off)    Enable autonomous
                                                                trigger / meta /
                                                                auditor actions.
redaction             ARNOLD_REDACTION_ENABLED      1 (on)     Redact secrets from
                                                                persisted and
                                                                outbound artifacts.
====================  ============================  =========  ===================

Every caller MUST import from here rather than calling ``os.getenv`` or
``os.environ.get`` directly for the env vars listed above.
"""

from __future__ import annotations

import os

_DISABLE_VALUES: frozenset[str] = frozenset({"0", "false", "no", "off"})


def _is_enabled(env_name: str, default: bool) -> bool:
    """Return *True* when *env_name* is set to a truthy string.

    When *env_name* is unset or empty the *default* is returned.
    Values in ``_DISABLE_VALUES`` always mean *False*.
    """
    raw = os.getenv(env_name, "").strip().lower()
    if not raw:
        return default
    if raw in _DISABLE_VALUES:
        return False
    return True


# ---------------------------------------------------------------------------
# Public API — observe-only flags (default ON)
# ---------------------------------------------------------------------------


def resolver_observe_enabled() -> bool:
    """Return ``True`` when the resolver should capture observe evidence.

    Controlled by ``ARNOLD_RESOLVER_OBSERVE`` — defaults to ON (``"1"``).

    In M1 the resolver records evidence without changing repair decisions,
    state-clearing, or target selection.  This flag gates the *capture* only;
    even when enabled the resolver output is NOT authoritative.
    """
    return _is_enabled("ARNOLD_RESOLVER_OBSERVE", True)


def redaction_enabled() -> bool:
    """Return ``True`` when redaction should be applied.

    Controlled by ``ARNOLD_REDACTION_ENABLED`` — defaults to ON (``"1"``).

    Delegates to :func:`arnold_pipelines.megaplan.cloud.redact.redaction_enabled`
    so the single source of truth lives in the redaction module.
    """
    from arnold_pipelines.megaplan.cloud.redact import redaction_enabled as _impl

    return _impl()


# ---------------------------------------------------------------------------
# Public API — behavior-changing flags (default OFF)
# ---------------------------------------------------------------------------


def resolver_enforcement_enabled() -> bool:
    """Return ``True`` when resolver output should be authoritative.

    Controlled by ``ARNOLD_RESOLVER_ENFORCEMENT`` — defaults to OFF (``"0"``).

    When enabled, the resolver's target selection, staleness determination,
    and state-clearing recommendations become authoritative over the legacy
    watchdog helpers.  This is a North Star gating requirement: enforcement
    stays off until safety checks pass.
    """
    return _is_enabled("ARNOLD_RESOLVER_ENFORCEMENT", False)


def escalation_ledger_enabled() -> bool:
    """Return ``True`` when the escalation ledger should be active.

    Controlled by ``ARNOLD_ESCALATION_LEDGER`` — defaults to OFF (``"0"``).

    When enabled, :class:`EscalationLedgerWriter` instances are created in
    an active state.  When disabled (M1 default), ledger writes are no-ops.
    """
    return _is_enabled("ARNOLD_ESCALATION_LEDGER", False)


def autonomy_enabled() -> bool:
    """Return ``True`` when autonomous trigger / meta / auditor actions are permitted.

    Controlled by ``ARNOLD_AUTONOMY`` — defaults to OFF (``"0"``).

    When disabled, trigger dispatch, meta-launch decisions, and auditor
    autonomous intervention are all suppressed.  Only observe-only evidence
    capture is allowed.
    """
    return _is_enabled("ARNOLD_AUTONOMY", False)


# ---------------------------------------------------------------------------
# Convenience re-exports for callers that want a single import
# ---------------------------------------------------------------------------


def resolver_observe_on() -> bool:
    """Alias for :func:`resolver_observe_enabled`."""
    return resolver_observe_enabled()


def resolver_enforcement_on() -> bool:
    """Alias for :func:`resolver_enforcement_enabled`."""
    return resolver_enforcement_enabled()


def escalation_ledger_on() -> bool:
    """Alias for :func:`escalation_ledger_enabled`."""
    return escalation_ledger_enabled()


def autonomy_on() -> bool:
    """Alias for :func:`autonomy_enabled`."""
    return autonomy_enabled()


def redaction_on() -> bool:
    """Alias for :func:`redaction_enabled`."""
    return redaction_enabled()


__all__ = [
    "autonomy_enabled",
    "autonomy_on",
    "escalation_ledger_enabled",
    "escalation_ledger_on",
    "redaction_enabled",
    "redaction_on",
    "resolver_enforcement_enabled",
    "resolver_enforcement_on",
    "resolver_observe_enabled",
    "resolver_observe_on",
]
