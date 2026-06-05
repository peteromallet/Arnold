from __future__ import annotations

from pathlib import Path

import pytest

import arnold.pipelines.megaplan as megaplan
from arnold.pipelines.megaplan.handlers.finalize import (
    _apply_programmatic_coverage,
    _validate_finalize_payload,
    _write_finalize_artifacts,
)
from arnold.pipelines.megaplan.workers import WorkerResult
from tests.conftest import PlanFixture, load_state, read_json


def _state(project_dir: Path) -> dict:
    return {
        "name": "coverage",
        "idea": "coverage",
        "current_state": "gated",
        "iteration": 1,
        "config": {"project_dir": str(project_dir), "mode": "code"},
        "plan_versions": [{"version": 1, "file": "plan_v1.md", "hash": "sha256:test"}],
        "history": [],
        "sessions": {},
        "meta": {},
    }


def _payload(description: str) -> dict:
    return {
        "tasks": [
            {
                "id": "T1",
                "description": description,
                "depends_on": [],
                "status": "pending",
                "complexity": 2,
                "complexity_justification": "Localized change with an obvious test update → tier 2.",
                "executor_notes": "",
                "files_changed": [],
                "commands_run": [],
                "evidence_files": [],
                "reviewer_verdict": "",
            }
        ],
        "watch_items": [],
        "sense_checks": [],
        "user_actions": [],
        "meta_commentary": "ok",
    }


def test_programmatic_coverage_check_detects_uncovered_step(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    project_dir = tmp_path / "project"
    plan_dir.mkdir()
    project_dir.mkdir()
    (plan_dir / "plan_v1.md").write_text("## Step 1: Update auth.py\nShip auth fix.\n", encoding="utf-8")
    payload = _payload("Update db.py")

    _apply_programmatic_coverage(payload, plan_dir, _state(project_dir))

    validation = payload["validation"]
    assert validation["coverage_complete"] is False
    assert validation["plan_steps_covered"] == [
        {"plan_step_summary": "Update auth.py", "finalize_item_ids": []}
    ]
    assert "auto-detected uncovered step: Update auth.py" in validation["completeness_notes"]


def test_programmatic_coverage_check_passes_when_covered(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    project_dir = tmp_path / "project"
    plan_dir.mkdir()
    project_dir.mkdir()
    (plan_dir / "plan_v1.md").write_text("## Step 1: Update auth.py\nShip auth fix.\n", encoding="utf-8")
    payload = _payload("Update auth.py")

    _apply_programmatic_coverage(payload, plan_dir, _state(project_dir))

    validation = payload["validation"]
    assert validation["coverage_complete"] is True
    assert validation["plan_steps_covered"] == [
        {"plan_step_summary": "Update auth.py", "finalize_item_ids": ["T1"]}
    ]


def test_finalize_snapshot_status(plan_fixture: PlanFixture) -> None:
    state = load_state(plan_fixture.plan_dir)
    state["config"]["mode"] = "code"
    state["plan_versions"] = [{"version": 1, "file": "plan_v1.md", "hash": "sha256:test"}]
    (plan_fixture.plan_dir / "plan_v1.md").write_text(
        "## Step 1: Implement test idea\nShip the code change.\n",
        encoding="utf-8",
    )
    payload = _payload("Implement test idea")
    payload["tasks"].append(
        {
            "id": "T2",
            "description": "Run pytest to verify the change.",
            "depends_on": ["T1"],
            "status": "pending",
            "executor_notes": "",
            "files_changed": [],
            "commands_run": [],
            "evidence_files": [],
            "reviewer_verdict": "",
            "kind": "test",
        }
    )

    _write_finalize_artifacts(plan_fixture.plan_dir, payload, state)

    assert (plan_fixture.plan_dir / "finalize_snapshot.json").exists()
    assert read_json(plan_fixture.plan_dir / "finalize_snapshot.json") == read_json(
        plan_fixture.plan_dir / "finalize.json"
    )


def test_strict_finalize_validation_accepts_missing_final_test_task(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = load_state(plan_fixture.plan_dir)
    state["config"]["mode"] = "code"
    worker = WorkerResult(
        payload=_payload("Implement test idea"),
        raw_output="missing test task",
        duration_ms=1,
        cost_usd=0.0,
        session_id="strict-finalize",
    )
    monkeypatch.setenv("MEGAPLAN_FINALIZE_STRICT_VALIDATION", "1")

    _validate_finalize_payload(plan_fixture.plan_dir, state, worker)
