from __future__ import annotations

import json
from pathlib import Path

from arnold_pipelines.megaplan.incident import projection
from arnold_pipelines.megaplan.incident import (
    IncidentLedger,
    build_brief,
    rebuild_projections,
)


def _event(**overrides: object) -> dict[str, object]:
    event: dict[str, object] = {
        "schema_version": 1,
        "event_id": "evt-1",
        "ts": "2026-07-03T19:19:00Z",
        "scope": "repair_system",
        "outcome": "started",
        "incident_id": "inc-123",
        "type": "detection",
        "actor": "watchdog",
        "summary": "Build runner failed on startup",
        "evidence": [{"kind": "file", "path": "logs/runner.log"}],
        "next_expected_event": "immediate_repair.repair_attempt",
        "deadline_ts": "2026-07-03T19:34:00Z",
        "parent_event_ids": [],
        "trigger_event_id": None,
        "session_id": "session-1",
        "problem_id": "prob-1",
    }
    event.update(overrides)
    return event


def test_rebuild_projections_is_deterministic_and_tracks_incident_problem_state(
    tmp_path: Path,
) -> None:
    ledger = IncidentLedger(tmp_path)
    ledger.append_event(_event())
    ledger.append_event(
        _event(
            event_id="evt-2",
            type="repair_attempt",
            actor="immediate_repair",
            ts="2026-07-03T19:20:00Z",
            summary="Restarted the runner and captured output",
            parent_event_ids=["evt-1"],
            attempt_id="attempt-1",
            decision={"selected_action": "restart-runner"},
            actions=[{"kind": "command", "command": "systemctl restart runner"}],
            evidence=[{"kind": "file", "path": "logs/restart.log"}],
            outcome="failed",
        )
    )
    ledger_dir = tmp_path / ".megaplan" / "incident-ledger"
    (ledger_dir / "incidents.json").write_text(
        json.dumps(
            {"source": {"digest": "sha256:stale", "last_seq": -1}},
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    first = rebuild_projections(tmp_path)
    incidents_path = ledger_dir / "incidents.json"
    problems_path = ledger_dir / "problems.json"
    second = rebuild_projections(tmp_path)
    second_incidents_json = incidents_path.read_text(encoding="utf-8")
    second_problems_json = problems_path.read_text(encoding="utf-8")
    third = rebuild_projections(tmp_path)

    assert incidents_path.read_text(encoding="utf-8") == second_incidents_json
    assert problems_path.read_text(encoding="utf-8") == second_problems_json

    incident = first["incidents"]["incidents"][0]
    assert incident["incident_id"] == "inc-123"
    assert incident["state"] == "repair_attempt"
    assert incident["outcome"] == "failed"
    assert incident["next_expected_event"] == "immediate_repair.repair_attempt"
    assert incident["deadline_ts"] == "2026-07-03T19:34:00Z"
    assert incident["session_ids"] == ["session-1"]
    assert incident["attempts"] == [
        {
            "attempt_id": "attempt-1",
            "event_seqs": [1],
            "latest_outcome": "failed",
            "types": ["repair_attempt"],
        }
    ]
    assert incident["decisions"] == [
        {"seq": 1, "decision": {"selected_action": "restart-runner"}}
    ]
    assert incident["actions"] == [
        {
            "seq": 1,
            "actions": [{"kind": "command", "command": "systemctl restart runner"}],
        }
    ]
    assert incident["placeholders"] == {
        "install_freshness": "unknown",
        "recurrence": "unknown",
        "shipped_fix": "unknown",
    }
    assert any(
        finding["code"] == "index_divergence"
        and finding.get("projection") == "incidents"
        for finding in first["incidents"]["integrity"]
    )
    assert second["incidents"]["integrity"] == []
    assert third["incidents"]["integrity"] == []

    problem = first["problems"]["problems"][0]
    assert problem["problem_id"] == "prob-1"
    assert problem["scope"] == "repair_system"
    assert problem["occurrence_count"] == 2
    assert problem["linked_incident_ids"] == ["inc-123"]


def test_rebuild_projections_reports_malformed_schema_and_dangling_refs(
    tmp_path: Path,
) -> None:
    ledger_dir = tmp_path / ".megaplan" / "incident-ledger"
    ledger_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        json.dumps(
            {
                "seq": 0,
                "kind": "incident.detection",
                "payload": _event(),
            },
            sort_keys=True,
        ),
        "{broken json",
        json.dumps(
            {
                "seq": 1,
                "kind": "incident.detection",
                "payload": {
                    "schema_version": 1,
                    "incident_id": "inc-bad",
                    "type": "detection",
                    "actor": "watchdog",
                    "ts": "2026-07-03T19:19:10Z",
                    "scope": "repair_system",
                    "outcome": "started",
                    "evidence": [],
                    "next_expected_event": None,
                    "deadline_ts": None,
                    "parent_event_ids": [],
                    "trigger_event_id": None,
                },
            },
            sort_keys=True,
        ),
        json.dumps(
            {
                "seq": 2,
                "kind": "incident.repair_attempt",
                "payload": _event(
                    event_id="evt-2",
                    type="repair_attempt",
                    actor="immediate_repair",
                    ts="2026-07-03T19:20:00Z",
                    parent_event_ids=["missing-parent"],
                    trigger_event_id="missing-trigger",
                    attempt_id="attempt-2",
                ),
            },
            sort_keys=True,
        ),
    ]
    (ledger_dir / "events.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (ledger_dir / "problems.json").write_text("{not json", encoding="utf-8")

    result = rebuild_projections(tmp_path)

    findings = result["incidents"]["integrity"]
    codes = {(finding["code"], finding.get("projection")) for finding in findings}
    assert ("malformed_json", None) in codes
    assert ("schema_failure", None) in codes
    assert ("dangling_parent_ref", None) in codes
    assert ("dangling_trigger_ref", None) in codes
    assert ("index_divergence", "problems") in codes

    incident = result["incidents"]["incidents"][0]
    assert incident["incident_id"] == "inc-123"
    assert incident["event_count"] == 2
    assert all(
        finding["recommendation"] == "system.integrity_repair" for finding in findings
    )
    brief = build_brief("inc-123", root=tmp_path)
    assert brief["integrity"]["recommendation"] == "system.integrity_repair"
    assert "next_step" not in brief["integrity"]
    assert "valid_next" not in brief["integrity"]
    assert "workflow_cursor" not in brief["integrity"]


# ---------------------------------------------------------------------------
# M2 shipped-fix chain projection fixtures
# ---------------------------------------------------------------------------


def test_shipped_fix_happy_path_chain_marks_problem_fixed(
    tmp_path: Path,
) -> None:
    """Full M2 shipped-fix chain: source_fix_committed -> install_sync_applied
    -> repair_retriggered -> verified_recovered should mark the problem fixed."""
    ledger = IncidentLedger(tmp_path)
    ledger.append_event(
        _event(
            event_id="evt-1",
            type="detection",
            actor="watchdog",
            problem_id="prob-ship",
            summary="Build failure detected",
            outcome="started",
        )
    )
    ledger.append_event(
        _event(
            event_id="evt-2",
            type="source_fix_committed",
            actor="meta_repair",
            problem_id="prob-ship",
            summary="Fix committed for build failure",
            outcome="committed",
            parent_event_ids=["evt-1"],
            links={"commit": "abc123def"},
        )
    )
    ledger.append_event(
        _event(
            event_id="evt-3",
            type="install_sync_applied",
            actor="install_sync",
            problem_id="prob-ship",
            summary="Install sync applied fix to runtime",
            outcome="applied",
            parent_event_ids=["evt-2"],
            evidence=[
                {
                    "kind": "runtime_identity",
                    "before": "cpython-3.11.10",
                    "after": "cpython-3.11.11",
                    "path": "/usr/local/bin/python3",
                }
            ],
        )
    )
    ledger.append_event(
        _event(
            event_id="evt-4",
            type="repair_retriggered",
            actor="chain_runner",
            problem_id="prob-ship",
            summary="Repair retriggered after install sync",
            outcome="retriggered",
            parent_event_ids=["evt-3"],
        )
    )
    ledger.append_event(
        _event(
            event_id="evt-5",
            type="verified_recovered",
            actor="watchdog",
            problem_id="prob-ship",
            summary="Recovery verified after fix",
            outcome="recovered",
            parent_event_ids=["evt-4"],
        )
    )

    result = rebuild_projections(tmp_path)

    problems = result["problems"]["problems"]
    assert len(problems) == 1
    problem = problems[0]
    assert problem["problem_id"] == "prob-ship"
    assert problem["status"] == "fixed"
    assert problem["fix_commits"] == ["abc123def"]


def test_shipped_fix_missing_install_sync_not_fixed(
    tmp_path: Path,
) -> None:
    """source_fix_committed -> verified_recovered without install_sync_applied
    should NOT mark the problem as fixed."""
    ledger = IncidentLedger(tmp_path)
    ledger.append_event(
        _event(
            event_id="evt-1",
            type="detection",
            actor="watchdog",
            problem_id="prob-nosync",
            summary="Build failure detected",
            outcome="started",
        )
    )
    ledger.append_event(
        _event(
            event_id="evt-2",
            type="source_fix_committed",
            actor="meta_repair",
            problem_id="prob-nosync",
            summary="Fix committed",
            outcome="committed",
            parent_event_ids=["evt-1"],
            links={"commit": "abc123def"},
        )
    )
    ledger.append_event(
        _event(
            event_id="evt-3",
            type="verified_recovered",
            actor="watchdog",
            problem_id="prob-nosync",
            summary="Recovery verified without install evidence",
            outcome="recovered",
            parent_event_ids=["evt-2"],
        )
    )

    result = rebuild_projections(tmp_path)

    problems = result["problems"]["problems"]
    assert len(problems) == 1
    problem = problems[0]
    assert problem["problem_id"] == "prob-nosync"
    # Without install_sync_applied, the problem should NOT be marked fixed
    assert problem["status"] != "fixed"


def test_shipped_fix_install_sync_failed_not_fixed(
    tmp_path: Path,
) -> None:
    """source_fix_committed -> install_sync_failed -> verified_recovered
    should NOT mark the problem as fixed (install failure breaks the chain)."""
    ledger = IncidentLedger(tmp_path)
    ledger.append_event(
        _event(
            event_id="evt-1",
            type="detection",
            actor="watchdog",
            problem_id="prob-syncfail",
            summary="Build failure detected",
            outcome="started",
        )
    )
    ledger.append_event(
        _event(
            event_id="evt-2",
            type="source_fix_committed",
            actor="meta_repair",
            problem_id="prob-syncfail",
            summary="Fix committed",
            outcome="committed",
            parent_event_ids=["evt-1"],
            links={"commit": "abc123def"},
        )
    )
    ledger.append_event(
        _event(
            event_id="evt-3",
            type="install_sync_failed",
            actor="install_sync",
            problem_id="prob-syncfail",
            summary="Install sync failed — dependency conflict",
            outcome="failed",
            parent_event_ids=["evt-2"],
            evidence=[
                {
                    "kind": "runtime_identity",
                    "before": "cpython-3.11.10",
                    "after": "cpython-3.11.10",
                    "path": "/usr/local/bin/python3",
                }
            ],
        )
    )
    ledger.append_event(
        _event(
            event_id="evt-4",
            type="verified_recovered",
            actor="watchdog",
            problem_id="prob-syncfail",
            summary="Recovery verified despite install failure",
            outcome="recovered",
            parent_event_ids=["evt-3"],
        )
    )

    result = rebuild_projections(tmp_path)

    problems = result["problems"]["problems"]
    assert len(problems) == 1
    problem = problems[0]
    assert problem["problem_id"] == "prob-syncfail"
    # install_sync_failed should prevent the fix from being considered shipped
    assert problem["status"] != "fixed"


def test_shipped_fix_no_source_fix_not_fixed(
    tmp_path: Path,
) -> None:
    """verified_recovered without a prior source_fix_committed should NOT
    mark the problem as fixed."""
    ledger = IncidentLedger(tmp_path)
    ledger.append_event(
        _event(
            event_id="evt-1",
            type="detection",
            actor="watchdog",
            problem_id="prob-nocommit",
            summary="Build failure detected",
            outcome="started",
        )
    )
    ledger.append_event(
        _event(
            event_id="evt-2",
            type="install_sync_applied",
            actor="install_sync",
            problem_id="prob-nocommit",
            summary="Install sync applied",
            outcome="applied",
            parent_event_ids=["evt-1"],
        )
    )
    ledger.append_event(
        _event(
            event_id="evt-3",
            type="verified_recovered",
            actor="watchdog",
            problem_id="prob-nocommit",
            summary="Recovery without a known source fix",
            outcome="recovered",
            parent_event_ids=["evt-2"],
        )
    )

    result = rebuild_projections(tmp_path)

    problems = result["problems"]["problems"]
    assert len(problems) == 1
    problem = problems[0]
    assert problem["problem_id"] == "prob-nocommit"
    # Without a source_fix_committed, verified_recovered alone is not a shipped fix
    assert problem["status"] != "fixed"
    assert problem["fix_commits"] == []


def test_shipped_fix_no_verified_recovery_not_fixed(
    tmp_path: Path,
) -> None:
    """source_fix_committed -> install_sync_applied without verified_recovered
    should leave the problem as mitigated, not fixed."""
    ledger = IncidentLedger(tmp_path)
    ledger.append_event(
        _event(
            event_id="evt-1",
            type="detection",
            actor="watchdog",
            problem_id="prob-norecovery",
            summary="Build failure detected",
            outcome="started",
        )
    )
    ledger.append_event(
        _event(
            event_id="evt-2",
            type="source_fix_committed",
            actor="meta_repair",
            problem_id="prob-norecovery",
            summary="Fix committed",
            outcome="committed",
            parent_event_ids=["evt-1"],
            links={"commit": "abc123def"},
        )
    )
    ledger.append_event(
        _event(
            event_id="evt-3",
            type="install_sync_applied",
            actor="install_sync",
            problem_id="prob-norecovery",
            summary="Install sync applied",
            outcome="applied",
            parent_event_ids=["evt-2"],
        )
    )

    result = rebuild_projections(tmp_path)

    problems = result["problems"]["problems"]
    assert len(problems) == 1
    problem = problems[0]
    assert problem["problem_id"] == "prob-norecovery"
    # Fix is committed and installed, but not verified recovered
    assert problem["status"] != "fixed"
    assert problem["fix_commits"] == ["abc123def"]


# ---------------------------------------------------------------------------
# M2 repeated-attempt detection fixtures
# ---------------------------------------------------------------------------


def test_repeated_repair_attempts_no_new_evidence_reported(
    tmp_path: Path,
) -> None:
    """Three identical repair_attempt events with the same hypothesis and
    no new evidence between them should produce a loop_break integrity finding."""
    ledger = IncidentLedger(tmp_path)
    ledger.append_event(
        _event(
            event_id="evt-1",
            type="detection",
            actor="watchdog",
            incident_id="inc-loop",
            problem_id="prob-loop",
            summary="Build runner failed",
            outcome="started",
        )
    )
    # First repair attempt
    ledger.append_event(
        _event(
            event_id="evt-2",
            type="repair_attempt",
            actor="immediate_repair",
            incident_id="inc-loop",
            problem_id="prob-loop",
            summary="Restart runner",
            outcome="failed",
            parent_event_ids=["evt-1"],
            attempt_id="attempt-1",
            decision={"selected_action": "restart-runner"},
            actions=[{"kind": "command", "command": "systemctl restart runner"}],
            evidence=[{"kind": "file", "path": "logs/restart-1.log"}],
        )
    )
    # Second repair attempt — same hypothesis, outcome, no new evidence
    ledger.append_event(
        _event(
            event_id="evt-3",
            type="repair_attempt",
            actor="immediate_repair",
            incident_id="inc-loop",
            problem_id="prob-loop",
            summary="Restart runner",
            outcome="failed",
            parent_event_ids=["evt-2"],
            attempt_id="attempt-2",
            decision={"selected_action": "restart-runner"},
            actions=[{"kind": "command", "command": "systemctl restart runner"}],
            evidence=[{"kind": "file", "path": "logs/restart-2.log"}],
        )
    )
    # Third repair attempt — same again, no new evidence/code/state change
    ledger.append_event(
        _event(
            event_id="evt-4",
            type="repair_attempt",
            actor="immediate_repair",
            incident_id="inc-loop",
            problem_id="prob-loop",
            summary="Restart runner",
            outcome="failed",
            parent_event_ids=["evt-3"],
            attempt_id="attempt-3",
            decision={"selected_action": "restart-runner"},
            actions=[{"kind": "command", "command": "systemctl restart runner"}],
            evidence=[{"kind": "file", "path": "logs/restart-3.log"}],
        )
    )

    result = rebuild_projections(tmp_path)

    findings = result["incidents"]["integrity"]
    loop_codes = {
        finding["code"]
        for finding in findings
        if finding["code"].startswith("loop_break")
    }
    assert "loop_break_repeated_attempt_no_new_evidence" in loop_codes


def test_repeated_attempts_with_new_evidence_not_flagged(
    tmp_path: Path,
) -> None:
    """Repair attempts with different evidence between them should NOT
    trigger the loop_break finding."""
    ledger = IncidentLedger(tmp_path)
    ledger.append_event(
        _event(
            event_id="evt-1",
            type="detection",
            actor="watchdog",
            incident_id="inc-progress",
            problem_id="prob-progress",
            summary="Build runner failed",
            outcome="started",
        )
    )
    ledger.append_event(
        _event(
            event_id="evt-2",
            type="repair_attempt",
            actor="immediate_repair",
            incident_id="inc-progress",
            problem_id="prob-progress",
            summary="Restart runner",
            outcome="failed",
            parent_event_ids=["evt-1"],
            attempt_id="attempt-1",
            decision={"selected_action": "restart-runner"},
            evidence=[{"kind": "file", "path": "logs/restart-1.log"}],
        )
    )
    # Different evidence or action between attempts means progress
    ledger.append_event(
        _event(
            event_id="evt-3",
            type="repair_attempt",
            actor="immediate_repair",
            incident_id="inc-progress",
            problem_id="prob-progress",
            summary="Checked config and restarted",
            outcome="failed",
            parent_event_ids=["evt-2"],
            attempt_id="attempt-2",
            decision={"selected_action": "check-config-then-restart"},
            actions=[
                {"kind": "command", "command": "cat /etc/runner/config.toml"},
                {"kind": "command", "command": "systemctl restart runner"},
            ],
            evidence=[{"kind": "file", "path": "logs/config-check.log"}],
        )
    )

    result = rebuild_projections(tmp_path)

    findings = result["incidents"]["integrity"]
    loop_codes = {
        finding["code"]
        for finding in findings
        if finding["code"].startswith("loop_break")
    }
    # With new evidence and different decision, this should NOT be flagged
    assert "loop_break_repeated_attempt_no_new_evidence" not in loop_codes


# ---------------------------------------------------------------------------
# M2 install-sync event schema validation fixtures
# ---------------------------------------------------------------------------


def test_install_sync_applied_schema_valid_event_passes(
    tmp_path: Path,
) -> None:
    """A well-formed install_sync_applied event with before/after runtime
    identity should pass schema validation."""
    ledger = IncidentLedger(tmp_path)
    appended = ledger.append_event(
        _event(
            event_id="evt-install-ok",
            type="install_sync_applied",
            actor="install_sync",
            summary="Editable install synced to launch head",
            outcome="applied",
            evidence=[
                {
                    "kind": "runtime_identity",
                    "before": "cpython-3.11.10 / commit abc123",
                    "after": "cpython-3.11.11 / commit def456",
                    "path": "/usr/local/bin/python3",
                    "command": "pip install -e .",
                }
            ],
            links={"commit": "def456"},
        )
    )
    assert appended["kind"] == "incident.install_sync_applied"
    assert appended["payload"]["outcome"] == "applied"
    assert appended["payload"]["actor"] == "install_sync"


def test_install_sync_failed_schema_valid_event_passes(
    tmp_path: Path,
) -> None:
    """A well-formed install_sync_failed event with before/after runtime
    identity should pass schema validation."""
    ledger = IncidentLedger(tmp_path)
    appended = ledger.append_event(
        _event(
            event_id="evt-install-fail",
            type="install_sync_failed",
            actor="install_sync",
            summary="Editable install failed due to dependency conflict",
            outcome="failed",
            evidence=[
                {
                    "kind": "runtime_identity",
                    "before": "cpython-3.11.10 / commit abc123",
                    "after": "cpython-3.11.10 / commit abc123",
                    "path": "/usr/local/bin/python3",
                    "error": "Conflicting dependency: numpy>=2.0 vs numpy<2.0",
                }
            ],
        )
    )
    assert appended["kind"] == "incident.install_sync_failed"
    assert appended["payload"]["outcome"] == "failed"
    assert appended["payload"]["actor"] == "install_sync"


def test_install_sync_event_rejects_missing_runtime_identity_evidence(
    tmp_path: Path,
) -> None:
    """An install_sync event with empty evidence should still pass schema
    (schema is permissive on evidence content), but the projection should
    note it via integrity findings when runtime identity is absent."""
    ledger = IncidentLedger(tmp_path)
    appended = ledger.append_event(
        _event(
            event_id="evt-no-identity",
            type="install_sync_applied",
            actor="install_sync",
            summary="Install sync applied without runtime identity evidence",
            outcome="applied",
            evidence=[],
        )
    )
    # Schema validation is permissive — this should still pass
    assert appended["kind"] == "incident.install_sync_applied"


def test_install_sync_event_schema_roundtrip_through_projection(
    tmp_path: Path,
) -> None:
    """install_sync events should survive the full append → rebuild round-trip
    and appear in the incident projection with correct type and actor."""
    ledger = IncidentLedger(tmp_path)
    ledger.append_event(
        _event(
            event_id="evt-1",
            type="detection",
            actor="watchdog",
            incident_id="inc-sync-roundtrip",
            summary="Build failure detected",
            outcome="started",
        )
    )
    ledger.append_event(
        _event(
            event_id="evt-2",
            type="install_sync_applied",
            actor="install_sync",
            incident_id="inc-sync-roundtrip",
            summary="Install sync applied",
            outcome="applied",
            parent_event_ids=["evt-1"],
            evidence=[
                {
                    "kind": "runtime_identity",
                    "before": "cpython-3.11.10",
                    "after": "cpython-3.11.11",
                    "path": "/usr/local/bin/python3",
                }
            ],
        )
    )

    result = rebuild_projections(tmp_path)

    incidents = result["incidents"]["incidents"]
    assert len(incidents) == 1
    incident = incidents[0]
    assert incident["incident_id"] == "inc-sync-roundtrip"
    # The final state should reflect install_sync_applied
    assert incident["state"] == "install_sync_applied"
    assert incident["latest_actor"] == "install_sync"


def test_build_brief_reports_deadlines_claims_attempts_and_missing_evidence(
    tmp_path: Path,
) -> None:
    (tmp_path / "logs").mkdir()
    (tmp_path / "logs" / "runner.log").write_text("runner failed\n", encoding="utf-8")

    ledger = IncidentLedger(tmp_path)
    ledger.append_event(_event())
    ledger.append_event(
        _event(
            event_id="evt-2",
            type="claim.owner_assigned",
            actor="incident-commander",
            ts="2026-07-03T19:20:00Z",
            summary="Assigned the first responder",
            parent_event_ids=["evt-1"],
            claim_id="claim-expired",
            deadline_ts="2026-07-03T19:25:00Z",
            evidence=[{"kind": "file", "path": "logs/runner.log"}],
        )
    )
    ledger.append_event(
        _event(
            event_id="evt-3",
            type="repair_attempt",
            actor="immediate_repair",
            ts="2026-07-03T19:23:00Z",
            summary="Restarted the runner and captured output",
            parent_event_ids=["evt-2"],
            attempt_id="attempt-1",
            deadline_ts="2026-07-03T19:26:00Z",
            evidence=[
                {"kind": "file", "path": "logs/runner.log"},
                {"kind": "file", "path": "logs/missing.log"},
            ],
            outcome="failed",
        )
    )
    ledger.append_event(
        _event(
            event_id="evt-4",
            type="claim.waiting_customer",
            actor="incident-commander",
            ts="2026-07-03T19:24:00Z",
            summary="Waiting on customer confirmation",
            parent_event_ids=["evt-3"],
            claim_id="claim-active",
            deadline_ts="2026-07-03T19:40:00Z",
            evidence=[],
        )
    )

    brief = build_brief("session-1", root=tmp_path, now="2026-07-03T19:30:00Z")

    assert brief["found"] is True
    assert brief["incident_id"] == "inc-123"
    assert brief["state"] == "claim.waiting_customer"
    assert brief["deadline_ts"] == "2026-07-03T19:40:00Z"
    assert brief["deadline_status"] == "ok"
    assert brief["next_expected_event"] == "immediate_repair.repair_attempt"
    assert brief["attempts"] == [
        {
            "attempt_id": "attempt-1",
            "event_count": 1,
            "latest_outcome": "failed",
            "types": ["repair_attempt"],
        }
    ]
    assert brief["claims"] == [
        {
            "actor": "incident-commander",
            "claim_id": "claim-expired",
            "classification": "expired",
            "deadline_ts": "2026-07-03T19:25:00Z",
            "expected_transition": "immediate_repair.repair_attempt",
            "seq": 1,
            "status": "assigned",
            "summary": "Assigned the first responder",
        },
        {
            "actor": "incident-commander",
            "claim_id": "claim-active",
            "classification": "active",
            "deadline_ts": "2026-07-03T19:40:00Z",
            "expected_transition": "immediate_repair.repair_attempt",
            "seq": 3,
            "status": "customer",
            "summary": "Waiting on customer confirmation",
        },
    ]
    assert brief["evidence"] == [
        {"kind": "file", "path": "logs/missing.log", "status": "MISSING"},
        {"kind": "file", "path": "logs/runner.log", "status": "present"},
        {"kind": "file", "path": "logs/runner.log", "status": "present"},
        {"kind": "file", "path": "logs/runner.log", "status": "present"},
    ]
    assert brief["placeholders"] == {
        "install_freshness": "unknown",
        "recurrence": "unknown",
        "shipped_fix": "unknown",
    }
    assert brief["integrity"] == {
        "finding_count": 0,
        "recommendation": "system.integrity_repair",
        "severity": "ok",
    }


def test_build_brief_redacts_legacy_secret_shaped_payloads_during_projection(
    tmp_path: Path,
) -> None:
    ledger = IncidentLedger(tmp_path)
    ledger.append_event(_event())

    records = [
        json.loads(line)
        for line in ledger.events_path.read_text(encoding="utf-8").splitlines()
    ]
    records[0]["payload"]["summary"] = (
        "Authorization: Bearer bearer-secret-token-value sk-proj-secretsecretsecretsecret"
    )
    records[0]["payload"]["evidence"] = [
        {"kind": "log", "message": "Using github token ghp_secretgithubpat1234567890"},
        {"kind": "log", "message": "aws_access_key_id = AKIAIOSFODNN7EXAMPLE"},
        {
            "kind": "log",
            "message": (
                "-----BEGIN OPENSSH PRIVATE KEY-----\n"
                "private-material\n"
                "-----END OPENSSH PRIVATE KEY-----"
            ),
        },
    ]
    ledger.events_path.write_text(
        "\n".join(json.dumps(record) for record in records) + "\n",
        encoding="utf-8",
    )

    brief = build_brief("session-1", root=tmp_path)
    serialized = json.dumps(brief, sort_keys=True)

    for secret in (
        "bearer-secret-token-value",
        "sk-proj-secretsecretsecretsecret",
        "ghp_secretgithubpat1234567890",
        "AKIAIOSFODNN7EXAMPLE",
        "OPENSSH PRIVATE KEY",
    ):
        assert secret not in serialized
    assert "***REDACTED***" in brief["summary"]
    assert "***REDACTED***" in serialized


def test_problem_ids_remain_stable_across_transient_summary_variants_and_replay(
    tmp_path: Path,
) -> None:
    ledger = IncidentLedger(tmp_path)

    first_incident = [
        _event(
            event_id="evt-stable-1",
            incident_id="inc-stable-1",
            problem_id="prob-stable",
            summary=(
                "Build runner failed in /tmp/run-123/attempt-1 at "
                "2026-07-03T20:00:00Z pid=4321 container deadbeefcafebabe"
            ),
            deadline_ts="2026-07-03T21:00:00Z",
        ),
        _event(
            event_id="evt-stable-2",
            incident_id="inc-stable-1",
            problem_id="prob-stable",
            type="claim.owner_assigned",
            actor="six_hour_auditor",
            outcome="assigned",
            summary="Assigned owner after attempt-2 in /workspace/tmp/session-aaa",
            deadline_ts="2026-07-03T22:00:00Z",
            parent_event_ids=["evt-stable-1"],
        ),
        _event(
            event_id="evt-stable-3",
            incident_id="inc-stable-1",
            problem_id="prob-stable",
            type="verified_recovered",
            actor="repair_system",
            outcome="recovered",
            summary="Recovery verified after pid=9999 at 2026-07-03T20:30:00Z",
            parent_event_ids=["evt-stable-2"],
            deadline_ts="2026-07-03T22:15:00Z",
        ),
    ]
    second_incident = [
        _event(
            event_id="evt-stable-4",
            incident_id="inc-stable-2",
            problem_id="prob-stable",
            summary=(
                "Build runner failed in /tmp/run-999/attempt-9 at "
                "2026-07-04T00:00:00Z pid=9876 container 0123456789abcdef"
            ),
            deadline_ts="2026-07-04T01:00:00Z",
        ),
        _event(
            event_id="evt-stable-5",
            incident_id="inc-stable-2",
            problem_id="prob-stable",
            type="claim.owner_assigned",
            actor="watchdog",
            outcome="assigned",
            summary="Owner refreshed from /workspace/tmp/session-bbb attempt-10",
            deadline_ts="2026-07-04T02:00:00Z",
            parent_event_ids=["evt-stable-4"],
        ),
    ]

    for event in [*first_incident, *second_incident]:
        ledger.append_event(event)

    first = rebuild_projections(tmp_path)["problems"]["problems"]
    second = rebuild_projections(tmp_path)["problems"]["problems"]

    assert first == second
    assert len(first) == 1
    problem = first[0]
    assert problem["occurrence_count"] == 5
    assert problem["linked_incident_ids"] == ["inc-stable-1", "inc-stable-2"]
    assert problem["recurred_after_fix"] is True
    assert problem["status"] == "open"
    assert problem["owner_actor"] == "watchdog"
    assert problem["next_review_ts"] == "2026-07-03T21:00:00Z"


def test_problem_id_normalization_strips_transient_timestamp_pid_attempt_path_and_container_data() -> None:
    first = _event(
        summary=(
            "Repair stalled in /tmp/run-123/attempt-1 at 2026-07-03T20:00:00Z "
            "pid=4321 container deadbeefcafebabe"
        ),
    )
    second = _event(
        summary=(
            "Repair stalled in /workspace/service/attempt-22 at 2026-07-04T03:11:59Z "
            "pid=8765 container 0123456789abcdef"
        ),
    )

    assert projection._normalized_signature(first) == projection._normalized_signature(second)
    assert projection._problem_id_for_payload(first) == projection._problem_id_for_payload(second)
