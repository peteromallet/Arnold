"""Tests for live_supervisor classification and allowlist rules."""

from __future__ import annotations

import pytest

from arnold.pipelines.megaplan.pipelines.live_supervisor.model import (
    CheckFinding,
    HealthCategory,
    Incident,
    PlanEntry,
    RepairRecommendation,
    SignalBundle,
    Triage,
)
from arnold.pipelines.megaplan.pipelines.live_supervisor.rules import (
    classify_incident,
    enforce_allowlist,
    normalize_doctor_findings,
)


def _incident(
    *,
    triage: Triage = Triage.LIVE,
    liveness: str = "progressing",
    has_in_flight_llm: bool = False,
    last_event_age_seconds: float | None = 10.0,
    block_details: dict | None = None,
    findings: tuple[CheckFinding, ...] = (),
    degraded: bool = False,
    state: dict | None = None,
) -> Incident:
    return Incident(
        plan_entry=PlanEntry(
            plan_id="p1",
            plan_name="my-plan",
            plan_dir="/tmp/my-plan",
            repo_path="/tmp/repo",
            state=state or {"current_state": "planned"},
        ),
        signals=SignalBundle(
            liveness=liveness,
            liveness_reason="test",
            block_details=block_details or {},
            doctor_findings=findings,
            has_in_flight_llm=has_in_flight_llm,
            last_event_age_seconds=last_event_age_seconds,
            degraded=degraded,
        ),
        triage=triage,
    )


class TestClassifier:
    def test_all_good_live_and_progressing(self):
        incident = _incident(triage=Triage.LIVE, liveness="progressing")
        assert classify_incident(incident) is HealthCategory.ALL_GOOD

    def test_terminal_state_all_good(self):
        incident = _incident(
            triage=Triage.LIVE,
            liveness="stalled",
            state={"current_state": "completed"},
        )
        assert classify_incident(incident) is HealthCategory.ALL_GOOD

    def test_false_stall_progressing_with_hanging_llm(self):
        incident = _incident(
            triage=Triage.LIVE,
            liveness="progressing",
            has_in_flight_llm=True,
            last_event_age_seconds=350.0,
        )
        assert classify_incident(incident) is HealthCategory.FALSE_STALL

    def test_false_stall_stalled_with_hanging_llm(self):
        incident = _incident(
            triage=Triage.LIVE,
            liveness="stalled",
            has_in_flight_llm=True,
            last_event_age_seconds=350.0,
        )
        assert classify_incident(incident) is HealthCategory.FALSE_STALL

    def test_environment_issue_from_repo_finding(self):
        incident = _incident(
            triage=Triage.STALE,
            liveness="stalled",
            last_event_age_seconds=10.0,
            findings=(CheckFinding("repo", "skill_sync", "fail", "out of sync"),),
        )
        assert classify_incident(incident) is HealthCategory.ENVIRONMENT_ISSUE

    def test_harness_issue_from_stale_lock(self):
        incident = _incident(
            triage=Triage.LIVE,
            liveness="stalled",
            findings=(CheckFinding("plan", "stale_lock", "fail", "lock is stale"),),
        )
        assert classify_incident(incident) is HealthCategory.HARNESS_ISSUE

    def test_plan_issue_blocked(self):
        incident = _incident(
            triage=Triage.LIVE,
            liveness="stalled",
            block_details={"is_blocked": True, "recoverable_via": "resume"},
        )
        assert classify_incident(incident) is HealthCategory.PLAN_ISSUE

    def test_plan_issue_timeout_imminent(self):
        incident = _incident(
            triage=Triage.LIVE,
            liveness="timeout-imminent",
        )
        assert classify_incident(incident) is HealthCategory.PLAN_ISSUE

    def test_plan_issue_recoverable_via(self):
        incident = _incident(
            triage=Triage.LIVE,
            liveness="quiet",
            block_details={"recoverable_via": "resume"},
        )
        assert classify_incident(incident) is HealthCategory.PLAN_ISSUE

    def test_dead_or_disappeared_no_events(self):
        incident = _incident(
            triage=Triage.STALE,
            liveness="stalled",
            last_event_age_seconds=None,
        )
        assert classify_incident(incident) is HealthCategory.DEAD_OR_DISAPPEARED

    def test_dead_or_disappeared_stale_events(self):
        incident = _incident(
            triage=Triage.STALE,
            liveness="stalled",
            last_event_age_seconds=4000.0,
        )
        assert classify_incident(incident) is HealthCategory.DEAD_OR_DISAPPEARED

    def test_recent_not_dead(self):
        incident = _incident(
            triage=Triage.RECENT,
            liveness="quiet",
            last_event_age_seconds=30.0,
        )
        assert classify_incident(incident) is HealthCategory.UNKNOWN

    def test_degraded_maps_to_unknown(self):
        incident = _incident(
            triage=Triage.LIVE,
            liveness="progressing",
            degraded=True,
        )
        assert classify_incident(incident) is HealthCategory.UNKNOWN


class TestNormalizeDoctorFindings:
    def test_flattens_single_tuple_and_list(self):
        plan = [("stale_lock", "fail", "old")]
        repo = (("skill_sync", "ok", "synced"), ("rubric_drift", "fail", "drift"))
        findings = normalize_doctor_findings(plan, repo)
        assert len(findings) == 3
        assert findings[0] == CheckFinding("plan", "stale_lock", "fail", "old")
        assert findings[1] == CheckFinding("repo", "skill_sync", "ok", "synced")
        assert findings[2] == CheckFinding("repo", "rubric_drift", "fail", "drift")

    def test_ignores_none(self):
        assert normalize_doctor_findings(None, None) == ()


class TestAllowlist:
    def test_unconditional_safe_commands_allowed(self):
        for cmd in ("introspect", "trace", "doctor", "chain status"):
            rec = RepairRecommendation(command=cmd)
            verdict = enforce_allowlist(rec, {})
            assert verdict.allowed is True, cmd
            assert verdict.action is not None

    def test_destructive_git_commands_rejected(self):
        for cmd in (
            "git reset --hard HEAD",
            "git checkout main",
            "git push origin main",
            "git merge feature",
        ):
            rec = RepairRecommendation(command=cmd)
            verdict = enforce_allowlist(rec, {})
            assert verdict.allowed is False, cmd
            assert "destructive" in verdict.reason

    def test_destructive_worktree_delete_rejected(self):
        rec = RepairRecommendation(command="delete worktree /tmp/wt")
        verdict = enforce_allowlist(rec, {})
        assert verdict.allowed is False

    def test_auto_gated_on_context(self):
        context = {
            "plan_name": "my-plan",
            "state": {"current_state": "planned"},
            "block_details": {"recoverable_via": "resume"},
        }
        rec = RepairRecommendation(command="auto", context={})
        verdict = enforce_allowlist(rec, context)
        assert verdict.allowed is True

    def test_auto_rejected_without_context(self):
        rec = RepairRecommendation(command="auto")
        verdict = enforce_allowlist(rec, {})
        assert verdict.allowed is False

    def test_resume_gated_on_context(self):
        rec = RepairRecommendation(command="resume", context={"plan_name": "my-plan"})
        verdict = enforce_allowlist(rec, {"is_resumable": True})
        assert verdict.allowed is True

    def test_chain_start_gated_on_context(self):
        rec = RepairRecommendation(
            command="chain start --one --no-git-refresh --no-push",
            context={"chain_spec_path": "/tmp/chain.yaml"},
        )
        verdict = enforce_allowlist(rec, {"has_pending_milestones": True})
        assert verdict.allowed is True

    def test_unknown_command_rejected(self):
        rec = RepairRecommendation(command="rm -rf /")
        verdict = enforce_allowlist(rec, {})
        assert verdict.allowed is False

    def test_clean_lock_allowed_inside_plan_dir(self):
        rec = RepairRecommendation(
            command="rm /tmp/my-plan/.plan.lock",
            context={"plan_dir": "/tmp/my-plan"},
        )
        verdict = enforce_allowlist(rec, {"plan_dir": "/tmp/my-plan"})
        assert verdict.allowed is True

    def test_clean_lock_rejected_outside_plan_dir(self):
        rec = RepairRecommendation(
            command="rm /etc/passwd/.plan.lock",
            context={"plan_dir": "/tmp/my-plan"},
        )
        verdict = enforce_allowlist(rec, {"plan_dir": "/tmp/my-plan"})
        assert verdict.allowed is False

    def test_terminal_finalized_with_stale_lock_is_harness_issue(self):
        incident = _incident(
            triage=Triage.STALE,
            liveness="stalled",
            state={"current_state": "finalized"},
            findings=(CheckFinding("plan", "stale_lock", "fail", "lock is stale"),),
        )
        assert classify_incident(incident) is HealthCategory.HARNESS_ISSUE

    def test_terminal_finalized_without_stale_lock_is_all_good(self):
        incident = _incident(
            triage=Triage.STALE,
            liveness="stalled",
            state={"current_state": "finalized"},
        )
        assert classify_incident(incident) is HealthCategory.ALL_GOOD

    def test_orphan_subprocess_overrides_live_all_good(self):
        incident = _incident(
            triage=Triage.LIVE,
            liveness="live_process",
            findings=(CheckFinding("plan", "orphan_subprocess", "fail", "orphan shannon pid=99999"),),
        )
        assert classify_incident(incident) is HealthCategory.HARNESS_ISSUE

    def test_kill_allowed_for_known_orphan_pid(self):
        rec = RepairRecommendation(command="kill -9 99999", context={"orphan_pids": [99999]})
        verdict = enforce_allowlist(rec, {"orphan_pids": [99999]})
        assert verdict.allowed is True

    def test_kill_rejected_for_unknown_pid(self):
        rec = RepairRecommendation(command="kill -9 11111", context={"orphan_pids": [99999]})
        verdict = enforce_allowlist(rec, {"orphan_pids": [99999]})
        assert verdict.allowed is False

    def test_kill_rejected_for_claude_daemon(self):
        rec = RepairRecommendation(
            command="kill -9 99999",
            context={"orphan_pids": [99999], "target_category": "claude"},
        )
        verdict = enforce_allowlist(rec, {"orphan_pids": [99999]})
        assert verdict.allowed is False
