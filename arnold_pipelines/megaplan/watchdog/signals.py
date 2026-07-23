"""Signal-bundle computation for each discovered plan.

Liveness computation distinguishes live workers from dead, hung, and recycled
processes.  Worker identity normalization (:mod:`worker_identity`) ensures
that recycled PIDs, unrelated processes, and stale heartbeats produce typed
stale or unknown liveness — never false-positive progress.

Heartbeat liveness is computed from exact worker identities and source
timestamps.  Missing or stale heartbeat facts return ``unknown`` or ``stale``
— never optimistic progress.  The heartbeat-based liveness is carried in
the signal bundle alongside event-based liveness.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Optional, Tuple

from arnold_pipelines.megaplan.pipelines.live_supervisor.model import (
    CheckFinding,
    SignalBundle,
)
from arnold_pipelines.megaplan.observability.liveness import has_active_in_flight_llm
from arnold_pipelines.megaplan.watchdog.worker_identity import (
    LivenessState,
    ProcessCorrelationSnapshot,
    WorkerCorrelation,
    WorkerIdentity,
    WorkerLiveness,
)


def _read_json(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _read_events(plan_dir: Path) -> list[dict]:
    events_file = plan_dir / "events.ndjson"
    if not events_file.is_file():
        return []
    events: list[dict] = []
    try:
        for line in events_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except Exception:
                continue
    except Exception:
        return []
    return events


def _parse_iso(ts: str) -> float | None:
    """Parse ISO-8601 timestamp to epoch seconds (best-effort)."""
    if not ts:
        return None
    try:
        from datetime import datetime

        # Strip trailing Z and try common formats.
        clean = ts.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean)
        return dt.timestamp()
    except Exception:
        return None


def _compute_last_event_age(events: list[dict], now_ts: float) -> float | None:
    last_ts: float | None = None
    for ev in events:
        ts = _parse_iso(ev.get("ts_utc", ""))
        if ts is not None:
            last_ts = ts
    if last_ts is None:
        return None
    return now_ts - last_ts


def _compute_in_flight_llm(
    events: list[dict], state: dict | None, now_ts: float
) -> bool:
    """True only for an unmatched recent LLM call owned by the active step."""
    return has_active_in_flight_llm(
        events, state, now_ts, parse_timestamp=_parse_iso
    )


def _compute_liveness_and_reason(events: list[dict], state: dict | None, now_ts: float) -> tuple[str, str]:
    """Best-effort event-based liveness computation matching the introspect semantics."""
    # Phase age / timeout-imminent
    phase_timeout = 3600.0
    phase_age: float | None = None
    if state and isinstance(state, dict):
        active = state.get("active_step")
        if isinstance(active, dict):
            started = active.get("started_at")
            if started:
                started_epoch = _parse_iso(str(started))
                if started_epoch is not None:
                    phase_age = now_ts - started_epoch
        phase_timeout = float(state.get("phase_timeout_seconds") or phase_timeout)

    if phase_age is not None and phase_age > 0.8 * phase_timeout:
        return "timeout-imminent", f"phase_age {phase_age:.0f}s > 0.8 * timeout {phase_timeout:.0f}s"

    last_event_age = _compute_last_event_age(events, now_ts)
    has_in_flight = _compute_in_flight_llm(events, state, now_ts)

    if last_event_age is None:
        if has_in_flight:
            return "progressing", "no events yet but LLM call in flight"
        return "quiet", "no events recorded yet"

    if last_event_age < 60 or has_in_flight:
        return "progressing", "recent event or LLM call in flight"
    if last_event_age < 300:
        return "quiet", f"last event {last_event_age:.0f}s ago"
    return "stalled", f"last event {last_event_age:.0f}s ago"


def compute_heartbeat_liveness(
    worker_correlations: Tuple[WorkerCorrelation, ...] = (),
    *,
    process_correlation_snapshot: ProcessCorrelationSnapshot | None = None,
    now_epoch_ms: Optional[float] = None,
    heartbeat_freshness_window_ms: int = 30_000,
) -> dict[str, Any]:
    """Compute heartbeat-based liveness from exact worker identities.

    Evaluates liveness for every correlated worker using exact identity tuples
    (host, pid, boot_id) and source heartbeat timestamps.  Missing or stale
    heartbeat facts produce typed ``unknown`` or ``stale`` — never optimistic
    progress.

    Args:
        worker_correlations: Correlated workers with identity and liveness.
        process_correlation_snapshot: Aggregate snapshot (alternative input).
        now_epoch_ms: Current time for age calculations.
        heartbeat_freshness_window_ms: Max heartbeat age for recent (default 30s).

    Returns:
        Dict with:
        - ``heartbeat_liveness``: Aggregated state (``live``, ``stale``, ``unknown``, ``hung``, ``dead``).
        - ``heartbeat_liveness_reason``: Diagnostic detail.
        - ``worker_states``: Per-worker liveness detail list.
        - ``live_worker_count``, ``stale_worker_count``, ``dead_worker_count``.
        - ``_non_authoritative``: Always True.
    """
    now = now_epoch_ms or (time.time() * 1000)

    # Resolve worker correlations from snapshot if provided
    if process_correlation_snapshot is not None and not worker_correlations:
        worker_correlations = process_correlation_snapshot.correlations

    if not worker_correlations:
        return {
            "heartbeat_liveness": "unknown",
            "heartbeat_liveness_reason": "no worker correlations available; heartbeat liveness is unknown",
            "worker_states": [],
            "live_worker_count": 0,
            "stale_worker_count": 0,
            "dead_worker_count": 0,
            "_non_authoritative": True,
        }

    worker_states: list[dict[str, Any]] = []
    live_count = 0
    stale_count = 0
    dead_count = 0

    for wc in worker_correlations:
        identity = wc.identity
        liveness = wc.liveness

        worker_state = {
            "correlation_key": identity.correlation_key,
            "state": liveness.state.value,
            "cursor_state": liveness.cursor_state,
            "is_pid_live": liveness.is_pid_live,
            "has_recent_heartbeat": liveness.has_recent_heartbeat,
            "heartbeat_age_ms": liveness.heartbeat_age_ms,
            "identity_digest": f"sha256:{identity.identity_digest}",
            "plan_dirs": list(wc.plan_dirs),
            "detail": liveness.detail,
        }
        worker_states.append(worker_state)

        if liveness.state == LivenessState.LIVE:
            live_count += 1
        elif liveness.state in (LivenessState.STALE, LivenessState.HUNG, LivenessState.RECYCLED):
            stale_count += 1
        elif liveness.state == LivenessState.DEAD:
            dead_count += 1

    # Aggregate heartbeat liveness state
    if live_count > 0:
        aggregate_state = "live"
        if stale_count > 0 or dead_count > 0:
            reason = (
                f"{live_count} live worker(s), "
                f"{stale_count} stale/hung/recycled, {dead_count} dead"
            )
        else:
            reason = f"{live_count} live worker(s) with recent heartbeats"
    elif stale_count > 0:
        aggregate_state = "stale"
        reason = (
            f"no live workers; {stale_count} stale/hung/recycled, {dead_count} dead"
        )
    elif dead_count > 0:
        aggregate_state = "dead"
        reason = f"no live workers; {dead_count} dead (pid not live)"
    else:
        aggregate_state = "unknown"
        reason = "no workers with determinable liveness"

    return {
        "heartbeat_liveness": aggregate_state,
        "heartbeat_liveness_reason": reason,
        "worker_states": worker_states,
        "live_worker_count": live_count,
        "stale_worker_count": stale_count,
        "dead_worker_count": dead_count,
        "_non_authoritative": True,
    }


def _compute_block_details(plan_dir: Path, state: dict | None) -> dict[str, Any]:
    """Best-effort block details."""
    result: dict[str, Any] = {"is_blocked": False, "current_state": None, "recoverable_via": None}
    if state is None:
        return result
    current_state = state.get("current_state")
    result["current_state"] = current_state

    if not isinstance(current_state, str):
        return result

    # Count unresolved flags from gate_signals files.
    flags_count = 0
    try:
        for path_obj in sorted(plan_dir.glob("gate_signals_v*.json"), reverse=True):
            try:
                data = json.loads(path_obj.read_text(encoding="utf-8"))
                flags = data.get("unresolved_flags", [])
                if isinstance(flags, list):
                    flags_count = len(flags)
                break
            except Exception:
                continue
    except Exception:
        pass

    is_blocked = flags_count > 0 or current_state in {"gated", "clarifying", "blocked"}
    result["is_blocked"] = is_blocked

    if is_blocked and current_state in {"gated", "clarifying", "blocked"}:
        result["recoverable_via"] = ["resume", "auto"]
    return result


def _doctor_findings(plan_dir: Path, state: dict | None) -> tuple[CheckFinding, ...]:
    """Lightweight doctor checks that do not require the megaplan CLI."""
    findings: list[CheckFinding] = []

    # Stale lock check.
    lock_file = plan_dir / ".plan.lock"
    if lock_file.exists():
        try:
            mtime = lock_file.stat().st_mtime
            age = time.time() - mtime
            if age > 300:
                findings.append(
                    CheckFinding(
                        scope="plan",
                        check="stale_lock",
                        status="fail",
                        message=f"plan lock is {age:.0f}s old",
                    )
                )
        except Exception:
            pass

    return tuple(findings)


def evaluate_worker_liveness(
    pid: int,
    *,
    is_pid_live: bool | None = None,
    heartbeat_epoch_ms: float | None = None,
    worker_type: str = "",
    cmdline: str = "",
    cwd: str = "",
    now_epoch_ms: float | None = None,
) -> WorkerLiveness:
    """Evaluate liveness for a worker process.

    Returns a typed :class:`WorkerLiveness` that distinguishes live, dead,
    hung, and recycled workers.  A live PID without heartbeat evidence is
    ``HUNG``, not ``LIVE`` — consumers must provide heartbeat evidence for
    positive liveness.
    """
    identity = WorkerIdentity.from_process_record(
        pid=pid,
        worker_type=worker_type,
        cmdline=cmdline,
        cwd=cwd,
    )
    if heartbeat_epoch_ms is not None:
        identity = identity.with_heartbeat(1, epoch_ms=heartbeat_epoch_ms)
    return WorkerLiveness.evaluate(
        identity,
        is_pid_live=is_pid_live,
        now_epoch_ms=now_epoch_ms,
    )


def compute_signal_bundle(
    plan_dir: Path,
    state: dict | None = None,
    *,
    # ── M9: heartbeat-liveness inputs ──
    worker_correlations: Tuple[WorkerCorrelation, ...] = (),
    process_correlation_snapshot: ProcessCorrelationSnapshot | None = None,
) -> SignalBundle:
    """Build a SignalBundle for a plan directory.

    Uses direct filesystem reads so it works even when the megaplan CLI is
    broken or shadowed. Degrades gracefully on any error.

    When worker correlations are provided, heartbeat-based liveness is
    computed from exact worker identities and source timestamps.  Missing
    or stale heartbeat facts produce typed ``unknown`` or ``stale`` —
    never optimistic progress.
    """
    plan_dir = Path(plan_dir)
    if state is None:
        state = _read_json(plan_dir / "state.json")

    try:
        events = _read_events(plan_dir)
        now_ts = time.time()
        liveness, liveness_reason = _compute_liveness_and_reason(events, state, now_ts)
        last_event_age_seconds = _compute_last_event_age(events, now_ts)
        has_in_flight_llm = _compute_in_flight_llm(events, state, now_ts)
        block_details = _compute_block_details(plan_dir, state)
        doctor_findings = _doctor_findings(plan_dir, state)

        # ── M9: heartbeat-based liveness from exact identities ──
        heartbeat_data = compute_heartbeat_liveness(
            worker_correlations=worker_correlations,
            process_correlation_snapshot=process_correlation_snapshot,
            now_epoch_ms=now_ts * 1000,
        )

        return SignalBundle(
            liveness=liveness,
            liveness_reason=liveness_reason,
            block_details=block_details,
            doctor_findings=doctor_findings,
            has_in_flight_llm=has_in_flight_llm,
            last_event_age_seconds=last_event_age_seconds,
            heartbeat_liveness=heartbeat_data.get("heartbeat_liveness", "unknown"),
            heartbeat_liveness_reason=heartbeat_data.get("heartbeat_liveness_reason", ""),
            worker_states=heartbeat_data.get("worker_states", []),
            live_worker_count=heartbeat_data.get("live_worker_count", 0),
            stale_worker_count=heartbeat_data.get("stale_worker_count", 0),
            dead_worker_count=heartbeat_data.get("dead_worker_count", 0),
        )
    except Exception as exc:
        return SignalBundle(
            liveness="unknown",
            liveness_reason="signal computation failed",
            block_details={},
            doctor_findings=(),
            degraded=True,
            failure_reason=str(exc),
        )


__all__ = [
    "compute_signal_bundle",
    "compute_heartbeat_liveness",
    "evaluate_worker_liveness",
]
