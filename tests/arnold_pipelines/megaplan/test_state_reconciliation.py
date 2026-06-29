from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from arnold_pipelines.megaplan._core.state import load_plan_from_dir
from arnold_pipelines.megaplan.handlers import shared
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
