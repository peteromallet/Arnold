from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from arnold_pipelines.megaplan._core.state import load_plan_from_dir, save_state_merge_meta
from arnold_pipelines.megaplan.handlers import shared
from arnold_pipelines.megaplan.orchestration.phase_result import PhaseResult
from arnold_pipelines.megaplan.workers import WorkerResult
from arnold_pipelines.megaplan.workflows.boundary_contracts import gate_to_revise, plan_to_critique


def _write_plan_state(plan_dir: Path, state: dict[str, object]) -> None:
    plan_dir.mkdir(parents=True)
    (plan_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")


def _finish_state(tmp_path: Path, *, current_state: str, iteration: int = 1) -> dict[str, object]:
    return {
        "name": "boundary-plan",
        "current_state": current_state,
        "iteration": iteration,
        "config": {"project_dir": str(tmp_path)},
        "sessions": {},
        "plan_versions": [],
        "history": [],
        "meta": {"current_invocation_id": "inv-123"},
        "last_gate": {},
        "latest_failure": None,
    }


def _worker_result(**overrides: object) -> WorkerResult:
    payload = dict(overrides.pop("payload", {}))
    return WorkerResult(
        payload=payload,
        raw_output=str(overrides.pop("raw_output", "")),
        duration_ms=int(overrides.pop("duration_ms", 1)),
        cost_usd=float(overrides.pop("cost_usd", 0.0)),
        session_id=overrides.pop("session_id", None),
        worker_channel=overrides.pop("worker_channel", None),
        auth_channel=overrides.pop("auth_channel", None),
        auth_metadata=overrides.pop("auth_metadata", None),
        prompt_tokens=int(overrides.pop("prompt_tokens", 0)),
        completion_tokens=int(overrides.pop("completion_tokens", 0)),
        total_tokens=int(overrides.pop("total_tokens", 0)),
        **overrides,
    )


def test_load_plan_reconciles_satisfied_user_action_gate(tmp_path: Path) -> None:
    plan_dir = tmp_path / ".megaplan" / "plans" / "blocked-plan"
    _write_plan_state(
        plan_dir,
        {
            "name": "blocked-plan",
            "current_state": "awaiting_human",
            "iteration": 1,
            "config": {},
            "sessions": {},
            "plan_versions": [],
            "history": [],
            "meta": {},
            "last_gate": {},
            "latest_failure": {"kind": "phase_failed"},
            "resume_cursor": {"phase": "execute"},
        },
    )
    (plan_dir / "finalize.json").write_text(
        '{"user_actions":[{"id":"ua-1","phase":"before_execute"}]}',
        encoding="utf-8",
    )
    (plan_dir / "user_action_resolutions.json").write_text(
        (
            '{"ua-1":{"action_id":"ua-1","state":"satisfied",'
            '"created_at":"2026-06-29T00:00:00Z","created_by":"test"}}'
        ),
        encoding="utf-8",
    )

    _, state = load_plan_from_dir(plan_dir)
    persisted = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))

    assert state["current_state"] == "finalized"
    assert persisted["current_state"] == "finalized"
    assert persisted["latest_failure"] is None
    assert "resume_cursor" not in persisted


def test_load_plan_keeps_awaiting_human_when_user_actions_unsatisfied(tmp_path: Path) -> None:
    plan_dir = tmp_path / ".megaplan" / "plans" / "blocked-plan"
    _write_plan_state(
        plan_dir,
        {
            "name": "blocked-plan",
            "current_state": "awaiting_human",
            "iteration": 1,
            "config": {},
            "sessions": {},
            "plan_versions": [],
            "history": [],
            "meta": {},
            "last_gate": {},
            "latest_failure": {"kind": "phase_failed"},
            "resume_cursor": {"phase": "execute"},
        },
    )
    (plan_dir / "finalize.json").write_text(
        '{"user_actions":[{"id":"ua-1","phase":"before_execute"}]}',
        encoding="utf-8",
    )

    _, state = load_plan_from_dir(plan_dir)

    assert state["current_state"] == "awaiting_human"
    assert state["latest_failure"] == {"kind": "phase_failed"}


def test_load_plan_reconciles_completed_review_to_done(tmp_path: Path) -> None:
    plan_dir = tmp_path / ".megaplan" / "plans" / "reviewed-plan"
    _write_plan_state(
        plan_dir,
        {
            "name": "reviewed-plan",
            "current_state": "executed",
            "iteration": 2,
            "config": {},
            "sessions": {},
            "plan_versions": [],
            "history": [],
            "meta": {},
            "last_gate": {},
            "latest_failure": {"kind": "control_binding_mismatch"},
            "resume_cursor": {"phase": "review", "retry_strategy": "repair_control_binding"},
        },
    )
    (plan_dir / "review.json").write_text(
        json.dumps(
            {
                "review_verdict": "approved",
                "outcome": {
                    "result": "success",
                    "review_verdict": "approved",
                    "state": "done",
                    "next_step": None,
                },
                "issues": [],
                "rework_items": [],
                "criteria": [],
            }
        ),
        encoding="utf-8",
    )

    _, state = load_plan_from_dir(plan_dir)
    persisted = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))

    assert state["current_state"] == "done"
    assert persisted["current_state"] == "done"
    assert persisted["latest_failure"] is None
    assert "resume_cursor" not in persisted


def test_load_plan_reconciles_failed_no_next_step_after_finalize(tmp_path: Path) -> None:
    plan_dir = tmp_path / ".megaplan" / "plans" / "finalized-plan"
    _write_plan_state(
        plan_dir,
        {
            "name": "finalized-plan",
            "current_state": "failed",
            "iteration": 6,
            "config": {},
            "sessions": {},
            "plan_versions": [],
            "history": [{"step": "finalize", "result": "success"}],
            "meta": {},
            "last_gate": {},
            "latest_failure": {"kind": "no_next_step"},
            "resume_cursor": {"phase": "status", "retry_strategy": "repair_state"},
        },
    )
    (plan_dir / "phase_result.json").write_text(
        json.dumps(
            PhaseResult(
                phase="finalize",
                invocation_id="test-finalize-success",
                exit_kind="success",
                artifacts_written=("finalize.json",),
            ).to_dict()
        ),
        encoding="utf-8",
    )

    _, state = load_plan_from_dir(plan_dir)
    persisted = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))

    assert state["current_state"] == "finalized"
    assert persisted["current_state"] == "finalized"
    assert persisted["latest_failure"] is None
    assert "resume_cursor" not in persisted


def test_load_plan_reconciles_failed_no_next_step_after_blocked_execute(
    tmp_path: Path,
    monkeypatch,
) -> None:
    plan_dir = tmp_path / ".megaplan" / "plans" / "executed-plan"
    _write_plan_state(
        plan_dir,
        {
            "name": "executed-plan",
            "current_state": "failed",
            "iteration": 2,
            "config": {},
            "sessions": {},
            "plan_versions": [],
            "history": [{"step": "execute", "result": "blocked"}],
            "meta": {},
            "last_gate": {},
            "latest_failure": {"kind": "no_next_step"},
            "resume_cursor": {"phase": "status", "retry_strategy": "repair_state"},
        },
    )
    from arnold_pipelines.megaplan import chain as chain_module

    monkeypatch.setattr(
        chain_module,
        "_latest_execution_batch_all_tasks_done",
        lambda _plan_dir: (True, "finalize.json"),
    )

    _, state = load_plan_from_dir(plan_dir)
    persisted = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))

    assert state["current_state"] == "executed"
    assert persisted["current_state"] == "executed"
    assert persisted["latest_failure"] is None
    assert "resume_cursor" not in persisted


def test_load_plan_reconciles_failed_finalize_state_after_failure_marker_clears(
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / ".megaplan" / "plans" / "finalized-plan"
    _write_plan_state(
        plan_dir,
        {
            "name": "finalized-plan",
            "current_state": "failed",
            "iteration": 6,
            "config": {},
            "sessions": {},
            "plan_versions": [],
            "history": [{"step": "finalize", "result": "success"}],
            "meta": {},
            "last_gate": {},
            "latest_failure": None,
            "resume_cursor": {"phase": "status", "retry_strategy": "repair_state"},
        },
    )
    (plan_dir / "phase_result.json").write_text(
        json.dumps(
            PhaseResult(
                phase="finalize",
                invocation_id="test-finalize-success",
                exit_kind="success",
                artifacts_written=("finalize.json",),
            ).to_dict()
        ),
        encoding="utf-8",
    )

    _, state = load_plan_from_dir(plan_dir)
    persisted = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))

    assert state["current_state"] == "finalized"
    assert persisted["current_state"] == "finalized"
    assert persisted["latest_failure"] is None
    assert "resume_cursor" not in persisted


def test_extract_deviations_ignores_gate_warnings() -> None:
    state = {
        "last_gate": {
            "warnings": [
                "Criteria 8 and 10 require runtime observation and subjective human judgment during deployment phases (Steps 9-11).",
            ]
        }
    }

    assert shared._extract_deviations_from_state(state) == ()


def test_save_state_merge_meta_phase_save_advances_state_by_default(tmp_path: Path) -> None:
    plan_dir = tmp_path / ".megaplan" / "plans" / "prep-plan"
    phase_state = {
        "name": "prep-plan",
        "current_state": "prepped",
        "iteration": 0,
        "config": {},
        "sessions": {},
        "plan_versions": [],
        "history": [{"step": "prep", "result": "success"}],
        "meta": {
            "overrides": [
                {"action": "phase-save", "timestamp": "2026-07-03T18:03:00Z"}
            ]
        },
        "last_gate": {},
        "latest_failure": None,
    }
    _write_plan_state(
        plan_dir,
        {
            "name": "prep-plan",
            "current_state": "initialized",
            "iteration": 0,
            "config": {},
            "sessions": {},
            "plan_versions": [],
            "history": [{"step": "init", "result": "success"}],
            "meta": {
                "notes": [{"timestamp": "2026-07-03T18:02:58Z", "note": "operator note"}]
            },
            "last_gate": {},
            "latest_failure": None,
        },
    )

    save_state_merge_meta(plan_dir, phase_state)

    persisted = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    assert persisted["current_state"] == "prepped"
    assert persisted["history"] == [{"step": "prep", "result": "success"}]
    assert persisted["meta"]["notes"][0]["note"] == "operator note"
    assert [item["action"] for item in persisted["meta"]["overrides"]] == ["phase-save"]


def test_save_state_merge_meta_can_preserve_newer_disk_transition(tmp_path: Path) -> None:
    plan_dir = tmp_path / ".megaplan" / "plans" / "clarified-plan"
    stale_note_state = {
        "name": "clarified-plan",
        "current_state": "awaiting_human_verify",
        "clarification": {"source": "prep", "questions": ["q1"]},
        "iteration": 1,
        "config": {},
        "sessions": {},
        "plan_versions": [],
        "history": [],
        "meta": {
            "notes": [{"timestamp": "2026-07-03T18:02:58Z", "note": "answer", "source": "repair"}],
            "overrides": [
                {
                    "action": "add-note",
                    "timestamp": "2026-07-03T18:02:58Z",
                    "note": "answer",
                    "source": "repair",
                }
            ],
        },
        "last_gate": {},
        "latest_failure": None,
    }
    _write_plan_state(
        plan_dir,
        {
            "name": "clarified-plan",
            "current_state": "prepped",
            "iteration": 1,
            "config": {},
            "sessions": {},
            "plan_versions": [],
            "history": [],
            "meta": {"overrides": [{"action": "resume-clarify", "timestamp": "2026-07-03T18:02:58Z"}]},
            "last_gate": {},
            "latest_failure": None,
        },
    )

    save_state_merge_meta(plan_dir, stale_note_state, preserve_disk_non_meta=True)

    persisted = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    assert persisted["current_state"] == "prepped"
    assert "clarification" not in persisted
    assert [item["action"] for item in persisted["meta"]["overrides"]] == [
        "resume-clarify",
        "add-note",
    ]
    assert persisted["meta"]["notes"][0]["note"] == "answer"


def test_finish_step_clears_latest_failure_on_success(
    tmp_path: Path,
    monkeypatch,
) -> None:
    plan_dir = tmp_path / ".megaplan" / "plans" / "retry-plan"
    plan_dir.mkdir(parents=True)
    state = {
        "name": "retry-plan",
        "current_state": "finalized",
        "iteration": 1,
        "config": {"project_dir": str(tmp_path)},
        "sessions": {},
        "plan_versions": [],
        "history": [],
        "meta": {},
        "last_gate": {},
        "latest_failure": {"kind": "phase_failed"},
        "resume_cursor": {"phase": "finalize"},
    }

    monkeypatch.setattr(shared, "_emit_receipt", lambda **_kwargs: None)
    monkeypatch.setattr(shared, "_emit_phase_result", lambda **_kwargs: None)

    shared._finish_step(
        plan_dir,
        state,
        SimpleNamespace(),
        step="finalize",
        worker=WorkerResult(payload={}, raw_output="", duration_ms=1, cost_usd=0.0),
        agent="codex",
        mode="ephemeral",
        refreshed=False,
        summary="ok",
        artifacts=["finalize.json"],
        output_file="finalize.json",
        artifact_hash="sha256:test",
        next_step="execute",
    )

    persisted = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    assert persisted["latest_failure"] is None
    assert "resume_cursor" not in persisted


def test_emit_boundary_receipt_builds_plan_receipt_from_finish_context(
    tmp_path: Path,
    monkeypatch,
) -> None:
    plan_dir = tmp_path / ".megaplan" / "plans" / "boundary-plan"
    plan_dir.mkdir(parents=True)
    state = _finish_state(tmp_path, current_state="planned", iteration=2)
    state["history"] = [
        {
            "step": "plan",
            "result": "success",
            "timestamp": "2026-07-06T06:30:00Z",
            "output_file": "plan_v2.md",
        }
    ]
    state["sessions"] = {
        "plan:codex": {
            "id": "session-plan-1",
            "worker_channel": "codex_cli",
            "auth_channel": "local",
        }
    }

    captured: list[object] = []
    monkeypatch.setattr(
        shared,
        "write_boundary_receipt",
        lambda plan_dir, receipt, project_dir=None: captured.append(receipt),
    )

    shared._emit_boundary_receipt(
        plan_dir=plan_dir,
        state=state,
        step="plan",
        worker=_worker_result(session_id="session-plan-1", worker_channel="codex_cli", auth_channel="local"),
        agent="codex",
        mode="ephemeral",
        artifacts=["plan_v2.md", "plan_v2.meta.json"],
        output_file="plan_v2.md",
        artifact_hash="sha256:plan",
        response={"next_step": "critique"},
    )

    assert len(captured) == 1
    receipt = captured[0]
    assert receipt.boundary_id == plan_to_critique.boundary_id
    assert receipt.row_id == plan_to_critique.row_id
    assert receipt.invocation_id == "inv-123"
    assert receipt.history_ref == plan_to_critique.expected_history_entry
    assert receipt.phase_result_ref == "phase_result.json"
    assert receipt.state_observation["current_phase"] == "plan"
    assert receipt.state_observation["current_state"] == "planned"
    assert receipt.state_observation["next_step"] == "critique"
    assert "plan_v2.md" in receipt.artifact_refs
    assert "phase_result.json" in receipt.artifact_refs


def test_emit_boundary_receipt_only_emits_gate_boundary_for_revise_routes(
    tmp_path: Path,
    monkeypatch,
) -> None:
    plan_dir = tmp_path / ".megaplan" / "plans" / "gate-plan"
    plan_dir.mkdir(parents=True)
    (plan_dir / "gate.json").write_text("{}", encoding="utf-8")
    (plan_dir / "gate_carry.json").write_text("{}", encoding="utf-8")

    state = _finish_state(tmp_path, current_state="critiqued", iteration=3)
    state["history"] = [{"step": "gate", "result": "success", "timestamp": "2026-07-06T06:31:00Z"}]

    captured: list[object] = []
    monkeypatch.setattr(
        shared,
        "write_boundary_receipt",
        lambda plan_dir, receipt, project_dir=None: captured.append(receipt),
    )

    worker = _worker_result(
        session_id="session-gate-1",
        worker_channel="codex_cli",
        auth_channel="review_board",
        auth_metadata={"actor": "gatekeeper", "role": "reviewer"},
    )

    shared._emit_boundary_receipt(
        plan_dir=plan_dir,
        state=state,
        step="gate",
        worker=worker,
        agent="codex",
        mode="ephemeral",
        artifacts=["gate.json", "gate_carry.json"],
        output_file="gate.json",
        artifact_hash="sha256:gate",
        response={"next_step": "finalize", "recommendation": "PROCEED", "passed": True},
    )

    assert captured == []

    shared._emit_boundary_receipt(
        plan_dir=plan_dir,
        state=state,
        step="gate",
        worker=worker,
        agent="codex",
        mode="ephemeral",
        artifacts=["gate.json", "gate_carry.json"],
        output_file="gate.json",
        artifact_hash="sha256:gate",
        response={
            "next_step": "revise",
            "recommendation": "ITERATE",
            "passed": False,
            "rationale": "Needs another pass.",
            "warnings": ["flag remains open"],
            "settled_decisions": [{"id": "SD4", "decision": "iterate"}],
            "debt_payload": {"debt_entries_added": 0},
        },
    )

    assert len(captured) == 1
    receipt = captured[0]
    assert receipt.boundary_id == gate_to_revise.boundary_id
    assert len(receipt.authority_records) == 1
    authority = receipt.authority_records[0]
    assert authority.actor == "gatekeeper"
    assert authority.role == "reviewer"
    assert authority.decision == "ITERATE"
    assert authority.scope == gate_to_revise.boundary_id
    assert "gate.json" in authority.evidence_refs
    assert authority.details["passed"] is False
    assert authority.details["debt_entries_added"] == 0


def test_finish_step_boundary_receipt_failure_preserves_route_and_state(
    tmp_path: Path,
    monkeypatch,
) -> None:
    plan_dir = tmp_path / ".megaplan" / "plans" / "route-plan"
    plan_dir.mkdir(parents=True)
    state = _finish_state(tmp_path, current_state="planned", iteration=2)
    state["latest_failure"] = {"kind": "phase_failed"}

    call_order: list[str] = []

    monkeypatch.setattr(shared, "_emit_receipt", lambda **_kwargs: call_order.append("step_receipt"))
    monkeypatch.setattr(shared, "_emit_phase_result", lambda **_kwargs: call_order.append("phase_result"))

    def _boom(*args, **kwargs) -> None:
        call_order.append("boundary_receipt")
        raise RuntimeError("boom")

    monkeypatch.setattr(shared, "write_boundary_receipt", _boom)

    response = shared._finish_step(
        plan_dir,
        state,
        SimpleNamespace(),
        step="plan",
        worker=_worker_result(session_id="session-plan-2", worker_channel="codex_cli"),
        agent="codex",
        mode="ephemeral",
        refreshed=False,
        summary="ok",
        artifacts=["plan_v2.md", "plan_v2.meta.json"],
        output_file="plan_v2.md",
        artifact_hash="sha256:plan",
        next_step="critique",
    )

    assert response["next_step"] == "critique"
    assert state["current_state"] == "planned"
    assert state["latest_failure"] is None
    assert state["history"][-1]["step"] == "plan"
    assert call_order == ["step_receipt", "phase_result", "boundary_receipt"]
