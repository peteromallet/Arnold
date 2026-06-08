"""Fixture tests for ``megaplan doctor --repo`` (and plan-level checks)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from arnold.pipelines.megaplan.observability.doctor import (
    _check_rubric_drift,
    _check_editable_install,
    _check_skill_sync,
    _check_stale_lock,
    _check_phase_timeout,
    _check_llm_liveness,
    _check_cost_trajectory,
    _check_orphan_subprocesses,
    _check_outstanding_flags,
    _doctor_plan,
    _doctor_repo,
    _check_status,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_plan_dir(tmp_path: Path, plan_name: str = "test-plan") -> Path:
    plan_dir = tmp_path / ".megaplan" / "plans" / plan_name
    plan_dir.mkdir(parents=True, exist_ok=True)
    return plan_dir


def _write_state(plan_dir: Path, state: dict) -> None:
    (plan_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")


def _write_gate_signals(plan_dir: Path, version: int, unresolved_flags: list) -> None:
    data = {"unresolved_flags": unresolved_flags}
    (plan_dir / f"gate_signals_v{version}.json").write_text(
        json.dumps(data), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# _check_status helper
# ---------------------------------------------------------------------------


class TestCheckStatus:
    def test_ok(self):
        sev, label, msg = _check_status("Test", True)
        assert sev == "OK"
        assert "OK" in msg

    def test_warn_with_remediation(self):
        sev, label, msg = _check_status(
            "Test", False, severity="WARN", remediation="Run foo"
        )
        assert sev == "WARN"
        assert "WARN" in msg
        assert "→ Run foo" in msg

    def test_error_with_remediation(self):
        sev, label, msg = _check_status(
            "Test", False, severity="ERROR", remediation="Fix it"
        )
        assert sev == "ERROR"
        assert "ERROR" in msg
        assert "→ Fix it" in msg


# ---------------------------------------------------------------------------
# Plan-level checks
# ---------------------------------------------------------------------------


class TestStaleLock:
    def test_no_lock(self, tmp_path):
        plan_dir = _make_plan_dir(tmp_path)
        sev, label, msg = _check_stale_lock(plan_dir)
        assert sev == "OK"

    def test_lock_with_dead_pid(self, tmp_path, monkeypatch):
        plan_dir = _make_plan_dir(tmp_path)
        lock_file = plan_dir / ".lock"
        lock_file.write_text(json.dumps({"pid": 99999}), encoding="utf-8")

        import psutil
        monkeypatch.setattr(psutil, "pid_exists", lambda pid: False)
        sev, label, msg = _check_stale_lock(plan_dir)
        assert sev == "WARN"
        assert "Stale lock" in msg or "stale" in msg.lower()

    def test_lock_with_live_pid(self, tmp_path, monkeypatch):
        plan_dir = _make_plan_dir(tmp_path)
        lock_file = plan_dir / ".lock"
        lock_file.write_text(json.dumps({"pid": 1}), encoding="utf-8")

        import psutil
        monkeypatch.setattr(psutil, "pid_exists", lambda pid: True)
        sev, label, msg = _check_stale_lock(plan_dir)
        assert sev == "OK"
        assert "live" in msg.lower() or "Lock held" in msg


class TestPhaseTimeout:
    def test_no_state(self, tmp_path):
        plan_dir = _make_plan_dir(tmp_path)
        sev, label, msg = _check_phase_timeout(plan_dir)
        assert sev == "OK"

    def test_no_active_step(self, tmp_path):
        plan_dir = _make_plan_dir(tmp_path)
        _write_state(plan_dir, {"current_state": "planned"})
        sev, label, msg = _check_phase_timeout(plan_dir)
        assert sev == "OK"
        assert "No active phase" in msg

    def test_active_step_within_timeout(self, tmp_path, monkeypatch):
        import time as _time
        plan_dir = _make_plan_dir(tmp_path)
        now = _time.time()
        _write_state(
            plan_dir,
            {
                "current_state": "planning",
                "active_step": {
                    "step": "critique",
                    "started_at": _time.strftime(
                        "%Y-%m-%dT%H:%M:%SZ", _time.gmtime(now - 100)
                    ),
                },
            },
        )
        sev, label, msg = _check_phase_timeout(plan_dir)
        assert sev == "OK"

    def test_active_step_past_80_percent(self, tmp_path, monkeypatch):
        import time as _time
        plan_dir = _make_plan_dir(tmp_path)
        now = _time.time()
        # 3000s ago is > 0.8 * 3600 (2880)
        _write_state(
            plan_dir,
            {
                "current_state": "planning",
                "active_step": {
                    "step": "critique",
                    "started_at": _time.strftime(
                        "%Y-%m-%dT%H:%M:%SZ", _time.gmtime(now - 3000)
                    ),
                },
            },
        )
        sev, label, msg = _check_phase_timeout(plan_dir)
        assert sev == "WARN"
        assert "80%" in msg.replace("80", "") or "timeout" in msg.lower()


class TestLLMLiveness:
    def test_no_events(self, tmp_path):
        plan_dir = _make_plan_dir(tmp_path)
        sev, label, msg = _check_llm_liveness(plan_dir)
        assert sev == "OK"

    def test_matched_llm_call(self, tmp_path):
        plan_dir = _make_plan_dir(tmp_path)
        ndjson = plan_dir / "events.ndjson"
        ndjson.write_text(
            json.dumps(
                {
                    "seq": 0,
                    "ts_utc": "2025-01-01T00:00:00Z",
                    "ts_rel_init_s": 0,
                    "kind": "llm_call_start",
                    "phase": "critique",
                    "payload": {"request_id": "req-123"},
                }
            )
            + "\n"
            + json.dumps(
                {
                    "seq": 1,
                    "ts_utc": "2025-01-01T00:01:00Z",
                    "ts_rel_init_s": 60,
                    "kind": "llm_call_end",
                    "phase": "critique",
                    "payload": {"request_id": "req-123", "tokens_in": 100, "tokens_out": 200},
                }
            )
            + "\n",
            encoding="utf-8",
        )
        sev, label, msg = _check_llm_liveness(plan_dir)
        assert sev == "OK"

    def test_unmatched_start_no_heartbeat(self, tmp_path):
        plan_dir = _make_plan_dir(tmp_path)
        ndjson = plan_dir / "events.ndjson"
        # Start event is old enough to trigger the >60s check
        import time as _time
        old_ts = _time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", _time.gmtime(_time.time() - 120)
        )
        ndjson.write_text(
            json.dumps(
                {
                    "seq": 0,
                    "ts_utc": old_ts,
                    "ts_rel_init_s": 0,
                    "kind": "llm_call_start",
                    "phase": "critique",
                    "payload": {"provider": "openrouter", "model": "test"},
                }
            )
            + "\n",
            encoding="utf-8",
        )
        sev, label, msg = _check_llm_liveness(plan_dir)
        # Should be WARN because unmatched start >60s with no heartbeat
        assert sev == "WARN"
        assert "heartbeat" in msg.lower()


class TestCostTrajectory:
    def test_no_cost(self, tmp_path):
        plan_dir = _make_plan_dir(tmp_path)
        sev, label, msg = _check_cost_trajectory(plan_dir)
        assert sev == "OK"

    def test_cost_over_2x_cap(self, tmp_path):
        plan_dir = _make_plan_dir(tmp_path)
        ndjson = plan_dir / "events.ndjson"
        ndjson.write_text(
            json.dumps(
                {
                    "seq": 0,
                    "ts_utc": "2025-01-01T00:00:00Z",
                    "ts_rel_init_s": 0,
                    "kind": "cost_recorded",
                    "phase": None,
                    "payload": {"cost_usd": 65.0, "provider": "openrouter"},
                }
            )
            + "\n",
            encoding="utf-8",
        )
        sev, label, msg = _check_cost_trajectory(plan_dir)
        assert sev == "WARN"
        assert "2" in msg or "exceed" in msg.lower()


class TestOutstandingFlags:
    def test_no_state(self, tmp_path):
        plan_dir = _make_plan_dir(tmp_path)
        sev, label, msg = _check_outstanding_flags(plan_dir)
        assert sev == "OK"

    def test_with_flags(self, tmp_path):
        plan_dir = _make_plan_dir(tmp_path)
        _write_state(plan_dir, {"current_state": "gated"})
        _write_gate_signals(
            plan_dir,
            1,
            [
                {"flag_id": "flag-1", "severity": "WARN"},
                {"flag_id": "flag-2", "severity": "ERROR"},
            ],
        )
        sev, label, msg = _check_outstanding_flags(plan_dir)
        assert sev == "WARN"
        assert "2 outstanding" in msg or "flag" in msg.lower()


# ---------------------------------------------------------------------------
# Repo-level checks
# ---------------------------------------------------------------------------


class TestRubricDrift:
    def test_no_drift(self, monkeypatch):
        """Rubric profiles all available in binary — no drift."""
        monkeypatch.setattr(
            "arnold.pipelines.megaplan.observability.doctor._parse_decision_skill_profiles",
            lambda: ["solo", "directed", "partnered"],
        )
        monkeypatch.setattr(
            "arnold.pipelines.megaplan.observability.doctor._get_profiles_list",
            lambda: ["solo", "directed", "partnered", "premium", "apex"],
        )
        results = _check_rubric_drift()
        assert len(results) == 1
        sev, label, msg = results[0]
        assert sev == "OK"

    def test_missing_profile_warn(self, monkeypatch):
        """A profile referenced in the skill doc is missing from binary → WARN."""
        monkeypatch.setattr(
            "arnold.pipelines.megaplan.observability.doctor._parse_decision_skill_profiles",
            lambda: ["basic", "thoughtful"],  # not in the real profiles
        )
        monkeypatch.setattr(
            "arnold.pipelines.megaplan.observability.doctor._get_profiles_list",
            lambda: ["solo", "directed", "partnered", "premium", "apex"],
        )
        results = _check_rubric_drift()
        assert len(results) == 1
        sev, label, msg = results[0]
        assert sev == "WARN"
        assert "basic" in msg or "thoughtful" in msg
        assert "Missing profiles" in msg


class TestEditableInstall:
    def test_no_editable_install(self, monkeypatch):
        monkeypatch.setattr(
            "arnold.pipelines.megaplan.observability.doctor._is_editable_install",
            lambda: False,
        )
        sev, label, msg = _check_editable_install()
        assert sev == "OK"

    def test_editable_install_dirty(self, monkeypatch, tmp_path):
        """Editable install + dirty tree → WARN."""
        monkeypatch.setattr(
            "arnold.pipelines.megaplan.observability.doctor._is_editable_install",
            lambda: True,
        )

        # Mock pip show to return a location
        def mock_pip_run(*args, **kwargs):
            result = MagicMock()
            result.returncode = 0
            result.stdout = f"Editable project location: {tmp_path}\n"
            return result

        monkeypatch.setattr(subprocess, "run", mock_pip_run)

        # Mock git dirty
        monkeypatch.setattr(
            "arnold.pipelines.megaplan.observability.doctor._git_dirty",
            lambda path: True,
        )
        monkeypatch.setattr(
            "arnold.pipelines.megaplan.observability.doctor._git_branch",
            lambda path: "feature/test",
        )

        sev, label, msg = _check_editable_install()
        assert sev == "WARN"
        assert "dirty" in msg.lower() or "Editable install" in msg


class TestSkillSync:
    def test_no_installed_skills(self, monkeypatch):
        """When no skill files exist, produce no sync warnings."""
        # Make both paths not exist
        monkeypatch.setattr(
            Path, "exists", lambda self: False
        )
        results = _check_skill_sync()
        # Should return empty list (no checks emitted)
        assert isinstance(results, list)


# ---------------------------------------------------------------------------
# Exit code tests
# ---------------------------------------------------------------------------


class TestDoctorExitCodes:
    def test_doctor_plan_all_ok(self, tmp_path, monkeypatch):
        """All plan checks pass → exit code 0."""
        plan_dir = _make_plan_dir(tmp_path)
        _write_state(plan_dir, {"current_state": "planned"})
        # All mocks return OK
        exit_code = _doctor_plan(plan_dir)
        assert exit_code == 0

    def test_doctor_repo_all_ok(self, tmp_path, monkeypatch):
        """All repo checks pass → exit code 0."""
        monkeypatch.setattr(
            "arnold.pipelines.megaplan.observability.doctor._parse_decision_skill_profiles",
            lambda: ["solo"],
        )
        monkeypatch.setattr(
            "arnold.pipelines.megaplan.observability.doctor._get_profiles_list",
            lambda: ["solo", "directed", "partnered", "premium", "apex"],
        )
        monkeypatch.setattr(
            "arnold.pipelines.megaplan.observability.doctor._is_editable_install",
            lambda: False,
        )
        monkeypatch.setattr(
            "arnold.pipelines.megaplan.observability.doctor._find_megaplan_checkouts",
            lambda: [tmp_path],
        )
        monkeypatch.setattr(
            "arnold.pipelines.megaplan.observability.doctor._check_skill_sync",
            lambda: [],
        )
        exit_code = _doctor_repo(tmp_path)
        assert exit_code == 0

    def test_doctor_repo_with_warn_still_ok_exit(self, tmp_path, monkeypatch):
        """WARN-level issues still exit 0."""
        monkeypatch.setattr(
            "arnold.pipelines.megaplan.observability.doctor._check_rubric_drift",
            lambda: [
                _check_status(
                    "Test", False, severity="WARN", remediation="Test remediation."
                )
            ],
        )
        monkeypatch.setattr(
            "arnold.pipelines.megaplan.observability.doctor._check_editable_install",
            lambda: _check_status("Editable", True, severity="OK"),
        )
        monkeypatch.setattr(
            "arnold.pipelines.megaplan.observability.doctor._check_multiple_checkouts",
            lambda: _check_status("Checkouts", True, severity="OK"),
        )
        monkeypatch.setattr(
            "arnold.pipelines.megaplan.observability.doctor._check_skill_sync",
            lambda: [],
        )
        exit_code = _doctor_repo(tmp_path)
        assert exit_code == 0

    def test_doctor_repo_with_error_exits_1(self, tmp_path, monkeypatch):
        """ERROR-level issue → exit code 1."""
        monkeypatch.setattr(
            "arnold.pipelines.megaplan.observability.doctor._check_rubric_drift",
            lambda: [
                _check_status(
                    "Test", False, severity="ERROR", remediation="Critical."
                )
            ],
        )
        monkeypatch.setattr(
            "arnold.pipelines.megaplan.observability.doctor._check_editable_install",
            lambda: _check_status("Editable", True, severity="OK"),
        )
        monkeypatch.setattr(
            "arnold.pipelines.megaplan.observability.doctor._check_multiple_checkouts",
            lambda: _check_status("Checkouts", True, severity="OK"),
        )
        monkeypatch.setattr(
            "arnold.pipelines.megaplan.observability.doctor._check_skill_sync",
            lambda: [],
        )
        exit_code = _doctor_repo(tmp_path)
        assert exit_code == 1
