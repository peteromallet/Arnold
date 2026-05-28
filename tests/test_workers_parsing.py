"""Direct parsing and payload validation tests for megaplan.workers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from megaplan.types import CliError
from megaplan.workers import (
    _extract_claude_usage,
    _recover_codex_payload,
    extract_session_id,
    parse_claude_envelope,
    parse_json_file,
    validate_payload,
)


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
        (
            "revise",
            {
                "plan": "x",
                "changes_summary": "y",
                "flags_addressed": [],
                "assumptions": [],
                "success_criteria": [],
                "questions": [],
            },
        ),
        (
            "gate",
            {
                "recommendation": "PROCEED",
                "rationale": "ok",
                "signals_assessment": "ok",
                "warnings": [],
                "settled_decisions": [],
                "flag_resolutions": [],
                "accepted_tradeoffs": [],
            },
        ),
        (
            "finalize",
            {
                "tasks": [
                    {
                        "id": "T1",
                        "description": "Do work",
                        "depends_on": [],
                        "status": "pending",
                        "executor_notes": "",
                        "files_changed": [],
                        "commands_run": [],
                        "evidence_files": [],
                        "reviewer_verdict": "",
                    }
                ],
                "watch_items": [],
                "sense_checks": [
                    {
                        "id": "SC1",
                        "task_id": "T1",
                        "question": "Did it work?",
                        "executor_note": "",
                        "verdict": "",
                    }
                ],
                "user_actions": [],
                "meta_commentary": "ok",
                "validation": {
                    "plan_steps_covered": [{"plan_step_summary": "Do work", "finalize_item_ids": ["T1"]}],
                    "orphan_tasks": [],
                    "completeness_notes": "All covered.",
                    "coverage_complete": True,
                },
            },
        ),
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
        (
            "review",
            {
                "review_verdict": "approved",
                "checks": [],
                "pre_check_flags": [],
                "verified_flag_ids": [],
                "disputed_flag_ids": [],
                "criteria": [],
                "issues": [],
                "rework_items": [],
                "summary": "ok",
                "task_verdicts": [
                    {
                        "task_id": "T1",
                        "reviewer_verdict": "Pass",
                        "evidence_files": ["megaplan/workers.py"],
                    }
                ],
                "sense_check_verdicts": [{"sense_check_id": "SC1", "verdict": "Confirmed"}],
            },
        ),
    ],
)
def test_validate_payload_accepts_current_worker_steps(step: str, payload: dict[str, object]) -> None:
    validate_payload(step, payload)

def test_validate_payload_rejects_missing_gate_key() -> None:
    with pytest.raises(CliError, match="signals_assessment"):
        validate_payload(
            "gate",
            {
                "recommendation": "PROCEED",
                "rationale": "x",
                "warnings": [],
                "settled_decisions": [],
                "flag_resolutions": [],
                "accepted_tradeoffs": [],
            },
        )

def test_validate_payload_accepts_review_without_parallel_check_bookkeeping() -> None:
    validate_payload(
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
    )

def test_validate_payload_accepts_execute_batch_shape() -> None:
    validate_payload(
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

    recovered = _recover_codex_payload(
        "critique",
        plan_dir=plan_dir,
        output_path=output_path,
        raw="",
    )
    assert recovered == valid_payload

def test_recover_codex_payload_prefers_valid_output_file_over_raw_transcript(tmp_path: Path) -> None:
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

    recovered = _recover_codex_payload(
        "critique",
        plan_dir=plan_dir,
        output_path=output_path,
        raw=f"thinking...\n{json.dumps(raw_payload)}\n",
    )

    assert recovered == file_payload

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

    recovered = _recover_codex_payload(
        "critique",
        plan_dir=plan_dir,
        output_path=output_path,
        raw="",
    )

    assert recovered == completed_payload

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

    recovered = _recover_codex_payload(
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

    recovered = _recover_codex_payload(
        "critique",
        plan_dir=plan_dir,
        output_path=output_path,
        raw="",
    )

    assert recovered == complete_payload

def test_recover_codex_payload_normalizes_execute_batch_aliases(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    output_path = plan_dir / "execute_output.json"
    output_path.write_text(
        json.dumps(
            {
                "task_updates": [
                    {
                        "id": "T3",
                        "status": "completed",
                        "executor_notes": "Generated the template index.",
                        "files_changed": ["vibecomfy/template_index.json"],
                        "commands_run": ["python -m json.tool template_index.json"],
                    }
                ],
                "sense_check_acknowledgments": [
                    {
                        "id": "SC3",
                        "executor_note": "Template index count is 51.",
                        "verdict": "",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    recovered = _recover_codex_payload(
        "execute",
        plan_dir=plan_dir,
        output_path=output_path,
        raw="",
    )

    assert recovered is not None
    assert recovered["task_updates"][0]["task_id"] == "T3"
    assert recovered["task_updates"][0]["status"] == "done"
    assert recovered["sense_check_acknowledgments"][0]["sense_check_id"] == "SC3"

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

    recovered = _recover_codex_payload(
        "review",
        plan_dir=plan_dir,
        output_path=output_path,
        raw="",
    )

    assert recovered == {
        **valid_payload,
        "checks": [],
        "pre_check_flags": [],
        "verified_flag_ids": [],
        "disputed_flag_ids": [],
    }

def test_recover_codex_payload_reports_missing_required_keys_for_json_object(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    output_path = plan_dir / "plan_output.json"
    # Optional array keys present so the payload "looks like" a plan, but the
    # required string `plan` key is missing — the defensive-defaults block
    # only fills array keys, so validation still surfaces the gap.
    output_path.write_text(
        json.dumps({"questions": ["?"], "success_criteria": ["ok"], "assumptions": ["x"]}),
        encoding="utf-8",
    )

    with pytest.raises(CliError) as exc_info:
        _recover_codex_payload(
            "plan",
            plan_dir=plan_dir,
            output_path=output_path,
            raw="",
        )

    assert "plan output missing required keys" in exc_info.value.message
    assert "not valid JSON" not in exc_info.value.message

def test_validate_payload_critique_requires_flags() -> None:
    with pytest.raises(CliError, match="flags"):
        validate_payload("critique", {"verified_flag_ids": [], "disputed_flag_ids": []})

def test_validate_payload_execute_requires_output() -> None:
    with pytest.raises(CliError, match="output"):
        validate_payload(
            "execute",
            {"files_changed": [], "commands_run": [], "deviations": [], "sense_check_acknowledgments": []},
        )

def test_validate_payload_review_requires_criteria() -> None:
    with pytest.raises(CliError, match="criteria"):
        validate_payload(
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
