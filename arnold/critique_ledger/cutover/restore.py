"""Cutover backup restore and verification (CL5 Step 14).

This module is the **fail-closed inverse** of
:mod:`arnold.critique_ledger.cutover.backup`: given a content-addressed backup
tarball, it verifies the archive *before* extraction, restores the snapshot
into a target directory, runs ``PRAGMA integrity_check`` on the restored
SQLite database, **replays the content-addressed projection** (re-deriving the
``(path, sha256)`` file projection from the restored bytes and recomputing the
canonical bundle hash), and **fails closed** unless the restored projection
hashes equal the manifest.

The restore is authoritative-or-rejected at every gate, in the exact order
prescribed by CL5 Step 14:

1. **Archive gate** — :func:`~arnold.critique_ledger.cutover.backup.verify_tarball`
   re-reads every tarball member, recomputes its ``sha256``, re-derives the
   bundle hash from the manifest file list, and checks the manifest
   ``content_hash``. This runs *before* any file is extracted, so a tampered,
   truncated, or unlisted-member archive is rejected before it can pollute the
   target directory.
2. **Extraction** — every snapshot member (never the embedded manifest) is
   written under ``target_dir`` preserving its archive path. Path-traversal
   members are rejected.
3. **Database gate** — ``PRAGMA integrity_check`` runs on the restored database
   opened read-only/immutable so no ``-wal``/``-shm`` sidecar pollutes the
   target; anything other than ``ok`` fails closed.
4. **Projection gate** — the restored files are re-hashed into
   :class:`~arnold.critique_ledger.cutover.backup.FileEntry` records, the
   per-file hashes and sizes are checked against the manifest, the file set is
   checked for extras/omissions, and the canonical bundle hash is recomputed
   and compared to ``manifest.bundle_sha256``. Any divergence fails closed.

On any gate failure the restore raises :class:`RestoreError`, removes the
files it extracted, and never returns a :class:`RestoreResult` — so the target
directory never holds an unverified "restored state". A successful return is
the only way restored state is exposed.
"""

from __future__ import annotations

import hashlib
import sqlite3
import tarfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from arnold.critique_ledger.cutover.backup import (
    BACKUP_MANIFEST_SCHEMA,
    DATABASE_TAR_PREFIX,
    HASH_ALGORITHM,
    FileEntry,
    MANIFEST_TAR_ENTRY,
    compute_bundle_hash,
    hash_file,
    verify_manifest_content_hash,
    verify_tarball,
)

#: Restore-result schema identifier.
RESTORE_RESULT_SCHEMA: str = "cl5.cutover-restore-result.v1"

#: The canonical ``PRAGMA integrity_check`` success token.
INTEGRITY_CHECK_OK: str = "ok"


class RestoreError(RuntimeError):
    """Raised when a cutover backup cannot be verified or restored.

    The restore is fail-closed: a tampered archive, a path-traversal member, a
    database that fails ``integrity_check``, a missing/extra restored file, a
    per-file hash/size mismatch, or a bundle-hash divergence all abort the
    restore rather than exposing partial state.
    """


@dataclass(frozen=True)
class IntegrityCheckResult:
    """Outcome of ``PRAGMA integrity_check`` on the restored database.

    ``ok`` is ``True`` exactly when the check returns the single token
    ``["ok"]``. ``output`` carries the raw rows so a failure is diagnosable.
    """

    ok: bool
    output: tuple[str, ...]


@dataclass(frozen=True)
class RestoreResult:
    """Verified cutover backup restore.

    A :class:`RestoreResult` is returned ONLY after every gate passes; the
    restored state is therefore always verified before it is exposed.
    """

    #: The verified manifest embedded in (and re-read from) the tarball.
    manifest: dict[str, Any]
    #: Absolute path the snapshot was restored into.
    target_dir: str
    #: Archive paths of the files restored, in canonical sorted order.
    restored_files: tuple[str, ...]
    #: Absolute path of the restored database file (or ``None`` if none).
    database_path: str | None
    #: Recomputed canonical bundle hash over the restored files.
    bundle_sha256: str
    #: The ``integrity_check`` outcome for the restored database.
    integrity_check: IntegrityCheckResult


# ── primitives ───────────────────────────────────────────────────────────────


def _hash_bytes(data: bytes) -> str:
    """Return the ``sha256`` hex digest of *data* using :data:`HASH_ALGORITHM`."""
    return hashlib.new(HASH_ALGORITHM, data).hexdigest()


def _restore_member_path(target_dir: Path, archive_path: str) -> Path:
    """Resolve *archive_path* under *target_dir*, rejecting traversal.

    A member that is absolute, contains a drive, or escapes the target via
    ``..`` is rejected so a malicious archive cannot write outside the restore
    directory. The resolved path is checked to stay within ``target_dir``.
    """
    if not archive_path or archive_path.startswith("/"):
        raise RestoreError(
            f"Tarball member {archive_path!r} has an absolute path; refusing "
            "to extract outside the target directory."
        )
    # Reject any backslash-driven or drive-prefixed path.
    if "\\" in archive_path or len(archive_path) > 1 and archive_path[1] == ":":
        raise RestoreError(
            f"Tarball member {archive_path!r} uses a disallowed path form."
        )
    parts = Path(archive_path).parts
    if any(part == ".." for part in parts):
        raise RestoreError(
            f"Tarball member {archive_path!r} contains a '..' component; "
            "refusing to extract outside the target directory."
        )
    resolved = (target_dir / archive_path).resolve()
    try:
        resolved.relative_to(target_dir.resolve())
    except ValueError as exc:
        raise RestoreError(
            f"Tarball member {archive_path!r} resolves outside the target "
            f"directory {target_dir!s}."
        ) from exc
    return resolved


def _readonly_immutable_uri(db_path: Path) -> str:
    """Build a ``file:`` URI opening *db_path* read-only and immutable.

    ``immutable=1`` tells SQLite the file cannot be modified by any process,
    so it neither requires nor creates the ``-wal``/``-shm`` sidecars — keeping
    the restored target directory byte-identical to the manifest projection
    while still allowing ``PRAGMA integrity_check``.
    """
    posix = db_path.resolve().as_posix()
    # Absolute POSIX paths begin with '/'; the URI authority is empty so the
    # path is taken literally. Relative paths (tests) are handled too.
    if not posix.startswith("/"):
        posix = "/" + posix
    return f"file:{posix}?mode=ro&immutable=1"


# ── database integrity ───────────────────────────────────────────────────────


def run_integrity_check(db_path: str | Path) -> IntegrityCheckResult:
    """Run ``PRAGMA integrity_check`` on the restored database file.

    The database is opened read-only/immutable so the restore never creates
    ``-wal``/``-shm`` sidecars in the target directory. Returns
    :class:`IntegrityCheckResult`; the caller decides whether to fail closed.
    """
    path = Path(db_path)
    if not path.is_file():
        raise RestoreError(
            f"Restored database file {path!s} does not exist or is not a "
            "regular file; integrity_check cannot run."
        )
    uri = _readonly_immutable_uri(path)
    try:
        conn = sqlite3.connect(uri, uri=True)
    except sqlite3.Error as exc:
        raise RestoreError(
            f"Could not open restored database {path!s} for integrity_check: "
            f"{exc}"
        ) from exc
    try:
        rows = conn.execute("PRAGMA integrity_check").fetchall()
    except sqlite3.Error as exc:
        raise RestoreError(
            f"PRAGMA integrity_check failed on {path!s}: {exc}"
        ) from exc
    finally:
        conn.close()
    output = tuple(str(row[0]) for row in rows)
    return IntegrityCheckResult(ok=(output == (INTEGRITY_CHECK_OK,)), output=output)


# ── extraction ───────────────────────────────────────────────────────────────


def extract_tarball(
    tarball_path: str | Path,
    target_dir: str | Path,
) -> tuple[list[str], list[Path]]:
    """Extract every snapshot member of the tarball into *target_dir*.

    The embedded manifest member (:data:`MANIFEST_TAR_ENTRY`) is intentionally
    NOT extracted — it is restored only as the in-memory manifest via
    :func:`~arnold.critique_ledger.cutover.backup.verify_tarball`. Only regular
    file members are extracted; directories, symlinks, and devices are rejected
    so the restore writes a flat, verifiable file set.

    Returns ``(restored_archive_paths, created_directories)``:
    * ``restored_archive_paths`` — sorted archive paths of the files written.
    * ``created_directories`` — directories created during extraction, in
      creation order, so a failed restore can clean them up.

    Raises :class:`RestoreError` for any non-regular member or path traversal.
    """
    tar_path = Path(tarball_path)
    if not tar_path.is_file():
        raise RestoreError(f"Tarball {tar_path!s} does not exist.")
    target = Path(target_dir)
    target.mkdir(parents=True, exist_ok=True)

    restored: list[str] = []
    created_dirs: list[Path] = []
    with tarfile.open(tar_path, mode="r") as tar:
        for member in tar.getmembers():
            if member.name == MANIFEST_TAR_ENTRY:
                continue
            if member.isdir():
                # The backup stores a flat file set; a directory member is
                # unexpected and would not be covered by the manifest file
                # projection. Reject rather than silently materialize it.
                raise RestoreError(
                    f"Tarball member {member.name!r} is a directory; the "
                    "restore expects a flat regular-file snapshot only."
                )
            if not member.isfile():
                raise RestoreError(
                    f"Tarball member {member.name!r} is not a regular file "
                    "(symlink/device/hardlink); refusing to extract."
                )
            dest = _restore_member_path(target, member.name)
            dest.parent.mkdir(parents=True, exist_ok=True)
            # Track directories we create so a failed restore can clean them.
            parent = dest.parent
            while parent != target.resolve() and parent != target:
                if parent not in created_dirs and not parent.exists():
                    created_dirs.append(parent)
                elif parent not in created_dirs and parent.exists():
                    # Pre-existing directory; stop climbing so we never delete
                    # caller-owned directories.
                    break
                parent = parent.parent
            fh = tar.extractfile(member)
            if fh is None:  # pragma: no cover - defensive
                raise RestoreError(
                    f"Could not read tarball member {member.name!r}."
                )
            data = fh.read()
            dest.write_bytes(data)
            restored.append(member.name)

    return sorted(restored), created_dirs


# ── projection replay ────────────────────────────────────────────────────────


def replay_projections(
    target_dir: str | Path,
    manifest: dict[str, Any],
) -> tuple[list[FileEntry], str]:
    """Re-derive the content-addressed projection from the restored files.

    For every file listed in ``manifest["files"]`` the restored bytes are
    re-read from ``target_dir/<archive_path>``, re-hashed, and checked against
    the manifest per-file ``sha256`` and ``size``. The restored file set is
    required to be exactly the manifest file set (no missing files, no extras),
    and the canonical bundle hash is recomputed from the restored
    :class:`FileEntry` records.

    Returns ``(restored_entries, restored_bundle_sha256)``. Raises
    :class:`RestoreError` on any missing/extra file, per-file hash/size
    mismatch, or bundle-hash divergence from ``manifest.bundle_sha256``.

    This is the deterministic projection replay: the same pure
    :func:`~arnold.critique_ledger.cutover.backup.compute_bundle_hash` over the
    same sorted ``(path, sha256)`` pairs must reproduce the manifest bundle —
    proving the restored bytes are byte-identical to the snapshotted state.
    """
    target = Path(target_dir)
    manifest_files = manifest.get("files", [])
    manifest_by_path = {f["path"]: f for f in manifest_files}

    restored_entries: list[FileEntry] = []
    seen: set[str] = set()
    for entry in manifest_files:
        archive_path = entry["path"]
        if archive_path in seen:  # pragma: no cover - manifest is content-hashed
            raise RestoreError(
                f"Manifest lists duplicate path {archive_path!r}."
            )
        seen.add(archive_path)
        restored_file = target / archive_path
        if not restored_file.is_file():
            raise RestoreError(
                f"Restored file {archive_path!r} is missing from the target "
                f"directory {target!s}; projection replay cannot continue."
            )
        try:
            digest = hash_file(restored_file)
            size = restored_file.stat().st_size
        except OSError as exc:
            raise RestoreError(
                f"Could not re-hash restored file {restored_file!s}: {exc}"
            ) from exc
        expected_sha = entry.get("sha256")
        expected_size = entry.get("size")
        if expected_sha != digest:
            raise RestoreError(
                f"Restored per-file hash mismatch for {archive_path!r}: "
                f"manifest {expected_sha!r} != restored {digest!r}."
            )
        if int(expected_size) != size:
            raise RestoreError(
                f"Restored size mismatch for {archive_path!r}: manifest "
                f"{expected_size} != restored {size}."
            )
        restored_entries.append(
            FileEntry(path=archive_path, size=size, sha256=digest)
        )

    # Reject any extra files the restore wrote that the manifest does not list.
    restored_paths = set(seen)
    extra: list[str] = []
    for found in sorted(target.rglob("*")):
        if not found.is_file():
            continue
        rel = found.relative_to(target).as_posix()
        if rel == MANIFEST_TAR_ENTRY:
            continue
        if rel not in restored_paths:
            extra.append(rel)
    if extra:
        raise RestoreError(
            f"Restored target directory contains files not listed in the "
            f"manifest: {extra}. The projection must be byte-for-byte the "
            "manifest file set."
        )

    restored_bundle = compute_bundle_hash(restored_entries)
    expected_bundle = manifest.get("bundle_sha256")
    if expected_bundle != restored_bundle:
        raise RestoreError(
            f"Restored projection bundle hash diverges from manifest: "
            f"manifest {expected_bundle!r} != restored {restored_bundle!r}."
        )

    return restored_entries, restored_bundle


# ── cleanup ──────────────────────────────────────────────────────────────────


def _cleanup_partial_restore(
    target_dir: Path,
    restored_archive_paths: Sequence[str],
    created_dirs: Sequence[Path],
) -> None:
    """Remove the files extracted during a failed restore.

    Only the exact files that were written and the directories created during
    extraction are removed — caller-owned pre-existing content in
    ``target_dir`` is never touched. Best-effort: cleanup errors are swallowed
    so the original :class:`RestoreError` remains the visible failure.
    """
    target = Path(target_dir)
    for archive_path in restored_archive_paths:
        try:
            (target / archive_path).unlink()
        except OSError:
            pass
    # Remove created directories from deepest to shallowest, only if now empty.
    for directory in sorted(created_dirs, key=lambda p: len(p.parts), reverse=True):
        try:
            directory.rmdir()
        except OSError:
            # Not empty (caller content landed here) or already gone — leave it.
            pass


# ── orchestration ───────────────────────────────────────────────────────────


def restore_backup(
    tarball_path: str | Path,
    target_dir: str | Path,
    *,
    expected_config: Any = None,
    cleanup_on_failure: bool = True,
) -> RestoreResult:
    """Verify and restore a content-addressed cutover backup.

    Runs the four fail-closed gates in order:

    1. **Archive gate** (:func:`verify_tarball`) — re-verifies the tarball
       *before* any extraction.
    2. **Extraction** (:func:`extract_tarball`) — writes the snapshot into
       ``target_dir``.
    3. **Database gate** (:func:`run_integrity_check`) — ``PRAGMA
       integrity_check`` on the restored database (skipped only if the
       manifest carries no database file, which a valid backup never does).
    4. **Projection gate** (:func:`replay_projections`) — re-derives the
       content-addressed projection and requires the bundle hash to equal
       ``manifest.bundle_sha256``.

    Args:
        tarball_path: Path to the content-addressed backup tarball.
        target_dir: Directory to restore the snapshot into (created if absent).
        expected_config: Optional :class:`CutoverConfig` whose North Star
            binding and revisions the restored manifest must match; supplied by
            callers that want to bind the restore to a specific cutover config.
        cleanup_on_failure: When ``True`` (default), files extracted during a
            failed restore are removed so the target directory never holds an
            unverified partial restore.

    Returns:
        A :class:`RestoreResult` — the only way restored state is exposed.

    Raises:
        RestoreError: On any archive, database, or projection mismatch. When
            ``cleanup_on_failure`` is set, the extracted files are removed
            before the error propagates.
    """
    target = Path(target_dir)

    # 1. Archive gate — verify BEFORE extraction. verify_tarball recomputes
    #    every per-file hash, re-derives the bundle hash from the manifest, and
    #    checks the manifest content_hash; it raises BackupError (a RuntimeError)
    #    on any mismatch. Wrap it so the restore surfaces a RestoreError.
    try:
        manifest = verify_tarball(tarball_path)
    except RestoreError:
        raise
    except RuntimeError as exc:
        raise RestoreError(
            f"Archive verification failed before extraction: {exc}"
        ) from exc
    if manifest.get("schema") != BACKUP_MANIFEST_SCHEMA:
        raise RestoreError(
            f"Embedded manifest schema {manifest.get('schema')!r} is not "
            f"{BACKUP_MANIFEST_SCHEMA!r}."
        )
    if not verify_manifest_content_hash(manifest):
        raise RestoreError(
            "Embedded manifest content_hash does not match its canonical body."
        )

    # Optional config binding: the restored manifest must carry the caller's
    # exact North Star runtime binding.
    if expected_config is not None:
        from arnold.critique_ledger.cutover.config import validate_config

        validate_config(expected_config)
        embedded = manifest.get("cutover_config", {})
        for field in (
            "source_revision",
            "target_revision",
            "schema_version",
            "wbc_contract_hash",
            "m6_oracle_hash",
            "corpus_fixture_hash",
            "operator_approval_revision",
            "backup_identity",
            "build_revision",
            "north_star_runtime_binding",
        ):
            if embedded.get(field) != getattr(expected_config, field):
                raise RestoreError(
                    f"Restored backup does not bind the expected config field "
                    f"{field!r}: manifest {embedded.get(field)!r} != expected "
                    f"{getattr(expected_config, field)!r}."
                )

    # 2. Extraction.
    restored_paths, created_dirs = extract_tarball(tarball_path, target)

    try:
        # Locate the restored database (backup always stores exactly one under
        # DATABASE_TAR_PREFIX).
        db_entries = [
            f
            for f in manifest.get("files", [])
            if str(f["path"]).startswith(DATABASE_TAR_PREFIX + "/")
        ]
        database_path: str | None = None
        if db_entries:
            if len(db_entries) > 1:
                raise RestoreError(
                    f"Manifest lists {len(db_entries)} database files; exactly "
                    "one is expected under the database/ prefix."
                )
            database_path = str((target / db_entries[0]["path"]).resolve())

            # 3. Database gate — integrity_check on the restored database.
            integrity = run_integrity_check(database_path)
            if not integrity.ok:
                raise RestoreError(
                    f"SQLite integrity_check failed on the restored database "
                    f"{database_path!r}: {list(integrity.output)}."
                )
        else:
            # A valid cutover backup always snapshots the database; reaching
            # here means the archive was tampered post-verify (the manifest is
            # content-hashed), so fail closed defensively.
            raise RestoreError(
                "Restored manifest lists no database file; a cutover backup "
                "must contain exactly one."
            )

        # 4. Projection gate — replay the content-addressed projection.
        restored_entries, bundle_sha256 = replay_projections(target, manifest)

    except RestoreError:
        if cleanup_on_failure:
            _cleanup_partial_restore(target, restored_paths, created_dirs)
        raise

    return RestoreResult(
        manifest=manifest,
        target_dir=str(target.resolve()),
        restored_files=tuple(restored_paths),
        database_path=database_path,
        bundle_sha256=bundle_sha256,
        integrity_check=IntegrityCheckResult(ok=True, output=(INTEGRITY_CHECK_OK,))
        if database_path is not None
        else IntegrityCheckResult(ok=True, output=()),
    )


__all__ = [
    "INTEGRITY_CHECK_OK",
    "RESTORE_RESULT_SCHEMA",
    "IntegrityCheckResult",
    "RestoreError",
    "RestoreResult",
    "extract_tarball",
    "replay_projections",
    "restore_backup",
    "run_integrity_check",
]
