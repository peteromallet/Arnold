"""Durable effect controller for policy-authorized six-hour escalations.

The shell auditor finishes deterministic gather/report inputs before calling
this controller.  Ordinary findings stay observations.  Only a finding with a
validated ``true_stall`` gate can enter canonical repair custody, and only a
validated managed-agent manifest can be reported as dispatched.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import subprocess
from typing import Any

from arnold_pipelines.megaplan.cloud.progress_auditor_escalation import (
    EscalationPolicy,
    bounded_repair_context,
    classify_true_stall,
    next_attempt_state,
    plan_dispatch,
    record_reverification,
    validate_managed_launch,
    verify_recovery,
)
from arnold_pipelines.megaplan.cloud.progress_auditor_ownership import (
    launch_suppressed_by_existing_owner,
)
from arnold_pipelines.megaplan.cloud.six_hour_auditor import (
    enqueue_audit_repair_request,
)


CONTROLLER_SCHEMA = "arnold-progress-auditor-escalation-controller-v1"


@dataclass(frozen=True)
class TriggerResult:
    returncode: int
    stdout: str
    stderr: str


TriggerRunner = Callable[[Sequence[str]], TriggerResult]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(dict(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _state_path(state_root: Path, escalation_id: str) -> Path:
    token = escalation_id.rsplit(":", 1)[-1]
    return state_root / token / "state.json"


def _context_path(state_root: Path, escalation_id: str) -> Path:
    return _state_path(state_root, escalation_id).with_name("repair-context.json")


def _default_trigger_runner(argv: Sequence[str]) -> TriggerResult:
    try:
        completed = subprocess.run(
            list(argv),
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return TriggerResult(returncode=127, stdout="", stderr=f"{exc.__class__.__name__}: {exc}")
    return TriggerResult(
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def _trigger_event(stdout: str, request_id: str) -> dict[str, Any]:
    matches: list[dict[str, Any]] = []
    for line in stdout.splitlines():
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        if str(payload.get("request_id") or "") != request_id:
            continue
        matches.append(payload)
    for payload in reversed(matches):
        if payload.get("event") == "repair_trigger_dispatch":
            return payload
    return matches[-1] if matches else {}


def _active_counts(state_root: Path) -> tuple[int, dict[str, int]]:
    global_count = 0
    by_session: dict[str, int] = {}
    for path in state_root.glob("*/state.json"):
        state = _load_json(path)
        for attempt in state.get("attempts") or []:
            if not isinstance(attempt, dict):
                continue
            manifest_path = Path(str(attempt.get("managed_manifest_path") or ""))
            manifest = _load_json(manifest_path) if str(manifest_path) else {}
            if str(manifest.get("status") or "") not in {
                "reserved",
                "launching",
                "running",
                "adopting",
            }:
                continue
            global_count += 1
            session = str(state.get("session") or "")
            if session:
                by_session[session] = by_session.get(session, 0) + 1
    return global_count, by_session


def _terminal_reverification(
    state: Mapping[str, Any],
    finding: Mapping[str, Any],
    *,
    now: datetime | None,
    policy: EscalationPolicy,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Reverify a completed managed repair against fresh auditor evidence."""

    attempts = state.get("attempts") or []
    if not attempts or not isinstance(attempts[-1], Mapping):
        return dict(state), None
    attempt = attempts[-1]
    if str(attempt.get("status") or "") != "running":
        return dict(state), None
    manifest_path = Path(str(attempt.get("managed_manifest_path") or ""))
    if not str(attempt.get("managed_manifest_path") or ""):
        return dict(state), None
    manifest = _load_json(manifest_path)
    if str(manifest.get("status") or "") in {
        "reserved",
        "launching",
        "running",
        "adopting",
    }:
        return dict(state), None
    links = manifest.get("links") if isinstance(manifest.get("links"), Mapping) else {}
    outcome_path_raw = str(
        manifest.get("repair_outcome_path")
        or links.get("repair_outcome_path")
        or ""
    )
    outcome = _load_json(Path(outcome_path_raw)) if outcome_path_raw else {}
    if not outcome:
        outcome = {
            "managed_status": manifest.get("status"),
            "managed_exit_code": manifest.get("exit_code"),
            "fixer_fixed": False,
            "backstop_fixed": False,
            "guard_weakened": False,
        }
    verification = verify_recovery(
        baseline=state.get("baseline_cursor") if isinstance(state.get("baseline_cursor"), Mapping) else {},
        current_finding=finding,
        repair_outcome=outcome,
    )
    updated = record_reverification(
        state,
        verification=verification,
        now=now,
        policy=policy,
    )
    updated["repair_outcome_path"] = outcome_path_raw
    return updated, verification


def _persist_pending_request(
    state: Mapping[str, Any],
    *,
    gate: Mapping[str, Any],
    request_id: str,
    request_path: str,
    context_path: Path,
) -> dict[str, Any]:
    updated = dict(state)
    updated.update(
        {
            "schema_version": CONTROLLER_SCHEMA,
            "policy_version": gate.get("policy_version"),
            "escalation_id": gate.get("escalation_id"),
            "session": gate.get("session"),
            "plan": gate.get("plan"),
            "finding_evidence_digest": gate.get("evidence_digest"),
            "baseline_cursor": gate.get("baseline_cursor"),
            "route": gate.get("route"),
            "repair_request_id": request_id,
            "repair_request_path": request_path,
            "repair_context_path": str(context_path),
            "updated_at": _utc_now(),
            "outcome": "request_queued",
            "attempts": list(state.get("attempts") or []),
        }
    )
    return updated


def run_escalation_controller(
    payload: Mapping[str, Any],
    *,
    state_root: Path,
    queue_root: Path,
    authorized: bool,
    trigger_argv: Sequence[str] | None,
    trigger_runner: TriggerRunner | None = None,
    now: datetime | None = None,
    policy: EscalationPolicy | None = None,
) -> dict[str, Any]:
    """Evaluate findings and, if authorized, invoke canonical repair custody.

    ``trigger_argv`` must identify ``arnold-repair-trigger``.  The controller
    appends ``--request-id`` so the resulting run is correlated with this exact
    finding rather than whichever global queue entry happens to sort first.
    """

    selected = policy or EscalationPolicy()
    runner = trigger_runner or _default_trigger_runner
    result = dict(payload)
    findings = [dict(item) for item in payload.get("findings") or [] if isinstance(item, dict)]
    green_checks = [dict(item) for item in payload.get("green_checks") or [] if isinstance(item, dict)]
    summary: list[dict[str, Any]] = []
    if not authorized:
        for finding in findings:
            gate = classify_true_stall(finding, policy=selected)
            finding["l3_escalation_gate"] = gate
            existing_owner = launch_suppressed_by_existing_owner(finding)
            finding["l3_escalation"] = {
                "escalation_id": gate["escalation_id"],
                "session": gate.get("session"),
                "plan": gate.get("plan"),
                "gate": gate.get("decision"),
                "decision": (
                    "existing_owner_no_new_launch"
                    if existing_owner
                    else "blocked_authority"
                    if gate.get("eligible")
                    else "report_only"
                ),
                "reason": (
                    "healthy canonical ownership already covers this repair objective"
                    if existing_owner
                    else "L3 master-plus-path mutation authority is absent"
                    if gate.get("eligible")
                    else "true-stall gate did not pass"
                ),
                "repair_dispatched": False,
                "managed_run_id": "",
                "managed_manifest_path": "",
            }
            summary.append(dict(finding["l3_escalation"]))
        for item in green_checks:
            item["l3_escalation_gate"] = classify_true_stall(item, policy=selected)
            item["l3_escalation"] = {
                "decision": "report_only",
                "repair_dispatched": False,
                "reason": "green observation is not an actionable true stall",
            }
        result["findings"] = findings
        result["green_checks"] = green_checks
        result["l3_escalation_summary"] = {
            "schema_version": CONTROLLER_SCHEMA,
            "authorized": False,
            "evaluated": len(findings),
            "dispatched": 0,
            "items": summary,
        }
        return result

    state_root.mkdir(parents=True, exist_ok=True)
    lock_path = state_root / ".controller.lock"
    with lock_path.open("a+b") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        active_global, active_by_session = _active_counts(state_root)
        for finding in findings:
            gate = classify_true_stall(finding, policy=selected)
            finding["l3_escalation_gate"] = gate
            if launch_suppressed_by_existing_owner(finding):
                ownership = finding.get("existing_agent_ownership") or {}
                record = {
                    "escalation_id": gate["escalation_id"],
                    "session": gate.get("session"),
                    "plan": gate.get("plan"),
                    "gate": gate.get("decision"),
                    "decision": "existing_owner_no_new_launch",
                    "reason": "healthy canonical ownership already covers this repair objective",
                    "repair_dispatched": False,
                    "managed_run_id": "",
                    "managed_manifest_path": "",
                    "existing_owner_run_id": (
                        ownership.get("healthy_aligned_run_ids") or [""]
                    )[0],
                }
                finding["l3_escalation"] = record
                summary.append(record)
                continue
            path = _state_path(state_root, str(gate["escalation_id"]))
            state = _load_json(path)
            state, verification = _terminal_reverification(
                state,
                finding,
                now=now,
                policy=selected,
            )
            if verification is not None:
                _atomic_json(path, state)
            dispatch = plan_dispatch(
                gate,
                state,
                authorized=authorized,
                active_global=active_global,
                active_for_session=active_by_session.get(str(gate.get("session") or ""), 0),
                now=now,
                policy=selected,
            )
            record: dict[str, Any] = {
                "escalation_id": gate["escalation_id"],
                "session": gate.get("session"),
                "plan": gate.get("plan"),
                "gate": gate.get("decision"),
                "decision": dispatch["decision"],
                "reason": dispatch["reason"],
                "repair_dispatched": False,
                "managed_run_id": "",
                "managed_manifest_path": "",
            }
            if verification is not None:
                record["reverification"] = verification
            if not dispatch["dispatch"]:
                finding["l3_escalation"] = record
                summary.append(record)
                continue

            context_path = _context_path(state_root, str(gate["escalation_id"]))
            context = bounded_repair_context(finding)
            _atomic_json(context_path, context)
            attempts = [
                item for item in state.get("attempts") or [] if isinstance(item, Mapping)
            ]
            queued = enqueue_audit_repair_request(
                {
                    **finding,
                    "l3_escalation_gate": gate,
                    "l3_repair_context_path": str(context_path),
                    "l3_repair_context_digest": context.get("context_digest"),
                    "l3_retry_ordinal": len(attempts) + 1,
                    "l3_retry_of_run_id": str(attempts[-1].get("managed_run_id") or "")
                    if attempts
                    else "",
                },
                queue_root=queue_root,
            )
            if not queued:
                record.update(
                    {
                        "decision": "request_rejected",
                        "reason": "true-stall finding did not produce a typed repair request",
                    }
                )
                state = next_attempt_state(
                    state,
                    gate=gate,
                    outcome="launch_failed",
                    now=now,
                    policy=selected,
                )
                _atomic_json(path, state)
                finding["l3_escalation"] = record
                summary.append(record)
                continue
            request = queued.get("request") if isinstance(queued.get("request"), dict) else {}
            request_id = str(request.get("request_id") or "")
            state = _persist_pending_request(
                state,
                gate=gate,
                request_id=request_id,
                request_path=str(queued.get("path") or ""),
                context_path=context_path,
            )
            _atomic_json(path, state)
            record.update(
                {
                    "repair_request_id": request_id,
                    "repair_request_status": queued.get("status"),
                    "repair_request_path": queued.get("path"),
                    "repair_context_path": str(context_path),
                    "repair_context_digest": context.get("context_digest"),
                }
            )
            if not trigger_argv:
                record.update(
                    {
                        "decision": "request_queued",
                        "reason": "canonical trigger invocation was not configured",
                    }
                )
                finding["l3_escalation"] = record
                summary.append(record)
                continue

            trigger = runner([*trigger_argv, "--request-id", request_id])
            event = _trigger_event(trigger.stdout, request_id)
            record["trigger_returncode"] = trigger.returncode
            record["trigger_event"] = event
            record["trigger_stderr"] = trigger.stderr[-4000:]
            manifest_path = Path(str(event.get("managed_manifest_path") or ""))
            manifest = _load_json(manifest_path) if str(manifest_path) else {}
            launch = validate_managed_launch(
                manifest,
                gate=gate,
                request_id=request_id,
            )
            if event.get("status") != "dispatched" or not launch["valid"]:
                record.update(
                    {
                        "decision": "launch_failed",
                        "reason": "canonical managed launch evidence was not established",
                        "launch_validation_errors": launch["errors"],
                    }
                )
                state = next_attempt_state(
                    state,
                    gate=gate,
                    outcome="launch_failed",
                    request_id=request_id,
                    now=now,
                    policy=selected,
                )
                state["last_launch_failure"] = {
                    "recorded_at": _utc_now(),
                    "returncode": trigger.returncode,
                    "stderr": trigger.stderr[-4000:],
                    "stdout": trigger.stdout[-4000:],
                    "event": event,
                    "manifest_validation_errors": launch["errors"],
                }
            else:
                record.update(
                    {
                        "decision": "dispatched",
                        "reason": "canonical managed launch manifest validated",
                        "repair_dispatched": True,
                        "managed_run_id": launch["managed_run_id"],
                        "managed_manifest_path": launch["managed_manifest_path"],
                    }
                )
                state = next_attempt_state(
                    state,
                    gate=gate,
                    outcome="dispatched",
                    managed_run_id=launch["managed_run_id"],
                    managed_manifest_path=launch["managed_manifest_path"],
                    request_id=request_id,
                    now=now,
                    policy=selected,
                )
                active_global += 1
                session = str(gate.get("session") or "")
                active_by_session[session] = active_by_session.get(session, 0) + 1
            _atomic_json(path, state)
            finding["l3_escalation"] = record
            summary.append(record)

        # Healthy observations are still useful for independent re-verification,
        # but they can never create repair custody.
        for item in green_checks:
            item["l3_escalation_gate"] = classify_true_stall(item, policy=selected)
            item["l3_escalation"] = {
                "decision": "report_only",
                "repair_dispatched": False,
                "reason": "green observation is not an actionable true stall",
            }
    result["findings"] = findings
    result["green_checks"] = green_checks
    result["l3_escalation_summary"] = {
        "schema_version": CONTROLLER_SCHEMA,
        "authorized": authorized,
        "evaluated": len(findings),
        "dispatched": sum(1 for item in summary if item.get("repair_dispatched") is True),
        "items": summary,
    }
    return result


def run_file_controller(
    findings_path: Path,
    *,
    state_root: Path,
    queue_root: Path,
    authorized: bool,
    trigger_argv: Sequence[str] | None,
) -> dict[str, Any]:
    payload = _load_json(findings_path)
    result = run_escalation_controller(
        payload,
        state_root=state_root,
        queue_root=queue_root,
        authorized=authorized,
        trigger_argv=trigger_argv,
    )
    _atomic_json(findings_path, result)
    return result


__all__ = [
    "CONTROLLER_SCHEMA",
    "TriggerResult",
    "run_escalation_controller",
    "run_file_controller",
]
