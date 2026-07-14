"""Execution-evidence validation helpers."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
from typing import Any

from arnold_pipelines.megaplan.types import PlanState
from arnold_pipelines.megaplan._core import is_prose_mode
from arnold_pipelines.megaplan.orchestration.authority_readers import (
    has_durable_terminal_task_evidence,
)
from arnold_pipelines.megaplan._core.io import list_batch_artifacts, read_json
from arnold_pipelines.megaplan.execute.quality import unchanged_baseline_uncommitted_paths
from arnold_pipelines.megaplan.loop.git import _collect_git_status_paths_with_nested_repos, _normalize_repo_path

from .advisory_projection import ADVISORY_PATH_PROJECTION_LIMIT, summarize_path_list_for_prose
from .rubber_stamp import _is_perfunctory_ack, is_rubber_stamp


def _is_runtime_artifact_path(path: str) -> bool:
    normalized = path.strip()
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized == ".megaplan" or normalized.startswith(".megaplan/")


def _pre_existing_task_ids(plan_dir: Path | None) -> set[str]:
    """Return task IDs declared as pre-existing in ``contract.json``."""

    if plan_dir is None:
        return set()
    contract_path = plan_dir / "contract.json"
    try:
        data = json.loads(contract_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    if not isinstance(data, dict):
        return set()
    pre_existing = data.get("pre_existing")
    if not isinstance(pre_existing, list):
        return set()
    return {
        str(item).strip()
        for item in pre_existing
        if isinstance(item, str) and item.strip()
    }


def _authoritative_execute_task_overrides(plan_dir: Path | None) -> dict[str, dict[str, Any]]:
    """Return newest persisted execute task records keyed by task ID."""

    if plan_dir is None:
        return {}
    overrides: dict[str, dict[str, Any]] = {}
    try:
        artifacts = list_batch_artifacts(plan_dir)
    except Exception:
        return {}
    for artifact in artifacts:
        try:
            payload = read_json(artifact)
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        raw_updates = payload.get("task_updates")
        if not isinstance(raw_updates, list):
            continue
        for item in raw_updates:
            if not isinstance(item, dict):
                continue
            task_id = item.get("task_id") or item.get("id")
            if isinstance(task_id, str) and task_id.strip():
                overrides[task_id.strip()] = item
    return overrides


def apply_authoritative_execute_overrides(
    finalize_data: dict[str, Any],
    *,
    plan_dir: Path | None,
) -> dict[str, Any]:
    """Merge persisted execute evidence back into ``finalize_data``.

    Some execute batches are reconstructed from tool-call logs after the worker
    fails to emit a structured JSON report. Those artifacts may still carry
    authoritative top-level ``files_changed`` / ``commands_run`` evidence but
    omit the matching ``task_updates`` / ``sense_check_acknowledgments``
    records, leaving finalize tasks stranded in ``pending`` despite the work
    being present in the batch artifact and repository. When an artifact's
    top-level evidence maps uniquely to one still-untracked task, synthesize a
    narrow override from that artifact so terminal execute aggregation does not
    deadlock on tracking noise alone.
    """

    if plan_dir is None:
        return finalize_data
    tasks = finalize_data.get("tasks")
    sense_checks = finalize_data.get("sense_checks")
    if not isinstance(tasks, list) or not isinstance(sense_checks, list):
        return finalize_data

    try:
        artifacts = list_batch_artifacts(plan_dir)
    except Exception:
        return finalize_data

    tasks_by_id = {
        str(task.get("id")).strip(): task
        for task in tasks
        if isinstance(task, dict) and isinstance(task.get("id"), str) and task.get("id", "").strip()
    }
    sense_checks_by_id = {
        str(check.get("id")).strip(): check
        for check in sense_checks
        if isinstance(check, dict) and isinstance(check.get("id"), str) and check.get("id", "").strip()
    }

    explicit_task_ids: set[str] = set()
    explicit_sense_check_ids: set[str] = set()
    for artifact in artifacts:
        try:
            payload = read_json(artifact)
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        for item in payload.get("task_updates", []):
            if not isinstance(item, dict):
                continue
            task_id = item.get("task_id") or item.get("id")
            if isinstance(task_id, str) and task_id.strip():
                explicit_task_ids.add(task_id.strip())
                task = tasks_by_id.get(task_id.strip())
                if task is not None and not has_durable_terminal_task_evidence(task):
                    task.update(item)
                    task.setdefault("id", task_id.strip())
        for item in payload.get("sense_check_acknowledgments", []):
            if not isinstance(item, dict):
                continue
            check_id = item.get("sense_check_id") or item.get("id")
            if isinstance(check_id, str) and check_id.strip():
                explicit_sense_check_ids.add(check_id.strip())
                check = sense_checks_by_id.get(check_id.strip())
                if check is not None and isinstance(item.get("executor_note"), str):
                    check["executor_note"] = item["executor_note"]

    for artifact in artifacts:
        try:
            payload = read_json(artifact)
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        top_files = {
            _normalize_repo_path(path, plan_dir.parent)
            for path in payload.get("files_changed", [])
            if isinstance(path, str) and path.strip()
        }
        top_commands = {
            str(command).strip()
            for command in payload.get("commands_run", [])
            if isinstance(command, str) and command.strip()
        }
        if not top_files and not top_commands:
            continue

        candidate_tasks: list[dict[str, Any]] = []
        for task in tasks:
            if not isinstance(task, dict):
                continue
            task_id = task.get("id")
            if not isinstance(task_id, str) or not task_id.strip():
                continue
            if task_id in explicit_task_ids:
                continue
            if str(task.get("executor_notes", "")).strip():
                continue
            declared_files = {
                _normalize_repo_path(path, plan_dir.parent)
                for path in task.get("files_changed", [])
                if isinstance(path, str) and path.strip()
            }
            declared_commands = {
                str(command).strip()
                for command in task.get("commands_run", [])
                if isinstance(command, str) and command.strip()
            }
            file_match = bool(declared_files and declared_files.intersection(top_files))
            command_match = bool(declared_commands and declared_commands.intersection(top_commands))
            if file_match or command_match:
                candidate_tasks.append(task)
        if len(candidate_tasks) != 1:
            continue

        task = candidate_tasks[0]
        task_id = str(task.get("id")).strip()
        task["status"] = "done"
        task["executor_notes"] = (
            str(payload.get("output", "")).strip()
            or "[harness] synthesized from artifact-level execute evidence"
        )
        if top_files:
            task["files_changed"] = sorted(top_files.intersection(
                {
                    _normalize_repo_path(path, plan_dir.parent)
                    for path in task.get("files_changed", [])
                    if isinstance(path, str) and path.strip()
                }
            ) or top_files)
        if top_commands:
            task["commands_run"] = sorted(top_commands)
        head_sha = payload.get("head_sha")
        if isinstance(head_sha, str) and head_sha.strip():
            task["head_sha"] = head_sha.strip()
        explicit_task_ids.add(task_id)

        candidate_checks = [
            check
            for check in sense_checks
            if isinstance(check, dict)
            and check.get("task_id") == task_id
            and not str(check.get("executor_note", "")).strip()
            and str(check.get("id", "")).strip() not in explicit_sense_check_ids
        ]
        if len(candidate_checks) == 1:
            candidate_checks[0]["executor_note"] = task["executor_notes"]
            explicit_sense_check_ids.add(str(candidate_checks[0].get("id")).strip())

    return finalize_data


def validate_execution_evidence(
    finalize_data: dict[str, Any],
    project_dir: Path,
    *,
    mode: str = "code",
    state: PlanState | None = None,
    plan_dir: Path | None = None,
    artifact_prefix: str = "execution_audit",
    base_ref: str | None = None,
    head_ref: str | None = None,
) -> dict[str, Any]:
    finalize_data = apply_authoritative_execute_overrides(
        finalize_data,
        plan_dir=plan_dir,
    )
    if is_prose_mode(state or {"config": {"mode": mode}}):
        return _validate_execution_evidence_doc(finalize_data, project_dir)
    return _validate_execution_evidence_code(
        finalize_data,
        project_dir,
        plan_dir=plan_dir,
        artifact_prefix=artifact_prefix,
        base_ref=base_ref,
        head_ref=head_ref,
        state=state,
    )


def _evidence_window(
    project_dir: Path,
    base_ref: str | None = None,
    head_ref: str | None = None,
) -> dict[str, Any]:
    def _rev_parse(ref: str) -> str | None:
        try:
            completed = subprocess.run(
                ["git", "rev-parse", ref],
                cwd=project_dir,
                text=True,
                capture_output=True,
                check=False,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return None
        if completed.returncode != 0:
            return None
        return completed.stdout.strip() or None

    return {
        "source": "declared" if base_ref else "heuristic_merge_base",
        "base_ref": base_ref,
        "base_sha": _rev_parse(base_ref) if base_ref else None,
        "head_ref": head_ref or "HEAD",
        "head_sha": _rev_parse(head_ref or "HEAD"),
    }


def _resolve_ref_sha(project_dir: Path, ref: str | None) -> str | None:
    if not ref:
        return None
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--verify", ref],
            cwd=project_dir,
            text=True,
            capture_output=True,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout.strip() or None


def _git_rev_parse_head(project_dir: Path) -> str | None:
    return _resolve_ref_sha(project_dir, "HEAD")


def _collect_declared_committed_paths(
    project_dir: Path,
    base_sha: str,
    head_sha: str,
) -> set[str]:
    try:
        completed = subprocess.run(
            ["git", "diff", "--name-only", f"{base_sha}..{head_sha}"],
            cwd=project_dir,
            text=True,
            capture_output=True,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return set()
    if completed.returncode != 0:
        return set()
    return {
        _normalize_repo_path(line.strip().strip('"'), project_dir)
        for line in completed.stdout.splitlines()
        if line.strip()
    }


def _summarize_advisory_paths(
    paths: list[str],
    *,
    plan_dir: Path | None,
    artifact_prefix: str,
    label: str,
) -> str:
    if plan_dir is None:
        item_limit = ADVISORY_PATH_PROJECTION_LIMIT
        if len(paths) <= item_limit:
            return ", ".join(paths)
        shown = ", ".join(paths[:item_limit])
        return f"{len(paths)} paths (showing {item_limit}): {shown}"
    return summarize_path_list_for_prose(
        paths,
        plan_dir=plan_dir,
        artifact_prefix=artifact_prefix,
        label=label,
    )


def _validate_execution_evidence_doc(finalize_data: dict[str, Any], project_dir: Path) -> dict[str, Any]:
    del project_dir
    findings: list[str] = []
    tasks = finalize_data.get("tasks", [])

    planned_sections: set[str] = set()
    claimed_sections: set[str] = set()
    for task in tasks:
        if task.get("status") != "done":
            continue
        for section_id in task.get("sections_written", []):
            if isinstance(section_id, str) and section_id.strip():
                claimed_sections.add(section_id)

    for task in tasks:
        for section_id in task.get("sections_written", []):
            if isinstance(section_id, str) and section_id.strip():
                planned_sections.add(section_id)

    missing_sections = sorted(planned_sections - claimed_sections)
    if missing_sections:
        findings.append(
            "Planned sections not claimed by any done task: "
            + ", ".join(missing_sections)
        )

    unclaimed = sorted(claimed_sections - planned_sections)
    if unclaimed:
        findings.append(
            "Sections claimed by done tasks but not in any task plan: "
            + ", ".join(unclaimed)
        )

    output_path_str = ""
    config = finalize_data.get("config", {})
    if isinstance(config, dict):
        output_path_str = config.get("output_path", "")
    if not output_path_str:
        for task in tasks:
            if task.get("sections_written"):
                break

    for sense_check in finalize_data.get("sense_checks", []):
        sense_check_id = sense_check.get("id", "?")
        note = sense_check.get("executor_note", "")
        if not isinstance(note, str) or not note.strip():
            findings.append(f"Sense check {sense_check_id} is missing an executor acknowledgment.")
            continue
        if _is_perfunctory_ack(note):
            findings.append(
                f"Sense check {sense_check_id} acknowledgment is perfunctory: {note.strip()!r}."
            )

    for task in tasks:
        if task.get("status") != "done":
            continue
        task_id = task.get("id", "?")
        notes = task.get("executor_notes", "")
        if not isinstance(notes, str) or not notes.strip():
            continue
        if is_rubber_stamp(notes, strict=True):
            findings.append(
                f"Task {task_id} executor_notes are perfunctory: {notes.strip()!r}."
            )

    return {
        "findings": findings,
        "files_in_diff": [],
        "files_claimed": [],
        "skipped": False,
        "reason": "",
    }


def _validate_execution_evidence_code(
    finalize_data: dict[str, Any],
    project_dir: Path,
    *,
    plan_dir: Path | None = None,
    artifact_prefix: str = "execution_audit",
    base_ref: str | None = None,
    head_ref: str | None = None,
    state: PlanState | None = None,
) -> dict[str, Any]:
    authoritative_overrides = _authoritative_execute_task_overrides(plan_dir)
    audited_tasks: list[dict[str, Any]] = []
    for task in finalize_data.get("tasks", []):
        if not isinstance(task, dict):
            continue
        task_id = task.get("id") or task.get("task_id")
        merged = dict(task)
        if isinstance(task_id, str):
            authoritative = authoritative_overrides.get(task_id)
            if isinstance(authoritative, dict) and not has_durable_terminal_task_evidence(task):
                merged.update(authoritative)
                merged.setdefault("id", task_id)
                merged.setdefault("task_id", task_id)
        audited_tasks.append(merged)

    findings: list[str] = []
    files_claimed = sorted(
        {
            _normalize_repo_path(path, project_dir)
            for task in audited_tasks
            for path in task.get("files_changed", [])
            if isinstance(path, str)
            and path.strip()
            and not _is_runtime_artifact_path(_normalize_repo_path(path, project_dir))
        }
    )

    if not (project_dir / ".git").exists():
        return {
            "findings": findings,
            "files_in_diff": [],
            "files_claimed": files_claimed,
            "skipped": True,
            "reason": "Project directory is not a git repository.",
            "evidence_window": _evidence_window(project_dir, base_ref, head_ref),
        }

    active_head_sha = _git_rev_parse_head(project_dir)
    head_sha = _resolve_ref_sha(project_dir, head_ref or "HEAD")
    base_sha = _resolve_ref_sha(project_dir, base_ref) if base_ref is not None else None
    evidence_window: dict[str, Any] = {
        "base_sha": base_sha,
        "head_ref": head_ref or "HEAD",
        "head_sha": head_sha,
        "source": "declared" if base_ref is not None else "heuristic_merge_base",
    }

    declared_authoritative = (
        base_ref is not None and base_sha is not None and head_sha is not None
    )
    committed_paths = (
        {
            path
            for path in _collect_declared_committed_paths(project_dir, base_sha, head_sha)
            if not _is_runtime_artifact_path(path)
        }
        if declared_authoritative
        else set()
    )
    historical_window = bool(
        declared_authoritative and head_ref and head_sha != active_head_sha
    )
    if historical_window:
        # Historical receipts bind the immutable base..landed-head range. The
        # caller's later checkout and working tree are not evidence for it.
        files_in_diff_set, status_error = set(committed_paths), None
    else:
        files_in_diff_set, status_error = _collect_git_status_paths_with_nested_repos(
            project_dir,
            claimed_paths=set(files_claimed),
            # Chain milestones commit their work before review, leaving a clean
            # working tree; a status-only check would falsely report every committed
            # file as a phantom claim ("implementation not present in the diff").
            # Include the committed milestone range so committed work counts.
            include_committed=True,
            committed_base_ref=base_sha if declared_authoritative else None,
            committed_head_ref=head_sha if declared_authoritative else None,
        )
    if status_error is not None:
        return {
            "findings": findings,
            "files_in_diff": [],
            "files_claimed": files_claimed,
            "skipped": True,
            "reason": status_error,
            "evidence_window": _evidence_window(project_dir, base_ref, head_ref),
        }

    files_in_diff = sorted(
        path for path in files_in_diff_set if not _is_runtime_artifact_path(path)
    )
    claimed_set = set(files_claimed)
    diff_set = set(files_in_diff)
    authority_set = committed_paths if declared_authoritative else diff_set

    dir_prefixes = [path for path in diff_set if path.endswith("/")]

    def _covered_by_diff(claimed: str) -> bool:
        if claimed in authority_set:
            return True
        return any(claimed.startswith(prefix) or claimed == prefix.rstrip("/") for prefix in dir_prefixes)

    phantom_claims = sorted(claimed for claimed in claimed_set if not _covered_by_diff(claimed))
    if phantom_claims:
        findings.append(
            "Executor claimed changed files not present in git status: "
            + _summarize_advisory_paths(
                phantom_claims,
                plan_dir=plan_dir,
                artifact_prefix=artifact_prefix,
                label="phantom_claims",
            )
        )

    def _dir_is_claimed(diff_path: str) -> bool:
        if not diff_path.endswith("/"):
            return False
        return any(claimed.startswith(diff_path) for claimed in claimed_set)

    unclaimed_source = authority_set if declared_authoritative else diff_set
    unclaimed_source = unclaimed_source - unchanged_baseline_uncommitted_paths(
        project_dir, state or {}
    )
    unclaimed_changes = sorted(
        diff_path for diff_path in unclaimed_source
        if diff_path not in claimed_set and not _dir_is_claimed(diff_path)
    )
    if unclaimed_changes:
        findings.append(
            "Git status shows changed files not claimed by any task: "
            + _summarize_advisory_paths(
                unclaimed_changes,
                plan_dir=plan_dir,
                artifact_prefix=artifact_prefix,
                label="unclaimed_changes",
            )
        )

    for sense_check in finalize_data.get("sense_checks", []):
        sense_check_id = sense_check.get("id", "?")
        note = sense_check.get("executor_note", "")
        if not isinstance(note, str) or not note.strip():
            findings.append(f"Sense check {sense_check_id} is missing an executor acknowledgment.")
            continue
        if _is_perfunctory_ack(note):
            findings.append(
                f"Sense check {sense_check_id} acknowledgment is perfunctory: {note.strip()!r}."
            )

    pending_tasks: list[str] = []
    skipped_without_reason: list[str] = []
    blocked_without_reason: list[str] = []
    hollow_done_tasks: list[str] = []
    pre_existing_ids = _pre_existing_task_ids(plan_dir)
    for task in audited_tasks:
        task_id = task.get("id", "?")
        status = task.get("status", "")
        notes = task.get("executor_notes", "")
        notes_text = notes.strip() if isinstance(notes, str) else ""
        if status == "pending":
            pending_tasks.append(task_id)
            continue
        if status == "skipped" and not notes_text:
            skipped_without_reason.append(task_id)
            continue
        if status == "blocked" and not notes_text:
            blocked_without_reason.append(task_id)
            continue
        if status == "done":
            if task_id in pre_existing_ids:
                continue
            files = task.get("files_changed") or []
            commands = task.get("commands_run") or []
            if not files and not commands:
                if not notes_text or is_rubber_stamp(notes, strict=True):
                    hollow_done_tasks.append(task_id)
                continue
            if notes_text and is_rubber_stamp(notes, strict=True):
                findings.append(
                    f"Task {task_id} executor_notes are perfunctory: {notes_text!r}."
                )

    if pending_tasks:
        findings.append(
            "Tasks left pending after execute (executor never started them): "
            + ", ".join(pending_tasks)
        )
    if skipped_without_reason:
        findings.append(
            "Tasks marked skipped without an executor_notes reason: "
            + ", ".join(skipped_without_reason)
        )
    if blocked_without_reason:
        findings.append(
            "Tasks marked blocked without an executor_notes reason: "
            + ", ".join(blocked_without_reason)
        )
    if hollow_done_tasks:
        findings.append(
            "Tasks marked done with neither files_changed nor commands_run "
            "(suspicious — executor may have skipped without flagging): "
            + ", ".join(hollow_done_tasks)
        )

    return {
        "findings": findings,
        "files_in_diff": files_in_diff,
        "files_in_committed_range": sorted(committed_paths),
        "files_claimed": files_claimed,
        "skipped": False,
        "reason": "",
        "evidence_window": _evidence_window(project_dir, base_ref, head_ref),
    }
