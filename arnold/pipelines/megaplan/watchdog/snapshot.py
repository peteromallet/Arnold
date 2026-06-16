"""Snapshot construction for the live watchdog."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from arnold.pipelines.megaplan.pipelines.live_supervisor.model import (
    CheckFinding,
    Incident,
    PlanEntry,
    SignalBundle,
    Snapshot,
    Triage,
)
from arnold.pipelines.megaplan.watchdog.correlate import (
    _path_contains,
    correlate_processes_to_plans,
    infer_plan_dirs_from_processes,
)
from arnold.pipelines.megaplan.watchdog.discovery import discover_plans, read_plan_state
from arnold.pipelines.megaplan.watchdog.log import log_event
from arnold.pipelines.megaplan.watchdog.orphans import find_orphan_processes
from arnold.pipelines.megaplan.watchdog.processes import scan_processes
from arnold.pipelines.megaplan.watchdog.signals import compute_signal_bundle


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
