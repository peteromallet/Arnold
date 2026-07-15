from __future__ import annotations

from pathlib import Path

from arnold.pipelines.megaplan._core import atomic_write_json, atomic_write_text
from arnold.pipelines.megaplan.prompts._projection import MAX_META_COMMENTARY_CHARS
from arnold.pipelines.megaplan.prompts import _execute_batch_prompt
from arnold.pipelines.megaplan.types import PlanState


def _state(project_dir: Path) -> PlanState:
    return {
        "name": "batch-prompt-test",
        "idea": "Harden batch execution prompts without bloating worker context.",
        "current_state": "finalized",
        "iteration": 1,
        "created_at": "2026-05-21T00:00:00Z",
        "config": {
            "project_dir": str(project_dir),
            "auto_approve": False,
            "robustness": "standard",
        },
        "sessions": {},
        "plan_versions": [
            {
                "version": 1,
                "file": "plan_v1.md",
                "hash": "sha256:test",
                "timestamp": "2026-05-21T00:00:00Z",
            }
        ],
        "history": [],
        "meta": {"user_approved_gate": True},
        "last_gate": {},
    }


def _task(task_id: str, description: str, *, status: str = "pending") -> dict[str, object]:
    return {
        "id": task_id,
        "description": description,
        "depends_on": [],
        "status": status,
        "executor_notes": "",
        "files_changed": [],
        "commands_run": [],
        "evidence_files": [],
        "reviewer_verdict": "",
    }


def _scaffold(tmp_path: Path, *, plan_text: str | None = None) -> tuple[Path, PlanState]:
    plan_dir = tmp_path / "plan"
    project_dir = tmp_path / "project"
    plan_dir.mkdir()
    project_dir.mkdir()
    state = _state(project_dir)
    atomic_write_text(
        plan_dir / "plan_v1.md",
        plan_text
        if plan_text is not None
        else "# Plan\n\n## Execution Order\n\nDo foundations before integration.\n\n## Tasks\n",
    )
    atomic_write_json(
        plan_dir / "gate_carry.json",
        {
            "version": 1,
            "recommendation": "PROCEED",
            "passed": True,
            "settled_decisions": [],
        },
    )
    return plan_dir, state


def _write_finalize(
    plan_dir: Path,
    *,
    tasks: list[dict[str, object]],
    meta_commentary: str = "",
) -> None:
    atomic_write_json(
        plan_dir / "finalize.json",
        {
            "tasks": tasks,
            "sense_checks": [
                {
                    "id": f"SC-{task['id']}",
                    "task_id": task["id"],
                    "question": f"Was {task['id']} verified?",
                    "executor_note": "",
                    "verdict": "",
                }
                for task in tasks
            ],
            "user_actions": [],
            "watch_items": [],
            "baseline_test_failures": [],
            "meta_commentary": meta_commentary,
        },
    )


def test_batch_prompt_no_full_finalize_dump(tmp_path: Path) -> None:
    plan_dir, state = _scaffold(tmp_path)
    _write_finalize(
        plan_dir,
        tasks=[
            _task("T-BATCH", "Implement the batch change"),
            _task("T-DONE", "Completed dependency", status="done"),
            _task("T-OFF-BATCH", "OFF_BATCH_UNIQUE_SHOULD_NOT_RENDER"),
        ],
    )

    prompt = _execute_batch_prompt(state, plan_dir, ["T-BATCH"], {"T-DONE"})

    assert "Full execution tracking source of truth" not in prompt
    assert '"id": "T-BATCH"' in prompt
    assert '"id": "T-DONE"' in prompt
    assert "T-OFF-BATCH" not in prompt
    assert "OFF_BATCH_UNIQUE_SHOULD_NOT_RENDER" not in prompt


def test_batch_prompt_includes_settled_decisions(tmp_path: Path) -> None:
    plan_dir, state = _scaffold(tmp_path)
    atomic_write_json(
        plan_dir / "gate_carry.json",
        {
            "version": 1,
            "recommendation": "PROCEED",
            "passed": True,
            "settled_decisions": [
                {
                    "id": "SD7",
                    "decision": "Use gate carry as the execution handoff.",
                    "rationale": "It is the bounded post-gate artifact.",
                },
                {
                    "id": "SD8",
                    "decision": "Do not re-open accepted sequencing tradeoffs.",
                    "rationale": "Gate already settled the order.",
                },
            ],
        },
    )
    _write_finalize(plan_dir, tasks=[_task("T1", "Do it")])

    prompt = _execute_batch_prompt(state, plan_dir, ["T1"], set())

    assert "## Execution context (settled" in prompt
    assert "SD7: Use gate carry as the execution handoff." in prompt
    assert "It is the bounded post-gate artifact." in prompt
    assert "SD8: Do not re-open accepted sequencing tradeoffs." in prompt


def test_batch_prompt_includes_execution_order_summary(tmp_path: Path) -> None:
    plan_dir, state = _scaffold(
        tmp_path,
        plan_text=(
            "# Plan\n\n"
            "## Execution Order\n\n"
            "1. First update the shared prompt helper.\n"
            "2. Then add regression coverage.\n\n"
            "## Validation\n\nRun focused tests.\n"
        ),
    )
    _write_finalize(plan_dir, tasks=[_task("T1", "Do it")])

    prompt = _execute_batch_prompt(state, plan_dir, ["T1"], set())

    assert "## Plan execution order rationale" in prompt
    assert "First update the shared prompt helper." in prompt
    assert "Then add regression coverage." in prompt
    assert "Run focused tests." not in prompt


def test_batch_prompt_includes_meta_commentary_truncated(tmp_path: Path) -> None:
    plan_dir, state = _scaffold(tmp_path)
    meta_commentary = ("A" * 1500) + "TAIL_SHOULD_NOT_RENDER"
    _write_finalize(plan_dir, tasks=[_task("T1", "Do it")], meta_commentary=meta_commentary)

    prompt = _execute_batch_prompt(state, plan_dir, ["T1"], set())

    assert "## Inter-task guidance from finalize" in prompt
    assert ("A" * (MAX_META_COMMENTARY_CHARS - 3)) + "..." in prompt
    assert "TAIL_SHOULD_NOT_RENDER" not in prompt


def test_batch_prompt_no_execution_order_falls_back_gracefully(tmp_path: Path) -> None:
    plan_dir, state = _scaffold(tmp_path, plan_text="# Plan\n\nNo ordering section.\n")
    _write_finalize(plan_dir, tasks=[_task("T1", "Do it")])

    prompt = _execute_batch_prompt(state, plan_dir, ["T1"], set())

    assert "## Plan execution order rationale" in prompt
    assert "(none specified)" in prompt


def test_batch_prompt_size_reasonable(tmp_path: Path) -> None:
    plan_dir, state = _scaffold(
        tmp_path,
        plan_text=(
            "# Plan\n\n## Execution Order\n\n"
            "Complete isolated prompt rendering first, then wire the execution batch context, "
            "then validate with focused and broad tests.\n"
        ),
    )
    atomic_write_json(
        plan_dir / "gate_carry.json",
        {
            "version": 1,
            "recommendation": "PROCEED",
            "passed": True,
            "settled_decisions": [
                {
                    "id": f"SD{index}",
                    "decision": f"Decision {index} " + ("x" * 160),
                    "rationale": f"Rationale {index} " + ("y" * 220),
                }
                for index in range(1, 8)
            ],
        },
    )
    tasks = [
        _task(f"T{index}", f"Task {index}: " + ("implement realistic scoped work. " * 12))
        for index in range(1, 21)
    ]
    for task in tasks[:5]:
        task["status"] = "done"
    _write_finalize(plan_dir, tasks=tasks, meta_commentary="m" * 4000)

    prompt = _execute_batch_prompt(
        state,
        plan_dir,
        ["T6", "T7", "T8", "T9", "T10"],
        {"T1", "T2", "T3", "T4", "T5"},
    )

    assert len(prompt) < 30_000
    assert "T20" not in prompt


def test_batch_prompt_annotates_rework_tasks_with_concrete_review_directives(
    tmp_path: Path,
) -> None:
    plan_dir, state = _scaffold(tmp_path)
    _write_finalize(
        plan_dir,
        tasks=[_task("T1", "Old finalize prose that no longer matches the rework target.")],
    )

    prompt = _execute_batch_prompt(
        state,
        plan_dir,
        ["T1"],
        set(),
        rework_context={
            "rework_items": [
                {
                    "task_id": "T1",
                    "issue": "Rewrite the metadata file instead of replaying the old artifact-copy step.",
                    "expected": "plan_v3.meta.json carries only the 21 approved selectors.",
                    "actual": "The stale 312-selector expansion is still present.",
                    "evidence_file": ".megaplan/plans/example/plan_v3.meta.json",
                    "source": "review_metadata_check",
                }
            ]
        },
    )

    assert '"review_rework_directives"' in prompt
    assert "Rewrite the metadata file instead of replaying the old artifact-copy step." in prompt
    assert '"review_rework_evidence_files"' in prompt
    assert ".megaplan/plans/example/plan_v3.meta.json" in prompt
    assert "higher-authority instructions than stale original task prose" in prompt
