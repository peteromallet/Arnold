"""Conjunctive Run Authority, Custody, and WBC action-boundary validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
import os
from pathlib import Path
from typing import Any, Literal, Mapping

from arnold_pipelines.run_authority import (
    CapabilityGrant,
    ContractError,
    CoordinatorFence,
    IdentityConflict,
    RevisionConflict,
    validate_scope_binding,
)

from .contracts import CustodyLease, CustodyTargetKey, normalize_custody_target_key
from .lease_store import CustodyLeaseStore, open_lease_store
from .outbox import CustodyOutbox, open_outbox


ACTION_VALIDATOR_SCHEMA_VERSION = 1
_ENV_ENFORCEMENT = "ARNOLD_M7_ACTION_VALIDATOR_ENFORCEMENT"
_DISABLE_VALUES = frozenset({"", "0", "false", "no", "off"})
_LEASE_TERMINAL_STATUSES = frozenset(
    {
        "conflict",
        "expire",
        "expired",
        "quarantine",
        "quarantined",
        "reclaim",
        "release",
        "released",
    }
)

ActionBoundaryType = Literal[
    "dispatch",
    "repair",
    "completion",
    "cancellation",
    "publication",
    "delivery",
]
ACTION_BOUNDARY_TYPES = frozenset(
    {"dispatch", "repair", "completion", "cancellation", "publication", "delivery"}
)


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _production_enforcement_enabled() -> bool:
    raw = os.getenv(_ENV_ENFORCEMENT, "").strip().lower()
    if not raw:
        return False
    if raw in _DISABLE_VALUES:
        return False
    return True


class ValidationOutcome(StrEnum):
    SATISFIED = "satisfied"
    MISSING = "missing"
    STALE = "stale"
    CONFLICT = "conflict"
    EXPIRED = "expired"
    FENCED = "fenced"
    NOT_OWNER = "not_owner"
    ERROR = "error"


class GateResult(StrEnum):
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
    ERROR = "error"


@dataclass(frozen=True)
class SourceCheck:
    source: str
    outcome: ValidationOutcome
    detail: str = ""
    observed_at: str = field(default_factory=_utcnow)
    observed_value: Mapping[str, Any] = field(default_factory=dict)
    identity: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "outcome": self.outcome.value,
            "detail": self.detail,
            "observed_at": self.observed_at,
            "observed_value": dict(self.observed_value),
            "identity": self.identity,
        }


@dataclass(frozen=True)
class ActionBoundaryContext:
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
    run_authority_grant: CapabilityGrant | None = None
    coordinator_fence: CoordinatorFence | None = None
    required_capability: str = ""
    required_wbc_evidence_version: str = ""

    def __post_init__(self) -> None:
        if self.action_type not in ACTION_BOUNDARY_TYPES:
            raise ContractError(f"unsupported action boundary {self.action_type!r}")
        if not isinstance(self.target, CustodyTargetKey):
            raise TypeError("target must be a CustodyTargetKey")
        if not isinstance(self.coordinator_fence_token, int) or isinstance(self.coordinator_fence_token, bool):
            raise ContractError("coordinator_fence_token must be an integer")
        if self.coordinator_fence_token < 0:
            raise ContractError("coordinator_fence_token must be non-negative")
        if self.expected_custody_epoch < 0:
            raise ContractError("expected_custody_epoch must be non-negative")


@dataclass(frozen=True)
class ActionBoundaryResult:
    gate_result: GateResult
    action_type: ActionBoundaryType
    target_digest: str
    checks: tuple[SourceCheck, ...]
    enforcement_enabled: bool = False
    validated_at: str = field(default_factory=_utcnow)
    diagnostics: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "gate_result": self.gate_result.value,
            "action_type": self.action_type,
            "target_digest": self.target_digest,
            "checks": [check.to_dict() for check in self.checks],
            "enforcement_enabled": self.enforcement_enabled,
            "validated_at": self.validated_at,
            "diagnostics": dict(self.diagnostics),
        }


def _parse_timestamp(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _lease_is_active(lease: CustodyLease) -> bool:
    status = str(getattr(lease, "status", "")).strip().lower()
    if status in _LEASE_TERMINAL_STATUSES:
        return False
    expires = _parse_timestamp(getattr(lease, "expires_at", ""))
    return expires is None or expires > datetime.now(timezone.utc)


def _stringify_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    return dict(value)


def _target_matches(lease: CustodyLease, target: CustodyTargetKey) -> bool:
    lease_target = getattr(lease, "target_key", None)
    if lease_target is None:
        return False
    return lease_target.to_dict() == target.to_dict()


def _reread_run_authority_grant(context: ActionBoundaryContext) -> SourceCheck:
    grant_id = context.run_authority_grant_id.strip()
    if not grant_id:
        return SourceCheck(
            source="run_authority_grant",
            outcome=ValidationOutcome.MISSING,
            identity="grant_id",
            detail="missing current Run Authority grant ID",
        )
    grant = context.run_authority_grant
    if grant is None:
        return SourceCheck(
            source="run_authority_grant",
            outcome=ValidationOutcome.MISSING,
            identity="grant",
            detail=f"missing current Run Authority grant {grant_id!r}",
            observed_value={"grant_id": grant_id},
        )
    try:
        validate_scope_binding(
            grant=grant,
            fence=context.coordinator_fence or CoordinatorFence(
                grant.run_id,
                grant.run_revision,
                grant.coordinator_attempt_id,
                grant.fence_token,
            ),
            expected_grant_id=grant_id,
            subject_id=context.target.subject_id,
            fence_token=context.coordinator_fence_token,
            required_capability=context.required_capability or None,
        )
    except RevisionConflict as exc:
        identity = "grant_id" if grant.grant_id != grant_id else "fence_token"
        return SourceCheck(
            source="run_authority_grant",
            outcome=ValidationOutcome.STALE,
            identity=identity,
            detail=str(exc),
            observed_value={
                "expected_grant_id": grant_id,
                "observed_grant_id": grant.grant_id,
                "subject_id": context.target.subject_id,
                "fence_token": grant.fence_token,
            },
        )
    except IdentityConflict as exc:
        detail = str(exc)
        identity = "subject_id"
        outcome = ValidationOutcome.CONFLICT
        if "capability" in detail:
            identity = "capability"
        return SourceCheck(
            source="run_authority_grant",
            outcome=outcome,
            identity=identity,
            detail=detail,
            observed_value={
                "grant_id": grant.grant_id,
                "subject_ids": grant.subject_ids,
                "capabilities": grant.capabilities,
            },
        )
    return SourceCheck(
        source="run_authority_grant",
        outcome=ValidationOutcome.SATISFIED,
        identity="grant_id",
        detail=f"grant {grant.grant_id!r} currently authorizes subject {context.target.subject_id!r}",
        observed_value={
            "grant_id": grant.grant_id,
            "subject_ids": grant.subject_ids,
            "capabilities": grant.capabilities,
            "evidence_ids": grant.evidence_ids,
        },
    )


def _reread_run_authority_fence(context: ActionBoundaryContext) -> SourceCheck:
    grant_id = context.run_authority_grant_id.strip()
    if not grant_id:
        return SourceCheck(
            source="run_authority_fence",
            outcome=ValidationOutcome.MISSING,
            identity="grant_id",
            detail="cannot validate current fence without a current grant ID",
        )
    fence = context.coordinator_fence
    if fence is None:
        return SourceCheck(
            source="run_authority_fence",
            outcome=ValidationOutcome.MISSING,
            identity="fence",
            detail=f"missing current coordinator fence for grant {grant_id!r}",
            observed_value={"grant_id": grant_id},
        )
    if fence.token != context.coordinator_fence_token:
        return SourceCheck(
            source="run_authority_fence",
            outcome=ValidationOutcome.FENCED,
            identity="fence_token",
            detail=(
                f"stale coordinator fence token: expected {context.coordinator_fence_token!r}, "
                f"observed {fence.token!r}"
            ),
            observed_value={
                "grant_id": grant_id,
                "expected_fence_token": context.coordinator_fence_token,
                "observed_fence_token": fence.token,
                "coordinator_attempt_id": fence.coordinator_attempt_id,
            },
        )
    grant = context.run_authority_grant
    if grant is not None and grant.coordinator_attempt_id != fence.coordinator_attempt_id:
        return SourceCheck(
            source="run_authority_fence",
            outcome=ValidationOutcome.CONFLICT,
            identity="coordinator_attempt_id",
            detail=(
                "grant and fence identify different coordinator attempts: "
                f"{grant.coordinator_attempt_id!r} vs {fence.coordinator_attempt_id!r}"
            ),
            observed_value={
                "grant_id": grant.grant_id,
                "grant_coordinator_attempt_id": grant.coordinator_attempt_id,
                "fence_coordinator_attempt_id": fence.coordinator_attempt_id,
            },
        )
    return SourceCheck(
        source="run_authority_fence",
        outcome=ValidationOutcome.SATISFIED,
        identity="fence_token",
        detail=f"coordinator fence token {fence.token!r} is current",
        observed_value={
            "grant_id": grant_id,
            "fence_token": fence.token,
            "coordinator_attempt_id": fence.coordinator_attempt_id,
        },
    )


def _select_current_lease(
    lease_store: CustodyLeaseStore,
    context: ActionBoundaryContext,
) -> tuple[CustodyLease | None, list[CustodyLease]]:
    if context.expected_lease_id.strip():
        current = lease_store.current_lease(context.expected_lease_id.strip())
        candidates = [] if current is None else [current]
        return current, candidates
    candidates = [
        lease
        for lease in lease_store.find_by_target_key(
            context.target.subject_type,
            context.target.subject_id,
            context.target.action,
            context.target.target_kind,
            context.target.target_id,
            context.target.contract_id,
        )
        if _lease_is_active(lease)
    ]
    if not candidates:
        return None, []
    candidates.sort(key=lambda lease: (int(getattr(lease, "epoch", 0)), getattr(lease, "lease_id", "")), reverse=True)
    return candidates[0], candidates


def _reread_custody_lease(
    context: ActionBoundaryContext,
    lease_store: CustodyLeaseStore | None,
) -> SourceCheck:
    if lease_store is None:
        return SourceCheck(
            source="custody_lease",
            outcome=ValidationOutcome.MISSING,
            identity="lease_store",
            detail="missing current Custody lease store",
        )
    try:
        lease, candidates = _select_current_lease(lease_store, context)
    except Exception as exc:  # pragma: no cover - defensive around store adapters
        return SourceCheck(
            source="custody_lease",
            outcome=ValidationOutcome.ERROR,
            identity="lease_store",
            detail=f"lease reread error: {type(exc).__name__}: {exc}",
        )
    if lease is None:
        return SourceCheck(
            source="custody_lease",
            outcome=ValidationOutcome.MISSING,
            identity="lease_id" if context.expected_lease_id.strip() else "target",
            detail=(
                f"missing current Custody lease for lease_id {context.expected_lease_id!r}"
                if context.expected_lease_id.strip()
                else "missing current Custody lease for exact subject/action target"
            ),
            observed_value={"target": context.target.to_dict()},
        )
    if len(candidates) > 1 and not context.expected_lease_id.strip():
        return SourceCheck(
            source="custody_lease",
            outcome=ValidationOutcome.CONFLICT,
            identity="lease_id",
            detail="multiple active Custody leases exist for the exact subject/action target",
            observed_value={"lease_ids": [item.lease_id for item in candidates]},
        )
    if not _target_matches(lease, context.target):
        return SourceCheck(
            source="custody_lease",
            outcome=ValidationOutcome.CONFLICT,
            identity="target",
            detail="current Custody lease target does not match the exact subject/action target",
            observed_value={
                "lease_id": lease.lease_id,
                "expected_target": context.target.to_dict(),
                "observed_target": lease.target_key.to_dict() if lease.target_key is not None else {},
            },
        )
    if lease.is_expired or not _lease_is_active(lease):
        return SourceCheck(
            source="custody_lease",
            outcome=ValidationOutcome.EXPIRED,
            identity="lease_id",
            detail=f"lease {lease.lease_id!r} is expired or terminal",
            observed_value={
                "lease_id": lease.lease_id,
                "custody_epoch": lease.custody_epoch,
                "expires_at": lease.expires_at,
                "status": lease.status,
            },
        )
    if context.expected_custody_epoch > 0 and lease.custody_epoch != context.expected_custody_epoch:
        return SourceCheck(
            source="custody_lease",
            outcome=ValidationOutcome.STALE,
            identity="custody_epoch",
            detail=(
                f"stale custody epoch: expected {context.expected_custody_epoch!r}, "
                f"observed {lease.custody_epoch!r}"
            ),
            observed_value={
                "lease_id": lease.lease_id,
                "expected_custody_epoch": context.expected_custody_epoch,
                "observed_custody_epoch": lease.custody_epoch,
            },
        )
    if context.run_authority_grant_id and lease.run_authority_grant_id != context.run_authority_grant_id:
        return SourceCheck(
            source="custody_lease",
            outcome=ValidationOutcome.STALE,
            identity="grant_id",
            detail=(
                f"lease {lease.lease_id!r} is bound to stale Run Authority grant "
                f"{lease.run_authority_grant_id!r}"
            ),
            observed_value={
                "lease_id": lease.lease_id,
                "expected_grant_id": context.run_authority_grant_id,
                "observed_grant_id": lease.run_authority_grant_id,
            },
        )
    if str(lease.fence_token) != str(context.coordinator_fence_token):
        return SourceCheck(
            source="custody_lease",
            outcome=ValidationOutcome.FENCED,
            identity="fence_token",
            detail=(
                f"lease {lease.lease_id!r} is fenced by token {lease.fence_token!r}, "
                f"not {context.coordinator_fence_token!r}"
            ),
            observed_value={"lease_id": lease.lease_id, "observed_fence_token": lease.fence_token},
        )
    if context.wbc_attempt_reference and lease.wbc_attempt_reference != context.wbc_attempt_reference:
        return SourceCheck(
            source="custody_lease",
            outcome=ValidationOutcome.CONFLICT,
            identity="wbc_attempt_reference",
            detail=(
                f"lease {lease.lease_id!r} is bound to WBC attempt {lease.wbc_attempt_reference!r}, "
                f"not {context.wbc_attempt_reference!r}"
            ),
            observed_value={
                "lease_id": lease.lease_id,
                "observed_wbc_attempt_reference": lease.wbc_attempt_reference,
            },
        )
    if context.owner_host and context.owner_pid:
        if (lease.owner_host, lease.owner_pid) != (context.owner_host, context.owner_pid):
            return SourceCheck(
                source="custody_lease",
                outcome=ValidationOutcome.NOT_OWNER,
                identity="owner",
                detail=(
                    f"lease owner mismatch: expected {(context.owner_host, context.owner_pid)!r}, "
                    f"observed {(lease.owner_host, lease.owner_pid)!r}"
                ),
                observed_value={
                    "lease_id": lease.lease_id,
                    "owner_host": lease.owner_host,
                    "owner_pid": lease.owner_pid,
                    "owner_boot_id": lease.owner_boot_id,
                },
            )
    return SourceCheck(
        source="custody_lease",
        outcome=ValidationOutcome.SATISFIED,
        identity="lease_id",
        detail=f"lease {lease.lease_id!r} is current for the exact subject/action target",
        observed_value={
            "lease_id": lease.lease_id,
            "custody_epoch": lease.custody_epoch,
            "owner_host": lease.owner_host,
            "owner_pid": lease.owner_pid,
            "owner_boot_id": lease.owner_boot_id,
            "fence_token": lease.fence_token,
            "run_authority_grant_id": lease.run_authority_grant_id,
        },
    )


def _record_version(record: Any) -> str:
    payload = getattr(record, "payload", {}) or {}
    if not isinstance(payload, Mapping):
        return ""
    for key in ("schema_version", "evidence_version", "version"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _reread_wbc_attempt(
    context: ActionBoundaryContext,
    outbox: CustodyOutbox | None,
    target_digest: str,
) -> SourceCheck:
    if outbox is None:
        return SourceCheck(
            source="wbc_attempt",
            outcome=ValidationOutcome.MISSING,
            identity="outbox",
            detail="missing current WBC evidence outbox",
        )
    if not context.wbc_attempt_reference.strip():
        return SourceCheck(
            source="wbc_attempt",
            outcome=ValidationOutcome.MISSING,
            identity="wbc_attempt_reference",
            detail="missing current WBC attempt reference",
            observed_value={"target_digest": target_digest},
        )
    try:
        all_records = tuple(outbox.list_records())
    except Exception as exc:  # pragma: no cover - defensive around adapter stores
        return SourceCheck(
            source="wbc_attempt",
            outcome=ValidationOutcome.ERROR,
            identity="outbox",
            detail=f"WBC attempt reread error: {type(exc).__name__}: {exc}",
        )
    matching = [r for r in all_records if getattr(r, "wbc_attempt_reference", "") == context.wbc_attempt_reference]
    if not matching:
        return SourceCheck(
            source="wbc_attempt",
            outcome=ValidationOutcome.MISSING,
            identity="wbc_attempt_reference",
            detail=f"missing current WBC evidence for attempt {context.wbc_attempt_reference!r}",
            observed_value={
                "wbc_attempt_reference": context.wbc_attempt_reference,
                "outbox_record_count": len(all_records),
            },
        )
    grant_ids = {getattr(r, "run_authority_grant_id", "") for r in matching if getattr(r, "run_authority_grant_id", "")}
    if context.run_authority_grant_id and grant_ids and grant_ids != {context.run_authority_grant_id}:
        return SourceCheck(
            source="wbc_attempt",
            outcome=ValidationOutcome.CONFLICT,
            identity="grant_id",
            detail=f"WBC evidence is bound to different Run Authority grants: {sorted(grant_ids)!r}",
            observed_value={"grant_ids": sorted(grant_ids)},
        )
    fence_tokens = {
        int(getattr(r, "coordinator_fence_token"))
        for r in matching
        if getattr(r, "coordinator_fence_token", None) not in ("", None)
    }
    if fence_tokens and fence_tokens != {context.coordinator_fence_token}:
        return SourceCheck(
            source="wbc_attempt",
            outcome=ValidationOutcome.STALE,
            identity="fence_token",
            detail=(
                f"WBC evidence is bound to stale fence tokens {sorted(fence_tokens)!r}, "
                f"expected {context.coordinator_fence_token!r}"
            ),
            observed_value={"fence_tokens": sorted(fence_tokens)},
        )
    versions = {version for version in (_record_version(record) for record in matching) if version}
    required_version = context.required_wbc_evidence_version.strip()
    if required_version and not versions:
        return SourceCheck(
            source="wbc_attempt",
            outcome=ValidationOutcome.MISSING,
            identity="wbc_evidence_version",
            detail=f"required WBC evidence version {required_version!r} is missing",
            observed_value={"matching_record_count": len(matching)},
        )
    if len(versions) > 1:
        return SourceCheck(
            source="wbc_attempt",
            outcome=ValidationOutcome.CONFLICT,
            identity="wbc_evidence_version",
            detail=f"conflicting WBC evidence versions observed: {sorted(versions)!r}",
            observed_value={"versions": sorted(versions)},
        )
    if required_version and versions and next(iter(versions)) != required_version:
        observed_version = next(iter(versions))
        return SourceCheck(
            source="wbc_attempt",
            outcome=ValidationOutcome.STALE,
            identity="wbc_evidence_version",
            detail=(
                f"stale WBC evidence version: expected {required_version!r}, "
                f"observed {observed_version!r}"
            ),
            observed_value={
                "expected_wbc_evidence_version": required_version,
                "observed_wbc_evidence_version": observed_version,
            },
        )
    observed_target_digests = {
        payload.get("target_digest")
        for payload in (getattr(record, "payload", {}) or {} for record in matching)
        if isinstance(payload, Mapping) and isinstance(payload.get("target_digest"), str)
    }
    if observed_target_digests and observed_target_digests != {target_digest}:
        return SourceCheck(
            source="wbc_attempt",
            outcome=ValidationOutcome.CONFLICT,
            identity="target_digest",
            detail="WBC evidence references a different exact subject/action target",
            observed_value={"observed_target_digests": sorted(observed_target_digests)},
        )
    statuses = {
        str(getattr(getattr(record, "status", None), "value", getattr(record, "status", "")))
        for record in matching
    }
    statuses.discard("")
    if len(statuses) > 1:
        return SourceCheck(
            source="wbc_attempt",
            outcome=ValidationOutcome.CONFLICT,
            identity="status",
            detail=f"conflicting WBC evidence statuses observed: {sorted(statuses)!r}",
            observed_value={"statuses": sorted(statuses)},
        )
    observed_version = next(iter(versions)) if versions else ""
    return SourceCheck(
        source="wbc_attempt",
        outcome=ValidationOutcome.SATISFIED,
        identity="wbc_attempt_reference",
        detail=f"WBC evidence is current for attempt {context.wbc_attempt_reference!r}",
        observed_value={
            "wbc_attempt_reference": context.wbc_attempt_reference,
            "matching_record_count": len(matching),
            "status": next(iter(statuses)) if statuses else "",
            "wbc_evidence_version": observed_version,
        },
    )


def _compute_gate_result(checks: tuple[SourceCheck, ...], enforcement_enabled: bool) -> GateResult:
    if any(check.outcome == ValidationOutcome.ERROR for check in checks):
        return GateResult.ERROR
    if not enforcement_enabled:
        return GateResult.SHADOW_PASS
    for check in checks:
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
            if check.identity == "target":
                return GateResult.BLOCKED_TARGET_MISMATCH
            return GateResult.BLOCKED_STALE_EPOCH
        if check.source == "wbc_attempt":
            if check.outcome == ValidationOutcome.MISSING:
                return GateResult.BLOCKED_WBC_MISSING
            if check.identity == "wbc_evidence_version":
                return GateResult.BLOCKED_WBC_VERSION_MISMATCH
            return GateResult.BLOCKED_WBC_CONFLICT
    return GateResult.AUTHORIZED


def _build_diagnostics(
    checks: tuple[SourceCheck, ...],
    enforcement_enabled: bool,
    action_type: ActionBoundaryType,
) -> dict[str, Any]:
    denials = [check.to_dict() for check in checks if check.outcome != ValidationOutcome.SATISFIED]
    diagnostics: dict[str, Any] = {
        "m7_schema_version": ACTION_VALIDATOR_SCHEMA_VERSION,
        "shadow_enforcement": not enforcement_enabled,
        "enforcement_env_var": _ENV_ENFORCEMENT,
        "action_boundary": action_type,
        "checks_summary": {check.source: check.outcome.value for check in checks},
    }
    if denials:
        diagnostics["denials"] = denials
        diagnostics["sources_with_issues"] = [check["source"] for check in denials]
    return diagnostics


def validate_action_boundary(
    context: ActionBoundaryContext,
    *,
    lease_store: CustodyLeaseStore | None = None,
    outbox: CustodyOutbox | None = None,
    enforcement_enabled: bool | None = None,
) -> ActionBoundaryResult:
    if enforcement_enabled is None:
        enforcement_enabled = _production_enforcement_enabled()
    target_digest = context.target.target_digest
    checks = (
        _reread_run_authority_grant(context),
        _reread_run_authority_fence(context),
        _reread_custody_lease(context, lease_store),
        _reread_wbc_attempt(context, outbox, target_digest),
    )
    diagnostics = _build_diagnostics(checks, enforcement_enabled, context.action_type)
    return ActionBoundaryResult(
        gate_result=_compute_gate_result(checks, enforcement_enabled),
        action_type=context.action_type,
        target_digest=target_digest,
        checks=checks,
        enforcement_enabled=enforcement_enabled,
        diagnostics=diagnostics,
    )


def production_enforcement_enabled() -> bool:
    return _production_enforcement_enabled()


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
                        identity="target",
                        detail="invalid target: could not normalize to CustodyTargetKey",
                    ),
                ),
                enforcement_enabled=enforcement,
                diagnostics={"error": "invalid target"},
            )
    else:
        raise TypeError("target must be a CustodyTargetKey or a Mapping")

    owner_host = ""
    owner_pid = ""
    owner_boot_id = ""
    try:
        import socket

        owner_host = socket.gethostname()
    except Exception:
        pass
    try:
        owner_pid = str(os.getpid())
    except Exception:
        pass
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

    lease_store = None if lease_store_dir is None else open_lease_store(Path(lease_store_dir))
    outbox = None if outbox_dir is None else open_outbox(Path(outbox_dir))
    return validate_action_boundary(context, lease_store=lease_store, outbox=outbox)


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
