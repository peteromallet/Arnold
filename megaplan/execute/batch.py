from __future__ import annotations

import argparse
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable

import megaplan.workers as worker_module
from megaplan._core import (
    apply_session_update,
    append_history,
    atomic_write_json,
    atomic_write_text,
    batch_artifact_path,
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
from megaplan.audits.quality_gates import capture_before_line_counts
from megaplan.observability.routing_ledger import (
    format_selected_spec,
    record_step_routing,
)
from megaplan.execute.aggregation import (
    _append_scope_drift_blocker,
    _build_aggregate_execution_payload,
    _compute_execute_scope_drift,
    _compute_scope_drift_for_execute_surface,
    _stable_unique_strings,
)
from megaplan.execute.merge import (
    TERMINAL_TASK_STATUSES,
    _merge_batch_results,
)
from megaplan.execute.quality import (
    AttributionResult,
    _auto_attribute_unclaimed_paths,
    _capture_git_status_snapshot,
    _capture_git_status_snapshot_recursive,
    _check_done_task_evidence,
    _check_done_task_evidence_by_kind,
    _collect_quality_deviations,
    _observe_git_changes,
)
from megaplan.execute.timeout import (
    _recover_execute_timeout,
    _resolve_execute_approval_mode,
)
from megaplan.orchestration.execution_evidence import validate_execution_evidence
from megaplan.orchestration.phase_result import Deviation
from megaplan.prompts import _execute_batch_prompt
from megaplan.receipts import build_receipt
from megaplan.receipts.extractors import execute_metrics
from megaplan.receipts.writer import write_receipt
from megaplan.types import (
    CliError,
    PlanState,
    STATE_BLOCKED,
    STATE_EXECUTED,
    STATE_FINALIZED,
    StepResponse,
)
from megaplan.blocker_recovery import evaluate_quality_blockers
from megaplan.workers import WorkerResult

log = logging.getLogger(__name__)

_BATCH_ARTIFACT_RE = re.compile(r"execution_batch_(\d+)\.json$")
_UNROUTABLE_REWORK_ATTEMPTS_KEY = "unroutable_rework_attempts"
_MAX_UNROUTABLE_REWORK_RERUNS = 2

def _resolve_tier_spec(
    args: argparse.Namespace,
    tier_spec: str,
    *,
    phase: str = "execute",
) -> tuple[str, str, str | None]:
    """Resolve a tier spec string to (agent, mode, model) without mutating *args*.

    Copies *args*, sets ``phase_model=["{phase}=<tier_spec>"]`` on the
    copy, and calls ``resolve_agent_mode``.  Does not prepend ahead of a
    user CLI override — the override guard in ``apply_profile_expansion``
    already strips ``tier_models.{phase}`` when ``--phase-model {phase}=…``
    is present, so this helper is only called when tier routing is active.
    """
    import copy

    tier_args = copy.copy(args)
    tier_args.phase_model = [f"{phase}={tier_spec}"]
    agent, _mode, _refreshed, model = worker_module.resolve_agent_mode(
        phase, tier_args
    )
    return agent, _mode, model


# Lowest complexity tier the auto-driver's tier-drop fallback will route to.
# Premium tier maps put cheaper / less-capable models below tier 3 (e.g. the
# DeepSeek tiers in profiles/premium.toml), so dropping below this floor risks
# routing a genuinely-hard task to a model that cannot do it.  A floor of 3
# keeps the worst-case drop at "premium-thinking" (e.g. Opus → Sonnet), which
# is exactly the move that unblocks a repeatedly-stalling premium worker.
DEFAULT_TIER_DROP_FLOOR = 3


def _max_execute_tier(args: argparse.Namespace) -> int | None:
    value = getattr(args, "max_execute_tier", None)
    if isinstance(value, int) and 1 <= value <= 5:
        return value
    return None


def _resolve_effective_tier_complexity(
    batch_complexity: int,
    tier_drop: int,
    *,
    floor: int = DEFAULT_TIER_DROP_FLOOR,
    tier_override_floor: int | None = None,
) -> int:
    """Apply an auto-driver tier-drop to a batch's resolved complexity.

    ``tier_drop`` is the number of tiers the driver has decided to drop for
    this dispatch after observing repeated worker stalls.  The result is
    clamped at ``floor`` so the fallback never routes below the lowest
    premium tier.  ``tier_drop <= 0`` is a no-op (normal routing).
    """
    effective_floor = floor
    if isinstance(tier_override_floor, int) and 1 <= tier_override_floor <= 5:
        effective_floor = max(effective_floor, tier_override_floor)
    if tier_drop <= 0:
        return max(effective_floor, batch_complexity) if tier_override_floor else batch_complexity
    return max(effective_floor, batch_complexity - tier_drop)


def _batch_tier_override_floor(
    finalize_data: dict[str, Any],
    batch_task_ids: list[str],
) -> int | None:
    wanted = set(batch_task_ids)
    floors: list[int] = []
    for task in finalize_data.get("tasks", []) or []:
        if not isinstance(task, dict) or task.get("id") not in wanted:
            continue
        override = task.get("tier_override")
        if isinstance(override, int) and 1 <= override <= 5:
            floors.append(override)
    return max(floors) if floors else None


# Private marker set: dispatcher return paths stamp one of these four values.
# Handlers later read _phase_outcome to derive the correct ExitKind for
# phase_result.json emission.
_PHASE_OUTCOMES = frozenset(
    {"success", "blocked_by_quality", "blocked_by_prereq", "timeout"}
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
    """Return a tier map with integer complexity keys.

    Persisted ``state.config.tier_models`` comes back from JSON with string
    keys. Dispatch always looks up by integer complexity, so normalize at
    consumption to avoid silent fallback to the flat model.
    """
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


def _is_codex_gpt5_family(model: str | None) -> bool:
    """Whether ``model`` is a codex GPT-5.x model (gpt-5.4, gpt-5.5, gpt-5.3-codex, ...).

    Codex differentiates work by reasoning effort rather than the exact gpt-5.x point
    release, and the provider routinely serves a newer same-family model than the one
    pinned (e.g. gpt-5.4 -> gpt-5.5) as upstream aliases or deprecates versions.
    """
    bare = _strip_provider_prefix(model)
    return isinstance(bare, str) and bare.lower().startswith("gpt-5")


def _models_match(selected: str | None, actual: str | None) -> bool:
    if not selected or not actual:
        return True
    if selected == actual or _strip_provider_prefix(selected) == _strip_provider_prefix(actual):
        return True
    # A provider serving a different model WITHIN the same codex gpt-5.x family is an
    # acceptable substitution (upstream aliasing/deprecation), not a routing failure that
    # should block execution. Cross-vendor mismatches (codex<->claude) are caught
    # separately by the agent-level audit, so this only relaxes same-family gpt-5.x
    # point-release differences.
    if _is_codex_gpt5_family(selected) and _is_codex_gpt5_family(actual):
        return True
    return False


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
    if routing.get("resolved_agent") and routing.get("actual_agent") != routing.get("resolved_agent"):
        degradations.append(
            f"selected agent {routing.get('resolved_agent')} but worker returned {routing.get('actual_agent')}"
        )
    if not _models_match(routing.get("resolved_model"), actual_model):
        degradations.append(
            f"selected model {routing.get('resolved_model')} but provider reported {actual_model}"
        )
    if degradations:
        try:
            from megaplan.observability.events import EventKind, emit

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
) -> tuple[int, int, int, int]:
    tracked_tasks = sum(
        1
        for task in finalize_data.get("tasks", [])
        if task.get("id") in active_task_ids
        and task.get("status") in TERMINAL_TASK_STATUSES
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


def _filter_non_terminal_quality_blocking_reasons(
    blocking_reasons: list[str],
    state: PlanState,
) -> list[str]:
    """Honor accepted quality-resolution events before deciding to block.

    Execute constructs some aggregate blockers directly from audit strings
    (tracking gaps, missing evidence, scope drift). Operators can resolve those
    quality blockers through the quality-gate ledger, so this final decision
    point must read the same ledger instead of treating the fresh strings as
    unconditionally terminal.
    """
    if not blocking_reasons:
        return []
    evaluation = evaluate_quality_blockers(state, blocking_reasons)
    non_terminal_messages = {
        blocker.message for blocker in evaluation.blockers if blocker.is_non_terminal
    }
    if not non_terminal_messages:
        return blocking_reasons
    return [reason for reason in blocking_reasons if reason not in non_terminal_messages]


def _blocked_task_reason(task_ids: Iterable[str]) -> str | None:
    blocked_ids = sorted({task_id for task_id in task_ids if task_id})
    if not blocked_ids:
        return None
    return (
        "task(s) reported status=blocked by the worker: "
        f"{', '.join(blocked_ids)}. Resolve or replan the blocked task(s) "
        "before continuing."
    )


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
    from megaplan.types import AgentMode as _AgentMode
    am_for_worker = _AgentMode(
        agent=agent,
        mode=mode,
        refreshed=refreshed,
        model=model,
        effort=effort,
        resolved_model=resolved_model if resolved_model is not None else model,
    )
    worker, agent, mode, refreshed = worker_module.run_step_with_worker(
        "execute",
        state,
        plan_dir,
        args,
        root=root,
        resolved=am_for_worker,
        prompt_override=prompt_override,
    )
    payload = dict(worker.payload)
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
    if not is_prose_mode(state):
        deviations.extend(
            _collect_quality_deviations(
                project_dir=project_dir,
                before_snapshot=before_snapshot,
                before_line_counts=before_line_counts,
                quality_config=quality_config,
                capture_git_status_snapshot_fn=capture_git_status_snapshot_fn,
            )
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
            )
        )
    if is_prose_mode(state):
        missing_task_evidence = _check_done_task_evidence(
            finalize_data.get("tasks", []),
            issues=deviations,
            should_classify=lambda task: task.get("id") in batch_task_id_set,
            has_evidence=lambda task: bool(task.get("sections_written")),
            has_advisory_evidence=lambda task: True,
            missing_message="Done tasks missing sections_written: ",
            advisory_message="",
        )
    else:
        missing_task_evidence = _check_done_task_evidence_by_kind(
            finalize_data.get("tasks", []),
            issues=deviations,
            should_classify=lambda task: task.get("id") in batch_task_id_set,
        )
    execution_audit = validate_execution_evidence(finalize_data, project_dir, mode=plan_mode, state=state)
    if attribution_result.records:
        execution_audit["auto_attribution"] = list(attribution_result.records)
    if execution_audit["skipped"]:
        deviations.append(f"Advisory audit skip: {execution_audit['reason']}")
    for finding in execution_audit["findings"]:
        deviations.append(f"Advisory audit finding: {finding}")
    payload["deviations"] = deviations
    atomic_write_json(batch_artifact_path(plan_dir, batch_number), payload)
    atomic_write_json(plan_dir / "execution_audit.json", execution_audit)
    atomic_write_json(plan_dir / "finalize.json", finalize_data)
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
    # In per-batch execute mode, finalize.json is only rewritten after the
    # final batch — between batches the per-task status overlay lives in
    # execution_batch_<n>.json. Apply that overlay so prerequisite checks
    # see the most recent on-disk truth.
    batch_status_overlay: dict[str, str] = {}
    for batch_path in list_batch_artifacts(plan_dir):
        match = _BATCH_ARTIFACT_RE.fullmatch(batch_path.name)
        if match is None:
            continue
        if int(match.group(1)) >= batch_number:
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
    completed_ids = {
        task["id"]
        for task in tasks
        if isinstance(task.get("id"), str)
        and batch_status_overlay.get(task["id"], task.get("status"))
        in {"done", "skipped"}
    }
    for prior_idx in range(batch_number - 1):
        prior_batch = global_batches[prior_idx]
        missing = [task_id for task_id in prior_batch if task_id not in completed_ids]
        if missing:
            raise CliError(
                "batch_prerequisites",
                f"Batch {batch_number} requires batches 1..{batch_number - 1} to be complete. "
                f"Batch {prior_idx + 1} has incomplete tasks: {', '.join(missing)}",
            )

    batch_task_ids = global_batches[batch_number - 1]
    active_task_ids = set(batch_task_ids)
    batch_sense_check_ids = _active_sense_check_ids(finalize_data, active_task_ids)
    batch_prompt = _execute_batch_prompt(
        state, plan_dir, batch_task_ids, completed_ids, root=root
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
    if tier_map:
        batch_complexity = compute_batch_complexity(finalize_data, batch_task_ids)
        raw_batch_complexity = batch_complexity
        # Auto-driver tier-drop fallback: after repeated worker stalls the
        # driver passes --tier-drop N to route this batch one (or N) tiers
        # lower, clamped at the premium floor. tier_drop=0 is normal routing.
        tier_drop = int(getattr(args, "tier_drop", 0) or 0)
        effective_complexity = _resolve_effective_tier_complexity(
            batch_complexity,
            tier_drop,
            tier_override_floor=_batch_tier_override_floor(finalize_data, batch_task_ids),
        )
        max_execute_tier = _max_execute_tier(args)
        if max_execute_tier is not None:
            effective_complexity = min(effective_complexity, max_execute_tier)
        tier_complexity = effective_complexity
        tier_spec = tier_map.get(effective_complexity)
        if tier_spec:
            tier_spec_raw = tier_spec
            tier_agent, tier_mode, tier_model = _resolve_tier_spec(
                args, tier_spec
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
            resolved_model=resolved_model,
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
                auto_approve=auto_approve,
                args=args,
                batch_number=batch_number,
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
    batch_blocked_ids = [
        task.get("id")
        for task in tracked_tasks
        if task.get("id") in set(batch_task_ids)
        and task.get("status") == "blocked"
    ]
    blocked_task_reason = _blocked_task_reason(batch_blocked_ids)
    if blocked_task_reason:
        blocking_reasons.append(blocked_task_reason)
    if result.routing_degradations:
        blocking_reasons.extend(result.routing_degradations)
    all_tracked = all(
        task.get("status") in {"done", "skipped"}
        for task in tracked_tasks
    )
    any_done = any(task.get("status") == "done" for task in tracked_tasks)
    if all_tracked and tracked_tasks and not any_done:
        blocking_reasons.append(
            "All tasks were skipped with none completed — execution produced no work."
        )
        all_tracked = False

    aggregate_payload: dict[str, Any] | None = None
    batch_payloads: list[dict[str, Any]] = []
    drift = None
    if is_final_batch and all_tracked:
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
        # _run_and_merge_batch already wrote execution_audit.json; this handler
        # only writes the aggregate execution.json after the batch returns.
        atomic_write_json(plan_dir / "execution.json", aggregate_payload)
        drift = _compute_scope_drift_for_execute_surface(
            project_dir=project_dir,
            aggregate_payload=aggregate_payload,
            state=state,
            phase_context=f"final execute batch {batch_number}/{batches_total}",
            plan_dir=plan_dir,
        )
        _append_scope_drift_blocker(blocking_reasons, state, drift)

    blocking_reasons = _filter_non_terminal_quality_blocking_reasons(
        blocking_reasons,
        state,
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
            output_file=f"execution_batch_{batch_number}.json",
            artifact_hash=sha256_file(batch_artifact_path(plan_dir, batch_number)),
            finalize_hash=result.finalize_hash,
            approval_mode=approval_mode,
            batch_complexity=tier_complexity if tier_routing_active else None,
            tier_model_spec=tier_spec_raw if tier_routing_active else None,
            tier_model_resolved=tier_resolved_model if tier_routing_active else None,
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
            prompt_tokens=result.worker.prompt_tokens,
            completion_tokens=result.worker.completion_tokens,
            total_tokens=result.worker.total_tokens,
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
        f"execution_batch_{batch_number}.json",
        "execution_audit.json",
        "finalize.json",
        "final.md",
    ]
    if aggregate_payload is not None and not blocked:
        artifacts.insert(0, "execution.json")
    if trace_written:
        artifacts.append("execution_trace.jsonl")

    if blocked:
        summary = (
            "Blocked: "
            + "; ".join(blocking_reasons)
            + ". Re-run execute to complete tracking."
        )
        next_step = "execute"
        response_state = STATE_BLOCKED if routing_blocked else STATE_FINALIZED
    elif is_final_batch and all_tracked:
        summary = result.payload.get("output", "Batch complete.") + tracking_note
        next_step = "review"
        response_state = STATE_EXECUTED
    else:
        summary = (
            f"Batch {batch_number}/{batches_total} complete.{tracking_note} "
            f"{batches_remaining} batch(es) remaining."
        )
        next_step = "execute"
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
    response_deviations = result.payload.get("deviations", [])
    if blocked:
        response_deviations = _stable_unique_strings(
            [*response_deviations, *blocking_reasons]
        )
    response: StepResponse = {
        "success": not blocked,
        "step": "execute",
        "summary": summary,
        "artifacts": artifacts,
        "monitor_hint": build_monitor_hint(plan_dir),
        "next_step": next_step,
        "state": response_state,
        "batch": batch_number,
        "batches_total": batches_total,
        "batches_remaining": batches_remaining,
        "files_changed": result.payload.get("files_changed", []),
        "deviations": response_deviations,
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
    if next_step == "execute" and not blocked:
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
        task["status"] = "pending"
        task["executor_notes"] = ""
        task["files_changed"] = []
        task["commands_run"] = []
        task["evidence_files"] = []
        task["reviewer_verdict"] = ""
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
) -> list[str]:
    """Skip interim baseline-dependent checkpoints when no baseline exists.

    A task whose contract is "introduce no new failures vs the recorded
    baseline" is not actionable when baseline capture failed. If such a task is
    placed before later implementation tasks, running it only produces an
    indeterminate block and prevents the consumer fixes that may make the suite
    meaningful. Defer only interim checkpoints; a final checkpoint with no
    downstream work remains runnable/blocking so the operator still gets an
    end-of-run signal.
    """
    if finalize_data.get("baseline_test_failures") is not None:
        return []
    tasks = finalize_data.get("tasks")
    if not isinstance(tasks, list):
        return []

    deferred_ids: list[str] = []
    for index, task in enumerate(tasks):
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
        if not _has_downstream_runnable_tasks(tasks, checkpoint_index=index):
            continue

        prior_notes = str(task.get("executor_notes") or "").strip()
        defer_note = (
            "Deferred by harness: baseline_test_failures is null, so this "
            "interim no-new-failures checkpoint cannot compare against a "
            "recorded baseline. Continuing to downstream implementation tasks; "
            "the final verification/review phase remains authoritative."
        )
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
    return deferred_ids


def _review_requests_rework(review_data: dict[str, Any]) -> bool:
    return (
        review_data.get("review_verdict") == "needs_rework"
        or bool(review_data.get("rework_items"))
    )


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
        task_id = item.get("task_id")
        if not isinstance(task_id, str) or not task_id:
            unrunnable.append(str(task_id or "<missing>"))
            continue
        if source == "review_incomplete":
            unrunnable.append(task_id)
            continue
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
        "next_step": "execute",
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
    unmatched = ", ".join(sorted(set(unrunnable_task_ids)))
    reason = (
        "review requested rework but no runnable finalize task IDs could be derived. "
        f"Unmatched rework task_id(s): {unmatched}. "
        "Re-run review so rework_items reference concrete finalize task IDs."
    )
    meta[_UNROUTABLE_REWORK_ATTEMPTS_KEY] = attempts

    if attempts <= _MAX_UNROUTABLE_REWORK_RERUNS:
        state["current_state"] = STATE_EXECUTED
        summary = (
            "Review requested rework with only unroutable task IDs "
            f"({unmatched}); re-running review "
            f"({attempts}/{_MAX_UNROUTABLE_REWORK_RERUNS}) instead of blocking execute."
        )
        append_history(
            state,
            make_history_entry(
                "execute",
                duration_ms=0,
                cost_usd=0.0,
                result="rerun_review",
                message=summary,
            ),
        )
        save_state_merge_meta(plan_dir, state)
        from megaplan.observability.events import EventKind, emit

        emit(
            EventKind.PHASE_RETRY,
            plan_dir=plan_dir,
            phase="review",
            payload={
                "reason": "unroutable_review_rework",
                "attempt": attempts,
                "max_attempts": _MAX_UNROUTABLE_REWORK_RERUNS,
                "unrunnable_rework_task_ids": sorted(set(unrunnable_task_ids)),
            },
        )
        response: StepResponse = {
            "success": True,
            "step": "execute",
            "summary": summary,
            "artifacts": ["review.json", "finalize.json", "final.md"],
            "monitor_hint": build_monitor_hint(plan_dir),
            "next_step": "review",
            "state": STATE_EXECUTED,
            "files_changed": [],
            "deviations": [],
            "warnings": [summary],
            "auto_approve": auto_approve,
            "user_approved_gate": bool(state["meta"].get("user_approved_gate", False)),
            "unrunnable_rework_task_ids": sorted(set(unrunnable_task_ids)),
            "_phase_outcome": "success",
        }
        _attach_next_step_runtime(response)
        return response

    from megaplan.observability.events import EventKind, emit

    emit(
        EventKind.STATE_TRANSITION,
        plan_dir=plan_dir,
        phase="execute",
        payload={
            "reason": "unroutable_review_rework",
            "from": STATE_FINALIZED,
            "to": STATE_BLOCKED,
            "attempt": attempts,
            "max_attempts": _MAX_UNROUTABLE_REWORK_RERUNS,
            "unrunnable_rework_task_ids": sorted(set(unrunnable_task_ids)),
        },
    )
    response = _block_no_runnable_rework(
        plan_dir=plan_dir,
        state=state,
        auto_approve=auto_approve,
        reason=(
            f"{reason} Review re-run attempts exhausted "
            f"({attempts - 1}/{_MAX_UNROUTABLE_REWORK_RERUNS}); "
            "resolve the quality blocker or recover-blocked after operator review."
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
    from megaplan.observability.events import EventKind, emit

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
    global_config = load_config()
    quality_config = global_config.get("quality_checks", {})
    project_dir = Path(state["config"]["project_dir"])
    tasks = finalize_data.get("tasks", [])

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
        reset_ids = _reset_blocked_tasks_to_pending(
            finalize_data,
            exclude_task_ids=baseline_unavailable_ids,
        )
        if reset_ids:
            atomic_write_json(plan_dir / "finalize.json", finalize_data)
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

    deferred_checkpoint_ids = _defer_baseline_unavailable_checkpoints(finalize_data)
    if deferred_checkpoint_ids:
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
    completed_task_ids = {
        task["id"]
        for task in tasks
        if task.get("status") in {"done", "skipped"} and isinstance(task.get("id"), str)
    }
    blocked_task_ids = {
        task["id"]
        for task in tasks
        if task.get("status") == "blocked" and isinstance(task.get("id"), str)
    }
    pending_tasks = [
        task
        for task in tasks
        if task.get("status") == "pending" and isinstance(task.get("id"), str)
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
                            "review requested rework but no runnable finalize task IDs could be derived."
                            " Re-run review so rework_items reference concrete finalize task IDs."
                        ),
                        unrunnable_task_ids=unrunnable_rework_task_ids,
                    )
                # Runnable rework exists. If unroutable items ALSO coexist, the
                # unroutable subset cannot be cleared by re-running execute on the
                # runnable tasks, so we must track the same unroutable-rework cap
                # here (DEFECT 1) — independent of the runnable items — and escalate
                # to recoverable-blocked once it is exceeded, instead of silently
                # dropping the unroutable findings every cycle. Only reset the
                # counter when there are zero unroutable items (all rework routable).
                if unrunnable_rework_task_ids:
                    meta = state.setdefault("meta", {})
                    prior_attempts = meta.get(_UNROUTABLE_REWORK_ATTEMPTS_KEY, 0)
                    attempts = (
                        prior_attempts + 1 if isinstance(prior_attempts, int) else 1
                    )
                    meta[_UNROUTABLE_REWORK_ATTEMPTS_KEY] = attempts
                    if attempts > _MAX_UNROUTABLE_REWORK_RERUNS:
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
            atomic_write_json(plan_dir / "finalize.json", finalize_data)
            # Recompute blocked_task_ids after reset — should now be empty
            blocked_task_ids = {
                task["id"]
                for task in tasks
                if task.get("status") == "blocked" and isinstance(task.get("id"), str)
            }
        # Now, only short-circuit if blocked tasks remain (within-session)
        if blocked_task_ids:
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
                    "next_step": "execute",
                    "state": STATE_FINALIZED,
                    "files_changed": [],
                    "deviations": _deviation_dicts(baseline_deviations),
                    "warnings": [summary],
                    "auto_approve": auto_approve,
                    "user_approved_gate": bool(
                        state["meta"].get("user_approved_gate", False)
                    ),
                    "_phase_outcome": "blocked_by_quality",
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
                "next_step": "execute",
                "state": STATE_FINALIZED,
                "files_changed": [],
                "deviations": [],
                "warnings": [summary],
                "auto_approve": auto_approve,
                "user_approved_gate": bool(state["meta"].get("user_approved_gate", False)),
                "blocked_task_ids": sorted(prereq_blocked_ids or blocked_task_ids),
                "_phase_outcome": "blocked_by_prereq",
            }
            if baseline_deviations:
                response["deviations"] = _deviation_dicts(baseline_deviations)
            _attach_next_step_runtime(response)
            return response

    effective_completed_task_ids = (
        completed_task_ids - set(review_rework_task_ids)
        if rework_mode
        else completed_task_ids
    )

    if (
        all_task_ids
        and not pending_tasks
        and not blocked_task_ids
        and set(all_task_ids) <= effective_completed_task_ids
    ):
        max_tasks_per_batch = _resolve_max_tasks_per_batch(state, args)
        expected_batches = split_oversized_batches(
            compute_global_batches(finalize_data),
            max_tasks_per_batch,
        )
        batch_payloads = [read_json(path) for path in list_batch_artifacts(plan_dir)]
        plan_mode = state["config"].get("mode", "code")
        aggregate_payload = _build_aggregate_execution_payload(
            batch_payloads,
            completed_batches=len(batch_payloads),
            total_batches=max(len(expected_batches), len(batch_payloads)),
            mode=plan_mode,
            plan_dir=plan_dir,
            state=state,
        )
        if not aggregate_payload.get("output"):
            aggregate_payload["output"] = (
                f"Execution already complete: {len(completed_task_ids)}/{len(all_task_ids)} "
                "tasks tracked."
            )
        execution_audit = validate_execution_evidence(
            finalize_data,
            project_dir,
            mode=plan_mode,
            state=state,
        )
        atomic_write_json(plan_dir / "execution.json", aggregate_payload)
        atomic_write_json(plan_dir / "execution_audit.json", execution_audit)
        atomic_write_json(plan_dir / "finalize.json", finalize_data)
        atomic_write_text(
            plan_dir / "final.md", render_final_md(finalize_data, phase="execute")
        )
        state["current_state"] = STATE_EXECUTED
        append_history(
            state,
            make_history_entry(
                "execute",
                duration_ms=0,
                cost_usd=0.0,
                result="success",
                output_file="execution.json",
            ),
        )
        save_state_merge_meta(plan_dir, state)
        response: StepResponse = {
            "success": True,
            "step": "execute",
            "summary": aggregate_payload.get("output", "Execution already complete."),
            "artifacts": [
                "execution.json",
                "execution_audit.json",
                "finalize.json",
                "final.md",
            ],
            "monitor_hint": build_monitor_hint(plan_dir),
            "next_step": "review",
            "state": STATE_EXECUTED,
            "files_changed": aggregate_payload.get("files_changed", []),
            "deviations": aggregate_payload.get("deviations", []),
            "warnings": [],
            "auto_approve": auto_approve,
            "user_approved_gate": bool(state["meta"].get("user_approved_gate", False)),
            "_phase_outcome": "success",
        }
        _attach_next_step_runtime(response)
        return response

    pending_batches = compute_task_batches(
        pending_tasks, completed_ids=effective_completed_task_ids
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
    single_batch_mode = (
        not rework_mode
        and bool(pending_tasks)
        and len(split_batches) <= 1
        and len(all_task_ids) <= max_tasks_per_batch
    )
    global_batches = split_oversized_batches(
        compute_global_batches(finalize_data),
        max_tasks_per_batch,
    )
    global_batch_lookup = {
        tuple(batch): index + 1 for index, batch in enumerate(global_batches)
    }
    batches_to_run = [all_task_ids] if single_batch_mode else split_batches
    if not batches_to_run:
        return _block_no_runnable_rework(
            plan_dir=plan_dir,
            state=state,
            auto_approve=auto_approve,
            reason="no pending tasks or runnable review rework tasks are available for execute.",
        )
    total_batches = len(batches_to_run) or 1
    active_task_ids = set(
        all_task_ids if single_batch_mode else [task["id"] for task in pending_tasks]
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
    timeout_error: CliError | None = None
    latest_session_id: str | None = None
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
            )
        )
        batch_number_for_artifact = (
            1
            if single_batch_mode
            else global_batch_lookup.get(tuple(batch_task_ids), batch_index)
        )
        batch_sense_check_ids = (
            all_sense_check_ids
            if single_batch_mode
            else _active_sense_check_ids(finalize_data, set(batch_task_ids))
        )
        batches_total_for_observation = total_batches

        # Per-batch tier resolution: select the model for the max task
        # complexity in this batch.  Falls back to the caller-provided
        # agent/mode/model when tier_map is None or the complexity has no entry.
        batch_agent, batch_mode, batch_refreshed, batch_model = (
            agent, mode, refreshed, model
        )
        # Bound per-batch context: when fresh_session_per_batch is on, force a
        # fresh worker session for every batch so the executor's conversation
        # history cannot snowball across batches. Each batch prompt already
        # carries the completed-task context it needs (see _execute_batch_prompt),
        # so continuity is preserved by the prompt, not by an ever-growing session
        # that is re-sent on every tool turn (the 2-3M cumulative-token / stalled
        # -turn failure mode on large plans). First batch keeps the caller's
        # refreshed value so a same-session resume from a prior phase still works.
        if not single_batch_mode and get_effective(
            "execution", "fresh_session_per_batch"
        ):
            # Refresh every batch, INCLUDING batch 1: separate `megaplan execute`
            # reruns of the auto-loop (the driver restarts execute after each
            # timeout/retry) otherwise resume the SAME persistent executor session
            # and keep growing it across invocations — the cross-invocation half
            # of the snowball. Batch 1 of a rerun is a fresh batch of pending
            # tasks, so a fresh session is correct.
            batch_refreshed = True
        # Tier routing per-batch observability (only populated when active).
        batch_raw_complexity: int | None = None
        batch_tier_complexity: int | None = None
        batch_tier_spec: str | None = None
        if tier_map:
            batch_complexity = compute_batch_complexity(
                finalize_data, batch_task_ids
            )
            batch_raw_complexity = batch_complexity
            # Auto-driver tier-drop fallback (see handle_execute_one_batch).
            tier_drop = int(getattr(args, "tier_drop", 0) or 0)
            effective_complexity = _resolve_effective_tier_complexity(
                batch_complexity,
                tier_drop,
                tier_override_floor=_batch_tier_override_floor(finalize_data, batch_task_ids),
            )
            max_execute_tier = _max_execute_tier(args)
            if max_execute_tier is not None:
                effective_complexity = min(effective_complexity, max_execute_tier)
            batch_tier_complexity = effective_complexity
            tier_spec = tier_map.get(effective_complexity)
            if tier_spec:
                batch_tier_spec = tier_spec
                tier_agent, tier_mode, tier_model = _resolve_tier_spec(
                    args, tier_spec
                )
                batch_agent, batch_mode, batch_model = (
                    tier_agent, tier_mode, tier_model
                )
                # Freshness: first batch keeps the caller's refreshed
                # value (unless rework/block retry already forced it);
                # later batches force a fresh session when the resolved
                # model identity differs from the previous batch.
                if batch_index == 1:
                    batch_refreshed = refreshed  # already set by caller
                elif prev_batch_identity is not None:
                    new_identity = (batch_agent, batch_model)
                    if new_identity != prev_batch_identity:
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
        latest_session_id = result.worker.session_id
        apply_session_update(
            state,
            "execute",
            result.agent,
            result.worker.session_id,
            mode=result.mode,
            refreshed=result.refreshed,
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
            })
        batch_payloads.append(result.payload)
        all_attribution_records.extend(result.attribution_records)
        routing_degradations.extend(result.routing_degradations)
        if result.worker.trace_output is not None:
            trace_chunks.append(result.worker.trace_output)
        completed_task_ids.update(
            task_id
            for task_id in batch_task_ids
            if task_id
            in {
                task["id"]
                for task in finalize_data.get("tasks", [])
                if task.get("status") in {"done", "skipped"}
                and isinstance(task.get("id"), str)
            }
        )
        newly_blocked_task_ids = {
            task["id"]
            for task in finalize_data.get("tasks", [])
            if task.get("status") == "blocked"
            and isinstance(task.get("id"), str)
            and task["id"] in set(batch_task_ids)
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
    aggregate_payload = _build_aggregate_execution_payload(
        batch_payloads,
        completed_batches=len(batch_payloads),
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
    execution_audit = validate_execution_evidence(
        finalize_data,
        project_dir,
        mode=state["config"].get("mode", "code"),
        state=state,
    )
    deviations = list(aggregate_payload.get("deviations", []))
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
    if all_attribution_records:
        execution_audit["auto_attribution"] = all_attribution_records
    if blocked_task_ids:
        deviations.append(
            f"Pre-existing blocked tasks treated as satisfied for scheduling: "
            f"{sorted(blocked_task_ids)}. Downstream tasks ran assuming the blocked "
            f"work is handled out-of-band; re-run those tasks once the blockage is resolved."
        )
    aggregate_payload["deviations"] = deviations
    atomic_write_json(plan_dir / "execution.json", aggregate_payload)
    drift = _compute_scope_drift_for_execute_surface(
        project_dir=project_dir,
        aggregate_payload=aggregate_payload,
        state=state,
        phase_context=f"execute auto-loop aggregate after {len(batch_payloads)}/{total_batches} completed batches",
        plan_dir=plan_dir,
    )
    atomic_write_json(plan_dir / "execution_audit.json", execution_audit)
    atomic_write_json(plan_dir / "finalize.json", finalize_data)
    atomic_write_text(
        plan_dir / "final.md", render_final_md(finalize_data, phase="execute")
    )
    finalize_hash = sha256_file(plan_dir / "finalize.json")

    tracked_tasks, total_tasks, acknowledged_checks, total_checks = (
        _count_execute_tracking(
            finalize_data,
            active_task_ids=active_task_ids,
            active_sense_check_ids=active_sense_check_ids,
        )
    )
    if is_prose_mode(state):
        missing_task_evidence = _check_done_task_evidence(
            finalize_data.get("tasks", []),
            issues=deviations,
            should_classify=lambda task: task.get("id") in active_task_ids,
            has_evidence=lambda task: bool(task.get("sections_written")),
            has_advisory_evidence=lambda task: True,
            missing_message="Done tasks missing sections_written: ",
            advisory_message="",
        )
    else:
        missing_task_evidence = _check_done_task_evidence_by_kind(
            finalize_data.get("tasks", []),
            issues=deviations,
            should_classify=lambda task: task.get("id") in active_task_ids,
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
    deferred_checkpoint_ids = _defer_baseline_unavailable_checkpoints(finalize_data)
    if deferred_checkpoint_ids:
        atomic_write_json(plan_dir / "finalize.json", finalize_data)
        tracking_note = _format_execute_tracking_note(
            merged_count=tracked_tasks,
            total_tasks=total_tasks,
            acknowledged_count=acknowledged_checks,
            total_checks=total_checks,
        )
        log.info(
            "deferred baseline-unavailable interim verification checkpoint(s): %s",
            ", ".join(deferred_checkpoint_ids),
        )
    active_blocked_task_ids = {
        task["id"]
        for task in finalize_data.get("tasks", [])
        if task.get("status") == "blocked"
        and isinstance(task.get("id"), str)
        and task["id"] in active_task_ids
    }
    baseline_deviations = baseline_unavailable_checkpoint_deviations(
        finalize_data,
        active_blocked_task_ids,
    )
    baseline_blocked_task_ids = {
        deviation.task_id
        for deviation in baseline_deviations
        if deviation.task_id is not None
    }
    prereq_blocked_task_ids = active_blocked_task_ids - baseline_blocked_task_ids
    blocked_task_reason = _blocked_task_reason(prereq_blocked_task_ids)
    if blocked_task_reason:
        blocking_reasons.append(blocked_task_reason)
    blocking_reasons.extend(_deviation_messages(baseline_deviations))
    _append_scope_drift_blocker(blocking_reasons, state, drift)
    if routing_degradations:
        blocking_reasons.extend(routing_degradations)

    blocking_reasons = _filter_non_terminal_quality_blocking_reasons(
        blocking_reasons,
        state,
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
            state, "execute", agent, latest_session_id, mode=mode, refreshed=refreshed
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
        prompt_tokens=total_prompt_tokens,
        completion_tokens=total_completion_tokens,
        total_tokens=total_total_tokens,
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
    elif prereq_blocked_task_ids:
        phase_outcome = "blocked_by_prereq"
    elif blocked:
        phase_outcome = "blocked_by_quality"
    else:
        phase_outcome = "success"
    response_deviations = deviations
    if blocked and phase_outcome == "blocked_by_quality":
        baseline_messages = set(_deviation_messages(baseline_deviations))
        quality_reason_strings = [
            reason for reason in blocking_reasons if reason not in baseline_messages
        ]
        response_deviations = [
            *_stable_unique_strings([*deviations, *quality_reason_strings]),
            *_deviation_dicts(baseline_deviations),
        ]

    # Collect blocked task notes for blocked_by_prereq path
    blocked_task_notes: dict[str, str] = {}
    if prereq_blocked_task_ids:
        for task in finalize_data.get("tasks", []):
            tid = task.get("id")
            if isinstance(tid, str) and tid in prereq_blocked_task_ids:
                notes = task.get("executor_notes") or ""
                if notes:
                    blocked_task_notes[tid] = str(notes)

    response: StepResponse = {
        "success": not blocked and timeout_error is None,
        "step": "execute",
        "summary": summary,
        "artifacts": artifacts,
        "monitor_hint": build_monitor_hint(plan_dir),
        "next_step": "execute" if blocked or timeout_error is not None else "review",
        "state": (
            STATE_BLOCKED
            if routing_blocked
            else STATE_FINALIZED if blocked or timeout_error is not None else STATE_EXECUTED
        ),
        "files_changed": aggregate_payload.get("files_changed", []),
        "deviations": response_deviations,
        "warnings": [summary] if blocked or timeout_error is not None else [],
        "auto_approve": auto_approve,
        "user_approved_gate": user_approved_gate,
        "_phase_outcome": phase_outcome,
    }
    if prereq_blocked_task_ids:
        response["blocked_task_ids"] = sorted(prereq_blocked_task_ids)
    if routing_blocked:
        response["result"] = "blocked"
    if blocked_task_notes:
        response["blocked_task_notes"] = blocked_task_notes
    _attach_next_step_runtime(response)
    return response
