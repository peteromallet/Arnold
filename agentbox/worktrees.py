"""Operation-scoped git worktree allocation for AgentBox."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any, Mapping

from arnold.runtime.durable_ops import (
    ResourceType,
    TypedResource,
    TypedResourceAlreadyExists,
)

from agentbox.config import AgentBoxConfig
from agentbox.git_worktree import (
    GitWorktreeError,
    WorktreeInfo,
    attach_existing_local_branch,
    checked_out_branch_worktree,
    create_branch_worktree,
    has_local_branch,
    has_remote_tracking_ref,
    is_registered_worktree,
    list_worktrees,
    resolve_ref,
)
from agentbox.locks import acquire_repo_lock
from agentbox.operations import open_operation_store
from agentbox.repos import RegisteredRepo, get_repo


_BRANCH_COMPONENT_PATTERN = re.compile(r"[^A-Za-z0-9._-]+")


class WorktreeAllocationError(RuntimeError):
    """Raised when a worktree cannot be represented without destructive action."""

    def __init__(
        self,
        kind: str,
        message: str,
        *,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.kind = kind
        self.details = dict(details or {})


@dataclass(frozen=True)
class WorktreeAllocation:
    """Result of representing one operation/repo git worktree."""

    operation_id: str
    repo_name: str
    canonical_repo_path: Path
    worktree_path: Path
    branch: str
    base_ref: str
    base_sha: str
    status: str
    resource: TypedResource
    worktree: WorktreeInfo | None = None


def worktree_path(config: AgentBoxConfig, operation_id: str, repo_name: str) -> Path:
    """Return the operation-scoped worktree path for ``repo_name``."""

    return config.runs_root / operation_id / "worktrees" / repo_name


def branch_name(operation_id: str, repo_name: str) -> str:
    """Return the deterministic local branch name for an operation repo."""

    return f"agentbox/{_branch_component(operation_id)}/{_branch_component(repo_name)}"


def allocate_worktree(
    config: AgentBoxConfig,
    operation_id: str,
    repo_name: str,
    *,
    base_ref: str | None = None,
    lock_timeout_seconds: float = 30.0,
) -> WorktreeAllocation:
    """Allocate or re-represent one operation-scoped git worktree.

    This function is intentionally non-destructive: it never removes paths, branches,
    registrations, or durable resources. Retry paths either reuse the existing
    durable resource/worktree or fail with a typed conflict.
    """

    repo = get_repo(config, repo_name)
    selected_base_ref = base_ref or repo.default_ref
    branch = branch_name(operation_id, repo.name)
    target = worktree_path(config, operation_id, repo.name)

    with acquire_repo_lock(
        config,
        repo.name,
        timeout_seconds=lock_timeout_seconds,
    ):
        return _allocate_locked(
            config,
            operation_id=operation_id,
            repo=repo,
            branch=branch,
            target=target,
            base_ref=selected_base_ref,
        )


def record_worktree_resource(
    config: AgentBoxConfig,
    allocation: WorktreeAllocation,
) -> TypedResource:
    """Record a GIT_WORKTREE resource, returning an existing one on retry."""

    return _create_or_reuse_resource(
        config,
        operation_id=allocation.operation_id,
        repo_name=allocation.repo_name,
        canonical_repo_path=allocation.canonical_repo_path,
        worktree_path=allocation.worktree_path,
        branch=allocation.branch,
        base_ref=allocation.base_ref,
        base_sha=allocation.base_sha,
        status=allocation.status,
    )


def _allocate_locked(
    config: AgentBoxConfig,
    *,
    operation_id: str,
    repo: RegisteredRepo,
    branch: str,
    target: Path,
    base_ref: str,
) -> WorktreeAllocation:
    existing_resource = _existing_resource(config, operation_id, repo.name)
    base_sha = resolve_ref(repo.path, base_ref)
    checked_out = checked_out_branch_worktree(repo.path, branch)

    if checked_out is not None:
        if checked_out.path.resolve() != target.resolve():
            raise WorktreeAllocationError(
                "branch_checked_out_elsewhere",
                f"branch {branch!r} is already checked out at {checked_out.path}",
                details={
                    "repo_name": repo.name,
                    "branch": branch,
                    "existing_path": str(checked_out.path),
                    "requested_path": str(target),
                },
            )
        _validate_existing_resource(
            existing_resource,
            repo=repo,
            branch=branch,
            target=target,
        )
        return _allocation_with_resource(
            config,
            operation_id=operation_id,
            repo=repo,
            branch=branch,
            target=target,
            base_ref=base_ref,
            base_sha=base_sha,
            status="reused_registered_worktree",
            worktree=checked_out,
            existing_resource=existing_resource,
        )

    if target.exists() and not is_registered_worktree(repo.path, target):
        raise WorktreeAllocationError(
            "worktree_path_conflict",
            f"worktree path already exists and is not registered: {target}",
            details={"repo_name": repo.name, "path": str(target), "branch": branch},
        )
    registered_at_target = _registered_worktree_at(repo.path, target)
    if registered_at_target is not None:
        raise WorktreeAllocationError(
            "worktree_path_conflict",
            f"worktree path is registered for a different branch: {target}",
            details={
                "repo_name": repo.name,
                "path": str(target),
                "branch": branch,
                "observed_branch": registered_at_target.branch_name,
            },
        )

    _validate_existing_resource(
        existing_resource,
        repo=repo,
        branch=branch,
        target=target,
        allow_missing_worktree=True,
    )

    if has_local_branch(repo.path, branch):
        try:
            worktree = attach_existing_local_branch(repo.path, target, branch)
        except GitWorktreeError as exc:
            raise WorktreeAllocationError(
                "local_branch_reattach_failed",
                str(exc),
                details={"repo_name": repo.name, "path": str(target), "branch": branch},
            ) from exc
        return _allocation_with_resource(
            config,
            operation_id=operation_id,
            repo=repo,
            branch=branch,
            target=target,
            base_ref=base_ref,
            base_sha=base_sha,
            status="reattached_local_branch",
            worktree=worktree,
            existing_resource=existing_resource,
        )

    if has_remote_tracking_ref(repo.path, f"origin/{branch}"):
        raise WorktreeAllocationError(
            "remote_tracking_branch_conflict",
            f"branch {branch!r} exists only as a remote-tracking ref",
            details={
                "repo_name": repo.name,
                "branch": branch,
                "remote_ref": f"refs/remotes/origin/{branch}",
            },
        )

    try:
        worktree = create_branch_worktree(repo.path, target, branch, base_ref)
    except GitWorktreeError as exc:
        if has_remote_tracking_ref(repo.path, f"origin/{branch}"):
            raise WorktreeAllocationError(
                "remote_tracking_branch_conflict",
                f"branch {branch!r} exists only as a remote-tracking ref",
                details={
                    "repo_name": repo.name,
                    "branch": branch,
                    "remote_ref": f"refs/remotes/origin/{branch}",
                },
            ) from exc
        raise WorktreeAllocationError(
            "git_worktree_create_failed",
            str(exc),
            details={"repo_name": repo.name, "path": str(target), "branch": branch},
        ) from exc
    return _allocation_with_resource(
        config,
        operation_id=operation_id,
        repo=repo,
        branch=branch,
        target=target,
        base_ref=base_ref,
        base_sha=base_sha,
        status="created",
        worktree=worktree,
        existing_resource=existing_resource,
    )


def _allocation_with_resource(
    config: AgentBoxConfig,
    *,
    operation_id: str,
    repo: RegisteredRepo,
    branch: str,
    target: Path,
    base_ref: str,
    base_sha: str,
    status: str,
    worktree: WorktreeInfo | None,
    existing_resource: TypedResource | None,
) -> WorktreeAllocation:
    resource = existing_resource or _create_or_reuse_resource(
        config,
        operation_id=operation_id,
        repo_name=repo.name,
        canonical_repo_path=repo.path,
        worktree_path=target,
        branch=branch,
        base_ref=base_ref,
        base_sha=base_sha,
        status=status,
    )
    return WorktreeAllocation(
        operation_id=operation_id,
        repo_name=repo.name,
        canonical_repo_path=repo.path,
        worktree_path=target,
        branch=branch,
        base_ref=base_ref,
        base_sha=base_sha,
        status=status,
        resource=resource,
        worktree=worktree,
    )


def _create_or_reuse_resource(
    config: AgentBoxConfig,
    *,
    operation_id: str,
    repo_name: str,
    canonical_repo_path: Path,
    worktree_path: Path,
    branch: str,
    base_ref: str,
    base_sha: str,
    status: str,
) -> TypedResource:
    resource = TypedResource(
        id=_resource_id(operation_id, repo_name),
        operation_id=operation_id,
        resource_type=ResourceType.GIT_WORKTREE,
        name=f"{repo_name} worktree",
        details={
            "repo_name": repo_name,
            "canonical_repo_path": str(canonical_repo_path),
            "worktree_path": str(worktree_path),
            "branch": branch,
            "base_ref": base_ref,
            "base_sha": base_sha,
            "status": status,
        },
    )
    store = open_operation_store(config)
    try:
        return store.create_typed_resource(resource)
    except TypedResourceAlreadyExists:
        existing = _existing_resource(config, operation_id, repo_name)
        if existing is not None:
            return existing
        raise


def _existing_resource(
    config: AgentBoxConfig,
    operation_id: str,
    repo_name: str,
) -> TypedResource | None:
    resource_id = _resource_id(operation_id, repo_name)
    for resource in open_operation_store(config).list_typed_resources(operation_id):
        if resource.id == resource_id:
            return resource
    return None


def _registered_worktree_at(repo_path: Path, target: Path) -> WorktreeInfo | None:
    resolved = target.resolve()
    for worktree in list_worktrees(repo_path):
        if worktree.path.resolve() == resolved:
            return worktree
    return None


def _validate_existing_resource(
    resource: TypedResource | None,
    *,
    repo: RegisteredRepo,
    branch: str,
    target: Path,
    allow_missing_worktree: bool = False,
) -> None:
    if resource is None:
        return
    expected = {
        "repo_name": repo.name,
        "canonical_repo_path": str(repo.path),
        "worktree_path": str(target),
        "branch": branch,
    }
    mismatches = {
        key: {"expected": value, "actual": resource.details.get(key)}
        for key, value in expected.items()
        if resource.details.get(key) != value
    }
    if mismatches:
        raise WorktreeAllocationError(
            "git_worktree_resource_conflict",
            f"existing git worktree resource does not match requested repo {repo.name!r}",
            details={
                "resource_id": resource.id,
                "repo_name": repo.name,
                "mismatches": mismatches,
            },
        )
    if not allow_missing_worktree:
        if not is_registered_worktree(repo.path, target):
            raise WorktreeAllocationError(
                "git_worktree_resource_stale",
                f"existing git worktree resource points at an unregistered path: {target}",
                details={
                    "resource_id": resource.id,
                    "repo_name": repo.name,
                    "path": str(target),
                    "branch": branch,
                },
            )


def _resource_id(operation_id: str, repo_name: str) -> str:
    return f"{operation_id}:{repo_name}:git-worktree"


def _branch_component(value: str) -> str:
    cleaned = _BRANCH_COMPONENT_PATTERN.sub("-", value).strip(".-/")
    return cleaned or "unnamed"


__all__ = [
    "WorktreeAllocation",
    "WorktreeAllocationError",
    "allocate_worktree",
    "branch_name",
    "record_worktree_resource",
    "worktree_path",
]
