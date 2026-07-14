"""Canonical milestone-source admission and deferred reconciliation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from arnold_pipelines.megaplan._core import now_utc
from arnold_pipelines.megaplan.planning.source_binding import canonical_source_identity
from arnold_pipelines.megaplan.types import CliError


CHAIN_SOURCE_SCHEMA = "arnold.megaplan.chain_source_admission.v1"
CHAIN_SOURCE_ERROR = "canonical_milestone_source_changed"


def _milestone_index_and_idea(spec: Any, label: str) -> tuple[int, str]:
    for index, milestone in enumerate(spec.milestones):
        if milestone.label == label:
            return index, str(milestone.idea)
    raise CliError("invalid_args", f"Unknown chain milestone: {label}")


def _append_event(state: Any, event: Mapping[str, Any]) -> None:
    metadata = dict(getattr(state, "metadata", {}) or {})
    events = metadata.setdefault("canonical_source_reconciliations", [])
    if not isinstance(events, list):
        events = []
        metadata["canonical_source_reconciliations"] = events
    events.append(dict(event))
    del events[:-100]
    state.metadata = metadata


def require_milestone_source_update(
    *,
    spec_path: Path,
    state: Any,
    spec: Any,
    milestone_label: str,
    authoritative_source: Path,
    reason: str,
    promotion_receipt: Path | None = None,
    require_promotion_receipt: bool = False,
) -> dict[str, Any]:
    index, installed_idea = _milestone_index_and_idea(spec, milestone_label)
    active_index = int(getattr(state, "current_milestone_index", -1))
    if index < active_index or (index == active_index and getattr(state, "current_plan_name", None)):
        raise CliError(
            "materialized_milestone_source_update",
            f"Milestone {milestone_label} is already materialized; use plan override replan.",
        )
    project_root = spec_path.resolve().parents[3]
    expected = canonical_source_identity(
        authoritative_source,
        project_dir=authoritative_source.resolve().parent,
    )
    if not expected.get("exists") or expected.get("errors"):
        raise CliError(
            "canonical_source_unavailable",
            f"Authoritative source is unavailable: {expected.get('errors')}",
        )
    installed_path = Path(installed_idea)
    if not installed_path.is_absolute():
        installed_path = project_root / installed_path
    observed = canonical_source_identity(installed_path, project_dir=project_root)
    receipt_report: dict[str, Any] | None = None
    if require_promotion_receipt and promotion_receipt is None:
        raise CliError(
            "invalid_runtime_promotion_receipt",
            "A valid content-addressed runtime promotion receipt is required.",
        )
    if promotion_receipt is not None:
        from arnold_pipelines.megaplan.chain.promotion_receipt import (
            verify_promotion_receipt,
        )

        receipt_report = verify_promotion_receipt(
            promotion_receipt,
            expected_milestone=milestone_label,
            expected_semantic_sha256=str(expected["semantic_sha256"]),
        )
    receipt_ready = not require_promotion_receipt or bool(receipt_report and receipt_report["valid"])
    source_ready = observed.get("semantic_sha256") == expected.get("semantic_sha256")
    requirement = {
        "schema": CHAIN_SOURCE_SCHEMA,
        "milestone": milestone_label,
        "milestone_index": index,
        "required_at": now_utc(),
        "reason": reason,
        "installed_path": str(installed_path.resolve(strict=False)),
        "expected": expected,
        "observed_at_registration": observed,
        "status": "ready_to_reconcile" if source_ready and receipt_ready else "pending_source_update",
        "admission_boundary": "after_base_refresh_before_plan_init",
        "admission_decision": "admit_after_reconcile" if source_ready and receipt_ready else "block",
        "block_code": "" if source_ready and receipt_ready else CHAIN_SOURCE_ERROR,
        "promotion_receipt_required": require_promotion_receipt,
        "promotion_receipt": receipt_report,
    }
    metadata = dict(getattr(state, "metadata", {}) or {})
    requirements = metadata.setdefault("required_canonical_source_updates", {})
    if not isinstance(requirements, dict):
        requirements = {}
        metadata["required_canonical_source_updates"] = requirements
    requirements[milestone_label] = requirement
    state.metadata = metadata
    _append_event(
        state,
        {
            "schema": CHAIN_SOURCE_SCHEMA,
            "checked_at": requirement["required_at"],
            "milestone": milestone_label,
            "operation": "register_required_source_update",
            "outcome": requirement["status"],
            "old_identity": observed,
            "new_identity": expected,
            "promotion_receipt": receipt_report,
            "reason": reason,
        },
    )
    return requirement


def _bundle_sha(identity: Mapping[str, Any]) -> str:
    core = {
        "chain_spec_sha256": identity.get("chain_spec_sha256"),
        "milestone_sequence": identity.get("milestone_sequence"),
        "assets": identity.get("assets"),
        "intended_initiative_revision": identity.get("intended_initiative_revision"),
        "initiative_path": identity.get("initiative_path"),
    }
    return hashlib.sha256(
        json.dumps(core, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def admit_milestone_source(
    *,
    root: Path,
    spec_path: Path,
    spec: Any,
    state: Any,
    milestone: Any,
    milestone_index: int,
) -> dict[str, Any]:
    """Reconcile an unmaterialized source or block before plan initialization."""

    installed_path = Path(str(milestone.idea))
    if not installed_path.is_absolute():
        installed_path = root / installed_path
    observed = canonical_source_identity(installed_path, project_dir=root)
    metadata = dict(getattr(state, "metadata", {}) or {})
    requirements = metadata.get("required_canonical_source_updates")
    requirement = requirements.get(milestone.label) if isinstance(requirements, dict) else None
    binding = metadata.get("execution_binding")
    launched = binding.get("launched_identity") if isinstance(binding, dict) else None
    old_asset: Mapping[str, Any] | None = None
    if isinstance(launched, Mapping):
        assets = launched.get("assets")
        if isinstance(assets, list):
            old_asset = next(
                (
                    item
                    for item in assets
                    if isinstance(item, Mapping)
                    and item.get("kind") == f"milestone_brief:{milestone_index}"
                ),
                None,
            )
    expected_sha = ""
    expected_identity: Mapping[str, Any] | None = None
    if isinstance(requirement, Mapping):
        expected_identity = requirement.get("expected") if isinstance(requirement.get("expected"), Mapping) else None
        expected_sha = str((expected_identity or {}).get("semantic_sha256") or "")
    if not expected_sha and isinstance(old_asset, Mapping):
        expected_sha = str(old_asset.get("semantic_sha256") or "")
        if not expected_sha and old_asset.get("resolved_path"):
            old_path = Path(str(old_asset["resolved_path"]))
            if old_path.is_file():
                expected_sha = canonical_source_identity(old_path, project_dir=root).get("semantic_sha256", "")
    current_sha = str(observed.get("semantic_sha256") or "")
    checked_at = now_utc()
    receipt_report: dict[str, Any] | None = None
    receipt_error = ""
    if isinstance(requirement, Mapping) and requirement.get("promotion_receipt_required"):
        receipt = requirement.get("promotion_receipt")
        receipt_path = str(receipt.get("path") or "") if isinstance(receipt, Mapping) else ""
        try:
            from arnold_pipelines.megaplan.chain.promotion_receipt import (
                verify_promotion_receipt,
            )

            receipt_report = verify_promotion_receipt(
                Path(receipt_path),
                expected_milestone=milestone.label,
                expected_semantic_sha256=expected_sha,
            )
        except CliError as exc:
            receipt_error = str(exc)
    if (
        not observed.get("exists")
        or observed.get("errors")
        or (expected_sha and current_sha != expected_sha)
        or receipt_error
    ):
        event = {
            "schema": CHAIN_SOURCE_SCHEMA,
            "checked_at": checked_at,
            "milestone": milestone.label,
            "milestone_index": milestone_index,
            "operation": "milestone_admission",
            "outcome": "blocked",
            "old_identity": dict(old_asset or {}),
            "required_identity": dict(expected_identity or {}),
            "current_identity": observed,
            "promotion_receipt": receipt_report,
            "reason": receipt_error or "current canonical source does not satisfy the bound/required identity",
        }
        _append_event(state, event)
        from arnold_pipelines.megaplan.chain.spec import save_chain_state

        save_chain_state(spec_path, state)
        raise CliError(
            CHAIN_SOURCE_ERROR,
            f"Milestone {milestone.label} admission refused before materialization: "
            f"required={expected_sha or 'bound file identity'} current={current_sha or 'missing'}"
            f" receipt={'invalid' if receipt_error else 'valid_or_not_required'}.",
            extra={"canonical_source_admission": event},
        )

    outcome = "unchanged"
    if isinstance(requirement, dict) or (
        isinstance(old_asset, Mapping) and old_asset.get("sha256") != observed.get("file_sha256")
    ):
        outcome = "reconciled"
        # Adoption is safe here because no plan exists for this milestone and
        # an explicit semantic identity (when required) matched exactly.
        if isinstance(launched, dict):
            from arnold_pipelines.megaplan.chain.execution_binding import active_execution_identity

            active = active_execution_identity(spec_path)
            launched.update(active)
            launched["bundle_sha256"] = _bundle_sha(launched)
        if isinstance(requirement, dict):
            requirement["status"] = "reconciled"
            requirement["admission_decision"] = "admitted"
            requirement["block_code"] = ""
            requirement["reconciled_at"] = checked_at
            requirement["reconciled_identity"] = observed
            if receipt_report is not None:
                requirement["promotion_receipt"] = receipt_report
    event = {
        "schema": CHAIN_SOURCE_SCHEMA,
        "checked_at": checked_at,
        "milestone": milestone.label,
        "milestone_index": milestone_index,
        "operation": "milestone_admission",
        "outcome": outcome,
        "old_identity": dict(old_asset or {}),
        "required_identity": dict(expected_identity or {}),
        "current_identity": observed,
        "promotion_receipt": receipt_report,
        "reason": "source identity verified before plan initialization",
    }
    _append_event(state, event)
    from arnold_pipelines.megaplan.chain.spec import save_chain_state

    save_chain_state(spec_path, state)
    return event
