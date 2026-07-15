from __future__ import annotations

import json
import os
from pathlib import Path

from arnold_pipelines.megaplan.cloud import repair_contract
from arnold_pipelines.megaplan.cloud.repair_goal import (
    GOAL_ACTIVE,
    GOAL_APPROVAL_REQUIRED,
    GOAL_PROGRESSED,
    ensure_repair_goal,
    evaluate_repair_goal,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")


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


def test_later_authoritative_transition_beyond_checkpoint_completes_goal(tmp_path: Path) -> None:
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

    result = evaluate_repair_goal(path, action="post_redrive_verify")

    assert result["status"] == GOAL_PROGRESSED
    assert result["semantic_completion"] is True
    assert result["evaluation"]["authoritative_progress"] is True
    assert result["evaluation"]["acceptance_event"]["seq"] == 14


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
    assert mechanical.index("preserved:live_progress") < mechanical.index("kill_matching_runner_processes")
    assert "run_repair_investigator_turn()" in wrapper
    assert "automatic_research_subagent" in wrapper
    assert "--sandbox read-only" in wrapper
    assert 'REPAIR_OWNER_MODEL="${CLOUD_WATCHDOG_REPAIR_OWNER_MODEL:-gpt-5.6-sol}"' in wrapper
    assert 'REPAIR_ITERATION_MAX="${CLOUD_WATCHDOG_REPAIR_ITERATION_MAX:-1}"' in wrapper
    assert "sole high-reasoning goal owner" in wrapper
    assert "Success requires the blocker cleared" in wrapper
