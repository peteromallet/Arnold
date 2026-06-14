from __future__ import annotations

import logging
from argparse import Namespace
from pathlib import Path

from arnold.pipelines.megaplan._core import atomic_write_json, read_json, save_state
import arnold.pipelines.megaplan.handlers.review as review_handler
from arnold.pipelines.megaplan.handlers.review import (
    _finalize_review_outcome,
    _format_review_success_summary,
    _prepare_review_payload,
    _review_infrastructure_failure,
    _synthesize_review_rework_items,
    _wrap_parallel_review_worker,
)
from arnold.pipelines.megaplan.orchestration.transition_policy import (
    TRANSITION_DECISION_REVIEW_DONE_FILENAME,
)
import arnold.pipelines.megaplan.orchestration.transition_policy as transition_policy_module
from arnold.pipelines.megaplan.planning.state import STATE_DONE, STATE_EXECUTED
from arnold.pipelines.megaplan.workers import WorkerResult


def test_rework_uses_real_task_ids() -> None:
    rework_items = _synthesize_review_rework_items(
        [
            {
                "id": "coverage",
                "question": "Does coverage pass?",
                "concerned_task_ids": ["T1", "T3"],
                "findings": [
                    {
                        "detail": "The diff misses two issue examples that are assigned to concrete finalize tasks.",
                        "flagged": True,
                        "status": "blocking",
                        "evidence_file": "pkg/module.py",
                    }
                ],
            }
        ]
    )

    assert [item["task_id"] for item in rework_items] == ["T1", "T3"]
    assert all(item["flag_id"] == "REVIEW-coverage" for item in rework_items)


def test_rework_falls_back_when_missing_concerned_ids(caplog) -> None:
    with caplog.at_level(logging.WARNING):
        rework_items = _synthesize_review_rework_items(
            [
                {
                    "id": "coverage",
                    "question": "Does coverage pass?",
                    "findings": [
                        {
                            "detail": "The diff misses an issue example but the legacy checker omitted task IDs.",
                            "flagged": True,
                            "status": "blocking",
                        }
                    ],
                }
            ]
        )

    assert rework_items[0]["task_id"] == "REVIEW-coverage"
    assert "omitted concerned_task_ids" in caplog.text


def test_review_process_error_is_recoverable_review_infrastructure() -> None:
    payload = {
        "review_verdict": "needs_rework",
        "rework_items": [
            {
                "task_id": "T1",
                "issue": "No verification commands or file inspection were performed before verdict.",
                "expected": "Review should inspect the workspace.",
                "actual": "Premature final verdict.",
                "source": "review_process_error",
                "status": "n/a",
            }
        ],
    }

    assert _review_infrastructure_failure(
        payload,
        issues=[],
        total_tasks=1,
        total_checks=0,
    )


def test_review_infra_classifier_does_not_swallow_failed_must_criterion() -> None:
    payload = {
        "review_verdict": "needs_rework",
        "review_completion_status": "complete",
        "criteria": [
            {
                "name": "Regression is fixed",
                "priority": "must",
                "pass": "fail",
                "evidence": "No file inspection guard covers the real failed branch.",
            }
        ],
        "issues": ["The implementation still fails when the issue text mentions no file inspection."],
        "rework_items": [
            {
                "task_id": "T1",
                "issue": "The no file inspection phrase appears in a genuine rejection.",
                "expected": "Real rework should route to execute.",
                "actual": "The implementation still fails the must criterion.",
                "source": "review_coverage",
            }
        ],
    }

    assert not _review_infrastructure_failure(
        payload,
        issues=payload["issues"],
        total_tasks=1,
        total_checks=0,
    )


def test_review_completion_status_incomplete_is_infrastructure_failure() -> None:
    payload = {
        "review_verdict": "needs_rework",
        "review_completion_status": "incomplete",
        "criteria": [],
        "issues": [],
        "rework_items": [],
        "task_verdicts": [{"task_id": "T1", "reviewer_verdict": "", "evidence_files": []}],
        "sense_check_verdicts": [],
    }

    assert _review_infrastructure_failure(
        payload,
        issues=[],
        total_tasks=1,
        total_checks=0,
    )


def test_incomplete_status_wins_over_untagged_infra_rework_item() -> None:
    payload = {
        "review_verdict": "needs_rework",
        "review_completion_status": "incomplete",
        "criteria": [],
        "issues": ["Incomplete review"],
        "rework_items": [
            {
                "task_id": "T1",
                "issue": "Could not complete repository inspection; premature verdict",
                "expected": "Complete repo inspection",
                "actual": "No inspection performed",
            }
        ],
        "task_verdicts": [
            {"task_id": "T1", "reviewer_verdict": "limited", "evidence_files": ["src/x.py"]}
        ],
        "sense_check_verdicts": [],
    }

    assert _review_infrastructure_failure(
        payload,
        issues=["Incomplete review"],
        total_tasks=1,
        total_checks=0,
    )


def test_blank_review_completion_status_uses_legacy_empty_verdict_fallback() -> None:
    payload = {
        "review_verdict": "needs_rework",
        "review_completion_status": "",
        "criteria": [],
        "issues": [],
        "rework_items": [],
        "task_verdicts": [],
        "sense_check_verdicts": [],
    }

    assert _review_infrastructure_failure(
        payload,
        issues=[],
        total_tasks=1,
        total_checks=0,
    )


def test_review_infra_classifier_does_not_swallow_blocking_rework_item() -> None:
    payload = {
        "review_verdict": "needs_rework",
        "review_completion_status": "complete",
        "criteria": [],
        "issues": ["Blocking rework mentions no file inspection but is still real."],
        "rework_items": [
            {
                "task_id": "T1",
                "issue": "Blocking issue text includes no file inspection as a quoted product phrase.",
                "expected": "The task should be fixed.",
                "actual": "It is still broken.",
                "status": "blocking",
            }
        ],
    }

    assert not _review_infrastructure_failure(
        payload,
        issues=payload["issues"],
        total_tasks=1,
        total_checks=0,
    )


def test_review_success_summary_explains_non_passing_non_blocking_criteria() -> None:
    summary = _format_review_success_summary(
        [
            {"name": "A", "pass": "pass"},
            {"name": "B", "pass": True},
            {"name": "C", "pass": "waived"},
            {"name": "D", "pass": "deferred_human"},
        ]
    )

    assert summary == (
        "Review complete: 2/4 success criteria passed "
        "(1 waived, 1 deferred to human)."
    )


def test_review_success_summary_all_passed_has_no_breakdown() -> None:
    summary = _format_review_success_summary(
        [
            {"name": "A", "pass": "pass"},
            {"name": "B", "pass": True},
        ]
    )

    assert summary == "Review complete: 2/2 success criteria passed."


def test_review_success_summary_explains_non_blocking_failed_criteria() -> None:
    summary = _format_review_success_summary(
        [
            {"name": "A", "pass": "pass"},
            {"name": "B", "pass": "fail"},
            {"name": "C", "pass": False},
        ]
    )

    assert summary == (
        "Review complete: 1/3 success criteria passed "
        "(2 failed but non-blocking)."
    )


def _make_review_state(tmp_path: Path, *, iteration: int = 1, invocation_id: str = "inv-review") -> tuple[Path, Path, dict]:
    plan_dir = tmp_path / "plan"
    project_dir = tmp_path / "project"
    plan_dir.mkdir()
    project_dir.mkdir()
    state = {
        "name": "plan",
        "idea": "review",
        "current_state": STATE_EXECUTED,
        "active_step": {"step": "review", "run_id": f"run-{iteration}"},
        "iteration": iteration,
        "created_at": "2026-05-21T00:00:00Z",
        "config": {"project_dir": str(project_dir), "robustness": "full"},
        "sessions": {},
        "plan_versions": [{"version": 1, "file": "plan_v1.md"}],
        "history": [],
        "meta": {"notes": [], "overrides": [], "total_cost_usd": 0.0, "current_invocation_id": invocation_id},
    }
    save_state(plan_dir, state)
    atomic_write_json(
        plan_dir / "finalize.json",
        {
            "tasks": [{"id": "T1", "status": "done", "description": "task"}],
            "sense_checks": [{"id": "SC1", "task_id": "T1", "question": "Question?", "check": "Check."}],
        },
    )
    return plan_dir, project_dir, state


def _approved_review_payload(**overrides) -> dict:
    payload = {
        "review_verdict": "approved",
        "review_completion_status": "complete",
        "repository_inspected": True,
        "criteria": [{"name": "Implementation", "pass": "pass"}],
        "issues": [],
        "rework_items": [],
        "summary": "approved",
        "task_verdicts": [{"task_id": "T1", "reviewer_verdict": "Looks correct.", "evidence_files": ["pkg/module.py"]}],
        "sense_check_verdicts": [{"sense_check_id": "SC1", "verdict": "Confirmed."}],
    }
    payload.update(overrides)
    return payload


def _review_worker(payload: dict, *, session_id: str = "session") -> WorkerResult:
    return WorkerResult(
        payload=payload,
        raw_output="review",
        duration_ms=1,
        cost_usd=0.0,
        session_id=session_id,
        prompt_tokens=0,
        completion_tokens=0,
        total_tokens=0,
    )


def _write_review_evidence(plan_dir: Path, evidence: list[dict], *, head_sha=None, invocation_id: str = "inv-review") -> None:
    atomic_write_json(
        plan_dir / "review_evidence.json",
        {
            "evidence": evidence,
            "base_sha": "base",
            "head_sha": head_sha,
            "invocation_id": invocation_id,
        },
    )


def _finalize_review_for_test(tmp_path: Path, plan_dir: Path, state: dict, payload: dict) -> dict:
    return _finalize_review_outcome(
        root=tmp_path,
        args=Namespace(plan="plan"),
        plan_dir=plan_dir,
        state=state,
        worker=_review_worker(payload),
        agent="codex",
        mode="persistent",
        refreshed=False,
        robustness="full",
    )


def test_parallel_review_worker_wrapper_preserves_rate_limit_exactly() -> None:
    parallel_result = WorkerResult(
        payload={"criteria_payload": {"review_verdict": "approved"}},
        raw_output="parallel",
        duration_ms=12,
        cost_usd=0.25,
        session_id="parallel-session",
        prompt_tokens=3,
        completion_tokens=4,
        total_tokens=7,
        rate_limit={"values": [{"provider": "review", "remaining": 2}]},
    )

    wrapped = _wrap_parallel_review_worker({"review_verdict": "approved"}, parallel_result)

    assert wrapped.payload == {"review_verdict": "approved"}
    assert wrapped.rate_limit == parallel_result.rate_limit
    assert wrapped.prompt_tokens == 3
    assert wrapped.session_id is None


def test_review_does_not_mutate_finalize_json(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    project_dir = tmp_path / "project"
    plan_dir.mkdir()
    project_dir.mkdir()
    state = {
        "name": "plan",
        "idea": "review",
        "current_state": STATE_EXECUTED,
        "iteration": 1,
        "created_at": "2026-05-21T00:00:00Z",
        "config": {"project_dir": str(project_dir), "robustness": "full"},
        "sessions": {},
        "plan_versions": [{"version": 1, "file": "plan_v1.md"}],
        "history": [],
        "meta": {"notes": [], "overrides": [], "total_cost_usd": 0.0},
    }
    save_state(plan_dir, state)
    atomic_write_json(
        plan_dir / "finalize.json",
        {
            "tasks": [{"id": "T1", "status": "done", "description": "task"}],
            "sense_checks": [{"id": "SC1", "task_id": "T1", "question": "Question?", "check": "Check."}],
        },
    )
    before = (plan_dir / "finalize.json").read_bytes()
    payload = {
        "review_verdict": "approved",
        "criteria": [],
        "issues": [],
        "rework_items": [],
        "summary": "approved",
        "task_verdicts": [{"task_id": "T1", "reviewer_verdict": "Looks correct.", "evidence_files": ["pkg/module.py"]}],
        "sense_check_verdicts": [{"sense_check_id": "SC1", "verdict": "Confirmed."}],
    }
    atomic_write_json(plan_dir / "review.json", payload)
    worker = WorkerResult(
        payload=payload,
        raw_output="review",
        duration_ms=1,
        cost_usd=0.0,
        session_id="session",
        prompt_tokens=0,
        completion_tokens=0,
        total_tokens=0,
    )

    _finalize_review_outcome(
        root=tmp_path,
        args=Namespace(plan="plan"),
        plan_dir=plan_dir,
        state=state,
        worker=worker,
        agent="codex",
        mode="persistent",
        refreshed=False,
        robustness="full",
    )

    assert (plan_dir / "finalize.json").read_bytes() == before
    review = read_json(plan_dir / "review.json")
    assert review["task_verdicts"][0]["task_id"] == "T1"
    assert review["sense_check_verdicts"][0]["sense_check_id"] == "SC1"


def test_review_final_md_preserves_contract_sections(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    project_dir = tmp_path / "project"
    plan_dir.mkdir()
    project_dir.mkdir()
    state = {
        "name": "plan",
        "idea": "review",
        "current_state": STATE_EXECUTED,
        "iteration": 1,
        "created_at": "2026-05-21T00:00:00Z",
        "config": {"project_dir": str(project_dir), "robustness": "full"},
        "sessions": {},
        "plan_versions": [{"version": 1, "file": "plan_v1.md"}],
        "history": [],
        "meta": {"notes": [], "overrides": [], "total_cost_usd": 0.0},
    }
    save_state(plan_dir, state)
    atomic_write_json(
        plan_dir / "finalize.json",
        {
            "tasks": [{"id": "T1", "status": "done", "description": "task"}],
            "sense_checks": [{"id": "SC1", "task_id": "T1", "question": "Question?", "check": "Check."}],
            "watch_items": [],
            "meta_commentary": "ok",
            "provides": [
                {
                    "name": "Planner surface",
                    "description": "",
                    "interfaces": [
                        {
                            "symbol": "Planner.run",
                            "signature": "Planner.run(config) -> None",
                            "path": "megaplan/planner.py",
                        }
                    ],
                }
            ],
            "assumes": [
                {
                    "name": "Runtime contract",
                    "upstream_milestone": "m1",
                    "interfaces": [
                        {
                            "symbol": "Runtime.run",
                            "signature": "Runtime.run(config) -> None",
                            "path": "megaplan/runtime.py",
                        }
                    ],
                }
            ],
        },
    )
    payload = {
        "review_verdict": "approved",
        "criteria": [],
        "issues": [],
        "rework_items": [],
        "summary": "approved",
        "task_verdicts": [{"task_id": "T1", "reviewer_verdict": "Looks correct.", "evidence_files": ["pkg/module.py"]}],
        "sense_check_verdicts": [{"sense_check_id": "SC1", "verdict": "Confirmed."}],
    }
    atomic_write_json(plan_dir / "review.json", payload)
    worker = WorkerResult(
        payload=payload,
        raw_output="review",
        duration_ms=1,
        cost_usd=0.0,
        session_id="session",
        prompt_tokens=0,
        completion_tokens=0,
        total_tokens=0,
    )

    _finalize_review_outcome(
        root=tmp_path,
        args=Namespace(plan="plan"),
        plan_dir=plan_dir,
        state=state,
        worker=worker,
        agent="codex",
        mode="persistent",
        refreshed=False,
        robustness="full",
    )

    final_md = (plan_dir / "final.md").read_text(encoding="utf-8")
    assert "## Provides" in final_md
    assert "## Assumes" in final_md
    assert "`Planner.run`" in final_md


def test_review_done_transition_decision_is_written_before_success_bookkeeping(
    tmp_path: Path,
    monkeypatch,
) -> None:
    plan_dir = tmp_path / "plan"
    project_dir = tmp_path / "project"
    plan_dir.mkdir()
    project_dir.mkdir()
    state = {
        "name": "plan",
        "idea": "review",
        "current_state": STATE_EXECUTED,
        "iteration": 2,
        "created_at": "2026-05-21T00:00:00Z",
        "config": {"project_dir": str(project_dir), "robustness": "full"},
        "sessions": {},
        "plan_versions": [{"version": 1, "file": "plan_v1.md"}],
        "history": [],
        "meta": {"notes": [], "overrides": [], "total_cost_usd": 0.0, "current_invocation_id": "inv-1"},
    }
    save_state(plan_dir, state)
    atomic_write_json(
        plan_dir / "finalize.json",
        {
            "tasks": [{"id": "T1", "status": "done", "description": "task"}],
            "sense_checks": [{"id": "SC1", "task_id": "T1", "question": "Question?", "check": "Check."}],
        },
    )
    atomic_write_json(
        plan_dir / "review_evidence.json",
        {
            "evidence": [],
            "base_sha": "base",
            "head_sha": None,
            "invocation_id": "inv-1",
        },
    )
    payload = {
        "review_verdict": "approved",
        "criteria": [],
        "issues": [],
        "rework_items": [],
        "summary": "approved",
        "task_verdicts": [{"task_id": "T1", "reviewer_verdict": "Looks correct.", "evidence_files": ["pkg/module.py"]}],
        "sense_check_verdicts": [{"sense_check_id": "SC1", "verdict": "Confirmed."}],
    }
    worker = WorkerResult(
        payload=payload,
        raw_output="review",
        duration_ms=1,
        cost_usd=0.0,
        session_id="session",
        prompt_tokens=0,
        completion_tokens=0,
        total_tokens=0,
    )

    def assert_decision_exists_before_final_md(*args, **kwargs):
        assert (plan_dir / TRANSITION_DECISION_REVIEW_DONE_FILENAME).exists()
        return "# final"

    monkeypatch.setattr(review_handler, "render_final_md", assert_decision_exists_before_final_md)

    response = _finalize_review_outcome(
        root=tmp_path,
        args=Namespace(plan="plan"),
        plan_dir=plan_dir,
        state=state,
        worker=worker,
        agent="codex",
        mode="persistent",
        refreshed=False,
        robustness="full",
    )

    decision = read_json(plan_dir / TRANSITION_DECISION_REVIEW_DONE_FILENAME)
    assert decision["status"] == "allowed"
    assert decision["action"] == "allow_transition"
    assert decision["from_state"] == STATE_EXECUTED
    assert decision["to_state"] == STATE_DONE
    assert decision["invocation_id"] == "inv-1"
    assert decision["routing_provenance"]["next_action"] == "mark_done"
    assert response["success"] is True
    assert state["current_state"] == STATE_DONE


def test_review_done_policy_denial_keeps_review_open_and_preserves_final_md(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    project_dir = tmp_path / "project"
    plan_dir.mkdir()
    project_dir.mkdir()
    state = {
        "name": "plan",
        "idea": "review",
        "current_state": STATE_EXECUTED,
        "active_step": {"step": "review", "run_id": "run-1"},
        "iteration": 3,
        "created_at": "2026-05-21T00:00:00Z",
        "config": {"project_dir": str(project_dir), "robustness": "full"},
        "sessions": {},
        "plan_versions": [{"version": 1, "file": "plan_v1.md"}],
        "history": [],
        "meta": {"notes": [], "overrides": [], "total_cost_usd": 0.0, "current_invocation_id": "inv-denied"},
    }
    save_state(plan_dir, state)
    atomic_write_json(
        plan_dir / "finalize.json",
        {
            "tasks": [{"id": "T1", "status": "done", "description": "task"}],
            "sense_checks": [{"id": "SC1", "task_id": "T1", "question": "Question?", "check": "Check."}],
        },
    )
    (plan_dir / "final.md").write_text("previous final", encoding="utf-8")
    atomic_write_json(
        plan_dir / "review_evidence.json",
        {
            "evidence": [
                {
                    "kind": "green_suite",
                    "status": "unsatisfied",
                    "summary": "tests failed",
                    "details": {"required": True},
                    "trust_class": "evidence",
                }
            ],
            "base_sha": "base",
            "head_sha": None,
            "invocation_id": "inv-denied",
        },
    )
    payload = {
        "review_verdict": "approved",
        "review_completion_status": "complete",
        "criteria": [],
        "issues": [],
        "rework_items": [],
        "summary": "approved",
        "task_verdicts": [{"task_id": "T1", "reviewer_verdict": "Looks correct.", "evidence_files": ["pkg/module.py"]}],
        "sense_check_verdicts": [{"sense_check_id": "SC1", "verdict": "Confirmed."}],
    }
    worker = WorkerResult(
        payload=payload,
        raw_output="review",
        duration_ms=1,
        cost_usd=0.0,
        session_id="session",
        prompt_tokens=0,
        completion_tokens=0,
        total_tokens=0,
    )

    response = _finalize_review_outcome(
        root=tmp_path,
        args=Namespace(plan="plan"),
        plan_dir=plan_dir,
        state=state,
        worker=worker,
        agent="codex",
        mode="persistent",
        refreshed=False,
        robustness="full",
    )

    review = read_json(plan_dir / "review.json")
    decision = read_json(plan_dir / TRANSITION_DECISION_REVIEW_DONE_FILENAME)
    phase_result = read_json(plan_dir / "phase_result.json")
    persisted_state = read_json(plan_dir / "state.json")
    denial = review["outcome"]["policy_denial"]

    assert review["outcome"]["result"] == "policy_denied"
    assert review["outcome"]["state"] == STATE_EXECUTED
    assert review["outcome"]["next_step"] == "review"
    assert denial["retryable"] is True
    assert denial["next_action"] == "review"
    assert denial["denial_kind"] == "policy_denied"
    assert "fresh required evidence unsatisfied: green_suite" in denial["reasons"]
    assert decision["status"] == "denied"
    assert decision["action"] == "deny_transition"
    assert decision["routing_provenance"]["denial_kind"] == "policy_denied"
    assert decision["routing_provenance"]["next_action"] == "review"
    assert (plan_dir / "final.md").read_text(encoding="utf-8") == "previous final"
    assert state["current_state"] == STATE_EXECUTED
    assert "active_step" not in state
    assert persisted_state["current_state"] == STATE_EXECUTED
    assert "active_step" not in persisted_state
    assert state["history"][-1]["result"] == "policy_denied"
    assert response["success"] is False
    assert response["state"] == STATE_EXECUTED
    assert response["next_step"] == "review"
    assert response["policy_denial"]["retryable"] is True
    assert response["_phase_outcome"] == "blocked_by_quality"
    assert phase_result["exit_kind"] == "blocked_by_quality"


def test_review_done_allowed_persists_decision_and_success_artifacts(tmp_path: Path) -> None:
    plan_dir, _project_dir, state = _make_review_state(tmp_path, iteration=4, invocation_id="inv-allowed")
    _write_review_evidence(
        plan_dir,
        [
            {
                "kind": "green_suite",
                "status": "satisfied",
                "summary": "tests passed",
                "details": {"required": True},
                "trust_class": "evidence",
            }
        ],
        invocation_id="inv-allowed",
    )

    response = _finalize_review_for_test(tmp_path, plan_dir, state, _approved_review_payload())

    review = read_json(plan_dir / "review.json")
    decision = read_json(plan_dir / TRANSITION_DECISION_REVIEW_DONE_FILENAME)
    phase_result = read_json(plan_dir / "phase_result.json")
    persisted_state = read_json(plan_dir / "state.json")

    assert response["success"] is True
    assert response["state"] == STATE_DONE
    assert review["outcome"]["result"] == "success"
    assert decision["status"] == "allowed"
    assert decision["action"] == "allow_transition"
    assert decision["from_state"] == STATE_EXECUTED
    assert decision["to_state"] == STATE_DONE
    assert decision["routing_provenance"]["retryable"] is False
    assert decision["routing_provenance"]["next_action"] == "mark_done"
    assert decision["routing_provenance"]["denial_kind"] is None
    assert decision["routing_provenance"]["fresh_evidence_path"] == "review_evidence.json"
    assert (plan_dir / "final.md").exists()
    assert state["current_state"] == STATE_DONE
    assert persisted_state["current_state"] == STATE_DONE
    assert state["history"][-1]["result"] == "success"
    assert phase_result["exit_kind"] == "success"


def test_review_done_required_evidence_denial_rewrites_review_but_not_success_final(
    tmp_path: Path,
) -> None:
    plan_dir, _project_dir, state = _make_review_state(tmp_path, iteration=5, invocation_id="inv-required-denied")
    (plan_dir / "final.md").write_text("success from an earlier review", encoding="utf-8")
    _write_review_evidence(
        plan_dir,
        [
            {
                "kind": "green_suite",
                "status": "unsatisfied",
                "summary": "tests failed",
                "details": {"required": True},
                "trust_class": "evidence",
                "artifact": {"path": "review_evidence.json", "artifact_type": "json"},
            }
        ],
        invocation_id="inv-required-denied",
    )

    response = _finalize_review_for_test(tmp_path, plan_dir, state, _approved_review_payload())

    review = read_json(plan_dir / "review.json")
    decision = read_json(plan_dir / TRANSITION_DECISION_REVIEW_DONE_FILENAME)
    phase_result = read_json(plan_dir / "phase_result.json")
    receipts = list(plan_dir.glob("step_receipt_review_v*.json"))
    assert len(receipts) == 1
    receipt = read_json(receipts[0])

    assert review["outcome"]["result"] == "policy_denied"
    assert review["outcome"]["state"] == STATE_EXECUTED
    assert review["outcome"]["next_step"] == "review"
    assert review["outcome"]["policy_denial"]["retryable"] is True
    assert review["outcome"]["policy_denial"]["next_action"] == "review"
    assert "fresh required evidence unsatisfied: green_suite" in review["outcome"]["policy_denial"]["reasons"]
    assert decision["status"] == "denied"
    assert decision["would_block_reasons"] == ["fresh required evidence unsatisfied: green_suite"]
    assert decision["routing_provenance"]["retryable"] is True
    assert decision["routing_provenance"]["next_action"] == "review"
    assert decision["routing_provenance"]["denial_kind"] == "policy_denied"
    assert decision["routing_provenance"]["evidence_refs_compact"][0]["artifact_path"] == "review_evidence.json"
    assert (plan_dir / "final.md").read_text(encoding="utf-8") == "success from an earlier review"
    assert state["current_state"] == STATE_EXECUTED
    assert read_json(plan_dir / "state.json")["current_state"] == STATE_EXECUTED
    assert state["history"][-1]["result"] == "policy_denied"
    assert receipt["verdict"] == "policy_denied"
    assert response["success"] is False
    assert response["state"] == STATE_EXECUTED
    assert response["policy_denial"]["retryable"] is True
    assert response["next_step"] == "review"
    assert phase_result["exit_kind"] == "blocked_by_quality"


def test_review_done_stale_required_denial_loses_to_freshness_advisory(
    tmp_path: Path,
    monkeypatch,
) -> None:
    plan_dir, _project_dir, state = _make_review_state(tmp_path, iteration=6, invocation_id="inv-stale")
    _write_review_evidence(
        plan_dir,
        [
            {
                "kind": "green_suite",
                "status": "unsatisfied",
                "summary": "stale test failure",
                "details": {"required": True},
                "trust_class": "evidence",
            }
        ],
        head_sha="old-head",
        invocation_id="inv-stale",
    )

    class Completed:
        stdout = "new-head\n"

    monkeypatch.setattr(transition_policy_module.subprocess, "run", lambda *args, **kwargs: Completed())

    response = _finalize_review_for_test(tmp_path, plan_dir, state, _approved_review_payload())

    decision = read_json(plan_dir / TRANSITION_DECISION_REVIEW_DONE_FILENAME)
    review = read_json(plan_dir / "review.json")
    assert response["success"] is True
    assert response["state"] == STATE_DONE
    assert review["outcome"]["result"] == "success"
    assert decision["status"] == "allowed"
    assert decision["would_block_reasons"] == []
    assert "stale review evidence is advisory" in decision["routing_provenance"]["advisory"]
    assert state["current_state"] == STATE_DONE


def test_review_done_unsupported_blockers_are_policy_denied(tmp_path: Path) -> None:
    plan_dir, _project_dir, state = _make_review_state(tmp_path, iteration=7, invocation_id="inv-unsupported")
    _write_review_evidence(plan_dir, [], invocation_id="inv-unsupported")
    payload = _approved_review_payload(
        unsupported_blockers=[
            {
                "task_id": "T1",
                "status": "blocking",
                "issue": "Reviewer approved while preserving an unsupported blocker.",
            }
        ]
    )

    response = _finalize_review_for_test(tmp_path, plan_dir, state, payload)

    review = read_json(plan_dir / "review.json")
    decision = read_json(plan_dir / TRANSITION_DECISION_REVIEW_DONE_FILENAME)
    assert response["success"] is False
    assert review["outcome"]["result"] == "policy_denied"
    assert "approved review still contains blocking rework" in decision["would_block_reasons"]
    assert "approved review still contains unsupported blockers" in decision["would_block_reasons"]
    assert state["current_state"] == STATE_EXECUTED


def test_review_done_no_inspection_approval_is_policy_denied(tmp_path: Path) -> None:
    plan_dir, _project_dir, state = _make_review_state(tmp_path, iteration=8, invocation_id="inv-no-inspection")
    _write_review_evidence(plan_dir, [], invocation_id="inv-no-inspection")
    payload = _approved_review_payload(repository_inspected=False, summary="approved without inspection")

    response = _finalize_review_for_test(tmp_path, plan_dir, state, payload)

    review = read_json(plan_dir / "review.json")
    decision = read_json(plan_dir / TRANSITION_DECISION_REVIEW_DONE_FILENAME)
    assert response["success"] is False
    assert review["outcome"]["result"] == "policy_denied"
    assert decision["status"] == "denied"
    assert "review approval did not inspect the repository" in decision["would_block_reasons"]
    assert review["outcome"]["policy_denial"]["next_action"] == "review"
    assert state["current_state"] == STATE_EXECUTED


# ── T17: _prepare_review_payload bookkeeping default tests ──────────────────
# These prove that migrated review bookkeeping defaults come from the handler's
# _prepare_review_payload(), not from _normalize_worker_payload().

def test_prepare_review_payload_sets_missing_bookkeeping_arrays() -> None:
    """Prove _prepare_review_payload defaults checks/pre_check_flags/
    verified_flag_ids/disputed_flag_ids when missing from the payload."""
    payload: dict[str, object] = {
        "review_verdict": "approved",
        "criteria": [],
        "issues": [],
        "rework_items": [],
        "summary": "ok",
        "task_verdicts": [],
        "sense_check_verdicts": [],
    }
    result = _prepare_review_payload(payload)

    assert result["checks"] == []
    assert result["pre_check_flags"] == []
    assert result["verified_flag_ids"] == []
    assert result["disputed_flag_ids"] == []


def test_prepare_review_payload_preserves_existing_bookkeeping_arrays() -> None:
    """Prove _prepare_review_payload preserves existing bookkeeping values."""
    payload: dict[str, object] = {
        "review_verdict": "needs_rework",
        "criteria": [],
        "issues": [],
        "rework_items": [],
        "checks": [{"id": "coverage", "question": "...", "findings": []}],
        "pre_check_flags": [{"id": "X", "check": "source_touch", "detail": "ok", "severity": "minor", "evidence_file": ""}],
        "verified_flag_ids": ["FLAG-1"],
        "disputed_flag_ids": ["FLAG-2"],
    }
    result = _prepare_review_payload(payload)

    assert result["checks"] == payload["checks"]
    assert result["verified_flag_ids"] == ["FLAG-1"]
    assert result["disputed_flag_ids"] == ["FLAG-2"]
    # pre_check_flags get normalized — the provided flags should be preserved
    assert len(result["pre_check_flags"]) == 1
    assert result["pre_check_flags"][0]["id"] == "X"


def test_prepare_review_payload_uses_explicit_pre_check_flags() -> None:
    """Prove _prepare_review_payload normalizes and uses explicitly provided
    pre_check_flags even when the payload also carries its own."""
    payload: dict[str, object] = {
        "review_verdict": "approved",
        "pre_check_flags": [{"id": "FROM_PAYLOAD", "check": "old", "detail": "old"}],
    }
    supplied = [
        {"id": "FROM_SUPPLIED", "check": "source_touch", "detail": "The diff touches src", "severity": "minor"},
    ]
    result = _prepare_review_payload(payload, pre_check_flags=supplied)

    assert result["pre_check_flags"][0]["id"] == "FROM_SUPPLIED"
    assert result["pre_check_flags"][0]["check"] == "source_touch"


def test_prepare_review_payload_handles_none_bookkeeping_keys() -> None:
    """Prove _prepare_review_payload replaces None-valued bookkeeping keys
    with empty lists instead of leaving them as None."""
    payload: dict[str, object] = {
        "review_verdict": "approved",
        "checks": None,
        "verified_flag_ids": None,
        "disputed_flag_ids": None,
    }
    result = _prepare_review_payload(payload)

    assert result["checks"] == []
    assert result["verified_flag_ids"] == []
    assert result["disputed_flag_ids"] == []


def test_prepare_review_payload_is_handler_owned_not_worker_normalized() -> None:
    """Review bookkeeping arrays come from the handler helper, not workers."""
    payload: dict[str, object] = {
        "review_verdict": "approved",
        "criteria": [],
        "issues": [],
        "rework_items": [],
        "summary": "ok",
        "task_verdicts": [],
        "sense_check_verdicts": [],
    }
    prepared = _prepare_review_payload(dict(payload))
    assert prepared["checks"] == []
    assert prepared["pre_check_flags"] == []
    assert prepared["verified_flag_ids"] == []
    assert prepared["disputed_flag_ids"] == []
