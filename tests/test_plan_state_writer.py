import json
import subprocess
import threading
import time
from pathlib import Path

import pytest

from megaplan._core.state import (
    save_state,
    save_state_merge_meta,
    touch_active_step,
    write_plan_state,
)
from megaplan._pipeline.executor import _merge_state_to_disk
from megaplan._pipeline.resume import ResumeCursor
from megaplan.auto import _clear_orphaned_active_step
from megaplan.bakeoff.merge import _rewrite_project_dir
from megaplan.chain import _mark_blocked_execute_as_executed
from megaplan.store.plan_repository import PlanRepository
from megaplan.types import CliError, STATE_INITIALIZED, STATE_PLANNED
from megaplan.types import STATE_EXECUTED, STATE_FINALIZED


def _state(**overrides):
    state = {
        "name": "p",
        "idea": "i",
        "current_state": STATE_INITIALIZED,
        "iteration": 1,
        "created_at": "2026-01-01T00:00:00Z",
        "config": {"project_dir": "/old"},
        "sessions": {},
        "plan_versions": [],
        "history": [],
        "meta": {},
    }
    state.update(overrides)
    return state


def _read(plan_dir: Path) -> dict:
    return json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))


def test_write_plan_state_rejects_invalid_current_state(tmp_path: Path) -> None:
    with pytest.raises(CliError, match="invalid current_state"):
        write_plan_state(
            tmp_path,
            mode="replace",
            state=_state(current_state="not-a-real-state"),
        )
    assert not (tmp_path / "state.json").exists()


def test_write_plan_state_rejects_invalid_current_state_during_copy_time_rewrite(tmp_path: Path) -> None:
    save_state(tmp_path, _state(config={"project_dir": "/old"}))
    raw = _read(tmp_path)
    raw["current_state"] = "not-a-real-state"
    (tmp_path / "state.json").write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(CliError, match="invalid current_state"):
        _rewrite_project_dir(tmp_path / "state.json", project_dir="/new")

    assert _read(tmp_path)["config"]["project_dir"] == "/old"


def test_write_plan_state_patch_modes_preserve_existing_state(tmp_path: Path) -> None:
    save_state(tmp_path, _state(meta={"a": 1}))

    write_plan_state(tmp_path, mode="patch-key", key="current_state", value=STATE_PLANNED)
    write_plan_state(tmp_path, mode="patch-many", patch={"resume_cursor": {"phase": "execute"}})

    state = _read(tmp_path)
    assert state["current_state"] == STATE_PLANNED
    assert state["meta"] == {"a": 1}
    assert state["resume_cursor"] == {"phase": "execute"}


def test_write_plan_state_patch_many_creates_state_file_on_first_run(tmp_path: Path) -> None:
    write_plan_state(tmp_path, mode="patch-many", patch={"meta": {"created": True}})

    assert _read(tmp_path) == {"meta": {"created": True}, "schema_version": 0}


def test_write_plan_state_executor_key_merge_keeps_unowned_disk_keys(tmp_path: Path) -> None:
    save_state(tmp_path, _state(meta={"disk": True}, current_state=STATE_PLANNED))

    _merge_state_to_disk(
        tmp_path,
        {**_state(), "meta": {"stale": True}, "_pipeline_paused": True},
        executor_owned_keys={"_pipeline_paused"},
    )

    state = _read(tmp_path)
    assert state["current_state"] == STATE_PLANNED
    assert state["meta"] == {"disk": True}
    assert state["_pipeline_paused"] is True


def test_write_plan_state_rejects_corrupt_json_without_renaming_state(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    state_path.write_text("{not valid json", encoding="utf-8")

    with pytest.raises(CliError, match="M3B_HALT_CORRUPT_STATE_WRITE"):
        write_plan_state(tmp_path, mode="patch-many", patch={"meta": {"x": 1}})

    assert state_path.read_text(encoding="utf-8") == "{not valid json"
    assert not list(tmp_path.glob("state.json.corrupt-executor-backup*"))


def test_write_plan_state_rejects_non_object_json_shape(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    state_path.write_text('["not", "an", "object"]', encoding="utf-8")

    with pytest.raises(CliError, match="M3B_HALT_INVALID_STATE_SHAPE"):
        write_plan_state(tmp_path, mode="patch-many", patch={"meta": {"x": 1}})

    assert state_path.read_text(encoding="utf-8") == '["not", "an", "object"]'
    assert not list(tmp_path.glob("state.json.corrupt-executor-backup*"))


def test_executor_merge_backs_up_corrupt_state_before_reraising(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    state_path.write_text("{not valid json", encoding="utf-8")

    with pytest.raises(CliError, match="M3B_HALT_CORRUPT_STATE_WRITE") as excinfo:
        _merge_state_to_disk(tmp_path, _state(), executor_owned_keys={"meta"})

    backup_path = Path(excinfo.value.extra["forensic_backup_path"])
    assert backup_path.parent == tmp_path
    assert backup_path.name == "state.json.corrupt-executor-backup"
    assert backup_path.read_text(encoding="utf-8") == "{not valid json"
    assert state_path.read_text(encoding="utf-8") == "{not valid json"


def test_resume_cursor_save_patches_only_resume_cursor(tmp_path: Path) -> None:
    save_state(tmp_path, _state(meta={"kept": True}, current_state=STATE_PLANNED))

    ResumeCursor(stage="execute", payload={"retry_strategy": "same-worker"}).save(tmp_path)

    state = _read(tmp_path)
    assert state["resume_cursor"] == {
        "phase": "execute",
        "retry_strategy": "same-worker",
    }
    assert state["meta"] == {"kept": True}
    assert state["current_state"] == STATE_PLANNED


def test_plan_repository_save_state_full_replace_semantics(tmp_path: Path) -> None:
    save_state(tmp_path, _state(meta={"old": True}, resume_cursor={"phase": "plan"}))
    replacement = _state(current_state=STATE_PLANNED, meta={"new": True})

    PlanRepository(tmp_path).save_state(replacement)

    state = _read(tmp_path)
    assert state["current_state"] == STATE_PLANNED
    assert state["meta"] == {"new": True}
    assert "resume_cursor" not in state


def test_write_plan_state_merge_meta_list_unions_append_only_fields(tmp_path: Path) -> None:
    save_state(
        tmp_path,
        _state(meta={"notes": [{"timestamp": "2026-01-01T00:00:00Z", "note": "disk"}]}),
    )
    in_memory = _state(
        meta={
            "notes": [
                {"timestamp": "2026-01-01T00:00:00Z", "note": "disk"},
                {"timestamp": "2026-01-01T00:00:01Z", "note": "memory"},
            ]
        }
    )

    save_state_merge_meta(tmp_path, in_memory)

    assert [entry["note"] for entry in _read(tmp_path)["meta"]["notes"]] == ["disk", "memory"]
    assert [entry["note"] for entry in in_memory["meta"]["notes"]] == ["disk", "memory"]


def test_write_plan_state_active_step_heartbeat_only_updates_matching_run(tmp_path: Path) -> None:
    save_state(
        tmp_path,
        _state(
            active_step={
                "phase": "execute",
                "agent": "codex",
                "mode": "fresh",
                "run_id": "r1",
                "last_activity_at": "2026-01-01T00:00:00Z",
                "last_activity_kind": "started",
            }
        ),
    )

    touch_active_step(tmp_path, run_id="other", kind="token", detail="ignored")
    assert _read(tmp_path)["active_step"]["last_activity_kind"] == "started"

    touch_active_step(tmp_path, run_id="r1", kind="token", detail="x" * 600)
    active = _read(tmp_path)["active_step"]
    assert active["phase"] == "execute"
    assert active["agent"] == "codex"
    assert active["mode"] == "fresh"
    assert active["run_id"] == "r1"
    assert active["last_activity_kind"] == "token"
    assert active["last_activity_detail"] == "x" * 500
    assert active["last_activity_at"] != "2026-01-01T00:00:00Z"


def test_write_plan_state_legacy_migration_persists_normalized_state(tmp_path: Path) -> None:
    save_state(tmp_path, _state(current_state="initialized"))
    raw = _read(tmp_path)
    raw["current_state"] = "evaluated"
    raw["last_evaluation"] = {"legacy": True}
    (tmp_path / "state.json").write_text(json.dumps(raw), encoding="utf-8")

    migrated = write_plan_state(tmp_path, mode="legacy-migration")
    assert migrated["current_state"] == "critiqued"
    assert "last_evaluation" not in migrated
    assert migrated["last_gate"] == {}
    assert _read(tmp_path) == migrated


def test_bakeoff_rewrite_project_dir_routes_through_plan_state_writer(tmp_path: Path) -> None:
    save_state(tmp_path, _state(config={"project_dir": "/old", "other": "kept"}))

    _rewrite_project_dir(tmp_path / "state.json", project_dir="/new")

    rewritten = _read(tmp_path)
    assert rewritten["config"]["project_dir"] == "/new"
    assert rewritten["config"]["archived_project_dir"] == "/old"
    assert rewritten["config"]["other"] == "kept"


def test_auto_orphan_recovery_patch_preserves_existing_state(tmp_path: Path) -> None:
    save_state(
        tmp_path,
        _state(
            current_state=STATE_FINALIZED,
            active_step={"step": "execute", "run_id": "r1"},
            meta={"kept": True},
        ),
    )

    assert _clear_orphaned_active_step(tmp_path, "execute") is True

    state = _read(tmp_path)
    assert "active_step" not in state
    assert state["current_state"] == STATE_FINALIZED
    assert state["meta"]["kept"] is True


def test_chain_blocked_execute_recovery_patch_preserves_unrelated_keys(tmp_path: Path) -> None:
    save_state(
        tmp_path,
        _state(
            current_state=STATE_FINALIZED,
            active_step={"step": "execute", "run_id": "r1"},
            latest_failure={"kind": "execute_blocked"},
            resume_cursor={"phase": "execute"},
            meta={"kept": True},
        ),
    )

    _mark_blocked_execute_as_executed(tmp_path)

    state = _read(tmp_path)
    assert state["current_state"] == STATE_EXECUTED
    assert state["meta"] == {"kept": True}
    assert "active_step" not in state
    assert "latest_failure" not in state
    assert "resume_cursor" not in state


def test_concurrent_patch_many_writes_do_not_lose_updates(tmp_path: Path) -> None:
    save_state(tmp_path, _state(meta={}))
    workers = 24
    barrier = threading.Barrier(workers)

    def patch_worker(index: int) -> None:
        barrier.wait()

        def _add_marker(current: dict) -> bool:
            meta = current.setdefault("meta", {})
            assert isinstance(meta, dict)
            markers = meta.setdefault("concurrent_markers", {})
            assert isinstance(markers, dict)
            markers[f"worker-{index}"] = index
            time.sleep(0.005)
            return True

        write_plan_state(tmp_path, mode="patch-many", patch={}, mutation=_add_marker)

    threads = [threading.Thread(target=patch_worker, args=(index,)) for index in range(workers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)
        assert not thread.is_alive()

    markers = _read(tmp_path)["meta"]["concurrent_markers"]
    assert markers == {f"worker-{index}": index for index in range(workers)}


def test_no_direct_production_plan_run_state_writes_regression() -> None:
    repo = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [
            "rg",
            "-n",
            r"state_path\.write_text|\(.*state\.json.*\)\.write_text|atomic_write_json\([^\n]*(state_path|state\.json)",
            "megaplan",
        ],
        cwd=repo,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert result.returncode in {0, 1}, result.stderr
    offenders = []
    allowed = (
        "megaplan/_core/state.py:",
        "megaplan/loop/engine.py:",
        "megaplan/workers/shannon.py:",
        "megaplan/agent/tests/",
    )
    for line in result.stdout.splitlines():
        if line.startswith(allowed):
            continue
        offenders.append(line)
    assert offenders == []
