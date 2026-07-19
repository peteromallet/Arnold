from __future__ import annotations

import json
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.prompts import _execute_batch_prompt
from arnold_pipelines.megaplan.prompts._projection import (
    MAX_COMPLETED_TASK_RECEIPT_CONTEXT_CHARS,
    MAX_COMPLETED_TASK_RECEIPTS,
    project_completed_task_receipts,
)
from arnold_pipelines.megaplan.types import PlanState


def _task(
    task_id: str,
    *,
    depends_on: list[str] | None = None,
    status: str = "done",
    marker: str = "",
) -> dict[str, object]:
    return {
        "id": task_id,
        "description": f"description:{task_id}:{marker}" + ("d" * 800),
        "depends_on": list(depends_on or []),
        "status": status,
        "executor_notes": f"outcome:{task_id}:{marker}" + ("n" * 1_200),
        "files_changed": [f"src/{task_id}/{index}-{'f' * 300}.py" for index in range(20)],
        "commands_run": [f"pytest {task_id}-{index}-{'c' * 300}" for index in range(20)],
        "evidence_files": [f"evidence/{task_id}/{index}-{'e' * 300}.json" for index in range(20)],
        "reviewer_verdict": "recorded",
    }


def _state(project_dir: Path, *, mode: str) -> PlanState:
    config: dict[str, object] = {
        "project_dir": str(project_dir),
        "auto_approve": False,
        "robustness": "standard",
        "mode": mode,
        "output_path": "output.md",
    }
    if mode == "creative":
        config["form"] = "joke"
        config["primary_criterion"] = "Make the dependency receipt legible."
    return {
        "name": "receipt-test",
        "idea": "Bound completed task replay.",
        "current_state": "executing",
        "iteration": 1,
        "created_at": "2026-07-15T00:00:00Z",
        "config": config,
        "sessions": {},
        "plan_versions": [
            {
                "version": 1,
                "file": "plan_v1.md",
                "hash": "sha256:test",
                "timestamp": "2026-07-15T00:00:00Z",
            }
        ],
        "history": [],
        "meta": {"user_approved_gate": True},
        "last_gate": {},
    }


def _scaffold(tmp_path: Path, tasks: list[dict[str, object]], *, mode: str) -> tuple[Path, PlanState]:
    plan_dir = tmp_path / mode / "plan"
    project_dir = tmp_path / mode / "project"
    plan_dir.mkdir(parents=True)
    project_dir.mkdir(parents=True)
    (plan_dir / "plan_v1.md").write_text(
        "# Plan\n\n## Execution Order\n\nUse dependency receipts before active work.\n",
        encoding="utf-8",
    )
    (plan_dir / "gate_carry.json").write_text(
        json.dumps(
            {
                "version": 1,
                "recommendation": "PROCEED",
                "passed": True,
                "rationale": "The receipt projection is ready for execution.",
                "signals_assessment": "Focused fixture evidence is sufficient.",
                "warnings": [],
                "settled_decisions": [],
                "flag_resolutions": [],
                "accepted_tradeoffs": [],
                "north_star_actions": [],
            }
        ),
        encoding="utf-8",
    )
    (plan_dir / "finalize.json").write_text(
        json.dumps(
            {
                "tasks": tasks,
                "sense_checks": [],
                "user_actions": [],
                "watch_items": [],
                "baseline_test_failures": [],
                "meta_commentary": "",
            }
        ),
        encoding="utf-8",
    )
    return plan_dir, _state(project_dir, mode=mode)


def test_receipts_include_only_completed_dependency_closure() -> None:
    tasks = [
        _task("ROOT", marker="ROOT_REQUIRED_EVIDENCE"),
        _task(
            "DIRECT",
            depends_on=["ROOT"],
            marker="DIRECT_REQUIRED_EVIDENCE",
        ),
        _task("UNRELATED", marker="UNRELATED_RECORD_MUST_NOT_REPLAY"),
        _task("ACTIVE", depends_on=["DIRECT"], status="pending"),
    ]

    receipts = project_completed_task_receipts(
        {"tasks": tasks},
        batch_task_ids=["ACTIVE"],
        completed_task_ids={"ROOT", "DIRECT", "UNRELATED"},
    )

    assert [receipt["task_id"] for receipt in receipts["receipts"]] == [
        "DIRECT",
        "ROOT",
    ]
    assert [receipt["dependency_scope"] for receipt in receipts["receipts"]] == [
        "direct",
        "transitive",
    ]
    assert receipts["completed_task_count"] == 3
    assert receipts["dependency_task_count"] == 2
    assert receipts["unrelated_completed_task_count"] == 1
    assert receipts["omitted_dependency_receipt_count"] == 0
    rendered = json.dumps(receipts)
    assert "DIRECT_REQUIRED_EVIDENCE" in rendered
    assert "ROOT_REQUIRED_EVIDENCE" in rendered
    assert "UNRELATED_RECORD_MUST_NOT_REPLAY" not in rendered


def test_receipts_have_hard_count_and_serialized_size_bounds() -> None:
    dependency_ids = [f"DONE-{index:03d}" for index in range(200)]
    tasks = [_task(task_id, marker=f"MARKER-{task_id}") for task_id in dependency_ids]
    tasks.append(_task("ACTIVE", depends_on=dependency_ids, status="pending"))

    receipts = project_completed_task_receipts(
        {"tasks": tasks},
        batch_task_ids=["ACTIVE"],
        completed_task_ids=set(dependency_ids),
        source_artifact_ref="/plan/finalize.json",
    )

    assert len(receipts["receipts"]) <= MAX_COMPLETED_TASK_RECEIPTS
    assert len(json.dumps(receipts, sort_keys=True, ensure_ascii=False)) <= (
        MAX_COMPLETED_TASK_RECEIPT_CONTEXT_CHARS
    )
    assert receipts["omitted_dependency_receipt_count"] > 0
    assert receipts["overflow"]["task_id_set_sha256"]
    assert "block instead of guessing" in receipts["overflow"]["required_action"]


@pytest.mark.parametrize("mode", ["code", "doc", "creative"])
def test_execute_prompt_variants_do_not_replay_unrelated_completed_records(
    tmp_path: Path,
    mode: str,
) -> None:
    completed_ids = {f"DONE-{index:03d}" for index in range(120)}
    tasks = [
        _task(
            task_id,
            marker=(
                "REQUIRED_DEPENDENCY_RECORD"
                if task_id == "DONE-000"
                else f"UNRELATED_FULL_RECORD_{task_id}"
            ),
        )
        for task_id in sorted(completed_ids)
    ]
    tasks.append(_task("ACTIVE", depends_on=["DONE-000"], status="pending"))
    plan_dir, state = _scaffold(tmp_path, tasks, mode=mode)

    prompt = _execute_batch_prompt(
        state,
        plan_dir,
        ["ACTIVE"],
        completed_ids,
    )

    assert "megaplan.completed_task_receipts.v1" in prompt
    assert "REQUIRED_DEPENDENCY_RECORD" in prompt
    assert "UNRELATED_FULL_RECORD_DONE-001" not in prompt
    assert "UNRELATED_FULL_RECORD_DONE-119" not in prompt
    assert "Already completed task IDs available as dependency context" not in prompt
    assert len(prompt) < 60_000
