"""Snapshot construction for the live watchdog.

Snapshot building uses normalized worker identity to ensure that recycled,
unrelated, dead, and hung workers produce typed stale or unknown liveness
only — never false-positive progress.  The process-correlation dimension
in the source-cursor vector reflects exact worker identity.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from arnold_pipelines.megaplan.pipelines.live_supervisor.model import (
    CheckFinding,
    Incident,
    PlanEntry,
    SignalBundle,
    Snapshot,
    Triage,
)
from arnold_pipelines.megaplan.watchdog.correlate import (
    _path_contains,
    correlate_processes_to_plans,
    infer_plan_dirs_from_processes,
)
from arnold_pipelines.megaplan.watchdog.discovery import discover_plans, read_plan_state
from arnold_pipelines.megaplan.watchdog.log import log_event
from arnold_pipelines.megaplan.watchdog.orphans import find_orphan_processes
from arnold_pipelines.megaplan.watchdog.processes import scan_processes
from arnold_pipelines.megaplan.watchdog.signals import compute_signal_bundle
from arnold_pipelines.megaplan.watchdog.worker_identity import (
    LivenessState,
    ProcessCorrelationSnapshot,
    WorkerCorrelation,
)


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


def build_process_correlation_snapshot(
    correlations: tuple[Any, ...],
    processes: tuple[Any, ...],
) -> ProcessCorrelationSnapshot:
    """Build a typed process-correlation snapshot from watchdog data.

    Converts raw Correlation and ProcessRecord tuples into a
    :class:`ProcessCorrelationSnapshot` that the source-cursor vector's
    ``process_correlation`` dimension can consume.  Recycled, dead, hung,
    and unrelated workers produce ``stale`` or ``unknown`` cursor state.
    """
    worker_corrs: list[WorkerCorrelation] = []
    seen_pids: set[int] = set()

    # Build a lookup from pid to process record
    proc_by_pid: dict[int, Any] = {}
    for proc in processes:
        pid = int(getattr(proc, "pid", 0) or (proc.get("pid", 0) if isinstance(proc, dict) else 0))
        if pid:
            proc_by_pid[pid] = proc

    for corr in correlations:
        pid = corr.process_pid
        if pid in seen_pids:
            continue
        seen_pids.add(pid)

        proc = proc_by_pid.get(pid)
        if proc is not None:
            if isinstance(proc, dict):
                is_pid_live = proc.get("is_live", None)
                worker_type = proc.get("category", "")
                cmdline = proc.get("cmdline", "")
                cwd = proc.get("cwd", "")
            else:
                is_pid_live = getattr(proc, "is_live", None)
                worker_type = getattr(proc, "category", "")
                cmdline = getattr(proc, "cmdline", "")
                cwd = getattr(proc, "cwd", "")
        else:
            is_pid_live = None
            worker_type = ""
            cmdline = ""
            cwd = ""

        wc = corr.to_worker_correlation(
            is_pid_live=is_pid_live,
            worker_type=worker_type,
            cmdline=cmdline,
            cwd=cwd or "",
        )
        worker_corrs.append(wc)

    return ProcessCorrelationSnapshot(correlations=tuple(worker_corrs))


def build_incidents(
    plans: tuple[PlanEntry, ...],
    signal_bundles: dict[str, SignalBundle],
    live_plan_ids: set[str],
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
        incidents.append(Incident(plan_entry=plan, signals=signals, triage=triage))
    return tuple(incidents)


def build_snapshot(
    roots: tuple[str, ...] | None = None,
    *,
    max_age_hours: float | None = None,
    process_scanner: Any | None = None,
    logger: logging.Logger | None = None,
) -> Snapshot:
    """Discover plans and build a Snapshot with signal bundles and triage.

    Uses direct filesystem/process access only; does not require a working
    ``megaplan`` CLI.

    When ``max_age_hours`` is set, plans are only included if they have a live
    process or some recent activity (state mtime or event mtime/age) within the
    window. ``None`` means no age filter.
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

    # ── M9: build process-correlation snapshot for heartbeat liveness ──
    process_correlation_snapshot = build_process_correlation_snapshot(
        correlations, processes
    )
    # Map plan_dir -> correlated workers for that plan
    workers_by_plan_dir: dict[str, list[Any]] = {}
    for wc in process_correlation_snapshot.correlations:
        for plan_dir in wc.plan_dirs:
            workers_by_plan_dir.setdefault(plan_dir, []).append(wc)

    signal_bundles: dict[str, SignalBundle] = {}
    for plan in plans:
        plan_path = Path(plan.plan_dir)
        plan_workers = tuple(workers_by_plan_dir.get(str(plan_path.resolve()), ()))
        signals = compute_signal_bundle(
            plan_path,
            plan.state,
            worker_correlations=plan_workers,
            process_correlation_snapshot=process_correlation_snapshot,
        )
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
                heartbeat_liveness=signals.heartbeat_liveness,
                heartbeat_liveness_reason=signals.heartbeat_liveness_reason,
                worker_states=signals.worker_states,
                live_worker_count=signals.live_worker_count,
                stale_worker_count=signals.stale_worker_count,
                dead_worker_count=signals.dead_worker_count,
            )
        elif orphan_findings:
            signals = SignalBundle(
                liveness=signals.liveness,
                liveness_reason=signals.liveness_reason,
                block_details=signals.block_details,
                doctor_findings=signals.doctor_findings + tuple(orphan_findings),
                has_in_flight_llm=signals.has_in_flight_llm,
                last_event_age_seconds=signals.last_event_age_seconds,
                heartbeat_liveness=signals.heartbeat_liveness,
                heartbeat_liveness_reason=signals.heartbeat_liveness_reason,
                worker_states=signals.worker_states,
                live_worker_count=signals.live_worker_count,
                stale_worker_count=signals.stale_worker_count,
                dead_worker_count=signals.dead_worker_count,
            )
        signal_bundles[plan.plan_id] = signals

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

    incidents = build_incidents(tuple(plans), signal_bundles, live_plan_ids)

    return Snapshot(
        scan_ts_utc=datetime.now(timezone.utc).isoformat(),
        plans=tuple(plans),
        incidents=tuple(incidents),
    )


__all__ = [
    "build_incidents",
    "build_snapshot",
]
