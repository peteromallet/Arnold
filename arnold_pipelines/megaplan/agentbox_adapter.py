"""AgentBox adapter for Megaplan chain operations."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from arnold.runtime.durable_ops import (
    OperationNotFound,
    OperationState,
    ResourceType,
    can_transition_operation,
    is_terminal_operation_state,
)
from arnold_pipelines.megaplan.chain.spec import load_spec, validate_paths
from arnold_pipelines.megaplan.chain.status import ChainStatusSnapshot, build_chain_status_snapshot
from arnold_pipelines.megaplan.types import CliError

from agentbox.config import AgentBoxConfig
from agentbox.host import (
    HostLaunchError,
    HostLaunchResult,
    HostPreparedResources,
    prepare_host_resources,
    start_host_session,
)
from agentbox.operations import load_agentbox_operation, open_operation_store, update_agentbox_operation
from agentbox.repos import get_repo
from agentbox.run_dirs import RunDirPaths, append_event, read_metadata, run_dir_paths, write_metadata
from agentbox.tmux import inspect_session
from agentbox.worktrees import WorktreeAllocation


MEGAPLAN_CHAIN_OPERATION_TYPE = "megaplan_chain"


class MegaplanChainLaunchError(RuntimeError):
    """Raised after Megaplan chain launch diagnostics have been persisted."""

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
class MegaplanChainLaunchResult:
    """Result of preparing, validating, and starting a Megaplan chain."""

    host_result: HostLaunchResult
    resolved_spec_path: Path
    project_root: Path

    @property
    def operation_id(self) -> str:
        return self.host_result.operation_id

    @property
    def launch_state(self) -> str:
        return self.host_result.launch_state


class MegaplanChainHandler:
    """Launch Megaplan chains through AgentBox-owned durable resources."""

    operation_type = MEGAPLAN_CHAIN_OPERATION_TYPE

    def launch(
        self,
        config: AgentBoxConfig,
        operation_id: str,
        *,
        repo_name: str,
        spec_path: Path | str,
        base_ref: str | None = None,
        metadata: Mapping[str, Any] | None = None,
        lock_timeout_seconds: float = 30.0,
    ) -> MegaplanChainLaunchResult:
        """Prepare AgentBox resources, validate the chain spec, then start tmux."""

        existing = _load_existing_megaplan_operation(config, operation_id)
        if existing is not None:
            if is_terminal_operation_state(existing.state):
                message = (
                    f"operation {operation_id!r} is terminal "
                    f"({existing.state.value}) and cannot be relaunched"
                )
                diagnostics = {
                    "phase": "retry",
                    "kind": "terminal_operation",
                    "message": message,
                    "operation_state": existing.state.value,
                    "launch_state": existing.metadata.get("launch_state"),
                }
                _record_retry_refusal(config, operation_id, diagnostics)
                raise MegaplanChainLaunchError(
                    "terminal_operation",
                    message,
                    diagnostics=diagnostics,
                )
            running_result = _summarize_live_running_session(config, existing)
            if running_result is not None:
                if metadata:
                    update_agentbox_operation(
                        config,
                        operation_id,
                        metadata=metadata,
                        expected_lock_version=existing.lock_version,
                    )
                return MegaplanChainLaunchResult(
                    host_result=running_result,
                    resolved_spec_path=_resolved_spec_from_metadata(existing.metadata),
                    project_root=_project_root_from_metadata(existing.metadata),
                )

        launch_metadata = {
            "adapter": "megaplan_chain",
            "spec_path": str(spec_path),
        }
        if metadata:
            launch_metadata.update(dict(metadata))
        prepared = prepare_host_resources(
            config,
            operation_id,
            operation_type=MEGAPLAN_CHAIN_OPERATION_TYPE,
            command=_prevalidation_command(spec_path),
            repo_names=(repo_name,),
            base_refs={repo_name: base_ref} if base_ref else None,
            launch_intent="megaplan_chain",
            metadata=launch_metadata,
            lock_timeout_seconds=lock_timeout_seconds,
        )
        project_root = _primary_worktree(prepared)
        resolved_spec_path = _resolve_spec_path(spec_path, project_root)

        try:
            spec = load_spec(resolved_spec_path)
            validate_paths(spec, project_root)
        except CliError as exc:
            diagnostics = _validation_diagnostics(
                kind=exc.code,
                message=exc.message,
                spec_path=resolved_spec_path,
                project_root=project_root,
                extra=exc.extra,
            )
            _record_validation_failure(config, operation_id, prepared.run_paths, diagnostics)
            raise MegaplanChainLaunchError(exc.code, exc.message, diagnostics=diagnostics) from exc
        except Exception as exc:
            diagnostics = _validation_diagnostics(
                kind=type(exc).__name__,
                message=str(exc),
                spec_path=resolved_spec_path,
                project_root=project_root,
            )
            _record_validation_failure(config, operation_id, prepared.run_paths, diagnostics)
            raise MegaplanChainLaunchError("validation_failed", str(exc), diagnostics=diagnostics) from exc

        command = _chain_start_command(resolved_spec_path, project_root)
        validation = {
            "status": "passed",
            "spec_path": str(resolved_spec_path),
            "project_root": str(project_root),
        }
        update_agentbox_operation(
            config,
            operation_id,
            metadata={
                "command": list(command),
                "resolved_spec_path": str(resolved_spec_path),
                "project_root": str(project_root),
                "validation": validation,
            },
            launch_state="validated",
        )
        _merge_run_metadata(
            prepared.run_paths,
            {
                "command": list(command),
                "resolved_spec_path": str(resolved_spec_path),
                "project_root": str(project_root),
                "validation": validation,
            },
        )
        append_event(
            prepared.run_paths,
            "megaplan_chain.validation_passed",
            payload={"spec_path": str(resolved_spec_path), "project_root": str(project_root)},
        )
        try:
            host_result = start_host_session(
                config,
                prepared,
                command=command,
                cwd=project_root,
            )
        except HostLaunchError as exc:
            raise MegaplanChainLaunchError(
                exc.kind,
                str(exc),
                diagnostics=exc.diagnostics,
            ) from exc
        return MegaplanChainLaunchResult(
            host_result=host_result,
            resolved_spec_path=resolved_spec_path,
            project_root=project_root,
        )

    def status(self, config: AgentBoxConfig, operation_id: str) -> ChainStatusSnapshot:
        """Return a provider-independent chain status snapshot."""

        run = load_agentbox_operation(
            config,
            operation_id,
            operation_types=(MEGAPLAN_CHAIN_OPERATION_TYPE,),
        )
        resources = open_operation_store(config).list_typed_resources(operation_id)
        return build_chain_status_snapshot(
            run,
            resources=resources,
            inspect_runner=inspect_session,
        )

    def tick(self, config: AgentBoxConfig, operation_id: str) -> Any:
        """Refresh persisted operation state from the chain classifier."""

        snapshot = self.status(config, operation_id)
        classification = snapshot.classification
        current = load_agentbox_operation(
            config,
            operation_id,
            operation_types=(MEGAPLAN_CHAIN_OPERATION_TYPE,),
        )
        previous = _classification_metadata(current.metadata)
        current_summary = classification.to_dict()
        metadata = {
            "chain_status": current_summary,
            "chain_status_snapshot": {
                "effective_status": classification.effective_status,
                "reason": classification.reason,
                "runner": snapshot.runner,
                "plan_status": snapshot.plan_status,
            },
        }
        target_state = classification.operation_state
        update_state: OperationState | None = None
        if target_state is not current.state and can_transition_operation(current.state, target_state):
            update_state = target_state
        updated = update_agentbox_operation(
            config,
            operation_id,
            metadata=metadata,
            state=update_state,
        )
        if previous != current_summary:
            paths = run_dir_paths(config, operation_id)
            append_event(
                paths,
                "megaplan_chain.status_changed",
                payload={
                    "previous": previous,
                    "current": current_summary,
                    "persisted_operation_state": updated.state.value,
                },
            )
        return updated

    def resume(self, config: AgentBoxConfig, operation_id: str) -> Any:
        """Restart the stored chain command for stale suspended runner cases."""

        snapshot = self.status(config, operation_id)
        classification = snapshot.classification
        if (
            classification.operation_state is OperationState.PENDING
            and snapshot.launch_state == "failed_before_running"
        ):
            message = (
                f"operation {operation_id!r} failed before the chain runner started; "
                "retry the launch with `agentbox run --operation-id`"
            )
            diagnostics = {
                "phase": "resume",
                "kind": "pre_running_retry_required",
                "message": message,
                "launch_state": snapshot.launch_state,
            }
            _record_resume_refusal(config, operation_id, diagnostics)
            raise MegaplanChainLaunchError(
                "pre_running_retry_required",
                message,
                diagnostics=diagnostics,
            )

        if not _is_stale_runner_resume(snapshot):
            message = (
                f"operation {operation_id!r} is {classification.effective_status!r} "
                f"({classification.reason}) and is not a stale runner resume candidate"
            )
            diagnostics = {
                "phase": "resume",
                "kind": "resume_not_allowed",
                "message": message,
                "classification": classification.to_dict(),
                "runner": snapshot.runner,
            }
            _record_resume_refusal(config, operation_id, diagnostics)
            raise MegaplanChainLaunchError("resume_not_allowed", message, diagnostics=diagnostics)

        run = load_agentbox_operation(
            config,
            operation_id,
            operation_types=(MEGAPLAN_CHAIN_OPERATION_TYPE,),
        )
        resources = open_operation_store(config).list_typed_resources(operation_id)
        command = _stored_chain_command(run.metadata)
        prepared = HostPreparedResources(
            operation_id=operation_id,
            run_paths=run_dir_paths(config, operation_id),
            requested_repo_names=tuple(str(name) for name in run.metadata.get("repo_names", ())),
            worktrees=_worktrees_from_resources(config, operation_id, list(resources)),
            log_resources=tuple(
                resource for resource in resources if resource.resource_type is ResourceType.LOG
            ),
        )
        try:
            result = start_host_session(
                config,
                prepared,
                command=command,
                cwd=snapshot.project_root,
            )
        except HostLaunchError as exc:
            raise MegaplanChainLaunchError(
                exc.kind,
                str(exc),
                diagnostics=exc.diagnostics,
            ) from exc
        append_event(
            result.run_paths,
            "megaplan_chain.resumed",
            payload={
                "reason": classification.reason,
                "runner": snapshot.runner,
                "session_name": result.session_name,
            },
        )
        return load_agentbox_operation(
            config,
            operation_id,
            operation_types=(MEGAPLAN_CHAIN_OPERATION_TYPE,),
        )

    def summarize(self, config: AgentBoxConfig, operation_id: str) -> str:
        """Return compact CLI-oriented status text for a chain operation."""

        snapshot = self.status(config, operation_id)
        classification = snapshot.classification
        parts = [
            f"{snapshot.operation_id}: {classification.effective_status}",
            f"state={classification.operation_state.value}",
            f"reason={classification.reason}",
        ]
        current_plan = snapshot.chain_state.get("current_plan_name")
        if current_plan:
            parts.append(f"plan={current_plan}")
        runner_status = snapshot.runner.get("status")
        if runner_status:
            parts.append(f"runner={runner_status}")
        if snapshot.spec_path is not None:
            parts.append(f"spec={snapshot.spec_path}")
        return " ".join(parts)

    def cleanup_descriptor(self, config: AgentBoxConfig, operation_id: str) -> dict[str, Any]:
        """Describe operation-owned resources without deleting anything."""

        run = load_agentbox_operation(
            config,
            operation_id,
            operation_types=(MEGAPLAN_CHAIN_OPERATION_TYPE,),
        )
        resources = open_operation_store(config).list_typed_resources(operation_id)
        paths = run_dir_paths(config, operation_id)
        return {
            "operation_id": operation_id,
            "operation_type": run.operation_type,
            "operation_state": run.state.value,
            "non_destructive": True,
            "run_dir": str(paths.root),
            "paths": {
                "events": str(paths.events_path),
                "metadata": str(paths.metadata_path),
                "stdout": str(paths.stdout_path),
                "stderr": str(paths.stderr_path),
            },
            "resources": [
                {
                    "id": resource.id,
                    "type": resource.resource_type.value,
                    "name": resource.name,
                    "details": dict(resource.details),
                }
                for resource in resources
            ],
        }


def get_agentbox_adapter() -> MegaplanChainHandler:
    """Factory used by the lazy AgentBox adapter registry."""

    return MegaplanChainHandler()


def _prevalidation_command(spec_path: Path | str) -> list[str]:
    return [
        "python",
        "-m",
        "arnold_pipelines.megaplan",
        "chain",
        "start",
        "--spec",
        str(spec_path),
    ]


def _chain_start_command(spec_path: Path, project_root: Path) -> tuple[str, ...]:
    return (
        "python",
        "-m",
        "arnold_pipelines.megaplan",
        "chain",
        "start",
        "--spec",
        str(spec_path),
        "--project-dir",
        str(project_root),
    )


def _primary_worktree(prepared: HostPreparedResources) -> Path:
    if not prepared.worktrees:
        raise MegaplanChainLaunchError(
            "missing_worktree",
            "megaplan_chain launch requires at least one prepared worktree",
            diagnostics={"phase": "prepare", "kind": "missing_worktree"},
        )
    return prepared.worktrees[0].worktree_path.expanduser().resolve()


def _resolve_spec_path(spec_path: Path | str, project_root: Path) -> Path:
    path = Path(spec_path).expanduser()
    if not path.is_absolute():
        path = project_root / path
    return path.resolve()


def _validation_diagnostics(
    *,
    kind: str,
    message: str,
    spec_path: Path,
    project_root: Path,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    diagnostics = {
        "phase": "validation",
        "kind": kind,
        "message": message,
        "spec_path": str(spec_path),
        "project_root": str(project_root),
    }
    if extra:
        diagnostics["extra"] = dict(extra)
    return diagnostics


def _record_validation_failure(
    config: AgentBoxConfig,
    operation_id: str,
    run_paths: RunDirPaths,
    diagnostics: Mapping[str, Any],
) -> None:
    validation = {"status": "failed", **dict(diagnostics)}
    update_agentbox_operation(
        config,
        operation_id,
        metadata={"launch_diagnostics": dict(diagnostics), "validation": validation},
        launch_state="failed_before_running",
    )
    _merge_run_metadata(
        run_paths,
        {
            "launch_state": "failed_before_running",
            "launch_diagnostics": dict(diagnostics),
            "validation": validation,
        },
    )
    append_event(run_paths, "megaplan_chain.validation_failed", payload=dict(diagnostics))


def _load_existing_megaplan_operation(config: AgentBoxConfig, operation_id: str) -> Any | None:
    try:
        return load_agentbox_operation(
            config,
            operation_id,
            operation_types=(MEGAPLAN_CHAIN_OPERATION_TYPE,),
        )
    except OperationNotFound:
        return None


def _record_retry_refusal(
    config: AgentBoxConfig,
    operation_id: str,
    diagnostics: Mapping[str, Any],
) -> None:
    paths = run_dir_paths(config, operation_id)
    if paths.root.exists():
        _merge_run_metadata(paths, {"retry_refusal": dict(diagnostics)})
        append_event(paths, "megaplan_chain.retry_refused", payload=dict(diagnostics))


def _record_resume_refusal(
    config: AgentBoxConfig,
    operation_id: str,
    diagnostics: Mapping[str, Any],
) -> None:
    paths = run_dir_paths(config, operation_id)
    if paths.root.exists():
        _merge_run_metadata(paths, {"resume_refusal": dict(diagnostics)})
        append_event(paths, "megaplan_chain.resume_refused", payload=dict(diagnostics))


def _summarize_live_running_session(config: AgentBoxConfig, run: Any) -> HostLaunchResult | None:
    if run.state is not OperationState.RUNNING:
        return None
    resources = open_operation_store(config).list_typed_resources(run.id)
    process_resources = [
        resource for resource in resources if resource.resource_type is ResourceType.PROCESS_SESSION
    ]
    session_name = _session_name_from_run(run.metadata, process_resources)
    if not session_name:
        return None
    status = inspect_session(session_name)
    if not status.exists or status.state != "running":
        return None

    run_paths = run_dir_paths(config, run.id)
    payload = {"session_name": session_name, "session_state": status.state}
    append_event(run_paths, "megaplan_chain.running_reused", payload=payload)
    _merge_run_metadata(run_paths, {"duplicate_launch": payload})
    return HostLaunchResult(
        operation_id=run.id,
        launch_state="running",
        operation_state=run.state,
        run_paths=run_paths,
        worktrees=_worktrees_from_resources(config, run.id, resources),
        log_resources=tuple(
            resource for resource in resources if resource.resource_type is ResourceType.LOG
        ),
        session_name=session_name,
        session_status=status,
        process_session_resource=process_resources[0] if process_resources else None,
        diagnostics={
            "phase": "retry",
            "kind": "already_running",
            "message": f"operation {run.id!r} already has a live RUNNING session",
            "session_name": session_name,
        },
    )


def _session_name_from_run(metadata: Mapping[str, Any], process_resources: list[Any]) -> str | None:
    value = metadata.get("session_name")
    if isinstance(value, str) and value:
        return value
    for resource in process_resources:
        value = resource.details.get("session_name")
        if isinstance(value, str) and value:
            return value
    return None


def _worktrees_from_resources(
    config: AgentBoxConfig,
    operation_id: str,
    resources: list[Any],
) -> tuple[WorktreeAllocation, ...]:
    worktrees: list[WorktreeAllocation] = []
    for resource in resources:
        if resource.resource_type is not ResourceType.GIT_WORKTREE:
            continue
        repo_name = str(resource.details["repo_name"])
        repo = get_repo(config, repo_name)
        worktrees.append(
            WorktreeAllocation(
                operation_id=operation_id,
                repo_name=repo_name,
                canonical_repo_path=Path(str(resource.details["canonical_repo_path"])),
                worktree_path=Path(str(resource.details["worktree_path"])),
                branch=str(resource.details["branch"]),
                base_ref=str(resource.details["base_ref"]),
                base_sha=str(resource.details["base_sha"]),
                status=str(resource.details["status"]),
                resource=resource,
                worktree=None,
            )
        )
        if worktrees[-1].canonical_repo_path != repo.path:
            raise MegaplanChainLaunchError(
                "git_worktree_resource_conflict",
                f"existing git worktree resource does not match registered repo {repo_name!r}",
                diagnostics={
                    "phase": "retry",
                    "kind": "git_worktree_resource_conflict",
                    "repo_name": repo_name,
                },
            )
    return tuple(worktrees)


def _resolved_spec_from_metadata(metadata: Mapping[str, Any]) -> Path:
    value = metadata.get("resolved_spec_path") or metadata.get("spec_path")
    if not isinstance(value, str) or not value:
        raise MegaplanChainLaunchError(
            "missing_resolved_spec_path",
            "running megaplan_chain operation is missing resolved spec path metadata",
            diagnostics={"phase": "retry", "kind": "missing_resolved_spec_path"},
        )
    return Path(value)


def _project_root_from_metadata(metadata: Mapping[str, Any]) -> Path:
    value = metadata.get("project_root")
    if not isinstance(value, str) or not value:
        raise MegaplanChainLaunchError(
            "missing_project_root",
            "running megaplan_chain operation is missing project root metadata",
            diagnostics={"phase": "retry", "kind": "missing_project_root"},
        )
    return Path(value)


def _classification_metadata(metadata: Mapping[str, Any]) -> dict[str, Any] | None:
    value = metadata.get("chain_status")
    return dict(value) if isinstance(value, Mapping) else None


def _is_stale_runner_resume(snapshot: ChainStatusSnapshot) -> bool:
    classification = snapshot.classification
    return (
        classification.operation_state is OperationState.SUSPENDED
        and classification.effective_status == "stale_bookkeeping"
        and classification.reason
        in {
            "active_plan_without_live_runner",
            "running_operation_without_live_runner",
            "human_verification_satisfied_runner_inactive",
        }
        and snapshot.runner.get("status") in {"dead", "missing", "unknown", "unavailable"}
    )


def _stored_chain_command(metadata: Mapping[str, Any]) -> tuple[str, ...]:
    command = metadata.get("command")
    if isinstance(command, list) and all(isinstance(part, str) for part in command):
        if tuple(command[:4]) == ("python", "-m", "arnold_pipelines.megaplan", "chain"):
            return tuple(command)
    message = "megaplan_chain operation is missing a stored chain command"
    raise MegaplanChainLaunchError(
        "missing_stored_chain_command",
        message,
        diagnostics={"phase": "resume", "kind": "missing_stored_chain_command"},
    )


def _merge_run_metadata(paths: RunDirPaths, values: Mapping[str, Any]) -> None:
    current = read_metadata(paths)
    current.update(values)
    write_metadata(paths, current)


__all__ = [
    "MEGAPLAN_CHAIN_OPERATION_TYPE",
    "MegaplanChainHandler",
    "MegaplanChainLaunchError",
    "MegaplanChainLaunchResult",
    "get_agentbox_adapter",
]
