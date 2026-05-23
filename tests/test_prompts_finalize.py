from __future__ import annotations

from pathlib import Path

from megaplan._core import atomic_write_json
from megaplan.prompts import create_claude_prompt
from megaplan.workers.hermes import _toolsets_for_phase
from tests.test_prompts import _scaffold


def test_finalize_prompt_drops_critique_history(tmp_path: Path) -> None:
    plan_dir, state = _scaffold(tmp_path)
    atomic_write_json(
        plan_dir / "critique_v1.json",
        {"flags": [{"id": "FLAG-CRITIQUE-ONLY", "concern": "critique-only-token"}]},
    )

    prompt = create_claude_prompt("finalize", state, plan_dir, root=tmp_path)

    assert "Critique history:" not in prompt
    assert "critique-only-token" not in prompt


def test_finalize_prompt_drops_debt_block(tmp_path: Path) -> None:
    plan_dir, state = _scaffold(tmp_path)
    debt_path = tmp_path / ".megaplan" / "debt.json"
    debt_path.parent.mkdir(parents=True)
    atomic_write_json(
        debt_path,
        {
            "items": [
                {
                    "id": "DEBT-999",
                    "status": "open",
                    "concern": "debt-only-token",
                    "subsystem": "finalize",
                    "occurrence_count": 1,
                    "plan_ids": ["p1"],
                }
            ]
        },
    )

    prompt = create_claude_prompt("finalize", state, plan_dir, root=tmp_path)

    assert "Debt watch items" not in prompt
    assert "debt-only-token" not in prompt


def test_finalize_prompt_size_under_15k_tokens(tmp_path: Path) -> None:
    plan_dir, state = _scaffold(tmp_path)
    long_flags = [
        {
            "id": f"FLAG-{index}",
            "concern": "x" * 1000,
            "category": "correctness",
            "severity": "significant",
            "status": "open",
        }
        for index in range(50)
    ]
    atomic_write_json(plan_dir / "critique_v1.json", {"flags": long_flags})

    prompt = create_claude_prompt("finalize", state, plan_dir, root=tmp_path)

    assert len(prompt) < 60000


def test_finalize_instruction_forbids_self_validation(tmp_path: Path) -> None:
    plan_dir, state = _scaffold(tmp_path)

    prompt = create_claude_prompt("finalize", state, plan_dir)

    assert "Do not include `validation` or `coverage_complete` fields" in prompt
    assert "plan_steps_covered" not in prompt
    assert "orphan_tasks" not in prompt
    assert "self-checks plan coverage" not in prompt


def test_finalize_prompt_uses_task_native_dependency_guidance(tmp_path: Path) -> None:
    plan_dir, state = _scaffold(tmp_path)

    prompt = create_claude_prompt("finalize", state, plan_dir)

    assert "task-native serial execution" in prompt
    assert "real prerequisites only" in prompt
    assert "one dependency-ready task at a time" in prompt
    assert "stable user-facing task ID" in prompt
    assert "deterministic safe filesystem/task keys" in prompt
    legacy_first_group = "batch" + "_1"
    retired_capacity_key = "max_tasks" + "_per_batch"
    legacy_dependency_verb = "spr" + "ead"
    assert legacy_first_group not in prompt
    assert retired_capacity_key not in prompt
    assert "batch" + "-size" not in prompt
    assert "batch" + " size" not in prompt
    assert legacy_dependency_verb not in prompt.lower()


def test_finalize_has_no_hermes_file_toolset() -> None:
    assert _toolsets_for_phase("finalize") is None
