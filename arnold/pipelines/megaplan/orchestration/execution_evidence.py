"""Execution-evidence validation helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from arnold.pipelines.megaplan.types import PlanState
from arnold.pipelines.megaplan._core import is_prose_mode
from arnold.pipelines.megaplan.loop.git import _collect_git_status_paths_with_nested_repos, _normalize_repo_path

from .advisory_projection import ADVISORY_PATH_PROJECTION_LIMIT, summarize_path_list_for_prose
from .rubber_stamp import _is_perfunctory_ack, is_rubber_stamp


def _is_runtime_artifact_path(path: str) -> bool:
    normalized = path.strip()
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized == ".megaplan" or normalized.startswith(".megaplan/")


def validate_execution_evidence(
    finalize_data: dict[str, Any],
    project_dir: Path,
    *,
    mode: str = "code",
    state: PlanState | None = None,
    plan_dir: Path | None = None,
    artifact_prefix: str = "execution_audit",
) -> dict[str, Any]:
    if is_prose_mode(state or {"config": {"mode": mode}}):
        return _validate_execution_evidence_doc(finalize_data, project_dir)
    return _validate_execution_evidence_code(
        finalize_data,
        project_dir,
        plan_dir=plan_dir,
        artifact_prefix=artifact_prefix,
    )


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
) -> dict[str, Any]:
    findings: list[str] = []
    files_claimed = sorted(
        {
            _normalize_repo_path(path, project_dir)
            for task in finalize_data.get("tasks", [])
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
        }

    files_in_diff_set, status_error = _collect_git_status_paths_with_nested_repos(
        project_dir,
        claimed_paths=set(files_claimed),
        # Chain milestones commit their work before review, leaving a clean
        # working tree; a status-only check would falsely report every committed
        # file as a phantom claim ("implementation not present in the diff").
        # Include the committed milestone range so committed work counts.
        include_committed=True,
    )
    if status_error is not None:
        return {
            "findings": findings,
            "files_in_diff": [],
            "files_claimed": files_claimed,
            "skipped": True,
            "reason": status_error,
        }

    files_in_diff = sorted(
        path for path in files_in_diff_set if not _is_runtime_artifact_path(path)
    )
    claimed_set = set(files_claimed)
    diff_set = set(files_in_diff)

    dir_prefixes = [path for path in diff_set if path.endswith("/")]

    def _covered_by_diff(claimed: str) -> bool:
        if claimed in diff_set:
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

    unclaimed_changes = sorted(
        diff_path for diff_path in diff_set
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
    for task in finalize_data.get("tasks", []):
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
        "files_claimed": files_claimed,
        "skipped": False,
        "reason": "",
    }
