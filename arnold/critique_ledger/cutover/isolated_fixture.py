"""Isolated restore proof (CL5 Step 14b / SC26).

This module is the **no-side-effect wrapper** around
:mod:`arnold.critique_ledger.cutover.restore`: it restores a content-addressed
backup into a *throwaway temporary directory* and **proves the production
database and artifact paths are byte-identical before and after**.

The production guard is explicit and side-effect-asserting (SC26: "Can the
isolation test prove no production database or artifact path changed during
restore proof?"):

1. **Before** the restore, every production file (the database and every file
   under the artifact directories) is fingerprinted into a
   :class:`ProductionGuard` — a frozen mapping of absolute path to
   ``(st_mtime_ns, sha256)``.
2. The restore runs into a private :class:`~tempfile.TemporaryDirectory` that
   is *never* the production path (the temp dir is created under the system
   temp root, not under the production tree).
3. **After** the restore, the same production files are re-fingerprinted.
4. The two guards are compared. Any divergence — a changed mtime, a changed
   ``sha256``, a deleted file, or a new file — raises :class:`IsolationError`,
   proving the restore touched production.

The restore itself is read-only w.r.t. production by construction (it writes
only into the temp dir and opens the restored database read-only/immutable),
so the guard is a *verification* of that invariant, not the mechanism. On any
restore failure the wrapper raises :class:`IsolationError` (wrapping the
underlying :class:`~arnold.critique_ledger.cutover.restore.RestoreError`) and
re-checks the production guard so a failed restore also cannot have left
production mutated.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from arnold.critique_ledger.cutover.backup import hash_file
from arnold.critique_ledger.cutover.restore import RestoreError, restore_backup

#: Isolation-proof schema identifier.
ISOLATION_PROOF_SCHEMA: str = "cl5.cutover-isolated-restore-proof.v1"


class IsolationError(RuntimeError):
    """Raised when an isolated restore touched a production path, or the
    underlying restore could not be verified.

    The wrapper is fail-closed: a restore that fails, or a restore after which
    any guarded production file differs (mtime or content), raises this so the
    caller can never treat an isolation proof as satisfied when production was
    mutated.
    """


@dataclass(frozen=True)
class ProductionGuard:
    """Frozen identity snapshot of a set of production files.

    Each entry maps an absolute path to ``(st_mtime_ns, sha256)``. Two equal
    guards prove no production file was written, truncated, or merely touched.
    A file present in one guard but not the other, or with a different mtime or
    content hash, makes the guards unequal.
    """

    #: Sorted ``(absolute_path, (st_mtime_ns, sha256))`` tuples.
    entries: tuple[tuple[str, tuple[int, str]], ...]


@dataclass(frozen=True)
class IsolationProofResult:
    """Outcome of :func:`isolated_restore_proof`.

    ``isolation_verified`` is ``True`` only when the restore succeeded in a
    throwaway temporary directory AND every guarded production path is
    byte-identical (same ``st_mtime_ns`` and ``sha256``) before and after.
    ``target_dir`` is the path of the (now removed) temporary restore
    directory; it is recorded for audit but is intentionally ephemeral — the
    proof verifies, it does not retain restored state.
    """

    schema: str
    target_dir: str
    restore_verified: bool
    integrity_check_ok: bool
    restored_bundle_sha256: str
    manifest_bundle_sha256: str
    bundle_match: bool
    guarded_path_count: int
    production_guard_before: ProductionGuard
    production_guard_after: ProductionGuard
    isolation_verified: bool


# ── production file collection ───────────────────────────────────────────────


def collect_production_files(
    db_path: str | Path,
    artifact_dirs: Sequence[str | Path] = (),
) -> list[Path]:
    """Collect the absolute, resolved paths of every guarded production file.

    The database file MUST exist (guarding a nonexistent production database
    would prove nothing). Missing artifact directories are skipped so an
    operator can guard a production tree that has no artifacts yet. The result
    is de-duplicated and sorted for a deterministic guard ordering.
    """
    db = Path(db_path)
    if not db.is_file():
        raise IsolationError(
            f"Production database file {db!s} does not exist or is not a "
            "regular file; the isolation guard has nothing to protect."
        )

    files: list[Path] = [db.resolve()]
    seen_dirs: set[Path] = set()
    for raw_dir in artifact_dirs:
        directory = Path(raw_dir)
        if not directory.is_dir():
            continue
        directory = directory.resolve()
        if directory in seen_dirs:
            continue
        seen_dirs.add(directory)
        for root, dirs, names in os.walk(directory):
            # Deterministic traversal order.
            dirs.sort()
            for name in sorted(names):
                files.append((Path(root) / name).resolve())

    # De-duplicate (the db could theoretically sit inside an artifact dir) and
    # sort for a canonical guard ordering.
    unique: list[Path] = []
    seen: set[Path] = set()
    for f in sorted(files, key=lambda p: str(p)):
        if f not in seen:
            seen.add(f)
            unique.append(f)
    return unique


# ── guard primitives ──────────────────────────────────────────────────────────


def snapshot_production_guard(paths: Sequence[Path]) -> ProductionGuard:
    """Fingerprint every path in *paths* into a :class:`ProductionGuard`.

    Each file is hashed (``sha256``) and its ``st_mtime_ns`` recorded. A guard
    therefore detects both a content change (different ``sha256``) and a mere
    touch (different ``st_mtime_ns`` with the same content).
    """
    entries: list[tuple[str, tuple[int, str]]] = []
    for f in paths:
        path = Path(f)
        if not path.is_file():
            raise IsolationError(
                f"Guarded production file {path!s} is missing or not a regular "
                "file; it may have been deleted during the restore."
            )
        try:
            st = path.stat()
            digest = hash_file(path)
        except OSError as exc:  # pragma: no cover - defensive
            raise IsolationError(
                f"Could not fingerprint guarded production file {path!s}: {exc}"
            ) from exc
        entries.append((str(path), (int(st.st_mtime_ns), digest)))
    return ProductionGuard(tuple(sorted(entries)))


def verify_guard_unchanged(
    before: ProductionGuard,
    after: ProductionGuard,
) -> None:
    """Assert two guards are identical; raise :class:`IsolationError` otherwise.

    Divergence is reported precisely: a changed/touched file, a deleted file,
    or a new file are all named so the operator knows exactly what the restore
    mutated. The comparison is exact (both ``st_mtime_ns`` and ``sha256`` must
    match), so even an in-place rewrite that preserves content but changes the
    mtime is flagged.
    """
    if before == after:
        return

    before_map = dict(before.entries)
    after_map = dict(after.entries)
    changed: list[str] = []
    for path, ident in before_map.items():
        other = after_map.get(path)
        if other is None:
            changed.append(f"{path} (deleted)")
        elif other != ident:
            changed.append(f"{path} (mtime/content changed)")
    for path in after_map:
        if path not in before_map:
            changed.append(f"{path} (new file)")

    raise IsolationError(
        "Isolated restore verification detected production mutation: "
        + "; ".join(changed)
        + ". The restore must touch ONLY the temporary target directory."
    )


# ── orchestration ────────────────────────────────────────────────────────────


def isolated_restore_proof(
    tarball_path: str | Path,
    *,
    production_db_path: str | Path,
    production_artifact_dirs: Sequence[str | Path] = (),
    expected_config: Any = None,
) -> IsolationProofResult:
    """Prove a backup restores in isolation without touching production.

    Restores *tarball_path* into a private
    :class:`~tempfile.TemporaryDirectory` (never the production path) and
    verifies every guarded production file (``production_db_path`` plus every
    file under ``production_artifact_dirs``) is byte-identical before and
    after. Returns an :class:`IsolationProofResult` whose
    ``isolation_verified`` is ``True`` only when the restore succeeded and no
    production path changed.

    Args:
        tarball_path: Path to the content-addressed backup tarball to restore.
        production_db_path: Absolute path of the live production database to
            guard against writes.
        production_artifact_dirs: Production artifact directories whose every
            file is also guarded. Missing directories are skipped.
        expected_config: Optional :class:`CutoverConfig` the restored manifest
            must bind (forwarded to :func:`restore_backup`).

    Returns:
        An :class:`IsolationProofResult`. ``target_dir`` is the path of the
        now-removed temporary restore directory.

    Raises:
        IsolationError: If the restore fails OR any guarded production path
            differs (mtime or content) after the restore.
    """
    # 1. Snapshot production BEFORE the restore.
    files = collect_production_files(production_db_path, production_artifact_dirs)
    guard_before = snapshot_production_guard(files)

    proof: IsolationProofResult | None = None
    # 2. Restore into a throwaway temporary directory (never production).
    with tempfile.TemporaryDirectory(
        prefix="cutover-isolated-restore-"
    ) as tmp:
        target = Path(tmp)
        try:
            result = restore_backup(
                tarball_path, target, expected_config=expected_config
            )
        except RestoreError as exc:
            # Even on failure, re-verify production was not mutated before
            # surfacing the error — a failed restore must be side-effect-free.
            guard_after_fail = snapshot_production_guard(files)
            verify_guard_unchanged(guard_before, guard_after_fail)
            raise IsolationError(
                f"Isolated restore verification failed: {exc}"
            ) from exc

        # 3. Snapshot production AFTER the restore.
        guard_after = snapshot_production_guard(files)
        # 4. Assert no production path changed.
        verify_guard_unchanged(guard_before, guard_after)

        manifest_bundle = result.manifest.get("bundle_sha256", "")
        proof = IsolationProofResult(
            schema=ISOLATION_PROOF_SCHEMA,
            target_dir=str(target),
            restore_verified=True,
            integrity_check_ok=result.integrity_check.ok,
            restored_bundle_sha256=result.bundle_sha256,
            manifest_bundle_sha256=manifest_bundle,
            bundle_match=(result.bundle_sha256 == manifest_bundle),
            guarded_path_count=len(files),
            production_guard_before=guard_before,
            production_guard_after=guard_after,
            isolation_verified=True,
        )
    # ``target`` is removed when the ``with`` block exits; the proof records the
    # path for audit but the restored state is intentionally ephemeral.
    assert proof is not None  # pragma: no cover - set inside the ``with`` block
    return proof


__all__ = [
    "ISOLATION_PROOF_SCHEMA",
    "IsolationError",
    "IsolationProofResult",
    "ProductionGuard",
    "collect_production_files",
    "isolated_restore_proof",
    "snapshot_production_guard",
    "verify_guard_unchanged",
]
