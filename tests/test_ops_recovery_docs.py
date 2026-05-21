from __future__ import annotations

from datetime import timedelta
import json
from pathlib import Path

import megaplan.cli
from megaplan._core.io import (
    journal_bytes_write,
    journal_commit_path,
    prepare_journal_transaction,
    recover_journal,
    write_journal_commit_marker,
)
from megaplan.schemas import MigrationRun, utc_now
from megaplan.store import MultiStore, deterministic_idempotency_key
from megaplan.store.file import FileStore


REQUIRED_SCENARIOS = {
    "Stuck FileStore Transaction Journal": "OPS-JOURNAL-RECOVERY",
    "Abandoned `migration_run`": "OPS-MIGRATION-RUN-RESUME",
    "Orphaned `execution_lease`": "OPS-EXECUTION-LEASE-EXPIRED",
    "Corrupt Or Missing Blob Payload Or Metadata": "OPS-BLOB-MISSING-CORRUPT",
    "Failed Or Partial Legacy Local Plan Migration": "OPS-LEGACY-MIGRATION-PARTIAL",
    "Failed Export Or Unusable Backup Tar": "OPS-EXPORT-TAR-VALIDATION",
    "Cloud Chain Worker Stall": "OPS-CLOUD-CHAIN-STALL-MANUAL",
    "Cloud Supervisor Tick": "OPS-CLOUD-SUPERVISOR",
    "DB Artifact Binary Compatibility During File-To-DB Promotion": "OPS-DB-BINARY-ARTIFACT-PROMOTION",
}


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


def test_ops_runbook_scenarios_have_evidence_and_required_sections() -> None:
    text = (Path(__file__).resolve().parents[1] / "docs" / "ops" / "recovery-runbooks.md").read_text(encoding="utf-8")
    for heading, evidence_id in REQUIRED_SCENARIOS.items():
        assert f"## {heading}" in text
        section = text.split(f"## {heading}", 1)[1].split("\n## ", 1)[0]
        assert f"Evidence id: `{evidence_id}`" in section
        for required in [
            "Symptoms:",
            "Diagnosis:",
            "Reproduction setup:",
            "Recovery steps:",
            "Post-recovery validation:",
            "Concrete references:",
        ]:
            assert required in section
        if "Cloud Chain" in heading:
            assert "manual" in section.lower()
        else:
            assert "tests/" in section or "pytest " in section


def test_ops_journal_recovery_replays_committed_and_discards_uncommitted(tmp_path: Path) -> None:
    root = tmp_path / "journal-root"
    committed_target = tmp_path / "committed.bin"
    discarded_target = tmp_path / "discarded.bin"
    prepare_journal_transaction(
        root,
        "committed",
        writes=[journal_bytes_write(committed_target, b"committed", tx_id="committed")],
    )
    write_journal_commit_marker(root, "committed")
    prepare_journal_transaction(
        root,
        "discarded",
        writes=[journal_bytes_write(discarded_target, b"discarded", tx_id="discarded")],
    )

    result = recover_journal(root)

    assert result["replayed"] == ["committed"]
    assert result["discarded"] == ["discarded"]
    assert committed_target.read_bytes() == b"committed"
    assert not discarded_target.exists()
    assert not journal_commit_path(root, "committed").exists()


def test_ops_migration_run_resume_reporting_and_expired_execution_lease(tmp_path: Path) -> None:
    store = _store(tmp_path)
    epic = store.create_epic(title="File", goal="g", body="body", home_backend="file")
    plan = store.create_plan(
        sprint_id=None,
        epic_id=epic.id,
        name="leased",
        idea="lease",
        idempotency_key=deterministic_idempotency_key("ops", epic.id, "plan"),
    )
    lease = store.acquire_execution_lease(
        plan.id,
        "holder",
        "local_cli",
        0,
        idempotency_key=deterministic_idempotency_key("ops", plan.id, "lease"),
    )
    assert lease.expires_at <= utc_now()
    assert store.file.get_active_lease(plan.id) is None

    run = store.migrate_epic(epic.id, to="db", ttl_seconds=60)
    resumed = store.resume_migration(run.id, ttl_seconds=60)
    assert resumed.id == run.id
    assert resumed.phase == "complete"

    incomplete = MigrationRun(
        id="migration-warning",
        epic_id=epic.id,
        source_backend="file",
        target_backend="db",
        phase="verifying",
        manifest={},
        copied_ids={},
        blob_copy_progress={},
        holder_id="stale",
        expires_at=utc_now() - timedelta(seconds=1),
    )
    store.db.create_migration_run(incomplete)
    warnings = store.incomplete_migration_warnings()
    assert "migration-warning" in warnings[0]


def test_ops_missing_blob_export_and_partial_legacy_conflict(tmp_path: Path, monkeypatch, capsys) -> None:
    project = _project(tmp_path)
    store = _store(tmp_path)
    epic = store.create_epic(title="Blob", goal="g", body="![alt](mp://image/diagram)", home_backend="file")
    image = store.attach_image(
        epic_id=epic.id,
        content=b"image",
        content_type="image/png",
        reference_key="diagram",
        idempotency_key=deterministic_idempotency_key("ops", epic.id, "image"),
    )
    store.file.blobs.delete(image.blob_id)
    monkeypatch.chdir(project)
    monkeypatch.setattr(megaplan.cli, "build_epic_store", lambda root, actor_id=None: store)

    fail_exit = megaplan.cli.main(["epic", "export", epic.id, "--output", str(tmp_path / "failed.tar")])
    fail_response = json.loads(capsys.readouterr().out)
    assert fail_exit == 1
    assert fail_response["error"] == "export_failed"

    home = tmp_path / "home"
    source_plan = home / ".megaplan" / "old" / "plans" / "plan-a"
    source_plan.mkdir(parents=True)
    (source_plan / "state.json").write_text("{\"ok\": true}\n", encoding="utf-8")
    args = [
        "migrate-local-plans",
        "--source-home",
        str(home),
        "--source-project",
        "old",
        "--target-project-dir",
        str(project),
    ]
    assert megaplan.cli.main(args) == 0
    capsys.readouterr()
    (source_plan / "state.json").write_text("{\"ok\": false}\n", encoding="utf-8")
    assert megaplan.cli.main(args) == 0
    conflict = json.loads(capsys.readouterr().out)
    assert conflict["conflicts"]


def test_ops_binary_artifact_survives_file_to_db_promotion(tmp_path: Path) -> None:
    store = _store(tmp_path)
    epic = store.create_epic(title="Binary", goal="g", body="body", home_backend="file")
    plan = store.create_plan(
        sprint_id=None,
        epic_id=epic.id,
        name="binary",
        idea="binary",
        idempotency_key=deterministic_idempotency_key("ops", epic.id, "binary-plan"),
    )
    data = b"\x00\xffops\x80\n"
    store.write_plan_artifact(
        plan.id,
        "nested/binary.bin",
        data,
        idempotency_key=deterministic_idempotency_key("ops", plan.id, "binary-artifact"),
    )

    store.migrate_epic(epic.id, to="db", ttl_seconds=60)

    assert store.db.read_plan_artifact(plan.id, "nested/binary.bin") == data
    assert store.db.stat_plan_artifact(plan.id, "nested/binary.bin").size_bytes == len(data)
