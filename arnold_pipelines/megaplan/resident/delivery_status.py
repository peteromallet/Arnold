"""Authoritative resident work, delivery, and aggregation status projections.

Aggregation role describes how a result participates in synthesis.  It is not
delivery policy.  This module keeps that distinction explicit while projecting
legacy manifests that predate the v2 delivery-status contract.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Any, Mapping, Sequence


DELIVERY_STATUS_SCHEMA = "arnold-resident-delivery-status-v2"
OUTCOME_CONTRACTS = frozenset(
    {"analytical_fragment", "independently_meaningful_execution", "synthesis_result"}
)
_ANALYTICAL_TASK_KINDS = frozenset(
    {"lookup", "extraction", "research", "root_cause", "architecture", "review"}
)
_EXECUTION_TASK_KINDS = frozenset({"coding", "debugging", "migration", "autonomous"})
_INDEPENDENT_EXECUTION_RE = re.compile(
    r"\b(repair(?:s|ed|ing)?|deploy(?:s|ed|ing)?|integrat(?:e|es|ed|ing|ion)|"
    r"activat(?:e|es|ed|ing|ion)|prov(?:e|es|ed|ing)|implement(?:s|ed|ing|ation)?|"
    r"fix(?:es|ed|ing)?|migrat(?:e|es|ed|ing|ion))\b",
    re.IGNORECASE,
)


def infer_outcome_contract(
    *,
    task: str,
    description: str | None,
    task_kind: str,
    aggregation_role: str,
    explicit: str | None = None,
) -> tuple[str, str]:
    """Resolve the result contract and record whether it was explicit or inferred."""

    text = f"{description or ''}\n{task}"
    semantic_execution = bool(
        task_kind in _EXECUTION_TASK_KINDS or _INDEPENDENT_EXECUTION_RE.search(text)
    )
    if explicit is not None:
        value = str(explicit).strip()
        if value not in OUTCOME_CONTRACTS:
            raise ValueError(
                "outcome_contract must be analytical_fragment, "
                "independently_meaningful_execution, or synthesis_result"
            )
        if aggregation_role == "internal_contributor" and value == "synthesis_result":
            raise ValueError(
                "internal_contributor cannot declare the synthesis_result contract"
            )
        if value == "analytical_fragment" and semantic_execution:
            raise ValueError(
                "an independently meaningful execution task cannot be classified as an "
                "analytical_fragment; use independently_meaningful_execution and record "
                "a nondelivery override when suppression is intentional"
            )
        return value, "explicit_launch_contract"
    if aggregation_role == "synthesis_delivery_owner":
        return "synthesis_result", "aggregation_owner_default"
    if semantic_execution:
        return "independently_meaningful_execution", "task_contract_inference"
    if task_kind in _ANALYTICAL_TASK_KINDS:
        return "analytical_fragment", "task_contract_inference"
    return "analytical_fragment", "compatibility_default"


def delivery_policy_for_launch(
    *,
    aggregation_role: str,
    outcome_contract: str,
    suppression_override_reason: str | None,
) -> str:
    """Resolve delivery independently from aggregation role."""

    reason = str(suppression_override_reason or "").strip()
    if len(reason) > 500:
        raise ValueError("delivery_suppression_override_reason exceeds 500 characters")
    if aggregation_role != "internal_contributor":
        if reason:
            raise ValueError(
                "delivery_suppression_override_reason applies only to internal_contributor"
            )
        return "deliver_synthesis_result"
    if outcome_contract == "independently_meaningful_execution":
        return "suppress_with_recorded_override" if reason else "deliver_independently"
    if reason:
        raise ValueError(
            "delivery_suppression_override_reason is unnecessary for an analytical fragment"
        )
    return "suppress_analytical_fragment"


def manifest_execution_contract(manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Read v2 execution intent or deterministically project a legacy manifest."""

    stored = manifest.get("execution_contract")
    if isinstance(stored, Mapping) and stored.get("outcome_contract") in OUTCOME_CONTRACTS:
        return dict(stored)
    aggregation = manifest.get("aggregation")
    role = (
        str(aggregation.get("role") or "synthesis_delivery_owner")
        if isinstance(aggregation, Mapping)
        else "synthesis_delivery_owner"
    )
    outcome, authority = infer_outcome_contract(
        task=str(manifest.get("task_excerpt") or ""),
        description=str(manifest.get("description") or "") or None,
        task_kind=str(manifest.get("task_kind") or "routine"),
        aggregation_role=role,
    )
    delivery = manifest.get("completion_delivery")
    stored_status = str(delivery.get("status") or "") if isinstance(delivery, Mapping) else ""
    if role == "internal_contributor" and stored_status == "suppressed":
        policy = (
            "legacy_suppressed_independent_result"
            if outcome == "independently_meaningful_execution"
            else "suppress_analytical_fragment"
        )
    else:
        policy = (
            "deliver_independently"
            if role == "internal_contributor"
            else "deliver_synthesis_result"
        )
    return {
        "schema_version": DELIVERY_STATUS_SCHEMA,
        "outcome_contract": outcome,
        "outcome_contract_authority": f"legacy_{authority}",
        "delivery_policy": policy,
        "migration_projection": True,
    }


def dependency_run_ids(manifest: Mapping[str, Any]) -> list[str]:
    queue = manifest.get("queue")
    if not isinstance(queue, Mapping):
        return []
    plural = queue.get("predecessor_run_ids")
    if isinstance(plural, Sequence) and not isinstance(plural, (str, bytes)):
        return [str(item) for item in plural if str(item).strip()]
    singular = str(queue.get("predecessor_run_id") or "").strip()
    return [singular] if singular else []


def work_status_for(observed_status: str) -> str:
    return {
        "completed": "worker_completed",
        "failed": "worker_failed",
        "interrupted": "worker_interrupted",
        "cancelled": "worker_cancelled",
        "superseded": "worker_superseded",
        "queued": "queued",
        "launching": "launching",
        "running": "running",
    }.get(observed_status, "unknown")


def _parse_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


def _result_is_useful(manifest: Mapping[str, Any], manifest_path: Path) -> bool:
    if str(manifest.get("status") or "") != "completed":
        return False
    raw = Path(str(manifest.get("result_path") or "result.md"))
    path = raw if raw.is_absolute() else manifest_path.parent / raw
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            return bool(handle.read(8_192).strip())
    except OSError:
        return False


def build_delivery_projection(
    *,
    manifest: Mapping[str, Any],
    manifest_path: Path,
    observed_status: str,
    manifest_index: Mapping[str, tuple[Path, Mapping[str, Any]]],
) -> dict[str, Any]:
    """Project current status, refreshing dependencies from durable manifests."""

    execution = manifest_execution_contract(manifest)
    aggregation = manifest.get("aggregation")
    role = (
        str(aggregation.get("role") or "synthesis_delivery_owner")
        if isinstance(aggregation, Mapping)
        else "synthesis_delivery_owner"
    )
    delivery = manifest.get("completion_delivery")
    delivery_status = (
        str(delivery.get("status") or "pending")
        if isinstance(delivery, Mapping)
        else "not_applicable"
    )
    predecessor_states: list[dict[str, Any]] = []
    for run_id in dependency_run_ids(manifest):
        current = manifest_index.get(run_id)
        if current is None:
            predecessor_states.append({"run_id": run_id, "status": "missing"})
            continue
        current_path, current_manifest = current
        predecessor_states.append(
            {
                "run_id": run_id,
                "status": str(current_manifest.get("status") or "unknown"),
                "work_status": work_status_for(str(current_manifest.get("status") or "unknown")),
                "delivery_status": str(
                    dict(current_manifest.get("completion_delivery") or {}).get("status")
                    or "not_applicable"
                ),
                "outcome_contract": manifest_execution_contract(current_manifest).get(
                    "outcome_contract"
                ),
                "result_useful": _result_is_useful(current_manifest, current_path),
            }
        )
    queue = manifest.get("queue")
    embedded_states = (
        list(queue.get("predecessor_states") or [])
        if isinstance(queue, Mapping)
        else []
    )
    stale_snapshot = bool(embedded_states and embedded_states != predecessor_states)
    failed_dependency = any(
        item["status"] in {"failed", "interrupted", "cancelled", "abandoned", "missing", "unknown"}
        for item in predecessor_states
    )
    waiting_dependency = any(
        item["status"] not in {"completed", "failed", "interrupted", "cancelled", "abandoned"}
        for item in predecessor_states
    )
    worker_completed = observed_status == "completed"
    request_delivered = bool(
        delivery_status == "delivered" and role == "synthesis_delivery_owner"
    )
    if request_delivered:
        request_status = "request_delivered"
    elif failed_dependency:
        request_status = "aggregation_blocked"
    elif predecessor_states and waiting_dependency:
        request_status = "awaiting_predecessors"
    elif worker_completed and delivery_status == "delivered":
        request_status = "independent_result_delivered_request_open"
    elif worker_completed and delivery_status in {"pending", "retry_pending", "sending"}:
        request_status = "awaiting_delivery"
    elif worker_completed and role == "internal_contributor":
        request_status = "awaiting_aggregation"
    elif observed_status in {"failed", "interrupted", "cancelled"}:
        request_status = "request_blocked"
    else:
        request_status = "in_progress"
    return {
        "schema_version": DELIVERY_STATUS_SCHEMA,
        "work": {
            "status": work_status_for(observed_status),
            "legacy_status": observed_status,
            "worker_completed": worker_completed,
        },
        "delivery": {
            "status": delivery_status,
            "policy": execution.get("delivery_policy"),
            "independently_deliverable": execution.get("outcome_contract")
            == "independently_meaningful_execution",
        },
        "request": {
            "status": request_status,
            "request_delivered": request_delivered,
            "aggregation_role": role,
            "aggregation_key": aggregation.get("key") if isinstance(aggregation, Mapping) else None,
        },
        "dependencies": {
            "policy": str(
                dict(queue or {}).get("policy")
                or dict(queue or {}).get("join_policy")
                or "all_success"
            ),
            "source": "current_durable_manifests",
            "predecessor_states": predecessor_states,
            "stale_embedded_snapshot_detected": stale_snapshot,
        },
        "execution_contract": execution,
    }


def build_delivery_attention(
    *,
    manifest_index: Mapping[str, tuple[Path, Mapping[str, Any]]],
    projections: Mapping[str, Mapping[str, Any]],
    now: datetime,
    abnormal_wait_seconds: int = 3600,
) -> list[dict[str, Any]]:
    """Return deterministic actionable fan-in and hidden-delivery warnings."""

    attention: list[dict[str, Any]] = []

    def add(code: str, run_id: str, reason: str, action: str, **extra: Any) -> None:
        attention.append(
            {"code": code, "run_id": run_id, "reason": reason, "action": action, **extra}
        )

    for run_id in sorted(manifest_index):
        path, manifest = manifest_index[run_id]
        projection = projections[run_id]
        execution = projection["execution_contract"]
        work = projection["work"]
        delivery = projection["delivery"]
        if (
            work["worker_completed"]
            and execution.get("outcome_contract") == "independently_meaningful_execution"
            and delivery["status"] in {"suppressed", "superseded"}
            and _result_is_useful(manifest, path)
        ):
            add(
                "completed_independent_result_suppressed",
                run_id,
                "An independently useful execution result completed but has no "
                "truthful terminal delivery.",
                "Deliver the bounded result now, or honor the recorded nondelivery "
                "override through explicit owner follow-through.",
                delivery_status=delivery["status"],
                suppression_override_reason=execution.get(
                    "delivery_suppression_override_reason"
                ),
            )

        dependencies = projection["dependencies"]
        states = list(dependencies.get("predecessor_states") or [])
        if not states:
            continue
        successful_hidden = [
            item for item in states
            if item.get("status") == "completed"
            and item.get("result_useful")
            and item.get("outcome_contract") == "independently_meaningful_execution"
            and item.get("delivery_status") in {"suppressed", "superseded"}
        ]
        incomplete = [
            item
            for item in states
            if item.get("status")
            not in {"completed", "failed", "interrupted", "cancelled", "abandoned"}
        ]
        failed = [
            item
            for item in states
            if item.get("status")
            in {"failed", "interrupted", "cancelled", "abandoned", "missing", "unknown"}
        ]
        if successful_hidden and incomplete:
            add(
                "completed_result_hidden_by_predecessor",
                run_id,
                "All-success fan-in is hiding a completed independently useful "
                "result behind another predecessor.",
                "Issue the completed result's truthful terminal update without "
                "closing the aggregate request.",
                predecessor_run_ids=[item["run_id"] for item in successful_hidden],
                blocking_run_ids=[item["run_id"] for item in incomplete],
            )
        if successful_hidden and failed:
            add(
                "failed_predecessor_hides_success",
                run_id,
                "A failed predecessor prevents successful independently useful "
                "results from becoming visible.",
                "Deliver successful bounded outcomes and separately report the "
                "failed aggregate dependency.",
                predecessor_run_ids=[item["run_id"] for item in successful_hidden],
                failed_run_ids=[item["run_id"] for item in failed],
            )
        independent = [
            item
            for item in states
            if item.get("outcome_contract") == "independently_meaningful_execution"
        ]
        predecessor_subjects = []
        for item in independent:
            predecessor = manifest_index.get(str(item["run_id"]))
            if predecessor:
                predecessor_manifest = predecessor[1]
                predecessor_subjects.append(
                    str(
                        dict(predecessor_manifest.get("execution_contract") or {}).get(
                            "outcome_key"
                        )
                        or predecessor_manifest.get("source_record_id")
                        or predecessor_manifest.get("request_id")
                        or predecessor_manifest.get("task_sha256")
                        or item["run_id"]
                    )
                )
        if len(independent) >= 2 and len(set(predecessor_subjects)) >= 2:
            add(
                "unrelated_execution_predecessors_all_success",
                run_id,
                "Distinct independently meaningful execution outcomes are coupled "
                "by an all-success join.",
                "Keep synthesis ownership, but decouple terminal delivery for each "
                "independently useful outcome.",
                predecessor_run_ids=[item["run_id"] for item in independent],
            )
        created = _parse_timestamp(manifest.get("created_at") or manifest.get("started_at"))
        age = (now - created).total_seconds() if created is not None else 0
        role = projection["request"].get("aggregation_role")
        if role == "synthesis_delivery_owner" and age >= abnormal_wait_seconds and (
            projection["request"]["status"] in {"awaiting_predecessors", "awaiting_delivery"}
        ):
            add(
                "delivery_owner_abnormally_waiting",
                run_id,
                "The synthesis/delivery owner has waited beyond the bounded operational threshold.",
                "Inspect current predecessor and delivery evidence; deliver "
                "completed bounded outcomes now.",
                waiting_seconds=int(age),
            )
    unique: dict[tuple[str, str], dict[str, Any]] = {}
    for item in attention:
        unique[(item["code"], item["run_id"])] = item
    return [unique[key] for key in sorted(unique)]
