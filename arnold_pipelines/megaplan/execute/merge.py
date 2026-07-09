from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, Callable

from arnold_pipelines.megaplan._core import (
    atomic_write_text,
    is_creative_mode,
    is_prose_mode,
    list_batch_artifacts,
    read_json,
    render_final_md,
)
from arnold_pipelines.megaplan.store import write_plan_artifact_json
from arnold_pipelines.megaplan.forms.stance import validate_stance
from arnold_pipelines.megaplan.types import PlanState
from arnold_pipelines.megaplan.execute.status_constants import (
    EXECUTE_TASK_STATUS_ALIASES,
    TERMINAL_TASK_STATUSES,
)


# Common field name aliases that models use instead of the canonical names.
# Models often use finalize.json's field names (e.g. "id") instead of the
# execute schema's names (e.g. "task_id").
_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "task_id": ("id", "taskId", "task"),
    "sense_check_id": ("id", "senseCheckId", "check_id"),
    "executor_notes": ("notes", "executor_note", "note"),
    "executor_note": ("notes", "executor_notes", "note"),
    "concern": ("summary", "description", "issue", "finding"),
    "evidence": ("detail", "details", "explanation", "reasoning"),
}


# Normalize enum values to canonical forms — sourced from the shared
# status_constants module so merge-time aliasing and capture pre-processing
# (model_seam / batch) use the same single source of truth.
_VALUE_ALIASES: dict[str, dict[str, str]] = {
    "status": dict(EXECUTE_TASK_STATUS_ALIASES),
}


_DEVIATION_BLOCKING_PHRASES: tuple[str, ...] = (
    "patch artifact",
    "patch_artifact",
    "patch_corruption",
    "budget exhausted",
    "iteration budget",
    "context budget",
    "out of context",
    # Deliberately do not keyword-match "syntax error"/"syntaxerror" in prose:
    # a task may describe a syntax error it already fixed. Real current Python
    # syntax failures are caught by _validate_python_file_for_task below.
)


def _append_executor_note(task: dict[str, Any], note: str) -> None:
    existing = task.get("executor_notes")
    if isinstance(existing, str) and existing:
        task["executor_notes"] = f"{existing}\n{note}"
    else:
        task["executor_notes"] = note


def _is_blocking_deviation(deviation: str) -> str | None:
    normalized = deviation.casefold()
    for phrase in _DEVIATION_BLOCKING_PHRASES:
        if phrase in normalized:
            return phrase
    if "correctness" in normalized and "failed" in normalized:
        return "correctness failed"
    if "unfinished" in normalized and "task" in normalized:
        return "unfinished task"
    return None


def _task_deviation_strings(task: dict[str, Any], issues: list[str]) -> list[str]:
    task_deviations = [
        deviation
        for deviation in task.get("deviations", [])
        if isinstance(deviation, str)
    ]
    task_id = task.get("id")
    if not isinstance(task_id, str) or not task_id:
        return task_deviations
    return task_deviations + [
        deviation
        for deviation in issues
        if isinstance(deviation, str) and task_id in deviation
    ]


def _validate_python_file_for_task(task: dict[str, Any], issues: list[str]) -> None:
    for file_name in task.get("files_changed", []) or []:
        if not isinstance(file_name, str) or not file_name.endswith(".py"):
            continue
        path = Path(file_name)
        if not path.exists():
            continue
        try:
            content = path.read_text(encoding="utf-8")
            ast.parse(content, filename=str(path))
        except UnicodeDecodeError:
            message = f"patch_corruption: {file_name}: file not valid UTF-8"
        except SyntaxError as exc:
            line = exc.lineno or "unknown"
            message = f"patch_corruption: {file_name} line {line}: {exc.msg}"
        else:
            continue
        task["status"] = "blocked"
        _append_executor_note(task, f"[harness] {message}")
        issues.append(message)


def _apply_task_update_guardrails(
    entries: list[dict[str, Any]],
    *,
    targets_by_id: dict[str, dict[str, Any]],
    id_field: str,
    merge_fields: tuple[str, ...],
    issues: list[str],
) -> None:
    if id_field != "task_id" or "files_changed" not in merge_fields:
        return
    task_ids = {
        entry[id_field]
        for entry in entries
        if isinstance(entry.get(id_field), str)
    }
    for task_id in task_ids:
        task = targets_by_id.get(task_id)
        if task is None:
            continue
        _validate_python_file_for_task(task, issues)
    for task_id in task_ids:
        task = targets_by_id.get(task_id)
        if task is None or task.get("status") not in {"done", "blocked"}:
            continue
        for deviation in _task_deviation_strings(task, issues):
            matched = _is_blocking_deviation(deviation)
            if matched is None:
                continue
            task["status"] = "blocked"
            _append_executor_note(
                task,
                f"[harness] status auto-downgraded: deviation contains {matched}",
            )
            break


def _normalize_field_aliases(entry: dict[str, Any], required_fields: tuple[str, ...]) -> dict[str, Any]:
    """Copy aliased field values to canonical names if the canonical name is missing,
    and normalize enum value synonyms."""
    for field in required_fields:
        if field in entry:
            continue
        aliases = _FIELD_ALIASES.get(field, ())
        for alias in aliases:
            if alias in entry:
                entry[field] = entry[alias]
                break
    # Default missing array fields to [] and missing string fields to ""
    # rather than rejecting. Models often omit empty arrays/strings.
    for field in required_fields:
        if field not in entry:
            if field in ("files_changed", "commands_run"):
                entry[field] = []
            elif field in ("executor_notes", "executor_note"):
                entry[field] = "(not provided)"
    # Normalize enum value aliases
    for field, value_map in _VALUE_ALIASES.items():
        if field in entry and isinstance(entry[field], str):
            canonical = value_map.get(entry[field])
            if canonical is not None:
                entry[field] = canonical
    return entry


def _validate_merge_inputs(
    entries: Any,
    *,
    required_fields: tuple[str, ...],
    optional_fields: tuple[str, ...] = (),
    enum_fields: dict[str, set[str]] | None = None,
    nonempty_fields: set[str] | None = None,
    array_fields: tuple[str, ...] = (),
    object_fields: tuple[str, ...] = (),
    deviations: list[str] | None = None,
    label: str,
) -> list[dict[str, Any]]:
    enum_fields = enum_fields or {}
    nonempty_fields = nonempty_fields or set()
    array_field_set = set(array_fields)
    object_field_set = set(object_fields)
    valid_entries: list[dict[str, Any]] = []
    if not isinstance(entries, list):
        return valid_entries
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            if deviations is not None:
                deviations.append(f"Skipped malformed {label}[{index}]: expected object.")
            continue
        # Normalize field aliases before checking required fields
        _normalize_field_aliases(entry, required_fields)
        if any(field not in entry for field in required_fields):
            if deviations is not None:
                deviations.append(f"Skipped malformed {label}[{index}]: missing required keys.")
            continue
        normalized: dict[str, Any] = {}
        malformed = False
        present_optional_fields = tuple(field for field in optional_fields if field in entry)
        for field in (*required_fields, *present_optional_fields):
            value = entry[field]
            if field in array_field_set:
                if not isinstance(value, list):
                    malformed = True
                    break
                normalized[field] = list(value)
                continue
            if field in object_field_set:
                if not isinstance(value, dict):
                    malformed = True
                    break
                normalized[field] = dict(value)
                continue
            if not isinstance(value, str):
                malformed = True
                break
            allowed = enum_fields.get(field)
            if allowed is not None and value not in allowed:
                malformed = True
                break
            normalized[field] = value
        if malformed:
            if deviations is not None:
                deviations.append(f"Skipped malformed {label}[{index}]: invalid field types or enum values.")
            continue
        empty_field = next((field for field in nonempty_fields if normalized.get(field, "").strip() == ""), None)
        if empty_field is not None:
            if deviations is not None:
                deviations.append(f"Skipped {label}[{index}]: '{empty_field}' must not be empty.")
            continue
        valid_entries.append(normalized)
    return valid_entries


def _merge_validated_entries(
    entries: list[dict[str, Any]],
    *,
    targets_by_id: dict[str, dict[str, Any]],
    id_field: str,
    merge_fields: tuple[str, ...],
    issues: list[str],
    label: str,
) -> int:
    """Merge validated entries into targets, deduplicating by ID. Returns unique merge count."""
    seen: set[str] = set()
    for entry in entries:
        entry_id = entry[id_field]
        target = targets_by_id.get(entry_id)
        if target is None:
            issues.append(f"Skipped {label} for unknown {id_field} '{entry_id}'.")
            continue
        if entry_id in seen:
            issues.append(f"Duplicate {label} for '{entry_id}' — last entry wins.")
        for field in merge_fields:
            if field in entry:
                target[field] = entry[field]
        seen.add(entry_id)
    return len(seen)


def _validate_and_merge_batch(
    entries: Any,
    *,
    required_fields: tuple[str, ...],
    optional_fields: tuple[str, ...] = (),
    targets_by_id: dict[str, dict[str, Any]],
    id_field: str,
    merge_fields: tuple[str, ...],
    issues: list[str],
    validation_label: str,
    merge_label: str,
    incomplete_message: Callable[[int, int], str] | None = None,
    enum_fields: dict[str, set[str]] | None = None,
    nonempty_fields: set[str] | None = None,
    array_fields: tuple[str, ...] = (),
    object_fields: tuple[str, ...] = (),
) -> tuple[int, int]:
    valid_entries = _validate_merge_inputs(
        entries,
        required_fields=required_fields,
        optional_fields=optional_fields,
        enum_fields=enum_fields,
        nonempty_fields=nonempty_fields,
        array_fields=array_fields,
        object_fields=object_fields,
        deviations=issues,
        label=validation_label,
    )
    total = len(targets_by_id)
    merged_count = _merge_validated_entries(
        valid_entries,
        targets_by_id=targets_by_id,
        id_field=id_field,
        merge_fields=merge_fields,
        issues=issues,
        label=merge_label,
    )
    _apply_task_update_guardrails(
        valid_entries,
        targets_by_id=targets_by_id,
        id_field=id_field,
        merge_fields=merge_fields,
        issues=issues,
    )
    if incomplete_message is not None and merged_count < total:
        issues.append(incomplete_message(merged_count, total))
    return merged_count, total


def _snapshot_task_statuses(tasks: list[dict[str, Any]]) -> dict[str, str]:
    return {
        task["id"]: str(task.get("status", ""))
        for task in tasks
        if isinstance(task, dict) and isinstance(task.get("id"), str)
    }


def _append_execute_reconciliation_advisories(
    *,
    before_statuses: dict[str, str],
    tasks_by_id: dict[str, dict[str, Any]],
    issues: list[str],
) -> None:
    for task_id, before_status in before_statuses.items():
        after_status = str(tasks_by_id.get(task_id, {}).get("status", ""))
        if before_status not in {"done", "skipped"} or after_status == before_status:
            continue
        issues.append(
            f"Advisory: task {task_id} was {before_status!r} on disk before merge but structured output set it to {after_status!r}. Structured output remains authoritative."
        )


def _merge_batch_results(
    *,
    finalize_data: dict[str, Any],
    payload: dict[str, Any],
    batch_task_ids: list[str],
    batch_sense_check_ids: list[str],
    issues: list[str],
    mode: str = "code",
    state: PlanState | None = None,
) -> tuple[int, int, int, int]:
    batch_task_id_set = set(batch_task_ids)
    batch_sense_check_id_set = set(batch_sense_check_ids)
    pre_merge_statuses = _snapshot_task_statuses(
        [
            task
            for task in finalize_data.get("tasks", [])
            if task.get("id") in batch_task_id_set
        ]
    )
    all_tasks_by_id = {
        task["id"]: task
        for task in finalize_data.get("tasks", [])
        if isinstance(task, dict) and isinstance(task.get("id"), str)
    }
    mode_state = state or {"config": {"mode": mode}}
    creative_mode = is_creative_mode(mode_state)
    if creative_mode and isinstance(payload.get("task_updates"), list):
        for task_update in payload["task_updates"]:
            if not isinstance(task_update, dict) or not isinstance(task_update.get("stance"), dict):
                continue
            violations = validate_stance(task_update["stance"])
            if violations:
                task_update["stance_violations"] = violations
    evidence_context_fields = ("head_sha", "code_hash")
    if is_prose_mode(mode_state):
        required_fields = ("task_id", "status", "executor_notes", "sections_written")
        object_fields: tuple[str, ...] = ()
        optional_fields: tuple[str, ...] = evidence_context_fields
        if is_creative_mode(mode_state):
            required_fields = required_fields + ("stance", "stop_signal")
            object_fields = ("stance", "stop_signal")
            optional_fields = ("stance_violations",) + evidence_context_fields
        merge_fields = (
            "status",
            "executor_notes",
            "sections_written",
            "stance",
            "stop_signal",
            "stance_violations",
        ) + evidence_context_fields
        array_fields = ("sections_written", "stance_violations")
    else:
        required_fields = ("task_id", "status", "executor_notes", "files_changed", "commands_run")
        merge_fields = ("status", "executor_notes", "files_changed", "commands_run") + evidence_context_fields
        array_fields = ("files_changed", "commands_run")
        object_fields = ()
        optional_fields = evidence_context_fields
    merge_targets_by_id = all_tasks_by_id if creative_mode else {
        task_id: task
        for task_id, task in all_tasks_by_id.items()
        if task_id in batch_task_id_set
    }
    merged_count, _ = _validate_and_merge_batch(
        payload.get("task_updates"),
        required_fields=required_fields,
        optional_fields=optional_fields,
        targets_by_id=merge_targets_by_id,
        id_field="task_id",
        merge_fields=merge_fields,
        issues=issues,
        validation_label="task_updates",
        merge_label="task_update",
        incomplete_message=None,
        enum_fields={"status": set(TERMINAL_TASK_STATUSES)},
        nonempty_fields={"executor_notes"},
        array_fields=array_fields,
        object_fields=object_fields,
    )
    # Check batch-specific coverage: how many of THIS batch's tasks got updates?
    # Any terminal status counts as "tracked" — the executor reported back.
    # "blocked" / "completed" specifically used to be left out of this filter,
    # which produced a false "tracking is incomplete" message when the
    # executor legitimately blocked on a user prerequisite.
    total_batch_tasks = len(batch_task_id_set)
    batch_merged = sum(
        1
        for tid in batch_task_id_set
        if all_tasks_by_id.get(tid, {}).get("status") in TERMINAL_TASK_STATUSES
    )
    if batch_merged < total_batch_tasks:
        issues.append(
            f"{total_batch_tasks - batch_merged}/{total_batch_tasks} batch tasks have no executor update — tracking is incomplete."
        )
    # Same for sense checks — accept any valid sense check ID.
    all_sense_checks_by_id = {
        sense_check["id"]: sense_check
        for sense_check in finalize_data.get("sense_checks", [])
        if isinstance(sense_check, dict) and isinstance(sense_check.get("id"), str)
    }
    acknowledged_count, _ = _validate_and_merge_batch(
        payload.get("sense_check_acknowledgments"),
        required_fields=("sense_check_id", "executor_note"),
        targets_by_id=all_sense_checks_by_id,
        id_field="sense_check_id",
        merge_fields=("executor_note",),
        issues=issues,
        validation_label="sense_check_acknowledgments",
        merge_label="sense_check_acknowledgment",
        incomplete_message=None,
        nonempty_fields={"executor_note"},
    )
    total_batch_checks = len(batch_sense_check_id_set)
    batch_acknowledged = sum(
        1
        for sid in batch_sense_check_id_set
        if all_sense_checks_by_id.get(sid, {}).get("executor_note")
    )
    if batch_acknowledged < total_batch_checks:
        issues.append(
            f"{total_batch_checks - batch_acknowledged}/{total_batch_checks} batch sense checks have no executor acknowledgment — tracking is incomplete."
        )
    _append_execute_reconciliation_advisories(
        before_statuses=pre_merge_statuses,
        tasks_by_id=all_tasks_by_id,
        issues=issues,
    )
    return merged_count, total_batch_tasks, acknowledged_count, total_batch_checks


def reconcile_latest_execution_batch(plan_dir: Path, state: PlanState) -> dict[str, Any]:
    """Best-effort merge of the latest execution_batch_N artifact into finalize.json.

    This is used at failure boundaries outside the execute handler, such as a
    chain phase-complete callback failing after an execute subprocess produced
    a checkpoint artifact. It intentionally treats the latest batch payload as
    structured evidence and lets the normal merge validator decide which
    entries are usable.
    """

    artifacts = list_batch_artifacts(plan_dir)
    if not artifacts:
        return {"reconciled": False, "reason": "no execution batch artifacts"}
    latest = artifacts[-1]
    try:
        payload = read_json(latest)
        finalize_data = read_json(plan_dir / "finalize.json")
    except Exception as error:
        return {
            "reconciled": False,
            "artifact": latest.name,
            "reason": f"failed to read checkpoint inputs: {error}",
        }
    if not isinstance(payload, dict) or not isinstance(finalize_data, dict):
        return {
            "reconciled": False,
            "artifact": latest.name,
            "reason": "checkpoint or finalize payload was not an object",
        }

    batch_task_ids = [
        task["id"]
        for task in finalize_data.get("tasks", [])
        if isinstance(task, dict) and isinstance(task.get("id"), str)
    ]
    batch_sense_check_ids = [
        check["id"]
        for check in finalize_data.get("sense_checks", [])
        if isinstance(check, dict) and isinstance(check.get("id"), str)
    ]
    issues: list[str] = []
    merged_count, total_task_count, acknowledged_count, total_check_count = _merge_batch_results(
        finalize_data=finalize_data,
        payload=payload,
        batch_task_ids=batch_task_ids,
        batch_sense_check_ids=batch_sense_check_ids,
        issues=issues,
        mode=state.get("config", {}).get("mode", "code"),
        state=state,
    )
    write_plan_artifact_json(plan_dir, "finalize.json", finalize_data, contract_context=None)
    final_md_error: str | None = None
    try:
        atomic_write_text(
            plan_dir / "final.md", render_final_md(finalize_data, phase="execute")
        )
    except Exception as error:
        final_md_error = str(error)
    return {
        "reconciled": True,
        "artifact": latest.name,
        "merged_task_count": merged_count,
        "total_task_count": total_task_count,
        "acknowledged_sense_check_count": acknowledged_count,
        "total_sense_check_count": total_check_count,
        "issues": issues,
        "final_md_error": final_md_error,
    }
