"""Guarded recovery for a failed cloud bootstrap before chain authority exists.

This seam is intentionally narrower than a chain restart.  It only repairs the
source/runtime boundary after a launch recorded a failed, non-advanced outcome;
the chain state, runner custody, and old runtime generation remain untouched.
All durable control evidence is written through the existing chain-control
journal and the per-runtime manifest writer.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from arnold_pipelines.megaplan.chain import spec as chain_spec
from arnold_pipelines.megaplan.cloud.runtime_manifest import (
    ManifestError,
    cutover_runtime_manifest,
    load_manifest,
    write_manifest,
)
from arnold_pipelines.megaplan.types import CliError


RECOVERY_ERROR = "failed_prechain_recovery_refused"
RECOVERY_SCHEMA = "arnold.megaplan.failed-prechain-recovery.v1"
RECOVERY_INTENT = "failed_prechain_recovery"
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SECRET_TEXT = re.compile(
    r"(?:api[_-]?key|access[_-]?token|bearer\s+|password|secret|gh[pousr]_|sk-[A-Za-z0-9])",
    re.IGNORECASE,
)
_OCCUPANCY_KEYS = (
    "owner", "runner", "tmux_session", "chain_pid", "worker_pid",
    "fixer_owner", "fixer_pid",
)


def _refuse(message: str, *, extra: Mapping[str, Any] | None = None) -> CliError:
    return CliError(RECOVERY_ERROR, message, extra=dict(extra or {}))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _full(value: Any, *, label: str) -> str:
    result = str(value or "").strip().lower()
    if _SHA256.fullmatch(result) is None:
        raise _refuse(f"{label} must be a full SHA-256")
    return result


def _safe_text(value: Any, *, label: str) -> str:
    result = str(value or "").strip()
    if not result:
        raise _refuse(f"{label} is required")
    if _SECRET_TEXT.search(result):
        raise _refuse(f"{label} contains credential-like material")
    return result


def _git(source: Path, *args: str, check: bool = False) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            ["git", "-C", str(source), *args],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        raise _refuse(f"git operation unavailable: {exc}") from exc
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout or "git operation failed").strip()
        raise _refuse(detail)
    return result


def _head(source: Path) -> str:
    result = _git(source, "rev-parse", "--verify", "HEAD")
    value = result.stdout.strip().lower() if result.returncode == 0 else ""
    if _SHA40.fullmatch(value) is None:
        raise _refuse("source checkout HEAD is unavailable or malformed")
    return value


def _status(source: Path) -> list[str]:
    result = _git(source, "status", "--porcelain=v1", "--untracked-files=all")
    if result.returncode != 0:
        raise _refuse("source checkout status is unavailable")
    return [line for line in result.stdout.splitlines() if line]


def _untracked(source: Path) -> list[Path]:
    result = _git(source, "ls-files", "--others", "--exclude-standard", "-z")
    if result.returncode != 0:
        raise _refuse("source checkout untracked-file inventory is unavailable")
    return [source / item for item in result.stdout.split("\0") if item]


def _dirty_fingerprint(source: Path) -> list[dict[str, Any]]:
    """Content-address every dirty path, including symlink identity."""
    rows: list[dict[str, Any]] = []
    for status in _status(source):
        if len(status) < 4:
            raise _refuse("source status contains a malformed path")
        code, relative = status[:2], status[3:].rstrip("/")
        path = source / relative
        try:
            info = path.lstat()
        except OSError as exc:
            raise _refuse("source dirty path disappeared while fingerprinting") from exc
        if path.is_symlink():
            target = os.readlink(path)
            rows.append({"path": relative, "status": code, "kind": "symlink", "target": target})
        elif path.is_file():
            rows.append({"path": relative, "status": code, "kind": "file", "sha256": _sha(path), "size": info.st_size})
        elif path.is_dir():
            rows.append({"path": relative, "status": code, "kind": "directory"})
        else:
            rows.append({"path": relative, "status": code, "kind": "other", "mode": info.st_mode})
    return sorted(rows, key=lambda row: (str(row.get("path")), str(row.get("status"))))


def _git_diff(source: Path, *, exclude_paths: tuple[str, ...] = ()) -> bytes:
    args = ["diff", "HEAD"]
    if exclude_paths:
        args.extend(["--", *[f":(exclude){item}" for item in exclude_paths]])
    return _git(source, *args).stdout.encode("utf-8")


def _archive_dirty_state(
    source: Path,
    custody_dir: Path,
    operation_id: str,
    *,
    exclude_paths: tuple[str, ...] = (),
) -> tuple[Path, dict[str, Any]]:
    """Archive tracked diff and untracked bytes once, content-addressed."""
    root = custody_dir.expanduser().resolve(strict=False) / operation_id
    manifest_path = root / "manifest.json"
    if manifest_path.is_file():
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise _refuse("existing recovery archive manifest is unreadable") from exc
        if not isinstance(payload, Mapping) or payload.get("schema") != RECOVERY_SCHEMA:
            raise _refuse("existing recovery archive has the wrong schema")
        return manifest_path, dict(payload)

    status = _status(source)
    if not status:
        raise _refuse("failed-prechain recovery requires the recorded dirty source state")
    diff = _git_diff(source, exclude_paths=exclude_paths)
    root.mkdir(parents=True, exist_ok=True)
    diff_path = root / "tracked.diff"
    diff_path.write_bytes(diff)
    entries: list[dict[str, Any]] = [{
        "path": "tracked.diff", "sha256": hashlib.sha256(diff).hexdigest(), "size": len(diff)
    }]
    for path in _untracked(source):
        if not path.is_file() and not path.is_symlink():
            raise _refuse(f"untracked recovery path is not a file or symlink: {path}")
        relative = path.relative_to(source).as_posix()
        target = root / "untracked" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if path.is_symlink():
            target.symlink_to(os.readlink(path))
            entries.append({"path": f"untracked/{relative}", "kind": "symlink", "target": os.readlink(path)})
        else:
            shutil.copyfile(path, target)
            entries.append({"path": f"untracked/{relative}", "kind": "file", "sha256": _sha(target), "size": target.stat().st_size})
    payload = {
        "schema": RECOVERY_SCHEMA,
        "operation_id": operation_id,
        "source_head": _head(source),
        "status": status,
        "worktree_fingerprint": _dirty_fingerprint(source),
        "entries": entries,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    manifest_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest_path, payload


def _verify_archive(manifest_path: Path, payload: Mapping[str, Any], operation_id: str) -> None:
    if payload.get("schema") != RECOVERY_SCHEMA or payload.get("operation_id") != operation_id:
        raise _refuse("recovery archive does not match this operation")
    entries = payload.get("entries")
    if not isinstance(entries, list) or not entries:
        raise _refuse("recovery archive has no entries")
    root = manifest_path.parent
    for row in entries:
        if not isinstance(row, Mapping) or not isinstance(row.get("path"), str):
            raise _refuse("recovery archive entry is malformed")
        path = root / row["path"]
        if row.get("kind") == "symlink":
            if not path.is_symlink() or os.readlink(path) != row.get("target"):
                raise _refuse("recovery archive symlink entry is missing or changed")
        elif not path.is_file() or _sha(path) != str(row.get("sha256") or "") or path.stat().st_size != row.get("size"):
            raise _refuse("recovery archive entry is missing or changed")


def _assert_source_archive_fingerprint(
    source: Path,
    archive_path: Path,
    payload: Mapping[str, Any],
    *,
    exclude_paths: tuple[str, ...] = (),
    before_excluded: Mapping[str, Mapping[str, Any]] | None = None,
) -> None:
    def excluded(path: str) -> bool:
        return any(path == item or path.startswith(item + "/") for item in exclude_paths)

    expected_tree = payload.get("worktree_fingerprint")
    if not isinstance(expected_tree, list):
        raise _refuse("source tracked, untracked, or symlink set differs from the archive")
    expected_rows = [row for row in expected_tree if isinstance(row, Mapping) and not excluded(str(row.get("path") or ""))]
    actual_tree = _dirty_fingerprint(source)
    actual_rows = [row for row in actual_tree if not excluded(str(row.get("path") or ""))]
    if actual_rows != expected_rows:
        raise _refuse("source tracked, untracked, or symlink set differs from the archive")
    if before_excluded is not None:
        expected_by_path = {
            str(row.get("path")): row
            for row in expected_tree
            if isinstance(row, Mapping) and str(row.get("path") or "") in exclude_paths
        }
        for path, before in before_excluded.items():
            if expected_by_path.get(path) != before:
                raise _refuse("archived journal baseline does not match the guarded workspace")
    entries = payload.get("entries") if isinstance(payload.get("entries"), list) else []
    tracked = next((row for row in entries if isinstance(row, Mapping) and row.get("path") == "tracked.diff"), None)
    if not isinstance(tracked, Mapping):
        raise _refuse("recovery archive has no tracked diff entry")
    current_diff = _git_diff(source, exclude_paths=exclude_paths)
    if hashlib.sha256(current_diff).hexdigest() != tracked.get("sha256"):
        raise _refuse("tracked source changes differ from the archived failed launch")
    for row in entries:
        if not isinstance(row, Mapping) or not str(row.get("path") or "").startswith("untracked/"):
            continue
        relative = str(row["path"])[len("untracked/"):]
        candidate = source / relative
        if row.get("kind") == "symlink":
            valid = candidate.is_symlink() and os.readlink(candidate) == row.get("target")
        else:
            valid = candidate.is_file() and _sha(candidate) == str(row.get("sha256") or "")
        if not valid:
            raise _refuse("untracked source changes differ from the archived failed launch")


def _journal_owned_paths(journal: Any, chain_id: str, workspace: Path) -> tuple[str, ...]:
    """Return only the journal paths this recovery is allowed to create/change."""
    ledger_dir = Path(journal.ledger.ledger_dir).resolve(strict=False)
    paths = [
        ledger_dir / ".events.seq",
        ledger_dir / ".events.init_ts",
        ledger_dir / "events.jsonl",
        Path(journal.scope_lock_path(chain_id)).resolve(strict=False),
        ledger_dir / ".nbf08-locks",
    ]
    relative: list[str] = []
    for path in paths:
        try:
            relative.append(path.relative_to(workspace).as_posix())
        except ValueError:
            continue
    return tuple(sorted(set(relative)))


def _journal_baseline(workspace: Path, paths: tuple[str, ...]) -> dict[str, Mapping[str, Any]]:
    rows = {str(row.get("path")): row for row in _dirty_fingerprint(workspace)}
    return {path: rows[path] for path in paths if path in rows}


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    except BaseException:
        try:
            os.unlink(name)
        except OSError:
            pass
        raise


def _atomic_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    except BaseException:
        try:
            os.unlink(name)
        except OSError:
            pass
        raise


def _occupied(marker: Mapping[str, Any]) -> str | None:
    for key in _OCCUPANCY_KEYS:
        value = marker.get(key)
        if value not in (None, False, "", [], {}, 0):
            return key
    return None


def _assert_marker(
    marker: Mapping[str, Any], *, session: str, workspace: Path, manifest_path: Path,
) -> None:
    if marker.get("session") != session:
        raise _refuse("session marker identity does not match")
    if marker.get("workspace") and Path(str(marker["workspace"])).resolve(strict=False) != workspace:
        raise _refuse("session marker workspace does not match")
    declared = marker.get("bootstrap_manifest_path") or marker.get("manifest_path")
    if declared and Path(str(declared)).resolve(strict=False) != manifest_path:
        raise _refuse("session marker manifest identity does not match")
    outcome = marker.get("launch_outcome")
    if not isinstance(outcome, Mapping) or str(outcome.get("status") or "").lower() != "failed" or str(outcome.get("code") or "").lower() not in {"failed", "launch_not_advanced"}:
        raise _refuse("marker does not record a failed, non-advanced launch")
    occupied = _occupied(marker)
    if occupied:
        raise _refuse(f"failed-prechain recovery requires no live {occupied}")


def _stage_runtime(source: Path, staged: Path, old_sha: str, new_sha: str) -> None:
    if _head(source) != old_sha:
        raise _refuse("source HEAD changed before recovery")
    ancestor = _git(source, "merge-base", "--is-ancestor", old_sha, new_sha)
    if ancestor.returncode != 0:
        raise _refuse("reviewed recovery source is not a descendant of the failed source")
    if staged.exists():
        if _head(staged) != new_sha or _status(staged):
            raise _refuse("staged runtime exists but is not the exact clean reviewed revision")
        return
    staged.parent.mkdir(parents=True, exist_ok=True)
    added = _git(source, "clone", "--no-hardlinks", "--no-checkout", str(source), str(staged))
    if added.returncode != 0:
        raise _refuse("staged runtime could not be cloned without mutating the source checkout")
    checked = _git(staged, "checkout", "--detach", new_sha)
    if checked.returncode != 0 or _head(staged) != new_sha or _status(staged):
        raise _refuse("staged runtime could not be created at the reviewed revision")
    # Dependency environments are normally ignored by Git.  Carry the old
    # environment into the new immutable root by value when it is part of the
    # runtime layout; the source checkout itself is never touched.
    old_venv = source / ".venv"
    new_venv = staged / ".venv"
    if old_venv.is_dir() and not new_venv.exists():
        shutil.copytree(old_venv, new_venv, symlinks=True)


def _copy_journal_state(workspace: Path, staged: Path, relative_paths: tuple[str, ...]) -> None:
    """Carry the authoritative pre-swap journal bytes into the clean candidate."""
    for relative in relative_paths:
        source = workspace / relative
        target = staged / relative
        if source.is_dir() and not source.is_symlink():
            shutil.copytree(source, target, symlinks=True, dirs_exist_ok=True)
        elif source.is_symlink():
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists() or target.is_symlink():
                target.unlink()
            target.symlink_to(os.readlink(source))
        elif source.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)


def _promote_staged_runtime(
    source: Path,
    staged: Path,
    backup: Path,
    *,
    new_sha: str,
    allowed_dirty_paths: tuple[str, ...] = (),
) -> None:
    """Atomically replace the dirty workspace, retaining it as custody."""
    dirty = _status(staged)
    if allowed_dirty_paths:
        dirty = [
            item for item in dirty
            if not any(item[3:].rstrip("/") == allowed or item[3:].rstrip("/").startswith(allowed + "/") for allowed in allowed_dirty_paths)
        ]
    if _head(staged) != new_sha or dirty:
        raise _refuse("staged runtime is not clean at the reviewed revision")
    if backup.exists():
        if source.exists() and _head(source) == new_sha and not _status(source):
            return
        raise _refuse("failed workspace custody path already exists")
    backup.parent.mkdir(parents=True, exist_ok=True)
    os.replace(source, backup)
    try:
        os.replace(staged, source)
    except BaseException:
        os.replace(backup, source)
        raise


def recover_failed_prechain(
    spec_path: Path,
    project_root: Path,
    *,
    marker_path: Path,
    manifest_path: Path,
    source_path: Path,
    workspace_path: Path,
    staged_runtime_path: Path,
    custody_dir: Path,
    expected_session_id: str,
    expected_marker_sha256: str,
    expected_manifest_sha256: str,
    expected_spec_sha256: str,
    expected_old_sha: str,
    reviewed_new_sha: str,
    reason: str,
    actor: str = "operator",
) -> dict[str, Any]:
    """Recover one failed same-session bootstrap, with one journaled effect."""
    spec_path = spec_path.expanduser().resolve(strict=False)
    project_root = project_root.expanduser().resolve(strict=False)
    marker_path = marker_path.expanduser().resolve(strict=False)
    manifest_path = manifest_path.expanduser().resolve(strict=False)
    source_path = source_path.expanduser().resolve(strict=False)
    workspace_path = workspace_path.expanduser().resolve(strict=False)
    staged_runtime_path = staged_runtime_path.expanduser().resolve(strict=False)
    custody_dir = custody_dir.expanduser().resolve(strict=False)
    expected_marker_sha256 = _full(expected_marker_sha256, label="marker SHA-256")
    expected_manifest_sha256 = _full(expected_manifest_sha256, label="manifest SHA-256")
    expected_spec_sha256 = _full(expected_spec_sha256, label="spec SHA-256")
    old_sha = str(expected_old_sha or "").strip().lower()
    new_sha = str(reviewed_new_sha or "").strip().lower()
    if _SHA40.fullmatch(old_sha) is None or _SHA40.fullmatch(new_sha) is None:
        raise _refuse("old and reviewed source revisions must be full Git SHAs")
    expected_session_id = _safe_text(expected_session_id, label="session")
    reason = _safe_text(reason, label="reason")
    actor = _safe_text(actor, label="actor")
    if not spec_path.is_file() or _sha(spec_path) != expected_spec_sha256:
        raise _refuse("chain spec identity does not match")
    if project_root.name != expected_session_id:
        raise _refuse("project root is not the guarded session")
    for candidate, label in ((custody_dir, "custody"), (staged_runtime_path, "staged runtime")):
        for root, root_label in (
            (source_path, "reviewed source"),
            (workspace_path, "chain workspace"),
        ):
            try:
                candidate.relative_to(root)
            except ValueError:
                continue
            raise _refuse(f"{label} path must not be inside the {root_label}")
    operation_id = hashlib.sha256(
        f"{RECOVERY_INTENT}\0{expected_session_id}\0{expected_manifest_sha256}\0{old_sha}\0{new_sha}".encode()
    ).hexdigest()
    state_path = chain_spec._state_path_for(spec_path)
    if state_path.exists():
        raise _refuse("failed-prechain recovery requires absent chain state")
    try:
        marker_raw = marker_path.read_bytes()
        marker = json.loads(marker_raw)
        manifest_raw = manifest_path.read_bytes()
        manifest = load_manifest(manifest_path)
    except (OSError, json.JSONDecodeError, ManifestError) as exc:
        raise _refuse("marker or runtime manifest is unavailable") from exc
    # A committed recovery is a deterministic terminal result.  Permit the
    # same guarded invocation to emit replay evidence even though the marker
    # and manifest now carry their post-recovery hashes.
    prior = marker.get("failed_prechain_recovery") if isinstance(marker, Mapping) else None
    if isinstance(prior, Mapping) and prior.get("operation_id") == operation_id:
        archive_path = custody_dir.expanduser().resolve(strict=False) / operation_id / "manifest.json"
        receipt_path = archive_path.parent / "recovery-receipt.json"
        _verify_archive(archive_path, json.loads(archive_path.read_text(encoding="utf-8")), operation_id)
        return {"outcome": "replay", "operation_id": operation_id, "archive_manifest": str(archive_path), "receipt": str(receipt_path)}
    if hashlib.sha256(marker_raw).hexdigest() != expected_marker_sha256:
        raise _refuse("session marker changed since recovery guards were computed")
    if hashlib.sha256(manifest_raw).hexdigest() != expected_manifest_sha256:
        raise _refuse("runtime manifest changed since recovery guards were computed")
    _assert_marker(marker, session=expected_session_id, workspace=workspace_path, manifest_path=manifest_path)
    engine_runtime_path = Path(str(manifest.epic.get("runtime_root") or "")).expanduser().resolve(strict=False)
    if not engine_runtime_path.is_dir():
        raise _refuse("runtime manifest engine root is unavailable")
    for candidate, label in ((custody_dir, "custody"), (staged_runtime_path, "staged runtime")):
        try:
            candidate.relative_to(engine_runtime_path)
        except ValueError:
            continue
        raise _refuse(f"{label} path must not be inside the engine runtime")
    if str(manifest.epic.get("expected_head") or "").lower() != old_sha:
        raise _refuse("runtime manifest does not describe the failed source")
    if _head(workspace_path) != old_sha:
        raise _refuse("chain workspace does not describe the failed runtime")
    if source_path == workspace_path:
        # Preserve the original single-root API for older callers.  New cloud
        # launches use the three-root contract below.
        if engine_runtime_path != workspace_path:
            raise _refuse("legacy source/workspace identity does not match the engine runtime")
    else:
        if _head(source_path) != old_sha or _status(source_path):
            raise _refuse("reviewed source checkout is not the clean failed revision")
        if engine_runtime_path in {source_path, workspace_path}:
            raise _refuse("three-root recovery requires distinct engine and chain roots")
        if _head(engine_runtime_path) != old_sha or _status(engine_runtime_path):
            raise _refuse("immutable engine runtime is not the clean failed revision")
    from arnold_pipelines.megaplan.incident.chain_control import (
        ChainControlHold,
        chain_id_for_spec,
        journal_for,
    )
    chain_id = chain_id_for_spec(spec_path)
    journal = journal_for(project_root)
    journal_owned_paths = _journal_owned_paths(journal, chain_id, workspace_path)
    journal_before = _journal_baseline(workspace_path, journal_owned_paths)
    archive_path, archive = _archive_dirty_state(
        workspace_path,
        custody_dir,
        operation_id,
        exclude_paths=journal_owned_paths,
    )
    _verify_archive(archive_path, archive, operation_id)
    receipt_path = archive_path.parent / "recovery-receipt.json"
    journal.ensure_genesis(chain_id=chain_id, actor={"id": actor, "class": "operator"}, spec_identity=str(spec_path))

    existing = journal.operation_result(operation_id)
    if existing is not None and existing.get("event_kind") == "chain_control.committed":
        return {"outcome": "replay", "operation_id": operation_id, "event_hash": existing.get("event_hash"), "archive_manifest": str(archive_path), "receipt": str(receipt_path)}

    def effect(txn: Any) -> dict[str, Any]:
        nonlocal rollback_state
        # Re-read every identity under the chain-control lock immediately
        # before the only source/manifest/marker writes.
        current_marker_raw = marker_path.read_bytes()
        current_manifest_raw = manifest_path.read_bytes()
        current_marker = json.loads(current_marker_raw)
        current_manifest = load_manifest(manifest_path)
        if _sha(spec_path) != expected_spec_sha256:
            raise ChainControlHold("spec_cas_conflict", "chain spec changed under recovery lock")
        if state_path.exists():
            raise ChainControlHold("chain_state_present", "chain state appeared under recovery lock")
        if hashlib.sha256(current_marker_raw).hexdigest() != expected_marker_sha256:
            raise ChainControlHold("marker_cas_conflict", "session marker changed under recovery lock")
        if hashlib.sha256(current_manifest_raw).hexdigest() != expected_manifest_sha256:
            raise ChainControlHold("manifest_cas_conflict", "runtime manifest changed under recovery lock")
        _assert_marker(current_marker, session=expected_session_id, workspace=workspace_path, manifest_path=manifest_path)
        if _head(workspace_path) != old_sha:
            raise ChainControlHold("workspace_cas_conflict", "chain workspace changed under recovery lock")
        if source_path != workspace_path and (_head(source_path) != old_sha or _status(source_path)):
            raise ChainControlHold("source_cas_conflict", "reviewed source checkout changed under recovery lock")
        if source_path != workspace_path and (_head(engine_runtime_path) != old_sha or _status(engine_runtime_path)):
            raise ChainControlHold("engine_cas_conflict", "immutable engine runtime changed under recovery lock")
        try:
            _assert_source_archive_fingerprint(
                workspace_path,
                archive_path,
                archive,
                exclude_paths=journal_owned_paths,
                before_excluded=journal_before,
            )
        except CliError as exc:
            raise ChainControlHold("source_cas_conflict", str(exc)) from exc
        # The exception above is narrowly limited to known journal files; the
        # journal itself must still be structurally valid and strictly replayable.
        try:
            journal.replay_strict()
        except ChainControlHold:
            raise
        failed_workspace = archive_path.parent / "failed-workspace"
        receipt_before = receipt_path.read_bytes() if receipt_path.exists() and receipt_path.stat().st_size else None
        promoted_workspace = False
        restored = False

        def restore() -> None:
            nonlocal restored
            if restored:
                return
            restored = True
            if promoted_workspace and failed_workspace.exists() and workspace_path.exists():
                if not staged_runtime_path.exists():
                    os.replace(workspace_path, staged_runtime_path)
                os.replace(failed_workspace, workspace_path)
            _atomic_bytes(manifest_path, current_manifest_raw)
            _atomic_bytes(marker_path, current_marker_raw)
            if receipt_before is None:
                if receipt_path.exists():
                    receipt_path.unlink()
            else:
                _atomic_bytes(receipt_path, receipt_before)

        # The journal finalizer invokes this if the committed-event append
        # fails after this effect has returned.  It runs under the same lock.
        rollback_state = restore
        try:
            _stage_runtime(source_path, staged_runtime_path, old_sha, new_sha)
            _copy_journal_state(workspace_path, staged_runtime_path, journal_owned_paths)
            _promote_staged_runtime(
                workspace_path,
                staged_runtime_path,
                failed_workspace,
                new_sha=new_sha,
                allowed_dirty_paths=journal_owned_paths,
            )
            promoted_workspace = True
            if Path(str(current_manifest.epic.get("runtime_root") or "")).expanduser().resolve(strict=False) != engine_runtime_path:
                raise ChainControlHold("engine_cas_conflict", "runtime manifest engine identity changed")
            old_epic = current_manifest.epic
            old_root = engine_runtime_path
            new_root = workspace_path
            def _relocate(value: Any) -> str:
                raw = str(value or "")
                if not raw:
                    return raw
                candidate = Path(raw).expanduser().resolve(strict=False)
                try:
                    return str(new_root / candidate.relative_to(old_root))
                except ValueError:
                    return raw
            promoted = cutover_runtime_manifest(
                current_manifest,
                from_runtime_root=str(old_root),
                from_expected_head=old_sha,
                to_runtime_root=str(new_root),
                to_expected_head=new_sha,
                to_venv_path=_relocate(old_epic.get("venv_path")),
                to_repair_bin=_relocate(old_epic.get("repair_bin")),
                reason=reason,
            )
            write_manifest(promoted, manifest_path)
            history = list(current_marker.get("launch_outcome_history") or []) if isinstance(current_marker.get("launch_outcome_history"), list) else []
            history.append(dict(current_marker.get("launch_outcome") or {}))
            updated_marker = dict(current_marker)
            updated_marker["launch_outcome_history"] = history
            updated_marker["failed_prechain_recovery"] = {
                "schema": RECOVERY_SCHEMA,
                "operation_id": operation_id,
                "old_sha": old_sha,
                "new_sha": new_sha,
                "reviewed_source": str(source_path),
                "chain_workspace": str(workspace_path),
                "engine_runtime_before": str(engine_runtime_path),
                "engine_runtime_after": str(workspace_path),
                "archive_manifest": {"path": str(archive_path), "sha256": _sha(archive_path)},
                "manifest_generation": promoted.generation,
                "reason": reason,
                "actor": actor,
            }
            updated_marker["should_run"] = True
            _atomic_json(marker_path, updated_marker)
            receipt = {
                "schema": RECOVERY_SCHEMA,
                "operation_id": operation_id,
                "session": expected_session_id,
                "chain_id": chain_id,
                "marker": {"path": str(marker_path), "before_sha256": expected_marker_sha256, "after_sha256": _sha(marker_path)},
                "manifest": {"path": str(manifest_path), "before_sha256": expected_manifest_sha256, "after_sha256": _sha(manifest_path), "generation": promoted.generation},
                "source": {"path": str(source_path), "old_sha": old_sha, "new_sha": new_sha},
                "staged_runtime": str(workspace_path),
                "preserved_failed_workspace": str(failed_workspace),
                "workspace": str(workspace_path),
                "engine_runtime": {"old_path": str(engine_runtime_path), "new_path": str(workspace_path)},
                "archive_manifest": {"path": str(archive_path), "sha256": _sha(archive_path)},
                "launch_outcome": dict(current_marker.get("launch_outcome") or {}),
                "outcome": "recovered",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            _atomic_json(receipt_path, receipt)
        except BaseException as exc:
            # The source swap, manifest, marker, and receipt are one logical
            # boundary.  On any injected or real failure restore the exact
            # pre-effect bytes and leave the clean staged checkout as evidence.
            rollback_error: BaseException | None = None
            try:
                restore()
            except BaseException as restore_exc:
                rollback_error = restore_exc
            if rollback_error is not None:
                raise ChainControlHold("recovery_rollback_failed", str(rollback_error)) from rollback_error
            if isinstance(exc, ChainControlHold):
                raise
            raise ChainControlHold("recovery_rolled_back", str(exc)) from exc
        return {
            "source_old_sha": old_sha,
            "source_new_sha": new_sha,
            "staged_runtime": str(workspace_path),
            "manifest_generation": promoted.generation,
            "archive_manifest": {"path": str(archive_path), "sha256": _sha(archive_path)},
            "receipt": str(receipt_path),
            "marker_sha256": _sha(marker_path),
            "manifest_sha256": _sha(manifest_path),
            "chain_state": "absent",
            "linked_receipts": [str(archive_path), str(receipt_path)],
        }

    rollback_state: Callable[[], None] | None = None

    def on_commit_failure(_txn: Any, exc: BaseException) -> Mapping[str, Any]:
        if rollback_state is None:
            return {"rolled_back": False, "error_type": type(exc).__name__}
        rollback_state()
        return {"rolled_back": True, "error_type": type(exc).__name__}

    try:
        result = journal.mutate(
            chain_id=chain_id,
            operation_id=operation_id,
            intent_kind=RECOVERY_INTENT,
            actor={"id": actor, "class": "operator"},
            # The state file itself must remain absent, so use an external
            # custody lock keyed to its canonical name instead of allowing
            # transaction setup to O_CREAT the state file or dirty checkout.
            state_paths=[
                spec_path,
                custody_dir / f"{state_path.name}.recovery.lock",
                custody_dir / "locks" / (hashlib.sha256(str(source_path).encode()).hexdigest() + ".source.lock"),
                custody_dir / "locks" / (hashlib.sha256(str(workspace_path).encode()).hexdigest() + ".workspace.lock"),
                custody_dir / "locks" / (hashlib.sha256(str(engine_runtime_path).encode()).hexdigest() + ".engine.lock"),
                marker_path,
                manifest_path,
                receipt_path,
            ],
            effect=effect,
            claim_class="required",
            linked_receipts=[str(archive_path)],
            spec_identity=str(spec_path),
            source_identity={
                "old_sha": old_sha,
                "new_sha": new_sha,
                "reviewed_source": str(source_path),
                "chain_workspace": str(workspace_path),
                "engine_runtime": str(engine_runtime_path),
            },
            intent_context={
                "session": expected_session_id,
                "old_sha": old_sha,
                "new_sha": new_sha,
                "reviewed_source": str(source_path),
                "chain_workspace": str(workspace_path),
                "engine_runtime": str(engine_runtime_path),
            },
            on_commit_failure=on_commit_failure,
        )
    except ChainControlHold as exc:
        raise _refuse(str(exc)) from exc
    if result.get("outcome") != "committed":
        error = result.get("error")
        raise _refuse(str(error or "failed-prechain recovery did not commit"))
    return {"outcome": "committed", "operation_id": operation_id, "event": result.get("event"), "effect": result.get("effect"), "archive_manifest": str(archive_path), "receipt": str(receipt_path)}


def reconcile_failed_prechain_hold(
    spec_path: Path,
    project_root: Path,
    *,
    marker_path: Path,
    manifest_path: Path,
    source_path: Path,
    workspace_path: Path,
    custody_dir: Path,
    held_operation_id: str,
    expected_hold_event_hash: str,
    expected_session_id: str,
    expected_marker_sha256: str,
    expected_manifest_sha256: str,
    expected_spec_sha256: str,
    expected_old_sha: str,
    held_reviewed_new_sha: str,
    recovery_evidence: Path,
    reason: str,
    actor: str = "operator",
) -> dict[str, Any]:
    """Close exactly one legacy failed-prechain hold with no external effect.

    This is deliberately not a general hold release.  It accepts only the
    exact hold produced by ``failed_prechain_recovery`` and writes one linked,
    no-effect terminal event using that same operation id.  That lets strict
    replay close the old operation while preserving its original hold and all
    source/runtime/marker authority bytes.
    """
    from arnold_pipelines.megaplan.incident.chain_control import (
        ChainControlHold,
        chain_id_for_spec,
        journal_for,
    )

    spec_path = spec_path.expanduser().resolve(strict=False)
    project_root = project_root.expanduser().resolve(strict=False)
    marker_path = marker_path.expanduser().resolve(strict=False)
    manifest_path = manifest_path.expanduser().resolve(strict=False)
    source_path = source_path.expanduser().resolve(strict=False)
    workspace_path = workspace_path.expanduser().resolve(strict=False)
    custody_dir = custody_dir.expanduser().resolve(strict=False)
    recovery_evidence = recovery_evidence.expanduser().resolve(strict=False)
    held_operation_id = _safe_text(held_operation_id, label="held operation")
    expected_hold_event_hash = _full(expected_hold_event_hash, label="held event SHA-256")
    expected_marker_sha256 = _full(expected_marker_sha256, label="marker SHA-256")
    expected_manifest_sha256 = _full(expected_manifest_sha256, label="manifest SHA-256")
    expected_spec_sha256 = _full(expected_spec_sha256, label="spec SHA-256")
    old_sha = str(expected_old_sha or "").strip().lower()
    new_sha = str(held_reviewed_new_sha or "").strip().lower()
    if _SHA40.fullmatch(old_sha) is None or _SHA40.fullmatch(new_sha) is None:
        raise _refuse("held old and reviewed source revisions must be full Git SHAs")
    expected_session_id = _safe_text(expected_session_id, label="session")
    reason = _safe_text(reason, label="reason")
    actor = _safe_text(actor, label="actor")
    if not recovery_evidence.is_file():
        raise _refuse("held recovery evidence is unavailable")
    evidence_sha = _sha(recovery_evidence)
    if not spec_path.is_file() or _sha(spec_path) != expected_spec_sha256:
        raise _refuse("chain spec identity does not match")
    if project_root.name != expected_session_id:
        raise _refuse("project root is not the guarded session")
    state_path = chain_spec._state_path_for(spec_path)
    chain_id = chain_id_for_spec(spec_path)
    journal = journal_for(project_root)

    try:
        marker_raw = marker_path.read_bytes()
        marker = json.loads(marker_raw)
        manifest_raw = manifest_path.read_bytes()
        manifest = load_manifest(manifest_path)
    except (OSError, json.JSONDecodeError, ManifestError) as exc:
        raise _refuse("marker or runtime manifest is unavailable") from exc
    if hashlib.sha256(marker_raw).hexdigest() != expected_marker_sha256:
        raise _refuse("session marker changed since held operation")
    if hashlib.sha256(manifest_raw).hexdigest() != expected_manifest_sha256:
        raise _refuse("runtime manifest changed since held operation")
    _assert_marker(marker, session=expected_session_id, workspace=workspace_path, manifest_path=manifest_path)
    if isinstance(marker.get("failed_prechain_recovery"), Mapping):
        raise _refuse("failed-prechain recovery effect is already present")
    if state_path.exists():
        raise _refuse("held recovery requires absent chain state")
    engine_runtime_path = Path(str(manifest.epic.get("runtime_root") or "")).expanduser().resolve(strict=False)
    held_identity = {
        "session": expected_session_id,
        "old_sha": old_sha,
        "new_sha": new_sha,
        "reviewed_source": str(source_path),
        "chain_workspace": str(workspace_path),
        "engine_runtime": str(engine_runtime_path),
    }
    expected_source_identity = {
        "old_sha": old_sha,
        "new_sha": new_sha,
        "reviewed_source": str(source_path),
        "chain_workspace": str(workspace_path),
        "engine_runtime": str(engine_runtime_path),
    }

    def _live_identity() -> dict[str, Any]:
        """Re-read every authoritative identity under the final lock."""
        current_marker_raw = marker_path.read_bytes()
        current_manifest_raw = manifest_path.read_bytes()
        current_marker = json.loads(current_marker_raw)
        current_manifest = load_manifest(manifest_path)
        if hashlib.sha256(spec_path.read_bytes()).hexdigest() != expected_spec_sha256:
            raise ChainControlHold("spec_cas_conflict", "chain spec changed while reconciling held operation")
        if hashlib.sha256(current_marker_raw).hexdigest() != expected_marker_sha256:
            raise ChainControlHold("marker_cas_conflict", "session marker changed while reconciling held operation")
        if hashlib.sha256(current_manifest_raw).hexdigest() != expected_manifest_sha256:
            raise ChainControlHold("manifest_cas_conflict", "runtime manifest changed while reconciling held operation")
        _assert_marker(current_marker, session=expected_session_id, workspace=workspace_path, manifest_path=manifest_path)
        if isinstance(current_marker.get("failed_prechain_recovery"), Mapping):
            raise ChainControlHold("effect_present", "failed-prechain recovery effect is already present")
        if state_path.exists():
            raise ChainControlHold("chain_state_present", "chain state appeared while reconciling held operation")
        current_engine = Path(str(current_manifest.epic.get("runtime_root") or "")).expanduser().resolve(strict=False)
        if current_engine != engine_runtime_path:
            raise ChainControlHold("engine_identity_conflict", "runtime manifest engine identity changed")
        if str(current_manifest.epic.get("expected_head") or "").lower() != old_sha:
            raise ChainControlHold("manifest_identity_conflict", "runtime manifest no longer describes held source")
        if _head(source_path) != old_sha or _status(source_path):
            raise ChainControlHold("source_effect_present", "reviewed source is not the unchanged clean held revision")
        if _head(workspace_path) != old_sha:
            raise ChainControlHold("workspace_effect_present", "chain workspace HEAD changed")
        if _head(engine_runtime_path) != old_sha or _status(engine_runtime_path):
            raise ChainControlHold("engine_effect_present", "engine runtime is not the unchanged clean held revision")
        receipt_path = recovery_evidence.parent / "recovery-receipt.json"
        if receipt_path.exists():
            raise ChainControlHold("receipt_effect_present", "recovery receipt already exists for held operation")
        return {
            "marker_sha256": hashlib.sha256(current_marker_raw).hexdigest(),
            "manifest_sha256": hashlib.sha256(current_manifest_raw).hexdigest(),
            "source_head": _head(source_path),
            "workspace_head": _head(workspace_path),
            "engine_runtime": str(current_engine),
            "engine_head": _head(current_engine),
        }

    replay = journal.replay_strict()
    operation_events = [
        event for event in replay["accepted"]
        if event.get("chain_id") == chain_id and event.get("operation_id") == held_operation_id
    ]
    if not operation_events:
        raise _refuse("held operation does not belong to this chain")
    holds = [
        event for event in operation_events
        if event.get("event_kind") == "chain_control.hold" and event.get("event_hash") == expected_hold_event_hash
    ]
    if len(holds) != 1:
        raise _refuse("exact held operation/event was not found")
    intent = next((event for event in operation_events if event.get("event_kind") == "chain_control.intent"), None)
    if not isinstance(intent, Mapping):
        raise _refuse("held operation has no authoritative intent")
    intent_payload = intent.get("payload") if isinstance(intent.get("payload"), Mapping) else {}
    if intent.get("spec_identity") != str(spec_path) or intent.get("intent") != RECOVERY_INTENT:
        raise _refuse("held operation kind or spec identity does not match")
    if {key: intent_payload.get(key) for key in held_identity} != held_identity:
        raise _refuse("held operation session/source/workspace identity does not match")
    if intent.get("source_identity") != expected_source_identity:
        raise _refuse("held operation source identity does not match")
    # ``mutate`` historically attached the archive only to the eventual
    # committed event, while a held operation has no committed event.  Bind
    # the evidence by its canonical custody location and content-addressed
    # archive schema instead of trusting a caller-provided receipt link.
    expected_evidence = custody_dir / held_operation_id / "manifest.json"
    if recovery_evidence != expected_evidence:
        raise _refuse("held recovery evidence is not the canonical operation archive")
    try:
        archive_payload = json.loads(recovery_evidence.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise _refuse("held recovery evidence archive is unreadable") from exc
    _verify_archive(recovery_evidence, archive_payload, held_operation_id)
    hold = holds[0]
    hold_payload = hold.get("payload") if isinstance(hold.get("payload"), Mapping) else {}
    if any(hold_payload.get(key) != value for key, value in held_identity.items()):
        raise _refuse("held hold identity does not match its intent")
    latest = operation_events[-1]
    terminal_events = [event for event in operation_events if event.get("event_kind") == "chain_control.hold_reconciled"]
    reconciliation_id = hashlib.sha256(
        f"reconcile-held-no-effect\0{chain_id}\0{held_operation_id}\0{expected_hold_event_hash}".encode()
    ).hexdigest()
    if terminal_events:
        terminal = terminal_events[-1]
        payload = terminal.get("payload") if isinstance(terminal.get("payload"), Mapping) else {}
        expected_terminal = {
            "disposition": "aborted_no_effect",
            "held_operation_id": held_operation_id,
            "held_event_hash": expected_hold_event_hash,
            "session": expected_session_id,
            "spec_path": str(spec_path),
            "spec_sha256": expected_spec_sha256,
            "marker_path": str(marker_path),
            "marker_sha256": expected_marker_sha256,
            "manifest_path": str(manifest_path),
            "manifest_sha256": expected_manifest_sha256,
            **held_identity,
            "recovery_evidence": {"path": str(recovery_evidence), "sha256": evidence_sha},
        }
        if terminal.get("recovery_id") != reconciliation_id or any(payload.get(k) != v for k, v in expected_terminal.items()):
            raise _refuse("held operation has a contradictory reconciliation terminal")
        if latest.get("event_kind") != "chain_control.hold_reconciled":
            raise _refuse("held operation has a later nonterminal event")
    elif latest.get("event_hash") != expected_hold_event_hash:
        raise _refuse("held operation is no longer an unresolved exact hold")

    lock_paths = [
        spec_path,
        marker_path,
        manifest_path,
        custody_dir / "locks" / (hashlib.sha256(str(source_path).encode()).hexdigest() + ".source.lock"),
        custody_dir / "locks" / (hashlib.sha256(str(workspace_path).encode()).hexdigest() + ".workspace.lock"),
        custody_dir / "locks" / (hashlib.sha256(str(engine_runtime_path).encode()).hexdigest() + ".engine.lock"),
        custody_dir / f"{state_path.name}.recovery.lock",
    ]
    with journal.transaction(
        chain_ids=[chain_id],
        state_paths=lock_paths,
        expected_revision=None,
        operation_id=held_operation_id,
        actor={"id": actor, "class": "operator"},
    ) as txn:
        live = _live_identity()
        if terminal_events:
            return {
                "outcome": "replay",
                "operation_id": held_operation_id,
                "reconciliation_id": reconciliation_id,
                "event": terminal_events[-1],
                "external_effect": False,
            }
        payload = {
            "disposition": "aborted_no_effect",
            "held_operation_id": held_operation_id,
            "held_event_hash": expected_hold_event_hash,
            "held_event_id": hold.get("event_id"),
            "session": expected_session_id,
            "spec_path": str(spec_path),
            "spec_sha256": expected_spec_sha256,
            "marker_path": str(marker_path),
            "marker_sha256": expected_marker_sha256,
            "manifest_path": str(manifest_path),
            "manifest_sha256": expected_manifest_sha256,
            **held_identity,
            "recovery_evidence": {"path": str(recovery_evidence), "sha256": evidence_sha},
            "reason": reason,
            "actor": actor,
            "zero_effect_identity": live,
        }
        event = journal.append_under_lock(
            txn,
            event_kind="chain_control.hold_reconciled",
            chain_id=chain_id,
            operation_id=held_operation_id,
            causation_id=str(hold.get("event_id") or held_operation_id),
            correlation_id=held_operation_id,
            recovery_id=reconciliation_id,
            payload=payload,
            semantic_effect="no_change",
            claim_class="evidence-only",
            actor={"id": actor, "class": "operator"},
            outcome="aborted_no_effect",
            failure_class="chain_control.hold",
            intent="reconcile-held-no-effect",
            linked_receipts=[str(recovery_evidence)],
            spec_identity=str(spec_path),
            source_identity=expected_source_identity,
        )
        return {
            "outcome": "committed",
            "operation_id": held_operation_id,
            "reconciliation_id": reconciliation_id,
            "event": event.get("payload", event),
            "external_effect": False,
        }


__all__ = [
    "RECOVERY_ERROR",
    "RECOVERY_SCHEMA",
    "RECOVERY_INTENT",
    "recover_failed_prechain",
    "reconcile_failed_prechain_hold",
]
