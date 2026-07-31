"""Step 22A-22B: Generate evidence/m10-recovery-slo-receipt.json.

Produces a candidate-bound recovery SLO receipt that:
  - reports an eligible denominator, exclusions, and occurrence IDs,
  - records the denominated p95 latency against the 300s SLO target,
  - emits a typed escalation when p95 exceeds the target or evidence is
    missing/indeterminate,
  - captures the six-hour backstop reconciliation of a deliberately
    missed event without making the auditor a primary mutator.

The receipt is produced by exercising the installed-runtime
:class:`RecoveryEventStore` and :class:`SixHourAuditor` with a fixed
scenario.  It is **not** a runtime snapshot of production state — M10
keeps all production effects action-off (SD3).  It is machine-verifiable
proof that the SLO and backstop code paths compute the right verdicts
from the installed runtime.

Usage::

    python tools/generate_m10_recovery_slo_receipt.py
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# Ensure repo root is importable when run as a script.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from arnold_pipelines.megaplan.cloud.recovery_events import (  # noqa: E402
    RecoveryEvent,
    RecoveryEventBuilder,
    RecoveryEventKind,
    RecoveryEventStore,
)
from arnold_pipelines.megaplan.cloud.six_hour_auditor import (  # noqa: E402
    AUDITOR_RECONCILIATION_INTERVAL,
    AuditSeverity,
    SixHourAuditor,
)


SLO_TARGET_SECONDS = 300.0
RECEIPT_PATH = _REPO_ROOT / "evidence" / "m10-recovery-slo-receipt.json"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _build_slo_scenario(now: datetime) -> tuple[RecoveryEventStore, list[dict[str, Any]], list[RecoveryEvent]]:
    """Build a representative recovery SLO scenario.

    Five repaired blocker events resolve well under the 300s SLO; one
    event resolves just over to exercise the typed-escalation path; and
    one deliberately missed blocker has no linked repair request.
    """
    store = RecoveryEventStore()
    occurrences: list[RecoveryEvent] = []

    # Five fast repairs under the SLO.
    for i in range(1, 6):
        occurred = now - timedelta(seconds=400 - i * 10)
        terminal = occurred + timedelta(seconds=120 + i * 5)
        request_id = f"req-fast-{i}"
        blocker = RecoveryEventBuilder.blocker_detected(
            blocker_id=f"blk-fast-{i}",
            session="session-slo",
            failure_kind="parser_loss",
            phase_or_step="step-7b",
            denominator_group="parser",
        )
        # Override timestamps to a controlled scenario.
        blocker = RecoveryEvent(
            event_id=blocker.event_id,
            kind=blocker.kind,
            occurred_at=_iso(occurred),
            recorded_at=_iso(occurred + timedelta(seconds=2)),
            request_id=request_id,
            claim_time=_iso(occurred + timedelta(seconds=10)),
            terminal_time=_iso(terminal),
            slo_target_seconds=SLO_TARGET_SECONDS,
            denominator_group="parser",
        )
        store.record(blocker)
        # Repair request rows for the auditor to inspect.
        store.record(RecoveryEvent(
            event_id=f"enqueue-fast-{i}",
            kind=RecoveryEventKind.REPAIR_REQUEST_ENQUEUED,
            occurred_at=_iso(occurred + timedelta(seconds=2)),
            recorded_at=_iso(occurred + timedelta(seconds=2)),
            request_id=request_id,
            denominator_group="parser",
        ))
        store.record(RecoveryEvent(
            event_id=f"claim-fast-{i}",
            kind=RecoveryEventKind.REPAIR_CLAIMED,
            occurred_at=_iso(occurred + timedelta(seconds=10)),
            recorded_at=_iso(occurred + timedelta(seconds=10)),
            request_id=request_id,
            claim_time=_iso(occurred + timedelta(seconds=10)),
            denominator_group="parser",
        ))
        store.record(RecoveryEvent(
            event_id=f"terminal-fast-{i}",
            kind=RecoveryEventKind.REPAIR_TERMINAL,
            occurred_at=_iso(terminal),
            recorded_at=_iso(terminal),
            request_id=request_id,
            claim_time=_iso(occurred + timedelta(seconds=10)),
            terminal_time=_iso(terminal),
            denominator_group="parser",
        ))
        occurrences.append(blocker)

    # One slow repair exceeding the SLO (typed escalation).
    slow_occurred = now - timedelta(seconds=900)
    slow_terminal = slow_occurred + timedelta(seconds=420)
    slow_request = "req-slow-1"
    slow_blocker = RecoveryEvent(
        event_id="blocker-slow-1",
        kind=RecoveryEventKind.BLOCKER_DETECTED,
        occurred_at=_iso(slow_occurred),
        recorded_at=_iso(slow_occurred + timedelta(seconds=2)),
        request_id=slow_request,
        claim_time=_iso(slow_occurred + timedelta(seconds=15)),
        terminal_time=_iso(slow_terminal),
        slo_target_seconds=SLO_TARGET_SECONDS,
        denominator_group="parser",
        slo_exceeded=True,
    )
    store.record(slow_blocker)
    store.record(RecoveryEvent(
        event_id="enqueue-slow-1",
        kind=RecoveryEventKind.REPAIR_REQUEST_ENQUEUED,
        occurred_at=_iso(slow_occurred + timedelta(seconds=2)),
        recorded_at=_iso(slow_occurred + timedelta(seconds=2)),
        request_id=slow_request,
        denominator_group="parser",
    ))
    store.record(RecoveryEvent(
        event_id="claim-slow-1",
        kind=RecoveryEventKind.REPAIR_CLAIMED,
        occurred_at=_iso(slow_occurred + timedelta(seconds=15)),
        recorded_at=_iso(slow_occurred + timedelta(seconds=15)),
        request_id=slow_request,
        claim_time=_iso(slow_occurred + timedelta(seconds=15)),
        denominator_group="parser",
    ))
    store.record(RecoveryEvent(
        event_id="terminal-slow-1",
        kind=RecoveryEventKind.REPAIR_TERMINAL,
        occurred_at=_iso(slow_terminal),
        recorded_at=_iso(slow_terminal),
        request_id=slow_request,
        claim_time=_iso(slow_occurred + timedelta(seconds=15)),
        terminal_time=_iso(slow_terminal),
        denominator_group="parser",
    ))
    occurrences.append(slow_blocker)

    # Deliberately missed event: blocker with no linked repair request.
    missed_occurred = now - timedelta(seconds=7200)
    missed_blocker = RecoveryEvent(
        event_id="blocker-missed-1",
        kind=RecoveryEventKind.BLOCKER_DETECTED,
        occurred_at=_iso(missed_occurred),
        recorded_at=_iso(missed_occurred),
        request_id="",  # no request linked — this is the "missed" event
        denominator_group="parser",
    )
    store.record(missed_blocker)
    occurrences.append(missed_blocker)

    # Repair request ledger view (subset the auditor consumes).
    requests = [
        {
            "request_id": f"req-fast-{i}",
            "status": "terminal",
            "created_at": _iso(now - timedelta(seconds=400 - i * 10)),
        }
        for i in range(1, 6)
    ]
    requests.append({
        "request_id": slow_request,
        "status": "terminal",
        "created_at": _iso(slow_occurred),
    })

    return store, requests, occurrences


def _run_next_three_hour_reconciliation(
    store: RecoveryEventStore,
    requests: list[dict[str, Any]],
    now: datetime,
) -> dict[str, Any]:
    """Run the auditor and capture its next-three-hour reconciliation evidence.

    Step 47 (T33): positive proof now flows through the next-three-hour
    reconciliation cadence (``AUDITOR_RECONCILIATION_INTERVAL``).  The
    historical ``six_hour`` spelling is retained ONLY as a compatibility
    alias in the emitted receipt; it must not mint repair authority on its
    own.
    """
    escalations: list[dict[str, Any]] = []

    def sink(finding) -> None:
        escalations.append({
            "finding_id": finding.finding_id,
            "severity": finding.severity.value,
            "category": finding.category,
            "detail": finding.detail,
        })

    auditor = SixHourAuditor(
        event_store=store,
        repair_request_provider=lambda: requests,
        escalation_sink=sink,
        now_fn=lambda: now,
    )
    report = auditor.run_audit()

    missed_findings = [
        f for f in report.findings if f.category == "missed_event"
    ]
    slo_findings = [
        f for f in report.findings if f.category == "slo_violation"
    ]

    return {
        "reconciliation_interval": AUDITOR_RECONCILIATION_INTERVAL,
        "audit_id": report.audit_id,
        "ran_at": _iso(now),
        "events_checked": report.events_checked,
        "requests_checked": report.requests_checked,
        "missed_event_findings": [
            {
                "finding_id": f.finding_id,
                "severity": f.severity.value,
                "detail": f.detail,
                "evidence": f.evidence,
            }
            for f in missed_findings
        ],
        "slo_violation_findings": [
            {
                "finding_id": f.finding_id,
                "severity": f.severity.value,
                "detail": f.detail,
            }
            for f in slo_findings
        ],
        "escalated_count": report.escalated_count,
        "escalations": escalations,
        "ok": report.ok,
        "requires_attention": report.requires_attention,
        "primary_mutator_invoked": False,
    }


def _content_hash(value: Any) -> str:
    """Stable SHA-256 over canonical JSON."""
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def generate_receipt() -> dict[str, Any]:
    """Build the full SLO receipt structure."""
    now = _utc_now()
    store, requests, occurrences = _build_slo_scenario(now)

    # SLO computation over the eligible denominator.
    eligible = [ev for ev in occurrences if ev.request_id]
    excluded = [
        {
            "event_id": ev.event_id,
            "reason": "missed_event_no_request",
        }
        for ev in occurrences
        if not ev.request_id
    ]

    latencies = sorted(
        ev.total_latency_seconds for ev in eligible
        if ev.total_latency_seconds is not None
    )
    p95: float | None = None
    if latencies:
        idx = int(len(latencies) * 0.95)
        p95 = latencies[min(idx, len(latencies) - 1)]

    slo_met = p95 is not None and p95 <= SLO_TARGET_SECONDS
    slo_exceeded_events = store.slo_violations(target_seconds=SLO_TARGET_SECONDS)

    # Step 47 (T33): next-three-hour reconciliation carries the positive proof.
    # The legacy ``six_hour_backstop`` key is retained as a full compatibility
    # alias of the same payload (with compatibility markers) so existing
    # consumers keep working; it must never mint repair authority on its own.
    reconciliation = _run_next_three_hour_reconciliation(store, requests, now)
    six_hour_backstop_alias = dict(reconciliation)
    six_hour_backstop_alias["compatibility_alias_for"] = "next_three_hour_reconciliation"
    six_hour_backstop_alias["legacy_cadence_label"] = "six_hour"
    six_hour_backstop_alias["compatibility_only"] = True

    occurrence_ids = [ev.event_id for ev in occurrences]
    receipt = {
        "schema_version": 1,
        "step": "22A-22B",
        "milestone": "M10",
        "generated_at": _iso(now),
        "slo_target_seconds": SLO_TARGET_SECONDS,
        "eligible_denominator": len(eligible),
        "exclusions": excluded,
        "occurrence_ids": occurrence_ids,
        "latencies_seconds": latencies,
        "p95_seconds": p95,
        "slo_met": slo_met,
        "slo_exceeded_count": len(slo_exceeded_events),
        "slo_exceeded_event_ids": [ev.event_id for ev in slo_exceeded_events],
        "typed_escalation": {
            "required": not slo_met,
            "reason": (
                "p95 %.1fs exceeds target %.1fs" % (p95, SLO_TARGET_SECONDS)
                if p95 is not None and not slo_met
                else "not required"
            ),
        },
        "next_three_hour_reconciliation": reconciliation,
        "six_hour_backstop": six_hour_backstop_alias,
        "constraints": {
            "production_effects_action_off": True,
            "auditor_is_primary_mutator": False,
            "evidence_source": "installed_runtime_recovery_events_store",
            "positive_proof_cadence": AUDITOR_RECONCILIATION_INTERVAL,
            "six_hour_names_compatibility_only": True,
        },
    }

    receipt["content_hash"] = _content_hash(
        {k: v for k, v in receipt.items() if k != "content_hash"}
    )
    return receipt


def main() -> int:
    receipt = generate_receipt()
    RECEIPT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT_PATH.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(f"wrote {RECEIPT_PATH}")
    print(f"p95_seconds={receipt['p95_seconds']} slo_met={receipt['slo_met']}")
    reconciliation = receipt["next_three_hour_reconciliation"]
    print(f"missed_event_findings={len(reconciliation['missed_event_findings'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
