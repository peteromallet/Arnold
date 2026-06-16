from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from arnold.pipelines.megaplan._core.io import read_json
from arnold.pipelines.megaplan.handlers.override import handle_override
from arnold.pipelines.megaplan.orchestration.phase_result import (
    ExitKind,
    PhaseResult,
    atomic_write_phase_result,
    read_phase_result,
)
from arnold.pipelines.megaplan.types import CliError


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _plan_dir(root: Path) -> Path:
    plan_dir = root / ".megaplan" / "plans" / "adopt-me"
    _write_json(
        plan_dir / "state.json",
        {
            "schema_version": 1,
            "name": "adopt-me",
            "current_state": "finalized",
            "iteration": 1,
            "idea": "recover execute",
            "config": {"project_dir": str(root)},
            "history": [],
            "meta": {"overrides": [], "notes": [], "total_cost_usd": 0.0},
        },
    )
    _write_json(
        plan_dir / "finalize.json",
        {
            "tasks": [
                {"id": "T1", "status": "done"},
                {"id": "T2", "status": "done"},
            ],
            "sense_checks": [
                {"id": "SC1", "task_id": "T1"},
                {"id": "SC2", "task_id": "T2"},
            ],
        },
    )
    _write_json(
        plan_dir / "execution.json",
        {
            "output": "done",
            "task_updates": [
                {"task_id": "T1", "status": "done"},
                {"task_id": "T2", "status": "done"},
            ],
            "sense_check_acknowledgments": [
                {"sense_check_id": "SC1", "executor_note": "ok"},
                {"sense_check_id": "SC2", "executor_note": "ok"},
            ],
            "deviations": [],
        },
    )
    atomic_write_phase_result(
        plan_dir,
        PhaseResult(
            phase="execute",
            invocation_id="execute-before",
            exit_kind=ExitKind.internal_error.value,
            cli_provenance={"error": "worker execution failed before adoption"},
        ),
    )
    return plan_dir


def _args(**overrides: object) -> argparse.Namespace:
    data = {
        "override_action": "adopt-execution",
        "plan": "adopt-me",
        "reason": "validated complete execution artifact",
    }
    data.update(overrides)
    return argparse.Namespace(**data)


def test_override_adopt_execution_promotes_complete_artifact(tmp_path: Path) -> None:
    plan_dir = _plan_dir(tmp_path)

    response = handle_override(tmp_path, _args())

    state = read_json(plan_dir / "state.json")
    phase_result = read_phase_result(plan_dir)
    assert response["success"] is True
    assert response["state"] == "executed"
    assert response["next_step"] == "review"
    assert state["current_state"] == "executed"
    assert state["history"][-1]["step"] == "execute"
    assert state["history"][-1]["result"] == "success"
    assert state["history"][-1]["output_file"] == "execution.json"
    assert state["meta"]["overrides"][-1]["action"] == "adopt-execution"
    assert phase_result is not None
    assert phase_result.phase == "execute"
    assert phase_result.invocation_id == "execute-before"
    assert phase_result.exit_kind == ExitKind.success.value
    assert phase_result.cli_provenance["adopted"] is True


def test_override_adopt_execution_refuses_incomplete_artifact(tmp_path: Path) -> None:
    plan_dir = _plan_dir(tmp_path)
    execution = read_json(plan_dir / "execution.json")
    execution["task_updates"] = [{"task_id": "T1", "status": "done"}]
    _write_json(plan_dir / "execution.json", execution)

    with pytest.raises(CliError) as excinfo:
        handle_override(tmp_path, _args())

    assert excinfo.value.code == "incomplete_execution_artifact"
    assert excinfo.value.extra["missing_task_updates"] == ["T2"]
    state = read_json(plan_dir / "state.json")
    phase_result = read_phase_result(plan_dir)
    assert state["current_state"] == "finalized"
    assert phase_result is not None
    assert phase_result.exit_kind == ExitKind.internal_error.value
