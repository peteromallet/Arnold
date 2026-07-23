from __future__ import annotations

from arnold_pipelines.megaplan.workers.hermes import (
    _finalize_structural_repair_prompt,
    _toolsets_for_phase,
)


def test_finalize_uses_explicit_empty_tool_filter() -> None:
    # None means "load all tools" to AIAgent; finalize must request no tools.
    assert _toolsets_for_phase("finalize") == []


def test_finalize_structural_repair_is_bounded_to_candidate_errors_and_schema() -> None:
    candidate = {
        "task_contract_version": 1,
        "tasks": [{"id": "T1", "description": "Keep this semantic task."}],
        "validation_jobs": [],
    }
    error = ValueError(
        "additional property task_contract_version; "
        "missing required auto_attributed_files, commands_run, evidence_files"
    )
    schema = {
        "type": "object",
        "properties": {
            "task_contract_version": {"type": "integer"},
            "tasks": {"type": "array", "items": {"type": "object"}},
            "validation_jobs": {"type": "array", "items": {"type": "object"}},
        },
    }

    prompt = _finalize_structural_repair_prompt(candidate, error, schema)

    assert "Keep this semantic task." in prompt
    assert "task_contract_version" in prompt
    assert "validation_jobs" in prompt
    assert "auto_attributed_files" in prompt
    assert "commands_run" in prompt
    assert "evidence_files" in prompt
    assert "ORIGINAL_FULL_FINALIZE_CONTEXT" not in prompt
    assert len(prompt) < 20_000
