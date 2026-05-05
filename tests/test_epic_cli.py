from __future__ import annotations

import json
from pathlib import Path

import megaplan.cli
from megaplan.store import MultiStore, deterministic_idempotency_key
from megaplan.store.file import FileStore
from megaplan.types import CliError


def _project(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    project.mkdir()
    (project / ".git").mkdir()
    return project


def _store(tmp_path: Path) -> MultiStore:
    return MultiStore(
        file_store=FileStore(tmp_path / "file"),
        db_store=FileStore(tmp_path / "db"),
        actor_id="actor",
    )


def test_epic_snapshot_writes_offline_json(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    project = _project(tmp_path)
    home = tmp_path / "home"
    home.mkdir()
    store = _store(tmp_path)
    epic = store.create_epic(title="DB Epic", goal="g", body="snapshot body", home_backend="db")
    plan = store.create_plan(
        sprint_id=None,
        epic_id=epic.id,
        name="snapshot-plan",
        idea="snapshot",
        idempotency_key=deterministic_idempotency_key("cli", epic.id, "snapshot-plan"),
    )
    store.write_plan_artifact(
        plan.id,
        "state.json",
        b"{\"offline\": true}\n",
        idempotency_key=deterministic_idempotency_key("cli", plan.id, "snapshot-artifact"),
    )
    monkeypatch.chdir(project)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(megaplan.cli, "build_epic_store", lambda root, actor_id=None: store)

    exit_code = megaplan.cli.main(["epic", "snapshot", epic.id])
    response = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert response["success"] is True
    assert response["action"] == "snapshot"
    snapshot_path = Path(response["path"])
    assert snapshot_path.parent.parent == home / ".megaplan" / "snapshots"
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    assert snapshot["epic"]["id"] == epic.id
    assert snapshot["body"] == "snapshot body"
    assert snapshot["plan_artifacts_by_plan"][plan.id][0]["content_text"] == "{\"offline\": true}\n"


def test_epic_migrate_requires_actor_before_store_creation(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    project = _project(tmp_path)
    monkeypatch.chdir(project)
    monkeypatch.delenv("MEGAPLAN_ACTOR_ID", raising=False)

    def fail_build_store(root: Path, *, actor_id: str | None = None) -> MultiStore:
        raise AssertionError("store should not be built without actor")

    monkeypatch.setattr(megaplan.cli, "build_epic_store", fail_build_store)

    exit_code = megaplan.cli.main(["epic", "migrate", "epic_1", "--to", "db"])
    response = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert response["success"] is False
    assert response["error"] == "missing_actor"


def test_epic_migrate_and_resume_print_final_state(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    project = _project(tmp_path)
    store = _store(tmp_path)
    epic = store.create_epic(title="File Epic", goal="g", body="body", home_backend="file")
    monkeypatch.chdir(project)

    def build_store(root: Path, *, actor_id: str | None = None) -> MultiStore:
        assert actor_id == "actor"
        return store

    monkeypatch.setattr(megaplan.cli, "build_epic_store", build_store)

    exit_code = megaplan.cli.main(["epic", "migrate", epic.id, "--to", "db", "--actor", "actor", "--ttl", "60"])
    migrate_response = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert migrate_response["success"] is True
    assert migrate_response["action"] == "migrate"
    assert migrate_response["phase"] == "complete"
    assert migrate_response["epic_id"] == epic.id
    assert migrate_response["target_backend"] == "db"

    exit_code = megaplan.cli.main(["epic", "migrate", "--resume", migrate_response["migration_id"], "--actor", "actor"])
    resume_response = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert resume_response["success"] is True
    assert resume_response["action"] == "resume"
    assert resume_response["phase"] == "complete"
    assert resume_response["migration_id"] == migrate_response["migration_id"]


def test_resume_command_uses_actor_store_for_epic_backed_plan(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    project = _project(tmp_path)
    store = _store(tmp_path)
    epic = store.create_epic(title="Epic", goal="g", body="body")
    plan_dir = project / ".megaplan" / "plans" / "blocked-plan"
    plan_dir.mkdir(parents=True)
    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "name": "blocked-plan",
                "idea": "idea",
                "epic_id": epic.id,
                "current_state": "blocked",
                "iteration": 1,
                "created_at": "2026-05-05T00:00:00Z",
                "config": {},
                "sessions": {},
                "plan_versions": [],
                "history": [],
                "meta": {},
                "last_gate": {},
                "latest_failure": {"kind": "execution_blocked"},
                "resume_cursor": {"phase": "execute", "batch_index": 1},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(project)
    monkeypatch.setenv("MEGAPLAN_ACTOR_ID", "actor")
    monkeypatch.setattr(megaplan.cli, "build_epic_store", lambda root, actor_id=None: store)

    def fail_resume(root: Path, plan: str, *, store=None):
        assert store is not None
        raise CliError("revision_conflict", "expected revision 1, found 2")

    monkeypatch.setattr(megaplan.cli, "resume_plan", fail_resume)

    exit_code = megaplan.cli.main(["resume", "--plan", "blocked-plan"])
    response = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert response["error"] == "revision_conflict"
