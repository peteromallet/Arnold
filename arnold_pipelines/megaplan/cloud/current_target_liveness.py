"""One identity-bound tri-state liveness view for cloud control decisions.

PIDs and tmux sessions are namespace-local.  This module is the sole place
where those observations may become ``live`` or ``dead``.  A local PID is
authoritative only when both its PID namespace and process-start identity are
bound to the target.  A runner-owned, marker-bound lease is the cross-container
path to ``live``.  Everything else is ``unknown`` and therefore cannot
authorize mutation, escalation, or retrigger.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping

from arnold_pipelines.megaplan.cloud.liveness_lease import observe_liveness_lease


SCHEMA = "arnold.megaplan.current_target_liveness.v1"

PidProbe = Callable[[int], bool | None]
ProcessStartProbe = Callable[[int], str | None]
SessionProbe = Callable[[str], bool | None]


def _text(value: object) -> str:
    return str(value or "").strip()


def _integer(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _namespace_id() -> str:
    try:
        return os.readlink("/proc/self/ns/pid")
    except OSError:
        return ""


def _process_start_identity(pid: int) -> str | None:
    """Return Linux boot-id + start ticks for one PID incarnation."""

    try:
        raw = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
        start_ticks = raw.rsplit(")", 1)[1].strip().split()[19]
        boot_id = (
            Path("/proc/sys/kernel/random/boot_id").read_text(encoding="utf-8").strip()
        )
    except (OSError, IndexError):
        return None
    return f"{boot_id}:{start_ticks}"


def _pid_live(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _candidate(
    marker: Mapping[str, Any], active_step: Mapping[str, Any]
) -> dict[str, Any]:
    """Prefer launch identity, then an explicitly-bound active worker."""

    candidates: list[dict[str, Any]] = []
    for source, value in (("marker", marker), ("active_step", active_step)):
        pid = _integer(
            value.get("pid") if source == "marker" else value.get("worker_pid")
        )
        namespace = _text(
            value.get("pid_namespace_id")
            or value.get("runner_pid_namespace_id")
            or value.get("worker_pid_namespace_id")
        )
        start = _text(
            value.get("process_start_identity")
            or value.get("runner_process_start_identity")
            or value.get("target_process_start_identity")
            or value.get("worker_process_start_identity")
        )
        if pid is not None:
            candidates.append(
                {
                    "source": source,
                    "pid": pid,
                    "pid_namespace_id": namespace,
                    "process_start_identity": start,
                }
            )
    for candidate in candidates:
        if candidate["pid_namespace_id"] and candidate["process_start_identity"]:
            return candidate
    if candidates:
        return candidates[0]
    return {
        "source": "",
        "pid": None,
        "pid_namespace_id": "",
        "process_start_identity": "",
    }


def _result(
    state: str,
    *,
    source: str,
    reason: str,
    identity: Mapping[str, Any],
    lease: Mapping[str, Any],
    diagnostics: list[str],
) -> dict[str, Any]:
    known = state in {"live", "dead"}
    return {
        "schema": SCHEMA,
        "state": state,
        "live": state == "live",
        "dead": state == "dead",
        "known": known,
        "source": source,
        "reason": reason,
        "identity": dict(identity),
        "lease": dict(lease),
        "diagnostics": diagnostics,
        "control_permitted": known,
        "mutation_permitted": known,
        "escalation_permitted": known,
        "retrigger_permitted": known,
    }


def observe_current_target_liveness(
    marker: Mapping[str, Any],
    *,
    marker_dir: str | Path,
    active_step: Mapping[str, Any] | None = None,
    pid_is_live: PidProbe | None = None,
    process_start_identity: ProcessStartProbe | None = None,
    observer_pid_namespace_id: str | None = None,
    session_is_live: SessionProbe | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Observe one target without interpreting foreign-namespace misses as death."""

    marker = marker if isinstance(marker, Mapping) else {}
    active_step = active_step if isinstance(active_step, Mapping) else {}
    diagnostics: list[str] = []
    session = _text(marker.get("session"))
    lease = observe_liveness_lease(marker, marker_dir=Path(marker_dir), now=now)

    identity = _candidate(marker, active_step)
    expected_pid = _integer(identity.get("pid"))
    expected_namespace = _text(identity.get("pid_namespace_id"))
    expected_start = _text(identity.get("process_start_identity"))
    observer_namespace = (
        _text(observer_pid_namespace_id)
        if observer_pid_namespace_id is not None
        else _namespace_id()
    )
    identity.update(
        {
            "observer_pid_namespace_id": observer_namespace,
            "namespace_matches": bool(
                expected_namespace
                and observer_namespace
                and expected_namespace == observer_namespace
            ),
            "observed_process_start_identity": "",
            "process_start_matches": None,
        }
    )

    local_state = "unknown"
    local_reason = "target has no namespace-and-start-bound local PID"
    if expected_pid is not None and expected_namespace and expected_start:
        if not observer_namespace:
            local_reason = "observer PID namespace is unavailable"
        elif expected_namespace != observer_namespace:
            local_reason = "target PID belongs to a foreign namespace"
        else:
            live_probe = pid_is_live or _pid_live
            start_probe = process_start_identity or _process_start_identity
            probe_live = live_probe(expected_pid)
            if probe_live is False:
                # The observer is in the bound namespace and the marker names
                # the exact incarnation.  Absence is therefore meaningful.
                local_state = "dead"
                local_reason = "bound PID is absent in its owning namespace"
            elif probe_live is True:
                observed_start = start_probe(expected_pid)
                identity["observed_process_start_identity"] = observed_start or ""
                identity["process_start_matches"] = bool(
                    observed_start and observed_start == expected_start
                )
                if observed_start == expected_start:
                    local_state = "live"
                    local_reason = "namespace and process-start identity match"
                elif observed_start:
                    local_state = "dead"
                    local_reason = "PID was reused by a different process incarnation"
                else:
                    local_reason = "process start identity could not be observed"
            else:
                local_reason = "bound PID probe returned unknown"
    else:
        missing = []
        if expected_pid is None:
            missing.append("pid")
        if not expected_namespace:
            missing.append("pid_namespace_id")
        if not expected_start:
            missing.append("process_start_identity")
        diagnostics.append("local identity incomplete: " + ", ".join(missing))

    # tmux is useful diagnostic evidence but cannot decide target liveness:
    # its namespace is not bound by the marker contract.
    if session and session_is_live is not None:
        try:
            diagnostics.append(f"unbound session probe={session_is_live(session)!r}")
        except Exception as exc:  # pragma: no cover - defensive adapter boundary
            diagnostics.append(f"session probe failed: {type(exc).__name__}")

    lease_live = lease.get("state") == "live" and lease.get("live") is True
    if lease_live and local_state == "dead":
        return _result(
            "unknown",
            source="contradictory_bound_evidence",
            reason="fresh owner lease contradicts local bound-PID absence",
            identity=identity,
            lease=lease,
            diagnostics=diagnostics,
        )
    if lease_live:
        return _result(
            "live",
            source="fresh_owner_lease",
            reason="fresh marker-bound runner lease",
            identity=identity,
            lease=lease,
            diagnostics=diagnostics,
        )
    if local_state in {"live", "dead"}:
        return _result(
            local_state,
            source="matched_local_process_identity",
            reason=local_reason,
            identity=identity,
            lease=lease,
            diagnostics=diagnostics,
        )
    return _result(
        "unknown",
        source="insufficient_bound_evidence",
        reason=local_reason,
        identity=identity,
        lease=lease,
        diagnostics=diagnostics,
    )


def liveness_from_current_target(target: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return the canonical view, never upgrading legacy booleans to authority."""

    if isinstance(target, Mapping):
        value = target.get("current_target_liveness") or target.get("liveness")
        if isinstance(value, Mapping) and value.get("schema") == SCHEMA:
            return dict(value)
    return _result(
        "unknown",
        source="canonical_observation_missing",
        reason="current target has no bound liveness observation",
        identity={},
        lease={},
        diagnostics=[],
    )


_ACTION_FLAG = {
    "control": "control_permitted",
    "mutation": "mutation_permitted",
    "escalation": "escalation_permitted",
    "retrigger": "retrigger_permitted",
}


def control_liveness_from_current_target(
    target: Mapping[str, Any] | None, *, action: str = "control"
) -> dict[str, Any]:
    """Return a strict canonical observation suitable for wrapper control.

    ``liveness_from_current_target`` is also a compatibility reader for older
    callers that only display the record.  Control-plane wrappers need a
    stronger contract: the schema, tri-state booleans, and action-specific
    permission bit must all agree.  Missing, truncated, hand-written, or
    otherwise corrupt records therefore collapse to ``unknown``.  Legacy PID,
    tmux, heartbeat, and runner-transition fields are deliberately ignored.
    """

    required_flag = _ACTION_FLAG.get(action)
    if required_flag is None:
        raise ValueError(f"unsupported liveness control action: {action}")
    raw = None
    if isinstance(target, Mapping):
        candidate = target.get("current_target_liveness") or target.get("liveness")
        if isinstance(candidate, Mapping):
            raw = candidate
    state = _text(raw.get("state") if raw else "").lower()
    known = state in {"live", "dead"}
    structurally_valid = bool(
        raw
        and raw.get("schema") == SCHEMA
        and state in {"live", "dead", "unknown"}
        and raw.get("known") is known
        and raw.get("live") is (state == "live")
        and raw.get("dead") is (state == "dead")
        and raw.get("control_permitted") is known
        and raw.get("mutation_permitted") is known
        and raw.get("escalation_permitted") is known
        and raw.get("retrigger_permitted") is known
    )
    if not structurally_valid:
        result = _result(
            "unknown",
            source="canonical_observation_invalid",
            reason="canonical liveness record is missing or structurally invalid",
            identity={},
            lease={},
            diagnostics=["legacy process evidence is diagnostic-only"],
        )
        result.update(
            {
                "authoritative": False,
                "requested_action": action,
                "action_permitted": False,
            }
        )
        return result
    result = dict(raw)
    permitted = bool(known and raw.get(required_flag) is True)
    result.update(
        {
            "authoritative": True,
            "requested_action": action,
            "action_permitted": permitted,
            "control_permitted": bool(
                known and raw.get("control_permitted") is True
            ),
        }
    )
    return result


__all__ = [
    "SCHEMA",
    "control_liveness_from_current_target",
    "liveness_from_current_target",
    "observe_current_target_liveness",
]
