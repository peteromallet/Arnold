"""Centralized per-phase runtime policy for patience, polling, and timeouts."""

from __future__ import annotations

import hashlib
import json
import os
import socket
import subprocess
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


WORKER_LIVE = "live"
WORKER_DEAD = "dead"
WORKER_UNKNOWN = "unknown"


@dataclass(frozen=True)
class WorkerLivenessObservation:
    state: str
    reason: str
    evidence: dict[str, Any]


def _pid_namespace_id(pid: int | str = "self") -> str:
    try:
        return os.readlink(f"/proc/{pid}/ns/pid")
    except OSError:
        return "unknown"


def _process_start_identity(pid: int) -> str | None:
    try:
        raw = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
        start_ticks = raw.rsplit(")", 1)[1].strip().split()[19]
        boot_id = Path("/proc/sys/kernel/random/boot_id").read_text(
            encoding="utf-8"
        ).strip()
        return f"{boot_id}:{start_ticks}"
    except (OSError, IndexError):
        try:
            os.kill(pid, 0)
            result = subprocess.run(
                ["ps", "-o", "lstart=", "-p", str(pid)],
                check=False,
                capture_output=True,
                text=True,
                timeout=2,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        started = result.stdout.strip()
        if result.returncode != 0 or not started:
            return None
        host = socket.gethostname()
        return f"portable-{hashlib.sha256(host.encode()).hexdigest()[:16]}:{started}"


def current_runner_incarnation(*, pid: int | None = None) -> dict[str, Any]:
    """Return the local process identity needed to disambiguate PID reuse."""

    worker_pid = int(pid or os.getpid())
    return {
        "schema": "arnold.megaplan.runner_incarnation.v1",
        "host_id": socket.gethostname(),
        "pid_namespace_id": _pid_namespace_id(),
        "worker_pid": worker_pid,
        "worker_process_start_identity": _process_start_identity(worker_pid),
    }


def current_runner_lease_binding() -> dict[str, Any] | None:
    """Capture the immutable identity of the runner-owned shared lease."""

    session = str(os.environ.get("ARNOLD_REPAIR_SESSION") or "").strip()
    if not session:
        return None
    marker_dir = Path(
        os.environ.get("ARNOLD_REPAIR_MARKER_DIR")
        or "/workspace/.megaplan/cloud-sessions"
    )
    try:
        from arnold_pipelines.megaplan.cloud.liveness_lease import (
            lease_path,
            marker_binding,
            observe_liveness_lease,
        )

        marker = json.loads((marker_dir / f"{session}.json").read_text(encoding="utf-8"))
        raw = json.loads(lease_path(session, marker_dir=marker_dir).read_text(encoding="utf-8"))
        observed = observe_liveness_lease(marker, marker_dir=marker_dir)
    except (OSError, ValueError, TypeError):
        return None
    if not isinstance(marker, Mapping) or not isinstance(raw, Mapping):
        return None
    if observed.get("state") != "live":
        return None
    return {
        "schema": "arnold.megaplan.active_step_runner_lease.v1",
        "session": session,
        "marker_dir": str(marker_dir.resolve()),
        "marker_binding": marker_binding(marker),
        "lease_id": raw.get("lease_id"),
        "runner_fence": raw.get("runner_fence"),
        "runner_container_id": raw.get("runner_container_id"),
        "pid_namespace_id": raw.get("pid_namespace_id"),
        "target_process_start_identity": raw.get("target_process_start_identity"),
    }


def active_step_cas_token(active_step: Mapping[str, Any]) -> str:
    """Content identity used to compare-and-swap one exact active occurrence."""

    encoded = json.dumps(
        dict(active_step), sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _observe_bound_lease(
    binding: Mapping[str, Any],
    *,
    now: datetime | None = None,
) -> WorkerLivenessObservation:
    session = str(binding.get("session") or "")
    marker_dir_raw = binding.get("marker_dir")
    if not session or not isinstance(marker_dir_raw, str):
        return WorkerLivenessObservation(WORKER_UNKNOWN, "runner lease binding incomplete", {})
    marker_dir = Path(marker_dir_raw)
    try:
        from arnold_pipelines.megaplan.cloud.liveness_lease import observe_liveness_lease

        marker = json.loads((marker_dir / f"{session}.json").read_text(encoding="utf-8"))
        observed = observe_liveness_lease(marker, marker_dir=marker_dir, now=now)
    except (OSError, ValueError, TypeError):
        return WorkerLivenessObservation(WORKER_UNKNOWN, "bound runner lease unreadable", {})
    if not isinstance(observed, Mapping):
        return WorkerLivenessObservation(WORKER_UNKNOWN, "bound runner lease invalid", {})
    observed_lease_id = observed.get("lease_id")
    expected_lease_id = binding.get("lease_id")
    if observed_lease_id is not None and observed_lease_id != expected_lease_id:
        return WorkerLivenessObservation(
            WORKER_DEAD,
            "runner lease was replaced by a different fenced incarnation",
            dict(observed),
        )
    state = str(observed.get("state") or "unknown")
    expected_fence = binding.get("runner_fence")
    observed_fence = observed.get("runner_fence")
    if state == "fenced" or (
        observed_fence is not None
        and expected_fence is not None
        and observed_fence != expected_fence
    ):
        return WorkerLivenessObservation(
            WORKER_DEAD,
            "runner fence generation was replaced",
            dict(observed),
        )
    if state == "live" and observed_lease_id == expected_lease_id:
        return WorkerLivenessObservation(
            WORKER_LIVE, "fresh exact runner lease", dict(observed)
        )
    if state in {"expired", "stopped"} and observed_lease_id == expected_lease_id:
        return WorkerLivenessObservation(
            WORKER_DEAD, "exact runner lease expired or stopped", dict(observed)
        )
    return WorkerLivenessObservation(
        WORKER_UNKNOWN,
        f"runner lease cannot prove death ({state})",
        dict(observed),
    )


def observe_active_step_worker(
    active_step: Any,
    *,
    now: datetime | None = None,
) -> WorkerLivenessObservation:
    """Classify one active occurrence without treating a foreign PID miss as death."""

    if not isinstance(active_step, Mapping):
        return WorkerLivenessObservation(WORKER_UNKNOWN, "active step missing", {})
    incarnation = active_step.get("runner_incarnation")
    if not isinstance(incarnation, Mapping):
        raw_legacy_pid = active_step.get("worker_pid", active_step.get("pid"))
        try:
            legacy_pid = int(raw_legacy_pid)
        except (TypeError, ValueError):
            legacy_pid = -1
        if legacy_pid == os.getpid() and _pid_alive(legacy_pid):
            return WorkerLivenessObservation(
                WORKER_LIVE,
                "legacy active step names the observing process itself",
                {"pid": legacy_pid, "legacy": True},
            )
        return WorkerLivenessObservation(
            WORKER_UNKNOWN, "active step has no runner incarnation binding", {}
        )
    raw_pid = active_step.get("worker_pid", incarnation.get("worker_pid"))
    try:
        pid = int(raw_pid)
    except (TypeError, ValueError):
        return WorkerLivenessObservation(WORKER_UNKNOWN, "worker pid invalid", {})
    recorded_namespace = str(incarnation.get("pid_namespace_id") or "unknown")
    recorded_host = str(incarnation.get("host_id") or "")
    local_namespace = _pid_namespace_id()
    local_host = socket.gethostname()
    same_incarnation_domain = (
        recorded_host == local_host
        and (
            (recorded_namespace != "unknown" and recorded_namespace == local_namespace)
            or pid == os.getpid()
        )
    )
    if same_incarnation_domain:
        if not _pid_alive(pid):
            return WorkerLivenessObservation(
                WORKER_DEAD, "worker absent in its owning PID namespace", {"pid": pid}
            )
        expected_start = incarnation.get("worker_process_start_identity")
        observed_start = _process_start_identity(pid)
        if not expected_start or not observed_start:
            return WorkerLivenessObservation(
                WORKER_UNKNOWN, "worker process incarnation cannot be verified", {"pid": pid}
            )
        if observed_start != expected_start:
            return WorkerLivenessObservation(
                WORKER_DEAD, "worker PID was reused by a different process", {"pid": pid}
            )
        return WorkerLivenessObservation(
            WORKER_LIVE, "exact local worker process incarnation is alive", {"pid": pid}
        )
    lease_binding = active_step.get("runner_lease")
    if isinstance(lease_binding, Mapping):
        return _observe_bound_lease(lease_binding, now=now)
    return WorkerLivenessObservation(
        WORKER_UNKNOWN,
        "worker PID belongs to a foreign or unknown namespace and no bound lease exists",
        {"pid": pid, "recorded_namespace": recorded_namespace, "local_namespace": local_namespace},
    )


def _pid_alive(pid: int) -> bool:
    """Return True iff the given pid corresponds to a running process.

    Uses signal-0 probe; treats PermissionError as alive (process exists,
    owned by someone else). Returns False for non-positive pids.
    """
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False


def active_step_has_live_worker(active_step: Any) -> bool:
    """Return whether an active-step record names a currently live worker.

    Phase names and resumable model ``session_id`` values are not liveness.
    Local workers require an exact process incarnation; foreign workers require
    their exact fresh runner lease. UNKNOWN is not reported as live.
    """

    return observe_active_step_worker(active_step).state == WORKER_LIVE


# 2026-08-25: raised 900 -> 7200. The 900s cap predates frontier-model plan
# phases (Ox Alpha crosswalk deliverables run 15-90 min); the flash-era cap
# TERMed every non-execute phase at exactly +15 min. Aligned with
# worker_timeout_seconds (7200).
DEFAULT_NON_EXECUTE_TIMEOUT_CAP_SECONDS = 7200


@dataclass(frozen=True)
class PhaseRuntimePolicy:
    expected_min_seconds: int
    expected_max_seconds: int | None
    recommended_next_check_seconds: int
    escalation_threshold_seconds: int | None
    timeout_cap_seconds: int | None
    artifact_mode: str = "completion_only"


@dataclass(frozen=True)
class ResolvedPhaseRuntime:
    expected_duration_seconds: dict[str, int]
    recommended_next_check_seconds: int
    escalation_threshold_seconds: int
    timeout_budget_seconds: int
    artifact_mode: str


PHASE_RUNTIME_POLICY: dict[str, PhaseRuntimePolicy] = {
    "prep": PhaseRuntimePolicy(
        expected_min_seconds=30,
        expected_max_seconds=DEFAULT_NON_EXECUTE_TIMEOUT_CAP_SECONDS,
        recommended_next_check_seconds=60,
        escalation_threshold_seconds=DEFAULT_NON_EXECUTE_TIMEOUT_CAP_SECONDS,
        timeout_cap_seconds=DEFAULT_NON_EXECUTE_TIMEOUT_CAP_SECONDS,
    ),
    "prep-triage": PhaseRuntimePolicy(
        expected_min_seconds=30,
        expected_max_seconds=DEFAULT_NON_EXECUTE_TIMEOUT_CAP_SECONDS,
        recommended_next_check_seconds=60,
        escalation_threshold_seconds=DEFAULT_NON_EXECUTE_TIMEOUT_CAP_SECONDS,
        timeout_cap_seconds=DEFAULT_NON_EXECUTE_TIMEOUT_CAP_SECONDS,
    ),
    "prep-research": PhaseRuntimePolicy(
        expected_min_seconds=60,
        expected_max_seconds=DEFAULT_NON_EXECUTE_TIMEOUT_CAP_SECONDS,
        recommended_next_check_seconds=120,
        escalation_threshold_seconds=DEFAULT_NON_EXECUTE_TIMEOUT_CAP_SECONDS,
        timeout_cap_seconds=DEFAULT_NON_EXECUTE_TIMEOUT_CAP_SECONDS,
    ),
    "prep-distill": PhaseRuntimePolicy(
        expected_min_seconds=30,
        expected_max_seconds=DEFAULT_NON_EXECUTE_TIMEOUT_CAP_SECONDS,
        recommended_next_check_seconds=60,
        escalation_threshold_seconds=DEFAULT_NON_EXECUTE_TIMEOUT_CAP_SECONDS,
        timeout_cap_seconds=DEFAULT_NON_EXECUTE_TIMEOUT_CAP_SECONDS,
    ),
    "plan": PhaseRuntimePolicy(
        expected_min_seconds=60,
        expected_max_seconds=DEFAULT_NON_EXECUTE_TIMEOUT_CAP_SECONDS,
        recommended_next_check_seconds=120,
        escalation_threshold_seconds=DEFAULT_NON_EXECUTE_TIMEOUT_CAP_SECONDS,
        timeout_cap_seconds=DEFAULT_NON_EXECUTE_TIMEOUT_CAP_SECONDS,
    ),
    "critique": PhaseRuntimePolicy(
        expected_min_seconds=60,
        expected_max_seconds=DEFAULT_NON_EXECUTE_TIMEOUT_CAP_SECONDS,
        recommended_next_check_seconds=120,
        escalation_threshold_seconds=DEFAULT_NON_EXECUTE_TIMEOUT_CAP_SECONDS,
        timeout_cap_seconds=DEFAULT_NON_EXECUTE_TIMEOUT_CAP_SECONDS,
    ),
    "critique_evaluator": PhaseRuntimePolicy(
        expected_min_seconds=30,
        expected_max_seconds=DEFAULT_NON_EXECUTE_TIMEOUT_CAP_SECONDS,
        recommended_next_check_seconds=60,
        escalation_threshold_seconds=DEFAULT_NON_EXECUTE_TIMEOUT_CAP_SECONDS,
        timeout_cap_seconds=DEFAULT_NON_EXECUTE_TIMEOUT_CAP_SECONDS,
    ),
    "revise": PhaseRuntimePolicy(
        expected_min_seconds=60,
        expected_max_seconds=DEFAULT_NON_EXECUTE_TIMEOUT_CAP_SECONDS,
        recommended_next_check_seconds=120,
        escalation_threshold_seconds=DEFAULT_NON_EXECUTE_TIMEOUT_CAP_SECONDS,
        timeout_cap_seconds=DEFAULT_NON_EXECUTE_TIMEOUT_CAP_SECONDS,
    ),
    "gate": PhaseRuntimePolicy(
        expected_min_seconds=30,
        expected_max_seconds=DEFAULT_NON_EXECUTE_TIMEOUT_CAP_SECONDS,
        recommended_next_check_seconds=60,
        escalation_threshold_seconds=DEFAULT_NON_EXECUTE_TIMEOUT_CAP_SECONDS,
        timeout_cap_seconds=DEFAULT_NON_EXECUTE_TIMEOUT_CAP_SECONDS,
    ),
    "finalize": PhaseRuntimePolicy(
        expected_min_seconds=60,
        expected_max_seconds=DEFAULT_NON_EXECUTE_TIMEOUT_CAP_SECONDS,
        recommended_next_check_seconds=120,
        escalation_threshold_seconds=DEFAULT_NON_EXECUTE_TIMEOUT_CAP_SECONDS,
        timeout_cap_seconds=DEFAULT_NON_EXECUTE_TIMEOUT_CAP_SECONDS,
    ),
    "execute": PhaseRuntimePolicy(
        expected_min_seconds=300,
        expected_max_seconds=None,
        recommended_next_check_seconds=300,
        escalation_threshold_seconds=None,
        timeout_cap_seconds=None,
    ),
    "feedback": PhaseRuntimePolicy(
        expected_min_seconds=30,
        expected_max_seconds=DEFAULT_NON_EXECUTE_TIMEOUT_CAP_SECONDS,
        recommended_next_check_seconds=60,
        escalation_threshold_seconds=DEFAULT_NON_EXECUTE_TIMEOUT_CAP_SECONDS,
        timeout_cap_seconds=DEFAULT_NON_EXECUTE_TIMEOUT_CAP_SECONDS,
    ),
    "review": PhaseRuntimePolicy(
        expected_min_seconds=60,
        expected_max_seconds=DEFAULT_NON_EXECUTE_TIMEOUT_CAP_SECONDS,
        recommended_next_check_seconds=120,
        escalation_threshold_seconds=DEFAULT_NON_EXECUTE_TIMEOUT_CAP_SECONDS,
        timeout_cap_seconds=DEFAULT_NON_EXECUTE_TIMEOUT_CAP_SECONDS,
    ),
    "loop_plan": PhaseRuntimePolicy(
        expected_min_seconds=60,
        expected_max_seconds=DEFAULT_NON_EXECUTE_TIMEOUT_CAP_SECONDS,
        recommended_next_check_seconds=120,
        escalation_threshold_seconds=DEFAULT_NON_EXECUTE_TIMEOUT_CAP_SECONDS,
        timeout_cap_seconds=DEFAULT_NON_EXECUTE_TIMEOUT_CAP_SECONDS,
    ),
    "loop_execute": PhaseRuntimePolicy(
        expected_min_seconds=300,
        expected_max_seconds=None,
        recommended_next_check_seconds=300,
        escalation_threshold_seconds=None,
        timeout_cap_seconds=None,
    ),
    "tiebreaker_researcher": PhaseRuntimePolicy(
        expected_min_seconds=60,
        expected_max_seconds=DEFAULT_NON_EXECUTE_TIMEOUT_CAP_SECONDS,
        recommended_next_check_seconds=120,
        escalation_threshold_seconds=DEFAULT_NON_EXECUTE_TIMEOUT_CAP_SECONDS,
        timeout_cap_seconds=DEFAULT_NON_EXECUTE_TIMEOUT_CAP_SECONDS,
    ),
    "tiebreaker_challenger": PhaseRuntimePolicy(
        expected_min_seconds=60,
        expected_max_seconds=DEFAULT_NON_EXECUTE_TIMEOUT_CAP_SECONDS,
        recommended_next_check_seconds=120,
        escalation_threshold_seconds=DEFAULT_NON_EXECUTE_TIMEOUT_CAP_SECONDS,
        timeout_cap_seconds=DEFAULT_NON_EXECUTE_TIMEOUT_CAP_SECONDS,
    ),
}


def phase_runtime_policy(step: str) -> PhaseRuntimePolicy:
    try:
        return PHASE_RUNTIME_POLICY[step]
    except KeyError as exc:
        raise KeyError(f"Unknown phase runtime step: {step}") from exc


def humanize_seconds(seconds: int) -> str:
    total_seconds = max(0, int(seconds))
    if total_seconds < 60:
        return f"{total_seconds}s"
    minutes, remainder = divmod(total_seconds, 60)
    if total_seconds < 3600:
        if remainder == 0:
            return f"{minutes}m"
        return f"{minutes}m {remainder}s"
    hours, minutes = divmod(minutes, 60)
    if minutes == 0:
        return f"{hours}h"
    return f"{hours}h {minutes}m"


def resolve_phase_runtime(step: str, *, configured_timeout_seconds: int) -> ResolvedPhaseRuntime:
    policy = phase_runtime_policy(step)
    timeout_budget_seconds = configured_timeout_seconds
    if policy.timeout_cap_seconds is not None:
        timeout_budget_seconds = min(timeout_budget_seconds, policy.timeout_cap_seconds)
    expected_max_seconds = timeout_budget_seconds
    if policy.expected_max_seconds is not None:
        expected_max_seconds = min(expected_max_seconds, policy.expected_max_seconds)
    escalation_threshold_seconds = timeout_budget_seconds
    if policy.escalation_threshold_seconds is not None:
        escalation_threshold_seconds = min(
            escalation_threshold_seconds,
            policy.escalation_threshold_seconds,
        )
    return ResolvedPhaseRuntime(
        expected_duration_seconds={
            "min": policy.expected_min_seconds,
            "max": max(policy.expected_min_seconds, expected_max_seconds),
        },
        recommended_next_check_seconds=policy.recommended_next_check_seconds,
        escalation_threshold_seconds=max(policy.expected_min_seconds, escalation_threshold_seconds),
        timeout_budget_seconds=max(policy.expected_min_seconds, timeout_budget_seconds),
        artifact_mode=policy.artifact_mode,
    )


def format_duration_hint(step: str, *, configured_timeout_seconds: int) -> str:
    policy = phase_runtime_policy(step)
    resolved = resolve_phase_runtime(step, configured_timeout_seconds=configured_timeout_seconds)
    if policy.expected_max_seconds is None:
        return (
            f"Expected minimum duration: {humanize_seconds(policy.expected_min_seconds)} "
            "(depends on task count)."
        )
    return (
        "Expected duration: "
        f"{humanize_seconds(resolved.expected_duration_seconds['min'])}-"
        f"{humanize_seconds(resolved.expected_duration_seconds['max'])}."
    )


def build_next_step_runtime(
    step: Any,
    *,
    configured_timeout_seconds: int,
) -> dict[str, Any] | None:
    if not isinstance(step, str) or step not in PHASE_RUNTIME_POLICY:
        return None
    resolved = resolve_phase_runtime(step, configured_timeout_seconds=configured_timeout_seconds)
    return {
        "expected_duration_seconds": resolved.expected_duration_seconds,
        "recommended_next_check_seconds": resolved.recommended_next_check_seconds,
        "duration_hint": format_duration_hint(
            step,
            configured_timeout_seconds=configured_timeout_seconds,
        ),
    }


def phase_timeout_seconds(step: str, *, configured_timeout_seconds: int) -> int:
    return resolve_phase_runtime(
        step,
        configured_timeout_seconds=configured_timeout_seconds,
    ).timeout_budget_seconds


def phase_stale_seconds(step: str, *, configured_timeout_seconds: int) -> int:
    return resolve_phase_runtime(
        step,
        configured_timeout_seconds=configured_timeout_seconds,
    ).escalation_threshold_seconds


def build_phase_observability(
    step: str,
    *,
    configured_timeout_seconds: int,
    age_seconds: int | None = None,
    lock_held: bool = False,
    worker_pid: int | None = None,
    active_step_record: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    resolved = resolve_phase_runtime(step, configured_timeout_seconds=configured_timeout_seconds)
    payload: dict[str, Any] = asdict(resolved)
    stale = False
    if age_seconds is not None:
        stale = age_seconds >= resolved.escalation_threshold_seconds
        payload["age_seconds"] = age_seconds
        payload["stale"] = stale
    observation = (
        observe_active_step_worker(active_step_record)
        if active_step_record is not None
        else WorkerLivenessObservation(
            WORKER_UNKNOWN,
            "pid-only record has no namespace/process-incarnation binding",
            {"pid": worker_pid},
        )
        if worker_pid is not None
        else None
    )
    if observation is not None:
        payload["worker_liveness"] = observation.state
        payload["worker_liveness_reason"] = observation.reason
    if observation is not None and observation.state == WORKER_DEAD:
        payload["health"] = "dead"
        payload["worker_pid_alive"] = False
        payload["recommended_action"] = "resume_or_recover"
        payload["recommended_action_reason"] = observation.reason
        return payload
    if observation is not None and observation.state == WORKER_LIVE:
        payload["worker_pid_alive"] = True
    if observation is not None and observation.state == WORKER_UNKNOWN:
        payload["health"] = "unknown"
        payload["recommended_action"] = "wait"
        payload["recommended_action_reason"] = (
            f"Worker liveness is UNKNOWN: {observation.reason}; redispatch is forbidden."
        )
        return payload
    if age_seconds is None or not stale:
        payload["health"] = "healthy"
        payload["recommended_action"] = "wait"
        payload["recommended_action_reason"] = "The active step is within its expected runtime window."
        return payload
    if lock_held:
        payload["health"] = "slow"
        payload["recommended_action"] = "wait"
        payload["recommended_action_reason"] = (
            "The active step has exceeded its expected runtime window, but the plan lock is still held."
        )
        return payload
    payload["health"] = "stale"
    if step in {"execute", "loop_execute"}:
        payload["recommended_action"] = "rerun_execute"
        payload["recommended_action_reason"] = (
            "The active execute step is stale and no process holds the plan lock."
        )
    else:
        payload["recommended_action"] = "rerun_same_step"
        payload["recommended_action_reason"] = (
            "The active step is stale and no process holds the plan lock."
        )
    return payload
