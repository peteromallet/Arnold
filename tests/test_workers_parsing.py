"""Direct parsing and payload validation tests for megaplan.workers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from arnold.pipeline import StepInvocation
from arnold.pipelines.megaplan.model_seam import (
    ModelStructuralAuditError,
    _RecoveredPayload,
    _recovery_critique_completeness_score,
    capture_step_output,
)
from arnold.pipelines.megaplan.types import CliError
from arnold.pipelines.megaplan.workers import (
    CommandResult,
    _extract_claude_usage,
    extract_session_id,
    parse_claude_envelope,
    parse_json_file,
    run_codex_step,
)
from arnold.pipelines.megaplan.workers._impl import CommandResult, run_codex_step


def _deleted_validate_payload(step: str, payload: dict[str, object]) -> None:
    """Compatibility shim for legacy retirement tests.

    The production helper is deleted; these tests keep proving old direct
    validation paths cannot authorize payloads for migrated steps.
    """
    raise CliError(
        "parse_error",
        f"Legacy validate_payload() is retired for {step}; use schema-backed capture/audit instead.",
    )


def test_validate_payload_is_not_importable_from_impl() -> None:
    with pytest.raises(ImportError):
        exec("from arnold.pipelines.megaplan.workers._impl import validate_payload", {})


def _capture_recovered_output(
    step: str,
    *,
    plan_dir: Path,
    output_path: Path,
    raw: str,
    prefer_output_file: bool = True,
) -> object:
    invocation = StepInvocation(
        kind="model",
        metadata={
            "validation_step": step,
            "capture_recovery": {
                "step": step,
                "plan_dir": str(plan_dir),
                "output_path": str(output_path),
                "prefer_output_file": prefer_output_file,
            },
        },
    )
    return capture_step_output(invocation, raw)


def _recover_payload(
    step: str,
    *,
    plan_dir: Path,
    output_path: Path,
    raw: str,
    prefer_output_file: bool = True,
) -> dict[str, object]:
    outcome = _capture_recovered_output(
        step,
        plan_dir=plan_dir,
        output_path=output_path,
        raw=raw,
        prefer_output_file=prefer_output_file,
    )
    return outcome.legacy_payload


def test_parse_claude_envelope_prefers_structured_output() -> None:
    raw = json.dumps({"structured_output": {"plan": "x"}, "total_cost_usd": 0.01})
    envelope, payload = parse_claude_envelope(raw)
    assert envelope["total_cost_usd"] == 0.01
    assert payload == {"plan": "x"}

def test_extract_claude_usage_sums_input_and_cache_tokens() -> None:
    envelope = {
        "usage": {
            "input_tokens": 100,
            "cache_read_input_tokens": 400,
            "cache_creation_input_tokens": 50,
            "output_tokens": 200,
        }
    }
    prompt, completion = _extract_claude_usage(envelope)
    assert prompt == 550
    assert completion == 200

def test_extract_claude_usage_handles_missing_or_invalid() -> None:
    # No envelope.
    assert _extract_claude_usage(None) == (0, 0)
    # No usage key.
    assert _extract_claude_usage({}) == (0, 0)
    # usage is not a dict.
    assert _extract_claude_usage({"usage": "bogus"}) == (0, 0)
    # Partial / non-numeric fields default to 0.
    envelope = {"usage": {"input_tokens": "55", "output_tokens": None}}
    assert _extract_claude_usage(envelope) == (55, 0)

def test_parse_claude_envelope_rejects_invalid_json() -> None:
    with pytest.raises(CliError, match="valid JSON"):
        parse_claude_envelope("not json")

def test_parse_claude_envelope_classifies_not_logged_in_as_auth_error() -> None:
    raw = json.dumps({"is_error": True, "result": "Not logged in · Please run /login"})
    with pytest.raises(CliError) as exc_info:
        parse_claude_envelope(raw)
    assert exc_info.value.code == "auth_error"
    assert "not logged in" in exc_info.value.message.lower()

@pytest.mark.parametrize(
    ("step", "payload"),
    [
        (
            "execute",
            {
                "output": "done",
                "files_changed": [],
                "commands_run": [],
                "deviations": [],
                "task_updates": [
                    {
                        "task_id": "T1",
                        "status": "done",
                        "executor_notes": "Implemented.",
                        "files_changed": ["megaplan/workers.py"],
                        "commands_run": ["pytest tests/test_workers.py"],
                    }
                ],
                "sense_check_acknowledgments": [
                    {"sense_check_id": "SC1", "executor_note": "Confirmed."}
                ],
            },
        ),
    ],
)
def test_validate_payload_retired_for_execute(step: str, payload: dict[str, object]) -> None:
    with pytest.raises(CliError, match="retired for execute"):
        _deleted_validate_payload(step, payload)

@pytest.mark.parametrize("step,payload", [
    (
        "finalize",
        {
            "tasks": [],
            "watch_items": [],
            "sense_checks": [],
            "user_actions": [],
            "meta_commentary": "ok",
            "validation": {
                "plan_steps_covered": [],
                "orphan_tasks": [],
                "coverage_complete": True,
            },
        },
    ),
    (
        "critique",
        {
            "checks": [],
            "flags": [],
            "verified_flag_ids": [],
            "disputed_flag_ids": [],
        },
    ),
    (
        "review",
        {
            "review_verdict": "approved",
            "criteria": [],
            "issues": [],
            "rework_items": [],
            "summary": "ok",
            "task_verdicts": [],
            "sense_check_verdicts": [],
        },
    ),
    (
        "gate",
        {
            "recommendation": "PROCEED",
            "rationale": "x",
            "signals_assessment": "ok",
            "warnings": [],
            "settled_decisions": [],
            "flag_resolutions": [],
            "accepted_tradeoffs": [],
        },
    ),
    ("plan", {"plan": "x", "questions": [], "success_criteria": [{"criterion": "test", "priority": "must"}], "assumptions": []}),
    (
        "prep",
        {
            "skip": False,
            "task_summary": "Prepare context before planning.",
            "key_evidence": [],
            "relevant_code": [],
            "test_expectations": [],
            "constraints": [],
            "suggested_approach": "Use the brief as primary context.",
        },
    ),
    ("prep-triage", {"triage_framing": "Research needed.", "areas": []}),
    ("prep-research", {"findings": []}),
    ("prep-distill", {"skip": False, "task_summary": "Distilled findings.", "key_evidence": [], "relevant_code": [], "test_expectations": [], "constraints": [], "suggested_approach": "Use the brief."}),
    (
        "critique_evaluator",
        {
            "selections": [],
            "skipped": [],
            "evaluator_model": "mock-model",
        },
    ),
    (
        "feedback",
        {
            "overall": {"rating": 8, "comment": "Good work."},
            "stages": {},
        },
    ),
    ("loop_plan", {"spec_updates": {}, "next_action": "continue", "reasoning": "ok"}),
    ("loop_execute", {"diagnosis": "x", "fix_description": "y", "files_to_change": [], "confidence": "low", "outcome": "continue", "should_pause": False}),
    (
        "tiebreaker_researcher",
        {
            "question": "Which option?",
            "evidence": [],
            "options": [],
            "preliminary_pick": {
                "option_name": "A",
                "rationale": "ok",
                "what_im_least_sure_about": "tradeoffs",
            },
        },
    ),
    (
        "tiebreaker_challenger",
        {
            "measurements_vs_assumptions": "ok",
            "missing_options": [],
            "hard_cases": [],
            "reframings": [],
            "aging_analysis": "ok",
            "counter_recommendation": {
                "option_name": "A",
                "rationale": "ok",
                "agrees_with_researcher": True,
            },
        },
    ),
])
def test_validate_payload_rejects_migrated_native_steps(
    step: str,
    payload: dict[str, object],
) -> None:
    with pytest.raises(CliError, match=rf"retired for {step}"):
        _deleted_validate_payload(
            step,
            payload,
        )

def test_validate_payload_execute_batch_shape_is_retired() -> None:
    with pytest.raises(CliError, match="retired for execute"):
        _deleted_validate_payload(
            "execute",
            {
                "task_updates": [
                    {
                        "task_id": "T8",
                        "status": "done",
                        "executor_notes": "Implemented batch task.",
                        "files_changed": ["reigh-worker/tests/test_preview_harness.py"],
                        "commands_run": ["pytest tests/test_preview_harness.py -v"],
                    }
                ],
                "sense_check_acknowledgments": [
                    {
                        "sense_check_id": "SC8",
                        "executor_note": "Confirmed batch verification.",
                    }
                ],
            },
        )

def test_extract_session_id_supports_jsonl() -> None:
    raw = '{"type":"thread.started","thread_id":"abc-123"}\n'
    assert extract_session_id(raw) == "abc-123"

def test_parse_json_file_reads_object(tmp_path: Path) -> None:
    path = tmp_path / "out.json"
    path.write_text(json.dumps({"ok": True}), encoding="utf-8")
    assert parse_json_file(path) == {"ok": True}

def test_recover_codex_payload_handles_stderr_bleed_in_output_file(tmp_path: Path) -> None:
    """Codex sometimes appends stderr/log noise to the -o output file after the JSON.

    parse_json_file() uses strict json.loads() and rejects trailing junk. The recovery
    path must also feed the file contents through _extract_json_candidates_from_raw
    so the leading valid JSON object can still be salvaged.
    """
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    output_path = plan_dir / "critique_output.json"
    valid_payload = {
        "checks": [
            {
                "id": "check-1",
                "question": "Is the plan grounded in the repository?",
                "findings": [
                    {"detail": "Plan references the actual files.", "flagged": False}
                ],
            }
        ],
        "flags": [],
        "verified_flag_ids": [],
        "disputed_flag_ids": [],
    }
    polluted = (
        json.dumps(valid_payload)
        + "\n2026-04-27T00:16:08.726626Z ERROR codex_core::session: "
        + "failed to record rollout items: thread x not found\n"
        + "tokens used\n674,216\n"
    )
    output_path.write_text(polluted, encoding="utf-8")

    recovered = _recover_payload(
        "critique",
        plan_dir=plan_dir,
        output_path=output_path,
        raw="",
    )
    assert recovered == valid_payload

def test_recover_codex_payload_prefers_more_complete_valid_critique_over_output_file_order(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    output_path = plan_dir / "critique_output.json"
    file_payload = {
        "checks": [],
        "flags": [
            {
                "id": "FLAG-001",
                "concern": "The plan should revise the RunPod disk defaults.",
                "evidence": "runpod-lifecycle config still contains stale defaults.",
                "severity": "medium",
                "category": "correctness",
            }
        ],
        "verified_flag_ids": [],
        "disputed_flag_ids": [],
    }
    raw_payload = {
        "checks": [
            {
                "id": "disk-defaults",
                "question": "Are disk defaults aligned?",
                "findings": [
                    {
                        "detail": "Intermediate transcript JSON should not outrank the output file.",
                        "flagged": True,
                    }
                ],
            }
        ],
        "flags": [],
        "verified_flag_ids": [],
        "disputed_flag_ids": [],
    }
    output_path.write_text(json.dumps(file_payload), encoding="utf-8")

    recovered = _recover_payload(
        "critique",
        plan_dir=plan_dir,
        output_path=output_path,
        raw=f"thinking...\n{json.dumps(raw_payload)}\n",
    )

    assert recovered == raw_payload

def test_recover_codex_payload_prefers_completed_critique_template_over_schema_summary(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    output_path = tmp_path / "codex-o.json"
    summary_payload = {
        "checks": [
            {
                "id": "issue_hints",
                "question": "Did the plan address the brief?",
                "findings": [
                    {
                        "detail": "Wrote the critique output file with the detailed findings.",
                        "flagged": False,
                    }
                ],
            }
        ],
        "flags": [],
        "verified_flag_ids": [],
        "disputed_flag_ids": [],
    }
    completed_payload = {
        "checks": [
            {
                "id": "issue_hints",
                "question": "Did the plan address the brief?",
                "findings": [
                    {
                        "detail": "Found one concrete issue in the issue-hints lens.",
                        "flagged": True,
                    }
                ],
            },
            {
                "id": "correctness",
                "question": "Is the plan technically correct?",
                "findings": [
                    {
                        "detail": "Found one concrete issue in the correctness lens.",
                        "flagged": True,
                    }
                ],
            },
            {
                "id": "scope",
                "question": "Is the plan scoped correctly?",
                "findings": [
                    {
                        "detail": "Found one concrete issue in the scope lens.",
                        "flagged": True,
                    }
                ],
            },
        ],
        "flags": [
            {
                "id": "FLAG-001",
                "concern": "Detailed critique should win over a schema-summary payload.",
                "evidence": "The side-effect template contains more completed checks.",
                "category": "correctness",
                "severity_hint": "likely-significant",
            }
        ],
        "verified_flag_ids": [],
        "disputed_flag_ids": [],
    }
    output_path.write_text(json.dumps(summary_payload), encoding="utf-8")
    (plan_dir / "critique_output.json").write_text(json.dumps(completed_payload), encoding="utf-8")

    recovered = _recover_payload(
        "critique",
        plan_dir=plan_dir,
        output_path=output_path,
        raw="",
    )

    assert recovered == completed_payload

def test_recover_codex_payload_reports_template_provenance_without_legacy_authority(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    output_path = tmp_path / "codex-o.json"
    output_path.write_text(
        json.dumps({"checks": 1, "flags": [], "verified_flag_ids": [], "disputed_flag_ids": []}),
        encoding="utf-8",
    )
    template_payload = {
        "checks": [
            {
                "id": "complete",
                "question": "Did template recovery work?",
                "findings": [{"detail": "Template should be selected.", "flagged": False}],
            }
        ],
        "flags": [],
        "verified_flag_ids": [],
        "disputed_flag_ids": [],
    }
    raw_payload = {
        "checks": [],
        "flags": [],
        "verified_flag_ids": [],
        "disputed_flag_ids": [],
    }
    (plan_dir / "critique_output.json").write_text(json.dumps(template_payload), encoding="utf-8")

    outcome = _capture_recovered_output(
        "critique",
        plan_dir=plan_dir,
        output_path=output_path,
        raw=json.dumps(raw_payload),
    )

    assert outcome.legacy_payload == template_payload
    assert outcome.contract_result.provenance.sources == (
        "model_step_output",
        "codex_recovery:template_file",
    )

def test_recover_codex_payload_falls_back_from_file_to_template_to_raw_order(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    output_path = tmp_path / "codex-o.json"
    output_path.write_text(json.dumps({"task_updates": "wrong-type"}), encoding="utf-8")
    (plan_dir / "execute_output.json").write_text(
        json.dumps(
            {
                "task_updates": [{"task_id": "T7", "status": "done"}],
                "sense_check_acknowledgments": [{"sense_check_id": "SC7", "executor_note": "ok"}],
            }
        ),
        encoding="utf-8",
    )
    raw_payload = {
        "task_updates": [{"task_id": "T8", "status": "done"}],
        "sense_check_acknowledgments": [{"sense_check_id": "SC8", "executor_note": "ok"}],
    }

    outcome = _capture_recovered_output(
        "execute",
        plan_dir=plan_dir,
        output_path=output_path,
        raw=json.dumps(raw_payload),
    )

    assert outcome.contract_result.provenance.sources == (
        "model_step_output",
        "codex_recovery:template_file",
    )
    assert outcome.legacy_payload["task_updates"][0]["task_id"] == "T7"
    assert outcome.legacy_payload["task_updates"][0]["status"] == "done"

def test_recover_codex_payload_keeps_meaningful_critique_when_template_is_empty(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    output_path = tmp_path / "codex-o.json"
    meaningful_payload = {
        "checks": [
            {
                "id": "issue_hints",
                "question": "Did the plan address the brief?",
                "findings": [
                    {
                        "detail": "The output file contains the only meaningful critique finding.",
                        "flagged": True,
                    }
                ],
            }
        ],
        "flags": [],
        "verified_flag_ids": [],
        "disputed_flag_ids": [],
    }
    empty_template = {
        "checks": [
            {
                "id": "issue_hints",
                "question": "Did the plan address the brief?",
                "findings": [],
            }
        ],
        "flags": [],
        "verified_flag_ids": [],
        "disputed_flag_ids": [],
    }
    output_path.write_text(json.dumps(meaningful_payload), encoding="utf-8")
    (plan_dir / "critique_output.json").write_text(json.dumps(empty_template), encoding="utf-8")

    recovered = _recover_payload(
        "critique",
        plan_dir=plan_dir,
        output_path=output_path,
        raw="",
    )

    assert recovered == meaningful_payload

def test_recover_codex_payload_critique_scoring_handles_scalar_checks(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    output_path = tmp_path / "codex-o.json"
    malformed_payload = {
        "checks": 1,
        "flags": [],
        "verified_flag_ids": [],
        "disputed_flag_ids": [],
    }
    complete_payload = {
        "checks": [
            {
                "id": "issue_hints",
                "question": "Did the plan address the brief?",
                "findings": [
                    {
                        "detail": "A scalar checks candidate must not crash recovery.",
                        "flagged": False,
                    }
                ],
            }
        ],
        "flags": [],
        "verified_flag_ids": [],
        "disputed_flag_ids": [],
    }
    output_path.write_text(json.dumps(malformed_payload), encoding="utf-8")
    (plan_dir / "critique_output.json").write_text(json.dumps(complete_payload), encoding="utf-8")

    recovered = _recover_payload(
        "critique",
        plan_dir=plan_dir,
        output_path=output_path,
        raw="",
    )

    assert recovered == complete_payload

def test_recover_codex_payload_accepts_schema_valid_execute_batch_payload(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    output_path = plan_dir / "execute_output.json"
    output_path.write_text(
        json.dumps(
            {
                "task_updates": [
                    {
                        "task_id": "T3",
                        "status": "done",
                        "executor_notes": "Generated the template index.",
                        "files_changed": ["vibecomfy/template_index.json"],
                        "commands_run": ["python -m json.tool template_index.json"],
                    }
                ],
                "sense_check_acknowledgments": [
                    {
                        "sense_check_id": "SC3",
                        "executor_note": "Template index count is 51.",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    recovered = _recover_payload(
        "execute",
        plan_dir=plan_dir,
        output_path=output_path,
        raw="",
    )

    assert recovered is not None
    assert recovered["task_updates"][0]["task_id"] == "T3"
    assert recovered["task_updates"][0]["status"] == "done"
    assert recovered["sense_check_acknowledgments"][0]["sense_check_id"] == "SC3"

def test_recover_codex_payload_accepts_execute_batch_aliases_after_schema_migration(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    output_path = plan_dir / "execute_output.json"
    output_path.write_text(
        json.dumps(
            {
                "task_updates": [{"id": "T3", "status": "completed"}],
                "sense_check_acknowledgments": [{"id": "SC3", "executor_note": "ok"}],
            }
        ),
        encoding="utf-8",
    )

    recovered = _recover_payload(
        "execute",
        plan_dir=plan_dir,
        output_path=output_path,
        raw="",
    )

    assert recovered is not None
    assert recovered["task_updates"][0]["id"] == "T3"
    assert recovered["task_updates"][0]["status"] == "completed"
    assert recovered["sense_check_acknowledgments"][0]["id"] == "SC3"

def test_recover_codex_payload_accepts_review_without_checks_and_trailing_telemetry(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    output_path = plan_dir / "review_output.json"
    valid_payload = {
        "review_verdict": "approved",
        "criteria": [
            {
                "name": "Regression coverage exists",
                "priority": "must",
                "pass": "pass",
                "evidence": "Focused worker tests cover review JSON recovery.",
            }
        ],
        "issues": [],
        "rework_items": [],
        "summary": "Approved. All must criteria pass.",
        "task_verdicts": [
            {
                "task_id": "T1",
                "reviewer_verdict": "Pass. The implementation matches the task.",
                "evidence_files": ["megaplan/workers.py"],
            }
        ],
        "sense_check_verdicts": [
            {"sense_check_id": "SC1", "verdict": "Confirmed. Review recovery accepts the newer shape."}
        ],
    }
    output_path.write_text(
        json.dumps(valid_payload)
        + "\n2026-05-03T12:00:00Z INFO codex telemetry: tokens used 1234\n",
        encoding="utf-8",
    )

    recovered = _recover_payload(
        "review",
        plan_dir=plan_dir,
        output_path=output_path,
        raw="",
    )

    assert recovered == {**valid_payload, "checks": []}

def test_recover_codex_payload_reports_missing_required_keys_for_json_object(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    output_path = plan_dir / "revise_output.json"
    # Optional array keys present so the payload \"looks like\" a revise, but the
    # required string `plan` key is missing — the defensive-defaults block
    # only fills array keys, so validation still surfaces the gap.
    output_path.write_text(
        json.dumps({"changes_summary": "y", "flags_addressed": [], "assumptions": [], "success_criteria": [], "questions": []}),
        encoding="utf-8",
    )

    with pytest.raises(ModelStructuralAuditError) as exc_info:
        _capture_recovered_output(
            "revise",
            plan_dir=plan_dir,
            output_path=output_path,
            raw="",
        )

    assert "Recovered JSON object for revise failed validation" in str(exc_info.value)
    assert "not valid JSON" not in str(exc_info.value)


def test_recover_codex_payload_rejects_gate_payload_missing_required_arrays(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    output_path = plan_dir / "gate_output.json"
    output_path.write_text(
        json.dumps(
            {
                "recommendation": "PROCEED",
                "rationale": "Proceed.",
                "signals_assessment": "Looks good.",
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ModelStructuralAuditError) as exc_info:
        _capture_recovered_output(
            "gate",
            plan_dir=plan_dir,
            output_path=output_path,
            raw="",
        )

    assert "Recovered JSON object for gate failed validation" in str(exc_info.value)
    assert "/warnings" in str(exc_info.value)


def test_recover_codex_payload_rejects_gate_payload_with_wrong_array_types(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    output_path = plan_dir / "gate_output.json"
    output_path.write_text(
        json.dumps(
            {
                "recommendation": "PROCEED",
                "rationale": "Proceed.",
                "signals_assessment": "Looks good.",
                "warnings": "not-a-list",
                "settled_decisions": [],
                "flag_resolutions": {},
                "accepted_tradeoffs": [],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ModelStructuralAuditError) as exc_info:
        _capture_recovered_output(
            "gate",
            plan_dir=plan_dir,
            output_path=output_path,
            raw="",
        )

    assert "Recovered JSON object for gate failed validation" in str(exc_info.value)
    assert "/warnings" in str(exc_info.value) or "/flag_resolutions" in str(exc_info.value)

def test_validate_payload_critique_requires_flags() -> None:
    with pytest.raises(CliError, match=r"retired for critique"):
        _deleted_validate_payload("critique", {"verified_flag_ids": [], "disputed_flag_ids": []})

def test_validate_payload_execute_is_retired() -> None:
    with pytest.raises(CliError, match="retired for execute"):
        _deleted_validate_payload(
            "execute",
            {"files_changed": [], "commands_run": [], "deviations": [], "sense_check_acknowledgments": []},
        )

def test_validate_payload_review_requires_criteria() -> None:
    with pytest.raises(CliError, match=r"retired for review"):
        _deleted_validate_payload(
            "review",
            {
                "review_verdict": "approved",
                "checks": [],
                "pre_check_flags": [],
                "verified_flag_ids": [],
                "disputed_flag_ids": [],
                "issues": [],
                "rework_items": [],
                "summary": "ok",
                "task_verdicts": [],
                "sense_check_verdicts": [],
            },
        )


def _valid_revise_payload() -> dict[str, object]:
    return {
        "plan": "Use regex clarify\\\\s*\\\\( safely.",
        "changes_summary": "Escaped regex backslashes.",
        "flags_addressed": [],
        "assumptions": [],
        "success_criteria": [],
        "questions": [],
    }


def test_codex_parse_failure_invokes_one_repair_retry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests._workers_helpers import _mock_state

    plan_dir, state = _mock_state(tmp_path)
    output_path = plan_dir / "revise_output.json"
    invalid_raw = (
        '{"plan":"Use regex clarify\\s*\\(","changes_summary":"x",'
        '"flags_addressed":[],"assumptions":[],"success_criteria":[],"questions":[]}'
    )
    valid_payload = _valid_revise_payload()
    prompts: list[str] = []

    def fake_run_command(command, *, cwd, stdin_text, **_kwargs):
        prompts.append(stdin_text)
        target = Path(command[command.index("-o") + 1])
        target.write_text(
            invalid_raw if len(prompts) == 1 else json.dumps(valid_payload),
            encoding="utf-8",
        )
        return CommandResult(
            command=list(command),
            cwd=Path(cwd),
            returncode=0,
            stdout="",
            stderr="",
            duration_ms=1,
        )

    monkeypatch.setattr("arnold.pipelines.megaplan.workers._impl.run_command", fake_run_command)

    result = run_codex_step(
        "revise",
        state,
        plan_dir,
        root=Path(__file__).resolve().parents[1],
        persistent=False,
        fresh=True,
        model="gpt-5.5",
        output_path=output_path,
    )

    assert result.payload == valid_payload
    assert len(prompts) == 2
    assert "error at line 1 col" in prompts[1]
    assert "Escape every backslash as `\\\\`" in prompts[1]
    assert "clarify\\\\s*\\\\(" in prompts[1]


# ---------------------------------------------------------------------------
# T1 characterization: inventory of native-only recovery and validation paths
# in the worker parsing layer.
#
# After the all-NATIVE guard passes, recovery paths no longer branch through
# _normalize_worker_payload; all capture recovery is schema-audited.
# ---------------------------------------------------------------------------

_MIGRATED_SITES: tuple[str, ...] = ("finalize", "critique", "review", "gate", "execute")


def test_normalize_worker_payload_is_deleted() -> None:
    import arnold.pipelines.megaplan.workers._impl as workers_impl

    assert not hasattr(workers_impl, "_normalize_worker_payload")


def test_validate_payload_no_longer_authorizes_migrated_sites() -> None:
    """validate_payload is retired for migrated non-execute steps.

    Execute keeps its batch-relaxed legacy semantics here, but finalize,
    critique, review, and gate must now flow through schema-backed capture.
    """
    from arnold.pipelines.megaplan.types import CliError

    for step, payload in (
        ("finalize", {"meta_commentary": "x"}),
        ("critique", {"verified_flag_ids": [], "disputed_flag_ids": []}),
        ("review", {"criteria": [], "issues": [], "rework_items": [], "summary": "ok", "task_verdicts": [], "sense_check_verdicts": []}),
        ("gate", {"rationale": "ok", "signals_assessment": "ok"}),
    ):
        with pytest.raises(CliError, match=rf"retired for {step}"):
            _deleted_validate_payload(step, payload)


def test_validate_payload_retirement_precedes_missing_required_key_checks() -> None:
    """Migrated steps fail because the legacy validator is retired, not because
    it is still acting as a partial schema authority."""
    from arnold.pipelines.megaplan.types import CliError

    with pytest.raises(CliError, match=r"retired for finalize"):
        _deleted_validate_payload("finalize", {"meta_commentary": "x"})
    with pytest.raises(CliError, match=r"retired for critique"):
        _deleted_validate_payload("critique", {"verified_flag_ids": [], "disputed_flag_ids": []})
    with pytest.raises(CliError, match=r"retired for review"):
        _deleted_validate_payload("review", {"criteria": [], "issues": [], "rework_items": [],
                                    "summary": "ok", "task_verdicts": [], "sense_check_verdicts": []})
    with pytest.raises(CliError, match=r"retired for gate"):
        _deleted_validate_payload("gate", {"rationale": "ok", "signals_assessment": "ok"})


def test_workers_impl_has_no_normalize_worker_payload_definition() -> None:
    import ast
    from pathlib import Path

    worker_path = (
        Path(__file__).resolve().parents[1]
        / "arnold/pipelines/megaplan/workers/_impl.py"
    )
    source = worker_path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    normalize_defs = [
        node.name
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_normalize_worker_payload"
    ]
    assert normalize_defs == []


def test_megaplan_production_code_has_no_normalize_worker_payload_imports_or_calls() -> None:
    import ast

    package_root = Path(__file__).resolve().parents[1] / "arnold/pipelines/megaplan"
    violations: list[str] = []

    for path in sorted(package_root.rglob("*.py")):
        if "agent" in path.parts:
            continue
        if path.name == "__init__.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name == "_normalize_worker_payload":
                        violations.append(f"{path}:from-import")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.endswith("._normalize_worker_payload"):
                        violations.append(f"{path}:import")
            elif isinstance(node, ast.Name) and node.id == "_normalize_worker_payload":
                violations.append(f"{path}:name")
            elif isinstance(node, ast.Attribute) and node.attr == "_normalize_worker_payload":
                violations.append(f"{path}:attribute")

    assert violations == []


def test_worker_recovery_helpers_are_deleted_after_model_seam_takeover() -> None:
    import arnold.pipelines.megaplan.workers._impl as workers_impl

    assert not hasattr(workers_impl, "_recover_codex_payload")
    assert not hasattr(workers_impl, "_recover_codex_payload_with_provenance")
    assert callable(capture_step_output)


def test_codex_repair_retry_is_bounded_to_one_attempt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests._workers_helpers import _mock_state

    plan_dir, state = _mock_state(tmp_path)
    output_path = plan_dir / "revise_output.json"
    invalid_raw = (
        '{"plan":"Use regex clarify\\s*\\(","changes_summary":"x",'
        '"flags_addressed":[],"assumptions":[],"success_criteria":[],"questions":[]}'
    )
    prompts: list[str] = []

    def fake_run_command(command, *, cwd, stdin_text, **_kwargs):
        prompts.append(stdin_text)
        target = Path(command[command.index("-o") + 1])
        target.write_text(invalid_raw, encoding="utf-8")
        return CommandResult(
            command=list(command),
            cwd=Path(cwd),
            returncode=0,
            stdout="",
            stderr="",
            duration_ms=1,
        )

    monkeypatch.setattr("arnold.pipelines.megaplan.workers._impl.run_command", fake_run_command)

    with pytest.raises(CliError) as exc_info:
        run_codex_step(
            "revise",
            state,
            plan_dir,
            root=Path(__file__).resolve().parents[1],
            persistent=False,
            fresh=True,
            model="gpt-5.5",
            output_path=output_path,
        )

    assert len(prompts) == 2
    assert exc_info.value.code == "parse_error"
    assert exc_info.value.extra["model_output_parse_error"] is True


# ── _recovery_critique_completeness_score unit tests ──────────────────────────

def test_recovery_critique_completeness_score_ranks_by_completed_checks_and_findings() -> None:
    sparse = _RecoveredPayload(
        payload={
            "checks": [
                {"id": "a", "question": "?", "findings": [{"detail": "d", "flagged": True}]},
            ],
            "flags": [],
            "verified_flag_ids": [],
            "disputed_flag_ids": [],
        },
        provenance="raw_output",
    )
    dense = _RecoveredPayload(
        payload={
            "checks": [
                {"id": "a", "question": "?", "findings": [{"detail": "d1", "flagged": True}]},
                {"id": "b", "question": "?", "findings": [{"detail": "d2", "flagged": True}]},
            ],
            "flags": [],
            "verified_flag_ids": [],
            "disputed_flag_ids": [],
        },
        provenance="output_file",
    )

    assert _recovery_critique_completeness_score(sparse) == (1, 1)
    assert _recovery_critique_completeness_score(dense) == (2, 2)
    # dense should rank higher
    assert _recovery_critique_completeness_score(dense) > _recovery_critique_completeness_score(sparse)


def test_recovery_critique_completeness_score_handles_non_list_checks() -> None:
    scalar_checks = _RecoveredPayload(
        payload={"checks": 1, "flags": [], "verified_flag_ids": [], "disputed_flag_ids": []},
        provenance="raw_output",
    )
    assert _recovery_critique_completeness_score(scalar_checks) == (0, 0)


def test_recovery_critique_completeness_score_handles_empty_findings() -> None:
    empty_findings = _RecoveredPayload(
        payload={
            "checks": [
                {"id": "a", "question": "?", "findings": []},
                {"id": "b", "question": "?", "findings": []},
            ],
            "flags": [],
            "verified_flag_ids": [],
            "disputed_flag_ids": [],
        },
        provenance="output_file",
    )
    assert _recovery_critique_completeness_score(empty_findings) == (0, 0)


def test_recovery_critique_completeness_score_breaks_ties_with_total_findings() -> None:
    many_findings = _RecoveredPayload(
        payload={
            "checks": [
                {
                    "id": "a",
                    "question": "?",
                    "findings": [
                        {"detail": "d1", "flagged": True},
                        {"detail": "d2", "flagged": True},
                        {"detail": "d3", "flagged": True},
                    ],
                },
            ],
            "flags": [],
            "verified_flag_ids": [],
            "disputed_flag_ids": [],
        },
        provenance="raw_output",
    )
    few_findings = _RecoveredPayload(
        payload={
            "checks": [
                {"id": "a", "question": "?", "findings": [{"detail": "d1", "flagged": True}]},
            ],
            "flags": [],
            "verified_flag_ids": [],
            "disputed_flag_ids": [],
        },
        provenance="output_file",
    )

    assert _recovery_critique_completeness_score(many_findings) == (1, 3)
    assert _recovery_critique_completeness_score(few_findings) == (1, 1)
    assert _recovery_critique_completeness_score(many_findings) > _recovery_critique_completeness_score(few_findings)


# ── critique recovery: schema-valid ranking (migrated path) ──────────

def test_recover_codex_payload_critique_ranks_only_schema_valid_candidates(tmp_path: Path) -> None:
    """Schema-invalid critique candidates are excluded before completeness ranking."""
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    output_path = tmp_path / "codex-o.json"

    # schema-invalid: missing 'flags' key
    schema_invalid = {
        "checks": [
            {
                "id": "a",
                "question": "?",
                "findings": [
                    {"detail": "This has checks but is schema-invalid.", "flagged": True},
                    {"detail": "Another finding.", "flagged": False},
                ],
            },
        ],
        "verified_flag_ids": [],
        "disputed_flag_ids": [],
    }
    # schema-valid but less complete
    valid_sparse = {
        "checks": [
            {
                "id": "b",
                "question": "?",
                "findings": [{"detail": "Only one finding.", "flagged": True}],
            },
        ],
        "flags": [],
        "verified_flag_ids": [],
        "disputed_flag_ids": [],
    }
    # schema-valid and more complete
    valid_dense = {
        "checks": [
            {
                "id": "c",
                "question": "Q1",
                "findings": [
                    {"detail": "Finding 1.", "flagged": True},
                    {"detail": "Finding 2.", "flagged": True},
                ],
            },
            {
                "id": "d",
                "question": "Q2",
                "findings": [
                    {"detail": "Finding 3.", "flagged": True},
                ],
            },
        ],
        "flags": [],
        "verified_flag_ids": [],
        "disputed_flag_ids": [],
    }

    output_path.write_text(json.dumps(schema_invalid), encoding="utf-8")
    (plan_dir / "critique_output.json").write_text(json.dumps(valid_sparse), encoding="utf-8")

    outcome = _capture_recovered_output(
        "critique",
        plan_dir=plan_dir,
        output_path=output_path,
        raw=json.dumps(valid_dense),
    )

    # The schema-invalid output file and the sparse fallback should be skipped;
    # the dense raw-output should win because it's the most complete *valid* candidate.
    assert outcome.legacy_payload == valid_dense
    assert outcome.contract_result.provenance.sources == (
        "model_step_output",
        "codex_recovery:raw_output",
    )


def test_recover_codex_payload_critique_preserves_ordering_on_completeness_tie(
    tmp_path: Path,
) -> None:
    """When completeness scores tie, output-file beats fallback-file beats raw-transcript."""
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    output_path = tmp_path / "codex-o.json"

    output_payload = {
        "checks": [
            {
                "id": "a",
                "question": "Q",
                "findings": [{"detail": "from output file.", "flagged": True}],
            },
        ],
        "flags": [],
        "verified_flag_ids": [],
        "disputed_flag_ids": [],
    }
    fallback_payload = {
        "checks": [
            {
                "id": "a",
                "question": "Q",
                "findings": [{"detail": "from fallback file.", "flagged": True}],
            },
        ],
        "flags": [],
        "verified_flag_ids": [],
        "disputed_flag_ids": [],
    }
    raw_payload = {
        "checks": [
            {
                "id": "a",
                "question": "Q",
                "findings": [{"detail": "from raw transcript.", "flagged": True}],
            },
        ],
        "flags": [],
        "verified_flag_ids": [],
        "disputed_flag_ids": [],
    }

    output_path.write_text(json.dumps(output_payload), encoding="utf-8")
    (plan_dir / "critique_output.json").write_text(json.dumps(fallback_payload), encoding="utf-8")

    outcome = _capture_recovered_output(
        "critique",
        plan_dir=plan_dir,
        output_path=output_path,
        raw=json.dumps(raw_payload),
    )

    # All three have equal completeness: (1, 1). Output file should win.
    assert outcome.legacy_payload == output_payload
    assert outcome.contract_result.provenance.sources == (
        "model_step_output",
        "codex_recovery:output_file",
    )


def test_recover_codex_payload_critique_fallback_beats_raw_on_tie(tmp_path: Path) -> None:
    """When output file is invalid and fallback/raw tie on completeness, fallback wins."""
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    output_path = tmp_path / "codex-o.json"

    # Invalid output file
    output_path.write_text(json.dumps({"not": "a critique"}), encoding="utf-8")

    fallback_payload = {
        "checks": [
            {
                "id": "a",
                "question": "Q",
                "findings": [{"detail": "fallback wins tie.", "flagged": True}],
            },
        ],
        "flags": [],
        "verified_flag_ids": [],
        "disputed_flag_ids": [],
    }
    raw_payload = {
        "checks": [
            {
                "id": "a",
                "question": "Q",
                "findings": [{"detail": "raw loses tie.", "flagged": True}],
            },
        ],
        "flags": [],
        "verified_flag_ids": [],
        "disputed_flag_ids": [],
    }

    (plan_dir / "critique_output.json").write_text(json.dumps(fallback_payload), encoding="utf-8")

    outcome = _capture_recovered_output(
        "critique",
        plan_dir=plan_dir,
        output_path=output_path,
        raw=json.dumps(raw_payload),
    )

    assert outcome.legacy_payload == fallback_payload
    assert outcome.contract_result.provenance.sources == (
        "model_step_output",
        "codex_recovery:template_file",
    )


# ---------------------------------------------------------------------------
# T2/T24: Recovery ranking schema-audit guards.
# ---------------------------------------------------------------------------


def test_recovery_ranking_only_considers_schema_valid_candidates_for_migrated_steps() -> None:
    """Recovery ranking for migrated steps must filter through schema audit.

    The seam-owned recovery helper must route migrated
    steps through schema validation and exclude schema-invalid candidates
    before completeness ranking.  This test proves the function exists and
    can be called — actual ranking behavior is asserted by the schema-valid
    ranking tests above.
    """
    import ast
    from pathlib import Path

    seam_path = (
        Path(__file__).resolve().parents[1]
        / "arnold/pipelines/megaplan/model_seam.py"
    )
    source = seam_path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    migrated = {"finalize", "critique", "review", "gate", "execute"}

    # Find the seam-owned recovery helper.
    for node in tree.body:
        if (
            isinstance(node, ast.FunctionDef)
            and node.name == "_recover_payload_with_provenance"
        ):
            for subnode in ast.walk(node):
                if isinstance(subnode, ast.Call):
                    if (
                        isinstance(subnode.func, ast.Name)
                        and subnode.func.id == "validate_payload"
                    ):
                        if subnode.args and isinstance(subnode.args[0], ast.Constant):
                            step_name = subnode.args[0].value
                            assert step_name not in migrated, (
                                f"_recover_payload_with_provenance must not "
                                f"call _deleted_validate_payload('{step_name}', ...) — "
                                f"migrated steps use schema audit"
                            )
            break
    else:
        raise AssertionError("model_seam must define _recover_payload_with_provenance")


def test_recovery_critique_ranking_excludes_schema_invalid_candidates_for_migrated_step(
    tmp_path: Path,
) -> None:
    """Schema-invalid critique recovery candidates must be excluded before ranking.

    This tests that the recovery path for a migrated step (critique) does not
    return a schema-invalid payload, even when it has more "checks" than a
    valid one.  Schema validity is the first filter; completeness ranking
    only applies among valid candidates.
    """
    import json

    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    output_path = tmp_path / "codex-o.json"

    # Schema-invalid: has many checks but missing required 'flags' key
    schema_invalid_dense = {
        "checks": [
            {
                "id": "a", "question": "Q1?",
                "findings": [
                    {"detail": "Finding A1.", "flagged": True},
                    {"detail": "Finding A2.", "flagged": True},
                    {"detail": "Finding A3.", "flagged": True},
                ],
            },
            {
                "id": "b", "question": "Q2?",
                "findings": [
                    {"detail": "Finding B1.", "flagged": True},
                    {"detail": "Finding B2.", "flagged": True},
                ],
            },
            {
                "id": "c", "question": "Q3?",
                "findings": [
                    {"detail": "Finding C1.", "flagged": True},
                ],
            },
        ],
        "verified_flag_ids": [],
        "disputed_flag_ids": [],
        # NOTE: missing 'flags' key — schema-invalid for critique
    }

    # Schema-valid but sparse: fewer checks but has all required keys
    schema_valid_sparse = {
        "checks": [
            {
                "id": "a", "question": "Q1?",
                "findings": [{"detail": "Only finding.", "flagged": True}],
            },
        ],
        "flags": [],
        "verified_flag_ids": [],
        "disputed_flag_ids": [],
    }

    output_path.write_text(json.dumps(schema_invalid_dense), encoding="utf-8")
    (plan_dir / "critique_output.json").write_text(
        json.dumps(schema_valid_sparse), encoding="utf-8"
    )

    outcome = _capture_recovered_output(
        "critique",
        plan_dir=plan_dir,
        output_path=output_path,
        raw="",
    )

    # The schema-invalid dense candidate should be excluded;
    # the schema-valid sparse candidate should win.
    assert outcome.legacy_payload == schema_valid_sparse


def test_recover_codex_payload_revise_uses_model_seam_schema_audit_path(
    tmp_path: Path,
) -> None:
    """Recovered revise payloads now flow through capture_step_output."""
    import json

    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    output_path = plan_dir / "revise_output.json"

    revise_payload = {
        "plan": "Revised plan text.",
        "changes_summary": "Summary of changes.",
        "flags_addressed": [],
        "assumptions": [],
        "success_criteria": [],
        "questions": [],
    }

    output_path.write_text(json.dumps(revise_payload), encoding="utf-8")

    outcome = _capture_recovered_output(
        "revise",
        plan_dir=plan_dir,
        output_path=output_path,
        raw="",
    )

    assert outcome.legacy_payload == revise_payload
    assert outcome.contract_result.provenance.sources == (
        "model_step_output",
        "codex_recovery:output_file",
    )


def test_recover_codex_payload_tiebreaker_challenger_uses_model_seam_schema_audit_path(
    tmp_path: Path,
) -> None:
    """A low-traffic long-tail seam still recovers through schema-audited capture."""
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    output_path = plan_dir / "tiebreaker_challenger_output.json"

    challenger_payload = {
        "measurements_vs_assumptions": "Observed constraints favor the alternate path.",
        "missing_options": [],
        "hard_cases": [],
        "reframings": [],
        "aging_analysis": "The incumbent choice degrades under future scale assumptions.",
        "counter_recommendation": {
            "option_name": "alternate-path",
            "rationale": "It holds up better under the measured hard cases.",
            "agrees_with_researcher": False,
        },
    }

    output_path.write_text(json.dumps(challenger_payload), encoding="utf-8")

    outcome = _capture_recovered_output(
        "tiebreaker_challenger",
        plan_dir=plan_dir,
        output_path=output_path,
        raw="",
    )

    assert outcome.legacy_payload == challenger_payload
    assert outcome.contract_result.payload["telemetry"]["audit_result"] == "passed"
    assert outcome.contract_result.provenance.sources == (
        "model_step_output",
        "codex_recovery:output_file",
    )


# ---------------------------------------------------------------------------
# T2: Long-tail allowlist cross-reference.
# ---------------------------------------------------------------------------


def test_long_tail_allowlist_matches_remaining_legacy_validate_payload_steps() -> None:
    """The T2 allowlist from test_contract_non_wiring must match the set of
    steps that validate_payload still accepts (non-migrated).

    All capture steps including execute are now retired from validate_payload
    and use schema-backed capture/audit instead.
    """
    from arnold.pipelines.megaplan.workers._impl import (
        _RETIRED_VALIDATE_PAYLOAD_STEPS,
        _STEP_REQUIRED_KEYS,
    )

    expected_retired = {
        "finalize", "critique", "review", "gate",
        "plan", "prep", "prep-triage", "prep-research", "prep-distill",
        "feedback", "critique_evaluator", "revise",
        "loop_plan", "loop_execute", "tiebreaker_researcher", "tiebreaker_challenger",
        "execute",
    }
    assert set(_RETIRED_VALIDATE_PAYLOAD_STEPS) == expected_retired, (
        f"validate_payload retires unexpected steps:\n"
        f"  Expected retired: {sorted(expected_retired)}\n"
        f"  Actually retired: {sorted(set(_RETIRED_VALIDATE_PAYLOAD_STEPS))}"
    )

    # All capture steps are now retired — validate_payload should accept no
    # known step names. The allowlist should be empty.
    known_legacy_accepts = set(_STEP_REQUIRED_KEYS.keys()) - set(_RETIRED_VALIDATE_PAYLOAD_STEPS)
    known_legacy_accepts.discard("execute")

    # Import the allowlist from test_contract_non_wiring
    from tests.test_contract_non_wiring import _M6_LONG_TAIL_ALLOWLIST

    assert known_legacy_accepts == set(_M6_LONG_TAIL_ALLOWLIST), (
        f"validate_payload legacy accept steps mismatch with allowlist:\n"
        f"  Legacy accepts:      {sorted(known_legacy_accepts)}\n"
        f"  Allowlist:           {sorted(set(_M6_LONG_TAIL_ALLOWLIST))}\n"
        f"  Extra in accepts:    {sorted(known_legacy_accepts - set(_M6_LONG_TAIL_ALLOWLIST))}\n"
        f"  Extra in allowlist:  {sorted(set(_M6_LONG_TAIL_ALLOWLIST) - known_legacy_accepts)}"
    )
