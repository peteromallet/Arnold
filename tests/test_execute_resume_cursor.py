from __future__ import annotations

import json

import pytest

from megaplan.execute_resume_cursor import (
    TASK_WORKTREE_RETRY_STRATEGY,
    build_task_resume_cursor,
    validate_worktree_native_resume_cursor,
)
from megaplan._core.workflow import resume_plan
from megaplan.store import PlanRepository
from megaplan.types import CliError, EXECUTE_MODEL_WORKTREE_NATIVE
from megaplan.worktrees import append_registry_entry, make_task_identity


def _finalize_data() -> dict:
    return {
        "tasks": [
            {"id": "T1", "status": "done"},
            {"id": "path/$(bad)\nTrailer: nope", "status": "pending"},
        ]
    }


def test_task_resume_cursor_contains_task_identity_metadata() -> None:
    task_id = "path/$(bad)\nTrailer: nope"
    identity = make_task_identity(task_id)

    cursor = build_task_resume_cursor(_finalize_data(), task_id)

    assert cursor == {
        "phase": "execute",
        "task_id": task_id,
        "task_key": identity.task_key,
        "task_id_encoded": identity.original_task_id_encoded,
        "task_id_encoding": identity.trailer_encoding,
        "trailer_encoding_version": identity.trailer_encoding,
        "cursor_schema_version": 1,
        "retry_strategy": TASK_WORKTREE_RETRY_STRATEGY,
    }
    assert "/" not in cursor["task_key"]
    assert "\n" not in cursor["task_key"]


def test_task_resume_cursor_validation_rejects_legacy_batch_index() -> None:
    with pytest.raises(CliError) as excinfo:
        validate_worktree_native_resume_cursor(
            {
                "phase": "execute",
                "batch_index": 2,
                "retry_strategy": "fresh_session",
            },
            finalize_data=_finalize_data(),
        )

    assert excinfo.value.code == "legacy_execute_migration_required"
    assert "migrate-plan --diagnose" in str(excinfo.value)


def test_task_resume_cursor_validation_checks_finalize_identity() -> None:
    cursor = build_task_resume_cursor(_finalize_data(), "T1")
    cursor["task_key"] = make_task_identity("T2").task_key

    with pytest.raises(CliError) as excinfo:
        validate_worktree_native_resume_cursor(cursor, finalize_data=_finalize_data())

    assert excinfo.value.code == "invalid_resume_cursor"
    assert "task_key" in str(excinfo.value)


def test_task_resume_cursor_validation_checks_registry_identity(tmp_path) -> None:
    project_dir = tmp_path / "repo"
    project_dir.mkdir()
    task_id = "T1"
    cursor = build_task_resume_cursor(_finalize_data(), task_id)
    registry_entry = append_registry_entry(
        project_dir,
        "run-1",
        "started",
        {"worktree": "ok"},
        identity=make_task_identity(task_id),
    )
    validate_worktree_native_resume_cursor(
        cursor,
        finalize_data=_finalize_data(),
        registry_entries=[registry_entry],
    )

    bad_registry_entry = dict(registry_entry)
    bad_registry_entry["identity"] = dict(registry_entry["identity"])
    bad_registry_entry["identity"]["original_task_id_encoded"] = (
        make_task_identity("different").original_task_id_encoded
    )
    with pytest.raises(CliError) as excinfo:
        validate_worktree_native_resume_cursor(
            cursor,
            finalize_data=_finalize_data(),
            registry_entries=[bad_registry_entry],
        )
    assert "registry identity" in str(excinfo.value)


def test_plan_repository_rejects_batch_index_cursor_for_worktree_native_plan(tmp_path) -> None:
    plan_dir = tmp_path / ".megaplan" / "plans" / "demo"
    plan_dir.mkdir(parents=True)
    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "name": "demo",
                "current_state": "finalized",
                "config": {"execute_model": EXECUTE_MODEL_WORKTREE_NATIVE},
            }
        ),
        encoding="utf-8",
    )
    (plan_dir / "finalize.json").write_text(json.dumps(_finalize_data()), encoding="utf-8")

    with pytest.raises(CliError) as excinfo:
        PlanRepository.from_plan_dir(plan_dir).record_lifecycle_failure(
            kind="execution_blocked",
            message="blocked",
            current_state="blocked",
            phase="execute",
            resume_cursor={
                "phase": "execute",
                "batch_index": None,
                "retry_strategy": "fresh_session",
            },
        )

    assert excinfo.value.code == "legacy_execute_migration_required"


def test_resume_plan_rejects_batch_index_cursor_for_worktree_native_plan(tmp_path) -> None:
    plan_dir = tmp_path / ".megaplan" / "plans" / "demo"
    plan_dir.mkdir(parents=True)
    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                    "name": "demo",
                    "idea": "idea",
                    "current_state": "blocked",
                "created_at": "2026-05-22T00:00:00Z",
                "iteration": 1,
                "config": {"execute_model": EXECUTE_MODEL_WORKTREE_NATIVE},
                "sessions": {},
                "plan_versions": [],
                "history": [],
                "meta": {},
                "last_gate": {},
                "resume_cursor": {
                    "phase": "execute",
                    "batch_index": 1,
                    "retry_strategy": "fresh_session",
                },
            }
        ),
        encoding="utf-8",
    )
    (plan_dir / "finalize.json").write_text(json.dumps(_finalize_data()), encoding="utf-8")

    with pytest.raises(CliError) as excinfo:
        resume_plan(tmp_path, "demo", runner=lambda *_args, **_kwargs: (0, "", ""))

    assert excinfo.value.code == "legacy_execute_migration_required"
