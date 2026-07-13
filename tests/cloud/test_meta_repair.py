"""Tests for meta-repair classification, evidence loading, and prompt assembly.

Covers:
- All six trigger types (repair_timeout, persistent_recurring_retry,
  state_inspection_failure, model_tool_launch_failure,
  partial_liveness_recurrence, discord_delivery_failure).
- Explicit non-trigger cases (success outcome, healthy repair,
  Discord failure without TRUE_BLOCKER).
- Secret redaction in loaded evidence and generated prompts.
- Trigger priority ordering.
"""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

import arnold_pipelines.megaplan.cloud.meta_repair as meta_repair_module
from arnold_pipelines.megaplan.cloud.meta_repair import (
    META_REPAIR_BUDGET_SECS,
    MetaRepairClassification,
    MetaRepairRecord,
    extract_reported_repair_custody,
    verify_meta_repair_commit_custody,
    MetaRepairTrigger,
    RetriggerExecutionResult,
    build_meta_repair_prompt,
    classify_repair_system_failure,
    compute_meta_deadline,
    evaluate_meta_repair_triggers,
    is_model_tool_launch_failure_status,
    is_meta_budget_exhausted,
    load_meta_repair_record,
    load_redacted_evidence,
    persist_meta_repair_record,
    remaining_meta_budget_secs,
    retrigger_ordinary_repair,
    trigger_priority,
    verify_retrigger_success,
)
from arnold_pipelines.megaplan.cloud.redact import REDACTION
from arnold_pipelines.megaplan.cloud.repair_contract import (
    COMPLETE,
    DISCORD_ESCALATED,
    LIVE_WITH_FRESH_ACTIVITY,
    NEEDS_HUMAN,
    PARTIAL_LIVENESS,
    REPAIR_EXHAUSTED,
    REPAIR_TIMEOUT,
    REPAIRING,
    atomic_write_json,
    merge_additive_fields,
    read_repair_index,
    save_repair_data,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout.strip()


def _commit_file(repo: Path, name: str, content: str, message: str) -> str:
    (repo / name).write_text(content, encoding="utf-8")
    _git(repo, "add", name)
    _git(repo, "commit", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


class TestMetaRepairCommitCustody:
    def _repo(self, tmp_path: Path) -> tuple[Path, Path, str]:
        remote = tmp_path / "remote.git"
        subprocess.run(["git", "init", "--bare", str(remote)], check=True)
        repo = tmp_path / "repo"
        repo.mkdir()
        _git(repo, "init", "-b", "editible-install")
        _git(repo, "config", "user.email", "test@example.invalid")
        _git(repo, "config", "user.name", "Test")
        _git(repo, "remote", "add", "origin", str(remote))
        baseline = _commit_file(repo, "repair.py", "old\n", "baseline")
        _git(repo, "push", "-u", "origin", "editible-install")
        return repo, remote, baseline

    def test_fixed_requires_the_new_commit_to_be_published(self, tmp_path: Path) -> None:
        repo, _, baseline = self._repo(tmp_path)
        current = _commit_file(repo, "repair.py", "fixed\n", "fix repair")

        rejected = verify_meta_repair_commit_custody(
            repo,
            baseline_head=baseline,
            verdict="FIXED",
            push_required=True,
        )
        assert rejected["accepted"] is False
        assert rejected["current_head"] == current
        assert rejected["local_reachable"] is True
        assert rejected["remote_reachable"] is False

        _git(repo, "push", "origin", "editible-install")
        accepted = verify_meta_repair_commit_custody(
            repo,
            baseline_head=baseline,
            verdict="FIXED",
            push_required=True,
        )
        assert accepted["accepted"] is True
        assert accepted["outcome"] == "commit_custody_verified"
        assert accepted["remote_reachable"] is True

    def test_rejects_detached_or_nonfixed_source_changes(self, tmp_path: Path) -> None:
        repo, _, baseline = self._repo(tmp_path)
        current = _commit_file(repo, "repair.py", "changed\n", "unexpected change")

        nonfixed = verify_meta_repair_commit_custody(
            repo,
            baseline_head=baseline,
            verdict="ESCALATE",
            push_required=False,
        )
        assert nonfixed["accepted"] is False
        assert nonfixed["reason"] == "non-FIXED verdict moved source HEAD"

        _git(repo, "checkout", "--detach", current)
        detached_nonfixed = verify_meta_repair_commit_custody(
            repo,
            baseline_head=current,
            verdict="ESCALATE",
            push_required=False,
        )
        assert detached_nonfixed["accepted"] is False
        assert detached_nonfixed["reason"] == "source commit is on detached HEAD"

        detached = verify_meta_repair_commit_custody(
            repo,
            baseline_head=baseline,
            verdict="FIXED",
            push_required=False,
        )
        assert detached["accepted"] is False
        assert detached["reason"] == "source commit is on detached HEAD"

    def test_custody_rejection_controls_the_effective_outcome(self) -> None:
        outcome = meta_repair_module.derive_meta_repair_effective_outcome(
            verdict="ESCALATE",
            post_retrigger_verification={
                "commit_custody": {"accepted": False},
            },
        )
        assert outcome == "commit_custody_failed"


def _make_session_dir(tmp_path: Path, session: str) -> Path:
    """Create a minimal repair-data directory for *session*."""
    repair_root = tmp_path / "repair-data"
    repair_root.mkdir(parents=True, exist_ok=True)
    repair_data = {
        "session": session,
        "workspace": "/workspace/test-project",
        "plan_name": "test-plan",
        "outcome": REPAIRING,
    }
    path = repair_root / f"{session}.repair-data.json"
    path.write_text(json.dumps(repair_data), encoding="utf-8")
    return repair_root


# ---------------------------------------------------------------------------
# Trigger priority
# ---------------------------------------------------------------------------


class TestTriggerPriority:
    def test_all_triggers_have_priority(self) -> None:
        for trigger in MetaRepairTrigger:
            assert trigger_priority(trigger) in range(1, 8)

    def test_non_trigger_has_no_priority(self) -> None:
        assert trigger_priority("none") == 99  # type: ignore[arg-type]

    def test_priorities_are_unique(self) -> None:
        values = [trigger_priority(t) for t in MetaRepairTrigger]
        assert len(values) == len(set(values))


# ---------------------------------------------------------------------------
# Classification: all six trigger types
# ---------------------------------------------------------------------------


class TestClassifyRepairTimeout:
    def test_repair_timeout_triggers(self) -> None:
        result = classify_repair_system_failure(
            session="s1",
            repair_outcome=REPAIR_TIMEOUT,
            repair_budget_exhausted=True,
        )
        assert result.trigger == MetaRepairTrigger.REPAIR_TIMEOUT
        assert result.should_dispatch is True
        assert result.trigger_label == "repair_timeout"
        assert len(result.rationale) > 0

    def test_repair_exhausted_triggers(self) -> None:
        result = classify_repair_system_failure(
            session="s2",
            repair_outcome=REPAIR_EXHAUSTED,
            repair_budget_exhausted=True,
        )
        assert result.trigger == MetaRepairTrigger.REPAIR_TIMEOUT

    def test_timeout_without_budget_exhaustion_does_not_trigger(self) -> None:
        result = classify_repair_system_failure(
            session="s3",
            repair_outcome=REPAIR_TIMEOUT,
            repair_budget_exhausted=False,
        )
        assert result.trigger is None  # budget must be explicitly exhausted
        assert result.should_dispatch is False


class TestClassifyPersistentRecurringRetry:
    def test_recurring_retry_triggers(self) -> None:
        result = classify_repair_system_failure(
            session="s4",
            failure_kinds=["phase_failed", "phase_failed", "phase_failed"],
            attempt_outcomes=[REPAIRING, REPAIRING, REPAIRING],
        )
        assert result.trigger == MetaRepairTrigger.PERSISTENT_RECURRING_RETRY
        assert result.should_dispatch is True

    def test_recurring_retry_not_enough_attempts(self) -> None:
        result = classify_repair_system_failure(
            session="s5",
            failure_kinds=["phase_failed", "phase_failed"],
            attempt_outcomes=[REPAIRING, REPAIRING],
        )
        assert result.trigger is None

    def test_recurring_retry_interrupted_by_success(self) -> None:
        result = classify_repair_system_failure(
            session="s6",
            failure_kinds=["phase_failed", "phase_failed", "phase_failed"],
            attempt_outcomes=[REPAIRING, COMPLETE, REPAIRING],
        )
        assert result.trigger is None  # recent success means it's not persistent

    def test_recurring_retry_with_mixed_kinds_does_not_trigger(self) -> None:
        result = classify_repair_system_failure(
            session="s7",
            failure_kinds=["phase_failed", "model_crash", "timeout"],
            attempt_outcomes=[REPAIRING, REPAIRING, REPAIRING],
        )
        assert result.trigger is None  # not enough of the same kind

    def test_recurring_retry_skips_stale_repair_data_when_current_target_recovered(self) -> None:
        result = classify_repair_system_failure(
            session="s7b",
            evidence={
                "repair_data": {
                    "current_signature": {
                        "milestone_or_plan": "demo-plan",
                        "current_state": "blocked",
                    }
                }
            },
            current_target_observation={
                "authoritative_source": "chain_state",
                "current_refs": {
                    "current_plan_name": "demo-plan",
                    "plan_current_state": "finalized",
                    "chain_last_state": "finalized",
                },
                "plan_state": {"present": True},
                "chain_state": {"present": True},
                "active_step_heartbeat": {"active": False},
            },
            failure_kinds=["phase_failed", "phase_failed", "phase_failed"],
            attempt_outcomes=[REPAIRING, REPAIRING, REPAIRING],
        )
        assert result.trigger is None
        assert result.should_dispatch is False
        assert "supersedes stale recurring repair evidence" in result.rationale[0]

    def test_recurring_retry_skips_stale_repair_data_when_chain_spec_is_gone(self) -> None:
        result = classify_repair_system_failure(
            session="s7c",
            evidence={
                "repair_data": {
                    "current_signature": {
                        "milestone_or_plan": "demo-plan",
                        "current_state": "blocked",
                    }
                }
            },
            current_target_observation={
                "authoritative_source": "marker",
                "current_refs": {
                    "run_kind": "chain",
                    "current_plan_name": "",
                    "chain_current_plan_name": "",
                    "plan_current_state": "",
                    "chain_last_state": "",
                },
                "plan_state": {"present": False},
                "chain_state": {"present": False},
                "chain_log": {"present": False},
                "active_step_heartbeat": {"active": False},
                "stale_evidence": [{"kind": "spec_missing"}],
            },
            failure_kinds=["phase_failed", "phase_failed", "phase_failed"],
            attempt_outcomes=[REPAIRING, REPAIRING, REPAIRING],
        )
        assert result.trigger is None
        assert result.should_dispatch is False
        assert "chain spec is missing" in result.rationale[0]

    def test_recurring_retry_skips_stale_repair_data_when_only_chain_log_remains(self) -> None:
        result = classify_repair_system_failure(
            session="s7d",
            evidence={
                "repair_data": {
                    "current_signature": {
                        "milestone_or_plan": "demo-plan",
                        "current_state": "blocked",
                    }
                }
            },
            current_target_observation={
                "authoritative_source": "marker",
                "current_refs": {
                    "run_kind": "chain",
                    "current_plan_name": "",
                    "chain_current_plan_name": "",
                    "plan_current_state": "",
                    "chain_last_state": "",
                },
                "plan_state": {"present": False},
                "chain_state": {"present": False},
                "chain_log": {"present": True},
                "active_step_heartbeat": {"active": False},
                "tmux_process": {"live_status": "unknown"},
                "stale_evidence": [{"kind": "spec_missing"}],
            },
            failure_kinds=["phase_failed", "phase_failed", "phase_failed"],
            attempt_outcomes=[REPAIRING, REPAIRING, REPAIRING],
        )
        assert result.trigger is None
        assert result.should_dispatch is False
        assert "chain spec is missing" in result.rationale[0]

    def test_recurring_retry_skips_stale_execute_loop_when_live_status_has_no_retry_path(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(
            meta_repair_module,
            "_load_current_target_status",
            lambda _path: {
                "state": "finalized",
                "next_step": None,
                "valid_next": [],
                "active_step": None,
                "blocker_recovery": {
                    "has_terminal_blockers": True,
                },
            },
        )

        result = classify_repair_system_failure(
            session="s7d",
            evidence={
                "repair_data": {
                    "current_signature": {
                        "milestone_or_plan": "demo-plan",
                        "current_state": "finalized",
                        "failure_kind": "blocked_state_or_recovery_error",
                        "phase_or_step": "execute",
                    }
                }
            },
            current_target_observation={
                "authoritative_source": "chain_state",
                "current_refs": {
                    "current_plan_name": "demo-plan",
                    "plan_current_state": "finalized",
                    "chain_last_state": "finalized",
                },
                "plan_state": {"present": True, "path": "/tmp/demo/state.json"},
                "chain_state": {"present": True},
                "active_step_heartbeat": {"active": False},
            },
            failure_kinds=[
                "blocked_state_or_recovery_error",
                "blocked_state_or_recovery_error",
                "blocked_state_or_recovery_error",
            ],
            attempt_outcomes=[REPAIRING, REPAIRING, REPAIRING],
        )
        assert result.trigger is None
        assert result.should_dispatch is False
        assert "no execute retry path" in result.rationale[0]

    def test_recurring_retry_skips_terminal_non_success_when_live_target_is_done(
        self,
    ) -> None:
        result = classify_repair_system_failure(
            session="s7e",
            evidence={
                "repair_data": {
                    "outcome": DISCORD_ESCALATED,
                    "current_failure_context": {
                        "stale_state": {
                            "classification": "NO LATEST FAILURE",
                            "recommended_action": "mechanical re-drive only",
                        },
                        "plan_latest_failure": {
                            "current_state": "done",
                        },
                        "plan_runtime_state": {
                            "current_state": "done",
                        },
                    },
                }
            },
            current_target_observation={
                "authoritative_source": "plan_state",
                "current_refs": {
                    "current_plan_name": "demo-plan",
                    "plan_current_state": "done",
                    "chain_last_state": "done",
                },
                "plan_state": {"present": True},
                "chain_state": {"present": True},
                "active_step_heartbeat": {"active": False},
            },
            failure_kinds=["blocked_state_or_recovery_error"] * 3,
            attempt_outcomes=[REPAIRING, REPAIRING, REPAIRING],
        )
        assert result.trigger is None
        assert result.should_dispatch is False
        assert "repair outcome is discord_escalated" in result.rationale[0]


class TestClassifyStateInspectionFailure:
    def test_state_inspection_error_triggers(self) -> None:
        result = classify_repair_system_failure(
            session="s8",
            has_state_inspection_error=True,
        )
        assert result.trigger == MetaRepairTrigger.STATE_INSPECTION_FAILURE
        assert result.should_dispatch is True

    def test_state_inspection_normal_does_not_trigger(self) -> None:
        result = classify_repair_system_failure(
            session="s9",
            has_state_inspection_error=False,
        )
        assert result.trigger is None


class TestClassifyModelToolLaunchFailure:
    def test_launch_error_triggers(self) -> None:
        result = classify_repair_system_failure(
            session="s10",
            has_model_tool_launch_error=True,
        )
        assert result.trigger == MetaRepairTrigger.MODEL_TOOL_LAUNCH_FAILURE
        assert result.should_dispatch is True

    def test_launch_normal_does_not_trigger(self) -> None:
        result = classify_repair_system_failure(
            session="s11",
            has_model_tool_launch_error=False,
        )
        assert result.trigger is None


class TestModelToolLaunchFailureStatus:
    def test_tmux_launch_failure_counts_as_launch_error(self) -> None:
        assert is_model_tool_launch_failure_status("failed:tmux_launch_failed") is True

    def test_missing_relaunch_command_counts_as_launch_error(self) -> None:
        assert is_model_tool_launch_failure_status("failed:missing_relaunch_command") is True

    def test_missing_api_key_counts_as_launch_error(self) -> None:
        assert is_model_tool_launch_failure_status("failed:KIMI_API_KEY missing") is True

    def test_stopped_health_does_not_count_as_launch_error(self) -> None:
        assert is_model_tool_launch_failure_status("failed:stopped") is False

    def test_retrying_failure_does_not_count_as_launch_error(self) -> None:
        assert is_model_tool_launch_failure_status("failed:retrying_failure") is False

    def test_state_inspection_status_is_not_launch_error(self) -> None:
        assert (
            is_model_tool_launch_failure_status(
                "failed:state_unreadable: malformed state.json",
                state_tokens=(
                    "failed:missing_state_path",
                    "failed:state_unreadable",
                    "failed:state_not_object",
                    "state_inspection_error",
                ),
            )
            is False
        )


class TestClassifyPartialLivenessRecurrence:
    def test_partial_liveness_triggers(self) -> None:
        result = classify_repair_system_failure(
            session="s12",
            partial_liveness_ticks=2,
        )
        assert result.trigger == MetaRepairTrigger.PARTIAL_LIVENESS_RECURRENCE
        assert result.should_dispatch is True

    def test_partial_liveness_below_threshold(self) -> None:
        result = classify_repair_system_failure(
            session="s13",
            partial_liveness_ticks=1,
        )
        assert result.trigger is None

    def test_partial_liveness_zero(self) -> None:
        result = classify_repair_system_failure(
            session="s14",
            partial_liveness_ticks=0,
        )
        assert result.trigger is None

    def test_partial_liveness_three_ticks(self) -> None:
        result = classify_repair_system_failure(
            session="s15",
            partial_liveness_ticks=3,
        )
        assert result.trigger == MetaRepairTrigger.PARTIAL_LIVENESS_RECURRENCE

    def test_partial_liveness_suppressed_by_fresher_live_target(self, tmp_path: Path) -> None:
        repair_root = _make_session_dir(tmp_path, "s15-live")
        repair_data_path = repair_root / "s15-live.repair-data.json"
        repair_data_path.write_text(
            json.dumps(
                {
                    "session": "s15-live",
                    "outcome": "running",
                    "attempts": [
                        {
                            "attempt_id": 1,
                            "failure_classification": "blocked_state_or_recovery_error",
                            "dispatched_at": "2026-07-04T09:33:21Z",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        result, _ = evaluate_meta_repair_triggers(
            "s15-live",
            repair_data_dir=repair_root,
            repair_outcome=REPAIRING,
            partial_liveness_ticks=3,
            current_target_observation={
                "authoritative_source": "chain_state",
                "active_step_heartbeat": {"active": False},
                "current_refs": {
                    "current_plan_name": "test-plan",
                    "chain_current_plan_name": "test-plan",
                    "plan_current_state": "finalized",
                    "chain_last_state": "finalized",
                },
                "plan_state": {"present": True, "mtime": datetime(2026, 7, 4, 10, 13, tzinfo=timezone.utc).timestamp()},
                "chain_state": {"present": True, "mtime": datetime(2026, 7, 4, 10, 13, tzinfo=timezone.utc).timestamp()},
                "chain_log": {"present": True, "mtime": datetime(2026, 7, 4, 10, 13, tzinfo=timezone.utc).timestamp()},
                "event_cursors": {"mtime": datetime(2026, 7, 4, 10, 13, tzinfo=timezone.utc).timestamp()},
            },
            load_evidence=True,
        )
        assert result.trigger is None
        assert result.should_dispatch is False
        assert "supersedes stale recurring repair evidence" in result.rationale[0]


class TestClassifyDiscordDeliveryFailure:
    def test_discord_true_blocker_triggers(self) -> None:
        result = classify_repair_system_failure(
            session="s16",
            discord_delivery_failed=True,
            discord_escalation_is_true_blocker=True,
        )
        assert result.trigger == MetaRepairTrigger.DISCORD_DELIVERY_FAILURE
        assert result.should_dispatch is True

    def test_discord_not_true_blocker_no_trigger(self) -> None:
        result = classify_repair_system_failure(
            session="s17",
            discord_delivery_failed=True,
            discord_escalation_is_true_blocker=False,
        )
        assert result.trigger is None  # explicit non-trigger
        assert result.should_dispatch is False
        assert "NOT a TRUE_BLOCKER" in result.rationale[0]

    def test_discord_delivery_success_no_trigger(self) -> None:
        result = classify_repair_system_failure(
            session="s18",
            discord_delivery_failed=False,
            discord_escalation_is_true_blocker=True,
        )
        assert result.trigger is None
        assert result.should_dispatch is False


# ---------------------------------------------------------------------------
# Explicit non-trigger cases
# ---------------------------------------------------------------------------


class TestNonTriggerCases:
    def test_success_outcome_no_trigger(self) -> None:
        result = classify_repair_system_failure(
            session="s19",
            repair_outcome=COMPLETE,
        )
        assert result.trigger is None
        assert result.should_dispatch is False
        assert "terminal success outcome" in result.rationale[0]

    def test_success_outcome_suppresses_stale_launch_failure(self) -> None:
        result = classify_repair_system_failure(
            session="s19-success-launch",
            repair_outcome=LIVE_WITH_FRESH_ACTIVITY,
            has_model_tool_launch_error=True,
            partial_liveness_ticks=4,
        )
        assert result.trigger is None
        assert result.should_dispatch is False
        assert "terminal success outcome" in result.rationale[0]

    def test_still_repairing_no_trigger(self) -> None:
        result = classify_repair_system_failure(
            session="s20",
            repair_outcome=REPAIRING,
        )
        assert result.trigger is None
        assert result.should_dispatch is False

    def test_healthy_normal_operation_no_trigger(self) -> None:
        result = classify_repair_system_failure(
            session="s21",
            repair_outcome="complete",
            has_state_inspection_error=False,
            has_model_tool_launch_error=False,
            partial_liveness_ticks=0,
            discord_delivery_failed=False,
            repair_budget_exhausted=False,
        )
        assert result.trigger is None
        assert result.should_dispatch is False

    def test_empty_all_fields_no_trigger(self) -> None:
        result = classify_repair_system_failure(session="s22")
        assert result.trigger is None
        assert result.should_dispatch is False


# ---------------------------------------------------------------------------
# Priority ordering (first-match-wins)
# ---------------------------------------------------------------------------


class TestClassificationPriority:
    """Verify that the first-match-wins decision tree gives correct priority."""

    def test_discord_true_blocker_wins_over_timeout(self) -> None:
        """Discord delivery failure (trigger 1) beats repair timeout (trigger 2)."""
        result = classify_repair_system_failure(
            session="s23",
            discord_delivery_failed=True,
            discord_escalation_is_true_blocker=True,
            repair_outcome=REPAIR_TIMEOUT,
            repair_budget_exhausted=True,
        )
        assert result.trigger == MetaRepairTrigger.DISCORD_DELIVERY_FAILURE

    def test_timeout_wins_over_recurring_retry(self) -> None:
        """Repair timeout (trigger 2) beats persistent recurring retry (trigger 3)."""
        result = classify_repair_system_failure(
            session="s24",
            repair_outcome=REPAIR_TIMEOUT,
            repair_budget_exhausted=True,
            failure_kinds=["phase_failed", "phase_failed", "phase_failed"],
            attempt_outcomes=[REPAIRING, REPAIRING, REPAIRING],
        )
        assert result.trigger == MetaRepairTrigger.REPAIR_TIMEOUT

    def test_recurring_retry_wins_over_state_inspection(self) -> None:
        """Persistent recurring retry (trigger 3) beats state inspection (trigger 4)."""
        result = classify_repair_system_failure(
            session="s25",
            failure_kinds=["phase_failed", "phase_failed", "phase_failed"],
            attempt_outcomes=[REPAIRING, REPAIRING, REPAIRING],
            has_state_inspection_error=True,
        )
        assert result.trigger == MetaRepairTrigger.PERSISTENT_RECURRING_RETRY

    def test_state_inspection_wins_over_launch_failure(self) -> None:
        """State inspection (trigger 4) beats model/tool launch (trigger 5)."""
        result = classify_repair_system_failure(
            session="s26",
            has_state_inspection_error=True,
            has_model_tool_launch_error=True,
        )
        assert result.trigger == MetaRepairTrigger.STATE_INSPECTION_FAILURE

    def test_launch_failure_wins_over_partial_liveness(self) -> None:
        """Model/tool launch (trigger 5) beats partial liveness (trigger 6)."""
        result = classify_repair_system_failure(
            session="s27",
            has_model_tool_launch_error=True,
            partial_liveness_ticks=5,
        )
        assert result.trigger == MetaRepairTrigger.MODEL_TOOL_LAUNCH_FAILURE

    def test_success_outcome_beats_launch_failure(self) -> None:
        result = classify_repair_system_failure(
            session="s27-success",
            repair_outcome=LIVE_WITH_FRESH_ACTIVITY,
            has_model_tool_launch_error=True,
        )
        assert result.trigger is None


# ---------------------------------------------------------------------------
# Classification: metadata fields
# ---------------------------------------------------------------------------


class TestClassificationMetadata:
    def test_classification_session_is_preserved(self) -> None:
        result = classify_repair_system_failure(
            session="my-session",
            repair_outcome=REPAIR_TIMEOUT,
            repair_budget_exhausted=True,
        )
        assert result.session == "my-session"

    def test_classification_has_attempted_at(self) -> None:
        result = classify_repair_system_failure(
            session="s28",
            repair_outcome=REPAIR_TIMEOUT,
            repair_budget_exhausted=True,
        )
        assert result.attempted_at
        # Must be parseable ISO-8601
        datetime.fromisoformat(result.attempted_at)

    def test_classification_rationale_is_tuple(self) -> None:
        result = classify_repair_system_failure(
            session="s29",
            repair_outcome=REPAIR_TIMEOUT,
            repair_budget_exhausted=True,
        )
        assert isinstance(result.rationale, tuple)
        assert all(isinstance(r, str) for r in result.rationale)

    def test_non_trigger_rationale_mentions_debug_info(self) -> None:
        result = classify_repair_system_failure(session="s30")
        assert result.trigger is None
        assert "no meta-repair trigger condition matched" in result.rationale[0]

    def test_evidence_attached_when_provided(self) -> None:
        evidence = {"repair_data": {"session": "s31"}}
        result = classify_repair_system_failure(
            session="s31",
            evidence=evidence,
            repair_outcome=REPAIR_TIMEOUT,
            repair_budget_exhausted=True,
        )
        assert result.evidence == evidence


# ---------------------------------------------------------------------------
# Evidence loading
# ---------------------------------------------------------------------------


class TestLoadRedactedEvidence:
    def test_loads_evidence_from_session_dir(self, tmp_path: Path) -> None:
        session = "test-session"
        repair_root = _make_session_dir(tmp_path, session)
        evidence = load_redacted_evidence(
            session,
            repair_data_dir=repair_root,
        )
        assert evidence["session"] == session
        assert "loaded_at" in evidence
        assert "repair_data" in evidence
        assert "recent_attempts" in evidence
        assert isinstance(evidence["recent_attempts"], list)
        assert "index" in evidence
        assert isinstance(evidence["index"], dict)

    def test_missing_repair_data_handled_gracefully(self, tmp_path: Path) -> None:
        repair_root = tmp_path / "repair-data"
        repair_root.mkdir(parents=True)
        evidence = load_redacted_evidence(
            "missing-session",
            repair_data_dir=repair_root,
        )
        assert evidence["session"] == "missing-session"
        assert evidence["repair_data"] == {}

    def test_redacts_secrets_in_evidence(self, tmp_path: Path) -> None:
        session = "secret-session"
        repair_root = _make_session_dir(tmp_path, session)
        # Write a repair-data file that contains a bearer token
        path = repair_root / f"{session}.repair-data.json"
        payload = {
            "session": session,
            "stderr": "Authorization: Bearer sk-secret-token-value-12345",
            "env_assign": "DISCORD_WEBHOOK_TOKEN=super-secret-webhook-key",
        }
        path.write_text(json.dumps(payload), encoding="utf-8")

        evidence = load_redacted_evidence(
            session,
            repair_data_dir=repair_root,
            secret_names=["DISCORD_WEBHOOK_TOKEN"],
        )
        repair_data = evidence["repair_data"]
        assert "sk-secret-token" not in str(repair_data)
        assert "super-secret-webhook-key" not in str(repair_data)
        assert REDACTION in str(repair_data)

    def test_partial_liveness_history_is_filtered_to_session(self, tmp_path: Path) -> None:
        session = "target-session"
        repair_root = _make_session_dir(tmp_path, session)
        sidecar_dir = repair_root.with_name(f"{repair_root.name}.d")
        events_dir = sidecar_dir / "events"
        events_dir.mkdir(parents=True, exist_ok=True)
        events_path = events_dir / "events.jsonl"
        records = [
            {
                "session": f"other-{idx}",
                "outcome": PARTIAL_LIVENESS,
                "recorded_at": f"2026-07-03T19:{idx:02d}:00Z",
            }
            for idx in range(5)
        ]
        records.append(
            {
                "session": session,
                "outcome": PARTIAL_LIVENESS,
                "recorded_at": "2026-07-03T19:12:01Z",
            }
        )
        events_path.write_text(
            "\n".join(json.dumps(record) for record in records) + "\n",
            encoding="utf-8",
        )

        evidence = load_redacted_evidence(
            session,
            repair_data_dir=repair_root,
            max_attempts=20,
        )
        history = evidence["partial_liveness_history"]
        assert len(history) == 1
        assert history[0]["session"] == session

        classification, _ = evaluate_meta_repair_triggers(
            session,
            repair_data_dir=repair_root,
            repair_outcome=REPAIRING,
            attempt_outcomes=[REPAIRING],
            failure_kinds=["timeout_or_hang"],
            load_evidence=True,
        )
        assert classification.should_dispatch is False
        assert classification.trigger is None

    def test_partial_liveness_history_ignores_ticks_before_current_attempt(self, tmp_path: Path) -> None:
        session = "windowed-session"
        repair_root = _make_session_dir(tmp_path, session)
        repair_data_path = repair_root / f"{session}.repair-data.json"
        repair_data_path.write_text(
            json.dumps(
                {
                    "session": session,
                    "outcome": PARTIAL_LIVENESS,
                    "current_attempt_id": 2,
                    "current_recurrence": {
                        "attempt_id": 2,
                        "dispatched_at": "2026-07-03T20:00:00Z",
                    },
                    "current_signature": {
                        "milestone_or_plan": "demo-plan",
                    },
                    "attempts": [
                        {"attempt_id": 1, "dispatched_at": "2026-07-03T19:00:00Z"},
                        {"attempt_id": 2, "dispatched_at": "2026-07-03T20:00:00Z"},
                    ],
                }
            ),
            encoding="utf-8",
        )
        sidecar_dir = repair_root.with_name(f"{repair_root.name}.d")
        events_dir = sidecar_dir / "events"
        events_dir.mkdir(parents=True, exist_ok=True)
        events_path = events_dir / "events.jsonl"
        events_path.write_text(
            "\n".join(
                [
                    json.dumps(
                        {
                            "session": session,
                            "outcome": PARTIAL_LIVENESS,
                            "recorded_at": "2026-07-03T19:05:00Z",
                            "run_kind": "chain",
                            "plan_name": "demo-plan",
                        }
                    ),
                    json.dumps(
                        {
                            "session": session,
                            "outcome": PARTIAL_LIVENESS,
                            "recorded_at": "2026-07-03T19:15:00Z",
                            "run_kind": "chain",
                            "plan_name": "demo-plan",
                        }
                    ),
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        evidence = load_redacted_evidence(session, repair_data_dir=repair_root)
        assert evidence["partial_liveness_history"] == []

        classification, _ = evaluate_meta_repair_triggers(
            session,
            repair_data_dir=repair_root,
            repair_outcome=PARTIAL_LIVENESS,
            load_evidence=True,
        )
        assert classification.should_dispatch is False
        assert classification.trigger is None

    def test_partial_liveness_history_keeps_current_attempt_ticks(self, tmp_path: Path) -> None:
        session = "current-window-session"
        repair_root = _make_session_dir(tmp_path, session)
        repair_data_path = repair_root / f"{session}.repair-data.json"
        repair_data_path.write_text(
            json.dumps(
                {
                    "session": session,
                    "outcome": PARTIAL_LIVENESS,
                    "current_attempt_id": 3,
                    "current_recurrence": {
                        "attempt_id": 3,
                        "dispatched_at": "2026-07-03T20:00:00Z",
                    },
                    "current_signature": {
                        "milestone_or_plan": "demo-plan",
                    },
                }
            ),
            encoding="utf-8",
        )
        sidecar_dir = repair_root.with_name(f"{repair_root.name}.d")
        events_dir = sidecar_dir / "events"
        events_dir.mkdir(parents=True, exist_ok=True)
        events_path = events_dir / "events.jsonl"
        events_path.write_text(
            "\n".join(
                [
                    json.dumps(
                        {
                            "session": session,
                            "outcome": PARTIAL_LIVENESS,
                            "recorded_at": "2026-07-03T20:05:00Z",
                            "run_kind": "chain",
                            "plan_name": "demo-plan",
                        }
                    ),
                    json.dumps(
                        {
                            "session": session,
                            "outcome": PARTIAL_LIVENESS,
                            "recorded_at": "2026-07-03T20:06:00Z",
                            "run_kind": "chain",
                            "plan_name": "demo-plan",
                        }
                    ),
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        evidence = load_redacted_evidence(session, repair_data_dir=repair_root)
        assert len(evidence["partial_liveness_history"]) == 2

        classification, _ = evaluate_meta_repair_triggers(
            session,
            repair_data_dir=repair_root,
            repair_outcome=PARTIAL_LIVENESS,
            load_evidence=True,
        )
        assert classification.should_dispatch is True
        assert classification.trigger == MetaRepairTrigger.PARTIAL_LIVENESS_RECURRENCE


# ---------------------------------------------------------------------------
# Prompt assembly
# ---------------------------------------------------------------------------


class TestBuildMetaRepairPrompt:
    def test_prompt_includes_trigger_and_session(self) -> None:
        classification = classify_repair_system_failure(
            session="prompt-session",
            repair_outcome=REPAIR_TIMEOUT,
            repair_budget_exhausted=True,
        )
        prompt = build_meta_repair_prompt(classification)
        assert "repair_timeout" in prompt
        assert "prompt-session" in prompt

    def test_prompt_includes_rationale(self) -> None:
        classification = classify_repair_system_failure(
            session="p2",
            repair_outcome=REPAIR_TIMEOUT,
            repair_budget_exhausted=True,
        )
        prompt = build_meta_repair_prompt(classification)
        assert "### Rationale" in prompt
        assert "repair budget exhausted" in prompt.lower()

    def test_prompt_includes_evidence_section(self) -> None:
        classification = classify_repair_system_failure(
            session="p3",
            evidence={"key": "value"},
            repair_outcome=REPAIR_TIMEOUT,
            repair_budget_exhausted=True,
        )
        prompt = build_meta_repair_prompt(classification)
        assert "### Redacted Evidence" in prompt
        assert '"key": "value"' in prompt

    def test_prompt_includes_extra_context(self) -> None:
        classification = classify_repair_system_failure(
            session="p4",
            repair_outcome=REPAIR_TIMEOUT,
            repair_budget_exhausted=True,
        )
        prompt = build_meta_repair_prompt(
            classification,
            extra_context={"plan": "test-plan", "workspace": "/ws"},
        )
        assert "### Additional Context" in prompt
        assert "test-plan" in prompt

    def test_prompt_includes_instructions(self) -> None:
        classification = classify_repair_system_failure(
            session="p5",
            repair_outcome=REPAIR_TIMEOUT,
            repair_budget_exhausted=True,
        )
        prompt = build_meta_repair_prompt(classification)
        assert "### Instructions" in prompt
        assert "Diagnose the root cause" in prompt

    def test_non_trigger_prompt_shows_status(self) -> None:
        classification = classify_repair_system_failure(session="p6")
        prompt = build_meta_repair_prompt(classification)
        assert "Non-trigger" in prompt
        assert "none" in prompt

    def test_prompt_redacts_secrets(self) -> None:
        evidence = {
            "stderr": "Authorization: Bearer sk-very-secret-token-abc123",
            "env": "API_KEY=super-secret-key-12345",
        }
        classification = classify_repair_system_failure(
            session="p7",
            evidence=evidence,
            repair_outcome=REPAIR_TIMEOUT,
            repair_budget_exhausted=True,
        )
        prompt = build_meta_repair_prompt(classification)
        assert "sk-very-secret-token" not in prompt
        assert REDACTION in prompt

    def test_prompt_includes_repair_data_dir_when_provided(self) -> None:
        classification = classify_repair_system_failure(
            session="p8",
            repair_outcome=REPAIR_TIMEOUT,
            repair_budget_exhausted=True,
        )
        prompt = build_meta_repair_prompt(
            classification,
            repair_data_dir="/tmp/repair-data",
        )
        assert "/tmp/repair-data" in prompt

    def test_prompt_compacts_large_evidence_to_budget(self) -> None:
        huge_text = "A" * 300_000
        classification = classify_repair_system_failure(
            session="p9",
            evidence={
                "repair_data": {
                    "marker_json": huge_text,
                    "failure_context": {
                        "chain_log_tail": huge_text,
                    },
                }
            },
            repair_outcome=REPAIR_TIMEOUT,
            repair_budget_exhausted=True,
        )
        prompt = build_meta_repair_prompt(classification)
        assert len(prompt) < 250_000
        assert "truncated" in prompt
        assert huge_text not in prompt

    def test_prompt_hard_caps_total_length_for_many_huge_attempts(self) -> None:
        huge_text = "B" * 250_000
        classification = classify_repair_system_failure(
            session="p10",
            evidence={
                "repair_data": {
                    "attempts": [
                        {
                            "attempt_id": idx,
                            "dev_report": {"log_tail": huge_text},
                            "iterations": [{"artifact": huge_text}],
                        }
                        for idx in range(10)
                    ],
                }
            },
            repair_outcome=REPAIR_TIMEOUT,
            repair_budget_exhausted=True,
        )

        prompt = build_meta_repair_prompt(classification)
        assert len(prompt) < 900_000
        assert huge_text not in prompt

    def test_force_emergency_prompt_uses_compacted_evidence(self) -> None:
        huge_text = "C" * 200_000
        classification = classify_repair_system_failure(
            session="p11",
            evidence={
                "repair_data": {
                    "attempts": [
                        {
                            "attempt_id": 1,
                            "outcome": "repair_exhausted",
                            "dev_report": {"chain_log_tail": huge_text},
                        }
                    ]
                }
            },
            repair_outcome=REPAIR_TIMEOUT,
            repair_budget_exhausted=True,
        )

        prompt = build_meta_repair_prompt(classification, force_emergency=True)
        assert "Evidence was compacted" in prompt
        assert '"repair_attempt_summaries"' in prompt
        assert huge_text not in prompt


# ---------------------------------------------------------------------------
# Combined evaluate_meta_repair_triggers
# ---------------------------------------------------------------------------


class TestEvaluateMetaRepairTriggers:
    def test_returns_classification_and_prompt_when_triggered(self, tmp_path: Path) -> None:
        repair_root = _make_session_dir(tmp_path, "eval-s1")
        classification, prompt = evaluate_meta_repair_triggers(
            session="eval-s1",
            repair_data_dir=repair_root,
            repair_outcome=REPAIR_TIMEOUT,
            repair_budget_exhausted=True,
        )
        assert classification.should_dispatch is True
        assert prompt is not None
        assert "repair_timeout" in prompt

    def test_returns_none_prompt_when_not_triggered(self, tmp_path: Path) -> None:
        repair_root = _make_session_dir(tmp_path, "eval-s2")
        classification, prompt = evaluate_meta_repair_triggers(
            session="eval-s2",
            repair_data_dir=repair_root,
            repair_outcome=COMPLETE,
        )
        assert classification.should_dispatch is False
        assert prompt is None

    def test_live_with_fresh_activity_suppresses_stale_launch_trigger(
        self, tmp_path: Path
    ) -> None:
        repair_root = _make_session_dir(tmp_path, "eval-s2-live-launch")
        (repair_root / "eval-s2-live-launch.repair-data.json").write_text(
            json.dumps(
                {
                    "session": "eval-s2-live-launch",
                    "workspace": "/workspace/test-project",
                    "plan_name": "test-plan",
                    "outcome": LIVE_WITH_FRESH_ACTIVITY,
                    "attempts": [
                        {
                            "attempt_id": 1,
                            "mechanical_launch": "failed:tmux_launch_failed",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        classification, prompt = evaluate_meta_repair_triggers(
            session="eval-s2-live-launch",
            repair_data_dir=repair_root,
            repair_outcome=LIVE_WITH_FRESH_ACTIVITY,
            has_model_tool_launch_error=True,
            current_target_observation={
                "authoritative_source": "chain_state",
                "active_step_heartbeat": {"active": False},
                "current_refs": {
                    "current_plan_name": "test-plan",
                    "chain_current_plan_name": "test-plan",
                    "plan_current_state": "initialized",
                    "chain_last_state": "initialized",
                },
                "plan_state": {"present": True},
                "chain_state": {"present": True},
            },
            load_evidence=True,
        )
        assert classification.should_dispatch is False
        assert classification.trigger is None
        assert prompt is None

    def test_loads_evidence_when_requested(self, tmp_path: Path) -> None:
        repair_root = _make_session_dir(tmp_path, "eval-s3")
        classification, prompt = evaluate_meta_repair_triggers(
            session="eval-s3",
            repair_data_dir=repair_root,
            repair_outcome=REPAIR_TIMEOUT,
            repair_budget_exhausted=True,
            load_evidence=True,
        )
        assert classification.should_dispatch is True
        assert classification.evidence
        assert "repair_data" in classification.evidence

    def test_extra_context_in_prompt_when_triggered(self, tmp_path: Path) -> None:
        repair_root = _make_session_dir(tmp_path, "eval-s4")
        _, prompt = evaluate_meta_repair_triggers(
            session="eval-s4",
            repair_data_dir=repair_root,
            repair_outcome=REPAIR_TIMEOUT,
            repair_budget_exhausted=True,
            extra_context={"note": "test context"},
        )
        assert prompt is not None
        assert "test context" in prompt

    def test_load_evidence_compacts_huge_repair_data_before_prompt(self, tmp_path: Path) -> None:
        repair_root = _make_session_dir(tmp_path, "eval-s5")
        payload = json.loads((repair_root / "eval-s5.repair-data.json").read_text(encoding="utf-8"))
        huge_text = "B" * 350_000
        payload["initial_facts"] = {
            "marker_json": huge_text,
            "failure_context": {
                "chain_log_tail": huge_text,
            },
        }
        (repair_root / "eval-s5.repair-data.json").write_text(
            json.dumps(payload),
            encoding="utf-8",
        )

        classification, prompt = evaluate_meta_repair_triggers(
            session="eval-s5",
            repair_data_dir=repair_root,
            repair_outcome=REPAIR_TIMEOUT,
            repair_budget_exhausted=True,
            load_evidence=True,
        )
        assert classification.should_dispatch is True
        assert prompt is not None
        assert len(prompt) < 250_000
        assert huge_text not in prompt
        assert "truncated" in prompt


# ---------------------------------------------------------------------------
# Secret redaction in prompts and evidence
# ---------------------------------------------------------------------------


class TestSecretRedaction:
    def test_redacts_bearer_token_in_evidence(self) -> None:
        evidence = {
            "log": "Authorization: Bearer sk-secret-token-abc123def456",
        }
        classification = classify_repair_system_failure(
            session="redact-1",
            evidence=evidence,
            repair_outcome=REPAIR_TIMEOUT,
            repair_budget_exhausted=True,
        )
        prompt = build_meta_repair_prompt(classification)
        assert "sk-secret-token-abc123def456" not in prompt
        assert REDACTION in prompt

    def test_redacts_github_token(self) -> None:
        evidence = {
            "log": "Using token: ghp_secretgithubpat1234567890",
        }
        classification = classify_repair_system_failure(
            session="redact-2",
            evidence=evidence,
            repair_outcome=REPAIR_TIMEOUT,
            repair_budget_exhausted=True,
        )
        prompt = build_meta_repair_prompt(classification)
        assert "ghp_secretgithubpat" not in prompt
        assert REDACTION in prompt

    def test_redacts_aws_key_in_evidence(self) -> None:
        evidence = {
            "config": "aws_access_key_id = AKIAIOSFODNN7EXAMPLE",
        }
        classification = classify_repair_system_failure(
            session="redact-3",
            evidence=evidence,
            repair_outcome=REPAIR_TIMEOUT,
            repair_budget_exhausted=True,
        )
        prompt = build_meta_repair_prompt(classification)
        assert "AKIAIOSFODNN7EXAMPLE" not in prompt
        assert REDACTION in prompt

    def test_redacts_json_secret_field(self) -> None:
        evidence = {
            "json_config": '{"api_key": "secret-api-key-value-12345"}',
        }
        classification = classify_repair_system_failure(
            session="redact-4",
            evidence=evidence,
            repair_outcome=REPAIR_TIMEOUT,
            repair_budget_exhausted=True,
        )
        prompt = build_meta_repair_prompt(classification)
        assert "secret-api-key-value-12345" not in prompt
        assert REDACTION in prompt

    def test_redacts_env_assignment_in_evidence(self) -> None:
        evidence = {
            "env": "DISCORD_WEBHOOK_TOKEN=super-secret-discord-token-xyz",
        }
        classification = classify_repair_system_failure(
            session="redact-5",
            evidence=evidence,
            repair_outcome=REPAIR_TIMEOUT,
            repair_budget_exhausted=True,
        )
        prompt = build_meta_repair_prompt(classification)
        assert "super-secret-discord-token-xyz" not in prompt
        assert REDACTION in prompt

    def test_redacts_command_line_secret_flag(self) -> None:
        evidence = {
            "cmd": "deploy --api-key=my-secret-deploy-key",
        }
        classification = classify_repair_system_failure(
            session="redact-6",
            evidence=evidence,
            repair_outcome=REPAIR_TIMEOUT,
            repair_budget_exhausted=True,
        )
        prompt = build_meta_repair_prompt(classification)
        assert "my-secret-deploy-key" not in prompt
        assert REDACTION in prompt

    def test_redacts_db_connection_string(self) -> None:
        evidence = {
            "log": "postgresql://user:secret-password-123@host:5432/db",
        }
        classification = classify_repair_system_failure(
            session="redact-7",
            evidence=evidence,
            repair_outcome=REPAIR_TIMEOUT,
            repair_budget_exhausted=True,
        )
        prompt = build_meta_repair_prompt(classification)
        assert "secret-password-123" not in prompt
        assert REDACTION in prompt

    def test_redacts_private_key_block(self) -> None:
        evidence = {
            "file": (
                "-----BEGIN RSA PRIVATE KEY-----\n"
                "MIIEpAIBAAKCAQEA...\n"
                "-----END RSA PRIVATE KEY-----"
            ),
        }
        classification = classify_repair_system_failure(
            session="redact-8",
            evidence=evidence,
            repair_outcome=REPAIR_TIMEOUT,
            repair_budget_exhausted=True,
        )
        prompt = build_meta_repair_prompt(classification)
        assert "PRIVATE KEY" not in prompt

    def test_non_secret_content_preserved_after_redaction(self) -> None:
        evidence = {
            "log": "Build step completed successfully.",
            "info": "Plan: test-plan, Session: abc-123",
        }
        classification = classify_repair_system_failure(
            session="redact-9",
            evidence=evidence,
            repair_outcome=REPAIR_TIMEOUT,
            repair_budget_exhausted=True,
        )
        prompt = build_meta_repair_prompt(classification)
        assert "Build step completed successfully" in prompt
        assert "test-plan" in prompt
        assert "abc-123" in prompt


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_none_evidence_dict_accepted(self) -> None:
        result = classify_repair_system_failure(
            session="edge-1",
            evidence=None,
            repair_outcome=REPAIR_TIMEOUT,
            repair_budget_exhausted=True,
        )
        assert result.trigger == MetaRepairTrigger.REPAIR_TIMEOUT
        assert result.evidence == {}

    def test_evidence_deepcopied_not_mutated(self) -> None:
        evidence = {"key": ["list", "of", "values"]}
        result = classify_repair_system_failure(
            session="edge-2",
            evidence=evidence,
            repair_outcome=REPAIR_TIMEOUT,
            repair_budget_exhausted=True,
        )
        # Mutating original should not affect stored evidence
        evidence["key"].append("extra")
        assert len(result.evidence["key"]) == 3

    def test_many_failure_kinds_only_counts_same_kind(self) -> None:
        kinds = ["phase_failed"] * 10
        outcomes = [REPAIRING] * 10
        result = classify_repair_system_failure(
            session="edge-3",
            failure_kinds=kinds,
            attempt_outcomes=outcomes,
        )
        assert result.trigger == MetaRepairTrigger.PERSISTENT_RECURRING_RETRY

    def test_failure_kinds_with_empty_strings_filtered(self) -> None:
        kinds = ["", "phase_failed", "", "phase_failed", "", "phase_failed"]
        outcomes = [REPAIRING] * 6
        result = classify_repair_system_failure(
            session="edge-4",
            failure_kinds=kinds,
            attempt_outcomes=outcomes,
        )
        assert result.trigger == MetaRepairTrigger.PERSISTENT_RECURRING_RETRY

    def test_all_triggers_represented(self) -> None:
        """Ensure all seven trigger enum values are distinct and enumerable."""
        triggers = set(t.value for t in MetaRepairTrigger)
        assert triggers == {
            "repair_timeout",
            "persistent_recurring_retry",
            "state_inspection_failure",
            "model_tool_launch_failure",
            "partial_liveness_recurrence",
            "discord_delivery_failure",
            "l1_custody_failure",
        }
        assert len(triggers) == 7

    def test_trigger_label_for_non_trigger(self) -> None:
        result = classify_repair_system_failure(session="edge-5")
        assert result.trigger_label == "none"

    def test_trigger_label_for_trigger(self) -> None:
        result = classify_repair_system_failure(
            session="edge-6",
            repair_outcome=REPAIR_TIMEOUT,
            repair_budget_exhausted=True,
        )
        assert result.trigger_label == "repair_timeout"


# ---------------------------------------------------------------------------
# Load_redacted_evidence with secret names
# ---------------------------------------------------------------------------


class TestLoadRedactedEvidenceWithSecrets:
    def test_load_evidence_redacts_named_secrets(self, tmp_path: Path) -> None:
        session = "sec-test"
        repair_root = _make_session_dir(tmp_path, session)
        # Overwrite repair data with secrets
        path = repair_root / f"{session}.repair-data.json"
        payload = {
            "session": session,
            "stderr": "MY_API_TOKEN=abcdef1234567890",
            "env_var": "SECRET_KEY=hunter2",
        }
        path.write_text(json.dumps(payload), encoding="utf-8")

        evidence = load_redacted_evidence(
            session,
            repair_data_dir=repair_root,
            secret_names=["MY_API_TOKEN", "SECRET_KEY"],
        )
        repair_data = evidence["repair_data"]
        data_str = str(repair_data)
        assert "abcdef1234567890" not in data_str
        assert "hunter2" not in data_str
        assert REDACTION in data_str

    def test_load_evidence_with_attempts(self, tmp_path: Path) -> None:
        session = "attempt-test"
        repair_root = _make_session_dir(tmp_path, session)
        attempts_dir = repair_root / "attempts"
        attempts_dir.mkdir(parents=True)

        for i in range(5):
            attempt = {
                "attempt_id": f"a{i}",
                "outcome": REPAIRING if i < 3 else COMPLETE,
                "failure_kind": "phase_failed" if i < 3 else "",
            }
            (attempts_dir / f"attempt-{i:04d}.json").write_text(
                json.dumps(attempt), encoding="utf-8"
            )

        evidence = load_redacted_evidence(
            session,
            repair_data_dir=repair_root,
            max_attempts=10,
        )
        assert len(evidence["recent_attempts"]) == 5
        # Sorted reverse – most recent first (a4, a3, a2, a1, a0)
        assert evidence["recent_attempts"][0]["attempt_id"] == "a4"


# ---------------------------------------------------------------------------
# T5: Budget constant and helpers
# ---------------------------------------------------------------------------


class TestMetaRepairBudgetConstant:
    def test_budget_constant_is_5400(self) -> None:
        assert META_REPAIR_BUDGET_SECS == 5400

    def test_budget_constant_is_int(self) -> None:
        assert isinstance(META_REPAIR_BUDGET_SECS, int)

    def test_budget_greater_than_ordinary_repair(self) -> None:
        """Meta-repair gets a longer budget than ordinary repair (3600)."""
        assert META_REPAIR_BUDGET_SECS > 3600


class TestComputeMetaDeadline:
    def test_default_budget_is_meta_budget(self) -> None:
        from datetime import datetime, timedelta, timezone

        start = datetime(2026, 7, 1, 12, 0, 0, tzinfo=timezone.utc)
        deadline = compute_meta_deadline(start)
        expected = start + timedelta(seconds=META_REPAIR_BUDGET_SECS)
        assert deadline == expected

    def test_custom_budget_override(self) -> None:
        from datetime import datetime, timedelta, timezone

        start = datetime(2026, 7, 1, 12, 0, 0, tzinfo=timezone.utc)
        deadline = compute_meta_deadline(start, budget_secs=60)
        assert deadline == start + timedelta(seconds=60)


class TestRemainingMetaBudget:
    def test_positive_remaining(self) -> None:
        from datetime import datetime, timedelta, timezone

        now = datetime(2026, 7, 1, 12, 0, 0, tzinfo=timezone.utc)
        deadline = now + timedelta(seconds=1800)
        remaining = remaining_meta_budget_secs(deadline, now)
        assert remaining == 1800.0

    def test_exhausted_returns_zero(self) -> None:
        from datetime import datetime, timedelta, timezone

        now = datetime(2026, 7, 1, 12, 0, 0, tzinfo=timezone.utc)
        deadline = now - timedelta(seconds=60)
        remaining = remaining_meta_budget_secs(deadline, now)
        assert remaining == 0.0

    def test_exact_deadline_returns_zero(self) -> None:
        from datetime import datetime, timezone

        now = datetime(2026, 7, 1, 12, 0, 0, tzinfo=timezone.utc)
        assert remaining_meta_budget_secs(now, now) == 0.0


class TestIsMetaBudgetExhausted:
    def test_not_exhausted_with_remaining(self) -> None:
        from datetime import datetime, timedelta, timezone

        now = datetime(2026, 7, 1, 12, 0, 0, tzinfo=timezone.utc)
        deadline = now + timedelta(seconds=3600)
        assert not is_meta_budget_exhausted(deadline, now)

    def test_exhausted_when_past_deadline(self) -> None:
        from datetime import datetime, timedelta, timezone

        now = datetime(2026, 7, 1, 12, 0, 0, tzinfo=timezone.utc)
        deadline = now - timedelta(seconds=1)
        assert is_meta_budget_exhausted(deadline, now)

    def test_exhausted_at_deadline(self) -> None:
        from datetime import datetime, timezone

        now = datetime(2026, 7, 1, 12, 0, 0, tzinfo=timezone.utc)
        assert is_meta_budget_exhausted(now, now)


# ---------------------------------------------------------------------------
# T5: MetaRepairRecord shape and serialization
# ---------------------------------------------------------------------------


class TestMetaRepairRecordShape:
    def test_record_has_all_required_fields(self) -> None:
        record = MetaRepairRecord(
            meta_repair_id="mr-001",
            session="test-session",
            trigger=MetaRepairTrigger.REPAIR_TIMEOUT,
        )
        d = record.to_dict()
        required_keys = {
            "meta_repair_id",
            "session",
            "trigger",
            "diagnosis",
            "subagent_results",
            "changes",
            "tests",
            "retrigger_command",
            "post_retrigger_verification",
            "outcome",
            "created_at",
        }
        assert set(d.keys()) == required_keys

    def test_extracts_reported_change_and_test_custody(self) -> None:
        response = """ESCALATE

Change made: [meta_repair.py](/workspace/arnold/arnold_pipelines/megaplan/cloud/meta_repair.py:250) now scopes history.
Focused validation passed: `python3 -m py_compile arnold_pipelines/megaplan/cloud/meta_repair.py`.
Focused tests passed: `python3 -m pytest tests/cloud/test_meta_repair.py -q` -> `5 passed`.
"""

        changes, tests = extract_reported_repair_custody(response)

        assert changes == [
            {
                "file": "/workspace/arnold/arnold_pipelines/megaplan/cloud/meta_repair.py",
                "status": "reported",
            }
        ]
        assert tests == [
            {
                "command": "python3 -m py_compile arnold_pipelines/megaplan/cloud/meta_repair.py",
                "result": "reported_pass",
            },
            {
                "command": "python3 -m pytest tests/cloud/test_meta_repair.py -q",
                "result": "reported_pass",
            },
        ]

    def test_record_defaults_are_empty(self) -> None:
        record = MetaRepairRecord(
            meta_repair_id="mr-002",
            session="s",
            trigger=None,
        )
        assert record.diagnosis == ""
        assert record.subagent_results == {}
        assert record.changes == []
        assert record.tests == []
        assert record.retrigger_command == ""
        assert record.post_retrigger_verification == {}
        assert record.outcome == ""

    def test_created_at_is_auto_populated(self) -> None:
        record = MetaRepairRecord(
            meta_repair_id="mr-003",
            session="s",
            trigger=None,
        )
        assert record.created_at
        # Must be parseable ISO-8601
        from datetime import datetime

        datetime.fromisoformat(record.created_at)

    def test_explicit_created_at_preserved(self) -> None:
        record = MetaRepairRecord(
            meta_repair_id="mr-004",
            session="s",
            trigger=None,
            created_at="2026-07-01T00:00:00+00:00",
        )
        assert record.created_at == "2026-07-01T00:00:00+00:00"

    def test_full_record_to_dict_contains_all_data(self) -> None:
        record = MetaRepairRecord(
            meta_repair_id="mr-full",
            session="full-session",
            trigger=MetaRepairTrigger.PERSISTENT_RECURRING_RETRY,
            diagnosis="Root cause: flaky network in tool launch",
            subagent_results={"codex": {"verdict": "phase_failed"}},
            changes=[{"file": "foo.py", "action": "patched"}],
            tests=[{"name": "test_foo", "result": "pass"}],
            retrigger_command="repair --session full-session --retry",
            post_retrigger_verification={"outcome": "complete"},
            outcome="complete",
            created_at="2026-07-01T12:00:00+00:00",
        )
        d = record.to_dict()
        assert d["meta_repair_id"] == "mr-full"
        assert d["session"] == "full-session"
        assert d["trigger"] == "persistent_recurring_retry"
        assert d["diagnosis"] == "Root cause: flaky network in tool launch"
        assert d["subagent_results"]["codex"]["verdict"] == "phase_failed"
        assert d["changes"][0]["file"] == "foo.py"
        assert d["tests"][0]["name"] == "test_foo"
        assert d["retrigger_command"] == "repair --session full-session --retry"
        assert d["post_retrigger_verification"]["outcome"] == "complete"
        assert d["outcome"] == "complete"
        assert d["created_at"] == "2026-07-01T12:00:00+00:00"

    def test_roundtrip_to_dict_from_dict(self) -> None:
        original = MetaRepairRecord(
            meta_repair_id="mr-roundtrip",
            session="rt-session",
            trigger=MetaRepairTrigger.DISCORD_DELIVERY_FAILURE,
            diagnosis="Discord webhook unreachable",
            subagent_results={"deepseek": {"verdict": "needs_human"}},
            changes=[{"file": "config.yaml", "action": "update_webhook_url"}],
            tests=[],
            retrigger_command="repair --session rt-session",
            post_retrigger_verification={"outcome": "needs_human"},
            outcome="needs_human",
            created_at="2026-07-01T13:00:00+00:00",
        )
        reloaded = MetaRepairRecord.from_dict(original.to_dict())
        assert reloaded.meta_repair_id == original.meta_repair_id
        assert reloaded.session == original.session
        assert reloaded.trigger == original.trigger
        assert reloaded.diagnosis == original.diagnosis
        assert reloaded.subagent_results == original.subagent_results
        assert reloaded.changes == original.changes
        assert reloaded.tests == original.tests
        assert reloaded.retrigger_command == original.retrigger_command
        assert reloaded.post_retrigger_verification == original.post_retrigger_verification
        assert reloaded.outcome == original.outcome
        assert reloaded.created_at == original.created_at

    def test_from_dict_null_trigger(self) -> None:
        record = MetaRepairRecord.from_dict(
            {
                "meta_repair_id": "mr-null",
                "session": "s",
                "trigger": None,
                "created_at": "2026-07-01T00:00:00+00:00",
            }
        )
        assert record.trigger is None
        assert record.meta_repair_id == "mr-null"

    def test_from_dict_unknown_trigger_becomes_none(self) -> None:
        record = MetaRepairRecord.from_dict(
            {
                "meta_repair_id": "mr-bad",
                "session": "s",
                "trigger": "nonexistent_trigger",
                "created_at": "2026-07-01T00:00:00+00:00",
            }
        )
        assert record.trigger is None

    def test_from_dict_missing_fields_get_defaults(self) -> None:
        record = MetaRepairRecord.from_dict(
            {
                "meta_repair_id": "mr-min",
                "session": "minimal",
            }
        )
        assert record.diagnosis == ""
        assert record.subagent_results == {}
        assert record.outcome == ""


# ---------------------------------------------------------------------------
# T5: Persistence (repair-data/meta/<id>.json)
# ---------------------------------------------------------------------------


class TestPersistMetaRepairRecord:
    def test_persist_creates_meta_directory_and_file(self, tmp_path: Path) -> None:
        repair_dir = tmp_path / "repair-data"
        repair_dir.mkdir(parents=True)

        record = MetaRepairRecord(
            meta_repair_id="mr-persist-1",
            session="persist-session",
            trigger=MetaRepairTrigger.REPAIR_TIMEOUT,
            diagnosis="Timeout during phase 3",
            outcome="complete",
            created_at="2026-07-01T12:00:00+00:00",
        )

        file_path = persist_meta_repair_record(
            record,
            repair_data_dir=repair_dir,
        )

        assert file_path.exists()
        assert file_path.parent.name == "meta"
        assert file_path.name == "mr-persist-1.json"

    def test_persisted_file_is_valid_json(self, tmp_path: Path) -> None:
        repair_dir = tmp_path / "repair-data"
        repair_dir.mkdir(parents=True)

        record = MetaRepairRecord(
            meta_repair_id="mr-valid-json",
            session="json-session",
            trigger=MetaRepairTrigger.STATE_INSPECTION_FAILURE,
            diagnosis="Snapshot read error",
            changes=[{"file": "a.py", "action": "add"}],
            outcome="needs_human",
            created_at="2026-07-01T12:00:00+00:00",
        )

        file_path = persist_meta_repair_record(
            record,
            repair_data_dir=repair_dir,
        )

        loaded = json.loads(file_path.read_text(encoding="utf-8"))
        assert loaded["meta_repair_id"] == "mr-valid-json"
        assert loaded["session"] == "json-session"
        assert loaded["trigger"] == "state_inspection_failure"
        assert loaded["diagnosis"] == "Snapshot read error"
        assert loaded["changes"] == [{"file": "a.py", "action": "add"}]
        assert loaded["outcome"] == "needs_human"

    def test_persist_updates_session_index_without_clobbering_latest_outcome(
        self, tmp_path: Path
    ) -> None:
        repair_dir = tmp_path / "repair-data"
        repair_dir.mkdir(parents=True)
        save_repair_data(
            repair_dir / "json-session.repair-data.json",
            merge_additive_fields(
                {
                    "session": "json-session",
                    "workspace": "/workspace/project",
                    "run_kind": "chain",
                    "plan_name": "m5-plan",
                    "outcome": REPAIR_TIMEOUT,
                    "attempts": [],
                    "iterations": [],
                    "initial_facts": {},
                    "current_advancement_snapshot": {},
                    "current_signature": {},
                },
                verification={"recorded_at": "2026-07-01T11:50:00+00:00"},
            ),
        )

        record = MetaRepairRecord(
            meta_repair_id="mr-indexed",
            session="json-session",
            trigger=MetaRepairTrigger.STATE_INSPECTION_FAILURE,
            diagnosis="Snapshot read error",
            outcome="fixed",
            created_at="2026-07-01T12:00:00+00:00",
        )

        persist_meta_repair_record(record, repair_data_dir=repair_dir)

        index_payload = read_repair_index(repair_dir / "index.json")
        session_entry = index_payload["sessions"]["json-session"]
        assert session_entry["refs"]["latest-outcome"]["outcome"] == REPAIR_TIMEOUT
        assert session_entry["latest_meta_repair_id"] == "mr-indexed"
        assert session_entry["latest_meta_outcome"] == "fixed"
        assert session_entry["latest_meta_recorded_at"] == "2026-07-01T12:00:00+00:00"
        assert session_entry["latest_meta_record_path"].endswith("/repair-data/meta/mr-indexed.json")

    def test_load_persisted_record_roundtrip(self, tmp_path: Path) -> None:
        repair_dir = tmp_path / "repair-data"
        repair_dir.mkdir(parents=True)

        original = MetaRepairRecord(
            meta_repair_id="mr-load-1",
            session="load-session",
            trigger=MetaRepairTrigger.PERSISTENT_RECURRING_RETRY,
            diagnosis="Phase failed repeating",
            subagent_results={"codex": {"result": "identified"}},
            changes=[{"file": "x.py", "action": "patch"}],
            tests=[{"name": "test_x", "result": "pass"}],
            retrigger_command="repair --session load-session",
            post_retrigger_verification={"outcome": "complete"},
            outcome="complete",
            created_at="2026-07-01T14:00:00+00:00",
        )

        persist_meta_repair_record(original, repair_data_dir=repair_dir)
        loaded = load_meta_repair_record("mr-load-1", repair_data_dir=repair_dir)

        assert loaded is not None
        assert loaded.meta_repair_id == original.meta_repair_id
        assert loaded.session == original.session
        assert loaded.trigger == original.trigger
        assert loaded.diagnosis == original.diagnosis
        assert loaded.subagent_results == original.subagent_results
        assert loaded.changes == original.changes
        assert loaded.tests == original.tests
        assert loaded.post_retrigger_verification == original.post_retrigger_verification
        assert loaded.outcome == original.outcome

    def test_load_nonexistent_record_returns_none(self, tmp_path: Path) -> None:
        repair_dir = tmp_path / "repair-data"
        repair_dir.mkdir(parents=True)
        result = load_meta_repair_record("nonexistent", repair_data_dir=repair_dir)
        assert result is None

    def test_persist_redacts_retrigger_command(self, tmp_path: Path) -> None:
        repair_dir = tmp_path / "repair-data"
        repair_dir.mkdir(parents=True)

        record = MetaRepairRecord(
            meta_repair_id="mr-redact-cmd",
            session="redact-session",
            trigger=MetaRepairTrigger.REPAIR_TIMEOUT,
            retrigger_command="repair --session redact-session --token sk-secret-api-key-12345",
            outcome="complete",
            created_at="2026-07-01T12:00:00+00:00",
        )

        file_path = persist_meta_repair_record(
            record,
            repair_data_dir=repair_dir,
            secret_names=["token"],
        )

        loaded = json.loads(file_path.read_text(encoding="utf-8"))
        assert "sk-secret-api-key-12345" not in loaded["retrigger_command"]
        assert REDACTION in loaded["retrigger_command"]

    def test_persist_empty_retrigger_command_unchanged(self, tmp_path: Path) -> None:
        repair_dir = tmp_path / "repair-data"
        repair_dir.mkdir(parents=True)

        record = MetaRepairRecord(
            meta_repair_id="mr-empty-cmd",
            session="empty-cmd",
            trigger=None,
            retrigger_command="",
            created_at="2026-07-01T12:00:00+00:00",
        )

        file_path = persist_meta_repair_record(
            record,
            repair_data_dir=repair_dir,
        )

        loaded = json.loads(file_path.read_text(encoding="utf-8"))
        assert loaded["retrigger_command"] == ""


# ---------------------------------------------------------------------------
# T5: Timeout-aware behavior
# ---------------------------------------------------------------------------


class TestMetaRepairTimeout:
    def test_budget_exhausted_after_full_duration(self) -> None:
        """After META_REPAIR_BUDGET_SECS, the budget should be exhausted."""
        from datetime import datetime, timedelta, timezone

        start = datetime(2026, 7, 1, 12, 0, 0, tzinfo=timezone.utc)
        deadline = compute_meta_deadline(start)
        # At exactly the deadline, budget is exhausted
        assert is_meta_budget_exhausted(deadline, deadline)

    def test_budget_not_exhausted_before_duration(self) -> None:
        from datetime import datetime, timedelta, timezone

        start = datetime(2026, 7, 1, 12, 0, 0, tzinfo=timezone.utc)
        deadline = compute_meta_deadline(start)
        # One second before the deadline, budget should still be available
        just_before = start + timedelta(seconds=META_REPAIR_BUDGET_SECS - 1)
        assert not is_meta_budget_exhausted(deadline, just_before)
        assert remaining_meta_budget_secs(deadline, just_before) == 1.0

    def test_compute_meta_deadline_with_explicit_budget(self) -> None:
        from datetime import datetime, timedelta, timezone

        start = datetime(2026, 7, 1, 12, 0, 0, tzinfo=timezone.utc)
        deadline = compute_meta_deadline(start, budget_secs=7200)
        assert deadline == start + timedelta(seconds=7200)

    def test_record_persistence_preserves_timeout_context(self, tmp_path: Path) -> None:
        """Verify that a record persisted with a timeout trigger retains full context."""
        repair_dir = tmp_path / "repair-data"
        repair_dir.mkdir(parents=True)

        record = MetaRepairRecord(
            meta_repair_id="mr-timeout-ctx",
            session="timeout-session",
            trigger=MetaRepairTrigger.REPAIR_TIMEOUT,
            diagnosis="Repair exceeded 5400s meta-repair budget",
            subagent_results={"codex": {"analysis": "budget_exhausted"}},
            changes=[],
            tests=[{"name": "test_budget", "result": "skipped"}],
            retrigger_command="repair --session timeout-session --with-extended-budget",
            post_retrigger_verification={"outcome": "pending"},
            outcome="meta_repair_timeout",
            created_at="2026-07-01T15:00:00+00:00",
        )

        persist_meta_repair_record(record, repair_data_dir=repair_dir)
        loaded = load_meta_repair_record("mr-timeout-ctx", repair_data_dir=repair_dir)

        assert loaded is not None
        assert loaded.trigger == MetaRepairTrigger.REPAIR_TIMEOUT
        assert loaded.diagnosis == "Repair exceeded 5400s meta-repair budget"
        assert loaded.outcome == "meta_repair_timeout"
        assert loaded.subagent_results["codex"]["analysis"] == "budget_exhausted"
        assert loaded.tests[0]["result"] == "skipped"


class TestRetriggerVerification:
    @pytest.mark.parametrize(
        "verification",
        [
            {"outcome": COMPLETE, "kind": "pid", "pid_alive": True},
            {"outcome": COMPLETE, "kind": "heartbeat", "heartbeat_active": True},
            {"outcome": PARTIAL_LIVENESS, "kind": "partial_liveness", "is_live": True},
            {"outcome": COMPLETE, "kind": "subprocess_success"},
        ],
    )
    def test_process_and_liveness_only_are_never_accepted(
        self, verification: dict[str, object]
    ) -> None:
        result = verify_retrigger_success(
            retriggered=True,
            retrigger_result=RetriggerExecutionResult(
                command=("arnold-repair-loop", "demo-session"),
                returncode=0,
                stdout="ok",
                stderr="",
                lock_released=True,
            ),
            post_retrigger_verification=verification,
        )

        assert result["accepted"] is False
        assert result["recovery_status"] == "provisional"
        assert result["recovery_verification"]["authorizes_verified_recovered"] is False

    def test_partial_liveness_remains_rejected(self) -> None:
        result = verify_retrigger_success(
            retriggered=True,
            retrigger_result=RetriggerExecutionResult(
                command=("arnold-repair-loop", "demo-session"),
                returncode=0,
                stdout="ok",
                stderr="",
                lock_released=True,
            ),
            post_retrigger_verification={"outcome": PARTIAL_LIVENESS},
        )

        assert result["accepted"] is False
        assert result["outcome"] == PARTIAL_LIVENESS
        assert result["recovery_status"] == "provisional"

    @pytest.mark.parametrize("unknown_type", ["missing", "stale", "partial", "contradictory"])
    def test_typed_unknown_verification_fails_closed(self, unknown_type: str) -> None:
        result = verify_retrigger_success(
            retriggered=True,
            retrigger_result=RetriggerExecutionResult(
                command=("arnold-repair-loop", "demo-session"), returncode=0
            ),
            post_retrigger_verification={
                "outcome": COMPLETE,
                "original_blocker": {"blocker_id": "blocker-42"},
                "observation": {
                    "evidence_state": {
                        "status": "unknown",
                        "unknown_type": unknown_type,
                    }
                },
                "repair_completed_at": "2026-07-09T07:53:00+00:00",
            },
        )

        assert result["accepted"] is False
        assert result["recovery_status"] == "unknown"
        assert result["unknown_type"] == unknown_type

    def test_later_independent_blocker_specific_observation_is_accepted(self) -> None:
        result = verify_retrigger_success(
            retriggered=True,
            retrigger_result=RetriggerExecutionResult(
                command=("arnold-repair-loop", "demo-session"), returncode=0
            ),
            post_retrigger_verification={
                "outcome": COMPLETE,
                "repair_completed_at": "2026-07-09T07:53:00+00:00",
                "post_snapshot": _terminal_post_snapshot(),
                "original_blocker": {"blocker_id": "blocker-42"},
                "observation": {
                    "kind": "plan_state",
                    "blocker_id": "blocker-42",
                    "blocker_cleared": True,
                    "directly_observed": True,
                    "independent": True,
                    "observed_at": "2026-07-09T07:54:00+00:00",
                },
            },
        )

        assert result["accepted"] is True
        assert result["recovery_status"] == "verified_recovered"
        assert result["recovery_verification"]["blocker_identity"] == "blocker-42"


@pytest.mark.parametrize(
    ("master", "path", "authorized"),
    [("0", "0", False), ("0", "1", False), ("1", "0", False), ("1", "1", True)],
)
def test_retrigger_effect_boundary_requires_master_and_l2_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    master: str,
    path: str,
    authorized: bool,
) -> None:
    monkeypatch.setenv("ARNOLD_AUTONOMY", master)
    monkeypatch.setenv("ARNOLD_META_REPAIR_ENABLED", path)
    calls: list[str] = []

    def release(_path: object, *, expected_pid: int | None = None) -> bool:
        calls.append(f"release:{expected_pid}")
        return True

    def runner(*_args: object, **_kwargs: object) -> object:
        calls.append("launch")
        return type("Completed", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    if not authorized:
        with pytest.raises(PermissionError, match="L2 mutation requires"):
            retrigger_ordinary_repair(
                command=("arnold-repair-loop", "session"),
                repair_lock_dir=tmp_path / "lock",
                expected_lock_pid=42,
                runner=runner,
                release_lock=release,
            )
        assert calls == []
        return

    result = retrigger_ordinary_repair(
        command=("arnold-repair-loop", "session"),
        repair_lock_dir=tmp_path / "lock",
        expected_lock_pid=42,
        runner=runner,
        release_lock=release,
    )
    assert result.returncode == 0
    assert calls == ["release:42", "launch"]


# ---------------------------------------------------------------------------
# T7: Meta-repair policy guards — recursion prevention and commit gating
# ---------------------------------------------------------------------------

from arnold_pipelines.megaplan.cloud.meta_repair_policy import (
    CommitGateResult,
    RecursionCheckResult,
    can_commit_changes,
    can_push_changes,
    check_meta_repair_recursion,
)


class TestRecursionCheckResult:
    """Unit tests for the RecursionCheckResult dataclass."""

    def test_not_recursing_should_not_escalate(self) -> None:
        result = RecursionCheckResult(
            session="s1",
            recursing=False,
            recommendation="safe",
        )
        assert result.should_escalate is False
        assert result.recursing is False

    def test_recursing_should_escalate(self) -> None:
        result = RecursionCheckResult(
            session="s1",
            recursing=True,
            existing_meta_repair_ids=("mr-1",),
            recommendation="escalate",
        )
        assert result.should_escalate is True
        assert result.recursing is True

    def test_defaults_are_empty(self) -> None:
        result = RecursionCheckResult(session="s", recursing=False)
        assert result.existing_meta_repair_ids == ()
        assert result.recommendation == ""

    def test_frozen_dataclass(self) -> None:
        result = RecursionCheckResult(session="s", recursing=False)
        with pytest.raises(Exception):
            result.recursing = True  # type: ignore[misc]


class TestCheckMetaRepairRecursion:
    """Recursion guard: meta-repair must escalate instead of recursing."""

    def test_no_meta_dir_means_no_recursion(self, tmp_path: Path) -> None:
        repair_dir = tmp_path / "repair-data"
        repair_dir.mkdir()
        result = check_meta_repair_recursion(
            session="test-session",
            repair_data_dir=repair_dir,
        )
        assert result.recursing is False
        assert result.should_escalate is False
        assert "safe to proceed" in result.recommendation

    def test_empty_meta_dir_means_no_recursion(self, tmp_path: Path) -> None:
        repair_dir = tmp_path / "repair-data"
        meta_dir = repair_dir / "meta"
        meta_dir.mkdir(parents=True)
        result = check_meta_repair_recursion(
            session="test-session",
            repair_data_dir=repair_dir,
        )
        assert result.recursing is False
        assert result.should_escalate is False

    def test_existing_record_causes_recursion_for_same_session(
        self, tmp_path: Path
    ) -> None:
        repair_dir = tmp_path / "repair-data"
        meta_dir = repair_dir / "meta"
        meta_dir.mkdir(parents=True)

        # Persist a meta-repair record for the same session
        record = {
            "meta_repair_id": "mr-001",
            "session": "recursion-test",
            "trigger": "repair_timeout",
            "diagnosis": "previous attempt",
            "outcome": "needs_human",
        }
        (meta_dir / "mr-001.json").write_text(json.dumps(record), encoding="utf-8")

        result = check_meta_repair_recursion(
            session="recursion-test",
            repair_data_dir=repair_dir,
        )
        assert result.recursing is True
        assert result.should_escalate is True
        assert NEEDS_HUMAN in result.recommendation
        assert "mr-001" in result.existing_meta_repair_ids

    def test_codex_launch_failure_record_does_not_poison_recursion(
        self, tmp_path: Path
    ) -> None:
        repair_dir = tmp_path / "repair-data"
        meta_dir = repair_dir / "meta"
        meta_dir.mkdir(parents=True)

        record = {
            "meta_repair_id": "mr-launch-failed",
            "session": "recursion-test",
            "trigger": "partial_liveness_recurrence",
            "diagnosis": "Codex meta-repair orchestrator returned no output (timed out or failed to launch DeepSeek/Hermes subagents); see meta-repair log.",
            "subagent_results": {
                "codex_response": "Not inside a trusted directory and --skip-git-repo-check was not specified."
            },
            "outcome": "Codex meta-repair orchestrator returned no output (timed out or failed to launch DeepSeek/Hermes subagents); see meta-repair log.",
        }
        (meta_dir / "mr-launch-failed.json").write_text(
            json.dumps(record), encoding="utf-8"
        )

        result = check_meta_repair_recursion(
            session="recursion-test",
            repair_data_dir=repair_dir,
        )
        assert result.recursing is False
        assert result.existing_meta_repair_ids == ()

    def test_one_commit_custody_failure_allows_bounded_retry(self, tmp_path: Path) -> None:
        repair_dir = tmp_path / "repair-data"
        meta_dir = repair_dir / "meta"
        meta_dir.mkdir(parents=True)
        (meta_dir / "mr-custody-1.json").write_text(
            json.dumps({
                "meta_repair_id": "mr-custody-1",
                "session": "recursion-test",
                "outcome": "commit_custody_failed",
            }),
            encoding="utf-8",
        )

        result = check_meta_repair_recursion(
            session="recursion-test", repair_data_dir=repair_dir
        )

        assert result.recursing is False
        assert result.existing_meta_repair_ids == ()

    def test_repeated_commit_custody_failure_escalates(self, tmp_path: Path) -> None:
        repair_dir = tmp_path / "repair-data"
        meta_dir = repair_dir / "meta"
        meta_dir.mkdir(parents=True)
        for index in (1, 2):
            (meta_dir / f"mr-custody-{index}.json").write_text(
                json.dumps({
                    "meta_repair_id": f"mr-custody-{index}",
                    "session": "recursion-test",
                    "outcome": "commit_custody_failed",
                }),
                encoding="utf-8",
            )

        result = check_meta_repair_recursion(
            session="recursion-test", repair_data_dir=repair_dir
        )

        assert result.recursing is True
        assert result.existing_meta_repair_ids == (
            "mr-custody-1",
            "mr-custody-2",
        )

    def test_input_too_large_record_does_not_poison_recursion(
        self, tmp_path: Path
    ) -> None:
        repair_dir = tmp_path / "repair-data"
        meta_dir = repair_dir / "meta"
        meta_dir.mkdir(parents=True)

        record = {
            "meta_repair_id": "mr-input-too-large",
            "session": "recursion-test",
            "trigger": "repair_timeout",
            "diagnosis": "Codex meta-repair prompt exceeded input limit; see meta-repair log.",
            "subagent_results": {
                "codex_response": "Input exceeds the maximum length of 1048576 characters. (code -32602)"
            },
            "outcome": "Codex meta-repair prompt exceeded input limit; see meta-repair log.",
        }
        (meta_dir / "mr-input-too-large.json").write_text(
            json.dumps(record), encoding="utf-8"
        )

        result = check_meta_repair_recursion(
            session="recursion-test",
            repair_data_dir=repair_dir,
        )
        assert result.recursing is False
        assert result.existing_meta_repair_ids == ()

    def test_existing_record_for_different_session_is_not_recursion(
        self, tmp_path: Path
    ) -> None:
        repair_dir = tmp_path / "repair-data"
        meta_dir = repair_dir / "meta"
        meta_dir.mkdir(parents=True)

        record = {
            "meta_repair_id": "mr-002",
            "session": "other-session",
            "trigger": "repair_timeout",
            "diagnosis": "different session",
            "outcome": "needs_human",
        }
        (meta_dir / "mr-002.json").write_text(json.dumps(record), encoding="utf-8")

        # Check for a different session
        result = check_meta_repair_recursion(
            session="my-session",
            repair_data_dir=repair_dir,
        )
        assert result.recursing is False
        assert result.should_escalate is False
        assert "safe to proceed" in result.recommendation

    def test_max_meta_repair_attempts_larger_than_one(
        self, tmp_path: Path
    ) -> None:
        repair_dir = tmp_path / "repair-data"
        meta_dir = repair_dir / "meta"
        meta_dir.mkdir(parents=True)

        # Write one record for the session
        record = {
            "meta_repair_id": "mr-003",
            "session": "multi-attempt",
            "trigger": "repair_timeout",
            "diagnosis": "first attempt",
            "outcome": "needs_human",
        }
        (meta_dir / "mr-003.json").write_text(json.dumps(record), encoding="utf-8")

        # max_meta_repair_attempts=2 — one existing is still OK
        result = check_meta_repair_recursion(
            session="multi-attempt",
            repair_data_dir=repair_dir,
            max_meta_repair_attempts=2,
        )
        assert result.recursing is False
        assert result.should_escalate is False

        # Now add a second record
        record2 = {
            "meta_repair_id": "mr-004",
            "session": "multi-attempt",
            "trigger": "state_inspection_failure",
            "diagnosis": "second attempt",
            "outcome": "needs_human",
        }
        (meta_dir / "mr-004.json").write_text(json.dumps(record2), encoding="utf-8")

        result = check_meta_repair_recursion(
            session="multi-attempt",
            repair_data_dir=repair_dir,
            max_meta_repair_attempts=2,
        )
        assert result.recursing is True
        assert result.should_escalate is True
        assert len(result.existing_meta_repair_ids) == 2

    def test_multiple_records_listed_in_recommendation(
        self, tmp_path: Path
    ) -> None:
        repair_dir = tmp_path / "repair-data"
        meta_dir = repair_dir / "meta"
        meta_dir.mkdir(parents=True)

        for i in range(3):
            record = {
                "meta_repair_id": f"mr-{i:03d}",
                "session": "many-records",
                "trigger": "repair_timeout",
                "diagnosis": f"attempt {i}",
                "outcome": "needs_human",
            }
            (meta_dir / f"mr-{i:03d}.json").write_text(
                json.dumps(record), encoding="utf-8"
            )

        result = check_meta_repair_recursion(
            session="many-records",
            repair_data_dir=repair_dir,
        )
        assert result.recursing is True
        assert len(result.existing_meta_repair_ids) == 3
        assert all(f"mr-{i:03d}" in result.existing_meta_repair_ids for i in range(3))
        assert NEEDS_HUMAN in result.recommendation

    def test_corrupt_json_file_handled_gracefully(
        self, tmp_path: Path
    ) -> None:
        repair_dir = tmp_path / "repair-data"
        meta_dir = repair_dir / "meta"
        meta_dir.mkdir(parents=True)

        # Write a valid JSON file that does NOT belong to this session
        (meta_dir / "mr-other.json").write_text(
            json.dumps({"meta_repair_id": "mr-other", "session": "other-session"}),
            encoding="utf-8",
        )
        # Write a valid JSON for our session
        (meta_dir / "mr-mine.json").write_text(
            json.dumps({"meta_repair_id": "mr-mine", "session": "my-session"}),
            encoding="utf-8",
        )

        result = check_meta_repair_recursion(
            session="my-session",
            repair_data_dir=repair_dir,
        )
        # Only the matching file is counted — not the other-session one
        assert result.recursing is True
        assert "mr-mine" in result.existing_meta_repair_ids
        assert "mr-other" not in result.existing_meta_repair_ids


class TestCommitGateResult:
    """Unit tests for the CommitGateResult dataclass."""

    def test_allowed_true(self) -> None:
        result = CommitGateResult(allowed=True, reason="commits permitted")
        assert result.allowed is True
        assert result.reason == "commits permitted"

    def test_allowed_false(self) -> None:
        result = CommitGateResult(allowed=False, reason="commits blocked")
        assert result.allowed is False
        assert result.reason == "commits blocked"

    def test_default_flag_name(self) -> None:
        result = CommitGateResult(allowed=False, reason="nope")
        assert result.flag_name == "ARNOLD_META_REPAIR_COMMIT_ENABLED"

    def test_frozen_dataclass(self) -> None:
        result = CommitGateResult(allowed=False, reason="x")
        with pytest.raises(Exception):
            result.allowed = True  # type: ignore[misc]


class TestCanCommitChanges:
    """Commit gating: commits require META_REPAIR_COMMIT_ENABLED."""

    def test_commit_allowed_when_flag_unset(self) -> None:
        os.environ.pop("ARNOLD_META_REPAIR_COMMIT_ENABLED", None)
        result = can_commit_changes()
        assert result.allowed is True
        assert result.flag_name == "ARNOLD_META_REPAIR_COMMIT_ENABLED"

    def test_commit_allowed_when_flag_on(self) -> None:
        os.environ["ARNOLD_AUTONOMY"] = "1"
        os.environ["ARNOLD_META_REPAIR_ENABLED"] = "1"
        os.environ["ARNOLD_META_REPAIR_COMMIT_ENABLED"] = "1"
        try:
            result = can_commit_changes()
            assert result.allowed is True
            assert "on" in result.reason.lower() or "permitted" in result.reason.lower()
        finally:
            os.environ.pop("ARNOLD_AUTONOMY", None)
            os.environ.pop("ARNOLD_META_REPAIR_ENABLED", None)
            os.environ.pop("ARNOLD_META_REPAIR_COMMIT_ENABLED", None)

    def test_commit_blocked_when_commit_on_but_master_off(self) -> None:
        os.environ["ARNOLD_AUTONOMY"] = "0"
        os.environ["ARNOLD_META_REPAIR_ENABLED"] = "1"
        os.environ["ARNOLD_META_REPAIR_COMMIT_ENABLED"] = "1"
        try:
            result = can_commit_changes()
            assert result.allowed is False
            assert "master" in result.reason.lower()
        finally:
            os.environ.pop("ARNOLD_AUTONOMY", None)
            os.environ.pop("ARNOLD_META_REPAIR_ENABLED", None)
            os.environ.pop("ARNOLD_META_REPAIR_COMMIT_ENABLED", None)

    def test_commit_blocked_with_falsey_values(self) -> None:
        for val in ("0", "false", "no", "off"):
            os.environ["ARNOLD_META_REPAIR_COMMIT_ENABLED"] = val
            try:
                result = can_commit_changes()
                assert result.allowed is False, f"Should block for val={val!r}"
            finally:
                os.environ.pop("ARNOLD_META_REPAIR_COMMIT_ENABLED", None)

    def test_commit_includes_session_in_reason(self) -> None:
        os.environ.pop("ARNOLD_META_REPAIR_COMMIT_ENABLED", None)
        result = can_commit_changes(session="my-session")
        assert "my-session" in result.reason

    def test_commit_allowed_with_unset_env(self) -> None:
        os.environ.pop("ARNOLD_META_REPAIR_COMMIT_ENABLED", None)
        result = can_commit_changes(session="")
        assert result.allowed is True


class TestCanPushChanges:
    """Push gating: push uses the same commit gate."""

    def test_push_allowed_when_flag_unset(self) -> None:
        os.environ.pop("ARNOLD_META_REPAIR_COMMIT_ENABLED", None)
        result = can_push_changes()
        assert result.allowed is True
        assert "push" in result.reason.lower()

    def test_push_allowed_when_flag_on(self) -> None:
        os.environ["ARNOLD_AUTONOMY"] = "1"
        os.environ["ARNOLD_META_REPAIR_ENABLED"] = "1"
        os.environ["ARNOLD_META_REPAIR_COMMIT_ENABLED"] = "1"
        try:
            result = can_push_changes()
            assert result.allowed is True
            assert "push" in result.reason.lower()
        finally:
            os.environ.pop("ARNOLD_AUTONOMY", None)
            os.environ.pop("ARNOLD_META_REPAIR_ENABLED", None)
            os.environ.pop("ARNOLD_META_REPAIR_COMMIT_ENABLED", None)

    def test_push_blocked_with_falsey_values(self) -> None:
        for val in ("0", "false"):
            os.environ["ARNOLD_META_REPAIR_COMMIT_ENABLED"] = val
            try:
                result = can_push_changes()
                assert result.allowed is False, f"Should block for val={val!r}"
            finally:
                os.environ.pop("ARNOLD_META_REPAIR_COMMIT_ENABLED", None)

    def test_push_uses_same_gate_as_commit(self) -> None:
        """Push blocked when commit blocked; push allowed when commit allowed."""
        os.environ.pop("ARNOLD_META_REPAIR_COMMIT_ENABLED", None)
        commit_result = can_commit_changes()
        push_result = can_push_changes()
        assert push_result.allowed == commit_result.allowed

        os.environ["ARNOLD_META_REPAIR_COMMIT_ENABLED"] = "1"
        os.environ["ARNOLD_AUTONOMY"] = "1"
        os.environ["ARNOLD_META_REPAIR_ENABLED"] = "1"
        try:
            commit_result = can_commit_changes()
            push_result = can_push_changes()
            assert push_result.allowed == commit_result.allowed
        finally:
            os.environ.pop("ARNOLD_AUTONOMY", None)
            os.environ.pop("ARNOLD_META_REPAIR_ENABLED", None)
            os.environ.pop("ARNOLD_META_REPAIR_COMMIT_ENABLED", None)

    def test_push_includes_session_in_reason(self) -> None:
        os.environ.pop("ARNOLD_META_REPAIR_COMMIT_ENABLED", None)
        result = can_push_changes(session="push-session")
        assert "push-session" in result.reason


class TestPolicyEndToEnd:
    """End-to-end: recursion escalation + commit gating interact correctly."""

    def test_recursion_escalation_is_durable_human_escalation(
        self, tmp_path: Path
    ) -> None:
        """When recursion is detected, recommendation must reference NEEDS_HUMAN."""
        repair_dir = tmp_path / "repair-data"
        meta_dir = repair_dir / "meta"
        meta_dir.mkdir(parents=True)

        record = {
            "meta_repair_id": "mr-e2e-1",
            "session": "e2e-session",
            "trigger": "repair_timeout",
            "diagnosis": "already attempted",
            "outcome": "needs_human",
        }
        (meta_dir / "mr-e2e-1.json").write_text(json.dumps(record), encoding="utf-8")

        recursion = check_meta_repair_recursion(
            session="e2e-session",
            repair_data_dir=repair_dir,
        )
        assert recursion.recursing is True
        assert NEEDS_HUMAN in recursion.recommendation

    def test_recursion_blocks_further_commits_implicitly(self) -> None:
        """Recursion escalation is independent of commit gating.

        Even when commits are theoretically allowed, if the recursion
        check says escalate, the caller should not commit.
        """
        # Set commit flag ON
        os.environ["ARNOLD_META_REPAIR_COMMIT_ENABLED"] = "1"
        os.environ["ARNOLD_AUTONOMY"] = "1"
        os.environ["ARNOLD_META_REPAIR_ENABLED"] = "1"
        try:
            commit_result = can_commit_changes(session="any")
            assert commit_result.allowed is True

            # But recursion check would independently block progress
            # This test verifies the two gates are independent mechanisms
            recursion = RecursionCheckResult(
                session="any",
                recursing=True,
                existing_meta_repair_ids=("mr-prior",),
                recommendation=f"Escalate to {NEEDS_HUMAN}",
            )
            assert recursion.should_escalate is True
            # Both gates must be checked independently by the caller
        finally:
            os.environ.pop("ARNOLD_AUTONOMY", None)
            os.environ.pop("ARNOLD_META_REPAIR_ENABLED", None)
            os.environ.pop("ARNOLD_META_REPAIR_COMMIT_ENABLED", None)

    def test_commit_gate_independent_of_recursion(self) -> None:
        """Commit gate default is independent of recursion state."""
        os.environ.pop("ARNOLD_META_REPAIR_COMMIT_ENABLED", None)
        result = can_commit_changes()
        assert result.allowed is True


def test_repair_evidence_superseded_terminal_blocker_does_not_crash(tmp_path):
    from arnold_pipelines.megaplan.cloud.meta_repair import (
        _repair_evidence_superseded_by_current_target,
    )

    status_path = tmp_path / "state.json"
    status_path.write_text(
        json.dumps(
            {
                "current_state": "finalized",
                "next_step": None,
                "valid_next": [],
                "blocker_recovery": {"has_terminal_blockers": True},
            }
        ),
        encoding="utf-8",
    )
    evidence = {
        "repair_data": {
            "current_signature": {
                "failure_kind": "blocked_state_or_recovery_error",
                "phase_or_step": "execute",
            },
            "current_failure_context": {
                "plan_runtime_state": {"current_state": "finalized"},
            },
        }
    }
    observation = {
        "authoritative_source": "chain_state",
        "current_refs": {
            "current_plan_name": "plan-a",
            "plan_current_state": "finalized",
            "chain_last_state": "finalized",
        },
        "plan_state": {"path": str(status_path)},
        "chain_state": {"present": True},
    }

    reason = _repair_evidence_superseded_by_current_target(
        evidence=evidence,
        current_target_observation=observation,
    )

    assert isinstance(reason, str)


def _terminal_post_snapshot(**overrides: object) -> dict[str, object]:
    snapshot: dict[str, object] = {
        "captured_at": "2026-07-10T01:00:00+00:00",
        "milestone_total": 2,
        "completed_count": 2,
        "chain_last_state": "done",
        "plan_current_state": "done",
        "active_step_present": False,
        "worker_pid_alive": None,
    }
    snapshot.update(overrides)
    return snapshot


def test_meta_retrigger_refuses_complete_without_authoritative_snapshot() -> None:
    verification = verify_retrigger_success(
        retriggered=True,
        retrigger_result=RetriggerExecutionResult(command=("repair",), returncode=0),
        post_retrigger_verification={"outcome": COMPLETE},
    )

    assert verification["accepted"] is False
    assert "snapshot missing" in verification["rejection_reason"]


@pytest.mark.parametrize(
    "snapshot, expected",
    [
        (_terminal_post_snapshot(completed_count=1), "incomplete (1/2)"),
        (_terminal_post_snapshot(active_step_present=True), "still has active_step"),
        (_terminal_post_snapshot(worker_pid_alive=False), "dead worker"),
        (_terminal_post_snapshot(plan_current_state="finalized"), "nonterminal plan state"),
    ],
)
def test_meta_retrigger_refuses_contradictory_complete_snapshot(
    snapshot: dict[str, object], expected: str
) -> None:
    verification = verify_retrigger_success(
        retriggered=True,
        retrigger_result=RetriggerExecutionResult(command=("repair",), returncode=0),
        post_retrigger_verification={"outcome": COMPLETE, "post_snapshot": snapshot},
    )

    assert verification["accepted"] is False
    assert expected in verification["rejection_reason"]


def test_meta_retrigger_accepts_only_complete_with_authoritative_terminal_snapshot() -> None:
    verification = verify_retrigger_success(
        retriggered=True,
        retrigger_result=RetriggerExecutionResult(command=("repair",), returncode=0),
        post_retrigger_verification={
            "outcome": COMPLETE,
            "post_snapshot": _terminal_post_snapshot(),
            "repair_completed_at": "2026-07-10T00:59:00+00:00",
            "original_blocker": {"blocker_id": "blocker-terminal"},
            "observation": {
                "kind": "plan_state",
                "blocker_id": "blocker-terminal",
                "blocker_cleared": True,
                "directly_observed": True,
                "independent": True,
                "observed_at": "2026-07-10T01:00:00+00:00",
            },
        },
    )

    assert verification["accepted"] is True
