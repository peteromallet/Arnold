"""Small GitHub CLI helper for AgentBox cleanup and completion."""

from __future__ import annotations

import json as _json
import shutil
import subprocess
from pathlib import Path
from typing import Any


class GitHubCliError(RuntimeError):
    """Raised when a GitHub CLI invocation fails."""


def gh_installed() -> bool:
    """Return true when the ``gh`` command is available."""

    return shutil.which("gh") is not None


def validate_github_auth(repo_path: Path | str) -> dict[str, Any]:
    """Check whether ``gh`` is authenticated for ``repo_path``.

    Returns ``{"ok": bool, "fix_command": str | None, "error": str | None}``.
    On any failure the fix command is ``"gh auth login"``.
    """

    if not gh_installed():
        return {
            "ok": False,
            "fix_command": "gh auth login",
            "error": "gh is not installed",
        }
    result = subprocess.run(
        ("gh", "auth", "status"),
        cwd=Path(repo_path),
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode == 0:
        return {"ok": True, "fix_command": None, "error": None}
    error = (result.stderr or result.stdout or f"gh auth status exited {result.returncode}").strip()
    return {"ok": False, "fix_command": "gh auth login", "error": error}


def pr_for_branch(repo_path: Path | str, branch: str) -> dict[str, Any]:
    """Return PR facts for ``branch`` using ``gh pr list``.

    If ``gh`` is missing or auth fails, all PR fields are ``None`` and the
    result includes ``auth_ok``/``fix_command``.
    """

    auth = validate_github_auth(repo_path)
    if not auth["ok"]:
        return {
            "number": None,
            "url": None,
            "state": None,
            "title": None,
            "auth_ok": False,
            "fix_command": auth["fix_command"],
        }
    result = subprocess.run(
        (
            "gh",
            "pr",
            "list",
            "--head",
            branch,
            "--state",
            "all",
            "--json",
            "number,url,state,title",
        ),
        cwd=Path(repo_path),
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        return {
            "number": None,
            "url": None,
            "state": None,
            "title": None,
            "auth_ok": False,
            "fix_command": "gh auth login",
        }
    try:
        rows = _json.loads(result.stdout or "[]")
    except _json.JSONDecodeError:
        rows = []
    if rows:
        row = rows[0]
        return {
            "number": _int_or_none(row.get("number")),
            "url": row.get("url"),
            "state": row.get("state"),
            "title": row.get("title"),
            "auth_ok": True,
            "fix_command": None,
        }
    return {
        "number": None,
        "url": None,
        "state": None,
        "title": None,
        "auth_ok": True,
        "fix_command": None,
    }


def create_draft_pr(
    repo_path: Path | str,
    branch: str,
    base: str,
    title: str,
    body: str,
) -> dict[str, Any]:
    """Create a draft PR for ``branch`` against ``base``.

    Validates auth first. On auth failure returns
    ``{"ok": False, "fix_command": "gh auth login"}``. On success returns
    ``{"ok": True, "number": int, "url": str}``.
    """

    auth = validate_github_auth(repo_path)
    if not auth["ok"]:
        return {"ok": False, "fix_command": auth["fix_command"], "error": auth["error"]}
    result = subprocess.run(
        (
            "gh",
            "pr",
            "create",
            "--draft",
            "--base",
            base,
            "--head",
            branch,
            "--title",
            title,
            "--body",
            body,
        ),
        cwd=Path(repo_path),
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        return {
            "ok": False,
            "fix_command": "gh auth login",
            "error": (result.stderr or result.stdout or "gh pr create failed").strip(),
        }
    url = result.stdout.strip().splitlines()[0].strip()
    number = _pr_number_from_url(url)
    return {"ok": True, "number": number, "url": url}


def create_issue(
    repo_path: Path | str,
    repo: str,
    title: str,
    body: str,
    *,
    labels: list[str] | None = None,
) -> dict[str, Any]:
    """Create a GitHub issue and return a stable evidence ref."""

    auth = validate_github_auth(repo_path)
    if not auth["ok"]:
        return {"ok": False, "fix_command": auth["fix_command"], "error": auth["error"]}
    command = [
        "gh",
        "issue",
        "create",
        "--repo",
        repo,
        "--title",
        title,
        "--body",
        body,
    ]
    for label in labels or []:
        command.extend(["--label", label])
    result = subprocess.run(
        tuple(command),
        cwd=Path(repo_path),
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        return {
            "ok": False,
            "fix_command": "gh auth login",
            "error": (result.stderr or result.stdout or "gh issue create failed").strip(),
        }
    url = result.stdout.strip().splitlines()[0].strip()
    return {"ok": True, "evidence_ref": _issue_evidence_ref(repo=repo, url=url, action="created")}


def comment_issue(
    repo_path: Path | str,
    repo: str,
    issue_number: int,
    body: str,
) -> dict[str, Any]:
    """Comment on an existing GitHub issue and return a stable evidence ref."""

    auth = validate_github_auth(repo_path)
    if not auth["ok"]:
        return {"ok": False, "fix_command": auth["fix_command"], "error": auth["error"]}
    result = subprocess.run(
        (
            "gh",
            "issue",
            "comment",
            str(issue_number),
            "--repo",
            repo,
            "--body",
            body,
        ),
        cwd=Path(repo_path),
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        return {
            "ok": False,
            "fix_command": "gh auth login",
            "error": (result.stderr or result.stdout or "gh issue comment failed").strip(),
        }
    url = result.stdout.strip().splitlines()[0].strip()
    return {
        "ok": True,
        "evidence_ref": _issue_evidence_ref(
            repo=repo,
            url=url,
            action="commented",
            number=issue_number,
        ),
    }


def list_issues_by_label(
    repo_path: Path | str,
    repo: str,
    label: str,
    *,
    state: str = "open",
) -> dict[str, Any]:
    """List issues for a label and return stable evidence refs."""

    auth = validate_github_auth(repo_path)
    if not auth["ok"]:
        return {"ok": False, "fix_command": auth["fix_command"], "error": auth["error"]}
    result = subprocess.run(
        (
            "gh",
            "issue",
            "list",
            "--repo",
            repo,
            "--label",
            label,
            "--state",
            state,
            "--json",
            "number,url,title,state",
        ),
        cwd=Path(repo_path),
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        return {
            "ok": False,
            "fix_command": "gh auth login",
            "error": (result.stderr or result.stdout or "gh issue list failed").strip(),
        }
    return {"ok": True, "issues": _parse_issue_rows(result.stdout, repo=repo, action="listed")}


def search_issues(
    repo_path: Path | str,
    repo: str,
    query: str,
    *,
    state: str = "all",
) -> dict[str, Any]:
    """Search issues with ``gh issue list --search`` and return stable evidence refs."""

    auth = validate_github_auth(repo_path)
    if not auth["ok"]:
        return {"ok": False, "fix_command": auth["fix_command"], "error": auth["error"]}
    result = subprocess.run(
        (
            "gh",
            "issue",
            "list",
            "--repo",
            repo,
            "--search",
            query,
            "--state",
            state,
            "--json",
            "number,url,title,state",
        ),
        cwd=Path(repo_path),
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        return {
            "ok": False,
            "fix_command": "gh auth login",
            "error": (result.stderr or result.stdout or "gh issue search failed").strip(),
        }
    return {"ok": True, "issues": _parse_issue_rows(result.stdout, repo=repo, action="searched")}


def ci_status_for_branch(repo_path: Path | str, branch: str) -> dict[str, Any]:
    """Return CI status for the PR associated with ``branch``.

    Uses ``gh pr view`` if a PR exists and auth is valid. Returns
    ``{"status": "passed"|"failed"|"pending"|"unknown", "fix_command": str|None}``.
    """

    pr = pr_for_branch(repo_path, branch)
    if not pr.get("auth_ok"):
        return {"status": "unknown", "fix_command": pr.get("fix_command")}
    if pr.get("number") is None:
        return {"status": "unknown", "fix_command": None}
    result = subprocess.run(
        ("gh", "pr", "view", branch, "--json", "statusCheckRollup"),
        cwd=Path(repo_path),
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        return {"status": "unknown", "fix_command": "gh auth login"}
    try:
        data = _json.loads(result.stdout or "{}")
    except _json.JSONDecodeError:
        return {"status": "unknown", "fix_command": None}
    return {"status": _rollup_status(data.get("statusCheckRollup") or []), "fix_command": None}


def _int_or_none(value: object) -> int | None:
    if isinstance(value, int):
        return value
    return None


def _pr_number_from_url(url: str) -> int | None:
    if not url:
        return None
    parts = url.rstrip("/").split("/")
    if parts and parts[-1].isdigit():
        return int(parts[-1])
    return None


def _issue_number_from_url(url: str) -> int | None:
    if not url:
        return None
    parts = url.rstrip("/").split("/")
    if parts and parts[-1].isdigit():
        return int(parts[-1])
    return None


def _issue_evidence_ref(
    *,
    repo: str,
    url: str,
    action: str,
    number: int | None = None,
) -> dict[str, Any]:
    issue_number = number if number is not None else _issue_number_from_url(url)
    return {
        "kind": "github.issue",
        "url": url,
        "number": issue_number,
        "repo": repo,
        "action": action,
    }


def _parse_issue_rows(stdout: str, *, repo: str, action: str) -> list[dict[str, Any]]:
    try:
        rows = _json.loads(stdout or "[]")
    except _json.JSONDecodeError:
        return []
    refs: list[dict[str, Any]] = []
    if not isinstance(rows, list):
        return refs
    for row in rows:
        if not isinstance(row, dict):
            continue
        refs.append(
            _issue_evidence_ref(
                repo=repo,
                url=str(row.get("url") or ""),
                action=action,
                number=_int_or_none(row.get("number")),
            )
        )
    return refs


def _rollup_status(checks: list[dict[str, Any]]) -> str:
    if not checks:
        return "unknown"
    states = {str(check.get("state") or check.get("status") or "").upper() for check in checks}
    if any(state == "FAILURE" for state in states):
        return "failed"
    if any(state in {"PENDING", "IN_PROGRESS", "QUEUED", "WAITING"} for state in states):
        return "pending"
    if all(state == "SUCCESS" for state in states):
        return "passed"
    return "unknown"


__all__ = [
    "GitHubCliError",
    "ci_status_for_branch",
    "comment_issue",
    "create_issue",
    "create_draft_pr",
    "gh_installed",
    "list_issues_by_label",
    "pr_for_branch",
    "search_issues",
    "validate_github_auth",
]
