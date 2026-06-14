"""Regression tests for --no-push local milestone commits."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import yaml

from megaplan import chain as chain_module
from megaplan.auto import DriverOutcome
from megaplan.chain import load_chain_state, run_chain
from megaplan.chain.git_ops import CommitResult
from megaplan.types import STATE_FINALIZED


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )


def _write_spec(root: Path, *, idea: Path) -> Path:
    spec_path = root / "chain.yaml"
    spec_path.write_text(
        yaml.safe_dump(
            {
                "base_branch": "main",
                "milestones": [{"label": "m1", "idea": str(idea)}],
            }
        ),
        encoding="utf-8",
    )
    return spec_path


def _fake_outcome(plan: str, status: str) -> DriverOutcome:
    return DriverOutcome(
        status=status,
        plan=plan,
        final_state=status,
        iterations=1,
        reason="",
    )


def _init_repo_with_spec(root: Path) -> tuple[Path, str]:
    _git(root, "init")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Test User")
    _git(root, "checkout", "-b", "main")
    (root / ".gitignore").write_text(".megaplan/\n", encoding="utf-8")
    (root / "README.md").write_text("root\n", encoding="utf-8")
    idea = root / "ideas" / "m1.txt"
    idea.parent.mkdir()
    idea.write_text("build app file\n", encoding="utf-8")
    spec_path = _write_spec(root, idea=idea)
    _git(root, "add", ".gitignore", "README.md", "ideas/m1.txt", "chain.yaml")
    _git(root, "commit", "-m", "init")
    return spec_path, _git(root, "rev-parse", "HEAD").stdout.strip()


def test_no_push_start_mode_commits_completed_milestone_locally(tmp_path: Path) -> None:
    spec_path, initial_head = _init_repo_with_spec(tmp_path)

    def fake_drive(root, plan, spec, *, stop_at_finalized=False, on_phase_complete=None, writer):
        del spec, stop_at_finalized, on_phase_complete, writer
        (root / "app.txt").write_text("milestone output\n", encoding="utf-8")
        plan_dir = root / ".megaplan" / "plans" / plan
        plan_dir.mkdir(parents=True)
        (plan_dir / "execution.json").write_text(
            json.dumps({"files_changed": ["app.txt"]}),
            encoding="utf-8",
        )
        return _fake_outcome(plan, "done")

    with patch("megaplan.chain._refresh_base_branch", lambda *a, **k: None), \
         patch("megaplan.chain._init_plan", return_value="plan-m1"), \
         patch("megaplan.chain._drive_plan", side_effect=fake_drive), \
         patch("megaplan.chain._commit_phase", wraps=chain_module._commit_phase) as commit_phase:
        result = run_chain(spec_path, tmp_path, writer=lambda _m: None, no_push=True, mode="start")

    head = _git(tmp_path, "rev-parse", "HEAD").stdout.strip()
    saved = load_chain_state(spec_path)
    assert result["status"] == "done"
    assert head != initial_head
    assert saved.completed[0]["local_commit_sha"] == head
    assert saved.completed[0]["plan_branch"] == "main"
    commit_phase.assert_called_once()
    assert commit_phase.call_args.args[:3] == (tmp_path, "plan-m1", "done")


def test_no_push_plan_mode_does_not_commit_completed_milestone_locally(tmp_path: Path) -> None:
    spec_path, initial_head = _init_repo_with_spec(tmp_path)

    def fake_drive(root, plan, spec, *, stop_at_finalized=False, on_phase_complete=None, writer):
        del root, spec, on_phase_complete, writer
        assert plan == "plan-m1"
        assert stop_at_finalized is True
        return _fake_outcome(plan, STATE_FINALIZED)

    with patch("megaplan.chain._refresh_base_branch", lambda *a, **k: None), \
         patch("megaplan.chain._init_plan", return_value="plan-m1"), \
         patch("megaplan.chain._drive_plan", side_effect=fake_drive), \
         patch(
             "megaplan.chain.commit_plan_artifacts_to_base",
             return_value=CommitResult(
                 committed=True,
                 pushed=False,
                 commit_sha="artifact-sha",
                 base_branch="main",
             ),
         ), \
         patch("megaplan.chain._commit_phase", wraps=chain_module._commit_phase) as commit_phase:
        result = run_chain(spec_path, tmp_path, writer=lambda _m: None, no_push=True, mode="plan")

    saved = load_chain_state(spec_path)
    assert result["status"] == "done"
    assert _git(tmp_path, "rev-parse", "HEAD").stdout.strip() == initial_head
    assert saved.completed[0]["status"] == STATE_FINALIZED
    assert saved.completed[0]["artifact_commit_sha"] == "artifact-sha"
    assert "local_commit_sha" not in saved.completed[0]
    commit_phase.assert_not_called()
