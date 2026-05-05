from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from megaplan.schemas import Plan
from megaplan.store import FileStore, PlanRepository
from megaplan._core.io import orphan_plans_root


FIXTURE_ROOT = Path("arnold-source/.megaplan/plans")


def _copy_fixture(tmp_path: Path, name: str) -> Path:
    source = FIXTURE_ROOT / name
    if not source.exists():
        pytest.skip(f"arnold-source fixture missing: {source}")
    target = tmp_path / name
    shutil.copytree(source, target)
    return target


def test_plan_repository_resolves_canonical_orphan_plan_and_lock_path(
    tmp_path: Path,
    monkeypatch,
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))

    project = tmp_path / "project"
    project.mkdir()
    (project / ".git").mkdir()

    plan_dir = orphan_plans_root(project) / "canonical-plan"
    plan_dir.mkdir(parents=True)
    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "name": "canonical-plan",
                "idea": "Keep existing behavior",
                "current_state": "initialized",
                "iteration": 1,
                "created_at": "2026-05-03T00:00:00Z",
                "config": {},
                "sessions": {},
                "plan_versions": [],
                "history": [],
                "meta": {},
                "last_gate": {},
            }
        ),
        encoding="utf-8",
    )

    repo = PlanRepository(project).for_plan("canonical-plan")

    assert repo.plan_dir == plan_dir
    assert repo.working_dir == plan_dir
    assert repo.compatibility_lock_path == plan_dir / ".plan.lock"


def test_plan_repository_round_trips_fixture_bytes_without_layout_changes(tmp_path: Path) -> None:
    plan_dir = _copy_fixture(tmp_path, "sprint-6-images-second-opinion")
    repo = PlanRepository.from_plan_dir(plan_dir)

    before = {name: repo.read_artifact_bytes(name) for name in repo.list_artifact_names()}

    for name, payload in before.items():
        assert payload is not None
        repo.write_artifact_bytes(name, payload)

    after = {name: repo.read_artifact_bytes(name) for name in repo.list_artifact_names()}

    assert after == before
    assert repo.list_artifact_names() == sorted(before)


def test_plan_repository_preserves_lexicographic_execution_batch_order(tmp_path: Path) -> None:
    plan_dir = _copy_fixture(tmp_path, "sprint-1b-discord-resident")
    repo = PlanRepository.from_plan_dir(plan_dir)

    batch_names = [path.name for path in repo.list_execution_batch_artifacts()]

    assert batch_names[:6] == [
        "execution_batch_1.json",
        "execution_batch_10.json",
        "execution_batch_11.json",
        "execution_batch_12.json",
        "execution_batch_13.json",
        "execution_batch_14.json",
    ]
    assert batch_names[-1] == "execution_batch_9.json"
    assert repo.latest_execution_batch_artifact() == plan_dir / "execution_batch_9.json"


def test_plan_repository_load_plan_exposes_hot_state_and_artifact_manifest(tmp_path: Path) -> None:
    plan_dir = _copy_fixture(tmp_path, "sprint-1b-discord-resident")
    repo = PlanRepository.from_plan_dir(plan_dir)

    plan = repo.load_plan()

    assert isinstance(plan, Plan)
    assert plan.id == "sprint-1b-discord-resident"
    assert plan.name == "sprint-1b-discord-resident"
    assert plan.latest_review is not None
    assert plan.latest_execution is not None
    assert repo.compatibility_lock_path.exists()
    assert any(artifact.name == "execution_batch_10.json" and artifact.batch == 10 for artifact in plan.artifacts)


def test_plan_repository_round_trips_latest_failure_and_resume_cursor(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    state = {
        "name": "plan",
        "idea": "idea",
        "current_state": "blocked",
        "iteration": 1,
        "created_at": "2026-05-03T00:00:00Z",
        "config": {},
        "sessions": {},
        "plan_versions": [],
        "history": [],
        "meta": {},
        "last_gate": {},
        "latest_failure": {"kind": "worker_blocked", "message": "quality gates"},
        "resume_cursor": {"phase": "execute", "batch_index": 3},
    }
    (plan_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
    repo = PlanRepository.from_plan_dir(plan_dir)

    plan = repo.load_plan()

    assert plan.latest_failure == {"kind": "worker_blocked", "message": "quality gates"}
    assert plan.resume_cursor == {"phase": "execute", "batch_index": 3}
    repo.save_plan(plan)
    saved = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    assert saved["latest_failure"] == {"kind": "worker_blocked", "message": "quality gates"}
    assert saved["resume_cursor"] == {"phase": "execute", "batch_index": 3}


def test_plan_repository_legacy_state_without_resume_cursor_stays_compatible(tmp_path: Path) -> None:
    plan_dir = tmp_path / "legacy"
    plan_dir.mkdir()
    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "name": "legacy",
                "idea": "idea",
                "current_state": "initialized",
                "iteration": 1,
                "created_at": "2026-05-03T00:00:00Z",
                "config": {},
                "sessions": {},
                "plan_versions": [],
                "history": [{"step": "execute", "result": "failed", "message": "boom"}],
                "meta": {},
                "last_gate": {},
            }
        ),
        encoding="utf-8",
    )
    plan = PlanRepository.from_plan_dir(plan_dir).load_plan()

    assert plan.resume_cursor is None
    assert plan.latest_failure == {"step": "execute", "result": "failed", "message": "boom"}


def test_plan_repository_records_lifecycle_failure_and_resume_cursor(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "name": "plan",
                "idea": "idea",
                "current_state": "finalized",
                "iteration": 1,
                "created_at": "2026-05-03T00:00:00Z",
                "config": {},
                "sessions": {},
                "plan_versions": [],
                "history": [],
                "meta": {},
                "last_gate": {},
            }
        ),
        encoding="utf-8",
    )
    repo = PlanRepository.from_plan_dir(plan_dir)

    failure = repo.record_lifecycle_failure(
        kind="phase_failed",
        message="execute failed",
        current_state="failed",
        phase="execute",
        resume_cursor={"phase": "execute", "retry_strategy": "rerun_phase"},
        last_artifact="execution_batch_1.json",
        suggested_action="retry",
        metadata={"exit_code": 1},
    )

    state = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    assert state["current_state"] == "failed"
    assert state["latest_failure"] == failure
    assert state["latest_failure"]["kind"] == "phase_failed"
    assert state["latest_failure"]["last_artifact"] == "execution_batch_1.json"
    assert state["resume_cursor"] == {"phase": "execute", "retry_strategy": "rerun_phase"}
    assert repo.load_plan().latest_failure["message"] == "execute failed"


def test_plan_repository_lifecycle_failure_appends_progress_for_epic_backed_plan(tmp_path: Path) -> None:
    store = FileStore(tmp_path / "store")
    epic = store.create_epic(title="Epic", goal="Goal", body="Body")
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "name": "plan",
                "idea": "idea",
                "epic_id": epic.id,
                "current_state": "finalized",
                "iteration": 1,
                "created_at": "2026-05-03T00:00:00Z",
                "config": {},
                "sessions": {},
                "plan_versions": [],
                "history": [],
                "meta": {},
                "last_gate": {},
            }
        ),
        encoding="utf-8",
    )

    repo = PlanRepository.from_plan_dir(plan_dir, store=store)
    repo.record_lifecycle_failure(
        kind="execution_blocked",
        message="quality gates blocked execute",
        current_state="blocked",
        phase="execute",
        resume_cursor={"phase": "execute", "retry_strategy": "fresh_session"},
    )

    events = store.list_progress_events(epic_id=epic.id, plan_id="plan")
    assert len(events) == 1
    assert events[0].kind == "execution_blocked"
    assert events[0].details["kind"] == "execution_blocked"


def test_plan_repository_lifecycle_failed_state_appends_plan_failed_progress(tmp_path: Path) -> None:
    store = FileStore(tmp_path / "store")
    epic = store.create_epic(title="Epic", goal="Goal", body="Body")
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "name": "plan",
                "idea": "idea",
                "meta": {"epic_id": epic.id},
                "current_state": "finalized",
                "iteration": 1,
                "created_at": "2026-05-03T00:00:00Z",
                "config": {},
                "sessions": {},
                "plan_versions": [],
                "history": [],
                "last_gate": {},
            }
        ),
        encoding="utf-8",
    )

    repo = PlanRepository.from_plan_dir(plan_dir, store=store)
    failure = repo.record_lifecycle_failure(
        kind="phase_failed",
        message="review failed",
        current_state="failed",
        phase="review",
        resume_cursor={"phase": "review", "retry_strategy": "rerun_phase"},
    )

    events = store.list_progress_events(epic_id=epic.id, plan_id="plan")
    assert len(events) == 1
    assert events[0].kind == "plan_failed"
    assert events[0].summary == "review failed"
    assert events[0].details == failure
