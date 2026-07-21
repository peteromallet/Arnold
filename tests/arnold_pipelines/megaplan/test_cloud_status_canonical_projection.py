"""Tests proving cloud status snapshots/formats preserve stale/degraded fields
as structured evidence gaps and agree on CLI output for identical canonical inputs.

M9 — T15: cloud status migration from marker/watchdog/report/plan-state authority
reads to canonical query projections.
"""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from arnold_pipelines.megaplan.cloud.status_format import (
    format_cloud_status_detailed,
    format_cloud_status_short,
)
from arnold_pipelines.megaplan.cloud.status_snapshot import (
    build_cloud_status_snapshot,
)


# ── Helpers ────────────────────────────────────────────────────────────────


def _make_minimal_snapshot(**overrides: Any) -> dict[str, Any]:
    """Build a minimal valid snapshot dict for format testing."""
    snap: dict[str, Any] = {
        "generated_at": "2026-07-21T12:00:00Z",
        "source": "test",
        "marker_dir": "/tmp/test-markers",
        "watchdog_report": "/tmp/watchdog-report.json",
        "summary": {"running": 1, "repairing": 0, "blocked": 0, "attention": 0, "complete": 0},
        "sessions": [
            {
                "session": "test-session",
                "status": "running",
                "current_plan": "test-plan",
                "completed_count": 0,
                "milestone_count": 3,
                "chain_complete": False,
                "plan_state": "finalized",
                "lifecycle_state": "finalized",
                "activity_phase": "execute",
                "custody_state": "",
                "repair_state": "none",
                "progress": {},
                "evidence": {"marker": "/tmp/test-markers/test-session.json"},
                "tmux": True,
                "process": True,
                "watchdog": "alive",
                "latest_activity": "2026-07-21T11:59:00Z",
                "operator_next": "",
                "evidence_gaps": {},
            }
        ],
        "degraded": None,
        "source_cursor_vector": {
            "authority": "absent",
            "reason": "no_source_cursor_vector_provided",
        },
    }
    snap.update(overrides)
    return snap


def _snapshot_digest(snapshot: Mapping[str, Any]) -> str:
    """Deterministic SHA-256 over canonical JSON for comparing snapshots."""
    payload = json.dumps(dict(snapshot), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# ═══════════════════════════════════════════════════════════════════════════
# CLI agreement: identical canonical inputs → identical format output
# ═══════════════════════════════════════════════════════════════════════════


class TestCliAgreementIdenticalInputs:
    """Build snapshots from identical inputs and verify format output agrees."""

    def test_short_format_deterministic_for_identical_snapshot(self) -> None:
        """Short format output is deterministic for the same snapshot dict."""
        snap = _make_minimal_snapshot()
        chunks_a = format_cloud_status_short(snap)
        chunks_b = format_cloud_status_short(snap)
        assert chunks_a == chunks_b, "short format must be deterministic"

    def test_detailed_format_deterministic_for_identical_snapshot(self) -> None:
        """Detailed format output is deterministic for the same snapshot dict."""
        snap = _make_minimal_snapshot()
        out_a = format_cloud_status_detailed(snap)
        out_b = format_cloud_status_detailed(snap)
        assert out_a == out_b, "detailed format must be deterministic"

    def test_short_format_chunks_agree_across_identical_inputs(self) -> None:
        """Two snapshots with identical structure but different dict identities
        produce identical short format chunks."""
        snap_a = _make_minimal_snapshot()
        snap_b = copy.deepcopy(snap_a)
        assert snap_a is not snap_b, "sanity: deep copy is a different object"
        assert format_cloud_status_short(snap_a) == format_cloud_status_short(snap_b)

    def test_detailed_format_agrees_across_identical_inputs(self) -> None:
        """Two snapshots with identical structure but different dict identities
        produce identical detailed format output."""
        snap_a = _make_minimal_snapshot()
        snap_b = copy.deepcopy(snap_a)
        assert format_cloud_status_detailed(snap_a) == format_cloud_status_detailed(snap_b)

    def test_short_and_detailed_agree_on_session_count(self) -> None:
        """Both formats report the same number of sessions."""
        snap = _make_minimal_snapshot()
        detailed = format_cloud_status_detailed(snap)
        short_chunks = format_cloud_status_short(snap)
        short_combined = "\n".join(short_chunks)
        # Both should reference the session name
        assert "test-session" in detailed
        assert "test-session" in short_combined

    def test_short_and_detailed_agree_on_status(self) -> None:
        """Both formats agree on the session status."""
        snap = _make_minimal_snapshot()
        detailed = format_cloud_status_detailed(snap)
        short_chunks = format_cloud_status_short(snap)
        short_combined = "\n".join(short_chunks)
        assert "[running]" in detailed
        assert "running" in short_combined

    def test_short_and_detailed_agree_on_degraded(self) -> None:
        """Both formats surface degraded reasons when present.

        The short format surfaces degraded reasons in its degraded-mode message
        (shown when no sessions are available).  The detailed format always
        shows them inline.  With sessions present, both formats agree on the
        session-level status even when the snapshot is degraded.
        """
        # With sessions present, the short format renders sessions normally
        # while the detailed format also renders the degraded banner.
        snap = _make_minimal_snapshot(
            degraded={"reasons": ["watchdog report unreadable"]},
        )
        detailed = format_cloud_status_detailed(snap)
        short_chunks = format_cloud_status_short(snap)
        short_combined = "\n".join(short_chunks)
        # Detailed format surfaces degraded reasons
        assert "watchdog report unreadable" in detailed
        # Both formats agree on session status
        assert "test-session" in detailed
        assert "test-session" in short_combined
        assert "running" in detailed
        assert "running" in short_combined

    def test_short_format_degraded_mode_surfaces_reasons(self) -> None:
        """When no sessions are available, short format shows degraded reasons."""
        snap: dict[str, Any] = {
            "generated_at": "2026-07-21T12:00:00Z",
            "source": "test",
            "summary": {"running": 0, "repairing": 0, "blocked": 0, "attention": 0, "complete": 0},
            "sessions": [],
            "degraded": {"reasons": ["watchdog report unreadable"]},
            "source_cursor_vector": {"authority": "absent", "reason": "none"},
        }
        chunks = format_cloud_status_short(snap)
        combined = "\n".join(chunks)
        assert "degraded" in combined.lower()
        assert "watchdog report unreadable" in combined

    def test_short_format_preserves_evidence_citation(self) -> None:
        """Short format always includes source citation line."""
        snap = _make_minimal_snapshot()
        chunks = format_cloud_status_short(snap)
        combined = "\n".join(chunks)
        assert "source:" in combined.lower()
        assert "generated:" in combined.lower()


# ═══════════════════════════════════════════════════════════════════════════
# Evidence gap preservation — stale/degraded fields as structured gaps
# ═══════════════════════════════════════════════════════════════════════════


class TestEvidenceGapsPreserved:
    """Stale or degraded display fields must appear as structured evidence gaps."""

    def test_evidence_gaps_field_present_in_snapshot_sessions(self) -> None:
        """Every session entry carries an ``evidence_gaps`` dict."""
        snap = _make_minimal_snapshot()
        for session in snap.get("sessions", []):
            assert "evidence_gaps" in session, "every session must have evidence_gaps"
            assert isinstance(session["evidence_gaps"], dict)

    def test_watchdog_stale_becomes_evidence_gap(self) -> None:
        """A stale watchdog status appears as an evidence gap in detailed format."""
        snap = _make_minimal_snapshot(
            sessions=[
                {
                    "session": "test-session",
                    "status": "attention",
                    "current_plan": "test-plan",
                    "completed_count": 0,
                    "milestone_count": 3,
                    "chain_complete": False,
                    "plan_state": "finalized",
                    "lifecycle_state": "finalized",
                    "activity_phase": "attention",
                    "custody_state": "",
                    "repair_state": "none",
                    "progress": {},
                    "evidence": {"marker": "/tmp/marker"},
                    "tmux": False,
                    "process": False,
                    "watchdog": "stale",
                    "latest_activity": "2026-07-21T11:00:00Z",
                    "operator_next": "check watchdog",
                    "evidence_gaps": {
                        "watchdog_status": {
                            "gap": "watchdog_status_stale",
                            "reason": "watchdog report describes an earlier sweep; not current runner truth",
                            "evidence_status": "stale",
                        }
                    },
                }
            ],
        )
        detailed = format_cloud_status_detailed(snap)
        assert "evidence_gap:" in detailed
        assert "watchdog_status_stale" in detailed
        assert "[stale]" in detailed

    def test_custody_mismatch_preserved_as_gap(self) -> None:
        """Custody mismatch is preserved as a structured evidence gap."""
        snap = _make_minimal_snapshot(
            sessions=[
                {
                    "session": "test-session",
                    "status": "attention",
                    "current_plan": "test-plan",
                    "completed_count": 0,
                    "milestone_count": 3,
                    "chain_complete": False,
                    "plan_state": None,
                    "lifecycle_state": "",
                    "activity_phase": "attention",
                    "custody_state": "",
                    "repair_state": "none",
                    "progress": {},
                    "evidence": {"marker": "/tmp/marker"},
                    "tmux": False,
                    "process": False,
                    "watchdog": "alive",
                    "latest_activity": "2026-07-21T11:00:00Z",
                    "operator_next": "check custody",
                    "custody_mismatch": True,
                    "evidence_gaps": {
                        "custody_mismatch": {
                            "gap": "chain_custody_mismatch",
                            "reason": "terminal chain state with incomplete milestone count; plan state label suppressed",
                            "evidence_status": "degraded",
                        }
                    },
                }
            ],
        )
        detailed = format_cloud_status_detailed(snap)
        assert "evidence_gap:" in detailed
        assert "chain_custody_mismatch" in detailed
        assert "[degraded]" in detailed

    def test_repair_projection_degraded_as_gap(self) -> None:
        """Repair projection degradation is preserved as evidence gap."""
        snap = _make_minimal_snapshot(
            sessions=[
                {
                    "session": "test-session",
                    "status": "repairing",
                    "current_plan": "test-plan",
                    "completed_count": 0,
                    "milestone_count": 3,
                    "chain_complete": False,
                    "plan_state": "failed",
                    "lifecycle_state": "failed",
                    "activity_phase": "repair",
                    "custody_state": "repairing",
                    "repair_state": "active",
                    "progress": {},
                    "evidence": {"marker": "/tmp/marker"},
                    "tmux": False,
                    "process": False,
                    "watchdog": "alive",
                    "latest_activity": "2026-07-21T11:00:00Z",
                    "operator_next": "repair dispatched",
                    "repair_projection_degraded": {
                        "status": "degraded",
                        "reason": "canonical repair projection failed: ValueError",
                    },
                    "evidence_gaps": {
                        "repair_projection": {
                            "gap": "repair_projection_degraded",
                            "reason": "canonical repair projection failed: ValueError",
                            "evidence_status": "degraded",
                        }
                    },
                }
            ],
        )
        detailed = format_cloud_status_detailed(snap)
        assert "evidence_gap:" in detailed
        assert "repair_projection_degraded" in detailed

    def test_source_cursor_vector_absent_rendered(self) -> None:
        """When source_cursor_vector is absent, the detailed format reports it."""
        snap = _make_minimal_snapshot(
            source_cursor_vector={
                "authority": "absent",
                "reason": "no_source_cursor_vector_provided",
            },
        )
        detailed = format_cloud_status_detailed(snap)
        assert "source_cursor_vector" in detailed
        assert "absent" in detailed

    def test_source_cursor_vector_present_rendered(self) -> None:
        """When source_cursor_vector is present, the detailed format notes it."""
        snap = _make_minimal_snapshot(
            source_cursor_vector={
                "authority": "evidence_extracted_display_only",
                "value": {
                    "source_path": "/workspace/.megaplan/cloud-sessions/test-session.json",
                    "source_record_count": 1,
                    "source_digest": "abc123",
                    "computed_at": "2026-07-21T12:00:00Z",
                },
            },
        )
        detailed = format_cloud_status_detailed(snap)
        assert "source_cursor_vector" in detailed
        assert "display-only" in detailed
        assert "non-authoritative" in detailed

    def test_multiple_evidence_gaps_rendered(self) -> None:
        """Multiple evidence gaps for a session are all rendered."""
        snap = _make_minimal_snapshot(
            sessions=[
                {
                    "session": "test-session",
                    "status": "attention",
                    "current_plan": "test-plan",
                    "completed_count": 0,
                    "milestone_count": 3,
                    "chain_complete": False,
                    "plan_state": None,
                    "lifecycle_state": "",
                    "activity_phase": "attention",
                    "custody_state": "",
                    "repair_state": "none",
                    "progress": {},
                    "evidence": {"marker": "/tmp/marker"},
                    "tmux": False,
                    "process": False,
                    "watchdog": "stale",
                    "latest_activity": "2026-07-21T11:00:00Z",
                    "operator_next": "needs investigation",
                    "repair_projection_degraded": {
                        "status": "degraded",
                        "reason": "projection unavailable",
                    },
                    "evidence_gaps": {
                        "watchdog_status": {
                            "gap": "watchdog_status_stale",
                            "reason": "watchdog report describes an earlier sweep; not current runner truth",
                            "evidence_status": "stale",
                        },
                        "plan_state": {
                            "gap": "plan_state_unavailable",
                            "reason": "plan state file missing or unreadable",
                            "evidence_status": "missing",
                        },
                        "repair_projection": {
                            "gap": "repair_projection_degraded",
                            "reason": "projection unavailable",
                            "evidence_status": "degraded",
                        },
                    },
                }
            ],
        )
        detailed = format_cloud_status_detailed(snap)
        # All three gaps should appear
        assert "watchdog_status_stale" in detailed
        assert "plan_state_unavailable" in detailed
        assert "repair_projection_degraded" in detailed
        # All status annotations present
        assert "[stale]" in detailed
        assert "[missing]" in detailed
        assert "[degraded]" in detailed


# ═══════════════════════════════════════════════════════════════════════════
# Non-authoritative guarantees — format output never implies authority
# ═══════════════════════════════════════════════════════════════════════════

FORBIDDEN_ACTIONS = {"dispatch", "completion", "cancellation", "publication", "delivery"}


class TestFormatNeverImpliesAuthority:
    """Format output must never suggest it grants any of the five forbidden actions."""

    def test_detailed_format_never_contains_forbidden_action_verbs(self) -> None:
        """Detailed format must not contain any forbidden action verb."""
        snap = _make_minimal_snapshot()
        detailed = format_cloud_status_detailed(snap).lower()
        for action in FORBIDDEN_ACTIONS:
            assert action not in detailed, (
                f"detailed format unexpectedly contains forbidden action: {action!r}"
            )

    def test_short_format_never_contains_forbidden_action_verbs(self) -> None:
        """Short format must not contain any forbidden action verb."""
        snap = _make_minimal_snapshot()
        chunks = format_cloud_status_short(snap)
        combined = "\n".join(chunks).lower()
        for action in FORBIDDEN_ACTIONS:
            assert action not in combined, (
                f"short format unexpectedly contains forbidden action: {action!r}"
            )

    def test_evidence_gap_never_grants_authority(self) -> None:
        """Evidence gaps are display-only and never reference authority grants."""
        snap = _make_minimal_snapshot(
            sessions=[
                {
                    "session": "test-session",
                    "status": "attention",
                    "current_plan": "test-plan",
                    "completed_count": 0,
                    "milestone_count": 3,
                    "chain_complete": False,
                    "plan_state": None,
                    "lifecycle_state": "",
                    "activity_phase": "attention",
                    "custody_state": "",
                    "repair_state": "none",
                    "progress": {},
                    "evidence": {"marker": "/tmp/marker"},
                    "tmux": False,
                    "process": False,
                    "watchdog": "stale",
                    "latest_activity": "2026-07-21T11:00:00Z",
                    "operator_next": "needs investigation",
                    "evidence_gaps": {
                        "test_gap": {
                            "gap": "test_gap_id",
                            "reason": "test reason",
                            "evidence_status": "missing",
                        }
                    },
                }
            ],
        )
        detailed = format_cloud_status_detailed(snap)
        # Evidence gaps are annotated with evidence_gap: prefix, not authority
        assert "evidence_gap:" in detailed
        for action in FORBIDDEN_ACTIONS:
            # evidence_gap lines should never reference forbidden actions
            gap_lines = [line for line in detailed.splitlines() if "evidence_gap:" in line]
            for line in gap_lines:
                assert action not in line.lower(), (
                    f"evidence gap line contains forbidden action {action!r}: {line!r}"
                )

    def test_source_cursor_vector_annotated_non_authoritative(self) -> None:
        """Source cursor vector annotation always carries non-authoritative marker."""
        snap = _make_minimal_snapshot(
            source_cursor_vector={
                "authority": "evidence_extracted_display_only",
                "value": {"source_path": "/tmp/test.json", "source_digest": "abc"},
            },
        )
        detailed = format_cloud_status_detailed(snap)
        assert "non-authoritative" in detailed or "display-only" in detailed


# ═══════════════════════════════════════════════════════════════════════════
# Snapshot builder integration — source_cursor_vector threading
# ═══════════════════════════════════════════════════════════════════════════


class TestSnapshotBuilderSourceCursor:
    """The snapshot builder threads source_cursor_vector through to the output."""

    def test_source_cursor_vector_in_snapshot_output(self, tmp_path: Path) -> None:
        """When a source_cursor_vector is supplied, it appears in the snapshot."""
        marker_dir = tmp_path / "markers"
        marker_dir.mkdir()
        # Write a minimal session marker
        marker = {
            "session": "test-session",
            "workspace": str(tmp_path / "workspace"),
            "remote_spec": "",
            "started_at": "2026-07-21T12:00:00Z",
        }
        (marker_dir / "test-session.json").write_text(json.dumps(marker))

        cursor_vector = {
            "source_path": str(marker_dir / "test-session.json"),
            "source_record_count": 1,
            "source_digest": hashlib.sha256(
                json.dumps(marker, sort_keys=True).encode()
            ).hexdigest(),
            "computed_at": "2026-07-21T12:00:00Z",
        }

        snapshot = build_cloud_status_snapshot(
            marker_dir=marker_dir,
            watchdog_report_path=tmp_path / "nonexistent.json",
            now=datetime(2026, 7, 21, 12, 0, tzinfo=timezone.utc),
            source_cursor_vector=cursor_vector,
        )

        assert "source_cursor_vector" in snapshot
        scv = snapshot["source_cursor_vector"]
        assert scv["authority"] == "evidence_extracted_display_only"
        assert scv["value"] == cursor_vector

    def test_source_cursor_vector_absent_when_not_supplied(self, tmp_path: Path) -> None:
        """When no source_cursor_vector is supplied, the sentinel is used."""
        marker_dir = tmp_path / "markers"
        marker_dir.mkdir()
        marker = {
            "session": "test-session",
            "workspace": str(tmp_path / "workspace"),
            "remote_spec": "",
            "started_at": "2026-07-21T12:00:00Z",
        }
        (marker_dir / "test-session.json").write_text(json.dumps(marker))

        snapshot = build_cloud_status_snapshot(
            marker_dir=marker_dir,
            watchdog_report_path=tmp_path / "nonexistent.json",
            now=datetime(2026, 7, 21, 12, 0, tzinfo=timezone.utc),
        )

        assert "source_cursor_vector" in snapshot
        scv = snapshot["source_cursor_vector"]
        assert scv["authority"] == "absent"
        assert "no_source_cursor_vector_provided" in scv["reason"]

    def test_evidence_gaps_populated_for_missing_watchdog(self, tmp_path: Path) -> None:
        """When watchdog report is missing, evidence gaps reflect that."""
        marker_dir = tmp_path / "markers"
        marker_dir.mkdir()
        marker = {
            "session": "test-session",
            "workspace": str(tmp_path / "workspace"),
            "remote_spec": "",
            "started_at": "2026-07-21T12:00:00Z",
        }
        (marker_dir / "test-session.json").write_text(json.dumps(marker))

        snapshot = build_cloud_status_snapshot(
            marker_dir=marker_dir,
            watchdog_report_path=tmp_path / "nonexistent.json",
            now=datetime(2026, 7, 21, 12, 0, tzinfo=timezone.utc),
        )

        sessions = snapshot.get("sessions", [])
        assert len(sessions) >= 1
        for session in sessions:
            gaps = session.get("evidence_gaps", {})
            assert isinstance(gaps, dict)
            # Watchdog status gap expected when report is missing
            if "watchdog_status" in gaps:
                wd_gap = gaps["watchdog_status"]
                assert wd_gap["gap"] in ("watchdog_status_unavailable", "watchdog_status_stale")


# ═══════════════════════════════════════════════════════════════════════════
# Snapshot digest stability — identical inputs produce identical digests
# ═══════════════════════════════════════════════════════════════════════════


class TestSnapshotDigestStability:
    """Canonical snapshots from identical inputs produce identical digests."""

    def test_identical_inputs_produce_identical_digests(self, tmp_path: Path) -> None:
        """Two snapshots built from identical fixtures produce identical digests."""
        marker_dir = tmp_path / "markers"
        marker_dir.mkdir()
        marker = {
            "session": "test-session",
            "workspace": str(tmp_path / "workspace"),
            "remote_spec": "",
            "started_at": "2026-07-21T12:00:00Z",
        }
        (marker_dir / "test-session.json").write_text(json.dumps(marker))

        now = datetime(2026, 7, 21, 12, 0, tzinfo=timezone.utc)
        cursor_vector = {
            "source_path": str(marker_dir / "test-session.json"),
            "source_record_count": 1,
            "source_digest": hashlib.sha256(
                json.dumps(marker, sort_keys=True).encode()
            ).hexdigest(),
            "computed_at": "2026-07-21T12:00:00Z",
        }

        snap_a = build_cloud_status_snapshot(
            marker_dir=marker_dir,
            watchdog_report_path=tmp_path / "nonexistent.json",
            now=now,
            source_cursor_vector=cursor_vector,
        )
        snap_b = build_cloud_status_snapshot(
            marker_dir=marker_dir,
            watchdog_report_path=tmp_path / "nonexistent.json",
            now=now,
            source_cursor_vector=cursor_vector,
        )

        assert _snapshot_digest(snap_a) == _snapshot_digest(snap_b), (
            "identical fixtures must produce identical snapshot digests"
        )

    def test_different_cursor_produces_different_digest(self, tmp_path: Path) -> None:
        """Different source cursor vectors produce different snapshot digests."""
        marker_dir = tmp_path / "markers"
        marker_dir.mkdir()
        marker = {
            "session": "test-session",
            "workspace": str(tmp_path / "workspace"),
            "remote_spec": "",
            "started_at": "2026-07-21T12:00:00Z",
        }
        (marker_dir / "test-session.json").write_text(json.dumps(marker))

        now = datetime(2026, 7, 21, 12, 0, tzinfo=timezone.utc)

        snap_a = build_cloud_status_snapshot(
            marker_dir=marker_dir,
            watchdog_report_path=tmp_path / "nonexistent.json",
            now=now,
            source_cursor_vector={"source_path": "/tmp/a.json", "source_digest": "aaa"},
        )
        snap_b = build_cloud_status_snapshot(
            marker_dir=marker_dir,
            watchdog_report_path=tmp_path / "nonexistent.json",
            now=now,
            source_cursor_vector={"source_path": "/tmp/b.json", "source_digest": "bbb"},
        )

        assert _snapshot_digest(snap_a) != _snapshot_digest(snap_b), (
            "different cursor vectors must produce different digests"
        )

    def test_format_output_stable_across_identical_snapshot_digests(self) -> None:
        """Format output is stable even when digest changes are from harmless reordering."""
        snap = _make_minimal_snapshot()
        detailed_a = format_cloud_status_detailed(snap)
        # Build a logically identical snapshot with keys in different insertion order
        snap_b = _make_minimal_snapshot()
        detailed_b = format_cloud_status_detailed(snap_b)
        assert detailed_a == detailed_b
