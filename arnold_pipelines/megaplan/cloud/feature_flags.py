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
repair-request-queue  ARNOLD_REPAIR_REQUEST_QUEUE   1 (on)     Persist observe-only
                                                                repair request
                                                                markers.
repair-trigger        ARNOLD_REPAIR_TRIGGER_ENABLED 0 (off)    Dispatch queued
                                                                repair requests.
autonomy              ARNOLD_AUTONOMY               0 (off)    Enable autonomous
                                                                trigger / meta /
                                                                auditor actions.
meta-repair           ARNOLD_META_REPAIR_ENABLED    0 (off)    Enable meta-repair
                                                                gating and dispatch.
audit-autofix         ARNOLD_AUDIT_AUTOFIX_ENABLED  0 (off)    Enable auditor
                                                                autofix prompt
                                                                generation.
meta-repair-commit    ARNOLD_META_REPAIR_COMMIT_
                      ENABLED                       0 (off)    Allow meta-repair
                                                                to commit changes.
audit-autofix-commit  ARNOLD_AUDIT_AUTOFIX_COMMIT_
                      ENABLED                       0 (off)    Allow auditor
                                                                autofix commits.
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


def repair_request_queue_enabled() -> bool:
    """Return ``True`` when observe-only repair queue markers should be written.

    Controlled by ``ARNOLD_REPAIR_REQUEST_QUEUE`` — defaults to ON (``"1"``).

    This gate only controls immutable marker production.  It does not dispatch
    repair work.
    """
    return _is_enabled("ARNOLD_REPAIR_REQUEST_QUEUE", True)


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


def repair_trigger_enabled() -> bool:
    """Return ``True`` when queued failure-triggered repair may dispatch.

    Controlled by ``ARNOLD_REPAIR_TRIGGER_ENABLED`` — defaults to OFF (``"0"``).
    """
    return _is_enabled("ARNOLD_REPAIR_TRIGGER_ENABLED", False)


def meta_repair_enabled() -> bool:
    """Return ``True`` when meta-repair gating and dispatch are permitted.

    Controlled by ``ARNOLD_META_REPAIR_ENABLED`` — defaults to OFF (``"0"``).

    When enabled, the meta-repair subsystem may evaluate repair outcomes
    and trigger re-repair loops.  Even when enabled, meta-repair must
    still satisfy SUCCESS_OUTCOMES verification through the ordinary
    repair loop — it cannot claim success from process liveness alone.
    """
    return _is_enabled("ARNOLD_META_REPAIR_ENABLED", False)


def audit_autofix_enabled() -> bool:
    """Return ``True`` when the auditor may generate autofix prompts.

    Controlled by ``ARNOLD_AUDIT_AUTOFIX_ENABLED`` — defaults to OFF (``"0"``).

    When enabled, the progress auditor may suggest targeted fixes for
    stalled or failing repairs.  The auditor still requires explicit
    gating before any autofix is committed.
    """
    return _is_enabled("ARNOLD_AUDIT_AUTOFIX_ENABLED", False)


def meta_repair_commit_enabled() -> bool:
    """Return ``True`` when meta-repair is allowed to commit changes.

    Controlled by ``ARNOLD_META_REPAIR_COMMIT_ENABLED`` — defaults to OFF (``"0"``).

    This is a separate gate from ``ARNOLD_META_REPAIR_ENABLED`` so that
    meta-repair can evaluate and report without committing until the
    commit gate is explicitly enabled.
    """
    return _is_enabled("ARNOLD_META_REPAIR_COMMIT_ENABLED", False)


def audit_autofix_commit_enabled() -> bool:
    """Return ``True`` when auditor autofix commits are permitted.

    Controlled by ``ARNOLD_AUDIT_AUTOFIX_COMMIT_ENABLED`` — defaults to OFF (``"0"``).

    Separated from ``ARNOLD_AUDIT_AUTOFIX_ENABLED`` so autofix prompts
    can be generated and reviewed before any commit action is taken.
    """
    return _is_enabled("ARNOLD_AUDIT_AUTOFIX_COMMIT_ENABLED", False)


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


def repair_request_queue_on() -> bool:
    """Alias for :func:`repair_request_queue_enabled`."""
    return repair_request_queue_enabled()


def repair_trigger_on() -> bool:
    """Alias for :func:`repair_trigger_enabled`."""
    return repair_trigger_enabled()


def meta_repair_on() -> bool:
    """Alias for :func:`meta_repair_enabled`."""
    return meta_repair_enabled()


def audit_autofix_on() -> bool:
    """Alias for :func:`audit_autofix_enabled`."""
    return audit_autofix_enabled()


def meta_repair_commit_on() -> bool:
    """Alias for :func:`meta_repair_commit_enabled`."""
    return meta_repair_commit_enabled()


def audit_autofix_commit_on() -> bool:
    """Alias for :func:`audit_autofix_commit_enabled`."""
    return audit_autofix_commit_enabled()


__all__ = [
    "audit_autofix_commit_enabled",
    "audit_autofix_commit_on",
    "audit_autofix_enabled",
    "audit_autofix_on",
    "autonomy_enabled",
    "autonomy_on",
    "escalation_ledger_enabled",
    "escalation_ledger_on",
    "meta_repair_commit_enabled",
    "meta_repair_commit_on",
    "meta_repair_enabled",
    "meta_repair_on",
    "redaction_enabled",
    "redaction_on",
    "repair_request_queue_enabled",
    "repair_request_queue_on",
    "repair_trigger_enabled",
    "repair_trigger_on",
    "resolver_enforcement_enabled",
    "resolver_enforcement_on",
    "resolver_observe_enabled",
    "resolver_observe_on",
]
