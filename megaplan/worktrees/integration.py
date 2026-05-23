"""Restartable task patch integration state machine."""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .identity import TaskIdentity, build_task_identity_map
from .patches import PatchBundleRecord, _bundle_bytes, load_patch_bundle, prevalidate_patch_apply
from .paths import validate_run_id, validate_task_id
from .registry import MISSING_ANCHOR, MISSING_REGISTRY, RegistryError, append_registry_entry, read_registry_entries


@dataclass(frozen=True)
class TaskIntegrationResult:
    run_id: str
    task_id: str
    task_key: str
    status: str
    commit_sha: str | None
    staged_fingerprint: str | None
    pruned: bool


class TaskIntegrationError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def integrate_task_patch(
    project_dir: str | Path,
    run_id: str,
    task_id: str,
    milestone_repo: str | Path,
    finalize_data: dict[str, Any],
    *,
    push: bool = False,
    pr_url: str | None = None,
    prune_task_worktree: str | Path | None = None,
) -> TaskIntegrationResult:
    """Apply one task patch to a clean milestone checkout and record ordered states."""
    run_id = validate_run_id(run_id)
    task_id = validate_task_id(task_id)
    identity = _identity_from_finalize(finalize_data, task_id)
    existing_terminal = _latest_task_entry(project_dir, run_id, identity, "integration_complete")
    if existing_terminal is not None:
        return TaskIntegrationResult(
            run_id=run_id,
            task_id=task_id,
            task_key=identity.task_key,
            status="already_complete",
            commit_sha=existing_terminal.get("payload", {}).get("commit_sha"),
            staged_fingerprint=existing_terminal.get("payload", {}).get("staged_fingerprint"),
            pruned=_has_task_entry(project_dir, run_id, identity, "pruned"),
        )

    repo = Path(milestone_repo).resolve()
    _record(project_dir, run_id, identity, "integration_started", {"task_id": task_id, "task_key": identity.task_key})
    _require_clean_checkout(repo)
    current_head = _git_stdout(repo, ["rev-parse", "HEAD"]).strip()
    _record(project_dir, run_id, identity, "clean_checkout_verified", {"head": current_head})

    prevalidation = prevalidate_patch_apply(project_dir, run_id, task_id, repo, finalize_data)
    if not prevalidation.get("ok"):
        _record(project_dir, run_id, identity, "integration_blocked", {"reason": "apply_prevalidation_failed", "prevalidation": prevalidation})
        raise TaskIntegrationError("apply_prevalidation_failed", "patch apply prevalidation failed")

    bundle = load_patch_bundle(project_dir, run_id, task_id)
    _apply_bundle_to_index(repo, bundle)
    _record(project_dir, run_id, identity, "patch_applied", {"base_head": current_head, "apply_mode": "git apply --3way --index"})

    fingerprint = _staged_fingerprint(repo)
    if fingerprint is None:
        _record(project_dir, run_id, identity, "integration_noop", {"base_head": current_head})
        commit_sha = None
    else:
        _record(project_dir, run_id, identity, "staged_fingerprinted", fingerprint)
        commit_sha = _commit_staged(repo, identity)
        _record(
            project_dir,
            run_id,
            identity,
            "task_committed",
            {
                "commit_sha": commit_sha,
                "message_subject": f"mp-task:{identity.task_key}",
                "trailers": identity.trailer_fields(),
                "staged_fingerprint": fingerprint,
            },
        )

    if push:
        _record(project_dir, run_id, identity, "push_pending", {"commit_sha": commit_sha})
    else:
        _record(project_dir, run_id, identity, "push_noop", {"reason": "push_not_requested", "commit_sha": commit_sha})

    if pr_url:
        _record(project_dir, run_id, identity, "pr_recorded", {"url": pr_url, "commit_sha": commit_sha})
    else:
        _record(project_dir, run_id, identity, "pr_noop", {"reason": "pr_not_requested", "commit_sha": commit_sha})

    _record(
        project_dir,
        run_id,
        identity,
        "integration_complete",
        {
            "commit_sha": commit_sha,
            "staged_fingerprint": fingerprint,
            "terminal": True,
        },
    )
    pruned = False
    if prune_task_worktree is not None:
        _record(project_dir, run_id, identity, "prune_started", {"path": str(Path(prune_task_worktree).resolve())})
        shutil.rmtree(Path(prune_task_worktree).resolve())
        pruned = True
        _record(project_dir, run_id, identity, "pruned", {"path": str(Path(prune_task_worktree).resolve())})

    return TaskIntegrationResult(
        run_id=run_id,
        task_id=task_id,
        task_key=identity.task_key,
        status="complete",
        commit_sha=commit_sha,
        staged_fingerprint=fingerprint["sha256"] if fingerprint else None,
        pruned=pruned,
    )


def _identity_from_finalize(finalize_data: dict[str, Any], task_id: str) -> TaskIdentity:
    tasks = finalize_data.get("tasks")
    if not isinstance(tasks, list):
        raise TaskIntegrationError("finalize_tasks_missing", "finalize data must contain a tasks list")
    try:
        identity_map = build_task_identity_map(tasks)
    except Exception as exc:
        raise TaskIntegrationError("finalize_identity_invalid", str(exc)) from exc
    identity = identity_map.get(task_id)
    if identity is None:
        raise TaskIntegrationError("task_identity_missing", f"finalize data does not contain task {task_id!r}")
    return identity


def _record(
    project_dir: str | Path,
    run_id: str,
    identity: TaskIdentity,
    entry_type: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    return append_registry_entry(project_dir, run_id, entry_type, payload, identity=identity)


def _latest_task_entry(
    project_dir: str | Path,
    run_id: str,
    identity: TaskIdentity,
    entry_type: str,
) -> dict[str, Any] | None:
    try:
        registry_entries = read_registry_entries(project_dir, run_id)
    except RegistryError as exc:
        if exc.code in {MISSING_ANCHOR, MISSING_REGISTRY}:
            return None
        raise
    entries = [
        entry
        for entry in registry_entries
        if entry.get("task_key") == identity.task_key and entry.get("entry_type") == entry_type
    ]
    return entries[-1] if entries else None


def _has_task_entry(project_dir: str | Path, run_id: str, identity: TaskIdentity, entry_type: str) -> bool:
    return _latest_task_entry(project_dir, run_id, identity, entry_type) is not None


def _require_clean_checkout(repo: Path) -> None:
    _ensure_git_worktree(repo)
    status = _git_stdout(repo, ["status", "--porcelain=v1"]).strip()
    if status:
        raise TaskIntegrationError("milestone_checkout_dirty", "milestone checkout must be clean before task integration")


def _apply_bundle_to_index(repo: Path, bundle: PatchBundleRecord) -> None:
    patch_bytes = _bundle_bytes(bundle)
    proc = _run_git(
        repo,
        ["apply", "--3way", "--index", "--binary", "--whitespace=nowarn", "-"],
        input_bytes=patch_bytes,
        check=False,
    )
    if proc.returncode != 0:
        stderr = proc.stderr.decode("utf-8", errors="replace")
        stdout = proc.stdout.decode("utf-8", errors="replace")
        raise TaskIntegrationError("git_apply_failed", (stderr or stdout).strip() or "git apply failed")


def _staged_fingerprint(repo: Path) -> dict[str, Any] | None:
    diff = _git_stdout_bytes(repo, ["diff", "--cached", "--binary", "--full-index", "--no-ext-diff", "HEAD", "--"])
    if not diff:
        return None
    tree = _git_stdout(repo, ["write-tree"]).strip()
    return {
        "sha256": "sha256:" + hashlib.sha256(diff).hexdigest(),
        "size_bytes": len(diff),
        "tree": tree,
    }


def _commit_staged(repo: Path, identity: TaskIdentity) -> str:
    message = _commit_message(identity)
    _run_git(repo, ["commit", "-m", message])
    return _git_stdout(repo, ["rev-parse", "HEAD"]).strip()


def _commit_message(identity: TaskIdentity) -> str:
    trailers = "\n".join(f"{key}: {value}" for key, value in identity.trailer_fields().items())
    return f"mp-task:{identity.task_key}\n\n{trailers}"


def _ensure_git_worktree(repo: Path) -> None:
    if not (repo / ".git").exists():
        raise TaskIntegrationError("not_git_worktree", f"{repo} is not a git worktree")


def _git_stdout(repo: Path, args: list[str]) -> str:
    return _run_git(repo, args).stdout.decode("utf-8", errors="replace")


def _git_stdout_bytes(repo: Path, args: list[str]) -> bytes:
    return _run_git(repo, args).stdout


def _run_git(
    repo: Path,
    args: list[str],
    *,
    input_bytes: bytes | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[bytes]:
    env = dict(os.environ)
    env.update(
        {
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_PAGER": "cat",
            "GIT_DIFF_OPTS": "",
        }
    )
    env.pop("GIT_EXTERNAL_DIFF", None)
    proc = subprocess.run(
        _integration_git_command(args),
        cwd=str(repo),
        input=input_bytes,
        env=env,
        capture_output=True,
        check=False,
        timeout=30,
    )
    if check and proc.returncode != 0:
        stderr = proc.stderr.decode("utf-8", errors="replace")
        stdout = proc.stdout.decode("utf-8", errors="replace")
        raise TaskIntegrationError("git_failed", (stderr or stdout).strip() or f"git {' '.join(args)} failed")
    return proc


def _integration_git_command(args: list[str]) -> list[str]:
    return [
        "git",
        "-c",
        "color.ui=false",
        "-c",
        "core.pager=cat",
        "-c",
        "pager.diff=false",
        "-c",
        "diff.textconv=false",
        *args,
    ]
