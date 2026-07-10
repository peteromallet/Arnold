"""Fixture-driven tests for the canonical cloud status snapshot.

These lock in the contract from
``docs/ops/elegant-cloud-status-resident-plan.md``: the snapshot is produced by
local observation only, classifies sessions into a stable vocabulary, and is the
single source every status consumer reads.
"""

from __future__ import annotations

import hashlib
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

    def add_plan_state(
        self,
        session: str,
        plan_name: str,
        *,
        current_state: str = "finalized",
        active_step: dict | None = None,
    ) -> None:
        plan_dir = self.root / session / ".megaplan" / "plans" / plan_name
        plan_dir.mkdir(parents=True, exist_ok=True)
        payload: dict = {"name": plan_name, "current_state": current_state}
        if active_step is not None:
            payload["active_step"] = active_step
        (plan_dir / "state.json").write_text(json.dumps(payload), encoding="utf-8")

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



def test_active_repair_overrides_stale_needs_human_marker(fx):
    fx.add_session("repairing", plan_name="planR")
    fx.add_chain_health(
        "repairing",
        current_plan_name="planR",
        last_state="blocked",
        updated_at=NOW - timedelta(hours=3),
    )
    fx.add_needs_human("repairing", summary="old deterministic failure")
    fx.add_repair_progress("repairing", updated_at=NOW - timedelta(minutes=2))
    fx.add_repair_data("repairing", outcome="repairing")

    snap = fx.build()
    entry = _by_session(snap, "repairing")

    assert entry["status"] == "repairing"
    assert entry["repairing"] is True
    assert entry["operator_next"] == "automated repair dispatched for this session"
    assert snap["summary"]["repairing"] == 1
    assert snap["summary"]["blocked"] == 0

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
    fx.add_repair_data("recovered", outcome="complete")

    snap = fx.build()
    entry = _by_session(snap, "recovered")
    assert entry["status"] == "attention"
    assert entry["repairing"] is False


def test_live_process_with_current_phase_failure_is_attention(fx):
    fx.add_session("alive-failed", plan_name="planFailed")
    fx.add_chain_health(
        "alive-failed",
        current_plan_name="planFailed",
        last_state="finalized",
        updated_at=NOW - timedelta(minutes=5),
    )
    fx.add_plan_state(
        "alive-failed",
        "planFailed",
        current_state="finalized",
    )
    state_path = fx.root / "alive-failed" / ".megaplan" / "plans" / "planFailed" / "state.json"
    payload = json.loads(state_path.read_text(encoding="utf-8"))
    payload["latest_failure"] = {
        "kind": "phase_failed",
        "phase": "execute",
        "message": "ValueError: module must be a Python identifier",
    }
    state_path.write_text(json.dumps(payload), encoding="utf-8")

    snap = fx.build(liveness_probe=lambda _marker: {"tmux": False, "process": True})
    entry = _by_session(snap, "alive-failed")
    assert entry["status"] == "attention"
    assert entry["repairing"] is False
    assert "alive_but_failed" in entry["operator_next"]


def test_recent_execution_blocked_without_runner_is_attention_not_running(fx):
    fx.add_session("blocked-execute", plan_name="planBlocked")
    fx.add_chain_health(
        "blocked-execute",
        current_plan_name="planBlocked",
        last_state="blocked",
        updated_at=NOW - timedelta(seconds=30),
    )
    fx.add_plan_state(
        "blocked-execute",
        "planBlocked",
        current_state="blocked",
    )
    state_path = (
        fx.root
        / "blocked-execute"
        / ".megaplan"
        / "plans"
        / "planBlocked"
        / "state.json"
    )
    payload = json.loads(state_path.read_text(encoding="utf-8"))
    payload["latest_failure"] = {
        "kind": "execution_blocked",
        "phase": "execute",
        "message": "execute reported prerequisite-blocked tasks: T1",
    }
    state_path.write_text(json.dumps(payload), encoding="utf-8")

    snap = fx.build(liveness_probe=lambda _marker: {"tmux": False, "process": False})
    entry = _by_session(snap, "blocked-execute")

    assert entry["status"] == "attention"
    assert entry["operator_next"] == "alive_but_failed: current repairable failure receipt remains"
    assert snap["summary"]["running"] == 0
    assert snap["summary"]["attention"] == 1


def test_live_process_with_failed_no_next_step_is_attention(fx):
    fx.add_session("alive-no-next", plan_name="planStuck")
    fx.add_chain_health(
        "alive-no-next",
        current_plan_name="planStuck",
        last_state="failed",
        updated_at=NOW - timedelta(minutes=5),
    )
    fx.add_plan_state(
        "alive-no-next",
        "planStuck",
        current_state="failed",
    )
    state_path = fx.root / "alive-no-next" / ".megaplan" / "plans" / "planStuck" / "state.json"
    payload = json.loads(state_path.read_text(encoding="utf-8"))
    payload["latest_failure"] = {
        "kind": "no_next_step",
        "phase": "",
        "message": "no next_step and no override available",
    }
    state_path.write_text(json.dumps(payload), encoding="utf-8")

    snap = fx.build(liveness_probe=lambda _marker: {"tmux": False, "process": True})
    entry = _by_session(snap, "alive-no-next")
    assert entry["status"] == "attention"
    assert entry["repairing"] is False
    assert "alive_but_failed" in entry["operator_next"]


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
    assert entry["status"] == "repairing"
    assert entry["repairing"] is True


def test_active_plan_step_counts_as_live_process_and_latest_activity(fx, monkeypatch):
    fx.add_session("manual", plan_name="planManual")
    fx.add_chain_health(
        "manual",
        current_plan_name="planManual",
        last_state="finalized",
        updated_at=NOW - timedelta(hours=2),
    )
    fx.add_plan_state(
        "manual",
        "planManual",
        active_step={
            "phase": "execute",
            "worker_pid": 4242,
            "started_at": (NOW - timedelta(minutes=40)).isoformat(),
            "last_activity_at": (NOW - timedelta(minutes=2)).isoformat(),
        },
    )
    monkeypatch.setattr(ss, "_pid_is_live", lambda pid: pid == 4242)

    snap = fx.build()
    entry = _by_session(snap, "manual")

    assert entry["status"] == "running"
    assert entry["process"] is True
    assert entry["operator_next"] == "live runner process observed"
    assert entry["latest_activity"] == "2026-07-04T22:11:15Z"


def test_plan_live_activity_sidecar_does_not_count_as_live_process_without_pid(fx):
    fx.add_session("manual", plan_name="planManual")
    fx.add_chain_health(
        "manual",
        current_plan_name="planManual",
        last_state="finalized",
        updated_at=NOW - timedelta(hours=2),
    )
    sidecar = fx.marker_dir / "manual.chain-health.progress.json"
    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    payload["plan_has_active_step"] = True
    payload["plan_has_live_activity"] = True
    payload["plan_signal_liveness"] = "progressing"
    sidecar.write_text(json.dumps(payload), encoding="utf-8")

    snap = fx.build()
    entry = _by_session(snap, "manual")

    assert entry["status"] == "attention"
    assert entry["process"] is False
    assert "stalled" in entry["operator_next"]



def test_live_activity_supersedes_stale_needs_human_and_chain_health_plan(fx):
    spec = fx.root / "native" / ".megaplan" / "initiatives" / "demo" / "chain.yaml"
    spec.parent.mkdir(parents=True, exist_ok=True)
    spec.write_text("milestones: []\n", encoding="utf-8")
    workspace = fx.add_session("native", remote_spec=str(spec))
    old_plan = "plan-old"
    new_plan = "plan-new"
    fx.add_chain_health(
        "native",
        current_plan_name=old_plan,
        last_state="blocked",
        updated_at=NOW - timedelta(hours=1),
    )
    chain_digest = hashlib.sha1(str(spec.resolve()).encode("utf-8")).hexdigest()[:12]
    chain_state = workspace / ".megaplan" / "plans" / ".chains" / f"chain-{chain_digest}.json"
    chain_state.parent.mkdir(parents=True, exist_ok=True)
    chain_state.write_text(
        json.dumps({"current_plan_name": new_plan, "last_state": "blocked"}),
        encoding="utf-8",
    )
    fx.add_plan_state(
        "native",
        new_plan,
        current_state="finalized",
        active_step={
            "phase": "execute",
            "worker_pid": 4242,
            "last_activity_at": (NOW - timedelta(minutes=1)).isoformat(),
        },
    )
    (fx.repair_dir / "native.needs-human.json").write_text(
        json.dumps(
            {
                "session": "native",
                "summary": "old escalation",
                "recorded_at": (NOW - timedelta(minutes=10)).isoformat(),
                "current_plan_name": old_plan,
            }
        ),
        encoding="utf-8",
    )

    snap = fx.build(liveness_probe=lambda _marker: {"tmux": False, "process": True})
    entry = _by_session(snap, "native")

    assert entry["status"] == "running"
    assert entry["current_plan"] == new_plan
    assert entry["operator_next"] == "live runner activity supersedes older needs-human marker"

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


def test_newer_incomplete_done_chain_state_beats_watchdog_complete_verdict(fx):
    workspace = fx.root / "epic-run"
    spec_path = workspace / ".megaplan" / "initiatives" / "demo" / "chain.yaml"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text(
        "milestones:\n"
        "  - label: m1\n"
        "    idea: m1.md\n"
        "  - label: m2\n"
        "    idea: m2.md\n"
        "  - label: m3\n"
        "    idea: m3.md\n"
        "  - label: m4\n"
        "    idea: m4.md\n",
        encoding="utf-8",
    )
    fx.add_session("epic-run", workspace=str(workspace), remote_spec=str(spec_path))
    fx.add_chain_health(
        "epic-run",
        chain_complete=False,
        completed_count=0,
        milestone_count=4,
        current_plan_name="m4-demo-plan",
        last_state="failed",
        updated_at=NOW - timedelta(hours=6),
    )
    fx.add_watchdog_report(
        items=[{"session": "epic-run", "status": "complete", "action": "observe", "message": "chain complete"}]
    )

    digest = hashlib.sha1(str(spec_path.resolve()).encode("utf-8")).hexdigest()[:12]
    chain_state_path = workspace / ".megaplan" / "plans" / ".chains" / f"chain-{digest}.json"
    chain_state_path.parent.mkdir(parents=True, exist_ok=True)
    chain_state_path.write_text(
        json.dumps(
            {
                "current_milestone_index": 4,
                "last_state": "done",
                "completed": [{"label": "m1", "status": "done"}],
            }
        ),
        encoding="utf-8",
    )

    snap = fx.build(watchdog_report_path=fx.root / "watchdog-report.json")
    entry = _by_session(snap, "epic-run")

    assert entry["status"] == "attention"
    assert entry["chain_complete"] is False
    assert entry["completed_count"] == 1
    assert entry["milestone_count"] == 4
    assert "chain custody mismatch" in entry["operator_next"]


def test_newer_four_of_four_chain_state_unlocks_complete_status(fx):
    workspace = fx.root / "epic-run"
    spec_path = workspace / ".megaplan" / "initiatives" / "demo" / "chain.yaml"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text(
        "milestones:\n"
        "  - label: m1\n"
        "    idea: m1.md\n"
        "  - label: m2\n"
        "    idea: m2.md\n"
        "  - label: m3\n"
        "    idea: m3.md\n"
        "  - label: m4\n"
        "    idea: m4.md\n",
        encoding="utf-8",
    )
    fx.add_session("epic-run", workspace=str(workspace), remote_spec=str(spec_path))
    fx.add_chain_health(
        "epic-run",
        chain_complete=False,
        completed_count=0,
        milestone_count=4,
        current_plan_name="m4-demo-plan",
        last_state="failed",
        updated_at=NOW - timedelta(hours=6),
    )
    fx.add_watchdog_report(
        items=[{"session": "epic-run", "status": "complete", "action": "observe", "message": "chain complete"}]
    )

    digest = hashlib.sha1(str(spec_path.resolve()).encode("utf-8")).hexdigest()[:12]
    chain_state_path = workspace / ".megaplan" / "plans" / ".chains" / f"chain-{digest}.json"
    chain_state_path.parent.mkdir(parents=True, exist_ok=True)
    chain_state_path.write_text(
        json.dumps(
            {
                "current_milestone_index": 4,
                "last_state": "done",
                "completed": [
                    {"label": "m1", "status": "done"},
                    {"label": "m2", "status": "done"},
                    {"label": "m3", "status": "done"},
                    {"label": "m4", "status": "done"},
                ],
            }
        ),
        encoding="utf-8",
    )

    snap = fx.build(watchdog_report_path=fx.root / "watchdog-report.json")
    entry = _by_session(snap, "epic-run")

    assert entry["status"] == "complete"
    assert entry["should_run"] is False
    assert entry["chain_complete"] is True
    assert entry["completed_count"] == 4
    assert entry["milestone_count"] == 4
    assert entry["progress"]["percent"] == 100


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


def test_snapshot_adds_separate_read_only_shadow_views_without_reclassification(fx):
    workspace = fx.add_session("shadowed", plan_name="plan-a")
    fx.add_chain_health(
        "shadowed",
        current_plan_name="plan-a",
        completed_count=1,
        milestone_count=3,
        pr_number=42,
        pr_state="open",
    )
    fx.add_plan_state("shadowed", "plan-a", current_state="executed")

    entry = _by_session(fx.build(), "shadowed")

    # Existing compatibility fields and classification retain their established
    # values even when the sibling views disagree about runner/publication state.
    assert {
        key: entry[key]
        for key in ("session", "workspace", "status", "should_run", "current_plan", "pr_number", "pr_state")
    } == {
        "session": "shadowed",
        "workspace": str(workspace),
        "status": "running",
        "should_run": True,
        "current_plan": "plan-a",
        "pr_number": 42,
        "pr_state": "open",
    }
    sections = [entry["execution_authority"], entry["runner"], entry["publication"]]
    assert all(section["shadow"] is True and section["read_only"] is True for section in sections)
    assert len({section["view_hash"] for section in sections}) == 3
    assert entry["execution_authority"]["accepted_task_ids"] == []
    assert any(
        item["code"] == "legacy_plan_state_observation"
        and item["source"].endswith("/plan-a/state.json")
        for item in entry["execution_authority"]["diagnostics"]
    )
    assert entry["runner"]["status"] == "stopped"
    publication = {item["field"]: item for item in entry["publication"]["observations"]}
    assert publication["pull_request"]["value"] == "42"
    assert publication["branch"]["state"] == "unknown"


def test_shadow_views_reuse_collected_contradiction_paths_and_are_deterministic(fx):
    fx.add_session("contradicted", plan_name="marker-plan")
    fx.add_chain_health("contradicted", current_plan_name="chain-plan")
    marker_file = fx.marker_dir / "contradicted.json"
    marker = json.loads(marker_file.read_text(encoding="utf-8"))
    marker["branch"] = "marker-branch"
    marker_file.write_text(json.dumps(marker), encoding="utf-8")
    health_file = fx.marker_dir / "contradicted.chain-health.progress.json"
    health = json.loads(health_file.read_text(encoding="utf-8"))
    health["branch"] = "health-branch"
    health_file.write_text(json.dumps(health), encoding="utf-8")

    first = _by_session(fx.build(), "contradicted")
    second = _by_session(fx.build(), "contradicted")

    for name in ("execution_authority", "runner", "publication"):
        assert first[name] == second[name]
    diagnostics = first["publication"]["diagnostics"]
    assert any(
        item["code"] == "publication_observation_contradiction"
        and "contradicted.json" in item["source"]
        and "contradicted.chain-health.progress.json" in item["source"]
        and item["reason"] == "conflicting observations for branch"
        for item in diagnostics
    )


def test_detailed_status_renders_separate_shadow_views_with_hashes_and_sources(fx):
    fx.add_session("contradicted", plan_name="marker-plan")
    fx.add_chain_health("contradicted", current_plan_name="chain-plan")
    marker_file = fx.marker_dir / "contradicted.json"
    marker = json.loads(marker_file.read_text(encoding="utf-8"))
    marker["branch"] = "marker-branch"
    marker_file.write_text(json.dumps(marker), encoding="utf-8")
    health_file = fx.marker_dir / "contradicted.chain-health.progress.json"
    health = json.loads(health_file.read_text(encoding="utf-8"))
    health["branch"] = "health-branch"
    health_file.write_text(json.dumps(health), encoding="utf-8")

    detailed = sf.format_cloud_status_detailed(fx.build())

    # The established session/evidence surface remains present, followed by
    # operator-facing views that do not imply authority or mutate the snapshot.
    assert "[running] contradicted" in detailed
    assert f"evidence: {marker_file}" in detailed
    assert "execution_authority [shadow, read-only]:" in detailed
    assert "runner [shadow, read-only]:" in detailed
    assert "publication [shadow, read-only]:" in detailed
    assert detailed.count("hash=") == 3
    assert "observation: branch=contradicted" in detailed
    assert "diagnostic: publication_observation_contradiction subject=branch" in detailed
    assert str(marker_file) in detailed
    assert str(health_file) in detailed


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


def test_has_local_markers_independent_of_env(tmp_path, monkeypatch):
    # P0: the resident's build-vs-read trigger is marker-dir presence, NOT the
    # trust env var — a manually-restarted resident that lost
    # MEGAPLAN_TRUSTED_CONTAINER must still build fresh when on the box.
    monkeypatch.delenv("MEGAPLAN_TRUSTED_CONTAINER", raising=False)
    monkeypatch.setattr(ss, "DEFAULT_MARKER_DIR", tmp_path)
    assert ss.has_local_markers() is True  # marker dir present, env unset
    custom = tmp_path / "elsewhere"
    assert ss.has_local_markers(custom) is False
    custom.mkdir()
    assert ss.has_local_markers(custom) is True
    monkeypatch.setattr(ss, "DEFAULT_MARKER_DIR", tmp_path / "does-not-exist")
    assert ss.has_local_markers() is False


def test_plan_activity_summary_degraded_on_stale_banner():
    # P1: a sanitized stale snapshot surfaces as degraded with empty buckets so
    # consumers can't read "0 running" off a frozen view.
    snap = {
        "stale_banner": "WATCHDOG STALE",
        "stale_reason": "snapshot stale (9000s old, limit 7200s)",
        "sessions": [],
    }
    derived = ss.plan_activity_summary(snap)
    assert derived["degraded"] is True
    assert derived["stale_banner"] == "WATCHDOG STALE"
    assert derived["active_working"] == []
    assert derived["should_be_working_but_needs_attention"] == []
    assert derived["recently_completed"] == []


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
    assert entry["progress"]["percent"] == 44
    assert entry["progress"]["current_plan"] == "s2-front-half-2026"
    statuses = [s["status"] for s in entry["progress"]["sprints"]]
    assert statuses == ["done", "in_progress", "pending", "pending"]


def test_newer_terminal_chain_state_with_missing_completed_records_is_attention(fx):
    workspace = fx.root / "epic-run"
    spec_path = fx.root / "chain.yaml"
    spec_path.write_text(
        "base_branch: main\n"
        "milestones:\n"
        "  - label: m1\n"
        "    idea: m1.md\n"
        "  - label: m2\n"
        "    idea: m2.md\n"
        "  - label: m3\n"
        "    idea: m3.md\n"
        "  - label: m4\n"
        "    idea: m4.md\n",
        encoding="utf-8",
    )
    fx.add_session("epic-run", workspace=str(workspace), remote_spec=str(spec_path))
    fx.add_chain_health(
        "epic-run",
        chain_complete=True,
        completed_count=4,
        milestone_count=4,
        current_plan_name="",
        last_state="done",
        updated_at=NOW - timedelta(minutes=5),
    )
    chain_dir = workspace / ".megaplan" / "plans" / ".chains"
    chain_dir.mkdir(parents=True, exist_ok=True)
    (chain_dir / "chain.json").write_text(
        json.dumps(
            {
                "current_milestone_index": 4,
                "last_state": "done",
                "completed": [{"label": "m1", "pr_number": 93, "pr_state": "merged"}],
            }
        ),
        encoding="utf-8",
    )

    snap = fx.build()
    entry = _by_session(snap, "epic-run")

    assert entry["status"] == "attention"
    assert entry["chain_complete"] is False
    assert entry["completed_count"] == 1
    assert entry["milestone_count"] == 4
    assert entry["progress"]["percent"] == 25
    assert "chain custody mismatch" in entry["operator_next"]


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
    assert active[0]["progress"]["percent"] == 88
    assert active[0]["progress"]["sprints"][1]["status"] == "in_progress"


def test_detailed_renders_progress_percent(fx):
    fx.add_session("epic-run", plan_name="s2-loop")
    fx.add_chain_health("epic-run", current_plan_name="s2-loop", completed_count=1, milestone_count=4)
    snap = fx.build(watchdog_report_path=fx.root / "absent.json")
    detailed = sf.format_cloud_status_detailed(snap)
    assert "progress=44%" in detailed


# --- per-plan stage % (in-flight plan estimate) ---------------------------


def test_plan_stage_percent_maps_ladder_rungs():
    # completed-stages / total-stages across the 8 rungs; initialized = 0%.
    assert ss._plan_stage_percent("") is None
    assert ss._plan_stage_percent("initialized") == 0
    assert ss._plan_stage_percent("prepped") == 12
    assert ss._plan_stage_percent("planned") == 25
    assert ss._plan_stage_percent("gated") == 50
    assert ss._plan_stage_percent("executed") == 75
    assert ss._plan_stage_percent("reviewed") == 88
    assert ss._plan_stage_percent("done") == 100


def test_plan_stage_percent_none_for_off_ladder_states():
    for off_ladder in (
        "blocked",
        "failed",
        "aborted",
        "awaiting_pr_merge",
        "awaiting_human_verify",
        "tiebreaker_pending",
        "nonsense",
    ):
        assert ss._plan_stage_percent(off_ladder) is None


def test_session_progress_carries_in_flight_plan_percent():
    progress = ss._session_progress(
        completed_count=1,
        milestone_count=3,
        current_plan="s2-loop-2026",
        complete=False,
        plan_state="executed",
    )
    assert progress["plan_state"] == "executed"
    assert progress["plan_percent"] == 75
    in_flight = progress["sprints"][1]
    assert in_flight["status"] == "in_progress"
    assert in_flight["plan_state"] == "executed"
    assert in_flight["plan_percent"] == 75


def test_session_progress_state_label_without_percent_when_blocked():
    progress = ss._session_progress(
        completed_count=0,
        milestone_count=2,
        current_plan="s1-x",
        complete=False,
        plan_state="blocked",
    )
    # blocked is off the ladder → no percent, but the raw state is still exposed.
    assert progress["plan_state"] == "blocked"
    assert "plan_percent" not in progress
    in_flight = progress["sprints"][0]
    assert in_flight["plan_state"] == "blocked"
    assert "plan_percent" not in in_flight


def test_session_progress_no_plan_keys_without_state():
    progress = ss._session_progress(
        completed_count=1, milestone_count=3, current_plan="s2-x", complete=False
    )
    assert "plan_state" not in progress
    assert "plan_percent" not in progress
    assert "plan_state" not in progress["sprints"][1]


def test_session_progress_no_plan_keys_when_complete():
    progress = ss._session_progress(
        completed_count=2,
        milestone_count=2,
        current_plan=None,
        complete=True,
        plan_state="done",
    )
    # No in-flight plan on a complete chain → no per-plan estimate.
    assert "plan_state" not in progress
    assert "plan_percent" not in progress


def test_session_entry_carries_plan_percent_from_last_state(fx):
    fx.add_session("epic-run", plan_name="s2-loop")
    fx.add_chain_health(
        "epic-run",
        current_plan_name="s2-loop",
        completed_count=1,
        milestone_count=4,
        last_state="reviewed",
    )
    snap = fx.build()
    entry = _by_session(snap, "epic-run")
    assert entry["progress"]["plan_state"] == "reviewed"
    assert entry["progress"]["plan_percent"] == 88


def test_plan_activity_summary_propagates_plan_percent(fx):
    fx.add_session("epic-run", plan_name="s2-loop")
    fx.add_chain_health(
        "epic-run",
        current_plan_name="s2-loop",
        completed_count=1,
        milestone_count=4,
        last_state="executed",
    )
    snap = fx.build()
    active = ss.plan_activity_summary(snap)["active_working"]
    assert active[0]["progress"]["plan_percent"] == 75
    assert active[0]["progress"]["plan_state"] == "executed"


def test_detailed_renders_plan_percent_and_state(fx):
    fx.add_session("epic-run", plan_name="s2-loop")
    fx.add_chain_health(
        "epic-run",
        current_plan_name="s2-loop",
        completed_count=1,
        milestone_count=4,
        last_state="executed",
    )
    snap = fx.build(watchdog_report_path=fx.root / "absent.json")
    detailed = sf.format_cloud_status_detailed(snap)
    assert "progress=44%" in detailed
    assert "plan=75% (executed)" in detailed


def test_epic_percent_folds_in_flight_plan_fraction():
    # Epic % = (completed + plan_percent/100) / total, so it advances with the
    # in-flight plan instead of freezing between milestones.
    gated = ss._session_progress(
        completed_count=2, milestone_count=8, current_plan="s3-x", complete=False, plan_state="gated"
    )
    assert gated["plan_percent"] == 50
    assert gated["percent"] == 31  # (2 + 0.5) / 8 = 31.25 -> 31
    executed = ss._session_progress(
        completed_count=2, milestone_count=8, current_plan="s3-x", complete=False, plan_state="executed"
    )
    assert executed["percent"] == 34  # (2 + 0.75) / 8 = 34.375 -> 34
    # No plan-stage signal -> plain completed/total (frozen milestone view).
    no_state = ss._session_progress(
        completed_count=2, milestone_count=8, current_plan="s3-x", complete=False
    )
    assert no_state["percent"] == 25


def test_detailed_renders_plan_state_when_not_percentageable(fx):
    fx.add_session("blk", plan_name="s1-x")
    fx.add_chain_health(
        "blk",
        current_plan_name="s1-x",
        completed_count=0,
        milestone_count=3,
        last_state="blocked",
    )
    fx.add_needs_human("blk")
    snap = fx.build(watchdog_report_path=fx.root / "absent.json")
    detailed = sf.format_cloud_status_detailed(snap)
    assert "plan=blocked" in detailed
    assert "plan=blocked%" not in detailed


# --- progress history + time-series deltas --------------------------------


def test_append_progress_history_writes_compact_row(tmp_path):
    history = tmp_path / "progress-history.jsonl"
    snapshot = {
        "sessions": [
            {
                "session": "s1",
                "progress": {"percent": 30, "plan_percent": 60, "plan_state": "executed", "current_plan": "p1"},
            }
        ]
    }
    ss.append_progress_history(snapshot, history, now=NOW)
    ss.append_progress_history(snapshot, history, now=NOW)
    lines = history.read_text().splitlines()
    assert len(lines) == 2
    row = json.loads(lines[0])
    assert row["ts"]
    assert row["sessions"] == [
        {"session": "s1", "epic_percent": 30, "plan_percent": 60, "plan_state": "executed", "current_plan": "p1"}
    ]


def test_append_progress_history_skips_sessions_without_progress(tmp_path):
    history = tmp_path / "progress-history.jsonl"
    ss.append_progress_history({"sessions": [{"session": "s1"}]}, history, now=NOW)
    assert not history.exists()


def test_compute_progress_deltas_windows_and_plan_start(tmp_path):
    history = tmp_path / "ph.jsonl"
    base = datetime(2026, 7, 6, 14, 0, 0, tzinfo=timezone.utc)
    # t-90m: epic 20 plan-A · t-40m: epic 30 plan-A · now: epic 45 plan-B
    for offset_min, pct, plan in ((90, 20, "plan-A"), (40, 30, "plan-A"), (0, 45, "plan-B")):
        ss.append_progress_history(
            {"sessions": [{"session": "s1", "progress": {"percent": pct, "current_plan": plan}}]},
            history,
            now=base - timedelta(minutes=offset_min),
        )
    deltas = ss.compute_progress_deltas(
        history_path=history, session="s1", now=base, started_at="2026-07-06T12:00:00Z", now_percent=45
    )
    assert deltas["epic_delta_1h"] == 25  # 45 - 20 (latest sample >=1h old)
    assert deltas["epic_delta_5h"] is None  # nothing 5h back -> honestly omitted
    assert deltas["plan_started_at"].startswith("2026-07-06T14:00:00")  # A->B transition
    assert deltas["epic_started_at"] == "2026-07-06T12:00:00Z"  # marker started_at preferred


def test_compute_progress_deltas_none_without_history(tmp_path):
    assert ss.compute_progress_deltas(history_path=tmp_path / "absent.jsonl", session="s1", now=NOW) is None


def test_compute_progress_deltas_none_for_unknown_session(tmp_path):
    history = tmp_path / "ph.jsonl"
    ss.append_progress_history(
        {"sessions": [{"session": "other", "progress": {"percent": 10, "current_plan": "p"}}]}, history, now=NOW
    )
    assert ss.compute_progress_deltas(history_path=history, session="s1", now=NOW) is None


def test_snapshot_enriches_progress_with_deltas(tmp_path, fx):
    history = tmp_path / "ph.jsonl"
    # completed=1/4 + executed(75%) -> epic 44. Seed history: 24 at 2h ago, 34 at 1h ago.
    for offset_min, pct in ((120, 24), (60, 34)):
        ss.append_progress_history(
            {"sessions": [{"session": "epic-run", "progress": {"percent": pct, "current_plan": "s2-loop"}}]},
            history,
            now=NOW - timedelta(minutes=offset_min),
        )
    fx.add_session("epic-run", plan_name="s2-loop")
    fx.add_chain_health(
        "epic-run", current_plan_name="s2-loop", completed_count=1, milestone_count=4, last_state="executed"
    )
    snap = fx.build(history_path=history)
    progress = _by_session(snap, "epic-run")["progress"]
    assert progress["percent"] == 44
    assert progress["epic_delta_1h"] == 10  # 44 - 34 (sample ~1h ago)
    assert progress["epic_delta_5h"] is None
    assert progress["plan_started_at"].startswith("2026-07-04T20")  # first sample ~NOW-2h


def test_detailed_renders_epic_deltas(fx, tmp_path):
    history = tmp_path / "ph.jsonl"
    ss.append_progress_history(
        {"sessions": [{"session": "epic-run", "progress": {"percent": 24, "current_plan": "s2-loop"}}]},
        history,
        now=NOW - timedelta(minutes=60),
    )
    fx.add_session("epic-run", plan_name="s2-loop")
    fx.add_chain_health(
        "epic-run", current_plan_name="s2-loop", completed_count=1, milestone_count=4, last_state="executed"
    )
    snap = fx.build(history_path=history, watchdog_report_path=fx.root / "absent.json")
    detailed = sf.format_cloud_status_detailed(snap)
    assert "(+20%/1h)" in detailed  # 44 now - 24 an hour ago


def test_compute_progress_deltas_stage_changes(tmp_path):
    history = tmp_path / "ph.jsonl"
    base = datetime(2026, 7, 6, 14, 0, 0, tzinfo=timezone.utc)
    # t-90m: planned · t-40m: gated · now: finalized
    for offset_min, plan_state in ((90, "planned"), (40, "gated"), (0, "finalized")):
        ss.append_progress_history(
            {
                "sessions": [
                    {"session": "s1", "progress": {"percent": 10, "current_plan": "p", "plan_state": plan_state}}
                ]
            },
            history,
            now=base - timedelta(minutes=offset_min),
        )
    deltas = ss.compute_progress_deltas(history_path=history, session="s1", now=base, now_percent=10)
    # prior (>=1h old) = planned; window newly reached gated then finalized
    assert deltas["stage_changes_1h"] == ["gated", "finalized"]


def test_compute_progress_deltas_stage_changes_empty_when_static(tmp_path):
    history = tmp_path / "ph.jsonl"
    base = datetime(2026, 7, 6, 14, 0, 0, tzinfo=timezone.utc)
    for offset_min in (90, 40, 0):
        ss.append_progress_history(
            {
                "sessions": [
                    {"session": "s1", "progress": {"percent": 10, "current_plan": "p", "plan_state": "finalized"}}
                ]
            },
            history,
            now=base - timedelta(minutes=offset_min),
        )
    deltas = ss.compute_progress_deltas(history_path=history, session="s1", now=base, now_percent=10)
    # held finalized the whole window -> no new stages
    assert deltas["stage_changes_1h"] == []


def test_compute_progress_deltas_stage_changes_skips_off_ladder(tmp_path):
    history = tmp_path / "ph.jsonl"
    base = datetime(2026, 7, 6, 14, 0, 0, tzinfo=timezone.utc)
    # prior: planned; window: authority_divergence (off-ladder, ignored) then finalized
    for offset_min, plan_state in ((90, "planned"), (40, "authority_divergence"), (0, "finalized")):
        ss.append_progress_history(
            {
                "sessions": [
                    {"session": "s1", "progress": {"percent": 10, "current_plan": "p", "plan_state": plan_state}}
                ]
            },
            history,
            now=base - timedelta(minutes=offset_min),
        )
    deltas = ss.compute_progress_deltas(history_path=history, session="s1", now=base, now_percent=10)
    assert deltas["stage_changes_1h"] == ["finalized"]  # authority_divergence skipped


def test_detailed_renders_stage_changes(fx, tmp_path):
    history = tmp_path / "ph.jsonl"
    base = NOW
    for offset_min, plan_state in ((90, "planned"), (0, "gated")):
        ss.append_progress_history(
            {
                "sessions": [
                    {"session": "epic-run", "progress": {"percent": 20, "current_plan": "s2-loop", "plan_state": plan_state}}
                ]
            },
            history,
            now=base - timedelta(minutes=offset_min),
        )
    fx.add_session("epic-run", plan_name="s2-loop")
    fx.add_chain_health(
        "epic-run", current_plan_name="s2-loop", completed_count=0, milestone_count=4, last_state="gated"
    )
    snap = fx.build(history_path=history, watchdog_report_path=fx.root / "absent.json")
    detailed = sf.format_cloud_status_detailed(snap)
    assert "stages1h:gated" in detailed
