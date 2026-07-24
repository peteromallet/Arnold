"""Provider-independent Megaplan chain status snapshots."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from arnold.runtime.durable_ops import OperationRun, OperationState, ResourceType, TypedResource

from arnold_pipelines.megaplan._core import latest_plan_meta_path, load_plan_from_dir
from arnold_pipelines.megaplan.chain.spec import (
    ChainSpec,
    ChainState,
    effective_chain_policy,
    load_chain_state,
    load_runtime_policy,
    load_spec,
)
from arnold_pipelines.megaplan.handlers.verifiability import get_human_verification_status
from arnold_pipelines.megaplan.planning.state import (
    STATE_ABORTED,
    STATE_AWAITING_HUMAN_VERIFY,
    STATE_AWAITING_PR_MERGE,
    STATE_BLOCKED,
    STATE_CANCELLED,
    STATE_DONE,
    STATE_FAILED,
    STATE_PAUSED,
    TERMINAL_STATES,
)


@dataclass(frozen=True)
class ChainStatusClassification:
    """Deterministic mapping from gathered facts to an Arnold operation state."""

    operation_state: OperationState
    effective_status: str
    reason: str
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "operation_state": self.operation_state.value,
            "effective_status": self.effective_status,
            "reason": self.reason,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class ChainStatusSnapshot:
    """Read-only chain status facts plus the derived Arnold classification."""

    operation_id: str
    operation_type: str
    operation_state: OperationState
    launch_state: str | None
    spec_path: Path | None
    project_root: Path | None
    spec: dict[str, Any]
    policy: dict[str, Any]
    chain_state: dict[str, Any]
    summary: dict[str, Any]
    plan_status: dict[str, Any]
    plan_metadata: dict[str, Any]
    human_verification: dict[str, Any]
    runner: dict[str, Any]
    pr: dict[str, Any]
    sync: dict[str, Any]
    milestone_boundary_evidence: dict[str, Any]
    classification: ChainStatusClassification
    diagnostics: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "operation_id": self.operation_id,
            "operation_type": self.operation_type,
            "operation_state": self.operation_state.value,
            "launch_state": self.launch_state,
            "spec_path": str(self.spec_path) if self.spec_path is not None else None,
            "project_root": str(self.project_root) if self.project_root is not None else None,
            "spec": dict(self.spec),
            "policy": dict(self.policy),
            "chain_state": dict(self.chain_state),
            "summary": dict(self.summary),
            "plan_status": dict(self.plan_status),
            "plan_metadata": dict(self.plan_metadata),
            "human_verification": dict(self.human_verification),
            "runner": dict(self.runner),
            "pr": dict(self.pr),
            "sync": dict(self.sync),
            "milestone_boundary_evidence": dict(self.milestone_boundary_evidence),
            "classification": self.classification.to_dict(),
            "diagnostics": list(self.diagnostics),
        }


def build_chain_status_snapshot(
    operation: OperationRun,
    *,
    resources: Iterable[TypedResource] = (),
    inspect_runner: Any | None = None,
) -> ChainStatusSnapshot:
    """Gather local chain facts and classify them into an Arnold operation state."""

    diagnostics: list[dict[str, Any]] = []
    resource_tuple = tuple(resources)
    metadata = operation.metadata
    spec_path = _metadata_path(metadata, "resolved_spec_path") or _metadata_path(metadata, "spec_path")
    project_root = _metadata_path(metadata, "project_root") or _project_root_from_resources(resource_tuple)

    spec: ChainSpec | None = None
    chain_state: ChainState | None = None
    spec_facts: dict[str, Any] = {"status": "unavailable"}
    policy: dict[str, Any] = {"status": "unavailable"}
    summary: dict[str, Any] = {"status": "unavailable"}
    chain_state_facts: dict[str, Any] = {"status": "unavailable"}

    if spec_path is None:
        diagnostics.append(_diagnostic("spec", "missing", "operation metadata has no spec path"))
    else:
        try:
            spec = load_spec(spec_path)
            runtime_policy = load_runtime_policy(spec_path)
            policy = effective_chain_policy(spec, runtime_policy)
            spec_facts = {
                "status": "available",
                "milestone_count": len(spec.milestones),
                "seed_plan": spec.seed_plan,
                "base_branch": spec.base_branch,
                "runtime_overrides": runtime_policy,
            }
            chain_state = load_chain_state(spec_path)
            chain_state_facts = chain_state.to_dict()
            chain_state_facts["status"] = "available"
            summary = _format_chain_status(spec, chain_state)
        except Exception as exc:
            diagnostics.append(_diagnostic("chain", type(exc).__name__, str(exc)))

    plan_status, plan_metadata = _current_plan_facts(project_root, chain_state, diagnostics)
    human_verification = _human_verification_facts(project_root, chain_state, plan_status, plan_metadata)
    runner = _runner_facts(operation, resource_tuple, inspect_runner=inspect_runner)
    pr = _pr_facts(chain_state)
    sync = _sync_facts(chain_state)
    milestone_boundary_evidence = _milestone_boundary_evidence_facts(chain_state, summary)
    classification = classify_chain_status(
        operation_state=operation.state,
        launch_state=_string_or_none(metadata.get("launch_state")),
        spec=spec,
        chain_state=chain_state,
        plan_status=plan_status,
        human_verification=human_verification,
        runner=runner,
        policy=policy,
        sync=sync,
    )

    return ChainStatusSnapshot(
        operation_id=operation.id,
        operation_type=operation.operation_type,
        operation_state=operation.state,
        launch_state=_string_or_none(metadata.get("launch_state")),
        spec_path=spec_path,
        project_root=project_root,
        spec=spec_facts,
        policy=policy,
        chain_state=chain_state_facts,
        summary=summary,
        plan_status=plan_status,
        plan_metadata=plan_metadata,
        human_verification=human_verification,
        runner=runner,
        pr=pr,
        sync=sync,
        milestone_boundary_evidence=milestone_boundary_evidence,
        classification=classification,
        diagnostics=diagnostics,
    )


def classify_chain_status(
    *,
    operation_state: OperationState,
    launch_state: str | None,
    spec: ChainSpec | None,
    chain_state: ChainState | None,
    plan_status: Mapping[str, Any],
    human_verification: Mapping[str, Any],
    runner: Mapping[str, Any],
    policy: Mapping[str, Any],
    sync: Mapping[str, Any],
) -> ChainStatusClassification:
    """Classify gathered chain facts into a durable Arnold operation state."""

    base_metadata = {
        "source_operation_state": operation_state.value,
        "launch_state": launch_state,
        "runner_status": runner.get("status"),
        "plan_status": plan_status.get("status"),
        "sync_state": sync.get("sync_state"),
    }

    if chain_state is not None:
        from arnold_pipelines.megaplan.chain.operator_pause import is_paused

        if is_paused(chain_state):
            return _classification(
                OperationState.SUSPENDED,
                "paused",
                "operator_pause",
                base_metadata,
            )

    if spec is not None and chain_state is not None:
        current_index = chain_state.current_milestone_index
        milestone_count = len(spec.milestones)
        if (
            milestone_count > 0
            and current_index >= milestone_count
            and _chain_has_full_completed_set(spec, chain_state)
        ):
            return _classification(
                OperationState.SUCCEEDED,
                "complete",
                "all_milestones_completed",
                base_metadata,
            )

    if chain_state is not None and chain_state.last_state == STATE_AWAITING_PR_MERGE:
        return _classification(
            OperationState.AWAITING_APPROVAL,
            "awaiting_pr_merge",
            "chain_waiting_for_pr_merge",
            base_metadata,
        )

    state = _string_or_none(plan_status.get("status"))
    if state == STATE_AWAITING_HUMAN_VERIFY:
        if _human_verification_satisfied(human_verification):
            if _runner_alive(runner):
                return _classification(
                    OperationState.RUNNING,
                    "running",
                    "human_verification_satisfied_runner_alive",
                    base_metadata,
                )
            return _classification(
                OperationState.SUSPENDED,
                "stale_bookkeeping",
                "human_verification_satisfied_runner_inactive",
                base_metadata,
            )
        return _classification(
            OperationState.AWAITING_APPROVAL,
            "awaiting_human_verify",
            "latest_verdict_human_verification_pending",
            base_metadata,
        )

    if state in {STATE_FAILED, STATE_BLOCKED}:
        return _classification(OperationState.FAILED, state, f"plan_{state}", base_metadata)
    if state in {STATE_ABORTED, STATE_CANCELLED}:
        return _classification(OperationState.CANCELLED, state, f"plan_{state}", base_metadata)
    if state == STATE_PAUSED:
        return _classification(OperationState.SUSPENDED, "paused", "plan_paused", base_metadata)
    if state == STATE_AWAITING_PR_MERGE:
        return _classification(
            OperationState.AWAITING_APPROVAL,
            "awaiting_pr_merge",
            "plan_waiting_for_pr_merge",
            base_metadata,
        )

    if operation_state in {OperationState.SUCCEEDED, OperationState.FAILED, OperationState.CANCELLED}:
        return _classification(
            operation_state,
            operation_state.value,
            "terminal_operation_state",
            base_metadata,
        )

    if _runner_alive(runner):
        return _classification(OperationState.RUNNING, "running", "runner_alive", base_metadata)

    if state and state not in {"missing", "unavailable"} and state not in TERMINAL_STATES:
        return _classification(
            OperationState.SUSPENDED,
            "stale_bookkeeping",
            "active_plan_without_live_runner",
            base_metadata,
        )

    if launch_state == "failed_before_running":
        return _classification(
            OperationState.PENDING,
            "validation_failed_before_running",
            "pre_running_failure_retryable",
            base_metadata,
        )

    if policy.get("prerequisite_policy") == "required":
        return _classification(
            OperationState.AWAITING_APPROVAL,
            "human_prerequisite",
            "required_prerequisite_policy",
            base_metadata,
        )
    if policy.get("validation_policy") == "required":
        return _classification(
            OperationState.AWAITING_APPROVAL,
            "quality_gate",
            "required_validation_policy",
            base_metadata,
        )

    if operation_state is OperationState.RUNNING:
        return _classification(
            OperationState.SUSPENDED,
            "stale_bookkeeping",
            "running_operation_without_live_runner",
            base_metadata,
        )
    return _classification(operation_state, operation_state.value, "operation_state_fallback", base_metadata)


def _current_plan_facts(
    project_root: Path | None,
    chain_state: ChainState | None,
    diagnostics: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    plan_name = _active_current_plan_name(chain_state)
    if not plan_name:
        return {"status": "missing", "reason": "no current plan"}, {"status": "missing"}
    if project_root is None:
        return {"status": "unavailable", "reason": "missing project root", "plan": plan_name}, {"status": "unavailable"}

    plan_dir = project_root / ".megaplan" / "plans" / plan_name
    try:
        loaded_plan_dir, state = load_plan_from_dir(plan_dir)
        current_state = _string_or_none(state.get("current_state")) or "unknown"
        if _is_stale_completed_current_plan(chain_state, plan_name, state):
            return {"status": "missing", "reason": "no current plan"}, {"status": "missing"}
        try:
            meta_path = latest_plan_meta_path(loaded_plan_dir, state)
            meta = _read_json_object(meta_path)
            return (
                {"status": current_state, "plan": plan_name, "plan_dir": str(loaded_plan_dir)},
                {"status": "available", "path": str(meta_path), **meta},
            )
        except Exception as exc:
            diagnostics.append(_diagnostic("plan_metadata", type(exc).__name__, str(exc)))
            return (
                {"status": current_state, "plan": plan_name, "plan_dir": str(loaded_plan_dir)},
                {"status": "unavailable", "reason": str(exc)},
            )
    except Exception as exc:
        diagnostics.append(_diagnostic("plan_state", type(exc).__name__, str(exc)))
        return {"status": "unavailable", "reason": str(exc), "plan": plan_name}, {"status": "unavailable"}


def _is_stale_completed_current_plan(
    chain_state: ChainState | None,
    plan_name: str,
    plan_state: Mapping[str, Any],
) -> bool:
    if chain_state is None or chain_state.current_milestone_index < 0:
        return False
    milestone_label = _plan_milestone_label(plan_state)
    for index, completed in enumerate(chain_state.completed):
        if not isinstance(completed, Mapping):
            continue
        completed_plan = _string_or_none(completed.get("plan"))
        completed_label = _string_or_none(completed.get("label"))
        same_plan = completed_plan == plan_name
        same_milestone = milestone_label is not None and completed_label == milestone_label
        if not same_plan and not same_milestone:
            continue
        if chain_state.current_milestone_index >= index + 1:
            return True
    return False


def _plan_milestone_label(plan_state: Mapping[str, Any]) -> str | None:
    meta = plan_state.get("meta")
    if not isinstance(meta, Mapping):
        return None
    chain_policy = meta.get("chain_policy")
    if not isinstance(chain_policy, Mapping):
        return None
    return _string_or_none(chain_policy.get("milestone_label"))


def _active_current_plan_name(chain_state: ChainState | None) -> str | None:
    if chain_state is None or not chain_state.current_plan_name:
        return None
    for index, completed in enumerate(chain_state.completed):
        if not isinstance(completed, Mapping):
            continue
        if completed.get("plan") != chain_state.current_plan_name:
            continue
        if chain_state.current_milestone_index >= index + 1:
            return None
    return chain_state.current_plan_name


def _human_verification_facts(
    project_root: Path | None,
    chain_state: ChainState | None,
    plan_status: Mapping[str, Any],
    plan_metadata: Mapping[str, Any],
) -> dict[str, Any]:
    plan_name = chain_state.current_plan_name if chain_state is not None else None
    if not plan_name or project_root is None:
        return {"status": "missing", "reason": "no current plan"}
    if plan_status.get("status") != STATE_AWAITING_HUMAN_VERIFY:
        return {"status": "not_applicable", "semantics": "latest_verdict"}
    if plan_metadata.get("status") != "available":
        return {"status": "unavailable", "reason": "latest plan metadata unavailable"}
    try:
        plan_dir = project_root / ".megaplan" / "plans" / plan_name
        status = get_human_verification_status(plan_dir, dict(plan_metadata))
        return {"status": "available", **status}
    except Exception as exc:
        return {"status": "unavailable", "reason": str(exc)}


def _runner_facts(
    operation: OperationRun,
    resources: tuple[TypedResource, ...],
    *,
    inspect_runner: Any | None,
) -> dict[str, Any]:
    process_resources = tuple(
        resource for resource in resources if resource.resource_type is ResourceType.PROCESS_SESSION
    )
    session_name = _string_or_none(operation.metadata.get("session_name"))
    for resource in process_resources:
        session_name = session_name or _string_or_none(resource.details.get("session_name"))
    if not session_name:
        return {"status": "missing", "resource_count": len(process_resources)}
    if inspect_runner is None:
        return {"status": "unknown", "session_name": session_name, "resource_count": len(process_resources)}
    try:
        session_status = inspect_runner(session_name)
    except FileNotFoundError as exc:
        return {"status": "unavailable", "session_name": session_name, "reason": str(exc)}
    except Exception as exc:
        return {"status": "unknown", "session_name": session_name, "reason": str(exc)}
    exists = bool(getattr(session_status, "exists", False))
    state = _string_or_none(getattr(session_status, "state", None)) or "unknown"
    status = "alive" if exists and state == "running" else "dead"
    return {
        "status": status,
        "session_name": session_name,
        "session_state": state,
        "exists": exists,
        "resource_count": len(process_resources),
    }


def _pr_facts(chain_state: ChainState | None) -> dict[str, Any]:
    if chain_state is None or chain_state.pr_number is None:
        return {"status": "none"}
    return {
        "status": "available",
        "pr_number": chain_state.pr_number,
        "pr_state": chain_state.pr_state,
        "pr_head": chain_state.pr_head,
    }


def _sync_facts(chain_state: ChainState | None) -> dict[str, Any]:
    if chain_state is None:
        return {"status": "unavailable"}
    return {
        "status": "available",
        "branch_head": chain_state.branch_head,
        "pr_head": chain_state.pr_head,
        "last_pushed_commit": chain_state.last_pushed_commit,
        "dirty_flag": chain_state.dirty_flag,
        "sync_state": chain_state.sync_state,
        "extra_repo_sync": list(chain_state.extra_repo_sync),
    }


def _milestone_boundary_evidence_facts(
    chain_state: ChainState | None,
    summary: dict[str, Any],
) -> dict[str, Any]:
    """Extract read-only milestone boundary evidence refs from chain state.

    Evidence is drawn from chain state (producer authority) and presented
    as a read-only view.  The summary already carries a formatted variant;
    this helper lifts the raw contract-level refs for direct inspection.
    """
    if chain_state is None:
        return {"status": "unavailable"}
    raw = chain_state.milestone_boundary_evidence
    if not raw:
        return {"status": "empty"}
    compact: dict[str, Any] = {}
    for label, entry in raw.items():
        if not isinstance(entry, dict):
            continue
        compact[label] = {
            "milestone_label": entry.get("milestone_label"),
            "milestone_index": entry.get("milestone_index"),
            "plan_name": entry.get("plan_name"),
            "contract_id": entry.get("contract_id"),
            "contract_boundary_id": entry.get("contract_boundary_id"),
        }
    return {"status": "available", "entries": compact}


def _metadata_path(metadata: Mapping[str, Any], key: str) -> Path | None:
    value = metadata.get(key)
    if not isinstance(value, str) or not value:
        return None
    return Path(value).expanduser().resolve()


def _project_root_from_resources(resources: tuple[TypedResource, ...]) -> Path | None:
    for resource in resources:
        if resource.resource_type is ResourceType.GIT_WORKTREE:
            value = resource.details.get("worktree_path")
            if isinstance(value, str) and value:
                return Path(value).expanduser().resolve()
    return None


def _read_json_object(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return raw if isinstance(raw, dict) else {}


def _chain_has_full_completed_set(spec: ChainSpec, chain_state: ChainState) -> bool:
    completed_labels = {
        str(entry.get("label"))
        for entry in chain_state.completed
        if isinstance(entry, Mapping) and isinstance(entry.get("label"), str)
    }
    return all(milestone.label in completed_labels for milestone in spec.milestones)


def _format_chain_status(spec: ChainSpec, chain_state: ChainState) -> dict[str, Any]:
    from arnold_pipelines.megaplan import chain as chain_module

    return chain_module.format_chain_status(spec, chain_state)


def _human_verification_satisfied(human_verification: Mapping[str, Any]) -> bool:
    return (
        human_verification.get("status") == "available"
        and human_verification.get("semantics") == "latest_verdict"
        and human_verification.get("all_deferred_must_verified") is True
    )


def _runner_alive(runner: Mapping[str, Any]) -> bool:
    return runner.get("status") in {"alive", "connected"}


def _classification(
    state: OperationState,
    effective_status: str,
    reason: str,
    metadata: Mapping[str, Any],
) -> ChainStatusClassification:
    return ChainStatusClassification(
        operation_state=state,
        effective_status=effective_status,
        reason=reason,
        metadata=dict(metadata),
    )


def _diagnostic(source: str, kind: str, message: str) -> dict[str, Any]:
    return {"source": source, "kind": kind, "message": message}


def _string_or_none(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


__all__ = [
    "ChainStatusClassification",
    "ChainStatusSnapshot",
    "build_chain_status_snapshot",
    "classify_chain_status",
]
