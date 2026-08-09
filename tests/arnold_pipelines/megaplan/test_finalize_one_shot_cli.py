from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

import arnold_pipelines.megaplan.cli as cli
from arnold_pipelines.megaplan._core import save_state, set_active_step
from arnold_pipelines.megaplan.custody.phase_wbc import (
    PHASE_WBC_LEDGER_FILENAME,
    activate_phase_wbc,
    cancel_active_phase_wbc_attempt,
)
from arnold_pipelines.megaplan.handlers import finalize as finalize_handler
from arnold_pipelines.megaplan.handlers import shared as shared_handlers
from arnold_pipelines.megaplan.prompts import finalize as finalize_prompt
from arnold_pipelines.megaplan.types import CliError
from arnold_pipelines.megaplan.workers import WorkerResult


def _paused_attempt_8(root: Path) -> tuple[Path, dict[str, Any]]:
    project_dir = root / "project"
    project_dir.mkdir()
    plan_dir = root / ".megaplan" / "plans" / "demo"
    plan_dir.mkdir(parents=True)
    state: dict[str, Any] = {
        "name": "demo",
        "current_state": "gated",
        "iteration": 1,
        "config": {
            "project_dir": str(project_dir),
            "profile": "partnered-5-glm",
            "robustness": "full",
            "mode": "doc",
        },
        "meta": {},
        "history": [
            {"step": "finalize", "result": "error", "timestamp": f"t-{index}"}
            for index in range(7)
        ],
        "sessions": {},
    }
    run_id = set_active_step(
        state,
        step="finalize",
        agent="codex",
        mode="persistent",
        model="gpt-5.6-sol",
    )
    assert state["active_step"]["attempt"] == 8
    attempt = activate_phase_wbc(
        state=state,
        plan_dir=plan_dir,
        step="finalize",
        agent="codex",
    )
    assert attempt is not None
    save_state(plan_dir, state)
    cancel_active_phase_wbc_attempt(
        plan_dir=plan_dir,
        step="finalize",
        expected_attempt_id=str(attempt["attempt_id"]),
        expected_invocation_id=str(attempt["invocation_id"]),
        expected_run_id=run_id,
        expected_attempt_ordinal=8,
        agent="operator",
        reason="retire paused attempt 8 before one-shot attempt 9",
    )
    return plan_dir, attempt


def _phase_events(plan_dir: Path) -> list[tuple[str, str]]:
    with sqlite3.connect(plan_dir / PHASE_WBC_LEDGER_FILENAME) as connection:
        return [
            (str(attempt_id), str(event_type))
            for attempt_id, event_type in connection.execute(
                "SELECT attempt_id, event_type FROM attempt_events "
                "ORDER BY appended_at_ns, sequence"
            )
        ]


def _patch_finalize_shell(
    monkeypatch: pytest.MonkeyPatch,
    *,
    plan_dir: Path,
    worker_error: CliError | None = None,
) -> list[int]:
    observed_ordinals: list[int] = []
    monkeypatch.setenv("MEGAPLAN_AUDIT_DIR", str(plan_dir / "audit"))
    monkeypatch.setattr(cli, "_auto_sync_installed_skills", lambda: None)
    monkeypatch.setattr(cli, "pre_commit_hook_status", lambda _cwd: ("missing", None))
    monkeypatch.setattr(
        finalize_handler, "write_critique_clearance", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr(
        finalize_handler, "_validate_finalize_payload", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr(
        finalize_handler,
        "_reject_finalize_unresolved_north_star",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        finalize_handler, "_ensure_execution_baseline", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr(shared_handlers, "_emit_receipt", lambda **_kwargs: None)

    def seed(target_dir: Path, _state: dict[str, Any]) -> Path:
        path = target_dir / "finalize_output.json"
        path.write_text("{}\n", encoding="utf-8")
        return path

    monkeypatch.setattr(finalize_prompt, "_write_finalize_template", seed)

    def run_worker(
        _step: str,
        state: dict[str, Any],
        _target_dir: Path,
        _args: Any,
        **_kwargs: Any,
    ) -> tuple[WorkerResult, str, str, bool]:
        observed_ordinals.append(int(state["active_step"]["attempt"]))
        if worker_error is not None:
            raise worker_error
        return (
            WorkerResult(
                payload={"tasks": [], "watch_items": []},
                raw_output="{}",
                duration_ms=1,
                cost_usd=0.0,
                worker_channel="test",
                auth_channel="test",
                auth_metadata={"actor": "test"},
            ),
            "codex",
            "persistent",
            False,
        )

    monkeypatch.setattr(
        shared_handlers.worker_module, "run_step_with_worker", run_worker
    )

    def write_artifacts(
        target_dir: Path,
        payload: dict[str, Any],
        _state: dict[str, Any],
        **_kwargs: Any,
    ) -> str:
        for name, body in {
            "contract.json": "{}\n",
            "final.md": "# Final\n",
            "finalize.json": json.dumps(payload) + "\n",
            "user_actions.md": "# User actions\n",
        }.items():
            (target_dir / name).write_text(body, encoding="utf-8")
        return "finalize-hash"

    monkeypatch.setattr(finalize_handler, "_write_finalize_artifacts", write_artifacts)
    return observed_ordinals


def test_direct_finalize_cli_after_attempt_8_cancel_is_exactly_attempt_9(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan_dir, attempt_8 = _paused_attempt_8(tmp_path)
    ordinals = _patch_finalize_shell(monkeypatch, plan_dir=plan_dir)
    monkeypatch.chdir(tmp_path)

    exit_code = cli.main(["finalize", "--plan", "demo"])

    assert exit_code == 0
    assert ordinals == [9]
    persisted = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    assert persisted["current_state"] == "finalized"
    assert "active_step" not in persisted
    assert persisted["history"][-1]["step"] == "finalize"
    assert persisted["history"][-1]["result"] == "success"
    events = _phase_events(plan_dir)
    attempt_ids = {attempt_id for attempt_id, _event in events}
    assert str(attempt_8["attempt_id"]) in attempt_ids
    assert len(attempt_ids) == 2
    assert [
        event for attempt_id, event in events if attempt_id == attempt_8["attempt_id"]
    ] == [
        "started",
        "cancelled",
    ]
    attempt_9_id = next(
        attempt_id
        for attempt_id in attempt_ids
        if attempt_id != attempt_8["attempt_id"]
    )
    assert [event for attempt_id, event in events if attempt_id == attempt_9_id] == [
        "started",
        "completed",
    ]

    status = cli.handle_status(tmp_path, type("Args", (), {"plan": "demo"})())
    assert status["state"] == "finalized"
    assert status["next_step"] == "execute"


def test_direct_finalize_cli_failure_stops_without_attempt_10(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan_dir, attempt_8 = _paused_attempt_8(tmp_path)
    ordinals = _patch_finalize_shell(
        monkeypatch,
        plan_dir=plan_dir,
        worker_error=CliError("provider_error", "one-shot provider failure"),
    )
    monkeypatch.chdir(tmp_path)

    exit_code = cli.main(["finalize", "--plan", "demo"])

    assert exit_code != 0
    assert ordinals == [9]
    persisted = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    assert persisted["current_state"] == "gated"
    assert "active_step" not in persisted
    assert all(
        not (entry.get("step") == "finalize" and entry.get("attempt") == 10)
        for entry in persisted["history"]
    )
    events = _phase_events(plan_dir)
    attempt_ids = {attempt_id for attempt_id, _event in events}
    assert len(attempt_ids) == 2
    assert sum(event == "started" for _attempt_id, event in events) == 2
    attempt_9_id = next(
        attempt_id
        for attempt_id in attempt_ids
        if attempt_id != attempt_8["attempt_id"]
    )
    assert [event for attempt_id, event in events if attempt_id == attempt_9_id] == [
        "started",
        "failed",
    ]
