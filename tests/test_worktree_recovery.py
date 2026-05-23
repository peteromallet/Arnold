from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

import megaplan.worktrees.registry as registry_module
from megaplan.store.plan_repository import PlanRepository
from megaplan.worktrees import (
    capture_patch_bundle,
    custody_paths,
    load_patch_bundle,
    make_task_identity,
    read_registry_entries,
    reconcile_task_integration,
)
from megaplan.worktrees.integration import _apply_bundle_to_index, _commit_staged


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


def _finalize_data(task_id: str = "T15") -> dict[str, object]:
    return {"tasks": [{"id": task_id, "description": "Recover task integration"}]}


def _captured_patch(tmp_path: Path) -> tuple[Path, Path, Path]:
    milestone = tmp_path / "milestone"
    task_worktree = tmp_path / "task-worktree"
    project_dir = tmp_path / "coordinator"
    _init_repo(milestone)
    _clone_repo(milestone, task_worktree)
    (task_worktree / "file.txt").write_text("base\nchanged\n", encoding="utf-8")
    capture_patch_bundle(project_dir, "run-15", "T15", task_worktree, secret_scan_mode="local_only")
    return project_dir, milestone, task_worktree


def _entry_types(project_dir: Path) -> list[str]:
    return [entry["entry_type"] for entry in read_registry_entries(project_dir, "run-15")]


def test_reconcile_post_apply_pre_commit_commits_and_records_terminal_state(tmp_path: Path) -> None:
    project_dir, milestone, _task_worktree = _captured_patch(tmp_path)
    bundle = load_patch_bundle(project_dir, "run-15", "T15")
    _apply_bundle_to_index(milestone, bundle)
    identity = make_task_identity("T15")
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    (plan_dir / "state.json").write_text("{}", encoding="utf-8")
    PlanRepository.from_plan_dir(plan_dir).write_task_execution_artifact(identity, {"status": "done", "task_key": identity.task_key})
    progress_events = [{"kind": "task_complete", "task_key": identity.task_key, "summary": "done"}]

    result = reconcile_task_integration(
        project_dir,
        "run-15",
        "T15",
        milestone,
        _finalize_data(),
        plan_dir=plan_dir,
        progress_events=progress_events,
    )

    assert result.status == "reconciled"
    assert result.action == "commit_staged_patch"
    assert result.commit_sha == _git(milestone, "rev-parse", "HEAD").stdout.strip()
    assert _git(milestone, "status", "--porcelain=v1").stdout == ""
    assert (milestone / "file.txt").read_text(encoding="utf-8") == "base\nchanged\n"
    assert result.evidence["task_artifact"]["status"] == "done"
    assert result.evidence["progress"]["task_complete_events"] == progress_events
    entry_types = _entry_types(project_dir)
    assert "recovery_checked" in entry_types
    assert "recovery_reconciled" in entry_types
    assert "task_committed" in entry_types
    assert entry_types[-1] == "integration_complete"

    second = reconcile_task_integration(
        project_dir,
        "run-15",
        "T15",
        milestone,
        _finalize_data(),
        plan_dir=plan_dir,
        progress_events=progress_events,
    )

    assert second.status == "already_complete"
    assert second.commit_sha == result.commit_sha
    assert (milestone / "file.txt").read_text(encoding="utf-8") == "base\nchanged\n"
    assert _entry_types(project_dir).count("integration_complete") == 1


def test_reconcile_post_commit_pre_registry_records_existing_commit_idempotently(tmp_path: Path) -> None:
    project_dir, milestone, _task_worktree = _captured_patch(tmp_path)
    identity = make_task_identity("T15")
    bundle = load_patch_bundle(project_dir, "run-15", "T15")
    _apply_bundle_to_index(milestone, bundle)
    commit_sha = _commit_staged(milestone, identity)

    result = reconcile_task_integration(project_dir, "run-15", "T15", milestone, _finalize_data())

    assert result.status == "reconciled"
    assert result.action == "record_existing_commit"
    assert result.commit_sha == commit_sha
    assert _git(milestone, "rev-parse", "HEAD").stdout.strip() == commit_sha
    entry_types = _entry_types(project_dir)
    assert "task_committed" in entry_types
    assert "integration_complete" in entry_types
    assert "recovery_idempotent" in entry_types

    second = reconcile_task_integration(project_dir, "run-15", "T15", milestone, _finalize_data())

    assert second.status == "already_complete"
    assert second.commit_sha == commit_sha
    assert _entry_types(project_dir).count("integration_complete") == 1


def test_reconcile_blocks_index_lock_before_mutation(tmp_path: Path) -> None:
    project_dir, milestone, _task_worktree = _captured_patch(tmp_path)
    (milestone / ".git" / "index.lock").write_text("locked\n", encoding="utf-8")

    result = reconcile_task_integration(project_dir, "run-15", "T15", milestone, _finalize_data())

    assert result.status == "blocked"
    assert result.blocked_reason == "index_lock"
    assert _git(milestone, "rev-parse", "--verify", "HEAD").stdout.strip() == load_patch_bundle(
        project_dir, "run-15", "T15"
    ).base_head
    assert "recovery_blocked" in _entry_types(project_dir)


def test_reconcile_blocks_conflicted_checkout_before_mutation(tmp_path: Path) -> None:
    project_dir, milestone, _task_worktree = _captured_patch(tmp_path)
    default_branch = _git(milestone, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    _git(milestone, "checkout", "-b", "other")
    (milestone / "file.txt").write_text("other\n", encoding="utf-8")
    _git(milestone, "commit", "-am", "other edit")
    _git(milestone, "checkout", default_branch)
    (milestone / "file.txt").write_text("master\n", encoding="utf-8")
    _git(milestone, "commit", "-am", "master edit")
    merge = subprocess.run(
        ["git", "merge", "other"],
        cwd=milestone,
        text=True,
        capture_output=True,
        check=False,
    )
    assert merge.returncode != 0
    assert _git(milestone, "ls-files", "-u").stdout

    result = reconcile_task_integration(project_dir, "run-15", "T15", milestone, _finalize_data())

    assert result.status == "blocked"
    assert result.blocked_reason == "conflicted_checkout"
    assert "recovery_blocked" in _entry_types(project_dir)


def test_reconcile_blocks_manifest_identity_and_secret_scan_disagreement(tmp_path: Path) -> None:
    project_dir, milestone, _task_worktree = _captured_patch(tmp_path)
    bundle = load_patch_bundle(project_dir, "run-15", "T15")
    manifest = json.loads(bundle.manifest_path.read_text(encoding="utf-8"))
    manifest["identity"]["task_key"] = "wrong-1111111111111111"
    bundle.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = reconcile_task_integration(project_dir, "run-15", "T15", milestone, _finalize_data())

    assert result.status == "blocked"
    assert result.blocked_reason == "identity_mismatch"

    secret_root = tmp_path / "secret"
    secret_root.mkdir()
    project_dir, milestone, _task_worktree = _captured_patch(secret_root)
    bundle = load_patch_bundle(project_dir, "run-15", "T15")
    manifest = json.loads(bundle.manifest_path.read_text(encoding="utf-8"))
    manifest["secret_scan"]["mode"] = "pr_pushed"
    bundle.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = reconcile_task_integration(project_dir, "run-15", "T15", milestone, _finalize_data())

    assert result.status == "blocked"
    assert result.blocked_reason == "secret_scan_disagreement"


def test_reconcile_blocks_existing_commit_with_malformed_trailers(tmp_path: Path) -> None:
    project_dir, milestone, _task_worktree = _captured_patch(tmp_path)
    identity = make_task_identity("T15")
    bundle = load_patch_bundle(project_dir, "run-15", "T15")
    _apply_bundle_to_index(milestone, bundle)
    _git(milestone, "commit", "-m", f"mp-task:{identity.task_key}\n\nTask-Key: {identity.task_key}")

    result = reconcile_task_integration(project_dir, "run-15", "T15", milestone, _finalize_data())

    assert result.status == "blocked"
    assert result.blocked_reason == "malformed_trailers"
    assert "recovery_blocked" in _entry_types(project_dir)


@pytest.mark.parametrize(
    "message",
    [
        "mp-task:{key}\n\nTask-Key: {key}\nTask-Key: {key}\nTask-Id-Encoding: {encoding}\nTask-Id-B64: {encoded}",
        "mp-task:{key}\n\nTask-Key: {key}\n continuation\nTask-Id-Encoding: {encoding}\nTask-Id-B64: {encoded}",
        "mp-task:{key}\n\nTask-Key: {key}\nTask-Id-Encoding: {encoding}\nTask-Id-B64: ____",
        "mp-task:{key}\n\nTask-Key: {key}\nTask-Id: T15\nTask-Id-Encoding: {encoding}\nTask-Id-B64: {encoded}",
    ],
)
def test_reconcile_blocks_duplicate_multiline_undecodable_and_raw_trailers(
    tmp_path: Path,
    message: str,
) -> None:
    project_dir, milestone, _task_worktree = _captured_patch(tmp_path)
    identity = make_task_identity("T15")
    bundle = load_patch_bundle(project_dir, "run-15", "T15")
    _apply_bundle_to_index(milestone, bundle)
    trailers = identity.trailer_fields()
    _git(
        milestone,
        "commit",
        "-m",
        message.format(
            key=identity.task_key,
            encoding=trailers["Task-Id-Encoding"],
            encoded=trailers["Task-Id-B64"],
        ),
    )

    result = reconcile_task_integration(project_dir, "run-15", "T15", milestone, _finalize_data())

    assert result.status == "blocked"
    assert result.blocked_reason == "malformed_trailers"


def test_reconcile_blocks_existing_commit_with_identity_mismatch_trailers(tmp_path: Path) -> None:
    project_dir, milestone, _task_worktree = _captured_patch(tmp_path)
    identity = make_task_identity("T15")
    other = make_task_identity("T99")
    bundle = load_patch_bundle(project_dir, "run-15", "T15")
    _apply_bundle_to_index(milestone, bundle)
    _git(
        milestone,
        "commit",
        "-m",
        "\n".join(
            [
                f"mp-task:{identity.task_key}",
                "",
                f"Task-Key: {identity.task_key}",
                f"Task-Id-Encoding: {other.trailer_encoding}",
                f"Task-Id-B64: {other.original_task_id_encoded}",
            ]
        ),
    )

    result = reconcile_task_integration(project_dir, "run-15", "T15", milestone, _finalize_data())

    assert result.status == "blocked"
    assert result.blocked_reason == "identity_mismatch"


def test_reconcile_blocks_invalid_schema_v2_registry_records(tmp_path: Path) -> None:
    project_dir, milestone, _task_worktree = _captured_patch(tmp_path)
    paths = custody_paths(project_dir)
    entries = read_registry_entries(project_dir, "run-15")
    entries[0]["task_id"] = "T15"
    entries[0]["entry_hash"] = registry_module._entry_digest(entries[0])
    paths.registry_jsonl("run-15").write_text(
        "".join(json.dumps(entry, sort_keys=True, separators=(",", ":")) + "\n" for entry in entries),
        encoding="utf-8",
    )

    result = reconcile_task_integration(project_dir, "run-15", "T15", milestone, _finalize_data())

    assert result.status == "blocked"
    assert result.blocked_reason == "invalid_registry"
    assert result.evidence["registry"]["error"]["code"] == "identity_mismatch"
