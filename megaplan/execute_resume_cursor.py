"""Task-native execute resume cursor helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from megaplan._core.io import read_json
from megaplan.types import (
    CliError,
    EXECUTE_MODEL_WORKTREE_NATIVE,
    PlanState,
)
from megaplan.worktrees import (
    TASK_ID_TRAILER_ENCODING,
    build_task_identity_map,
    make_task_identity,
)

TASK_RESUME_CURSOR_SCHEMA_VERSION = 1
TASK_WORKTREE_RETRY_STRATEGY = "task_worktree"


def build_task_resume_cursor(
    finalize_data: dict[str, Any],
    task_id: str,
    *,
    phase: str = "execute",
) -> dict[str, Any]:
    identity_map = build_task_identity_map(finalize_data.get("tasks", []))
    identity = identity_map.get(task_id)
    if identity is None:
        raise CliError(
            "invalid_resume_cursor",
            f"execute resume cursor task_id {task_id!r} is not present in finalize.json",
        )
    return {
        "phase": phase,
        "task_id": identity.original_task_id,
        "task_key": identity.task_key,
        "task_id_encoded": identity.original_task_id_encoded,
        "task_id_encoding": identity.trailer_encoding,
        "trailer_encoding_version": identity.trailer_encoding,
        "cursor_schema_version": TASK_RESUME_CURSOR_SCHEMA_VERSION,
        "retry_strategy": TASK_WORKTREE_RETRY_STRATEGY,
    }


def build_best_effort_task_resume_cursor(
    plan_dir: Path,
    *,
    task_id: str | None = None,
) -> dict[str, Any]:
    finalize_path = plan_dir / "finalize.json"
    if not finalize_path.exists():
        return {"phase": "execute", "retry_strategy": TASK_WORKTREE_RETRY_STRATEGY}
    finalize_data = read_json(finalize_path)
    selected_task_id = task_id if _finalize_has_task(finalize_data, task_id) else None
    if selected_task_id is None:
        selected_task_id = _first_pending_or_first_task_id(finalize_data)
    if selected_task_id is None:
        return {"phase": "execute", "retry_strategy": TASK_WORKTREE_RETRY_STRATEGY}
    return build_task_resume_cursor(finalize_data, selected_task_id)


def validate_worktree_native_resume_cursor(
    cursor: dict[str, Any],
    *,
    finalize_data: dict[str, Any],
    registry_entries: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if cursor.get("phase") != "execute":
        return cursor
    if "batch_index" in cursor:
        raise CliError(
            "legacy_execute_migration_required",
            "Worktree-native execute resume cursors are task-scoped. Legacy "
            "`batch_index` cursors must be handled through migration diagnostics; "
            "run `megaplan migrate-plan --diagnose <plan>` and choose `--restart` "
            "or `--close` before resuming execute.",
            extra={"resume_cursor": cursor},
        )
    if cursor.get("retry_strategy") != TASK_WORKTREE_RETRY_STRATEGY:
        raise CliError(
            "invalid_resume_cursor",
            "worktree-native execute resume cursors require retry_strategy='task_worktree'",
            extra={"resume_cursor": cursor},
        )
    task_id = cursor.get("task_id")
    if not isinstance(task_id, str) or not task_id:
        raise CliError(
            "invalid_resume_cursor",
            "worktree-native execute resume cursors require task_id",
            extra={"resume_cursor": cursor},
        )
    expected = make_task_identity(task_id)
    identity_map = build_task_identity_map(finalize_data.get("tasks", []))
    finalize_identity = identity_map.get(task_id)
    if finalize_identity is None:
        raise CliError(
            "invalid_resume_cursor",
            f"resume cursor task_id {task_id!r} is not present in finalize.json",
            extra={"resume_cursor": cursor},
        )
    if expected.task_key != finalize_identity.task_key:
        raise CliError(
            "invalid_resume_cursor",
            "resume cursor task identity does not match finalize-derived identity",
            extra={"resume_cursor": cursor},
        )
    if cursor.get("task_key") != expected.task_key:
        raise CliError(
            "invalid_resume_cursor",
            "resume cursor task_key does not match task_id",
            extra={"resume_cursor": cursor},
        )
    if cursor.get("task_id_encoding") != TASK_ID_TRAILER_ENCODING:
        raise CliError(
            "invalid_resume_cursor",
            "resume cursor task_id_encoding is unsupported",
            extra={"resume_cursor": cursor},
        )
    if cursor.get("trailer_encoding_version") != TASK_ID_TRAILER_ENCODING:
        raise CliError(
            "invalid_resume_cursor",
            "resume cursor trailer_encoding_version is unsupported",
            extra={"resume_cursor": cursor},
        )
    if cursor.get("task_id_encoded") != expected.original_task_id_encoded:
        raise CliError(
            "invalid_resume_cursor",
            "resume cursor encoded task id does not match task_id",
            extra={"resume_cursor": cursor},
        )
    if registry_entries is not None:
        _validate_registry_identity(cursor, registry_entries)
    return cursor


def validate_state_resume_cursor(plan_dir: Path, state: PlanState) -> None:
    cursor = state.get("resume_cursor")
    if not isinstance(cursor, dict):
        return
    config = state.get("config") if isinstance(state.get("config"), dict) else {}
    if (
        config.get("execute_model") == EXECUTE_MODEL_WORKTREE_NATIVE
        and cursor.get("phase") == "execute"
    ):
        finalize_path = plan_dir / "finalize.json"
        finalize_data = read_json(finalize_path) if finalize_path.exists() else {}
        validate_worktree_native_resume_cursor(cursor, finalize_data=finalize_data)


def _validate_registry_identity(
    cursor: dict[str, Any],
    registry_entries: list[dict[str, Any]],
) -> None:
    matching = [
        entry for entry in registry_entries
        if entry.get("task_key") == cursor.get("task_key")
    ]
    if not matching:
        return
    for entry in matching:
        identity = entry.get("identity")
        if not isinstance(identity, dict):
            continue
        if identity.get("task_key") != cursor.get("task_key"):
            raise CliError(
                "invalid_resume_cursor",
                "resume cursor task_key conflicts with registry identity metadata",
                extra={"resume_cursor": cursor},
            )
        if identity.get("original_task_id_encoded") != cursor.get("task_id_encoded"):
            raise CliError(
                "invalid_resume_cursor",
                "resume cursor task_id_encoded conflicts with registry identity metadata",
                extra={"resume_cursor": cursor},
            )
        if identity.get("original_task_id_encoding") != cursor.get("task_id_encoding"):
            raise CliError(
                "invalid_resume_cursor",
                "resume cursor task_id_encoding conflicts with registry identity metadata",
                extra={"resume_cursor": cursor},
            )


def _finalize_has_task(finalize_data: dict[str, Any], task_id: str | None) -> bool:
    if not isinstance(task_id, str) or not task_id:
        return False
    return any(
        isinstance(task, dict) and task.get("id") == task_id
        for task in finalize_data.get("tasks", []) or []
    )


def _first_pending_or_first_task_id(finalize_data: dict[str, Any]) -> str | None:
    tasks = [task for task in finalize_data.get("tasks", []) or [] if isinstance(task, dict)]
    for task in tasks:
        task_id = task.get("id")
        if isinstance(task_id, str) and task.get("status") != "done":
            return task_id
    for task in tasks:
        task_id = task.get("id")
        if isinstance(task_id, str):
            return task_id
    return None
