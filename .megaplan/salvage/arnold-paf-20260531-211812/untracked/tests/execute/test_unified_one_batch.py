"""SC9 — unified scheduler path parity in handle_execute_one_batch.

Verifies that under MEGAPLAN_UNIFIED_EXECUTE=1:
  - run_scheduler is called (the new scheduler path is actually taken).
  - _run_and_merge_batch is called with _classification_mode='reducer'.
  - Response fields (_phase_outcome, state, batches_remaining, user_approved_gate,
    STATE_EXECUTED transition) match flag-off on a SUCCESS outcome.
  - A worker_timeout CliError triggers _recover_execute_timeout early return.
  - _recover_execute_timeout guard fires before the scheduler result is consumed.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import megaplan
import megaplan.execute.aggregation
import megaplan.execute.batch
import megaplan.execute.core
import megaplan.workers
from megaplan._core import read_json
from megaplan.types import STATE_EXECUTED, CliError
from megaplan.workers import WorkerResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _setup_plan_for_execute(plan_fixture) -> None:
    """Run plan/critique/finalize pipeline and inject a simple single task."""
    make_args = plan_fixture.make_args
    megaplan.handle_plan(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_override(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, override_action="force-proceed", reason="test"),
    )
    megaplan.handle_finalize(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    finalize_path = plan_fixture.plan_dir / "finalize.json"
    finalize_data = read_json(finalize_path)
    finalize_data["tasks"] = [
        {
            "id": "T1",
            "description": "Implement the target file.",
            "depends_on": [],
            "status": "pending",
            "executor_notes": "",
            "files_changed": [],
            "commands_run": [],
            "evidence_files": [],
            "reviewer_verdict": "",
            "complexity": 3,
            "complexity_justification": "Standard task.",
        }
    ]
    finalize_data["sense_checks"] = []
    finalize_path.write_text(json.dumps(finalize_data, indent=2) + "\n", encoding="utf-8")


def _done_worker(project_dir: Path):
    """Worker that creates a file on disk and marks T1 done with file evidence."""
    def worker(step, state, plan_dir, args, *, root=None, resolved=None, prompt_override=None):
        del step, state, plan_dir, args, root, resolved, prompt_override
        new_file = project_dir / "impl.py"
        new_file.write_text("# generated\n", encoding="utf-8")
        payload = {
            "output": "Done.",
            "files_changed": ["impl.py"],
            "commands_run": [],
            "deviations": [],
            "task_updates": [
                {
                    "task_id": "T1",
                    "status": "done",
                    "executor_notes": "Completed.",
                    "files_changed": ["impl.py"],
                    "commands_run": [],
                    "auto_attributed_files": None,
                }
            ],
            "sense_check_acknowledgments": [],
        }
        return (
            WorkerResult(
                payload=payload,
                raw_output="done",
                duration_ms=1,
                cost_usd=0.0,
                session_id="test-worker",
            ),
            "codex",
            "persistent",
            False,
        )
    return worker


def _stub_git_snapshots(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stub git-status snapshots to report impl.py as a new file."""
    before = ({}, None)
    after = ({"impl.py": "<hash>"}, None)
    # before-worker / after-worker / scope snapshot: iterate through the 3 calls
    snapshots_iter: list = [before, after, after]
    idx = [0]

    def _rotating_snap(*_):
        val = snapshots_iter[min(idx[0], len(snapshots_iter) - 1)]
        idx[0] += 1
        return val

    monkeypatch.setattr(megaplan.execute.batch, "_capture_git_status_snapshot", _rotating_snap)
    monkeypatch.setattr(megaplan.execute.aggregation, "_capture_git_status_snapshot", _rotating_snap)
    monkeypatch.setattr(
        megaplan.execute.batch,
        "_capture_git_status_snapshot_recursive",
        lambda *_: ({"impl.py": "<hash>"}, None),
    )


def _call_one_batch(plan_fixture, *, flag_on: bool, monkeypatch: pytest.MonkeyPatch):
    """Call handle_execute_one_batch with the given unified-execute flag."""
    monkeypatch.setattr(
        megaplan.execute.batch,
        "unified_execute_enabled",
        lambda: flag_on,
    )
    state = read_json(plan_fixture.plan_dir / "state.json")
    return megaplan.execute.core.handle_execute_one_batch(
        root=plan_fixture.root,
        plan_dir=plan_fixture.plan_dir,
        state=state,
        args=plan_fixture.make_args(
            plan=plan_fixture.plan_name,
            confirm_destructive=True,
            user_approved=True,
            batch=1,
        ),
        batch_number=1,
        auto_approve=False,
        agent="codex",
        mode="persistent",
        refreshed=False,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_unified_path_calls_run_scheduler(
    plan_fixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When flag=on, run_scheduler is called once inside handle_execute_one_batch."""
    _setup_plan_for_execute(plan_fixture)
    _stub_git_snapshots(monkeypatch)
    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", _done_worker(plan_fixture.project_dir))

    scheduler_calls: list = []
    original = megaplan.execute.batch.run_scheduler

    def _spy(**kwargs):
        scheduler_calls.append(kwargs)
        return original(**kwargs)

    monkeypatch.setattr(megaplan.execute.batch, "run_scheduler", _spy)

    response = _call_one_batch(plan_fixture, flag_on=True, monkeypatch=monkeypatch)

    assert len(scheduler_calls) == 1, "run_scheduler must be called exactly once"
    assert response["success"] is True
    assert response["state"] == STATE_EXECUTED
    assert response["_phase_outcome"] == "success"
    assert response["batches_remaining"] == 0
    assert response["user_approved_gate"] is False


def test_unified_path_passes_reducer_mode_to_merge(
    plan_fixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When flag=on, _run_and_merge_batch is called with _classification_mode='reducer'."""
    _setup_plan_for_execute(plan_fixture)
    _stub_git_snapshots(monkeypatch)
    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", _done_worker(plan_fixture.project_dir))

    merge_calls: list = []
    original_merge = megaplan.execute.batch._run_and_merge_batch

    def _spy_merge(**kwargs):
        merge_calls.append(kwargs.get("_classification_mode"))
        return original_merge(**kwargs)

    monkeypatch.setattr(megaplan.execute.batch, "_run_and_merge_batch", _spy_merge)

    _call_one_batch(plan_fixture, flag_on=True, monkeypatch=monkeypatch)

    assert len(merge_calls) == 1
    assert merge_calls[0] == "reducer", (
        "_run_and_merge_batch must be called with _classification_mode='reducer' under unified path"
    )


def test_unified_response_matches_expected_success_fields(
    plan_fixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Flag-on produces the same critical success fields as the legacy path on SUCCESS.

    The legacy-path counterpart is tested in test_legacy_path_not_broken_by_unified_import.
    Both must satisfy the same expected contract — STATE_EXECUTED, _phase_outcome='success',
    next_step='review', batches_remaining=0.
    """
    _setup_plan_for_execute(plan_fixture)
    _stub_git_snapshots(monkeypatch)
    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", _done_worker(plan_fixture.project_dir))

    response = _call_one_batch(plan_fixture, flag_on=True, monkeypatch=monkeypatch)

    assert response["success"] is True
    assert response["state"] == STATE_EXECUTED
    assert response["_phase_outcome"] == "success"
    assert response["next_step"] == "review"
    assert response["batches_remaining"] == 0
    assert response["batches_total"] == 1
    assert response["user_approved_gate"] is False


def test_unified_path_worker_timeout_early_return(
    plan_fixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Flag-on: worker_timeout raises CliError → _recover_execute_timeout fires,
    response has _phase_outcome='timeout' (guard runs before scheduler result is consumed)."""
    _setup_plan_for_execute(plan_fixture)
    _stub_git_snapshots(monkeypatch)

    # Worker raises worker_timeout
    def _timeout_worker(step, state, plan_dir, args, *, root=None, resolved=None, prompt_override=None):
        raise CliError("worker_timeout", "Timed out")

    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", _timeout_worker)

    # Stub _recover_execute_timeout to return a sentinel response without touching disk
    recover_calls: list = []

    def _stub_recover(*, plan_dir, state, error, agent, mode, refreshed, auto_approve, args, batch_number):
        recover_calls.append(batch_number)
        return {
            "success": False,
            "step": "execute",
            "summary": "timeout",
            "artifacts": [],
            "monitor_hint": "",
            "next_step": "execute",
            "state": "finalized",
            "batch": batch_number,
            "batches_total": 1,
            "batches_remaining": 1,
            "files_changed": [],
            "deviations": [],
            "warnings": [],
            "auto_approve": False,
            "user_approved_gate": False,
            "blocked_task_ids": [],
        }

    monkeypatch.setattr(megaplan.execute.batch, "_recover_execute_timeout", _stub_recover)

    response = _call_one_batch(plan_fixture, flag_on=True, monkeypatch=monkeypatch)

    assert len(recover_calls) == 1, "_recover_execute_timeout must be called once"
    assert response["_phase_outcome"] == "timeout"
    assert response["step"] == "execute"


def test_legacy_path_not_broken_by_unified_import(
    plan_fixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Flag-off: the legacy path still works after the unified branch was added."""
    _setup_plan_for_execute(plan_fixture)
    _stub_git_snapshots(monkeypatch)
    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", _done_worker(plan_fixture.project_dir))

    response = _call_one_batch(plan_fixture, flag_on=False, monkeypatch=monkeypatch)

    assert response["success"] is True
    assert response["state"] == STATE_EXECUTED
    assert response["_phase_outcome"] == "success"
    assert response["next_step"] == "review"
