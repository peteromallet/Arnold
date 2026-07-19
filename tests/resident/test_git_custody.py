from __future__ import annotations

import json
from pathlib import Path
import subprocess

import pytest

from arnold_pipelines.megaplan.resident import subagent as subagent_module
from arnold_pipelines.megaplan.resident.git_custody import (
    GIT_CUSTODY_EVIDENCE_SCHEMA,
    GitCustodyError,
    resolve_launch_git_custody,
    validate_git_custody_evidence,
)


def _git(path: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(path), *args],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.stdout.strip()


def _commit(path: Path, message: str, filename: str) -> str:
    (path / filename).write_text(message + "\n", encoding="utf-8")
    _git(path, "add", filename)
    _git(path, "commit", "-m", message)
    return _git(path, "rev-parse", "HEAD")


def _repo(path: Path) -> str:
    subprocess.run(
        ["git", "init", "-b", "main", str(path)],
        check=True,
        stdout=subprocess.PIPE,
    )
    _git(path, "config", "user.name", "Test User")
    _git(path, "config", "user.email", "test@example.com")
    return _commit(path, "base", "base.txt")


def test_dirty_divergent_project_does_not_hide_unambiguous_non_main_runtime_target(
    tmp_path: Path,
) -> None:
    remote = tmp_path / "remote.git"
    subprocess.run(
        ["git", "init", "--bare", str(remote)],
        check=True,
        stdout=subprocess.PIPE,
    )
    _git(remote, "symbolic-ref", "HEAD", "refs/heads/main")
    project = tmp_path / "project"
    subprocess.run(
        ["git", "clone", str(remote), str(project)],
        check=True,
        stdout=subprocess.PIPE,
    )
    _git(project, "config", "user.name", "Test User")
    _git(project, "config", "user.email", "test@example.com")
    base = _commit(project, "base", "base.txt")
    _git(project, "push", "-u", "origin", "main")
    runtime = tmp_path / "runtime"
    _git(project, "worktree", "add", "-b", "resident-runtime", str(runtime), base)

    _commit(project, "local ahead", "local.txt")
    other = tmp_path / "other"
    subprocess.run(
        ["git", "clone", str(remote), str(other)],
        check=True,
        stdout=subprocess.PIPE,
    )
    _git(other, "config", "user.name", "Other User")
    _git(other, "config", "user.email", "other@example.com")
    _commit(other, "remote ahead", "remote.txt")
    _git(other, "push", "origin", "main")
    _git(project, "fetch", "origin")
    (project / "dirty.txt").write_text("concurrent work\n", encoding="utf-8")

    custody = resolve_launch_git_custody(
        project_root=project,
        runtime_root=runtime,
        evidence_path=tmp_path / "receipt.json",
    )

    project_snapshot = custody["launch_checkouts"]["project"]
    assert project_snapshot["dirty"] is True
    assert (project_snapshot["upstream_ahead"], project_snapshot["upstream_behind"]) == (1, 1)
    assert custody["target_resolution"] == {
        "status": "resolved",
        "reason": "pinned_runtime_attached_branch_in_project_repository",
        "target_path": str(runtime.resolve()),
        "target_ref": "refs/heads/resident-runtime",
        "base_revision": base,
    }


def test_resolved_target_rejects_false_ambiguity_gate(tmp_path: Path) -> None:
    project = tmp_path / "project"
    base = _repo(project)
    runtime = tmp_path / "runtime"
    _git(project, "worktree", "add", "-b", "resident-runtime", str(runtime), base)
    evidence_path = tmp_path / "receipt.json"
    custody = resolve_launch_git_custody(
        project_root=project,
        runtime_root=runtime,
        evidence_path=evidence_path,
    )
    evidence_path.write_text(
        json.dumps(
            {
                "schema_version": GIT_CUSTODY_EVIDENCE_SCHEMA,
                "integration": {
                    "status": "blocked_ambiguity",
                    "gate": "dirty main needs a target decision",
                },
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(GitCustodyError, match="launch target was resolved"):
        validate_git_custody_evidence(custody)


def test_genuinely_detached_candidates_fail_closed_with_exact_gate(tmp_path: Path) -> None:
    project = tmp_path / "project"
    base = _repo(project)
    _git(project, "checkout", "--detach", base)
    runtime = tmp_path / "runtime"
    _git(project, "worktree", "add", "--detach", str(runtime), base)
    evidence_path = tmp_path / "receipt.json"
    custody = resolve_launch_git_custody(
        project_root=project,
        runtime_root=runtime,
        evidence_path=evidence_path,
    )
    resolution = custody["target_resolution"]
    assert resolution["status"] == "ambiguous"
    assert resolution["gate"] == (
        f"select one writable local target ref and relaunch; candidates: "
        f"project=detached@{base}, pinned_runtime=detached@{base}"
    )
    evidence_path.write_text(
        json.dumps(
            {
                "schema_version": GIT_CUSTODY_EVIDENCE_SCHEMA,
                "integration": {
                    "status": "blocked_ambiguity",
                    "gate": resolution["gate"],
                },
            }
        ),
        encoding="utf-8",
    )

    assert (
        validate_git_custody_evidence(custody)["status"]
        == "verified_ambiguity_gate"
    )
    assert _git(project, "rev-parse", "HEAD") == base
    assert _git(runtime, "rev-parse", "HEAD") == base


def test_integrated_receipt_proves_clean_worktree_diff_tests_and_ancestry(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    base = _repo(project)
    runtime = tmp_path / "runtime"
    _git(project, "worktree", "add", "-b", "resident-runtime", str(runtime), base)
    evidence_path = tmp_path / "receipt.json"
    custody = resolve_launch_git_custody(
        project_root=project,
        runtime_root=runtime,
        evidence_path=evidence_path,
    )
    feature = tmp_path / "feature"
    _git(project, "worktree", "add", "-b", "feature/custody", str(feature), base)
    original_commit = _commit(feature, "implement", "feature.txt")
    _commit(runtime, "concurrent target advance", "runtime.txt")
    before = _git(runtime, "rev-parse", "refs/heads/resident-runtime")
    _git(feature, "rebase", "refs/heads/resident-runtime")
    commit = _git(feature, "rev-parse", "HEAD")
    assert commit != original_commit
    _git(runtime, "merge", "--ff-only", "refs/heads/feature/custody")
    after = _git(runtime, "rev-parse", "refs/heads/resident-runtime")
    evidence_path.write_text(
        json.dumps(
            {
                "schema_version": GIT_CUSTODY_EVIDENCE_SCHEMA,
                "launch_target": {
                    "target_ref": "refs/heads/resident-runtime",
                    "base_revision": base,
                },
                "implementation": {
                    "worktree_path": str(feature),
                    "branch_ref": "refs/heads/feature/custody",
                    "base_revision": base,
                    "commit_revision": commit,
                },
                "verification": {
                    "diff_reviewed": True,
                    "git_diff_check": "passed",
                    "tests": [{"command": "pytest -q focused", "status": "passed"}],
                },
                "preservation": {"launch_checkout_untouched": True},
                "revalidation": {
                    "target_ref": "refs/heads/resident-runtime",
                    "observed_revision": before,
                },
                "integration": {
                    "status": "integrated",
                    "target_ref": "refs/heads/resident-runtime",
                    "before_revision": before,
                    "after_revision": after,
                },
            }
        ),
        encoding="utf-8",
    )

    verified = validate_git_custody_evidence(custody)
    assert verified["status"] == "verified_integrated"
    assert verified["commit_revision"] == commit
    assert verified["target_revision"] == commit
    assert _git(feature, "status", "--porcelain") == ""
    assert (
        _git(
            runtime,
            "merge-base",
            "--is-ancestor",
            commit,
            "refs/heads/resident-runtime",
        )
        == ""
    )


def test_zero_exit_worker_fails_closed_without_git_custody_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    _repo(project)
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    prompt_path = run_dir / "prompt.md"
    result_path = run_dir / "result.md"
    manifest_path = run_dir / "manifest.json"
    prompt_path.write_text("implement it", encoding="utf-8")
    custody = resolve_launch_git_custody(
        project_root=project,
        runtime_root=project,
        evidence_path=run_dir / "git-custody-evidence.json",
    )
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": "arnold-managed-agent-run-v2",
                "run_kind": "resident_delegated_agent",
                "custodian": "arnold.megaplan.managed_agent",
                "status": "running",
                "pid": 111,
                "prompt_path": str(prompt_path),
                "result_path": str(result_path),
                "project_dir": str(project),
                "model": "gpt-test",
                "reasoning_effort": "high",
                "work_intent": "execution",
                "git_custody": custody,
            }
        ),
        encoding="utf-8",
    )

    class _Worker:
        pid = 222

        def wait(self, timeout=None):
            return 0

        def poll(self):
            return 0

    monkeypatch.setattr(
        subagent_module.subprocess,
        "Popen",
        lambda *args, **kwargs: _Worker(),
    )

    assert subagent_module._run_codex_manifest(manifest_path) == 2
    terminal = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert terminal["status"] == "failed"
    assert terminal["terminal_outcome"] == "failed"
    assert terminal["error"] == "git custody verification failed"
    assert "missing or invalid git custody evidence" in terminal["git_custody_error"]
