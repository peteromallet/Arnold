"""Step 22A-22B: Recovery SLO receipt and missed-event backstop tests.

Verifies that ``evidence/m10-recovery-slo-receipt.json``:
  - reports an eligible denominator and explicit exclusions,
  - records the p95 latency and the 300s SLO verdict,
  - emits a typed escalation when p95 exceeds the target,
  - captures the six-hour backstop reconciliation of a deliberately
    missed event without making the auditor a primary mutator.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.cloud.recovery_events import (
    RecoveryEvent,
    RecoveryEventKind,
    RecoveryEventStore,
)
from arnold_pipelines.megaplan.cloud.six_hour_auditor import (
    AuditSeverity,
    SixHourAuditor,
)
from tools.generate_m10_recovery_slo_receipt import (
    SLO_TARGET_SECONDS,
    generate_receipt,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
RECEIPT_PATH = REPO_ROOT / "evidence" / "m10-recovery-slo-receipt.json"


@pytest.fixture(scope="module")
def receipt() -> dict:
    """Generate (or re-read) the receipt once for the whole module."""
    receipt_data = generate_receipt()
    return receipt_data


# ── Step 22A: recovery SLO receipt ───────────────────────────────────────


class TestStep22ARecoverySloReceipt:
    def test_receipt_file_exists(self) -> None:
        assert RECEIPT_PATH.exists(), f"missing {RECEIPT_PATH}"

    def test_receipt_schema_version(self, receipt: dict) -> None:
        assert receipt["schema_version"] == 1
        assert receipt["step"] == "22A-22B"
        assert receipt["milestone"] == "M10"

    def test_slo_target_is_300_seconds(self, receipt: dict) -> None:
        assert receipt["slo_target_seconds"] == SLO_TARGET_SECONDS
        assert receipt["slo_target_seconds"] == 300.0

    def test_eligible_denominator_is_positive(self, receipt: dict) -> None:
        assert receipt["eligible_denominator"] > 0

    def test_exclusions_are_explicit(self, receipt: dict) -> None:
        exclusions = receipt["exclusions"]
        assert isinstance(exclusions, list)
        # The deliberately missed event must appear as an exclusion.
        missed = [e for e in exclusions if e["reason"] == "missed_event_no_request"]
        assert len(missed) == 1
        assert missed[0]["event_id"]

    def test_occurrence_ids_are_present(self, receipt: dict) -> None:
        ids = receipt["occurrence_ids"]
        assert isinstance(ids, list)
        assert len(ids) >= 2  # at least one eligible and one missed
        assert len(set(ids)) == len(ids), "occurrence IDs must be unique"

    def test_p95_is_computed(self, receipt: dict) -> None:
        assert receipt["p95_seconds"] is not None
        assert receipt["p95_seconds"] > 0

    def test_p95_matches_latencies(self, receipt: dict) -> None:
        latencies = sorted(receipt["latencies_seconds"])
        idx = int(len(latencies) * 0.95)
        expected = latencies[min(idx, len(latencies) - 1)]
        assert receipt["p95_seconds"] == pytest.approx(expected)

    def test_slo_met_flag_matches_p95(self, receipt: dict) -> None:
        p95 = receipt["p95_seconds"]
        assert receipt["slo_met"] == (p95 <= SLO_TARGET_SECONDS)

    def test_typed_escalation_when_slo_exceeded(self, receipt: dict) -> None:
        # The scenario deliberately includes a slow event exceeding 300s.
        assert receipt["slo_exceeded_count"] >= 1
        esc = receipt["typed_escalation"]
        assert esc["required"] is True
        assert "exceeds target" in esc["reason"]

    def test_slo_exceeded_event_ids_are_recorded(self, receipt: dict) -> None:
        ids = receipt["slo_exceeded_event_ids"]
        assert isinstance(ids, list)
        assert len(ids) == receipt["slo_exceeded_count"]

    def test_content_hash_is_stable(self, receipt: dict) -> None:
        payload = {k: v for k, v in receipt.items() if k != "content_hash"}
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        import hashlib
        expected = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        assert receipt["content_hash"] == expected


# ── Step 22B: missed-event backstop ──────────────────────────────────────


class TestStep22BMissedEventBackstop:
    def test_backstop_section_present(self, receipt: dict) -> None:
        assert "six_hour_backstop" in receipt

    def test_backstop_detected_missed_event(self, receipt: dict) -> None:
        backstop = receipt["six_hour_backstop"]
        missed = backstop["missed_event_findings"]
        assert len(missed) >= 1
        finding = missed[0]
        assert finding["severity"] in (
            AuditSeverity.DEGRADED.value,
            AuditSeverity.FAILED.value,
        )
        assert "no repair request" in finding["detail"].lower() or "missed" in finding["detail"].lower()

    def test_backstop_recorded_slo_violations(self, receipt: dict) -> None:
        backstop = receipt["six_hour_backstop"]
        slo_findings = backstop["slo_violation_findings"]
        assert len(slo_findings) >= 1

    def test_auditor_is_not_primary_mutator(self, receipt: dict) -> None:
        backstop = receipt["six_hour_backstop"]
        assert backstop["primary_mutator_invoked"] is False
        assert receipt["constraints"]["auditor_is_primary_mutator"] is False

    def test_auditor_escalated_findings(self, receipt: dict) -> None:
        backstop = receipt["six_hour_backstop"]
        assert backstop["escalated_count"] >= 1
        escalations = backstop["escalations"]
        assert len(escalations) == backstop["escalated_count"]
        for esc in escalations:
            assert esc["severity"] in (
                AuditSeverity.DEGRADED.value,
                AuditSeverity.FAILED.value,
            )

    def test_production_effects_action_off(self, receipt: dict) -> None:
        assert receipt["constraints"]["production_effects_action_off"] is True


# ── Direct store/auditor behavior ────────────────────────────────────────


class TestRecoverySloStoreBehavior:
    def test_store_p95_below_target_when_all_fast(self) -> None:
        from datetime import datetime, timedelta, timezone
        now = datetime.now(timezone.utc)
        store = RecoveryEventStore()
        for i in range(5):
            occurred = now - timedelta(seconds=200)
            terminal = occurred + timedelta(seconds=60 + i)
            store.record(RecoveryEvent(
                event_id=f"ev-fast-{i}",
                kind=RecoveryEventKind.BLOCKER_DETECTED,
                occurred_at=occurred.isoformat(),
                recorded_at=occurred.isoformat(),
                request_id=f"r-{i}",
                terminal_time=terminal.isoformat(),
                denominator_group="parser",
            ))
        p95 = store.p95_latency()
        assert p95 is not None
        assert p95 <= SLO_TARGET_SECONDS

    def test_store_p95_exceeds_target_with_slow_event(self) -> None:
        from datetime import datetime, timedelta, timezone
        now = datetime.now(timezone.utc)
        store = RecoveryEventStore()
        occurred = now - timedelta(seconds=900)
        terminal = occurred + timedelta(seconds=420)
        store.record(RecoveryEvent(
            event_id="ev-slow",
            kind=RecoveryEventKind.BLOCKER_DETECTED,
            occurred_at=occurred.isoformat(),
            recorded_at=occurred.isoformat(),
            request_id="r-slow",
            terminal_time=terminal.isoformat(),
            denominator_group="parser",
        ))
        p95 = store.p95_latency()
        assert p95 is not None
        assert p95 > SLO_TARGET_SECONDS
        violations = store.slo_violations(target_seconds=SLO_TARGET_SECONDS)
        assert len(violations) == 1

    def test_auditor_detects_unlinked_blocker_as_missed(self) -> None:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        store = RecoveryEventStore()
        store.record(RecoveryEvent(
            event_id="blk-orphan",
            kind=RecoveryEventKind.BLOCKER_DETECTED,
            occurred_at=now.isoformat(),
            recorded_at=now.isoformat(),
            request_id="",  # no request — missed
            denominator_group="parser",
        ))
        auditor = SixHourAuditor(
            event_store=store,
            repair_request_provider=lambda: [],
            now_fn=lambda: now,
        )
        report = auditor.run_audit()
        missed = [f for f in report.findings if f.category == "missed_event"]
        assert len(missed) == 1
        assert missed[0].severity == AuditSeverity.DEGRADED

    def test_auditor_does_not_mutate_on_detection(self) -> None:
        """The auditor must not enqueue repair requests or otherwise mutate."""
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        store = RecoveryEventStore()
        store.record(RecoveryEvent(
            event_id="blk-orphan-2",
            kind=RecoveryEventKind.BLOCKER_DETECTED,
            occurred_at=now.isoformat(),
            recorded_at=now.isoformat(),
            request_id="",
            denominator_group="parser",
        ))
        requests_before: list[dict] = []
        auditor = SixHourAuditor(
            event_store=store,
            repair_request_provider=lambda: list(requests_before),
            now_fn=lambda: now,
        )
        report = auditor.run_audit()
        # No new requests should be added by the auditor.
        assert requests_before == []
        # Event store should be unchanged.
        assert len(store.all_events()) == 1
        assert report.escalated_count >= 1
