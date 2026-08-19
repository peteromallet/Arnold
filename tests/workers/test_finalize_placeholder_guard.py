"""Regression: finalize must never accept an unfilled schema template as a payload.

Failure lineage (astrid-first m5, occurrence 0c582f90a36d):
- 2026-08-19T12:13:52Z resume: the finalize agent echoed the JSON schema template
  (``id: "string"``, ``complexity: 0``, ``task_contract_version: 0``) as its
  final response.  ``parse_agent_output`` accepted it as a payload because it is
  syntactically valid JSON, and the finalize validator rejected it with an
  opaque ``invalid_finalize`` that had no repair lane -> plan hard-blocked.

The fix:
1. ``_is_finalize_placeholder_payload`` detects placeholder-shaped finalize
   payloads at the parse boundary (both the template-file gate and the inline
   final-response parse, including the summary-prompt re-fill).
2. ``handlers/finalize.py::_persist_invalid_finalize_feedback`` makes any
   residual ``invalid_finalize`` repairable by persisting structured feedback
   for the next finalizer invocation.

These tests prove: placeholder -> discarded -> summary prompt recovers a real
fill; real graph -> passes through untouched; placeholder with no repair ->
clean ``worker_parse_error`` (never accepted as payload).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.finalize_contract import FINALIZE_MODEL_OUTPUT_SCHEMA
from arnold_pipelines.megaplan.types import CliError
from arnold_pipelines.megaplan.workers.hermes import (
    _is_finalize_placeholder_payload,
    parse_agent_output,
)

PLACEHOLDER_PAYLOAD = {
    "task_contract_version": 0,
    "tasks": [
        {
            "id": "string",
            "objective": "string",
            "description": "string",
            "status": "pending",
            "kind": "code",
            "complexity": 0,
            "complexity_justification": "string",
            "estimated_minutes": 0,
            "depends_on": ["string"],
            "dependency_reasons": {},
            "routing_group": "string",
            "write_set": {"paths": ["string"], "complete": True},
            "narrow_tests": {"selectors": ["string"], "max_seconds": 0, "max_runs": 0},
            "checkpoint": {"required": True, "max_interval_seconds": 0, "records": ["string"]},
        }
    ],
    "validation_jobs": [],
    "critique_resolution_coverage": [],
    "sense_checks": ["string"],
    "watch_items": ["string"],
    "meta_commentary": "string",
    "user_actions": [{"id": "string", "description": "string", "phase": "before_execute", "requires_human_only_reason": "string"}],
}

REAL_PAYLOAD = {
    "task_contract_version": 2,
    "tasks": [
        {
            "id": "T1",
            "objective": "Implement the media reference resolver",
            "description": "Add resolve() to the media reference repository and wire it into the CLI.",
            "status": "pending",
            "kind": "code",
            "complexity": 3,
            "complexity_justification": "Localized change in one repository module; moderate blast radius.",
            "estimated_minutes": 8,
            "depends_on": [],
            "dependency_reasons": {},
            "routing_group": "",
            "write_set": {"paths": ["astrid/core/media_references.py"], "complete": True},
            "narrow_tests": {"selectors": ["tests/v10/test_reference_media.py::test_resolve"], "max_seconds": 120, "max_runs": 2},
            "checkpoint": {"required": False, "max_interval_seconds": 300, "records": []},
            "executor_notes": "",
            "reviewer_verdict": "",
        }
    ],
    "validation_jobs": [],
    "critique_resolution_coverage": [],
    "sense_checks": [{"id": "SC1", "task_id": "T1", "question": "Does resolve() handle missing references?", "verdict": ""}],
    "watch_items": ["reference repository contract stability"],
    "meta_commentary": "Keep the CLI surface unchanged.",
    "user_actions": [],
}


class FakeAgent:
    """Minimal stand-in for the hermes AIAgent run_conversation surface."""

    def __init__(self, responses: list[dict]) -> None:
        self._responses = list(responses)
        self.calls: list[tuple[str, object]] = []
        self.model = "accounts/fireworks/models/glm-5p2"

    def run_conversation(self, *, user_message: str, conversation_history: object, **kwargs) -> dict:
        self.calls.append((user_message, conversation_history))
        if not self._responses:
            return {"final_response": "", "messages": []}
        return self._responses.pop(0)


def _result(final_response: str) -> dict:
    return {
        "final_response": final_response,
        "messages": [{"role": "assistant", "content": "I investigated the plan."}],
    }


def test_finalize_placeholder_detector() -> None:
    assert _is_finalize_placeholder_payload(PLACEHOLDER_PAYLOAD) is True
    assert _is_finalize_placeholder_payload(REAL_PAYLOAD) is False
    # Empty task list = unfilled template (finalize always emits tasks).
    assert _is_finalize_placeholder_payload({"task_contract_version": 0, "tasks": []}) is True
    # A real graph is never flagged, even with task_contract_version 0 (that
    # goes through the feasibility repair lane, which has its own feedback).
    assert _is_finalize_placeholder_payload(dict(REAL_PAYLOAD, task_contract_version=0)) is False
    assert _is_finalize_placeholder_payload(None) is False
    assert _is_finalize_placeholder_payload("nope") is False


def test_placeholder_echo_is_discarded_and_summary_prompt_recovers(tmp_path: Path) -> None:
    agent = FakeAgent(
        [
            {"final_response": json.dumps(REAL_PAYLOAD), "messages": []},  # summary re-fill
        ]
    )
    payload, raw = parse_agent_output(
        agent,
        _result(json.dumps(PLACEHOLDER_PAYLOAD)),
        output_path=tmp_path / "finalize_output.json",  # does not exist
        schema=FINALIZE_MODEL_OUTPUT_SCHEMA,
        step="finalize",
        project_dir=tmp_path,
        plan_dir=tmp_path,
    )
    # The placeholder was discarded; the repair re-fill was accepted.
    assert payload == REAL_PAYLOAD
    assert agent.calls, "summary prompt must have been invoked to recover a real fill"


def test_real_finalize_graph_passes_through_untouched(tmp_path: Path) -> None:
    agent = FakeAgent([])
    payload, raw = parse_agent_output(
        agent,
        _result(json.dumps(REAL_PAYLOAD)),
        output_path=tmp_path / "finalize_output.json",
        schema=FINALIZE_MODEL_OUTPUT_SCHEMA,
        step="finalize",
        project_dir=tmp_path,
        plan_dir=tmp_path,
    )
    assert payload == REAL_PAYLOAD
    assert agent.calls == [], "real graphs must not trigger repair calls"


def test_placeholder_without_repair_fails_cleanly(tmp_path: Path) -> None:
    agent = FakeAgent(
        [
            # Summary prompt re-fill STILL echoes the template.
            {"final_response": json.dumps(PLACEHOLDER_PAYLOAD), "messages": []},
        ]
    )
    with pytest.raises(CliError) as excinfo:
        parse_agent_output(
            agent,
            _result(json.dumps(PLACEHOLDER_PAYLOAD)),
            output_path=tmp_path / "finalize_output.json",
            schema=FINALIZE_MODEL_OUTPUT_SCHEMA,
            step="finalize",
            project_dir=tmp_path,
            plan_dir=tmp_path,
        )
    assert excinfo.value.code == "worker_parse_error"
    # The placeholder payload must never be accepted as the worker payload.
    assert "could not extract JSON" in str(excinfo.value.message)
