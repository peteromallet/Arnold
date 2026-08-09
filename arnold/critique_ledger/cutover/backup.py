"""Content-addressed cutover backup (CL5 Step 13).

This module produces a *verifiable* backup of the cutover's durable state:

1. **Quiesce the writer** — engage the durable ``cutover_in_progress``
   admission fence via :func:`~arnold.critique_ledger.cutover.quiesce.quiesce`
   and drain the surviving in-flight attempts to ``INDETERMINATE`` so the
   ledger reaches a quiescent, fail-closed state before the snapshot.
2. **Checkpoint the SQLite WAL** — issue ``PRAGMA wal_checkpoint(TRUNCATE)`` on
   the store connection so the main database file holds every committed frame
   and the ``-wal`` sidecar is emptied; the snapshot therefore reflects a
   single durable image rather than a half-flushed WAL.
3. **Snapshot** the database file and every artifact directory.
4. **Hash every file** (per-file ``sha256``) and **the canonical bundle** — a
   single ``sha256`` over the sorted ``path\\0sha256`` envelope of the
   snapshot, which is reproducible from the manifest alone.
5. **Emit a verifiable tarball** plus a content-addressed manifest that binds
   the immutable :class:`CutoverConfig` — including
   ``north_star_runtime_binding`` — so the snapshot is independently
   reproducible: an operator can re-hash every file and re-derive the bundle
   hash from the manifest, and detect any tampering or divergence.

Because the bundle hash is a pure function of the ``(path, sha256)`` pairs (not
of the raw bytes), it can be re-derived from the manifest without re-reading
the snapshot — see :func:`compute_bundle_hash`.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import tarfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from arnold.critique_ledger.cutover.config import (
    CutoverConfig,
    NORTH_STAR_RUNTIME_HASH,
    validate_config,
)
from arnold.critique_ledger.cutover.quiesce import drain, quiesce
from arnold.adapters.ledger_store_adapter import AttemptLedgerStore

#: Manifest schema identifier.
BACKUP_MANIFEST_SCHEMA: str = "cl5.cutover-backup-manifest.v1"

#: Canonical hash algorithm (content-addressing).
HASH_ALGORITHM: str = "sha256"

#: The directory entry name for the manifest inside the tarball.
MANIFEST_TAR_ENTRY: str = "manifest.json"

#: The directory prefix for the database file inside the tarball.
DATABASE_TAR_PREFIX: str = "database"

#: Fixed tarball member mtime so the archive is byte-reproducible.
_TARBALL_FIXED_MTIME: int = 0


class BackupError(RuntimeError):
    """Raised when a verifiable cutover backup cannot be produced.

    The backup is fail-closed: a missing database file, an un-engaged fence, a
    WAL checkpoint that cannot complete, or any unreadable snapshot file aborts
    the backup rather than emitting partial evidence.
    """


@dataclass(frozen=True)
class FileEntry:
    """One hashed file in the backup snapshot."""

    #: POSIX-style path of the file within the tarball root.
    path: str
    #: File size in bytes.
    size: int
    #: ``sha256`` hex digest of the file content.
    sha256: str


@dataclass(frozen=True)
class WalCheckpointResult:
    """Outcome of ``PRAGMA wal_checkpoint(TRUNCATE)``.

    The three SQLite columns are:

    * ``busy`` — 1 if the writer was busy and the checkpoint could not run to
      completion, 0 otherwise.
    * ``log_frames`` — the number of frames in the WAL log.
    * ``checkpointed_frames`` — the number of frames checkpointed into the
      database file.
    """

    mode: str
    busy: int
    log_frames: int
    checkpointed_frames: int


@dataclass(frozen=True)
class BackupResult:
    """Result of :func:`create_cutover_backup`.

    ``manifest`` is the canonical, content-addressed manifest dict. ``tarball``
    is the absolute path the archive was written to (or ``None`` when no
    ``output_path`` was supplied).
    """

    manifest: dict[str, Any]
    tarball: str | None


# ── primitives ───────────────────────────────────────────────────────────────


def hash_file(path: str | Path) -> str:
    """Return the ``sha256`` hex digest of *path*'s content (chunked)."""
    h = hashlib.new(HASH_ALGORITHM)
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def compute_bundle_hash(entries: Sequence[FileEntry]) -> str:
    """Canonical aggregate ``sha256`` over a set of :class:`FileEntry`.

    The bundle hash is a pure function of the ``(path, sha256)`` pairs — sorted
    by path, joined with ``path\\0sha256\\n`` — so it can be **independently
    re-derived from the manifest alone** without re-reading any snapshot bytes.
    This is what makes the backup verifiable: an operator who only has the
    manifest can recompute the bundle hash and detect a tampered file list.
    """
    h = hashlib.new(HASH_ALGORITHM)
    for entry in sorted(entries, key=lambda e: e.path):
        h.update(entry.path.encode("utf-8"))
        h.update(b"\0")
        h.update(entry.sha256.encode("ascii"))
        h.update(b"\n")
    return h.hexdigest()


def checkpoint_wal(store: AttemptLedgerStore) -> WalCheckpointResult:
    """Issue ``PRAGMA wal_checkpoint(TRUNCATE)`` on the store's connection.

    Touching :attr:`~arnold.workflow.attempt_ledger_store.SqliteAttemptLedgerStore.conn`
    opens (or reuses) the SQLite connection that owns the WAL; checkpointing on
    that connection flushes every committed frame into the main database file
    and truncates the ``-wal`` sidecar so the snapshot reflects a single
    durable image. A ``busy`` result (the writer held the lock) fails closed.
    """
    conn = store.conn  # lazily opens + enables WAL mode
    rows = conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchall()
    row = rows[0] if rows else (None, None, None)
    busy, log_frames, checkpointed = row[0], row[1], row[2]
    result = WalCheckpointResult(
        mode="TRUNCATE",
        busy=int(busy) if busy is not None else -1,
        log_frames=int(log_frames) if log_frames is not None else -1,
        checkpointed_frames=int(checkpointed) if checkpointed is not None else -1,
    )
    if result.busy == 1:
        raise BackupError(
            "SQLite WAL checkpoint(TRUNCATE) returned busy=1; the writer held "
            "the lock and the snapshot cannot be guaranteed consistent. The "
            "writer must be quiesced before the backup."
        )
    return result


# ── snapshot collection ───────────────────────────────────────────────────────


def collect_snapshot(
    db_path: str | Path,
    artifact_dirs: Sequence[str | Path],
) -> list[tuple[Path, str]]:
    """Collect ``(absolute_path, archive_path)`` pairs for the snapshot.

    The database file is stored under ``database/<name>``; each artifact
    directory is stored under its own basename, preserving the directory tree.
    The database file MUST exist (a backup of a nonexistent database fails
    closed). Missing artifact directories are skipped with no error so an
    operator can snapshot a cutover with no artifacts yet produced.
    """
    db = Path(db_path)
    if not db.is_file():
        raise BackupError(
            f"Database file {db!s} does not exist or is not a regular file; "
            "the cutover backup cannot snapshot a missing database."
        )

    collected: list[tuple[Path, str]] = [(db, f"{DATABASE_TAR_PREFIX}/{db.name}")]

    seen_dirs: set[Path] = set()
    for raw_dir in artifact_dirs:
        directory = Path(raw_dir)
        if not directory.is_dir():
            continue
        directory = directory.resolve()
        if directory in seen_dirs:
            continue
        seen_dirs.add(directory)
        root_name = directory.name
        for root, dirs, files in os.walk(directory):
            # Deterministic traversal order.
            dirs.sort()
            for name in sorted(files):
                abs_path = Path(root) / name
                rel = abs_path.relative_to(directory)
                archive_path = f"{root_name}/{rel.as_posix()}"
                collected.append((abs_path, archive_path))

    # Globally deterministic ordering by archive path so the snapshot, the
    # manifest file list, and the tarball members all share one canonical order.
    return sorted(collected, key=lambda pair: pair[1])


def hash_snapshot(
    snapshot: Sequence[tuple[Path, str]],
) -> list[FileEntry]:
    """Hash every file in *snapshot*, returning :class:`FileEntry` records.

    Sorted by archive path for a deterministic manifest ordering. Raises
    :class:`BackupError` if any snapshot file cannot be read — the backup is
    fail-closed so a partially-readable snapshot never emits evidence.
    """
    entries: list[FileEntry] = []
    for abs_path, archive_path in sorted(snapshot, key=lambda pair: pair[1]):
        if not abs_path.is_file():
            raise BackupError(
                f"Snapshot file {abs_path!s} (archive path {archive_path!r}) is "
                "missing or not a regular file; the backup cannot hash it."
            )
        try:
            digest = hash_file(abs_path)
            size = abs_path.stat().st_size
        except OSError as exc:  # pragma: no cover - defensive
            raise BackupError(
                f"Could not hash snapshot file {abs_path!s}: {exc}"
            ) from exc
        entries.append(FileEntry(path=archive_path, size=size, sha256=digest))
    return entries


# ── manifest ────────────────────────────────────────────────────────────────


def build_manifest(
    *,
    config: CutoverConfig,
    cutover_in_progress: bool,
    previously_in_progress: bool,
    in_flight_count: int,
    drained_count: int,
    marked_indeterminate_count: int,
    timed_out: bool,
    wal_checkpoint: WalCheckpointResult,
    file_entries: Sequence[FileEntry],
    bundle_sha256: str,
    now: float | None = None,
) -> dict[str, Any]:
    """Assemble the canonical, content-addressed backup manifest.

    The manifest binds the immutable :class:`CutoverConfig` (including
    ``north_star_runtime_binding``), records the quiesce/drain/checkpoint
    state, lists every per-file ``sha256``, and carries the canonical bundle
    hash. A self ``content_hash`` (``sha256`` over the canonical manifest JSON
    excluding ``content_hash`` itself) makes any post-hoc tampering detectable.
    """
    timestamp = time.strftime(
        "%Y-%m-%dT%H:%M:%SZ", time.gmtime(now if now is not None else time.time())
    )

    manifest: dict[str, Any] = {
        "schema": BACKUP_MANIFEST_SCHEMA,
        "generated_at": timestamp,
        "hash_algorithm": HASH_ALGORITHM,
        "quiesce_state": {
            "cutover_in_progress": cutover_in_progress,
            "previously_in_progress": previously_in_progress,
            "in_flight_enumerated": in_flight_count,
            "drained": drained_count,
            "marked_indeterminate": marked_indeterminate_count,
            "drain_timed_out": timed_out,
        },
        "wal_checkpoint": {
            "mode": wal_checkpoint.mode,
            "busy": wal_checkpoint.busy,
            "log_frames": wal_checkpoint.log_frames,
            "checkpointed_frames": wal_checkpoint.checkpointed_frames,
        },
        "cutover_config": {
            "source_revision": config.source_revision,
            "target_revision": config.target_revision,
            "schema_version": config.schema_version,
            "wbc_contract_hash": config.wbc_contract_hash,
            "m6_oracle_hash": config.m6_oracle_hash,
            "corpus_fixture_hash": config.corpus_fixture_hash,
            "operator_approval_revision": config.operator_approval_revision,
            "backup_identity": config.backup_identity,
            "build_revision": config.build_revision,
            "north_star_runtime_binding": config.north_star_runtime_binding,
        },
        "file_count": len(file_entries),
        "files": [
            {"path": e.path, "size": e.size, "sha256": e.sha256}
            for e in file_entries
        ],
        "bundle_sha256": bundle_sha256,
    }

    # Content-address the canonical manifest (content_hash excluded) so
    # tampering with any field — including north_star_runtime_binding — is
    # detectable on re-verification.
    canonical = json.dumps(manifest, sort_keys=True, ensure_ascii=False)
    manifest["content_hash"] = "sha256:" + hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()
    return manifest


def manifest_bundle_hash(manifest: dict[str, Any]) -> str:
    """Re-derive the canonical bundle hash from a manifest's file list.

    Pure function over ``manifest["files"]`` — used by verifiers that only have
    the manifest (not the snapshot bytes) to confirm the bundle hash matches.
    """
    entries = [
        FileEntry(
            path=f["path"],
            size=int(f["size"]),
            sha256=f["sha256"],
        )
        for f in manifest.get("files", [])
    ]
    return compute_bundle_hash(entries)


def verify_manifest_content_hash(manifest: dict[str, Any]) -> bool:
    """Return whether the manifest's ``content_hash`` matches its canonical body."""
    stored = manifest.get("content_hash")
    if not isinstance(stored, str) or not stored.startswith("sha256:"):
        return False
    body = {k: v for k, v in manifest.items() if k != "content_hash"}
    canonical = json.dumps(body, sort_keys=True, ensure_ascii=False)
    expected = "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return stored == expected


# ── tarball ─────────────────────────────────────────────────────────────────


def write_tarball(
    manifest: dict[str, Any],
    snapshot: Sequence[tuple[Path, str]],
    output_path: str | Path,
) -> str:
    """Write a deterministic, content-addressed tarball to *output_path*.

    The archive contains every snapshot file plus the manifest at
    ``manifest.json``. Members are added in sorted archive-path order with a
    fixed mtime so the archive is byte-reproducible from the same inputs. The
    manifest is written last (its ``content_hash`` already covers it), so the
    tarball is self-describing.
    """
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    tar_path = out.resolve()

    sorted_snapshot = sorted(snapshot, key=lambda pair: pair[1])
    manifest_bytes = json.dumps(
        manifest, sort_keys=True, ensure_ascii=False, indent=2
    ).encode("utf-8")

    # Use no compression so the archive is fully deterministic and the per-file
    # hashes can be verified by re-reading raw member bytes.
    with tarfile.open(tar_path, mode="w") as tar:
        for abs_path, archive_path in sorted_snapshot:
            info = tarfile.TarInfo(name=archive_path)
            info.size = abs_path.stat().st_size
            info.mtime = _TARBALL_FIXED_MTIME
            info.mode = 0o644
            with open(abs_path, "rb") as fh:
                tar.addfile(info, fh)
        # Append the manifest so the archive is self-describing.
        m_info = tarfile.TarInfo(name=MANIFEST_TAR_ENTRY)
        m_info.size = len(manifest_bytes)
        m_info.mtime = _TARBALL_FIXED_MTIME
        m_info.mode = 0o644
        tar.addfile(m_info, io.BytesIO(manifest_bytes))

    return str(tar_path)


def verify_tarball(
    tarball_path: str | Path,
) -> dict[str, Any]:
    """Independently verify a backup tarball against its embedded manifest.

    Re-reads every snapshot member from the archive, recomputes its ``sha256``,
    checks it against the manifest's per-file hash, and re-derives the bundle
    hash from the manifest file list. Raises :class:`BackupError` on any
    mismatch so callers can treat the tarball as authoritative-or-rejected.

    Returns the embedded manifest on success.
    """
    path = Path(tarball_path)
    if not path.is_file():
        raise BackupError(f"Tarball {path!s} does not exist.")
    with tarfile.open(path, mode="r") as tar:
        members = {m.name: m for m in tar.getmembers()}
        if MANIFEST_TAR_ENTRY not in members:
            raise BackupError(
                f"Tarball {path!s} is missing the embedded manifest "
                f"({MANIFEST_TAR_ENTRY!r})."
            )
        manifest = json.loads(
            tar.extractfile(members[MANIFEST_TAR_ENTRY]).read().decode("utf-8")
        )
        manifest_files = {f["path"]: f for f in manifest.get("files", [])}

        # Verify every snapshot member that is NOT the manifest.
        recomputed: list[FileEntry] = []
        for name in sorted(m for m in members if m != MANIFEST_TAR_ENTRY):
            member = members[name]
            if not member.isfile():
                raise BackupError(
                    f"Tarball member {name!r} is not a regular file."
                )
            fh = tar.extractfile(member)
            if fh is None:  # pragma: no cover - defensive
                raise BackupError(f"Could not read tarball member {name!r}.")
            h = hashlib.new(HASH_ALGORITHM)
            size = 0
            for chunk in iter(lambda: fh.read(1 << 16), b""):
                h.update(chunk)
                size += len(chunk)
            digest = h.hexdigest()
            expected = manifest_files.get(name)
            if expected is None:
                raise BackupError(
                    f"Tarball member {name!r} is not listed in the manifest."
                )
            if expected["sha256"] != digest:
                raise BackupError(
                    f"Per-file hash mismatch for {name!r}: manifest "
                    f"{expected['sha256']!r} != recomputed {digest!r}."
                )
            if int(expected["size"]) != size:
                raise BackupError(
                    f"Size mismatch for {name!r}: manifest "
                    f"{expected['size']} != recomputed {size}."
                )
            recomputed.append(
                FileEntry(path=name, size=size, sha256=digest)
            )

        # Every manifest file entry must be present in the tarball.
        missing = set(manifest_files) - {
            m for m in members if m != MANIFEST_TAR_ENTRY
        }
        if missing:
            raise BackupError(
                f"Manifest lists files missing from the tarball: {sorted(missing)}."
            )

        # Re-derive the bundle hash from the manifest file list.
        if manifest.get("bundle_sha256") != compute_bundle_hash(
            [
                FileEntry(
                    path=f["path"], size=int(f["size"]), sha256=f["sha256"]
                )
                for f in manifest["files"]
            ]
        ):
            raise BackupError(
                "Manifest bundle_sha256 does not match the re-derived bundle "
                "hash from its own file list."
            )

        # Re-derive the per-file bundle from the recomputed (post-extract) hashes.
        if manifest["bundle_sha256"] != compute_bundle_hash(recomputed):
            raise BackupError(
                "Recomputed per-file bundle hash does not match the manifest; "
                "one or more tarball members diverged from the manifest."
            )

        if not verify_manifest_content_hash(manifest):
            raise BackupError(
                "Manifest content_hash does not match its canonical body; the "
                "manifest may have been tampered with."
            )

    return manifest


# ── orchestration ───────────────────────────────────────────────────────────


def create_cutover_backup(
    config: CutoverConfig,
    store: AttemptLedgerStore,
    db_path: str | Path,
    artifact_dirs: Sequence[str | Path] = (),
    output_path: str | Path | None = None,
    *,
    drain_timeout_seconds: float = 0.0,
    now: float | None = None,
) -> BackupResult:
    """Produce a verifiable cutover backup bound to *config*.

    Orchestrates: validate the immutable config → quiesce the writer → drain
    in-flight attempts to ``INDETERMINATE`` → checkpoint the SQLite WAL
    (``TRUNCATE``) → snapshot the database + artifact directories → hash every
    file and the canonical bundle → emit the content-addressed manifest (and a
    tarball when ``output_path`` is given).

    The backup is fail-closed at every step: an invalid config, an
    un-checkpointable WAL, a missing database, or an unreadable snapshot file
    raises :class:`BackupError` rather than emitting partial evidence.

    Args:
        config: The immutable cutover config; validates the North Star runtime
            binding before any snapshot is taken.
        store: The live SQLite attempt-ledger store (used to quiesce, drain,
            and checkpoint the WAL on its connection).
        db_path: Path to the database file to snapshot (after the WAL
            checkpoint).
        artifact_dirs: Additional directories to snapshot (e.g. evidence,
            manifest artifacts). Missing directories are skipped.
        output_path: When given, write a deterministic tarball there containing
            the snapshot plus the manifest.
        drain_timeout_seconds: Drain poll window before marking remaining
            attempts ``INDETERMINATE`` (default ``0.0`` = immediate fail-closed
            mark).
        now: Override the wall-clock timestamp (deterministic testing).

    Returns:
        A :class:`BackupResult` carrying the manifest and (optionally) the
        tarball path.
    """
    # 1. Bind the backup to the immutable cutover config (North Star runtime).
    validate_config(config)

    # 2. Quiesce the writer: engage the durable fence + enumerate in-flight.
    quiesce_result = quiesce(store)
    if not quiesce_result.cutover_in_progress:
        # pragma: no cover - quiesce always engages the fence.
        raise BackupError(
            "quiesce() did not engage the cutover_in_progress fence; the "
            "writer is not quiesced and the snapshot would be inconsistent."
        )

    # 3. Drain remaining in-flight attempts to INDETERMINATE (fail-closed).
    drain_result = drain(store, timeout_seconds=drain_timeout_seconds)

    # 4. Checkpoint the SQLite WAL so the main db file holds every frame.
    wal = checkpoint_wal(store)

    # 5. Snapshot the database file + artifact directories and hash each file.
    snapshot = collect_snapshot(db_path, artifact_dirs)
    file_entries = hash_snapshot(snapshot)

    # 6. Canonical bundle hash over the (path, sha256) pairs.
    bundle_sha256 = compute_bundle_hash(file_entries)

    # 7. Assemble the content-addressed manifest bound to the config.
    manifest = build_manifest(
        config=config,
        cutover_in_progress=quiesce_result.cutover_in_progress,
        previously_in_progress=quiesce_result.previously_in_progress,
        in_flight_count=len(quiesce_result.in_flight),
        drained_count=len(drain_result.drained),
        marked_indeterminate_count=len(drain_result.marked_indeterminate),
        timed_out=drain_result.timed_out,
        wal_checkpoint=wal,
        file_entries=file_entries,
        bundle_sha256=bundle_sha256,
        now=now,
    )

    # 8. Optionally emit the verifiable tarball.
    tarball_path: str | None = None
    if output_path is not None:
        tarball_path = write_tarball(manifest, snapshot, output_path)

    return BackupResult(manifest=manifest, tarball=tarball_path)


__all__ = [
    "BACKUP_MANIFEST_SCHEMA",
    "BackupError",
    "BackupResult",
    "DATABASE_TAR_PREFIX",
    "FileEntry",
    "HASH_ALGORITHM",
    "MANIFEST_TAR_ENTRY",
    "WalCheckpointResult",
    "build_manifest",
    "checkpoint_wal",
    "collect_snapshot",
    "compute_bundle_hash",
    "create_cutover_backup",
    "hash_file",
    "hash_snapshot",
    "manifest_bundle_hash",
    "verify_manifest_content_hash",
    "verify_tarball",
    "write_tarball",
]
