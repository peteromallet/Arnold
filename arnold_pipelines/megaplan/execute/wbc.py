from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import uuid
from typing import Any, Iterable, Mapping

from arnold.workflow.attempt_ledger_store import SqliteAttemptLedgerStore
from arnold.workflow.execution_attempt_ledger import (
    AdapterKind,
    AttemptEventType,
    AttemptIdentity,
    AttemptOutcome,
    AttemptProvenance,
    GrantRef,
    LedgerEvent,
    PersistenceStatus,
    RuntimeAdapter,
    VersionSet,
)
from arnold_pipelines.megaplan.authority.batch_scope import DISPATCH_IDENTITY_KEY
from arnold_pipelines.megaplan.authority.binding import DispatchIdentity
from arnold_pipelines.megaplan.custody.action_validator import ActionBoundaryContext
from arnold_pipelines.megaplan.custody.common_worker_dispatch import CommonWorkerDispatchSpec
from arnold_pipelines.megaplan.custody.controlled_writer_registry import (
    Cohort,
    ControlledWriter,
    register_writer,
)
from arnold_pipelines.megaplan.custody.contracts import CustodyTargetKey
from arnold_pipelines.megaplan.custody.wbc_runtime import (
    ExactSourceRecord,
    ImmutableAttemptArtifacts,
    PromotionMode,
    WbcRuntimeProducerFacade,
)
from arnold_pipelines.megaplan.types import PlanState

EXECUTE_WBC_LEDGER_FILENAME = ".execute_wbc_attempts.sqlite3"
EXECUTE_DISPATCH_WBC_KEY = "execute_dispatch_wbc"
EXECUTE_TRANSITION_WBC_KEY = "execute_transition_wbc"
EXECUTE_PARENT_CUSTODY_KEY = "execute_parent_custody"
EXECUTE_WBC_SCHEMA_VERSION = 1
EXECUTE_DISPATCH_WRITER_ID = "megaplan.execute.dispatch_wbc"
EXECUTE_DISPATCH_SURFACE = "megaplan.execute.dispatch_wbc"

_EXECUTE_CONTRACT_IDS = (
    "execute_batch_checkpoint",
    "execute_partial_failure",
    "execute_resume_anchor",
    "execute_aggregate_promotion",
)


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def register_execute_wbc_writer() -> None:
    try:
        register_writer(
            ControlledWriter(
                writer_id=EXECUTE_DISPATCH_WRITER_ID,
                surface_name=EXECUTE_DISPATCH_SURFACE,
                cohort=Cohort.ACTIVE,
                contract_ids=_EXECUTE_CONTRACT_IDS,
                source_file="arnold_pipelines/megaplan/execute/batch.py",
                function_name="_run_and_merge_batch",
                required_wbc_phases=("start", "terminal", "result"),
                action_kind="execute_dispatch",
            )
        )
    except ValueError:
        return


def execute_dispatch_source_version(
    identity: DispatchIdentity,
    *,
    batch_number: int,
) -> str:
    return (
        f"execute-batch:{batch_number}:{identity.plan_revision}:"
        f"{identity.fence_token}:{identity.dispatch_id}"
    )


def execute_dispatch_lookup_key(*, batch_number: int, stage: str) -> str:
    return f"execute-batch:{batch_number}:{stage}"


def _attempt_id(plan_dir: Path, identity: DispatchIdentity) -> str:
    return str(
        uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"{plan_dir.resolve()}::{identity.dispatch_id}::execute-dispatch",
        )
    )


def _target(identity: DispatchIdentity, *, batch_number: int) -> CustodyTargetKey:
    return CustodyTargetKey(
        "execute_batch",
        identity.dispatch_id,
        "dispatch",
        "batch",
        str(batch_number),
        "execute_batch_checkpoint",
    )


def _shadow_action_context(
    *,
    identity: DispatchIdentity,
    batch_number: int,
    attempt_id: str,
    action_type: str,
) -> ActionBoundaryContext:
    return ActionBoundaryContext(
        action_type=action_type,  # type: ignore[arg-type]
        target=_target(identity, batch_number=batch_number),
        run_authority_grant_id=identity.dispatch_id,
        coordinator_fence_token=identity.fence_token,
        wbc_attempt_reference=attempt_id,
        required_capability=(identity.capabilities[0] if identity.capabilities else ""),
        required_wbc_evidence_version=execute_dispatch_source_version(
            identity,
            batch_number=batch_number,
        ),
    )


def _identity(
    *,
    identity: DispatchIdentity,
    attempt_id: str,
) -> AttemptIdentity:
    return AttemptIdentity(
        workflow_id="megaplan.execute",
        run_id=identity.run_id,
        graph_revision=identity.plan_revision,
        step_id="execute",
        invocation_id=identity.coordinator_attempt_id,
        attempt_ordinal=identity.fence_token,
        attempt_id=attempt_id,
    )


def _event(
    *,
    identity: DispatchIdentity,
    attempt_id: str,
    batch_number: int,
    batch_task_ids: Iterable[str],
    batch_sense_check_ids: Iterable[str],
    sequence: int,
    event_type: AttemptEventType,
    idempotency_suffix: str,
    outcome: AttemptOutcome | None = None,
    payload: Mapping[str, Any] | None = None,
) -> LedgerEvent:
    body = {
        "batch_number": batch_number,
        "dispatch_id": identity.dispatch_id,
        "task_ids": list(batch_task_ids),
        "sense_check_ids": list(batch_sense_check_ids),
    }
    if payload:
        body.update(dict(payload))
    return LedgerEvent(
        idempotency_key=f"{identity.dispatch_id}:{idempotency_suffix}",
        event_type=event_type,
        identity=_identity(identity=identity, attempt_id=attempt_id),
        provenance=AttemptProvenance(
            actor_id="megaplan.execute",
            tool_id="megaplan.execute.dispatch_wbc",
        ),
        adapter=RuntimeAdapter(
            adapter_kind=AdapterKind.MEGAPLAN_PHASE,
            adapter_version="1",
        ),
        versions=VersionSet(
            code_version=execute_dispatch_source_version(
                identity,
                batch_number=batch_number,
            ),
            config_version="execute.config.v1",
            template_version="execute.dispatch.v1",
        ),
        grant_ref=GrantRef(grant_id=identity.dispatch_id),
        sequence=sequence,
        causal_predecessor_sequence=max(sequence - 1, 0),
        append_position=sequence,
        occurred_at=_utcnow(),
        observed_at=_utcnow(),
        persistence_status=PersistenceStatus.DURABLE,
        outcome=outcome,
        payload=body,
    )


def build_execute_batch_dispatch_spec(
    *,
    plan_dir: Path,
    state: PlanState,
    dispatch_identity: DispatchIdentity,
    batch_number: int,
    batch_task_ids: list[str],
    batch_sense_check_ids: list[str],
    start_action_context: ActionBoundaryContext | None = None,
    success_action_context: ActionBoundaryContext | None = None,
    failure_action_context: ActionBoundaryContext | None = None,
    enforcement_enabled: bool = False,
) -> CommonWorkerDispatchSpec:
    del state  # reserved for future exact-source/state-backed adapters
    register_execute_wbc_writer()
    attempt_id = _attempt_id(plan_dir, dispatch_identity)
    expected_source_version = execute_dispatch_source_version(
        dispatch_identity,
        batch_number=batch_number,
    )
    facade = WbcRuntimeProducerFacade(
        SqliteAttemptLedgerStore(plan_dir / EXECUTE_WBC_LEDGER_FILENAME),
        source_lookup=lambda key: ExactSourceRecord(
            lookup_key=key,
            version=expected_source_version,
            source_uri=f"plan://{plan_dir.name}/{key}",
            observed_at=_utcnow(),
            metadata={
                "dispatch_id": dispatch_identity.dispatch_id,
                "batch_number": batch_number,
            },
        ),
        promotion_mode=PromotionMode.ACTION_OFF,
        enforcement_enabled=enforcement_enabled,
    )
    artifacts = ImmutableAttemptArtifacts(
        attempt_id=attempt_id,
        metadata={
            "batch_number": batch_number,
            "dispatch_id": dispatch_identity.dispatch_id,
            "task_ids": list(batch_task_ids),
            "sense_check_ids": list(batch_sense_check_ids),
        },
    )
    return CommonWorkerDispatchSpec(
        facade=facade,
        attempt_id=attempt_id,
        start_event=_event(
            identity=dispatch_identity,
            attempt_id=attempt_id,
            batch_number=batch_number,
            batch_task_ids=batch_task_ids,
            batch_sense_check_ids=batch_sense_check_ids,
            sequence=1,
            event_type=AttemptEventType.STARTED,
            idempotency_suffix="started",
            payload={"status": "started"},
        ),
        success_event_factory=lambda _worker_result: _event(
            identity=dispatch_identity,
            attempt_id=attempt_id,
            batch_number=batch_number,
            batch_task_ids=batch_task_ids,
            batch_sense_check_ids=batch_sense_check_ids,
            sequence=2,
            event_type=AttemptEventType.COMPLETED,
            idempotency_suffix="completed",
            outcome=AttemptOutcome.SUCCEEDED,
            payload={"status": "completed"},
        ),
        failure_event_factory=lambda exc: _event(
            identity=dispatch_identity,
            attempt_id=attempt_id,
            batch_number=batch_number,
            batch_task_ids=batch_task_ids,
            batch_sense_check_ids=batch_sense_check_ids,
            sequence=2,
            event_type=AttemptEventType.FAILED,
            idempotency_suffix="failed",
            outcome=AttemptOutcome.INDETERMINATE,
            payload={
                "status": "failed",
                "error_type": type(exc).__name__,
                "error": str(exc),
            },
        ),
        start_action_context=(
            start_action_context
            or _shadow_action_context(
                identity=dispatch_identity,
                batch_number=batch_number,
                attempt_id=attempt_id,
                action_type="dispatch",
            )
        ),
        success_action_context=(
            success_action_context
            or _shadow_action_context(
                identity=dispatch_identity,
                batch_number=batch_number,
                attempt_id=attempt_id,
                action_type="completion",
            )
        ),
        failure_action_context=(
            failure_action_context
            or _shadow_action_context(
                identity=dispatch_identity,
                batch_number=batch_number,
                attempt_id=attempt_id,
                action_type="repair",
            )
        ),
        artifacts=artifacts,
        writer_id=EXECUTE_DISPATCH_WRITER_ID,
        surface_name=EXECUTE_DISPATCH_SURFACE,
        expected_source_version=expected_source_version,
        start_source_lookup_key=execute_dispatch_lookup_key(
            batch_number=batch_number,
            stage="start",
        ),
        success_source_lookup_key=execute_dispatch_lookup_key(
            batch_number=batch_number,
            stage="complete",
        ),
        failure_source_lookup_key=execute_dispatch_lookup_key(
            batch_number=batch_number,
            stage="failure",
        ),
    )


def dispatch_wbc_summary(
    *,
    auth_metadata: Mapping[str, Any] | None,
    dispatch_identity: DispatchIdentity,
    batch_number: int,
) -> dict[str, Any] | None:
    if not isinstance(auth_metadata, Mapping):
        return None
    raw = auth_metadata.get("wbc_dispatch")
    if not isinstance(raw, Mapping):
        return None
    expected_source_version = execute_dispatch_source_version(
        dispatch_identity,
        batch_number=batch_number,
    )
    return {
        "schema_version": EXECUTE_WBC_SCHEMA_VERSION,
        "attempt_id": raw.get("attempt_id"),
        "writer_id": raw.get("writer_id"),
        "surface_name": raw.get("surface_name"),
        "dispatch_id": dispatch_identity.dispatch_id,
        "plan_revision": dispatch_identity.plan_revision,
        "fence_token": dispatch_identity.fence_token,
        "prerequisite_digest": dispatch_identity.prerequisite_digest,
        "worker_id": dispatch_identity.worker_id,
        "expected_source_version": expected_source_version,
        "start_source_lookup_key": execute_dispatch_lookup_key(
            batch_number=batch_number,
            stage="start",
        ),
        "terminal_source_lookup_key": execute_dispatch_lookup_key(
            batch_number=batch_number,
            stage="complete",
        ),
        "verified_start_sequence": raw.get("start_event_sequence"),
        "verified_terminal_sequence": raw.get("terminal_event_sequence"),
        "verified_reread": bool(
            raw.get("start_event_sequence") and raw.get("terminal_event_sequence")
        ),
    }


def build_transition_wbc_summary(
    *,
    dispatch_summary: Mapping[str, Any],
    boundary_id: str,
    receipt_path: str,
    transition: str,
    result_value: str,
    batch_number: int,
    batches_total: int,
) -> dict[str, Any]:
    return {
        "schema_version": EXECUTE_WBC_SCHEMA_VERSION,
        "dispatch_attempt_id": dispatch_summary.get("attempt_id"),
        "dispatch_id": dispatch_summary.get("dispatch_id"),
        "plan_revision": dispatch_summary.get("plan_revision"),
        "fence_token": dispatch_summary.get("fence_token"),
        "boundary_id": boundary_id,
        "receipt_path": receipt_path,
        "transition": transition,
        "result": result_value,
        "batch_number": batch_number,
        "batches_total": batches_total,
        "receipt_reread_verified": True,
    }


def validate_dispatch_wbc_payload(
    payload: Mapping[str, Any],
    *,
    state: PlanState | None = None,
) -> str | None:
    del state
    raw_identity = payload.get(DISPATCH_IDENTITY_KEY)
    if not isinstance(raw_identity, Mapping):
        if raw_identity is None:
            return "missing_dispatch_identity"
        return "malformed_dispatch_identity"
    try:
        identity = DispatchIdentity.from_dict(raw_identity)
    except Exception:
        return "malformed_dispatch_identity"
    raw_summary = payload.get(EXECUTE_DISPATCH_WBC_KEY)
    if not isinstance(raw_summary, Mapping):
        return "missing_execute_dispatch_wbc"
    summary = dict(raw_summary)
    expected = {
        "dispatch_id": identity.dispatch_id,
        "plan_revision": identity.plan_revision,
        "fence_token": identity.fence_token,
        "prerequisite_digest": identity.prerequisite_digest,
        "worker_id": identity.worker_id,
    }
    for key, expected_value in expected.items():
        if summary.get(key) != expected_value:
            return f"{key}_mismatch"
    if not isinstance(summary.get("expected_source_version"), str) or not str(
        summary.get("expected_source_version")
    ).strip():
        return "missing_exact_source_version"
    if not isinstance(summary.get("verified_start_sequence"), int):
        return "missing_durable_start_sequence"
    if not isinstance(summary.get("verified_terminal_sequence"), int):
        return "missing_dispatch_terminal_sequence"
    if not summary.get("verified_reread"):
        return "dispatch_reread_not_verified"
    return None


def validate_transition_wbc_payload(payload: Mapping[str, Any]) -> str | None:
    raw_summary = payload.get(EXECUTE_TRANSITION_WBC_KEY)
    if not isinstance(raw_summary, Mapping):
        return "missing_execute_transition_wbc"
    raw_dispatch = payload.get(EXECUTE_DISPATCH_WBC_KEY)
    if not isinstance(raw_dispatch, Mapping):
        return "missing_execute_dispatch_wbc"
    if raw_summary.get("dispatch_attempt_id") != raw_dispatch.get("attempt_id"):
        return "dispatch_attempt_id_mismatch"
    if raw_summary.get("dispatch_id") != raw_dispatch.get("dispatch_id"):
        return "dispatch_id_mismatch"
    if raw_summary.get("plan_revision") != raw_dispatch.get("plan_revision"):
        return "plan_revision_mismatch"
    if raw_summary.get("fence_token") != raw_dispatch.get("fence_token"):
        return "fence_token_mismatch"
    boundary_id = raw_summary.get("boundary_id")
    if not isinstance(boundary_id, str) or not boundary_id.strip():
        return "missing_boundary_id"
    if not raw_summary.get("receipt_reread_verified"):
        return "receipt_reread_not_verified"
    receipt_path = raw_summary.get("receipt_path")
    if not isinstance(receipt_path, str) or not receipt_path.strip():
        return "missing_receipt_path"
    return None


def _stable_unique_strings(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        normalized = str(value).strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return ordered


def _normalized_string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return _stable_unique_strings((value,))
    if not isinstance(value, (list, tuple, set)):
        return []
    return _stable_unique_strings(
        item for item in value if isinstance(item, str) and item.strip()
    )


def _repair_custody_is_active(payload: Mapping[str, Any]) -> bool:
    active_requests = {
        value
        for value in _normalized_string_list(payload.get("active_request_ids"))
    }
    active_claims = {
        value
        for value in _normalized_string_list(payload.get("active_claim_request_ids"))
    }
    if active_requests & active_claims:
        return True
    attempts = payload.get("attempts")
    if not isinstance(attempts, list):
        return False
    return any(
        isinstance(attempt, Mapping)
        and attempt.get("terminal") is False
        and isinstance(attempt.get("attempt_id"), str)
        and str(attempt.get("attempt_id")).strip()
        and (
            str(attempt.get("request_id") or "").strip() in active_requests
            or str(attempt.get("source") or "").strip() == "repair_queue_dispatch_attempt"
        )
        for attempt in attempts
    )


def _normalized_parent_custody_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    accepted_subject_ids: list[str] = []
    active_repair_subject_ids: list[str] = []
    accepted_repair_occurrence_ids: list[str] = []
    active_repair_occurrence_ids: list[str] = []

    raw_parent = payload.get(EXECUTE_PARENT_CUSTODY_KEY)
    if isinstance(raw_parent, Mapping):
        accepted_subject_ids.extend(
            _normalized_string_list(raw_parent.get("accepted_subject_ids"))
        )
        active_repair_subject_ids.extend(
            _normalized_string_list(raw_parent.get("active_repair_subject_ids"))
        )
        accepted_repair_occurrence_ids.extend(
            _normalized_string_list(raw_parent.get("accepted_repair_occurrence_ids"))
        )
        active_repair_occurrence_ids.extend(
            _normalized_string_list(raw_parent.get("active_repair_occurrence_ids"))
        )

    if (
        validate_dispatch_wbc_payload(payload) is None
        and validate_transition_wbc_payload(payload) is None
    ):
        dispatch = payload.get(EXECUTE_DISPATCH_WBC_KEY)
        if isinstance(dispatch, Mapping):
            attempt_id = dispatch.get("attempt_id")
            if isinstance(attempt_id, str) and attempt_id.strip():
                accepted_subject_ids.append(attempt_id.strip())

    repair_custody = payload.get("repair_custody")
    if isinstance(repair_custody, Mapping) and _repair_custody_is_active(repair_custody):
        current_target = (
            repair_custody.get("current_target")
            if isinstance(repair_custody.get("current_target"), Mapping)
            else {}
        )
        current_refs = (
            current_target.get("current_refs")
            if isinstance(current_target, Mapping)
            and isinstance(current_target.get("current_refs"), Mapping)
            else {}
        )
        active_repair_subject_ids.extend(
            _normalized_string_list(
                [
                    current_refs.get("current_plan_name"),
                    current_refs.get("chain_current_plan_name"),
                    repair_custody.get("subject_id"),
                    repair_custody.get("subject_attempt_id"),
                ]
            )
        )
        blocker_id = repair_custody.get("blocker_id")
        if isinstance(blocker_id, str) and blocker_id.strip():
            active_repair_occurrence_ids.append(blocker_id.strip())

    accepted_subject_ids = _stable_unique_strings(accepted_subject_ids)
    active_repair_subject_ids = _stable_unique_strings(active_repair_subject_ids)
    accepted_repair_occurrence_ids = _stable_unique_strings(
        accepted_repair_occurrence_ids
    )
    active_repair_occurrence_ids = _stable_unique_strings(
        active_repair_occurrence_ids
    )
    conflicting_subject_ids = sorted(
        set(accepted_subject_ids).intersection(active_repair_subject_ids)
    )
    conflicting_repair_occurrence_ids = sorted(
        set(accepted_repair_occurrence_ids).intersection(
            active_repair_occurrence_ids
        )
    )
    return {
        "schema_version": EXECUTE_WBC_SCHEMA_VERSION,
        "accepted_subject_ids": accepted_subject_ids,
        "active_repair_subject_ids": active_repair_subject_ids,
        "accepted_repair_occurrence_ids": accepted_repair_occurrence_ids,
        "active_repair_occurrence_ids": active_repair_occurrence_ids,
        "conflicting_subject_ids": conflicting_subject_ids,
        "conflicting_repair_occurrence_ids": conflicting_repair_occurrence_ids,
        "conflict_free": not (
            conflicting_subject_ids or conflicting_repair_occurrence_ids
        ),
    }


def parent_custody_conflict_messages(summary: Mapping[str, Any]) -> list[str]:
    messages: list[str] = []
    conflicting_subject_ids = _normalized_string_list(
        summary.get("conflicting_subject_ids")
    )
    conflicting_repair_occurrence_ids = _normalized_string_list(
        summary.get("conflicting_repair_occurrence_ids")
    )
    if conflicting_subject_ids:
        messages.append(
            "execute parent custody conflict: accepted worker and repair custody "
            f"overlap on subject ids {conflicting_subject_ids}"
        )
    if conflicting_repair_occurrence_ids:
        messages.append(
            "execute parent custody conflict: accepted worker and repair custody "
            "overlap on repair occurrences "
            f"{conflicting_repair_occurrence_ids}"
        )
    return messages


def validate_parent_custody_payload(payload: Mapping[str, Any]) -> str | None:
    summary = _normalized_parent_custody_payload(payload)
    messages = parent_custody_conflict_messages(summary)
    if not messages:
        return None
    return "; ".join(messages)


def summarize_execute_parent_custody(
    batch_payloads: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    accepted_subject_ids: list[str] = []
    active_repair_subject_ids: list[str] = []
    accepted_repair_occurrence_ids: list[str] = []
    active_repair_occurrence_ids: list[str] = []
    for payload in batch_payloads:
        summary = _normalized_parent_custody_payload(payload)
        accepted_subject_ids.extend(summary["accepted_subject_ids"])
        active_repair_subject_ids.extend(summary["active_repair_subject_ids"])
        accepted_repair_occurrence_ids.extend(
            summary["accepted_repair_occurrence_ids"]
        )
        active_repair_occurrence_ids.extend(
            summary["active_repair_occurrence_ids"]
        )

    aggregate = _normalized_parent_custody_payload(
        {
            EXECUTE_PARENT_CUSTODY_KEY: {
                "accepted_subject_ids": accepted_subject_ids,
                "active_repair_subject_ids": active_repair_subject_ids,
                "accepted_repair_occurrence_ids": accepted_repair_occurrence_ids,
                "active_repair_occurrence_ids": active_repair_occurrence_ids,
            }
        }
    )
    aggregate["messages"] = parent_custody_conflict_messages(aggregate)
    return aggregate


def summarize_execute_wbc_batch_payloads(
    batch_payloads: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    dispatch_attempt_ids: list[str] = []
    boundary_ids: list[str] = []
    source_versions: list[str] = []
    fence_tokens: list[int] = []
    all_dispatch_verified = True
    all_transition_verified = True
    for payload in batch_payloads:
        dispatch = payload.get(EXECUTE_DISPATCH_WBC_KEY)
        if isinstance(dispatch, Mapping):
            attempt_id = dispatch.get("attempt_id")
            if isinstance(attempt_id, str) and attempt_id:
                dispatch_attempt_ids.append(attempt_id)
            source_version = dispatch.get("expected_source_version")
            if isinstance(source_version, str) and source_version:
                source_versions.append(source_version)
            fence = dispatch.get("fence_token")
            if isinstance(fence, int):
                fence_tokens.append(fence)
            all_dispatch_verified = all_dispatch_verified and bool(
                dispatch.get("verified_reread")
            )
        else:
            all_dispatch_verified = False
        transition = payload.get(EXECUTE_TRANSITION_WBC_KEY)
        if isinstance(transition, Mapping):
            boundary_id = transition.get("boundary_id")
            if isinstance(boundary_id, str) and boundary_id:
                boundary_ids.append(boundary_id)
            all_transition_verified = all_transition_verified and bool(
                transition.get("receipt_reread_verified")
            )
        else:
            all_transition_verified = False
    return {
        "schema_version": EXECUTE_WBC_SCHEMA_VERSION,
        "dispatch_attempt_ids": sorted(dict.fromkeys(dispatch_attempt_ids)),
        "boundary_ids": sorted(dict.fromkeys(boundary_ids)),
        "source_versions": sorted(dict.fromkeys(source_versions)),
        "fence_tokens": sorted(dict.fromkeys(fence_tokens)),
        "all_dispatch_verified": all_dispatch_verified,
        "all_transition_verified": all_transition_verified,
    }


__all__ = [
    "EXECUTE_DISPATCH_SURFACE",
    "EXECUTE_DISPATCH_WBC_KEY",
    "EXECUTE_PARENT_CUSTODY_KEY",
    "EXECUTE_DISPATCH_WRITER_ID",
    "EXECUTE_TRANSITION_WBC_KEY",
    "EXECUTE_WBC_LEDGER_FILENAME",
    "EXECUTE_WBC_SCHEMA_VERSION",
    "build_execute_batch_dispatch_spec",
    "build_transition_wbc_summary",
    "parent_custody_conflict_messages",
    "dispatch_wbc_summary",
    "execute_dispatch_lookup_key",
    "execute_dispatch_source_version",
    "register_execute_wbc_writer",
    "summarize_execute_parent_custody",
    "summarize_execute_wbc_batch_payloads",
    "validate_parent_custody_payload",
    "validate_dispatch_wbc_payload",
    "validate_transition_wbc_payload",
]
