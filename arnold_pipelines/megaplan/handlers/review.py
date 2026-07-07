from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import dataclass
import logging
import os
from pathlib import Path
from typing import Any

from arnold_pipelines.megaplan import handlers as _pkg
from arnold_pipelines.megaplan.review import checks as review_checks
from arnold_pipelines.megaplan.execute.quality import _check_done_task_evidence
from arnold_pipelines.megaplan.execute.batch import build_monitor_hint
from arnold_pipelines.megaplan.orchestration.rubber_stamp import is_rubber_stamp
from arnold_pipelines.megaplan.orchestration.evidence_contract import (
    EvidenceRef,
    TransitionDecision,
)
from arnold_pipelines.megaplan.orchestration.authority_readers import (
    AuthorityDecision,
    effective_execute_completed_task_ids,
)
from arnold_pipelines.megaplan.orchestration.transition_policy import (
    TRANSITION_DECISION_REVIEW_DONE_FILENAME,
    TransitionPolicy,
    TransitionWriter,
)
from arnold_pipelines.megaplan.execute.merge import _validate_and_merge_batch
from arnold_pipelines.megaplan.model_seam import ModelStructuralAuditError, audit_step_payload
from arnold_pipelines.megaplan.prompts import create_claude_prompt, create_codex_prompt, create_hermes_prompt
from arnold_pipelines.megaplan.profiles import apply_profile_expansion, normalize_robustness
from arnold_pipelines.megaplan.types import (
    MOCK_ENV_VAR,
    CliError,
    PlanState,
    StepResponse,
)
from arnold_pipelines.megaplan.planning.state import (
    STATE_AWAITING_HUMAN_VERIFY,
    STATE_BLOCKED,
    STATE_DONE,
    STATE_EXECUTED,
    STATE_FINALIZED,
    STATE_REVIEWED,
)
from arnold.pipeline.step_io_contract import StepIOOperation
from arnold_pipelines.megaplan.runtime.schema_registry_adapter import create_step_io_contract_context
from arnold_pipelines.megaplan.store import write_plan_artifact_json
from arnold_pipelines.megaplan.workers import (
    WorkerResult,
    warn_if_work_dir_differs_from_project_dir,
)
from arnold_pipelines.megaplan.runtime.execution_environment import preflight_phase
from arnold_pipelines.megaplan._core import (
    list_batch_artifacts,
    append_history,
    apply_session_update,
    atomic_write_json,
    atomic_write_text,
    clear_active_step,
    configured_robustness,
    get_effective,
    is_prose_mode,
    is_creative_mode,
    load_plan_locked,
    make_history_entry,
    now_utc,
    read_json,
    record_step_failure,
    render_final_md,
    require_state,
    save_state,
    save_state_merge_meta,
    set_active_step,
    sha256_file,
)

from .shared import (
    _attach_next_step_runtime,
    _active_step_fallback_fields,
    _agent_mode_parts,
    _emit_phase_notice,
    _emit_receipt,
    _raise_step_validation_error,
    _run_worker,
    _supports_prompt_kwargs,
    attach_agent_fallback,
    worker_module,
)
from arnold_pipelines.megaplan.orchestration.phase_result import _emit_phase_result
from arnold_pipelines.megaplan.orchestration.phase_result import Deviation as _PhaseDeviation
from arnold_pipelines.megaplan.receipts.extractors import review_metrics

"""Review handler — post-execute implementation-evidence pass.

Review runs *after* execute and evaluates implementation evidence,
merged artifacts, and completion quality.  It is the counterpart to
critique (which runs *before* execute and evaluates plan quality).
These two passes are distinct: critique judges the *plan*, review
judges the *work product*.  Do not rename or conflate them.
"""

log = logging.getLogger(__name__)

# ── T11: Review-scoped scratch promotion known keys ───────────────────────
# The model produces only these keys in the scratch template; unknown
# top-level keys injected by the model are stripped before promotion.
_REVIEW_SCRATCH_KNOWN_KEYS: frozenset[str] = frozenset(
    {
        "review_verdict",
        "review_completion_status",
        "criteria",
        "issues",
        "rework_items",
        "summary",
        "task_verdicts",
        "sense_check_verdicts",
    }
)
# ────────────────────────────────────────────────────────────────────────────


def _build_review_blocked_message(
    *,
    verdict_count: int,
    total_tasks: int,
    check_count: int,
    total_checks: int,
    missing_reviewer_evidence: list[str],
    infrastructure_failure: bool = False,
) -> str:
    if infrastructure_failure:
        return (
            "Blocked: review infrastructure produced an incomplete review instead of repository-backed verdicts. "
            "Re-run review to complete repository inspection."
        )
    if missing_reviewer_evidence:
        return (
            "Blocked: done tasks are missing reviewer evidence_files without a substantive reviewer_verdict ("
            + ", ".join(missing_reviewer_evidence)
            + "). Re-run review to complete."
        )
    return (
        "Blocked: incomplete review coverage "
        f"({verdict_count}/{total_tasks} task verdicts, {check_count}/{total_checks} sense checks). "
        "Re-run review to complete."
    )

def _is_substantive_reviewer_verdict(text: str) -> bool:
    return not is_rubber_stamp(text, strict=True)


_REVIEW_INFRASTRUCTURE_SOURCES = {"review_incomplete", "review_process_error"}
_NO_REPOSITORY_INSPECTION_MARKERS = (
    "no repository inspection",
    "without repository inspection",
    "did not inspect the repository",
    "didn't inspect the repository",
    "could not inspect the repository",
    "no repo inspection",
    "without repo inspection",
    "no verification commands",
    "without verification commands",
    "no file inspection",
    "without file inspection",
    "did not inspect files",
    "didn't inspect files",
    "premature final verdict",
    "premature verdict",
    "placeholder review",
    "review could not complete",
)


def _text_indicates_no_repository_inspection(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    lowered = value.lower()
    return any(marker in lowered for marker in _NO_REPOSITORY_INSPECTION_MARKERS)


def _has_genuine_rejection(payload: dict[str, Any]) -> bool:
    for criterion in payload.get("criteria", []) or []:
        if not isinstance(criterion, dict):
            continue
        if criterion.get("priority") == "must" and criterion.get("pass") in (False, "fail"):
            return True
    for item in payload.get("rework_items", []) or []:
        if not isinstance(item, dict):
            continue
        source = item.get("source")
        if isinstance(source, str) and source in _REVIEW_INFRASTRUCTURE_SOURCES:
            continue
        if _rework_item_is_blocker(item):
            return True
    return False


def _review_infrastructure_failure(
    payload: dict[str, Any],
    *,
    issues: list[str],
    total_tasks: int,
    total_checks: int,
) -> bool:
    """Detect placeholder review output that must be retried as review infra.

    These payloads are not implementation rework. Routing them to execute turns
    a reviewer failure into a bogus executor pass and can overwrite useful
    execution evidence.
    """
    raw_completion_status = payload.get("review_completion_status")
    completion_status = (
        raw_completion_status
        if raw_completion_status in {"complete", "incomplete"}
        else None
    )
    # Explicit structured infra signals are authoritative and win first: the
    # reviewer is self-reporting that it could not complete, so an explicit
    # incomplete status or infra-tagged rework item must keep the plan in review.
    if completion_status == "incomplete":
        return True
    for item in payload.get("rework_items", []) or []:
        if not isinstance(item, dict):
            continue
        source = item.get("source")
        if isinstance(source, str) and source in _REVIEW_INFRASTRUCTURE_SOURCES:
            return True

    # A genuine rejection beats only the fuzzy text / empty-verdict heuristics
    # below. Structured infra signals above already took precedence.
    if _has_genuine_rejection(payload):
        return False

    if completion_status is not None:
        return False

    for item in payload.get("rework_items", []) or []:
        if not isinstance(item, dict):
            continue
        if _text_indicates_no_repository_inspection(item.get("issue")):
            return True
    if any(_text_indicates_no_repository_inspection(issue) for issue in issues):
        return True
    task_verdicts = payload.get("task_verdicts")
    sense_verdicts = payload.get("sense_check_verdicts")
    return (
        (total_tasks > 0 and isinstance(task_verdicts, list) and not task_verdicts)
        or (total_checks > 0 and isinstance(sense_verdicts, list) and not sense_verdicts)
    )

def _build_review_prompt_override(
    agent_type: str,
    state: PlanState,
    plan_dir: Path,
    *,
    root: Path,
    pre_check_flags: list[dict[str, Any]],
) -> str:
    if agent_type == "claude":
        return create_claude_prompt("review", state, plan_dir, root=root, pre_check_flags=pre_check_flags)
    if agent_type == "hermes":
        return create_hermes_prompt("review", state, plan_dir, root=root, pre_check_flags=pre_check_flags)
    return create_codex_prompt("review", state, plan_dir, root=root, pre_check_flags=pre_check_flags)


def _normalize_pre_check_flags(pre_check_flags: list[dict[str, Any]] | None) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    for item in pre_check_flags or []:
        if not isinstance(item, dict):
            continue
        normalized.append(
            {
                "id": str(item.get("id", "") or ""),
                "check": str(item.get("check", "") or ""),
                "detail": str(item.get("detail", "") or ""),
                "severity": str(item.get("severity", "") or ""),
                "evidence_file": str(item.get("evidence_file", "") or ""),
            }
        )
    return normalized


def _prepare_review_payload(
    payload: dict[str, Any],
    *,
    pre_check_flags: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if payload.get("checks") is None:
        payload["checks"] = []
    else:
        payload.setdefault("checks", [])
    if pre_check_flags is None:
        existing_pre_check_flags = payload.get("pre_check_flags")
        payload["pre_check_flags"] = _normalize_pre_check_flags(
            existing_pre_check_flags if isinstance(existing_pre_check_flags, list) else []
        )
    else:
        payload["pre_check_flags"] = _normalize_pre_check_flags(pre_check_flags)
    for key in ("verified_flag_ids", "disputed_flag_ids"):
        if payload.get(key) is None:
            payload[key] = []
        else:
            payload.setdefault(key, [])
    rework_items = payload.get("rework_items")
    if isinstance(rework_items, list):
        for item in rework_items:
            if not isinstance(item, dict):
                continue
            task_id = item.get("task_id")
            task_id_str = task_id if isinstance(task_id, str) and task_id else None
            target = item.get("target")
            if isinstance(target, dict):
                kind = target.get("kind")
                if not isinstance(kind, str) or not kind:
                    target["kind"] = "task" if task_id_str else "global"
                if "task_id" not in target:
                    target["task_id"] = task_id_str
                if "task_ids" not in target:
                    target["task_ids"] = [task_id_str] if task_id_str else []
                if "id" not in target:
                    target["id"] = None
            elif "target" not in item:
                item["target"] = (
                    {
                        "kind": "task",
                        "task_id": task_id_str,
                        "task_ids": [task_id_str],
                        "id": None,
                    }
                    if task_id_str
                    else None
                )
            if "deterministic_check" not in item:
                item["deterministic_check"] = None
            deterministic_check = item.get("deterministic_check")
            if isinstance(deterministic_check, dict):
                deterministic_check.setdefault("evidence_file", None)
    return payload


def _task_review_evidence_files(task: dict[str, Any]) -> list[str]:
    candidates = task.get("evidence_files")
    if not isinstance(candidates, list) or not candidates:
        candidates = task.get("files_changed")
    if not isinstance(candidates, list) or not candidates:
        return ["execution.json"]
    evidence: list[str] = []
    seen: set[str] = set()
    for item in candidates:
        if not isinstance(item, str) or not item.strip():
            continue
        normalized = item.strip()
        if normalized not in seen:
            evidence.append(normalized)
            seen.add(normalized)
    return evidence or ["execution.json"]


def _backfill_empty_approved_review_from_execution(
    payload: dict[str, Any],
    finalize_data: dict[str, Any],
) -> bool:
    """Fill required review coverage when an approved reviewer returns empty lists.

    This is deliberately narrow: it only applies to approved reviews with no
    rework items and no task/sense verdicts. The fallback does not invent a
    human-style review; it records that verdict coverage came from the already
    captured execution/finalize evidence so the run can advance to the policy
    gate instead of looping on an empty reviewer response.
    """
    if payload.get("review_verdict") != "approved":
        return False
    if payload.get("rework_items"):
        return False
    task_verdicts = payload.get("task_verdicts")
    sense_verdicts = payload.get("sense_check_verdicts")
    if not (isinstance(task_verdicts, list) and not task_verdicts):
        return False
    if not (isinstance(sense_verdicts, list) and not sense_verdicts):
        return False

    tasks = [task for task in finalize_data.get("tasks", []) if isinstance(task, dict)]
    sense_checks = [
        check for check in finalize_data.get("sense_checks", []) if isinstance(check, dict)
    ]
    if not tasks and not sense_checks:
        return False

    original_issues = [issue for issue in payload.get("issues", []) if isinstance(issue, str)]
    payload["review_evidence_backfill_notes"] = original_issues
    payload["issues"] = [
        "Approved review returned empty task/sense verdict arrays; harness backfilled verdict coverage from execution/finalize evidence.",
    ]
    payload["task_verdicts"] = [
        {
            "task_id": str(task.get("id", "")),
            "reviewer_verdict": (
                "Backfilled from execution evidence: task was completed by the executor "
                "and covered by recorded files/commands in finalize.json."
            ),
            "evidence_files": _task_review_evidence_files(task),
        }
        for task in tasks
        if task.get("id")
    ]
    payload["sense_check_verdicts"] = [
        {
            "sense_check_id": str(check.get("id", "")),
            "verdict": (
                "Backfilled from executor sense-check evidence recorded in finalize.json."
            ),
        }
        for check in sense_checks
        if check.get("id")
    ]
    payload["review_completion_status"] = "complete"
    payload["review_evidence_backfilled"] = True
    return True


def _review_execution_batch_completed_task_ids(
    plan_dir: Path,
    *,
    project_dir: Path | None,
    state: PlanState,
) -> set[str]:
    completed: set[str] = set()
    for batch_path in sorted(list_batch_artifacts(plan_dir)):
        try:
            payload = read_json(batch_path)
        except (OSError, ValueError):
            continue
        if not isinstance(payload, dict):
            continue
        records = [
            item
            for item in payload.get("task_updates", []) or []
            if isinstance(item, dict)
        ]
        if not records:
            continue
        completed.update(
            effective_execute_completed_task_ids(
                records,
                plan_dir=plan_dir,
                project_dir=project_dir,
                state=state,
            )
        )
    return completed


def _review_execute_authority_gaps(
    *,
    finalize_data: dict[str, Any],
    plan_dir: Path,
    project_dir: Path | None,
    state: PlanState,
) -> list[str]:
    tasks = [
        task
        for task in finalize_data.get("tasks", []) or []
        if isinstance(task, dict) and (task.get("id") or task.get("task_id"))
    ]
    if not tasks:
        return []

    decisions: dict[str, AuthorityDecision] = {}
    completed = effective_execute_completed_task_ids(
        tasks,
        plan_dir=plan_dir,
        project_dir=project_dir,
        state=state,
        decisions=decisions,
    )
    batch_completed = _review_execution_batch_completed_task_ids(
        plan_dir,
        project_dir=project_dir,
        state=state,
    )
    gaps: list[str] = []
    for task in tasks:
        task_id = str(task.get("id") or task.get("task_id") or "")
        raw_status = task.get("status")
        if raw_status in {None, "", "pending", "todo", "in_progress"}:
            if task_id in batch_completed:
                continue
            gaps.append(
                f"{task_id or '<missing-task-id>'}:"
                f"not_executed:{raw_status or 'missing_status'}"
            )
            continue
        if (
            raw_status in {"done", "completed", "skipped", "waived", "not_applicable"}
            and task_id not in completed
        ):
            if (
                raw_status == "skipped"
                and task.get("reviewer_verdict") == "deferred_baseline_unavailable"
            ):
                continue
            decision = decisions.get(task_id)
            reason = "unknown"
            if decision is not None:
                reason = decision.status.value
                if decision.would_block_reasons:
                    reason = f"{reason}:{','.join(decision.would_block_reasons)}"
            gaps.append(f"{task_id}:{reason}")
    return gaps


def _enforce_review_execute_authority(
    *,
    payload: dict[str, Any],
    finalize_data: dict[str, Any],
    plan_dir: Path,
    project_dir: Path | None,
    state: PlanState,
    issues: list[str],
) -> bool:
    gaps = _review_execute_authority_gaps(
        finalize_data=finalize_data,
        plan_dir=plan_dir,
        project_dir=project_dir,
        state=state,
    )
    if not gaps:
        return False

    payload["review_verdict"] = "needs_rework"
    payload["review_completion_status"] = "complete"
    issue = (
        "Execution authority is incomplete for finalized tasks; review cannot approve "
        f"until execute completes them: {', '.join(gaps)}"
    )
    issues.append(issue)
    payload["issues"] = issues
    rework_items = payload.get("rework_items")
    if not isinstance(rework_items, list):
        rework_items = []
        payload["rework_items"] = rework_items
    for gap in gaps:
        task_id = gap.split(":", 1)[0]
        rework_items.append(
            {
                "task_id": task_id if task_id != "<missing-task-id>" else None,
                "issue": f"Execute did not provide authoritative completion evidence: {gap}",
                "source": "execute_authority",
                "target": {
                    "kind": "task" if task_id != "<missing-task-id>" else "global",
                    "task_id": task_id if task_id != "<missing-task-id>" else None,
                    "task_ids": [] if task_id == "<missing-task-id>" else [task_id],
                    "id": None,
                },
                "deterministic_check": None,
            }
        )
    criteria = payload.get("criteria")
    if not isinstance(criteria, list):
        criteria = []
        payload["criteria"] = criteria
    criteria.append(
        {
            "id": "execute_authority_complete",
            "priority": "must",
            "pass": False,
            "rationale": issue,
        }
    )
    payload["execute_authority_missing"] = gaps
    return True


def _preserve_raw_review_rework_verdict(
    *,
    plan_dir: Path,
    payload: dict[str, Any],
    issues: list[str],
) -> bool:
    """Fail closed when the raw review artifact disagrees with the normalized payload.

    The model seam writes ``review_output.json`` before the handler persists the
    normalized ``review.json``. If the raw artifact says ``needs_rework``, no
    later wrapper/backfill payload may turn that into ``approved``. Review may
    still demote unsupported advisory rework through the normal blocker
    normalizer, but only from the raw review content itself.
    """

    if payload.get("review_verdict") == "needs_rework":
        return False
    raw_path = plan_dir / "review_output.json"
    if not raw_path.exists():
        return False
    try:
        raw = read_json(raw_path)
    except (OSError, ValueError):
        return False
    if not isinstance(raw, dict) or raw.get("review_verdict") != "needs_rework":
        return False

    payload["review_verdict"] = "needs_rework"
    payload["review_completion_status"] = raw.get("review_completion_status") or payload.get(
        "review_completion_status"
    )
    for key in (
        "summary",
        "issues",
        "task_verdicts",
        "sense_check_verdicts",
        "rework_items",
        "criteria",
        "blocking_rework_items",
    ):
        value = raw.get(key)
        if value:
            payload[key] = value
    issues[:] = [issue for issue in payload.get("issues", []) if isinstance(issue, str)]
    issues.append(
        "Raw review_output.json returned needs_rework; normalized review payload "
        "was forced back to rework."
    )
    payload["issues"] = issues
    payload["raw_review_verdict_preserved"] = True
    return True


def _promote_authoritative_review_output(
    *,
    plan_dir: Path,
    payload: dict[str, Any],
) -> bool:
    """Promote a filled raw review artifact over wrapper/inline payload.

    Scratch promotion normally compares ``review_output.json`` to the seed
    written before worker execution. A stale or late seed read can make the
    final filled file look "unmodified", falling back to an inline wrapper
    payload. At review-finalization time, a valid raw review artifact with a
    concrete verdict is the authoritative reviewer output.
    """

    raw_path = plan_dir / "review_output.json"
    if not raw_path.exists():
        return False
    try:
        raw = read_json(raw_path)
    except (OSError, ValueError):
        return False
    if not isinstance(raw, dict):
        return False
    if raw.get("review_verdict") not in {"approved", "needs_rework"}:
        return False

    promoted = {key: raw[key] for key in _REVIEW_SCRATCH_KNOWN_KEYS if key in raw}
    payload.clear()
    payload.update(promoted)
    payload["raw_review_output_promoted"] = True
    return True


def _audit_review_payload_or_raise(
    *,
    plan_dir: Path,
    state: PlanState,
    payload: dict[str, Any],
    raw_output: str | None,
    duration_ms: int,
) -> None:
    try:
        audit_step_payload("review", payload)
    except ModelStructuralAuditError as error:
        worker = WorkerResult(
            payload=payload,
            raw_output=raw_output,
            duration_ms=duration_ms,
            cost_usd=0.0,
            session_id=None,
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
        )
        _raise_step_validation_error(
            plan_dir=plan_dir,
            state=state,
            step="review",
            iteration=state["iteration"],
            worker=worker,
            code="invalid_review",
            message=f"Review output failed schema audit: {error.details}",
        )


def _prepare_parallel_review_checks(
    payload_checks: list[Any],
    *,
    check_specs: tuple[Any, ...],
) -> list[Any]:
    spec_by_id: dict[str, Any] = {}
    for spec in check_specs:
        check_id = spec.get("id") if isinstance(spec, dict) else getattr(spec, "id", None)
        if isinstance(check_id, str):
            spec_by_id[check_id] = spec

    for check in payload_checks:
        if not isinstance(check, dict):
            continue
        check_id = check.get("id")
        spec = spec_by_id.get(check_id) if isinstance(check_id, str) else None
        if check.get("concerned_task_ids") is None:
            check["concerned_task_ids"] = []
        else:
            check.setdefault("concerned_task_ids", [])
        if check.get("prior_findings") is None:
            check["prior_findings"] = []
        else:
            check.setdefault("prior_findings", [])
        if spec is not None and check.get("guidance") is None:
            guidance = spec.get("guidance") if isinstance(spec, dict) else getattr(spec, "guidance", None)
            if isinstance(guidance, str):
                check["guidance"] = guidance
        findings = check.get("findings")
        if isinstance(findings, list):
            for finding in findings:
                if isinstance(finding, dict) and finding.get("evidence_file") is None:
                    finding["evidence_file"] = ""
    return payload_checks


def _merge_review_verdicts(
    worker_payload: dict[str, Any],
    finalize_data: dict[str, Any],
    issues: list[str],
) -> tuple[int, int, int, int, list[str]]:
    """Merge task verdicts and sense check verdicts into finalize_data.

    Returns (verdict_count, total_tasks, check_count, total_checks, missing_evidence).
    """
    tasks_by_id = {task["id"]: task for task in finalize_data.get("tasks", [])}
    verdict_count, total_tasks = _validate_and_merge_batch(
        worker_payload.get("task_verdicts"),
        required_fields=("task_id", "reviewer_verdict", "evidence_files"),
        targets_by_id=tasks_by_id,
        id_field="task_id",
        merge_fields=("reviewer_verdict", "evidence_files"),
        issues=issues,
        validation_label="task_verdicts",
        merge_label="task_verdict",
        incomplete_message=lambda merged, total: f"Incomplete review: {merged}/{total} tasks received a reviewer verdict.",
        nonempty_fields={"reviewer_verdict"},
        array_fields=("evidence_files",),
    )
    sense_checks_by_id = {sc["id"]: sc for sc in finalize_data.get("sense_checks", [])}
    check_count, total_checks = _validate_and_merge_batch(
        worker_payload.get("sense_check_verdicts"),
        required_fields=("sense_check_id", "verdict"),
        targets_by_id=sense_checks_by_id,
        id_field="sense_check_id",
        merge_fields=("verdict",),
        issues=issues,
        validation_label="sense_check_verdicts",
        merge_label="sense_check_verdict",
        incomplete_message=lambda merged, total: f"Incomplete review: {merged}/{total} sense checks received a verdict.",
        nonempty_fields={"verdict"},
    )
    missing_evidence = _check_done_task_evidence(
        finalize_data.get("tasks", []),
        issues=issues,
        should_classify=lambda task: bool(task.get("reviewer_verdict", "").strip()),
        has_evidence=lambda task: bool(task.get("evidence_files")),
        has_advisory_evidence=lambda task: _is_substantive_reviewer_verdict(task.get("reviewer_verdict", "")),
        missing_message="Done tasks missing reviewer evidence_files without a substantive reviewer_verdict: ",
        advisory_message="Advisory: done tasks rely on substantive reviewer_verdict without evidence_files (FLAG-006 softening): ",
    )
    return verdict_count, total_tasks, check_count, total_checks, missing_evidence


_FAILED_CHECK_STATUSES = {"fail", "failed", "failing", "red", "newly_failing", "unsatisfied"}
_PASSED_CHECK_STATUSES = {"pass", "passed", "passing", "green", "satisfied"}


def _failed_check_status(value: Any) -> bool:
    if value is False:
        return True
    if not isinstance(value, str):
        return False
    normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
    return normalized in _FAILED_CHECK_STATUSES or normalized.startswith(
        tuple(f"{status}_" for status in _FAILED_CHECK_STATUSES)
    )


def _passed_check_status(value: Any) -> bool:
    if value is True:
        return True
    if not isinstance(value, str):
        return False
    normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
    return normalized in _PASSED_CHECK_STATUSES or normalized.startswith(
        tuple(f"{status}_" for status in _PASSED_CHECK_STATUSES)
    )


def _grounding_check(value: dict[str, Any]) -> dict[str, Any]:
    raw = value.get("deterministic_check")
    if isinstance(raw, dict):
        return raw
    return value


def _has_grounded_deterministic_failure(value: dict[str, Any]) -> bool:
    check = _grounding_check(value)
    if check.get("deterministic") is False:
        return False
    command = check.get("command") or check.get("check") or check.get("name")
    if not isinstance(command, str) or not command.strip():
        return False
    baseline_failed = (
        check.get("failed_on_baseline") is True
        or _failed_check_status(check.get("baseline_status"))
        or _failed_check_status(check.get("baseline_result"))
        or _failed_check_status(check.get("pre_status"))
        or _failed_check_status(check.get("pre_execute_status"))
    )
    post_failed = (
        check.get("failed_after_execute") is True
        or _failed_check_status(check.get("post_status"))
        or _failed_check_status(check.get("post_result"))
        or _failed_check_status(check.get("current_status"))
        or _failed_check_status(check.get("post_execute_status"))
    )
    baseline_passed = (
        _passed_check_status(check.get("baseline_status"))
        or _passed_check_status(check.get("baseline_result"))
        or _passed_check_status(check.get("pre_status"))
        or _passed_check_status(check.get("pre_execute_status"))
    )
    return post_failed and (baseline_failed or baseline_passed)


def _normalize_review_blockers(payload: dict[str, Any], issues: list[str]) -> None:
    """Demote ungrounded reviewer concerns before state-machine routing."""
    rework_items = payload.get("rework_items")
    if not isinstance(rework_items, list):
        return
    disputed_ids = {
        flag_id
        for flag_id in payload.get("disputed_flag_ids", []) or []
        if isinstance(flag_id, str) and flag_id
    }
    blocking: list[dict[str, Any]] = []
    advisory: list[dict[str, Any]] = []
    for item in rework_items:
        if not isinstance(item, dict):
            continue
        flag_id = item.get("flag_id")
        if isinstance(flag_id, str) and flag_id in disputed_ids:
            advisory.append(item)
            continue
        if _has_grounded_deterministic_failure(item):
            blocking.append(item)
        else:
            advisory.append(item)

    failed_criteria = [
        criterion
        for criterion in payload.get("criteria", []) or []
        if isinstance(criterion, dict)
        and criterion.get("priority") == "must"
        and criterion.get("pass") in (False, "fail")
    ]
    grounded_failed_criteria = [
        criterion
        for criterion in failed_criteria
        if _has_grounded_deterministic_failure(criterion)
    ]

    if advisory:
        payload["advisory_rework_items"] = advisory
    if failed_criteria and len(grounded_failed_criteria) < len(failed_criteria):
        payload["advisory_failed_criteria"] = [
            criterion
            for criterion in failed_criteria
            if criterion not in grounded_failed_criteria
        ]
    payload["rework_items"] = blocking
    payload["blocking_rework_items"] = blocking
    if grounded_failed_criteria:
        payload["blocking_failed_criteria"] = grounded_failed_criteria

    if (
        payload.get("review_verdict") == "needs_rework"
        and not blocking
        and not grounded_failed_criteria
    ):
        payload["review_verdict"] = "approved"
        if advisory or failed_criteria:
            issues.append(
                "Advisory: review requested rework without a deterministic check "
                "that failed on both baseline and post-execute; not blocking."
            )


def _maker_requested_stop(plan_dir: Path) -> dict[str, str] | None:
    finalize_path = plan_dir / "finalize.json"
    if not finalize_path.exists():
        return None
    try:
        finalize_data = read_json(finalize_path)
    except (OSError, ValueError):
        return None
    for task in finalize_data.get("tasks", []):
        if not isinstance(task, dict):
            continue
        stop_signal = task.get("stop_signal")
        if isinstance(stop_signal, dict) and stop_signal.get("requested") is True:
            return {"defense": str(stop_signal.get("defense", "")).strip()}
    return None


def _record_maker_stop(state: PlanState, plan_dir: Path, *, defense: str) -> None:
    note = f"Maker stop honored: {defense or 'No defense supplied.'}"
    state.setdefault("meta", {}).setdefault("notes", []).append(
        {"timestamp": now_utc(), "note": note}
    )
    notes_path = plan_dir / "directors_notes.json"
    if not notes_path.exists():
        return
    try:
        notes = read_json(notes_path)
    except (OSError, ValueError):
        return
    passes = notes.get("passes", [])
    if isinstance(passes, list) and passes:
        last_pass = passes[-1]
        if isinstance(last_pass, dict):
            last_pass["stop_requested"] = True
            last_pass["stop_defense"] = defense
            atomic_write_json(notes_path, notes)


_NON_BLOCKING_SEVERITY_TOKENS = {
    "significant",
    "minor",
    "n/a",
    "na",
    "should",
    "info",
    "advisory",
    "cosmetic",
    "nit",
    "nitpick",
}


def _rework_item_is_blocker(item: dict[str, Any]) -> bool:
    for field in ("severity", "priority", "status"):
        raw = item.get(field)
        if isinstance(raw, str) and raw.strip().lower() in _NON_BLOCKING_SEVERITY_TOKENS:
            return False
    return True


def _force_proceed_blockers(
    criteria: list[dict[str, Any]] | None,
    rework_items: list[dict[str, Any]] | None,
) -> list[str]:
    blockers: list[str] = []
    for crit in criteria or []:
        if not isinstance(crit, dict):
            continue
        if crit.get("priority") == "must" and crit.get("pass") in (False, "fail"):
            label = str(
                crit.get("criterion") or crit.get("id") or crit.get("text") or "must criterion"
            ).strip()
            blockers.append(f"failed must-criterion: {label}")
    for item in rework_items or []:
        if not isinstance(item, dict):
            continue
        if _rework_item_is_blocker(item):
            label = str(
                item.get("issue") or item.get("task_id") or item.get("flag_id") or "rework item"
            ).strip()
            blockers.append(f"unresolved blocking rework: {label}")
    return blockers


@dataclass(frozen=True)
class ReviewRouteDecision:
    result: str
    next_state: str
    route_signal: str


def _resolve_review_outcome(
    plan_dir: Path,
    review_verdict: str,
    verdict_count: int,
    total_tasks: int,
    check_count: int,
    total_checks: int,
    missing_evidence: list[str],
    robustness: str,
    state: PlanState,
    issues: list[str],
    criteria: list[dict[str, Any]] | None = None,
    infrastructure_failure: bool = False,
    rework_items: list[dict[str, Any]] | None = None,
) -> ReviewRouteDecision:
    """Determine review result, next state, and review route signal."""
    robustness = normalize_robustness(robustness)
    blocked = (
        infrastructure_failure
        or verdict_count < total_tasks
        or check_count < total_checks
        or bool(missing_evidence)
    )
    if blocked:
        return ReviewRouteDecision("blocked", STATE_EXECUTED, "blocked")

    rework_requested = review_verdict == "needs_rework"
    if rework_requested:
        if is_creative_mode(state):
            stop_data = _maker_requested_stop(plan_dir)
            if stop_data is not None:
                _record_maker_stop(state, plan_dir, defense=stop_data.get("defense", ""))
                return ReviewRouteDecision("success", STATE_DONE, "pass")
        cap_key = (
            "max_robust_review_rework_cycles"
            if robustness in {"thorough", "extreme"}
            else "max_review_rework_cycles"
        )
        max_review_rework_cycles = get_effective("execution", cap_key)
        prior_rework_count = sum(
            1 for entry in state.get("history", [])
            if entry.get("step") == "review" and entry.get("result") == "needs_rework"
        )
        if prior_rework_count >= max_review_rework_cycles:
            blockers = _force_proceed_blockers(criteria, rework_items)
            if blockers:
                blocker_list = "; ".join(blockers[:10])
                more = "" if len(blockers) <= 10 else f" (+{len(blockers) - 10} more)"
                issues.append(
                    f"Max review rework cycles ({max_review_rework_cycles}) reached with "
                    f"{len(blockers)} unresolved blocker(s) — escalating to recoverable "
                    "blocked instead of force-proceeding to done. Blockers: "
                    f"{blocker_list}{more}. Resolve them and resume review, or "
                    "`override recover-blocked`/`force-proceed` after operator review to ship anyway."
                )
                return ReviewRouteDecision("blocked", STATE_BLOCKED, "blocked")
            issues.append(
                f"Max review rework cycles ({max_review_rework_cycles}) reached. "
                "Force-proceeding to done despite unresolved review issues "
                "(all remaining items are non-blocking/cosmetic)."
            )
            return ReviewRouteDecision("force_proceeded", STATE_DONE, "force_proceeded")
        return ReviewRouteDecision("needs_rework", STATE_FINALIZED, "rework")

    if criteria:
        has_deferred_must = any(
            c.get("pass") == "deferred_human" and c.get("priority") == "must"
            for c in criteria
        )
        if has_deferred_must:
            # STATE_AWAITING_HUMAN_VERIFY is intentionally NOT modified for with_feedback.
            # When deferred_must criteria require human verification, the plan is not
            # considered complete yet — scaffolding feedback.md would be misleading
            # because the user still needs to verify. Feedback scaffolding is deferred
            # until the plan actually reaches done (via the existing interactive
            # 'megaplan feedback edit' path after verification).
            return ReviewRouteDecision("success", STATE_AWAITING_HUMAN_VERIFY, "deferred_human")

    with_feedback = state.get("config", {}).get("with_feedback", False)
    return ReviewRouteDecision("success", STATE_REVIEWED if with_feedback else STATE_DONE, "pass")


def _compat_next_step_for_review_route(decision: ReviewRouteDecision) -> str | None:
    if decision.route_signal == "rework":
        return "execute"
    if decision.route_signal == "blocked":
        return "review"
    return None


def _format_review_success_summary(criteria: list[dict[str, Any]]) -> str:
    passed = sum(1 for c in criteria if c.get("pass") in (True, "pass"))
    total = len(criteria)
    waived = sum(1 for c in criteria if c.get("pass") == "waived")
    deferred = sum(1 for c in criteria if c.get("pass") == "deferred_human")
    failed = sum(1 for c in criteria if c.get("pass") in (False, "fail"))
    details: list[str] = []
    if waived:
        details.append(f"{waived} waived")
    if deferred:
        details.append(f"{deferred} deferred to human")
    if failed:
        details.append(f"{failed} failed but non-blocking")
    if details:
        return (
            f"Review complete: {passed}/{total} success criteria passed "
            f"({', '.join(details)})."
        )
    return f"Review complete: {passed}/{total} success criteria passed."


def _wrap_parallel_review_worker(
    merged_payload: dict[str, Any],
    parallel_result: WorkerResult,
) -> WorkerResult:
    return WorkerResult(
        payload=merged_payload,
        raw_output=parallel_result.raw_output,
        duration_ms=parallel_result.duration_ms,
        cost_usd=parallel_result.cost_usd,
        session_id=None,
        prompt_tokens=parallel_result.prompt_tokens,
        completion_tokens=parallel_result.completion_tokens,
        total_tokens=parallel_result.total_tokens,
        rate_limit=parallel_result.rate_limit,
    )


_EXPECTED_BY_CHECK_ID = {
    "coverage": "Extend the fix so every concrete failing example, symptom, or 'X should Y' statement in the issue is addressed by at least one diff line.",
    "placement": "Move the fix upstream to where the bad state is first introduced, or extend it to cover any alternate entry points identified in the finding.",
    "adjacent_calls": "Apply the same fix to each additional call site, sibling class, or downstream consumer identified in the finding.",
    "simplicity": "Remove unjustified changes, or justify each extra line against a concrete issue requirement.",
}

def _synthesize_review_rework_items(checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rework_items: list[dict[str, Any]] = []
    for check in checks:
        check_id = check.get("id", "")
        if not isinstance(check_id, str) or not check_id:
            continue
        check_def = review_checks.get_check_by_id(check_id)
        if getattr(check_def, "default_severity", "") != "likely-significant":
            continue
        question = str(check.get("question", "") or "").strip()
        findings = check.get("findings", [])
        if not isinstance(findings, list):
            continue
        for finding in findings:
            if not isinstance(finding, dict) or not finding.get("flagged"):
                continue
            status = str(finding.get("status", "") or "").strip().lower()
            # megaplan/prompts/review.py:243-249 constrains status to {blocking, significant, minor, n/a};
            # significant is the explicit non-blocking downgrade for gate-settled concerns, while missing or
            # empty status means the model failed to classify, so we keep the check's default_severity gate as
            # the blocking fallback. That is the safe default for the sympy-21930 / sphinx-9711 regressions.
            if status and status != "blocking":
                continue
            detail = str(finding.get("detail", "") or "").strip()
            evidence_file = finding.get("evidence_file", "")
            if not isinstance(evidence_file, str):
                evidence_file = ""
            issue = detail or question or f"Heavy review found a blocking {check_id} issue."
            # Prefer a per-check actionable expected string; fall back to the
            # check's self-question; ultimately fall back to a generic message.
            expected = (
                _EXPECTED_BY_CHECK_ID.get(check_id)
                or question
                or f"Review check '{check_id}' should pass without blocking findings."
            )
            # `actual` should NOT duplicate `issue` — use a templated
            # acknowledgment of the finding instead so the executor sees
            # a clear "you didn't resolve it" signal without a copy of
            # the detail text.
            actual = f"The diff did not resolve the flagged {check_id} concern above."
            concerned_task_ids = check.get("concerned_task_ids", [])
            if (
                not isinstance(concerned_task_ids, list)
                or not concerned_task_ids
                or not all(isinstance(task_id, str) and task_id for task_id in concerned_task_ids)
            ):
                log.warning(
                    "Parallel review check %s omitted concerned_task_ids; falling back to synthetic REVIEW-%s task id.",
                    check_id,
                    check_id,
                )
                concerned_task_ids = [f"REVIEW-{check_id}"]
            task_ids = [str(candidate) for candidate in concerned_task_ids if isinstance(candidate, str) and candidate]
            for task_id in concerned_task_ids:
                item = {
                    "task_id": task_id,
                    "issue": issue,
                    "expected": expected,
                    "actual": actual,
                    "evidence_file": evidence_file,
                    "flag_id": f"REVIEW-{check_id}",
                    "source": f"review_{check_id}",
                    "target": {
                        "kind": "task",
                        "task_id": task_id,
                        "task_ids": task_ids,
                        "id": None,
                    },
                }
                deterministic_check = finding.get("deterministic_check")
                if isinstance(deterministic_check, dict):
                    item["deterministic_check"] = deterministic_check
                else:
                    item["deterministic_check"] = None
                rework_items.append(item)
    return rework_items


def _review_done_evidence_refs(review_evidence: dict[str, Any]) -> tuple[EvidenceRef, ...]:
    raw_evidence = review_evidence.get("evidence")
    if not isinstance(raw_evidence, list):
        return ()
    return tuple(
        EvidenceRef.from_dict(ref)
        for ref in raw_evidence
        if isinstance(ref, dict)
    )


def _persist_review_done_transition_decision(
    *,
    plan_dir: Path,
    state: PlanState,
    result: str,
    next_state: str,
    review_payload: dict[str, Any],
) -> Any | None:
    if result != "success" or next_state != STATE_DONE:
        return None

    review_evidence_path = plan_dir / "review_evidence.json"
    review_evidence = read_json(review_evidence_path) if review_evidence_path.exists() else {}
    if not isinstance(review_evidence, dict):
        review_evidence = {}
    project_dir = Path(str(state.get("config", {}).get("project_dir", "")))
    policy_decision = TransitionPolicy.evaluate_review_done(
        result=result,
        next_state=next_state,
        review_payload=review_payload,
        review_evidence=review_evidence,
        project_dir=project_dir if str(project_dir) else None,
    )
    meta = state.get("meta") if isinstance(state.get("meta"), dict) else {}
    invocation_id = meta.get("current_invocation_id")
    if not isinstance(invocation_id, str) or not invocation_id:
        invocation_id = review_evidence.get("invocation_id")
    iteration = state.get("iteration")
    decision = TransitionDecision(
        decision_id=f"review-done-{invocation_id or iteration or 'unknown'}",
        subject=f"plan:{state.get('name', '')}",
        from_state=str(state.get("current_state")) if state.get("current_state") is not None else None,
        to_state=next_state,
        action="allow_transition" if policy_decision.allowed else "deny_transition",
        status="allowed" if policy_decision.allowed else "denied",
        evidence=_review_done_evidence_refs(review_evidence),
        would_block_reasons=policy_decision.reasons,
        invocation_id=invocation_id if isinstance(invocation_id, str) else None,
        phase="review",
        iteration=iteration if isinstance(iteration, int) else None,
        base_sha=review_evidence.get("base_sha") if isinstance(review_evidence.get("base_sha"), str) else None,
        head_sha=review_evidence.get("head_sha") if isinstance(review_evidence.get("head_sha"), str) else None,
        code_hash=review_evidence.get("code_hash") if isinstance(review_evidence.get("code_hash"), str) else None,
        routing_provider="transition_policy",
        routing_provenance={
            "policy": "review_done",
            "advisory": list(policy_decision.advisory),
        },
    )
    TransitionWriter.write_review_done(
        plan_dir,
        decision,
        retryable=not policy_decision.allowed,
        next_action="mark_done" if policy_decision.allowed else "review",
        denial_kind=None if policy_decision.allowed else "policy_denied",
        operator_summary=(
            "Review-to-done transition allowed by policy."
            if policy_decision.allowed
            else "Review-to-done transition denied by policy."
        ),
    )
    return policy_decision


def _finalize_review_outcome(
    *,
    root: Path,
    args: argparse.Namespace,
    plan_dir: Path,
    state: PlanState,
    worker: WorkerResult,
    agent: str,
    mode: str,
    refreshed: bool,
    robustness: str,
) -> StepResponse:
    """Post-worker bookkeeping shared by both review paths.

    The single-worker (claude/codex/mock) and parallel-hermes branches of
    :func:`handle_review` previously inlined the same ~100-line block of
    verdict-merging, state advancement, receipt emission, and response
    construction. This helper is the single owner of that flow.
    """
    raw_review_promoted = _promote_authoritative_review_output(
        plan_dir=plan_dir,
        payload=worker.payload,
    )
    issues = list(worker.payload.get("issues", []))
    finalize_data = read_json(plan_dir / "finalize.json")
    review_projection = deepcopy(finalize_data)

    # ── M4 T8: Consume evidence_window from execution audit ───────────────
    evidence_window: dict[str, Any] | None = None
    audit_path = plan_dir / "execution_audit.json"
    if audit_path.exists():
        try:
            audit_data = read_json(audit_path)
            if isinstance(audit_data, dict):
                evidence_window = audit_data.get("evidence_window")
        except (OSError, ValueError):
            pass
    if isinstance(evidence_window, dict):
        worker.payload.setdefault("evidence_window", evidence_window)
    # ──────────────────────────────────────────────────────────────────────

    review_verdict = worker.payload.get("review_verdict")
    invalid_review_verdict = False
    if review_verdict not in {"approved", "needs_rework"}:
        issues.append("Invalid review_verdict; expected 'approved' or 'needs_rework'.")
        review_verdict = "needs_rework"
        invalid_review_verdict = True
        worker.payload["review_verdict"] = review_verdict

    raw_rework_preserved = _preserve_raw_review_rework_verdict(
        plan_dir=plan_dir,
        payload=worker.payload,
        issues=issues,
    )
    if raw_rework_preserved:
        review_verdict = worker.payload.get("review_verdict")

    raw_rework_promoted = (
        raw_review_promoted and worker.payload.get("review_verdict") == "needs_rework"
    )
    if not invalid_review_verdict and not raw_rework_preserved and not raw_rework_promoted:
        _normalize_review_blockers(worker.payload, issues)
        review_verdict = worker.payload.get("review_verdict")

    authority_enforced = _enforce_review_execute_authority(
        payload=worker.payload,
        finalize_data=finalize_data,
        plan_dir=plan_dir,
        project_dir=root,
        state=state,
        issues=issues,
    )
    if authority_enforced:
        review_verdict = worker.payload.get("review_verdict")

    if _backfill_empty_approved_review_from_execution(worker.payload, finalize_data):
        issues = list(worker.payload.get("issues", []))

    verdict_count, total_tasks, check_count, total_checks, missing_evidence = _merge_review_verdicts(
        worker.payload, review_projection, issues,
    )
    worker.payload["issues"] = issues
    worker.payload["total_tasks"] = total_tasks
    worker.payload["total_sense_checks"] = total_checks
    infrastructure_failure = _review_infrastructure_failure(
        worker.payload,
        issues=issues,
        total_tasks=total_tasks,
        total_checks=total_checks,
    )
    finalize_hash = sha256_file(plan_dir / "finalize.json")

    decision = _resolve_review_outcome(
        plan_dir,
        review_verdict, verdict_count, total_tasks,
        check_count, total_checks, missing_evidence,
        robustness,
        state, issues,
        criteria=worker.payload.get("criteria", []),
        infrastructure_failure=infrastructure_failure,
        rework_items=worker.payload.get("rework_items", []),
    )
    result = decision.result
    next_state = decision.next_state
    next_step = _compat_next_step_for_review_route(decision)
    worker.payload["issues"] = issues
    worker.payload["outcome"] = {
        "result": result,
        "review_verdict": review_verdict,
        "state": next_state,
        "next_step": next_step,
        "route_signal": decision.route_signal,
    }
    write_plan_artifact_json(
        plan_dir, "review.json", worker.payload,
        contract_context=create_step_io_contract_context(
            operation=StepIOOperation.WRITE,
            explicit_root=plan_dir,
        ),
    )
    policy_decision = _persist_review_done_transition_decision(
        plan_dir=plan_dir,
        state=state,
        result=result,
        next_state=next_state,
        review_payload=worker.payload,
    )
    if policy_decision is not None and not policy_decision.allowed:
        denial_metadata = {
            "denial_kind": "policy_denied",
            "reasons": list(policy_decision.reasons),
            "advisory": list(policy_decision.advisory),
            "retryable": True,
            "next_action": "review",
            "operator_summary": "Review-to-done transition denied by policy.",
            "transition_decision": TRANSITION_DECISION_REVIEW_DONE_FILENAME,
        }
        worker.payload["outcome"] = {
            "result": "policy_denied",
            "review_verdict": review_verdict,
            "state": STATE_EXECUTED,
            "next_step": "review",
            "route_signal": "blocked",
            "policy_denial": denial_metadata,
        }
        write_plan_artifact_json(
            plan_dir, "review.json", worker.payload,
            contract_context=create_step_io_contract_context(
                operation=StepIOOperation.WRITE,
                explicit_root=plan_dir,
            ),
        )
        state["current_state"] = STATE_EXECUTED
        clear_active_step(state)
        apply_session_update(state, "review", agent, worker.session_id, mode=mode, refreshed=refreshed)
        append_history(
            state,
            make_history_entry(
                "review",
                duration_ms=worker.duration_ms, cost_usd=worker.cost_usd,
                result="policy_denied",
                worker=worker, agent=agent, mode=mode,
                output_file="review.json",
                prompt_tokens=worker.prompt_tokens,
                completion_tokens=worker.completion_tokens,
                total_tokens=worker.total_tokens,
                artifact_hash=sha256_file(plan_dir / "review.json"),
                finalize_hash=finalize_hash,
            ),
        )
        worker.receipt_metrics = review_metrics(worker.payload, plan_dir / "review.json")
        _emit_receipt(
            plan_dir=plan_dir,
            state=state,
            args=args,
            worker=worker,
            agent=agent,
            mode=mode,
            phase="review",
            output_file="review.json",
            artifact_hash=sha256_file(plan_dir / "review.json"),
            verdict="policy_denied",
        )
        save_state_merge_meta(plan_dir, state)
        summary = "Review-to-done transition denied by policy. Re-run review after addressing the policy evidence."
        deviations = tuple(_PhaseDeviation.from_string(reason) for reason in policy_decision.reasons)
        _emit_phase_result(
            phase="review",
            state=state,
            plan_dir=plan_dir,
            exit_kind="blocked_by_quality",
            deviations=deviations,
            artifacts_written=("review.json", TRANSITION_DECISION_REVIEW_DONE_FILENAME),
        )
        response: StepResponse = {
            "success": False,
            "step": "review",
            "summary": summary,
            "artifacts": ["review.json", "finalize.json", TRANSITION_DECISION_REVIEW_DONE_FILENAME],
            "monitor_hint": build_monitor_hint(plan_dir),
            "next_step": "review",
            "state": STATE_EXECUTED,
            "issues": issues,
            "rework_items": list(worker.payload.get("rework_items", [])),
            "policy_denial": denial_metadata,
            "deviations": list(policy_decision.reasons),
            "warnings": list(policy_decision.reasons),
            "_phase_outcome": "blocked_by_quality",
        }
        _attach_next_step_runtime(response)
        attach_agent_fallback(response, args)
        return response
    atomic_write_text(plan_dir / "final.md", render_final_md(review_projection, phase="review"))
    force_proceed_blocked = result == "blocked" and next_state == STATE_BLOCKED
    if force_proceed_blocked:
        state["resume_cursor"] = {
            "phase": "review",
            "retry_strategy": "manual_review",
        }
    state["current_state"] = next_state
    if result != "blocked" and next_state != STATE_BLOCKED:
        state["latest_failure"] = None
        state.pop("resume_cursor", None)

    clear_active_step(state)
    apply_session_update(state, "review", agent, worker.session_id, mode=mode, refreshed=refreshed)
    append_history(
        state,
        make_history_entry(
            "review",
            duration_ms=worker.duration_ms, cost_usd=worker.cost_usd,
            result=result,
            worker=worker, agent=agent, mode=mode,
            output_file="review.json",
            prompt_tokens=worker.prompt_tokens,
            completion_tokens=worker.completion_tokens,
            total_tokens=worker.total_tokens,
            artifact_hash=sha256_file(plan_dir / "review.json"),
            finalize_hash=finalize_hash,
        ),
    )
    worker.receipt_metrics = review_metrics(worker.payload, plan_dir / "review.json")
    _emit_receipt(
        plan_dir=plan_dir,
        state=state,
        args=args,
        worker=worker,
        agent=agent,
        mode=mode,
        phase="review",
        output_file="review.json",
        artifact_hash=sha256_file(plan_dir / "review.json"),
        verdict=result if result == "force_proceeded" else review_verdict,
    )
    save_state_merge_meta(plan_dir, state)

    criteria = worker.payload.get("criteria", [])
    if force_proceed_blocked:
        summary = next(
            (
                issue for issue in reversed(issues)
                if "escalating to recoverable blocked" in issue
            ),
            "Review rework cap reached with unresolved blockers — escalated to "
            "recoverable blocked instead of force-proceeding to done.",
        )
    elif result == "blocked":
        summary = _build_review_blocked_message(
            verdict_count=verdict_count, total_tasks=total_tasks,
            check_count=check_count, total_checks=total_checks,
            missing_reviewer_evidence=missing_evidence,
            infrastructure_failure=infrastructure_failure,
        )
    elif result == "needs_rework":
        summary = "Review requested another execute pass. Re-run execute using the review findings as context."
    elif result == "force_proceeded":
        summary = "Review force-proceeded after the rework cap with only non-blocking review issues unresolved."
    else:
        summary = _format_review_success_summary(criteria if isinstance(criteria, list) else [])

    response: StepResponse = {
        "success": result in {"success", "force_proceeded"},
        "step": "review",
        "summary": summary,
        "artifacts": ["review.json", "finalize.json", "final.md"],
        "monitor_hint": build_monitor_hint(plan_dir),
        "next_step": next_step,
        "route_signal": decision.route_signal,
        "state": next_state,
        "issues": issues,
        "rework_items": list(worker.payload.get("rework_items", [])),
    }
    if force_proceed_blocked:
        response["deviations"] = [summary]
        response["warnings"] = [summary]
        response["_phase_outcome"] = "blocked_by_quality"
        _emit_phase_result(
            phase="review",
            state=state,
            plan_dir=plan_dir,
            exit_kind="blocked_by_quality",
            deviations=(_PhaseDeviation.from_string(summary),),
        )
    elif result == "force_proceeded":
        force_deviations = [issue for issue in issues if "Force-proceeding" in issue]
        response["deviations"] = force_deviations
        response["warnings"] = force_deviations
        _emit_phase_result(
            phase="review",
            state=state,
            plan_dir=plan_dir,
            exit_kind="success",
            deviations=tuple(_PhaseDeviation.from_string(d) for d in force_deviations),
        )
    else:
        _emit_phase_result(
            phase="review",
            state=state,
            plan_dir=plan_dir,
            exit_kind="success",
        )
    _attach_next_step_runtime(response)
    attach_agent_fallback(response, args)
    return response


def handle_review(root: Path, args: argparse.Namespace) -> StepResponse:
    with load_plan_locked(root, args.plan, step="review") as (plan_dir, state):
        require_state(state, "review", {STATE_EXECUTED})
        apply_profile_expansion(args, Path(state["config"]["project_dir"]), state=state)
        # Mirror the execute-phase sandbox-divergence warning so reviewers
        # notice when codex is pinned to a narrower tree than the plan's
        # project_dir.
        warn_if_work_dir_differs_from_project_dir(state)
        preflight_phase(root=root, state=state, phase="review")
        save_state_merge_meta(plan_dir, state)
        robustness = configured_robustness(state)
        plan_mode = state["config"].get("mode", "code")
        pre_check_flags: list[dict[str, Any]] = []
        if robustness in {"full", "thorough", "extreme"} and not is_prose_mode(state):
            pre_check_flags = _pkg.run_pre_checks(plan_dir, state, Path(state["config"]["project_dir"]))
        if robustness in {"full", "light", "thorough"}:
            resolved = None
            prompt_override = None
            prompt_kwargs = None
            if robustness in {"full", "thorough"}:
                resolved = _pkg.resolve_agent_mode("review", args)
                agent_type, _mode, _refreshed, _model = _agent_mode_parts(resolved)
                if _supports_prompt_kwargs(worker_module.run_step_with_worker):
                    prompt_kwargs = {"pre_check_flags": pre_check_flags}
                else:
                    prompt_override = _build_review_prompt_override(
                        agent_type,
                        state,
                        plan_dir,
                        root=root,
                        pre_check_flags=pre_check_flags,
                    )
            worker, agent, mode, refreshed = _run_worker(
                "review",
                state,
                plan_dir,
                args,
                root=root,
                resolved=resolved,
                prompt_override=prompt_override,
                prompt_kwargs=prompt_kwargs,
                read_only=True,
            )

            # ── T11: Scratch promotion for review (single-worker) ──
            # Prefer valid filled review_output.json over worker.payload;
            # fall back to worker.payload when scratch is missing/unmodified;
            # fail hard on modified invalid scratch when file-fill was
            # instructed (hermes agent).  Canonical promotion to
            # review.json is preserved unchanged below.
            from arnold_pipelines.megaplan.handlers.structured_output import (
                promote_scratch,
                require_scratch_filename_for_phase,
            )

            _scratch_filename = require_scratch_filename_for_phase("review")
            _seed_path = plan_dir / _scratch_filename
            _seed_json: str | None = None
            if _seed_path.exists():
                try:
                    _seed_json = _seed_path.read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError):
                    _seed_json = None

            _file_fill_instructed = agent == "hermes"

            _, _promoted = promote_scratch(
                plan_dir,
                _scratch_filename,
                _REVIEW_SCRATCH_KNOWN_KEYS,
                worker,
                seed_json=_seed_json,
                file_fill_instructed=_file_fill_instructed,
            )
            worker.payload = _promoted
            # ──────────────────────────────────────────────────────────

            _prepare_review_payload(worker.payload, pre_check_flags=pre_check_flags)
            _audit_review_payload_or_raise(
                plan_dir=plan_dir,
                state=state,
                payload=worker.payload,
                raw_output=worker.raw_output,
                duration_ms=worker.duration_ms,
            )
            if robustness in {"full", "thorough"}:
                _pkg.update_flags_after_review(plan_dir, worker.payload, iteration=state["iteration"])
            write_plan_artifact_json(
                plan_dir, "review.json", worker.payload,
                contract_context=create_step_io_contract_context(
                    operation=StepIOOperation.WRITE,
                    explicit_root=plan_dir,
                ),
            )
        else:
            rev_resolved = _pkg.resolve_agent_mode("review", args)
            agent_type, mode, refreshed, model = _agent_mode_parts(rev_resolved)
            if agent_type != "hermes" or os.getenv(MOCK_ENV_VAR) == "1":
                worker, agent, mode, refreshed = _run_worker(
                    "review",
                    state,
                    plan_dir,
                    args,
                    root=root,
                    resolved=(agent_type, mode, refreshed, model),
                    read_only=True,
                )

                # ── T11: Scratch promotion for review (single-worker, extreme) ──
                from arnold_pipelines.megaplan.handlers.structured_output import (
                    promote_scratch,
                    require_scratch_filename_for_phase,
                )

                _scratch_filename = require_scratch_filename_for_phase("review")
                _seed_path = plan_dir / _scratch_filename
                _seed_json: str | None = None
                if _seed_path.exists():
                    try:
                        _seed_json = _seed_path.read_text(encoding="utf-8")
                    except (OSError, UnicodeDecodeError):
                        _seed_json = None

                _file_fill_instructed = agent == "hermes"

                _, _promoted = promote_scratch(
                    plan_dir,
                    _scratch_filename,
                    _REVIEW_SCRATCH_KNOWN_KEYS,
                    worker,
                    seed_json=_seed_json,
                    file_fill_instructed=_file_fill_instructed,
                )
                worker.payload = _promoted
                # ──────────────────────────────────────────────────────────────

                _prepare_review_payload(worker.payload)
                _audit_review_payload_or_raise(
                    plan_dir=plan_dir,
                    state=state,
                    payload=worker.payload,
                    raw_output=worker.raw_output,
                    duration_ms=worker.duration_ms,
                )
                write_plan_artifact_json(
                    plan_dir, "review.json", worker.payload,
                    contract_context=create_step_io_contract_context(
                        operation=StepIOOperation.WRITE,
                        explicit_root=plan_dir,
                    ),
                )
                return _finalize_review_outcome(
                    root=root,
                    args=args,
                    plan_dir=plan_dir,
                    state=state,
                    worker=worker,
                    agent=agent,
                    mode=mode,
                    refreshed=refreshed,
                    robustness=robustness,
                )

            run_id = None
            try:
                run_id = set_active_step(
                    state,
                    step="review",
                    agent=agent_type,
                    mode=mode,
                    model=model,
                    **_active_step_fallback_fields("review", args, agent=agent_type, model=model),
                )
                _emit_phase_notice("review")
                save_state_merge_meta(plan_dir, state)
                checks = review_checks.checks_for_robustness("extreme")
                parallel_result = _pkg.run_parallel_review(
                    state,
                    plan_dir,
                    root=root,
                    model=model if agent_type == "hermes" else None,
                    checks=checks,
                    pre_check_flags=pre_check_flags,
                )
                criteria_payload = parallel_result.payload.get("criteria_payload")
                if not isinstance(criteria_payload, dict):
                    raise CliError("worker_parse_error", "Parallel review did not return a criteria payload object")
                merged_payload = dict(criteria_payload)
                merged_payload["checks"] = _prepare_parallel_review_checks(
                    list(parallel_result.payload.get("checks", [])),
                    check_specs=checks,
                )
                merged_payload["verified_flag_ids"] = list(parallel_result.payload.get("verified_flag_ids", []))
                merged_payload["disputed_flag_ids"] = list(parallel_result.payload.get("disputed_flag_ids", []))
                _prepare_review_payload(merged_payload, pre_check_flags=pre_check_flags)

                review_rework_items = _synthesize_review_rework_items(merged_payload["checks"])
                merged_payload.setdefault("rework_items", [])
                merged_payload.setdefault("issues", [])
                if review_rework_items:
                    merged_payload["rework_items"].extend(review_rework_items)
                    existing_issues = {str(issue) for issue in merged_payload["issues"] if isinstance(issue, str)}
                    for item in review_rework_items:
                        if item["issue"] not in existing_issues:
                            merged_payload["issues"].append(item["issue"])
                            existing_issues.add(item["issue"])
                    merged_payload["review_verdict"] = "needs_rework"

                _prepare_review_payload(merged_payload, pre_check_flags=pre_check_flags)
                _audit_review_payload_or_raise(
                    plan_dir=plan_dir,
                    state=state,
                    payload=merged_payload,
                    raw_output=parallel_result.raw_output,
                    duration_ms=parallel_result.duration_ms,
                )
                write_plan_artifact_json(
                    plan_dir, "review.json", merged_payload,
                    contract_context=create_step_io_contract_context(
                        operation=StepIOOperation.WRITE,
                        explicit_root=plan_dir,
                    ),
                )
                _pkg.update_flags_after_review(plan_dir, merged_payload, iteration=state["iteration"])
                worker = _wrap_parallel_review_worker(merged_payload, parallel_result)
                agent, mode, refreshed = "hermes", "persistent", True
            except CliError as error:
                clear_active_step(state, run_id=run_id)
                record_step_failure(plan_dir, state, step="review", iteration=state["iteration"], error=error)
                raise
            except Exception:
                clear_active_step(state, run_id=run_id)
                save_state_merge_meta(plan_dir, state)
                raise

        return _finalize_review_outcome(
            root=root,
            args=args,
            plan_dir=plan_dir,
            state=state,
            worker=worker,
            agent=agent,
            mode=mode,
            refreshed=refreshed,
            robustness=robustness,
        )
