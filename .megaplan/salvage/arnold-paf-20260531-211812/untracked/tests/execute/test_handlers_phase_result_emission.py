"""T9b — phase_result.json emission parity under unified execute.

Confirms that when ``MEGAPLAN_UNIFIED_EXECUTE=1`` the unified path emits
a ``phase_result.json`` whose ``exit_kind`` (the ``kind`` in the task
description) and ``blocked_tasks`` structure match the legacy path for
one representative fixture (a single-batch SUCCESS outcome).

The emission flows through ``megaplan/handlers/execute.py:276-316``
(``_emit_phase_result`` with typed ``ExitKind`` / ``BlockedTask`` /
``Deviation``), which is the common code after both the legacy and
unified branches.  This test calls ``megaplan.handle_execute`` (the full
handler dispatch) so the emission code runs.
"""

from __future__ import annotations

import json

import pytest

import megaplan
import megaplan.execute.aggregation
import megaplan.execute.batch
import megaplan.workers
from megaplan._core import read_json
from megaplan.orchestration.phase_result import PhaseResult, read_phase_result
from megaplan.types import STATE_EXECUTED
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
        make_args(
            plan=plan_fixture.plan_name, override_action="force-proceed", reason="test"
        ),
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


def _done_worker(plan_fixture):
    """Worker that creates a file on disk and marks T1 done."""

    def worker(
        step,
        state,
        plan_dir,
        args,
        *,
        root=None,
        resolved=None,
        prompt_override=None,
    ):
        del step, state, plan_dir, args, root, resolved, prompt_override
        new_file = plan_fixture.project_dir / "impl.py"
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
    """Stub git-status snapshots."""
    before = ({}, None)
    after = ({"impl.py": "<hash>"}, None)
    snapshots_iter: list = [before, after, after]
    idx = [0]

    def _rotating_snap(*_):
        val = snapshots_iter[min(idx[0], len(snapshots_iter) - 1)]
        idx[0] += 1
        return val

    monkeypatch.setattr(
        megaplan.execute.batch, "_capture_git_status_snapshot", _rotating_snap
    )
    monkeypatch.setattr(
        megaplan.execute.aggregation,
        "_capture_git_status_snapshot",
        _rotating_snap,
    )
    monkeypatch.setattr(
        megaplan.execute.batch,
        "_capture_git_status_snapshot_recursive",
        lambda *_: ({"impl.py": "<hash>"}, None),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestPhaseResultEmissionParity:
    """Both paths must emit structurally identical phase_result.json."""

    def test_legacy_path_phase_result(
        self, plan_fixture, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Legacy path (flag off) emits phase_result.json with
        exit_kind='success' and empty blocked_tasks."""
        _setup_plan_for_execute(plan_fixture)
        _stub_git_snapshots(monkeypatch)
        monkeypatch.setattr(
            megaplan.workers, "run_step_with_worker", _done_worker(plan_fixture)
        )
        monkeypatch.setattr(
            megaplan.execute.batch, "unified_execute_enabled", lambda: False
        )

        response = megaplan.handle_execute(
            plan_fixture.root,
            plan_fixture.make_args(
                plan=plan_fixture.plan_name,
                confirm_destructive=True,
                user_approved=True,
                batch=1,
            ),
        )
        pr = read_phase_result(plan_fixture.plan_dir)

        assert pr is not None, "Legacy path must emit a phase_result.json"
        assert isinstance(pr, PhaseResult)
        assert pr.exit_kind == "success", f"Expected 'success', got {pr.exit_kind!r}"
        assert pr.blocked_tasks == (), "blocked_tasks must be empty for SUCCESS"
        assert pr.phase == "execute"
        assert response["state"] == STATE_EXECUTED
        assert response["success"] is True

    def test_unified_path_phase_result(
        self, plan_fixture, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Unified path (flag on) emits phase_result.json with
        exit_kind='success' and empty blocked_tasks — same structure as
        legacy."""
        _setup_plan_for_execute(plan_fixture)
        _stub_git_snapshots(monkeypatch)
        monkeypatch.setattr(
            megaplan.workers, "run_step_with_worker", _done_worker(plan_fixture)
        )
        monkeypatch.setattr(
            megaplan.execute.batch, "unified_execute_enabled", lambda: True
        )

        response = megaplan.handle_execute(
            plan_fixture.root,
            plan_fixture.make_args(
                plan=plan_fixture.plan_name,
                confirm_destructive=True,
                user_approved=True,
                batch=1,
            ),
        )
        pr = read_phase_result(plan_fixture.plan_dir)

        assert pr is not None, "Unified path must emit a phase_result.json"
        assert isinstance(pr, PhaseResult)
        assert pr.exit_kind == "success", f"Expected 'success', got {pr.exit_kind!r}"
        assert pr.blocked_tasks == (), "blocked_tasks must be empty for SUCCESS"
        assert pr.phase == "execute"
        assert response["state"] == STATE_EXECUTED
        assert response["success"] is True
