from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from arnold.workflow.boundary_evidence import AuthorityRecord, BoundaryOutcome, BoundaryReceipt
import arnold_pipelines.megaplan.workers as worker_module
from arnold_pipelines.megaplan.fallback_chains import select_fallback_spec
from arnold_pipelines.megaplan.feature_flags import calibration_query_route_on
from arnold_pipelines.megaplan.receipts.writer import write_boundary_receipt
from arnold_pipelines.megaplan.store import write_plan_artifact_json
from arnold_pipelines.megaplan._core import (
    apply_session_update,
    append_history,
    atomic_write_json,
    atomic_write_text,
    batch_artifact_index,
    execute_batch_artifact_path,
    build_next_step_runtime,
    compute_batch_complexity,
    compute_global_batches,
    compute_task_batches,
    get_effective,
    is_prose_mode,
    list_batch_artifacts,
    load_config,
    make_history_entry,
    record_step_failure,
    read_json,
    render_final_md,
    save_state_merge_meta,
    set_active_step,
    sha256_file,
    split_oversized_batches,
    store_raw_worker_output,
)
from arnold_pipelines.megaplan.audits.quality_gates import capture_before_line_counts
from arnold_pipelines.megaplan.authority.batch_scope import (
    BATCH_SCOPE_KEY,
    DISPATCH_IDENTITY_KEY,
    RESULT_ENVELOPES_KEY,
    BatchScope,
    BatchScopeQuarantine,
)
from arnold_pipelines.megaplan.authority.binding import (
    DispatchIdentity,
    EvidenceEnvelope,
    ResultEnvelope,
    SENSE_CHECK_RESULT_CAPABILITY,
    SENSE_CHECK_ACK_CLAIM,
    SenseCheckAttempt,
    SenseCheckClaim,
    TASK_RESULT_CAPABILITY,
    TASK_COMPLETION_CLAIM,
    TaskAttempt,
    TaskClaim,
)
from arnold_pipelines.megaplan.observability.routing_ledger import (
    format_selected_spec,
    record_step_routing,
)
from arnold_pipelines.megaplan.execute.policy import (
    NextExecuteTransition,
    NextStepDecision,
    evaluate_blocker_recovery_policy,
    resolve_batch_tier,
    resolve_partial_failure_resume,
    resolve_single_batch_next_step,
)
from arnold_pipelines.megaplan.execute.aggregation import (
    _append_scope_drift_blocker,
    _build_aggregate_execution_payload,
    _compute_scope_drift_for_execute_surface,
    phase_quality_deviations_for_current_attempt,
    reconcile_finalized_review_scope_claims,
)
from arnold_pipelines.megaplan.execute.merge import (
    TERMINAL_TASK_STATUSES,
    _merge_batch_results,
    _merge_scoped_batch_artifact_through_validator,
)
from arnold_pipelines.megaplan.execute.wbc import (
    EXECUTE_PARENT_CUSTODY_KEY,
    EXECUTE_DISPATCH_WBC_KEY,
    EXECUTE_TRANSITION_WBC_KEY,
    build_execute_batch_dispatch_spec,
    build_transition_wbc_summary,
    dispatch_wbc_summary,
)
from arnold_pipelines.megaplan.execute.quality import (
    AttributionResult,
    _auto_attribute_unclaimed_paths,
    _capture_git_status_snapshot,
    _capture_git_status_snapshot_recursive,
    _check_done_task_evidence,
    _check_done_task_evidence_by_kind,
    _collect_quality_deviations,
    _is_harness_generated_path,
    _observe_git_changes,
    project_advisory_path_sets,
)
from arnold_pipelines.megaplan.execute.timeout import (
    _recover_execute_timeout,
    _resolve_execute_approval_mode,
)
from arnold_pipelines.megaplan.model_seam import (
    ModelTier,
    _normalize_execute_capture_payload as _normalize_execute_capture_payload_at_seam,
    capture_step_output,
    render_step_message,
)
from arnold_pipelines.megaplan.orchestration.execution_evidence import (
    apply_authoritative_execute_overrides,
    validate_execution_evidence,
)
from arnold_pipelines.megaplan.orchestration.phase_result import BlockedTask, Deviation
from arnold_pipelines.megaplan.orchestration.authority_readers import (
    effective_execute_completed_task_ids,
)
from arnold_pipelines.megaplan.orchestration.plan_contracts import (
    pre_existing_task_ids_from_contract,
)
from arnold_pipelines.megaplan.calibration import query_route_if_enabled
from arnold_pipelines.megaplan.blocker_recovery import build_prerequisite_scopes
from arnold_pipelines.megaplan.prompts import (
    _execute_batch_prompt,
    _write_execute_batch_template,
)
from arnold_pipelines.megaplan.receipts import build_receipt
from arnold_pipelines.megaplan.receipts.extractors import execute_metrics
from arnold_pipelines.megaplan.receipts.writer import write_receipt
from arnold_pipelines.megaplan.resolution_contract import (
    HARD_BLOCK,
    classify_resolution_behavior,
    resolution_applies_to_task,
    resolution_state,
)
from arnold_pipelines.megaplan.resolutions import effective_user_action_resolutions
from arnold_pipelines.megaplan.types import (
    CliError,
    MOCK_ENV_VAR,
    PlanState,
    StepResponse,
)
from arnold.execution.step_invocation import StepInvocation
from arnold_pipelines.run_authority import ContractError
from arnold_pipelines.megaplan.planning.state import (
    STATE_BLOCKED,
    STATE_EXECUTED,
    STATE_FINALIZED,
)
try:
    from arnold_pipelines.megaplan.bakeoff.channel_shadow import maybe_run_channel_shadow
except ImportError:  # pragma: no cover - exercised by import-isolation subprocess tests
    def maybe_run_channel_shadow(**_kwargs: Any) -> None:
        return None
from arnold_pipelines.megaplan.workers import WorkerResult
from arnold_pipelines.megaplan.workers.result_metadata import aggregate_rate_limits

log = logging.getLogger(__name__)

_UNROUTABLE_REWORK_ATTEMPTS_KEY = "unroutable_rework_attempts"
_MAX_UNROUTABLE_REWORK_RERUNS = 2
_ROUTABLE_REWORK_TARGET_KINDS = {"task", "bulk", "manifest"}
_MODEL_SEAM_PROVIDER_PREFIXES = frozenset(
    {
        "anthropic",
        "claude",
        "copilot",
        "copilot-acp",
        "deep-seek",
        "deepseek",
        "fireworks",
        "github",
        "github-copilot",
        "github-models",
        "glm",
        "google",
        "kimi",
        "kimi-coding",
        "minimax",
        "minimax-cn",
        "moonshot",
        "openai",
        "openai-codex",
        "openrouter",
        "z-ai",
        "z.ai",
        "zai",
        "zhipu",
    }
)


def _repair_missing_user_action_gate(
    finalize_data: dict[str, Any],
    plan_dir: Path,
    state: PlanState,
) -> bool:
    raw_actions = finalize_data.get("user_actions", [])
    tasks = finalize_data.get("tasks", [])
    if not isinstance(raw_actions, list) or not isinstance(tasks, list) or not tasks:
        return False
    if not any(
        isinstance(action, dict) and action.get("phase") == "before_execute"
        for action in raw_actions
    ):
        return False

    from arnold_pipelines.megaplan.blocker_recovery import (
        find_synthetic_before_execute_gate,
    )

    gate_task_id, _protected = find_synthetic_before_execute_gate(finalize_data)
    if gate_task_id is not None:
        return False

    from arnold_pipelines.megaplan.handlers.finalize import (
        _ensure_user_actions_pre_gate_task,
        _render_user_actions_md,
    )

    _ensure_user_actions_pre_gate_task(finalize_data, state)
    if find_synthetic_before_execute_gate(finalize_data)[0] is None:
        return False
    write_plan_artifact_json(
        plan_dir, "finalize.json", finalize_data, contract_context=None
    )
    atomic_write_text(plan_dir / "user_actions.md", _render_user_actions_md(finalize_data))
    atomic_write_text(plan_dir / "final.md", render_final_md(finalize_data, phase="execute"))
    return True


def _pre_existing_task_ids(plan_dir: Path) -> set[str]:
    """Read pre-existing task IDs persisted in ``contract.json``."""

    contract_path = plan_dir / "contract.json"
    if not contract_path.is_file():
        return set()
    try:
        return pre_existing_task_ids_from_contract(
            json.loads(contract_path.read_text(encoding="utf-8"))
        )
    except (OSError, ValueError):
        return set()


def _filter_harness_artifacts_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Remove harness metadata paths from file claims and evidence."""

    def _clean_path_list(values: Any) -> Any:
        if isinstance(values, dict):
            return values
        if not isinstance(values, list):
            return []
        return [
            str(path)
            for path in values
            if isinstance(path, str)
            and path.strip()
            and not _is_harness_generated_path(path)
        ]

    filtered = dict(payload)
    for key in ("files_changed", "evidence_files"):
        if key in filtered:
            filtered[key] = _clean_path_list(filtered[key])

    task_updates = filtered.get("task_updates")
    if isinstance(task_updates, list):
        cleaned_updates: list[dict[str, Any]] = []
        for item in task_updates:
            if not isinstance(item, dict):
                cleaned_updates.append(item)
                continue
            update = dict(item)
            for key in ("files_changed", "evidence_files"):
                if key in update:
                    update[key] = _clean_path_list(update[key])
            cleaned_updates.append(update)
        filtered["task_updates"] = cleaned_updates

    return filtered


def _scheduler_completed_ids_for_tasks(
    tasks: Iterable[dict[str, Any]],
    *,
    plan_dir: Path,
    root: Path | None = None,
    state: PlanState | None = None,
    decisions: dict[str, Any] | None = None,
) -> set[str]:
    config = state.get("config") if isinstance(state, dict) else None
    configured_project_dir = (
        config.get("project_dir") if isinstance(config, dict) else None
    )
    project_dir = (
        Path(configured_project_dir)
        if isinstance(configured_project_dir, str) and configured_project_dir
        else root
    )
    current_head = _best_effort_git_head(project_dir)
    return effective_execute_completed_task_ids(
        tasks,
        plan_dir=plan_dir,
        project_dir=project_dir,
        state=state,
        current_head=current_head,
        decisions=decisions,
    )
def _best_effort_git_head(root: Path | None) -> str | None:
    if root is None:
        return None
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    head = completed.stdout.strip()
    return head or None


def _stamp_head_sha_on_task_records(
    payload: dict[str, Any],
    finalize_data: dict[str, Any],
    root: Path | None,
) -> None:
    """Stamp current git HEAD onto task records so evidence refs stay fresh.

    The M2 authority reader treats evidence without a matching ``head_sha`` as
    stale. Execute workers do not know the project HEAD, so the batch runner
    must anchor completed task records to the HEAD at write time. This is a
    minimal, safe injection: it only adds ``head_sha`` when the record already
    carries task-output evidence (``files_changed`` or ``commands_run``) and
    does not already have a ``head_sha``/``head`` value.
    """

    head = _best_effort_git_head(root)
    if not head:
        return

    def _stamp(record: Any) -> None:
        if not isinstance(record, dict):
            return
        has_evidence = bool(record.get("files_changed") or record.get("commands_run"))
        has_head = bool(record.get("head_sha") or record.get("head"))
        if has_evidence and not has_head:
            record["head_sha"] = head

    for update in payload.get("task_updates") or []:
        _stamp(update)
    for task in finalize_data.get("tasks") or []:
        _stamp(task)


def _batch_task_signature(batch_task_ids: Iterable[str], batch_complexity: int) -> str:
    """Build the calibration task signature for a batch query."""
    ids = [task_id for task_id in batch_task_ids if isinstance(task_id, str) and task_id]
    return f"batch:max_complexity={batch_complexity}:task_ids={','.join(sorted(ids))}"


@dataclass(frozen=True)
class _TierResolution:
    """Resolved tier metadata from one route decision.

    Carries the selected spec along with observability tags that describe
    *how* the decision was reached (source, projected tier, exploration,
    confidence).  ``spec`` is ``None`` when no usable tier could be resolved.
    """

    spec: str | None
    source: str  # "toml" or "calibration_query"
    projected_tier: int | None
    counterfactual_tag: str | None
    low_confidence: bool


def _legacy_next_step_for_execute_policy(
    decision: NextStepDecision | NextExecuteTransition,
) -> str | None:
    """Translate typed execute policy transitions into legacy response fields."""
    transition = decision.transition if isinstance(decision, NextStepDecision) else decision
    if transition in (NextExecuteTransition.EXECUTE, NextExecuteTransition.BLOCKED):
        return "execute"
    if transition is NextExecuteTransition.REVIEW:
        return "review"
    if transition in (
        NextExecuteTransition.DONE,
        NextExecuteTransition.AWAITING_HUMAN,
    ):
        return None
    raise AssertionError(f"unhandled execute transition: {transition!r}")


def _calibration_tier_spec(
    *,
    plan_dir: Path,
    tier_map: dict[int, str],
    batch_task_ids: Iterable[str],
    batch_complexity: int,
) -> _TierResolution:
    """Return a validated calibration suggestion or fall back to TOML routing.

    The fallback behaviour routes through ``resolve_batch_tier`` when the flag
    is off, no suggestion exists, or the suggestion is malformed.

    Returns a :class:`_TierResolution` whose ``spec`` field is the selected
    tier spec string (or ``None`` when no spec could be resolved).
    """
    fallback_decision = resolve_batch_tier(
        tier_map=tier_map,
        batch_complexity=batch_complexity,
    )
    fallback_spec = fallback_decision.spec if fallback_decision.has_spec else None
    fallback_tier = fallback_decision.selected_tier
    if not calibration_query_route_on():
        return _TierResolution(
            spec=fallback_spec,
            source="toml",
            projected_tier=fallback_tier,
            counterfactual_tag=None,
            low_confidence=False,
        )
    suggestion = query_route_if_enabled(
        _batch_task_signature(batch_task_ids, batch_complexity),
        plan_dir=plan_dir,
        taint_class=None,
        exploration_budget=0.0,
        default_tier=batch_complexity,
        tier_models={"execute": {str(k): str(v) for k, v in tier_map.items()}},
    )
    if suggestion is None:
        return _TierResolution(
            spec=fallback_spec,
            source="toml",
            projected_tier=fallback_tier,
            counterfactual_tag=None,
            low_confidence=False,
        )
    suggested_spec = suggestion.tier_spec
    if (
        not isinstance(suggested_spec, str)
        or not suggested_spec.strip()
        or suggested_spec not in {str(spec) for spec in tier_map.values()}
    ):
        return _TierResolution(
            spec=fallback_spec,
            source="toml",
            projected_tier=fallback_tier,
            counterfactual_tag=None,
            low_confidence=False,
        )
    return _TierResolution(
        spec=suggested_spec,
        source="calibration_query",
        projected_tier=suggestion.projected_tier,
        counterfactual_tag=suggestion.counterfactual_tag,
        low_confidence=suggestion.low_confidence,
    )

def _resolve_tier_spec(
    args: argparse.Namespace,
    tier_spec: str | list[str],
    *,
    phase: str = "execute",
) -> tuple[str, str, str | None]:
    """Resolve a tier spec string to (agent, mode, model) without mutating *args*.

    Copies *args*, sets ``phase_model=["<phase>=<tier_spec>"]`` on the
    copy, and calls ``resolve_agent_mode``.  Does not prepend ahead of a
    user CLI override — the override guard in ``apply_profile_expansion``
    already strips ``tier_models.execute`` when ``--phase-model execute=…``
    is present, so this helper is only called when tier routing is active.
    """
    import copy

    selected_spec = (
        tier_spec
        if isinstance(tier_spec, str)
        else select_fallback_spec(tier_spec, 0, path=f"tier_models.{phase}")
    )
    tier_args = copy.copy(args)
    tier_args.phase_model = [f"{phase}={selected_spec}"]
    resolved = worker_module.resolve_agent_mode(phase, tier_args)
    resolved_model = resolved.resolved_model if hasattr(resolved, "resolved_model") else None
    return resolved.agent, resolved.mode, resolved_model if resolved_model is not None else resolved.model


def _task_to_global_batch_number_map(
    global_batches: list[list[str]],
) -> dict[str, int]:
    """Map each task ID to its 1-indexed global batch number."""

    mapping: dict[str, int] = {}
    for batch_number, batch in enumerate(global_batches, start=1):
        for task_id in batch:
            if isinstance(task_id, str) and task_id:
                mapping[task_id] = batch_number
    return mapping


def _resolve_batch_artifact_number(
    batch_task_ids: Iterable[str],
    *,
    global_batch_lookup: dict[tuple[str, ...], int],
    task_to_batch_number: dict[str, int],
    batch_index: int,
) -> int:
    """Choose the durable artifact slot for an auto-loop batch.

    Resumed execute runs often work on the unfinished subset of an original
    global batch. Exact tuple matching is too strict for that case because the
    remaining task list no longer equals the original batch tuple.
    """

    batch_tuple = tuple(batch_task_ids)
    exact = global_batch_lookup.get(batch_tuple)
    if exact is not None:
        return exact

    candidate_numbers = {
        task_to_batch_number[task_id]
        for task_id in batch_tuple
        if task_id in task_to_batch_number
    }
    if len(candidate_numbers) == 1:
        return next(iter(candidate_numbers))
    return batch_index


def _stamp_batch_scope(
    payload: dict[str, Any],
    *,
    batch_number: int,
    task_ids: Iterable[str],
    sense_check_ids: Iterable[str],
) -> BatchScope:
    """Attach canonical dispatch scope before a batch artifact is persisted."""

    scope = BatchScope.create(
        batch_number=batch_number,
        task_ids=task_ids,
        sense_check_ids=sense_check_ids,
    )
    payload[BATCH_SCOPE_KEY] = scope.to_dict()
    return scope


def _latest_run_revision(state: PlanState | None, plan_dir: Path | None = None) -> str:
    """Return the best stable plan revision available at dispatch time."""

    if isinstance(state, dict):
        versions = state.get("plan_versions")
        if isinstance(versions, list) and versions:
            latest = versions[-1]
            if isinstance(latest, dict):
                revision = latest.get("hash") or latest.get("file")
                if isinstance(revision, str) and revision.strip():
                    return revision
        meta = state.get("meta")
        if isinstance(meta, dict):
            invocation_id = meta.get("current_invocation_id")
            if isinstance(invocation_id, str) and invocation_id.strip():
                return invocation_id
        created_at = state.get("created_at")
        if isinstance(created_at, str) and created_at.strip():
            return created_at
    if plan_dir is not None:
        return plan_dir.name
    return "unknown-plan-revision"


def _coordinator_attempt_id(
    state: PlanState | None,
    *,
    run_id: str,
    batch_number: int,
    task_set_digest: str,
) -> str:
    active_step = state.get("active_step") if isinstance(state, dict) else None
    if isinstance(active_step, dict):
        active_run_id = active_step.get("run_id")
        if isinstance(active_run_id, str) and active_run_id.strip():
            return active_run_id
    return f"{run_id}:execute:batch:{batch_number}:{task_set_digest}"


def _fence_token(state: PlanState | None) -> int:
    active_step = state.get("active_step") if isinstance(state, dict) else None
    if isinstance(active_step, dict):
        attempt = active_step.get("attempt")
        if isinstance(attempt, int) and not isinstance(attempt, bool) and attempt >= 0:
            return attempt
    if isinstance(state, dict):
        iteration = state.get("iteration")
        if (
            isinstance(iteration, int)
            and not isinstance(iteration, bool)
            and iteration >= 0
        ):
            return iteration
    return 0


def _prerequisite_digest(
    *,
    scope: BatchScope,
    finalize_data: dict[str, Any] | None,
) -> str:
    """Hash dispatch prerequisite observations without expanding scope authority."""

    selected_task_ids = set(scope.task_ids)
    selected_sense_check_ids = set(scope.sense_check_ids)
    payload: dict[str, Any] = {
        "schema_version": 1,
        "batch_number": scope.batch_number,
        "task_ids": list(scope.task_ids),
        "sense_check_ids": list(scope.sense_check_ids),
    }
    if isinstance(finalize_data, dict):
        task_prerequisites: list[dict[str, Any]] = []
        for task in finalize_data.get("tasks", []) or []:
            if not isinstance(task, dict) or task.get("id") not in selected_task_ids:
                continue
            depends_on = task.get("depends_on", [])
            if not isinstance(depends_on, list):
                depends_on = []
            task_prerequisites.append(
                {
                    "task_id": task.get("id"),
                    "depends_on": sorted(
                        dep for dep in depends_on if isinstance(dep, str) and dep
                    ),
                }
            )
        payload["task_prerequisites"] = sorted(
            task_prerequisites, key=lambda item: str(item["task_id"])
        )

        check_bindings: list[dict[str, Any]] = []
        for check in finalize_data.get("sense_checks", []) or []:
            if (
                not isinstance(check, dict)
                or check.get("id") not in selected_sense_check_ids
            ):
                continue
            check_bindings.append(
                {
                    "sense_check_id": check.get("id"),
                    "task_id": check.get("task_id"),
                }
            )
        payload["sense_check_bindings"] = sorted(
            check_bindings, key=lambda item: str(item["sense_check_id"])
        )

        prerequisite_scopes = build_prerequisite_scopes(finalize_data)
        blocking_actions = [
            scope_record.to_dict()
            for scope_record in prerequisite_scopes.values()
            if selected_task_ids.intersection(scope_record.effective_task_ids)
        ]
        payload["blocking_actions"] = sorted(
            blocking_actions, key=lambda item: str(item["action_id"])
        )
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _dispatch_worker_id(scope: BatchScope) -> str:
    return f"megaplan-execute-batch-{scope.batch_number}-{scope.task_set_digest}"


def _build_dispatch_identity(
    *,
    plan_dir: Path | None,
    state: PlanState | None,
    scope: BatchScope,
    finalize_data: dict[str, Any] | None = None,
) -> DispatchIdentity:
    state_name = state.get("name") if isinstance(state, dict) else None
    run_id = str(
        state_name
        if isinstance(state_name, str) and state_name
        else plan_dir.name if plan_dir is not None else "unknown-run"
    )
    capabilities = [TASK_RESULT_CAPABILITY]
    if scope.sense_check_ids:
        capabilities.append(SENSE_CHECK_RESULT_CAPABILITY)
    return DispatchIdentity.create(
        dispatch_id=(
            f"{run_id}:execute:batch:{scope.batch_number}:{scope.task_set_digest}"
        ),
        run_id=run_id,
        run_revision=_latest_run_revision(state, plan_dir),
        coordinator_attempt_id=_coordinator_attempt_id(
            state,
            run_id=run_id,
            batch_number=scope.batch_number,
            task_set_digest=scope.task_set_digest,
        ),
        fence_token=_fence_token(state),
        subject_ids=(*scope.task_ids, *scope.sense_check_ids),
        capabilities=tuple(capabilities),
        prerequisite_digest=_prerequisite_digest(
            scope=scope,
            finalize_data=finalize_data,
        ),
        worker_id=_dispatch_worker_id(scope),
    )


def _stamp_dispatch_metadata(
    payload: dict[str, Any],
    *,
    plan_dir: Path | None,
    state: PlanState | None,
    scope: BatchScope,
    finalize_data: dict[str, Any] | None = None,
) -> DispatchIdentity:
    """Attach Sprint 2 dispatch metadata beside, not inside, batch scope."""

    identity = _build_dispatch_identity(
        plan_dir=plan_dir,
        state=state,
        scope=scope,
        finalize_data=finalize_data,
    )
    payload[DISPATCH_IDENTITY_KEY] = identity.to_dict()
    payload.setdefault(RESULT_ENVELOPES_KEY, [])
    return identity


def _jsonable_authority_payload(value: Any) -> Any:
    """Return a JSON contract-safe copy of model-provided result data."""

    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, dict):
        return {
            str(key): _jsonable_authority_payload(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
            if str(key) != "authority"
        }
    if isinstance(value, (list, tuple)):
        return [_jsonable_authority_payload(item) for item in value]
    return str(value)


def _result_authority_echo(envelope: ResultEnvelope) -> dict[str, Any]:
    """Compact worker-result echo for adapters that do not load full envelopes."""

    dispatch = envelope.dispatch
    return {
        "schema_version": 1,
        "envelope_digest": envelope.digest(),
        "dispatch_id": dispatch.dispatch_id,
        "run_revision": dispatch.run_revision,
        "plan_revision": dispatch.plan_revision,
        "fence": dispatch.fence.to_dict(),
        "scope": {
            "subject_ids": list(dispatch.subject_ids),
            "capabilities": list(dispatch.capabilities),
        },
        "prerequisite_digest": dispatch.prerequisite_digest,
        "worker_id": dispatch.worker_id,
        "attempt": envelope.attempt.to_dict(),
    }


def _task_result_envelope(
    *,
    identity: DispatchIdentity,
    entry: dict[str, Any],
    ordinal: int,
    source: str,
) -> ResultEnvelope | None:
    task_id = entry.get("task_id")
    if not isinstance(task_id, str) or not task_id.strip():
        return None
    base_id = f"{identity.dispatch_id}:task:{task_id}"
    evidence = EvidenceEnvelope(
        evidence_id=f"{base_id}:worker-result",
        run_id=identity.run_id,
        run_revision=identity.run_revision,
        evidence_type="megaplan.task_update",
        source=source,
        payload={
            "subject_id": task_id,
            "dispatch_id": identity.dispatch_id,
            "result": _jsonable_authority_payload(entry),
        },
    )
    attempt = TaskAttempt(
        attempt_id=f"{base_id}:attempt:{ordinal}",
        run_id=identity.run_id,
        run_revision=identity.run_revision,
        subject_id=task_id,
        grant_id=identity.dispatch_id,
        coordinator_attempt_id=identity.coordinator_attempt_id,
        fence_token=identity.fence_token,
        ordinal=ordinal,
    )
    claim = TaskClaim(
        claim_id=f"{base_id}:claim:{ordinal}",
        run_id=identity.run_id,
        run_revision=identity.run_revision,
        subject_id=task_id,
        attempt_id=attempt.attempt_id,
        grant_id=identity.dispatch_id,
        coordinator_attempt_id=identity.coordinator_attempt_id,
        fence_token=identity.fence_token,
        claim_type=TASK_COMPLETION_CLAIM,
        evidence_ids=(evidence.evidence_id,),
        idempotency_key=f"{base_id}:claim:{ordinal}",
        payload=_jsonable_authority_payload(entry),
    )
    return ResultEnvelope(
        dispatch=identity,
        attempt=attempt,
        claim=claim,
        evidence=(evidence,),
    )


def _sense_check_result_envelope(
    *,
    identity: DispatchIdentity,
    entry: dict[str, Any],
    ordinal: int,
    source: str,
) -> ResultEnvelope | None:
    sense_check_id = entry.get("sense_check_id")
    if not isinstance(sense_check_id, str) or not sense_check_id.strip():
        return None
    base_id = f"{identity.dispatch_id}:sense_check:{sense_check_id}"
    evidence = EvidenceEnvelope(
        evidence_id=f"{base_id}:worker-result",
        run_id=identity.run_id,
        run_revision=identity.run_revision,
        evidence_type="megaplan.sense_check_acknowledgment",
        source=source,
        payload={
            "subject_id": sense_check_id,
            "dispatch_id": identity.dispatch_id,
            "result": _jsonable_authority_payload(entry),
        },
    )
    attempt = SenseCheckAttempt(
        attempt_id=f"{base_id}:attempt:{ordinal}",
        run_id=identity.run_id,
        run_revision=identity.run_revision,
        subject_id=sense_check_id,
        grant_id=identity.dispatch_id,
        coordinator_attempt_id=identity.coordinator_attempt_id,
        fence_token=identity.fence_token,
        ordinal=ordinal,
    )
    claim = SenseCheckClaim(
        claim_id=f"{base_id}:claim:{ordinal}",
        run_id=identity.run_id,
        run_revision=identity.run_revision,
        subject_id=sense_check_id,
        attempt_id=attempt.attempt_id,
        grant_id=identity.dispatch_id,
        coordinator_attempt_id=identity.coordinator_attempt_id,
        fence_token=identity.fence_token,
        claim_type=SENSE_CHECK_ACK_CLAIM,
        evidence_ids=(evidence.evidence_id,),
        idempotency_key=f"{base_id}:claim:{ordinal}",
        payload=_jsonable_authority_payload(entry),
    )
    return ResultEnvelope(
        dispatch=identity,
        attempt=attempt,
        claim=claim,
        evidence=(evidence,),
    )


def _stamp_result_envelopes(
    payload: dict[str, Any],
    *,
    identity: DispatchIdentity,
    artifact_path: Path,
) -> tuple[ResultEnvelope, ...]:
    """Attach worker-result authority echoes built from persisted dispatch."""

    source = str(artifact_path)
    envelopes: list[ResultEnvelope] = []
    task_entries = payload.get("task_updates")
    if isinstance(task_entries, list):
        for index, entry in enumerate(task_entries, start=1):
            if not isinstance(entry, dict):
                continue
            try:
                envelope = _task_result_envelope(
                    identity=identity,
                    entry=entry,
                    ordinal=index,
                    source=source,
                )
            except ContractError as error:
                entry["authority_generation_error"] = str(error)
                continue
            if envelope is None:
                continue
            entry["authority"] = _result_authority_echo(envelope)
            envelopes.append(envelope)

    sense_check_entries = payload.get("sense_check_acknowledgments")
    if isinstance(sense_check_entries, list):
        for index, entry in enumerate(sense_check_entries, start=1):
            if not isinstance(entry, dict):
                continue
            try:
                envelope = _sense_check_result_envelope(
                    identity=identity,
                    entry=entry,
                    ordinal=index,
                    source=source,
                )
            except ContractError as error:
                entry["authority_generation_error"] = str(error)
                continue
            if envelope is None:
                continue
            entry["authority"] = _result_authority_echo(envelope)
            envelopes.append(envelope)

    payload[RESULT_ENVELOPES_KEY] = [envelope.to_dict() for envelope in envelopes]
    return tuple(envelopes)


def _prepare_scoped_batch_checkpoint(
    plan_dir: Path,
    *,
    batch_number: int,
    task_ids: list[str],
    sense_check_ids: list[str],
    state: PlanState | None = None,
    finalize_data: dict[str, Any] | None = None,
) -> Path:
    """Create the worker checkpoint with immutable scope before dispatch.

    Workers update checkpoints by reading and rewriting the whole document, so
    pre-creating the file also preserves scope across interruption before the
    harness receives the worker's final structured response.
    """

    artifact_path = execute_batch_artifact_path(plan_dir, batch_number, task_ids)
    payload: dict[str, Any] = {}
    if artifact_path.is_file():
        try:
            existing = read_json(artifact_path)
        except (OSError, UnicodeDecodeError, ValueError):
            existing = {}
        if isinstance(existing, dict):
            payload = dict(existing)
    scope = _stamp_batch_scope(
        payload,
        batch_number=batch_number,
        task_ids=task_ids,
        sense_check_ids=sense_check_ids,
    )
    identity = _stamp_dispatch_metadata(
        payload,
        plan_dir=plan_dir,
        state=state,
        scope=scope,
        finalize_data=finalize_data,
    )
    _stamp_result_envelopes(payload, identity=identity, artifact_path=artifact_path)
    atomic_write_json(artifact_path, payload)
    return artifact_path


def _all_batch_artifact_paths(plan_dir: Path) -> list[Path]:
    """Enumerate every S4 and legacy artifact, including same-index resumes."""

    candidates = {
        path
        for pattern in (
            "execute_batches/batch_*/tasks_*.json",
            "execution_batch_*.json",
        )
        for path in plan_dir.glob(pattern)
        if path.is_file()
    }
    return sorted(
        candidates,
        key=lambda path: (batch_artifact_index(path) or 0, str(path)),
    )


def _emit_batch_scope_quarantine(
    plan_dir: Path,
    quarantine: BatchScopeQuarantine,
) -> None:
    """Report scope refusal through the existing authority-divergence event."""

    from arnold_pipelines.megaplan.observability.events import EventKind, emit

    payload = {
        "diagnostic_version": 1,
        "authority_status": "quarantined",
        "authoritative": False,
        "reason": f"batch_scope_{quarantine.reason}",
        "artifact_path": quarantine.source_path,
        "quarantine": quarantine.to_dict(),
    }
    try:
        emit(
            EventKind.AUTHORITY_DIVERGENCE,
            plan_dir=plan_dir,
            phase="execute",
            payload=payload,
        )
    except Exception:
        log.warning(
            "failed to emit batch-scope quarantine for %s",
            quarantine.source_path,
            exc_info=True,
        )


def _replay_proven_batch_artifacts(
    *,
    plan_dir: Path,
    finalize_data: dict[str, Any],
    known_task_ids: Iterable[str],
    known_sense_check_ids: Iterable[str],
    mode: str,
    state: PlanState,
) -> list[dict[str, Any]]:
    """Replay each artifact against only its independently proven scope."""

    proven_payloads: list[dict[str, Any]] = []
    for artifact_path in _all_batch_artifact_paths(plan_dir):
        try:
            payload = read_json(artifact_path)
        except (OSError, UnicodeDecodeError, ValueError) as exc:
            quarantine = BatchScopeQuarantine(
                reason="unreadable_artifact",
                message=f"artifact could not be read as JSON: {exc}",
                source_path=str(artifact_path),
            )
            _emit_batch_scope_quarantine(plan_dir, quarantine)
            log.warning("skipping unreadable execution artifact %s", artifact_path)
            continue
        merge_result = _merge_scoped_batch_artifact_through_validator(
            plan_dir=plan_dir,
            artifact_path=artifact_path,
            payload=payload,
            finalize_data=finalize_data,
            known_task_ids=known_task_ids,
            known_sense_check_ids=known_sense_check_ids,
            mode=mode,
            state=state,
        )
        if merge_result.quarantine is not None:
            _emit_batch_scope_quarantine(plan_dir, merge_result.quarantine)
            log.warning(
                "skipping unproven execution artifact %s: %s",
                artifact_path,
                merge_result.quarantine.reason,
            )
            continue
        if merge_result.issues:
            log.debug(
                "resume-merge issues from %s: %s",
                artifact_path,
                list(merge_result.issues),
            )
        proven_payloads.append(merge_result.payload or payload)
    return proven_payloads


# Private marker set: dispatcher return paths stamp one of these four values.
# Handlers later read _phase_outcome to derive the correct ExitKind for
# phase_result.json emission.
_PHASE_OUTCOMES = frozenset(
    {"success", "blocked_by_quality", "blocked_by_prereq", "timeout"}
)


# ---------------------------------------------------------------------------
# Evidence-only batch boundary receipt emission
# ---------------------------------------------------------------------------


def _emit_batch_boundary_receipt(
    *,
    boundary_id: str,
    plan_dir: Path,
    state: dict[str, Any],
    outcome: BoundaryOutcome,
    artifact_refs: tuple[str, ...] = (),
    batch_number: int | None = None,
    batch_task_ids: list[str] | None = None,
    extra_details: dict[str, Any] | None = None,
    strict: bool = False,
) -> dict[str, Any] | None:
    """Emit an evidence-only batch boundary receipt without raising.

    Receipts are strictly observational — they do not affect branch
    decisions, batch routing, or state transitions.
    """
    try:
        from arnold_pipelines.megaplan.workflows.boundary_contracts import (
            BOUNDARY_CONTRACTS_BY_ID,
        )
        contract = BOUNDARY_CONTRACTS_BY_ID.get(boundary_id)
        if contract is None:
            if strict:
                raise CliError(
                    "missing_execute_boundary_contract",
                    f"missing execute boundary contract for {boundary_id!r}",
                )
            return None

        meta = state.get("meta") or {}
        invocation_id = meta.get("current_invocation_id")
        project_dir = Path(state["config"]["project_dir"])

        details: dict[str, Any] = {
            "current_state": state.get("current_state"),
            "iteration": state.get("iteration"),
        }
        if batch_number is not None:
            details["batch_index"] = batch_number
        if batch_task_ids:
            details["task_ids"] = list(batch_task_ids)
        if extra_details:
            details.update(extra_details)

        receipt = BoundaryReceipt(
            boundary_id=contract.boundary_id,
            workflow_id=contract.workflow_id,
            row_id=contract.row_id,
            invocation_id=invocation_id,
            artifact_refs=artifact_refs,
            state_observation={
                "current_phase": "execute",
                "current_state": state.get("current_state"),
                "iteration": state.get("iteration"),
                "batch_number": batch_number,
            },
            history_ref=contract.expected_history_entry,
            phase_result_ref="phase_result.json" if contract.phase_result_required else None,
            outcome=outcome,
            details=details,
        )
        write_boundary_receipt(plan_dir, receipt, project_dir=project_dir)
        if not strict:
            return None
        receipt_path = plan_dir / "boundary_receipts" / f"{contract.boundary_id}.json"
        if not receipt_path.is_file():
            raise CliError(
                "missing_execute_boundary_receipt",
                f"boundary receipt {contract.boundary_id!r} was not persisted",
                extra={"boundary_id": contract.boundary_id},
            )
        reread = read_json(receipt_path)
        if (
            not isinstance(reread, dict)
            or reread.get("boundary_id") != contract.boundary_id
            or reread.get("row_id") != contract.row_id
            or reread.get("history_ref") != contract.expected_history_entry
        ):
            raise CliError(
                "execute_boundary_receipt_reread_mismatch",
                f"boundary receipt reread mismatch for {contract.boundary_id!r}",
                extra={
                    "boundary_id": contract.boundary_id,
                    "receipt_path": str(receipt_path),
                },
            )
        return {
            "boundary_id": contract.boundary_id,
            "row_id": contract.row_id,
            "history_ref": contract.expected_history_entry,
            "receipt_path": str(receipt_path.relative_to(plan_dir)),
        }
    except Exception:
        if strict:
            raise
        log.warning(
            "Batch boundary receipt emission failed for %s", boundary_id, exc_info=True
        )
        return None


@dataclass
class BatchResult:
    worker: WorkerResult
    agent: str
    mode: str
    refreshed: bool
    payload: dict[str, Any]
    batch_number: int
    batch_task_ids: list[str]
    batch_sense_check_ids: list[str]
    merged_task_count: int
    total_task_count: int
    acknowledged_sense_check_count: int
    total_sense_check_count: int
    missing_task_evidence: list[str]
    execution_audit: dict[str, Any]
    finalize_hash: str
    attribution_records: list[dict[str, Any]] = field(default_factory=list)
    routing_degradations: list[str] = field(default_factory=list)


def normalize_tier_map(tier_map: dict[Any, Any] | None) -> dict[int, str] | None:
    if not isinstance(tier_map, dict) or not tier_map:
        return None
    normalized: dict[int, str] = {}
    for raw_key, raw_value in tier_map.items():
        try:
            key = int(raw_key)
        except (TypeError, ValueError):
            continue
        if isinstance(raw_value, str) and raw_value:
            normalized[key] = raw_value
            continue
        if isinstance(raw_value, list):
            normalized[key] = select_fallback_spec(raw_value, 0, path=f"tier_models.execute.{key}")
    return normalized or None


def _strip_provider_prefix(model: str | None) -> str | None:
    if not isinstance(model, str) or not model.strip():
        return None
    value = model.strip()
    provider, sep, bare = value.partition(":")
    known_prefixes = {
        "anthropic",
        "claude",
        "codex",
        "deepseek",
        "fireworks",
        "hermes",
        "local",
        "minimax",
        "nous",
        "openai",
        "openrouter",
        "zhipu",
    }
    if sep and provider.lower() in known_prefixes and bare:
        return bare
    return value


def _claude_tier(model: str | None) -> str | None:
    """Return the Claude tier name encoded in *model*, if any."""
    bare = _strip_provider_prefix(model)
    if not isinstance(bare, str):
        return None
    lowered = bare.lower()
    for tier in ("haiku", "sonnet", "opus"):
        if lowered == tier or f"-{tier}" in lowered or lowered.startswith(f"{tier}-"):
            return tier
    return None


def _models_match(selected: str | None, actual: str | None) -> bool:
    if not selected or not actual:
        return True
    if selected == actual or _strip_provider_prefix(selected) == _strip_provider_prefix(actual):
        return True
    selected_tier = _claude_tier(selected)
    actual_tier = _claude_tier(actual)
    if selected_tier is not None or actual_tier is not None:
        return selected_tier is not None and selected_tier == actual_tier
    selected_bare = _strip_provider_prefix(selected)
    actual_bare = _strip_provider_prefix(actual)
    return bool(
        isinstance(selected_bare, str)
        and isinstance(actual_bare, str)
        and selected_bare.lower().startswith("gpt-5")
        and actual_bare.lower().startswith("gpt-5")
    )


def _build_routing_record(
    *,
    batch_complexity: int | None,
    selected_tier: int | None,
    selected_spec: str | None,
    resolved_agent: str,
    resolved_mode: str,
    resolved_model: str | None,
    tier_map_configured: bool,
    tier_routing_active: bool,
) -> dict[str, Any]:
    return {
        "batch_complexity": batch_complexity,
        "selected_tier": selected_tier,
        "selected_spec": selected_spec,
        "resolved_agent": resolved_agent,
        "resolved_mode": resolved_mode,
        "resolved_model": resolved_model,
        "actual_agent": None,
        "actual_model": None,
        "tier_map_configured": tier_map_configured,
        "tier_routing_active": tier_routing_active,
        "warnings": [],
    }


def _finalize_routing_record(
    routing: dict[str, Any] | None,
    *,
    actual_agent: str,
    actual_model: str | None,
    plan_dir: Path,
    batch_number: int,
) -> list[str]:
    if routing is None:
        return []
    routing["actual_agent"] = actual_agent
    routing["actual_model"] = actual_model
    warnings = routing.setdefault("warnings", [])
    if routing.get("resolved_model") and not actual_model:
        warnings.append("actual_model_missing")

    degradations: list[str] = []
    if routing.get("tier_map_configured") and not routing.get("tier_routing_active"):
        degradations.append("tier map configured but tier routing was inactive")
    if routing.get("tier_map_configured") and routing.get("selected_spec") is None:
        degradations.append(
            f"tier map configured but no spec matched selected tier {routing.get('selected_tier')}"
        )
    if (
        routing.get("resolved_agent")
        and routing.get("actual_agent") != routing.get("resolved_agent")
        and os.getenv(MOCK_ENV_VAR) != "1"
    ):
        degradations.append(
            f"selected agent {routing.get('resolved_agent')} but worker returned {routing.get('actual_agent')}"
        )
    if not _models_match(routing.get("resolved_model"), actual_model):
        degradations.append(
            f"selected model {routing.get('resolved_model')} but provider reported {actual_model}"
        )
    if degradations:
        try:
            from arnold_pipelines.megaplan.observability.events import EventKind, emit

            emit(
                EventKind.ROUTING_DEGRADATION,
                plan_dir=plan_dir,
                phase="execute",
                payload={
                    "batch_number": batch_number,
                    "degradations": degradations,
                    "routing": dict(routing),
                },
            )
        except Exception:
            log.warning("Routing degradation event emission failed", exc_info=True)
    return [
        "Routing audit degradation: " + degradation
        for degradation in degradations
    ]


def _positive_int_or_default(value: Any, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _normalize_model_for_execute_seam(model: str | None) -> str | None:
    if model is None:
        return None
    normalized = model.strip()
    if not normalized:
        return None
    for separator in (":", "/"):
        if separator not in normalized:
            continue
        prefix, suffix = normalized.split(separator, 1)
        if prefix.strip().lower() in _MODEL_SEAM_PROVIDER_PREFIXES and suffix.strip():
            normalized = suffix.strip()
    return normalized


def _execute_model_metadata(
    *,
    agent: str,
    model: str | None,
    resolved_model: str | None,
) -> dict[str, Any]:
    selected_model = resolved_model if resolved_model is not None else model
    normalized_model = _normalize_model_for_execute_seam(selected_model)
    return {
        "tier": ModelTier.NON_ENFORCED.value,
        "worker": agent,
        "model": selected_model,
        "normalized_model": normalized_model,
        "validation_step": "execute",
        "compatibility_validation_step": "execute",
    }


def _render_execute_prompt_for_dispatch(
    *,
    agent: str,
    state: PlanState,
    plan_dir: Path,
    root: Path,
    model: str | None,
    resolved_model: str | None,
    prompt_override: str | None,
) -> str | None:
    if prompt_override is None:
        return None
    metadata = _execute_model_metadata(
        agent=agent,
        model=model,
        resolved_model=resolved_model,
    )
    rendered = render_step_message(
        StepInvocation(
            kind="model",
            metadata={
                **metadata,
                "prompt": prompt_override,
                "prompt_components": prompt_override,
            },
        )
    )
    return rendered.prompt


def _capture_execute_payload(
    *,
    agent: str,
    model: str | None,
    resolved_model: str | None,
    payload: dict[str, Any],
) -> dict[str, Any]:
    # Capture is a direct generic call; registry is render-side only.
    payload = _normalize_execute_capture_payload(payload)
    outcome = capture_step_output(
        StepInvocation(
            kind="model",
            metadata=_execute_model_metadata(
                agent=agent,
                model=model,
                resolved_model=resolved_model,
            ),
        ),
        payload,
    )
    return dict(outcome.legacy_payload)


def _normalize_execute_capture_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Use the shared execute seam, then apply batch-only path filtering."""

    return _filter_harness_artifacts_from_payload(
        _normalize_execute_capture_payload_at_seam(payload)
    )


def _default_max_tasks_per_batch() -> int:
    return _positive_int_or_default(
        get_effective("execution", "max_tasks_per_batch"),
        5,
    )


def _resolve_max_tasks_per_batch(state: PlanState, args: argparse.Namespace) -> int:
    default = _default_max_tasks_per_batch()
    cli_value = getattr(args, "max_tasks_per_batch", None)
    if cli_value is not None:
        return _positive_int_or_default(cli_value, default)
    state_value = state.get("config", {}).get("max_tasks_per_batch")
    return _positive_int_or_default(state_value, default)


def _single_batch_mode_allowed(
    *,
    all_task_ids: list[str],
    pending_task_count: int,
    pending_batch_count: int,
    completed_task_ids: set[str],
    max_tasks_per_batch: int,
) -> bool:
    """Allow the whole-plan fast path only for a clean first execution."""

    return (
        not completed_task_ids
        and pending_task_count == len(all_task_ids)
        and pending_batch_count <= 1
        and len(all_task_ids) <= max_tasks_per_batch
    )


def build_monitor_hint(plan_dir: Path) -> str:
    return f"Use `megaplan status --plan {plan_dir.name}` for updates."


def _attach_next_step_runtime(response: StepResponse) -> None:
    runtime = build_next_step_runtime(
        response.get("next_step"),
        configured_timeout_seconds=int(get_effective("execution", "worker_timeout_seconds")),
    )
    if runtime is not None:
        response["next_step_runtime"] = runtime


def _format_execute_tracking_note(
    *,
    merged_count: int,
    total_tasks: int,
    acknowledged_count: int,
    total_checks: int,
) -> str:
    tracking_bits: list[str] = []
    if total_tasks > 0:
        tracking_bits.append(f"{merged_count}/{total_tasks} tasks tracked")
    if total_checks > 0:
        tracking_bits.append(
            f"{acknowledged_count}/{total_checks} sense checks acknowledged"
        )
    return f" ({', '.join(tracking_bits)})" if tracking_bits else ""


def _active_sense_check_ids(
    finalize_data: dict[str, Any], active_task_ids: set[str]
) -> list[str]:
    return [
        sense_check["id"]
        for sense_check in finalize_data.get("sense_checks", [])
        if isinstance(sense_check, dict)
        and isinstance(sense_check.get("id"), str)
        and sense_check.get("task_id") in active_task_ids
    ]


def _count_execute_tracking(
    finalize_data: dict[str, Any],
    *,
    active_task_ids: set[str],
    active_sense_check_ids: set[str],
    completed_task_ids: set[str] | None = None,
) -> tuple[int, int, int, int]:
    tracked_tasks = sum(
        1
        for task in finalize_data.get("tasks", [])
        if task.get("id") in active_task_ids
        and (
            task.get("id") in completed_task_ids
            if completed_task_ids is not None
            else task.get("status") in TERMINAL_TASK_STATUSES
        )
    )
    acknowledged_checks = sum(
        1
        for sense_check in finalize_data.get("sense_checks", [])
        if sense_check.get("id") in active_sense_check_ids
        and str(sense_check.get("executor_note", "")).strip()
    )
    return (
        tracked_tasks,
        len(active_task_ids),
        acknowledged_checks,
        len(active_sense_check_ids),
    )


def _durably_evidenced_finalized_task_ids(
    tasks: Iterable[dict[str, Any]],
) -> set[str]:
    """Return terminal task IDs with output evidence for quality coverage.

    This deliberately does not relax scheduler authority: it only keeps a
    replayed or partial retry from erasing finalized task coverage.
    """
    completed: set[str] = set()
    for task in tasks:
        task_id = task.get("id")
        if not isinstance(task_id, str) or not task_id:
            continue
        status = task.get("status")
        if status == "done" and (task.get("files_changed") or task.get("commands_run")):
            completed.add(task_id)
            continue
        if status == "skipped":
            notes = task.get("executor_notes")
            if isinstance(notes, str) and notes.strip():
                completed.add(task_id)
    return completed


def build_blocking_reasons(
    *,
    tracked_tasks: int,
    total_tasks: int,
    acknowledged_checks: int,
    total_checks: int,
    missing_task_evidence: list[str],
    timeout_reason: str | None = None,
) -> list[str]:
    reasons: list[str] = []
    if tracked_tasks < total_tasks:
        reasons.append(
            f"{total_tasks - tracked_tasks}/{total_tasks} tasks have no executor update"
        )
    if acknowledged_checks < total_checks:
        reasons.append(
            f"{total_checks - acknowledged_checks}/{total_checks} sense checks have no executor acknowledgment"
        )
    if missing_task_evidence:
        reasons.append(
            "done tasks missing both files_changed and commands_run: "
            + ", ".join(missing_task_evidence)
        )
    if timeout_reason is not None:
        reasons.append(timeout_reason)
    return reasons


def _blocked_task_reason(task_ids: Iterable[str]) -> str | None:
    blocked_ids = sorted({task_id for task_id in task_ids if task_id})
    if not blocked_ids:
        return None
    return (
        "task(s) reported status=blocked by the worker: "
        f"{', '.join(blocked_ids)}. Resolve or replan the blocked task(s) "
        "before continuing."
    )


def _is_transient_execute_advisory(message: object) -> bool:
    """Return True for batch-local execute advisories that should not survive
    into the terminal aggregate payload.

    Per-batch payloads legitimately mention then-pending downstream tasks,
    partial sense-check coverage, and provisional git-diff observations. Once
    the aggregate execution audit recomputes final-state evidence, carrying
    those earlier advisories forward makes the terminal execute artifact look
    blocked for work that later completed.
    """

    if not isinstance(message, str):
        return False
    transient_prefixes = (
        "Advisory observation mismatch:",
        "Advisory audit finding:",
        "Advisory audit skip:",
        "Advisory carry-forward observation:",
    )
    if message.startswith(transient_prefixes):
        return True
    transient_fragments = (
        "tasks have no executor update",
        "sense checks have no executor acknowledgment",
        "Tasks left pending after execute",
    )
    return any(fragment in message for fragment in transient_fragments)


def _aggregate_terminal_deviations(
    aggregate_payload: dict[str, Any],
    *,
    timeout_recovery: dict[str, Any] | None,
    execution_audit: dict[str, Any],
    blocked_task_ids: set[str],
) -> list[str]:
    deviations: list[str] = []
    for deviation in aggregate_payload.get("deviations", []):
        if _is_transient_execute_advisory(deviation):
            continue
        if deviation not in deviations:
            deviations.append(deviation)
    if timeout_recovery is not None:
        deviations.extend(
            deviation
            for deviation in timeout_recovery.get("deviations", [])
            if deviation not in deviations
        )
    if execution_audit["skipped"]:
        deviations.append(f"Advisory audit skip: {execution_audit['reason']}")
    for finding in execution_audit["findings"]:
        deviations.append(f"Advisory audit finding: {finding}")
    if blocked_task_ids:
        deviations.append(
            f"Pre-existing blocked tasks treated as satisfied for scheduling: "
            f"{sorted(blocked_task_ids)}. Downstream tasks ran assuming the blocked "
            f"work is handled out-of-band; re-run those tasks once the blockage is resolved."
        )
    return deviations


def _is_harness_generated_block(task: dict[str, Any]) -> bool:
    if task.get("status") != "blocked":
        return False
    notes = task.get("executor_notes")
    return isinstance(notes, str) and "[harness]" in notes


def _prerequisite_blocked_task_ids(
    tasks: Iterable[dict[str, Any]],
    *,
    active_task_ids: set[str],
) -> set[str]:
    return {
        task["id"]
        for task in tasks
        if task.get("status") == "blocked"
        and not _is_harness_generated_block(task)
        and isinstance(task.get("id"), str)
        and task["id"] in active_task_ids
    }


def baseline_unavailable_checkpoint_ids(
    finalize_data: dict[str, Any],
    candidate_ids: Iterable[str],
) -> set[str]:
    """Return no-new-failures checkpoint ids that cannot be evaluated.

    A null ``baseline_test_failures`` means baseline capture failed or was
    skipped. In that case the harness cannot evaluate the synthetic "Introduce
    no new failures vs the recorded baseline" checkpoint, so it should not
    deadlock execution or chain completion by treating that checkpoint as a
    human-resolvable task block.
    """
    candidate_set = {task_id for task_id in candidate_ids if task_id}
    if not candidate_set or finalize_data.get("baseline_test_failures") is not None:
        return set()
    unavailable: set[str] = set()
    for task in finalize_data.get("tasks", []):
        if not isinstance(task, dict):
            continue
        task_id = task.get("id")
        if not isinstance(task_id, str) or task_id not in candidate_set:
            continue
        description = str(task.get("description") or "").casefold()
        if "no new failures" in description and "recorded baseline" in description:
            unavailable.add(task_id)
    return unavailable


def _has_code_task_advisory_evidence(task: dict[str, Any]) -> bool:
    return bool(task.get("commands_run"))


def _run_and_merge_batch(
    *,
    root: Path,
    plan_dir: Path,
    state: PlanState,
    args: argparse.Namespace,
    agent: str,
    mode: str,
    refreshed: bool,
    model: str | None = None,
    effort: str | None = None,
    resolved_model: str | None = None,
    prompt_override: str | None,
    batch_task_ids: list[str],
    batch_sense_check_ids: list[str],
    finalize_data: dict[str, Any],
    batch_number: int,
    batches_total: int,
    quality_config: dict[str, Any],
    routing_record: dict[str, Any] | None = None,
    capture_git_status_snapshot_fn: Callable[
        [Path], tuple[dict[str, str], str | None]
    ] = _capture_git_status_snapshot,
) -> BatchResult:
    project_dir = Path(state["config"]["project_dir"])
    plan_mode = state["config"].get("mode", "code")
    batch_artifact_path = execute_batch_artifact_path(
        plan_dir, batch_number, batch_task_ids
    )
    dispatch_scope = BatchScope.create(
        batch_number=batch_number,
        task_ids=batch_task_ids,
        sense_check_ids=batch_sense_check_ids,
    )
    dispatch_identity = _build_dispatch_identity(
        plan_dir=plan_dir,
        state=state,
        scope=dispatch_scope,
        finalize_data=finalize_data,
    )
    if is_prose_mode(state):
        before_snapshot: dict[str, str] = {}
        before_error: str | None = None
        before_line_counts: dict[str, int] = {}
    else:
        before_snapshot, before_error = capture_git_status_snapshot_fn(project_dir)
        before_line_counts = capture_before_line_counts(project_dir, before_snapshot.keys())
    # Pass a full AgentMode (with effort + resolved_model) rather than a bare
    # 4-tuple. The 4-tuple form drops both fields downstream, which causes
    # ``run_codex_step`` to be invoked with ``model=None`` / ``effort=None`` and
    # leads to the codex CLI hanging at startup. See diagnostic
    # /tmp/codex_wedge_diagnostic.md.
    from arnold_pipelines.megaplan.types import AgentMode as _AgentMode
    am_for_worker = _AgentMode(
        agent=agent,
        mode=mode,
        refreshed=refreshed,
        model=model,
        effort=effort,
        resolved_model=resolved_model if resolved_model is not None else model,
    )
    rendered_prompt_override = _render_execute_prompt_for_dispatch(
        agent=agent,
        state=state,
        plan_dir=plan_dir,
        root=root,
        model=model,
        resolved_model=resolved_model,
        prompt_override=prompt_override,
    )
    wbc_dispatch = build_execute_batch_dispatch_spec(
        plan_dir=plan_dir,
        state=state,
        dispatch_identity=dispatch_identity,
        batch_number=batch_number,
        batch_task_ids=batch_task_ids,
        batch_sense_check_ids=batch_sense_check_ids,
    )
    worker, agent, mode, refreshed = worker_module.run_step_with_worker(
        "execute",
        state,
        plan_dir,
        args,
        root=root,
        resolved=am_for_worker,
        prompt_override=rendered_prompt_override,
        wbc_dispatch=wbc_dispatch,
    )
    maybe_run_channel_shadow(
        root=root,
        plan_dir=plan_dir,
        state=state,
        args=args,
        step="execute",
        primary_worker=worker,
        primary_agent=agent,
        prompt_override=prompt_override,
        sample_key=f"{state.get('name') or plan_dir.name}:execute:{batch_number}",
        resolved=am_for_worker,
    )
    payload = _capture_execute_payload(
        agent=agent,
        model=model,
        resolved_model=resolved_model,
        payload=dict(worker.payload),
    )
    dispatch_summary = dispatch_wbc_summary(
        auth_metadata=worker.auth_metadata if isinstance(worker.auth_metadata, dict) else None,
        dispatch_identity=dispatch_identity,
        batch_number=batch_number,
    )
    if dispatch_summary is not None:
        payload[EXECUTE_DISPATCH_WBC_KEY] = dispatch_summary
    routing_degradations = _finalize_routing_record(
        routing_record,
        actual_agent=agent,
        actual_model=worker.model_actual,
        plan_dir=plan_dir,
        batch_number=batch_number,
    )
    if routing_record is not None:
        record_step_routing(
            plan_dir,
            phase="execute",
            step_label=f"batch_{batch_number}",
            agent=agent,
            selected_spec=routing_record.get("selected_spec")
            or format_selected_spec(agent, model, effort),
            resolved_model=routing_record.get("resolved_model"),
            actual_model=worker.model_actual,
            tier=routing_record.get("selected_tier"),
            complexity=routing_record.get("batch_complexity"),
            tier_routing_active=bool(routing_record.get("tier_routing_active")),
        )
    if routing_record is not None:
        payload["routing"] = routing_record
    deviations = list(payload.get("deviations", []))
    deviations.extend(routing_degradations)
    batch_task_id_set = set(batch_task_ids)
    # Resolve milestone evidence-window context (chain policy → base SHA and
    # carry-forward manifest) BEFORE the first use below. Quality-deviation,
    # unclaimed-path attribution, and git-observation all judge against this
    # window; computing it here keeps every consumer on the same base_ref.
    _chain_policy: dict[str, Any] = {}
    if state is not None:
        _cp = (state.get("meta") or {}).get("chain_policy")
        if isinstance(_cp, dict):
            _chain_policy = _cp
    _cf_manifest = _chain_policy.get("carry_forward_manifest")
    _carry_forward_paths: set[str] | None = None
    if isinstance(_cf_manifest, dict) and _cf_manifest:
        _carry_forward_paths = set(_cf_manifest.keys())
    elif isinstance(_cf_manifest, list) and _cf_manifest:
        _carry_forward_paths = {str(p) for p in _cf_manifest if isinstance(p, str)} or None
    _milestone_base_sha: str | None = _chain_policy.get("milestone_base_sha")
    if not is_prose_mode(state):
        deviations.extend(
            _collect_quality_deviations(
                project_dir=project_dir,
                before_snapshot=before_snapshot,
                before_line_counts=before_line_counts,
                quality_config=quality_config,
                capture_git_status_snapshot_fn=capture_git_status_snapshot_fn,
                base_ref=_milestone_base_sha,
                state=state,
            )
        )
    _stamp_head_sha_on_task_records(payload, finalize_data, project_dir)
    payload[BATCH_SCOPE_KEY] = dispatch_scope.to_dict()
    payload[DISPATCH_IDENTITY_KEY] = dispatch_identity.to_dict()
    payload.setdefault(RESULT_ENVELOPES_KEY, [])
    _stamp_result_envelopes(
        payload,
        identity=dispatch_identity,
        artifact_path=batch_artifact_path,
    )
    merged_count, total_batch_tasks, acknowledged_count, total_batch_checks = (
        _merge_batch_results(
            finalize_data=finalize_data,
            payload=payload,
            batch_task_ids=batch_task_ids,
            batch_sense_check_ids=batch_sense_check_ids,
            issues=deviations,
            mode=plan_mode,
            state=state,
            source_path=batch_artifact_path,
        )
    )
    attribution_result = AttributionResult(records=[], recursive_snapshot=None)
    if not is_prose_mode(state):
        attribution_result = _auto_attribute_unclaimed_paths(
            project_dir=project_dir,
            finalize_data=finalize_data,
            payload=payload,
            batch_task_ids=batch_task_ids,
            issues=deviations,
            capture_recursive_snapshot_fn=_capture_git_status_snapshot_recursive,
            carry_forward_paths=_carry_forward_paths,
            base_ref=_milestone_base_sha,
            state=state,
        )
        observation_snapshot_fn = capture_git_status_snapshot_fn
        if (
            attribution_result.records
            and attribution_result.recursive_snapshot is not None
        ):
            cached_snapshot = attribution_result.recursive_snapshot
            observation_snapshot_fn = lambda _p, _snap=cached_snapshot: (_snap, None)
        deviations.extend(
            _observe_git_changes(
                project_dir=project_dir,
                payload=payload,
                before_snapshot=before_snapshot,
                before_error=before_error,
                batch_number=batch_number,
                batches_total=batches_total,
                capture_git_status_snapshot_fn=observation_snapshot_fn,
                plan_dir=plan_dir,
                carry_forward_paths=_carry_forward_paths,
                base_ref=_milestone_base_sha,
                state=state,
            )
        )
    pre_existing_ids = _pre_existing_task_ids(plan_dir)
    if is_prose_mode(state):
        missing_task_evidence = _check_done_task_evidence(
            finalize_data.get("tasks", []),
            issues=deviations,
            should_classify=lambda task: task.get("id") in batch_task_id_set,
            has_evidence=lambda task: bool(task.get("sections_written")),
            has_advisory_evidence=lambda task: True,
            missing_message="Done tasks missing sections_written: ",
            advisory_message="",
            pre_existing=pre_existing_ids,
        )
    else:
        missing_task_evidence = _check_done_task_evidence_by_kind(
            finalize_data.get("tasks", []),
            issues=deviations,
            should_classify=lambda task: task.get("id") in batch_task_id_set,
            pre_existing=pre_existing_ids,
        )
    execution_audit = validate_execution_evidence(
        finalize_data,
        project_dir,
        mode=plan_mode,
        state=state,
        plan_dir=plan_dir,
        artifact_prefix=f"execution_audit_batch_{batch_number}",
        base_ref=_milestone_base_sha,
    )
    if attribution_result.records:
        execution_audit["auto_attribution"] = list(attribution_result.records)
    if execution_audit["skipped"]:
        deviations.append(f"Advisory audit skip: {execution_audit['reason']}")
    for finding in execution_audit["findings"]:
        deviations.append(f"Advisory audit finding: {finding}")
    payload["deviations"] = deviations
    if not is_prose_mode(state):
        project_advisory_path_sets(
            payload,
            plan_dir=plan_dir,
            artifact_prefix=f"execution_batch_{batch_number}",
            keys=("files_changed",),
        )
    atomic_write_json(batch_artifact_path, payload)
    atomic_write_json(plan_dir / "execution_audit.json", execution_audit)
    write_plan_artifact_json(plan_dir, "finalize.json", finalize_data, contract_context=None)
    atomic_write_text(
        plan_dir / "final.md", render_final_md(finalize_data, phase="execute")
    )
    return BatchResult(
        worker=worker,
        agent=agent,
        mode=mode,
        refreshed=refreshed,
        payload=payload,
        batch_number=batch_number,
        batch_task_ids=list(batch_task_ids),
        batch_sense_check_ids=list(batch_sense_check_ids),
        merged_task_count=merged_count,
        total_task_count=total_batch_tasks,
        acknowledged_sense_check_count=acknowledged_count,
        total_sense_check_count=total_batch_checks,
        missing_task_evidence=missing_task_evidence,
        execution_audit=execution_audit,
        finalize_hash=sha256_file(plan_dir / "finalize.json"),
        attribution_records=list(attribution_result.records),
        routing_degradations=routing_degradations,
    )


def _append_trace_output(plan_dir: Path, trace_output: str | None) -> bool:
    if trace_output is None:
        return False
    trace_path = plan_dir / "execution_trace.jsonl"
    existing_trace = (
        trace_path.read_text(encoding="utf-8") if trace_path.exists() else ""
    )
    atomic_write_text(trace_path, existing_trace + trace_output)
    return True


def handle_execute_one_batch(
    *,
    root: Path,
    plan_dir: Path,
    state: PlanState,
    args: argparse.Namespace,
    batch_number: int,
    auto_approve: bool,
    agent: str,
    mode: str,
    refreshed: bool,
    model: str | None = None,
    effort: str | None = None,
    resolved_model: str | None = None,
    tier_map: dict[int, str] | None = None,
) -> StepResponse:
    tier_map = normalize_tier_map(tier_map)
    finalize_data = read_json(plan_dir / "finalize.json")
    if _repair_missing_user_action_gate(finalize_data, plan_dir, state):
        log.info(
            "backfilled missing before_execute user-action gate for stale finalize payload"
        )
    global_config = load_config()
    quality_config = global_config.get("quality_checks", {})
    project_dir = Path(state["config"]["project_dir"])
    max_tasks_per_batch = _resolve_max_tasks_per_batch(state, args)
    global_batches = split_oversized_batches(
        compute_global_batches(finalize_data),
        max_tasks_per_batch,
    )
    batches_total = len(global_batches)

    if batch_number < 1 or batch_number > batches_total:
        raise CliError(
            "batch_out_of_range",
            f"--batch {batch_number} is out of range. Plan has {batches_total} batch(es) (1-indexed).",
        )

    tasks = finalize_data.get("tasks", [])
    finalize_data, resolved_prereq_reset_ids = _sync_resolved_prerequisite_blocked_tasks(
        finalize_data,
        plan_dir=plan_dir,
        state=state,
        log_label="resolved-prereq-retry(batch)",
    )
    if resolved_prereq_reset_ids:
        tasks = finalize_data.get("tasks", [])
    # In per-batch execute mode, finalize.json is only rewritten after the
    # final batch — between batches the per-task status overlay lives in
    # the S4 batch artifacts (execute_batches/batch_<n>/tasks_*.json; legacy
    # execution_batch_<n>.json still readable for migration). Apply that
    # overlay so prerequisite checks see the most recent on-disk truth.
    batch_status_overlay: dict[str, str] = {}
    for batch_path in list_batch_artifacts(plan_dir):
        prior_index = batch_artifact_index(batch_path)
        if prior_index is None:
            continue
        if prior_index >= batch_number:
            continue
        try:
            batch_data = read_json(batch_path)
        except (OSError, UnicodeDecodeError, ValueError) as exc:
            raise CliError(
                "corrupt_execution_batch",
                "M3B_HALT_CORRUPT_EXECUTION_BATCH: "
                f"failed to read prior execution batch artifact {batch_path}: {exc}",
                extra={"artifact_path": str(batch_path), "batch_number": batch_number},
            ) from exc
        for update in batch_data.get("task_updates", []) or []:
            if not isinstance(update, dict):
                continue
            tid = update.get("task_id")
            status = update.get("status")
            if isinstance(tid, str) and isinstance(status, str) and status:
                batch_status_overlay[tid] = status
    overlaid_tasks = []
    for task in tasks:
        if not isinstance(task, dict):
            continue
        task_id = task.get("id")
        if not isinstance(task_id, str):
            continue
        overlaid_task = dict(task)
        if task_id in batch_status_overlay:
            overlaid_task["status"] = batch_status_overlay[task_id]
        overlaid_tasks.append(overlaid_task)
    authority_decisions: dict[str, Any] = {}
    completed_ids = _scheduler_completed_ids_for_tasks(
        overlaid_tasks,
        plan_dir=plan_dir,
        root=root,
        state=state,
        decisions=authority_decisions,
    )
    for prior_idx in range(batch_number - 1):
        prior_batch = global_batches[prior_idx]
        missing = [task_id for task_id in prior_batch if task_id not in completed_ids]
        if missing:
            missing_decisions = {
                task_id: authority_decisions[task_id].diagnostics
                | {
                    "authority_status": authority_decisions[task_id].status.value,
                    "would_block_reasons": list(authority_decisions[task_id].would_block_reasons),
                    "missing_outputs": list(authority_decisions[task_id].missing_outputs),
                    "stale_evidence": list(authority_decisions[task_id].stale_evidence),
                }
                for task_id in missing
                if task_id in authority_decisions
            }
            raise CliError(
                "batch_prerequisites",
                f"Batch {batch_number} requires batches 1..{batch_number - 1} to be complete. "
                f"Batch {prior_idx + 1} has incomplete tasks: {', '.join(missing)}",
                extra={
                    "batch_number": batch_number,
                    "prior_batch_number": prior_idx + 1,
                    "missing_task_ids": missing,
                    "authority_decisions": missing_decisions,
                },
            )

    batch_task_ids = global_batches[batch_number - 1]
    active_task_ids = set(batch_task_ids)
    batch_sense_check_ids = _active_sense_check_ids(finalize_data, active_task_ids)
    _prepare_scoped_batch_checkpoint(
        plan_dir,
        batch_number=batch_number,
        task_ids=batch_task_ids,
        sense_check_ids=batch_sense_check_ids,
        state=state,
        finalize_data=finalize_data,
    )
    batch_template_path = _write_execute_batch_template(
        plan_dir,
        batch_number,
        batch_task_ids,
        batch_sense_check_ids,
    )
    batch_prompt = _execute_batch_prompt(
        state,
        plan_dir,
        batch_task_ids,
        completed_ids,
        root=root,
        batch_template_path=batch_template_path,
    )

    # Per-batch tier resolution: when tier_map is provided, select the model
    # for the maximum task complexity in this batch.
    fallback_agent, fallback_mode, fallback_refreshed, fallback_model = (
        agent, mode, refreshed, model
    )
    # Tier routing observability — populated only when tier_map is active.
    tier_routing_active = bool(tier_map)
    raw_batch_complexity: int | None = None
    tier_complexity: int | None = None
    tier_spec_raw: str | None = None
    tier_resolved_model: str | None = None
    # New T14 metadata fields.
    tier_routing_source: str | None = None
    tier_projected: int | None = None
    tier_counterfactual_tag: str | None = None
    tier_low_confidence: bool = False
    if tier_map:
        batch_complexity = compute_batch_complexity(finalize_data, batch_task_ids)
        raw_batch_complexity = batch_complexity
        tier_complexity = batch_complexity
        resolution = _calibration_tier_spec(
            plan_dir=plan_dir,
            tier_map=tier_map,
            batch_task_ids=batch_task_ids,
            batch_complexity=batch_complexity,
        )
        tier_routing_source = resolution.source
        tier_projected = resolution.projected_tier
        tier_counterfactual_tag = resolution.counterfactual_tag
        tier_low_confidence = resolution.low_confidence
        if resolution.spec:
            tier_spec_raw = resolution.spec
            tier_agent, tier_mode, tier_model = _resolve_tier_spec(
                args, resolution.spec
            )
            tier_resolved_model = tier_model
            agent, mode, model = tier_agent, tier_mode, tier_model
            # Force fresh session when the tier-selected model differs from
            # the fallback model.
            if tier_model != fallback_model:
                refreshed = True
            # Update active-step state to reflect the tier-selected model
            # while this batch runs. Persist immediately so the run_id on disk
            # matches the one the worker's liveness callback uses for
            # ``touch_active_step`` — otherwise the per-batch run_id would
            # diverge from the on-disk state and the liveness heartbeat would
            # silently no-op for every batch after the first.
            set_active_step(
                state, step="execute", agent=agent, mode=mode, model=model
            )
            save_state_merge_meta(plan_dir, state)
    selected_resolved_model = model if model is not None else resolved_model
    routing_record = _build_routing_record(
        batch_complexity=raw_batch_complexity,
        selected_tier=tier_complexity,
        selected_spec=tier_spec_raw,
        resolved_agent=agent,
        resolved_mode=mode,
        resolved_model=selected_resolved_model,
        tier_map_configured=bool(tier_map),
        tier_routing_active=tier_routing_active,
    )

    selected_resolved_model = model if model is not None else resolved_model
    routing_record = _build_routing_record(
        batch_complexity=raw_batch_complexity,
        selected_tier=tier_complexity,
        selected_spec=tier_spec_raw,
        resolved_agent=agent,
        resolved_mode=mode,
        resolved_model=selected_resolved_model,
        tier_map_configured=bool(tier_map),
        tier_routing_active=tier_routing_active,
    )

    try:
        result = _run_and_merge_batch(
            root=root,
            plan_dir=plan_dir,
            state=state,
            args=args,
            agent=agent,
            mode=mode,
            refreshed=refreshed,
            model=model,
            effort=effort,
            resolved_model=selected_resolved_model,
            prompt_override=batch_prompt,
            batch_task_ids=batch_task_ids,
            batch_sense_check_ids=batch_sense_check_ids,
            finalize_data=finalize_data,
            batch_number=batch_number,
            batches_total=batches_total,
            quality_config=quality_config,
            routing_record=routing_record,
            capture_git_status_snapshot_fn=_capture_git_status_snapshot,
        )
    except CliError as error:
        if error.code == "worker_timeout":
            timeout_resp = _recover_execute_timeout(
                plan_dir=plan_dir,
                state=state,
                error=error,
                agent=agent,
                mode=mode,
                refreshed=refreshed,
                model=resolved_model,
                auto_approve=auto_approve,
                args=args,
                batch_number=batch_number,
            )
            timeout_decision = resolve_single_batch_next_step(
                is_final_batch=False,
                all_tracked=False,
                blocked=False,
            )
            timeout_resp["next_step"] = _legacy_next_step_for_execute_policy(
                timeout_decision
            )
            timeout_resp["_phase_outcome"] = "timeout"
            return timeout_resp
        record_step_failure(
            plan_dir, state, step="execute", iteration=state["iteration"], error=error
        )
        raise

    apply_session_update(
        state,
        "execute",
        result.agent,
        result.worker.session_id,
        mode=result.mode,
        refreshed=result.refreshed,
        model=resolved_model,
        worker_channel=result.worker.worker_channel,
        auth_channel=result.worker.auth_channel,
        auth_metadata=result.worker.auth_metadata,
    )
    trace_written = _append_trace_output(plan_dir, result.worker.trace_output)
    blocking_reasons = build_blocking_reasons(
        tracked_tasks=result.merged_task_count,
        total_tasks=result.total_task_count,
        acknowledged_checks=result.acknowledged_sense_check_count,
        total_checks=result.total_sense_check_count,
        missing_task_evidence=result.missing_task_evidence,
    )

    all_tasks = finalize_data.get("tasks", [])
    is_final_batch = batch_number == batches_total
    tracked_tasks = [
        task for task in all_tasks if isinstance(task.get("id"), str)
    ]
    effective_completed_ids = _scheduler_completed_ids_for_tasks(
        tracked_tasks,
        plan_dir=plan_dir,
        root=root,
        state=state,
    )
    effective_completed_id_set = set(effective_completed_ids)
    batch_blocked_ids = [
        task.get("id")
        for task in tracked_tasks
        if task.get("id") in set(batch_task_ids)
        and task.get("status") == "blocked"
        and task.get("id") not in effective_completed_id_set
    ]
    blocked_task_reason = _blocked_task_reason(batch_blocked_ids)
    if blocked_task_reason:
        blocking_reasons.append(blocked_task_reason)
    if result.routing_degradations:
        blocking_reasons.extend(result.routing_degradations)
    all_tracked = all(task.get("id") in effective_completed_ids for task in tracked_tasks)
    any_done = any(task.get("id") in effective_completed_id_set for task in tracked_tasks)
    if all_tracked and tracked_tasks and not any_done:
        blocking_reasons.append(
            "All tasks were skipped with none completed — execution produced no work."
        )
        all_tracked = False

    aggregate_payload: dict[str, Any] | None = None
    batch_payloads: list[dict[str, Any]] = []
    drift = None
    if is_final_batch and all_tracked:
        deferred_checkpoint_ids, deferred_acks = _defer_baseline_unavailable_checkpoints(
            finalize_data
        )
        if deferred_checkpoint_ids:
            atomic_write_json(plan_dir / "finalize.json", finalize_data)
            log.info(
                "deferred baseline-unavailable verification checkpoint(s): %s",
                ", ".join(deferred_checkpoint_ids),
            )
        plan_mode = state["config"].get("mode", "code")
        batch_payloads = [read_json(path) for path in list_batch_artifacts(plan_dir)]
        aggregate_payload = _build_aggregate_execution_payload(
            batch_payloads,
            completed_batches=len(batch_payloads),
            total_batches=batches_total,
            mode=plan_mode,
            plan_dir=plan_dir,
            state=state,
        )
        parent_custody = aggregate_payload.get(EXECUTE_PARENT_CUSTODY_KEY)
        if isinstance(parent_custody, Mapping):
            blocking_reasons.extend(
                message
                for message in parent_custody.get("messages", [])
                if isinstance(message, str) and message not in blocking_reasons
            )
        if deferred_acks:
            aggregate_payload.setdefault("sense_check_acknowledgments", []).extend(
                deferred_acks
            )
        reconcile_finalized_review_scope_claims(
            finalize_data,
            plan_dir=plan_dir,
            project_dir=project_dir,
            state=state,
        )
        atomic_write_json(plan_dir / "finalize.json", finalize_data)
        # _run_and_merge_batch already wrote execution_audit.json; this handler
        # only writes the aggregate execution.json after the batch returns.
        write_plan_artifact_json(plan_dir, "execution.json", aggregate_payload, contract_context=None)
        drift = _compute_scope_drift_for_execute_surface(
            project_dir=project_dir,
            aggregate_payload=aggregate_payload,
            state=state,
            phase_context=f"final execute batch {batch_number}/{batches_total}",
            plan_dir=plan_dir,
        )
    if drift is not None:
        _append_scope_drift_blocker(blocking_reasons, state, drift)

    batch_artifact = execute_batch_artifact_path(
        plan_dir, batch_number, batch_task_ids
    )
    batches_remaining = batches_total - batch_number
    provisional_blocked = bool(blocking_reasons)
    provisional_artifacts = [
        str(batch_artifact.relative_to(plan_dir)),
        "execution_audit.json",
        "finalize.json",
        "final.md",
    ]
    if aggregate_payload is not None and not provisional_blocked:
        provisional_artifacts.insert(0, "execution.json")
    if trace_written:
        provisional_artifacts.append("execution_trace.jsonl")
    next_step_decision = resolve_single_batch_next_step(
        is_final_batch=is_final_batch,
        all_tracked=all_tracked,
        blocked=provisional_blocked,
    )
    transition_receipt: dict[str, Any] | None = None
    try:
        if next_step_decision.transition is NextExecuteTransition.BLOCKED:
            transition_receipt = _emit_batch_boundary_receipt(
                boundary_id="execute_partial_failure",
                plan_dir=plan_dir,
                state=state,
                outcome=BoundaryOutcome.PARTIAL,
                artifact_refs=tuple(provisional_artifacts),
                batch_number=batch_number,
                batch_task_ids=list(batch_task_ids),
                extra_details={
                    "blocking_reasons": list(blocking_reasons),
                    "routing_blocked": any(
                        reason in blocking_reasons
                        for reason in result.routing_degradations
                    ),
                    "batches_total": batches_total,
                },
                strict=True,
            )
        elif next_step_decision.transition is NextExecuteTransition.REVIEW:
            child_trace_refs: dict[str, Any] = {}
            if aggregate_payload is not None:
                task_updates = aggregate_payload.get("task_updates", [])
                if isinstance(task_updates, list):
                    child_trace_refs["task_count"] = len(task_updates)
                child_trace_refs["execution_json"] = "execution.json"
            transition_receipt = _emit_batch_boundary_receipt(
                boundary_id="execute_aggregate_promotion",
                plan_dir=plan_dir,
                state=state,
                outcome=BoundaryOutcome.COMPLETE,
                artifact_refs=tuple(provisional_artifacts),
                batch_number=batch_number,
                batch_task_ids=list(batch_task_ids),
                extra_details={
                    "reducer_promotion": True,
                    "child_trace_path": "execute/aggregate",
                    "child_trace_refs": child_trace_refs,
                    "batches_total": batches_total,
                },
                strict=True,
            )
        else:
            transition_receipt = _emit_batch_boundary_receipt(
                boundary_id="execute_batch_checkpoint",
                plan_dir=plan_dir,
                state=state,
                outcome=BoundaryOutcome.COMPLETE,
                artifact_refs=tuple(provisional_artifacts),
                batch_number=batch_number,
                batch_task_ids=list(batch_task_ids),
                extra_details={
                    "batches_remaining": batches_remaining,
                    "batches_total": batches_total,
                },
                strict=True,
            )
    except Exception as error:
        blocking_reasons.append(
            f"execute transition evidence failed closed: {type(error).__name__}: {error}"
        )

    routing_blocked = any(
        reason in blocking_reasons for reason in result.routing_degradations
    )
    blocked = bool(blocking_reasons)
    if routing_blocked:
        state["current_state"] = STATE_BLOCKED
        state["resume_cursor"] = {
            "phase": "execute",
            "batch_index": batch_number,
            "retry_strategy": "fresh_session",
            "reason": "routing_degradation",
        }
    elif is_final_batch and all_tracked and not blocked:
        state["current_state"] = STATE_EXECUTED

    user_approved_gate = bool(state["meta"].get("user_approved_gate", False))
    approval_mode = _resolve_execute_approval_mode(
        auto_approve=auto_approve,
        user_approved_gate=user_approved_gate,
    )
    result_value = (
        "blocked"
        if blocked
        else "success" if (is_final_batch and all_tracked) else "partial"
    )
    final_transition = resolve_single_batch_next_step(
        is_final_batch=is_final_batch,
        all_tracked=all_tracked,
        blocked=blocked,
    )
    dispatch_summary = result.payload.get(EXECUTE_DISPATCH_WBC_KEY)
    if transition_receipt is not None and isinstance(dispatch_summary, Mapping):
        transition_summary = build_transition_wbc_summary(
            dispatch_summary=dispatch_summary,
            boundary_id=str(transition_receipt["boundary_id"]),
            receipt_path=str(transition_receipt["receipt_path"]),
            transition=final_transition.transition.value,
            result_value=result_value,
            batch_number=batch_number,
            batches_total=batches_total,
        )
        result.payload[EXECUTE_TRANSITION_WBC_KEY] = transition_summary
        atomic_write_json(batch_artifact, result.payload)
        if aggregate_payload is not None:
            aggregate_payload[EXECUTE_TRANSITION_WBC_KEY] = transition_summary
            write_plan_artifact_json(
                plan_dir,
                "execution.json",
                aggregate_payload,
                contract_context=None,
            )

    append_history(
        state,
        make_history_entry(
            "execute",
            duration_ms=result.worker.duration_ms,
            cost_usd=result.worker.cost_usd,
            result=result_value,
            worker=result.worker,
            agent=result.agent,
            mode=result.mode,
            output_file=str(batch_artifact.relative_to(plan_dir)),
            artifact_hash=sha256_file(batch_artifact),
            finalize_hash=result.finalize_hash,
            approval_mode=approval_mode,
            batch_complexity=tier_complexity if tier_routing_active else None,
            tier_model_spec=tier_spec_raw if tier_routing_active else None,
            tier_model_resolved=tier_resolved_model if tier_routing_active else None,
            tier_routing_source=tier_routing_source if tier_routing_active else None,
            tier_projected=tier_projected if tier_routing_active else None,
            tier_counterfactual_tag=tier_counterfactual_tag if tier_routing_active else None,
            tier_low_confidence=tier_low_confidence if tier_routing_active else False,
        ),
    )
    if aggregate_payload is not None and drift is not None:
        receipt_worker = WorkerResult(
            payload=aggregate_payload,
            raw_output="",
            duration_ms=result.worker.duration_ms,
            cost_usd=result.worker.cost_usd,
            session_id=result.worker.session_id,
            trace_output=result.worker.trace_output,
            rendered_prompt=result.worker.rendered_prompt,
            model_actual=result.worker.model_actual,
            prompt_tokens=result.worker.prompt_tokens,
            completion_tokens=result.worker.completion_tokens,
            total_tokens=result.worker.total_tokens,
            rate_limit=result.worker.rate_limit,
            worker_channel=result.worker.worker_channel,
            auth_channel=result.worker.auth_channel,
            auth_metadata=result.worker.auth_metadata,
        )
        receipt_metrics = execute_metrics(aggregate_payload, drift)
        receipt_metrics["batches"] = batch_payloads
        receipt_worker.receipt_metrics = receipt_metrics
        try:
            artifact_hash = sha256_file(plan_dir / "execution.json")
            receipt = build_receipt(
                phase="execute",
                state=state,
                plan_dir=plan_dir,
                args=args,
                worker=receipt_worker,
                agent=result.agent,
                mode=result.mode,
                output_file="execution.json",
                artifact_hash=artifact_hash,
                verdict=result_value,
                drift=drift,
            )
            write_receipt(plan_dir, receipt, project_dir=project_dir)
        except Exception:
            log.warning("Execute receipt emission failed", exc_info=True)
    save_state_merge_meta(plan_dir, state)

    tracking_note = _format_execute_tracking_note(
        merged_count=result.merged_task_count,
        total_tasks=result.total_task_count,
        acknowledged_count=result.acknowledged_sense_check_count,
        total_checks=result.total_sense_check_count,
    )
    artifacts = [
        str(batch_artifact.relative_to(plan_dir)),
        "execution_audit.json",
        "finalize.json",
        "final.md",
    ]
    if aggregate_payload is not None and not blocked:
        artifacts.insert(0, "execution.json")
    if trace_written:
        artifacts.append("execution_trace.jsonl")

    next_step_decision = final_transition
    legacy_transition_target = _legacy_next_step_for_execute_policy(
        next_step_decision
    )

    if next_step_decision.transition is NextExecuteTransition.BLOCKED:
        summary = (
            "Blocked: "
            + "; ".join(blocking_reasons)
            + ". Re-run execute to complete tracking."
        )
        response_state = STATE_BLOCKED if routing_blocked else STATE_FINALIZED
    elif next_step_decision.transition is NextExecuteTransition.REVIEW:
        summary = result.payload.get("output", "Batch complete.") + tracking_note
        response_state = STATE_EXECUTED
    else:
        summary = (
            f"Batch {batch_number}/{batches_total} complete.{tracking_note} "
            f"{batches_remaining} batch(es) remaining."
        )
        response_state = STATE_FINALIZED
    if drift is not None and drift.severity != "none":
        summary = f"[scope_drift={drift.severity}] {summary}"

    warnings: list[str] = []
    if blocked:
        warnings.append(summary)
    if batch_blocked_ids:
        warnings.append(
            f"{len(batch_blocked_ids)} task(s) reported status=blocked by the worker "
            "— investigate executor_notes before continuing"
        )

    phase_outcome = "blocked_by_quality" if blocked else "success"
    response: StepResponse = {
        "success": not blocked,
        "step": "execute",
        "summary": summary,
        "artifacts": artifacts,
        "monitor_hint": build_monitor_hint(plan_dir),
        "next_step": legacy_transition_target,
        "state": response_state,
        "batch": batch_number,
        "batches_total": batches_total,
        "batches_remaining": batches_remaining,
        "files_changed": result.payload.get("files_changed", []),
        "deviations": result.payload.get("deviations", []),
        "warnings": warnings,
        "auto_approve": auto_approve,
        "user_approved_gate": user_approved_gate,
        "blocked_task_ids": batch_blocked_ids,
        "_phase_outcome": phase_outcome,
    }
    if routing_blocked:
        response["result"] = "blocked"
    # Tier routing observability — omitted for flat profiles.
    if tier_routing_active:
        response["batch_complexity"] = tier_complexity
        response["tier_model_spec"] = tier_spec_raw
        response["tier_agent"] = agent
        response["tier_mode"] = mode
        response["tier_model"] = model
        if tier_routing_source is not None:
            response["tier_routing_source"] = tier_routing_source
        if tier_projected is not None:
            response["tier_projected"] = tier_projected
        if tier_counterfactual_tag is not None:
            response["tier_counterfactual_tag"] = tier_counterfactual_tag
        response["tier_low_confidence"] = tier_low_confidence
    if (
        next_step_decision.transition is NextExecuteTransition.EXECUTE
        and not blocked
    ):
        response["guidance"] = f"Run --batch {batch_number + 1}"
    emitter = getattr(args, "progress_emitter", None)
    if emitter is not None:
        emitter.batch_complete(
            str(batch_number),
            summary=f"Batch {batch_number}/{batches_total} complete",
            batch_number=batch_number,
            batches_total=batches_total,
            task_ids=batch_task_ids,
            sense_check_ids=batch_sense_check_ids,
            merged_task_count=result.merged_task_count,
            total_task_count=result.total_task_count,
            blocked=blocked,
            state=response_state,
            batch_complexity=tier_complexity if tier_routing_active else None,
            tier_model_spec=tier_spec_raw if tier_routing_active else None,
            tier_model=tier_resolved_model if tier_routing_active else None,
        )
    _attach_next_step_runtime(response)

    return response


def _reset_blocked_tasks_to_pending(
    finalize_data: dict[str, Any],
    *,
    exclude_task_ids: Iterable[str] = (),
) -> list[str]:
    """Flip tasks at status="blocked" back to "pending" and clear per-attempt fields.

    Returns the sorted list of task IDs that were reset. The mutation is
    in-place on ``finalize_data``; the caller is responsible for atomic
    persistence.

    The fields cleared mirror the per-attempt fields written by the merge
    layer when a task reports back (executor_notes, files_changed, etc.) so
    the next execute attempt sees a clean slate and isn't biased by stale
    notes from the prior session.
    """
    excluded = {task_id for task_id in exclude_task_ids if task_id}
    reset_ids: list[str] = []
    for task in finalize_data.get("tasks", []):
        if not isinstance(task, dict):
            continue
        task_id = task.get("id")
        if not isinstance(task_id, str):
            continue
        if task_id in excluded:
            continue
        if task.get("status") != "blocked":
            continue
        _clear_task_attempt_fields(task)
        reset_ids.append(task_id)
    return sorted(reset_ids)


def _clear_task_attempt_fields(task: dict[str, Any]) -> None:
    task["status"] = "pending"
    task["executor_notes"] = ""
    task["files_changed"] = []
    task["commands_run"] = []
    task["evidence_files"] = []
    task["reviewer_verdict"] = ""
    task.pop("recorded_invocation_id", None)


def _task_blocking_action_ids(
    task: dict[str, Any],
    scopes: dict[str, Any],
) -> tuple[str, ...]:
    explicit = task.get("blocked_by_user_action_ids")
    if isinstance(explicit, list):
        action_ids = [
            action_id
            for action_id in explicit
            if isinstance(action_id, str) and action_id in scopes
        ]
        if action_ids:
            return tuple(action_ids)
    notes = task.get("executor_notes")
    if isinstance(notes, str) and notes.strip():
        noted_action_ids = [action_id for action_id in scopes if action_id in notes]
        if noted_action_ids:
            return tuple(noted_action_ids)
    task_id = task.get("id")
    if not isinstance(task_id, str):
        return ()
    return tuple(
        scope.action_id
        for scope in scopes.values()
        if task_id in scope.effective_task_ids
    )


def _reset_resolved_prerequisite_blocked_tasks(
    finalize_data: dict[str, Any],
    *,
    plan_dir: Path,
    state: PlanState,
) -> list[str]:
    """Clear stale prerequisite blocks once their user actions are resolved."""
    scopes = build_prerequisite_scopes(finalize_data)
    if not scopes:
        return []

    effective = effective_user_action_resolutions(plan_dir, state)
    if not effective:
        return []

    reset_ids: list[str] = []
    for task in finalize_data.get("tasks", []):
        if not isinstance(task, dict) or task.get("status") != "blocked":
            continue
        task_id = task.get("id")
        if not isinstance(task_id, str):
            continue
        matching_scopes = [
            scopes[action_id]
            for action_id in _task_blocking_action_ids(task, scopes)
            if action_id in scopes
        ]
        if not matching_scopes:
            continue
        can_retry = True
        for scope in matching_scopes:
            resolution_event = effective.get(scope.action_id)
            if resolution_event is None:
                can_retry = False
                break
            if not resolution_applies_to_task(
                resolution_event,
                task_id,
                source="memory",
            ):
                can_retry = False
                break
            resolution = resolution_state(resolution_event, source="memory")
            if classify_resolution_behavior(resolution) == HARD_BLOCK:
                can_retry = False
                break
        if not can_retry:
            continue
        _clear_task_attempt_fields(task)
        reset_ids.append(task_id)
    return sorted(reset_ids)


def _sync_resolved_prerequisite_blocked_tasks(
    finalize_data: dict[str, Any],
    *,
    plan_dir: Path,
    state: PlanState,
    log_label: str,
) -> tuple[dict[str, Any], list[str]]:
    """Reload finalize state from disk and clear stale resolved prereq blocks."""
    try:
        refreshed = read_json(plan_dir / "finalize.json")
    except (OSError, UnicodeDecodeError, ValueError):
        refreshed = finalize_data
    if isinstance(refreshed, dict):
        finalize_data = refreshed
    reset_ids = _reset_resolved_prerequisite_blocked_tasks(
        finalize_data,
        plan_dir=plan_dir,
        state=state,
    )
    if reset_ids:
        write_plan_artifact_json(
            plan_dir,
            "finalize.json",
            finalize_data,
            contract_context=None,
        )
        log.info(
            "%s: reset %d stale prerequisite-blocked task(s) to pending: %s",
            log_label,
            len(reset_ids),
            ", ".join(reset_ids),
        )
    return finalize_data, reset_ids


def _reset_stale_authority_done_tasks(
    finalize_data: dict[str, Any],
    *,
    plan_dir: Path,
    root: Path | None,
    state: PlanState,
) -> list[str]:
    """Demote terminal-success rows whose authority evidence went stale."""

    tasks = finalize_data.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        return []
    decisions: dict[str, Any] = {}
    completed_ids = _scheduler_completed_ids_for_tasks(
        [task for task in tasks if isinstance(task, dict)],
        plan_dir=plan_dir,
        root=root,
        state=state,
        decisions=decisions,
    )
    reset_ids: list[str] = []
    for task in tasks:
        if not isinstance(task, dict):
            continue
        task_id = task.get("id")
        raw_status = task.get("status")
        if not isinstance(task_id, str) or raw_status not in {"done", "completed"}:
            continue
        if task_id in completed_ids:
            continue
        decision = decisions.get(task_id)
        if decision is None:
            continue
        reasons = tuple(
            reason
            for reason in getattr(decision, "would_block_reasons", ())
            if isinstance(reason, str) and reason
        )
        if not reasons or any(not reason.startswith("stale_evidence:") for reason in reasons):
            continue
        _clear_task_attempt_fields(task)
        reset_ids.append(task_id)
    return sorted(reset_ids)


_BASELINE_VERIFICATION_MARKER = "introduce no new failures vs the recorded baseline"
_BASELINE_UNAVAILABLE_BLOCKER_KIND = "baseline-unavailable-no-new-failures-checkpoint"


def _is_baseline_dependent_verification_task(task: dict[str, Any]) -> bool:
    description = task.get("description")
    if not isinstance(description, str):
        return False
    return _BASELINE_VERIFICATION_MARKER in description.lower()


def _has_downstream_runnable_tasks(
    tasks: list[Any],
    *,
    checkpoint_index: int,
) -> bool:
    for later in tasks[checkpoint_index + 1 :]:
        if not isinstance(later, dict):
            continue
        if later.get("status") == "pending" and isinstance(later.get("id"), str):
            return True
    return False


def _task_dependencies_complete(tasks: list[Any], task: dict[str, Any]) -> bool:
    task_by_id = {
        candidate.get("id"): candidate
        for candidate in tasks
        if isinstance(candidate, dict) and isinstance(candidate.get("id"), str)
    }
    for dep_id in task.get("depends_on") or []:
        if not isinstance(dep_id, str):
            continue
        dependency = task_by_id.get(dep_id)
        if not isinstance(dependency, dict):
            return False
        if dependency.get("status") not in {"done", "skipped"}:
            return False
    return True


def baseline_unavailable_checkpoint_ids(
    finalize_data: dict[str, Any],
    task_ids: Iterable[str],
) -> set[str]:
    """Return no-new-failures checkpoint task IDs that cannot use a baseline."""
    if finalize_data.get("baseline_test_failures") is not None:
        return set()
    candidate_ids = {task_id for task_id in task_ids if task_id}
    if not candidate_ids:
        return set()
    tasks = finalize_data.get("tasks")
    if not isinstance(tasks, list):
        return set()

    blocked_ids: set[str] = set()
    for task in tasks:
        if not isinstance(task, dict):
            continue
        task_id = task.get("id")
        if not isinstance(task_id, str) or task_id not in candidate_ids:
            continue
        if _is_baseline_dependent_verification_task(task):
            blocked_ids.add(task_id)
    return blocked_ids


def baseline_unavailable_checkpoint_deviations(
    finalize_data: dict[str, Any],
    task_ids: Iterable[str],
) -> tuple[Deviation, ...]:
    deviations: list[Deviation] = []
    for task_id in sorted(baseline_unavailable_checkpoint_ids(finalize_data, task_ids)):
        deviations.append(
            Deviation(
                kind="quality_gate",
                task_id=task_id,
                blocker_id=f"quality:{task_id}:{_BASELINE_UNAVAILABLE_BLOCKER_KIND}",
                phase="execute",
                message=(
                    f"task {task_id} is a no-new-failures checkpoint, but "
                    "finalize.json has baseline_test_failures=null, so the "
                    "harness cannot distinguish pre-existing suite failures "
                    "from regressions for this checkpoint"
                ),
            )
        )
    return tuple(deviations)


def _deviation_messages(deviations: Iterable[Deviation]) -> list[str]:
    return [deviation.message for deviation in deviations]


def _deviation_dicts(deviations: Iterable[Deviation]) -> list[dict[str, Any]]:
    return [deviation.to_dict() for deviation in deviations]


def _defer_baseline_unavailable_checkpoints(
    finalize_data: dict[str, Any],
) -> tuple[list[str], list[dict[str, Any]]]:
    """Skip baseline-dependent checkpoints when no baseline exists.

    A task whose contract is "introduce no new failures vs the recorded
    baseline" is not actionable when baseline capture failed. Running it only
    produces an indeterminate block: there is no recorded baseline to compare
    against, and the harness-owned final verification/review remains the
    authoritative end-of-run signal. Mark all such checkpoints non-runnable so
    they cannot remain as permanently pending executable work.
    """
    if finalize_data.get("baseline_test_failures") is not None:
        return [], []
    tasks = finalize_data.get("tasks")
    if not isinstance(tasks, list):
        return [], []

    defer_note = (
        "Deferred by harness: baseline_test_failures is null, so this "
        "no-new-failures checkpoint cannot compare against a recorded "
        "baseline. The harness-owned final verification/review phase "
        "remains authoritative."
    )
    deferred_ids: list[str] = []
    acknowledgments: list[dict[str, Any]] = []
    sense_checks = finalize_data.get("sense_checks") or []
    if not isinstance(sense_checks, list):
        sense_checks = []

    for task in tasks:
        if not isinstance(task, dict):
            continue
        task_id = task.get("id")
        if not isinstance(task_id, str):
            continue
        if task.get("status") not in {"pending", "blocked"}:
            continue
        if not _task_dependencies_complete(tasks, task):
            continue
        if not _is_baseline_dependent_verification_task(task):
            continue

        prior_notes = str(task.get("executor_notes") or "").strip()
        task["status"] = "skipped"
        task["executor_notes"] = (
            f"{prior_notes}\n{defer_note}" if prior_notes else defer_note
        )
        task["files_changed"] = []
        task["commands_run"] = []
        task["evidence_files"] = []
        task["reviewer_verdict"] = "deferred_baseline_unavailable"
        task.pop("recorded_invocation_id", None)
        deferred_ids.append(task_id)

        matched = False
        for sense_check in sense_checks:
            if not isinstance(sense_check, dict):
                continue
            if sense_check.get("task_id") != task_id:
                continue
            sense_check["executor_note"] = defer_note
            sc_id = sense_check.get("id")
            if isinstance(sc_id, str) and sc_id:
                acknowledgments.append(
                    {"sense_check_id": sc_id, "executor_note": defer_note}
                )
                matched = True
        if not matched:
            acknowledgments.append(
                {
                    "sense_check_id": f"baseline-unavailable-{task_id}",
                    "executor_note": defer_note,
                }
            )
    return deferred_ids, acknowledgments


def _review_requests_rework(review_data: dict[str, Any]) -> bool:
    return (
        review_data.get("review_verdict") == "needs_rework"
        or bool(review_data.get("rework_items"))
    )


def _strings_from(value: Any) -> list[str]:
    if isinstance(value, str) and value:
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str) and item]
    return []


def _rework_item_target_task_ids(item: dict[str, Any]) -> tuple[list[str], str | None]:
    target = item.get("target")
    if isinstance(target, dict):
        raw_kind = target.get("kind") or target.get("type") or target.get("route")
        kind = str(raw_kind).strip().lower() if isinstance(raw_kind, str) else "task"
        target_id = target.get("id") or target.get("target_id")
        label = (
            f"{kind}:{target_id}"
            if isinstance(target_id, str) and target_id
            else kind
        )
        candidate_ids = []
        if kind == "task":
            candidate_ids.extend(_strings_from(target.get("task_id") or target.get("id")))
        candidate_ids.extend(_strings_from(target.get("task_ids")))
        candidate_ids.extend(_strings_from(target.get("concerned_task_ids")))
        if kind not in _ROUTABLE_REWORK_TARGET_KINDS:
            return [], label
        if candidate_ids:
            return candidate_ids, None
        return [], label

    target_kind = item.get("target_kind") or item.get("target_type") or item.get("route")
    if isinstance(target_kind, str) and target_kind:
        kind = target_kind.strip().lower()
        label_id = item.get("target_id") or item.get("artifact_ref") or item.get("flag_id")
        label = f"{kind}:{label_id}" if isinstance(label_id, str) and label_id else kind
        candidate_ids = []
        if kind == "task":
            candidate_ids.extend(_strings_from(item.get("target_id")))
        candidate_ids.extend(_strings_from(item.get("task_ids")))
        candidate_ids.extend(_strings_from(item.get("concerned_task_ids")))
        if kind not in _ROUTABLE_REWORK_TARGET_KINDS:
            return [], label
        if candidate_ids:
            return candidate_ids, None
        return [], label

    task_id = item.get("task_id")
    if not isinstance(task_id, str) or not task_id:
        return [], str(task_id or "<missing>")
    if task_id == "REVIEW":
        return [], "REVIEW"
    return [task_id], None


def _review_rework_task_ids(
    review_data: dict[str, Any],
    finalize_data: dict[str, Any],
) -> tuple[list[str], list[str]]:
    task_ids = {
        task["id"]
        for task in finalize_data.get("tasks", [])
        if isinstance(task, dict) and isinstance(task.get("id"), str)
    }
    runnable: list[str] = []
    unrunnable: list[str] = []
    seen: set[str] = set()
    for item in review_data.get("rework_items", []) or []:
        if not isinstance(item, dict):
            continue
        source = item.get("source")
        candidate_task_ids, unrunnable_label = _rework_item_target_task_ids(item)
        if source == "review_incomplete":
            unrunnable.append(unrunnable_label or ",".join(candidate_task_ids) or "<missing>")
            continue
        if unrunnable_label and not candidate_task_ids:
            unrunnable.append(unrunnable_label)
            continue
        for task_id in candidate_task_ids:
            if task_id not in task_ids:
                unrunnable.append(task_id)
                continue
            if task_id in seen:
                continue
            seen.add(task_id)
            runnable.append(task_id)
    return runnable, unrunnable


def _stable_string_list(values: Iterable[Any]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if not isinstance(value, str):
            continue
        stripped = value.strip()
        if not stripped or stripped in seen:
            continue
        seen.add(stripped)
        result.append(stripped)
    return result


def _milestone_changed_files(finalize_data: dict[str, Any]) -> list[str]:
    files: list[Any] = []
    for task in finalize_data.get("tasks", []) or []:
        if not isinstance(task, dict):
            continue
        for key in ("files_changed", "evidence_files"):
            values = task.get(key, [])
            if isinstance(values, list):
                files.extend(values)
    return _stable_string_list(files)


def _review_rework_context(
    review_data: dict[str, Any],
    finalize_data: dict[str, Any],
    batch_task_ids: list[str],
) -> dict[str, Any]:
    wanted = set(batch_task_ids)
    milestone_files = _milestone_changed_files(finalize_data)
    context_items: list[dict[str, Any]] = []
    scope_candidates: list[Any] = []
    for item in review_data.get("rework_items", []) or []:
        if not isinstance(item, dict) or item.get("task_id") not in wanted:
            continue
        evidence_file = item.get("evidence_file", "")
        normalized = {
            "task_id": item.get("task_id"),
            "issue": item.get("issue", ""),
            "expected": item.get("expected", ""),
            "actual": item.get("actual", ""),
            "evidence_file": evidence_file if isinstance(evidence_file, str) else "",
            "flag_id": item.get("flag_id"),
            "source": item.get("source"),
        }
        if normalized["evidence_file"]:
            scope_candidates.append(normalized["evidence_file"])
        else:
            scope_candidates.extend(milestone_files)
        context_items.append(normalized)
    return {
        "rework_items": context_items,
        "scope_files": _stable_string_list(scope_candidates) or milestone_files,
        "milestone_changed_files": milestone_files,
    }


def _block_no_runnable_rework(
    *,
    plan_dir: Path,
    state: PlanState,
    auto_approve: bool,
    reason: str,
    unrunnable_task_ids: list[str] | None = None,
) -> StepResponse:
    summary = f"Blocked: {reason}"
    blocked_decision = resolve_single_batch_next_step(
        is_final_batch=False,
        all_tracked=False,
        blocked=True,
    )
    append_history(
        state,
        make_history_entry(
            "execute",
            duration_ms=0,
            cost_usd=0.0,
            result="blocked",
            message=summary,
        ),
    )
    save_state_merge_meta(plan_dir, state)
    response: StepResponse = {
        "success": False,
        "step": "execute",
        "summary": summary,
        "artifacts": ["review.json", "finalize.json", "final.md"],
        "monitor_hint": build_monitor_hint(plan_dir),
        "next_step": _legacy_next_step_for_execute_policy(blocked_decision),
        "state": STATE_FINALIZED,
        "files_changed": [],
        "deviations": [summary],
        "warnings": [summary],
        "auto_approve": auto_approve,
        "user_approved_gate": bool(state["meta"].get("user_approved_gate", False)),
        "_phase_outcome": "blocked_by_quality",
    }
    if unrunnable_task_ids:
        response["unrunnable_rework_task_ids"] = sorted(set(unrunnable_task_ids))
    _attach_next_step_runtime(response)
    return response


def _handle_unroutable_review_rework(
    *,
    plan_dir: Path,
    state: PlanState,
    auto_approve: bool,
    unrunnable_task_ids: list[str],
) -> StepResponse:
    meta = state.setdefault("meta", {})
    prior_attempts = meta.get(_UNROUTABLE_REWORK_ATTEMPTS_KEY, 0)
    attempts = prior_attempts + 1 if isinstance(prior_attempts, int) else 1
    unmatched = ", ".join(sorted(set(unrunnable_task_ids))) or "<none>"
    reason = (
        "review requested rework but no runnable finalize task IDs could be derived. "
        f"Unmatched rework target(s): {unmatched}. "
        "Use typed rework targets that route to concrete finalize task IDs, "
        "or resolve the review blocker manually."
    )
    meta[_UNROUTABLE_REWORK_ATTEMPTS_KEY] = attempts

    from arnold_pipelines.megaplan.observability.events import EventKind, emit

    emit(
        EventKind.STATE_TRANSITION,
        plan_dir=plan_dir,
        phase="execute",
        payload={
            "reason": "unroutable_review_rework",
            "from": STATE_FINALIZED,
            "to": STATE_BLOCKED,
            "attempt": attempts,
            "unrunnable_rework_task_ids": sorted(set(unrunnable_task_ids)),
        },
    )
    response = _block_no_runnable_rework(
        plan_dir=plan_dir,
        state=state,
        auto_approve=auto_approve,
        reason=reason,
        unrunnable_task_ids=unrunnable_task_ids,
    )
    response["result"] = "blocked"
    return response


def _escalate_persistent_unroutable_rework(
    *,
    plan_dir: Path,
    state: PlanState,
    auto_approve: bool,
    unrunnable_task_ids: list[str],
    runnable_task_ids: list[str],
) -> StepResponse:
    """Escalate when mixed unroutable review rework persists past the cap."""
    unmatched = ", ".join(sorted(set(unrunnable_task_ids)))
    runnable = ", ".join(sorted(set(runnable_task_ids)))
    from arnold_pipelines.megaplan.observability.events import EventKind, emit

    emit(
        EventKind.STATE_TRANSITION,
        plan_dir=plan_dir,
        phase="execute",
        payload={
            "reason": "unroutable_review_rework_mixed",
            "from": STATE_FINALIZED,
            "to": STATE_BLOCKED,
            "max_attempts": _MAX_UNROUTABLE_REWORK_RERUNS,
            "unrunnable_rework_task_ids": sorted(set(unrunnable_task_ids)),
            "runnable_rework_task_ids": sorted(set(runnable_task_ids)),
        },
    )
    response = _block_no_runnable_rework(
        plan_dir=plan_dir,
        state=state,
        auto_approve=auto_approve,
        reason=(
            "review rework includes unroutable item(s) that re-running execute "
            f"cannot resolve. Unmatched rework task_id(s): {unmatched}. "
            f"Runnable rework task_id(s): {runnable or 'none'}. "
            f"Unroutable re-run attempts exhausted ({_MAX_UNROUTABLE_REWORK_RERUNS}/"
            f"{_MAX_UNROUTABLE_REWORK_RERUNS}); re-run review so rework_items "
            "reference concrete finalize task IDs, or recover-blocked after "
            "operator review."
        ),
        unrunnable_task_ids=unrunnable_task_ids,
    )
    response["result"] = "blocked"
    return response


def _escalate_persistent_unroutable_rework(
    *,
    plan_dir: Path,
    state: PlanState,
    auto_approve: bool,
    unrunnable_task_ids: list[str],
    runnable_task_ids: list[str],
) -> StepResponse:
    """Escalate to recoverable-blocked when unroutable rework persists past the cap.

    Used for the MIXED case (some runnable rework task IDs PLUS unroutable
    ``REVIEW``-style items). The unroutable subset cannot be removed by re-running
    execute on the runnable tasks, so without this the same unfixable findings
    recur forever. Reuses the same recoverable-blocked surface as
    ``_handle_unroutable_review_rework`` (clearable via ``override
    recover-blocked``/``force-proceed`` after operator review).
    """
    unmatched = ", ".join(sorted(set(unrunnable_task_ids)))
    runnable = ", ".join(sorted(set(runnable_task_ids)))
    from arnold_pipelines.megaplan.observability.events import EventKind, emit

    emit(
        EventKind.STATE_TRANSITION,
        plan_dir=plan_dir,
        phase="execute",
        payload={
            "reason": "unroutable_review_rework_mixed",
            "from": STATE_FINALIZED,
            "to": STATE_BLOCKED,
            "max_attempts": _MAX_UNROUTABLE_REWORK_RERUNS,
            "unrunnable_rework_task_ids": sorted(set(unrunnable_task_ids)),
            "runnable_rework_task_ids": sorted(set(runnable_task_ids)),
        },
    )
    response = _block_no_runnable_rework(
        plan_dir=plan_dir,
        state=state,
        auto_approve=auto_approve,
        reason=(
            "review rework includes unroutable item(s) that re-running execute "
            f"cannot resolve. Unmatched rework task_id(s): {unmatched}. "
            f"Runnable rework task_id(s): {runnable or 'none'}. "
            f"Unroutable re-run attempts exhausted ({_MAX_UNROUTABLE_REWORK_RERUNS}/"
            f"{_MAX_UNROUTABLE_REWORK_RERUNS}); re-run review so rework_items "
            "reference concrete finalize task IDs, or recover-blocked after "
            "operator review."
        ),
        unrunnable_task_ids=unrunnable_task_ids,
    )
    response["result"] = "blocked"
    return response


def handle_execute_auto_loop(
    *,
    root: Path,
    plan_dir: Path,
    state: PlanState,
    args: argparse.Namespace,
    auto_approve: bool,
    agent: str,
    mode: str,
    refreshed: bool,
    model: str | None = None,
    effort: str | None = None,
    resolved_model: str | None = None,
    tier_map: dict[int, str] | None = None,
) -> StepResponse:
    tier_map = normalize_tier_map(tier_map)
    finalize_data = read_json(plan_dir / "finalize.json")
    if _repair_missing_user_action_gate(finalize_data, plan_dir, state):
        log.info(
            "backfilled missing before_execute user-action gate for stale finalize payload"
        )
    global_config = load_config()
    quality_config = global_config.get("quality_checks", {})
    project_dir = Path(state["config"]["project_dir"])
    tasks = finalize_data.get("tasks", [])
    baseline_unavailable_acks: list[dict[str, Any]] = []

    # Cross-session blocked-task reset: when the caller (typically `megaplan auto`)
    # opts in via --retry-blocked-tasks, any task persisted at status="blocked"
    # from a prior run is flipped back to "pending" so the executor LLM gets a
    # fresh attempt. The auto-driver always passes this flag because each fresh
    # `megaplan auto` invocation is the user's signal that whatever external
    # prereq was missing has been resolved. Within-session retries don't reach
    # this code path with blocked tasks — eb4ac447 routes task-level
    # status=blocked to awaiting_human, which terminates the auto loop.
    if getattr(args, "retry_blocked_tasks", False):
        blocked_before_retry = [
            task["id"]
            for task in tasks
            if isinstance(task, dict)
            and task.get("status") == "blocked"
            and isinstance(task.get("id"), str)
        ]
        baseline_unavailable_ids = baseline_unavailable_checkpoint_ids(
            finalize_data,
            blocked_before_retry,
        )
        authority_completed_before_retry = _scheduler_completed_ids_for_tasks(
            tasks,
            plan_dir=plan_dir,
            root=root,
            state=state,
        )
        # ------------------------------------------------------------------
        # Explicit partial-failure resume partition (T12).
        #
        # ``resolve_partial_failure_resume`` is the *source-visible* policy
        # authority that decides which task IDs rerun (failed / blocked) versus
        # which are preserved (done / skipped) with their artifacts, debt
        # records, checkpoint artifacts, and receipt evidence intact.  The
        # dispatcher only flips the rerun set back to pending; it must never
        # touch preserved task records.
        # ------------------------------------------------------------------
        resume_decision = resolve_partial_failure_resume(
            tasks,
            preserved_artifact_refs=(
                str(plan_dir / "execute_batches"),
                str(plan_dir / "finalize.json"),
            ),
            preserved_receipt_ids=(
                "execute_partial_failure",
                "execute_resume_anchor",
            ),
        )
        reset_ids = _reset_blocked_tasks_to_pending(
            finalize_data,
            exclude_task_ids=baseline_unavailable_ids | authority_completed_before_retry,
        )
        # Defensive invariant: the reset set must equal the policy's rerun set
        # minus baseline-unavailable checkpoints.  A mismatch would mean the
        # handler is silently rerunning (or dropping) tasks the policy did not
        # authorize — a non-local consistency violation.
        expected_reset = sorted(
            set(resume_decision.rerun_task_ids)
            - baseline_unavailable_ids
            - authority_completed_before_retry
        )
        if reset_ids != expected_reset:
            log.warning(
                "partial-failure resume partition mismatch: policy rerun=%r "
                "actual reset=%r baseline_unavailable=%r — honoring policy rerun set",
                resume_decision.rerun_task_ids,
                reset_ids,
                sorted(baseline_unavailable_ids),
            )
        # Assert preservation: no succeeded task ID may appear in the reset set.
        preservation_violation = sorted(
            set(reset_ids) & set(resume_decision.preserved_task_ids)
        )
        if preservation_violation:
            raise AssertionError(
                "partial-failure resume would rerun preserved task(s): "
                f"{preservation_violation}"
            )
        if reset_ids:
            write_plan_artifact_json(plan_dir, "finalize.json", finalize_data, contract_context=None)
            log.info(
                "retry-blocked-tasks: reset %d task(s) from blocked -> pending: %s",
                len(reset_ids),
                ", ".join(reset_ids),
            )
            tasks = finalize_data.get("tasks", [])
        if baseline_unavailable_ids:
            log.info(
                "retry-blocked-tasks: left baseline-unavailable checkpoint(s) blocked: %s",
                ", ".join(sorted(baseline_unavailable_ids)),
            )
        # Emit evidence-only resume anchor receipt recording the explicit
        # partition so the evidence trail shows which tasks reran and which
        # durable outputs were preserved.  Receipts are observational and must
        # not affect branch decisions.
        _emit_batch_boundary_receipt(
            boundary_id="execute_resume_anchor",
            plan_dir=plan_dir,
            state=state,
            outcome=BoundaryOutcome.SUCCEEDED,
            artifact_refs=resume_decision.preserved_artifact_refs,
            extra_details={
                "resume_outcome": resume_decision.outcome.value,
                "rerun_task_ids": list(resume_decision.rerun_task_ids),
                "preserved_task_ids": list(resume_decision.preserved_task_ids),
                "baseline_unavailable_ids": sorted(baseline_unavailable_ids),
                "authority_completed_ids": sorted(authority_completed_before_retry),
                "debt_registry_preserved": resume_decision.debt_registry_preserved,
                "preserved_receipt_ids": list(resume_decision.preserved_receipt_ids),
            },
            strict=True,
        )

    finalize_data, resolved_prereq_reset_ids = _sync_resolved_prerequisite_blocked_tasks(
        finalize_data,
        plan_dir=plan_dir,
        state=state,
        log_label="resolved-prereq-retry",
    )
    if resolved_prereq_reset_ids:
        tasks = finalize_data.get("tasks", [])

    stale_authority_reset_ids = _reset_stale_authority_done_tasks(
        finalize_data,
        plan_dir=plan_dir,
        root=root,
        state=state,
    )
    if stale_authority_reset_ids:
        write_plan_artifact_json(
            plan_dir,
            "finalize.json",
            finalize_data,
            contract_context=None,
        )
        log.info(
            "stale-authority-retry: reset %d stale done task(s) to pending: %s",
            len(stale_authority_reset_ids),
            ", ".join(stale_authority_reset_ids),
        )
        tasks = finalize_data.get("tasks", [])

    deferred_checkpoint_ids, deferred_acks = _defer_baseline_unavailable_checkpoints(
        finalize_data
    )
    if deferred_checkpoint_ids:
        baseline_unavailable_acks.extend(deferred_acks)
        atomic_write_json(plan_dir / "finalize.json", finalize_data)
        log.info(
            "deferred baseline-unavailable interim verification checkpoint(s): %s",
            ", ".join(deferred_checkpoint_ids),
        )
        tasks = finalize_data.get("tasks", [])

    all_task_ids = [
        task["id"]
        for task in tasks
        if isinstance(task, dict) and isinstance(task.get("id"), str)
    ]
    all_sense_check_ids = [
        sense_check["id"]
        for sense_check in finalize_data.get("sense_checks", [])
        if isinstance(sense_check, dict) and isinstance(sense_check.get("id"), str)
    ]
    completed_task_ids = _scheduler_completed_ids_for_tasks(
        tasks,
        plan_dir=plan_dir,
        root=root,
        state=state,
    )
    blocked_task_ids = {
        task["id"]
        for task in tasks
        if task.get("status") == "blocked" and isinstance(task.get("id"), str)
        and task["id"] not in completed_task_ids
    }
    pending_tasks = [
        task
        for task in tasks
        if isinstance(task.get("id"), str)
        and task.get("status") != "blocked"
        and task.get("id") not in completed_task_ids
    ]
    review_data: dict[str, Any] = {}
    review_rework_task_ids: list[str] = []
    unrunnable_rework_task_ids: list[str] = []
    rework_mode = False
    if not pending_tasks and (plan_dir / "review.json").exists():
        try:
            loaded_review = read_json(plan_dir / "review.json")
        except (OSError, UnicodeDecodeError, ValueError):
            loaded_review = {}
        if isinstance(loaded_review, dict):
            review_data = loaded_review
            if _review_requests_rework(review_data):
                review_rework_task_ids, unrunnable_rework_task_ids = _review_rework_task_ids(
                    review_data,
                    finalize_data,
                )
                if not review_rework_task_ids:
                    if unrunnable_rework_task_ids:
                        return _handle_unroutable_review_rework(
                            plan_dir=plan_dir,
                            state=state,
                            auto_approve=auto_approve,
                            unrunnable_task_ids=unrunnable_rework_task_ids,
                        )
                    return _block_no_runnable_rework(
                        plan_dir=plan_dir,
                        state=state,
                        auto_approve=auto_approve,
                        reason=(
                            "review requested rework but did not provide any "
                            "rework_items with concrete finalize task IDs."
                        ),
                        unrunnable_task_ids=unrunnable_rework_task_ids,
                    )
                if unrunnable_rework_task_ids:
                    meta = state.setdefault("meta", {})
                    prior_attempts = meta.get(_UNROUTABLE_REWORK_ATTEMPTS_KEY, 0)
                    attempts = (
                        prior_attempts + 1 if isinstance(prior_attempts, int) else 1
                    )
                    meta[_UNROUTABLE_REWORK_ATTEMPTS_KEY] = attempts
                    return _escalate_persistent_unroutable_rework(
                        plan_dir=plan_dir,
                        state=state,
                        auto_approve=auto_approve,
                        unrunnable_task_ids=unrunnable_rework_task_ids,
                        runnable_task_ids=review_rework_task_ids,
                    )
                else:
                    state.setdefault("meta", {}).pop(
                        _UNROUTABLE_REWORK_ATTEMPTS_KEY, None
                    )
                rework_mode = True
                pending_tasks = [
                    task
                    for task in tasks
                    if task.get("id") in set(review_rework_task_ids)
                ]
    if blocked_task_ids:
        # Cross-session retry detection: if any blocked task was recorded
        # under a *different* invocation_id, this is a fresh session and we
        # should reset the blocked tasks → pending instead of short-circuiting.
        current_inv_id = (state.get("meta") or {}).get("current_invocation_id", "")
        cross_session = False
        if current_inv_id:
            for task in tasks:
                if (
                    isinstance(task, dict)
                    and task.get("id") in blocked_task_ids
                ):
                    recorded = task.get("recorded_invocation_id")
                    if isinstance(recorded, str) and recorded and recorded != current_inv_id:
                        cross_session = True
                        break
                    # Legacy blocked task without invocation stamp: treat as
                    # within-session (the conservative default). The
                    # --retry-blocked-tasks path above already handles the
                    # explicit cross-session opt-in.
        if cross_session:
            log.info(
                "Cross-session retry detected (invocation_id mismatch) — "
                "resetting blocked tasks to pending"
            )
            for task in tasks:
                if (
                    isinstance(task, dict)
                    and task.get("id") in blocked_task_ids
                ):
                    task["status"] = "pending"
                    task["executor_notes"] = ""
                    task["files_changed"] = []
                    task["commands_run"] = []
                    task["evidence_files"] = []
                    task["reviewer_verdict"] = ""
                    task.pop("recorded_invocation_id", None)
            write_plan_artifact_json(plan_dir, "finalize.json", finalize_data, contract_context=None)
            # Recompute blocked_task_ids after reset — should now be empty
            blocked_task_ids = {
                task["id"]
                for task in tasks
                if task.get("status") == "blocked" and isinstance(task.get("id"), str)
                and task["id"] not in completed_task_ids
            }
        if blocked_task_ids:
            finalize_data, resolved_prereq_reset_ids = _sync_resolved_prerequisite_blocked_tasks(
                finalize_data,
                plan_dir=plan_dir,
                state=state,
                log_label="resolved-prereq-retry(blocked-short-circuit)",
            )
            if resolved_prereq_reset_ids:
                tasks = finalize_data.get("tasks", [])
                blocked_task_ids = {
                    task["id"]
                    for task in tasks
                    if task.get("status") == "blocked"
                    and isinstance(task.get("id"), str)
                    and task["id"] not in completed_task_ids
                }
        # A declared unavailable baseline is not a task failure.  Convert an
        # all-baseline blocked frontier into durable deferred evidence before
        # evaluating the ordinary blocked-task short circuit.  Otherwise a
        # baseline capture outage consumes quality retries forever even though
        # the final review is the authoritative verifier for this condition.
        _initial_baseline_deviations = baseline_unavailable_checkpoint_deviations(
            finalize_data, blocked_task_ids
        )
        _initial_baseline_ids = {
            deviation.task_id
            for deviation in _initial_baseline_deviations
            if deviation.task_id is not None
        }
        if _initial_baseline_ids and _initial_baseline_ids == blocked_task_ids:
            deferred_ids, deferred_acks = _defer_baseline_unavailable_checkpoints(
                finalize_data
            )
            if deferred_ids:
                baseline_unavailable_acks.extend(deferred_acks)
                write_plan_artifact_json(
                    plan_dir, "finalize.json", finalize_data, contract_context=None
                )
                tasks = finalize_data.get("tasks", [])
                blocked_task_ids = {
                    task["id"]
                    for task in tasks
                    if isinstance(task, dict)
                    and task.get("status") == "blocked"
                    and isinstance(task.get("id"), str)
                }

        # Now, only short-circuit if blocked tasks remain (within-session).
        # Route blocked-task evaluation through typed policy outcomes
        # (``evaluate_blocker_recovery_policy``) while preserving the
        # existing baseline / prerequisite response structure.
        if blocked_task_ids:
            blocked_short_circuit_decision = resolve_single_batch_next_step(
                is_final_batch=False,
                all_tracked=False,
                blocked=True,
            )
            blocked_short_circuit_target = _legacy_next_step_for_execute_policy(
                blocked_short_circuit_decision
            )

            baseline_deviations = baseline_unavailable_checkpoint_deviations(
                finalize_data,
                blocked_task_ids,
            )
            baseline_blocked_ids = {
                deviation.task_id
                for deviation in baseline_deviations
                if deviation.task_id is not None
            }
            prereq_blocked_ids = blocked_task_ids - baseline_blocked_ids

            # Build typed objects for policy evaluation — every blocked task
            # and baseline deviation flows through
            # ``evaluate_blocker_recovery`` → ``BlockerRecoveryEvaluation``
            # → ``BlockedRetryDecision``.
            policy_blocked = tuple(
                BlockedTask(task_id=tid, reason="blocked_by_prereq")
                for tid in sorted(prereq_blocked_ids)
            )
            _retry_decision = evaluate_blocker_recovery_policy(
                finalize_data,
                state,
                plan_dir=plan_dir,
                blocked_tasks=policy_blocked,
                deviations=baseline_deviations,
                cross_session=False,
            )

            if baseline_deviations and not prereq_blocked_ids:
                summary = "Blocked: " + "; ".join(
                    _deviation_messages(baseline_deviations)
                )
                append_history(
                    state,
                    make_history_entry(
                        "execute",
                        duration_ms=0,
                        cost_usd=0.0,
                        result="blocked",
                        message=summary,
                    ),
                )
                save_state_merge_meta(plan_dir, state)
                response = {
                    "success": False,
                    "step": "execute",
                    "summary": summary,
                    "artifacts": ["finalize.json", "final.md"],
                    "monitor_hint": build_monitor_hint(plan_dir),
                    "next_step": blocked_short_circuit_target,
                    "state": STATE_FINALIZED,
                    "files_changed": [],
                    "deviations": _deviation_dicts(baseline_deviations),
                    "warnings": [summary],
                    "auto_approve": auto_approve,
                    "user_approved_gate": bool(
                        state["meta"].get("user_approved_gate", False)
                    ),
                    "_phase_outcome": "blocked_by_quality",
                    # Attach the typed retry decision so the handler can
                    # emit targeted anchor evidence without re-deriving it.
                    "_blocked_retry_decision": {
                        "outcome": _retry_decision.outcome.value,
                        "reason": _retry_decision.reason,
                    },
                }
                _attach_next_step_runtime(response)
                return response

            blocked_list = ", ".join(sorted(prereq_blocked_ids or blocked_task_ids))
            summary = (
                f"Blocked: existing blocked task(s) prevent dependent execution: {blocked_list}. "
                "Resolve or replan the blocked task(s) before continuing."
            )
            append_history(
                state,
                make_history_entry(
                    "execute",
                    duration_ms=0,
                    cost_usd=0.0,
                    result="blocked",
                    message=summary,
                ),
            )
            save_state_merge_meta(plan_dir, state)
            response: StepResponse = {
                "success": False,
                "step": "execute",
                "summary": summary,
                "artifacts": ["finalize.json", "final.md"],
                "monitor_hint": build_monitor_hint(plan_dir),
                "next_step": blocked_short_circuit_target,
                "state": STATE_FINALIZED,
                "files_changed": [],
                "deviations": [],
                "warnings": [summary],
                "auto_approve": auto_approve,
                "user_approved_gate": bool(state["meta"].get("user_approved_gate", False)),
                "blocked_task_ids": sorted(prereq_blocked_ids or blocked_task_ids),
                "_phase_outcome": "blocked_by_prereq",
                # Attach the typed retry decision so the handler can
                # emit targeted anchor evidence without re-deriving it.
                "_blocked_retry_decision": {
                    "outcome": _retry_decision.outcome.value,
                    "reason": _retry_decision.reason,
                },
            }
            if baseline_deviations:
                response["deviations"] = _deviation_dicts(baseline_deviations)
            _attach_next_step_runtime(response)
            return response

    baseline_deviations = []
    pending_batches = compute_task_batches(
        pending_tasks, completed_ids=completed_task_ids
    )
    max_tasks_per_batch = _resolve_max_tasks_per_batch(state, args)
    split_batches = split_oversized_batches(pending_batches, max_tasks_per_batch)
    if len(split_batches) != len(pending_batches):
        for batch_index, batch in enumerate(pending_batches, start=1):
            if len(batch) <= max_tasks_per_batch:
                continue
            chunks = (len(batch) + max_tasks_per_batch - 1) // max_tasks_per_batch
            log.warning(
                "oversized batch %d dispatched %d tasks (> ceiling %d); "
                "splitting into %d chunks of <=%d",
                batch_index,
                len(batch),
                max_tasks_per_batch,
                chunks,
                max_tasks_per_batch,
            )
    # The single-batch fast path is only safe for a clean first execution.
    # On resume, ``pending_batches`` is the authoritative runnable frontier;
    # replacing it with ``all_task_ids`` can co-scope unrelated/stale tasks
    # and route the batch using complexity from outside that frontier.
    single_batch_mode = _single_batch_mode_allowed(
        all_task_ids=all_task_ids,
        pending_task_count=len(pending_tasks),
        pending_batch_count=len(split_batches),
        completed_task_ids=completed_task_ids,
        max_tasks_per_batch=max_tasks_per_batch,
    )
    global_batches = split_oversized_batches(
        compute_global_batches(finalize_data),
        max_tasks_per_batch,
    )
    global_batch_lookup = {
        tuple(batch): index + 1 for index, batch in enumerate(global_batches)
    }
    task_to_batch_number = _task_to_global_batch_number_map(global_batches)
    no_pending_execution = not pending_tasks and not rework_mode
    batches_to_run = (
        [review_rework_task_ids]
        if rework_mode
        else ([] if no_pending_execution else ([all_task_ids] if single_batch_mode else split_batches))
    )
    total_batches = len(batches_to_run) or 1
    plan_mode = state["config"].get("mode", "code")
    if no_pending_execution:
        # All tasks are already terminal; the durable record lives in the
        # per-batch artifacts. Load them so aggregation, sense-check
        # accounting, and the final transition use the completed work instead
        # of an empty reconstructed payload.
        loaded_batch_payloads = _replay_proven_batch_artifacts(
            plan_dir=plan_dir,
            finalize_data=finalize_data,
            known_task_ids=all_task_ids,
            known_sense_check_ids=all_sense_check_ids,
            mode=plan_mode,
            state=state,
        )
        if loaded_batch_payloads:
            total_batches = max(total_batches, len(loaded_batch_payloads))
            write_plan_artifact_json(
                plan_dir, "finalize.json", finalize_data, contract_context=None
            )
            batch_payloads = loaded_batch_payloads
    active_task_ids = set(
        review_rework_task_ids
        if rework_mode
        else (
            all_task_ids
            if no_pending_execution or single_batch_mode
            else [task["id"] for task in pending_tasks]
        )
    )
    active_sense_check_ids = set(
        all_sense_check_ids
        if single_batch_mode
        else _active_sense_check_ids(finalize_data, active_task_ids)
    )

    batch_payloads: list[dict[str, Any]] = []
    all_attribution_records: list[dict[str, Any]] = []
    trace_chunks: list[str] = []
    total_duration_ms = 0
    total_cost_usd = 0.0
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_total_tokens = 0
    rate_limits: list[dict[str, Any] | None] = []
    timeout_error: CliError | None = None
    latest_session_id: str | None = None
    latest_model_actual: str | None = None
    latest_worker_channel: str | None = None
    latest_auth_channel: str | None = None
    latest_auth_metadata: dict[str, Any] | None = None
    latest_rendered_prompt: str | None = None
    blocking_reasons: list[str] = []
    routing_degradations: list[str] = []
    timeout_recovery: StepResponse | None = None
    # Per-batch tier routing: track the previous batch's resolved (agent, model)
    # identity so we can force a fresh session when the model changes.
    prev_batch_identity: tuple[str, str | None] | None = None
    # Save the fallback identity for tier-change freshness detection.
    fallback_agent, fallback_mode, fallback_refreshed, fallback_model = (
        agent, mode, refreshed, model
    )
    # Tier routing observability — only populated when tier_map is active.
    tier_routing_active = bool(tier_map)
    # Batch-to-tier mapping for the aggregate history entry summary.
    batch_to_tier: list[dict[str, Any]] = []

    for batch_index, batch_task_ids in enumerate(batches_to_run, start=1):
        batch_number_for_artifact = 1 if single_batch_mode else _resolve_batch_artifact_number(
            batch_task_ids,
            global_batch_lookup=global_batch_lookup,
            task_to_batch_number=task_to_batch_number,
            batch_index=batch_index,
        )
        batch_sense_check_ids = (
            all_sense_check_ids
            if single_batch_mode
            else _active_sense_check_ids(finalize_data, set(batch_task_ids))
        )
        _prepare_scoped_batch_checkpoint(
            plan_dir,
            batch_number=batch_number_for_artifact,
            task_ids=batch_task_ids,
            sense_check_ids=batch_sense_check_ids,
            state=state,
            finalize_data=finalize_data,
        )
        batch_template_path = (
            None
            if single_batch_mode
            else _write_execute_batch_template(
                plan_dir,
                batch_number_for_artifact,
                batch_task_ids,
                batch_sense_check_ids,
            )
        )
        batch_prompt = (
            None
            if single_batch_mode
            else _execute_batch_prompt(
                state,
                plan_dir,
                batch_task_ids,
                completed_task_ids,
                root=root,
                rework_context=(
                    _review_rework_context(review_data, finalize_data, batch_task_ids)
                    if rework_mode
                    else None
                ),
                batch_template_path=batch_template_path,
            )
        )
        batches_total_for_observation = total_batches

        # Per-batch tier resolution: select the model for the max task
        # complexity in this batch.  Falls back to the caller-provided
        # agent/mode/model when tier_map is None or the complexity has no entry.
        batch_agent, batch_mode, batch_refreshed, batch_model = (
            agent, mode, refreshed, model
        )
        # Tier routing per-batch observability (only populated when active).
        batch_raw_complexity: int | None = None
        batch_tier_complexity: int | None = None
        batch_tier_spec: str | None = None
        batch_tier_source: str | None = None
        batch_tier_projected: int | None = None
        batch_tier_counterfactual_tag: str | None = None
        batch_tier_low_confidence: bool = False
        if tier_map:
            batch_complexity = compute_batch_complexity(
                finalize_data, batch_task_ids
            )
            batch_raw_complexity = batch_complexity
            batch_tier_complexity = batch_complexity
            resolution = _calibration_tier_spec(
                plan_dir=plan_dir,
                tier_map=tier_map,
                batch_task_ids=batch_task_ids,
                batch_complexity=batch_complexity,
            )
            batch_tier_source = resolution.source
            batch_tier_projected = resolution.projected_tier
            batch_tier_counterfactual_tag = resolution.counterfactual_tag
            batch_tier_low_confidence = resolution.low_confidence
            if resolution.spec:
                batch_tier_spec = resolution.spec
                tier_agent, tier_mode, tier_model = _resolve_tier_spec(
                    args, resolution.spec
                )
                batch_agent, batch_mode, batch_model = (
                    tier_agent, tier_mode, tier_model
                )
                # Freshness: start a new session for every batch after the
                # first. Persistent codex sessions accumulate context across
                # batches and eventually return empty output; per-batch sessions
                # keep context bounded without changing the resolved model.
                if batch_index == 1:
                    batch_refreshed = refreshed  # already set by caller
                else:
                    batch_refreshed = True
                # Update active-step state to reflect the tier-selected model
                # while this batch runs. Persist immediately so the on-disk
                # run_id matches the one the worker's liveness callback uses for
                # ``touch_active_step`` (see the matching note in
                # handle_execute_one_batch) — otherwise the liveness heartbeat
                # silently no-ops for every batch after the first.
                set_active_step(
                    state,
                    step="execute",
                    agent=batch_agent,
                    mode=batch_mode,
                    model=batch_model,
                )
                save_state_merge_meta(plan_dir, state)

        batch_resolved_model = (
            batch_model if batch_model is not None else resolved_model
        )
        routing_record = _build_routing_record(
            batch_complexity=batch_raw_complexity,
            selected_tier=batch_tier_complexity,
            selected_spec=batch_tier_spec,
            resolved_agent=batch_agent,
            resolved_mode=batch_mode,
            resolved_model=batch_resolved_model,
            tier_map_configured=bool(tier_map),
            tier_routing_active=tier_routing_active,
        )

        try:
            # Per-batch tier routing may have replaced ``batch_model`` with a
            # tier-resolved literal (already a real model name). For the
            # fallback / non-tier case, ``batch_model`` is the unresolved
            # ``model`` and ``resolved_model`` carries the default-applied
            # version. Use the tier-resolved literal when present (it is
            # already concrete), otherwise the caller-supplied resolved_model.
            result = _run_and_merge_batch(
                root=root,
                plan_dir=plan_dir,
                state=state,
                args=args,
                agent=batch_agent,
                mode=batch_mode,
                refreshed=batch_refreshed,
                model=batch_model,
                effort=effort,
                resolved_model=batch_resolved_model,
                prompt_override=batch_prompt,
                batch_task_ids=batch_task_ids,
                batch_sense_check_ids=batch_sense_check_ids,
                finalize_data=finalize_data,
                batch_number=batch_number_for_artifact,
                batches_total=batches_total_for_observation,
                quality_config=quality_config,
                routing_record=routing_record,
                capture_git_status_snapshot_fn=_capture_git_status_snapshot,
            )
        except CliError as error:
            if error.code == "worker_timeout":
                timeout_error = error
                latest_session_id = (
                    error.extra.get("session_id")
                    if isinstance(error.extra.get("session_id"), str)
                    else latest_session_id
                )
                timeout_recovery = _recover_execute_timeout(
                    plan_dir=plan_dir,
                    state=state,
                    error=error,
                    agent=batch_agent,
                    mode=batch_mode,
                    refreshed=refreshed,
                    model=batch_resolved_model,
                    auto_approve=auto_approve,
                    args=args,
                    batch_number=(
                        None if single_batch_mode else batch_number_for_artifact
                    ),
                    persist_state=False,
                )
                finalize_data = read_json(plan_dir / "finalize.json")
                break
            record_step_failure(
                plan_dir,
                state,
                step="execute",
                iteration=state["iteration"],
                error=error,
            )
            raise

        total_duration_ms += result.worker.duration_ms
        total_cost_usd += result.worker.cost_usd
        total_prompt_tokens += int(result.worker.prompt_tokens or 0)
        total_completion_tokens += int(result.worker.completion_tokens or 0)
        total_total_tokens += int(result.worker.total_tokens or 0)
        rate_limits.append(result.worker.rate_limit)
        latest_session_id = result.worker.session_id
        latest_model_actual = result.worker.model_actual
        latest_worker_channel = result.worker.worker_channel
        latest_auth_channel = result.worker.auth_channel
        latest_auth_metadata = result.worker.auth_metadata
        latest_rendered_prompt = result.worker.rendered_prompt
        apply_session_update(
            state,
            "execute",
            result.agent,
            result.worker.session_id,
            mode=result.mode,
            refreshed=result.refreshed,
            model=batch_resolved_model,
            worker_channel=result.worker.worker_channel,
            auth_channel=result.worker.auth_channel,
            auth_metadata=result.worker.auth_metadata,
        )
        # Track the actual tier-selected model identity for the next batch's
        # freshness comparison (timeout recovery paths read this same tracking).
        prev_batch_identity = (batch_agent, batch_model)
        # Record batch-to-tier mapping for the aggregate history entry.
        if tier_routing_active:
            batch_to_tier.append({
                "batch_number": batch_number_for_artifact,
                "batch_index": batch_index,
                "batch_complexity": batch_tier_complexity,
                "tier_model_spec": batch_tier_spec,
                "resolved_agent": batch_agent,
                "resolved_mode": batch_mode,
                "resolved_model": batch_model,
                "actual_agent": result.payload.get("routing", {}).get("actual_agent"),
                "actual_model": result.payload.get("routing", {}).get("actual_model"),
                "routing_source": batch_tier_source,
                "projected_tier": batch_tier_projected,
                "counterfactual_tag": batch_tier_counterfactual_tag,
                "low_confidence": batch_tier_low_confidence,
            })
        batch_payloads.append(result.payload)
        all_attribution_records.extend(result.attribution_records)
        routing_degradations.extend(result.routing_degradations)
        if result.worker.trace_output is not None:
            trace_chunks.append(result.worker.trace_output)
        completed_task_ids = _scheduler_completed_ids_for_tasks(
            finalize_data.get("tasks", []),
            plan_dir=plan_dir,
            root=root,
            state=state,
        )
        newly_blocked_task_ids = {
            task["id"]
            for task in finalize_data.get("tasks", [])
            if task.get("status") == "blocked"
            and isinstance(task.get("id"), str)
            and task["id"] in set(batch_task_ids)
            and task["id"] not in completed_task_ids
        }
        # Stamp each newly-blocked task with the current invocation_id so the
        # short-circuit can distinguish within-session from cross-session blocks.
        current_inv_id = (state.get("meta") or {}).get("current_invocation_id", "")
        if newly_blocked_task_ids and current_inv_id:
            for task in finalize_data.get("tasks", []):
                if (
                    isinstance(task, dict)
                    and task.get("id") in newly_blocked_task_ids
                ):
                    task["recorded_invocation_id"] = current_inv_id
        blocking_reasons = build_blocking_reasons(
            tracked_tasks=result.merged_task_count,
            total_tasks=result.total_task_count,
            acknowledged_checks=result.acknowledged_sense_check_count,
            total_checks=result.total_sense_check_count,
            missing_task_evidence=result.missing_task_evidence,
        )
        blocked_task_reason = _blocked_task_reason(newly_blocked_task_ids)
        if blocked_task_reason:
            blocking_reasons.append(blocked_task_reason)
        if blocking_reasons:
            agent = result.agent
            mode = result.mode
            refreshed = result.refreshed
            break
        agent = result.agent
        mode = result.mode
        refreshed = result.refreshed

    plan_mode = state["config"].get("mode", "code")
    # Aggregate from the durable audited batch artifacts (execution_batch_N.json)
    # rather than the in-memory raw payloads. Raw payloads can be truncated or
    # placeholders; the audited files carry the final files_changed/task_updates.
    audited_batch_payloads = [
        read_json(path) for path in list_batch_artifacts(plan_dir)
    ] or batch_payloads
    aggregate_payload = _build_aggregate_execution_payload(
        audited_batch_payloads,
        completed_batches=len(audited_batch_payloads),
        total_batches=total_batches,
        mode=plan_mode,
        plan_dir=plan_dir,
        state=state,
    )
    if timeout_error is not None:
        aggregate_payload["deviations"] = list(aggregate_payload.get("deviations", []))
        aggregate_payload["deviations"].append(
            f"Execute timed out after {len(batch_payloads)}/{total_batches} completed batches: {timeout_error.message}"
        )
    if trace_chunks:
        atomic_write_text(plan_dir / "execution_trace.jsonl", "".join(trace_chunks))

    finalize_data = read_json(plan_dir / "finalize.json")
    finalize_data = apply_authoritative_execute_overrides(
        finalize_data,
        plan_dir=plan_dir,
    )
    reconcile_finalized_review_scope_claims(
        finalize_data,
        plan_dir=plan_dir,
        project_dir=project_dir,
        state=state,
    )
    deferred_checkpoint_ids, deferred_acks = _defer_baseline_unavailable_checkpoints(
        finalize_data
    )
    if deferred_checkpoint_ids:
        baseline_unavailable_acks.extend(deferred_acks)
        log.info(
            "deferred baseline-unavailable verification checkpoint(s): %s",
            ", ".join(deferred_checkpoint_ids),
        )
    if baseline_unavailable_acks:
        aggregate_payload.setdefault("sense_check_acknowledgments", []).extend(
            baseline_unavailable_acks
        )
    _chain_policy = (state.get("meta") or {}).get("chain_policy")
    _milestone_base_sha = (
        _chain_policy.get("milestone_base_sha")
        if isinstance(_chain_policy, dict)
        else None
    )
    execution_audit = validate_execution_evidence(
        finalize_data,
        project_dir,
        mode=state["config"].get("mode", "code"),
        state=state,
        plan_dir=plan_dir,
        artifact_prefix="execution_audit_aggregate",
        base_ref=_milestone_base_sha,
    )
    deviations = _aggregate_terminal_deviations(
        aggregate_payload,
        timeout_recovery=timeout_recovery,
        execution_audit=execution_audit,
        blocked_task_ids=blocked_task_ids,
    )
    if all_attribution_records:
        execution_audit["auto_attribution"] = all_attribution_records
    aggregate_payload["deviations"] = deviations
    if not is_prose_mode(state):
        project_advisory_path_sets(
            aggregate_payload,
            plan_dir=plan_dir,
            artifact_prefix="execution",
            keys=("files_changed",),
        )
    write_plan_artifact_json(plan_dir, "execution.json", aggregate_payload, contract_context=None)
    drift = _compute_scope_drift_for_execute_surface(
        project_dir=project_dir,
        aggregate_payload=aggregate_payload,
        state=state,
        phase_context=f"execute auto-loop aggregate after {len(batch_payloads)}/{total_batches} completed batches",
        plan_dir=plan_dir,
    )
    atomic_write_json(plan_dir / "execution_audit.json", execution_audit)
    write_plan_artifact_json(plan_dir, "finalize.json", finalize_data, contract_context=None)
    atomic_write_text(
        plan_dir / "final.md", render_final_md(finalize_data, phase="execute")
    )
    finalize_hash = sha256_file(plan_dir / "finalize.json")

    completed_task_ids = _scheduler_completed_ids_for_tasks(
        finalize_data.get("tasks", []),
        plan_dir=plan_dir,
        root=root,
        state=state,
    )
    completed_task_ids |= _durably_evidenced_finalized_task_ids(
        finalize_data.get("tasks", [])
    )
    tracked_tasks, total_tasks, acknowledged_checks, total_checks = (
        _count_execute_tracking(
            finalize_data,
            active_task_ids=active_task_ids,
            active_sense_check_ids=active_sense_check_ids,
            completed_task_ids=completed_task_ids,
        )
    )
    aggregate_pre_existing_ids = _pre_existing_task_ids(plan_dir)
    if is_prose_mode(state):
        missing_task_evidence = _check_done_task_evidence(
            finalize_data.get("tasks", []),
            issues=deviations,
            should_classify=lambda task: task.get("id") in active_task_ids,
            has_evidence=lambda task: bool(task.get("sections_written")),
            has_advisory_evidence=lambda task: True,
            missing_message="Done tasks missing sections_written: ",
            advisory_message="",
            pre_existing=aggregate_pre_existing_ids,
        )
    else:
        missing_task_evidence = _check_done_task_evidence_by_kind(
            finalize_data.get("tasks", []),
            issues=deviations,
            should_classify=lambda task: task.get("id") in active_task_ids,
            pre_existing=aggregate_pre_existing_ids,
        )
    blocking_reasons = build_blocking_reasons(
        tracked_tasks=tracked_tasks,
        total_tasks=total_tasks,
        acknowledged_checks=acknowledged_checks,
        total_checks=total_checks,
        missing_task_evidence=missing_task_evidence,
        timeout_reason=(
            f"execution timed out after {len(batch_payloads)}/{total_batches} completed batches"
            if timeout_error is not None
            else None
        ),
    )
    active_blocked_task_ids = {
        task["id"]
        for task in finalize_data.get("tasks", [])
        if task.get("status") == "blocked"
        and isinstance(task.get("id"), str)
        and task["id"] in active_task_ids
        and task["id"] not in completed_task_ids
    }
    baseline_unavailable_blocked_ids = baseline_unavailable_checkpoint_ids(
        finalize_data, active_blocked_task_ids
    )
    active_blocked_task_ids -= baseline_unavailable_blocked_ids
    prereq_blocked_task_ids = _prerequisite_blocked_task_ids(
        finalize_data.get("tasks", []),
        active_task_ids=active_task_ids,
    )
    blocked_task_reason = _blocked_task_reason(active_blocked_task_ids)
    if blocked_task_reason:
        blocking_reasons.append(blocked_task_reason)
    blocking_reasons.extend(_deviation_messages(baseline_deviations))
    _append_scope_drift_blocker(blocking_reasons, state, drift)
    if routing_degradations:
        blocking_reasons.extend(routing_degradations)

    routing_blocked = any(reason in blocking_reasons for reason in routing_degradations)
    blocked = bool(blocking_reasons)
    if routing_blocked:
        state["current_state"] = STATE_BLOCKED
        state["resume_cursor"] = {
            "phase": "execute",
            "batch_index": None,
            "retry_strategy": "fresh_session",
            "reason": "routing_degradation",
        }
    elif not blocked and timeout_error is None:
        state["current_state"] = STATE_EXECUTED
    if timeout_error is not None and latest_session_id is not None:
        apply_session_update(
            state,
            "execute",
            agent,
            latest_session_id,
            mode=mode,
            refreshed=refreshed,
            model=resolved_model,
        )
    user_approved_gate = bool(state["meta"].get("user_approved_gate", False))
    approval_mode = _resolve_execute_approval_mode(
        auto_approve=auto_approve,
        user_approved_gate=user_approved_gate,
    )
    raw_output_file: str | None = None
    result_value = "blocked" if blocked else "success"
    message: str | None = None
    if timeout_error is not None:
        result_value = "timeout"
        raw_output = str(timeout_error.extra.get("raw_output") or timeout_error.message)
        raw_output_file = store_raw_worker_output(
            plan_dir, "execute", state["iteration"], raw_output
        )
        message = timeout_error.message
    receipt_worker = WorkerResult(
        payload=aggregate_payload,
        raw_output="",
        duration_ms=total_duration_ms,
        cost_usd=total_cost_usd,
        session_id=latest_session_id,
        trace_output="".join(trace_chunks) if trace_chunks else None,
        rendered_prompt=latest_rendered_prompt,
        model_actual=latest_model_actual,
        prompt_tokens=total_prompt_tokens,
        completion_tokens=total_completion_tokens,
        total_tokens=total_total_tokens,
        rate_limit=aggregate_rate_limits(rate_limits),
        worker_channel=latest_worker_channel,
        auth_channel=latest_auth_channel,
        auth_metadata=latest_auth_metadata,
    )
    receipt_metrics = execute_metrics(aggregate_payload, drift)
    receipt_metrics["batches"] = batch_payloads
    receipt_worker.receipt_metrics = receipt_metrics
    aggregate_history_entry = make_history_entry(
        "execute",
        duration_ms=total_duration_ms,
        cost_usd=total_cost_usd,
        result=result_value,
        agent=agent,
        mode=mode,
        worker=receipt_worker,
        output_file="execution.json",
        artifact_hash=sha256_file(plan_dir / "execution.json"),
        finalize_hash=finalize_hash,
        raw_output_file=raw_output_file,
        message=message,
        approval_mode=approval_mode,
    )
    # Include batch-to-tier mapping summary when tier routing was active.
    if tier_routing_active and batch_to_tier:
        aggregate_history_entry["batch_to_tier"] = batch_to_tier
    append_history(state, aggregate_history_entry)
    try:
        artifact_hash = sha256_file(plan_dir / "execution.json")
        receipt = build_receipt(
            phase="execute",
            state=state,
            plan_dir=plan_dir,
            args=args,
            worker=receipt_worker,
            agent=agent,
            mode=mode,
            output_file="execution.json",
            artifact_hash=artifact_hash,
            verdict=result_value,
            drift=drift,
        )
        write_receipt(plan_dir, receipt, project_dir=project_dir)
    except Exception:
        log.warning("Execute receipt emission failed", exc_info=True)
    save_state_merge_meta(plan_dir, state)

    artifacts = ["execution.json", "execution_audit.json", "finalize.json", "final.md"]
    if trace_chunks:
        artifacts.append("execution_trace.jsonl")
    tracking_note = _format_execute_tracking_note(
        merged_count=tracked_tasks,
        total_tasks=total_tasks,
        acknowledged_count=acknowledged_checks,
        total_checks=total_checks,
    )
    if timeout_error is not None:
        summary = (
            f"Execute timed out after {len(batch_payloads)}/{total_batches} completed batches. "
            "Prior batches were persisted; re-run execute to continue."
        )
    elif blocked:
        summary = (
            "Blocked: "
            + "; ".join(blocking_reasons)
            + ". Re-run execute to complete tracking."
        )
    else:
        summary = aggregate_payload["output"] + tracking_note
    if drift.severity != "none":
        summary = f"[scope_drift={drift.severity}] {summary}"
    # Determine _phase_outcome with priority: timeout > prereq > quality > success
    if timeout_error is not None:
        phase_outcome = "timeout"
        aggregate_next_step_decision = resolve_single_batch_next_step(
            is_final_batch=False,
            all_tracked=False,
            blocked=False,
        )
    elif prereq_blocked_task_ids:
        phase_outcome = "blocked_by_prereq"
        aggregate_next_step_decision = resolve_single_batch_next_step(
            is_final_batch=True,
            all_tracked=False,
            blocked=True,
        )
    elif blocked:
        phase_outcome = "blocked_by_quality"
        aggregate_next_step_decision = resolve_single_batch_next_step(
            is_final_batch=True,
            all_tracked=False,
            blocked=True,
        )
    else:
        phase_outcome = "success"
        aggregate_next_step_decision = resolve_single_batch_next_step(
            is_final_batch=True,
            all_tracked=True,
            blocked=False,
        )

    # Collect blocked task notes for blocked_by_prereq path
    blocked_task_notes: dict[str, str] = {}
    if prereq_blocked_task_ids:
        for task in finalize_data.get("tasks", []):
            tid = task.get("id")
            if isinstance(tid, str) and tid in prereq_blocked_task_ids:
                notes = task.get("executor_notes") or ""
                if notes:
                    blocked_task_notes[tid] = str(notes)

    # ``execution.json`` is intentionally cumulative evidence.  The phase
    # result drives retry policy, so it must only carry diagnostics produced by
    # this invocation.  A no-pending resume loads old artifacts solely to
    # corroborate completed work; none of their old deviations can gate this
    # new transition.
    phase_deviations, deferred_evidence = phase_quality_deviations_for_current_attempt(
        batch_payloads if not no_pending_execution else [],
        blocking_reasons=blocking_reasons,
    )

    response: StepResponse = {
        "success": not blocked and timeout_error is None,
        "step": "execute",
        "summary": summary,
        "artifacts": artifacts,
        "monitor_hint": build_monitor_hint(plan_dir),
        "next_step": _legacy_next_step_for_execute_policy(
            aggregate_next_step_decision
        ),
        "state": (
            STATE_BLOCKED
            if routing_blocked
            else STATE_FINALIZED if blocked or timeout_error is not None else STATE_EXECUTED
        ),
        "files_changed": aggregate_payload.get("files_changed", []),
        "deviations": phase_deviations,
        "warnings": [summary] if blocked or timeout_error is not None else [],
        "auto_approve": auto_approve,
        "user_approved_gate": user_approved_gate,
        "_phase_outcome": phase_outcome,
    }
    if active_blocked_task_ids:
        response["blocked_task_ids"] = sorted(active_blocked_task_ids)
    if deferred_evidence:
        response["deferred_evidence"] = deferred_evidence
    if routing_blocked:
        response["result"] = "blocked"
    if blocked_task_notes:
        response["blocked_task_notes"] = blocked_task_notes
    _attach_next_step_runtime(response)
    return response
