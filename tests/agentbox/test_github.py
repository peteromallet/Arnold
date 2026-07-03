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


def test_create_issue_returns_stable_evidence_ref(tmp_path: Path) -> None:
    with patch.object(github, "validate_github_auth", return_value={"ok": True, "fix_command": None, "error": None}):
        with patch.object(github.subprocess, "run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "https://github.com/acme/repo/issues/42\n"
            mock_run.return_value.stderr = ""

            result = github.create_issue(
                tmp_path,
                "acme/repo",
                "Persistent incident",
                "body",
                labels=["incident", "persistent-problem"],
            )

    assert result == {
        "ok": True,
        "evidence_ref": {
            "kind": "github.issue",
            "url": "https://github.com/acme/repo/issues/42",
            "number": 42,
            "repo": "acme/repo",
            "action": "created",
        },
    }
    assert mock_run.call_args.args[0] == (
        "gh",
        "issue",
        "create",
        "--repo",
        "acme/repo",
        "--title",
        "Persistent incident",
        "--body",
        "body",
        "--label",
        "incident",
        "--label",
        "persistent-problem",
    )


def test_comment_issue_returns_stable_evidence_ref(tmp_path: Path) -> None:
    with patch.object(github, "validate_github_auth", return_value={"ok": True, "fix_command": None, "error": None}):
        with patch.object(github.subprocess, "run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "https://github.com/acme/repo/issues/42#issuecomment-1\n"
            mock_run.return_value.stderr = ""

            result = github.comment_issue(tmp_path, "acme/repo", 42, "still open")

    assert result == {
        "ok": True,
        "evidence_ref": {
            "kind": "github.issue",
            "url": "https://github.com/acme/repo/issues/42#issuecomment-1",
            "number": 42,
            "repo": "acme/repo",
            "action": "commented",
        },
    }
    assert mock_run.call_args.args[0] == (
        "gh",
        "issue",
        "comment",
        "42",
        "--repo",
        "acme/repo",
        "--body",
        "still open",
    )


def test_list_issues_by_label_returns_stable_evidence_refs(tmp_path: Path) -> None:
    with patch.object(github, "validate_github_auth", return_value={"ok": True, "fix_command": None, "error": None}):
        with patch.object(github.subprocess, "run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = (
                '[{"number": 7, "url": "https://github.com/acme/repo/issues/7", "title": "A", "state": "OPEN"}]'
            )
            mock_run.return_value.stderr = ""

            result = github.list_issues_by_label(tmp_path, "acme/repo", "incident")

    assert result == {
        "ok": True,
        "issues": [
            {
                "kind": "github.issue",
                "url": "https://github.com/acme/repo/issues/7",
                "number": 7,
                "repo": "acme/repo",
                "action": "listed",
            }
        ],
    }
    assert mock_run.call_args.args[0] == (
        "gh",
        "issue",
        "list",
        "--repo",
        "acme/repo",
        "--label",
        "incident",
        "--state",
        "open",
        "--json",
        "number,url,title,state",
    )


def test_search_issues_returns_stable_evidence_refs(tmp_path: Path) -> None:
    with patch.object(github, "validate_github_auth", return_value={"ok": True, "fix_command": None, "error": None}):
        with patch.object(github.subprocess, "run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = (
                '[{"number": 9, "url": "https://github.com/acme/repo/issues/9", "title": "B", "state": "OPEN"}]'
            )
            mock_run.return_value.stderr = ""

            result = github.search_issues(tmp_path, "acme/repo", "problem-123")

    assert result == {
        "ok": True,
        "issues": [
            {
                "kind": "github.issue",
                "url": "https://github.com/acme/repo/issues/9",
                "number": 9,
                "repo": "acme/repo",
                "action": "searched",
            }
        ],
    }
    assert mock_run.call_args.args[0] == (
        "gh",
        "issue",
        "list",
        "--repo",
        "acme/repo",
        "--search",
        "problem-123",
        "--state",
        "all",
        "--json",
        "number,url,title,state",
    )


def test_issue_wrappers_preserve_auth_failure_style(tmp_path: Path) -> None:
    auth_failure = {"ok": False, "fix_command": "gh auth login", "error": "not logged in"}
    with patch.object(github, "validate_github_auth", return_value=auth_failure):
        assert github.create_issue(tmp_path, "acme/repo", "t", "b") == {
            "ok": False,
            "fix_command": "gh auth login",
            "error": "not logged in",
        }
        assert github.comment_issue(tmp_path, "acme/repo", 1, "b") == {
            "ok": False,
            "fix_command": "gh auth login",
            "error": "not logged in",
        }
        assert github.list_issues_by_label(tmp_path, "acme/repo", "incident") == {
            "ok": False,
            "fix_command": "gh auth login",
            "error": "not logged in",
        }
        assert github.search_issues(tmp_path, "acme/repo", "problem") == {
            "ok": False,
            "fix_command": "gh auth login",
            "error": "not logged in",
        }
