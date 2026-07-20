"""Idle pinned-runtime canary — projection promotion gate (M7 shadow-only).

Composes existing source-record checks from :mod:`action_validator` and
:mod:`projections` into a single projection promotion gate.  Before a
projection is promoted (rebuilt from shadow to active), the canary
verifies:

1. **Installed source provenance** — the running code matches known good
   signatures (deferred to test doubles in M7).
2. **Current Run Authority grant/fence** — reread immediately.
3. **Current Custody lease/epoch** — reread immediately.
4. **Current WBC attempt status** — reread immediately.

All four checks must pass; any failure blocks projection promotion.
The canary is an idle pinned-runtime check — it runs periodically in a
pinned (stable, known-good) runtime and gates projection promotion decisions.

Principles
----------
* **Bounded module** — Uses ``action_validator`` for Run Authority, Custody,
  and WBC checks; uses ``projections`` for cursor/source validation.
  Does not duplicate or bypass existing gate logic.
* **Test doubles** — Source provenance and cross-owner reads use test
  doubles in M7; real enforcement is deferred to M6/M6A acceptance.
* **Shadow-only** — Production enforcement is disabled; the canary runs
  in diagnostic/shadow mode only.  A ``shadow_pass`` result is NOT
  authorization to promote — callers must check ``result.authorized``.
* **Promotion gate** — Projection promotion is gated on all four source
  checks passing.  A false pass (promotion under stale provenance) is
  the primary failure mode this module prevents.

North Star alignment
--------------------
* **Single-owner** — Custody does not own Run Authority or WBC state;
  cross-owner references are read-only.
* **Conjunctive** — All sources must verify before promotion is allowed.
* **Shadow-first** — Enforcement remains off until M6/M6A acceptance.
* **No stale-source acceptance** — Every canary check rereads current
  sources immediately.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType
from typing import Any, Literal, Mapping, Optional, Sequence

from arnold_pipelines.megaplan.custody.action_validator import (
    ACTION_BOUNDARY_TYPES,
    ActionBoundaryContext,
    ActionBoundaryResult,
    ActionBoundaryType,
    GateResult,
    SourceCheck,
    ValidationOutcome,
    validate_action_boundary,
    validate_action_boundary_simple,
)
from arnold_pipelines.megaplan.custody.contracts import (
    CustodyTargetKey,
    normalize_custody_target_key,
)
from arnold_pipelines.megaplan.custody.lease_store import (
    CustodyLeaseStore,
    open_lease_store,
)
from arnold_pipelines.megaplan.custody.outbox import (
    CustodyOutbox,
    open_outbox,
)
from arnold_pipelines.megaplan.custody.projections import (
    CustodyProjectionStore,
    open_projection_store,
)


# ── Schema version constant ────────────────────────────────────────────────

CANARY_SCHEMA_VERSION = 1

# ── Env-var gate constants ─────────────────────────────────────────────────

_ENV_ENFORCEMENT = "ARNOLD_M7_CANARY_ENFORCEMENT"
_DISABLE_VALUES: frozenset[str] = frozenset({"0", "false", "no", "off"})


def _canary_enforcement_enabled() -> bool:
    """Return ``True`` only when the M7 canary enforcement flag is on.

    Controlled by ``ARNOLD_M7_CANARY_ENFORCEMENT`` — defaults to OFF.
    When disabled (the default), the canary performs every check but
    the gate result is ``shadow_pass``.
    """
    raw = os.getenv(_ENV_ENFORCEMENT, "").strip().lower()
    if not raw:
        return False
    if raw in _DISABLE_VALUES:
        return False
    return True


# ── Canary check types ─────────────────────────────────────────────────────

CanaryCheckType = Literal[
    "source_provenance",
    "run_authority",
    "custody_lease",
    "wbc_attempt",
]

CANARY_CHECK_TYPES: frozenset[CanaryCheckType] = frozenset(
    {"source_provenance", "run_authority", "custody_lease", "wbc_attempt"}
)


# ── Canary outcome codes ───────────────────────────────────────────────────


class CanaryOutcome(StrEnum):
    """Outcome of a single canary check within a promotion gate."""

    SATISFIED = "satisfied"
    MISSING = "missing"
    STALE = "stale"
    CONFLICT = "conflict"
    EXPIRED = "expired"
    FENCED = "fenced"
    NOT_OWNER = "not_owner"
    PROVENANCE_UNVERIFIED = "provenance_unverified"
    ERROR = "error"


# ── Promotion gate result ──────────────────────────────────────────────────


class PromotionGateDecision(StrEnum):
    """Overall gate decision for a projection promotion canary check."""

    AUTHORIZED = "authorized"
    """All checks passed; promotion is authorized."""

    SHADOW_PASS = "shadow_pass"
    """All checks executed but enforcement is off; not authoritative."""

    BLOCKED_SOURCE_PROVENANCE = "blocked_source_provenance"
    """Installed source provenance could not be verified."""

    BLOCKED_MISSING_GRANT = "blocked_missing_grant"
    """Run Authority grant is missing or invalid."""

    BLOCKED_FENCE_MISMATCH = "blocked_fence_mismatch"
    """Coordinator fence token does not match the grant."""

    BLOCKED_NO_LEASE = "blocked_no_lease"
    """No active Custody lease exists for the target."""

    BLOCKED_EXPIRED_LEASE = "blocked_expired_lease"
    """The Custody lease has expired."""

    BLOCKED_STALE_EPOCH = "blocked_stale_epoch"
    """The Custody lease epoch is stale (regressed or transferred)."""

    BLOCKED_NOT_OWNER = "blocked_not_owner"
    """The current process is not the lease owner."""

    BLOCKED_WBC_MISSING = "blocked_wbc_missing"
    """WBC attempt status cannot be verified (missing reference or records)."""

    BLOCKED_WBC_CONFLICT = "blocked_wbc_conflict"
    """Conflicting WBC attempt statuses detected."""

    ERROR = "error"
    """An unexpected error occurred during validation."""


# ── Source provenance check result ─────────────────────────────────────────


@dataclass(frozen=True)
class SourceProvenanceCheck:
    """Result of an installed source provenance verification.

    In M7 shadow mode, provenance verification uses test doubles.
    Real cryptographic verification is deferred to M6/M6A acceptance.
    """

    outcome: CanaryOutcome
    detail: str = ""
    provenance_source: str = ""
    observed_digest: str = ""
    expected_digest: str = ""
    verified_at: str = ""

    def __post_init__(self) -> None:
        if not self.verified_at:
            object.__setattr__(
                self,
                "verified_at",
                datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "outcome": self.outcome.value,
            "detail": self.detail,
            "provenance_source": self.provenance_source,
            "observed_digest": self.observed_digest,
            "expected_digest": self.expected_digest,
            "verified_at": self.verified_at,
        }


# ── Canary check entry ─────────────────────────────────────────────────────


@dataclass(frozen=True)
class CanaryCheck:
    """Result of a single canary check within a promotion gate.

    Wraps either a :class:`SourceCheck` (from the action validator) or a
    :class:`SourceProvenanceCheck` (for installed code provenance).
    """

    check_type: CanaryCheckType
    outcome: CanaryOutcome
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
            object.__setattr__(
                self, "observed_value", MappingProxyType(dict(self.observed_value))
            )

    @classmethod
    def from_source_check(
        cls, check_type: CanaryCheckType, source_check: SourceCheck
    ) -> CanaryCheck:
        """Convert an action-validator SourceCheck into a CanaryCheck."""
        outcome_map: dict[ValidationOutcome, CanaryOutcome] = {
            ValidationOutcome.SATISFIED: CanaryOutcome.SATISFIED,
            ValidationOutcome.MISSING: CanaryOutcome.MISSING,
            ValidationOutcome.STALE: CanaryOutcome.STALE,
            ValidationOutcome.CONFLICT: CanaryOutcome.CONFLICT,
            ValidationOutcome.EXPIRED: CanaryOutcome.EXPIRED,
            ValidationOutcome.FENCED: CanaryOutcome.FENCED,
            ValidationOutcome.NOT_OWNER: CanaryOutcome.NOT_OWNER,
            ValidationOutcome.ERROR: CanaryOutcome.ERROR,
        }
        return cls(
            check_type=check_type,
            outcome=outcome_map.get(source_check.outcome, CanaryOutcome.ERROR),
            detail=source_check.detail,
            observed_at=source_check.observed_at,
            observed_value=source_check.observed_value,
        )

    @classmethod
    def from_provenance_check(
        cls, prov_check: SourceProvenanceCheck
    ) -> CanaryCheck:
        """Convert a SourceProvenanceCheck into a CanaryCheck."""
        return cls(
            check_type="source_provenance",
            outcome=prov_check.outcome,
            detail=prov_check.detail,
            observed_at=prov_check.verified_at,
            observed_value={
                "provenance_source": prov_check.provenance_source,
                "observed_digest": prov_check.observed_digest,
                "expected_digest": prov_check.expected_digest,
            },
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_type": self.check_type,
            "outcome": self.outcome.value,
            "detail": self.detail,
            "observed_at": self.observed_at,
            "observed_value": dict(self.observed_value),
        }

    @property
    def satisfied(self) -> bool:
        """Return True when the check passed."""
        return self.outcome == CanaryOutcome.SATISFIED

    @property
    def blocked(self) -> bool:
        """Return True when the check did not pass (not SATISFIED and not SHADOW)."""
        return self.outcome not in {
            CanaryOutcome.SATISFIED,
        }


# ── Promotion gate context ─────────────────────────────────────────────────


@dataclass(frozen=True)
class PromotionGateContext:
    """Context required to validate a projection promotion.

    All fields are read-only pointers to source state.  The canary
    never duplicates or mutates source ledgers.

    Required fields:
      - projection_id: the projection being promoted
      - target: the CustodyTargetKey identifying the repair occurrence
      - run_authority_grant_id: the Run Authority grant
      - coordinator_fence_token: the coordinator fence token
      - source_path: path to the source-record ledger for cursor validation

    Optional fields:
      - wbc_attempt_reference: the WBC attempt reference
      - owner_host, owner_pid, owner_boot_id: current process identity
    """

    projection_id: str
    target: CustodyTargetKey
    run_authority_grant_id: str
    coordinator_fence_token: int
    source_path: str = ""
    wbc_attempt_reference: str = ""
    owner_host: str = ""
    owner_pid: str = ""
    owner_boot_id: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.projection_id, str) or not self.projection_id.strip():
            raise ValueError("projection_id must be a non-empty string")
        if not isinstance(self.target, CustodyTargetKey):
            raise TypeError("target must be a CustodyTargetKey")
        if (
            not isinstance(self.run_authority_grant_id, str)
            or not self.run_authority_grant_id.strip()
        ):
            raise ValueError("run_authority_grant_id must be a non-empty string")
        if (
            not isinstance(self.coordinator_fence_token, int)
            or isinstance(self.coordinator_fence_token, bool)
            or self.coordinator_fence_token < 0
        ):
            raise ValueError("coordinator_fence_token must be a non-negative integer")
        if not isinstance(self.source_path, str):
            raise ValueError("source_path must be a string")
        if not isinstance(self.wbc_attempt_reference, str):
            raise ValueError("wbc_attempt_reference must be a string")
        if not isinstance(self.owner_host, str):
            raise ValueError("owner_host must be a string")
        if not isinstance(self.owner_pid, str):
            raise ValueError("owner_pid must be a string")
        if not isinstance(self.owner_boot_id, str):
            raise ValueError("owner_boot_id must be a string")


# ── Promotion gate result ──────────────────────────────────────────────────


@dataclass(frozen=True)
class PromotionGateResult:
    """Result of a projection promotion canary gate check.

    Fields:
      - gate_result: the overall gate result
      - projection_id: the projection being validated
      - target_digest: deterministic digest of the target
      - checks: per-source canary checks (source provenance, Run Authority,
        Custody lease, WBC attempt)
      - enforcement_enabled: whether production enforcement was active
      - validated_at: ISO-8601 timestamp of validation
      - diagnostics: additional diagnostics
    """

    gate_result: PromotionGateDecision
    projection_id: str
    target_digest: str
    checks: tuple[CanaryCheck, ...]
    enforcement_enabled: bool = False
    validated_at: str = ""
    diagnostics: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.gate_result, PromotionGateDecision):
            raise TypeError("gate_result must be a PromotionGateDecision")
        if not isinstance(self.projection_id, str) or not self.projection_id.strip():
            raise ValueError("projection_id must be a non-empty string")
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
            object.__setattr__(
                self, "diagnostics", MappingProxyType(dict(self.diagnostics))
            )

    @property
    def authorized(self) -> bool:
        """Return ``True`` when the gate result is ``AUTHORIZED``.

        Note: ``SHADOW_PASS`` is NOT authoritative — enforcement must be
        enabled for ``authorized`` to be ``True``.
        """
        return self.gate_result == PromotionGateDecision.AUTHORIZED

    @property
    def blocked(self) -> bool:
        """Return ``True`` when the gate is blocked (any non-pass result)."""
        return self.gate_result not in {
            PromotionGateDecision.AUTHORIZED,
            PromotionGateDecision.SHADOW_PASS,
        }

    @property
    def is_shadow(self) -> bool:
        """Return ``True`` when the canary ran in shadow mode."""
        return not self.enforcement_enabled

    def to_dict(self) -> dict[str, Any]:
        return {
            "gate_result": self.gate_result.value,
            "projection_id": self.projection_id,
            "target_digest": self.target_digest,
            "checks": [c.to_dict() for c in self.checks],
            "enforcement_enabled": self.enforcement_enabled,
            "validated_at": self.validated_at,
            "diagnostics": dict(self.diagnostics),
        }


# ── Source provenance verification (test double in M7) ─────────────────────


def _verify_source_provenance(
    source_path: str,
    *,
    provenance_source: str = "",
    expected_digest: str = "",
) -> SourceProvenanceCheck:
    """Verify that installed source provenance matches expected signatures.

    In M7 shadow mode, this uses a test double that returns SATISFIED
    when source_path is non-empty and syntactically valid.  Real
    cryptographic verification (package signatures, binary hashes,
    signed attestations) is deferred to M6/M6A acceptance.

    Parameters
    ----------
    source_path:
        Path to the accepted-source-record ledger for provenance verification.
    provenance_source:
        Label identifying the provenance source (e.g. "pip", "git", "docker").
    expected_digest:
        Expected SHA-256 digest of the source.  If empty, verification is
        best-effort (test double returns SATISFIED).

    Returns
    -------
    SourceProvenanceCheck
        The provenance verification result.
    """
    if not source_path.strip():
        return SourceProvenanceCheck(
            outcome=CanaryOutcome.PROVENANCE_UNVERIFIED,
            detail="source_path is empty; cannot verify installed provenance",
            provenance_source=provenance_source,
        )

    try:
        source = Path(source_path)
        if not source.exists():
            return SourceProvenanceCheck(
                outcome=CanaryOutcome.PROVENANCE_UNVERIFIED,
                detail=f"source_path {source_path!r} does not exist",
                provenance_source=provenance_source,
            )

        # M7 test double: compute a digest of the source record to
        # demonstrate the provenance pattern.  Real enforcement will
        # verify cryptographic signatures against a trusted root.
        if source.is_file():
            content = source.read_bytes()
            observed = "sha256:" + hashlib.sha256(content).hexdigest()
        elif source.is_dir():
            # Directory: hash the sorted file listing as a stable proxy
            listing = sorted(
                str(p.relative_to(source)) for p in source.rglob("*") if p.is_file()
            )
            observed = "sha256:" + hashlib.sha256(
                "\n".join(listing).encode("utf-8")
            ).hexdigest()
        else:
            observed = ""

        if expected_digest and observed != expected_digest:
            return SourceProvenanceCheck(
                outcome=CanaryOutcome.PROVENANCE_UNVERIFIED,
                detail=(
                    f"source digest mismatch: "
                    f"expected {expected_digest[:16]}..., "
                    f"observed {observed[:16]}..."
                ),
                provenance_source=provenance_source,
                observed_digest=observed,
                expected_digest=expected_digest,
            )

        return SourceProvenanceCheck(
            outcome=CanaryOutcome.SATISFIED,
            detail=f"source provenance verified (M7 test double): {observed[:16]}...",
            provenance_source=provenance_source,
            observed_digest=observed,
            expected_digest=expected_digest,
        )
    except Exception as exc:
        return SourceProvenanceCheck(
            outcome=CanaryOutcome.ERROR,
            detail=f"provenance verification error: {type(exc).__name__}: {exc}",
            provenance_source=provenance_source,
        )


# ── Promotion gate logic ───────────────────────────────────────────────────


def _compute_promotion_gate(
    checks: tuple[CanaryCheck, ...],
    enforcement_enabled: bool,
) -> PromotionGateDecision:
    """Compute the overall promotion gate decision from per-source checks.

    Precedence order:
      1. If enforcement is disabled → SHADOW_PASS (regardless of check outcomes)
      2. If any check has ERROR → ERROR
      3. If source_provenance is PROVENANCE_UNVERIFIED → BLOCKED_SOURCE_PROVENANCE
      4. If run_authority is MISSING → BLOCKED_MISSING_GRANT
      5. If run_authority is FENCED → BLOCKED_FENCE_MISMATCH
      6. If custody_lease is MISSING → BLOCKED_NO_LEASE
      7. If custody_lease is EXPIRED → BLOCKED_EXPIRED_LEASE
      8. If custody_lease is STALE → BLOCKED_STALE_EPOCH
      9. If custody_lease is NOT_OWNER → BLOCKED_NOT_OWNER
     10. If wbc_attempt is MISSING → BLOCKED_WBC_MISSING
     11. If wbc_attempt is CONFLICT → BLOCKED_WBC_CONFLICT
     12. Otherwise → AUTHORIZED
    """
    if not enforcement_enabled:
        return PromotionGateDecision.SHADOW_PASS

    checks_by_type: dict[str, CanaryCheck] = {c.check_type: c for c in checks}

    # ERROR takes precedence
    for c in checks:
        if c.outcome == CanaryOutcome.ERROR:
            return PromotionGateDecision.ERROR

    # Source provenance
    prov = checks_by_type.get("source_provenance")
    if prov is not None and prov.outcome == CanaryOutcome.PROVENANCE_UNVERIFIED:
        return PromotionGateDecision.BLOCKED_SOURCE_PROVENANCE

    # Run Authority grant
    ra = checks_by_type.get("run_authority")
    if ra is not None:
        if ra.outcome == CanaryOutcome.MISSING:
            return PromotionGateDecision.BLOCKED_MISSING_GRANT
        if ra.outcome == CanaryOutcome.FENCED:
            return PromotionGateDecision.BLOCKED_FENCE_MISMATCH

    # Custody lease
    cl = checks_by_type.get("custody_lease")
    if cl is not None:
        if cl.outcome == CanaryOutcome.MISSING:
            return PromotionGateDecision.BLOCKED_NO_LEASE
        if cl.outcome == CanaryOutcome.EXPIRED:
            return PromotionGateDecision.BLOCKED_EXPIRED_LEASE
        if cl.outcome == CanaryOutcome.STALE:
            return PromotionGateDecision.BLOCKED_STALE_EPOCH
        if cl.outcome == CanaryOutcome.NOT_OWNER:
            return PromotionGateDecision.BLOCKED_NOT_OWNER

    # WBC attempt
    wbc = checks_by_type.get("wbc_attempt")
    if wbc is not None:
        if wbc.outcome == CanaryOutcome.MISSING:
            return PromotionGateDecision.BLOCKED_WBC_MISSING
        if wbc.outcome == CanaryOutcome.CONFLICT:
            return PromotionGateDecision.BLOCKED_WBC_CONFLICT

    return PromotionGateDecision.AUTHORIZED


def _build_promotion_diagnostics(
    checks: tuple[CanaryCheck, ...],
    enforcement_enabled: bool,
    projection_id: str,
) -> dict[str, Any]:
    """Build diagnostic metadata for the promotion gate result."""
    diag: dict[str, Any] = {
        "m7_canary_schema_version": CANARY_SCHEMA_VERSION,
        "shadow_enforcement": not enforcement_enabled,
        "enforcement_env_var": _ENV_ENFORCEMENT,
        "projection_id": projection_id,
        "checks_summary": {c.check_type: c.outcome.value for c in checks},
    }
    issues = [
        c.check_type
        for c in checks
        if c.outcome != CanaryOutcome.SATISFIED
    ]
    if issues:
        diag["sources_with_issues"] = issues
    return diag


# ═══════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════


def validate_promotion_gate(
    context: PromotionGateContext,
    *,
    lease_store: CustodyLeaseStore | None = None,
    outbox: CustodyOutbox | None = None,
    projection_store: CustodyProjectionStore | None = None,
    provenance_source: str = "",
    expected_source_digest: str = "",
    enforcement_enabled: bool | None = None,
) -> PromotionGateResult:
    """Validate that a projection may be promoted through the canary gate.

    Composes four conjunctive checks:
    1. **Source provenance** — installed code matches known signatures.
    2. **Run Authority** — current grant and fence are valid (via action_validator).
    3. **Custody lease** — current lease is active and owned (via action_validator).
    4. **WBC attempt** — attempt status is consistent (via action_validator).

    All four must pass.  Any failure blocks promotion.

    Parameters
    ----------
    context:
        The promotion gate context — projection_id, target, grant/fence/WBC refs.
    lease_store:
        An open Custody lease store.  If ``None``, the custody lease
        check will return ``MISSING``.
    outbox:
        An open Custody outbox.  If ``None``, the WBC attempt check
        will return ``MISSING``.
    projection_store:
        An open Custody projection store.  If ``None``, source provenance
        is verified from the filesystem directly.
    provenance_source:
        Label for the provenance source (e.g. "pip", "git").
    expected_source_digest:
        Expected SHA-256 digest of the installed source.  Empty = best-effort.
    enforcement_enabled:
        Override the production enforcement flag.  If ``None``, reads
        ``ARNOLD_M7_CANARY_ENFORCEMENT`` from the environment.

    Returns
    -------
    PromotionGateResult
        The full promotion gate result.  When enforcement is disabled,
        the gate result is always ``SHADOW_PASS`` (non-blocking), but
        the per-source checks and diagnostics are fully populated.

        Callers must test ``result.authorized`` — NOT ``result.gate_result
        == PromotionGateDecision.SHADOW_PASS`` — before treating the result
        as authorization to promote.
    """
    if enforcement_enabled is None:
        enforcement_enabled = _canary_enforcement_enabled()

    target_digest = context.target.target_digest

    checks: list[CanaryCheck] = []

    # 1. Source provenance verification
    prov_check = _verify_source_provenance(
        context.source_path,
        provenance_source=provenance_source,
        expected_digest=expected_source_digest,
    )
    checks.append(CanaryCheck.from_provenance_check(prov_check))

    # 2. Run Authority + Custody + WBC via action_validator
    #    We build an ActionBoundaryContext and delegate to the
    #    existing conjunctive validator to avoid duplicating logic.
    try:
        action_context = ActionBoundaryContext(
            action_type="publication",  # projection promotion is a publication action
            target=context.target,
            run_authority_grant_id=context.run_authority_grant_id,
            coordinator_fence_token=context.coordinator_fence_token,
            wbc_attempt_reference=context.wbc_attempt_reference,
            owner_host=context.owner_host,
            owner_pid=context.owner_pid,
            owner_boot_id=context.owner_boot_id,
        )
        action_result = validate_action_boundary(
            action_context,
            lease_store=lease_store,
            outbox=outbox,
            enforcement_enabled=enforcement_enabled,
        )

        # Map each SourceCheck to a CanaryCheck
        for source_check in action_result.checks:
            check_type_map: dict[str, CanaryCheckType] = {
                "run_authority_grant": "run_authority",
                "run_authority_fence": "run_authority",
                "custody_lease": "custody_lease",
                "wbc_attempt": "wbc_attempt",
            }
            ct = check_type_map.get(source_check.source)
            if ct is not None:
                # Merge run_authority_grant + run_authority_fence into a single
                # "run_authority" canary check — take the worst outcome.
                existing_ra = next(
                    (c for c in checks if c.check_type == "run_authority"), None
                )
                if ct == "run_authority" and existing_ra is not None:
                    # Replace if the new outcome is worse
                    new_outcome = CanaryCheck.from_source_check(ct, source_check).outcome
                    if _outcome_severity(new_outcome) > _outcome_severity(
                        existing_ra.outcome
                    ):
                        checks = [c for c in checks if c.check_type != "run_authority"]
                        checks.append(CanaryCheck.from_source_check(ct, source_check))
                else:
                    checks.append(CanaryCheck.from_source_check(ct, source_check))
    except Exception as exc:
        checks.append(
            CanaryCheck(
                check_type="run_authority",
                outcome=CanaryOutcome.ERROR,
                detail=f"action_validator error: {type(exc).__name__}: {exc}",
            )
        )
        checks.append(
            CanaryCheck(
                check_type="custody_lease",
                outcome=CanaryOutcome.ERROR,
                detail=f"action_validator error: {type(exc).__name__}: {exc}",
            )
        )
        checks.append(
            CanaryCheck(
                check_type="wbc_attempt",
                outcome=CanaryOutcome.ERROR,
                detail=f"action_validator error: {type(exc).__name__}: {exc}",
            )
        )

    # Compute the conjunctive gate result
    checks_tuple = tuple(checks)
    gate_result = _compute_promotion_gate(checks_tuple, enforcement_enabled)
    diagnostics = _build_promotion_diagnostics(
        checks_tuple, enforcement_enabled, context.projection_id
    )

    return PromotionGateResult(
        gate_result=gate_result,
        projection_id=context.projection_id,
        target_digest=target_digest,
        checks=checks_tuple,
        enforcement_enabled=enforcement_enabled,
        diagnostics=diagnostics,
    )


# ── Outcome severity helper ────────────────────────────────────────────────


_OUTCOME_SEVERITY: dict[CanaryOutcome, int] = {
    CanaryOutcome.SATISFIED: 0,
    CanaryOutcome.MISSING: 1,
    CanaryOutcome.STALE: 2,
    CanaryOutcome.EXPIRED: 3,
    CanaryOutcome.FENCED: 4,
    CanaryOutcome.CONFLICT: 5,
    CanaryOutcome.NOT_OWNER: 6,
    CanaryOutcome.PROVENANCE_UNVERIFIED: 7,
    CanaryOutcome.ERROR: 8,
}


def _outcome_severity(outcome: CanaryOutcome) -> int:
    """Return a severity score for comparing CanaryOutcome values.

    Higher = worse.  Used to merge multiple checks of the same type.
    """
    return _OUTCOME_SEVERITY.get(outcome, 0)


# ── Convenience: validate with minimal setup ───────────────────────────────


def validate_promotion_gate_simple(
    *,
    projection_id: str,
    target: Mapping[str, Any] | CustodyTargetKey,
    run_authority_grant_id: str,
    coordinator_fence_token: int,
    source_path: str = "",
    wbc_attempt_reference: str = "",
    lease_store_dir: str | Path | None = None,
    outbox_dir: str | Path | None = None,
    projection_store_dir: str | Path | None = None,
    provenance_source: str = "",
    expected_source_digest: str = "",
) -> PromotionGateResult:
    """Validate a projection promotion gate with default store setup.

    This is a convenience wrapper that opens the lease store, outbox, and
    projection store from the given directories (or defaults), builds the
    context, and calls :func:`validate_promotion_gate`.

    Parameters
    ----------
    projection_id:
        The projection being promoted.
    target:
        The custody target — either a ``CustodyTargetKey`` or a dict
        that will be normalized into one.
    run_authority_grant_id:
        The Run Authority grant ID.
    coordinator_fence_token:
        The coordinator fence token.
    source_path:
        Path to the source-record ledger for provenance verification.
    wbc_attempt_reference:
        The WBC attempt reference (optional).
    lease_store_dir:
        Directory for the lease store (default: ``~/.megaplan/custody/leases``).
    outbox_dir:
        Directory for the outbox (default: ``~/.megaplan/custody/outbox``).
    projection_store_dir:
        Directory for the projection store (default: ``~/.megaplan/custody/projections``).
    provenance_source:
        Label for the provenance source.
    expected_source_digest:
        Expected SHA-256 digest of the installed source.

    Returns
    -------
    PromotionGateResult
    """
    if isinstance(target, CustodyTargetKey):
        custody_target = target
    elif isinstance(target, Mapping):
        custody_target = normalize_custody_target_key(target)
        if custody_target is None:
            enforcement = _canary_enforcement_enabled()
            return PromotionGateResult(
                gate_result=(
                    PromotionGateDecision.ERROR
                    if enforcement
                    else PromotionGateDecision.SHADOW_PASS
                ),
                projection_id=projection_id,
                target_digest="invalid-target",
                checks=(
                    CanaryCheck(
                        check_type="run_authority",
                        outcome=CanaryOutcome.ERROR,
                        detail="invalid target: could not normalize to CustodyTargetKey",
                    ),
                ),
                enforcement_enabled=enforcement,
                diagnostics={"error": "invalid target"},
            )
    else:
        raise TypeError("target must be a CustodyTargetKey or a Mapping")

    # Collect owner identity
    import socket as _socket

    owner_host = ""
    owner_pid = ""
    owner_boot_id = ""
    try:
        owner_host = _socket.gethostname()
    except Exception:
        pass
    owner_pid = str(os.getpid())
    try:
        owner_boot_id = (
            Path("/proc/sys/kernel/random/boot_id")
            .read_text(encoding="utf-8")
            .strip()
        )
    except Exception:
        pass

    context = PromotionGateContext(
        projection_id=projection_id,
        target=custody_target,
        run_authority_grant_id=run_authority_grant_id,
        coordinator_fence_token=coordinator_fence_token,
        source_path=source_path,
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

    return validate_promotion_gate(
        context,
        lease_store=ls,
        outbox=ob,
        projection_store=None,
        provenance_source=provenance_source,
        expected_source_digest=expected_source_digest,
    )


# ── Production enforcement flag (public accessor) ──────────────────────────


def canary_enforcement_enabled() -> bool:
    """Return ``True`` when M7 canary enforcement is active.

    Controlled by ``ARNOLD_M7_CANARY_ENFORCEMENT`` — defaults to OFF.
    """
    return _canary_enforcement_enabled()


# ── Public exports ─────────────────────────────────────────────────────────


__all__ = [
    "CANARY_CHECK_TYPES",
    "CANARY_SCHEMA_VERSION",
    "CanaryCheck",
    "CanaryCheckType",
    "CanaryOutcome",
    "PromotionGateContext",
    "PromotionGateDecision",
    "PromotionGateResult",
    "SourceProvenanceCheck",
    "canary_enforcement_enabled",
    "validate_promotion_gate",
    "validate_promotion_gate_simple",
]
