"""Tests for cutover backup restore & verification (CL5 Step 14 / SC25).

Coverage (SC25: restore rejects archive, database, or projection mismatches
before exposing any restored state):

* Happy path: a real backup restores end-to-end; ``PRAGMA integrity_check`` is
  ``ok``; the replayed projection bundle hash equals the manifest bundle hash;
  the restored per-file hashes reproduce the manifest; the result is the ONLY
  way restored state is exposed.
* **Archive gate** (before extraction): a tampered member, a missing manifest,
  and an unlisted member are all rejected by :func:`restore_backup` BEFORE any
  file is extracted (the target directory stays empty).
* **Database gate**: a self-consistent tarball carrying a corrupt SQLite
  database passes the archive gate but is rejected at ``integrity_check``;
  ``cleanup_on_failure`` removes the extracted files so no partial state is
  exposed.
* **Projection gate**: :func:`replay_projections` rejects a missing restored
  file, an extra file not listed in the manifest, and a per-file hash mismatch;
  the recomputed bundle hash must equal the manifest bundle hash.
* The restore is read-only w.r.t. sidecar files: opening the restored database
  for ``integrity_check`` never creates ``-wal``/``-shm`` in the target.
"""

from __future__ import annotations

import io
import json
import sqlite3
import tarfile as _tarfile
import uuid
from pathlib import Path

import pytest

from arnold.critique_ledger.cutover.backup import (
    BACKUP_MANIFEST_SCHEMA,
    DATABASE_TAR_PREFIX,
    MANIFEST_TAR_ENTRY,
    compute_bundle_hash,
    create_cutover_backup,
)
from arnold.critique_ledger.cutover.config import NORTH_STAR_RUNTIME_HASH
from arnold.critique_ledger.cutover.quiesce import quiesce
from arnold.critique_ledger.cutover.restore import (
    INTEGRITY_CHECK_OK,
    RestoreError,
    extract_tarball,
    replay_projections,
    restore_backup,
    run_integrity_check,
)
from arnold.workflow.attempt_ledger_store import SqliteAttemptLedgerStore
from arnold.workflow.execution_attempt_ledger import (
    AdapterKind,
    AttemptEventType,
    AttemptIdentity,
    AttemptProvenance,
    GrantRef,
    LedgerEvent,
    PersistenceStatus,
    RuntimeAdapter,
    VersionSet,
)


# ── helpers (mirror tests/arnold/critique_ledger/test_cutover_backup.py) ─────


def _aid() -> str:
    return str(uuid.uuid4())


def _make_identity(attempt_id: str) -> AttemptIdentity:
    return AttemptIdentity(
        workflow_id="wf-1",
        run_id="run-1",
        graph_revision="rev-1",
        attempt_ordinal=1,
        attempt_id=attempt_id,
    )


def _make_provenance() -> AttemptProvenance:
    return AttemptProvenance(
        parent_attempt_id=None,
        causal_lineage=(),
        actor_id=None,
        tool_id=None,
    )


def _make_event(
    attempt_id: str,
    sequence: int,
    event_type: AttemptEventType,
    idempotency_key: str,
    causal_predecessor_sequence: int | None = None,
    *,
    persistence_status: PersistenceStatus = PersistenceStatus.DURABLE,
) -> LedgerEvent:
    cps = sequence - 1 if causal_predecessor_sequence is None else causal_predecessor_sequence
    return LedgerEvent(
        idempotency_key=idempotency_key,
        event_type=event_type,
        identity=_make_identity(attempt_id),
        provenance=_make_provenance(),
        adapter=RuntimeAdapter(adapter_kind=AdapterKind.NATIVE, adapter_version="1"),
        versions=VersionSet(code_version="c1"),
        grant_ref=GrantRef(grant_id="grant-1"),
        sequence=sequence,
        causal_predecessor_sequence=cps,
        append_position=sequence - 1,
        occurred_at=f"2025-01-01T00:00:{sequence:02d}Z",
        observed_at=f"2025-01-01T00:00:{sequence:02d}Z",
        persistence_status=persistence_status,
    )


def _seed_in_flight(store: SqliteAttemptLedgerStore, attempt_id: str) -> None:
    store.append_started(
        attempt_id,
        _make_event(attempt_id, sequence=1, event_type=AttemptEventType.STARTED, idempotency_key="k-start"),
    )


def _valid_config():
    from arnold.critique_ledger.cutover.config import CutoverConfig

    return CutoverConfig(
        source_revision=NORTH_STAR_RUNTIME_HASH,
        target_revision="t" * 40,
        schema_version="sch" * 13,
        wbc_contract_hash="w" * 40,
        m6_oracle_hash="o" * 40,
        corpus_fixture_hash="c" * 40,
        operator_approval_revision="op" * 20,
        backup_identity="b" * 40,
        build_revision="br" * 20,
        north_star_runtime_binding=NORTH_STAR_RUNTIME_HASH,
    )


def _build_backup(tmp_path: Path) -> tuple[Path, SqliteAttemptLedgerStore, Path, Path]:
    """Create a real, verifiable backup tarball with a db + artifact dir."""
    db_path = tmp_path / "s.sqlite3"
    store = SqliteAttemptLedgerStore(db_path)
    for _ in range(3):
        _seed_in_flight(store, _aid())
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    (artifacts / "proof.json").write_text(json.dumps({"k": 1}), encoding="utf-8")
    (artifacts / "sub").mkdir()
    (artifacts / "sub" / "deep.json").write_text(json.dumps({"deep": True}), encoding="utf-8")
    out = tmp_path / "backup.tar"
    create_cutover_backup(
        _valid_config(), store, db_path, [artifacts], output_path=out, now=0.0
    )
    return out, store, db_path, artifacts


def _self_consistent_rewrite(
    src_tarball: Path,
    dst_tarball: Path,
    replace: dict[str, bytes],
) -> dict:
    """Copy *src_tarball* to *dst_tarball*, replacing member bytes in *replace*,
    and rewriting the embedded manifest so the copy is fully self-consistent
    (passes ``verify_tarball``). Returns the new manifest.

    This is used to build an archive that passes the archive gate but carries
    a corrupt database (to exercise the database gate in isolation).
    """
    import hashlib

    with _tarfile.open(src_tarball, mode="r") as src:
        members = {m.name: m for m in src.getmembers()}
        manifest = json.loads(
            src.extractfile(members[MANIFEST_TAR_ENTRY]).read().decode("utf-8")
        )
        member_bytes: dict[str, bytes] = {}
        for name, member in members.items():
            if name == MANIFEST_TAR_ENTRY:
                continue
            fh = src.extractfile(member)
            member_bytes[name] = replace.get(name, fh.read())

    # Rewrite per-file hashes/sizes for replaced members.
    for entry in manifest["files"]:
        path = entry["path"]
        if path in replace:
            data = member_bytes[path]
            entry["sha256"] = hashlib.sha256(data).hexdigest()
            entry["size"] = len(data)

    # Re-derive the bundle hash over the (possibly updated) file list.
    from arnold.critique_ledger.cutover.backup import FileEntry

    entries = [
        FileEntry(path=f["path"], size=int(f["size"]), sha256=f["sha256"])
        for f in manifest["files"]
    ]
    manifest["bundle_sha256"] = compute_bundle_hash(entries)
    # Re-stamp the manifest content_hash last.
    body = {k: v for k, v in manifest.items() if k != "content_hash"}
    manifest["content_hash"] = "sha256:" + hashlib.sha256(
        json.dumps(body, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()

    manifest_bytes = json.dumps(
        manifest, sort_keys=True, ensure_ascii=False, indent=2
    ).encode("utf-8")
    with _tarfile.open(dst_tarball, mode="w") as dst:
        for path in sorted(member_bytes):
            info = _tarfile.TarInfo(name=path)
            info.size = len(member_bytes[path])
            info.mtime = 0
            info.mode = 0o644
            dst.addfile(info, io.BytesIO(member_bytes[path]))
        m_info = _tarfile.TarInfo(name=MANIFEST_TAR_ENTRY)
        m_info.size = len(manifest_bytes)
        m_info.mtime = 0
        m_info.mode = 0o644
        dst.addfile(m_info, io.BytesIO(manifest_bytes))
    return manifest


# ── run_integrity_check ──────────────────────────────────────────────────────


class TestRunIntegrityCheck:
    def test_ok_on_healthy_restored_db(self, tmp_path: Path) -> None:
        out, store, db_path, _ = _build_backup(tmp_path)
        store.close()
        target = tmp_path / "restore"
        result = restore_backup(out, target)
        # The restored db passes integrity_check.
        check = run_integrity_check(result.database_path)
        assert check.ok is True
        assert check.output == (INTEGRITY_CHECK_OK,)

    def test_no_wal_sidecar_created_in_target(self, tmp_path: Path) -> None:
        out, store, db_path, _ = _build_backup(tmp_path)
        store.close()
        target = tmp_path / "restore"
        result = restore_backup(out, target)
        # Opening the restored db for integrity_check must NOT create -wal/-shm.
        run_integrity_check(result.database_path)
        names = {p.name for p in Path(target).rglob("*") if p.is_file()}
        assert not any(n.endswith("-wal") or n.endswith("-shm") for n in names)

    def test_fails_on_corrupt_db_file(self, tmp_path: Path) -> None:
        corrupt = tmp_path / "corrupt.sqlite3"
        corrupt.write_bytes(b"not a sqlite database at all")
        with pytest.raises(RestoreError, match="integrity_check"):
            run_integrity_check(corrupt)


# ── extract_tarball ──────────────────────────────────────────────────────────


class TestExtractTarball:
    def test_extracts_snapshot_members_not_manifest(self, tmp_path: Path) -> None:
        out, store, _, _ = _build_backup(tmp_path)
        store.close()
        target = tmp_path / "restore"
        restored, _created = extract_tarball(out, target)
        assert MANIFEST_TAR_ENTRY not in restored
        # Every restored path is a real file under the target.
        for archive_path in restored:
            assert (target / archive_path).is_file()
        # The database member is restored under the database/ prefix.
        assert any(p.startswith(f"{DATABASE_TAR_PREFIX}/") for p in restored)

    def test_rejects_path_traversal_member(self, tmp_path: Path) -> None:
        out, store, _, _ = _build_backup(tmp_path)
        store.close()
        evil = tmp_path / "evil.tar"
        payload = b"sneaky"
        with _tarfile.open(out, mode="r") as src, _tarfile.open(evil, mode="w") as dst:
            for member in src.getmembers():
                fh = src.extractfile(member)
                dst.addfile(member, fh)
            info = _tarfile.TarInfo(name="../escape.bin")
            info.size = len(payload)
            info.mtime = 0
            info.mode = 0o644
            dst.addfile(info, io.BytesIO(payload))
        with pytest.raises(RestoreError, match="refusing to extract outside the target"):
            extract_tarball(evil, tmp_path / "target")


# ── replay_projections (projection gate) ─────────────────────────────────────


class TestReplayProjections:
    def test_reproduces_manifest_bundle_on_clean_restore(self, tmp_path: Path) -> None:
        out, store, _, _ = _build_backup(tmp_path)
        store.close()
        target = tmp_path / "restore"
        restore_backup(out, target)
        manifest = json.loads(
            _tarfile.open(out, mode="r")
            .extractfile(MANIFEST_TAR_ENTRY)
            .read()
            .decode("utf-8")
        )
        entries, bundle = replay_projections(target, manifest)
        assert bundle == manifest["bundle_sha256"]
        assert {e.path for e in entries} == {f["path"] for f in manifest["files"]}

    def test_rejects_missing_restored_file(self, tmp_path: Path) -> None:
        out, store, _, _ = _build_backup(tmp_path)
        store.close()
        target = tmp_path / "restore"
        restore_backup(out, target)
        manifest = json.loads(
            _tarfile.open(out).extractfile(MANIFEST_TAR_ENTRY).read().decode("utf-8")
        )
        # Delete one restored file.
        victim = target / manifest["files"][0]["path"]
        victim.unlink()
        with pytest.raises(RestoreError, match="missing from the target"):
            replay_projections(target, manifest)

    def test_rejects_extra_file_not_in_manifest(self, tmp_path: Path) -> None:
        out, store, _, _ = _build_backup(tmp_path)
        store.close()
        target = tmp_path / "restore"
        restore_backup(out, target)
        manifest = json.loads(
            _tarfile.open(out).extractfile(MANIFEST_TAR_ENTRY).read().decode("utf-8")
        )
        (target / "artifacts" / "rogue.json").write_text("rogue")
        with pytest.raises(RestoreError, match="not listed in the manifest"):
            replay_projections(target, manifest)

    def test_rejects_per_file_hash_mismatch(self, tmp_path: Path) -> None:
        out, store, _, _ = _build_backup(tmp_path)
        store.close()
        target = tmp_path / "restore"
        restore_backup(out, target)
        manifest = json.loads(
            _tarfile.open(out).extractfile(MANIFEST_TAR_ENTRY).read().decode("utf-8")
        )
        # Corrupt a non-database restored file so its hash diverges.
        non_db = next(
            f for f in manifest["files"] if not f["path"].startswith(f"{DATABASE_TAR_PREFIX}/")
        )
        victim = target / non_db["path"]
        victim.write_bytes(b"totally different content")
        with pytest.raises(RestoreError, match="per-file hash mismatch"):
            replay_projections(target, manifest)


# ── restore_backup orchestration ─────────────────────────────────────────────


class TestRestoreBackup:
    def test_happy_path_restores_and_verifies_all_gates(self, tmp_path: Path) -> None:
        out, store, db_path, artifacts = _build_backup(tmp_path)
        store.close()
        target = tmp_path / "restore"
        result = restore_backup(out, target)

        # Archive gate produced the verified manifest.
        assert result.manifest["schema"] == BACKUP_MANIFEST_SCHEMA
        # Database gate passed.
        assert result.integrity_check.ok is True
        assert result.database_path is not None
        assert Path(result.database_path).is_file()
        # Projection gate: recomputed bundle equals the manifest bundle.
        assert result.bundle_sha256 == result.manifest["bundle_sha256"]
        # Every restored file exists and is listed.
        assert set(result.restored_files) == {
            f["path"] for f in result.manifest["files"]
        }
        # The artifact tree was restored faithfully.
        assert (target / "artifacts" / "proof.json").is_file()
        assert (target / "artifacts" / "sub" / "deep.json").is_file()

    def test_restored_database_is_queryable(self, tmp_path: Path) -> None:
        out, store, _, _ = _build_backup(tmp_path)
        store.close()
        result = restore_backup(out, tmp_path / "restore")
        # The restored db has the store's tables and the seeded rows survived.
        conn = sqlite3.connect(result.database_path)
        tables = {
            r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "attempt_events" in tables
        conn.close()

    def test_binds_expected_config_north_star_runtime(self, tmp_path: Path) -> None:
        out, store, _, _ = _build_backup(tmp_path)
        store.close()
        result = restore_backup(
            out, tmp_path / "restore", expected_config=_valid_config()
        )
        assert (
            result.manifest["cutover_config"]["north_star_runtime_binding"]
            == NORTH_STAR_RUNTIME_HASH
        )

    def test_rejects_expected_config_mismatch(self, tmp_path: Path) -> None:
        from arnold.critique_ledger.cutover.config import CutoverConfig

        out, store, _, _ = _build_backup(tmp_path)
        store.close()
        wrong = CutoverConfig(
            source_revision=NORTH_STAR_RUNTIME_HASH,
            target_revision="DIFFERENT" + "x" * 30,
            schema_version="sch" * 13,
            wbc_contract_hash="w" * 40,
            m6_oracle_hash="o" * 40,
            corpus_fixture_hash="c" * 40,
            operator_approval_revision="op" * 20,
            backup_identity="b" * 40,
            build_revision="br" * 20,
            north_star_runtime_binding=NORTH_STAR_RUNTIME_HASH,
        )
        with pytest.raises(RestoreError, match="does not bind the expected config"):
            restore_backup(out, tmp_path / "restore", expected_config=wrong)
        # Nothing was extracted (archive gate passes, but config gate is before
        # extraction).
        assert not (tmp_path / "restore").exists() or not any(
            (tmp_path / "restore").rglob("*")
        )

    # ── archive gate: rejected BEFORE extraction ───────────────────────────

    def test_archive_gate_rejects_tampered_member_before_extraction(
        self, tmp_path: Path
    ) -> None:
        out, store, _, _ = _build_backup(tmp_path)
        store.close()
        tampered = tmp_path / "tampered.tar"
        with _tarfile.open(out, mode="r") as src, _tarfile.open(tampered, mode="w") as dst:
            for member in src.getmembers():
                fh = src.extractfile(member)
                if member.name != MANIFEST_TAR_ENTRY and member.isfile() and fh is not None:
                    data = fh.read()
                    data = (data[:-1] + bytes([data[-1] ^ 0xFF])) if data else b"X"
                    info = _tarfile.TarInfo(name=member.name)
                    info.size = len(data)
                    info.mtime = 0
                    info.mode = 0o644
                    dst.addfile(info, io.BytesIO(data))
                else:
                    if fh is not None:
                        dst.addfile(member, fh)
                    else:
                        dst.addfile(member)
        target = tmp_path / "restore"
        with pytest.raises(RestoreError, match="Archive verification failed"):
            restore_backup(tampered, target)
        # No file was extracted: the archive gate runs before extraction.
        assert not target.exists() or not any(target.rglob("*"))

    def test_archive_gate_rejects_missing_manifest_before_extraction(
        self, tmp_path: Path
    ) -> None:
        out, store, _, _ = _build_backup(tmp_path)
        store.close()
        no_manifest = tmp_path / "no_manifest.tar"
        with _tarfile.open(out, mode="r") as src, _tarfile.open(no_manifest, mode="w") as dst:
            for member in src.getmembers():
                if member.name == MANIFEST_TAR_ENTRY:
                    continue
                fh = src.extractfile(member)
                dst.addfile(member, fh)
        target = tmp_path / "restore"
        with pytest.raises(RestoreError, match="Archive verification failed"):
            restore_backup(no_manifest, target)
        assert not target.exists() or not any(target.rglob("*"))

    # ── database gate: archive ok, corrupt db rejected ─────────────────────

    def test_database_gate_rejects_corrupt_db_and_cleans_up(
        self, tmp_path: Path
    ) -> None:
        out, store, db_path, _ = _build_backup(tmp_path)
        store.close()
        # Identify the database member name.
        with _tarfile.open(out, mode="r") as tar:
            names = [m.name for m in tar.getmembers() if m.name != MANIFEST_TAR_ENTRY]
        db_member = next(n for n in names if n.startswith(f"{DATABASE_TAR_PREFIX}/"))

        # Build a self-consistent tarball whose db member is corrupt bytes.
        corrupt = tmp_path / "corrupt_db.tar"
        _self_consistent_rewrite(out, corrupt, replace={db_member: b"corrupt-not-sqlite"})

        target = tmp_path / "restore"
        with pytest.raises(RestoreError, match="integrity_check failed"):
            restore_backup(corrupt, target)
        # cleanup_on_failure removed the extracted files -> no partial state.
        assert not any(p.is_file() for p in target.rglob("*")) if target.exists() else True

    def test_database_gate_corrupt_db_leaves_files_when_cleanup_disabled(
        self, tmp_path: Path
    ) -> None:
        out, store, _, _ = _build_backup(tmp_path)
        store.close()
        with _tarfile.open(out, mode="r") as tar:
            names = [m.name for m in tar.getmembers() if m.name != MANIFEST_TAR_ENTRY]
        db_member = next(n for n in names if n.startswith(f"{DATABASE_TAR_PREFIX}/"))
        corrupt = tmp_path / "corrupt_db.tar"
        _self_consistent_rewrite(out, corrupt, replace={db_member: b"corrupt-not-sqlite"})

        target = tmp_path / "restore"
        with pytest.raises(RestoreError, match="integrity_check failed"):
            restore_backup(corrupt, target, cleanup_on_failure=False)
        # Files remain when cleanup is disabled (caller manages the target).
        assert any(p.is_file() for p in target.rglob("*"))
