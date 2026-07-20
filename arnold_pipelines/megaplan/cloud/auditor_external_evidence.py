"""Read-only external evidence collectors for the six-hour auditor."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Callable

Runner = Callable[..., subprocess.CompletedProcess[str]]

_IGNORED_ENGINE_TREE_PREFIXES = (".megaplan/",)
_ENGINE_TREE_CONSUMERS = (
    ("arnold_pipelines/megaplan/cloud/wrappers/", "cloud_wrappers"),
    ("arnold_pipelines/megaplan/cloud/", "cloud_runtime"),
    ("arnold_pipelines/", "python_package"),
    ("tests/", "tests"),
)
_PASSING_CHECK_STATES = frozenset({"pass", "passing", "success", "skipping", "skip", "neutral"})
_FAILING_RUN_CONCLUSIONS = frozenset({"action_required", "failure", "startup_failure", "timed_out"})


def _run(
    command: list[str],
    *,
    cwd: Path,
    runner: Runner,
) -> subprocess.CompletedProcess[str]:
    return runner(
        command,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )


def _tail(text: str, *, max_lines: int = 20) -> str:
    lines = (text or "").splitlines()
    if len(lines) <= max_lines:
        return (text or "").strip()
    return "\n".join(lines[-max_lines:]).strip()


def _parse_json_list(stdout: str) -> list[dict[str, Any]]:
    try:
        loaded = json.loads(stdout or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(loaded, list):
        return []
    return [item for item in loaded if isinstance(item, dict)]


def _failing_runs(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    failing: list[dict[str, Any]] = []
    for run in runs:
        conclusion = str(run.get("conclusion") or "").strip().lower()
        status = str(run.get("status") or "").strip().lower()
        if conclusion in _FAILING_RUN_CONCLUSIONS:
            failing.append(run)
            continue
        if status == "completed" and conclusion and conclusion not in _PASSING_CHECK_STATES:
            failing.append(run)
    return failing


def _parse_failed_checks(stdout: str) -> list[dict[str, str]]:
    failed: list[dict[str, str]] = []
    for line in (stdout or "").splitlines():
        parts = [part.strip() for part in line.split("\t")]
        if len(parts) < 2:
            continue
        state = parts[1].lower()
        if state in _PASSING_CHECK_STATES:
            continue
        failed.append(
            {
                "name": parts[0],
                "state": parts[1],
                "details": parts[2] if len(parts) > 2 else "",
            }
        )
    return failed


def collect_ci_health(
    repo_root: Path | str,
    *,
    base_branch: str = "main",
    runner: Runner = subprocess.run,
) -> dict[str, Any]:
    """Collect read-only CI health evidence via gh CLI."""

    root = Path(repo_root).expanduser().resolve()
    run_command = [
        "gh",
        "run",
        "list",
        "--branch",
        base_branch,
        "--limit",
        "20",
        "--json",
        "databaseId,headBranch,status,conclusion,workflowName,url",
    ]
    try:
        runs_proc = _run(run_command, cwd=root, runner=runner)
    except FileNotFoundError:
        return {
            "status": "unavailable",
            "available": False,
            "base_branch": base_branch,
            "reason": "gh_unavailable",
        }
    if runs_proc.returncode != 0:
        return {
            "status": "unavailable",
            "available": False,
            "base_branch": base_branch,
            "reason": "gh_run_list_failed",
            "stderr_tail": _tail(runs_proc.stderr or ""),
        }

    recent_runs = _parse_json_list(runs_proc.stdout or "")
    if runs_proc.stdout and not recent_runs:
        return {
            "status": "unavailable",
            "available": False,
            "base_branch": base_branch,
            "reason": "gh_run_list_invalid_json",
            "stdout_tail": _tail(runs_proc.stdout or ""),
        }

    try:
        checks_proc = _run(["gh", "pr", "checks", base_branch], cwd=root, runner=runner)
    except FileNotFoundError:
        checks_proc = None

    failed_checks: list[dict[str, str]] = []
    checks_probe: dict[str, Any] = {"available": False, "reason": "not_run"}
    if checks_proc is not None:
        if checks_proc.returncode == 0:
            failed_checks = _parse_failed_checks(checks_proc.stdout or "")
            checks_probe = {"available": True}
        else:
            checks_probe = {
                "available": False,
                "reason": "gh_pr_checks_failed",
                "stderr_tail": _tail(checks_proc.stderr or ""),
            }

    failing_runs = _failing_runs(recent_runs)
    status = "red" if failing_runs or failed_checks else "green"

    return {
        "status": status,
        "available": True,
        "base_branch": base_branch,
        "failing_run_count": len(failing_runs),
        "failed_checks": failed_checks,
        "recent_runs": recent_runs,
        "checks_probe": checks_probe,
    }


def _parse_porcelain_paths(stdout: str) -> list[str]:
    dirty_paths: list[str] = []
    for raw_line in (stdout or "").splitlines():
        if not raw_line.strip():
            continue
        path_text = raw_line[3:] if len(raw_line) >= 4 else raw_line
        if " -> " in path_text:
            path_text = path_text.rsplit(" -> ", 1)[-1]
        path = path_text.strip().strip('"')
        if not path:
            continue
        if path == ".megaplan" or any(path.startswith(prefix) for prefix in _IGNORED_ENGINE_TREE_PREFIXES):
            continue
        dirty_paths.append(path)
    return sorted(set(dirty_paths))


def _engine_tree_consumers(paths: list[str]) -> list[str]:
    consumers: set[str] = set()
    for path in paths:
        for prefix, consumer in _ENGINE_TREE_CONSUMERS:
            if path.startswith(prefix):
                consumers.add(consumer)
                break
    return sorted(consumers)


def _git_head(repo_root: Path, runner: Runner) -> dict[str, Any]:
    proc = _run(["git", "rev-parse", "HEAD"], cwd=repo_root, runner=runner)
    if proc.returncode != 0:
        return {
            "available": False,
            "reason": "git_head_failed",
            "stderr_tail": _tail(proc.stderr or ""),
        }
    return {
        "available": True,
        "head": (proc.stdout or "").strip(),
    }


def _mirror_changed_paths(
    repo_root: Path,
    *,
    primary_head: str,
    runner: Runner,
) -> list[str]:
    proc = _run(["git", "diff", "--name-only", primary_head, "HEAD"], cwd=repo_root, runner=runner)
    if proc.returncode != 0:
        return []
    changed = [line.strip() for line in (proc.stdout or "").splitlines() if line.strip()]
    return sorted(
        path
        for path in set(changed)
        if path != ".megaplan" and not any(path.startswith(prefix) for prefix in _IGNORED_ENGINE_TREE_PREFIXES)
    )


def collect_engine_tree_evidence(
    repo_root: Path | str,
    *,
    workspace_root: Path | str,
    candidate_mirror_roots: list[Path | str] | None = None,
    runner: Runner = subprocess.run,
) -> dict[str, Any]:
    """Collect read-only worktree and mirror divergence evidence."""

    root = Path(repo_root).expanduser().resolve()
    workspace = Path(workspace_root).expanduser().resolve()
    try:
        status_proc = _run(["git", "status", "--porcelain"], cwd=root, runner=runner)
    except FileNotFoundError:
        return {
            "status": "unavailable",
            "available": False,
            "workspace_root": str(workspace),
            "repo_root": str(root),
            "reason": "git_unavailable",
        }
    if status_proc.returncode != 0:
        return {
            "status": "unavailable",
            "available": False,
            "workspace_root": str(workspace),
            "repo_root": str(root),
            "reason": "git_status_failed",
            "stderr_tail": _tail(status_proc.stderr or ""),
        }

    dirty_paths = _parse_porcelain_paths(status_proc.stdout or "")
    try:
        primary_head = _git_head(root, runner)
    except FileNotFoundError:
        return {
            "status": "unavailable",
            "available": False,
            "workspace_root": str(workspace),
            "repo_root": str(root),
            "reason": "git_unavailable",
        }
    if not primary_head.get("available"):
        return {
            "status": "unavailable",
            "available": False,
            "workspace_root": str(workspace),
            "repo_root": str(root),
            "reason": str(primary_head.get("reason") or "git_head_failed"),
            "stderr_tail": str(primary_head.get("stderr_tail") or ""),
        }

    raw_candidates = candidate_mirror_roots if candidate_mirror_roots is not None else [root]
    candidate_paths: list[Path] = []
    seen: set[Path] = set()
    for candidate in raw_candidates:
        resolved = Path(candidate).expanduser().resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        candidate_paths.append(resolved)

    divergent_mirrors: list[dict[str, Any]] = []
    missing_mirrors: list[str] = []
    mirror_probe_errors: list[dict[str, str]] = []
    impacted_paths = list(dirty_paths)

    for candidate in candidate_paths:
        if candidate == root:
            continue
        if not candidate.exists():
            missing_mirrors.append(str(candidate))
            continue
        try:
            candidate_head = _git_head(candidate, runner)
        except FileNotFoundError:
            return {
                "status": "unavailable",
                "available": False,
                "workspace_root": str(workspace),
                "repo_root": str(root),
                "reason": "git_unavailable",
            }
        if not candidate_head.get("available"):
            mirror_probe_errors.append(
                {
                    "mirror_root": str(candidate),
                    "reason": str(candidate_head.get("reason") or "git_head_failed"),
                }
            )
            continue
        if candidate_head.get("head") == primary_head.get("head"):
            continue
        changed_paths = _mirror_changed_paths(
            candidate,
            primary_head=str(primary_head.get("head") or ""),
            runner=runner,
        )
        impacted_paths.extend(changed_paths)
        divergent_mirrors.append(
            {
                "mirror_root": str(candidate),
                "primary_head": primary_head.get("head"),
                "mirror_head": candidate_head.get("head"),
                "changed_paths": changed_paths,
            }
        )

    impacted_consumers = _engine_tree_consumers(sorted(set(impacted_paths)))
    status = "red" if dirty_paths or divergent_mirrors or missing_mirrors or mirror_probe_errors else "green"

    return {
        "status": status,
        "available": True,
        "workspace_root": str(workspace),
        "repo_root": str(root),
        "dirty_paths": dirty_paths,
        "divergent_mirrors": divergent_mirrors,
        "missing_mirrors": missing_mirrors,
        "mirror_probe_errors": mirror_probe_errors,
        "impacted_consumers": impacted_consumers,
    }


__all__ = [
    "collect_ci_health",
    "collect_engine_tree_evidence",
]
