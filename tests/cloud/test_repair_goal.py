from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from arnold_pipelines.megaplan.cloud import repair_contract
from arnold_pipelines.megaplan.cloud.repair_goal import (
    GOAL_ACTIVE,
    GOAL_APPROVAL_REQUIRED,
    GOAL_PROGRESSED,
    _quality_resolution_commit_custody,
    ensure_repair_goal,
    evaluate_checkpoint,
    evaluate_repair_goal,
    next_repair_goal_retry_sequence,
    record_terminal_failure,
    reconcile_l2_replan,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")


def test_retry_sequence_includes_failed_managed_identity_reservations(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    run_root = workspace / ".megaplan" / "plans" / "resident-subagents"
    goal = {
        "goal_id": "repair-goal-stuck",
        "target": {"workspace": str(workspace)},
        "owners": [{"run_id": f"owner-{index}"} for index in range(7)],
    }
    _write_json(
        run_root / "managed-automatic-repair-failed" / "manifest.json",
        {
            "status": "failed",
            "launch_idempotency_key": "request:goal:repair-goal-stuck:retry:8",
        },
    )

    assert next_repair_goal_retry_sequence(goal) == 9


def _target(tmp_path: Path) -> tuple[Path, Path, str, str]:
    workspace = tmp_path / "target"
    marker_dir = tmp_path / "markers"
    plan = "frozen-plan"
    spec = workspace / ".megaplan" / "initiatives" / "demo" / "chain.yaml"
    spec.parent.mkdir(parents=True)
    spec.write_text("milestones: []\n", encoding="utf-8")
    plan_dir = workspace / ".megaplan" / "plans" / plan
    _write_json(
        plan_dir / "state.json",
        {
            "name": plan,
            "current_state": "blocked",
            "iteration": 3,
            "latest_failure": {
                "failure_kind": "review_quality_blocked",
                "phase": "review",
                "message": "exact frozen review error",
            },
            "history": [{"step": "review", "result": "blocked"}],
        },
    )
    (plan_dir / "events.ndjson").write_text(
        json.dumps(
            {
                "kind": "state_transition",
                "seq": 10,
                "ts_utc": "2026-07-15T00:00:00+00:00",
                "payload": {"from": "executed", "to": "blocked"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    _write_json(
        workspace / ".megaplan" / "plans" / ".chains" / "chain-demo.json",
        {
            "current_plan_name": plan,
            "current_milestone_index": 4,
            "completed": [{"plan": f"plan-{index}"} for index in range(4)],
            "last_state": "blocked",
            "metadata": {"chain_spec_path": str(spec)},
        },
    )
    return workspace, marker_dir, plan, str(spec)


def _goal(tmp_path: Path, *, owner: str = "repair-owner-1") -> tuple[Path, dict]:
    workspace, marker_dir, plan, spec = _target(tmp_path)
    return ensure_repair_goal(
        marker_dir=marker_dir,
        session="demo-session",
        workspace=workspace,
        remote_spec=spec,
        plan_name=plan,
        blocker_id="blocker:v1:frozen",
        request_id="request-1",
        owner_run_id=owner,
        owner_manifest_path=f"/manifests/{owner}.json",
    )


def test_fixer_exit_without_target_change_keeps_goal_active(tmp_path: Path) -> None:
    path, initial = _goal(tmp_path)

    result = evaluate_repair_goal(path, action="fixer_exit_returncode_0")

    assert result["status"] == GOAL_ACTIVE
    assert result["semantic_completion"] is False
    assert repair_contract.is_terminal_outcome("partial_liveness") is False
    assert result["checkpoint_digest"] == initial["checkpoint_digest"]
    assert "blocker-clearance" in result["evaluation"]["reason"]


def test_heartbeat_and_log_churn_do_not_count_as_acceptance_progress(tmp_path: Path) -> None:
    path, _ = _goal(tmp_path)
    goal = json.loads(path.read_text(encoding="utf-8"))
    events = Path(goal["frozen_checkpoint"]["events_path"])
    with events.open("a", encoding="utf-8") as handle:
        for seq, kind in ((11, "llm_token_heartbeat"), (12, "state_written"), (13, "cost_recorded")):
            handle.write(
                json.dumps(
                    {
                        "kind": kind,
                        "seq": seq,
                        "ts_utc": "2026-07-15T00:01:00+00:00",
                        "payload": {"activity": True},
                    }
                )
                + "\n"
            )

    result = evaluate_repair_goal(path, action="heartbeat_observation")

    assert result["status"] == GOAL_ACTIVE
    assert "heartbeat" in result["evaluation"]["ignored_activity"]
    assert result["observation"]["acceptance"]["seq"] == 10


def test_retry_inherits_same_goal_and_frozen_checkpoint(tmp_path: Path) -> None:
    path, first = _goal(tmp_path, owner="repair-owner-1")
    workspace = Path(first["target"]["workspace"])
    second_path, second = ensure_repair_goal(
        marker_dir=path.parents[2],
        session="demo-session",
        workspace=workspace,
        remote_spec=first["target"]["remote_spec"],
        plan_name=first["target"]["plan_name"],
        blocker_id=first["target"]["blocker_id"],
        request_id="request-2",
        owner_run_id="repair-owner-2",
        owner_manifest_path="/manifests/repair-owner-2.json",
    )

    assert second_path == path
    assert second["goal_id"] == first["goal_id"]
    assert second["checkpoint_digest"] == first["checkpoint_digest"]
    assert [owner["run_id"] for owner in second["owners"]] == [
        "repair-owner-1",
        "repair-owner-2",
    ]
    assert second["request_ids"] == ["request-1", "request-2"]


def test_l2_replan_epoch_is_idempotent_and_preserves_checkpoint(tmp_path: Path) -> None:
    path, goal = _goal(tmp_path)
    target = goal["target"]
    kwargs = {
        "session": "demo-session", "workspace": target["workspace"],
        "remote_spec": target["remote_spec"], "blocker_id": target["blocker_id"],
    }
    first = reconcile_l2_replan(path, context_digest="digest-1", receipt_digest="receipt-1", **kwargs)
    repeated = reconcile_l2_replan(path, context_digest="digest-1", receipt_digest="receipt-1", **kwargs)
    second = reconcile_l2_replan(path, context_digest="digest-2", **kwargs)

    persisted = json.loads(path.read_text(encoding="utf-8"))
    assert first["status"] == "newly_reconciled"
    assert repeated == {**first, "status": "already_reconciled"}
    assert second["replan_epoch"] == 2
    assert persisted["checkpoint_digest"] == goal["checkpoint_digest"]
    assert [item["context_digest"] for item in persisted["l2_replans"]] == ["digest-1", "digest-2"]


def test_l2_replan_epoch_scopes_deterministic_owner_breaker(tmp_path: Path) -> None:
    path, goal = _goal(tmp_path)
    target = goal["target"]
    first = evaluate_repair_goal(path, action="owner-iteration-1-post-dev-fix")
    tripped = evaluate_repair_goal(path, action="owner-iteration-2-post-dev-fix")
    assert first["evaluation"].get("control_action") != "replan"
    assert tripped["evaluation"]["control_action"] == "replan"

    reconcile_l2_replan(
        path,
        session="demo-session",
        workspace=target["workspace"],
        remote_spec=target["remote_spec"],
        blocker_id=target["blocker_id"],
        context_digest="fresh-l2-context",
    )
    fresh = evaluate_repair_goal(path, action="owner-iteration-1-post-dev-fix")

    assert fresh["evaluation"].get("control_action") != "replan"
    assert fresh["recovery_contract"] == goal["recovery_contract"]


def test_later_authoritative_transition_beyond_checkpoint_completes_goal(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("MEGAPLAN_REPAIR_RECOVERY_FOLLOWUP_SECONDS", "0")
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.cloud.repair_goal._canonical_runner_live",
        lambda _observation: True,
    )
    path, goal = _goal(tmp_path)
    state_path = Path(goal["frozen_checkpoint"]["plan_state_path"])
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["current_state"] = "reviewed"
    state["latest_failure"] = None
    _write_json(state_path, state)
    events = Path(goal["frozen_checkpoint"]["events_path"])
    with events.open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    "kind": "state_transition",
                    "seq": 14,
                    "ts_utc": "2026-07-15T00:02:00+00:00",
                    "payload": {"from": "blocked", "to": "reviewed"},
                }
            )
            + "\n"
        )

    candidate = evaluate_repair_goal(path, action="post_redrive_verify")

    assert candidate["status"] == GOAL_ACTIVE
    assert candidate["evaluation"]["control_action"] == "observe_recovery"
    with events.open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    "kind": "state_transition",
                    "seq": 15,
                    "ts_utc": "2026-07-15T00:03:00+00:00",
                    "payload": {"from": "reviewed", "to": "reviewed"},
                }
            )
            + "\n"
        )

    result = evaluate_repair_goal(path, action="post_redrive_bounded_followup")

    assert result["status"] == GOAL_PROGRESSED
    assert result["semantic_completion"] is True
    assert result["evaluation"]["authoritative_progress"] is True
    assert result["evaluation"]["recovery_gate_accepted"] is True
    assert result["recovery_acceptance"]["accepted"] is True


def test_terminal_cursor_transition_closes_stale_goal_before_successor_launch(
    tmp_path: Path,
) -> None:
    path, goal = _goal(tmp_path)
    state_path = Path(goal["frozen_checkpoint"]["plan_state_path"])
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["current_state"] = "done"
    state["latest_failure"] = None
    _write_json(state_path, state)
    chain_path = Path(goal["frozen_checkpoint"]["chain_state_path"])
    chain = json.loads(chain_path.read_text(encoding="utf-8"))
    chain["completed"].append({"plan": "frozen-plan", "status": "done"})
    chain["current_milestone_index"] = 5
    chain["current_plan_name"] = None
    chain["last_state"] = "pr_closed"
    _write_json(chain_path, chain)

    result = evaluate_repair_goal(path, action="watchdog_authority_check")

    assert result["status"] == GOAL_PROGRESSED
    assert result["semantic_completion"] is True
    assert result["evaluation"]["superseded_blocker"] is True
    assert result["evaluation"]["recovery_gate_not_applicable"] == "superseded_target"
    assert result["evaluation"]["control_action"] == "complete"


def test_watchdog_relaunches_successor_after_stale_goal_closes() -> None:
    wrapper = (
        Path(__file__).parents[2]
        / "arnold_pipelines"
        / "megaplan"
        / "cloud"
        / "wrappers"
        / "arnold-watchdog"
    ).read_text(encoding="utf-8")

    assert "local repair_goal_progressed=0" in wrapper
    assert "repair_goal_progressed=1" in wrapper
    assert 'if [[ "$repair_goal_progressed" != "1" ]]; then' in wrapper
    assert "bypassing historical repair-failure routing for successor relaunch" in wrapper


def test_replacement_session_evidence_cannot_complete_original_goal(tmp_path: Path) -> None:
    path, goal = _goal(tmp_path)
    target = goal["target"]
    marker_path = Path(target["marker_dir"]) / "demo-session.json"
    _write_json(
        marker_path,
        {
            "session": "replacement-session",
            "workspace": target["workspace"],
            "remote_spec": target["remote_spec"],
        },
    )
    chain_path = Path(goal["frozen_checkpoint"]["chain_state_path"])
    chain = json.loads(chain_path.read_text(encoding="utf-8"))
    chain["current_milestone_index"] = 5
    chain["completed"].append({"plan": "replacement-plan"})
    _write_json(chain_path, chain)

    result = evaluate_repair_goal(path, action="post-redrive-replacement-session")

    assert result["status"] == GOAL_ACTIVE
    assert result["semantic_completion"] is False
    assert result["evaluation"]["authoritative_progress"] is False
    assert result["evaluation"]["replacement_session_evidence_rejected"] is True
    assert result["evaluation"]["observed_session_identity"]["marker_session"] == (
        "replacement-session"
    )


def test_live_execute_worker_is_preserved_until_review_stage(tmp_path: Path) -> None:
    workspace, marker_dir, plan, spec = _target(tmp_path)
    state_path = workspace / ".megaplan" / "plans" / plan / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["latest_failure"] = {
        "failure_kind": "execution_blocked",
        "phase": "execute",
        "message": "exact execute blocker",
    }
    state["history"] = [{"step": "execute", "result": "blocked"}]
    _write_json(state_path, state)
    path, goal = ensure_repair_goal(
        marker_dir=marker_dir,
        session="demo-session",
        workspace=workspace,
        remote_spec=spec,
        plan_name=plan,
        blocker_id="blocker:v1:execute",
        request_id="request-execute",
        owner_run_id="repair-owner-1",
        owner_manifest_path="/manifests/repair-owner-1.json",
    )
    state_path = Path(goal["frozen_checkpoint"]["plan_state_path"])
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["current_state"] = "finalized"
    state["latest_failure"] = None
    state["active_step"] = {
        "phase": "execute",
        "worker_pid": os.getpid(),
        "run_id": "execute-run-1",
        "last_activity_at": goal["frozen_checkpoint"]["captured_at"],
        "last_activity_kind": "llm_stream",
    }
    _write_json(state_path, state)

    result = evaluate_repair_goal(path, action="pre-mechanical-relaunch")

    assert result["status"] == GOAL_ACTIVE
    assert result["evaluation"]["control_action"] == "preserve_live"
    assert result["evaluation"]["blocker_cleared"] is True
    assert result["evaluation"]["stage_advanced"] is False
    assert result["evaluation"]["correct_worker_alive"] is True

    repeated_poll = evaluate_repair_goal(
        path, action="owner-iteration-1-post-dev-fix"
    )
    assert repeated_poll["evaluation"]["control_action"] == "preserve_live"
    assert repeated_poll["evaluation"].get("circuit_breaker_required") is not True


def test_same_owner_failure_twice_opens_replan_circuit(tmp_path: Path) -> None:
    path, _ = _goal(tmp_path)

    first = evaluate_repair_goal(path, action="owner-iteration-1-post-dev-fix")
    second = evaluate_repair_goal(path, action="owner-iteration-2-post-dev-fix")

    assert first["evaluation"]["control_action"] == "investigate"
    assert second["evaluation"]["control_action"] == "replan"
    assert second["evaluation"]["circuit_breaker_required"] is True
    assert second["evaluation"]["deterministic_repeat_count"] == 2


def test_bounded_terminal_failure_records_exact_unresolved_checkpoint(tmp_path: Path) -> None:
    path, goal = _goal(tmp_path)

    result = record_terminal_failure(
        path,
        outcome="deterministic_failure",
        phase="deterministic-owner-circuit-breaker",
        reason="same owner repeated without progress",
        owner_run_id="repair-owner-1",
        owner_manifest_path="/manifests/repair-owner-1.json",
    )

    assert result["status"] == GOAL_ACTIVE
    assert result["semantic_completion"] is False
    failure = result["terminal_failure"]
    assert failure["owner_terminal"] is True
    assert failure["escalation_required"] is True
    assert failure["checkpoint_digest"] == goal["checkpoint_digest"]
    assert failure["replan_epoch"] == 0
    assert failure["unresolved_checkpoint"]["digest"] == goal["checkpoint_digest"]
    assert failure["unresolved_checkpoint"]["latest_failure"] == (
        goal["frozen_checkpoint"]["latest_failure"]
    )
    persisted = json.loads(path.read_text(encoding="utf-8"))
    assert persisted["last_terminal_failure"] == failure


def test_current_epoch_investigator_replan_routes_to_l2_once(tmp_path: Path) -> None:
    path, goal = _goal(tmp_path)
    target = goal["target"]
    failure = record_terminal_failure(
        path,
        outcome="replan_required",
        phase="investigator-replan-required",
        reason="validated investigator requires L2 replan before target mutation",
        owner_run_id="repair-owner-1",
    )

    routed = evaluate_repair_goal(path, action="watchdog_authority_check")

    assert failure["terminal_failure"]["replan_epoch"] == 0
    assert routed["status"] == GOAL_ACTIVE
    assert routed["evaluation"]["control_action"] == "meta_repair"
    assert routed["evaluation"]["failed_fixer_evidence"]["phase"] == (
        "investigator-replan-required"
    )

    reconcile_l2_replan(
        path,
        session="demo-session",
        workspace=target["workspace"],
        remote_spec=target["remote_spec"],
        blocker_id=target["blocker_id"],
        context_digest="accepted-l2-context",
    )
    after_reconcile = evaluate_repair_goal(path, action="watchdog_authority_check")

    assert after_reconcile["evaluation"]["control_action"] != "meta_repair"


def test_current_epoch_arnold_source_replan_routes_to_l2_once(
    tmp_path: Path,
) -> None:
    path, _goal_payload = _goal(tmp_path)
    failure = record_terminal_failure(
        path,
        outcome="deterministic_failure_source_fix_needed",
        phase="investigator-replan-arnold-source",
        reason="validated investigator replan targets Arnold repair-system source",
        owner_run_id="repair-owner-1",
    )

    routed = evaluate_repair_goal(path, action="watchdog_authority_check")

    assert failure["terminal_failure"]["replan_epoch"] == 0
    assert routed["status"] == GOAL_ACTIVE
    assert routed["evaluation"]["control_action"] == "meta_repair"
    assert routed["evaluation"]["failed_fixer_evidence"]["phase"] == (
        "investigator-replan-arnold-source"
    )


def test_productive_target_commit_resets_breaker_without_completing_goal(tmp_path: Path) -> None:
    path, goal = _goal(tmp_path)
    workspace = Path(goal["target"]["workspace"])
    subprocess.run(["git", "init", "-q", str(workspace)], check=True)
    subprocess.run(["git", "-C", str(workspace), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(workspace), "-c", "user.name=test", "-c", "user.email=test@example.com", "commit", "-qm", "initial"],
        check=True,
    )

    first = evaluate_repair_goal(path, action="owner-iteration-1-post-dev-fix")
    (workspace / "productive-fix.txt").write_text("fixed\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(workspace), "add", "productive-fix.txt"], check=True)
    subprocess.run(
        ["git", "-C", str(workspace), "-c", "user.name=test", "-c", "user.email=test@example.com", "commit", "-qm", "productive fix"],
        check=True,
    )
    changed = evaluate_repair_goal(path, action="owner-iteration-2-post-dev-fix")
    repeated = evaluate_repair_goal(path, action="owner-iteration-3-post-dev-fix")

    assert first["status"] == GOAL_ACTIVE
    assert changed["status"] == GOAL_ACTIVE
    assert changed["evaluation"]["control_action"] == "investigate"
    assert changed["semantic_completion"] is False
    assert repeated["evaluation"]["control_action"] == "replan"


def test_explicit_authorization_gate_terminates_with_exact_gate_evidence(tmp_path: Path) -> None:
    path, goal = _goal(tmp_path)
    state_path = Path(goal["frozen_checkpoint"]["plan_state_path"])
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["current_state"] = "awaiting_authorization"
    _write_json(state_path, state)

    result = evaluate_repair_goal(path, action="approval_gate_check")

    assert result["status"] == GOAL_APPROVAL_REQUIRED
    assert result["terminal"] is True
    assert result["semantic_completion"] is False
    assert result["evaluation"]["authoritative_progress"] is False
    gate = result["evaluation"]["approval_gate"]
    assert gate["gate_state"] == "awaiting_authorization"
    assert gate["plan_state_path"] == str(state_path)


def test_watchdog_retry_explicitly_inherits_goal_checkpoint_and_unique_identity() -> None:
    wrapper = (
        Path(__file__).parents[2]
        / "arnold_pipelines"
        / "megaplan"
        / "cloud"
        / "wrappers"
        / "arnold-watchdog"
    ).read_text(encoding="utf-8")

    assert 'inherited_goal_path="${ARNOLD_REPAIR_RETRY_GOAL_PATH:-}"' in wrapper
    assert 'managed_identity="${managed_identity}:goal:${inherited_goal_id}:retry:' in wrapper
    assert 'claim_active_repair_launch "$session" "$workspace" "$remote_spec" "$blocker_id" "$request_id"' in wrapper
    assert '--link "repair_goal_path=$inherited_goal_path"' in wrapper
    assert 'ARNOLD_REPAIR_GOAL_PATH="$inherited_goal_path"' in wrapper
    assert 'ARNOLD_REPAIR_CHECKPOINT_DIGEST="$inherited_checkpoint_digest"' in wrapper
    assert 'if [[ -n "${ARNOLD_REPAIR_RETRY_GOAL_ID:-}" ]]; then' in wrapper
    assert 'retained repair goal background-dispatched without touching target' in wrapper

    retained_retry = wrapper.index('if [[ -n "${ARNOLD_REPAIR_RETRY_GOAL_ID:-}" ]]; then')
    retained_end = wrapper.index('if mechanical_relaunch_attempted_previously "$session"; then', retained_retry)
    legacy_failed = wrapper.index('if kimi_dispatch_failed_previously "$session"; then', retained_end)
    target_kill = wrapper.index('tmux kill-session -t "$session"', legacy_failed)
    retained_block = wrapper[retained_retry:retained_end]
    assert 'dispatch_kimi_repair "$session" "$workspace" "$remote_spec"' in retained_block
    assert 'tmux kill-session -t "$session"' not in retained_block
    assert retained_retry < legacy_failed < target_kill


def test_watchdog_preserves_goal_control_action_through_dispatch_decision() -> None:
    wrapper = (
        Path(__file__).parents[2]
        / "arnold_pipelines"
        / "megaplan"
        / "cloud"
        / "wrappers"
        / "arnold-watchdog"
    ).read_text(encoding="utf-8")

    status = wrapper[wrapper.index("repair_goal_watchdog_status() {") :]
    status = status[: status.index("\n}\n")]
    assert 'control_action = str(evaluation.get("control_action") or "")' in status
    assert "{reason}\\t{control_action}" in status

    launch = wrapper[wrapper.index("launch_chain_tick() {") :]
    launch = launch[: launch.index("\n}\n")]
    assert "repair_goal_control_action" in launch
    assert 'if [[ "$repair_goal_control_action" == "preserve_live" ]]' in launch
    preserve = launch.index('if [[ "$repair_goal_control_action" == "preserve_live" ]]')
    dispatch = launch.index("repair_unintended_stop", preserve)
    assert launch.index("return 0", preserve) < dispatch


def test_blocker_cleared_live_runner_transition_is_preserved_not_accepted() -> None:
    result = evaluate_checkpoint(
        {
            "target_stage": "execute",
            "target_stage_rank": 6,
            "chain_current_plan_name": "m5a",
            "chain_current_milestone_index": 1,
            "chain_completed_count": 1,
        },
        {
            "target_stage": "execute",
            "target_stage_rank": 6,
            "chain_current_plan_name": "m5a",
            "chain_current_milestone_index": 1,
            "chain_completed_count": 1,
            "latest_failure_cleared": True,
            "active_worker": {},
            "runner_transition": {"runner_pid": 123, "runner_pid_live": True, "fresh": True},
        },
    )

    assert result["status"] == GOAL_ACTIVE
    assert result["control_action"] == "preserve_live"
    assert result["authoritative_progress"] is False
    assert "step-transition" in result["reason"]


def test_missing_quality_repair_commit_overrides_false_stage_advancement() -> None:
    result = evaluate_checkpoint(
        {
            "target_stage": "review",
            "target_stage_rank": 7,
            "chain_current_plan_name": "m5a",
            "chain_current_milestone_index": 1,
            "chain_completed_count": 1,
        },
        {
            "target_stage": "done",
            "target_stage_rank": 11,
            "plan_state": "done",
            "latest_failure_cleared": True,
            "chain_current_plan_name": "m5a",
            "chain_current_milestone_index": 1,
            "chain_completed_count": 1,
            "quality_resolution_commit_custody": {
                "required_commits": ["a" * 40],
                "missing_commits": ["a" * 40],
                "verified": False,
            },
        },
    )

    assert result["status"] == "active"
    assert result["control_action"] == "investigate"
    assert result["blocker_cleared"] is False
    assert "not contained" in result["reason"]


def test_terminal_chain_transition_supersedes_stale_commit_blocker() -> None:
    result = evaluate_checkpoint(
        {
            "target_stage": "review",
            "target_stage_rank": 7,
            "chain_current_plan_name": "m5a",
            "chain_current_milestone_index": 1,
            "chain_completed_count": 1,
        },
        {
            "target_stage": "done",
            "target_stage_rank": 11,
            "plan_state": "done",
            "latest_failure_cleared": True,
            "chain_current_plan_name": "",
            "chain_current_milestone_index": 2,
            "chain_completed_count": 2,
            "chain_last_state": "pr_closed",
            "quality_resolution_commit_custody": {
                "required_commits": ["a" * 40],
                "missing_commits": ["a" * 40],
                "verified": False,
            },
        },
    )

    assert result["status"] == GOAL_PROGRESSED
    assert result["control_action"] == "complete"
    assert result["superseded_blocker"] is True
    assert result["superseded_by"] == {
        "chain_completed_count": 2,
        "chain_current_milestone_index": 2,
        "chain_current_plan_name": "",
        "chain_last_state": "pr_closed",
    }


def test_quality_repair_commit_custody_reads_nested_state_metadata(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    subprocess.run(["git", "init", "-q", str(workspace)], check=True)
    subprocess.run(["git", "-C", str(workspace), "config", "user.email", "test@example.com"], check=True)
    subprocess.run(["git", "-C", str(workspace), "config", "user.name", "Test"], check=True)
    (workspace / "tracked.txt").write_text("base\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(workspace), "add", "tracked.txt"], check=True)
    subprocess.run(["git", "-C", str(workspace), "commit", "-qm", "base"], check=True)
    head = subprocess.run(
        ["git", "-C", str(workspace), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    missing = "f" * 40
    result = _quality_resolution_commit_custody(
        {
            "meta": {
                "quality_gate_resolutions": [
                    {
                        "resolution": "fixed",
                        "evidence": [f"local dev fix commit:{missing}"],
                    }
                ]
            }
        },
        workspace=workspace,
        workspace_head=head,
    )

    assert result == {
        "required_commits": [missing],
        "missing_commits": [missing],
        "verified": False,
    }


def test_repair_loop_refuses_goal_custody_without_request_and_blocker_links() -> None:
    wrapper = (
        Path(__file__).parents[2]
        / "arnold_pipelines"
        / "megaplan"
        / "cloud"
        / "wrappers"
        / "arnold-repair-loop"
    ).read_text(encoding="utf-8")

    assert 'blocker_id="${CLOUD_WATCHDOG_REPAIR_BLOCKER_ID:-}"' in wrapper
    assert 'request_id="${CLOUD_WATCHDOG_REPAIR_REQUEST_ID:-}"' in wrapper
    assert 'if [[ -z "$blocker_id" || -z "$request_id" ]]; then' in wrapper
    assert "blocker:session:$SESSION" not in wrapper


def test_repair_loop_fences_mechanical_relaunch_and_uses_two_stage_owner() -> None:
    wrapper = (
        Path(__file__).parents[2]
        / "arnold_pipelines"
        / "megaplan"
        / "cloud"
        / "wrappers"
        / "arnold-repair-loop"
    ).read_text(encoding="utf-8")

    mechanical = wrapper[wrapper.index("mechanical_launch_step() {") :]
    mechanical = mechanical[: mechanical.index("\n}\n")]
    assert 'repair_goal_control_snapshot "pre-mechanical-relaunch-$iteration"' in mechanical
    assert 'control_action"' in mechanical
    assert 'echo "preserved:live_progress"' in mechanical
    assert mechanical.index("preserved:live_progress") < mechanical.index('tmux has-session -t "$session"')
    assert 'echo "preserved:runner_transition"' in mechanical
    assert mechanical.index("preserved:runner_transition") < mechanical.index('tmux has-session -t "$session"')
    assert "kill_matching_runner_processes" not in mechanical
    assert "tmux kill-session" not in mechanical
    assert "run_repair_investigator_turn()" in wrapper
    assert '"investigator-replan-required"' in wrapper
    assert '"validated investigator requires L2 replan before any target mutation"' in wrapper
    assert "automatic_research_subagent" in wrapper
    assert "--sandbox read-only" in wrapper
    assert 'REPAIR_OWNER_MODEL="${CLOUD_WATCHDOG_REPAIR_OWNER_MODEL:-gpt-5.6-sol}"' in wrapper
    assert 'REPAIR_ITERATION_MAX="${CLOUD_WATCHDOG_REPAIR_ITERATION_MAX:-1}"' in wrapper
    assert "sole high-reasoning goal owner" in wrapper
    assert "Success requires the blocker cleared" in wrapper
    assert '--difficulty "$([[ "$recurring" == "1" ]] && printf 8 || printf 7)"' in wrapper
    assert 'printf 9 || printf 7' not in wrapper

    investigator = wrapper[wrapper.index("run_repair_investigator_turn() {") :]
    investigator = investigator[: investigator.index("\n}\n")]
    assert '--link "repair_goal_id=' not in investigator
    assert '--link "repair_goal_path=' not in investigator

    terminal = wrapper[wrapper.index("if [[ \"${BREAKER_TRIPPED:-0}\" == \"1\" ]]") :]
    terminal = terminal[: terminal.index("\nfi\n")]
    assert 'repair_data_set_outcome "deterministic_failure"' in terminal
    assert 'repair_goal_record_terminal_failure' in terminal
    assert 'repair_data_set_outcome "recurring_retry_pending"' not in terminal
