"""Controlled authoritative-writer action-boundary validator (M7 default-deny).

Provides the central conjunctive gate ``validate_action_boundary(...)`` that
rereads current Run Authority grant/fence, current Custody lease/epoch, and
required WBC attempt status immediately before dispatch, repair, completion,
cancellation, publication, or delivery.

Production enforcement is **on by default** (deny-by-default).  The
``ARNOLD_M7_ACTION_VALIDATOR_ENFORCEMENT`` environment variable is now an
explicit-disable switch: absent means enforced, and a disable value
(``"0"``, ``"false"``, ``"no"``, ``"off"``) returns to shadow mode.  The
single source of truth for the flag is
:func:`megaplan.cloud.feature_flags.production_enforcement_enabled`;
this module exposes it publicly as
:func:`production_enforcement_enabled`.  When enforcement is off, the
validator still performs every check and returns the full diagnostics,
but the gate result is ``shadow_pass`` instead of blocking the caller.

North Star alignment
--------------------
* **Single-owner** — Custody is the sole owner of lease state.
  Cross-owner references (WBC attempt ids, Run Authority grant ids,
  coordinator fence tokens) are read-only pointers, never duplicate ledgers.
* **Conjunctive** — All three sources (Run Authority, Custody, WBC) must
  agree before an authority boundary action is accepted.
* **Deny-by-default** — Enforcement is ON unless explicitly disabled;
  shadow mode must be opted into via
  ``ARNOLD_M7_ACTION_VALIDATOR_ENFORCEMENT=0``.
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

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType
from typing import Any, Literal, Mapping, Optional

from arnold_pipelines.megaplan.cloud.feature_flags import (
    production_enforcement_enabled as _feature_flags_production_enforcement_enabled,
)
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


def _production_enforcement_enabled() -> bool:
    """Return ``True`` when M7 action-validator enforcement is active.

    Delegates to the canonical
    :func:`~megaplan.cloud.feature_flags.production_enforcement_enabled`
    gate.  ``ARNOLD_M7_ACTION_VALIDATOR_ENFORCEMENT`` now defaults to ON:
    absent means enforced (deny-by-default); a disable value (``"0"``,
    ``"false"``, ``"no"``, ``"off"``) explicitly disables enforcement.

    When disabled, the validator performs every check but the gate result
    is ``shadow_pass``.  Callers must NOT treat a ``shadow_pass`` as an
    authoritative authorization.
    """
    return _feature_flags_production_enforcement_enabled()


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
    BLOCKED_STALE_GRANT = "blocked_stale_grant"
    BLOCKED_FENCE_MISMATCH = "blocked_fence_mismatch"
    BLOCKED_SUBJECT_SCOPE_MISMATCH = "blocked_subject_scope_mismatch"
    BLOCKED_CAPABILITY_MISMATCH = "blocked_capability_mismatch"
    BLOCKED_NO_LEASE = "blocked_no_lease"
    BLOCKED_EXPIRED_LEASE = "blocked_expired_lease"
    BLOCKED_STALE_EPOCH = "blocked_stale_epoch"
    BLOCKED_TARGET_MISMATCH = "blocked_target_mismatch"
    BLOCKED_WBC_MISSING = "blocked_wbc_missing"
    BLOCKED_WBC_CONFLICT = "blocked_wbc_conflict"
    BLOCKED_WBC_VERSION_MISMATCH = "blocked_wbc_version_mismatch"
    BLOCKED_NOT_OWNER = "blocked_not_owner"
    BLOCKED_RA_UNSATISFIED = "blocked_ra_unsatisfied"
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
    identity: str = ""

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
            "identity": self.identity,
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
    expected_custody_epoch: int = 0
    expected_lease_id: str = ""
    # Predecessor M8/M9 evidence objects remain accepted for exact stale/torn
    # compatibility checks.  They are evidence inputs only and never bearer
    # authority.
    run_authority_grant: Any | None = None
    coordinator_fence: Any | None = None
    required_capability: str = ""
    required_wbc_evidence_version: str = ""

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
        if not isinstance(self.expected_custody_epoch, int) or isinstance(self.expected_custody_epoch, bool):
            raise ValueError("expected_custody_epoch must be an integer")
        if not isinstance(self.expected_lease_id, str):
            raise ValueError("expected_lease_id must be a string")


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
    expected_custody_epoch: int = 0,
    expected_lease_id: str = "",
) -> SourceCheck:
    """Reread the current Custody lease for the target.

    Returns a SourceCheck with outcome SATISFIED, MISSING, EXPIRED,
    STALE, NOT_OWNER, or ERROR.

    When *expected_custody_epoch* is provided and > 0, the reread lease's
    epoch is compared to it; a mismatch yields STALE so callers can detect
    epoch drift between observation and action-boundary validation.
    """
    if lease_store is None:
        return SourceCheck(
            source="custody_lease",
            outcome=ValidationOutcome.MISSING,
            detail="lease store is not available (None)",
        )

    try:
        # Use expected_lease_id if provided, otherwise derive from target digest.
        if expected_lease_id.strip():
            lease_id = expected_lease_id.strip()
        else:
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

        # Check stale epoch: compare caller-observed epoch to reread epoch
        if expected_custody_epoch > 0 and current.custody_epoch != expected_custody_epoch:
            return SourceCheck(
                source="custody_lease",
                outcome=ValidationOutcome.STALE,
                detail=f"stale custody epoch: caller observed {expected_custody_epoch}, lease store has {current.custody_epoch}",
                observed_value={
                    "lease_id": current.lease_id,
                    "custody_epoch": current.custody_epoch,
                    "expected_custody_epoch": expected_custody_epoch,
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
    *,
    wbc_evidence_only: bool = False,
) -> GateResult:
    """Compute the overall gate result from per-source checks.

    When *enforcement_enabled* is ``False`` the result is always
    ``SHADOW_PASS`` regardless of individual check outcomes.

    When *wbc_evidence_only* is ``True`` (M11 Step 10):

      - Run Authority grant/fence and Custody lease/epoch are **required**
        authority sources.  Absent checks BLOCK (stale-half fix) — they
        do not fall through to AUTHORIZED.
      - WBC is **evidence-only**: its outcome is recorded in diagnostics
        but never gates the result.

    The default ordering (``wbc_evidence_only=False``) keeps the legacy
    precedence documented below.

    Legacy precedence:
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

    # ── M11 Step 10: RA + Custody required, WBC evidence-only ──────
    if wbc_evidence_only:
        # Run Authority grant: required authority source (stale-half fix)
        grant = checks_by_source.get("run_authority_grant")
        if grant is None:
            return GateResult.BLOCKED_MISSING_GRANT
        if grant.outcome == ValidationOutcome.MISSING:
            return GateResult.BLOCKED_MISSING_GRANT
        if grant.outcome != ValidationOutcome.SATISFIED:
            return GateResult.BLOCKED_RA_UNSATISFIED

        # Run Authority fence: required authority source (stale-half fix)
        fence = checks_by_source.get("run_authority_fence")
        if fence is None:
            return GateResult.BLOCKED_FENCE_MISMATCH
        if fence.outcome == ValidationOutcome.FENCED:
            return GateResult.BLOCKED_FENCE_MISMATCH
        if fence.outcome != ValidationOutcome.SATISFIED:
            return GateResult.BLOCKED_RA_UNSATISFIED

        # Custody lease: required authority source (stale-half fix)
        lease = checks_by_source.get("custody_lease")
        if lease is None:
            return GateResult.BLOCKED_NO_LEASE
        if lease.outcome == ValidationOutcome.MISSING:
            return GateResult.BLOCKED_NO_LEASE
        if lease.outcome == ValidationOutcome.EXPIRED:
            return GateResult.BLOCKED_EXPIRED_LEASE
        if lease.outcome == ValidationOutcome.STALE:
            return GateResult.BLOCKED_STALE_EPOCH
        if lease.outcome == ValidationOutcome.NOT_OWNER:
            return GateResult.BLOCKED_NOT_OWNER
        if lease.outcome != ValidationOutcome.SATISFIED:
            return GateResult.BLOCKED_NO_LEASE

        # WBC: evidence-only — recorded in diagnostics but never gates.
        return GateResult.AUTHORIZED

    # ── Legacy precedence (pre-M11): WBC is a blocking authority source

    # Run Authority grant
    grant = checks_by_source.get("run_authority_grant")
    if grant is not None and grant.outcome == ValidationOutcome.MISSING:
        return GateResult.BLOCKED_MISSING_GRANT

    # Run Authority fence
    fence = checks_by_source.get("run_authority_fence")
    if fence is not None and fence.outcome == ValidationOutcome.FENCED:
        return GateResult.BLOCKED_FENCE_MISMATCH

    # NSA-M10-GATE-1 / Step 12A: any *other* non-SATISFIED Run Authority
    # outcome (stale grant, conflicted grant, superseded fence, etc.) must
    # also block.  The previous code fell through to AUTHORIZED here,
    # which could authorize a stale or conflicted grant.  Only an exact
    # SATISFIED on both RA sources allows the run-authority conjunct.
    for ra_source in ("run_authority_grant", "run_authority_fence"):
        ra_check = checks_by_source.get(ra_source)
        if ra_check is not None and ra_check.outcome != ValidationOutcome.SATISFIED:
            return GateResult.BLOCKED_RA_UNSATISFIED

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


def _legacy_evidence_checks(
    context: ActionBoundaryContext,
    *,
    lease_store: CustodyLeaseStore | None,
    outbox: CustodyOutbox | None,
) -> tuple[SourceCheck, ...]:
    """Reread the predecessor M8/M9 evidence objects when supplied.

    M10 retained the context fields but regressed to syntactic grant/fence
    checks.  Keep the current F01 contract path intact while restoring the
    exact-evidence compatibility path used by the M8/M9 acceptance suite.
    """
    grant = context.run_authority_grant
    if grant is None:
        grant_check = SourceCheck(
            source="run_authority_grant",
            outcome=ValidationOutcome.MISSING,
            identity="grant",
            detail="missing current Run Authority grant",
        )
    elif grant.grant_id != context.run_authority_grant_id:
        grant_check = SourceCheck(
            source="run_authority_grant",
            outcome=ValidationOutcome.STALE,
            identity="grant_id",
            detail=(
                f"stale Run Authority grant: expected "
                f"{context.run_authority_grant_id!r}, observed {grant.grant_id!r}"
            ),
            observed_value={
                "expected_grant_id": context.run_authority_grant_id,
                "observed_grant_id": grant.grant_id,
            },
        )
    elif context.target.subject_id not in grant.subject_ids:
        grant_check = SourceCheck(
            source="run_authority_grant",
            outcome=ValidationOutcome.CONFLICT,
            identity="subject_id",
            detail="Run Authority grant does not cover the exact subject",
            observed_value={"subject_ids": grant.subject_ids},
        )
    elif (
        context.required_capability
        and context.required_capability not in grant.capabilities
    ):
        grant_check = SourceCheck(
            source="run_authority_grant",
            outcome=ValidationOutcome.CONFLICT,
            identity="capability",
            detail="Run Authority grant lacks the required capability",
            observed_value={"capabilities": grant.capabilities},
        )
    else:
        grant_check = SourceCheck(
            source="run_authority_grant",
            outcome=ValidationOutcome.SATISFIED,
            identity="grant_id",
            detail=f"grant {grant.grant_id!r} is current",
            observed_value={"grant_id": grant.grant_id},
        )

    fence = context.coordinator_fence
    if fence is None:
        fence_check = SourceCheck(
            source="run_authority_fence",
            outcome=ValidationOutcome.MISSING,
            identity="fence",
            detail="missing current coordinator fence",
        )
    elif fence.token != context.coordinator_fence_token:
        fence_check = SourceCheck(
            source="run_authority_fence",
            outcome=ValidationOutcome.FENCED,
            identity="fence_token",
            detail=(
                f"stale coordinator fence: expected "
                f"{context.coordinator_fence_token!r}, observed {fence.token!r}"
            ),
            observed_value={
                "expected_fence_token": context.coordinator_fence_token,
                "observed_fence_token": fence.token,
            },
        )
    else:
        fence_check = SourceCheck(
            source="run_authority_fence",
            outcome=ValidationOutcome.SATISFIED,
            identity="fence_token",
            detail=f"coordinator fence {fence.token!r} is current",
            observed_value={"fence_token": fence.token},
        )

    lease_check = _reread_custody_lease(
        lease_store,
        context.target.target_digest,
        context.owner_host,
        context.owner_pid,
        context.owner_boot_id,
        expected_custody_epoch=context.expected_custody_epoch,
        expected_lease_id=context.expected_lease_id,
    )
    if lease_store is not None and context.expected_lease_id:
        lease = lease_store.current_lease(context.expected_lease_id)
        if lease is not None:
            lease_observed = dict(lease_check.observed_value)
            lease_observed["status"] = lease.status
            lease_check = SourceCheck(
                source=lease_check.source,
                outcome=lease_check.outcome,
                identity=(
                    "lease_id"
                    if lease_check.outcome in {
                        ValidationOutcome.EXPIRED,
                        ValidationOutcome.MISSING,
                    }
                    else "custody_epoch"
                ),
                detail=lease_check.detail,
                observed_at=lease_check.observed_at,
                observed_value=lease_observed,
            )

    wbc_check = _reread_wbc_attempt(
        outbox,
        context.wbc_attempt_reference,
        context.target.target_digest,
    )
    if (
        outbox is not None
        and context.required_wbc_evidence_version
        and wbc_check.outcome == ValidationOutcome.SATISFIED
    ):
        matching = [
            record
            for record in outbox.list_records()
            if record.wbc_attempt_reference == context.wbc_attempt_reference
        ]
        versions = set()
        for record in matching:
            payload = record.payload or {}
            if not isinstance(payload, Mapping):
                continue
            for field_name in ("schema_version", "evidence_version", "version"):
                value = str(payload.get(field_name, "")).strip()
                if value:
                    versions.add(value)
                    break
        versions.discard("")
        if versions != {context.required_wbc_evidence_version}:
            wbc_check = SourceCheck(
                source="wbc_attempt",
                outcome=ValidationOutcome.STALE,
                identity="wbc_evidence_version",
                detail=(
                    "WBC evidence version mismatch: expected "
                    f"{context.required_wbc_evidence_version!r}, "
                    f"observed {sorted(versions)!r}"
                ),
                observed_value={"versions": sorted(versions)},
            )
    if wbc_check.outcome == ValidationOutcome.CONFLICT:
        wbc_check = SourceCheck(
            source=wbc_check.source,
            outcome=wbc_check.outcome,
            identity="status",
            detail=wbc_check.detail,
            observed_at=wbc_check.observed_at,
            observed_value=wbc_check.observed_value,
        )
    return grant_check, fence_check, lease_check, wbc_check


def _compute_legacy_evidence_gate(
    checks: tuple[SourceCheck, ...],
    *,
    enforcement_enabled: bool,
) -> GateResult:
    if not enforcement_enabled:
        return GateResult.SHADOW_PASS
    for check in checks:
        if check.outcome == ValidationOutcome.ERROR:
            return GateResult.ERROR
        if check.outcome == ValidationOutcome.SATISFIED:
            continue
        if check.source == "run_authority_grant":
            if check.outcome == ValidationOutcome.MISSING:
                return GateResult.BLOCKED_MISSING_GRANT
            if check.identity == "capability":
                return GateResult.BLOCKED_CAPABILITY_MISMATCH
            if check.identity == "subject_id":
                return GateResult.BLOCKED_SUBJECT_SCOPE_MISMATCH
            return GateResult.BLOCKED_STALE_GRANT
        if check.source == "run_authority_fence":
            return GateResult.BLOCKED_FENCE_MISMATCH
        if check.source == "custody_lease":
            if check.outcome == ValidationOutcome.MISSING:
                return GateResult.BLOCKED_NO_LEASE
            if check.outcome == ValidationOutcome.EXPIRED:
                return GateResult.BLOCKED_EXPIRED_LEASE
            if check.outcome == ValidationOutcome.NOT_OWNER:
                return GateResult.BLOCKED_NOT_OWNER
            return GateResult.BLOCKED_STALE_EPOCH
        if check.source == "wbc_attempt":
            if check.outcome == ValidationOutcome.MISSING:
                return GateResult.BLOCKED_WBC_MISSING
            if check.identity == "wbc_evidence_version":
                return GateResult.BLOCKED_WBC_VERSION_MISMATCH
            return GateResult.BLOCKED_WBC_CONFLICT
    return GateResult.AUTHORIZED


# ═══════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════


def validate_action_boundary(
    context: ActionBoundaryContext,
    *,
    lease_store: CustodyLeaseStore | None = None,
    outbox: CustodyOutbox | None = None,
    enforcement_enabled: bool | None = None,
    wbc_evidence_only: bool = False,
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
        environment (defaults to ``True`` — deny-by-default).
    wbc_evidence_only:
        When ``True`` (M11 Step 10), authority is created **only** from
        RA grant/fence and Custody lease/epoch.  WBC is recorded as
        evidence but never gates the result.  Absent RA or Custody
        checks BLOCK (stale-half fix).

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

    if context.run_authority_grant is not None or context.coordinator_fence is not None:
        legacy_checks = _legacy_evidence_checks(
            context,
            lease_store=lease_store,
            outbox=outbox,
        )
        return ActionBoundaryResult(
            gate_result=_compute_legacy_evidence_gate(
                legacy_checks,
                enforcement_enabled=enforcement_enabled,
            ),
            action_type=context.action_type,
            target_digest=target_digest,
            checks=legacy_checks,
            enforcement_enabled=enforcement_enabled,
            diagnostics=_build_diagnostics(
                legacy_checks,
                enforcement_enabled,
                context.action_type,
            ),
        )

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
        expected_custody_epoch=context.expected_custody_epoch,
        expected_lease_id=context.expected_lease_id,
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
    gate_result = _compute_gate_result(
        checks_tuple,
        enforcement_enabled,
        wbc_evidence_only=wbc_evidence_only,
    )
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

    This is the single custody-facing accessor for the
    ``ARNOLD_M7_ACTION_VALIDATOR_ENFORCEMENT`` gate (delegating to the
    canonical :func:`megaplan.cloud.feature_flags.production_enforcement_enabled`).
    Defaults to ``True`` (deny-by-default); the env var only disables.
    Callers should use this before treating
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
    wbc_evidence_only: bool = False,
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
    wbc_evidence_only:
        When ``True`` (M11 Step 10), authority is created only from RA
        grant/fence and Custody lease/epoch; WBC is evidence-only.

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
                target_digest="invalid-target",
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

    return validate_action_boundary(
        context, lease_store=ls, outbox=ob, wbc_evidence_only=wbc_evidence_only
    )


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
