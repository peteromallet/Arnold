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
import re
import time
from typing import Any

from arnold_pipelines.megaplan.cloud.maintenance_dispatch import (
    MAINTENANCE_REQUIRED_RUNTIME_MODEL,
    MaintenanceModelEnforcementError,
    finalize_maintenance_dispatch_receipt,
    prepare_maintenance_dispatch_receipt,
    record_maintenance_started,
)
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
from arnold_pipelines.megaplan.cloud.repair_contract import append_escalation_record
from arnold_pipelines.megaplan.cloud.six_hour_auditor import (
    AUDIT_CODEX_MODEL,
    AuditDispatchError,
    enqueue_audit_repair_request,
    validate_audit_model_inputs,
)
from arnold_pipelines.megaplan.receipts.writer import (
    DispatchFinalizationError,
    DispatchInitializationError,
    initialize_dispatch_receipt,
)
from arnold_pipelines.megaplan.chain.spec import (
    chain_spec_sha256 as _chain_spec_sha256,
)
from arnold_pipelines.megaplan.incident.ledger import RuntimeTransitionWriter
from arnold_pipelines.megaplan.cloud.wrappers.repair_delegation import (
    emit_zero_authority_rejection,
)


CONTROLLER_SCHEMA = "arnold-progress-auditor-escalation-controller-v1"
MANAGED_LAUNCH_SETTLE_SECONDS = 5.0
MANAGED_LAUNCH_SETTLE_POLL_SECONDS = 0.05


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


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _finding_spec_path(finding: Mapping[str, Any]) -> str:
    """Return the chain spec path referenced by a finding, or ``""``.

    The chain-spec contract digest for the mandatory runtime-transition
    journal is derived from the finding's authoritative spec reference
    (``session_header.remote_spec``, falling back to the current target's
    ``remote_spec``).  A missing reference fails closed at the enqueue point.
    """
    header = _mapping(finding.get("session_header"))
    target_refs = _mapping(_mapping(finding.get("current_target")).get("current_refs"))
    return str(header.get("remote_spec") or target_refs.get("remote_spec") or "").strip()


def _settled_managed_launch(
    manifest_path: Path,
    *,
    gate: Mapping[str, Any],
    request_id: str,
    timeout_seconds: float = MANAGED_LAUNCH_SETTLE_SECONDS,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Wait briefly for the asynchronous managed supervisor's start receipt.

    The repair trigger intentionally returns after spawning the supervisor.  Its
    manifest is therefore allowed a small bounded establishment window.  Once a
    non-empty manifest has non-transient contract errors, validation still fails
    immediately rather than waiting or weakening the launch contract.
    """

    deadline = time.monotonic() + max(0.0, timeout_seconds)
    while True:
        manifest = _load_json(manifest_path)
        launch = validate_managed_launch(
            manifest,
            gate=gate,
            request_id=request_id,
        )
        transient = not manifest or set(launch["errors"]) == {
            "worker_start_evidence_missing"
        }
        if launch["valid"] or not transient or time.monotonic() >= deadline:
            return manifest, launch
        time.sleep(MANAGED_LAUNCH_SETTLE_POLL_SECONDS)


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


def _sidecar_dir(state_root: Path) -> Path:
    return state_root.with_name(f"{state_root.name}.d")


def _reconciler_drift_findings(finding: Mapping[str, Any]) -> list[dict[str, Any]]:
    incident_audit = (
        finding.get("incident_audit")
        if isinstance(finding.get("incident_audit"), Mapping)
        else {}
    )
    audit_findings = incident_audit.get("findings") if isinstance(incident_audit, Mapping) else []
    preserved: list[dict[str, Any]] = []
    if not isinstance(audit_findings, Sequence):
        return preserved
    for item in audit_findings:
        if not isinstance(item, Mapping):
            continue
        if str(item.get("code") or "") != "DRIFT_DETECTED":
            continue
        preserved.append(
            {
                "layer": str(item.get("layer") or ""),
                "code": str(item.get("code") or ""),
                "source_pair": str(item.get("source_pair") or ""),
                "contradiction": str(item.get("contradiction") or ""),
                "recommendation": str(item.get("recommendation") or ""),
                "observed": dict(item.get("observed") or {})
                if isinstance(item.get("observed"), Mapping)
                else {},
                "expected": dict(item.get("expected") or {})
                if isinstance(item.get("expected"), Mapping)
                else {},
            }
        )
    return preserved


def _append_l3_evidence(
    state_root: Path,
    *,
    gate: Mapping[str, Any],
    finding: Mapping[str, Any],
    record: Mapping[str, Any],
) -> Path:
    payload: dict[str, Any] = {
        "session": str(gate.get("session") or record.get("session") or ""),
        "event": "l3_escalation_decision",
        "escalation_id": str(gate.get("escalation_id") or record.get("escalation_id") or ""),
        "plan": str(gate.get("plan") or record.get("plan") or ""),
        "gate": str(record.get("gate") or gate.get("decision") or ""),
        "decision": str(record.get("decision") or ""),
        "reason": str(record.get("reason") or ""),
        "repair_dispatched": bool(record.get("repair_dispatched") is True),
        "repair_request_id": str(record.get("repair_request_id") or ""),
        "managed_run_id": str(record.get("managed_run_id") or ""),
        "managed_manifest_path": str(record.get("managed_manifest_path") or ""),
        "reconciler_drift_findings": _reconciler_drift_findings(finding),
        "resolver_state": dict(finding.get("resolver_state") or {})
        if isinstance(finding.get("resolver_state"), Mapping)
        else {},
        "deterministic_superfixer_evidence": dict(
            finding.get("deterministic_superfixer_evidence") or {}
        )
        if isinstance(finding.get("deterministic_superfixer_evidence"), Mapping)
        else {},
    }
    if isinstance(record.get("reverification"), Mapping):
        payload["reverification"] = dict(record.get("reverification") or {})
    return append_escalation_record(_sidecar_dir(state_root), payload)


# ── Step 43: trigger argv shim validation ────────────────────────────────────
#
# Arbitrary trigger argv execution (the legacy default subprocess runner path)
# has been retired.  The controller no longer spawns a child process from
# caller-supplied argv.  Instead, argv that reaches the production dispatch
# path (``trigger_runner is None``) is classified against a closed rejection
# vocabulary and emitted as a typed zero-authority outcome through the
# repair-delegation shim.  Authority is never derived from labels, liveness,
# WBC receipts, or rebuildable projections: recognition only narrows the typed
# rejection reason and never constitutes authority.

#: Closed vocabulary of trigger-argv rejection kinds.
TRIGGER_ARGV_REJECTION_KINDS: tuple[str, ...] = (
    "legacy_binary_name",
    "shell_token",
    "caller_runner",
    "deep_superfixer_identity",
)

#: Legacy binary/script names whose presence in argv is a retired authority
#: surface.  The canonical path is simple_fixer delegation, not a subprocess
#: trigger binary.
_LEGACY_TRIGGER_BINARY_NAMES: tuple[str, ...] = (
    "arnold-repair-trigger",
    "arnold-repair-loop",
    "arnold-watchdog",
    "arnold-auditor",
    "arnold-meta",
)

#: Legacy binary-selection flags from the retired wrapper contract.
_LEGACY_TRIGGER_BINARY_FLAGS: tuple[str, ...] = (
    "--repair-bin",
    "--meta-repair-bin",
)

#: Shell metacharacters that turn an argv token into an injection vector.
_SHELL_TOKEN_PATTERN = re.compile(r"[;&|`$<>]|\|\||&&|\$\(|\$\{|\n|\r")

#: Markers that identify a direct caller-runner or module launch rather than a
#: canonical delegation surface.
_CALLER_RUNNER_MARKERS: tuple[str, ...] = (
    "repairrunner",
    "subprocess.popen",
    "subprocess.run",
    "os.system",
    "python -m arnold_pipelines",
    "arnold_pipelines.megaplan.cloud.",
)

#: Deep-superfixer / deep-repair identity markers that are not typed occurrence
#: outcomes of a canonical repair.
_DEEP_SUPERFIXER_MARKERS: tuple[str, ...] = (
    "superfixer",
    "deep_repair",
    "deep-repair",
)


def _classify_trigger_argv(trigger_argv: Sequence[str]) -> str | None:
    """Classify caller-supplied trigger argv against the closed rejection set.

    Returns the rejection kind (a member of
    :data:`TRIGGER_ARGV_REJECTION_KINDS`) when the argv carries a recognized
    command-authority bypass marker, or ``None`` when no marker is recognized.
    Recognition never constitutes authority: a ``None`` return on the
    production path still results in a typed rejection because arbitrary
    subprocess execution has been retired in favour of simple_fixer delegation.
    """
    for token in trigger_argv:
        lowered = str(token).lower()
        if any(name in lowered for name in _LEGACY_TRIGGER_BINARY_NAMES):
            return "legacy_binary_name"
        if any(flag in lowered for flag in _LEGACY_TRIGGER_BINARY_FLAGS):
            return "legacy_binary_name"
        if _SHELL_TOKEN_PATTERN.search(str(token)):
            return "shell_token"
        if any(marker in lowered for marker in _CALLER_RUNNER_MARKERS):
            return "caller_runner"
        if any(marker in lowered for marker in _DEEP_SUPERFIXER_MARKERS):
            return "deep_superfixer_identity"
    return None


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


def _reconcile_terminal_states(
    state_root: Path,
    findings: Sequence[Mapping[str, Any]],
    *,
    now: datetime | None,
    policy: EscalationPolicy,
) -> None:
    """Close terminal attempts even when fresh evidence changed the fingerprint.

    Escalation identity deliberately includes the current failure fingerprint.
    A failed worker can therefore expose a new failure class before the next
    audit. Reconcile older same-target state first so durable custody never
    leaves a terminal manifest labelled ``running`` merely because its newer
    finding now hashes to a different escalation id.
    """

    by_target: dict[tuple[str, str], Mapping[str, Any]] = {}
    current_escalation_ids: set[str] = set()
    for finding in findings:
        key = (
            str(finding.get("session") or ""),
            str(finding.get("plan") or ""),
        )
        if all(key):
            by_target[key] = finding
        current_escalation_ids.add(
            str(classify_true_stall(finding, policy=policy).get("escalation_id") or "")
        )
    for path in state_root.glob("*/state.json"):
        state = _load_json(path)
        if str(state.get("escalation_id") or "") in current_escalation_ids:
            # The main controller loop re-verifies this exact identity and
            # carries the verification receipt into the current report.
            continue
        finding = by_target.get(
            (str(state.get("session") or ""), str(state.get("plan") or ""))
        )
        if finding is None:
            continue
        updated, verification = _terminal_reverification(
            state,
            finding,
            now=now,
            policy=policy,
        )
        if verification is not None:
            _atomic_json(path, updated)


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
    transition_writer: RuntimeTransitionWriter | None = None,
    chain_spec_sha256: str = "",
    dispatch_receipt_root: Path | None = None,
    resolved_runtime_model: str | None = None,
) -> dict[str, Any]:
    """Evaluate findings and, if authorized, invoke canonical repair custody.

    G3: every enqueue that creates a repair request must FIRST journal the
    declared deviation and the considered fallback to the incident ledger.
    When no ``transition_writer`` is supplied it is constructed from the
    finding's workspace, and when no ``chain_spec_sha256`` is supplied it is
    derived from the finding's chain spec reference.  Missing inputs (no
    workspace, no spec reference, unreadable spec) FAIL CLOSED: the enqueue —
    and therefore the dispatch — is blocked before any request is created.

    Arbitrary ``trigger_argv`` execution has been retired (Step 43).  When no
    ``trigger_runner`` is supplied (the production path), the controller no
    longer spawns a subprocess: argv is classified against a closed rejection
    vocabulary and emitted as a typed zero-authority outcome via the
    repair-delegation shim.  A caller-supplied ``trigger_runner`` remains a
    controlled test seam for managed-launch validation and still receives
    ``--request-id`` so the resulting run is correlated with this exact finding.
    """

    selected = policy or EscalationPolicy()
    runner = trigger_runner
    result = dict(payload)
    findings = [dict(item) for item in payload.get("findings") or [] if isinstance(item, dict)]
    green_checks = [dict(item) for item in payload.get("green_checks") or [] if isinstance(item, dict)]
    summary: list[dict[str, Any]] = []
    if not authorized:
        for finding in findings:
            gate = classify_true_stall(finding, policy=selected)
            finding["l3_escalation_gate"] = gate
            existing_owner = launch_suppressed_by_existing_owner(finding)
            approval_required = gate.get("decision") == "approval_required"
            finding["l3_escalation"] = {
                "escalation_id": gate["escalation_id"],
                "session": gate.get("session"),
                "plan": gate.get("plan"),
                "gate": gate.get("decision"),
                "decision": (
                    "approval_required"
                    if approval_required
                    else "existing_owner_no_new_launch"
                    if existing_owner
                    else "blocked_authority"
                    if gate.get("eligible")
                    else "report_only"
                ),
                "reason": (
                    str(_mapping(gate.get("corrective_path")).get("reason") or "")
                    if approval_required
                    else "healthy canonical ownership already covers this repair objective"
                    if existing_owner
                    else "L3 master-plus-path mutation authority is absent"
                    if gate.get("eligible")
                    else str(gate.get("gather_reason") or "true-stall gate did not pass")
                ),
                "repair_dispatched": False,
                "corrective_path": dict(_mapping(gate.get("corrective_path"))),
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
        _reconcile_terminal_states(
            state_root,
            findings,
            now=now,
            policy=selected,
        )
        active_global, active_by_session = _active_counts(state_root)
        seen_escalations: set[str] = set()
        for finding in findings:
            gate = classify_true_stall(finding, policy=selected)
            finding["l3_escalation_gate"] = gate

            def finalize_record(record: dict[str, Any]) -> None:
                finding["l3_escalation"] = record
                record["repair_evidence_path"] = str(
                    _append_l3_evidence(
                        state_root,
                        gate=gate,
                        finding=finding,
                        record=record,
                    )
                )
                summary.append(record)

            if gate.get("decision") == "approval_required":
                record = {
                    "escalation_id": gate["escalation_id"],
                    "session": gate.get("session"),
                    "plan": gate.get("plan"),
                    "gate": "approval_required",
                    "decision": "approval_required",
                    "reason": str(
                        _mapping(gate.get("corrective_path")).get("reason") or ""
                    ),
                    "repair_dispatched": False,
                    "managed_run_id": "",
                    "managed_manifest_path": "",
                    "corrective_path": dict(_mapping(gate.get("corrective_path"))),
                }
                finalize_record(record)
                continue
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
                finalize_record(record)
                continue
            escalation_id = str(gate["escalation_id"])
            if escalation_id in seen_escalations:
                record = {
                    "escalation_id": escalation_id,
                    "session": gate.get("session"),
                    "plan": gate.get("plan"),
                    "gate": gate.get("decision"),
                    "decision": "duplicate_target_observation",
                    "reason": "another finding in this cycle already owns the authoritative target",
                    "repair_dispatched": False,
                    "managed_run_id": "",
                    "managed_manifest_path": "",
                }
                finalize_record(record)
                continue
            seen_escalations.add(escalation_id)
            path = _state_path(state_root, escalation_id)
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
            if gate.get("gather_reason"):
                record["gather_reason"] = gate["gather_reason"]
            if verification is not None:
                record["reverification"] = verification
            if not dispatch["dispatch"]:
                finalize_record(record)
                continue

            context_path = _context_path(state_root, str(gate["escalation_id"]))
            context = bounded_repair_context(finding)
            _atomic_json(context_path, context)
            attempts = [
                item for item in state.get("attempts") or [] if isinstance(item, Mapping)
            ]
            # G3: mandatory emission — the enqueue is the auditor's only
            # operational handoff and must be journaled FIRST.  A missing
            # writer (no workspace), a missing spec reference, or an
            # unreadable spec FAILS CLOSED before any request is created.
            writer = transition_writer
            if writer is None:
                workspace_root = str(finding.get("workspace") or "").strip()
                if not workspace_root:
                    raise ValueError(
                        "l3 escalation enqueue blocked: finding carries no "
                        "workspace to construct the runtime transition writer "
                        "(missing input fails closed)"
                    )
                writer = RuntimeTransitionWriter(Path(workspace_root))
            spec_path = _finding_spec_path(finding)
            if not spec_path:
                raise ValueError(
                    "l3 escalation enqueue blocked: finding carries no chain "
                    "spec reference to compute chain_spec_sha256 (missing "
                    "input fails closed)"
                )
            if not chain_spec_sha256:
                try:
                    chain_digest = _chain_spec_sha256(Path(spec_path))
                except (OSError, TypeError, ValueError) as exc:
                    raise ValueError(
                        "l3 escalation enqueue blocked: chain_spec_sha256 "
                        f"could not be computed from {spec_path}: {exc}"
                    ) from exc
            else:
                chain_digest = chain_spec_sha256
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
                transition_writer=writer,
                chain_spec_sha256=chain_digest,
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
                finalize_record(record)
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
                finalize_record(record)
                continue

            # Step 43: arbitrary trigger argv execution has been retired.  The
            # production dispatch path (no caller-supplied trigger_runner)
            # classifies argv through the closed rejection vocabulary and emits
            # a typed zero-authority rejection via the delegation shim instead
            # of spawning a child process.  A caller-supplied trigger_runner
            # remains a controlled test seam for managed-launch validation, so
            # existing managed-launch receipts keep flowing through it.
            if runner is None:
                rejection_kind = _classify_trigger_argv(trigger_argv) or (
                    "retired_subprocess_authority"
                )
                rejection = emit_zero_authority_rejection(
                    "controller",
                    request_id or str(gate.get("escalation_id") or ""),
                    reason=(
                        "noncanonical trigger argv rejected by shim validation: "
                        f"{rejection_kind}"
                    ),
                )
                record.update(
                    {
                        "decision": "trigger_argv_rejected",
                        "reason": (
                            "trigger argv authority bypass rejected; arbitrary "
                            "subprocess dispatch has been retired in favour of "
                            "canonical simple_fixer delegation"
                        ),
                        "trigger_argv_rejection_kind": rejection_kind,
                        "delegation_outcome": rejection.outcome,
                    }
                )
                finalize_record(record)
                continue

            # T13: prelaunch receipt initialization.  The maintenance
            # subprocess may launch only behind a durable initialized dispatch
            # receipt, an exact receipt-proven runtime model, and
            # non-conflicting pins.  Initialization failure blocks the launch;
            # conflicting pins and wrong/missing resolved-model evidence fail
            # visibly before any subprocess effect.
            dispatch_receipt = None
            if dispatch_receipt_root is not None:
                validate_audit_model_inputs(dict(os.environ))
                if resolved_runtime_model != MAINTENANCE_REQUIRED_RUNTIME_MODEL:
                    raise AuditDispatchError(
                        "l3 escalation dispatch refused: receipt-proven runtime "
                        f"model must be exactly {MAINTENANCE_REQUIRED_RUNTIME_MODEL!r}, "
                        f"got {resolved_runtime_model!r}",
                    )
                dispatch_receipt = initialize_dispatch_receipt(
                    dispatch_receipt_root,
                    prepare_maintenance_dispatch_receipt(
                        action="l3_escalation_dispatch",
                        configured_model=MAINTENANCE_REQUIRED_RUNTIME_MODEL,
                    ),
                )
                record["dispatch_receipt_root"] = str(dispatch_receipt_root)
                record["dispatch_id"] = dispatch_receipt["dispatch_id"]
                finding["dispatch_receipt_root"] = str(dispatch_receipt_root)
                finding["dispatch_id"] = dispatch_receipt["dispatch_id"]

            trigger = runner([*trigger_argv, "--request-id", request_id])

            # The subprocess-start transition is recorded with the resolved
            # runtime model the moment launch returns.  A persistence failure
            # surfaces the explicit indeterminate receipt and never downgrades
            # the started action back to report-only.
            if dispatch_receipt is not None:
                try:
                    dispatch_receipt = record_maintenance_started(
                        dispatch_receipt_root,
                        dispatch_receipt,
                        resolved_runtime_model=resolved_runtime_model,
                    )
                except DispatchFinalizationError as exc:
                    record["dispatch_receipt_error"] = str(exc)
                    record["dispatch_receipt_indeterminate"] = dict(exc.receipt)
            event = _trigger_event(trigger.stdout, request_id)
            record["trigger_returncode"] = trigger.returncode
            record["trigger_event"] = event
            record["trigger_stderr"] = trigger.stderr[-4000:]
            manifest_path = Path(str(event.get("managed_manifest_path") or ""))
            if event.get("status") == "dispatched" and str(manifest_path):
                manifest, launch = _settled_managed_launch(
                    manifest_path,
                    gate=gate,
                    request_id=request_id,
                )
            else:
                manifest = _load_json(manifest_path) if str(manifest_path) else {}
                launch = validate_managed_launch(
                    manifest,
                    gate=gate,
                    request_id=request_id,
                )
            event_run_id = str(event.get("managed_run_id") or "")
            manifest_run_id = str(manifest.get("run_id") or "")
            if event_run_id and event_run_id != manifest_run_id:
                launch = {
                    **launch,
                    "valid": False,
                    "dispatched": False,
                    "errors": [*launch["errors"], "trigger_manifest_run_id_mismatch"],
                    "managed_run_id": "",
                    "managed_manifest_path": "",
                }
            if (
                trigger.returncode != 0
                or event.get("status") != "dispatched"
                or not launch["valid"]
            ):
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
            # T13: close the dispatch receipt with explicit mutation facts.
            # The launch itself performed no state/source/commit/push mutation;
            # those facts are recorded explicitly rather than inferred.  Any
            # post-launch receipt failure leaves the explicit indeterminate
            # receipt on the record, so a started action is never downgraded.
            if dispatch_receipt is not None:
                receipt_outcome = (
                    "succeeded"
                    if (
                        trigger.returncode == 0
                        and event.get("status") == "dispatched"
                        and launch["valid"]
                    )
                    else "failed"
                )
                try:
                    finalize_maintenance_dispatch_receipt(
                        dispatch_receipt_root,
                        dispatch_receipt,
                        outcome=receipt_outcome,
                        resolved_runtime_model=resolved_runtime_model,
                        mutation_facts={
                            "state": False,
                            "source": False,
                            "commit": False,
                            "push": False,
                        },
                        detail=(
                            "l3 escalation dispatch subprocess returned "
                            f"{trigger.returncode}; launch evidence "
                            f"{'established' if receipt_outcome == 'succeeded' else 'not established'}"
                        ),
                    )
                except (DispatchFinalizationError, MaintenanceModelEnforcementError) as exc:
                    record["dispatch_receipt_error"] = str(exc)
                    record["dispatch_receipt_indeterminate"] = dict(exc.receipt)
            _atomic_json(path, state)
            finalize_record(record)

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
    transition_writer: RuntimeTransitionWriter | None = None,
    chain_spec_sha256: str = "",
    dispatch_receipt_root: Path | None = None,
    resolved_runtime_model: str | None = None,
) -> dict[str, Any]:
    payload = _load_json(findings_path)
    result = run_escalation_controller(
        payload,
        state_root=state_root,
        queue_root=queue_root,
        authorized=authorized,
        trigger_argv=trigger_argv,
        transition_writer=transition_writer,
        chain_spec_sha256=chain_spec_sha256,
        dispatch_receipt_root=dispatch_receipt_root,
        resolved_runtime_model=resolved_runtime_model,
    )
    _atomic_json(findings_path, result)
    return result


__all__ = [
    "CONTROLLER_SCHEMA",
    "TRIGGER_ARGV_REJECTION_KINDS",
    "TriggerResult",
    "run_escalation_controller",
    "run_file_controller",
]
