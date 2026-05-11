from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from megaplan._core import (
    apply_session_update,
    append_history,
    atomic_write_json,
    atomic_write_text,
    batch_artifact_path,
    make_history_entry,
    read_json,
    render_final_md,
    save_state_merge_meta,
    sha256_file,
    is_prose_mode,
    store_raw_worker_output,
)
from megaplan.evaluation import validate_execution_evidence
from megaplan.execute.quality import (
    _check_done_task_evidence,
    _check_done_task_evidence_by_kind,
    _normalize_execute_claimed_path,
)
from megaplan.execute.merge import TERMINAL_TASK_STATUSES, _validate_and_merge_batch
from megaplan.types import CliError, PlanState, STATE_FINALIZED, StepResponse
from megaplan.workers import WorkerResult


def _resolve_execute_approval_mode(
    *, auto_approve: bool, user_approved_gate: bool
) -> str:
    if auto_approve:
        return "auto_approve"
    if user_approved_gate:
        return "user_approved"
    return "manual"


def _reset_timeout_invalid_tasks(
    finalize_data: dict[str, Any],
    *,
    execution_audit: dict[str, Any],
    issues: list[str],
    mode: str = "code",
) -> list[str]:
    reset_reasons: dict[str, list[str]] = {}
    mode_state = {"config": {"mode": mode}}
    def _has_code_task_advisory_evidence(task: dict[str, Any]) -> bool:
        return bool(task.get("commands_run"))

    if is_prose_mode(mode_state):
        missing_task_ids = _check_done_task_evidence(
            finalize_data.get("tasks", []),
            issues=issues,
            should_classify=lambda task: True,
            has_evidence=lambda task: bool(task.get("sections_written")),
            has_advisory_evidence=lambda task: True,
            missing_message="Done tasks missing sections_written during timeout recovery: ",
            advisory_message="",
        )
    else:
        missing_task_ids = _check_done_task_evidence_by_kind(
            finalize_data.get("tasks", []),
            issues=issues,
            should_classify=lambda task: True,
            code_has_advisory=_has_code_task_advisory_evidence,
            code_missing_message="Done tasks missing files_changed, commands_run, evidence_files, and executor_notes during timeout recovery: ",
            code_advisory_message="Advisory: done tasks rely on non-file evidence during timeout recovery: ",
        )
    for task_id in missing_task_ids:
        if is_prose_mode(mode_state):
            reset_reasons.setdefault(task_id, []).append("missing sections_written")
        else:
            reset_reasons.setdefault(task_id, []).append(
                "missing both files_changed and commands_run"
            )

    if not is_prose_mode(mode_state) and not execution_audit.get("skipped"):
        files_in_diff = {
            _normalize_execute_claimed_path(path)
            for path in execution_audit.get("files_in_diff", [])
            if isinstance(path, str) and path.strip()
        }
        for task in finalize_data.get("tasks", []):
            if task.get("status") != "done":
                continue
            claimed_paths = [
                _normalize_execute_claimed_path(path)
                for path in task.get("files_changed", [])
                if isinstance(path, str) and path.strip()
            ]
            if claimed_paths and any(
                path not in files_in_diff for path in claimed_paths
            ):
                reset_reasons.setdefault(task["id"], []).append(
                    "claimed files not present in git status"
                )

    for task in finalize_data.get("tasks", []):
        reasons = reset_reasons.get(task.get("id"))
        if not reasons:
            continue
        note_prefix = str(task.get("executor_notes", "")).strip()
        reset_note = (
            "Timeout recovery reset this task to pending because "
            + " and ".join(reasons)
            + "."
        )
        task["status"] = "pending"
        task["executor_notes"] = f"{note_prefix} {reset_note}".strip()

    if reset_reasons:
        issues.append(
            "Reset timed-out done tasks to pending after evidence validation: "
            + ", ".join(sorted(reset_reasons))
        )
    return sorted(reset_reasons)


def _timeout_checkpoint_path(plan_dir: Path, *, batch_number: int | None) -> Path:
    if batch_number is None:
        return plan_dir / "execution_checkpoint.json"
    return batch_artifact_path(plan_dir, batch_number)


def _merge_timeout_checkpoint(
    *,
    finalize_data: dict[str, Any],
    checkpoint_data: dict[str, Any],
    checkpoint_name: str,
    issues: list[str],
    mode: str = "code",
) -> None:
    tasks_by_id = {
        task["id"]: task
        for task in finalize_data.get("tasks", [])
        if isinstance(task, dict) and isinstance(task.get("id"), str)
    }
    if is_prose_mode({"config": {"mode": mode}}):
        required_fields = ("task_id", "status", "executor_notes", "sections_written")
        merge_fields = ("status", "executor_notes", "sections_written", "stance", "stop_signal")
        array_fields = ("sections_written",)
    else:
        required_fields = ("task_id", "status", "executor_notes", "files_changed", "commands_run")
        merge_fields = ("status", "executor_notes", "files_changed", "commands_run")
        array_fields = ("files_changed", "commands_run")
    merged_tasks, _ = _validate_and_merge_batch(
        checkpoint_data.get("task_updates"),
        required_fields=required_fields,
        targets_by_id=tasks_by_id,
        id_field="task_id",
        merge_fields=merge_fields,
        issues=issues,
        validation_label=f"{checkpoint_name}.task_updates",
        merge_label="checkpoint task_update",
        enum_fields={"status": set(TERMINAL_TASK_STATUSES)},
        nonempty_fields={"executor_notes"},
        array_fields=array_fields,
    )
    sense_checks_by_id = {
        sense_check["id"]: sense_check
        for sense_check in finalize_data.get("sense_checks", [])
        if isinstance(sense_check, dict) and isinstance(sense_check.get("id"), str)
    }
    merged_checks, _ = _validate_and_merge_batch(
        checkpoint_data.get("sense_check_acknowledgments"),
        required_fields=("sense_check_id", "executor_note"),
        targets_by_id=sense_checks_by_id,
        id_field="sense_check_id",
        merge_fields=("executor_note",),
        issues=issues,
        validation_label=f"{checkpoint_name}.sense_check_acknowledgments",
        merge_label="checkpoint sense_check_acknowledgment",
        nonempty_fields={"executor_note"},
    )
    if merged_tasks > 0 or merged_checks > 0:
        issues.append(
            f"Recovered timeout checkpoint from {checkpoint_name}: merged {merged_tasks} task update(s) and {merged_checks} sense check acknowledgment(s)."
        )


def _recover_execute_timeout(
    *,
    plan_dir: Path,
    state: PlanState,
    error: CliError,
    agent: str,
    mode: str,
    refreshed: bool,
    auto_approve: bool,
    args: argparse.Namespace,
    batch_number: int | None,
    persist_state: bool = True,
) -> StepResponse:
    deviations = [f"Execute timed out: {error.message}"]
    finalize_data = read_json(plan_dir / "finalize.json")
    project_dir = Path(state["config"]["project_dir"])
    plan_mode = state["config"].get("mode", "code")
    checkpoint_path = _timeout_checkpoint_path(plan_dir, batch_number=batch_number)
    try:
        checkpoint_data = read_json(checkpoint_path)
    except FileNotFoundError:
        deviations.append(
            f"Advisory: timeout checkpoint {checkpoint_path.name} was not found."
        )
    except json.JSONDecodeError as exc:
        deviations.append(
            f"Advisory: timeout checkpoint {checkpoint_path.name} was not valid JSON: {exc}"
        )
    else:
        if isinstance(checkpoint_data, dict):
            _merge_timeout_checkpoint(
                finalize_data=finalize_data,
                checkpoint_data=checkpoint_data,
                checkpoint_name=checkpoint_path.name,
                issues=deviations,
                mode=plan_mode,
            )
        else:
            deviations.append(
                f"Advisory: timeout checkpoint {checkpoint_path.name} did not contain an object."
            )

    initial_audit = validate_execution_evidence(finalize_data, project_dir, mode=plan_mode, state=state)

    if initial_audit["skipped"]:
        deviations.append(
            f"Advisory audit skip during timeout recovery: {initial_audit['reason']}"
        )
    for finding in initial_audit["findings"]:
        deviations.append(f"Advisory audit finding during timeout recovery: {finding}")

    _reset_timeout_invalid_tasks(
        finalize_data,
        execution_audit=initial_audit,
        issues=deviations,
        mode=plan_mode,
    )
    execution_audit = validate_execution_evidence(finalize_data, project_dir, mode=plan_mode, state=state)
    atomic_write_json(plan_dir / "execution_audit.json", execution_audit)
    atomic_write_json(plan_dir / "finalize.json", finalize_data)
    atomic_write_text(
        plan_dir / "final.md", render_final_md(finalize_data, phase="execute")
    )

    finalize_hash = sha256_file(plan_dir / "finalize.json")
    raw_output = str(error.extra.get("raw_output") or error.message)
    raw_name = store_raw_worker_output(
        plan_dir, "execute", state["iteration"], raw_output
    )
    session_id = error.extra.get("session_id")
    timeout_worker = WorkerResult(
        payload={},
        raw_output=raw_output,
        duration_ms=0,
        cost_usd=0.0,
        session_id=session_id if isinstance(session_id, str) else None,
    )
    if persist_state:
        apply_session_update(
            state,
            "execute",
            agent,
            timeout_worker.session_id,
            mode=mode,
            refreshed=refreshed,
        )
    user_approved_gate = bool(state["meta"].get("user_approved_gate", False))
    approval_mode = _resolve_execute_approval_mode(
        auto_approve=auto_approve,
        user_approved_gate=user_approved_gate,
    )
    if persist_state:
        append_history(
            state,
            make_history_entry(
                "execute",
                duration_ms=0,
                cost_usd=0.0,
                result="timeout",
                worker=timeout_worker,
                agent=agent,
                mode=mode,
                output_file="finalize.json",
                artifact_hash=finalize_hash,
                finalize_hash=finalize_hash,
                raw_output_file=raw_name,
                message=error.message,
                approval_mode=approval_mode,
            ),
        )
        # Execute timeout recovery runs while the execute lock is held; merge
        # meta to avoid clobbering concurrent override appends.
        save_state_merge_meta(plan_dir, state)

    tasks = finalize_data.get("tasks", [])
    completed_tasks = [
        task for task in tasks if task.get("status") in {"done", "skipped"}
    ]
    if is_prose_mode(state):
        files_changed = sorted(
            {
                section
                for task in completed_tasks
                for section in task.get("sections_written", [])
                if isinstance(section, str) and section.strip()
            }
        )
    else:
        files_changed = sorted(
            {
                path
                for task in completed_tasks
                for path in task.get("files_changed", [])
                if isinstance(path, str) and path.strip()
            }
        )
    summary = (
        "Execute timed out after partial progress. "
        f"{len(completed_tasks)}/{len(tasks)} tasks remain marked done or skipped on disk. "
        "Re-run execute to finish and re-emit structured output."
    )
    response: StepResponse = {
        "success": False,
        "step": "execute",
        "summary": summary,
        "artifacts": ["execution_audit.json", "finalize.json", "final.md"],
        "next_step": "execute",
        "state": STATE_FINALIZED,
        "files_changed": files_changed,
        "deviations": deviations,
        "warnings": [summary],
        "auto_approve": auto_approve,
        "user_approved_gate": user_approved_gate,
    }
    return response
