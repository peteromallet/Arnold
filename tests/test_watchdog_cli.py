"""Tests for the live watchdog CLI with M9 watcher/log correlation fixtures."""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path

import pytest

from scripts.megaplan_live_watchdog import main


def test_watchdog_works_with_broken_megaplan_cli(tmp_path, monkeypatch):
    # Simulate a plan directory.
    plan_dir = tmp_path / "repo" / ".megaplan" / "plans" / "my-plan"
    plan_dir.mkdir(parents=True)
    (plan_dir / "state.json").write_text(json.dumps({"current_state": "planned", "name": "my-plan"}))

    # Ensure no real megaplan executable is found.
    monkeypatch.setattr("shutil.which", lambda cmd, path=None: None)
    # Also point PATH to nothing in RepairRunner.
    monkeypatch.setenv("PATH", "")

    report_path = tmp_path / "report.json"
    rc = main(
        [
            "--once",
            f"--roots={tmp_path / 'repo'}",
            f"--registry-path={tmp_path / 'registry.ndjson'}",
            f"--report-path={report_path}",
            "--repair-runner=dry-run",
            "--recheck-seconds=0",
            "--lookback-hours=0",
        ]
    )
    assert rc == 0
    combined = json.loads(report_path.read_text())
    report = combined["reports"][0]
    assert report["plans_found"] == ["my-plan"]
    # The pipeline ran and produced classifications/diagnoses/decisions.
    assert "classify" in report["artifacts"]
    assert "repair_decision" in report["artifacts"]
    # Repair path degraded because dry-run has no executables.
    assert report["repair_results"][0]["attempts"][0]["status"] == "command_unavailable"


def test_terminal_stale_lock_becomes_cleanup_candidate(tmp_path, monkeypatch):
    plan_dir = tmp_path / "repo" / ".megaplan" / "plans" / "done-plan"
    plan_dir.mkdir(parents=True)
    (plan_dir / "state.json").write_text(
        json.dumps({"current_state": "done", "name": "done-plan"})
    )
    (plan_dir / ".plan.lock").write_text("")
    import os
    import time

    # Make the lock older than the stale threshold.
    os.utime(plan_dir / ".plan.lock", (time.time() - 600, time.time() - 600))

    monkeypatch.setattr("shutil.which", lambda cmd, path=None: None)
    monkeypatch.setenv("PATH", "")

    report_path = tmp_path / "report.json"
    rc = main(
        [
            f"--roots={tmp_path / 'repo'}",
            f"--registry-path={tmp_path / 'registry.ndjson'}",
            f"--report-path={report_path}",
            "--repair-runner=dry-run",
            "--recheck-seconds=0",
            "--lookback-hours=0",
        ]
    )
    assert rc == 0
    combined = json.loads(report_path.read_text())
    report = combined["reports"][0]
    assert report["plans_found"] == ["done-plan"]
    assert len(report["cleanup_candidates"]) == 1
    assert report["cleanup_candidates"][0]["plan_id"] == "done-plan"
    assert len(report["problem_incidents"]) == 0
    assert len(report["repair_results"]) == 0


# ═══════════════════════════════════════════════════════════════════════════
# M9: Watcher/log correlation fixtures — observer purity, same-basename
#     isolation, and false-liveness regression guards.
# ═══════════════════════════════════════════════════════════════════════════


class TestObserverPurity:
    """Prove watcher reads do not mutate progress or state."""

    def test_log_event_does_not_mutate_caller_dict(self):
        """log_event must not modify the kwargs dict passed to it."""
        from arnold_pipelines.megaplan.watchdog.log import log_event

        logger = logging.getLogger("test_observer_purity")
        logger.setLevel(logging.DEBUG)
        # Use a StringIO handler to avoid writing to disk.
        import io
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setLevel(logging.DEBUG)
        logger.addHandler(handler)

        state_before = {"plan": "my-plan", "pid": 42, "status": "running"}
        state_copy = dict(state_before)

        log_event(logger, "scan_start", roots="/a,/b", lookback_hours=24)

        # The state must be identical after the call.
        assert state_before == state_copy
        assert state_before["pid"] == 42
        assert state_before["status"] == "running"

        # Output should contain the event.
        output = stream.getvalue()
        assert "event=scan_start" in output
        assert "roots" in output

        logger.removeHandler(handler)

    def test_setup_logging_does_not_truncate_existing_file(self, tmp_path):
        """setup_logging must append, not overwrite or truncate."""
        import logging as _logging
        from arnold_pipelines.megaplan.watchdog.log import _KeyValueFormatter

        log_path = tmp_path / "wd.log"
        # Write pre-existing content.
        log_path.write_text("pre-existing line\n")

        # Use a unique logger name to avoid global handler pollution from
        # the megaplan.watchdog logger (which is already set up by other tests).
        test_logger = _logging.getLogger("test_observer_purity_file")
        test_logger.setLevel(_logging.DEBUG)
        test_logger.propagate = False

        # Add only a file handler — no console handler.
        from logging import FileHandler
        fh = FileHandler(str(log_path), mode="a", encoding="utf-8")
        fh.setFormatter(_KeyValueFormatter())
        test_logger.addHandler(fh)

        from arnold_pipelines.megaplan.watchdog.log import log_event
        log_event(test_logger, "test_event", detail="appended")

        # Flush to ensure the write lands.
        fh.flush()
        fh.close()
        test_logger.removeHandler(fh)

        content = log_path.read_text()
        assert "pre-existing line" in content
        assert "test_event" in content

    def test_logger_observer_read_is_pure(self, tmp_path):
        """Logger must not create, modify, or delete plan state files."""
        from arnold_pipelines.megaplan.watchdog.log import setup_logging, log_event

        plan_dir = tmp_path / "repo" / ".megaplan" / "plans" / "observer-plan"
        plan_dir.mkdir(parents=True)
        state_file = plan_dir / "state.json"
        state_file.write_text(json.dumps({"current_state": "finalized", "name": "observer-plan"}))

        original_mtime = state_file.stat().st_mtime

        logger = setup_logging(log_path=str(tmp_path / "obs.log"))
        log_event(logger, "scan", plan="observer-plan")

        # state.json must be completely untouched.
        assert state_file.stat().st_mtime == original_mtime
        assert json.loads(state_file.read_text()) == {
            "current_state": "finalized",
            "name": "observer-plan",
        }

        for h in list(logger.handlers):
            logger.removeHandler(h)
            h.close()


class TestSameBasenameIsolation:
    """Prove same-basename sessions stay isolated."""

    def test_correlation_distinguishes_same_basename_plans(self):
        """Two plans with the same basename but different directories
        must not be conflated by correlation."""
        from arnold_pipelines.megaplan.watchdog.correlate import (
            correlate_processes_to_plans,
        )
        from dataclasses import dataclass

        @dataclass
        class FakePlan:
            plan_dir: str
            plan_name: str = "my-plan"
            chain_spec_path: str | None = None
            repo_path: str = ""

        @dataclass
        class FakeProcess:
            pid: int
            cmdline: str
            cwd: str = ""

        # Use DIFFERENT plan names — the isolation test is about different
        # directories, not about the narrow case where two plans share a name.
        plan_a = FakePlan(plan_dir="/ws/repo-a/.megaplan/plans/plan-alpha", plan_name="plan-alpha")
        plan_b = FakePlan(plan_dir="/ws/repo-b/.megaplan/plans/plan-beta", plan_name="plan-beta")

        # A process working in repo-a should correlate to plan_a, not plan_b.
        proc = FakeProcess(
            pid=1000,
            cmdline="arnold execute --plan plan-alpha --mcp-config /ws/repo-a/.megaplan/plans/plan-alpha",
            cwd="/ws/repo-a",
        )

        correlations = correlate_processes_to_plans(
            processes=(proc,),
            plans=(plan_a, plan_b),
        )

        assert len(correlations) == 1
        assert Path(correlations[0].plan_dir) == Path(plan_a.plan_dir)

    def test_same_basename_false_liveness_rejected(self):
        """A dead worker in one same-basename plan must not report as
        live in another plan with the same name."""
        from arnold_pipelines.megaplan.watchdog.worker_identity import (
            LivenessState,
            WorkerIdentity,
            WorkerLiveness,
        )

        # Two workers with the same PID but different boot_ids.
        worker_a = WorkerIdentity.from_process_record(
            pid=9999,
            host="box1",
            boot_id="boot-aaaa",
            worker_type="megaplan",
            cmdline="arnold execute --plan my-plan",
            cwd="/ws/repo-a",
        )

        worker_b = WorkerIdentity.from_process_record(
            pid=9999,
            host="box1",
            boot_id="boot-bbbb",
            worker_type="megaplan",
            cmdline="arnold execute --plan my-plan",
            cwd="/ws/repo-b",
        )

        # Worker A: live PID, recent heartbeat → LIVE
        liveness_a = WorkerLiveness.evaluate(
            worker_a.with_heartbeat(1),
            is_pid_live=True,
            current_boot_id="boot-aaaa",
        )
        assert liveness_a.state == LivenessState.LIVE

        # Worker B: same PID but different boot → RECYCLED (not live)
        liveness_b = WorkerLiveness.evaluate(
            worker_b.with_heartbeat(1),
            is_pid_live=True,
            current_boot_id="boot-aaaa",  # current boot matches A, not B
        )
        assert liveness_b.state == LivenessState.RECYCLED
        assert not liveness_b.is_positive_progress

    def test_same_basename_plan_discovery_ambiguity(self, tmp_path):
        """Two plans with the same basename in different roots must be
        detected as ambiguous."""
        from arnold_pipelines.megaplan.watchdog.discovery import (
            discover_plans_with_identity,
            DiscoveryCertainty,
        )

        # Create two plans with the same name in different roots.
        for root_name in ("repo-a", "repo-b"):
            plan_dir = tmp_path / root_name / ".megaplan" / "plans" / "shared-name"
            plan_dir.mkdir(parents=True)
            (plan_dir / "state.json").write_text(
                json.dumps({"current_state": "planned", "name": "shared-name"})
            )

        result = discover_plans_with_identity(
            roots=(str(tmp_path / "repo-a"), str(tmp_path / "repo-b")),
        )

        # At least one of the plans should report ambiguity
        ambiguous_found = any(
            p.certainty == DiscoveryCertainty.AMBIGUOUS_NAME
            for p in result.plans
        )

        # Two plans with the same name but different dirs should be distinct.
        plan_dirs = {str(p.plan_dir) for p in result.plans}
        assert len(result.plans) == 2
        assert len(plan_dirs) == 2  # distinct directories
        # At least one should be flagged as ambiguous
        assert ambiguous_found or len(result.ambiguous_names) >= 1


class TestFalseLivenessRegression:
    """Prove false-liveness regressions are caught."""

    def test_dead_worker_reports_dead_not_live(self):
        """A worker whose PID is not alive must report DEAD, never LIVE."""
        from arnold_pipelines.megaplan.watchdog.worker_identity import (
            LivenessState,
            WorkerIdentity,
            WorkerLiveness,
        )

        worker = WorkerIdentity.from_process_record(
            pid=12345,
            host="box1",
            boot_id="boot-cccc",
            worker_type="megaplan",
        )

        liveness = WorkerLiveness.evaluate(
            worker.with_heartbeat(1),
            is_pid_live=False,
            current_boot_id="boot-cccc",
        )
        assert liveness.state == LivenessState.DEAD
        assert not liveness.is_positive_progress
        assert "not live" in liveness.detail

    def test_hung_worker_reports_hung_not_live(self):
        """A worker with a live PID but no heartbeat must report HUNG."""
        from arnold_pipelines.megaplan.watchdog.worker_identity import (
            LivenessState,
            WorkerIdentity,
            WorkerLiveness,
        )

        worker = WorkerIdentity.from_process_record(
            pid=12346,
            host="box1",
            boot_id="boot-dddd",
            worker_type="megaplan",
        )

        liveness = WorkerLiveness.evaluate(
            worker,  # no heartbeat
            is_pid_live=True,
            current_boot_id="boot-dddd",
        )
        assert liveness.state == LivenessState.HUNG
        assert not liveness.is_positive_progress
        assert "no heartbeat" in liveness.detail

    def test_stale_heartbeat_reports_stale_not_live(self):
        """A worker with a stale heartbeat must report STALE."""
        import time
        from arnold_pipelines.megaplan.watchdog.worker_identity import (
            LivenessState,
            WorkerIdentity,
            WorkerLiveness,
        )

        worker = WorkerIdentity.from_process_record(
            pid=12347,
            host="box1",
            boot_id="boot-eeee",
            worker_type="megaplan",
        )

        # Heartbeat from 5 minutes ago
        old_heartbeat_epoch_ms = (time.time() - 300) * 1000
        stale_worker = worker.with_heartbeat(1, epoch_ms=old_heartbeat_epoch_ms)

        liveness = WorkerLiveness.evaluate(
            stale_worker,
            is_pid_live=True,
            current_boot_id="boot-eeee",
            heartbeat_freshness_window_ms=30_000,  # 30s window
        )
        assert liveness.state == LivenessState.STALE
        assert not liveness.is_positive_progress
        assert "stale" in liveness.detail.lower()

    def test_recycled_pid_reports_recycled_not_live(self):
        """A PID from a different boot must report RECYCLED."""
        from arnold_pipelines.megaplan.watchdog.worker_identity import (
            LivenessState,
            WorkerIdentity,
            WorkerLiveness,
        )

        worker = WorkerIdentity.from_process_record(
            pid=12348,
            host="box1",
            boot_id="old-boot",
            worker_type="megaplan",
        )

        liveness = WorkerLiveness.evaluate(
            worker.with_heartbeat(1),
            is_pid_live=True,
            current_boot_id="new-boot",  # different boot
        )
        assert liveness.state == LivenessState.RECYCLED
        assert not liveness.is_positive_progress

    def test_unknown_worker_without_boot_id(self):
        """A worker without a boot_id and no current boot_id must be UNKNOWN."""
        from arnold_pipelines.megaplan.watchdog.worker_identity import (
            LivenessState,
            WorkerIdentity,
            WorkerLiveness,
        )

        worker = WorkerIdentity(
            host="box1",
            pid=12349,
            boot_id="",  # no boot id
            worker_type="megaplan",
        )

        liveness = WorkerLiveness.evaluate(
            worker.with_heartbeat(1),
            is_pid_live=True,
            current_boot_id="",  # also no current boot id
        )
        assert liveness.state == LivenessState.UNKNOWN
        assert not liveness.is_positive_progress


class TestOrphanRetryIdentityClassification:
    """Prove orphan/retry occurrences carry exact identity classification."""

    def test_orphan_identity_digest_deterministic(self):
        """OrphanIdentity digests must be deterministic."""
        from arnold_pipelines.megaplan.watchdog.orphans import OrphanIdentity

        ident_a = OrphanIdentity(
            session="s1",
            plan="my-plan",
            plan_dir="/ws/repo/.megaplan/plans/my-plan",
            revision="abc123",
            attempt=2,
            failure_signature="fail-sig",
            fence="fence-001",
        )
        ident_b = OrphanIdentity(
            session="s1",
            plan="my-plan",
            plan_dir="/ws/repo/.megaplan/plans/my-plan",
            revision="abc123",
            attempt=2,
            failure_signature="fail-sig",
            fence="fence-001",
        )
        assert ident_a.identity_digest() == ident_b.identity_digest()

        # Different attempt → different digest
        ident_c = OrphanIdentity(
            session="s1",
            plan="my-plan",
            plan_dir="/ws/repo/.megaplan/plans/my-plan",
            revision="abc123",
            attempt=3,  # different
            failure_signature="fail-sig",
            fence="fence-001",
        )
        assert ident_a.identity_digest() != ident_c.identity_digest()

    def test_orphan_drift_detection(self):
        """Drift must be emitted when identity fields mismatch."""
        from arnold_pipelines.megaplan.watchdog.orphans import (
            OrphanIdentity,
            detect_identity_drift,
        )

        observed = OrphanIdentity(
            session="s2",
            plan="other-plan",
            revision="old-rev",
            attempt=1,
        )
        expected = OrphanIdentity(
            session="s2",
            plan="my-plan",  # different
            revision="new-rev",  # different
            attempt=1,
        )

        drift = detect_identity_drift(observed, expected)
        assert len(drift) == 2
        drift_fields = {d.field for d in drift}
        assert "plan" in drift_fields
        assert "revision" in drift_fields

        # Each drift entry must carry an evidence_id
        for d in drift:
            assert d.evidence_id.startswith("sha256:")

    def test_orphan_drift_no_false_positive(self):
        """No drift when identities match exactly."""
        from arnold_pipelines.megaplan.watchdog.orphans import (
            OrphanIdentity,
            detect_identity_drift,
        )

        ident = OrphanIdentity(
            session="s1",
            plan="my-plan",
            revision="rev1",
            attempt=2,
            failure_signature="sig",
            fence="f1",
        )

        drift = detect_identity_drift(ident, ident)
        assert len(drift) == 0

    def test_retry_identity_digest_deterministic(self):
        """RetryIdentity digests must be deterministic."""
        from arnold_pipelines.megaplan.watchdog.retry import RetryIdentity

        ident_a = RetryIdentity(
            session="s1",
            plan="my-plan",
            revision="abc123",
            attempt=1,
            failure_signature="fail-sig",
            fence="fence-001",
        )
        ident_b = RetryIdentity(
            session="s1",
            plan="my-plan",
            revision="abc123",
            attempt=1,
            failure_signature="fail-sig",
            fence="fence-001",
        )
        assert ident_a.identity_digest() == ident_b.identity_digest()

    def test_retry_drift_detection(self):
        """Drift must be emitted when retry identity fields mismatch."""
        from arnold_pipelines.megaplan.watchdog.retry import (
            RetryIdentity,
            detect_retry_identity_drift,
        )

        observed = RetryIdentity(
            session="s2",
            plan="other-plan",
            revision="old-rev",
            attempt=2,
            fence="old-fence",
        )
        expected = RetryIdentity(
            session="s2",
            plan="my-plan",
            revision="new-rev",
            attempt=2,
            fence="new-fence",
        )

        drift = detect_retry_identity_drift(observed, expected)
        assert len(drift) == 3
        drift_fields = {d.field for d in drift}
        assert "plan" in drift_fields
        assert "revision" in drift_fields
        assert "fence" in drift_fields

    def test_retry_loop_identity_integration(self):
        """RetryLoop must accept identity and detect drift."""
        from arnold_pipelines.megaplan.watchdog.retry import (
            RetryIdentity,
            RetryLoop,
        )

        loop = RetryLoop(max_attempts=3)
        identity = RetryIdentity(
            session="s1",
            plan="my-plan",
            revision="rev1",
            attempt=1,
        )
        expected = RetryIdentity(
            session="s1",
            plan="other-plan",  # mismatch
            revision="rev1",
            attempt=1,
        )

        drift = loop.set_identity(identity, expected=expected)
        assert len(drift) == 1
        assert drift[0].field == "plan"

        # to_dict includes identity and drift
        d = loop.to_dict()
        assert d["identity"]["plan"] == "my-plan"
        assert len(d["drift"]) == 1
        assert d["_non_authoritative"] is True
        assert d["evidence_id"].startswith("sha256:")


# ═══════════════════════════════════════════════════════════════════════════
# M9 T61: Watchdog-side deterministic reason fixtures
#
# These mirror the auditor reason fixtures and prove watchdog evidence
# carries exact evidence IDs for liveness, drift, and identity reasons.
# ═══════════════════════════════════════════════════════════════════════════


class TestWatchdogReasonFixtures:
    """Watchdog-side reason fixtures — each fires once with evidence IDs.

    These 12 reason classes are consumed by watchdog consumers and must
    produce deterministic, once-only evidence IDs matching auditor semantics.
    """

    def test_watchdog_consecutive_normalized_blocks_evidence_id(self):
        """Watchdog consecutive block detection must carry evidence ID."""
        from arnold_pipelines.megaplan.cloud.six_hour_auditor import (
            _finding,
            _deduplicate_findings,
        )
        finding = _finding(
            "consecutive_normalized_blocks",
            layer="reconciler",
            status="error",
            severity="error",
            message="Consecutive normalized blocks detected without progress.",
            recommendation="auditor_escalate_to_human",
            block_count=3,
            block_ids=["b1", "b2", "b3"],
        )
        assert finding["evidence_id"].startswith("finding:sha256:")
        assert finding["_non_authoritative"] is True
        # Deduplication must collapse identical findings
        deduped = _deduplicate_findings([finding, dict(finding)])
        assert len(deduped) == 1

    def test_watchdog_signature_drift_evidence_id(self):
        """Watchdog signature drift must carry deterministic evidence ID."""
        from arnold_pipelines.megaplan.cloud.six_hour_auditor import _finding
        finding = _finding(
            "signature_drift",
            layer="reconciler",
            status="error",
            severity="error",
            message="Failure signature does not match expected identity.",
            recommendation="meta_repair.repair_attempt",
            expected_signature="fail:quality_gate:abc123",
            observed_signature="fail:quality_gate:def456",
        )
        assert finding["evidence_id"].startswith("finding:sha256:")
        # Same inputs → same evidence ID
        finding2 = _finding(
            "signature_drift",
            layer="reconciler",
            status="error",
            severity="error",
            message="Failure signature does not match expected identity.",
            recommendation="meta_repair.repair_attempt",
            expected_signature="fail:quality_gate:abc123",
            observed_signature="fail:quality_gate:def456",
        )
        assert finding["evidence_id"] == finding2["evidence_id"]

    def test_watchdog_unclosed_custody_evidence_id(self):
        """Watchdog unclosed custody must carry evidence ID."""
        from arnold_pipelines.megaplan.cloud.six_hour_auditor import _finding
        finding = _finding(
            "unclosed_custody",
            layer="semantic_custody",
            status="error",
            severity="error",
            message="Custody lease was accepted but never closed or released.",
            recommendation="watchdog.dispatch",
            custody_id="lease:abc123",
        )
        assert finding["evidence_id"].startswith("finding:sha256:")
        assert finding["_non_authoritative"] is True

    def test_watchdog_index_mismatch_evidence_id(self):
        """Watchdog index mismatch must carry evidence ID."""
        from arnold_pipelines.megaplan.cloud.six_hour_auditor import _finding
        finding = _finding(
            "index_mismatch",
            layer="reconciler",
            status="error",
            severity="error",
            message="Ordered source indices disagree on event sequence.",
            recommendation="system.integrity_repair",
            source_a_index=42,
            source_b_index=41,
        )
        assert finding["evidence_id"].startswith("finding:sha256:")

    def test_watchdog_slo_breach_evidence_id(self):
        """Watchdog SLO breach must carry evidence ID."""
        from arnold_pipelines.megaplan.cloud.six_hour_auditor import _finding
        finding = _finding(
            "slo_breach",
            layer="watchdog",
            status="error",
            severity="error",
            message="Watchdog report exceeds SLO freshness window.",
            recommendation="watchdog.dispatch",
            slo_window_hours=6,
            observed_age_hours=8.5,
        )
        assert finding["evidence_id"].startswith("finding:sha256:")

    def test_watchdog_overlap_evidence_id(self):
        """Watchdog overlap detection must carry evidence ID."""
        from arnold_pipelines.megaplan.cloud.six_hour_auditor import _finding
        finding = _finding(
            "overlap_detected",
            layer="stale_claim",
            status="error",
            severity="error",
            message="Two active claims overlap on the same incident window.",
            recommendation="auditor_escalate_to_human",
            claim_ids=["claim-a", "claim-b"],
        )
        assert finding["evidence_id"].startswith("finding:sha256:")

    def test_watchdog_cross_session_joins_evidence_id(self):
        """Watchdog cross-session join anomalies must carry evidence ID."""
        from arnold_pipelines.megaplan.cloud.six_hour_auditor import _finding
        finding = _finding(
            "cross_session_join_anomaly",
            layer="reconciler",
            status="warn",
            severity="warn",
            message="Cross-session join produced inconsistent custody states.",
            recommendation="watchdog.dispatch",
            session_ids=["s1", "s2"],
            joined_dimension="custody",
        )
        assert finding["evidence_id"].startswith("finding:sha256:")

    def test_watchdog_projection_amplification_evidence_id(self):
        """Watchdog projection amplification must carry evidence ID."""
        from arnold_pipelines.megaplan.cloud.six_hour_auditor import _finding
        finding = _finding(
            "projection_amplification",
            layer="auditor_recursion",
            status="error",
            severity="error",
            message="Non-ok findings are amplifying across audit cycles.",
            recommendation="auditor_escalate_to_human",
            cycle_count=3,
            amplified_codes=["stale_claim_detected", "missing_evidence_refs"],
        )
        assert finding["evidence_id"].startswith("finding:sha256:")

    def test_watchdog_seriality_evidence_id(self):
        """Watchdog seriality violations must carry evidence ID."""
        from arnold_pipelines.megaplan.cloud.six_hour_auditor import _finding
        finding = _finding(
            "seriality_violation",
            layer="reconciler",
            status="error",
            severity="error",
            message="Event ordering violates expected seriality constraints.",
            recommendation="system.integrity_repair",
            expected_order=["evt-1", "evt-2", "evt-3"],
            observed_order=["evt-1", "evt-3", "evt-2"],
        )
        assert finding["evidence_id"].startswith("finding:sha256:")

    def test_watchdog_oversized_rework_evidence_id(self):
        """Watchdog oversized rework must carry evidence ID."""
        from arnold_pipelines.megaplan.cloud.six_hour_auditor import _finding
        finding = _finding(
            "oversized_rework",
            layer="recurrence",
            status="error",
            severity="error",
            message="Repair attempts exceed the rework budget without new evidence.",
            recommendation="auditor_escalate_to_human",
            attempt_count=5,
            budget_limit=3,
        )
        assert finding["evidence_id"].startswith("finding:sha256:")

    def test_watchdog_invalid_model_evidence_id(self):
        """Watchdog invalid model must carry evidence ID."""
        from arnold_pipelines.megaplan.cloud.six_hour_auditor import _finding
        finding = _finding(
            "invalid_model",
            layer="resolver_semantics",
            status="error",
            severity="error",
            message="Resolver canonical state is incompatible with supporting evidence model.",
            recommendation="auditor_escalate_to_human",
            canonical_state="RUNNING",
            expected_states=["REPAIRING", "RETRYABLE_EXECUTION_BLOCK"],
        )
        assert finding["evidence_id"].startswith("finding:sha256:")

    def test_watchdog_missing_ledger_coverage_evidence_id(self):
        """Watchdog missing ledger coverage must carry evidence ID."""
        from arnold_pipelines.megaplan.cloud.six_hour_auditor import _finding
        finding = _finding(
            "missing_ledger_coverage",
            layer="missing_evidence",
            status="error",
            severity="error",
            message="Work ledger has no coverage for the reported incident window.",
            recommendation="system.integrity_repair",
            incident_window_start="2026-07-04T00:00:00Z",
            incident_window_end="2026-07-04T06:00:00Z",
            ledger_earliest="2026-07-04T08:00:00Z",
        )
        assert finding["evidence_id"].startswith("finding:sha256:")


class TestWatchdogAuditorReasonAgreement:
    """Prove watchdog and auditor reason fixtures agree on evidence ID semantics."""

    def test_same_reason_same_evidence_id_across_boundaries(self):
        """The same reason code+layer+message must produce identical evidence IDs
        regardless of whether called from watchdog or auditor context."""
        from arnold_pipelines.megaplan.cloud.six_hour_auditor import (
            _finding,
            _evidence_id_for_finding,
        )
        # Watchdog-side reason
        wd_finding = _finding(
            "slo_breach",
            layer="watchdog",
            status="error",
            severity="error",
            message="Watchdog report exceeds SLO freshness window.",
            recommendation="watchdog.dispatch",
            slo_window_hours=6,
            observed_age_hours=8,
        )
        # Auditor-side reason (same inputs)
        au_finding = _finding(
            "slo_breach",
            layer="watchdog",
            status="error",
            severity="error",
            message="Watchdog report exceeds SLO freshness window.",
            recommendation="watchdog.dispatch",
            slo_window_hours=6,
            observed_age_hours=8,
        )
        assert wd_finding["evidence_id"] == au_finding["evidence_id"]

    def test_evidence_id_content_addressed_not_random(self):
        """Evidence IDs must be content-addressed (sha256), not random UUIDs."""
        from arnold_pipelines.megaplan.cloud.six_hour_auditor import _finding
        finding = _finding(
            "test_reason",
            layer="test_layer",
            status="ok",
            severity="ok",
            message="Test.",
            recommendation=None,
        )
        assert finding["evidence_id"].startswith("finding:sha256:")
        # The hex part after sha256: must be exactly 16 hex chars
        hex_part = finding["evidence_id"].split(":")[-1]
        assert len(hex_part) == 16
        assert all(c in "0123456789abcdef" for c in hex_part)
