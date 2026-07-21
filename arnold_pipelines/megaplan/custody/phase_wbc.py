"""Phase-scoped WBC lifecycle evidence for front-half and tiebreaker producers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import uuid
from typing import Any, Mapping

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

from .controlled_writer_registry import Cohort, ControlledWriter, register_writer
from .wbc_runtime import ExactSourceRecord, ImmutableAttemptArtifacts, PromotionMode, WbcRuntimeProducerFacade


PHASE_WBC_STATE_KEY = "_phase_wbc"
PHASE_WBC_LEDGER_FILENAME = ".phase_wbc_attempts.sqlite3"


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

    attempt_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{plan_dir.resolve()}::{step}::{invocation_id}"))
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
    ledger_path = plan_dir / PHASE_WBC_LEDGER_FILENAME
    return WbcRuntimeProducerFacade(
        SqliteAttemptLedgerStore(ledger_path),
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
    "PHASE_WBC_STATE_KEY",
    "activate_phase_wbc",
    "complete_phase_wbc",
    "fail_phase_wbc",
    "phase_wbc_required",
    "phase_wbc_state",
    "register_phase_wbc_writers",
]
