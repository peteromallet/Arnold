"""Read-only inventory adapter for Warrant source projections."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping
import json

from arnold.pipelines.megaplan.schemas import (
    WarrantAccount,
    WarrantAuthority,
    WarrantRationaleAnchor,
    WarrantSourceCompleteness,
    WarrantSourceProjection,
)


REQUIRED_WARRANT_SOURCE_FIELDS: tuple[str, ...] = (
    "authority_envelope",
    "verified_work_account",
    "rationale_anchor",
    "behavioral_or_manifest_hash",
    "verified_result_ref",
)
OPTIONAL_WARRANT_SOURCE_FIELDS: tuple[str, ...] = (
    "provider_cost_ref",
    "runtime_topology_hash",
    "receipt_refs",
    "ledger_refs",
)


def build_warrant_source_projection(
    *,
    authority_envelope: Mapping[str, Any] | WarrantAuthority | None = None,
    verified_work_account: Mapping[str, Any] | WarrantAccount | None = None,
    rationale_anchor: Mapping[str, Any] | WarrantRationaleAnchor | None = None,
    behavioral_or_manifest_hash: str | None = None,
    verified_result_ref: Mapping[str, Any] | None = None,
    unsupported: list[str] | tuple[str, ...] = (),
    source_refs: Mapping[str, Any] | None = None,
    projection_id: str = "warrant-source-projection",
) -> WarrantSourceProjection:
    """Build a projection from already-collected source facts.

    This helper is intentionally read-only: absent facts become missing or
    unsupported inventory entries instead of being inferred or written back.
    """
    unsupported_set = set(unsupported)
    present: list[str] = []
    missing: list[str] = []

    def _classify(name: str, value: object) -> None:
        if name in unsupported_set:
            return
        if value is None:
            missing.append(name)
        else:
            present.append(name)

    _classify("authority_envelope", authority_envelope)
    _classify("verified_work_account", verified_work_account)
    _classify("rationale_anchor", rationale_anchor)
    _classify("behavioral_or_manifest_hash", behavioral_or_manifest_hash)
    _classify("verified_result_ref", verified_result_ref)

    missing.extend(name for name in OPTIONAL_WARRANT_SOURCE_FIELDS if name not in unsupported_set)
    signable = not (set(REQUIRED_WARRANT_SOURCE_FIELDS) & (set(missing) | unsupported_set))

    authority = (
        authority_envelope
        if isinstance(authority_envelope, WarrantAuthority)
        else WarrantAuthority(**authority_envelope)
        if authority_envelope is not None and "authority_envelope" not in unsupported_set
        else None
    )
    account = (
        verified_work_account
        if isinstance(verified_work_account, WarrantAccount)
        else WarrantAccount(**verified_work_account)
        if verified_work_account is not None and "verified_work_account" not in unsupported_set
        else None
    )
    anchor = (
        rationale_anchor
        if isinstance(rationale_anchor, WarrantRationaleAnchor)
        else WarrantRationaleAnchor(**rationale_anchor)
        if rationale_anchor is not None and "rationale_anchor" not in unsupported_set
        else None
    )

    return WarrantSourceProjection(
        projection_id=projection_id,
        completeness=WarrantSourceCompleteness(
            present=sorted(set(present)),
            missing=sorted(set(missing)),
            unsupported=sorted(unsupported_set),
            required_fields=list(REQUIRED_WARRANT_SOURCE_FIELDS),
            signable=signable,
        ),
        authority=authority,
        account=account,
        rationale_anchor=anchor,
        behavioral_manifest_hash=behavioral_or_manifest_hash,
        verified_result_ref=dict(verified_result_ref) if verified_result_ref is not None else None,
        source_refs=dict(source_refs or {}),
    )


def _read_json_if_present(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else None


def inventory_warrant_sources(plan_dir: str | Path) -> WarrantSourceProjection:
    """Inventory current plan-directory sources without altering receipts."""
    root = Path(plan_dir)
    finalize_data = _read_json_if_present(root / "finalize.json")
    review_data = _read_json_if_present(root / "review.json")
    state_data = _read_json_if_present(root / "state.json")  # cache-tolerant: warrant source inventory snapshots plan state as evidence context.
    phase_result = _read_json_if_present(root / "phase_result.json")

    receipt_refs = sorted(path.name for path in root.glob("step_receipt_*.json"))
    source_refs: dict[str, Any] = {"plan_dir": str(root)}
    if receipt_refs:
        source_refs["receipt_refs"] = receipt_refs
    if review_data is not None:
        source_refs["review_ref"] = "review.json"
    if finalize_data is not None:
        source_refs["finalize_ref"] = "finalize.json"
    if phase_result is not None:
        source_refs["phase_result_ref"] = "phase_result.json"

    verified_result_ref: dict[str, Any] | None = None
    if phase_result is not None:
        exit_kind = phase_result.get("exit_kind")
        if isinstance(exit_kind, str):
            verified_result_ref = {"kind": "phase_result", "path": "phase_result.json", "exit_kind": exit_kind}
    if verified_result_ref is None and finalize_data is not None:
        verified_result_ref = {"kind": "finalize", "path": "finalize.json"}

    behavioral_hash = None
    if isinstance(state_data, dict):
        manifest = state_data.get("behavioral_manifest") or state_data.get("capsule_definition")
        if isinstance(manifest, dict):
            value = manifest.get("static_behavioral_hash") or manifest.get("identity_hash")
            if isinstance(value, str):
                behavioral_hash = value

    authority_envelope = None
    if isinstance(state_data, dict):
        policy = state_data.get("authority_envelope")
        if isinstance(policy, dict):
            authority_envelope = {
                "authority_id": str(policy.get("authority_id", "plan-authority")),
                "policy_envelope": policy,
                "grantor": policy.get("grantor") if isinstance(policy.get("grantor"), str) else None,
                "autonomy_level": policy.get("autonomy_level") if isinstance(policy.get("autonomy_level"), str) else None,
            }

    verified_work_account = None
    if verified_result_ref is not None and review_data is not None:
        task_verdicts = review_data.get("task_verdicts")
        if isinstance(task_verdicts, list) and task_verdicts:
            verified_work_account = {
                "account_id": "review-verified-work",
                "verified_work_units": task_verdicts,
                "verified_result_ref": verified_result_ref,
            }

    rationale_anchor = None
    if review_data is not None:
        rationale = review_data.get("summary") or review_data.get("review_verdict")
        if isinstance(rationale, str) and rationale.strip() and behavioral_hash is not None:
            rationale_anchor = {
                "anchor_id": "review-rationale",
                "manifest_hash": behavioral_hash,
                "rationale_ref": {"path": "review.json", "field": "summary" if "summary" in review_data else "review_verdict"},
            }

    unsupported = ["provider_cost_ref", "ledger_refs"]
    if behavioral_hash is None and receipt_refs:
        unsupported.append("behavioral_or_manifest_hash")

    projection = build_warrant_source_projection(
        authority_envelope=authority_envelope,
        verified_work_account=verified_work_account,
        rationale_anchor=rationale_anchor,
        behavioral_or_manifest_hash=behavioral_hash,
        verified_result_ref=verified_result_ref,
        unsupported=unsupported,
        source_refs=source_refs,
        projection_id=f"warrant-source-{root.name or 'plan'}",
    )
    present = set(projection.completeness.present)
    missing = set(projection.completeness.missing)
    unsupported_set = set(projection.completeness.unsupported)
    if receipt_refs:
        present.add("receipt_refs")
    else:
        missing.add("receipt_refs")
    if "runtime_topology_hash" not in unsupported_set:
        missing.add("runtime_topology_hash")
    projection.completeness.present = sorted(present)
    projection.completeness.missing = sorted(missing - present - unsupported_set)
    return projection


__all__ = [
    "OPTIONAL_WARRANT_SOURCE_FIELDS",
    "REQUIRED_WARRANT_SOURCE_FIELDS",
    "build_warrant_source_projection",
    "inventory_warrant_sources",
]
