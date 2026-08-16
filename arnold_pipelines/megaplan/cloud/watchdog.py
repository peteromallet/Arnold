"""Steps 15B-15C: Watchdog wrapper seams for recovery backstops.

Step 15B: Watchdog wrapper that converts malformed output, absent child,
fallback mismatch, missed events, and malformed L1/L2 evidence into
durable failures or typed escalation — never treating process presence
as success.

Step 15C: The wrapper is the single seam used by the six-hour
reconciliation backstop.  It accepts a runnable callable, captures
structured output, and refuses to treat a running process as evidence
of correctness.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

LOGGER = logging.getLogger(__name__)


# ── Escalation level ─────────────────────────────────────────────────────────


class EscalationLevel(str, Enum):
    """Typed escalation levels for recovery backstop failures."""

    NONE = "none"
    """No escalation needed — check passed."""

    WARNING = "warning"
    """Non-blocking anomaly — logged and tracked."""

    BLOCKING = "blocking"
    """Durable failure — requires human review."""

    CRITICAL = "critical"
    """Immediate escalation — data integrity at risk."""


# ── Evidence level ───────────────────────────────────────────────────────────


class EvidenceLevel(str, Enum):
    """Evidence quality levels for recovery verification."""

    L1 = "L1"
    """Direct measurement (process exit code, file existence)."""

    L2 = "L2"
    """Derived evidence (log analysis, hash comparison)."""

    L3 = "L3"
    """Synthetic/projection evidence — NOT accepted as authority."""


# ── Watchdog result ─────────────────────────────────────────────────────────


@dataclass(frozen=True)
class WatchdogResult:
    """Result of a watchdog-wrapped recovery check.

    Step 15B: A check that passes produces ``escalation=NONE``.
    Malformed output, absent child, fallback mismatch, missed events,
    and malformed L1/L2 evidence all produce ``escalation=BLOCKING``
    or ``escalation=CRITICAL``.
    """

    ok: bool
    """True if the check passed without durable failure."""

    check_name: str
    """Stable name for this watchdog check."""

    escalation: EscalationLevel
    """Escalation level if the check failed."""

    evidence_level: EvidenceLevel
    """What level of evidence was used."""

    detail: str = ""
    """Human-readable detail about the failure."""

    evidence: dict[str, Any] = field(default_factory=dict)
    """Structured evidence from the check."""

    child_present: bool = True
    """True if the monitored child process/artifact was present."""

    matched_expected: bool = True
    """True if the output matched expected structure."""

    maintenance_shadow: Optional[dict[str, Any]] = None
    """M2 read-only Maintenance shadow comparison (data only, never authority).

    When a coherent Maintenance envelope is available, the normalized legacy
    watchdog verdict is compared against it and the replayable comparison row
    (bucket, digests, denominators, diagnostics) is attached here.  This field
    never escalates, never launches repair, never dispatches, and never
    mutates any state; process/activity evidence is never treated as recovery.
    ``None`` when no Maintenance shadow was attached.
    """

    @property
    def requires_escalation(self) -> bool:
        return self.escalation in (
            EscalationLevel.BLOCKING,
            EscalationLevel.CRITICAL,
        )


def assess_watchdog_accepted_progress(
    projection: dict[str, Any],
    *,
    chain_complete: bool,
    is_fail_closed: bool,
    has_declared_successors: bool,
) -> dict[str, Any]:
    """Classify accepted progress and surface contradictory repair activity.

    Accepted milestone evidence is authoritative for progress classification;
    process/status activity is not.  If a completed fail-closed chain still
    advertises active repair state, return an explicit drift signal instead of
    allowing the watchdog projection to obscure accepted completion.
    """

    accepted = projection.get("accepted_progress")
    accepted_progress = (
        isinstance(accepted, dict)
        and accepted.get("acceptance_required") is True
        and accepted.get("waiting_for_acceptance") is False
        and (
            accepted.get("final_milestone_accepted") is True
            or bool(accepted.get("accepted_milestones"))
        )
    )
    repair_activity = (
        projection.get("status") in {"repairing", "reworking"}
        or projection.get("repairing") is True
        or (
            isinstance(projection.get("repair_state"), dict)
            and projection["repair_state"].get("active") is True
        )
    )
    contradictory_repair = (
        accepted_progress
        and repair_activity
        and chain_complete
        and is_fail_closed
        and has_declared_successors
    )

    return {
        "activity_classification": (
            "accepted_progress"
            if accepted_progress
            else "repair_activity"
            if repair_activity
            else "no_accepted_progress"
        ),
        "drift_detected": contradictory_repair,
        "drift_reason": (
            "accepted_progress_conflicts_with_repair_activity"
            if contradictory_repair
            else ""
        ),
    }


# ── P2 typed runtime transition absence reporting (read-only) ──────────────
#
# One typed deviation/fallback event path lives in the incident ledger
# (``<root>/.megaplan/incident-ledger/events.jsonl``).  Watchers NEVER become
# action authorities: the helpers below only READ the ledger and the runtime
# policy sidecar and report absence or drift — they never dispatch repair and
# never trigger a scan.  Absence reporting is the "watcher verifies absence"
# primitive: missing ``runtime.*`` events, invalid failure classes, chain-spec
# digest drift, and expired ``allow_manifestless`` permits are surfaced as
# structured findings, never silently assumed away.

_RUNTIME_EVENT_TYPES: tuple[str, ...] = (
    "runtime.manifest_selected",
    "runtime.deviation_declared",
    "runtime.fallback_considered",
    "runtime.fallback_taken",
    "runtime.fallback_rejected",
)


def _incident_ledger_events_path(ledger_root: Path | str) -> Path:
    return Path(ledger_root) / ".megaplan" / "incident-ledger" / "events.jsonl"


def iter_incident_runtime_events(ledger_root: Path | str) -> list[dict[str, Any]]:
    """Read-only: every incident-ledger event payload for the given root.

    Returns the ``payload`` dict of each journal envelope; a missing or
    unreadable ledger yields ``[]``.
    """
    path = _incident_ledger_events_path(ledger_root)
    if not path.exists():
        return []
    payloads: list[dict[str, Any]] = []
    try:
        for raw in path.read_text(encoding="utf-8").splitlines():
            raw = raw.strip()
            if not raw:
                continue
            try:
                envelope = json.loads(raw)
            except ValueError:
                continue
            payload = envelope.get("payload") if isinstance(envelope, dict) else None
            if isinstance(payload, dict):
                payloads.append(payload)
    except OSError:
        return []
    return payloads


def missing_runtime_events(
    *,
    ledger_root: Path | str,
    session_id: str,
    expected_events: tuple[str, ...] | None = None,
) -> list[str]:
    """Read-only: which ``runtime.*`` event types are absent for a session.

    Returns the subset of *expected_events* (default: all five runtime.*
    event types) that have no recorded event whose ``session_id`` matches.
    A session with dispatch evidence but no declared deviation/fallback trail
    is reported, never silently assumed.
    """
    expected = (
        tuple(expected_events)
        if expected_events is not None
        else _RUNTIME_EVENT_TYPES
    )
    observed = {
        str(payload.get("type") or "")
        for payload in iter_incident_runtime_events(ledger_root)
        if str(payload.get("session_id") or "") == session_id
    }
    return [event_type for event_type in expected if event_type not in observed]


def invalid_failure_class_events(*, ledger_root: Path | str) -> list[dict[str, Any]]:
    """Read-only: runtime.* events carrying an unknown ``failure_class``.

    Only the KNOWN failure classes (retryable availability/infrastructure,
    permanent auth/config/semantic/schema/test/evidence/execute) may appear;
    anything else is a typed-event-path violation.
    """
    from arnold_pipelines.megaplan.incident.ledger import KNOWN_FAILURE_CLASSES

    findings: list[dict[str, Any]] = []
    for payload in iter_incident_runtime_events(ledger_root):
        failure_class = payload.get("failure_class")
        if failure_class is None:
            continue
        if str(failure_class) not in KNOWN_FAILURE_CLASSES:
            findings.append(
                {
                    "kind": "invalid_failure_class",
                    "severity": "error",
                    "event_id": str(payload.get("event_id") or ""),
                    "type": str(payload.get("type") or ""),
                    "failure_class": str(failure_class),
                    "session_id": str(payload.get("session_id") or ""),
                    "detail": (
                        f"runtime event records unknown failure_class "
                        f"{failure_class!r}"
                    ),
                }
            )
    return findings


def manifest_digest_drift(
    *,
    spec_path: Path | str,
    ledger_root: Path | str,
    session_id: str = "",
) -> list[dict[str, Any]]:
    """Read-only: drift between the manifest-admission contract digest and the
    current chain spec.

    A runtime manifest is selected against a chain-spec contract digest
    (``chain_spec_sha256``, recorded on every deviation/fallback event).  If
    the chain spec has changed since those events were recorded, the recorded
    admission no longer matches the current chain — the drift is reported.
    """
    from arnold_pipelines.megaplan.chain.spec import chain_spec_sha256

    spec = Path(spec_path)
    if not spec.exists():
        return [
            {
                "kind": "chain_spec_missing",
                "severity": "error",
                "detail": f"chain spec missing at {spec}",
            }
        ]
    try:
        current_digest = chain_spec_sha256(spec)
    except OSError as exc:
        return [
            {
                "kind": "chain_spec_unreadable",
                "severity": "error",
                "detail": f"chain spec unreadable: {exc}",
            }
        ]
    recorded: list[str] = []
    for payload in iter_incident_runtime_events(ledger_root):
        if session_id and str(payload.get("session_id") or "") != session_id:
            continue
        digest = str(payload.get("chain_spec_sha256") or "")
        if digest:
            recorded.append(digest)
    if not recorded:
        return [
            {
                "kind": "manifest_digest_drift",
                "severity": "warn",
                "session_id": session_id,
                "detail": (
                    "no runtime event recorded a chain_spec_sha256 to compare "
                    "against the current chain spec"
                ),
            }
        ]
    drifting = [digest for digest in recorded if digest != current_digest]
    if drifting:
        return [
            {
                "kind": "manifest_digest_drift",
                "severity": "warn",
                "session_id": session_id,
                "detail": (
                    f"runtime events recorded chain_spec_sha256 that no longer "
                    f"matches the current chain spec ({current_digest}): "
                    f"{sorted(set(drifting))}"
                ),
            }
        ]
    return []


def expired_manifestless_permit(*, spec_path: Path | str) -> list[dict[str, Any]]:
    """Read-only: report the ``allow_manifestless`` permit state for a spec.

    Uses chain/spec.py's canonical permit resolution (sidecar path +
    ``active_allow_manifestless_permit``).  An absent sidecar or a currently
    inactive (expired/revoked/structurally invalid) permit is reported —
    absence of a valid permit must never silently admit (deny-by-default).
    """
    from arnold_pipelines.megaplan.chain.spec import (
        active_allow_manifestless_permit,
        runtime_policy_sidecar_path,
    )

    spec = Path(spec_path)
    if not spec.exists():
        return [
            {
                "kind": "chain_spec_missing",
                "severity": "error",
                "detail": f"chain spec missing at {spec}",
            }
        ]
    sidecar = runtime_policy_sidecar_path(spec)
    if not sidecar.exists():
        return [
            {
                "kind": "allow_manifestless_permit_missing",
                "severity": "warn",
                "detail": f"no .runtime_policy.json sidecar at {sidecar}",
            }
        ]
    active = active_allow_manifestless_permit(spec)
    if active is None:
        return [
            {
                "kind": "allow_manifestless_permit_expired",
                "severity": "warn",
                "detail": (
                    f"no active (unexpired, unrevoked) allow_manifestless permit "
                    f"in {sidecar}"
                ),
            }
        ]
    return []


def runtime_transition_absences(
    *,
    ledger_root: Path | str,
    session_id: str = "",
    spec_path: Path | str | None = None,
) -> list[dict[str, Any]]:
    """Read-only: aggregate runtime-transition absence reports.

    Combines missing ``runtime.*`` events for *session_id*, invalid failure
    classes, chain-spec digest drift, and expired ``allow_manifestless``
    permits into one list of structured findings.  Never writes; never
    dispatches.
    """
    findings: list[dict[str, Any]] = []
    if session_id:
        for event_type in missing_runtime_events(
            ledger_root=ledger_root, session_id=session_id
        ):
            findings.append(
                {
                    "kind": "missing_runtime_event",
                    "severity": "warn",
                    "session_id": session_id,
                    "event_type": event_type,
                    "detail": (
                        f"no runtime.{event_type.removeprefix('runtime.')} event "
                        f"recorded for session {session_id}"
                    ),
                }
            )
    findings.extend(invalid_failure_class_events(ledger_root=ledger_root))
    if spec_path is not None:
        findings.extend(
            manifest_digest_drift(
                spec_path=spec_path,
                ledger_root=ledger_root,
                session_id=session_id,
            )
        )
        findings.extend(expired_manifestless_permit(spec_path=spec_path))
    return findings


def record_observed_runtime_transition(
    transition_writer: Any | None,
    event_type: str,
    *,
    scope: str,
    failure_class: str,
    chain_spec_sha256: str,
    error: str,
    candidate_to: str | dict[str, Any] | None = None,
    candidate_from: str | dict[str, Any] | None = None,
    evidence: list[Any] | None = None,
    actor: str = "arnold-watchdog-seam",
    session_id: str = "",
) -> bool:
    """Best-effort append of an observed runtime transition.

    Read-only seams (watchdog wrappers, six-hour auditor) never act on their
    observations; this records what they observed as a typed runtime event
    BEFORE any caller side effect.  A failure to record is logged and reported
    as ``False`` — the observation verdict is never changed by a ledger write
    problem because these seams are not dispatch authorities.
    """
    if transition_writer is None:
        return False
    emit = {
        "deviation_declared": transition_writer.emit_deviation_declared,
        "fallback_considered": transition_writer.emit_fallback_considered,
        "fallback_taken": transition_writer.emit_fallback_taken,
        "fallback_rejected": transition_writer.emit_fallback_rejected,
    }[event_type]
    try:
        emit(
            scope=scope,
            failure_class=failure_class,
            chain_spec_sha256=chain_spec_sha256,
            candidate_from=candidate_from,
            candidate_to=candidate_to,
            error=error,
            evidence=evidence if evidence is not None else [],
            actor=actor,
            session_id=session_id,
        )
    except (ValueError, OSError) as exc:
        LOGGER.exception("Runtime transition %s not recorded: %s", event_type, exc)
        return False
    return True


# ── Watchdog wrapper ────────────────────────────────────────────────────────


def run_watchdog_check(
    *,
    check_name: str,
    check_fn: Callable[[], Any],
    expected_keys: tuple[str, ...] | None = None,
    child_path: str | None = None,
    timeout_seconds: float = 30.0,
    fallback_fn: Callable[[], Any] | None = None,
    transition_writer: Any | None = None,
    session_id: str = "",
    chain_spec_sha256: str = "",
    failure_class: str = "availability",
    actor: str = "arnold-watchdog-seam",
) -> WatchdogResult:
    """Step 15B: Wrap a recovery check in watchdog semantics.

    The wrapper converts failures into durable, typed escalations:

    - **Malformed output**: If the check returns output missing required
      ``expected_keys``, escalate to BLOCKING.
    - **Absent child**: If ``child_path`` is provided and the path does
      not exist, escalate to CRITICAL.
    - **Fallback mismatch**: If a ``fallback_fn`` is provided and its
      result contradicts the primary check, escalate to BLOCKING.
    - **Missed events**: If the check raises an exception, escalate to
      BLOCKING (never treat a running process as success).
    - **Malformed L1/L2 evidence**: If evidence is not a dict or is
      missing required fields, escalate to BLOCKING.

    P2 (optional): when a ``transition_writer`` (``RuntimeTransitionWriter``)
    is supplied, the observed deviation is recorded as a typed
    ``runtime.deviation_declared`` event (and ``runtime.fallback_rejected``
    when a supplied fallback contradicts the primary check) before the result
    is returned.  The recording is best-effort observation capture: this
    read-only seam never acts on its observations, so a ledger write problem
    only surfaces ``"runtime_transition_recorded": False`` in the evidence
    without changing the escalation verdict.

    Process presence alone is never treated as success.  The wrapper
    requires structured output.
    """
    start_time = time.monotonic()

    # Absent child check (Step 15B: CRITICAL escalation)
    if child_path is not None:
        import os
        if not os.path.exists(child_path):
            detail = f"Absent child: {child_path} does not exist"
            recorded = record_observed_runtime_transition(
                transition_writer,
                "deviation_declared",
                scope=f"watchdog:{check_name}",
                failure_class=failure_class,
                chain_spec_sha256=chain_spec_sha256,
                error=detail,
                candidate_to=child_path,
                evidence=[
                    {"check_name": check_name, "escalation": "critical"}
                ],
                actor=actor,
                session_id=session_id,
            )
            return WatchdogResult(
                ok=False,
                check_name=check_name,
                escalation=EscalationLevel.CRITICAL,
                evidence_level=EvidenceLevel.L1,
                detail=detail,
                evidence={
                    "child_path": child_path,
                    "check_name": check_name,
                    "elapsed_seconds": time.monotonic() - start_time,
                    "runtime_transition_recorded": recorded,
                },
                child_present=False,
                matched_expected=False,
            )

    # Run the primary check
    try:
        raw_output = check_fn()
    except Exception as exc:
        LOGGER.exception("Watchdog check %s raised exception", check_name)
        detail = f"Check raised {type(exc).__name__}: {exc}"
        recorded = record_observed_runtime_transition(
            transition_writer,
            "deviation_declared",
            scope=f"watchdog:{check_name}",
            failure_class=failure_class,
            chain_spec_sha256=chain_spec_sha256,
            error=detail,
            evidence=[
                {
                    "check_name": check_name,
                    "exception_type": type(exc).__name__,
                    "escalation": "blocking",
                }
            ],
            actor=actor,
            session_id=session_id,
        )
        return WatchdogResult(
            ok=False,
            check_name=check_name,
            escalation=EscalationLevel.BLOCKING,
            evidence_level=EvidenceLevel.L1,
            detail=detail,
            evidence={
                "exception_type": type(exc).__name__,
                "exception_message": str(exc),
                "check_name": check_name,
                "elapsed_seconds": time.monotonic() - start_time,
                "runtime_transition_recorded": recorded,
            },
            child_present=child_path is None,
            matched_expected=False,
        )

    elapsed = time.monotonic() - start_time

    # Timeout check
    if elapsed > timeout_seconds:
        LOGGER.warning(
            "Watchdog check %s exceeded timeout (%.1fs > %.1fs)",
            check_name, elapsed, timeout_seconds,
        )
        detail = f"Timeout: {elapsed:.1f}s > {timeout_seconds:.1f}s"
        recorded = record_observed_runtime_transition(
            transition_writer,
            "deviation_declared",
            scope=f"watchdog:{check_name}",
            failure_class=failure_class,
            chain_spec_sha256=chain_spec_sha256,
            error=detail,
            evidence=[
                {"check_name": check_name, "escalation": "blocking"}
            ],
            actor=actor,
            session_id=session_id,
        )
        return WatchdogResult(
            ok=False,
            check_name=check_name,
            escalation=EscalationLevel.BLOCKING,
            evidence_level=EvidenceLevel.L1,
            detail=detail,
            evidence={
                "elapsed_seconds": elapsed,
                "timeout_seconds": timeout_seconds,
                "check_name": check_name,
                "runtime_transition_recorded": recorded,
            },
            child_present=child_path is None,
            matched_expected=False,
        )

    # Malformed output check (Step 15B: missing expected keys)
    if expected_keys is not None:
        if not isinstance(raw_output, dict):
            detail = f"Malformed output: expected dict, got {type(raw_output).__name__}"
            recorded = record_observed_runtime_transition(
                transition_writer,
                "deviation_declared",
                scope=f"watchdog:{check_name}",
                failure_class=failure_class,
                chain_spec_sha256=chain_spec_sha256,
                error=detail,
                evidence=[
                    {"check_name": check_name, "escalation": "blocking"}
                ],
                actor=actor,
                session_id=session_id,
            )
            return WatchdogResult(
                ok=False,
                check_name=check_name,
                escalation=EscalationLevel.BLOCKING,
                evidence_level=EvidenceLevel.L1,
                detail=detail,
                evidence={
                    "raw_output_type": type(raw_output).__name__,
                    "expected_keys": list(expected_keys),
                    "elapsed_seconds": elapsed,
                    "runtime_transition_recorded": recorded,
                },
                child_present=child_path is None,
                matched_expected=False,
            )

        missing_keys = [k for k in expected_keys if k not in raw_output]
        if missing_keys:
            detail = f"Malformed output: missing keys {missing_keys}"
            recorded = record_observed_runtime_transition(
                transition_writer,
                "deviation_declared",
                scope=f"watchdog:{check_name}",
                failure_class=failure_class,
                chain_spec_sha256=chain_spec_sha256,
                error=detail,
                evidence=[
                    {"check_name": check_name, "escalation": "blocking"}
                ],
                actor=actor,
                session_id=session_id,
            )
            return WatchdogResult(
                ok=False,
                check_name=check_name,
                escalation=EscalationLevel.BLOCKING,
                evidence_level=EvidenceLevel.L2,
                detail=detail,
                evidence={
                    "missing_keys": missing_keys,
                    "expected_keys": list(expected_keys),
                    "available_keys": list(raw_output.keys()),
                    "elapsed_seconds": elapsed,
                    "runtime_transition_recorded": recorded,
                },
                child_present=child_path is None,
                matched_expected=False,
            )

    # Fallback mismatch check (Step 15B)
    if fallback_fn is not None:
        try:
            fallback_output = fallback_fn()
        except Exception as fallback_exc:
            LOGGER.warning(
                "Watchdog check %s fallback raised %s — treating as mismatch",
                check_name,
                type(fallback_exc).__name__,
            )
            detail = f"Fallback mismatch: fallback raised {type(fallback_exc).__name__}"
            recorded = record_observed_runtime_transition(
                transition_writer,
                "deviation_declared",
                scope=f"watchdog:{check_name}",
                failure_class=failure_class,
                chain_spec_sha256=chain_spec_sha256,
                error=detail,
                candidate_from=str(raw_output)[:500],
                evidence=[
                    {"check_name": check_name, "escalation": "blocking"}
                ],
                actor=actor,
                session_id=session_id,
            )
            rejected_recorded = record_observed_runtime_transition(
                transition_writer,
                "fallback_rejected",
                scope=f"watchdog:{check_name}",
                failure_class=failure_class,
                chain_spec_sha256=chain_spec_sha256,
                error=detail,
                candidate_from=str(raw_output)[:500],
                candidate_to="fallback_fn",
                evidence=[
                    {
                        "check_name": check_name,
                        "fallback_exception": str(fallback_exc),
                    }
                ],
                actor=actor,
                session_id=session_id,
            )
            return WatchdogResult(
                ok=False,
                check_name=check_name,
                escalation=EscalationLevel.BLOCKING,
                evidence_level=EvidenceLevel.L2,
                detail=detail,
                evidence={
                    "fallback_exception": str(fallback_exc),
                    "primary_output": str(raw_output)[:500],
                    "elapsed_seconds": elapsed,
                    "runtime_transition_recorded": recorded,
                    "runtime_fallback_rejection_recorded": rejected_recorded,
                },
                child_present=child_path is None,
                matched_expected=False,
            )

        # Canonical comparison: both must be dicts with matching key sets
        if isinstance(raw_output, dict) and isinstance(fallback_output, dict):
            primary_keys = set(raw_output.keys())
            fallback_keys = set(fallback_output.keys())
            if primary_keys != fallback_keys:
                detail = (
                    f"Fallback mismatch: primary keys {sorted(primary_keys)} "
                    f"!= fallback keys {sorted(fallback_keys)}"
                )
                recorded = record_observed_runtime_transition(
                    transition_writer,
                    "deviation_declared",
                    scope=f"watchdog:{check_name}",
                    failure_class=failure_class,
                    chain_spec_sha256=chain_spec_sha256,
                    error=detail,
                    candidate_from=str(raw_output)[:500],
                    evidence=[
                        {"check_name": check_name, "escalation": "blocking"}
                    ],
                    actor=actor,
                    session_id=session_id,
                )
                rejected_recorded = record_observed_runtime_transition(
                    transition_writer,
                    "fallback_rejected",
                    scope=f"watchdog:{check_name}",
                    failure_class=failure_class,
                    chain_spec_sha256=chain_spec_sha256,
                    error=detail,
                    candidate_from=str(raw_output)[:500],
                    candidate_to=str(fallback_output)[:500],
                    evidence=[
                        {
                            "check_name": check_name,
                            "primary_keys": sorted(primary_keys),
                            "fallback_keys": sorted(fallback_keys),
                        }
                    ],
                    actor=actor,
                    session_id=session_id,
                )
                return WatchdogResult(
                    ok=False,
                    check_name=check_name,
                    escalation=EscalationLevel.BLOCKING,
                    evidence_level=EvidenceLevel.L2,
                    detail=detail,
                    evidence={
                        "primary_keys": sorted(primary_keys),
                        "fallback_keys": sorted(fallback_keys),
                        "elapsed_seconds": elapsed,
                        "runtime_transition_recorded": recorded,
                        "runtime_fallback_rejection_recorded": rejected_recorded,
                    },
                    child_present=child_path is None,
                    matched_expected=False,
                )

    # Success
    return WatchdogResult(
        ok=True,
        check_name=check_name,
        escalation=EscalationLevel.NONE,
        evidence_level=EvidenceLevel.L1 if child_path is not None else EvidenceLevel.L2,
        detail="",
        evidence={
            "output": (
                raw_output if isinstance(raw_output, dict)
                else {"raw": str(raw_output)[:500]}
            ),
            "elapsed_seconds": elapsed,
        },
        child_present=child_path is None or True,
        matched_expected=True,
    )


# ──────────────────────────────────────────────────────────────────────────────
# M2 (T15): strict DetectionEvent references and Maintenance shadow comparison
# ──────────────────────────────────────────────────────────────────────────────
#
# These helpers attach a *read-only, replayable* Maintenance shadow comparison
# to a watchdog result.  They preserve every existing escalation and
# repair-launch outcome byte-for-behavior: the result's ``ok``/``escalation``/
# ``evidence_level``/``detail``/``child_present``/``matched_expected`` fields
# are never modified, the function never launches repair, never dispatches,
# and never mutates plan/chain/ledger truth beyond the explicit best-effort
# ledger append described below.  PID/tmux/activity/status evidence is never
# treated as recovery: the normalized legacy verdict derives ``green`` ONLY
# from the watchdog's own structured verdict (``ok`` and escalation), never
# from process presence or mutable status fields.


def watchdog_legacy_verdict(result: WatchdogResult) -> dict[str, bool]:
    """Return the normalized read-only legacy verdict for *result*.

    ``green`` is derived ONLY from the watchdog's structured verdict
    (``ok`` and escalation).  Process presence (``child_present``),
    ``matched_expected``, and raw output are observation data, never
    recovery evidence — they cannot turn a non-green verdict green.
    The watchdog never dispatches and never terminates on its own, so
    ``dispatchable`` and ``terminal`` are always ``False``.
    """
    return {
        "green": bool(result.ok) and not result.requires_escalation,
        "dispatchable": False,
        "terminal": False,
    }


def build_watchdog_detection_event(
    *,
    check_name: str,
    occurrence_id: str,
    event_id: Optional[str] = None,
    observed_at: Optional[Any] = None,
    event_time: Optional[Any] = None,
    window: Optional[Any] = None,
    watermark: Optional[Any] = None,
    severity: Optional[str] = None,
    description: Optional[str] = None,
    evidence_refs: tuple[Any, ...] = (),
    classifier_version: str = "watchdog-seam/1",
    confidence: Optional[float] = None,
    impact: Optional[str] = None,
    environment: Optional[str] = None,
    run: Optional[str] = None,
    chain: Optional[str] = None,
    plan: Optional[str] = None,
    stage: Optional[str] = None,
    max_attempts: int = 1,
) -> Any:
    """Build a strict Maintenance ``DetectionEvent`` for one watchdog detection.

    The payload is the closed :class:`DetectionEvent` (detection_kind,
    subject, severity, description, and locator-only immutable
    ``evidence_refs``) wrapped in the common strict ``MaintenanceEvent``
    envelope with occurrence-scoped identity (SD2: occurrence_id is the
    idempotency/lease/budget scope).  Defaults are deterministic:
    ``observed_at == event_time == now`` (UTC), the watermark is one second
    in the past (so the event is ON_TIME), and the window is the past hour
    containing the event time.  Owner payloads are never embedded — only
    immutable references (``OwnerRef``) may be passed as ``evidence_refs``.

    This function performs no I/O, no dispatch, and no mutation.
    """
    # Lazy import keeps the watchdog module import-light and avoids any
    # import cycle with the Maintenance package (same pattern as the
    # existing local imports of incident/chain modules above).
    from datetime import datetime, timedelta, timezone

    from arnold_pipelines.megaplan.maintenance.events import (
        ClassifierInfo,
        DetectionEvent,
        MaintenanceEvent,
        OccurrenceBudget,
        RootCauseCluster,
    )
    from arnold_pipelines.megaplan.maintenance.identity import (
        EventWindow,
        UtcTime,
        utc_now,
    )

    now = utc_now() if observed_at is None else observed_at
    if isinstance(now, datetime) and now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    instant = now
    if isinstance(instant, datetime) and instant.tzinfo is not None:
        instant = instant.astimezone(timezone.utc)
    effective_event_time = instant if event_time is None else event_time
    effective_watermark = (
        (instant - timedelta(seconds=1)) if watermark is None else watermark
    )
    effective_window = (
        EventWindow(
            start=UtcTime(instant - timedelta(hours=1)),
            end=UtcTime(instant + timedelta(seconds=1)),
        )
        if window is None
        else window
    )
    detection_kind = f"watchdog:{check_name}"
    return MaintenanceEvent.build(
        event_id=event_id or f"watchdog-{check_name}-{occurrence_id}",
        occurrence_id=occurrence_id,
        observed_at=now,
        event_time=effective_event_time,
        window=effective_window,
        watermark=effective_watermark,
        classifier=ClassifierInfo(
            classifier_version=classifier_version,
            confidence=confidence,
            impact=impact,
        ),
        cluster=RootCauseCluster(signature=detection_kind),
        budget=OccurrenceBudget(max_attempts=max_attempts),
        payload=DetectionEvent(
            detection_kind=detection_kind,
            subject=check_name,
            severity=severity,
            description=description,
            evidence_refs=tuple(evidence_refs),
        ),
        environment=environment,
        run=run,
        chain=chain,
        plan=plan,
        stage=stage,
    )


def attach_maintenance_shadow_to_result(
    result: WatchdogResult,
    *,
    envelope: Optional[Any] = None,
    ledger: Optional[Any] = None,
    detection_event: Optional[Any] = None,
    observed_at: Optional[Any] = None,
) -> WatchdogResult:
    """Attach a replayable Maintenance shadow comparison to *result*.

    * When ``envelope`` is ``None`` (no coherent capture available) the
      result is returned unchanged with ``maintenance_shadow=None`` — the
      legacy watchdog verdict and escalation path are untouched.
    * Otherwise the normalized legacy verdict is compared to the coherent
      envelope through the shared shadow comparator; the digest-stable
      comparison row is attached as data.  A non-eligible envelope
      (UNKNOWN/PARTIAL/INCOHERENT, stale, cross-environment, stale
      projection, or digest mismatch) can never yield a green/dispatchable/
      terminal shadow row — the discrepancy stays visible in the attached
      diagnostics and is never promoted.
    * When ``ledger`` is supplied, a strict ``DetectionEvent`` (built from
      the result, or passed as ``detection_event``) is appended to the
      Maintenance ledger best-effort.  An append failure surfaces a typed
      diagnostic (``append_status="failed"``) and never changes the
      escalation outcome, never launches repair, and never dispatches.

    The returned result is a new frozen :class:`WatchdogResult` carrying the
    same verdict fields as *result*; only ``maintenance_shadow`` differs.
    """
    if envelope is None:
        return result
    from arnold_pipelines.megaplan.maintenance.shadow import compare_shadow

    legacy = watchdog_legacy_verdict(result)
    comparison = compare_shadow(legacy, envelope)
    shadow: dict[str, Any] = {
        "schema_version": 1,
        "present": True,
        "envelope_digest": comparison.envelope_digest,
        "bucket": comparison.bucket.value,
        "reasons": list(comparison.reasons),
        "legacy_green": comparison.legacy_green,
        "green": comparison.green,
        "dispatchable": comparison.dispatchable,
        "terminal": comparison.terminal,
        "envelope_eligible": comparison.envelope_eligible,
        "envelope_green": comparison.envelope_green,
        "envelope_dispatchable": comparison.envelope_dispatchable,
        "envelope_terminal": comparison.envelope_terminal,
        "cross_environment": comparison.cross_environment,
        "comparison_digest": comparison.digest,
        "legacy_hash": comparison.legacy_hash,
        "denominator": comparison.denominator,
        "covered_count": comparison.covered_count,
        "coverage": comparison.coverage,
        "stale_projection": comparison.stale_projection,
        "digest_mismatch": comparison.digest_mismatch,
        "missing_denominator": comparison.missing_denominator,
        "detection_event_id": None,
        "detection_event_digest": None,
        "append_status": None,
        "diagnostics": [],
    }
    diagnostics: list[str] = []
    if not comparison.envelope_eligible:
        diagnostics.append(
            "envelope_not_eligible: maintenance evidence cannot promote "
            "watchdog recovery (process/activity/status evidence is never "
            "treated as recovery)"
        )
    if comparison.cross_environment:
        diagnostics.append("cross_environment_evidence")
    if comparison.stale_projection:
        diagnostics.append("stale_projection")
    if comparison.digest_mismatch:
        diagnostics.append("digest_mismatch")

    if ledger is not None:
        event = detection_event
        if event is None:
            event = build_watchdog_detection_event(
                check_name=result.check_name,
                occurrence_id=f"{result.check_name}:{result.detail or 'ok'}",
                observed_at=observed_at,
                severity=result.escalation.value,
                description=result.detail or None,
            )
        try:
            from arnold_pipelines.megaplan.maintenance.events import (
                event_digest,
            )

            ledger.append(event)
            shadow["detection_event_id"] = event.event_id
            shadow["detection_event_digest"] = event_digest(event)
            shadow["append_status"] = "appended"
        except Exception as exc:  # best-effort: never re-raise from shadow
            shadow["append_status"] = "failed"
            diagnostics.append(
                f"detection_append_failed:{type(exc).__name__}"
            )
            LOGGER.warning(
                "watchdog %s: Maintenance detection append failed (%s); "
                "escalation/repair-launch outcome unchanged",
                result.check_name,
                type(exc).__name__,
            )
    shadow["diagnostics"] = diagnostics
    return dataclasses_replace(
        result,
        maintenance_shadow=shadow,
    )


def dataclasses_replace(
    result: WatchdogResult, **changes: Any
) -> WatchdogResult:
    """Rebuild a frozen :class:`WatchdogResult` with only *changes* applied."""
    from dataclasses import replace

    return replace(result, **changes)


__all__ = [
    "EscalationLevel",
    "EvidenceLevel",
    "WatchdogResult",
    "assess_watchdog_accepted_progress",
    "attach_maintenance_shadow_to_result",
    "build_watchdog_detection_event",
    "expired_manifestless_permit",
    "invalid_failure_class_events",
    "iter_incident_runtime_events",
    "manifest_digest_drift",
    "missing_runtime_events",
    "record_observed_runtime_transition",
    "run_watchdog_check",
    "runtime_transition_absences",
    "watchdog_legacy_verdict",
]
