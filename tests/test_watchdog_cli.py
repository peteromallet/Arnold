"""Tests for the live watchdog CLI."""

from __future__ import annotations

import json
import shutil

from scripts.megaplan_live_watchdog import main


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
