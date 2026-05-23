from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

import megaplan.cli as cli
import megaplan.execute.core as execute_core
from megaplan._core import atomic_write_json
from megaplan.types import EXECUTE_MODEL_WORKTREE_NATIVE, STATE_FINALIZED, CliError
from megaplan.workers import WorkerResult
from megaplan.worktrees.identity import make_task_identity
from megaplan.worktrees.registry import append_registry_entry


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_finalize(plan_dir: Path, tasks: list[dict[str, Any]]) -> None:
    sense_checks = [
        {
            "id": f"SC{index}",
            "task_id": task["id"],
            "question": f"{task['id']} complete?",
            "executor_note": "",
            "verdict": "",
        }
        for index, task in enumerate(tasks, start=1)
    ]
    atomic_write_json(
        plan_dir / "finalize.json",
        {
            "tasks": tasks,
            "sense_checks": sense_checks,
        },
    )


def _make_batch_result(
    *,
    batch_task_ids: list[str],
    batch_sense_check_ids: list[str],
    batch_number: int,
    agent: str,
    mode: str,
    refreshed: bool,
    model: str | None,
) -> execute_core.BatchResult:
    payload = {
        "output": f"Task group {batch_number} complete.",
        "files_changed": [f"task-{batch_number}.py"],
        "commands_run": [f"pytest task-{batch_number}"],
        "deviations": [],
        "task_updates": [
            {
                "task_id": task_id,
                "status": "done",
                "executor_notes": f"Completed {task_id}.",
                "files_changed": [f"task-{batch_number}.py"],
                "commands_run": [f"pytest task-{batch_number}"],
            }
            for task_id in batch_task_ids
        ],
        "sense_check_acknowledgments": [
            {
                "sense_check_id": sense_check_id,
                "executor_note": f"Acknowledged {sense_check_id}.",
            }
            for sense_check_id in batch_sense_check_ids
        ],
    }
    return execute_core.BatchResult(
        worker=WorkerResult(
            payload=payload,
            raw_output="",
            duration_ms=1,
            cost_usd=0.0,
            session_id=f"session-{batch_number}",
        ),
        agent=agent,
        mode=mode,
        refreshed=refreshed,
        payload=payload,
        batch_number=batch_number,
        batch_task_ids=list(batch_task_ids),
        batch_sense_check_ids=list(batch_sense_check_ids),
        merged_task_count=len(batch_task_ids),
        total_task_count=len(batch_task_ids),
        acknowledged_sense_check_count=len(batch_sense_check_ids),
        total_sense_check_count=len(batch_sense_check_ids),
        missing_task_evidence=[],
        execution_audit={"skipped": False, "reason": "", "findings": []},
        finalize_hash="fake-finalize-hash",
        attribution_records=[],
    )


def _prepare_state(plan_fixture: Any) -> dict[str, Any]:
    state = read_json(plan_fixture.plan_dir / "state.json")
    state["current_state"] = STATE_FINALIZED
    state["config"]["execute_model"] = EXECUTE_MODEL_WORKTREE_NATIVE
    state["config"]["secret_scan_mode"] = "local_only"
    state["config"]["max_tasks_per_batch"] = 99
    state.setdefault("meta", {})["user_approved_gate"] = True
    state["meta"]["current_invocation_id"] = "run17"
    return state


def test_worktree_native_auto_loop_dispatches_one_ready_task_at_a_time(
    plan_fixture: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tasks = [
        {"id": "T1", "description": "Task one", "depends_on": [], "status": "pending", "complexity": 1},
        {"id": "T2", "description": "Task two", "depends_on": [], "status": "pending", "complexity": 3},
        {"id": "T3", "description": "Task three", "depends_on": [], "status": "pending", "complexity": 5},
    ]
    _write_finalize(plan_fixture.plan_dir, tasks)
    state = _prepare_state(plan_fixture)
    monkeypatch.setattr(execute_core, "load_config", lambda: {})
    monkeypatch.setattr(execute_core, "_capture_git_status_snapshot", lambda *_: ({}, None))
    monkeypatch.setattr(
        execute_core, "_capture_git_status_snapshot_recursive", lambda *_: ({}, None)
    )
    monkeypatch.setattr(
        execute_core,
        "_resolve_tier_spec",
        lambda args, tier_spec: ("codex", "persistent", tier_spec),
    )
    monkeypatch.setattr(
        execute_core,
        "_execute_batch_prompt",
        lambda state, plan_dir, task_ids, completed_ids, *, root: json.dumps(
            {"task_ids": task_ids, "completed_ids": sorted(completed_ids)}
        ),
    )
    dispatches: list[dict[str, Any]] = []

    def _fake_run_and_merge(**kwargs: Any) -> execute_core.BatchResult:
        dispatches.append(
            {
                "task_ids": list(kwargs["batch_task_ids"]),
                "model": kwargs["model"],
                "auto_attribution": kwargs["enable_auto_attribution"],
            }
        )
        if len(dispatches) == 2:
            interim = read_json(plan_fixture.plan_dir / "execution.json")
            assert [item["task_id"] for item in interim["task_artifacts"]] == ["T1"]
        task_id = kwargs["batch_task_ids"][0]
        identity = make_task_identity(task_id)
        append_registry_entry(
            plan_fixture.project_dir,
            "run17",
            "integration_complete",
            {"commit_sha": f"commit-{task_id}", "terminal": True},
            identity=identity,
        )
        finalize_data = read_json(kwargs["plan_dir"] / "finalize.json")
        for task in finalize_data["tasks"]:
            if task["id"] in kwargs["batch_task_ids"]:
                task["status"] = "done"
                task["executor_notes"] = f"Completed {task['id']}."
                task["files_changed"] = [f"{task['id']}.py"]
                task["commands_run"] = ["pytest tests/test_task.py"]
        for sense_check in finalize_data["sense_checks"]:
            if sense_check["id"] in kwargs["batch_sense_check_ids"]:
                sense_check["executor_note"] = "Acknowledged."
                sense_check["verdict"] = "pass"
        atomic_write_json(kwargs["plan_dir"] / "finalize.json", finalize_data)
        kwargs["finalize_data"].update(finalize_data)
        return _make_batch_result(
            batch_task_ids=kwargs["batch_task_ids"],
            batch_sense_check_ids=kwargs["batch_sense_check_ids"],
            batch_number=kwargs["batch_number"],
            agent=kwargs["agent"],
            mode=kwargs["mode"],
            refreshed=kwargs["refreshed"],
            model=kwargs["model"],
        )

    monkeypatch.setattr(execute_core, "_run_and_merge_batch", _fake_run_and_merge)

    response = execute_core.handle_execute_auto_loop(
        root=plan_fixture.root,
        plan_dir=plan_fixture.plan_dir,
        state=state,
        args=plan_fixture.make_args(plan=plan_fixture.plan_name, user_approved=True),
        auto_approve=True,
        agent="codex",
        mode="persistent",
        refreshed=False,
        tier_map={1: "model-one", 3: "model-three", 5: "model-five"},
    )

    assert response["success"] is True
    assert [item["task_ids"] for item in dispatches] == [["T1"], ["T2"], ["T3"]]
    assert [item["model"] for item in dispatches] == [
        "model-one",
        "model-three",
        "model-five",
    ]
    assert [item["auto_attribution"] for item in dispatches] == [False, False, False]
    for task_id in ["T1", "T2", "T3"]:
        identity = make_task_identity(task_id)
        artifact = (
            plan_fixture.plan_dir
            / "tasks"
            / identity.task_key
            / "execution.json"
        )
        artifact_data = read_json(artifact)
        assert artifact_data["task_key"] == identity.task_key
        assert artifact_data["secret_scan"]["mode"] == "local_only"
        metadata = artifact_data["metadata"]
        assert metadata["identity"]["task_key"] == identity.task_key
        assert metadata["trailers"] == identity.trailer_fields()
        assert metadata["tier"]["task_id"] == task_id
        assert metadata["progress"]["event"] == "task_complete"
        assert metadata["registry"]["available"] is True
        assert metadata["integration"]["available"] is True
        assert metadata["patch"]["available"] is False
        assert metadata["receipt"]["agent"] == "codex"
    execution = read_json(plan_fixture.plan_dir / "execution.json")
    assert [item["task_id"] for item in execution["task_artifacts"]] == [
        "T1",
        "T2",
        "T3",
    ]
    assert "batch_to_tier" not in execution
    progress = cli._build_progress_payload(plan_fixture.plan_dir, state)
    assert progress["current_task"] is None
    assert [item["task_id"] for item in progress["task_artifacts"]] == ["T1", "T2", "T3"]
    first_task_execution = progress["tasks"][0]["task_execution"]
    assert first_task_execution["task_key"] == make_task_identity("T1").task_key
    assert first_task_execution["artifact"].startswith("tasks/")
    assert first_task_execution["secret_scan"]["mode"] == "local_only"
    assert first_task_execution["integration"]["state"] == "integration_complete"
    assert first_task_execution["tier"]["selected_model"] == "model-one"
    assert first_task_execution["commit_identity"]["trailers_present"] is True
    status_payload = cli._build_status_payload(plan_fixture.plan_dir, state)
    assert status_payload["task_artifact_count"] == 3
    assert status_payload["task_artifacts"][0]["task_key"] == make_task_identity("T1").task_key


def test_worktree_native_timeout_writes_task_blocked_evidence(
    plan_fixture: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tasks = [
        {
            "id": "T-timeout",
            "description": "Task that times out",
            "depends_on": [],
            "status": "pending",
            "complexity": 2,
        },
    ]
    _write_finalize(plan_fixture.plan_dir, tasks)
    state = _prepare_state(plan_fixture)
    monkeypatch.setattr(execute_core, "load_config", lambda: {})
    monkeypatch.setattr(execute_core, "_capture_git_status_snapshot", lambda *_: ({}, None))
    monkeypatch.setattr(
        execute_core,
        "_execute_batch_prompt",
        lambda state, plan_dir, task_ids, completed_ids, *, root: json.dumps(
            {"task_ids": task_ids, "completed_ids": sorted(completed_ids)}
        ),
    )

    def _timeout(**kwargs: Any) -> execute_core.BatchResult:
        raise CliError(
            "worker_timeout",
            "worker timed out",
            extra={"session_id": "timeout-session"},
        )

    monkeypatch.setattr(execute_core, "_run_and_merge_batch", _timeout)

    response = execute_core.handle_execute_auto_loop(
        root=plan_fixture.root,
        plan_dir=plan_fixture.plan_dir,
        state=state,
        args=plan_fixture.make_args(plan=plan_fixture.plan_name, user_approved=True),
        auto_approve=True,
        agent="codex",
        mode="persistent",
        refreshed=False,
    )

    assert response["success"] is False
    assert response["_phase_outcome"] == "timeout"
    finalize_data = read_json(plan_fixture.plan_dir / "finalize.json")
    assert finalize_data["tasks"][0]["status"] == "blocked"
    identity = make_task_identity("T-timeout")
    artifact = (
        plan_fixture.plan_dir / "tasks" / identity.task_key / "execution.json"
    )
    artifact_data = read_json(artifact)
    assert artifact_data["status"] == "blocked"
    assert artifact_data["blocked_reason"] == "worker_timeout"
    assert artifact_data["worktree_preserved"] is True
