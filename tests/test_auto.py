"""Tests for megaplan.auto — the auto-driver loop.

Focus: the rework-cycle-aware stall detector added in v0.18.1. A plan in
``finalized`` state that's doing review→rework loops should not be flagged
as stalled just because ``state`` hasn't advanced — new ``review.json``
artifacts indicate real forward progress.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

from megaplan import auto
from megaplan.auto import DriverOutcome, drive


def _make_plan_dir(tmp_path: Path, plan: str) -> Path:
    """Create a skeletal plan dir that `_resolve_plan_dir` can locate."""
    plan_dir = tmp_path / ".megaplan" / "plans" / plan
    plan_dir.mkdir(parents=True)
    (plan_dir / "state.json").write_text(
        json.dumps({"name": plan, "current_state": "finalized"}),
        encoding="utf-8",
    )
    return plan_dir


def _finalized_status(plan: str) -> dict:
    """Return a status snapshot that looks like 'review is next'."""
    return {
        "success": True,
        "step": "status",
        "plan": plan,
        "state": "finalized",
        "iteration": 1,
        "summary": "Plan is in state 'finalized'.",
        "next_step": "review",
        "valid_next": ["review"],
    }


def _execute_status(plan: str, state: str = "finalized") -> dict:
    return {
        "success": True,
        "step": "status",
        "plan": plan,
        "state": state,
        "iteration": 1,
        "summary": f"Plan is in state '{state}'.",
        "next_step": "execute",
        "valid_next": ["execute"],
    }


def _phase_status(plan: str, state: str = "planning", next_step: str = "prep") -> dict:
    return {
        "success": True,
        "step": "status",
        "plan": plan,
        "state": state,
        "iteration": 1,
        "summary": f"Plan is in state '{state}'.",
        "next_step": next_step,
        "valid_next": [next_step],
    }


def _done_status(plan: str) -> dict:
    return {
        "success": True,
        "step": "status",
        "plan": plan,
        "state": "done",
        "iteration": 1,
        "summary": "Plan is in state 'done'.",
        "next_step": None,
        "valid_next": [],
    }


def _terminal_status(plan: str, state: str) -> dict:
    return {
        "success": True,
        "step": "status",
        "plan": plan,
        "state": state,
        "iteration": 1,
        "summary": f"Plan is in state '{state}'.",
        "next_step": None,
        "valid_next": [],
    }


def _write_history(plan_dir: Path, costs: list[object]) -> None:
    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "name": plan_dir.name,
                "current_state": "finalized",
                "history": [{"cost_usd": cost} for cost in costs],
            }
        ),
        encoding="utf-8",
    )


def _append_history_cost(plan_dir: Path, cost: float) -> None:
    state_path = plan_dir / "state.json"
    state_data = json.loads(state_path.read_text(encoding="utf-8"))
    history = state_data.setdefault("history", [])
    history.append({"cost_usd": cost})
    state_path.write_text(json.dumps(state_data), encoding="utf-8")


def test_stall_counter_resets_when_review_json_is_rewritten(tmp_path: Path) -> None:
    """Stall detection must be rework-aware.

    Simulates the production bug: state pinned at `finalized` while execute
    rework and review re-run. Each time review rewrites `review.json`, the
    stall counter must reset so the driver doesn't bail prematurely.
    """
    plan = "rework-plan"
    plan_dir = _make_plan_dir(tmp_path, plan)
    review_path = plan_dir / "review.json"
    review_path.write_text("{}", encoding="utf-8")
    base_mtime = review_path.stat().st_mtime

    iteration_counter = {"n": 0}

    def fake_status(plan_name: str, cwd=None, timeout=60):
        # Always return finalized — simulates state ping-pong that looks
        # stuck to the naive stall counter.
        return _finalized_status(plan_name)

    def fake_run(args, cwd=None, timeout=None):
        # Every phase invocation bumps review.json mtime by 1s, simulating
        # a completed review cycle. Over 6 iterations the driver should
        # observe ~5 rework cycles — well past the default stall_threshold
        # of 5, but NOT bail because each cycle resets the counter.
        iteration_counter["n"] += 1
        new_mtime = base_mtime + iteration_counter["n"]
        os.utime(review_path, (new_mtime, new_mtime))
        return 0, "{}", ""

    # Cap iterations low and allow plenty of rework cycles so we exercise
    # the reset path without tripping the rework cap.
    with patch.object(auto, "_status", side_effect=fake_status), \
         patch.object(auto, "_run_megaplan", side_effect=fake_run):
        outcome = drive(
            plan,
            cwd=tmp_path,
            stall_threshold=3,  # would normally trip after 3 same-state iters
            max_iterations=6,
            max_review_rework_cycles=10,  # high so we exercise reset, not cap
            poll_sleep=0,
            writer=lambda _m: None,
        )

    # We should NOT have stalled — each rework cycle reset the stall counter.
    assert outcome.status == "cap", (
        f"expected cap (hit max_iterations) with rework resets, got "
        f"{outcome.status}: {outcome.reason}"
    )
    # And we should have observed multiple rework cycles.
    rework_events = [
        e for e in outcome.events if "rework cycle" in e.get("msg", "")
    ]
    assert len(rework_events) >= 3, (
        f"expected at least 3 rework cycles observed, got "
        f"{len(rework_events)}: {[e['msg'] for e in rework_events]}"
    )


def test_rework_cap_bails_after_exceeding_max_review_rework_cycles(
    tmp_path: Path,
) -> None:
    """The rework-cap guard must stop runaway needs_rework loops."""
    plan = "rework-cap-plan"
    plan_dir = _make_plan_dir(tmp_path, plan)
    review_path = plan_dir / "review.json"
    review_path.write_text("{}", encoding="utf-8")
    base_mtime = review_path.stat().st_mtime

    iteration_counter = {"n": 0}

    def fake_status(plan_name: str, cwd=None, timeout=60):
        return _finalized_status(plan_name)

    def fake_run(args, cwd=None, timeout=None):
        iteration_counter["n"] += 1
        new_mtime = base_mtime + iteration_counter["n"]
        os.utime(review_path, (new_mtime, new_mtime))
        return 0, "{}", ""

    with patch.object(auto, "_status", side_effect=fake_status), \
         patch.object(auto, "_run_megaplan", side_effect=fake_run):
        outcome = drive(
            plan,
            cwd=tmp_path,
            stall_threshold=100,  # effectively disabled — force cap to trip
            max_iterations=20,
            max_review_rework_cycles=2,  # tight cap
            poll_sleep=0,
            writer=lambda _m: None,
        )

    assert outcome.status == "stalled"
    assert "review rework cap" in outcome.reason
    assert outcome.final_state == "finalized"


def test_stall_still_trips_without_review_progress(tmp_path: Path) -> None:
    """Preserve existing stall detection for non-rework plans.

    When a plan has no ``review.json`` (e.g. light-robustness plans that
    skip review entirely) the marker stays ``None``, rework tracking is
    inert, and the driver should fall back to the plain stall counter.
    """
    plan = "no-review-plan"
    _make_plan_dir(tmp_path, plan)  # no review.json on disk

    def fake_status(plan_name: str, cwd=None, timeout=60):
        return _finalized_status(plan_name)

    def fake_run(args, cwd=None, timeout=None):
        return 0, "{}", ""

    with patch.object(auto, "_status", side_effect=fake_status), \
         patch.object(auto, "_run_megaplan", side_effect=fake_run):
        outcome = drive(
            plan,
            cwd=tmp_path,
            stall_threshold=3,
            max_iterations=20,
            poll_sleep=0,
            writer=lambda _m: None,
        )

    assert outcome.status == "stalled"
    assert "stalled at 'finalized'" in outcome.reason


def test_resolve_plan_dir_finds_plans_in_parent_tree(tmp_path: Path) -> None:
    """``_resolve_plan_dir`` must mirror `megaplan status`'s resolution."""
    plan = "nested-plan"
    plan_dir = _make_plan_dir(tmp_path, plan)

    # Check cwd itself.
    assert auto._resolve_plan_dir(plan, tmp_path) == plan_dir

    # Check a child cwd (walks up).
    child = tmp_path / "nested" / "subdir"
    child.mkdir(parents=True)
    assert auto._resolve_plan_dir(plan, child) == plan_dir

    # Unknown plan returns None.
    assert auto._resolve_plan_dir("does-not-exist", tmp_path) is None


def test_get_review_marker_returns_none_when_review_missing(
    tmp_path: Path,
) -> None:
    plan = "no-review"
    plan_dir = _make_plan_dir(tmp_path, plan)
    assert auto._get_review_marker(plan_dir) is None
    assert auto._get_review_marker(None) is None

    (plan_dir / "review.json").write_text("{}", encoding="utf-8")
    marker = auto._get_review_marker(plan_dir)
    assert marker is not None
    assert isinstance(marker, float)


def test_run_megaplan_uses_module_launcher(tmp_path: Path) -> None:
    proc = auto.subprocess.CompletedProcess(
        args=[],
        returncode=0,
        stdout="{}",
        stderr="",
    )

    with patch.object(auto.subprocess, "run", return_value=proc) as mock_run:
        code, out, err = auto._run_megaplan(["status", "--plan", "demo"], cwd=tmp_path, timeout=5)

    assert (code, out, err) == (0, "{}", "")
    assert mock_run.call_args.args[0] == [
        sys.executable,
        "-m",
        "megaplan",
        "status",
        "--plan",
        "demo",
    ]


def _auto_args(plan: str, outcome_file: str | None = None) -> argparse.Namespace:
    return argparse.Namespace(
        plan=plan,
        stall_threshold=1,
        max_iterations=1,
        max_review_rework_cycles=1,
        on_escalate="force-proceed",
        poll_sleep=0,
        phase_timeout=1,
        status_timeout=1,
        outcome_file=outcome_file,
        max_cost_usd=None,
        max_context_retries=2,
        max_blocked_retries=1,
    )


def test_run_auto_writes_outcome_file_matching_stdout(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    outcome = DriverOutcome(
        status="done",
        plan="demo",
        final_state="done",
        iterations=2,
        reason="complete",
        last_phase="review",
        events=[{"msg": "finished"}],
    )
    outcome_path = tmp_path / "nested" / "outcome.json"

    with patch.object(auto, "drive", return_value=outcome):
        rc = auto.run_auto(tmp_path, _auto_args("demo", str(outcome_path)))

    stdout = capsys.readouterr().out
    outcome_json = outcome.to_json()
    assert rc == 0
    assert outcome_path.read_text(encoding="utf-8") == outcome_json
    assert stdout == outcome_json + "\n"


def test_run_auto_without_outcome_file_preserves_stdout_only_behavior(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    outcome = DriverOutcome(
        status="stalled",
        plan="demo",
        final_state="finalized",
        iterations=3,
        reason="stalled",
    )

    with patch.object(auto, "drive", return_value=outcome):
        rc = auto.run_auto(tmp_path, _auto_args("demo"))

    stdout = capsys.readouterr().out
    assert rc == 2
    assert stdout == outcome.to_json() + "\n"


def test_run_auto_passes_progress_env_to_driver(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from megaplan.progress import ProgressContext

    captured: dict[str, dict[str, str] | None] = {}
    env = ProgressContext(
        backend="file",
        file_root=str(tmp_path / "store"),
        epic_id="epic-1",
        plan_id="demo",
        run_id="run-1",
    ).to_env()
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    outcome = DriverOutcome(status="done", plan="demo", final_state="done", iterations=1)

    def fake_drive(*args, **kwargs):
        del args
        captured["progress_env"] = kwargs.get("progress_env")
        return outcome

    with patch.object(auto, "drive", side_effect=fake_drive):
        assert auto.run_auto(tmp_path, _auto_args("demo")) == 0

    assert captured["progress_env"] == env


def test_auto_driver_stops_on_lifecycle_terminal_states_without_phase_runs(tmp_path: Path) -> None:
    expected = {
        "failed": "failed",
        "blocked": "blocked",
        "cancelled": "cancelled",
        "paused": "paused",
    }
    for state, status in expected.items():
        plan = f"auto-{state}"
        _make_plan_dir(tmp_path, plan)
        calls: list[list[str]] = []

        with patch.object(auto, "_status", return_value=_terminal_status(plan, state)), \
             patch.object(auto, "_run_megaplan", side_effect=lambda *args, **kwargs: calls.append(list(args[0])) or (0, "", "")):
            outcome = drive(plan, cwd=tmp_path, poll_sleep=0, writer=lambda _m: None)

        assert outcome.status == status
        assert outcome.final_state == state
        assert calls == []


def test_run_auto_exit_codes_for_lifecycle_outcomes(tmp_path: Path, capsys) -> None:
    outcomes = {
        "failed": 1,
        "blocked": 5,
        "cancelled": 0,
        "paused": 0,
    }
    for status, expected_rc in outcomes.items():
        outcome = DriverOutcome(status=status, plan=f"demo-{status}", final_state=status, iterations=1)
        with patch.object(auto, "drive", return_value=outcome):
            assert auto.run_auto(tmp_path, _auto_args(f"demo-{status}")) == expected_rc
        capsys.readouterr()
def test_context_retry_success_retries_execute_with_fresh(tmp_path: Path) -> None:
    plan = "context-retry-success"
    _make_plan_dir(tmp_path, plan)
    statuses = [_execute_status(plan), _done_status(plan)]
    calls: list[list[str]] = []
    fragment = "Codex ran out of room in the model's context window."

    def fake_status(plan_name: str, cwd=None, timeout=60):
        return statuses.pop(0)

    def fake_run(args, cwd=None, timeout=None):
        calls.append(list(args))
        if len(calls) == 1:
            return 1, "", fragment
        return 0, "", ""

    with patch.object(auto, "_status", side_effect=fake_status), \
         patch.object(auto, "_run_megaplan", side_effect=fake_run):
        outcome = drive(plan, cwd=tmp_path, poll_sleep=0, writer=lambda _m: None)

    assert outcome.status == "done"
    assert outcome.context_retries_used == 1
    assert len(calls) == 2
    assert "--fresh" not in calls[0]
    assert "--fresh" in calls[1]


def test_context_retry_exhaustion_stops_after_max_retries(tmp_path: Path) -> None:
    plan = "context-retry-exhausted"
    _make_plan_dir(tmp_path, plan)
    calls: list[list[str]] = []
    fragment = "Codex ran out of room in the model's context window."

    def fake_status(plan_name: str, cwd=None, timeout=60):
        return _execute_status(plan)

    def fake_run(args, cwd=None, timeout=None):
        calls.append(list(args))
        return 1, fragment, ""

    with patch.object(auto, "_status", side_effect=fake_status), \
         patch.object(auto, "_run_megaplan", side_effect=fake_run):
        outcome = drive(
            plan,
            cwd=tmp_path,
            max_context_retries=2,
            poll_sleep=0,
            writer=lambda _m: None,
        )

    assert outcome.status == "context_retry_exhausted"
    assert outcome.context_retries_used == 2
    assert len(calls) == 3
    assert "--fresh" not in calls[0]
    assert "--fresh" in calls[1]
    assert "--fresh" in calls[2]


def test_context_retry_zero_disables_context_handling(tmp_path: Path) -> None:
    plan = "context-retry-disabled"
    _make_plan_dir(tmp_path, plan)
    calls: list[list[str]] = []
    fragment = "Codex ran out of room in the model's context window."

    def fake_status(plan_name: str, cwd=None, timeout=60):
        return _execute_status(plan)

    def fake_run(args, cwd=None, timeout=None):
        calls.append(list(args))
        return 1, "", fragment

    with patch.object(auto, "_status", side_effect=fake_status), \
         patch.object(auto, "_run_megaplan", side_effect=fake_run):
        outcome = drive(
            plan,
            cwd=tmp_path,
            max_context_retries=0,
            stall_threshold=1,
            poll_sleep=0,
            writer=lambda _m: None,
        )

    assert outcome.status == "stalled"
    assert outcome.status != "context_retry_exhausted"
    assert outcome.context_retries_used == 0
    assert len(calls) == 1
    assert all("--fresh" not in call for call in calls)


def test_generic_execute_failure_uses_stall_path_not_fresh_retry(tmp_path: Path) -> None:
    plan = "generic-execute-failure"
    _make_plan_dir(tmp_path, plan)
    calls: list[list[str]] = []

    def fake_status(plan_name: str, cwd=None, timeout=60):
        return _execute_status(plan)

    def fake_run(args, cwd=None, timeout=None):
        calls.append(list(args))
        return 1, "", "ordinary execute failure"

    with patch.object(auto, "_status", side_effect=fake_status), \
         patch.object(auto, "_run_megaplan", side_effect=fake_run):
        outcome = drive(
            plan,
            cwd=tmp_path,
            stall_threshold=1,
            poll_sleep=0,
            writer=lambda _m: None,
        )

    assert outcome.status == "stalled"
    assert outcome.context_retries_used == 0
    assert len(calls) == 1
    assert all("--fresh" not in call for call in calls)
    state_data = json.loads((tmp_path / ".megaplan" / "plans" / plan / "state.json").read_text(encoding="utf-8"))
    assert state_data["current_state"] == "blocked"
    assert state_data["latest_failure"]["kind"] == "stalled"
    assert state_data["resume_cursor"]["phase"] == "execute"


def test_phase_failure_persists_failure_before_next_status(tmp_path: Path) -> None:
    plan = "phase-failure-persists"
    plan_dir = _make_plan_dir(tmp_path, plan)
    statuses = [_phase_status(plan, state="planning", next_step="prep"), _terminal_status(plan, "failed")]

    def fake_status(plan_name: str, cwd=None, timeout=60):
        return statuses.pop(0)

    def fake_run(args, cwd=None, timeout=None):
        return 7, "", "prep exploded"

    with patch.object(auto, "_status", side_effect=fake_status), \
         patch.object(auto, "_run_megaplan", side_effect=fake_run):
        outcome = drive(plan, cwd=tmp_path, poll_sleep=0, writer=lambda _m: None)

    state_data = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    assert outcome.status == "failed"
    assert state_data["current_state"] == "failed"
    assert state_data["latest_failure"]["kind"] == "phase_failed"
    assert state_data["latest_failure"]["phase"] == "prep"
    assert state_data["latest_failure"]["metadata"]["exit_code"] == 7
    assert state_data["resume_cursor"] == {"phase": "prep", "retry_strategy": "rerun_phase"}


def test_cli_rejects_negative_max_context_retries() -> None:
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "megaplan",
            "auto",
            "--plan",
            "x",
            "--max-context-retries",
            "-1",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode != 0
    assert "--max-context-retries" in proc.stderr
    assert "non-negative" in proc.stderr


def test_cost_cap_aborts_after_cumulative_cost_exceeds_cap(tmp_path: Path) -> None:
    plan = "cost-cap-cumulative"
    plan_dir = _make_plan_dir(tmp_path, plan)
    _write_history(plan_dir, [])
    calls: list[list[str]] = []

    def fake_status(plan_name: str, cwd=None, timeout=60):
        return _phase_status(plan, state="planning", next_step="prep")

    def fake_run(args, cwd=None, timeout=None):
        calls.append(list(args))
        _append_history_cost(plan_dir, 1.0)
        return 0, "", ""

    with patch.object(auto, "_status", side_effect=fake_status), \
         patch.object(auto, "_run_megaplan", side_effect=fake_run):
        outcome = drive(
            plan,
            cwd=tmp_path,
            max_cost_usd=2.5,
            stall_threshold=100,
            poll_sleep=0,
            writer=lambda _m: None,
        )

    assert outcome.status == "cost_cap_exceeded"
    assert outcome.total_cost_usd == 3.0
    assert outcome.cost_cap_usd == 2.5
    assert len(calls) == 3


def test_cost_cap_equal_boundary_does_not_abort(tmp_path: Path) -> None:
    plan = "cost-cap-boundary"
    plan_dir = _make_plan_dir(tmp_path, plan)
    _write_history(plan_dir, [])
    calls: list[list[str]] = []
    statuses = [_phase_status(plan, state="planning", next_step="prep"), _done_status(plan)]

    def fake_status(plan_name: str, cwd=None, timeout=60):
        return statuses.pop(0)

    def fake_run(args, cwd=None, timeout=None):
        calls.append(list(args))
        _append_history_cost(plan_dir, 2.5)
        return 0, "", ""

    with patch.object(auto, "_status", side_effect=fake_status), \
         patch.object(auto, "_run_megaplan", side_effect=fake_run):
        outcome = drive(
            plan,
            cwd=tmp_path,
            max_cost_usd=2.5,
            poll_sleep=0,
            writer=lambda _m: None,
        )

    assert outcome.status != "cost_cap_exceeded"
    assert outcome.status == "done"
    assert outcome.total_cost_usd == 2.5
    assert len(calls) == 1


def test_cost_cap_single_expensive_phase_finishes_before_abort(tmp_path: Path) -> None:
    plan = "cost-cap-single-expensive"
    plan_dir = _make_plan_dir(tmp_path, plan)
    _write_history(plan_dir, [])
    calls: list[list[str]] = []

    def fake_status(plan_name: str, cwd=None, timeout=60):
        return _phase_status(plan, state="planning", next_step="prep")

    def fake_run(args, cwd=None, timeout=None):
        calls.append(list(args))
        _append_history_cost(plan_dir, 10.0)
        return 0, "", ""

    with patch.object(auto, "_status", side_effect=fake_status), \
         patch.object(auto, "_run_megaplan", side_effect=fake_run):
        outcome = drive(
            plan,
            cwd=tmp_path,
            max_cost_usd=5.0,
            stall_threshold=100,
            poll_sleep=0,
            writer=lambda _m: None,
        )

    assert outcome.status == "cost_cap_exceeded"
    assert outcome.total_cost_usd == 10.0
    assert outcome.cost_cap_usd == 5.0
    assert len(calls) == 1


def test_unset_cost_cap_does_not_terminate_on_high_cost(tmp_path: Path) -> None:
    plan = "cost-cap-unset"
    plan_dir = _make_plan_dir(tmp_path, plan)
    _write_history(plan_dir, [])
    calls: list[list[str]] = []
    statuses = [_phase_status(plan, state="planning", next_step="prep"), _done_status(plan)]

    def fake_status(plan_name: str, cwd=None, timeout=60):
        return statuses.pop(0)

    def fake_run(args, cwd=None, timeout=None):
        calls.append(list(args))
        _append_history_cost(plan_dir, 9999.0)
        return 0, "", ""

    with patch.object(auto, "_status", side_effect=fake_status), \
         patch.object(auto, "_run_megaplan", side_effect=fake_run):
        outcome = drive(
            plan,
            cwd=tmp_path,
            max_cost_usd=None,
            poll_sleep=0,
            writer=lambda _m: None,
        )

    assert outcome.status == "done"
    assert outcome.status != "cost_cap_exceeded"
    assert outcome.total_cost_usd == 9999.0
    assert len(calls) == 1


def test_cli_rejects_negative_max_cost_usd() -> None:
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "megaplan",
            "auto",
            "--plan",
            "x",
            "--max-cost-usd",
            "-1.0",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode != 0
    assert "--max-cost-usd" in proc.stderr
    assert "non-negative" in proc.stderr


def test_sum_history_cost_usd_handles_missing_corrupt_and_bad_entries(
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()

    assert auto._sum_history_cost_usd(plan_dir) == 0.0

    (plan_dir / "state.json").write_text("{bad json", encoding="utf-8")
    assert auto._sum_history_cost_usd(plan_dir) == 0.0

    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "history": [
                    {"cost_usd": "1.25"},
                    {"cost_usd": None},
                    {"cost_usd": "not-a-number"},
                    {"cost_usd": 2},
                    {"other": 99},
                    "not-a-dict",
                ],
                "meta": {"total_cost_usd": 9999},
            }
        ),
        encoding="utf-8",
    )
    assert auto._sum_history_cost_usd(plan_dir) == 3.25


def test_auto_help_surfaces_cost_and_context_retry_flags() -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "megaplan", "auto", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0
    assert "--max-context-retries" in proc.stdout
    assert "--max-cost-usd" in proc.stdout
    assert "--max-blocked-retries" in proc.stdout
    assert "context" in proc.stdout
    assert "cost" in proc.stdout


def _write_blocked_execute_history(plan_dir: Path, deviations: list[str] | None = None) -> None:
    """Stamp a history entry that mimics the executor finishing with result=blocked."""
    state_path = plan_dir / "state.json"
    state_data = json.loads(state_path.read_text(encoding="utf-8"))
    state_data.setdefault("history", []).append({"step": "execute", "result": "blocked", "cost_usd": 0.16})
    state_path.write_text(json.dumps(state_data), encoding="utf-8")
    if deviations is not None:
        (plan_dir / "execution_batch_1.json").write_text(
            json.dumps({"deviations": deviations}),
            encoding="utf-8",
        )


def test_worker_blocked_after_max_retries_emits_terminal_status(tmp_path: Path) -> None:
    plan = "worker-blocked-cap"
    plan_dir = _make_plan_dir(tmp_path, plan)
    _write_blocked_execute_history(
        plan_dir,
        deviations=[
            "done tasks missing both files_changed and commands_run: T1, T2",
            "Advisory: done tasks rely on commands_run without files_changed (FLAG-006 softening): T3",
        ],
    )

    def fake_status(plan_name: str, cwd=None, timeout=60):
        return _execute_status(plan)

    def fake_run(args, cwd=None, timeout=None):
        # Worker exits 0; the result=blocked is observable via history.
        return 0, "", ""

    with patch.object(auto, "_status", side_effect=fake_status), \
         patch.object(auto, "_run_megaplan", side_effect=fake_run):
        outcome = drive(
            plan,
            cwd=tmp_path,
            max_blocked_retries=1,
            poll_sleep=0,
            writer=lambda _m: None,
        )

    assert outcome.status == "worker_blocked"
    assert outcome.blocked_retries_used == 1
    # Only the BLOCKING deviations surface, not the FLAG-006 advisory.
    assert any("missing both files_changed" in r for r in outcome.blocking_reasons)
    assert not any("FLAG-006 softening" in r for r in outcome.blocking_reasons)
    state_data = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    assert state_data["current_state"] == "blocked"
    assert state_data["latest_failure"]["kind"] == "execution_blocked"
    assert state_data["latest_failure"]["last_artifact"] == "execution_batch_1.json"
    assert state_data["resume_cursor"]["phase"] == "execute"


def test_worker_blocked_does_not_loop_forever_with_zero_retries(tmp_path: Path) -> None:
    plan = "worker-blocked-zero"
    plan_dir = _make_plan_dir(tmp_path, plan)
    _write_blocked_execute_history(plan_dir)

    def fake_status(plan_name: str, cwd=None, timeout=60):
        return _execute_status(plan)

    def fake_run(args, cwd=None, timeout=None):
        return 0, "", ""

    with patch.object(auto, "_status", side_effect=fake_status), \
         patch.object(auto, "_run_megaplan", side_effect=fake_run):
        outcome = drive(
            plan,
            cwd=tmp_path,
            max_blocked_retries=0,
            poll_sleep=0,
            writer=lambda _m: None,
        )

    assert outcome.status == "worker_blocked"
    assert outcome.blocked_retries_used == 0


def test_worker_blocked_detection_skipped_when_execute_result_is_success(tmp_path: Path) -> None:
    """A clean execute (result=success) must NOT trigger the worker_blocked path."""
    plan = "execute-success-no-blocked"
    plan_dir = _make_plan_dir(tmp_path, plan)
    state_data = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    state_data.setdefault("history", []).append({"step": "execute", "result": "success", "cost_usd": 0.5})
    (plan_dir / "state.json").write_text(json.dumps(state_data), encoding="utf-8")
    statuses = [_execute_status(plan), _done_status(plan)]

    def fake_status(plan_name: str, cwd=None, timeout=60):
        return statuses.pop(0)

    def fake_run(args, cwd=None, timeout=None):
        return 0, "", ""

    with patch.object(auto, "_status", side_effect=fake_status), \
         patch.object(auto, "_run_megaplan", side_effect=fake_run):
        outcome = drive(plan, cwd=tmp_path, poll_sleep=0, writer=lambda _m: None)

    assert outcome.status == "done"
    assert outcome.blocked_retries_used == 0


def test_auto_strict_notes_blocks_force_proceed_after_escalate(tmp_path: Path) -> None:
    """When force-proceed is rejected by strict-notes, the auto driver should
    surface a `human_required` outcome rather than a generic `failed`."""
    plan = "strict-plan"
    _make_plan_dir(tmp_path, plan)

    def escalated_status(plan_name: str, cwd=None, timeout=60):
        return {
            "success": True,
            "step": "status",
            "plan": plan_name,
            "state": "critiqued",
            "iteration": 1,
            "summary": "Escalate awaiting override.",
            "next_step": None,
            "valid_next": ["override force-proceed", "override add-note", "override abort"],
        }

    def fake_run(args, cwd=None, timeout=None):
        # The first override-force-proceed call should fail with the strict
        # invariant error code in stderr.
        if args[:2] == ["override", "force-proceed"]:
            return 1, "", "CliError: escalate_requires_user_approval — user must approve"
        return 0, "{}", ""

    with patch.object(auto, "_status", side_effect=escalated_status), \
         patch.object(auto, "_run_megaplan", side_effect=fake_run):
        outcome = drive(
            plan,
            cwd=tmp_path,
            on_escalate="force-proceed",
            poll_sleep=0,
            writer=lambda _m: None,
        )

    assert outcome.status == "human_required", (
        f"expected human_required outcome, got {outcome.status}: {outcome.reason}"
    )
    assert "strict-notes" in outcome.reason


def test_last_history_step_result_handles_missing_and_corrupt(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    assert auto._last_history_step_result(plan_dir, "execute") is None
    (plan_dir / "state.json").write_text("{bad json", encoding="utf-8")
    assert auto._last_history_step_result(plan_dir, "execute") is None
    (plan_dir / "state.json").write_text(
        json.dumps({"history": [
            {"step": "plan", "result": "success"},
            {"step": "execute", "result": "blocked"},
            {"step": "review", "result": "approved"},
            {"step": "execute", "result": "success"},
        ]}),
        encoding="utf-8",
    )
    # Most recent execute wins; intervening review is ignored for the execute query.
    assert auto._last_history_step_result(plan_dir, "execute") == "success"
    assert auto._last_history_step_result(plan_dir, "review") == "approved"
