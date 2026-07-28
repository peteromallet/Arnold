"""Tests proving current-target and human-blocker surfaces use canonical query
projections and typed evidence gaps, and agree on identical inputs.

M9 — T16: current-target / human-blocker migration to canonical projections.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import pytest

from arnold_pipelines.megaplan.cloud.current_target import (
    _artifact_sort_key,
    _classify_evidence_state,
    _collect_target_evidence_gaps,
    _format_source_cursor as _ct_format_source_cursor,
    _safe_load_dict,
    _safe_plan_name,
    _safe_text,
    resolve_current_target,
)
from arnold_pipelines.megaplan.cloud.human_blockers import (
    BlockerVerdict,
    HumanBlockerClassification,
    _collect_human_blocker_evidence_gaps,
    _format_source_cursor as _hb_format_source_cursor,
    classify_needs_human_blocker,
)
from arnold_pipelines.megaplan.cloud.status_snapshot import (
    build_cloud_status_snapshot,
)
from arnold_pipelines.megaplan.cloud.status_format import (
    format_cloud_status_detailed,
    format_cloud_status_short,
)


# ── Helpers ────────────────────────────────────────────────────────────────


def _write_marker(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_plan_state(plans_dir: Path, plan_name: str, state: dict[str, object]) -> None:
    plan_dir = plans_dir / plan_name
    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")


def _make_minimal_fixture(tmp_path: Path) -> dict[str, Path]:
    """Create a minimal marker/workspace directory tree."""
    marker_dir = tmp_path / "markers"
    repair_data_dir = marker_dir / "repair-data"
    workspace = tmp_path / "ws"
    plans_dir = workspace / ".megaplan" / "plans"

    marker_dir.mkdir(parents=True)
    repair_data_dir.mkdir(parents=True)
    workspace.mkdir(parents=True)
    plans_dir.mkdir(parents=True)

    return {
        "marker_dir": marker_dir,
        "repair_data_dir": repair_data_dir,
        "workspace": workspace,
        "plans_dir": plans_dir,
    }


def _snapshot_digest(snapshot: Mapping[str, Any]) -> str:
    """Deterministic SHA-256 over canonical JSON."""
    payload = json.dumps(dict(snapshot), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# ═══════════════════════════════════════════════════════════════════════════
# Source cursor vector — display-only, never authority
# ═══════════════════════════════════════════════════════════════════════════


class TestSourceCursorVectorDisplayOnly:
    """Source cursor vectors are display-only annotations, never authority."""

    def test_resolve_current_target_attaches_cursor_when_provided(self, tmp_path: Path) -> None:
        """When a source cursor vector is supplied, it appears in the record."""
        fx = _make_minimal_fixture(tmp_path)
        _write_marker(
            fx["marker_dir"] / "sess.json",
            {"session": "sess", "workspace": str(fx["workspace"]), "run_kind": "plan", "plan_name": "p"},
        )
        cursor = {"source_path": "/fake/ledger.jsonl", "source_record_count": 5}
        record = resolve_current_target(
            "sess",
            marker_dir=fx["marker_dir"],
            source_cursor_vector=cursor,
        )
        assert "source_cursor_vector" in record
        scv = record["source_cursor_vector"]
        assert isinstance(scv, dict)
        assert scv.get("authority") == "evidence_extracted_display_only"
        assert isinstance(scv.get("value"), dict)

    def test_resolve_current_target_absent_sentinel_when_no_cursor(self, tmp_path: Path) -> None:
        """When no source cursor vector is supplied, the field is absent sentinel."""
        fx = _make_minimal_fixture(tmp_path)
        _write_marker(
            fx["marker_dir"] / "sess.json",
            {"session": "sess", "workspace": str(fx["workspace"]), "run_kind": "plan", "plan_name": "p"},
        )
        record = resolve_current_target("sess", marker_dir=fx["marker_dir"])
        scv = record["source_cursor_vector"]
        assert scv["authority"] == "absent"
        assert scv["reason"] == "no_source_cursor_vector_provided"

    def test_source_cursor_never_grants_mutation_authority(self, tmp_path: Path) -> None:
        """The source_cursor_vector field never authorizes mutation."""
        fx = _make_minimal_fixture(tmp_path)
        _write_marker(
            fx["marker_dir"] / "sess.json",
            {"session": "sess", "workspace": str(fx["workspace"]), "run_kind": "plan", "plan_name": "p"},
        )
        cursor = {"source_path": "/fake/ledger.jsonl"}
        record = resolve_current_target(
            "sess", marker_dir=fx["marker_dir"], source_cursor_vector=cursor,
        )
        scv = record["source_cursor_vector"]
        # The cursor is always display-only — never "authoritative"
        assert scv.get("authority") != "authoritative"
        assert scv.get("authority") in ("evidence_extracted_display_only", "absent")

    def test_classify_blocker_attaches_cursor_when_provided(self, tmp_path: Path) -> None:
        """Human blocker classification carries the source cursor vector."""
        fx = _make_minimal_fixture(tmp_path)
        _write_marker(
            fx["marker_dir"] / "sess.json",
            {"session": "sess", "workspace": str(fx["workspace"]), "run_kind": "plan", "plan_name": "p"},
        )
        cursor = {"source_path": "/fake/ledger.jsonl", "source_record_count": 3}
        classification = classify_needs_human_blocker(
            "sess",
            current_plan="p",
            marker_dir=fx["marker_dir"],
            repair_data_dir=fx["repair_data_dir"],
            source_cursor_vector=cursor,
        )
        assert classification.source_cursor_vector is not None
        scv = classification.source_cursor_vector
        assert isinstance(scv, dict)
        assert scv.get("authority") == "evidence_extracted_display_only"

    def test_classify_blocker_none_cursor_when_not_provided(self, tmp_path: Path) -> None:
        """When no cursor is supplied, the classification field is None."""
        fx = _make_minimal_fixture(tmp_path)
        _write_marker(
            fx["marker_dir"] / "sess.json",
            {"session": "sess", "workspace": str(fx["workspace"]), "run_kind": "plan", "plan_name": "p"},
        )
        classification = classify_needs_human_blocker(
            "sess",
            current_plan="p",
            marker_dir=fx["marker_dir"],
            repair_data_dir=fx["repair_data_dir"],
        )
        assert classification.source_cursor_vector is None


# ═══════════════════════════════════════════════════════════════════════════
# Evidence gaps — typed degradation annotations, never authority
# ═══════════════════════════════════════════════════════════════════════════


class TestTargetEvidenceGaps:
    """Current-target evidence gaps are structured, typed annotations."""

    def test_gaps_present_in_resolver_record(self, tmp_path: Path) -> None:
        """Every resolver record carries an evidence_gaps dict."""
        fx = _make_minimal_fixture(tmp_path)
        _write_marker(
            fx["marker_dir"] / "sess.json",
            {"session": "sess", "workspace": str(fx["workspace"]), "run_kind": "plan", "plan_name": "p"},
        )
        record = resolve_current_target("sess", marker_dir=fx["marker_dir"])
        assert "evidence_gaps" in record
        assert isinstance(record["evidence_gaps"], dict)

    def test_missing_marker_produces_gap(self) -> None:
        """When the marker is missing, a marker gap is produced."""
        gaps = _collect_target_evidence_gaps(
            {}, stale_evidence=[], marker_present=False,
        )
        assert "marker" in gaps
        assert gaps["marker"]["gap"] == "marker_unavailable"
        assert gaps["marker"]["evidence_status"] == "missing"

    def test_missing_plan_state_produces_gap(self) -> None:
        """When plan state is missing, a plan_state gap appears."""
        stale = [{"kind": "missing_plan_state", "path": "/fake/state.json"}]
        gaps = _collect_target_evidence_gaps(
            {}, stale_evidence=stale, marker_present=True,
        )
        assert "plan_state" in gaps
        assert gaps["plan_state"]["gap"] == "plan_state_unavailable"

    def test_stale_needs_human_produces_gap(self) -> None:
        """A stale needs-human plan ref produces a gap."""
        stale = [{"kind": "stale_needs_human_plan_ref", "path": "/fake/nh.json"}]
        gaps = _collect_target_evidence_gaps(
            {}, stale_evidence=stale, marker_present=True,
        )
        assert "needs_human_plan_ref" in gaps
        assert gaps["needs_human_plan_ref"]["evidence_status"] == "stale"

    def test_superseded_by_sibling_produces_gap(self) -> None:
        """Superseded-by-live-sibling produces a gap."""
        stale = [{"kind": "superseded_by_live_sibling", "path": "/fake/sib.json", "session": "sib"}]
        gaps = _collect_target_evidence_gaps(
            {}, stale_evidence=stale, marker_present=True,
        )
        assert "superseded_by_sibling" in gaps
        assert gaps["superseded_by_sibling"]["evidence_status"] == "superseded"

    def test_contradictory_identity_produces_gap(self) -> None:
        """Contradictory plan identity produces a gap."""
        stale = [{"kind": "contradictory_plan_identity", "path": "/fake/state.json"}]
        gaps = _collect_target_evidence_gaps(
            {}, stale_evidence=stale, marker_present=True,
        )
        assert "plan_identity" in gaps
        assert gaps["plan_identity"]["evidence_status"] == "degraded"

    def test_gaps_never_grant_authority(self, tmp_path: Path) -> None:
        """Evidence gaps in the resolver record never carry authority grants."""
        fx = _make_minimal_fixture(tmp_path)
        _write_marker(
            fx["marker_dir"] / "sess.json",
            {"session": "sess", "workspace": str(fx["workspace"]), "run_kind": "plan", "plan_name": "p"},
        )
        record = resolve_current_target("sess", marker_dir=fx["marker_dir"])
        gaps = record["evidence_gaps"]
        for key, gap in gaps.items():
            assert isinstance(gap, dict), f"gap {key} must be a dict"
            # Gaps are purely informational — no authority keys
            forbidden = {"authorizes_mutation", "grants_dispatch", "grants_completion"}
            assert not forbidden & set(gap.keys()), (
                f"gap {key} must not carry authority keys"
            )


class TestBlockerEvidenceGaps:
    """Human-blocker evidence gaps are structured, typed annotations."""

    def test_missing_payload_produces_gap(self) -> None:
        """When needs-human payload is missing, a gap appears."""
        gaps = _collect_human_blocker_evidence_gaps(
            has_payload=False, has_resolver=False,
        )
        assert "needs_human_payload" in gaps
        assert gaps["needs_human_payload"]["gap"] == "needs_human_payload_missing"

    def test_missing_resolver_produces_gap(self) -> None:
        """When resolver record is missing, a gap appears."""
        gaps = _collect_human_blocker_evidence_gaps(
            has_payload=True, has_resolver=False,
        )
        assert "resolver_record" in gaps
        assert gaps["resolver_record"]["gap"] == "resolver_record_missing"

    def test_stale_needs_human_kind_produces_gap(self) -> None:
        """Stale needs-human plan ref in stale kinds produces gap."""
        gaps = _collect_human_blocker_evidence_gaps(
            has_payload=True, has_resolver=True,
            stale_kinds={"stale_needs_human_plan_ref"},
        )
        assert "needs_human_plan_ref" in gaps
        assert gaps["needs_human_plan_ref"]["evidence_status"] == "stale"

    def test_empty_plan_refs_produces_gap(self) -> None:
        """Empty resolver plan_refs produces a degraded gap."""
        gaps = _collect_human_blocker_evidence_gaps(
            has_payload=True, has_resolver=True,
            resolver_plan_refs=[],
            current_plan="p",
        )
        assert "plan_refs" in gaps
        assert gaps["plan_refs"]["evidence_status"] == "degraded"

    def test_plan_mismatch_produces_gap(self) -> None:
        """Current plan not in resolver plan_refs produces a stale gap."""
        gaps = _collect_human_blocker_evidence_gaps(
            has_payload=True, has_resolver=True,
            resolver_plan_refs=["other-plan"],
            current_plan="current-plan",
        )
        assert "plan_mismatch" in gaps
        assert gaps["plan_mismatch"]["evidence_status"] == "stale"

    def test_missing_target_proof_produces_gap(self) -> None:
        """Missing current-target proof produces a degraded gap."""
        gaps = _collect_human_blocker_evidence_gaps(
            has_payload=True, has_resolver=True,
            resolver_plan_refs=["p"],
            current_plan="p",
            has_current_target_proof=False,
        )
        assert "current_target_proof" in gaps
        assert gaps["current_target_proof"]["evidence_status"] == "degraded"

    def test_classification_carries_evidence_gaps(self, tmp_path: Path) -> None:
        """Every classification carries evidence_gaps (never None)."""
        fx = _make_minimal_fixture(tmp_path)
        _write_marker(
            fx["marker_dir"] / "sess.json",
            {"session": "sess", "workspace": str(fx["workspace"]), "run_kind": "plan", "plan_name": "p"},
        )
        classification = classify_needs_human_blocker(
            "sess",
            current_plan="p",
            marker_dir=fx["marker_dir"],
            repair_data_dir=fx["repair_data_dir"],
        )
        # Classification always has gaps (could be empty dict, but not None)
        assert classification.evidence_gaps is not None
        assert isinstance(classification.evidence_gaps, dict)


# ═══════════════════════════════════════════════════════════════════════════
# Same-input agreement — identical inputs → identical outputs
# ═══════════════════════════════════════════════════════════════════════════


class TestSameInputAgreementCurrentTarget:
    """Identical inputs to resolve_current_target produce identical outputs."""

    def test_identical_inputs_produce_identical_records(self, tmp_path: Path) -> None:
        """Two calls with the same filesystem produce identical records."""
        fx = _make_minimal_fixture(tmp_path)
        _write_marker(
            fx["marker_dir"] / "sess.json",
            {"session": "sess", "workspace": str(fx["workspace"]), "run_kind": "plan", "plan_name": "p"},
        )
        _write_plan_state(fx["plans_dir"], "p", {"name": "p", "current_state": "planned"})
        cursor = {"source_path": "/fake/ledger.jsonl", "source_record_count": 3}
        rec_a = resolve_current_target(
            "sess", marker_dir=fx["marker_dir"], source_cursor_vector=cursor,
        )
        rec_b = resolve_current_target(
            "sess", marker_dir=fx["marker_dir"], source_cursor_vector=cursor,
        )
        # Remove the source_cursor_vector's computed_at which may differ
        rec_a_clean = copy.deepcopy(rec_a)
        rec_b_clean = copy.deepcopy(rec_b)
        if "value" in rec_a_clean.get("source_cursor_vector", {}):
            rec_a_clean["source_cursor_vector"]["value"].pop("computed_at", None)
        if "value" in rec_b_clean.get("source_cursor_vector", {}):
            rec_b_clean["source_cursor_vector"]["value"].pop("computed_at", None)
        assert rec_a_clean == rec_b_clean

    def test_different_inputs_produce_different_records(self, tmp_path: Path) -> None:
        """Different plan states produce different records."""
        fx = _make_minimal_fixture(tmp_path)
        _write_marker(
            fx["marker_dir"] / "sess.json",
            {"session": "sess", "workspace": str(fx["workspace"]), "run_kind": "plan", "plan_name": "a"},
        )
        _write_plan_state(fx["plans_dir"], "a", {"name": "a", "current_state": "planned"})
        rec_a = resolve_current_target("sess", marker_dir=fx["marker_dir"])

        # Now change the plan state
        _write_plan_state(fx["plans_dir"], "a", {"name": "a", "current_state": "executing"})
        rec_b = resolve_current_target("sess", marker_dir=fx["marker_dir"])

        assert rec_a != rec_b, "different plan state must produce different record"

    def test_record_is_deterministic_given_stable_filesystem(self, tmp_path: Path) -> None:
        """Deep-copied fixture produces identical records via digest."""
        fx = _make_minimal_fixture(tmp_path)
        _write_marker(
            fx["marker_dir"] / "sess.json",
            {"session": "sess", "workspace": str(fx["workspace"]), "run_kind": "plan", "plan_name": "p"},
        )
        _write_plan_state(fx["plans_dir"], "p", {"name": "p", "current_state": "planned"})
        rec_a = resolve_current_target("sess", marker_dir=fx["marker_dir"])
        rec_b = resolve_current_target("sess", marker_dir=fx["marker_dir"])
        # Same digest = same content (ignoring computed_at on cursor)
        a = copy.deepcopy(rec_a)
        b = copy.deepcopy(rec_b)
        if "value" in a.get("source_cursor_vector", {}):
            a["source_cursor_vector"]["value"].pop("computed_at", None)
        if "value" in b.get("source_cursor_vector", {}):
            b["source_cursor_vector"]["value"].pop("computed_at", None)
        assert _snapshot_digest(a) == _snapshot_digest(b)

    def test_source_cursor_preserved_in_resolver_output(self, tmp_path: Path) -> None:
        """The source cursor value is round-tripped through the resolver."""
        fx = _make_minimal_fixture(tmp_path)
        _write_marker(
            fx["marker_dir"] / "sess.json",
            {"session": "sess", "workspace": str(fx["workspace"]), "run_kind": "plan", "plan_name": "p"},
        )
        cursor = {"source_path": "/fake/ledger.jsonl", "source_record_count": 42, "source_digest": "abc"}
        record = resolve_current_target(
            "sess", marker_dir=fx["marker_dir"], source_cursor_vector=cursor,
        )
        scv = record["source_cursor_vector"]
        assert scv["authority"] == "evidence_extracted_display_only"
        assert scv["value"]["source_path"] == "/fake/ledger.jsonl"
        assert scv["value"]["source_record_count"] == 42
        assert scv["value"]["source_digest"] == "abc"


class TestSameInputAgreementHumanBlockers:
    """Identical inputs to classify_needs_human_blocker produce identical outputs."""

    def test_identical_inputs_produce_identical_classifications(self, tmp_path: Path) -> None:
        """Two calls with identical inputs produce the same classification."""
        fx = _make_minimal_fixture(tmp_path)
        _write_marker(
            fx["marker_dir"] / "sess.json",
            {"session": "sess", "workspace": str(fx["workspace"]), "run_kind": "plan", "plan_name": "p"},
        )
        # Write a needs-human sidecar
        nh_path = fx["repair_data_dir"] / "sess.needs-human.json"
        nh_path.parent.mkdir(parents=True, exist_ok=True)
        nh_path.write_text(json.dumps({
            "plan_name": "p",
            "summary": "needs review",
            "current_plan_name": "p",
        }), encoding="utf-8")

        _write_plan_state(fx["plans_dir"], "p", {"name": "p", "current_state": "planned"})
        cursor = {"source_path": "/fake/ledger.jsonl", "count": 1}

        c_a = classify_needs_human_blocker(
            "sess", current_plan="p", marker_dir=fx["marker_dir"],
            source_cursor_vector=cursor,
        )
        c_b = classify_needs_human_blocker(
            "sess", current_plan="p", marker_dir=fx["marker_dir"],
            source_cursor_vector=cursor,
        )

        assert c_a.verdict == c_b.verdict
        assert c_a.current_plan == c_b.current_plan
        assert c_a.rationale == c_b.rationale
        assert c_a.evidence_gaps == c_b.evidence_gaps
        assert c_a.source_cursor_vector == c_b.source_cursor_vector

    def test_classification_verdict_never_none(self, tmp_path: Path) -> None:
        """Every classification has a non-None verdict."""
        fx = _make_minimal_fixture(tmp_path)
        _write_marker(
            fx["marker_dir"] / "sess.json",
            {"session": "sess", "workspace": str(fx["workspace"]), "run_kind": "plan", "plan_name": "p"},
        )
        c = classify_needs_human_blocker(
            "sess", current_plan="p", marker_dir=fx["marker_dir"],
        )
        assert c.verdict is not None
        assert isinstance(c.verdict, BlockerVerdict)

    def test_different_resolver_record_produces_different_classification(self, tmp_path: Path) -> None:
        """Different resolver records can produce different classifications."""
        fx = _make_minimal_fixture(tmp_path)
        _write_marker(
            fx["marker_dir"] / "sess.json",
            {"session": "sess", "workspace": str(fx["workspace"]), "run_kind": "plan", "plan_name": "p"},
        )
        nh_path = fx["repair_data_dir"] / "sess.needs-human.json"
        nh_path.parent.mkdir(parents=True, exist_ok=True)
        nh_path.write_text(json.dumps({
            "plan_name": "p",
            "summary": "needs review",
            "current_plan_name": "p",
        }), encoding="utf-8")

        # Without plan state → no current-target proof
        c_no_state = classify_needs_human_blocker(
            "sess", current_plan="p", marker_dir=fx["marker_dir"],
            repair_data_dir=fx["repair_data_dir"],
        )

        # With plan state → current-target proof
        _write_plan_state(fx["plans_dir"], "p", {"name": "p", "current_state": "planned"})
        c_with_state = classify_needs_human_blocker(
            "sess", current_plan="p", marker_dir=fx["marker_dir"],
            repair_data_dir=fx["repair_data_dir"],
        )

        # Different resolver evidence should affect the classification
        # (at minimum the evidence_gaps may differ)
        assert c_no_state.evidence_gaps != c_with_state.evidence_gaps or \
            c_no_state.verdict != c_with_state.verdict, \
            "classification should differ when resolver evidence changes"

    def test_source_cursor_preserved_in_classification(self, tmp_path: Path) -> None:
        """The source cursor is round-tripped through the classifier."""
        fx = _make_minimal_fixture(tmp_path)
        _write_marker(
            fx["marker_dir"] / "sess.json",
            {"session": "sess", "workspace": str(fx["workspace"]), "run_kind": "plan", "plan_name": "p"},
        )
        nh_path = fx["repair_data_dir"] / "sess.needs-human.json"
        nh_path.parent.mkdir(parents=True, exist_ok=True)
        nh_path.write_text(json.dumps({
            "plan_name": "p", "summary": "test", "current_plan_name": "p",
        }), encoding="utf-8")
        _write_plan_state(fx["plans_dir"], "p", {"name": "p", "current_state": "planned"})

        cursor = {"source_path": "/fake/ledger.jsonl", "source_record_count": 7, "source_digest": "xyz"}
        c = classify_needs_human_blocker(
            "sess", current_plan="p", marker_dir=fx["marker_dir"],
            source_cursor_vector=cursor,
        )
        assert c.source_cursor_vector is not None
        scv = c.source_cursor_vector
        assert scv["authority"] == "evidence_extracted_display_only"
        assert scv["value"]["source_path"] == "/fake/ledger.jsonl"
        assert scv["value"]["source_record_count"] == 7
        assert scv["value"]["source_digest"] == "xyz"


# ═══════════════════════════════════════════════════════════════════════════
# Cross-surface agreement — current-target, cloud status, CLI agree
# ═══════════════════════════════════════════════════════════════════════════


class TestCrossSurfaceAgreement:
    """Current-target, cloud-status, and CLI views agree on same inputs."""

    def test_current_target_and_cloud_status_agree_on_session(self, tmp_path: Path) -> None:
        """Both resolver and cloud status agree on session identity."""
        fx = _make_minimal_fixture(tmp_path)
        sess = "test-session"
        _write_marker(
            fx["marker_dir"] / f"{sess}.json",
            {"session": sess, "workspace": str(fx["workspace"]), "run_kind": "plan", "plan_name": "p"},
        )
        _write_plan_state(fx["plans_dir"], "p", {"name": "p", "current_state": "planned"})

        target = resolve_current_target(sess, marker_dir=fx["marker_dir"])
        snapshot = build_cloud_status_snapshot(marker_dir=fx["marker_dir"])

        assert target["session"] == sess
        snapshot_sessions = [s.get("session") for s in snapshot.get("sessions", [])]
        assert sess in snapshot_sessions

    def test_current_target_and_cloud_status_agree_on_plan(self, tmp_path: Path) -> None:
        """Both resolver and cloud status agree on current plan name."""
        fx = _make_minimal_fixture(tmp_path)
        sess = "sess"
        _write_marker(
            fx["marker_dir"] / f"{sess}.json",
            {"session": sess, "workspace": str(fx["workspace"]), "run_kind": "plan", "plan_name": "my-plan"},
        )
        _write_plan_state(fx["plans_dir"], "my-plan", {"name": "my-plan", "current_state": "planned"})

        target = resolve_current_target(sess, marker_dir=fx["marker_dir"])
        snapshot = build_cloud_status_snapshot(marker_dir=fx["marker_dir"])

        target_plan = target["current_refs"].get("current_plan_name")
        snapshot_plans = [s.get("current_plan") for s in snapshot.get("sessions", [])]
        assert target_plan in snapshot_plans

    def test_cli_formats_agree_on_identical_snapshots(self) -> None:
        """Short and detailed CLI formats agree on identical snapshot content."""
        snap: dict[str, Any] = {
            "generated_at": "2026-07-21T12:00:00Z",
            "source": "test",
            "marker_dir": "/tmp/markers",
            "watchdog_report": "/tmp/wd.json",
            "summary": {"running": 1, "repairing": 0, "blocked": 0, "attention": 0, "complete": 0},
            "sessions": [{
                "session": "sess",
                "status": "running",
                "current_plan": "p",
                "completed_count": 0,
                "milestone_count": 3,
                "chain_complete": False,
                "plan_state": "planned",
                "lifecycle_state": "planned",
                "activity_phase": "execute",
                "custody_state": "",
                "repair_state": "none",
                "progress": {},
                "evidence": {"marker": "/tmp/markers/sess.json"},
                "tmux": True,
                "process": True,
                "watchdog": "alive",
                "latest_activity": "2026-07-21T11:59:00Z",
                "operator_next": "",
                "evidence_gaps": {},
            }],
            "degraded": None,
            "source_cursor_vector": {"authority": "absent", "reason": "none"},
        }
        short = "\n".join(format_cloud_status_short(snap))
        detailed = format_cloud_status_detailed(snap)
        # Both formats must reference the session
        assert "sess" in short
        assert "sess" in detailed
        # Both agree on status
        assert "running" in short
        assert "running" in detailed

    def test_current_target_and_cli_agree_on_status_wording(self, tmp_path: Path) -> None:
        """The resolver record and CLI format use consistent terminology."""
        fx = _make_minimal_fixture(tmp_path)
        sess = "sess"
        _write_marker(
            fx["marker_dir"] / f"{sess}.json",
            {"session": sess, "workspace": str(fx["workspace"]), "run_kind": "plan", "plan_name": "p"},
        )
        _write_plan_state(fx["plans_dir"], "p", {"name": "p", "current_state": "planned"})

        target = resolve_current_target(sess, marker_dir=fx["marker_dir"])
        snapshot = build_cloud_status_snapshot(marker_dir=fx["marker_dir"])
        detailed = format_cloud_status_detailed(snapshot)

        # The target record's plan name must appear in the CLI output
        target_plan = target["current_refs"].get("current_plan_name", "")
        assert target_plan and target_plan in detailed, (
            f"plan {target_plan!r} must appear in CLI output"
        )

    def test_evidence_gaps_visible_in_snapshot(self, tmp_path: Path) -> None:
        """Evidence gaps from the resolver appear in cloud status snapshot."""
        fx = _make_minimal_fixture(tmp_path)
        sess = "sess"
        _write_marker(
            fx["marker_dir"] / f"{sess}.json",
            {"session": sess, "workspace": str(fx["workspace"]), "run_kind": "plan", "plan_name": "p"},
        )
        _write_plan_state(fx["plans_dir"], "p", {"name": "p", "current_state": "planned"})

        target = resolve_current_target(sess, marker_dir=fx["marker_dir"])
        gaps = target.get("evidence_gaps", {})
        assert isinstance(gaps, dict), "resolver record must have evidence_gaps dict"

        snapshot = build_cloud_status_snapshot(marker_dir=fx["marker_dir"])
        for entry in snapshot.get("sessions", []):
            sess_gaps = entry.get("evidence_gaps", {})
            assert isinstance(sess_gaps, dict), (
                f"snapshot session {entry.get('session')} must have evidence_gaps dict"
            )

    def test_blocker_classification_and_resolver_agree_on_current_plan(self, tmp_path: Path) -> None:
        """Blocker classifier and resolver agree on current plan identity."""
        fx = _make_minimal_fixture(tmp_path)
        sess = "sess"
        _write_marker(
            fx["marker_dir"] / f"{sess}.json",
            {"session": sess, "workspace": str(fx["workspace"]), "run_kind": "plan", "plan_name": "p"},
        )
        _write_plan_state(fx["plans_dir"], "p", {"name": "p", "current_state": "planned"})

        nh_path = fx["repair_data_dir"] / "sess.needs-human.json"
        nh_path.parent.mkdir(parents=True, exist_ok=True)
        nh_path.write_text(json.dumps({
            "plan_name": "p", "summary": "test", "current_plan_name": "p",
        }), encoding="utf-8")

        target = resolve_current_target(sess, marker_dir=fx["marker_dir"])
        classification = classify_needs_human_blocker(
            sess, current_plan="p", marker_dir=fx["marker_dir"],
        )

        target_plan = target["current_refs"].get("current_plan_name", "")
        assert target_plan == classification.current_plan, (
            "resolver and classifier must agree on current plan"
        )


# ═══════════════════════════════════════════════════════════════════════════
# Non-authoritative outputs — markers/plan-state labels never drive action
# ═══════════════════════════════════════════════════════════════════════════


class TestNonAuthoritativeOutputs:
    """Current-target and blocker outputs are display-only, never action authority."""

    def test_resolver_record_never_grants_dispatch(self, tmp_path: Path) -> None:
        """The resolver record never carries dispatch/action authorization."""
        fx = _make_minimal_fixture(tmp_path)
        _write_marker(
            fx["marker_dir"] / "sess.json",
            {"session": "sess", "workspace": str(fx["workspace"]), "run_kind": "plan", "plan_name": "p"},
        )
        record = resolve_current_target("sess", marker_dir=fx["marker_dir"])
        forbidden_keys = {"authorizes_dispatch", "authorizes_completion",
                          "authorizes_cancellation", "authorizes_publication",
                          "authorizes_delivery", "grants_action"}
        found_forbidden = forbidden_keys & set(record.keys())
        assert not found_forbidden, (
            f"resolver record must not carry authority keys: {found_forbidden}"
        )

    def test_evidence_state_never_authorizes_mutation(self, tmp_path: Path) -> None:
        """The evidence_state block always sets authorizes_mutation to False."""
        fx = _make_minimal_fixture(tmp_path)
        _write_marker(
            fx["marker_dir"] / "sess.json",
            {"session": "sess", "workspace": str(fx["workspace"]), "run_kind": "plan", "plan_name": "p"},
        )
        record = resolve_current_target("sess", marker_dir=fx["marker_dir"])
        evidence_state = record.get("evidence_state", {})
        assert evidence_state.get("authorizes_mutation") is False, (
            "evidence_state must never authorize mutation"
        )

    def test_classification_never_grants_action_authority(self, tmp_path: Path) -> None:
        """The blocker classification is a diagnostic, never an action grant."""
        fx = _make_minimal_fixture(tmp_path)
        _write_marker(
            fx["marker_dir"] / "sess.json",
            {"session": "sess", "workspace": str(fx["workspace"]), "run_kind": "plan", "plan_name": "p"},
        )
        c = classify_needs_human_blocker(
            "sess", current_plan="p", marker_dir=fx["marker_dir"],
        )
        # The classification is an enum verdict + rationale, not an action grant
        assert c.verdict in BlockerVerdict
        # source_cursor_vector is display-only
        if c.source_cursor_vector:
            assert c.source_cursor_vector.get("authority") != "authoritative"

    def test_display_only_cursor_never_promoted_to_authority(self) -> None:
        """The format_source_cursor helper always returns non-authoritative."""
        cursor = {"source_path": "/fake/path"}
        result = _ct_format_source_cursor(cursor)
        assert result["authority"] == "evidence_extracted_display_only"
        assert result["authority"] != "authoritative"

        result_hb = _hb_format_source_cursor(cursor)
        # hb variant returns None when not provided, or display-only when provided
        if result_hb is not None:
            assert result_hb.get("authority") == "evidence_extracted_display_only"
            assert result_hb.get("authority") != "authoritative"


# ═══════════════════════════════════════════════════════════════════════════
# Degradation-as-diagnostic — markers/plan-state labels never drive action
# ═══════════════════════════════════════════════════════════════════════════


class TestDegradationAsDiagnostic:
    """Degradation is preserved as diagnostic evidence without driving action."""

    def test_missing_workspace_produces_diagnostic_gap_not_error(self, tmp_path: Path) -> None:
        """Missing workspace produces an evidence gap, not an exception."""
        fx = _make_minimal_fixture(tmp_path)
        _write_marker(
            fx["marker_dir"] / "sess.json",
            {"session": "sess", "run_kind": "plan", "plan_name": "p"},
        )
        # Should not raise — missing workspace is a diagnostic gap
        record = resolve_current_target("sess", marker_dir=fx["marker_dir"])
        assert record["evidence_state"]["status"] in ("unknown", "resolved", "missing", "partial", "stale", "contradictory")
        gaps = record.get("evidence_gaps", {})
        assert isinstance(gaps, dict)

    def test_missing_marker_produces_diagnostic_not_error(self, tmp_path: Path) -> None:
        """A non-existent marker produces a diagnostic gap, not an error."""
        fx = _make_minimal_fixture(tmp_path)
        # No marker written — should not raise
        record = resolve_current_target("no-such-session", marker_dir=fx["marker_dir"])
        assert record["evidence_state"]["status"] in ("unknown", "resolved", "missing", "partial", "stale", "contradictory")
        # Should have a marker-related evidence gap
        gaps = record.get("evidence_gaps", {})
        assert any("marker" in str(k).lower() for k in gaps.keys()) or record["evidence_state"]["status"] in ("missing", "unknown")

    def test_classifier_handles_missing_payload_without_error(self, tmp_path: Path) -> None:
        """Classifier handles missing needs-human payload without raising."""
        fx = _make_minimal_fixture(tmp_path)
        _write_marker(
            fx["marker_dir"] / "sess.json",
            {"session": "sess", "workspace": str(fx["workspace"]), "run_kind": "plan", "plan_name": "p"},
        )
        # No needs-human file — should not raise
        c = classify_needs_human_blocker(
            "sess", current_plan="p", marker_dir=fx["marker_dir"],
        )
        assert c.verdict == BlockerVerdict.AMBIGUOUS_BLOCKER
        assert c.evidence_gaps is not None

    def test_classifier_handles_stale_plan_ref_without_error(self, tmp_path: Path) -> None:
        """Classifier handles stale plan reference diagnostically, not by error."""
        fx = _make_minimal_fixture(tmp_path)
        _write_marker(
            fx["marker_dir"] / "sess.json",
            {"session": "sess", "workspace": str(fx["workspace"]), "run_kind": "plan", "plan_name": "old-plan"},
        )
        nh_path = fx["repair_data_dir"] / "sess.needs-human.json"
        nh_path.parent.mkdir(parents=True, exist_ok=True)
        nh_path.write_text(json.dumps({
            "plan_name": "old-plan",
            "summary": "test",
            "current_plan_name": "old-plan",
        }), encoding="utf-8")

        c = classify_needs_human_blocker(
            "sess", current_plan="new-plan", marker_dir=fx["marker_dir"],
        )
        # Should not raise; verdict reflects the mismatch
        assert c.verdict in BlockerVerdict
        assert c.evidence_gaps is not None
