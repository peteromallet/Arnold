"""Tests for watchdog repair runner."""

from __future__ import annotations

from arnold.pipelines.megaplan.watchdog.repair_runner import RepairRunner


def test_repair_runner_executes_allowlisted_command():
    runner = RepairRunner()
    result = runner.run("echo hello")
    assert result.status == "success"
    assert result.rc == 0
    assert "hello" in result.stdout


def test_repair_runner_handles_missing_executable(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda cmd, path=None: None)
    runner = RepairRunner()
    result = runner.run("definitely-not-installed-xyz --plan foo")
    assert result.status == "command_unavailable"
    assert "not found" in result.stderr


def test_repair_runner_reports_nonzero_rc():
    runner = RepairRunner()
    result = runner.run("false")
    assert result.status == "failed"
    assert result.rc == 1
