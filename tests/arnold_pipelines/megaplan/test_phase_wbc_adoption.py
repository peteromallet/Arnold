from __future__ import annotations

import argparse
import json
from contextlib import contextmanager
from pathlib import Path
import uuid

import pytest

from arnold.workflow.attempt_ledger_store import SqliteAttemptLedgerStore
from arnold.workflow.execution_attempt_ledger import AttemptEventType
from arnold_pipelines.megaplan.handlers import finalize as finalize_handler
from arnold_pipelines.megaplan.handlers import review as review_handler
from arnold_pipelines.megaplan.handlers import shared as shared_handlers
from arnold_pipelines.megaplan.orchestration import tiebreaker_runtime
from arnold_pipelines.megaplan.outcomes import ReviewDecisionResult
from arnold_pipelines.megaplan.planning.state import STATE_TIEBREAKER_READY
from arnold_pipelines.megaplan.workers import WorkerResult
from arnold_pipelines.megaplan._core import set_active_step
from arnold_pipelines.megaplan.custody.controlled_writer_registry import _clear_registry
from arnold_pipelines.megaplan.custody.phase_wbc import (
    PHASE_WBC_LEDGER_FILENAME,
    activate_phase_wbc,
    complete_phase_wbc,
)


@pytest.fixture(autouse=True)
def _reset_writer_registry() -> None:
    _clear_registry()
    yield
    _clear_registry()


def _state(project_dir: Path, *, current_state: str) -> dict[str, object]:
    return {
        "name": "demo",
        "current_state": current_state,
        "iteration": 1,
        "config": {"project_dir": str(project_dir), "profile": "test"},
        "meta": {},
        "history": [],
        "sessions": {},
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
        auth_metadata={"actor": "test", "role": "test"},
    )


def _events(plan_dir: Path, attempt_id: str):
    store = SqliteAttemptLedgerStore(plan_dir / PHASE_WBC_LEDGER_FILENAME)
    return store.read_events(attempt_id)


def test_finish_step_records_started_and_completed_phase_wbc(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project_dir = tmp_path / "project"
    plan_dir = tmp_path / "plan"
    project_dir.mkdir()
    plan_dir.mkdir()
    monkeypatch.setenv("MEGAPLAN_AUDIT_DIR", str(tmp_path / "audit"))
    monkeypatch.setattr(shared_handlers, "_emit_receipt", lambda **_kwargs: None)
    state = _state(project_dir, current_state="planned")
    run_id = set_active_step(state, step="plan", agent="planner", mode="test")
    metadata = activate_phase_wbc(state=state, plan_dir=plan_dir, step="plan", agent="planner")
    assert metadata is not None
    (plan_dir / "plan.md").write_text("# Plan\n", encoding="utf-8")

    response = shared_handlers._finish_step(
        plan_dir,
        state,
        argparse.Namespace(plan="demo"),
        step="plan",
        worker=_worker(),
        agent="planner",
        mode="test",
        refreshed=False,
        summary="planned",
        artifacts=["plan.md"],
        output_file="plan.md",
        artifact_hash="hash-plan",
        next_step="critique",
        run_id=run_id,
    )

    assert response["next_step"] == "critique"
    events = _events(plan_dir, str(metadata["attempt_id"]))
    assert [event.event_type for event in events] == [AttemptEventType.STARTED, AttemptEventType.COMPLETED]
    assert events[1].payload["boundary_receipt_id"] == "plan_to_critique"
    assert (plan_dir / "boundary_receipts" / "plan_to_critique.json").exists()


def test_finish_step_fails_closed_when_required_boundary_receipt_is_not_persisted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_dir = tmp_path / "project"
    plan_dir = tmp_path / "plan"
    project_dir.mkdir()
    plan_dir.mkdir()
    monkeypatch.setenv("MEGAPLAN_AUDIT_DIR", str(tmp_path / "audit"))
    monkeypatch.setattr(shared_handlers, "_emit_receipt", lambda **_kwargs: None)
    monkeypatch.setattr(shared_handlers, "write_boundary_receipt", lambda *args, **kwargs: None)
    state = _state(project_dir, current_state="planned")
    run_id = set_active_step(state, step="plan", agent="planner", mode="test")
    metadata = activate_phase_wbc(state=state, plan_dir=plan_dir, step="plan", agent="planner")
    assert metadata is not None
    (plan_dir / "plan.md").write_text("# Plan\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="was not durably persisted"):
        shared_handlers._finish_step(
            plan_dir,
            state,
            argparse.Namespace(plan="demo"),
            step="plan",
            worker=_worker(),
            agent="planner",
            mode="test",
            refreshed=False,
            summary="planned",
            artifacts=["plan.md"],
            output_file="plan.md",
            artifact_hash="hash-plan",
            next_step="critique",
            run_id=run_id,
        )

    events = _events(plan_dir, str(metadata["attempt_id"]))
    assert [event.event_type for event in events] == [AttemptEventType.STARTED, AttemptEventType.FAILED]
    assert events[1].payload["failure_stage"] == "result_evidence"


@contextmanager
def _locked_plan(plan_dir: Path, state: dict[str, object]):
    yield plan_dir, state


def test_tiebreaker_researcher_emits_canonical_result_receipt_and_phase_wbc(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "root"
    project_dir = tmp_path / "project"
    plan_dir = tmp_path / "plan"
    root.mkdir()
    project_dir.mkdir()
    plan_dir.mkdir()
    monkeypatch.setenv("MEGAPLAN_AUDIT_DIR", str(tmp_path / "audit"))
    state = _state(project_dir, current_state=STATE_TIEBREAKER_READY)
    (plan_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
    (plan_dir / "gate.json").write_text(
        json.dumps(
            {
                "tiebreaker_question": "Which plan is safer?",
                "tiebreaker_flag_ids": ["F1"],
                "tiebreaker_fuzzy_group_id": "grp-1",
            }
        ),
        encoding="utf-8",
    )
    (plan_dir / "tiebreaker_researcher.json").write_text(
        json.dumps({"recommendation": "A", "evidence": ["r"]}),
        encoding="utf-8",
    )
    (plan_dir / "tiebreaker_challenger.json").write_text(
        json.dumps({"recommendation": "B", "evidence": ["c"]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(tiebreaker_runtime, "load_plan_locked", lambda *_args, **_kwargs: _locked_plan(plan_dir, state))

    response = tiebreaker_runtime.handle_tiebreaker_run(
        root,
        argparse.Namespace(plan="demo", node_id="tiebreaker_researcher", agent=None, hermes=None, phase_model=[], profile=None, fresh=False, persist=False, ephemeral=False),
    )

    assert response["step"] == "tiebreaker_researcher"
    assert "next_step" not in response
    assert (plan_dir / "research_findings.json").exists()
    assert (plan_dir / "phase_result.json").exists()
    assert (plan_dir / "boundary_receipts" / "tiebreaker_researcher_to_challenger.json").exists()
    store = SqliteAttemptLedgerStore(plan_dir / PHASE_WBC_LEDGER_FILENAME)
    invocation_id = str(state["meta"]["current_invocation_id"])
    attempt_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{plan_dir.resolve()}::tiebreaker_researcher::{invocation_id}"))
    events = store.read_events(attempt_id)
    assert [event.event_type for event in events] == [AttemptEventType.STARTED, AttemptEventType.COMPLETED]
    assert events[1].payload["boundary_receipt_id"] == "tiebreaker_researcher_to_challenger"


def test_finish_step_records_finalize_and_projection_phase_wbc(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_dir = tmp_path / "project"
    plan_dir = tmp_path / "plan"
    project_dir.mkdir()
    plan_dir.mkdir()
    monkeypatch.setenv("MEGAPLAN_AUDIT_DIR", str(tmp_path / "audit"))
    monkeypatch.setattr(shared_handlers, "_emit_receipt", lambda **_kwargs: None)
    state = _state(project_dir, current_state="gated")
    run_id = set_active_step(state, step="finalize", agent="finalizer", mode="test")
    metadata = activate_phase_wbc(state=state, plan_dir=plan_dir, step="finalize", agent="finalizer")
    assert metadata is not None
    for name, body in (
        ("contract.json", "{}"),
        ("final.md", "# Final\n"),
        ("finalize.json", '{"tasks": []}'),
    ):
        (plan_dir / name).write_text(body, encoding="utf-8")

    response = shared_handlers._finish_step(
        plan_dir,
        state,
        argparse.Namespace(plan="demo"),
        step="finalize",
        worker=_worker(),
        agent="finalizer",
        mode="test",
        refreshed=False,
        summary="finalized",
        artifacts=["contract.json", "final.md", "finalize.json"],
        output_file="finalize.json",
        artifact_hash="hash-finalize",
        next_step="execute",
        run_id=run_id,
        extra_boundary_ids=("final_projection",),
    )

    assert response["next_step"] == "execute"
    events = _events(plan_dir, str(metadata["attempt_id"]))
    assert [event.event_type for event in events] == [AttemptEventType.STARTED, AttemptEventType.COMPLETED]
    assert events[1].payload["boundary_receipt_id"] == "finalize_artifacts"
    assert events[1].payload["boundary_receipt_ids"] == ["finalize_artifacts", "final_projection"]
    assert (plan_dir / "boundary_receipts" / "finalize_artifacts.json").exists()
    assert (plan_dir / "boundary_receipts" / "final_projection.json").exists()


def test_review_rework_receipt_joins_one_phase_attempt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_dir = tmp_path / "project"
    plan_dir = tmp_path / "plan"
    project_dir.mkdir()
    plan_dir.mkdir()
    monkeypatch.setenv("MEGAPLAN_AUDIT_DIR", str(tmp_path / "audit"))
    state = _state(project_dir, current_state="executed")
    set_active_step(state, step="review", agent="reviewer", mode="test")
    metadata = activate_phase_wbc(state=state, plan_dir=plan_dir, step="review", agent="reviewer")
    assert metadata is not None
    for name, body in (
        ("review.json", "{}"),
        ("finalize.json", '{"tasks": []}'),
        ("final.md", "# Final\n"),
    ):
        (plan_dir / name).write_text(body, encoding="utf-8")
    response = {
        "success": False,
        "step": "review",
        "summary": "needs rework",
        "artifacts": ["review.json", "finalize.json", "final.md"],
        "monitor_hint": {},
        "next_step": "execute",
        "route_signal": "rework",
        "state": "finalized",
        "issues": [],
        "rework_items": [],
    }

    emitted_ids = review_handler._emit_review_route_boundary_receipts(
        plan_dir=plan_dir,
        state=state,
        worker=_worker(),
        agent="reviewer",
        mode="test",
        result=ReviewDecisionResult.NEEDS_REWORK,
        next_state="finalized",
        response=response,
        artifact_hash="hash-review",
        strict=True,
    )

    assert emitted_ids == ("review_rework_effects",)
    complete_phase_wbc(
        state=state,
        plan_dir=plan_dir,
        step="review",
        agent="reviewer",
        payload={
            "phase": "review",
            "status": "completed",
            "phase_result_ref": "phase_result.json",
            "boundary_receipt_id": emitted_ids[0],
            "boundary_receipt_ids": list(emitted_ids),
        },
    )
    events = _events(plan_dir, str(metadata["attempt_id"]))
    assert [event.event_type for event in events] == [AttemptEventType.STARTED, AttemptEventType.COMPLETED]
    assert events[1].payload["boundary_receipt_id"] == "review_rework_effects"
    assert (plan_dir / "boundary_receipts" / "review_rework_effects.json").exists()


def test_finalize_revise_fallback_records_phase_wbc_and_receipt(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    plan_dir = tmp_path / "plan"
    project_dir.mkdir()
    plan_dir.mkdir()
    state = _state(project_dir, current_state="gated")
    set_active_step(state, step="finalize", agent="finalizer", mode="test")
    metadata = activate_phase_wbc(state=state, plan_dir=plan_dir, step="finalize", agent="finalizer")
    assert metadata is not None

    response = finalize_handler._route_finalize_baseline_selection_failure_to_revise(
        plan_dir,
        state,
        argparse.Namespace(plan="demo"),
        _worker(),
        "finalizer",
        "test",
        False,
        finalize_handler.FinalizeBaselineSelectionError(
            {
                "reason": "missing scoped baseline",
                "fallback_reason": "scoped selection unresolved",
            }
        ),
    )

    assert response["next_step"] == "revise"
    assert (plan_dir / "phase_result.json").exists()
    assert (plan_dir / "boundary_receipts" / "finalize_fallback.json").exists()
    events = _events(plan_dir, str(metadata["attempt_id"]))
    assert [event.event_type for event in events] == [AttemptEventType.STARTED, AttemptEventType.COMPLETED]
    assert events[1].payload["boundary_receipt_id"] == "finalize_fallback"
