from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from agentbox import github


def test_validate_github_auth_failure_returns_fix_command(tmp_path: Path) -> None:
    with patch.object(github, "gh_installed", return_value=True):
        with patch.object(github.subprocess, "run") as mock_run:
            mock_run.return_value.returncode = 1
            mock_run.return_value.stdout = ""
            mock_run.return_value.stderr = "not logged in"

            result = github.validate_github_auth(tmp_path)

    assert result["ok"] is False
    assert result["fix_command"] == "gh auth login"
    assert "not logged in" in result["error"]


def test_validate_github_auth_missing_gh_returns_fix_command(tmp_path: Path) -> None:
    with patch.object(github, "gh_installed", return_value=False):
        result = github.validate_github_auth(tmp_path)

    assert result["ok"] is False
    assert result["fix_command"] == "gh auth login"
    assert "not installed" in result["error"]


def test_pr_number_from_url_parses_number() -> None:
    assert github._pr_number_from_url("https://github.com/org/repo/pull/42") == 42
    assert github._pr_number_from_url("") is None
    assert github._pr_number_from_url("https://github.com/org/repo/pull/") is None


def test_rollup_status_maps_check_states() -> None:
    assert github._rollup_status([{"state": "SUCCESS"}]) == "passed"
    assert github._rollup_status([{"state": "FAILURE"}]) == "failed"
    assert github._rollup_status([{"state": "PENDING"}]) == "pending"
    assert github._rollup_status([]) == "unknown"
