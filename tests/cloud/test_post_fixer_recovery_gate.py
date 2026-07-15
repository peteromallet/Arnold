from __future__ import annotations

import json
from pathlib import Path

from arnold_pipelines.megaplan.cloud import repair_contract
from arnold_pipelines.megaplan.cloud.progress_auditor_escalation import (
    _l1_failure_fingerprint,
    bounded_repair_context,
)
from arnold_pipelines.megaplan.cloud.repair_goal import (
    GOAL_ACTIVE,
    ensure_repair_goal,
    evaluate_repair_goal,
    recovery_acceptance_verification,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")


def _recovery_fixture(tmp_path: Path) -> tuple[Path, dict, Path, Path]:
    workspace = tmp_path / "workspace"
    marker_dir = tmp_path / "markers"
    plan_name = "plan-t24"
    spec = workspace / ".megaplan" / "initiatives" / "custody" / "chain.yaml"
    spec.parent.mkdir(parents=True)
    spec.write_text("milestones:\n  - label: m5a\n  - label: m6\n", encoding="utf-8")
    marker_dir.mkdir(parents=True)
    _write_json(
        marker_dir / "custody-session.json",
        {
            "session": "custody-session",
            "workspace": str(workspace),
            "remote_spec": str(spec),
            "should_run": True,
        },
    )
    plan_dir = workspace / ".megaplan" / "plans" / plan_name
    state_path = plan_dir / "state.json"
    _write_json(
        state_path,
        {
            "name": plan_name,
            "current_state": "blocked",
            "latest_failure": {
                "kind": "quality_gate_blocked",
                "phase": "review",
                "message": "T24 remains blocked",
                "task_id": "T24",
            },
            "history": [{"step": "review", "result": "blocked"}],
        },
    )
    events_path = plan_dir / "events.ndjson"
    events_path.write_text(
        json.dumps(
            {
                "kind": "state_transition",
                "seq": 20,
                "ts_utc": "2026-07-15T15:00:00+00:00",
                "payload": {"from": "executed", "to": "blocked"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    _write_json(
        workspace / ".megaplan" / "plans" / ".chains" / "chain.json",
        {
            "current_plan_name": plan_name,
            "current_milestone_index": 1,
            "completed": [{"plan": "m5"}],
            "last_state": "blocked",
            "metadata": {"chain_spec_path": str(spec)},
        },
    )
    run_root = workspace / ".megaplan" / "plans" / "resident-subagents" / "fixer-run"
    _write_json(
        run_root / "manifest.json",
        {"run_id": "fixer-run", "status": "complete"},
    )
    (run_root / "run.log").write_text("failed fixer transcript\n", encoding="utf-8")
    (run_root / "result.md").write_text("claimed success\n", encoding="utf-8")
    goal_path, goal = ensure_repair_goal(
        marker_dir=marker_dir,
        session="custody-session",
        workspace=workspace,
        remote_spec=str(spec),
        plan_name=plan_name,
        blocker_id="blocker:t24",
        request_id="request-t24",
        owner_run_id="fixer-run",
        owner_manifest_path=str(run_root / "manifest.json"),
    )
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["current_state"] = "reviewed"
    state["latest_failure"] = None
    state["history"].append({"step": "review", "result": "success"})
    _write_json(state_path, state)
    with events_path.open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    "kind": "state_transition",
                    "seq": 21,
                    "ts_utc": "2026-07-15T15:01:00+00:00",
                    "payload": {"from": "blocked", "to": "reviewed"},
                }
            )
            + "\n"
        )
    return goal_path, goal, state_path, events_path


def test_false_success_without_live_canonical_runner_escalates_with_transcript_refs(
    tmp_path: Path,
) -> None:
    goal_path, _, _, _ = _recovery_fixture(tmp_path)

    result = evaluate_repair_goal(goal_path, action="fixer-terminalization")

    assert result["status"] == GOAL_ACTIVE
    assert result["semantic_completion"] is False
    assert result["evaluation"]["control_action"] == "meta_repair"
    assert result["evaluation"]["recovery_gate_reasons"] == [
        "canonical_runner_not_live"
    ]
    receipt = result["recovery_acceptance"]
    assert receipt["accepted"] is False
    assert receipt["escalation"]["target"] == "meta_repair_root_cause"
    refs = receipt["failed_fixer_evidence"]
    assert {item["kind"] for item in refs} == {"manifest", "transcript", "result"}
    assert all(item["exists"] is True and len(item["sha256"]) == 64 for item in refs)


def test_bounded_followup_without_continued_progress_fails_closed(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("MEGAPLAN_REPAIR_RECOVERY_FOLLOWUP_SECONDS", "0")
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.cloud.repair_goal._canonical_runner_live",
        lambda _observation: True,
    )
    goal_path, _, _, _ = _recovery_fixture(tmp_path)

    candidate = evaluate_repair_goal(goal_path, action="fixer-terminalization")
    followup = evaluate_repair_goal(goal_path, action="bounded-followup")

    assert candidate["evaluation"]["control_action"] == "observe_recovery"
    assert followup["status"] == GOAL_ACTIVE
    assert followup["evaluation"]["control_action"] == "meta_repair"
    assert "continued_progress_not_observed" in followup["evaluation"][
        "recovery_gate_reasons"
    ]


def test_recovery_classifier_requires_full_two_observation_contract() -> None:
    weak = repair_contract.classify_recovery_verification(
        original_blocker={"blocker_id": "blocker:t24"},
        observation={
            "blocker_id": "blocker:t24",
            "blocker_cleared": True,
            "directly_observed": True,
            "independent": True,
            "observed_at": "2026-07-15T15:02:00+00:00",
        },
        repair_completed_at="2026-07-15T15:00:00+00:00",
    )
    strong = repair_contract.classify_recovery_verification(
        original_blocker={"blocker_id": "blocker:t24"},
        observation={
            "blocker_id": "blocker:t24",
            "blocker_cleared": True,
            "directly_observed": True,
            "independent": True,
            "canonical_runner_live": True,
            "fresh_progress_beyond_checkpoint": True,
            "continued_progress": True,
            "first_progress_observed_at": "2026-07-15T15:01:00+00:00",
            "observed_at": "2026-07-15T15:02:00+00:00",
        },
        repair_completed_at="2026-07-15T15:00:00+00:00",
    )

    assert weak["authorizes_verified_recovered"] is False
    assert "canonical runner" in weak["reason"]
    assert strong["authorizes_verified_recovered"] is True


def test_accepted_goal_receipt_projects_into_shared_meta_verifier() -> None:
    goal = {
        "created_at": "2026-07-15T15:00:00+00:00",
        "target": {"blocker_id": "blocker:t24"},
        "recovery_acceptance": {
            "schema_version": "arnold-post-fixer-recovery-acceptance-v1",
            "accepted": True,
            "recorded_at": "2026-07-15T15:02:00+00:00",
            "checkpoint_digest": "a" * 64,
            "pre_recovery_checkpoint": {
                "captured_at": "2026-07-15T15:00:00+00:00"
            },
            "post_recovery_checkpoint": {
                "captured_at": "2026-07-15T15:01:00+00:00",
                "progress_token": "before-followup",
            },
            "followup_checkpoint": {
                "captured_at": "2026-07-15T15:02:00+00:00",
                "progress_token": "after-followup",
                "latest_failure_cleared": True,
                "runner_transition": {
                    "runner_pid_live": True,
                    "fresh": True,
                },
            },
            "failed_fixer_evidence": [
                {"kind": "transcript", "path": "/evidence/run.log"}
            ],
        },
    }

    verification = recovery_acceptance_verification(goal)
    classified = repair_contract.classify_recovery_verification(
        original_blocker=verification["original_blocker"],
        observation=verification["observation"],
        repair_completed_at=verification["repair_completed_at"],
    )

    assert verification["observation"]["canonical_runner_live"] is True
    assert verification["observation"]["continued_progress"] is True
    assert classified["authorizes_verified_recovered"] is True


def test_l3_classifies_post_fixer_gate_failure_and_propagates_artifacts() -> None:
    evidence = [
        {"kind": "transcript", "path": "/evidence/fixer/run.log", "exists": True}
    ]
    finding = {
        "repair_data_summary": {"outcome": "complete"},
        "meta_repair_summary": {
            "repair_goal": {
                "recovery_gate_failed": True,
                "recovery_gate": {"accepted": False},
                "failed_fixer_evidence": evidence,
            }
        },
        "chain_state_summary": {"current": {"last_state": "blocked"}},
    }

    fingerprint = _l1_failure_fingerprint(finding)
    context = bounded_repair_context(finding)

    assert fingerprint["failed"] is True
    assert fingerprint["axis"] == "FIXED"
    assert fingerprint["post_fixer_recovery_gate_failed"] is True
    assert context["failed_fixer_evidence"] == evidence


def test_watchdog_and_l3_have_deterministic_gate_failure_routes() -> None:
    watchdog = (
        REPO_ROOT
        / "arnold_pipelines"
        / "megaplan"
        / "cloud"
        / "wrappers"
        / "arnold-watchdog"
    ).read_text(encoding="utf-8")
    auditor = (
        REPO_ROOT
        / "arnold_pipelines"
        / "megaplan"
        / "cloud"
        / "wrappers"
        / "arnold-progress-auditor"
    ).read_text(encoding="utf-8")
    repair_loop = (
        REPO_ROOT
        / "arnold_pipelines"
        / "megaplan"
        / "cloud"
        / "wrappers"
        / "arnold-repair-loop"
    ).read_text(encoding="utf-8")

    assert '"post_fixer_recovery_gate_failed"' in watchdog
    assert 'trigger = "post_fixer_recovery_gate_failed"' in auditor
    assert "failed_fixer_evidence" in auditor
    assert "post-fixer recovery circuit breaker stopped this repair owner" in repair_loop
    assert "L2 transcript-aware meta-repair required" in repair_loop
