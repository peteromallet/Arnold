"""Phase-scoped WBC lifecycle evidence for front-half and tiebreaker producers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import uuid
from typing import Any, Mapping

from arnold.workflow.attempt_ledger_store import SourceCursor, SqliteAttemptLedgerStore
from arnold.workflow.execution_attempt_ledger import (
    AdapterKind,
    AttemptEventType,
    AttemptIdentity,
    AttemptOutcome,
    AttemptProvenance,
    CheckpointPayload,
    GrantRef,
    LedgerEvent,
    PersistenceStatus,
    RuntimeAdapter,
    VersionSet,
)
from arnold_pipelines.megaplan.types import PlanState

from .controlled_writer_registry import Cohort, ControlledWriter, register_writer
from .wbc_runtime import ExactSourceRecord, ImmutableAttemptArtifacts, PromotionMode, WbcRuntimeProducerFacade


PHASE_WBC_STATE_KEY = "_phase_wbc"
PHASE_WBC_SUSPENSIONS_STATE_KEY = "phase_wbc_suspensions"
PHASE_WBC_LEDGER_FILENAME = ".phase_wbc_attempts.sqlite3"
PHASE_WBC_SUSPENSION_CURSOR_KEY = "clarification"


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class PhaseWbcSpec:
    step: str
    writer_id: str
    surface_name: str
    contract_ids: tuple[str, ...]
    source_file: str
    function_name: str


_PHASE_WBC_SPECS: tuple[PhaseWbcSpec, ...] = (
    PhaseWbcSpec(
        step="prep",
        writer_id="megaplan.phase_wbc.prep",
        surface_name="megaplan.phase_wbc.prep",
        contract_ids=("prep_to_plan",),
        source_file="arnold_pipelines/megaplan/handlers/plan.py",
        function_name="handle_prep",
    ),
    PhaseWbcSpec(
        step="plan",
        writer_id="megaplan.phase_wbc.plan",
        surface_name="megaplan.phase_wbc.plan",
        contract_ids=("plan_to_critique",),
        source_file="arnold_pipelines/megaplan/handlers/plan.py",
        function_name="handle_plan",
    ),
    PhaseWbcSpec(
        step="critique",
        writer_id="megaplan.phase_wbc.critique",
        surface_name="megaplan.phase_wbc.critique",
        contract_ids=("critique_to_gate",),
        source_file="arnold_pipelines/megaplan/orchestration/critique_runtime.py",
        function_name="handle_critique",
    ),
    PhaseWbcSpec(
        step="gate",
        writer_id="megaplan.phase_wbc.gate",
        surface_name="megaplan.phase_wbc.gate",
        contract_ids=("gate_to_revise",),
        source_file="arnold_pipelines/megaplan/handlers/gate.py",
        function_name="handle_gate",
    ),
    PhaseWbcSpec(
        step="revise",
        writer_id="megaplan.phase_wbc.revise",
        surface_name="megaplan.phase_wbc.revise",
        contract_ids=("revise_to_critique",),
        source_file="arnold_pipelines/megaplan/orchestration/critique_runtime.py",
        function_name="handle_revise",
    ),
    PhaseWbcSpec(
        step="tiebreaker_researcher",
        writer_id="megaplan.phase_wbc.tiebreaker_researcher",
        surface_name="megaplan.phase_wbc.tiebreaker_researcher",
        contract_ids=("tiebreaker_researcher_to_challenger",),
        source_file="arnold_pipelines/megaplan/orchestration/tiebreaker_runtime.py",
        function_name="handle_tiebreaker_run",
    ),
    PhaseWbcSpec(
        step="tiebreaker_challenger",
        writer_id="megaplan.phase_wbc.tiebreaker_challenger",
        surface_name="megaplan.phase_wbc.tiebreaker_challenger",
        contract_ids=("tiebreaker_challenger_to_synthesis",),
        source_file="arnold_pipelines/megaplan/orchestration/tiebreaker_runtime.py",
        function_name="handle_tiebreaker_run",
    ),
    PhaseWbcSpec(
        step="tiebreaker_synthesis",
        writer_id="megaplan.phase_wbc.tiebreaker_synthesis",
        surface_name="megaplan.phase_wbc.tiebreaker_synthesis",
        contract_ids=("tiebreaker_synthesis_to_decision",),
        source_file="arnold_pipelines/megaplan/orchestration/tiebreaker_runtime.py",
        function_name="handle_tiebreaker_run",
    ),
    PhaseWbcSpec(
        step="tiebreaker_decision",
        writer_id="megaplan.phase_wbc.tiebreaker_decision",
        surface_name="megaplan.phase_wbc.tiebreaker_decision",
        contract_ids=("tiebreaker_decision_to_parent",),
        source_file="arnold_pipelines/megaplan/orchestration/tiebreaker_runtime.py",
        function_name="handle_tiebreaker_decide",
    ),
    PhaseWbcSpec(
        step="review",
        writer_id="megaplan.phase_wbc.review",
        surface_name="megaplan.phase_wbc.review",
        contract_ids=(
            "review_reducer_promotion",
            "review_rework_effects",
            "review_cap_authority",
            "review_human_verification",
        ),
        source_file="arnold_pipelines/megaplan/handlers/review.py",
        function_name="handle_review",
    ),
    PhaseWbcSpec(
        step="finalize",
        writer_id="megaplan.phase_wbc.finalize",
        surface_name="megaplan.phase_wbc.finalize",
        contract_ids=(
            "finalize_artifacts",
            "finalize_fallback",
            "final_projection",
        ),
        source_file="arnold_pipelines/megaplan/handlers/finalize.py",
        function_name="handle_finalize",
    ),
)

_PHASE_WBC_SPEC_BY_STEP = {spec.step: spec for spec in _PHASE_WBC_SPECS}


def phase_wbc_required(step: str) -> bool:
    return step in _PHASE_WBC_SPEC_BY_STEP


def register_phase_wbc_writers() -> None:
    for spec in _PHASE_WBC_SPECS:
        try:
            register_writer(
                ControlledWriter(
                    writer_id=spec.writer_id,
                    surface_name=spec.surface_name,
                    cohort=Cohort.ACTIVE,
                    contract_ids=spec.contract_ids,
                    source_file=spec.source_file,
                    function_name=spec.function_name,
                    required_wbc_phases=("start", "terminal", "result"),
                    action_kind="phase_transition",
                )
            )
        except ValueError:
            continue


def phase_wbc_state(state: PlanState, *, step: str | None = None) -> dict[str, Any] | None:
    active_step = state.get("active_step")
    if not isinstance(active_step, dict):
        return None
    payload = active_step.get(PHASE_WBC_STATE_KEY)
    if not isinstance(payload, dict):
        return None
    if step is not None and payload.get("step") != step:
        return None
    return dict(payload)


def phase_wbc_suspension_state(
    state: PlanState,
    *,
    step: str,
) -> dict[str, Any] | None:
    meta = state.get("meta")
    if not isinstance(meta, dict):
        return None
    suspensions = meta.get(PHASE_WBC_SUSPENSIONS_STATE_KEY)
    if not isinstance(suspensions, dict):
        return None
    payload = suspensions.get(step)
    return dict(payload) if isinstance(payload, dict) else None


def phase_wbc_attempt_id(plan_dir: Path, *, step: str, invocation_id: str) -> str:
    return str(
        uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"{plan_dir.resolve()}::{step}::{invocation_id}",
        )
    )


def query_phase_wbc_events(
    plan_dir: Path,
    *,
    step: str,
    invocation_id: str,
) -> tuple[LedgerEvent, ...]:
    attempt_id = phase_wbc_attempt_id(
        plan_dir,
        step=step,
        invocation_id=invocation_id,
    )
    return tuple(_phase_store(plan_dir).read_events(attempt_id))


def query_phase_wbc_cursor(
    plan_dir: Path,
    *,
    step: str,
    invocation_id: str,
    cursor_key: str = PHASE_WBC_SUSPENSION_CURSOR_KEY,
) -> SourceCursor | None:
    attempt_id = phase_wbc_attempt_id(
        plan_dir,
        step=step,
        invocation_id=invocation_id,
    )
    return _phase_store(plan_dir).query_source_cursor(attempt_id, cursor_key)


def activate_phase_wbc(
    *,
    state: PlanState,
    plan_dir: Path,
    step: str,
    agent: str,
) -> dict[str, Any] | None:
    spec = _PHASE_WBC_SPEC_BY_STEP.get(step)
    if spec is None:
        return None
    active_step = state.get("active_step")
    if not isinstance(active_step, dict):
        raise RuntimeError(f"active_step is required before activating phase WBC for {step!r}")
    existing = phase_wbc_state(state, step=step)
    if existing is not None:
        return existing

    register_phase_wbc_writers()
    invocation_id = str((state.get("meta") or {}).get("current_invocation_id") or "").strip()
    if not invocation_id:
        raise RuntimeError(f"current_invocation_id is required before activating phase WBC for {step!r}")

    attempt_id = phase_wbc_attempt_id(
        plan_dir,
        step=step,
        invocation_id=invocation_id,
    )
    source_version = f"{step}:{invocation_id}"
    facade = _phase_facade(plan_dir)
    artifacts = ImmutableAttemptArtifacts(
        attempt_id=attempt_id,
        metadata={"phase": step, "invocation_id": invocation_id},
    )
    start_lookup_key = f"{step}:{invocation_id}:start"
    facade.reserve_attempt(
        attempt_id=attempt_id,
        writer_id=spec.writer_id,
        surface_name=spec.surface_name,
        source_lookup_key=start_lookup_key,
        expected_source_version=source_version,
        artifacts=artifacts,
    )
    facade.start_attempt(
        attempt_id=attempt_id,
        event=_event(
            state=state,
            attempt_id=attempt_id,
            step=step,
            invocation_id=invocation_id,
            sequence=1,
            event_type=AttemptEventType.STARTED,
            outcome=None,
            agent=agent,
            payload={
                "phase": step,
                "status": "started",
                "invocation_id": invocation_id,
            },
        ),
        writer_id=spec.writer_id,
        surface_name=spec.surface_name,
        source_lookup_key=start_lookup_key,
        expected_source_version=source_version,
        artifacts=artifacts,
    )
    metadata = {
        "step": step,
        "attempt_id": attempt_id,
        "invocation_id": invocation_id,
        "writer_id": spec.writer_id,
        "surface_name": spec.surface_name,
        "source_version": source_version,
    }
    active_step[PHASE_WBC_STATE_KEY] = metadata
    return dict(metadata)


def suspend_phase_wbc(
    *,
    state: PlanState,
    plan_dir: Path,
    step: str,
    checkpoint: Mapping[str, Any],
    cursor: Mapping[str, Any],
    agent: str,
) -> dict[str, Any]:
    metadata = phase_wbc_state(state, step=step)
    if metadata is None:
        raise RuntimeError(f"active phase WBC attempt is required to suspend {step!r}")
    spec = _PHASE_WBC_SPEC_BY_STEP[step]
    attempt_id = str(metadata["attempt_id"])
    invocation_id = str(metadata["invocation_id"])
    source_version = str(metadata["source_version"])
    checkpoint_data = dict(checkpoint)
    cursor_data = dict(cursor)
    checkpoint_digest = _canonical_digest(
        {"checkpoint": checkpoint_data, "cursor": cursor_data}
    )
    typed_checkpoint = CheckpointPayload(
        inline_data={
            "checkpoint": checkpoint_data,
            "cursor": cursor_data,
        },
        content_digest=checkpoint_digest,
    )
    checkpoint_payload = {
        "schema_version": typed_checkpoint.schema_version,
        **typed_checkpoint.to_dict(),
    }
    facade = _phase_facade(plan_dir)
    artifacts = ImmutableAttemptArtifacts(
        attempt_id=attempt_id,
        metadata={"phase": step, "invocation_id": invocation_id},
    )
    facade.suspend_attempt(
        attempt_id=attempt_id,
        event=_event(
            state=state,
            attempt_id=attempt_id,
            step=step,
            invocation_id=invocation_id,
            sequence=2,
            event_type=AttemptEventType.SUSPENDED,
            outcome=None,
            agent=agent,
            payload={
                "phase": step,
                "status": "suspended",
                "invocation_id": invocation_id,
                "checkpoint": checkpoint_payload,
            },
        ),
        writer_id=spec.writer_id,
        surface_name=spec.surface_name,
        source_lookup_key=f"{step}:{invocation_id}:suspended",
        expected_source_version=source_version,
        artifacts=artifacts,
        cursor_key=PHASE_WBC_SUSPENSION_CURSOR_KEY,
    )
    _phase_store(plan_dir).update_source_cursor(
        attempt_id,
        2,
        PHASE_WBC_SUSPENSION_CURSOR_KEY,
        checkpoint_digest,
    )
    suspension = {
        **metadata,
        "checkpoint": checkpoint_payload,
        "checkpoint_digest": checkpoint_digest,
        "cursor_key": PHASE_WBC_SUSPENSION_CURSOR_KEY,
        "suspended_sequence": 2,
    }
    meta = state.setdefault("meta", {})
    suspensions = meta.setdefault(PHASE_WBC_SUSPENSIONS_STATE_KEY, {})
    suspensions[step] = suspension
    active_step = state.get("active_step")
    if isinstance(active_step, dict):
        active_step.pop(PHASE_WBC_STATE_KEY, None)
    return dict(suspension)


def resume_suspended_phase_wbc(
    *,
    state: PlanState,
    plan_dir: Path,
    step: str,
    agent: str,
) -> str:
    metadata = phase_wbc_suspension_state(state, step=step)
    if metadata is None:
        raise RuntimeError(f"durable phase WBC suspension is required to resume {step!r}")
    spec = _PHASE_WBC_SPEC_BY_STEP[step]
    attempt_id = str(metadata["attempt_id"])
    invocation_id = str(metadata["invocation_id"])
    source_version = str(metadata["source_version"])
    checkpoint_digest = str(metadata["checkpoint_digest"])
    cursor_key = str(metadata["cursor_key"])
    store = _phase_store(plan_dir)
    cursor = store.query_source_cursor(attempt_id, cursor_key)
    persisted_events = tuple(store.read_events(attempt_id))
    event_types = tuple(event.event_type for event in persisted_events)
    completed_lifecycle = (
        AttemptEventType.STARTED,
        AttemptEventType.SUSPENDED,
        AttemptEventType.RESUMED,
        AttemptEventType.COMPLETED,
    )
    resumed_lifecycle = completed_lifecycle[:-1]
    if event_types == completed_lifecycle:
        resumed_payload = persisted_events[2].payload
        reentry_invocation_id = (
            str(resumed_payload.get("reentry_invocation_id") or "")
            if isinstance(resumed_payload, dict)
            else ""
        )
        if not reentry_invocation_id:
            raise RuntimeError(
                f"completed phase WBC resume is missing reentry lineage for {step!r}"
            )
        store.update_source_cursor(
            attempt_id,
            4,
            cursor_key,
            "completed",
        )
        clear_phase_wbc_suspension(state, step=step)
        return reentry_invocation_id
    suspended_lifecycle = (
        AttemptEventType.STARTED,
        AttemptEventType.SUSPENDED,
    )
    if event_types not in {
        suspended_lifecycle,
        resumed_lifecycle,
    }:
        raise RuntimeError(
            f"phase WBC suspension lifecycle mismatch for {step!r} attempt {attempt_id}"
        )
    if event_types == suspended_lifecycle and (
        cursor is None
        or cursor.last_sequence != int(metadata["suspended_sequence"])
        or cursor.last_position != checkpoint_digest
    ):
        raise RuntimeError(
            f"phase WBC suspension cursor mismatch for {step!r} attempt {attempt_id}"
        )
    if event_types == resumed_lifecycle:
        resumed_payload = persisted_events[2].payload
        reentry_invocation_id = (
            str(resumed_payload.get("reentry_invocation_id") or "")
            if isinstance(resumed_payload, dict)
            else ""
        )
        if not reentry_invocation_id:
            raise RuntimeError(
                f"resumed phase WBC attempt is missing reentry lineage for {step!r}"
            )
    else:
        reentry_invocation_id = str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"{attempt_id}::resume-clarify::{checkpoint_digest}",
            )
        )
    facade = _phase_facade(plan_dir)
    artifacts = ImmutableAttemptArtifacts(
        attempt_id=attempt_id,
        metadata={"phase": step, "invocation_id": invocation_id},
    )
    common = {
        "attempt_id": attempt_id,
        "writer_id": spec.writer_id,
        "surface_name": spec.surface_name,
        "expected_source_version": source_version,
        "artifacts": artifacts,
        "cursor_key": cursor_key,
    }
    if event_types != resumed_lifecycle:
        facade.resume_attempt(
            event=_event(
                state=state,
                attempt_id=attempt_id,
                step=step,
                invocation_id=invocation_id,
                sequence=3,
                event_type=AttemptEventType.RESUMED,
                outcome=None,
                agent=agent,
                payload={
                    "phase": step,
                    "status": "resumed",
                    "invocation_id": invocation_id,
                    "reentry_invocation_id": reentry_invocation_id,
                    "checkpoint": metadata["checkpoint"],
                },
            ),
            source_lookup_key=f"{step}:{invocation_id}:resumed",
            **common,
        )
    store.update_source_cursor(
        attempt_id,
        3,
        cursor_key,
        reentry_invocation_id,
    )
    facade.complete_attempt(
        event=_event(
            state=state,
            attempt_id=attempt_id,
            step=step,
            invocation_id=invocation_id,
            sequence=4,
            event_type=AttemptEventType.COMPLETED,
            outcome=AttemptOutcome.SUCCEEDED,
            agent=agent,
            payload={
                "phase": step,
                "status": "completed",
                "invocation_id": invocation_id,
                "reentry_invocation_id": reentry_invocation_id,
                "completion_reason": "clarification_resumed",
            },
        ),
        source_lookup_key=f"{step}:{invocation_id}:resumed-terminal",
        **common,
    )
    store.update_source_cursor(
        attempt_id,
        4,
        cursor_key,
        "completed",
    )
    clear_phase_wbc_suspension(state, step=step)
    return reentry_invocation_id


def resume_clarification_phase_wbc_if_present(
    *,
    state: PlanState,
    plan_dir: Path,
    agent: str,
) -> str | None:
    suspension = phase_wbc_suspension_state(state, step="prep")
    has_ledger = (plan_dir / PHASE_WBC_LEDGER_FILENAME).is_file()
    if suspension is None and not has_ledger:
        return None
    return resume_suspended_phase_wbc(
        state=state,
        plan_dir=plan_dir,
        step="prep",
        agent=agent,
    )


def complete_phase_wbc(
    *,
    state: PlanState,
    plan_dir: Path,
    step: str,
    payload: Mapping[str, Any],
    agent: str,
) -> None:
    _terminal_phase_wbc(
        state=state,
        plan_dir=plan_dir,
        step=step,
        agent=agent,
        event_type=AttemptEventType.COMPLETED,
        outcome=AttemptOutcome.SUCCEEDED,
        payload=payload,
    )


def fail_phase_wbc(
    *,
    state: PlanState,
    plan_dir: Path,
    step: str,
    payload: Mapping[str, Any],
    agent: str,
) -> None:
    _terminal_phase_wbc(
        state=state,
        plan_dir=plan_dir,
        step=step,
        agent=agent,
        event_type=AttemptEventType.FAILED,
        outcome=AttemptOutcome.INDETERMINATE,
        payload=payload,
    )


def cancel_phase_wbc(
    *,
    state: PlanState,
    plan_dir: Path,
    step: str,
    expected_attempt_id: str,
    expected_invocation_id: str,
    agent: str,
    reason: str,
) -> dict[str, Any]:
    """Terminalize exactly one active phase attempt as ``CANCELLED``.

    This is the operator/recovery counterpart to ``complete_phase_wbc`` and
    ``fail_phase_wbc``.  Both durable identities are mandatory CAS operands;
    a caller can never cancel whichever attempt happens to be current.  The
    function removes only the matching ``_phase_wbc`` custody record and does
    not clear ``active_step`` itself.
    """

    expected_attempt_id = str(expected_attempt_id).strip()
    expected_invocation_id = str(expected_invocation_id).strip()
    if not expected_attempt_id or not expected_invocation_id:
        raise ValueError("phase WBC cancellation requires attempt and invocation ids")
    metadata = phase_wbc_state(state, step=step)
    if metadata is None:
        raise RuntimeError(f"active phase WBC attempt is required to cancel {step!r}")
    actual_attempt_id = str(metadata.get("attempt_id") or "")
    actual_invocation_id = str(metadata.get("invocation_id") or "")
    if (
        actual_attempt_id != expected_attempt_id
        or actual_invocation_id != expected_invocation_id
    ):
        raise RuntimeError(
            "phase WBC cancellation identity mismatch: "
            f"expected {expected_attempt_id}/{expected_invocation_id}, "
            f"found {actual_attempt_id}/{actual_invocation_id}"
        )
    derived_attempt_id = phase_wbc_attempt_id(
        plan_dir,
        step=step,
        invocation_id=expected_invocation_id,
    )
    if derived_attempt_id != expected_attempt_id:
        raise RuntimeError(
            "phase WBC cancellation attempt id does not match plan/step/invocation lineage"
        )
    events = query_phase_wbc_events(
        plan_dir,
        step=step,
        invocation_id=expected_invocation_id,
    )
    event_types = tuple(event.event_type for event in events)
    fresh_cancel = event_types == (AttemptEventType.STARTED,)
    replayed_cancel = event_types == (
        AttemptEventType.STARTED,
        AttemptEventType.CANCELLED,
    )
    if not fresh_cancel and not replayed_cancel:
        raise RuntimeError(
            f"phase WBC attempt {expected_attempt_id} is not uniquely cancellable from STARTED"
        )
    if replayed_cancel:
        terminal = events[-1]
        if (
            terminal.identity.attempt_id != expected_attempt_id
            or terminal.identity.invocation_id != expected_invocation_id
            or terminal.outcome is not AttemptOutcome.CANCELLED
        ):
            raise RuntimeError(
                "phase WBC cancellation replay does not match the expected terminal identity"
            )
    else:
        spec = _PHASE_WBC_SPEC_BY_STEP[step]
        source_version = str(metadata["source_version"])
        event = _event(
            state=state,
            attempt_id=expected_attempt_id,
            step=step,
            invocation_id=expected_invocation_id,
            sequence=2,
            event_type=AttemptEventType.CANCELLED,
            outcome=AttemptOutcome.CANCELLED,
            agent=agent,
            payload={
                "phase": step,
                "status": "cancelled",
                "invocation_id": expected_invocation_id,
                "reason": str(reason).strip() or "operator_cancelled",
            },
        )
        artifacts = ImmutableAttemptArtifacts(
            attempt_id=expected_attempt_id,
            metadata={"phase": step, "invocation_id": expected_invocation_id},
        )
        _phase_facade(plan_dir).cancel_attempt(
            attempt_id=expected_attempt_id,
            event=event,
            writer_id=spec.writer_id,
            surface_name=spec.surface_name,
            source_lookup_key=f"{step}:{expected_invocation_id}:terminal",
            expected_source_version=source_version,
            artifacts=artifacts,
        )

    # In-memory compare-and-remove: even after the durable terminal event, a
    # replacement custody record must not be erased by this older operation.
    active_step = state.get("active_step")
    current = (
        active_step.get(PHASE_WBC_STATE_KEY)
        if isinstance(active_step, dict)
        else None
    )
    if not isinstance(current, dict) or dict(current) != metadata:
        raise RuntimeError(
            "phase WBC custody changed during cancellation; refusing in-memory clear"
        )
    active_step.pop(PHASE_WBC_STATE_KEY, None)
    return {
        "step": step,
        "attempt_id": expected_attempt_id,
        "invocation_id": expected_invocation_id,
        "event_type": AttemptEventType.CANCELLED.value,
        "outcome": AttemptOutcome.CANCELLED.value,
        "sequence": 2,
        "active_step_preserved": True,
        "replayed": replayed_cancel,
    }


def _terminal_phase_wbc(
    *,
    state: PlanState,
    plan_dir: Path,
    step: str,
    agent: str,
    event_type: AttemptEventType,
    outcome: AttemptOutcome,
    payload: Mapping[str, Any],
) -> None:
    metadata = phase_wbc_state(state, step=step)
    if metadata is None:
        return
    spec = _PHASE_WBC_SPEC_BY_STEP[step]
    facade = _phase_facade(plan_dir)
    attempt_id = str(metadata["attempt_id"])
    invocation_id = str(metadata["invocation_id"])
    source_version = str(metadata["source_version"])
    lookup_key = f"{step}:{invocation_id}:terminal"
    artifacts = ImmutableAttemptArtifacts(
        attempt_id=attempt_id,
        metadata={"phase": step, "invocation_id": invocation_id},
    )
    event = _event(
        state=state,
        attempt_id=attempt_id,
        step=step,
        invocation_id=invocation_id,
        sequence=2,
        event_type=event_type,
        outcome=outcome,
        agent=agent,
        payload=dict(payload),
    )
    if event_type is AttemptEventType.COMPLETED:
        facade.complete_attempt(
            attempt_id=attempt_id,
            event=event,
            writer_id=spec.writer_id,
            surface_name=spec.surface_name,
            source_lookup_key=lookup_key,
            expected_source_version=source_version,
            artifacts=artifacts,
        )
    else:
        facade.fail_attempt(
            attempt_id=attempt_id,
            event=event,
            writer_id=spec.writer_id,
            surface_name=spec.surface_name,
            source_lookup_key=lookup_key,
            expected_source_version=source_version,
            artifacts=artifacts,
        )
    active_step = state.get("active_step")
    if isinstance(active_step, dict):
        active_step.pop(PHASE_WBC_STATE_KEY, None)


def _phase_facade(plan_dir: Path) -> WbcRuntimeProducerFacade:
    return WbcRuntimeProducerFacade(
        _phase_store(plan_dir),
        source_lookup=lambda key: ExactSourceRecord(
            lookup_key=key,
            version=_source_version_from_lookup_key(key),
            source_uri=f"plan://{plan_dir.name}/{key}",
            observed_at=_utcnow(),
            metadata={"lookup_key": key},
        ),
        promotion_mode=PromotionMode.ACTION_OFF,
        enforcement_enabled=False,
    )


def _phase_store(plan_dir: Path) -> SqliteAttemptLedgerStore:
    return SqliteAttemptLedgerStore(plan_dir / PHASE_WBC_LEDGER_FILENAME)


def _canonical_digest(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def clear_phase_wbc_suspension(state: PlanState, *, step: str) -> None:
    meta = state.get("meta")
    suspensions = (
        meta.get(PHASE_WBC_SUSPENSIONS_STATE_KEY)
        if isinstance(meta, dict)
        else None
    )
    if isinstance(suspensions, dict):
        suspensions.pop(step, None)
        if not suspensions:
            meta.pop(PHASE_WBC_SUSPENSIONS_STATE_KEY, None)


def _source_version_from_lookup_key(lookup_key: str) -> str:
    head, _sep, tail = str(lookup_key).rpartition(":")
    return head if head else str(lookup_key)


def _event(
    *,
    state: PlanState,
    attempt_id: str,
    step: str,
    invocation_id: str,
    sequence: int,
    event_type: AttemptEventType,
    outcome: AttemptOutcome | None,
    agent: str,
    payload: Mapping[str, Any],
) -> LedgerEvent:
    active_step = state.get("active_step") if isinstance(state.get("active_step"), dict) else {}
    attempt_ordinal = int(active_step.get("attempt", 1) or 1) if isinstance(active_step, dict) else 1
    source_version = f"{step}:{invocation_id}"
    return LedgerEvent(
        idempotency_key=f"{attempt_id}:{event_type.value}",
        event_type=event_type,
        identity=AttemptIdentity(
            workflow_id="megaplan-review",
            run_id=str(state.get("name") or "megaplan"),
            graph_revision=str(state.get("iteration") or 0),
            step_id=step,
            invocation_id=invocation_id,
            attempt_ordinal=attempt_ordinal,
            attempt_id=attempt_id,
        ),
        provenance=AttemptProvenance(actor_id=str(agent or "megaplan"), tool_id="megaplan.phase_wbc"),
        adapter=RuntimeAdapter(adapter_kind=AdapterKind.MEGAPLAN_PHASE, adapter_version="1"),
        versions=VersionSet(
            code_version=source_version,
            config_version=str(((state.get("config") or {}) if isinstance(state.get("config"), dict) else {}).get("profile") or "default"),
            template_version="phase_wbc.v1",
        ),
        grant_ref=GrantRef(grant_id=f"phase-wbc:{step}"),
        sequence=sequence,
        causal_predecessor_sequence=max(sequence - 1, 0),
        append_position=sequence,
        occurred_at=_utcnow(),
        observed_at=_utcnow(),
        persistence_status=PersistenceStatus.DURABLE,
        outcome=outcome,
        payload=dict(payload),
    )


__all__ = [
    "PHASE_WBC_LEDGER_FILENAME",
    "PHASE_WBC_SUSPENSIONS_STATE_KEY",
    "PHASE_WBC_SUSPENSION_CURSOR_KEY",
    "PHASE_WBC_STATE_KEY",
    "activate_phase_wbc",
    "clear_phase_wbc_suspension",
    "complete_phase_wbc",
    "fail_phase_wbc",
    "phase_wbc_attempt_id",
    "phase_wbc_required",
    "phase_wbc_suspension_state",
    "phase_wbc_state",
    "query_phase_wbc_cursor",
    "query_phase_wbc_events",
    "register_phase_wbc_writers",
    "resume_clarification_phase_wbc_if_present",
    "resume_suspended_phase_wbc",
    "suspend_phase_wbc",
]
