"""Tests for Steps 15B-15C: Watchdog wrapper and six-hour auditor.

Covers:
- run_watchdog_check: malformed output, absent child, fallback mismatch,
  missed events, timeout
- SixHourAuditor: all nine audit checks, escalation
- Durable failures and typed escalation without primary mutation
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from arnold_pipelines.megaplan.cloud.watchdog import (
    EscalationLevel,
    EvidenceLevel,
    WatchdogResult,
    run_watchdog_check,
)
from arnold_pipelines.megaplan.cloud.six_hour_auditor import (
    AuditSeverity,
    AuditFinding,
    SixHourAuditReport,
    SixHourAuditor,
    SIX_HOURS_SECONDS,
)
from arnold_pipelines.megaplan.cloud.recovery_events import (
    RecoveryEventKind,
    RecoveryEvent,
    RecoveryEventStore,
    RecoveryEventBuilder,
)


# ── Watchdog: malformed output ───────────────────────────────────────────────


def test_watchdog_malformed_output_non_dict():
    """Non-dict output with expected_keys is malformed."""
    result = run_watchdog_check(
        check_name="test-malformed",
        check_fn=lambda: "not a dict",
        expected_keys=("status", "result"),
    )
    assert not result.ok
    assert result.escalation == EscalationLevel.BLOCKING
    assert "malformed" in result.detail.lower()


def test_watchdog_missing_expected_keys():
    """Output missing expected keys is malformed."""
    result = run_watchdog_check(
        check_name="test-missing-keys",
        check_fn=lambda: {"status": "ok"},
        expected_keys=("status", "result", "evidence"),
    )
    assert not result.ok
    assert result.escalation == EscalationLevel.BLOCKING
    assert "missing keys" in result.detail.lower()


def test_watchdog_all_expected_keys_present():
    """Output with all expected keys passes."""
    result = run_watchdog_check(
        check_name="test-ok",
        check_fn=lambda: {"status": "ok", "result": "done", "evidence": {}},
        expected_keys=("status", "result", "evidence"),
    )
    assert result.ok
    assert result.escalation == EscalationLevel.NONE


# ── Watchdog: absent child ───────────────────────────────────────────────────


def test_watchdog_absent_child(tmp_path):
    """Absent child path triggers CRITICAL escalation."""
    missing_path = tmp_path / "nonexistent" / "child.pid"
    result = run_watchdog_check(
        check_name="test-absent-child",
        check_fn=lambda: {"status": "ok"},
        child_path=str(missing_path),
    )
    assert not result.ok
    assert result.escalation == EscalationLevel.CRITICAL
    assert "Absent child" in result.detail
    assert not result.child_present


def test_watchdog_present_child(tmp_path):
    """Present child path passes the child check."""
    child = tmp_path / "present.txt"
    child.write_text("ok")
    result = run_watchdog_check(
        check_name="test-present-child",
        check_fn=lambda: {"status": "ok"},
        child_path=str(child),
        expected_keys=("status",),
    )
    assert result.ok


# ── Watchdog: fallback mismatch ──────────────────────────────────────────────


def test_watchdog_fallback_mismatch_different_keys():
    """Fallback output with different keys triggers BLOCKING."""
    result = run_watchdog_check(
        check_name="test-fallback-mismatch",
        check_fn=lambda: {"status": "ok", "value": 1},
        fallback_fn=lambda: {"status": "ok", "other": 2},
        expected_keys=("status",),
    )
    assert not result.ok
    assert result.escalation == EscalationLevel.BLOCKING
    assert "Fallback mismatch" in result.detail


def test_watchdog_fallback_match():
    """Matching fallback output passes."""
    result = run_watchdog_check(
        check_name="test-fallback-match",
        check_fn=lambda: {"status": "ok", "value": 1},
        fallback_fn=lambda: {"status": "ok", "value": 1},
    )
    assert result.ok


def test_watchdog_fallback_raises():
    """Fallback that raises is treated as mismatch."""
    def failing_fallback():
        raise RuntimeError("fallback crashed")

    result = run_watchdog_check(
        check_name="test-fallback-crash",
        check_fn=lambda: {"status": "ok"},
        fallback_fn=failing_fallback,
    )
    assert not result.ok
    assert result.escalation == EscalationLevel.BLOCKING


# ── Watchdog: exception handling ─────────────────────────────────────────────


def test_watchdog_check_raises():
    """Check that raises produces BLOCKING escalation."""
    def crashing_check():
        raise ValueError("check failure")

    result = run_watchdog_check(
        check_name="test-crash",
        check_fn=crashing_check,
    )
    assert not result.ok
    assert result.escalation == EscalationLevel.BLOCKING
    assert "ValueError" in result.detail


# ── Watchdog: timeout ────────────────────────────────────────────────────────


def test_watchdog_timeout():
    """Check that exceeds timeout produces BLOCKING."""
    import time
    def slow_check():
        time.sleep(0.2)
        return {"status": "ok"}

    result = run_watchdog_check(
        check_name="test-timeout",
        check_fn=slow_check,
        timeout_seconds=0.05,
    )
    assert not result.ok
    assert result.escalation == EscalationLevel.BLOCKING
    assert "Timeout" in result.detail


# ── Watchdog: success ────────────────────────────────────────────────────────


def test_watchdog_success_no_expected_keys():
    """Check with no expected_keys requirement passes."""
    result = run_watchdog_check(
        check_name="test-simple",
        check_fn=lambda: {"any": "output"},
    )
    assert result.ok
    assert result.escalation == EscalationLevel.NONE


def test_watchdog_result_requires_escalation():
    """WatchdogResult.requires_escalation is True for BLOCKING/CRITICAL."""
    ok_result = WatchdogResult(
        ok=True, check_name="t", escalation=EscalationLevel.NONE,
        evidence_level=EvidenceLevel.L1,
    )
    assert not ok_result.requires_escalation

    blocking_result = WatchdogResult(
        ok=False, check_name="t", escalation=EscalationLevel.BLOCKING,
        evidence_level=EvidenceLevel.L1, child_present=False,
    )
    assert blocking_result.requires_escalation


# ── SixHourAuditor: missed events ────────────────────────────────────────────


def test_auditor_detects_missed_blocker_events():
    """Blocker events without linked requests are detected."""
    store = RecoveryEventStore()
    event = RecoveryEventBuilder.blocker_detected(
        blocker_id="blk-1", session="s1", failure_kind="crash",
    )
    store.record(event)

    auditor = SixHourAuditor(event_store=store)
    report = auditor.run_audit()

    # Should have at least one finding for the missed blocker event
    missed = [f for f in report.findings if f.category == "missed_event"]
    assert len(missed) >= 1


def test_auditor_detects_parser_loss():
    """Parser loss events are detected as FAILED."""
    store = RecoveryEventStore()
    event = RecoveryEventBuilder.parser_loss(
        session="s1", phase_or_step="parse", detail="no output",
    )
    store.record(event)

    auditor = SixHourAuditor(event_store=store)
    report = auditor.run_audit()

    parser_findings = [f for f in report.findings if f.category == "parser_loss"]
    assert len(parser_findings) >= 1
    assert parser_findings[0].severity == AuditSeverity.FAILED


def test_auditor_detects_classification_incompatibility():
    """Classification incompatibility events are FAILED."""
    store = RecoveryEventStore()
    event = RecoveryEventBuilder.classification_incompatible(
        session="s1", expected_schema="v2", observed="v1",
    )
    store.record(event)

    auditor = SixHourAuditor(event_store=store)
    report = auditor.run_audit()

    class_findings = [f for f in report.findings if f.category == "classification_incompatible"]
    assert len(class_findings) >= 1
    assert class_findings[0].severity == AuditSeverity.FAILED


def test_auditor_detects_launcher_failure():
    """Launcher failure events are FAILED."""
    store = RecoveryEventStore()
    event = RecoveryEventBuilder.launcher_failure(
        session="s1", launcher_name="codex", exit_code=1,
    )
    store.record(event)

    auditor = SixHourAuditor(event_store=store)
    report = auditor.run_audit()

    launcher_findings = [f for f in report.findings if f.category == "launcher_failure"]
    assert len(launcher_findings) >= 1
    assert launcher_findings[0].severity == AuditSeverity.FAILED


def test_auditor_detects_missing_children():
    """Missing child events with still-absent children are FAILED."""
    store = RecoveryEventStore()
    event = RecoveryEventBuilder.missing_child(
        session="s1", child_id="worker-1", expected_path="/tmp/child.pid",
    )
    store.record(event)

    auditor = SixHourAuditor(
        event_store=store,
        child_presence_check=lambda p: False,  # still absent
    )
    report = auditor.run_audit()

    child_findings = [f for f in report.findings if f.category == "missing_child"]
    assert len(child_findings) >= 1
    assert child_findings[0].severity == AuditSeverity.FAILED


def test_auditor_recovered_child_is_anomaly():
    """Previously missing child that reappeared is downgraded to ANOMALY."""
    store = RecoveryEventStore()
    event = RecoveryEventBuilder.missing_child(
        session="s1", child_id="worker-2", expected_path="/tmp/recovered.pid",
    )
    store.record(event)

    auditor = SixHourAuditor(
        event_store=store,
        child_presence_check=lambda p: True,  # reappeared
    )
    report = auditor.run_audit()

    child_findings = [f for f in report.findings if f.category == "missing_child"]
    assert len(child_findings) >= 1
    assert child_findings[0].severity == AuditSeverity.ANOMALY


# ── SixHourAuditor: malformed evidence ───────────────────────────────────────


def test_auditor_detects_non_dict_evidence():
    """Non-dict evidence is FAILED."""
    store = RecoveryEventStore()
    # Create an event with non-dict metadata (simulate)
    event = RecoveryEvent(
        event_id="bad-ev-1",
        kind=RecoveryEventKind.BLOCKER_DETECTED,
        occurred_at="2024-01-01T00:00:00+00:00",
        recorded_at="2024-01-01T00:00:00+00:00",
        metadata="not a dict",  # type: ignore
    )
    store.record(event)

    auditor = SixHourAuditor(event_store=store)
    report = auditor.run_audit()

    evidence_findings = [f for f in report.findings if f.category == "malformed_evidence"]
    assert len(evidence_findings) >= 1


def test_auditor_detects_empty_evidence():
    """Empty evidence dict is DEGRADED."""
    store = RecoveryEventStore()
    event = RecoveryEvent(
        event_id="empty-ev-1",
        kind=RecoveryEventKind.BLOCKER_DETECTED,
        occurred_at="2024-01-01T00:00:00+00:00",
        recorded_at="2024-01-01T00:00:00+00:00",
        metadata={},
    )
    store.record(event)

    auditor = SixHourAuditor(event_store=store)
    report = auditor.run_audit()

    evidence_findings = [f for f in report.findings if f.category == "malformed_evidence"]
    assert len(evidence_findings) >= 1
    assert evidence_findings[0].severity == AuditSeverity.DEGRADED


# ── SixHourAuditor: SLO violations ───────────────────────────────────────────


def test_auditor_detects_slo_violations():
    """SLO violations are detected."""
    store = RecoveryEventStore()
    event = RecoveryEvent(
        event_id="slo-ev-1",
        kind=RecoveryEventKind.REPAIR_TERMINAL,
        occurred_at="2024-01-01T00:00:00+00:00",
        recorded_at="2024-01-01T00:10:00+00:00",  # 10 minutes > 300s target
        request_id="req-1",
        terminal_time="2024-01-01T00:10:00+00:00",
        slo_exceeded=True,
        denominator_group="test",
    )
    store.record(event)

    auditor = SixHourAuditor(event_store=store)
    report = auditor.run_audit()

    slo_findings = [f for f in report.findings if f.category == "slo_violation"]
    assert len(slo_findings) >= 1
    assert report.slo_violations >= 1


# ── SixHourAuditor: fallback mismatches ──────────────────────────────────────


def test_auditor_detects_time_mismatch():
    """Claim time after terminal time is a fallback mismatch."""
    store = RecoveryEventStore()
    event = RecoveryEvent(
        event_id="time-bad-1",
        kind=RecoveryEventKind.REPAIR_TERMINAL,
        occurred_at="2024-01-01T00:00:00+00:00",
        recorded_at="2024-01-01T00:05:00+00:00",
        request_id="req-1",
        claim_time="2024-01-01T00:03:00+00:00",
        terminal_time="2024-01-01T00:01:00+00:00",  # terminal before claim!
    )
    store.record(event)

    auditor = SixHourAuditor(event_store=store)
    report = auditor.run_audit()

    mismatch_findings = [f for f in report.findings if f.category == "fallback_mismatch"]
    assert len(mismatch_findings) >= 1


# ── SixHourAuditor: escalation ────────────────────────────────────────────────


def test_auditor_escalates_findings():
    """DEGRADED and FAILED findings are passed to the escalation sink."""
    store = RecoveryEventStore()
    event = RecoveryEventBuilder.parser_loss(session="s1", detail="bad parse")
    store.record(event)

    escalated: list = []
    auditor = SixHourAuditor(
        event_store=store,
        escalation_sink=lambda f: escalated.append(f),
    )
    report = auditor.run_audit()

    assert report.escalated_count >= 1
    assert len(escalated) >= 1


# ── SixHourAuditor: report structure ─────────────────────────────────────────


def test_audit_report_has_expected_metrics():
    """SixHourAuditReport has all required metrics."""
    store = RecoveryEventStore()
    auditor = SixHourAuditor(event_store=store)
    report = auditor.run_audit()

    assert report.audit_id.startswith("six-hour-")
    assert report.started_at
    assert report.completed_at
    assert report.duration_seconds >= 0
    assert report.events_checked >= 0
    assert report.requests_checked >= 0
    assert report.slo_violations >= 0
    assert report.escalated_count >= 0


def test_audit_report_ok_when_no_anomalies():
    """A clean report is ok."""
    store = RecoveryEventStore()
    auditor = SixHourAuditor(event_store=store)
    report = auditor.run_audit()

    # No events recorded, so it should be ok
    assert report.ok


def test_audit_report_requires_attention_with_anomalies():
    """A report with anomalies requires_attention."""
    store = RecoveryEventStore()
    event = RecoveryEventBuilder.parser_loss(session="s1", detail="error")
    store.record(event)

    auditor = SixHourAuditor(event_store=store)
    report = auditor.run_audit()

    assert report.requires_attention


# ── AuditFinding structure ───────────────────────────────────────────────────


def test_audit_finding_structure():
    """AuditFinding has the expected fields."""
    finding = AuditFinding(
        finding_id="f-1",
        severity=AuditSeverity.FAILED,
        category="parser_loss",
        detail="Parser failed",
        occurred_at="2024-01-01T00:00:00+00:00",
        evidence={"key": "value"},
    )
    assert finding.severity == AuditSeverity.FAILED
    assert finding.category == "parser_loss"
    assert not finding.escalated
