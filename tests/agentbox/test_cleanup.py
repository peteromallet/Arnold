from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from arnold.runtime.durable_ops import OperationState

from agentbox.cleanup import CleanupFinding, CleanupSurveyReport, apply_cleanup, survey_cleanup
from agentbox.completion import format_completion_dm
from agentbox.config import AgentBoxConfig
from agentbox.operations import (
    create_agentbox_operation,
    update_agentbox_operation,
)
from agentbox.repos import register_repo
from agentbox.worktrees import allocate_worktree, branch_name, worktree_path


def test_survey_cleanup_classifies_dirty_worktree_as_park(tmp_path: Path) -> None:
    config, repo = _registered_repo(tmp_path)
    create_agentbox_operation(config, "op-1", command="echo hi", repo_names=["demo"])
    allocate_worktree(config, "op-1", "demo")
    target = worktree_path(config, "op-1", "demo")
    (target / "new.txt").write_text("dirty\n", encoding="utf-8")

    report = survey_cleanup(config)
    finding = _finding_for_repo(report, "op-1", "demo")

    assert finding.recommendation == "park"
    assert finding.evidence["dirty"] is True


def test_survey_cleanup_classifies_merged_branch_as_delete(tmp_path: Path) -> None:
    config, repo = _registered_repo(tmp_path)
    create_agentbox_operation(config, "op-1", command="echo hi", repo_names=["demo"])
    allocate_worktree(config, "op-1", "demo")
    target = worktree_path(config, "op-1", "demo")
    branch = branch_name("op-1", "demo")

    _git(target, "config", "user.email", "agentbox@example.test")
    _git(target, "config", "user.name", "AgentBox Tests")
    (target / "feature.txt").write_text("feature\n", encoding="utf-8")
    _git(target, "add", "feature.txt")
    _git(target, "commit", "-m", "feature commit")

    _git(repo, "checkout", "main")
    _git(repo, "merge", "--no-ff", branch, "-m", "merge feature")

    update_agentbox_operation(
        config,
        "op-1",
        state=OperationState.RUNNING,
    )
    update_agentbox_operation(
        config,
        "op-1",
        state=OperationState.SUCCEEDED,
    )

    report = survey_cleanup(config)
    finding = _finding_for_repo(report, "op-1", "demo")

    assert finding.recommendation == "delete"
    assert finding.evidence["merged"] is True


def test_survey_cleanup_classifies_parked_branch(tmp_path: Path) -> None:
    config, repo = _registered_repo(tmp_path)
    create_agentbox_operation(config, "op-1", command="echo hi", repo_names=["demo"])
    allocate_worktree(config, "op-1", "demo")
    target = worktree_path(config, "op-1", "demo")
    (target / "untracked.txt").write_text("untracked\n", encoding="utf-8")

    report = survey_cleanup(config)
    finding = _finding_for_repo(report, "op-1", "demo")

    assert finding.recommendation == "park"


def test_survey_cleanup_reports_orphan_run_dir_as_park(tmp_path: Path) -> None:
    config = AgentBoxConfig(workspace_root=tmp_path / "workspace")
    orphan = config.runs_root / "orphan-op"
    orphan.mkdir(parents=True)

    report = survey_cleanup(config)
    orphan_findings = [f for f in report.findings if f.operation_id == "orphan-op"]

    assert len(orphan_findings) == 1
    assert orphan_findings[0].recommendation == "park"
    assert orphan_findings[0].evidence.get("orphan_run_dir") is True


def test_github_auth_failure_returns_fix_command(monkeypatch) -> None:
    from agentbox import github

    monkeypatch.setattr(github, "gh_installed", lambda: True)

    class _FakeResult:
        returncode = 1
        stdout = ""
        stderr = "not logged in"

    monkeypatch.setattr(github.subprocess, "run", lambda *a, **k: _FakeResult())

    result = github.validate_github_auth(Path("."))

    assert result["ok"] is False
    assert result["fix_command"] == "gh auth login"
    assert result["error"] is not None


def test_format_completion_dm_includes_summary_validation_branch_and_next_action() -> None:
    operation_status = {
        "operation_id": "op-1",
        "operation_state": "succeeded",
        "branch": "agentbox/op-1/demo",
        "pr_number": 42,
        "pr_url": "https://github.com/example/repo/pull/42",
        "ci_status": "passed",
    }
    text = format_completion_dm(
        operation_status,
        validation={"status": "passed"},
        branch_status={
            "branch": "agentbox/op-1/demo",
            "pr_number": 42,
            "pr_url": "https://github.com/example/repo/pull/42",
            "ci_status": "passed",
        },
        next_action="Review the PR and run cleanup survey.",
    )

    assert "Operation op-1 completed with state succeeded" in text
    assert "Validation: passed" in text
    assert "branch=agentbox/op-1/demo" in text
    assert "pr_number=42" in text
    assert "pr_url=https://github.com/example/repo/pull/42" in text
    assert "ci_status=passed" in text
    assert "Next action: Review the PR and run cleanup survey." in text


def test_cleanup_finding_to_dict_is_stable() -> None:
    finding = CleanupFinding(
        finding_id="op-1:demo",
        operation_id="op-1",
        repo_name="demo",
        branch="agentbox/op-1/demo",
        worktree_path="/workspace/runs/op-1/worktrees/demo",
        recommendation="park",
        reason="dirty",
        evidence={"dirty": True},
        requires_confirmation=False,
    )
    data = finding.to_dict()

    assert data["finding_id"] == "op-1:demo"
    assert data["recommendation"] == "park"
    assert data["evidence"]["dirty"] is True


def test_cleanup_survey_report_to_dict_is_stable() -> None:
    finding = CleanupFinding(
        finding_id="op-1:demo",
        operation_id="op-1",
        repo_name="demo",
        branch="agentbox/op-1/demo",
        worktree_path="/workspace/runs/op-1/worktrees/demo",
        recommendation="park",
        reason="dirty",
        evidence={"dirty": True},
        requires_confirmation=False,
    )
    report = CleanupSurveyReport(findings=(finding,))

    data = report.to_dict()

    assert len(data["findings"]) == 1
    assert data["findings"][0]["finding_id"] == "op-1:demo"


def test_apply_cleanup_park_records_cleanup_state(tmp_path: Path) -> None:
    config, repo = _registered_repo(tmp_path)
    create_agentbox_operation(config, "op-1", command="echo hi", repo_names=["demo"])
    allocate_worktree(config, "op-1", "demo")

    report = survey_cleanup(config)
    finding = _finding_for_repo(report, "op-1", "demo")
    result = apply_cleanup(config, finding.finding_id, "park")

    assert result["ok"] is True
    assert result["action"] == "park"


def _registered_repo(tmp_path: Path) -> tuple[AgentBoxConfig, Path]:
    config = AgentBoxConfig(workspace_root=tmp_path / "workspace")
    repo = _init_repo(config.repos_root / "demo")
    register_repo(config, "demo", path=repo)
    return config, repo


def _init_repo(path: Path) -> Path:
    path.mkdir(parents=True)
    _git(path, "init", "-b", "main")
    _git(path, "config", "user.email", "agentbox@example.test")
    _git(path, "config", "user.name", "AgentBox Tests")
    (path / "README.md").write_text("# test\n", encoding="utf-8")
    _git(path, "add", "README.md")
    _git(path, "commit", "-m", "initial")
    return path


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ("git", *args),
        cwd=cwd,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout.strip()


def _finding_for_repo(report: CleanupSurveyReport, operation_id: str, repo_name: str) -> CleanupFinding:
    finding = next(
        (f for f in report.findings if f.operation_id == operation_id and f.repo_name == repo_name),
        None,
    )
    assert finding is not None, f"finding {operation_id}/{repo_name} not in report"
    return finding


# ── T-0027: delete behind the reference census ───────────────────────────────


def _census_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Point every reference-census store at (absent) sandbox dirs so the
    census is hermetic and injectable per test."""
    for var, sub in (
        ("ARNOLD_BASE_DIR", "base"),
        ("ARNOLD_RUNTIME_MANIFEST_DIR", "manifests"),
        ("ARNOLD_REFERENCE_CHAIN_STORE", "ref-chains"),
        ("ARNOLD_REFERENCE_MARKER_STORE", "ref-markers"),
        ("ARNOLD_REFERENCE_SCHEDULE_STORES", "ref-schedules"),
        ("ARNOLD_REFERENCE_REPAIR_QUEUE", "ref-repair-queue"),
        ("ARNOLD_REFERENCE_LEASE_STORE", "ref-leases"),
    ):
        monkeypatch.setenv(var, str(tmp_path / sub))


def _merged_delete_finding(tmp_path: Path) -> tuple[AgentBoxConfig, CleanupFinding, Path]:
    config, repo = _registered_repo(tmp_path)
    create_agentbox_operation(config, "op-1", command="echo hi", repo_names=["demo"])
    allocate_worktree(config, "op-1", "demo")
    target = worktree_path(config, "op-1", "demo")
    branch = branch_name("op-1", "demo")

    _git(target, "config", "user.email", "agentbox@example.test")
    _git(target, "config", "user.name", "AgentBox Tests")
    (target / "feature.txt").write_text("feature\n", encoding="utf-8")
    _git(target, "add", "feature.txt")
    _git(target, "commit", "-m", "feature commit")

    _git(repo, "checkout", "main")
    _git(repo, "merge", "--no-ff", branch, "-m", "merge feature")

    update_agentbox_operation(
        config,
        "op-1",
        state=OperationState.RUNNING,
    )
    update_agentbox_operation(
        config,
        "op-1",
        state=OperationState.SUCCEEDED,
    )

    report = survey_cleanup(config)
    finding = _finding_for_repo(report, "op-1", "demo")
    assert finding.recommendation == "delete"
    return config, finding, target


def test_apply_delete_refuses_when_worktree_referenced_by_lease(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """T-0027: ``_apply_delete`` (git branch -D + worktree remove) is behind
    the reference census.  A custody lease referencing the exact worktree
    root refuses the delete with zero branch -D / worktree remove calls."""
    config, finding, target = _merged_delete_finding(tmp_path)
    _census_env(monkeypatch, tmp_path)
    lease_store = tmp_path / "ref-leases"
    lease_store.mkdir(parents=True)
    (lease_store / "lease-1.history.jsonl").write_text(
        json.dumps({"cwd": str(target)}) + "\n", encoding="utf-8"
    )

    from agentbox import cleanup as cleanup_module

    calls: list[tuple] = []
    real_git = cleanup_module.git

    def recording_git(repo, *args, **kwargs):
        calls.append(args)
        return real_git(repo, *args, **kwargs)

    monkeypatch.setattr(cleanup_module, "git", recording_git)

    result = apply_cleanup(config, finding.finding_id, "delete")

    assert result["ok"] is False
    assert result["census_verdict"] == "REFERENCED"
    assert "refused" in result["error"]
    assert target.exists()
    assert not any(call[:2] == ("branch", "-D") for call in calls), calls
    assert not any(call[:2] == ("worktree", "remove") for call in calls), calls


def test_apply_delete_refuses_when_census_store_corrupt(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """T-0027 fail-closed: an unreadable/corrupt reference store makes the
    census UNKNOWN and the delete refuses — delete-on-unknown never happens."""
    config, finding, target = _merged_delete_finding(tmp_path)
    _census_env(monkeypatch, tmp_path)
    # A file squatting on the configured chain store path => UNKNOWN.
    chain_store = tmp_path / "ref-chains"
    chain_store.write_text("not a directory\n", encoding="utf-8")

    result = apply_cleanup(config, finding.finding_id, "delete")

    assert result["ok"] is False
    assert result["census_verdict"] == "UNKNOWN"
    assert "refused" in result["error"]
    assert target.exists()


def test_apply_delete_proceeds_on_clear_census(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """T-0027: with a CLEAR census verdict the delete proceeds and removes
    the registered worktree (route authority: terminal merged operation)."""
    config, finding, target = _merged_delete_finding(tmp_path)
    _census_env(monkeypatch, tmp_path)  # all stores absent => CLEAR

    from agentbox import cleanup as cleanup_module

    calls: list[tuple] = []
    real_git = cleanup_module.git

    def recording_git(repo, *args, **kwargs):
        calls.append(args)
        return real_git(repo, *args, **kwargs)

    monkeypatch.setattr(cleanup_module, "git", recording_git)

    result = apply_cleanup(config, finding.finding_id, "delete")

    assert result["ok"] is True
    assert not target.exists()
    assert any(call[:2] == ("worktree", "remove") for call in calls), calls


def test_apply_delete_refuses_when_active_manifest_references_worktree(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """G6 round-4: the cleanup delete census must NOT exclude the ACTIVE
    manifest (ARNOLD_RUNTIME_MANIFEST) from its scan.  An active manifest
    whose epic.runtime_root IS the worktree refuses the delete (REFERENCED,
    zero branch -D / worktree remove)."""
    config, finding, target = _merged_delete_finding(tmp_path)
    _census_env(monkeypatch, tmp_path)
    manifest_dir = tmp_path / "manifests"
    manifest_dir.mkdir(parents=True)
    active = manifest_dir / "epic-live.json"
    active.write_text(
        json.dumps({"epic": {"runtime_root": str(target)}}), encoding="utf-8"
    )
    monkeypatch.setenv("ARNOLD_RUNTIME_MANIFEST", str(active))

    from agentbox import cleanup as cleanup_module

    calls: list[tuple] = []
    real_git = cleanup_module.git

    def recording_git(repo, *args, **kwargs):
        calls.append(args)
        return real_git(repo, *args, **kwargs)

    monkeypatch.setattr(cleanup_module, "git", recording_git)

    result = apply_cleanup(config, finding.finding_id, "delete")

    assert result["ok"] is False
    assert result["census_verdict"] == "REFERENCED"
    assert "refused" in result["error"]
    assert target.exists()
    assert not any(call[:2] == ("branch", "-D") for call in calls), calls
    assert not any(call[:2] == ("worktree", "remove") for call in calls), calls


def test_apply_delete_refuses_when_active_manifest_corrupt(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """G6 round-4: a corrupt ACTIVE manifest makes the census UNKNOWN — it
    was previously excluded as ``current_manifest`` so the corruption
    collapsed to CLEAR and the delete ran (delete-on-unknown violated)."""
    config, finding, target = _merged_delete_finding(tmp_path)
    _census_env(monkeypatch, tmp_path)
    manifest_dir = tmp_path / "manifests"
    manifest_dir.mkdir(parents=True)
    active = manifest_dir / "epic-live.json"
    active.write_text("{not valid json\n", encoding="utf-8")
    monkeypatch.setenv("ARNOLD_RUNTIME_MANIFEST", str(active))

    from agentbox import cleanup as cleanup_module

    calls: list[tuple] = []
    real_git = cleanup_module.git

    def recording_git(repo, *args, **kwargs):
        calls.append(args)
        return real_git(repo, *args, **kwargs)

    monkeypatch.setattr(cleanup_module, "git", recording_git)

    result = apply_cleanup(config, finding.finding_id, "delete")

    assert result["ok"] is False
    assert result["census_verdict"] == "UNKNOWN"
    assert "refused" in result["error"]
    assert target.exists()
    assert not any(call[:2] == ("branch", "-D") for call in calls), calls
    assert not any(call[:2] == ("worktree", "remove") for call in calls), calls
