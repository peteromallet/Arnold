"""Fixture-driven tests for the canonical cloud status snapshot.

These lock in the contract from
``docs/ops/elegant-cloud-status-resident-plan.md``: the snapshot is produced by
local observation only, classifies sessions into a stable vocabulary, and is the
single source every status consumer reads.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.cloud import status_format as sf
from arnold_pipelines.megaplan.cloud import status_snapshot as ss


NOW = datetime(2026, 7, 4, 22, 13, 15, tzinfo=timezone.utc)


def _dead_probe(_marker):
    return {"tmux": False, "process": False}


class Fixture:
    """Builds a marker directory with canonical markers + sidecars."""

    def __init__(self, tmp_path: Path):
        self.root = tmp_path
        self.marker_dir = tmp_path / "cloud-sessions"
        self.repair_dir = self.marker_dir / "repair-data"
        self.marker_dir.mkdir(parents=True, exist_ok=True)
        self.repair_dir.mkdir(parents=True, exist_ok=True)

    def add_session(
        self,
        name: str,
        *,
        workspace: str | None = None,
        remote_spec: str | None = None,
        run_kind: str = "chain",
        plan_name: str = "",
        started_at: str = "2026-07-04T20:00:00Z",
    ) -> Path:
        ws = workspace or str(self.root / name)
        Path(ws).mkdir(parents=True, exist_ok=True)
        remote = remote_spec if remote_spec is not None else f"/spec/{name}"
        payload = {
            "session": name,
            "workspace": ws,
            "remote_spec": remote,
            "started_at": started_at,
            "run_kind": run_kind,
        }
        if plan_name:
            payload["plan_name"] = plan_name
        path = self.marker_dir / f"{name}.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return Path(ws)

    def add_chain_health(
        self,
        name: str,
        *,
        chain_complete: bool = False,
        completed_count: int = 0,
        milestone_count: int = 1,
        current_plan_name: str | None = None,
        last_state: str = "executed",
        updated_at: datetime | None = None,
        pr_number: int | None = None,
        pr_state: str | None = None,
    ) -> None:
        payload = {
            "chain_complete": chain_complete,
            "completed_count": completed_count,
            "milestone_count": milestone_count,
            "last_state": last_state,
            "updated_at": (updated_at or NOW - timedelta(seconds=60)).isoformat(),
        }
        if current_plan_name is not None:
            payload["current_plan_name"] = current_plan_name
        if pr_number is not None:
            payload["pr_number"] = pr_number
        if pr_state is not None:
            payload["pr_state"] = pr_state
        (self.marker_dir / f"{name}.chain-health.progress.json").write_text(
            json.dumps(payload), encoding="utf-8"
        )

    def add_repair_progress(self, name: str, *, updated_at: datetime | None = None) -> None:
        (self.marker_dir / f"{name}.repair-progress.json").write_text(
            json.dumps(
                {
                    "advancement_since_last_dispatch": False,
                    "updated_at": (updated_at or NOW - timedelta(minutes=5)).isoformat(),
                }
            ),
            encoding="utf-8",
        )

    def add_repair_data(self, name: str, *, outcome: str = "repairing") -> None:
        (self.repair_dir / f"{name}.repair-data.json").write_text(
            json.dumps({"session": name, "outcome": outcome}),
            encoding="utf-8",
        )

    def add_needs_human(self, name: str, *, summary: str = "awaiting human action") -> None:
        (self.repair_dir / f"{name}.needs-human.json").write_text(
            json.dumps(
                {"session": name, "summary": summary, "recorded_at": NOW.isoformat()},
            ),
            encoding="utf-8",
        )

    def add_watchdog_report(
        self, *, items: list[dict] | None = None, sessions_seen: int | None = None
    ) -> Path:
        path = self.root / "watchdog-report.json"
        payload = {
            "timestamp_utc": NOW.isoformat(),
            "sessions_seen": sessions_seen if sessions_seen is not None else len(items or []),
            "items": items or [],
            "issues": [],
        }
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def build(self, **overrides):
        kwargs = dict(
            marker_dir=self.marker_dir,
            repair_data_dir=self.repair_dir,
            workspace_root=self.root,
            now=NOW,
            liveness_probe=_dead_probe,
        )
        kwargs.update(overrides)
        return ss.build_cloud_status_snapshot(**kwargs)


@pytest.fixture
def fx(tmp_path):
    return Fixture(tmp_path)


def _by_session(snapshot, name):
    for entry in snapshot["sessions"]:
        if entry["session"] == name:
            return entry
    raise AssertionError(f"session {name!r} missing from snapshot")


# --- classification contract ----------------------------------------------


def test_two_running_plus_one_repairing(fx):
    fx.add_session("a", plan_name="planA")
    fx.add_chain_health("a", current_plan_name="planA", completed_count=2, milestone_count=5)
    fx.add_session("b", plan_name="planB")
    fx.add_chain_health("b", current_plan_name="planB", completed_count=1, milestone_count=5)

    fx.add_session("c", plan_name="planC")
    fx.add_chain_health(
        "c",
        current_plan_name="planC",
        last_state="error",
        updated_at=NOW - timedelta(hours=3),
    )
    fx.add_repair_progress("c")

    snap = fx.build()
    assert snap["summary"]["running"] == 2
    assert snap["summary"]["repairing"] == 1


def test_completed_not_counted_as_active_even_with_stale_failure(fx):
    fx.add_session("done", plan_name="planDone")
    fx.add_chain_health(
        "done",
        chain_complete=True,
        completed_count=4,
        milestone_count=4,
        last_state="done",
        updated_at=NOW - timedelta(hours=5),
    )
    # Stale plan-state finalized must not drag a complete chain back into active.
    plan_state_dir = fx.root / "done" / ".megaplan" / "plans" / "planDone"
    plan_state_dir.mkdir(parents=True, exist_ok=True)
    (plan_state_dir / "state.json").write_text(
        json.dumps({"current_state": "finalized"}), encoding="utf-8"
    )

    snap = fx.build()
    entry = _by_session(snap, "done")
    assert entry["status"] == "complete"
    assert entry["should_run"] is False
    assert all(s["status"] != "running" for s in snap["sessions"])


def test_completed_chain_without_active_plan_ignores_stale_needs_human(fx):
    fx.add_session("done")
    fx.add_chain_health(
        "done",
        chain_complete=True,
        completed_count=3,
        milestone_count=3,
        current_plan_name="",
        last_state="done",
        updated_at=NOW - timedelta(minutes=1),
    )
    fx.add_needs_human("done", summary="old repair exhaustion from timeout_or_hang")

    snap = fx.build()
    entry = _by_session(snap, "done")
    assert entry["status"] == "complete"
    assert entry["operator_next"] == "chain complete; no runner expected"


def test_missing_workspace_becomes_attention_not_complete(fx):
    # No workspace dir created; point the marker at a path that does not exist.
    (fx.marker_dir / "ghost.json").write_text(
        json.dumps(
            {
                "session": "ghost",
                "workspace": str(fx.root / "does-not-exist"),
                "remote_spec": "/spec/ghost",
                "started_at": "2026-07-04T20:00:00Z",
                "run_kind": "chain",
            }
        ),
        encoding="utf-8",
    )
    snap = fx.build()
    entry = _by_session(snap, "ghost")
    assert entry["status"] == "attention"
    assert entry["status"] != "complete"


def test_repair_marker_plus_blocked_watchdog_item_is_repairing(fx):
    fx.add_session("stuck", plan_name="planStuck")
    fx.add_chain_health(
        "stuck",
        current_plan_name="planStuck",
        last_state="error",
        updated_at=NOW - timedelta(hours=4),
    )
    fx.add_repair_progress("stuck")
    fx.add_watchdog_report(
        items=[{"session": "stuck", "status": "restarted", "action": "repair", "message": "restarted"}]
    )
    snap = fx.build(watchdog_report_path=fx.root / "watchdog-report.json")
    entry = _by_session(snap, "stuck")
    assert entry["status"] == "repairing"
    assert entry["repairing"] is True


def test_successful_repair_data_suppresses_stale_repair_marker(fx):
    fx.add_session("recovered", plan_name="planRecovered")
    fx.add_chain_health(
        "recovered",
        current_plan_name="planRecovered",
        last_state="finalized",
        updated_at=NOW - timedelta(hours=4),
    )
    fx.add_repair_progress("recovered")
    fx.add_repair_data("recovered", outcome="live_with_fresh_activity")

    snap = fx.build()
    entry = _by_session(snap, "recovered")
    assert entry["status"] == "attention"
    assert entry["repairing"] is False


def test_live_process_beats_repair_marker(fx):
    fx.add_session("live-repair", plan_name="planLive")
    fx.add_chain_health(
        "live-repair",
        current_plan_name="planLive",
        last_state="error",
        updated_at=NOW - timedelta(hours=4),
    )
    fx.add_repair_progress("live-repair")

    snap = fx.build(liveness_probe=lambda _marker: {"tmux": False, "process": True})
    entry = _by_session(snap, "live-repair")
    assert entry["status"] == "running"
    assert entry["repairing"] is False


def test_blocked_session_when_needs_human_marker_present(fx):
    fx.add_session("gated", plan_name="planGated")
    fx.add_chain_health(
        "gated",
        current_plan_name="planGated",
        last_state="awaiting_human",
        updated_at=NOW - timedelta(hours=1),
    )
    fx.add_needs_human("gated", summary="merge the PR before continuing")
    snap = fx.build()
    entry = _by_session(snap, "gated")
    assert entry["status"] == "blocked"
    assert "merge the PR" in entry["operator_next"]




def test_needs_human_marker_beats_watchdog_complete_verdict(fx):
    fx.add_session("false_done", plan_name="planFalseDone")
    fx.add_chain_health(
        "false_done",
        current_plan_name="planFalseDone",
        last_state="validation_failed",
        updated_at=NOW - timedelta(hours=1),
    )
    fx.add_needs_human("false_done", summary="repair loop exhausted after validation failure")
    fx.add_watchdog_report(
        items=[
            {
                "session": "false_done",
                "status": "complete",
                "action": "observe",
                "message": "watchdog reports chain complete",
            }
        ]
    )

    snap = fx.build(watchdog_report_path=fx.root / "watchdog-report.json")
    entry = _by_session(snap, "false_done")

    assert entry["status"] == "blocked"
    assert "repair loop exhausted" in entry["operator_next"]


def test_stale_parent_needs_human_is_superseded_by_completed_child(fx):
    workspace = fx.root / "shared-workspace"
    fx.add_session(
        "parent",
        workspace=str(workspace),
        remote_spec=str(
            workspace / ".megaplan" / "initiatives" / "demo" / "assets" / "epic-chain.yaml"
        ),
        run_kind="epic_chain",
        started_at="2026-07-01T02:02:15Z",
    )
    fx.add_needs_human("parent", summary="old parent repair exhaustion")

    fx.add_session(
        "child",
        workspace=str(workspace),
        remote_spec=str(workspace / ".megaplan" / "initiatives" / "demo" / "chain.yaml"),
        run_kind="chain",
        started_at="2026-07-01T03:52:27Z",
    )
    fx.add_chain_health(
        "child",
        chain_complete=True,
        completed_count=8,
        milestone_count=8,
        last_state="done",
    )

    snap = fx.build()
    parent = _by_session(snap, "parent")
    assert parent["status"] == "complete"
    assert parent["should_run"] is False
    assert "superseded by sibling session child:complete" in parent["operator_next"]
    assert parent["evidence"]["superseded_by"] == "child:complete"
    assert parent not in ss.plan_activity_summary(snap)["should_be_working_but_needs_attention"]


def test_frozen_chain_health_sidecar_defers_to_watchdog_complete(fx):
    """A done chain's chain-health sidecar can freeze at the last non-complete
    snapshot once the session goes idle. The snapshot must defer to the
    watchdog's authoritative per-session verdict instead of reporting the done
    chain as stalled attention."""
    fx.add_session("done", plan_name="planDone")
    fx.add_chain_health(
        "done",
        current_plan_name="planDone",
        chain_complete=False,
        last_state="executed",
        updated_at=NOW - timedelta(hours=18),
    )
    fx.add_watchdog_report(
        items=[{"session": "done", "status": "complete", "action": "observe", "message": "chain complete"}]
    )
    snap = fx.build(watchdog_report_path=fx.root / "watchdog-report.json")
    entry = _by_session(snap, "done")
    assert entry["status"] == "complete"
    assert entry["should_run"] is False


def test_summary_counts_partition_all_sessions(fx):
    fx.add_session("r1"); fx.add_chain_health("r1")
    fx.add_session("r2"); fx.add_chain_health("r2")
    fx.add_session("rep"); fx.add_chain_health("rep", last_state="error", updated_at=NOW - timedelta(hours=3)); fx.add_repair_progress("rep")
    fx.add_session("blk"); fx.add_chain_health("blk", last_state="awaiting_human"); fx.add_needs_human("blk")
    fx.add_session("dn"); fx.add_chain_health("dn", chain_complete=True, completed_count=2, milestone_count=2, last_state="done")
    fx.add_session("att"); fx.add_chain_health("att", last_state="executed", updated_at=NOW - timedelta(hours=8))

    snap = fx.build()
    summary = snap["summary"]
    total = sum(summary.values())
    assert total == 6, summary
    assert summary == {"running": 2, "repairing": 1, "blocked": 1, "complete": 1, "attention": 1}


# --- degraded mode + freshness -------------------------------------------


def test_missing_watchdog_report_marks_degraded_but_still_builds(fx):
    fx.add_session("a"); fx.add_chain_health("a")
    snap = fx.build(watchdog_report_path=fx.root / "absent.json")
    assert snap["degraded"] is not None
    assert snap["degraded"]["reasons"]
    assert _by_session(snap, "a")["status"] == "running"


def test_plan_activity_summary_prefers_snapshot_over_no_snapshot():
    derived_none = ss.plan_activity_summary(None)
    assert derived_none["degraded"] is True
    assert derived_none["active_working"] == []

    snap = {
        "sessions": [
            {"session": "r", "status": "running", "current_plan": "m1", "operator_next": "x", "latest_activity": "t"},
            {"session": "d", "status": "complete", "current_plan": "m9", "operator_next": "", "latest_activity": "t"},
            {"session": "a", "status": "attention", "current_plan": "m3", "operator_next": "stalled", "latest_activity": "t"},
        ]
    }
    derived = ss.plan_activity_summary(snap)
    assert derived["degraded"] is False
    assert [e["session"] for e in derived["active_working"]] == ["r"]
    assert [e["session"] for e in derived["recently_completed"]] == ["d"]
    assert [e["session"] for e in derived["should_be_working_but_needs_attention"]] == ["a"]


def test_write_load_roundtrip_and_freshness(tmp_path, fx):
    fx.add_session("a"); fx.add_chain_health("a")
    snap = fx.build(watchdog_report_path=fx.root / "absent.json")
    target = tmp_path / "status" / "cloud-status.json"
    previous = tmp_path / "status" / "cloud-status.previous.json"

    written = ss.write_cloud_status_snapshot(snap, path=target, previous_path=previous)
    assert written == target

    loaded, reason = ss.load_cloud_status_snapshot(target, max_age_s=60, now=NOW)
    assert reason is None
    assert loaded["summary"] == snap["summary"]

    # Second write rotates the prior snapshot into previous_path.
    snap2 = dict(snap)
    snap2 = json.loads(json.dumps(snap))
    snap2["generated_at"] = (NOW + timedelta(seconds=1)).isoformat().replace("+00:00", "Z")
    ss.write_cloud_status_snapshot(snap2, path=target, previous_path=previous)
    assert previous.exists()
    rotated, _ = ss.load_cloud_status_snapshot(previous)
    assert rotated["summary"] == snap["summary"]

    stale, reason = ss.load_cloud_status_snapshot(target, max_age_s=60, now=NOW + timedelta(hours=2))
    assert stale is not None
    assert reason is not None
    assert "stale" in reason


def test_load_missing_snapshot_returns_degraded_reason(tmp_path):
    loaded, reason = ss.load_cloud_status_snapshot(tmp_path / "nope.json")
    assert loaded is None
    assert "missing" in reason


def test_is_trusted_container_requires_env_and_marker_dir(tmp_path, monkeypatch):
    monkeypatch.delenv("MEGAPLAN_TRUSTED_CONTAINER", raising=False)
    monkeypatch.setattr(ss, "DEFAULT_MARKER_DIR", tmp_path)
    assert ss.is_trusted_container() is False
    monkeypatch.setenv("MEGAPLAN_TRUSTED_CONTAINER", "1")
    assert ss.is_trusted_container() is True  # marker dir exists now
    missing = tmp_path / "does-not-exist"
    monkeypatch.setattr(ss, "DEFAULT_MARKER_DIR", missing)
    assert ss.is_trusted_container() is False


# --- formatter contract ---------------------------------------------------


def test_discord_short_chunks_under_limit(fx):
    for i in range(60):
        fx.add_session(f"very-long-running-session-name-{i:03d}")
        fx.add_chain_health(f"very-long-running-session-name-{i:03d}", current_plan_name=f"milestone-plan-{i:03d}")
    snap = fx.build(watchdog_report_path=fx.root / "absent.json")
    chunks = sf.format_cloud_status_short(snap)
    assert chunks
    assert all(len(c) <= 2000 for c in chunks)
    assert any("running" in c for c in chunks)


def test_discord_short_splits_on_small_cap(fx):
    fx.add_session("a"); fx.add_chain_health("a", current_plan_name="plan-a")
    fx.add_session("b"); fx.add_chain_health("b", current_plan_name="plan-b")
    snap = fx.build(watchdog_report_path=fx.root / "absent.json")
    chunks = sf.format_cloud_status_short(snap, max_chars=80)
    assert len(chunks) >= 2
    assert all(len(c) <= 80 for c in chunks)


def test_discord_short_degraded_when_snapshot_absent():
    chunks = sf.format_cloud_status_short(None)
    assert len(chunks) == 1
    assert "degraded" in chunks[0]


def test_attention_only_empty_when_nothing_noteworthy(fx):
    fx.add_session("a"); fx.add_chain_health("a")
    fx.add_session("d"); fx.add_chain_health("d", chain_complete=True, completed_count=1, milestone_count=1, last_state="done")
    snap = fx.build(watchdog_report_path=fx.root / "absent.json")
    assert sf.format_attention_only(snap) == ""


def test_attention_only_lists_blocked_and_repairing(fx):
    fx.add_session("rep"); fx.add_chain_health("rep", last_state="error", updated_at=NOW - timedelta(hours=3)); fx.add_repair_progress("rep")
    fx.add_session("blk"); fx.add_chain_health("blk", last_state="awaiting_human"); fx.add_needs_human("blk")
    snap = fx.build(watchdog_report_path=fx.root / "absent.json")
    body = sf.format_attention_only(snap)
    assert "rep" in body and "blk" in body


def test_detailed_cites_evidence_source_and_timestamp(fx):
    fx.add_session("a"); fx.add_chain_health("a", current_plan_name="m1")
    snap = fx.build(watchdog_report_path=fx.root / "absent.json")
    detailed = sf.format_cloud_status_detailed(snap)
    assert "Cloud status —" in detailed
    assert snap["generated_at"] in detailed
    assert "cloud-local-observer" in detailed


# --- pre-calculated progress (sprint % + epic %) --------------------------


def test_session_progress_none_without_milestone_data():
    assert ss._session_progress(completed_count=2, milestone_count=None, current_plan="p", complete=False) is None
    assert ss._session_progress(completed_count=2, milestone_count=0, current_plan="p", complete=False) is None
    assert ss._session_progress(completed_count=None, milestone_count="oops", current_plan=None, complete=False) is None


def test_session_progress_partial_marks_in_flight_sprint():
    progress = ss._session_progress(
        completed_count=1, milestone_count=3, current_plan="s2-front-half-2026", complete=False
    )
    assert progress == {
        "completed_milestones": 1,
        "total_milestones": 3,
        "percent": 33,
        "complete": False,
        "current_plan": "s2-front-half-2026",
        "sprints": [
            {"sprint": "s1", "status": "done"},
            {"sprint": "s2", "status": "in_progress", "plan": "s2-front-half-2026"},
            {"sprint": "s3", "status": "pending"},
        ],
    }


def test_session_progress_in_flight_without_plan_name():
    progress = ss._session_progress(completed_count=0, milestone_count=2, current_plan=None, complete=False)
    assert progress["percent"] == 0
    assert progress["sprints"][0] == {"sprint": "s1", "status": "in_progress"}
    assert progress["sprints"][1] == {"sprint": "s2", "status": "pending"}


def test_session_progress_complete_forces_all_done_and_100():
    progress = ss._session_progress(
        completed_count=2, milestone_count=3, current_plan=None, complete=True
    )
    assert progress["percent"] == 100
    assert progress["complete"] is True
    assert progress["completed_milestones"] == 3
    assert [s["status"] for s in progress["sprints"]] == ["done", "done", "done"]


def test_session_progress_clamps_and_rounds():
    # completed_count above total clamps to total; rounds to nearest percent.
    progress = ss._session_progress(completed_count=99, milestone_count=3, current_plan="p", complete=False)
    assert progress["completed_milestones"] == 3
    assert progress["percent"] == 100


def test_session_entry_carries_progress_block(fx):
    fx.add_session("epic-a", plan_name="s2-front-half-2026")
    fx.add_chain_health("epic-a", current_plan_name="s2-front-half-2026", completed_count=1, milestone_count=4)
    snap = fx.build()
    entry = _by_session(snap, "epic-a")
    assert entry["chain_complete"] is False
    assert entry["progress"]["completed_milestones"] == 1
    assert entry["progress"]["total_milestones"] == 4
    assert entry["progress"]["percent"] == 25
    assert entry["progress"]["current_plan"] == "s2-front-half-2026"
    statuses = [s["status"] for s in entry["progress"]["sprints"]]
    assert statuses == ["done", "in_progress", "pending", "pending"]


def test_session_entry_progress_none_without_milestones(fx):
    fx.add_session("plan-only", plan_name="planX")
    # chain-health with no milestone_count → nothing to score → progress is None.
    (fx.marker_dir / "plan-only.chain-health.progress.json").write_text(
        json.dumps(
            {
                "current_plan_name": "planX",
                "last_state": "executed",
                "updated_at": (NOW - timedelta(seconds=60)).isoformat(),
            }
        ),
        encoding="utf-8",
    )
    snap = fx.build()
    entry = _by_session(snap, "plan-only")
    assert entry["progress"] is None


def test_plan_activity_summary_propagates_progress(fx):
    fx.add_session("epic-run", plan_name="s2-loop")
    fx.add_chain_health("epic-run", current_plan_name="s2-loop", completed_count=1, milestone_count=2)
    snap = fx.build()
    summary = ss.plan_activity_summary(snap)
    assert summary["degraded"] is False
    active = summary["active_working"]
    assert len(active) == 1
    assert active[0]["progress"]["percent"] == 50
    assert active[0]["progress"]["sprints"][1]["status"] == "in_progress"


def test_detailed_renders_progress_percent(fx):
    fx.add_session("epic-run", plan_name="s2-loop")
    fx.add_chain_health("epic-run", current_plan_name="s2-loop", completed_count=1, milestone_count=4)
    snap = fx.build(watchdog_report_path=fx.root / "absent.json")
    detailed = sf.format_cloud_status_detailed(snap)
    assert "progress=25%" in detailed
