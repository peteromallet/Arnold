"""Read-only custody and orphan reporting for worktree execute substrate."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from megaplan._core import atomic_write_json, now_utc

from .identity import decode_original_task_id
from .paths import custody_paths, validate_run_id, validate_task_id
from .registry import validate_registry

CUSTODY_REPORT_SCHEMA_VERSION = 1


def custody_report_dir(project_dir: str | Path) -> Path:
    return custody_paths(project_dir).reports_dir


def custody_report_run_dir(project_dir: str | Path, run_id: str) -> Path:
    return custody_paths(project_dir).custody_report_dir(run_id)


def custody_report_path(project_dir: str | Path, run_id: str) -> Path:
    return custody_paths(project_dir).custody_report(run_id)


def build_custody_report(
    project_dir: str | Path,
    run_id: str,
    *,
    write: bool = False,
) -> dict[str, Any]:
    """Build a custody report; writes only when explicitly requested."""
    run_id = validate_run_id(run_id)
    paths = custody_paths(project_dir)
    project_root = paths.project_root
    validation = validate_registry(project_root, run_id)
    issues: list[dict[str, Any]] = []

    registry = _registry_section(paths, run_id, validation, issues)
    artifact_index = _task_artifact_index(project_root, run_id)
    task_ids = _discover_task_ids(paths, run_id, validation.entries, artifact_index)
    tasks = [
        _task_section(paths, run_id, task_id, validation.entries, artifact_index, issues)
        for task_id in sorted(task_ids)
    ]

    report: dict[str, Any] = {
        "schema_version": CUSTODY_REPORT_SCHEMA_VERSION,
        "run_id": run_id,
        "generated_at": now_utc(),
        "project_dir": str(project_root),
        "read_only": not write,
        "registry": registry,
        "tasks": tasks,
        "issue_count": len(issues),
        "issues": issues,
        "persisted_path": None,
    }
    if write:
        path = custody_report_path(project_root, run_id)
        atomic_write_json(path, report)
        report["persisted_path"] = str(path)
        atomic_write_json(path, report)
    return report


def _registry_section(
    paths: Any,
    run_id: str,
    validation: Any,
    issues: list[dict[str, Any]],
) -> dict[str, Any]:
    registry_path = paths.registry_jsonl(run_id)
    head_path = paths.registry_head(run_id)
    lock_path = paths.registry_lock(run_id)
    for error in validation.errors:
        issues.append(
            _issue(
                f"registry_{error.code}",
                error.message,
                path=error.path,
                line=error.line,
            )
        )
        if error.code == "anchored_tail_truncation":
            issues.append(_issue("anchored_tail_truncation", error.message, path=error.path))
    if (registry_path.exists() or head_path.exists()) and not lock_path.exists():
        issues.append(
            _issue(
                "registry_lock_missing",
                "registry has active state but no writer lock file",
                path=str(lock_path),
            )
        )
    if lock_path.exists() and not registry_path.exists() and not head_path.exists():
        issues.append(
            _issue(
                "registry_lock_orphaned",
                "registry lock exists without registry JSONL or head anchor",
                path=str(lock_path),
            )
        )
    return {
        "ok": validation.ok,
        "jsonl_path": str(registry_path),
        "jsonl_exists": registry_path.exists(),
        "head_path": str(head_path),
        "head_exists": head_path.exists(),
        "lock_path": str(lock_path),
        "lock_exists": lock_path.exists(),
        "entry_count": len(validation.entries),
        "head": validation.head,
        "errors": [
            {
                "code": error.code,
                "message": error.message,
                "path": error.path,
                "line": error.line,
            }
            for error in validation.errors
        ],
    }


def _discover_task_ids(
    paths: Any,
    run_id: str,
    entries: list[dict[str, Any]],
    artifact_index: dict[str, dict[str, Any]],
) -> set[str]:
    task_ids: set[str] = set()
    for entry in entries:
        original = _entry_original_task_id(entry)
        if original is not None:
            task_ids.add(original)
            continue
        task_id = entry.get("task_id")
        if isinstance(task_id, str):
            task_ids.add(task_id)
        payload = entry.get("payload")
        if isinstance(payload, dict) and isinstance(payload.get("task_id"), str):
            task_ids.add(payload["task_id"])
    for parent in [paths.scratch_worktrees_dir / run_id, paths.patch_run_dir(run_id)]:
        if not parent.exists():
            continue
        for child in parent.iterdir():
            if child.is_dir() and child.name.startswith("task-"):
                candidate = child.name[len("task-"):]
                try:
                    task_ids.add(validate_task_id(candidate))
                except ValueError:
                    continue
    task_ids.update(
        task_id
        for task_id in artifact_index
        if isinstance(task_id, str) and task_id
    )
    return task_ids


def _task_artifact_index(project_root: Path, run_id: str) -> dict[str, dict[str, Any]]:
    from megaplan.store import PlanRepository

    plans_root = project_root / ".megaplan" / "plans"
    if not plans_root.exists():
        return {}
    by_task: dict[str, dict[str, Any]] = {}
    for plan_dir in sorted(path for path in plans_root.iterdir() if path.is_dir()):
        try:
            summaries = PlanRepository.from_plan_dir(plan_dir).list_task_execution_summaries()
        except (OSError, RuntimeError, ValueError):
            continue
        for summary in summaries:
            if not _summary_matches_run(summary, run_id):
                continue
            task_id = summary.get("task_id")
            if isinstance(task_id, str) and task_id:
                enriched = dict(summary)
                enriched["plan_dir"] = str(plan_dir)
                by_task[task_id] = enriched
    return by_task


def _summary_matches_run(summary: dict[str, Any], run_id: str) -> bool:
    for section_name in ("registry", "patch"):
        section = summary.get(section_name)
        if isinstance(section, dict) and section.get("run_id") == run_id:
            return True
    return False


def _task_section(
    paths: Any,
    run_id: str,
    task_id: str,
    entries: list[dict[str, Any]],
    artifact_index: dict[str, dict[str, Any]],
    issues: list[dict[str, Any]],
) -> dict[str, Any]:
    task_entries = [entry for entry in entries if _entry_task_id(entry) == task_id]
    artifact_summary = artifact_index.get(task_id, {})
    registered = bool(task_entries)
    task_key = _entry_task_key(task_entries) or artifact_summary.get("task_key") or task_id
    path_id = _existing_or_preferred_path_id(paths, run_id, task_id, task_key)
    worktree = _entry_worktree(task_entries) or paths.scratch_worktree(run_id, path_id)
    manifest_path = paths.patch_manifest(run_id, path_id)
    manifest = _read_json_object(manifest_path)
    patch_path = _manifest_patch_path(paths.custody_root, manifest) or paths.patch_payload(run_id, path_id)

    task: dict[str, Any] = {
        "task_id": task_id,
        "task_key": task_key,
        "registered": registered,
        "entry_count": len(task_entries),
        "worktree_path": str(worktree),
        "worktree_exists": worktree.exists(),
        "worktree_dirty": False,
        "manifest_path": str(manifest_path),
        "manifest_exists": manifest_path.exists(),
        "patch_path": str(patch_path),
        "patch_exists": patch_path.exists(),
        "base_sha_matches": None,
        "secret_scan_status": None,
        "task_artifact": artifact_summary or None,
        "task_artifact_path": artifact_summary.get("artifact_path"),
        "task_artifact_plan_dir": artifact_summary.get("plan_dir"),
        "worktree_preserved": bool(artifact_summary.get("worktree_preserved")),
        "selected_tier": artifact_summary.get("tier"),
        "latest_task_progress": artifact_summary.get("progress"),
        "integration_state": (
            artifact_summary.get("integration", {}).get("state")
            if isinstance(artifact_summary.get("integration"), dict)
            else None
        ),
        "registry_identity_state": artifact_summary.get("registry"),
        "commit_identity_state": artifact_summary.get("commit_identity"),
    }
    artifact_secret_scan = artifact_summary.get("secret_scan")
    if isinstance(artifact_secret_scan, dict):
        task["secret_scan_status"] = artifact_secret_scan.get("status")
        task["secret_scan_mode"] = artifact_secret_scan.get("mode")
        task["secret_scan_source"] = artifact_secret_scan.get("source")
    if not registered and worktree.exists():
        issues.append(_issue("task_worktree_unregistered", "task worktree has no registry entry", task_id=task_id, path=str(worktree)))
    if registered and not worktree.exists():
        issues.append(_issue("task_worktree_missing", "registered task worktree is missing", task_id=task_id, path=str(worktree)))
    if worktree.exists() and (worktree / ".git").exists():
        dirty = _git_stdout(worktree, ["status", "--porcelain=v1"]) != ""
        task["worktree_dirty"] = dirty
        if dirty:
            issues.append(_issue("task_worktree_dirty", "task worktree has uncommitted changes", task_id=task_id, path=str(worktree)))
    if manifest_path.exists() and manifest is None:
        issues.append(_issue("bundle_manifest_drift", "bundle manifest is not valid JSON object", task_id=task_id, path=str(manifest_path)))
    if not manifest_path.exists() and paths.patch_task_dir(run_id, task_id).exists():
        issues.append(_issue("bundle_manifest_missing", "patch task directory has no manifest", task_id=task_id, path=str(manifest_path)))
    if manifest is not None:
        _check_manifest(paths, run_id, task_id, manifest, patch_path, task, issues)
        _check_base_sha(worktree, manifest, task, issues, task_id)
        _check_secret_scan(manifest, task, issues, task_id)
    return task


def _check_manifest(
    paths: Any,
    run_id: str,
    task_id: str,
    manifest: dict[str, Any],
    patch_path: Path,
    task: dict[str, Any],
    issues: list[dict[str, Any]],
) -> None:
    patch_info = manifest.get("patch")
    if not isinstance(patch_info, dict):
        issues.append(_issue("bundle_manifest_drift", "bundle manifest has no patch object", task_id=task_id, path=task["manifest_path"]))
        return
    if not patch_path.exists():
        issues.append(_issue("bundle_patch_missing", "bundle manifest references a missing patch", task_id=task_id, path=str(patch_path)))
        return
    actual_sha = _sha256_file(patch_path)
    actual_size = patch_path.stat().st_size
    task["patch_sha256"] = actual_sha
    task["patch_size_bytes"] = actual_size
    if patch_info.get("sha256") != actual_sha or patch_info.get("size_bytes") != actual_size:
        issues.append(_issue("bundle_patch_drift", "bundle patch hash or size differs from manifest", task_id=task_id, path=str(patch_path)))
    expected_path = paths.patch_payload(run_id, task_id)
    if patch_path.resolve() != expected_path.resolve():
        issues.append(_issue("bundle_manifest_drift", "bundle manifest patch path does not match custody layout", task_id=task_id, path=str(patch_path)))


def _check_base_sha(
    worktree: Path,
    manifest: dict[str, Any],
    task: dict[str, Any],
    issues: list[dict[str, Any]],
    task_id: str,
) -> None:
    base_head = manifest.get("base_head")
    if not isinstance(base_head, str) or not base_head or not (worktree / ".git").exists():
        return
    current_head = _git_stdout(worktree, ["rev-parse", "HEAD"])
    task["current_head"] = current_head
    task["base_head"] = base_head
    task["base_sha_matches"] = current_head == base_head
    if current_head != base_head:
        issues.append(
            _issue(
                "base_sha_mismatch",
                "task worktree HEAD differs from bundle base_head",
                task_id=task_id,
                path=str(worktree),
            )
        )


def _check_secret_scan(
    manifest: dict[str, Any],
    task: dict[str, Any],
    issues: list[dict[str, Any]],
    task_id: str,
) -> None:
    secret_scan = manifest.get("secret_scan")
    if not isinstance(secret_scan, dict):
        return
    status = secret_scan.get("status")
    task["secret_scan_status"] = status
    task["secret_scan_mode"] = secret_scan.get("mode")
    task["secret_scan_source"] = secret_scan.get("source") or secret_scan.get("policy")
    if status == "failed":
        issues.append(_issue("secret_scan_failed", "bundle secret scan failed closed", task_id=task_id))
    elif status == "skipped":
        issues.append(_issue("secret_scan_skipped", "bundle secret scan was explicitly skipped", task_id=task_id))


def _entry_task_id(entry: dict[str, Any]) -> str | None:
    original = _entry_original_task_id(entry)
    if original is not None:
        return original
    task_id = entry.get("task_id")
    if isinstance(task_id, str):
        return task_id
    payload = entry.get("payload")
    if isinstance(payload, dict) and isinstance(payload.get("task_id"), str):
        return payload["task_id"]
    return None


def _entry_original_task_id(entry: dict[str, Any]) -> str | None:
    identity = entry.get("identity")
    if isinstance(identity, dict):
        encoded = identity.get("original_task_id_encoded")
        if isinstance(encoded, str):
            try:
                return decode_original_task_id(encoded)
            except ValueError:
                return None
    return None


def _entry_task_key(entries: list[dict[str, Any]]) -> str | None:
    for entry in reversed(entries):
        task_key = entry.get("task_key")
        if isinstance(task_key, str):
            return task_key
    return None


def _existing_or_preferred_path_id(paths: Any, run_id: str, task_id: str, task_key: str) -> str:
    try:
        legacy_patch_dir = paths.patch_task_dir(run_id, task_id)
        legacy_worktree = paths.scratch_worktree(run_id, task_id)
    except (TypeError, ValueError):
        return task_key
    if legacy_patch_dir.exists() or legacy_worktree.exists():
        return task_id
    return task_key


def _entry_worktree(entries: list[dict[str, Any]]) -> Path | None:
    for entry in reversed(entries):
        payload = entry.get("payload")
        if not isinstance(payload, dict):
            continue
        for key in ("worktree", "worktree_path", "task_worktree"):
            value = payload.get(key)
            if isinstance(value, str) and value:
                return Path(value)
    return None


def _read_json_object(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _manifest_patch_path(custody_root: Path, manifest: dict[str, Any] | None) -> Path | None:
    if manifest is None:
        return None
    patch = manifest.get("patch")
    if not isinstance(patch, dict) or not isinstance(patch.get("path"), str):
        return None
    return custody_root / patch["path"]


def _sha256_file(path: Path) -> str:
    with path.open("rb") as handle:
        return "sha256:" + hashlib.sha256(handle.read()).hexdigest()


def _git_stdout(worktree: Path, args: list[str]) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=worktree,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    if proc.returncode != 0:
        return ""
    return proc.stdout.strip()


def _issue(
    code: str,
    message: str,
    *,
    task_id: str | None = None,
    path: str | None = None,
    line: int | None = None,
) -> dict[str, Any]:
    issue: dict[str, Any] = {"code": code, "message": message}
    if task_id is not None:
        issue["task_id"] = task_id
    if path is not None:
        issue["path"] = path
    if line is not None:
        issue["line"] = line
    return issue
