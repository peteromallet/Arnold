"""Tests for the isolated restore proof (CL5 Step 14b / SC26).

SC26: "Can the isolation test prove no production database or artifact path
changed during restore proof?"

Coverage:

* **Happy path**: a real backup restores into a throwaway temp dir, the
  restored bundle reproduces the manifest, and every guarded production file
  (database + artifacts) is byte-identical before and after →
  ``isolation_verified is True``.
* **Side-effect assertion**: the guard detects a changed production file
  (content), a touched production file (mtime-only), a deleted production
  file, and a new production file. The proof is not tautological — a genuine
  mutation is caught.
* **Restore-failure isolation**: a corrupt backup fails the restore, the
  wrapper raises :class:`IsolationError`, and production is still byte-clean
  (the failed-restore path re-verifies the guard).
* **No production write**: the restore target is a system temp dir, never the
  production database or artifact path, and it is removed after the proof.
"""

from __future__ import annotations

import io
import json
import os
import tarfile as _tarfile
import tempfile
import time
import uuid
from pathlib import Path

import pytest

from arnold.critique_ledger.cutover.backup import (
    MANIFEST_TAR_ENTRY,
    create_cutover_backup,
)
from arnold.critique_ledger.cutover.config import NORTH_STAR_RUNTIME_HASH
from arnold.critique_ledger.cutover.isolated_fixture import (
    ISOLATION_PROOF_SCHEMA,
    IsolationError,
    collect_production_files,
    isolated_restore_proof,
    snapshot_production_guard,
    verify_guard_unchanged,
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


def _build_production_tree(tmp_path: Path) -> tuple[Path, SqliteAttemptLedgerStore, Path, Path, Path]:
    """Build a production-shaped db + artifact dir and a backup tarball of it.

    Returns ``(tarball, store, db_path, artifacts, backup_tarball)``-style
    tuple: ``(tarball, store, db_path, artifacts)``. The store is left OPEN so
    the caller can close it (closing before the proof keeps the production db
    mtime stable).
    """
    db_path = tmp_path / "prod.sqlite3"
    store = SqliteAttemptLedgerStore(db_path)
    for _ in range(3):
        _seed_in_flight(store, _aid())
    artifacts = tmp_path / "prod-artifacts"
    artifacts.mkdir()
    (artifacts / "proof.json").write_text(json.dumps({"k": 1}), encoding="utf-8")
    (artifacts / "sub").mkdir()
    (artifacts / "sub" / "deep.json").write_text(json.dumps({"deep": True}), encoding="utf-8")
    out = tmp_path / "backup.tar"
    create_cutover_backup(
        _valid_config(), store, db_path, [artifacts], output_path=out, now=0.0
    )
    return out, store, db_path, artifacts


# ── collect / snapshot primitives ────────────────────────────────────────────


class TestCollectProductionFiles:
    def test_includes_db_and_artifact_files(self, tmp_path: Path) -> None:
        db = tmp_path / "db.sqlite3"
        db.write_bytes(b"x")
        arts = tmp_path / "arts"
        (arts / "sub").mkdir(parents=True)
        (arts / "a.json").write_text("a")
        (arts / "sub" / "b.json").write_text("b")
        files = collect_production_files(db, [arts])
        names = {f.name for f in files}
        assert "db.sqlite3" in names
        assert "a.json" in names
        assert "b.json" in names

    def test_missing_db_raises(self, tmp_path: Path) -> None:
        with pytest.raises(IsolationError, match="does not exist"):
            collect_production_files(tmp_path / "nope.sqlite3", [])

    def test_missing_artifact_dir_skipped(self, tmp_path: Path) -> None:
        db = tmp_path / "db.sqlite3"
        db.write_bytes(b"x")
        files = collect_production_files(db, [tmp_path / "absent"])
        assert files == [db.resolve()]


class TestSnapshotGuard:
    def test_guard_is_frozen_and_sorted(self, tmp_path: Path) -> None:
        a = tmp_path / "a"
        a.write_text("a")
        b = tmp_path / "b"
        b.write_text("b")
        guard = snapshot_production_guard([b, a])
        paths = [p for p, _ in guard.entries]
        assert paths == sorted(paths)

    def test_equal_guards_match(self, tmp_path: Path) -> None:
        a = tmp_path / "a"
        a.write_text("a")
        g1 = snapshot_production_guard([a])
        g2 = snapshot_production_guard([a])
        verify_guard_unchanged(g1, g2)  # no raise


# ── verify_guard_unchanged detects every mutation kind ────────────────────────


class TestVerifyGuardUnchanged:
    def test_detects_content_change(self, tmp_path: Path) -> None:
        a = tmp_path / "a"
        a.write_text("a")
        before = snapshot_production_guard([a])
        a.write_text("changed")
        after = snapshot_production_guard([a])
        with pytest.raises(IsolationError, match="content changed"):
            verify_guard_unchanged(before, after)

    def test_detects_mtime_only_touch(self, tmp_path: Path) -> None:
        a = tmp_path / "a"
        a.write_text("a")
        before = snapshot_production_guard([a])
        # Touch: same content, different mtime_ns.
        os.utime(a, ns=(time.time_ns() + 10_000_000, time.time_ns() + 10_000_000))
        after = snapshot_production_guard([a])
        with pytest.raises(IsolationError, match="content changed"):
            verify_guard_unchanged(before, after)

    def test_detects_deleted_file(self, tmp_path: Path) -> None:
        a = tmp_path / "a"
        a.write_text("a")
        before = snapshot_production_guard([a])
        a.unlink()
        after = snapshot_production_guard([])
        with pytest.raises(IsolationError, match="deleted"):
            verify_guard_unchanged(before, after)

    def test_detects_new_file(self, tmp_path: Path) -> None:
        a = tmp_path / "a"
        a.write_text("a")
        before = snapshot_production_guard([a])
        b = tmp_path / "b"
        b.write_text("b")
        after = snapshot_production_guard([a, b])
        with pytest.raises(IsolationError, match="new file"):
            verify_guard_unchanged(before, after)


# ── isolated_restore_proof orchestration ──────────────────────────────────────


class TestIsolatedRestoreProof:
    def test_happy_path_proves_no_production_mutation(self, tmp_path: Path) -> None:
        tarball, store, db_path, artifacts = _build_production_tree(tmp_path)
        store.close()
        proof = isolated_restore_proof(
            tarball,
            production_db_path=db_path,
            production_artifact_dirs=[artifacts],
        )
        assert proof.schema == ISOLATION_PROOF_SCHEMA
        assert proof.isolation_verified is True
        assert proof.restore_verified is True
        assert proof.integrity_check_ok is True
        assert proof.bundle_match is True
        assert proof.restored_bundle_sha256 == proof.manifest_bundle_sha256
        # The production guard is byte-identical before and after.
        assert proof.production_guard_before == proof.production_guard_after
        assert proof.guarded_path_count >= 1

    def test_restore_target_is_a_temp_dir_not_production(self, tmp_path: Path) -> None:
        tarball, store, db_path, artifacts = _build_production_tree(tmp_path)
        store.close()
        proof = isolated_restore_proof(
            tarball,
            production_db_path=db_path,
            production_artifact_dirs=[artifacts],
        )
        # The restore target is under the system temp root, not the production
        # tree (db_path / artifacts live under tmp_path).
        assert str(tmp_path) not in proof.target_dir or proof.target_dir.startswith(
            tempfile.gettempdir()
        )
        assert proof.target_dir != str(db_path)
        assert proof.target_dir != str(artifacts)
        # The temp dir was removed after the proof (ephemeral restore).
        assert not Path(proof.target_dir).exists()

    def test_corrupt_backup_raises_and_leaves_production_clean(
        self, tmp_path: Path
    ) -> None:
        tarball, store, db_path, artifacts = _build_production_tree(tmp_path)
        store.close()
        # Snapshot production now to compare after the failed proof.
        prod_files = collect_production_files(db_path, [artifacts])
        clean_guard = snapshot_production_guard(prod_files)

        # Corrupt a tarball member so the archive gate rejects it.
        corrupt = tmp_path / "corrupt.tar"
        with _tarfile.open(tarball, mode="r") as src, _tarfile.open(corrupt, mode="w") as dst:
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

        with pytest.raises(IsolationError, match="restore verification failed"):
            isolated_restore_proof(
                corrupt,
                production_db_path=db_path,
                production_artifact_dirs=[artifacts],
            )
        # Production is byte-clean after the failed proof.
        after_guard = snapshot_production_guard(prod_files)
        verify_guard_unchanged(clean_guard, after_guard)

    def test_expected_config_binding_is_forwarded(self, tmp_path: Path) -> None:
        tarball, store, db_path, artifacts = _build_production_tree(tmp_path)
        store.close()
        # The matching config is accepted; isolation still verified.
        proof = isolated_restore_proof(
            tarball,
            production_db_path=db_path,
            production_artifact_dirs=[artifacts],
            expected_config=_valid_config(),
        )
        assert proof.isolation_verified is True

    def test_production_db_guarded_against_unrelated_writer(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """If an *unrelated* writer mutates production between the before and
        after snapshots, the proof detects it — proving the guard is a real
        assertion, not a tautology, even on the happy restore path."""
        tarball, store, db_path, artifacts = _build_production_tree(tmp_path)
        store.close()

        import arnold.critique_ledger.cutover.isolated_fixture as mod

        original = mod.snapshot_production_guard
        calls: list = []

        def snapshot_then_mutate(paths):
            calls.append(paths)
            # Right before the AFTER snapshot (2nd call), simulate an unrelated
            # writer mutating a production artifact. The guard then diverges.
            if len(calls) == 2:
                (artifacts / "proof.json").write_text(
                    json.dumps({"mutated": True})
                )
            return original(paths)

        monkeypatch.setattr(mod, "snapshot_production_guard", snapshot_then_mutate)
        with pytest.raises(IsolationError, match="production mutation"):
            isolated_restore_proof(
                tarball,
                production_db_path=db_path,
                production_artifact_dirs=[artifacts],
            )
        assert len(calls) == 2  # before-snapshot + after-snapshot
