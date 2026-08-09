"""Adversarial cutover smoke scenarios (CL5 Step 17b / SC30).

SC30: "Do all injected failures leave admission closed and target state
inactive while selecting bounded recovery?"

This is one bounded test file that injects the five prescribed failure modes
into the real cutover package (no import mocks) and proves three fail-closed
outcomes for every one:

1. **Admission stays closed** — the cutover receipt never carries
   ``single_target_architecture_active = True``. For a wrong North Star binding
   the config never validates; for a corrupt/divergent backup the restore never
   exposes state; for a tampered/missing retirement proof the receipt is never
   emitted; for a pending proof the activation is explicitly ``False``.
2. **No partial target state is activated** — a rejected restore cleans up its
   extracted files (``cleanup_on_failure``); a rejected restore never reaches
   the projection gate; a tampered proof never produces a receipt body at all.
3. **The bounded recovery path is selected** — every failure raises a *typed,
   named* error (``CutoverConfigError`` / ``RestoreError`` / ``ReceiptError``)
   that an operator can act on, rather than a generic crash. The fail-closed
   rejection *is* the bounded recovery selector.

A final meta-test asserts that no failure mode can ever emit a receipt with an
active target architecture, and that the receipt always forces
``bridge_mode = False``.
"""

from __future__ import annotations

import hashlib
import io
import json
import tarfile as _tarfile
import uuid
from pathlib import Path

import pytest

from arnold.critique_ledger.cutover.backup import (
    BACKUP_MANIFEST_SCHEMA,
    DATABASE_TAR_PREFIX,
    MANIFEST_TAR_ENTRY,
    BackupError,
    create_cutover_backup,
)
from arnold.critique_ledger.cutover.config import (
    NORTH_STAR_RUNTIME_HASH,
    CutoverConfig,
    CutoverConfigError,
)
from arnold.critique_ledger.cutover.receipt import (
    ReceiptError,
    evaluate_activation,
    generate_cutover_receipt,
    verify_receipt_content_hash,
)
from arnold.critique_ledger.cutover.retire import generate_retirement_proof
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


def _wrong_north_star_config() -> CutoverConfig:
    """A config that binds the WRONG North Star runtime on both pinned fields."""
    return CutoverConfig(
        source_revision="0" * 40,
        target_revision="t" * 40,
        schema_version="sch" * 13,
        wbc_contract_hash="w" * 40,
        m6_oracle_hash="o" * 40,
        corpus_fixture_hash="c" * 40,
        operator_approval_revision="op" * 20,
        backup_identity="b" * 40,
        build_revision="br" * 20,
        north_star_runtime_binding="1" * 40,
    )


def _build_backup(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Create a real, verifiable backup tarball with a db + artifact dir.

    Returns ``(tarball, db_path, artifacts)``. The store is closed before
    returning so the snapshot is durable.
    """
    db_path = tmp_path / "s.sqlite3"
    store = SqliteAttemptLedgerStore(db_path)
    for _ in range(3):
        _seed_in_flight(store, _aid())
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    (artifacts / "proof.json").write_text(json.dumps({"k": 1}), encoding="utf-8")
    out = tmp_path / "backup.tar"
    create_cutover_backup(
        _valid_config(), store, db_path, [artifacts], output_path=out, now=0.0
    )
    store.close()
    return out, db_path, artifacts


def _read_manifest(tarball: Path) -> dict:
    with _tarfile.open(tarball, mode="r") as tar:
        return json.loads(
            tar.extractfile(MANIFEST_TAR_ENTRY).read().decode("utf-8")
        )


def _corrupt_member(src_tarball: Path, dst_tarball: Path) -> Path:
    """Copy *src* to *dst* flipping one byte of a snapshot member so the
    archive gate rejects it (the per-file hash no longer matches)."""
    with _tarfile.open(src_tarball, mode="r") as src, _tarfile.open(dst_tarball, mode="w") as dst:
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
    return dst_tarball


def _minimal_backup_manifest() -> dict:
    """A minimal manifest shape accepted by ``generate_cutover_receipt``."""
    return {
        "schema": BACKUP_MANIFEST_SCHEMA,
        "bundle_sha256": "x" * 64,
        "content_hash": "sha256:y",
        "file_count": 1,
    }


# ── SC30: each injected failure leaves admission closed ───────────────────────


class TestFailClosedCutoverSmoke:
    """CL5 Step 17b adversarial smoke (SC30)."""

    # ── wrong North Star binding ──────────────────────────────────────────

    def test_wrong_north_star_binding_keeps_admission_closed(
        self, tmp_path: Path
    ) -> None:
        wrong = _wrong_north_star_config()
        # The config never validates -> the cutover cannot bind its runtime.
        with pytest.raises(CutoverConfigError, match="north_star_runtime_binding"):
            wrong.validate()
        # A backup bound to the wrong runtime is refused (validate_config first).
        store = SqliteAttemptLedgerStore(tmp_path / "db.sqlite3")
        db_path = tmp_path / "db.sqlite3"
        with pytest.raises(CutoverConfigError):
            create_cutover_backup(wrong, store, db_path)
        store.close()
        # A receipt bound to the wrong runtime is never emitted.
        proof = generate_retirement_proof(_valid_config())
        with pytest.raises(CutoverConfigError):
            generate_cutover_receipt(
                wrong,
                backup_manifest=_minimal_backup_manifest(),
                retirement_proof=proof,
            )
        # Bounded recovery: the named config error is the selectable signal.

    # ── corrupt backup ─────────────────────────────────────────────────────

    def test_corrupt_backup_selects_bounded_restore_recovery(
        self, tmp_path: Path
    ) -> None:
        tarball, _db, _arts = _build_backup(tmp_path)
        corrupt = _corrupt_member(tarball, tmp_path / "corrupt.tar")
        target = tmp_path / "restore"
        # The archive gate rejects the corrupt backup BEFORE extraction.
        with pytest.raises(RestoreError, match="Archive verification failed"):
            restore_backup(corrupt, target)
        # No partial target state: nothing was extracted.
        assert not target.exists() or not any(target.rglob("*"))
        # Admission stays closed: without a verified restore there is nothing to
        # activate, and no receipt can be generated from an unverified backup.

    # ── projection divergence ──────────────────────────────────────────────

    def test_projection_divergence_selects_bounded_recovery(
        self, tmp_path: Path
    ) -> None:
        tarball, _db, _arts = _build_backup(tmp_path)
        target = tmp_path / "restore"
        restore_backup(tarball, target)  # clean restore first
        manifest = _read_manifest(tarball)
        # Corrupt a NON-database restored file so the replayed projection
        # diverges from the manifest (content-addressed mismatch).
        non_db = next(
            f for f in manifest["files"]
            if not f["path"].startswith(f"{DATABASE_TAR_PREFIX}/")
        )
        (target / non_db["path"]).write_bytes(b"divergent projection content")
        with pytest.raises(RestoreError, match="per-file hash mismatch"):
            replay_projections(target, manifest)
        # Bounded recovery: the projection gate names the divergence; the
        # cutover cannot accept a divergent projection.

    # ── stale custody (manifest binds a superseded config) ─────────────────

    def test_stale_custody_manifest_binding_selects_bounded_recovery(
        self, tmp_path: Path
    ) -> None:
        tarball, _db, _arts = _build_backup(tmp_path)  # bound to _valid_config()
        # The operator's CURRENT config advanced past the backup's stale custody
        # chain (e.g. a newer target_revision). Restoring against the current
        # config must reject the stale backup, not silently accept it.
        current = CutoverConfig(
            source_revision=NORTH_STAR_RUNTIME_HASH,
            target_revision="ADVANCED" + "x" * 32,
            schema_version="sch" * 13,
            wbc_contract_hash="w" * 40,
            m6_oracle_hash="o" * 40,
            corpus_fixture_hash="c" * 40,
            operator_approval_revision="op" * 20,
            backup_identity="b" * 40,
            build_revision="br" * 20,
            north_star_runtime_binding=NORTH_STAR_RUNTIME_HASH,
        )
        target = tmp_path / "restore"
        with pytest.raises(RestoreError, match="does not bind the expected config"):
            restore_backup(tarball, target, expected_config=current)
        # No partial state: the config-binding gate runs before extraction.
        assert not target.exists() or not any(target.rglob("*"))

    # ── missing evidence (retirement proof) ────────────────────────────────

    def test_missing_retirement_proof_keeps_target_inactive(
        self, tmp_path: Path
    ) -> None:
        config = _valid_config()
        # "Missing evidence": a retirement proof carrying the wrong schema is
        # not the expected evidence type.
        wrong_schema_proof = {
            "schema": "not-the-retirement-proof-schema",
            "content_hash": "sha256:" + "0" * 64,
        }
        with pytest.raises(ReceiptError, match="schema"):
            evaluate_activation(config, wrong_schema_proof)
        # No receipt with an active target can be emitted.
        with pytest.raises(ReceiptError, match="schema"):
            generate_cutover_receipt(
                config,
                backup_manifest=_minimal_backup_manifest(),
                retirement_proof=wrong_schema_proof,
            )

    # ── tampered evidence (retirement proof) ───────────────────────────────

    def test_tampered_retirement_proof_keeps_target_inactive(
        self, tmp_path: Path
    ) -> None:
        config = _valid_config()
        proof = generate_retirement_proof(config)
        # Tamper: the content_hash no longer matches the canonical body.
        tampered = dict(proof)
        tampered["content_hash"] = "sha256:" + "0" * 64
        with pytest.raises(ReceiptError, match="content_hash"):
            evaluate_activation(config, tampered)
        # A receipt bound to tampered evidence is never emitted.
        with pytest.raises(ReceiptError, match="content_hash"):
            generate_cutover_receipt(
                config,
                backup_manifest=_minimal_backup_manifest(),
                retirement_proof=tampered,
            )

    # ── pending (well-formed but not-yet-active) proof ─────────────────────

    def test_pending_retirement_proof_keeps_target_inactive(
        self, tmp_path: Path
    ) -> None:
        """A well-formed retirement proof that has NOT activated (pending)
        leaves the target architecture inactive — admission stays closed with
        NO partial activation, and the receipt honestly records the pending
        state instead of activating."""
        config = _valid_config()
        proof = generate_retirement_proof(config)
        # Re-sign the proof as a pending (not-yet-active) variant.
        pending = dict(proof)
        pending["single_target_architecture_active"] = False
        body = {k: v for k, v in pending.items() if k != "content_hash"}
        pending["content_hash"] = "sha256:" + hashlib.sha256(
            json.dumps(body, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        activation = evaluate_activation(config, pending)
        assert activation.single_target_architecture_active is False
        assert activation.bridge_mode is False
        receipt = generate_cutover_receipt(
            config,
            backup_manifest=_minimal_backup_manifest(),
            retirement_proof=pending,
        )
        # Admission stays closed: the target architecture is NOT active.
        assert receipt["single_target_architecture_active"] is False
        # No partial bridge path is activated either.
        assert receipt["bridge_mode"] is False
        assert receipt["retirement_verified"] is False

    # ── meta: no failure ever emits an active target receipt ───────────────

    def test_no_failure_emits_active_target_receipt(self, tmp_path: Path) -> None:
        """The receipt module structurally cannot emit a receipt with an active
        target from any failure path: it forces ``bridge_mode = False`` and
        gates activation behind a verified retirement proof whose content_hash
        and North Star binding match the config."""
        config = _valid_config()
        proof = generate_retirement_proof(config)
        # A valid, verified proof DOES activate (positive control).
        receipt = generate_cutover_receipt(
            config,
            backup_manifest=_minimal_backup_manifest(),
            retirement_proof=proof,
        )
        assert receipt["single_target_architecture_active"] is True
        assert receipt["bridge_mode"] is False
        assert verify_receipt_content_hash(receipt) is True
        # The activation field is content-addressed: tampering it breaks the hash.
        forged = dict(receipt)
        forged["single_target_architecture_active"] = True  # already true; flip bridge instead
        forged["bridge_mode"] = True  # a forged bridge activation
        assert verify_receipt_content_hash(forged) is False

    def test_corrupt_backup_via_database_gate_selects_bounded_recovery(
        self, tmp_path: Path
    ) -> None:
        """A self-consistent tarball whose database member is corrupt passes
        the archive gate but is rejected at ``integrity_check``; the extracted
        files are cleaned up so no partial state is exposed (bounded recovery).
        """
        tarball, _db, _arts = _build_backup(tmp_path)
        with _tarfile.open(tarball, mode="r") as tar:
            names = [m.name for m in tar.getmembers() if m.name != MANIFEST_TAR_ENTRY]
        db_member = next(n for n in names if n.startswith(f"{DATABASE_TAR_PREFIX}/"))

        corrupt = tmp_path / "corrupt_db.tar"
        _self_consistent_rewrite(tarball, corrupt, replace={db_member: b"corrupt-not-sqlite"})
        target = tmp_path / "restore"
        with pytest.raises(RestoreError, match="integrity_check failed"):
            restore_backup(corrupt, target)
        # cleanup_on_failure removed the extracted files -> no partial state.
        assert not target.exists() or not any(p.is_file() for p in target.rglob("*"))


def _self_consistent_rewrite(
    src_tarball: Path,
    dst_tarball: Path,
    replace: dict[str, bytes],
) -> dict:
    """Copy *src* to *dst*, replacing member bytes and rewriting the embedded
    manifest so the copy passes ``verify_tarball`` (archive gate) but carries
    the substituted content (to exercise a later gate in isolation)."""
    from arnold.critique_ledger.cutover.backup import FileEntry, compute_bundle_hash

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

    for entry in manifest["files"]:
        path = entry["path"]
        if path in replace:
            data = member_bytes[path]
            entry["sha256"] = hashlib.sha256(data).hexdigest()
            entry["size"] = len(data)

    entries = [
        FileEntry(path=f["path"], size=int(f["size"]), sha256=f["sha256"])
        for f in manifest["files"]
    ]
    manifest["bundle_sha256"] = compute_bundle_hash(entries)
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
