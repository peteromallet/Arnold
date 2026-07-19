from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.cloud.progress_auditor_escalation import (
    AUDIT_REVIEW_EVIDENCE_MAX_BYTES,
    DEEP_REPAIR_DIFFICULTY,
    DEEP_REPAIR_MODEL,
    DEEP_REPAIR_RUN_KIND,
    EscalationPolicy,
    bounded_repair_context,
    bounded_audit_review_pointer,
    bounded_auditor_projection,
    classify_true_stall,
    next_attempt_state,
    normalize_audit_review_response,
    plan_dispatch,
    record_reverification,
    validate_l3_repair_dispatch_context,
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


def _approval_gate_after_superfixer_repair() -> dict:
    finding = _true_stall()
    finding["current_state"] = "done"
    finding["resolver_state"] = {
        "canonical_state": "COMPLETED",
        "confidence": "high",
    }
    finding["chain_state_summary"]["current"].update(
        {
            "last_state": "awaiting_pr_merge",
            "chain_complete": False,
            "pr_number": 255,
            "pr_state": "open",
        }
    )
    finding["current_target"]["ci_health"] = {
        "available": True,
        "status": "green",
        "pr_number": 255,
    }
    finding["repair_data_summary"].update(
        {
            "repair_goal_summary": {"status": "approval_required"},
            "investigation_summary": {
                "actual_failure": {
                    "mechanism": "required quality commit was absent from target ancestry"
                },
                "safe_repair_target": {
                    "kind": "target_workspace",
                    "scope": "apply-required-quality-commit",
                },
            },
        }
    )
    finding["meta_repair_summary"]["repair_goal"] = {
        "status": "approval_required",
        "control_action": "await_approval",
    }
    return finding


def test_l3_dispatch_context_requires_coherent_bounded_request_custody(
    tmp_path: Path,
) -> None:
    context = bounded_repair_context(_true_stall())
    context_path = tmp_path / "repair-context.json"
    context_path.write_text(json.dumps(context), encoding="utf-8")
    request_id = "a" * 64
    request_path = tmp_path / f"{request_id}.json"
    gate = context["gate"]
    request = {
        "schema_version": 1,
        "kind": "repair_request",
        "request_id": request_id,
        "source": "six_hour_auditor",
        "session": context["session"],
        "resident_delegation": {
            "schema_version": "arnold-resident-delegation-provenance-v1",
            "source_record_id": "message-1",
        },
        "target": {
            "dispatch_intent": "deep_superfixer_repair",
            "retry_strategy": "deep_superfixer_repair",
            "repair_context_path": str(context_path),
            "repair_context_digest": context["context_digest"],
            "root_cause_identity": gate["escalation_id"],
            "l3_escalation_gate": gate,
        },
    }
    request_path.write_text(json.dumps(request), encoding="utf-8")

    pointer = validate_l3_repair_dispatch_context(
        context_path=context_path,
        request_path=request_path,
        expected_session=context["session"],
        expected_context_digest=context["context_digest"],
        expected_escalation_id=gate["escalation_id"],
        expected_request_id=request_id,
    )

    assert pointer["schema_version"] == "arnold-l3-meta-repair-pointer-v1"
    assert pointer["context"]["bytes"] == context_path.stat().st_size
    assert pointer["gate"]["first_broken_layer"] == "L1"

    request["target"]["repair_context_digest"] = "b" * 64
    request_path.write_text(json.dumps(request), encoding="utf-8")
    with pytest.raises(ValueError, match="disagrees"):
        validate_l3_repair_dispatch_context(
            context_path=context_path,
            request_path=request_path,
            expected_session=context["session"],
            expected_context_digest=context["context_digest"],
            expected_escalation_id=gate["escalation_id"],
            expected_request_id=request_id,
        )


def test_l3_dispatch_context_fails_closed_above_64_kib(tmp_path: Path) -> None:
    context_path = tmp_path / "repair-context.json"
    context_path.write_bytes(b"{" + b" " * (64 * 1024) + b"}")
    request_id = "c" * 64
    request_path = tmp_path / f"{request_id}.json"
    request_path.write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="byte bound"):
        validate_l3_repair_dispatch_context(
            context_path=context_path,
            request_path=request_path,
            expected_session="stuck-chain",
            expected_context_digest="d" * 64,
            expected_escalation_id="l3-escalation:test",
            expected_request_id=request_id,
        )


def test_l3_review_pointer_does_not_inline_recursive_projection(
    tmp_path: Path,
) -> None:
    recursive = {
        "incident_id": "inc-1",
        "summary": "current incident",
        "decision": {"prior_audit_response": "x" * (23 * 1024 * 1024)},
    }
    bounded_projection = bounded_auditor_projection(recursive, kind="incident")
    assert "decision" not in bounded_projection
    assert len(json.dumps(bounded_projection).encode("utf-8")) < 8192

    finding = _true_stall()
    finding["incident_projection"] = recursive
    evidence_path = tmp_path / "finding.json"
    evidence_path.write_text(json.dumps(finding), encoding="utf-8")
    pointer = bounded_audit_review_pointer(finding, evidence_path=evidence_path)
    encoded = json.dumps(pointer, sort_keys=True).encode("utf-8")

    assert len(encoded) <= AUDIT_REVIEW_EVIDENCE_MAX_BYTES
    assert pointer["authoritative_evidence"]["bytes"] > 23 * 1024 * 1024
    assert "x" * 4096 not in encoded.decode("utf-8")


def test_l3_review_response_fails_closed_on_overflow_and_cli_error() -> None:
    overflow = normalize_audit_review_response("x" * (33 * 1024))
    cli_error = normalize_audit_review_response(
        "OpenAI Codex\nError: turn/start failed: Input exceeds the maximum length; input_too_large"
    )

    assert overflow.startswith("REPAIR_REQUEST\n")
    assert cli_error.startswith("REPAIR_REQUEST\n")
    assert normalize_audit_review_response("PASSIVE\nNo issue.") == "PASSIVE\nNo issue."


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


def test_retroactive_superfixer_failure_routes_to_explicit_approval_gate() -> None:
    gate = classify_true_stall(_approval_gate_after_superfixer_repair())

    assert gate["eligible"] is False
    assert gate["decision"] == "approval_required"
    assert gate["corrective_path"] == {
        "schema_version": "arnold-l3-corrective-path-v1",
        "kind": "approval_gate",
        "decision": "approval_required",
        "action": "await_human_pr_merge",
        "repair_dispatch_permitted": False,
        "pr_number": 255,
        "pr_state": "open",
        "gate_state": "awaiting_pr_merge",
        "root_cause": "required quality commit was absent from target ancestry",
        "safe_repair_target": {
            "kind": "target_workspace",
            "scope": "apply-required-quality-commit",
        },
        "first_broken_layer": "L1",
        "first_broken_axis": gate["custody_walk"]["first_broken_axis"],
        "missed_by_layer": "L2",
        "missed_by_axis": gate["custody_walk"]["missed_by_axis"],
        "reason": (
            "the historical L1/L2 failure is detected and repaired locally, but "
            "the authoritative review policy requires remote PR merge approval"
        ),
    }
    assert gate["custody_walk"]["first_broken_layer"] == "L1"
    assert gate["custody_walk"]["missed_by_layer"] == "L2"


def test_terminal_l2_receipt_completes_process_evidence_without_live_pid() -> None:
    finding = _true_stall()
    finding["current_target"]["tmux_process"] = {
        "session": "custody-control-plane",
        "live_status": "unknown",
    }
    finding["active_step_liveness"] = {"present": False}
    finding["prior_watchdog_report_refs"] = [{"matched_status": "dispatched"}]
    finding["meta_repair_summary"].update(
        {
            "should_dispatch": True,
            "meta_run_refs": [
                {
                    "current_episode": True,
                    "failure_code": "meta_repair_authority_blocked",
                }
            ],
            "failed_meta_run_count": 1,
            "failed_meta_run_evidence": True,
        }
    )
    finding["deterministic_superfixer_evidence"].update(
        {
            "actionable": True,
            "failed_l2_evidence": True,
            "runner_dead": True,
            "chain_incomplete": True,
        }
    )

    gate = classify_true_stall(finding)

    assert gate["evidence_sources"]["live_process"]["state"] == "dead"
    assert "incomplete_or_incoherent_evidence" not in gate["blocks"]
    assert gate["eligible"] is True


def test_terminal_l2_all_launch_paths_failed_is_dispatchable_immediately() -> None:
    finding = _true_stall()
    finding["current_target"]["tmux_process"] = {"live_status": "unknown"}
    finding["active_step_liveness"] = {"present": False}
    finding["meta_repair_summary"].update(
        {
            "should_dispatch": True,
            "missing_meta_run_evidence": False,
            "meta_run_refs": [
                {
                    "current_episode": True,
                    "failure_code": "meta_repair_launch_failure",
                    "launch_failure": True,
                    "terminal_failure": True,
                }
            ],
            "failed_meta_run_count": 1,
            "failed_meta_run_evidence": True,
        }
    )
    finding["deterministic_superfixer_evidence"].update(
        {
            "actionable": True,
            "failed_l2_evidence": True,
            "runner_dead": True,
            "chain_incomplete": True,
        }
    )

    gate = classify_true_stall(finding)

    assert gate["custody_walk"]["L2"]["FIXED"] is False
    assert gate["evidence_sources"]["live_process"]["state"] == "dead"
    assert gate["eligible"] is True


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
    # "No healthy L2" is not the same as "no current L2 context": this
    # current failed episode is sufficient context for the FIXED-axis verdict.
    finding["deterministic_superfixer_evidence"]["absent_or_stale_l2"] = True

    gate = classify_true_stall(finding)

    assert gate["custody_walk"]["L2"]["TRACKED"] is True
    assert gate["custody_walk"]["L2"]["CONTEXT"] is True
    assert gate["custody_walk"]["L2"]["FIXED"] is False
    assert gate["custody_walk"]["L2"]["failure"]["axis"] == "FIXED"


def test_meta_trigger_rejection_is_l2_fixed_axis_with_current_context() -> None:
    finding = _true_stall()
    finding["meta_repair_summary"].update(
        {
            "failed_meta_run_count": 0,
            "missing_meta_run_evidence": False,
            "meta_record_count": 1,
            "meta_run_log_count": 1,
            "meta_run_refs": [
                {
                    "current_episode": True,
                    "failure_code": "meta_repair_trigger_rejected",
                    "trigger_rejected": True,
                    "launch_failure": False,
                }
            ],
        }
    )
    finding["deterministic_superfixer_evidence"]["absent_or_stale_l2"] = True

    gate = classify_true_stall(finding)

    l2 = gate["custody_walk"]["L2"]
    assert l2["TRACKED"] is True
    assert l2["CONTEXT"] is True
    assert l2["FIXED"] is False
    assert l2["failure"]["axis"] == "FIXED"
    assert l2["failure"]["trigger_rejected"] is True


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
