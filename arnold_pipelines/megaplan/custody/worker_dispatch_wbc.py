"""Auto-built WBC dispatch specs for provider-backed worker families."""

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
from arnold_pipelines.megaplan.types import PlanState

from .action_validator import ActionBoundaryContext
from .common_worker_dispatch import CommonWorkerDispatchSpec
from .controlled_writer_registry import Cohort, ControlledWriter, register_writer
from .contracts import CustodyTargetKey
from .phase_wbc import phase_wbc_state
from .wbc_runtime import ExactSourceRecord, ImmutableAttemptArtifacts, PromotionMode, WbcRuntimeProducerFacade

WORKER_DISPATCH_WBC_LEDGER_FILENAME = ".worker_dispatch_wbc_attempts.sqlite3"


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class WorkerDispatchWriterSpec:
    route_kind: str
    writer_id: str
    surface_name: str
    contract_ids: tuple[str, ...]
    source_file: str
    function_name: str


_WRITER_SPECS: tuple[WorkerDispatchWriterSpec, ...] = (
    WorkerDispatchWriterSpec(
        route_kind="direct",
        writer_id="megaplan.worker_dispatch.direct",
        surface_name="megaplan.worker_dispatch.direct",
        contract_ids=(
            "provider_dispatch",
            "fallback_chain",
            "hermes_dispatch",
            "shannon_dispatch",
            "shannon_stream_dispatch",
            "shannon_session_dispatch",
        ),
        source_file="arnold_pipelines/megaplan/handlers/shared.py",
        function_name="_run_worker",
    ),
    WorkerDispatchWriterSpec(
        route_kind="subprocess",
        writer_id="megaplan.worker_dispatch.subprocess",
        surface_name="megaplan.worker_dispatch.subprocess",
        contract_ids=(
            "worker_subprocess_dispatch",
            "fallback_chain",
            "hermes_dispatch",
            "shannon_dispatch",
            "shannon_stream_dispatch",
            "shannon_session_dispatch",
        ),
        source_file="arnold_pipelines/megaplan/_core/worker_fanout.py",
        function_name="_dispatch_worker_unit_attempt",
    ),
)
_WRITER_SPEC_BY_ROUTE = {spec.route_kind: spec for spec in _WRITER_SPECS}


def register_worker_dispatch_wbc_writers() -> None:
    for spec in _WRITER_SPECS:
        try:
            register_writer(
                ControlledWriter(
                    writer_id=spec.writer_id,
                    surface_name=spec.surface_name,
                    cohort=Cohort.ACTIVE,
                    contract_ids=spec.contract_ids,
                    source_file=spec.source_file,
                    function_name=spec.function_name,
                    required_wbc_phases=("start", "terminal"),
                    action_kind="dispatch",
                )
            )
        except ValueError:
            continue


def build_worker_dispatch_spec(
    *,
    plan_dir: Path,
    state: PlanState,
    step: str,
    agent: str,
    selected_spec: str,
    route_kind: str,
    attempt_index: int = 0,
    configured_specs: Iterable[str] = (),
    attempted_specs: Iterable[str] = (),
    failed_attempt_reasons: Iterable[str] = (),
    fallback_trigger: str | None = None,
    phase_step: str | None = None,
    dispatch_key: str | None = None,
) -> CommonWorkerDispatchSpec | None:
    phase = phase_wbc_state(state, step=phase_step or step) or phase_wbc_state(state)
    if phase is None:
        return None
    writer_spec = _WRITER_SPEC_BY_ROUTE.get(route_kind)
    if writer_spec is None:
        raise ValueError(f"unsupported worker dispatch route kind: {route_kind!r}")
    register_worker_dispatch_wbc_writers()

    selected_spec = str(selected_spec or agent).strip()
    phase_attempt_id = str(phase.get("attempt_id") or "").strip()
    phase_source_version = str(phase.get("source_version") or "").strip()
    phase_name = str(phase.get("step") or step).strip() or step
    if not phase_attempt_id or not phase_source_version:
        return None
    normalized_dispatch_key: str | None = None
    if dispatch_key is not None:
        normalized_dispatch_key = str(dispatch_key).strip()
        if not normalized_dispatch_key:
            raise ValueError("dispatch_key must be non-empty when provided")

    identity_parts = (
        f"{phase_source_version}:{route_kind}:{phase_name}:{selected_spec}:{int(attempt_index)}"
    )
    expected_source_version = (
        identity_parts
        if normalized_dispatch_key is None
        else f"{identity_parts}:{normalized_dispatch_key}"
    )
    dispatch_invocation_id = str(
        (state.get("meta") or {}).get("current_invocation_id") or "worker-dispatch"
    )
    legacy_attempt_identity = (
        f"{phase_attempt_id}::{route_kind}::{phase_name}::{selected_spec}::{int(attempt_index)}"
    )
    if normalized_dispatch_key is not None:
        legacy_attempt_identity = f"{legacy_attempt_identity}::{normalized_dispatch_key}"
    legacy_attempt_id = str(
        uuid.uuid5(
            uuid.NAMESPACE_URL,
            legacy_attempt_identity,
        )
    )
    attempt_id = str(
        uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"{legacy_attempt_identity}::{dispatch_invocation_id}::worker-dispatch-v2",
        )
    )
    legacy_idempotency_key = False
    legacy_store = SqliteAttemptLedgerStore(plan_dir / WORKER_DISPATCH_WBC_LEDGER_FILENAME)
    try:
        legacy_events = legacy_store.read_events(legacy_attempt_id)
        if legacy_events:
            expected_legacy_identity = _identity(
                state=state,
                attempt_id=legacy_attempt_id,
                phase_step=phase_name,
                worker_step=step,
                attempt_index=int(attempt_index),
                dispatch_key=normalized_dispatch_key,
                invocation_id=dispatch_invocation_id,
            )
            legacy_idempotency_key = legacy_events[0].identity == expected_legacy_identity
    finally:
        legacy_store.close()
    if legacy_idempotency_key:
        attempt_id = legacy_attempt_id
    configured_specs_tuple = tuple(str(item) for item in configured_specs)
    attempted_specs_tuple = tuple(str(item) for item in attempted_specs)
    failed_attempt_reasons_tuple = tuple(str(item) for item in failed_attempt_reasons)
    metadata = {
        "route_kind": route_kind,
        "phase_step": phase_name,
        "worker_step": step,
        "worker_agent": agent,
        "selected_spec": selected_spec,
        "attempt_index": int(attempt_index),
        "configured_specs": list(configured_specs_tuple),
        "attempted_specs": list(attempted_specs_tuple),
        "failed_attempt_reasons": list(failed_attempt_reasons_tuple),
        "fallback_trigger": fallback_trigger,
        "phase_attempt_id": phase_attempt_id,
    }
    if normalized_dispatch_key is not None:
        metadata["dispatch_key"] = normalized_dispatch_key
    facade = WbcRuntimeProducerFacade(
        SqliteAttemptLedgerStore(plan_dir / WORKER_DISPATCH_WBC_LEDGER_FILENAME),
        source_lookup=lambda key: _exact_source_record(
            state=state,
            step=step,
            selected_spec=selected_spec,
            route_kind=route_kind,
            attempt_index=int(attempt_index),
            phase_step=phase_step,
            dispatch_key=normalized_dispatch_key,
            lookup_key=key,
        ),
        promotion_mode=PromotionMode.ACTION_OFF,
        enforcement_enabled=False,
    )
    artifacts = ImmutableAttemptArtifacts(
        attempt_id=attempt_id,
        metadata=metadata,
    )
    return CommonWorkerDispatchSpec(
        facade=facade,
        attempt_id=attempt_id,
        start_event=_event(
            state=state,
            attempt_id=attempt_id,
            phase_step=phase_name,
            worker_step=step,
            route_kind=route_kind,
            selected_spec=selected_spec,
            dispatch_attempt_index=int(attempt_index),
            dispatch_key=normalized_dispatch_key,
            invocation_id=dispatch_invocation_id,
            sequence=1,
            event_type=AttemptEventType.STARTED,
            idempotency_suffix="started",
            payload={
                **metadata,
                "status": "started",
            },
        ),
        success_event_factory=lambda result: _event(
            state=state,
            attempt_id=attempt_id,
            phase_step=phase_name,
            worker_step=step,
            route_kind=route_kind,
            selected_spec=selected_spec,
            dispatch_attempt_index=int(attempt_index),
            dispatch_key=normalized_dispatch_key,
            invocation_id=dispatch_invocation_id,
            sequence=2,
            event_type=AttemptEventType.COMPLETED,
            idempotency_suffix="completed",
            outcome=AttemptOutcome.SUCCEEDED,
            payload={
                **metadata,
                "status": "completed",
                **_worker_result_summary(result),
            },
        ),
        failure_event_factory=lambda exc: _event(
            state=state,
            attempt_id=attempt_id,
            phase_step=phase_name,
            worker_step=step,
            route_kind=route_kind,
            selected_spec=selected_spec,
            dispatch_attempt_index=int(attempt_index),
            dispatch_key=normalized_dispatch_key,
            invocation_id=dispatch_invocation_id,
            sequence=2,
            event_type=AttemptEventType.FAILED,
            idempotency_suffix="failed",
            outcome=AttemptOutcome.INDETERMINATE,
            payload={
                **metadata,
                "status": "failed",
                "error_type": type(exc).__name__,
                "error": str(exc),
            },
        ),
        start_action_context=_shadow_action_context(
            phase_step=phase_name,
            worker_step=step,
            route_kind=route_kind,
            selected_spec=selected_spec,
            expected_source_version=expected_source_version,
            attempt_id=attempt_id,
            action_type="dispatch",
        ),
        success_action_context=_shadow_action_context(
            phase_step=phase_name,
            worker_step=step,
            route_kind=route_kind,
            selected_spec=selected_spec,
            expected_source_version=expected_source_version,
            attempt_id=attempt_id,
            action_type="completion",
        ),
        failure_action_context=_shadow_action_context(
            phase_step=phase_name,
            worker_step=step,
            route_kind=route_kind,
            selected_spec=selected_spec,
            expected_source_version=expected_source_version,
            attempt_id=attempt_id,
            action_type="repair",
        ),
        artifacts=artifacts,
        writer_id=writer_spec.writer_id,
        surface_name=writer_spec.surface_name,
        expected_source_version=expected_source_version,
        start_source_lookup_key=_lookup_key(
            phase_step=phase_name,
            worker_step=step,
            route_kind=route_kind,
            attempt_index=int(attempt_index),
            dispatch_key=normalized_dispatch_key,
            stage="start",
        ),
        success_source_lookup_key=_lookup_key(
            phase_step=phase_name,
            worker_step=step,
            route_kind=route_kind,
            attempt_index=int(attempt_index),
            dispatch_key=normalized_dispatch_key,
            stage="complete",
        ),
        failure_source_lookup_key=_lookup_key(
            phase_step=phase_name,
            worker_step=step,
            route_kind=route_kind,
            attempt_index=int(attempt_index),
            dispatch_key=normalized_dispatch_key,
            stage="failure",
        ),
    )


def _lookup_key(
    *,
    phase_step: str,
    worker_step: str,
    route_kind: str,
    attempt_index: int,
    dispatch_key: str | None,
    stage: str,
) -> str:
    base = f"{phase_step}:{worker_step}:{route_kind}:{attempt_index}"
    if dispatch_key is not None:
        base = f"{base}:{dispatch_key}"
    return f"{base}:{stage}"


def _exact_source_record(
    *,
    state: PlanState,
    step: str,
    selected_spec: str,
    route_kind: str,
    attempt_index: int,
    phase_step: str | None,
    dispatch_key: str | None,
    lookup_key: str,
) -> ExactSourceRecord | None:
    phase = phase_wbc_state(state, step=phase_step or step) or phase_wbc_state(state)
    if phase is None:
        return None
    phase_source_version = str(phase.get("source_version") or "").strip()
    phase_attempt_id = str(phase.get("attempt_id") or "").strip()
    phase_name = str(phase.get("step") or step).strip() or step
    if not phase_source_version or not phase_attempt_id:
        return None
    version = f"{phase_source_version}:{route_kind}:{phase_name}:{selected_spec}:{attempt_index}"
    if dispatch_key is not None:
        version = f"{version}:{dispatch_key}"
    metadata = {
        "phase_step": phase_name,
        "worker_step": step,
        "selected_spec": selected_spec,
        "route_kind": route_kind,
        "attempt_index": attempt_index,
        "phase_attempt_id": phase_attempt_id,
    }
    if dispatch_key is not None:
        metadata["dispatch_key"] = dispatch_key
    return ExactSourceRecord(
        lookup_key=lookup_key,
        version=version,
        source_uri=f"plan://{phase_name}/{route_kind}/{step}",
        observed_at=_utcnow(),
        metadata=metadata,
    )


def _identity(
    *,
    state: PlanState,
    attempt_id: str,
    phase_step: str,
    worker_step: str,
    attempt_index: int,
    dispatch_key: str | None,
    invocation_id: str | None = None,
) -> AttemptIdentity:
    invocation_id = str(
        invocation_id
        or (state.get("meta") or {}).get("current_invocation_id")
        or "worker-dispatch"
    )
    return AttemptIdentity(
        workflow_id="megaplan.worker_dispatch",
        run_id=str(state.get("name") or "megaplan-plan"),
        graph_revision=phase_step,
        step_id=worker_step if dispatch_key is None else f"{worker_step}:{dispatch_key}",
        invocation_id=invocation_id,
        attempt_ordinal=max(attempt_index + 1, 1),
        attempt_id=attempt_id,
    )


def _event(
    *,
    state: PlanState,
    attempt_id: str,
    phase_step: str,
    worker_step: str,
    route_kind: str,
    selected_spec: str,
    dispatch_attempt_index: int,
    dispatch_key: str | None,
    sequence: int,
    event_type: AttemptEventType,
    idempotency_suffix: str,
    invocation_id: str | None = None,
    outcome: AttemptOutcome | None = None,
    payload: Mapping[str, Any] | None = None,
) -> LedgerEvent:
    return LedgerEvent(
        idempotency_key=f"{attempt_id}:{idempotency_suffix}",
        event_type=event_type,
        identity=_identity(
            state=state,
            attempt_id=attempt_id,
            phase_step=phase_step,
            worker_step=worker_step,
            attempt_index=dispatch_attempt_index,
            dispatch_key=dispatch_key,
            invocation_id=invocation_id,
        ),
        provenance=AttemptProvenance(
            actor_id="megaplan.worker_dispatch",
            tool_id=route_kind,
        ),
        adapter=RuntimeAdapter(
            adapter_kind=AdapterKind.MEGAPLAN_PHASE,
            adapter_version="1",
        ),
        versions=VersionSet(
            code_version=f"{phase_step}:{selected_spec}",
            config_version=f"{route_kind}.config.v1",
            template_version=f"{worker_step}.dispatch.v1",
        ),
        grant_ref=GrantRef(grant_id=f"{phase_step}:{route_kind}:{selected_spec}"),
        sequence=sequence,
        causal_predecessor_sequence=max(sequence - 1, 0),
        append_position=sequence,
        occurred_at=_utcnow(),
        observed_at=_utcnow(),
        persistence_status=PersistenceStatus.DURABLE,
        outcome=outcome,
        payload=dict(payload or {}),
    )


def _shadow_action_context(
    *,
    phase_step: str,
    worker_step: str,
    route_kind: str,
    selected_spec: str,
    expected_source_version: str,
    attempt_id: str,
    action_type: str,
) -> ActionBoundaryContext:
    return ActionBoundaryContext(
        action_type=action_type,  # type: ignore[arg-type]
        target=CustodyTargetKey(
            "phase_worker_dispatch",
            phase_step,
            action_type,
            route_kind,
            worker_step,
            selected_spec,
        ),
        run_authority_grant_id=attempt_id,
        coordinator_fence_token=0,
        wbc_attempt_reference=attempt_id,
        required_capability=route_kind,
        required_wbc_evidence_version=expected_source_version,
    )


def _worker_result_summary(result: Any) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for field_name in ("session_id", "model_actual", "worker_channel", "auth_channel"):
        value = getattr(result, field_name, None)
        if value not in (None, ""):
            summary[field_name] = value
    auth_metadata = getattr(result, "auth_metadata", None)
    if isinstance(auth_metadata, Mapping):
        summary["auth_metadata"] = dict(auth_metadata)
    return summary


def query_worker_dispatch_manifest(
    plan_dir: Path,
    *,
    phase_attempt_id: str,
) -> list[dict[str, Any]]:
    """Return terminally evidenced child dispatches for one phase attempt."""
    store = SqliteAttemptLedgerStore(plan_dir / WORKER_DISPATCH_WBC_LEDGER_FILENAME)
    try:
        rows = store.conn.execute(
            "SELECT DISTINCT attempt_id FROM attempt_events ORDER BY attempt_id"
        ).fetchall()
        manifest: list[dict[str, Any]] = []
        for (attempt_id,) in rows:
            events = store.read_events(str(attempt_id))
            if not events:
                continue
            start = events[0]
            start_payload = dict(start.payload or {})
            if start_payload.get("phase_attempt_id") != phase_attempt_id:
                continue
            terminal = events[-1]
            if terminal.event_type not in {
                AttemptEventType.COMPLETED,
                AttemptEventType.FAILED,
                AttemptEventType.CANCELLED,
            }:
                raise RuntimeError(
                    f"worker dispatch {attempt_id} has no terminal custody event"
                )
            terminal_payload = dict(terminal.payload or {})
            manifest.append(
                {
                    "attempt_id": str(attempt_id),
                    "dispatch_key": start_payload.get("dispatch_key"),
                    "worker_step": start_payload.get("worker_step"),
                    "selected_spec": start_payload.get("selected_spec"),
                    "attempt_index": start_payload.get("attempt_index"),
                    "terminal_event": terminal.event_type.value,
                    "terminal_status": terminal_payload.get("status"),
                    "start_sequence": start.sequence,
                    "terminal_sequence": terminal.sequence,
                }
            )
        return sorted(
            manifest,
            key=lambda row: (
                str(row.get("dispatch_key") or ""),
                int(row.get("attempt_index") or 0),
                str(row["attempt_id"]),
            ),
        )
    finally:
        store.close()


__all__ = [
    "WORKER_DISPATCH_WBC_LEDGER_FILENAME",
    "build_worker_dispatch_spec",
    "query_worker_dispatch_manifest",
    "register_worker_dispatch_wbc_writers",
]
