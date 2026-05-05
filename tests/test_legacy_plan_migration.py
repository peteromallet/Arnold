from __future__ import annotations

import json
from pathlib import Path

import megaplan.cli
from megaplan.store import MultiStore
from megaplan.store.file import FileStore


def _project(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    project.mkdir()
    (project / ".git").mkdir()
    return project


def test_legacy_plan_migration_orphan_dry_run_idempotency_and_conflict(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    project = _project(tmp_path)
    source_home = tmp_path / "source-home"
    target_home = tmp_path / "target-home"
    source_plan = source_home / ".megaplan" / "old-project" / "plans" / "plan-a"
    (source_plan / "nested").mkdir(parents=True)
    binary = b"\x00\xfflegacy\x80\n"
    (source_plan / "nested" / "artifact.bin").write_bytes(binary)
    (source_plan / "state.json").write_text("{\"legacy\": true}\n", encoding="utf-8")
    monkeypatch.chdir(project)
    monkeypatch.setenv("HOME", str(target_home))

    dry_exit = megaplan.cli.main([
        "migrate-local-plans",
        "--source-home",
        str(source_home),
        "--source-project",
        "old-project",
        "--target-project-dir",
        str(project),
        "--dry-run",
    ])
    dry_run = json.loads(capsys.readouterr().out)

    assert dry_exit == 0
    assert dry_run["success"] is True
    assert dry_run["dry_run"] is True
    assert dry_run["created"][0]["file_count"] == 2
    assert not MultiStore.canonical_filestore_root(project).exists()

    import_exit = megaplan.cli.main([
        "migrate-local-plans",
        "--source-home",
        str(source_home),
        "--source-project",
        "old-project",
        "--target-project-dir",
        str(project),
    ])
    imported = json.loads(capsys.readouterr().out)

    assert import_exit == 0
    plan_id = imported["created"][0]["plan_id"]
    store = FileStore(MultiStore.canonical_filestore_root(project))
    plan = store.load_plan(plan_id)
    assert plan is not None
    assert plan.epic_id is None
    assert plan.meta["legacy_migration"]["source_project"] == "old-project"
    assert [ref.name for ref in store.list_plan_artifacts(plan_id)] == ["nested/artifact.bin", "state.json"]
    assert store.read_plan_artifact(plan_id, "nested/artifact.bin") == binary

    rerun_exit = megaplan.cli.main([
        "migrate-local-plans",
        "--source-home",
        str(source_home),
        "--source-project",
        "old-project",
        "--target-project-dir",
        str(project),
    ])
    rerun = json.loads(capsys.readouterr().out)
    assert rerun_exit == 0
    assert rerun["skipped"] == [{"plan_id": plan_id, "reason": "unchanged"}]

    (source_plan / "state.json").write_text("{\"legacy\": false}\n", encoding="utf-8")
    conflict_exit = megaplan.cli.main([
        "migrate-local-plans",
        "--source-home",
        str(source_home),
        "--source-project",
        "old-project",
        "--target-project-dir",
        str(project),
    ])
    conflict = json.loads(capsys.readouterr().out)
    assert conflict_exit == 0
    assert conflict["success"] is False
    assert conflict["conflicts"][0]["plan_id"] == plan_id


def test_legacy_plan_migration_all_projects_legacy_epic_and_db_promotion(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    project = _project(tmp_path)
    source_home = tmp_path / "source-home"
    target_home = tmp_path / "target-home"
    first_plan = source_home / ".megaplan" / "project-one" / "plans" / "plan-a"
    second_plan = source_home / ".megaplan" / "project-two" / "plans" / "plan-b"
    (first_plan / "nested").mkdir(parents=True)
    second_plan.mkdir(parents=True)
    binary = b"\x00\xffpromote\x80\n"
    (first_plan / "nested" / "artifact.bin").write_bytes(binary)
    (second_plan / "state.json").write_text("{\"two\": true}\n", encoding="utf-8")
    monkeypatch.chdir(project)
    monkeypatch.setenv("HOME", str(target_home))

    exit_code = megaplan.cli.main([
        "migrate-local-plans",
        "--source-home",
        str(source_home),
        "--all-projects",
        "--target-project-dir",
        str(project),
        "--mode",
        "legacy-epic",
    ])
    response = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert response["success"] is True
    assert {entry["source_project"] for entry in response["projects"]} == {"project-one", "project-two"}
    legacy_epic_id = response["legacy_epic_id"]

    file_store = FileStore(MultiStore.canonical_filestore_root(project))
    plans = file_store.list_plans(epic_id=legacy_epic_id)
    assert {plan.meta["legacy_migration"]["source_project"] for plan in plans} == {"project-one", "project-two"}
    binary_plan = next(plan for plan in plans if plan.meta["legacy_migration"]["source_project"] == "project-one")
    assert file_store.read_plan_artifact(binary_plan.id, "nested/artifact.bin") == binary

    promoted = MultiStore(file_store=file_store, db_store=FileStore(tmp_path / "db"), actor_id="actor")
    promoted.migrate_epic(legacy_epic_id, to="db", ttl_seconds=60)
    assert promoted.db.read_plan_artifact(binary_plan.id, "nested/artifact.bin") == binary
