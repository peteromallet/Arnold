from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

import megaplan.cli
from megaplan.worktrees import append_registry_entry, build_custody_report, custody_paths
from megaplan.worktrees.identity import make_task_identity
from megaplan.store import PlanRepository


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        text=True,
        capture_output=True,
        check=True,
    )


def _init_repo(repo: Path) -> str:
    repo.mkdir(parents=True)
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    (repo / "tracked.txt").write_text("base\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base")
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _tree_hashes(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    return {
        child.relative_to(path).as_posix(): hashlib.sha256(child.read_bytes()).hexdigest()
        for child in sorted(path.rglob("*"))
        if child.is_file()
    }


def _issue_codes(report: dict) -> set[str]:
    return {issue["code"] for issue in report["issues"]}


def test_custody_report_is_read_only_and_reports_dirty_registered_worktree(
    tmp_path: Path,
) -> None:
    project_dir = tmp_path / "repo"
    worktree = tmp_path / "task-worktree"
    _init_repo(worktree)
    (worktree / "tracked.txt").write_text("base\nchanged\n", encoding="utf-8")
    append_registry_entry(
        project_dir,
        "run-11",
        "task_worktree_created",
        {"worktree": str(worktree)},
        task_id="T11",
    )
    before = _tree_hashes(custody_paths(project_dir).custody_root)

    report = build_custody_report(project_dir, "run-11")

    assert _tree_hashes(custody_paths(project_dir).custody_root) == before
    assert report["read_only"] is True
    assert report["persisted_path"] is None
    assert "task_worktree_dirty" in _issue_codes(report)
    assert report["tasks"][0]["task_id"] == "T11"
    assert report["tasks"][0]["worktree_dirty"] is True


def test_custody_report_surfaces_worktree_orphan_missing_and_lock_drift(
    tmp_path: Path,
) -> None:
    project_dir = tmp_path / "repo"
    paths = custody_paths(project_dir)
    orphan = paths.scratch_worktree("run-11", "T-orphan")
    _init_repo(orphan)
    append_registry_entry(
        project_dir,
        "run-11",
        "task_registered",
        {"worktree": str(tmp_path / "missing-worktree")},
        task_id="T-missing",
    )
    paths.registry_lock("run-11").unlink()

    report = build_custody_report(project_dir, "run-11")

    assert {
        "task_worktree_unregistered",
        "task_worktree_missing",
        "registry_lock_missing",
    }.issubset(_issue_codes(report))


def test_custody_report_surfaces_bundle_base_sha_and_secret_scan_drift(
    tmp_path: Path,
) -> None:
    project_dir = tmp_path / "repo"
    worktree = tmp_path / "task-worktree"
    base_head = _init_repo(worktree)
    append_registry_entry(
        project_dir,
        "run-11",
        "task_worktree_created",
        {"worktree": str(worktree)},
        task_id="T11",
    )
    paths = custody_paths(project_dir)
    patch_path = paths.patch_payload("run-11", "T11")
    patch_path.parent.mkdir(parents=True)
    patch_path.write_text("patch body changed\n", encoding="utf-8")
    _write_json(
        paths.patch_manifest("run-11", "T11"),
        {
            "schema_version": 1,
            "run_id": "run-11",
            "task_id": "T11",
            "worktree": str(worktree),
            "base_head": base_head,
            "patch": {
                "path": patch_path.relative_to(paths.custody_root).as_posix(),
                "sha256": "sha256:" + "0" * 64,
                "size_bytes": 1,
            },
            "secret_scan": {"status": "failed", "mode": "pr_pushed"},
        },
    )
    (worktree / "second.txt").write_text("second\n", encoding="utf-8")
    _git(worktree, "add", ".")
    _git(worktree, "commit", "-m", "second")

    report = build_custody_report(project_dir, "run-11")

    assert {
        "bundle_patch_drift",
        "base_sha_mismatch",
        "secret_scan_failed",
    }.issubset(_issue_codes(report))
    task = report["tasks"][0]
    assert task["base_sha_matches"] is False
    assert task["secret_scan_status"] == "failed"


def test_custody_report_surfaces_manifest_patch_missing_and_skipped_scan(
    tmp_path: Path,
) -> None:
    project_dir = tmp_path / "repo"
    worktree = tmp_path / "task-worktree"
    _init_repo(worktree)
    append_registry_entry(
        project_dir,
        "run-11",
        "task_worktree_created",
        {"worktree": str(worktree)},
        task_id="T11",
    )
    paths = custody_paths(project_dir)
    _write_json(
        paths.patch_manifest("run-11", "T11"),
        {
            "patch": {
                "path": paths.patch_payload("run-11", "T11").relative_to(paths.custody_root).as_posix(),
                "sha256": "sha256:" + "0" * 64,
                "size_bytes": 0,
            },
            "secret_scan": {"status": "skipped", "mode": "local_only"},
        },
    )

    report = build_custody_report(project_dir, "run-11")

    assert {"bundle_patch_missing", "secret_scan_skipped"}.issubset(_issue_codes(report))


def test_custody_report_surfaces_task_artifact_status_metadata(tmp_path: Path) -> None:
    project_dir = tmp_path / "repo"
    identity = make_task_identity("T11")
    append_registry_entry(
        project_dir,
        "run-11",
        "integration_complete",
        {"commit_sha": "abc123", "terminal": True},
        identity=identity,
    )
    plan_dir = project_dir / ".megaplan" / "plans" / "plan"
    plan_dir.mkdir(parents=True)
    (plan_dir / "state.json").write_text("{}", encoding="utf-8")
    PlanRepository.from_plan_dir(plan_dir).write_task_execution_artifact(
        identity,
        {
            "task_id": "T11",
            "task_key": identity.task_key,
            "status": "blocked",
            "worktree_preserved": True,
            "metadata": {
                "identity": identity.registry_identity(),
                "trailers": identity.trailer_fields(),
                "tier": {
                    "task_complexity": 4,
                    "resolved_agent": "codex",
                    "resolved_mode": "persistent",
                    "resolved_model": "gpt-5.4",
                },
                "patch": {
                    "run_id": "run-11",
                    "available": True,
                    "manifest_path": "/tmp/manifest.json",
                    "patch_path": "/tmp/task.patch",
                    "secret_scan": {"status": "passed", "mode": "local_only"},
                },
                "secret_scan": {
                    "mode": "local_only",
                    "source": "execution.secret_scan_mode",
                },
                "progress": {"event": "task_complete", "status": "blocked"},
                "registry": {
                    "run_id": "run-11",
                    "available": True,
                    "entry_count": 1,
                    "entries": [
                        {
                            "entry_type": "integration_complete",
                            "payload": {"commit_sha": "abc123", "terminal": True},
                        }
                    ],
                },
                "integration": {
                    "available": True,
                    "entries": [
                        {
                            "entry_type": "integration_complete",
                            "payload": {"commit_sha": "abc123", "terminal": True},
                        }
                    ],
                },
                "receipt": {"agent": "codex", "mode": "persistent", "model": "gpt-5.4"},
            },
        },
    )

    report = build_custody_report(project_dir, "run-11")

    task = report["tasks"][0]
    assert task["task_id"] == "T11"
    assert task["task_key"] == identity.task_key
    assert task["task_artifact_path"].endswith(f"tasks/{identity.task_key}/execution.json")
    assert task["worktree_preserved"] is True
    assert task["secret_scan_mode"] == "local_only"
    assert task["secret_scan_status"] == "passed"
    assert task["selected_tier"]["selected_model"] == "gpt-5.4"
    assert task["latest_task_progress"]["event"] == "task_complete"
    assert task["integration_state"] == "integration_complete"
    assert task["commit_identity_state"]["trailers_present"] is True


def test_custody_report_surfaces_invalid_registry_chain_and_tail_truncation(
    tmp_path: Path,
) -> None:
    project_dir = tmp_path / "repo"
    first = append_registry_entry(project_dir, "run-11", "one", {"n": 1}, task_id="T11")
    append_registry_entry(project_dir, "run-11", "two", {"n": 2}, task_id="T11")
    paths = custody_paths(project_dir)
    paths.registry_jsonl("run-11").write_text(json.dumps(first, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")

    report = build_custody_report(project_dir, "run-11")

    assert {"registry_anchored_tail_truncation", "anchored_tail_truncation"}.issubset(_issue_codes(report))
    assert report["registry"]["ok"] is False


def test_custody_report_cli_json_is_read_only_and_write_is_explicit(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    project_dir = tmp_path / "repo"
    append_registry_entry(project_dir, "run-11", "one", {"n": 1}, task_id="T11")

    exit_code = megaplan.cli.main([
        "custody-report",
        "--run-id",
        "run-11",
        "--json",
        "--project-dir",
        str(project_dir),
    ])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["success"] is True
    assert payload["report"]["read_only"] is True
    assert payload["report"]["persisted_path"] is None
    assert not custody_paths(project_dir).custody_report("run-11").exists()

    exit_code = megaplan.cli.main([
        "custody-report",
        "--run-id",
        "run-11",
        "--json",
        "--write",
        "--project-dir",
        str(project_dir),
    ])
    payload = json.loads(capsys.readouterr().out)

    report_path = Path(payload["report"]["persisted_path"])
    assert exit_code == 0
    assert payload["report"]["read_only"] is False
    assert report_path == custody_paths(project_dir).custody_report("run-11")
    assert report_path.exists()
    assert report_path.parent == custody_paths(project_dir).reports_dir / "run-11"


def test_custody_report_cli_requires_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    project_dir = tmp_path / "repo"
    project_dir.mkdir()
    exit_code = megaplan.cli.main([
        "custody-report",
        "--run-id",
        "run-11",
        "--project-dir",
        str(project_dir),
    ])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code != 0
    assert payload["error"] == "invalid_args"
