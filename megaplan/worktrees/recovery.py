"""Crash recovery reconciliation for task patch integration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .identity import TaskIdentity, TaskIdentityError, build_task_identity_map, validate_trailer_identity
from .integration import (
    TaskIntegrationError,
    _commit_staged,
    _git_stdout,
    _git_stdout_bytes,
    _record,
    _staged_fingerprint,
)
from .patches import PatchCaptureError, load_patch_bundle
from .paths import validate_run_id, validate_task_id
from .registry import MISSING_ANCHOR, MISSING_REGISTRY, RegistryError, read_registry_entries, validate_registry


@dataclass(frozen=True)
class TaskRecoveryResult:
    run_id: str
    task_id: str
    task_key: str
    status: str
    action: str
    commit_sha: str | None
    blocked_reason: str | None
    evidence: dict[str, Any]


class TaskRecoveryError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def reconcile_task_integration(
    project_dir: str | Path,
    run_id: str,
    task_id: str,
    milestone_repo: str | Path,
    finalize_data: dict[str, Any],
    *,
    plan_dir: str | Path | None = None,
    progress_events: list[dict[str, Any]] | None = None,
) -> TaskRecoveryResult:
    """Reconcile a crashed task integration attempt without replaying unsafe mutations."""
    run_id = validate_run_id(run_id)
    task_id = validate_task_id(task_id)
    repo = Path(milestone_repo).resolve()
    identity = _identity_from_finalize(finalize_data, task_id)
    bundle = load_patch_bundle(project_dir, run_id, task_id)
    registry_error = _registry_blocking_error(project_dir, run_id)
    if registry_error is not None:
        evidence = _recovery_evidence(
            project_dir,
            run_id,
            identity,
            repo,
            [],
            bundle,
            plan_dir=plan_dir,
            progress_events=progress_events,
        )
        evidence["registry"]["error"] = registry_error
        return TaskRecoveryResult(
            run_id,
            task_id,
            identity.task_key,
            "blocked",
            "none",
            None,
            "invalid_registry",
            evidence,
        )
    registry_entries = _read_registry_entries(project_dir, run_id)
    evidence = _recovery_evidence(
        project_dir,
        run_id,
        identity,
        repo,
        registry_entries,
        bundle,
        plan_dir=plan_dir,
        progress_events=progress_events,
    )
    _record(project_dir, run_id, identity, "recovery_checked", evidence)

    terminal = _latest_entry(registry_entries, identity, "integration_complete")
    if terminal is not None:
        payload = {"reason": "terminal_registry_state_present", "commit_sha": terminal.get("payload", {}).get("commit_sha")}
        _record(project_dir, run_id, identity, "recovery_idempotent", payload)
        return TaskRecoveryResult(run_id, task_id, identity.task_key, "already_complete", "none", payload["commit_sha"], None, evidence)

    block_reason = _blocking_reason(repo, bundle, registry_entries, identity)
    if block_reason is not None:
        _record(project_dir, run_id, identity, "recovery_blocked", {"reason": block_reason, "evidence": evidence})
        return TaskRecoveryResult(run_id, task_id, identity.task_key, "blocked", "none", None, block_reason, evidence)

    existing_commit = _find_existing_task_commit(repo, identity)
    if existing_commit is not None:
        _record_post_commit_reconciliation(project_dir, run_id, identity, existing_commit, evidence)
        return TaskRecoveryResult(
            run_id,
            task_id,
            identity.task_key,
            "reconciled",
            "record_existing_commit",
            existing_commit,
            None,
            evidence,
        )

    if _is_post_apply_pre_commit(repo, bundle):
        fingerprint = _staged_fingerprint(repo)
        if fingerprint is None:
            _record(project_dir, run_id, identity, "recovery_blocked", {"reason": "missing_staged_patch", "evidence": evidence})
            return TaskRecoveryResult(run_id, task_id, identity.task_key, "blocked", "none", None, "missing_staged_patch", evidence)
        _record(project_dir, run_id, identity, "recovery_reconciled", {"phase": "post_apply_pre_commit", "staged_fingerprint": fingerprint})
        _record(project_dir, run_id, identity, "staged_fingerprinted", fingerprint)
        commit_sha = _commit_staged(repo, identity)
        _record_commit_terminal(project_dir, run_id, identity, commit_sha, fingerprint)
        return TaskRecoveryResult(run_id, task_id, identity.task_key, "reconciled", "commit_staged_patch", commit_sha, None, evidence)

    dirty = _git_status(repo)
    if dirty:
        _record(project_dir, run_id, identity, "recovery_blocked", {"reason": "dirty_checkout", "status": dirty, "evidence": evidence})
        return TaskRecoveryResult(run_id, task_id, identity.task_key, "blocked", "none", None, "dirty_checkout", evidence)

    _record(project_dir, run_id, identity, "recovery_blocked", {"reason": "no_recoverable_state", "evidence": evidence})
    return TaskRecoveryResult(run_id, task_id, identity.task_key, "blocked", "none", None, "no_recoverable_state", evidence)


def _identity_from_finalize(finalize_data: dict[str, Any], task_id: str) -> TaskIdentity:
    tasks = finalize_data.get("tasks")
    if not isinstance(tasks, list):
        raise TaskRecoveryError("finalize_tasks_missing", "finalize data must contain a tasks list")
    try:
        identity_map = build_task_identity_map(tasks)
    except Exception as exc:
        raise TaskRecoveryError("finalize_identity_invalid", str(exc)) from exc
    identity = identity_map.get(task_id)
    if identity is None:
        raise TaskRecoveryError("task_identity_missing", f"finalize data does not contain task {task_id!r}")
    return identity


def _read_registry_entries(project_dir: str | Path, run_id: str) -> list[dict[str, Any]]:
    try:
        return read_registry_entries(project_dir, run_id)
    except RegistryError as exc:
        if exc.code in {MISSING_ANCHOR, MISSING_REGISTRY}:
            return []
        raise


def _registry_blocking_error(project_dir: str | Path, run_id: str) -> dict[str, Any] | None:
    validation = validate_registry(project_dir, run_id)
    if not validation.errors:
        return None
    missing_only = {error.code for error in validation.errors} <= {MISSING_ANCHOR, MISSING_REGISTRY}
    if missing_only:
        return None
    error = validation.errors[0]
    return {
        "code": error.code,
        "message": error.message,
        "path": error.path,
        "line": error.line,
    }


def _latest_entry(
    registry_entries: list[dict[str, Any]],
    identity: TaskIdentity,
    entry_type: str,
) -> dict[str, Any] | None:
    matches = [
        entry
        for entry in registry_entries
        if entry.get("task_key") == identity.task_key and entry.get("entry_type") == entry_type
    ]
    return matches[-1] if matches else None


def _recovery_evidence(
    project_dir: str | Path,
    run_id: str,
    identity: TaskIdentity,
    repo: Path,
    registry_entries: list[dict[str, Any]],
    bundle: Any,
    *,
    plan_dir: str | Path | None,
    progress_events: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    task_artifact = _task_artifact(identity, plan_dir)
    return {
        "task_id": identity.original_task_id,
        "task_key": identity.task_key,
        "manifest": {
            "base_head": bundle.base_head,
            "task_key": bundle.task_key,
            "identity": bundle.identity,
            "trailers": bundle.trailers,
            "secret_scan": bundle.secret_scan,
            "patch_sha256": bundle.patch_sha256,
            "patch_size_bytes": bundle.patch_size_bytes,
        },
        "registry": {
            "entry_types": [entry.get("entry_type") for entry in registry_entries if entry.get("task_key") == identity.task_key],
            "has_terminal": _latest_entry(registry_entries, identity, "integration_complete") is not None,
        },
        "git": {
            "head": _safe_git_stdout(repo, ["rev-parse", "HEAD"]),
            "status": _safe_git_stdout(repo, ["status", "--porcelain=v1"]),
            "has_index_lock": _index_lock(repo).exists(),
            "has_conflicts": bool(_safe_git_stdout(repo, ["ls-files", "-u"])),
            "existing_commit": _find_existing_task_commit(repo, identity),
        },
        "task_artifact": task_artifact,
        "progress": {
            "task_complete_events": _matching_task_complete_events(progress_events or [], identity),
        },
    }


def _task_artifact(identity: TaskIdentity, plan_dir: str | Path | None) -> dict[str, Any] | None:
    if plan_dir is None:
        return None
    from megaplan.store.plan_repository import PlanRepository

    artifact = PlanRepository.from_plan_dir(plan_dir).read_task_execution_artifact(identity)
    return artifact if isinstance(artifact, dict) else None


def _matching_task_complete_events(events: list[dict[str, Any]], identity: TaskIdentity) -> list[dict[str, Any]]:
    return [
        event
        for event in events
        if event.get("kind") == "task_complete"
        and (event.get("task_key") == identity.task_key or event.get("details", {}).get("task_key") == identity.task_key)
    ]


def _blocking_reason(repo: Path, bundle: Any, registry_entries: list[dict[str, Any]], identity: TaskIdentity) -> str | None:
    if _index_lock(repo).exists():
        return "index_lock"
    if _safe_git_stdout(repo, ["ls-files", "-u"]):
        return "conflicted_checkout"
    if bundle.task_key != identity.task_key or bundle.identity != identity.registry_identity():
        return "identity_mismatch"
    trailers = bundle.trailers
    if not isinstance(trailers, dict):
        return "malformed_trailers"
    try:
        validate_trailer_identity(trailers, {identity.original_task_id: identity})
    except TaskIdentityError:
        return "malformed_trailers"
    if trailers != identity.trailer_fields():
        return "identity_mismatch"
    if _secret_scan_disagrees(bundle, registry_entries, identity):
        return "secret_scan_disagreement"
    existing_commit = _find_existing_task_commit(repo, identity, validate=False)
    if existing_commit is not None:
        commit_reason = _commit_identity_block_reason(repo, existing_commit, identity)
        if commit_reason is not None:
            return commit_reason
    return None


def _secret_scan_disagrees(bundle: Any, registry_entries: list[dict[str, Any]], identity: TaskIdentity) -> bool:
    if not isinstance(bundle.secret_scan, dict) or bundle.secret_scan.get("status") == "failed":
        return True
    patch_captured = _latest_entry(registry_entries, identity, "patch_captured")
    if patch_captured is None:
        return False
    registry_scan = patch_captured.get("payload", {}).get("secret_scan")
    return registry_scan != bundle.secret_scan


def _commit_identity_block_reason(repo: Path, commit_sha: str, identity: TaskIdentity) -> str | None:
    try:
        trailers = _commit_trailers(repo, commit_sha, identity)
        validate_trailer_identity(trailers, {identity.original_task_id: identity})
    except TaskIdentityError as exc:
        if exc.code in {"task_key_mismatch", "unknown_task_identity"}:
            return "identity_mismatch"
        return "malformed_trailers"
    if trailers != identity.trailer_fields():
        return "identity_mismatch"
    return None


def _find_existing_task_commit(repo: Path, identity: TaskIdentity, *, validate: bool = True) -> str | None:
    try:
        output = _git_stdout(repo, ["log", "--format=%H%x00%s", "-n", "50"])
    except TaskIntegrationError:
        return None
    subject = f"mp-task:{identity.task_key}"
    for line in output.splitlines():
        if "\x00" not in line:
            continue
        sha, commit_subject = line.split("\x00", 1)
        if commit_subject != subject:
            continue
        if validate:
            reason = _commit_identity_block_reason(repo, sha, identity)
            if reason is not None:
                return None
        return sha
    return None


def _commit_trailers(repo: Path, commit_sha: str, identity: TaskIdentity) -> dict[str, str]:
    message = _git_stdout(repo, ["log", "-1", "--format=%B", commit_sha])
    lines = [line.strip() for line in message.splitlines() if line.strip()]
    if not lines or lines[0] != f"mp-task:{identity.task_key}":
        raise TaskIdentityError("task_key_mismatch", "commit subject does not match task key")
    allowed_keys = set(identity.trailer_fields())
    trailers: dict[str, str] = {}
    for line in lines[1:]:
        if ": " not in line:
            raise TaskIdentityError("malformed_identity_trailer", "commit contains non-trailer identity metadata")
        key, value = line.split(": ", 1)
        if key not in allowed_keys:
            raise TaskIdentityError("malformed_identity_trailer", f"unexpected task identity trailer: {key}")
        if key in trailers:
            raise TaskIdentityError("malformed_identity_trailer", f"duplicate task identity trailer: {key}")
        trailers[key] = value
    return trailers


def _is_post_apply_pre_commit(repo: Path, bundle: Any) -> bool:
    if _safe_git_stdout(repo, ["rev-parse", "HEAD"]) != bundle.base_head:
        return False
    if _safe_git_stdout(repo, ["diff", "--name-only"]):
        return False
    return bool(_safe_git_stdout(repo, ["diff", "--cached", "--name-only"]))


def _record_post_commit_reconciliation(
    project_dir: str | Path,
    run_id: str,
    identity: TaskIdentity,
    commit_sha: str,
    evidence: dict[str, Any],
) -> None:
    _record(project_dir, run_id, identity, "recovery_reconciled", {"phase": "post_commit_pre_registry", "commit_sha": commit_sha})
    _record_commit_terminal(project_dir, run_id, identity, commit_sha, None)
    _record(project_dir, run_id, identity, "recovery_idempotent", {"commit_sha": commit_sha, "evidence": evidence})


def _record_commit_terminal(
    project_dir: str | Path,
    run_id: str,
    identity: TaskIdentity,
    commit_sha: str,
    fingerprint: dict[str, Any] | None,
) -> None:
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
            "recovered": True,
        },
    )
    _record(project_dir, run_id, identity, "push_noop", {"reason": "recovery_no_push", "commit_sha": commit_sha})
    _record(project_dir, run_id, identity, "pr_noop", {"reason": "recovery_no_pr", "commit_sha": commit_sha})
    _record(
        project_dir,
        run_id,
        identity,
        "integration_complete",
        {"commit_sha": commit_sha, "staged_fingerprint": fingerprint, "terminal": True, "recovered": True},
    )


def _index_lock(repo: Path) -> Path:
    return repo / ".git" / "index.lock"


def _git_status(repo: Path) -> str:
    return _safe_git_stdout(repo, ["status", "--porcelain=v1"])


def _safe_git_stdout(repo: Path, args: list[str]) -> str:
    try:
        return _git_stdout(repo, args).strip()
    except TaskIntegrationError:
        return ""
