"""T11 — Four-outcome flag-on/flag-off ``StepResponse`` parity.

For ``success`` and ``blocked_by_quality`` (which
``handle_execute_one_batch`` produces natively at
``megaplan/execute/batch.py:779``), drives ``handle_execute_one_batch``
directly — the same pattern used by the T13 replay oracle.

For ``blocked_by_prereq`` and ``timeout`` (only produced by
``handle_execute_auto_loop`` at ``:1489–1497``), drives
``handle_execute_auto_loop`` against a single-batch fixture so the
auto-loop wraps a single one-batch call.  This keeps the strangler
envelope intact — the auto-loop path is legacy + unmodified (per T9a) —
while still exercising the four-outcome parity contract.

For each fixture, flag-OFF and flag-ON are run on two separate plan
instances within the same test function and the returned
``StepResponse`` objects are compared: same ``_phase_outcome``, same
``state`` (``current_state``), same ``warnings``, same ``artifacts``
set, same ``next_step``.

The payloads reuse real finalize-shape data cribbed from the existing
characterization tests (T9b, T13).
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
from megaplan.types import CliError, STATE_EXECUTED, STATE_FINALIZED
from megaplan.workers import WorkerResult

# ---------------------------------------------------------------------------
# Helpers — setup, workers, comparison
# ---------------------------------------------------------------------------


def _setup_plan_for_execute(
    plan_fixture,
    *,
    task_status: str = "pending",
    task_id: str = "T1",
    depends_on: list[str] | None = None,
) -> None:
    """Run plan/critique/finalize pipeline and inject a simple task.

    Lifted from T13 (``test_execute_replay_oracle.py``) — same
    finalize-shape payload.
    """
    make_args = plan_fixture.make_args
    megaplan.handle_plan(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(
        plan_fixture.root, make_args(plan=plan_fixture.plan_name)
    )
    megaplan.handle_override(
        plan_fixture.root,
        make_args(
            plan=plan_fixture.plan_name,
            override_action="force-proceed",
            reason="test",
        ),
    )
    megaplan.handle_finalize(
        plan_fixture.root, make_args(plan=plan_fixture.plan_name)
    )
    finalize_path = plan_fixture.plan_dir / "finalize.json"
    finalize_data = read_json(finalize_path)
    finalize_data["tasks"] = [
        {
            "id": task_id,
            "description": "Implement the target file.",
            "depends_on": depends_on if depends_on is not None else [],
            "status": task_status,
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


def _setup_multi_task_plan(plan_fixture, *, blocked_task_id: str = "T1") -> None:
    """Set up a two-task plan where T1 is blocked and T2 depends on T1.

    This triggers ``blocked_by_prereq`` in the auto-loop early-return
    path at ``batch.py:1074-1108``.
    """
    make_args = plan_fixture.make_args
    megaplan.handle_plan(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(
        plan_fixture.root, make_args(plan=plan_fixture.plan_name)
    )
    megaplan.handle_override(
        plan_fixture.root,
        make_args(
            plan=plan_fixture.plan_name,
            override_action="force-proceed",
            reason="test",
        ),
    )
    megaplan.handle_finalize(
        plan_fixture.root, make_args(plan=plan_fixture.plan_name)
    )
    finalize_path = plan_fixture.plan_dir / "finalize.json"
    finalize_data = read_json(finalize_path)

    # Write a matching current_invocation_id into state so the auto-loop
    # treats the blocked task as within-session (not cross-session).
    state_path = plan_fixture.plan_dir / "state.json"
    state = read_json(state_path)
    inv_id = state.setdefault("meta", {}).get("current_invocation_id")
    if not inv_id:
        import uuid
        inv_id = str(uuid.uuid4())
        state.setdefault("meta", {})["current_invocation_id"] = inv_id
        state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")

    finalize_data["tasks"] = [
        {
            "id": blocked_task_id,
            "description": "Blocked task.",
            "depends_on": [],
            "status": "blocked",
            "executor_notes": "Blocked by previous batch.",
            "files_changed": [],
            "commands_run": [],
            "evidence_files": [],
            "reviewer_verdict": "",
            "complexity": 3,
            "complexity_justification": "Standard task.",
            "recorded_invocation_id": inv_id,
        },
        {
            "id": "T2",
            "description": "Dependent task.",
            "depends_on": [blocked_task_id],
            "status": "pending",
            "executor_notes": "",
            "files_changed": [],
            "commands_run": [],
            "evidence_files": [],
            "reviewer_verdict": "",
            "complexity": 3,
            "complexity_justification": "Standard task.",
        },
    ]
    finalize_data["sense_checks"] = []
    finalize_path.write_text(json.dumps(finalize_data, indent=2) + "\n", encoding="utf-8")


def _stub_git_snapshots(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stub git-status snapshots.

    Lifted from T13 (``test_execute_replay_oracle.py``).
    """
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


def _success_worker(plan_fixture):
    """Worker that marks T1 done — success outcome."""

    def worker(step, state, plan_dir, args, *, root=None, resolved=None, prompt_override=None):
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


def _blocking_worker(plan_fixture):
    """Worker that blocks T1 via ``patch_corruption`` deviation —
    ``blocked_by_quality`` outcome."""

    def worker(step, state, plan_dir, args, *, root=None, resolved=None, prompt_override=None):
        del step, state, plan_dir, args, root, resolved, prompt_override
        payload = {
            "output": "Blocked.",
            "files_changed": [],
            "commands_run": [],
            "deviations": ["quality_gate: patch_corruption"],
            "task_updates": [
                {
                    "task_id": "T1",
                    "status": "blocked",
                    "executor_notes": "Blocked by worker.",
                    "files_changed": [],
                    "commands_run": [],
                    "auto_attributed_files": None,
                }
            ],
            "sense_check_acknowledgments": [],
        }
        return (
            WorkerResult(
                payload=payload,
                raw_output="blocked",
                duration_ms=1,
                cost_usd=0.0,
                session_id="test-blocked-worker",
            ),
            "codex",
            "persistent",
            False,
        )

    return worker


# ---------------------------------------------------------------------------
# StepResponse comparison
# ---------------------------------------------------------------------------


def _parity_fields(response: dict) -> dict:
    """Extract the five parity-contract fields from a StepResponse."""
    return {
        "_phase_outcome": response.get("_phase_outcome"),
        "state": response.get("state"),
        "next_step": response.get("next_step"),
        "warnings": sorted(response.get("warnings", [])),
        "artifacts": sorted(response.get("artifacts", [])),
    }


def _assert_parity(resp_off: dict, resp_on: dict) -> None:
    """Assert flag-off and flag-on responses are identical on the
    five parity-contract fields."""
    off_fields = _parity_fields(resp_off)
    on_fields = _parity_fields(resp_on)

    assert off_fields["_phase_outcome"] == on_fields["_phase_outcome"], (
        f"_phase_outcome mismatch: {off_fields['_phase_outcome']!r} "
        f"vs {on_fields['_phase_outcome']!r}"
    )
    assert off_fields["state"] == on_fields["state"], (
        f"state mismatch: {off_fields['state']!r} vs {on_fields['state']!r}"
    )
    assert off_fields["next_step"] == on_fields["next_step"], (
        f"next_step mismatch: {off_fields['next_step']!r} vs {on_fields['next_step']!r}"
    )
    assert off_fields["warnings"] == on_fields["warnings"], (
        f"warnings mismatch: {off_fields['warnings']!r} vs {on_fields['warnings']!r}"
    )
    assert off_fields["artifacts"] == on_fields["artifacts"], (
        f"artifacts mismatch: {off_fields['artifacts']!r} vs {on_fields['artifacts']!r}"
    )


# ---------------------------------------------------------------------------
# One-batch driver (success + blocked_by_quality)
# ---------------------------------------------------------------------------


def _drive_one_batch(plan_fixture, *, flag_on: bool, monkeypatch: pytest.MonkeyPatch) -> dict:
    """Call ``handle_execute_one_batch`` and return the StepResponse."""
    monkeypatch.setattr(
        megaplan.execute.batch, "unified_execute_enabled", lambda: flag_on
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
# Auto-loop driver (blocked_by_prereq + timeout)
# ---------------------------------------------------------------------------


def _drive_auto_loop(plan_fixture, *, flag_on: bool, monkeypatch: pytest.MonkeyPatch) -> dict:
    """Call ``handle_execute_auto_loop`` and return the StepResponse.

    The auto-loop is wrapped around a single-batch fixture so the
    strangler envelope stays intact (auto-loop path is legacy +
    unmodified per T9a) while still exercising the four-outcome parity
    contract.
    """
    monkeypatch.setattr(
        megaplan.execute.batch, "unified_execute_enabled", lambda: flag_on
    )
    state = read_json(plan_fixture.plan_dir / "state.json")
    return megaplan.execute.core.handle_execute_auto_loop(
        root=plan_fixture.root,
        plan_dir=plan_fixture.plan_dir,
        state=state,
        args=plan_fixture.make_args(
            plan=plan_fixture.plan_name,
            confirm_destructive=True,
            user_approved=True,
        ),
        auto_approve=False,
        agent="codex",
        mode="persistent",
        refreshed=False,
    )


# ---------------------------------------------------------------------------
# Tests — success outcome
# ---------------------------------------------------------------------------


class TestSuccessOutcomeParity:
    """``success`` via ``handle_execute_one_batch`` — flag-on/off parity."""

    def test_success_parity(
        self, plan_fixture, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        # Create the flag-ON plan fixture BEFORE monkeypatching
        # ``run_step_with_worker`` — otherwise the mock worker that returns
        # execute payloads breaks ``handle_init`` → ``handle_plan`` inside
        # ``_make_plan_fixture_with_robustness``.
        from tests.conftest import _make_plan_fixture_with_robustness
        sub = tmp_path / "flag_on"
        sub.mkdir()
        fixture_on = _make_plan_fixture_with_robustness(sub, monkeypatch, robustness="standard")
        _setup_plan_for_execute(fixture_on)

        # Now set up both plan instances with their respective workers and drive.
        _setup_plan_for_execute(plan_fixture)
        _stub_git_snapshots(monkeypatch)

        # --- flag-OFF ---
        monkeypatch.setattr(
            megaplan.workers, "run_step_with_worker",
            _success_worker(plan_fixture),
        )
        resp_off = _drive_one_batch(plan_fixture, flag_on=False, monkeypatch=monkeypatch)

        # --- flag-ON ---
        monkeypatch.setattr(
            megaplan.workers, "run_step_with_worker",
            _success_worker(fixture_on),
        )
        _stub_git_snapshots(monkeypatch)
        resp_on = _drive_one_batch(fixture_on, flag_on=True, monkeypatch=monkeypatch)

        _assert_parity(resp_off, resp_on)

        # Also assert the expected specific values
        assert resp_off["_phase_outcome"] == "success"
        assert resp_on["_phase_outcome"] == "success"
        assert resp_off["state"] == STATE_EXECUTED
        assert resp_on["state"] == STATE_EXECUTED
        assert resp_off["next_step"] == "review"
        assert resp_on["next_step"] == "review"


# ---------------------------------------------------------------------------
# Tests — blocked_by_quality outcome
# ---------------------------------------------------------------------------


class TestBlockedByQualityOutcomeParity:
    """``blocked_by_quality`` via ``handle_execute_one_batch`` —
    flag-on/off parity."""

    def test_blocked_by_quality_parity(
        self, plan_fixture, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        # Create the flag-ON fixture BEFORE monkeypatching run_step_with_worker.
        from tests.conftest import _make_plan_fixture_with_robustness
        sub = tmp_path / "flag_on"
        sub.mkdir()
        fixture_on = _make_plan_fixture_with_robustness(sub, monkeypatch, robustness="standard")
        _setup_plan_for_execute(fixture_on)

        _setup_plan_for_execute(plan_fixture)
        _stub_git_snapshots(monkeypatch)

        # --- flag-OFF ---
        monkeypatch.setattr(
            megaplan.workers, "run_step_with_worker",
            _blocking_worker(plan_fixture),
        )
        resp_off = _drive_one_batch(plan_fixture, flag_on=False, monkeypatch=monkeypatch)

        # --- flag-ON ---
        monkeypatch.setattr(
            megaplan.workers, "run_step_with_worker",
            _blocking_worker(fixture_on),
        )
        _stub_git_snapshots(monkeypatch)
        resp_on = _drive_one_batch(fixture_on, flag_on=True, monkeypatch=monkeypatch)

        _assert_parity(resp_off, resp_on)

        assert resp_off["_phase_outcome"] == "blocked_by_quality"
        assert resp_on["_phase_outcome"] == "blocked_by_quality"
        assert resp_off["state"] == STATE_FINALIZED
        assert resp_on["state"] == STATE_FINALIZED
        assert resp_off["next_step"] == "execute"
        assert resp_on["next_step"] == "execute"


# ---------------------------------------------------------------------------
# Tests — blocked_by_prereq outcome
# ---------------------------------------------------------------------------


class TestBlockedByPrereqOutcomeParity:
    """``blocked_by_prereq`` via ``handle_execute_auto_loop`` —
    flag-on/off parity.

    The auto-loop short-circuits when it finds within-session blocked
    tasks, returning ``_phase_outcome='blocked_by_prereq'`` at
    ``batch.py:1074-1108``.  The auto-loop is legacy + unmodified (per
    T9a), so flag-on and flag-off should produce byte-identical results.
    """

    def test_blocked_by_prereq_parity(
        self, plan_fixture, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        # Create the flag-ON fixture BEFORE monkeypatching.
        from tests.conftest import _make_plan_fixture_with_robustness
        sub = tmp_path / "flag_on"
        sub.mkdir()
        fixture_on = _make_plan_fixture_with_robustness(sub, monkeypatch, robustness="standard")
        _setup_multi_task_plan(fixture_on, blocked_task_id="T1")

        # --- flag-OFF ---
        _setup_multi_task_plan(plan_fixture, blocked_task_id="T1")
        resp_off = _drive_auto_loop(plan_fixture, flag_on=False, monkeypatch=monkeypatch)

        # --- flag-ON ---
        resp_on = _drive_auto_loop(fixture_on, flag_on=True, monkeypatch=monkeypatch)

        _assert_parity(resp_off, resp_on)

        assert resp_off["_phase_outcome"] == "blocked_by_prereq"
        assert resp_on["_phase_outcome"] == "blocked_by_prereq"
        assert resp_off["state"] == STATE_FINALIZED
        assert resp_on["state"] == STATE_FINALIZED
        assert resp_off["next_step"] == "execute"
        assert resp_on["next_step"] == "execute"


# ---------------------------------------------------------------------------
# Tests — timeout outcome
# ---------------------------------------------------------------------------


class TestTimeoutOutcomeParity:
    """``timeout`` via ``handle_execute_auto_loop`` — flag-on/off parity.

    Simulates a worker-timeout by monkeypatching ``_run_and_merge_batch``
    to raise ``CliError('worker_timeout')``.  The auto-loop catches this
    and returns ``_phase_outcome='timeout'`` at ``batch.py:1509-1514``.
    """

    def test_timeout_parity(
        self, plan_fixture, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        # Create the flag-ON fixture BEFORE monkeypatching.
        from tests.conftest import _make_plan_fixture_with_robustness
        sub = tmp_path / "flag_on"
        sub.mkdir()
        fixture_on = _make_plan_fixture_with_robustness(sub, monkeypatch, robustness="standard")
        _setup_plan_for_execute(fixture_on)

        _setup_plan_for_execute(plan_fixture)
        _stub_git_snapshots(monkeypatch)

        def _raise_timeout(*args, **kwargs):
            del args, kwargs
            raise CliError(
                "worker_timeout",
                "Worker timed out after 300s",
                extra={"session_id": "timeout-session"},
            )

        # --- flag-OFF ---
        monkeypatch.setattr(
            megaplan.execute.batch, "_run_and_merge_batch", _raise_timeout
        )
        resp_off = _drive_auto_loop(plan_fixture, flag_on=False, monkeypatch=monkeypatch)

        # --- flag-ON ---
        _stub_git_snapshots(monkeypatch)  # reset snapshot index for second fixture
        monkeypatch.setattr(
            megaplan.execute.batch, "_run_and_merge_batch", _raise_timeout
        )
        resp_on = _drive_auto_loop(fixture_on, flag_on=True, monkeypatch=monkeypatch)

        _assert_parity(resp_off, resp_on)

        assert resp_off["_phase_outcome"] == "timeout"
        assert resp_on["_phase_outcome"] == "timeout"
        assert resp_off["state"] == STATE_FINALIZED
        assert resp_on["state"] == STATE_FINALIZED
        assert resp_off["next_step"] == "execute"
        assert resp_on["next_step"] == "execute"
