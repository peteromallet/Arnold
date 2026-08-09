"""Isolated restore proof and corruption checks (CL5 Step 14c / SC33).

SC33: "Does isolated replay reproduce projection hashes and fail on both bundle
corruption and projection divergence?"

This is the focused, combined data-integrity + isolation proof described by
T33. It uses the COMPLETED backup (T24) and isolated-restore (T26) APIs to:

1. **Create a backup**, **restore it to a temporary directory**, run
   ``integrity_check`` and ``replay_full`` (the projection replay), and assert
   the **restored projection hashes reproduce the manifest bundle**.
2. **Assert production state is untouched** — the isolated restore wrapper
   (T26) proves the guarded production db + artifacts are byte-identical before
   and after the restore (no side effects).
3. **Prove hash corruption fails closed** — a backup whose snapshot member bytes
   no longer match the manifest per-file hash is rejected at the archive gate
   *before* extraction (no partial state).
4. **Prove projection divergence fails closed** — a self-consistent restore
   whose restored bytes diverge from the manifest projection is rejected by the
   projection replay gate (per-file hash / bundle divergence).

These four cases operationalize SC33: isolated replay reproduces the
content-addressed projection, and *both* bundle corruption and projection
divergence fail closed.
"""

from __future__ import annotations

import io
import json
import tarfile as _tarfile
import uuid
from pathlib import Path

import pytest

from arnold.critique_ledger.cutover.backup import (
    DATABASE_TAR_PREFIX,
    MANIFEST_TAR_ENTRY,
    compute_bundle_hash,
    create_cutover_backup,
)
from arnold.critique_ledger.cutover.config import (
    NORTH_STAR_RUNTIME_HASH,
    CutoverConfig,
)
from arnold.critique_ledger.cutover.isolated_fixture import (
    isolated_restore_proof,
    snapshot_production_guard,
)
from arnold.critique_ledger.cutover.restore import (
    RestoreError,
    replay_projections,
    restore_backup,
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


# ── helpers (mirror tests/arnold/critique_ledger/test_cutover_restore.py) ─────


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
    *,
    persistence_status: PersistenceStatus = PersistenceStatus.DURABLE,
) -> LedgerEvent:
    cps = sequence - 1
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
        _make_event(
            attempt_id,
            sequence=1,
            event_type=AttemptEventType.STARTED,
            idempotency_key="k-start",
        ),
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


def _build_production_tree(
    tmp_path: Path,
) -> tuple[Path, Path, Path, SqliteAttemptLedgerStore]:
    """Create a production db + artifact dir and a verifiable backup tarball.

    Returns ``(tarball, db_path, artifacts, store)``. The store is left OPEN so
    the caller can snapshot the production guard then close it.
    """
    db_path = tmp_path / "prod.sqlite3"
    store = SqliteAttemptLedgerStore(db_path)
    for _ in range(2):
        _seed_in_flight(store, _aid())
    artifacts = tmp_path / "prod-artifacts"
    artifacts.mkdir()
    (artifacts / "proof.json").write_text(json.dumps({"k": 1}), encoding="utf-8")
    (artifacts / "sub").mkdir()
    (artifacts / "sub" / "deep.json").write_text(
        json.dumps({"deep": True}), encoding="utf-8"
    )
    tarball = tmp_path / "backup.tar"
    create_cutover_backup(
        _valid_config(), store, db_path, [artifacts], output_path=tarball, now=0.0
    )
    return tarball, db_path, artifacts, store


def _read_manifest(tarball: Path) -> dict:
    with _tarfile.open(tarball, mode="r") as tar:
        return json.loads(
            tar.extractfile(MANIFEST_TAR_ENTRY).read().decode("utf-8")
        )


# ── SC33: isolated replay reproduces projection hashes ────────────────────────


class TestIsolatedRestoreProof:
    """CL5 Step 14c focused proof (SC33)."""

    def test_isolated_replay_reproduces_projection_hashes(
        self, tmp_path: Path
    ) -> None:
        """Create a backup, restore to a temp dir, run integrity_check and the
        projection replay, and assert the restored projection hashes REPRODUCE
        the manifest bundle — the core of SC33."""
        tarball, db_path, artifacts, store = _build_production_tree(tmp_path)
        store.close()

        target = tmp_path / "restore"
        result = restore_backup(tarball, target, expected_config=_valid_config())

        # integrity_check ran on the restored database and returned ``ok``.
        assert result.integrity_check.ok is True
        assert result.integrity_check.output == ("ok",)

        # replay_full: the projection replay recomputed the bundle hash and it
        # equals the manifest's content-addressed bundle.
        manifest = result.manifest
        assert result.bundle_sha256 == manifest["bundle_sha256"]

        # Independent replay reproduces the SAME bundle hash from the restored
        # files (the deterministic projection replay).
        replayed_entries, replayed_bundle = replay_projections(target, manifest)
        assert replayed_bundle == manifest["bundle_sha256"]
        assert replayed_bundle == result.bundle_sha256
        # Every restored file's per-file hash matches the manifest projection.
        manifest_by_path = {f["path"]: f for f in manifest["files"]}
        assert {e.path for e in replayed_entries} == set(manifest_by_path)
        for entry in replayed_entries:
            assert entry.sha256 == manifest_by_path[entry.path]["sha256"]

    def test_production_state_is_untouched_by_isolated_restore(
        self, tmp_path: Path
    ) -> None:
        """The isolated restore wrapper restores into a throwaway temp dir and
        proves the guarded production db + artifacts are byte-identical before
        and after (no side effects)."""
        tarball, db_path, artifacts, store = _build_production_tree(tmp_path)
        store.close()

        proof = isolated_restore_proof(
            tarball,
            production_db_path=db_path,
            production_artifact_dirs=[artifacts],
            expected_config=_valid_config(),
        )
        assert proof.isolation_verified is True
        assert proof.restore_verified is True
        assert proof.integrity_check_ok is True
        # The restored bundle reproduced the manifest bundle.
        assert proof.bundle_match is True
        assert proof.restored_bundle_sha256 == proof.manifest_bundle_sha256
        # Production guard is byte-identical before and after.
        assert proof.production_guard_before == proof.production_guard_after
        assert proof.guarded_path_count >= 1
        # An independent re-snapshot of production still matches the before
        # guard — production was not touched.
        from arnold.critique_ledger.cutover.isolated_fixture import (
            collect_production_files,
        )

        prod_files = collect_production_files(db_path, [artifacts])
        after = snapshot_production_guard(prod_files)
        assert after == proof.production_guard_before

    def test_hash_corruption_fails_closed_before_extraction(
        self, tmp_path: Path
    ) -> None:
        """A backup whose snapshot member bytes no longer match the manifest
        per-file hash (hash corruption) is rejected at the archive gate BEFORE
        extraction — no partial restored state is exposed."""
        tarball, _db, _arts, store = _build_production_tree(tmp_path)
        store.close()

        corrupt = tmp_path / "corrupt.tar"
        with _tarfile.open(tarball, mode="r") as src, _tarfile.open(
            corrupt, mode="w"
        ) as dst:
            for member in src.getmembers():
                fh = src.extractfile(member)
                if (
                    member.name != MANIFEST_TAR_ENTRY
                    and member.isfile()
                    and fh is not None
                ):
                    data = fh.read()
                    data = (
                        (data[:-1] + bytes([data[-1] ^ 0xFF])) if data else b"X"
                    )
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
        # The archive gate rejects the hash-corrupted backup before extraction.
        with pytest.raises(RestoreError, match="Archive verification failed"):
            restore_backup(corrupt, target)
        # No partial state: nothing was extracted.
        assert not target.exists() or not any(
            p.is_file() for p in target.rglob("*")
        )

    def test_projection_divergence_fails_closed(self, tmp_path: Path) -> None:
        """A self-consistent restore whose restored bytes diverge from the
        manifest projection is rejected by the projection replay gate (per-file
        hash / bundle divergence)."""
        tarball, _db, _arts, store = _build_production_tree(tmp_path)
        store.close()

        # Clean restore first.
        target = tmp_path / "restore"
        restore_backup(tarball, target)
        manifest = _read_manifest(tarball)

        # Mutate a NON-database restored file so the replayed projection
        # diverges from the manifest (content-addressed mismatch).
        non_db = next(
            f
            for f in manifest["files"]
            if not f["path"].startswith(f"{DATABASE_TAR_PREFIX}/")
        )
        (target / non_db["path"]).write_bytes(b"divergent projection content")

        # The projection replay gate fails closed on the divergence.
        with pytest.raises(RestoreError, match="per-file hash mismatch"):
            replay_projections(target, manifest)

        # A second divergence: an extra file not listed in the manifest. The
        # replay gate also rejects this projection divergence.
        target2 = tmp_path / "restore2"
        restore_backup(tarball, target2)
        (target2 / "rogue.json").write_bytes(b"not in the manifest projection")
        with pytest.raises(RestoreError, match="not listed in the manifest"):
            replay_projections(target2, manifest)
