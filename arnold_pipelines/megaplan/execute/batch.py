from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import shlex
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from arnold.workflow.boundary_evidence import AuthorityRecord, BoundaryOutcome, BoundaryReceipt
import arnold_pipelines.megaplan.workers as worker_module
from arnold_pipelines.megaplan.fallback_chains import (
    classify_retryability,
    configured_fallback_chain_for_phase,
    fallback_observability_fields,
    is_retryable_classification,
    normalize_fallback_spec_list,
    provider_family,
    select_fallback_spec,
)
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
    is_transient_execute_advisory,
    list_batch_artifacts,
    load_config,
    make_history_entry,
    record_step_failure,
    read_json,
    render_final_md,
    save_state_merge_meta,
    set_active_step,
    sha256_file,
    sha256_text,
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
    is_contradictory_done_budget_row,
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
    EXECUTE_DISPATCH_WBC_KEY,
    build_execute_batch_dispatch_spec,
    dispatch_wbc_summary,
)
from arnold_pipelines.megaplan.orchestration.finalize_authority import (
    FinalizeMutationContext,
    load_finalize_for_update,
    publish_finalize_update,
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
    validate_execution_evidence,
)
from arnold_pipelines.megaplan.orchestration.phase_result import BlockedTask, Deviation
from arnold_pipelines.megaplan.orchestration.authority_readers import (
    effective_execute_completed_task_ids,
)
from arnold_pipelines.megaplan.orchestration.validation_jobs import (
    SELECTOR_DEFERRED,
    SELECTOR_INVALID,
    classify_selector_lifecycle,
    declared_task_output_paths,
    deferred_selector_evidence,
    graph_declared_output_paths,
    normalize_selector_path,
)
from arnold_pipelines.megaplan.orchestration.plan_contracts import (
    pre_existing_task_ids_from_contract,
)
from arnold_pipelines.megaplan.calibration import query_route_if_enabled
from arnold_pipelines.megaplan.blocker_recovery import build_prerequisite_scopes
from arnold_pipelines.megaplan.quality_resolutions import (
    is_non_terminal_quality_resolution,
    latest_quality_resolutions,
)
from arnold_pipelines.megaplan.blocker_recovery import quality_blocker_id
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
    AgentMode,
    CliError,
    MOCK_ENV_VAR,
    PlanState,
    StepResponse,
    parse_agent_spec,
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


def _publish_execute_finalize(
    plan_dir: Path,
    finalize_data: dict[str, Any],
    *,
    operation: str,
    state: Mapping[str, Any] | None = None,
) -> None:
    """Publish execution-owned fields through the sole Finalize writer."""

    active_step = state.get("active_step") if isinstance(state, Mapping) else None
    run_id = (
        active_step.get("run_id")
        if isinstance(active_step, Mapping) and isinstance(active_step.get("run_id"), str)
        else None
    )
    publish_finalize_update(
        plan_dir,
        finalize_data,
        context=FinalizeMutationContext(
            owner="execute",
            operation=operation,
            attempt_id=f"execute:{operation}:{run_id or 'unbound'}",
            run_id=run_id,
        ),
        # All production callers are inside handle_execute's plan lock.  Tests
        # invoke lower-level helpers directly but still exercise identical CAS.
        lock_held=True,
    )

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
    _publish_execute_finalize(
        plan_dir,
        finalize_data,
        operation="repair-missing-user-action-gate",
        state=state,
    )
    atomic_write_text(plan_dir / "user_actions.md", _render_user_actions_md(finalize_data))
    atomic_write_text(plan_dir / "final.md", render_final_md(finalize_data, phase="execute"))
    return True




# ═══════════════════════════════════════════════════════════════════════════
# M8A Step 13 — Verify-only repair adoption at the execute action boundary
# ═══════════════════════════════════════════════════════════════════════════
#
# This wiring rereads current Run Authority grant/fence, current Custody
# lease/epoch, and the required WBC attempt reference through the existing
# ``arnold_pipelines.megaplan.custody.action_validator`` action-boundary seam
# before repair/worker dispatch.  On exact match it records adoption
# evidence and emits a ``repair_verify`` work-ledger event; on mismatch it
# quarantines the receipt as evidence and continues normal execution WITHOUT
# rewriting immutable attempts.
#
# North Star guarantees:
# * **Verify-only** — The receipt is evidence, NOT authority.  Adoption is a
#   deterministic comparison; it never substitutes for an authoritative
#   action-boundary validation, grant, lease, WBC, completion, publication,
#   delivery, or status decision.
# * **No stale-source acceptance** — Every call rereads current sources
#   immediately.  Receipt fields are never used as substitutes for current
#   reads; they identify *which* current values to read.
# * **Shadow-first** — All production gates and mutating effects remain
#   disabled in M8A.  The helper runs in shadow/report-only mode (emits
#   evidence + ledger events, never skips replay or modifies dispatch)
#   until canary promotion flips ``ARNOLD_M8A_REPAIR_ADOPTION_ENFORCEMENT``.

_M8A_REPAIR_ADOPTION_ENFORCEMENT_ENV = "ARNOLD_M8A_REPAIR_ADOPTION_ENFORCEMENT"
_M8A_REPAIR_ADOPTION_DISABLE_VALUES: frozenset[str] = frozenset(
    {"0", "false", "no", "off"}
)


def _m8a_repair_adoption_enforcement_enabled() -> bool:
    """Return ``True`` when M8A repair-adoption canary promotion is active.

    Controlled by ``ARNOLD_M8A_REPAIR_ADOPTION_ENFORCEMENT`` — defaults to
    ON after the post-M11 promotion.  When explicitly disabled, the repair adoption check
    runs in shadow/report-only mode: it rereads boundary conditions, emits
    adoption/quarantine evidence, and emits ``repair_verify`` work-ledger
    events, but never skips replay or modifies dispatch flow.
    """
    raw = os.getenv(_M8A_REPAIR_ADOPTION_ENFORCEMENT_ENV, "").strip().lower()
    if raw in _M8A_REPAIR_ADOPTION_DISABLE_VALUES:
        return False
    return True


def _collect_pending_repair_receipts(
    finalize_data: dict[str, Any],
    plan_dir: Path,
    batch_task_ids: list[str],
) -> list[dict[str, Any]]:
    """Collect pending repair receipts applicable to this batch's tasks.

    Looks for receipts in:
    * ``finalize_data["pending_repair_receipts"]`` (list of dict payloads).
    * ``<plan_dir>/repair_receipts/*.json`` (one receipt payload per file).

    Filters to receipts whose ``task_contract`` matches a batch task ID
    (exact or ``"<task_id>:<suffix>"`` form).  Returns an empty list when
    no pending receipts apply.
    """
    import json as _json

    batch_id_set = set(batch_task_ids)
    candidates: list[dict[str, Any]] = []

    pending = finalize_data.get("pending_repair_receipts")
    if isinstance(pending, list):
        for r in pending:
            if isinstance(r, dict):
                candidates.append(dict(r))

    receipts_dir = Path(plan_dir) / "repair_receipts"
    if receipts_dir.is_dir():
        for path in sorted(receipts_dir.glob("*.json")):
            try:
                data = _json.loads(path.read_text())
            except (OSError, _json.JSONDecodeError):
                continue
            if isinstance(data, dict):
                stamped = {"__source_path": str(path)}
                stamped.update(data)
                candidates.append(stamped)

    applicable: list[dict[str, Any]] = []
    for r in candidates:
        task_contract = r.get("task_contract")
        if not isinstance(task_contract, str) or not task_contract:
            continue
        if any(
            task_contract == tid or task_contract.startswith(tid + ":")
            for tid in batch_id_set
        ):
            applicable.append(r)
    return applicable


def _reread_current_boundary_conditions(
    receipt: Mapping[str, Any],
    *,
    plan_dir: Path | None = None,
    task_contract: str = "",
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Reread current Run Authority, Custody, and WBC boundary conditions.

    Uses the existing ``action_validator.validate_action_boundary_simple``
    seam to perform the reread.  Receipt fields are used only to identify
    *which* current values to read (grant id, fence token, target, WBC
    reference) — they are NEVER substituted for the current reads
    themselves.

    Returns ``(current_values, diagnostics)``.  Missing sources are
    recorded in ``diagnostics`` rather than silently defaulted from the
    receipt.
    """
    diagnostics: dict[str, Any] = {
        "reread_attempted": True,
        "sources": {},
        "reread_errors": [],
    }
    current: dict[str, Any] = {}

    grant_id = str(receipt.get("run_authority_grant_id") or "")
    try:
        fence_token = int(receipt.get("coordinator_fence_token") or 0)
    except (TypeError, ValueError):
        fence_token = 0
    wbc_ref = str(receipt.get("wbc_attempt_reference") or "")
    target = receipt.get("target")
    if not isinstance(target, Mapping):
        target = {}

    try:
        from arnold_pipelines.megaplan.custody.action_validator import (
            validate_action_boundary_simple,
        )

        result = validate_action_boundary_simple(
            action_type="repair",
            target=dict(target),
            run_authority_grant_id=grant_id,
            coordinator_fence_token=fence_token,
            wbc_attempt_reference=wbc_ref,
        )
        for check in result.checks:
            src = check.source
            obs = dict(check.observed_value) if check.observed_value else {}
            diagnostics["sources"][src] = {
                "outcome": str(check.outcome),
                "detail": check.detail,
                "observed_value": obs,
            }
            if src == "run_authority_grant":
                grant_obs = obs.get("grant_id") or obs.get("id")
                if grant_obs:
                    current["run_authority_grant_id"] = str(grant_obs)
            elif src == "run_authority_fence":
                fence_obs = obs.get("fence_token") or obs.get("token")
                if fence_obs is not None:
                    try:
                        current["coordinator_fence_token"] = int(fence_obs)
                    except (TypeError, ValueError):
                        pass
            elif src == "custody_lease":
                lease_obs = obs.get("lease_id") or obs.get("id")
                if lease_obs:
                    current["custody_lease_id"] = str(lease_obs)
                epoch_obs = obs.get("epoch")
                if epoch_obs is not None:
                    try:
                        current["custody_epoch"] = int(epoch_obs)
                    except (TypeError, ValueError):
                        pass
            elif src == "wbc_attempt":
                wbc_obs = obs.get("attempt_id") or obs.get("reference")
                if wbc_obs:
                    current["wbc_attempt_reference"] = str(wbc_obs)
    except Exception as exc:  # pragma: no cover - defensive: reread must not crash dispatch
        diagnostics["reread_errors"].append(f"{type(exc).__name__}: {exc}")

    if plan_dir is None:
        return current, diagnostics

    # The remaining adoption fields must come from current execution
    # artifacts, never from the candidate receipt.  A missing current value
    # deliberately leaves the adoption context incomplete so the caller
    # quarantines the receipt instead of manufacturing a self-match.
    try:
        state_payload = read_json(Path(plan_dir) / "state.json")
    except (OSError, ValueError, TypeError):
        state_payload = {}
    config = state_payload.get("config") if isinstance(state_payload, dict) else {}
    project_dir_value = config.get("project_dir") if isinstance(config, dict) else None
    project_dir = (
        Path(project_dir_value)
        if isinstance(project_dir_value, str) and project_dir_value
        else None
    )
    if task_contract:
        current["task_contract"] = task_contract

    newest_task_evidence: tuple[int, Path, dict[str, Any]] | None = None
    batches_dir = Path(plan_dir) / "execute_batches"
    if batches_dir.is_dir() and task_contract:
        for artifact_path in batches_dir.glob("batch_*/tasks_*.json"):
            try:
                artifact = read_json(artifact_path)
            except (OSError, ValueError, TypeError):
                artifact = {}
            if not isinstance(artifact, dict):
                continue
            for envelope in artifact.get("result_envelopes") or []:
                if not isinstance(envelope, dict):
                    continue
                claim = envelope.get("claim")
                if not isinstance(claim, dict) or claim.get("subject_id") != task_contract:
                    continue
                candidate = (artifact_path.stat().st_mtime_ns, artifact_path, envelope)
                if newest_task_evidence is None or candidate[0] > newest_task_evidence[0]:
                    newest_task_evidence = candidate

    if newest_task_evidence is not None:
        _, evidence_path, envelope = newest_task_evidence
        dispatch = envelope.get("dispatch")
        grant = dispatch.get("grant") if isinstance(dispatch, dict) else {}
        claim = envelope.get("claim")
        plan_revision = grant.get("run_revision") if isinstance(grant, dict) else None
        result_hash = claim.get("payload_hash") if isinstance(claim, dict) else None
        if isinstance(plan_revision, str) and plan_revision:
            current["plan_revision"] = plan_revision
        if isinstance(result_hash, str) and result_hash:
            current["test_result_hash"] = result_hash
        diagnostics["sources"]["current_task_result"] = {
            "outcome": "observed",
            "detail": "latest durable result envelope for current task contract",
            "observed_value": {
                "path": str(evidence_path),
                "plan_revision": plan_revision,
                "task_contract": task_contract,
                "result_hash": result_hash,
            },
        }
    else:
        diagnostics["reread_errors"].append(
            f"current task result not found for {task_contract or '<missing>'}"
        )

    if project_dir is not None:
        try:
            proc = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=str(project_dir),
                capture_output=True,
                text=True,
                check=False,
                timeout=15,
            )
            head = proc.stdout.strip() if proc.returncode == 0 else ""
            if head:
                current["tree_commit"] = head
                diagnostics["sources"]["git_head"] = {
                    "outcome": "observed",
                    "detail": "current project HEAD",
                    "observed_value": {"tree_commit": head},
                }
            else:
                diagnostics["reread_errors"].append("current git HEAD unavailable")
        except Exception as exc:  # pragma: no cover - defensive fail closed
            diagnostics["reread_errors"].append(
                f"current git HEAD read failed: {type(exc).__name__}: {exc}"
            )

    failure = state_payload.get("latest_failure") if isinstance(state_payload, dict) else None
    if isinstance(failure, dict) and failure:
        current["blocker_hash"] = "sha256:" + hashlib.sha256(
            json.dumps(failure, sort_keys=True, separators=(",", ":"), default=str).encode(
                "utf-8"
            )
        ).hexdigest()
    else:
        current["blocker_hash"] = ""

    return current, diagnostics


def _run_repair_adoption_check(
    *,
    plan_dir: Path,
    finalize_data: dict[str, Any],
    batch_task_ids: list[str],
) -> dict[str, Any]:
    """Verify-only repair adoption check at the execute action boundary.

    For every pending repair receipt applicable to this batch's tasks:

    * Rereads current Run Authority grant/fence, Custody lease/epoch, and
      required WBC attempt reference through the existing
      :func:`action_validator.validate_action_boundary_simple` seam.
    * Builds an :class:`AdoptionContext` from the *current* reads only.
    * Calls :func:`repair_adoption.adopt_repair_receipt` to obtain a
      deterministic :class:`AdoptionDecision`.
    * On ``ADOPT``: emits a ``repair_verify`` work-ledger event and writes
      content-addressed adoption evidence.  Under canary promotion, the
      caller MAY skip replay.
    * On ``QUARANTINE`` / ``INVALID``: emits a ``repair_verify`` event
      with mismatch diagnostics and writes quarantine evidence.  Normal
      execution continues WITHOUT rewriting immutable attempts.

    Returns a structured summary.  This helper never raises — a reread or
    comparison failure is recorded as a quarantine and execution
    continues.
    """
    import hashlib as _hashlib
    import json as _json
    import time as _time

    from arnold_pipelines.megaplan.custody.repair_adoption import (
        AdoptionContext,
        AdoptionOutcome,
        adopt_repair_receipt,
    )
    from arnold_pipelines.megaplan.observability.work_ledger import (
        emit_repair_verify,
        emit_unavailable_reason,
    )

    enforcement = _m8a_repair_adoption_enforcement_enabled()
    summary: dict[str, Any] = {
        "contract_type": "repair_adoption_summary",
        "schema_version": 1,
        "enforcement": enforcement,
        "evaluated": [],
        "adopted_count": 0,
        "quarantined_count": 0,
        "skip_replay": False,
    }

    receipts = _collect_pending_repair_receipts(finalize_data, plan_dir, batch_task_ids)
    if not receipts:
        return summary

    evidence_dir = Path(plan_dir) / "evidence"
    batch_id_set = set(batch_task_ids)

    for receipt in receipts:
        task_contract_raw = str(receipt.get("task_contract") or "")
        task_id = task_contract_raw
        for tid in batch_id_set:
            if task_contract_raw == tid or task_contract_raw.startswith(tid + ":"):
                task_id = tid
                break

        start = _time.monotonic()
        current, reread_diag = _reread_current_boundary_conditions(
            receipt,
            plan_dir=Path(plan_dir),
            task_contract=task_contract_raw,
        )

        try:
            context = AdoptionContext(
                run_authority_grant_id=str(current.get("run_authority_grant_id") or ""),
                coordinator_fence_token=int(current.get("coordinator_fence_token") or 0),
                custody_lease_id=str(current.get("custody_lease_id") or ""),
                custody_epoch=int(current.get("custody_epoch") or 0),
                wbc_attempt_reference=str(current.get("wbc_attempt_reference") or ""),
                plan_revision=str(current.get("plan_revision") or ""),
                task_contract=str(current.get("task_contract") or ""),
                tree_commit=str(current.get("tree_commit") or ""),
                test_result_hash=str(current.get("test_result_hash") or ""),
                blocker_hash=str(current.get("blocker_hash") or ""),
            )
        except (ValueError, TypeError) as exc:
            duration_ms = int((_time.monotonic() - start) * 1000)
            receipt_digest = str(receipt.get("receipt_digest") or "")
            emit_unavailable_reason(
                plan_dir,
                task_id=task_id,
                measure="repair_adoption_context",
                reason=f"context_construction_failed: {type(exc).__name__}: {exc}",
            )
            emit_repair_verify(
                plan_dir,
                task_id=task_id,
                receipt_hash=receipt_digest,
                outcome="quarantine",
                duration_ms=duration_ms,
                grant_match=False,
                fence_match=False,
                mismatches=[],
                diagnostics={
                    "error": f"{type(exc).__name__}: {exc}",
                    "reread": reread_diag,
                    "enforcement": enforcement,
                },
            )
            quarantine_payload = {
                "contract_type": "repair_adoption_evidence",
                "schema_version": 1,
                "task_id": task_id,
                "decision": {
                    "outcome": "quarantine",
                    "receipt_digest": receipt_digest,
                    "mismatches": [],
                    "error": f"{type(exc).__name__}: {exc}",
                },
                "reread_diagnostics": reread_diag,
                "enforcement": enforcement,
            }
            q_hash = _hashlib.sha256(
                _json.dumps(quarantine_payload, sort_keys=True, default=str).encode("utf-8")
            ).hexdigest()[:16]
            q_filename = (
                f"repair-adoption-quarantine-{(receipt_digest or 'noreceipt')[:12]}-{q_hash}.json"
            )
            try:
                evidence_dir.mkdir(parents=True, exist_ok=True)
                (evidence_dir / q_filename).write_text(
                    _json.dumps(quarantine_payload, indent=2, sort_keys=True, default=str)
                )
            except OSError:
                pass
            summary["evaluated"].append(
                {
                    "task_id": task_id,
                    "outcome": "quarantine",
                    "receipt_digest": receipt_digest,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            summary["quarantined_count"] += 1
            continue

        decision = adopt_repair_receipt(receipt, context)
        duration_ms = int((_time.monotonic() - start) * 1000)
        outcome_str = str(decision.outcome)
        receipt_digest = decision.receipt_digest or str(receipt.get("receipt_digest") or "")
        mismatch_fields = {m.field for m in decision.mismatches}

        emit_repair_verify(
            plan_dir,
            task_id=task_id,
            receipt_hash=receipt_digest,
            outcome=outcome_str,
            duration_ms=duration_ms,
            grant_match="run_authority_grant_id" not in mismatch_fields,
            fence_match="coordinator_fence_token" not in mismatch_fields,
            mismatches=[m.to_dict() for m in decision.mismatches],
            diagnostics={
                "compared_at": decision.compared_at,
                "reread": reread_diag,
                "enforcement": enforcement,
            },
        )

        evidence_payload = {
            "contract_type": "repair_adoption_evidence",
            "schema_version": 1,
            "task_id": task_id,
            "decision": decision.to_dict(),
            "reread_diagnostics": reread_diag,
            "enforcement": enforcement,
        }
        ev_hash = _hashlib.sha256(
            _json.dumps(evidence_payload, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()[:16]
        ev_digest_suffix = (receipt_digest or "noreceipt")[:12]
        evidence_filename = (
            f"repair-adoption-{outcome_str}-{ev_digest_suffix}-{ev_hash}.json"
        )
        try:
            evidence_dir.mkdir(parents=True, exist_ok=True)
            (evidence_dir / evidence_filename).write_text(
                _json.dumps(evidence_payload, indent=2, sort_keys=True, default=str)
            )
        except OSError:
            pass

        evaluation_row = {
            "task_id": task_id,
            "outcome": outcome_str,
            "receipt_digest": receipt_digest,
            "mismatch_count": len(decision.mismatches),
            "mismatch_fields": sorted(mismatch_fields),
        }
        if decision.outcome == AdoptionOutcome.ADOPT:
            from arnold_pipelines.megaplan.authority.scope_recovery import (
                ScopeRecoveryConflict,
                claim_successor_generation,
                request_from_receipt,
            )

            authority_digest = _hashlib.sha256(
                _json.dumps(
                    {
                        "run_authority_grant_id": context.run_authority_grant_id,
                        "coordinator_fence_token": context.coordinator_fence_token,
                        "custody_lease_id": context.custody_lease_id,
                        "custody_epoch": context.custody_epoch,
                        "wbc_attempt_reference": context.wbc_attempt_reference,
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest()
            task_record = next(
                (
                    task
                    for task in finalize_data.get("tasks", [])
                    if isinstance(task, dict) and task.get("id") == task_id
                ),
                {},
            )
            generation = task_record.get("generation", 0)
            generation = generation if isinstance(generation, int) else 0
            request = request_from_receipt(
                receipt,
                task_id=task_id,
                batch_id=",".join(batch_task_ids),
                current_generation=generation,
                authority_digest=authority_digest,
            )
            try:
                successor = (
                    claim_successor_generation(plan_dir, request)
                    if request is not None
                    else None
                )
            except (ScopeRecoveryConflict, ValueError) as exc:
                evaluation_row["outcome"] = "quarantine"
                evaluation_row["scope_recovery_error"] = str(exc)
                summary["quarantined_count"] += 1
            else:
                if successor is not None:
                    evaluation_row["successor_claim"] = successor
                    task_record["generation"] = successor["generation"]
                    task_record["scope_recovery_claim_id"] = successor["claim_id"]
                    from arnold_pipelines.megaplan.execute.merge import (
                        _test_command_evidence,
                    )
                    from arnold_pipelines.megaplan.orchestration import (
                        suite_runner as _scope_suite_runner,
                    )

                    narrow = task_record.get("narrow_tests")
                    narrow = narrow if isinstance(narrow, Mapping) else {}
                    allowed_selectors = {
                        str(selector).strip().lstrip("./")
                        for selector in narrow.get("selectors", [])
                        if isinstance(selector, str) and selector.strip()
                    }
                    per_command_max = narrow.get(
                        "per_command_max_seconds",
                        narrow.get("max_seconds", 120),
                    )
                    total_max = narrow.get("total_max_seconds")
                    max_runs = narrow.get("max_runs", 2)
                    commands = list(successor["verification_commands"])
                    admission_errors: list[str] = []
                    total_declared = 0
                    if isinstance(max_runs, int) and len(commands) > max_runs:
                        admission_errors.append("verification command count exceeds max_runs")
                    for command in commands:
                        parsed = _test_command_evidence(command)
                        if parsed is None:
                            admission_errors.append(f"not a bounded test command: {command!r}")
                            continue
                        timeout_seconds, selectors = parsed
                        if timeout_seconds is None:
                            admission_errors.append(f"missing timeout wrapper: {command!r}")
                        else:
                            total_declared += timeout_seconds
                            if (
                                isinstance(per_command_max, int)
                                and timeout_seconds > per_command_max
                            ):
                                admission_errors.append(
                                    f"command timeout {timeout_seconds}s exceeds "
                                    f"per-command maximum {per_command_max}s"
                                )
                        for selector in selectors:
                            selector_base = selector.split("::", 1)[0]
                            if not any(
                                selector == allowed
                                or selector_base == allowed.split("::", 1)[0]
                                for allowed in allowed_selectors
                            ):
                                admission_errors.append(
                                    f"selector {selector!r} is outside admitted narrow tests"
                                )
                    if isinstance(total_max, int) and total_declared > total_max:
                        admission_errors.append(
                            f"declared timeout total {total_declared}s exceeds "
                            f"total maximum {total_max}s"
                        )
                    verification_results = []
                    if not admission_errors:
                        try:
                            _scope_state = read_json(Path(plan_dir) / "state.json")
                        except (OSError, ValueError, TypeError):
                            _scope_state = {}
                        _scope_config = (
                            _scope_state.get("config")
                            if isinstance(_scope_state, Mapping)
                            else {}
                        )
                        _scope_project_dir = Path(
                            str(
                                _scope_config.get("project_dir")
                                if isinstance(_scope_config, Mapping)
                                else Path.cwd()
                            )
                        )
                        for command in commands:
                            parsed = _test_command_evidence(command)
                            timeout_seconds = parsed[0] if parsed is not None else None
                            result = _scope_suite_runner.run_suite(
                                _scope_project_dir,
                                {
                                    "project_dir": str(_scope_project_dir),
                                    "plan_dir": str(plan_dir),
                                    "test_command": command,
                                },
                                phase="scope_recovery_verification",
                                deadline_seconds=(
                                    time.monotonic()
                                    + float(timeout_seconds or per_command_max or 120)
                                ),
                                idle_seconds=None,
                            )
                            verification_results.append(
                                {
                                    "command": result.command,
                                    "exit_code": result.exit_code,
                                    "status": result.status,
                                    "code_hash": result.code_hash,
                                    "timeout_reason": result.timeout_reason,
                                }
                            )
                    verification_passed = (
                        not admission_errors
                        and bool(verification_results)
                        and all(row["exit_code"] == 0 for row in verification_results)
                    )
                    verification_receipt = {
                        "schema": "megaplan.scope_recovery_verification",
                        "schema_version": 1,
                        "claim_id": successor["claim_id"],
                        "admission_errors": admission_errors,
                        "results": verification_results,
                        "passed": verification_passed,
                    }
                    verification_dir = Path(plan_dir) / "scope_recovery_verification"
                    verification_dir.mkdir(parents=True, exist_ok=True)
                    atomic_write_json(
                        verification_dir
                        / f"{str(successor['claim_id']).split(':')[-1]}.json",
                        verification_receipt,
                    )
                    evaluation_row["scope_recovery_verification"] = verification_receipt
                    if not verification_passed:
                        evaluation_row["outcome"] = "quarantine"
                        summary["quarantined_count"] += 1
                        summary["evaluated"].append(evaluation_row)
                        continue
                summary["adopted_count"] += 1
                if enforcement:
                    summary["skip_replay"] = True
        else:
            summary["quarantined_count"] += 1
        summary["evaluated"].append(evaluation_row)

    return summary

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
    completed = effective_execute_completed_task_ids(
        tasks,
        plan_dir=plan_dir,
        project_dir=project_dir,
        state=state,
        current_head=current_head,
        decisions=decisions,
    )
    # Budget-gate rows are NEVER effectively completed, even when their result
    # envelope authority was accepted (occurrence 0513dbf3f069 / 93e301ead5
    # contract: "authority adoption never overrides the gate"). The merge gate
    # stamps status=blocked plus the marker; the durable field survives the
    # --retry-blocked-tasks reset. Excluding them from the shared completed
    # reader keeps the planner (pending frontier), the reducer (blocked, not
    # false SUCCESS), the adopt gate, and the stale-authority demotion all
    # consistent: a budget-blocked row must re-enter the runnable frontier.
    budget_blocked = {
        task["id"]
        for task in tasks
        if isinstance(task, dict) and isinstance(task.get("id"), str)
        and _is_task_test_budget_blocked(task)
    }
    if budget_blocked:
        completed = {tid for tid in completed if tid not in budget_blocked}
    return completed
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
) -> AgentMode:
    """Resolve a tier spec string without mutating *args*.

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
    if isinstance(resolved, AgentMode):
        return resolved
    resolved_model = resolved.resolved_model if hasattr(resolved, "resolved_model") else None
    return AgentMode(
        agent=resolved.agent,
        mode=resolved.mode,
        refreshed=resolved.refreshed,
        model=resolved.model,
        resolved_model=resolved_model if resolved_model is not None else resolved.model,
    )


def _execute_configured_specs(
    args: argparse.Namespace,
    *,
    selected_tier_spec: str | None,
    default_spec: str,
) -> tuple[str, ...]:
    """Recover the ordered chain hidden behind a tier's selected scalar."""

    tier_models = getattr(args, "tier_models", None)
    execute_tiers = tier_models.get("execute") if isinstance(tier_models, dict) else None
    if selected_tier_spec is not None and isinstance(execute_tiers, dict):
        for raw_tier, raw_value in execute_tiers.items():
            try:
                specs = normalize_fallback_spec_list(
                    raw_value,
                    path=f"tier_models.execute.{raw_tier}",
                )
            except (TypeError, ValueError):
                continue
            if specs[0] == selected_tier_spec:
                return specs

    configured = configured_fallback_chain_for_phase(
        getattr(args, "phase_model", None),
        "execute",
    )
    if configured is not None and configured.selected() == default_spec:
        return configured.specs
    return (default_spec,)


@dataclass(frozen=True, slots=True)
class _ExecuteWorkspaceFingerprint:
    head: str | None
    entries: tuple[tuple[str, str], ...]
    status: str = ""
    error: str | None = None


def _capture_execute_workspace_fingerprint(root: Path) -> _ExecuteWorkspaceFingerprint:
    """Capture enough git state to prove a failed executor made no source change."""

    snapshot, snapshot_error = _capture_git_status_snapshot_recursive(root)
    try:
        head_result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        status_result = subprocess.run(
            ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return _ExecuteWorkspaceFingerprint(
            None,
            tuple(sorted(snapshot.items())),
            error=snapshot_error or f"git_fingerprint_failed:{type(exc).__name__}",
        )
    head = head_result.stdout.strip() if head_result.returncode == 0 else None
    error = snapshot_error
    if head is None:
        error = error or "git_head_unavailable"
    if status_result.returncode != 0:
        error = error or "git_status_unavailable"
    return _ExecuteWorkspaceFingerprint(
        head,
        tuple(sorted(snapshot.items())),
        status_result.stdout,
        error,
    )


def _run_execute_worker_with_configured_fallback(
    *,
    root: Path,
    plan_dir: Path,
    state: PlanState,
    args: argparse.Namespace,
    agent: str,
    mode: str,
    refreshed: bool,
    model: str | None,
    effort: str | None,
    resolved_model: str | None,
    prompt_override: str | None,
    configured_specs: tuple[str, ...],
    batch_number: int,
    wbc_dispatch: Any = None,
) -> tuple[WorkerResult, str, str, bool]:
    """Advance execute only after a retryable, side-effect-free provider outage."""

    attempted_specs: list[str] = [configured_specs[0]]
    failed_reasons: list[str] = []
    fallback_trigger: str | None = None
    current_agent = agent
    current_mode = mode
    current_refreshed = refreshed
    current_model = model
    current_effort = effort
    current_resolved_model = resolved_model

    for attempt_index, selected_spec in enumerate(configured_specs):
        if attempt_index:
            current_agent, current_mode, current_model = _resolve_tier_spec(
                args,
                selected_spec,
            )
            current_effort = parse_agent_spec(selected_spec).effort
            current_resolved_model = current_model
            current_refreshed = True

        before = _capture_execute_workspace_fingerprint(root)
        rendered_prompt = _render_execute_prompt_for_dispatch(
            agent=current_agent,
            state=state,
            plan_dir=plan_dir,
            root=root,
            model=current_model,
            resolved_model=current_resolved_model,
            prompt_override=prompt_override,
        )
        resolved = AgentMode(
            agent=current_agent,
            mode=current_mode,
            refreshed=current_refreshed,
            model=current_model,
            effort=current_effort,
            resolved_model=current_resolved_model,
        )
        try:
            return worker_module.run_step_with_worker(
                "execute",
                state,
                plan_dir,
                args,
                root=root,
                resolved=resolved,
                prompt_override=rendered_prompt,
                wbc_dispatch=wbc_dispatch,
                worker_options={"_suppress_ambient_agent_fallback": True},
                ledger_step_label=f"batch_{batch_number}",
                ledger_selected_spec=selected_spec,
                ledger_configured_specs=configured_specs,
                ledger_attempt_index=attempt_index,
                ledger_attempted_specs=attempted_specs,
                ledger_failed_attempt_reasons=failed_reasons,
                ledger_fallback_trigger=fallback_trigger,
            )
        except CliError as error:
            classification = classify_retryability(
                {
                    "code": error.code,
                    "message": str(error),
                    "status_code": error.extra.get("status_code"),
                    "retryable": error.extra.get("retryable"),
                }
            )
            next_index = attempt_index + 1
            if (
                next_index >= len(configured_specs)
                or not is_retryable_classification(classification)
                or provider_family(configured_specs[next_index])
                == provider_family(selected_spec)
            ):
                raise
            after = _capture_execute_workspace_fingerprint(root)
            if before.error or after.error or before != after:
                raise CliError(
                    "execute_fallback_unsafe",
                    "Retryable execute provider failure could not be handed off "
                    "because the workspace was changed or could not be proven unchanged.",
                    extra={
                        "failed_spec": selected_spec,
                        "next_spec": configured_specs[next_index],
                        "failure_class": classification,
                        "before_error": before.error,
                        "after_error": after.error,
                    },
                ) from error
            failed_reasons.append(classification)
            fallback_trigger = classification
            attempted_specs.append(configured_specs[next_index])
            next_agent, next_mode, next_model = _resolve_tier_spec(
                args,
                configured_specs[next_index],
            )
            from arnold_pipelines.megaplan.workers._impl import (
                _patch_active_step_fallback_metadata,
            )

            _patch_active_step_fallback_metadata(
                plan_dir,
                state,
                {
                    "configured_specs": configured_specs,
                    "attempt_index": next_index,
                    "attempted_specs": tuple(attempted_specs),
                    "failed_attempt_reasons": tuple(failed_reasons),
                    "fallback_trigger": fallback_trigger,
                },
                agent=next_agent,
                mode=next_mode,
                model=next_model,
            )
            active_step = state.get("active_step")
            if isinstance(active_step, dict):
                active_step.update(
                    fallback_observability_fields(
                        configured_specs,
                        attempt_index=next_index,
                        attempted_specs=attempted_specs,
                        failed_attempt_reasons=failed_reasons,
                        fallback_trigger=fallback_trigger,
                    )
                )
                active_step.update(
                    {"agent": next_agent, "mode": next_mode, "model": next_model}
                )

    raise AssertionError("configured execute fallback loop exhausted unexpectedly")


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


PRIOR_RESULT_ENVELOPES_KEY = "prior_result_envelopes"
ACCEPTED_RECEIPT_STATUSES: frozenset[str] = frozenset({"done", "completed", "skipped"})


def _persisted_envelope_dict_subject(envelope: Mapping[str, Any]) -> str | None:
    attempt = envelope.get("attempt")
    subject = attempt.get("subject_id") if isinstance(attempt, Mapping) else None
    if isinstance(subject, str) and subject.strip():
        return subject.strip()
    claim = envelope.get("claim")
    subject = claim.get("subject_id") if isinstance(claim, Mapping) else None
    if isinstance(subject, str) and subject.strip():
        return subject.strip()
    return None


def _persisted_envelope_dict_ordinal(envelope: Mapping[str, Any]) -> int:
    attempt = envelope.get("attempt")
    ordinal = attempt.get("ordinal") if isinstance(attempt, Mapping) else None
    return ordinal if isinstance(ordinal, int) else 0


def _persisted_envelope_dict_status(envelope: Mapping[str, Any]) -> str | None:
    evidence = envelope.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        return None
    head = evidence[0]
    if not isinstance(head, Mapping):
        return None
    payload = head.get("payload")
    result = payload.get("result") if isinstance(payload, Mapping) else None
    status = result.get("status") if isinstance(result, Mapping) else None
    return status if isinstance(status, str) else None


def _persisted_envelope_dict_matches_identity(
    envelope: Mapping[str, Any], identity: DispatchIdentity
) -> bool:
    dispatch = envelope.get("dispatch")
    if not isinstance(dispatch, Mapping):
        return False
    try:
        return DispatchIdentity.from_dict(dispatch).digest() == identity.digest()
    except Exception:
        return False


def _stamp_result_envelopes(
    payload: dict[str, Any],
    *,
    identity: DispatchIdentity,
    artifact_path: Path,
) -> tuple[ResultEnvelope, ...]:
    """Attach worker-result authority echoes built from persisted dispatch.

    Receipts are append-only across fences: when a later fence (N+1) re-stamps
    the same checkpoint, fence-N envelopes are moved into
    ``PRIOR_RESULT_ENVELOPES_KEY`` so they remain byte-addressable by their
    stable ``attempt_id`` while ``RESULT_ENVELOPES_KEY`` keeps only envelopes
    bound to the current dispatch identity (so the authority resolver stays a
    single-identity proof).  Ordinals continue from the highest persisted value
    so attempt addresses never collide.  A subject that already holds an
    *accepted* receipt (done/completed/skipped) is never re-stamped — valid
    accepted work is not re-executed and its receipt is never overwritten.
    """

    source = str(artifact_path)
    prior_store = payload.get(PRIOR_RESULT_ENVELOPES_KEY)
    if not isinstance(prior_store, list):
        prior_store = []
    current_existing: list[dict[str, Any]] = []
    carried_prior: list[dict[str, Any]] = []
    for store in (payload.get(RESULT_ENVELOPES_KEY), prior_store):
        if not isinstance(store, list):
            continue
        for envelope in store:
            if not isinstance(envelope, Mapping):
                continue
            if _persisted_envelope_dict_matches_identity(envelope, identity):
                current_existing.append(dict(envelope))
            else:
                carried_prior.append(dict(envelope))

    all_persisted = current_existing + carried_prior
    next_ordinal = max(
        (_persisted_envelope_dict_ordinal(env) for env in all_persisted),
        default=0,
    ) + 1
    accepted_subjects = {
        _persisted_envelope_dict_subject(env)
        for env in all_persisted
        if _persisted_envelope_dict_status(env) in ACCEPTED_RECEIPT_STATUSES
    }
    accepted_subjects.discard(None)

    new_envelopes: list[ResultEnvelope] = []
    skipped_reexecutions: list[str] = []

    task_entries = payload.get("task_updates")
    if isinstance(task_entries, list):
        for entry in task_entries:
            if not isinstance(entry, dict):
                continue
            task_id = entry.get("task_id")
            if isinstance(task_id, str) and task_id in accepted_subjects:
                skipped_reexecutions.append(task_id)
                continue
            try:
                envelope = _task_result_envelope(
                    identity=identity,
                    entry=entry,
                    ordinal=next_ordinal,
                    source=source,
                )
            except ContractError as error:
                entry["authority_generation_error"] = str(error)
                continue
            if envelope is None:
                continue
            next_ordinal += 1
            entry["authority"] = _result_authority_echo(envelope)
            new_envelopes.append(envelope)

    sense_check_entries = payload.get("sense_check_acknowledgments")
    if isinstance(sense_check_entries, list):
        for entry in sense_check_entries:
            if not isinstance(entry, dict):
                continue
            sense_check_id = entry.get("sense_check_id")
            if isinstance(sense_check_id, str) and sense_check_id in accepted_subjects:
                skipped_reexecutions.append(sense_check_id)
                continue
            try:
                envelope = _sense_check_result_envelope(
                    identity=identity,
                    entry=entry,
                    ordinal=next_ordinal,
                    source=source,
                )
            except ContractError as error:
                entry["authority_generation_error"] = str(error)
                continue
            if envelope is None:
                continue
            next_ordinal += 1
            entry["authority"] = _result_authority_echo(envelope)
            new_envelopes.append(envelope)

    current_dicts = current_existing + [env.to_dict() for env in new_envelopes]
    payload[RESULT_ENVELOPES_KEY] = current_dicts
    if carried_prior or PRIOR_RESULT_ENVELOPES_KEY in payload:
        payload[PRIOR_RESULT_ENVELOPES_KEY] = carried_prior
    if skipped_reexecutions:
        payload.setdefault("append_only_attempts", {})["skipped_reexecutions"] = sorted(
            set(skipped_reexecutions)
        )
    return tuple(new_envelopes)


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
        # Stale pre-contract S4 artifacts (written before the versioned
        # batch_scope / dispatch_identity contract landed) lack the fields the
        # authority validator requires; replaying them only produces
        # quarantine noise and stale evidence. Silently exclude them. Legacy
        # flat execution_batch_*.json artifacts are NOT pruned for lacking S4
        # fields — they predate the S4 layout by design.
        is_s4_artifact = (
            artifact_path.parent.parent.name == "execute_batches"
            and re.fullmatch(r"batch_\d+", artifact_path.parent.name) is not None
            and re.fullmatch(r"tasks_[^.]+\.json", artifact_path.name) is not None
        )
        if is_s4_artifact and isinstance(payload, dict):
            scope = payload.get(BATCH_SCOPE_KEY)
            versioned_scope = (
                isinstance(scope, dict)
                and isinstance(scope.get("schema_version"), int)
                and not isinstance(scope.get("schema_version"), bool)
            )
            if not versioned_scope or not isinstance(
                payload.get(DISPATCH_IDENTITY_KEY), dict
            ):
                log.info("ignoring stale pre-contract S4 artifact %s", artifact_path)
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
            # preserve_accepted=True: an authority-adopted task (blocked or
            # pending promoted to done by _adopt_authority_completed_blocked_
            # tasks) must NOT be demoted back to its stale pre-adopt status
            # when the proven artifact is replayed on resume (grok consult,
            # astrid m1 batch-22): replay with preserve_accepted=False demoted
            # adopted T41 to pending, re-derived its incomplete-record
            # deviation, and reopened the quality-gate circuit every execute
            # despite a clean 43/43-done finalize.
            preserve_accepted=True,
            require_dispatch_wbc=False,
            # replay_proven=True: the artifact's dispatch identity is its own
            # accepted wave (coordinator attempt id / fence token), not the
            # current resume run's. Bypass ONLY the temporal coordinator/fence
            # comparison; plan revision, prerequisite, worker, echo, evidence,
            # and CAS validation stay enforced. (occurrence 0ae19cc17afd)
            replay_proven=True,
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
) -> None:
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
            return

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
    except Exception:
        log.warning(
            "Batch boundary receipt emission failed for %s", boundary_id, exc_info=True
        )


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


def _reconcile_prompt_override(
    plan_dir: Path,
    batch_prompt: str | None,
) -> str | None:
    """Render the P6 reconcile executor prompt when this plan carries the marker.

    The chain writes ``reconcile_inputs.json`` into a ``kind: reconcile``
    milestone's plan dir at init (rubric docs + ``git log --first-parent`` +
    candidate commits + target branch).  When present, the execute step is a
    SELECTION task whose authoritative output is the JSON SHA list
    (``selected_shas`` + ``verification_evidence``) — the generic batch
    prompt cannot carry that contract, so the reconcile prompt replaces it.
    Returns ``batch_prompt`` unchanged when the marker is absent or unusable
    (fail-open on marker problems: the brief still instructs selection).
    """
    if batch_prompt is None:
        return None
    inputs_path = plan_dir / "reconcile_inputs.json"
    if not inputs_path.is_file():
        return batch_prompt
    try:
        from arnold_pipelines.megaplan.prompts.execute import render_reconcile_prompt

        inputs = json.loads(inputs_path.read_text(encoding="utf-8"))
        if not isinstance(inputs, dict):
            return batch_prompt
        rubric_docs = inputs.get("rubric_docs")
        candidate_commits = inputs.get("candidate_commits")
        first_parent_log = inputs.get("first_parent_log")
        target_branch = inputs.get("target_branch")
        # Shape-validate the marker payload: a malformed marker must fall
        # back to the generic prompt, never render garbage (e.g. iterating a
        # string rubric_docs character-by-character).
        if not isinstance(rubric_docs, list) or not all(
            isinstance(doc, str) for doc in rubric_docs
        ):
            return batch_prompt
        if not isinstance(candidate_commits, list) or not all(
            isinstance(commit, dict) for commit in candidate_commits
        ):
            return batch_prompt
        if not isinstance(first_parent_log, str):
            return batch_prompt
        if not isinstance(target_branch, str) or not target_branch.strip():
            target_branch = "main"
        return render_reconcile_prompt(
            rubric_docs=rubric_docs,
            first_parent_log=first_parent_log,
            candidate_commits=candidate_commits,
            target_branch=target_branch,
        )
    except Exception:  # noqa: BLE001 - marker problems never break execute
        return batch_prompt


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


def _weight_aware_max_tasks_per_batch(
    base: int,
    tasks: Iterable[Mapping[str, Any]],
) -> int:
    """Shrink the batch for heavy tasks so one worker can finish it.

    The execute worker runs under a fixed tool-iteration budget (Hermes
    max_turns, default 90). A batch whose tasks each need many tool calls
    (implementation + multiple test runs) exhausts that budget mid-batch: the
    worker dies, no authority envelopes are stamped, the pending frontier
    never advances, and resume restarts from the top (astrid m2 reap loop,
    2026-08-16 — 5-task batches of 9-12min tasks never completed; mega m3's
    2-task batches of 3-4min tasks completed cleanly).

    Heavy tasks (estimated_minutes >= 8 or complexity >= 6) batch at most 2;
    light tasks keep the configured default. This preserves the fast path for
    simple work and prevents guaranteed worker-budget exhaustion for heavy
    work, without raising the worker cap (which would mask the underlying
    budget mismatch).
    """
    base = max(1, int(base))
    if base <= 1:
        return base
    try:
        tasks_list = list(tasks)
    except TypeError:
        return base
    if not tasks_list:
        return base
    heavy = sum(
        1
        for task in tasks_list
        if isinstance(task, Mapping)
        and (
            (isinstance(task.get("estimated_minutes"), (int, float)) and task["estimated_minutes"] >= 8)
            or (isinstance(task.get("complexity"), (int, float)) and task["complexity"] >= 6)
        )
    )
    if heavy >= 1 and len(tasks_list) >= 2:
        return min(base, 2)
    return base


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
    plan_dir: Path | None = None,
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
    acked_in_finalize = {
        str(sense_check.get("id"))
        for sense_check in finalize_data.get("sense_checks", [])
        if sense_check.get("id") in active_sense_check_ids
        and str(sense_check.get("executor_note", "")).strip()
    }
    acked_in_batches: set[str] = set()
    if plan_dir is not None:
        from arnold_pipelines.megaplan._core import list_all_batch_artifacts

        for batch_path in list_all_batch_artifacts(plan_dir):
            try:
                payload = json.loads(batch_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError, UnicodeDecodeError, ValueError):
                continue
            if not isinstance(payload, dict):
                continue
            for ack in payload.get("sense_check_acknowledgments", []) or []:
                if not isinstance(ack, dict):
                    continue
                sc_id = ack.get("sense_check_id")
                note = ack.get("executor_note")
                if (
                    isinstance(sc_id, str)
                    and sc_id in active_sense_check_ids
                    and isinstance(note, str)
                    and note.strip()
                ):
                    acked_in_batches.add(sc_id)
    acknowledged_ids = acked_in_finalize | acked_in_batches
    acknowledged_checks = sum(
        1
        for sc_id in active_sense_check_ids
        if sc_id in acknowledged_ids
    )
    return (
        tracked_tasks,
        len(active_task_ids),
        acknowledged_checks,
        len(active_sense_check_ids),
    )


def build_blocking_reasons(
    *,
    tracked_tasks: int,
    total_tasks: int,
    acknowledged_checks: int,
    total_checks: int,
    missing_task_evidence: list[str],
    timeout_reason: str | None = None,
    payload: Mapping[str, Any] | None = None,
) -> list[str]:
    reasons: list[str] = []
    # P6 reconcile selection envelope: a read-only reconcile selector emits the
    # authoritative selection JSON (top-level selected_shas +
    # verification_evidence) instead of the generic batch report; the
    # selection IS the batch's completion evidence, so the per-task tracking
    # and sense-check acknowledgment gates must not block it (occurrence
    # 47671addc195 — without this the milestone stranded blocked with
    # "N/M tasks have no executor update" despite a complete selection).
    selection_complete = bool(
        isinstance(payload, Mapping)
        and (
            "selected_shas" in payload or "verification_evidence" in payload
        )
    )
    if not selection_complete:
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


def _pending_left_behind_reason(task_ids: Iterable[str]) -> str | None:
    pending_ids = sorted({task_id for task_id in task_ids if task_id})
    if not pending_ids:
        return None
    return (
        "task(s) remained non-complete after their execute batch: "
        f"{', '.join(pending_ids)}. Stopping before dispatching later "
        "batches; retry execute."
    )


def _drop_resolved_quality_blocking_reasons(
    blocking_reasons: list[str],
    *,
    state: PlanState | None,
) -> list[str]:
    """Drop blocking reasons whose quality blocker the operator already
    resolved as non-terminal debt.

    The execute phase and the auto driver consume ``blocking_reasons`` to
    decide quality-gate blocking, but only ``override recover-blocked``
    consulted ``quality_gate_resolutions``.  That asymmetry meant an operator
    ``accepted_with_debt`` resolution (the designed debt-acceptance seam) could
    never clear a recurring execute deviation: the plan looped
    blocked -> recover-blocked -> finalized -> execute -> same deviation ->
    circuit open forever.  Honor the recorded resolution here so a resolved
    deviation no longer re-blocks execute while the debt record stays durable
    in state meta.
    """

    if not blocking_reasons or not isinstance(state, dict):
        return list(blocking_reasons)
    meta = state.get("meta") if isinstance(state.get("meta"), dict) else {}
    raw_resolutions = meta.get("quality_gate_resolutions", [])
    resolutions = latest_quality_resolutions(
        raw_resolutions if isinstance(raw_resolutions, list) else []
    )
    if not resolutions:
        return list(blocking_reasons)
    kept: list[str] = []
    for reason in blocking_reasons:
        try:
            deviation = Deviation.from_string(str(reason))
        except Exception:
            deviation = None
        blocker_id = (
            quality_blocker_id(deviation)
            if deviation is not None
            else None
        )
        event = resolutions.get(blocker_id) if blocker_id is not None else None
        if event is None:
            kept.append(reason)
            continue
        resolution = event.get("resolution")
        if is_non_terminal_quality_resolution(resolution, deviation_active=True):
            log.info(
                "dropping resolved quality blocking reason %r (blocker %s "
                "resolved %s)",
                reason,
                blocker_id,
                resolution,
            )
            continue
        kept.append(reason)
    return kept


def _aggregate_terminal_deviations(
    aggregate_payload: dict[str, Any],
    *,
    timeout_recovery: dict[str, Any] | None,
    execution_audit: dict[str, Any],
    blocked_task_ids: set[str],
) -> list[str]:
    deviations: list[str] = []
    for deviation in aggregate_payload.get("deviations", []):
        if is_transient_execute_advisory(deviation):
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
    configured_specs: tuple[str, ...] | None = None,
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
    wbc_dispatch = build_execute_batch_dispatch_spec(
        plan_dir=plan_dir,
        state=state,
        dispatch_identity=dispatch_identity,
        batch_number=batch_number,
        batch_task_ids=batch_task_ids,
        batch_sense_check_ids=batch_sense_check_ids,
    )
    if is_prose_mode(state):
        before_snapshot: dict[str, str] = {}
        before_error: str | None = None
        before_line_counts: dict[str, int] = {}
    else:
        before_snapshot, before_error = capture_git_status_snapshot_fn(project_dir)
        before_line_counts = capture_before_line_counts(project_dir, before_snapshot.keys())
    selected_default_spec = format_selected_spec(agent, model, effort) or agent
    configured_specs = configured_specs or (selected_default_spec,)
    selected = parse_agent_spec(configured_specs[0])
    am_for_worker = AgentMode(
        agent=agent,
        mode=mode,
        refreshed=refreshed,
        model=selected.model,
        effort=selected.effort,
        resolved_model=resolved_model if resolved_model is not None else selected.model,
    )
    # M8A Step 13 — Verify-only repair adoption at the execute action
    # boundary.  Runs BEFORE repair/worker dispatch.  Rereads current Run
    # Authority grant/fence, Custody lease/epoch, and required WBC
    # conditions through the existing action_validator seam; on exact match
    # emits adoption evidence + a ``repair_verify`` work-ledger event and
    # (under canary promotion) may skip replay; on mismatch quarantines the
    # receipt and continues normal execution without rewriting immutable
    # attempts.  Shadow/report-only by default.
    try:
        _repair_adoption_summary = _run_repair_adoption_check(
            plan_dir=plan_dir,
            finalize_data=finalize_data,
            batch_task_ids=batch_task_ids,
        )
    except Exception as exc:  # pragma: no cover - adoption must never crash dispatch
        log.warning("repair adoption check failed: %s: %s", type(exc).__name__, exc)
        _repair_adoption_summary = {
            "contract_type": "repair_adoption_summary",
            "error": f"{type(exc).__name__}: {exc}",
            "evaluated": [],
            "adopted_count": 0,
            "quarantined_count": 0,
            "skip_replay": False,
        }
    # M8A T18 — track dispatch start time for queue-duration measurement.
    # M8A T10 - run deterministic harness validation jobs outside model dispatch.
    _is_final_batch_flag = False
    _bn = locals().get("batch_number")
    _bt = locals().get("batches_total")
    if isinstance(_bn, int) and isinstance(_bt, int) and _bn >= _bt:
        _is_final_batch_flag = True
    # Harness validation is an execution admission gate.  Let its typed
    # failures propagate so productive dispatch cannot continue after a
    # malformed job or an unexpected deterministic-suite result.
    _pre_dispatch_validation_results = _run_batch_validation_jobs(
        plan_dir=plan_dir,
        project_dir=project_dir,
        finalize_data=finalize_data,
        batch_task_ids=batch_task_ids,
        is_final_batch=_is_final_batch_flag,
        # Admission-only: the execute admission gate may accept pytest exit
        # code 1 when every failed node ID is a plan-baseline-known failure.
        # Deferred/final rechecks and sweeps never opt into subtraction.
        admission=True,
    )
    _dispatch_start = time.monotonic()
    # M8A T16 - under opt-in canary enforcement, when repair adoption
    # adopted every task in this batch, skip the worker replay/dispatch path.
    _adopted_ids: set[str] = set()
    if _repair_adoption_summary.get("skip_replay"):
        for _e in _repair_adoption_summary.get("evaluated", []) or []:
            if (
                isinstance(_e, dict)
                and str(_e.get("outcome") or "").lower() == "adopt"
            ):
                _tid = _e.get("task_id")
                if isinstance(_tid, str):
                    _adopted_ids.add(_tid)
    if _adopted_ids and batch_task_ids and set(batch_task_ids) == _adopted_ids:
        log.info(
            "M8A repair adoption: skipping worker dispatch for %d adopted task(s): %s",
            len(_adopted_ids),
            sorted(_adopted_ids),
        )
        import types as _types
        _successors = {
            row["task_id"]: row.get("successor_claim")
            for row in _repair_adoption_summary.get("evaluated", [])
            if isinstance(row, dict) and isinstance(row.get("task_id"), str)
        }
        _task_records = {
            task["id"]: task
            for task in finalize_data.get("tasks", [])
            if isinstance(task, dict) and isinstance(task.get("id"), str)
        }
        _adopted_updates = []
        for _task_id in batch_task_ids:
            _task = _task_records[_task_id]
            _successor = _successors.get(_task_id)
            _verification_commands = (
                list(_successor.get("verification_commands", []))
                if isinstance(_successor, Mapping)
                else list(_task.get("commands_run", []))
            )
            _adopted_updates.append(
                {
                    "task_id": _task_id,
                    "status": "done",
                    "executor_notes": (
                        "Recovered landed implementation through an authority-valid "
                        "verification-only successor claim; implementation body was not replayed."
                    ),
                    "files_changed": list(_task.get("files_changed", [])),
                    "commands_run": _verification_commands,
                    "evidence_files": list(_task.get("evidence_files", [])),
                    "scope_recovery_claim_id": (
                        _successor.get("claim_id")
                        if isinstance(_successor, Mapping)
                        else None
                    ),
                }
            )
        worker = _types.SimpleNamespace(
            payload={
                "task_updates": _adopted_updates,
                "sense_check_acknowledgments": [
                    {
                        "sense_check_id": sense_id,
                        "executor_note": "Preserved by verification-only successor recovery.",
                    }
                    for sense_id in batch_sense_check_ids
                ],
                "deviations": [],
            },
            model_actual=(resolved_model or model),
            skipped_replay=True,
            auth_metadata=None,
            attempt_index=0,
            duration_ms=0,
            cost_usd=0.0,
            cost_pricing=None,
            total_tokens=0,
            raw_output="",
            trace_output=None,
            session_id=None,
            worker_channel="repair_adoption",
            auth_channel=None,
        )
    else:
        worker, agent, mode, refreshed = _run_execute_worker_with_configured_fallback(
            root=root,
            plan_dir=plan_dir,
            state=state,
            args=args,
            agent=agent,
            mode=mode,
            refreshed=refreshed,
            model=model,
            effort=effort,
            resolved_model=resolved_model if resolved_model is not None else model,
            prompt_override=prompt_override,
            configured_specs=configured_specs,
            batch_number=batch_number,
            wbc_dispatch=wbc_dispatch,
        )
        selected = parse_agent_spec(configured_specs[worker.attempt_index])
        am_for_worker = AgentMode(
            agent=agent,
            mode=mode,
            refreshed=refreshed,
            model=selected.model,
            effort=selected.effort,
            resolved_model=worker.model_actual or selected.model,
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
    # ── M8A T18 — Work-class event emission ──────────────────────────
    # Emit productive / queue / unavailable_reason work-ledger events for
    # this batch's worker dispatch.  Every measure is attributed to an
    # explicit class or an ``unavailable_reason`` — never defaulted to
    # zero or silently dropped.
    _dispatch_end = time.monotonic()
    _dispatch_duration_ms = int((_dispatch_end - _dispatch_start) * 1000)
    try:
        from arnold_pipelines.megaplan.observability.work_ledger import (
            emit_productive,
            emit_queue,
            emit_unavailable_reason,
        )
        # Emit one ``productive`` event per batch task.  The worker ran
        # on the whole batch collectively, so we attribute the batch-level
        # metrics to each task.  Individual per-task breakdown is not
        # available from worker-level metrics; this is flagged as a
        # known limitation via unavailable_reason when relevant.
        _w = worker
        _tokens = getattr(_w, "total_tokens", 0) or 0
        _cost = getattr(_w, "cost_usd", 0.0) or 0.0
        _calls = 1  # one worker dispatch = one model call for this batch
        _duration = getattr(_w, "duration_ms", 0) or 0
        _cost_priced = bool(getattr(_w, "cost_pricing", None))
        _model_actual = getattr(_w, "model_actual", None) or "unknown"
        for _task_id in batch_task_ids:
            emit_productive(
                plan_dir,
                task_id=_task_id,
                work_class="batch_execute",
                duration_ms=_duration,
                tokens=_tokens if _tokens > 0 else None,
                cost_usd=_cost if (_cost > 0 or _cost_priced) else None,
                model_calls=_calls,
                batch_number=batch_number,
                model_actual=_model_actual,
                dispatch_duration_ms=_dispatch_duration_ms,
            )
            # Emit unavailable_reason when cost/token data is genuinely
            # unavailable (not priced, not reported by the provider).
            if not _cost_priced and _cost == 0.0:
                emit_unavailable_reason(
                    plan_dir,
                    task_id=_task_id,
                    measure="cost_usd",
                    reason="provider did not report pricing; cost_pricing is None or empty",
                    batch_number=batch_number,
                )
            if _tokens == 0:
                emit_unavailable_reason(
                    plan_dir,
                    task_id=_task_id,
                    measure="tokens",
                    reason="worker did not report token usage",
                    batch_number=batch_number,
                )
        # Emit a queue event measuring time spent from admission to dispatch
        # completion.
        if _dispatch_duration_ms > 0:
            emit_queue(
                plan_dir,
                task_id=batch_task_ids[0] if batch_task_ids else "unknown",
                duration_ms=_dispatch_duration_ms,
                queue_reason="worker_dispatch_wait",
                batch_number=batch_number,
            )
    except Exception as _exc:  # pragma: no cover — ledger must never crash dispatch
        log.warning(
            "work-ledger productive event emission failed for batch %d: %s: %s",
            batch_number,
            type(_exc).__name__,
            _exc,
        )
    payload = _capture_execute_payload(
        agent=agent,
        model=model,
        resolved_model=resolved_model,
        payload=dict(worker.payload),
    )
    dispatch_summary = dispatch_wbc_summary(
        auth_metadata=(
            worker.auth_metadata
            if isinstance(worker.auth_metadata, Mapping)
            else None
        ),
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
    scope = _stamp_batch_scope(
        payload,
        batch_number=batch_number,
        task_ids=batch_task_ids,
        sense_check_ids=batch_sense_check_ids,
    )
    identity = _stamp_dispatch_metadata(
        payload,
        plan_dir=plan_dir,
        state=state,
        scope=scope,
        finalize_data=finalize_data,
    )
    _stamp_result_envelopes(
        payload,
        identity=identity,
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
    # Persist the merged payload BEFORE the authority adopt so this batch's
    # accepted result envelopes are on disk for the kernel projection (grok
    # consult, astrid deferred-revalidation wedge): the adopt previously only
    # saw PRIOR batches' envelopes, so a this-batch blocked task kept the
    # deferred revalidation refusing (task_result_blocked_by_post_merge_policy)
    # and every resume advanced exactly one batch before blocking again.  The
    # late write below still produces the complete artifact (audit/deviation
    # enriched); this early write is the merge-complete crash-recovery point.
    atomic_write_json(batch_artifact_path, payload)
    # Adopt authority-completed blocked tasks BEFORE the deferred-selector
    # revalidation gate: a task whose accepted-attempt kernel authority is
    # dependency-closed (done) must not keep its stale `blocked` status, or a
    # deferred narrow recheck referencing that task refuses with
    # task_result_blocked_by_post_merge_policy.  The kernel projection (not the
    # live payload's pre-policy accepted flag) is the source of truth; a task
    # only grant-accepted this turn (policy not yet closed) stays blocked and
    # the gate keeps refusing — that is the intentional post-merge policy.
    authority_adopted_ids = _adopt_authority_completed_blocked_tasks(
        finalize_data,
        plan_dir=plan_dir,
        root=root,
        state=state,
    )
    if authority_adopted_ids:
        _publish_execute_finalize(
            plan_dir,
            finalize_data,
            operation="adopt-authority-completed-blocked",
            state=state,
        )
        log.info(
            "authority-adopt: promoted %d authority-completed blocked task(s) to done: %s",
            len(authority_adopted_ids),
            ", ".join(authority_adopted_ids),
        )
    # A narrow validation whose selector was a declared task output is not a
    # terminal pass.  Re-check it only after the task's *accepted* result
    # envelope proves that the task created the exact path.  This keeps the
    # deferred state from becoming a silent bypass while also preventing a
    # pre-dispatch worker from being gated by its own future output.
    _deferred_validation_results = _rerun_deferred_selector_validation_jobs(
        plan_dir=plan_dir,
        project_dir=project_dir,
        finalize_data=finalize_data,
        batch_task_ids=batch_task_ids,
        pre_dispatch_results=_pre_dispatch_validation_results,
        payload=payload,
        state=state,
    )
    if _deferred_validation_results:
        payload.setdefault("validation_results", []).extend(
            _deferred_validation_results
        )
    # Final-batch deferred sweep: every admitted task has now run, so any
    # narrow job whose selector was missing at its own pre-dispatch can be
    # re-attempted (selector exists -> run), or fails closed (still missing ->
    # undeclared or declared-but-never-created).  Runs BEFORE execute success
    # is projected so a broken write-set contract blocks, never silently
    # passes.
    if _is_final_batch_flag:
        _final_sweep_results = _sweep_persisted_deferred_selector_jobs(
            plan_dir=plan_dir,
            project_dir=project_dir,
            finalize_data=finalize_data,
            state=state,
        )
        if _final_sweep_results:
            payload.setdefault("validation_results", []).extend(
                _final_sweep_results
            )
        # Evidence-gated budget-debt acceptance (occurrence 927ad612eda8):
        # a cumulative max_seconds-only block whose FULL admitted selection
        # passes strict against the current merged tree is reconciled to
        # durable accepted_with_debt so TDD-style plans cannot wedge in
        # blocked_by_quality on a parametrized selector that can never fit
        # the cap.  Runs after the final deferred sweep (fresh strict
        # evidence) and before deviation/audit publication.
        _budget_debt_accepted = _accept_strictly_verified_test_budget_debt(
            plan_dir=plan_dir,
            project_dir=project_dir,
            finalize_data=finalize_data,
            payload=payload,
            deviations=deviations,
        )
        if _budget_debt_accepted:
            log.info(
                "final sweep: test-budget debt accepted with strict evidence "
                "for task(s): %s",
                ", ".join(_budget_debt_accepted),
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
    # The immutable batch artifact is the crash-recovery evidence.  Do not
    # publish an interim whole-document Finalize projection here; the execute
    # coordinator owns the single aggregate publication below.
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
        finalize_hash=(
            sha256_file(plan_dir / "finalize.json")
            if (plan_dir / "finalize.json").exists()
            else sha256_text(json.dumps(finalize_data, indent=2) + "\n")
        ),
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



_MAX_SERIAL_REWORK = 5
_BATCH_CIRCUIT: dict = {}


class _ReworkWaveError:
    """Lightweight error proxy for circuit advancement of review-rework waves (M8A T14)."""

    def __init__(self, message, *, code="review_quality_block", kind="quality_gate_blocked"):
        self.message = message
        self.code = code
        self.kind = kind
        self.error_kind = ""
        self.error_layer = ""
        self.extra: dict = {}


def _split_high_complexity(batches, finalize_data, *, max_tasks_per_batch):
    """Isolate complexity >=7 tasks into their own batches before worker dispatch (M8A T8)."""
    try:
        from arnold_pipelines.megaplan._core.io import split_high_complexity_batches
        return split_high_complexity_batches(
            batches, finalize_data, max_tasks_per_batch=max_tasks_per_batch
        )
    except Exception:
        return batches


def _guard_execute_batch_admission(finalize_data, state, *, plan_dir=None):
    """Reassert finalized task-graph admission at execute batch entry (M8A T7).

    Converts admission failures to a ``CliError`` with
    ``valid_next=['finalize','revise']`` so workers are never dispatched
    against a mutated or inadmissible post-finalize graph.

    M10 Step 7H-b: threads ``config`` (previously omitted — the shadow-feasibility
    bug) and the gate-step ``seed_epoch`` attestation into the verdict, and
    blocks v1/``None`` admission escapes so only fully-admitted v2 graphs reach
    worker dispatch.  The epoch protocol is only activated when the gate step
    actually produced a ``seed_epoch`` attestation; an absent key preserves
    backward-compat for pre-M10 plans.
    """
    from arnold_pipelines.megaplan.orchestration.task_feasibility import (
        assert_admitted_task_feasibility,
    )
    config = state.get("config") if isinstance(state, dict) else None
    epoch_kwargs: dict = {}
    if isinstance(state, dict) and state.get("seed_epoch") is not None:
        epoch_kwargs["current_epoch"] = state.get("seed_epoch")
    try:
        admission_report = assert_admitted_task_feasibility(
            finalize_data, config, **epoch_kwargs
        )
    except ValueError as exc:
        raise CliError(
            "finalized_task_graph_changed",
            str(exc),
            valid_next=["finalize", "revise"],
        ) from exc
    # Block v1/None admission escapes in the supported M10 dispatch path so
    # only fully-admitted v2 graphs reach worker dispatch.
    if admission_report is None:
        raise CliError(
            "finalized_task_graph_changed",
            "v1 task contract is not admitted by M10 dispatch; "
            "re-finalize under the v2 task contract before executing",
            valid_next=["finalize", "revise"],
        )


def _advance_batch_circuit(error, *, task_id="", attempt_id=""):
    """Advance a normalized circuit for a batch retry/rework decision (M8A T14).

    Applies ``classify_failure_class`` + ``normalize_failure_signature`` +
    ``circuit_transition`` and returns ``(new_state, decision, failure_class)``.
    """
    from arnold_pipelines.megaplan.orchestration.recovery_policy import (
        CircuitState,
        classify_failure_class,
        normalize_failure_signature,
        circuit_transition,
    )
    fclass = classify_failure_class(error)
    signature = normalize_failure_signature(
        fclass, error, task_id=task_id, attempt_id=attempt_id
    )
    key = f"{fclass}:{task_id}:{attempt_id}"
    current = _BATCH_CIRCUIT.get(key, CircuitState(failure_class=fclass))
    new_state, decision = circuit_transition(current, signature)
    _BATCH_CIRCUIT[key] = new_state
    return new_state, decision, fclass


def _legacy_validation_recovery_cursor_active(plan_dir: Path) -> bool:
    """True only for the exact blocked pre-dispatch validation recovery cursor."""
    try:
        state = json.loads((Path(plan_dir) / "state.json").read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return False
    if not isinstance(state, dict) or state.get("current_state") != "blocked":
        return False
    failure = state.get("latest_failure")
    if not isinstance(failure, dict) or failure.get("kind") != "pre_dispatch_validation_failed":
        return False
    metadata = failure.get("metadata")
    if not isinstance(metadata, dict) or metadata.get("error_code") != "invalid_validation_job":
        return False
    cursor = state.get("resume_cursor")
    return (
        isinstance(cursor, dict)
        and cursor.get("phase") == "execute"
        and cursor.get("retry_strategy") == "repair_validation_failure"
    )


def _persisted_validation_jobs_malformed(jobs: list[dict[str, Any]]) -> bool:
    """True when any persisted narrow job carries a command-shaped selector."""
    from arnold_pipelines.megaplan.orchestration.validation_jobs import (
        validate_narrow_selector_shape,
    )

    for job in jobs:
        if job.get("kind") != "narrow_recheck":
            continue
        selectors = job.get("selectors")
        if isinstance(selectors, list):
            for selector in selectors:
                if isinstance(selector, str) and not validate_narrow_selector_shape(
                    selector
                )[0]:
                    return True
    return False


def _project_legacy_validation_contract_for_recovery(
    *,
    plan_dir: Path,
    finalize_data: Mapping[str, Any],
    persisted_jobs: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Cursor-gated in-memory recovery projection for malformed legacy jobs.

    Returns ``None`` unless every precondition holds AND every effective
    narrow job still classifies READY or DEFERRED under the unchanged
    lifecycle ownership rules (fail closed).  Never rewrites plan artifacts.
    """
    if len(persisted_jobs) < 2:
        return None
    if not _legacy_validation_recovery_cursor_active(plan_dir):
        return None
    if not _persisted_validation_jobs_malformed(persisted_jobs):
        return None
    from arnold_pipelines.megaplan.orchestration.validation_jobs import (
        SELECTOR_INVALID,
        classify_selector_lifecycle,
        project_legacy_validation_contract,
    )

    projected = project_legacy_validation_contract(finalize_data)
    if projected is None:
        return None

    tasks = finalize_data.get("tasks")
    task_by_id: dict[str, Mapping[str, Any]] = {}
    if isinstance(tasks, list):
        for task in tasks:
            if isinstance(task, Mapping) and isinstance(task.get("id"), str):
                task_by_id[task["id"]] = task

    project_dir = finalize_data.get("_project_dir") or plan_dir
    all_declared_outputs = graph_declared_output_paths(finalize_data.get("tasks"))
    for job in projected["effective_jobs"]:
        if job.get("kind") != "narrow_recheck":
            continue
        task_id = job.get("task_id")
        task = task_by_id.get(task_id) if isinstance(task_id, str) else None
        lifecycle = classify_selector_lifecycle(
            project_dir=project_dir,
            job=job,
            task=task,
            all_declared_outputs=all_declared_outputs,
        )
        if lifecycle.status == SELECTOR_INVALID:
            # Fail closed: recovery must never admit a job the unchanged gate
            # would reject.
            return None

    original = projected.get("original_jobs", [])
    effective = projected.get("effective_jobs", [])
    try:
        original_sha = "sha256:" + hashlib.sha256(
            json.dumps(original, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        effective_sha = "sha256:" + hashlib.sha256(
            json.dumps(effective, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
    except (TypeError, ValueError):
        original_sha = ""
        effective_sha = ""
    return {
        "effective_jobs": effective,
        "original_jobs_sha256": original_sha,
        "effective_jobs_sha256": effective_sha,
        "excluded": projected.get("excluded", []),
    }


def _persist_validation_recovery_receipt(
    plan_dir: Path,
    projected: Mapping[str, Any],
) -> None:
    """Persist the additive execute recovery receipt (never touches finalize.json)."""
    try:
        verification_dir = Path(plan_dir) / "verification"
        verification_dir.mkdir(parents=True, exist_ok=True)
        receipt = {
            "schema": "megaplan.execute.validation_contract_recovery.v1",
            "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            **{k: v for k, v in projected.items() if k != "effective_jobs"},
            "effective_job_ids": [str(j.get("id") or "") for j in projected.get("effective_jobs", [])],
        }
        receipt_path = verification_dir / "validation_contract_recovery.json"
        tmp = receipt_path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        tmp.replace(receipt_path)
    except Exception:  # pragma: no cover - receipt persistence is best-effort
        logging.getLogger("megaplan.execute.batch").warning(
            "validation contract recovery receipt persistence failed",
            exc_info=True,
        )


def _validation_failure_ids(raw: object) -> list[str] | None:
    """Normalize baseline/failure payloads to canonical pytest node IDs.

    Accepts a list of plain node-ID strings or a list of records carrying a
    canonical ``node_id`` key.  Returns ``None`` (fail-closed) for null,
    empty, malformed, or partially-blank input so callers never subtract on
    ambiguous evidence.
    """
    if not isinstance(raw, list) or not raw:
        return None
    ids: list[str] = []
    for item in raw:
        if isinstance(item, str):
            node_id = item
        elif isinstance(item, Mapping) and isinstance(item.get("node_id"), str):
            node_id = item["node_id"]
        else:
            return None
        if not node_id.strip():
            return None
        ids.append(node_id)
    return ids


def _baseline_known_failures_only(
    *,
    exit_code: int | None,
    failed_test_ids: object,
    baseline_test_failures: object,
    collection_errors: object,
    timeout_reason: object,
    status: object,
) -> list[str] | None:
    """Return the baseline-known failure IDs to admit, or ``None`` to block.

    Pre-dispatch admission (``admission=True`` at the execute admission
    gate) accepts pytest exit code 1 ONLY when every observed failed node ID
    is a member of the plan's non-empty baseline.  Everything else fails
    closed: exit codes 2-5, runner errors, timeouts, collection errors, and
    any new failure keep the strict blocking path.  This is admission, not
    enforcement: the real ``exit_code`` and failure list stay in the
    evidence, and deferred/final rechecks never opt into subtraction.
    """
    if exit_code != 1:
        return None
    if status != "failed":
        return None
    if timeout_reason not in (None, ""):
        return None
    if collection_errors:
        return None
    baseline_ids = _validation_failure_ids(baseline_test_failures)
    observed_ids = _validation_failure_ids(failed_test_ids)
    if baseline_ids is None or observed_ids is None:
        return None
    if not baseline_ids or not observed_ids:
        return None
    if set(observed_ids) - set(baseline_ids):
        return None
    return sorted(set(observed_ids))


# ---------------------------------------------------------------------------
# No-new-failures delta lifecycle for narrow_recheck (occurrence a07166d38fbc)
#
# A pre-dispatch narrow_recheck that demands exit 0 on full-file selectors
# under a planner probe budget is a deterministic gate for suites whose
# selectors (a) exceed the probe budget or (b) contain environment-dependent
# failures that are not task regressions.  The task contract is "introduce no
# new failures vs the recorded baseline" with the authoritative verdict at
# post-execute verification — so the pre-dispatch run becomes a COMPLETE
# pre-execution envelope capture (fail closed on timeout/signal/collection
# errors/malformed output), and the pass/fail verdict moves to a post-adoption
# delta recheck that compares the merged state against that envelope.  The
# enforcement boundary moves from "all selected tests green before dispatch"
# to "selected files completely observed before dispatch AND no new failures
# after adoption" — real post-merge contradictions still block, authority IDs
# persist only on pass, and nothing is exempted.
# ---------------------------------------------------------------------------

NARROW_RECHECK_DELTA_ACCEPTANCE = "no_new_failures_delta"
PRE_ENVELOPE_CAPTURED = "pre_envelope_captured"
POST_DELTA_PASSED = "post_delta_passed"
POST_DELTA_FAILED = "post_delta_failed"
_PRE_ENVELOPE_ARTIFACT_SUFFIX = "_pre_envelope.json"
_POST_DELTA_ARTIFACT_SUFFIX = "_post_delta.json"


def _validation_comparison_ceiling(finalize_data: Mapping[str, Any]) -> int | None:
    """Derive the authoritative comparison ceiling for narrow-recheck runs.

    Prefers the plan's ``post_execute_suite`` budget (the authoritative
    full-suite ceiling); falls back to the largest validation-job budget.
    Returns ``None`` when no budget exists — callers must fail closed rather
    than silently falling back to the planner's probe value.
    """
    jobs = finalize_data.get("validation_jobs")
    if not isinstance(jobs, list):
        return None
    ceiling: int | None = None
    for job in jobs:
        if not isinstance(job, Mapping):
            continue
        ms = job.get("max_seconds") or job.get("timeout_seconds")
        if not isinstance(ms, (int, float)) or ms <= 0:
            continue
        if job.get("kind") == "post_execute_suite":
            return int(ms)
        if ceiling is None or int(ms) > ceiling:
            ceiling = int(ms)
    return ceiling


def _recompile_legacy_narrow_recheck_command(
    command: object,
    selectors: object,
) -> str | None:
    """Recompile a legacy compiled narrow-recheck command from validated selectors.

    Legacy compiled commands embed ``timeout <N>s pytest <selectors> [opts]``.
    The embedded GNU timeout duplicates the suite-runner deadline and is the
    deterministic 124 killer for suites whose planner probe budget is too
    small.  Rebuild a trusted pytest argv from the *validated structured
    selectors* — never string-edit or execute the persisted shell command.
    Returns ``None`` when the command is not the legacy embedded-timeout
    pytest shape or when the command's selectors drift from the structured
    selectors (fail closed — keep the original command).
    """
    if not isinstance(command, str) or not command.strip():
        return None
    if not isinstance(selectors, list) or not selectors:
        return None
    try:
        parts = shlex.split(command)
    except ValueError:
        return None
    if len(parts) < 3 or parts[0] != "timeout" or parts[2] != "pytest":
        return None
    selector_tokens: list[str] = []
    option_tokens: list[str] = []
    seen_selector = False
    for tok in parts[3:]:
        if tok.startswith("-"):
            option_tokens.append(tok)
        else:
            seen_selector = True
            selector_tokens.append(tok.strip("'\""))
    expected = {str(s).strip("'\"") for s in selectors}
    if not seen_selector or not selector_tokens or set(selector_tokens) != expected:
        return None
    rebuilt = "pytest " + " ".join(shlex.quote(str(s)) for s in selectors)
    if option_tokens:
        rebuilt = f"{rebuilt} " + " ".join(shlex.quote(t) for t in option_tokens)
    return rebuilt


def _narrow_recheck_delta_policy(job: Mapping[str, Any], command: object) -> bool:
    """True when a narrow_recheck job uses the no-new-failures delta lifecycle.

    Explicitly persisted by the v2 compiler (``acceptance_mode``), or derived
    for legacy jobs whose command carries the old embedded-timeout pytest
    shape.  Everything else keeps the strict exit-0 gate.
    """
    if job.get("kind") != "narrow_recheck":
        return False
    if job.get("acceptance_mode") == NARROW_RECHECK_DELTA_ACCEPTANCE:
        return True
    return (
        _recompile_legacy_narrow_recheck_command(command, job.get("selectors"))
        is not None
    )


def _pre_envelope_artifact_path(verification_dir: Path, job_id: str) -> Path:
    return verification_dir / f"validation_{job_id}{_PRE_ENVELOPE_ARTIFACT_SUFFIX}"


def _quarantine_pre_envelope_artifact_required(
    artifact: Path,
    *,
    job_id: str,
    reason: str,
) -> Path:
    """Atomically move a stale pre-envelope under ``verification/stale/``.

    This is the REQUIRED (fail-closed) recovery for the pre-dispatch drift
    gate: a completed pre-envelope whose selectors/command/source digest no
    longer matches the current tree must never be re-captured in place (the
    post-adoption delta would self-compare and mask new failures), but a hard
    raise with no in-code recovery wedges every TDD-style plan whose agent
    WIP (or the watchdog's own ledger appends) changes the digested tree
    between envelope capture and dispatch (occurrence 927ad612eda8: VJ27
    drift fired on every resume until an operator manually removed the stale
    artifact — twice).

    The stale artifact is preserved under a unique name so the audit trail
    survives; the job then re-runs normally and durably writes a fresh
    pre-envelope against the CURRENT tree.  On any move failure the gate
    fails closed and nothing is overwritten.
    """
    try:
        stale_dir = artifact.parent / "stale"
        stale_dir.mkdir(parents=True, exist_ok=True)
        target = stale_dir / (
            f"{artifact.stem}-stale-{time.time_ns()}-{os.getpid()}"
            f"-{id(artifact):x}{artifact.suffix}"
        )
        artifact.replace(target)
    except OSError as exc:
        raise CliError(
            "validation_job_failed",
            f"validation job {job_id} {reason}: could not quarantine stale "
            f"pre-envelope {artifact}",
            valid_next=["execute", "revise"],
            extra={
                "job_id": job_id,
                "reason": "pre_envelope_quarantine_failed",
                "artifact_path": str(artifact),
            },
        ) from exc
    return target


def _post_delta_artifact_path(verification_dir: Path, job_id: str) -> Path:
    return verification_dir / f"validation_{job_id}{_POST_DELTA_ARTIFACT_SUFFIX}"


def _current_source_digest(project_dir: Path) -> str | None:
    """Deterministic source-tree digest for the current tree.

    Reuses suite_runner's canonical ``_compute_code_hash`` (git ``ls-tree``
    primary, deterministic filesystem-hash fallback) so a stored envelope's
    ``code_hash`` can be compared with the CURRENT tree on resume.  Returns
    ``None`` only when the digest cannot be computed at all — callers must
    treat ``None`` as a mismatch and fail closed (never reuse an envelope
    against an unverifiable tree).
    """
    try:
        from arnold_pipelines.megaplan.orchestration.suite_runner import (
            _compute_code_hash,
        )

        return _compute_code_hash(Path(project_dir))
    except Exception:
        return None


# Engine-owned volatile ledger files (watchdog appends ~every few minutes).
# Tracked + continuously modified incident metadata — never a task
# deliverable.  Excluded from the worktree digest by explicit enumerated
# path so validation artifacts stay binding-valid across short windows
# (occurrence 927ad612eda8: D1 pre-envelope drift, D2 strict-binding
# acceptance).  See _current_worktree_digest.
_WORKTREE_DIGEST_EXCLUDED_RELATIVE_PATHS = frozenset(
    {
        ".megaplan/incident-ledger/events.jsonl",
        ".megaplan/incident-ledger/.events.seq",
    }
)


def _current_worktree_digest(project_dir: Path) -> str | None:
    """Worktree-aware source digest: HEAD tree PLUS working-tree CONTENT.

    ``_compute_code_hash`` hashes ``git ls-tree HEAD`` only, so it cannot see
    uncommitted task changes (this occurrence's task outputs land uncommitted
    on the workspace tree).  Resume-reuse decisions must invalidate when the
    WORKING TREE changes, so this combines the HEAD tree with the CONTENT of
    every staged/unstaged change and every untracked file.  A path/status-only
    view (``git status --porcelain``) is NOT enough — re-editing an
    already-dirty file leaves the porcelain line unchanged, which would let a
    stale envelope or POST_DELTA_PASSED be reused after the content actually
    changed (codex 20260818T2226Z verdict).  ``git diff --binary HEAD`` carries
    the actual content of all tracked changes (staged + unstaged); untracked
    files are hashed directly.  Falls back to the plain source digest when git
    is unavailable.    ``None`` only when nothing can be computed — callers
    treat ``None`` as a mismatch and fail closed.

    Engine-owned volatile ledger files (``.megaplan/incident-ledger/
    events.jsonl``, ``.megaplan/incident-ledger/.events.seq``) are tracked
    and appended by the watchdog every few minutes.  They are incident
    metadata, never a task deliverable, so hashing them makes every
    worktree digest (and every validation artifact bound to it) stale
    within minutes for no semantic gain — wedging pre-envelope reuse (D1)
    and evidence-gated budget-debt acceptance (D2) (occurrence
    927ad612eda8, 2026-08-19).  They are excluded here by explicit
    enumerated path only; a task that ever declares them as deliverables
    must revisit this exclusion.
    """
    _excluded = _WORKTREE_DIGEST_EXCLUDED_RELATIVE_PATHS
    try:
        head = subprocess.run(
            ["git", "-C", str(project_dir), "ls-tree", "-r", "HEAD", "--", "."],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if head.returncode == 0 and head.stdout.strip():
            blob = head.stdout
            diff_argv = [
                "git",
                "-C",
                str(project_dir),
                "diff",
                "--binary",
                "HEAD",
                "--",
                ".",
            ]
            diff_argv.extend(
                f":(exclude){path}" for path in sorted(_excluded)
            )
            diff = subprocess.run(
                diff_argv,
                capture_output=True,
                text=True,
                timeout=60,
            )
            if diff.returncode == 0:
                blob += "\n" + diff.stdout
            untracked = subprocess.run(
                [
                    "git",
                    "-C",
                    str(project_dir),
                    "ls-files",
                    "--others",
                    "--exclude-standard",
                    "-z",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if untracked.returncode == 0:
                for path in (p for p in untracked.stdout.split("\x00") if p):
                    if path in _excluded:
                        # Defensive: the enumerated engine-owned ledger
                        # files must never perturb the digest even if they
                        # are untracked in some checkout (see constant).
                        continue
                    blob += f"\n? {path}"
                    full = Path(project_dir) / path
                    if full.exists() and full.is_file():
                        try:
                            digest = hashlib.sha256(
                                full.read_bytes()
                            ).hexdigest()
                            blob += f" sha256:{digest}"
                        except OSError:
                            blob += " UNREADABLE"
                    else:
                        blob += " MISSING"
            return "sha256:" + hashlib.sha256(
                blob.encode("utf-8")
            ).hexdigest()
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    return _current_source_digest(project_dir)


def _envelope_matches_current_tree(
    env: Mapping[str, Any], project_dir: Path
) -> bool:
    """True when a stored envelope/verdict was computed against the CURRENT tree.

    Prefers the worktree-aware digest (records uncommitted task changes);
    falls back to the plain code hash for legacy artifacts written before the
    worktree digest existed.  A ``None`` current digest is a mismatch — fail
    closed, never reuse against an unverifiable tree.
    """
    _wt = _current_worktree_digest(project_dir)
    if env.get("worktree_digest") is not None:
        return env.get("worktree_digest") == _wt
    return env.get("code_hash") == _current_source_digest(project_dir)


def _raise_artifact_not_durable(
    *,
    job_id: str,
    reason: str,
    artifact_path: Path,
    error: Exception,
) -> None:
    """Fail closed when a delta-lifecycle artifact cannot be persisted.

    Dispatch may proceed ONLY after the pre-execution envelope (or post-delta
    verdict) is durable — a swallowed write would let T11 dispatch with no
    verifiable baseline and would let authority persist without evidence.
    """
    raise CliError(
        "validation_job_failed",
        f"validation job {job_id} {reason}: {error}",
        valid_next=["execute", "revise"],
        extra={
            "job_id": job_id,
            "reason": reason,
            "artifact_path": str(artifact_path),
        },
    ) from error


def _validation_commands_equivalent(stored_command: object, effective_command: str) -> bool:
    """True when a stored envelope's command is the same pytest invocation.

    The stored envelope records the EXECUTED command (suite_runner rewrites
    it to ``<interpreter> -m pytest <selectors> ...`` and appends the
    standard reporting flags ``--tb=no --no-header -rA``), while the reuse
    gate holds the RECOMPILED command (bare ``pytest <selectors> ...``).
    Comparing the raw strings can therefore never match, so every second
    pre-dispatch invocation raised ``pre_envelope_digest_drift`` and the
    no-new-failures delta lifecycle could never resume after its first
    envelope capture (occurrence a07166d38fbc, second wave).

    Canonicalize both sides through the suite runner's ``_pytest_command``:
    it rewrites a bare ``pytest`` to the running interpreter and appends the
    missing standard flags, so the executed form and the recompiled form
    reduce to the same canonical string.  Any unparseable command falls back
    to strict equality (fail closed).
    """
    from arnold_pipelines.megaplan.orchestration.suite_runner import (
        _pytest_command,
    )

    try:
        return _pytest_command(str(stored_command or "")) == _pytest_command(
            str(effective_command or "")
        )
    except Exception:
        return str(stored_command or "") == str(effective_command or "")


def _narrow_recheck_envelope_complete(result: Any) -> bool:
    """A COMPLETE pre-execution envelope: exit 1, successful collection,
    parsed failure set, no collection errors, no timeout.

    Anything else (timeout, signal, exit 2-5, collection errors, malformed
    output, missing failure data) is unknown — never ``[]`` — and stays
    fail-closed.

    Collection proof accepts EITHER the ``collected`` count (pytest prints
    "collected N items" only at verbosity >= 1) OR the parsed
    ``collected_ids`` list (always populated from the ``-rA`` report).
    The harness's recompiled narrow-recheck command runs pytest with ``-q``
    (see ``_recompile_legacy_narrow_recheck_command``), which suppresses the
    collected-count line and leaves ``collected == 0`` while ``collected_ids``
    is complete and ``collections_parse_ok`` is true.  Without this the
    no-new-failures delta lifecycle can never capture its pre-dispatch
    envelope, so a complete exit-1 run fails the admission gate instead of
    deferring to the post-adoption delta (occurrence a07166d38fbc).
    """
    return bool(
        result.exit_code == 1
        and result.status == "failed"
        and bool(result.collections_parse_ok)
        and (
            int(getattr(result, "collected", 0) or 0) > 0
            or bool(getattr(result, "collected_ids", None) or [])
        )
        and not (result.collection_errors or [])
        and bool(result.failures)
        and result.timeout_reason in (None, "")
    )


class _EnvelopeSuiteRun:
    """Minimal ``SuiteRunProtocol`` adapter over a stored pre-execution envelope.

    Lets the canonical ``compute_delta`` (suite_delta) consume a persisted
    envelope as its baseline without materializing a synthetic run result.
    """

    def __init__(self, failures: list[str], collected_ids: list[str]) -> None:
        self.failures = list(failures or [])
        self.collected_ids = list(collected_ids or [])


def _run_batch_validation_jobs(*, plan_dir, project_dir, finalize_data, batch_task_ids, is_final_batch=False, state=None, admission: bool = False, delta_baseline_envelope: Mapping[str, Any] | None = None, comparison_ceiling_override: int | None = None, force_strict_gate: bool = False):
    """Run deterministic harness validation jobs outside model dispatch (M8A T10).

    Returns a list of content-addressed evidence dicts (one per applicable
    job). Each ``evidence_hash`` is ``sha256:``-prefixed; a copy is persisted
    under ``<plan_dir>/verification/`` and a real ``validation`` work-class
    event is emitted via ``work_ledger``. A runner failure emits an
    ``unavailable_reason`` event instead of aborting dispatch.

    ``delta_baseline_envelope`` activates the post-adoption delta verdict for
    no-new-failures narrow_recheck jobs: a completed post run with no novel
    failures passes even when its raw exit remains 1; any new failing node,
    collection failure, timeout, or malformed result blocks.  When ``None``
    (pre-dispatch), a completed exit-1 run captures the pre-execution
    envelope and defers the verdict.

    ``force_strict_gate`` disables the no-new-failures delta acceptance for a
    deferred-selector recheck: a deferred task-output selector has no
    pre-task state, so a pre-execution envelope is impossible by construction
    and capturing one against the post-merge tree would launder the delta.
    Forced-strict runs keep the strict exit-code gate (never weaker than the
    delta comparison — for a task-created file the baseline is empty, so
    strict exit-0 equals no-new-failures exactly) and never create or consume
    pre/post-delta envelopes.
    """
    import hashlib as _hashlib
    import json as _json
    from arnold_pipelines.megaplan.orchestration import suite_runner as _suite_runner
    from arnold_pipelines.megaplan.observability import work_ledger as _wl

    evidence_results: list[dict] = []
    if not isinstance(finalize_data, dict):
        return evidence_results
    validation_jobs = finalize_data.get("validation_jobs")
    if not isinstance(validation_jobs, list) or not validation_jobs:
        return evidence_results
    # Bounded legacy-contract recovery: a blocked pre-dispatch validation
    # failure (cursor {phase: execute, retry_strategy: repair_validation_failure})
    # may deterministically recompile an in-memory validation contract from the
    # preserved finalize payload.  The projector is cursor-gated, fail-closed,
    # and never rewrites plan artifacts.
    _recovery_projection = _project_legacy_validation_contract_for_recovery(
        plan_dir=plan_dir,
        finalize_data=finalize_data,
        persisted_jobs=validation_jobs,
    )
    if _recovery_projection is not None:
        logging.getLogger("megaplan.execute.batch").info(
            "execute validation contract recovery: %d effective jobs replacing %d persisted jobs",
            len(_recovery_projection["effective_jobs"]),
            len(validation_jobs),
        )
        validation_jobs = _recovery_projection["effective_jobs"]
        _persist_validation_recovery_receipt(plan_dir, _recovery_projection)
    batch_id_set = set(batch_task_ids or [])
    verification_dir = Path(plan_dir) / "verification"
    try:
        verification_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    for job in validation_jobs:
        if not isinstance(job, dict):
            continue
        kind = job.get("kind")
        if kind == "post_execute_suite" and is_final_batch:
            applicable = True
        elif kind == "narrow_recheck":
            tid = job.get("task_id")
            applicable = isinstance(tid, str) and tid in batch_id_set
        else:
            applicable = False
        if not applicable:
            continue
        if kind == "post_execute_suite":
            _shadow_skip = False
            try:
                _ps = _json.loads(
                    (Path(plan_dir) / "state.json").read_text(encoding="utf-8")
                )
                _cfg = _ps.get("config") if isinstance(_ps, dict) else None
                _shadow_skip = isinstance(_cfg, dict) and _cfg.get("full_suite_backstop_mode") == "shadow"
            except Exception:
                pass
            if _shadow_skip:
                # Shadow mode: do NOT run the full-suite backstop synchronously
                # at pre-dispatch. Record it as deferred and let dispatch proceed
                # on the per-task narrow subsections. The backstop is a
                # milestone-wide observe-only safety net, not a pre-dispatch gate.
                _jid = str(job.get("id") or "vj")
                evidence_results.append({
                    "job_id": _jid,
                    "kind": kind,
                    "status": "shadow_deferred",
                    "exit_code": None,
                })
                log.info("post-execute suite %s deferred in SHADOW mode (non-blocking pre-dispatch)", _jid)
                continue
        timeout = job.get("max_seconds") or job.get("timeout_seconds") or 600
        job_id = str(job.get("id") or "vj")
        command = job.get("command")
        invalid_fields: list[str] = []
        if not isinstance(command, str) or not command.strip():
            invalid_fields.append("command")
        elif "\x00" in command or "\n" in command or "\r" in command:
            invalid_fields.append("command_shape")
        if job.get("mutates", False) is not False:
            invalid_fields.append("mutates")
        if job.get("writes_files") is not False:
            invalid_fields.append("writes_files")
        if invalid_fields:
            raise CliError(
                "invalid_validation_job",
                f"validation job {job_id} failed harness-owned admission: "
                f"{', '.join(invalid_fields)}",
                valid_next=["finalize", "revise"],
                extra={
                    "job_id": job_id,
                    "invalid_fields": invalid_fields,
                    "validation_job_kind": kind,
                },
            )
        if kind == "narrow_recheck":
            task_id = str(job.get("task_id") or "")
            # Older fixture payloads omitted ``tasks`` entirely.  Preserve
            # their compatibility path only for legacy payloads.  A canonical
            # v2 payload with no task graph is malformed and must not bypass
            # selector ownership classification.
            if "tasks" in finalize_data:
                task = next(
                    (
                        item
                        for item in finalize_data.get("tasks", [])
                        if isinstance(item, dict) and item.get("id") == task_id
                    ),
                    None,
                )
                if not isinstance(task, Mapping):
                    raise CliError(
                        "invalid_validation_job",
                        f"validation job {job_id} has no matching task owner",
                        valid_next=["finalize", "revise"],
                        extra={
                            "job_id": job_id,
                            "invalid_fields": ["task_id"],
                            "validation_job_kind": kind,
                            "reason": "task_owner_missing",
                        },
                    )
                lifecycle = classify_selector_lifecycle(
                    project_dir=project_dir,
                    job=job,
                    task=task,
                    all_declared_outputs=graph_declared_output_paths(
                        finalize_data.get("tasks")
                    ),
                )
                if lifecycle.status == SELECTOR_INVALID:
                    raise CliError(
                        "invalid_validation_job",
                        f"validation job {job_id} references missing selectors "
                        "that are not declared task outputs",
                        valid_next=["finalize", "revise"],
                        extra={
                            "job_id": job_id,
                            "invalid_fields": ["selectors"],
                            "missing_selectors": list(lifecycle.missing_selectors),
                            "undeclared_missing_selectors": list(
                                lifecycle.undeclared_missing_selectors
                            ),
                            "validation_job_kind": kind,
                            "reason": lifecycle.reason,
                        },
                    )
                if lifecycle.status == SELECTOR_DEFERRED:
                    evidence = deferred_selector_evidence(job, lifecycle)
                    artifact_path = verification_dir / f"validation_{job_id}_deferred.json"
                    try:
                        atomic_write_json(artifact_path, evidence)
                    except Exception:
                        pass
                    evidence_results.append(evidence)
                    log.info(
                        "validation job %s deferred until task %s creates %s",
                        job_id,
                        task_id,
                        sorted(set(lifecycle.missing_selectors)),
                    )
                    continue
            elif finalize_data.get("task_contract_version") == 2:
                # The execute admission guard normally rejects this earlier;
                # keep the validation-job boundary independently fail-closed
                # so direct/recovery callers cannot run a selector without a
                # canonical task owner.
                raise CliError(
                    "invalid_validation_job",
                    f"validation job {job_id} cannot run without the finalized task graph",
                    valid_next=["finalize", "revise"],
                    extra={
                        "job_id": job_id,
                        "invalid_fields": ["tasks"],
                        "validation_job_kind": kind,
                        "reason": "task_contract_missing",
                    },
                )
        # ---- no-new-failures delta lifecycle (narrow_recheck) ----
        # The planner probe budget is a cost hint, not the deadline for a
        # required full-file differential comparison.  Derive the
        # authoritative comparison ceiling from the enclosing full-suite
        # budget; fail closed when none exists rather than silently falling
        # back to the probe value.
        _delta_policy = False
        _comparison_ceiling: int | None = None
        _recompiled_command: str | None = None
        if kind == "narrow_recheck":
            # Detect the delta policy and recompile any legacy command shape
            # BEFORE suppression: forced-strict deferred rechecks still
            # normalize legacy embedded-timeout commands (the normalization is
            # the fix for the deterministic 124 killer, not a delta privilege).
            _detected_delta_policy = _narrow_recheck_delta_policy(
                job, job.get("command")
            )
            if _detected_delta_policy:
                _recompiled_command = _recompile_legacy_narrow_recheck_command(
                    job.get("command"), job.get("selectors")
                )
            _delta_policy = _detected_delta_policy and not force_strict_gate
            if _delta_policy or comparison_ceiling_override is not None:
                _comparison_ceiling = (
                    comparison_ceiling_override
                    if comparison_ceiling_override is not None
                    else _validation_comparison_ceiling(finalize_data)
                )
                if _delta_policy and _comparison_ceiling is None:
                    raise CliError(
                        "validation_job_failed",
                        f"validation job {job_id} uses the no-new-failures delta "
                        "lifecycle but no authoritative comparison budget exists",
                        valid_next=["finalize", "revise"],
                        extra={
                            "job_id": job_id,
                            "validation_job_kind": kind,
                            "reason": "comparison_budget_missing",
                            "expected_exit_codes": job.get("expected_exit_codes", [0]),
                        },
                    )
            _effective_command = command.strip()
            if _recompiled_command is not None:
                _effective_command = _recompiled_command
            # Resume reuse: a durable pre-execution envelope is a HISTORICAL
            # record of the pre-task state.  Reuse it without re-capturing —
            # re-capturing against a tree that already contains the task's
            # changes would launder the post-adoption delta.  Completed
            # envelopes (exit-1 ``pre_envelope_captured`` AND exit-0
            # ``passed``) are reused ONLY when selectors, effective command,
            # and the current worktree digest all match; anything else fails
            # closed — a completed envelope is never re-captured onto a
            # changed tree.
            # PRE-DISPATCH ONLY (``delta_baseline_envelope is None``): the
            # post-adoption rerun must NEVER consume the stored envelope and
            # skip the comparison — it always re-runs the selectors against
            # the merged state and computes the delta.
            if _delta_policy and delta_baseline_envelope is None:
                _env_artifact = _pre_envelope_artifact_path(verification_dir, job_id)
                try:
                    if _env_artifact.exists():
                        _stored_env = _json.loads(
                            _env_artifact.read_text(encoding="utf-8")
                        )
                    else:
                        _stored_env = None
                except Exception:
                    _stored_env = None
                _completed_env_statuses = (PRE_ENVELOPE_CAPTURED, "passed")
                _reused_envelope = False
                if isinstance(_stored_env, dict) and _stored_env.get(
                    "status"
                ) in _completed_env_statuses:
                    if (
                        set(_stored_env.get("selectors") or [])
                        == set(job.get("selectors") or [])
                        and _validation_commands_equivalent(
                            _stored_env.get("command"), _effective_command
                        )
                        and _envelope_matches_current_tree(_stored_env, project_dir)
                    ):
                        evidence_results.append(_stored_env)
                        _reused_envelope = True
                        log.info(
                            "validation job %s reusing durable pre-execution envelope %s",
                            job_id,
                            _stored_env.get("evidence_hash"),
                        )
                if not _reused_envelope and _env_artifact.exists():
                    # A COMPLETED envelope whose selectors/command/source no
                    # longer match must never be overwritten by a re-capture
                    # against the changed tree — the post-adoption delta would
                    # self-compare and mask new failures.  Recovery (occurrence
                    # 927ad612eda8): quarantine ANY non-reusable artifact
                    # (drifted, unreadable JSON, non-object, incomplete/unknown
                    # status) under verification/stale/ and re-run the job so a
                    # FRESH pre-envelope is durably captured against the
                    # CURRENT tree.  Safe because the job has not executed yet
                    # and the post-adoption path never consumes the stored
                    # envelope; the quarantine is required and fails closed.
                    _quarantine_pre_envelope_artifact_required(
                        _env_artifact,
                        job_id=job_id,
                        reason="pre_envelope_digest_drift",
                    )
                    log.info(
                        "validation job %s stale pre-envelope quarantined "
                        "to verification/stale/; re-running to refresh "
                        "against the current tree",
                        job_id,
                    )
                if _reused_envelope:
                    continue
                # Fall through to the normal suite execution; the existing
                # atomic write below remains the only producer of the
                # fresh pre-envelope.
        _effective_command = command.strip()
        if _recompiled_command is not None:
            _effective_command = _recompiled_command
        config = {
            "project_dir": str(project_dir),
            "plan_dir": str(plan_dir),
            "test_command": _effective_command,
        }
        if kind == "post_execute_suite":
            # The compiled suite timeout can be far smaller than the plan's
            # blast-radius suite actually needs.  Align the suite gate with
            # the chain-authoritative phase budget (bounded) so a slow but
            # healthy suite is not a false gate.  The admitted command remains
            # byte-for-byte authoritative: missing selectors and collection
            # errors are failures, never an invitation to weaken the gate.
            try:
                plan_state = _json.loads(
                    (Path(plan_dir) / "state.json").read_text(encoding="utf-8")
                )
                cfg = plan_state.get("config") if isinstance(plan_state, dict) else None
                pb = cfg.get("phase_timeout_seconds") if isinstance(cfg, dict) else None
                if isinstance(pb, (int, float)) and pb > 0:
                    timeout = max(int(timeout), min(int(pb), 14400))
            except Exception:
                pass
        _run_deadline_seconds = float(timeout)
        if _comparison_ceiling is not None:
            # The comparison ceiling (authoritative full-suite budget) is the
            # deadline for the required differential run, NOT the planner's
            # probe hint.  It ends promptly when the selectors complete.
            # Forced-strict deferred rechecks honor the same ceiling: the
            # planner probe budget is a cost hint, never a deadline for a
            # required revalidation.
            _run_deadline_seconds = float(_comparison_ceiling)
        try:
            result = _suite_runner.run_suite(
                Path(project_dir),
                config,
                phase="m8a_validation",
                deadline_seconds=time.monotonic() + _run_deadline_seconds,
                idle_seconds=None,
            )
        except Exception as exc:
            log.warning("validation job %s failed: %s", job_id, exc)
            error_detail = f"{type(exc).__name__}: {exc}"
            if _delta_policy or force_strict_gate:
                # A runner EXCEPTION in the no-new-failures delta lifecycle or
                # in a forced-strict deferred recheck is unknown, not a pass:
                # no envelope, no verdict, no dispatch.  The generic
                # runner_error/continue path would let dispatch or authority
                # progress without either — fail closed instead.
                _strict_runner_error = force_strict_gate and not _delta_policy
                raise CliError(
                    "validation_job_failed",
                    f"validation job {job_id} runner error in "
                    f"{'strict deferred gate' if _strict_runner_error else 'delta lifecycle'}: "
                    f"{error_detail}",
                    valid_next=["execute", "revise"],
                    extra={
                        "job_id": job_id,
                        "validation_job_kind": kind,
                        "reason": (
                            "strict_gate_runner_error"
                            if _strict_runner_error
                            else "delta_runner_error"
                        ),
                        "error": error_detail,
                    },
                ) from exc
            err_payload = {"job_id": job_id, "kind": kind, "error": error_detail}
            err_canonical = _json.dumps(err_payload, sort_keys=True, separators=(",", ":"))
            err_hash = "sha256:" + _hashlib.sha256(err_canonical.encode("utf-8")).hexdigest()
            evidence_results.append({
                "job_id": job_id,
                "kind": kind,
                "status": "runner_error",
                "exit_code": None,
                "evidence_hash": err_hash,
                "error": error_detail,
            })
            try:
                _wl.emit_unavailable_reason(
                    Path(plan_dir),
                    referenced_identity=str(job.get("task_id") or job_id),
                    reason="validation_runner_error",
                    detail=error_detail,
                )
            except Exception:
                pass
            continue
        evidence = {
            "job_id": job_id,
            "kind": kind,
            "command": result.command,
            "exit_code": result.exit_code,
            "duration": result.duration,
            "raw_log_path": (str(result.raw_log_path) if result.raw_log_path is not None else None),
            "code_hash": result.code_hash,
            "passes": list(result.passes or []),
            "failures": list(result.failures or []),
            "status": result.status,
            "timeout_reason": result.timeout_reason,
        }
        if kind == "narrow_recheck":
            evidence["collected"] = int(getattr(result, "collected", 0) or 0)
            evidence["collected_ids"] = list(result.collected_ids or [])
            evidence["selectors"] = list(job.get("selectors") or [])
            # Worktree binding for semantic resolution: a strict recheck pass
            # is only evidence against the merged tree it actually ran on.
            evidence["worktree_digest"] = _current_worktree_digest(project_dir)
        canonical = _json.dumps(evidence, sort_keys=True, separators=(",", ":"))
        evidence_hash = "sha256:" + _hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        evidence["evidence_hash"] = evidence_hash
        run_id = getattr(result, "run_id", job_id)
        artifact_path = verification_dir / f"validation_{job_id}_{run_id}.json"
        try:
            atomic_write_json(artifact_path, evidence)
        except Exception:
            pass
        try:
            _wl.emit_validation(
                Path(plan_dir),
                task_id=str(job.get("task_id") or ""),
                job_id=job_id,
                command=result.command,
                exit_code=result.exit_code,
                duration_ms=int((result.duration or 0) * 1000),
                evidence_hash=evidence_hash,
            )
        except Exception as exc:
            log.warning("emit_validation failed for %s: %s", job_id, exc)
        evidence_results.append(evidence)
        expected_exit_codes = job.get("expected_exit_codes", [0])
        if not isinstance(expected_exit_codes, list) or not all(
            isinstance(code, int) for code in expected_exit_codes
        ):
            raise CliError(
                "invalid_validation_job",
                f"validation job {job_id} has invalid expected_exit_codes",
                valid_next=["finalize", "revise"],
                extra={
                    "job_id": job_id,
                    "invalid_fields": ["expected_exit_codes"],
                    "validation_job_kind": kind,
                },
            )
        if result.exit_code not in expected_exit_codes:
            _subtracted_test_ids: list[str] | None = None
            if admission and kind == "narrow_recheck" and not _delta_policy:
                _subtracted_test_ids = _baseline_known_failures_only(
                    exit_code=result.exit_code,
                    failed_test_ids=list(result.failures or []),
                    baseline_test_failures=finalize_data.get(
                        "baseline_test_failures"
                    ),
                    collection_errors=list(result.collection_errors or []),
                    timeout_reason=result.timeout_reason,
                    status=result.status,
                )
            if _subtracted_test_ids is not None:
                # Admission-only pre-dispatch gate: the job failed ONLY on
                # node IDs the plan baseline already records as failing.
                # Keep the real exit_code + failures in the evidence and mark
                # the admission explicitly; deferred/final rechecks stay
                # strict and never subtract.
                evidence["status"] = "baseline_known_failures_only"
                evidence["admission"] = "pre_dispatch"
                evidence["subtracted_test_ids"] = _subtracted_test_ids
                evidence["new_failed_test_ids"] = []
                _baseline_ids = _validation_failure_ids(
                    finalize_data.get("baseline_test_failures")
                )
                evidence["baseline_test_failures_count"] = (
                    len(_baseline_ids) if _baseline_ids is not None else 0
                )
                log.warning(
                    "validation job %s admitted on baseline-known failures "
                    "only (exit_code=%s, subtracted=%s)",
                    job_id,
                    result.exit_code,
                    _subtracted_test_ids,
                )
                continue
            if _delta_policy:
                if delta_baseline_envelope is None:
                    # Pre-dispatch envelope capture: a COMPLETE exit-1 run
                    # records the pre-execution envelope and defers the
                    # verdict to the post-adoption delta recheck.  Timeouts,
                    # signals, exit 2-5, collection errors, and malformed
                    # output stay fail-closed (never an empty envelope).
                    if _narrow_recheck_envelope_complete(result):
                        evidence["status"] = PRE_ENVELOPE_CAPTURED
                        evidence["admission"] = "pre_dispatch_delta_envelope"
                        evidence["comparison_ceiling"] = _comparison_ceiling
                        evidence["worktree_digest"] = _current_worktree_digest(
                            project_dir
                        )
                        try:
                            atomic_write_json(
                                _pre_envelope_artifact_path(verification_dir, job_id),
                                evidence,
                            )
                        except Exception as _exc:
                            _raise_artifact_not_durable(
                                job_id=job_id,
                                reason="pre_envelope_not_durable",
                                artifact_path=_pre_envelope_artifact_path(
                                    verification_dir, job_id
                                ),
                                error=_exc,
                            )
                        log.warning(
                            "validation job %s captured pre-execution envelope "
                            "(exit_code=1, %d failure(s)); verdict deferred to "
                            "post-adoption delta recheck",
                            job_id,
                            len(result.failures or []),
                        )
                        continue
                else:
                    # Post-adoption delta verdict: compare the merged-state
                    # run against the pre-execution envelope.  An unchanged
                    # failure set passes even with raw exit 1; any novel
                    # failure blocks and never carries authority.
                    if _narrow_recheck_envelope_complete(result) or (
                        result.exit_code == 0
                    ):
                        _newly_failing: list[str] = []
                        _deleted_tests: list[str] = []
                        if result.exit_code == 1:
                            from arnold_pipelines.megaplan.orchestration.completion_contract import (
                                compute_delta as _compute_delta,
                            )

                            _delta = _compute_delta(
                                _EnvelopeSuiteRun(
                                    failures=list(
                                        delta_baseline_envelope.get("failures") or []
                                    ),
                                    collected_ids=list(
                                        delta_baseline_envelope.get("collected_ids")
                                        or []
                                    ),
                                ),
                                result,
                            )
                            _newly_failing = list(_delta.newly_failing)
                            _deleted_tests = list(_delta.deleted_tests)
                        if _newly_failing:
                            evidence["status"] = POST_DELTA_FAILED
                            evidence["admission"] = "post_dispatch_delta"
                            evidence["newly_failing"] = _newly_failing
                            evidence["deleted_tests"] = _deleted_tests
                            evidence["baseline_envelope_hash"] = (
                                delta_baseline_envelope.get("evidence_hash")
                            )
                            evidence["worktree_digest"] = _current_worktree_digest(
                                project_dir
                            )
                            try:
                                atomic_write_json(
                                    _post_delta_artifact_path(verification_dir, job_id),
                                    evidence,
                                )
                            except Exception as _exc:
                                _raise_artifact_not_durable(
                                    job_id=job_id,
                                    reason="post_delta_failed_artifact_not_durable",
                                    artifact_path=_post_delta_artifact_path(
                                        verification_dir, job_id
                                    ),
                                    error=_exc,
                                )
                            log.warning(
                                "validation job %s post-adoption delta FAILED: "
                                "%d new failure(s): %s",
                                job_id,
                                len(_newly_failing),
                                _newly_failing,
                            )
                            _raise_deferred_selector_result_block(
                                job_id=job_id,
                                task_id=str(job.get("task_id") or ""),
                                reason="post_delta_new_failures",
                                extra={"newly_failing": _newly_failing},
                            )
                        evidence["status"] = POST_DELTA_PASSED
                        evidence["admission"] = "post_dispatch_delta"
                        evidence["newly_failing"] = []
                        evidence["deleted_tests"] = _deleted_tests
                        evidence["baseline_envelope_hash"] = (
                            delta_baseline_envelope.get("evidence_hash")
                        )
                        evidence["worktree_digest"] = _current_worktree_digest(
                            project_dir
                        )
                        try:
                            atomic_write_json(
                                _post_delta_artifact_path(verification_dir, job_id),
                                evidence,
                            )
                        except Exception as _exc:
                            _raise_artifact_not_durable(
                                job_id=job_id,
                                reason="post_delta_passed_artifact_not_durable",
                                artifact_path=_post_delta_artifact_path(
                                    verification_dir, job_id
                                ),
                                error=_exc,
                            )
                        log.warning(
                            "validation job %s post-adoption delta clean "
                            "(exit_code=%s, %d failure(s) unchanged vs envelope)",
                            job_id,
                            result.exit_code,
                            len(result.failures or []),
                        )
                        continue
                    # fall through: timeout/signal/exit 2-5/collection
                    # errors/malformed output stay fail-closed in delta mode.
            _shadow_backstop = False
            try:
                _ps = _json.loads(
                    (Path(plan_dir) / "state.json").read_text(encoding="utf-8")
                )
                _cfg = _ps.get("config") if isinstance(_ps, dict) else None
                _shadow_backstop = (
                    kind == "post_execute_suite"
                    and isinstance(_cfg, dict)
                    and _cfg.get("full_suite_backstop_mode") == "shadow"
                )
            except Exception:
                pass
            if _shadow_backstop:
                # Honor full_suite_backstop_mode=shadow: the full-suite backstop
                # records/reports its result but does not gate dispatch. Real
                # enforcement mode stays fail-closed below.
                evidence["status"] = "shadow_nonblocking"
                log.warning(
                    "validation job %s exited %s in SHADOW backstop mode; "
                    "recording without blocking dispatch",
                    job_id, result.exit_code,
                )
            else:
                raise CliError(
                    "validation_job_failed",
                    f"validation job {job_id} exited {result.exit_code}; "
                    f"expected one of {expected_exit_codes}",
                    valid_next=["execute", "revise", "finalize"],
                    extra={
                        "job_id": job_id,
                        "validation_job_kind": kind,
                        "exit_code": result.exit_code,
                        "expected_exit_codes": expected_exit_codes,
                        "evidence_hash": evidence_hash,
                        "artifact_path": str(artifact_path),
                    },
                )
        if _delta_policy and result.exit_code in expected_exit_codes:
            if delta_baseline_envelope is not None:
                # POST-ADOPTION green run: exit 0 means the merged state has
                # NO failures — a delta pass against the pre-execution
                # envelope, durably tied to the exact envelope hash.  Never
                # overwrite the pre-envelope with the post-task run (that
                # would launder the baseline into a self-comparing delta).
                evidence["status"] = POST_DELTA_PASSED
                evidence["admission"] = "post_dispatch_delta"
                evidence["newly_failing"] = []
                evidence["deleted_tests"] = []
                evidence["baseline_envelope_hash"] = (
                    delta_baseline_envelope.get("evidence_hash")
                )
                evidence["worktree_digest"] = _current_worktree_digest(project_dir)
                try:
                    atomic_write_json(
                        _post_delta_artifact_path(verification_dir, job_id),
                        evidence,
                    )
                except Exception as _exc:
                    _raise_artifact_not_durable(
                        job_id=job_id,
                        reason="post_delta_passed_artifact_not_durable",
                        artifact_path=_post_delta_artifact_path(
                            verification_dir, job_id
                        ),
                        error=_exc,
                    )
                log.warning(
                    "validation job %s post-adoption delta clean (exit_code=0, "
                    "no failures vs envelope)",
                    job_id,
                )
                continue
            # Known-empty pre-execution envelope (PRE-DISPATCH): persist for
            # resume reuse and as the post-adoption delta baseline.  A green
            # pre-dispatch run still gets a post-adoption recheck — the task
            # may introduce new failures.
            evidence["admission"] = "pre_dispatch_delta_envelope"
            evidence["comparison_ceiling"] = _comparison_ceiling
            evidence["worktree_digest"] = _current_worktree_digest(project_dir)
            try:
                atomic_write_json(
                    _pre_envelope_artifact_path(verification_dir, job_id),
                    evidence,
                )
            except Exception as _exc:
                _raise_artifact_not_durable(
                    job_id=job_id,
                    reason="pre_envelope_not_durable",
                    artifact_path=_pre_envelope_artifact_path(
                        verification_dir, job_id
                    ),
                    error=_exc,
                )
    return evidence_results


def _accepted_task_result_envelopes(
    payload: Mapping[str, Any],
) -> dict[str, tuple[Mapping[str, Any], ResultEnvelope]]:
    """Return task rows paired with their grant-aware accepted envelopes.

    A syntactically valid envelope is not enough to release a deferred
    selector.  The merge validator records ``authority_validation.outcome``
    on each row; only the exact ``accepted`` outcome is eligible here.  This
    deliberately excludes legacy rows, quarantined envelopes, and blocked or
    off-scope results.
    """

    raw_envelopes = payload.get(RESULT_ENVELOPES_KEY)
    if not isinstance(raw_envelopes, list):
        return {}
    by_subject: dict[str, list[ResultEnvelope]] = {}
    for raw in raw_envelopes:
        if not isinstance(raw, Mapping):
            continue
        try:
            envelope = ResultEnvelope.from_dict(raw)
        except (ContractError, TypeError, ValueError, KeyError):
            continue
        if not isinstance(envelope.claim, TaskClaim):
            continue
        by_subject.setdefault(envelope.subject_id, []).append(envelope)

    rows = payload.get("task_updates")
    if not isinstance(rows, list):
        return {}
    accepted: dict[str, tuple[Mapping[str, Any], ResultEnvelope]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        task_id = row.get("task_id")
        if not isinstance(task_id, str) or not task_id.strip():
            continue
        validation = row.get("authority_validation")
        if not isinstance(validation, Mapping) or validation.get("outcome") != "accepted":
            continue
        candidates = list(by_subject.get(task_id, ()))
        expected_digest = validation.get("envelope_digest")
        if isinstance(expected_digest, str) and expected_digest:
            candidates = [
                envelope
                for envelope in candidates
                if envelope.digest() == expected_digest
            ]
        if len(candidates) != 1:
            # Ambiguous or missing authority cannot prove the task-owned
            # output; the caller turns this into a typed deferred block.
            continue
        accepted[task_id] = (row, candidates[0])
    return accepted


def _raise_deferred_selector_result_block(
    *,
    job_id: str,
    task_id: str,
    reason: str,
    extra: Mapping[str, Any] | None = None,
) -> None:
    details = {
        "job_id": job_id,
        "task_id": task_id,
        "validation_job_kind": "narrow_recheck",
        "reason": reason,
    }
    if isinstance(extra, Mapping):
        details.update(dict(extra))
    raise CliError(
        "deferred_validation_result_missing",
        f"deferred validation job {job_id} cannot be revalidated: {reason}",
        valid_next=["execute", "revise"],
        extra=details,
    )


_POST_MERGE_POLICY_BLOCKED = "post_merge_policy_blocked"


def _park_post_merge_policy_block(
    *,
    verification_dir: Path,
    job_id: str,
    task_id: str,
    task_status: object,
) -> dict[str, Any]:
    """Persist a typed validation-blocked disposition for a policy-blocked row.

    A task blocked by the merge admission gate (e.g. the test-budget gate)
    cannot release a deferred selector.  Instead of raising a terminal
    ``task_result_blocked_by_post_merge_policy`` that kills the execute
    coordinator's aggregate state publication, park the refusal as a typed
    ``validation_blocked`` disposition so the plan survives to a fresh
    compliant attempt.  The row itself stays blocked; authority adoption never
    overrides the gate; the next ``--retry-blocked-tasks`` dispatch resets it.
    """

    evidence = {
        "job_id": job_id,
        "task_id": task_id,
        "kind": "narrow_recheck",
        "status": _POST_MERGE_POLICY_BLOCKED,
        "disposition": "validation_blocked",
        "reason": "task_result_blocked_by_post_merge_policy",
        "task_status": task_status,
    }
    atomic_write_json(
        verification_dir / f"validation_{job_id}_policy_blocked.json",
        evidence,
    )
    return evidence


def _load_current_unresolved_deferred_selector_jobs(
    *,
    plan_dir: Path,
    finalize_data: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Load persisted deferred-selector records for CURRENT finalize jobs.

    Only records whose ``job_id`` maps to an effective ``narrow_recheck``
    job in the preserved finalize payload are considered; stale or malformed
    artifacts are ignored (they are best-effort evidence; the finalize
    payload is authoritative).  Records are deduplicated by ``job_id``.
    """

    jobs_by_id = {
        str(job.get("id")): job
        for job in finalize_data.get("validation_jobs", [])
        if isinstance(job, Mapping)
        and isinstance(job.get("id"), str)
        and job.get("kind") == "narrow_recheck"
    }
    verification_dir = Path(plan_dir) / "verification"
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    try:
        candidates = sorted(verification_dir.glob("validation_*_deferred.json"))
    except OSError:
        return []
    for artifact in candidates:
        try:
            record = json.loads(artifact.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            log.warning("ignoring unreadable deferred evidence %s", artifact)
            continue
        if not isinstance(record, Mapping):
            continue
        job_id = str(record.get("job_id") or "")
        if not job_id or job_id in seen:
            continue
        if job_id not in jobs_by_id:
            continue
        seen.add(job_id)
        records.append(dict(record))
    return records


def _quarantine_validation_artifact(artifact: Path, stale_dir: Path) -> None:
    """Move a non-resolving validation artifact under ``verification/stale/``.

    Keeps the audit evidence while guaranteeing it can never suppress a
    future strict recheck.  Idempotent and never destructive: a name clash is
    resolved by suffixing the source mtime ns.
    """
    try:
        stale_dir.mkdir(parents=True, exist_ok=True)
        target = stale_dir / artifact.name
        if target.exists():
            target = stale_dir / (
                f"{artifact.stem}-{artifact.stat().st_mtime_ns}{artifact.suffix}"
            )
        artifact.replace(target)
    except OSError as _exc:
        log.warning(
            "could not quarantine validation artifact %s: %s", artifact, _exc
        )


def _semantic_deferred_resolution(
    *,
    verification_dir: Path,
    job_id: str,
    job: Mapping[str, Any],
    project_dir: Path,
) -> bool:
    """True only when a CURRENT binding-valid PASS artifact resolves a job.

    Filename existence is not a verdict: deferred markers, pre/post-delta
    envelopes, policy blocks, failed/runner-error/timeout evidence, malformed
    records, and binding-mismatched passes never resolve a deferred job.
    Such artifacts are quarantined under ``verification/stale/`` so the next
    sweep re-runs the job against the merged tree (occurrence ae1f50c01dbd —
    stale ``pre_envelope_captured`` evidence must not suppress the strict
    recheck).
    """
    import json as _json

    expected_selectors = {
        str(s).strip("'\"") for s in (job.get("selectors") or []) if isinstance(s, str)
    }
    stale_dir = verification_dir / "stale"
    for artifact in sorted(verification_dir.glob(f"validation_{job_id}_*.json")):
        name = artifact.name
        if name == f"validation_{job_id}_deferred.json":
            # The deferred marker is the reason we are here; keep it.
            continue
        if name.endswith(_PRE_ENVELOPE_ARTIFACT_SUFFIX) or name.endswith(
            _POST_DELTA_ARTIFACT_SUFFIX
        ):
            _quarantine_validation_artifact(artifact, stale_dir)
            continue
        try:
            record = _json.loads(artifact.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            _quarantine_validation_artifact(artifact, stale_dir)
            continue
        if not isinstance(record, Mapping):
            _quarantine_validation_artifact(artifact, stale_dir)
            continue
        status = record.get("status")
        if status not in ("passed", POST_DELTA_PASSED):
            _quarantine_validation_artifact(artifact, stale_dir)
            continue
        selectors_ok = (
            {str(s).strip("'\"") for s in (record.get("selectors") or []) if isinstance(s, str)}
            == expected_selectors
        )
        digest_ok = bool(record.get("worktree_digest")) and record.get(
            "worktree_digest"
        ) == _current_worktree_digest(project_dir)
        if status == POST_DELTA_PASSED:
            newly_failing = record.get("newly_failing") or []
            if (
                not newly_failing
                and record.get("baseline_envelope_hash")
                and selectors_ok
                and digest_ok
            ):
                return True
        elif status == "passed" and selectors_ok and digest_ok:
            return True
        _quarantine_validation_artifact(artifact, stale_dir)
    return False


def _find_binding_valid_strict_pass(
    *,
    verification_dir: Path,
    job_id: str,
    job: Mapping[str, Any],
    project_dir: Path,
) -> dict[str, Any] | None:
    """Return the CURRENT binding-valid strict PASS artifact for a job.

    Mirrors ``_semantic_deferred_resolution`` but returns the record and adds
    the strict-gate fields (exit_code == 0, no failures/timeout, admitted
    command equivalence) so an evidence-gated budget-debt acceptance can cite
    the exact evidence hash.  Only a strict ``passed`` (never a pre/post-delta
    envelope, never a deferred marker, never a policy block, never a stale
    digest) qualifies; anything else is ignored (NOT quarantined here — the
    sweep owns quarantine).
    """
    import json as _json

    expected_selectors = {
        str(s).strip("'\"") for s in (job.get("selectors") or []) if isinstance(s, str)
    }
    effective_command = str(job.get("command") or "").strip()
    current_digest = _current_worktree_digest(project_dir)
    for artifact in sorted(verification_dir.glob(f"validation_{job_id}_*.json")):
        name = artifact.name
        if name.endswith(_PRE_ENVELOPE_ARTIFACT_SUFFIX) or name.endswith(
            _POST_DELTA_ARTIFACT_SUFFIX
        ):
            continue
        try:
            record = _json.loads(artifact.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(record, Mapping) or record.get("status") != "passed":
            continue
        if record.get("exit_code") != 0:
            continue
        if record.get("timeout_reason") or record.get("failures"):
            continue
        selectors_ok = (
            {str(s).strip("'\"") for s in (record.get("selectors") or []) if isinstance(s, str)}
            == expected_selectors
        )
        digest_ok = bool(record.get("worktree_digest")) and record.get(
            "worktree_digest"
        ) == current_digest
        command_ok = _validation_commands_equivalent(
            record.get("command"), effective_command
        )
        if selectors_ok and digest_ok and command_ok:
            return dict(record)
    return None


def _budget_debt_acceptance_receipt_path(
    verification_dir: Path, task_id: str, evidence_prefix: str
) -> Path:
    return verification_dir / (
        f"task_budget_acceptance_{task_id}_{evidence_prefix}.json"
    )


def _accept_strictly_verified_test_budget_debt(
    *,
    plan_dir: Path,
    project_dir: Path,
    finalize_data: dict[str, Any],
    payload: Mapping[str, Any],
    deviations: list[str],
) -> list[str]:
    """Evidence-gated acceptance of a cumulative-time-only test-budget block.

    The merge budget gate (merge.py:_enforce_task_test_budgets) stays strict:
    a task whose recorded invocations exceed ``max_seconds`` is blocked with a
    durable typed ``task_test_budget_violations`` list.  For TDD-style plans a
    declared selector can be parametrized so wide that the FULL admitted
    selection deterministically cannot finish inside ``max_seconds`` (m5 T28:
    tests/cloud/test_progress_auditor.py ~225 cases, 217s green run vs a 120s
    cap).  A fresh compliant attempt can therefore never converge, wedging
    execute in ``blocked_by_quality`` forever (occurrence 927ad612eda8).

    This reconciler converts ONLY the single non-correctness case AFTER merge:
    - the durable violations are EXACTLY ``{max_seconds_exceeded}``;
    - every recorded run used only admitted selectors and wrappers (implied by
      the absence of every other typed kind);
    - run count is within ``max_runs`` (also implied);
    - the task has an ACCEPTED result envelope (kernel authority);
    - the task has exactly one ``narrow_recheck`` job whose normalized
      selectors equal ``task.narrow_tests.selectors``; and
    - a binding-valid CURRENT-worktree strict artifact for that job exists
      (status passed, exit 0, no failures/timeout, equivalent command, exact
      selectors, current digest).

    On eligibility the task is promoted to ``done`` with the block cleared and
    the original violation retained as durable ``task_test_budget_debt``
    (disposition ``accepted_with_debt``) plus a content-addressed acceptance
    receipt under ``verification/``.  Any other violation kind, missing
    authority, stale digest, widened selector, missing wrapper, run-count
    excess, or genuine strict failure remains blocked — never laundered.
    """
    import json as _json
    import time as _time

    tasks = finalize_data.get("tasks")
    if not isinstance(tasks, list):
        return []
    jobs_by_id: dict[str, Mapping[str, Any]] = {}
    for job in finalize_data.get("validation_jobs", []):
        if isinstance(job, Mapping) and isinstance(job.get("id"), str):
            jobs_by_id[str(job.get("id"))] = job
    verification_dir = Path(plan_dir) / "verification"
    current_digest = _current_worktree_digest(project_dir)
    accepted_envelopes = _accepted_task_result_envelopes(payload)
    accepted_ids: list[str] = []
    for task in tasks:
        if not isinstance(task, dict):
            continue
        task_id = task.get("id")
        if not isinstance(task_id, str) or task.get("status") != "blocked":
            continue
        violations = task.get("task_test_budget_violations")
        if not isinstance(violations, list) or not violations:
            continue
        kinds = {
            str(v.get("kind"))
            for v in violations
            if isinstance(v, Mapping) and isinstance(v.get("kind"), str)
        }
        if kinds != {"max_seconds_exceeded"}:
            continue
        # Accepted kernel authority: the merged row carries the accepted
        # outcome, the current payload has the accepted envelope, OR the
        # merged row carries kernel-witnessed WORK EVIDENCE (non-empty
        # files_changed AND commands_run) from a budget-killed dispatch.
        # The merge only admits authority-validated entries
        # (merge.py:_validate_and_merge_batch), so merged-row evidence is
        # kernel-witnessed; a skipped task has empty evidence and can never
        # satisfy this; and max_seconds_exceeded structurally implies the
        # admitted commands actually ran (merge.py:_enforce_task_test_budgets
        # derives the typed violations from recorded runs).  The envelope
        # preconditions alone are unsatisfiable for budget-killed tasks —
        # the worker is forced to return blocked by the cap, so no accepted
        # envelope is ever produced (occurrence 927ad612eda8 live regression
        # 2026-08-19T10:46Z) — making the work-evidence disjunct the only
        # path that can fire for exactly the case this reconciler exists for.
        row_authority = task.get("authority_validation")
        work_evidence = bool(
            isinstance(task.get("files_changed"), list)
            and task.get("files_changed")
            and isinstance(task.get("commands_run"), list)
            and task.get("commands_run")
        )
        has_authority = (
            isinstance(row_authority, Mapping)
            and row_authority.get("outcome") == "accepted"
        ) or task_id in accepted_envelopes or work_evidence
        if not has_authority:
            continue
        narrow = task.get("narrow_tests")
        if not isinstance(narrow, Mapping):
            continue
        admitted_selectors = {
            str(s).strip("'\"")
            for s in narrow.get("selectors", [])
            if isinstance(s, str) and s.strip()
        }
        if not admitted_selectors:
            continue
        matching_jobs = [
            job
            for job in jobs_by_id.values()
            if job.get("kind") == "narrow_recheck"
            and str(job.get("task_id") or "") == task_id
        ]
        if len(matching_jobs) != 1:
            continue
        job = matching_jobs[0]
        job_selectors = {
            str(s).strip("'\"") for s in (job.get("selectors") or []) if isinstance(s, str)
        }
        if job_selectors != admitted_selectors:
            continue
        strict = _find_binding_valid_strict_pass(
            verification_dir=verification_dir,
            job_id=str(job.get("id") or ""),
            job=job,
            project_dir=project_dir,
        )
        if strict is None:
            continue
        evidence_prefix = str(strict.get("evidence_hash") or "").replace(
            "sha256:", ""
        )[:12]
        receipt_path = _budget_debt_acceptance_receipt_path(
            verification_dir, task_id, evidence_prefix
        )
        debt = {
            "disposition": "accepted_with_debt",
            "violation": violations,
            "task_id": task_id,
            "job_id": job.get("id"),
            "strict_evidence_hash": strict.get("evidence_hash"),
            "worktree_digest": current_digest,
            "selectors": sorted(admitted_selectors),
            "command": str(job.get("command") or ""),
            "accepted_envelope": (
                accepted_envelopes.get(task_id, (None, None))[1].to_dict()
                if task_id in accepted_envelopes
                else None
            ),
            "accepted_at": _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime()),
        }
        try:
            atomic_write_json(receipt_path, debt)
        except Exception as _exc:
            raise CliError(
                "validation_job_failed",
                f"task {task_id} budget-debt acceptance receipt not durable",
                valid_next=["execute", "revise"],
                extra={
                    "task_id": task_id,
                    "reason": "budget_debt_acceptance_not_durable",
                    "artifact_path": str(receipt_path),
                },
            ) from _exc
        task["status"] = "done"
        task.pop("blocked_reason", None)
        task.pop("task_test_budget_exhausted", None)
        task["task_test_budget_debt"] = debt
        # Replace the merge-generated quality blocker with an advisory so
        # aggregation keeps the debt as deferred evidence, not a blocker.
        prefix = f"Task {task_id} blocked by admitted test budget:"
        merged = [
            msg
            for msg in deviations
            if not (isinstance(msg, str) and msg.startswith(prefix))
        ]
        merged.append(
            "Advisory test-budget debt accepted after current strict "
            f"validation: {task_id} ({str(job.get('id') or '')} strict pass "
            f"{strict.get('evidence_hash')})."
        )
        deviations[:] = merged
        accepted_ids.append(task_id)
        log.info(
            "test-budget debt accepted with evidence for task %s "
            "(job %s strict pass %s); task promoted to done",
            task_id,
            job.get("id"),
            strict.get("evidence_hash"),
        )
    return sorted(accepted_ids)


def _sweep_persisted_deferred_selector_jobs(
    *,
    plan_dir: Path,
    project_dir: Path,
    finalize_data: Mapping[str, Any],
    state: PlanState | None = None,
) -> list[dict[str, Any]]:
    """Re-attempt unresolved deferred narrow jobs once every task has run.

    Called at the final batch post-merge, after the same-batch deferred
    recheck.  Every admitted task has now produced (or failed to produce) its
    declared outputs, so a deferred selector that is STILL missing is either
    genuinely undeclared (invalid) or declared-but-never-created (fail
    closed).  A selector that now exists runs its narrow recheck through the
    same deterministic job runner; a failing recheck raises
    ``validation_job_failed`` exactly like any other harness run.
    """

    if not isinstance(finalize_data, dict):
        return []
    graph_outputs = graph_declared_output_paths(finalize_data.get("tasks"))
    tasks_by_id = {
        str(task.get("id")): task
        for task in finalize_data.get("tasks", [])
        if isinstance(task, Mapping) and isinstance(task.get("id"), str)
    }
    jobs_by_id = {
        str(job.get("id")): job
        for job in finalize_data.get("validation_jobs", [])
        if isinstance(job, Mapping)
        and isinstance(job.get("id"), str)
        and job.get("kind") == "narrow_recheck"
    }
    verification_dir = Path(plan_dir) / "verification"
    deferred = _load_current_unresolved_deferred_selector_jobs(
        plan_dir=plan_dir,
        finalize_data=finalize_data,
    )
    sweep_results: list[dict[str, Any]] = []
    for record in deferred:
        job_id = str(record.get("job_id") or "")
        task_id = str(record.get("task_id") or "")
        job = jobs_by_id.get(job_id)
        task = tasks_by_id.get(task_id)
        if job is None or task is None:
            raise CliError(
                "deferred_validation_result_missing",
                f"deferred validation job {job_id} cannot be revalidated: "
                "task_or_validation_job_missing_from_finalize_contract",
                valid_next=["execute", "revise"],
                extra={
                    "job_id": job_id,
                    "task_id": task_id,
                    "validation_job_kind": "narrow_recheck",
                    "reason": "task_or_validation_job_missing_from_finalize_contract",
                },
            )
        # A CURRENT binding-valid PASS artifact proves this job already
        # passed against the merged tree (e.g. a prior sweep's strict recheck
        # discharged it); do not re-run a resolved job.  Filename existence is
        # NOT a verdict: failed/stale/pre-envelope/policy-blocked evidence is
        # quarantined so it cannot suppress the strict recheck (occurrence
        # ae1f50c01dbd).
        if _semantic_deferred_resolution(
            verification_dir=verification_dir,
            job_id=job_id,
            job=job,
            project_dir=project_dir,
        ):
            continue
        lifecycle = classify_selector_lifecycle(
            project_dir=project_dir,
            job=job,
            task=task,
            all_declared_outputs=graph_outputs,
        )
        if lifecycle.status == SELECTOR_INVALID:
            raise CliError(
                "invalid_validation_job",
                f"validation job {job_id} references missing selectors "
                "that are not declared task outputs",
                valid_next=["finalize", "revise"],
                extra={
                    "job_id": job_id,
                    "invalid_fields": ["selectors"],
                    "missing_selectors": list(lifecycle.missing_selectors),
                    "undeclared_missing_selectors": list(
                        lifecycle.undeclared_missing_selectors
                    ),
                    "validation_job_kind": "narrow_recheck",
                    "reason": lifecycle.reason,
                },
            )
        if lifecycle.status == SELECTOR_DEFERRED:
            task_status = task.get("status") if isinstance(task, Mapping) else None
            if task_status not in {"done", "completed"}:
                # Abort-recovery park: the declaring task never completed
                # (e.g. a worker aborted mid-batch), so the missing selector is
                # not yet evidence of a broken write-set contract.  Keep the
                # deferred evidence parked; the next resume re-dispatches the
                # pending task and this sweep only fires after every admitted
                # task of the run has been processed.
                log.info(
                    "validation job %s remains deferred at final sweep: "
                    "owner task %s not complete (status=%r), parked",
                    job_id,
                    task_id,
                    task_status,
                )
                continue
            missing_selectors = set(lifecycle.missing_selectors)
            incomplete_declaring_task_ids = sorted(
                str(candidate.get("id"))
                for candidate in finalize_data.get("tasks", [])
                if isinstance(candidate, Mapping)
                and isinstance(candidate.get("id"), str)
                and candidate.get("status") not in {"done", "completed"}
                and missing_selectors.intersection(
                    declared_task_output_paths(candidate)
                )
            )
            if incomplete_declaring_task_ids:
                # A cross-task producer of this selector is still unfinished;
                # parking is correct until every declaring producer completes.
                # Only then can a still-missing selector be judged a write-set
                # contract break.
                log.info(
                    "validation job %s remains deferred at final sweep: "
                    "declaring task(s) %s not complete, parked",
                    job_id,
                    incomplete_declaring_task_ids,
                )
                continue
            # Every admitted task has run; a still-missing graph-declared
            # selector means the declaring task broke its write-set contract.
            raise CliError(
                "deferred_validation_result_missing",
                f"deferred validation job {job_id} cannot be revalidated: "
                "declared_selector_output_never_created",
                valid_next=["execute", "revise"],
                extra={
                    "job_id": job_id,
                    "task_id": task_id,
                    "validation_job_kind": "narrow_recheck",
                    "reason": "declared_selector_output_never_created",
                    "missing_selectors": sorted(set(lifecycle.missing_selectors)),
                },
            )
        # A deferred selector is a task-output path that did not exist at
        # pre-dispatch time; a no-new-failures delta job has no pre-task state
        # by construction, so NO delta job (explicit OR legacy-derived) may be
        # admitted through the sweep with its delta lifecycle — capturing a
        # "pre-envelope" against the post-task tree would launder the
        # post-adoption delta.  Instead the sweep revalidates every deferred
        # job whose selector now exists with the STRICT exit-0 gate
        # (``force_strict_gate``): the strict gate is never weaker than the
        # delta comparison (occurrence 0a0ce24c3510), and for a task-created
        # file the baseline is empty so strict exit-0 equals no-new-failures
        # exactly (occurrence ae1f50c01dbd — explicit-delta TDD plans must
        # not wedge at the final sweep).
        # The sweep runs the job as a singleton; carry the authoritative
        # comparison ceiling from the FULL plan list so the planner probe
        # budget never becomes a recheck deadline.
        _sweep_ceiling = _validation_comparison_ceiling(finalize_data)
        if _sweep_ceiling is None:
            raise CliError(
                "deferred_validation_result_missing",
                f"deferred validation job {job_id} cannot be revalidated: "
                "comparison_budget_missing",
                valid_next=["execute", "revise"],
                extra={
                    "job_id": job_id,
                    "task_id": task_id,
                    "validation_job_kind": "narrow_recheck",
                    "reason": "comparison_budget_missing",
                },
            )
        # Selector now exists: run the narrow recheck as a singleton job so
        # only THIS job's command is admitted (never sibling jobs of the task).
        rerun_data = dict(finalize_data)
        rerun_data["validation_jobs"] = [dict(job)]
        sweep_results.extend(
            _run_batch_validation_jobs(
                plan_dir=plan_dir,
                project_dir=project_dir,
                finalize_data=rerun_data,
                batch_task_ids=[task_id],
                is_final_batch=False,
                state=state,
                comparison_ceiling_override=_sweep_ceiling,
                force_strict_gate=True,
            )
        )
    return sweep_results


def _rerun_deferred_selector_validation_jobs(
    *,
    plan_dir: Path,
    project_dir: Path,
    finalize_data: dict[str, Any],
    batch_task_ids: list[str],
    pre_dispatch_results: Any,
    payload: Mapping[str, Any],
    state: PlanState | None = None,
) -> list[dict[str, Any]]:
    """Re-run deferred narrow jobs after an accepted task result envelope.

    Deferred validation is a two-phase protocol: Execute may defer a missing
    selector only when ``write_set.paths`` declares ownership; after worker
    merge, the result claim must be accepted and explicitly report the exact
    selector path in ``files_changed``.  That claim is evidence, not a write
    set mutation, and therefore cannot widen task ownership.
    """

    if not isinstance(pre_dispatch_results, list):
        return []
    deferred = [
        item
        for item in pre_dispatch_results
        if isinstance(item, Mapping) and item.get("status") == SELECTOR_DEFERRED
    ]
    enveloped = [
        item
        for item in pre_dispatch_results
        if isinstance(item, Mapping)
        and item.get("admission") == "pre_dispatch_delta_envelope"
        and item.get("status") in (PRE_ENVELOPE_CAPTURED, "passed", "failed")
    ]
    if not deferred and not enveloped:
        return []
    import json as _json

    verification_dir = Path(plan_dir) / "verification"

    jobs_by_id = {
        str(job.get("id")): job
        for job in finalize_data.get("validation_jobs", [])
        if isinstance(job, Mapping) and isinstance(job.get("id"), str)
    }
    tasks_by_id = {
        str(task.get("id")): task
        for task in finalize_data.get("tasks", [])
        if isinstance(task, Mapping) and isinstance(task.get("id"), str)
    }
    accepted = _accepted_task_result_envelopes(payload)
    rerun_results: list[dict[str, Any]] = []
    batch_id_set = set(batch_task_ids or [])
    for deferred_record in deferred:
        job_id = str(deferred_record.get("job_id") or "vj")
        task_id = str(deferred_record.get("task_id") or "")
        if task_id not in batch_id_set:
            # The pre-dispatch helper only emits deferred jobs for this batch,
            # but retain the guard if a caller supplies a mixed evidence list.
            continue
        job = jobs_by_id.get(job_id)
        task = tasks_by_id.get(task_id)
        accepted_row_and_envelope = accepted.get(task_id)
        if job is None or task is None:
            _raise_deferred_selector_result_block(
                job_id=job_id,
                task_id=task_id,
                reason="task_or_validation_job_missing_from_finalize_contract",
            )
        task_status = task.get("status") if isinstance(task, Mapping) else None
        if accepted_row_and_envelope is None:
            if task_status not in {"done", "completed"}:
                # Abort-recovery park: the worker aborted mid-batch (e.g. a
                # provider/transport failure) before minting an accepted result
                # envelope, so the declaring task is still pending.  Raising a
                # terminal block here would wedge the whole plan on a task that
                # was never completed.  Keep the persisted deferred evidence
                # untouched; the next resume re-dispatches the task and this
                # recheck re-runs once an accepted envelope appears.
                log.info(
                    "validation job %s remains deferred: task %s not complete "
                    "(status=%r), no accepted result envelope",
                    job_id,
                    task_id,
                    task_status,
                )
                continue
            _raise_deferred_selector_result_block(
                job_id=job_id,
                task_id=task_id,
                reason="accepted_task_result_envelope_missing",
            )
        _row, envelope = accepted_row_and_envelope
        # The grant-aware authority decision is recorded before the later
        # task-policy/write/test guardrails run.  A policy-blocked target must
        # therefore not release a deferred selector merely because that
        # earlier authority check said ``accepted``.
        if task_status == "blocked":
            # Post-merge policy block (e.g. test-budget admission gate): park
            # as a typed validation_blocked disposition instead of raising a
            # terminal refusal that kills the execute coordinator's aggregate
            # state publication.  The row stays blocked; the next
            # --retry-blocked-tasks dispatch resets it for a fresh compliant
            # attempt (authority adoption never overrides the gate).
            rerun_results.append(
                _park_post_merge_policy_block(
                    verification_dir=verification_dir,
                    job_id=job_id,
                    task_id=task_id,
                    task_status=task_status,
                )
            )
            continue
        if task_status not in {"done", "completed"}:
            _raise_deferred_selector_result_block(
                job_id=job_id,
                task_id=task_id,
                reason="task_result_not_completed_after_merge",
                extra={"task_status": task_status},
            )
        claim_payload = envelope.claim.payload
        if not isinstance(claim_payload, Mapping):
            _raise_deferred_selector_result_block(
                job_id=job_id,
                task_id=task_id,
                reason="accepted_task_result_payload_missing",
            )
        status = claim_payload.get("status")
        if status not in {"done", "completed"}:
            _raise_deferred_selector_result_block(
                job_id=job_id,
                task_id=task_id,
                reason="accepted_task_result_not_completed",
                extra={"status": status},
            )
        raw_files_changed = claim_payload.get("files_changed")
        if not isinstance(raw_files_changed, (list, tuple)) or not raw_files_changed:
            _raise_deferred_selector_result_block(
                job_id=job_id,
                task_id=task_id,
                reason="accepted_task_result_files_changed_missing_or_empty",
            )
        result_paths = {
            path
            for raw_path in raw_files_changed
            if (path := normalize_selector_path(raw_path)) is not None
        }
        missing_from_result = sorted(
            set(
                item
                for item in deferred_record.get("missing_selectors", [])
                if isinstance(item, str)
            )
            - result_paths
        )
        if missing_from_result:
            # Cross-task ownership: a deferred selector may be declared as an
            # output of ANOTHER admitted task (produced in this or a later
            # batch) rather than the owning task.  The owning task's accepted
            # result is not required to claim it; the deferred evidence stays
            # unresolved until the final sweep re-classifies it against the
            # graph.  Own-task outputs and no-task-declared paths remain
            # fail-closed exactly as before.
            own_outputs = set(declared_task_output_paths(task))
            graph_outputs = set(
                graph_declared_output_paths(finalize_data.get("tasks"))
            )
            own_declared_unclaimed = sorted(
                set(missing_from_result) & own_outputs
            )
            undeclared_missing = sorted(
                set(missing_from_result) - graph_outputs
            )
            other_task_declared = sorted(
                (set(missing_from_result) - own_outputs) & graph_outputs
            )
            if own_declared_unclaimed:
                _raise_deferred_selector_result_block(
                    job_id=job_id,
                    task_id=task_id,
                    reason="accepted_task_result_does_not_claim_selector_output",
                    extra={"missing_result_paths": own_declared_unclaimed},
                )
            if undeclared_missing:
                raise CliError(
                    "invalid_validation_job",
                    f"validation job {job_id} references missing selectors "
                    "that are not declared task outputs",
                    valid_next=["finalize", "revise"],
                    extra={
                        "job_id": job_id,
                        "invalid_fields": ["selectors"],
                        "missing_selectors": missing_from_result,
                        "undeclared_missing_selectors": undeclared_missing,
                        "validation_job_kind": "narrow_recheck",
                        "reason": "undeclared_missing_selector",
                    },
                )
            if other_task_declared:
                # A different admitted task may produce these paths in this or
                # a later batch.  Keep the persisted deferred evidence
                # unresolved; the final-batch sweep re-attempts the job once
                # every admitted task has run.
                log.info(
                    "validation job %s remains deferred: selectors %s are "
                    "declared outputs of other tasks, not the owning task %s",
                    job_id,
                    sorted(other_task_declared),
                    task_id,
                )
                continue

        lifecycle = classify_selector_lifecycle(
            project_dir=project_dir,
            job=job,
            task=task,
            all_declared_outputs=graph_declared_output_paths(
                finalize_data.get("tasks")
            ),
        )
        if lifecycle.status == SELECTOR_INVALID:
            raise CliError(
                "invalid_validation_job",
                f"validation job {job_id} references missing selectors "
                "that are not declared task outputs",
                valid_next=["finalize", "revise"],
                extra={
                    "job_id": job_id,
                    "invalid_fields": ["selectors"],
                    "missing_selectors": list(lifecycle.missing_selectors),
                    "undeclared_missing_selectors": list(
                        lifecycle.undeclared_missing_selectors
                    ),
                    "validation_job_kind": "narrow_recheck",
                },
            )
        if lifecycle.status == SELECTOR_DEFERRED:
            _raise_deferred_selector_result_block(
                job_id=job_id,
                task_id=task_id,
                reason="task_result_did_not_create_selector_output",
                extra={"missing_selectors": list(lifecycle.missing_selectors)},
            )

        # A deferred selector is a task-output path that did not exist at
        # pre-dispatch time; a no-new-failures delta job has no pre-task
        # state by construction, so NO delta job (explicit OR legacy-derived)
        # may be admitted through the deferred path with its delta lifecycle
        # (it would capture a fake "pre-envelope" against the post-task tree
        # and launder the post-adoption delta).  The strict recheck below
        # (``force_strict_gate``) is never weaker than the delta comparison
        # (occurrence 0a0ce24c3510) and equals it exactly for task-created
        # files (occurrence ae1f50c01dbd — explicit-delta TDD plans must not
        # wedge at the deferred recheck).
        # The rerun list is truncated to this single job; re-derive the
        # authoritative comparison ceiling from the FULL plan list.  Never
        # let the planner probe budget (120s) become a recheck deadline.
        _rerun_ceiling = _validation_comparison_ceiling(finalize_data)
        if _rerun_ceiling is None:
            _raise_deferred_selector_result_block(
                job_id=job_id,
                task_id=task_id,
                reason="comparison_budget_missing",
            )
        rerun_data = dict(finalize_data)
        rerun_data["validation_jobs"] = [dict(job)]
        rerun_results.extend(
            _run_batch_validation_jobs(
                plan_dir=plan_dir,
                project_dir=project_dir,
                finalize_data=rerun_data,
                batch_task_ids=[task_id],
                is_final_batch=False,
                state=state,
                comparison_ceiling_override=_rerun_ceiling,
                force_strict_gate=True,
            )
        )
    # ---- post-adoption delta recheck for captured pre-execution envelopes ----
    # A narrow_recheck whose pre-dispatch run captured a COMPLETE
    # pre-execution envelope (no-new-failures delta lifecycle) is not a
    # terminal pass.  After the task's accepted result envelope lands, re-run
    # the identical selectors against the merged state and compare against the
    # envelope: an unchanged failure set passes (even with raw exit 1); any
    # novel failure blocks and never carries authority.  The rerun is strict
    # (admission=False) — baseline subtraction is a pre-dispatch-only
    # admission, never a recheck.
    for envelope_record in enveloped:
        job_id = str(envelope_record.get("job_id") or "vj")
        job = jobs_by_id.get(job_id)
        if job is None:
            _raise_deferred_selector_result_block(
                job_id=job_id,
                task_id="",
                reason="task_or_validation_job_missing_from_finalize_contract",
            )
        task_id = str(job.get("task_id") or envelope_record.get("task_id") or "")
        if task_id not in batch_id_set:
            # The pre-dispatch helper only emits jobs for this batch, but
            # retain the guard if a caller supplies a mixed evidence list.
            continue
        task = tasks_by_id.get(task_id)
        accepted_row_and_envelope = accepted.get(task_id)
        if task is None:
            _raise_deferred_selector_result_block(
                job_id=job_id,
                task_id=task_id,
                reason="task_or_validation_job_missing_from_finalize_contract",
            )
        task_status = task.get("status") if isinstance(task, Mapping) else None
        if accepted_row_and_envelope is None:
            if task_status not in {"done", "completed"}:
                # Abort-recovery park (same shape as the deferred path): the
                # task never completed, so keep the envelope untouched; the
                # next resume re-dispatches the task and this recheck re-runs
                # once an accepted envelope appears.
                log.info(
                    "validation job %s delta recheck pending: task %s not "
                    "complete (status=%r), no accepted result envelope",
                    job_id,
                    task_id,
                    task_status,
                )
                continue
            _raise_deferred_selector_result_block(
                job_id=job_id,
                task_id=task_id,
                reason="accepted_task_result_envelope_missing",
            )
        if task_status == "blocked":
            # Same park-vs-raise split as the deferred path: a post-merge
            # policy block (test-budget admission gate) must not kill the
            # execute coordinator's aggregate state publication.  Park the
            # refusal as a typed validation_blocked disposition; the row
            # stays blocked and a fresh compliant attempt is still required.
            rerun_results.append(
                _park_post_merge_policy_block(
                    verification_dir=verification_dir,
                    job_id=job_id,
                    task_id=task_id,
                    task_status=task_status,
                )
            )
            continue
        if task_status not in {"done", "completed"}:
            _raise_deferred_selector_result_block(
                job_id=job_id,
                task_id=task_id,
                reason="task_result_not_completed_after_merge",
                extra={"task_status": task_status},
            )
        # A post-adoption delta check must fail closed when the task removed
        # one of its selectors — a missing selector is not a pass.
        missing_now = sorted(
            p
            for p in (job.get("selectors") or [])
            if isinstance(p, str) and not (Path(project_dir) / p).exists()
        )
        if missing_now:
            _raise_deferred_selector_result_block(
                job_id=job_id,
                task_id=task_id,
                reason="post_delta_selector_missing",
                extra={"missing_selectors": missing_now},
            )
        # Resume reuse: a durable POST_DELTA_PASSED artifact means this batch's
        # delta already passed — do not redo it (resume after pass does not
        # rerun).  A POST_DELTA_FAILED artifact is never reused: the candidate
        # must be reworked and the check re-run (resume after real fail does
        # not skip).
        try:
            _pd_artifact = _post_delta_artifact_path(verification_dir, job_id)
            if _pd_artifact.exists():
                _stored_pd = _json.loads(_pd_artifact.read_text(encoding="utf-8"))
            else:
                _stored_pd = None
        except Exception:
            _stored_pd = None
        if (
            isinstance(_stored_pd, dict)
            and _stored_pd.get("status") == POST_DELTA_PASSED
            and set(_stored_pd.get("selectors") or [])
            == set(job.get("selectors") or [])
            and _envelope_matches_current_tree(_stored_pd, project_dir)
            and _stored_pd.get("baseline_envelope_hash")
            == envelope_record.get("evidence_hash")
        ):
            rerun_results.append(_stored_pd)
            log.info(
                "validation job %s post-adoption delta already passed; skipping rerun",
                job_id,
            )
            continue
        # A stored PASS that does not match (selectors/command/source/envelope
        # drift) is never reused and never skipped: fall through to the strict
        # rerun against the current pre-envelope so the verdict is recomputed
        # on the merged state.  POST_DELTA_FAILED is never reused either —
        # the candidate must be reworked and the check re-run.
        # The rerun list is truncated to this single job; re-derive the
        # authoritative comparison ceiling from the persisted pre-envelope
        # first (recorded at capture time against the FULL job list), then
        # the full plan list.  Never let the planner probe budget (120s)
        # become the post-adoption deadline — the selectors take ~254s.
        _stored_ceiling = envelope_record.get("comparison_ceiling")
        _rerun_ceiling = (
            int(_stored_ceiling)
            if isinstance(_stored_ceiling, (int, float)) and _stored_ceiling > 0
            else _validation_comparison_ceiling(finalize_data)
        )
        if _rerun_ceiling is None:
            _raise_deferred_selector_result_block(
                job_id=job_id,
                task_id=task_id,
                reason="comparison_budget_missing",
            )
        rerun_data = dict(finalize_data)
        rerun_data["validation_jobs"] = [dict(job)]
        rerun_results.extend(
            _run_batch_validation_jobs(
                plan_dir=plan_dir,
                project_dir=project_dir,
                finalize_data=rerun_data,
                batch_task_ids=[task_id],
                is_final_batch=False,
                state=state,
                delta_baseline_envelope=dict(envelope_record),
                comparison_ceiling_override=_rerun_ceiling,
            )
        )
    return rerun_results


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
    finalize_data = load_finalize_for_update(plan_dir)
    if _repair_missing_user_action_gate(finalize_data, plan_dir, state):
        log.info(
            "backfilled missing before_execute user-action gate for stale finalize payload"
        )
    _guard_execute_batch_admission(plan_dir=plan_dir, finalize_data=finalize_data, state=state)
    global_config = load_config()
    quality_config = global_config.get("quality_checks", {})
    project_dir = Path(state["config"]["project_dir"])
    max_tasks_per_batch = _weight_aware_max_tasks_per_batch(
        _resolve_max_tasks_per_batch(state, args),
        (finalize_data.get("tasks") or []),
    )
    global_batches = _split_high_complexity(
        split_oversized_batches(
            compute_global_batches(finalize_data),
            max_tasks_per_batch,
        ),
        finalize_data,
        max_tasks_per_batch=max_tasks_per_batch,
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
    # Prior batch artifacts are observations until their result envelopes have
    # passed the accepted-attempt projection. Never copy their raw status into
    # scheduling inputs.
    schedulable_tasks = [task for task in tasks if isinstance(task, dict)]
    authority_decisions: dict[str, Any] = {}
    completed_ids = _scheduler_completed_ids_for_tasks(
        schedulable_tasks,
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

    # Adopt authority-completed blocked tasks before dispatching this batch: a
    # blocked row whose accepted-attempt kernel authority is dependency-closed
    # is promoted to done so (a) the batch-prerequisites check above passes and
    # (b) a deferred narrow recheck referencing the task revalidates instead of
    # refusing with task_result_blocked_by_post_merge_policy.  Mirrors the
    # auto-loop's adopt-after-merge in `_run_and_merge_batch`.
    authority_adopted_ids = _adopt_authority_completed_blocked_tasks(
        finalize_data,
        plan_dir=plan_dir,
        root=root,
        state=state,
    )
    if authority_adopted_ids:
        _publish_execute_finalize(
            plan_dir,
            finalize_data,
            operation="adopt-authority-completed-blocked(batch)",
            state=state,
        )
        log.info(
            "authority-adopt(batch): promoted %d authority-completed blocked task(s) to done: %s",
            len(authority_adopted_ids),
            ", ".join(authority_adopted_ids),
        )
        tasks = finalize_data.get("tasks", [])

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
    batch_prompt = _reconcile_prompt_override(
        plan_dir,
        _execute_batch_prompt(
            state,
            plan_dir,
            batch_task_ids,
            current_artifact_number=batch_number,
            completed_task_ids=completed_ids,
            root=root,
            batch_template_path=batch_template_path,
        ),
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
            tier_resolution = _resolve_tier_spec(args, resolution.spec)
            tier_agent, tier_mode, tier_model = (
                tier_resolution.agent,
                tier_resolution.mode,
                tier_resolution.resolved_model or tier_resolution.model,
            )
            tier_resolved_model = tier_model
            agent, mode, model = tier_agent, tier_mode, tier_model
            if tier_resolution.effort is not None:
                effort = tier_resolution.effort
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
                state,
                step="execute",
                agent=agent,
                mode=mode,
                model=model,
                run_id=(state.get("active_step") or {}).get("run_id"),
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
            configured_specs=_execute_configured_specs(
                args,
                selected_tier_spec=tier_spec_raw,
                default_spec=format_selected_spec(agent, model, effort) or agent,
            ),
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
        payload=result.payload,
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
    # Abort-recovery park (single-batch path): a batch task left non-terminal
    # after merge (worker aborted mid-batch, no accepted envelope) must surface
    # as a blocker, never as success with unfinished tasks.
    batch_blocked_id_set = set(batch_blocked_ids)
    batch_pending_left_behind_ids = [
        task.get("id")
        for task in tracked_tasks
        if task.get("id") in set(batch_task_ids)
        and task.get("status") not in TERMINAL_TASK_STATUSES
        and task.get("id") not in effective_completed_id_set
        and task.get("id") not in batch_blocked_id_set
    ]
    pending_left_behind_reason = _pending_left_behind_reason(
        batch_pending_left_behind_ids
    )
    if pending_left_behind_reason:
        blocking_reasons.append(pending_left_behind_reason)
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
            _publish_execute_finalize(
                plan_dir,
                finalize_data,
                operation="defer-baseline-checkpoints",
                state=state,
            )
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
        _publish_execute_finalize(
            plan_dir,
            finalize_data,
            operation="publish-aggregate-execute",
            state=state,
        )
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

    # Drop quality-gate blockers whose root cause is resolved (grok consult,
    # astrid m1): the one-batch path previously missed the drop that the
    # aggregate path applies, so an operator-resolved blocker (accepted_with_
    # debt / fixed) re-blocked the final batch on every execute even with a
    # clean 43/43-done finalize.  Mirrors the aggregate call after all
    # blocking_reasons (incl. scope drift) are built.
    blocking_reasons = _drop_resolved_quality_blocking_reasons(
        blocking_reasons,
        state=state,
    )
    routing_blocked = any(
        reason in blocking_reasons for reason in result.routing_degradations
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
    if is_final_batch and all_tracked and not blocked:
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
    batch_artifact = execute_batch_artifact_path(
        plan_dir, batch_number, batch_task_ids
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

    batches_remaining = batches_total - batch_number
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

    next_step_decision = resolve_single_batch_next_step(
        is_final_batch=is_final_batch,
        all_tracked=all_tracked,
        blocked=blocked,
    )
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

    # ── Evidence-only batch boundary receipts ──────────────────────────
    if next_step_decision.transition is NextExecuteTransition.BLOCKED:
        _emit_batch_boundary_receipt(
            boundary_id="execute_partial_failure",
            plan_dir=plan_dir,
            state=state,
            outcome=BoundaryOutcome.PARTIAL,
            artifact_refs=tuple(a for a in artifacts if isinstance(a, str)),
            batch_number=batch_number,
            batch_task_ids=list(batch_task_ids),
            extra_details={
                "blocking_reasons": blocking_reasons,
                "routing_blocked": routing_blocked,
                "batches_total": batches_total,
            },
        )
    elif next_step_decision.transition is NextExecuteTransition.REVIEW:
        # Aggregate promotion receipt with child trace/reducer evidence.
        child_trace_refs: dict[str, Any] = {}
        if aggregate_payload is not None:
            task_updates = aggregate_payload.get("task_updates", [])
            if isinstance(task_updates, list):
                child_trace_refs["task_count"] = len(task_updates)
            child_trace_refs["execution_json"] = "execution.json"
        _emit_batch_boundary_receipt(
            boundary_id="execute_aggregate_promotion",
            plan_dir=plan_dir,
            state=state,
            outcome=BoundaryOutcome.COMPLETE,
            artifact_refs=tuple(a for a in artifacts if isinstance(a, str)),
            batch_number=batch_number,
            batch_task_ids=list(batch_task_ids),
            extra_details={
                "reducer_promotion": True,
                "child_trace_path": "execute/aggregate",
                "child_trace_refs": child_trace_refs,
                "batches_total": batches_total,
            },
        )
    else:
        # Non-final, non-blocked batch → checkpoint receipt.
        _emit_batch_boundary_receipt(
            boundary_id="execute_batch_checkpoint",
            plan_dir=plan_dir,
            state=state,
            outcome=BoundaryOutcome.COMPLETE,
            artifact_refs=tuple(a for a in artifacts if isinstance(a, str)),
            batch_number=batch_number,
            batch_task_ids=list(batch_task_ids),
            extra_details={
                "batches_remaining": batches_remaining,
                "batches_total": batches_total,
            },
        )

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
        if task.get("status") == "blocked":
            _clear_task_attempt_fields(task)
            reset_ids.append(task_id)
            continue
        # Contradictory class (occurrence 0a0ce24c3510): a DONE row that still
        # carries the durable budget-block identity with NO admitted evidence.
        # A valid state can never contain one: the merge budget gate stamps the
        # field only on blocked/pending rows, the adopt helper pops it on
        # promote, and a compliant attempt produces evidence. They arise when
        # adopt runs before the proven-artifact replay stamps the envelope
        # budget identity into the row, so the adopt exclusion misses it and
        # promotes the budget-gated row to done without evidence — wedging the
        # quality gate ("done tasks missing both files_changed and
        # commands_run"). Return them to the runnable frontier for a fresh
        # compliant attempt; the durable field survives the reset (2f28baee99)
        # so the adopt gate keeps them out until that attempt passes.
        if (
            task.get("status") == "done"
            and isinstance(task.get("task_test_budget_exhausted"), str)
            and task["task_test_budget_exhausted"].strip()
            and not (task.get("files_changed") or task.get("commands_run"))
        ):
            _clear_task_attempt_fields(task)
            reset_ids.append(task_id)
    return sorted(reset_ids)


_TASK_TEST_BUDGET_MARKER = "[harness] task_test_budget_exhausted:"


def _is_task_test_budget_blocked(task: Mapping[str, Any]) -> bool:
    """True for a budget-gated row, INCLUDING after the retry reset.

    The merge gate stamps status="blocked" plus the marker in executor_notes.
    ``_clear_task_attempt_fields`` (the --retry-blocked-tasks reset) flips the
    row to pending and wipes notes, which previously erased the budget identity
    and let _adopt_authority_completed_blocked_tasks re-promote the
    authority-completed row to done WITHOUT evidence -> quality gate re-blocks
    (occurrence 0513dbf3f069 infinite loop). The durable
    ``task_test_budget_exhausted`` field (set by the merge gate, popped by the
    adopt helper on promote) survives the reset, so a pending row that was
    budget-gated still counts as budget-blocked and stays out of authority
    adoption until a fresh compliant attempt passes.
    """
    if task.get("status") not in ("blocked", "pending"):
        return False
    if isinstance(task.get("task_test_budget_exhausted"), str) and task["task_test_budget_exhausted"]:
        return True
    notes = task.get("executor_notes")
    return isinstance(notes, str) and (_TASK_TEST_BUDGET_MARKER in notes)


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
        refreshed = load_finalize_for_update(plan_dir)
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
        _publish_execute_finalize(
            plan_dir,
            finalize_data,
            operation="clear-resolved-prerequisite-blocks",
            state=state,
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
    """Demote terminal-success rows whose authority evidence went stale.

    A task is only durably ``done``/``completed`` when its result envelope
    carries strict accepted authority (terminal attempt status **and** an
    explicit grant-aware decision with outcome ``accepted`` — see
    ``accepted_attempt_execution_projection``).  Rows marked terminal by a
    merge that never produced such authority (e.g. hollow shadow-wave
    envelopes) must return to ``pending`` so the truthful frontier re-dispatches
    instead of being silently skipped by the scheduler and then rejected by the
    ``before_cursor_clear`` authority gate (``execute_authority_diverged``).

    The same reset applies to retryable aggregate-level blocks: a task blocked
    solely by the failed execute aggregate (scope drift, iteration-cap, budget
    exhaustion) has no durable authority either and must re-enter the frontier.
    Genuine task-level blockers (explicit prereq/user-action blocks with a
    recorded reason) remain blocked.
    """

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
        if not isinstance(task_id, str):
            continue
        if raw_status in {"done", "completed"}:
            terminal_without_authority = task_id not in completed_ids
        elif raw_status == "blocked":
            if task_id in completed_ids:
                continue
            if _has_genuine_task_level_blocker(task):
                continue
            terminal_without_authority = True
        else:
            continue
        if not terminal_without_authority:
            continue
        decision = decisions.get(task_id)
        if decision is not None and getattr(decision, "satisfied", False):
            continue
        _clear_task_attempt_fields(task)
        reset_ids.append(task_id)
    return sorted(reset_ids)


def _has_genuine_task_level_blocker(task: Mapping[str, Any]) -> bool:
    """True when a blocked task carries an explicit task-level blocker.

    Aggregate-level execute blocks (scope drift, iteration-cap, budget
    exhaustion) are recorded without a specific blocker reason/by set and are
    retryable.  Prereq/user-action blocks carry a concrete reason or by-set and
    must not be silently reset.

    ``validation_blocked`` is the typed disposition for a task-scoped
    worker/policy block with no accepted terminal authority (e.g. a
    verification-budget artifact: implemented but unverified).  It is NOT a
    genuine blocker: the row must return to the runnable frontier on a fresh
    session so a new worker session can re-verify it.  Only
    ``prerequisite_blocked`` (or explicit by/user-action/dependency fields)
    keeps a row parked across sessions.
    """
    for key in (
        "blocked_by",
        "blocked_by_user_action_ids",
        "unresolved_dependency_ids",
    ):
        value = task.get(key)
        if isinstance(value, str) and value.strip():
            return True
        if isinstance(value, (list, tuple, set)) and value:
            return True
    reason = task.get("blocked_reason")
    if isinstance(reason, str) and reason.strip():
        return reason.strip() != "validation_blocked"
    return False


def _envelope_budget_blocked_task_ids(plan_dir: Path) -> set[str]:
    """Task IDs whose PROVEN batch envelopes carry the durable budget-block
    identity (merge.py:_enforce_task_test_budgets stamps it on the entry and
    the target row). The adopt gate must consult these even when the finalize
    row has not yet been stamped: the execute auto-loop runs adopt before the
    proven-artifact replay, so a budget-gated row whose identity lives only in
    the envelope would otherwise be promoted to done WITHOUT evidence and the
    quality gate would re-block forever (occurrence 0a0ce24c3510, 24 rows).

    A task with a binding-valid budget-debt ACCEPTANCE receipt
    (``verification/task_budget_acceptance_<task-id>_*.json``) is subtracted:
    old immutable batch artifacts retain the original violation by design, but
    the acceptance receipt proves the block was reconciled after a current
    strict pass (occurrence 927ad612eda8), so it must not resurrect the block.
    """
    blocked: set[str] = set()
    for artifact_path in _all_batch_artifact_paths(plan_dir):
        try:
            payload = read_json(artifact_path)
        except (OSError, UnicodeDecodeError, ValueError):
            continue
        if not isinstance(payload, dict):
            continue
        for key in ("task_updates", "result_envelopes"):
            entries = payload.get(key)
            if not isinstance(entries, list):
                continue
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                task_id = entry.get("task_id") or entry.get("id")
                value = entry.get("task_test_budget_exhausted")
                if (
                    isinstance(task_id, str)
                    and isinstance(value, str)
                    and value.strip()
                ):
                    blocked.add(task_id)
    if blocked:
        verification_dir = Path(plan_dir) / "verification"
        accepted: set[str] = set()
        for receipt in verification_dir.glob(
            "task_budget_acceptance_*_*.json"
        ):
            try:
                receipt_data = read_json(receipt)
            except (OSError, UnicodeDecodeError, ValueError):
                continue
            if (
                isinstance(receipt_data, dict)
                and isinstance(receipt_data.get("task_id"), str)
                and receipt_data.get("disposition") == "accepted_with_debt"
            ):
                accepted.add(receipt_data["task_id"])
        blocked -= accepted
    return blocked


def _adopt_authority_completed_blocked_tasks(
    finalize_data: dict[str, Any],
    *,
    plan_dir: Path,
    root: Path | None,
    state: PlanState,
) -> list[str]:
    """Promote blocked/pending rows whose accepted-attempt authority is dependency-closed.

    A task can be terminal-success in the kernel authority (accepted attempt,
    dependencies closed) while finalize.json still shows ``blocked`` or
    ``pending``. Promote those stale rows, except a live test-budget rejection:
    accepted worker authority cannot override the merge admission gate, which
    requires a fresh compliant attempt.
    """

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
    adopted_ids: list[str] = []
    # Envelope-level budget identities: adopt runs before the proven-artifact
    # replay stamps the durable field into rows, so a budget-gated row whose
    # identity lives only in its batch envelope must still be excluded
    # (occurrence 0a0ce24c3510 — adopt-before-replay promoted 24 budget-gated
    # rows to done without evidence, wedging the quality gate).
    envelope_budget_blocked = _envelope_budget_blocked_task_ids(plan_dir)
    for task in tasks:
        if not isinstance(task, dict):
            continue
        task_id = task.get("id")
        raw_status = task.get("status")
        if not isinstance(task_id, str):
            continue
        # Promote rows whose accepted-attempt kernel authority is satisfied:
        # blocked (stale harness projection) AND pending (the finalize status
        # lags a substantively-complete batch — the worktree + accepted
        # envelopes satisfy the contract while finalize.json still shows
        # pending, e.g. astrid m1 batch-22 T41 dependency record).  The
        # authority reader is the source of truth; a pending task with NO
        # accepted envelope stays pending.
        if raw_status not in {"blocked", "pending"}:
            continue
        if _is_task_test_budget_blocked(task):
            continue
        if task_id in envelope_budget_blocked:
            continue
        if task_id not in completed_ids:
            continue
        decision = decisions.get(task_id)
        if decision is None or not getattr(decision, "satisfied", False):
            continue
        task["status"] = "done"
        for key in (
            "blocked_reason",
            "blocked_by",
            "task_test_budget_exhausted",
            "blocked_attempt_ids",
            "unresolved_dependency_ids",
        ):
            task.pop(key, None)
        adopted_ids.append(task_id)
    return sorted(adopted_ids)


_BASELINE_VERIFICATION_MARKER = "introduce no new failures vs the recorded baseline"
_BASELINE_UNAVAILABLE_BLOCKER_KIND = "baseline-unavailable-no-new-failures-checkpoint"
# The baseline-unavailable deferral is a VERIFICATION-only disposition: it
# exists for tasks whose contract is "introduce no new failures vs the
# recorded baseline". Implementation (code) tasks must never be deferred by
# it, even when their description happens to carry the boilerplate marker —
# deferring them launders real implementation work into a fake "skipped"
# completion (observed: m3 T4, kind=code, was marked skipped by
# _defer_baseline_unavailable_checkpoints with no authority/envelope
# evidence, leaving the projection to re-work it while finalize accounting
# mislabeled it done). "audit" is the kind used for *_proof tasks in current
# plans; "proof"/"verification" are accepted aliases for other naming
# conventions. The description marker must still match, so this can only
# NARROW the set of deferrable tasks.
_BASELINE_VERIFICATION_KINDS = frozenset({"audit", "proof", "verification"})


def _is_baseline_dependent_verification_task(task: dict[str, Any]) -> bool:
    kind = task.get("kind")
    if not isinstance(kind, str) or kind not in _BASELINE_VERIFICATION_KINDS:
        return False
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


def _partition_review_rework_tasks(
    task_ids: list[str],
    *,
    ceiling: int = _MAX_SERIAL_REWORK,
) -> list[list[str]]:
    """Partition one review wave without changing its ordered task frontier.

    The serial ceiling constrains a single worker dispatch, not the total
    number of legitimate findings a review may return. Preserve every routed
    task exactly once and let the existing review-cycle/non-convergence guards
    bound the overall loop.
    """

    return split_oversized_batches([list(task_ids)], ceiling) if task_ids else []


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
        if not isinstance(item, dict):
            continue
        candidate_task_ids, _ = _rework_item_target_task_ids(item)
        matched_task_ids = [task_id for task_id in candidate_task_ids if task_id in wanted]
        if not matched_task_ids:
            continue
        evidence_file = item.get("evidence_file", "")
        normalized = {
            "task_id": item.get("task_id"),
            "task_ids": matched_task_ids,
            "target": item.get("target"),
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


def _scoped_successors_for_failed_validation(
    validation_jobs: list[Mapping[str, Any]],
    validation_results: list[Mapping[str, Any]],
    accepted_task_ids: set[str] | frozenset[str],
) -> list[str]:
    """Derive scoped successor tasks from FAILED bounded validation jobs.

    A bulk/manifest/global review rework item is admitted as a validation-only
    job: the accepted task_ids it names are suppressed, not reopened.  When
    the deterministic check FAILS, the engine demands a "scoped successor
    task" — the named accepted tasks ARE those successors.  This helper
    returns the accepted task_ids covered by failed jobs (in job order,
    deduplicated), or [] when no job fails / no job covers accepted tasks.
    """
    successors: list[str] = []
    for job, result in zip(validation_jobs, validation_results):
        if not (
            result.get("error")
            or result.get("timed_out")
            or result.get("exit_code") != 0
        ):
            continue
        covered = job.get("task_ids") or []
        for task_id in covered:
            if task_id in accepted_task_ids and task_id not in successors:
                successors.append(task_id)
    return successors


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


def _dependency_closed_blocked_task_ids(
    tasks: Iterable[Mapping[str, Any]],
    blocked_task_ids: Iterable[str],
) -> set[str]:
    """Return blocked ids plus every task that transitively depends on them.

    The execute auto-loop parks task-level blocks (kept at status=blocked with
    a typed disposition) and continues with the dependency-independent
    runnable frontier. Tasks whose dependency closure contains a parked block
    must stay out of that frontier because their prerequisites are
    unsatisfied; they remain pending so a later session can retry them once
    the block resolves.
    """
    blocked = {str(task_id) for task_id in blocked_task_ids if task_id}
    dependents: dict[str, set[str]] = {}
    for task in tasks:
        if not isinstance(task, Mapping):
            continue
        task_id = task.get("id")
        if isinstance(task_id, str) and task_id:
            dependents.setdefault(task_id, set())
    for task in tasks:
        if not isinstance(task, Mapping):
            continue
        task_id = task.get("id")
        if not isinstance(task_id, str) or task_id not in dependents:
            continue
        deps = task.get("depends_on")
        if not isinstance(deps, list):
            continue
        for dep in deps:
            if isinstance(dep, str) and dep in dependents:
                dependents[dep].add(task_id)
    closed = set(blocked)
    changed = True
    while changed:
        changed = False
        for dep, dependent_ids in dependents.items():
            if dep not in closed:
                continue
            for dependent_id in dependent_ids:
                if dependent_id not in closed:
                    closed.add(dependent_id)
                    changed = True
    return closed


def _park_blocked_task_dispositions(
    finalize_data: Mapping[str, Any],
    newly_blocked_task_ids: Iterable[str],
    current_invocation_id: str,
) -> None:
    """Stamp typed blocker dispositions onto newly blocked tasks.

    Each task the worker reported status=blocked for gets a typed
    ``blocked_reason``: ``prerequisite_blocked`` when it carries an explicit
    prereq/user-action blocker (``_has_genuine_task_level_blocker``), otherwise
    ``validation_blocked`` (a task-scoped worker/policy block with no accepted
    terminal authority — e.g. a verification-budget artifact). The row also
    keeps its ``recorded_invocation_id`` so the cross-session reset path can
    distinguish within-session from fresh-session blocks. Dispositions are
    never flipped back to pending within the same invocation.
    """
    blocked_set = {str(task_id) for task_id in newly_blocked_task_ids if task_id}
    if not blocked_set:
        return
    for task in finalize_data.get("tasks", []):
        if not isinstance(task, dict):
            continue
        if task.get("id") not in blocked_set:
            continue
        if _has_genuine_task_level_blocker(task):
            task["blocked_reason"] = "prerequisite_blocked"
        else:
            task["blocked_reason"] = "validation_blocked"
        if current_invocation_id:
            task["recorded_invocation_id"] = current_invocation_id


def _recompute_runnable_batches(
    finalize_data: Mapping[str, Any],
    *,
    completed_task_ids: set[str],
    state: PlanState,
    args: argparse.Namespace,
) -> list[list[str]]:
    """Recompute the runnable batch frontier after task-level blocks.

    Blocked tasks (parked at status=blocked with a typed disposition) and
    their transitive dependents are excluded; the remaining pending tasks are
    re-batched with the same pipeline used for the initial frontier
    (topological batches, oversized split, weight-aware cap, high-complexity
    isolation). Returns an empty list when no runnable frontier remains.
    """
    tasks = finalize_data.get("tasks") or []
    if not isinstance(tasks, list):
        return []
    blocked_ids = {
        task["id"]
        for task in tasks
        if isinstance(task, Mapping)
        and isinstance(task.get("id"), str)
        and task.get("status") == "blocked"
        and task["id"] not in completed_task_ids
    }
    if not blocked_ids:
        return []
    excluded = _dependency_closed_blocked_task_ids(tasks, blocked_ids)
    runnable = [
        task
        for task in tasks
        if isinstance(task, Mapping)
        and isinstance(task.get("id"), str)
        and task.get("status") != "blocked"
        and task["id"] not in completed_task_ids
        and task["id"] not in excluded
    ]
    if not runnable:
        return []
    pending_batches = compute_task_batches(runnable, completed_ids=completed_task_ids)
    max_tasks_per_batch = _weight_aware_max_tasks_per_batch(
        _resolve_max_tasks_per_batch(state, args),
        tasks,
    )
    return _split_high_complexity(
        split_oversized_batches(pending_batches, max_tasks_per_batch),
        finalize_data,
        max_tasks_per_batch=max_tasks_per_batch,
    )


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
    finalize_data = load_finalize_for_update(plan_dir)
    if _repair_missing_user_action_gate(finalize_data, plan_dir, state):
        log.info(
            "backfilled missing before_execute user-action gate for stale finalize payload"
        )
    _guard_execute_batch_admission(plan_dir=plan_dir, finalize_data=finalize_data, state=state)
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
        # Accepted worker authority cannot suppress a fresh retry of a result
        # rejected by the merge-layer test-budget admission gate.
        authority_completed_before_retry.difference_update(
            task["id"] for task in tasks
            if isinstance(task, dict) and isinstance(task.get("id"), str)
            and (
                _is_task_test_budget_blocked(task)
                or is_contradictory_done_budget_row(task)
            )
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
            _publish_execute_finalize(
                plan_dir,
                finalize_data,
                operation="retry-blocked-tasks",
                state=state,
            )
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
        _publish_execute_finalize(
            plan_dir,
            finalize_data,
            operation="repair-user-action-gate",
            state=state,
        )
        log.info(
            "stale-authority-retry: reset %d stale done task(s) to pending: %s",
            len(stale_authority_reset_ids),
            ", ".join(stale_authority_reset_ids),
        )
        tasks = finalize_data.get("tasks", [])

    authority_adopted_ids = _adopt_authority_completed_blocked_tasks(
        finalize_data,
        plan_dir=plan_dir,
        root=root,
        state=state,
    )
    if authority_adopted_ids:
        _publish_execute_finalize(
            plan_dir,
            finalize_data,
            operation="adopt-authority-completed-blocked",
            state=state,
        )
        log.info(
            "authority-adopt: promoted %d authority-completed blocked task(s) to done: %s",
            len(authority_adopted_ids),
            ", ".join(authority_adopted_ids),
        )
        tasks = finalize_data.get("tasks", [])

    deferred_checkpoint_ids, deferred_acks = _defer_baseline_unavailable_checkpoints(
        finalize_data
    )
    if deferred_checkpoint_ids:
        baseline_unavailable_acks.extend(deferred_acks)
        _publish_execute_finalize(
            plan_dir,
            finalize_data,
            operation="defer-interim-baseline-checkpoints",
            state=state,
        )
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
    # Contradictory done-budget rows (astrid fix 4d39b18d33): a DONE row
    # that still carries the durable budget-block identity with NO admitted
    # evidence cannot be produced by any valid flow (adopt-before-replay
    # artifact) and must return to the runnable frontier for a fresh
    # compliant attempt.  The --retry-blocked-tasks partition reruns them,
    # but the PLAIN resume path (no flag) must do the same, or execute
    # stays blocked on "done tasks missing both files_changed and
    # commands_run" forever (occurrence 927ad612eda8, live regression
    # 2026-08-19T12:12Z).  Review-rework scopes are preserved (review.json
    # present = scoped frontier is authoritative).
    if not (plan_dir / "review.json").exists():
        contradictory_ids = [
            task["id"]
            for task in tasks
            if isinstance(task, dict)
            and isinstance(task.get("id"), str)
            and is_contradictory_done_budget_row(task)
        ]
        if contradictory_ids:
            for task in tasks:
                if (
                    isinstance(task, dict)
                    and isinstance(task.get("id"), str)
                    and task["id"] in contradictory_ids
                ):
                    _clear_task_attempt_fields(task)
            log.info(
                "resume: returned %d contradictory done-budget row(s) to the "
                "runnable frontier for a fresh compliant attempt: %s",
                len(contradictory_ids),
                ", ".join(sorted(contradictory_ids)),
            )
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
                from arnold_pipelines.megaplan.orchestration.rework_admission import (
                    reconcile_review_rework,
                )
                review_revision = None
                review_evidence_path = plan_dir / "review_evidence.json"
                if review_evidence_path.exists():
                    try:
                        review_evidence = read_json(review_evidence_path)
                    except (OSError, UnicodeDecodeError, ValueError):
                        review_evidence = {}
                    if isinstance(review_evidence, dict):
                        raw_revision = review_evidence.get("head_sha")
                        if isinstance(raw_revision, str) and raw_revision:
                            review_revision = raw_revision
                authority_revision = _best_effort_git_head(root)
                rework_admission = reconcile_review_rework(
                    review_data,
                    known_task_ids=set(all_task_ids),
                    accepted_task_ids=set(completed_task_ids),
                    authority_revision=authority_revision,
                    review_revision=review_revision,
                )
                atomic_write_json(
                    plan_dir / "review_rework_admission.json",
                    rework_admission.to_dict(),
                )
                review_rework_task_ids = list(rework_admission.runnable_task_ids)
                unrunnable_rework_task_ids = [
                    str(row.get("code") or "rework_admission_blocked")
                    for row in rework_admission.blockers
                ]
                validation_only_satisfied = False
                if rework_admission.validation_jobs:
                    import shlex as _shlex
                    from arnold_pipelines.megaplan.execute.validation_runner import (
                        run_single_validation_job,
                    )

                    validation_results = []
                    for job in rework_admission.validation_jobs:
                        validation_results.append(
                            run_single_validation_job(
                                {
                                    "id": job["id"],
                                    "command": _shlex.split(str(job["command"])),
                                    "environment": {},
                                    "timeout_seconds": 600,
                                    "expected_output_paths": [],
                                },
                                project_dir=Path(root),
                            ).as_dict()
                        )
                    atomic_write_json(
                        plan_dir / "review_rework_validation.json",
                        {
                            "schema": "megaplan.review_rework_validation",
                            "schema_version": 1,
                            "authority_digest": rework_admission.authority_digest,
                            "results": validation_results,
                        },
                    )
                    failed_validation = [
                        row
                        for row in validation_results
                        if row.get("error") or row.get("timed_out") or row.get("exit_code") != 0
                    ]
                    if failed_validation and not review_rework_task_ids:
                        # A failing bulk/manifest/global validation job names
                        # the accepted tasks it covered (review rework item's
                        # task_ids).  The admission treats bulk+check as
                        # validation-only and suppresses those accepted ids, so
                        # without this reopen the plan dead-ends on "scoped
                        # successor task is required" — the named accepted
                        # tasks ARE the scoped successors the message demands.
                        # Reopen exactly the accepted tasks covered by FAILED
                        # jobs; the deterministic check failing is the proof of
                        # regression (no laundering: tasks must re-run and pass
                        # verification again).  Jobs whose task_ids are not in
                        # the accepted set contribute nothing here.
                        accepted_set = set(completed_task_ids)
                        failed_job_successors = _scoped_successors_for_failed_validation(
                            rework_admission.validation_jobs,
                            validation_results,
                            accepted_set,
                        )
                        if failed_job_successors:
                            review_rework_task_ids = failed_job_successors
                            log.info(
                                "review bulk verification failed; reopening scoped "
                                "successors %s (covered by failed validation job)",
                                sorted(failed_job_successors),
                            )
                        else:
                            return _block_no_runnable_rework(
                                plan_dir=plan_dir,
                                state=state,
                                auto_approve=auto_approve,
                                reason=(
                                    "review bulk verification failed its bounded validation "
                                    "job; a scoped successor task is required"
                                ),
                            )
                    validation_only_satisfied = not review_rework_task_ids
                if not review_rework_task_ids and not validation_only_satisfied:
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
                rework_mode = bool(review_rework_task_ids)
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
            _publish_execute_finalize(
                plan_dir,
                finalize_data,
                operation="reset-blocked-after-user-action",
                state=state,
            )
            # Recompute blocked_task_ids after reset — should now be empty
            blocked_task_ids = {
                task["id"]
                for task in tasks
                if task.get("status") == "blocked" and isinstance(task.get("id"), str)
                and task["id"] not in completed_task_ids
            }
            # Recompute the runnable frontier too: reset tasks must rejoin
            # pending_tasks, otherwise a pending dependent (T29 -> T28) keeps
            # referencing a task absent from the batch graph and
            # compute_task_batches raises "Unknown dependency ID" (occurrence
            # 927ad612eda8, resume after cross-session blocked-task reset).
            # The review-rework frontier (explicit scoped task list) is
            # preserved when active.
            if not rework_mode:
                pending_tasks = [
                    task
                    for task in tasks
                    if isinstance(task.get("id"), str)
                    and task.get("status") != "blocked"
                    and task.get("id") not in completed_task_ids
                ]
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
                _publish_execute_finalize(
                    plan_dir,
                    finalize_data,
                    operation="defer-short-circuit-checkpoints",
                    state=state,
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
    max_tasks_per_batch = _weight_aware_max_tasks_per_batch(
        _resolve_max_tasks_per_batch(state, args),
        (finalize_data.get("tasks") or []) if isinstance(finalize_data, Mapping) else pending_tasks,
    )
    split_batches = _split_high_complexity(
        split_oversized_batches(pending_batches, max_tasks_per_batch),
        finalize_data,
        max_tasks_per_batch=max_tasks_per_batch,
    )
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
    global_batches = _split_high_complexity(
        split_oversized_batches(
            compute_global_batches(finalize_data),
            max_tasks_per_batch,
        ),
        finalize_data,
        max_tasks_per_batch=max_tasks_per_batch,
    )
    global_batch_lookup = {
        tuple(batch): index + 1 for index, batch in enumerate(global_batches)
    }
    task_to_batch_number = _task_to_global_batch_number_map(global_batches)
    no_pending_execution = not pending_tasks and not rework_mode
    # The review-wave ceiling is a per-dispatch bound. A legitimate review may
    # route more tasks than that, so partition the ordered frontier while
    # preserving the existing cycle and non-convergence limits.
    if rework_mode and isinstance(review_rework_task_ids, list) and review_rework_task_ids:
        _wave_size = len(review_rework_task_ids)
        review_rework_batches = _partition_review_rework_tasks(
            review_rework_task_ids,
            ceiling=_MAX_SERIAL_REWORK,
        )
        if len(review_rework_batches) > 1:
            log.info(
                "partitioning review rework wave of %d task(s) into %d "
                "bounded dispatches (ceiling=%d)",
                _wave_size,
                len(review_rework_batches),
                _MAX_SERIAL_REWORK,
            )
            try:
                from arnold_pipelines.megaplan.observability.events import EventKind, emit

                emit(
                    EventKind.STATE_TRANSITION,
                    plan_dir=plan_dir,
                    phase="execute",
                    payload={
                        "rework_wave_size": _wave_size,
                        "ceiling": _MAX_SERIAL_REWORK,
                        "rework_task_ids": list(review_rework_task_ids),
                        "subwaves": review_rework_batches,
                        "reason": "review_rework_wave_partitioned",
                    },
                )
            except Exception:
                pass
    else:
        review_rework_batches = []
    batches_to_run = (
        review_rework_batches
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
            _publish_execute_finalize(
                plan_dir,
                finalize_data,
                operation="resume-loaded-batches",
                state=state,
            )
            # The persisted execution_audit.json may predate the replayed
            # evidence (e.g. a quality-gate block recorded findings before the
            # replay backfilled files_changed/commands_run from accepted
            # waves). Invalidate it so downstream prompts and review never read
            # stale findings; the aggregate path recomputes and rewrites it
            # fresh after replay. (chain-gate escalation)
            stale_audit = plan_dir / "execution_audit.json"
            if stale_audit.exists():
                try:
                    stale_audit.unlink()
                    log.info("invalidated stale execution_audit.json before replay aggregation")
                except OSError:
                    log.warning("could not remove stale execution_audit.json", exc_info=True)
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
    pending_left_behind_task_ids: set[str] = set()
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

    # Dependency-aware continuation: the loop is a re-derivable frontier
    # queue. When a task-level block parks one or more tasks, the remaining
    # runnable frontier is recomputed and the loop continues, so a single
    # budget-blocked task cannot strand dependency-independent batches.
    # ``batch_index`` is a monotonic dispatch ordinal (never reset), so
    # re-derived batches always receive fresh artifact slots.
    batch_index = 0
    while batch_index < len(batches_to_run):
        batch_index += 1
        batch_task_ids = batches_to_run[batch_index - 1]
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
            else _reconcile_prompt_override(
                plan_dir,
                _execute_batch_prompt(
                    state,
                    plan_dir,
                    batch_task_ids,
                    current_artifact_number=batch_number_for_artifact,
                    completed_task_ids=completed_task_ids,
                    root=root,
                    rework_context=(
                        _review_rework_context(
                            review_data, finalize_data, batch_task_ids
                        )
                        if rework_mode
                        else None
                    ),
                    batch_template_path=batch_template_path,
                ),
            )
        )
        batches_total_for_observation = total_batches

        # Per-batch tier resolution: select the model for the max task
        # complexity in this batch.  Falls back to the caller-provided
        # agent/mode/model when tier_map is None or the complexity has no entry.
        batch_agent, batch_mode, batch_refreshed, batch_model = (
            agent, mode, refreshed, model
        )
        batch_effort = effort
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
                tier_resolution = _resolve_tier_spec(args, resolution.spec)
                tier_agent, tier_mode, tier_model = (
                    tier_resolution.agent,
                    tier_resolution.mode,
                    tier_resolution.resolved_model or tier_resolution.model,
                )
                batch_agent, batch_mode, batch_model = (
                    tier_agent, tier_mode, tier_model
                )
                batch_effort = (
                    tier_resolution.effort
                    if tier_resolution.effort is not None
                    else effort
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
                    run_id=(state.get("active_step") or {}).get("run_id"),
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
                effort=batch_effort,
                resolved_model=batch_resolved_model,
                prompt_override=batch_prompt,
                batch_task_ids=batch_task_ids,
                batch_sense_check_ids=batch_sense_check_ids,
                finalize_data=finalize_data,
                batch_number=batch_number_for_artifact,
                batches_total=batches_total_for_observation,
                quality_config=quality_config,
                routing_record=routing_record,
                configured_specs=_execute_configured_specs(
                    args,
                    selected_tier_spec=batch_tier_spec,
                    default_spec=(
                        format_selected_spec(batch_agent, batch_model, effort)
                        or batch_agent
                    ),
                ),
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
                finalize_data = load_finalize_for_update(plan_dir)
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
        # Stamp each newly-blocked task with the current invocation_id and a
        # typed blocker disposition so the short-circuit can distinguish
        # within-session from cross-session blocks and the phase result can
        # carry the blocker kind.
        current_inv_id = (state.get("meta") or {}).get("current_invocation_id", "")
        if newly_blocked_task_ids:
            _park_blocked_task_dispositions(
                finalize_data,
                newly_blocked_task_ids,
                current_inv_id,
            )
        blocking_reasons = build_blocking_reasons(
            tracked_tasks=result.merged_task_count,
            total_tasks=result.total_task_count,
            acknowledged_checks=result.acknowledged_sense_check_count,
            total_checks=result.total_sense_check_count,
            missing_task_evidence=result.missing_task_evidence,
            payload=result.payload,
        )
        blocked_task_reason = _blocked_task_reason(newly_blocked_task_ids)
        if blocked_task_reason:
            blocking_reasons.append(blocked_task_reason)
        # Abort-recovery stop: a batch task that is still non-terminal after
        # merge (worker aborted mid-batch, no accepted envelope, not
        # authority-completed) must not silently pass.  Park it and stop the
        # loop so dependent chunks are not dispatched against a still-pending
        # prerequisite; the next resume recomputes the frontier and re-dispatches
        # the pending task.
        current_batch_noncomplete_ids = {
            task["id"]
            for task in finalize_data.get("tasks", [])
            if isinstance(task, Mapping)
            and isinstance(task.get("id"), str)
            and task["id"] in set(batch_task_ids)
            and task.get("status") not in TERMINAL_TASK_STATUSES
        }
        current_batch_pending_left_behind = (
            current_batch_noncomplete_ids - newly_blocked_task_ids
        )
        pending_left_behind_task_ids.update(current_batch_pending_left_behind)
        pending_left_behind_reason = _pending_left_behind_reason(
            current_batch_pending_left_behind
        )
        if pending_left_behind_reason:
            blocking_reasons.append(pending_left_behind_reason)
        # Break only on aggregate quality reasons (untracked task updates,
        # sense-check gaps, missing evidence) or when no runnable frontier
        # remains. A sole task-level block (worker reported status=blocked for
        # task(s) in this batch) parks the blocked tasks with a typed
        # disposition and continues with the dependency-independent frontier
        # instead of halting the whole phase.
        if blocking_reasons and not (
            blocked_task_reason is not None and len(blocking_reasons) == 1
        ):
            agent = result.agent
            mode = result.mode
            refreshed = result.refreshed
            break
        if newly_blocked_task_ids:
            recomputed = _recompute_runnable_batches(
                finalize_data,
                completed_task_ids=completed_task_ids,
                state=state,
                args=args,
            )
            if recomputed:
                # Preserve the monotonic dispatch cursor: keep the already
                # consumed prefix and replace the REMAINING queue with the
                # recomputed runnable frontier (blocked-task dependents and
                # completed work excluded), so the cursor advances onto the
                # fresh remainder instead of overshooting the shorter list
                # (occurrence 4c0190500877: T16 stayed undispatched after the
                # batch-12 budget block even though it was dependency-free).
                batches_to_run = batches_to_run[:batch_index] + recomputed
                log.info(
                    "task-level block(s) %s parked; continuing with %d "
                    "runnable batch(es) excluding their dependents",
                    sorted(newly_blocked_task_ids),
                    len(recomputed),
                )
            else:
                agent = result.agent
                mode = result.mode
                refreshed = result.refreshed
                break
        # Success-path frontier rescan (grok consult 2026-08-16, astrid m2
        # T19-T27 never dispatched): after a batch that COMPLETED tasks,
        # newly-eligible dependents (their deps now done) must be dispatched
        # in THIS invocation. Previously the loop walked a FROZEN batch list —
        # compute_task_batches put T19/T22/... in later layers of the initial
        # split, the auto-loop never rescanned after a successful merge, and
        # the quality gate then flagged them as "executor never started them".
        # The only mid-run rescan was the task-level-block path above, which
        # replaces batches_to_run with the independent remainder while
        # batch_index stays ahead of the shorter list -> zero of the new
        # queue ran. Recompute the frontier with the updated completed set and
        # APPEND the newly-eligible batches (deduped) so the loop cursor
        # naturally continues onto them.
        else:
            frontier = _recompute_runnable_batches(
                finalize_data,
                completed_task_ids=completed_task_ids,
                state=state,
                args=args,
            )
            if frontier:
                existing = {
                    task_id for batch in batches_to_run for task_id in batch
                }
                fresh = [
                    batch
                    for batch in frontier
                    if any(task_id not in existing for task_id in batch)
                ]
                if fresh:
                    batches_to_run = batches_to_run + fresh
                    log.info(
                        "frontier rescan: %d newly-eligible dependent "
                        "batch(es) appended after completed batch",
                        len(fresh),
                    )
        agent = result.agent
        mode = result.mode
        refreshed = result.refreshed

    plan_mode = state["config"].get("mode", "code")
    # Replay every independently proven batch artifact (including same-index
    # waves shadowed by a newer preferred attempt) through the scoped merge
    # validator, so accepted rows from earlier waves backfill evidence and
    # acknowledgments before the authoritative completion/quality checks.
    # Idempotent and validator-gated: authority IDs persist only on pass.
    # (occurrence 0ae19cc17afd)
    _replay_proven_batch_artifacts(
        plan_dir=plan_dir,
        finalize_data=finalize_data,
        known_task_ids=all_task_ids,
        known_sense_check_ids=all_sense_check_ids,
        mode=plan_mode,
        state=state,
    )
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

    # Keep the in-memory merged ledger: batches merge accepted acks/task results
    # into it and interim finalize.json is not published, so reloading here
    # would discard that evidence before aggregate accounting and final publish.
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
    _publish_execute_finalize(
        plan_dir,
        finalize_data,
        operation="publish-execute-completion",
        state=state,
    )
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
    tracked_tasks, total_tasks, acknowledged_checks, total_checks = (
        _count_execute_tracking(
            finalize_data,
            active_task_ids=active_task_ids,
            active_sense_check_ids=active_sense_check_ids,
            completed_task_ids=completed_task_ids,
            plan_dir=plan_dir,
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
        payload=(batch_payloads[-1] if batch_payloads else None),
    )
    # Carry the abort-recovery park into the phase-final decision: the in-loop
    # blocking_reasons list is rebuilt above, so a pending-left-behind task must
    # be re-appended here or the phase would report success with unfinished
    # tasks.  ``completed_task_ids`` was recomputed from the merged finalize
    # data, so tasks that completed during the loop are dropped from the set.
    pending_left_behind_task_ids.difference_update(completed_task_ids)
    pending_left_behind_reason = _pending_left_behind_reason(
        pending_left_behind_task_ids
    )
    if pending_left_behind_reason:
        blocking_reasons.append(pending_left_behind_reason)
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
    ) - completed_task_ids
    blocked_task_reason = _blocked_task_reason(active_blocked_task_ids)
    if blocked_task_reason:
        blocking_reasons.append(blocked_task_reason)
    blocking_reasons.extend(_deviation_messages(baseline_deviations))
    _append_scope_drift_blocker(blocking_reasons, state, drift)
    if routing_degradations:
        blocking_reasons.extend(routing_degradations)

    # Drop quality-gate blockers whose root cause the operator resolved as
    # non-terminal debt (accepted_with_debt / fixed).  This MUST run after the
    # blocked-task and scope-drift reasons are appended: the one-batch path
    # drops after drift (see the grok astrid m1 consult) and the aggregate
    # auto-loop path must mirror it, otherwise an operator resolution can never
    # clear the two recurring auto-loop park reasons (blocked task carried in
    # blocked_task_ids + scope_drift_severity=high) and the plan loops
    # blocked -> recover-blocked -> execute -> same deviation forever.
    blocking_reasons = _drop_resolved_quality_blocking_reasons(
        blocking_reasons,
        state=state,
    )

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
    blocked_task_kinds: dict[str, str] = {}
    if prereq_blocked_task_ids:
        for task in finalize_data.get("tasks", []):
            tid = task.get("id")
            if isinstance(tid, str) and tid in prereq_blocked_task_ids:
                notes = task.get("executor_notes") or ""
                if notes:
                    blocked_task_notes[tid] = str(notes)
                reason = task.get("blocked_reason")
                if isinstance(reason, str) and reason:
                    blocked_task_kinds[tid] = reason

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
    if phase_outcome == "blocked_by_prereq":
        response["blocked_task_ids"] = sorted(prereq_blocked_task_ids)
    elif active_blocked_task_ids:
        response["blocked_task_ids"] = sorted(active_blocked_task_ids)
    if deferred_evidence:
        response["deferred_evidence"] = deferred_evidence
    if routing_blocked:
        response["result"] = "blocked"
    if blocked_task_notes:
        response["blocked_task_notes"] = blocked_task_notes
    if blocked_task_kinds:
        response["blocked_task_kinds"] = blocked_task_kinds
    _attach_next_step_runtime(response)
    return response