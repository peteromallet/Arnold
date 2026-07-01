from __future__ import annotations

import hashlib
import json
from pathlib import Path

from arnold_pipelines.megaplan.cloud.current_target import (
    compare_needs_human_diagnostic,
    resolve_current_target,
)


def test_resolve_current_target_prefers_live_child_session(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    repair_data_dir = marker_dir / "repair-data"
    marker_dir.mkdir()
    repair_data_dir.mkdir()
    workspace = tmp_path / "ws"
    workspace.mkdir()
    parent_spec = workspace / ".megaplan" / "initiatives" / "demo" / "assets" / "epic-chain.yaml"
    child_spec = workspace / ".megaplan" / "initiatives" / "demo" / "chain.yaml"
    parent_spec.parent.mkdir(parents=True)
    child_spec.parent.mkdir(parents=True, exist_ok=True)
    parent_spec.write_text("chains: []\n", encoding="utf-8")
    child_spec.write_text("milestones: []\n", encoding="utf-8")
    _write_marker(
        marker_dir / "parent-session.json",
        {
            "session": "parent-session",
            "workspace": str(workspace),
            "remote_spec": str(parent_spec),
            "run_kind": "chain",
            "plan_name": "m1-parent-plan",
        },
    )
    _write_marker(
        marker_dir / "child-session.json",
        {
            "session": "child-session",
            "workspace": str(workspace),
            "remote_spec": str(child_spec),
            "run_kind": "chain",
            "plan_name": "m2-child-plan",
        },
    )
    (marker_dir / "parent-session.repair-progress.json").write_text(
        json.dumps({"status": "waiting"}), encoding="utf-8"
    )

    record = resolve_current_target(
        "parent-session",
        marker_dir=marker_dir,
        repair_data_dir=repair_data_dir,
        session_is_live=lambda name: name == "child-session",
    )

    assert record["authoritative_source"] == "live_sibling_session"
    assert record["target_session"] == "child-session"
    assert record["repair_progress"]["present"] is True
    assert record["sibling_sessions"] == [
        {
            "session": "child-session",
            "marker_path": str(marker_dir / "child-session.json"),
            "run_kind": "chain",
            "plan_name": "m2-child-plan",
            "live_status": "alive",
        }
    ]
    assert record["stale_evidence"] == [
        {
            "kind": "missing_chain_state",
            "path": str(_chain_state_path(workspace, parent_spec)),
        },
        {
            "kind": "missing_plan_state",
            "path": str(workspace / ".megaplan" / "plans" / "m1-parent-plan" / "state.json"),
            "plan_name": "m1-parent-plan",
        },
        {
            "kind": "superseded_by_live_sibling",
            "path": str(marker_dir / "child-session.json"),
            "session": "child-session",
        },
    ]
    assert "live sibling session supersedes current marker: child-session" in record["rationale"]


def test_resolve_current_target_marks_stale_parent_from_chain_state(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    repair_data_dir = marker_dir / "repair-data"
    marker_dir.mkdir()
    repair_data_dir.mkdir()
    workspace = tmp_path / "ws"
    workspace.mkdir()
    spec_path = workspace / ".megaplan" / "initiatives" / "demo" / "chain.yaml"
    spec_path.parent.mkdir(parents=True)
    spec_path.write_text("milestones: []\n", encoding="utf-8")
    _write_marker(
        marker_dir / "demo-session.json",
        {
            "session": "demo-session",
            "workspace": str(workspace),
            "remote_spec": str(spec_path),
            "run_kind": "chain",
            "plan_name": "m1-old-plan",
        },
    )
    _write_chain_state(
        _chain_state_path(workspace, spec_path),
        {"current_plan_name": "m3-current-plan", "last_state": "awaiting_human"},
    )
    _write_plan(
        workspace / ".megaplan" / "plans" / "m3-current-plan",
        {"name": "m3-current-plan", "current_state": "awaiting_human"},
    )

    record = resolve_current_target("demo-session", marker_dir=marker_dir, repair_data_dir=repair_data_dir)

    assert record["authoritative_source"] == "chain_state"
    assert record["current_refs"]["marker_plan_name"] == "m1-old-plan"
    assert record["current_refs"]["current_plan_name"] == "m3-current-plan"
    assert record["stale_evidence"] == [
        {
            "current_plan": "m3-current-plan",
            "kind": "stale_marker_plan_ref",
            "observed_plan": "m1-old-plan",
            "path": str(marker_dir / "demo-session.json"),
        }
    ]
    assert record["rationale"] == ["marker plan reference is older than chain state"]


def test_resolve_current_target_marks_stale_needs_human(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    repair_data_dir = marker_dir / "repair-data"
    marker_dir.mkdir()
    repair_data_dir.mkdir()
    workspace = tmp_path / "ws"
    workspace.mkdir()
    spec_path = workspace / ".megaplan" / "initiatives" / "demo" / "chain.yaml"
    spec_path.parent.mkdir(parents=True)
    spec_path.write_text("milestones: []\n", encoding="utf-8")
    _write_marker(
        marker_dir / "demo-session.json",
        {
            "session": "demo-session",
            "workspace": str(workspace),
            "remote_spec": str(spec_path),
            "run_kind": "chain",
        },
    )
    _write_chain_state(
        _chain_state_path(workspace, spec_path),
        {"current_plan_name": "m3-current-plan", "last_state": "awaiting_human"},
    )
    _write_plan(
        workspace / ".megaplan" / "plans" / "m3-current-plan",
        {
            "name": "m3-current-plan",
            "current_state": "awaiting_human",
            "resume_cursor": {"retry_strategy": "manual_review"},
        },
        events_body='{"kind":"gate_entered"}\n{"kind":"state_written"}\n',
    )
    repair_data_path = repair_data_dir / "demo-session.repair-data.json"
    repair_data_path.write_text(
        json.dumps(
            {
                "iterations": [
                    {"chain_state_summary": {"current_plan_name": "m1-old-plan"}},
                ]
            }
        ),
        encoding="utf-8",
    )
    (repair_data_dir / "demo-session.needs-human.json").write_text(
        json.dumps(
            {
                "summary": "old repair exhaustion",
                "repair_data_path": str(repair_data_path),
                "chain_current_plan_name": "m1-old-plan",
            }
        ),
        encoding="utf-8",
    )

    record = resolve_current_target("demo-session", marker_dir=marker_dir, repair_data_dir=repair_data_dir)

    assert record["authoritative_source"] == "chain_state"
    assert record["event_cursors"] == {
        "events_path": str(workspace / ".megaplan" / "plans" / "m3-current-plan" / "events.ndjson"),
        "events_present": True,
        "line_count": 2,
        "latest_gate_kind": "gate_entered",
        "resume_retry_strategy": "manual_review",
    }
    assert record["needs_human"]["plan_refs"] == ["m1-old-plan"]
    assert record["stale_evidence"] == [
        {
            "current_plan": "m3-current-plan",
            "kind": "stale_needs_human_plan_ref",
            "observed_plans": ["m1-old-plan"],
            "path": str(repair_data_dir / "demo-session.needs-human.json"),
        }
    ]
    assert "needs-human sidecar references an older plan" in record["rationale"]


def test_resolve_current_target_reports_missing_state_deterministically(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    repair_data_dir = marker_dir / "repair-data"
    marker_dir.mkdir()
    repair_data_dir.mkdir()
    workspace = tmp_path / "ws"
    workspace.mkdir()
    spec_path = workspace / ".megaplan" / "initiatives" / "demo" / "chain.yaml"
    spec_path.parent.mkdir(parents=True)
    spec_path.write_text("milestones: []\n", encoding="utf-8")
    _write_marker(
        marker_dir / "demo-session.json",
        {
            "session": "demo-session",
            "workspace": str(workspace),
            "remote_spec": str(spec_path),
            "run_kind": "chain",
            "plan_name": "m2-plan",
            "pid": 4242,
        },
    )

    first = resolve_current_target(
        "demo-session",
        marker_dir=marker_dir,
        repair_data_dir=repair_data_dir,
        pid_is_live=lambda pid: False if pid == 4242 else None,
    )
    second = resolve_current_target(
        "demo-session",
        marker_dir=marker_dir,
        repair_data_dir=repair_data_dir,
        pid_is_live=lambda pid: False if pid == 4242 else None,
    )

    assert first == second
    assert first["authoritative_source"] == "marker"
    assert first["tmux_process"]["live_status"] == "stopped"
    assert first["stale_evidence"] == [
        {
            "kind": "missing_chain_state",
            "path": str(_chain_state_path(workspace, spec_path)),
        },
        {
            "kind": "missing_plan_state",
            "path": str(workspace / ".megaplan" / "plans" / "m2-plan" / "state.json"),
            "plan_name": "m2-plan",
        },
    ]


def test_resolve_current_target_tolerates_partial_evidence_fixture(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    repair_data_dir = marker_dir / "repair-data"
    marker_dir.mkdir()
    repair_data_dir.mkdir()
    (marker_dir / "partial-session.json").write_text('{"session":"partial-session","workspace":', encoding="utf-8")
    (repair_data_dir / "partial-session.needs-human.json").write_text("not-json", encoding="utf-8")
    (marker_dir / "ignored.reap-progress.json").write_text(json.dumps({"status": "old"}), encoding="utf-8")

    record = resolve_current_target("partial-session", marker_dir=marker_dir, repair_data_dir=repair_data_dir)

    assert record["authoritative_source"] == "marker"
    assert record["current_refs"] == {
        "workspace": "",
        "run_kind": "unknown",
        "remote_spec": "",
        "marker_plan_name": "",
        "current_plan_name": "",
        "chain_current_plan_name": "",
        "chain_last_state": "",
        "plan_current_state": "",
    }
    assert record["ignored_artifacts"] == []
    assert record["repair_progress"] == {"present": False, "items": []}
    assert record["stale_evidence"] == [
        {
            "kind": "invalid_marker_json",
            "path": str(marker_dir / "partial-session.json"),
        },
        {
            "kind": "invalid_needs_human_json",
            "path": str(repair_data_dir / "partial-session.needs-human.json"),
        },
    ]
    assert record["rationale"] == [
        "marker JSON was unreadable; continuing with partial evidence",
        "marker did not provide a usable remote spec",
        "marker did not provide a usable workspace",
    ]


def _write_marker(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_plan(plan_dir: Path, state: dict[str, object], events_body: str = "") -> None:
    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
    if events_body:
        (plan_dir / "events.ndjson").write_text(events_body, encoding="utf-8")


def _write_chain_state(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_compare_needs_human_diagnostic_agreement_when_both_stale(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    marker_dir = tmp_path / "markers"
    repair_data_dir = marker_dir / "repair-data"
    marker_dir.mkdir()
    repair_data_dir.mkdir()
    new_plan = "m3-new-plan"
    _write_plan(workspace / ".megaplan" / "plans" / new_plan, {"name": new_plan, "current_state": "running"})
    (marker_dir / "demo.json").write_text(
        json.dumps({"session": "demo", "workspace": str(workspace), "plan_name": new_plan}),
        encoding="utf-8",
    )
    sidecar = repair_data_dir / "demo.needs-human.json"
    sidecar.write_text(
        json.dumps({"summary": "old plan ref", "plan_name": "old-plan"}),
        encoding="utf-8",
    )

    # Legacy says stale (current plan "m3-new-plan" is NOT in sidecar's refs)
    # Resolver should also see it as stale because needs-human refs "old-plan"
    # but current plan is "m3-new-plan"
    diag = compare_needs_human_diagnostic(
        "demo",
        "m3-new-plan",
        marker_dir=marker_dir,
        repair_data_dir=repair_data_dir,
        legacy_matches=False,
        legacy_plans=["old-plan"],
    )
    assert diag["agreement"] is True
    assert diag["legacy"]["stale"] is True
    assert diag["resolver"]["stale"] is True


def test_compare_needs_human_diagnostic_agreement_when_both_current(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    marker_dir = tmp_path / "markers"
    repair_data_dir = marker_dir / "repair-data"
    marker_dir.mkdir()
    repair_data_dir.mkdir()
    plan_name = "current-plan"
    _write_plan(workspace / ".megaplan" / "plans" / plan_name, {"name": plan_name, "current_state": "running"})
    (marker_dir / "demo.json").write_text(
        json.dumps({"session": "demo", "workspace": str(workspace), "plan_name": plan_name}),
        encoding="utf-8",
    )
    sidecar = repair_data_dir / "demo.needs-human.json"
    sidecar.write_text(
        json.dumps({"summary": "current plan ref", "plan_name": plan_name}),
        encoding="utf-8",
    )

    # Legacy says match (current plan IS in sidecar refs)
    diag = compare_needs_human_diagnostic(
        "demo",
        plan_name,
        marker_dir=marker_dir,
        repair_data_dir=repair_data_dir,
        legacy_matches=True,
        legacy_plans=[plan_name],
    )
    assert diag["agreement"] is True
    assert diag["legacy"]["stale"] is False
    assert diag["resolver"]["stale"] is False


def test_compare_needs_human_diagnostic_reports_discrepancy(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    marker_dir = tmp_path / "markers"
    repair_data_dir = marker_dir / "repair-data"
    marker_dir.mkdir()
    repair_data_dir.mkdir()
    plan_name = "current-plan"
    _write_plan(workspace / ".megaplan" / "plans" / plan_name, {"name": plan_name, "current_state": "running"})
    (marker_dir / "demo.json").write_text(
        json.dumps({"session": "demo", "workspace": str(workspace), "plan_name": plan_name}),
        encoding="utf-8",
    )
    # Sidecar references current-plan, so resolver sees it as current
    sidecar = repair_data_dir / "demo.needs-human.json"
    sidecar.write_text(
        json.dumps({"summary": "still relevant", "plan_name": plan_name}),
        encoding="utf-8",
    )

    # Legacy (simulated) says stale, but resolver says current -> discrepancy
    diag = compare_needs_human_diagnostic(
        "demo",
        plan_name,
        marker_dir=marker_dir,
        repair_data_dir=repair_data_dir,
        legacy_matches=False,
        legacy_plans=["other-plan"],
    )
    assert diag["agreement"] is False
    assert diag["legacy"]["stale"] is True
    assert diag["resolver"]["stale"] is False


def _chain_state_path(workspace: Path, spec_path: Path) -> Path:
    digest = hashlib.sha1(str(spec_path.resolve()).encode("utf-8")).hexdigest()[:12]
    return workspace / ".megaplan" / "plans" / ".chains" / f"chain-{digest}.json"
