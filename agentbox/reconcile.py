"""Report-only reconciliation for AgentBox host-local state."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
from pathlib import Path
from typing import Any, Mapping

from arnold.runtime.durable_ops import (
    OperationRun,
    ResourceType,
    TypedResource,
    is_terminal_operation_state,
)

from agentbox.cleanup import _classify_cleanup_recommendation
from agentbox.config import AgentBoxConfig
from agentbox.git_worktree import (
    GitWorktreeError,
    GitDirtyStatus,
    WorktreeInfo,
    git,
    git_dirty_status,
    git_operation_status,
    has_local_branch,
    has_remote_tracking_ref,
    list_worktrees,
)
from agentbox.operations import list_agentbox_operations, open_operation_store
from agentbox.repos import AgentBoxRepoNotFound, RegisteredRepo, get_repo
from agentbox.run_dirs import run_dir_paths
from agentbox.tmux import SessionStatus, inspect_session, session_name
from agentbox.worktrees import branch_name, worktree_path


@dataclass(frozen=True)
class RunDirReconciliation:
    """Filesystem status for one operation run directory."""

    operation_id: str
    path: str
    state: str
    exists: bool
    missing_files: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return _asdict(self)


@dataclass(frozen=True)
class WorktreeReconciliation:
    """Git/filesystem status for one operation/repo pair."""

    operation_id: str
    repo_name: str
    state: str
    recommended_action: str
    branch: str
    worktree_path: str
    canonical_repo_path: str | None
    local_branch_exists: bool
    remote_tracking_ref_exists: bool
    remote_tracking_only: bool
    target_path_exists: bool
    target_registered: bool
    checked_out_path: str | None = None
    checked_out_elsewhere: bool = False
    durable_resource_id: str | None = None
    prunable_reason: str | None = None
    detail: str | None = None
    pr_number: int | None = None
    pr_url: str | None = None
    ci_status: str | None = None
    cleanup_recommendation: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return _asdict(self)


@dataclass(frozen=True)
class SessionReconciliation:
    """Tmux session status referenced by one operation."""

    operation_id: str
    session_name: str
    state: str
    exists: bool
    durable_resource_id: str | None = None
    detail: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return _asdict(self)


@dataclass(frozen=True)
class OperationReconciliation:
    """Combined report-only status for one durable AgentBox operation."""

    operation_id: str
    operation_state: str
    launch_state: str | None
    resource_count: int
    run_dir: RunDirReconciliation
    worktrees: tuple[WorktreeReconciliation, ...]
    sessions: tuple[SessionReconciliation, ...]

    def to_dict(self) -> dict[str, Any]:
        return _asdict(self)


@dataclass(frozen=True)
class OrphanRunDirReconciliation:
    """Run directory with no durable AgentBox operation."""

    operation_id: str
    path: str
    state: str = "orphan_run_dir"

    def to_dict(self) -> dict[str, Any]:
        return _asdict(self)


@dataclass(frozen=True)
class ReconciliationReport:
    """Top-level report-only reconciliation snapshot."""

    operations: tuple[OperationReconciliation, ...]
    orphan_run_dirs: tuple[OrphanRunDirReconciliation, ...]

    def to_dict(self) -> dict[str, Any]:
        return _asdict(self)


@dataclass(frozen=True)
class FileProbe:
    """Observed file state for reconcile decisions."""

    path: str
    exists: bool
    sha256: str | None = None
    content_matches: bool | None = None
    sha256_matches: bool | None = None


def reconcile(config: AgentBoxConfig) -> ReconciliationReport:
    """Return an AgentBox host-local reconciliation report without mutating state."""

    operations = list_agentbox_operations(config)
    operation_reports = tuple(
        _reconcile_operation(config, operation)
        for operation in operations
    )
    known_operation_ids = {operation.id for operation in operations}
    return ReconciliationReport(
        operations=operation_reports,
        orphan_run_dirs=_orphan_run_dirs(config, known_operation_ids),
    )


def parse_porcelain_paths(entries: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    """Extract repo-relative paths from ``git status --porcelain`` entries."""

    paths: list[str] = []
    for entry in entries:
        if len(entry) < 4:
            continue
        payload = entry[3:]
        if " -> " in payload:
            _, _, payload = payload.partition(" -> ")
        normalized = payload.strip()
        if normalized:
            paths.append(normalized)
    return tuple(paths)


def probe_dirty_paths(repo_path: Path | str) -> tuple[str, ...]:
    """Return repo-relative dirty paths for a checkout."""

    status: GitDirtyStatus = git_dirty_status(repo_path)
    return parse_porcelain_paths(status.entries)


def probe_file(
    path: Path | str,
    *,
    expected_content: str | None = None,
    expected_sha256: str | None = None,
) -> FileProbe:
    """Inspect a file and compare it against expected content or digest."""

    target = Path(path)
    if not target.exists():
        return FileProbe(
            path=str(target),
            exists=False,
            content_matches=False if expected_content is not None else None,
            sha256_matches=False if expected_sha256 is not None else None,
        )

    data = target.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    content_matches: bool | None = None
    if expected_content is not None:
        try:
            content_matches = data.decode("utf-8") == expected_content
        except UnicodeDecodeError:
            content_matches = False
    sha256_matches = (
        digest == expected_sha256 if expected_sha256 is not None else None
    )
    return FileProbe(
        path=str(target),
        exists=True,
        sha256=digest,
        content_matches=content_matches,
        sha256_matches=sha256_matches,
    )


def _reconcile_operation(
    config: AgentBoxConfig,
    operation: OperationRun,
) -> OperationReconciliation:
    resources = open_operation_store(config).list_typed_resources(operation.id)
    return OperationReconciliation(
        operation_id=operation.id,
        operation_state=operation.state.value,
        launch_state=_metadata_str(operation.metadata, "launch_state"),
        resource_count=len(resources),
        run_dir=_reconcile_run_dir(config, operation.id),
        worktrees=tuple(
            _reconcile_worktree(config, operation, repo_name, resources)
            for repo_name in _repo_names(operation, resources)
        ),
        sessions=tuple(
            _reconcile_session(operation.id, name, resource)
            for name, resource in _session_names(operation, resources)
        ),
    )


def _reconcile_run_dir(config: AgentBoxConfig, operation_id: str) -> RunDirReconciliation:
    paths = run_dir_paths(config, operation_id)
    expected = {
        "events.ndjson": paths.events_path,
        "stdout.log": paths.stdout_path,
        "stderr.log": paths.stderr_path,
        "metadata.json": paths.metadata_path,
    }
    missing = tuple(name for name, path in expected.items() if not path.exists())
    if not paths.root.exists():
        state = "missing"
    elif missing:
        state = "partial"
    else:
        state = "ready"
    return RunDirReconciliation(
        operation_id=operation_id,
        path=str(paths.root),
        state=state,
        exists=paths.root.exists(),
        missing_files=missing,
    )


def _reconcile_worktree(
    config: AgentBoxConfig,
    operation: OperationRun,
    repo_name: str,
    resources: tuple[TypedResource, ...],
) -> WorktreeReconciliation:
    branch = branch_name(operation.id, repo_name)
    target = worktree_path(config, operation.id, repo_name)
    resource = _git_worktree_resource(resources, repo_name)
    try:
        repo = get_repo(config, repo_name)
    except AgentBoxRepoNotFound:
        return _unknown_repo_worktree(operation.id, repo_name, branch, target, resource)

    try:
        worktrees = list_worktrees(repo.path)
        checked_out = _checked_out_from(worktrees, branch)
        registered_at_target = _registered_at(worktrees, target)
        local_exists = has_local_branch(repo.path, branch)
        remote_exists = has_remote_tracking_ref(repo.path, f"origin/{branch}")
    except (GitWorktreeError, OSError) as exc:
        return _git_unavailable_worktree(operation.id, repo, branch, target, resource, exc)

    remote_only = remote_exists and not local_exists
    target_registered = registered_at_target is not None
    checked_out_path = str(checked_out.path) if checked_out else None
    checked_out_elsewhere = bool(checked_out and checked_out.path.resolve() != target.resolve())
    state, action, detail = _worktree_state_and_action(
        target=target,
        branch=branch,
        checked_out=checked_out,
        registered_at_target=registered_at_target,
        local_exists=local_exists,
        remote_only=remote_only,
        resource=resource,
    )
    pr_info = _pr_info_for_branch(repo.path, branch)
    ci_status = _ci_status_for_branch(repo.path, branch, pr_info)
    cleanup_recommendation = _cleanup_recommendation_for_worktree(
        repo=repo,
        branch=branch,
        target=target,
        checked_out_elsewhere=checked_out_elsewhere,
        operation=operation,
        pr_info=pr_info,
    )
    return WorktreeReconciliation(
        operation_id=operation.id,
        repo_name=repo_name,
        state=state,
        recommended_action=action,
        branch=branch,
        worktree_path=str(target),
        canonical_repo_path=str(repo.path),
        local_branch_exists=local_exists,
        remote_tracking_ref_exists=remote_exists,
        remote_tracking_only=remote_only,
        target_path_exists=target.exists(),
        target_registered=target_registered,
        checked_out_path=checked_out_path,
        checked_out_elsewhere=checked_out_elsewhere,
        durable_resource_id=resource.id if resource else None,
        prunable_reason=registered_at_target.prunable_reason if registered_at_target else None,
        detail=detail,
        pr_number=pr_info.get("number"),
        pr_url=pr_info.get("url"),
        ci_status=ci_status,
        cleanup_recommendation=cleanup_recommendation,
    )


def _worktree_state_and_action(
    *,
    target: Path,
    branch: str,
    checked_out: WorktreeInfo | None,
    registered_at_target: WorktreeInfo | None,
    local_exists: bool,
    remote_only: bool,
    resource: TypedResource | None,
) -> tuple[str, str, str | None]:
    if checked_out is not None:
        if checked_out.path.resolve() == target.resolve():
            return "ready", "none", None
        return (
            "branch_checked_out_elsewhere",
            "manual_inspection_required",
            f"branch is checked out at {checked_out.path}",
        )
    if registered_at_target is not None:
        return (
            "worktree_path_registered_different_branch",
            "manual_inspection_required",
            f"target path is registered for {registered_at_target.branch_name!r}",
        )
    if target.exists():
        return (
            "worktree_path_conflict",
            "manual_inspection_required",
            "target path exists but is not registered as a git worktree",
        )
    if local_exists:
        return "local_branch_missing_worktree", "attach_existing_local_branch", None
    if remote_only:
        return (
            "remote_tracking_only_ref",
            "inspect_remote_tracking_ref",
            f"refs/remotes/origin/{branch} exists but refs/heads/{branch} does not",
        )
    if resource is not None:
        return "durable_resource_without_git_state", "manual_inspection_required", None
    return "missing", "create_branch_worktree", None


def _reconcile_session(
    operation_id: str,
    name: str,
    resource: TypedResource | None,
) -> SessionReconciliation:
    try:
        status = inspect_session(name)
    except FileNotFoundError as exc:
        status = SessionStatus(
            session_name=name,
            state="tmux_unavailable",
            exists=False,
            detail=str(exc),
        )
    except Exception as exc:
        status = SessionStatus(
            session_name=name,
            state="inspect_failed",
            exists=False,
            detail=str(exc),
        )
    return SessionReconciliation(
        operation_id=operation_id,
        session_name=name,
        state=status.state,
        exists=status.exists,
        durable_resource_id=resource.id if resource else None,
        detail=status.detail,
    )


def _repo_names(
    operation: OperationRun,
    resources: tuple[TypedResource, ...],
) -> tuple[str, ...]:
    names: set[str] = set()
    raw_names = operation.metadata.get("repo_names")
    if isinstance(raw_names, list):
        names.update(str(name) for name in raw_names)
    for resource in resources:
        if resource.resource_type is ResourceType.GIT_WORKTREE:
            repo_name = resource.details.get("repo_name")
            if repo_name is not None:
                names.add(str(repo_name))
    return tuple(sorted(names))


def _session_names(
    operation: OperationRun,
    resources: tuple[TypedResource, ...],
) -> tuple[tuple[str, TypedResource | None], ...]:
    sessions: dict[str, TypedResource | None] = {}
    metadata_name = _metadata_str(operation.metadata, "session_name")
    if metadata_name:
        sessions[metadata_name] = None
    for resource in resources:
        if resource.resource_type is not ResourceType.PROCESS_SESSION:
            continue
        resource_name = resource.details.get("session_name") or resource.name
        if resource_name:
            sessions[str(resource_name)] = resource
    if not sessions and operation.metadata.get("launch_state") == "running":
        sessions[session_name(operation.id)] = None
    return tuple(sorted(sessions.items()))


def _git_worktree_resource(
    resources: tuple[TypedResource, ...],
    repo_name: str,
) -> TypedResource | None:
    for resource in resources:
        if (
            resource.resource_type is ResourceType.GIT_WORKTREE
            and resource.details.get("repo_name") == repo_name
        ):
            return resource
    return None


def _unknown_repo_worktree(
    operation_id: str,
    repo_name: str,
    branch: str,
    target: Path,
    resource: TypedResource | None,
) -> WorktreeReconciliation:
    return WorktreeReconciliation(
        operation_id=operation_id,
        repo_name=repo_name,
        state="repo_not_registered",
        recommended_action="register_repo_or_update_operation_metadata",
        branch=branch,
        worktree_path=str(target),
        canonical_repo_path=None,
        local_branch_exists=False,
        remote_tracking_ref_exists=False,
        remote_tracking_only=False,
        target_path_exists=target.exists(),
        target_registered=False,
        durable_resource_id=resource.id if resource else None,
    )


def _git_unavailable_worktree(
    operation_id: str,
    repo: RegisteredRepo,
    branch: str,
    target: Path,
    resource: TypedResource | None,
    exc: BaseException,
) -> WorktreeReconciliation:
    return WorktreeReconciliation(
        operation_id=operation_id,
        repo_name=repo.name,
        state="git_status_unavailable",
        recommended_action="manual_inspection_required",
        branch=branch,
        worktree_path=str(target),
        canonical_repo_path=str(repo.path),
        local_branch_exists=False,
        remote_tracking_ref_exists=False,
        remote_tracking_only=False,
        target_path_exists=target.exists(),
        target_registered=False,
        durable_resource_id=resource.id if resource else None,
        detail=str(exc),
    )


def _orphan_run_dirs(
    config: AgentBoxConfig,
    known_operation_ids: set[str],
) -> tuple[OrphanRunDirReconciliation, ...]:
    if not config.runs_root.exists():
        return ()
    return tuple(
        OrphanRunDirReconciliation(operation_id=path.name, path=str(path))
        for path in sorted(config.runs_root.iterdir())
        if path.is_dir() and path.name not in known_operation_ids
    )


def _pr_info_for_branch(repo_path: Path, branch: str) -> dict[str, Any]:
    from agentbox import github

    if not github.gh_installed():
        return {"number": None, "url": None, "state": None, "title": None}
    result = github.pr_for_branch(repo_path, branch)
    if not result.get("auth_ok"):
        return {"number": None, "url": None, "state": None, "title": None}
    return {
        "number": result.get("number"),
        "url": result.get("url"),
        "state": result.get("state"),
        "title": result.get("title"),
    }


def _ci_status_for_branch(repo_path: Path, branch: str, pr_info: dict[str, Any]) -> str | None:
    from agentbox import github

    if pr_info.get("number") is None or not github.gh_installed():
        return None
    result = github.ci_status_for_branch(repo_path, branch)
    return result.get("status")


def _cleanup_recommendation_for_worktree(
    *,
    repo: RegisteredRepo,
    branch: str,
    target: Path,
    checked_out_elsewhere: bool,
    operation: OperationRun,
    pr_info: dict[str, Any],
) -> str:
    evidence: dict[str, Any] = {
        "terminal": is_terminal_operation_state(operation.state),
        "checked_out_elsewhere": checked_out_elsewhere,
        "open_pr": pr_info.get("state") == "OPEN",
    }
    status_path = target if target.exists() else repo.path
    try:
        evidence["dirty"] = bool(
            git(status_path, "status", "--porcelain", check=False).stdout.strip()
        )
    except Exception:
        evidence["dirty"] = False
    try:
        op_status = git_operation_status(status_path)
        evidence["git_operation_in_progress"] = op_status.in_progress
    except Exception:
        evidence["git_operation_in_progress"] = False
    try:
        evidence["merged"] = _is_ancestor(repo.path, branch, repo.default_ref)
        evidence["unique_commits"] = (
            not evidence["merged"]
            and has_local_branch(repo.path, branch)
            and _has_unique_commits(repo.path, branch, repo.default_ref)
        )
    except Exception:
        evidence["merged"] = False
        evidence["unique_commits"] = False
    return _classify_cleanup_recommendation(evidence)


def _is_ancestor(repo_path: Path, descendant: str, ancestor: str) -> bool:
    import subprocess

    result = subprocess.run(
        ("git", "merge-base", "--is-ancestor", descendant, ancestor),
        cwd=repo_path,
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


def _has_unique_commits(repo_path: Path, branch: str, base: str) -> bool:
    from agentbox.git_worktree import git

    result = git(repo_path, "log", f"{base}..{branch}", "--oneline", check=False)
    return bool(result.stdout.strip())


def _checked_out_from(
    worktrees: tuple[WorktreeInfo, ...],
    branch: str,
) -> WorktreeInfo | None:
    for worktree in worktrees:
        if worktree.branch_name == branch:
            return worktree
    return None


def _registered_at(
    worktrees: tuple[WorktreeInfo, ...],
    target: Path,
) -> WorktreeInfo | None:
    resolved = target.resolve()
    for worktree in worktrees:
        if worktree.path.resolve() == resolved:
            return worktree
    return None


def _metadata_str(metadata: Mapping[str, Any], key: str) -> str | None:
    value = metadata.get(key)
    if value is None:
        return None
    return str(value)


def _asdict(value: Any) -> Any:
    return asdict(value)


__all__ = [
    "FileProbe",
    "OperationReconciliation",
    "OrphanRunDirReconciliation",
    "ReconciliationReport",
    "RunDirReconciliation",
    "SessionReconciliation",
    "WorktreeReconciliation",
    "parse_porcelain_paths",
    "probe_dirty_paths",
    "probe_file",
    "reconcile",
]
