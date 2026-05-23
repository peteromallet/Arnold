from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

import megaplan.worktrees.patches as patches_module
import megaplan.worktrees.integration as integration_module
from megaplan._core import atomic_write_json
from megaplan.orchestration.progress import ProgressEmitter
from megaplan.store import FileStore, PlanRepository
from megaplan.worktrees import (
    TaskIntegrationError,
    capture_patch_bundle,
    integrate_task_patch,
    load_patch_bundle,
    make_task_identity,
    prepare_task_worktree,
    read_registry_entries,
)
from megaplan.worktrees.identity import build_task_identity_map, validate_trailer_identity


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        text=True,
        capture_output=True,
        check=True,
    )


def _init_repo(repo: Path) -> None:
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    (repo / "file.txt").write_text("base\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base")


def _clone_repo(source: Path, destination: Path) -> None:
    subprocess.run(["git", "clone", str(source), str(destination)], text=True, capture_output=True, check=True)
    _git(destination, "config", "user.email", "test@example.com")
    _git(destination, "config", "user.name", "Test User")


def _finalize_data(task_id: str = "T14") -> dict[str, object]:
    return {"tasks": [{"id": task_id, "description": "Integrate task patch"}]}


def _entry_types(project_dir: Path, run_id: str) -> list[str]:
    return [entry["entry_type"] for entry in read_registry_entries(project_dir, run_id)]


def _parse_trailers(message: str) -> dict[str, str]:
    trailers: dict[str, str] = {}
    for line in message.splitlines():
        if ": " not in line:
            continue
        key, value = line.split(": ", 1)
        trailers[key] = value
    return trailers


def test_integrate_task_patch_applies_commits_records_order_and_prunes_after_terminal(
    tmp_path: Path,
) -> None:
    milestone = tmp_path / "milestone"
    task_worktree = tmp_path / "task-worktree"
    project_dir = tmp_path / "coordinator"
    _init_repo(milestone)
    _clone_repo(milestone, task_worktree)
    identity = make_task_identity("T14")
    (task_worktree / "file.txt").write_text("base\nchanged\n", encoding="utf-8")
    capture_patch_bundle(project_dir, "run-14", "T14", task_worktree, secret_scan_mode="local_only", identity=identity)

    result = integrate_task_patch(
        project_dir,
        "run-14",
        "T14",
        milestone,
        _finalize_data(),
        prune_task_worktree=task_worktree,
    )

    assert result.status == "complete"
    assert result.task_key == identity.task_key
    assert result.commit_sha == _git(milestone, "rev-parse", "HEAD").stdout.strip()
    assert result.staged_fingerprint.startswith("sha256:")
    assert result.pruned is True
    assert not task_worktree.exists()
    assert _git(milestone, "status", "--porcelain=v1").stdout == ""
    assert (milestone / "file.txt").read_text(encoding="utf-8") == "base\nchanged\n"
    commit_message = _git(milestone, "log", "-1", "--format=%B").stdout
    assert commit_message.startswith(f"mp-task:{identity.task_key}\n")
    for key, value in identity.trailer_fields().items():
        assert f"{key}: {value}" in commit_message

    entry_types = _entry_types(project_dir, "run-14")
    expected_tail = [
        "integration_started",
        "clean_checkout_verified",
        "apply_checked",
        "patch_applied",
        "staged_fingerprinted",
        "task_committed",
        "push_noop",
        "pr_noop",
        "integration_complete",
        "prune_started",
        "pruned",
    ]
    assert entry_types[0] == "patch_captured"
    assert entry_types[1:] == expected_tail
    assert entry_types.index("integration_complete") < entry_types.index("prune_started")
    entries = read_registry_entries(project_dir, "run-14")
    assert all(entry["task_key"] == identity.task_key for entry in entries)
    committed = next(entry for entry in entries if entry["entry_type"] == "task_committed")
    assert committed["payload"]["message_subject"] == f"mp-task:{identity.task_key}"
    assert committed["payload"]["trailers"] == identity.trailer_fields()


def test_integrate_task_patch_requires_clean_milestone_before_apply(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    milestone = tmp_path / "milestone"
    task_worktree = tmp_path / "task-worktree"
    project_dir = tmp_path / "coordinator"
    _init_repo(milestone)
    _clone_repo(milestone, task_worktree)
    (task_worktree / "file.txt").write_text("base\nchanged\n", encoding="utf-8")
    capture_patch_bundle(project_dir, "run-14", "T14", task_worktree, secret_scan_mode="local_only")
    (milestone / "file.txt").write_text("dirty\n", encoding="utf-8")

    def fail_if_called(_repo: Path, _bundle: object) -> None:
        raise AssertionError("bundle must not be applied when the milestone checkout is dirty")

    monkeypatch.setattr(integration_module, "_apply_bundle_to_index", fail_if_called)

    with pytest.raises(TaskIntegrationError) as excinfo:
        integrate_task_patch(project_dir, "run-14", "T14", milestone, _finalize_data())

    assert excinfo.value.code == "milestone_checkout_dirty"
    assert (milestone / "file.txt").read_text(encoding="utf-8") == "dirty\n"
    assert _entry_types(project_dir, "run-14") == ["patch_captured", "integration_started"]


def test_serial_dependent_tasks_integrate_real_git_commits_artifacts_and_progress(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    milestone = tmp_path / "milestone"
    run_id = "run-20"
    _init_repo(milestone)
    plan_dir = milestone / ".megaplan" / "plans" / "serial-real-git"
    plan_dir.mkdir(parents=True)
    tasks = [
        {
            "id": "Path_Task_01",
            "description": "Create the first line",
            "depends_on": [],
            "status": "pending",
            "complexity": 1,
        },
        {
            "id": "Trailer-Task_02",
            "description": "Append the second line",
            "depends_on": ["Path_Task_01"],
            "status": "pending",
            "complexity": 3,
        },
        {
            "id": "Serial_Task-03",
            "description": "Append the third line",
            "depends_on": ["Trailer-Task_02"],
            "status": "pending",
            "complexity": 5,
        },
    ]
    finalize_data: dict[str, object] = {"tasks": tasks, "sense_checks": []}
    atomic_write_json(
        plan_dir / "state.json",
        {
            "current_state": "finalized",
            "config": {
                "execute_model": "worktree_native",
                "secret_scan_mode": "pr_pushed",
            },
        },
    )
    atomic_write_json(plan_dir / "finalize.json", finalize_data)
    (plan_dir / "state.idea").write_text("serial real git\n", encoding="utf-8")
    (plan_dir / "plan.md").write_text("# Plan\n", encoding="utf-8")
    (milestone / ".gitignore").write_text(
        ".megaplan-worktrees/\n.megaplan/worktrees/\n.megaplan/plans/*/tasks/\n",
        encoding="utf-8",
    )
    _git(milestone, "add", ".")
    _git(milestone, "commit", "-m", "add plan context")
    base_before_tasks = _git(milestone, "rev-parse", "HEAD").stdout.strip()

    def fake_secret_scan(worktree: Path, *, mode: str) -> dict[str, object]:
        return {
            "mode": mode,
            "source": "execution.secret_scan_mode",
            "status": "passed",
            "available": True,
            "explicit_local_only_opt_in": mode == "local_only",
            "redacted_reason": "",
        }

    monkeypatch.setattr(patches_module, "run_gitleaks_policy", fake_secret_scan)

    store = FileStore(tmp_path / "store")
    epic = store.create_epic(title="Epic", goal="Goal", body="Body")
    emitter = ProgressEmitter(
        store,
        epic_id=epic.id,
        plan_id="serial-real-git",
        sprint_id="sprint-b",
        run_id=run_id,
    )
    repository = PlanRepository.from_plan_dir(plan_dir)
    identity_map = build_task_identity_map(tasks)
    commit_shas: list[str] = []
    base_shas: list[str] = []
    secret_modes = ["pr_pushed", "local_only", "pr_pushed"]

    for index, task in enumerate(tasks, start=1):
        task_id = task["id"]
        identity = identity_map[task_id]
        record = prepare_task_worktree(milestone, plan_dir, run_id, identity)
        base_shas.append(record.base_sha)
        assert _git(milestone, "status", "--porcelain=v1").stdout == ""

        feature_path = record.worktree_path / "file.txt"
        feature_path.write_text(feature_path.read_text(encoding="utf-8") + f"{task_id}\n", encoding="utf-8")
        assert _git(milestone, "status", "--porcelain=v1").stdout == ""
        assert _git(record.worktree_path, "status", "--porcelain=v1").stdout != ""

        capture = capture_patch_bundle(
            milestone,
            run_id,
            task_id,
            record.worktree_path,
            secret_scan_mode=secret_modes[index - 1],
            identity=identity,
        )
        bundle = load_patch_bundle(milestone, run_id, task_id)
        result = integrate_task_patch(
            milestone,
            run_id,
            task_id,
            milestone,
            finalize_data,
            prune_task_worktree=record.worktree_path,
        )
        progress_event = emitter.task_complete(
            identity.task_key,
            task_id=task_id,
            task_id_encoded=identity.original_task_id_encoded,
            status="done",
        )
        assert progress_event is not None

        registry_entries = [
            entry
            for entry in read_registry_entries(milestone, run_id)
            if entry["task_key"] == identity.task_key
        ]
        integration_entries = [
            entry for entry in registry_entries if entry["entry_type"].startswith("integration_")
        ]
        repository.write_task_execution_artifact(
            identity,
            {
                "task_id": task_id,
                "task_key": identity.task_key,
                "status": "done",
                "files_changed": ["file.txt"],
                "commands_run": ["git status --porcelain=v1"],
                "secret_scan": bundle.secret_scan,
                "metadata": {
                    "identity": identity.registry_identity(),
                    "trailers": identity.trailer_fields(),
                    "patch": {
                        "available": True,
                        "manifest_path": str(capture.manifest_path),
                        "patch_path": str(capture.patch_path),
                        "secret_scan": bundle.secret_scan,
                    },
                    "progress": {
                        "event": "task_complete",
                        "task_key": identity.task_key,
                        "status": "done",
                    },
                    "registry": {
                        "available": True,
                        "entry_count": len(registry_entries),
                        "entries": registry_entries,
                    },
                    "integration": {
                        "available": True,
                        "state": "integration_complete",
                        "commit_sha": result.commit_sha,
                        "entries": integration_entries,
                    },
                    "tier": {
                        "task_id": task_id,
                        "task_complexity": task["complexity"],
                        "resolved_model": f"model-{index}",
                    },
                    "receipt": {"agent": "mock-worker", "mode": "task-worktree"},
                },
            },
        )
        commit_shas.append(result.commit_sha or "")
        assert result.status == "complete"
        assert result.task_key == identity.task_key
        assert result.pruned is True
        assert not record.worktree_path.exists()
        assert _git(milestone, "status", "--porcelain=v1").stdout == ""

    assert base_shas == [base_before_tasks, commit_shas[0], commit_shas[1]]
    assert (milestone / "file.txt").read_text(encoding="utf-8") == (
        "base\nPath_Task_01\nTrailer-Task_02\nSerial_Task-03\n"
    )

    subjects = _git(milestone, "log", "--first-parent", "--format=%s", "-3").stdout.splitlines()
    expected_subjects = [
        f"mp-task:{identity_map['Serial_Task-03'].task_key}",
        f"mp-task:{identity_map['Trailer-Task_02'].task_key}",
        f"mp-task:{identity_map['Path_Task_01'].task_key}",
    ]
    assert subjects == expected_subjects
    for task in tasks:
        identity = identity_map[task["id"]]
        commit_sha = commit_shas[tasks.index(task)]
        message = _git(milestone, "log", "-1", "--format=%B", commit_sha).stdout
        assert message.startswith(f"mp-task:{identity.task_key}\n")
        assert task["id"] not in message
        trailers = _parse_trailers(message)
        assert trailers == identity.trailer_fields()
        assert validate_trailer_identity(trailers, identity_map) == identity

    registry_entries = read_registry_entries(milestone, run_id)
    assert registry_entries
    assert all(entry["schema_version"] == 2 for entry in registry_entries)
    assert all("task_key" in entry and "task_id" not in entry for entry in registry_entries)
    for task in tasks:
        identity = identity_map[task["id"]]
        task_entry_types = [
            entry["entry_type"]
            for entry in registry_entries
            if entry["task_key"] == identity.task_key
        ]
        assert "task_worktree_created" in task_entry_types
        assert "task_context_snapshot_created" in task_entry_types
        assert "patch_captured" in task_entry_types
        assert "task_committed" in task_entry_types
        assert "integration_complete" in task_entry_types

    task_artifacts = repository.list_task_execution_summaries()
    artifacts_by_task = {artifact["task_id"]: artifact for artifact in task_artifacts}
    assert set(artifacts_by_task) == {task["id"] for task in tasks}
    assert [
        artifacts_by_task[task["id"]]["secret_scan"]["mode"]
        for task in tasks
    ] == secret_modes
    assert all(
        artifacts_by_task[task["id"]]["commit_identity"]["trailers_present"]
        for task in tasks
    )
    assert all(
        artifacts_by_task[task["id"]]["integration"]["state"] == "integration_complete"
        for task in tasks
    )

    events = store.list_progress_events(epic_id=epic.id, plan_id="serial-real-git")
    assert [event.kind for event in events] == ["task_complete", "task_complete", "task_complete"]
    assert [event.details["task_key"] for event in events] == [
        identity_map[task["id"]].task_key for task in tasks
    ]
    state = (plan_dir / "state.json").read_text(encoding="utf-8")
    assert "max_tasks_per_batch" not in state
