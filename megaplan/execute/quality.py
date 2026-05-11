from __future__ import annotations

import hashlib
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from megaplan.evaluation import (
    _collect_git_status_paths_with_nested_repos,
    _parse_git_status_paths,
)
from megaplan.audits.quality_gates import run_quality_checks


AUTO_ATTRIBUTION_PATH_LIST_LIMIT = 8


@dataclass
class AttributionResult:
    records: list[dict[str, Any]]
    recursive_snapshot: dict[str, str] | None


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


# Minimum length of executor_notes to count as substantive evidence for
# audit / research style tasks (which intentionally produce no files_changed).
_AUDIT_NOTES_MIN_LEN = 100
_DOCS_NOTES_ADVISORY_MIN_LEN = 50


def _task_kind(task: dict[str, Any]) -> str:
    """Return the declared task kind, defaulting to ``code`` for back-compat."""
    kind = task.get("kind")
    if isinstance(kind, str) and kind:
        return kind
    return "code"


def _has_audit_or_research_evidence(task: dict[str, Any]) -> bool:
    notes = (task.get("executor_notes") or "").strip()
    return len(notes) >= _AUDIT_NOTES_MIN_LEN


def _has_audit_or_research_advisory(task: dict[str, Any]) -> bool:
    return bool((task.get("executor_notes") or "").strip())


def _has_test_task_evidence(task: dict[str, Any]) -> bool:
    if task.get("files_changed"):
        return True
    cmds = task.get("commands_run") or []
    for cmd in cmds:
        text = str(cmd).lower()
        if "pytest" in text or "test" in text:
            return True
    return False


def _has_test_task_advisory(task: dict[str, Any]) -> bool:
    return bool(task.get("commands_run"))


def _has_docs_task_evidence(task: dict[str, Any]) -> bool:
    return bool(task.get("files_changed"))


def _has_docs_task_advisory(task: dict[str, Any]) -> bool:
    if task.get("commands_run"):
        return True
    notes = (task.get("executor_notes") or "").strip()
    return len(notes) >= _DOCS_NOTES_ADVISORY_MIN_LEN


def _has_code_task_evidence(task: dict[str, Any]) -> bool:
    return bool(task.get("files_changed"))


def _has_code_task_advisory(task: dict[str, Any]) -> bool:
    return bool(task.get("commands_run"))


def _evidence_check_for_kind(
    kind: str,
) -> tuple[
    Callable[[dict[str, Any]], bool],
    Callable[[dict[str, Any]], bool],
    str,
    str,
]:
    """Return ``(has_evidence, has_advisory, missing_msg, advisory_msg)`` for a kind."""
    if kind in ("audit", "research"):
        return (
            _has_audit_or_research_evidence,
            _has_audit_or_research_advisory,
            "Done audit/research tasks missing substantial executor_notes "
            f"(need >={_AUDIT_NOTES_MIN_LEN} chars): ",
            "Advisory: audit/research task has brief executor_notes: ",
        )
    if kind == "test":
        return (
            _has_test_task_evidence,
            _has_test_task_advisory,
            "Done test tasks missing files_changed or pytest commands_run: ",
            "Advisory: test task has commands_run but no files_changed: ",
        )
    if kind == "docs":
        return (
            _has_docs_task_evidence,
            _has_docs_task_advisory,
            "Done docs tasks missing files_changed: ",
            "Advisory: docs task has notes but no files_changed: ",
        )
    # code (default)
    return (
        _has_code_task_evidence,
        _has_code_task_advisory,
        "Done tasks missing both files_changed and commands_run: ",
        "Advisory: done tasks rely on non-file evidence (FLAG-006 softening): ",
    )


def _check_done_task_evidence_by_kind(
    tasks: list[dict[str, Any]],
    *,
    issues: list[str],
    should_classify: Callable[[dict[str, Any]], bool],
    code_has_evidence: Callable[[dict[str, Any]], bool] | None = None,
    code_has_advisory: Callable[[dict[str, Any]], bool] | None = None,
    code_missing_message: str | None = None,
    code_advisory_message: str | None = None,
) -> list[str]:
    """Per-kind dispatch over ``_check_done_task_evidence``.

    Buckets eligible done tasks by their declared ``kind`` and applies the
    appropriate evidence-check shape for each. Tasks without a ``kind`` are
    treated as ``code`` (preserving the prior default behaviour).

    The ``code_*`` overrides allow callers (e.g. prose mode, callers with
    bespoke messages) to override the evidence shape for the ``code`` bucket
    only — ``audit``/``research``/``test``/``docs`` always use the
    kind-specific defaults.
    """
    groups: dict[str, list[dict[str, Any]]] = {}
    for task in tasks:
        if task.get("status") != "done" or not should_classify(task):
            continue
        groups.setdefault(_task_kind(task), []).append(task)

    missing: list[str] = []
    for kind, group_tasks in groups.items():
        has_evidence, has_advisory, missing_msg, advisory_msg = _evidence_check_for_kind(
            kind
        )
        if kind == "code":
            if code_has_evidence is not None:
                has_evidence = code_has_evidence
            if code_has_advisory is not None:
                has_advisory = code_has_advisory
            if code_missing_message is not None:
                missing_msg = code_missing_message
            if code_advisory_message is not None:
                advisory_msg = code_advisory_message
        missing.extend(
            _check_done_task_evidence(
                group_tasks,
                issues=issues,
                should_classify=lambda _task: True,
                has_evidence=has_evidence,
                has_advisory_evidence=has_advisory,
                missing_message=missing_msg,
                advisory_message=advisory_msg,
            )
        )
    return missing


def _format_auto_attributed_paths(paths: list[str]) -> str:
    displayed = paths[:AUTO_ATTRIBUTION_PATH_LIST_LIMIT]
    if len(paths) > AUTO_ATTRIBUTION_PATH_LIST_LIMIT:
        displayed = [*displayed, "…"]
    return ", ".join(displayed)


def _auto_attribute_unclaimed_paths(
    *,
    project_dir: Path,
    finalize_data: dict[str, Any],
    payload: dict[str, Any],
    batch_task_ids: list[str],
    issues: list[str],
    capture_recursive_snapshot_fn: Callable[[Path], tuple[dict[str, str], str | None]],
) -> AttributionResult:
    batch_id_set = set(batch_task_ids)
    tasks = finalize_data.get("tasks") or []
    unattributed_done_tasks = [
        task
        for task in tasks
        if task.get("id") in batch_id_set
        and task.get("status") == "done"
        and not (task.get("files_changed") or [])
        and not (task.get("commands_run") or [])
    ]
    if not unattributed_done_tasks:
        return AttributionResult(records=[], recursive_snapshot=None)

    snapshot, error = capture_recursive_snapshot_fn(project_dir)
    if error is not None:
        return AttributionResult(records=[], recursive_snapshot=None)

    git_paths = {path for path in snapshot if not path.endswith("/")}
    claimed = {
        _normalize_execute_claimed_path(path, project_dir)
        for task in tasks
        for path in (task.get("files_changed") or [])
        if isinstance(path, str) and path.strip()
    }
    unclaimed_paths = sorted(git_paths - claimed)
    if not unclaimed_paths:
        return AttributionResult(records=[], recursive_snapshot=snapshot)

    task_updates_by_id = {
        update.get("task_id"): update
        for update in (payload.get("task_updates") or [])
        if isinstance(update, dict)
    }
    existing_payload_files = [
        path for path in (payload.get("files_changed") or []) if isinstance(path, str)
    ]
    seen_payload_files = {
        _normalize_execute_claimed_path(path, project_dir)
        for path in existing_payload_files
        if path.strip()
    }
    merged_payload_files = list(existing_payload_files)
    for path in unclaimed_paths:
        normalized = _normalize_execute_claimed_path(path, project_dir)
        if normalized not in seen_payload_files:
            merged_payload_files.append(path)
            seen_payload_files.add(normalized)
    payload["files_changed"] = merged_payload_files

    ambiguous = len(unattributed_done_tasks) > 1
    truncated_list = _format_auto_attributed_paths(unclaimed_paths)
    records: list[dict[str, Any]] = []
    for task in unattributed_done_tasks:
        task_id = task.get("id")
        task["files_changed"] = list(unclaimed_paths)
        task["auto_attributed_files"] = True
        update = task_updates_by_id.get(task_id)
        if update is not None:
            update["files_changed"] = list(unclaimed_paths)
            update["auto_attributed_files"] = True
        issues.append(
            f"Auto-attributed {len(unclaimed_paths)} unclaimed file(s) to task {task_id} "
            f"(worker reported empty files_changed): {truncated_list}"
        )
        records.append(
            {
                "task_id": task_id,
                "files": list(unclaimed_paths),
                "ambiguous": ambiguous,
            }
        )
    if ambiguous:
        issues.append(
            f"Auto-attribution ambiguous: {len(unattributed_done_tasks)} done tasks shared "
            f"{len(unclaimed_paths)} unclaimed files"
        )
    return AttributionResult(records=records, recursive_snapshot=snapshot)


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


def _run_git_status_snapshot(
    project_dir: Path,
    *,
    untracked_mode: str,
    claimed_paths: set[str] | None = None,
) -> tuple[dict[str, str], str | None]:
    if not (project_dir / ".git").exists():
        return {}, "Project directory is not a git repository."
    if claimed_paths:
        paths, error = _collect_git_status_paths_with_nested_repos(
            project_dir,
            claimed_paths=claimed_paths,
            untracked_mode=untracked_mode,
        )
        if error is not None:
            return {}, error
    else:
        command = ["git", "status", "--short"]
        if untracked_mode == "all":
            command.append("--untracked-files=all")
        try:
            process = subprocess.run(
                command,
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


def _capture_git_status_snapshot(
    project_dir: Path,
    claimed_paths: set[str] | None = None,
) -> tuple[dict[str, str], str | None]:
    return _run_git_status_snapshot(
        project_dir,
        untracked_mode="normal",
        claimed_paths=claimed_paths,
    )


def _capture_git_status_snapshot_recursive(
    project_dir: Path,
    claimed_paths: set[str] | None = None,
) -> tuple[dict[str, str], str | None]:
    return _run_git_status_snapshot(
        project_dir,
        untracked_mode="all",
        claimed_paths=claimed_paths,
    )


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
