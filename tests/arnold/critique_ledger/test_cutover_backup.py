"""Tests for content-addressed cutover backup (CL5 Step 13).

Coverage:

* ``hash_file`` / ``compute_bundle_hash`` are deterministic and the bundle hash
  is independently re-derivable from the ``(path, sha256)`` pairs alone (no raw
  bytes).
* ``checkpoint_wal`` issues ``PRAGMA wal_checkpoint(TRUNCATE)`` on the store
  connection and reports a non-busy result on a quiescent store.
* ``collect_snapshot`` snapshots the db file plus artifact directories in
  deterministic order and fails closed on a missing database.
* ``create_cutover_backup`` validates the immutable config, engages the fence,
  drains remaining attempts to ``INDETERMINATE``, checkpoints the WAL, hashes
  every file + the canonical bundle, binds ``config`` and
  ``north_star_runtime_binding``, and emits a verifiable tarball.
* The backup tarball and manifest **independently reproduce every per-file and
  aggregate hash after a full WAL checkpoint** (SC24): re-hashing each tarball
  member reproduces the manifest per-file hashes, and the bundle hash is
  re-derivable from the manifest file list. Tampering with a member, the
  manifest list, the bundle hash, or the content hash is detected.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path

import pytest

from arnold.critique_ledger.cutover.backup import (
    BACKUP_MANIFEST_SCHEMA,
    BackupError,
    DATABASE_TAR_PREFIX,
    FileEntry,
    HASH_ALGORITHM,
    MANIFEST_TAR_ENTRY,
    build_manifest,
    checkpoint_wal,
    collect_snapshot,
    compute_bundle_hash,
    create_cutover_backup,
    hash_file,
    hash_snapshot,
    manifest_bundle_hash,
    verify_manifest_content_hash,
    verify_tarball,
    write_tarball,
)
from arnold.critique_ledger.cutover.config import (
    CutoverConfig,
    CutoverConfigError,
    NORTH_STAR_RUNTIME_HASH,
)
from arnold.critique_ledger.cutover.drain_map import DrainCategory
from arnold.critique_ledger.cutover.quiesce import quiesce
from arnold.workflow.attempt_ledger_store import SqliteAttemptLedgerStore
from arnold.workflow.execution_attempt_ledger import (
    AdapterKind,
    AttemptEventType,
    AttemptIdentity,
    AttemptOutcome,
    AttemptProvenance,
    GrantRef,
    LedgerEvent,
    PersistenceStatus,
    RuntimeAdapter,
    VersionSet,
)

# ── Event helpers (mirror tests/arnold/critique_ledger/test_cutover_quiesce.py) ──


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


def _valid_config() -> CutoverConfig:
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


# ── pure hashing primitives ──────────────────────────────────────────────────


class TestHashingPrimitives:
    def test_hash_file_matches_sha256_of_content(self, tmp_path: Path) -> None:
        f = tmp_path / "a.bin"
        payload = b"cutover-backup-payload-\x00\x01\x02"
        f.write_bytes(payload)
        assert hash_file(f) == hashlib.sha256(payload).hexdigest()

    def test_hash_file_is_chunked_for_large_files(self, tmp_path: Path) -> None:
        f = tmp_path / "big.bin"
        payload = b"x" * (1 << 18)  # 256 KiB > chunk size
        f.write_bytes(payload)
        assert hash_file(f) == hashlib.sha256(payload).hexdigest()

    def test_bundle_hash_is_deterministic_and_order_independent(self) -> None:
        entries = [
            FileEntry(path="b/x", size=1, sha256="a" * 64),
            FileEntry(path="a/y", size=2, sha256="b" * 64),
        ]
        h1 = compute_bundle_hash(entries)
        h2 = compute_bundle_hash(list(reversed(entries)))
        # Sorting inside compute_bundle_hash makes order irrelevant.
        assert h1 == h2
        # Pure function of (path, sha256) pairs.
        expected = hashlib.sha256(
            b"a/y\x00" + b"b" * 64 + b"\n" + b"b/x\x00" + b"a" * 64 + b"\n"
        ).hexdigest()
        assert h1 == expected

    def test_bundle_hash_reproducible_from_manifest_pairs_alone(self) -> None:
        entries = [
            FileEntry(path="database/s.sqlite3", size=4096, sha256="0" * 64),
            FileEntry(path="artifacts/p.json", size=11, sha256="1" * 64),
        ]
        bundle = compute_bundle_hash(entries)
        # An operator with only the (path, sha256) pairs re-derives the same hash
        # WITHOUT re-reading any snapshot bytes.
        recomputed = compute_bundle_hash(
            [FileEntry(path=e.path, size=e.size, sha256=e.sha256) for e in entries]
        )
        assert recomputed == bundle


# ── WAL checkpoint ───────────────────────────────────────────────────────────


class TestCheckpointWal:
    def test_checkpoint_returns_truncate_mode_and_not_busy_on_quiescent_store(
        self, tmp_path: Path
    ) -> None:
        store = SqliteAttemptLedgerStore(tmp_path / "s.sqlite3")
        # Touch the connection so WAL mode is active, then quiesce.
        quiesce(store)
        result = checkpoint_wal(store)
        assert result.mode == "TRUNCATE"
        assert result.busy == 0
        store.close()

    def test_checkpoint_after_writes_merges_wal_into_main_db(
        self, tmp_path: Path
    ) -> None:
        db_path = tmp_path / "s.sqlite3"
        store = SqliteAttemptLedgerStore(db_path)
        # Create committed WAL frames by writing events.
        for _ in range(3):
            _seed_in_flight(store, _aid())
        store.set_cutover_in_progress()

        wal_path = db_path.with_suffix(db_path.suffix + "-wal")
        # After writes in WAL mode the -wal file is typically present and non-empty;
        # checkpoint(TRUNCATE) empties it.
        result = checkpoint_wal(store)
        assert result.busy == 0
        assert result.mode == "TRUNCATE"
        if wal_path.exists():
            assert wal_path.stat().st_size == 0
        store.close()


# ── snapshot collection ──────────────────────────────────────────────────────


class TestCollectSnapshot:
    def test_collects_db_file_and_artifact_tree(self, tmp_path: Path) -> None:
        db = tmp_path / "s.sqlite3"
        db.write_bytes(b"DB")
        artifacts = tmp_path / "artifacts"
        (artifacts / "sub").mkdir(parents=True)
        (artifacts / "a.json").write_text("{}")
        (artifacts / "sub" / "b.json").write_text("[]")

        collected = collect_snapshot(db, [artifacts])
        by_archive = {archive: abs_path for abs_path, archive in collected}
        assert by_archive[f"{DATABASE_TAR_PREFIX}/{db.name}"] == db.resolve() or \
            by_archive[f"{DATABASE_TAR_PREFIX}/{db.name}"] == db
        assert "artifacts/a.json" in by_archive
        assert "artifacts/sub/b.json" in by_archive

    def test_deterministic_sorted_order(self, tmp_path: Path) -> None:
        db = tmp_path / "s.sqlite3"
        db.write_bytes(b"DB")
        artifacts = tmp_path / "artifacts"
        artifacts.mkdir()
        (artifacts / "z.json").write_text("z")
        (artifacts / "a.json").write_text("a")
        collected = collect_snapshot(db, [artifacts])
        archive_paths = [archive for _, archive in collected]
        assert archive_paths == sorted(archive_paths)

    def test_missing_database_fails_closed(self, tmp_path: Path) -> None:
        with pytest.raises(BackupError, match="Database file"):
            collect_snapshot(tmp_path / "missing.sqlite3", [])

    def test_missing_artifact_dir_is_skipped_silently(self, tmp_path: Path) -> None:
        db = tmp_path / "s.sqlite3"
        db.write_bytes(b"DB")
        collected = collect_snapshot(db, [tmp_path / "nope"])
        assert [archive for _, archive in collected] == [
            f"{DATABASE_TAR_PREFIX}/{db.name}"
        ]

    def test_hash_snapshot_missing_file_fails_closed(self, tmp_path: Path) -> None:
        snapshot = [(tmp_path / "gone.bin", "gone.bin")]
        with pytest.raises(BackupError, match="Snapshot file"):
            hash_snapshot(snapshot)


# ── manifest ─────────────────────────────────────────────────────────────────


class TestManifest:
    def _wal(self) -> object:
        from arnold.critique_ledger.cutover.backup import WalCheckpointResult

        return WalCheckpointResult(
            mode="TRUNCATE", busy=0, log_frames=2, checkpointed_frames=2
        )

    def test_manifest_binds_config_and_north_star_runtime_binding(self) -> None:
        config = _valid_config()
        entries = [FileEntry(path="database/s.sqlite3", size=10, sha256="f" * 64)]
        manifest = build_manifest(
            config=config,
            cutover_in_progress=True,
            previously_in_progress=False,
            in_flight_count=1,
            drained_count=0,
            marked_indeterminate_count=1,
            timed_out=True,
            wal_checkpoint=self._wal(),  # type: ignore[arg-type]
            file_entries=entries,
            bundle_sha256=compute_bundle_hash(entries),
            now=0.0,
        )
        assert manifest["schema"] == BACKUP_MANIFEST_SCHEMA
        assert manifest["hash_algorithm"] == HASH_ALGORITHM
        cfg = manifest["cutover_config"]
        assert cfg["source_revision"] == NORTH_STAR_RUNTIME_HASH
        assert cfg["north_star_runtime_binding"] == NORTH_STAR_RUNTIME_HASH
        assert cfg["backup_identity"] == config.backup_identity
        assert manifest["quiesce_state"]["cutover_in_progress"] is True
        assert manifest["quiesce_state"]["marked_indeterminate"] == 1
        assert manifest["wal_checkpoint"]["mode"] == "TRUNCATE"
        assert manifest["files"][0]["sha256"] == "f" * 64
        assert manifest["bundle_sha256"] == compute_bundle_hash(entries)
        assert manifest["content_hash"].startswith("sha256:")
        assert verify_manifest_content_hash(manifest) is True

    def test_content_hash_detects_tampering(self) -> None:
        config = _valid_config()
        entries: list[FileEntry] = []
        manifest = build_manifest(
            config=config,
            cutover_in_progress=True,
            previously_in_progress=False,
            in_flight_count=0,
            drained_count=0,
            marked_indeterminate_count=0,
            timed_out=False,
            wal_checkpoint=self._wal(),  # type: ignore[arg-type]
            file_entries=entries,
            bundle_sha256=compute_bundle_hash(entries),
            now=0.0,
        )
        tampered = dict(manifest)
        tampered = json.loads(json.dumps(manifest))
        tampered["cutover_config"]["north_star_runtime_binding"] = "deadbeef" * 5
        # content_hash unchanged but body mutated -> mismatch detected.
        assert verify_manifest_content_hash(tampered) is False

    def test_manifest_bundle_hash_re_derivable(self) -> None:
        entries = [
            FileEntry(path="database/s.sqlite3", size=10, sha256="a" * 64),
            FileEntry(path="artifacts/x.json", size=2, sha256="b" * 64),
        ]
        manifest = build_manifest(
            config=_valid_config(),
            cutover_in_progress=True,
            previously_in_progress=False,
            in_flight_count=0,
            drained_count=0,
            marked_indeterminate_count=0,
            timed_out=False,
            wal_checkpoint=self._wal(),  # type: ignore[arg-type]
            file_entries=entries,
            bundle_sha256=compute_bundle_hash(entries),
            now=0.0,
        )
        # Re-derive from manifest alone (no snapshot bytes).
        assert manifest_bundle_hash(manifest) == manifest["bundle_sha256"]


# ── create_cutover_backup ────────────────────────────────────────────────────


class TestCreateCutoverBackup:
    def test_rejects_invalid_config(self, tmp_path: Path) -> None:
        store = SqliteAttemptLedgerStore(tmp_path / "s.sqlite3")
        bad = _valid_config()
        invalid = CutoverConfig(
            source_revision="deadbeef" * 5,
            target_revision=bad.target_revision,
            schema_version=bad.schema_version,
            wbc_contract_hash=bad.wbc_contract_hash,
            m6_oracle_hash=bad.m6_oracle_hash,
            corpus_fixture_hash=bad.corpus_fixture_hash,
            operator_approval_revision=bad.operator_approval_revision,
            backup_identity=bad.backup_identity,
            build_revision=bad.build_revision,
            north_star_runtime_binding="deadbeef" * 5,
        )
        with pytest.raises(CutoverConfigError):
            create_cutover_backup(
                invalid, store, tmp_path / "s.sqlite3", now=0.0
            )
        # The fence must NOT be engaged when validation fails up front.
        assert store.is_cutover_in_progress() is False
        store.close()

    def test_engages_fence_drains_and_checkpoints_wal(self, tmp_path: Path) -> None:
        db_path = tmp_path / "s.sqlite3"
        store = SqliteAttemptLedgerStore(db_path)
        in_flight = _aid()
        _seed_in_flight(store, in_flight)

        result = create_cutover_backup(
            _valid_config(), store, db_path, now=0.0, drain_timeout_seconds=0.0
        )

        manifest = result.manifest
        # The writer is quiesced.
        assert manifest["quiesce_state"]["cutover_in_progress"] is True
        assert store.is_cutover_in_progress() is True
        # The in-flight attempt was drained to INDETERMINATE (fail-closed).
        assert manifest["quiesce_state"]["in_flight_enumerated"] == 1
        assert manifest["quiesce_state"]["marked_indeterminate"] == 1
        marks = store.get_cutover_indeterminate_marks()
        assert {m.attempt_id for m in marks} == {in_flight}
        # WAL was checkpointed.
        assert manifest["wal_checkpoint"]["mode"] == "TRUNCATE"
        assert manifest["wal_checkpoint"]["busy"] == 0
        store.close()

    def test_manifest_binds_north_star_and_hashes_database(
        self, tmp_path: Path
    ) -> None:
        db_path = tmp_path / "s.sqlite3"
        store = SqliteAttemptLedgerStore(db_path)
        # Force WAL activity.
        _seed_in_flight(store, _aid())

        result = create_cutover_backup(_valid_config(), store, db_path, now=0.0)
        manifest = result.manifest

        assert manifest["cutover_config"]["north_star_runtime_binding"] == NORTH_STAR_RUNTIME_HASH
        # The database file is in the snapshot.
        db_entry = [
            f for f in manifest["files"] if f["path"] == f"{DATABASE_TAR_PREFIX}/{db_path.name}"
        ]
        assert len(db_entry) == 1
        # The per-file hash matches a fresh re-hash of the post-checkpoint db file.
        # Close the store so no further WAL frames are pending, then re-checkpoint.
        store.close()
        assert db_entry[0]["sha256"] == hash_file(db_path)

    def test_includes_artifact_dirs_in_snapshot(self, tmp_path: Path) -> None:
        db_path = tmp_path / "s.sqlite3"
        store = SqliteAttemptLedgerStore(db_path)
        artifacts = tmp_path / "artifacts"
        artifacts.mkdir()
        (artifacts / "proof.json").write_text(json.dumps({"k": 1}), encoding="utf-8")

        result = create_cutover_backup(
            _valid_config(), store, db_path, [artifacts], now=0.0
        )
        manifest = result.manifest
        paths = {f["path"] for f in manifest["files"]}
        assert any(p.startswith("artifacts/") for p in paths)
        assert "artifacts/proof.json" in paths
        store.close()

    def test_writes_verifiable_tarball(self, tmp_path: Path) -> None:
        db_path = tmp_path / "s.sqlite3"
        store = SqliteAttemptLedgerStore(db_path)
        _seed_in_flight(store, _aid())
        artifacts = tmp_path / "artifacts"
        artifacts.mkdir()
        (artifacts / "p.json").write_text("{}")

        out = tmp_path / "backup.tar"
        result = create_cutover_backup(
            _valid_config(), store, db_path, [artifacts], output_path=out, now=0.0
        )
        assert result.tarball == str(out.resolve())
        assert Path(out).is_file()
        # The tarball is self-verifying.
        verified = verify_tarball(out)
        assert verified["schema"] == BACKUP_MANIFEST_SCHEMA
        assert verified["cutover_config"]["north_star_runtime_binding"] == NORTH_STAR_RUNTIME_HASH
        store.close()


# ── SC24: independent reproduction after a full WAL checkpoint ──────────────


class TestIndependentReproduction:
    def _build_backup_with_wal_activity(self, tmp_path: Path) -> tuple[Path, SqliteAttemptLedgerStore, Path]:
        db_path = tmp_path / "s.sqlite3"
        store = SqliteAttemptLedgerStore(db_path)
        # Generate substantial WAL activity across multiple in-flight attempts.
        for _ in range(4):
            _seed_in_flight(store, _aid())
        artifacts = tmp_path / "artifacts"
        artifacts.mkdir()
        (artifacts / "a.json").write_text(json.dumps({"a": 1}), encoding="utf-8")
        (artifacts / "b.json").write_text(json.dumps({"b": 2}), encoding="utf-8")
        out = tmp_path / "backup.tar"
        create_cutover_backup(
            _valid_config(), store, db_path, [artifacts], output_path=out, now=0.0
        )
        return out, store, db_path

    def test_verify_tarball_reproduces_every_per_file_hash(
        self, tmp_path: Path
    ) -> None:
        out, store, _ = self._build_backup_with_wal_activity(tmp_path)
        # verify_tarball re-reads each member, recomputes sha256, and checks
        # against the manifest per-file hashes; raises on any mismatch.
        manifest = verify_tarball(out)
        assert manifest["content_hash"].startswith("sha256:")
        store.close()

    def test_bundle_hash_re_derivable_from_manifest_after_wal_checkpoint(
        self, tmp_path: Path
    ) -> None:
        out, store, _ = self._build_backup_with_wal_activity(tmp_path)
        manifest = verify_tarball(out)
        # Independently re-derive the aggregate hash from the manifest file list.
        recomputed_bundle = manifest_bundle_hash(manifest)
        assert recomputed_bundle == manifest["bundle_sha256"]
        store.close()

    def test_database_member_matches_post_checkpoint_db_bytes(
        self, tmp_path: Path
    ) -> None:
        out, store, db_path = self._build_backup_with_wal_activity(tmp_path)
        manifest = verify_tarball(out)
        # Close the store (the backup already checkpointed the WAL), then
        # re-hash the on-disk database file: it MUST equal the tarball member
        # hash, proving the snapshot reflects the full WAL checkpoint.
        store.close()
        db_member = f"{DATABASE_TAR_PREFIX}/{db_path.name}"
        db_entry = next(f for f in manifest["files"] if f["path"] == db_member)
        assert db_entry["sha256"] == hash_file(db_path)
        # And the WAL is empty after the TRUNCATE checkpoint.
        wal_path = db_path.with_suffix(db_path.suffix + "-wal")
        if wal_path.exists():
            assert wal_path.stat().st_size == 0

    def test_tarball_is_byte_reproducible(self, tmp_path: Path) -> None:
        # The orchestration is stateful (the fence persists across runs, so
        # the second run reports previously_in_progress=True and emits a
        # different manifest). Byte-reproducibility is therefore a property
        # of the tarball writer: identical manifest + snapshot inputs MUST
        # produce identical archive bytes (deterministic order + fixed mtime).
        db_path = tmp_path / "s.sqlite3"
        store = SqliteAttemptLedgerStore(db_path)
        _seed_in_flight(store, _aid())
        artifacts = tmp_path / "artifacts"
        artifacts.mkdir()
        (artifacts / "p.json").write_text("{}")
        (artifacts / "q.json").write_text("[]")

        result = create_cutover_backup(
            _valid_config(), store, db_path, [artifacts], now=0.0
        )
        manifest = result.manifest
        snapshot = collect_snapshot(db_path, [artifacts])
        store.close()

        out_a = tmp_path / "a.tar"
        out_b = tmp_path / "b.tar"
        write_tarball(manifest, snapshot, out_a)
        write_tarball(manifest, snapshot, out_b)
        # Identical inputs -> identical archive bytes (deterministic).
        assert out_a.read_bytes() == out_b.read_bytes()

    def test_verify_tarball_detects_tampered_member(self, tmp_path: Path) -> None:
        out, store, _ = self._build_backup_with_wal_activity(tmp_path)
        store.close()
        # Rewrite one snapshot file's member bytes in a fresh tarball copy.
        import tarfile as _tarfile

        tampered = tmp_path / "tampered.tar"
        with _tarfile.open(out, mode="r") as src, _tarfile.open(tampered, mode="w") as dst:
            for member in src.getmembers():
                fh = src.extractfile(member)
                if member.name != MANIFEST_TAR_ENTRY and member.isfile() and fh is not None:
                    data = fh.read()
                    # Flip one byte to corrupt the content.
                    data = (data[:-1] + bytes([data[-1] ^ 0xFF])) if data else b"X"
                    info = _tarfile.TarInfo(name=member.name)
                    info.size = len(data)
                    info.mtime = 0
                    info.mode = 0o644
                    import io as _io
                    dst.addfile(info, _io.BytesIO(data))
                else:
                    if fh is not None:
                        dst.addfile(member, fh)
                    else:
                        dst.addfile(member)
        with pytest.raises(BackupError, match="Per-file hash mismatch"):
            verify_tarball(tampered)

    def test_verify_tarball_detects_missing_manifest(self, tmp_path: Path) -> None:
        out, store, _ = self._build_backup_with_wal_activity(tmp_path)
        store.close()
        import tarfile as _tarfile
        import io as _io

        no_manifest = tmp_path / "no_manifest.tar"
        with _tarfile.open(out, mode="r") as src, _tarfile.open(no_manifest, mode="w") as dst:
            for member in src.getmembers():
                if member.name == MANIFEST_TAR_ENTRY:
                    continue
                fh = src.extractfile(member)
                dst.addfile(member, fh)
        with pytest.raises(BackupError, match="missing the embedded manifest"):
            verify_tarball(no_manifest)

    def test_verify_tarball_detects_unlisted_member(self, tmp_path: Path) -> None:
        out, store, _ = self._build_backup_with_wal_activity(tmp_path)
        store.close()
        import tarfile as _tarfile
        import io as _io

        extra = tmp_path / "extra.tar"
        with _tarfile.open(out, mode="r") as src, _tarfile.open(extra, mode="w") as dst:
            for member in src.getmembers():
                fh = src.extractfile(member)
                if fh is not None:
                    dst.addfile(member, fh)
            # Inject a file that the manifest does not list.
            payload = b"sneaky"
            info = _tarfile.TarInfo(name="unlisted.bin")
            info.size = len(payload)
            info.mtime = 0
            info.mode = 0o644
            dst.addfile(info, _io.BytesIO(payload))
        with pytest.raises(BackupError, match="not listed in the manifest"):
            verify_tarball(extra)
