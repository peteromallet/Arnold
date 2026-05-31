from __future__ import annotations

import logging
from argparse import Namespace
from pathlib import Path

from megaplan._core import atomic_write_json, read_json, save_state
from megaplan.handlers.review import (
    _finalize_review_outcome,
    _format_review_success_summary,
    _synthesize_review_rework_items,
)
from megaplan.types import STATE_EXECUTED
from megaplan.workers import WorkerResult


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
