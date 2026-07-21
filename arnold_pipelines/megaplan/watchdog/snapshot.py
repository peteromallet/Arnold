"""Snapshot construction for the live watchdog.

M9 — T17: process, tmux, heartbeat, and activity facts are now correlated
*evidence only*. ``build_snapshot`` accepts an optional ``source_cursor_vector``
plus per-plan WBC attempt-identity envelopes and joins them to the discovered
processes via :func:`classify_worker_liveness`. The resulting liveness verdict
(matched/recycled/hung/dead/unrelated) is attached to each ``Incident`` and to
the ``Snapshot`` as a display-only ``liveness_authority`` annotation. No path
through this module converts liveness into a success, completion, repair, or
dispatch verdict.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from arnold_pipelines.megaplan.pipelines.live_supervisor.model import (
    CheckFinding,
    Incident,
    PlanEntry,
    SignalBundle,
    Snapshot,
    Triage,
)
from arnold_pipelines.megaplan.watchdog.correlate import (
    LIVENESS_DEAD,
    LIVENESS_HUNG,
    LIVENESS_MATCHED,
    LIVENESS_RECYCLED,
    LIVENESS_UNRELATED,
    RUNNER_LOST,
    RUNNER_UNKNOWN,
    _format_source_cursor,
    _path_contains,
    classify_worker_liveness,
    correlate_processes_to_plans,
    infer_plan_dirs_from_processes,
)
from arnold_pipelines.megaplan.watchdog.discovery import discover_plans, read_plan_state
from arnold_pipelines.megaplan.watchdog.log import log_event
from arnold_pipelines.megaplan.watchdog.orphans import find_orphan_processes
from arnold_pipelines.megaplan.watchdog.processes import scan_processes
from arnold_pipelines.megaplan.watchdog.signals import compute_signal_bundle


def _triage_from_signals(
    signals: SignalBundle,
    has_live_process: bool,
) -> Triage:
    if has_live_process:
        return Triage.LIVE
    age = signals.last_event_age_seconds
    if age is None:
        return Triage.MAYBE_LIVE
    if age < 300:
        return Triage.RECENT
    return Triage.STALE


def _plan_recency_age_seconds(plan_dir: Path, signals: SignalBundle) -> float:
    """Best estimate of how stale a plan is: min(state mtime age, last event age)."""
    now = time.time()
    ages: list[float] = []
    state_file = plan_dir / "state.json"
    try:
        ages.append(now - state_file.stat().st_mtime)
    except Exception:
        pass
    if signals.last_event_age_seconds is not None:
        ages.append(signals.last_event_age_seconds)
    events_file = plan_dir / "events.ndjson"
    try:
        ages.append(now - events_file.stat().st_mtime)
    except Exception:
        pass
    return min(ages) if ages else float("inf")


def _format_liveness_authority_summary(
    per_plan: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Aggregate per-plan liveness classifications into a display-only summary.

    The summary counts classifications and records the worst ``runner_verdict``
    observed. It never authorizes action: ``authority`` is always
    ``evidence_extracted_non_authoritative``.
    """
    counts: dict[str, int] = {}
    worst = RUNNER_UNKNOWN
    for entry in per_plan.values():
        classification = entry.get("classification", LIVENESS_UNRELATED)
        counts[classification] = counts.get(classification, 0) + 1
        verdict = entry.get("runner_verdict", RUNNER_UNKNOWN)
        # ``lost`` is "worse" than ``unknown`` for display ordering, but neither
        # is authority.
        if verdict == RUNNER_LOST:
            worst = RUNNER_LOST
    return {
        "authority": "evidence_extracted_non_authoritative",
        "classification_counts": dict(counts),
        "worst_runner_verdict": worst,
        "note": (
            "liveness is correlated evidence about in-flight attempts; it never "
            "authorizes success, completion, repair, or dispatch"
        ),
    }


def _collect_snapshot_evidence_gaps(
    plan: PlanEntry,
    liveness: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Collect structured evidence gaps for one plan's liveness correlation.

    Gaps are pure display annotations and never feed dispatch/completion/etc.
    """
    gaps: dict[str, Any] = {}
    if liveness is None:
        gaps["liveness_classification"] = {
            "gap": "liveness_unclassified",
            "reason": "no worker process correlated to this plan; liveness unknown",
            "evidence_status": "missing",
        }
        return gaps
    classification = liveness.get("classification")
    if classification in (LIVENESS_RECYCLED, LIVENESS_HUNG, LIVENESS_DEAD, LIVENESS_UNRELATED):
        gaps["liveness_classification"] = {
            "gap": f"worker_{classification}",
            "reason": liveness.get("reason", f"worker classified as {classification}"),
            "evidence_status": "degraded" if classification != LIVENESS_DEAD else "dead",
        }
    return gaps


def build_incidents(
    plans: tuple[PlanEntry, ...],
    signal_bundles: dict[str, SignalBundle],
    live_plan_ids: set[str],
    liveness_authority_map: Mapping[str, Mapping[str, Any]] | None = None,
) -> tuple[Incident, ...]:
    incidents: list[Incident] = []
    for plan in plans:
        signals = signal_bundles.get(plan.plan_id, SignalBundle(
            liveness="unknown",
            liveness_reason="no signals computed",
            block_details={},
            doctor_findings=(),
            degraded=True,
            failure_reason="missing signal bundle",
        ))
        triage = _triage_from_signals(signals, plan.plan_id in live_plan_ids)
        liveness = None
        if liveness_authority_map is not None:
            liveness = dict(liveness_authority_map.get(plan.plan_id) or {})
        incidents.append(
            Incident(
                plan_entry=plan,
                signals=signals,
                triage=triage,
                liveness_authority=liveness or {},
            )
        )
    return tuple(incidents)


def build_snapshot(
    roots: tuple[str, ...] | None = None,
    *,
    max_age_hours: float | None = None,
    process_scanner: Any | None = None,
    logger: logging.Logger | None = None,
    source_cursor_vector: Mapping[str, Any] | None = None,
    wbc_terminal_envelopes: Mapping[str, Mapping[str, Any]] | None = None,
    wbc_gap_envelopes: Mapping[str, Mapping[str, Any]] | None = None,
    heartbeat_fresh_by_plan: Mapping[str, bool] | None = None,
) -> Snapshot:
    """Discover plans and build a Snapshot with signal bundles and triage.

    Uses direct filesystem/process access only; does not require a working
    ``megaplan`` CLI.

    When ``max_age_hours`` is set, plans are only included if they have a live
    process or some recent activity (state mtime or event mtime/age) within the
    window. ``None`` means no age filter.

    M9 parameters (all *evidence only*, never authority):

    * ``source_cursor_vector`` — canonical source cursors attached to the
      snapshot as a display-only ``source_cursor_vector`` field.
    * ``wbc_terminal_envelopes`` / ``wbc_gap_envelopes`` — per-plan (keyed by
      ``plan_id``) canonical WBC attempt-identity envelopes used to join process
      facts to attempt identity for liveness classification.
    * ``heartbeat_fresh_by_plan`` — per-plan heartbeat freshness booleans.

    The liveness verdict computed from these joins is attached to each incident
    and to the snapshot as ``liveness_authority``; it is always marked
    ``evidence_extracted_non_authoritative`` and never feeds dispatch,
    completion, cancellation, publication, or delivery.
    """
    plan_dirs = discover_plans(roots)

    if logger is not None:
        log_event(logger, "discovery_complete", discovered_plans=len(plan_dirs), roots=",".join(str(r) for r in (roots or ())))

    scanner = process_scanner if process_scanner is not None else scan_processes
    processes = scanner()
    inferred_dirs = infer_plan_dirs_from_processes(processes)

    if logger is not None:
        log_event(
            logger,
            "process_scan_complete",
            matched_processes=len(processes),
            inferred_plans=len(inferred_dirs),
        )

    plans: list[PlanEntry] = []
    seen_plan_dirs: set[Path] = set()

    def _add_plan(plan_dir: Path) -> None:
        canonical = plan_dir.resolve()
        if canonical in seen_plan_dirs:
            return
        seen_plan_dirs.add(canonical)
        state = read_plan_state(canonical) or {}
        plan_name = state.get("name") or canonical.name
        repo_path = state.get("repo_path") or (
            str(canonical.parents[2]) if len(canonical.parents) >= 3 else str(canonical)
        )
        plans.append(
            PlanEntry(
                plan_id=canonical.name,
                plan_name=plan_name,
                plan_dir=str(canonical),
                repo_path=repo_path,
                state=state,
            )
        )

    for plan_dir in plan_dirs:
        _add_plan(plan_dir)
    for plan_dir in inferred_dirs:
        _add_plan(plan_dir)

    correlations = correlate_processes_to_plans(processes, tuple(plans))
    live_plan_ids: set[str] = {c.plan_dir.name for c in correlations}
    orphans_by_plan = find_orphan_processes(processes, correlations)

    # Build a pid -> process lookup so we can join correlated processes to WBC
    # attempt identity for liveness classification.
    proc_by_pid: dict[int, Any] = {}
    for proc in processes:
        try:
            pid = int(proc["pid"]) if isinstance(proc, dict) else int(getattr(proc, "pid"))
            proc_by_pid[pid] = proc
        except Exception:
            continue

    if logger is not None:
        log_event(
            logger,
            "correlation_complete",
            correlations=len(correlations),
            live_plan_ids=",".join(sorted(live_plan_ids)) if live_plan_ids else "",
            orphan_plans=len(orphans_by_plan),
        )
        for plan_dir, orphans in orphans_by_plan.items():
            for orphan in orphans:
                log_event(
                    logger,
                    "orphan_detected",
                    plan_id=plan_dir.name,
                    pid=orphan.pid,
                    category=orphan.category,
                    elapsed_seconds=orphan.elapsed_seconds,
                    reason=orphan.reason,
                )

    signal_bundles: dict[str, SignalBundle] = {}
    for plan in plans:
        signals = compute_signal_bundle(Path(plan.plan_dir), plan.state)
        orphan_findings: list[CheckFinding] = []
        for orphan in orphans_by_plan.get(Path(plan.plan_dir), ()):
            orphan_findings.append(
                CheckFinding(
                    scope="plan",
                    check="orphan_subprocess",
                    status="fail",
                    message=(
                        f"orphan {orphan.category} pid={orphan.pid} "
                        f"elapsed={orphan.elapsed_seconds:.0f}s reason={orphan.reason}"
                    ),
                )
            )
        if plan.plan_id in live_plan_ids:
            # A lock held by a live process is not stale; drop stale_lock findings
            # so live terminal plans are not misclassified as harness issues.
            live_findings = tuple(
                f for f in signals.doctor_findings if f.check != "stale_lock"
            )
            signals = SignalBundle(
                liveness="live_process",
                liveness_reason=f"live process correlated to {plan.plan_dir}",
                block_details=signals.block_details,
                doctor_findings=live_findings + tuple(orphan_findings),
                has_in_flight_llm=signals.has_in_flight_llm,
                last_event_age_seconds=signals.last_event_age_seconds,
            )
        elif orphan_findings:
            signals = SignalBundle(
                liveness=signals.liveness,
                liveness_reason=signals.liveness_reason,
                block_details=signals.block_details,
                doctor_findings=signals.doctor_findings + tuple(orphan_findings),
                has_in_flight_llm=signals.has_in_flight_llm,
                last_event_age_seconds=signals.last_event_age_seconds,
            )
        signal_bundles[plan.plan_id] = signals

    # M9 — join process facts to WBC attempt identity for liveness
    # classification. The verdict is evidence-only: recycled/hung/dead/unrelated
    # workers resolve to unknown/lost, never success or repair.
    liveness_authority_map: dict[str, dict[str, Any]] = {}
    correlations_by_plan: dict[str, list[Any]] = {}
    for corr in correlations:
        correlations_by_plan.setdefault(corr.plan_dir.name, []).append(corr)
    for plan in plans:
        plan_correlations = correlations_by_plan.get(plan.plan_id, [])
        terminal_env = (wbc_terminal_envelopes or {}).get(plan.plan_id)
        gap_env = (wbc_gap_envelopes or {}).get(plan.plan_id)
        heartbeat_fresh = (heartbeat_fresh_by_plan or {}).get(plan.plan_id)

        if plan_correlations:
            # Classify the first correlated process for this plan.
            corr = plan_correlations[0]
            proc = proc_by_pid.get(corr.process_pid)
            if proc is None:
                classification = {
                    "classification": LIVENESS_UNRELATED,
                    "runner_verdict": RUNNER_UNKNOWN,
                    "reason": "correlated process pid not found in scan results",
                    "authority": "evidence_extracted_non_authoritative",
                    "evidence_basis": [corr.method],
                    "evidence_gaps": {},
                }
            else:
                attempt_session = None
                attempt_start = None
                runner_lease = None
                identity_supplied = False
                if isinstance(terminal_env, Mapping):
                    identity_supplied = True
                    attempt_session = terminal_env.get("session") or terminal_env.get("session_token")
                    attempt_start = terminal_env.get("attempt_start_epoch") or terminal_env.get("started_at_epoch")
                if isinstance(gap_env, Mapping) and not identity_supplied:
                    identity_supplied = True
                    attempt_session = attempt_session or gap_env.get("session")
                verdict = classify_worker_liveness(
                    proc,
                    attempt_session_token=attempt_session,
                    attempt_start_epoch=attempt_start,
                    runner_lease_ref=runner_lease,
                    heartbeat_fresh=heartbeat_fresh,
                    wbc_attempt_identity_supplied=identity_supplied,
                    source_cursor_vector=source_cursor_vector,
                )
                classification = verdict.to_dict()
                classification["correlation_method"] = corr.method
        else:
            # No correlated process for this plan.
            classification = {
                "classification": LIVENESS_UNRELATED,
                "runner_verdict": RUNNER_UNKNOWN,
                "reason": "no worker process correlated to this plan",
                "authority": "evidence_extracted_non_authoritative",
                "evidence_basis": [],
                "evidence_gaps": _collect_snapshot_evidence_gaps(plan, None),
            }
        liveness_authority_map[plan.plan_id] = classification

    if max_age_hours is not None:
        max_age_seconds = max_age_hours * 3600
        filtered_plans: list[PlanEntry] = []
        for plan in plans:
            signals = signal_bundles[plan.plan_id]
            is_live = plan.plan_id in live_plan_ids
            recent = _plan_recency_age_seconds(Path(plan.plan_dir), signals) <= max_age_seconds
            if is_live or recent:
                filtered_plans.append(plan)
        plans = filtered_plans

    incidents = build_incidents(
        tuple(plans),
        signal_bundles,
        live_plan_ids,
        liveness_authority_map=liveness_authority_map,
    )

    liveness_summary = _format_liveness_authority_summary(liveness_authority_map)

    return Snapshot(
        scan_ts_utc=datetime.now(timezone.utc).isoformat(),
        plans=tuple(plans),
        incidents=tuple(incidents),
        source_cursor_vector=_format_source_cursor(source_cursor_vector),
        liveness_authority=liveness_summary,
    )


__all__ = [
    "build_incidents",
    "build_snapshot",
]
