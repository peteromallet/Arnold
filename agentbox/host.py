"""Host-local AgentBox launch orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from arnold.runtime.durable_ops import (
    OperationAlreadyExists,
    OperationState,
    TypedResource,
)

from agentbox.config import AgentBoxConfig
from agentbox.operations import (
    create_agentbox_operation,
    load_agentbox_operation,
    update_agentbox_operation,
)
from agentbox.run_dirs import (
    RunDirPaths,
    append_event,
    ensure_run_dir,
    read_metadata,
    record_log_resources,
    write_metadata,
)
from agentbox.tmux import (
    SessionStatus,
    inspect_session,
    record_process_session_resource,
    start_session,
)
from agentbox.worktrees import WorktreeAllocation, WorktreeAllocationError, allocate_worktree


class HostLaunchError(RuntimeError):
    """Raised after persisting diagnostics for an unsuccessful host launch."""

    def __init__(
        self,
        kind: str,
        message: str,
        *,
        diagnostics: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.kind = kind
        self.diagnostics = dict(diagnostics or {})


@dataclass(frozen=True)
class HostLaunchResult:
    """Durable resources and state created by one host launch attempt."""

    operation_id: str
    launch_state: str
    operation_state: OperationState
    run_paths: RunDirPaths
    worktrees: tuple[WorktreeAllocation, ...]
    log_resources: tuple[TypedResource, TypedResource]
    session_name: str | None = None
    session_status: SessionStatus | None = None
    process_session_resource: TypedResource | None = None
    diagnostics: Mapping[str, Any] | None = None


def launch_host(
    config: AgentBoxConfig,
    operation_id: str,
    *,
    command: Sequence[str] | str,
    repo_names: Sequence[str] = (),
    base_refs: Mapping[str, str] | None = None,
    cwd: Path | str | None = None,
    metadata: Mapping[str, Any] | None = None,
    lock_timeout_seconds: float = 30.0,
) -> HostLaunchResult:
    """Create or load an operation, provision repos, then start tmux.

    The launch is intentionally ordered so tmux never starts until every requested
    repository has an operation-scoped worktree. Partial worktree/log/run-dir
    artifacts are left in place and represented in metadata/events for retry.
    """

    run = _create_or_load_operation(
        config,
        operation_id,
        command=command,
        repo_names=repo_names,
        metadata=metadata,
    )
    run_paths = ensure_run_dir(config, operation_id, metadata=dict(run.metadata))
    append_event(
        run_paths,
        "host_launch.started",
        payload={"repo_names": list(repo_names), "command": _command_payload(command)},
    )
    log_resources = record_log_resources(config, operation_id)

    worktrees: list[WorktreeAllocation] = []
    try:
        for repo_name in repo_names:
            allocation = allocate_worktree(
                config,
                operation_id,
                repo_name,
                base_ref=(base_refs or {}).get(repo_name),
                lock_timeout_seconds=lock_timeout_seconds,
            )
            worktrees.append(allocation)
            append_event(
                run_paths,
                "host_launch.worktree_ready",
                payload=_worktree_payload(allocation),
            )
    except WorktreeAllocationError as exc:
        diagnostics = {
            "phase": "worktrees",
            "kind": exc.kind,
            "message": str(exc),
            "details": exc.details,
            "completed_repos": [allocation.repo_name for allocation in worktrees],
            "requested_repos": list(repo_names),
        }
        _record_failed_attempt(config, operation_id, run_paths, diagnostics)
        raise HostLaunchError(exc.kind, str(exc), diagnostics=diagnostics) from exc
    except Exception as exc:
        diagnostics = {
            "phase": "worktrees",
            "kind": type(exc).__name__,
            "message": str(exc),
            "completed_repos": [allocation.repo_name for allocation in worktrees],
            "requested_repos": list(repo_names),
        }
        _record_failed_attempt(config, operation_id, run_paths, diagnostics)
        raise HostLaunchError("worktree_provision_failed", str(exc), diagnostics=diagnostics) from exc

    session_name = None
    try:
        session_name = start_session(
            operation_id,
            command,
            cwd=cwd or _default_cwd(worktrees, run_paths),
            run_paths=run_paths,
        )
        status = inspect_session(session_name)
        process_resource = record_process_session_resource(
            config,
            operation_id,
            name=session_name,
            status=status,
            details={"command": _command_payload(command)},
        )
    except Exception as exc:
        diagnostics = {
            "phase": "tmux",
            "kind": type(exc).__name__,
            "message": str(exc),
            "session_name": session_name,
            "completed_repos": [allocation.repo_name for allocation in worktrees],
            "requested_repos": list(repo_names),
        }
        _record_failed_attempt(config, operation_id, run_paths, diagnostics)
        raise HostLaunchError("tmux_launch_failed", str(exc), diagnostics=diagnostics) from exc

    updated = update_agentbox_operation(
        config,
        operation_id,
        metadata={
            "session_name": session_name,
            "worktrees": [_worktree_payload(allocation) for allocation in worktrees],
        },
        launch_state="running",
        state=OperationState.RUNNING,
    )
    _merge_run_metadata(
        run_paths,
        {
            "launch_state": "running",
            "operation_state": updated.state.value,
            "session_name": session_name,
            "worktrees": [_worktree_payload(allocation) for allocation in worktrees],
        },
    )
    append_event(
        run_paths,
        "host_launch.running",
        payload={"session_name": session_name, "session_state": status.state},
    )
    return HostLaunchResult(
        operation_id=operation_id,
        launch_state="running",
        operation_state=updated.state,
        run_paths=run_paths,
        worktrees=tuple(worktrees),
        log_resources=log_resources,
        session_name=session_name,
        session_status=status,
        process_session_resource=process_resource,
    )


def _create_or_load_operation(
    config: AgentBoxConfig,
    operation_id: str,
    *,
    command: Sequence[str] | str,
    repo_names: Sequence[str],
    metadata: Mapping[str, Any] | None,
) -> Any:
    try:
        return create_agentbox_operation(
            config,
            operation_id,
            command=command,
            repo_names=repo_names,
            launch_state="launching",
            metadata=metadata,
        )
    except OperationAlreadyExists:
        return load_agentbox_operation(config, operation_id)


def _record_failed_attempt(
    config: AgentBoxConfig,
    operation_id: str,
    run_paths: RunDirPaths,
    diagnostics: Mapping[str, Any],
) -> None:
    update_agentbox_operation(
        config,
        operation_id,
        metadata={"launch_diagnostics": dict(diagnostics)},
        launch_state="failed_before_running",
    )
    _merge_run_metadata(
        run_paths,
        {
            "launch_state": "failed_before_running",
            "operation_state": load_agentbox_operation(config, operation_id).state.value,
            "launch_diagnostics": dict(diagnostics),
        },
    )
    append_event(run_paths, "host_launch.failed", payload=dict(diagnostics))


def _merge_run_metadata(paths: RunDirPaths, values: Mapping[str, Any]) -> None:
    current = read_metadata(paths)
    current.update(values)
    write_metadata(paths, current)


def _default_cwd(worktrees: Sequence[WorktreeAllocation], run_paths: RunDirPaths) -> Path:
    if worktrees:
        return worktrees[0].worktree_path
    return run_paths.root


def _worktree_payload(allocation: WorktreeAllocation) -> dict[str, Any]:
    return {
        "repo_name": allocation.repo_name,
        "worktree_path": str(allocation.worktree_path),
        "branch": allocation.branch,
        "base_ref": allocation.base_ref,
        "base_sha": allocation.base_sha,
        "status": allocation.status,
    }


def _command_payload(command: Sequence[str] | str) -> str | list[str]:
    if isinstance(command, str):
        return command
    return list(command)


__all__ = [
    "HostLaunchError",
    "HostLaunchResult",
    "launch_host",
]
