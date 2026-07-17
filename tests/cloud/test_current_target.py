from __future__ import annotations

import hashlib
import json
from pathlib import Path

from arnold_pipelines.megaplan.chain import spec as chain_spec
from arnold_pipelines.megaplan.cloud.current_target import (
    _collect_sibling_sessions,
    compare_needs_human_diagnostic,
    resolve_current_target,
)
from arnold_pipelines.megaplan.cloud.session_markers import (
    is_canonical_session_marker_path,
    is_canonical_sidecar_path,
    canonical_sidecar_suffix,
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
            "path": str(chain_spec._state_path_for(parent_spec)),
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
        "mtime": (workspace / ".megaplan" / "plans" / "m3-current-plan" / "events.ndjson").stat().st_mtime,
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
    assert first["evidence_state"]["status"] == "unknown"
    assert first["evidence_state"]["unknown_type"] == "partial"
    assert first["evidence_state"]["green"] is False
    assert first["evidence_state"]["mutation_eligible"] is False
    assert first["evidence_state"]["authorizes_mutation"] is False
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


def test_resolve_current_target_infers_chain_run_kind_from_legacy_marker(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    repair_data_dir = marker_dir / "repair-data"
    marker_dir.mkdir()
    repair_data_dir.mkdir()
    workspace = tmp_path / "ws"
    workspace.mkdir()
    spec_path = workspace / ".megaplan" / "initiatives" / "demo" / "chain.yaml"
    spec_path.parent.mkdir(parents=True)
    spec_path.write_text("milestones: []\n", encoding="utf-8")
    state_path = _chain_state_path(workspace, spec_path)
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        json.dumps({"current_plan_name": "m1-demo", "last_state": "done"}),
        encoding="utf-8",
    )
    _write_marker(
        marker_dir / "legacy.json",
        {
            "session": "legacy",
            "workspace": str(workspace),
            "remote_spec": str(spec_path),
        },
    )

    record = resolve_current_target("legacy", marker_dir=marker_dir, repair_data_dir=repair_data_dir)

    assert record["current_refs"]["run_kind"] == "chain"
    assert record["authoritative_source"] == "chain_state"
    assert record["chain_state"]["path"] == str(state_path)
    assert record["chain_state"]["current_plan_name"] == "m1-demo"


def test_resolve_current_target_uses_existing_fallback_chain_state_candidate(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    repair_data_dir = marker_dir / "repair-data"
    marker_dir.mkdir()
    repair_data_dir.mkdir()
    workspace = tmp_path / "ws"
    workspace.mkdir()
    spec_path = workspace / ".megaplan" / "initiatives" / "demo.chain" / "chain.yaml"
    spec_path.parent.mkdir(parents=True)
    spec_path.write_text("milestones: []\n", encoding="utf-8")
    fallback_state_path = chain_spec._state_path_candidates_for(spec_path)[1]
    fallback_state_path.parent.mkdir(parents=True, exist_ok=True)
    fallback_state_path.write_text(
        json.dumps({"current_plan_name": "m1-demo", "last_state": "finalized"}),
        encoding="utf-8",
    )
    _write_marker(
        marker_dir / "demo-session.json",
        {
            "session": "demo-session",
            "workspace": str(workspace),
            "remote_spec": str(spec_path),
            "run_kind": "chain",
        },
    )

    record = resolve_current_target("demo-session", marker_dir=marker_dir, repair_data_dir=repair_data_dir)

    assert record["authoritative_source"] == "chain_state"
    assert record["chain_state"]["present"] is True
    assert record["chain_state"]["path"] == str(fallback_state_path)
    assert record["current_refs"]["chain_current_plan_name"] == "m1-demo"
    assert record["stale_evidence"] == [
        {
            "kind": "missing_plan_state",
            "path": str(workspace / ".megaplan" / "plans" / "m1-demo" / "state.json"),
            "plan_name": "m1-demo",
        }
    ]


def test_resolve_current_target_prefers_terminal_plan_over_stale_chain_state(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    repair_data_dir = marker_dir / "repair-data"
    marker_dir.mkdir()
    repair_data_dir.mkdir()
    workspace = tmp_path / "ws"
    workspace.mkdir()
    spec_path = workspace / ".megaplan" / "initiatives" / "demo" / "chain.yaml"
    spec_path.parent.mkdir(parents=True)
    spec_path.write_text("milestones: []\n", encoding="utf-8")
    plan_name = "m3-current-plan"
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
        {"current_plan_name": plan_name, "last_state": "executed"},
    )
    _write_plan(
        workspace / ".megaplan" / "plans" / plan_name,
        {"name": plan_name, "current_state": "done"},
    )

    record = resolve_current_target("demo-session", marker_dir=marker_dir, repair_data_dir=repair_data_dir)

    assert record["authoritative_source"] == "plan_state"
    assert record["current_refs"]["current_plan_name"] == plan_name
    assert record["current_refs"]["plan_current_state"] == "done"
    assert record["stale_evidence"] == [
        {
            "kind": "stale_chain_state_after_terminal_plan",
            "path": str(_chain_state_path(workspace, spec_path)),
            "plan_name": plan_name,
            "plan_state": "done",
            "chain_last_state": "executed",
        }
    ]
    assert "terminal plan state supersedes stale chain state" in record["rationale"]


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
    assert record["evidence_state"]["unknown_type"] == "partial"
    assert record["current_refs"] == {
        "workspace": "",
        "run_kind": "unknown",
        "remote_spec": "",
        "marker_plan_name": "",
        "current_plan_name": "",
        "chain_current_plan_name": "",
        "chain_last_state": "",
        "plan_current_state": "",
        "plan_current_phase": "",
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
        {
            "kind": "spec_missing",
            "path": "",
        },
        {
            "kind": "workspace_missing",
            "path": "",
        },
    ]
    assert record["rationale"] == [
        "marker JSON was unreadable; continuing with partial evidence",
        "marker did not provide a usable remote spec",
        "marker did not provide a usable workspace",
    ]


def test_resolve_current_target_types_wholly_missing_evidence(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()

    record = resolve_current_target("absent", marker_dir=marker_dir)

    assert record["evidence_state"] == {
        "status": "unknown",
        "unknown_type": "missing",
        "issue_kinds": ["missing_marker_json", "spec_missing", "workspace_missing"],
        "mutation_eligible": False,
        "authorizes_mutation": False,
        "green": False,
    }


def test_resolve_current_target_accepts_explicit_wrapper_workspace_hint(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    workspace = tmp_path / "ws"
    workspace.mkdir()
    plan_name = "hinted-plan"
    _write_plan(
        workspace / ".megaplan" / "plans" / plan_name,
        {"name": plan_name, "current_state": "blocked"},
    )
    _write_marker(
        marker_dir / "hinted.json",
        {"session": "hinted", "run_kind": "plan", "plan_name": plan_name},
    )

    record = resolve_current_target(
        "hinted",
        marker_dir=marker_dir,
        workspace_hint=workspace,
    )

    assert record["current_refs"]["workspace"] == str(workspace)
    assert record["plan_state"]["present"] is True
    assert record["evidence_state"]["status"] == "resolved"
    assert record["evidence_state"]["mutation_eligible"] is True
    assert "wrapper workspace argument supplied the missing marker workspace" in record["rationale"]


def test_resolve_current_target_types_stale_evidence(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    workspace = tmp_path / "ws"
    workspace.mkdir()
    plan_name = "stale-plan"
    _write_plan(
        workspace / ".megaplan" / "plans" / plan_name,
        {
            "name": plan_name,
            "current_state": "executing",
            "active_step": {"phase": "execute", "worker_pid": 999999},
        },
    )
    _write_marker(
        marker_dir / "stale.json",
        {
            "session": "stale",
            "workspace": str(workspace),
            "run_kind": "plan",
            "plan_name": plan_name,
        },
    )

    record = resolve_current_target(
        "stale",
        marker_dir=marker_dir,
        pid_is_live=lambda _pid: False,
    )

    assert record["evidence_state"]["status"] == "unknown"
    assert record["evidence_state"]["unknown_type"] == "stale"
    assert record["evidence_state"]["mutation_eligible"] is False
    assert record["evidence_state"]["green"] is False


def test_resolve_current_target_types_contradictory_plan_identity(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    workspace = tmp_path / "ws"
    workspace.mkdir()
    spec_path = workspace / ".megaplan" / "initiatives" / "demo" / "chain.yaml"
    spec_path.parent.mkdir(parents=True)
    spec_path.write_text("milestones: []\n", encoding="utf-8")
    _write_marker(
        marker_dir / "contradictory.json",
        {
            "session": "contradictory",
            "workspace": str(workspace),
            "remote_spec": str(spec_path),
            "run_kind": "chain",
        },
    )
    _write_chain_state(
        _chain_state_path(workspace, spec_path),
        {"current_plan_name": "chain-plan", "last_state": "executing"},
    )
    _write_plan(
        workspace / ".megaplan" / "plans" / "chain-plan",
        {"name": "different-plan", "current_state": "executing"},
    )

    record = resolve_current_target("contradictory", marker_dir=marker_dir)

    assert record["evidence_state"]["status"] == "unknown"
    assert record["evidence_state"]["unknown_type"] == "contradictory"
    assert record["evidence_state"]["issue_kinds"] == ["contradictory_plan_identity"]
    assert record["evidence_state"]["mutation_eligible"] is False
    assert record["evidence_state"]["green"] is False


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


# ── T11: sidecar / session-marker classification tests ──────────────────


def test_canonical_sidecar_suffix_identifies_repair_progress() -> None:
    assert canonical_sidecar_suffix("demo.repair-progress.json") == ".repair-progress.json"
    assert canonical_sidecar_suffix("demo.reap-progress.json") == ".reap-progress.json"
    assert canonical_sidecar_suffix("demo.chain-health.progress.json") == ".chain-health.progress.json"
    assert canonical_sidecar_suffix("demo.progress.json") == ".progress.json"


def test_canonical_sidecar_suffix_returns_none_for_session_markers() -> None:
    assert canonical_sidecar_suffix("demo-session.json") is None
    assert canonical_sidecar_suffix("parent-session.json") is None
    assert canonical_sidecar_suffix("child-session.json") is None


def test_is_canonical_sidecar_path_true_for_all_known_suffixes() -> None:
    for suffix in (".repair-progress.json", ".reap-progress.json", ".chain-health.progress.json", ".progress.json"):
        assert is_canonical_sidecar_path(f"session{suffix}") is True


def test_is_canonical_sidecar_path_false_for_session_markers() -> None:
    assert is_canonical_sidecar_path("session.json") is False
    assert is_canonical_sidecar_path("parent-session.json") is False


def test_is_canonical_session_marker_path_true_for_markers() -> None:
    assert is_canonical_session_marker_path("my-session.json") is True
    assert is_canonical_session_marker_path("parent-session.json") is True


def test_is_canonical_session_marker_path_false_for_sidecars() -> None:
    for suffix in (".repair-progress.json", ".reap-progress.json", ".chain-health.progress.json", ".progress.json"):
        assert is_canonical_session_marker_path(f"session{suffix}") is False


def test_collect_sibling_sessions_excludes_canonical_sidecar_jsons(tmp_path: Path) -> None:
    """Sibling collection must skip all canonical sidecar files and return only
    real session markers."""
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    workspace = tmp_path / "ws"
    workspace.mkdir()
    # Real sibling marker
    _write_marker(
        marker_dir / "sibling-1.json",
        {"session": "sibling-1", "workspace": str(workspace), "run_kind": "chain"},
    )
    # Canonical sidecars — must be excluded
    for suffix in (
        ".repair-progress.json",
        ".reap-progress.json",
        ".chain-health.progress.json",
        ".progress.json",
    ):
        (marker_dir / f"current-session{suffix}").write_text("{}", encoding="utf-8")
        (marker_dir / f"sibling-1{suffix}").write_text("{}", encoding="utf-8")

    siblings = _collect_sibling_sessions(
        marker_dir,
        session="current-session",
        workspace=workspace,
        session_is_live=None,
    )

    assert len(siblings) == 1
    assert siblings[0]["session"] == "sibling-1"


def test_collect_sibling_sessions_one_row_per_session(tmp_path: Path) -> None:
    """Even when multiple sidecars exist per session, each session contributes
    exactly one canonical row."""
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    workspace = tmp_path / "ws"
    workspace.mkdir()
    _write_marker(
        marker_dir / "alpha.json",
        {"session": "alpha", "workspace": str(workspace), "run_kind": "chain"},
    )
    _write_marker(
        marker_dir / "beta.json",
        {"session": "beta", "workspace": str(workspace), "run_kind": "chain"},
    )
    # Sidecars for both sessions
    for suffix in (".repair-progress.json", ".progress.json"):
        (marker_dir / f"alpha{suffix}").write_text("{}", encoding="utf-8")
        (marker_dir / f"beta{suffix}").write_text("{}", encoding="utf-8")

    siblings = _collect_sibling_sessions(
        marker_dir,
        session="current-session",
        workspace=workspace,
        session_is_live=None,
    )

    assert len(siblings) == 2
    names = {s["session"] for s in siblings}
    assert names == {"alpha", "beta"}


def test_collect_sibling_sessions_marker_only_sessions_preserved(tmp_path: Path) -> None:
    """A session with only its canonical .json marker (no tmux, no process) is
    still included as a sibling row — it must not be filtered out."""
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    workspace = tmp_path / "ws"
    workspace.mkdir()
    _write_marker(
        marker_dir / "marker-only.json",
        {"session": "marker-only", "workspace": str(workspace), "run_kind": "chain"},
    )

    siblings = _collect_sibling_sessions(
        marker_dir,
        session="current-session",
        workspace=workspace,
        session_is_live=None,
    )

    assert len(siblings) == 1
    assert siblings[0]["session"] == "marker-only"
    assert siblings[0]["live_status"] == "unknown"


def test_resolve_current_target_excludes_all_canonical_sidecars_from_siblings(tmp_path: Path) -> None:
    """The full resolver must not include canonical sidecar files in its
    sibling_sessions output."""
    marker_dir = tmp_path / "markers"
    repair_data_dir = marker_dir / "repair-data"
    marker_dir.mkdir()
    repair_data_dir.mkdir()
    workspace = tmp_path / "ws"
    workspace.mkdir()
    spec = workspace / ".megaplan" / "initiatives" / "demo" / "chain.yaml"
    spec.parent.mkdir(parents=True)
    spec.write_text("milestones: []\n", encoding="utf-8")
    _write_marker(
        marker_dir / "current.json",
        {"session": "current", "workspace": str(workspace), "remote_spec": str(spec), "run_kind": "chain"},
    )
    _write_marker(
        marker_dir / "sibling.json",
        {"session": "sibling", "workspace": str(workspace), "remote_spec": str(spec), "run_kind": "chain"},
    )
    # Sidecars that must not appear as siblings
    for suffix in (".repair-progress.json", ".reap-progress.json", ".chain-health.progress.json", ".progress.json"):
        (marker_dir / f"current{suffix}").write_text("{}", encoding="utf-8")
        (marker_dir / f"sibling{suffix}").write_text("{}", encoding="utf-8")

    record = resolve_current_target("current", marker_dir=marker_dir, repair_data_dir=repair_data_dir)

    sibling_sessions = record.get("sibling_sessions", [])
    sibling_names = {s["session"] for s in sibling_sessions}
    assert sibling_names == {"sibling"}
# ---------------------------------------------------------------------------
# New T2 tests: disabled-observe compatibility, deterministic evidence fields,
# unchanged-live vs fresh-activity differentiation
# ---------------------------------------------------------------------------


def test_resolve_current_target_disabled_observe_returns_stub(tmp_path: Path, monkeypatch) -> None:
    """When ARNOLD_RESOLVER_OBSERVE is disabled the stub includes new fields."""
    monkeypatch.setenv("ARNOLD_RESOLVER_OBSERVE", "0")
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()

    record = resolve_current_target("test-session", marker_dir=marker_dir)

    assert record["authoritative_source"] == "resolver_observe_disabled"
    assert record["chain_log"] == {}
    assert record["active_step_heartbeat"] == {}
    assert "mtime" not in record["plan_state"]  # stub is empty dict
    assert "fingerprint" not in record["plan_state"]


def test_resolve_current_target_includes_evidence_mtime_and_fingerprint(tmp_path: Path) -> None:
    """Plan/chain state snapshots carry mtime and fingerprint for comparison."""
    workspace = tmp_path / "ws"
    workspace.mkdir()
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    plan_name = "demo-plan"
    plan_dir = workspace / ".megaplan" / "plans" / plan_name
    plan_dir.mkdir(parents=True)
    (plan_dir / "state.json").write_text(
        json.dumps({"name": plan_name, "current_state": "running"}), encoding="utf-8"
    )
    (marker_dir / "demo.json").write_text(
        json.dumps({"session": "demo", "workspace": str(workspace), "plan_name": plan_name}),
        encoding="utf-8",
    )

    record = resolve_current_target("demo", marker_dir=marker_dir)

    ps = record["plan_state"]
    assert ps["present"] is True
    assert isinstance(ps["mtime"], float) and ps["mtime"] > 0
    assert len(ps["fingerprint"]) == 64  # SHA256 hex digest
    assert ps["fingerprint"] == hashlib.sha256(
        (plan_dir / "state.json").read_bytes()
    ).hexdigest()


def test_resolve_current_target_chain_log_evidence(tmp_path: Path) -> None:
    """Chain log section captures path, mtime, size, and fingerprint."""
    workspace = tmp_path / "ws"
    workspace.mkdir()
    chain_log_dir = workspace / ".megaplan"
    chain_log_dir.mkdir(parents=True)
    chain_log_path = chain_log_dir / "cloud-chain.log"
    chain_log_path.write_text("chain started\nmilestone complete\n", encoding="utf-8")

    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    (marker_dir / "demo.json").write_text(
        json.dumps({"session": "demo", "workspace": str(workspace), "plan_name": "p1"}),
        encoding="utf-8",
    )

    record = resolve_current_target("demo", marker_dir=marker_dir)

    cl = record["chain_log"]
    assert cl["present"] is True
    assert cl["path"] == str(chain_log_path)
    assert cl["mtime"] > 0
    assert cl["size"] > 0
    assert len(cl["fingerprint"]) == 64


def test_resolve_current_target_chain_log_missing(tmp_path: Path) -> None:
    """Chain log section is empty-but-stable when no log file exists."""
    workspace = tmp_path / "ws"
    workspace.mkdir()
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    (marker_dir / "demo.json").write_text(
        json.dumps({"session": "demo", "workspace": str(workspace), "plan_name": "p1"}),
        encoding="utf-8",
    )

    record = resolve_current_target("demo", marker_dir=marker_dir)

    cl = record["chain_log"]
    assert cl["present"] is False
    assert cl["mtime"] == 0.0
    assert cl["size"] == 0
    assert cl["fingerprint"] == ""


def test_resolve_current_target_active_step_heartbeat_present(tmp_path: Path) -> None:
    """Active-step heartbeat is extracted from plan state when present."""
    workspace = tmp_path / "ws"
    workspace.mkdir()
    plan_name = "hb-plan"
    plan_dir = workspace / ".megaplan" / "plans" / plan_name
    plan_dir.mkdir(parents=True)
    (plan_dir / "state.json").write_text(
        json.dumps({
            "name": plan_name,
            "current_state": "running",
            "active_step": {
                "phase": "execute",
                "attempt": 2,
                "worker_pid": "12345",
                "started_at": "2025-07-01T12:00:00Z",
            },
        }),
        encoding="utf-8",
    )
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    (marker_dir / "demo.json").write_text(
        json.dumps({"session": "demo", "workspace": str(workspace), "plan_name": plan_name}),
        encoding="utf-8",
    )

    record = resolve_current_target("demo", marker_dir=marker_dir, pid_is_live=lambda pid: pid == 12345)

    hb = record["active_step_heartbeat"]
    assert hb["active"] is True
    assert hb["phase"] == "execute"
    assert hb["attempt"] == 2
    assert hb["worker_pid"] == "12345"
    assert hb["started_at"] == "2025-07-01T12:00:00Z"
    assert hb["pid_live"] is True


def test_resolve_current_target_active_step_heartbeat_absent(tmp_path: Path) -> None:
    """Active-step heartbeat is inactive when plan state has no active_step."""
    workspace = tmp_path / "ws"
    workspace.mkdir()
    plan_name = "idle-plan"
    plan_dir = workspace / ".megaplan" / "plans" / plan_name
    plan_dir.mkdir(parents=True)
    (plan_dir / "state.json").write_text(
        json.dumps({"name": plan_name, "current_state": "idle"}),
        encoding="utf-8",
    )
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    (marker_dir / "demo.json").write_text(
        json.dumps({"session": "demo", "workspace": str(workspace), "plan_name": plan_name}),
        encoding="utf-8",
    )

    record = resolve_current_target("demo", marker_dir=marker_dir)

    hb = record["active_step_heartbeat"]
    assert hb["active"] is False
    assert hb["phase"] == ""
    assert hb["attempt"] == 0


def test_snapshots_distinguish_unchanged_live_from_fresh_activity(tmp_path: Path) -> None:
    """Two snapshots taken at different times expose evidence deltas.

    - Unchanged tmux without file changes: same fingerprints, same mtimes.
    - Fresh activity: event line count or chain-log mtime advances.
    """
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / ".megaplan").mkdir()
    chain_log = workspace / ".megaplan" / "cloud-chain.log"
    chain_log.write_text("initial line\n", encoding="utf-8")

    plan_name = "delta-plan"
    plan_dir = workspace / ".megaplan" / "plans" / plan_name
    plan_dir.mkdir(parents=True)
    (plan_dir / "state.json").write_text(
        json.dumps({"name": plan_name, "current_state": "running"}),
        encoding="utf-8",
    )
    events_path = plan_dir / "events.ndjson"
    events_path.write_text(
        '{"kind":"gate_entered"}\n{"kind":"state_written"}\n',
        encoding="utf-8",
    )

    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    (marker_dir / "demo.json").write_text(
        json.dumps({
            "session": "demo",
            "workspace": str(workspace),
            "plan_name": plan_name,
            "pid": 9999,
        }),
        encoding="utf-8",
    )

    # --- First snapshot: tmux is alive, no activity ---
    snap1 = resolve_current_target(
        "demo",
        marker_dir=marker_dir,
        session_is_live=lambda s: True if s == "demo" else None,
        pid_is_live=lambda p: True if p == 9999 else None,
    )
    assert snap1["tmux_process"]["live_status"] == "alive"
    ec1 = snap1["event_cursors"]
    cl1 = snap1["chain_log"]

    # --- Simulate fresh activity: more events written ---
    events_path.write_text(
        '{"kind":"gate_entered"}\n{"kind":"state_written"}\n{"kind":"gate_passed"}\n',
        encoding="utf-8",
    )

    # --- Second snapshot ---
    snap2 = resolve_current_target(
        "demo",
        marker_dir=marker_dir,
        session_is_live=lambda s: True if s == "demo" else None,
        pid_is_live=lambda p: True if p == 9999 else None,
    )
    assert snap2["tmux_process"]["live_status"] == "alive"
    ec2 = snap2["event_cursors"]

    # Unchanged-live case: same fingerprint, no delta
    assert snap1["plan_state"]["fingerprint"] == snap2["plan_state"]["fingerprint"]

    # Fresh activity case: event line count increased
    assert ec2["line_count"] > ec1["line_count"]

    # Determinism: second snapshot with same files produces same fingerprint
    snap2b = resolve_current_target(
        "demo",
        marker_dir=marker_dir,
        session_is_live=lambda s: True if s == "demo" else None,
        pid_is_live=lambda p: True if p == 9999 else None,
    )
    assert snap2 == snap2b


def test_repair_progress_sidecar_includes_mtime(tmp_path: Path) -> None:
    """Repair-progress sidecar items carry mtime for comparison."""
    workspace = tmp_path / "ws"
    workspace.mkdir()
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    (marker_dir / "demo.json").write_text(
        json.dumps({"session": "demo", "workspace": str(workspace), "plan_name": "p1"}),
        encoding="utf-8",
    )
    sidecar = marker_dir / "demo.repair-progress.json"
    sidecar.write_text(json.dumps({"status": "waiting"}), encoding="utf-8")

    record = resolve_current_target("demo", marker_dir=marker_dir)

    assert record["repair_progress"]["present"] is True
    items = record["repair_progress"]["items"]
    assert len(items) == 1
    assert items[0]["status"] == "waiting"
    assert isinstance(items[0]["mtime"], float) and items[0]["mtime"] > 0

def test_active_step_dead_pid_is_stale_not_live(tmp_path: Path) -> None:
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
        {"current_plan_name": "m1-plan", "last_state": "finalized"},
    )
    _write_plan(
        workspace / ".megaplan" / "plans" / "m1-plan",
        {
            "name": "m1-plan",
            "current_state": "finalized",
            "active_step": {"phase": "execute", "worker_pid": 4242},
        },
    )

    record = resolve_current_target(
        "demo-session",
        marker_dir=marker_dir,
        repair_data_dir=repair_data_dir,
        pid_is_live=lambda pid: False,
    )

    assert record["active_step_heartbeat"]["active"] is False
    assert record["active_step_heartbeat"]["pid_live"] is False
    assert record["plan_state"]["current_phase"] == "execute"
    assert record["current_refs"]["plan_current_phase"] == "execute"
    assert {item["kind"] for item in record["stale_evidence"]} >= {"stale_active_step_dead_pid"}
    assert "active_step worker PID is not live" in record["rationale"]


def test_resolve_current_target_phase_precedence_is_deterministic(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    workspace = tmp_path / "ws"
    plan_name = "phase-plan"
    _write_plan(
        workspace / ".megaplan" / "plans" / plan_name,
        {
            "name": plan_name,
            "current_state": "failed",
            "current_phase": "gate",
            "active_step": {"phase": "execute", "worker_pid": 4242},
            "resume_cursor": {"phase": "review"},
        },
    )
    _write_marker(
        marker_dir / "demo-session.json",
        {
            "session": "demo-session",
            "workspace": str(workspace),
            "plan_name": plan_name,
            "run_kind": "plan",
        },
    )

    record = resolve_current_target(
        "demo-session",
        marker_dir=marker_dir,
        pid_is_live=lambda pid: False,
    )

    assert record["plan_state"]["current_phase"] == "gate"
    assert record["current_refs"]["plan_current_phase"] == "gate"


def test_resolve_current_target_reports_failed_resume_execute_authority_divergence(
    tmp_path: Path,
) -> None:
    marker_dir = tmp_path / "markers"
    repair_data_dir = marker_dir / "repair-data"
    marker_dir.mkdir()
    repair_data_dir.mkdir()
    workspace = tmp_path / "ws"
    workspace.mkdir()
    plan_name = "failed-review-plan"
    plan_dir = workspace / ".megaplan" / "plans" / plan_name
    _write_plan(
        plan_dir,
        {
            "name": plan_name,
            "current_state": "failed",
            "resume_cursor": {"phase": "review", "retry_strategy": "rerun_phase"},
            "latest_failure": {
                "kind": "phase_failed",
                "phase": "review",
                "message": "Cannot run 'review' while current state is 'failed'",
            },
        },
    )
    (plan_dir / "finalize.json").write_text(
        json.dumps({"tasks": [{"id": "T1", "status": "done"}]}),
        encoding="utf-8",
    )
    _write_marker(
        marker_dir / "demo.json",
        {
            "session": "demo",
            "workspace": str(workspace),
            "run_kind": "plan",
            "plan_name": plan_name,
        },
    )

    record = resolve_current_target(
        "demo",
        marker_dir=marker_dir,
        repair_data_dir=repair_data_dir,
    )

    failure = record["resume_authority_failure"]
    assert failure["code"] == "resume_execute_authority_blocked"
    assert failure["reason"] == "execute_authority_diverged"
    assert failure["phase"] == "review"
    assert failure["plan_name"] == plan_name
    assert failure["missing_task_ids"] == ["T1"]

def _chain_state_path(workspace: Path, spec_path: Path) -> Path:
    return chain_spec._state_path_for(spec_path)
