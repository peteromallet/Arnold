"""Helpers for durable override authority receipts.

This module keeps override-authority validation declarative and bounded to
receipt/authority evidence. It does not derive routes or next steps.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
from typing import Any, Mapping

from arnold.workflow.boundary_evidence import AuthorityRecord, BoundaryContract
from arnold_pipelines.megaplan.workflows.override_matrix import get_entry


@dataclass(frozen=True)
class OverrideAuthorityError(ValueError):
    message: str

    def __str__(self) -> str:
        return self.message


@dataclass(frozen=True)
class OverrideAuthorityIssue:
    code: str
    message: str
    severity: str
    details: Mapping[str, Any]


def _transition_contracts_by_key() -> dict[str, BoundaryContract]:
    from arnold_pipelines.megaplan.workflows.boundary_contracts import (
        OVERRIDE_AUTHORITY_CONTRACTS,
    )

    contracts: dict[str, BoundaryContract] = {}
    for contract in OVERRIDE_AUTHORITY_CONTRACTS:
        transition = contract.details.get("authority_transition")
        if isinstance(transition, str) and transition:
            contracts[transition] = contract
    return contracts


def override_authority_contract_for_transition(transition: str) -> BoundaryContract:
    try:
        return _transition_contracts_by_key()[transition]
    except KeyError as exc:
        raise OverrideAuthorityError(
            f"Unknown override authority transition: {transition}"
        ) from exc


def activated_override_authority_transitions(
    state: Mapping[str, Any] | None,
) -> tuple[str, ...]:
    if not isinstance(state, Mapping):
        return ()
    meta = state.get("meta")
    if not isinstance(meta, Mapping):
        return ()
    overrides = meta.get("overrides")
    if not isinstance(overrides, list):
        return ()
    active: list[str] = []
    for entry in overrides:
        if not isinstance(entry, Mapping):
            continue
        action = entry.get("action")
        if isinstance(action, str) and action in _transition_contracts_by_key():
            active.append(action)
    return tuple(dict.fromkeys(active))


def current_freshness_token(
    state: Mapping[str, Any] | None,
    *,
    transition: str | None = None,
) -> str | None:
    if not isinstance(state, Mapping):
        return None
    meta = state.get("meta")
    if isinstance(meta, Mapping):
        invocation_id = meta.get("current_invocation_id")
        if isinstance(invocation_id, str) and invocation_id:
            return invocation_id
        if transition:
            overrides = meta.get("overrides")
            if isinstance(overrides, list):
                for entry in reversed(overrides):
                    if not isinstance(entry, Mapping):
                        continue
                    if entry.get("action") != transition:
                        continue
                    timestamp = entry.get("timestamp")
                    if isinstance(timestamp, str) and timestamp:
                        return timestamp
    return None


def _normalize_refs(raw_refs: object) -> tuple[str, ...]:
    if isinstance(raw_refs, (list, tuple)):
        refs = [ref for ref in raw_refs if isinstance(ref, str) and ref]
        return tuple(refs)
    return ()


def _required_evidence_refs(contract: BoundaryContract) -> tuple[str, ...]:
    return _normalize_refs(contract.details.get("required_evidence_refs"))


def _optional_evidence_refs(contract: BoundaryContract) -> tuple[str, ...]:
    return _normalize_refs(contract.details.get("optional_evidence_refs"))


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_override_authority_record(
    transition: str,
    *,
    plan_dir: Path,
    actor: str,
    role: str,
    decision: str | None = None,
    freshness_token: str | None = None,
    expected_freshness_token: str | None = None,
    evidence_refs: tuple[str, ...] | None = None,
    scope: str | None = None,
    waiver_reason: str | None = None,
    details: Mapping[str, Any] | None = None,
) -> AuthorityRecord:
    contract = override_authority_contract_for_transition(transition)
    required_refs = _required_evidence_refs(contract)
    selected_refs = evidence_refs or required_refs + tuple(
        ref for ref in _optional_evidence_refs(contract) if (plan_dir / ref).is_file()
    )
    missing_required = [ref for ref in required_refs if ref not in selected_refs]
    if missing_required:
        raise OverrideAuthorityError(
            f"{transition} missing required evidence refs: {missing_required}"
        )
    if not actor.strip():
        raise OverrideAuthorityError("override authority actor must be non-empty")
    if not role.strip():
        raise OverrideAuthorityError("override authority role must be non-empty")
    if freshness_token is None or not freshness_token.strip():
        raise OverrideAuthorityError("override authority freshness token must be non-empty")
    if (
        expected_freshness_token is not None
        and freshness_token != expected_freshness_token
    ):
        raise OverrideAuthorityError(
            f"{transition} stale override authority input: "
            f"expected freshness token {expected_freshness_token!r}, "
            f"got {freshness_token!r}"
        )
    evidence_hashes: dict[str, str] = {}
    for ref in selected_refs:
        path = plan_dir / ref
        if not path.is_file():
            raise OverrideAuthorityError(
                f"{transition} evidence ref does not exist on disk: {ref}"
            )
        evidence_hashes[ref] = _sha256_file(path)
    record_details: dict[str, Any] = {
        "authority_transition": transition,
        "contract_ref": contract.boundary_id,
        "required_evidence_refs": required_refs,
        "optional_evidence_refs": _optional_evidence_refs(contract),
        "evidence_hashes": evidence_hashes,
        "freshness_token": freshness_token,
        "freshness_token_ref": contract.details.get("freshness_token_ref"),
        "actor_role_ref": contract.details.get("actor_role_ref"),
    }
    if details:
        record_details.update(details)
    record_scope = scope or str(contract.details.get("authority_scope") or contract.boundary_id)
    return AuthorityRecord(
        actor=actor,
        role=role,
        decision=decision or transition,
        scope=record_scope,
        evidence_refs=selected_refs,
        waiver_reason=waiver_reason,
        details=record_details,
    )


def override_authority_transition_is_active(
    contract: BoundaryContract,
    *,
    state: Mapping[str, Any] | None,
    receipt_present: bool,
) -> bool:
    transition = contract.details.get("authority_transition")
    if not isinstance(transition, str) or not transition:
        return False
    active_transitions = set(activated_override_authority_transitions(state))
    if transition in active_transitions:
        return True
    if transition == "suspension-waiver":
        current_state = state.get("current_state") if isinstance(state, Mapping) else None
        return receipt_present and current_state == "awaiting_human_verify"
    if transition == "human-gate":
        current_state = state.get("current_state") if isinstance(state, Mapping) else None
        return receipt_present and current_state in {"awaiting_human", "awaiting_human_verify"}
    return False


def validate_override_authority_record(
    *,
    plan_dir: Path,
    state: Mapping[str, Any] | None,
    contract: BoundaryContract,
    record: Mapping[str, Any],
) -> tuple[OverrideAuthorityIssue, ...]:
    transition = contract.details.get("authority_transition")
    if not isinstance(transition, str) or not transition:
        return ()

    issues: list[OverrideAuthorityIssue] = []
    actor = record.get("actor")
    role = record.get("role")
    decision = record.get("decision")
    scope = record.get("scope")
    if not isinstance(actor, str) or not actor:
        issues.append(
            OverrideAuthorityIssue(
                code="actor-missing",
                severity="missing",
                message=f"{contract.boundary_id} authority record is missing actor data",
                details={},
            )
        )
    if not isinstance(role, str) or not role:
        issues.append(
            OverrideAuthorityIssue(
                code="role-missing",
                severity="missing",
                message=f"{contract.boundary_id} authority record is missing role data",
                details={},
            )
        )
    if not isinstance(decision, str) or not decision:
        issues.append(
            OverrideAuthorityIssue(
                code="decision-missing",
                severity="missing",
                message=f"{contract.boundary_id} authority record is missing a decision",
                details={},
            )
        )
    elif decision != transition:
        issues.append(
            OverrideAuthorityIssue(
                code="decision-out-of-scope",
                severity="stale",
                message=(
                    f"{contract.boundary_id} authority decision {decision!r} falls "
                    f"outside declared transition scope {transition!r}"
                ),
                details={
                    "expected_decision": transition,
                    "actual_decision": decision,
                },
            )
        )
    expected_scope = contract.details.get("authority_scope")
    if isinstance(expected_scope, str) and expected_scope:
        if not isinstance(scope, str) or scope != expected_scope:
            issues.append(
                OverrideAuthorityIssue(
                    code="scope-mismatch",
                    severity="stale",
                    message=(
                        f"{contract.boundary_id} authority scope {scope!r} does not match "
                        f"expected {expected_scope!r}"
                    ),
                    details={
                        "expected_scope": expected_scope,
                        "actual_scope": scope,
                    },
                )
            )

    evidence_refs = _normalize_refs(record.get("evidence_refs"))
    required_refs = _required_evidence_refs(contract)
    allowed_refs = required_refs + tuple(
        ref for ref in _optional_evidence_refs(contract) if ref not in required_refs
    )
    missing_refs = [ref for ref in required_refs if ref not in evidence_refs]
    if missing_refs:
        issues.append(
            OverrideAuthorityIssue(
                code="required-evidence-refs-missing",
                severity="missing",
                message=(
                    f"{contract.boundary_id} authority record is missing required "
                    f"evidence refs: {missing_refs}"
                ),
                details={"missing_refs": missing_refs},
            )
        )
    undeclared_refs = [ref for ref in evidence_refs if ref not in allowed_refs]
    if undeclared_refs:
        issues.append(
            OverrideAuthorityIssue(
                code="undeclared-evidence-refs",
                severity="stale",
                message=(
                    f"{contract.boundary_id} authority record references "
                    f"undeclared evidence refs: {undeclared_refs}"
                ),
                details={
                    "allowed_refs": allowed_refs,
                    "undeclared_refs": undeclared_refs,
                },
            )
        )

    details = record.get("details")
    details_map = details if isinstance(details, Mapping) else {}
    override_entry = get_entry(transition)
    detail_transition = details_map.get("authority_transition")
    if isinstance(detail_transition, str) and detail_transition != transition:
        issues.append(
            OverrideAuthorityIssue(
                code="detail-transition-mismatch",
                severity="stale",
                message=(
                    f"{contract.boundary_id} authority details transition "
                    f"{detail_transition!r} does not match declared transition "
                    f"{transition!r}"
                ),
                details={
                    "expected_transition": transition,
                    "actual_transition": detail_transition,
                },
            )
        )
    detail_contract_ref = details_map.get("contract_ref")
    if isinstance(detail_contract_ref, str) and detail_contract_ref != contract.boundary_id:
        issues.append(
            OverrideAuthorityIssue(
                code="detail-contract-ref-mismatch",
                severity="stale",
                message=(
                    f"{contract.boundary_id} authority details contract_ref "
                    f"{detail_contract_ref!r} does not match boundary "
                    f"{contract.boundary_id!r}"
                ),
                details={
                    "expected_contract_ref": contract.boundary_id,
                    "actual_contract_ref": detail_contract_ref,
                },
                )
            )
    expected_target_ref = override_entry.declared_target_ref or override_entry.target_ref
    actual_target_ref = details_map.get("declared_target_ref", details_map.get("target_ref"))
    if isinstance(actual_target_ref, str):
        if expected_target_ref is None or actual_target_ref != expected_target_ref:
            issues.append(
                OverrideAuthorityIssue(
                    code="declared-target-ref-mismatch",
                    severity="stale",
                    message=(
                        f"{contract.boundary_id} authority details declared_target_ref "
                        f"{actual_target_ref!r} does not match declared native target "
                        f"{expected_target_ref!r}"
                    ),
                    details={
                        "expected_declared_target_ref": expected_target_ref,
                        "actual_declared_target_ref": actual_target_ref,
                    },
                )
            )
    actual_route_signal = details_map.get("route_signal")
    if isinstance(actual_route_signal, str):
        if override_entry.route_signal is None or actual_route_signal != override_entry.route_signal:
            issues.append(
                OverrideAuthorityIssue(
                    code="route-signal-mismatch",
                    severity="stale",
                    message=(
                        f"{contract.boundary_id} authority details route_signal "
                        f"{actual_route_signal!r} does not match declared route signal "
                        f"{override_entry.route_signal!r}"
                    ),
                    details={
                        "expected_route_signal": override_entry.route_signal,
                        "actual_route_signal": actual_route_signal,
                    },
                )
            )
    actual_policy_route_ref = details_map.get("policy_route_ref")
    if isinstance(actual_policy_route_ref, str):
        if (
            override_entry.policy_route_ref is None
            or actual_policy_route_ref != override_entry.policy_route_ref
        ):
            issues.append(
                OverrideAuthorityIssue(
                    code="policy-route-ref-mismatch",
                    severity="stale",
                    message=(
                        f"{contract.boundary_id} authority details policy_route_ref "
                        f"{actual_policy_route_ref!r} does not match declared native policy "
                        f"{override_entry.policy_route_ref!r}"
                    ),
                    details={
                        "expected_policy_route_ref": override_entry.policy_route_ref,
                        "actual_policy_route_ref": actual_policy_route_ref,
                    },
                )
            )
    raw_hashes = details_map.get("evidence_hashes")
    if not isinstance(raw_hashes, Mapping):
        issues.append(
            OverrideAuthorityIssue(
                code="evidence-hashes-missing",
                severity="missing",
                message=f"{contract.boundary_id} authority record is missing evidence hashes",
                details={},
            )
        )
    else:
        for ref in evidence_refs:
            path = plan_dir / ref
            if not path.is_file():
                issues.append(
                    OverrideAuthorityIssue(
                        code="evidence-ref-missing-on-disk",
                        severity="missing",
                        message=(
                            f"{contract.boundary_id} evidence ref {ref!r} is not present on disk"
                        ),
                        details={"missing_ref": ref},
                    )
                )
                continue
            expected_hash = _sha256_file(path)
            actual_hash = raw_hashes.get(ref)
            if not isinstance(actual_hash, str) or not actual_hash:
                issues.append(
                    OverrideAuthorityIssue(
                        code="evidence-hash-entry-missing",
                        severity="missing",
                        message=(
                            f"{contract.boundary_id} authority record lacks a hash for {ref!r}"
                        ),
                        details={"evidence_ref": ref},
                    )
                )
                continue
            if actual_hash != expected_hash:
                issues.append(
                    OverrideAuthorityIssue(
                        code="evidence-hash-mismatch",
                        severity="stale",
                        message=(
                            f"{contract.boundary_id} authority hash for {ref!r} does not "
                            "match the current durable evidence"
                        ),
                        details={
                            "evidence_ref": ref,
                            "expected_hash": expected_hash,
                            "actual_hash": actual_hash,
                        },
                    )
                )

    expected_token = current_freshness_token(state, transition=transition)
    actual_token = details_map.get("freshness_token")
    if expected_token:
        if not isinstance(actual_token, str) or not actual_token:
            issues.append(
                OverrideAuthorityIssue(
                    code="freshness-token-missing",
                    severity="missing",
                    message=(
                        f"{contract.boundary_id} authority record is missing its freshness token"
                    ),
                    details={"expected_token": expected_token},
                )
            )
        elif actual_token != expected_token:
            issues.append(
                OverrideAuthorityIssue(
                    code="freshness-token-stale",
                    severity="stale",
                    message=(
                        f"{contract.boundary_id} freshness token {actual_token!r} does not "
                        f"match current token {expected_token!r}"
                    ),
                    details={
                        "expected_token": expected_token,
                        "actual_token": actual_token,
                    },
                )
            )

    return tuple(issues)


__all__ = [
    "OverrideAuthorityError",
    "OverrideAuthorityIssue",
    "activated_override_authority_transitions",
    "build_override_authority_record",
    "current_freshness_token",
    "override_authority_contract_for_transition",
    "override_authority_transition_is_active",
    "validate_override_authority_record",
]
