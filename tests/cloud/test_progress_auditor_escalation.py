from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json

from arnold_pipelines.megaplan.cloud.progress_auditor_escalation import (
    DEEP_REPAIR_DIFFICULTY,
    DEEP_REPAIR_MODEL,
    DEEP_REPAIR_RUN_KIND,
    EscalationPolicy,
    bounded_repair_context,
    classify_true_stall,
    next_attempt_state,
    plan_dispatch,
    record_reverification,
    validate_managed_launch,
    verify_recovery,
)


NOW = datetime(2026, 7, 13, 22, 0, tzinfo=timezone.utc)


def _true_stall() -> dict:
    return {
        "session": "stuck-chain",
        "plan": "m2-repair-contract",
        "workspace": "/workspace/stuck/Arnold",
        "state_path": "/workspace/stuck/Arnold/.megaplan/plans/m2-repair-contract/state.json",
        "current_state": "blocked",
        "iteration": 3,
        "events_size": 4096,
        "events_mtime_age_min": 150,
        "session_header": {
            "session": "stuck-chain",
            "workspace": "/workspace/stuck/Arnold",
            "kind": "chain",
            "remote_spec": "/workspace/stuck/Arnold/.megaplan/initiatives/demo/chain.yaml",
            "marker_path": "/workspace/.megaplan/cloud-sessions/stuck-chain.json",
            "log": "/workspace/stuck/Arnold/.megaplan/cloud-chain-stuck-chain.log",
        },
        "current_target": {
            "session": "stuck-chain",
            "target_id": "stuck-chain:m2-repair-contract",
            "authoritative_source": "chain_state",
            "current_refs": {
                "workspace": "/workspace/stuck/Arnold",
                "remote_spec": "/workspace/stuck/Arnold/.megaplan/initiatives/demo/chain.yaml",
                "marker_path": "/workspace/.megaplan/cloud-sessions/stuck-chain.json",
            },
            "tmux_process": {
                "pid_live": False,
                "session_live": False,
                "live_status": "stopped",
            },
            "ci_health": {"status": "unavailable", "reason": "not applicable"},
        },
        "resolver_state": {
            "canonical_state": "MACHINE_ACTION_REQUIRED",
            "confidence": "high",
            "next_action": "meta_repair.repair_attempt",
        },
        "active_step_liveness": {
            "present": True,
            "worker_pid": 777,
            "worker_pid_alive": False,
        },
        "chain_state_summary": {
            "current": {
                "path": "/workspace/stuck/Arnold/.megaplan/plans/.chains/demo.json",
                "last_state": "blocked",
                "chain_complete": False,
                "current_plan_name": "m2-repair-contract",
                "completed_count": 1,
                "total_milestones": 4,
                "pr_state": "",
            }
        },
        "chain_log": {
            "path": "/workspace/stuck/Arnold/.megaplan/cloud-chain-stuck-chain.log",
            "size_bytes": 8192,
            "mtime_age_min": 145,
            "repetition_summary": [{"signature": "same_exception", "count": 4}],
        },
        "repair_data_summary": {
            "exists": True,
            "outcome": "repair_exhausted",
            "mtime_age_min": 130,
            "iterations": [
                {
                    "exception": "RuntimeError: writer/reader token drift",
                    "returncode": 1,
                    "command": "megaplan auto --resume",
                }
            ],
        },
        "repair_custody_summary": {
            "blocker_id": "blocker-123",
            "accepted_unclaimed_request_ids": ["request-123"],
            "claim_count": 0,
            "attempt_count": 0,
            "retry_budget": {
                "claim_retries_used": 2,
                "claim_retries_remaining": 1,
            },
        },
        "meta_repair_summary": {
            "should_dispatch": True,
            "trigger": "l1_custody_failure",
            "missing_meta_run_evidence": True,
            "meta_record_count": 0,
            "meta_run_log_count": 0,
        },
        "deterministic_superfixer_evidence": {
            "actionable": True,
            "runner_dead": True,
            "chain_incomplete": True,
            "absent_or_stale_l2": True,
            "accepted_unclaimed_request_ids": ["request-123"],
        },
        "deterministic_retry_evidence": {
            "count": 4,
            "signature": "RuntimeError: writer/reader token drift",
        },
        "plan_latest_failure": {
            "kind": "execution_blocked",
            "phase": "execute",
            "message": "writer/reader token drift",
            "recorded_at": "2026-07-13T18:00:00Z",
            "metadata": {
                "stderr": "RuntimeError: expected awaiting_human, got awaiting_human_verify",
                "returncode": 1,
                "exception": "RuntimeError",
                "command": "megaplan auto --resume",
            },
        },
        "user_action_context": {"unresolved_user_actions": []},
        "source_refs": {
            "watchdog_report_paths": ["/workspace/watchdog-reports/one.json"],
            "attempt_paths": ["/workspace/.megaplan/repair-queue/attempts/one.json"],
            "meta_run_log_paths": ["/workspace/.megaplan/meta-runs/one.log"],
        },
        "reasons": [
            "stale_l1_l2_cycle: accepted-unclaimed repair exhausted",
            "deterministic_retry_exhaustion: same exception 4x",
        ],
    }


def test_true_stall_gate_requires_all_six_sources_and_walks_l1_l2_l3() -> None:
    gate = classify_true_stall(_true_stall())

    assert gate["eligible"] is True
    assert gate["decision"] == "true_stall"
    assert set(gate["evidence_sources"]) == {
        "live_process",
        "session_marker",
        "chain_json",
        "plan_state",
        "logs",
        "external_state",
    }
    assert gate["custody_walk"]["first_broken_layer"] == "L1"
    assert gate["custody_walk"]["missed_by_layer"] == "L2"
    assert gate["route"] == {
        "requested_difficulty": 9,
        "effective_difficulty": 9,
        "model": "gpt-5.6-sol",
        "reasoning_effort": "high",
        "child_difficulty_ceiling": 9,
        "promotion_reason": "",
    }
    assert gate["quarantine"]["state"] == "not_applied"


def test_live_slow_chain_with_fresh_heartbeat_is_a_hard_noop() -> None:
    finding = _true_stall()
    finding["events_mtime_age_min"] = 2
    finding["chain_log"]["mtime_age_min"] = 3
    finding["current_target"]["tmux_process"] = {
        "pid_live": True,
        "session_live": True,
        "live_status": "alive",
    }
    finding["active_step_liveness"] = {
        "present": True,
        "worker_pid_alive": True,
        "token_heartbeat_age_min": 1,
    }

    gate = classify_true_stall(finding)

    assert gate["eligible"] is False
    assert "healthy_live_process" in gate["blocks"]
    assert gate["progress"]["fresh"] is False
    assert "token_heartbeat" in gate["progress"]["liveness_sources"]
    assert gate["progress"]["fresh_sources"] == []
    assert gate["progress"]["liveness_sources"] == [
        "events",
        "chain_log",
        "token_heartbeat",
    ]


def test_superseded_snapshot_fails_closed() -> None:
    finding = _true_stall()
    finding["evidence_snapshot"] = {
        "status": "superseded",
        "changed_refs": [{"kind": "repair_data", "path": "/tmp/repair.json"}],
    }

    gate = classify_true_stall(finding)

    assert gate["eligible"] is False
    assert "evidence_snapshot_superseded" in gate["blocks"]


def test_terminal_repair_failure_is_not_semantic_progress() -> None:
    finding = _true_stall()
    finding["events_mtime_age_min"] = 2
    finding["repair_data_summary"]["mtime_age_min"] = 1
    finding["acceptance_progress"] = {"advanced": False, "accepted_event_age_min": None}
    finding["deterministic_superfixer_evidence"].update(
        {"actionable": True, "runner_dead": True, "chain_incomplete": True}
    )

    gate = classify_true_stall(finding)

    assert "no_progress_window_not_proven" not in gate["blocks"]
    assert gate["progress"]["terminal_repair_failure_without_progress"] is True


def test_ordinary_retrigger_failure_is_l2_fixed_axis_not_tracking_axis() -> None:
    finding = _true_stall()
    finding["meta_repair_summary"]["failed_meta_run_count"] = 0
    finding["meta_repair_summary"]["missing_meta_run_evidence"] = False
    finding["meta_repair_summary"]["meta_record_count"] = 1
    finding["meta_repair_summary"]["meta_run_log_count"] = 1
    finding["meta_repair_summary"]["meta_run_refs"] = [
        {
            "current_episode": True,
            "failure_code": "ordinary_retrigger_failed",
            "ordinary_retrigger_failed": True,
            "launch_failure": False,
        }
    ]
    finding["deterministic_superfixer_evidence"]["absent_or_stale_l2"] = False

    gate = classify_true_stall(finding)

    assert gate["custody_walk"]["L2"]["TRACKED"] is True
    assert gate["custody_walk"]["L2"]["CONTEXT"] is True
    assert gate["custody_walk"]["L2"]["FIXED"] is False
    assert gate["custody_walk"]["L2"]["failure"]["axis"] == "FIXED"


def test_partial_liveness_with_unclaimed_request_is_l1_context_failure() -> None:
    finding = _true_stall()
    finding["repair_data_summary"]["outcome"] = "partial_liveness"
    finding["repair_custody_summary"]["retry_budget"] = {
        "claim_retries_used": 0,
        "claim_retries_remaining": 3,
    }
    finding["deterministic_retry_evidence"]["count"] = 2

    gate = classify_true_stall(finding)

    assert gate["eligible"] is True
    l1 = gate["custody_walk"]["L1"]["failure"]
    assert l1["provisional_liveness"] is True
    assert l1["liveness_without_custody"] is True
    assert gate["custody_walk"]["first_broken_axis"] == "CONTEXT"
    assert gate["custody_walk"]["missed_by_layer"] == "L2"


def test_partial_liveness_with_empty_custody_links_is_l1_context_failure() -> None:
    finding = _true_stall()
    finding["repair_data_summary"]["outcome"] = "partial_liveness"
    finding["repair_custody_summary"]["blocker_id"] = ""
    finding["repair_custody_summary"]["active_request_ids"] = []
    finding["repair_custody_summary"]["accepted_unclaimed_request_ids"] = []
    finding["repair_custody_summary"]["retry_budget"] = {
        "claim_retries_used": 0,
        "claim_retries_remaining": 3,
    }

    gate = classify_true_stall(finding)

    assert gate["eligible"] is True
    l1 = gate["custody_walk"]["L1"]["failure"]
    assert l1["missing_custody_links"] is True
    assert l1["liveness_without_custody"] is True
    assert gate["custody_walk"]["first_broken_axis"] == "CONTEXT"


def test_l1_false_success_is_caught_and_l2_miss_remains_required() -> None:
    finding = _true_stall()
    finding["repair_data_summary"]["outcome"] = "complete"
    finding["repair_custody_summary"]["accepted_unclaimed_request_ids"] = []
    finding["reasons"].append("repair_complete_incomplete_chain: false success")

    gate = classify_true_stall(finding)

    assert gate["eligible"] is True
    l1 = gate["custody_walk"]["L1"]["failure"]
    assert l1["false_success"] is True
    assert gate["custody_walk"]["first_broken_axis"] == "FIXED"
    assert gate["custody_walk"]["missed_by_layer"] == "L2"


def test_missing_marker_or_canonical_chain_path_fails_closed() -> None:
    finding = _true_stall()
    finding["session_header"]["marker_path"] = ""
    finding["current_target"]["current_refs"]["marker_path"] = ""
    finding["chain_state_summary"]["current"]["path"] = ""

    gate = classify_true_stall(finding)

    assert gate["eligible"] is False
    assert gate["missing_sources"] == [
        "canonical_chain_path",
        "session_marker",
    ]
    assert "incomplete_or_incoherent_evidence" in gate["blocks"]


def test_intentional_pause_and_human_gate_are_not_faults() -> None:
    paused = _true_stall()
    paused["current_state"] = "paused"
    paused["resolver_state"]["canonical_state"] = "PAUSED"
    human = _true_stall()
    human["resolver_state"]["canonical_state"] = "HUMAN_ACTION_REQUIRED"
    human["user_action_context"]["unresolved_user_actions"] = [{"id": "approve-release"}]

    for finding in (paused, human):
        gate = classify_true_stall(finding)
        assert gate["eligible"] is False
        assert "intentional_pause_or_human_gate" in gate["blocks"]
        assert gate["quarantine"]["state"] == "not_applied"


def test_open_pr_or_pending_external_state_is_an_intentional_wait() -> None:
    finding = _true_stall()
    finding["chain_state_summary"]["current"].update(
        {"last_state": "awaiting_pr_merge", "pr_number": 42, "pr_state": "open"}
    )
    finding["current_target"]["ci_health"] = {"status": "pending", "available": True}

    gate = classify_true_stall(finding)

    assert gate["eligible"] is False
    assert gate["evidence_sources"]["external_state"]["intentional_wait"] is True
    assert "intentional_pause_or_human_gate" in gate["blocks"]


def test_open_pr_does_not_hide_blocked_unowned_active_repair_goal() -> None:
    finding = _true_stall()
    finding["resolver_state"] = {"canonical_state": "UNKNOWN", "confidence": "low"}
    finding["chain_state_summary"]["current"].update(
        {"last_state": "blocked", "pr_number": 255, "pr_state": "open"}
    )
    finding["current_target"]["ci_health"] = {
        "status": "failure", "available": True, "pr_number": 255
    }
    finding["repair_data_summary"].update(
        {"outcome": "deterministic_failure", "mtime_age_min": 130}
    )
    finding["repair_custody_summary"]["retry_budget"] = {
        "claim_retries_used": 0, "claim_retries_remaining": 3
    }
    finding["meta_repair_summary"]["repair_goal"] = {
        "goal_id": "repair-goal-original-epic",
        "status": "active",
        "owner_live": False,
        "control_action": "investigate",
    }
    # Hourly control-plane writes are liveness, not semantic progress.
    finding["events_mtime_age_min"] = 2
    finding["chain_log"]["mtime_age_min"] = 3
    finding["acceptance_progress"] = {
        "advanced": False, "accepted_event_age_min": 150
    }

    gate = classify_true_stall(finding)

    assert gate["eligible"] is True
    assert gate["custody_walk"]["L1"]["failure"]["active_unowned_goal"] is True
    assert gate["progress"]["fresh"] is False
    assert gate["progress"]["liveness_sources"] == ["events", "chain_log"]
    assert gate["evidence_sources"]["external_state"]["intentional_wait"] is False


def test_preserve_live_goal_does_not_create_unowned_goal_failure() -> None:
    finding = _true_stall()
    finding["repair_custody_summary"]["accepted_unclaimed_request_ids"] = []
    finding["repair_data_summary"]["outcome"] = "partial_liveness"
    finding["meta_repair_summary"]["repair_goal"] = {
        "status": "active", "owner_live": False, "control_action": "preserve_live"
    }
    finding["meta_repair_summary"].update(
        {"should_dispatch": False, "missing_meta_run_evidence": False}
    )
    finding["deterministic_superfixer_evidence"]["actionable"] = False
    finding["deterministic_superfixer_evidence"]["absent_or_stale_l2"] = False
    finding["deterministic_retry_evidence"]["count"] = 0
    finding["reasons"] = []

    gate = classify_true_stall(finding)

    assert gate["eligible"] is False
    assert gate["custody_walk"]["L1"]["failure"]["active_unowned_goal"] is False
    assert "preserve_live_repair_goal" in gate["blocks"]


def test_applicable_external_state_must_match_the_exact_pr() -> None:
    finding = _true_stall()
    finding["chain_state_summary"]["current"].update(
        {"pr_number": 42, "pr_state": "closed"}
    )
    finding["current_target"]["ci_health"] = {
        "status": "green",
        "available": True,
        "pr_number": 41,
    }

    gate = classify_true_stall(finding)

    assert gate["eligible"] is False
    assert gate["evidence_sources"]["external_state"]["coherent"] is False
    assert "external_state" in gate["missing_sources"]


def test_dispatch_requires_authority_and_obeys_dedupe_cooldown_and_concurrency() -> None:
    gate = classify_true_stall(_true_stall())
    assert plan_dispatch(gate, {}, authorized=False, now=NOW)["decision"] == "blocked_authority"
    assert plan_dispatch(gate, {}, authorized=True, now=NOW)["decision"] == "dispatch_authorized"
    active = {
        "attempts": [{"status": "running", "managed_run_id": "managed-one", "outcome": "dispatched"}]
    }
    assert plan_dispatch(gate, active, authorized=True, now=NOW)["decision"] == "deduplicated_active"
    cooling = {"attempts": [], "cooldown_until": (NOW + timedelta(hours=1)).isoformat()}
    assert plan_dispatch(gate, cooling, authorized=True, now=NOW)["decision"] == "cooldown"
    assert plan_dispatch(gate, {}, authorized=True, active_global=1, now=NOW)["decision"] == "concurrency_limited"


def test_retry_exhaustion_opens_durable_circuit_breaker() -> None:
    gate = classify_true_stall(_true_stall())
    state = next_attempt_state({}, gate=gate, outcome="launch_failed", now=NOW)
    state = next_attempt_state(
        state,
        gate=gate,
        outcome="launch_failed",
        now=NOW + timedelta(minutes=10),
    )

    assert state["circuit_reason"] == "launch_establishment_budget_exhausted"
    decision = plan_dispatch(
        gate,
        state,
        authorized=True,
        now=NOW + timedelta(minutes=20),
    )
    assert decision["decision"] == "circuit_open"
    assert decision["dispatch"] is False


def test_reverification_closes_attempt_and_blocks_repeat_dispatch() -> None:
    gate = classify_true_stall(_true_stall())
    state = next_attempt_state(
        {},
        gate=gate,
        outcome="dispatched",
        managed_run_id="managed-deep",
        managed_manifest_path="/tmp/manifest.json",
        now=NOW,
    )
    state = record_reverification(
        state,
        verification={"verified": True, "outcome": "recovery_verified"},
        now=NOW + timedelta(hours=1),
    )

    assert state["attempts"][-1]["status"] == "completed"
    assert state["outcome"] == "recovery_verified"
    assert plan_dispatch(
        gate,
        state,
        authorized=True,
        now=NOW + timedelta(hours=7),
    )["decision"] == "recovery_verified"


def _valid_manifest(gate: dict) -> dict:
    provenance = {
        "schema_version": "arnold-machine-origin-provenance-v1",
        "applicability": "not_applicable",
        "transport": "automatic_system",
        "origin_kind": "periodic_progress_auditor",
        "origin_id": gate["escalation_id"],
        "component": "test_progress_auditor_escalation",
        "trigger_id": "request-deep",
    }
    return {
        "schema_version": "arnold-managed-agent-run-v2",
        "custodian": "arnold.megaplan.managed_agent",
        "run_id": "managed-automatic-root-cause-repair-123",
        "run_kind": DEEP_REPAIR_RUN_KIND,
        "manifest_path": "/workspace/stuck/Arnold/.megaplan/plans/resident-subagents/run/manifest.json",
        "model": DEEP_REPAIR_MODEL,
        "reasoning_effort": "high",
        "task_kind": "root_cause",
        "route_class": "progress_auditor_d9_repair",
        "backend": "meta-repair-loop",
        "log_path": "/tmp/managed-root-repair.log",
        "result_path": "/tmp/managed-root-repair-result.json",
        "difficulty": DEEP_REPAIR_DIFFICULTY,
        "authority": {"child_difficulty_ceiling": DEEP_REPAIR_DIFFICULTY},
        "launch_contract_sha256": "a" * 64,
        "launch_provenance": provenance,
        "provenance_sha256": hashlib.sha256(
            json.dumps(provenance, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
        "stdin": {"kind": "devnull", "sealed": True, "size_bytes": 0},
        "links": {
            "repair_request_id": "request-deep",
            "audit_escalation_id": gate["escalation_id"],
            "cloud_session": gate["session"],
        },
        "status_history": [{"status": "running", "evidence": "worker_process_started"}],
    }


def test_canonical_durable_manifest_is_required_before_dispatched_claim() -> None:
    gate = classify_true_stall(_true_stall())
    valid = validate_managed_launch(
        _valid_manifest(gate), gate=gate, request_id="request-deep"
    )
    missing = _valid_manifest(gate)
    missing["status_history"] = []
    invalid = validate_managed_launch(missing, gate=gate, request_id="request-deep")

    assert valid["valid"] is True
    assert valid["dispatched"] is True
    assert valid["managed_run_id"].startswith("managed-")
    assert invalid["valid"] is False
    assert invalid["dispatched"] is False
    assert invalid["managed_run_id"] == ""
    assert "worker_start_evidence_missing" in invalid["errors"]


def test_recovery_requires_fixer_and_backstop_then_normal_retrigger_and_original_advance() -> None:
    finding = _true_stall()
    baseline = classify_true_stall(finding)["baseline_cursor"]
    recovered = _true_stall()
    recovered["chain_state_summary"]["current"].update(
        {
            "current_plan_name": "m3-next",
            "completed_count": 2,
            "last_state": "running",
        }
    )
    recovered["events_size"] = 8192
    recovered["current_target"]["tmux_process"] = {
        "pid_live": True,
        "session_live": True,
        "live_status": "alive",
    }
    outcome = {
        "fixer_fixed": True,
        "backstop_fixed": True,
        "ordinary_retrigger_run_id": "managed-retrigger",
        "ordinary_retrigger_manifest_path": "/workspace/retrigger/manifest.json",
        "guard_changes": [],
    }

    result = verify_recovery(
        baseline=baseline,
        current_finding=recovered,
        repair_outcome=outcome,
    )

    assert result["verified"] is True
    assert result["original_run_advanced"] is True
    assert result["ordinary_retriggered"] is True


def test_agent_completion_or_guard_weakening_cannot_manufacture_recovery() -> None:
    finding = _true_stall()
    baseline = classify_true_stall(finding)["baseline_cursor"]
    outcome = {
        "agent_status": "completed",
        "fixer_fixed": True,
        "backstop_fixed": True,
        "ordinary_retrigger_run_id": "managed-retrigger",
        "ordinary_retrigger_manifest_path": "/workspace/retrigger/manifest.json",
        "guard_changes": ["completion_guard: required -> optional"],
        "direct_state_advance": True,
    }

    result = verify_recovery(
        baseline=baseline,
        current_finding=finding,
        repair_outcome=outcome,
    )

    assert result["verified"] is False
    assert result["guard_weakened"] is True
    assert "completion_or_safety_guard_weakened" in result["reasons"]
    assert "original_run_did_not_advance" in result["reasons"]


def test_deep_context_contains_actual_failure_mechanics_and_bounded_artifacts() -> None:
    context = bounded_repair_context(_true_stall())

    assert context["failure_mechanics"] == {
        "stderr": "RuntimeError: expected awaiting_human, got awaiting_human_verify",
        "returncode": 1,
        "exception": "RuntimeError",
        "command": "megaplan auto --resume",
    }
    assert context["artifact_refs"]["attempt_paths"] == [
        "/workspace/.megaplan/repair-queue/attempts/one.json"
    ]
    assert context["required_method"]["methodology"] == "superfixer-debug"
    assert context["required_method"]["child_difficulty_ceiling"] == 9
    assert len(context["context_digest"]) == 64


def test_policy_rejects_child_authority_above_root_ceiling() -> None:
    gate = classify_true_stall(_true_stall())
    manifest = _valid_manifest(gate)
    manifest["authority"]["child_difficulty_ceiling"] = 10

    result = validate_managed_launch(manifest, gate=gate, request_id="request-deep")

    assert result["valid"] is False
    assert "child_authority_ceiling_invalid" in result["errors"]
