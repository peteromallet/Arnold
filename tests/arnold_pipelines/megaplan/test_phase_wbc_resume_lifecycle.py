from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from arnold.workflow.execution_attempt_ledger import AttemptEventType
from arnold.control.interface import ControlTransition
from arnold_pipelines.megaplan._core import set_active_step
from arnold_pipelines.megaplan.control_interface import apply_transition
from arnold_pipelines.megaplan.custody.controlled_writer_registry import (
    _clear_registry,
)
from arnold_pipelines.megaplan.custody.phase_wbc import (
    PHASE_WBC_SUSPENSIONS_STATE_KEY,
    PHASE_WBC_SUSPENSION_CURSOR_KEY,
    activate_phase_wbc,
    complete_phase_wbc,
    phase_wbc_required,
    phase_wbc_suspension_state,
    query_phase_wbc_cursor,
    query_phase_wbc_events,
    resume_suspended_phase_wbc,
)
from arnold_pipelines.megaplan.custody.wbc_runtime import (
    WbcRuntimeProducerFacade,
)
from arnold_pipelines.megaplan.handlers import override as override_handler
from arnold_pipelines.megaplan.handlers import shared as shared_handlers
from arnold_pipelines.megaplan.outcomes import PrepOutcome
from arnold_pipelines.megaplan.planning.state import (
    STATE_AWAITING_HUMAN,
    STATE_INITIALIZED,
    STATE_PREPPED,
)
from arnold_pipelines.megaplan.planning.control_binding import (
    planning_run_state_view,
)
from arnold_pipelines.megaplan.types import CliError
from arnold_pipelines.megaplan.workers import WorkerResult


@pytest.fixture(autouse=True)
def _reset_writer_registry() -> None:
    _clear_registry()
    yield
    _clear_registry()


def _state(project_dir: Path, *, current_state: str = STATE_INITIALIZED) -> dict:
    return {
        "name": "demo",
        "current_state": current_state,
        "iteration": 0,
        "config": {"project_dir": str(project_dir), "profile": "partnered-5"},
        "meta": {},
        "history": [],
        "sessions": {},
        "plan_versions": [],
        "last_gate": {},
    }


def _worker() -> WorkerResult:
    return WorkerResult(
        payload={},
        raw_output="",
        duration_ms=1,
        cost_usd=0.0,
        session_id="session-1",
        worker_channel="test",
        auth_channel="test",
        auth_metadata={"actor": "test"},
        prompt_tokens=1,
        completion_tokens=1,
        total_tokens=2,
    )


def _suspend_prep(
    *,
    project_dir: Path,
    plan_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[dict, str]:
    monkeypatch.setenv("MEGAPLAN_AUDIT_DIR", str(plan_dir / "audit"))
    monkeypatch.setattr(shared_handlers, "_emit_receipt", lambda **_kwargs: None)
    state = _state(project_dir)
    run_id = set_active_step(state, step="prep", agent="prep", mode="test")
    metadata = activate_phase_wbc(
        state=state,
        plan_dir=plan_dir,
        step="prep",
        agent="prep",
    )
    assert metadata is not None
    invocation_id = str(metadata["invocation_id"])
    state["current_state"] = STATE_AWAITING_HUMAN
    state["clarification"] = {
        "source": "prep",
        "questions": ["Which target should be used?"],
    }
    (plan_dir / "prep.json").write_text("{}", encoding="utf-8")

    response = shared_handlers._finish_step(
        plan_dir,
        state,
        argparse.Namespace(plan="demo"),
        step="prep",
        worker=_worker(),
        agent="prep",
        mode="test",
        refreshed=False,
        summary="awaiting clarification",
        artifacts=["prep.json"],
        output_file="prep.json",
        artifact_hash="prep-hash",
        next_step="override resume-clarify",
        response_fields={"prep_outcome": PrepOutcome.AWAITING_HUMAN},
        run_id=run_id,
    )

    assert response["state"] == STATE_AWAITING_HUMAN
    return state, invocation_id


def test_revise_is_an_existing_phase_wbc_surface() -> None:
    assert phase_wbc_required("revise")


def test_revise_worker_failure_emits_started_then_failed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_dir = tmp_path / "project"
    plan_dir = tmp_path / "plan"
    project_dir.mkdir()
    plan_dir.mkdir()
    state = _state(project_dir, current_state="critiqued")

    def fail_worker(*_args, **_kwargs):
        raise CliError("worker_failed", "revise failed")

    monkeypatch.setattr(shared_handlers.worker_module, "run_step_with_worker", fail_worker)

    with pytest.raises(CliError, match="revise failed"):
        shared_handlers._run_worker(
            "revise",
            state,
            plan_dir,
            argparse.Namespace(),
            root=project_dir,
            resolved=("codex", "test", False, None),
        )

    invocation_id = str(state["meta"]["current_invocation_id"])
    events = query_phase_wbc_events(
        plan_dir,
        step="revise",
        invocation_id=invocation_id,
    )
    assert [event.event_type for event in events] == [
        AttemptEventType.STARTED,
        AttemptEventType.FAILED,
    ]
    assert events[-1].payload["failure_stage"] == "phase_handler"


@pytest.mark.parametrize(
    "step",
    [
        "tiebreaker_researcher",
        "tiebreaker_challenger",
        "tiebreaker_synthesis",
        "tiebreaker_decision",
    ],
)
def test_canonical_tiebreaker_phase_queries_round_trip_lifecycle(
    tmp_path: Path,
    step: str,
) -> None:
    project_dir = tmp_path / "project"
    plan_dir = tmp_path / "plan"
    project_dir.mkdir()
    plan_dir.mkdir()
    state = _state(project_dir, current_state="tiebreaker_ready")
    set_active_step(state, step=step, agent="tiebreaker-bridge", mode="bridge")
    metadata = activate_phase_wbc(
        state=state,
        plan_dir=plan_dir,
        step=step,
        agent="tiebreaker-bridge",
    )
    assert metadata is not None

    complete_phase_wbc(
        state=state,
        plan_dir=plan_dir,
        step=step,
        agent="tiebreaker-bridge",
        payload={"phase": step, "status": "completed"},
    )

    events = query_phase_wbc_events(
        plan_dir,
        step=step,
        invocation_id=str(metadata["invocation_id"]),
    )
    assert [event.event_type for event in events] == [
        AttemptEventType.STARTED,
        AttemptEventType.COMPLETED,
    ]
    assert events[-1].payload["__wbc_runtime__"]["promotion_mode"] == "action_off"


def test_clarification_suspend_resume_has_checkpoint_cursor_and_reentry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_dir = tmp_path / "project"
    plan_dir = tmp_path / "plan"
    project_dir.mkdir()
    plan_dir.mkdir()
    state, invocation_id = _suspend_prep(
        project_dir=project_dir,
        plan_dir=plan_dir,
        monkeypatch=monkeypatch,
    )

    suspended = query_phase_wbc_events(
        plan_dir,
        step="prep",
        invocation_id=invocation_id,
    )
    cursor = query_phase_wbc_cursor(
        plan_dir,
        step="prep",
        invocation_id=invocation_id,
    )
    assert [event.event_type for event in suspended] == [
        AttemptEventType.STARTED,
        AttemptEventType.SUSPENDED,
    ]
    assert cursor is not None
    assert cursor.cursor_key == PHASE_WBC_SUSPENSION_CURSOR_KEY
    assert cursor.last_sequence == 2
    checkpoint = suspended[-1].payload["checkpoint"]
    assert checkpoint["schema_version"] == (
        "arnold.workflow.ledger.checkpoint_payload.v1"
    )
    assert checkpoint["inline_data"]["cursor"]["resume_action"] == (
        "override:resume-clarify"
    )
    assert checkpoint["content_digest"] == cursor.last_position
    assert phase_wbc_suspension_state(state, step="prep") is not None

    state["meta"]["notes"] = [
        {"source": "user", "timestamp": "2026-07-31T00:00:00Z", "text": "Use staging."}
    ]
    response = override_handler._override_resume_clarify(
        project_dir,
        plan_dir,
        state,
        argparse.Namespace(actor="operator"),
    )

    events = query_phase_wbc_events(
        plan_dir,
        step="prep",
        invocation_id=invocation_id,
    )
    assert [event.event_type for event in events] == [
        AttemptEventType.STARTED,
        AttemptEventType.SUSPENDED,
        AttemptEventType.RESUMED,
        AttemptEventType.COMPLETED,
    ]
    reentry_invocation_id = events[2].payload["reentry_invocation_id"]
    assert reentry_invocation_id != invocation_id
    assert events[2].identity.invocation_id == invocation_id
    assert events[3].payload["reentry_invocation_id"] == reentry_invocation_id
    assert response["phase_wbc_reentry_invocation_id"] == reentry_invocation_id
    assert state["current_state"] == STATE_PREPPED
    assert phase_wbc_suspension_state(state, step="prep") is None
    terminal_cursor = query_phase_wbc_cursor(
        plan_dir,
        step="prep",
        invocation_id=invocation_id,
    )
    assert terminal_cursor is not None
    assert terminal_cursor.last_sequence == 4
    assert terminal_cursor.last_position == "completed"


def test_clarification_resume_fails_closed_on_cursor_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_dir = tmp_path / "project"
    plan_dir = tmp_path / "plan"
    project_dir.mkdir()
    plan_dir.mkdir()
    state, invocation_id = _suspend_prep(
        project_dir=project_dir,
        plan_dir=plan_dir,
        monkeypatch=monkeypatch,
    )
    from arnold.workflow.attempt_ledger_store import SqliteAttemptLedgerStore
    from arnold_pipelines.megaplan.custody.phase_wbc import (
        PHASE_WBC_LEDGER_FILENAME,
        phase_wbc_attempt_id,
    )

    attempt_id = phase_wbc_attempt_id(
        plan_dir,
        step="prep",
        invocation_id=invocation_id,
    )
    SqliteAttemptLedgerStore(
        plan_dir / PHASE_WBC_LEDGER_FILENAME
    ).update_source_cursor(
        attempt_id,
        2,
        PHASE_WBC_SUSPENSION_CURSOR_KEY,
        "sha256:" + ("0" * 64),
    )

    with pytest.raises(RuntimeError, match="suspension cursor mismatch"):
        resume_suspended_phase_wbc(
            state=state,
            plan_dir=plan_dir,
            step="prep",
            agent="operator",
        )

    assert state["current_state"] == STATE_AWAITING_HUMAN
    events = query_phase_wbc_events(
        plan_dir,
        step="prep",
        invocation_id=invocation_id,
    )
    assert [event.event_type for event in events] == [
        AttemptEventType.STARTED,
        AttemptEventType.SUSPENDED,
    ]


def test_clarification_resume_continues_after_partial_resumed_append(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_dir = tmp_path / "project"
    plan_dir = tmp_path / "plan"
    project_dir.mkdir()
    plan_dir.mkdir()
    state, invocation_id = _suspend_prep(
        project_dir=project_dir,
        plan_dir=plan_dir,
        monkeypatch=monkeypatch,
    )
    original_complete = WbcRuntimeProducerFacade.complete_attempt
    failed_once = False

    def fail_first_complete(self, **kwargs):
        nonlocal failed_once
        if not failed_once:
            failed_once = True
            raise RuntimeError("simulated crash after RESUMED")
        return original_complete(self, **kwargs)

    monkeypatch.setattr(
        WbcRuntimeProducerFacade,
        "complete_attempt",
        fail_first_complete,
    )
    with pytest.raises(RuntimeError, match="simulated crash"):
        resume_suspended_phase_wbc(
            state=state,
            plan_dir=plan_dir,
            step="prep",
            agent="operator",
        )

    partial_events = query_phase_wbc_events(
        plan_dir,
        step="prep",
        invocation_id=invocation_id,
    )
    assert [event.event_type for event in partial_events] == [
        AttemptEventType.STARTED,
        AttemptEventType.SUSPENDED,
        AttemptEventType.RESUMED,
    ]

    reentry_invocation_id = resume_suspended_phase_wbc(
        state=state,
        plan_dir=plan_dir,
        step="prep",
        agent="operator",
    )

    completed_events = query_phase_wbc_events(
        plan_dir,
        step="prep",
        invocation_id=invocation_id,
    )
    assert [event.event_type for event in completed_events] == [
        AttemptEventType.STARTED,
        AttemptEventType.SUSPENDED,
        AttemptEventType.RESUMED,
        AttemptEventType.COMPLETED,
    ]
    assert completed_events[2].payload["reentry_invocation_id"] == (
        reentry_invocation_id
    )
    assert phase_wbc_suspension_state(state, step="prep") is None


def test_clarification_resume_reconciles_completed_ledger_after_state_save_loss(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_dir = tmp_path / "project"
    plan_dir = tmp_path / "plan"
    project_dir.mkdir()
    plan_dir.mkdir()
    state, invocation_id = _suspend_prep(
        project_dir=project_dir,
        plan_dir=plan_dir,
        monkeypatch=monkeypatch,
    )
    suspended_metadata = phase_wbc_suspension_state(state, step="prep")
    assert suspended_metadata is not None
    first_reentry = resume_suspended_phase_wbc(
        state=state,
        plan_dir=plan_dir,
        step="prep",
        agent="operator",
    )

    # Simulate a crash after the ledger and cursor committed but before the
    # cleared suspension projection reached state.json.
    state["meta"][PHASE_WBC_SUSPENSIONS_STATE_KEY] = {
        "prep": suspended_metadata,
    }
    second_reentry = resume_suspended_phase_wbc(
        state=state,
        plan_dir=plan_dir,
        step="prep",
        agent="operator",
    )

    assert second_reentry == first_reentry
    events = query_phase_wbc_events(
        plan_dir,
        step="prep",
        invocation_id=invocation_id,
    )
    assert [event.event_type for event in events] == [
        AttemptEventType.STARTED,
        AttemptEventType.SUSPENDED,
        AttemptEventType.RESUMED,
        AttemptEventType.COMPLETED,
    ]
    assert phase_wbc_suspension_state(state, step="prep") is None


def test_control_routed_clarification_resume_commits_wbc_before_state_transition(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_dir = tmp_path / "project"
    plan_dir = tmp_path / "plan"
    project_dir.mkdir()
    plan_dir.mkdir()
    state, invocation_id = _suspend_prep(
        project_dir=project_dir,
        plan_dir=plan_dir,
        monkeypatch=monkeypatch,
    )
    state["meta"]["notes"] = [
        {"source": "user", "timestamp": "2026-07-31T00:00:00Z", "text": "Use staging."}
    ]
    (plan_dir / "state.json").write_text(
        json.dumps(state),
        encoding="utf-8",
    )

    result = apply_transition(
        planning_run_state_view(state),
        ControlTransition(
            op="override",
            target_id="resume-clarify",
            payload={},
        ),
        "megaplan",
        plan_dir=plan_dir,
    )

    assert result.accepted is True
    reentry_invocation_id = result.artifacts["phase_wbc_reentry_invocation_id"]
    persisted_state = json.loads(
        (plan_dir / "state.json").read_text(encoding="utf-8")
    )
    assert persisted_state["current_state"] == STATE_PREPPED
    assert phase_wbc_suspension_state(persisted_state, step="prep") is None
    events = query_phase_wbc_events(
        plan_dir,
        step="prep",
        invocation_id=invocation_id,
    )
    assert [event.event_type for event in events] == [
        AttemptEventType.STARTED,
        AttemptEventType.SUSPENDED,
        AttemptEventType.RESUMED,
        AttemptEventType.COMPLETED,
    ]
    assert events[2].payload["reentry_invocation_id"] == reentry_invocation_id
