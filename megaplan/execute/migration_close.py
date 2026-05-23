"""Terminal close migration helpers for legacy execute plans."""

from __future__ import annotations

from typing import Any

from megaplan._core import atomic_write_json, now_utc
from megaplan.store import PlanRepository
from megaplan.types import (
    EXECUTE_MODEL_LEGACY_BATCH,
    EXECUTE_SCHEMA_VERSION,
    STATE_DONE,
)

from .migration_restart import (
    _archive_file,
    _decision_id,
    _default_operator,
    _json_clone,
    _sha256_file_bytes,
)


def close_legacy_execute_backend(
    repo: PlanRepository,
    *,
    operator: str | None,
    before_diagnostic: dict[str, Any],
    after_diagnostic_fn,
) -> dict[str, Any]:
    plan_dir = repo.plan_dir
    state = repo.load_state()
    decision_id = _decision_id().replace("restart-", "close-", 1)
    archive_dir = plan_dir / "migration_decisions" / decision_id
    archive_dir.mkdir(parents=True, exist_ok=False)
    operator_value = operator or _default_operator()

    full_inventory = _artifact_inventory(repo)
    quarantine_inventory = [
        _archive_file(plan_dir, archive_dir, path)
        for path in repo.list_execution_batch_artifacts()
    ]

    state_before = _json_clone(state)
    state_after = _close_state(
        state,
        decision_id=decision_id,
        decision_record=f"migration_decisions/{decision_id}.json",
        operator=operator_value,
    )
    atomic_write_json(plan_dir / "state.json", state_after)

    after_diagnostic = after_diagnostic_fn(repo)
    decision_record = {
        "id": decision_id,
        "action": "close",
        "timestamp": now_utc(),
        "operator": operator_value,
        "plan": repo.plan_name,
        "plan_dir": str(plan_dir),
        "before_diagnostic": before_diagnostic,
        "after_diagnostic": after_diagnostic,
        "state": {
            "before": state_before,
            "after": state_after,
        },
        "artifact_inventory": full_inventory,
        "quarantine_inventory": quarantine_inventory,
        "archive_dir": archive_dir.relative_to(plan_dir).as_posix(),
        "batch_discovery_clean": _batch_discovery_clean(after_diagnostic),
    }
    decision_path = plan_dir / "migration_decisions" / f"{decision_id}.json"
    atomic_write_json(decision_path, decision_record)

    return {
        "success": True,
        "action": "close",
        "plan": repo.plan_name,
        "decision_id": decision_id,
        "decision_record": decision_path.relative_to(plan_dir).as_posix(),
        "archive_dir": archive_dir.relative_to(plan_dir).as_posix(),
        "artifact_inventory": full_inventory,
        "quarantine_inventory": quarantine_inventory,
        "batch_discovery_clean": decision_record["batch_discovery_clean"],
        "before_diagnostic": before_diagnostic,
        "after_diagnostic": after_diagnostic,
        "state": state_after["current_state"],
    }


def _artifact_inventory(repo: PlanRepository) -> list[dict[str, Any]]:
    plan_dir = repo.plan_dir
    inventory: list[dict[str, Any]] = []
    for path in repo.list_artifact_paths():
        inventory.append(
            {
                "path": path.relative_to(plan_dir).as_posix(),
                "basename": path.name,
                "sha256": _sha256_file_bytes(path),
                "size_bytes": path.stat().st_size,
            }
        )
    return inventory


def _close_state(
    state: dict[str, Any],
    *,
    decision_id: str,
    decision_record: str,
    operator: str,
) -> dict[str, Any]:
    closed = _json_clone(state)
    closed["current_state"] = STATE_DONE
    closed.pop("active_step", None)
    closed.pop("latest_failure", None)
    closed.pop("resume_cursor", None)
    config = closed.setdefault("config", {})
    if isinstance(config, dict):
        config["execute_model"] = EXECUTE_MODEL_LEGACY_BATCH
        config["execute_schema_version"] = EXECUTE_SCHEMA_VERSION
    meta = closed.setdefault("meta", {})
    if isinstance(meta, dict):
        meta["execute_migration"] = {
            "last_close_decision_id": decision_id,
            "last_close_decision_record": decision_record,
            "last_close_operator": operator,
            "last_close_at": now_utc(),
        }
    return closed


def _batch_discovery_clean(diagnostic: dict[str, Any]) -> bool:
    artifacts = diagnostic.get("artifacts")
    if not isinstance(artifacts, dict):
        return False
    discovery = diagnostic.get("discovery_paths")
    if not isinstance(discovery, dict):
        return False
    latest = discovery.get("latest_artifact")
    top_level = discovery.get("execute_status_overlay")
    return (
        not artifacts.get("top_level_execution_batches")
        and not artifacts.get("recursive_execution_batches")
        and isinstance(latest, dict)
        and not latest.get("active")
        and isinstance(top_level, dict)
        and not top_level.get("active")
    )
