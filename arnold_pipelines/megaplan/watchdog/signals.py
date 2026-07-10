"""Signal-bundle computation for each discovered plan."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from arnold_pipelines.megaplan.pipelines.live_supervisor.model import (
    CheckFinding,
    SignalBundle,
)
from arnold_pipelines.megaplan.observability.liveness import has_active_in_flight_llm


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
    """Best-effort liveness computation matching the introspect semantics."""
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


def compute_signal_bundle(plan_dir: Path, state: dict | None = None) -> SignalBundle:
    """Build a SignalBundle for a plan directory.

    Uses direct filesystem reads so it works even when the megaplan CLI is
    broken or shadowed. Degrades gracefully on any error.
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

        return SignalBundle(
            liveness=liveness,
            liveness_reason=liveness_reason,
            block_details=block_details,
            doctor_findings=doctor_findings,
            has_in_flight_llm=has_in_flight_llm,
            last_event_age_seconds=last_event_age_seconds,
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
]
