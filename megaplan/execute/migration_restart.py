"""Non-destructive execute restart quarantine helpers."""

from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from megaplan._core import atomic_write_json, now_utc
from megaplan.store import PlanRepository
from megaplan.types import (
    EXECUTE_MODEL_LEGACY_BATCH,
    EXECUTE_SCHEMA_VERSION,
    STATE_FINALIZED,
)


EXECUTE_STATE_TASK_FIELDS = {
    "auto_attributed_files",
    "commands_run",
    "evidence_files",
    "executor_notes",
    "files_changed",
    "reviewer_verdict",
    "sections_written",
    "stance",
    "stance_violations",
    "stop_signal",
}
TOP_LEVEL_EXECUTE_ARTIFACTS = (
    "execution.json",
    "execution_audit.json",
    "execution_checkpoint.json",
    "execution_trace.jsonl",
)


def restart_legacy_execute_backend(
    repo: PlanRepository,
    *,
    operator: str | None,
    before_diagnostic: dict[str, Any],
    after_diagnostic_fn,
) -> dict[str, Any]:
    plan_dir = repo.plan_dir
    state = repo.load_state()
    finalize = repo.read_artifact_json("finalize.json")
    decision_id = _decision_id()
    archive_dir = plan_dir / "migration_decisions" / decision_id
    archive_dir.mkdir(parents=True, exist_ok=False)

    inventory: list[dict[str, Any]] = []
    for path in _active_execute_artifacts(repo):
        inventory.append(_archive_file(plan_dir, archive_dir, path))

    finalize_snapshot: dict[str, Any] | None = None
    if isinstance(finalize, dict):
        snapshot_path = archive_dir / "finalize-before-restart.payload.json"
        atomic_write_json(snapshot_path, finalize)
        finalize_snapshot = _inventory_entry(
            plan_dir,
            snapshot_path,
            original_path=plan_dir / "finalize.json",
            artifact_role="finalize_snapshot",
            action="copied",
        )
        inventory.append(finalize_snapshot)
        reset_finalize = _reset_finalize_for_restart(finalize)
        atomic_write_json(plan_dir / "finalize.json", reset_finalize)

    state_before = _json_clone(state)
    state_after = _reset_state_for_restart(
        state,
        decision_id=decision_id,
        decision_record=f"migration_decisions/{decision_id}.json",
        operator=operator or _default_operator(),
    )
    atomic_write_json(plan_dir / "state.json", state_after)

    after_diagnostic = after_diagnostic_fn(repo)
    decision_record = {
        "id": decision_id,
        "action": "restart",
        "timestamp": now_utc(),
        "operator": operator or _default_operator(),
        "plan": repo.plan_name,
        "plan_dir": str(plan_dir),
        "before_diagnostic": before_diagnostic,
        "after_diagnostic": after_diagnostic,
        "state": {
            "before": state_before,
            "after": state_after,
        },
        "inventory": inventory,
        "archive_dir": archive_dir.relative_to(plan_dir).as_posix(),
        "active_discovery_clean": _active_discovery_clean(after_diagnostic),
    }
    decision_path = plan_dir / "migration_decisions" / f"{decision_id}.json"
    atomic_write_json(decision_path, decision_record)

    result = {
        "success": True,
        "action": "restart",
        "plan": repo.plan_name,
        "decision_id": decision_id,
        "decision_record": decision_path.relative_to(plan_dir).as_posix(),
        "archive_dir": archive_dir.relative_to(plan_dir).as_posix(),
        "inventory": inventory,
        "active_discovery_clean": decision_record["active_discovery_clean"],
        "before_diagnostic": before_diagnostic,
        "after_diagnostic": after_diagnostic,
        "state": state_after["current_state"],
    }
    return result


def _active_execute_artifacts(repo: PlanRepository) -> list[Path]:
    plan_dir = repo.plan_dir
    artifacts: list[Path] = []
    artifacts.extend(repo.list_execution_batch_artifacts())
    for name in TOP_LEVEL_EXECUTE_ARTIFACTS:
        path = plan_dir / name
        if path.exists() and path.is_file():
            artifacts.append(path)
    return sorted(set(artifacts), key=lambda path: path.relative_to(plan_dir).as_posix())


def _archive_file(plan_dir: Path, archive_dir: Path, source: Path) -> dict[str, Any]:
    relative = source.relative_to(plan_dir).as_posix()
    destination = _archive_destination(archive_dir, relative)
    destination.parent.mkdir(parents=True, exist_ok=True)
    source.replace(destination)
    return _inventory_entry(
        plan_dir,
        destination,
        original_path=plan_dir / relative,
        artifact_role=_artifact_role_for_name(source.name),
        action="moved",
    )


def _archive_destination(archive_dir: Path, relative_source: str) -> Path:
    safe_stem = (
        relative_source.replace("/", "__")
        .replace("\\", "__")
        .replace("execution_batch_", "batch-")
        .replace("execution", "execute")
        .replace("finalize", "final")
    )
    destination = archive_dir / "artifacts" / f"{safe_stem}.payload"
    if destination.exists():
        index = 2
        while True:
            candidate = archive_dir / "artifacts" / f"{safe_stem}.{index}.payload"
            if not candidate.exists():
                return candidate
            index += 1
    return destination


def _inventory_entry(
    plan_dir: Path,
    archived_path: Path,
    *,
    original_path: Path,
    artifact_role: str,
    action: str,
) -> dict[str, Any]:
    return {
        "action": action,
        "artifact_role": artifact_role,
        "original_path": original_path.relative_to(plan_dir).as_posix(),
        "original_basename": original_path.name,
        "archived_path": archived_path.relative_to(plan_dir).as_posix(),
        "sha256": _sha256_file_bytes(archived_path),
        "size_bytes": archived_path.stat().st_size,
    }


def _artifact_role_for_name(name: str) -> str:
    if name.startswith("execution_batch_"):
        return "execution_batch"
    if name == "execution.json":
        return "execution"
    if name == "execution_audit.json":
        return "execution_audit"
    if name == "execution_checkpoint.json":
        return "execution_checkpoint"
    if name == "execution_trace.jsonl":
        return "execution_trace"
    return "execute_artifact"


def _reset_finalize_for_restart(finalize: dict[str, Any]) -> dict[str, Any]:
    reset = _json_clone(finalize)
    tasks = reset.get("tasks")
    if isinstance(tasks, list):
        for task in tasks:
            if not isinstance(task, dict):
                continue
            task["status"] = "pending"
            for field in EXECUTE_STATE_TASK_FIELDS:
                task.pop(field, None)
    for key in ("execution", "execution_summary", "task_updates"):
        reset.pop(key, None)
    reset.setdefault("meta", {})
    if isinstance(reset["meta"], dict):
        reset["meta"]["execute_restart_reset_at"] = now_utc()
    return reset


def _reset_state_for_restart(
    state: dict[str, Any],
    *,
    decision_id: str,
    decision_record: str,
    operator: str,
) -> dict[str, Any]:
    reset = _json_clone(state)
    reset["current_state"] = STATE_FINALIZED
    reset.pop("active_step", None)
    reset.pop("latest_failure", None)
    reset.pop("resume_cursor", None)
    config = reset.setdefault("config", {})
    if isinstance(config, dict):
        config["execute_model"] = EXECUTE_MODEL_LEGACY_BATCH
        config["execute_schema_version"] = EXECUTE_SCHEMA_VERSION
    meta = reset.setdefault("meta", {})
    if isinstance(meta, dict):
        meta["execute_migration"] = {
            "last_restart_decision_id": decision_id,
            "last_restart_decision_record": decision_record,
            "last_restart_operator": operator,
            "last_restart_at": now_utc(),
        }
    return reset


def _active_discovery_clean(diagnostic: dict[str, Any]) -> bool:
    discovery = diagnostic.get("discovery_paths")
    if not isinstance(discovery, dict):
        return False
    return all(
        not item.get("active")
        for item in discovery.values()
        if isinstance(item, dict)
    )


def _sha256_file_bytes(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _json_clone(value: Any) -> Any:
    import copy

    return copy.deepcopy(value)


def _decision_id() -> str:
    stamp = (
        datetime.now(timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
        .replace(":", "")
        .replace("-", "")
        .replace(".", "")
        .replace("Z", "")
    )
    return f"restart-{stamp}"


def _default_operator() -> str:
    for key in ("MEGAPLAN_ACTOR_ID", "USER", "LOGNAME"):
        value = os.environ.get(key)
        if value:
            return value
    return "unknown"
