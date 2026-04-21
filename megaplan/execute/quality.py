from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from typing import Any, Callable

from megaplan.evaluation import _parse_git_status_paths
from megaplan.audits.quality_gates import run_quality_checks


def _check_done_task_evidence(
    tasks: list[dict[str, Any]],
    *,
    issues: list[str],
    should_classify: Callable[[dict[str, Any]], bool],
    has_evidence: Callable[[dict[str, Any]], bool],
    has_advisory_evidence: Callable[[dict[str, Any]], bool],
    missing_message: str,
    advisory_message: str,
) -> list[str]:
    missing_task_ids: list[str] = []
    advisory_task_ids: list[str] = []
    for task in tasks:
        if task.get("status") != "done" or not should_classify(task):
            continue
        if has_evidence(task):
            continue
        if has_advisory_evidence(task):
            advisory_task_ids.append(task["id"])
        else:
            missing_task_ids.append(task["id"])
    if missing_task_ids:
        issues.append(missing_message + ", ".join(missing_task_ids))
    if advisory_task_ids:
        issues.append(advisory_message + ", ".join(advisory_task_ids))
    return missing_task_ids


def _normalize_execute_claimed_path(path: str, project_dir: Path | None = None) -> str:
    p = Path(path.strip())
    if project_dir is not None and p.is_absolute():
        try:
            p = p.relative_to(project_dir)
        except ValueError:
            pass
    return p.as_posix()


def _repo_path_hash(project_dir: Path, relative_path: str) -> str:
    target = project_dir / relative_path
    if not target.exists():
        return "<missing>"
    if target.is_dir():
        return "<directory>"
    return hashlib.sha256(target.read_bytes()).hexdigest()


def _capture_git_status_snapshot(
    project_dir: Path,
) -> tuple[dict[str, str], str | None]:
    if not (project_dir / ".git").exists():
        return {}, "Project directory is not a git repository."
    try:
        process = subprocess.run(
            ["git", "status", "--short"],
            cwd=str(project_dir),
            text=True,
            capture_output=True,
            timeout=30,
        )
    except FileNotFoundError:
        return {}, "git not found on PATH."
    except subprocess.TimeoutExpired:
        return {}, "git status timed out."
    if process.returncode != 0:
        return (
            {},
            f"git status failed: {process.stderr.strip() or process.stdout.strip()}",
        )
    paths = _parse_git_status_paths(process.stdout)
    return {path: _repo_path_hash(project_dir, path) for path in paths}, None


def _observed_batch_paths(
    *,
    project_dir: Path,
    before_snapshot: dict[str, str],
    after_snapshot: dict[str, str],
) -> set[str]:
    observed: set[str] = set()
    for path in set(before_snapshot) | set(after_snapshot):
        before_hash = before_snapshot.get(path)
        after_hash = after_snapshot.get(path)
        if after_hash is None:
            after_hash = _repo_path_hash(project_dir, path)
        if before_hash is None or before_hash != after_hash:
            observed.add(path)
    return observed


def _collect_execute_claimed_paths(
    payload: dict[str, Any], project_dir: Path | None = None
) -> set[str]:
    """Collect top-level files_changed only for git observation comparison.

    Per-task files_changed are intentionally excluded — they often include
    files the executor read/verified but didn't modify, which causes false
    phantom-claim deviations when compared against git status deltas.
    Per-task evidence is validated separately by the audit path.
    """
    return {
        _normalize_execute_claimed_path(path, project_dir)
        for path in payload.get("files_changed", [])
        if isinstance(path, str) and path.strip()
    }


def _observe_git_changes(
    *,
    project_dir: Path,
    payload: dict[str, Any],
    before_snapshot: dict[str, str],
    before_error: str | None,
    batch_number: int,
    batches_total: int,
    capture_git_status_snapshot_fn: Callable[[Path], tuple[dict[str, str], str | None]],
) -> list[str]:
    issues: list[str] = []
    if before_error is not None:
        issues.append(
            f"Advisory observation skip before batch {batch_number}/{batches_total}: {before_error}"
        )
    after_snapshot, after_error = capture_git_status_snapshot_fn(project_dir)
    if after_error is not None:
        issues.append(
            f"Advisory observation skip after batch {batch_number}/{batches_total}: {after_error}"
        )
    elif before_error is None:
        observed_paths = _observed_batch_paths(
            project_dir=project_dir,
            before_snapshot=before_snapshot,
            after_snapshot=after_snapshot,
        )
        claimed_paths = _collect_execute_claimed_paths(payload, project_dir)
        phantom_claims = sorted(claimed_paths - observed_paths)
        if phantom_claims:
            issues.append(
                "Advisory observation mismatch: executor claimed files not observed in git status/content hash delta: "
                + ", ".join(phantom_claims)
            )
        unclaimed_changes = sorted(observed_paths - claimed_paths)
        if unclaimed_changes:
            issues.append(
                "Advisory observation mismatch: git status/content hash delta found unclaimed files: "
                + ", ".join(unclaimed_changes)
            )
    return issues


def _collect_quality_deviations(
    *,
    project_dir: Path,
    before_snapshot: dict[str, str],
    before_line_counts: dict[str, int],
    quality_config: dict[str, Any],
    capture_git_status_snapshot_fn: Callable[[Path], tuple[dict[str, str], str | None]],
) -> list[str]:
    try:
        after_snapshot, after_error = capture_git_status_snapshot_fn(project_dir)
    except (
        Exception
    ) as exc:  # pragma: no cover - defensive guard for advisory-only quality checks.
        return [
            f"Advisory quality: skipped quality checks because post-batch git snapshot failed: {exc}"
        ]
    if after_error is not None:
        return [
            f"Advisory quality: skipped quality checks because post-batch git snapshot failed: {after_error}"
        ]
    changed_paths = _observed_batch_paths(
        project_dir=project_dir,
        before_snapshot=before_snapshot,
        after_snapshot=after_snapshot,
    )
    return run_quality_checks(
        project_dir,
        changed_paths=changed_paths,
        before_line_counts=before_line_counts,
        config=quality_config,
    )
