from __future__ import annotations

import pytest

from arnold_pipelines.megaplan.types import CliError
from arnold_pipelines.megaplan.workers.hermes import (
    _default_max_tokens_for_step,
    _finalize_structural_repair_prompt,
    _install_content_tool_call_normalizer,
    _raise_for_terminal_provider_failure,
    _toolsets_for_phase,
)


def test_finalize_uses_explicit_empty_tool_filter() -> None:
    # None means "load all tools" to AIAgent; finalize must request no tools.
    assert _toolsets_for_phase("finalize") == []


def test_hermes_transport_omits_null_tool_fields_for_provider_calls() -> None:
    class FakeAIAgent:
        unary_kwargs = None
        streaming_kwargs = None

        def _interruptible_api_call(self, api_kwargs):
            type(self).unary_kwargs = api_kwargs
            return None

        def _interruptible_streaming_api_call(
            self, api_kwargs, *, on_first_delta=None
        ):
            type(self).streaming_kwargs = api_kwargs
            return None

    _install_content_tool_call_normalizer(FakeAIAgent)
    agent = FakeAIAgent()
    original = {
        "model": "accounts/fireworks/models/kimi-k2p6",
        "messages": [],
        "tools": None,
        "tool_choice": None,
    }

    agent._interruptible_api_call(original)
    agent._interruptible_streaming_api_call(original)

    assert original["tools"] is None
    assert "tools" not in FakeAIAgent.unary_kwargs
    assert "tool_choice" not in FakeAIAgent.unary_kwargs
    assert "tools" not in FakeAIAgent.streaming_kwargs
    assert "tool_choice" not in FakeAIAgent.streaming_kwargs


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


def test_finalize_length_truncation_is_not_laundered_through_structural_repair() -> None:
    result = {
        "messages": [
            {
                "role": "assistant",
                "content": '{"task_contract_version": 2, "tasks": [',
                "finish_reason": "length",
            }
        ]
    }

    with pytest.raises(CliError) as raised:
        _raise_for_terminal_provider_failure(result, step="finalize")

    assert raised.value.code == "worker_output_truncated"
    assert raised.value.extra["provider_failure_category"] == "capacity"


def test_finalize_detects_production_first_response_truncation_shape() -> None:
    # AIAgent does not append the first truncated assistant message to the
    # returned messages list. It reports the terminal condition via
    # failed/error instead; this is the exact production result shape.
    result = {
        "final_response": None,
        "messages": [{"role": "user", "content": "large finalize prompt"}],
        "api_calls": 1,
        "completed": False,
        "failed": True,
        "error": "First response truncated due to output length limit",
    }

    with pytest.raises(CliError) as raised:
        _raise_for_terminal_provider_failure(result, step="finalize")

    assert raised.value.code == "worker_output_truncated"
    assert raised.value.extra == {"provider_failure_category": "capacity"}


def test_non_finalize_length_response_preserves_existing_recovery_paths() -> None:
    _raise_for_terminal_provider_failure(
        {
            "messages": [
                {"role": "assistant", "content": "partial", "finish_reason": "length"}
            ]
        },
        step="execute",
    )


def test_finalize_and_execute_receive_large_graph_output_budget() -> None:
    assert _default_max_tokens_for_step("finalize") == 65536
    assert _default_max_tokens_for_step("execute") == 65536
    assert _default_max_tokens_for_step("critique") == 32768
