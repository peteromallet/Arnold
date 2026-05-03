from __future__ import annotations

import json
import subprocess
from argparse import Namespace
from pathlib import Path

import pytest

import megaplan
import megaplan._core
import megaplan.execute.core
import megaplan.handlers
import megaplan.workers
from megaplan._core import load_plan
from megaplan.execute.quality import (
    _auto_attribute_unclaimed_paths,
    _capture_git_status_snapshot,
    _capture_git_status_snapshot_recursive,
    _check_done_task_evidence,
)
from megaplan.workers import WorkerResult
from tests.conftest import (
    PlanFixture,
    _make_plan_fixture_with_robustness,
    _write_lines,
    load_state,
    make_args_factory,
    read_json,
)


def _missing_code_task_evidence(tasks: list[dict[str, object]]) -> list[str]:
    issues: list[str] = []
    return _check_done_task_evidence(
        tasks,
        issues=issues,
        should_classify=lambda task: True,
        has_evidence=lambda task: bool(task.get("files_changed")),
        has_advisory_evidence=megaplan.execute.core._has_code_task_advisory_evidence,
        missing_message="missing: ",
        advisory_message="advisory: ",
    )


def test_auto_attribute_single_done_task_with_unclaimed_changes(tmp_path: Path) -> None:
    finalize_data = {
        "tasks": [
            {
                "id": "T1",
                "status": "done",
                "files_changed": [],
                "commands_run": [],
            }
        ]
    }
    payload = {
        "files_changed": [],
        "task_updates": [
            {
                "task_id": "T1",
                "status": "done",
                "executor_notes": "done",
                "files_changed": [],
                "commands_run": [],
            }
        ],
    }
    deviations: list[str] = []

    result = _auto_attribute_unclaimed_paths(
        project_dir=tmp_path,
        finalize_data=finalize_data,
        payload=payload,
        batch_task_ids=["T1"],
        issues=deviations,
        capture_recursive_snapshot_fn=lambda _p: ({"new.py": "<hash>"}, None),
    )

    task = finalize_data["tasks"][0]
    update = payload["task_updates"][0]
    assert task["files_changed"] == ["new.py"]
    assert task["auto_attributed_files"] is True
    assert update["files_changed"] == ["new.py"]
    assert update["auto_attributed_files"] is True
    assert payload["files_changed"] == ["new.py"]
    assert result.records == [
        {"task_id": "T1", "files": ["new.py"], "ambiguous": False}
    ]
    assert result.recursive_snapshot == {"new.py": "<hash>"}
    assert _missing_code_task_evidence(finalize_data["tasks"]) == []


def test_done_task_evidence_accepts_evidence_files_and_notes() -> None:
    tasks = [
        {
            "id": "T1",
            "status": "done",
            "files_changed": [],
            "commands_run": [],
            "evidence_files": ["finalize.json"],
            "executor_notes": "",
        },
        {
            "id": "T2",
            "status": "done",
            "files_changed": [],
            "commands_run": [],
            "evidence_files": [],
            "executor_notes": "Human-only follow-up was surfaced.",
        },
    ]

    assert _missing_code_task_evidence(tasks) == []


def test_auto_attribute_multiple_done_tasks_share_unclaimed_paths(tmp_path: Path) -> None:
    finalize_data = {
        "tasks": [
            {"id": "T1", "status": "done", "files_changed": [], "commands_run": []},
            {"id": "T2", "status": "done", "files_changed": [], "commands_run": []},
        ]
    }
    payload = {
        "files_changed": [],
        "task_updates": [
            {"task_id": "T1", "files_changed": [], "commands_run": []},
            {"task_id": "T2", "files_changed": [], "commands_run": []},
        ],
    }
    deviations: list[str] = []

    result = _auto_attribute_unclaimed_paths(
        project_dir=tmp_path,
        finalize_data=finalize_data,
        payload=payload,
        batch_task_ids=["T1", "T2"],
        issues=deviations,
        capture_recursive_snapshot_fn=lambda _p: (
            {"b.py": "<hash-b>", "a.py": "<hash-a>"},
            None,
        ),
    )

    assert finalize_data["tasks"][0]["files_changed"] == ["a.py", "b.py"]
    assert finalize_data["tasks"][1]["files_changed"] == ["a.py", "b.py"]
    assert payload["task_updates"][0]["auto_attributed_files"] is True
    assert payload["task_updates"][1]["auto_attributed_files"] is True
    assert len(
        [
            deviation
            for deviation in deviations
            if deviation.startswith("Auto-attributed 2 unclaimed file(s) to task")
        ]
    ) == 2
    assert (
        deviations.count("Auto-attribution ambiguous: 2 done tasks shared 2 unclaimed files")
        == 1
    )
    assert result.records == [
        {"task_id": "T1", "files": ["a.py", "b.py"], "ambiguous": True},
        {"task_id": "T2", "files": ["a.py", "b.py"], "ambiguous": True},
    ]


def test_auto_attribute_clean_worktree_keeps_missing_evidence(tmp_path: Path) -> None:
    finalize_data = {
        "tasks": [
            {"id": "T1", "status": "done", "files_changed": [], "commands_run": []}
        ]
    }
    payload = {
        "files_changed": [],
        "task_updates": [{"task_id": "T1", "files_changed": [], "commands_run": []}],
    }
    deviations: list[str] = []

    result = _auto_attribute_unclaimed_paths(
        project_dir=tmp_path,
        finalize_data=finalize_data,
        payload=payload,
        batch_task_ids=["T1"],
        issues=deviations,
        capture_recursive_snapshot_fn=lambda _p: ({}, None),
    )

    assert finalize_data["tasks"][0]["files_changed"] == []
    assert "auto_attributed_files" not in finalize_data["tasks"][0]
    assert payload["task_updates"][0]["files_changed"] == []
    assert result.records == []
    assert result.recursive_snapshot == {}
    assert _missing_code_task_evidence(finalize_data["tasks"]) == ["T1"]


def test_auto_attribute_populated_files_changed_short_circuits(tmp_path: Path) -> None:
    finalize_data = {
        "tasks": [
            {
                "id": "T1",
                "status": "done",
                "files_changed": ["claimed.py"],
                "commands_run": [],
            }
        ]
    }
    payload = {
        "files_changed": [],
        "task_updates": [
            {"task_id": "T1", "files_changed": ["claimed.py"], "commands_run": []}
        ],
    }
    deviations: list[str] = []
    calls = 0

    def snapshot(_project_dir: Path) -> tuple[dict[str, str], str | None]:
        nonlocal calls
        calls += 1
        return {"new.py": "<hash>"}, None

    result = _auto_attribute_unclaimed_paths(
        project_dir=tmp_path,
        finalize_data=finalize_data,
        payload=payload,
        batch_task_ids=["T1"],
        issues=deviations,
        capture_recursive_snapshot_fn=snapshot,
    )

    assert calls == 0
    assert finalize_data["tasks"][0]["files_changed"] == ["claimed.py"]
    assert payload["task_updates"][0]["files_changed"] == ["claimed.py"]
    assert deviations == []
    assert result.records == []
    assert result.recursive_snapshot is None


def test_auto_attribute_skipped_tasks_ignored(tmp_path: Path) -> None:
    finalize_data = {
        "tasks": [
            {"id": "T1", "status": "skipped", "files_changed": [], "commands_run": []}
        ]
    }
    payload = {
        "files_changed": [],
        "task_updates": [{"task_id": "T1", "files_changed": [], "commands_run": []}],
    }
    deviations: list[str] = []

    result = _auto_attribute_unclaimed_paths(
        project_dir=tmp_path,
        finalize_data=finalize_data,
        payload=payload,
        batch_task_ids=["T1"],
        issues=deviations,
        capture_recursive_snapshot_fn=lambda _p: ({"new.py": "<hash>"}, None),
    )

    assert finalize_data["tasks"][0]["files_changed"] == []
    assert payload["task_updates"][0]["files_changed"] == []
    assert deviations == []
    assert result.records == []
    assert result.recursive_snapshot is None


def test_auto_attribute_excludes_files_claimed_by_other_tasks(tmp_path: Path) -> None:
    finalize_data = {
        "tasks": [
            {"id": "T1", "status": "done", "files_changed": ["a.py"], "commands_run": []},
            {"id": "T2", "status": "done", "files_changed": [], "commands_run": []},
        ]
    }
    payload = {
        "files_changed": ["existing.py"],
        "task_updates": [
            {"task_id": "T1", "files_changed": ["a.py"], "commands_run": []},
            {"task_id": "T2", "files_changed": [], "commands_run": []},
        ],
    }
    deviations: list[str] = []

    result = _auto_attribute_unclaimed_paths(
        project_dir=tmp_path,
        finalize_data=finalize_data,
        payload=payload,
        batch_task_ids=["T1", "T2"],
        issues=deviations,
        capture_recursive_snapshot_fn=lambda _p: (
            {"a.py": "<hash-a>", "b.py": "<hash-b>"},
            None,
        ),
    )

    assert finalize_data["tasks"][0]["files_changed"] == ["a.py"]
    assert finalize_data["tasks"][1]["files_changed"] == ["b.py"]
    assert payload["task_updates"][1]["files_changed"] == ["b.py"]
    assert payload["files_changed"] == ["existing.py", "b.py"]
    assert result.records == [
        {"task_id": "T2", "files": ["b.py"], "ambiguous": False}
    ]


def test_snapshot_recursive_expands_untracked_directory(tmp_path: Path) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=tmp_path,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=tmp_path,
        check=True,
    )
    (tmp_path / "tracked.py").write_text("print('tracked')\n", encoding="utf-8")
    subprocess.run(["git", "add", "tracked.py"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    (tmp_path / "newpkg").mkdir()
    (tmp_path / "newpkg" / "file.py").write_text("print('new')\n", encoding="utf-8")

    snapshot, error = _capture_git_status_snapshot_recursive(tmp_path)

    assert error is None
    assert "newpkg/file.py" in snapshot
    assert "newpkg/" not in snapshot


def test_snapshot_recursive_default_does_not_recurse_into_untracked_directory(tmp_path: Path) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=tmp_path,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=tmp_path,
        check=True,
    )
    (tmp_path / "tracked.py").write_text("print('tracked')\n", encoding="utf-8")
    subprocess.run(["git", "add", "tracked.py"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    (tmp_path / "newpkg").mkdir()
    (tmp_path / "newpkg" / "file.py").write_text("print('new')\n", encoding="utf-8")

    snapshot, error = _capture_git_status_snapshot(tmp_path)

    assert error is None
    assert "newpkg/file.py" not in snapshot
    assert "newpkg/" in snapshot


def _setup_single_auto_attribute_plan(plan_fixture: PlanFixture) -> None:
    make_args = plan_fixture.make_args
    megaplan.handle_plan(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_override(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, override_action="force-proceed", reason="test"),
    )
    megaplan.handle_finalize(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    finalize_data = read_json(plan_fixture.plan_dir / "finalize.json")
    finalize_data["tasks"] = [
        {
            "id": "T1",
            "description": "Implement the new package file.",
            "depends_on": [],
            "status": "pending",
            "executor_notes": "",
            "files_changed": [],
            "commands_run": [],
            "evidence_files": [],
            "reviewer_verdict": "",
        }
    ]
    finalize_data["sense_checks"] = [
        {
            "id": "SC1",
            "task_id": "T1",
            "question": "Was the new package file implemented?",
            "executor_note": "",
            "verdict": "",
        }
    ]
    (plan_fixture.plan_dir / "finalize.json").write_text(
        json.dumps(finalize_data, indent=2) + "\n", encoding="utf-8"
    )


def _stub_auto_attribute_git_snapshots(
    monkeypatch: pytest.MonkeyPatch,
    *,
    scope_snapshot: dict[str, str] | None = None,
) -> None:
    snapshots = iter(
        [
            ({}, None),
            ({"newpkg/": "<dir-marker>"}, None),
            (scope_snapshot or {"newpkg/": "<dir-marker>"}, None),
        ]
    )
    monkeypatch.setattr(
        megaplan.execute.core,
        "_capture_git_status_snapshot",
        lambda *_: next(snapshots),
    )
    monkeypatch.setattr(
        megaplan.execute.core,
        "_capture_git_status_snapshot_recursive",
        lambda *_: ({"newpkg/file.py": "<hash>"}, None),
    )


def _hermes_style_worker(project_dir: Path):
    def worker(step, state, plan_dir, args, *, root=None, resolved=None, prompt_override=None):
        del step, state, plan_dir, args, root, resolved, prompt_override
        new_file = project_dir / "newpkg" / "file.py"
        new_file.parent.mkdir(exist_ok=True)
        _write_lines(new_file, 25, prefix="generated")
        payload = {
            "output": "Hermes-style execution completed.",
            "files_changed": [],
            "commands_run": [],
            "deviations": [],
            "task_updates": [
                {
                    "task_id": "T1",
                    "status": "done",
                    "executor_notes": "Implemented the new package file on disk while leaving structured file evidence empty for attribution recovery.",
                    "files_changed": [],
                    "commands_run": [],
                }
            ],
            "sense_check_acknowledgments": [
                {
                    "sense_check_id": "SC1",
                    "executor_note": "Confirmed the new package file was created during execution.",
                }
            ],
        }
        return (
            WorkerResult(
                payload=payload,
                raw_output="hermes-style",
                duration_ms=1,
                cost_usd=0.0,
                session_id="hermes-style",
            ),
            "codex",
            "persistent",
            False,
        )

    return worker


def _execute_auto_loop_direct(plan_fixture: PlanFixture) -> dict:
    state = load_state(plan_fixture.plan_dir)
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


def test_auto_attribute_auto_loop_hermes_style_reaches_executed(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _setup_single_auto_attribute_plan(plan_fixture)
    _stub_auto_attribute_git_snapshots(monkeypatch)
    monkeypatch.setattr(
        megaplan.workers,
        "run_step_with_worker",
        _hermes_style_worker(plan_fixture.project_dir),
    )

    response = _execute_auto_loop_direct(plan_fixture)
    finalize_data = read_json(plan_fixture.plan_dir / "finalize.json")
    batch = read_json(plan_fixture.plan_dir / "execution_batch_1.json")
    execution = read_json(plan_fixture.plan_dir / "execution.json")
    audit = read_json(plan_fixture.plan_dir / "execution_audit.json")
    deviations = execution["deviations"]

    assert response["success"] is True
    assert response["state"] == megaplan.STATE_EXECUTED
    task = finalize_data["tasks"][0]
    assert task["auto_attributed_files"] is True
    assert task["files_changed"] == ["newpkg/file.py"]
    update = batch["task_updates"][0]
    assert update["auto_attributed_files"] is True
    assert update["files_changed"] == ["newpkg/file.py"]
    assert "newpkg/file.py" in execution["files_changed"]
    assert audit["auto_attribution"] == [
        {"task_id": "T1", "files": ["newpkg/file.py"], "ambiguous": False}
    ]
    assert any(
        "Auto-attributed 1 unclaimed file(s) to task T1" in deviation
        for deviation in deviations
    )
    assert not any(
        "Advisory observation mismatch:" in deviation and "newpkg/" in deviation
        for deviation in deviations
    )
    assert not any(
        "executor claimed files not observed in git status" in deviation
        and "newpkg/file.py" in deviation
        for deviation in deviations
    )


def test_auto_attribute_robust_auto_loop_avoids_scope_drift_blocker(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan_fixture = _make_plan_fixture_with_robustness(
        tmp_path, monkeypatch, robustness="robust"
    )
    _setup_single_auto_attribute_plan(plan_fixture)
    _stub_auto_attribute_git_snapshots(
        monkeypatch,
        scope_snapshot={"newpkg/file.py": "<hash>"},
    )
    monkeypatch.setattr(
        megaplan.workers,
        "run_step_with_worker",
        _hermes_style_worker(plan_fixture.project_dir),
    )

    response = _execute_auto_loop_direct(plan_fixture)
    execution = read_json(plan_fixture.plan_dir / "execution.json")

    assert response["success"] is True
    assert response["state"] == megaplan.STATE_EXECUTED
    assert "newpkg/file.py" in execution["files_changed"]
    assert not any("scope_drift_severity=high" in warning for warning in response["warnings"])
    assert not any("scope_drift_severity=high" in deviation for deviation in response["deviations"])


def test_auto_attribute_one_batch_handler_persists_per_batch_audit(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _setup_single_auto_attribute_plan(plan_fixture)
    _stub_auto_attribute_git_snapshots(monkeypatch)
    monkeypatch.setattr(
        megaplan.workers,
        "run_step_with_worker",
        _hermes_style_worker(plan_fixture.project_dir),
    )
    state = load_state(plan_fixture.plan_dir)

    response = megaplan.execute.core.handle_execute_one_batch(
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
    audit = read_json(plan_fixture.plan_dir / "execution_audit.json")

    assert response["success"] is True
    assert response["state"] == megaplan.STATE_EXECUTED
    assert audit["auto_attribution"] == [
        {"task_id": "T1", "files": ["newpkg/file.py"], "ambiguous": False}
    ]


def test_capture_test_baseline_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv(megaplan.handlers.MOCK_ENV_VAR, raising=False)
    monkeypatch.setattr(megaplan.handlers.shutil, "which", lambda name: "/usr/bin/pytest")
    monkeypatch.setattr(
        megaplan.handlers.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=args[0],
            returncode=1,
            stdout=(
                "tests/test_a.py::test_one FAILED\n"
                "tests/test_b.py::test_two FAILED\n"
                "2 failed, 5 passed\n"
            ),
            stderr="",
        ),
    )

    result = megaplan.handlers._capture_test_baseline(tmp_path, {})

    assert result["baseline_test_failures"] == [
        "tests/test_a.py::test_one",
        "tests/test_b.py::test_two",
    ]
    assert result["baseline_test_command"] == "pytest --tb=no -q --no-header"
    assert "baseline_test_note" not in result


def test_capture_test_baseline_no_runner(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv(megaplan.handlers.MOCK_ENV_VAR, raising=False)
    monkeypatch.setattr(megaplan.handlers.shutil, "which", lambda name: None)

    result = megaplan.handlers._capture_test_baseline(tmp_path, {})

    assert result["baseline_test_failures"] is None
    assert result["baseline_test_command"] is None
    assert "No supported test runner" in result["baseline_test_note"]


def test_capture_test_baseline_timeout(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv(megaplan.handlers.MOCK_ENV_VAR, raising=False)
    monkeypatch.setattr(megaplan.handlers.shutil, "which", lambda name: "/usr/bin/pytest")

    def _raise_timeout(*args: object, **kwargs: object) -> object:
        raise subprocess.TimeoutExpired(cmd="pytest --tb=no -q --no-header", timeout=120)

    monkeypatch.setattr(megaplan.handlers.subprocess, "run", _raise_timeout)

    result = megaplan.handlers._capture_test_baseline(tmp_path, {})

    assert result["baseline_test_failures"] is None
    assert "timed out" in result["baseline_test_note"].lower()


def test_execute_requires_confirm_destructive(plan_fixture: PlanFixture) -> None:
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    megaplan.handle_override(
        plan_fixture.root,
        plan_fixture.make_args(plan=plan_fixture.plan_name, override_action="force-proceed", reason="test"),
    )
    megaplan.handle_finalize(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    with pytest.raises(megaplan.CliError, match="confirm-destructive"):
        megaplan.handle_execute(
            plan_fixture.root,
            plan_fixture.make_args(plan=plan_fixture.plan_name, confirm_destructive=False),
        )


def test_execute_requires_user_approval_in_review_mode(plan_fixture: PlanFixture) -> None:
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    megaplan.handle_override(
        plan_fixture.root,
        plan_fixture.make_args(plan=plan_fixture.plan_name, override_action="force-proceed", reason="test"),
    )
    megaplan.handle_finalize(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    with pytest.raises(megaplan.CliError, match="user approval"):
        megaplan.handle_execute(
            plan_fixture.root,
            plan_fixture.make_args(plan=plan_fixture.plan_name, confirm_destructive=True, user_approved=False),
        )


def test_execute_succeeds_with_user_approval(plan_fixture: PlanFixture) -> None:
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    megaplan.handle_override(
        plan_fixture.root,
        plan_fixture.make_args(plan=plan_fixture.plan_name, override_action="force-proceed", reason="test"),
    )
    megaplan.handle_finalize(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    response = megaplan.handle_execute(
        plan_fixture.root,
        plan_fixture.make_args(plan=plan_fixture.plan_name, confirm_destructive=True, user_approved=True),
    )
    assert response["success"] is True
    assert response["state"] == megaplan.STATE_EXECUTED
    assert "finalize.json" in response["artifacts"]
    assert "final.md" in response["artifacts"]
    assert (plan_fixture.plan_dir / "execution_batch_1.json").exists()


def test_execute_succeeds_in_auto_approve_mode(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "root"
    project_dir = tmp_path / "project"
    root.mkdir()
    project_dir.mkdir()
    (project_dir / ".git").mkdir()
    monkeypatch.setenv(megaplan.MOCK_ENV_VAR, "1")
    monkeypatch.setattr(
        megaplan._core.shutil,
        "which",
        lambda name: "/usr/bin/mock" if name in {"claude", "codex"} else None,
    )
    make_args = make_args_factory(project_dir)
    megaplan.handle_init(root, make_args(auto_approve=True))
    megaplan.handle_plan(root, make_args(plan="test-plan"))
    megaplan.handle_critique(root, make_args(plan="test-plan"))
    megaplan.handle_override(root, make_args(plan="test-plan", override_action="force-proceed", reason="test"))
    megaplan.handle_finalize(root, make_args(plan="test-plan"))
    response = megaplan.handle_execute(
        root,
        make_args(plan="test-plan", confirm_destructive=True, user_approved=False),
    )
    assert response["success"] is True
    assert response["auto_approve"] is True
    assert "finalize.json" in response["artifacts"]


def test_step_failure_records_error_in_history(plan_fixture: PlanFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))

    def failing_worker(*a, **kw):
        raise megaplan.CliError("test_error", "Worker blew up", extra={"raw_output": "boom"})

    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", failing_worker)
    with pytest.raises(megaplan.CliError, match="Worker blew up"):
        megaplan.handle_critique(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    state = load_state(plan_fixture.plan_dir)
    error_entries = [h for h in state["history"] if h.get("result") == "error"]
    assert len(error_entries) >= 1
    assert "Worker blew up" in error_entries[-1].get("message", "")


def test_step_failure_stores_raw_output_file(plan_fixture: PlanFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))

    def failing_worker(*a, **kw):
        raise megaplan.CliError("test_error", "fail", extra={"raw_output": "raw content here"})

    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", failing_worker)
    with pytest.raises(megaplan.CliError):
        megaplan.handle_critique(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    state = load_state(plan_fixture.plan_dir)
    error_entry = next(h for h in state["history"] if h.get("result") == "error")
    raw_file = error_entry.get("raw_output_file")
    assert raw_file is not None
    assert (plan_fixture.plan_dir / raw_file).exists()


def test_step_failure_uses_message_when_no_raw_output(plan_fixture: PlanFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))

    def failing_worker(*a, **kw):
        raise megaplan.CliError("test_error", "the error message")

    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", failing_worker)
    with pytest.raises(megaplan.CliError):
        megaplan.handle_critique(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    state = load_state(plan_fixture.plan_dir)
    error_entry = next(h for h in state["history"] if h.get("result") == "error")
    raw_file = error_entry.get("raw_output_file")
    content = (plan_fixture.plan_dir / raw_file).read_text(encoding="utf-8")
    assert "the error message" in content


def test_run_command_raises_on_timeout() -> None:
    from megaplan.workers import run_command

    with pytest.raises(megaplan.CliError, match="timed out"):
        run_command(["sleep", "60"], cwd=Path.cwd(), timeout=1)


def test_run_command_raises_on_file_not_found() -> None:
    from megaplan.workers import run_command

    with pytest.raises(megaplan.CliError, match="not found"):
        run_command(["nonexistent_command_xyz"], cwd=Path.cwd())


def test_execute_prompt_includes_approval_note(plan_fixture: PlanFixture) -> None:
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    megaplan.handle_override(
        plan_fixture.root,
        plan_fixture.make_args(plan=plan_fixture.plan_name, override_action="force-proceed", reason="test"),
    )
    megaplan.handle_finalize(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    _, state = load_plan(plan_fixture.root, plan_fixture.plan_name)
    from megaplan.prompts import create_claude_prompt

    prompt = create_claude_prompt("execute", state, plan_fixture.plan_dir)
    assert "Review mode" in prompt or "auto-approve" in prompt or "approved" in prompt


def test_execute_happy_path_tracks_all_tasks(plan_fixture: PlanFixture) -> None:
    """The default mock execute output still covers every finalized task."""
    make_args = plan_fixture.make_args
    megaplan.handle_plan(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_override(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, override_action="force-proceed", reason="test"),
    )
    megaplan.handle_finalize(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    response = megaplan.handle_execute(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, confirm_destructive=True, user_approved=True),
    )
    assert response["success"] is True
    assert response["warnings"] == []
    assert "2/2 tasks tracked" in response["summary"]
    assert "2/2 sense checks acknowledged" in response["summary"]


def test_execute_timeout_recovers_partial_progress_from_finalize_json(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    make_args = plan_fixture.make_args
    megaplan.handle_plan(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_override(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, override_action="force-proceed", reason="test"),
    )
    megaplan.handle_finalize(plan_fixture.root, make_args(plan=plan_fixture.plan_name))

    finalize_data = read_json(plan_fixture.plan_dir / "finalize.json")
    finalize_data["tasks"][0]["status"] = "done"
    finalize_data["tasks"][0]["executor_notes"] = "Verified the implementation artifact before timeout recovery."
    finalize_data["tasks"][0]["files_changed"] = ["IMPLEMENTED_BY_MEGAPLAN.txt"]
    finalize_data["tasks"][0]["commands_run"] = ["mock-write IMPLEMENTED_BY_MEGAPLAN.txt"]
    finalize_data["sense_checks"][0]["executor_note"] = "Confirmed the implementation artifact exists."
    (plan_fixture.plan_dir / "finalize.json").write_text(json.dumps(finalize_data, indent=2) + "\n", encoding="utf-8")

    def timing_out_worker(*args, **kwargs):
        raise megaplan.CliError("worker_timeout", "execute timed out", extra={"session_id": "test-session", "raw_output": ""})

    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", timing_out_worker)

    response = megaplan.handle_execute(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, confirm_destructive=True, user_approved=True),
    )
    state = load_state(plan_fixture.plan_dir)
    recovered = read_json(plan_fixture.plan_dir / "finalize.json")

    assert response["success"] is False
    assert response["next_step"] == "execute"
    assert response["state"] == megaplan.STATE_FINALIZED
    assert recovered["tasks"][0]["status"] == "done"
    assert state["history"][-1]["result"] == "timeout"
    assert state["sessions"][megaplan.workers.session_key_for("execute", "codex")]["id"] == "test-session"


def test_execute_timeout_reads_execution_checkpoint_json(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    make_args = plan_fixture.make_args
    megaplan.handle_plan(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_override(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, override_action="force-proceed", reason="test"),
    )
    megaplan.handle_finalize(plan_fixture.root, make_args(plan=plan_fixture.plan_name))

    checkpoint_payload = {
        "task_updates": [
            {
                "task_id": "T1",
                "status": "done",
                "executor_notes": "Recovered from execution checkpoint.",
                "files_changed": ["IMPLEMENTED_BY_MEGAPLAN.txt"],
                "commands_run": ["mock-write IMPLEMENTED_BY_MEGAPLAN.txt"],
            }
        ],
        "sense_check_acknowledgments": [
            {"sense_check_id": "SC1", "executor_note": "Recovered checkpoint sense check."}
        ],
    }
    (plan_fixture.plan_dir / "execution_checkpoint.json").write_text(
        json.dumps(checkpoint_payload, indent=2) + "\n",
        encoding="utf-8",
    )

    def timing_out_worker(*args, **kwargs):
        raise megaplan.CliError("worker_timeout", "execute timed out", extra={"session_id": "checkpoint-session", "raw_output": ""})

    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", timing_out_worker)

    response = megaplan.handle_execute(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, confirm_destructive=True, user_approved=True),
    )
    recovered = read_json(plan_fixture.plan_dir / "finalize.json")

    assert response["success"] is False
    assert response["state"] == megaplan.STATE_FINALIZED
    assert recovered["tasks"][0]["status"] == "done"
    assert recovered["tasks"][0]["files_changed"] == ["IMPLEMENTED_BY_MEGAPLAN.txt"]
    assert recovered["sense_checks"][0]["executor_note"] == "Recovered checkpoint sense check."
    assert any(
        "Recovered timeout checkpoint from execution_checkpoint.json" in deviation
        for deviation in response["deviations"]
    )


def test_execute_timeout_resets_done_tasks_without_any_evidence(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    make_args = plan_fixture.make_args
    megaplan.handle_plan(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_override(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, override_action="force-proceed", reason="test"),
    )
    megaplan.handle_finalize(plan_fixture.root, make_args(plan=plan_fixture.plan_name))

    finalize_data = read_json(plan_fixture.plan_dir / "finalize.json")
    finalize_data["tasks"][0]["status"] = "done"
    finalize_data["tasks"][0]["executor_notes"] = "Claimed completion without evidence."
    (plan_fixture.plan_dir / "finalize.json").write_text(json.dumps(finalize_data, indent=2) + "\n", encoding="utf-8")

    def timing_out_worker(*args, **kwargs):
        raise megaplan.CliError("worker_timeout", "execute timed out", extra={"session_id": "test-session", "raw_output": ""})

    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", timing_out_worker)

    response = megaplan.handle_execute(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, confirm_destructive=True, user_approved=True),
    )
    recovered = read_json(plan_fixture.plan_dir / "finalize.json")

    assert response["success"] is False
    assert recovered["tasks"][0]["status"] == "pending"
    assert "Timeout recovery reset this task to pending" in recovered["tasks"][0]["executor_notes"]
    assert any("Reset timed-out done tasks to pending" in deviation for deviation in response["deviations"])


def test_execute_reports_advisory_when_structured_output_disagrees_with_disk_checkpoint(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    make_args = plan_fixture.make_args
    megaplan.handle_plan(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_override(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, override_action="force-proceed", reason="test"),
    )
    megaplan.handle_finalize(plan_fixture.root, make_args(plan=plan_fixture.plan_name))

    finalize_data = read_json(plan_fixture.plan_dir / "finalize.json")
    finalize_data["tasks"][0]["status"] = "done"
    finalize_data["tasks"][0]["executor_notes"] = "Checkpointed as done on disk before final structured output."
    finalize_data["tasks"][0]["files_changed"] = ["IMPLEMENTED_BY_MEGAPLAN.txt"]
    finalize_data["tasks"][0]["commands_run"] = ["mock-write IMPLEMENTED_BY_MEGAPLAN.txt"]
    (plan_fixture.plan_dir / "finalize.json").write_text(json.dumps(finalize_data, indent=2) + "\n", encoding="utf-8")

    worker = WorkerResult(
        payload={
            "output": "Execution completed with structured output.",
            "files_changed": ["IMPLEMENTED_BY_MEGAPLAN.txt"],
            "commands_run": ["mock-write IMPLEMENTED_BY_MEGAPLAN.txt"],
            "deviations": [],
            "task_updates": [
                {
                    "task_id": "T1",
                    "status": "skipped",
                    "executor_notes": "Verified the disk checkpoint should be downgraded because no additional work was required.",
                    "files_changed": [],
                    "commands_run": [],
                },
                {
                    "task_id": "T2",
                    "status": "done",
                    "executor_notes": "Verified the remaining task completed successfully.",
                    "files_changed": ["IMPLEMENTED_BY_MEGAPLAN.txt"],
                    "commands_run": ["mock-write IMPLEMENTED_BY_MEGAPLAN.txt"],
                },
            ],
            "sense_check_acknowledgments": [
                {"sense_check_id": "SC1", "executor_note": "Confirmed the checkpoint mismatch was intentional."},
                {"sense_check_id": "SC2", "executor_note": "Confirmed the remaining task completed successfully."},
            ],
        },
        raw_output="execute with mismatch",
        duration_ms=1,
        cost_usd=0.0,
        session_id="execute-mismatch",
    )
    monkeypatch.setattr(
        megaplan.workers,
        "run_step_with_worker",
        lambda *args, **kwargs: (worker, "codex", "persistent", False),
    )

    response = megaplan.handle_execute(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, confirm_destructive=True, user_approved=True),
    )
    merged_finalize = read_json(plan_fixture.plan_dir / "finalize.json")

    assert response["success"] is True
    assert merged_finalize["tasks"][0]["status"] == "skipped"
    assert any(
        "task T1 was 'done' on disk before merge but structured output set it to 'skipped'" in deviation
        for deviation in response["deviations"]
    )


def test_execute_deduplicates_task_updates_and_blocks_incomplete_coverage(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    make_args = plan_fixture.make_args
    megaplan.handle_plan(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_override(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, override_action="force-proceed", reason="test"),
    )
    megaplan.handle_finalize(plan_fixture.root, make_args(plan=plan_fixture.plan_name))

    worker = WorkerResult(
        payload={
            "output": "Partial execution completed.",
            "files_changed": ["src/example.py"],
            "commands_run": ["pytest -k partial"],
            "deviations": [],
            "task_updates": [
                {
                    "task_id": "T1",
                    "status": "done",
                    "executor_notes": "Initial pass.",
                    "files_changed": ["src/example.py"],
                    "commands_run": ["pytest -k partial"],
                },
                {
                    "task_id": "T1",
                    "status": "done",
                    "executor_notes": "Final pass.",
                    "files_changed": ["src/example.py"],
                    "commands_run": ["pytest -k partial"],
                },
            ],
            "sense_check_acknowledgments": [
                {"sense_check_id": "SC1", "executor_note": "Confirmed."},
            ],
        },
        raw_output="partial execute",
        duration_ms=1,
        cost_usd=0.0,
        session_id="execute-duplicate",
    )
    monkeypatch.setattr(
        megaplan.workers,
        "run_step_with_worker",
        lambda *args, **kwargs: (worker, "codex", "persistent", False),
    )

    response = megaplan.handle_execute(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, confirm_destructive=True, user_approved=True),
    )
    state = load_state(plan_fixture.plan_dir)
    finalize_data = read_json(plan_fixture.plan_dir / "finalize.json")
    execute_entry = next(entry for entry in state["history"] if entry["step"] == "execute")
    final_md = (plan_fixture.plan_dir / "final.md").read_text(encoding="utf-8")

    assert response["success"] is False
    assert response["state"] == megaplan.STATE_FINALIZED
    assert response["next_step"] == "execute"
    assert response["summary"] == (
        "Blocked: 1/2 tasks have no executor update; 1/2 sense checks have no executor acknowledgment. "
        "Re-run execute to complete tracking."
    )
    assert "Duplicate task_update for 'T1' — last entry wins." in response["deviations"]
    assert finalize_data["tasks"][0]["executor_notes"] == "Final pass."
    assert finalize_data["tasks"][1]["status"] == "pending"
    assert execute_entry["result"] == "blocked"
    assert (plan_fixture.plan_dir / "execution.json").exists()
    assert (plan_fixture.plan_dir / "execution_audit.json").exists()
    assert "## Coverage Gaps" in final_md
    assert "Tasks without executor updates: 1" in final_md


def test_execute_blocks_done_task_without_any_per_task_evidence(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    make_args = plan_fixture.make_args
    megaplan.handle_plan(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_override(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, override_action="force-proceed", reason="test"),
    )
    megaplan.handle_finalize(plan_fixture.root, make_args(plan=plan_fixture.plan_name))

    worker = WorkerResult(
        payload={
            "output": "Executed with incomplete evidence.",
            "files_changed": ["IMPLEMENTED_BY_MEGAPLAN.txt"],
            "commands_run": ["mock-run"],
            "deviations": [],
            "task_updates": [
                {
                    "task_id": "T1",
                    "status": "done",
                    "executor_notes": "Implemented the main artifact.",
                    "files_changed": ["IMPLEMENTED_BY_MEGAPLAN.txt"],
                    "commands_run": ["mock-run"],
                },
                {
                    "task_id": "T2",
                    "status": "done",
                    "executor_notes": "Verified the work but forgot to capture evidence.",
                    "files_changed": [],
                    "commands_run": [],
                },
            ],
            "sense_check_acknowledgments": [
                {"sense_check_id": "SC1", "executor_note": "Confirmed the implementation artifact exists."},
                {"sense_check_id": "SC2", "executor_note": "Confirmed the verification task was reviewed."},
            ],
        },
        raw_output="execute missing evidence",
        duration_ms=1,
        cost_usd=0.0,
        session_id="execute-missing-evidence",
    )
    monkeypatch.setattr(
        megaplan.workers,
        "run_step_with_worker",
        lambda *args, **kwargs: (worker, "codex", "persistent", False),
    )

    response = megaplan.handle_execute(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, confirm_destructive=True, user_approved=True),
    )

    assert response["success"] is False
    assert response["state"] == megaplan.STATE_FINALIZED
    assert response["next_step"] == "execute"
    assert "missing both files_changed and commands_run" in response["summary"]


def test_execute_softens_done_task_with_commands_only(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    make_args = plan_fixture.make_args
    megaplan.handle_plan(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_override(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, override_action="force-proceed", reason="test"),
    )
    megaplan.handle_finalize(plan_fixture.root, make_args(plan=plan_fixture.plan_name))

    worker = WorkerResult(
        payload={
            "output": "Executed with command-only verification evidence.",
            "files_changed": ["IMPLEMENTED_BY_MEGAPLAN.txt"],
            "commands_run": ["mock-run", "mock-verify"],
            "deviations": [],
            "task_updates": [
                {
                    "task_id": "T1",
                    "status": "done",
                    "executor_notes": "Implemented the main artifact.",
                    "files_changed": ["IMPLEMENTED_BY_MEGAPLAN.txt"],
                    "commands_run": ["mock-run"],
                },
                {
                    "task_id": "T2",
                    "status": "done",
                    "executor_notes": "Verified the work using command output only.",
                    "files_changed": [],
                    "commands_run": ["mock-verify"],
                },
            ],
            "sense_check_acknowledgments": [
                {"sense_check_id": "SC1", "executor_note": "Confirmed the implementation artifact exists."},
                {"sense_check_id": "SC2", "executor_note": "Confirmed the verification task is backed by command output."},
            ],
        },
        raw_output="execute softened evidence",
        duration_ms=1,
        cost_usd=0.0,
        session_id="execute-softened-evidence",
    )
    monkeypatch.setattr(
        megaplan.workers,
        "run_step_with_worker",
        lambda *args, **kwargs: (worker, "codex", "persistent", False),
    )

    response = megaplan.handle_execute(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, confirm_destructive=True, user_approved=True),
    )
    finalize_data = read_json(plan_fixture.plan_dir / "finalize.json")

    assert response["success"] is True
    assert response["state"] == megaplan.STATE_EXECUTED
    assert any("FLAG-006 softening" in deviation for deviation in response["deviations"])
    assert finalize_data["tasks"][1]["files_changed"] == []
    assert finalize_data["tasks"][1]["commands_run"] == ["mock-verify"]


def test_execute_multi_batch_happy_path_aggregates_results(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    make_args = plan_fixture.make_args
    megaplan.handle_plan(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_override(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, override_action="force-proceed", reason="test"),
    )
    megaplan.handle_finalize(plan_fixture.root, make_args(plan=plan_fixture.plan_name))

    finalize_data = read_json(plan_fixture.plan_dir / "finalize.json")
    finalize_data["tasks"] = [
        {
            "id": "T1",
            "description": "First batch",
            "depends_on": [],
            "status": "pending",
            "executor_notes": "",
            "files_changed": [],
            "commands_run": [],
            "evidence_files": [],
            "reviewer_verdict": "",
        },
        {
            "id": "T2",
            "description": "Second batch",
            "depends_on": ["T1"],
            "status": "pending",
            "executor_notes": "",
            "files_changed": [],
            "commands_run": [],
            "evidence_files": [],
            "reviewer_verdict": "",
        },
    ]
    finalize_data["sense_checks"] = [
        {"id": "SC1", "task_id": "T1", "question": "Batch one?", "executor_note": "", "verdict": ""},
        {"id": "SC2", "task_id": "T2", "question": "Batch two?", "executor_note": "", "verdict": ""},
    ]
    (plan_fixture.plan_dir / "finalize.json").write_text(json.dumps(finalize_data, indent=2) + "\n", encoding="utf-8")

    snapshots = iter([
        ({}, None),
        ({"batch1.py": "hash-1"}, None),
        ({"batch1.py": "hash-1"}, None),
        ({"batch1.py": "hash-1"}, None),
        ({"batch1.py": "hash-1", "batch2.py": "hash-2"}, None),
        ({"batch1.py": "hash-1", "batch2.py": "hash-2"}, None),
    ])
    monkeypatch.setattr(megaplan.execute.core, "_capture_git_status_snapshot", lambda *_: next(snapshots))

    def batched_worker(step: str, state: dict, plan_dir: Path, args: Namespace, *, root: Path, resolved=None, prompt_override: str | None = None):
        assert prompt_override is not None
        if "[T1]" in prompt_override:
            payload = {
                "output": "Batch one complete.",
                "files_changed": ["batch1.py"],
                "commands_run": ["pytest -k batch1"],
                "deviations": [],
                "task_updates": [
                    {
                        "task_id": "T1",
                        "status": "done",
                        "executor_notes": "Completed the first batch and verified its focused check.",
                        "files_changed": ["batch1.py"],
                        "commands_run": ["pytest -k batch1"],
                    }
                ],
                "sense_check_acknowledgments": [
                    {"sense_check_id": "SC1", "executor_note": "Confirmed batch one output."}
                ],
            }
            return WorkerResult(payload=payload, raw_output="batch1", duration_ms=2, cost_usd=0.1, session_id="batch-1", trace_output='{"batch":1}\n'), "codex", "persistent", False
        if "[T2]" in prompt_override:
            payload = {
                "output": "Batch two complete.",
                "files_changed": ["batch2.py"],
                "commands_run": ["pytest -k batch2"],
                "deviations": [],
                "task_updates": [
                    {
                        "task_id": "T2",
                        "status": "done",
                        "executor_notes": "Completed the dependent batch after T1 was persisted.",
                        "files_changed": ["batch2.py"],
                        "commands_run": ["pytest -k batch2"],
                    }
                ],
                "sense_check_acknowledgments": [
                    {"sense_check_id": "SC2", "executor_note": "Confirmed batch two output."}
                ],
            }
            return WorkerResult(payload=payload, raw_output="batch2", duration_ms=3, cost_usd=0.2, session_id="batch-2", trace_output='{"batch":2}\n'), "codex", "persistent", False
        raise AssertionError(f"Unexpected batch prompt: {prompt_override}")

    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", batched_worker)

    response = megaplan.handle_execute(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, confirm_destructive=True, user_approved=True),
    )
    final_data = read_json(plan_fixture.plan_dir / "finalize.json")
    execution = read_json(plan_fixture.plan_dir / "execution.json")

    assert response["success"] is True
    assert response["state"] == megaplan.STATE_EXECUTED
    assert [task["status"] for task in final_data["tasks"]] == ["done", "done"]
    assert [check["executor_note"] for check in final_data["sense_checks"]] == [
        "Confirmed batch one output.",
        "Confirmed batch two output.",
    ]
    assert execution["output"].startswith("Aggregated execute batches: completed 2/2.")
    assert [item["task_id"] for item in execution["task_updates"]] == ["T1", "T2"]
    assert [item["sense_check_id"] for item in execution["sense_check_acknowledgments"]] == ["SC1", "SC2"]
    assert execution["files_changed"] == ["batch1.py", "batch2.py"]
    assert execution["commands_run"] == ["pytest -k batch1", "pytest -k batch2"]
    assert (plan_fixture.plan_dir / "execution_trace.jsonl").read_text(encoding="utf-8") == '{"batch":1}\n{"batch":2}\n'
    batch_1 = read_json(plan_fixture.plan_dir / "execution_batch_1.json")
    batch_2 = read_json(plan_fixture.plan_dir / "execution_batch_2.json")
    assert [item["task_id"] for item in batch_1["task_updates"]] == ["T1"]
    assert [item["task_id"] for item in batch_2["task_updates"]] == ["T2"]


def test_execute_multi_batch_timeout_preserves_prior_batches(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    make_args = plan_fixture.make_args
    megaplan.handle_plan(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_override(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, override_action="force-proceed", reason="test"),
    )
    megaplan.handle_finalize(plan_fixture.root, make_args(plan=plan_fixture.plan_name))

    finalize_data = read_json(plan_fixture.plan_dir / "finalize.json")
    finalize_data["tasks"][1]["depends_on"] = ["T1"]
    (plan_fixture.plan_dir / "finalize.json").write_text(json.dumps(finalize_data, indent=2) + "\n", encoding="utf-8")

    snapshots = iter([
        ({}, None),
        ({"batch1.py": "hash-1"}, None),
        ({"batch1.py": "hash-1"}, None),
        ({"batch1.py": "hash-1"}, None),
    ])
    monkeypatch.setattr(megaplan.execute.core, "_capture_git_status_snapshot", lambda *_: next(snapshots))

    def timed_worker(step: str, state: dict, plan_dir: Path, args: Namespace, *, root: Path, resolved=None, prompt_override: str | None = None):
        assert prompt_override is not None
        if "[T1]" in prompt_override:
            payload = {
                "output": "Batch one complete.",
                "files_changed": ["batch1.py"],
                "commands_run": ["pytest -k batch1"],
                "deviations": [],
                "task_updates": [
                    {
                        "task_id": "T1",
                        "status": "done",
                        "executor_notes": "Completed the first batch and verified its focused check.",
                        "files_changed": ["batch1.py"],
                        "commands_run": ["pytest -k batch1"],
                    }
                ],
                "sense_check_acknowledgments": [
                    {"sense_check_id": "SC1", "executor_note": "Confirmed batch one output."}
                ],
            }
            return WorkerResult(payload=payload, raw_output="batch1", duration_ms=2, cost_usd=0.1, session_id="batch-1"), "codex", "persistent", False
        raise megaplan.CliError("worker_timeout", "execute timed out", extra={"session_id": "batch-2", "raw_output": "partial"})

    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", timed_worker)

    response = megaplan.handle_execute(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, confirm_destructive=True, user_approved=True),
    )
    final_data = read_json(plan_fixture.plan_dir / "finalize.json")
    execution = read_json(plan_fixture.plan_dir / "execution.json")
    state = load_state(plan_fixture.plan_dir)

    assert response["success"] is False
    assert response["state"] == megaplan.STATE_FINALIZED
    assert response["next_step"] == "execute"
    assert final_data["tasks"][0]["status"] == "done"
    assert final_data["tasks"][1]["status"] == "pending"
    assert final_data["sense_checks"][0]["executor_note"] == "Confirmed batch one output."
    assert final_data["sense_checks"][1]["executor_note"] == ""
    assert [item["task_id"] for item in execution["task_updates"]] == ["T1"]
    assert state["history"][-1]["result"] == "timeout"


def test_execute_rerun_with_completed_dependency_uses_single_batch_fast_path(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    make_args = plan_fixture.make_args
    megaplan.handle_plan(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_override(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, override_action="force-proceed", reason="test"),
    )
    megaplan.handle_finalize(plan_fixture.root, make_args(plan=plan_fixture.plan_name))

    finalize_data = read_json(plan_fixture.plan_dir / "finalize.json")
    finalize_data["tasks"][0]["status"] = "done"
    finalize_data["tasks"][0]["executor_notes"] = "Already completed."
    finalize_data["tasks"][0]["files_changed"] = ["batch1.py"]
    finalize_data["tasks"][0]["commands_run"] = ["pytest -k batch1"]
    finalize_data["tasks"][1]["depends_on"] = ["T1"]
    finalize_data["sense_checks"][0]["executor_note"] = "Already acknowledged."
    (plan_fixture.plan_dir / "finalize.json").write_text(json.dumps(finalize_data, indent=2) + "\n", encoding="utf-8")

    prompt_overrides: list[str | None] = []

    def rerun_worker(step: str, state: dict, plan_dir: Path, args: Namespace, *, root: Path, resolved=None, prompt_override: str | None = None):
        prompt_overrides.append(prompt_override)
        payload = {
            "output": "Rerun complete.",
            "files_changed": ["batch1.py", "batch2.py"],
            "commands_run": ["pytest -k rerun"],
            "deviations": [],
            "task_updates": [
                {
                    "task_id": "T1",
                    "status": "done",
                    "executor_notes": "Kept the already-completed task intact during rerun.",
                    "files_changed": ["batch1.py"],
                    "commands_run": ["pytest -k batch1"],
                },
                {
                    "task_id": "T2",
                    "status": "done",
                    "executor_notes": "Completed the remaining dependent task.",
                    "files_changed": ["batch2.py"],
                    "commands_run": ["pytest -k rerun"],
                },
            ],
            "sense_check_acknowledgments": [
                {"sense_check_id": "SC1", "executor_note": "Already acknowledged."},
                {"sense_check_id": "SC2", "executor_note": "Confirmed rerun output."},
            ],
        }
        return WorkerResult(payload=payload, raw_output="rerun", duration_ms=1, cost_usd=0.0, session_id="rerun"), "codex", "persistent", False

    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", rerun_worker)

    response = megaplan.handle_execute(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, confirm_destructive=True, user_approved=True),
    )

    assert response["success"] is True
    assert prompt_overrides == [None]


def test_execute_multi_batch_observation_allows_cross_batch_reedit_and_flags_phantoms(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    make_args = plan_fixture.make_args
    megaplan.handle_plan(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_override(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, override_action="force-proceed", reason="test"),
    )
    megaplan.handle_finalize(plan_fixture.root, make_args(plan=plan_fixture.plan_name))

    finalize_data = read_json(plan_fixture.plan_dir / "finalize.json")
    finalize_data["tasks"][1]["depends_on"] = ["T1"]
    (plan_fixture.plan_dir / "finalize.json").write_text(json.dumps(finalize_data, indent=2) + "\n", encoding="utf-8")

    snapshots = iter([
        ({}, None),
        ({"megaplan/handlers.py": "hash-1"}, None),
        ({"megaplan/handlers.py": "hash-1"}, None),
        ({"megaplan/handlers.py": "hash-1"}, None),
        ({"megaplan/handlers.py": "hash-2"}, None),
        ({"megaplan/handlers.py": "hash-2"}, None),
    ])
    monkeypatch.setattr(megaplan.execute.core, "_capture_git_status_snapshot", lambda *_: next(snapshots))

    def observation_worker(step: str, state: dict, plan_dir: Path, args: Namespace, *, root: Path, resolved=None, prompt_override: str | None = None):
        assert prompt_override is not None
        if "[T1]" in prompt_override:
            payload = {
                "output": "Batch one complete.",
                "files_changed": ["megaplan/handlers.py"],
                "commands_run": ["pytest -k batch1"],
                "deviations": [],
                "task_updates": [
                    {
                        "task_id": "T1",
                        "status": "done",
                        "executor_notes": "Edited handlers.py in batch one.",
                        "files_changed": ["megaplan/handlers.py"],
                        "commands_run": ["pytest -k batch1"],
                    }
                ],
                "sense_check_acknowledgments": [
                    {"sense_check_id": "SC1", "executor_note": "Confirmed batch one output."}
                ],
            }
            return WorkerResult(payload=payload, raw_output="batch1", duration_ms=1, cost_usd=0.0, session_id="batch-1"), "codex", "persistent", False
        payload = {
            "output": "Batch two complete.",
            "files_changed": ["megaplan/handlers.py", "ghost.py"],
            "commands_run": ["pytest -k batch2"],
            "deviations": [],
            "task_updates": [
                {
                    "task_id": "T2",
                    "status": "done",
                    "executor_notes": "Re-edited handlers.py in batch two.",
                    "files_changed": ["megaplan/handlers.py", "ghost.py"],
                    "commands_run": ["pytest -k batch2"],
                }
            ],
            "sense_check_acknowledgments": [
                {"sense_check_id": "SC2", "executor_note": "Confirmed batch two output."}
            ],
        }
        return WorkerResult(payload=payload, raw_output="batch2", duration_ms=1, cost_usd=0.0, session_id="batch-2"), "codex", "persistent", False

    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", observation_worker)

    response = megaplan.handle_execute(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, confirm_destructive=True, user_approved=True),
    )

    assert response["success"] is True
    assert any("ghost.py" in deviation for deviation in response["deviations"])
    assert not any(
        "executor claimed files not observed" in deviation and "megaplan/handlers.py" in deviation
        for deviation in response["deviations"]
    )

def _setup_two_batch_plan(plan_fixture: PlanFixture) -> None:
    """Drive plan to finalized and set up 2-batch task structure."""
    make_args = plan_fixture.make_args
    megaplan.handle_plan(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_override(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, override_action="force-proceed", reason="test"),
    )
    megaplan.handle_finalize(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    finalize_data = read_json(plan_fixture.plan_dir / "finalize.json")
    finalize_data["tasks"] = [
        {
            "id": "T1",
            "description": "First batch",
            "depends_on": [],
            "status": "pending",
            "executor_notes": "",
            "files_changed": [],
            "commands_run": [],
            "evidence_files": [],
            "reviewer_verdict": "",
        },
        {
            "id": "T2",
            "description": "Second batch",
            "depends_on": ["T1"],
            "status": "pending",
            "executor_notes": "",
            "files_changed": [],
            "commands_run": [],
            "evidence_files": [],
            "reviewer_verdict": "",
        },
    ]
    finalize_data["sense_checks"] = [
        {"id": "SC1", "task_id": "T1", "question": "Batch one?", "executor_note": "", "verdict": ""},
        {"id": "SC2", "task_id": "T2", "question": "Batch two?", "executor_note": "", "verdict": ""},
    ]
    (plan_fixture.plan_dir / "finalize.json").write_text(
        json.dumps(finalize_data, indent=2) + "\n", encoding="utf-8"
    )

def _batch_worker(step, state, plan_dir, args, *, root=None, resolved=None, prompt_override=None):
    """Mock worker that returns batch-specific results based on prompt content."""
    assert prompt_override is not None
    if "[T1]" in prompt_override:
        payload = {
            "output": "Batch one complete.",
            "files_changed": ["batch1.py"],
            "commands_run": ["pytest -k batch1"],
            "deviations": [],
            "task_updates": [
                {
                    "task_id": "T1",
                    "status": "done",
                    "executor_notes": "Completed the first batch.",
                    "files_changed": ["batch1.py"],
                    "commands_run": ["pytest -k batch1"],
                }
            ],
            "sense_check_acknowledgments": [
                {"sense_check_id": "SC1", "executor_note": "Confirmed batch one."}
            ],
        }
        return WorkerResult(payload=payload, raw_output="batch1", duration_ms=2, cost_usd=0.1, session_id="batch-1"), "codex", "persistent", False
    if "[T2]" in prompt_override:
        payload = {
            "output": "Batch two complete.",
            "files_changed": ["batch2.py"],
            "commands_run": ["pytest -k batch2"],
            "deviations": [],
            "task_updates": [
                {
                    "task_id": "T2",
                    "status": "done",
                    "executor_notes": "Completed the second batch.",
                    "files_changed": ["batch2.py"],
                    "commands_run": ["pytest -k batch2"],
                }
            ],
            "sense_check_acknowledgments": [
                {"sense_check_id": "SC2", "executor_note": "Confirmed batch two."}
            ],
        }
        return WorkerResult(payload=payload, raw_output="batch2", duration_ms=3, cost_usd=0.2, session_id="batch-2"), "codex", "persistent", False
    raise AssertionError(f"Unexpected batch prompt: {prompt_override}")

def test_batch_1_on_two_batch_plan_stays_finalized(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _setup_two_batch_plan(plan_fixture)
    monkeypatch.setattr(megaplan.execute.core, "_capture_git_status_snapshot", lambda *_: ({}, None))
    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", _batch_worker)

    make_args = plan_fixture.make_args
    response = megaplan.handle_execute(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, confirm_destructive=True, user_approved=True, batch=1),
    )
    state = read_json(plan_fixture.plan_dir / "state.json")
    finalize_data = read_json(plan_fixture.plan_dir / "finalize.json")

    assert response["state"] == megaplan.STATE_FINALIZED
    assert response["next_step"] == "execute"
    assert response["batch"] == 1
    assert response["batches_total"] == 2
    assert response["batches_remaining"] == 1
    assert (plan_fixture.plan_dir / "execution_batch_1.json").exists()
    assert not (plan_fixture.plan_dir / "execution.json").exists()
    assert finalize_data["tasks"][0]["status"] == "done"
    assert finalize_data["tasks"][1]["status"] == "pending"

def test_batch_timeout_reads_execution_batch_n_json(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _setup_two_batch_plan(plan_fixture)
    monkeypatch.setattr(megaplan.execute.core, "_capture_git_status_snapshot", lambda *_: ({}, None))

    checkpoint_payload = {
        "task_updates": [
            {
                "task_id": "T1",
                "status": "done",
                "executor_notes": "Recovered from batch checkpoint.",
                "files_changed": ["batch1.py"],
                "commands_run": ["pytest -k batch1"],
            }
        ],
        "sense_check_acknowledgments": [
            {"sense_check_id": "SC1", "executor_note": "Recovered batch checkpoint sense check."}
        ],
    }
    (plan_fixture.plan_dir / "execution_batch_1.json").write_text(
        json.dumps(checkpoint_payload, indent=2) + "\n",
        encoding="utf-8",
    )

    def timing_out_batch_worker(*args, **kwargs):
        raise megaplan.CliError("worker_timeout", "execute timed out", extra={"session_id": "batch-timeout", "raw_output": ""})

    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", timing_out_batch_worker)

    response = megaplan.handle_execute(
        plan_fixture.root,
        plan_fixture.make_args(plan=plan_fixture.plan_name, confirm_destructive=True, user_approved=True, batch=1),
    )
    recovered = read_json(plan_fixture.plan_dir / "finalize.json")

    assert response["success"] is False
    assert response["state"] == megaplan.STATE_FINALIZED
    assert response["next_step"] == "execute"
    assert recovered["tasks"][0]["status"] == "done"
    assert recovered["tasks"][0]["files_changed"] == ["batch1.py"]
    assert recovered["tasks"][1]["status"] == "pending"
    assert recovered["sense_checks"][0]["executor_note"] == "Recovered batch checkpoint sense check."
    assert any(
        "Recovered timeout checkpoint from execution_batch_1.json" in deviation
        for deviation in response["deviations"]
    )

def test_batch_2_after_batch_1_transitions_to_executed(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _setup_two_batch_plan(plan_fixture)
    monkeypatch.setattr(megaplan.execute.core, "_capture_git_status_snapshot", lambda *_: ({}, None))
    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", _batch_worker)

    make_args = plan_fixture.make_args
    megaplan.handle_execute(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, confirm_destructive=True, user_approved=True, batch=1),
    )
    response = megaplan.handle_execute(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, confirm_destructive=True, user_approved=True, batch=2),
    )
    state = read_json(plan_fixture.plan_dir / "state.json")
    finalize_data = read_json(plan_fixture.plan_dir / "finalize.json")

    assert response["state"] == megaplan.STATE_EXECUTED
    assert response["next_step"] == "review"
    assert response["batch"] == 2
    assert response["batches_remaining"] == 0
    assert (plan_fixture.plan_dir / "execution.json").exists()
    execution = read_json(plan_fixture.plan_dir / "execution.json")
    assert [item["task_id"] for item in execution["task_updates"]] == ["T1", "T2"]
    assert all(t["status"] == "done" for t in finalize_data["tasks"])

def test_execute_quality_advisories_flow_into_batch_artifacts_aggregate_and_next_prompt(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _setup_two_batch_plan(plan_fixture)
    batch1_path = plan_fixture.project_dir / "batch1.txt"
    batch2_path = plan_fixture.project_dir / "batch2.txt"
    _write_lines(batch1_path, 10, prefix="batch1_before")
    _write_lines(batch2_path, 10, prefix="batch2_before")

    snapshots = iter([
        ({"batch1.txt": "before-1"}, None),
        ({"batch1.txt": "after-1"}, None),
        ({"batch1.txt": "after-1"}, None),
        ({"batch1.txt": "after-1", "batch2.txt": "before-2"}, None),
        ({"batch1.txt": "after-1", "batch2.txt": "after-2"}, None),
        ({"batch1.txt": "after-1", "batch2.txt": "after-2"}, None),
    ])
    monkeypatch.setattr(megaplan.execute.core, "_capture_git_status_snapshot", lambda *_: next(snapshots))
    monkeypatch.setattr(megaplan.execute.core, "load_config", lambda *_: {})

    seen_prompts: list[str | None] = []

    def quality_batch_worker(step, state, plan_dir, args, *, root=None, resolved=None, prompt_override=None):
        seen_prompts.append(prompt_override)
        assert prompt_override is not None
        if "[T1]" in prompt_override:
            _write_lines(batch1_path, 310, prefix="batch1_after")
            payload = {
                "output": "Batch one complete.",
                "files_changed": ["batch1.txt"],
                "commands_run": ["pytest -k batch1"],
                "deviations": [],
                "task_updates": [
                    {
                        "task_id": "T1",
                        "status": "done",
                        "executor_notes": "Completed the first batch and verified the file growth trigger.",
                        "files_changed": ["batch1.txt"],
                        "commands_run": ["pytest -k batch1"],
                    }
                ],
                "sense_check_acknowledgments": [
                    {"sense_check_id": "SC1", "executor_note": "Confirmed batch one output."}
                ],
            }
            return WorkerResult(payload=payload, raw_output="batch1", duration_ms=2, cost_usd=0.1, session_id="batch-1"), "codex", "persistent", False
        if "[T2]" in prompt_override:
            assert "Prior batch deviations (address if applicable):" in prompt_override
            assert "Advisory quality: batch1.txt grew by 300 lines (threshold 200)." in prompt_override
            _write_lines(batch2_path, 20, prefix="batch2_after")
            payload = {
                "output": "Batch two complete.",
                "files_changed": ["batch2.txt"],
                "commands_run": ["pytest -k batch2"],
                "deviations": [],
                "task_updates": [
                    {
                        "task_id": "T2",
                        "status": "done",
                        "executor_notes": "Completed the second batch after reviewing prior advisories.",
                        "files_changed": ["batch2.txt"],
                        "commands_run": ["pytest -k batch2"],
                    }
                ],
                "sense_check_acknowledgments": [
                    {"sense_check_id": "SC2", "executor_note": "Confirmed batch two output."}
                ],
            }
            return WorkerResult(payload=payload, raw_output="batch2", duration_ms=3, cost_usd=0.2, session_id="batch-2"), "codex", "persistent", False
        raise AssertionError(f"Unexpected batch prompt: {prompt_override}")

    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", quality_batch_worker)

    response = megaplan.handle_execute(
        plan_fixture.root,
        plan_fixture.make_args(plan=plan_fixture.plan_name, confirm_destructive=True, user_approved=True),
    )
    batch_1 = read_json(plan_fixture.plan_dir / "execution_batch_1.json")
    execution = read_json(plan_fixture.plan_dir / "execution.json")

    assert response["success"] is True
    assert "Advisory quality: batch1.txt grew by 300 lines (threshold 200)." in batch_1["deviations"]
    assert any(deviation.startswith("Advisory quality:") for deviation in batch_1["deviations"])
    assert "Advisory quality: batch1.txt grew by 300 lines (threshold 200)." in execution["deviations"]
    assert any(
        prompt is not None and "Prior batch deviations (address if applicable):" in prompt and "[T2]" in prompt
        for prompt in seen_prompts
    )

def test_execute_quality_config_disable_suppresses_file_growth_deviation_end_to_end(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _setup_two_batch_plan(plan_fixture)
    finalize_data = read_json(plan_fixture.plan_dir / "finalize.json")
    finalize_data["tasks"] = [finalize_data["tasks"][0]]
    finalize_data["sense_checks"] = [finalize_data["sense_checks"][0]]
    (plan_fixture.plan_dir / "finalize.json").write_text(
        json.dumps(finalize_data, indent=2) + "\n", encoding="utf-8"
    )

    notes_path = plan_fixture.project_dir / "notes.txt"
    _write_lines(notes_path, 10, prefix="notes_before")

    snapshots = iter([
        ({"notes.txt": "before-1"}, None),
        ({"notes.txt": "after-1"}, None),
        ({"notes.txt": "after-1"}, None),
    ])
    monkeypatch.setattr(megaplan.execute.core, "_capture_git_status_snapshot", lambda *_: next(snapshots))
    monkeypatch.setattr(
        megaplan.execute.core,
        "load_config",
        lambda *_: {"quality_checks": {"file_growth": {"enabled": False}}},
    )

    def single_quality_worker(step, state, plan_dir, args, *, root=None, resolved=None, prompt_override=None):
        _write_lines(notes_path, 310, prefix="notes_after")
        payload = {
            "output": "Single batch complete.",
            "files_changed": ["notes.txt"],
            "commands_run": ["pytest -k quality-disable"],
            "deviations": [],
            "task_updates": [
                {
                    "task_id": "T1",
                    "status": "done",
                    "executor_notes": "Completed the batch with file growth disabled in config.",
                    "files_changed": ["notes.txt"],
                    "commands_run": ["pytest -k quality-disable"],
                }
            ],
            "sense_check_acknowledgments": [
                {"sense_check_id": "SC1", "executor_note": "Confirmed config-disabled batch output."}
            ],
        }
        return WorkerResult(payload=payload, raw_output="single", duration_ms=1, cost_usd=0.1, session_id="single"), "codex", "persistent", False

    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", single_quality_worker)

    response = megaplan.handle_execute(
        plan_fixture.root,
        plan_fixture.make_args(plan=plan_fixture.plan_name, confirm_destructive=True, user_approved=True),
    )
    batch_1 = read_json(plan_fixture.plan_dir / "execution_batch_1.json")
    execution = read_json(plan_fixture.plan_dir / "execution.json")

    assert response["success"] is True
    assert not any("notes.txt grew by" in deviation for deviation in batch_1["deviations"])
    assert not any("notes.txt grew by" in deviation for deviation in execution["deviations"])
    assert not any("notes.txt grew by" in deviation for deviation in response["deviations"])

def test_batch_out_of_range_raises(
    plan_fixture: PlanFixture,
) -> None:
    _setup_two_batch_plan(plan_fixture)
    make_args = plan_fixture.make_args
    with pytest.raises(megaplan.CliError, match="out of range"):
        megaplan.handle_execute(
            plan_fixture.root,
            make_args(plan=plan_fixture.plan_name, confirm_destructive=True, user_approved=True, batch=3),
        )

def test_batch_2_without_batch_1_raises_prerequisites(
    plan_fixture: PlanFixture,
) -> None:
    _setup_two_batch_plan(plan_fixture)
    make_args = plan_fixture.make_args
    with pytest.raises(megaplan.CliError, match="requires batches") as exc_info:
        megaplan.handle_execute(
            plan_fixture.root,
            make_args(plan=plan_fixture.plan_name, confirm_destructive=True, user_approved=True, batch=2),
        )
    assert exc_info.value.code == "batch_prerequisites"

def test_batch_1_on_single_batch_plan_transitions_to_executed(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _setup_two_batch_plan(plan_fixture)
    finalize_data = read_json(plan_fixture.plan_dir / "finalize.json")
    finalize_data["tasks"][1]["depends_on"] = []
    (plan_fixture.plan_dir / "finalize.json").write_text(
        json.dumps(finalize_data, indent=2) + "\n", encoding="utf-8"
    )
    monkeypatch.setattr(megaplan.execute.core, "_capture_git_status_snapshot", lambda *_: ({}, None))

    def single_batch_worker(step, state, plan_dir, args, *, root=None, resolved=None, prompt_override=None):
        payload = {
            "output": "All tasks complete.",
            "files_changed": ["batch1.py", "batch2.py"],
            "commands_run": ["pytest"],
            "deviations": [],
            "task_updates": [
                {"task_id": "T1", "status": "done", "executor_notes": "Done T1.", "files_changed": ["batch1.py"], "commands_run": ["pytest"]},
                {"task_id": "T2", "status": "done", "executor_notes": "Done T2.", "files_changed": ["batch2.py"], "commands_run": ["pytest"]},
            ],
            "sense_check_acknowledgments": [
                {"sense_check_id": "SC1", "executor_note": "Confirmed."},
                {"sense_check_id": "SC2", "executor_note": "Confirmed."},
            ],
        }
        return WorkerResult(payload=payload, raw_output="all", duration_ms=1, cost_usd=0.1, session_id="single"), "codex", "persistent", False

    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", single_batch_worker)

    make_args = plan_fixture.make_args
    response = megaplan.handle_execute(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, confirm_destructive=True, user_approved=True, batch=1),
    )

    assert response["state"] == megaplan.STATE_EXECUTED
    assert response["next_step"] == "review"
    assert (plan_fixture.plan_dir / "execution_batch_1.json").exists()
    assert (plan_fixture.plan_dir / "execution.json").exists()

def test_light_batch_1_on_single_batch_plan_transitions_to_done(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan_fixture = _make_plan_fixture_with_robustness(tmp_path, monkeypatch, robustness="light")
    _setup_two_batch_plan(plan_fixture)
    finalize_data = read_json(plan_fixture.plan_dir / "finalize.json")
    finalize_data["tasks"][1]["depends_on"] = []
    (plan_fixture.plan_dir / "finalize.json").write_text(
        json.dumps(finalize_data, indent=2) + "\n", encoding="utf-8"
    )
    monkeypatch.setattr(megaplan.execute.core, "_capture_git_status_snapshot", lambda *_: ({}, None))

    def single_batch_worker(step, state, plan_dir, args, *, root=None, resolved=None, prompt_override=None):
        payload = {
            "output": "All tasks complete.",
            "files_changed": ["batch1.py", "batch2.py"],
            "commands_run": ["pytest"],
            "deviations": [],
            "task_updates": [
                {"task_id": "T1", "status": "done", "executor_notes": "Done T1.", "files_changed": ["batch1.py"], "commands_run": ["pytest"]},
                {"task_id": "T2", "status": "done", "executor_notes": "Done T2.", "files_changed": ["batch2.py"], "commands_run": ["pytest"]},
            ],
            "sense_check_acknowledgments": [
                {"sense_check_id": "SC1", "executor_note": "Confirmed."},
                {"sense_check_id": "SC2", "executor_note": "Confirmed."},
            ],
        }
        return WorkerResult(payload=payload, raw_output="all", duration_ms=1, cost_usd=0.1, session_id="single"), "codex", "persistent", False

    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", single_batch_worker)

    response = megaplan.handle_execute(
        plan_fixture.root,
        plan_fixture.make_args(plan=plan_fixture.plan_name, confirm_destructive=True, user_approved=True, batch=1),
    )
    state = load_state(plan_fixture.plan_dir)
    stored_review = read_json(plan_fixture.plan_dir / "review.json")

    assert response["state"] == megaplan.STATE_DONE
    assert response["next_step"] is None
    assert state["current_state"] == megaplan.STATE_DONE
    assert "review.json" in response["artifacts"]
    assert stored_review["review_verdict"] == "approved"
    assert (plan_fixture.plan_dir / "execution_batch_1.json").exists()
    assert (plan_fixture.plan_dir / "execution.json").exists()

def test_batch_1_incomplete_tracking_returns_blocked(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _setup_two_batch_plan(plan_fixture)
    monkeypatch.setattr(megaplan.execute.core, "_capture_git_status_snapshot", lambda *_: ({}, None))

    def incomplete_batch_worker(step, state, plan_dir, args, *, root=None, resolved=None, prompt_override=None):
        assert prompt_override is not None
        return WorkerResult(
            payload={
                "output": "Batch one incomplete.",
                "files_changed": [],
                "commands_run": [],
                "deviations": [],
                "task_updates": [],
                "sense_check_acknowledgments": [],
            },
            raw_output="batch incomplete",
            duration_ms=1,
            cost_usd=0.0,
            session_id="batch-incomplete",
        ), "codex", "persistent", False

    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", incomplete_batch_worker)

    response = megaplan.handle_execute(
        plan_fixture.root,
        plan_fixture.make_args(plan=plan_fixture.plan_name, confirm_destructive=True, user_approved=True, batch=1),
    )
    state = load_state(plan_fixture.plan_dir)
    finalize_data = read_json(plan_fixture.plan_dir / "finalize.json")

    assert response["success"] is False
    assert response["state"] == megaplan.STATE_FINALIZED
    assert response["next_step"] == "execute"
    assert response["summary"] == (
        "Blocked: 1/1 tasks have no executor update; 1/1 sense checks have no executor acknowledgment. "
        "Re-run execute to complete tracking."
    )
    assert finalize_data["tasks"][0]["status"] == "pending"
    assert state["history"][-1]["result"] == "blocked"
