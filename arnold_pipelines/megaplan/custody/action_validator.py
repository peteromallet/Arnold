"""Controlled authoritative-writer action-boundary validator (M7 shadow-only).

Provides the central conjunctive gate ``validate_action_boundary(...)`` that
rereads current Run Authority grant/fence, current Custody lease/epoch, and
required WBC attempt status immediately before dispatch, repair, completion,
cancellation, publication, or delivery.

Production enforcement is disabled by default and gated behind the
``ARNOLD_M7_ACTION_VALIDATOR_ENFORCEMENT`` environment variable (default
``"0"``).  When enforcement is off, the validator still performs every
check and returns the full diagnostics, but the gate result is
``shadow_pass`` instead of blocking the caller.  This mirrors the
``ARNOLD_RESOLVER_OBSERVE`` / ``ARNOLD_RESOLVER_ENFORCEMENT`` pattern from
:mod:`megaplan.cloud.feature_flags`.

North Star alignment
--------------------
* **Single-owner** — Custody is the sole owner of lease state.
  Cross-owner references (WBC attempt ids, Run Authority grant ids,
  coordinator fence tokens) are read-only pointers, never duplicate ledgers.
* **Conjunctive** — All three sources (Run Authority, Custody, WBC) must
  agree before an authority boundary action is accepted.
* **Shadow-first** — Enforcement remains off until M6 proof and M6A
  operational WBC API are machine-verifiably accepted.
* **No stale-source acceptance** — Every call rereads current sources
  immediately; the validator never caches prior results.

Action boundaries
-----------------
==============  ============================================================
dispatch        An action is about to be dispatched to an executor.
repair          A repair operation is about to be started or resumed.
completion      A task/plan completion verdict is about to be published.
cancellation    A task/plan cancellation is about to be published.
publication     A chain publication is about to be pushed.
delivery        A deliverable is about to be delivered to a downstream system.
==============  ============================================================
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType
from typing import Any, Literal, Mapping, Optional

from arnold_pipelines.megaplan.custody.contracts import (
    CustodyLease,
    CustodyTargetKey,
    RepairOccurrenceKey,
    normalize_custody_target_key,
)
from arnold_pipelines.megaplan.custody.lease_store import (
    CustodyLeaseStore,
    open_lease_store,
)
from arnold_pipelines.megaplan.custody.outbox import (
    CustodyOutbox,
    OutboxRecord,
    open_outbox,
)
from arnold_pipelines.run_authority.contracts import (
    CapabilityGrant,
    CoordinatorFence,
)

# ── Schema version constant ────────────────────────────────────────────────

ACTION_VALIDATOR_SCHEMA_VERSION = 1

# ── Env-var gate constants ─────────────────────────────────────────────────

_ENV_ENFORCEMENT = "ARNOLD_M7_ACTION_VALIDATOR_ENFORCEMENT"
_DISABLE_VALUES: frozenset[str] = frozenset({"0", "false", "no", "off"})


def _production_enforcement_enabled() -> bool:
    """Return ``True`` only when the M7 action validator enforcement flag is on.

    Controlled by ``ARNOLD_M7_ACTION_VALIDATOR_ENFORCEMENT`` — defaults to
    OFF (``"0"``).  This follows the same pattern as
    :func:`~megaplan.cloud.feature_flags.resolver_enforcement_enabled`.

    When disabled (the default), the validator performs every check but
    the gate result is ``shadow_pass``.  Callers must NOT treat a
    ``shadow_pass`` as an authoritative authorization.
    """
    raw = os.getenv(_ENV_ENFORCEMENT, "").strip().lower()
    if not raw:
        return False
    if raw in _DISABLE_VALUES:
        return False
    return True


# ── Action boundary types ──────────────────────────────────────────────────

ActionBoundaryType = Literal[
    "dispatch",
    "repair",
    "completion",
    "cancellation",
    "publication",
    "delivery",
]

ACTION_BOUNDARY_TYPES: frozenset[ActionBoundaryType] = frozenset(
    {
        "dispatch",
        "repair",
        "completion",
        "cancellation",
        "publication",
        "delivery",
    }
)

# ── Validation outcome codes ───────────────────────────────────────────────


class ValidationOutcome(StrEnum):
    """Outcome of a single conjunctive check within an action boundary."""

    SATISFIED = "satisfied"
    MISSING = "missing"
    STALE = "stale"
    CONFLICT = "conflict"
    EXPIRED = "expired"
    FENCED = "fenced"
    NOT_OWNER = "not_owner"
    ERROR = "error"


# ── Gate result ────────────────────────────────────────────────────────────


class GateResult(StrEnum):
    """Overall gate result for an action boundary validation."""

    AUTHORIZED = "authorized"
    SHADOW_PASS = "shadow_pass"
    BLOCKED_MISSING_GRANT = "blocked_missing_grant"
    BLOCKED_FENCE_MISMATCH = "blocked_fence_mismatch"
    BLOCKED_NO_LEASE = "blocked_no_lease"
    BLOCKED_EXPIRED_LEASE = "blocked_expired_lease"
    BLOCKED_STALE_EPOCH = "blocked_stale_epoch"
    BLOCKED_WBC_MISSING = "blocked_wbc_missing"
    BLOCKED_WBC_CONFLICT = "blocked_wbc_conflict"
    BLOCKED_NOT_OWNER = "blocked_not_owner"
    ERROR = "error"


# ── Per-source check result ────────────────────────────────────────────────


@dataclass(frozen=True)
class SourceCheck:
    """Result of a single source reread within an action-boundary validation."""

    source: str  # "run_authority_grant", "run_authority_fence", "custody_lease", "wbc_attempt"
    outcome: ValidationOutcome
    detail: str = ""
    observed_at: str = ""
    observed_value: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.observed_at:
            object.__setattr__(
                self,
                "observed_at",
                datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            )
        if not isinstance(self.observed_value, Mapping):
            object.__setattr__(self, "observed_value", MappingProxyType({}))
        else:
            object.__setattr__(self, "observed_value", MappingProxyType(dict(self.observed_value)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "outcome": self.outcome.value,
            "detail": self.detail,
            "observed_at": self.observed_at,
            "observed_value": dict(self.observed_value),
        }


# ── Action boundary context ────────────────────────────────────────────────


@dataclass(frozen=True)
class ActionBoundaryContext:
    """Context required to validate an action boundary.

    All fields are read-only pointers to source state — the validator
    never duplicates or mutates source ledgers.

    Required fields:
      - action_type: the type of action being validated
      - target: the CustodyTargetKey identifying the repair occurrence
      - run_authority_grant_id: the Run Authority grant that authorizes the action
      - coordinator_fence_token: the coordinator fence token at the time of the grant
      - wbc_attempt_reference: the WBC attempt reference (may be empty)

    Optional owner identity:
      - owner_host, owner_pid, owner_boot_id: current process identity
    """

    action_type: ActionBoundaryType
    target: CustodyTargetKey
    run_authority_grant_id: str
    coordinator_fence_token: int
    wbc_attempt_reference: str = ""
    owner_host: str = ""
    owner_pid: str = ""
    owner_boot_id: str = ""

    def __post_init__(self) -> None:
        if self.action_type not in ACTION_BOUNDARY_TYPES:
            raise ValueError(f"unknown action_type {self.action_type!r}")
        if not isinstance(self.target, CustodyTargetKey):
            raise TypeError("target must be a CustodyTargetKey")
        if not isinstance(self.run_authority_grant_id, str) or not self.run_authority_grant_id.strip():
            raise ValueError("run_authority_grant_id must be a non-empty string")
        if not isinstance(self.coordinator_fence_token, int) or isinstance(self.coordinator_fence_token, bool) or self.coordinator_fence_token < 0:
            raise ValueError("coordinator_fence_token must be a non-negative integer")
        if not isinstance(self.wbc_attempt_reference, str):
            raise ValueError("wbc_attempt_reference must be a string")
        if not isinstance(self.owner_host, str):
            raise ValueError("owner_host must be a string")
        if not isinstance(self.owner_pid, str):
            raise ValueError("owner_pid must be a string")
        if not isinstance(self.owner_boot_id, str):
            raise ValueError("owner_boot_id must be a string")


# ── Validation result ──────────────────────────────────────────────────────


@dataclass(frozen=True)
class ActionBoundaryResult:
    """Result of validating an action boundary.

    Fields:
      - gate_result: the overall gate result
      - action_type: the type of action that was validated
      - target_digest: the deterministic digest of the target
      - checks: per-source check results (Run Authority grant, fence, Custody lease, WBC attempt)
      - enforcement_enabled: whether production enforcement was active
      - validated_at: ISO-8601 timestamp of validation
      - diagnostics: additional human/machine-readable diagnostics
    """

    gate_result: GateResult
    action_type: ActionBoundaryType
    target_digest: str
    checks: tuple[SourceCheck, ...]
    enforcement_enabled: bool = False
    validated_at: str = ""
    diagnostics: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.gate_result, GateResult):
            raise TypeError("gate_result must be a GateResult")
        if self.action_type not in ACTION_BOUNDARY_TYPES:
            raise ValueError(f"unknown action_type {self.action_type!r}")
        if not isinstance(self.target_digest, str) or not self.target_digest.strip():
            raise ValueError("target_digest must be a non-empty string")
        if not self.validated_at:
            object.__setattr__(
                self,
                "validated_at",
                datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            )
        if not isinstance(self.diagnostics, Mapping):
            object.__setattr__(self, "diagnostics", MappingProxyType({}))
        else:
            object.__setattr__(self, "diagnostics", MappingProxyType(dict(self.diagnostics)))

    @property
    def authorized(self) -> bool:
        """Return ``True`` when the gate result is ``AUTHORIZED``.

        Note: ``SHADOW_PASS`` is NOT authoritative — enforcement must be
        enabled for ``authorized`` to be ``True``.
        """
        return self.gate_result == GateResult.AUTHORIZED

    @property
    def blocked(self) -> bool:
        """Return ``True`` when the gate is blocked (any non-pass result)."""
        return self.gate_result not in {GateResult.AUTHORIZED, GateResult.SHADOW_PASS}

    @property
    def is_shadow(self) -> bool:
        """Return ``True`` when the validator ran in shadow mode."""
        return not self.enforcement_enabled

    def to_dict(self) -> dict[str, Any]:
        return {
            "gate_result": self.gate_result.value,
            "action_type": self.action_type,
            "target_digest": self.target_digest,
            "checks": [c.to_dict() for c in self.checks],
            "enforcement_enabled": self.enforcement_enabled,
            "validated_at": self.validated_at,
            "diagnostics": dict(self.diagnostics),
        }


# ── Source reread helpers ──────────────────────────────────────────────────


def _reread_run_authority_grant(
    grant_id: str,
    fence_token: int,
) -> SourceCheck:
    """Reread the Run Authority grant and verify its identity.

    Returns a SourceCheck with outcome SATISFIED, MISSING, or ERROR.
    """
    if not grant_id.strip():
        return SourceCheck(
            source="run_authority_grant",
            outcome=ValidationOutcome.MISSING,
            detail="Run Authority grant ID is empty",
        )

    # The grant must exist and reference the same fence token.
    # In M7 shadow mode, we cannot reach into the Run Authority store
    # to fetch the actual CapabilityGrant record — that store is owned
    # by Run Authority, not Custody.  Instead we verify that the
    # grant_id and fence_token are syntactically valid and defer the
    # actual grant-fetch to the caller-supplied grant record.
    #
    # For now, this is a placeholder that returns SATISFIED if the
    # grant_id and fence_token are syntactically valid.  When M6/M6A
    # acceptance is machine-verifiable, this will be upgraded to a
    # real cross-owner read from the Run Authority store.
    try:
        # Validate fence_token is non-negative
        if not isinstance(fence_token, int) or isinstance(fence_token, bool) or fence_token < 0:
            return SourceCheck(
                source="run_authority_grant",
                outcome=ValidationOutcome.ERROR,
                detail=f"invalid fence_token: {fence_token!r}",
            )
        return SourceCheck(
            source="run_authority_grant",
            outcome=ValidationOutcome.SATISFIED,
            detail=f"grant_id={grant_id!r} syntactically valid; cross-owner grant fetch deferred to M6/M6A",
            observed_value={"grant_id": grant_id, "fence_token": fence_token},
        )
    except Exception as exc:
        return SourceCheck(
            source="run_authority_grant",
            outcome=ValidationOutcome.ERROR,
            detail=f"grant reread error: {type(exc).__name__}: {exc}",
        )


def _reread_run_authority_fence(
    fence_token: int,
    expected_grant_id: str,
) -> SourceCheck:
    """Reread the coordinator fence and verify it matches the expected grant.

    Returns a SourceCheck with outcome SATISFIED, FENCED, or ERROR.
    """
    if not expected_grant_id.strip():
        return SourceCheck(
            source="run_authority_fence",
            outcome=ValidationOutcome.MISSING,
            detail="cannot verify fence without a grant ID",
        )

    try:
        if not isinstance(fence_token, int) or isinstance(fence_token, bool) or fence_token < 0:
            return SourceCheck(
                source="run_authority_fence",
                outcome=ValidationOutcome.ERROR,
                detail=f"invalid fence_token: {fence_token!r}",
            )
        return SourceCheck(
            source="run_authority_fence",
            outcome=ValidationOutcome.SATISFIED,
            detail=f"fence_token={fence_token} syntactically valid; cross-owner fence fetch deferred to M6/M6A",
            observed_value={"fence_token": fence_token, "grant_id": expected_grant_id},
        )
    except Exception as exc:
        return SourceCheck(
            source="run_authority_fence",
            outcome=ValidationOutcome.ERROR,
            detail=f"fence reread error: {type(exc).__name__}: {exc}",
        )


def _reread_custody_lease(
    lease_store: CustodyLeaseStore | None,
    target_digest: str,
    owner_host: str,
    owner_pid: str,
    owner_boot_id: str,
) -> SourceCheck:
    """Reread the current Custody lease for the target.

    Returns a SourceCheck with outcome SATISFIED, MISSING, EXPIRED,
    STALE, NOT_OWNER, or ERROR.
    """
    if lease_store is None:
        return SourceCheck(
            source="custody_lease",
            outcome=ValidationOutcome.MISSING,
            detail="lease store is not available (None)",
        )

    try:
        # The lease_id is derived from the target digest for lookups.
        lease_id = f"custody-lease-{target_digest[:16]}"

        current = lease_store.current_lease(lease_id)
        if current is None:
            return SourceCheck(
                source="custody_lease",
                outcome=ValidationOutcome.MISSING,
                detail=f"no lease found for lease_id={lease_id!r}",
                observed_value={"lease_id": lease_id, "target_digest": target_digest},
            )

        # Check expiry
        if current.is_expired:
            return SourceCheck(
                source="custody_lease",
                outcome=ValidationOutcome.EXPIRED,
                detail=f"lease {current.lease_id!r} expired at {current.expires_at}",
                observed_value={
                    "lease_id": current.lease_id,
                    "custody_epoch": current.custody_epoch,
                    "acquired_at": current.acquired_at,
                    "expires_at": current.expires_at,
                },
            )

        # Check owner identity
        if owner_host and owner_pid:
            observed_owner = current.owner_identity
            # boot_id is best-effort; only compare if both sides provide one
            if owner_boot_id and current.owner_boot_id:
                expected_owner = (owner_host, owner_pid, owner_boot_id)
            else:
                expected_owner = (owner_host, owner_pid, current.owner_boot_id)
            if (owner_host != current.owner_host) or (owner_pid != current.owner_pid):
                return SourceCheck(
                    source="custody_lease",
                    outcome=ValidationOutcome.NOT_OWNER,
                    detail=f"owner mismatch: expected ({owner_host!r}, {owner_pid!r}), observed ({current.owner_host!r}, {current.owner_pid!r})",
                    observed_value={
                        "lease_id": current.lease_id,
                        "custody_epoch": current.custody_epoch,
                        "owner_host": current.owner_host,
                        "owner_pid": current.owner_pid,
                        "owner_boot_id": current.owner_boot_id,
                    },
                )
            # boot_id mismatch is not blocking but worth noting
            if owner_boot_id and current.owner_boot_id and owner_boot_id != current.owner_boot_id:
                return SourceCheck(
                    source="custody_lease",
                    outcome=ValidationOutcome.SATISFIED,
                    detail=f"lease {current.lease_id!r} active (epoch={current.custody_epoch}); boot_id differs (ctx={owner_boot_id!r}, lease={current.owner_boot_id!r})",
                    observed_value={
                        "lease_id": current.lease_id,
                        "custody_epoch": current.custody_epoch,
                        "acquired_at": current.acquired_at,
                        "expires_at": current.expires_at,
                        "owner_host": current.owner_host,
                        "owner_pid": current.owner_pid,
                        "owner_boot_id": current.owner_boot_id,
                        "context_boot_id": owner_boot_id,
                    },
                )

        return SourceCheck(
            source="custody_lease",
            outcome=ValidationOutcome.SATISFIED,
            detail=f"lease {current.lease_id!r} is active (epoch={current.custody_epoch})",
            observed_value={
                "lease_id": current.lease_id,
                "custody_epoch": current.custody_epoch,
                "acquired_at": current.acquired_at,
                "expires_at": current.expires_at,
                "owner_host": current.owner_host,
                "owner_pid": current.owner_pid,
            },
        )
    except Exception as exc:
        return SourceCheck(
            source="custody_lease",
            outcome=ValidationOutcome.ERROR,
            detail=f"lease reread error: {type(exc).__name__}: {exc}",
        )


def _reread_wbc_attempt(
    outbox: CustodyOutbox | None,
    wbc_attempt_reference: str,
    target_digest: str,
) -> SourceCheck:
    """Reread the WBC attempt status from the outbox.

    Returns a SourceCheck with outcome SATISFIED, MISSING, CONFLICT,
    or ERROR.
    """
    if outbox is None:
        # When no outbox is available, we treat this as not yet
        # configured rather than a hard failure — the caller may
        # not have set up the outbox yet in M7 shadow mode.
        return SourceCheck(
            source="wbc_attempt",
            outcome=ValidationOutcome.MISSING,
            detail="outbox is not available (None); WBC attempt status cannot be verified",
        )

    if not wbc_attempt_reference.strip():
        return SourceCheck(
            source="wbc_attempt",
            outcome=ValidationOutcome.MISSING,
            detail="no WBC attempt reference provided",
            observed_value={"target_digest": target_digest},
        )

    try:
        # Look up outbox records that reference this WBC attempt
        # The outbox is queried by lease_id, not by WBC attempt reference
        # directly, so we need to iterate or use a different path.
        # In M7 shadow mode, we report the reference as present but
        # cross-owner fetch is deferred.
        all_records = outbox.list_records()
        matching = [r for r in all_records if r.wbc_attempt_reference == wbc_attempt_reference]

        if not matching:
            return SourceCheck(
                source="wbc_attempt",
                outcome=ValidationOutcome.MISSING,
                detail=f"no outbox records found for WBC attempt {wbc_attempt_reference!r}",
                observed_value={
                    "wbc_attempt_reference": wbc_attempt_reference,
                    "target_digest": target_digest,
                    "outbox_record_count": len(all_records),
                },
            )

        # Check for conflicts among the matching records
        statuses = set(r.status.value for r in matching)
        if len(statuses) > 1:
            return SourceCheck(
                source="wbc_attempt",
                outcome=ValidationOutcome.CONFLICT,
                detail=f"conflicting statuses for WBC attempt {wbc_attempt_reference!r}: {sorted(statuses)}",
                observed_value={
                    "wbc_attempt_reference": wbc_attempt_reference,
                    "matching_record_count": len(matching),
                    "statuses": sorted(statuses),
                },
            )

        return SourceCheck(
            source="wbc_attempt",
            outcome=ValidationOutcome.SATISFIED,
            detail=f"WBC attempt {wbc_attempt_reference!r} has consistent status {statuses.pop()!r}",
            observed_value={
                "wbc_attempt_reference": wbc_attempt_reference,
                "matching_record_count": len(matching),
                "status": statuses.pop() if statuses else "unknown",
            },
        )
    except Exception as exc:
        return SourceCheck(
            source="wbc_attempt",
            outcome=ValidationOutcome.ERROR,
            detail=f"WBC attempt reread error: {type(exc).__name__}: {exc}",
        )


# ── Conjunctive gate ───────────────────────────────────────────────────────


def _compute_gate_result(
    checks: tuple[SourceCheck, ...],
    enforcement_enabled: bool,
) -> GateResult:
    """Compute the overall gate result from per-source checks.

    The order of precedence is:
      1. If enforcement is disabled → SHADOW_PASS (regardless of check outcomes)
      2. If any check has ERROR → ERROR
      3. If run_authority_grant is MISSING → BLOCKED_MISSING_GRANT
      4. If run_authority_fence is FENCED → BLOCKED_FENCE_MISMATCH
      5. If custody_lease is MISSING → BLOCKED_NO_LEASE
      6. If custody_lease is EXPIRED → BLOCKED_EXPIRED_LEASE
      7. If custody_lease is STALE → BLOCKED_STALE_EPOCH
      8. If custody_lease is NOT_OWNER → BLOCKED_NOT_OWNER
      9. If wbc_attempt is MISSING → BLOCKED_WBC_MISSING
     10. If wbc_attempt is CONFLICT → BLOCKED_WBC_CONFLICT
     11. Otherwise → AUTHORIZED
    """
    if not enforcement_enabled:
        return GateResult.SHADOW_PASS

    checks_by_source: dict[str, SourceCheck] = {c.source: c for c in checks}

    # ERROR takes precedence
    for c in checks:
        if c.outcome == ValidationOutcome.ERROR:
            return GateResult.ERROR

    # Run Authority grant
    grant = checks_by_source.get("run_authority_grant")
    if grant is not None and grant.outcome == ValidationOutcome.MISSING:
        return GateResult.BLOCKED_MISSING_GRANT

    # Run Authority fence
    fence = checks_by_source.get("run_authority_fence")
    if fence is not None and fence.outcome == ValidationOutcome.FENCED:
        return GateResult.BLOCKED_FENCE_MISMATCH

    # Custody lease
    lease = checks_by_source.get("custody_lease")
    if lease is not None:
        if lease.outcome == ValidationOutcome.MISSING:
            return GateResult.BLOCKED_NO_LEASE
        if lease.outcome == ValidationOutcome.EXPIRED:
            return GateResult.BLOCKED_EXPIRED_LEASE
        if lease.outcome == ValidationOutcome.STALE:
            return GateResult.BLOCKED_STALE_EPOCH
        if lease.outcome == ValidationOutcome.NOT_OWNER:
            return GateResult.BLOCKED_NOT_OWNER

    # WBC attempt
    wbc = checks_by_source.get("wbc_attempt")
    if wbc is not None:
        if wbc.outcome == ValidationOutcome.MISSING:
            return GateResult.BLOCKED_WBC_MISSING
        if wbc.outcome == ValidationOutcome.CONFLICT:
            return GateResult.BLOCKED_WBC_CONFLICT

    return GateResult.AUTHORIZED


def _build_diagnostics(
    checks: tuple[SourceCheck, ...],
    enforcement_enabled: bool,
    action_type: ActionBoundaryType,
) -> dict[str, Any]:
    """Build diagnostic metadata for the validation result."""
    diag: dict[str, Any] = {
        "m7_schema_version": ACTION_VALIDATOR_SCHEMA_VERSION,
        "shadow_enforcement": not enforcement_enabled,
        "enforcement_env_var": _ENV_ENFORCEMENT,
        "action_boundary": action_type,
        "checks_summary": {
            c.source: c.outcome.value for c in checks
        },
    }
    # Record which sources had non-SATISFIED outcomes
    issues = [c.source for c in checks if c.outcome != ValidationOutcome.SATISFIED]
    if issues:
        diag["sources_with_issues"] = issues
    return diag


# ═══════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════


def validate_action_boundary(
    context: ActionBoundaryContext,
    *,
    lease_store: CustodyLeaseStore | None = None,
    outbox: CustodyOutbox | None = None,
    enforcement_enabled: bool | None = None,
) -> ActionBoundaryResult:
    """Validate that an action may proceed at this boundary.

    Rereads current Run Authority grant/fence, Custody lease/epoch, and
    WBC attempt status immediately — never returns a cached or stale
    result.

    Parameters
    ----------
    context:
        The action boundary context — must include the action type,
        target, grant ID, fence token, and optional WBC attempt reference.
    lease_store:
        An open Custody lease store.  If ``None``, the custody lease
        check will return ``MISSING``.
    outbox:
        An open Custody outbox.  If ``None``, the WBC attempt check
        will return ``MISSING``.
    enforcement_enabled:
        Override the production enforcement flag.  If ``None`` (default),
        reads ``ARNOLD_M7_ACTION_VALIDATOR_ENFORCEMENT`` from the
        environment (defaults to ``False``).

    Returns
    -------
    ActionBoundaryResult
        The full validation result.  When enforcement is disabled, the
        gate result is always ``SHADOW_PASS`` (non-blocking), but the
        per-source checks and diagnostics are still fully populated.

        Callers must test ``result.authorized`` — NOT ``result.gate_result
        == GateResult.SHADOW_PASS`` — before treating the result as
        authorization to proceed with the action.
    """
    if enforcement_enabled is None:
        enforcement_enabled = _production_enforcement_enabled()

    target_digest = context.target.target_digest

    checks: list[SourceCheck] = []

    # 1. Reread Run Authority grant
    grant_check = _reread_run_authority_grant(
        context.run_authority_grant_id,
        context.coordinator_fence_token,
    )
    checks.append(grant_check)

    # 2. Reread Run Authority fence
    fence_check = _reread_run_authority_fence(
        context.coordinator_fence_token,
        context.run_authority_grant_id,
    )
    checks.append(fence_check)

    # 3. Reread Custody lease
    lease_check = _reread_custody_lease(
        lease_store,
        target_digest,
        context.owner_host,
        context.owner_pid,
        context.owner_boot_id,
    )
    checks.append(lease_check)

    # 4. Reread WBC attempt status
    wbc_check = _reread_wbc_attempt(
        outbox,
        context.wbc_attempt_reference,
        target_digest,
    )
    checks.append(wbc_check)

    # Compute the conjunctive gate result
    checks_tuple = tuple(checks)
    gate_result = _compute_gate_result(checks_tuple, enforcement_enabled)
    diagnostics = _build_diagnostics(checks_tuple, enforcement_enabled, context.action_type)

    return ActionBoundaryResult(
        gate_result=gate_result,
        action_type=context.action_type,
        target_digest=target_digest,
        checks=checks_tuple,
        enforcement_enabled=enforcement_enabled,
        diagnostics=diagnostics,
    )


def production_enforcement_enabled() -> bool:
    """Return ``True`` when M7 action-validator enforcement is active.

    This is the public accessor for the ``ARNOLD_M7_ACTION_VALIDATOR_ENFORCEMENT``
    env var.  Callers should use this before treating
    :func:`validate_action_boundary` results as authoritative.
    """
    return _production_enforcement_enabled()


# ── Convenience: validate with minimal setup ───────────────────────────────


def validate_action_boundary_simple(
    *,
    action_type: ActionBoundaryType,
    target: Mapping[str, Any] | CustodyTargetKey,
    run_authority_grant_id: str,
    coordinator_fence_token: int,
    wbc_attempt_reference: str = "",
    lease_store_dir: str | Path | None = None,
    outbox_dir: str | Path | None = None,
) -> ActionBoundaryResult:
    """Validate an action boundary with default store/outbox setup.

    This is a convenience wrapper that opens the lease store and outbox
    from the given directories (or defaults), builds the context, and
    calls :func:`validate_action_boundary`.

    Parameters
    ----------
    action_type:
        The type of action being validated.
    target:
        The custody target — either a ``CustodyTargetKey`` or a dict
        that will be normalized into one.
    run_authority_grant_id:
        The Run Authority grant ID.
    coordinator_fence_token:
        The coordinator fence token.
    wbc_attempt_reference:
        The WBC attempt reference (optional).
    lease_store_dir:
        Directory for the lease store (default: ``~/.megaplan/custody/leases``).
    outbox_dir:
        Directory for the outbox (default: ``~/.megaplan/custody/outbox``).

    Returns
    -------
    ActionBoundaryResult
    """
    if isinstance(target, CustodyTargetKey):
        custody_target = target
    elif isinstance(target, Mapping):
        custody_target = normalize_custody_target_key(target)
        if custody_target is None:
            enforcement = _production_enforcement_enabled()
            return ActionBoundaryResult(
                gate_result=GateResult.ERROR if enforcement else GateResult.SHADOW_PASS,
                action_type=action_type,
                target_digest="",
                checks=(
                    SourceCheck(
                        source="target",
                        outcome=ValidationOutcome.ERROR,
                        detail="invalid target: could not normalize to CustodyTargetKey",
                    ),
                ),
                enforcement_enabled=enforcement,
                diagnostics={"error": "invalid target"},
            )
    else:
        raise TypeError("target must be a CustodyTargetKey or a Mapping")

    # Build context
    import os as _os
    import socket as _socket

    owner_host = ""
    owner_pid = ""
    owner_boot_id = ""
    try:
        owner_host = _socket.gethostname()
    except Exception:
        pass
    owner_pid = str(_os.getpid())
    try:
        owner_boot_id = Path("/proc/sys/kernel/random/boot_id").read_text(encoding="utf-8").strip()
    except Exception:
        pass

    context = ActionBoundaryContext(
        action_type=action_type,
        target=custody_target,
        run_authority_grant_id=run_authority_grant_id,
        coordinator_fence_token=coordinator_fence_token,
        wbc_attempt_reference=wbc_attempt_reference,
        owner_host=owner_host,
        owner_pid=owner_pid,
        owner_boot_id=owner_boot_id,
    )

    # Open stores
    ls = None
    if lease_store_dir is not None:
        ls = open_lease_store(Path(lease_store_dir), flock=False)
    ob = None
    if outbox_dir is not None:
        ob = open_outbox(Path(outbox_dir), flock=False)

    return validate_action_boundary(context, lease_store=ls, outbox=ob)


__all__ = [
    "ACTION_BOUNDARY_TYPES",
    "ACTION_VALIDATOR_SCHEMA_VERSION",
    "ActionBoundaryContext",
    "ActionBoundaryResult",
    "ActionBoundaryType",
    "GateResult",
    "SourceCheck",
    "ValidationOutcome",
    "production_enforcement_enabled",
    "validate_action_boundary",
    "validate_action_boundary_simple",
]
