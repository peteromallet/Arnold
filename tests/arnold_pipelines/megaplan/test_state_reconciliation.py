from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from arnold_pipelines.megaplan._core.state import load_plan_from_dir, save_state_merge_meta
from arnold_pipelines.megaplan.handlers import shared
from arnold_pipelines.megaplan.orchestration.phase_result import PhaseResult
from arnold_pipelines.megaplan.workers import WorkerResult


def _write_plan_state(plan_dir: Path, state: dict[str, object]) -> None:
    plan_dir.mkdir(parents=True)
    (plan_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")


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
