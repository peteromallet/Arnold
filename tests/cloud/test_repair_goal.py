from __future__ import annotations

import json
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
    assert "not produced authoritative acceptance progress" in result["evaluation"]["reason"]


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
    state["current_state"] = "executed"
    _write_json(state_path, state)
    events = Path(goal["frozen_checkpoint"]["events_path"])
    with events.open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    "kind": "state_transition",
                    "seq": 14,
                    "ts_utc": "2026-07-15T00:02:00+00:00",
                    "payload": {"from": "blocked", "to": "executed"},
                }
            )
            + "\n"
        )

    result = evaluate_repair_goal(path, action="post_redrive_verify")

    assert result["status"] == GOAL_PROGRESSED
    assert result["semantic_completion"] is True
    assert result["evaluation"]["authoritative_progress"] is True
    assert result["evaluation"]["acceptance_event"]["seq"] == 14


def test_explicit_authorization_gate_terminates_with_exact_gate_evidence(tmp_path: Path) -> None:
    path, goal = _goal(tmp_path)
    state_path = Path(goal["frozen_checkpoint"]["plan_state_path"])
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["current_state"] = "awaiting_authorization"
    _write_json(state_path, state)

    result = evaluate_repair_goal(path, action="approval_gate_check")

    assert result["status"] == GOAL_APPROVAL_REQUIRED
    assert result["semantic_completion"] is True
    assert result["evaluation"]["authoritative_progress"] is False
    gate = result["evaluation"]["approval_gate"]
    assert gate["gate_state"] == "awaiting_authorization"
    assert gate["plan_state_path"] == str(state_path)
