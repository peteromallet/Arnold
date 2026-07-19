"""Centralized env-backed feature-flag defaults for the cloud-safe repair substrate.

Repair automation is **enabled by default**. Operators can still explicitly
disable individual paths with ``"0"``, ``"false"``, ``"no"``, or ``"off"``.
Mutation is nevertheless disabled by default: every mutation-capable action
must pass the default-off ``ARNOLD_AUTONOMY`` master gate *and* its path gate.
Observation, evidence capture, and reporting retain their independent flags.

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
repair-trigger        ARNOLD_REPAIR_TRIGGER_ENABLED 1 (on)     L1 path gate;
                                                                mutation still
                                                                requires autonomy.
autonomy              ARNOLD_AUTONOMY               0 (off)    Enable autonomous
                                                                trigger / meta /
                                                                auditor actions.
meta-repair           ARNOLD_META_REPAIR_ENABLED    1 (on)     L2 path gate;
                                                                mutation still
                                                                requires autonomy.
audit-autofix         ARNOLD_AUDIT_AUTOFIX_ENABLED  1 (on)     L3 path gate;
                                                                mutation still
                                                                requires autonomy.
meta-repair-commit    ARNOLD_META_REPAIR_COMMIT_
                      ENABLED                       1 (on)     Allow meta-repair
                                                                to commit changes.
meta-repair-push      ARNOLD_META_REPAIR_PUSH_
                      ENABLED                       0 (off)    Allow meta-repair
                                                                to push commits.
audit-autofix-commit  ARNOLD_AUDIT_AUTOFIX_COMMIT_
                      ENABLED                       1 (on)     Allow auditor
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

# Stable names for the three mutation-capable repair paths.  Callers must use
# ``mutation_authorized`` at the effect boundary rather than combining the
# master and path flags themselves.
MUTATION_PATH_L1 = "l1"
MUTATION_PATH_L2 = "l2"
MUTATION_PATH_L3 = "l3"


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
# Public API — behavior-changing flags
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
    """Return ``True`` when the L1 repair-trigger path is enabled.

    Controlled by ``ARNOLD_REPAIR_TRIGGER_ENABLED`` — defaults to ON (``"1"``).

    This is not mutation authority by itself; use :func:`mutation_authorized`
    at a mutation boundary.
    """
    return _is_enabled("ARNOLD_REPAIR_TRIGGER_ENABLED", True)


def meta_repair_enabled() -> bool:
    """Return ``True`` when the L2 meta-repair path is enabled.

    Controlled by ``ARNOLD_META_REPAIR_ENABLED`` — defaults to ON (``"1"``).

    This is not mutation authority by itself; use :func:`mutation_authorized`
    at a mutation boundary.  Meta-repair must still satisfy SUCCESS_OUTCOMES
    verification through the ordinary repair loop — it cannot claim success
    from process liveness alone.
    """
    return _is_enabled("ARNOLD_META_REPAIR_ENABLED", True)


def audit_autofix_enabled() -> bool:
    """Return ``True`` when the L3 auditor-autofix path is enabled.

    Controlled by ``ARNOLD_AUDIT_AUTOFIX_ENABLED`` — defaults to ON (``"1"``).

    This is not mutation authority by itself; use :func:`mutation_authorized`
    at a mutation boundary.  Observation and report generation remain outside
    this mutation authorization contract.
    """
    return _is_enabled("ARNOLD_AUDIT_AUTOFIX_ENABLED", True)


def meta_repair_commit_enabled() -> bool:
    """Return ``True`` when meta-repair is allowed to commit changes.

    Controlled by ``ARNOLD_META_REPAIR_COMMIT_ENABLED`` — defaults to ON (``"1"``).

    This remains a separate opt-out gate from ``ARNOLD_META_REPAIR_ENABLED`` so
    operators can disable commits while leaving meta-repair diagnostics running.
    """
    return _is_enabled("ARNOLD_META_REPAIR_COMMIT_ENABLED", True)


def meta_repair_push_enabled() -> bool:
    """Return ``True`` when meta-repair is explicitly allowed to push changes.

    Controlled by ``ARNOLD_META_REPAIR_PUSH_ENABLED`` and defaults OFF.  Push
    is an externally consequential superset of a local commit, so autonomy and
    commit authority must not imply it. A local commit grant must never silently
    authorize a remote effect.
    """
    return _is_enabled("ARNOLD_META_REPAIR_PUSH_ENABLED", False)


def audit_autofix_commit_enabled() -> bool:
    """Return ``True`` when auditor autofix commits are permitted.

    Controlled by ``ARNOLD_AUDIT_AUTOFIX_COMMIT_ENABLED`` — defaults to ON (``"1"``).

    Separated from ``ARNOLD_AUDIT_AUTOFIX_ENABLED`` so commits can be explicitly
    disabled while autofix diagnosis remains active.
    """
    return _is_enabled("ARNOLD_AUDIT_AUTOFIX_COMMIT_ENABLED", True)


# ---------------------------------------------------------------------------
# Public API — mutation authorization
# ---------------------------------------------------------------------------


def mutation_authorized(path: str) -> bool:
    """Return whether mutation is authorized for the named repair *path*.

    The default-off ``ARNOLD_AUTONOMY`` gate is the master authority for
    L1/L2/L3 state, source, commit, and mutation-capable subprocess effects. A
    path's own gate is necessary but insufficient: authorization requires both
    gates. Push has an additional explicit gate because it is externally
    consequential. Unknown paths fail closed.

    This predicate deliberately does not gate observation, redaction, evidence
    capture, queue inspection, or reporting.  Those operations retain their
    independent feature flags and remain available while mutation is blocked.
    """
    path_gate = {
        MUTATION_PATH_L1: repair_trigger_enabled,
        MUTATION_PATH_L2: meta_repair_enabled,
        MUTATION_PATH_L3: audit_autofix_enabled,
    }.get(path)
    return autonomy_enabled() and path_gate is not None and path_gate()


def audit_autofix_mutation_authorized() -> bool:
    """Shell-friendly L3 authorization adapter for wrapper dispatch seams."""
    return mutation_authorized(MUTATION_PATH_L3)


def meta_repair_mutation_authorized() -> bool:
    """Shell-friendly L2 authorization adapter for wrapper dispatch seams."""
    return mutation_authorized(MUTATION_PATH_L2)


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


def meta_repair_push_on() -> bool:
    """Alias for :func:`meta_repair_push_enabled`."""
    return meta_repair_push_enabled()


def audit_autofix_commit_on() -> bool:
    """Alias for :func:`audit_autofix_commit_enabled`."""
    return audit_autofix_commit_enabled()


__all__ = [
    "audit_autofix_commit_enabled",
    "audit_autofix_commit_on",
    "audit_autofix_enabled",
    "audit_autofix_mutation_authorized",
    "audit_autofix_on",
    "autonomy_enabled",
    "autonomy_on",
    "escalation_ledger_enabled",
    "escalation_ledger_on",
    "meta_repair_commit_enabled",
    "meta_repair_commit_on",
    "meta_repair_push_enabled",
    "meta_repair_push_on",
    "meta_repair_enabled",
    "meta_repair_mutation_authorized",
    "meta_repair_on",
    "MUTATION_PATH_L1",
    "MUTATION_PATH_L2",
    "MUTATION_PATH_L3",
    "mutation_authorized",
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
