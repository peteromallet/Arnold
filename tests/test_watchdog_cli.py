"""Tests for the live watchdog CLI."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from arnold_pipelines.megaplan.pipelines.live_supervisor.model import (
    Incident,
    PlanEntry,
    SignalBundle,
    Snapshot,
    Triage,
)
from scripts.megaplan_live_watchdog import main
from scripts.megaplan_live_watchdog import _select_semantic_problem


class _NoopLogger:
    def info(self, *args, **kwargs):
        pass


def _snapshot_for_plan(plan_dir: Path, state: str) -> Snapshot:
    plan = PlanEntry(
        plan_id=plan_dir.name,
        plan_name=plan_dir.name,
        plan_dir=str(plan_dir),
        repo_path=str(plan_dir.parents[2]),
        state={"current_state": state, "name": plan_dir.name},
    )
    incident = Incident(
        plan_entry=plan,
        signals=SignalBundle(
            liveness="unknown",
            liveness_reason="unit test",
            block_details={},
            doctor_findings=(),
        ),
        triage=Triage.STALE,
    )
    return Snapshot(
        scan_ts_utc=datetime.now(timezone.utc).isoformat(),
        plans=(plan,),
        incidents=(incident,),
    )


def test_watchdog_works_with_broken_megaplan_cli(tmp_path, monkeypatch):
    # Simulate a plan directory.
    plan_dir = tmp_path / "repo" / ".megaplan" / "plans" / "my-plan"
    plan_dir.mkdir(parents=True)
    (plan_dir / "state.json").write_text(json.dumps({"current_state": "planned", "name": "my-plan"}))

    # Ensure no real megaplan executable is found.
    monkeypatch.setattr("shutil.which", lambda cmd, path=None: None)
    # Also point PATH to nothing in RepairRunner.
    monkeypatch.setenv("PATH", "")

    report_path = tmp_path / "report.json"
    rc = main(
        [
            "--once",
            f"--roots={tmp_path / 'repo'}",
            f"--registry-path={tmp_path / 'registry.ndjson'}",
            f"--report-path={report_path}",
            "--repair-runner=dry-run",
            "--recheck-seconds=0",
            "--lookback-hours=0",
        ]
    )
    assert rc == 0
    combined = json.loads(report_path.read_text())
    report = combined["reports"][0]
    assert report["plans_found"] == ["my-plan"]
    # The pipeline ran and produced classifications/diagnoses/decisions.
    assert "classify" in report["artifacts"]
    assert "repair_decision" in report["artifacts"]
    # Repair path degraded because dry-run has no executables.
    assert report["repair_results"][0]["attempts"][0]["status"] == "command_unavailable"


def test_terminal_stale_lock_becomes_cleanup_candidate(tmp_path, monkeypatch):
    plan_dir = tmp_path / "repo" / ".megaplan" / "plans" / "done-plan"
    plan_dir.mkdir(parents=True)
    (plan_dir / "state.json").write_text(
        json.dumps({"current_state": "done", "name": "done-plan"})
    )
    (plan_dir / ".plan.lock").write_text("")
    import os
    import time

    # Make the lock older than the stale threshold.
    os.utime(plan_dir / ".plan.lock", (time.time() - 600, time.time() - 600))

    monkeypatch.setattr("shutil.which", lambda cmd, path=None: None)
    monkeypatch.setenv("PATH", "")

    report_path = tmp_path / "report.json"
    rc = main(
        [
            f"--roots={tmp_path / 'repo'}",
            f"--registry-path={tmp_path / 'registry.ndjson'}",
            f"--report-path={report_path}",
            "--repair-runner=dry-run",
            "--recheck-seconds=0",
            "--lookback-hours=0",
        ]
    )
    assert rc == 0
    combined = json.loads(report_path.read_text())
    report = combined["reports"][0]
    assert report["plans_found"] == ["done-plan"]
    assert len(report["cleanup_candidates"]) == 1
    assert report["cleanup_candidates"][0]["plan_id"] == "done-plan"
    assert len(report["problem_incidents"]) == 0
    assert len(report["repair_results"]) == 0


def test_semantic_recovery_drives_prepped_plan_before_stale_child_or_parent(tmp_path):
    repo = tmp_path / "repo"
    plan_dir = repo / ".megaplan" / "plans" / "m1-demo"
    plan_dir.mkdir(parents=True)
    (plan_dir / "state.json").write_text(
        json.dumps({"current_state": "prepped", "name": "m1-demo"}),
        encoding="utf-8",
    )

    chain_dir = repo / ".megaplan" / "plans" / ".chains"
    chain_dir.mkdir(parents=True)
    (chain_dir / "chain-demo.json").write_text(
        json.dumps(
            {
                "current_plan_name": "m1-demo",
                "last_state": "awaiting_human",
                "metadata": {
                    "chain_spec_path": str(repo / ".megaplan" / "initiatives" / "demo" / "chain.yaml"),
                    "execution_environment": {"project_root": str(repo)},
                },
            }
        ),
        encoding="utf-8",
    )

    parent_dir = repo / ".megaplan" / "plans" / ".epic_chains"
    parent_dir.mkdir(parents=True)
    (parent_dir / "epic-chain-demo.json").write_text(
        json.dumps(
            {
                "current_epic_id": "demo",
                "current_spec_path": str(repo / ".megaplan" / "initiatives" / "demo" / "chain.yaml"),
                "last_state": "awaiting_human_verify",
            }
        ),
        encoding="utf-8",
    )

    problem, semantic_view = _select_semantic_problem(
        (str(repo),),
        _snapshot_for_plan(plan_dir, "prepped"),
        _NoopLogger(),
    )

    assert problem is not None
    assert problem["plan_id"] == "m1-demo"
    action = problem["decision"]["verdict"]["action"]
    assert action["command"] == "plan --plan m1-demo"
    assert "child chain last_state=awaiting_human" not in problem["decision"]["verdict"]["reason"]
    assert semantic_view["parents"][0]["last_state"] == "awaiting_human_verify"
    assert semantic_view["children"][0]["stale_summary"] is True


def test_semantic_recovery_answers_assumed_prep_clarification(tmp_path):
    repo = tmp_path / "repo"
    plan_dir = repo / ".megaplan" / "plans" / "m1-demo"
    plan_dir.mkdir(parents=True)
    (plan_dir / "state.json").write_text(
        json.dumps({"current_state": "awaiting_human_verify", "name": "m1-demo"}),
        encoding="utf-8",
    )
    (plan_dir / "prep.json").write_text(
        json.dumps(
            {
                "open_questions": [
                    {
                        "severity": "assume_and_proceed",
                        "question": "Which module path wins?",
                        "assumption": "Use surviving modules.",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    problem, _ = _select_semantic_problem(
        (str(repo),),
        _snapshot_for_plan(plan_dir, "awaiting_human_verify"),
        _NoopLogger(),
    )

    assert problem is not None
    action = problem["decision"]["verdict"]["action"]
    assert action["commands"][0].startswith("override add-note --plan m1-demo")
    assert action["commands"][1] == "override resume-clarify --plan m1-demo"


def test_semantic_recovery_surfaces_unresolved_human_blocker(tmp_path):
    repo = tmp_path / "repo"
    plan_dir = repo / ".megaplan" / "plans" / "m1-demo"
    plan_dir.mkdir(parents=True)
    (plan_dir / "state.json").write_text(
        json.dumps({"current_state": "awaiting_human_verify", "name": "m1-demo"}),
        encoding="utf-8",
    )
    (plan_dir / "prep.json").write_text(
        json.dumps(
            {
                "open_questions": [
                    {
                        "severity": "blocking",
                        "question": "Delete production data?",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    problem, _ = _select_semantic_problem(
        (str(repo),),
        _snapshot_for_plan(plan_dir, "awaiting_human_verify"),
        _NoopLogger(),
    )

    assert problem is not None
    verdict = problem["decision"]["verdict"]
    assert verdict["allowed"] is False
    assert "Delete production data?" in verdict["reason"]
