from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from megaplan._core.io import list_batch_artifacts
from megaplan.execute.migration import (
    close_legacy_execute,
    diagnose_legacy_execute,
    restart_legacy_execute,
)
from megaplan.handlers.execute import _prepare_execute_model_or_refuse
from megaplan.store import PlanRepository
from megaplan.types import (
    CliError,
    EXECUTE_MODEL_LEGACY_BATCH,
    EXECUTE_MODEL_WORKTREE_NATIVE,
    EXECUTE_SCHEMA_VERSION,
    SECRET_SCAN_MODE_PR_PUSHED,
    STATE_DONE,
    STATE_FINALIZED,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _state(*, config: dict | None = None) -> dict:
    return {
        "name": "plan",
        "idea": "idea",
        "current_state": "finalized",
        "iteration": 1,
        "created_at": "2026-05-03T00:00:00Z",
        "config": dict(config or {}),
        "sessions": {},
        "plan_versions": [],
        "history": [],
        "meta": {},
        "last_gate": {},
    }


def _tree_hashes(plan_dir: Path) -> dict[str, str]:
    return {
        path.relative_to(plan_dir).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(plan_dir.rglob("*"))
        if path.is_file()
    }


def test_diagnose_infers_unmarked_legacy_batch_from_artifacts_read_only(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    _write_json(plan_dir / "state.json", _state())
    _write_json(
        plan_dir / "finalize.json",
        {"tasks": [{"id": "T1", "status": "done"}, {"id": "T2", "status": "pending"}]},
    )
    _write_json(
        plan_dir / "execution_batch_1.json",
        {"task_updates": [{"task_id": "T1", "status": "done"}]},
    )
    _write_json(
        plan_dir / "migration_decisions" / "execution_batch_99.json",
        {"task_updates": [{"task_id": "OLD", "status": "done"}]},
    )
    _write_json(
        plan_dir / "execution.json",
        {"batches": [{"task_updates": [{"task_id": "T1", "status": "done"}]}]},
    )
    before_hashes = _tree_hashes(plan_dir)

    diagnostic = diagnose_legacy_execute(plan_dir)

    assert _tree_hashes(plan_dir) == before_hashes
    assert diagnostic["read_only"] is True
    assert diagnostic["execute_model"] is None
    assert diagnostic["inferred_execute_model"] == EXECUTE_MODEL_LEGACY_BATCH
    assert diagnostic["classification"] == "legacy_batch_inferred"
    assert diagnostic["counts"]["top_level_execution_batches"] == 1
    assert diagnostic["counts"]["recursive_execution_batches"] == 2
    assert diagnostic["counts"]["nested_execution_batches"] == 1
    assert diagnostic["counts"]["finalize_tasks_terminal"] == 1
    assert diagnostic["artifacts"]["latest_execution_batch"] == "migration_decisions/execution_batch_99.json"

    warnings = {warning["code"]: warning for warning in diagnostic["warnings"]}
    assert warnings["stale_top_level_execution_batch_artifacts"]["consumers"] == [
        "execute_status_overlay",
        "execute_recovery",
        "chain_recovery",
        "status_overlay",
        "auto_liveness",
        "latest_artifact",
    ]
    assert warnings["stale_recursive_execution_batch_artifacts"]["paths"] == [
        "migration_decisions/execution_batch_99.json"
    ]
    assert warnings["stale_execution_json"]["paths"] == ["execution.json"]
    assert warnings["stale_finalize_task_status_evidence"]["paths"] == ["finalize.json"]

    assert diagnostic["discovery_paths"]["execute_status_overlay"] == {
        "active": True,
        "paths": ["execution_batch_1.json"],
    }
    assert diagnostic["discovery_paths"]["latest_artifact"] == {
        "active": True,
        "paths": ["execution_batch_1.json", "migration_decisions/execution_batch_99.json"],
    }


def test_diagnose_preserves_marked_legacy_classification(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    _write_json(
        plan_dir / "state.json",
        _state(
            config={
                "execute_model": EXECUTE_MODEL_LEGACY_BATCH,
                "execute_schema_version": EXECUTE_SCHEMA_VERSION,
            }
        ),
    )

    diagnostic = diagnose_legacy_execute(PlanRepository.from_plan_dir(plan_dir))

    assert diagnostic["execute_model"] == EXECUTE_MODEL_LEGACY_BATCH
    assert diagnostic["execute_schema_version"] == EXECUTE_SCHEMA_VERSION
    assert diagnostic["inferred_execute_model"] == EXECUTE_MODEL_LEGACY_BATCH
    assert diagnostic["classification"] == "legacy_batch_marked"
    assert diagnostic["counts"]["warnings"] == 0


def test_diagnose_unmarked_plan_without_execute_evidence_has_no_warnings(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    _write_json(plan_dir / "state.json", _state())

    diagnostic = diagnose_legacy_execute(plan_dir)

    assert diagnostic["classification"] == "unmarked_no_execute_evidence"
    assert diagnostic["inferred_execute_model"] is None
    assert diagnostic["recommended_action"] == "no execute migration needed"
    assert diagnostic["counts"]["warnings"] == 0
    assert all(not item["active"] for item in diagnostic["discovery_paths"].values())


def test_diagnose_unmarked_finalized_pending_plan_is_worktree_native_candidate(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    _write_json(plan_dir / "state.json", _state())
    _write_json(
        plan_dir / "finalize.json",
        {"tasks": [{"id": "T1", "status": "pending"}, {"id": "T2", "status": "pending"}]},
    )

    diagnostic = diagnose_legacy_execute(plan_dir)

    assert diagnostic["classification"] == "unmarked_no_execute_evidence"
    assert diagnostic["inferred_execute_model"] is None
    assert diagnostic["counts"]["finalize_tasks"] == 2
    assert diagnostic["counts"]["finalize_tasks_terminal"] == 0
    assert diagnostic["counts"]["warnings"] == 0


def test_execute_start_stamps_unmarked_finalized_pending_plan(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    state = _state()
    _write_json(plan_dir / "state.json", state)
    _write_json(plan_dir / "finalize.json", {"tasks": [{"id": "T1", "status": "pending"}]})

    _prepare_execute_model_or_refuse(plan_dir, state)

    assert state["config"]["execute_model"] == EXECUTE_MODEL_WORKTREE_NATIVE
    assert state["config"]["execute_schema_version"] == EXECUTE_SCHEMA_VERSION
    assert state["config"]["secret_scan_mode"] == SECRET_SCAN_MODE_PR_PUSHED
    assert "max_tasks_per_batch" not in state["config"]


def test_execute_start_refuses_aggregate_only_legacy_execution_json(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    state = _state()
    _write_json(plan_dir / "state.json", state)
    _write_json(plan_dir / "finalize.json", {"tasks": [{"id": "T1", "status": "pending"}]})
    _write_json(plan_dir / "execution.json", {"batches": [{"id": 1}]})

    try:
        _prepare_execute_model_or_refuse(plan_dir, state)
    except CliError as exc:
        assert exc.code == "legacy_execute_migration_required"
        diagnostic = exc.extra["diagnostic"]
    else:
        raise AssertionError("expected legacy execute refusal")

    assert diagnostic["classification"] == "legacy_batch_inferred"
    assert diagnostic["inferred_execute_model"] == EXECUTE_MODEL_LEGACY_BATCH


def test_restart_quarantines_active_execute_artifacts_and_resets_discovery(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    _write_json(
        plan_dir / "state.json",
        {
            **_state(),
            "current_state": "executed",
            "active_step": {"step": "execute"},
            "latest_failure": {"kind": "phase_failed"},
            "resume_cursor": {"phase": "execute"},
        },
    )
    _write_json(
        plan_dir / "finalize.json",
        {
            "tasks": [
                {
                    "id": "T1",
                    "status": "done",
                    "executor_notes": "done",
                    "files_changed": ["app.py"],
                    "commands_run": ["pytest"],
                },
                {"id": "T2", "status": "blocked", "executor_notes": "blocked"},
            ]
        },
    )
    _write_json(
        plan_dir / "execution_batch_1.json",
        {"task_updates": [{"task_id": "T1", "status": "done"}]},
    )
    _write_json(
        plan_dir / "migration_decisions" / "old" / "execution_batch_99.json",
        {"task_updates": [{"task_id": "OLD", "status": "done"}]},
    )
    _write_json(plan_dir / "execution.json", {"batches": [{"id": 1}]})
    _write_json(plan_dir / "execution_audit.json", {"audit": True})
    before = diagnose_legacy_execute(plan_dir)
    assert before["discovery_paths"]["latest_artifact"]["active"] is True

    result = restart_legacy_execute(plan_dir, operator="tester")

    assert result["success"] is True
    assert result["state"] == STATE_FINALIZED
    assert result["active_discovery_clean"] is True
    assert not (plan_dir / "execution.json").exists()
    assert not (plan_dir / "execution_audit.json").exists()
    assert not list(plan_dir.glob("execution_batch_*.json"))
    assert list_batch_artifacts(plan_dir) == []
    assert PlanRepository.from_plan_dir(plan_dir).list_execution_batch_artifacts() == []

    after = diagnose_legacy_execute(plan_dir)
    assert after["classification"] == "legacy_batch_marked"
    assert after["counts"]["recursive_execution_batches"] == 0
    assert after["counts"]["finalize_tasks_terminal"] == 0
    assert after["warnings"] == []
    assert all(not item["active"] for item in after["discovery_paths"].values())

    state = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    assert state["current_state"] == STATE_FINALIZED
    assert state["config"]["execute_model"] == EXECUTE_MODEL_LEGACY_BATCH
    assert state["config"]["execute_schema_version"] == EXECUTE_SCHEMA_VERSION
    assert "active_step" not in state
    assert "latest_failure" not in state
    assert "resume_cursor" not in state
    assert state["meta"]["execute_migration"]["last_restart_operator"] == "tester"

    finalize = json.loads((plan_dir / "finalize.json").read_text(encoding="utf-8"))
    assert [task["status"] for task in finalize["tasks"]] == ["pending", "pending"]
    assert all("executor_notes" not in task for task in finalize["tasks"])
    assert all("files_changed" not in task for task in finalize["tasks"])
    assert all("commands_run" not in task for task in finalize["tasks"])

    decision_path = plan_dir / result["decision_record"]
    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    assert decision["operator"] == "tester"
    assert decision["active_discovery_clean"] is True
    inventory_by_basename = {
        item["original_basename"]: item for item in decision["inventory"]
    }
    assert {
        "execution_batch_1.json",
        "execution_batch_99.json",
        "execution.json",
        "execution_audit.json",
        "finalize.json",
    } <= set(inventory_by_basename)
    for item in decision["inventory"]:
        archived = plan_dir / item["archived_path"]
        assert archived.exists()
        assert item["sha256"] == "sha256:" + hashlib.sha256(archived.read_bytes()).hexdigest()
        assert not re.fullmatch(r"execution_batch_\d+\.json", archived.name)
        assert archived.name not in {"execution.json", "finalize.json"}
    archived_batch = json.loads(
        (plan_dir / inventory_by_basename["execution_batch_1.json"]["archived_path"]).read_text(
            encoding="utf-8"
        )
    )
    archived_finalize = json.loads(
        (plan_dir / inventory_by_basename["finalize.json"]["archived_path"]).read_text(
            encoding="utf-8"
        )
    )
    assert archived_batch["task_updates"] == [{"task_id": "T1", "status": "done"}]
    assert [task["status"] for task in archived_finalize["tasks"]] == ["done", "blocked"]
    assert inventory_by_basename["execution_batch_1.json"]["original_path"] == "execution_batch_1.json"
    assert (
        inventory_by_basename["execution_batch_99.json"]["original_path"]
        == "migration_decisions/old/execution_batch_99.json"
    )


def test_close_records_terminal_decision_without_worktree_semantics_or_execute_launch(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    _write_json(
        plan_dir / "state.json",
        {
            **_state(),
            "active_step": {"step": "execute"},
            "history": [{"step": "plan", "result": "success"}],
        },
    )
    _write_json(
        plan_dir / "finalize.json",
        {"tasks": [{"id": "T1", "status": "done", "executor_notes": "done"}]},
    )
    _write_json(
        plan_dir / "execution_batch_1.json",
        {"task_updates": [{"task_id": "T1", "status": "done"}]},
    )
    _write_json(
        plan_dir / "migration_decisions" / "old" / "execution_batch_9.json",
        {"task_updates": [{"task_id": "OLD", "status": "done"}]},
    )
    _write_json(plan_dir / "execution.json", {"batches": [{"id": 1}]})
    before = diagnose_legacy_execute(plan_dir)
    assert before["discovery_paths"]["latest_artifact"]["active"] is True

    result = close_legacy_execute(plan_dir, operator="closer")

    assert result["success"] is True
    assert result["action"] == "close"
    assert result["state"] == STATE_DONE
    assert result["batch_discovery_clean"] is True
    assert list_batch_artifacts(plan_dir) == []
    assert PlanRepository.from_plan_dir(plan_dir).list_execution_batch_artifacts() == []
    assert (plan_dir / "execution.json").exists()

    state = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    assert state["current_state"] == STATE_DONE
    assert state["config"]["execute_model"] == EXECUTE_MODEL_LEGACY_BATCH
    assert state["config"]["execute_model"] != EXECUTE_MODEL_WORKTREE_NATIVE
    assert state["config"]["execute_schema_version"] == EXECUTE_SCHEMA_VERSION
    assert "active_step" not in state
    assert state["history"] == [{"step": "plan", "result": "success"}]
    assert all(entry.get("step") != "execute" for entry in state["history"])
    assert state["meta"]["execute_migration"]["last_close_operator"] == "closer"

    after = diagnose_legacy_execute(plan_dir)
    assert after["classification"] == "legacy_batch_marked"
    assert after["counts"]["recursive_execution_batches"] == 0
    assert after["discovery_paths"]["latest_artifact"]["active"] is False
    assert after["discovery_paths"]["execute_status_overlay"]["active"] is False

    decision_path = plan_dir / result["decision_record"]
    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    assert decision["action"] == "close"
    assert decision["operator"] == "closer"
    assert decision["batch_discovery_clean"] is True
    inventory = {item["basename"]: item for item in decision["artifact_inventory"]}
    assert {"state.json", "finalize.json", "execution.json", "execution_batch_1.json"} <= set(inventory)
    quarantine = {item["original_basename"]: item for item in decision["quarantine_inventory"]}
    assert set(quarantine) == {"execution_batch_1.json", "execution_batch_9.json"}
    for item in decision["quarantine_inventory"]:
        archived = plan_dir / item["archived_path"]
        assert archived.exists()
        assert item["sha256"] == "sha256:" + hashlib.sha256(archived.read_bytes()).hexdigest()
        assert not re.fullmatch(r"execution_batch_\d+\.json", archived.name)
    archived_nested = json.loads(
        (plan_dir / quarantine["execution_batch_9.json"]["archived_path"]).read_text(
            encoding="utf-8"
        )
    )
    assert archived_nested["task_updates"] == [{"task_id": "OLD", "status": "done"}]
