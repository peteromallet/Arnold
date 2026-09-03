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


def _archive_dirty_state(source: Path, custody_dir: Path, operation_id: str) -> tuple[Path, dict[str, Any]]:
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
    diff = _git(source, "diff", "HEAD").stdout.encode("utf-8")
    root.mkdir(parents=True, exist_ok=True)
    diff_path = root / "tracked.diff"
    diff_path.write_bytes(diff)
    entries: list[dict[str, Any]] = [{
        "path": "tracked.diff", "sha256": hashlib.sha256(diff).hexdigest(), "size": len(diff)
    }]
    for path in _untracked(source):
        if not path.is_file():
            raise _refuse(f"untracked recovery path is not a regular file: {path}")
        relative = path.relative_to(source).as_posix()
        target = root / "untracked" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        entries.append({"path": f"untracked/{relative}", "sha256": _sha(target), "size": target.stat().st_size})
    payload = {
        "schema": RECOVERY_SCHEMA,
        "operation_id": operation_id,
        "source_head": _head(source),
        "status": status,
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
        if not path.is_file() or _sha(path) != str(row.get("sha256") or "") or path.stat().st_size != row.get("size"):
            raise _refuse("recovery archive entry is missing or changed")


def _assert_source_archive_fingerprint(source: Path, archive_path: Path, payload: Mapping[str, Any]) -> None:
    entries = payload.get("entries") if isinstance(payload.get("entries"), list) else []
    tracked = next((row for row in entries if isinstance(row, Mapping) and row.get("path") == "tracked.diff"), None)
    if not isinstance(tracked, Mapping):
        raise _refuse("recovery archive has no tracked diff entry")
    current_diff = _git(source, "diff", "HEAD").stdout.encode("utf-8")
    if hashlib.sha256(current_diff).hexdigest() != tracked.get("sha256"):
        raise _refuse("tracked source changes differ from the archived failed launch")
    for row in entries:
        if not isinstance(row, Mapping) or not str(row.get("path") or "").startswith("untracked/"):
            continue
        relative = str(row["path"])[len("untracked/"):]
        candidate = source / relative
        if not candidate.is_file() or _sha(candidate) != str(row.get("sha256") or ""):
            raise _refuse("untracked source changes differ from the archived failed launch")


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


def _promote_staged_runtime(source: Path, staged: Path, backup: Path, *, new_sha: str) -> None:
    """Atomically replace the dirty workspace, retaining it as custody."""
    if _head(staged) != new_sha or _status(staged):
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
    expected_marker_sha256 = _full(expected_marker_sha256, label="marker SHA-256")
    expected_manifest_sha256 = _full(expected_manifest_sha256, label="manifest SHA-256")
    expected_spec_sha256 = _full(expected_spec_sha256, label="spec SHA-256")
    old_sha = str(expected_old_sha or "").strip().lower()
    new_sha = str(reviewed_new_sha or "").strip().lower()
    if _SHA40.fullmatch(old_sha) is None or _SHA40.fullmatch(new_sha) is None:
        raise _refuse("old and reviewed source revisions must be full Git SHAs")
    if not expected_session_id.strip() or not reason.strip() or not actor.strip():
        raise _refuse("session, reason, and actor are required")
    if not spec_path.is_file() or _sha(spec_path) != expected_spec_sha256:
        raise _refuse("chain spec identity does not match")
    if project_root.name != expected_session_id:
        raise _refuse("project root is not the guarded session")
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
    if Path(str(manifest.epic.get("runtime_root") or "")).expanduser().resolve(strict=False) != workspace_path:
        raise _refuse("runtime manifest workspace identity does not match")
    if str(manifest.epic.get("expected_head") or "").lower() != old_sha:
        raise _refuse("runtime manifest does not describe the failed source")
    if _head(source_path) != old_sha or source_path != workspace_path:
        raise _refuse("source/workspace identity does not match the failed runtime")
    archive_path, archive = _archive_dirty_state(source_path, custody_dir, operation_id)
    _verify_archive(archive_path, archive, operation_id)
    receipt_path = archive_path.parent / "recovery-receipt.json"

    from arnold_pipelines.megaplan.incident.chain_control import (
        ChainControlHold,
        _stable_id,
        chain_id_for_spec,
        journal_for,
    )
    chain_id = chain_id_for_spec(spec_path)
    journal = journal_for(project_root)
    journal.ensure_genesis(chain_id=chain_id, actor={"id": actor, "class": "operator"}, spec_identity=str(spec_path))

    existing = journal.operation_result(operation_id)
    if existing is not None and existing.get("event_kind") == "chain_control.committed":
        return {"outcome": "replay", "operation_id": operation_id, "event_hash": existing.get("event_hash"), "archive_manifest": str(archive_path), "receipt": str(receipt_path)}

    def effect(txn: Any) -> dict[str, Any]:
        # Re-read every identity under the chain-control lock immediately
        # before the only source/manifest/marker writes.
        current_marker_raw = marker_path.read_bytes()
        current_manifest_raw = manifest_path.read_bytes()
        current_marker = json.loads(current_marker_raw)
        current_manifest = load_manifest(manifest_path)
        if hashlib.sha256(current_marker_raw).hexdigest() != expected_marker_sha256:
            raise ChainControlHold("marker_cas_conflict", "session marker changed under recovery lock")
        if hashlib.sha256(current_manifest_raw).hexdigest() != expected_manifest_sha256:
            raise ChainControlHold("manifest_cas_conflict", "runtime manifest changed under recovery lock")
        _assert_marker(current_marker, session=expected_session_id, workspace=workspace_path, manifest_path=manifest_path)
        if _head(source_path) != old_sha:
            raise ChainControlHold("source_cas_conflict", "source checkout changed under recovery lock")
        try:
            _assert_source_archive_fingerprint(source_path, archive_path, archive)
        except CliError as exc:
            raise ChainControlHold("source_cas_conflict", str(exc)) from exc
        _stage_runtime(source_path, staged_runtime_path, old_sha, new_sha)
        failed_workspace = archive_path.parent / "failed-workspace"
        _promote_staged_runtime(source_path, staged_runtime_path, failed_workspace, new_sha=new_sha)
        try:
            if Path(str(current_manifest.epic.get("runtime_root") or "")).expanduser().resolve(strict=False) != workspace_path:
                raise ChainControlHold("workspace_cas_conflict", "runtime manifest workspace changed")
            old_epic = current_manifest.epic
            old_root = workspace_path
            new_root = source_path
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
                "staged_runtime": str(source_path),
                "preserved_failed_workspace": str(failed_workspace),
                "workspace": str(workspace_path),
                "archive_manifest": {"path": str(archive_path), "sha256": _sha(archive_path)},
                "launch_outcome": dict(current_marker.get("launch_outcome") or {}),
                "outcome": "recovered",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            _atomic_json(receipt_path, receipt)
        except ManifestError as exc:
            raise ChainControlHold("runtime_generation_refused", str(exc)) from exc
        return {
            "source_old_sha": old_sha,
            "source_new_sha": new_sha,
            "staged_runtime": str(source_path),
            "manifest_generation": promoted.generation,
            "archive_manifest": {"path": str(archive_path), "sha256": _sha(archive_path)},
            "receipt": str(receipt_path),
            "marker_sha256": _sha(marker_path),
            "manifest_sha256": _sha(manifest_path),
            "chain_state": "absent",
            "linked_receipts": [str(archive_path), str(receipt_path)],
        }

    try:
        result = journal.mutate(
            chain_id=chain_id,
            operation_id=operation_id,
            intent_kind=RECOVERY_INTENT,
            actor={"id": actor, "class": "operator"},
            state_paths=[marker_path, manifest_path, receipt_path],
            effect=effect,
            claim_class="required",
            linked_receipts=[str(archive_path)],
            spec_identity=str(spec_path),
            source_identity={"old_sha": old_sha, "new_sha": new_sha, "source": str(source_path)},
            intent_context={"session": expected_session_id, "old_sha": old_sha, "new_sha": new_sha},
        )
    except ChainControlHold as exc:
        raise _refuse(str(exc)) from exc
    if result.get("outcome") != "committed":
        error = result.get("error")
        raise _refuse(str(error or "failed-prechain recovery did not commit"))
    return {"outcome": "committed", "operation_id": operation_id, "event": result.get("event"), "effect": result.get("effect"), "archive_manifest": str(archive_path), "receipt": str(receipt_path)}


__all__ = ["RECOVERY_ERROR", "RECOVERY_SCHEMA", "RECOVERY_INTENT", "recover_failed_prechain"]
