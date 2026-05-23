from __future__ import annotations

import json
import hashlib
import tarfile
from pathlib import Path

import megaplan.cli
from megaplan.store import MultiStore, deterministic_idempotency_key
from megaplan.store.file import FileStore
from megaplan.store.export import collect_epic_export
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
    json.dumps(snapshot)


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


def test_migrate_local_plans_requires_explicit_source_selection(tmp_path: Path, monkeypatch, capsys) -> None:
    project = _project(tmp_path)
    monkeypatch.chdir(project)

    exit_code = megaplan.cli.main([
        "migrate-local-plans",
        "--source-home",
        str(tmp_path / "home"),
        "--target-project-dir",
        str(project),
    ])
    response = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert response["error"] == "invalid_args"


def test_migrate_local_plans_dry_run_does_not_write_and_import_preserves_nested_binary(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    project = _project(tmp_path)
    home = tmp_path / "home"
    source_plan = home / ".megaplan" / "old-project" / "plans" / "plan-a"
    (source_plan / "nested").mkdir(parents=True)
    (source_plan / "state.json").write_text("{\"legacy\": true}\n", encoding="utf-8")
    binary = b"\x00\xfflegacy\x80\n"
    (source_plan / "nested" / "blob.bin").write_bytes(binary)
    monkeypatch.chdir(project)
    monkeypatch.setenv("HOME", str(tmp_path / "target-home"))

    dry_exit = megaplan.cli.main([
        "migrate-local-plans",
        "--source-home",
        str(home),
        "--source-project",
        "old-project",
        "--target-project-dir",
        str(project),
        "--dry-run",
    ])
    dry = json.loads(capsys.readouterr().out)
    assert dry_exit == 0
    assert dry["dry_run"] is True
    assert dry["created"][0]["file_count"] == 2
    assert not MultiStore.canonical_filestore_root(project).exists()

    import_exit = megaplan.cli.main([
        "migrate-local-plans",
        "--source-home",
        str(home),
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
    assert [ref.name for ref in store.list_plan_artifacts(plan_id)] == ["nested/blob.bin", "state.json"]
    assert store.read_plan_artifact(plan_id, "nested/blob.bin") == binary

    rerun_exit = megaplan.cli.main([
        "migrate-local-plans",
        "--source-home",
        str(home),
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
        str(home),
        "--source-project",
        "old-project",
        "--target-project-dir",
        str(project),
    ])
    conflict = json.loads(capsys.readouterr().out)
    assert conflict_exit == 0
    assert conflict["success"] is False
    assert conflict["conflicts"][0]["plan_id"] == plan_id


def test_migrate_local_plans_all_projects_legacy_epic_and_db_promotion_preserve_binary(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    project = _project(tmp_path)
    home = tmp_path / "home"
    first_plan = home / ".megaplan" / "project-one" / "plans" / "plan-a"
    second_plan = home / ".megaplan" / "project-two" / "plans" / "plan-b"
    (first_plan / "nested").mkdir(parents=True)
    second_plan.mkdir(parents=True)
    binary = b"\x00\xffpromote\x80\n"
    (first_plan / "nested" / "blob.bin").write_bytes(binary)
    (second_plan / "state.json").write_text("{\"two\": true}\n", encoding="utf-8")
    monkeypatch.chdir(project)
    monkeypatch.setenv("HOME", str(tmp_path / "target-home"))

    exit_code = megaplan.cli.main([
        "migrate-local-plans",
        "--source-home",
        str(home),
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
    assert len(response["created"]) == 2

    file_store = FileStore(MultiStore.canonical_filestore_root(project))
    legacy_epic_ids = response["legacy_epic_ids"]
    assert set(legacy_epic_ids) == {"project-one", "project-two"}
    first_plans = file_store.list_plans(epic_id=legacy_epic_ids["project-one"])
    second_plans = file_store.list_plans(epic_id=legacy_epic_ids["project-two"])
    assert {plan.meta["legacy_migration"]["source_project"] for plan in first_plans} == {"project-one"}
    assert {plan.meta["legacy_migration"]["source_project"] for plan in second_plans} == {"project-two"}
    binary_plan = first_plans[0]
    assert file_store.read_plan_artifact(binary_plan.id, "nested/blob.bin") == binary

    promoted = MultiStore(file_store=file_store, db_store=FileStore(tmp_path / "db"), actor_id="actor")
    promoted.migrate_epic(legacy_epic_ids["project-one"], to="db", ttl_seconds=60)
    assert promoted.db.read_plan_artifact(binary_plan.id, "nested/blob.bin") == binary


def test_collect_epic_export_is_byte_oriented_and_separate_from_snapshot(tmp_path: Path) -> None:
    store = _store(tmp_path)
    epic = store.create_epic(title="Export", goal="g", body="![alt](mp://image/diagram)", home_backend="file")
    plan = store.create_plan(
        sprint_id=None,
        epic_id=epic.id,
        name="export-plan",
        idea="export",
        idempotency_key=deterministic_idempotency_key("cli", epic.id, "export-plan"),
    )
    artifact_bytes = b"\x00\xffexport\x80\n"
    store.write_plan_artifact(
        plan.id,
        "nested/blob.bin",
        artifact_bytes,
        idempotency_key=deterministic_idempotency_key("cli", plan.id, "export-artifact"),
    )
    image = store.attach_image(
        epic_id=epic.id,
        content=b"image-bytes",
        content_type="image/png",
        reference_key="diagram",
        idempotency_key=deterministic_idempotency_key("cli", epic.id, "export-image"),
    )

    collected = collect_epic_export(store, epic.id)
    by_path = {entry["path"]: entry for entry in collected["files"]}

    assert by_path[f"plan_artifacts/{plan.id}/nested/blob.bin"]["bytes"] == artifact_bytes
    assert by_path[f"plan_artifacts/{plan.id}/nested/blob.bin"]["sha256"] == hashlib.sha256(artifact_bytes).hexdigest()
    assert by_path[f"blobs/{image.blob_id}/payload.bin"]["bytes"] == b"image-bytes"
    assert by_path["rows/epic.json"]["bytes"].endswith(b"\n")
    assert collected["manifest"]["errors"] == []
    assert all("bytes" not in item for item in collected["manifest"]["files"])


def test_epic_export_writes_deterministic_tar_and_gzip(tmp_path: Path, monkeypatch, capsys) -> None:
    project = _project(tmp_path)
    store = _store(tmp_path)
    epic = store.create_epic(title="Export", goal="g", body="body", home_backend="file")
    plan = store.create_plan(
        sprint_id=None,
        epic_id=epic.id,
        name="export-plan",
        idea="export",
        idempotency_key=deterministic_idempotency_key("cli", epic.id, "tar-plan"),
    )
    data = b"\x00\xfftar\x80\n"
    store.write_plan_artifact(
        plan.id,
        "nested/blob.bin",
        data,
        idempotency_key=deterministic_idempotency_key("cli", plan.id, "tar-artifact"),
    )
    monkeypatch.chdir(project)
    monkeypatch.setattr(megaplan.cli, "build_epic_store", lambda root, actor_id=None: store)

    tar_path = tmp_path / "backup.tar"
    exit_code = megaplan.cli.main(["epic", "export", epic.id, "--output", str(tar_path)])
    response = json.loads(capsys.readouterr().out)
    first_bytes = tar_path.read_bytes()
    exit_code_2 = megaplan.cli.main(["epic", "export", epic.id, "--output", str(tar_path)])
    response_2 = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert exit_code_2 == 0
    assert response["success"] is True
    assert response["action"] == "export"
    assert response["sha256"] == response_2["sha256"]
    assert first_bytes == tar_path.read_bytes()
    with tarfile.open(tar_path, "r") as tar:
        names = tar.getnames()
        assert names == sorted(names)
        assert "manifest.json" in names
        manifest = json.loads(tar.extractfile("manifest.json").read().decode("utf-8"))
        members = {name: tar.extractfile(name).read() for name in names if name != "manifest.json"}
        for entry in manifest["files"]:
            assert hashlib.sha256(members[entry["path"]]).hexdigest() == entry["sha256"]
            assert len(members[entry["path"]]) == entry["size_bytes"]
        assert tar.extractfile(f"plan_artifacts/{plan.id}/nested/blob.bin").read() == data

    gz_path = tmp_path / "backup.tar.gz"
    gz_exit = megaplan.cli.main(["epic", "export", epic.id, "--output", str(gz_path), "--gzip"])
    gz_response = json.loads(capsys.readouterr().out)
    assert gz_exit == 0
    assert gz_response["gzip"] is True
    with tarfile.open(gz_path, "r:gz") as tar:
        assert "manifest.json" in tar.getnames()


def test_epic_export_db_home_includes_binary_artifacts_and_snapshot_stays_json(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    project = _project(tmp_path)
    home = tmp_path / "home"
    home.mkdir()
    store = _store(tmp_path)
    epic = store.create_epic(title="DB Export", goal="g", body="snapshot body", home_backend="db")
    plan = store.create_plan(
        sprint_id=None,
        epic_id=epic.id,
        name="db-export-plan",
        idea="export",
        idempotency_key=deterministic_idempotency_key("cli", epic.id, "db-export-plan"),
    )
    binary = b"\x00\xffdb-home\x80\n"
    store.write_plan_artifact(
        plan.id,
        "nested/binary.bin",
        binary,
        idempotency_key=deterministic_idempotency_key("cli", plan.id, "db-export-artifact"),
    )
    monkeypatch.chdir(project)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(megaplan.cli, "build_epic_store", lambda root, actor_id=None: store)

    export_path = tmp_path / "db-home.tar"
    export_exit = megaplan.cli.main(["epic", "export", epic.id, "--output", str(export_path)])
    export_response = json.loads(capsys.readouterr().out)
    assert export_exit == 0
    assert export_response["success"] is True
    with tarfile.open(export_path, "r") as tar:
        assert tar.extractfile(f"plan_artifacts/{plan.id}/nested/binary.bin").read() == binary

    snapshot_exit = megaplan.cli.main(["epic", "snapshot", epic.id])
    snapshot_response = json.loads(capsys.readouterr().out)
    assert snapshot_exit == 0
    snapshot = json.loads(Path(snapshot_response["path"]).read_text(encoding="utf-8"))
    json.dumps(snapshot)
    artifact = snapshot["plan_artifacts_by_plan"][plan.id][0]
    assert artifact["size_bytes"] == len(binary)
    assert artifact["sha256"] == hashlib.sha256(binary).hexdigest()


def test_epic_export_missing_epic_and_missing_blob_behaviors(tmp_path: Path, monkeypatch, capsys) -> None:
    project = _project(tmp_path)
    store = _store(tmp_path)
    epic = store.create_epic(title="Export", goal="g", body="![alt](mp://image/diagram)", home_backend="file")
    image = store.attach_image(
        epic_id=epic.id,
        content=b"image-bytes",
        content_type="image/png",
        reference_key="diagram",
        idempotency_key=deterministic_idempotency_key("cli", epic.id, "missing-image"),
    )
    store.file.blobs.delete(image.blob_id)
    monkeypatch.chdir(project)
    monkeypatch.setattr(megaplan.cli, "build_epic_store", lambda root, actor_id=None: store)

    missing_exit = megaplan.cli.main(["epic", "export", "missing", "--output", str(tmp_path / "missing.tar")])
    missing_response = json.loads(capsys.readouterr().out)
    assert missing_exit == 1
    assert missing_response["error"] == "not_found"

    fail_exit = megaplan.cli.main(["epic", "export", epic.id, "--output", str(tmp_path / "fail.tar")])
    fail_response = json.loads(capsys.readouterr().out)
    assert fail_exit == 1
    assert fail_response["error"] == "export_failed"
    assert not (tmp_path / "fail.tar").exists()

    allowed_exit = megaplan.cli.main([
        "epic",
        "export",
        epic.id,
        "--output",
        str(tmp_path / "allowed.tar"),
        "--allow-missing-blobs",
    ])
    allowed_response = json.loads(capsys.readouterr().out)
    assert allowed_exit == 0
    assert allowed_response["warnings"]
    assert (tmp_path / "allowed.tar").exists()


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
