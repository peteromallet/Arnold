"""Tests for megaplan.auto — the auto-driver loop.

Focus: the rework-cycle-aware stall detector added in v0.18.1. A plan in
``finalized`` state that's doing review→rework loops should not be flagged
as stalled just because ``state`` hasn't advanced — new ``review.json``
artifacts indicate real forward progress.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from megaplan import auto
from megaplan.auto import drive


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
