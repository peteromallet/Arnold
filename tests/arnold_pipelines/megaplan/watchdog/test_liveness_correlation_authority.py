"""M9 — T17: Watchdog liveness correlation as correlated evidence only.

These tests pin the contract that process, tmux, heartbeat, and activity facts
joined to WBC attempt identity produce correlated evidence — *never* success,
repair, completion, or dispatch authority. Recycled, hung, dead, and unrelated
workers must classify as ``unknown`` or ``lost``; even a fully ``matched`` live
worker resolves to ``unknown`` (a live worker proves an in-flight attempt, not
success).
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.watchdog.correlate import (
    LIVENESS_DEAD,
    LIVENESS_HUNG,
    LIVENESS_MATCHED,
    LIVENESS_RECYCLED,
    LIVENESS_UNRELATED,
    RUNNER_LOST,
    RUNNER_UNKNOWN,
    WorkerLivenessClassification,
    _collect_liveness_evidence_gaps,
    _format_source_cursor,
    classify_worker_liveness,
)
from arnold_pipelines.megaplan.watchdog.processes import (
    ProcessRecord,
    _extract_runner_lease_ref,
    _extract_session_token,
    scan_processes,
)
from arnold_pipelines.megaplan.watchdog.snapshot import build_snapshot


# Verdicts that liveness MUST NEVER produce. If any classification path returns
# one of these, liveness has been upgraded into terminal/completion authority —
# a North-Star violation.
_FORBIDDEN_VERDICTS = frozenset({"success", "repair", "complete", "completed", "verified"})


def _proc(
    *,
    pid: int = 1,
    is_live: bool = True,
    session_token: str | None = "S1",
    birth_time_seconds: float | None = 100.0,
) -> ProcessRecord:
    return ProcessRecord(
        pid=pid,
        cmdline="arnold --session S1 demo-plan",
        category="arnold",
        is_live=is_live,
        session_token=session_token,
        birth_time_seconds=birth_time_seconds,
    )


# ──────────────────────────────────────────────────────────────────────────────
# classify_worker_liveness — the 5 canonical classifications
# ──────────────────────────────────────────────────────────────────────────────


class TestMatchedWorkerIsUnknownNotSuccess:
    """A live worker with matching identity is still ``unknown`` — never success."""

    def test_matched_live_worker_resolves_to_unknown(self):
        v = classify_worker_liveness(
            _proc(is_live=True, session_token="S1", birth_time_seconds=100.0),
            attempt_session_token="S1",
            attempt_start_epoch=200.0,
            runner_lease_ref="lease-1",
            heartbeat_fresh=True,
            wbc_attempt_identity_supplied=True,
        )
        assert v.classification == LIVENESS_MATCHED
        assert v.runner_verdict == RUNNER_UNKNOWN
        assert v.runner_verdict not in _FORBIDDEN_VERDICTS

    def test_matched_with_unobserved_heartbeat_still_unknown(self):
        v = classify_worker_liveness(
            _proc(),
            attempt_session_token="S1",
            attempt_start_epoch=200.0,
            heartbeat_fresh=None,
            wbc_attempt_identity_supplied=True,
        )
        assert v.classification == LIVENESS_MATCHED
        assert v.runner_verdict == RUNNER_UNKNOWN

    def test_matched_never_carries_terminal_authority(self):
        v = classify_worker_liveness(
            _proc(),
            attempt_session_token="S1",
            attempt_start_epoch=200.0,
            heartbeat_fresh=True,
            wbc_attempt_identity_supplied=True,
        )
        assert v.authority == "evidence_extracted_non_authoritative"


class TestRecycledPidClassifiedAsUnknown:
    """A recycled PID (birth postdates attempt start) is ``unknown``."""

    def test_pid_birth_after_attempt_start_is_recycled(self):
        v = classify_worker_liveness(
            _proc(birth_time_seconds=300.0),
            attempt_session_token="S1",
            attempt_start_epoch=100.0,
            heartbeat_fresh=True,
            wbc_attempt_identity_supplied=True,
        )
        assert v.classification == LIVENESS_RECYCLED
        assert v.runner_verdict == RUNNER_UNKNOWN
        assert v.runner_verdict not in _FORBIDDEN_VERDICTS

    def test_session_token_mismatch_is_recycled(self):
        v = classify_worker_liveness(
            _proc(session_token="OTHER", birth_time_seconds=50.0),
            attempt_session_token="S1",
            attempt_start_epoch=100.0,
            heartbeat_fresh=True,
            wbc_attempt_identity_supplied=True,
        )
        assert v.classification == LIVENESS_RECYCLED
        assert v.runner_verdict == RUNNER_UNKNOWN

    def test_recycled_carries_pid_birth_gap(self):
        v = classify_worker_liveness(
            _proc(birth_time_seconds=300.0),
            attempt_session_token="S1",
            attempt_start_epoch=100.0,
            heartbeat_fresh=True,
            wbc_attempt_identity_supplied=True,
        )
        assert "recycled_pid" in v.evidence_gaps
        assert v.evidence_gaps["recycled_pid"]["evidence_status"] == "conflict"


class TestHungWorkerClassifiedAsLost:
    """A live worker with a stale heartbeat is ``lost`` (hung), not ``unknown``."""

    def test_live_with_stale_heartbeat_is_hung(self):
        v = classify_worker_liveness(
            _proc(),
            attempt_session_token="S1",
            attempt_start_epoch=200.0,
            heartbeat_fresh=False,
            wbc_attempt_identity_supplied=True,
        )
        assert v.classification == LIVENESS_HUNG
        assert v.runner_verdict == RUNNER_LOST
        assert v.runner_verdict not in _FORBIDDEN_VERDICTS

    def test_hung_carries_heartbeat_stale_gap(self):
        v = classify_worker_liveness(
            _proc(),
            attempt_session_token="S1",
            attempt_start_epoch=200.0,
            heartbeat_fresh=False,
            wbc_attempt_identity_supplied=True,
        )
        assert v.evidence_gaps["heartbeat_freshness"]["evidence_status"] == "stale"


class TestDeadWorkerClassifiedAsLost:
    """A non-live worker is ``dead`` → ``lost``, regardless of identity match."""

    def test_dead_worker_is_lost(self):
        v = classify_worker_liveness(
            _proc(is_live=False),
            attempt_session_token="S1",
            attempt_start_epoch=200.0,
            heartbeat_fresh=True,
            wbc_attempt_identity_supplied=True,
        )
        assert v.classification == LIVENESS_DEAD
        assert v.runner_verdict == RUNNER_LOST
        assert v.runner_verdict not in _FORBIDDEN_VERDICTS

    def test_dead_takes_precedence_over_session_match(self):
        # Dead wins even when identity would otherwise match.
        v = classify_worker_liveness(
            _proc(is_live=False, session_token="S1", birth_time_seconds=50.0),
            attempt_session_token="S1",
            attempt_start_epoch=200.0,
            heartbeat_fresh=True,
            wbc_attempt_identity_supplied=True,
        )
        assert v.classification == LIVENESS_DEAD


class TestUnrelatedWorkerClassifiedAsUnknown:
    """A worker with no WBC attempt identity join is ``unrelated`` → ``unknown``."""

    def test_no_attempt_identity_supplied_is_unrelated(self):
        v = classify_worker_liveness(
            _proc(),
            attempt_session_token=None,
            attempt_start_epoch=None,
            heartbeat_fresh=True,
            wbc_attempt_identity_supplied=False,
        )
        assert v.classification == LIVENESS_UNRELATED
        assert v.runner_verdict == RUNNER_UNKNOWN
        assert v.runner_verdict not in _FORBIDDEN_VERDICTS

    def test_unrelated_carries_wbc_identity_gap(self):
        v = classify_worker_liveness(
            _proc(),
            wbc_attempt_identity_supplied=False,
        )
        assert "wbc_attempt_identity" in v.evidence_gaps


# ──────────────────────────────────────────────────────────────────────────────
# Authority trap — no path produces success/repair/completion
# ──────────────────────────────────────────────────────────────────────────────


class TestNoPathProducesTerminalAuthority:
    """Exhaustive matrix: no input combination yields a forbidden verdict."""

    @pytest.mark.parametrize(
        "is_live,session,birth,attempt_session,attempt_start,hb_fresh,supplied",
        [
            # matched variants
            (True, "S1", 50.0, "S1", 100.0, True, True),
            (True, "S1", 50.0, "S1", 100.0, None, True),
            # recycled variants
            (True, "S1", 300.0, "S1", 100.0, True, True),
            (True, "OTHER", 50.0, "S1", 100.0, True, True),
            # hung
            (True, "S1", 50.0, "S1", 100.0, False, True),
            # dead
            (False, "S1", 50.0, "S1", 100.0, True, True),
            (False, None, None, None, None, None, False),
            # unrelated / no identity
            (True, "S1", 50.0, None, None, True, False),
            (True, None, None, None, None, None, False),
            # edge: live but no session anywhere
            (True, None, 50.0, "S1", 100.0, True, True),
        ],
    )
    def test_no_forbidden_verdict(
        self, is_live, session, birth, attempt_session, attempt_start, hb_fresh, supplied
    ):
        v = classify_worker_liveness(
            _proc(is_live=is_live, session_token=session, birth_time_seconds=birth),
            attempt_session_token=attempt_session,
            attempt_start_epoch=attempt_start,
            heartbeat_fresh=hb_fresh,
            wbc_attempt_identity_supplied=supplied,
        )
        assert v.runner_verdict not in _FORBIDDEN_VERDICTS, (
            f"classification={v.classification} yielded forbidden verdict "
            f"{v.runner_verdict!r}"
        )
        assert v.authority == "evidence_extracted_non_authoritative"
        assert v.classification in {
            LIVENESS_MATCHED,
            LIVENESS_RECYCLED,
            LIVENESS_HUNG,
            LIVENESS_DEAD,
            LIVENESS_UNRELATED,
        }

    def test_runner_verdict_universe_is_bounded(self):
        """Only ``unknown`` and ``lost`` are ever produced."""
        seen = set()
        for is_live in (True, False):
            for session in (None, "S1", "OTHER"):
                for birth in (None, 50.0, 300.0):
                    for attempt_session in (None, "S1"):
                        for attempt_start in (None, 100.0, 200.0):
                            for hb in (None, True, False):
                                for supplied in (True, False):
                                    v = classify_worker_liveness(
                                        _proc(
                                            is_live=is_live,
                                            session_token=session,
                                            birth_time_seconds=birth,
                                        ),
                                        attempt_session_token=attempt_session,
                                        attempt_start_epoch=attempt_start,
                                        heartbeat_fresh=hb,
                                        wbc_attempt_identity_supplied=supplied,
                                    )
                                    seen.add(v.runner_verdict)
        assert seen <= {RUNNER_UNKNOWN, RUNNER_LOST}, seen


# ──────────────────────────────────────────────────────────────────────────────
# Evidence gaps are structured {gap, reason, evidence_status} triples
# ──────────────────────────────────────────────────────────────────────────────


class TestEvidenceGapsAreStructured:
    def test_missing_session_token_gap(self):
        gaps = _collect_liveness_evidence_gaps(
            process=_proc(),
            attempt_session_token=None,
            attempt_start_epoch=100.0,
            runner_lease_ref="L",
            heartbeat_fresh=True,
            heartbeat_age_seconds=None,
            wbc_attempt_identity_supplied=True,
        )
        g = gaps["attempt_session_token"]
        assert set(g.keys()) == {"gap", "reason", "evidence_status"}
        assert g["evidence_status"] == "missing"

    def test_recycled_pid_gap_is_conflict(self):
        gaps = _collect_liveness_evidence_gaps(
            process=_proc(birth_time_seconds=300.0),
            attempt_session_token="S1",
            attempt_start_epoch=100.0,
            runner_lease_ref="L",
            heartbeat_fresh=True,
            heartbeat_age_seconds=None,
            wbc_attempt_identity_supplied=True,
        )
        assert gaps["recycled_pid"]["evidence_status"] == "conflict"

    def test_dead_process_gap(self):
        gaps = _collect_liveness_evidence_gaps(
            process=_proc(is_live=False),
            attempt_session_token="S1",
            attempt_start_epoch=100.0,
            runner_lease_ref="L",
            heartbeat_fresh=True,
            heartbeat_age_seconds=None,
            wbc_attempt_identity_supplied=True,
        )
        assert gaps["process_liveness"]["evidence_status"] == "dead"

    def test_no_gaps_when_everything_matches(self):
        gaps = _collect_liveness_evidence_gaps(
            process=_proc(is_live=True, session_token="S1", birth_time_seconds=50.0),
            attempt_session_token="S1",
            attempt_start_epoch=100.0,
            runner_lease_ref="L",
            heartbeat_fresh=True,
            heartbeat_age_seconds=1.0,
            wbc_attempt_identity_supplied=True,
        )
        # A fully-matched worker has no liveness gaps.
        assert gaps == {}


# ──────────────────────────────────────────────────────────────────────────────
# ProcessRecord extraction helpers — best-effort, evidence only
# ──────────────────────────────────────────────────────────────────────────────


class TestSessionTokenExtraction:
    @pytest.mark.parametrize(
        "cmdline,expected",
        [
            ("arnold --session S1 demo", "S1"),
            ("arnold --session-id TOK-2 demo", "TOK-2"),
            ("MEGAPLAN_SESSION=ENV1 arnold", "ENV1"),
            ("arnold MEGAPLAN_SESSION=ENV1 demo", "ENV1"),
            ("arnold --env ARNOLD_SESSION=AR1", "AR1"),
            ("arnold --env RUN_SESSION=RS9 demo", "RS9"),
            ("arnold demo-plan", None),
            ("", None),
        ],
    )
    def test_extract_session_token(self, cmdline, expected):
        assert _extract_session_token(cmdline) == expected


class TestRunnerLeaseExtraction:
    @pytest.mark.parametrize(
        "cmdline,expected",
        [
            ("arnold --lease L1 demo", "L1"),
            ("arnold --lease-id LID2 demo", "LID2"),
            ("arnold --runner-lease RL3 demo", "RL3"),
            ("RUNNER_LEASE=RL4 arnold", "RL4"),
            ("arnold RUNNER_LEASE=RL4 demo", "RL4"),
            ("arnold demo-plan", None),
            ("", None),
        ],
    )
    def test_extract_runner_lease_ref(self, cmdline, expected):
        assert _extract_runner_lease_ref(cmdline) == expected


class TestScanProcessesExtractsCorrelationFields:
    """scan_processes populates birth_time / session_token / runner_lease_ref."""

    def test_metadata_format_extracts_fields(self):
        # Build ps-style line: pid ppid etime time args
        # Use a large enough elapsed so birth_time_seconds is well below now.
        lines = [
            "  PID  PPID     ELAPSED     TIME COMMAND",
            "100 1 10:00:00 00:00:01 arnold --session S1 --lease L1 demo-plan",
        ]
        records = scan_processes(lines)
        assert len(records) == 1
        r = records[0]
        assert r.session_token == "S1"
        assert r.runner_lease_ref == "L1"
        assert r.birth_time_seconds is not None
        assert r.birth_time_seconds > 0

    def test_legacy_format_extracts_session_token(self):
        lines = ["PID args", "100 arnold --session S1 demo"]
        records = scan_processes(lines)
        assert len(records) == 1
        assert records[0].session_token == "S1"


# ──────────────────────────────────────────────────────────────────────────────
# Source cursor formatting — display only
# ──────────────────────────────────────────────────────────────────────────────


class TestSourceCursorFormatting:
    def test_present_cursor_is_display_only(self):
        out = _format_source_cursor({"plan_state": "abc"})
        assert out["authority"] == "evidence_extracted_display_only"
        assert out["value"] == {"plan_state": "abc"}

    def test_absent_cursor_marked_absent(self):
        out = _format_source_cursor(None)
        assert out["authority"] == "absent"
        assert "reason" in out

    def test_empty_cursor_marked_absent(self):
        out = _format_source_cursor({})
        assert out["authority"] == "absent"


# ──────────────────────────────────────────────────────────────────────────────
# build_snapshot — end-to-end authority trap
# ──────────────────────────────────────────────────────────────────────────────


def _make_repo_with_plan(tmpdir: str, plan_name: str = "demo-plan") -> Path:
    repo = Path(tmpdir) / "repo"
    plan_dir = repo / ".megaplan" / "plans" / plan_name
    plan_dir.mkdir(parents=True)
    (plan_dir / "state.json").write_text(
        json.dumps({"name": plan_name, "repo_path": str(repo)})
    )
    return repo


class TestBuildSnapshotLivenessIsEvidenceOnly:
    def test_matched_incident_is_unknown_with_display_cursor(self):
        with tempfile.TemporaryDirectory() as td:
            repo = _make_repo_with_plan(td)
            plan_id = "demo-plan"

            def scanner():
                return (
                    ProcessRecord(
                        pid=100,
                        cmdline="arnold --session S1 demo-plan",
                        category="arnold",
                        is_live=True,
                        cwd=str(repo / ".megaplan" / "plans" / plan_id),
                        session_token="S1",
                        birth_time_seconds=50.0,
                    ),
                )

            snap = build_snapshot(
                roots=(str(repo),),
                process_scanner=scanner,
                source_cursor_vector={"plan_state": "abc123"},
                wbc_terminal_envelopes={
                    plan_id: {"session": "S1", "attempt_start_epoch": 100.0}
                },
                heartbeat_fresh_by_plan={plan_id: True},
            )
            assert len(snap.incidents) == 1
            inc = snap.incidents[0]
            # Matched → unknown, NEVER success.
            assert inc.liveness_authority["classification"] == LIVENESS_MATCHED
            assert inc.liveness_authority["runner_verdict"] == RUNNER_UNKNOWN
            assert inc.liveness_authority["runner_verdict"] not in _FORBIDDEN_VERDICTS
            assert inc.liveness_authority["authority"] == "evidence_extracted_non_authoritative"
            # Snapshot-level annotations are display-only.
            assert snap.source_cursor_vector["authority"] == "evidence_extracted_display_only"
            assert snap.liveness_authority["authority"] == "evidence_extracted_non_authoritative"

    def test_recycled_pid_incident_is_unknown(self):
        with tempfile.TemporaryDirectory() as td:
            repo = _make_repo_with_plan(td)
            plan_id = "demo-plan"

            def scanner():
                return (
                    ProcessRecord(
                        pid=100,
                        cmdline="arnold --session S1 demo-plan",
                        category="arnold",
                        is_live=True,
                        cwd=str(repo / ".megaplan" / "plans" / plan_id),
                        session_token="S1",
                        # Birth AFTER the attempt start → recycled PID.
                        birth_time_seconds=300.0,
                    ),
                )

            snap = build_snapshot(
                roots=(str(repo),),
                process_scanner=scanner,
                wbc_terminal_envelopes={
                    plan_id: {"session": "S1", "attempt_start_epoch": 100.0}
                },
                heartbeat_fresh_by_plan={plan_id: True},
            )
            inc = snap.incidents[0]
            assert inc.liveness_authority["classification"] == LIVENESS_RECYCLED
            assert inc.liveness_authority["runner_verdict"] == RUNNER_UNKNOWN
            assert inc.liveness_authority["runner_verdict"] not in _FORBIDDEN_VERDICTS

    def test_dead_incident_is_lost(self):
        with tempfile.TemporaryDirectory() as td:
            repo = _make_repo_with_plan(td)
            plan_id = "demo-plan"

            def scanner():
                return (
                    ProcessRecord(
                        pid=100,
                        cmdline="arnold --session S1 demo-plan",
                        category="arnold",
                        is_live=False,
                        cwd=str(repo / ".megaplan" / "plans" / plan_id),
                        session_token="S1",
                        birth_time_seconds=50.0,
                    ),
                )

            snap = build_snapshot(
                roots=(str(repo),),
                process_scanner=scanner,
                wbc_terminal_envelopes={
                    plan_id: {"session": "S1", "attempt_start_epoch": 100.0}
                },
                heartbeat_fresh_by_plan={plan_id: True},
            )
            inc = snap.incidents[0]
            assert inc.liveness_authority["classification"] == LIVENESS_DEAD
            assert inc.liveness_authority["runner_verdict"] == RUNNER_LOST
            assert inc.liveness_authority["runner_verdict"] not in _FORBIDDEN_VERDICTS

    def test_no_wbc_identity_is_unrelated_unknown(self):
        with tempfile.TemporaryDirectory() as td:
            repo = _make_repo_with_plan(td)
            plan_id = "demo-plan"

            def scanner():
                return (
                    ProcessRecord(
                        pid=100,
                        cmdline="arnold --session S1 demo-plan",
                        category="arnold",
                        is_live=True,
                        cwd=str(repo / ".megaplan" / "plans" / plan_id),
                        session_token="S1",
                        birth_time_seconds=50.0,
                    ),
                )

            # No WBC envelopes supplied → identity join is absent.
            snap = build_snapshot(roots=(str(repo),), process_scanner=scanner)
            inc = snap.incidents[0]
            assert inc.liveness_authority["classification"] == LIVENESS_UNRELATED
            assert inc.liveness_authority["runner_verdict"] == RUNNER_UNKNOWN

    def test_no_correlated_process_is_unrelated_unknown(self):
        with tempfile.TemporaryDirectory() as td:
            repo = _make_repo_with_plan(td)
            plan_id = "demo-plan"

            def scanner():
                return ()  # no processes at all

            snap = build_snapshot(
                roots=(str(repo),),
                process_scanner=scanner,
                wbc_terminal_envelopes={
                    plan_id: {"session": "S1", "attempt_start_epoch": 100.0}
                },
            )
            inc = snap.incidents[0]
            assert inc.liveness_authority["classification"] == LIVENESS_UNRELATED
            assert inc.liveness_authority["runner_verdict"] == RUNNER_UNKNOWN
            assert inc.liveness_authority["runner_verdict"] not in _FORBIDDEN_VERDICTS

    def test_snapshot_summary_worst_verdict_never_success(self):
        with tempfile.TemporaryDirectory() as td:
            repo = _make_repo_with_plan(td)
            plan_id = "demo-plan"

            def scanner():
                return (
                    ProcessRecord(
                        pid=100,
                        cmdline="arnold --session S1 demo-plan",
                        category="arnold",
                        is_live=False,
                        cwd=str(repo / ".megaplan" / "plans" / plan_id),
                        session_token="S1",
                        birth_time_seconds=50.0,
                    ),
                )

            snap = build_snapshot(
                roots=(str(repo),),
                process_scanner=scanner,
                wbc_terminal_envelopes={
                    plan_id: {"session": "S1", "attempt_start_epoch": 100.0}
                },
            )
            worst = snap.liveness_authority["worst_runner_verdict"]
            assert worst in {RUNNER_UNKNOWN, RUNNER_LOST}
            assert worst not in _FORBIDDEN_VERDICTS

    def test_heartbeat_stale_drives_hung_classification(self):
        with tempfile.TemporaryDirectory() as td:
            repo = _make_repo_with_plan(td)
            plan_id = "demo-plan"

            def scanner():
                return (
                    ProcessRecord(
                        pid=100,
                        cmdline="arnold --session S1 demo-plan",
                        category="arnold",
                        is_live=True,
                        cwd=str(repo / ".megaplan" / "plans" / plan_id),
                        session_token="S1",
                        birth_time_seconds=50.0,
                    ),
                )

            snap = build_snapshot(
                roots=(str(repo),),
                process_scanner=scanner,
                wbc_terminal_envelopes={
                    plan_id: {"session": "S1", "attempt_start_epoch": 100.0}
                },
                heartbeat_fresh_by_plan={plan_id: False},
            )
            inc = snap.incidents[0]
            assert inc.liveness_authority["classification"] == LIVENESS_HUNG
            assert inc.liveness_authority["runner_verdict"] == RUNNER_LOST


# ──────────────────────────────────────────────────────────────────────────────
# WorkerLivenessClassification serialization
# ──────────────────────────────────────────────────────────────────────────────


class TestClassificationSerialization:
    def test_to_dict_round_trip_carries_authority(self):
        v = classify_worker_liveness(
            _proc(),
            attempt_session_token="S1",
            attempt_start_epoch=200.0,
            heartbeat_fresh=True,
            wbc_attempt_identity_supplied=True,
        )
        d = v.to_dict()
        assert set(d.keys()) == {
            "classification",
            "runner_verdict",
            "reason",
            "evidence_basis",
            "evidence_gaps",
            "authority",
        }
        assert d["authority"] == "evidence_extracted_non_authoritative"

    def test_classification_is_frozen(self):
        v = classify_worker_liveness(_proc(is_live=False))
        with pytest.raises(Exception):
            v.classification = "success"  # type: ignore[misc]
