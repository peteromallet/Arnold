"""A null/un-capturable test baseline must NOT deadlock milestone completion.

Root cause (m7-agent-runtime-extraction, 2026-06-09/10): the baseline test
capture timed out (suite never finished within the ceiling) → finalize.json's
``baseline_test_failures`` was null → the "introduce no new failures vs the
recorded baseline" checkpoint task (T10) stayed ``blocked`` because it could not
be evaluated. The execute layer correctly treats such checkpoints as
acknowledged deviations (``prereq_blocked = active_blocked - baseline_blocked``),
but the chain completion gate (``_latest_execution_batch_all_tasks_done``)
re-checked finalize.json independently and counted T10 as "incomplete" →
``stop_chain`` → the whole 12-milestone migration deadlocked on a TRANSIENT
infra failure, with no operator (auto_approve) to clear it — even though the
milestone's real work (132 files, arnold/agent/ extracted) was done.

The fix exempts baseline-unavailable checkpoints from the chain's incomplete
check, matching the execute layer. A genuinely incomplete NON-baseline task must
still block.
"""
from __future__ import annotations

import json
from pathlib import Path

from megaplan.chain import _latest_execution_batch_all_tasks_done

_BASELINE_DESC = (
    "Introduce no new failures vs the recorded baseline; do not try to make "
    "pre-existing baseline failures pass; do not narrow to individual functions."
)


def _write_plan(plan_dir: Path, *, finalize_tasks: list[dict], baseline) -> None:
    (plan_dir / "execution_batch_1.json").write_text(
        json.dumps({"task_updates": [{"id": "T1", "status": "done"}]}),
        encoding="utf-8",
    )
    (plan_dir / "finalize.json").write_text(
        json.dumps({"baseline_test_failures": baseline, "tasks": finalize_tasks}),
        encoding="utf-8",
    )


def test_null_baseline_checkpoint_does_not_block_completion(tmp_path: Path) -> None:
    _write_plan(
        tmp_path,
        baseline=None,  # capture failed → un-evaluable
        finalize_tasks=[
            {"id": "T1", "status": "done"},
            # The no-new-failures checkpoint stuck 'blocked' because baseline is null.
            {"id": "T10", "status": "blocked", "description": _BASELINE_DESC},
        ],
    )
    all_done, reason = _latest_execution_batch_all_tasks_done(tmp_path)
    assert all_done is True, reason


def test_real_incomplete_non_baseline_task_still_blocks(tmp_path: Path) -> None:
    _write_plan(
        tmp_path,
        baseline=None,
        finalize_tasks=[
            {"id": "T1", "status": "done"},
            {"id": "T10", "status": "blocked", "description": _BASELINE_DESC},
            # A genuine, non-baseline incomplete task MUST still block.
            {"id": "T2", "status": "blocked", "description": "Implement the runner."},
        ],
    )
    all_done, reason = _latest_execution_batch_all_tasks_done(tmp_path)
    assert all_done is False
    assert "T2" in reason


def test_with_real_baseline_normal_block_still_applies(tmp_path: Path) -> None:
    # When a baseline WAS captured, the checkpoint is evaluable and a blocked
    # one blocks normally (exemption only applies to the un-capturable case).
    _write_plan(
        tmp_path,
        baseline=["tests/test_x.py::test_y"],
        finalize_tasks=[
            {"id": "T1", "status": "done"},
            {"id": "T10", "status": "blocked", "description": _BASELINE_DESC},
        ],
    )
    all_done, reason = _latest_execution_batch_all_tasks_done(tmp_path)
    assert all_done is False
    assert "T10" in reason
