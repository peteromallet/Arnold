from __future__ import annotations

from pathlib import Path

from megaplan._core import atomic_write_json, atomic_write_text
import megaplan.prompts as prompt_module
from megaplan.prompts import _execute_batch_prompt
from megaplan.prompts._projection import PromptProjectionCapabilities
from megaplan.types import PlanState


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
    assert ("A" * 1497) + "..." in prompt
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


def test_execute_batch_prompt_forwards_projection_capabilities_to_mode_builder(
    monkeypatch, tmp_path: Path
) -> None:
    plan_dir, state = _scaffold(tmp_path)
    caps = PromptProjectionCapabilities.conservative()
    calls: list[tuple[str, PromptProjectionCapabilities | None]] = []

    def _fake_code(*args, **kwargs):
        calls.append(("code", kwargs.get("projection_capabilities")))
        return "code"

    def _fake_doc(*args, **kwargs):
        calls.append(("doc", kwargs.get("projection_capabilities")))
        return "doc"

    def _fake_creative(*args, **kwargs):
        calls.append(("creative", kwargs.get("projection_capabilities")))
        return "creative"

    monkeypatch.setattr(prompt_module, "_execute_code_batch_prompt", _fake_code)
    monkeypatch.setattr(prompt_module, "_execute_doc_batch_prompt", _fake_doc)
    monkeypatch.setattr(prompt_module, "_execute_creative_batch_prompt", _fake_creative)

    _execute_batch_prompt(state, plan_dir, ["T1"], set(), projection_capabilities=caps)
    state["config"]["mode"] = "doc"
    _execute_batch_prompt(state, plan_dir, ["T1"], set(), projection_capabilities=caps)
    state["config"]["mode"] = "creative"
    _execute_batch_prompt(state, plan_dir, ["T1"], set(), projection_capabilities=caps)

    assert calls == [("code", caps), ("doc", caps), ("creative", caps)]


# ---------------------------------------------------------------------------
# T15: Synthetic projection and prompt-size coverage
# ---------------------------------------------------------------------------


def test_batch_prompt_projects_large_ledger_active_details_retained(
    tmp_path: Path,
) -> None:
    """Large executor notes are truncated; active task descriptions and evidence remain."""
    plan_dir, state = _scaffold(tmp_path)
    long_note = "BLOAT-EXECUTOR-NOTE " * 200
    long_justification = "complexity-justification " * 150
    long_meta = "meta-commentary " * 600

    tasks = []
    for i in range(1, 9):
        tasks.append({
            "id": f"T{i}",
            "description": f"Active task {i}: implement the feature",
            "depends_on": [],
            "status": "pending" if i >= 5 else "done",
            "kind": "code",
            "complexity": 3,
            "executor_notes": long_note,
            "complexity_justification": long_justification,
            "files_changed": [f"src/module_{i}.py"],
            "commands_run": [f"pytest tests/test_feature_{i}.py"],
            "evidence_files": [],
            "reviewer_verdict": "",
        })

    _write_finalize(plan_dir, tasks=tasks, meta_commentary=long_meta)

    prompt = _execute_batch_prompt(
        state, plan_dir, ["T5", "T6"], {"T1", "T2", "T3", "T4"}
    )

    # Long raw strings must be absent (projected/bounded)
    assert long_note not in prompt
    assert long_justification not in prompt
    assert long_meta not in prompt

    # Active task descriptions preserved
    assert "Active task 5: implement the feature" in prompt
    assert "Active task 6: implement the feature" in prompt

    # Evidence preserved
    assert "src/module_5.py" in prompt
    assert "src/module_6.py" in prompt

    # Inactive sentinels omitted — off-batch tasks (T7, T8) not rendered
    assert "Active task 7" not in prompt
    assert "Active task 8" not in prompt


def test_batch_prompt_preserves_exact_scoping_strings(tmp_path: Path) -> None:
    """Exact batch-scoping strings are preserved verbatim in the prompt."""
    plan_dir, state = _scaffold(tmp_path)
    _write_finalize(
        plan_dir,
        tasks=[
            _task("T-EXEC", "Implement the change"),
            _task("T-DONE", "Completed dependency", status="done"),
        ],
    )

    prompt = _execute_batch_prompt(state, plan_dir, ["T-EXEC"], {"T-DONE"})

    # Exact batch framing strings
    assert "Batch framing:" in prompt
    assert "Actionable task IDs for this batch:" in prompt
    assert "Already completed task IDs available as dependency context:" in prompt
    assert "Actionable tasks for this batch:" in prompt
    assert "Completed task context (already satisfied, do not re-execute unless directly required by current edits):" in prompt
    assert "Batch-scoped sense checks:" in prompt
    assert "## Execution context (settled - DO NOT re-litigate)" in prompt
    assert "Debt watch items (do not make these worse):" in prompt

    # Task IDs rendered correctly
    assert "T-EXEC" in prompt
    assert "T-DONE" in prompt


def test_batch_prompt_budget_assertion(tmp_path: Path) -> None:
    """Prompt with 20 tasks and bloated notes stays under 50,000 characters."""
    plan_dir, state = _scaffold(tmp_path)
    long_note = "EXECUTOR_BLOAT " * 80
    long_meta = "META_BLOAT " * 300

    tasks = []
    for i in range(1, 21):
        tasks.append({
            "id": f"T{i}",
            "description": f"Task {i} description text",
            "depends_on": [],
            "status": "done" if i <= 15 else "pending",
            "kind": "code",
            "complexity": 2,
            "executor_notes": long_note,
            "complexity_justification": "Simple task.",
            "files_changed": [f"src/file_{i}.py"],
            "commands_run": [],
            "evidence_files": [],
            "reviewer_verdict": "",
        })

    _write_finalize(plan_dir, tasks=tasks, meta_commentary=long_meta)

    prompt = _execute_batch_prompt(
        state,
        plan_dir,
        [f"T{i}" for i in range(16, 21)],  # T16-T20
        {f"T{i}" for i in range(1, 16)},  # T1-T15
    )

    # Prompt must be well under 50k chars despite bloated source data
    assert len(prompt) < 50_000, f"Prompt size {len(prompt)} exceeds budget"

    # Active batch tasks (T16-T20) must be rendered
    for i in range(16, 21):
        assert f"T{i}" in prompt

    # Off-batch, non-completed task IDs (T21 theoretically) not rendered
    # (Completed tasks T1-T15 appear in completed context by design)


def test_batch_prompt_no_artifact_references_for_no_file_tools(
    tmp_path: Path,
) -> None:
    """With conservative capabilities, prompt renders without checkpoint-write references."""
    plan_dir, state = _scaffold(tmp_path)
    _write_finalize(
        plan_dir,
        tasks=[
            {
                "id": "T1",
                "description": "Implement the feature",
                "depends_on": [],
                "status": "pending",
                "kind": "code",
                "complexity": 2,
                "executor_notes": "Done.",
                "complexity_justification": "Simple.",
                "files_changed": ["src/module.py"],
                "commands_run": ["pytest"],
                "evidence_files": [],
                "reviewer_verdict": "",
            }
        ],
    )

    caps = PromptProjectionCapabilities.conservative()
    prompt = _execute_batch_prompt(
        state, plan_dir, ["T1"], set(), projection_capabilities=caps
    )

    # The prompt should still render (no crash)
    assert len(prompt) > 0
    assert "T1" in prompt

    # With conservative caps (no checkpoint write access), the checkpoint
    # summary should indicate the worker cannot write checkpoints
    assert "This worker cannot write" in prompt


def test_batch_prompt_inactive_sentinels_omitted(tmp_path: Path) -> None:
    """Tasks not in batch or completed set must not appear."""
    plan_dir, state = _scaffold(tmp_path)
    _write_finalize(
        plan_dir,
        tasks=[
            _task("T1", "INACTIVE_SENTINEL_1", status="pending"),
            _task("T2", "Active task 2", status="pending"),
            _task("T3", "Done task 3", status="done"),
            _task("T4", "INACTIVE_SENTINEL_4", status="pending"),
        ],
    )

    prompt = _execute_batch_prompt(state, plan_dir, ["T2"], {"T3"})

    # Active task present
    assert "Active task 2" in prompt
    # Done task present (as completed context)
    assert "Done task 3" in prompt
    # Inactive sentinels absent
    assert "INACTIVE_SENTINEL_1" not in prompt
    assert "INACTIVE_SENTINEL_4" not in prompt
