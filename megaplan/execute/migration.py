"""Read-only execute migration diagnostics."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from megaplan.types import (
    EXECUTE_MODEL_LEGACY_BATCH,
    EXECUTE_MODEL_WORKTREE_NATIVE,
    EXECUTE_SCHEMA_VERSION,
)
from megaplan.store import PlanRepository


EXECUTE_DISCOVERY_PATHS: dict[str, tuple[str, ...]] = {
    "execute_status_overlay": ("execution_batch_*.json",),
    "execute_recovery": ("execution_batch_*.json", "execution.json", "finalize.json"),
    "chain_recovery": ("execution_batch_*.json", "finalize.json"),
    "status_overlay": ("execution_batch_*.json", "finalize.json"),
    "auto_liveness": ("execution_batch_*.json",),
    "latest_artifact": ("**/execution_batch_*.json",),
}


def diagnose_legacy_execute(
    plan: str | Path | PlanRepository,
) -> dict[str, Any]:
    """Classify a plan's execute model from on-disk state and artifacts.

    This function intentionally performs no writes. It is used before migration
    mutation paths exist, so old plans must be diagnosable even when their
    ``state.json`` lacks T1 execute markers.
    """

    repo = plan if isinstance(plan, PlanRepository) else PlanRepository.from_plan_dir(plan)
    plan_dir = repo.plan_dir
    state, state_error = _read_json_object(plan_dir / "state.json")
    finalize, finalize_error = _read_json_object(plan_dir / "finalize.json")
    execution, execution_error = _read_json_object(plan_dir / "execution.json")

    top_level_batches = repo.list_top_level_execution_batch_artifacts()
    recursive_batches = repo.list_execution_batch_artifacts()
    batch_summaries = [_summarize_batch(path, plan_dir) for path in recursive_batches]

    config = state.get("config") if isinstance(state, dict) else {}
    if not isinstance(config, dict):
        config = {}
    execute_model = config.get("execute_model")
    execute_schema_version = config.get("execute_schema_version")

    finalize_tasks = _tasks_from_payload(finalize)
    execution_task_records = _task_records_from_execution(execution)
    terminal_finalize_tasks = [
        task
        for task in finalize_tasks
        if task.get("status") in {"done", "skipped", "blocked"}
    ]
    pending_finalize_tasks = [
        task for task in finalize_tasks if task.get("status") == "pending"
    ]

    evidence = {
        "state_marker": bool(execute_model),
        "execution_json": execution is not None,
        "top_level_execution_batches": len(top_level_batches),
        "recursive_execution_batches": len(recursive_batches),
        "finalize_tasks": len(finalize_tasks),
        "terminal_finalize_tasks": len(terminal_finalize_tasks),
        "execution_task_records": len(execution_task_records),
    }
    inferred_model = _infer_execute_model(
        execute_model=execute_model,
        top_level_batch_count=len(top_level_batches),
        recursive_batch_count=len(recursive_batches),
        execution=execution,
        terminal_finalize_task_count=len(terminal_finalize_tasks),
    )
    classification = _classification(execute_model, inferred_model, evidence)

    warnings = _build_warnings(
        plan_dir=plan_dir,
        top_level_batches=top_level_batches,
        recursive_batches=recursive_batches,
        has_execution_json=execution is not None,
        terminal_finalize_count=len(terminal_finalize_tasks),
        read_errors={
            "state.json": state_error,
            "finalize.json": finalize_error,
            "execution.json": execution_error,
            **{
                str(summary["path"]): summary.get("error")
                for summary in batch_summaries
                if summary.get("error")
            },
        },
    )

    return {
        "plan": repo.plan_name,
        "plan_dir": str(plan_dir),
        "read_only": True,
        "execute_model": execute_model,
        "execute_schema_version": execute_schema_version,
        "current_execute_schema_version": EXECUTE_SCHEMA_VERSION,
        "inferred_execute_model": inferred_model,
        "classification": classification,
        "recommended_action": _recommended_action(classification, warnings),
        "counts": {
            "top_level_execution_batches": len(top_level_batches),
            "recursive_execution_batches": len(recursive_batches),
            "nested_execution_batches": max(0, len(recursive_batches) - len(top_level_batches)),
            "finalize_tasks": len(finalize_tasks),
            "finalize_tasks_pending": len(pending_finalize_tasks),
            "finalize_tasks_terminal": len(terminal_finalize_tasks),
            "execution_task_records": len(execution_task_records),
            "warnings": len(warnings),
        },
        "artifacts": {
            "state": "state.json" if state is not None else None,
            "finalize": "finalize.json" if finalize is not None else None,
            "execution": "execution.json" if execution is not None else None,
            "top_level_execution_batches": _relative_paths(top_level_batches, plan_dir),
            "recursive_execution_batches": _relative_paths(recursive_batches, plan_dir),
            "latest_execution_batch": _relative_path(repo.latest_execution_batch_artifact(), plan_dir),
        },
        "discovery_paths": _discovery_report(
            plan_dir=plan_dir,
            top_level_batches=top_level_batches,
            recursive_batches=recursive_batches,
            has_execution_json=execution is not None,
            has_finalize_json=finalize is not None,
            terminal_finalize_count=len(terminal_finalize_tasks),
        ),
        "batch_summaries": batch_summaries,
        "warnings": warnings,
    }


def restart_legacy_execute(
    plan: str | Path | PlanRepository,
    *,
    operator: str | None = None,
) -> dict[str, Any]:
    """Quarantine legacy execute evidence and reset the plan to pre-execute.

    The restart path is explicit and non-destructive: active execute artifacts
    are moved under non-active archive names, the previous finalize payload is
    copied into the archive, and a decision record inventories original
    basenames plus archived hashes.
    """

    repo = plan if isinstance(plan, PlanRepository) else PlanRepository.from_plan_dir(plan)
    before = diagnose_legacy_execute(repo)
    from megaplan.execute.migration_restart import restart_legacy_execute_backend

    return restart_legacy_execute_backend(
        repo,
        operator=operator,
        before_diagnostic=before,
        after_diagnostic_fn=diagnose_legacy_execute,
    )


def close_legacy_execute(
    plan: str | Path | PlanRepository,
    *,
    operator: str | None = None,
) -> dict[str, Any]:
    """Record a terminal close decision for a legacy execute plan."""

    repo = plan if isinstance(plan, PlanRepository) else PlanRepository.from_plan_dir(plan)
    before = diagnose_legacy_execute(repo)
    from megaplan.execute.migration_close import close_legacy_execute_backend

    return close_legacy_execute_backend(
        repo,
        operator=operator,
        before_diagnostic=before,
        after_diagnostic_fn=diagnose_legacy_execute,
    )


def _classification(
    execute_model: Any,
    inferred_model: str | None,
    evidence: dict[str, Any],
) -> str:
    if execute_model == EXECUTE_MODEL_WORKTREE_NATIVE:
        return "worktree_native"
    if execute_model == EXECUTE_MODEL_LEGACY_BATCH:
        return "legacy_batch_marked"
    if inferred_model == EXECUTE_MODEL_LEGACY_BATCH:
        return "legacy_batch_inferred"
    if any(
        evidence[key]
        for key in (
            "execution_json",
            "top_level_execution_batches",
            "recursive_execution_batches",
            "terminal_finalize_tasks",
            "execution_task_records",
        )
    ):
        return "unmarked_execute_evidence"
    return "unmarked_no_execute_evidence"


def _infer_execute_model(
    *,
    execute_model: Any,
    top_level_batch_count: int,
    recursive_batch_count: int,
    execution: dict[str, Any] | None,
    terminal_finalize_task_count: int,
) -> str | None:
    if execute_model in {EXECUTE_MODEL_LEGACY_BATCH, EXECUTE_MODEL_WORKTREE_NATIVE}:
        return str(execute_model)
    if top_level_batch_count or recursive_batch_count:
        return EXECUTE_MODEL_LEGACY_BATCH
    if execution is not None:
        batches = execution.get("batches")
        if isinstance(batches, list):
            return EXECUTE_MODEL_LEGACY_BATCH
    if terminal_finalize_task_count:
        return EXECUTE_MODEL_LEGACY_BATCH
    return None


def _recommended_action(classification: str, warnings: list[dict[str, Any]]) -> str:
    if classification == "worktree_native" and not warnings:
        return "none"
    if classification in {"legacy_batch_marked", "legacy_batch_inferred", "unmarked_execute_evidence"}:
        return "run migrate-plan --diagnose, then choose --restart or --close"
    if warnings:
        return "inspect stale execute artifacts before migration"
    return "no execute migration needed"


def _build_warnings(
    *,
    plan_dir: Path,
    top_level_batches: list[Path],
    recursive_batches: list[Path],
    has_execution_json: bool,
    terminal_finalize_count: int,
    read_errors: dict[str, str | None],
) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    nested_batches = [
        path
        for path in recursive_batches
        if path.parent != plan_dir
    ]
    if top_level_batches:
        warnings.append(
            {
                "code": "stale_top_level_execution_batch_artifacts",
                "severity": "warning",
                "count": len(top_level_batches),
                "paths": _relative_paths(top_level_batches, plan_dir),
                "consumers": [
                    "execute_status_overlay",
                    "execute_recovery",
                    "chain_recovery",
                    "status_overlay",
                    "auto_liveness",
                    "latest_artifact",
                ],
                "message": "Top-level execution_batch_*.json files are still active evidence for execute, status, chain recovery, and auto liveness.",
            }
        )
    if nested_batches:
        warnings.append(
            {
                "code": "stale_recursive_execution_batch_artifacts",
                "severity": "warning",
                "count": len(nested_batches),
                "paths": _relative_paths(nested_batches, plan_dir),
                "consumers": ["latest_artifact"],
                "message": "Nested execution_batch_*.json files remain discoverable by recursive PlanRepository latest-artifact helpers.",
            }
        )
    if has_execution_json:
        warnings.append(
            {
                "code": "stale_execution_json",
                "severity": "warning",
                "count": 1,
                "paths": ["execution.json"],
                "consumers": ["execute_recovery"],
                "message": "execution.json remains active execute recovery evidence.",
            }
        )
    if terminal_finalize_count:
        warnings.append(
            {
                "code": "stale_finalize_task_status_evidence",
                "severity": "warning",
                "count": terminal_finalize_count,
                "paths": ["finalize.json"],
                "consumers": ["execute_recovery", "chain_recovery", "status_overlay"],
                "message": "finalize.json contains terminal task statuses that active status and recovery paths can still consume.",
            }
        )
    for path, error in sorted(read_errors.items()):
        if not error:
            continue
        warnings.append(
            {
                "code": "artifact_read_error",
                "severity": "warning",
                "count": 1,
                "paths": [path],
                "consumers": [],
                "message": error,
            }
        )
    return warnings


def _discovery_report(
    *,
    plan_dir: Path,
    top_level_batches: list[Path],
    recursive_batches: list[Path],
    has_execution_json: bool,
    has_finalize_json: bool,
    terminal_finalize_count: int,
) -> dict[str, dict[str, Any]]:
    top_level_batch_paths = _relative_paths(top_level_batches, plan_dir)
    recursive_batch_paths = _relative_paths(recursive_batches, plan_dir)
    finalize_paths = ["finalize.json"] if has_finalize_json and terminal_finalize_count else []
    execution_paths = ["execution.json"] if has_execution_json else []
    return {
        "execute_status_overlay": {
            "active": bool(top_level_batches),
            "paths": top_level_batch_paths,
        },
        "execute_recovery": {
            "active": bool(top_level_batches or execution_paths or finalize_paths),
            "paths": [*top_level_batch_paths, *execution_paths, *finalize_paths],
        },
        "chain_recovery": {
            "active": bool(top_level_batches or finalize_paths),
            "paths": [*top_level_batch_paths, *finalize_paths],
        },
        "status_overlay": {
            "active": bool(top_level_batches or finalize_paths),
            "paths": [*top_level_batch_paths, *finalize_paths],
        },
        "auto_liveness": {
            "active": bool(top_level_batches),
            "paths": top_level_batch_paths,
        },
        "latest_artifact": {
            "active": bool(recursive_batches),
            "paths": recursive_batch_paths,
        },
    }


def _summarize_batch(path: Path, plan_dir: Path) -> dict[str, Any]:
    payload, error = _read_json_object(path)
    task_records = _task_records_from_batch(payload)
    status_counts: dict[str, int] = {}
    for record in task_records:
        status = record.get("status")
        if isinstance(status, str) and status:
            status_counts[status] = status_counts.get(status, 0) + 1
    summary: dict[str, Any] = {
        "path": _relative_path(path, plan_dir),
        "task_records": len(task_records),
        "status_counts": status_counts,
    }
    if error:
        summary["error"] = error
    return summary


def _task_records_from_batch(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    records: list[dict[str, Any]] = []
    for key in ("task_updates", "tasks"):
        raw = payload.get(key)
        if isinstance(raw, list):
            records.extend(item for item in raw if isinstance(item, dict))
    return records


def _task_records_from_execution(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    records: list[dict[str, Any]] = []
    for key in ("task_updates", "tasks"):
        raw = payload.get(key)
        if isinstance(raw, list):
            records.extend(item for item in raw if isinstance(item, dict))
    batches = payload.get("batches")
    if isinstance(batches, list):
        for batch in batches:
            if isinstance(batch, dict):
                records.extend(_task_records_from_batch(batch))
    return records


def _tasks_from_payload(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    tasks = payload.get("tasks")
    if not isinstance(tasks, list):
        return []
    return [task for task in tasks if isinstance(task, dict)]


def _read_json_object(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    if not path.exists():
        return None, None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return None, f"{path.name} could not be read: {error}"
    if not isinstance(payload, dict):
        return None, f"{path.name} payload is not a JSON object"
    return payload, None


def _relative_paths(paths: list[Path], plan_dir: Path) -> list[str]:
    return [
        value
        for value in (_relative_path(path, plan_dir) for path in paths)
        if value is not None
    ]


def _relative_path(path: Path | None, plan_dir: Path) -> str | None:
    if path is None:
        return None
    try:
        return path.relative_to(plan_dir).as_posix()
    except ValueError:
        return path.as_posix()
